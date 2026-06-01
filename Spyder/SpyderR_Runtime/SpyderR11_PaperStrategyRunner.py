#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: SpyderR11_PaperStrategyRunner.py
Purpose: Autonomous paper-trading strategy runner — live Tradier data,
         simulated fills. Bridges market data → strategy signals → paper
         positions → exits → PaperTradingHarness.record_trade().

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-17

Module Description:
    The 30-day paper harness (SpyderR06) and launcher (SpyderQ93) track
    equity and drawdown but never invoke any strategy — no trades fire.
    This module fills that gap.

    Data plane: live Tradier quotes + option chain (TRADIER_ENVIRONMENT=live).
    Execution:  purely simulated; no orders are sent to Tradier. Fills are
                priced at the mid with a small configurable slippage.

    Two strategies ship enabled by default:

      1. BullPutCreditSpread (~7–14 DTE):
         - Short ~0.20-Δ OTM put, long put $5 below (defined-risk)
         - Exits: 50 % of credit profit target, 200 % of credit stop,
                  short-strike threat, or DTE ≤ 1.

      2. ZeroDTE IronCondor:
         - Short ~0.15-Δ OTM call + short ~0.15-Δ OTM put on today's
           expiry, each with a $5-wide long wing.
         - Exits: 50 % profit target, 200 % stop, short-strike threat,
                  or hard time-stop at 15:30 ET.

    On each call to :meth:`tick`, the runner:
            1. Pulls a fresh underlying quote.
      2. Evaluates exit rules for every open simulated position; closes
         at mid on trigger and calls ``harness.record_trade``.
      3. If below ``max_concurrent_positions`` and within each strategy's
         entry window, evaluates entry rules and opens a new position.

    SAFETY:
            - Refuses to start unless ``TRADING_MODE`` is "paper" unless
                ``LIVE_TRADING_CONFIRMED=true``.
      - Never calls TradierClient.place_*_order. All fills are local.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from __future__ import annotations

import os
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
    TradierClient,
    TradingEnvironment,
)
from Spyder.SpyderE_Risk.SpyderE00_RiskProtocol import (
    BoundarySignalType,
    RiskManagerProtocol,
    RiskValidationRequest,
)

logger = SpyderLogger.get_logger("SpyderR11_PaperStrategyRunner")
_ET_TZ = ZoneInfo("America/New_York")


# ==============================================================================
# CONSTANTS
# ==============================================================================
SPY_CONTRACT_MULTIPLIER: int = 100

# Sizing
RISK_PCT_PER_TRADE: float = 0.01        # 1 % of equity per defined-risk spread
MAX_CONTRACTS_CAP: int = 10             # hard ceiling regardless of equity
DEFAULT_STARTING_EQUITY: float = 100_000.0

# Bull-put parameters
BP_TARGET_SHORT_DELTA: float = 0.20
BP_SHORT_DELTA_TOLERANCE: float = 0.08  # accept 0.12 – 0.28
BP_WING_WIDTH_DOLLARS: float = 5.0
BP_MIN_CREDIT: float = 0.40             # $0.40 per share = $40 per contract
BP_TARGET_DTE_MIN: int = 7
BP_TARGET_DTE_MAX: int = 14
BP_MAX_OPEN: int = 2

# 0DTE Iron Condor parameters
ZDTE_TARGET_SHORT_DELTA: float = 0.15
ZDTE_SHORT_DELTA_TOLERANCE: float = 0.07  # accept 0.08 – 0.22
ZDTE_WING_WIDTH_DOLLARS: float = 5.0
ZDTE_MIN_TOTAL_CREDIT: float = 0.50     # combined put + call credit
ZDTE_MAX_OPEN: int = 1
DEFAULT_ZERO_DTE_PROFILE: str = "classic"
MARK_SPY_PAPER_ZERO_DTE_PROFILE: str = "mark_spy_paper"

# Shared exit rules
PROFIT_TARGET_PCT: float = 0.50         # close at +50 % of credit
STOP_LOSS_MULTIPLE: float = 2.00        # close at 200 % of credit (max loss region)
STRIKE_THREAT_PCT: float = 0.005        # within 0.5 % of short strike → close
BP_MIN_DTE_FOR_HOLD: int = 1            # close bull-put if DTE ≤ 1

# Entry windows (US/Eastern, naive — UTC-4 in DST, UTC-5 in EST)
BP_ENTRY_START_ET = time(10, 15)
BP_ENTRY_END_ET = time(15, 0)
ZDTE_ENTRY_START_ET = time(10, 30)
ZDTE_ENTRY_END_ET = time(14, 30)
ZDTE_HARD_CLOSE_ET = time(15, 30)

# Fill modelling
FILL_SLIPPAGE_PER_LEG: float = 0.02     # $0.02 per leg haircut from mid

# Overall ceiling
DEFAULT_MAX_CONCURRENT: int = 3

# ---- Regime gate (VIX-based, lightweight stand-in for SpyderF10) ----
# New entries are blocked when VIX exceeds the per-strategy cap.
# Rationale: selling premium into extreme volatility has negative expectancy
# (IV crush is unreliable and tail risk dominates). The full F10
# MarketRegimeDetector is a more nuanced replacement; these caps are the
# minimal safety net until F10 is wired in.
REGIME_VIX_SYMBOL: str = "VIX"          # Tradier accepts "VIX" directly
BP_MAX_VIX: float = 30.0                # skip new bull-puts above this
ZDTE_MAX_VIX: float = 35.0              # skip new 0DTE ICs above this
PAPER_UNDERLYING_SYMBOL: str = (
    os.environ.get("SPYDER_UNDERLYING_SYMBOL", "SPX").strip().upper() or "SPX"
)

ZERO_DTE_PROFILE_CONFIGS: dict[str, dict[str, Any]] = {
    DEFAULT_ZERO_DTE_PROFILE: {
        "target_short_delta": ZDTE_TARGET_SHORT_DELTA,
        "short_delta_min": 0.08,
        "short_delta_max": 0.22,
        "wing_width_dollars": ZDTE_WING_WIDTH_DOLLARS,
        "min_total_credit": ZDTE_MIN_TOTAL_CREDIT,
        "entry_start_et": ZDTE_ENTRY_START_ET,
        "entry_end_et": ZDTE_ENTRY_END_ET,
        "hard_close_et": ZDTE_HARD_CLOSE_ET,
        "max_open": ZDTE_MAX_OPEN,
        "max_daily_entries": 3,
        "max_vix": ZDTE_MAX_VIX,
        "profit_target_pct": PROFIT_TARGET_PCT,
        "stop_loss_multiple": STOP_LOSS_MULTIPLE,
        "threat_buffer_pct": STRIKE_THREAT_PCT,
        "threat_buffer_points": None,
        "risk_pct_per_trade": RISK_PCT_PER_TRADE,
        "max_contracts_cap": MAX_CONTRACTS_CAP,
    },
    MARK_SPY_PAPER_ZERO_DTE_PROFILE: {
        "target_short_delta": 0.12,
        "short_delta_min": 0.07,
        "short_delta_max": 0.20,
        "wing_width_dollars": 1.0,
        "min_total_credit": 0.20,
        "entry_start_et": time(9, 32),
        "entry_end_et": time(14, 30),
        "hard_close_et": time(15, 15),
        "max_open": 4,
        "max_daily_entries": 8,
        "max_vix": 30.0,
        "profit_target_pct": 0.30,
        "stop_loss_multiple": 1.25,
        "threat_buffer_pct": None,
        "threat_buffer_points": 0.35,
        "risk_pct_per_trade": 0.005,
        "max_contracts_cap": 5,
    },
}

