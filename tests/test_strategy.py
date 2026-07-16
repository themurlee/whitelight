"""
WhiteLight Systematic Trading & Analysis Pipeline - Strategy Unit Tests
Tests mathematical indicators (SMA, EMA, MACD, session VWAP) using static mock data.
"""

import unittest
from src.strategy import (
    calculate_sma,
    calculate_ema,
    calculate_macd,
    calculate_vwap
)


class TestStrategyIndicators(unittest.TestCase):

    def test_calculate_sma(self):
        # Normal inputs
        prices = [10.0, 11.0, 12.0, 13.0, 14.0]
        period = 3
        expected = [None, None, 11.0, 12.0, 13.0]
        self.assertEqual(calculate_sma(prices, period), expected)

        # Period larger than prices length
        self.assertEqual(calculate_sma(prices, 10), [None, None, None, None, None])

        # Edge cases: empty prices, non-positive period
        self.assertEqual(calculate_sma([], 3), [])
        self.assertEqual(calculate_sma(prices, 0), [None, None, None, None, None])
        self.assertEqual(calculate_sma(prices, -1), [None, None, None, None, None])

    def test_calculate_ema(self):
        # Normal inputs
        prices = [10.0, 11.0, 12.0, 13.0, 14.0]
        period = 3
        # First valid EMA (idx=2) = SMA(10, 11, 12) = 11.0
        # Multiplier = 2 / (3 + 1) = 0.5
        # idx=3: 13.0 * 0.5 + 11.0 * 0.5 = 12.0
        # idx=4: 14.0 * 0.5 + 12.0 * 0.5 = 13.0
        expected = [None, None, 11.0, 12.0, 13.0]
        self.assertEqual(calculate_ema(prices, period), expected)

        # Period larger than prices length
        self.assertEqual(calculate_ema(prices, 10), [None, None, None, None, None])

        # Edge cases: empty prices, non-positive period
        self.assertEqual(calculate_ema([], 3), [])
        self.assertEqual(calculate_ema(prices, 0), [None, None, None, None, None])

    def test_calculate_macd(self):
        # MACD needs a longer series to settle. Let's create a series of 40 prices.
        # Constant prices: EMAs will converge to the price, MACD line and signal line should approach 0.
        prices = [100.0] * 40
        macd, signal, hist = calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9)

        self.assertEqual(len(macd), 40)
        self.assertEqual(len(signal), 40)
        self.assertEqual(len(hist), 40)

        # The first 25 values for slow EMA (period 26) must be None.
        # So MACD line should be None for index < 25.
        for i in range(25):
            self.assertIsNone(macd[i])
            self.assertIsNone(signal[i])
            self.assertIsNone(hist[i])

        # The fast period is 12, slow is 26.
        # The 26th element (index 25) will have the first valid MACD line value.
        # Since fast EMA is 100 and slow EMA is 100, MACD should be 0.0.
        self.assertAlmostEqual(macd[25], 0.0)

        # Signal line needs 9 elements of MACD line to start.
        # So index 25 is the 1st valid MACD value.
        # Index 25 + 9 - 1 = 33 will be the first valid signal line value.
        for i in range(25, 33):
            self.assertIsNone(signal[i])
            self.assertIsNone(hist[i])

        self.assertAlmostEqual(signal[33], 0.0)
        self.assertAlmostEqual(hist[33], 0.0)

        # Test empty input
        m, s, h = calculate_macd([], 12, 26, 9)
        self.assertEqual(m, [])
        self.assertEqual(s, [])
        self.assertEqual(h, [])

    def test_calculate_vwap(self):
        # Two sessions: 2026-07-15 and 2026-07-16
        bars = [
            # Session 1 - Bar 1
            {
                "high": 10.0,
                "low": 8.0,
                "close": 9.0,
                "volume": 100,
                "timestamp": "2026-07-15T09:30:00Z"
            },
            # Session 1 - Bar 2
            {
                "high": 11.0,
                "low": 9.0,
                "close": 10.0,
                "volume": 200,
                "timestamp": "2026-07-15T09:45:00Z"
            },
            # Session 2 - Bar 3 (Date change, should reset VWAP)
            {
                "high": 12.0,
                "low": 10.0,
                "close": 11.0,
                "volume": 150,
                "timestamp": "2026-07-16T09:30:00Z"
            }
        ]

        vwap = calculate_vwap(bars)
        self.assertEqual(len(vwap), 3)

        # Bar 1 Typical Price = (10 + 8 + 9)/3 = 9.0
        # Cumulative TP*Vol = 9.0 * 100 = 900
        # Cumulative Vol = 100
        # Expected VWAP = 900 / 100 = 9.0
        self.assertAlmostEqual(vwap[0], 9.0)

        # Bar 2 Typical Price = (11 + 9 + 10)/3 = 10.0
        # Cumulative TP*Vol = 900 + (10.0 * 200) = 2900
        # Cumulative Vol = 100 + 200 = 300
        # Expected VWAP = 2900 / 300 = 9.66666667
        self.assertAlmostEqual(vwap[1], 9.66666667, places=6)

        # Bar 3 (Session 2 starts) Typical Price = (12 + 10 + 11)/3 = 11.0
        # Cumulative TP*Vol reset to 11.0 * 150 = 1650
        # Cumulative Vol reset to 150
        # Expected VWAP = 1650 / 150 = 11.0
        self.assertAlmostEqual(vwap[2], 11.0)


if __name__ == "__main__":
    unittest.main()
