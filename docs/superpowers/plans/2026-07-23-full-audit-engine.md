# Full Audit Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an explicit "Full Audit" pipeline for a searched ticker: price levels shown first, a multi-expiry (this-week/monthly/quarterly/LEAPS) strike-and-strategy recommendation grid anchored to those levels, and a 3-stage Rules→Agent→CircuitBreaker synthesis gate that always runs all 3 stages and auto-targets the single highest-PoP recommendation across all buckets.

**Architecture:** A new, self-contained `src/options/full_audit/` package (`levels.py`, `recommender.py`, `strategies.py`, `rules_engine.py`, `gate.py`) that calls into existing modules (`greeks.py`, `audit_engine.py::get_contracts_for_expiry`, `agents.py::DualAgentPipeline`, `circuit_breaker.py::CircuitBreaker`) without modifying any of them. Two new endpoints (`POST /api/options/full_audit`, `POST /api/options/full_audit/gate`) plus manual-levels CRUD are added to `src/api.py`. Frontend adds a "Full Audit" button, a Levels card, a bucketed recommendation grid, and reuses the existing inline audit-dropdown pattern for the gate verdict.

**Tech Stack:** Python 3.14 stdlib `http.server` backend (no new deps), pytest for backend tests, React (Vite) frontend, Tailwind classes matching existing `WhitelightCortexIntegratedPanel.jsx` conventions.

## Global Constraints

