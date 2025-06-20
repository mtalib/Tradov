#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderO01_GreekLimitsManager.py
Group: O (Professional Risk Controls)
Purpose: Real-time Greek limits monitoring and enforcement

Description:
This module manages portfolio Greeks within institutional limits.
    It monitors delta, gamma, vega, and theta in real-time with 5-second
    intervals, provides automatic rebalancing recommendations, and implements
    VIX-based dynamic adjustments following professional standards.

Author: Mohamed Talib
Date: 2025-06-13
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, deque
import json
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import asyncio
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import AlertLevel
from SpyderN_OptionsAnalytics.SpyderN07_OPRAGreeksHandler import OPRAGreeksHandler, PortfolioGreeks
from SpyderE_Risk.SpyderE01_RiskManager import RiskManager
from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
from SpyderJ_Alerts.SpyderJ01_AlertManager import AlertManager

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
MAX_PORTFOLIO_DELTA = 50.0          # ±50 delta per $1M (institutional standard)
MAX_PORTFOLIO_GAMMA = 50.0          # ±50 gamma per $1M 
MAX_PORTFOLIO_VEGA = 200.0          # ±200 vega per $1M
MAX_DAILY_THETA = -100.0            # Maximum theta burn per $100K
DELTA_REBALANCE_THRESHOLD = 0.10    # ±0.10 delta deviation triggers rebalance
GAMMA_WARNING_THRESHOLD = 100.0     # Warning at 100 gamma per $1M
VEGA_HEDGE_THRESHOLD = 100.0        # Hedge vega at ±100 per $1M
GREEK_MONITOR_INTERVAL = 5.0        # 5 second monitoring (institutional standard)
PORTFOLIO_UPDATE_INTERVAL = 15.0    # 15 minute portfolio rebalancing checks
RISK_REPORT_INTERVAL = 300.0        # 5 minute risk reporting
VIX_HIGH_THRESHOLD = 25.0           # Reduce limits by 50% when VIX > 25
VIX_EXTREME_THRESHOLD = 30.0        # Reduce limits by 75% when VIX > 30
class LimitType(Enum):
    """Greek limit types"""
    DELTA = "delta"
    GAMMA = "gamma"
    THETA = "theta"
    VEGA = "vega"
    RHO = "rho"
class LimitStatus(Enum):
    """Limit breach status"""
    NORMAL = auto()
    WARNING = auto()
    BREACH = auto()
    CRITICAL = auto()
class RebalanceAction(Enum):
    """Required rebalancing actions"""
    NONE = auto()
    HEDGE_DELTA = auto()
    REDUCE_GAMMA = auto()
    HEDGE_VEGA = auto()
    REDUCE_THETA = auto()
    EMERGENCY_FLATTEN = auto()
@dataclass
class GreekLimit:
    """Greek exposure limit configuration"""
    limit_type: LimitType
    max_positive: float
    max_negative: float
    warning_threshold: float = 0.8  # 80% of limit triggers warning
    # Dynamic adjustments
    vix_adjustment_factor: float = 1.0
    time_decay_factor: float = 1.0
    def get_effective_limit(self, is_positive: bool) -> float:
        """Get effective limit with adjustments"""
        base_limit = self.max_positive if is_positive else abs(self.max_negative)
        return base_limit * self.vix_adjustment_factor * self.time_decay_factor
@dataclass
class GreekExposure:
    """Current Greek exposure snapshot"""
    timestamp: datetime
    portfolio_value: float
    # Raw exposures
    total_delta: float
    total_gamma: float
    total_theta: float
    total_vega: float
    total_rho: float
    # Normalized exposures (per $1M)
    delta_per_million: float
    gamma_per_million: float
    theta_per_million: float
    vega_per_million: float
    # Risk metrics
    delta_dollars: float
    gamma_risk_1pct: float  # Risk from 1% SPY move
    vega_risk_1vol: float   # Risk from 1 vol point move
    theta_daily_decay: float
    # By expiration
    exposures_by_expiry: Dict[str, Dict[str, float]] = field(default_factory=dict)
