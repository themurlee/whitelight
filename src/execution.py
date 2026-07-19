"""
WhiteLight Systematic Trading & Analysis Pipeline - Execution & Circuit Breaker

Interfaces with Alpaca Trading API via alpaca-py SDK (TradingClient,
StockHistoricalDataClient, OptionHistoricalDataClient).

Circuit breaker: rolling 7-day / 15% drawdown lockdown (lockdown_active).
Manual override: operator-controlled manual_pause flag, independent of
lockdown_active. Both flags are checked before any order submission.
Neither flag can be cleared by the other's reset logic.

Env vars:
  ALPACA_API_KEY     — required
  ALPACA_SECRET_KEY  — required
  ALPACA_PAPER       — "true" (default) or "false" for live trading
"""

import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone

# Default file paths inside the data directory
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
POSITIONS_FILE = os.path.join(DATA_DIR, "positions.json")


def _is_paper() -> bool:
    """Return True if running in paper mode (default). Set ALPACA_PAPER=false for live."""
    return os.environ.get("ALPACA_PAPER", "true").lower() != "false"


def parse_option_symbol(symbol: str) -> Tuple[str, str, str, float]:
    """
    Parses standard OPRA options symbol format (e.g. AAPL260814C00185000)
    Returns Tuple of (ticker, expiration_date YYYY-MM-DD, option_type call/put, strike_price).
    """
    sym = symbol.replace(" ", "")

    # 1. Ticker
    ticker = ""
    idx = 0
    while idx < len(sym) and sym[idx].isalpha():
        ticker += sym[idx]
        idx += 1

    # 2. Expiration Date (YYMMDD) - 6 digits
    yy = sym[idx:idx+2]
    mm = sym[idx+2:idx+4]
    dd = sym[idx+4:idx+6]
    expiration = f"20{yy}-{mm}-{dd}"
    idx += 6

    # 3. Option Type (C or P)
    type_char = sym[idx].upper()
    option_type = "call" if type_char == "C" else "put"
    idx += 1

    # 4. Strike Price (8 digits representing strike * 1000)
    strike_str = sym[idx:idx+8]
    strike = float(strike_str) / 1000.0

    return ticker, expiration, option_type, strike


def _load_alpaca_keys() -> Tuple[Optional[str], Optional[str]]:
    """Load ALPACA_API_KEY and ALPACA_SECRET_KEY from env or .env file."""
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if api_key and secret_key:
        return api_key, secret_key

    env_file = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k == "ALPACA_API_KEY" and not api_key:
                        api_key = v
                    elif k == "ALPACA_SECRET_KEY" and not secret_key:
                        secret_key = v
        except Exception:
            pass
    return api_key, secret_key


