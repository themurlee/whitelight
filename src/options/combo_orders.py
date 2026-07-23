"""
Alpaca Combo Order Support for Multi-Leg Strategies (PMCC, Iron Condor, etc.)

Submits multiple option legs atomically using native Alpaca exchange-level combo orders.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, OptionLegRequest
from alpaca.trading.enums import OrderSide, OrderClass, TimeInForce, PositionIntent
from src.alpaca_client.retry_decorator import alpaca_retryable

logger = logging.getLogger("ComboOrders")

@dataclass
class ComboLeg:
    """Single leg of a combo order."""
    symbol: str                              # e.g., "AAPL260814C00185000"
    side: OrderSide                          # OrderSide.BUY or OrderSide.SELL
    ratio: int = 1                           # Quantity ratio for the leg
    position_intent: Optional[PositionIntent] = None # PositionIntent.BUY_TO_OPEN etc.

class ComboOrderRequest:
    """Wrapper for native Alpaca multi-leg combo order (submitted atomically)."""
    
    def __init__(
        self,
        symbol_base: str,
        legs: List[ComboLeg],
        qty: int = 1,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY
    ):
        """
        Args:
            symbol_base: Base symbol for the combo (e.g., "AAPL")
            legs: List of ComboLeg objects
            qty: Overall strategy quantity (multiplier for leg ratios)
            order_type: "market" or "limit"
            limit_price: Net limit price for the combo (required if order_type is limit)
            time_in_force: Order time in force (DAY, GTC, etc.)
        """
        self.symbol_base = symbol_base
        self.legs = legs
        self.qty = qty
        self.order_type = order_type
        self.limit_price = limit_price
        self.time_in_force = time_in_force
        
        # Validate legs
        if not legs or len(legs) < 2:
            raise ValueError("Combo orders require at least 2 legs")
        if len(legs) > 4:
            raise ValueError("Alpaca multi-leg orders support a maximum of 4 legs")
            
        if order_type == "limit" and limit_price is None:
            raise ValueError("Limit price must be specified for limit combo orders")

@alpaca_retryable(max_retries=3, base_delay=1.0)
def submit_combo_order(
    trading_client: TradingClient,
    combo_request: ComboOrderRequest
) -> dict:
    """
    Submit a native multi-leg combo order to Alpaca.
    
    All legs execute atomically: either all fill or none fill at the exchange.
    This eliminates execution risk (e.g., naked short exposure between fills).
    
    Args:
        trading_client: Alpaca trading client
        combo_request: ComboOrderRequest with all legs
    
    Returns:
        Dict with overall order status and leg metadata
    
    Raises:
        Exception: If submission fails
    """
    # 1. Map to OptionLegRequest list
    leg_requests = []
    for leg in combo_request.legs:
        # Default position intent based on side if not specified
        intent = leg.position_intent
        if intent is None:
            intent = PositionIntent.BUY_TO_OPEN if leg.side == OrderSide.BUY else PositionIntent.SELL_TO_OPEN
            
        leg_requests.append(OptionLegRequest(
            symbol=leg.symbol,
            ratio_qty=leg.ratio,
            side=leg.side,
            position_intent=intent
        ))
        
    # 2. Build unified MLEG order request
    if combo_request.order_type == "limit":
        order_data = LimitOrderRequest(
            side=OrderSide.BUY,  # Unified combo side (usually defaults to BUY for structure purchase)
            order_class=OrderClass.MLEG,
            time_in_force=combo_request.time_in_force,
            legs=leg_requests,
            limit_price=combo_request.limit_price,
            qty=combo_request.qty
        )
    else:
        order_data = MarketOrderRequest(
            side=OrderSide.BUY,
            order_class=OrderClass.MLEG,
            time_in_force=combo_request.time_in_force,
            legs=leg_requests,
            qty=combo_request.qty
        )
        
    logger.info(f"Submitting native MLEG combo order for {combo_request.symbol_base} (qty: {combo_request.qty}) with {len(combo_request.legs)} legs")
    
    try:
        order = trading_client.submit_order(order_data)
        logger.info(f"Native MLEG order {order.id} submitted successfully")
        
        results = {
            "symbol_base": combo_request.symbol_base,
            "order_id": order.id,
            "status": order.status.value,
            "legs": [
                {
                    "symbol": leg.symbol,
                    "order_id": order.id,
                    "status": order.status.value,
                    "qty": leg.ratio * combo_request.qty
                } for leg in combo_request.legs
            ]
        }
        return results
    except Exception as e:
        logger.error(f"Native MLEG order submission failed: {e}")
        raise

def wait_for_combo_fill(
    trading_client: TradingClient,
    combo_orders: dict,
    timeout_sec: float = 300.0
) -> dict:
    """
    Poll native MLEG order until filled or timeout.
    
    Args:
        trading_client: Alpaca trading client
        combo_orders: Result from submit_combo_order()
        timeout_sec: Max wait time in seconds
    
    Returns:
        Dict with final status of all legs
    """
    import time
    
    start_time = time.time()
    order_id = combo_orders["order_id"]
    
    while time.time() - start_time < timeout_sec:
        try:
            order = trading_client.get_order_by_id(order_id)
            status = order.status.value.lower()
            combo_orders["status"] = status
            
            # Map sub-leg statuses if returned by Alpaca
            if hasattr(order, "legs") and order.legs:
                for idx, leg_order in enumerate(order.legs):
                    if idx < len(combo_orders["legs"]):
                        combo_orders["legs"][idx]["latest_status"] = leg_order.status.value
            else:
                for leg in combo_orders["legs"]:
                    leg["latest_status"] = status
                    
            if status == "filled":
                combo_orders["final_status"] = "all_filled"
                logger.info(f"Native MLEG order {order_id} fully filled")
                break
            elif status in ["cancelled", "canceled", "expired", "rejected"]:
                combo_orders["final_status"] = "failed"
                logger.error(f"Native MLEG order {order_id} failed: {status}")
                break
        except Exception as e:
            logger.warning(f"Failed to get order status for {order_id}: {e}")
            
        time.sleep(2)
        
    if combo_orders.get("final_status") is None:
        combo_orders["final_status"] = "timeout"
        logger.error(f"Native MLEG order {order_id} timed out after {timeout_sec}s")
        
    return combo_orders
