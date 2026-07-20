import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

def calculate_intraday_signals(df_5min: pd.DataFrame) -> dict:
    """
    Computes 4 pure intraday signals strictly from today's 5-minute candles:
    1. Price direction from Open (% change)
    2. VWAP position (% distance from intraday VWAP)
    3. RSI-7 (7-period RSI on 5-min close prices)
    4. MACD(6,13,5) (Fast=6, Slow=13, Signal=5)
    
    No historical indicator pollution. Strictly today's bars.
    """
    if df_5min is None or df_5min.empty:
        return {
            "valid": False,
            "error": "No 5-minute intraday candle data available."
        }

    # Ensure index is datetime
    if not isinstance(df_5min.index, pd.DatetimeIndex):
        df_5min.index = pd.to_datetime(df_5min.index)

    # Sort by timestamp
    df = df_5min.sort_index().copy()

    # Filter strictly today's bars (or latest date in dataframe)
    latest_date = df.index[-1].date()
    today_df = df[df.index.date == latest_date].copy()

    if len(today_df) < 3:
        # Fallback to last N bars if market just opened
        today_df = df.tail(15).copy()

    closes = today_df['close'].astype(float)
    highs = today_df['high'].astype(float)
    lows = today_df['low'].astype(float)
    volumes = today_df['volume'].astype(float)

    # 1. Price direction from open
    open_price = float(today_df['open'].iloc[0])
    current_close = float(closes.iloc[-1])
    pct_from_open = ((current_close - open_price) / open_price) * 100.0

    # 2. Intraday VWAP Position
    typical_price = (highs + lows + closes) / 3.0
    cum_pv = (typical_price * volumes).cumsum()
    cum_vol = volumes.cumsum()
    # Avoid zero div
    vwap_series = np.where(cum_vol > 0, cum_pv / cum_vol, current_close)
    current_vwap = float(vwap_series[-1])
    vwap_diff_pct = ((current_close - current_vwap) / current_vwap) * 100.0

    # 3. RSI-7 on intraday closes
    delta = closes.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=7, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=7, min_periods=1).mean()
    rs = np.where(loss != 0, gain / loss, 100.0)
    rsi_series = 100.0 - (100.0 / (1.0 + rs))
    current_rsi = float(rsi_series[-1])

    # 4. MACD(6, 13, 5) on 5-min candles
    ema6 = closes.ewm(span=6, adjust=False).mean()
    ema13 = closes.ewm(span=13, adjust=False).mean()
    macd_line = ema6 - ema13
    signal_line = macd_line.ewm(span=5, adjust=False).mean()
    histogram = macd_line - signal_line

    current_macd = float(macd_line.iloc[-1])
    current_macd_signal = float(signal_line.iloc[-1])
    current_macd_hist = float(histogram.iloc[-1])

    # Classify overall intraday bias
    bias = "NEUTRAL"
    if pct_from_open > 0.3 and current_close > current_vwap and current_rsi > 55 and current_macd_hist > 0:
        bias = "STRONG_BULLISH"
    elif pct_from_open > 0.1 and current_close > current_vwap:
        bias = "BULLISH"
    elif pct_from_open < -0.3 and current_close < current_vwap and current_rsi < 45 and current_macd_hist < 0:
        bias = "STRONG_BEARISH"
    elif pct_from_open < -0.1 and current_close < current_vwap:
        bias = "BEARISH"

    return {
        "valid": True,
        "date": str(latest_date),
        "bars_count": len(today_df),
        "open_price": round(open_price, 2),
        "current_close": round(current_close, 2),
        "pct_from_open": round(pct_from_open, 2),
        "vwap": round(current_vwap, 2),
        "vwap_diff_pct": round(vwap_diff_pct, 2),
        "rsi_7": round(current_rsi, 2),
        "macd_6_13_5": {
            "macd": round(current_macd, 4),
            "signal": round(current_macd_signal, 4),
            "histogram": round(current_macd_hist, 4)
        },
        "intraday_bias": bias,
        "high_today": round(float(highs.max()), 2),
        "low_today": round(float(lows.min()), 2),
    }
