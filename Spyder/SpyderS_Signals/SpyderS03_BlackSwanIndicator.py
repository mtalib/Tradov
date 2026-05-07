#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderS03_BlackSwanIndicator.py
Group: S (Signals)
Purpose: Black Swan tail-risk indicator — data collection and composite score calculation
Author: Mohamed Talib
Date Created: 2025-01-31
Last Updated: 2026-03-27 Time: 00:00:00

Description:
    Merged module combining market data collection with Black Swan risk score
    calculation. Produces a composite tail-risk score on a 1–5 scale where
    1 = minimal / normal conditions and 5 = extreme / crisis-level risk.

Calculation Methodology:
    The overall Black Swan score is a weighted sum of four independent components:

        Component           Weight   Primary Input
        -----------------   -------  ------------------------------------------
        Volatility          35 %     VIX index (^VIX)
        Credit Stress       25 %     HYG / LQD price-ratio (high-yield spread)
        Liquidity           20 %     US Dollar Index (DX-Y.NYB)
        Market Internals    20 %     SPY price momentum (currently simplified)

    Overall Score = Σ(component_raw_score × weight)

    A momentum adjustment of +0.2 is applied automatically when the trailing
    5-period regression slope exceeds 0.2, indicating rapid risk deterioration.
    The final score is clamped to the range [1.0, 5.0].

Score Thresholds:
    GREEN   ≤ 1.95  Normal conditions — no action required
    YELLOW  ≤ 2.95  Elevated risk — monitor closely, manage exposure
    RED     ≥ 3.00  High risk — consider defensive positioning or hedges

Component Scoring Detail:
    Volatility (^VIX):
        VIX < 12    → 1.0               (very low volatility)
        VIX 12–20   → 1.5 – 2.0        (normal, linear interpolation)
        VIX 20–30   → 2.0 – 3.0        (elevated)
        VIX 30–40   → 3.0 – 4.0        (high)
        VIX > 40    → 4.0 – 5.0        (extreme)

    Credit Stress (HYG / LQD ratio):
        ratio > 0.73 → stress rising    (score increases linearly above baseline)
        ratio < 0.69 → conditions tight (moderate score increase)
        0.69 – 0.73  → 1.0             (normal credit conditions)

    Liquidity (DXY):
        DXY > 110   → 3.0+              (dollar squeeze — severe liquidity stress)
        DXY 105–110 → 2.0 – 3.0        (strong dollar — moderate stress)
        DXY ≤ 105   → 1.5              (normal liquidity)

    Market Internals:
        Currently returns a fixed neutral score of 1.5 (simplified placeholder).
        Planned: NYSE TICK, TRIN, advance/decline ratio, and breadth indicators.

When Calculations Are Triggered:
    - On demand:   call `calculate_swan_score()` at any time from any module.
    - Via scheduler: SpyderS04_BlackSwanScheduler invokes this module at the
      default schedule times: 04:00, 09:15, 12:00, 15:45, 16:30 ET.
    - Caching: market data is cached for 60 seconds by default (configurable via
      `cache_ttl`). Repeated calls within the TTL window return the cached result
      without hitting the data source again.

Data Sources:
    Primary:  yfinance — ^VIX, ^VIX9D, ^VXN, ^RVX (volatility)
                         HYG, LQD, TLT (credit)
                         SPY, QQQ, IWM, DX-Y.NYB (market / liquidity)
    Fallback: Simulated random values when yfinance is unavailable (test/offline).

Output (BlackSwanResult dataclass):
    overall_score       float        Composite score 1.0 – 5.0
    status              RiskStatus   GREEN / YELLOW / RED
    component_scores    dict         Raw and weighted scores per component
    data_quality        DataQuality  GOOD (>80 % symbols) / PARTIAL / POOR
    calculation_time_ms float        Wall-clock time for the full calculation
    timestamp           datetime     UTC timestamp of the calculation
    raw_data            dict|None    Full market data snapshot (if requested)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import numpy as np

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import yfinance as yf

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

try:
    from Spyder.SpyderC_MarketData.SpyderC29_DataProviderRouter import get_data_provider as _get_c29_provider  # noqa: E501
    _C29_AVAILABLE = True
except ImportError:
    _get_c29_provider = None  # type: ignore[assignment]
    _C29_AVAILABLE = False


# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

    SPYDER_INTEGRATION = True
except ImportError:
    SpyderLogger = logging
    SpyderErrorHandler = None
    SPYDER_INTEGRATION = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Risk Thresholds
GREEN_MAX = 1.95  # Below this = GREEN (normal)
YELLOW_MAX = 2.95  # Below this = YELLOW (elevated)
RED_MIN = 3.0  # Above this = RED (high risk)

# Component Weights
DEFAULT_WEIGHTS = {
    "volatility": 0.35,
    "credit_stress": 0.25,
    "liquidity": 0.20,
    "market_internals": 0.20,
}

# Data Source Symbols
VOLATILITY_SYMBOLS = {"vix": "^VIX", "vix9d": "^VIX9D", "vxn": "^VXN", "rvx": "^RVX"}

CREDIT_SYMBOLS = {
    "hyg": "HYG",  # High yield bonds
    "lqd": "LQD",  # Investment grade bonds
    "tlt": "TLT",  # Treasuries
}

MARKET_SYMBOLS = {"spy": "SPY", "qqq": "QQQ", "iwm": "IWM", "dxy": "DX-Y.NYB"}

# ==============================================================================
# ENUMS
# ==============================================================================


class RiskStatus(Enum):
    """Risk status levels"""

    GREEN = "GREEN"  # Normal conditions
    YELLOW = "YELLOW"  # Elevated risk
    RED = "RED"  # High risk


