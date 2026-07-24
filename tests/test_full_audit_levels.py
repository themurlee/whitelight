import os
import json
import pytest
from unittest.mock import patch
from src.options.full_audit.levels import get_daily_bars, compute_range_and_pivot, compute_volume_profile

def _write_bar_file(tmp_dir, ticker, date, o, h, l, c, v):
    t_dir = os.path.join(tmp_dir, ticker)
    os.makedirs(t_dir, exist_ok=True)
    with open(os.path.join(t_dir, f"{date}.jsonl"), "w") as f:
        json.dump({"timestamp": f"{date}T04:00:00+00:00", "open": o, "high": h, "low": l, "close": c, "volume": v}, f)

def test_get_daily_bars_reads_local_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.DATA_DIR", str(tmp_path))
    _write_bar_file(tmp_path, "ZZZZ", "2026-07-17", 95, 100, 94, 99, 800)
    _write_bar_file(tmp_path, "ZZZZ", "2026-07-18", 99, 104, 97, 102, 900)
    _write_bar_file(tmp_path, "ZZZZ", "2026-07-19", 102, 107, 100, 105, 1100)
    _write_bar_file(tmp_path, "ZZZZ", "2026-07-20", 100, 105, 98, 103, 1000)
    _write_bar_file(tmp_path, "ZZZZ", "2026-07-21", 103, 108, 101, 106, 1200)
    bars = get_daily_bars("ZZZZ", lookback_days=60)
    assert len(bars) == 5
    assert bars[0]["date"] == "2026-07-17"
    assert bars[0]["open"] == 95.0
    assert bars[4]["date"] == "2026-07-21"
    assert bars[4]["close"] == 106.0

def test_compute_range_and_pivot():
    bars = [
        {"date": "2026-07-20", "open": 690, "high": 700, "low": 685, "close": 695, "volume": 1000},
        {"date": "2026-07-21", "open": 695, "high": 698, "low": 688, "close": 692, "volume": 1100},
    ]
    result = compute_range_and_pivot(bars)
    assert result["range_low"] == 685
    assert result["range_high"] == 700
    # Pivot = (prior high + prior low + prior close) / 3, using the last bar as "prior period"
    expected_pivot = round((698 + 688 + 692) / 3.0, 2)
    assert result["pivot"] == expected_pivot
    assert len(result["resistance"]) == 2
    assert len(result["support"]) == 2
    assert result["resistance"][0] > result["pivot"]
    assert result["support"][0] < result["pivot"]

@patch("src.options.full_audit.levels._fetch_minute_bars_from_alpaca")
def test_compute_volume_profile(mock_fetch):
    # Two price levels: 100 (heavy volume) and 105 (light volume)
    mock_fetch.return_value = [
        {"close": 100.0, "volume": 5000},
        {"close": 100.0, "volume": 4800},
        {"close": 105.0, "volume": 200},
    ]
    result = compute_volume_profile("ZZZZ", window="1M")
    assert result["poc"] == 100.0
    assert result["vah"] >= result["poc"] >= result["val"]

def test_compute_volume_profile_invalid_window_defaults_to_1m():
    with patch("src.options.full_audit.levels._fetch_minute_bars_from_alpaca", return_value=[]):
        result = compute_volume_profile("ZZZZ", window="bogus")
        assert result == {"poc": 0.0, "vah": 0.0, "val": 0.0}

from src.options.full_audit.levels import (
    get_manual_levels, add_manual_level, delete_manual_level, get_price_levels
)

def test_manual_levels_add_list_delete(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.DATA_DIR", str(tmp_path))
    assert get_manual_levels("ZZZZ") == []
    add_manual_level("ZZZZ", 700.0, "gamma wall")
    levels = get_manual_levels("ZZZZ")
    assert levels == [{"price": 700.0, "label": "gamma wall"}]
    delete_manual_level("ZZZZ", 700.0)
    assert get_manual_levels("ZZZZ") == []

@patch("src.options.full_audit.levels.compute_volume_profile")
@patch("src.options.full_audit.levels.compute_range_and_pivot")
@patch("src.options.full_audit.levels.get_daily_bars")
def test_get_price_levels_merges_and_caps_at_5(mock_bars, mock_range, mock_vp, tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.DATA_DIR", str(tmp_path))
    mock_bars.return_value = [{"date": "2026-07-20", "open": 690, "high": 700, "low": 685, "close": 692, "volume": 1000}]
    mock_range.return_value = {
        "range_low": 685.0, "range_high": 700.0, "pivot": 692.0,
        "resistance": [696.0, 699.0], "support": [688.0, 684.0],
    }
    mock_vp.return_value = {"poc": 690.0, "vah": 698.0, "val": 682.0}
    add_manual_level("TSLA", 720.0, "manual resistance")

    result = get_price_levels("TSLA", current_price=692.0)
    assert result["ticker"] == "TSLA"
    assert result["current_price"] == 692.0
    assert len(result["levels_below"]) <= 5
    assert len(result["levels_above"]) <= 5
    assert all(l < 692.0 for l in result["levels_below"])
    assert all(l > 692.0 for l in result["levels_above"])
    assert 720.0 in result["levels_above"]  # manual level included
    assert result["levels_below"] == sorted(result["levels_below"], reverse=True)  # nearest-first
    assert result["levels_above"] == sorted(result["levels_above"])  # nearest-first
