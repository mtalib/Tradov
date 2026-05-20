#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS08_PivotMeanReversionSignal.py
Purpose: Pivot-point mean-reversion signal scorer for SPY. Combines four
         high-edge inputs into a single (direction, score, confidence)
         output that the strategy layer can consume without re-implementing
         confluence logic.

         Inputs (all injected — module is pure, no I/O):
           1. Daily pivot levels (P, R1..R3, S1..S3) — from F03
           2. Volatility regime label                — from F08
           3. ATR(14) + RSI(14)                      — from F01
           4. Net dealer GEX ($)                     — from N09 (optional)

         Output: PivotMRSignal dataclass with `direction`, `score` (0-100),
         `confidence`, and a verbose `reasons` breakdown for the audit log.

         The score is the additive composite designed in the v6 overview:
            +25  regime ∈ {LOW_VOL, RANGE}        (gate)
            +20  GEX > +$1B                       (single biggest SPY edge)
            +15  |price − level| / ATR ≥ 0.25     (trigger)
            +10  RSI ≥ 70 (fade R) or ≤ 30 (fade S)
            +10  VWAP slope flat / reverting      (optional)
            +10  max-pain pulls toward pivot      (optional)
            +10  breadth not extreme              (optional)
            -30  news window OR first/last 15 min (hard veto)
            -20  VIX > 22 OR backwardation        (near-veto)

         The MVP enables only the four core inputs (regime, ATR-distance,
         RSI, GEX). Optional fields are accepted but default to neutral so
         the module can be extended without breaking callers.

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-17 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Score weights (must sum to 100 for the four core inputs when all fire).
W_REGIME = 25
W_GEX = 20
W_ATR_DISTANCE = 15
W_RSI = 10
W_VWAP = 10
W_MAX_PAIN = 10
W_BREADTH = 10

# Vetos / penalties.
PEN_NEWS_OR_EDGE_OF_DAY = -30
PEN_HIGH_VIX = -20

# Trigger thresholds.
ATR_DISTANCE_TRIGGER = 0.25         # |price - level| / ATR
CENTER_PIVOT_PROXIMITY_ATR = 0.20   # |price - P| / ATR for center-bounce setup
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0
RSI_BULLISH_BIAS = 50.0
GEX_POSITIVE_THRESHOLD = 1_000_000_000.0  # $1B net dealer long-gamma
VIX_HIGH = 22.0

# Regimes considered safe for fading pivots. Match the F08 regime labels.
MEAN_REVERTING_REGIMES = frozenset({"LOW_VOL", "RANGE", "LOW", "NORMAL"})

# Composite score gate — strategies should only fire on score >= this.
MIN_FIRE_SCORE = 60

# Pivot levels we evaluate as fade targets.
RESISTANCE_KEYS = ("R1", "R2", "R3")
SUPPORT_KEYS = ("S1", "S2", "S3")
CENTER_KEY = "P"


# ==============================================================================
# TYPES
# ==============================================================================
class PivotDirection(StrEnum):
    """Direction of the proposed mean-reversion trade."""
    FADE_RESISTANCE = "fade_resistance"   # short bias / sell call spread
    FADE_SUPPORT = "fade_support"         # long bias / sell put spread
    NONE = "none"


CENTER_BOUNCE_LONG_TAG = "pivot_center_bounce_long"
CENTER_BOUNCE_SHORT_TAG = "pivot_center_bounce_short"


@dataclass
class PivotMRSignal:
    """Final composite output consumed by the strategy layer."""
    direction: PivotDirection
    score: int                                  # 0-100 composite
    confidence: float                           # 0.0-1.0 — score / 100, gated
    fired: bool                                 # score >= MIN_FIRE_SCORE
    nearest_level_name: str                     # e.g. "R1"
    nearest_level_price: float
    atr_distance: float                         # signed, in ATR units
    reasons: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)


