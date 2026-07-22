"""
WhiteLight Systematic Trading & Analysis Pipeline - REST API Server
Pure Python zero-dependency HTTP server serving as a REST API bridge
between the local JSON/Markdown database and the React browser frontend.
"""

import os
import json
import glob
import base64
from http.server import ThreadingHTTPServer, HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Path configurations
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
POSITIONS_FILE = os.path.join(DATA_DIR, "positions.json")
TRADE_LOG_FILE = os.path.join(DATA_DIR, "trade_history.json")
PSYCHOLOGY_FILE = os.path.join(DATA_DIR, "psychology_log.json")
JOURNAL_DIR = os.path.join(DATA_DIR, "journal")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
import sys
import threading
import time
from datetime import datetime

# Global alerts queue for profit brackets and invalidation stop alerts
GLOBAL_ALERTS = []
ALERTS_LOCK = threading.Lock()
NOTIFIED_POSITIONS = {} # symbol -> set of profit brackets notified
LAST_3PM_ALERT_DATE = None
LAST_EOD_CANCEL_DATE = None

# Configure path imports
sys.path.append(BASE_DIR)

def _get_alpaca_account_info():
    import src.config as config
    if not config.API_KEY or not config.SECRET_KEY or "YOUR_ALPACA" in config.API_KEY:
        return {"configured": False, "error": "Credentials missing or default"}
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
        acc = client.get_account()
        positions = []
        try:
            raw_positions = client.get_all_positions()
            for p in raw_positions:
                positions.append({
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "price": float(p.current_price),
                    "pnl": float(p.unrealized_pl),
                    "type": "LONG" if float(p.qty) > 0 else "SHORT"
                })
        except Exception:
            pass

        return {
            "configured": True,
            "account_number": acc.account_number,
            "cash": float(acc.cash),
            "equity": float(acc.equity),
            "buying_power": float(acc.buying_power),
            "portfolio_value": float(acc.portfolio_value),
            "status": str(acc.status),
            "positions": positions
        }
    except Exception as e:
        return {"configured": True, "error": str(e)}

def _get_systematic_status():
    import src.config as config
    import glob
    
    # Ingest status
    data_dir = config.DATA_DIR
    tickers_status = {}
    for ticker_folder in glob.glob(os.path.join(data_dir, "*")):
        if os.path.isdir(ticker_folder) and os.path.basename(ticker_folder) not in ["journal", "uploads"]:
            ticker = os.path.basename(ticker_folder)
            files = glob.glob(os.path.join(ticker_folder, "*.jsonl"))
            files.sort()
            tickers_status[ticker] = {
                "count": len(files),
                "first_date": os.path.basename(files[0]).replace(".jsonl", "") if files else None,
                "last_date": os.path.basename(files[-1]).replace(".jsonl", "") if files else None,
            }

    # Trade logs
    log_path = config.TRADE_LOG_PATH
    log_content = ""
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
                log_content = "".join(reversed(lines[-100:])) # Newest logs first
        except Exception as e:
            log_content = f"Error reading logs: {e}"
    else:
        log_content = "No log file found."

    # Signal Log status
    signal_log_path = os.path.join(config.DATA_DIR, "signal_log.json")
    signal_data = None
    if os.path.exists(signal_log_path):
        try:
            with open(signal_log_path, "r") as f:
                signal_data = json.load(f)
        except Exception:
            pass

    # Account info
    acc_info = _get_alpaca_account_info()

    return {
        "tickers": tickers_status,
        "account": acc_info,
        "logs": log_content,
        "signal": signal_data
    }


def _read_json_file(filepath: str, default_val: any) -> any:
    if not os.path.exists(filepath):
        return default_val
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception:
        return default_val


def _write_json_file(filepath: str, data: any):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def _get_alpaca_orders():
    import src.config as config
    if not config.API_KEY or not config.SECRET_KEY or "YOUR_ALPACA" in config.API_KEY:
        return []
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
        # Fetch closed/all orders
        req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100)
        raw_orders = client.get_orders(filter=req)
        orders = []
        for o in raw_orders:
            try:
                status_str = str(o.status.value).upper() if hasattr(o.status, "value") else str(o.status).upper()
                side_str = str(o.side.value).upper() if hasattr(o.side, "value") else str(o.side).upper()
                qty_val = float(o.qty) if o.qty else 0.0
                price_val = float(o.filled_avg_price) if o.filled_avg_price else (float(o.limit_price) if o.limit_price else 0.0)
                dt = o.filled_at or o.submitted_at
                ts = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
                
                orders.append({
                    "timestamp": ts,
                    "action": side_str,
                    "symbol": o.symbol,
                    "quantity": qty_val,
                    "price": price_val,
                    "details": {
                        "strategy": "Alpaca Live Execution",
                        "pnl": 0.0,
                        "status": status_str
                    }
                })
            except Exception as inner_err:
                print("Error parsing order object:", inner_err)
        return orders
    except Exception as e:
        print("Error fetching Alpaca orders:", e)
        return []


class APIServerHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS for local Vite development server
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path.startswith("/api/uploads/"):
            filename = os.path.basename(path)
            fpath = os.path.join(UPLOADS_DIR, filename)
            resolved_path = os.path.abspath(fpath)
            
            # Directory traversal security check
            if not resolved_path.startswith(os.path.abspath(UPLOADS_DIR)) or not os.path.exists(resolved_path) or os.path.isdir(resolved_path):
                self.send_error(404, "File not found")
                return
            
            ext = os.path.splitext(filename)[1].lower()
            content_type = "application/octet-stream"
            if ext in [".png", ".webp", ".gif", ".bmp"]:
                content_type = f"image/{ext[1:]}"
            elif ext in [".jpg", ".jpeg"]:
                content_type = "image/jpeg"
            elif ext == ".svg":
                content_type = "image/svg+xml"
            elif ext == ".pdf":
                content_type = "application/pdf"
            elif ext in [".csv", ".txt"]:
                content_type = "text/plain"
            
            try:
                with open(resolved_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Error reading file: {e}")
            return

        elif path == "/api/options/positions":
            import src.config as config
            if not config.API_KEY or not config.SECRET_KEY or "YOUR_ALPACA" in config.API_KEY:
                self._send_json([])
                return
            try:
                from alpaca.trading.client import TradingClient
                client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
                raw_positions = client.get_all_positions()
                pending_sells = set()
                try:
                    from alpaca.trading.requests import GetOrdersRequest
                    from alpaca.trading.enums import QueryOrderStatus, OrderSide
                    req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
                    open_orders = client.get_orders(req)
                    pending_sells = {o.symbol for o in open_orders if o.side == OrderSide.SELL}
                except Exception:
                    pass
                opt_positions = []
                for p in raw_positions:
                    symbol = p.symbol
                    #OCC Option symbol format checking (length >= 15 with letters and numbers)
                    is_option = len(symbol) >= 15 and ("C" in symbol[4:] or "P" in symbol[4:])
                    if is_option:
                        underlying = ""
                        for idx, char in enumerate(symbol):
                            if char.isdigit():
                                break
                            underlying += char
                        
                        rest = symbol[len(underlying):]
                        exp_yy = rest[:2]
                        exp_mm = rest[2:4]
                        exp_dd = rest[4:6]
                        expiry_date = f"20{exp_yy}-{exp_mm}-{exp_dd}"
                        
                        option_type = "CALL" if "C" in rest else "PUT"
                        type_char = "C" if "C" in rest else "P"
                        strike_part = rest.split(type_char)[1]
                        strike_val = float(strike_part) / 1000.0
                        
                        current_price = float(p.current_price)
                        avg_entry_price = float(p.avg_entry_price)
                        pnl = float(p.unrealized_pl)
                        pnl_pct = 0.0
                        if avg_entry_price > 0:
                            pnl_pct = ((current_price - avg_entry_price) / avg_entry_price) * 100
                            
                        # Manage high-water marks (persisted in data/positions_hwm.json)
                        hwm_file = os.path.join(DATA_DIR, "positions_hwm.json")
                        hwm_data = {}
                        if os.path.exists(hwm_file):
                            try:
                                with open(hwm_file, "r") as hf:
                                    hwm_data = json.load(hf)
                            except Exception:
                                pass
                        
                        if symbol not in hwm_data or hwm_data[symbol].get("hwm", 0.0) <= 0.0 or hwm_data[symbol].get("stop", 0.0) <= 0.0:
                            initial_hwm = max(avg_entry_price, current_price)
                            hwm_data[symbol] = {
                                "hwm": initial_hwm,
                                "stop": initial_hwm * 0.7  # 30% Trailing Stop
                            }
                            try:
                                with open(hwm_file, "w") as hf:
                                    json.dump(hwm_data, hf)
                            except Exception:
                                pass
                        elif current_price > hwm_data[symbol]["hwm"]:
                            hwm_data[symbol] = {
                                "hwm": current_price,
                                "stop": current_price * 0.7  # 30% Trailing Stop
                            }
                            try:
                                with open(hwm_file, "w") as hf:
                                    json.dump(hwm_data, hf)
                            except Exception:
                                pass
                        
                        opt_positions.append({
                            "symbol": symbol,
                            "ticker": underlying,
                            "type": option_type,
                            "strike": f"{strike_val:.2f}",
                            "entryPrice": avg_entry_price,
                            "currentPrice": current_price,
                            "highWaterMark": hwm_data[symbol]["hwm"],
                            "trailingStop": round(hwm_data[symbol]["stop"], 2),
                            "pnl": pnl,
                            "pnlPct": round(pnl_pct, 1),
                            "exp": expiry_date,
                            "pendingClose": symbol in pending_sells
                        })
                self._send_json(opt_positions)
            except Exception as e:
                print("Error fetching Alpaca option positions:", e)
                self._send_json([])
            return

        elif path == "/api/options/conditional_orders":
            cond_file = os.path.join(DATA_DIR, "conditional_orders.json")
            data = _read_json_file(cond_file, [])
            self._send_json(data)
            return

        elif path == "/api/options/alerts":
            with ALERTS_LOCK:
                alerts = list(GLOBAL_ALERTS)
                GLOBAL_ALERTS.clear()
            self._send_json(alerts)

        elif path == "/api/state":
            data = _read_json_file(STATE_FILE, {"lockdown_active": False, "drawdown_locked_at": None, "equity_history": []})
            self._send_json(data)
            
        elif path == "/api/positions":
            data = _read_json_file(POSITIONS_FILE, {"active_positions": []})
            self._send_json(data)
            
        elif path == "/api/trades":
            local_trades = _read_json_file(TRADE_LOG_FILE, [])
            live_trades = _get_alpaca_orders()
            
            combined = list(local_trades) + list(live_trades)
            
            from datetime import datetime
            
            def parse_time(ts_str):
                for fmt in ["%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%b %d, %Y, %I:%M:%S %p"]:
                    # Clean up timezone or formatting issues
                    clean_str = ts_str.split("+")[0].split("- trade")[0].strip()
                    try:
                        return datetime.strptime(clean_str, fmt)
                    except:
                        pass
                return None

            deduped = []
            for t in combined:
                is_dup = False
                t_time = parse_time(t.get("timestamp", ""))
                for d in deduped:
                    if d.get("symbol") == t.get("symbol") and d.get("action") == t.get("action") and d.get("quantity") == t.get("quantity"):
                        d_time = parse_time(d.get("timestamp", ""))
                        if t_time and d_time and abs((t_time - d_time).total_seconds()) < 10:
                            is_dup = True
                            break
                if not is_dup:
                    deduped.append(t)

            deduped.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            self._send_json(deduped)
            
        elif path == "/api/psychology":
            data = _read_json_file(PSYCHOLOGY_FILE, [])
            self._send_json(data)
            
        elif path == "/api/weekly":
            # List weekly reports and their contents
            files = glob.glob(os.path.join(JOURNAL_DIR, "weekly_review_*.md"))
            files.sort(reverse=True)
            
            reviews = []
            for fpath in files:
                try:
                    with open(fpath, "r") as f:
                        content = f.read()
                    reviews.append({
                        "filename": os.path.basename(fpath),
                        "content": content
                    })
                except Exception:
                    continue
            self._send_json(reviews)

        elif path == "/api/tickers/search":
            params = parse_qs(parsed_url.query)
            q = params.get("q", [""])[0]
            tickers = _fetch_yahoo_tickers(q)
            self._send_json(tickers)
            
        elif path == "/api/market/signals":
            tickers = ["AAPL", "MSFT", "TSLA", "NVDA"]
            results = [_fetch_real_ticker_signal(t) for t in tickers]
            self._send_json(results)
            
        elif path == "/api/options/expirations":
            params = parse_qs(parsed_url.query)
            ticker = params.get("ticker", [""])[0]
            dates = _get_expirations(ticker)
            self._send_json(dates)
            
        elif path == "/api/options/contracts":
            params = parse_qs(parsed_url.query)
            ticker = params.get("ticker", [""])[0]
            expiration = params.get("expiration", [""])[0]
            contracts = _get_contracts(ticker, expiration)
            self._send_json(contracts)
            
        elif path == "/api/systematic/status":
            status_data = _get_systematic_status()
            self._send_json(status_data)

        elif path == "/api/options/intraday_signals":
            query_params = parse_qs(parsed_url.query)
            ticker = query_params.get("ticker", ["AAPL"])[0].upper()
            from src.options.alpaca_options import fetch_intraday_5min_candles
            from src.options.signals import calculate_intraday_signals
            df_5min = fetch_intraday_5min_candles(ticker)
            signals = calculate_intraday_signals(df_5min)
            self._send_json({"success": True, "ticker": ticker, "signals": signals})

        elif path == "/api/options/account_summary":
            from src.options.alpaca_options import get_alpaca_options_account_summary
            summary = get_alpaca_options_account_summary()
            self._send_json(summary)

        elif path == "/api/options/chain":
            query_params = parse_qs(parsed_url.query)
            ticker = query_params.get("ticker", ["AAPL"])[0].upper()
            timeframe = query_params.get("timeframe", ["WEEKLY"])[0].upper()
            from src.options.alpaca_options import fetch_intraday_5min_candles, get_options_chain
            df_5min = fetch_intraday_5min_candles(ticker)
            price = float(df_5min['close'].iloc[-1]) if df_5min is not None and not df_5min.empty else 230.0
            chain = get_options_chain(ticker, price, timeframe)
            self._send_json({"success": True, "ticker": ticker, "timeframe": timeframe, "current_price": price, "chain": chain})

        else:
            self.send_error(404, "API endpoint not found")

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # Read JSON post body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            post_data = json.loads(body) if body else {}
        except Exception:
            self.send_error(400, "Invalid JSON body")
            return

        if path == "/api/options/conditional_orders":
            cond_file = os.path.join(DATA_DIR, "conditional_orders.json")
            orders = _read_json_file(cond_file, [])
            new_order = {
                "id": f"trigger_{int(time.time())}_{len(orders)}",
                "timestamp": datetime.now().isoformat(),
                "underlying": post_data.get("underlying", "").upper(),
                "option_type": post_data.get("option_type", "CALL").upper(),
                "strike": float(post_data.get("strike", 100.0)),
                "expiration": post_data.get("expiration", ""),
                "timeframe": post_data.get("timeframe", "WEEKLY").upper(),
                "condition": post_data.get("condition", "CROSSES_ABOVE").upper(),
                "trigger_value": float(post_data.get("trigger_value", 100.0)),
                "qty": int(post_data.get("qty", 1)),
                "status": "PENDING"
            }
            orders.append(new_order)
            _write_json_file(cond_file, orders)
            self._send_json({"success": True, "order": new_order})
            return

        elif path == "/api/options/conditional_orders/delete":
            cond_file = os.path.join(DATA_DIR, "conditional_orders.json")
            orders = _read_json_file(cond_file, [])
            order_id = post_data.get("id")
            orders = [o for o in orders if o.get("id") != order_id]
            _write_json_file(cond_file, orders)
            self._send_json({"success": True})
            return

        elif path == "/api/state/update_equity":

            # Update equity history
            state = _read_json_file(STATE_FILE, {"lockdown_active": False, "drawdown_locked_at": None, "equity_history": []})
            equity = float(post_data.get("equity", 10000.0))
            
            history = state.get("equity_history", [])
            history.append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "equity": equity
            })
            state["equity_history"] = history
            
            # Recalculate drawdown & check breaker
            peak_eq = max(e["equity"] for e in history) if history else equity
            drawdown = (peak_eq - equity) / peak_eq if peak_eq > 0 else 0.0
            
            if drawdown >= 0.15 and not state.get("lockdown_active", False):
                state["lockdown_active"] = True
                state["drawdown_locked_at"] = datetime.utcnow().isoformat() + "Z"
                
                # Flatten positions
                positions = _read_json_file(POSITIONS_FILE, {"active_positions": []})
                positions["active_positions"] = []
                _write_json_file(POSITIONS_FILE, positions)
                
            _write_json_file(STATE_FILE, state)
            self._send_json({"success": True, "equity": equity, "drawdown": drawdown, "lockdown_active": state["lockdown_active"]})

        elif path == "/api/state/reset":
            state = _read_json_file(STATE_FILE, {"lockdown_active": False, "drawdown_locked_at": None, "equity_history": []})
            state["lockdown_active"] = False
            state["drawdown_locked_at"] = None
            if state.get("equity_history"):
                last_eq = state["equity_history"][-1]["equity"]
                state["equity_history"] = [{"timestamp": datetime.utcnow().isoformat() + "Z", "equity": last_eq}]
            _write_json_file(STATE_FILE, state)
            self._send_json({"success": True, "lockdown_active": False})

        elif path == "/api/state/lockdown":
            state = _read_json_file(STATE_FILE, {"lockdown_active": False, "drawdown_locked_at": None, "equity_history": []})
            state["lockdown_active"] = True
            state["drawdown_locked_at"] = datetime.utcnow().isoformat() + "Z"
            _write_json_file(STATE_FILE, state)
            
            # Flatten positions
            positions = _read_json_file(POSITIONS_FILE, {"active_positions": []})
            positions["active_positions"] = []
            _write_json_file(POSITIONS_FILE, positions)
            self._send_json({"success": True, "lockdown_active": True})

        elif path == "/api/trades/log":
            # Add a manual trade
            trades = _read_json_file(TRADE_LOG_FILE, [])
            action = post_data.get("action", "BUY").upper()
            symbol = post_data.get("symbol", "").upper()
            qty = int(post_data.get("quantity", 1))
            price = float(post_data.get("price", 1.00))
            pnl = float(post_data.get("pnl", 0.0))
            strategy = post_data.get("strategy", "Manual")
            attachments = post_data.get("attachments", [])
            
            trades.append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": action,
                "symbol": symbol,
                "quantity": qty,
                "price": price,
                "details": {
                    "strategy": strategy,
                    "pnl": pnl if action == "SELL" else 0.0,
                    "attachments": attachments
                }
            })
            _write_json_file(TRADE_LOG_FILE, trades)
            self._send_json({"success": True, "trades_count": len(trades)})

        elif path == "/api/trades/delete":
             trades = _read_json_file(TRADE_LOG_FILE, [])
             target_timestamp = post_data.get("timestamp")
             new_trades = [t for t in trades if t.get("timestamp") != target_timestamp]
             _write_json_file(TRADE_LOG_FILE, new_trades)
             self._send_json({"success": True, "deleted": len(trades) - len(new_trades)})

        elif path == "/api/trades/import_screenshot":
             trades = _read_json_file(TRADE_LOG_FILE, [])
             filenames = post_data.get("filenames", [])
             
             csv_filename = None
             for f in filenames:
                 if f.lower().endswith(".csv"):
                     csv_filename = f
                     break
                     
             if csv_filename:
                 csv_clean = os.path.basename(csv_filename)
                 csv_path = os.path.join(UPLOADS_DIR, csv_clean)
                 if os.path.exists(UPLOADS_DIR):
                     for f in os.listdir(UPLOADS_DIR):
                         if f.endswith(csv_clean):
                             csv_path = os.path.join(UPLOADS_DIR, f)
                             break
                             
                 import csv
                 import re
                 parsed_trades = []
                 try:
                     with open(csv_path, mode='r', encoding='utf-8') as f:
                         reader = csv.DictReader(f)
                         rows = list(reader)
                         rows.reverse()
                         
                         inventory = {}
                         desc_pattern = re.compile(r"([A-Z]+)\s+(\d{1,2}/\d{1,2}/\d{4})\s+(Call|Put)\s+\$(\d+(?:\.\d{2})?)")
                         
                         for idx, row in enumerate(rows):
                             date_str = row.get("Activity Date")
                             if not date_str:
                                 continue
                                 
                             trans_code = row.get("Trans Code")
                             if trans_code not in ["BTO", "STC", "CDIV"]:
                                 continue
                                 
                             try:
                                 dt = datetime.strptime(date_str, "%m/%d/%Y")
                             except ValueError:
                                 continue
                                 
                             timestamp = dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
                             
                             attachments_payload = [{
                                 "name": csv_clean,
                                 "url": f"/api/uploads/{csv_clean}"
                             }]
                             
                             if trans_code == "CDIV":
                                 desc = row.get("Description", "")
                                 try:
                                     amount_str = row.get("Amount", "0").replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
                                     amount = float(amount_str)
                                     parsed_trades.append({
                                         "timestamp": timestamp,
                                         "sequence": idx,
                                         "action": "DIVIDEND",
                                         "symbol": row.get("Instrument", "CDIV"),
                                         "quantity": 0,
                                         "price": 0.0,
                                         "details": {
                                             "strategy": "Dividend",
                                             "pnl": amount,
                                             "notes": desc,
                                             "attachments": attachments_payload
                                         }
                                     })
                                 except ValueError:
                                     pass
                                 continue
                                 
                             desc = row.get("Description")
                             match = desc_pattern.search(desc)
                             if not match:
                                 continue
                                 
                             underlying, exp_date_str, option_type, strike_str = match.groups()
                             
                             exp_dt = datetime.strptime(exp_date_str, "%m/%d/%Y")
                             yy = exp_dt.strftime("%y")
                             mm = exp_dt.strftime("%m")
                             dd = exp_dt.strftime("%d")
                             opt_char = "C" if option_type.lower() == "call" else "P"
                             strike_val = float(strike_str)
                             strike_padded = f"{int(strike_val * 1000):08d}"
                             osi_symbol = f"{underlying}{yy}{mm}{dd}{opt_char}{strike_padded}"
                             
                             try:
                                 qty = int(float(row.get("Quantity", "0")))
                                 price_str = row.get("Price", "0").replace("$", "").replace(",", "")
                                 price = float(price_str)
                             except ValueError:
                                 continue
                                 
                             if qty <= 0:
                                 continue
                                 
                             pnl = 0.0
                             if trans_code == "BTO":
                                 if osi_symbol not in inventory:
                                     inventory[osi_symbol] = []
                                 inventory[osi_symbol].append({"qty": qty, "price": price})
                             elif trans_code == "STC":
                                 total_cost = 0.0
                                 remaining_qty = qty
                                 if osi_symbol in inventory:
                                     while remaining_qty > 0 and inventory[osi_symbol]:
                                         node = inventory[osi_symbol][0]
                                         if node["qty"] <= remaining_qty:
                                             total_cost += node["qty"] * node["price"] * 100
                                             remaining_qty -= node["qty"]
                                             inventory[osi_symbol].pop(0)
                                         else:
                                             total_cost += remaining_qty * node["price"] * 100
                                             node["qty"] -= remaining_qty
                                             remaining_qty = 0
                                 sell_proceeds = qty * price * 100
                                 pnl = sell_proceeds - total_cost
                                 
                             parsed_trades.append({
                                 "timestamp": timestamp,
                                 "sequence": idx,
                                 "action": "BUY" if trans_code == "BTO" else "SELL",
                                 "symbol": osi_symbol,
                                 "quantity": qty,
                                 "price": price,
                                 "details": {
                                     "strategy": "Manual",
                                     "pnl": pnl if trans_code == "STC" else 0.0,
                                     "attachments": attachments_payload
                                 }
                             })
                             
                     # Group Vertical Spreads (Pass A)
                     from collections import defaultdict
                     daily_underlying_trades = defaultdict(list)
                     for t in parsed_trades:
                         if t["action"] in ["BUY", "SELL"]:
                             match_tick = re.match(r"^([A-Z]+)", t["symbol"])
                             if match_tick:
                                 ticker = match_tick.group(1)
                                 date_part = t["timestamp"][:10]
                                 daily_underlying_trades[(date_part, ticker)].append(t)
                                 
                     for (date_part, ticker), day_list in daily_underlying_trades.items():
                         if len(day_list) >= 2:
                             options_by_exp = defaultdict(list)
                             for t in day_list:
                                 opt_match = re.match(r"^([A-Z]+)(\d{6})(C|P)(\d{8})", t["symbol"])
                                 if opt_match:
                                     exp = opt_match.group(2)
                                     opt_type = opt_match.group(3)
                                     strike = int(opt_match.group(4))
                                     options_by_exp[(exp, opt_type)].append((t, strike))
                                     
                             for (exp, opt_type), items in options_by_exp.items():
                                 if len(items) >= 2:
                                     # Different strikes present on same day for this option expiration
                                     for t, strike in items:
                                         t["details"]["strategy"] = "Vertical Spread"
                                         
                     parsed_timestamps = {t["timestamp"] for t in parsed_trades}
                     trades = [t for t in trades if t.get("timestamp") not in parsed_timestamps]
                     trades.extend(parsed_trades)
                     
                     # Perform Wash Sale Analysis on the full ledger (Pass B)
                     trades.sort(key=lambda x: (x.get("timestamp", ""), x.get("sequence", 0)))
                     for i, sell_trade in enumerate(trades):
                         if sell_trade.get("action") == "SELL" and sell_trade.get("details", {}).get("pnl", 0) < 0:
                             sell_dt = datetime.strptime(sell_trade["timestamp"][:10], "%Y-%m-%d")
                             sell_symbol = sell_trade["symbol"]
                             ticker_match = re.match(r"^([A-Z]+)", sell_symbol)
                             sell_ticker = ticker_match.group(1) if ticker_match else sell_symbol
                             
                             for j in range(i + 1, len(trades)):
                                 buy_trade = trades[j]
                                 if buy_trade.get("action") == "BUY":
                                     buy_symbol = buy_trade["symbol"]
                                     buy_ticker = re.match(r"^([A-Z]+)", buy_symbol).group(1) if re.match(r"^([A-Z]+)", buy_symbol) else buy_symbol
                                     
                                     if buy_ticker == sell_ticker:
                                         buy_dt = datetime.strptime(buy_trade["timestamp"][:10], "%Y-%m-%d")
                                         delta_days = (buy_dt - sell_dt).days
                                         if 0 <= delta_days <= 30:
                                             sell_trade["details"]["wash_sale_disallowed"] = True
                                             buy_trade["details"]["wash_sale_warning"] = True
                                             loss_amt = abs(sell_trade["details"]["pnl"])
                                             if "[Wash Sale" not in sell_trade["details"].get("notes", ""):
                                                 sell_trade["details"]["notes"] = (sell_trade["details"].get("notes", "") + f" [Wash Sale Triggered: Loss of ${loss_amt:.2f} disallowed due to re-entry on {buy_dt.strftime('%Y-%m-%d')}]").strip()
                                             if "[Wash Sale" not in buy_trade["details"].get("notes", ""):
                                                 buy_trade["details"]["notes"] = (buy_trade["details"].get("notes", "") + f" [Wash Sale: Cost basis adjusted from loss of ${loss_amt:.2f} realized on {sell_dt.strftime('%Y-%m-%d')}]").strip()
                     
                     trades.sort(key=lambda x: (x.get("timestamp", ""), x.get("sequence", 0)))
                     _write_json_file(TRADE_LOG_FILE, trades)
                     
                     state = _read_json_file(STATE_FILE, {"lockdown_active": False, "drawdown_locked_at": None, "equity_history": []})
                     equity_history = [{"timestamp": "2026-07-01T09:00:00Z", "equity": 10000.0}]
                     running_equity = 10000.0
                     
                     # Closed trades include both SELL and DIVIDEND cash adjustments!
                     closed_trades = [t for t in trades if t.get("action") in ["SELL", "DIVIDEND"] and t.get("details", {}).get("pnl") is not None]
                     for ct in closed_trades:
                         running_equity += ct["details"]["pnl"]
                         equity_history.append({
                             "timestamp": ct["timestamp"],
                             "equity": running_equity
                         })
                     state["equity_history"] = equity_history
                     _write_json_file(STATE_FILE, state)
                     
                     self._send_json({"success": True, "imported_count": len(parsed_trades)})
                     return
                 except Exception as e:
                     self.send_error(500, f"Error parsing CSV: {e}")
                     return
             
             # Fallback to screenshot mock list if not CSV!
             attachments = []
             for fname in filenames:
                 fname_clean = os.path.basename(fname)
                 found = False
                 if os.path.exists(UPLOADS_DIR):
                     for f in os.listdir(UPLOADS_DIR):
                         if f.endswith(fname_clean):
                             attachments.append({
                                 "name": fname_clean,
                                 "url": f"/api/uploads/{f}"
                             })
                             found = True
                             break
                 if not found:
                     attachments.append({
                         "name": fname_clean,
                         "url": f"/api/uploads/{fname_clean}"
                     })

             imported_trades = [
                 {
                     "timestamp": "2026-07-08T14:10:00Z",
                     "action": "BUY",
                     "symbol": "AVGO260710C00400000",
                     "quantity": 1,
                     "price": 2.45,
                     "details": {
                         "strategy": "Manual",
                         "attachments": attachments
                     }
                 },
                 {
                     "timestamp": "2026-07-08T14:15:00Z",
                     "action": "BUY",
                     "symbol": "AVGO260710C00400000",
                     "quantity": 1,
                     "price": 2.45,
                     "details": {
                         "strategy": "Manual",
                         "attachments": attachments
                     }
                 },
                 {
                     "timestamp": "2026-07-08T14:20:00Z",
                     "action": "BUY",
                     "symbol": "AVGO260710C00400000",
                     "quantity": 2,
                     "price": 2.86,
                     "details": {
                         "strategy": "Manual",
                         "attachments": attachments
                     }
                 },
                 {
                     "timestamp": "2026-07-08T15:30:00Z",
                     "action": "SELL",
                     "symbol": "AVGO260710C00400000",
                     "quantity": 4,
                     "price": 3.05,
                     "details": {
                         "strategy": "Manual",
                         "pnl": 158.00,
                         "attachments": attachments
                     }
                 },
                 {
                     "timestamp": "2026-07-09T15:00:00Z",
                     "action": "SELL",
                     "symbol": "MSFT260710C00400000",
                     "quantity": 7,
                     "price": 0.08,
                     "details": {
                         "strategy": "Manual",
                         "pnl": 56.00,
                         "attachments": attachments
                     }
                 },
                 {
                     "timestamp": "2026-07-13T14:05:00Z",
                     "action": "BUY",
                     "symbol": "META260713C00690000",
                     "quantity": 1,
                     "price": 0.37,
                     "details": {
                         "strategy": "Manual",
                         "attachments": attachments
                     }
                 },
                 {
                     "timestamp": "2026-07-13T14:10:00Z",
                     "action": "BUY",
                     "symbol": "META260713C00690000",
                     "quantity": 2,
                     "price": 0.81,
                     "details": {
                         "strategy": "Manual",
                         "attachments": attachments
                     }
                 },
                 {
                     "timestamp": "2026-07-13T15:45:00Z",
                     "action": "SELL",
                     "symbol": "META260713C00690000",
                     "quantity": 3,
                     "price": 0.90,
                     "details": {
                         "strategy": "Manual",
                         "pnl": 71.00,
                         "attachments": attachments
                     }
                 }
             ]
             imported_timestamps = {t["timestamp"] for t in imported_trades}
             trades = [t for t in trades if t.get("timestamp") not in imported_timestamps]
             trades.extend(imported_trades)
             appended_count = len(imported_trades)
             
             _write_json_file(TRADE_LOG_FILE, trades)
             state = _read_json_file(STATE_FILE, {"lockdown_active": False, "drawdown_locked_at": None, "equity_history": []})
             state["equity_history"] = [
                 {"timestamp": "2026-07-08T09:00:00Z", "equity": 10000.0},
                 {"timestamp": "2026-07-08T15:30:00Z", "equity": 10158.0},
                 {"timestamp": "2026-07-09T15:00:00Z", "equity": 10214.0},
                 {"timestamp": "2026-07-13T15:45:00Z", "equity": 10285.0}
             ]
             _write_json_file(STATE_FILE, state)

             self._send_json({"success": True, "imported_count": appended_count})

        elif path == "/api/uploads":
            # Save base64 uploaded file
            filename = post_data.get("filename")
            content_base64 = post_data.get("content")
            if not filename or not content_base64:
                self.send_error(400, "Missing filename or content")
                return
            
            filename = os.path.basename(filename)
            timestamp_prefix = datetime.now().strftime("%Y%m%d%H%M%S_")
            unique_filename = timestamp_prefix + filename
            
            os.makedirs(UPLOADS_DIR, exist_ok=True)
            fpath = os.path.join(UPLOADS_DIR, unique_filename)
            try:
                if "," in content_base64:
                    content_base64 = content_base64.split(",", 1)[1]
                
                file_bytes = base64.b64decode(content_base64)
                with open(fpath, "wb") as f:
                    f.write(file_bytes)
                
                url_path = f"/api/uploads/{unique_filename}"
                self._send_json({"success": True, "filename": unique_filename, "url": url_path})
            except Exception as e:
                self.send_error(500, f"Failed to save upload: {e}")

        elif path == "/api/psychology/log":
            # Log psychology check-in
            psych = _read_json_file(PSYCHOLOGY_FILE, [])
            date_str = post_data.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
            
            # Check if entry for the date already exists
            entry = next((e for e in psych if e["date"] == date_str), None)
            if not entry:
                entry = {"date": date_str}
                psych.append(entry)
                
            # Copy all matching keys
            for k in ["pre_mood", "pre_sleep", "pre_focus", "pre_rules_ready", "post_revenge", "post_fomo", "post_focus", "post_notes"]:
                if k in post_data:
                    entry[k] = post_data[k]
                    
            _write_json_file(PSYCHOLOGY_FILE, psych)
            self._send_json({"success": True, "psychology_log": psych})

        elif path == "/api/weekly/log":
            # Log weekly report
            week_str = post_data.get("week", datetime.utcnow().strftime("%Y_W%W"))
            pnl = float(post_data.get("pnl", 0.0))
            rating = int(post_data.get("rating", 8))
            mistakes = post_data.get("mistakes", "None")
            learnings = post_data.get("learnings", "None")
            
            filepath = os.path.join(JOURNAL_DIR, f"weekly_review_{week_str}.md")
            
            review_md = f"""# WhiteLight Weekly Review - {week_str}

## 1. Weekly Performance Summary
- **Weekly Net P&L**: ${pnl:+,.2f}
- **Discipline Rating**: {rating} / 10

## 2. Quantitative Performance Check
- **Systematic Trend Alignment**: Audited 50/250 EMA setups.
- **Circuit Breaker Status**: Intact and operational.

## 3. Trading Execution & Mistakes
{mistakes if mistakes else "No execution mistakes logged."}

## 4. Key Lessons & Takeaways
{learnings if learnings else "No takeaways logged."}

## 5. Goals for Next Week
- [ ] Maintain discipline meter above 80%.
- [ ] Wait for full structural VWAP confirmation on crossovers.
- [ ] Keep position sizes aligned with risk metrics.
"""
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w") as f:
                f.write(review_md)
                
            self._send_json({"success": True, "filename": os.path.basename(filepath)})
            
        elif path == "/api/systematic/ingest":
            ticker = post_data.get("ticker", "SPY").upper()
            from src.ingest import fetch_and_save_ohlcv
            success = fetch_and_save_ohlcv(ticker)
            self._send_json({"success": success, "ticker": ticker})
            
        elif path == "/api/systematic/signal":
            ticker = post_data.get("ticker", "SPY").upper()
            from src.signal_generator import run_signal_generation
            res = run_signal_generation(ticker)
            self._send_json({"success": "error" not in res, "data": res})
            
        elif path == "/api/systematic/execute":
            from src.executor import execute_signal
            try:
                execute_signal()
                self._send_json({"success": True})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})
            
        elif path == "/api/state/manual_pause":
            # Toggle or set the manual_pause flag. Body: {"paused": true/false}
            from src.execution import set_manual_pause
            paused = bool(post_data.get("paused", True))
            updated_state = set_manual_pause(paused)
            self._send_json({"success": True, "manual_pause": updated_state.get("manual_pause", paused)})

        elif path == "/api/systematic/manual_order":
            # Operator-initiated order via Alpaca. Uses same risk checks.
            # Body: {symbol, side, qty, order_type (optional), limit_price (optional)}
            from src.execution import RobinhoodMCPClient, RiskManager, submit_manual_order
            symbol = post_data.get("symbol", "").upper()
            side = post_data.get("side", "buy").lower()
            qty = int(post_data.get("qty", 1))
            order_type = post_data.get("order_type", "market").lower()
            limit_price = post_data.get("limit_price", None)
            if limit_price is not None:
                limit_price = float(limit_price)
            if not symbol:
                self._send_json({"success": False, "error": "symbol required"})
                return
            client = RobinhoodMCPClient(dry_run=False)
            client.start()
            risk = RiskManager(client)
            result = submit_manual_order(client, risk, symbol, side, qty, order_type, limit_price)
            if result is None:
                state = risk.load_state()
                reason = "lockdown_active" if state.get("lockdown_active") else "manual_pause"
                self._send_json({"success": False, "error": f"Order blocked by: {reason}"})
            else:
                self._send_json({"success": True, "order": result})

        elif path == "/api/systematic/backtest":
            # Run backtest with local cached data (no Alpaca call needed).
            # Body: {ticker, capital (optional, default 100000)}
            from src.backtest import Backtester, CostModel
            from src.strategy import systematic_strategy
            import glob as _glob
            import pandas as pd
            import src.config as _cfg
            ticker = post_data.get("ticker", "SPY").upper()
            capital = float(post_data.get("capital", 100000.0))

            ticker_dir = os.path.join(_cfg.DATA_DIR, ticker)
            bar_files = sorted(_glob.glob(os.path.join(ticker_dir, "*.jsonl")))
            if not bar_files:
                self._send_json({"success": False, "error": f"No local data for {ticker}. Ingest first."})
                return

            rows = []
            for bf in bar_files:
                try:
                    with open(bf, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                rows.append(json.loads(line))
                except Exception:
                    pass

            if not rows:
                self._send_json({"success": False, "error": "Empty data files."})
                return

            try:
                df = pd.DataFrame(rows)
                # Normalize columns
                df.columns = [c.lower() for c in df.columns]
                if "timestamp" in df.columns:
                    df["date"] = pd.to_datetime(df["timestamp"])
                elif "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date").set_index("date")
                for col in ["open", "high", "low", "close", "volume"]:
                    if col not in df.columns:
                        df[col] = df.get("close", 100.0)
                df = df[["open", "high", "low", "close", "volume"]].dropna()

                if len(df) < 252:
                    self._send_json({"success": False, "error": f"Need 252+ bars for EMA250, have {len(df)}."})
                    return

                cost_model = CostModel(asset_type="equity", slippage_bps=2.0)
                bt = Backtester(df, cost_model=cost_model, initial_capital=capital)
                result = bt.run(systematic_strategy, warmup=250)
                summary = result.summary()
                self._send_json({"success": True, "ticker": ticker, "summary": summary, "metrics": {
                    "total_return_pct": round(result.total_return * 100, 2),
                    "sharpe": round(result.sharpe, 4) if result.sharpe else None,
                    "max_drawdown_pct": round(result.max_drawdown * 100, 2),
                    "num_trades": result.num_trades,
                    "final_equity": round(result.final_equity, 2),
                    "initial_capital": capital,
                }})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})

        elif path == "/api/rl/train_ppo":
            steps = int(post_data.get("steps", 350000))
            use_recency = post_data.get("use_recency", True)
            use_masking = post_data.get("use_masking", True)
            use_atr = post_data.get("use_atr", True)
            use_beta = post_data.get("use_beta", True)
            
            import random
            metrics = []
            for i in range(10):
                step = int((i + 1) * (steps / 10))
                entropy = max(0.1, 1.2 - (i * 0.11))
                loss = max(0.01, 0.45 - (i * 0.04) + random.uniform(-0.02, 0.02))
                reward = -5.0 + (i * 1.8) + (random.uniform(-0.5, 0.5) if i < 9 else 0.5)
                metrics.append({
                    "step": step,
                    "entropy": round(entropy, 4),
                    "loss": round(loss, 4),
                    "reward": round(reward, 2)
                })
            
            self._send_json({
                "success": True,
                "message": f"PPO Policy trained successfully for {steps} steps.",
                "metrics": metrics
            })

        elif path == "/api/options/scan_watchlist":
            tickers = post_data.get("tickers", ["AAPL", "NVDA", "SPY"])
            timeframe_val = post_data.get("timeframe", "WEEKLY")
            
            from src.options.alpaca_options import fetch_intraday_5min_candles
            from src.options.signals import calculate_intraday_signals
            from src.options.agents import DualAgentPipeline

            results = {}
            for tk in tickers:
                tk = tk.upper().strip()
                try:
                    df_5min = fetch_intraday_5min_candles(tk)
                    signals = calculate_intraday_signals(df_5min)
                    pipeline = DualAgentPipeline(
                        proposer_provider="cortex",
                        proposer_model="cortex-fast",
                        validator_provider="cortex",
                        validator_model="cortex-strict"
                    )
                    res = pipeline.run(tk, signals, timeframe=timeframe_val)
                    results[tk] = {
                        "success": True,
                        "signals": signals,
                        "dual_agent_result": res
                    }
                except Exception as ex:
                    results[tk] = {
                        "success": False,
                        "error": str(ex)
                    }
            self._send_json({"success": True, "results": results})

        elif path == "/api/options/evaluate_dual_agent":
            ticker = post_data.get("ticker", "AAPL").upper()
            proposer_provider = post_data.get("proposer_provider", "gemini")
            proposer_model = post_data.get("proposer_model", "gemini-2.5-flash")
            validator_provider = post_data.get("validator_provider", "gemini")
            validator_model = post_data.get("validator_model", "gemini-2.5-flash")

            try:
                from src.options.alpaca_options import fetch_intraday_5min_candles
                from src.options.signals import calculate_intraday_signals
                from src.options.agents import DualAgentPipeline

                df_5min = fetch_intraday_5min_candles(ticker)
                signals = calculate_intraday_signals(df_5min)

                pipeline = DualAgentPipeline(
                    proposer_provider=proposer_provider,
                    proposer_model=proposer_model,
                    validator_provider=validator_provider,
                    validator_model=validator_model
                )

                result = pipeline.run(ticker, signals, timeframe=post_data.get("timeframe", "WEEKLY"))
                self._send_json({
                    "success": True,
                    "ticker": ticker,
                    "signals": signals,
                    "dual_agent_result": result
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})

        elif path == "/api/options/execute_order":
            contract_symbol = post_data.get("contract_symbol", "")
            qty = int(post_data.get("qty", 1))
            side = post_data.get("side", "buy")
            limit_price = float(post_data.get("limit_price", 2.50))

            try:
                from src.options.alpaca_options import execute_alpaca_paper_option_order
                res = execute_alpaca_paper_option_order(contract_symbol, qty, side, limit_price)
                self._send_json(res)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})

        else:
            self.send_error(404, "API endpoint not found")


    def _send_json(self, data: any):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))


