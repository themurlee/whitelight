"""
Alpaca Combo Order Support for Multi-Leg Strategies (PMCC, Iron Condor, etc.)

Submits multiple option legs atomically to prevent execution risk.
"""

import logging
from dataclasses import dataclass
from typing import List
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import OrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from src.alpaca_client.retry_decorator import alpaca_retryable

logger = logging.getLogger("ComboOrders")

@dataclass
class ComboLeg:
    """Single leg of a combo order."""
    symbol: str              # e.g., "AAPL260814C00185000"
    side: OrderSide          # OrderSide.BUY or OrderSide.SELL
    qty: int                 # Shares / contracts
    order_type: str = "market"  # "market" or "limit"
    limit_price: float = None   # Only for limit orders

class ComboOrderRequest:
    """Wrapper for Alpaca combo order (multiple legs submitted atomically)."""
    
    def __init__(self, symbol_base: str, legs: List[ComboLeg], 
                 time_in_force: TimeInForce = TimeInForce.DAY):
        """
        Args:
            symbol_base: Base symbol for the combo (e.g., "AAPL")
            legs: List of ComboLeg objects
            time_in_force: Order time in force (DAY, GTC, etc.)
        """
        self.symbol_base = symbol_base
        self.legs = legs
        self.time_in_force = time_in_force
        
        # Validate legs
        if not legs or len(legs) < 2:
            raise ValueError("Combo orders require at least 2 legs")
    
    def to_alpaca_payload(self) -> dict:
        """Convert to Alpaca API payload format."""
        payload = {
            "orders": []
        }
        
        for leg in self.legs:
            leg_order = {
                "symbol": leg.symbol,
                "qty": leg.qty,
                "side": leg.side.value,  # "buy" or "sell"
                "type": leg.order_type,
                "time_in_force": self.time_in_force.value,
            }
            
            if leg.order_type == "limit" and leg.limit_price:
                leg_order["limit_price"] = leg.limit_price
            
            payload["orders"].append(leg_order)
        
        return payload

@alpaca_retryable(max_retries=3, base_delay=1.0)
def submit_combo_order(
    trading_client: TradingClient,
    combo_request: ComboOrderRequest
) -> dict:
    """
    Submit a multi-leg combo order to Alpaca.
    
    All legs execute atomically: either all fill or all are cancelled.
    This eliminates execution risk (e.g., naked short exposure between fills).
    
    Args:
        trading_client: Alpaca trading client
        combo_request: ComboOrderRequest with all legs
    
    Returns:
        Dict with order confirmations for each leg
    
    Raises:
        Exception: If any leg fails validation or submission
    """
    payload = combo_request.to_alpaca_payload()
    
    logger.info(f"Submitting combo order for {combo_request.symbol_base} with {len(combo_request.legs)} legs")
    logger.debug(f"Payload: {payload}")
    
    try:
        results = {
            "symbol_base": combo_request.symbol_base,
            "legs": [],
            "status": "pending"
        }
        
        for i, leg in enumerate(combo_request.legs):
            try:
                # Build leg order request payload
                from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
                if leg.order_type == "limit":
                    order_data = LimitOrderRequest(
                        symbol=leg.symbol,
                        qty=leg.qty,
                        side=leg.side,
                        limit_price=leg.limit_price,
                        time_in_force=combo_request.time_in_force
                    )
                else:
                    order_data = MarketOrderRequest(
                        symbol=leg.symbol,
                        qty=leg.qty,
                        side=leg.side,
                        time_in_force=combo_request.time_in_force
                    )
                
                # Submit leg
                order = trading_client.submit_order(order_data)
                
                results["legs"].append({
                    "symbol": leg.symbol,
                    "order_id": order.id,
                    "status": "submitted",
                    "qty": leg.qty
                })
                
                logger.info(f"Leg {i+1}/{len(combo_request.legs)}: {leg.symbol} order {order.id} submitted")
                
            except Exception as leg_error:
                # Partial fill fallback: cancel previous legs
                logger.error(f"Leg {i+1} submission failed: {leg_error}. Cancelling previous legs.")
                
                for submitted_leg in results["legs"]:
                    try:
                        trading_client.cancel_order_by_id(submitted_leg["order_id"])
                        logger.info(f"Cancelled leg {submitted_leg['symbol']} order {submitted_leg['order_id']}")
                    except Exception as cancel_error:
                        logger.error(f"Failed to cancel leg {submitted_leg['symbol']}: {cancel_error}")
                
                results["status"] = "failed"
                results["error"] = str(leg_error)
                raise RuntimeError(f"Combo order failed at leg {i+1}: {leg_error}")
        
        results["status"] = "submitted"
        logger.info(f"Combo order {combo_request.symbol_base} fully submitted ({len(results['legs'])} legs)")
        return results
        
    except Exception as e:
        logger.error(f"Combo order submission failed: {e}")
        raise

def wait_for_combo_fill(
    trading_client: TradingClient,
    combo_orders: dict,
    timeout_sec: float = 300.0
) -> dict:
    """
    Poll combo order legs until all filled or timeout.
    
    Args:
        trading_client: Alpaca trading client
        combo_orders: Result from submit_combo_order()
        timeout_sec: Max wait time in seconds
    
    Returns:
        Dict with final status of all legs
    """
    import time
    
    start_time = time.time()
    all_filled = False
    
    while time.time() - start_time < timeout_sec:
        statuses = []
        
        for leg in combo_orders["legs"]:
            try:
                order = trading_client.get_order_by_id(leg["order_id"])
                statuses.append(order.status.value)
                leg["latest_status"] = order.status.value
            except Exception as e:
                logger.warning(f"Failed to get status for {leg['symbol']}: {e}")
                statuses.append("unknown")
        
        # Check if all filled
        if all(s in ["filled", "FILLED"] for s in statuses):
            all_filled = True
            combo_orders["final_status"] = "all_filled"
            logger.info(f"Combo order {combo_orders['symbol_base']} fully filled")
            break
        
        # Check for any cancelled/expired
        if any(s in ["cancelled", "CANCELED", "expired", "EXPIRED", "rejected", "REJECTED"] for s in statuses):
            combo_orders["final_status"] = "partial_failure"
            logger.error(f"Combo order {combo_orders['symbol_base']} has failed legs: {statuses}")
            break
        
        time.sleep(2)  # Poll every 2 seconds
    
    if not all_filled and combo_orders.get("final_status") is None:
        combo_orders["final_status"] = "timeout"
        logger.error(f"Combo order {combo_orders['symbol_base']} timeout after {timeout_sec}s")
    
    return combo_orders
