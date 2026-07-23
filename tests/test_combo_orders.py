import pytest
from unittest.mock import MagicMock, patch
from src.options.combo_orders import ComboLeg, ComboOrderRequest, submit_combo_order
from alpaca.trading.enums import OrderSide, OrderClass, TimeInForce

def test_combo_order_construction():
    """Verify combo order validates correctly."""
    
    legs = [
        ComboLeg(symbol="AAPL_CALL_long", side=OrderSide.BUY, ratio=1),
        ComboLeg(symbol="AAPL_CALL_short", side=OrderSide.SELL, ratio=1)
    ]
    
    combo = ComboOrderRequest(
        symbol_base="AAPL",
        legs=legs,
        qty=5,
        order_type="limit",
        limit_price=1.20,
        time_in_force=TimeInForce.DAY
    )
    
    assert combo.symbol_base == "AAPL"
    assert combo.qty == 5
    assert combo.order_type == "limit"
    assert combo.limit_price == 1.20
    assert len(combo.legs) == 2
    
    print("✓ Combo order construction validation passed")

def test_combo_order_validation_limits():
    """Verify leg boundary limits (2-4 legs) and missing limit price checks."""
    
    # 1. Test: Should fail with < 2 legs
    with pytest.raises(ValueError, match="require at least 2 legs"):
        ComboOrderRequest(symbol_base="AAPL", legs=[
            ComboLeg(symbol="AAPL_CALL", side=OrderSide.BUY)
        ])
        
    # 2. Test: Should fail with > 4 legs
    with pytest.raises(ValueError, match="maximum of 4 legs"):
        ComboOrderRequest(symbol_base="AAPL", legs=[
            ComboLeg(symbol="AAPL_CALL_1", side=OrderSide.BUY),
            ComboLeg(symbol="AAPL_CALL_2", side=OrderSide.BUY),
            ComboLeg(symbol="AAPL_CALL_3", side=OrderSide.BUY),
            ComboLeg(symbol="AAPL_CALL_4", side=OrderSide.BUY),
            ComboLeg(symbol="AAPL_CALL_5", side=OrderSide.BUY),
        ])
        
    # 3. Test: Should fail if limit order has no limit price
    with pytest.raises(ValueError, match="Limit price must be specified"):
        ComboOrderRequest(symbol_base="AAPL", legs=[
            ComboLeg(symbol="AAPL_CALL_1", side=OrderSide.BUY),
            ComboLeg(symbol="AAPL_CALL_2", side=OrderSide.SELL),
        ], order_type="limit", limit_price=None)
        
    print("✓ Combo order validation limits passed")

if __name__ == "__main__":
    test_combo_order_construction()
    test_combo_order_validation_limits()
