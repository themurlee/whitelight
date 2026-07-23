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
            position = trading_client.get_open_position(ticker)
        except Exception:
            pass

        open_orders = []
        try:
            orders_req = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                symbols=[ticker]
            )
            open_orders = trading_client.get_orders(orders_req)
        except Exception as e:
            log_to_journal(f"Failed to query open orders for {ticker}: {e}", "WARNING")
            
        # Cancel any open orders for this ticker to avoid wash sales or conflict rejections
        if open_orders:
            log_to_journal(f"Cancelling {len(open_orders)} existing open orders for {ticker} before executing new action...", "INFO")
            for o in open_orders:
                try:
                    trading_client.cancel_order_by_id(o.id)
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
            account = trading_client.get_account()
            portfolio_value = float(account.portfolio_value)
            max_allocation = portfolio_value * 0.05
            
            # Target share quantity
            qty = int(max_allocation // close_price)
            if qty <= 0:
                qty = 1 # Fallback to 1 share
                
            log_to_journal(f"Risk Check Passed: Allocating {qty} shares of {ticker} (Value: ${qty * close_price:.2f} <= Max allocation: ${max_allocation:.2f})", "INFO")
            
            # Submit Buy Order
            order_data = MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC
            )
            order = trading_client.submit_order(order_data)
            log_to_journal(f"BUY Order Submitted successfully: ID={order.id}, Qty={qty}, Status={order.status}", "INFO")

        elif action == "SELL":
            if position is None:
                log_to_journal(f"SELL signal received for {ticker}, but no open position exists. Skipping liquidation.", "WARNING")
                return
                
            qty_to_sell = int(position.qty)
            log_to_journal(f"Risk Check: Liquidating position of {qty_to_sell} shares of {ticker}.", "INFO")
            
            # Submit Sell Order
            order_data = MarketOrderRequest(
                symbol=ticker,
                qty=qty_to_sell,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC
            )
            order = trading_client.submit_order(order_data)
            log_to_journal(f"SELL Order Submitted successfully: ID={order.id}, Qty={qty_to_sell}, Status={order.status}", "INFO")

    except Exception as e:
        log_to_journal(f"Execution failed: {e}", "ERROR")

if __name__ == "__main__":
    execute_signal()
