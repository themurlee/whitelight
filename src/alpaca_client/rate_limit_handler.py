import time
import logging
import threading
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderStatus
from alpaca.trading.stream import TradingStream
import src.config as config
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

# Thread-safe websocket state
_order_events = {}  # maps order_id (str) -> threading.Event
_order_results = {} # maps order_id (str) -> Order object
_events_lock = threading.Lock()
_stream = None
_stream_thread = None

def on_trade_update(data):
    """Callback when a trade update event is pushed from Alpaca."""
    try:
        order = data.order
        order_id = str(order.id)
        with _events_lock:
            if order_id in _order_events:
                _order_results[order_id] = order
                status_str = str(order.status.value).lower()
                if status_str in ["filled", "canceled", "expired", "rejected", "suspended"]:
                    _order_events[order_id].set()
    except Exception as e:
        logger.error(f"Error handling trade update callback: {e}")

def get_trading_stream():
    """Lazy initialize and start background trade update stream."""
    global _stream, _stream_thread
    if _stream is None:
        try:
            _stream = TradingStream(config.API_KEY, config.SECRET_KEY, paper=True)
            _stream.subscribe_trade_updates(on_trade_update)
            _stream_thread = threading.Thread(target=_stream.run, daemon=True)
            _stream_thread.start()
            logger.info("Alpaca TradingStream websocket active in background thread.")
        except Exception as e:
            logger.error(f"Failed to start Alpaca TradingStream: {e}")
    return _stream

def wait_for_order_fill_websocket(trading_client: TradingClient, order_id: str, timeout_sec: float = 300.0) -> Any:
    """Wait for order fill/termination using background Trade Updates Websocket (non-polling)."""
    get_trading_stream()
    
    # Check if we already received a trade update for this order
    with _events_lock:
        if order_id in _order_results:
            order_res = _order_results[order_id]
            status_str = str(order_res.status.value).lower()
            if status_str in ["filled", "canceled", "expired", "rejected", "suspended"]:
                return order_res

        # If not already received, register event
        event = threading.Event()
        _order_events[order_id] = event

    # Block on event (blocks at OS level, not busy loop/sleep polling)
    completed = event.wait(timeout=timeout_sec)
    
    # Retrieve result if event fired
    order_res = None
    with _events_lock:
        order_res = _order_results.get(order_id)
        _order_events.pop(order_id, None)
        _order_results.pop(order_id, None)

    # Fallback to direct REST API query if websocket notification was missed or timed out
    if order_res is None:
        try:
            logger.info(f"Websocket wait for order {order_id} timed out or missed. Performing fallback REST query.")
            order_res = trading_client.get_order_by_id(order_id)
        except Exception as e:
            logger.error(f"Fallback REST query failed for order {order_id}: {e}")
            raise TimeoutError(f"Order {order_id} did not complete in {timeout_sec}s")

    return order_res
