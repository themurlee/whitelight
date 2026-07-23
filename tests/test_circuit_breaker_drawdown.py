import pytest
from src.risk.circuit_breaker import CircuitBreaker, RiskParams

def test_circuit_breaker_no_lockdown():
    cb = CircuitBreaker(RiskParams(max_drawdown_pct=5.0), baseline_account_value=100000.0)
    allowed, reason = cb.can_execute("SPY", 10, 100.0, 97000.0)
    assert allowed is True
    assert cb.locked is False

def test_circuit_breaker_lockdown():
    cb = CircuitBreaker(RiskParams(max_drawdown_pct=5.0), baseline_account_value=100000.0)
    allowed, reason = cb.can_execute("SPY", 10, 100.0, 94000.0)
    assert allowed is False
    assert cb.locked is True
    assert "drawdown limit breach" in reason
