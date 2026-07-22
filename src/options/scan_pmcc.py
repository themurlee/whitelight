"""
WhiteLight PMCC (Poor Man's Covered Call) Short Call Scanner
Queries the Alpaca Options API to dynamically calculate minimum safe strikes
and generate alerts when technical criteria are met.
"""

import os
import sys
import math
import argparse
from datetime import date, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOptionContractsRequest
from alpaca.trading.enums import ContractType, AssetStatus

# Configure project path imports
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASE_DIR)

import src.config as config

def get_minimum_short_strike(long_strike: float, debit_paid: float) -> float:
    """
    Calculates the absolute minimum strike to prevent a PMCC breakeven trap.
    Guarantees that assignment on the short call does not result in a net loss.
    """
    breakeven = long_strike + debit_paid
    # Round up to the nearest whole number to ensure a net credit upon assignment
    return float(math.ceil(breakeven))

def is_technically_overextended(symbol: str) -> bool:
    """
    Evaluates intraday momentum indicators.
    Returns True when the stock is pushing into structural resistance (e.g., above VWAP, overbought RSI).
    """
    try:
        from src.options.alpaca_options import fetch_intraday_5min_candles
        from src.options.signals import calculate_intraday_signals
        
        df = fetch_intraday_5min_candles(symbol)
        if df is not None and not df.empty:
            signals = calculate_intraday_signals(df)
            if signals.get("valid"):
                # Define PMCC short call momentum criteria (e.g., overbought or bullish bias)
                rsi = signals.get("rsi_7", 50.0)
                bias = signals.get("intraday_bias", "NEUTRAL")
                return rsi > 65.0 or bias in ["BULLISH", "STRONG_BULLISH"]
    except Exception as e:
        print(f"[WARNING] Indicator calculation failed for {symbol}: {e}. Falling back to default trigger.")
    
    return True

def scan_and_alert_short_calls(symbol: str, long_strike: float, debit_paid: float, target_dte: int = 30):
    """
    Scans the Alpaca option chain and prints/logs alert payloads if conditions are met.
    """
    # 1. Gate check: Only proceed on overextended days
    if not is_technically_overextended(symbol):
        print(f"[{symbol}] Indicators cool. No alert triggered.")
        return

    # 2. Calculate the strike safeguard
    min_strike = get_minimum_short_strike(long_strike, debit_paid)
    print(f"[{symbol}] Momentum detected. Minimum safe short strike calculated at: ${min_strike:.2f}")

    # 3. Define the expiration window
    target_exp_start = date.today() + timedelta(days=target_dte)
    target_exp_end = target_exp_start + timedelta(days=15)  # 15-day search window

    # 4. Initialize Alpaca Trading Client using project config
    api_key = config.API_KEY
    secret_key = config.SECRET_KEY
    
    if not api_key or not secret_key or "YOUR_ALPACA" in api_key:
        print("[WARNING] Alpaca API credentials not configured. Using dry run simulated chain lookup.")
        # Fallback simulated response
        simulated_exp = target_exp_start.strftime("%Y-%m-%d")
        print(f"\n🔔 OPTIONS ALERT (SIMULATED): Volatility Harvesting Opportunity for {symbol}")
        print("="*65)
        alert_payload = {
            "symbol": f"{symbol}{target_exp_start.strftime('%y%m%d')}C{int(min_strike*1000):08d}",
            "strike": min_strike,
            "expiration": simulated_exp,
            "action": "SELL TO OPEN",
            "reason": "Technical resistance met, strike above PMCC breakeven."
        }
        print(f"-> {alert_payload}")
        return

    try:
        trade_client = TradingClient(api_key=api_key, secret_key=secret_key, paper=True)

        # 5. Query Alpaca for active call contracts meeting safety criteria
        req = GetOptionContractsRequest(
            underlying_symbols=[symbol],
            status=AssetStatus.ACTIVE,
            type=ContractType.CALL,
            strike_price_gte=str(min_strike),  # Filters out loss-inducing strikes (must be string for alpaca-py)
            expiration_date_gte=target_exp_start,
            expiration_date_lte=target_exp_end
        )
        
        response = trade_client.get_option_contracts(req)
        contracts = response.option_contracts if response else []

        if contracts:
            print(f"\n🔔 OPTIONS ALERT: Volatility Harvesting Opportunity for {symbol}")
            print("="*65)
            
            # Sort by strike price to locate the nearest safe strikes
            contracts.sort(key=lambda x: x.strike_price)
            
            for contract in contracts[:3]:  # Alert on the top 3 nearest safe strikes
                alert_payload = {
                    "symbol": contract.symbol,
                    "strike": float(contract.strike_price),
                    "expiration": contract.expiration_date.strftime('%Y-%m-%d'),
                    "action": "SELL TO OPEN",
                    "reason": "Technical resistance met, strike above PMCC breakeven."
                }
                print(f"-> {alert_payload}")
        else:
            print(f"[{symbol}] No valid option contracts found meeting safety criteria (strike >= {min_strike}).")

    except Exception as err:
        print(f"[ERROR] Failed to query options chain from Alpaca: {err}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan short calls for PMCC configurations.")
    parser.add_argument("--symbol", type=str, default="RGTI", help="Underlying ticker symbol")
    parser.add_argument("--long-strike", type=float, default=8.00, help="Strike price of your long call option")
    parser.add_argument("--debit-paid", type=float, default=8.80, help="Total debit premium paid for the long call")
    parser.add_argument("--target-dte", type=int, default=30, help="Target Days to Expiry for the short call")
    
    args = parser.parse_args()
    scan_and_alert_short_calls(
        symbol=args.symbol.upper(),
        long_strike=args.long_strike,
        debit_paid=args.debit_paid,
        target_dte=args.target_dte
    )
