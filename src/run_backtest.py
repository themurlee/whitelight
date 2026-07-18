"""
run_backtest.py — CLI entrypoint for WhiteLight backtest engine.

Fetches daily OHLCV bars from Alpaca StockHistoricalDataClient and runs
the WhiteLight systematic strategy through the Backtester.

Usage:
    python3 src/run_backtest.py --ticker AAPL --start 2023-01-01 --end 2024-01-01
    python3 src/run_backtest.py --ticker SPY --start 2022-01-01 --end 2025-01-01 --capital 50000
"""

import argparse
import os
import sys
from datetime import datetime, timezone

# Make src importable from repo root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

import pandas as pd
import src.config as config
from src.backtest import Backtester, CostModel
from src.strategy import systematic_strategy


def fetch_alpaca_bars(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Fetch daily OHLCV bars from Alpaca StockHistoricalDataClient.
    Returns DataFrame indexed by datetime with columns: open, high, low, close, volume.
    """
    if not config.API_KEY or not config.SECRET_KEY:
        raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in environment.")

    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import DataFeed

    client = StockHistoricalDataClient(config.API_KEY, config.SECRET_KEY)

    start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    request = StockBarsRequest(
        symbol_or_symbols=[ticker],
        timeframe=TimeFrame.Day,
        start=start_dt,
        end=end_dt,
        feed=DataFeed.IEX,
    )

    bars = client.get_stock_bars(request)
    df = bars.df

    if df.empty:
        raise RuntimeError(f"No bars returned for {ticker} between {start} and {end}.")

    # Multi-index from alpaca: (symbol, timestamp) -> drop symbol level
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(ticker, level=0)

    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df.columns = [c.lower() for c in df.columns]

    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Bars missing required columns: {missing}")

    return df[["open", "high", "low", "close", "volume"]].copy()


def main():
    parser = argparse.ArgumentParser(description="WhiteLight Backtest CLI")
    parser.add_argument("--ticker", required=True, help="Equity ticker symbol (e.g. AAPL)")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=100_000.0, help="Initial capital (default: 100000)")
    parser.add_argument("--slippage-bps", type=float, default=2.0, help="Slippage in bps (default: 2.0)")
    args = parser.parse_args()

    print(f"[BACKTEST] Fetching {args.ticker} bars from {args.start} to {args.end}...")
    data = fetch_alpaca_bars(args.ticker, args.start, args.end)
    print(f"[BACKTEST] Fetched {len(data)} bars.")

    cost_model = CostModel(asset_type="equity", slippage_bps=args.slippage_bps)
    bt = Backtester(data, cost_model=cost_model, initial_capital=args.capital)

    # systematic_strategy expects volume column, which data has.
    print("[BACKTEST] Running systematic strategy (EMA50/EMA250/VWAP)...")
    result = bt.run(systematic_strategy, warmup=250)

    print()
    print(result.summary())


if __name__ == "__main__":
    main()
