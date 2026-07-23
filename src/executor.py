import os
import json
import sys
from datetime import datetime, timezone

# Configure path imports
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

import src.config as config
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from src.storage.atomic_writer import AtomicJSONWriter
from src.alpaca_client.retry_decorator import alpaca_retryable
from src.alpaca_client.rate_limit_handler import wait_for_order_fill
from src.execution.limit_order_wrapper import execute_signal_with_slippage_control, SUBMISSION_LOCK
from src.risk.circuit_breaker import CircuitBreaker, RiskParams
from src.risk.position_sizer import get_vix_adjusted_quantity
from src.state.execution_journal import ExecutionJournal, ExecutionState
from src.alerting.slack_notifier import post_alert

@alpaca_retryable(max_retries=5, base_delay=1.0)
def _get_open_position_with_retry(client, ticker):
    return client.get_open_position(ticker)

@alpaca_retryable(max_retries=5, base_delay=1.0)
def _get_orders_with_retry(client, orders_req):
    return client.get_orders(orders_req)

@alpaca_retryable(max_retries=5, base_delay=1.0)
def _cancel_order_with_retry(client, order_id):
    return client.cancel_order_by_id(order_id)

@alpaca_retryable(max_retries=5, base_delay=1.0)
def _get_account_with_retry(client):
    return client.get_account()

@alpaca_retryable(max_retries=5, base_delay=1.0)
def _submit_order_with_retry(client, order_data):
    return client.submit_order(order_data)

import fcntl

