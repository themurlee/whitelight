import os
import tempfile
import pytest
from datetime import datetime, timezone
from src.state.execution_journal import ExecutionJournal, ExecutionState

def test_idempotent_execution_journal():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        filepath = tmp.name

    try:
        journal = ExecutionJournal(filepath=filepath)
        
        cycle_id = "test-cycle-uuid-111"
        ticker = "SPY"
        
        assert journal.was_executed_this_cycle(ticker, cycle_id) is False
        
        state = ExecutionState(
            cycle_id=cycle_id,
            timestamp=datetime.now(timezone.utc),
            ticker=ticker,
            action="BUY",
            qty=10,
            order_id="order-xyz-123",
            status="filled"
        )
        journal.log_execution(state)
        
        assert journal.was_executed_this_cycle(ticker, cycle_id) is True
        assert journal.was_executed_this_cycle("AAPL", cycle_id) is False
        assert journal.was_executed_this_cycle(ticker, "test-cycle-uuid-222") is False

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
        lock_file = filepath + ".lock"
        if os.path.exists(lock_file):
            os.remove(lock_file)
