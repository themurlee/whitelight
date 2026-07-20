"""
backtest.py — WhiteLight event-driven backtesting engine.

Design goals (matches the gaps identified in the repo audit):
  1. Structural look-ahead prevention. Strategies never receive the current
     bar. The engine only ever hands a strategy function the history UP TO
     (not including) the bar it is about to fill on. This is enforced by
     slicing, not by convention (i.e. not "remember to .shift(1)").
  2. Realistic fills. Orders decided at bar i-1 fill at bar i's OPEN, never
     at bar i-1's close.
  3. Explicit transaction cost modeling for both equities (commission-free
     on Alpaca, but slippage is real) and options (per-contract fee +
     spread-crossing cost).
  4. Drawdown reporting that includes DURATION, not just depth, since the
     circuit breaker in execution.py is duration-sensitive (7-day window).
  5. Walk-forward validation as a first-class citizen, not an afterthought,
     with an explicit overfit flag rather than just raw numbers to eyeball.

This module has no dependency on Alpaca, MCP, or any broker — it operates
purely on OHLCV DataFrames so it can be unit tested with synthetic data and
reused for both the equity strategy (strategy.py) and, once options-chain
history is available, the options selectors.

Usage
-----
    from backtest import Backtester, CostModel, sma_crossover_example

    bt = Backtester(data, cost_model=CostModel(asset_type="equity"))
    result = bt.run(sma_crossover_example)
    print(result.summary())

See __main__ at the bottom for a runnable end-to-end example.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence
import itertools
import math

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Cost model
# --------------------------------------------------------------------------- #

@dataclass
class CostModel:
    """
    Transaction cost model. Two asset types are supported because equities
    and options have fundamentally different cost structures on Alpaca:

      equity  -> commission-free, cost is almost entirely slippage
      option  -> per-contract commission + you typically cross some
                 fraction of the bid/ask spread to get filled

    slippage_bps        : equities only. Applied against the fill price.
    commission_per_contract : options only. Per contract, per leg.
    option_spread_capture   : fraction of the quoted bid/ask spread you pay
                               to cross (0.5 = you pay the midpoint spread,
                               1.0 = you pay the full spread, worst case).
    """
    asset_type: str = "equity"                 # "equity" | "option"
    slippage_bps: float = 2.0                   # equities: bps of price
    commission_per_contract: float = 0.65        # options: $ per contract
    option_spread_capture: float = 0.5           # options: fraction of spread paid
    contract_multiplier: int = 100                # options: shares per contract

    def fill_price(self, quoted_price: float, side: int, spread: Optional[float] = None) -> float:
        """
        side: +1 for buy, -1 for sell.
        Returns the effective fill price after slippage/spread cost.
        """
        if self.asset_type == "equity":
            slip = quoted_price * (self.slippage_bps / 10_000.0)
            return quoted_price + slip * side
        else:
            if spread is None:
                spread = quoted_price * 0.02  # fallback: assume 2% wide market
            half_cost = spread * self.option_spread_capture
            return quoted_price + half_cost * side

    def commission(self, qty: float) -> float:
        if self.asset_type == "equity":
            return 0.0
        return self.commission_per_contract * abs(qty)


# --------------------------------------------------------------------------- #
# Trade / result records
# --------------------------------------------------------------------------- #

@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp]
    side: int              # +1 long, -1 short
    qty: float
    entry_price: float
    exit_price: Optional[float] = None
    commission_paid: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.exit_time is None

    @property
    def pnl(self) -> Optional[float]:
        if self.exit_price is None:
            return None
        gross = (self.exit_price - self.entry_price) * self.qty * self.side
        return gross - self.commission_paid

    @property
    def pnl_pct(self) -> Optional[float]:
        if self.exit_price is None:
            return None
        return (self.exit_price / self.entry_price - 1.0) * self.side


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: list[Trade]
    metrics: dict = field(default_factory=dict)

    def summary(self) -> str:
        m = self.metrics
        lines = [
            "WhiteLight Backtest Result",
            "-" * 32,
            f"Start            : {self.equity_curve.index[0]}",
            f"End              : {self.equity_curve.index[-1]}",
            f"Total Return     : {m['total_return_pct']:.2f}%",
            f"CAGR             : {m['cagr_pct']:.2f}%",
            f"Sharpe           : {m['sharpe']:.2f}",
            f"Sortino          : {m['sortino']:.2f}",
            f"Calmar           : {m['calmar']:.2f}",
            f"Max Drawdown     : {m['max_drawdown_pct']:.2f}%",
            f"Max DD Duration  : {m['max_drawdown_duration_days']} days",
            f"Win Rate         : {m['win_rate_pct']:.2f}%",
            f"Profit Factor    : {m['profit_factor']:.2f}",
            f"Trades           : {m['num_trades']}",
        ]
        return "\n".join(lines)

    @property
    def total_return(self) -> float:
        return self.metrics.get("total_return_pct", 0.0) / 100.0

    @property
    def sharpe(self) -> float:
        return self.metrics.get("sharpe", 0.0)

    @property
    def max_drawdown(self) -> float:
        return self.metrics.get("max_drawdown_pct", 0.0) / 100.0

    @property
    def num_trades(self) -> int:
        return self.metrics.get("num_trades", 0)

    @property
    def final_equity(self) -> float:
        return float(self.equity_curve.iloc[-1]) if len(self.equity_curve) > 0 else 0.0


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #

def _drawdown_series(equity: pd.Series) -> pd.Series:
    running_max = equity.cummax()
    return equity / running_max - 1.0


def max_drawdown(equity: pd.Series) -> float:
    return _drawdown_series(equity).min()


def max_drawdown_duration_days(equity: pd.Series) -> int:
    dd = _drawdown_series(equity)
    in_dd = dd < 0
    if not in_dd.any():
        return 0
    # find longest consecutive run of "underwater" days
    longest = current = 0
    start = None
    longest_start = longest_end = None
    for t, flag in in_dd.items():
        if flag:
            if current == 0:
                start = t
            current += 1
            if current > longest:
                longest = current
                longest_start, longest_end = start, t
        else:
            current = 0
    if longest_start is None:
        return 0
    return (longest_end - longest_start).days


def sharpe_ratio(returns: pd.Series, periods_per_year: int = 252, rf: float = 0.0) -> float:
    excess = returns - rf / periods_per_year
    if excess.std(ddof=0) == 0 or excess.empty:
        return 0.0
    return float(np.sqrt(periods_per_year) * excess.mean() / excess.std(ddof=0))


def sortino_ratio(returns: pd.Series, periods_per_year: int = 252, rf: float = 0.0) -> float:
    excess = returns - rf / periods_per_year
    downside = excess[excess < 0]
    if downside.std(ddof=0) == 0 or downside.empty:
        return 0.0
    return float(np.sqrt(periods_per_year) * excess.mean() / downside.std(ddof=0))


def calmar_ratio(cagr_pct: float, max_dd_pct: float) -> float:
    if max_dd_pct == 0:
        return 0.0
    return float(cagr_pct / abs(max_dd_pct))


def compute_metrics(equity: pd.Series, trades: Sequence[Trade],
                     periods_per_year: int = 252) -> dict:
    equity = equity.dropna()
    returns = equity.pct_change().dropna()

    n_years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / n_years) - 1.0

    closed = [t for t in trades if not t.is_open]
    wins = [t for t in closed if (t.pnl or 0) > 0]
    losses = [t for t in closed if (t.pnl or 0) <= 0]
    gross_profit = sum(t.pnl for t in wins) if wins else 0.0
    gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0.0

    mdd = max_drawdown(equity)

    return {
        "total_return_pct": total_return * 100,
        "cagr_pct": cagr * 100,
        "sharpe": sharpe_ratio(returns, periods_per_year),
        "sortino": sortino_ratio(returns, periods_per_year),
        "calmar": calmar_ratio(cagr * 100, mdd * 100),
        "max_drawdown_pct": mdd * 100,
        "max_drawdown_duration_days": max_drawdown_duration_days(equity),
        "num_trades": len(closed),
        "win_rate_pct": (len(wins) / len(closed) * 100) if closed else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0,
    }


# --------------------------------------------------------------------------- #
# Backtester
# --------------------------------------------------------------------------- #

StrategyFn = Callable[[pd.DataFrame], float]
# A strategy_fn receives ONLY history strictly before the current bar
# (i.e. data.iloc[:i], which excludes row i) and returns a target position
# in [-1.0, 1.0] representing fraction of capital to allocate, sign = side.


class Backtester:
    def __init__(self, data: pd.DataFrame, cost_model: Optional[CostModel] = None,
                 initial_capital: float = 100_000.0):
        """
        data must be a DataFrame indexed by datetime with at least
        ['open', 'high', 'low', 'close'] columns, sorted ascending.
        """
        required = {"open", "high", "low", "close"}
        missing = required - set(c.lower() for c in data.columns)
        if missing:
            raise ValueError(f"data missing required columns: {missing}")
        self.data = data.copy()
        self.data.columns = [c.lower() for c in self.data.columns]
        self.cost_model = cost_model or CostModel()
        self.initial_capital = initial_capital

    def run(self, strategy_fn: StrategyFn, warmup: int = 20) -> BacktestResult:
        """
        warmup: number of initial bars to skip before the strategy is
        allowed to trade (lets rolling indicators fill in without the
        strategy being called on near-empty history).
        """
        data = self.data
        n = len(data)
        cash = self.initial_capital
        position_qty = 0.0     # signed shares/contracts
        entry_price = None
        trades: list[Trade] = []
        equity_curve = pd.Series(index=data.index, dtype=float)
        equity_curve.iloc[:warmup] = self.initial_capital

        for i in range(warmup, n):
            # --- STRUCTURAL LOOK-AHEAD PREVENTION ---
            # strategy only ever sees rows [0, i), never row i itself.
            history = data.iloc[:i]
            target_frac = strategy_fn(history)
            target_frac = max(-1.0, min(1.0, float(target_frac)))

            bar = data.iloc[i]
            fill_ref_price = bar["open"]  # fills happen at the NEXT bar's open

            mark_price = bar["close"]
            current_equity = cash + position_qty * mark_price
            target_qty = (target_frac * current_equity) / fill_ref_price if fill_ref_price else 0.0

            delta_qty = target_qty - position_qty

            if abs(delta_qty) > 1e-9:
                side = 1 if delta_qty > 0 else -1
                fill_price = self.cost_model.fill_price(fill_ref_price, side)
                commission = self.cost_model.commission(delta_qty)

                # closing / reducing existing position -> realize a trade
                if position_qty != 0 and np.sign(delta_qty) != np.sign(position_qty):
                    closing_qty = min(abs(delta_qty), abs(position_qty))
                    trades.append(Trade(
                        entry_time=trades[-1].entry_time if trades and trades[-1].is_open else data.index[i],
                        exit_time=data.index[i],
                        side=int(np.sign(position_qty)),
                        qty=closing_qty,
                        entry_price=entry_price if entry_price else fill_price,
                        exit_price=fill_price,
                        commission_paid=commission,
                    ))

                cash -= delta_qty * fill_price + commission
                position_qty = target_qty
                entry_price = fill_price if position_qty != 0 else None

                if position_qty != 0 and (not trades or not trades[-1].is_open):
                    trades.append(Trade(
                        entry_time=data.index[i],
                        exit_time=None,
                        side=int(np.sign(position_qty)),
                        qty=abs(position_qty),
                        entry_price=fill_price,
                    ))

            equity_curve.iloc[i] = cash + position_qty * mark_price

        equity_curve = equity_curve.ffill()
        metrics = compute_metrics(equity_curve, trades)
        return BacktestResult(equity_curve=equity_curve, trades=trades, metrics=metrics)


# --------------------------------------------------------------------------- #
# Walk-forward validation
# --------------------------------------------------------------------------- #

@dataclass
class WalkForwardFold:
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp
    best_params: dict
    is_sharpe: float
    oos_sharpe: float
    overfit_flagged: bool


@dataclass
class WalkForwardResult:
    folds: list[WalkForwardFold]

    def summary(self) -> str:
        lines = ["Walk-Forward Validation", "-" * 32]
        for k, f in enumerate(self.folds, 1):
            flag = "  <-- OVERFIT FLAG" if f.overfit_flagged else ""
            lines.append(
                f"Fold {k}: IS [{f.is_start.date()} - {f.is_end.date()}] "
                f"OOS [{f.oos_start.date()} - {f.oos_end.date()}] "
                f"params={f.best_params} IS_sharpe={f.is_sharpe:.2f} "
                f"OOS_sharpe={f.oos_sharpe:.2f}{flag}"
            )
        n_flagged = sum(f.overfit_flagged for f in self.folds)
        lines.append(f"\n{n_flagged}/{len(self.folds)} folds flagged as likely overfit.")
        return "\n".join(lines)


class WalkForwardValidator:
    """
    Rolling, non-overlapping in-sample/out-of-sample walk-forward validation.

    strategy_factory(params: dict) -> StrategyFn
    param_grid: dict of {param_name: [values...]} — full grid search on IS,
                locked params applied unchanged to OOS.

    A fold is flagged overfit if OOS Sharpe < overfit_ratio * IS Sharpe
    (default: OOS must retain at least 50% of IS risk-adjusted performance).
    """

    def __init__(self, data: pd.DataFrame, is_days: int = 180, oos_days: int = 60,
                 step_days: Optional[int] = None, cost_model: Optional[CostModel] = None,
                 initial_capital: float = 100_000.0, overfit_ratio: float = 0.5):
        self.data = data
        self.is_days = is_days
        self.oos_days = oos_days
        self.step_days = step_days or oos_days
        self.cost_model = cost_model or CostModel()
        self.initial_capital = initial_capital
        self.overfit_ratio = overfit_ratio

    def run(self, strategy_factory: Callable[[dict], StrategyFn],
            param_grid: dict) -> WalkForwardResult:
        idx = self.data.index
        start = idx[0]
        end = idx[-1]
        folds: list[WalkForwardFold] = []

        is_delta = pd.Timedelta(days=self.is_days)
        oos_delta = pd.Timedelta(days=self.oos_days)
        step_delta = pd.Timedelta(days=self.step_days)

        cursor = start
        keys = list(param_grid.keys())
        combos = [dict(zip(keys, vals)) for vals in itertools.product(*param_grid.values())]

        while cursor + is_delta + oos_delta <= end:
            is_start, is_end = cursor, cursor + is_delta
            oos_start, oos_end = is_end, is_end + oos_delta

            is_slice = self.data.loc[is_start:is_end]
            oos_slice = self.data.loc[oos_start:oos_end]

            if len(is_slice) < 30 or len(oos_slice) < 10:
                cursor += step_delta
                continue

            best_params, best_sharpe = None, -np.inf
            for params in combos:
                bt = Backtester(is_slice, self.cost_model, self.initial_capital)
                result = bt.run(strategy_factory(params))
                s = result.metrics["sharpe"]
                if s > best_sharpe:
                    best_sharpe, best_params = s, params

            bt_oos = Backtester(oos_slice, self.cost_model, self.initial_capital)
            oos_result = bt_oos.run(strategy_factory(best_params))
            oos_sharpe = oos_result.metrics["sharpe"]

            overfit = oos_sharpe < self.overfit_ratio * best_sharpe if best_sharpe > 0 else True

            folds.append(WalkForwardFold(
                is_start=is_start, is_end=is_end,
                oos_start=oos_start, oos_end=oos_end,
                best_params=best_params,
                is_sharpe=best_sharpe, oos_sharpe=oos_sharpe,
                overfit_flagged=overfit,
            ))
            cursor += step_delta

        return WalkForwardResult(folds=folds)


# --------------------------------------------------------------------------- #
# Example strategy (for smoke-testing / docs — not investment advice)
# --------------------------------------------------------------------------- #

def sma_crossover_example(history: pd.DataFrame, fast: int = 10, slow: int = 30) -> float:
    """Reference strategy_fn. Only reads `history`, which the engine has
    already truncated to exclude the current bar — safe by construction."""
    if len(history) < slow:
        return 0.0
    fast_ma = history["close"].tail(fast).mean()
    slow_ma = history["close"].tail(slow).mean()
    return 1.0 if fast_ma > slow_ma else -1.0 if fast_ma < slow_ma else 0.0


def make_sma_crossover(params: dict) -> StrategyFn:
    """strategy_factory for use with WalkForwardValidator."""
    fast = params.get("fast", 10)
    slow = params.get("slow", 30)
    return lambda history: sma_crossover_example(history, fast=fast, slow=slow)


if __name__ == "__main__":
    # Synthetic random-walk demo so this file is runnable with zero external data.
    rng = np.random.default_rng(7)
    n = 800
    dates = pd.bdate_range("2023-01-01", periods=n)
    price = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n)))
    demo = pd.DataFrame({
        "open": price * (1 + rng.normal(0, 0.001, n)),
        "high": price * (1 + abs(rng.normal(0, 0.003, n))),
        "low": price * (1 - abs(rng.normal(0, 0.003, n))),
        "close": price,
    }, index=dates)

    print("=== Single backtest ===")
    bt = Backtester(demo, CostModel(asset_type="equity", slippage_bps=2.0))
    result = bt.run(sma_crossover_example)
    print(result.summary())

    print("\n=== Walk-forward validation ===")
    wfv = WalkForwardValidator(demo, is_days=180, oos_days=60,
                                cost_model=CostModel(asset_type="equity"))
    wf_result = wfv.run(make_sma_crossover, {"fast": [5, 10, 20], "slow": [30, 50]})
    print(wf_result.summary())
