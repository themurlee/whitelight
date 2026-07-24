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

@patch("src.options.full_audit.levels.compute_volume_profile")
@patch("src.options.full_audit.levels.compute_range_and_pivot")
@patch("src.options.full_audit.levels.get_daily_bars")
def test_get_price_levels_caps_overflow_and_dedups(mock_bars, mock_range, mock_vp, tmp_path, monkeypatch):
    """Test that >5 candidates are capped at nearest 5, and duplicates from different sources are deduplicated."""
    monkeypatch.setattr("src.config.DATA_DIR", str(tmp_path))
    mock_bars.return_value = [{"date": "2026-07-20", "open": 95, "high": 110, "low": 85, "close": 100, "volume": 1000}]

    # range_pivot returns: pivot=99.5 (will deduplicate with poc)
    mock_range.return_value = {
        "range_low": 90.0, "range_high": 110.0, "pivot": 99.5,
        "resistance": [105.0, 110.0], "support": [95.0, 85.0],
    }

    # volume_profile returns: poc=99.5 (DUPLICATE with pivot to test dedup), vah=108, val=92
    mock_vp.return_value = {"poc": 99.5, "vah": 108.0, "val": 92.0}

    # Add manual levels to create >5 candidates on both sides
    add_manual_level("TEST", 94.0, "manual below 1")
    add_manual_level("TEST", 96.0, "manual below 2")
    add_manual_level("TEST", 97.0, "manual below 3")
    add_manual_level("TEST", 98.0, "manual below 4")
    add_manual_level("TEST", 102.0, "manual above 1")
    add_manual_level("TEST", 103.0, "manual above 2")
    add_manual_level("TEST", 104.0, "manual above 3")
    add_manual_level("TEST", 106.0, "manual above 4")
    add_manual_level("TEST", 107.0, "manual above 5")
    add_manual_level("TEST", 109.0, "manual above 6")

    result = get_price_levels("TEST", current_price=100.0)

    # Verify exact cap at 5
    assert len(result["levels_below"]) == 5
    assert len(result["levels_above"]) == 5

    # Verify all are correct side of current price
    assert all(l < 100.0 for l in result["levels_below"])
    assert all(l > 100.0 for l in result["levels_above"])

    # Verify nearest-first ordering
    assert result["levels_below"] == sorted(result["levels_below"], reverse=True)
    assert result["levels_above"] == sorted(result["levels_above"])

    # Verify nearest 5 are selected (not arbitrary 5)
    # Below: candidates are [85, 90, 92, 94, 95, 96, 97, 98, 99.5], nearest 5 = [99.5, 98, 97, 96, 95]
    assert result["levels_below"] == [99.5, 98.0, 97.0, 96.0, 95.0]

    # Above: candidates are [102, 103, 104, 105, 106, 107, 108, 109, 110], nearest 5 = [102, 103, 104, 105, 106]
    assert result["levels_above"] == [102.0, 103.0, 104.0, 105.0, 106.0]

    # Verify dedup: 99.5 appears only once (from both pivot and poc sources, but set deduplicated it)
    assert result["levels_below"].count(99.5) == 1

def test_delete_manual_level_nonexistent(tmp_path, monkeypatch):
    """Test that deleting a non-existent manual level returns list unchanged (no-op)."""
    monkeypatch.setattr("src.config.DATA_DIR", str(tmp_path))

    # Start with empty list
    assert get_manual_levels("TEST") == []

    # Delete a price that was never added
    result = delete_manual_level("TEST", 999.0)
    assert result == []

    # Add some levels
    add_manual_level("TEST", 100.0, "level 1")
    add_manual_level("TEST", 200.0, "level 2")
    existing_levels = get_manual_levels("TEST")
    assert len(existing_levels) == 2

    # Delete a price that doesn't exist
    result = delete_manual_level("TEST", 150.0)

    # Verify list unchanged
    assert result == existing_levels
    assert len(result) == 2
    assert result[0]["price"] == 100.0
    assert result[1]["price"] == 200.0

    # Verify persisted state is also unchanged
    persisted = get_manual_levels("TEST")
    assert persisted == existing_levels
