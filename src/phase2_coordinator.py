import os
import sys
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import src.config as config
from src.strategies.shadow_bridge.strategy_registry import StrategyRegistry
from src.strategies.shadow_bridge.contract_selector import ContractSelectorBridge
from src.strategies.shadow_bridge.greeks_calculator import GreeksCalculatorBridge
from src.strategies.shadow_bridge.exit_rules_engine import ExitRulesEngine, Position
from src.strategies.shadow_bridge.market_data_adapter import AlpacaTradierAdapter
from src.risk.circuit_breaker import CircuitBreaker
from src.execution.limit_order_wrapper import execute_signal_with_slippage_control
from src.execution.dual_ledger_writer import DualLedgerWriter
from src.alerting.slack_notifier import post_alert

logger = logging.getLogger("Phase2Coordinator")

def log(msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [PHASE2_COORDINATOR] [{level}] {msg}")

def run_phase2_pipeline(
    tickers: List[str],
    strategy_ids: Optional[List[str]] = None,
    dry_run: bool = False,
    max_strategies_per_symbol: int = 3
) -> Dict[str, Any]:
    """
    Main Phase 2 Coordinator Pipeline.
    
    1. Loads and instantiates Shadow strategies from registry.
    2. Gathers current stock quotes and options chains using AlpacaTradierAdapter.
    3. Runs strategy scans in parallel to produce entry signals.
    4. For each ENTRY signal:
       - Maps the combo to active Alpaca options contracts.
       - Aggregates Delta/Gamma/Vega/Theta Greeks.
       - Gates the trade through the CircuitBreaker.
       - Executes limit order legs with slippage validation.
       - Atomically dual-writes to state.json and entries.jsonl.
       - Registers the active position with the ExitRulesEngine.
    """
    cycle_id = str(uuid.uuid4())
    log(f"Phase 2 pipeline starting. Cycle ID: {cycle_id} | Tickers: {tickers} | dry_run={dry_run}")
    post_alert(f"🚀 [whitelight-phase2] Started execution cycle {cycle_id} for tickers: {tickers}")
    
    if not config.API_KEY or not config.SECRET_KEY:
        log("Alpaca credentials missing. Skipping execution.", "ERROR")
        return {"error": "Missing Alpaca credentials"}
        
    try:
        # Initialize registry & load strategies
        registry = StrategyRegistry(config.SHADOW_REPO_PATH)
        all_strategies = registry.load_all_strategies()
        log(f"Loaded {len(all_strategies)} strategies from Shadow repository.")
        
        # If specific strategies were requested, filter to them
        if strategy_ids:
            registry.strategies = {k: v for k, v in registry.strategies.items() if k in strategy_ids}
            log(f"Filtered strategy registry to: {list(registry.strategies.keys())}")
            
        # Initialize Alpaca adapter and selector/greeks/writer tools
        adapter = AlpacaTradierAdapter(config.API_KEY, config.SECRET_KEY)
        contract_selector = ContractSelectorBridge(adapter.trading_client)
        greeks_calc = GreeksCalculatorBridge(config.SHADOW_REPO_PATH)
        
        # Fetch account details for circuit breaker
        account = adapter.trading_client.get_account()
        account_value = float(account.portfolio_value)
        open_positions = adapter.trading_client.get_all_positions()
        open_tickers = [p.symbol for p in open_positions]
        
        cb = CircuitBreaker(baseline_account_value=account_value)
        dual_writer = DualLedgerWriter(config.DATA_DIR, config.DATA_DIR) # Output to WhiteLight data dir
        exit_engine = ExitRulesEngine()
        
        # Fetch market quotes for tickers
        market_data = {}
        quotes = adapter.get_quotes(tickers)
        for t in tickers:
            if t in quotes:
                market_data[t] = {
                    "close": quotes[t].last,
                    "iv_rank": 50.0  # Default IV Rank
                }
                
        # Scan strategies
        log("Running parallel scans across all strategies...")
        scan_results = registry.scan_all_strategies(market_data)
        log(f"Scan complete. Found {len(scan_results)} strategy scan signals.")
        
        # Filter entry signals
        entries = [r for r in scan_results if r["signal"] == "ENTRY"]
        # Sort by confidence descending
        entries.sort(key=lambda x: x.get("confidence", 0.5), reverse=True)
        log(f"Identified {len(entries)} entry signals to evaluate.")
        
        executed_trades = []
        
        # Iterate over entry signals and execute them
        for entry_signal in entries[:max_strategies_per_symbol * len(tickers)]:
            strategy_id = entry_signal["strategy_id"]
            symbol = entry_signal["symbol"]
            combo = entry_signal["proposed_combo"]
            confidence = entry_signal["confidence"]
            
            log(f"Evaluating signal for {strategy_id} on {symbol} (confidence={confidence:.2f})")
            
            # Select contracts
            current_stock_price = market_data[symbol]["close"]
            contract_result = contract_selector.select_contracts(
                symbol=symbol,
                proposed_combo=combo,
                current_price=current_stock_price
            )
            
            if not contract_result["valid"]:
                log(f"Contract selection failed for {strategy_id} on {symbol}: {contract_result.get('reason')}", "WARNING")
                continue
                
            # Aggregate Greeks
            # Estimate DTE based on first leg
            dte = 30
            if contract_result["combo"]:
                # Try to calculate DTE
                from src.selector import calculate_dte
                try:
                    exp = contract_result["combo"][0]["expiry"]
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    dte = calculate_dte(exp, today_str)
                except Exception:
                    pass
                    
            greeks = greeks_calc.calculate_combo_greeks(
                combo=contract_result["combo"],
                current_price=current_stock_price,
                iv_rank=market_data[symbol]["iv_rank"],
                dte=dte
            )
            
            # Check Circuit Breaker
            # Use total credit/debit cost as the proxy for price
            cost = abs(contract_result["total_cost"])
            can_execute, cb_reason = cb.can_execute(
                ticker=symbol,
                qty=1,
                price=cost,
                account_value=account_value,
                open_tickers=open_tickers,
                trading_client=adapter.trading_client
            )
            
            if not can_execute:
                log(f"Circuit breaker rejected execution for {strategy_id} on {symbol}: {cb_reason}", "WARNING")
                continue
                
            # Execute legs
            if dry_run:
                log(f"[DRY RUN] Would execute {strategy_id} on {symbol} with combo: {contract_result['combo']}")
                executed_trades.append({
                    "strategy_id": strategy_id,
                    "symbol": symbol,
                    "status": "DRY_RUN",
                    "greeks": greeks
                })
                continue
                
            # Real execution
            try:
                filled_legs = []
                for i, leg in enumerate(contract_result["combo"]):
                    leg_symbol = leg["contract_id"]
                    leg_mid = leg["mid"]
                    leg_qty = 1
                    leg_side = "BUY" if leg["side"] == "long" else "SELL"
                    
                    log(f"Submitting leg order: {leg_side} {leg_qty} {leg_symbol} @ limit {leg_mid:.2f}")
                    
                    success = execute_signal_with_slippage_control(
                        trading_client=adapter.trading_client,
                        ticker=leg_symbol,
                        signal_close=leg_mid,
                        qty=leg_qty,
                        side=leg_side
                    )
                    
                    if success:
                        filled_legs.append(leg)
                    else:
                        log(f"Leg execution failed for {leg_symbol}. Aborting combo.", "ERROR")
                        break
                        
                if len(filled_legs) == len(contract_result["combo"]):
                    # Dual-write execution
                    # Capital at risk is approximated as 10% of stock notional or debit width
                    capital_at_risk = cost * 100.0 if cost > 0 else 500.0
                    
                    exec_res = {
                        "symbol": symbol,
                        "filled_at": datetime.now(timezone.utc).isoformat() + "Z",
                        "qty": 1,
                        "side": "BUY" if contract_result["total_cost"] < 0 else "SELL", # debit is buy, credit is sell
                        "strike_price": contract_result["combo"][0]["strike"],
                        "expiration_date": contract_result["combo"][0]["expiry"],
                        "option_type": contract_result["combo"][0]["type"],
                        "capital_at_risk": capital_at_risk
                    }
                    
                    # Assume 2% slippage for worst fill, 2% better for optimistic
                    worst_fill = contract_result["total_cost"] * 1.02 if contract_result["total_cost"] > 0 else contract_result["total_cost"] * 0.98
                    best_fill = contract_result["total_cost"] * 0.98 if contract_result["total_cost"] > 0 else contract_result["total_cost"] * 1.02
                    
                    dual_writer.write_execution(
                        execution_result=exec_res,
                        worst_fill=worst_fill,
                        base_fill=contract_result["total_cost"],
                        optimistic_fill=best_fill,
                        greeks=greeks,
                        strategy_id=strategy_id,
                        cycle_id=cycle_id
                    )
                    
                    # Register with Exit Engine
                    position = Position(
                        entry_id=f"{strategy_id}_{symbol}_{datetime.now(timezone.utc).isoformat()}",
                        symbol=symbol,
                        combo=contract_result["combo"],
                        entry_price=contract_result["total_cost"],
                        entry_timestamp=datetime.now(timezone.utc),
                        entry_greeks=greeks,
                        capital_at_risk=capital_at_risk,
                        strategy_id=strategy_id
                    )
                    exit_engine.register_position(position)
                    
                    executed_trades.append({
                        "strategy_id": strategy_id,
                        "symbol": symbol,
                        "status": "EXECUTED",
                        "greeks": greeks
                    })
                    post_alert(f"✅ [whitelight-phase2] Executed {strategy_id} on {symbol} (cost={contract_result['total_cost']:.2f})")
                else:
                    log(f"Partial fills occurred. Out of {len(contract_result['combo'])} legs, only {len(filled_legs)} filled.", "ERROR")
                    executed_trades.append({
                        "strategy_id": strategy_id,
                        "symbol": symbol,
                        "status": "PARTIAL_FILL",
                        "greeks": greeks
                    })
            except Exception as e:
                log(f"Execution crashed for {strategy_id} on {symbol}: {e}", "ERROR")
                executed_trades.append({
                    "strategy_id": strategy_id,
                    "symbol": symbol,
                    "status": "FAILED",
                    "error": str(e)
                })
                
        summary = f"Phase 2 cycle complete. Scanned {len(scan_results)} strategies, executed {len(executed_trades)} trades."
        log(summary)
        post_alert(f"🏁 [whitelight-phase2] Cycle complete: {cycle_id}\nExecuted: {len(executed_trades)} trades.")
        
        return {
            "cycle_id": cycle_id,
            "scanned": len(scan_results),
            "executed": executed_trades
        }
        
    except Exception as e:
        log(f"Phase 2 coordinator failed: {e}", "ERROR")
        post_alert(f"❌ [whitelight-phase2] Coordinator failed: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Phase 2 Coordinator for WhiteLight")
    parser.add_argument("tickers", nargs="*", help="Ticker symbols to scan (default: SPY)")
    parser.add_argument("--dry-run", action="store_true", help="Scan and select but skip order execution")
    args = parser.parse_args()
    
    tickers = [t.upper() for t in args.tickers] if args.tickers else ["SPY", "QQQ", "IWM", "AAPL", "MSFT"]
    run_phase2_pipeline(tickers, dry_run=args.dry_run)
