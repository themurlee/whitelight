"""
WhiteLight Systematic Trading & Analysis Pipeline - Options Selector Unit Tests
Tests options chain filtering logic using mock datasets.
"""

import unittest
from src.selector import calculate_dte, filter_options_chain


class TestOptionsSelector(unittest.TestCase):

    def test_calculate_dte(self):
        # 31 days between July 15 and August 15
        self.assertEqual(calculate_dte("2026-08-15", "2026-07-15"), 31)
        # Same day
        self.assertEqual(calculate_dte("2026-07-15", "2026-07-15"), 0)
        # Past date
        self.assertEqual(calculate_dte("2026-07-10", "2026-07-15"), -5)

        # Invalid format errors
        with self.assertRaises(ValueError):
            calculate_dte("08/15/2026", "2026-07-15")

    def test_filter_options_chain_calls(self):
        # Mock options chain
        mock_contracts = [
            # Call with close expiration (5 DTE)
            {
                "symbol": "AAPL260720C00170000",
                "expiration_date": "2026-07-20",
                "option_type": "call",
                "delta": 0.41,
                "strike_price": 170.0,
                "volume": 10
            },
            # Call with target expiration (30 DTE, delta too high)
            {
                "symbol": "AAPL260814C00150000",
                "expiration_date": "2026-08-14",
                "option_type": "call",
                "delta": 0.85,
                "strike_price": 150.0,
                "volume": 20
            },
            # Call with target expiration (30 DTE, delta closest to 0.40)
            {
                "symbol": "AAPL260814C00170000",
                "expiration_date": "2026-08-14",
                "option_type": "call",
                "delta": 0.42,
                "strike_price": 170.0,
                "volume": 100
            },
            # Call with target expiration (30 DTE, delta too low)
            {
                "symbol": "AAPL260814C00190000",
                "expiration_date": "2026-08-14",
                "option_type": "call",
                "delta": 0.15,
                "strike_price": 190.0,
                "volume": 50
            },
            # Call with far expiration (60 DTE)
            {
                "symbol": "AAPL260913C00170000",
                "expiration_date": "2026-09-13",
                "option_type": "call",
                "delta": 0.39,
                "strike_price": 170.0,
                "volume": 15
            }
        ]

        # Current date: 2026-07-15. Target DTE: 30.
        # Expiration "2026-08-14" is exactly 30 days away.
        selected = filter_options_chain(
            contracts=mock_contracts,
            option_type="call",
            current_date_str="2026-07-15",
            target_dte=30,
            target_delta=0.40
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["symbol"], "AAPL260814C00170000")
        self.assertEqual(selected["strike_price"], 170.0)

    def test_filter_options_chain_puts(self):
        mock_contracts = [
            # Put with target expiration (30 DTE, delta closest to -0.40)
            {
                "symbol": "AAPL260814P00160000",
                "expiration_date": "2026-08-14",
                "option_type": "put",
                "delta": -0.38,
                "strike_price": 160.0,
                "volume": 80
            },
            # Put with target expiration (30 DTE, delta further away)
            {
                "symbol": "AAPL260814P00150000",
                "expiration_date": "2026-08-14",
                "option_type": "put",
                "delta": -0.55,
                "strike_price": 150.0,
                "volume": 200
            }
        ]

        selected = filter_options_chain(
            contracts=mock_contracts,
            option_type="put",
            current_date_str="2026-07-15",
            target_dte=30,
            target_delta=0.40
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["symbol"], "AAPL260814P00160000")
        self.assertEqual(selected["strike_price"], 160.0)

    def test_volume_tie_breaker(self):
        mock_contracts = [
            # Two put contracts with same expiration and delta difference, different volume
            {
                "symbol": "AAPL260814C00170000",
                "expiration_date": "2026-08-14",
                "option_type": "call",
                "delta": 0.40,
                "strike_price": 170.0,
                "volume": 100
            },
            {
                "symbol": "AAPL260814C00171000",
                "expiration_date": "2026-08-14",
                "option_type": "call",
                "delta": 0.40,
                "strike_price": 171.0,
                "volume": 500
            }
        ]

        selected = filter_options_chain(
            contracts=mock_contracts,
            option_type="call",
            current_date_str="2026-07-15",
            target_dte=30,
            target_delta=0.40
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["symbol"], "AAPL260814C00171000")
        self.assertEqual(selected["volume"], 500)

    def test_past_expirations_ignored(self):
        mock_contracts = [
            # Expiration is in the past relative to current_date_str "2026-07-15"
            {
                "symbol": "AAPL260710C00170000",
                "expiration_date": "2026-07-10",
                "option_type": "call",
                "delta": 0.40,
                "strike_price": 170.0,
                "volume": 100
            }
        ]

        selected = filter_options_chain(
            contracts=mock_contracts,
            option_type="call",
            current_date_str="2026-07-15",
            target_dte=30,
            target_delta=0.40
        )

        self.assertIsNone(selected)

    def test_empty_or_no_matching_chain(self):
        self.assertIsNone(filter_options_chain([], "call", "2026-07-15"))


if __name__ == "__main__":
    unittest.main()
