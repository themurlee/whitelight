"""
WhiteLight Systematic Trading & Analysis Pipeline - Secure REST API Server (FastAPI)

Authenticated, encrypted REST API with bearer token authentication.
Replaces zero-dependency ThreadingHTTPServer with FastAPI + uvicorn for production security.

Features:
- Bearer token authentication on all endpoints
- HTTPS/TLS support
- Rate limiting per token
- Structured error responses
- Full API feature parity with original api.py
"""

import os
import json
import glob
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from functools import lru_cache

from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configuration
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
POSITIONS_FILE = os.path.join(DATA_DIR, "positions.json")
TRADE_LOG_FILE = os.path.join(DATA_DIR, "trade_history.json")
PSYCHOLOGY_FILE = os.path.join(DATA_DIR, "psychology_log.json")
JOURNAL_DIR = os.path.join(DATA_DIR, "journal")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API_SECURE")

# API Configuration
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_TOKEN = os.getenv("WHITELIGHT_API_TOKEN", "sk-whitelight-dev-token-change-in-prod")
API_USE_HTTPS = os.getenv("API_USE_HTTPS", "false").lower() == "true"
SSL_KEYFILE = os.getenv("API_SSL_KEYFILE", "./certs/server.key")
SSL_CERTFILE = os.getenv("API_SSL_CERTFILE", "./certs/server.crt")

# Rate limiting per token (requests per second)
RATE_LIMIT_EXECUTE = 1  # /api/execute: 1 req/sec
RATE_LIMIT_READ = 10    # /api/positions, /api/state: 10 req/sec

# Token request tracking (token -> {count, last_reset_time})
token_rates = {}


