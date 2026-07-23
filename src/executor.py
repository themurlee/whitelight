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
from src.execution.limit_order_wrapper import execute_signal_with_slippage_control

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

def log_to_journal(message: str, level: str = "INFO"):
    os.makedirs(config.JOURNAL_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log_line = f"[{timestamp}] [{level}] {message}\n"
    with open(config.TRADE_LOG_PATH, "a") as f:
        f.write(log_line)
    print(f"[{level}] {message}")

def execute_signal():
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

    if action == "HOLD":
        log_to_journal(f"Signal is HOLD for {ticker}. No execution action taken.", "INFO")
        return

    if not config.API_KEY or not config.SECRET_KEY:
        log_to_journal("Alpaca credentials missing in configuration", "ERROR")
        return

    try:
        trading_client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
        
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

        # 2. Risk Management & Execution Logic
        if action == "BUY":
            if position is not None:
                log_to_journal(f"BUY signal received for {ticker}, but position already exists (Qty: {position.qty}). Skipping purchase.", "WARNING")
                return

            # Risk metric: max position size 5% of portfolio equity
            account = _get_account_with_retry(trading_client)
            portfolio_value = float(account.portfolio_value)
            max_allocation = portfolio_value * 0.05
            
            # Target share quantity
            qty = int(max_allocation // close_price)
            if qty <= 0:
                qty = 1 # Fallback to 1 share
                
            log_to_journal(f"Risk Check Passed: Allocating {qty} shares of {ticker} (Value: ${qty * close_price:.2f} <= Max allocation: ${max_allocation:.2f})", "INFO")
            
            try:
                execute_signal_with_slippage_control(trading_client, ticker, close_price, qty, "BUY")
            except Exception as fe:
                log_to_journal(f"BUY Order execution failed: {fe}", "ERROR")

        elif action == "SELL":
            if position is None:
                log_to_journal(f"SELL signal received for {ticker}, but no open position exists. Skipping liquidation.", "WARNING")
                return
                
            qty_to_sell = int(position.qty)
            log_to_journal(f"Risk Check: Liquidating position of {qty_to_sell} shares of {ticker}.", "INFO")
            
            try:
                execute_signal_with_slippage_control(trading_client, ticker, close_price, qty_to_sell, "SELL")
            except Exception as fe:
                log_to_journal(f"SELL Order execution failed: {fe}", "ERROR")

    except Exception as e:
        log_to_journal(f"Execution failed: {e}", "ERROR")

if __name__ == "__main__":
    execute_signal()