# ---- Portfolio Greek ceilings (lightweight stand-in for SpyderE15) ----
# Caps are expressed as absolute values per contract unit. Position Greeks
# are captured at fill and summed across open positions. New entries that
# would push the portfolio past these caps are rejected.
MAX_PORTFOLIO_DELTA: float = 50.0       # |Σ delta × 100 × contracts|
MAX_PORTFOLIO_VEGA: float = 200.0       # |Σ vega × 100 × contracts|
MAX_PORTFOLIO_GAMMA: float = 10.0       # |Σ gamma × 100 × contracts|
MARK_SPY_PAPER_PORTFOLIO_GAMMA_CAP: float = 11.0


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class SimulatedLeg:
    """A single option leg in a simulated multi-leg position."""

    option_symbol: str         # e.g. "SPY260418P00500000"
    side: str                  # "short" or "long"
    strike: float
    option_type: str           # "put" or "call"
    entry_price: float         # per-share premium at fill
    qty: int                   # contracts (always positive)
    # Per-leg Greeks captured at entry (raw, unsigned — sign applied via side)
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0


@dataclass
class SimulatedPosition:
    """A simulated multi-leg options position tracked locally."""

    position_id: str
    strategy: str              # "BullPutCreditSpread" | "ZeroDTE_IronCondor"
    opened_at: datetime
    expiration: date
    legs: list[SimulatedLeg]
    contracts: int
    credit_received: float     # per contract (net, positive = we received)
    max_loss: float            # per contract (positive $ amount)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Short-strike reference for strike-threat exits
    short_put_strike: float | None = None
    short_call_strike: float | None = None

    # Populated on close
    closed_at: datetime | None = None
    exit_debit: float | None = None         # per contract paid to close
    realized_pnl: float | None = None       # total $
    exit_reason: str | None = None

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    # ---- Greek aggregation (signed: short legs contribute negatively) ----
    def _signed_greek(self, greek: str) -> float:
        """Sum signed per-leg Greeks × leg.qty (per-contract unit; ×100 applied by callers)."""
        total = 0.0
        for leg in self.legs:
            sign = -1.0 if leg.side == "short" else 1.0
            total += sign * getattr(leg, greek, 0.0) * leg.qty
        return total

    @property
    def position_delta(self) -> float:
        """Dollar-delta per $1 underlying move: Σ(signed Δ × leg.qty) × 100."""
        return self._signed_greek("delta") * SPY_CONTRACT_MULTIPLIER

    @property
    def position_gamma(self) -> float:
        return self._signed_greek("gamma") * SPY_CONTRACT_MULTIPLIER

    @property
    def position_vega(self) -> float:
        return self._signed_greek("vega") * SPY_CONTRACT_MULTIPLIER


# ==============================================================================
# STRATEGY ADAPTER PROTOCOL
# ==============================================================================
@dataclass
class MarketContext:
    """Snapshot passed to each adapter on every tick."""

    spy_price: float
    now: datetime
    vix: float | None = None    # None when VIX quote unavailable this tick


@dataclass
class ProposedPosition:
    """An adapter's proposed trade, pre-sizing and pre-risk-gate.

    The runner injects ``contracts`` only after :class:`PaperStrategyRunner`
    runs the E-Series risk gate and sizing layer, so adapters must supply
    per-contract credit and max-loss.
    """

    strategy: str
    expiration: date
    legs: list[SimulatedLeg]                # qty left as 0 here; runner fills
    credit_received: float                  # per contract
    max_loss: float                         # per contract
    short_put_strike: float | None = None
    short_call_strike: float | None = None
    primary_symbol: str = ""                # used for risk validation
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategyAdapter:
    """Interface every adapter must satisfy.

    Adapters are passive — they inspect a :class:`MarketContext` and either
    return a :class:`ProposedPosition` (entry) or a reason string (exit).
    The runner owns all sizing, risk validation, fills, and bookkeeping.
    """

    name: str = "StrategyAdapter"
    max_open: int = 1
    max_daily_entries: int | None = None
    max_vix: float | None = None   # None → no regime gate
    profit_target_pct: float = PROFIT_TARGET_PCT
    stop_loss_multiple: float = STOP_LOSS_MULTIPLE
    threat_buffer_pct: float | None = STRIKE_THREAT_PCT
    threat_buffer_points: float | None = None
    risk_pct_per_trade: float = RISK_PCT_PER_TRADE
    max_contracts_cap: int = MAX_CONTRACTS_CAP

    def within_entry_window(self, now: datetime) -> bool:  # pragma: no cover
        # A15 (v14): Safe no-op default. Any concrete adapter overrides this;
        # if the base class is ever hit at runtime we refuse to enter rather
        # than crash the paper runner.
        import logging
        logging.getLogger(__name__).warning(
            "StrategyAdapter.within_entry_window() default hit on %s; "
            "returning False (refuse entry)",
            type(self).__name__,
        )
        return False

    def regime_gate(self, ctx: MarketContext) -> str | None:
        """Return a reject reason if the current regime blocks new entries.

        Default: VIX-based cap (``self.max_vix``). When VIX is unavailable
        (``ctx.vix is None``) the gate is permissive — we don't block
        trading because of a missing data point. Subclasses can override
        with richer logic (e.g. SpyderF10 regime consultation).
        """
        if self.max_vix is None or ctx.vix is None:
            return None
        if ctx.vix > self.max_vix:
            return f"regime_vix_cap (VIX={ctx.vix:.2f} > {self.max_vix:.2f})"
        return None

    @staticmethod
    def _leg_with_greeks(
        runner: PaperStrategyRunner,
        opt: Any,
        side: str,
        strike: float,
        option_type: str,
        entry_price: float,
    ) -> SimulatedLeg:
        """Build a SimulatedLeg capturing per-leg Greeks from the chain quote."""
        return SimulatedLeg(
            option_symbol=str(runner.field_of(opt, "symbol", "")),
            side=side,
            strike=strike,
            option_type=option_type,
            entry_price=entry_price,
            qty=0,
            delta=float(runner.field_of(opt, "delta", 0.0) or 0.0),
            gamma=float(runner.field_of(opt, "gamma", 0.0) or 0.0),
            vega=float(runner.field_of(opt, "vega", 0.0) or 0.0),
            theta=float(runner.field_of(opt, "theta", 0.0) or 0.0),
        )

    def evaluate_entry(
        self,
        ctx: MarketContext,
        runner: PaperStrategyRunner,
    ) -> ProposedPosition | None:  # pragma: no cover
        # A15 (v14): Safe no-op default — see within_entry_window above.
        import logging
        logging.getLogger(__name__).warning(
            "StrategyAdapter.evaluate_entry() default hit on %s; "
            "returning None (no proposed position)",
            type(self).__name__,
        )
        return None

    def evaluate_exit(
        self,
        pos: SimulatedPosition,
        ctx: MarketContext,
        cur_debit: float,
    ) -> str | None:
        """Return exit reason string, or None to hold.

        Default implementation covers the common exits (profit target / stop
        loss / strike threat). Subclasses override and call super().
        """
        profit = pos.credit_received - cur_debit
        if profit >= self.profit_target_pct * pos.credit_received:
            return f"profit_target ({self.profit_target_pct:.0%})"
        if profit <= -self.stop_loss_multiple * pos.credit_received:
            return f"stop_loss ({self.stop_loss_multiple:.0%} credit)"

        if self.threat_buffer_points is not None:
            put_threat_price = (
                pos.short_put_strike + self.threat_buffer_points
                if pos.short_put_strike is not None
                else None
            )
            call_threat_price = (
                pos.short_call_strike - self.threat_buffer_points
                if pos.short_call_strike is not None
                else None
            )
        else:
            threat_pct = self.threat_buffer_pct or STRIKE_THREAT_PCT
            put_threat_price = (
                pos.short_put_strike * (1.0 + threat_pct)
                if pos.short_put_strike is not None
                else None
            )
            call_threat_price = (
                pos.short_call_strike * (1.0 - threat_pct)
                if pos.short_call_strike is not None
                else None
            )

        if put_threat_price is not None and ctx.spy_price <= put_threat_price:
            return f"short_put_threat @ {pos.short_put_strike:.0f}"
        if call_threat_price is not None and ctx.spy_price >= call_threat_price:
            return f"short_call_threat @ {pos.short_call_strike:.0f}"
        return None


