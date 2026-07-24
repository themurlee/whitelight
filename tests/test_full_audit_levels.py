import os
import json
import pytest
from src.options.full_audit.levels import get_daily_bars, compute_range_and_pivot

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