@dataclass
class LimitBreach:
    """Greek limit breach event"""
    breach_id: str
    timestamp: datetime
    limit_type: LimitType
    current_exposure: float
    limit_value: float
    breach_percentage: float
    status: LimitStatus
    recommended_action: RebalanceAction
    # Context
    portfolio_value: float
    vix_level: float
    market_conditions: str
@dataclass
class RebalanceRecommendation:
    """Portfolio rebalancing recommendation"""
    recommendation_id: str
    timestamp: datetime
    priority: int  # 1 = critical, 2 = high, 3 = medium
    # Target adjustments
    target_delta_adjustment: float
    target_gamma_adjustment: float
    target_vega_adjustment: float
    # Specific actions
    hedge_shares_needed: int  # SPY shares to hedge delta
    options_to_close: List[str]  # Option symbols to close
    vix_hedge_size: int  # VIX calls/puts for vega hedge
    # Execution details
    execution_urgency: str  # 'immediate', 'within_hour', 'end_of_day'
    estimated_cost: float
    expected_improvement: Dict[str, float]
class GreekLimitsManager:
    """
    Professional Greek limits management system.
    Implements institutional-grade Greek exposure monitoring with:
    - Real-time limit checking (5-second intervals)
    - Automatic rebalancing recommendations
    - VIX-based dynamic limit adjustments
    - Crisis management protocols
    - Professional risk reporting
    """
    def __init__(
        self,
        opra_handler: OPRAGreeksHandler,
        risk_manager: RiskManager,
        ib_client: IBClient,
        alert_manager: AlertManager,
        portfolio_value: float = 1000000.0
    ):
        """Initialize Greek limits manager."""
        self.opra_handler = opra_handler
        self.risk_manager = risk_manager
        self.ib_client = ib_client
        self.alert_manager = alert_manager
        self.portfolio_value = portfolio_value
        # Logging
        self.logger = SpyderLogger().get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        # Greek limits configuration
        self.greek_limits = self._initialize_limits()
        # Current state
        self.current_exposure: Optional[GreekExposure] = None
        self.current_vix = 0.0
        self.limit_breaches: List[LimitBreach] = []
        self.rebalance_recommendations: List[RebalanceRecommendation] = []
        # Monitoring control
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        # Historical tracking
        self.exposure_history = deque(maxlen=1000)  # Last 1000 readings
        self.breach_history = deque(maxlen=100)     # Last 100 breaches
        # Callbacks
        self.limit_breach_callbacks: List[Callable] = []
        self.rebalance_callbacks: List[Callable] = []
        # Performance tracking
        self.last_portfolio_update = datetime.now()
        self.rebalance_count = 0
        self.total_hedge_cost = 0.0
        self.logger.info("Greek Limits Manager initialized")
    # ==========================================================================
    # PUBLIC METHODS - CORE FUNCTIONALITY
    # ==========================================================================
    def start_monitoring(self) -> None:
        """Start real-time Greek monitoring."""
        if self.monitoring_active:
            self.logger.warning("Greek monitoring already active")
            return
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="GreekLimitsMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        self.logger.info("Greek limits monitoring started")
    def stop_monitoring(self) -> None:
        """Stop Greek monitoring."""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        self.logger.info("Greek limits monitoring stopped")
    def update_portfolio_value(self, new_value: float) -> None:
        """Update portfolio value for limit calculations."""
        old_value = self.portfolio_value
        self.portfolio_value = new_value
        # Adjust limits proportionally
        adjustment_factor = new_value / old_value if old_value > 0 else 1.0
        self._adjust_limits_for_portfolio_size(adjustment_factor)
        self.logger.info(f"Portfolio value updated: ${old_value:,.0f} -> ${new_value:,.0f}")
    def get_current_exposure(self) -> Optional[GreekExposure]:
        """Get current Greek exposure snapshot."""
        return self.current_exposure
    def get_limit_status(self) -> Dict[str, Dict[str, Any]]:
        """Get current limit status for all Greeks."""
        if not self.current_exposure:
            return {}
        status = {}
        for limit_type in LimitType:
            limit = self.greek_limits[limit_type]
            current_value = self._get_current_exposure_value(limit_type)
            status[limit_type.value] = {
                'current_exposure': current_value,
                'limit_positive': limit.get_effective_limit(True),
                'limit_negative': limit.get_effective_limit(False),
                'utilization_pct': self._calculate_utilization(limit_type, current_value),
                'status': self._get_limit_status(limit_type, current_value).name,
                'time_to_breach': self._estimate_time_to_breach(limit_type, current_value)
            }
        return status
    def force_rebalance_check(self) -> List[RebalanceRecommendation]:
        """Force immediate rebalancing analysis."""
        try:
            # Update current exposure
            self._update_current_exposure()
            # Check all limits
            breaches = self._check_all_limits()
            # Generate recommendations
            recommendations = self._generate_rebalance_recommendations(breaches)
            return recommendations
        except Exception as e:
            self.error_handler.handle_error(e, "force_rebalance_check")
            return []
    def execute_emergency_flatten(self) -> bool:
        """Execute emergency position flattening."""
        try:
            self.logger.critical("Executing emergency position flattening")
            # Get all positions
            positions = self.ib_client.get_positions()
            # Close all option positions immediately
            success = True
            for position in positions:
                if 'SPY' in position.contract.symbol and position.contract.secType == 'OPT':
                    # Market order to close
                    close_success = self.ib_client.close_position_market(position)
                    if not close_success:
                        success = False
                        self.logger.error(f"Failed to close position: {position.contract.symbol}")
            # Alert management
            self.alert_manager.send_critical_alert(
                "Emergency Position Flattening Executed",
                "All option positions closed due to critical Greek limit breach"
            )
            return success
        except Exception as e:
            self.error_handler.handle_error(e, "execute_emergency_flatten")
            return False
    # ==========================================================================
    # PUBLIC METHODS - CONFIGURATION
    # ==========================================================================
    def update_vix_level(self, vix: float) -> None:
        """Update VIX level for dynamic limit adjustments."""
        old_vix = self.current_vix
        self.current_vix = vix
        # Adjust limits based on VIX
        self._adjust_limits_for_vix(vix)
        if abs(vix - old_vix) > 2.0:  # Significant VIX change
            self.logger.info(f"VIX updated: {old_vix:.1f} -> {vix:.1f}, limits adjusted")
    def set_custom_limit(self, limit_type: LimitType, max_positive: float, 
                        max_negative: float, warning_threshold: float = 0.8) -> None:
        """Set custom Greek limit."""
        self.greek_limits[limit_type] = GreekLimit(
            limit_type=limit_type,
            max_positive=max_positive,
            max_negative=max_negative,
            warning_threshold=warning_threshold
        )
        self.logger.info(f"Custom limit set for {limit_type.value}: +{max_positive}, -{max_negative}")
    def add_breach_callback(self, callback: Callable[[LimitBreach], None]) -> None:
        """Add callback for limit breaches."""
        self.limit_breach_callbacks.append(callback)
    def add_rebalance_callback(self, callback: Callable[[RebalanceRecommendation], None]) -> None:
        """Add callback for rebalance recommendations."""
        self.rebalance_callbacks.append(callback)
    # ==========================================================================
    # PRIVATE METHODS - MONITORING LOOP
    # ==========================================================================
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        self.logger.info("Greek limits monitoring loop started")
        while self.monitoring_active:
            try:
                start_time = time.time()
                # Update current exposure
                self._update_current_exposure()
                # Check limits
                breaches = self._check_all_limits()
                # Handle breaches
                if breaches:
                    self._handle_limit_breaches(breaches)
                # Portfolio rebalancing check (every 15 minutes)
                if (datetime.now() - self.last_portfolio_update).seconds >= PORTFOLIO_UPDATE_INTERVAL:
                    self._perform_portfolio_rebalance_check()
                    self.last_portfolio_update = datetime.now()
                # Calculate sleep time to maintain interval
                elapsed = time.time() - start_time
                sleep_time = max(0, GREEK_MONITOR_INTERVAL - elapsed)
                time.sleep(sleep_time)
            except Exception as e:
                self.error_handler.handle_error(e, "_monitoring_loop")
                time.sleep(1.0)  # Brief pause before retry
    def _update_current_exposure(self) -> None:
        """Update current Greek exposure."""
        try:
            # Get portfolio Greeks from OPRA handler
            portfolio_greeks = self.opra_handler.calculate_portfolio_greeks()
            if not portfolio_greeks:
                return
            # Create exposure snapshot
            self.current_exposure = GreekExposure(
                timestamp=datetime.now(),
                portfolio_value=self.portfolio_value,
                # Raw exposures
                total_delta=portfolio_greeks.total_delta,
                total_gamma=portfolio_greeks.total_gamma,
                total_theta=portfolio_greeks.total_theta,
                total_vega=portfolio_greeks.total_vega,
                total_rho=portfolio_greeks.total_rho,
                # Normalized (per $1M)
                delta_per_million=portfolio_greeks.total_delta * 1000000 / self.portfolio_value,
                gamma_per_million=portfolio_greeks.total_gamma * 1000000 / self.portfolio_value,
                theta_per_million=portfolio_greeks.total_theta * 1000000 / self.portfolio_value,
                vega_per_million=portfolio_greeks.total_vega * 1000000 / self.portfolio_value,
                # Risk metrics
                delta_dollars=portfolio_greeks.delta_dollars,
                gamma_risk_1pct=portfolio_greeks.gamma_scalp_potential,
                vega_risk_1vol=portfolio_greeks.vega_exposure,
                theta_daily_decay=portfolio_greeks.daily_decay,
                # By expiration
                exposures_by_expiry=portfolio_greeks.greeks_by_expiry
            )
            # Add to history
            self.exposure_history.append(self.current_exposure)
        except Exception as e:
            self.error_handler.handle_error(e, "_update_current_exposure")
    def _check_all_limits(self) -> List[LimitBreach]:
        """Check all Greek limits for breaches."""
        if not self.current_exposure:
            return []
        breaches = []
        for limit_type in LimitType:
            current_value = self._get_current_exposure_value(limit_type)
            breach = self._check_single_limit(limit_type, current_value)
            if breach:
                breaches.append(breach)
        return breaches
    def _check_single_limit(self, limit_type: LimitType, current_value: float) -> Optional[LimitBreach]:
        """Check single Greek limit."""
        limit = self.greek_limits[limit_type]
        # Determine if positive or negative
        is_positive = current_value > 0
        effective_limit = limit.get_effective_limit(is_positive)
        # Check for breach
        if abs(current_value) > effective_limit:
            status = LimitStatus.BREACH
            recommended_action = self._get_recommended_action(limit_type, current_value)
        elif abs(current_value) > effective_limit * limit.warning_threshold:
            status = LimitStatus.WARNING
            recommended_action = RebalanceAction.NONE
        else:
            return None  # No breach
        # Create breach event
        breach = LimitBreach(
            breach_id=f"{limit_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(),
            limit_type=limit_type,
            current_exposure=current_value,
            limit_value=effective_limit if is_positive else -effective_limit,
            breach_percentage=(abs(current_value) / effective_limit - 1.0) * 100,
            status=status,
            recommended_action=recommended_action,
            portfolio_value=self.portfolio_value,
            vix_level=self.current_vix,
            market_conditions=self._assess_market_conditions()
        )
        return breach
    # ==========================================================================
    # PRIVATE METHODS - INITIALIZATION
    # ==========================================================================
    def _initialize_limits(self) -> Dict[LimitType, GreekLimit]:
        """Initialize Greek limits with institutional standards."""
        return {
            LimitType.DELTA: GreekLimit(
                limit_type=LimitType.DELTA,
                max_positive=MAX_PORTFOLIO_DELTA,
                max_negative=-MAX_PORTFOLIO_DELTA,
                warning_threshold=0.8
            ),
            LimitType.GAMMA: GreekLimit(
                limit_type=LimitType.GAMMA,
                max_positive=MAX_PORTFOLIO_GAMMA,
                max_negative=-MAX_PORTFOLIO_GAMMA,
                warning_threshold=0.8
            ),
            LimitType.THETA: GreekLimit(
                limit_type=LimitType.THETA,
                max_positive=0.0,  # Theta should be negative
                max_negative=MAX_DAILY_THETA,
                warning_threshold=0.8
            ),
            LimitType.VEGA: GreekLimit(
                limit_type=LimitType.VEGA,
                max_positive=MAX_PORTFOLIO_VEGA,
                max_negative=-MAX_PORTFOLIO_VEGA,
                warning_threshold=0.8
            ),
            LimitType.RHO: GreekLimit(
                limit_type=LimitType.RHO,
                max_positive=1000.0,  # Less critical for SPY
                max_negative=-1000.0,
                warning_threshold=0.9
            )
        }
    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _get_current_exposure_value(self, limit_type: LimitType) -> float:
        """Get current exposure value for specific Greek."""
        if not self.current_exposure:
            return 0.0
        if limit_type == LimitType.DELTA:
            return self.current_exposure.delta_per_million
        elif limit_type == LimitType.GAMMA:
            return self.current_exposure.gamma_per_million
        elif limit_type == LimitType.THETA:
            return self.current_exposure.theta_per_million
        elif limit_type == LimitType.VEGA:
            return self.current_exposure.vega_per_million
        elif limit_type == LimitType.RHO:
            return self.current_exposure.total_rho
        else:
            return 0.0
    def _adjust_limits_for_vix(self, vix: float) -> None:
        """Adjust limits based on VIX level."""
        if vix > VIX_EXTREME_THRESHOLD:
            adjustment_factor = 0.25  # Reduce limits by 75%
        elif vix > VIX_HIGH_THRESHOLD:
            adjustment_factor = 0.5   # Reduce limits by 50%
        else:
            adjustment_factor = 1.0   # Normal limits
        for limit in self.greek_limits.values():
            limit.vix_adjustment_factor = adjustment_factor
    def _generate_rebalance_recommendations(self, breaches: List[LimitBreach]) -> List[RebalanceRecommendation]:
        """Generate rebalancing recommendations."""
        if not breaches or not self.current_exposure:
            return []
        # For now, return simplified recommendations
        # Full implementation would calculate specific hedge ratios
        recommendations = []
        for breach in breaches:
            if breach.status == LimitStatus.BREACH:
                rec = RebalanceRecommendation(
                    recommendation_id=f"rebal_{breach.breach_id}",
                    timestamp=datetime.now(),
                    priority=1 if breach.status == LimitStatus.BREACH else 2,
                    target_delta_adjustment=0.0,
                    target_gamma_adjustment=0.0,
                    target_vega_adjustment=0.0,
                    hedge_shares_needed=0,
                    options_to_close=[],
                    vix_hedge_size=0,
                    execution_urgency="immediate",
                    estimated_cost=0.0,
                    expected_improvement={}
                )
                recommendations.append(rec)
        return recommendations
    def _handle_limit_breaches(self, breaches: List[LimitBreach]) -> None:
        """Handle limit breaches."""
        for breach in breaches:
            # Add to history
            self.breach_history.append(breach)
            # Send alerts
            alert_level = AlertLevel.CRITICAL if breach.status == LimitStatus.BREACH else AlertLevel.WARNING
            self.alert_manager.send_alert(
                level=alert_level,
                title=f"Greek Limit {breach.status.name}: {breach.limit_type.value.upper()}",
                message=f"Current: {breach.current_exposure:.1f}, Limit: {breach.limit_value:.1f}"
            )
            # Execute callbacks
            for callback in self.limit_breach_callbacks:
                try:
                    callback(breach)
                except Exception as e:
                    self.logger.error(f"Breach callback error: {e}")
    def _perform_portfolio_rebalance_check(self) -> None:
        """Perform comprehensive portfolio rebalancing check."""
        # Placeholder for portfolio rebalancing logic
        pass
    def _get_recommended_action(self, limit_type: LimitType, current_value: float) -> RebalanceAction:
        """Get recommended action for limit breach."""
        if limit_type == LimitType.DELTA:
            return RebalanceAction.HEDGE_DELTA
        elif limit_type == LimitType.GAMMA:
            return RebalanceAction.REDUCE_GAMMA
        elif limit_type == LimitType.VEGA:
            return RebalanceAction.HEDGE_VEGA
        elif limit_type == LimitType.THETA:
            return RebalanceAction.REDUCE_THETA
        else:
            return RebalanceAction.NONE
    def _assess_market_conditions(self) -> str:
        """Assess current market conditions."""
        if self.current_vix > 30:
            return "extreme_volatility"
        elif self.current_vix > 25:
            return "high_volatility"
        elif self.current_vix < 15:
            return "low_volatility"
        else:
            return "normal"
    def _calculate_utilization(self, limit_type: LimitType, current_value: float) -> float:
        """Calculate limit utilization percentage."""
        limit = self.greek_limits[limit_type]
        is_positive = current_value > 0
        effective_limit = limit.get_effective_limit(is_positive)
        if effective_limit == 0:
            return 0.0
        return abs(current_value) / effective_limit * 100
    def _get_limit_status(self, limit_type: LimitType, current_value: float) -> LimitStatus:
        """Get limit status for current value."""
        limit = self.greek_limits[limit_type]
        is_positive = current_value > 0
        effective_limit = limit.get_effective_limit(is_positive)
        utilization = abs(current_value) / effective_limit if effective_limit > 0 else 0
        if utilization >= 1.0:
            return LimitStatus.BREACH
        elif utilization >= limit.warning_threshold:
            return LimitStatus.WARNING
        else:
            return LimitStatus.NORMAL
    def _estimate_time_to_breach(self, limit_type: LimitType, current_value: float) -> Optional[float]:
        """Estimate time to limit breach in minutes."""
        # Simplified implementation - would use trend analysis
        return None
    def _adjust_limits_for_portfolio_size(self, adjustment_factor: float) -> None:
        """Adjust limits for portfolio size changes."""
        for limit in self.greek_limits.values():
            limit.max_positive *= adjustment_factor
            limit.max_negative *= adjustment_factor
    # ==========================================================================
    # PUBLIC METHODS - REPORTING
    # ==========================================================================
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            'monitoring_status': self.monitoring_active,
            'portfolio_value': self.portfolio_value,
            'current_vix': self.current_vix,
            'total_breaches': len(self.breach_history),
            'rebalance_count': self.rebalance_count,
            'total_hedge_cost': self.total_hedge_cost,
            'last_update': self.current_exposure.timestamp if self.current_exposure else None,
            'exposure_history_length': len(self.exposure_history)
        }
if __name__ == "__main__":
    # Example usage
    print("Greek Limits Manager - Professional Risk Controls")
    print("=" * 60)
    # Note: This is example code - actual implementation would need
    # real OPRA handler, risk manager, and IB client instances