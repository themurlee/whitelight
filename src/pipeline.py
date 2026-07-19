"""
WhiteLight Systematic Trading & Analysis Pipeline - Core Coordinator
Coordinates live market data fetch, systematic indicator calculations, option chain filtering,
safeguarded order routing, risk management checks, and journaling.
"""

import argparse
import sys
import os
from datetime import datetime

# Configure path imports
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from src.strategy import calculate_ema, calculate_vwap, calculate_macd
from src.selector import filter_options_chain
from src.execution import RobinhoodMCPClient, RiskManager, execute_order_safely
from src.journal import log_trade, log_error, log_state_transition, generate_daily_journal_template


def run_pipeline(ticker: str, dry_run: bool):
    """
    Runs the systematic trading pipeline for a given ticker.
    """
    print(f"[{datetime.utcnow().isoformat()}] Starting WhiteLight systematic pipeline for {ticker}...")
    
    # 1. Initialize & Start API Client
    client = RobinhoodMCPClient(dry_run=dry_run)
    client.start()
    
    risk_manager = RiskManager(client)
    
    # 2. Daily Journal Auto-Generation
    journal_path = generate_daily_journal_template()
    print(f"[JOURNAL] Ensured daily qualitative journal template at: {journal_path}")
    
    # 3. Perform 15-minute Risk Circuit Breaker Check
    print("[RISK] Running rolling 7D drawdown circuit breaker audit...")
    is_locked, drawdown = risk_manager.verify_and_update_drawdown()
    if is_locked:
        print(f"[RISK WARNING] System is locked down due to drawdown ({drawdown*100:.2f}% >= 15.00%). Terminating cycle.")
        client.stop()
        return

    # 4. Fetch Market Data & Calculate Systematic Signals
    print(f"[MARKET] Fetching historical bar data for {ticker}...")
    bars_data = client.get_historical_bars(ticker)
    
    if not bars_data:
        print(f"[MARKET ERROR] Failed to retrieve historical bar data for {ticker}. Aborting.")
        client.stop()
        return

    prices = [b["close"] for b in bars_data]
    
    if len(prices) < 250:
        print(f"[MARKET ERROR] Insufficient historical price bars ({len(prices)} < 250). Aborting.")
        client.stop()
        return

    # Calculate indicators
    ema_50 = calculate_ema(prices, 50)[-1]
    ema_250 = calculate_ema(prices, 250)[-1]
    
    # Use intraday/last session bars for VWAP (e.g. the last 78 bars of 5-minute ticks representing 6.5 hours of a session)
    session_bars = bars_data[-78:] if len(bars_data) >= 78 else bars_data
    vwap = calculate_vwap(session_bars)[-1]
    current_price = prices[-1]

    print(f"[STRATEGY] {ticker} Metrics -> Close: ${current_price:.2f} | EMA50: ${ema_50:.2f} | EMA250: ${ema_250:.2f} | VWAP: ${vwap:.2f}")

    # Determine Signal Crossovers
    signal_type = None
    if ema_50 > ema_250 and current_price > vwap:
        signal_type = "call"
        print(f"[SIGNAL] {ticker} is BULLISH (EMA50 > EMA250 & Price > VWAP)")
    elif ema_50 < ema_250 and current_price < vwap:
        signal_type = "put"
        print(f"[SIGNAL] {ticker} is BEARISH (EMA50 < EMA250 & Price < VWAP)")
    else:
        print(f"[SIGNAL] {ticker} is NEUTRAL. No option leg action taken.")
        client.stop()
        return

    # 5. Retrieve Options Chain and Filter for Target Leg (30 DTE, 0.40 Delta)
    print(f"[SELECTOR] Querying valid options expirations for {ticker}...")
    expirations = client.get_expiration_dates(ticker)
    if not expirations:
        print("[SELECTOR ERROR] Failed to fetch expiration dates. Aborting.")
        client.stop()
        return
        
    # Find closest expiration to 30 DTE
    current_date_str = datetime.utcnow().strftime("%Y-%m-%d")
    from src.selector import calculate_dte
    
    best_exp_date = None
    min_dte_diff = float("inf")
    for exp in expirations:
        try:
            dte = calculate_dte(exp, current_date_str)
            if dte >= 0:
                diff = abs(dte - 30)
                if diff < min_dte_diff:
                    min_dte_diff = diff
                    best_exp_date = exp
        except ValueError:
            continue
            
    if not best_exp_date:
        print("[SELECTOR ERROR] Could not calculate optimal expiration date. Aborting.")
        client.stop()
        return
        
    print(f"[SELECTOR] Selected optimal expiration: {best_exp_date} (closest to 30 DTE)")
    
    print(f"[SELECTOR] Fetching options chain for {ticker} {signal_type.upper()} on {best_exp_date}...")
    options_chain = client.get_options_chain(ticker, best_exp_date)

    selected_contract = filter_options_chain(
        contracts=options_chain,
        option_type=signal_type,
        current_date_str=current_date_str,
        target_dte=30,
        target_delta=0.40
    )

    if not selected_contract:
        print("[SELECTOR WARNING] No option contract matched target parameters.")
        client.stop()
        return

    print(f"[SELECTOR] Selected optimal contract: {selected_contract['symbol']} (Delta: {selected_contract['delta']})")

    # 6. Execute Systematic Leg Order Safely
    print(f"[EXECUTION] Submitting trade to acquire 1 contract of {selected_contract['symbol']}...")
    order_res = execute_order_safely(
        client=client,
        risk_manager=risk_manager,
        symbol=selected_contract["symbol"],
        quantity=1,
        side="buy",
        option_type=signal_type,
        strike_price=selected_contract["strike_price"],
        expiration_date=selected_contract["expiration_date"]
    )

    if order_res and order_res.get("status") == "placed":
        print(f"[EXECUTION SUCCESS] Position acquired successfully. Order ID: {order_res['order_id']}")
        
        # Log to trade_history.json
        log_trade(
            action="BUY",
            symbol=selected_contract["symbol"],
            quantity=1,
            price=selected_contract.get("strike_price"),
            details={"strategy": "EMA_VWAP_crossover", "order_id": order_res["order_id"]}
        )
    else:
        print("[EXECUTION FAILED] Order routing failed or circuit breaker blocked trade.")
        
    client.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WhiteLight Pipeline Coordinator")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Ticker symbol to analyze")
    parser.add_argument("--live", action="store_true", help="Connect to live Robinhood API (disable dry run)")
    args = parser.parse_args()

    try:
        run_pipeline(ticker=args.ticker, dry_run=not args.live)
    except Exception as e:
        import traceback
        err_msg = str(e)
        tb = traceback.format_exc()
        print(f"[CRITICAL ERROR] {err_msg}\n{tb}", file=sys.stderr)
        log_error(err_msg, tb, {"ticker": args.ticker})
