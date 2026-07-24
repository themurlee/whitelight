from unittest.mock import patch
from src.options.full_audit.gate import run_full_audit_gate

def _contract():
    return {"strike": 700.0, "bid": 1.0, "ask": 1.1, "midpoint": 1.05, "open_interest": 1000,
            "greeks": {"delta": 0.45}, "symbol": "QQQ260815C00700000"}

@patch("src.options.full_audit.gate.CircuitBreaker")
@patch("src.options.full_audit.gate.DualAgentPipeline")
def test_run_full_audit_gate_all_pass(mock_pipeline_cls, mock_cb_cls):
    mock_pipeline_cls.return_value.run.return_value = {
        "status": "COMPLETED", "execution_ready": True,
        "proposal": {"reasoning": "Delta within bounds, liquidity adequate"},
        "validation": {"validation_notes": "Looks good", "final_action": "EXECUTE"},
    }
    mock_cb_cls.return_value.can_execute.return_value = (True, "Account drawdown OK")

    result = run_full_audit_gate(
        ticker="QQQ", expiration="2026-08-15", strategy="LONG CALL",
        selected_contract=_contract(), iv_rank=30.0, dte=23,
        account_value=100000.0, open_tickers=[],
    )
    assert result["overall"] == "AUDIT PASSED"
    assert result["stages"]["rules"]["pass"] is True
    assert result["stages"]["agent"]["pass"] is True
    assert result["stages"]["circuit"]["pass"] is True

@patch("src.options.full_audit.gate.CircuitBreaker")
@patch("src.options.full_audit.gate.DualAgentPipeline")
def test_run_full_audit_gate_rules_fail_still_runs_all_3(mock_pipeline_cls, mock_cb_cls):
    mock_pipeline_cls.return_value.run.return_value = {
        "status": "COMPLETED", "execution_ready": True,
        "proposal": {"reasoning": "ok"}, "validation": {"validation_notes": "ok", "final_action": "EXECUTE"},
    }
    mock_cb_cls.return_value.can_execute.return_value = (True, "Account drawdown OK")

    result = run_full_audit_gate(
        ticker="QQQ", expiration="2026-08-15", strategy="LONG CALL",
        selected_contract=_contract(), iv_rank=30.0, dte=0,  # dte=0 fails min-DTE rule
        account_value=100000.0, open_tickers=[],
    )
    assert result["overall"] == "AUDIT FAILED"
    assert result["stages"]["rules"]["pass"] is False
    # All 3 stages must still be populated even though rules failed
    assert result["stages"]["agent"] is not None
    assert result["stages"]["circuit"] is not None

@patch("src.options.full_audit.gate.CircuitBreaker")
def test_run_full_audit_gate_real_pipeline_agent_stage_passes(mock_cb_cls):
    """Regression test for the contract-extraction bug: uses the REAL (unmocked)
    DualAgentPipeline / RuleBasedAdapter path (production default provider="cortex")
    with a well-formed contract that includes a nested "greeks" dict — exactly the
    shape that broke the old non-greedy regex extraction. Only CircuitBreaker is
    mocked, to keep this hermetic (no real Alpaca network call)."""
    mock_cb_cls.return_value.can_execute.return_value = (True, "Account drawdown OK")

    result = run_full_audit_gate(
        ticker="QQQ", expiration="2026-08-15", strategy="LONG CALL",
        selected_contract=_contract(), iv_rank=30.0, dte=23,
        account_value=100000.0, open_tickers=[],
    )
    assert result["stages"]["agent"]["pass"] is True
    assert result["overall"] == "AUDIT PASSED"

@patch("src.options.full_audit.gate.CircuitBreaker")
@patch("src.options.full_audit.gate.DualAgentPipeline")
def test_run_full_audit_gate_circuit_breaker_fail(mock_pipeline_cls, mock_cb_cls):
    mock_pipeline_cls.return_value.run.return_value = {
        "status": "COMPLETED", "execution_ready": True,
        "proposal": {"reasoning": "ok"}, "validation": {"validation_notes": "ok", "final_action": "EXECUTE"},
    }
    mock_cb_cls.return_value.can_execute.return_value = (False, "Daily loss limit exceeded")

    result = run_full_audit_gate(
        ticker="QQQ", expiration="2026-08-15", strategy="LONG CALL",
        selected_contract=_contract(), iv_rank=30.0, dte=23,
        account_value=100000.0, open_tickers=[],
    )
    assert result["overall"] == "AUDIT FAILED"
    assert result["stages"]["circuit"]["pass"] is False
    assert "Daily loss limit exceeded" in result["stages"]["circuit"]["reason"]