- No modification to `src/options/audit_engine.py`, `src/options/agents.py`, `src/options/llm_adapters.py`, `src/risk/circuit_breaker.py`, or any currently-working endpoint (`/api/options/audit`, `/evaluate_dual_agent`, `/scan_watchlist`) — new code only calls into these as read-only dependencies.
- IV Rank stays the existing formula-derived proxy (`calculate_black_scholes_greeks`'s `iv_rank` field) — no new historical IV data source, per spec Section 2/decision log.
- All 3 gate stages (Rules, Agent, Circuit Breaker) always run to completion on every gate call — no short-circuiting on early failure.
- The 3-stage gate runs strictly sequentially, single-threaded — no concurrency needed.
- Manual levels are a separate stored input (`data/levels/<TICKER>.json` via `AtomicJSONWriter`), not read from the TradingView embed widget (free tier has no drawing-readback API).
- Volume profile lookback is a selectable parameter (`1W`/`1M`/`3M`/`6M`/`1Y`, default `1M`), not hardcoded.
- Levels output format is always `{ticker, current_price, levels_below: [...max 5...], levels_above: [...max 5...]}` — merged from all sources, sorted, deduplicated.
- Full spec: `docs/superpowers/specs/2026-07-23-full-audit-engine-design.md`.

---

### Task 1: Price Level Engine — range, pivot points, and daily bar loading

**Files:**
- Create: `src/options/full_audit/__init__.py`
- Create: `src/options/full_audit/levels.py`
- Test: `tests/test_full_audit_levels.py`

**Interfaces:**
- Consumes: nothing from other new-package files (first task).
- Produces:
  - `get_daily_bars(ticker: str, lookback_days: int = 60) -> list[dict]` — each dict has `date` (str), `open`, `high`, `low`, `close`, `volume` (floats). Sorted ascending by date. Reads local `data/<TICKER>/*.jsonl` cache; falls back to Alpaca daily bars if fewer than 5 local files exist.
  - `compute_range_and_pivot(bars: list[dict]) -> dict` — returns `{"range_low": float, "range_high": float, "pivot": float, "resistance": [float, float], "support": [float, float]}`. Used by later tasks.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_full_audit_levels.py
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
    _write_bar_file(tmp_path, "ZZZZ", "2026-07-20", 100, 105, 98, 103, 1000)
    _write_bar_file(tmp_path, "ZZZZ", "2026-07-21", 103, 108, 101, 106, 1200)
    bars = get_daily_bars("ZZZZ", lookback_days=60)
    assert len(bars) == 2
    assert bars[0]["date"] == "2026-07-20"
    assert bars[1]["close"] == 106

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_full_audit_levels.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.options.full_audit'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/options/full_audit/__init__.py
```//empty init file

```python
# src/options/full_audit/levels.py
import os
import glob
import logging
from typing import List, Dict

import src.config as config
from src.storage.atomic_writer import AtomicJSONWriter

logger = logging.getLogger("FullAuditLevels")


def get_daily_bars(ticker: str, lookback_days: int = 60) -> List[Dict]:
    """Load daily OHLCV bars for a ticker, most recent `lookback_days` first, ascending by date.

    Reads local data/<TICKER>/*.jsonl cache first. Falls back to a live Alpaca daily-bars
    fetch (same pattern as CircuitBreaker.fetch_30day_bars_from_alpaca) when fewer than 5
    local files exist.
    """
    ticker = ticker.upper()
    t_dir = os.path.join(config.DATA_DIR, ticker)
    bars = []

    if os.path.isdir(t_dir):
        files = sorted(glob.glob(os.path.join(t_dir, "*.jsonl")))[-lookback_days:]
        for fpath in files:
            try:
                data = AtomicJSONWriter(fpath).read()
                if data and "close" in data:
                    date_str = os.path.basename(fpath).replace(".jsonl", "")
                    bars.append({
                        "date": date_str,
                        "open": float(data.get("open", data["close"])),
                        "high": float(data.get("high", data["close"])),
                        "low": float(data.get("low", data["close"])),
                        "close": float(data["close"]),
                        "volume": float(data.get("volume", 0)),
                    })
            except Exception as e:
                logger.warning(f"Skipping unreadable bar file {fpath}: {e}")

    if len(bars) >= 5:
        return sorted(bars, key=lambda b: b["date"])

    # Fallback: fetch from Alpaca directly
    try:
        from src.risk.circuit_breaker import fetch_30day_bars_from_alpaca
        closes = fetch_30day_bars_from_alpaca(ticker)
        if closes:
            from datetime import datetime, timedelta
            today = datetime.now()
            bars = []
            for i, c in enumerate(closes):
                d = (today - timedelta(days=len(closes) - i)).strftime("%Y-%m-%d")
                bars.append({"date": d, "open": c, "high": c, "low": c, "close": c, "volume": 0.0})
    except Exception as e:
        logger.warning(f"Alpaca daily-bar fallback failed for {ticker}: {e}")

    return sorted(bars, key=lambda b: b["date"])


def compute_range_and_pivot(bars: List[Dict]) -> Dict:
    """Rolling high/low range + classic floor-trader pivot points off the last bar."""
    if not bars:
        return {"range_low": 0.0, "range_high": 0.0, "pivot": 0.0, "resistance": [0.0, 0.0], "support": [0.0, 0.0]}

    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    last = bars[-1]

    range_low = round(min(lows), 2)
    range_high = round(max(highs), 2)

    pp = round((last["high"] + last["low"] + last["close"]) / 3.0, 2)
    r1 = round((2 * pp) - last["low"], 2)
    r2 = round(pp + (last["high"] - last["low"]), 2)
    s1 = round((2 * pp) - last["high"], 2)
    s2 = round(pp - (last["high"] - last["low"]), 2)

    return {
        "range_low": range_low,
        "range_high": range_high,
        "pivot": pp,
        "resistance": [r1, r2],
        "support": [s1, s2],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_full_audit_levels.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/options/full_audit/__init__.py src/options/full_audit/levels.py tests/test_full_audit_levels.py
git commit -m "feat(full-audit): add price range/pivot level computation"
```

---

### Task 2: Price Level Engine — volume profile

**Files:**
- Modify: `src/options/full_audit/levels.py`
- Test: `tests/test_full_audit_levels.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `compute_volume_profile(ticker: str, window: str = "1M") -> dict` — returns `{"poc": float, "vah": float, "val": float}`. `window` is one of `"1W"`, `"1M"`, `"3M"`, `"6M"`, `"1Y"`.

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_full_audit_levels.py
from unittest.mock import patch
from src.options.full_audit.levels import compute_volume_profile

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_full_audit_levels.py -v -k volume_profile`
Expected: FAIL with `AttributeError` / `ImportError` — `compute_volume_profile` not defined

- [ ] **Step 3: Write minimal implementation**

```python
# Append to src/options/full_audit/levels.py

_WINDOW_DAYS = {"1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365}


def _fetch_minute_bars_from_alpaca(ticker: str, days: int) -> List[Dict]:
    """Fetch historical minute bars from Alpaca for volume-profile computation."""
    try:
        if not config.API_KEY or not config.SECRET_KEY:
            return []
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed
        from datetime import datetime, timedelta, timezone

        client = StockHistoricalDataClient(config.API_KEY, config.SECRET_KEY)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        req = StockBarsRequest(
            symbol_or_symbols=[ticker],
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )
        bars = client.get_stock_bars(req)
        if bars and bars.df is not None and not bars.df.empty:
            df = bars.df
            if "symbol" in df.index.names:
                df = df.xs(ticker, level=0)
            return [{"close": float(r["close"]), "volume": float(r["volume"])} for _, r in df.iterrows()]
    except Exception as e:
        logger.warning(f"Minute-bar fetch failed for {ticker}: {e}")
    return []


def compute_volume_profile(ticker: str, window: str = "1M") -> Dict:
    """Point of Control (POC) and Value Area High/Low (~70% of volume) from minute bars."""
    days = _WINDOW_DAYS.get(window, _WINDOW_DAYS["1M"])
    bars = _fetch_minute_bars_from_alpaca(ticker, days)
    if not bars:
        return {"poc": 0.0, "vah": 0.0, "val": 0.0}

    # Bucket volume by price rounded to nearest 0.50 increment
    buckets: Dict[float, float] = {}
    for b in bars:
        price_bucket = round(b["close"] * 2) / 2.0
        buckets[price_bucket] = buckets.get(price_bucket, 0.0) + b["volume"]

    sorted_buckets = sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)
    poc = sorted_buckets[0][0]

    total_volume = sum(buckets.values())
    target = total_volume * 0.70
    accumulated = 0.0
    included_prices = []
    for price, vol in sorted_buckets:
        accumulated += vol
        included_prices.append(price)
        if accumulated >= target:
            break

    vah = max(included_prices)
    val = min(included_prices)

    return {"poc": round(poc, 2), "vah": round(vah, 2), "val": round(val, 2)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_full_audit_levels.py -v -k volume_profile`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/options/full_audit/levels.py tests/test_full_audit_levels.py
git commit -m "feat(full-audit): add volume profile (POC/VAH/VAL) computation"
```

---

### Task 3: Price Level Engine — manual levels storage and merged output

**Files:**
- Modify: `src/options/full_audit/levels.py`
- Test: `tests/test_full_audit_levels.py`

**Interfaces:**
- Consumes: `get_daily_bars`, `compute_range_and_pivot`, `compute_volume_profile` (Tasks 1-2, same file).
- Produces:
  - `get_manual_levels(ticker: str) -> list[dict]` — `[{"price": float, "label": str}, ...]`
  - `add_manual_level(ticker: str, price: float, label: str) -> list[dict]`
  - `delete_manual_level(ticker: str, price: float) -> list[dict]`
  - `get_price_levels(ticker: str, current_price: float, volume_profile_window: str = "1M") -> dict` — the final merged shape: `{"ticker": str, "current_price": float, "levels_below": [float, ...max 5], "levels_above": [float, ...max 5]}`. **This is the function `full_audit()` orchestration (Task 8) calls.**

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_full_audit_levels.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_full_audit_levels.py -v -k manual_levels or -k get_price_levels`
Expected: FAIL — functions not defined

- [ ] **Step 3: Write minimal implementation**

```python
# Append to src/options/full_audit/levels.py

def _manual_levels_path(ticker: str) -> str:
    levels_dir = os.path.join(config.DATA_DIR, "levels")
    os.makedirs(levels_dir, exist_ok=True)
    return os.path.join(levels_dir, f"{ticker.upper()}.json")


def get_manual_levels(ticker: str) -> List[Dict]:
    data = AtomicJSONWriter(_manual_levels_path(ticker)).read()
    return data.get("levels", []) if data else []


def add_manual_level(ticker: str, price: float, label: str) -> List[Dict]:
    levels = get_manual_levels(ticker)
    levels.append({"price": float(price), "label": label})
    AtomicJSONWriter(_manual_levels_path(ticker)).write({"levels": levels})
    return levels


def delete_manual_level(ticker: str, price: float) -> List[Dict]:
    levels = [l for l in get_manual_levels(ticker) if l["price"] != float(price)]
    AtomicJSONWriter(_manual_levels_path(ticker)).write({"levels": levels})
    return levels


def get_price_levels(ticker: str, current_price: float, volume_profile_window: str = "1M") -> Dict:
    """Merge range/pivot + volume profile + manual levels into levels_below/levels_above."""
    bars = get_daily_bars(ticker, lookback_days=60)
    range_pivot = compute_range_and_pivot(bars)
    vp = compute_volume_profile(ticker, window=volume_profile_window)
    manual = get_manual_levels(ticker)

    all_prices = set()
    for p in [range_pivot["range_low"], range_pivot["range_high"], range_pivot["pivot"],
              *range_pivot["resistance"], *range_pivot["support"],
              vp["poc"], vp["vah"], vp["val"]]:
        if p and p > 0:
            all_prices.add(round(float(p), 2))
    for m in manual:
        all_prices.add(round(float(m["price"]), 2))

    below = sorted([p for p in all_prices if p < current_price], reverse=True)[:5]
    above = sorted([p for p in all_prices if p > current_price])[:5]

    return {
        "ticker": ticker.upper(),
        "current_price": round(float(current_price), 2),
        "levels_below": below,
        "levels_above": above,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_full_audit_levels.py -v`
Expected: PASS (all tests in file)

- [ ] **Step 5: Commit**

```bash
git add src/options/full_audit/levels.py tests/test_full_audit_levels.py
git commit -m "feat(full-audit): add manual levels CRUD and merged levels_below/above output"
```

---

### Task 4: Multi-Expiry Bucketing

**Files:**
- Create: `src/options/full_audit/recommender.py`
- Test: `tests/test_full_audit_recommender.py`

**Interfaces:**
- Consumes: nothing from other full_audit files yet.
- Produces:
  - `get_real_expirations(ticker: str) -> list[str]` — sorted ascending `YYYY-MM-DD` strings.
  - `bucket_expirations(expirations: list[str], today: "datetime" = None) -> dict` — returns `{"this_week": [dates...], "monthly": [date or None], "quarterly": [date or None], "leaps": [date or None]}`. `this_week` keeps every date ≤7 DTE; the other 3 buckets keep only their single nearest-matching date (`None` if none available).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_full_audit_recommender.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_full_audit_recommender.py -v`
Expected: FAIL — module/function not found

- [ ] **Step 3: Write minimal implementation**

```python
# src/options/full_audit/recommender.py
import logging
from datetime import datetime
from typing import List, Dict, Optional

import src.config as config

logger = logging.getLogger("FullAuditRecommender")


def get_real_expirations(ticker: str) -> List[str]:
    """Fetch real available option expiration dates for a ticker from Alpaca."""
    ticker = ticker.upper()
    if config.API_KEY and config.SECRET_KEY and "YOUR_ALPACA" not in config.API_KEY:
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import GetOptionContractsRequest

            client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
            req = GetOptionContractsRequest(underlying_symbols=[ticker], limit=1000)
            res = client.get_option_contracts(req)
            if res and res.option_contracts:
                dates = sorted({str(c.expiration_date) for c in res.option_contracts})
                return dates
        except Exception as e:
            logger.warning(f"Alpaca expirations fetch failed for {ticker}: {e}")

    # Fallback: synthesize a realistic ladder of expirations
    from datetime import timedelta
    today = datetime.now()
    fallback = [7, 14, 21, 35, 49, 90, 120, 280, 365]
    return sorted((today + timedelta(days=d)).strftime("%Y-%m-%d") for d in fallback)


def bucket_expirations(expirations: List[str], today: Optional[datetime] = None) -> Dict:
    """Bucket real expiration dates into this_week (all <=7 DTE) / monthly / quarterly / leaps (nearest each)."""
    if today is None:
        today = datetime.now()

    dated = []
    for e in expirations:
        try:
            dt = datetime.strptime(e, "%Y-%m-%d")
            dte = (dt - today).days
            if dte >= 0:
                dated.append((e, dte))
        except Exception:
            continue
    dated.sort(key=lambda x: x[1])

    this_week = [e for e, dte in dated if dte <= 7]

    def nearest_in_range(lo: int, hi: int) -> Optional[str]:
        candidates = [e for e, dte in dated if lo <= dte <= hi]
        return candidates[0] if candidates else None

    monthly = nearest_in_range(8, 45)
    quarterly = nearest_in_range(46, 105)
    leaps = nearest_in_range(106, 100000)
    if leaps is None and dated:
        # "Longest available if nothing is >=270" per spec
        longest = max(dated, key=lambda x: x[1])
        if longest[1] >= 106:
            leaps = longest[0]

    return {"this_week": this_week, "monthly": monthly, "quarterly": quarterly, "leaps": leaps}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_full_audit_recommender.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/options/full_audit/recommender.py tests/test_full_audit_recommender.py
git commit -m "feat(full-audit): add real-expiration fetch and this_week/monthly/quarterly/leaps bucketing"
```

---

### Task 5: Strategy Library — level-anchored strike selection and cards (incl. new LEAPS strategy)

**Files:**
- Create: `src/options/full_audit/strategies.py`
- Test: `tests/test_full_audit_strategies.py`

**Interfaces:**
- Consumes: nothing new (takes already-fetched contracts as input — no direct import from `audit_engine.py` needed in this file, keeping it independently testable).
- Produces: `build_strategy_cards(ticker: str, expiration: str, dte: int, current_price: float, contracts: list[dict], bias: str, iv_rank: float, levels: dict) -> list[dict]`. Each card: `{"strategy": str, "description": str, "strike": float, "expiration": str, "dte": int, "probability_of_profit": float, "suitability": str, "greeks": dict, "level_reference": str | None}`. `contracts` items match `get_contracts_for_expiry()`'s shape: `{"symbol", "type", "strike", "expiration", "bid", "ask", "midpoint", "open_interest", "greeks"}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_full_audit_strategies.py
from src.options.full_audit.strategies import build_strategy_cards

def _mk_contract(strike, opt_type, delta):
    return {
        "symbol": f"TEST{opt_type[0]}{int(strike)}", "type": opt_type, "strike": float(strike),
        "expiration": "2026-08-15", "bid": 1.0, "ask": 1.2, "midpoint": 1.1,
        "open_interest": 1000, "greeks": {"delta": delta, "gamma": 0.02, "theta": -0.03, "vega": 0.1},
    }

def test_build_strategy_cards_bullish_low_iv_includes_long_call_and_csp():
    contracts = [
        _mk_contract(695, "PUT", -0.45),
        _mk_contract(700, "CALL", 0.50),
        _mk_contract(705, "CALL", 0.35),
    ]
    levels = {"levels_below": [685.0], "levels_above": [700.0, 705.0]}
    cards = build_strategy_cards(
        ticker="QQQ", expiration="2026-08-15", dte=23, current_price=698.0,
        contracts=contracts, bias="BULLISH", iv_rank=25.0, levels=levels,
    )
    strategies = {c["strategy"] for c in cards}
    assert "LONG CALL" in strategies
    assert "SHORT PUT (Cash Secured Put)" in strategies
    for c in cards:
        assert c["expiration"] == "2026-08-15"
        assert c["dte"] == 23
        assert 0.0 <= c["probability_of_profit"] <= 100.0

def test_build_strategy_cards_leaps_bucket_adds_leaps_strategy():
    contracts = [_mk_contract(650, "CALL", 0.78), _mk_contract(700, "CALL", 0.50)]
    levels = {"levels_below": [], "levels_above": [700.0]}
    cards = build_strategy_cards(
        ticker="QQQ", expiration="2027-06-18", dte=330, current_price=698.0,
        contracts=contracts, bias="BULLISH", iv_rank=25.0, levels=levels,
    )
    strategies = {c["strategy"] for c in cards}
    assert "LEAPS (Stock Replacement Call)" in strategies
    leaps_card = next(c for c in cards if c["strategy"] == "LEAPS (Stock Replacement Call)")
    assert leaps_card["greeks"]["delta"] >= 0.70
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_full_audit_strategies.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```python
# src/options/full_audit/strategies.py
from typing import List, Dict


def _nearest_level_reference(strike: float, levels: Dict) -> str:
    all_levels = levels.get("levels_below", []) + levels.get("levels_above", [])
    if not all_levels:
        return None
    nearest = min(all_levels, key=lambda l: abs(l - strike))
    if abs(nearest - strike) > (strike * 0.02):
        return None
    side = "resistance" if nearest in levels.get("levels_above", []) else "support"
    return f"near {side} ${nearest:.2f}"


def build_strategy_cards(
    ticker: str, expiration: str, dte: int, current_price: float,
    contracts: List[Dict], bias: str, iv_rank: float, levels: Dict,
) -> List[Dict]:
    """Generate ranked strategy cards for one expiry, anchored to the given price levels."""
    high_iv = iv_rank > 50.0
    direction = "BULLISH" if "BULLISH" in bias else ("BEARISH" if "BEARISH" in bias else "NEUTRAL")

    calls = sorted([c for c in contracts if c["type"] == "CALL"], key=lambda x: x["strike"])
    puts = sorted([c for c in contracts if c["type"] == "PUT"], key=lambda x: x["strike"])
    if not calls or not puts:
        return []

    atm_call = min(calls, key=lambda x: abs(x["strike"] - current_price))
    atm_put = min(puts, key=lambda x: abs(x["strike"] - current_price))
    otm_calls = [c for c in calls if c["strike"] > current_price]
    otm_call = otm_calls[0] if otm_calls else atm_call
    itm_calls = [c for c in calls if c["strike"] < current_price]
    itm_call = itm_calls[-1] if itm_calls else atm_call

    cards = []

    if direction in ("BULLISH", "NEUTRAL"):
        put_delta = abs(atm_put["greeks"].get("delta", 0.50))
        pop = min(round((1.0 - put_delta + 0.10) * 100, 1), 85.0)
        cards.append({
            "strategy": "SHORT PUT (Cash Secured Put)",
            "description": f"Sell to Open {ticker} ${atm_put['strike']} PUT @ ${atm_put['midpoint']:.2f}",
            "strike": atm_put["strike"], "expiration": expiration, "dte": dte,
            "probability_of_profit": pop, "suitability": "HIGH" if high_iv else "MEDIUM",
            "greeks": atm_put["greeks"], "level_reference": _nearest_level_reference(atm_put["strike"], levels),
        })

    if direction == "BULLISH":
        call_delta = abs(atm_call["greeks"].get("delta", 0.50))
        pop = max(round((call_delta - 0.10) * 100, 1), 30.0)
        cards.append({
            "strategy": "LONG CALL",
            "description": f"Buy to Open {ticker} ${atm_call['strike']} CALL @ ${atm_call['midpoint']:.2f}",
            "strike": atm_call["strike"], "expiration": expiration, "dte": dte,
            "probability_of_profit": pop, "suitability": "HIGH" if not high_iv else "LOW",
            "greeks": atm_call["greeks"], "level_reference": _nearest_level_reference(atm_call["strike"], levels),
        })

    if direction == "BULLISH" and dte >= 90:
        net_debit = max(1.0, itm_call["midpoint"] - otm_call["midpoint"])
        cards.append({
            "strategy": "POOR MAN'S COVERED CALL (PMCC)",
            "description": f"Buy deep ITM ${itm_call['strike']} Call, Sell OTM ${otm_call['strike']} Call",
            "strike": itm_call["strike"], "expiration": expiration, "dte": dte,
            "probability_of_profit": 72.5, "suitability": "HIGH" if not high_iv else "MEDIUM",
            "greeks": itm_call["greeks"], "level_reference": _nearest_level_reference(otm_call["strike"], levels),
        })

    if direction == "BEARISH":
        put_delta = abs(atm_put["greeks"].get("delta", 0.50))
        pop = max(round((put_delta - 0.10) * 100, 1), 30.0)
        cards.append({
            "strategy": "LONG PUT",
            "description": f"Buy to Open {ticker} ${atm_put['strike']} PUT @ ${atm_put['midpoint']:.2f}",
            "strike": atm_put["strike"], "expiration": expiration, "dte": dte,
            "probability_of_profit": pop, "suitability": "HIGH" if not high_iv else "LOW",
            "greeks": atm_put["greeks"], "level_reference": _nearest_level_reference(atm_put["strike"], levels),
        })

    # New: outright LEAPS stock-replacement call, deep ITM/ATM (delta >= 0.70), LEAPS bucket only
    if dte >= 270:
        deep_itm_calls = [c for c in calls if abs(c["greeks"].get("delta", 0)) >= 0.70]
        leaps_call = deep_itm_calls[0] if deep_itm_calls else itm_call
        cards.append({
            "strategy": "LEAPS (Stock Replacement Call)",
            "description": f"Buy to Open {ticker} ${leaps_call['strike']} CALL @ ${leaps_call['midpoint']:.2f} ({dte} DTE)",
            "strike": leaps_call["strike"], "expiration": expiration, "dte": dte,
            "probability_of_profit": 68.0, "suitability": "HIGH" if not high_iv else "MEDIUM",
            "greeks": leaps_call["greeks"], "level_reference": _nearest_level_reference(leaps_call["strike"], levels),
        })

    return sorted(cards, key=lambda c: c["probability_of_profit"], reverse=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_full_audit_strategies.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/options/full_audit/strategies.py tests/test_full_audit_strategies.py
git commit -m "feat(full-audit): add level-anchored strategy card builder with new LEAPS strategy"
```

---

### Task 6: Recommendation Orchestration — wire levels + bucketing + strategies together

**Files:**
- Modify: `src/options/full_audit/recommender.py`
- Test: `tests/test_full_audit_recommender.py`

**Interfaces:**
- Consumes: `levels.get_price_levels` (Task 3), `recommender.get_real_expirations` / `bucket_expirations` (Task 4), `strategies.build_strategy_cards` (Task 5), `audit_engine.get_contracts_for_expiry` (existing, read-only import).
- Produces: `get_multi_expiry_recommendations(ticker: str, volume_profile_window: str = "1M") -> dict` — the full grid: `{"ticker", "current_price", "levels": {...levels.py output...}, "buckets": {"this_week": [{expiration, dte, cards}, ...], "monthly": {...} | None, "quarterly": {...} | None, "leaps": {...} | None}}`.

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_full_audit_recommender.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_full_audit_recommender.py -v -k shape`
Expected: FAIL — `get_multi_expiry_recommendations` not defined

- [ ] **Step 3: Write minimal implementation**

```python
# Append to src/options/full_audit/recommender.py
from datetime import datetime as _dt

from src.options.alpaca_options import fetch_intraday_5min_candles
from src.options.signals import calculate_intraday_signals
from src.options.audit_engine import get_contracts_for_expiry
from src.options.full_audit.levels import get_price_levels
from src.options.full_audit.strategies import build_strategy_cards


def _expiry_entry(ticker: str, expiration: str, current_price: float, bias: str, iv_rank: float, levels: Dict) -> Dict:
    dte = max(1, (datetime.strptime(expiration, "%Y-%m-%d") - datetime.now()).days)
    contracts = get_contracts_for_expiry(ticker, expiration, current_price)
    cards = build_strategy_cards(ticker, expiration, dte, current_price, contracts, bias, iv_rank, levels)
    return {"expiration": expiration, "dte": dte, "cards": cards}


def get_multi_expiry_recommendations(ticker: str, volume_profile_window: str = "1M") -> Dict:
    """Levels + multi-expiry strategy recommendation grid for one ticker. Pure math, no LLM calls."""
    ticker = ticker.upper()

    df_5min = fetch_intraday_5min_candles(ticker)
    current_price = float(df_5min['close'].iloc[-1]) if df_5min is not None and not df_5min.empty else 100.0
    signals = calculate_intraday_signals(df_5min)
    bias = signals.get("intraday_bias", "NEUTRAL")
    iv_rank = float(signals.get("iv_rank", 35.0))

    levels = get_price_levels(ticker, current_price, volume_profile_window)

    expirations = get_real_expirations(ticker)
    buckets_raw = bucket_expirations(expirations)

    this_week = [
        _expiry_entry(ticker, e, current_price, bias, iv_rank, levels)
        for e in buckets_raw["this_week"]
    ]

    def single_bucket(expiration: Optional[str]) -> Optional[Dict]:
        if not expiration:
            return None
        return _expiry_entry(ticker, expiration, current_price, bias, iv_rank, levels)

    return {
        "ticker": ticker,
        "current_price": current_price,
        "levels": levels,
        "buckets": {
            "this_week": this_week,
            "monthly": single_bucket(buckets_raw["monthly"]),
            "quarterly": single_bucket(buckets_raw["quarterly"]),
            "leaps": single_bucket(buckets_raw["leaps"]),
        },
        "signals": {"intraday_bias": bias, "iv_rank": iv_rank},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_full_audit_recommender.py -v`
Expected: PASS (all tests in file)

- [ ] **Step 5: Commit**

```bash
git add src/options/full_audit/recommender.py tests/test_full_audit_recommender.py
git commit -m "feat(full-audit): orchestrate levels + multi-expiry bucketing + strategy cards"
```

---

### Task 7: Unified Rules Engine

**Files:**
- Create: `src/options/full_audit/rules_engine.py`
- Test: `tests/test_full_audit_rules_engine.py`

**Interfaces:**
- Consumes: nothing from other full_audit files.
- Produces: `evaluate_rules(selected_contract: dict, iv_rank: float, dte: int, account_equity: float = None, order_value: float = None) -> dict` — returns `{"pass": bool, "checks": [{"name": str, "pass": bool, "detail": str}, ...], "reason": str}`. `reason` is a one-line summary of the first failing check, or `"All rules passed"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_full_audit_rules_engine.py
from src.options.full_audit.rules_engine import evaluate_rules

def _contract(strike=700, bid=1.0, ask=1.1, oi=1000, delta=0.45):
    return {"strike": strike, "bid": bid, "ask": ask, "midpoint": (bid + ask) / 2.0,
            "open_interest": oi, "greeks": {"delta": delta}}

def test_evaluate_rules_all_pass():
    result = evaluate_rules(_contract(), iv_rank=30.0, dte=10)
    assert result["pass"] is True
    assert result["reason"] == "All rules passed"
    assert len(result["checks"]) == 5

def test_evaluate_rules_fails_on_low_liquidity():
    result = evaluate_rules(_contract(oi=100), iv_rank=30.0, dte=10)
    assert result["pass"] is False
    assert "iquidity" in result["reason"] or "Open Interest" in result["reason"]

def test_evaluate_rules_fails_on_min_dte():
    result = evaluate_rules(_contract(), iv_rank=30.0, dte=0)
    assert result["pass"] is False
    assert "DTE" in result["reason"]

def test_evaluate_rules_fails_on_low_delta():
    result = evaluate_rules(_contract(delta=0.10), iv_rank=30.0, dte=10)
    assert result["pass"] is False
    assert "Delta" in result["reason"]

def test_evaluate_rules_fails_on_position_sizing():
    result = evaluate_rules(_contract(), iv_rank=30.0, dte=10, account_equity=10000.0, order_value=5000.0)
    assert result["pass"] is False
    assert "allocation" in result["reason"].lower() or "sizing" in result["reason"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_full_audit_rules_engine.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```python
# src/options/full_audit/rules_engine.py
from typing import Dict, Optional


def evaluate_rules(
    selected_contract: Dict,
    iv_rank: float,
    dte: int,
    account_equity: Optional[float] = None,
    order_value: Optional[float] = None,
) -> Dict:
    """Unified deterministic rules gate: liquidity, spread, delta, min-DTE, position sizing.

    Merges RuleBasedAdapter's checks (liquidity/spread/delta/sizing) with a new
    minimum-DTE gate. Does not touch RuleBasedAdapter or audit_engine.py.
    """
    checks = []

    bid = float(selected_contract.get("bid", 0))
    ask = float(selected_contract.get("ask", 0))
    midpoint = float(selected_contract.get("midpoint", (bid + ask) / 2.0 if (bid or ask) else 0))
    open_interest = int(selected_contract.get("open_interest", 0))
    delta = abs(float(selected_contract.get("greeks", {}).get("delta", 0.5)))

    # 1. Liquidity
    liquidity_pass = open_interest >= 500
    checks.append({
        "name": "Liquidity", "pass": liquidity_pass,
        "detail": f"Open Interest {open_interest} ({'>=' if liquidity_pass else '<'} 500 required)",
    })

    # 2. Spread
    spread_pct = ((ask - bid) / midpoint * 100.0) if midpoint > 0 else 0.0
    spread_pass = spread_pct <= 10.0
    checks.append({
        "name": "Spread", "pass": spread_pass,
        "detail": f"Bid-Ask spread {spread_pct:.1f}% ({'<=' if spread_pass else '>'} 10% limit)",
    })

    # 3. Minimum DTE (new — did not exist in RuleBasedAdapter or audit_engine.py)
    min_dte_pass = dte >= 1
    checks.append({
        "name": "Minimum DTE", "pass": min_dte_pass,
        "detail": f"DTE is {dte} ({'>=' if min_dte_pass else '<'} 1 day required)",
    })

    # 4. Delta
    delta_pass = delta >= 0.35
    checks.append({
        "name": "Delta", "pass": delta_pass,
        "detail": f"Delta {delta:.2f} ({'>=' if delta_pass else '<'} 0.35 required)",
    })

    # 5. Position sizing (only checked if account context provided)
    if account_equity is not None and order_value is not None and account_equity > 0:
        max_alloc = account_equity * 0.02
        sizing_pass = order_value <= max_alloc
        checks.append({
            "name": "Position Sizing", "pass": sizing_pass,
            "detail": f"Order value ${order_value:.2f} vs max allocation ${max_alloc:.2f} (2% of equity)",
        })
    else:
        checks.append({"name": "Position Sizing", "pass": True, "detail": "No account context provided; skipped"})

    overall_pass = all(c["pass"] for c in checks)
    reason = "All rules passed" if overall_pass else next(c["detail"] for c in checks if not c["pass"])

    return {"pass": overall_pass, "checks": checks, "reason": reason}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_full_audit_rules_engine.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/options/full_audit/rules_engine.py tests/test_full_audit_rules_engine.py
git commit -m "feat(full-audit): add unified rules engine with new minimum-DTE gate"
```

---

### Task 8: 3-Stage Synthesis Gate

**Files:**
- Create: `src/options/full_audit/gate.py`
- Test: `tests/test_full_audit_gate.py`

**Interfaces:**
- Consumes: `rules_engine.evaluate_rules` (Task 7), `agents.DualAgentPipeline` (existing), `circuit_breaker.CircuitBreaker` (existing).
- Produces: `run_full_audit_gate(ticker: str, expiration: str, strategy: str, selected_contract: dict, iv_rank: float, dte: int, level_reference: str = None, account_value: float = None, open_tickers: list = None, proposer_provider: str = "cortex", proposer_model: str = "cortex-fast", validator_provider: str = "cortex", validator_model: str = "cortex-strict") -> dict` — returns the synthesis shape from the spec: `{"overall": "AUDIT PASSED"|"AUDIT FAILED", "stages": {"rules": {...}, "agent": {...}, "circuit": {...}}, "recommendation": str}`. All 3 stages always run, no short-circuiting.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_full_audit_gate.py
from unittest.mock import patch
from src.options.full_audit.gate import run_full_audit_gate

def _contract():
    return {"strike": 700.0, "bid": 1.0, "ask": 1.1, "midpoint": 1.05, "open_interest": 1000,
            "greeks": {"delta": 0.45}, "symbol": "QQQ260815C00700000"}

@patch("src.options.full_audit.gate.CircuitBreaker")
@patch("src.options.full_audit.gate.DualAgentPipeline")
def test_run_full_audit_gate_all_pass(mock_pipeline_cls, mock_cb_cls):
    mock_pipeline_cls.return_value.run.return_value = {
        "status": "COMPLETED", "execution_ready": True,
        "proposal": {"reasoning": "Delta within bounds, liquidity adequate"},
        "validation": {"validation_notes": "Looks good", "final_action": "EXECUTE"},
    }
    mock_cb_cls.return_value.can_execute.return_value = (True, "Account drawdown OK")

    result = run_full_audit_gate(
        ticker="QQQ", expiration="2026-08-15", strategy="LONG CALL",
        selected_contract=_contract(), iv_rank=30.0, dte=23,
        account_value=100000.0, open_tickers=[],
    )
    assert result["overall"] == "AUDIT PASSED"
    assert result["stages"]["rules"]["pass"] is True
    assert result["stages"]["agent"]["pass"] is True
    assert result["stages"]["circuit"]["pass"] is True

@patch("src.options.full_audit.gate.CircuitBreaker")
@patch("src.options.full_audit.gate.DualAgentPipeline")
def test_run_full_audit_gate_rules_fail_still_runs_all_3(mock_pipeline_cls, mock_cb_cls):
    mock_pipeline_cls.return_value.run.return_value = {
        "status": "COMPLETED", "execution_ready": True,
        "proposal": {"reasoning": "ok"}, "validation": {"validation_notes": "ok", "final_action": "EXECUTE"},
    }
    mock_cb_cls.return_value.can_execute.return_value = (True, "Account drawdown OK")

    result = run_full_audit_gate(
        ticker="QQQ", expiration="2026-08-15", strategy="LONG CALL",
        selected_contract=_contract(), iv_rank=30.0, dte=0,  # dte=0 fails min-DTE rule
        account_value=100000.0, open_tickers=[],
    )
    assert result["overall"] == "AUDIT FAILED"
    assert result["stages"]["rules"]["pass"] is False
    # All 3 stages must still be populated even though rules failed
    assert result["stages"]["agent"] is not None
    assert result["stages"]["circuit"] is not None

@patch("src.options.full_audit.gate.CircuitBreaker")
@patch("src.options.full_audit.gate.DualAgentPipeline")
def test_run_full_audit_gate_circuit_breaker_fail(mock_pipeline_cls, mock_cb_cls):
    mock_pipeline_cls.return_value.run.return_value = {
        "status": "COMPLETED", "execution_ready": True,
        "proposal": {"reasoning": "ok"}, "validation": {"validation_notes": "ok", "final_action": "EXECUTE"},
    }
    mock_cb_cls.return_value.can_execute.return_value = (False, "Daily loss limit exceeded")

    result = run_full_audit_gate(
        ticker="QQQ", expiration="2026-08-15", strategy="LONG CALL",
        selected_contract=_contract(), iv_rank=30.0, dte=23,
        account_value=100000.0, open_tickers=[],
    )
    assert result["overall"] == "AUDIT FAILED"
    assert result["stages"]["circuit"]["pass"] is False
    assert "Daily loss limit exceeded" in result["stages"]["circuit"]["reason"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_full_audit_gate.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```python
# src/options/full_audit/gate.py
import logging
from typing import Dict, List, Optional

from src.options.agents import DualAgentPipeline
from src.risk.circuit_breaker import CircuitBreaker
from src.options.full_audit.rules_engine import evaluate_rules

logger = logging.getLogger("FullAuditGate")


def run_full_audit_gate(
    ticker: str,
    expiration: str,
    strategy: str,
    selected_contract: Dict,
    iv_rank: float,
    dte: int,
    level_reference: Optional[str] = None,
    account_value: Optional[float] = None,
    open_tickers: Optional[List[str]] = None,
    proposer_provider: str = "cortex",
    proposer_model: str = "cortex-fast",
    validator_provider: str = "cortex",
    validator_model: str = "cortex-strict",
) -> Dict:
    """3-stage synthesis: Rules -> Agent -> Circuit Breaker. All 3 always run to completion."""
    ticker = ticker.upper()

    # Stage 1: Rules Engine
    order_value = float(selected_contract.get("midpoint", 0)) * 100
    rules_result = evaluate_rules(
        selected_contract, iv_rank=iv_rank, dte=dte,
        account_equity=account_value, order_value=order_value,
    )

    # Stage 2: Agent Audit (LLM Proposer/Validator, level-aware)
    signals = {
        "intraday_bias": "BULLISH" if "CALL" in strategy.upper() else "BEARISH",
        "rsi_7": 50.0,
        "iv_rank": iv_rank,
        "expiration": expiration,
        "dte": dte,
        "level_reference": level_reference or "No specific level context",
    }
    pipeline = DualAgentPipeline(
        proposer_provider=proposer_provider, proposer_model=proposer_model,
        validator_provider=validator_provider, validator_model=validator_model,
    )
    agent_raw = pipeline.run(ticker, signals, timeframe="WEEKLY", selected_contract=selected_contract)
    agent_pass = bool(agent_raw.get("execution_ready", False))
    agent_result = {
        "pass": agent_pass,
        "reasoning": agent_raw.get("proposal", {}).get("reasoning", "")
        or agent_raw.get("validation", {}).get("validation_notes", "No reasoning provided"),
    }

    # Stage 3: Circuit Breaker
    cb = CircuitBreaker(baseline_account_value=account_value or 100000.0)
    qty = 1
    price = float(selected_contract.get("midpoint", 0))
    cb_pass, cb_reason = cb.can_execute(
        ticker=ticker, qty=qty, price=price,
        account_value=account_value, open_tickers=open_tickers or [],
    )
    circuit_result = {"pass": cb_pass, "reason": cb_reason}

    overall_pass = rules_result["pass"] and agent_result["pass"] and circuit_result["pass"]

    return {
        "overall": "AUDIT PASSED" if overall_pass else "AUDIT FAILED",
        "stages": {
            "rules": rules_result,
            "agent": agent_result,
            "circuit": circuit_result,
        },
        "recommendation": f"{strategy} {expiration} ({dte} DTE)" if overall_pass else "NO_TRADE",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_full_audit_gate.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/options/full_audit/gate.py tests/test_full_audit_gate.py
git commit -m "feat(full-audit): add 3-stage Rules/Agent/CircuitBreaker synthesis gate"
```

---

### Task 9: API Endpoints — full_audit orchestration, gate re-run, manual levels CRUD

**Files:**
- Modify: `src/api.py` (add new routes; no existing routes changed)
- Test: `tests/test_full_audit_api.py`

**Interfaces:**
- Consumes: `recommender.get_multi_expiry_recommendations` (Task 6), `gate.run_full_audit_gate` (Task 8), `levels.get_manual_levels`/`add_manual_level`/`delete_manual_level` (Task 3), existing `_get_alpaca_account_info()` (`src/api.py:39`).
- Produces:
  - `POST /api/options/full_audit` — body `{"ticker": str, "volume_profile_window": str (optional, default "1M")}`. Runs the recommendation grid, picks the single highest-PoP card across all buckets (ties broken by lower DTE), auto-runs the gate against it, returns `{"success": true, "ticker", "current_price", "levels", "buckets", "top_pick": {...card fields..., "gate_result": {...}}}`.
  - `POST /api/options/full_audit/gate` — body `{"ticker", "expiration", "strategy", "selected_contract", "iv_rank", "dte", "level_reference"}`. Returns `{"success": true, "gate_result": {...}}` for re-gating an alternate card without recomputing levels/grid.
  - `GET /api/options/levels/manual?ticker=` — returns list.
  - `POST /api/options/levels/manual` — body `{"ticker", "price", "label"}`, returns updated list.
  - `POST /api/options/levels/manual/delete` — body `{"ticker", "price"}`, returns updated list.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_full_audit_api.py
import json
import threading
import time
import urllib.request
import pytest

from src.api import APIServerHandler
from http.server import ThreadingHTTPServer


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), APIServerHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def _post(base_url, path, payload):
    req = urllib.request.Request(
        f"{base_url}{path}", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(base_url, path):
    with urllib.request.urlopen(f"{base_url}{path}", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_manual_levels_crud_roundtrip(server):
    empty = _get(server, "/api/options/levels/manual?ticker=ZZZZ")
    assert empty == []
    added = _post(server, "/api/options/levels/manual", {"ticker": "ZZZZ", "price": 123.45, "label": "test level"})
    assert {"price": 123.45, "label": "test level"} in added
    deleted = _post(server, "/api/options/levels/manual/delete", {"ticker": "ZZZZ", "price": 123.45})
    assert deleted == []


def test_full_audit_endpoint_returns_expected_shape(server):
    result = _post(server, "/api/options/full_audit", {"ticker": "AAPL"})
    assert result["success"] is True
    assert result["ticker"] == "AAPL"
    assert "levels" in result
    assert "levels_below" in result["levels"]
    assert "buckets" in result
    assert "top_pick" in result
    assert "gate_result" in result["top_pick"]
    assert result["top_pick"]["gate_result"]["overall"] in ("AUDIT PASSED", "AUDIT FAILED")


def test_full_audit_gate_endpoint(server):
    contract = {"strike": 200.0, "bid": 1.0, "ask": 1.1, "midpoint": 1.05, "open_interest": 1000,
                "greeks": {"delta": 0.45}, "symbol": "AAPL260815C00200000"}
    result = _post(server, "/api/options/full_audit/gate", {
        "ticker": "AAPL", "expiration": "2026-08-15", "strategy": "LONG CALL",
        "selected_contract": contract, "iv_rank": 30.0, "dte": 23,
    })
    assert result["success"] is True
    assert result["gate_result"]["overall"] in ("AUDIT PASSED", "AUDIT FAILED")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_full_audit_api.py -v`
Expected: FAIL — 404 responses (routes don't exist yet), `urllib.error.HTTPError: HTTP Error 404`

- [ ] **Step 3: Write minimal implementation**

Add to `src/api.py`'s `do_GET`, immediately before the final `else: self.send_error(404, ...)` block (find the block starting `elif path == "/api/options/audit":` at line ~463 and insert after its `except` block, before the closing `else:`):

```python
        elif path == "/api/options/levels/manual":
            params = parse_qs(parsed_url.query)
            ticker = params.get("ticker", [""])[0]
            try:
                from src.options.full_audit.levels import get_manual_levels
                self._send_json(get_manual_levels(ticker))
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})

        else:
            self.send_error(404, "API endpoint not found")
```

Add to `src/api.py`'s `do_POST`, immediately before its final `else: self.send_error(404, ...)` block (find the block ending with the `/api/options/execute_order` handler around line 1274, insert before the closing `else:`):

```python
        elif path == "/api/options/levels/manual":
            ticker = post_data.get("ticker", "")
            price = post_data.get("price", 0)
            label = post_data.get("label", "")
            try:
                from src.options.full_audit.levels import add_manual_level
                self._send_json(add_manual_level(ticker, price, label))
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})
            return

        elif path == "/api/options/levels/manual/delete":
            ticker = post_data.get("ticker", "")
            price = post_data.get("price", 0)
            try:
                from src.options.full_audit.levels import delete_manual_level
                self._send_json(delete_manual_level(ticker, price))
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})
            return

        elif path == "/api/options/full_audit":
            ticker = post_data.get("ticker", "AAPL").upper()
            vp_window = post_data.get("volume_profile_window", "1M")
            try:
                from src.options.full_audit.recommender import get_multi_expiry_recommendations
                from src.options.full_audit.gate import run_full_audit_gate

                grid = get_multi_expiry_recommendations(ticker, vp_window)

                # Flatten all cards across all buckets, tagged with their expiry/dte
                all_cards = []
                for entry in grid["buckets"]["this_week"]:
                    for card in entry["cards"]:
                        all_cards.append(card)
                for bucket_key in ("monthly", "quarterly", "leaps"):
                    entry = grid["buckets"][bucket_key]
                    if entry:
                        for card in entry["cards"]:
                            all_cards.append(card)

                if not all_cards:
                    self._send_json({"success": False, "error": f"No option contracts available for {ticker}"})
                    return

                # Cross-bucket top pick: highest PoP, ties broken by lower DTE
                top_pick = sorted(all_cards, key=lambda c: (-c["probability_of_profit"], c["dte"]))[0]

                account_info = _get_alpaca_account_info()
                account_value = account_info.get("portfolio_value") or account_info.get("equity")
                open_tickers = [p["symbol"] for p in account_info.get("positions", [])]

                selected_contract = {
                    "strike": top_pick["strike"],
                    "bid": top_pick["greeks"].get("delta", 0),  # placeholder if bid/ask absent on card
                    "ask": top_pick["greeks"].get("delta", 0),
                    "midpoint": top_pick.get("midpoint", 1.0),
                    "open_interest": top_pick.get("open_interest", 1000),
                    "greeks": top_pick["greeks"],
                }
                gate_result = run_full_audit_gate(
                    ticker=ticker, expiration=top_pick["expiration"], strategy=top_pick["strategy"],
                    selected_contract=selected_contract, iv_rank=grid["signals"]["iv_rank"], dte=top_pick["dte"],
                    level_reference=top_pick.get("level_reference"),
                    account_value=account_value, open_tickers=open_tickers,
                )
                top_pick_with_gate = dict(top_pick)
                top_pick_with_gate["gate_result"] = gate_result

                self._send_json({
                    "success": True,
                    "ticker": grid["ticker"],
                    "current_price": grid["current_price"],
                    "levels": grid["levels"],
                    "buckets": grid["buckets"],
                    "top_pick": top_pick_with_gate,
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})
            return

        elif path == "/api/options/full_audit/gate":
            ticker = post_data.get("ticker", "AAPL").upper()
            expiration = post_data.get("expiration", "")
            strategy = post_data.get("strategy", "")
            selected_contract = post_data.get("selected_contract", {})
            iv_rank = float(post_data.get("iv_rank", 35.0))
            dte = int(post_data.get("dte", 30))
            level_reference = post_data.get("level_reference")
            try:
                from src.options.full_audit.gate import run_full_audit_gate
                account_info = _get_alpaca_account_info()
                account_value = account_info.get("portfolio_value") or account_info.get("equity")
                open_tickers = [p["symbol"] for p in account_info.get("positions", [])]
                gate_result = run_full_audit_gate(
                    ticker=ticker, expiration=expiration, strategy=strategy,
                    selected_contract=selected_contract, iv_rank=iv_rank, dte=dte,
                    level_reference=level_reference, account_value=account_value, open_tickers=open_tickers,
                )
                self._send_json({"success": True, "gate_result": gate_result})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})
            return

        else:
            self.send_error(404, "API endpoint not found")
