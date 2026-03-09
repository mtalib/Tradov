#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderS03_BlackSwanIndicator.py
Group: S (Signals)
Purpose: Black Swan risk indicator with integrated data collection and calculation
Author: Mohamed Talib
Date Created: 2025-01-31
Last Updated: 2025-01-31 Time: 12:00:00

Description:
    Merged module combining Black Swan data collection and risk calculation.
    Provides comprehensive tail risk assessment using volatility metrics,
    credit spreads, liquidity indicators, and market internals.
    Returns a risk score on a 1-5 scale where 1=minimal risk, 5=extreme risk.
"""

import logging
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
from dataclasses import dataclass, field
from datetime import datetime
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

        self.logger.info("Black Swan Indicator initialized")

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def calculate_swan_score(self) -> BlackSwanResult:
        """
        Calculate the complete Black Swan risk score.

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
            internals_score = self._calculate_internals_score(market_data)
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
            self.score_history.append((datetime.now(), overall_score))
            if len(self.score_history) > 100:
                self.score_history.pop(0)

            # Calculate execution time
            calc_time = (time.time() - start_time) * 1000

            result = BlackSwanResult(
                timestamp=datetime.now(),
                overall_score=round(overall_score, 2),
                status=status,
                component_scores=component_scores,
                data_quality=data_quality,
                calculation_time_ms=calc_time,
                raw_data=market_data if self.config.get("include_raw_data") else None,
            )

            self.logger.info(f"SWAN Score calculated: {result.overall_score:.2f} ({status.value})")
            return result

        except Exception as e:
            self.logger.error(f"Error calculating SWAN score: {e}")
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
            "timestamp": datetime.now(),
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
            self.logger.error(f"Error collecting market data: {e}")
            return data

    def _fetch_quote(self, symbol: str) -> float | None:
        """Fetch single quote from data source"""
        try:
            if YFINANCE_AVAILABLE:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                return info.get("regularMarketPrice") or info.get("price")
            else:
                # Fallback to simulation
                return self._simulate_quote(symbol)
        except BaseException:
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

    def _calculate_internals_score(self, data: dict) -> ComponentScore:
        """Calculate market internals component score"""
        # Simplified for now - would use TICK, TRIN, ADD, etc.
        spy = data.get("market", {}).get("spy", 450)

        # Calculate based on SPY momentum (simplified)
        raw_score = 1.5  # Default neutral
        description = "Market internals neutral"

        weight = self.weights["market_internals"]

        return ComponentScore(
            name="market_internals",
            raw_score=raw_score,
            weight=weight,
            weighted_score=raw_score * weight,
            description=description,
            details={"spy": spy},
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
        age = (datetime.now() - self._cache_timestamps[key]).total_seconds()
        return age < self.cache_ttl

    def _update_cache(self, key: str, data: Any):
        """Update cache with new data"""
        self._cache[key] = data
        self._cache_timestamps[key] = datetime.now()

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
            timestamp=datetime.now(),
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


def get_black_swan_indicator() -> BlackSwanIndicator:
    """Get singleton instance of Black Swan Indicator"""
    global _indicator_instance
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


    for _name, _score in result.component_scores.items():
        pass

