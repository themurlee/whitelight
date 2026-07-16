"""
WhiteLight Systematic Trading & Analysis Pipeline - Journaling Unit Tests
Validates flat-file logging formats and daily markdown journal templates.
"""

import os
import json
import unittest
from datetime import datetime
from src.journal import (
    log_trade,
    log_error,
    log_state_transition,
    generate_daily_journal_template,
    TRADE_LOG_FILE,
    ERROR_LOG_FILE,
    TRANSITION_LOG_FILE,
    JOURNAL_DIR
)


class TestJournaling(unittest.TestCase):

    def setUp(self):
        # Clear out test files to isolate execution
        for f in [TRADE_LOG_FILE, ERROR_LOG_FILE, TRANSITION_LOG_FILE]:
            if os.path.exists(f):
                os.remove(f)

    def tearDown(self):
        # Clean up files after test run
        for f in [TRADE_LOG_FILE, ERROR_LOG_FILE, TRANSITION_LOG_FILE]:
            if os.path.exists(f):
                os.remove(f)

    def test_log_trade(self):
        log_trade("BUY", "AAPL260814C00170000", 2, 5.20, {"reason": "EMA cross"})
        
        self.assertTrue(os.path.exists(TRADE_LOG_FILE))
        with open(TRADE_LOG_FILE, "r") as f:
            data = json.load(f)
            
        self.assertEqual(len(data), 1)
        entry = data[0]
        self.assertEqual(entry["action"], "BUY")
        self.assertEqual(entry["symbol"], "AAPL260814C00170000")
        self.assertEqual(entry["quantity"], 2)
        self.assertEqual(entry["price"], 5.20)
        self.assertEqual(entry["details"]["reason"], "EMA cross")
        self.assertIn("timestamp", entry)

    def test_log_error(self):
        log_error("Failed to connect to MCP", "Traceback info...", {"retries": 3})
        
        self.assertTrue(os.path.exists(ERROR_LOG_FILE))
        with open(ERROR_LOG_FILE, "r") as f:
            data = json.load(f)
            
        self.assertEqual(len(data), 1)
        entry = data[0]
        self.assertEqual(entry["message"], "Failed to connect to MCP")
        self.assertEqual(entry["traceback"], "Traceback info...")
        self.assertEqual(entry["context"]["retries"], 3)

    def test_log_state_transition(self):
        log_state_transition("NORMAL", "LOCKDOWN", "Drawdown limit exceeded")
        
        self.assertTrue(os.path.exists(TRANSITION_LOG_FILE))
        with open(TRANSITION_LOG_FILE, "r") as f:
            data = json.load(f)
            
        self.assertEqual(len(data), 1)
        entry = data[0]
        self.assertEqual(entry["from_state"], "NORMAL")
        self.assertEqual(entry["to_state"], "LOCKDOWN")
        self.assertEqual(entry["reason"], "Drawdown limit exceeded")

    def test_generate_daily_journal_template(self):
        test_date = "2026-07-15"
        filepath = generate_daily_journal_template(test_date)
        
        self.assertTrue(os.path.exists(filepath))
        
        with open(filepath, "r") as f:
            content = f.read()
            
        self.assertIn(f"WhiteLight Systematic Trading Journal - {test_date}", content)
        self.assertIn("## 1. Market Context & Macro Observations", content)
        self.assertIn("## 4. Narrative Reflections & Qualitative Logs", content)
        
        # Verify writing to existing journal does not overwrite
        with open(filepath, "w") as f:
            f.write("CUSTOM_REFLECTIONS")
            
        # Calling template generator again shouldn't wipe custom reflections
        generate_daily_journal_template(test_date)
        
        with open(filepath, "r") as f:
            content = f.read()
        self.assertEqual(content, "CUSTOM_REFLECTIONS")
        
        # Clean up test journal file
        if os.path.exists(filepath):
            os.remove(filepath)


if __name__ == "__main__":
    unittest.main()
