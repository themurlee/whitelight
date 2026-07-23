"""
ShadowGraderWrapper: Invoke Shadow's grading logic on WhiteLight ledgers

Grades WhiteLight's strategy using Shadow's worst-fill model and e-process wealth testing.

Key concepts:
- E-process wealth: sqrt(n) * (mean_pnl / std_pnl) — tests if strategy has edge
- Verdicts:
  * PROVEN: wealth >= 20 AND n_trades >= 25 (statistically significant edge)
  * UNPROVEN: n_trades < 25 (not enough data)
  * LOSER: wealth <= -20 (statistically significant negative edge)

This enables WhiteLight to:
1. Score its own strategies against Shadow's rigorous grading
2. Track verdict changes over time
3. Identify when a strategy's edge deteriorates
"""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

import numpy as np

from src.integration.shadow_ledger_reader import ShadowLedgerReader

logger = logging.getLogger("ShadowGraderWrapper")


class ShadowGraderWrapper:
    """Grade WhiteLight's strategy using Shadow's e-process wealth model."""

    # Verdict thresholds
    PROVEN_WEALTH_THRESHOLD = 20.0  # sqrt(n) * mean/std >= 20
    PROVEN_MIN_TRADES = 25
    LOSER_WEALTH_THRESHOLD = -20.0

    def __init__(self, shadow_repo_path: str = None, whitelight_data_dir: str = None):
        """
        Initialize grader wrapper.

        Args:
            shadow_repo_path: Path to Shadow repo (for future integration)
            whitelight_data_dir: Path to WhiteLight data directory containing ledgers
        """
        self.shadow_repo_path = shadow_repo_path
        self.wl_data_dir = whitelight_data_dir or os.path.join(os.path.dirname(__file__), "..", "..", "data")

        # Initialize ledger reader
        self.reader = ShadowLedgerReader(ledger_dir=self.wl_data_dir)

    def grade_whitelight_strategy(
        self,
        strategy_id: str = "whitelight_primary",
        fill_assumption: str = "worst"
    ) -> Dict:
        """
        Grade WhiteLight's strategy using worst-fill model.

        Args:
            strategy_id: Strategy identifier
            fill_assumption: "worst", "base", or "optimistic"

        Returns:
            Verdict dict with keys:
            - verdict: "PROVEN" | "UNPROVEN" | "LOSER"
            - wealth: e-process wealth score
            - n_trades: number of trades
            - win_rate: percentage of winners
            - avg_win: average winning trade
            - avg_loss: average losing trade
            - worst_case_drawdown: max drawdown using worst fills
            - base_case_drawdown: max drawdown using base fills
            - optimistic_drawdown: max drawdown using optimistic fills
            - timestamp: when grading was computed
        """

        # 1. Load entries for strategy
        entries = self.reader.load_entries(strategy_id=strategy_id)

        if not entries:
            logger.warning(f"No entries found for strategy {strategy_id}")
            return {
                "strategy_id": strategy_id,
                "verdict": "UNPROVEN",
                "n_trades": 0,
                "wealth": 0.0,
                "note": "No trades yet",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        # 2. Compute P&L across three fill assumptions
        pnl_worst = self._compute_pnl_list(entries, "worst")
        pnl_base = self._compute_pnl_list(entries, "base")
        pnl_optimistic = self._compute_pnl_list(entries, "optimistic")

        # 3. Compute wealth (simplified Shadow model)
        # wealth = sqrt(n) * (mean_pnl / std_pnl)
        # If std is 0 or mean is 0, health = 0
        wealth_worst = self._compute_wealth(pnl_worst)
        wealth_base = self._compute_wealth(pnl_base)
        wealth_optimistic = self._compute_wealth(pnl_optimistic)

        logger.info(
            f"Grading {strategy_id}: wealth_worst={wealth_worst:.2f}, "
            f"wealth_base={wealth_base:.2f}, wealth_opt={wealth_optimistic:.2f}, n={len(entries)}"
        )

        # 4. Determine verdict based on worst-case wealth
        verdict = self._determine_verdict(wealth_worst, len(entries))

        # 5. Compute drawdown under all three assumptions
        drawdown_worst = self.reader.compute_drawdown_by_worst_fill(entries)

        # Compute drawdown for base and optimistic (simplified)
        drawdown_base = self._compute_drawdown_for_assumption(entries, "base")
        drawdown_optimistic = self._compute_drawdown_for_assumption(entries, "optimistic")

        # 6. Compute P&L statistics
        pnl_stats_worst = self._compute_pnl_stats(pnl_worst)

        return {
            "strategy_id": strategy_id,
            "verdict": verdict,
            "wealth": float(wealth_worst),
            "wealth_base": float(wealth_base),
            "wealth_optimistic": float(wealth_optimistic),
            "n_trades": len(entries),
            "win_rate": pnl_stats_worst["win_rate"],
            "n_winners": pnl_stats_worst["n_winners"],
            "n_losers": pnl_stats_worst["n_losers"],
            "avg_win": pnl_stats_worst["avg_win"],
            "avg_loss": pnl_stats_worst["avg_loss"],
            "total_pnl": pnl_stats_worst["total_pnl"],
            "worst_case_drawdown": float(drawdown_worst),
            "base_case_drawdown": float(drawdown_base),
            "optimistic_drawdown": float(drawdown_optimistic),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def _compute_pnl_list(self, entries: List[Dict], fill_assumption: str) -> List[float]:
        """
        Compute P&L for each closed position under a fill assumption.

        Args:
            entries: List of entry dicts
            fill_assumption: "worst", "base", or "optimistic"

        Returns:
            List of P&L values
        """
        pnl_list = []

        for entry in entries:
            entry_id = entry.get("timestamp")

            # Get latest mark for this entry
            mark = self.reader.load_latest_mark_for_entry(entry_id)

            if not mark:
                # Position still open; skip (only grade closed positions)
                continue

            # Extract prices
            entry_key = f"entry_price_{fill_assumption}"
            mark_key = f"mark_{fill_assumption}"

            entry_price = entry.get(entry_key, entry.get("entry_price_base", 0.0))
            exit_price = mark.get(mark_key, mark.get("mark_base", 0.0))

            # Compute P&L (simple long position)
            side = entry.get("side", "long").lower()
            if side == "short":
                pnl = (entry_price - exit_price) * entry.get("qty", 0)
            else:
                pnl = (exit_price - entry_price) * entry.get("qty", 0)

            pnl_list.append(pnl)

        return pnl_list

    def _compute_wealth(self, pnl_list: List[float]) -> float:
        """
        Compute e-process wealth statistic.

        Wealth = sqrt(n) * (mean_pnl / std_pnl)

        This measures the strength of the edge:
        - wealth > 20: Statistically significant edge (PROVEN)
        - wealth < -20: Statistically significant negative edge (LOSER)
        - -20 <= wealth <= 20: No significant edge (UNPROVEN)

        Args:
            pnl_list: List of P&L values

        Returns:
            Wealth score
        """
        if not pnl_list or len(pnl_list) < 2:
            return 0.0

        n = len(pnl_list)
        mean_pnl = np.mean(pnl_list)
        std_pnl = np.std(pnl_list, ddof=1)  # Sample std

        if std_pnl == 0:
            if mean_pnl > 0:
                return 999.0
            elif mean_pnl < 0:
                return -999.0
            return 0.0

        wealth = np.sqrt(n) * (mean_pnl / std_pnl)
        return float(wealth)

    def _determine_verdict(self, wealth: float, n_trades: int) -> str:
        """
        Determine verdict based on wealth score and sample size.

        Args:
            wealth: E-process wealth score
            n_trades: Number of trades

        Returns:
            "PROVEN", "UNPROVEN", or "LOSER"
        """
        if n_trades < self.PROVEN_MIN_TRADES:
            return "UNPROVEN"

        if wealth >= self.PROVEN_WEALTH_THRESHOLD:
            return "PROVEN"
        elif wealth <= self.LOSER_WEALTH_THRESHOLD:
            return "LOSER"
        else:
            return "UNPROVEN"

    def _compute_drawdown_for_assumption(self, entries: List[Dict], assumption: str) -> float:
        """
        Compute max drawdown under a fill assumption.

        Args:
            entries: List of entry dicts
            assumption: "base" or "optimistic"

        Returns:
            Drawdown percentage
        """
        if not entries:
            return 0.0

        # Compute peak value
        peak_val = sum(entry.get(f"entry_price_{assumption}", 0.0) * entry.get("qty", 0) for entry in entries)

        # Compute current value using marks
        current_val = 0.0
        for entry in entries:
            entry_id = entry.get("timestamp")
            mark = self.reader.load_latest_mark_for_entry(entry_id)

            if mark:
                current_val += mark.get(f"mark_{assumption}", entry.get(f"entry_price_{assumption}", 0.0)) * entry.get("qty", 0)
            else:
                current_val += entry.get(f"entry_price_{assumption}", 0.0) * entry.get("qty", 0)

        if peak_val <= 0:
            return 0.0

        drawdown = (peak_val - current_val) / peak_val * 100.0
        return float(max(0.0, drawdown))  # Don't report negative drawdown

    def _compute_pnl_stats(self, pnl_list: List[float]) -> Dict:
        """Compute P&L statistics from a P&L list."""
        if not pnl_list:
            return {
                "total_pnl": 0.0,
                "n_winners": 0,
                "n_losers": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
            }

        winners = [p for p in pnl_list if p > 0]
        losers = [p for p in pnl_list if p < 0]

        return {
            "total_pnl": float(sum(pnl_list)),
            "n_winners": len(winners),
            "n_losers": len(losers),
            "win_rate": len(winners) / len(pnl_list) if pnl_list else 0.0,
            "avg_win": float(np.mean(winners)) if winners else 0.0,
            "avg_loss": float(np.mean(losers)) if losers else 0.0,
        }

    def save_scorecard(self, grade_result: Dict, output_path: str) -> bool:
        """
        Save grading result to scorecard.json.

        Args:
            grade_result: Verdict dict from grade_whitelight_strategy()
            output_path: Path to save scorecard

        Returns:
            True if save succeeded
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, "w") as f:
                json.dump(grade_result, f, indent=2)

            logger.info(f"Scorecard saved to {output_path}: verdict={grade_result.get('verdict')}")
            return True

        except Exception as e:
            logger.error(f"Failed to save scorecard: {e}")
            return False

    def save_scorecard_history(self, grade_result: Dict, history_dir: str) -> bool:
        """
        Append grading result to a history JSONL file.

        Args:
            grade_result: Verdict dict
            history_dir: Directory to store history file

        Returns:
            True if append succeeded
        """
        try:
            os.makedirs(history_dir, exist_ok=True)

            history_file = os.path.join(history_dir, "scorecard_history.jsonl")

            with open(history_file, "a") as f:
                f.write(json.dumps(grade_result) + "\n")

            logger.info(f"Scorecard appended to history: {history_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to append to scorecard history: {e}")
            return False