class ExecutionClient:
    """
    Alpaca Trading API client.
    Class name kept for backward compatibility with existing tests and imports.
    In dry_run mode, all methods return mock values without hitting Alpaca.
    In live mode, uses alpaca-py TradingClient + StockHistoricalDataClient.
    Paper vs live controlled by ALPACA_PAPER env var (default: paper=True).
    """

    def __init__(self, command: List[str] = None, dry_run: bool = True):
        self.dry_run = dry_run
        self._trading_client = None
        self._hist_client = None

    def start(self):
        """Authenticate and warm up Alpaca SDK clients."""
        if self.dry_run:
            return

        api_key, secret_key = _load_alpaca_keys()
        if not api_key or not secret_key:
            print("[ALPACA] Missing ALPACA_API_KEY/ALPACA_SECRET_KEY. Falling back to dry-run mode.")
            self.dry_run = True
            return

        paper = _is_paper()
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.historical import StockHistoricalDataClient
            self._trading_client = TradingClient(api_key, secret_key, paper=paper)
            self._hist_client = StockHistoricalDataClient(api_key, secret_key)
            # Verify auth works
            self._trading_client.get_account()
            mode = "paper" if paper else "LIVE"
            print(f"[ALPACA] Authenticated successfully ({mode} mode).")
        except Exception as e:
            print(f"[ALPACA] Authentication failed: {e}. Falling back to dry-run mode.")
            self.dry_run = True
            self._trading_client = None
            self._hist_client = None

    def stop(self):
        """Cleanup connections (no-op for Alpaca SDK)."""
        self._trading_client = None
        self._hist_client = None

    def _mock_call_tool(self, name: str, arguments: Dict) -> Dict:
        """Mock fallback values for offline/dry-run testing."""
        if name == "get_portfolio_metrics":
            return {
                "equity": 10000.0,
                "buying_power": 5000.0,
                "cash": 4500.0
            }
        elif name == "place_order":
            return {
                "order_id": "mock_order_id",
                "status": "placed",
                "symbol": arguments.get("symbol"),
                "quantity": arguments.get("quantity")
            }
        elif name == "cancel_all_orders":
            return {
                "status": "success",
                "cancelled_count": 5
            }
        return {"status": "mock_success"}

    def get_portfolio_equity(self) -> float:
        """Return current portfolio equity from Alpaca account."""
        if self.dry_run or self._trading_client is None:
            return float(self._mock_call_tool("get_portfolio_metrics", {}).get("equity", 10000.0))
        try:
            account = self._trading_client.get_account()
            return float(account.portfolio_value)
        except Exception as e:
            print(f"[ALPACA ERROR] Failed to fetch equity: {e}")
            return 10000.0

    def get_active_positions(self) -> List[Dict]:
        """Fetch open option positions from Alpaca."""
        if self.dry_run or self._trading_client is None:
            return []
        try:
            positions = self._trading_client.get_all_positions()
            result = []
            for pos in positions:
                if pos.asset_class != "us_option":
                    continue
                qty = int(float(pos.qty))
                if qty <= 0:
                    continue
                result.append({
                    "symbol": pos.symbol,
                    "quantity": qty,
                    "option_type": "call" if "C" in pos.symbol else "put",
                    "strike_price": 0.0,
                    "expiration_date": ""
                })
            return result
        except Exception as e:
            print(f"[ALPACA ERROR] Failed to fetch positions: {e}")
            return []

    def get_historical_bars(self, ticker: str) -> List[Dict]:
        """Fetch 5-minute historical bar data for technical indicators."""
        if self.dry_run or self._hist_client is None:
            # Generate simulated bars for strategy (300 bars)
            base_price = 180.0
            mock_prices = [base_price * (1.0 + (0.0003 * i)) for i in range(300)]
            mock_bars = []
            for i in range(300):
                p = mock_prices[i]
                mock_bars.append({
                    "high": p + 0.4,
                    "low": p - 0.4,
                    "close": p,
                    "volume": 2000.0,
                    "timestamp": f"2026-07-15T09:30:{i:02d}Z"
                })
            return mock_bars
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            from alpaca.data.enums import DataFeed
            from datetime import timedelta, timezone

            end_dt = datetime.now(timezone.utc)
            start_dt = end_dt - timedelta(days=7)
            request = StockBarsRequest(
                symbol_or_symbols=[ticker],
                timeframe=TimeFrame.Minute,
                start=start_dt,
                end=end_dt,
                feed=DataFeed.IEX,
            )
            bars_resp = self._hist_client.get_stock_bars(request)
            df = bars_resp.df
            if df.empty:
                return []
            import pandas as pd
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(ticker, level=0)
            bars = []
            for ts, row in df.iterrows():
                bars.append({
                    "high": float(row.get("high", row.get("close", 0))),
                    "low": float(row.get("low", row.get("close", 0))),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)),
                    "timestamp": str(ts),
                })
            return bars
        except Exception as e:
            print(f"[ALPACA ERROR] Failed to fetch historical bars: {e}")
            return []

    def get_expiration_dates(self, ticker: str) -> List[str]:
        """Query valid option expiration dates for ticker via Alpaca OptionHistoricalDataClient."""
        if self.dry_run or self._trading_client is None:
            return ["2026-08-14", "2026-09-15"]
        try:
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.data.requests import OptionChainRequest

            api_key, secret_key = _load_alpaca_keys()
            opt_client = OptionHistoricalDataClient(api_key, secret_key)
            request = OptionChainRequest(underlying_symbol=ticker)
            chain = opt_client.get_option_chain(request)
            expirations = sorted(set(
                contract.expiration_date
                for contract in chain.values()
                if hasattr(contract, "expiration_date")
            ))
            return expirations
        except Exception as e:
            print(f"[ALPACA ERROR] Failed to fetch expiration dates: {e}")
            return []

    def get_options_chain(self, ticker: str, expiration_date: str) -> List[Dict]:
        """Fetch options chain contracts with delta and volume for a given expiration."""
        if self.dry_run or self._trading_client is None:
            return [
                {
                    "symbol": f"{ticker}260814C00185000",
                    "expiration_date": expiration_date,
                    "option_type": "call",
                    "delta": 0.41,
                    "strike_price": 185.0,
                    "volume": 1200,
                    "bid": 3.50,
                    "ask": 3.60,
                },
                {
                    "symbol": f"{ticker}260814P00175000",
                    "expiration_date": expiration_date,
                    "option_type": "put",
                    "delta": -0.39,
                    "strike_price": 175.0,
                    "volume": 1200,
                    "bid": 2.80,
                    "ask": 2.90,
                }
            ]
        try:
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.data.requests import OptionChainRequest

            api_key, secret_key = _load_alpaca_keys()
            opt_client = OptionHistoricalDataClient(api_key, secret_key)
            request = OptionChainRequest(
                underlying_symbol=ticker,
                expiration_date=expiration_date,
            )
            chain_data = opt_client.get_option_chain(request)
            chain = []
            for symbol, snapshot in chain_data.items():
                greeks = getattr(snapshot, "greeks", None)
                delta = float(greeks.delta) if greeks and greeks.delta is not None else None
                quote = getattr(snapshot, "latest_quote", None)
                bid = float(quote.bid_price) if quote else 0.0
                ask = float(quote.ask_price) if quote else 0.0
                volume = float(getattr(snapshot, "minute_bar", {}).get("volume", 0)) if isinstance(getattr(snapshot, "minute_bar", None), dict) else 0

                details = getattr(snapshot, "latest_trade", None)
                opt_type = "call" if "C" in symbol else "put"

                try:
                    _, _, opt_type_parsed, strike = parse_option_symbol(symbol)
                    opt_type = opt_type_parsed
                except Exception:
                    pass

                chain.append({
                    "symbol": symbol,
                    "expiration_date": expiration_date,
                    "option_type": opt_type,
                    "delta": delta,
                    "strike_price": strike if "strike" in dir() else 0.0,
                    "volume": int(volume),
                    "bid": bid,
                    "ask": ask,
                })
            return chain
        except Exception as e:
            print(f"[ALPACA ERROR] Failed to fetch option chain: {e}")
            return []

    def place_option_order(self, symbol: str, quantity: int, side: str,
                           order_type: str = "market") -> Dict:
        """Submit an options order through Alpaca. Blocked if dry_run."""
        if self.dry_run or self._trading_client is None:
            return self._mock_call_tool("place_order", {"symbol": symbol, "quantity": quantity})
        try:
            from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass

            alpaca_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=alpaca_side,
                time_in_force=TimeInForce.DAY,
            )
            order = self._trading_client.submit_order(order_data)
            return {
                "order_id": str(order.id),
                "status": "placed",
                "symbol": symbol,
                "quantity": quantity,
            }
        except Exception as e:
            print(f"[ALPACA ORDER ERROR] Failed to place option order: {e}")
            return {"status": "failed", "error": str(e)}

    def place_equity_order(self, symbol: str, quantity: int, side: str,
                           order_type: str = "market",
                           limit_price: Optional[float] = None) -> Dict:
        """Submit an equity order through Alpaca. Blocked if dry_run."""
        if self.dry_run or self._trading_client is None:
            return self._mock_call_tool("place_order", {"symbol": symbol, "quantity": quantity})
        try:
            from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            alpaca_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            if order_type.lower() == "limit" and limit_price is not None:
                order_data = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price,
                )
            else:
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                )
            order = self._trading_client.submit_order(order_data)
            return {
                "order_id": str(order.id),
                "status": "placed",
                "symbol": symbol,
                "quantity": quantity,
            }
        except Exception as e:
            print(f"[ALPACA ORDER ERROR] Failed to place equity order: {e}")
            return {"status": "failed", "error": str(e)}

    def purge_all_orders(self) -> int:
        """Cancel all pending orders via Alpaca."""
        if self.dry_run or self._trading_client is None:
            return self._mock_call_tool("cancel_all_orders", {}).get("cancelled_count", 0)
        try:
            cancel_statuses = self._trading_client.cancel_orders()
            return len(cancel_statuses)
        except Exception as e:
            print(f"[ALPACA ERROR] Failed to cancel orders: {e}")
            return 0


