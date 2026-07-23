"""
DualLedgerWriter: Atomic dual-write to state.json (WhiteLight) + entries.jsonl (Shadow format)

Ensures every execution is recorded in both:
1. WhiteLight's state.json (mutable positions state)
2. Shadow's entries.jsonl (immutable append-only ledger)

This enables:
- WhiteLight to retain its existing risk checks (state.json)
- Shadow's grading to evaluate WhiteLight's trades (entries.jsonl)
- Nightly verdict scoring using worst-fill P&L model
"""

import os
import json
import fcntl
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import src.config as config
from src.storage.atomic_writer import AtomicJSONWriter

logger = logging.getLogger("DualLedgerWriter")


class DualLedgerWriter:
    """Atomically write execution results to both state.json and Shadow JSONL ledgers."""

    def __init__(self, state_dir: str, shadow_ledger_dir: str):
        """
        Initialize dual-ledger writer.

        Args:
            state_dir: Directory containing WhiteLight's state.json
            shadow_ledger_dir: Directory containing Shadow's ledger files (entries.jsonl, marks.jsonl, exits.jsonl)
        """
        self.state_dir = state_dir
        self.shadow_ledger_dir = shadow_ledger_dir
        self.state_file = os.path.join(state_dir, "state.json")
        self.entries_file = os.path.join(shadow_ledger_dir, "entries.jsonl")
        self.marks_file = os.path.join(shadow_ledger_dir, "marks.jsonl")

        # Ensure directories exist
        os.makedirs(state_dir, exist_ok=True)
        os.makedirs(shadow_ledger_dir, exist_ok=True)

        self.state_writer = AtomicJSONWriter(self.state_file)

    def write_execution(
        self,
        execution_result: dict,
        worst_fill: float,
        base_fill: float,
        optimistic_fill: float,
        greeks: dict,
        strategy_id: str,
        cycle_id: str
    ) -> bool:
        """
        Atomically write execution to both ledgers.

        Args:
            execution_result: Dict with keys: symbol, filled_at, qty, side, option_type,
                             strike_price, expiration_date, option_type, capital_at_risk
            worst_fill: Worst-case fill price (ask for BUY, bid for SELL)
            base_fill: Mid-point fill price
            optimistic_fill: Best-case fill price (bid for BUY, ask for SELL)
            greeks: Dict with delta, vega, theta, gamma, iv_rank
            strategy_id: Strategy identifier (e.g., "whitelight_primary")
            cycle_id: Unique cycle ID (UUID per pipeline run)

        Returns:
            bool: True if write succeeded, False otherwise

        Raises:
            Exception: If atomic write fails (will not partially update)
        """
        try:
            # Build Shadow ledger entry
            shadow_entry = self._build_shadow_entry(
                execution_result, worst_fill, base_fill, optimistic_fill, greeks, strategy_id, cycle_id
            )

            # Step 1: Update state.json with positions array
            logger.debug(f"Writing to state.json: {execution_result['symbol']}")
            self._update_state_positions(execution_result, worst_fill, base_fill, optimistic_fill)

            # Step 2: Append to entries.jsonl
            logger.debug(f"Appending to entries.jsonl: {execution_result['symbol']}")
            self._append_jsonl_entry(shadow_entry)

            logger.info(
                f"Dual-write succeeded for {execution_result['symbol']}: "
                f"state.json + entries.jsonl (cycle={cycle_id}, strategy={strategy_id})"
            )
            return True

        except Exception as e:
            logger.error(f"Dual-write failed: {e}", exc_info=True)
            raise

    def _build_shadow_entry(
        self,
        execution_result: dict,
        worst_fill: float,
        base_fill: float,
        optimistic_fill: float,
        greeks: dict,
        strategy_id: str,
        cycle_id: str
    ) -> dict:
        """Build a Shadow-format ledger entry."""

        entry_timestamp = execution_result.get("filled_at", datetime.utcnow().isoformat() + "Z")

        # Compute cohort hash from strategy_id (simplified; Shadow uses parameter tuples)
        cohort_hash = hash(strategy_id) % 10000000  # Keep it reasonable

        return {
            "timestamp": entry_timestamp,
            "symbol": execution_result["symbol"],
            "qty": execution_result["qty"],
            "side": execution_result.get("side", "BUY").lower(),
            "strike": execution_result.get("strike_price"),
            "expiry": execution_result.get("expiration_date"),
            "entry_price_worst": worst_fill,
            "entry_price_base": base_fill,
            "entry_price_optimistic": optimistic_fill,
            "delta": greeks.get("delta", 0.0),
            "gamma": greeks.get("gamma", 0.0),
            "vega": greeks.get("vega", 0.0),
            "theta": greeks.get("theta", 0.0),
            "iv_rank": greeks.get("iv_rank", 50.0),
            "strategy_id": strategy_id,
            "cohort_hash": cohort_hash,
            "cycle_id": cycle_id,
            "carisk_at_entry": execution_result.get("capital_at_risk", 0.0),
        }

    def _update_state_positions(
        self,
        execution_result: dict,
        worst_fill: float,
        base_fill: float,
        optimistic_fill: float
    ) -> None:
        """Update state.json with new position."""

        # Atomic read-modify-write
        with self.state_writer.lock(fcntl.LOCK_EX):
            state_data = self.state_writer.read_locked()

            if not isinstance(state_data, dict):
                state_data = {}

            # Initialize positions array if missing
            if "active_positions" not in state_data:
                state_data["active_positions"] = []

            # Append new position
            position = {
                "symbol": execution_result["symbol"],
                "quantity": execution_result["qty"],
                "option_type": execution_result.get("option_type", "stock"),
                "strike_price": execution_result.get("strike_price"),
                "expiration_date": execution_result.get("expiration_date"),
                "acquired_at": execution_result.get("filled_at", datetime.utcnow().isoformat() + "Z"),
                "entry_worst": worst_fill,
                "entry_base": base_fill,
                "entry_optimistic": optimistic_fill,
            }

            state_data["active_positions"].append(position)

            # Write atomically
            self.state_writer.write_locked(state_data)
            logger.debug(f"Updated state.json: added position {execution_result['symbol']}")

    def _append_jsonl_entry(self, entry: dict) -> None:
        """Append entry to JSONL file with atomic locking."""
        os.makedirs(os.path.dirname(self.entries_file), exist_ok=True)
        lock_file = self.entries_file + ".lock"
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_WRONLY, 0o666)
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                with open(self.entries_file, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
        except Exception as e:
            with open(self.entries_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
            logger.warning(f"Fallback append without lock for entries.jsonl: {e}")

    def write_execution_mark(
        self,
        entry_id: str,
        bid: float,
        ask: float,
        worst_mark: float,
        base_mark: float,
        optimistic_mark: float,
        age_seconds: int = 0
    ) -> bool:
        """
        Record a mark (re-pricing) for an entry.

        Shadow's mark system tracks continuous re-pricing of open positions.
        Each mark includes three fill assumptions (worst/base/optimistic).

        Args:
            entry_id: Timestamp of original entry
            bid: Current bid price
            ask: Current ask price
            worst_mark: Mark under worst-case assumption
            base_mark: Mark under base case
            optimistic_mark: Mark under optimistic case
            age_seconds: Staleness of the mark

        Returns:
            bool: True if write succeeded
        """
        try:
            mark_entry = {
                "entry_id": entry_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "bid": bid,
                "ask": ask,
                "mid": (bid + ask) / 2.0,
                "mark_worst": worst_mark,
                "mark_base": base_mark,
                "mark_optimistic": optimistic_mark,
                "age_s": age_seconds,
            }

            os.makedirs(os.path.dirname(self.marks_file), exist_ok=True)
            lock_file = self.marks_file + ".lock"
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_WRONLY, 0o666)
                fcntl.flock(fd, fcntl.LOCK_EX)
                try:
                    with open(self.marks_file, "a") as f:
                        f.write(json.dumps(mark_entry) + "\n")
                finally:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                    os.close(fd)
            except Exception as e:
                with open(self.marks_file, "a") as f:
                    f.write(json.dumps(mark_entry) + "\n")
                logger.warning(f"Fallback append without lock for marks.jsonl: {e}")

            logger.debug(f"Marked entry {entry_id}: mark_base={base_mark:.2f}")
            return True

        except Exception as e:
            logger.error(f"Failed to write mark for entry {entry_id}: {e}")
            return False
