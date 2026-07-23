import os
import json
import uuid
import fcntl
from dataclasses import dataclass
from datetime import datetime, timezone
import src.config as config
from src.storage.atomic_writer import AtomicJSONWriter

@dataclass
class ExecutionState:
    cycle_id: str
    timestamp: datetime
    ticker: str
    action: str
    qty: int
    order_id: str
    status: str
    fill_price: float = None

class ExecutionJournal:
    def __init__(self, filepath: str = None):
        self.filepath = filepath or os.path.join(config.DATA_DIR, "execution_journal.json")
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        # Create empty list if file doesn't exist
        if not os.path.exists(self.filepath):
            AtomicJSONWriter(self.filepath).write([])

    def load(self) -> list:
        """Load journal entries from disk."""
        try:
            data = AtomicJSONWriter(self.filepath).read()
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def was_executed_this_cycle(self, ticker: str, cycle_id: str) -> bool:
        """Check if ticker was already traded in the current pipeline run cycle."""
        records = self.load()
        for r in records:
            if r.get("cycle_id") == cycle_id and r.get("ticker") == ticker:
                return True
        return False

    def log_execution(self, state: ExecutionState):
        """Append execution state entry transactionally with atomic write locks."""
        writer = AtomicJSONWriter(self.filepath)
        with writer.lock(fcntl.LOCK_EX):
            records = writer.read_locked()
            if not isinstance(records, list):
                records = []
            
            entry = {
                "cycle_id": state.cycle_id,
                "timestamp": state.timestamp.isoformat() if hasattr(state.timestamp, "isoformat") else str(state.timestamp),
                "ticker": state.ticker,
                "action": state.action,
                "qty": state.qty,
                "order_id": state.order_id,
                "status": state.status,
                "fill_price": state.fill_price
            }
            records.append(entry)
            writer.write_locked(records)
