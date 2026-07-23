import logging
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
import src.config as config
from src.alpaca_client.retry_decorator import alpaca_retryable

logger = logging.getLogger("PositionSizer")

@alpaca_retryable(max_retries=3, base_delay=1.0)
def get_vix_quote() -> float:
    """Fetch the latest VIX index value from Alpaca."""
    if not config.API_KEY or not config.SECRET_KEY:
        return 20.0
    try:
        client = StockHistoricalDataClient(config.API_KEY, config.SECRET_KEY)
        req = StockLatestQuoteRequest(symbol_or_symbols=["VIX"])
        res = client.get_stock_latest_quote(req)
        if "VIX" in res:
            return float(res["VIX"].ask_price or res["VIX"].bid_price or 20.0)
    except Exception as e:
        logger.warning(f"Failed to fetch live VIX index from Alpaca: {e}. Defaulting to 20.0")
    return 20.0

def get_vix_adjusted_quantity(qty: int, vix: float = None) -> int:
    """Adjust execution share quantity dynamically based on market volatility (VIX)."""
    if qty <= 0:
        return 0
    if vix is None:
        vix = get_vix_quote()
        
    # Scale linearly from 100% at VIX <= 20 to 50% at VIX >= 40
    scale = 1.0
    if vix > 20.0:
        scale = max(0.5, 1.0 - (vix - 20.0) * 0.025)
        
    adjusted_qty = int(qty * scale)
    return max(1, adjusted_qty)