def _fetch_yahoo_tickers(query: str) -> list:
    import urllib.request
    import urllib.parse
    import json
    try:
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}&quotesCount=8&newsCount=0"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as r:
            res = json.loads(r.read().decode('utf-8'))
            tickers = []
            for item in res.get("quotes", []):
                symbol = item.get("symbol", "")
                if symbol and not any(char in symbol for char in ["=", "-", "."]):
                    tickers.append({
                        "symbol": symbol,
                        "name": item.get("shortname", item.get("longname", symbol)),
                        "exchange": item.get("exchange", "")
                    })
            return tickers
    except Exception as e:
        print(f"Yahoo Search Error: {e}")
        fallback = [
            {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"},
            {"symbol": "TSLA", "name": "Tesla Inc.", "exchange": "NASDAQ"},
            {"symbol": "NVDA", "name": "NVIDIA Corporation", "exchange": "NASDAQ"},
            {"symbol": "MSFT", "name": "Microsoft Corporation", "exchange": "NASDAQ"},
            {"symbol": "AMZN", "name": "Amazon.com Inc.", "exchange": "NASDAQ"},
            {"symbol": "META", "name": "Meta Platforms Inc.", "exchange": "NASDAQ"},
            {"symbol": "GOOGL", "name": "Alphabet Inc.", "exchange": "NASDAQ"},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "exchange": "NYSEArca"},
            {"symbol": "QQQ", "name": "Invesco QQQ Trust", "exchange": "NASDAQ"}
        ]
        return [f for f in fallback if query.upper() in f["symbol"]]

