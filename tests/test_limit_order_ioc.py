import pytest
from unittest.mock import patch, MagicMock
from alpaca.trading.enums import OrderStatus
from src.execution.limit_order_wrapper import execute_signal_with_slippage_control, SlippageConfig

@patch("src.execution.limit_order_wrapper.get_current_bid_ask")
def test_limit_order_ioc_filled(mock_quote):
    mock_quote.return_value = (99.95, 100.05)
    
    mock_client = MagicMock()
    
    mock_order = MagicMock()
    mock_order.id = "limit-order-123"
    mock_client.submit_order.return_value = mock_order
    
    mock_filled = MagicMock()
    mock_filled.status = OrderStatus.FILLED
    
    config = SlippageConfig(use_limit_orders=True, limit_order_offset_bps=5)
    
    with patch("src.execution.limit_order_wrapper.wait_for_order_fill", return_value=mock_filled):
        res = execute_signal_with_slippage_control(mock_client, "SPY", 100.0, 10, "BUY", config)
        assert res is True
        
        args, kwargs = mock_client.submit_order.call_args
        submitted_req = args[0]
        assert submitted_req.limit_price == 100.10

@patch("src.execution.limit_order_wrapper.get_current_bid_ask")
def test_limit_order_ioc_timeout_fallback(mock_quote):
    mock_quote.return_value = (99.95, 100.05)
    
    mock_client = MagicMock()
    
    mock_limit_order = MagicMock()
    mock_limit_order.id = "limit-order-123"
    
    mock_market_order = MagicMock()
    mock_market_order.id = "market-order-456"
    
    # Mock order get request returning CANCELED status
    mock_canceled_order = MagicMock()
    mock_canceled_order.status.value = "canceled"
    mock_client.get_order_by_id.return_value = mock_canceled_order
    
    def mock_submit(order_req):
        if hasattr(order_req, "limit_price"):
            return mock_limit_order
        return mock_market_order
        
    mock_client.submit_order.side_effect = mock_submit
    
    config = SlippageConfig(use_limit_orders=True, limit_order_offset_bps=5)
    
    call_count = 0
    def mock_fill(client, order_id, timeout_sec, poll_interval_sec):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TimeoutError("Polling timed out")
        mock_res = MagicMock()
        mock_res.status = OrderStatus.FILLED
        return mock_res
        
    with patch("src.execution.limit_order_wrapper.wait_for_order_fill", side_effect=mock_fill):
        with patch("time.sleep"):
            res = execute_signal_with_slippage_control(mock_client, "SPY", 100.0, 10, "BUY", config)
            assert res is True
            mock_client.cancel_order_by_id.assert_called_once_with("limit-order-123")
            assert mock_client.submit_order.call_count == 2
