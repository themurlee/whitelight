from dataclasses import dataclass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
import src.config as config
from src.alpaca_client.retry_decorator import alpaca_retryable

@dataclass
class SlippageConfig:
    max_slippage_pct: float = 0.2  # 0.2%
    max_spread_pct: float = 0.1    # 0.1%
    use_limit_orders: bool = True
    limit_order_offset_bps: int = 5  # 5 basis points

_client = None

@alpaca_retryable(max_retries=5, base_delay=1.0)
def get_current_bid_ask(ticker: str) -> tuple[float, float]:
    """Fetch latest bid and ask price from Alpaca."""
    global _client
    if _client is None:
        _client = StockHistoricalDataClient(config.API_KEY, config.SECRET_KEY)
    req = StockLatestQuoteRequest(symbol_or_symbols=[ticker])
    res = _client.get_stock_latest_quote(req)
    quote = res[ticker]
    bid = float(quote.bid_price)
    ask = float(quote.ask_price)
    if bid <= 0 or ask <= 0:
        raise ValueError(f"Invalid bid/ask received for {ticker}: bid={bid}, ask={ask}")
    return bid, ask

def validate_slippage(ticker: str, signal_close: float, side: str, bid: float, ask: float, slippage_config: SlippageConfig) -> float:
    """Validate quote spread and slippage against config limits. Returns worst-case fill price."""
    mid = (bid + ask) / 2.0
    spread_pct = ((ask - bid) / mid) * 100.0
    if spread_pct > slippage_config.max_spread_pct:
        raise ValueError(f"Spread gating rejected {ticker}: spread is {spread_pct:.4f}%, max allowed is {slippage_config.max_spread_pct}%")
        
    if side.upper() == "BUY":
        worst_case = ask
        slippage_pct = ((worst_case - signal_close) / signal_close) * 100.0
    elif side.upper() == "SELL":
        worst_case = bid
        slippage_pct = ((signal_close - worst_case) / signal_close) * 100.0
    else:
        raise ValueError(f"Invalid side: {side}")
        
    if slippage_pct > slippage_config.max_slippage_pct:
        raise ValueError(f"Slippage gating rejected {ticker}: slippage is {slippage_pct:.4f}%, max allowed is {slippage_config.max_slippage_pct}%")
        
    return worst_case
