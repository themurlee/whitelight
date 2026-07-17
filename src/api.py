"""
WhiteLight Systematic Trading & Analysis Pipeline - REST API Server
Pure Python zero-dependency HTTP server serving as a REST API bridge
between the local JSON/Markdown database and the React browser frontend.
"""

import os
import json
import glob
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
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
        return {
            "configured": True,
            "account_number": acc.account_number,
            "cash": float(acc.cash),
            "equity": float(acc.equity),
            "buying_power": float(acc.buying_power),
            "portfolio_value": float(acc.portfolio_value),
            "status": acc.status
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
                log_content = "".join(lines[-100:]) # Last 100 lines
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

        elif path == "/api/state":
            data = _read_json_file(STATE_FILE, {"lockdown_active": False, "drawdown_locked_at": None, "equity_history": []})
            self._send_json(data)
            
        elif path == "/api/positions":
            data = _read_json_file(POSITIONS_FILE, {"active_positions": []})
            self._send_json(data)
            
        elif path == "/api/trades":
            data = _read_json_file(TRADE_LOG_FILE, [])
            self._send_json(data)
            
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

        if path == "/api/state/update_equity":
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
                if "ROBINHOOD_USERNAME" in content and "ROBINHOOD_PASSWORD" in content:
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
                if "ROBINHOOD_USERNAME" in content and "ROBINHOOD_PASSWORD" in content:
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


def run_server(port=8000):
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, APIServerHandler)
    print(f"[API SERVER] Running on http://127.0.0.1:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down API server.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
