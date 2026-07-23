import os
from dotenv import load_dotenv

# Load local .env
load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
JOURNAL_DIR = os.path.join(DATA_DIR, "journal")
TRADE_LOG_PATH = os.path.join(JOURNAL_DIR, "trade_log.md")

# Phase 1: Shadow Integration Configuration
SHADOW_REPO_PATH = os.getenv(
    "SHADOW_REPO_PATH",
    "/Users/nekanyab/Downloads/shadow-options-trading-lab-main"
)
SHADOW_LEDGER_DIR = os.path.join(SHADOW_REPO_PATH, "atlas", "data", "ledgers")

# Grading schedule configuration
GRADING_SCHEDULE_HOUR = int(os.getenv("GRADING_SCHEDULE_HOUR", "20"))  # 8 PM UTC
GRADING_ENABLED = os.getenv("GRADING_ENABLED", "true").lower() == "true"