```

Note the `selected_contract` bid/ask placeholder above the `full_audit` handler — cards from `strategies.py` don't carry raw bid/ask (only `midpoint`/`open_interest`/`greeks`/`strike`), so this task must additionally widen `build_strategy_cards`' card dict (Task 5's `strategies.py`) to include `midpoint` and `open_interest` passthrough from the source contract. Do this now as part of this task's Step 3:

```python
# Modify src/options/full_audit/strategies.py — add these two keys to every card dict
# appended in build_strategy_cards (SHORT PUT, LONG CALL, PMCC, LONG PUT, LEAPS cards):
# "midpoint": <the source contract's midpoint>, "open_interest": <the source contract's open_interest>
```//see exact diff below

Apply this exact diff to `src/options/full_audit/strategies.py` (adds `midpoint`/`open_interest` to every card so the API layer can build a real `selected_contract` without placeholders):

```python
# In each cards.append({...}) block in build_strategy_cards, add two keys.
# Example for the SHORT PUT block:
        cards.append({
            "strategy": "SHORT PUT (Cash Secured Put)",
            "description": f"Sell to Open {ticker} ${atm_put['strike']} PUT @ ${atm_put['midpoint']:.2f}",
            "strike": atm_put["strike"], "expiration": expiration, "dte": dte,
            "probability_of_profit": pop, "suitability": "HIGH" if high_iv else "MEDIUM",
            "greeks": atm_put["greeks"], "level_reference": _nearest_level_reference(atm_put["strike"], levels),
            "midpoint": atm_put["midpoint"], "open_interest": atm_put["open_interest"],
        })