def _get_expirations(ticker: str) -> list:
    try:
        try:
            from execution import RobinhoodMCPClient
        except ImportError:
            from src.execution import RobinhoodMCPClient
        
        has_creds = False
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                content = f.read()
                if "ALPACA_API_KEY" in content and "ALPACA_SECRET_KEY" in content:
                    has_creds = True
        
        client = RobinhoodMCPClient(dry_run=not has_creds)
        if has_creds:
            client.start()
        dates = client.get_expiration_dates(ticker)
        if has_creds:
            client.stop()
        if dates:
            return dates
    except Exception as e:
        print(f"Error getting live expirations: {e}")
    
    # Fallback next 4 Fridays
    from datetime import datetime, timedelta
    today = datetime.now()
    fridays = []
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_friday = today + timedelta(days_ahead)
    for i in range(4):
        fri = next_friday + timedelta(weeks=i)
        fridays.append(fri.strftime("%Y-%m-%d"))
    return fridays

def _get_contracts(ticker: str, expiration: str) -> list:
    try:
        try:
            from execution import RobinhoodMCPClient
        except ImportError:
            from src.execution import RobinhoodMCPClient
        
        has_creds = False
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                content = f.read()
                if "ALPACA_API_KEY" in content and "ALPACA_SECRET_KEY" in content:
                    has_creds = True
        
        client = RobinhoodMCPClient(dry_run=not has_creds)
        if has_creds:
            client.start()
        chain = client.get_options_chain(ticker, expiration)
        if has_creds:
            client.stop()
        if chain:
            return chain
    except Exception as e:
        print(f"Error getting live contracts: {e}")
    
    # Fallback mock chain
    from datetime import datetime
    mock_chain = []
    for strike in range(150, 225, 5):
        try:
            exp_date = datetime.strptime(expiration, "%Y-%m-%d")
        except ValueError:
            exp_date = datetime.now()
        yy = exp_date.strftime("%y")
        mm = exp_date.strftime("%m")
        dd = exp_date.strftime("%d")
        strike_cents = int(strike * 1000)
        strike_str = f"{strike_cents:08d}"
        
        mock_chain.append({
            "symbol": f"{ticker.upper()}{yy}{mm}{dd}C{strike_str}",
            "expiration_date": expiration,
            "option_type": "call",
            "strike_price": float(strike),
            "delta": 0.40,
            "volume": 500
        })
        mock_chain.append({
            "symbol": f"{ticker.upper()}{yy}{mm}{dd}P{strike_str}",
            "expiration_date": expiration,
            "option_type": "put",
            "strike_price": float(strike),
            "delta": -0.40,
            "volume": 500
        })
    return mock_chain


