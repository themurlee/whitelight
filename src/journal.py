"""
WhiteLight Systematic Trading & Analysis Pipeline - Journaling & Logging
Manages structured JSON logs for trades and error events, and auto-generates
narrative Markdown reflection templates for qualitative human review.
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime

DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data")
)
JOURNAL_DIR = os.path.join(DATA_DIR, "journal")
TRADE_LOG_FILE = os.path.join(DATA_DIR, "trade_history.json")
ERROR_LOG_FILE = os.path.join(DATA_DIR, "system_errors.json")
TRANSITION_LOG_FILE = os.path.join(DATA_DIR, "state_transitions.json")


def _ensure_directories():
    """Ensure data and journal subdirectories exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(JOURNAL_DIR, exist_ok=True)


from src.storage.atomic_writer import AtomicJSONWriter

import fcntl

def _append_json_log(filepath: str, entry: Dict[str, Any]):
    """Safely append an entry to a local JSON list log in a single transaction."""
    _ensure_directories()
    
    writer = AtomicJSONWriter(filepath)
    with writer.lock(fcntl.LOCK_EX):
        data = []
        try:
            raw_data = writer.read_locked()
            if isinstance(raw_data, list):
                data = raw_data
            elif raw_data:
                data = [raw_data]
        except Exception:
            data = []

        data.append(entry)
        writer.write_locked(data)


def log_trade(action: str, symbol: str, quantity: int, price: float, details: Optional[Dict] = None):
    """
    Log a completed trade transaction.
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action.upper(),  # BUY, SELL, FLATTEN, PURGE
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
        "details": details or {}
    }
    _append_json_log(TRADE_LOG_FILE, entry)


def log_error(message: str, traceback_str: str = "", context: Optional[Dict] = None):
    """
    Log a system execution error or exception.
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "message": message,
        "traceback": traceback_str,
        "context": context or {}
    }
    _append_json_log(ERROR_LOG_FILE, entry)


def log_state_transition(from_state: str, to_state: str, reason: str):
    """
    Log systematic state updates, such as circuit breaker lockdowns or overrides.
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "from_state": from_state,
        "to_state": to_state,
        "reason": reason
    }
    _append_json_log(TRANSITION_LOG_FILE, entry)


def generate_daily_journal_template(date_str: Optional[str] = None) -> str:
    """
    Auto-generates a clean markdown template for daily qualitative reflections
    if it does not already exist. Returns the path of the generated file.
    """
    _ensure_directories()
    
    if not date_str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    filename = f"{date_str}_reflection.md"
    filepath = os.path.join(JOURNAL_DIR, filename)

    if os.path.exists(filepath):
        return filepath  # Prevent overwriting existing reflections

    template_content = f"""# WhiteLight Systematic Trading Journal - {date_str}

## 1. Market Context & Macro Observations
*Insert details regarding broad market index behaviors, macro events, or notable news here.*

## 2. Quantitative Signal Matrix Review
- **Tracked Tickers**: 
- **EMA Trend Alignment**: 
- **MACD Divergences**: 
- **VWAP Deviations**: 

## 3. Position Details & Risk Metrics
- **Active Exposure**: 
- **7-day Rolling Drawdown**: 
- **Circuit Breaker Status**: 

## 4. Narrative Reflections & Qualitative Logs
- **System Behavior Notes**: 
- **Emotional/Execution Control Notes**: 
- **Hypotheses to Validate**: 

## 5. Action Items for Next Session
- [ ] Verify circuit breaker status and state logs.
- [ ] Review option Greeks decay (theta, delta).
- [ ] Adjust position limits if necessary.
"""

    with open(filepath, "w") as f:
        f.write(template_content)

    return filepath
