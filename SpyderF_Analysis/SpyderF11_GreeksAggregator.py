#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderF11_GreeksAggregator.py
Group: F (Analysis)
Purpose: Professional portfolio-level Greeks aggregation and management

Description:
    Advanced Greeks calculation and portfolio aggregation system based on 
    LEAN's institutional-grade Greeks management. Provides real-time portfolio
    Greeks monitoring, delta-neutral management, and risk exposure analysis.

Based on: QuantConnect LEAN Greeks calculation algorithms
Author: Spyder Development Team
Created: 2025-06-23
Version: 1.0 (LEAN-Enhanced)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import math
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy import stats
from scipy.optimize import minimize_scalar

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import OptionType, OrderAction

# ==============================================================================
# CONSTANTS (From LEAN Greeks Algorithms)
# ==============================================================================
# Delta management
DELTA_NEUTRAL_THRESHOLD = 0.05      # Portfolio delta tolerance
DELTA_REBALANCE_TRIGGER = 0.10      # Trigger for delta rebalancing
DELTA_HEDGE_SIZE = 100              # Share size for delta hedging

# Gamma management
GAMMA_RISK_THRESHOLD = 10.0         # Maximum gamma exposure
GAMMA_SCALPING_THRESHOLD = 0.50     # Gamma scalping trigger
GAMMA_HEDGE_FREQUENCY = 15          # Minutes between gamma hedges

# Vega management
VEGA_RISK_THRESHOLD = 50.0          # Maximum vega exposure
VEGA_DIVERSIFICATION_LIMIT = 0.30   # Max vega concentration per expiry

# Theta management
THETA_DECAY_THRESHOLD = -100.0      # Daily theta decay limit
THETA_MONITORING_HOURS = [9, 12, 15] # Hours to monitor theta

# Risk management
MAX_PORTFOLIO_GREEK_EXPOSURE = 1000 # Maximum absolute Greek exposure
GREEKS_UPDATE_FREQUENCY = 60        # Seconds between updates
CORRELATION_LOOKBACK_DAYS = 30      # Days for correlation analysis

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class GreekType(Enum):
    """Greek risk sensitivities"""
    DELTA = "delta"         # Price sensitivity
    GAMMA = "gamma"         # Delta sensitivity
    THETA = "theta"         # Time decay
    VEGA = "vega"          # Volatility sensitivity
    RHO = "rho"            # Interest rate sensitivity
    CHARM = "charm"        # Delta decay
    VANNA = "vanna"        # Vega/spot correlation
    VOLGA = "volga"        # Vega convexity

