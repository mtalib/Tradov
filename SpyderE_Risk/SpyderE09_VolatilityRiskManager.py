#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE09_VolatilityRiskManager.py
Group: E (Risk Management)
Purpose: Volatility-specific risk management and protection protocols

Description:
    This module provides specialized risk management for volatility trading,
    including VIX spike protection protocols, volatility regime-based position
    sizing, gamma scalping automation, and comprehensive vol surface risk metrics.
    It integrates with existing risk management systems to add volatility-specific
    controls and protections. Provides real-time monitoring of volatility risks
    and automated hedging strategies.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-01
Last Updated: 2025-07-06 Time: 17:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
import uuid
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from dataclasses import dataclass, field, asdict
from collections import deque, defaultdict
from enum import Enum, auto
from pathlib import Path
import math
import statistics

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS - SAFE PATTERN
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    import logging
    SpyderLogger = type('SpyderLogger', (), {
        'get_logger': lambda name: logging.getLogger(name)
    })()

try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    SpyderErrorHandler = type('SpyderErrorHandler', (), {
        'handle_error': lambda self, e, context: print(f"Error in {context}: {e}")
    })

# ==============================================================================
# CONSTANTS
# ==============================================================================
# VIX Levels
VIX_LOW_THRESHOLD = 15
VIX_NORMAL_THRESHOLD = 20
VIX_HIGH_THRESHOLD = 30
VIX_EXTREME_THRESHOLD = 40
VIX_SPIKE_THRESHOLD = 5  # Daily change

# Greeks Exposure Limits (per $100k)
MAX_VEGA_EXPOSURE = 500
MAX_VOLGA_EXPOSURE = 100
MAX_VANNA_EXPOSURE = 200
MAX_GAMMA_EXPOSURE = 100

# Protection Thresholds
VEGA_PROTECTION_THRESHOLD = 0.8  # 80% of max
VIX_PROTECTION_ACTIVATION = 25
TERM_STRUCTURE_WARNING = 0.2  # 20% backwardation

# Gamma Scalping Parameters
GAMMA_SCALP_THRESHOLD = 0.5  # $0.50 move
MIN_GAMMA_FOR_SCALPING = 10
SCALP_PROFIT_TARGET = 0.001  # 0.1% per scalp

# Monitoring
VOL_CHECK_INTERVAL = 30  # seconds
SURFACE_UPDATE_INTERVAL = 300  # 5 minutes

