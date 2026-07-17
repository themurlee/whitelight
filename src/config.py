import os
from dotenv import load_dotenv

# Load local .env
load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
JOURNAL_DIR = os.path.join(DATA_DIR, "journal")
TRADE_LOG_PATH = os.path.join(JOURNAL_DIR, "trade_log.md")