class RiskLevel(Enum):
    """Risk level classifications"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"

class HedgeAction(Enum):
    """Hedging action types"""
    NO_ACTION = "no_action"
    DELTA_HEDGE = "delta_hedge"
    GAMMA_SCALP = "gamma_scalp"
    VEGA_ADJUST = "vega_adjust"
    PORTFOLIO_REBALANCE = "portfolio_rebalance"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PositionGreeks:
    """Greeks for individual position (LEAN-style)"""
    symbol: str
    position_size: int
    underlying_price: float
    
    # Primary Greeks
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    
    # Advanced Greeks
    charm: float = 0.0      # Delta decay (dDelta/dTime)
    vanna: float = 0.0      # Cross-gamma (dDelta/dVol)
    volga: float = 0.0      # Vega convexity (dVega/dVol)
    
    # Position metrics
    dollar_delta: float = 0.0
    dollar_gamma: float = 0.0
    dollar_theta: float = 0.0
    dollar_vega: float = 0.0
    
    # Risk metrics
    delta_equivalent_shares: int = 0
    gamma_risk_dollars: float = 0.0
    theta_decay_daily: float = 0.0
    
    # Metadata
    expiry: datetime = None
    strike: float = 0.0
    option_type: str = ""
    dte: int = 0
    
    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        self._calculate_dollar_greeks()
        self._calculate_risk_metrics()
    
    def _calculate_dollar_greeks(self):
        """Calculate dollar-equivalent Greeks (LEAN pattern)."""
        multiplier = 100  # Options multiplier
        
        self.dollar_delta = self.delta * self.position_size * multiplier
        self.dollar_gamma = self.gamma * self.position_size * multiplier
        self.dollar_theta = self.theta * self.position_size * multiplier
        self.dollar_vega = self.vega * self.position_size * multiplier
    
    def _calculate_risk_metrics(self):
        """Calculate risk-specific metrics."""
        self.delta_equivalent_shares = int(self.dollar_delta / self.underlying_price) if self.underlying_price > 0 else 0
        self.gamma_risk_dollars = abs(self.dollar_gamma * (self.underlying_price * 0.01))  # 1% move
        self.theta_decay_daily = self.dollar_theta

@dataclass
class PortfolioGreeks:
    """Portfolio-level Greeks aggregation (LEAN-enhanced)"""
    timestamp: datetime
    
    # Aggregate Greeks
    total_delta: float = 0.0
    total_gamma: float = 0.0
    total_theta: float = 0.0
    total_vega: float = 0.0
    total_rho: float = 0.0
    
    # Dollar Greeks
    dollar_delta: float = 0.0
    dollar_gamma: float = 0.0
    dollar_theta: float = 0.0
    dollar_vega: float = 0.0
    
    # Risk metrics
    delta_neutral_ratio: float = 0.0    # How close to delta neutral (0-1)
    gamma_risk_score: float = 0.0       # Gamma risk level (0-100)
    theta_decay_rate: float = 0.0       # Daily theta decay
    vega_concentration: float = 0.0     # Vega concentration risk (0-1)
    
    # Portfolio metrics
    net_delta_exposure: int = 0         # Equivalent shares delta exposure
    daily_theta_pnl: float = 0.0        # Expected daily theta P&L
    vol_sensitivity: float = 0.0        # Portfolio vol sensitivity
    
    # Expiry analysis
    greeks_by_expiry: Dict[str, Dict[str, float]] = field(default_factory=dict)
    expiry_concentration: Dict[str, float] = field(default_factory=dict)
    
    # Risk levels
    overall_risk_level: RiskLevel = RiskLevel.LOW
    risk_components: Dict[str, RiskLevel] = field(default_factory=dict)

@dataclass
class GreeksAlert:
    """Greeks-based risk alert"""
    alert_id: str
    timestamp: datetime
    alert_type: str
    severity: RiskLevel
    greek_type: GreekType
    current_value: float
    threshold_value: float
    recommended_action: HedgeAction
    description: str
    expiry_affected: Optional[str] = None

@dataclass
class HedgeRecommendation:
    """Greeks-based hedge recommendation"""
    recommendation_id: str
    timestamp: datetime
    action_type: HedgeAction
    target_greek: GreekType
    current_exposure: float
    target_exposure: float
    hedge_size: int
    hedge_instrument: str
    expected_cost: float
    risk_reduction: float
    priority: int  # 1-5 (5 = highest)
    reasoning: str

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderF11_GreeksAggregator:
    """
    LEAN-Enhanced Portfolio Greeks Aggregation Engine.
    
    Provides institutional-grade Greeks calculation, portfolio aggregation,
    and risk management based on QuantConnect LEAN's Greeks algorithms.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the Greeks Aggregator."""
        self.config = config or {}
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Portfolio state
        self.position_greeks: Dict[str, PositionGreeks] = {}
        self.portfolio_greeks: Optional[PortfolioGreeks] = None
        self.greeks_history: List[PortfolioGreeks] = []
        
        # Risk monitoring
        self.active_alerts: List[GreeksAlert] = []
        self.hedge_recommendations: List[HedgeRecommendation] = []
        
        # LEAN-style configuration
        self.delta_threshold = self.config.get('delta_threshold', DELTA_NEUTRAL_THRESHOLD)
        self.gamma_threshold = self.config.get('gamma_threshold', GAMMA_RISK_THRESHOLD)
        self.vega_threshold = self.config.get('vega_threshold', VEGA_RISK_THRESHOLD)
        self.theta_threshold = self.config.get('theta_threshold', THETA_DECAY_THRESHOLD)
        
        # Risk management
        self.risk_limits = {
            GreekType.DELTA: self.delta_threshold,
            GreekType.GAMMA: self.gamma_threshold,
            GreekType.VEGA: self.vega_threshold,
            GreekType.THETA: self.theta_threshold
        }
        
        self.logger.info("SpyderF11_GreeksAggregator initialized with LEAN enhancements")
    
    # ==========================================================================
    # GREEKS CALCULATION (LEAN-Enhanced)
    # ==========================================================================
    
    def calculate_position_greeks(self, 
                                position_data: Dict[str, Any],
                                market_data: Dict[str, Any]) -> PositionGreeks:
        """
        Calculate comprehensive Greeks for individual position using LEAN algorithms.
        
        Implements professional Greeks calculation with advanced Greeks
        (Charm, Vanna, Volga) based on LEAN's option pricing models.
        """
        try:
            symbol = position_data.get('symbol', '')
            position_size = position_data.get('quantity', 0)
            strike = position_data.get('strike', 0.0)
            expiry = position_data.get('expiry')
            option_type = position_data.get('option_type', '')
            
            underlying_price = market_data.get('underlying_price', 0.0)
            risk_free_rate = market_data.get('risk_free_rate', 0.05)
            volatility = market_data.get('implied_volatility', 0.20)
            dividend_yield = market_data.get('dividend_yield', 0.0)
            
            if not all([symbol, position_size, strike, expiry, underlying_price]):
                raise ValueError("Missing required position data")
            
            # Calculate time to expiration
            if isinstance(expiry, str):
                expiry = datetime.fromisoformat(expiry)
            
            dte = (expiry - datetime.now()).days
            time_to_expiry = max(dte / 365.0, 1/365.0)  # Minimum 1 day
            
            # LEAN Pattern: Calculate primary Greeks using Black-Scholes
            greeks = self._calculate_black_scholes_greeks(
                underlying_price, strike, time_to_expiry, risk_free_rate,
                volatility, dividend_yield, option_type
            )
            
            # LEAN Pattern: Calculate advanced Greeks
            advanced_greeks = self._calculate_advanced_greeks(
                underlying_price, strike, time_to_expiry, risk_free_rate,
                volatility, dividend_yield, option_type
            )
            
            # Create position Greeks object
            position_greeks = PositionGreeks(
                symbol=symbol,
                position_size=position_size,
                underlying_price=underlying_price,
                delta=greeks['delta'],
                gamma=greeks['gamma'],
                theta=greeks['theta'],
                vega=greeks['vega'],
                rho=greeks['rho'],
                charm=advanced_greeks['charm'],
                vanna=advanced_greeks['vanna'],
                volga=advanced_greeks['volga'],
                expiry=expiry,
                strike=strike,
                option_type=option_type,
                dte=dte
            )
            
            return position_greeks
            
        except Exception as e:
            self.logger.error(f"Position Greeks calculation failed for {symbol}: {e}")
            return self._create_default_position_greeks(position_data)
    
    def _calculate_black_scholes_greeks(self,
                                      S: float, K: float, T: float, r: float,
                                      sigma: float, q: float, option_type: str) -> Dict[str, float]:
        """
        Calculate Black-Scholes Greeks (LEAN algorithm implementation).
        
        Professional implementation of Black-Scholes Greeks calculation
        based on LEAN's option pricing algorithms.
        """
        try:
            # Prevent division by zero and negative values
            S = max(S, 0.01)
            T = max(T, 1/365.0)  # Minimum 1 day
            sigma = max(sigma, 0.01)  # Minimum 1% vol
            
            # Calculate d1 and d2
            d1 = (np.log(S/K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            # Standard normal CDF and PDF
            N_d1 = stats.norm.cdf(d1)
            N_d2 = stats.norm.cdf(d2)
            n_d1 = stats.norm.pdf(d1)
            
            # Calculate Greeks based on option type
            if option_type.upper() in ['CALL', 'C']:
                delta = np.exp(-q * T) * N_d1
                rho = K * T * np.exp(-r * T) * N_d2 / 100  # Per 1% change in rates
            else:  # PUT
                delta = -np.exp(-q * T) * (1 - N_d1)
                rho = -K * T * np.exp(-r * T) * (1 - N_d2) / 100
            
            # Greeks that are the same for calls and puts
            gamma = np.exp(-q * T) * n_d1 / (S * sigma * np.sqrt(T))
            theta = (-(S * n_d1 * sigma * np.exp(-q * T)) / (2 * np.sqrt(T)) 
                    - r * K * np.exp(-r * T) * N_d2 
                    + q * S * np.exp(-q * T) * N_d1) / 365  # Daily theta
            vega = S * np.exp(-q * T) * n_d1 * np.sqrt(T) / 100  # Per 1% change in vol
            
            return {
                'delta': delta,
                'gamma': gamma,
                'theta': theta,
                'vega': vega,
                'rho': rho
            }
            
        except Exception as e:
            self.logger.error(f"Black-Scholes Greeks calculation failed: {e}")
            return {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0, 'rho': 0.0}
    
    def _calculate_advanced_greeks(self,
                                 S: float, K: float, T: float, r: float,
                                 sigma: float, q: float, option_type: str) -> Dict[str, float]:
        """
        Calculate advanced Greeks (Charm, Vanna, Volga) using LEAN patterns.
        
        Second-order and cross-Greeks for sophisticated risk management.
        """
        try:
            # Prevent issues with small values
            T = max(T, 1/365.0)
            sigma = max(sigma, 0.01)
            
            # Calculate d1 and d2
            d1 = (np.log(S/K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            # Standard normal PDF
            n_d1 = stats.norm.pdf(d1)
            N_d1 = stats.norm.cdf(d1)
            
            # Charm (Delta decay) - dDelta/dTime
            if option_type.upper() in ['CALL', 'C']:
                charm = -np.exp(-q * T) * (n_d1 * (2 * (r - q) * T - d2 * sigma * np.sqrt(T)) / 
                                         (2 * T * sigma * np.sqrt(T)) + q * N_d1) / 365
            else:  # PUT
                charm = np.exp(-q * T) * (n_d1 * (2 * (r - q) * T - d2 * sigma * np.sqrt(T)) / 
                                        (2 * T * sigma * np.sqrt(T)) - q * (1 - N_d1)) / 365
            
            # Vanna (Cross-gamma) - dDelta/dVol = dVega/dSpot
            vanna = -np.exp(-q * T) * n_d1 * d2 / sigma / 100
            
            # Volga (Vega convexity) - dVega/dVol
            volga = S * np.exp(-q * T) * n_d1 * np.sqrt(T) * d1 * d2 / sigma / 100
            
            return {
                'charm': charm,
                'vanna': vanna,
                'volga': volga
            }
            
        except Exception as e:
            self.logger.error(f"Advanced Greeks calculation failed: {e}")
            return {'charm': 0.0, 'vanna': 0.0, 'volga': 0.0}
    
    # ==========================================================================
    # PORTFOLIO AGGREGATION (LEAN-Enhanced)
    # ==========================================================================
    
    def aggregate_portfolio_greeks(self, 
                                 positions: List[Dict[str, Any]],
                                 market_data: Dict[str, Any]) -> PortfolioGreeks:
        """
        Aggregate Greeks across entire portfolio using LEAN patterns.
        
        Professional portfolio-level Greeks calculation with risk analysis
        and expiry concentration monitoring.
        """
        try:
            # Calculate Greeks for each position
            position_greeks_list = []
            for position_data in positions:
                pos_greeks = self.calculate_position_greeks(position_data, market_data)
                position_greeks_list.append(pos_greeks)
                
                # Store in position Greeks dictionary
                symbol = position_data.get('symbol', '')
                if symbol:
                    self.position_greeks[symbol] = pos_greeks
            
            # LEAN Pattern: Aggregate across all positions
            total_delta = sum(pg.delta * pg.position_size for pg in position_greeks_list)
            total_gamma = sum(pg.gamma * pg.position_size for pg in position_greeks_list)
            total_theta = sum(pg.theta * pg.position_size for pg in position_greeks_list)
            total_vega = sum(pg.vega * pg.position_size for pg in position_greeks_list)
            total_rho = sum(pg.rho * pg.position_size for pg in position_greeks_list)
            
            # Calculate dollar Greeks
            underlying_price = market_data.get('underlying_price', 500.0)  # Default SPY price
            multiplier = 100  # Options multiplier
            
            dollar_delta = total_delta * multiplier
            dollar_gamma = total_gamma * multiplier
            dollar_theta = total_theta * multiplier
            dollar_vega = total_vega * multiplier
            
            # LEAN Pattern: Calculate risk metrics
            delta_neutral_ratio = self._calculate_delta_neutral_ratio(total_delta)
            gamma_risk_score = self._calculate_gamma_risk_score(total_gamma, underlying_price)
            theta_decay_rate = dollar_theta
            vega_concentration = self._calculate_vega_concentration(position_greeks_list)
            
            # Portfolio exposure metrics
            net_delta_exposure = int(dollar_delta / underlying_price) if underlying_price > 0 else 0
            daily_theta_pnl = dollar_theta
            vol_sensitivity = abs(dollar_vega)
            
            # Expiry analysis
            greeks_by_expiry = self._analyze_greeks_by_expiry(position_greeks_list)
            expiry_concentration = self._calculate_expiry_concentration(position_greeks_list)
            
            # Overall risk assessment
            overall_risk_level = self._assess_overall_risk_level(
                total_delta, total_gamma, total_theta, total_vega
            )
            
            risk_components = {
                'delta': self._assess_greek_risk_level(abs(total_delta), self.delta_threshold),
                'gamma': self._assess_greek_risk_level(abs(total_gamma), self.gamma_threshold),
                'theta': self._assess_greek_risk_level(abs(total_theta), abs(self.theta_threshold)),
                'vega': self._assess_greek_risk_level(abs(total_vega), self.vega_threshold)
            }
            
            # Create portfolio Greeks object
            portfolio_greeks = PortfolioGreeks(
                timestamp=datetime.now(),
                total_delta=total_delta,
                total_gamma=total_gamma,
                total_theta=total_theta,
                total_vega=total_vega,
                total_rho=total_rho,
                dollar_delta=dollar_delta,
                dollar_gamma=dollar_gamma,
                dollar_theta=dollar_theta,
                dollar_vega=dollar_vega,
                delta_neutral_ratio=delta_neutral_ratio,
                gamma_risk_score=gamma_risk_score,
                theta_decay_rate=theta_decay_rate,
                vega_concentration=vega_concentration,
                net_delta_exposure=net_delta_exposure,
                daily_theta_pnl=daily_theta_pnl,
                vol_sensitivity=vol_sensitivity,
                greeks_by_expiry=greeks_by_expiry,
                expiry_concentration=expiry_concentration,
                overall_risk_level=overall_risk_level,
                risk_components=risk_components
            )
            
            # Store portfolio Greeks
            self.portfolio_greeks = portfolio_greeks
            self.greeks_history.append(portfolio_greeks)
            
            # Keep only recent history (last 100 updates)
            if len(self.greeks_history) > 100:
                self.greeks_history = self.greeks_history[-100:]
            
            # Generate alerts and recommendations
            self._generate_greeks_alerts(portfolio_greeks)
            self._generate_hedge_recommendations(portfolio_greeks, market_data)
            
            return portfolio_greeks
            
        except Exception as e:
            self.logger.error(f"Portfolio Greeks aggregation failed: {e}")
            return self._create_default_portfolio_greeks()
    
    # ==========================================================================
    # RISK ANALYSIS (LEAN-Enhanced)
    # ==========================================================================
    
    def _calculate_delta_neutral_ratio(self, total_delta: float) -> float:
        """Calculate how close portfolio is to delta neutral (0-1)."""
        try:
            abs_delta = abs(total_delta)
            if abs_delta <= self.delta_threshold:
                return 1.0  # Perfect delta neutral
            elif abs_delta >= 1.0:
                return 0.0  # Far from delta neutral
            else:
                return 1.0 - (abs_delta / 1.0)  # Linear scaling
        except Exception:
            return 0.5
    
    def _calculate_gamma_risk_score(self, total_gamma: float, underlying_price: float) -> float:
        """Calculate gamma risk score (0-100)."""
        try:
            # Gamma risk = potential P&L from 1% underlying move
            gamma_risk = abs(total_gamma * (underlying_price * 0.01))
            
            # Scale to 0-100
            if gamma_risk <= 100:
                return gamma_risk
            elif gamma_risk >= 1000:
                return 100.0
            else:
                return min(100.0, (gamma_risk / 10))
        except Exception:
            return 50.0
    
    def _calculate_vega_concentration(self, position_greeks_list: List[PositionGreeks]) -> float:
        """Calculate vega concentration risk by expiry."""
        try:
            if not position_greeks_list:
                return 0.0
            
            # Group vega by expiry
            vega_by_expiry = {}
            total_vega = 0.0
            
            for pg in position_greeks_list:
                if pg.expiry:
                    expiry_str = pg.expiry.strftime('%Y-%m-%d')
                    position_vega = pg.vega * pg.position_size
                    vega_by_expiry[expiry_str] = vega_by_expiry.get(expiry_str, 0.0) + position_vega
                    total_vega += abs(position_vega)
            
            if total_vega == 0:
                return 0.0
            
            # Calculate concentration (max single expiry / total)
            max_expiry_vega = max(abs(v) for v in vega_by_expiry.values()) if vega_by_expiry else 0.0
            concentration = max_expiry_vega / total_vega if total_vega > 0 else 0.0
            
            return min(1.0, concentration)
            
        except Exception:
            return 0.5
    
    def _assess_overall_risk_level(self, delta: float, gamma: float, 
                                 theta: float, vega: float) -> RiskLevel:
        """Assess overall portfolio risk level based on Greeks."""
        try:
            risk_scores = []
            
            # Delta risk
            delta_risk = abs(delta) / self.delta_threshold
            risk_scores.append(delta_risk)
            
            # Gamma risk  
            gamma_risk = abs(gamma) / self.gamma_threshold
            risk_scores.append(gamma_risk)
            
            # Theta risk
            theta_risk = abs(theta) / abs(self.theta_threshold)
            risk_scores.append(theta_risk)
            
            # Vega risk
            vega_risk = abs(vega) / self.vega_threshold
            risk_scores.append(vega_risk)
            
            # Overall risk = maximum individual risk
            max_risk = max(risk_scores)
            
            if max_risk <= 0.5:
                return RiskLevel.LOW
            elif max_risk <= 1.0:
                return RiskLevel.MODERATE
            elif max_risk <= 2.0:
                return RiskLevel.HIGH
            else:
                return RiskLevel.EXTREME
                
        except Exception:
            return RiskLevel.MODERATE
    
    def _assess_greek_risk_level(self, value: float, threshold: float) -> RiskLevel:
        """Assess risk level for individual Greek."""
        try:
            ratio = value / threshold if threshold > 0 else 0
            
            if ratio <= 0.5:
                return RiskLevel.LOW
            elif ratio <= 1.0:
                return RiskLevel.MODERATE
            elif ratio <= 2.0:
                return RiskLevel.HIGH
            else:
                return RiskLevel.EXTREME
        except Exception:
            return RiskLevel.MODERATE
    
    # ==========================================================================
    # ALERT GENERATION
    # ==========================================================================
    
    def _generate_greeks_alerts(self, portfolio_greeks: PortfolioGreeks):
        """Generate Greeks-based risk alerts."""
        try:
            self.active_alerts.clear()  # Clear previous alerts
            
            # Delta alert
            if abs(portfolio_greeks.total_delta) > self.delta_threshold:
                alert = GreeksAlert(
                    alert_id=f"DELTA_{datetime.now().strftime('%H%M%S')}",
                    timestamp=datetime.now(),
                    alert_type="Delta Exposure",
                    severity=portfolio_greeks.risk_components.get('delta', RiskLevel.MODERATE),
                    greek_type=GreekType.DELTA,
                    current_value=portfolio_greeks.total_delta,
                    threshold_value=self.delta_threshold,
                    recommended_action=HedgeAction.DELTA_HEDGE,
                    description=f"Portfolio delta {portfolio_greeks.total_delta:.2f} exceeds threshold {self.delta_threshold}"
                )
                self.active_alerts.append(alert)
            
            # Gamma alert
            if abs(portfolio_greeks.total_gamma) > self.gamma_threshold:
                alert = GreeksAlert(
                    alert_id=f"GAMMA_{datetime.now().strftime('%H%M%S')}",
                    timestamp=datetime.now(),
                    alert_type="Gamma Risk",
                    severity=portfolio_greeks.risk_components.get('gamma', RiskLevel.MODERATE),
                    greek_type=GreekType.GAMMA,
                    current_value=portfolio_greeks.total_gamma,
                    threshold_value=self.gamma_threshold,
                    recommended_action=HedgeAction.GAMMA_SCALP,
                    description=f"Portfolio gamma {portfolio_greeks.total_gamma:.2f} exceeds risk threshold"
                )
                self.active_alerts.append(alert)
            
            # Theta alert
            if portfolio_greeks.total_theta < self.theta_threshold:
                alert = GreeksAlert(
                    alert_id=f"THETA_{datetime.now().strftime('%H%M%S')}",
                    timestamp=datetime.now(),
                    alert_type="Theta Decay",
                    severity=portfolio_greeks.risk_components.get('theta', RiskLevel.MODERATE),
                    greek_type=GreekType.THETA,
                    current_value=portfolio_greeks.total_theta,
                    threshold_value=self.theta_threshold,
                    recommended_action=HedgeAction.PORTFOLIO_REBALANCE,
                    description=f"Daily theta decay {portfolio_greeks.total_theta:.2f} exceeds limit"
                )
                self.active_alerts.append(alert)
            
            # Vega alert
            if abs(portfolio_greeks.total_vega) > self.vega_threshold:
                alert = GreeksAlert(
                    alert_id=f"VEGA_{datetime.now().strftime('%H%M%S')}",
                    timestamp=datetime.now(),
                    alert_type="Vega Exposure",
                    severity=portfolio_greeks.risk_components.get('vega', RiskLevel.MODERATE),
                    greek_type=GreekType.VEGA,
                    current_value=portfolio_greeks.total_vega,
                    threshold_value=self.vega_threshold,
                    recommended_action=HedgeAction.VEGA_ADJUST,
                    description=f"Portfolio vega {portfolio_greeks.total_vega:.2f} exceeds risk threshold"
                )
                self.active_alerts.append(alert)
            
        except Exception as e:
            self.logger.error(f"Alert generation failed: {e}")
    
    def _generate_hedge_recommendations(self, portfolio_greeks: PortfolioGreeks, market_data: Dict[str, Any]):
        """Generate hedge recommendations based on portfolio Greeks."""
        try:
            self.hedge_recommendations.clear()
            underlying_price = market_data.get('underlying_price', 500.0)
            
            # Delta hedge recommendation
            if abs(portfolio_greeks.total_delta) > self.delta_threshold:
                hedge_shares = -int(portfolio_greeks.net_delta_exposure)
                hedge_cost = abs(hedge_shares * underlying_price)
                
                recommendation = HedgeRecommendation(
                    recommendation_id=f"DELTA_HEDGE_{datetime.now().strftime('%H%M%S')}",
                    timestamp=datetime.now(),
                    action_type=HedgeAction.DELTA_HEDGE,
                    target_greek=GreekType.DELTA,
                    current_exposure=portfolio_greeks.total_delta,
                    target_exposure=0.0,
                    hedge_size=hedge_shares,
                    hedge_instrument="SPY",
                    expected_cost=hedge_cost,
                    risk_reduction=abs(portfolio_greeks.total_delta),
                    priority=5 if abs(portfolio_greeks.total_delta) > 2 * self.delta_threshold else 3,
                    reasoning=f"Hedge {hedge_shares} shares of SPY to neutralize delta exposure"
                )
                self.hedge_recommendations.append(recommendation)
            
            # Gamma scalping recommendation
            if portfolio_greeks.gamma_risk_score > 70:
                recommendation = HedgeRecommendation(
                    recommendation_id=f"GAMMA_SCALP_{datetime.now().strftime('%H%M%S')}",
                    timestamp=datetime.now(),
                    action_type=HedgeAction.GAMMA_SCALP,
                    target_greek=GreekType.GAMMA,
                    current_exposure=portfolio_greeks.total_gamma,
                    target_exposure=portfolio_greeks.total_gamma * 0.5,
                    hedge_size=int(portfolio_greeks.total_gamma * 50),  # Estimated shares
                    hedge_instrument="SPY",
                    expected_cost=0.0,  # Scalping should be profitable
                    risk_reduction=portfolio_greeks.gamma_risk_score * 0.3,
                    priority=4,
                    reasoning="Consider gamma scalping to reduce gamma risk and generate profits"
                )
                self.hedge_recommendations.append(recommendation)
                
        except Exception as e:
            self.logger.error(f"Hedge recommendation generation failed: {e}")
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _analyze_greeks_by_expiry(self, position_greeks_list: List[PositionGreeks]) -> Dict[str, Dict[str, float]]:
        """Analyze Greeks breakdown by expiration date."""
        try:
            greeks_by_expiry = {}
            
            for pg in position_greeks_list:
                if pg.expiry:
                    expiry_str = pg.expiry.strftime('%Y-%m-%d')
                    if expiry_str not in greeks_by_expiry:
                        greeks_by_expiry[expiry_str] = {
                            'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0
                        }
                    
                    greeks_by_expiry[expiry_str]['delta'] += pg.delta * pg.position_size
                    greeks_by_expiry[expiry_str]['gamma'] += pg.gamma * pg.position_size
                    greeks_by_expiry[expiry_str]['theta'] += pg.theta * pg.position_size
                    greeks_by_expiry[expiry_str]['vega'] += pg.vega * pg.position_size
            
            return greeks_by_expiry
            
        except Exception:
            return {}
    
    def _calculate_expiry_concentration(self, position_greeks_list: List[PositionGreeks]) -> Dict[str, float]:
        """Calculate concentration risk by expiry."""
        try:
            expiry_values = {}
            total_value = 0.0
            
            for pg in position_greeks_list:
                if pg.expiry:
                    expiry_str = pg.expiry.strftime('%Y-%m-%d')
                    position_value = abs(pg.position_size * pg.underlying_price)
                    expiry_values[expiry_str] = expiry_values.get(expiry_str, 0.0) + position_value
                    total_value += position_value
            
            # Calculate concentration percentages
            concentration = {}
            for expiry, value in expiry_values.items():
                concentration[expiry] = (value / total_value) if total_value > 0 else 0.0
            
            return concentration
            
        except Exception:
            return {}
    
    def _create_default_position_greeks(self, position_data: Dict[str, Any]) -> PositionGreeks:
        """Create default position Greeks for error cases."""
        return PositionGreeks(
            symbol=position_data.get('symbol', 'UNKNOWN'),
            position_size=position_data.get('quantity', 0),
            underlying_price=500.0  # Default SPY price
        )
    
    def _create_default_portfolio_greeks(self) -> PortfolioGreeks:
        """Create default portfolio Greeks for error cases."""
        return PortfolioGreeks(
            timestamp=datetime.now(),
            overall_risk_level=RiskLevel.LOW
        )
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    
    def get_portfolio_greeks(self) -> Optional[PortfolioGreeks]:
        """Get current portfolio Greeks."""
        return self.portfolio_greeks
    
    def get_position_greeks(self, symbol: str) -> Optional[PositionGreeks]:
        """Get Greeks for specific position."""
        return self.position_greeks.get(symbol)
    
    def get_active_alerts(self) -> List[GreeksAlert]:
        """Get current active alerts."""
        return self.active_alerts.copy()
    
    def get_hedge_recommendations(self) -> List[HedgeRecommendation]:
        """Get current hedge recommendations."""
        return self.hedge_recommendations.copy()
    
    def get_greeks_history(self, lookback_periods: int = 10) -> List[PortfolioGreeks]:
        """Get historical portfolio Greeks."""
        return self.greeks_history[-lookback_periods:] if self.greeks_history else []
    
    def calculate_portfolio_var(self, confidence_level: float = 0.95) -> Dict[str, float]:
        """Calculate portfolio Value at Risk based on Greeks."""
        try:
            if not self.portfolio_greeks:
                return {'var_1d': 0.0, 'var_1w': 0.0, 'var_1m': 0.0}
            
            # Simplified VaR calculation based on delta and gamma
            underlying_price = 500.0  # Default SPY price
            daily_vol = 0.01  # 1% daily volatility assumption
            
            # Calculate potential P&L from price moves
            z_score = stats.norm.ppf(confidence_level)
            price_move_1d = underlying_price * daily_vol * z_score
            
            # Delta P&L
            delta_pnl = self.portfolio_greeks.dollar_delta * (price_move_1d / underlying_price)
            
            # Gamma P&L (convexity)
            gamma_pnl = 0.5 * self.portfolio_greeks.dollar_gamma * ((price_move_1d / underlying_price) ** 2)
            
            # Total P&L
            total_pnl_1d = abs(delta_pnl + gamma_pnl)
            
            # Scale for different time horizons
            var_1d = total_pnl_1d
            var_1w = total_pnl_1d * math.sqrt(7)
            var_1m = total_pnl_1d * math.sqrt(21)
            
            return {
                'var_1d': var_1d,
                'var_1w': var_1w,
                'var_1m': var_1m,
                'confidence_level': confidence_level
            }
            
        except Exception as e:
            self.logger.error(f"VaR calculation failed: {e}")
            return {'var_1d': 0.0, 'var_1w': 0.0, 'var_1m': 0.0}
    
    def get_greeks_summary(self) -> Dict[str, Any]:
        """Get comprehensive Greeks summary."""
        try:
            if not self.portfolio_greeks:
                return {'error': 'No portfolio Greeks available'}
            
            return {
                'timestamp': self.portfolio_greeks.timestamp.isoformat(),
                'portfolio_greeks': {
                    'delta': self.portfolio_greeks.total_delta,
                    'gamma': self.portfolio_greeks.total_gamma,
                    'theta': self.portfolio_greeks.total_theta,
                    'vega': self.portfolio_greeks.total_vega,
                    'rho': self.portfolio_greeks.total_rho
                },
                'dollar_greeks': {
                    'delta': self.portfolio_greeks.dollar_delta,
                    'gamma': self.portfolio_greeks.dollar_gamma,
                    'theta': self.portfolio_greeks.dollar_theta,
                    'vega': self.portfolio_greeks.dollar_vega
                },
                'risk_metrics': {
                    'delta_neutral_ratio': self.portfolio_greeks.delta_neutral_ratio,
                    'gamma_risk_score': self.portfolio_greeks.gamma_risk_score,
                    'theta_decay_rate': self.portfolio_greeks.theta_decay_rate,
                    'vega_concentration': self.portfolio_greeks.vega_concentration,
                    'overall_risk_level': self.portfolio_greeks.overall_risk_level.value
                },
                'exposure_metrics': {
                    'net_delta_exposure': self.portfolio_greeks.net_delta_exposure,
                    'daily_theta_pnl': self.portfolio_greeks.daily_theta_pnl,
                    'vol_sensitivity': self.portfolio_greeks.vol_sensitivity
                },
                'alerts_count': len(self.active_alerts),
                'recommendations_count': len(self.hedge_recommendations),
                'position_count': len(self.position_greeks)
            }
            
        except Exception as e:
            self.logger.error(f"Greeks summary generation failed: {e}")
            return {'error': str(e)}

# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_greeks_aggregator(config: Dict[str, Any] = None) -> SpyderF11_GreeksAggregator:
    """Factory function to create Greeks Aggregator instance."""
    return SpyderF11_GreeksAggregator(config)

if __name__ == "__main__":
    # Example usage
    aggregator = create_greeks_aggregator()
    print("SpyderF11_GreeksAggregator initialized successfully!")
    print("Available features:")
    print("- Portfolio Greeks aggregation")
    print("- Individual position Greeks")
    print("- Risk alerts and monitoring")
    print("- Hedge recommendations")
    print("- Value at Risk calculations")
    print("- Advanced Greeks (Charm, Vanna, Volga)")
