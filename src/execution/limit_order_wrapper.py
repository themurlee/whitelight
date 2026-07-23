import time
import logging
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from src.execution.slippage_validator import SlippageConfig, get_current_bid_ask, validate_slippage
from src.alpaca_client.rate_limit_handler import wait_for_order_fill
from src.alpaca_client.retry_decorator import alpaca_retryable

logger = logging.getLogger("LimitOrderWrapper")

@alpaca_retryable(max_retries=5, base_delay=1.0)
def _submit_limit_order_with_retry(trading_client, order_data):
    return trading_client.submit_order(order_data)

@alpaca_retryable(max_retries=5, base_delay=1.0)
def _cancel_order_with_retry(trading_client, order_id):
    return trading_client.cancel_order_by_id(order_id)

@alpaca_retryable(max_retries=5, base_delay=1.0)
def _submit_market_order_with_retry(trading_client, order_data):
    return trading_client.submit_order(order_data)

def execute_signal_with_slippage_control(
    trading_client,
    ticker: str, 
    signal_close: float,
    qty: int,
    side: str,
    slippage_config: SlippageConfig = SlippageConfig()
) -> bool:
    """Execute order with dynamic quote spread checks and slippage limits."""
    # 1. Fetch live quotes
    bid, ask = get_current_bid_ask(ticker)
    
    # 2 & 3. Validate spread & slippage (raises exception on breach)
    validate_slippage(ticker, signal_close, side, bid, ask, slippage_config)
    
    # 4. Calculate limit price with offset
    offset = slippage_config.limit_order_offset_bps / 10000.0
    order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
    
    if order_side == OrderSide.BUY:
        limit_price = round(ask * (1 + offset), 2)
    else:
        limit_price = round(bid * (1 - offset), 2)
        
    # 5. Submit Limit order
    if slippage_config.use_limit_orders:
        order_data = LimitOrderRequest(
            symbol=ticker,
            qty=qty,
            limit_price=limit_price,
            side=order_side,
            time_in_force=TimeInForce.DAY
        )
        order = _submit_limit_order_with_retry(trading_client, order_data)
        logger.info(f"Submitted limit order for {ticker}: ID={order.id}, Limit Price={limit_price}, Qty={qty}")
        
        # Poll for fill status for up to 5 minutes (300 seconds)
        try:
            filled_order = wait_for_order_fill(trading_client, order.id, timeout_sec=300.0, poll_interval_sec=2.0)
            if filled_order.status.value in ["filled", "FILLED"]:
                logger.info(f"Limit order {order.id} filled successfully.")
                return True
            else:
                logger.warning(f"Limit order {order.id} finished with status {filled_order.status}. Cancelling and falling back to market order.")
        except TimeoutError:
            logger.warning(f"Limit order {order.id} did not fill in 5 minutes. Cancelling and falling back to market order.")
            try:
                _cancel_order_with_retry(trading_client, order.id)
                time.sleep(2)
            except Exception as ce:
                logger.error(f"Failed to cancel unfilled limit order {order.id}: {ce}")
        
        # Fallback to Market order
        logger.info(f"Submitting fallback market order for {ticker}, Qty={qty}")
        mkt_order_data = MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.GTC
        )
        mkt_order = _submit_market_order_with_retry(trading_client, mkt_order_data)
        try:
            wait_for_order_fill(trading_client, mkt_order.id, timeout_sec=60.0, poll_interval_sec=1.0)
            logger.info(f"Fallback market order {mkt_order.id} filled.")
            return True
        except Exception as me:
            logger.error(f"Fallback market order failed to fill: {me}")
            raise me
    else:
        mkt_order_data = MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.GTC
        )
        mkt_order = _submit_market_order_with_retry(trading_client, mkt_order_data)
        wait_for_order_fill(trading_client, mkt_order.id, timeout_sec=60.0, poll_interval_sec=1.0)
        return True
