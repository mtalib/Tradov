#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderN_OptionsAnalytics
Module: SpyderN11_OptionsGreeksFlow.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, auto
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderA_Core.SpyderA05_EventManager import (Event, EventType,

                                                 get_event_manager)
from Spyder.SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from Spyder.SpyderS_Signals.SpyderS05_GEXDEXCalculator import GammaExposureCalculator
# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Greeks Flow Parameters
MIN_GREEK_CHANGE = 0.01  # Minimum Greek change to track
GAMMA_FLIP_TOLERANCE = 5.0  # Price tolerance for gamma flip
VANNA_THRESHOLD = 0.5  # Significant vanna level
CHARM_DECAY_HOURS = [1, 4, 24]  # Charm decay timeframes

# Flow Detection Thresholds
LARGE_GAMMA_FLOW = 1_000_000  # $1M gamma exposure
LARGE_VANNA_FLOW = 500_000  # $500K vanna exposure
SIGNIFICANT_CHARM = 100_000  # $100K charm decay

# Expiry Effects
EXPIRY_VANNA_MULTIPLIER = 2.0  # Vanna effect multiplier near expiry
EXPIRY_DAYS_THRESHOLD = 2  # Days to expiry for enhanced effects

# Dealer Positioning
DEALER_LONG_GAMMA_THRESHOLD = 0.7  # 70% probability dealer is long gamma
DEALER_SHORT_GAMMA_THRESHOLD = 0.3  # 30% probability dealer is long gamma

# ==============================================================================
# ENUMS
# ==============================================================================


class GreekFlowType(Enum):
    """Types of Greek-based flows"""

    GAMMA_HEDGING = auto()
    VANNA_FLOW = auto()
    CHARM_DECAY = auto()
    VOMMA_FLOW = auto()
    SPEED_HEDGING = auto()


class DealerPositioning(Enum):
    """Dealer gamma positioning"""

    LONG_GAMMA = "LONG_GAMMA"
    SHORT_GAMMA = "SHORT_GAMMA"
    NEUTRAL_GAMMA = "NEUTRAL_GAMMA"
    FLIPPING = "FLIPPING"


class FlowDirection(Enum):
    """Greek flow direction"""

    BUYING_PRESSURE = "BUYING"
    SELLING_PRESSURE = "SELLING"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class GreekFlow:
    """Greek flow data structure"""

    timestamp: datetime
    flow_type: GreekFlowType
    strike: float
    expiry: date
    greek_value: float
    flow_size: float  # Dollar amount
    direction: FlowDirection
    underlying_price: float


@dataclass
class GammaFlow:
    """Gamma-specific flow analysis"""

    timestamp: datetime
    net_gamma: float
    gamma_by_strike: dict[float, float]
    flip_point: float
    dealer_position: DealerPositioning
    expected_hedging: float  # Expected dealer hedging flow
    confidence: float


@dataclass
class VannaFlow:
    """Vanna flow analysis"""

    timestamp: datetime
    net_vanna: float
    vanna_by_strike: dict[float, float]
    iv_change: float
    expected_flow: float
    expiry_enhanced: bool  # True if near expiry


@dataclass
class CharmFlow:
    """Charm (theta-delta) flow analysis"""

    timestamp: datetime
    net_charm: float
    charm_by_strike: dict[float, float]
    decay_schedule: dict[int, float]  # Hours -> expected decay
    overnight_flow: float


