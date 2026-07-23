import pytest
from datetime import datetime, timezone, timedelta
from src.options.greeks import calculate_greeks

def test_greeks_dte_correctness():
    """Verify DTE calculation is correct for both live and backtest modes."""
    
    # Mock option data
    class MockOption:
        expiration = "2026-12-31T16:00:00Z"
        symbol = "SPY_CALL"
        strike = 450.0
    
    opt_data = MockOption()
    stock_price = 450.0
    iv = 25.0  # 25% IV
    
    # Test 1: Live mode (valuation_date=None)
    # Expected: DTE ≈ (2026-12-31 - now).days
    greeks_live = calculate_greeks(
        symbol=opt_data.symbol,
        strike=opt_data.strike,
        expiry=opt_data.expiration,
        option_type="call",
        current_price=stock_price,
        iv_rank=iv,
        valuation_date=None
    )
    assert greeks_live["delta"] > 0, "Call delta should be positive"
    
    # Test 2: Backtest mode with DTE = 30 days
    backtest_date = datetime(2026, 12, 1, 16, 0, 0, tzinfo=timezone.utc)
    greeks_30d = calculate_greeks(
        symbol=opt_data.symbol,
        strike=opt_data.strike,
        expiry=opt_data.expiration,
        option_type="call",
        current_price=stock_price,
        iv_rank=iv,
        valuation_date=backtest_date
    )
    assert greeks_30d["theta"] < greeks_live["theta"], "30-day option has faster theta decay than far-dated"
    assert greeks_30d["delta"] > 0
    
    # Test 3: Backtest mode with DTE = 1 day
    backtest_near_expiry = datetime(2026, 12, 30, 16, 0, 0, tzinfo=timezone.utc)
    greeks_1d = calculate_greeks(
        symbol=opt_data.symbol,
        strike=opt_data.strike,
        expiry=opt_data.expiration,
        option_type="call",
        current_price=stock_price,
        iv_rank=iv,
        valuation_date=backtest_near_expiry
    )
    assert greeks_1d["theta"] < greeks_30d["theta"], "1-day theta decay is extreme (far more negative)"
    
    # Test 4: Expired option (DTE < 0) should be handled gracefully
    backtest_expired = datetime(2027, 1, 1, 16, 0, 0, tzinfo=timezone.utc)
    greeks_expired = calculate_greeks(
        symbol=opt_data.symbol,
        strike=opt_data.strike,
        expiry=opt_data.expiration,
        option_type="call",
        current_price=stock_price,
        iv_rank=iv,
        valuation_date=backtest_expired
    )
    # Should not crash; DTE clamped to 0.01
    assert greeks_expired["delta"] > 0
    
    print("✓ All Greeks backtest safety tests passed")

if __name__ == "__main__":
    test_greeks_dte_correctness()
