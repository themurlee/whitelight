"""
Phase 1 Test Suite: Dual-Ledger Writer and Shadow Integration

Tests:
1. Dual-write creates valid entries.jsonl entries
2. Atomic writes under concurrent load (10+ threads)
3. Grader computes e-process wealth correctly
4. State.json and entries.jsonl remain in sync
5. Nightly grader completes without errors
"""

import pytest
import json
import os
import tempfile
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from src.execution.dual_ledger_writer import DualLedgerWriter
from src.integration.shadow_ledger_reader import ShadowLedgerReader
from src.integration.shadow_grader_wrapper import ShadowGraderWrapper


@pytest.fixture
def temp_ledger_dir():
    """Create temporary directory for ledger files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestDualLedgerWriter:
    """Tests for DualLedgerWriter component."""

    def test_dual_write_creates_entries_jsonl(self, temp_ledger_dir):
        """Verify dual-write creates valid JSONL entries."""
        state_dir = os.path.join(temp_ledger_dir, "state")
        shadow_dir = os.path.join(temp_ledger_dir, "shadow")

        writer = DualLedgerWriter(state_dir, shadow_dir)

        execution = {
            "symbol": "SPY",
            "filled_at": "2026-07-23T15:30:00Z",
            "qty": 10,
            "side": "BUY",
            "option_type": "stock"
        }

        success = writer.write_execution(
            execution_result=execution,
            worst_fill=450.50,
            base_fill=450.25,
            optimistic_fill=450.00,
            greeks={"delta": 1.0, "vega": 0.0, "theta": 0.0},
            strategy_id="test_strategy",
            cycle_id="test-cycle-123"
        )

        assert success, "Dual-write should succeed"

        # Verify entries.jsonl was created
        entries_file = os.path.join(shadow_dir, "entries.jsonl")
        assert os.path.exists(entries_file), "entries.jsonl should be created"

        # Verify entries are valid JSON
        with open(entries_file) as f:
            entry = json.loads(f.readline())
            assert entry["symbol"] == "SPY"
            assert entry["entry_price_worst"] == 450.50
            assert entry["entry_price_base"] == 450.25
            assert entry["strategy_id"] == "test_strategy"
            assert entry["cycle_id"] == "test-cycle-123"

    def test_dual_write_updates_state_positions(self, temp_ledger_dir):
        """Verify state.json positions array is updated."""
        state_dir = os.path.join(temp_ledger_dir, "state")
        shadow_dir = os.path.join(temp_ledger_dir, "shadow")

        writer = DualLedgerWriter(state_dir, shadow_dir)

        execution = {
            "symbol": "SPY",
            "filled_at": "2026-07-23T15:30:00Z",
            "qty": 10,
            "side": "BUY",
            "option_type": "stock"
        }

        writer.write_execution(
            execution_result=execution,
            worst_fill=450.50,
            base_fill=450.25,
            optimistic_fill=450.00,
            greeks={},
            strategy_id="test",
            cycle_id="test-123"
        )

        # Verify state.json was updated
        state_file = os.path.join(state_dir, "state.json")
        assert os.path.exists(state_file), "state.json should be created"

        with open(state_file) as f:
            state = json.load(f)
            assert "active_positions" in state
            assert len(state["active_positions"]) == 1
            assert state["active_positions"][0]["symbol"] == "SPY"
            assert state["active_positions"][0]["quantity"] == 10

    def test_concurrent_writes_maintain_integrity(self, temp_ledger_dir):
        """Verify atomic writes under concurrent load."""
        state_dir = os.path.join(temp_ledger_dir, "state")
        shadow_dir = os.path.join(temp_ledger_dir, "shadow")

        writer = DualLedgerWriter(state_dir, shadow_dir)

        def write_order(i):
            execution = {
                "symbol": f"SYM{i}",
                "filled_at": f"2026-07-23T15:30:{i:02d}Z",
                "qty": i,
                "side": "BUY"
            }

            return writer.write_execution(
                execution_result=execution,
                worst_fill=100.0 + i,
                base_fill=100.0 + i,
                optimistic_fill=100.0 + i,
                greeks={},
                strategy_id="concurrent_test",
                cycle_id=f"cycle-{i}"
            )

        # Write 10 orders concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(write_order, range(10)))

        assert all(results), "All concurrent writes should succeed"

        # Verify all entries in JSONL
        entries_file = os.path.join(shadow_dir, "entries.jsonl")
        with open(entries_file) as f:
            entries = [json.loads(line) for line in f]
            assert len(entries) == 10, "Should have 10 entries"

    def test_mark_write_appends_to_marks_jsonl(self, temp_ledger_dir):
        """Verify write_execution_mark appends to marks.jsonl."""
        state_dir = os.path.join(temp_ledger_dir, "state")
        shadow_dir = os.path.join(temp_ledger_dir, "shadow")

        writer = DualLedgerWriter(state_dir, shadow_dir)

        success = writer.write_execution_mark(
            entry_id="2026-07-23T15:30:00Z",
            bid=450.00,
            ask=450.50,
            worst_mark=450.50,
            base_mark=450.25,
            optimistic_mark=450.00,
            age_seconds=30
        )

        assert success, "Mark write should succeed"

        marks_file = os.path.join(shadow_dir, "marks.jsonl")
        assert os.path.exists(marks_file), "marks.jsonl should be created"

        with open(marks_file) as f:
            mark = json.loads(f.readline())
            assert mark["entry_id"] == "2026-07-23T15:30:00Z"
            assert mark["mark_base"] == 450.25


class TestShadowLedgerReader:
    """Tests for ShadowLedgerReader component."""

    def test_load_entries_filters_by_strategy(self, temp_ledger_dir):
        """Verify entries loading and strategy filtering."""
        shadow_dir = os.path.join(temp_ledger_dir, "shadow")

        # Create sample entries.jsonl
        entries_file = os.path.join(shadow_dir, "entries.jsonl")
        os.makedirs(shadow_dir, exist_ok=True)

        entries = [
            {"timestamp": "2026-07-23T15:30:00Z", "symbol": "SPY", "strategy_id": "test_s1", "qty": 10},
            {"timestamp": "2026-07-23T15:31:00Z", "symbol": "QQQ", "strategy_id": "test_s2", "qty": 20},
            {"timestamp": "2026-07-23T15:32:00Z", "symbol": "IWM", "strategy_id": "test_s1", "qty": 30},
        ]

        with open(entries_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        reader = ShadowLedgerReader(ledger_dir=shadow_dir)

        # Load all entries
        all_entries = reader.load_entries()
        assert len(all_entries) == 3

        # Load filtered by strategy
        s1_entries = reader.load_entries(strategy_id="test_s1")
        assert len(s1_entries) == 2
        assert all(e["strategy_id"] == "test_s1" for e in s1_entries)

    def test_compute_drawdown_by_worst_fill(self, temp_ledger_dir):
        """Verify drawdown calculation."""
        shadow_dir = os.path.join(temp_ledger_dir, "shadow")
        os.makedirs(shadow_dir, exist_ok=True)

        # Create sample entries and marks
        entries_file = os.path.join(shadow_dir, "entries.jsonl")
        marks_file = os.path.join(shadow_dir, "marks.jsonl")

        entry_ts = "2026-07-23T15:30:00Z"

        with open(entries_file, "w") as f:
            f.write(json.dumps({
                "timestamp": entry_ts,
                "symbol": "SPY",
                "qty": 10,
                "entry_price_worst": 450.00,
                "strategy_id": "test"
            }) + "\n")

        with open(marks_file, "w") as f:
            # Mark with 5% loss
            f.write(json.dumps({
                "entry_id": entry_ts,
                "mark_worst": 427.50,  # 5% lower than entry
                "timestamp": "2026-07-23T16:00:00Z"
            }) + "\n")

        reader = ShadowLedgerReader(ledger_dir=shadow_dir)
        entries = reader.load_entries()

        drawdown = reader.compute_drawdown_by_worst_fill(entries)
        assert abs(drawdown - 5.0) < 0.1, f"Drawdown should be ~5%, got {drawdown}"


class TestShadowGraderWrapper:
    """Tests for ShadowGraderWrapper grading logic."""

    def test_grader_verdict_unproven_insufficient_trades(self, temp_ledger_dir):
        """Verify UNPROVEN verdict with insufficient trades."""
        shadow_dir = os.path.join(temp_ledger_dir, "shadow")
        os.makedirs(shadow_dir, exist_ok=True)

        # Create 10 entries (< 25 minimum for PROVEN)
        entries_file = os.path.join(shadow_dir, "entries.jsonl")

        with open(entries_file, "w") as f:
            for i in range(10):
                f.write(json.dumps({
                    "timestamp": f"2026-07-23T15:{i:02d}:00Z",
                    "symbol": "SPY",
                    "qty": 10,
                    "entry_price_worst": 450.00,
                    "strategy_id": "test"
                }) + "\n")

        grader = ShadowGraderWrapper(whitelight_data_dir=shadow_dir)
        result = grader.grade_whitelight_strategy("test")

        assert result["verdict"] == "UNPROVEN", "Should be UNPROVEN with < 25 trades"
        assert result["n_trades"] == 10

    def test_grader_computes_wealth_correctly(self, temp_ledger_dir):
        """Verify wealth calculation."""
        shadow_dir = os.path.join(temp_ledger_dir, "shadow")
        os.makedirs(shadow_dir, exist_ok=True)

        entries_file = os.path.join(shadow_dir, "entries.jsonl")
        marks_file = os.path.join(shadow_dir, "marks.jsonl")

        # Create profitable trades
        with open(entries_file, "w") as f:
            for i in range(30):  # 30 trades for statistical significance
                ts = f"2026-07-23T15:{i:02d}:00Z"
                f.write(json.dumps({
                    "timestamp": ts,
                    "symbol": "SPY",
                    "qty": 10,
                    "entry_price_worst": 450.00,
                    "entry_price_base": 450.00,
                    "strategy_id": "test"
                }) + "\n")

        with open(marks_file, "w") as f:
            for i in range(30):
                ts = f"2026-07-23T15:{i:02d}:00Z"
                # Profitable: exit higher than entry
                f.write(json.dumps({
                    "entry_id": ts,
                    "mark_worst": 460.00,  # +$100 profit per position
                    "mark_base": 460.00,
                    "timestamp": f"2026-07-23T16:{i:02d}:00Z"
                }) + "\n")

        grader = ShadowGraderWrapper(whitelight_data_dir=shadow_dir)
        result = grader.grade_whitelight_strategy("test")

        assert result["n_trades"] == 30
        assert result["wealth"] > 0, "Profitable strategy should have positive wealth"
        assert result["win_rate"] > 0.5, "Should have > 50% win rate"

    def test_grader_saves_scorecard(self, temp_ledger_dir):
        """Verify scorecard JSON is saved correctly."""
        shadow_dir = os.path.join(temp_ledger_dir, "shadow")

        grader = ShadowGraderWrapper(whitelight_data_dir=shadow_dir)

        grade_result = {
            "strategy_id": "test",
            "verdict": "PROVEN",
            "wealth": 25.5,
            "n_trades": 50,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        scorecard_path = os.path.join(shadow_dir, "scorecard.json")
        success = grader.save_scorecard(grade_result, scorecard_path)

        assert success, "Scorecard save should succeed"
        assert os.path.exists(scorecard_path), "Scorecard file should be created"

        with open(scorecard_path) as f:
            saved = json.load(f)
            assert saved["verdict"] == "PROVEN"
            assert saved["wealth"] == 25.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
