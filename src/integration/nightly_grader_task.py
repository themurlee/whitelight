"""
Nightly Grading Task: Scheduled execution of Shadow grading on WhiteLight ledgers

This script is intended to be run nightly (via cron or task scheduler) to:
1. Load WhiteLight's execution ledgers from entries.jsonl
2. Invoke ShadowGraderWrapper to compute verdicts
3. Save scorecard.json with strategy verdicts
4. Append to scorecard_history.jsonl for historical tracking

Usage:
    python -m src.integration.nightly_grader_task

Or via cron:
    0 20 * * * cd /path/to/whitelight && python -m src.integration.nightly_grader_task
"""

import os
import sys
import logging
from datetime import datetime

# Configure path imports
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, BASE_DIR)

import src.config as config
from src.integration.shadow_grader_wrapper import ShadowGraderWrapper
from src.alerting.slack_notifier import post_alert

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("NightlyGrader")


def run_nightly_grading():
    """
    Run nightly grading on WhiteLight's strategy.

    Steps:
    1. Check if grading is enabled
    2. Initialize grader
    3. Grade primary strategy
    4. Save scorecard and history
    5. Post Slack alert with results
    """

    if not config.GRADING_ENABLED:
        logger.info("Grading is disabled (GRADING_ENABLED=false). Exiting.")
        return

    try:
        logger.info("Starting nightly grading...")

        # Initialize grader
        grader = ShadowGraderWrapper(
            shadow_repo_path=config.SHADOW_REPO_PATH,
            whitelight_data_dir=config.DATA_DIR
        )

        # Grade primary strategy
        logger.info("Grading whitelight_primary strategy...")
        grade_result = grader.grade_whitelight_strategy(
            strategy_id="whitelight_primary",
            fill_assumption="worst"
        )

        logger.info(f"Grade result: {grade_result['verdict']} (wealth={grade_result.get('wealth', 0):.2f}, n={grade_result['n_trades']})")

        # Save scorecard.json
        scorecard_path = os.path.join(config.DATA_DIR, "scorecard.json")
        grader.save_scorecard(grade_result, scorecard_path)
        logger.info(f"Scorecard saved to {scorecard_path}")

        # Save to history
        history_dir = os.path.join(config.DATA_DIR, "grading")
        grader.save_scorecard_history(grade_result, history_dir)
        logger.info(f"Scorecard appended to history")

        # Post Slack alert
        emoji_map = {
            "PROVEN": "✅",
            "UNPROVEN": "⚠️",
            "LOSER": "❌"
        }
        emoji = emoji_map.get(grade_result["verdict"], "❓")

        alert_message = (
            f"{emoji} [whitelight-grader] {grade_result['verdict']} "
            f"(wealth={grade_result.get('wealth', 0):.2f}, n={grade_result['n_trades']}, "
            f"win_rate={grade_result.get('win_rate', 0):.1%})"
        )
        post_alert(alert_message)

        logger.info("Nightly grading completed successfully")
        return True

    except Exception as e:
        logger.error(f"Nightly grading failed: {e}", exc_info=True)
        post_alert(f"❌ [whitelight-grader] Nightly grading failed: {e}")
        return False


if __name__ == "__main__":
    success = run_nightly_grading()
    sys.exit(0 if success else 1)
