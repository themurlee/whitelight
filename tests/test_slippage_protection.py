import pytest
from src.execution.slippage_validator import SlippageConfig, validate_slippage

def test_slippage_protection_ok():
    config = SlippageConfig(max_slippage_pct=0.2, max_spread_pct=0.1)
    worst = validate_slippage("SPY", 100.0, "BUY", 99.95, 100.05, config)
    assert worst == 100.05

def test_slippage_protection_wide_spread():
    config = SlippageConfig(max_slippage_pct=0.2, max_spread_pct=0.1)
    with pytest.raises(ValueError, match="Spread gating rejected"):
        validate_slippage("SPY", 100.0, "BUY", 99.90, 100.10, config)

def test_slippage_protection_high_slippage():
    config = SlippageConfig(max_slippage_pct=0.2, max_spread_pct=0.5)
    with pytest.raises(ValueError, match="Slippage gating rejected"):
        validate_slippage("SPY", 100.0, "BUY", 100.0, 100.30, config)