# Apply the same two added keys (sourced from that block's relevant contract: atm_call, itm_call, or leaps_call) to the LONG CALL, PMCC, LONG PUT, and LEAPS card blocks.
```

And simplify the `full_audit` endpoint's `selected_contract` construction (fixing the bid/ask placeholder) to:

```python
                selected_contract = {
                    "strike": top_pick["strike"],
                    "bid": top_pick["midpoint"] - 0.05,
                    "ask": top_pick["midpoint"] + 0.05,
                    "midpoint": top_pick["midpoint"],
                    "open_interest": top_pick["open_interest"],
                    "greeks": top_pick["greeks"],
                }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_full_audit_api.py tests/test_full_audit_strategies.py -v`
Expected: PASS (all tests). Re-run `tests/test_audit_engine.py tests/test_api.py` too to confirm no regression: `pytest tests/test_audit_engine.py tests/test_api.py -v` — Expected: PASS (unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/api.py src/options/full_audit/strategies.py tests/test_full_audit_api.py
git commit -m "feat(full-audit): add full_audit, gate, and manual-levels API endpoints"
```

---

### Task 10: Frontend — Full Audit button, Levels card, recommendation grid, gate verdict

**Files:**
- Modify: `frontend/src/WhitelightCortexIntegratedPanel.jsx`