@dataclass
class GreeksFlowProfile:
    """Comprehensive Greeks flow profile"""

    timestamp: datetime
    gamma_flow: GammaFlow
    vanna_flow: VannaFlow
    charm_flow: CharmFlow
    total_expected_flow: float
    flow_direction: FlowDirection
    key_levels: list[float]  # Important price levels
    risk_assessment: dict[str, Any]


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class OptionsGreeksFlowAnalyzer:
    """
    Greeks-based options flow analyzer for dealer positioning and hedging.

    This class analyzes options flow through Greeks dynamics, providing insights
    into dealer hedging behavior, vanna flows, charm decay, and predicting
    market movements based on Greeks exposure changes.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance

    Example:
        >>> analyzer = OptionsGreeksFlowAnalyzer()
        >>> profile = analyzer.get_greeks_flow_profile()
        >>> if profile.gamma_flow.dealer_position == DealerPositioning.SHORT_GAMMA:
        >>>     print(f"Dealers short gamma - expect volatility expansion")
    """

    def __init__(self, config: dict | None = None):
        """Initialize Greeks flow analyzer."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()

        # Configuration
        self.config = config or {}

        # Component integration
        self.option_chain_mgr = OptionChainManager()
        self.greeks_calculator = GreeksCalculator()
        self.gex_calculator = GammaExposureCalculator()

        # Greeks tracking
        self.greek_flows: deque = deque(maxlen=10000)
        self.gamma_history: deque = deque(maxlen=1000)
        self.vanna_history: deque = deque(maxlen=1000)
        self.charm_history: deque = deque(maxlen=1000)

        # Real-time tracking
        self.current_greeks: dict[str, dict[str, float]] = {}
        self.previous_greeks: dict[str, dict[str, float]] = {}
        self.strike_gamma_map: dict[float, float] = defaultdict(float)
        self.strike_vanna_map: dict[float, float] = defaultdict(float)

        # Dealer positioning
        self.gamma_flip_history: list[tuple[datetime, float]] = []
        self.current_dealer_position = DealerPositioning.NEUTRAL_GAMMA

        # Threading
        self._lock = threading.Lock()
        self._monitoring_thread: threading.Thread | None = None
        self._running = False

        self.logger.info(f"{self.__class__.__name__} initialized")

    # ==========================================================================
    # PUBLIC METHODS - GREEKS FLOW ANALYSIS
    # ==========================================================================
    def get_greeks_flow_profile(self) -> GreeksFlowProfile:
        """
        Get comprehensive Greeks flow analysis.

        Returns:
            GreeksFlowProfile with current analysis
        """
        # Analyze each Greek component
        gamma_flow = self.analyze_gamma_flows()
        vanna_flow = self.analyze_vanna_flows()
        charm_flow = self.analyze_charm_flows()

        # Calculate total expected flow
        total_flow = (
            gamma_flow.expected_hedging + vanna_flow.expected_flow + charm_flow.overnight_flow
        )

        # Determine overall flow direction
        if total_flow > LARGE_GAMMA_FLOW:
            direction = FlowDirection.BUYING_PRESSURE
        elif total_flow < -LARGE_GAMMA_FLOW:
            direction = FlowDirection.SELLING_PRESSURE
        else:
            direction = FlowDirection.NEUTRAL

        # Identify key levels
        key_levels = self._identify_key_greek_levels(gamma_flow, vanna_flow)

        # Risk assessment
        risk_assessment = self._assess_greek_risks(gamma_flow, vanna_flow, charm_flow)

        return GreeksFlowProfile(
            timestamp=datetime.now(),
            gamma_flow=gamma_flow,
            vanna_flow=vanna_flow,
            charm_flow=charm_flow,
            total_expected_flow=total_flow,
            flow_direction=direction,
            key_levels=key_levels,
            risk_assessment=risk_assessment,
        )

    def analyze_gamma_flows(self) -> GammaFlow:
        """
        Analyze gamma-based flows and dealer positioning.

        Returns:
            GammaFlow analysis
        """
        # Get current gamma profile
        gex_profile = self.gex_calculator.calculate_gex_profile()

        # Calculate net gamma by strike
        gamma_by_strike = self._calculate_gamma_by_strike()

        # Determine dealer positioning
        dealer_position = self._determine_dealer_position(gex_profile)

        # Calculate expected hedging flow
        spot_price = self._get_spot_price()
        expected_hedging = self._calculate_gamma_hedging_flow(
            gex_profile.current_gex, spot_price, dealer_position
        )

        # Calculate confidence
        confidence = self._calculate_gamma_confidence(gex_profile, dealer_position)

        gamma_flow = GammaFlow(
            timestamp=datetime.now(),
            net_gamma=gex_profile.current_gex,
            gamma_by_strike=gamma_by_strike,
            flip_point=gex_profile.zero_gamma_level,
            dealer_position=dealer_position,
            expected_hedging=expected_hedging,
            confidence=confidence,
        )

        # Store history
        self.gamma_history.append(gamma_flow)

        return gamma_flow

    def analyze_vanna_flows(self) -> VannaFlow:
        """
        Analyze vanna flows (cross-Greek between delta and vega).

        Returns:
            VannaFlow analysis
        """
        # Calculate vanna exposure
        net_vanna, vanna_by_strike = self._calculate_vanna_exposure()

        # Get IV change
        iv_change = self._get_iv_change()

        # Calculate expected vanna flow
        expected_flow = net_vanna * iv_change * 100  # Convert to dollar flow

        # Check for expiry enhancement
        expiry_enhanced = self._check_expiry_vanna_effect()
        if expiry_enhanced:
            expected_flow *= EXPIRY_VANNA_MULTIPLIER

        vanna_flow = VannaFlow(
            timestamp=datetime.now(),
            net_vanna=net_vanna,
            vanna_by_strike=vanna_by_strike,
            iv_change=iv_change,
            expected_flow=expected_flow,
            expiry_enhanced=expiry_enhanced,
        )

        # Store history
        self.vanna_history.append(vanna_flow)

        return vanna_flow

    def analyze_charm_flows(self) -> CharmFlow:
        """
        Analyze charm (theta-delta) decay flows.

        Returns:
            CharmFlow analysis
        """
        # Calculate charm exposure
        net_charm, charm_by_strike = self._calculate_charm_exposure()

        # Calculate decay schedule
        decay_schedule = {}
        for hours in CHARM_DECAY_HOURS:
            decay_schedule[hours] = self._calculate_charm_decay(net_charm, hours)

        # Special calculation for overnight decay
        overnight_flow = self._calculate_overnight_charm_flow(net_charm, charm_by_strike)

        charm_flow = CharmFlow(
            timestamp=datetime.now(),
            net_charm=net_charm,
            charm_by_strike=charm_by_strike,
            decay_schedule=decay_schedule,
            overnight_flow=overnight_flow,
        )

        # Store history
        self.charm_history.append(charm_flow)

        return charm_flow

    # ==========================================================================
    # PUBLIC METHODS - GREEK CHANGE DETECTION
    # ==========================================================================
    def detect_greek_regime_change(self) -> dict[str, Any]:
        """
        Detect significant changes in Greek regimes.

        Returns:
            Regime change analysis
        """
        changes_detected = []

        # Check gamma regime change
        gamma_change = self._detect_gamma_regime_change()
        if gamma_change:
            changes_detected.append(gamma_change)

        # Check vanna regime change
        vanna_change = self._detect_vanna_regime_change()
        if vanna_change:
            changes_detected.append(vanna_change)

        # Check for gamma flip approaching
        flip_proximity = self._check_gamma_flip_proximity()

        return {
            "timestamp": datetime.now(),
            "regime_changes": changes_detected,
            "gamma_flip_proximity": flip_proximity,
            "action_required": len(changes_detected) > 0,
            "recommendations": self._generate_regime_recommendations(
                changes_detected, flip_proximity
            ),
        }

    def get_greek_strike_profile(self, strike: float) -> dict[str, Any]:
        """
        Get detailed Greek profile for a specific strike.

        Args:
            strike: Strike price to analyze

        Returns:
            Greek profile for the strike
        """
        profile = {
            "strike": strike,
            "gamma": 0.0,
            "vanna": 0.0,
            "charm": 0.0,
            "total_greek_exposure": 0.0,
            "dealer_interest": "LOW",
            "key_level": False,
        }

        # Aggregate Greeks for this strike
        with self._lock:
            # Get gamma
            if strike in self.strike_gamma_map:
                profile["gamma"] = self.strike_gamma_map[strike]

            # Get vanna
            if strike in self.strike_vanna_map:
                profile["vanna"] = self.strike_vanna_map[strike]

        # Calculate total exposure
        profile["total_greek_exposure"] = abs(profile["gamma"]) + abs(profile["vanna"])

        # Assess dealer interest
        if abs(profile["gamma"]) > LARGE_GAMMA_FLOW / 10:
            profile["dealer_interest"] = "HIGH"
        elif abs(profile["gamma"]) > LARGE_GAMMA_FLOW / 50:
            profile["dealer_interest"] = "MEDIUM"

        # Check if key level
        profile["key_level"] = self._is_key_greek_level(strike, profile)

        return profile

    # ==========================================================================
    # PUBLIC METHODS - FLOW PREDICTIONS
    # ==========================================================================
    def predict_hedging_flows(self, spot_move: float) -> dict[str, Any]:
        """
        Predict dealer hedging flows for a given spot move.

        Args:
            spot_move: Expected spot price move in points

        Returns:
            Hedging flow predictions
        """
        current_spot = self._get_spot_price()
        new_spot = current_spot + spot_move

        # Calculate gamma hedging
        gamma_flow = self.gamma_history[-1] if self.gamma_history else None
        if gamma_flow:
            gamma_hedging = self._calculate_gamma_hedging_flow(
                gamma_flow.net_gamma, spot_move, gamma_flow.dealer_position
            )
        else:
            gamma_hedging = 0

        # Calculate vanna impact
        vanna_impact = self._calculate_vanna_impact(spot_move)

        # Calculate charm impact
        charm_impact = self._calculate_charm_impact(spot_move)

        # Net hedging flow
        total_hedging = gamma_hedging + vanna_impact + charm_impact

        return {
            "spot_move": spot_move,
            "new_spot": new_spot,
            "gamma_hedging": gamma_hedging,
            "vanna_impact": vanna_impact,
            "charm_impact": charm_impact,
            "total_hedging_flow": total_hedging,
            "flow_direction": "BUY" if total_hedging > 0 else "SELL",
            "magnitude": abs(total_hedging),
            "market_impact": self._estimate_market_impact(total_hedging),
        }

    def get_expiry_greek_analysis(self, expiry: date) -> dict[str, Any]:
        """
        Analyze Greek dynamics for a specific expiry.

        Args:
            expiry: Expiration date

        Returns:
            Expiry-specific Greek analysis
        """
        days_to_expiry = (expiry - date.today()).days

        # Get options for this expiry
        chain = self.option_chain_mgr.get_option_chain("SPY")
        expiry_options = [opt for opt in chain if opt.expiry == expiry]

        # Calculate expiry Greeks
        expiry_gamma = sum(self._calculate_option_gamma(opt) for opt in expiry_options)
        expiry_vanna = sum(self._calculate_option_vanna(opt) for opt in expiry_options)
        expiry_charm = sum(self._calculate_option_charm(opt) for opt in expiry_options)

        # Analyze pin risk
        pin_risk = self._analyze_pin_risk(expiry_options, days_to_expiry)

        # Vanna effects
        vanna_effects = "ENHANCED" if days_to_expiry <= EXPIRY_DAYS_THRESHOLD else "NORMAL"

        return {
            "expiry": expiry,
            "days_to_expiry": days_to_expiry,
            "total_gamma": expiry_gamma,
            "total_vanna": expiry_vanna,
            "total_charm": expiry_charm,
            "pin_risk": pin_risk,
            "vanna_effects": vanna_effects,
            "key_strikes": self._identify_expiry_key_strikes(expiry_options),
            "expected_volatility": self._estimate_expiry_volatility(expiry_gamma, days_to_expiry),
        }

    # ==========================================================================
    # PRIVATE METHODS - GAMMA ANALYSIS
    # ==========================================================================
    def _calculate_gamma_by_strike(self) -> dict[float, float]:
        """Calculate gamma exposure by strike."""
        gamma_by_strike = defaultdict(float)

        chain = self.option_chain_mgr.get_option_chain("SPY")
        for option in chain:
            gamma = self._calculate_option_gamma(option)
            gamma_by_strike[option.strike] += gamma

        return dict(gamma_by_strike)

    def _determine_dealer_position(self, gex_profile) -> DealerPositioning:
        """Determine dealer gamma positioning."""
        spot_price = self._get_spot_price()

        # Check distance to flip point
        distance_to_flip = abs(spot_price - gex_profile.zero_gamma_level)

        if distance_to_flip < GAMMA_FLIP_TOLERANCE:
            return DealerPositioning.FLIPPING
        elif gex_profile.current_gex > 0:
            if gex_profile.current_gex > LARGE_GAMMA_FLOW:
                return DealerPositioning.LONG_GAMMA
            else:
                return DealerPositioning.NEUTRAL_GAMMA
        else:
            if abs(gex_profile.current_gex) > LARGE_GAMMA_FLOW:
                return DealerPositioning.SHORT_GAMMA
            else:
                return DealerPositioning.NEUTRAL_GAMMA

    def _calculate_gamma_hedging_flow(
        self, net_gamma: float, spot_move: float, dealer_position: DealerPositioning
    ) -> float:
        """Calculate expected gamma hedging flow."""
        if dealer_position == DealerPositioning.LONG_GAMMA:
            # Dealers sell on up moves, buy on down moves (dampening)
            return -net_gamma * spot_move
        elif dealer_position == DealerPositioning.SHORT_GAMMA:
            # Dealers buy on up moves, sell on down moves (accelerating)
            return -net_gamma * spot_move
        else:
            return 0

    def _calculate_gamma_confidence(self, gex_profile, dealer_position: DealerPositioning) -> float:
        """Calculate confidence in gamma positioning."""
        confidence_factors = []

        # GEX magnitude
        gex_magnitude = abs(gex_profile.current_gex)
        if gex_magnitude > 2 * LARGE_GAMMA_FLOW:
            confidence_factors.append(0.9)
        elif gex_magnitude > LARGE_GAMMA_FLOW:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.5)

        # Distance from flip
        spot = self._get_spot_price()
        flip_distance = abs(spot - gex_profile.zero_gamma_level) / spot
        if flip_distance > 0.02:  # 2% away
            confidence_factors.append(0.8)
        elif flip_distance > 0.01:  # 1% away
            confidence_factors.append(0.6)
        else:
            confidence_factors.append(0.3)

        # Historical stability
        if len(self.gamma_history) >= 5:
            recent_positions = [g.dealer_position for g in self.gamma_history[-5:]]
            if all(p == dealer_position for p in recent_positions):
                confidence_factors.append(0.8)
            else:
                confidence_factors.append(0.5)

        return np.mean(confidence_factors)

    # ==========================================================================
    # PRIVATE METHODS - VANNA ANALYSIS
    # ==========================================================================
    def _calculate_vanna_exposure(self) -> tuple[float, dict[float, float]]:
        """Calculate vanna exposure."""
        net_vanna = 0.0
        vanna_by_strike = defaultdict(float)

        chain = self.option_chain_mgr.get_option_chain("SPY")
        for option in chain:
            vanna = self._calculate_option_vanna(option)
            net_vanna += vanna
            vanna_by_strike[option.strike] += vanna

        return net_vanna, dict(vanna_by_strike)

    def _calculate_option_vanna(self, option) -> float:
        """Calculate vanna for an option."""
        # Vanna = dDelta/dIV = dVega/dSpot
        # Simplified calculation for demonstration
        spot = self._get_spot_price()

        # ATM options have highest vanna
        moneyness = spot / option.strike
        if 0.95 < moneyness < 1.05:  # Near ATM
            base_vanna = 0.5
        else:
            base_vanna = 0.2

        # Adjust for time to expiry
        days_to_expiry = (option.expiry - date.today()).days
        time_factor = np.sqrt(days_to_expiry / 365)

        # Adjust for open interest
        oi_factor = min(option.open_interest / 1000, 2.0)

        return base_vanna * time_factor * oi_factor * option.contract_size

    def _get_iv_change(self) -> float:
        """Get recent IV change."""
        # In production, this would track actual IV changes
        # For demonstration, returning synthetic value
        return np.random.normal(0, 0.02)  # 2% vol

    def _check_expiry_vanna_effect(self) -> bool:
        """Check if near expiry for enhanced vanna effects."""
        chain = self.option_chain_mgr.get_option_chain("SPY")
        if not chain:
            return False

        # Get nearest expiry
        expiries = sorted(set(opt.expiry for opt in chain))
        if expiries:
            nearest_expiry = expiries[0]
            days_to_expiry = (nearest_expiry - date.today()).days
            return days_to_expiry <= EXPIRY_DAYS_THRESHOLD

        return False

    # ==========================================================================
    # PRIVATE METHODS - CHARM ANALYSIS
    # ==========================================================================
    def _calculate_charm_exposure(self) -> tuple[float, dict[float, float]]:
        """Calculate charm exposure."""
        net_charm = 0.0
        charm_by_strike = defaultdict(float)

        chain = self.option_chain_mgr.get_option_chain("SPY")
        for option in chain:
            charm = self._calculate_option_charm(option)
            net_charm += charm
            charm_by_strike[option.strike] += charm

        return net_charm, dict(charm_by_strike)

    def _calculate_option_charm(self, option) -> float:
        """Calculate charm for an option."""
        # Charm = -dDelta/dTime
        # Highest for ATM options near expiry
        spot = self._get_spot_price()
        moneyness = spot / option.strike

        # ATM check
        if 0.98 < moneyness < 1.02:
            base_charm = 1.0
        else:
            base_charm = 0.3

        # Time decay acceleration
        days_to_expiry = (option.expiry - date.today()).days
        if days_to_expiry <= 5:
            time_factor = 3.0
        elif days_to_expiry <= 10:
            time_factor = 2.0
        else:
            time_factor = 1.0

        # Open interest factor
        oi_factor = min(option.open_interest / 1000, 2.0)

        return base_charm * time_factor * oi_factor * option.contract_size

    def _calculate_charm_decay(self, net_charm: float, hours: int) -> float:
        """Calculate charm decay over specified hours."""
        # Charm accelerates as time passes
        decay_rate = hours / 24  # Fraction of day
        return net_charm * decay_rate * self._get_spot_price()

    def _calculate_overnight_charm_flow(
        self, net_charm: float, charm_by_strike: dict[float, float]
    ) -> float:
        """Calculate expected overnight charm flow."""
        # Overnight represents ~16 hours of decay
        overnight_hours = 16
        base_flow = self._calculate_charm_decay(net_charm, overnight_hours)

        # Adjust for weekend if applicable
        if datetime.now().weekday() == 4:  # Friday
            base_flow *= 3  # Account for weekend decay

        return base_flow

    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _calculate_option_gamma(self, option) -> float:
        """Calculate gamma for an option."""
        try:
            greeks = self.greeks_calculator.calculate_greeks(
                option_type=option.option_type,
                spot=self._get_spot_price(),
                strike=option.strike,
                time_to_expiry=(option.expiry - date.today()).days / 365,
                volatility=option.implied_volatility,
                risk_free_rate=0.05,
                dividend_yield=0.01,
            )

            # Dollar gamma = Gamma * Spot^2 * Contract Size * Open Interest
            dollar_gamma = (
                greeks["gamma"]
                * self._get_spot_price() ** 2
                * option.contract_size
                * option.open_interest
                / 100
            )

            return dollar_gamma

        except Exception as e:
            self.logger.error(f"Error calculating gamma: {e}")
            return 0.0

    def _get_spot_price(self) -> float:
        """Get current spot price."""
        # In production, this would get real-time price
        return 450.0  # Placeholder

    def _identify_key_greek_levels(
        self, gamma_flow: GammaFlow, vanna_flow: VannaFlow
    ) -> list[float]:
        """Identify key price levels based on Greeks."""
        key_levels = []

        # Gamma flip point
        if gamma_flow.flip_point > 0:
            key_levels.append(gamma_flow.flip_point)

        # Major gamma strikes
        sorted_gamma = sorted(
            gamma_flow.gamma_by_strike.items(), key=lambda x: abs(x[1]), reverse=True
        )
        for strike, gamma in sorted_gamma[:3]:
            if abs(gamma) > LARGE_GAMMA_FLOW / 10:
                key_levels.append(strike)

        # Major vanna strikes
        sorted_vanna = sorted(
            vanna_flow.vanna_by_strike.items(), key=lambda x: abs(x[1]), reverse=True
        )
        for strike, vanna in sorted_vanna[:2]:
            if abs(vanna) > LARGE_VANNA_FLOW / 10:
                key_levels.append(strike)

        # Remove duplicates and sort
        return sorted(list(set(key_levels)))

    def _assess_greek_risks(
        self, gamma_flow: GammaFlow, vanna_flow: VannaFlow, charm_flow: CharmFlow
    ) -> dict[str, Any]:
        """Assess risks based on Greek profiles."""
        risks = {
            "gamma_risk": "LOW",
            "vanna_risk": "LOW",
            "charm_risk": "LOW",
            "overall_risk": "LOW",
            "risk_factors": [],
        }

        # Gamma risk
        if gamma_flow.dealer_position == DealerPositioning.SHORT_GAMMA:
            risks["gamma_risk"] = "HIGH"
            risks["risk_factors"].append("Dealers short gamma - volatility expansion risk")
        elif gamma_flow.dealer_position == DealerPositioning.FLIPPING:
            risks["gamma_risk"] = "MEDIUM"
            risks["risk_factors"].append("Near gamma flip point - unstable hedging flows")

        # Vanna risk
        if abs(vanna_flow.net_vanna) > LARGE_VANNA_FLOW and vanna_flow.expiry_enhanced:
            risks["vanna_risk"] = "HIGH"
            risks["risk_factors"].append("High vanna near expiry - vol/spot correlation risk")
        elif abs(vanna_flow.net_vanna) > LARGE_VANNA_FLOW / 2:
            risks["vanna_risk"] = "MEDIUM"

        # Charm risk
        if abs(charm_flow.overnight_flow) > SIGNIFICANT_CHARM:
            risks["charm_risk"] = "MEDIUM"
            risks["risk_factors"].append("Significant overnight charm decay expected")

        # Overall risk
        risk_scores = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

        total_score = (
            risk_scores[risks["gamma_risk"]]
            + risk_scores[risks["vanna_risk"]]
            + risk_scores[risks["charm_risk"]]
        )

        if total_score >= 7:
            risks["overall_risk"] = "HIGH"
        elif total_score >= 5:
            risks["overall_risk"] = "MEDIUM"

        return risks

    def _detect_gamma_regime_change(self) -> dict[str, Any] | None:
        """Detect gamma regime changes."""
        if len(self.gamma_history) < 2:
            return None

        current = self.gamma_history[-1]
        previous = self.gamma_history[-2]

        if current.dealer_position != previous.dealer_position:
            return {
                "type": "GAMMA_REGIME_CHANGE",
                "from": previous.dealer_position.value,
                "to": current.dealer_position.value,
                "timestamp": current.timestamp,
                "significance": "HIGH",
            }

        return None

    def _detect_vanna_regime_change(self) -> dict[str, Any] | None:
        """Detect vanna regime changes."""
        if len(self.vanna_history) < 5:
            return None

        recent_vanna = [v.net_vanna for v in self.vanna_history[-5:]]
        vanna_change = recent_vanna[-1] - np.mean(recent_vanna[:-1])

        if abs(vanna_change) > LARGE_VANNA_FLOW / 2:
            return {
                "type": "VANNA_SPIKE",
                "magnitude": vanna_change,
                "timestamp": self.vanna_history[-1].timestamp,
                "significance": "MEDIUM",
            }

        return None

    def _check_gamma_flip_proximity(self) -> dict[str, Any]:
        """Check proximity to gamma flip point."""
        if not self.gamma_history:
            return {"near_flip": False}

        current_gamma = self.gamma_history[-1]
        spot = self._get_spot_price()
        distance = abs(spot - current_gamma.flip_point)
        distance_pct = distance / spot

        return {
            "near_flip": distance < GAMMA_FLIP_TOLERANCE,
            "flip_point": current_gamma.flip_point,
            "distance": distance,
            "distance_pct": distance_pct,
            "direction": "ABOVE" if spot > current_gamma.flip_point else "BELOW",
        }

    def _generate_regime_recommendations(
        self, changes: list[dict], flip_proximity: dict
    ) -> list[str]:
        """Generate recommendations based on regime changes."""
        recommendations = []

        for change in changes:
            if change["type"] == "GAMMA_REGIME_CHANGE":
                if change["to"] == "SHORT_GAMMA":
                    recommendations.append("Dealers now short gamma - expect increased volatility")
                    recommendations.append("Consider long volatility strategies")
                elif change["to"] == "LONG_GAMMA":
                    recommendations.append("Dealers now long gamma - expect volatility dampening")
                    recommendations.append("Consider short volatility strategies")

            elif change["type"] == "VANNA_SPIKE":
                if change["magnitude"] > 0:
                    recommendations.append("Positive vanna spike - bullish vol/spot correlation")
                else:
                    recommendations.append("Negative vanna spike - bearish vol/spot correlation")

        if flip_proximity["near_flip"]:
            recommendations.append(f"Near gamma flip at {flip_proximity['flip_point']:.2f}")
            recommendations.append("Expect unstable price action around this level")

        return recommendations

    def _calculate_vanna_impact(self, spot_move: float) -> float:
        """Calculate vanna impact from spot move."""
        if not self.vanna_history:
            return 0.0

        current_vanna = self.vanna_history[-1]

        # Vanna creates flow when spot and vol move together
        # Assume vol moves 0.1 point for each 1 point spot move
        vol_spot_correlation = 0.1
        implied_vol_change = spot_move * vol_spot_correlation

        return current_vanna.net_vanna * implied_vol_change * 100

    def _calculate_charm_impact(self, spot_move: float) -> float:
        """Calculate charm impact from spot move."""
        if not self.charm_history:
            return 0.0

        current_charm = self.charm_history[-1]

        # Charm impact is generally smaller than gamma
        # But increases near expiry
        return current_charm.net_charm * spot_move * 0.1

    def _estimate_market_impact(self, flow: float) -> str:
        """Estimate market impact from flow size."""
        abs_flow = abs(flow)

        if abs_flow > 10 * LARGE_GAMMA_FLOW:
            return "EXTREME"
        elif abs_flow > 5 * LARGE_GAMMA_FLOW:
            return "HIGH"
        elif abs_flow > LARGE_GAMMA_FLOW:
            return "MODERATE"
        elif abs_flow > LARGE_GAMMA_FLOW / 2:
            return "LOW"
        else:
            return "MINIMAL"

    def _analyze_pin_risk(self, options: list, days_to_expiry: int) -> dict[str, Any]:
        """Analyze pinning risk for expiry."""
        if days_to_expiry > 2:
            return {"risk": "LOW", "pin_strikes": []}

        # Find strikes with high open interest
        strike_oi = defaultdict(int)
        for opt in options:
            strike_oi[opt.strike] += opt.open_interest

        # Find potential pin strikes
        sorted_strikes = sorted(strike_oi.items(), key=lambda x: x[1], reverse=True)
        pin_strikes = [strike for strike, oi in sorted_strikes[:3] if oi > 10000]

        if pin_strikes:
            return {
                "risk": "HIGH" if days_to_expiry == 0 else "MEDIUM",
                "pin_strikes": pin_strikes,
                "primary_pin": pin_strikes[0] if pin_strikes else None,
            }
        else:
            return {"risk": "LOW", "pin_strikes": []}

    def _identify_expiry_key_strikes(self, options: list) -> list[float]:
        """Identify key strikes for an expiry."""
        strike_importance = defaultdict(float)

        for opt in options:
            # Weight by open interest and gamma
            gamma = self._calculate_option_gamma(opt)
            importance = opt.open_interest * abs(gamma)
            strike_importance[opt.strike] += importance

        # Get top strikes
        sorted_strikes = sorted(strike_importance.items(), key=lambda x: x[1], reverse=True)

        return [strike for strike, _ in sorted_strikes[:5]]

    def _estimate_expiry_volatility(self, gamma: float, days: int) -> str:
        """Estimate volatility impact from expiry gamma."""
        if days > 5:
            return "NORMAL"

        gamma_per_day = abs(gamma) / max(days, 1)

        if gamma_per_day > LARGE_GAMMA_FLOW:
            return "HIGH"
        elif gamma_per_day > LARGE_GAMMA_FLOW / 2:
            return "ELEVATED"
        else:
            return "NORMAL"

    def _is_key_greek_level(self, strike: float, profile: dict[str, Any]) -> bool:
        """Check if strike is a key Greek level."""
        # High gamma strikes are key levels
        if abs(profile["gamma"]) > LARGE_GAMMA_FLOW / 10:
            return True

        # High vanna strikes near expiry
        if abs(profile["vanna"]) > LARGE_VANNA_FLOW / 10:
            chain = self.option_chain_mgr.get_option_chain("SPY")
            expiries = sorted(set(opt.expiry for opt in chain if opt.strike == strike))
            if expiries:
                days_to_expiry = (expiries[0] - date.today()).days
                if days_to_expiry <= EXPIRY_DAYS_THRESHOLD:
                    return True

        return False

    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def start_monitoring(self) -> None:
        """Start Greek flow monitoring."""
        if self._running:
            self.logger.warning("Greek flow monitoring already running")
            return

        self._running = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop, name="GreekFlowMonitor", daemon=True
        )
        self._monitoring_thread.start()
        self.logger.info("Greek flow monitoring started")

    def stop_monitoring(self) -> None:
        """Stop Greek flow monitoring."""
        self._running = False

        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)

        self.logger.info("Greek flow monitoring stopped")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Update Greek flows
                profile = self.get_greeks_flow_profile()

                # Check for regime changes
                regime_changes = self.detect_greek_regime_change()
                if regime_changes["action_required"]:
                    self.logger.warning(f"Greek regime change detected: {regime_changes}")

                # Emit significant flows
                if abs(profile.total_expected_flow) > LARGE_GAMMA_FLOW:
                    self._emit_greek_flow_event(profile)

                time.sleep(30)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error(f"Error in Greek flow monitoring: {e}")

    def _emit_greek_flow_event(self, profile: GreeksFlowProfile) -> None:
        """Emit event for significant Greek flow."""
        event_data = {
            "type": "greek_flow",
            "timestamp": profile.timestamp,
            "total_flow": profile.total_expected_flow,
            "flow_direction": profile.flow_direction.value,
            "gamma_position": profile.gamma_flow.dealer_position.value,
            "key_levels": profile.key_levels,
            "risk_assessment": profile.risk_assessment,
        }

        self.event_manager.emit(Event(EventType.MARKET_DATA, event_data))

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_monitoring()
        self.logger.info("Greek flow analyzer cleanup completed")


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_greeks_flow_analyzer(config: dict | None = None) -> OptionsGreeksFlowAnalyzer:
    """
    Create and return an OptionsGreeksFlowAnalyzer instance.

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured OptionsGreeksFlowAnalyzer instance
    """
    return OptionsGreeksFlowAnalyzer(config)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    analyzer = create_greeks_flow_analyzer()

    try:
        analyzer.start_monitoring()

        # Get Greeks flow profile
        profile = analyzer.get_greeks_flow_profile()

        # Gamma analysis

        # Vanna analysis

        # Charm analysis

        # Key levels
        for _level in profile.key_levels:
            pass

        # Risk assessment
        for _factor in profile.risk_assessment["risk_factors"]:
            pass

        # Test hedging flow prediction
        for move in [-5, -2, 0, 2, 5]:
            prediction = analyzer.predict_hedging_flows(move)

        time.sleep(5)  # thread-safe: time.sleep() intentional

    finally:
        analyzer.cleanup()
