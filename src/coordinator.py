"""
coordinator.py — Systematic Trading Pipeline Coordinator

Chains: Ingest → Signal → Execute for one or more tickers in sequence.
"""
import os
import sys
import argparse
import uuid
from datetime import datetime, timezone
from alpaca.trading.client import TradingClient

# Configure path so src.* imports work from project root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

import src.config as config
from src.ingest import fetch_and_save_ohlcv
from src.signal_generator import run_signal_generation
from src.executor import execute_signal
from src.risk.circuit_breaker import CircuitBreaker, RiskParams
from src.monitoring.metrics_exporter import MetricsExporter
from src.alerting.slack_notifier import post_alert
from src.storage.atomic_writer import AtomicJSONWriter

# --- Default tickers to run if none provided via CLI ---
DEFAULT_TICKERS = ["SPY"]

def log(msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [COORDINATOR] [{level}] {msg}")

def run_pipeline(tickers: list[str], dry_run: bool = False, skip_ingest: bool = False) -> dict:
    results = {}
    cycle_id = str(uuid.uuid4())

    log(f"Pipeline starting. Cycle ID: {cycle_id} | Tickers: {tickers} | dry_run={dry_run} | skip_ingest={skip_ingest}")
    post_alert(f"🚀 [whitelight] Pipeline cycle started: {cycle_id} for tickers: {tickers}")
    log("=" * 60)

    # Initialize client to fetch account stats for risk checks
    trading_client = None
    account_value = 100000.0
    open_tickers = []
    if config.API_KEY and config.SECRET_KEY:
        try:
            trading_client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
            account = trading_client.get_account()
            account_value = float(account.portfolio_value)
            positions = trading_client.get_all_positions()
            open_tickers = [p.symbol for p in positions]
        except Exception as e:
            log(f"Failed to fetch account info from Alpaca: {e}", "WARNING")

    # Load peak equity baseline for CircuitBreaker
    state_file = os.path.join(config.DATA_DIR, "state.json")
    baseline = account_value
    if os.path.exists(state_file):
        try:
            state_data = AtomicJSONWriter(state_file).read()
            if isinstance(state_data, dict):
                baseline = float(state_data.get("peak_equity", account_value))
        except Exception:
            pass
            
    cb = CircuitBreaker(baseline_account_value=baseline)

    for ticker in tickers:
        log(f"--- [{ticker}] BEGIN ---")
        ticker_result = {"ingest": None, "signal": None, "execution": None}

        # Step 1: Ingest
        if skip_ingest:
            log(f"[{ticker}] Ingest skipped (--no-ingest flag)")
            ticker_result["ingest"] = "skipped"
        else:
            log(f"[{ticker}] Step 1/3: Ingesting OHLCV data...")
            success = fetch_and_save_ohlcv(ticker)
            if not success:
                log(f"[{ticker}] Ingest failed. Aborting this ticker.", "ERROR")
                ticker_result["ingest"] = "failed"
                results[ticker] = ticker_result
                continue
            ticker_result["ingest"] = "ok"
            log(f"[{ticker}] Ingest complete.")

        # Step 2: Signal Generation
        log(f"[{ticker}] Step 2/3: Calculating indicators & generating signal...")
        signal = run_signal_generation(ticker)
        if "error" in signal:
            log(f"[{ticker}] Signal generation failed: {signal['error']}", "ERROR")
            ticker_result["signal"] = "failed"
            results[ticker] = ticker_result
            continue

        ticker_result["signal"] = signal["action"]
        log(f"[{ticker}] Signal: {signal['action']} | Close: {signal['close']} | RSI: {signal['rsi']} | MACD Hist: {signal['macd_histogram']}")

        # Step 3: Execution Gating and Submission
        if signal["action"] == "HOLD":
            log(f"[{ticker}] Step 3/3: Signal is HOLD. No execution action taken.")
            ticker_result["execution"] = "skipped_hold"
        elif dry_run:
            log(f"[{ticker}] Step 3/3: Dry-run — skipping order submission.")
            ticker_result["execution"] = "dry_run"
        else:
            log(f"[{ticker}] Step 3/3: Gating trade signal through Risk Circuit Breaker...")
            close_price = float(signal["close"])
            max_alloc = account_value * 0.05
            qty = int(max_alloc // close_price)
            if qty <= 0:
                qty = 1

            # Gating check
            allowed, cb_reason = cb.can_execute(
                ticker=ticker,
                qty=qty,
                price=close_price,
                account_value=account_value,
                open_tickers=open_tickers
            )
            if not allowed:
                log(f"[{ticker}] Execution blocked by Risk Circuit Breaker: {cb_reason}", "WARNING")
                ticker_result["execution"] = f"blocked: {cb_reason}"
            else:
                log(f"[{ticker}] Step 3/3: Executing signal via Alpaca paper trading...")
                execute_signal(cycle_id)
                ticker_result["execution"] = "submitted"
                log(f"[{ticker}] Execution complete. Check trade_log.md for order details.")

        log(f"--- [{ticker}] END ---")
        results[ticker] = ticker_result

    # Step 4: Export P&L Metrics to Prometheus Format
    open_pnl = 0.0
    closed_pnl = 0.0
    win_rate = 0.0
    if trading_client:
        try:
            positions = trading_client.get_all_positions()
            open_pnl = sum([float(p.unrealized_intraday_pl or 0.0) for p in positions])
        except Exception:
            pass
            
    history_file = os.path.join(config.DATA_DIR, "trade_history.json")
    if os.path.exists(history_file):
        try:
            trades = AtomicJSONWriter(history_file).read()
            if isinstance(trades, list) and trades:
                closed_pnl = sum([float(t.get("pnl", 0.0)) for t in trades])
                wins = sum([1 for t in trades if float(t.get("pnl", 0.0)) > 0])
                win_rate = wins / len(trades)
        except Exception:
            pass
            
    try:
        MetricsExporter().export_metrics(account_value, open_pnl, closed_pnl, win_rate)
        log(f"Exported Prometheus metrics successfully.")
    except Exception as e:
        log(f"Failed to export metrics: {e}", "ERROR")

    # Summary
    log("=" * 60)
    log("Pipeline Summary:")
    summary_lines = []
    for ticker, res in results.items():
        line = f"  {ticker}: ingest={res['ingest']} | signal={res['signal']} | execution={res['execution']}"
        log(line)
        summary_lines.append(line)
    log("Pipeline complete.")

    post_alert(f"🏁 [whitelight] Pipeline cycle complete: {cycle_id}\n" + "\n".join(summary_lines))
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WhiteLight Systematic Trading Pipeline Coordinator")
    parser.add_argument("tickers", nargs="*", help="Ticker symbols to process (default: SPY)")
    parser.add_argument("--dry-run", action="store_true", help="Calculate signals but skip order execution")
    parser.add_argument("--no-ingest", action="store_true", help="Skip data ingestion; use existing local files")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers] if args.tickers else DEFAULT_TICKERS
    run_pipeline(tickers, dry_run=args.dry_run, skip_ingest=args.no_ingest)