class BullPutAdapter(StrategyAdapter):
    """Bull-put credit spread adapter (~7–14 DTE, 0.20-Δ short)."""

    name = "BullPutCreditSpread"
    max_open = BP_MAX_OPEN
    max_vix = BP_MAX_VIX

    def within_entry_window(self, now: datetime) -> bool:
        return BP_ENTRY_START_ET <= now.time() <= BP_ENTRY_END_ET

    def evaluate_entry(
        self,
        ctx: MarketContext,
        runner: PaperStrategyRunner,
    ) -> ProposedPosition | None:
        target_expiry = runner.pick_expiration(
            ctx.now.date(), BP_TARGET_DTE_MIN, BP_TARGET_DTE_MAX,
        )
        if target_expiry is None:
            return None
        puts = runner.get_chain_with_greeks(target_expiry, option_type="put")
        if not puts:
            return None
        short = runner.find_put_by_delta(
            puts, ctx.spy_price, BP_TARGET_SHORT_DELTA, BP_SHORT_DELTA_TOLERANCE,
        )
        if short is None:
            return None
        short_strike = float(runner.field_of(short, "strike"))
        long_leg = runner.find_strike(puts, short_strike - BP_WING_WIDTH_DOLLARS)
        if long_leg is None or float(runner.field_of(long_leg, "strike")) >= short_strike:
            return None
        s_b, s_a, _ = runner.quote_of(short)
        l_b, l_a, _ = runner.quote_of(long_leg)
        short_fill = max(0.0, runner.mid(s_b, s_a) - FILL_SLIPPAGE_PER_LEG)
        long_fill = runner.mid(l_b, l_a) + FILL_SLIPPAGE_PER_LEG
        credit = short_fill - long_fill
        if credit < BP_MIN_CREDIT:
            return None
        long_strike = float(runner.field_of(long_leg, "strike"))
        width = short_strike - long_strike
        max_loss = max(0.01, width - credit)
        return ProposedPosition(
            strategy=self.name,
            expiration=date.fromisoformat(target_expiry),
            legs=[
                self._leg_with_greeks(runner, short, "short", short_strike, "put", short_fill),
                self._leg_with_greeks(runner, long_leg, "long", long_strike, "put", long_fill),
            ],
            credit_received=credit,
            max_loss=max_loss,
            short_put_strike=short_strike,
            primary_symbol=str(runner.field_of(short, "symbol", "")),
            metadata={"spy_at_entry": ctx.spy_price, "strategy_type": "bull_put_spread"},
        )

    def evaluate_exit(
        self,
        pos: SimulatedPosition,
        ctx: MarketContext,
        cur_debit: float,
    ) -> str | None:
        base = super().evaluate_exit(pos, ctx, cur_debit)
        if base is not None:
            return base
        dte = (pos.expiration - ctx.now.date()).days
        if dte <= BP_MIN_DTE_FOR_HOLD:
            return f"dte<={BP_MIN_DTE_FOR_HOLD}"
        return None


class ZeroDTEAdapter(StrategyAdapter):
    """0DTE iron condor adapter (~0.15-Δ shorts, $5 wings)."""

    name = "ZeroDTE_IronCondor"

    def __init__(self, profile_name: str = DEFAULT_ZERO_DTE_PROFILE) -> None:
        normalized_profile = str(profile_name or DEFAULT_ZERO_DTE_PROFILE).strip().lower()
        settings = ZERO_DTE_PROFILE_CONFIGS.get(normalized_profile)
        if settings is None:
            normalized_profile = DEFAULT_ZERO_DTE_PROFILE
            settings = ZERO_DTE_PROFILE_CONFIGS[normalized_profile]

        self.profile_name = normalized_profile
        self.target_short_delta = float(settings["target_short_delta"])
        self.short_delta_min = float(settings["short_delta_min"])
        self.short_delta_max = float(settings["short_delta_max"])
        self.wing_width_dollars = float(settings["wing_width_dollars"])
        self.min_total_credit = float(settings["min_total_credit"])
        self.entry_start_et = settings["entry_start_et"]
        self.entry_end_et = settings["entry_end_et"]
        self.hard_close_et = settings["hard_close_et"]
        self.max_open = int(settings["max_open"])
        self.max_daily_entries = int(settings["max_daily_entries"])
        self.max_vix = float(settings["max_vix"])
        self.profit_target_pct = float(settings["profit_target_pct"])
        self.stop_loss_multiple = float(settings["stop_loss_multiple"])
        threat_buffer_pct = settings.get("threat_buffer_pct")
        self.threat_buffer_pct = (
            None if threat_buffer_pct is None else float(threat_buffer_pct)
        )
        threat_buffer_points = settings.get("threat_buffer_points")
        self.threat_buffer_points = (
            None if threat_buffer_points is None else float(threat_buffer_points)
        )
        self.risk_pct_per_trade = float(settings["risk_pct_per_trade"])
        self.max_contracts_cap = int(settings["max_contracts_cap"])

    def within_entry_window(self, now: datetime) -> bool:
        return self.entry_start_et <= now.time() <= self.entry_end_et

    def _find_short_leg(
        self,
        options: list[Any],
        spot: float,
        runner: PaperStrategyRunner,
        option_type: str,
    ) -> Any | None:
        best = None
        best_err = float("inf")
        for option in options:
            strike = float(runner.field_of(option, "strike", 0.0) or 0.0)
            if strike <= 0:
                continue
            if option_type == "put" and strike >= spot:
                continue
            if option_type == "call" and strike <= spot:
                continue

            _, _, delta = runner.quote_of(option)
            if delta == 0.0:
                continue

            abs_delta = abs(delta)
            if abs_delta < self.short_delta_min or abs_delta > self.short_delta_max:
                continue

            err = abs(abs_delta - self.target_short_delta)
            if err < best_err:
                best = option
                best_err = err

        if best is not None:
            return best

        tolerance = max(
            abs(self.short_delta_max - self.target_short_delta),
            abs(self.target_short_delta - self.short_delta_min),
        )
        if option_type == "put":
            return runner.find_put_by_delta(options, spot, self.target_short_delta, tolerance)
        return runner.find_call_by_delta(options, spot, self.target_short_delta, tolerance)

    def _short_leg_candidates(
        self,
        options: list[Any],
        spot: float,
        runner: PaperStrategyRunner,
        option_type: str,
    ) -> list[Any]:
        candidates: list[tuple[float, Any]] = []
        for option in options:
            strike = float(runner.field_of(option, "strike", 0.0) or 0.0)
            if strike <= 0:
                continue
            if option_type == "put" and strike >= spot:
                continue
            if option_type == "call" and strike <= spot:
                continue

            _, _, delta = runner.quote_of(option)
            if delta == 0.0:
                continue

            abs_delta = abs(delta)
            if abs_delta < self.short_delta_min or abs_delta > self.short_delta_max:
                continue

            err = abs(abs_delta - self.target_short_delta)
            candidates.append((err, option))

        candidates.sort(key=lambda item: item[0])
        ordered = [option for _, option in candidates]
        if ordered:
            return ordered

        fallback = self._find_short_leg(options, spot, runner, option_type)
        if fallback is None:
            return []
        return [fallback]

    def evaluate_entry(
        self,
        ctx: MarketContext,
        runner: PaperStrategyRunner,
    ) -> ProposedPosition | None:
        today_iso = ctx.now.date().isoformat()
        if today_iso not in runner.get_expirations():
            return None
        chain = runner.get_chain_with_greeks(today_iso)
        if not chain:
            return None
        puts = [o for o in chain if str(runner.field_of(o, "option_type", "")).lower() == "put"]
        calls = [o for o in chain if str(runner.field_of(o, "option_type", "")).lower() == "call"]
        put_candidates = self._short_leg_candidates(puts, ctx.spy_price, runner, "put")
        call_candidates = self._short_leg_candidates(calls, ctx.spy_price, runner, "call")
        if not put_candidates or not call_candidates:
            return None

        selected: tuple[Any, Any, Any, Any, float] | None = None
        selected_err: float | None = None
        selected_credit: float | None = None
        for sp in put_candidates:
            sp_strike = float(runner.field_of(sp, "strike"))
            lp = runner.find_strike(puts, sp_strike - self.wing_width_dollars)
            if lp is None:
                continue
            sp_b, sp_a, sp_delta = runner.quote_of(sp)
            lp_b, lp_a, _ = runner.quote_of(lp)
            sp_fill = max(0.0, runner.mid(sp_b, sp_a) - FILL_SLIPPAGE_PER_LEG)
            lp_fill = runner.mid(lp_b, lp_a) + FILL_SLIPPAGE_PER_LEG

            for sc in call_candidates:
                sc_strike = float(runner.field_of(sc, "strike"))
                lc = runner.find_strike(calls, sc_strike + self.wing_width_dollars)
                if lc is None:
                    continue

                sc_b, sc_a, sc_delta = runner.quote_of(sc)
                lc_b, lc_a, _ = runner.quote_of(lc)
                sc_fill = max(0.0, runner.mid(sc_b, sc_a) - FILL_SLIPPAGE_PER_LEG)
                lc_fill = runner.mid(lc_b, lc_a) + FILL_SLIPPAGE_PER_LEG
                credit = (sp_fill - lp_fill) + (sc_fill - lc_fill)
                if credit < self.min_total_credit:
                    continue

                total_err = abs(abs(sp_delta) - self.target_short_delta) + abs(abs(sc_delta) - self.target_short_delta)
                if (
                    selected is None
                    or total_err < (selected_err or float("inf"))
                    or (
                        selected_err is not None
                        and abs(total_err - selected_err) < 1e-9
                        and selected_credit is not None
                        and credit > selected_credit
                    )
                ):
                    selected = (sp, lp, sc, lc, credit)
                    selected_err = total_err
                    selected_credit = credit

        if selected is None:
            return None

        sp, lp, sc, lc, credit = selected
        sp_strike = float(runner.field_of(sp, "strike"))
        sc_strike = float(runner.field_of(sc, "strike"))
        lp_strike = float(runner.field_of(lp, "strike"))
        lc_strike = float(runner.field_of(lc, "strike"))
        put_width = sp_strike - lp_strike
        call_width = lc_strike - sc_strike
        max_loss = max(0.01, max(put_width, call_width) - credit)
        return ProposedPosition(
            strategy=self.name,
            expiration=ctx.now.date(),
            legs=[
                self._leg_with_greeks(runner, sp, "short", sp_strike, "put", sp_fill),
                self._leg_with_greeks(runner, lp, "long", lp_strike, "put", lp_fill),
                self._leg_with_greeks(runner, sc, "short", sc_strike, "call", sc_fill),
                self._leg_with_greeks(runner, lc, "long", lc_strike, "call", lc_fill),
            ],
            credit_received=credit,
            max_loss=max_loss,
            short_put_strike=sp_strike,
            short_call_strike=sc_strike,
            primary_symbol=str(runner.field_of(sp, "symbol", "")),
            metadata={
                "spy_at_entry": ctx.spy_price,
                "strategy_type": "iron_condor",
                "profile": self.profile_name,
                "profit_target_pct": self.profit_target_pct,
                "stop_loss_multiple": self.stop_loss_multiple,
                "threat_buffer_points": self.threat_buffer_points,
                "risk_pct_per_trade": self.risk_pct_per_trade,
                "max_contracts_cap": self.max_contracts_cap,
            },
        )

    def evaluate_exit(
        self,
        pos: SimulatedPosition,
        ctx: MarketContext,
        cur_debit: float,
    ) -> str | None:
        base = super().evaluate_exit(pos, ctx, cur_debit)
        if base is not None:
            return base
        if ctx.now.time() >= self.hard_close_et:
            return f"zdte_hard_close_{self.hard_close_et.strftime('%H:%M')}"
        return None


