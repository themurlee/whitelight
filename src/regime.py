# """Regime scoring module for macro regime assessment.
# This file is a copy of the original `regime.py` implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import math

import numpy as np
import pandas as pd

BASE_WEIGHTS = {
    "concentration": ("RSP/SPY", 0.25),
    "yield_curve":   ("10Y-2Y",  0.20),
    "credit":        ("HYG/LQD", 0.15),
    "size":          ("IWM/SPY", 0.15),
    "equity_bond":   ("SPY/TLT", 0.15),
    "sector":        ("XLY/XLP", 0.10),
}

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def _trend_signal(ratio: pd.Series, slow: int = 200, slope_win: int = 20) -> tuple[Optional[float], str]:
    """
    -1/0/+1-ish signal: 0.5 * (above/below slow SMA) + 0.5 * (SMA rising/falling).
    Returns (None, "insufficient data") if there isn't enough history.
    """
    if len(ratio) < slow + slope_win:
        return None, "insufficient data"
    sma_now = ratio.tail(slow).mean()
    sma_then = ratio.iloc[-(slow + slope_win):-slope_win].tail(slow).mean()
    base = 1.0 if ratio.iloc[-1] > sma_now else -1.0
    trend = 1.0 if sma_now > sma_then else -1.0
    sig = 0.5 * base + 0.5 * trend
    detail = f"{'above' if base > 0 else 'below'} SMA{slow}, SMA{slow} {'rising' if trend > 0 else 'falling'}"
    return sig, detail


@dataclass
class RegimeComponent:
    name: str
    weight: float
    signal: Optional[float] = None
    detail: str = ""
    available: bool = True

@dataclass
class RegimeResult:
    composite: float                # -1..+1
    pillar_score: int               # -2..+2, same scale as a trend/momentum score
    pillar_label: str
    regime: str                     # Broadening | Concentration | Contraction | Inflationary | Transitional
    inflationary_flag: bool
    spy_tlt_corr: Optional[float]
    components: list[RegimeComponent] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

