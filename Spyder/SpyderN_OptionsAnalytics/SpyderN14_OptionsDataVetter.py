#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderN_OptionsAnalytics
Module: SpyderN14_OptionsDataVetter.py
Purpose: Central vetting pipeline for raw OPRA data from Tradier

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-28 Time: 00:00:00

Description:
    Single entry-point that ALL consumers (strategies, risk, analytics) must
    route Tradier option-chain data through before use.

    Applies, in order:
        1. Structural sanity (symbol non-empty, strike > 0, known option_type)
        2. Market-quality guards (crossed / locked market, excessive spread)
        3. Liquidity gate (volume and/or open-interest floor)
        4. Greeks bounds (delta, gamma, theta, vega, rho, IV — per contract)
        5. Optional BSM cross-check: re-computes delta from N01 and flags
           contracts where Tradier's reported delta deviates by more than
           MAX_DELTA_DEVIATION from the BSM value.

    Rejected contracts are counted and logged at WARNING level; callers receive
    only the vetted subset as a plain ``list[GreekData]``.

    Usage example::

        from Spyder.SpyderN_OptionsAnalytics.SpyderN14_OptionsDataVetter import (
            OptionsDataVetter,
        )
        vetter = OptionsDataVetter()
        clean = vetter.vet(raw_greek_data, spot_price=spy_price)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Lazy-import GreekData so this module does NOT create a circular dependency
# with SpyderB40_TradierClient.  The import is resolved at call time.
try:
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import GreekData
    _GREEK_DATA_AVAILABLE = True
except ImportError:
    _GREEK_DATA_AVAILABLE = False
    GreekData = Any  # type: ignore[assignment,misc]

# BSM pricer for cross-check (optional — vetter works without it)
try:
    from Spyder.SpyderN_OptionsAnalytics.SpyderN01_OptionsPricer import OptionsPricer
    _PRICER_AVAILABLE = True
except ImportError:
    _PRICER_AVAILABLE = False
    OptionsPricer = None  # type: ignore[assignment]

# ==============================================================================
# CONSTANTS
# ==============================================================================

# --- Greeks absolute bounds ---
_DELTA_ABS_MAX: float = 1.0          # |delta| must be ≤ 1.0
_GAMMA_MAX: float = 1.0              # gamma must be in [0, 1.0]
_THETA_MIN: float = -100.0           # daily theta floor (extreme long-dated)
_THETA_MAX: float = 10.0             # positive theta only plausible for deep ITM
_VEGA_MIN: float = -0.01             # vega is theoretically ≥ 0; allow tiny negatives
_VEGA_MAX: float = 50.0              # sanity ceiling
_IV_MIN: float = 0.0                 # 0 allowed (illiquid OTM); negative is impossible
_IV_MAX: float = 5.0                 # 500% IV ceiling — anything above is a data error

# --- Market quality ---
_MAX_SPREAD_PCT: float = 150.0       # bid-ask spread as % of mid — above = too wide
_MIN_MID_FOR_SPREAD_CHECK: float = 0.01  # skip spread-pct check on sub-penny mids

# --- Liquidity ---
_MIN_OPEN_INTEREST: int = 0          # 0 = disabled; set > 0 to require OI
_MIN_VOLUME: int = 0                 # 0 = disabled; set > 0 to require volume

# --- BSM cross-check ---
_BSM_CHECK_ENABLED: bool = True      # toggle off if N01 is slow / unavailable
_MAX_DELTA_DEVIATION: float = 0.15   # flag when |delta_tradier - delta_bsm| > this
_DEFAULT_RISK_FREE_RATE: float = 0.05


# ==============================================================================
# ENUMS & DATA CLASSES
# ==============================================================================

