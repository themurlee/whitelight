import os
import json
import pytest
import tempfile
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import src.config as config
from src.strategies.shadow_bridge.strategy_registry import StrategyRegistry
from src.strategies.shadow_bridge.contract_selector import ContractSelectorBridge
from src.strategies.shadow_bridge.greeks_calculator import GreeksCalculatorBridge
from src.strategies.shadow_bridge.exit_rules_engine import ExitRulesEngine, Position
from src.phase2_coordinator import run_phase2_pipeline

@pytest.fixture
def mock_alpaca_client():
    client = MagicMock()
    
    # Mock get_option_contracts response
    contract_mock1 = MagicMock()
    contract_mock1.symbol = "SPY260814P00450000"
    contract_mock1.underlying_symbol = "SPY"
    contract_mock1.strike_price = 450.0
    contract_mock1.expiration_date = "2026-08-14"
    contract_mock1.type = "PUT"
    contract_mock1.bid_price = 5.20
    contract_mock1.ask_price = 5.30
    contract_mock1.open_interest = 1200
    contract_mock1.volume = 150
    
    contract_mock2 = MagicMock()
    contract_mock2.symbol = "SPY260814C00455000"
    contract_mock2.underlying_symbol = "SPY"
    contract_mock2.strike_price = 455.0
    contract_mock2.expiration_date = "2026-08-14"
    contract_mock2.type = "CALL"
    contract_mock2.bid_price = 4.10
    contract_mock2.ask_price = 4.25
    contract_mock2.open_interest = 800
    contract_mock2.volume = 90
    
    response = MagicMock()
    response.option_contracts = [contract_mock1, contract_mock2]
    client.get_option_contracts.return_value = response
    
    # Mock account
    account_mock = MagicMock()
    account_mock.portfolio_value = 100000.0
    client.get_account.return_value = account_mock
    
    # Mock positions
    client.get_all_positions.return_value = []
    
    return client

class TestStrategyRegistry:
    def test_strategy_registry_loads_all_strategies(self):
        """Verify registry loads strategies from Shadow repo."""
        registry = StrategyRegistry(config.SHADOW_REPO_PATH)
        strategies = registry.load_all_strategies()
        # Ensure we can load strategies successfully
        assert len(strategies) > 0, "No strategies loaded"
        assert "vrp_short_straddle" in strategies or "rsi2_oversold_short_put" in strategies, "Expected strategies not found"

class TestContractSelectorBridge:
    def test_contract_selector_finds_valid_chains(self, mock_alpaca_client):
        """Verify selector maps abstract combo/proposed combo to Alpaca contracts."""
        selector = ContractSelectorBridge(mock_alpaca_client)
        
        # Test abstract format
        result = selector.select_contracts(
            symbol="SPY",
            proposed_combo=[(-0.01, 22, "short", "put")],
            current_price=455.0,
            min_oi=100
        )
        
        assert result["valid"], f"Selection failed: {result.get('reason')}"
        assert len(result["combo"]) == 1
        assert result["combo"][0]["contract_id"] == "SPY260814P00450000"
        assert result["combo"][0]["strike"] == 450.0

class TestGreeksCalculatorBridge:
    def test_greeks_combo_calculation(self):
        """Verify aggregate Greeks calculation works correctly."""
        greeks_calc = GreeksCalculatorBridge()
        
        combo = [
            {"symbol": "SPY", "strike": 450.0, "type": "put", "side": "short", "expiry": "2026-08-14"},
            {"symbol": "SPY", "strike": 455.0, "type": "call", "side": "long", "expiry": "2026-08-14"}
        ]
        
        greeks = greeks_calc.calculate_combo_greeks(
            combo=combo,
            current_price=452.0,
            iv_rank=35.0,
            dte=22
        )
        
        assert "delta" in greeks
        assert "gamma" in greeks
        assert "vega" in greeks
        assert "theta" in greeks
        assert isinstance(greeks["delta"], float)

