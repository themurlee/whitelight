"""
coordinator.py — Systematic Trading Pipeline Coordinator

Chains: Ingest → Signal → Execute for one or more tickers in sequence.

Usage:
    python3 src/coordinator.py SPY AAPL MSFT
    python3 src/coordinator.py SPY              # single ticker
    python3 src/coordinator.py                  # defaults to tickers in config

Flags:
    --dry-run     Calculate signals but skip order execution
    --no-ingest   Skip data ingestion (use existing local data)
"""
import os
import sys
import argparse
from datetime import datetime, timezone

# Configure path so src.* imports work from project root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

import src.config as config
from src.ingest import fetch_and_save_ohlcv
from src.signal_generator import run_signal_generation
from src.executor import execute_signal


# --- Default tickers to run if none provided via CLI ---
DEFAULT_TICKERS = ["SPY"]


def log(msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [COORDINATOR] [{level}] {msg}")


def run_pipeline(tickers: list[str], dry_run: bool = False, skip_ingest: bool = False) -> dict:
    results = {}

    log(f"Pipeline starting. Tickers: {tickers} | dry_run={dry_run} | skip_ingest={skip_ingest}")
    log("=" * 60)

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

        # Step 3: Execution
        if dry_run:
            log(f"[{ticker}] Step 3/3: Dry-run — skipping order submission.")
            ticker_result["execution"] = "dry_run"
        else:
            log(f"[{ticker}] Step 3/3: Executing signal via Alpaca paper trading...")
            execute_signal()
            ticker_result["execution"] = "submitted"
            log(f"[{ticker}] Execution complete. Check trade_log.md for order details.")

        log(f"--- [{ticker}] END ---")
        results[ticker] = ticker_result

    # Summary
    log("=" * 60)
    log("Pipeline Summary:")
    for ticker, res in results.items():
        log(f"  {ticker}: ingest={res['ingest']} | signal={res['signal']} | execution={res['execution']}")
    log("Pipeline complete.")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WhiteLight Systematic Trading Pipeline Coordinator")
    parser.add_argument("tickers", nargs="*", help="Ticker symbols to process (default: SPY)")
    parser.add_argument("--dry-run", action="store_true", help="Calculate signals but skip order execution")
    parser.add_argument("--no-ingest", action="store_true", help="Skip data ingestion; use existing local files")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers] if args.tickers else DEFAULT_TICKERS
    run_pipeline(tickers, dry_run=args.dry_run, skip_ingest=args.no_ingest)
