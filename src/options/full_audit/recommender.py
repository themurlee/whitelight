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
        now = datetime.now()
        today = datetime(now.year, now.month, now.day)

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
