"""
State Reconciliation Daemon/Worker

Periodic check to synchronize local state (positions.json) with Alpaca's ground-truth state.
"""

import os
import json
import logging
from datetime import datetime, timezone
from alpaca.trading.client import TradingClient
import src.config as config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StateReconciliation")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
POSITIONS_FILE = os.path.join(DATA_DIR, "positions.json")

def reconcile_positions(trading_client: TradingClient = None) -> dict:
    """
    Compares local active_positions in positions.json against Alpaca's active positions.
    Removes any locally-tracked positions that are no longer active on Alpaca.
    """
    logger.info("Starting broker state reconciliation...")
    
    if trading_client is None:
        trading_client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
        
    # 1. Fetch live positions from Alpaca
    try:
        alpaca_positions = trading_client.get_all_positions()
        alpaca_symbols = {p.symbol: p for p in alpaca_positions}
        logger.info(f"Fetched {len(alpaca_positions)} active positions from Alpaca: {list(alpaca_symbols.keys())}")
    except Exception as e:
        logger.error(f"Failed to fetch positions from Alpaca: {e}")
        return {"status": "error", "message": f"Alpaca fetch failed: {e}"}

    # 2. Load local positions
    if not os.path.exists(POSITIONS_FILE):
        logger.warning(f"Local positions file {POSITIONS_FILE} not found. Creating empty template.")
        local_data = {"active_positions": []}
    else:
        try:
            with open(POSITIONS_FILE, "r") as f:
                local_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse {POSITIONS_FILE}: {e}")
            return {"status": "error", "message": f"Local parse failed: {e}"}

    local_positions = local_data.get("active_positions", [])
    updated_local_positions = []
    reconciled_count = 0
    removed_positions = []

    # 3. Check each local position against Alpaca positions
    for pos in local_positions:
        symbol = pos.get("symbol")
        if symbol in alpaca_symbols:
            # Match found; keep local position
            updated_local_positions.append(pos)
        else:
            # No match on Alpaca; position was closed/liquidated manually or externally
            logger.warning(f"Reconciliation: Local position {symbol} not found on Alpaca. Removing from local state.")
            removed_positions.append(symbol)
            reconciled_count += 1

    # 4. Save updated positions if any changes
    if reconciled_count > 0:
        local_data["active_positions"] = updated_local_positions
        try:
            with open(POSITIONS_FILE, "w") as f:
                json.dump(local_data, f, indent=2)
            logger.info(f"Reconciliation complete. Removed {reconciled_count} obsolete positions.")
            
            # Log to journal reflection/trade log if applicable
            trade_log_path = os.path.join(DATA_DIR, "trade_history.json")
            if os.path.exists(trade_log_path):
                try:
                    with open(trade_log_path, "r") as f:
                        trades = json.load(f)
                    if not isinstance(trades, list):
                        trades = [trades]
                except Exception:
                    trades = []
                    
                for sym in removed_positions:
                    trades.append({
                        "symbol": sym,
                        "action": "RECONCILED_CLOSE",
                        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                        "notes": "Position removed by automated State Reconciliation Daemon."
                    })
                    
                with open(trade_log_path, "w") as f:
                    json.dump(trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write reconciled positions to disk: {e}")
            return {"status": "error", "message": f"Write failed: {e}"}
    else:
        logger.info("Reconciliation complete. Local state is fully in sync with Alpaca.")

    return {
        "status": "success",
        "reconciled_removed": removed_positions,
        "active_positions_count": len(updated_local_positions)
    }

if __name__ == "__main__":
    reconcile_positions()
