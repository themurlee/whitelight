import os
import json
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
import pandas as pd

# Mock config keys before importing ingest to ensure it runs
with patch.dict(os.environ, {
    "ALPACA_API_KEY": "mock_key",
    "ALPACA_SECRET_KEY": "mock_secret"
}):
    import src.config as config
    from src.ingest import fetch_and_save_ohlcv

class TestDataIngestion(unittest.TestCase):

    def setUp(self):
        # Set up a test directory inside data
        self.original_data_dir = config.DATA_DIR
        self.original_journal_dir = config.JOURNAL_DIR
        self.original_trade_log = config.TRADE_LOG_PATH
        
        config.DATA_DIR = os.path.join(self.original_data_dir, "test_run")
        config.JOURNAL_DIR = os.path.join(config.DATA_DIR, "journal")
        config.TRADE_LOG_PATH = os.path.join(config.JOURNAL_DIR, "trade_log.md")
        
        os.makedirs(config.DATA_DIR, exist_ok=True)
        os.makedirs(config.JOURNAL_DIR, exist_ok=True)

    def tearDown(self):
        # Cleanup
        import shutil
        if os.path.exists(config.DATA_DIR):
            shutil.rmtree(config.DATA_DIR)
            
        config.DATA_DIR = self.original_data_dir
        config.JOURNAL_DIR = self.original_journal_dir
        config.TRADE_LOG_PATH = self.original_trade_log

    @patch("src.ingest.StockHistoricalDataClient")
    def test_fetch_and_save_ohlcv_success(self, mock_client_class):
        # Arrange
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Prepare mock bars response
        mock_bars = MagicMock()
        timestamp = datetime.now(timezone.utc) - timedelta(days=1)
        
        mock_reset_df = pd.DataFrame([{
            "timestamp": timestamp,
            "open": 100.0,
            "high": 105.0,
            "low": 98.0,
            "close": 102.0,
            "volume": 10000,
            "vwap": 101.5
        }])
        mock_bars.df = MagicMock()
        mock_bars.df.empty = False
        mock_bars.df.reset_index.return_value = mock_reset_df
        mock_client.get_stock_bars.return_value = mock_bars
        
        # Act
        success = fetch_and_save_ohlcv("MOCK_SYM", days_to_fetch=5)
        
        # Assert
        self.assertTrue(success)
        date_str = timestamp.strftime("%Y-%m-%d")
        expected_file = os.path.join(config.DATA_DIR, "MOCK_SYM", f"{date_str}.jsonl")
        self.assertTrue(os.path.exists(expected_file))
        
        with open(expected_file, "r") as f:
            data = json.loads(f.read())
            self.assertEqual(data["open"], 100.0)
            self.assertEqual(data["close"], 102.0)
