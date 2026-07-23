import sys
import logging
from typing import List, Dict
from src.options.greeks import calculate_greeks as wl_greeks

logger = logging.getLogger("GreeksCalculatorBridge")

class GreeksCalculatorBridge:
    """Integrate Shadow's Greeks with WhiteLight's execution."""
    
    def __init__(self, shadow_repo_path: str = None):
        self.shadow_repo_path = shadow_repo_path
        if shadow_repo_path:
            sys.path.insert(0, shadow_repo_path)
    
    def calculate_combo_greeks(
        self,
        combo: List[Dict],  # [{"strike": 450, "type": "call", ...}, ...]
        current_price: float,
        iv_rank: float,
        dte: int
    ) -> Dict:
        """
        Calculate Greeks for the entire combo (multi-leg position).
        
        Returns:
        {
            "delta": 0.45,        # Net delta of combo
            "gamma": 0.012,       # Net gamma
            "vega": 2.3,          # Net vega
            "theta": -0.15,       # Net theta per day
            "is_theta_positive": False,  # Good/bad for theta?
        }
        """
        total_delta = 0.0
        total_gamma = 0.0
        total_vega = 0.0
        total_theta = 0.0
        
        # Calculate expiry date string based on DTE
        from datetime import datetime, timedelta
        expiry_date = datetime.now() + timedelta(days=max(1, dte))
        expiry_str = expiry_date.strftime("%Y-%m-%d")
        
        for leg in combo:
            # Normalize leg parameters
            strike = float(leg.get("strike", current_price))
            opt_type = leg.get("type", "call").lower()
            side = leg.get("side", "long").lower()
            
            # Use OCC symbol or fallback to calculate
            greeks = wl_greeks(
                symbol=leg.get("contract_id", leg.get("symbol", "")),
                strike=strike,
                expiry=expiry_str,
                option_type=opt_type,
                current_price=current_price,
                iv_rank=iv_rank
            )
            
            # Adjust sign if short
            # In some combos, side is represented as -1 for short and 1 for long
            is_short = False
            if isinstance(side, str) and side == "short":
                is_short = True
            elif isinstance(side, (int, float)) and side < 0:
                is_short = True
            elif leg.get("side_num", 1) < 0:
                is_short = True
                
            multiplier = -1 if is_short else 1
            
            total_delta += greeks.get("delta", 0.0) * multiplier
            total_gamma += greeks.get("gamma", 0.0) * multiplier
            total_vega += greeks.get("vega", 0.0) * multiplier
            total_theta += greeks.get("theta", 0.0) * multiplier
        
        return {
            "delta": round(total_delta, 4),
            "gamma": round(total_gamma, 4),
            "vega": round(total_vega, 4),
            "theta": round(total_theta, 4),
            "is_theta_positive": total_theta > 0,
            "is_vega_negative": total_vega < 0,  # Short vega
        }
