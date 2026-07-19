"""
WhiteLight Systematic Trading & Analysis Pipeline - Execution & Safety Unit Tests
Validates Risk Circuit Breaker drawdown calculation and emergency position flattening.
"""

import os
import json
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from src.execution import RobinhoodMCPClient, RiskManager, execute_order_safely, STATE_FILE, POSITIONS_FILE


class TestRiskCircuitBreaker(unittest.TestCase):

    def setUp(self):
        # Create fresh state files before each test to isolate executions
        self.client = RobinhoodMCPClient(dry_run=True)
        self.risk_manager = RiskManager(self.client)
        
        # Reset files to clean default state
        with open(STATE_FILE, "w") as f:
            json.dump({
                "lockdown_active": False,
                "drawdown_locked_at": None,
                "equity_history": []
            }, f, indent=2)

        with open(POSITIONS_FILE, "w") as f:
            json.dump({
                "active_positions": []
            }, f, indent=2)

    def tearDown(self):
        # Clean up files after test run if necessary
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
        if os.path.exists(POSITIONS_FILE):
            os.remove(POSITIONS_FILE)

    def test_verify_drawdown_within_limit(self):
        # Peak equity is 10000, current equity is 9500 (5% drawdown)
        self.client.get_portfolio_equity = MagicMock(return_value=9500.0)
        
        # Pre-seed history with 10000 yesterday
        yesterday_str = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
        state = self.risk_manager.load_state()
        state["equity_history"] = [{"timestamp": yesterday_str, "equity": 10000.0}]
        self.risk_manager.save_state(state)

        locked, drawdown = self.risk_manager.verify_and_update_drawdown()
        
        self.assertFalse(locked)
        self.assertAlmostEqual(drawdown, 0.05)
        
        # Verify state history got updated with the new 9500 value
        updated_state = self.risk_manager.load_state()
        self.assertEqual(len(updated_state["equity_history"]), 2)
        self.assertEqual(updated_state["equity_history"][-1]["equity"], 9500.0)

    def test_circuit_breaker_trigger_and_flatten(self):
        # Peak equity is 10000, current is 8400 (16% drawdown, triggers 15% breaker)
        self.client.get_portfolio_equity = MagicMock(return_value=8400.0)
        self.client.purge_all_orders = MagicMock(return_value=5)
        self.client.place_option_order = MagicMock(return_value={"status": "placed"})
        
        # Pre-seed active position to flatten
        positions = self.risk_manager.load_positions()
        positions["active_positions"].append({
            "symbol": "AAPL260814C00170000",
            "quantity": 2,
            "option_type": "call",
            "strike_price": 170.0,
            "expiration_date": "2026-08-14"
        })
        self.risk_manager.save_positions(positions)

        # Pre-seed history with 10000
        yesterday_str = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
        state = self.risk_manager.load_state()
        state["equity_history"] = [{"timestamp": yesterday_str, "equity": 10000.0}]
        self.risk_manager.save_state(state)

        locked, drawdown = self.risk_manager.verify_and_update_drawdown()
        
        self.assertTrue(locked)
        self.assertAlmostEqual(drawdown, 0.16)

        # Check state saved lockdown_active=True
        updated_state = self.risk_manager.load_state()
        self.assertTrue(updated_state["lockdown_active"])
        self.assertIsNotNone(updated_state["drawdown_locked_at"])

        # Check client methods were called
        self.client.purge_all_orders.assert_called_once()
        self.client.place_option_order.assert_called_once_with("AAPL260814C00170000", 2, side="sell")

        # Check positions file was cleared
        updated_positions = self.risk_manager.load_positions()
        self.assertEqual(len(updated_positions["active_positions"]), 0)

    def test_prevent_order_execution_during_lockdown(self):
        # Lock down system first
        state = self.risk_manager.load_state()
        state["lockdown_active"] = True
        self.risk_manager.save_state(state)

        # Try to execute order
        order = execute_order_safely(
            client=self.client,
            risk_manager=self.risk_manager,
            symbol="AAPL260814C00170000",
            quantity=1,
            side="buy",
            option_type="call",
            strike_price=170.0,
            expiration_date="2026-08-14"
        )
        
        self.assertIsNone(order)

    def test_pruning_expired_history(self):
        # Pre-seed history with entry from 10 days ago (should be pruned)
        ten_days_ago_str = (datetime.utcnow() - timedelta(days=10)).isoformat() + "Z"
        yesterday_str = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
        
        state = self.risk_manager.load_state()
        state["equity_history"] = [
            {"timestamp": ten_days_ago_str, "equity": 15000.0}, # Out of window
            {"timestamp": yesterday_str, "equity": 10000.0}    # Within window
        ]
        self.risk_manager.save_state(state)

        self.client.get_portfolio_equity = MagicMock(return_value=9500.0)

        locked, drawdown = self.risk_manager.verify_and_update_drawdown()
        
        # Drawdown should be calculated relative to 10000, not 15000
        # Peak=10000, Current=9500 -> Drawdown = 5%
        self.assertFalse(locked)
        self.assertAlmostEqual(drawdown, 0.05)

        # Verify 10-day-old record was pruned
        updated_state = self.risk_manager.load_state()
        history_dates = [entry["timestamp"] for entry in updated_state["equity_history"]]
        self.assertEqual(len(history_dates), 2) # Only yesterday + today should remain
        self.assertNotIn(ten_days_ago_str, history_dates)


if __name__ == "__main__":
    unittest.main()
