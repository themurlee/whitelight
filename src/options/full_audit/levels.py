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
