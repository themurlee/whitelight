import pytest
from unittest.mock import MagicMock, patch
from src.options.combo_orders import ComboLeg, ComboOrderRequest, submit_combo_order
from alpaca.trading.enums import OrderSide

def test_combo_order_construction():
    """Verify combo order is built correctly."""
    
    legs = [
        ComboLeg(symbol="AAPL_CALL_long", side=OrderSide.BUY, qty=10),
        ComboLeg(symbol="AAPL_CALL_short", side=OrderSide.SELL, qty=10)
    ]
    
    combo = ComboOrderRequest(symbol_base="AAPL", legs=legs)
    payload = combo.to_alpaca_payload()
    
    assert len(payload["orders"]) == 2
    assert payload["orders"][0]["symbol"] == "AAPL_CALL_long"
    assert payload["orders"][0]["side"] == "buy"
    assert payload["orders"][1]["symbol"] == "AAPL_CALL_short"
    assert payload["orders"][1]["side"] == "sell"
    
    print("✓ Combo order construction test passed")

def test_combo_order_validation():
    """Verify combo order validation (min 2 legs)."""
    
    # Test: Should fail with <2 legs
    with pytest.raises(ValueError, match="require at least 2 legs"):
        ComboOrderRequest(symbol_base="AAPL", legs=[
            ComboLeg(symbol="AAPL_CALL", side=OrderSide.BUY, qty=10)
        ])
    
    print("✓ Combo order validation test passed")

if __name__ == "__main__":
    test_combo_order_construction()
    test_combo_order_validation()