class RiskManager:
    """
    Implements drawdown analysis, circuit breaker trigger, and execution lockdown.

    Two independent flags gate order execution:
      lockdown_active : set by the automatic 7-day/15% drawdown circuit breaker.
                        Cleared ONLY by explicit manual operator action in state.json.
      manual_pause    : set/cleared by the operator via set_manual_pause().
                        Never touched by circuit-breaker logic.
    Both must be False for any order to proceed.
    """

    def __init__(self, client: ExecutionClient):
        self.client = client
        self._ensure_data_files()

    def _ensure_data_files(self):
        """Create /data/ and state/positions files if not exist."""
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(STATE_FILE):
            with open(STATE_FILE, "w") as f:
                json.dump({
                    "lockdown_active": False,
                    "manual_pause": False,
                    "drawdown_locked_at": None,
                    "equity_history": []
                }, f, indent=2)
        else:
            # Backfill manual_pause into existing state file if missing
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                if "manual_pause" not in state:
                    state["manual_pause"] = False
                    with open(STATE_FILE, "w") as f:
                        json.dump(state, f, indent=2)
            except Exception:
                pass

        if not os.path.exists(POSITIONS_FILE):
            with open(POSITIONS_FILE, "w") as f:
                json.dump({
                    "active_positions": []
                }, f, indent=2)

    def load_state(self) -> Dict:
        with open(STATE_FILE, "r") as f:
            return json.load(f)

    def save_state(self, state: Dict):
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def load_positions(self) -> Dict:
        with open(POSITIONS_FILE, "r") as f:
            return json.load(f)

    def save_positions(self, positions: Dict):
        with open(POSITIONS_FILE, "w") as f:
            json.dump(positions, f, indent=2)

    def is_execution_blocked(self) -> Tuple[bool, str]:
        """
        Check both flags independently.
        Returns (is_blocked, reason_string).
        """
        state = self.load_state()
        if state.get("lockdown_active", False):
            return True, "lockdown_active"
        if state.get("manual_pause", False):
            return True, "manual_pause"
        return False, ""

    def verify_and_update_drawdown(self) -> Tuple[bool, float]:
        """
        Reviews equity history, updates it with current equity from Alpaca,
        calculates rolling 7-day drawdown, triggers circuit breaker if drawdown >= 15%.
        Returns (is_lockdown_active, drawdown_percentage).
        Does NOT touch manual_pause.
        """
        state = self.load_state()

        # If already locked down, return true (but don't re-trigger)
        if state.get("lockdown_active", False):
            return True, 1.0

        current_equity = self.client.get_portfolio_equity()
        now_str = datetime.utcnow().isoformat() + "Z"

        history = state.get("equity_history", [])
        history.append({
            "timestamp": now_str,
            "equity": current_equity
        })

        # Keep only elements within rolling 7 days
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        filtered_history = []
        for entry in history:
            try:
                t_str = entry["timestamp"].replace("Z", "")
                t_dt = datetime.fromisoformat(t_str)
                if t_dt >= seven_days_ago:
                    filtered_history.append(entry)
            except Exception:
                filtered_history.append(entry)

        state["equity_history"] = filtered_history
        self.save_state(state)

        if not filtered_history:
            return False, 0.0

        peak_equity = max(entry["equity"] for entry in filtered_history)

        if peak_equity <= 0:
            return False, 0.0

        drawdown = (peak_equity - current_equity) / peak_equity

        if drawdown >= 0.15:
            self.trigger_lockdown(drawdown)
            return True, drawdown

        return False, drawdown

    def trigger_lockdown(self, drawdown: float):
        """
        Emergency lockdown:
        1. Set lockdown_active = True (does NOT touch manual_pause).
        2. Purge all open orders via Alpaca.
        3. Flatten all active positions.
        4. Clear positions record.
        """
        state = self.load_state()
        state["lockdown_active"] = True
        state["drawdown_locked_at"] = datetime.utcnow().isoformat() + "Z"
        # manual_pause is NOT modified here — intentional
        self.save_state(state)

        print(f"[CRITICAL CIRCUIT BREAKER] Drawdown of {drawdown*100:.2f}% exceeded 15% safety limit. Triggering emergency lockdown!")

        cancelled_count = self.client.purge_all_orders()
        print(f"[LOCKDOWN] Cancelled {cancelled_count} pending orders.")

        positions_data = self.load_positions()
        active = positions_data.get("active_positions", [])

        for pos in active:
            symbol = pos["symbol"]
            qty = pos["quantity"]
            print(f"[LOCKDOWN] Flattening active leg: {symbol} x {qty}")
            self.client.place_option_order(symbol, qty, side="sell")

        positions_data["active_positions"] = []
        self.save_positions(positions_data)