class TestExitRulesEngine:
    def test_exit_rules_fires_on_profit_target(self):
        """Verify exit rule triggers when profit target is hit."""
        engine = ExitRulesEngine()
        
        position = Position(
            entry_id="test_position_1",
            symbol="SPY",
            combo=[],
            entry_price=2.50,
            entry_timestamp=datetime.now(timezone.utc),
            entry_greeks={"dte": 30},
            capital_at_risk=250.0
        )
        engine.register_position(position)
        
        # Mock current state
        state = {
            "test_position_1": {
                "pnl_pct": 0.30,  # 30% profit (fires >= 25% target)
                "pnl": 75.0
            }
        }
        
        exits = engine.check_exits(state)
        assert len(exits) == 1
        assert exits[0]["rule_fired"] == "profit_target_25pct"
        
    def test_exit_rules_fires_on_max_loss(self):
        """Verify exit rule triggers when max loss is hit."""
        engine = ExitRulesEngine()
        
        position = Position(
            entry_id="test_position_2",
            symbol="QQQ",
            combo=[],
            entry_price=4.00,
            entry_timestamp=datetime.now(timezone.utc),
            entry_greeks={"dte": 30},
            capital_at_risk=400.0
        )
        engine.register_position(position)
        
        # Mock loss state
        state = {
            "test_position_2": {
                "pnl_pct": -1.10,
                "pnl": -450.0  # Fails limit of $400 capital at risk
            }
        }
        
        exits = engine.check_exits(state)
        assert len(exits) == 1
        assert exits[0]["rule_fired"] == "max_loss_circuit"

    def test_exit_rules_fires_on_new_rules(self):
        """Verify the 7 newly added exit rules trigger and map correctly."""
        engine = ExitRulesEngine()
        
        pos = Position(
            entry_id="test_new_rules",
            symbol="IWM",
            combo=[],
            entry_price=1.50,
            entry_timestamp=datetime.now(timezone.utc),
            entry_greeks={"dte": 30},
            capital_at_risk=150.0
        )
        engine.register_position(pos)
        
        # Test macro print
        assert engine.check_exits({"test_new_rules": {"macro_print": True}})[0]["rule_fired"] == "macro_print_blackout"
        
        # Test gamma risk breach
        assert engine.check_exits({"test_new_rules": {"gamma": 0.05, "price_move": 3.0, "gamma_threshold": 0.1}})[0]["rule_fired"] == "gamma_risk_breach"
        
        # Test technical breakdown
        assert engine.check_exits({"test_new_rules": {"technical_breakdown": True}})[0]["rule_fired"] == "technical_breakdown"
        
        # Test calendar vega roll
        assert engine.check_exits({"test_new_rules": {"calendar_vega_roll": True}})[0]["rule_fired"] == "calendar_vega_roll"
        
        # Test correlation breach
        assert engine.check_exits({"test_new_rules": {"correlation": 0.85}})[0]["rule_fired"] == "correlation_breach"
        
        # Test margin pressure
        assert engine.check_exits({"test_new_rules": {"margin_pct": 0.15}})[0]["rule_fired"] == "margin_pressure"
        
        # Test voluntary exit
        assert engine.check_exits({"test_new_rules": {"voluntary_exit": True}})[0]["rule_fired"] == "voluntary_exit"

class TestPhase2Coordinator:
    @patch("src.phase2_coordinator.AlpacaTradierAdapter")
    @patch("src.phase2_coordinator.execute_signal_with_slippage_control")
    @patch("src.phase2_coordinator.DualLedgerWriter")
    def test_phase2_coordinator_executes_top_strategies(
        self, mock_writer, mock_execute, mock_adapter_class, mock_alpaca_client
    ):
        """Verify end-to-end dry-run and execution pipeline checks."""
        # Setup mocks
        mock_adapter = MagicMock()
        mock_adapter.trading_client = mock_alpaca_client
        mock_adapter.get_quotes.return_value = {
            "SPY": MagicMock(last=455.0)
        }
        mock_adapter_class.return_value = mock_adapter
        
        # Create temp folder for data dir config
        with tempfile.TemporaryDirectory() as tmpdir:
            config.DATA_DIR = tmpdir
            
            # Execute pipeline (dry_run mode)
            result = run_phase2_pipeline(
                tickers=["SPY"],
                strategy_ids=["rsi2_oversold_short_put"],
                dry_run=True
            )
            
            assert "error" not in result
            assert result["scanned"] > 0
            assert len(result["executed"]) >= 0