class VetReason(Enum):
    """Reason a contract was rejected by the vetter."""
    EMPTY_SYMBOL = "empty_symbol"
    INVALID_STRIKE = "invalid_strike"
    UNKNOWN_OPTION_TYPE = "unknown_option_type"
    CROSSED_MARKET = "crossed_market"
    LOCKED_MARKET = "locked_market"
    SPREAD_TOO_WIDE = "spread_too_wide"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"
    DELTA_OUT_OF_BOUNDS = "delta_out_of_bounds"
    GAMMA_OUT_OF_BOUNDS = "gamma_out_of_bounds"
    THETA_OUT_OF_BOUNDS = "theta_out_of_bounds"
    VEGA_OUT_OF_BOUNDS = "vega_out_of_bounds"
    IV_OUT_OF_BOUNDS = "iv_out_of_bounds"
    BSM_DELTA_DEVIATION = "bsm_delta_deviation"


@dataclass
class VetResult:
    """
    Summary of a single vetting pass.

    Attributes:
        accepted: Contracts that passed all checks.
        rejected: List of (contract, reason) pairs for every dropped contract.
        total_in: Total input contracts.
        elapsed_ms: Wall-clock time for the vetting call (ms).
    """
    accepted: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    total_in: int = 0
    elapsed_ms: float = 0.0

    @property
    def accept_rate(self) -> float:
        """Fraction of contracts accepted (0.0 – 1.0)."""
        if self.total_in == 0:
            return 1.0
        return len(self.accepted) / self.total_in


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class OptionsDataVetter:
    """
    Central vetting pipeline for raw OPRA / Tradier option-chain data.

    Instantiate once and reuse across the session; the instance is
    thread-safe (all state is immutable after construction).

    Args:
        max_spread_pct: Maximum bid-ask spread as % of mid (default 150 %).
        min_open_interest: Minimum OI to accept a contract (0 = disabled).
        min_volume: Minimum volume to accept a contract (0 = disabled).
        bsm_check: Whether to cross-check delta against BSM model.
        max_delta_deviation: Max |Δtradier − Δbsm| before flagging (default 0.15).
        risk_free_rate: Risk-free rate for BSM delta cross-check (default 5 %).
    """

    def __init__(
        self,
        max_spread_pct: float = _MAX_SPREAD_PCT,
        min_open_interest: int = _MIN_OPEN_INTEREST,
        min_volume: int = _MIN_VOLUME,
        bsm_check: bool = _BSM_CHECK_ENABLED,
        max_delta_deviation: float = _MAX_DELTA_DEVIATION,
        risk_free_rate: float = _DEFAULT_RISK_FREE_RATE,
    ) -> None:
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        self.max_spread_pct = max_spread_pct
        self.min_open_interest = min_open_interest
        self.min_volume = min_volume
        self.bsm_check = bsm_check and _PRICER_AVAILABLE
        self.max_delta_deviation = max_delta_deviation
        self.risk_free_rate = risk_free_rate

        self._pricer: Any = OptionsPricer() if (self.bsm_check and OptionsPricer) else None
        # Rejection-summary log throttling: emit steady-state summaries less often
        # while still surfacing meaningful quality changes immediately.
        self._vet_log_lock = threading.Lock()
        self._last_reject_log_ts: datetime | None = None
        self._last_reject_accept_rate: float | None = None

        self.logger.debug(
            "OptionsDataVetter ready — spread_pct_max=%.0f%%, OI_min=%d, "
            "vol_min=%d, bsm_check=%s",
            self.max_spread_pct, self.min_open_interest, self.min_volume, self.bsm_check,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def vet(
        self,
        contracts: list,
        spot_price: float = 0.0,
    ) -> list:
        """
        Vet a list of ``GreekData`` objects and return only the clean subset.

        Args:
            contracts: Raw ``list[GreekData]`` from
                ``TradierClient.get_option_chain_with_greeks()``.
            spot_price: Current underlying spot price.  Required for the BSM
                delta cross-check; ignored when ``bsm_check=False``.

        Returns:
            Filtered ``list[GreekData]`` — only contracts that pass all checks.
        """
        result = self.vet_detailed(contracts, spot_price=spot_price)
        return result.accepted

    def vet_detailed(
        self,
        contracts: list,
        spot_price: float = 0.0,
    ) -> VetResult:
        """
        Like :meth:`vet` but returns a full :class:`VetResult` with rejection detail.

        Args:
            contracts: Raw ``list[GreekData]``.
            spot_price: Current underlying spot price.

        Returns:
            :class:`VetResult` with ``accepted``, ``rejected``, and statistics.
        """
        t0 = datetime.now(UTC)
        result = VetResult(total_in=len(contracts))

        for contract in contracts:
            reason = self._check(contract, spot_price)
            if reason is None:
                result.accepted.append(contract)
            else:
                result.rejected.append((contract, reason))

        elapsed = (datetime.now(UTC) - t0).total_seconds() * 1000
        result.elapsed_ms = elapsed

        if result.rejected:
            should_log = True
            now_utc = datetime.now(UTC)
            # Always surface genuine quality degradation as warning.
            if result.accept_rate < 0.70:
                log_fn = self.logger.warning
            else:
                log_fn = self.logger.info
                # For healthy acceptance, reduce repeated noise by logging only
                # on a periodic heartbeat.
                with self._vet_log_lock:
                    last_ts = self._last_reject_log_ts
                    time_elapsed = (
                        last_ts is None
                        or (now_utc - last_ts).total_seconds() >= 180
                    )
                    should_log = time_elapsed

                    if should_log:
                        self._last_reject_log_ts = now_utc
                        self._last_reject_accept_rate = result.accept_rate

            if should_log:
                log_fn(
                    "OptionsDataVetter: rejected %d/%d contracts (%.1f%% acceptance) "
                    "in %.1f ms — reasons: %s",
                    len(result.rejected),
                    result.total_in,
                    result.accept_rate * 100,
                    elapsed,
                    self._summarise_reasons(result.rejected),
                )

        return result

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    def _check(self, g: Any, spot_price: float) -> "VetReason | None":
        """
        Run all checks against a single contract.

        Returns:
            The first :class:`VetReason` that fails, or ``None`` if clean.
        """
        # 1. Structural
        if not g.symbol:
            return VetReason.EMPTY_SYMBOL
        if g.strike <= 0.0:
            return VetReason.INVALID_STRIKE
        if g.option_type.lower() not in ("call", "put"):
            return VetReason.UNKNOWN_OPTION_TYPE

        # 2. Market quality
        if g.bid > 0.0 and g.ask > 0.0:
            if g.bid > g.ask:
                return VetReason.CROSSED_MARKET
            if g.bid == g.ask and g.bid > 0.05:
                # Locked market on non-penny options is suspicious
                return VetReason.LOCKED_MARKET
            if g.mid >= _MIN_MID_FOR_SPREAD_CHECK:
                spread_pct = g.spread_pct  # uses GreekData.spread_pct property
                if spread_pct > self.max_spread_pct:
                    return VetReason.SPREAD_TOO_WIDE

        # 3. Liquidity
        if self.min_open_interest > 0 and g.open_interest < self.min_open_interest:
            return VetReason.INSUFFICIENT_LIQUIDITY
        if self.min_volume > 0 and g.volume < self.min_volume:
            return VetReason.INSUFFICIENT_LIQUIDITY

        # 4. Greeks bounds
        if not math.isfinite(g.delta) or abs(g.delta) > _DELTA_ABS_MAX:
            return VetReason.DELTA_OUT_OF_BOUNDS
        if not math.isfinite(g.gamma) or not (0.0 <= g.gamma <= _GAMMA_MAX):
            return VetReason.GAMMA_OUT_OF_BOUNDS
        if not math.isfinite(g.theta) or not (_THETA_MIN <= g.theta <= _THETA_MAX):
            return VetReason.THETA_OUT_OF_BOUNDS
        if not math.isfinite(g.vega) or not (_VEGA_MIN <= g.vega <= _VEGA_MAX):
            return VetReason.VEGA_OUT_OF_BOUNDS
        iv_value = g.iv
        if math.isfinite(iv_value) and (_IV_MAX < iv_value <= (_IV_MAX * 100.0)):
            # Some providers return IV in percent points (e.g., 42.5) instead
            # of decimal units (0.425). Normalize in place for downstream use.
            iv_value = iv_value / 100.0
            try:
                g.iv = iv_value
            except Exception:
                pass

        if not math.isfinite(iv_value) or not (_IV_MIN <= iv_value <= _IV_MAX):
            return VetReason.IV_OUT_OF_BOUNDS

        # 5. BSM delta cross-check (optional)
        if self.bsm_check and spot_price > 0.0 and g.iv > 0.0:
            bsm_delta = self._bsm_delta(g, spot_price)
            if bsm_delta is not None:
                deviation = abs(g.delta - bsm_delta)
                if deviation > self.max_delta_deviation:
                    self.logger.debug(
                        "BSM delta deviation on %s: tradier=%.4f bsm=%.4f diff=%.4f",
                        g.symbol, g.delta, bsm_delta, deviation,
                    )
                    return VetReason.BSM_DELTA_DEVIATION

        return None

    def _bsm_delta(self, g: Any, spot: float) -> "float | None":
        """
        Compute BSM delta via N01_OptionsPricer and return it, or ``None`` on error.

        Args:
            g: GreekData contract.
            spot: Underlying spot price.

        Returns:
            BSM delta float, or ``None`` if computation fails.
        """
        try:
            dte = self._parse_dte(g.expiration)
            if dte <= 0:
                return None
            T = dte / 365.0
            sigma = g.iv
            K = g.strike
            r = self.risk_free_rate

            d1 = (math.log(spot / K) + (r + 0.5 * sigma ** 2) * T) / (
                sigma * math.sqrt(T)
            )
            from scipy.stats import norm
            if g.option_type.lower() == "call":
                return norm.cdf(d1)
            else:
                return norm.cdf(d1) - 1.0
        except Exception:
            return None

    @staticmethod
    def _parse_dte(expiration: str) -> int:
        """
        Parse expiration string (YYYY-MM-DD or YYMMDD) into days-to-expiry.

        Args:
            expiration: Expiration date string.

        Returns:
            Integer DTE, or 0 if unparseable.
        """
        try:
            from datetime import date
            today = date.today()
            if "-" in expiration:
                exp = date.fromisoformat(expiration)
            elif len(expiration) == 6:
                yy, mm, dd = int(expiration[:2]), int(expiration[2:4]), int(expiration[4:])
                exp = date(2000 + yy, mm, dd)
            else:
                return 0
            return max(0, (exp - today).days)
        except (ValueError, OverflowError):
            return 0

    @staticmethod
    def _summarise_reasons(rejected: list) -> str:
        """
        Build a compact reason-count string for logging.

        Args:
            rejected: List of (contract, VetReason) tuples.

        Returns:
            String like ``"crossed_market×3, spread_too_wide×1"``.
        """
        counts: dict[str, int] = {}
        for _, reason in rejected:
            key = reason.value
            counts[key] = counts.get(key, 0) + 1
        return ", ".join(f"{k}×{v}" for k, v in sorted(counts.items()))


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================

_vetter_instance: OptionsDataVetter | None = None
_vetter_lock = threading.Lock()


def get_vetter(
    max_spread_pct: float = _MAX_SPREAD_PCT,
    min_open_interest: int = _MIN_OPEN_INTEREST,
    min_volume: int = _MIN_VOLUME,
) -> OptionsDataVetter:
    """
    Return the module-level :class:`OptionsDataVetter` singleton.

    The instance is created on first call and reused thereafter.

    Args:
        max_spread_pct: Passed to constructor on first call only.
        min_open_interest: Passed to constructor on first call only.
        min_volume: Passed to constructor on first call only.

    Returns:
        :class:`OptionsDataVetter` singleton.
    """
    global _vetter_instance
    if _vetter_instance is None:
        with _vetter_lock:
            if _vetter_instance is None:
                _vetter_instance = OptionsDataVetter(
                    max_spread_pct=max_spread_pct,
                    min_open_interest=min_open_interest,
                    min_volume=min_volume,
                )
    return _vetter_instance
