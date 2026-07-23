import pytest
from unittest.mock import patch
from src.risk.circuit_breaker import CircuitBreaker, RiskParams

def test_correlation_gate():
    config = RiskParams(max_correlation_to_existing=0.7)
    cb = CircuitBreaker(config)
    
    with patch.object(CircuitBreaker, "check_correlation", return_value=0.8):
        allowed, reason = cb.can_execute("AAPL", 10, 150.0, 100000.0, ["MSFT"])
        assert allowed is False
        assert "exceeds limit" in reason

    with patch.object(CircuitBreaker, "check_correlation", return_value=0.5):
        allowed, reason = cb.can_execute("AAPL", 10, 150.0, 100000.0, ["MSFT"])
        assert allowed is True