# ==============================================================================
# ENUMS
# ==============================================================================
class VolatilityRegime(Enum):
    """Volatility regime classifications."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"
    TRANSITION = "transition"

class VolRiskSignal(Enum):
    """Volatility risk signal levels."""
    SAFE = "safe"
    CAUTION = "caution"
    WARNING = "warning"
    DANGER = "danger"

class ProtectionLevel(Enum):
    """Protection protocol levels."""
    NONE = "none"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    FULL = "full"

class VolProtocolAction(Enum):
    """Volatility protection actions."""
    REDUCE_VEGA = "reduce_vega"
    BUY_PROTECTION = "buy_protection"
    CLOSE_SHORT_VOL = "close_short_vol"
    HEDGE_TAIL_RISK = "hedge_tail_risk"
    FLATTEN_BOOK = "flatten_book"
    ACTIVATE_SCALPING = "activate_scalping"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VolatilityMetrics:
    """Current volatility metrics."""
    timestamp: datetime
    spot_vix: float
    vix_change_1d: float
    vix_change_5d: float
    realized_vol_10d: float
    realized_vol_30d: float
    implied_vol_atm: float
    vol_of_vol: float
    put_call_ratio: float
    term_structure: Dict[str, float]
    regime: VolatilityRegime
    regime_confidence: float

@dataclass
class VolatilityExposure:
    """Portfolio volatility exposure."""
    vega_exposure: float
    volga_exposure: float  # Vega of vega
    vanna_exposure: float  # Vega of delta
    gamma_exposure: float
    vega_by_expiry: Dict[datetime, float]
    vega_by_strike: Dict[float, float]
    short_vol_exposure: float
    long_vol_exposure: float
    net_vol_exposure: float

@dataclass
class VolRiskAssessment:
    """Volatility risk assessment."""
    timestamp: datetime
    risk_signal: VolRiskSignal
    risk_score: float  # 0-100
    vix_spike_risk: float
    gamma_risk: float
    vega_concentration_risk: float
    term_structure_risk: float
    protection_needed: ProtectionLevel
    risk_factors: List[str]
    vega_exposure: float
    volga_exposure: float
    vanna_exposure: float

@dataclass
class VolProtectionProtocol:
    """Volatility protection protocol."""
    protocol_id: str
    activation_time: datetime
    protection_level: ProtectionLevel
    actions: List[VolProtocolAction]
    target_vega_reduction: float
    hedges_required: List[Dict[str, Any]]
    estimated_cost: float
    status: str  # 'pending', 'active', 'completed'

@dataclass
class GammaScalpingPlan:
    """Gamma scalping execution plan."""
    position_id: str
    underlying_price: float
    gamma_exposure: float
    scalp_threshold: float
    last_scalp_price: float
    scalps_executed: int
    total_pnl: float
    active: bool

@dataclass
class VolRiskProfile:
    """Complete volatility risk profile."""
    timestamp: datetime
    metrics: VolatilityMetrics
    exposure: VolatilityExposure
    risk_assessment: VolRiskAssessment
    active_protocols: List[VolProtectionProtocol]
    scalping_plans: List[GammaScalpingPlan]
    recommendations: List[str]
    overall_health: str  # 'healthy', 'cautious', 'at_risk', 'critical'

# ==============================================================================
# VOLATILITY RISK MANAGER CLASS
# ==============================================================================
class VolatilityRiskManager:
    """
    Manages volatility-specific risks and protection protocols.
    
    Provides comprehensive volatility risk management including VIX monitoring,
    vol surface analysis, Greeks-based hedging, and automated protection protocols.
    Integrates with main risk management system for holistic risk control.
    
    Attributes:
        current_regime: Current volatility regime
        protection_level: Active protection level
        active_protocols: Currently active protection protocols
        
    Example:
        >>> vol_mgr = VolatilityRiskManager()
        >>> risk_profile = vol_mgr.assess_volatility_risk()
        >>> if risk_profile.risk_assessment.risk_signal == VolRiskSignal.DANGER:
        ...     vol_mgr.activate_protection_protocol()
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize volatility risk manager.
        
        Args:
            config: Optional configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config or {}
        self.max_vega = self.config.get('max_vega', MAX_VEGA_EXPOSURE)
        self.max_volga = self.config.get('max_volga', MAX_VOLGA_EXPOSURE)
        self.max_vanna = self.config.get('max_vanna', MAX_VANNA_EXPOSURE)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Current state
        self.current_regime = VolatilityRegime.NORMAL
        self.protection_level = ProtectionLevel.NONE
        self.active_protocols: List[VolProtectionProtocol] = []
        
        # Risk tracking
        self.current_metrics: Optional[VolatilityMetrics] = None
        self.current_exposure: Optional[VolatilityExposure] = None
        
        # Gamma scalping
        self.scalping_positions: Dict[str, GammaScalpingPlan] = {}
        self.scalp_history: deque = deque(maxlen=100)
        
        # Historical data
        self.vix_history: deque = deque(maxlen=252)  # 1 year
        self.vol_history: deque = deque(maxlen=1000)
        self.risk_history: deque = deque(maxlen=1000)
        
        # Monitoring
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Initialize vol surface data
        self._vol_surface_data: Dict[str, Any] = {}
        self._last_surface_update = datetime.now()
        
        # Mock data for VIX (would come from market data in production)
        self._mock_vix_data = {
            'spot': 18.5,
            '30d': 19.2,
            '60d': 19.8,
            '90d': 20.1
        }
        
        self.logger.info("VolatilityRiskManager initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - RISK ASSESSMENT
    # ==========================================================================
    def assess_volatility_risk(self, positions: Optional[List[Dict[str, Any]]] = None) -> VolRiskProfile:
        """
        Perform comprehensive volatility risk assessment.
        
        Args:
            positions: Optional list of positions to analyze
            
        Returns:
            Complete volatility risk profile
        """
        with self._lock:
            try:
                # Update metrics
                self.current_metrics = self._calculate_volatility_metrics()
                
                # Calculate exposure
                self.current_exposure = self._calculate_vol_exposure(positions)
                
                # Perform risk assessment
                risk_assessment = self._assess_risk_levels()
                
                # Check active protocols
                self._update_active_protocols()
                
                # Get scalping plans
                active_scalping = [
                    plan for plan in self.scalping_positions.values() 
                    if plan.active
                ]
                
                # Generate recommendations
                recommendations = self._generate_recommendations(risk_assessment)
                
                # Determine overall health
                overall_health = self._determine_overall_health(risk_assessment)
                
                # Create profile
                profile = VolRiskProfile(
                    timestamp=datetime.now(),
                    metrics=self.current_metrics,
                    exposure=self.current_exposure,
                    risk_assessment=risk_assessment,
                    active_protocols=self.active_protocols,
                    scalping_plans=active_scalping,
                    recommendations=recommendations,
                    overall_health=overall_health
                )
                
                # Store in history
                self.risk_history.append({
                    'timestamp': profile.timestamp,
                    'risk_signal': profile.risk_assessment.risk_signal,
                    'risk_score': profile.risk_assessment.risk_score,
                    'vega_exposure': profile.exposure.vega_exposure
                })
                
                return profile
                
            except Exception as e:
                self.logger.error(f"Volatility risk assessment error: {e}")
                self.error_handler.handle_error(e, {"method": "assess_volatility_risk"})
                return self._create_default_risk_profile()
    
    def activate_protection_protocol(self, level: Optional[ProtectionLevel] = None) -> VolProtectionProtocol:
        """
        Activate volatility protection protocol.
        
        Args:
            level: Protection level to activate (auto-determined if None)
            
        Returns:
            Activated protection protocol
        """
        with self._lock:
            # Determine protection level if not specified
            if not level:
                level = self._determine_protection_level()
            
            # Create protocol
            protocol = VolProtectionProtocol(
                protocol_id=f"VOL_PROT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                activation_time=datetime.now(),
                protection_level=level,
                actions=self._determine_protection_actions(level),
                target_vega_reduction=self._calculate_target_vega_reduction(level),
                hedges_required=self._calculate_required_hedges(level),
                estimated_cost=0.0,  # Would calculate based on hedges
                status='active'
            )
            
            # Estimate cost
            protocol.estimated_cost = self._estimate_protection_cost(protocol)
            
            # Add to active protocols
            self.active_protocols.append(protocol)
            self.protection_level = level
            
            self.logger.warning(
                f"Activated {level.value} protection protocol: {protocol.protocol_id}"
            )
            
            return protocol
    
    def execute_gamma_scalping(self, position_id: str, position_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute gamma scalping for a position.
        
        Args:
            position_id: Position identifier
            position_data: Position details including Greeks
            
        Returns:
            Scalping execution details or None
        """
        with self._lock:
            # Check if position suitable for scalping
            gamma = position_data.get('gamma', 0)
            if abs(gamma) < MIN_GAMMA_FOR_SCALPING:
                return None
            
            # Get or create scalping plan
            if position_id not in self.scalping_positions:
                self.scalping_positions[position_id] = GammaScalpingPlan(
                    position_id=position_id,
                    underlying_price=position_data.get('underlying_price', 0),
                    gamma_exposure=gamma,
                    scalp_threshold=GAMMA_SCALP_THRESHOLD,
                    last_scalp_price=position_data.get('underlying_price', 0),
                    scalps_executed=0,
                    total_pnl=0.0,
                    active=True
                )
            
            plan = self.scalping_positions[position_id]
            current_price = position_data.get('underlying_price', 0)
            
            # Check if scalp threshold reached
            price_move = abs(current_price - plan.last_scalp_price)
            if price_move >= plan.scalp_threshold:
                # Calculate scalp details
                scalp_direction = 'BUY' if current_price < plan.last_scalp_price else 'SELL'
                scalp_quantity = int(abs(gamma) * 100)  # Simplified calculation
                
                # Record scalp
                scalp_result = {
                    'timestamp': datetime.now(),
                    'position_id': position_id,
                    'direction': scalp_direction,
                    'quantity': scalp_quantity,
                    'price': current_price,
                    'expected_pnl': scalp_quantity * SCALP_PROFIT_TARGET * current_price
                }
                
                # Update plan
                plan.last_scalp_price = current_price
                plan.scalps_executed += 1
                plan.total_pnl += scalp_result['expected_pnl']
                
                # Store in history
                self.scalp_history.append(scalp_result)
                
                self.logger.info(
                    f"Gamma scalp executed: {scalp_direction} {scalp_quantity} @ {current_price:.2f}"
                )
                
                return scalp_result
            
            return None
    
    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    def _calculate_volatility_metrics(self) -> VolatilityMetrics:
        """Calculate current volatility metrics."""
        # In production, would fetch from market data
        # Using mock data for demonstration
        
        spot_vix = self._mock_vix_data['spot']
        
        # Calculate changes
        vix_change_1d = 0.5  # Mock
        vix_change_5d = -1.2  # Mock
        
        # Calculate realized vol (mock)
        realized_vol_10d = 0.16
        realized_vol_30d = 0.18
        
        # ATM implied vol (mock)
        implied_vol_atm = 0.17
        
        # Vol of vol
        vol_of_vol = 0.25
        
        # Put/call ratio
        put_call_ratio = 1.2
        
        # Term structure
        term_structure = {
            '30d': self._mock_vix_data['30d'],
            '60d': self._mock_vix_data['60d'],
            '90d': self._mock_vix_data['90d']
        }
        
        # Determine regime
        regime = self._determine_volatility_regime(spot_vix)
        regime_confidence = 0.85  # Mock confidence
        
        return VolatilityMetrics(
            timestamp=datetime.now(),
            spot_vix=spot_vix,
            vix_change_1d=vix_change_1d,
            vix_change_5d=vix_change_5d,
            realized_vol_10d=realized_vol_10d,
            realized_vol_30d=realized_vol_30d,
            implied_vol_atm=implied_vol_atm,
            vol_of_vol=vol_of_vol,
            put_call_ratio=put_call_ratio,
            term_structure=term_structure,
            regime=regime,
            regime_confidence=regime_confidence
        )
    
    def _calculate_vol_exposure(self, positions: Optional[List[Dict[str, Any]]]) -> VolatilityExposure:
        """Calculate portfolio volatility exposure."""
        # Mock calculation - would aggregate from actual positions
        
        vega_exposure = 250.0  # Mock
        volga_exposure = 50.0  # Mock
        vanna_exposure = 75.0  # Mock
        gamma_exposure = 40.0  # Mock
        
        # Vega by expiry (mock)
        vega_by_expiry = {
            datetime.now() + timedelta(days=30): 100.0,
            datetime.now() + timedelta(days=60): 150.0
        }
        
        # Vega by strike (mock)
        vega_by_strike = {
            390.0: 50.0,
            400.0: 150.0,
            410.0: 50.0
        }
        
        short_vol = 100.0
        long_vol = 350.0
        
        return VolatilityExposure(
            vega_exposure=vega_exposure,
            volga_exposure=volga_exposure,
            vanna_exposure=vanna_exposure,
            gamma_exposure=gamma_exposure,
            vega_by_expiry=vega_by_expiry,
            vega_by_strike=vega_by_strike,
            short_vol_exposure=short_vol,
            long_vol_exposure=long_vol,
            net_vol_exposure=long_vol - short_vol
        )
    
    def _assess_risk_levels(self) -> VolRiskAssessment:
        """Assess volatility risk levels."""
        risk_factors = []
        risk_score = 0.0
        
        # VIX level risk
        vix_risk = 0.0
        if self.current_metrics.spot_vix > VIX_HIGH_THRESHOLD:
            vix_risk = 30.0
            risk_factors.append(f"High VIX: {self.current_metrics.spot_vix:.1f}")
        elif self.current_metrics.spot_vix > VIX_NORMAL_THRESHOLD:
            vix_risk = 15.0
        
        # VIX spike risk
        spike_risk = 0.0
        if abs(self.current_metrics.vix_change_1d) > VIX_SPIKE_THRESHOLD:
            spike_risk = 25.0
            risk_factors.append(f"VIX spike: {self.current_metrics.vix_change_1d:+.1f}")
        
        # Exposure risk
        exposure_risk = 0.0
        if self.current_exposure:
            vega_util = abs(self.current_exposure.vega_exposure) / self.max_vega
            if vega_util > 0.8:
                exposure_risk = 20.0
                risk_factors.append(f"High vega exposure: {vega_util:.0%}")
        
        # Term structure risk
        term_risk = self._calculate_term_structure_risk()
        if term_risk > 0.2:
            risk_factors.append("Term structure inversion")
        
        # Calculate total risk score
        risk_score = vix_risk + spike_risk + exposure_risk + (term_risk * 10)
        
        # Determine signal
        if risk_score >= 60:
            risk_signal = VolRiskSignal.DANGER
        elif risk_score >= 40:
            risk_signal = VolRiskSignal.WARNING
        elif risk_score >= 20:
            risk_signal = VolRiskSignal.CAUTION
        else:
            risk_signal = VolRiskSignal.SAFE
        
        # Determine protection needed
        if risk_signal == VolRiskSignal.DANGER:
            protection = ProtectionLevel.HEAVY
        elif risk_signal == VolRiskSignal.WARNING:
            protection = ProtectionLevel.MODERATE
        elif risk_signal == VolRiskSignal.CAUTION:
            protection = ProtectionLevel.LIGHT
        else:
            protection = ProtectionLevel.NONE
        
        return VolRiskAssessment(
            timestamp=datetime.now(),
            risk_signal=risk_signal,
            risk_score=risk_score,
            vix_spike_risk=spike_risk,
            gamma_risk=abs(self.current_exposure.gamma_exposure) if self.current_exposure else 0,
            vega_concentration_risk=self._calculate_vega_concentration_risk(),
            term_structure_risk=term_risk,
            protection_needed=protection,
            risk_factors=risk_factors,
            vega_exposure=self.current_exposure.vega_exposure if self.current_exposure else 0,
            volga_exposure=self.current_exposure.volga_exposure if self.current_exposure else 0,
            vanna_exposure=self.current_exposure.vanna_exposure if self.current_exposure else 0
        )
    
    def _determine_volatility_regime(self, vix_level: float) -> VolatilityRegime:
        """Determine current volatility regime."""
        if vix_level < VIX_LOW_THRESHOLD:
            return VolatilityRegime.LOW
        elif vix_level < VIX_NORMAL_THRESHOLD:
            return VolatilityRegime.NORMAL
        elif vix_level < VIX_HIGH_THRESHOLD:
            return VolatilityRegime.HIGH
        elif vix_level < VIX_EXTREME_THRESHOLD:
            return VolatilityRegime.EXTREME
        else:
            return VolatilityRegime.EXTREME
    
    def _calculate_term_structure_risk(self) -> float:
        """Calculate term structure risk (backwardation)."""
        if not self.current_metrics:
            return 0.0
        
        # Check for backwardation
        spot = self.current_metrics.spot_vix
        term_30d = self.current_metrics.term_structure.get('30d', spot)
        
        if term_30d < spot:
            # Backwardation
            return (spot - term_30d) / spot
        
        return 0.0
    
    def _calculate_vega_concentration_risk(self) -> float:
        """Calculate vega concentration risk."""
        if not self.current_exposure:
            return 0.0
        
        # Check concentration by expiry
        total_vega = abs(self.current_exposure.vega_exposure)
        if total_vega == 0:
            return 0.0
        
        max_concentration = 0.0
        for expiry_vega in self.current_exposure.vega_by_expiry.values():
            concentration = abs(expiry_vega) / total_vega
            max_concentration = max(max_concentration, concentration)
        
        return max_concentration
    
    # ==========================================================================
    # PRIVATE METHODS - PROTECTION
    # ==========================================================================
    def _determine_protection_level(self) -> ProtectionLevel:
        """Determine appropriate protection level."""
        if not self.current_metrics or not self.current_exposure:
            return ProtectionLevel.NONE
        
        # Based on current risk assessment
        risk_assessment = self._assess_risk_levels()
        return risk_assessment.protection_needed
    
    def _determine_protection_actions(self, level: ProtectionLevel) -> List[VolProtocolAction]:
        """Determine protection actions for level."""
        actions_map = {
            ProtectionLevel.NONE: [],
            ProtectionLevel.LIGHT: [
                VolProtocolAction.REDUCE_VEGA
            ],
            ProtectionLevel.MODERATE: [
                VolProtocolAction.REDUCE_VEGA,
                VolProtocolAction.BUY_PROTECTION
            ],
            ProtectionLevel.HEAVY: [
                VolProtocolAction.REDUCE_VEGA,
                VolProtocolAction.BUY_PROTECTION,
                VolProtocolAction.CLOSE_SHORT_VOL
            ],
            ProtectionLevel.FULL: [
                VolProtocolAction.FLATTEN_BOOK,
                VolProtocolAction.HEDGE_TAIL_RISK
            ]
        }
        
        return actions_map.get(level, [])
    
    def _calculate_target_vega_reduction(self, level: ProtectionLevel) -> float:
        """Calculate target vega reduction percentage."""
        reduction_map = {
            ProtectionLevel.NONE: 0.0,
            ProtectionLevel.LIGHT: 0.2,
            ProtectionLevel.MODERATE: 0.4,
            ProtectionLevel.HEAVY: 0.6,
            ProtectionLevel.FULL: 1.0
        }
        
        return reduction_map.get(level, 0.0)
    
    def _calculate_required_hedges(self, level: ProtectionLevel) -> List[Dict[str, Any]]:
        """Calculate required hedges for protection."""
        hedges = []
        
        if level in [ProtectionLevel.MODERATE, ProtectionLevel.HEAVY]:
            # VIX call hedge
            hedges.append({
                'type': 'vix_call',
                'strike': self.current_metrics.spot_vix + 5 if self.current_metrics else 25,
                'quantity': int(abs(self.current_exposure.vega_exposure / 100)) if self.current_exposure else 1,
                'expiry': '30d'
            })
        
        if level == ProtectionLevel.HEAVY:
            # SPY put hedge
            hedges.append({
                'type': 'spy_put',
                'strike': 'ATM-2%',
                'quantity': int(abs(self.current_exposure.gamma_exposure / 10)) if self.current_exposure else 1,
                'expiry': '30d'
            })
        
        return hedges
    
    def _estimate_protection_cost(self, protocol: VolProtectionProtocol) -> float:
        """Estimate cost of protection protocol."""
        # Simplified calculation
        cost = 0.0
        
        for hedge in protocol.hedges_required:
            if hedge['type'] == 'vix_call':
                # Rough estimate: $2 per VIX call
                cost += hedge['quantity'] * 2.0 * 100
            elif hedge['type'] == 'spy_put':
                # Rough estimate: $3 per SPY put
                cost += hedge['quantity'] * 3.0 * 100
        
        return cost
    
    def _update_active_protocols(self) -> None:
        """Update status of active protocols."""
        current_time = datetime.now()
        
        for protocol in self.active_protocols:
            # Check if protocol should be completed
            if protocol.status == 'active':
                # Simple time-based completion (would be more sophisticated)
                if (current_time - protocol.activation_time).seconds > 3600:  # 1 hour
                    protocol.status = 'completed'
    
    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _generate_recommendations(self, risk_assessment: VolRiskAssessment) -> List[str]:
        """Generate risk management recommendations."""
        recommendations = []
        
        # VIX-based recommendations
        if self.current_metrics:
            if self.current_metrics.spot_vix > VIX_HIGH_THRESHOLD:
                recommendations.append(
                    f"VIX elevated at {self.current_metrics.spot_vix:.1f} - consider reducing position sizes"
                )
            
            if abs(self.current_metrics.vix_change_1d) > 3:
                recommendations.append(
                    f"Large VIX move ({self.current_metrics.vix_change_1d:+.1f}) - monitor for continuation"
                )
        
        # Exposure recommendations
        if self.current_exposure:
            vega_util = abs(self.current_exposure.vega_exposure) / self.max_vega
            if vega_util > 0.8:
                recommendations.append(
                    f"Vega exposure at {vega_util:.0%} of limit - consider hedging"
                )
        
        # Risk signal recommendations
        if risk_assessment.risk_signal == VolRiskSignal.DANGER:
            recommendations.append("HIGH RISK: Activate protection protocols immediately")
        elif risk_assessment.risk_signal == VolRiskSignal.WARNING:
            recommendations.append("Elevated risk - prepare protection strategies")
        
        return recommendations
    
    def _determine_overall_health(self, risk_assessment: VolRiskAssessment) -> str:
        """Determine overall volatility health status."""
        if risk_assessment.risk_signal == VolRiskSignal.DANGER:
            return 'critical'
        elif risk_assessment.risk_signal == VolRiskSignal.WARNING:
            return 'at_risk'
        elif risk_assessment.risk_signal == VolRiskSignal.CAUTION:
            return 'cautious'
        else:
            return 'healthy'
    
    def _create_default_risk_profile(self) -> VolRiskProfile:
        """Create default risk profile for error cases."""
        default_metrics = VolatilityMetrics(
            timestamp=datetime.now(),
            spot_vix=20.0,
            vix_change_1d=0.0,
            vix_change_5d=0.0,
            realized_vol_10d=0.15,
            realized_vol_30d=0.16,
            implied_vol_atm=0.17,
            vol_of_vol=0.25,
            put_call_ratio=1.0,
            term_structure={'30d': 20.0, '60d': 20.5, '90d': 21.0},
            regime=VolatilityRegime.NORMAL,
            regime_confidence=0.5
        )
        
        default_exposure = VolatilityExposure(
            vega_exposure=0.0,
            volga_exposure=0.0,
            vanna_exposure=0.0,
            gamma_exposure=0.0,
            vega_by_expiry={},
            vega_by_strike={},
            short_vol_exposure=0.0,
            long_vol_exposure=0.0,
            net_vol_exposure=0.0
        )
        
        default_assessment = VolRiskAssessment(
            timestamp=datetime.now(),
            risk_signal=VolRiskSignal.SAFE,
            risk_score=0.0,
            vix_spike_risk=0.0,
            gamma_risk=0.0,
            vega_concentration_risk=0.0,
            term_structure_risk=0.0,
            protection_needed=ProtectionLevel.NONE,
            risk_factors=[],
            vega_exposure=0.0,
            volga_exposure=0.0,
            vanna_exposure=0.0
        )
        
        return VolRiskProfile(
            timestamp=datetime.now(),
            metrics=default_metrics,
            exposure=default_exposure,
            risk_assessment=default_assessment,
            active_protocols=[],
            scalping_plans=[],
            recommendations=["Unable to assess risk - using defaults"],
            overall_health='unknown'
        )
    
    # ==========================================================================
    # PUBLIC METHODS - CONFIGURATION
    # ==========================================================================
    def update_limits(self, limits: Dict[str, float]) -> None:
        """Update exposure limits."""
        with self._lock:
            if 'max_vega' in limits:
                self.max_vega = limits['max_vega']
            if 'max_volga' in limits:
                self.max_volga = limits['max_volga']
            if 'max_vanna' in limits:
                self.max_vanna = limits['max_vanna']
            
            self.logger.info(f"Updated volatility limits: {limits}")
    
    def get_risk_statistics(self) -> Dict[str, Any]:
        """Get volatility risk statistics."""
        with self._lock:
            if not self.risk_history:
                return {}
            
            recent_risks = list(self.risk_history)[-100:]
            risk_scores = [r['risk_score'] for r in recent_risks]
            
            return {
                'avg_risk_score': statistics.mean(risk_scores) if risk_scores else 0,
                'max_risk_score': max(risk_scores) if risk_scores else 0,
                'current_regime': self.current_regime.value,
                'protection_level': self.protection_level.value,
                'active_protocols': len(self.active_protocols),
                'total_scalps': sum(p.scalps_executed for p in self.scalping_positions.values()),
                'scalping_pnl': sum(p.total_pnl for p in self.scalping_positions.values())
            }
    
    def get_protection_history(self) -> List[Dict[str, Any]]:
        """Get protection protocol history."""
        with self._lock:
            return [
                {
                    'protocol_id': p.protocol_id,
                    'activation_time': p.activation_time.isoformat(),
                    'protection_level': p.protection_level.value,
                    'status': p.status,
                    'estimated_cost': p.estimated_cost
                }
                for p in self.active_protocols
            ]
    
    # ==========================================================================
    # PUBLIC METHODS - MONITORING
    # ==========================================================================
    def start_monitoring(self) -> None:
        """Start volatility monitoring."""
        if not self._monitoring_active:
            self._monitoring_active = True
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="VolatilityMonitor",
                daemon=True
            )
            self._monitor_thread.start()
            self.logger.info("Volatility monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop volatility monitoring."""
        if self._monitoring_active:
            self._monitoring_active = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5)
            self.logger.info("Volatility monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                # Periodic volatility check
                self.assess_volatility_risk()
                
                # Check if protection needed
                if self.current_metrics and self.current_metrics.spot_vix > VIX_PROTECTION_ACTIVATION:
                    if not self.active_protocols or all(p.status == 'completed' for p in self.active_protocols):
                        self.logger.warning("VIX elevated - considering protection")
                
                # Update vol surface periodically
                if (datetime.now() - self._last_surface_update).seconds > SURFACE_UPDATE_INTERVAL:
                    self._update_vol_surface()
                
                # Sleep
                threading.Event().wait(VOL_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                self.error_handler.handle_error(e, {"method": "_monitoring_loop"})
    
    def _update_vol_surface(self) -> None:
        """Update volatility surface data."""
        # In production, would fetch from market data
        self._last_surface_update = datetime.now()
        self.logger.debug("Volatility surface updated")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_volatility_risk_manager(config: Optional[Dict[str, Any]] = None) -> VolatilityRiskManager:
    """
    Create volatility risk manager instance.
    
    Args:
        config: Optional configuration
        
    Returns:
        VolatilityRiskManager instance
    """
    return VolatilityRiskManager(config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    print("="*80)
    print("SPYDER E09 - Volatility Risk Manager Test")
    print("="*80)
    
    # Create volatility risk manager
    vol_mgr = create_volatility_risk_manager()
    
    # Start monitoring
    vol_mgr.start_monitoring()
    
    # Assess current risk
    print("\n📊 Assessing Volatility Risk...")
    risk_profile = vol_mgr.assess_volatility_risk()
    
    print(f"\nVolatility Metrics:")
    print(f"  VIX Level: {risk_profile.metrics.spot_vix:.1f}")
    print(f"  VIX 1D Change: {risk_profile.metrics.vix_change_1d:+.1f}")
    print(f"  Regime: {risk_profile.metrics.regime.value}")
    print(f"  Put/Call Ratio: {risk_profile.metrics.put_call_ratio:.2f}")
    
    print(f"\nVolatility Exposure:")
    print(f"  Vega: ${risk_profile.exposure.vega_exposure:,.0f}")
    print(f"  Volga: ${risk_profile.exposure.volga_exposure:,.0f}")
    print(f"  Vanna: ${risk_profile.exposure.vanna_exposure:,.0f}")
    print(f"  Net Vol: ${risk_profile.exposure.net_vol_exposure:,.0f}")
    
    print(f"\nRisk Assessment:")
    print(f"  Risk Signal: {risk_profile.risk_assessment.risk_signal.value}")
    print(f"  Risk Score: {risk_profile.risk_assessment.risk_score:.1f}/100")
    print(f"  Protection Needed: {risk_profile.risk_assessment.protection_needed.value}")
    
    if risk_profile.risk_assessment.risk_factors:
        print(f"\nRisk Factors:")
        for factor in risk_profile.risk_assessment.risk_factors:
            print(f"  ⚠️  {factor}")
    
    if risk_profile.recommendations:
        print(f"\nRecommendations:")
        for rec in risk_profile.recommendations:
            print(f"  💡 {rec}")
    
    print(f"\nOverall Health: {risk_profile.overall_health}")
    
    # Test protection protocol
    print("\n\n🛡️ Testing Protection Protocol Activation")
    print("-"*40)
    
    # Simulate high VIX
    vol_mgr._mock_vix_data['spot'] = 35.0  # High VIX
    
    # Reassess risk
    high_risk_profile = vol_mgr.assess_volatility_risk()
    
    if high_risk_profile.risk_assessment.risk_signal in [VolRiskSignal.WARNING, VolRiskSignal.DANGER]:
        print(f"High risk detected! Activating protection...")
        
        protocol = vol_mgr.activate_protection_protocol()
        
        print(f"\nProtection Protocol: {protocol.protocol_id}")
        print(f"  Level: {protocol.protection_level.value}")
        print(f"  Target Vega Reduction: {protocol.target_vega_reduction:.0%}")
        print(f"  Estimated Cost: ${protocol.estimated_cost:,.2f}")
        
        print(f"\nActions:")
        for action in protocol.actions:
            print(f"  - {action.value}")
        
        print(f"\nRequired Hedges:")
        for hedge in protocol.hedges_required:
            print(f"  - {hedge['type']}: {hedge['quantity']} contracts @ {hedge.get('strike', 'market')}")
    
    # Test gamma scalping
    print("\n\n📈 Testing Gamma Scalping")
    print("-"*40)
    
    test_position = {
        'position_id': 'TEST001',
        'underlying_price': 400.0,
        'gamma': 15.0,  # High gamma position
        'delta': 25.0,
        'vega': 50.0
    }
    
    # Execute initial scalp setup
    scalp_result = vol_mgr.execute_gamma_scalping('TEST001', test_position)
    
    if scalp_result:
        print(f"Initial scalp setup complete")
    
    # Simulate price move
    test_position['underlying_price'] = 401.0  # $1 move
    
    scalp_result = vol_mgr.execute_gamma_scalping('TEST001', test_position)
    
    if scalp_result:
        print(f"\nScalp Executed:")
        print(f"  Direction: {scalp_result['direction']}")
        print(f"  Quantity: {scalp_result['quantity']}")
        print(f"  Price: ${scalp_result['price']:.2f}")
        print(f"  Expected P&L: ${scalp_result['expected_pnl']:.2f}")
    
    # Get statistics
    print("\n\n📊 Volatility Risk Statistics")
    print("-"*40)
    
    stats = vol_mgr.get_risk_statistics()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
    
    # Show protection history
    print("\n\n📜 Protection Protocol History")
    print("-"*40)
    
    history = vol_mgr.get_protection_history()
    for protocol in history:
        print(f"\n{protocol['protocol_id']}:")
        print(f"  Activated: {protocol['activation_time']}")
        print(f"  Level: {protocol['protection_level']}")
        print(f"  Status: {protocol['status']}")
        print(f"  Cost: ${protocol['estimated_cost']:,.2f}")
    
    # Stop monitoring
    vol_mgr.stop_monitoring()
    
    print("\n✅ Volatility Risk Manager test completed successfully!")