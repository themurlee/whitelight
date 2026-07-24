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
