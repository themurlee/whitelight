import os
import glob
import logging
from typing import List, Dict
from datetime import datetime, timedelta, timezone

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
