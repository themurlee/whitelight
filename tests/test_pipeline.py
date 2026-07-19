"""
WhiteLight Systematic Trading & Analysis Pipeline - End-to-End Pipeline Unit Tests
Validates coordination of indicators, option contract filtering, safety checks, and logs.
"""

import os
import json
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from src.pipeline import run_pipeline
from src.execution import STATE_FILE, POSITIONS_FILE
from src.journal import TRADE_LOG_FILE, ERROR_LOG_FILE


class TestPipelineEndToEnd(unittest.TestCase):

    def setUp(self):
        # Reset state databases
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        
        with open(STATE_FILE, "w") as f:
            json.dump({
                "lockdown_active": False,
                "drawdown_locked_at": None,
                "equity_history": [
                    {"timestamp": datetime.utcnow().isoformat() + "Z", "equity": 10000.0}
                ]
            }, f, indent=2)

        with open(POSITIONS_FILE, "w") as f:
            json.dump({
                "active_positions": []
            }, f, indent=2)

        for f in [TRADE_LOG_FILE, ERROR_LOG_FILE]:
            if os.path.exists(f):
                os.remove(f)

    def tearDown(self):
        # Cleanup log files
        for f in [TRADE_LOG_FILE, ERROR_LOG_FILE]:
            if os.path.exists(f):
                os.remove(f)

    @patch("src.execution.ExecutionClient.place_option_order")
    def test_pipeline_bullish_execution(self, mock_place_order):
        # Setup mock execution responses
        mock_place_order.return_value = {
            "order_id": "order_bullish_test",
            "status": "placed",
            "symbol": "AAPL260814C00185000",
            "quantity": 1
        }

        # Run pipeline in dry run mode for AAPL
        # Note: By default, the mock bars in pipeline.py are hardcoded to generate a bullish signal:
        # Close ~ 180 * (1 + 0.0003 * 299) = 196.14.
        # EMA50 and EMA250 will be less than Close, and VWAP will be ~ 195.
        # So it will trigger a BUY CALL on AAPL260814C00185000.
        run_pipeline(ticker="AAPL", dry_run=True)

        # Verify order got placed
        mock_place_order.assert_called_once_with("AAPL260814C00185000", 1, "buy")

        # Verify position was appended to positions.json
        with open(POSITIONS_FILE, "r") as f:
            pos_data = json.load(f)
        self.assertEqual(len(pos_data["active_positions"]), 1)
        self.assertEqual(pos_data["active_positions"][0]["symbol"], "AAPL260814C00185000")

        # Verify trade was logged in trade_history.json
        self.assertTrue(os.path.exists(TRADE_LOG_FILE))
        with open(TRADE_LOG_FILE, "r") as f:
            trades = json.load(f)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["action"], "BUY")
        self.assertEqual(trades[0]["symbol"], "AAPL260814C00185000")

    @patch("src.execution.ExecutionClient.place_option_order")
    def test_pipeline_blocked_by_lockdown(self, mock_place_order):
        # Force active lockdown state in state.json
        with open(STATE_FILE, "w") as f:
            json.dump({
                "lockdown_active": True,
                "drawdown_locked_at": datetime.utcnow().isoformat() + "Z",
                "equity_history": []
            }, f, indent=2)

        # Run pipeline
        run_pipeline(ticker="AAPL", dry_run=True)

        # Order should NOT have been placed
        mock_place_order.assert_not_called()

        # Positions and trade logs should remain empty
        with open(POSITIONS_FILE, "r") as f:
            pos_data = json.load(f)
        self.assertEqual(len(pos_data["active_positions"]), 0)


if __name__ == "__main__":
    unittest.main()