def log_to_journal(message: str, level: str = "INFO"):
    os.makedirs(config.JOURNAL_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log_line = f"[{timestamp}] [{level}] {message}\n"
    
    lockfile = config.TRADE_LOG_PATH + ".lock"
    try:
        fd = os.open(lockfile, os.O_CREAT | os.O_WRONLY, 0o666)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            with open(config.TRADE_LOG_PATH, "a") as f:
                f.write(log_line)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
    except Exception:
        with open(config.TRADE_LOG_PATH, "a") as f:
            f.write(log_line)
            
    print(f"[{level}] {message}")

import uuid

def execute_signal(cycle_id: str = None):
    signal_log_path = os.path.join(config.DATA_DIR, "signal_log.json")
    if not os.path.exists(signal_log_path):
        log_to_journal("No signal_log.json found. Skipping execution.", "WARNING")
        return

    try:
        signal_data = AtomicJSONWriter(signal_log_path).read()
        if not signal_data:
            log_to_journal("signal_log.json is empty.", "WARNING")
            return
    except Exception as e:
        log_to_journal(f"Failed to read signal_log.json: {e}", "ERROR")
        return

    ticker = signal_data.get("ticker")
    action = signal_data.get("action")
    close_price = signal_data.get("close")
    
    if not ticker or not action or not close_price:
        log_to_journal(f"Invalid signal data structure: {signal_data}", "ERROR")
        return

    # Check Execution Journal for Idempotency
    journal = ExecutionJournal()
    if cycle_id and journal.was_executed_this_cycle(ticker, cycle_id):
        log_to_journal(f"Idempotency Guard: Ticker {ticker} already executed in run cycle {cycle_id}. Skipping execution.", "WARNING")
        return

    if action == "HOLD":
        log_to_journal(f"Signal is HOLD for {ticker}. No execution action taken.", "INFO")
        return

    if not config.API_KEY or not config.SECRET_KEY:
        log_to_journal("Alpaca credentials missing in configuration", "ERROR")
        return

    try:
        trading_client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
        
        # Acquire lock to ensure atomic risk checking and order submission
        SUBMISSION_LOCK.acquire()
        lock_released = False
        try:
            # 1. Query existing position & open orders
            position = None
            try:
                position = _get_open_position_with_retry(trading_client, ticker)
            except Exception:
                pass

            open_orders = []
            try:
                orders_req = GetOrdersRequest(
                    status=QueryOrderStatus.OPEN,
                    symbols=[ticker]
                )
                open_orders = _get_orders_with_retry(trading_client, orders_req)
            except Exception as e:
                log_to_journal(f"Failed to query open orders for {ticker}: {e}", "WARNING")
                
            # Cancel any open orders for this ticker to avoid wash sales or conflict rejections
            if open_orders:
                log_to_journal(f"Cancelling {len(open_orders)} existing open orders for {ticker} before executing new action...", "INFO")
                for o in open_orders:
                    try:
                        _cancel_order_with_retry(trading_client, o.id)
                    except Exception as ex:
                        log_to_journal(f"Failed to cancel order {o.id}: {ex}", "WARNING")
                import time
                time.sleep(1.5)

            # Query account and open positions for risk gates
            account = _get_account_with_retry(trading_client)
            portfolio_value = float(account.portfolio_value)
            
            state_file = os.path.join(config.DATA_DIR, "state.json")
            baseline = portfolio_value
            state_data = {}
            if os.path.exists(state_file):
                try:
                    state_data = AtomicJSONWriter(state_file).read()
                    if isinstance(state_data, dict):
                        baseline = float(state_data.get("peak_equity", portfolio_value))
                except Exception:
                    pass

            # Dynamic HWM peak baseline update
            if portfolio_value > baseline:
                log_to_journal(f"New Peak Equity HWM: ${portfolio_value:.2f} (previous baseline: ${baseline:.2f}). Updating state.json.", "INFO")
                baseline = portfolio_value
                if not isinstance(state_data, dict):
                    state_data = {}
                state_data["peak_equity"] = baseline
                try:
                    AtomicJSONWriter(state_file).write(state_data)
                except Exception as se:
                    log_to_journal(f"Failed to save peak equity state: {se}", "WARNING")

            cb = CircuitBreaker(baseline_account_value=baseline)
            
            open_tickers = []
            try:
                positions = trading_client.get_all_positions()
                open_tickers = [p.symbol for p in positions]
            except Exception:
                pass

            # 2. Risk Management & Execution Logic
            if action == "BUY":
                if position is not None:
                    log_to_journal(f"BUY signal received for {ticker}, but position already exists (Qty: {position.qty}). Skipping purchase.", "WARNING")
                    SUBMISSION_LOCK.release()
                    lock_released = True
                    return

                # Risk metric: max position size 5% of portfolio equity
                max_allocation = portfolio_value * 0.05
                qty = int(max_allocation // close_price)
                if qty <= 0:
                    qty = 1
                    
                # Circuit Breaker validation
                allowed, cb_reason = cb.can_execute(
                    ticker=ticker,
                    qty=qty,
                    price=close_price,
                    account_value=portfolio_value,
                    open_tickers=open_tickers
                )
                if not allowed:
                    log_to_journal(f"Risk Circuit Breaker Refused Execution: {cb_reason}", "ERROR")
                    post_alert(f"⚠️ [whitelight] BUY Order Refused by Risk Framework for {ticker}: {cb_reason}")
                    SUBMISSION_LOCK.release()
                    lock_released = True
                    return

                # VIX Volatility Sizing Adjustment
                adjusted_qty = get_vix_adjusted_quantity(qty)
                log_to_journal(f"Original Qty: {qty} | Volatility Adjusted Qty: {adjusted_qty}", "INFO")
                
                # Send Slack Signal Alert
                post_alert(f"🟢 [whitelight] BUY Signal for {ticker} (Close: ${close_price}, Qty: {adjusted_qty})")

                try:
                    success = execute_signal_with_slippage_control(
                        trading_client, ticker, close_price, adjusted_qty, "BUY", submission_lock=SUBMISSION_LOCK
                    )
                    lock_released = True
                    if success:
                        post_alert(f"🎯 [whitelight] BUY Order FILLED for {ticker}: Qty={adjusted_qty}, Price=${close_price:.2f}")
                        if cycle_id:
                            journal.log_execution(ExecutionState(
                                cycle_id=cycle_id,
                                timestamp=datetime.now(timezone.utc),
                                ticker=ticker,
                                action="BUY",
                                qty=adjusted_qty,
                                order_id=f"order_{uuid.uuid4().hex[:8]}",
                                status="filled",
                                fill_price=close_price
                            ))
                except Exception as fe:
                    log_to_journal(f"BUY Order execution failed: {fe}", "ERROR")
                    post_alert(f"❌ [whitelight] BUY Execution Failed for {ticker}: {fe}")

            elif action == "SELL":
                if position is None:
                    log_to_journal(f"SELL signal received for {ticker}, but no open position exists. Skipping liquidation.", "WARNING")
                    SUBMISSION_LOCK.release()
                    lock_released = True
                    return
                    
                qty_to_sell = int(position.qty)
                
                # Send Slack Signal Alert
                post_alert(f"🔴 [whitelight] SELL Signal for {ticker} (Close: ${close_price}, Qty: {qty_to_sell})")

                try:
                    success = execute_signal_with_slippage_control(
                        trading_client, ticker, close_price, qty_to_sell, "SELL", submission_lock=SUBMISSION_LOCK
                    )
                    lock_released = True
                    if success:
                        post_alert(f"🎯 [whitelight] SELL Order FILLED for {ticker}: Qty={qty_to_sell}, Price=${close_price:.2f}")
                        if cycle_id:
                            journal.log_execution(ExecutionState(
                                cycle_id=cycle_id,
                                timestamp=datetime.now(timezone.utc),
                                ticker=ticker,
                                action="SELL",
                                qty=qty_to_sell,
                                order_id=f"order_{uuid.uuid4().hex[:8]}",
                                status="filled",
                                fill_price=close_price
                            ))
                except Exception as fe:
                    log_to_journal(f"SELL Order execution failed: {fe}", "ERROR")
                    post_alert(f"❌ [whitelight] SELL Execution Failed for {ticker}: {fe}")
        finally:
            if not lock_released:
                try:
                    SUBMISSION_LOCK.release()
                except RuntimeError:
                    pass
    except Exception as e:
        log_to_journal(f"Execution failed: {e}", "ERROR")

if __name__ == "__main__":
    execute_signal()