@dataclass
class PivotMRInputs:
    """Container for all signal inputs. Optional fields default to neutral."""
    # --- Required ---------------------------------------------------------
    spot_price: float
    pivots: dict[str, float]                    # {"P","R1","R2","R3","S1","S2","S3"}
    atr: float                                  # ATR(14), absolute price units
    rsi: float                                  # RSI(14), 0-100

    # --- Tier 1 / Tier 3 core ---------------------------------------------
    regime_label: str = ""                      # e.g. "LOW_VOL", "TREND", ""
    net_gex: float | None = None             # dollars, None = unknown

    # --- Optional confluences (default neutral) ---------------------------
    vwap_slope: float | None = None          # bps/min; None = unknown
    max_pain_strike: float | None = None
    breadth_tick: float | None = None        # NYSE TICK reading
    vix: float | None = None
    vix_backwardation: bool = False
    is_news_window: bool = False
    is_edge_of_day: bool = False                # first/last 15 min


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class PivotMeanReversionSignal:
    """Stateless scorer.

    Holds no market state — inject `PivotMRInputs` per call. This makes the
    module trivially testable and safe to invoke from any thread.
    """

    def __init__(self) -> None:
        self.logger = SpyderLogger.get_logger(__name__)

    # ------------------------------------------------------------------ public
    def evaluate(self, inputs: PivotMRInputs) -> PivotMRSignal:
        """Score a single pivot mean-reversion opportunity.

        Returns the highest-scoring direction across all R/S levels, or
        `PivotDirection.NONE` if no level is in fade range.
        """
        if inputs.atr <= 0:
            return _empty_signal("ATR <= 0 — cannot normalise distance")
        if not inputs.pivots:
            return _empty_signal("No pivot levels supplied")

        # Find the nearest fadeable level on each side.
        best_resistance = self._closest_breached_level(
            inputs.spot_price, inputs.pivots, inputs.atr, RESISTANCE_KEYS, side="above"
        )
        best_support = self._closest_breached_level(
            inputs.spot_price, inputs.pivots, inputs.atr, SUPPORT_KEYS, side="below"
        )
        center_candidate = self._center_pivot_candidate(inputs)

        # Score each candidate, return the better one.
        cand_resistance = (
            self._score_candidate(inputs, *best_resistance, PivotDirection.FADE_RESISTANCE)
            if best_resistance else None
        )
        cand_support = (
            self._score_candidate(inputs, *best_support, PivotDirection.FADE_SUPPORT)
            if best_support else None
        )
        cand_center = (
            self._score_candidate(inputs, *center_candidate)
            if center_candidate else None
        )

        candidates = [c for c in (cand_resistance, cand_support, cand_center) if c is not None]
        if not candidates:
            return _empty_signal("Price within all pivot bands — no fade trigger")

        best = max(candidates, key=lambda s: s.score)
        return best

    # ---------------------------------------------------------------- internal
    @staticmethod
    def _closest_breached_level(
        spot: float,
        pivots: dict[str, float],
        atr: float,
        keys: tuple[str, ...],
        side: str,
    ) -> tuple[str, float, float] | None:
        """Return (name, price, signed_atr_distance) of the closest level
        that price has reached on the given side, else None.

        For resistance (side='above') we want price >= level.
        For support    (side='below') we want price <= level.
        """
        # v27 fix: pick the DEEPEST breach (largest signed ATR distance), not
        # the closest. When multiple R/S levels are breached, the deepest one
        # — i.e. the level farthest from the current price — represents the
        # strongest fade signal because price has travelled the furthest past
        # the original breakout. The previous `dist < best[2]` selected the
        # closest, contradicting the test contract in T131.
        best: tuple[str, float, float] | None = None
        for k in keys:
            lvl = pivots.get(k)
            if lvl is None:
                continue
            if side == "above" and spot >= lvl:
                dist = (spot - lvl) / atr
                if best is None or dist > best[2]:   # deepest breached level
                    best = (k, float(lvl), float(dist))
            elif side == "below" and spot <= lvl:
                dist = (lvl - spot) / atr   # positive when below support
                if best is None or dist > best[2]:   # deepest breached level
                    best = (k, float(lvl), float(dist))
        return best

    @staticmethod
    def _center_pivot_candidate(
        inp: PivotMRInputs,
    ) -> tuple[str, float, float, PivotDirection] | None:
        """Return a center-pivot candidate when price is rotating around P.

        Direction is inferred from local RSI bias so the signal can qualify
        neutral-bull and neutral-bear rotations without creating a new strategy
        type. Outside the proximity window we return no candidate.
        """
        p_level = inp.pivots.get(CENTER_KEY)
        if p_level is None or inp.atr <= 0:
            return None

        atr_distance = abs(inp.spot_price - float(p_level)) / inp.atr
        if atr_distance > CENTER_PIVOT_PROXIMITY_ATR:
            return None

        direction = (
            PivotDirection.FADE_SUPPORT
            if inp.rsi >= RSI_BULLISH_BIAS
            else PivotDirection.FADE_RESISTANCE
        )
        return (CENTER_KEY, float(p_level), float(atr_distance), direction)

    def _score_candidate(
        self,
        inp: PivotMRInputs,
        level_name: str,
        level_price: float,
        atr_distance: float,
        direction: PivotDirection,
    ) -> PivotMRSignal:
        """Apply the composite scoring rubric to a single candidate level."""
        score = 0
        reasons: list[str] = []
        penalties: list[str] = []

        # --- Tier 1: regime gate -----------------------------------------
        if inp.regime_label and inp.regime_label.upper() in MEAN_REVERTING_REGIMES:
            score += W_REGIME
            reasons.append(f"+{W_REGIME} regime={inp.regime_label}")
        elif inp.regime_label:
            penalties.append(f"regime={inp.regime_label} not mean-reverting")

        # --- Tier 1: ATR-normalised distance trigger ---------------------
        if level_name == CENTER_KEY and atr_distance <= CENTER_PIVOT_PROXIMITY_ATR:
            reasons.append(
                CENTER_BOUNCE_LONG_TAG
                if direction == PivotDirection.FADE_SUPPORT
                else CENTER_BOUNCE_SHORT_TAG
            )
            score += W_ATR_DISTANCE
            reasons.append(
                f"+{W_ATR_DISTANCE} center-pivot rotation dist={atr_distance:.2f} ATR "
                f"≤ {CENTER_PIVOT_PROXIMITY_ATR}"
            )
        elif atr_distance >= ATR_DISTANCE_TRIGGER:
            score += W_ATR_DISTANCE
            reasons.append(
                f"+{W_ATR_DISTANCE} dist={atr_distance:.2f} ATR ≥ {ATR_DISTANCE_TRIGGER}"
            )
        else:
            penalties.append(
                f"dist={atr_distance:.2f} ATR < {ATR_DISTANCE_TRIGGER} (weak trigger)"
            )

        # --- Tier 2: RSI confirmation ------------------------------------
        if direction == PivotDirection.FADE_RESISTANCE and inp.rsi >= RSI_OVERBOUGHT:
            score += W_RSI
            reasons.append(f"+{W_RSI} RSI={inp.rsi:.1f} ≥ {RSI_OVERBOUGHT}")
        elif direction == PivotDirection.FADE_SUPPORT and inp.rsi <= RSI_OVERSOLD:
            score += W_RSI
            reasons.append(f"+{W_RSI} RSI={inp.rsi:.1f} ≤ {RSI_OVERSOLD}")

        # --- Tier 3: GEX (biggest SPY-specific edge) ---------------------
        if inp.net_gex is not None and inp.net_gex >= GEX_POSITIVE_THRESHOLD:
            score += W_GEX
            reasons.append(f"+{W_GEX} GEX={inp.net_gex / 1e9:.2f}B (long-gamma pinning)")
        elif inp.net_gex is not None and inp.net_gex < 0:
            penalties.append(f"GEX={inp.net_gex / 1e9:.2f}B (short-gamma — pivots break)")

        # --- Tier 2 optional: VWAP slope ---------------------------------
        if inp.vwap_slope is not None and abs(inp.vwap_slope) < 1.0:
            score += W_VWAP
            reasons.append(f"+{W_VWAP} VWAP slope flat ({inp.vwap_slope:+.2f} bps/min)")

        # --- Tier 3 optional: max pain pulls toward pivot ----------------
        if inp.max_pain_strike is not None:
            mp = inp.max_pain_strike
            if direction == PivotDirection.FADE_RESISTANCE and mp <= level_price:
                score += W_MAX_PAIN
                reasons.append(f"+{W_MAX_PAIN} max-pain {mp:.2f} ≤ R level (pulls down)")
            elif direction == PivotDirection.FADE_SUPPORT and mp >= level_price:
                score += W_MAX_PAIN
                reasons.append(f"+{W_MAX_PAIN} max-pain {mp:.2f} ≥ S level (pulls up)")

        # --- Tier 2 optional: breadth not extreme ------------------------
        if inp.breadth_tick is not None and abs(inp.breadth_tick) < 800:
            score += W_BREADTH
            reasons.append(f"+{W_BREADTH} TICK={inp.breadth_tick:+.0f} (not extreme)")
        elif inp.breadth_tick is not None:
            penalties.append(f"TICK={inp.breadth_tick:+.0f} extreme — trend-day risk")

        # --- Vetos -------------------------------------------------------
        if inp.is_news_window or inp.is_edge_of_day:
            score += PEN_NEWS_OR_EDGE_OF_DAY
            penalties.append(
                f"{PEN_NEWS_OR_EDGE_OF_DAY} news/edge-of-day window — hard veto"
            )
        if (inp.vix is not None and inp.vix > VIX_HIGH) or inp.vix_backwardation:
            score += PEN_HIGH_VIX
            penalties.append(
                f"{PEN_HIGH_VIX} VIX={inp.vix} backwardation={inp.vix_backwardation}"
            )

        score = max(0, min(100, score))
        confidence = score / 100.0
        fired = score >= MIN_FIRE_SCORE

        return PivotMRSignal(
            direction=direction,
            score=score,
            confidence=confidence,
            fired=fired,
            nearest_level_name=level_name,
            nearest_level_price=level_price,
            atr_distance=atr_distance,
            reasons=reasons,
            penalties=penalties,
        )


# ==============================================================================
# HELPERS
# ==============================================================================
def _empty_signal(reason: str) -> PivotMRSignal:
    """Build a no-op signal with an explanatory reason."""
    return PivotMRSignal(
        direction=PivotDirection.NONE,
        score=0,
        confidence=0.0,
        fired=False,
        nearest_level_name="",
        nearest_level_price=0.0,
        atr_distance=0.0,
        reasons=[],
        penalties=[reason],
    )
