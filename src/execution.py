"""
WhiteLight Systematic Trading & Analysis Pipeline - Execution & Circuit Breaker
Interfaces directly with Robinhood API using the pure Python 'robin_stocks' package.
Enforces 7-day rolling drawdown risk circuit breaker and manual controls.
"""

import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

# Default file paths inside the data directory
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
POSITIONS_FILE = os.path.join(DATA_DIR, "positions.json")


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


class RobinhoodMCPClient:
    """
    Robinhood API Client using the python-native 'robin_stocks' package.
    Keeps class name for project compatibility; falls back to mock logic if dry_run=True.
    """

    def __init__(self, command: List[str] = None, dry_run: bool = True):
        self.dry_run = dry_run
        self.logged_in = False
        self.request_id = 1

    def start(self):
        """Authenticates session to Robinhood API using credentials in environment or .env."""
        if self.dry_run:
            return

        username = os.environ.get("ROBINHOOD_USERNAME")
        password = os.environ.get("ROBINHOOD_PASSWORD")
        mfa_secret = os.environ.get("ROBINHOOD_MFA_SECRET")

        # Load from .env manually if not in system environment
        env_file = os.path.join(BASE_DIR, ".env")
        if (not username or not password) and os.path.exists(env_file):
            try:
                with open(env_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k == "ROBINHOOD_USERNAME":
                            username = v
                        elif k == "ROBINHOOD_PASSWORD":
                            password = v
                        elif k == "ROBINHOOD_MFA_SECRET":
                            mfa_secret = v
            except Exception as e:
                print(f"[ROBINHOOD] Error loading .env configuration: {e}")

        if not username or not password:
            print("[ROBINHOOD] Missing ROBINHOOD_USERNAME/PASSWORD. Falling back to dry-run mode.")
            self.dry_run = True
            return

        try:
            import robin_stocks.robinhood as r
            if mfa_secret:
                import pyotp
                totp = pyotp.TOTP(mfa_secret).now()
                r.login(username=username, password=password, mfa_code=totp, store_session=True)
            else:
                r.login(username=username, password=password, store_session=True)
            
            # Verify login was successful by loading basic profile metrics
            r.profiles.load_portfolio_profile()
            self.logged_in = True
            print("[ROBINHOOD] Logged in successfully to Robinhood API.")
        except Exception as e:
            print(f"[ROBINHOOD] Authentication failed/errored: {e}. Falling back to dry-run mode.")
            self.dry_run = True

    def stop(self):
        """Logs out from Robinhood API session."""
        if self.logged_in and not self.dry_run:
            try:
                import robin_stocks.robinhood as r
                r.logout()
                self.logged_in = False
                print("[ROBINHOOD] Logged out successfully.")
            except Exception:
                pass

    def _mock_call_tool(self, name: str, arguments: Dict) -> Dict:
        """Mock fallback values for offline testing."""
        if name == "get_portfolio_metrics":
            return {
                "equity": 10000.0,
                "buying_power": 5000.0,
                "cash": 4500.0
            }
        elif name == "place_order":
            return {
                "order_id": "mock_order_12345",
                "status": "placed",
                "symbol": arguments.get("symbol"),
                "quantity": arguments.get("quantity")
            }
        elif name == "cancel_all_orders":
            return {
                "status": "success",
                "cancelled_count": 3
            }
        return {"status": "mock_success"}

    def get_portfolio_equity(self) -> float:
        """Query actual portfolio valuation equity."""
        if self.dry_run:
            return float(self._mock_call_tool("get_portfolio_metrics", {}).get("equity", 10000.0))
        try:
            import robin_stocks.robinhood as r
            profile = r.profiles.load_portfolio_profile()
            eq = profile.get("equity")
            if eq is not None:
                return float(eq)
            return float(profile.get("portfolio_value", 10000.0))
        except Exception as e:
            print(f"[ROBINHOOD ERROR] Failed to fetch equity: {e}")
            return 10000.0

    def get_active_positions(self) -> List[Dict]:
        """Fetch live open option positions from Robinhood."""
        if self.dry_run:
            return []
        try:
            import robin_stocks.robinhood as r
            open_opts = r.options.get_open_option_positions()
            positions = []
            for pos in open_opts:
                qty = int(float(pos.get("quantity", 0)))
                if qty <= 0:
                    continue
                # Retrieve symbol details
                chain_sym = pos.get("chain_symbol", "")
                positions.append({
                    "symbol": chain_sym,
                    "quantity": qty,
                    "option_type": pos.get("type", "call"),
                    "strike_price": float(pos.get("strike_price", 0.0)),
                    "expiration_date": pos.get("expiration_date", "")
                })
            return positions
        except Exception as e:
            print(f"[ROBINHOOD ERROR] Failed to fetch positions: {e}")
            return []

    def get_historical_bars(self, ticker: str) -> List[Dict]:
        """Fetch 5-minute historical bar data for technical indicators."""
        if self.dry_run:
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
            import robin_stocks.robinhood as r
            # Use 5-minute bars over the last week (plenty of bars for EMA 250, and allows session boundaries)
            historicals = r.stocks.get_stock_historicals(ticker, interval='5minute', span='week')
            bars = []
            for bar in historicals:
                bars.append({
                    "high": float(bar.get("high_price") or 0.0),
                    "low": float(bar.get("low_price") or 0.0),
                    "close": float(bar.get("close_price") or 0.0),
                    "volume": float(bar.get("volume") or 0.0),
                    "timestamp": bar.get("begins_at", "")
                })
            return bars
        except Exception as e:
            print(f"[ROBINHOOD ERROR] Failed to fetch historical bars: {e}")
            return []

    def get_expiration_dates(self, ticker: str) -> List[str]:
        """Query valid option expiration dates for ticker."""
        if self.dry_run:
            return ["2026-08-14", "2026-09-15"]
        try:
            import robin_stocks.robinhood as r
            chain_info = r.options.get_chains(ticker)
            return chain_info.get("expiration_dates", [])
        except Exception as e:
            print(f"[ROBINHOOD ERROR] Failed to fetch expiration dates: {e}")
            return []

    def get_options_chain(self, ticker: str, expiration_date: str) -> List[Dict]:
        """Fetch options chain contracts for expiration date with delta and volume."""
        if self.dry_run:
            return [
                {
                    "symbol": f"{ticker}260814C00185000",
                    "expiration_date": expiration_date,
                    "option_type": "call",
                    "delta": 0.41,
                    "strike_price": 185.0,
                    "volume": 1200
                },
                {
                    "symbol": f"{ticker}260814P00175000",
                    "expiration_date": expiration_date,
                    "option_type": "put",
                    "delta": -0.39,
                    "strike_price": 175.0,
                    "volume": 1200
                }
            ]
        try:
            import robin_stocks.robinhood as r
            contracts = r.options.find_tradable_options(symbol=ticker, expirationDate=expiration_date)
            option_ids = [c["id"] for c in contracts if "id" in c]
            
            # Fetch option Greeks/market data in batch
            md_list = r.options.get_option_market_data_by_id(option_ids)
            md_map = {m["instrument"]: m for m in md_list if m and "instrument" in m}
            
            chain = []
            for contract in contracts:
                inst_url = contract.get("url")
                md = md_map.get(inst_url)
                if not md:
                    continue
                    
                delta_val = md.get("delta")
                vol_val = md.get("volume")
                
                chain.append({
                    "symbol": contract.get("symbol", ""),
                    "expiration_date": expiration_date,
                    "option_type": contract.get("type", "call"),
                    "delta": float(delta_val) if delta_val is not None else None,
                    "strike_price": float(contract.get("strike_price", 0.0)),
                    "volume": int(vol_val) if vol_val is not None else 0
                })
            return chain
        except Exception as e:
            print(f"[ROBINHOOD ERROR] Failed to fetch option chain: {e}")
            return []

    def place_option_order(self, symbol: str, quantity: int, side: str, order_type: str = "market") -> Dict:
        """Submit options order."""
        if self.dry_run:
            return self._mock_call_tool("place_order", {"symbol": symbol, "quantity": quantity})
        try:
            import robin_stocks.robinhood as r
            ticker, expiration, option_type, strike = parse_option_symbol(symbol)
            
            if side.lower() == "buy":
                res = r.orders.order_buy_option_market(
                    positionEffect="open",
                    symbol=ticker,
                    quantity=quantity,
                    expirationDate=expiration,
                    strike=strike,
                    optionType=option_type
                )
            else:
                res = r.orders.order_sell_option_market(
                    positionEffect="close",
                    symbol=ticker,
                    quantity=quantity,
                    expirationDate=expiration,
                    strike=strike,
                    optionType=option_type
                )
            
            if isinstance(res, dict) and "id" in res:
                return {
                    "order_id": res.get("id"),
                    "status": "placed",
                    "symbol": symbol,
                    "quantity": quantity
                }
            else:
                print(f"[ROBINHOOD ORDER WARNING] Order failed or returned empty: {res}")
                return {"status": "failed", "details": str(res)}
        except Exception as e:
            print(f"[ROBINHOOD ORDER ERROR] Failed to place order: {e}")
            return {"status": "failed", "error": str(e)}

    def purge_all_orders(self) -> int:
        """Cancel all pending option orders."""
        if self.dry_run:
            return self._mock_call_tool("cancel_all_orders", {}).get("cancelled_count", 0)
        try:
            import robin_stocks.robinhood as r
            res = r.orders.cancel_all_option_orders()
            return len(res) if isinstance(res, list) else 1
        except Exception as e:
            print(f"[ROBINHOOD ERROR] Failed to cancel option orders: {e}")
            return 0


class RiskManager:
    """
    Implements drawdown analysis, circuit breaker trigger, and execution lockdown.
    """

    def __init__(self, client: RobinhoodMCPClient):
        self.client = client
        self._ensure_data_files()

    def _ensure_data_files(self):
        """Create /data/ and state/positions files if not exist."""
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(STATE_FILE):
            with open(STATE_FILE, "w") as f:
                json.dump({
                    "lockdown_active": False,
                    "drawdown_locked_at": None,
                    "equity_history": []
                }, f, indent=2)

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

    def verify_and_update_drawdown(self) -> Tuple[bool, float]:
        """
        Reviews equity history, updates it with current equity from Robinhood,
        calculates rolling 7-day drawdown, triggers circuit breaker if drawdown > 15%.
        Returns (is_lockdown_active, drawdown_percentage).
        """
        state = self.load_state()
        
        # If already locked down, return true
        if state.get("lockdown_active", False):
            return True, 1.0

        current_equity = self.client.get_portfolio_equity()
        now_str = datetime.utcnow().isoformat() + "Z"

        # Update equity history
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
                # Remove timezone 'Z' to parse
                t_str = entry["timestamp"].replace("Z", "")
                t_dt = datetime.fromisoformat(t_str)
                if t_dt >= seven_days_ago:
                    filtered_history.append(entry)
            except Exception:
                # Keep if corrupt parser but default to saving
                filtered_history.append(entry)

        state["equity_history"] = filtered_history
        self.save_state(state)

        # Compute rolling peak
        if not filtered_history:
            return False, 0.0

        peak_equity = max(entry["equity"] for entry in filtered_history)
        
        if peak_equity <= 0:
            return False, 0.0

        drawdown = (peak_equity - current_equity) / peak_equity

        if drawdown >= 0.15:
            # TRIGGER CIRCUIT BREAKER LOCKDOWN
            self.trigger_lockdown(drawdown)
            return True, drawdown

        return False, drawdown

    def trigger_lockdown(self, drawdown: float):
        """
        Performs emergency flattening:
        1. Lock execution.
        2. Purge all open orders via MCP.
        3. Flatten (sell) all active option legs/positions.
        4. Log event and save state.
        """
        state = self.load_state()
        state["lockdown_active"] = True
        state["drawdown_locked_at"] = datetime.utcnow().isoformat() + "Z"
        self.save_state(state)

        print(f"[CRITICAL CIRCUIT BREAKER] Drawdown of {drawdown*100:.2f}% exceeded 15% safety limit. Triggering emergency lockdown!")

        # 1. Purge open orders
        cancelled_count = self.client.purge_all_orders()
        print(f"[LOCKDOWN] Cancelled {cancelled_count} pending orders.")

        # 2. Flatten positions
        positions_data = self.load_positions()
        active = positions_data.get("active_positions", [])
        
        for pos in active:
            symbol = pos["symbol"]
            qty = pos["quantity"]
            
            # Opposing order to sell/flatten
            print(f"[LOCKDOWN] Flattening active leg: {symbol} x {qty}")
            self.client.place_option_order(symbol, qty, side="sell")

        # Clear positions record
        positions_data["active_positions"] = []
        self.save_positions(positions_data)


def execute_order_safely(
    client: RobinhoodMCPClient,
    risk_manager: RiskManager,
    symbol: str,
    quantity: int,
    side: str,
    option_type: str,
    strike_price: float,
    expiration_date: str
) -> Optional[Dict]:
    """
    Submits a trade after verifying the risk circuit breaker is not tripped.
    Saves new long/short positions in positions.json state.
    """
    # 1. Check circuit breaker first
    locked, drawdown = risk_manager.verify_and_update_drawdown()
    if locked:
        print("[EXECUTION REFUSED] Risk circuit breaker is active. Execution locked.")
        return None

    # 2. Place order
    order_res = client.place_option_order(symbol, quantity, side)
    
    # 3. Update positions log if buy order succeeds
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
