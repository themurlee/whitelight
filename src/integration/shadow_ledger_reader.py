"""
ShadowLedgerReader: Read and analyze Shadow's append-only JSONL ledgers

Shadow maintains three ledger files:
- entries.jsonl: Initial position records (immutable)
- marks.jsonl: Continuous re-pricing updates
- exits.jsonl: Position closure records

This reader enables WhiteLight to:
1. Consume Shadow's ledger format
2. Compute worst-fill drawdown
3. Track mark-to-market values
4. Analyze closed positions
"""

import os
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger("ShadowLedgerReader")


class ShadowLedgerReader:
    """Read Shadow's append-only JSONL ledgers."""

    def __init__(self, ledger_dir: str):
        """
        Initialize ledger reader.

        Args:
            ledger_dir: Directory containing entries.jsonl, marks.jsonl, exits.jsonl
        """
        self.ledger_dir = ledger_dir
        self.entries_file = os.path.join(ledger_dir, "entries.jsonl")
        self.marks_file = os.path.join(ledger_dir, "marks.jsonl")
        self.exits_file = os.path.join(ledger_dir, "exits.jsonl")

    def load_entries(self, strategy_id: Optional[str] = None) -> List[Dict]:
        """
        Load all entries from entries.jsonl, optionally filtered by strategy.

        Args:
            strategy_id: If provided, only return entries matching this strategy

        Returns:
            List of entry dicts
        """
        entries = []

        if not os.path.exists(self.entries_file):
            logger.warning(f"entries.jsonl not found at {self.entries_file}")
            return entries

        try:
            with open(self.entries_file, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)

                        # Filter by strategy if provided
                        if strategy_id is None or entry.get("strategy_id") == strategy_id:
                            entries.append(entry)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Malformed JSON at entries.jsonl:{line_num}: {e}")
                        continue

            logger.info(f"Loaded {len(entries)} entries from ledger" + (f" (strategy={strategy_id})" if strategy_id else ""))
            return entries

        except Exception as e:
            logger.error(f"Failed to read entries.jsonl: {e}")
            return entries

    def load_all_marks(self) -> List[Dict]:
        """Load all mark records from marks.jsonl."""
        marks = []

        if not os.path.exists(self.marks_file):
            logger.debug(f"marks.jsonl not found at {self.marks_file}")
            return marks

        try:
            with open(self.marks_file, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        mark = json.loads(line)
                        marks.append(mark)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Malformed JSON at marks.jsonl:{line_num}: {e}")
                        continue

            logger.info(f"Loaded {len(marks)} marks from ledger")
            return marks

        except Exception as e:
            logger.error(f"Failed to read marks.jsonl: {e}")
            return marks

    def load_latest_mark_for_entry(self, entry_id: str) -> Optional[Dict]:
        """
        Load the most recent mark for an entry.

        Args:
            entry_id: Timestamp of the entry

        Returns:
            Most recent mark dict, or None if not found
        """
        marks = self.load_all_marks()

        # Filter by entry_id and sort by timestamp
        matching_marks = [m for m in marks if m.get("entry_id") == entry_id]

        if not matching_marks:
            return None

        # Sort by timestamp descending to get latest
        matching_marks.sort(key=lambda m: m.get("timestamp", ""), reverse=True)

        return matching_marks[0]

    def load_marks_for_entry(self, entry_id: str) -> List[Dict]:
        """
        Load all marks for an entry (chronologically ordered).

        Args:
            entry_id: Timestamp of the entry

        Returns:
            List of mark dicts
        """
        marks = self.load_all_marks()

        # Filter and sort
        matching_marks = [m for m in marks if m.get("entry_id") == entry_id]
        matching_marks.sort(key=lambda m: m.get("timestamp", ""))

        return matching_marks

    def load_exits(self) -> List[Dict]:
        """Load all exit records from exits.jsonl."""
        exits = []

        if not os.path.exists(self.exits_file):
            logger.debug(f"exits.jsonl not found at {self.exits_file}")
            return exits

        try:
            with open(self.exits_file, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        exit_record = json.loads(line)
                        exits.append(exit_record)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Malformed JSON at exits.jsonl:{line_num}: {e}")
                        continue

            logger.info(f"Loaded {len(exits)} exit records from ledger")
            return exits

        except Exception as e:
            logger.error(f"Failed to read exits.jsonl: {e}")
            return exits

    def compute_drawdown_by_worst_fill(self, entries: List[Dict]) -> float:
        """
        Compute portfolio drawdown using worst-fill assumption.

        Formula:
            peak_val = sum(entry_price_worst * qty for all entries)
            current_val = sum(mark_worst * qty for all entries, using latest mark)
            drawdown_pct = (peak_val - current_val) / peak_val * 100

        Args:
            entries: List of entry dicts

        Returns:
            Percentage drawdown (0-100)
        """
        if not entries:
            return 0.0

        # Compute peak value (sum of worst-fill entry prices)
        peak_val = 0.0
        for entry in entries:
            peak_val += entry.get("entry_price_worst", 0.0) * entry.get("qty", 0)

        # Compute current value (sum of worst-fill marks)
        current_val = 0.0
        for entry in entries:
            entry_id = entry.get("timestamp")
            mark = self.load_latest_mark_for_entry(entry_id)

            if mark:
                current_val += mark.get("mark_worst", entry.get("entry_price_worst", 0.0)) * entry.get("qty", 0)
            else:
                # No mark yet; assume current = entry
                current_val += entry.get("entry_price_worst", 0.0) * entry.get("qty", 0)

        if peak_val <= 0:
            return 0.0

        drawdown = (peak_val - current_val) / peak_val * 100.0
        logger.info(f"Drawdown (worst-fill): {drawdown:.2f}% (peak=${peak_val:.2f}, current=${current_val:.2f})")

        return drawdown

    def compute_pnl_stats(self, entries: List[Dict], fill_assumption: str = "worst") -> Dict:
        """
        Compute P&L statistics across entries.

        Args:
            entries: List of entry dicts
            fill_assumption: "worst", "base", or "optimistic"

        Returns:
            Dict with keys: total_pnl, n_trades, n_winners, n_losers, win_rate,
                           avg_win, avg_loss, win_loss_ratio, stddev_pnl
        """
        pnl_list = []

        for entry in entries:
            entry_id = entry.get("timestamp")
            mark = self.load_latest_mark_for_entry(entry_id)

            if not mark:
                # Position still open; use current mark value as 0 (unrealized)
                continue

            # P&L = (exit_price - entry_price) * qty
            entry_key = f"entry_price_{fill_assumption}"
            mark_key = f"mark_{fill_assumption}"

            entry_price = entry.get(entry_key, entry.get("entry_price_base", 0.0))
            exit_price = mark.get(mark_key, mark.get("mark_base", 0.0))

            # Adjust for direction (LONG = profit if exit > entry, SHORT = profit if entry > exit)
            side = entry.get("side", "long").lower()
            if side == "short":
                pnl = (entry_price - exit_price) * entry.get("qty", 0)
            else:
                pnl = (exit_price - entry_price) * entry.get("qty", 0)

            pnl_list.append(pnl)

        if not pnl_list:
            return {
                "total_pnl": 0.0,
                "n_trades": 0,
                "n_winners": 0,
                "n_losers": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "win_loss_ratio": 1.0,
                "stddev_pnl": 0.0,
            }

        import numpy as np

        total_pnl = sum(pnl_list)
        n_trades = len(pnl_list)
        winners = [p for p in pnl_list if p > 0]
        losers = [p for p in pnl_list if p < 0]
        n_winners = len(winners)
        n_losers = len(losers)
        win_rate = n_winners / n_trades if n_trades > 0 else 0.0
        avg_win = np.mean(winners) if winners else 0.0
        avg_loss = np.mean(losers) if losers else 0.0
        win_loss_ratio = avg_win / abs(avg_loss) if avg_loss != 0 else 1.0 if avg_win > 0 else 0.0
        stddev_pnl = float(np.std(pnl_list)) if len(pnl_list) > 1 else 0.0

        return {
            "total_pnl": float(total_pnl),
            "n_trades": n_trades,
            "n_winners": n_winners,
            "n_losers": n_losers,
            "win_rate": float(win_rate),
            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),
            "win_loss_ratio": float(win_loss_ratio),
            "stddev_pnl": stddev_pnl,
        }

    def get_ledger_summary(self, strategy_id: Optional[str] = None) -> Dict:
        """
        Get a high-level summary of the ledger.

        Args:
            strategy_id: Filter to specific strategy

        Returns:
            Summary dict with counts and stats
        """
        entries = self.load_entries(strategy_id=strategy_id)
        marks = self.load_all_marks()
        exits = self.load_exits()

        return {
            "n_entries": len(entries),
            "n_marks": len(marks),
            "n_exits": len(exits),
            "strategy_id": strategy_id,
            "last_entry_timestamp": entries[-1].get("timestamp") if entries else None,
            "last_mark_timestamp": marks[-1].get("timestamp") if marks else None,
            "last_exit_timestamp": exits[-1].get("timestamp") if exits else None,
        }