class DataQuality(Enum):
    """Data quality assessment"""

    GOOD = "good"
    PARTIAL = "partial"
    POOR = "poor"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class ComponentScore:
    """Individual component score"""

    name: str
    raw_score: float
    weight: float
    weighted_score: float
    description: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BlackSwanResult:
    """Complete Black Swan calculation result"""

    timestamp: datetime
    overall_score: float
    status: RiskStatus
    component_scores: dict[str, ComponentScore]
    data_quality: DataQuality
    calculation_time_ms: float
    raw_data: dict | None = None


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class BlackSwanIndicator:
    """
    Unified Black Swan risk indicator with data collection and calculation.

    This class combines market data collection with risk calculation to provide
    a comprehensive tail risk assessment score.

    Attributes:
        weights: Component weight configuration
        cache_ttl: Cache time-to-live in seconds
        use_cache: Whether to use cached data

    Example:
        >>> indicator = BlackSwanIndicator()
        >>> result = indicator.calculate_swan_score()
        >>> print(f"SWAN Score: {result.overall_score:.2f} ({result.status.value})")
    """

    def __init__(self, config: dict | None = None):
        """Initialize Black Swan Indicator"""
        # Logging
        if SPYDER_INTEGRATION:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger(__name__)
            self.error_handler = None

        # Configuration
        self.config = config or {}
        self.weights = self.config.get("weights", DEFAULT_WEIGHTS)
        self.cache_ttl = self.config.get("cache_ttl", 60)  # seconds
        self.use_cache = self.config.get("use_cache", True)

        # Data cache
        self._cache = {}
        self._cache_timestamps = {}

        # Historical scores for momentum calculation
        self.score_history = []

        self.logger.debug("Black Swan Indicator initialized")

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def calculate_swan_score(self, market_internals_override: dict | None = None) -> BlackSwanResult:
        """
        Calculate the complete Black Swan risk score.

        Args:
            market_internals_override: Optional dict with real-time breadth
                internals (keys: ``tick``, ``add``, ``trin``) supplied by S07.
                When provided, these values are incorporated into the
                market-internals component score alongside the existing
                term-structure and breadth signals.

        Returns:
            BlackSwanResult with score (1-5) and component breakdown
        """
        start_time = time.time()

        try:
            # Collect market data
            market_data = self._collect_market_data()

            if not market_data:
                self.logger.error("Failed to collect market data")
                return self._create_error_result()

            # Calculate component scores
            component_scores = {}

            # 1. Volatility Component
            vol_score = self._calculate_volatility_score(market_data)
            component_scores["volatility"] = vol_score

            # 2. Credit Stress Component
            credit_score = self._calculate_credit_score(market_data)
            component_scores["credit_stress"] = credit_score

            # 3. Liquidity Component
            liquidity_score = self._calculate_liquidity_score(market_data)
            component_scores["liquidity"] = liquidity_score

            # 4. Market Internals Component
            internals_score = self._calculate_internals_score(market_data, market_internals_override)
            component_scores["market_internals"] = internals_score

            # Calculate weighted overall score
            overall_score = sum(score.weighted_score for score in component_scores.values())

            # Apply momentum adjustments
            overall_score = self._apply_momentum_adjustments(overall_score)

            # Ensure score is in valid range
            overall_score = max(1.0, min(5.0, overall_score))

            # Determine status
            status = self._determine_status(overall_score)

            # Assess data quality
            data_quality = self._assess_data_quality(market_data)

            # Store in history
            self.score_history.append((datetime.now(timezone.utc), overall_score))
            if len(self.score_history) > 100:
                self.score_history.pop(0)

            # Calculate execution time
            calc_time = (time.time() - start_time) * 1000

            result = BlackSwanResult(
                timestamp=datetime.now(timezone.utc),
                overall_score=round(overall_score, 2),
                status=status,
                component_scores=component_scores,
                data_quality=data_quality,
                calculation_time_ms=calc_time,
                raw_data=market_data if self.config.get("include_raw_data") else None,
            )

            _swan_key = (round(result.overall_score, 2), status.value)
            self._last_swan_key = _swan_key
            self.logger.debug(f"SWAN Score calculated: {result.overall_score:.2f} ({status.value})")
            return result

        except Exception as e:
            self.logger.error("Error calculating SWAN score: %s", e, exc_info=True)
            if self.error_handler:
                self.error_handler.handle_error(e)
            return self._create_error_result()

    def get_current_risk_level(self) -> tuple[float, str]:
        """
        Get current risk level without full calculation.

        Returns:
            Tuple of (score, status)
        """
        if self.score_history:
            last_score = self.score_history[-1][1]
            status = self._determine_status(last_score)
            return last_score, status.value
        return 1.0, "GREEN"

    # ==========================================================================
    # DATA COLLECTION METHODS (from old S06)
    # ==========================================================================
    def _collect_market_data(self) -> dict[str, Any]:
        """Collect all required market data"""
        data = {
            "timestamp": datetime.now(timezone.utc),
            "volatility": {},
            "credit": {},
            "market": {},
            "internals": {},
        }

        # Check cache first
        if self.use_cache and self._is_cache_valid("market_data"):
            return self._cache.get("market_data", {})

        try:
            # Collect volatility data
            for name, symbol in VOLATILITY_SYMBOLS.items():
                value = self._fetch_quote(symbol)
                if value:
                    data["volatility"][name] = value

            # Collect credit data
            for name, symbol in CREDIT_SYMBOLS.items():
                value = self._fetch_quote(symbol)
                if value:
                    data["credit"][name] = value

            # Collect market data
            for name, symbol in MARKET_SYMBOLS.items():
                value = self._fetch_quote(symbol)
                if value:
                    data["market"][name] = value

            # Calculate derived metrics
            if "hyg" in data["credit"] and "lqd" in data["credit"]:
                data["credit"]["spread"] = data["credit"]["hyg"] / data["credit"]["lqd"]

            # Update cache
            if self.use_cache:
                self._update_cache("market_data", data)

            return data

        except Exception as e:
            self.logger.error("Error collecting market data: %s", e, exc_info=True)
            return data

    def _fetch_quote(self, symbol: str) -> float | None:
        """Fetch single quote from data source"""
        # Try C29 first (mid-price from bid/ask)
        if _C29_AVAILABLE:
            try:
                client = _get_c29_provider()
                quote = client.get_quote(symbol)
                if quote.bid and quote.ask:
                    return (quote.bid + quote.ask) / 2
                if quote.bid:
                    return quote.bid
                if quote.ask:
                    return quote.ask
            except Exception:
                pass
        # Fall back to yfinance
        try:
            if YFINANCE_AVAILABLE:
                self.logger.debug("C29 quote unavailable for %s — using yfinance fallback", symbol)
                ticker = yf.Ticker(symbol)
                info = ticker.info
                return info.get("regularMarketPrice") or info.get("price")
            else:
                # Fallback to simulation
                return self._simulate_quote(symbol)
        except Exception:
            return None

    def _simulate_quote(self, symbol: str) -> float:
        """Simulate quote for testing"""
        base_prices = {
            "^VIX": 15.0 + np.random.normal(0, 2),
            "SPY": 450.0 + np.random.normal(0, 5),
            "HYG": 85.0 + np.random.normal(0, 1),
            "LQD": 120.0 + np.random.normal(0, 1),
            "DX-Y.NYB": 102.0 + np.random.normal(0, 1),
        }
        return base_prices.get(symbol, 100.0 + np.random.normal(0, 2))

    # ==========================================================================
    # CALCULATION METHODS (new logic for S07)
    # ==========================================================================
    def _calculate_volatility_score(self, data: dict) -> ComponentScore:
        """Calculate volatility component score"""
        vix = data.get("volatility", {}).get("vix", 15)

        # Score based on VIX levels
        if vix < 12:
            raw_score = 1.0
            description = "Very low volatility"
        elif vix < 20:
            raw_score = 1.5 + (vix - 12) / 8 * 0.5
            description = "Normal volatility"
        elif vix < 30:
            raw_score = 2.0 + (vix - 20) / 10 * 1.0
            description = "Elevated volatility"
        elif vix < 40:
            raw_score = 3.0 + (vix - 30) / 10 * 1.0
            description = "High volatility"
        else:
            raw_score = 4.0 + min((vix - 40) / 20, 1.0)
            description = "Extreme volatility"

        weight = self.weights["volatility"]

        return ComponentScore(
            name="volatility",
            raw_score=raw_score,
            weight=weight,
            weighted_score=raw_score * weight,
            description=description,
            details={"vix": vix},
        )

    def _calculate_credit_score(self, data: dict) -> ComponentScore:
        """Calculate credit stress component score"""
        spread = data.get("credit", {}).get("spread", 0.71)

        # Score based on credit spread
        if spread > 0.73:
            raw_score = 1.0 + (spread - 0.73) * 10
            description = "Credit stress detected"
        elif spread < 0.69:
            raw_score = 1.0 + (0.69 - spread) * 5
            description = "Credit conditions tight"
        else:
            raw_score = 1.0
            description = "Normal credit conditions"

        raw_score = min(5.0, max(1.0, raw_score))
        weight = self.weights["credit_stress"]

        return ComponentScore(
            name="credit_stress",
            raw_score=raw_score,
            weight=weight,
            weighted_score=raw_score * weight,
            description=description,
            details={"spread": spread},
        )

    def _calculate_liquidity_score(self, data: dict) -> ComponentScore:
        """Calculate liquidity component score"""
        dxy = data.get("market", {}).get("dxy", 102)

        # Score based on dollar strength
        if dxy > 110:
            raw_score = 3.0 + (dxy - 110) / 10
            description = "Dollar squeeze - liquidity stress"
        elif dxy > 105:
            raw_score = 2.0 + (dxy - 105) / 5
            description = "Strong dollar - moderate stress"
        else:
            raw_score = 1.5
            description = "Normal liquidity conditions"

        raw_score = min(5.0, max(1.0, raw_score))
        weight = self.weights["liquidity"]

        return ComponentScore(
            name="liquidity",
            raw_score=raw_score,
            weight=weight,
            weighted_score=raw_score * weight,
            description=description,
            details={"dxy": dxy},
        )

    def _calculate_internals_score(self, data: dict, market_internals_override: dict | None = None) -> ComponentScore:  # noqa: E501
        """Calculate market internals component score.

        Uses VIX term-structure (VIX9D / VIX ratio) as a proxy for near-term
        stress relative to 30-day implied vol, combined with cross-asset breadth
        (QQQ and IWM relative weakness vs SPY) as a broad market-health indicator.
        """
        vol_data = data.get("volatility", {})
        market_data = data.get("market", {})

        details: dict = {}
        scores: list[float] = []

        # ── Term structure: VIX9D vs VIX ──────────────────────────────────────
        # Backwardation (VIX9D > VIX) means near-term fear exceeds medium-term
        # → stress signal. Contango (VIX9D < VIX) is the normal calm state.
        vix = vol_data.get("vix", 0.0)
        vix9d = vol_data.get("vix9d", 0.0)
        if vix and vix9d:
            ratio = vix9d / vix  # > 1.0 → backwardation (stress)
            if ratio > 1.10:
                ts_score = 4.0 + min((ratio - 1.10) / 0.10, 1.0)
                ts_desc = "Severe term-structure backwardation"
            elif ratio > 1.02:
                ts_score = 2.5 + (ratio - 1.02) / 0.08 * 1.5
                ts_desc = "Mild backwardation — elevated near-term fear"
            elif ratio > 0.95:
                ts_score = 1.5
                ts_desc = "Flat/normal term structure"
            else:
                ts_score = 1.0
                ts_desc = "Deep contango — complacent conditions"
            scores.append(ts_score)
            details["vix9d_vix_ratio"] = round(ratio, 3)
            details["term_structure"] = ts_desc

        # ── Cross-asset breadth: QQQ and IWM vs SPY ───────────────────────────
        # If both QQQ and IWM are significantly below SPY (size-cap divergence),
        # it indicates narrow market leadership — a classic internal weakness signal.
        spy = market_data.get("spy", 0.0)
        qqq = market_data.get("qqq", 0.0)
        iwm = market_data.get("iwm", 0.0)
        if spy and qqq and iwm:
            # Normalise to price ratios relative to their typical multiples
            # (QQQ ~0.98×SPY, IWM ~0.40×SPY at typical market levels)
            qqq_norm = qqq / (spy * 0.98) if spy else 1.0
            iwm_norm = iwm / (spy * 0.40) if spy else 1.0
            breadth = (qqq_norm + iwm_norm) / 2.0  # 1.0 = in-line with SPY
            if breadth < 0.93:
                breadth_score = 4.0 + min((0.93 - breadth) / 0.05, 1.0)
                breadth_desc = "Severe breadth divergence"
            elif breadth < 0.97:
                breadth_score = 2.5 + (0.97 - breadth) / 0.04 * 1.5
                breadth_desc = "Narrowing market — breadth weakening"
            else:
                breadth_score = 1.5
                breadth_desc = "Broad market participation"
            scores.append(breadth_score)
            details["breadth_ratio"] = round(breadth, 3)
            details["breadth"] = breadth_desc

        # ── Live breadth internals: TICK, ADD, TRIN (supplied by S07) ────────
        # Real-time NYSE breadth indicators are injected by S07 when the
        # TradingView client is active.  S03 cannot fetch these directly.
        if market_internals_override:
            _sub: list[float] = []
            _int_details: dict = {}
            _tick = market_internals_override.get("tick")
            _add  = market_internals_override.get("add")
            _trin = market_internals_override.get("trin")
            if _tick is not None:
                # Below −1000: panic selling → 4.5
                # −1000 to −600: broad selling → 2.5–4.5 linear
                # Above +800: strong breadth thrust → 1.0 (bullish)
                # Otherwise neutral → 1.5
                if _tick <= -1000:
                    _ts = 4.5
                elif _tick <= -600:
                    _ts = 2.5 + (abs(_tick) - 600) / 400.0 * 2.0
                elif _tick >= 800:
                    _ts = 1.0
                else:
                    _ts = 1.5
                _sub.append(_ts)
                _int_details["tick"] = round(_tick, 0)
            if _add is not None:
                if _add <= -2000:
                    _as = 4.5
                elif _add <= -1000:
                    _as = 2.5 + (abs(_add) - 1000) / 1000.0 * 2.0
                elif _add >= 1000:
                    _as = 1.0
                else:
                    _as = 1.5
                _sub.append(_as)
                _int_details["add"] = round(_add, 0)
            if _trin is not None:
                # Above 3.0: extreme selling volume → 4.5
                # 2.0–3.0:  strong selling → 3.0–4.5
                # Below 0.5: extreme buying rush (blow-off risk) → 2.0
                # 0.5–2.0:  normal → 1.0 + trin (1.5–3.0 linear)
                if _trin >= 3.0:
                    _tr = 4.5
                elif _trin >= 2.0:
                    _tr = 3.0 + (_trin - 2.0)
                elif _trin <= 0.5:
                    _tr = 2.0
                else:
                    _tr = 1.0 + _trin
                _sub.append(_tr)
                _int_details["trin"] = round(_trin, 2)
            if _sub:
                _live_score = float(np.mean(_sub))
                scores.append(max(1.0, min(5.0, _live_score)))
                details["live_internals"] = _int_details

        if scores:
            raw_score = float(np.mean(scores))
        else:
            raw_score = 1.5
        raw_score = min(5.0, max(1.0, raw_score))

        # Build human-readable description from the dominant signal
        if scores:
            ts_part = details.get("term_structure", "")
            br_part = details.get("breadth", "")
            live_part = (
                "Internals: " + ", ".join(f"{k}={v}" for k, v in details["live_internals"].items())
                if "live_internals" in details
                else ""
            )
            description = "; ".join(filter(None, [ts_part, br_part, live_part]))
        else:
            description = "Market internals: insufficient data"

        details["spy"] = spy
        weight = self.weights["market_internals"]

        return ComponentScore(
            name="market_internals",
            raw_score=raw_score,
            weight=weight,
            weighted_score=raw_score * weight,
            description=description,
            details=details,
        )

    def _apply_momentum_adjustments(self, score: float) -> float:
        """Apply momentum-based adjustments to score"""
        if len(self.score_history) < 3:
            return score

        # Check for rapid deterioration
        recent_scores = [s for t, s in self.score_history[-5:]]
        if len(recent_scores) >= 3:
            trend = np.polyfit(range(len(recent_scores)), recent_scores, 1)[0]
            if trend > 0.2:  # Rapid increase in risk
                score += 0.2

        return score

    def _determine_status(self, score: float) -> RiskStatus:
        """Determine risk status from score"""
        if score <= GREEN_MAX:
            return RiskStatus.GREEN
        elif score <= YELLOW_MAX:
            return RiskStatus.YELLOW
        else:
            return RiskStatus.RED

    def _assess_data_quality(self, data: dict) -> DataQuality:
        """Assess quality of collected data"""
        total_expected = len(VOLATILITY_SYMBOLS) + len(CREDIT_SYMBOLS) + len(MARKET_SYMBOLS)
        total_collected = (
            len(data.get("volatility", {}))
            + len(data.get("credit", {}))
            + len(data.get("market", {}))
        )

        ratio = total_collected / total_expected if total_expected > 0 else 0

        if ratio > 0.8:
            return DataQuality.GOOD
        elif ratio > 0.5:
            return DataQuality.PARTIAL
        else:
            return DataQuality.POOR

    # ==========================================================================
    # CACHE MANAGEMENT
    # ==========================================================================
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self._cache_timestamps:
            return False
        age = (datetime.now(timezone.utc) - self._cache_timestamps[key]).total_seconds()
        return age < self.cache_ttl

    def _update_cache(self, key: str, data: Any):
        """Update cache with new data"""
        self._cache[key] = data
        self._cache_timestamps[key] = datetime.now(timezone.utc)

    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self._cache_timestamps.clear()

    # ==========================================================================
    # ERROR HANDLING
    # ==========================================================================
    def _create_error_result(self) -> BlackSwanResult:
        """Create error result when calculation fails"""
        return BlackSwanResult(
            timestamp=datetime.now(timezone.utc),
            overall_score=1.0,
            status=RiskStatus.GREEN,
            component_scores={},
            data_quality=DataQuality.POOR,
            calculation_time_ms=0,
            raw_data=None,
        )


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_indicator_instance = None
_indicator_instance_lock = threading.Lock()


def get_black_swan_indicator() -> BlackSwanIndicator:
    """Get singleton instance of Black Swan Indicator"""
    global _indicator_instance
    if _indicator_instance is None:
        with _indicator_instance_lock:
            if _indicator_instance is None:
                _indicator_instance = BlackSwanIndicator()
    return _indicator_instance


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    # Create indicator
    indicator = BlackSwanIndicator({"include_raw_data": True})

    # Calculate score
    result = indicator.calculate_swan_score()

    print(f"SWAN Score : {result.overall_score:.2f}")  # noqa: T201
    print(f"Status     : {result.status.value}")  # noqa: T201
    print(f"Data Quality: {result.data_quality.value}")  # noqa: T201
    print(f"Calc Time  : {result.calculation_time_ms:.1f} ms")  # noqa: T201
    print()  # noqa: T201
    print("Component Breakdown:")  # noqa: T201
    for name, score in result.component_scores.items():
        print(f"  {name:<20} raw={score.raw_score:.2f}  weighted={score.weighted_score:.3f}  — {score.description}")  # noqa: E501, T201