def verify_bearer_token(authorization: str = Header(None)) -> str:
    """
    Verify bearer token from Authorization header.

    Expected format: Authorization: Bearer <token>
    """
    if not authorization:
        logger.warning("API request missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header"
        )

    if not authorization.startswith("Bearer "):
        logger.warning(f"API request invalid Authorization format: {authorization[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization format. Expected 'Bearer <token>'"
        )

    token = authorization.split(" ", 1)[1]

    if token != API_TOKEN:
        logger.warning(f"API request invalid token: {token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    return token


def check_rate_limit(token: str, endpoint: str, limit: int) -> None:
    """Check rate limit for token on endpoint."""
    import time
    now = time.time()

    key = f"{token}:{endpoint}"

    if key not in token_rates:
        token_rates[key] = {"count": 0, "last_reset": now}

    rate_info = token_rates[key]

    # Reset counter every second
    if now - rate_info["last_reset"] >= 1.0:
        rate_info["count"] = 0
        rate_info["last_reset"] = now

    rate_info["count"] += 1

    if rate_info["count"] > limit:
        logger.warning(f"Rate limit exceeded for token on {endpoint}: {rate_info['count']}/{limit}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit} requests per second"
        )


def _get_alpaca_account_info() -> Dict[str, Any]:
    """Fetch current account info from Alpaca API."""
    import sys
    sys.path.insert(0, BASE_DIR)
    import src.config as config

    if not config.API_KEY or not config.SECRET_KEY or "YOUR_ALPACA" in config.API_KEY:
        return {"configured": False, "error": "Credentials missing or default"}

    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
        acc = client.get_account()

        positions = []
        try:
            raw_positions = client.get_all_positions()
            for p in raw_positions:
                positions.append({
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "price": float(p.current_price),
                    "pnl": float(p.unrealized_pl),
                    "type": "LONG" if float(p.qty) > 0 else "SHORT"
                })
        except Exception:
            pass

        return {
            "configured": True,
            "account_number": acc.account_number,
            "cash": float(acc.cash),
            "equity": float(acc.equity),
            "buying_power": float(acc.buying_power),
            "portfolio_value": float(acc.portfolio_value),
            "status": str(acc.status),
            "positions": positions
        }
    except Exception as e:
        logger.error(f"Failed to fetch Alpaca account info: {e}")
        return {"configured": True, "error": str(e)}


def _get_systematic_status() -> Dict[str, Any]:
    """Get status of systematic trading pipeline."""
    tickers_status = {}

    for ticker_folder in glob.glob(os.path.join(DATA_DIR, "*")):
        if os.path.isdir(ticker_folder) and os.path.basename(ticker_folder) not in ["journal", "uploads"]:
            ticker = os.path.basename(ticker_folder)
            files = glob.glob(os.path.join(ticker_folder, "*.jsonl"))
            files.sort()
            tickers_status[ticker] = {
                "count": len(files),
                "first_date": os.path.basename(files[0]).replace(".jsonl", "") if files else None,
                "last_date": os.path.basename(files[-1]).replace(".jsonl", "") if files else None,
            }

    log_content = ""
    if os.path.exists(TRADE_LOG_FILE):
        try:
            with open(TRADE_LOG_FILE, "r") as f:
                lines = f.readlines()
                log_content = "".join(reversed(lines[-100:]))
        except Exception:
            pass

    return {
        "tickers": tickers_status,
        "last_logs": log_content,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def _get_journal_files() -> List[Dict[str, str]]:
    """List all journal reflection files."""
    journal_files = []
    if os.path.exists(JOURNAL_DIR):
        for file in sorted(glob.glob(os.path.join(JOURNAL_DIR, "*_reflection.md")), reverse=True):
            try:
                with open(file, "r") as f:
                    content = f.read()
                journal_files.append({
                    "filename": os.path.basename(file),
                    "content": content,
                    "date": os.path.basename(file).replace("_reflection.md", "")
                })
            except Exception:
                pass
    return journal_files


# Initialize FastAPI app
app = FastAPI(
    title="WhiteLight Trading Bot API",
    description="Secure REST API for WhiteLight systematic trading platform",
    version="1.0.0"
)

# CORS middleware (restrict to localhost for security)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["127.0.0.1", "localhost", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint (no auth required)."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/account")
async def get_account(token: str = Depends(verify_bearer_token)):
    """Get current Alpaca account info."""
    check_rate_limit(token, "/api/account", RATE_LIMIT_READ)
    account_info = _get_alpaca_account_info()
    return JSONResponse(content=account_info)


@app.get("/api/positions")
async def get_positions(token: str = Depends(verify_bearer_token)):
    """Get all open positions."""
    check_rate_limit(token, "/api/positions", RATE_LIMIT_READ)
    account_info = _get_alpaca_account_info()
    return JSONResponse(content={
        "positions": account_info.get("positions", []),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.get("/api/state")
async def get_state(token: str = Depends(verify_bearer_token)):
    """Get current system state."""
    check_rate_limit(token, "/api/state", RATE_LIMIT_READ)
    state_data = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state_data = json.load(f)
        except Exception:
            pass

    sys_status = _get_systematic_status()

    return JSONResponse(content={
        "state": state_data,
        "systematic": sys_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.post("/api/execute")
async def execute_signal(token: str = Depends(verify_bearer_token)):
    """Trigger signal execution (rate-limited)."""
    check_rate_limit(token, "/api/execute", RATE_LIMIT_EXECUTE)

    import sys
    sys.path.insert(0, BASE_DIR)

    try:
        from src.coordinator import run_pipeline

        # Execute pipeline
        result = run_pipeline(["SPY"], dry_run=False)

        return JSONResponse(content={
            "status": "executed",
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Signal execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@app.get("/api/options/audit")
async def get_options_audit(
    ticker: Optional[str] = None,
    underlying: Optional[str] = None,
    expiry: Optional[str] = None,
    expiration: Optional[str] = None,
    token: str = Depends(verify_bearer_token)
):
    """Run programmatic options trade audit analysis."""
    check_rate_limit(token, "/api/options/audit", RATE_LIMIT_READ)
    tk = ticker or underlying or "AAPL"
    exp = expiry or expiration or "WEEKLY"
    try:
        from src.options.audit_engine import audit_options_trade
        result = audit_options_trade(tk, exp)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/options/audit")
async def post_options_audit(
    payload: Dict[str, Any],
    token: str = Depends(verify_bearer_token)
):
    """Run programmatic options trade audit analysis via POST payload."""
    check_rate_limit(token, "/api/options/audit", RATE_LIMIT_READ)
    tk = payload.get("ticker") or payload.get("underlying") or "AAPL"
    exp = payload.get("expiry") or payload.get("expiration") or "WEEKLY"
    try:
        from src.options.audit_engine import audit_options_trade
        result = audit_options_trade(tk, exp)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/journal")
async def get_journal(token: str = Depends(verify_bearer_token)):
    """Get all journal reflection files."""
    check_rate_limit(token, "/api/journal", RATE_LIMIT_READ)
    journal_files = _get_journal_files()
    return JSONResponse(content={
        "journal": journal_files,
        "count": len(journal_files),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.get("/api/trades")
async def get_trades(token: str = Depends(verify_bearer_token)):
    """Get recent trade history."""
    check_rate_limit(token, "/api/trades", RATE_LIMIT_READ)
    trades = []
    if os.path.exists(TRADE_LOG_FILE):
        try:
            with open(TRADE_LOG_FILE, "r") as f:
                trades = json.load(f)
                if not isinstance(trades, list):
                    trades = [trades]
        except Exception:
            pass

    return JSONResponse(content={
        "trades": trades[-100:],  # Last 100 trades
        "count": len(trades),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


def run_secure_server(host: str = API_HOST, port: int = API_PORT, use_https: bool = API_USE_HTTPS):
    """Run the secure API server."""

    logger.info(f"Starting WhiteLight Secure API on {host}:{port}")
    logger.info(f"Bearer token authentication enabled")
    logger.info(f"HTTPS: {use_https}")

    ssl_config = {}
    if use_https:
        if os.path.exists(SSL_KEYFILE) and os.path.exists(SSL_CERTFILE):
            ssl_config = {
                "keyfile": SSL_KEYFILE,
                "certfile": SSL_CERTFILE
            }
            logger.info(f"Using SSL certificates: {SSL_CERTFILE}")
        else:
            logger.warning("HTTPS requested but SSL certificates not found. Running in plaintext.")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        **ssl_config
    )


if __name__ == "__main__":
    run_secure_server()