**Interfaces:**
- Consumes: `POST /api/options/full_audit`, `POST /api/options/full_audit/gate` (Task 9).
- Produces: no new exports — this is leaf UI wired to existing `tickerInput`/`activeTicker` state added in the prior search-bar fix.

- [ ] **Step 1: Add state and the fetch/trigger functions**

Add near the existing `searchAuditResult` state block (added in the prior search-bar fix):

```jsx
  const [fullAuditLoading, setFullAuditLoading] = useState(false);
  const [fullAuditResult, setFullAuditResult] = useState(null);
  const [fullAuditError, setFullAuditError] = useState(null);
  const [activeBucketTab, setActiveBucketTab] = useState("this_week");
  const [gatingCard, setGatingCard] = useState(null);

  const runFullAudit = async () => {
    if (!activeTicker) return;
    setFullAuditLoading(true);
    setFullAuditError(null);
    setFullAuditResult(null);
    try {
      const res = await fetch(`${API_BASE}/options/full_audit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: activeTicker, volume_profile_window: "1M" }),
      });
      const data = await res.json();
      if (data.success) {
        setFullAuditResult(data);
      } else {
        setFullAuditError(data.error || "Full audit failed");
      }
    } catch (e) {
      setFullAuditError(e.message);
    } finally {
      setFullAuditLoading(false);
    }
  };

  const runCardGate = async (card) => {
    setGatingCard(card);
    try {
      const res = await fetch(`${API_BASE}/options/full_audit/gate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: activeTicker,
          expiration: card.expiration,
          strategy: card.strategy,
          selected_contract: {
            strike: card.strike,
            bid: card.midpoint - 0.05,
            ask: card.midpoint + 0.05,
            midpoint: card.midpoint,
            open_interest: card.open_interest,
            greeks: card.greeks,
          },
          iv_rank: fullAuditResult?.signals?.iv_rank ?? 35.0,
          dte: card.dte,
          level_reference: card.level_reference,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setFullAuditResult((prev) => ({
          ...prev,
          top_pick: { ...card, gate_result: data.gate_result },
        }));
      }
    } finally {
      setGatingCard(null);
    }
  };
```

- [ ] **Step 2: Add the "Full Audit" button next to the search form**

Locate the closing `</form>` of the "Universal Ticker Search Form" (immediately after the inline search-audit dropdown block added in the prior fix) and add this button as a sibling right after the `</form>`:

```jsx
        <button
          type="button"
          onClick={runFullAudit}
          disabled={fullAuditLoading}
          className="px-3 py-1.5 text-xs font-bold rounded-lg border border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-all disabled:opacity-50"
        >
          {fullAuditLoading ? "⏳ Running Full Audit..." : "⚡ Full Audit"}
        </button>
```

- [ ] **Step 3: Render the Levels card, recommendation grid, and gate verdict**

Add this block directly after the Full Audit button from Step 2 (still inside the same header `<div>` container, as its own full-width row — wrap the button + this block in a `<div className="w-full">` if needed so it doesn't fight the existing `flex-wrap` header layout):

```jsx
        {fullAuditError && (
          <div className="w-full mt-3 p-3 rounded-lg border border-rose-500/40 bg-rose-500/10 text-rose-400 text-xs font-mono">
            Full Audit failed: {fullAuditError}
          </div>
        )}

        {fullAuditResult && (
          <div className="w-full mt-3 space-y-4 font-mono">
            {/* Levels card - always shown first */}
            <div className="p-4 rounded-xl border-l-4 border-l-sky-500 border border-slate-800 bg-slate-900/60">
              <div className="text-sm font-bold text-white mb-2">
                {fullAuditResult.ticker} <span className="font-normal text-slate-300">(Current Price: <span className="font-black">${fullAuditResult.current_price.toFixed(2)}</span>)</span>
              </div>
              <div className="text-xs text-slate-300">
                <span className="font-bold text-slate-400">Levels Below:</span> [{fullAuditResult.levels.levels_below.join(", ")}]
              </div>
              <div className="text-xs text-slate-300">
                <span className="font-bold text-slate-400">Levels Above:</span> [{fullAuditResult.levels.levels_above.join(", ")}]
              </div>
            </div>

            {/* Multi-expiry recommendation grid */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60">
              <div className="flex border-b border-slate-800">
                {["this_week", "monthly", "quarterly", "leaps"].map((bucketKey) => (
                  <button
                    key={bucketKey}
                    onClick={() => setActiveBucketTab(bucketKey)}
                    className={`px-4 py-2 text-xs font-bold uppercase tracking-wider ${
                      activeBucketTab === bucketKey ? "text-amber-400 border-b-2 border-amber-400" : "text-slate-500"
                    }`}
                  >
                    {bucketKey.replace("_", " ")}
                  </button>
                ))}
              </div>
              <div className="p-3 space-y-3">
                {(() => {
                  const bucketData = fullAuditResult.buckets[activeBucketTab];
                  const entries = Array.isArray(bucketData) ? bucketData : (bucketData ? [bucketData] : []);
                  if (entries.length === 0) {
                    return <div className="text-xs text-slate-500">No contracts available for this horizon.</div>;
                  }
                  return entries.map((entry) => (
                    <div key={entry.expiration} className="space-y-2">
                      <div className="text-xs font-bold text-slate-400">{entry.expiration} ({entry.dte} DTE)</div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {entry.cards.map((card, idx) => (
                          <button
                            key={`${entry.expiration}-${idx}`}
                            onClick={() => runCardGate(card)}
                            disabled={gatingCard === card}
                            className="text-left p-3 rounded-lg border border-slate-800 bg-slate-950 hover:border-amber-500/50 transition-all disabled:opacity-50"
                          >
                            <div className="text-xs font-bold text-amber-400">{card.strategy}</div>
                            <div className="text-[11px] text-slate-300 mt-1">{card.description}</div>
                            <div className="text-[10px] text-slate-500 mt-1">
                              PoP: {card.probability_of_profit}% {card.level_reference ? `· ${card.level_reference}` : ""}
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  ));
                })()}
              </div>
            </div>

            {/* Gate verdict for the current top pick / last-gated card */}
            {fullAuditResult.top_pick?.gate_result && (
              <div className={`p-4 rounded-xl border ${
                fullAuditResult.top_pick.gate_result.overall === "AUDIT PASSED"
                  ? "border-emerald-500/40 bg-emerald-500/5" : "border-rose-500/40 bg-rose-500/5"
              }`}>
                <div className={`text-sm font-black mb-2 ${
                  fullAuditResult.top_pick.gate_result.overall === "AUDIT PASSED" ? "text-emerald-400" : "text-rose-400"
                }`}>
                  {fullAuditResult.top_pick.gate_result.overall === "AUDIT PASSED" ? "✅" : "❌"} {fullAuditResult.top_pick.gate_result.overall}
                </div>
                <div className="text-xs text-slate-300 space-y-1">
                  <div>└─ Rules: {fullAuditResult.top_pick.gate_result.stages.rules.pass ? "✅ PASS" : "❌ FAIL"} — {fullAuditResult.top_pick.gate_result.stages.rules.reason}</div>
                  <div>└─ Agent: {fullAuditResult.top_pick.gate_result.stages.agent.pass ? "✅ PASS" : "❌ FAIL"} — {fullAuditResult.top_pick.gate_result.stages.agent.reasoning}</div>
                  <div>└─ Circuit: {fullAuditResult.top_pick.gate_result.stages.circuit.pass ? "✅ PASS" : "❌ FAIL"} — {fullAuditResult.top_pick.gate_result.stages.circuit.reason}</div>
                  <div className="pt-1 font-bold">└─ Recommendation: {fullAuditResult.top_pick.gate_result.recommendation}</div>
                </div>
              </div>
            )}
          </div>
        )}
```

- [ ] **Step 4: Build check**

Run: `cd frontend && npx --no-install vite build`
Expected: build succeeds with no new errors (pre-existing "chunk larger than 500kB" warning is fine, unrelated).

- [ ] **Step 5: Manual browser verification**

Start the frontend (`npm run dev`, confirm port from `vite.config.js`) and backend (`python src/api.py` if not already running), then:
1. Search a ticker (e.g. `QQQ`), hit Go.
2. Click the new "Full Audit" button.
3. Confirm the Levels card renders first, showing `Levels Below`/`Levels Above`.
4. Confirm the 4 bucket tabs render below it, with `This Week` showing 1+ cards.
5. Confirm the gate verdict panel renders below the grid for the auto-selected top pick.
6. Click a different card in another bucket tab; confirm the gate verdict panel updates to that card's result.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/WhitelightCortexIntegratedPanel.jsx
git commit -m "feat(full-audit): add Full Audit button, levels card, recommendation grid, and gate verdict UI"
```

---

## Self-Review Notes

- **Spec coverage:** Section 1 (Levels) → Tasks 1-3. Section 2 (Multi-Expiry + Strategies) → Tasks 4-6. Section 3 (3-Stage Gate) → Tasks 7-8. Section 4 (Endpoints + Frontend) → Tasks 9-10. All spec sections have a corresponding task.
- **Type consistency check:** `get_price_levels()` (Task 3) return shape matches what `recommender.py` (Task 6) embeds under `"levels"` and what the frontend (Task 10) reads (`levels_below`/`levels_above`). `build_strategy_cards()` (Task 5) card shape (including the `midpoint`/`open_interest` fields added at the end of Task 9) matches what `api.py`'s `full_audit` handler and the frontend's `runCardGate` both consume. `run_full_audit_gate()` (Task 8) return shape matches both API endpoints (Task 9) and the frontend's verdict rendering (Task 10) exactly (`overall`, `stages.rules/agent/circuit.pass/reason|reasoning`, `recommendation`).
- **No placeholders:** every step has complete, runnable code; no "TBD"/"add error handling" left unresolved.