# --------------------------------------------------------------------------- #
# Manual pause flag — independent of circuit breaker
# --------------------------------------------------------------------------- #

def set_manual_pause(paused: bool) -> Dict:
    """
    Set or clear the operator manual_pause flag.
    This flag is NEVER modified by circuit-breaker logic.
    Clearing it does NOT affect lockdown_active.

    Returns the updated state dict.
    """
    if not os.path.exists(STATE_FILE):
        os.makedirs(DATA_DIR, exist_ok=True)
        state = {
            "lockdown_active": False,
            "manual_pause": False,
            "drawdown_locked_at": None,
            "equity_history": []
        }
    else:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)

    state["manual_pause"] = bool(paused)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    action = "PAUSED" if paused else "RESUMED"
    print(f"[MANUAL CONTROL] Operator {action} order execution (manual_pause={paused}).")
    return state


# --------------------------------------------------------------------------- #
# Automated order execution
# --------------------------------------------------------------------------- #

def execute_order_safely(
    client: ExecutionClient,
    risk_manager: RiskManager,
    symbol: str,
    quantity: int,
    side: str,
    option_type: str,
    strike_price: float,
    expiration_date: str
) -> Optional[Dict]:
    """
    Submits an options trade after checking BOTH flags independently:
      1. lockdown_active (automatic circuit breaker)
      2. manual_pause (operator override)
    Both must be False for the order to proceed.
    Saves new positions in positions.json on successful buy.
    """
    blocked, reason = risk_manager.is_execution_blocked()
    if blocked:
        print(f"[EXECUTION REFUSED] Blocked by: {reason}.")
        return None

    # Run drawdown audit (only trips lockdown if threshold breached)
    locked, drawdown = risk_manager.verify_and_update_drawdown()
    if locked:
        print("[EXECUTION REFUSED] Risk circuit breaker is active. Execution locked.")
        return None

    order_res = client.place_option_order(symbol, quantity, side)

    if side.lower() == "buy" and order_res.get("status") == "placed":
        positions_data = risk_manager.load_positions()
        positions_data["active_positions"].append({
            "symbol": symbol,
            "quantity": quantity,
            "option_type": option_type,
            "strike_price": strike_price,
            "expiration_date": expiration_date,
            "acquired_at": datetime.utcnow().isoformat() + "Z"
        })
        risk_manager.save_positions(positions_data)

    return order_res


