"""
WhiteLight Systematic Trading & Analysis Pipeline - Options Selector Unit Tests
Tests options chain filtering logic using mock datasets.
"""

import unittest
from src.selector import (
    calculate_dte, filter_options_chain,
    vertical_credit_spread, iron_condor, _check_liquidity,
)


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


def _mock_chain(current_date: str = "2026-07-15") -> list:
    """Shared mock chain for spread/condor tests. 30-DTE expiry 2026-08-14."""
    return [
        # Puts
        {"symbol": "AAPL260814P00155000", "expiration_date": "2026-08-14",
         "option_type": "put", "delta": -0.10, "strike_price": 155.0,
         "bid": 0.40, "ask": 0.50, "volume": 300},
        {"symbol": "AAPL260814P00160000", "expiration_date": "2026-08-14",
         "option_type": "put", "delta": -0.20, "strike_price": 160.0,
         "bid": 0.90, "ask": 1.00, "volume": 400},
        {"symbol": "AAPL260814P00165000", "expiration_date": "2026-08-14",
         "option_type": "put", "delta": -0.30, "strike_price": 165.0,
         "bid": 1.60, "ask": 1.70, "volume": 500},
        # Calls
        {"symbol": "AAPL260814C00195000", "expiration_date": "2026-08-14",
         "option_type": "call", "delta": 0.10, "strike_price": 195.0,
         "bid": 0.35, "ask": 0.45, "volume": 250},
        {"symbol": "AAPL260814C00200000", "expiration_date": "2026-08-14",
         "option_type": "call", "delta": 0.20, "strike_price": 200.0,
         "bid": 0.85, "ask": 0.95, "volume": 350},
        {"symbol": "AAPL260814C00205000", "expiration_date": "2026-08-14",
         "option_type": "call", "delta": 0.30, "strike_price": 205.0,
         "bid": 1.55, "ask": 1.65, "volume": 450},
    ]


class TestLiquidityFilter(unittest.TestCase):

    def test_illiquid_contract_rejected(self):
        contracts = [
            {"bid": 1.00, "ask": 2.00},  # 67% spread — illiquid
            {"bid": 1.00, "ask": 1.05},  # ~5% spread — liquid
        ]
        result = _check_liquidity(contracts, max_spread_pct=0.10)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["ask"], 1.05)

    def test_no_bid_ask_passes_through(self):
        contracts = [{"strike_price": 100.0}]
        result = _check_liquidity(contracts, max_spread_pct=0.10)
        self.assertEqual(len(result), 1)


class TestVerticalCreditSpread(unittest.TestCase):

    def setUp(self):
        self.chain = _mock_chain()
        self.date = "2026-07-15"

    def test_bull_put_spread_returns_valid_structure(self):
        result = vertical_credit_spread(
            underlying="AAPL",
            contracts=self.chain,
            direction="bull_put",
            current_date_str=self.date,
            target_delta=0.20,
            width=5.0,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["direction"], "bull_put")
        self.assertIn("short_leg", result)
        self.assertIn("long_leg", result)
        # max_loss + net_credit should equal width
        self.assertAlmostEqual(
            result["max_loss"] + result["net_credit"],
            result["width"], places=4
        )

    def test_bear_call_spread_returns_valid_structure(self):
        result = vertical_credit_spread(
            underlying="AAPL",
            contracts=self.chain,
            direction="bear_call",
            current_date_str=self.date,
            target_delta=0.20,
            width=5.0,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["direction"], "bear_call")
        self.assertAlmostEqual(
            result["max_loss"] + result["net_credit"],
            result["width"], places=4
        )

    def test_invalid_direction_raises(self):
        with self.assertRaises(ValueError):
            vertical_credit_spread("AAPL", self.chain, "long_call", self.date)

    def test_returns_none_on_empty_chain(self):
        result = vertical_credit_spread("AAPL", [], "bull_put", self.date)
        self.assertIsNone(result)

    def test_illiquid_chain_rejected(self):
        # All contracts with >10% bid/ask spread
        wide_chain = [
            {"symbol": "X", "expiration_date": "2026-08-14",
             "option_type": "put", "delta": -0.20, "strike_price": 160.0,
             "bid": 1.00, "ask": 5.00, "volume": 0},
            {"symbol": "Y", "expiration_date": "2026-08-14",
             "option_type": "put", "delta": -0.10, "strike_price": 155.0,
             "bid": 0.50, "ask": 3.00, "volume": 0},
        ]
        result = vertical_credit_spread("AAPL", wide_chain, "bull_put", self.date)
        self.assertIsNone(result)

    def test_breakeven_direction_bull_put(self):
        result = vertical_credit_spread(
            underlying="AAPL",
            contracts=self.chain,
            direction="bull_put",
            current_date_str=self.date,
            target_delta=0.20,
            width=5.0,
        )
        # Bull put breakeven = short_strike - net_credit
        expected_be = float(result["short_leg"]["strike_price"]) - result["net_credit"]
        self.assertAlmostEqual(result["breakeven"], expected_be, places=4)

    def test_risk_metrics_keys_present(self):
        result = vertical_credit_spread(
            underlying="AAPL",
            contracts=self.chain,
            direction="bull_put",
            current_date_str=self.date,
        )
        for key in ["net_credit", "max_loss", "max_profit", "breakeven", "net_delta"]:
            self.assertIn(key, result)


class TestIronCondor(unittest.TestCase):

    def setUp(self):
        self.chain = _mock_chain()
        self.date = "2026-07-15"

    def test_iron_condor_returns_valid_structure(self):
        result = iron_condor(
            underlying="AAPL",
            contracts=self.chain,
            current_date_str=self.date,
            target_delta=0.20,
            width=5.0,
            iv_rank=None,  # skip IV filter in test
        )
        self.assertIsNotNone(result)
        self.assertIn("bull_put_spread", result)
        self.assertIn("bear_call_spread", result)
        self.assertEqual(len(result["breakevens"]), 2)
        self.assertIn("iv_rank_filter_met", result)

    def test_iron_condor_blocked_by_low_iv_rank(self):
        result = iron_condor(
            underlying="AAPL",
            contracts=self.chain,
            current_date_str=self.date,
            iv_rank=30.0,       # below min_iv_rank=45
            min_iv_rank=45.0,
        )
        self.assertIsNone(result)

    def test_iron_condor_passes_with_sufficient_iv_rank(self):
        result = iron_condor(
            underlying="AAPL",
            contracts=self.chain,
            current_date_str=self.date,
            iv_rank=55.0,
            min_iv_rank=45.0,
            target_delta=0.20,
            width=5.0,
        )
        self.assertIsNotNone(result)
        self.assertTrue(result["iv_rank_filter_met"])

    def test_net_credit_equals_sum_of_spreads(self):
        result = iron_condor(
            underlying="AAPL",
            contracts=self.chain,
            current_date_str=self.date,
            iv_rank=None,
            target_delta=0.20,
            width=5.0,
        )
        expected_credit = result["bull_put_spread"]["net_credit"] + result["bear_call_spread"]["net_credit"]
        self.assertAlmostEqual(result["net_credit"], expected_credit, places=4)

    def test_risk_metrics_keys_present(self):
        result = iron_condor(
            underlying="AAPL",
            contracts=self.chain,
            current_date_str=self.date,
            iv_rank=None,
        )
        for key in ["net_credit", "max_loss", "max_profit", "breakevens", "net_delta"]:
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