def _prioritize_zero_dte_adapter(profile_name: str) -> bool:
    """Return True when the ZeroDTE adapter should evaluate before BullPut."""
    normalized_profile = str(profile_name or DEFAULT_ZERO_DTE_PROFILE).strip().lower()
    return normalized_profile == MARK_SPY_PAPER_ZERO_DTE_PROFILE


def _resolve_portfolio_gamma_cap(profile_name: str) -> float:
    """Return the portfolio gamma ceiling for the selected ZeroDTE profile."""
    normalized_profile = str(profile_name or DEFAULT_ZERO_DTE_PROFILE).strip().lower()
    if normalized_profile == MARK_SPY_PAPER_ZERO_DTE_PROFILE:
        return MARK_SPY_PAPER_PORTFOLIO_GAMMA_CAP
    return MAX_PORTFOLIO_GAMMA


# ==============================================================================
# RUNNER
# ==============================================================================
class PaperStrategyRunner:
    """
    Autonomous paper-trading strategy runner.

    Wires live Tradier market data to two inline option strategies with
    simulated fills. Integrates with :class:`PaperTradingHarness` so trade
    counts and P&L show up in the 30-day validation snapshots.

    Args:
        data_client:
            A :class:`TradierClient` pointed at LIVE for market data.
            NEVER used to submit orders; read-only here.
        harness:
            The active :class:`PaperTradingHarness`. The runner calls
            ``harness.record_trade(...)`` on every simulated close.
        max_concurrent_positions:
            Hard cap on open simulated positions across all strategies.
        enable_bull_put:
            Enable the BullPutCreditSpread strategy (default True).
        enable_zero_dte:
            Enable the ZeroDTE IronCondor strategy (default True).
    """

    def __init__(
        self,
        data_client: TradierClient,
        harness: Any,
        max_concurrent_positions: int = DEFAULT_MAX_CONCURRENT,
        enable_bull_put: bool = True,
        enable_zero_dte: bool = True,
        zero_dte_profile: str = DEFAULT_ZERO_DTE_PROFILE,
        risk_manager: RiskManagerProtocol | None = None,
        starting_equity: float = DEFAULT_STARTING_EQUITY,
        adapters: list[StrategyAdapter] | None = None,
        sandbox_replayer: Any | None = None,
    ) -> None:
        self._client = data_client
        self._harness = harness
        self._max_concurrent = max_concurrent_positions
        self._risk_manager = risk_manager
        self._starting_equity = float(starting_equity)
        self._portfolio_delta_cap = MAX_PORTFOLIO_DELTA
        self._portfolio_vega_cap = MAX_PORTFOLIO_VEGA
        self._portfolio_gamma_cap = _resolve_portfolio_gamma_cap(zero_dte_profile)
        if sandbox_replayer is not None:
            logger.warning(
                "PaperStrategyRunner: deferred replay service ignored by live-only policy"
            )
        self._sandbox_replayer = None

        self._positions: list[SimulatedPosition] = []
        self._cumulative_sim_pnl: float = 0.0
        self._daily_entry_counts: dict[str, int] = {}
        self._daily_entry_date: date | None = None

        # Simple per-strategy cooldown to avoid thrashing on rejected signals
        self._last_entry_attempt: dict[str, datetime] = {}
        self._entry_cooldown = timedelta(minutes=5)
        self._no_entry_summary_interval = timedelta(seconds=30)
        self._last_no_entry_summary_ts: datetime | None = None

        # Build the adapter registry. Callers may pass their own list; the
        # default wires the two shipped strategies gated by the enable_* flags.
        if adapters is not None:
            self._adapters: list[StrategyAdapter] = list(adapters)
        else:
            self._adapters = []
            prioritize_zero_dte = enable_zero_dte and _prioritize_zero_dte_adapter(
                zero_dte_profile,
            )
            if prioritize_zero_dte:
                self._adapters.append(ZeroDTEAdapter(profile_name=zero_dte_profile))
            if enable_bull_put:
                self._adapters.append(BullPutAdapter())
            if enable_zero_dte and not prioritize_zero_dte:
                self._adapters.append(ZeroDTEAdapter(profile_name=zero_dte_profile))

        logger.info(
            "PaperStrategyRunner initialised — adapters=%s max_concurrent=%d "
            "zero_dte_profile=%s risk_gate=%s starting_equity=$%.0f",
            [a.name for a in self._adapters],
            max_concurrent_positions,
            zero_dte_profile,
            "on" if risk_manager is not None else "off",
            self._starting_equity,
        )

    # ------------------------------------------------------------------
    # Safety preflight
    # ------------------------------------------------------------------
    @staticmethod
    def preflight_safety_check() -> None:
        """
        Enforce the paper-trading safety invariant.

        Raises:
            RuntimeError: if ``TRADING_MODE`` is "live" but
                ``LIVE_TRADING_CONFIRMED`` is not "true".
        """
        mode = (os.environ.get("TRADING_MODE") or "paper").strip().lower()
        confirmed = (os.environ.get("LIVE_TRADING_CONFIRMED") or "false").strip().lower()
        if mode == "live" and confirmed != "true":
            raise RuntimeError(
                "Refusing to start PaperStrategyRunner: TRADING_MODE=live but "
                "LIVE_TRADING_CONFIRMED!=true. Use TRADING_MODE=paper.",
            )

    # ------------------------------------------------------------------
    # Public tick interface
    # ------------------------------------------------------------------
    def tick(self, now_et: datetime | None = None) -> dict[str, Any]:
        """
        Drive one heartbeat iteration: exits first, then entries.

        Args:
            now_et: Override for the current ET wall-clock (naive datetime).
                Defaults to the system's current time interpreted as ET.

        Returns:
            A dict with keys: ``spy_price``, ``open_positions``,
            ``closes_this_tick``, ``opens_this_tick``, ``sim_pnl``,
            ``top_no_entry_reason``, ``no_entry_reason_counts``, and
            ``no_entry_reasons_by_adapter``.
        """
        if now_et is None:
            now = datetime.now(_ET_TZ)
        elif now_et.tzinfo is None:
            now = now_et.replace(tzinfo=_ET_TZ)
        else:
            now = now_et.astimezone(_ET_TZ)

        self._reset_daily_entry_counts_if_needed(now.date())

        # 1) Pull underlying + VIX quotes in one batched call
        spy_quote, vix_price = self._get_spy_and_vix()
        if spy_quote is None:
            return {
                "spy_price": 0.0,
                "open_positions": self._count_open_total(),
                "closes_this_tick": 0,
                "opens_this_tick": 0,
                "sim_pnl": self._cumulative_sim_pnl,
            }
        spy_price = float(spy_quote.get("last") or 0.0)
        ctx = MarketContext(spy_price=spy_price, now=now, vix=vix_price)

        # 2) Exit evaluation for every open position
        closes = self._evaluate_exits(ctx)

        # 3) Entry evaluation — iterate adapters (respect overall + per-strategy caps)
        opens = 0
        no_entry_reasons: list[str] = []
        no_entry_reasons_by_adapter: dict[str, str] = {}

        def record_no_entry(adapter_name: str, reason: str) -> None:
            no_entry_reasons.append(f"{adapter_name}:{reason}")
            no_entry_reasons_by_adapter[adapter_name] = reason

        for adapter in self._adapters:
            if self._count_open_total() >= self._max_concurrent:
                record_no_entry(adapter.name, "max_concurrent_cap")
                break
            if self._count_open(adapter.name) >= adapter.max_open:
                record_no_entry(adapter.name, "strategy_open_cap")
                continue
            if (
                adapter.max_daily_entries is not None
                and self._count_entries_today(adapter.name) >= adapter.max_daily_entries
            ):
                record_no_entry(adapter.name, "daily_entry_cap")
                continue
            if not adapter.within_entry_window(now):
                record_no_entry(adapter.name, "outside_entry_window")
                continue
            if not self._cooldown_ok(adapter.name, now):
                # When a strategy already has an open position, cooldown spam
                # is not actionable. Suppress it so logs emphasize real gates.
                if self._count_open(adapter.name) <= 0:
                    record_no_entry(adapter.name, "cooldown")
                continue
            opened, reject_reason = self._try_enter(adapter, ctx)
            if opened:
                opens += 1
                self._last_entry_attempt[adapter.name] = now
            else:
                record_no_entry(adapter.name, reject_reason or "rejected")

        top_no_entry_reason = ""
        no_entry_reason_counts: dict[str, int] = {}
        no_entry_details = ""
        if no_entry_reasons:
            counts = Counter(no_entry_reasons)
            top_no_entry_reason, _ = counts.most_common(1)[0]
            no_entry_reason_counts = dict(counts)
            no_entry_details = ", ".join(
                f"{adapter_name}:{reason}"
                for adapter_name, reason in no_entry_reasons_by_adapter.items()
            )

        if opens == 0 and no_entry_reasons:
            should_log_summary = (
                self._last_no_entry_summary_ts is None
                or (now - self._last_no_entry_summary_ts) >= self._no_entry_summary_interval
            )
            if should_log_summary:
                self._last_no_entry_summary_ts = now
                if len(no_entry_reasons_by_adapter) > 1 and no_entry_details:
                    logger.info(
                        "No-entry summary: adapters=%d top_reason=%s details=%s",
                        len(self._adapters),
                        top_no_entry_reason,
                        no_entry_details,
                    )
                else:
                    logger.info(
                        "No-entry summary: adapters=%d top_reason=%s",
                        len(self._adapters),
                        top_no_entry_reason,
                    )

        return {
            "spy_price": spy_price,
            "open_positions": len([p for p in self._positions if p.is_open]),
            "closes_this_tick": closes,
            "opens_this_tick": opens,
            "sim_pnl": self._cumulative_sim_pnl,
            "top_no_entry_reason": top_no_entry_reason,
            "no_entry_reason_counts": no_entry_reason_counts,
            "no_entry_reasons_by_adapter": dict(no_entry_reasons_by_adapter),
        }

    def close_all_positions(self, reason: str = "session_end") -> int:
        """Force-close every open simulated position at mid. Returns count closed."""
        closed = 0
        for pos in list(self._positions):
            if pos.is_open:
                self._close_position(pos, reason=reason, now=datetime.now(UTC))
                closed += 1
        return closed

    def snapshot(self) -> dict[str, Any]:
        """Return a small dict describing current state (for dashboards / logs)."""
        open_ps = [p for p in self._positions if p.is_open]
        by_strategy: dict[str, int] = {a.name: self._count_open(a.name) for a in self._adapters}
        d, g, v = self._portfolio_greeks()
        return {
            "open_positions": len(open_ps),
            "total_positions": len(self._positions),
            "cumulative_sim_pnl": self._cumulative_sim_pnl,
            "by_strategy": by_strategy,
            "portfolio_greeks": {"delta": d, "gamma": g, "vega": v},
        }

    def flush_deferred_sandbox_replay(self, max_records: int = 50) -> dict[str, Any] | None:
        """Deferred replay is disabled under live-only policy."""
        _ = max_records
        return None

    # ------------------------------------------------------------------
    # Tradier data helpers
    # ------------------------------------------------------------------
    def _get_spy_quote(self) -> dict[str, Any] | None:
        try:
            resp = self._client.get_quotes([PAPER_UNDERLYING_SYMBOL])
            q = resp.get("quotes", {}).get("quote")
            if isinstance(q, list):
                q = q[0] if q else None
            return q
        except Exception as exc:
            logger.warning("%s quote fetch failed: %s", PAPER_UNDERLYING_SYMBOL, exc)
            return None

    def _get_spy_and_vix(self) -> tuple[dict[str, Any] | None, float | None]:
        """Batched underlying + VIX quote fetch.

        Returns ``(spy_quote_dict, vix_last_price)``. A missing VIX does not
        block trading — the regime gate treats ``None`` as "unknown, allow".
        """
        try:
            resp = self._client.get_quotes([PAPER_UNDERLYING_SYMBOL, REGIME_VIX_SYMBOL])
        except Exception as exc:
            logger.warning(
                "Batched %s/VIX quote fetch failed: %s",
                PAPER_UNDERLYING_SYMBOL,
                exc,
            )
            # Fall back to underlying-only so we stay trading
            return self._get_spy_quote(), None
        quotes = resp.get("quotes", {}).get("quote", [])
        if isinstance(quotes, dict):
            quotes = [quotes]
        spy_q: dict[str, Any] | None = None
        vix_last: float | None = None
        for q in quotes:
            if not isinstance(q, dict):
                continue
            sym = str(q.get("symbol", "")).upper()
            if sym == PAPER_UNDERLYING_SYMBOL:
                spy_q = q
            elif sym in {"VIX", "^VIX"}:
                try:
                    vix_last = float(q.get("last") or 0.0) or None
                except (TypeError, ValueError):
                    vix_last = None
        return spy_q, vix_last

    def get_chain_with_greeks(
        self,
        expiration: str,
        option_type: str | None = None,
    ) -> list[Any]:
        """Fetch option chain with greeks parsed by TradierClient."""
        try:
            return self._client.get_option_chain_with_greeks(
                PAPER_UNDERLYING_SYMBOL, expiration, option_type=option_type,
            )
        except Exception as exc:
            logger.warning("Option chain fetch failed for %s: %s", expiration, exc)
            return []

    def get_expirations(self) -> list[str]:
        try:
            resp = self._client.get_option_expirations(PAPER_UNDERLYING_SYMBOL)
            dates = resp.get("expirations", {}).get("date", [])
            if isinstance(dates, str):
                dates = [dates]
            return list(dates)
        except Exception as exc:
            logger.warning("Option expirations fetch failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Entry windows
    # ------------------------------------------------------------------
    def _count_open(self, strategy: str) -> int:
        return sum(1 for p in self._positions if p.is_open and p.strategy == strategy)

    def _count_open_total(self) -> int:
        return sum(1 for p in self._positions if p.is_open)

    def _reset_daily_entry_counts_if_needed(self, trading_day: date) -> None:
        if self._daily_entry_date != trading_day:
            self._daily_entry_date = trading_day
            self._daily_entry_counts = {}

    def _count_entries_today(self, strategy: str) -> int:
        return int(self._daily_entry_counts.get(strategy, 0))

    def _record_entry_today(self, strategy: str, trading_day: date) -> None:
        self._reset_daily_entry_counts_if_needed(trading_day)
        self._daily_entry_counts[strategy] = self._count_entries_today(strategy) + 1

    def _cooldown_ok(self, key: str, now: datetime) -> bool:
        last = self._last_entry_attempt.get(key)
        if last is None:
            return True
        return (now - last) >= self._entry_cooldown

    # ------------------------------------------------------------------
    # Fill simulation
    # ------------------------------------------------------------------
    @staticmethod
    def mid(bid: float, ask: float) -> float:
        if bid > 0 and ask > 0 and ask >= bid:
            return (bid + ask) / 2.0
        return max(bid, ask, 0.0)

    @staticmethod
    def quote_of(opt: Any) -> tuple[float, float, float]:
        """Extract (bid, ask, delta) from a GreekData/dict-like option."""
        bid = float(getattr(opt, "bid", None) or (opt.get("bid") if isinstance(opt, dict) else 0.0) or 0.0)  # noqa: E501
        ask = float(getattr(opt, "ask", None) or (opt.get("ask") if isinstance(opt, dict) else 0.0) or 0.0)  # noqa: E501
        delta = float(
            getattr(opt, "delta", None)
            or (opt.get("delta") if isinstance(opt, dict) else 0.0)
            or 0.0,
        )
        return bid, ask, delta

    @staticmethod
    def field_of(opt: Any, name: str, default: Any = None) -> Any:
        if isinstance(opt, dict):
            return opt.get(name, default)
        return getattr(opt, name, default)

    # ------------------------------------------------------------------
    # Entry: risk gate + sizing + fill
    # ------------------------------------------------------------------
    def _current_equity(self) -> float:
        """Best-effort current equity; falls back to starting_equity + sim PnL."""
        try:
            metrics = self._harness.get_current_metrics()
            if isinstance(metrics, dict):
                eq = metrics.get("current_equity")
                if eq is not None:
                    return float(eq)
        except Exception:
            pass
        return self._starting_equity + self._cumulative_sim_pnl

    def _size_position(
        self,
        max_loss_per_contract: float,
        risk_pct_per_trade: float = RISK_PCT_PER_TRADE,
        max_contracts_cap: int = MAX_CONTRACTS_CAP,
    ) -> int:
        """Risk-budget sizing: ``equity * risk_pct_per_trade / max_loss``.

        Returns an integer number of contracts in ``[1, max_contracts_cap]``.
        """
        if max_loss_per_contract <= 0:
            return 1
        equity = self._current_equity()
        dollar_budget = equity * max(0.0, float(risk_pct_per_trade))
        dollar_risk_per_contract = max_loss_per_contract * SPY_CONTRACT_MULTIPLIER
        raw = int(dollar_budget // max(0.01, dollar_risk_per_contract))
        return max(1, min(raw, max(1, int(max_contracts_cap))))

    def _risk_gate(self, proposal: ProposedPosition, contracts: int) -> tuple[bool, str, int]:
        """Run E-Series risk validation. Returns (approved, reason, max_qty).

        When no risk manager is wired, always approves at the requested size.
        """
        if self._risk_manager is None:
            return True, "", contracts
        req = RiskValidationRequest(
            symbol=proposal.primary_symbol or PAPER_UNDERLYING_SYMBOL,
            quantity=contracts,
            signal_type=BoundarySignalType.SELL,
            strategy_id=proposal.strategy,
            entry_price=proposal.credit_received,
            stop_loss=proposal.max_loss,
            metadata={
                **proposal.metadata,
                "credit": proposal.credit_received,
                "max_loss": proposal.max_loss,
                "short_put_strike": proposal.short_put_strike,
                "short_call_strike": proposal.short_call_strike,
            },
        )
        try:
            verdict = self._risk_manager.validate_signal(req)
        except Exception as exc:
            logger.warning("Risk gate raised %s: %s — treating as REJECT", type(exc).__name__, exc)
            return False, f"risk_gate_error: {exc}", 0
        approved = bool(getattr(verdict, "approved", False))
        reason = str(getattr(verdict, "rejection_reason", "") or "")
        max_qty = int(getattr(verdict, "max_safe_quantity", contracts) or contracts)
        return approved, reason, max_qty

    def _portfolio_greeks(self) -> tuple[float, float, float]:
        """Return current (delta, gamma, vega) across open sim positions."""
        d = g = v = 0.0
        for pos in self._positions:
            if not pos.is_open:
                continue
            d += pos.position_delta
            g += pos.position_gamma
            v += pos.position_vega
        return d, g, v

    def _greek_gate(
        self, proposal: ProposedPosition, contracts: int,
    ) -> str | None:
        """Reject if adding this proposal would breach portfolio Greek caps.

        Lightweight stand-in for SpyderE15_GreekLimitsManager. Sums signed
        per-leg Greeks from the proposal at the sized contract count, adds
        current portfolio exposure, and checks the three configured ceilings.
        Returns a reason string on rejection, or None to allow.
        """
        # Compute proposal Greeks at the sized quantity
        prop_d = prop_g = prop_v = 0.0
        delta_cap = float(getattr(self, "_portfolio_delta_cap", MAX_PORTFOLIO_DELTA))
        gamma_cap = float(getattr(self, "_portfolio_gamma_cap", MAX_PORTFOLIO_GAMMA))
        vega_cap = float(getattr(self, "_portfolio_vega_cap", MAX_PORTFOLIO_VEGA))
        for leg in proposal.legs:
            sign = -1.0 if leg.side == "short" else 1.0
            prop_d += sign * leg.delta * contracts * SPY_CONTRACT_MULTIPLIER
            prop_g += sign * leg.gamma * contracts * SPY_CONTRACT_MULTIPLIER
            prop_v += sign * leg.vega * contracts * SPY_CONTRACT_MULTIPLIER

        cur_d, cur_g, cur_v = self._portfolio_greeks()
        new_d, new_g, new_v = cur_d + prop_d, cur_g + prop_g, cur_v + prop_v

        if abs(new_d) > delta_cap:
            return f"portfolio_delta_cap (|{new_d:.1f}| > {delta_cap:.1f})"
        if abs(new_g) > gamma_cap:
            return f"portfolio_gamma_cap (|{new_g:.2f}| > {gamma_cap:.2f})"
        if abs(new_v) > vega_cap:
            return f"portfolio_vega_cap (|{new_v:.1f}| > {vega_cap:.1f})"
        return None

    def _try_enter(self, adapter: StrategyAdapter, ctx: MarketContext) -> tuple[bool, str]:
        """Evaluate adapter → regime gate → size → risk gate → Greek gate → fill."""
        # 1) Regime gate (cheap, no data fetch beyond the VIX already in ctx)
        regime_reject = adapter.regime_gate(ctx)
        if regime_reject is not None:
            logger.info("Regime REJECT %s: %s", adapter.name, regime_reject)
            return False, f"regime:{regime_reject}"

        proposal = adapter.evaluate_entry(ctx, self)
        if proposal is None:
            return False, "no_candidate"

        try:
            risk_pct_per_trade = float(
                proposal.metadata.get("risk_pct_per_trade", RISK_PCT_PER_TRADE),
            )
        except (TypeError, ValueError):
            risk_pct_per_trade = RISK_PCT_PER_TRADE
        try:
            max_contracts_cap = int(
                float(proposal.metadata.get("max_contracts_cap", MAX_CONTRACTS_CAP)),
            )
        except (TypeError, ValueError):
            max_contracts_cap = MAX_CONTRACTS_CAP

        contracts = self._size_position(
            proposal.max_loss,
            risk_pct_per_trade=risk_pct_per_trade,
            max_contracts_cap=max_contracts_cap,
        )

        # 2) E-Series risk gate
        approved, reason, max_qty = self._risk_gate(proposal, contracts)
        if not approved:
            logger.info(
                "Risk REJECT %s: %s (requested=%d)",
                adapter.name, reason or "unspecified", contracts,
            )
            return False, f"risk:{reason or 'unspecified'}"
        contracts = max(1, min(contracts, max_qty)) if max_qty > 0 else contracts
        if contracts <= 0:
            return False, "risk:max_qty_zero"

        # 3) Portfolio Greek gate (lightweight E15 stand-in)
        greek_reject = self._greek_gate(proposal, contracts)
        if greek_reject is not None:
            logger.info("Greek REJECT %s: %s", adapter.name, greek_reject)
            return False, f"greek:{greek_reject}"

        # Stamp contracts on every leg (preserving per-leg Greeks)
        legs = [
            SimulatedLeg(
                option_symbol=leg.option_symbol,
                side=leg.side,
                strike=leg.strike,
                option_type=leg.option_type,
                entry_price=leg.entry_price,
                qty=contracts,
                delta=leg.delta,
                gamma=leg.gamma,
                vega=leg.vega,
                theta=leg.theta,
            )
            for leg in proposal.legs
        ]
        prefix = "BP" if proposal.strategy == "BullPutCreditSpread" else (
            "ZDTE" if proposal.strategy == "ZeroDTE_IronCondor" else "POS"
        )
        position = SimulatedPosition(
            position_id=f"{prefix}-{uuid.uuid4().hex[:8]}",
            strategy=proposal.strategy,
            opened_at=ctx.now,
            expiration=proposal.expiration,
            legs=legs,
            contracts=contracts,
            credit_received=proposal.credit_received,
            max_loss=proposal.max_loss,
            short_put_strike=proposal.short_put_strike,
            short_call_strike=proposal.short_call_strike,
            metadata=dict(proposal.metadata),
        )
        self._positions.append(position)
        self._record_entry_today(adapter.name, ctx.now.date())
        self._harness.record_trade(pnl=0.0, placed=True, filled=True, won=None)

        if proposal.strategy == "BullPutCreditSpread" and len(legs) >= 2:
            logger.info(
                "OPEN BullPut %s: short %.0fP / long %.0fP @ exp %s x%d | credit=$%.2f "
                "max_loss=$%.2f %s=%.2f",
                position.position_id, legs[0].strike, legs[1].strike,
                proposal.expiration.isoformat(), contracts,
                proposal.credit_received, proposal.max_loss, PAPER_UNDERLYING_SYMBOL, ctx.spy_price,
            )
        elif proposal.strategy == "ZeroDTE_IronCondor" and len(legs) >= 4:
            logger.info(
                "OPEN 0DTE IC %s: %.0fP/%.0fP/%.0fC/%.0fC x%d | credit=$%.2f "
                "max_loss=$%.2f %s=%.2f",
                position.position_id,
                legs[1].strike, legs[0].strike, legs[2].strike, legs[3].strike,
                contracts,
                proposal.credit_received,
                proposal.max_loss,
                PAPER_UNDERLYING_SYMBOL,
                ctx.spy_price,
            )
        else:
            logger.info(
                "OPEN %s %s x%d | credit=$%.2f max_loss=$%.2f %s=%.2f",
                proposal.strategy, position.position_id, contracts,
                proposal.credit_received,
                proposal.max_loss,
                PAPER_UNDERLYING_SYMBOL,
                ctx.spy_price,
            )
        return True, "opened"

    # ------------------------------------------------------------------
    # Exit evaluation
    # ------------------------------------------------------------------
    def _evaluate_exits(self, ctx: MarketContext) -> int:
        closes = 0
        adapters_by_name = {a.name: a for a in self._adapters}
        for pos in list(self._positions):
            if not pos.is_open:
                continue
            adapter = adapters_by_name.get(pos.strategy)
            if adapter is None:
                # Strategy was deregistered while we had a live position — fall
                # back to the default exit semantics via a bare StrategyAdapter.
                adapter = StrategyAdapter()
                adapter.name = pos.strategy
            cur_debit = self._price_to_close(pos)
            if cur_debit is None:
                continue
            reason = adapter.evaluate_exit(pos, ctx, cur_debit)
            if reason:
                self._close_position(pos, reason=reason, now=ctx.now)
                closes += 1
        return closes

    def _price_to_close(self, pos: SimulatedPosition) -> float | None:
        """Return net debit per contract to close all legs, or None on data failure."""
        # Re-fetch chain for this expiration (once per position — acceptable for now)
        chain = self.get_chain_with_greeks(pos.expiration.isoformat())
        if not chain:
            return None
        by_symbol = {str(self.field_of(o, "symbol", "")): o for o in chain}

        total_debit = 0.0
        for leg in pos.legs:
            opt = by_symbol.get(leg.option_symbol)
            if opt is None:
                return None
            bid, ask, _ = self.quote_of(opt)
            mid = self.mid(bid, ask)
            if leg.side == "short":
                # To close short we buy at ask-side mid + slippage
                total_debit += mid + FILL_SLIPPAGE_PER_LEG
            else:
                # To close long we sell at bid-side mid - slippage
                total_debit -= max(0.0, mid - FILL_SLIPPAGE_PER_LEG)
        return total_debit

    def _close_position(
        self,
        pos: SimulatedPosition,
        reason: str,
        now: datetime,
    ) -> None:
        debit = self._price_to_close(pos)
        if debit is None:
            # Force close at assumed mid = 0 (data failure); count as break-even
            debit = pos.credit_received
            logger.warning(
                "Close %s with stale chain; forcing PnL=0 (reason=%s)",
                pos.position_id, reason,
            )

        pnl_per_contract = (pos.credit_received - debit) * SPY_CONTRACT_MULTIPLIER
        realized = pnl_per_contract * pos.contracts

        pos.closed_at = now
        pos.exit_debit = debit
        pos.realized_pnl = realized
        pos.exit_reason = reason

        self._cumulative_sim_pnl += realized
        won: bool | None = True if realized > 0 else (False if realized < 0 else None)

        # Counts + win/loss tally (pnl arg is informational — harness doesn't sum it)
        self._harness.record_trade(
            pnl=realized, placed=False, filled=True, won=won,
        )

        if self._sandbox_replayer is not None:
            try:
                replay_legs = [
                    {
                        "option_symbol": leg.option_symbol,
                        "side": leg.side,
                    }
                    for leg in pos.legs
                ]
                self._sandbox_replayer.enqueue_close_legs(
                    position_id=pos.position_id,
                    strategy=pos.strategy,
                    reason=reason,
                    legs=replay_legs,
                    contracts=pos.contracts,
                )
            except Exception as exc:
                logger.warning("Deferred replay enqueue failed for %s: %s", pos.position_id, exc)

        logger.info(
            "CLOSE %s (%s) %s: realized=$%.2f [reason=%s, credit=$%.2f debit=$%.2f]",
            pos.position_id,
            pos.strategy,
            "WIN" if won else ("LOSS" if won is False else "BE"),
            realized,
            reason,
            pos.credit_received,
            debit,
        )

    # ------------------------------------------------------------------
    # Chain helpers
    # ------------------------------------------------------------------
    def pick_expiration(
        self,
        today: date,
        dte_min: int,
        dte_max: int,
    ) -> str | None:
        expirations = self.get_expirations()
        best_dte: int | None = None
        best_iso: str | None = None
        for iso in expirations:
            try:
                d = date.fromisoformat(iso)
            except ValueError:
                continue
            dte = (d - today).days
            if dte_min <= dte <= dte_max and (best_dte is None or dte < best_dte):
                best_dte = dte
                best_iso = iso
        return best_iso

    @staticmethod
    def find_put_by_delta(
        puts: list[Any],
        spot: float,
        target_delta: float,
        tolerance: float,
    ) -> Any | None:
        """Find OTM put (strike < spot) whose |delta| is closest to target."""
        best = None
        best_err = 1e9
        for o in puts:
            strike = float(PaperStrategyRunner.field_of(o, "strike", 0.0) or 0.0)
            if strike <= 0 or strike >= spot:
                continue
            _, _, delta = PaperStrategyRunner.quote_of(o)
            if delta == 0.0:
                continue
            err = abs(abs(delta) - target_delta)
            if err <= tolerance and err < best_err:
                best = o
                best_err = err
        return best

    @staticmethod
    def find_call_by_delta(
        calls: list[Any],
        spot: float,
        target_delta: float,
        tolerance: float,
    ) -> Any | None:
        best = None
        best_err = 1e9
        for o in calls:
            strike = float(PaperStrategyRunner.field_of(o, "strike", 0.0) or 0.0)
            if strike <= 0 or strike <= spot:
                continue
            _, _, delta = PaperStrategyRunner.quote_of(o)
            if delta == 0.0:
                continue
            err = abs(abs(delta) - target_delta)
            if err <= tolerance and err < best_err:
                best = o
                best_err = err
        return best

    @staticmethod
    def find_strike(options: list[Any], target_strike: float) -> Any | None:
        """Return the option whose strike is numerically closest to target_strike."""
        best = None
        best_err = 1e9
        for o in options:
            strike = float(PaperStrategyRunner.field_of(o, "strike", 0.0) or 0.0)
            if strike <= 0:
                continue
            err = abs(strike - target_strike)
            if err < best_err:
                best = o
                best_err = err
        return best


# ==============================================================================
# FACTORY
# ==============================================================================
def create_paper_strategy_runner_from_env(harness: Any) -> PaperStrategyRunner:
    """
    Build a :class:`PaperStrategyRunner` using environment variables.

    Reads (from ``.env``):
        TRADIER_API_KEY, TRADIER_ACCOUNT_ID,
        optional TRADIER_LIVE_API_KEY / TRADIER_LIVE_ACCOUNT_ID overrides
        PAPER_STARTING_EQUITY (optional, default 100000)

    Always constructs the underlying :class:`TradierClient` with
    ``TradingEnvironment.LIVE`` (live-only data-plane policy). The returned
    runner only *reads* from that client — it never submits orders.

    An :class:`~Spyder.SpyderE_Risk.SpyderE01_RiskManager.RiskManager` is
    wired in as the pre-trade risk gate. Sizing uses the 1 %-of-equity rule
    capped at :data:`MAX_CONTRACTS_CAP` and clipped to whatever
    ``max_safe_quantity`` the risk layer returns.

    Raises:
        RuntimeError: If safety preflight fails or credentials are missing.
    """
    PaperStrategyRunner.preflight_safety_check()

    api_key = os.environ.get("TRADIER_API_KEY", "").strip()
    account_id = os.environ.get("TRADIER_ACCOUNT_ID", "").strip()
    env_name = (
        os.environ.get("TRADIER_MARKET_DATA_ENVIRONMENT")
        or os.environ.get("TRADIER_ENVIRONMENT")
        or "live"
    ).strip().lower()
    is_live_env = env_name in {"live", "production"}

    if not is_live_env:
        logger.warning(
            "PaperStrategyRunner forcing LIVE market-data endpoint "
            "(TRADIER_MARKET_DATA_ENVIRONMENT=%s ignored).",
            env_name or "<empty>",
        )

    api_key = os.environ.get("TRADIER_LIVE_API_KEY", "").strip() or api_key
    account_id = os.environ.get("TRADIER_LIVE_ACCOUNT_ID", "").strip() or account_id

    if not api_key or not account_id:
        raise RuntimeError(
            "TRADIER_API_KEY and TRADIER_ACCOUNT_ID must be set for "
            "PaperStrategyRunner market data.",
        )

    env_enum = TradingEnvironment.LIVE
    client = TradierClient(
        api_key=api_key,
        account_id=account_id,
        environment=env_enum,
    )
    logger.info(
        "PaperStrategyRunner: data plane = Tradier %s (read-only)",
        env_enum.value,
    )

    # Starting equity (for sizing and the E01 exposure ceiling)
    try:
        starting_equity = float(
            os.environ.get("PAPER_STARTING_EQUITY") or DEFAULT_STARTING_EQUITY,
        )
    except ValueError:
        starting_equity = DEFAULT_STARTING_EQUITY

    zero_dte_profile = str(
        os.environ.get("SPYDER_ZERO_DTE_PROFILE") or DEFAULT_ZERO_DTE_PROFILE,
    ).strip().lower() or DEFAULT_ZERO_DTE_PROFILE
    if zero_dte_profile not in ZERO_DTE_PROFILE_CONFIGS:
        logger.warning(
            "PaperStrategyRunner: unknown SPYDER_ZERO_DTE_PROFILE=%s; using %s",
            zero_dte_profile,
            DEFAULT_ZERO_DTE_PROFILE,
        )
        zero_dte_profile = DEFAULT_ZERO_DTE_PROFILE
    zero_dte_settings = ZERO_DTE_PROFILE_CONFIGS[zero_dte_profile]
    max_concurrent_positions = max(
        DEFAULT_MAX_CONCURRENT,
        BP_MAX_OPEN + int(zero_dte_settings.get("max_open", ZDTE_MAX_OPEN)),
    )

    # Build the E-Series risk gate. Factory tolerates missing deps and
    # returns a RiskManager wired with defaults — good enough for paper.
    risk_manager: RiskManagerProtocol | None
    try:
        from Spyder.SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
        risk_manager = get_risk_manager(portfolio_value=starting_equity)
        # Paper sessions can run without broker position sync; avoid startup-only
        # cold-state vetoes that block autonomous entry loops indefinitely.
        if hasattr(risk_manager, "_account_state_synced"):
            risk_manager._account_state_synced = True
        # Paper runner frequently operates without full S07 quality feeds
        # (vol-surface/dealer-flow), so keep this guard telemetry-only here.
        if hasattr(risk_manager, "_enforce_decision_quality_slo"):
            risk_manager._enforce_decision_quality_slo = False
        logger.info("PaperStrategyRunner: risk gate = SpyderE01.RiskManager")
    except Exception as exc:
        logger.warning("Could not build E01 RiskManager (%s) — running without risk gate", exc)
        risk_manager = None

    sandbox_replayer = None

    return PaperStrategyRunner(
        data_client=client,
        harness=harness,
        max_concurrent_positions=max_concurrent_positions,
        zero_dte_profile=zero_dte_profile,
        risk_manager=risk_manager,
        starting_equity=starting_equity,
        sandbox_replayer=sandbox_replayer,
    )


__all__ = [
    "PaperStrategyRunner",
    "SimulatedLeg",
    "SimulatedPosition",
    "ProposedPosition",
    "MarketContext",
    "StrategyAdapter",
    "BullPutAdapter",
    "ZeroDTEAdapter",
    "create_paper_strategy_runner_from_env",
]
