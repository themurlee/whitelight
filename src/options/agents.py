import json
import logging
from typing import Dict, Any
from src.options.llm_adapters import LLMFactory

logger = logging.getLogger(__name__)

PROPOSER_SYSTEM_PROMPT = """You are a Senior Options Desk Proposer Agent.
Your job is to analyze stock technicals, option Greeks, and DTE horizon (0-7D, 30-90D, 180D, 360D LEAP) to propose high-probability option trades (BUY_CALL, BUY_PUT, or NO_TRADE).

RULES:
- For 0-7D Weeklys: Focus on intraday 5-min VWAP momentum & RSI-7.
- For 30-90D Earnings Swings: Recommend Delta >= 0.40 options when IV Rank < 50%.
- For 180D/360D LEAPS: Recommend Deep ITM (Delta >= 0.70) or ATM (Delta >= 0.40) for low Theta decay holding.
- Respond STRICTLY in valid JSON.

JSON OUTPUT FORMAT:
{
  "action": "BUY_CALL" | "BUY_PUT" | "NO_TRADE",
  "contract_type": "CALL" | "PUT" | "NONE",
  "target_dte": 7 | 60 | 180 | 360,
  "confidence": 85,
  "target_strike_offset_pct": 1.0,
  "suggested_risk_pct": 2.0,
  "reasoning": "Technical & Greeks analysis explanation"
}
"""

VALIDATOR_SYSTEM_PROMPT = """You are a Wall Street Senior Risk Manager auditing Option Trades.
Your job is to strictly enforce these 5 Professional Options Trader Rules:

1. ORDER TYPE: Must use LIMIT order at Midpoint. Reject Market Orders.
2. LIQUIDITY: Reject contracts with Open Interest < 500 or Spread > 10%.
3. IV RANK: For 30-90D swings, reject if IV Rank > 50% (Vega collapse risk). Recommend exit 2 days before earnings.
4. DELTA: Require Delta >= 0.40. Reject OTM lottery tickets with Delta < 0.35.
5. POSITION SIZING: Max allocation capped at 2% of total account equity.
6. 0-7D STOP LOSS: Enforce mandatory 25% premium stop-loss on weekly scalps.

JSON OUTPUT FORMAT:
{
  "approved": true | false,
  "risk_rating": "LOW" | "MEDIUM" | "HIGH",
  "alignment_score": 92,
  "validation_notes": "Explanation of risk audit decision enforcing the 5 Trader Rules",
  "final_action": "EXECUTE" | "REJECT"
}
"""

class ProposerAgent:
    def __init__(self, provider: str = "gemini", model_name: str = "gemini-2.5-flash"):
        self.adapter = LLMFactory.get_adapter(provider=provider, model_name=model_name)

    def propose(self, ticker: str, signals: Dict[str, Any], timeframe: str = "WEEKLY") -> Dict[str, Any]:
        user_prompt = f"Ticker: {ticker}\nTimeframe Bucket: {timeframe}\nSignals & Data:\n{json.dumps(signals, indent=2)}"
        return self.adapter.generate_json(PROPOSER_SYSTEM_PROMPT, user_prompt)

class ValidatorAgent:
    def __init__(self, provider: str = "gemini", model_name: str = "gemini-2.5-flash"):
        self.adapter = LLMFactory.get_adapter(provider=provider, model_name=model_name)

    def validate(self, ticker: str, signals: Dict[str, Any], proposal: Dict[str, Any]) -> Dict[str, Any]:
        user_prompt = f"Ticker: {ticker}\nSignals & Data:\n{json.dumps(signals, indent=2)}\n\nProposal:\n{json.dumps(proposal, indent=2)}"
        return self.adapter.generate_json(VALIDATOR_SYSTEM_PROMPT, user_prompt)

class DualAgentPipeline:
    def __init__(
        self,
        proposer_provider: str = "gemini",
        proposer_model: str = "gemini-2.5-flash",
        validator_provider: str = "gemini",
        validator_model: str = "gemini-2.5-flash"
    ):
        self.proposer = ProposerAgent(provider=proposer_provider, model_name=proposer_model)
        self.validator = ValidatorAgent(provider=validator_provider, model_name=validator_model)

    def run(self, ticker: str, signals: Dict[str, Any], timeframe: str = "WEEKLY") -> Dict[str, Any]:
        proposal = self.proposer.propose(ticker, signals, timeframe)

        if proposal.get("action") == "NO_TRADE":
            return {
                "status": "COMPLETED",
                "proposal": proposal,
                "validation": {
                    "approved": False,
                    "risk_rating": "NONE",
                    "alignment_score": 100,
                    "validation_notes": "Proposer recommended NO_TRADE based on current market signals.",
                    "final_action": "NO_ACTION"
                },
                "execution_ready": False
            }

        validation = self.validator.validate(ticker, signals, proposal)
        execution_ready = validation.get("approved", False) and validation.get("final_action") == "EXECUTE"

        return {
            "status": "COMPLETED",
            "proposal": proposal,
            "validation": validation,
            "execution_ready": execution_ready
        }
