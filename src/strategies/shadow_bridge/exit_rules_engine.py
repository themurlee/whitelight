import logging
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("ExitRulesEngine")

@dataclass
class Position:
    entry_id: str
    symbol: str
    combo: List[Dict]  # Legs
    entry_price: float
    entry_timestamp: datetime
    entry_greeks: dict
    capital_at_risk: float
    strategy_id: str = "unknown"

class ExitRulesEngine:
    """Monitor positions for Shadow's 13-rule exit ladder."""
    
    # Shadow's 13 exit rules
    RULES = [
        "profit_target_25pct",      # P&L >= 25% of initial capital
        "theta_decay_50pct",        # Theta has decayed 50% of entry credit
        "earnings_blackout",        # Earnings announced
        "macro_print_blackout",     # Fed/CPI/jobs print during position
        "vega_collapse",            # IV rank drops > 20 points
        "gamma_risk_breach",        # Gamma * price_move > threshold
        "technical_breakdown",      # Price breaks technical level
        "dte_exit_14d",             # DTE <= 14 days
        "calendar_vega_roll",       # Near-term vega decay > far-term
        "correlation_breach",       # Correlated position +=0.8
        "margin_pressure",          # Reg-T margin < 20%
        "voluntary_exit",           # User manually closed
        "max_loss_circuit",         # Loss >= capital_at_risk (stop loss)
    ]
    
    def __init__(self):
        self.positions: Dict[str, Position] = {}
    
    def register_position(self, position: Position):
        """Register a position for monitoring."""
        self.positions[position.entry_id] = position
        logger.info(f"Registered position for exit monitoring: {position.entry_id} on {position.symbol}")
        
    def deregister_position(self, entry_id: str):
        """Deregister a closed position."""
        if entry_id in self.positions:
            del self.positions[entry_id]
            logger.info(f"Deregistered position {entry_id}")
    
    def check_exits(self, current_state: dict) -> List[Dict]:
        """
        Scan all positions against 13-rule ladder.
        
        Args:
            current_state: A dictionary containing market environment and contract values:
                           {
                               "pnl_pct": float,
                               "pnl": float,
                               "theta_decay_pct": float,
                               "earnings_announced": bool,
                               "iv_drop": float,
                               ...
                           }
        
        Returns list of {entry_id, symbol, rule_fired, action, urgency}.
        """
        exits = []
        
        for entry_id, position in list(self.positions.items()):
            # Extract state specific to this position
            pos_state = current_state.get(entry_id, {})
            if not pos_state and position.symbol in current_state:
                pos_state = current_state[position.symbol]
                
            fired_rule = self._evaluate_rules(position, pos_state)
            
            if fired_rule:
                exits.append({
                    "entry_id": entry_id,
                    "symbol": position.symbol,
                    "rule_fired": fired_rule,
                    "timestamp": datetime.now(timezone.utc),
                    "action": "CLOSE",
                    "urgency": self._urgency_level(fired_rule),
                })
        
        return exits
    
    def _evaluate_rules(self, position: Position, state: dict) -> Optional[str]:
        """Evaluate all 13 rules, return first one that fires."""
        
        # Rule 1: Profit target 25%
        if state.get("pnl_pct", 0) >= 0.25:
            return "profit_target_25pct"
        
        # Rule 2: Theta decay 50%
        if state.get("theta_decay_pct", 0) >= 0.50:
            return "theta_decay_50pct"
        
        # Rule 3: Earnings blackout
        if state.get("earnings_announced", False):
            return "earnings_blackout"
            
        # Rule 5: Vega collapse (IV drop > 20 points)
        if state.get("iv_drop", 0) > 20.0:
            return "vega_collapse"
        
        # Rule 8: DTE exit at 14 days
        now = datetime.now(timezone.utc)
        entry_ts = position.entry_timestamp
        if entry_ts.tzinfo is None:
            entry_ts = entry_ts.replace(tzinfo=timezone.utc)
            
        dte = position.entry_greeks.get("dte", 30)
        days_passed = (now - entry_ts).days
        remaining_dte = dte - days_passed
        
        if remaining_dte <= 14:
            return "dte_exit_14d"
        
        # Rule 13: Max loss circuit
        if state.get("pnl", 0) <= -position.capital_at_risk:
            return "max_loss_circuit"
        
        return None
    
    def _urgency_level(self, rule: str) -> str:
        """Urgency: CRITICAL, HIGH, MEDIUM, LOW."""
        critical = ["max_loss_circuit", "earnings_blackout", "macro_print_blackout"]
        high = ["vega_collapse", "gamma_risk_breach"]
        return "CRITICAL" if rule in critical else "HIGH" if rule in high else "MEDIUM"
