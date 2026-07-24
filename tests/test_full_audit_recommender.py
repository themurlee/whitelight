from datetime import datetime
from src.options.full_audit.recommender import bucket_expirations

def test_bucket_expirations_this_week_keeps_all_within_7_days():
    today = datetime(2026, 7, 23)
    expirations = ["2026-07-24", "2026-07-27", "2026-07-29", "2026-08-15", "2026-10-16", "2027-06-18"]
    buckets = bucket_expirations(expirations, today=today)
    assert buckets["this_week"] == ["2026-07-24", "2026-07-27", "2026-07-29"]
    assert buckets["monthly"] == "2026-08-15"
    assert buckets["quarterly"] == "2026-10-16"
    assert buckets["leaps"] == "2027-06-18"

def test_bucket_expirations_missing_bucket_is_none():
    today = datetime(2026, 7, 23)
    expirations = ["2026-07-24"]
    buckets = bucket_expirations(expirations, today=today)
    assert buckets["this_week"] == ["2026-07-24"]
    assert buckets["monthly"] is None
    assert buckets["quarterly"] is None
    assert buckets["leaps"] is None


from unittest.mock import patch
import pandas as pd
from src.options.full_audit.recommender import get_multi_expiry_recommendations

@patch("src.options.full_audit.recommender.get_contracts_for_expiry")
@patch("src.options.full_audit.recommender.get_real_expirations")
@patch("src.options.full_audit.recommender.get_price_levels")
@patch("src.options.full_audit.recommender.calculate_intraday_signals")
@patch("src.options.full_audit.recommender.fetch_intraday_5min_candles")
def test_get_multi_expiry_recommendations_shape(
    mock_candles, mock_signals, mock_levels, mock_expirations, mock_contracts,
):
    mock_candles.return_value = pd.DataFrame({"close": [698.0]})
    mock_signals.return_value = {"intraday_bias": "BULLISH", "rsi_7": 60.0, "iv_rank": 25.0}
    mock_levels.return_value = {
        "ticker": "QQQ", "current_price": 698.0, "levels_below": [685.0], "levels_above": [700.0],
    }
    mock_expirations.return_value = ["2026-07-24", "2026-08-15"]
    mock_contracts.return_value = [
        {"symbol": "T1", "type": "CALL", "strike": 700.0, "expiration": "2026-07-24", "bid": 1.0, "ask": 1.2,
         "midpoint": 1.1, "open_interest": 900, "greeks": {"delta": 0.4, "gamma": 0.02, "theta": -0.03, "vega": 0.1}},
        {"symbol": "T2", "type": "PUT", "strike": 695.0, "expiration": "2026-07-24", "bid": 1.0, "ask": 1.2,
         "midpoint": 1.1, "open_interest": 900, "greeks": {"delta": -0.4, "gamma": 0.02, "theta": -0.03, "vega": 0.1}},
    ]

    result = get_multi_expiry_recommendations("QQQ")
    assert result["ticker"] == "QQQ"
    assert result["current_price"] == 698.0
    assert "levels" in result
    assert "this_week" in result["buckets"]
    assert isinstance(result["buckets"]["this_week"], list)
    assert result["buckets"]["this_week"][0]["expiration"] == "2026-07-24"
    assert len(result["buckets"]["this_week"][0]["cards"]) > 0