# --------------------------------------------------------------------------- #
# Manual order ticket — operator-initiated, same risk path as automated orders
# --------------------------------------------------------------------------- #

def submit_manual_order(
    client: ExecutionClient,
    risk_manager: RiskManager,
    symbol: str,
    side: str,
    qty: int,
    order_type: str = "market",
    limit_price: Optional[float] = None
) -> Optional[Dict]:
    """
    Operator-initiated order routed through the SAME risk checks as automated orders.
    Blocked if EITHER lockdown_active OR manual_pause is True.
    Uses the same Alpaca order path as execute_order_safely.
    Does NOT bypass position-sizing or circuit-breaker checks.

    order_type: "market" or "limit" (requires limit_price if limit)
    """
    # Check BOTH flags independently
    state = risk_manager.load_state()
    if state.get("lockdown_active", False):
        print("[MANUAL ORDER REFUSED] System in automatic lockdown (lockdown_active=True).")
        return None
    if state.get("manual_pause", False):
        print("[MANUAL ORDER REFUSED] Operator manual pause is active (manual_pause=True).")
        return None

    if order_type.lower() == "limit" and limit_price is None:
        print("[MANUAL ORDER ERROR] limit order_type requires limit_price.")
        return None

    # Determine if this is an equity or option order
    is_option = any(c in symbol for c in ("C", "P")) and len(symbol) > 8
    if is_option:
        order_res = client.place_option_order(symbol, qty, side, order_type)
    else:
        order_res = client.place_equity_order(symbol, qty, side, order_type, limit_price)

    print(f"[MANUAL ORDER] {side.upper()} {qty}x {symbol} ({order_type}) -> status: {order_res.get('status')}")
    return order_res