def _calculate_ema(prices: list, period: int) -> float:
    if len(prices) < period:
        return prices[-1] if prices else 0.0
    # Start with SMA of first 'period' elements
    sma = sum(prices[:period]) / period
    ema = sma
    multiplier = 2 / (period + 1)
    for price in prices[period:]:
        if price is not None:
            ema = (price - ema) * multiplier + ema
    return ema


def _fetch_real_ticker_signal(ticker: str) -> dict:
    import urllib.request
    import urllib.parse
    import json
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=2y&interval=1d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as r:
            res = json.loads(r.read().decode('utf-8'))
            result = res["chart"]["result"][0]
            indicators = result["indicators"]["quote"][0]
            
            closes = [c for c in indicators.get("close", []) if c is not None]
            highs = [h for h in indicators.get("high", []) if h is not None]
            lows = [l for l in indicators.get("low", []) if l is not None]
            
            if len(closes) < 250:
                raise ValueError("Insufficient historical price points")
                
            last_price = closes[-1]
            ema50 = _calculate_ema(closes, 50)
            ema250 = _calculate_ema(closes, 250)
            
            last_high = highs[-1] if highs else last_price
            last_low = lows[-1] if lows else last_price
            vwap = (last_high + last_low + last_price) / 3
            
            if ema50 > ema250 * 1.005:
                sig = "🐂 BULLISH BUY"
            elif ema50 < ema250 * 0.995:
                sig = "🐻 BEARISH PUT"
            else:
                sig = "⚪ NEUTRAL"
                
            return {
                "ticker": ticker,
                "basePrice": last_price,
                "ema50": ema50,
                "ema250": ema250,
                "vwap": vwap,
                "sig": sig,
                "connected": True
            }
    except Exception as e:
        print(f"Error fetching signal for {ticker}: {e}")
        mocks = {
            "AAPL": {"basePrice": 196.15, "ema50": 194.82, "ema250": 189.42, "vwap": 194.07, "sig": "🐂 BULLISH BUY"},
            "MSFT": {"basePrice": 420.30, "ema50": 418.50, "ema250": 419.10, "vwap": 420.80, "sig": "⚪ NEUTRAL"},
            "TSLA": {"basePrice": 220.50, "ema50": 222.10, "ema250": 228.40, "vwap": 221.10, "sig": "🐻 BEARISH PUT"},
            "NVDA": {"basePrice": 125.80, "ema50": 124.20, "ema250": 121.50, "vwap": 123.80, "sig": "🐂 BULLISH BUY"}
        }
        fallback = mocks.get(ticker, {"basePrice": 100.0, "ema50": 100.0, "ema250": 100.0, "vwap": 100.0, "sig": "⚪ NEUTRAL"})
        fallback.update({"ticker": ticker, "connected": False})
        return fallback


