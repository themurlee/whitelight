import time
import logging
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderStatus
from src.alpaca_client.retry_decorator import alpaca_retryable

logger = logging.getLogger("AlpacaRateLimit")

@alpaca_retryable(max_retries=5, base_delay=1.0)
def get_order_with_retry(trading_client: TradingClient, order_id: str):
    return trading_client.get_order_by_id(order_id)

def wait_for_order_fill(trading_client: TradingClient, order_id: str, timeout_sec: float = 300.0, poll_interval_sec: float = 2.0):
    """Poll Alpaca order status until filled, cancelled, or timed out."""
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        try:
            order = get_order_with_retry(trading_client, order_id)
            status = order.status
            if status == OrderStatus.FILLED:
                logger.info(f"Order {order_id} filled successfully.")
                return order
            if status in [OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED]:
                logger.error(f"Order {order_id} failed with status: {status}")
                return order
            time.sleep(poll_interval_sec)
        except Exception as e:
            logger.warning(f"Error polling order {order_id}: {e}")
            time.sleep(poll_interval_sec)
    raise TimeoutError(f"Order {order_id} fill polling timed out after {timeout_sec}s")
