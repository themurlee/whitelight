import pytest
from unittest.mock import MagicMock, patch, mock_open
import os
import json
from src.state_reconciliation import reconcile_positions, POSITIONS_FILE

def test_reconcile_positions_out_of_sync():
    """Verify that positions not present on Alpaca are removed from local state."""
    
    # Mock Alpaca return positions
    class MockAlpacaPosition:
        def __init__(self, symbol):
            self.symbol = symbol
            
    mock_positions = [MockAlpacaPosition("AAPL260814C00185000")]
    mock_client = MagicMock()
    mock_client.get_all_positions.return_value = mock_positions
    
    # Setup mock local state with an obsolete entry
    initial_local = {
        "active_positions": [
            {
                "symbol": "AAPL260814C00185000",
                "quantity": 1
            },
            {
                "symbol": "MSFT260814C00400000",  # This is obsolete (not on Alpaca)
                "quantity": 1
            }
        ]
    }
    
    m_open = mock_open(read_data=json.dumps(initial_local))
    
    with patch("builtins.open", m_open):
        with patch("os.path.exists", return_value=True):
            result = reconcile_positions(trading_client=mock_client)
            
            assert result["status"] == "success"
            assert "MSFT260814C00400000" in result["reconciled_removed"]
            assert result["active_positions_count"] == 1
            
            # Verify file open calls
            m_open.assert_any_call(POSITIONS_FILE, "r")
            m_open.assert_any_call(POSITIONS_FILE, "w")
                    
    print("✓ State reconciliation test passed")

if __name__ == "__main__":
    test_reconcile_positions_out_of_sync()
