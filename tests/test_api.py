"""
Unit tests for the WhiteLight API endpoints and conditional order triggers.
"""

import os
import json
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import src.config as config

# Patch DATA_DIR to use a temporary directory for testing
TEST_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_data"))

@patch("src.api.DATA_DIR", TEST_DATA_DIR)
class TestAPIAndConditionalOrders(unittest.TestCase):

    def setUp(self):
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        self.cond_file = os.path.join(TEST_DATA_DIR, "conditional_orders.json")
        if os.path.exists(self.cond_file):
            os.remove(self.cond_file)

    def tearDown(self):
        if os.path.exists(self.cond_file):
            os.remove(self.cond_file)
        if os.path.exists(TEST_DATA_DIR):
            try:
                os.rmdir(TEST_DATA_DIR)
            except OSError:
                # Directory might not be empty, clean up files inside
                for f in os.listdir(TEST_DATA_DIR):
                    os.remove(os.path.join(TEST_DATA_DIR, f))
                os.rmdir(TEST_DATA_DIR)

    @patch("alpaca.trading.client.TradingClient")
    @patch("src.api._fetch_real_ticker_signal")
    @patch("src.options.alpaca_options.get_options_chain")
    def test_conditional_order_matching_by_expiration(self, mock_get_options_chain, mock_fetch_signal, mock_trading_client):
        # 1. Create a conditional order in PENDING status requiring a specific expiration
        from src.api import _write_json_file, _read_json_file
        
        pending_order = {
            "id": "test_order_123",
            "timestamp": datetime.now().isoformat(),
            "underlying": "SNDK",
            "option_type": "CALL",
            "strike": 1700.0,
            "expiration": "2026-07-24",
            "timeframe": "WEEKLY",
            "condition": "CROSSES_ABOVE",
            "trigger_value": 1533.0,
            "qty": 1,
            "status": "PENDING"
        }
        _write_json_file(self.cond_file, [pending_order])

        # 2. Mock current stock price above trigger threshold (trigger condition is met)
        mock_fetch_signal.return_value = {"basePrice": 1540.0}

        # Mock options chain containing contracts with different expirations
        mock_get_options_chain.return_value = [
            # Wrong expiration but closer/correct strike
            {
                "symbol": "SNDK260731C01700000",
                "type": "CALL",
                "strike": 1700.0,
                "expiration": "2026-07-31",
                "target_dte": 10,
                "bid": 2.50, "ask": 2.65, "midpoint": 2.57,
                "open_interest": 1000
            },
            # Correct expiration and correct strike
            {
                "symbol": "SNDK260724C01700000",
                "type": "CALL",
                "strike": 1700.0,
                "expiration": "2026-07-24",
                "target_dte": 3,
                "bid": 2.10, "ask": 2.25, "midpoint": 2.17,
                "open_interest": 1200
            }
        ]

        # Mock trading client to verify submission
        mock_client_instance = MagicMock()
        mock_client_instance.get_all_positions.return_value = []
        mock_trading_client.return_value = mock_client_instance

        # Mock config keys so checker loop does not return early
        config.API_KEY = "mock_api_key"
        config.SECRET_KEY = "mock_secret_key"

        # 3. Invoke position_risk_checker_loop once by patching time.sleep to raise an exception
        from src.api import position_risk_checker_loop
        
        with patch("time.sleep", side_effect=ValueError("StopLoop")):
            try:
                position_risk_checker_loop()
            except ValueError as e:
                self.assertEqual(str(e), "StopLoop")

        # 4. Verify that the correct contract symbol (with right expiration) was submitted
        mock_client_instance.submit_order.assert_called_once()
        called_args = mock_client_instance.submit_order.call_args[0][0]
        self.assertEqual(called_args.symbol, "SNDK260724C01700000")
        self.assertEqual(called_args.qty, 1)

        # 5. Verify the order status is now EXECUTED in the JSON database
        orders = _read_json_file(self.cond_file, [])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["status"], "EXECUTED")
        self.assertIn("triggered_at", orders[0])
