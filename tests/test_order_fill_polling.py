import time
from unittest.mock import patch, MagicMock
from alpaca.trading.enums import OrderStatus
from src.alpaca_client.rate_limit_handler import wait_for_order_fill

def test_order_fill_polling():
    mock_client = MagicMock()
    
    order_pending = MagicMock()
    order_pending.id = "test-order-123"
    order_pending.status = OrderStatus.ACCEPTED

    order_filled = MagicMock()
    order_filled.id = "test-order-123"
    order_filled.status = OrderStatus.FILLED

    call_count = 0
    def mock_get_order(order_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return order_pending
        return order_filled

    mock_client.get_order_by_id.side_effect = mock_get_order

    with patch("time.sleep") as mock_sleep:
        filled_order = wait_for_order_fill(mock_client, "test-order-123", timeout_sec=10.0, poll_interval_sec=1.0)
        assert filled_order.status == OrderStatus.FILLED
        assert call_count == 2
        mock_sleep.assert_called_with(1.0)
