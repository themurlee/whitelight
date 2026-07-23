"""
WhiteLight Paper Trade Validation Script

Performs programmatic checks of credentials, connectivity, strategy files,
and system directories to ensure the environment is ready for paper trading.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PaperTradeValidation")

# Add project root to path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

import src.config as config

def run_validation_suite() -> bool:
    logger.info("==============================================")
    logger.info("     WHITELIGHT PAPER TRADE VALIDATION RUN     ")
    logger.info("==============================================")
    
    passed_all = True
    
    # 1. Verify Configuration & Credentials
    logger.info("\n--- [STEP 1] CONFIGURATION & CREDENTIALS CHECK ---")
    if not config.API_KEY or not config.SECRET_KEY or "YOUR_ALPACA" in config.API_KEY:
        logger.error("❌ Alpaca API credentials are not set or contain placeholders in src/config.py")
        passed_all = False
    else:
        logger.info("✓ API_KEY and SECRET_KEY are populated")
        
    if not hasattr(config, "SHADOW_REPO_PATH") or not config.SHADOW_REPO_PATH:
        logger.error("❌ SHADOW_REPO_PATH is not configured in src/config.py")
        passed_all = False
    else:
        logger.info(f"✓ SHADOW_REPO_PATH is set to: {config.SHADOW_REPO_PATH}")

    # 2. Verify Directory Structures
    logger.info("\n--- [STEP 2] DIRECTORY STRUCTURES CHECK ---")
    data_dir = os.path.join(BASE_DIR, "data")
    if not os.path.exists(data_dir):
        logger.warning(f"⚠️ data/ directory does not exist at {data_dir}. Attempting to create it...")
        try:
            os.makedirs(data_dir)
            logger.info("✓ data/ directory created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create data/ directory: {e}")
            passed_all = False
    else:
        logger.info("✓ data/ directory exists")

    # 3. Test Alpaca Client Connectivity
    logger.info("\n--- [STEP 3] ALPACA TRADING CLIENT CONNECTIVITY CHECK ---")
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
        account = client.get_account()
        logger.info("✓ Successfully connected to Alpaca Paper account API")
        logger.info(f"  Account Number: {account.account_number}")
        logger.info(f"  Buying Power:  ${float(account.buying_power):,.2f}")
        logger.info(f"  Cash Balance:  ${float(account.cash):,.2f}")
        logger.info(f"  Portfolio Val: ${float(account.portfolio_value):,.2f}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Alpaca API: {e}")
        passed_all = False

    # 4. Verify Shadow Strategy B Registry Loading
    logger.info("\n--- [STEP 4] SHADOW STRATEGY REGISTRY CHECK ---")
    try:
        from src.strategies.shadow_bridge.strategy_registry import StrategyRegistry
        registry = StrategyRegistry(config.SHADOW_REPO_PATH)
        strategies = registry.load_all_strategies()
        logger.info(f"✓ Successfully loaded {len(strategies)} strategies from Strategy B repository")
        strat_list = list(strategies.values())
        for i, strat in enumerate(strat_list[:3]):
            logger.info(f"  Strategy {i+1}: {strat.__name__}")
        if len(strategies) > 3:
            logger.info(f"  ... and {len(strategies) - 3} more strategies cached.")
    except Exception as e:
        logger.error(f"❌ Failed to load Shadow Strategy registry: {e}")
        passed_all = False

    # 5. Check Risk Circuit Breaker Status
    logger.info("\n--- [STEP 5] RISK CIRCUIT BREAKER CHECK ---")
    try:
        from src.risk.circuit_breaker import CircuitBreaker
        # Instantiate and query circuit breaker
        cb = CircuitBreaker(baseline_account_value=100000.0)
        allowed, reason = cb.can_execute(
            ticker="SPY",
            qty=1,
            price=450.0,
            account_value=100000.0,
            open_tickers=[]
        )
        logger.info(f"✓ Circuit Breaker status query check complete.")
        logger.info(f"  Permission for SPY: {'ALLOWED' if allowed else 'BLOCKED'} (Reason: {reason})")
    except Exception as e:
        logger.error(f"❌ Failed to query Circuit Breaker module: {e}")
        passed_all = False

    logger.info("\n==============================================")
    if passed_all:
        logger.info("🎉 VALIDATION VERDICT: READY FOR PAPER TRADING")
        logger.info("==============================================")
        return True
    else:
        logger.error("❌ VALIDATION VERDICT: ENVIRONMENT HARDENING FAILED")
        logger.error("   Review error messages above before running execution scans.")
        logger.error("==============================================")
        return False

if __name__ == "__main__":
    success = run_validation_suite()
    sys.exit(0 if success else 1)
