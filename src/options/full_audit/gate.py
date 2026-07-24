import logging
from typing import Dict, List, Optional

from src.options.agents import DualAgentPipeline
from src.risk.circuit_breaker import CircuitBreaker
from src.options.full_audit.rules_engine import evaluate_rules

logger = logging.getLogger("FullAuditGate")


def run_full_audit_gate(
    ticker: str,
    expiration: str,
    strategy: str,
    selected_contract: Dict,
    iv_rank: float,
    dte: int,
    level_reference: Optional[str] = None,
    account_value: Optional[float] = None,
    open_tickers: Optional[List[str]] = None,
    proposer_provider: str = "cortex",
    proposer_model: str = "cortex-fast",
    validator_provider: str = "cortex",
    validator_model: str = "cortex-strict",
) -> Dict:
    """3-stage synthesis: Rules -> Agent -> Circuit Breaker. All 3 always run to completion."""
    ticker = ticker.upper()

    # Stage 1: Rules Engine
    order_value = float(selected_contract.get("midpoint", 0)) * 100
    rules_result = evaluate_rules(
        selected_contract, iv_rank=iv_rank, dte=dte,
        account_equity=account_value, order_value=order_value,
    )

    # Stage 2: Agent Audit (LLM Proposer/Validator, level-aware)
    signals = {
        "intraday_bias": "BULLISH" if "CALL" in strategy.upper() else "BEARISH",
        "rsi_7": 50.0,
        "iv_rank": iv_rank,
        "expiration": expiration,
        "dte": dte,
        "level_reference": level_reference or "No specific level context",
    }
    pipeline = DualAgentPipeline(
        proposer_provider=proposer_provider, proposer_model=proposer_model,
        validator_provider=validator_provider, validator_model=validator_model,
    )
    agent_raw = pipeline.run(ticker, signals, timeframe="WEEKLY", selected_contract=selected_contract)
    agent_pass = bool(agent_raw.get("execution_ready", False))
    agent_result = {
        "pass": agent_pass,
        "reasoning": agent_raw.get("proposal", {}).get("reasoning", "")
        or agent_raw.get("validation", {}).get("validation_notes", "No reasoning provided"),
    }

    # Stage 3: Circuit Breaker
    cb = CircuitBreaker(baseline_account_value=account_value or 100000.0)
    qty = 1
    price = float(selected_contract.get("midpoint", 0))
    cb_pass, cb_reason = cb.can_execute(
        ticker=ticker, qty=qty, price=price,
        account_value=account_value, open_tickers=open_tickers or [],
    )
    circuit_result = {"pass": cb_pass, "reason": cb_reason}

    overall_pass = rules_result["pass"] and agent_result["pass"] and circuit_result["pass"]

    return {
        "overall": "AUDIT PASSED" if overall_pass else "AUDIT FAILED",
        "stages": {
            "rules": rules_result,
            "agent": agent_result,
            "circuit": circuit_result,
        },
        "recommendation": f"{strategy} {expiration} ({dte} DTE)" if overall_pass else "NO_TRADE",
    }