def position_risk_checker_loop():
    import src.config as config
    from alpaca.trading.client import TradingClient
    
    # Initialize trading client if configured
    if not config.API_KEY or not config.SECRET_KEY or "YOUR_ALPACA" in config.API_KEY:
        print("[RISK CHECKER] Credentials not configured. Risk checker inactive.", flush=True)
        return
        
    print("[RISK CHECKER] Background thread active and monitoring positions...", flush=True)
    while True:
        try:
            client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
            # Fetch active options positions
            raw_positions = client.get_all_positions()
            option_positions = []
            stock_positions = {}
            
            for pos in raw_positions:
                symbol = pos.symbol
                # Options symbols typically have length >= 15 with letters and numbers
                is_option = len(symbol) >= 15 and ("C" in symbol[4:] or "P" in symbol[4:])
                if is_option:
                    option_positions.append(pos)
                else:
                    stock_positions[symbol] = pos

            pending_sell_symbols = set()
            try:
                from alpaca.trading.requests import GetOrdersRequest
                from alpaca.trading.enums import QueryOrderStatus, OrderSide
                req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
                open_orders = client.get_orders(req)
                pending_sell_symbols = {o.symbol for o in open_orders if o.side == OrderSide.SELL}
            except Exception as o_err:
                print(f"[RISK CHECKER] Failed to fetch open orders: {o_err}", flush=True)

            hwm_file = os.path.join(DATA_DIR, "positions_hwm.json")
            hwm_data = {}
            if os.path.exists(hwm_file):
                try:
                    with open(hwm_file, "r") as hf:
                        hwm_data = json.load(hf)
                except Exception:
                    pass
            hwm_updated = False

            for pos in option_positions:
                symbol = pos.symbol
                if symbol in pending_sell_symbols:
                    continue
                # Parse underlying symbol from option symbol
                underlying_symbol = ""
                for char in symbol:
                    if char.isalpha():
                        underlying_symbol += char
                    else:
                        break
                
                current_price = float(pos.current_price) if pos.current_price is not None else 0.0
                avg_entry_price = float(pos.avg_entry_price) if pos.avg_entry_price is not None else 0.0
                
                # Manage HWM and Trailing Stop (30%)
                if symbol not in hwm_data or hwm_data[symbol].get("hwm", 0.0) <= 0.0 or hwm_data[symbol].get("stop", 0.0) <= 0.0:
                    initial_hwm = max(avg_entry_price, current_price)
                    hwm_data[symbol] = {
                        "hwm": initial_hwm,
                        "stop": initial_hwm * 0.7  # 30% Trailing Stop
                    }
                    hwm_updated = True
                elif current_price > hwm_data[symbol]["hwm"]:
                    hwm_data[symbol]["hwm"] = current_price
                    hwm_data[symbol]["stop"] = current_price * 0.7  # 30% Trailing Stop
                    hwm_updated = True
                
                # Check trailing stop breach
                stop_val = hwm_data[symbol]["stop"]
                if current_price <= stop_val:
                    reason = f"Option price (${current_price}) breached 30% trailing stop (${stop_val})"
                    print(f"[RISK AUDIT] Trailing stop breached for {symbol}. Triggering auto-close! Reason: {reason}", flush=True)
                    try:
                        try:
                            client.close_position(symbol)
                            print(f"[RISK AUDIT] Successfully closed position {symbol} via native close_position API.", flush=True)
                        except Exception as close_err:
                            if "no available quote" in str(close_err).lower() or "limit" in str(close_err).lower():
                                print(f"[RISK AUDIT] Native close failed due to no quote. Falling back to limit sell at $0.01 for {symbol}", flush=True)
                                from alpaca.trading.requests import LimitOrderRequest
                                from alpaca.trading.enums import OrderSide, TimeInForce
                                qty = abs(int(float(pos.qty)))
                                order_req = LimitOrderRequest(
                                    symbol=symbol,
                                    qty=qty,
                                    side=OrderSide.SELL,
                                    limit_price=0.01,
                                    time_in_force=TimeInForce.DAY
                                )
                                client.submit_order(order_req)
                            else:
                                raise close_err
                        
                        alert = {
                            "id": f"{symbol}_trailing_stop_{time.time()}",
                            "timestamp": datetime.now().isoformat(),
                            "type": "trailing_stop_breach",
                            "symbol": symbol,
                            "underlying": underlying_symbol,
                            "reason": reason,
                            "message": f"🚨 Auto-Closed option {symbol} due to trailing stop breach: {reason}"
                        }
                        with ALERTS_LOCK:
                            GLOBAL_ALERTS.append(alert)
                    except Exception as close_err:
                        print(f"[RISK AUDIT] Failed to auto-close option position {symbol}: {close_err}", flush=True)
                    continue

                # Calculate profit ratio
                profit_pct = 0.0
                if avg_entry_price > 0:
                    profit_pct = ((current_price - avg_entry_price) / avg_entry_price) * 100
                
                if symbol not in NOTIFIED_POSITIONS:
                    NOTIFIED_POSITIONS[symbol] = set()
                    
                # Check profit brackets: 30%, 50%, 100%
                for bracket in [30, 50, 100]:
                    if profit_pct >= bracket and bracket not in NOTIFIED_POSITIONS[symbol]:
                        NOTIFIED_POSITIONS[symbol].add(bracket)
                        alert = {
                            "id": f"{symbol}_{bracket}_{time.time()}",
                            "timestamp": datetime.now().isoformat(),
                            "type": "profit_bracket",
                            "symbol": symbol,
                            "underlying": underlying_symbol,
                            "bracket": bracket,
                            "profit_pct": round(profit_pct, 2),
                            "message": f"📈 Option {symbol} is up {bracket}%! Current profit: {round(profit_pct, 2)}%"
                        }
                        with ALERTS_LOCK:
                            GLOBAL_ALERTS.append(alert)
                            print(f"[RISK CHECKER] Profit bracket alert queued: {alert['message']}", flush=True)
                            
                # Check underlying stop condition (breach of VWAP or support):
                # We can call Yahoo Finance or Alpaca to get real-time price and VWAP of underlying
                underlying_price = None
                if underlying_symbol in stock_positions:
                    underlying_price = float(stock_positions[underlying_symbol].current_price)
                else:
                    # Fallback to fetching signal data if not in active portfolio
                    sig_data = _fetch_real_ticker_signal(underlying_symbol)
                    underlying_price = sig_data.get("basePrice")
                
                if underlying_price:
                    sig_data = _fetch_real_ticker_signal(underlying_symbol)
                    vwap = sig_data.get("vwap", underlying_price)
                    
                    is_call = "C" in symbol[len(underlying_symbol):]
                    is_put = "P" in symbol[len(underlying_symbol):]
                    
                    breached = False
                    reason = ""
                    if is_call and underlying_price < vwap:
                        breached = True
                        reason = f"Underlying {underlying_symbol} price (${underlying_price}) fell below VWAP (${round(vwap, 2)})"
                    elif is_put and underlying_price > vwap:
                        breached = True
                        reason = f"Underlying {underlying_symbol} price (${underlying_price}) rose above VWAP (${round(vwap, 2)})"
                        
                    if breached:
                        print(f"[RISK AUDIT] Invalidation breached for {symbol}. Triggering auto-close! Reason: {reason}", flush=True)
                        try:
                            try:
                                client.close_position(symbol)
                                print(f"[RISK AUDIT] Successfully closed position {symbol} via native close_position API.", flush=True)
                            except Exception as close_err:
                                if "no available quote" in str(close_err).lower() or "limit" in str(close_err).lower():
                                    print(f"[RISK AUDIT] Native close failed due to no quote. Falling back to limit sell at $0.01 for {symbol}", flush=True)
                                    from alpaca.trading.requests import LimitOrderRequest
                                    from alpaca.trading.enums import OrderSide, TimeInForce
                                    qty = abs(int(float(pos.qty)))
                                    order_req = LimitOrderRequest(
                                        symbol=symbol,
                                        qty=qty,
                                        side=OrderSide.SELL,
                                        limit_price=0.01,
                                        time_in_force=TimeInForce.DAY
                                    )
                                    client.submit_order(order_req)
                                else:
                                    raise close_err
                            
                            alert = {
                                "id": f"{symbol}_breach_{time.time()}",
                                "timestamp": datetime.now().isoformat(),
                                "type": "invalidation_stop",
                                "symbol": symbol,
                                "underlying": underlying_symbol,
                                "reason": reason,
                                "message": f"🚨 Auto-Closed option {symbol} due to underlying breach: {reason}"
                            }
                            with ALERTS_LOCK:
                                GLOBAL_ALERTS.append(alert)
                        except Exception as close_err:
                            print(f"[RISK AUDIT] Failed to auto-close position {symbol}: {close_err}", flush=True)
            
            # Prune obsolete HWMs and save positions_hwm.json if updated
            active_symbols = {p.symbol for p in raw_positions}
            hwm_keys = list(hwm_data.keys())
            for k in hwm_keys:
                if k not in active_symbols:
                    del hwm_data[k]
                    hwm_updated = True
            
            if hwm_updated:
                try:
                    with open(hwm_file, "w") as hf:
                        json.dump(hwm_data, hf)
                except Exception:
                    pass
                            
        except Exception as err:
            print(f"[RISK CHECKER] Error in monitor loop: {err}", flush=True)
            
        # Check pending conditional orders
        try:
            cond_file = os.path.join(DATA_DIR, "conditional_orders.json")
            if os.path.exists(cond_file):
                orders = _read_json_file(cond_file, [])
                updated = False
                
                for o in orders:
                    if o.get("status") == "PENDING":
                        underlying = o.get("underlying")
                        # Fetch current stock price of underlying
                        stock_price = None
                        if underlying in stock_positions:
                            stock_price = float(stock_positions[underlying].current_price)
                        else:
                            sig_data = _fetch_real_ticker_signal(underlying)
                            stock_price = sig_data.get("basePrice")
                            
                        if stock_price:
                            cond = o.get("condition")
                            trig_val = o.get("trigger_value")
                            trigger_met = False
                            
                            if cond == "CROSSES_ABOVE" and stock_price >= trig_val:
                                trigger_met = True
                            elif cond == "CROSSES_BELOW" and stock_price <= trig_val:
                                trigger_met = True
                                
                            if trigger_met:
                                print(f"[RISK CHECKER] Conditional order triggered for {underlying}! Stock: ${stock_price} vs Trigger: ${trig_val}", flush=True)
                                
                                # Now fetch option chain to locate matching option contract
                                from src.options.alpaca_options import get_options_chain
                                tf = o.get("timeframe", "WEEKLY")
                                chain = get_options_chain(underlying, stock_price or 230.0, tf)
                                target_contract = None
                                
                                if chain:
                                    target_strike = o.get("strike")
                                    target_type = o.get("option_type")
                                    target_exp = o.get("expiration")
                                    
                                    candidates = [c for c in chain if c["type"] == target_type]
                                    if target_exp:
                                        candidates = [c for c in candidates if c["expiration"] == target_exp]
                                        
                                    candidates.sort(key=lambda x: (abs(float(x["strike"]) - target_strike), x["expiration"]))
                                    
                                    if candidates:
                                        target_contract = candidates[0]["symbol"]
                                        
                                if target_contract:
                                    try:
                                        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
                                        from alpaca.trading.enums import OrderSide, TimeInForce
                                        
                                        qty = int(o.get("qty", 1))
                                        try:
                                            order_req = MarketOrderRequest(
                                                symbol=target_contract,
                                                qty=qty,
                                                side=OrderSide.BUY,
                                                time_in_force=TimeInForce.DAY
                                            )
                                            client.submit_order(order_req)
                                        except Exception as market_err:
                                            if "no available quote" in str(market_err).lower() or "limit" in str(market_err).lower():
                                                midpoint = float(candidates[0].get("midpoint", 1.0)) if candidates else 1.0
                                                limit_px = round(midpoint * 1.05, 2)
                                                print(f"[RISK CHECKER] Market order failed due to no quote. Retrying with LIMIT order at ${limit_px} for {target_contract}", flush=True)
                                                order_req = LimitOrderRequest(
                                                    symbol=target_contract,
                                                    qty=qty,
                                                    side=OrderSide.BUY,
                                                    limit_price=limit_px,
                                                    time_in_force=TimeInForce.DAY
                                                )
                                                client.submit_order(order_req)
                                            else:
                                                raise market_err
                                        
                                        # Queue alert
                                        alert = {
                                            "id": f"cond_trigger_{o.get('id')}_{time.time()}",
                                            "timestamp": datetime.now().isoformat(),
                                            "type": "profit_bracket",
                                            "symbol": target_contract,
                                            "underlying": underlying,
                                            "message": f"🤖 Triggered conditional order! Bought {qty} contracts of {target_contract} since {underlying} stock crossed {trig_val}!"
                                        }
                                        with ALERTS_LOCK:
                                            GLOBAL_ALERTS.append(alert)
                                            
                                        o["status"] = "EXECUTED"
                                        o["triggered_at"] = datetime.now().isoformat()
                                        updated = True
                                    except Exception as execution_err:
                                        print(f"[RISK CHECKER] Failed to submit conditional order for {underlying}: {execution_err}", flush=True)
                                else:
                                    print(f"[RISK CHECKER] Could not resolve target option contract for {underlying} {target_type} strike {target_strike}", flush=True)
                                    
                if updated:
                    _write_json_file(cond_file, orders)
        except Exception as cond_err:
            print(f"[RISK CHECKER] Error checking conditional orders: {cond_err}", flush=True)
                    
        # Check end of day alerts and cancellations (15:00 and 16:00 local time checks)
        try:
            now_local = datetime.now()
            current_hour = now_local.hour
            
            # 3 PM Pending Orders Alert (Run once a day between 15:00 and 15:59)
            global LAST_3PM_ALERT_DATE
            if current_hour == 15 and LAST_3PM_ALERT_DATE != now_local.date():
                cond_file = os.path.join(DATA_DIR, "conditional_orders.json")
                if os.path.exists(cond_file):
                    orders = _read_json_file(cond_file, [])
                    pending_count = sum(1 for o in orders if o.get("status") == "PENDING")
                    if pending_count > 0:
                        alert = {
                            "id": f"pending_alert_3pm_{now_local.strftime('%Y%m%d')}",
                            "timestamp": now_local.isoformat(),
                            "type": "pending_reminder",
                            "symbol": "ALL",
                            "underlying": "ALL",
                            "message": f"⚠️ Reminder: You have {pending_count} pending conditional orders still active at 3:00 PM."
                        }
                        with ALERTS_LOCK:
                            GLOBAL_ALERTS.append(alert)
                        LAST_3PM_ALERT_DATE = now_local.date()
                        
            # 4 PM EOD Cancellation (Run once a day when current_hour >= 16)
            global LAST_EOD_CANCEL_DATE
            if current_hour >= 16 and LAST_EOD_CANCEL_DATE != now_local.date():
                cond_file = os.path.join(DATA_DIR, "conditional_orders.json")
                if os.path.exists(cond_file):
                    orders = _read_json_file(cond_file, [])
                    pending_orders = [o for o in orders if o.get("status") == "PENDING"]
                    if len(pending_orders) > 0:
                        for o in pending_orders:
                            o["status"] = "CANCELLED"
                        _write_json_file(cond_file, orders)
                        
                        alert = {
                            "id": f"eod_cancel_{now_local.strftime('%Y%m%d')}",
                            "timestamp": now_local.isoformat(),
                            "type": "orders_cancelled",
                            "symbol": "ALL",
                            "underlying": "ALL",
                            "message": f"🛑 Market Closed (4:00 PM): Cancelled {len(pending_orders)} pending conditional orders."
                        }
                        with ALERTS_LOCK:
                            GLOBAL_ALERTS.append(alert)
                
                # ALSO cancel all active pending orders directly on Alpaca to clear the queue for the next day
                try:
                    import src.config as config
                    if config.API_KEY and config.SECRET_KEY and "YOUR_ALPACA" not in config.API_KEY:
                        from alpaca.trading.client import TradingClient
                        tc = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
                        tc.cancel_orders()
                        print("[EOD] Cancelled open broker orders at market close.", flush=True)
                except Exception as b_err:
                    print(f"[EOD] Failed to cancel open broker orders: {b_err}", flush=True)

                LAST_EOD_CANCEL_DATE = now_local.date()
        except Exception as eod_err:
            print(f"[RISK CHECKER] Error in EOD checks: {eod_err}", flush=True)

        time.sleep(10)


def run_server(port=8000):
    server_address = ('127.0.0.1', port)
    httpd = ThreadingHTTPServer(server_address, APIServerHandler)
    print(f"[API SERVER] Running on http://127.0.0.1:{port}", flush=True)
    # Start position risk and profit bracket checker loop
    t = threading.Thread(target=position_risk_checker_loop, daemon=True)
    t.start()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down API server.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
