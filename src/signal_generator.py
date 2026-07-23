import os
import json
import glob
import sys
from datetime import datetime, timezone

# Configure path imports
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

import src.config as config
from src.strategy import calculate_macd, calculate_rsi
from src.storage.atomic_writer import AtomicJSONWriter

def get_signal_for_ticker(ticker: str) -> dict:
    ticker_dir = os.path.join(config.DATA_DIR, ticker)
    if not os.path.exists(ticker_dir):
        return {"error": f"No data directory found for ticker {ticker}"}

    # Load all jsonl files
    files = glob.glob(os.path.join(ticker_dir, "*.jsonl"))
    files.sort()
    
    dates = []
    prices = []
    timestamps = []
    
    for fpath in files:
        try:
            data = AtomicJSONWriter(fpath).read()
            if not data:
                continue
            dates.append(os.path.basename(fpath).replace(".jsonl", ""))
            prices.append(float(data["close"]))
            timestamps.append(data.get("timestamp", ""))
        except Exception:
            continue

    if len(prices) < 26: # Minimum required for MACD
        return {"error": f"Insufficient data points ({len(prices)} < 26) to calculate indicators."}

    # Calculate MACD and RSI
    macd_line, signal_line, histogram = calculate_macd(prices)
    rsi_line = calculate_rsi(prices)

    # Latest values
    last_close = prices[-1]
    last_macd = macd_line[-1]
    last_sig = signal_line[-1]
    last_hist = histogram[-1]
    last_rsi = rsi_line[-1]
    last_timestamp = timestamps[-1]

    # Crossover checks
    # To confirm crossover we check current and previous points
    prev_macd = macd_line[-2]
    prev_sig = signal_line[-2]

    action = "HOLD"
    
    if last_macd is not None and last_sig is not None and prev_macd is not None and prev_sig is not None:
        # Bullish Crossover: MACD crosses above signal line
        if prev_macd <= prev_sig and last_macd > last_sig:
            # RSI filter: verify not overbought
            if last_rsi is not None and last_rsi < 70:
                action = "BUY"
        # Bearish Crossover: MACD crosses below signal line
        elif prev_macd >= prev_sig and last_macd < last_sig:
            action = "SELL"

    result = {
        "ticker": ticker,
        "timestamp": last_timestamp if last_timestamp else datetime.now(timezone.utc).isoformat() + "Z",
        "close": last_close,
        "rsi": round(last_rsi, 4) if last_rsi is not None else None,
        "macd": round(last_macd, 4) if last_macd is not None else None,
        "macd_signal": round(last_sig, 4) if last_sig is not None else None,
        "macd_histogram": round(last_hist, 4) if last_hist is not None else None,
        "action": action
    }
    
    return result

def run_signal_generation(ticker: str):
    res = get_signal_for_ticker(ticker)
    if "error" in res:
        print(f"[SIGNAL GENERATOR ERROR] {res['error']}")
        return res

    signal_log_path = os.path.join(config.DATA_DIR, "signal_log.json")
    try:
        AtomicJSONWriter(signal_log_path).write(res)
        print(f"[SIGNAL GENERATOR] Signal logic complete for {ticker}: {res['action']} (RSI: {res['rsi']}, MACD: {res['macd']})")
    except Exception as e:
        print(f"[SIGNAL GENERATOR ERROR] Failed to save signal_log: {e}")
        
    return res

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    run_signal_generation(ticker)