def score_regime(
    prices: dict[str, pd.Series],
    yield_spread_bps: Optional[float] = None,
    yield_spread_history: Optional[pd.Series] = None,
    slow: int = 200,
    slope_win: int = 20,
    corr_win: int = 40,
) -> RegimeResult:
    """
    prices: dict of {"SPY": close_series, "RSP": ..., "IWM": ..., "HYG": ..., "LQD": ..., "TLT": ..., "XLY": ..., "XLP": ...}
            Missing symbols are fine — that component's weight is
            redistributed across the rest.
    yield_spread_bps: current 10Y-2Y spread, in bps, e.g. -30.0. Optional.
    yield_spread_history: optional Series of the spread for slope calc; if
            omitted, only a level signal is used (weaker, no slope).
    """
    notes: list[str] = []
    comps: dict[str, RegimeComponent] = {}

    def ratio(a: str, b: str) -> Optional[pd.Series]:
        if a in prices and b in prices:
            aligned = pd.concat([prices[a], prices[b]], axis=1, join="inner").dropna()
            if aligned.empty:
                return None
            return aligned.iloc[:, 0] / aligned.iloc[:, 1]
        return None

    # 1. Concentration: RSP/SPY
    c = RegimeComponent("Concentration (RSP/SPY)", BASE_WEIGHTS["concentration"][1])
    r = ratio("RSP", "SPY")
    if r is not None:
        c.signal, c.detail = _trend_signal(r, slow, slope_win)
        c.available = c.signal is not None
    else:
        c.available = False
    comps["concentration"] = c

    # 2. Yield curve (injected, not proxied by treasury ETFs — proxies are fragile)
    c = RegimeComponent("Yield Curve (10Y-2Y)", BASE_WEIGHTS["yield_curve"][1])
    if yield_spread_history is not None and len(yield_spread_history) >= slope_win + 1:
        now = yield_spread_history.iloc[-1]
        then = yield_spread_history.iloc[-1 - slope_win]
        base = 1.0 if now > 0 else -1.0
        trend = 1.0 if now > then else -1.0
        c.signal = 0.5 * base + 0.5 * trend
        c.detail = f"spread {now:+.0f}bps, {'steepening' if trend > 0 else 'flattening'}"
    elif yield_spread_bps is not None:
        c.signal = 0.5 if yield_spread_bps > 0 else -0.5
        c.detail = f"spread {yield_spread_bps:+.0f}bps (level only, no slope)"
        notes.append("yield spread: level only, no history for slope -> weaker signal (±0.5).")
    else:
        c.available = False
        notes.append("No yield spread provided: redistributing its 20% weight across other components.")
    comps["yield_curve"] = c

    # 3. Credit: HYG/LQD
    c = RegimeComponent("Credit (HYG/LQD)", BASE_WEIGHTS["credit"][1])
    r = ratio("HYG", "LQD")
    if r is not None:
        c.signal, c.detail = _trend_signal(r, slow, slope_win)
        c.available = c.signal is not None
    else:
        c.available = False
    comps["credit"] = c

    # 4. Size: IWM/SPY
    c = RegimeComponent("Size (IWM/SPY)", BASE_WEIGHTS["size"][1])
    r = ratio("IWM", "SPY")
    if r is not None:
        c.signal, c.detail = _trend_signal(r, slow, slope_win)
        c.available = c.signal is not None
    else:
        c.available = False
    comps["size"] = c

    # 5. Equity vs Bond: SPY/TLT
    c = RegimeComponent("Equity vs Bond (SPY/TLT)", BASE_WEIGHTS["equity_bond"][1])
    r = ratio("SPY", "TLT")
    if r is not None:
        c.signal, c.detail = _trend_signal(r, slow, slope_win)
        c.available = c.signal is not None
    else:
        c.available = False
    comps["equity_bond"] = c

    # 6. Sector rotation: XLY/XLP
    c = RegimeComponent("Sector (XLY/XLP)", BASE_WEIGHTS["sector"][1])
    r = ratio("XLY", "XLP")
    if r is not None:
        c.signal, c.detail = _trend_signal(r, slow, slope_win)
        c.available = c.signal is not None
    else:
        c.available = False
    comps["sector"] = c

    # SPY-TLT correlation (inflationary regime flag)
    spy_tlt_corr = None
    if "SPY" in prices and "TLT" in prices:
        aligned = pd.concat([prices["SPY"], prices["TLT"]], axis=1, join="inner").dropna().tail(corr_win + 1)
        if len(aligned) >= 5:
            rs = aligned.iloc[:, 0].pct_change().dropna()
            rt = aligned.iloc[:, 1].pct_change().dropna()
            if rs.std() > 0 and rt.std() > 0:
                spy_tlt_corr = float(rs.corr(rt))

    avail = [c for c in comps.values() if c.available and c.signal is not None]
    if not avail:
        raise ValueError("regime.score_regime: no components had sufficient data")

    wsum = sum(c.weight for c in avail)
    composite = sum(c.signal * c.weight for c in avail) / wsum
    composite = _clamp(composite, -1.0, 1.0)

    eb = comps["equity_bond"]
    inflationary = bool(
        spy_tlt_corr is not None and spy_tlt_corr > 0.25
        and eb.available and eb.signal is not None and eb.signal <= 0
    )

    conc_sig = comps["concentration"].signal or 0
    size_sig = comps["size"].signal or 0
    credit_sig = comps["credit"].signal or 0

    if inflationary:
        regime = "Inflationary"
    elif composite <= -0.5 and credit_sig < 0:
        regime = "Contraction"
    elif composite >= 0.4 and size_sig > 0:
        regime = "Broadening"
    elif conc_sig < 0 and size_sig < 0 and composite > -0.5:
        regime = "Concentration"
    else:
        regime = "Transitional"

    if composite >= 0.5:
        pillar, plabel = 2, "Strongly favorable macro"
    elif composite >= 0.2:
        pillar, plabel = 1, "Favorable macro"
    elif composite > -0.2:
        pillar, plabel = 0, "Neutral macro"
    elif composite > -0.5:
        pillar, plabel = -1, "Adverse macro"
    else:
        pillar, plabel = -2, "Strongly adverse macro"

    if regime in ("Contraction", "Inflationary") and pillar > -1:
        pillar, plabel = -1, f"Adverse macro (capped: {regime} regime)"
        notes.append(f"Pillar capped at -1 due to {regime} regime.")

    return RegimeResult(
        composite=round(composite, 3),
        pillar_score=pillar,
        pillar_label=plabel,
        regime=regime,
        inflationary_flag=inflationary,
        spy_tlt_corr=round(spy_tlt_corr, 3) if spy_tlt_corr is not None else None,
        components=list(comps.values()),
        notes=notes,
    )
