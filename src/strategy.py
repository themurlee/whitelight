"""
WhiteLight Systematic Trading & Analysis Pipeline - Strategy Indicators
Provides pure Python implementations of technical indicators (EMA, MACD, session VWAP)
to eliminate external dependency overhead and ensure deterministic execution.
"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime


def calculate_sma(prices: List[float], period: int) -> List[Optional[float]]:
    """
    Calculate the Simple Moving Average (SMA).
    Returns a list of the same length as prices, with None for indices < period - 1.
    """
    if not prices or period <= 0:
        return [None] * len(prices)

    sma: List[Optional[float]] = [None] * len(prices)
    if len(prices) < period:
        return sma

    # Initial SMA
    current_sum = sum(prices[:period])
    sma[period - 1] = current_sum / period

    for i in range(period, len(prices)):
        current_sum = current_sum - prices[i - period] + prices[i]
        sma[i] = current_sum / period

    return sma


def calculate_ema(prices: List[float], period: int) -> List[Optional[float]]:
    """
    Calculate the Exponential Moving Average (EMA).
    Returns a list of the same length as prices, with None for indices < period - 1.
    Uses SMA as the starting point for the first valid EMA value.
    EMA_t = Price_t * multiplier + EMA_{t-1} * (1 - multiplier)
    multiplier = 2 / (period + 1)
    """
    if not prices or period <= 0:
        return [None] * len(prices)

    ema: List[Optional[float]] = [None] * len(prices)
    if len(prices) < period:
        return ema

    # Start with SMA for the first period
    sma_vals = calculate_sma(prices, period)
    ema[period - 1] = sma_vals[period - 1]

    multiplier = 2.0 / (period + 1)

    for i in range(period, len(prices)):
        prev_ema = ema[i - 1]
        if prev_ema is not None:
            ema[i] = prices[i] * multiplier + prev_ema * (1.0 - multiplier)

    return ema


def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """
    Calculate the Moving Average Convergence Divergence (MACD).
    MACD Line = Fast EMA - Slow EMA
    Signal Line = EMA of MACD Line (with signal_period)
    Histogram = MACD Line - Signal Line

    Returns a tuple of (macd_line, signal_line, histogram) of the same length as prices.
    """
    if not prices or fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
        n = len(prices)
        return [None] * n, [None] * n, [None] * n

    # 1. Calculate Fast and Slow EMAs
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)

    # 2. Calculate MACD Line
    macd_line: List[Optional[float]] = [None] * len(prices)
    for i in range(len(prices)):
        f = fast_ema[i]
        s = slow_ema[i]
        if f is not None and s is not None:
            macd_line[i] = f - s

    # 3. Calculate Signal Line (EMA of MACD line)
    # Since MACD Line contains None in the beginning, we must handle the offset.
    # We find the first index where macd_line is not None.
    first_valid_macd_idx = next((i for i, val in enumerate(macd_line) if val is not None), -1)

    signal_line: List[Optional[float]] = [None] * len(prices)
    if first_valid_macd_idx != -1 and len(macd_line) - first_valid_macd_idx >= signal_period:
        valid_macd_slice = [val for val in macd_line[first_valid_macd_idx:] if val is not None]
        valid_signal_slice = calculate_ema(valid_macd_slice, signal_period)
        
        # Align back to the main list
        for idx_slice, val in enumerate(valid_signal_slice):
            if val is not None:
                signal_line[first_valid_macd_idx + idx_slice] = val

    # 4. Calculate Histogram
    histogram: List[Optional[float]] = [None] * len(prices)
    for i in range(len(prices)):
        m = macd_line[i]
        sig = signal_line[i]
        if m is not None and sig is not None:
            histogram[i] = m - sig

    return macd_line, signal_line, histogram


def _get_session_date(timestamp_str: str) -> str:
    """
    Extract session date string from ISO timestamp or epoch.
    Expects format like "2026-07-15T09:30:00Z" or just "2026-07-15".
    """
    try:
        # ISO string handling
        if "T" in timestamp_str:
            return timestamp_str.split("T")[0]
        # space separator
        elif " " in timestamp_str:
            return timestamp_str.split(" ")[0]
        return timestamp_str
    except Exception:
        return "default_session"


def calculate_vwap(bars: List[Dict]) -> List[Optional[float]]:
    """
    Calculate the Session Volume Weighted Average Price (VWAP).
    Each bar should be a dict containing:
    - 'high' (float)
    - 'low' (float)
    - 'close' (float)
    - 'volume' (float or int)
    - 'timestamp' (str representing date/time)

    VWAP resets at the start of each session (calendar date change).
    Typical Price = (High + Low + Close) / 3
    VWAP = Sum(Typical Price * Volume) / Sum(Volume)
    """
    if not bars:
        return []

    vwap_values: List[Optional[float]] = []
    
    current_session_date: Optional[str] = None
    cumulative_tp_vol = 0.0
    cumulative_vol = 0.0

    for bar in bars:
        high = float(bar.get("high", bar.get("close", 0)))
        low = float(bar.get("low", bar.get("close", 0)))
        close = float(bar.get("close", 0))
        volume = float(bar.get("volume", 0))
        timestamp = str(bar.get("timestamp", ""))

        session_date = _get_session_date(timestamp)

        # Check for session boundary reset
        if current_session_date != session_date:
            current_session_date = session_date
            cumulative_tp_vol = 0.0
            cumulative_vol = 0.0

        typical_price = (high + low + close) / 3.0
        
        cumulative_tp_vol += typical_price * volume
        cumulative_vol += volume

        if cumulative_vol > 0:
            vwap_values.append(cumulative_tp_vol / cumulative_vol)
        else:
            # Fallback to typical price or close if volume is zero
            vwap_values.append(typical_price)

    return vwap_values


def calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Calculate the Relative Strength Index (RSI).
    Wilder's smoothing method.
    Returns a list of the same length as prices, with None for indices < period.
    """
    if not prices or period <= 0 or len(prices) <= period:
        return [None] * len(prices)

    rsi_values: List[Optional[float]] = [None] * len(prices)

    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))

    # Initial average gain/loss (simple average over first 'period' changes)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        rsi_values[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_values[period] = 100.0 - (100.0 / (1.0 + rs))

    # Wilder's smoothing for subsequent values
    for i in range(period + 1, len(prices)):
        gain = gains[i - 1]
        loss = losses[i - 1]
        
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi_values[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_values[i] = 100.0 - (100.0 / (1.0 + rs))

    return rsi_values

