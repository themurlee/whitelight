import os
import json
import time
from datetime import datetime, timezone, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

import sys
# Configure path imports
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

import src.config as config

def log_to_journal(message: str, level: str = "INFO"):
    os.makedirs(config.JOURNAL_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log_line = f"[{timestamp}] [{level}] {message}\n"
    with open(config.TRADE_LOG_PATH, "a") as f:
        f.write(log_line)
    print(f"[{level}] {message}")

def fetch_and_save_ohlcv(ticker: str, days_to_fetch: int = 400):
    """
    Fetches historical OHLCV data for a ticker and saves each day's bar
    into data/{ticker}/YYYY-MM-DD.jsonl if the file does not exist.
    """
    ticker_dir = os.path.join(config.DATA_DIR, ticker)
    os.makedirs(ticker_dir, exist_ok=True)

    if not config.API_KEY or not config.SECRET_KEY:
        log_to_journal("Alpaca credentials missing in environment", "ERROR")
        return False

    # Determine date range (offset 16 min for free tier)
    end_date = datetime.now(timezone.utc) - timedelta(minutes=16)
    start_date = end_date - timedelta(days=days_to_fetch)
    
    # Pre-check: which dates are missing?
    missing_dates = []
    current_check = start_date
    while current_check <= end_date:
        date_str = current_check.strftime("%Y-%m-%d")
        file_path = os.path.join(ticker_dir, f"{date_str}.jsonl")
        if not os.path.exists(file_path):
            missing_dates.append(current_check)
        current_check += timedelta(days=1)

    if not missing_dates:
        log_to_journal(f"All files for {ticker} up to date. Skipping fetch.", "INFO")
        return True

    log_to_journal(f"Fetching data for {ticker} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...", "INFO")
    
    # Initialize client and fetch with retries
    retries = 3
    bars = None
    for attempt in range(retries):
        try:
            client = StockHistoricalDataClient(config.API_KEY, config.SECRET_KEY)
            request = StockBarsRequest(
                symbol_or_symbols=[ticker],
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date,
                feed=DataFeed.IEX
            )
            bars = client.get_stock_bars(request)
            break
        except Exception as e:
            log_to_journal(f"API attempt {attempt+1} failed: {e}", "WARNING")
            if attempt < retries - 1:
                time.sleep(2)
            else:
                log_to_journal(f"Failed to fetch data for {ticker} after {retries} retries.", "ERROR")
                return False

    if not bars or bars.df.empty:
        log_to_journal(f"No new bars returned for {ticker} (data may be current).", "INFO")
        return True

    # Save bars
    saved_count = 0
    df_reset = bars.df.reset_index()
    for _, row in df_reset.iterrows():
        timestamp = row['timestamp']
        date_str = timestamp.strftime("%Y-%m-%d")
        file_path = os.path.join(ticker_dir, f"{date_str}.jsonl")
        
        # Save only if missing
        if not os.path.exists(file_path):
            entry = {
                "timestamp": timestamp.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
                "vwap": float(row["vwap"]) if "vwap" in row else None
            }
            with open(file_path, "w") as f:
                f.write(json.dumps(entry) + "\n")
            saved_count += 1

    log_to_journal(f"Data ingestion complete for {ticker}. Saved {saved_count} daily files.", "INFO")
    return True

if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    fetch_and_save_ohlcv(ticker)
