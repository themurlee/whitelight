import os
import json
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Mock config keys before importing executor to ensure it runs
with patch.dict(os.environ, {
    "ALPACA_API_KEY": "mock_key",
    "ALPACA_SECRET_KEY": "mock_secret"
}):
    import src.config as config
    from src.executor import execute_signal

class TestExecutionEngine(unittest.TestCase):

    def setUp(self):
        self.original_data_dir = config.DATA_DIR
        self.original_journal_dir = config.JOURNAL_DIR
        self.original_trade_log = config.TRADE_LOG_PATH
        
        config.DATA_DIR = os.path.join(self.original_data_dir, "test_executor_run")
        config.JOURNAL_DIR = os.path.join(config.DATA_DIR, "journal")
        config.TRADE_LOG_PATH = os.path.join(config.JOURNAL_DIR, "trade_log.md")
        
        os.makedirs(config.DATA_DIR, exist_ok=True)
        os.makedirs(config.JOURNAL_DIR, exist_ok=True)

    def tearDown(self):
        import shutil
        if os.path.exists(config.DATA_DIR):
            shutil.rmtree(config.DATA_DIR)
            
        config.DATA_DIR = self.original_data_dir
        config.JOURNAL_DIR = self.original_journal_dir
        config.TRADE_LOG_PATH = self.original_trade_log

    @patch("src.executor.TradingClient")
    def test_execute_signal_buy_success(self, mock_trading_client_class):
        # Arrange
        mock_client = MagicMock()
        mock_trading_client_class.return_value = mock_client
        
        # Setup get_open_position to throw exception (meaning no position exists)
        mock_client.get_open_position.side_effect = Exception("No position")
        # No open orders
        mock_client.get_orders.return_value = []
        
        # Mock get_account for risk validation
        mock_account = MagicMock()
        mock_account.portfolio_value = 100000.0
        mock_client.get_account.return_value = mock_account
        
        # Mock submit_order
        mock_order = MagicMock()
        mock_order.id = "mock_order_id"
        mock_order.status = "accepted"
        mock_client.submit_order.return_value = mock_order

        # Write mock signal log
        signal_log_path = os.path.join(config.DATA_DIR, "signal_log.json")
        with open(signal_log_path, "w") as f:
            json.dump({
                "ticker": "SPY",
                "action": "BUY",
                "close": 100.0
            }, f)

        # Act
        execute_signal()

        # Assert
        mock_client.submit_order.assert_called_once()
        self.assertTrue(os.path.exists(config.TRADE_LOG_PATH))
