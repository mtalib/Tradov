#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderN13_MarketImpactModel.py
Group: N (Options Analytics)
Purpose: Advanced market impact modeling for options and equity orders
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 13:00:00

Description:
    This module provides sophisticated market impact models to predict and minimize
    price movement caused by large orders. It implements multiple impact models
    including Almgren-Chriss, square-root, and machine learning-based predictions.
    The module is critical for optimizing execution strategies and preventing
    adverse price movements that can significantly affect trading profitability.

Key Features:
    - Multiple market impact models (linear, square-root, Almgren-Chriss)
    - Options-specific impact modeling with Greeks considerations
    - Temporary vs permanent impact decomposition
    - Cross-asset impact correlation analysis
    - Machine learning impact prediction
    - Real-time impact tracking and calibration
    - Pre-trade impact estimation
    - Post-trade impact analysis
    - Optimal execution trajectory calculation
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import scipy.optimize as optimize
from scipy.stats import norm
import warnings
import logging
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logging.info("⚠️ ML libraries not available - using analytical models only")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False
    import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Market Impact Parameters
DEFAULT_DAILY_VOLUME_FRACTION = 0.05  # 5% of ADV
TEMPORARY_IMPACT_HALFLIFE = 300  # seconds (5 minutes)
PERMANENT_IMPACT_FACTOR = 0.5  # 50% of total impact is permanent

# Model Calibration Parameters
MIN_OBSERVATIONS_FOR_CALIBRATION = 100
CALIBRATION_WINDOW_DAYS = 30
IMPACT_DECAY_RATE = 0.1  # per minute

# Options Impact Multipliers
DELTA_IMPACT_MULTIPLIER = 1.5  # Higher impact for high delta options
GAMMA_IMPACT_MULTIPLIER = 2.0  # Gamma hedging amplifies impact
VEGA_IMPACT_MULTIPLIER = 1.2  # Volatility sensitivity
OTM_IMPACT_REDUCTION = 0.7  # Out-of-money options have less impact

# Risk Limits
MAX_ACCEPTABLE_IMPACT_BPS = 50  # 50 basis points
CRITICAL_IMPACT_BPS = 100  # 100 basis points triggers alert

# ==============================================================================
# ENUMS
# ==============================================================================

class ImpactModel(Enum):
    """Market impact model types"""
    LINEAR = "LINEAR"
    SQUARE_ROOT = "SQUARE_ROOT"
    ALMGREN_CHRISS = "ALMGREN_CHRISS"
    POWER_LAW = "POWER_LAW"
    ML_ENSEMBLE = "ML_ENSEMBLE"
    HYBRID = "HYBRID"

class OrderUrgency(Enum):
    """Order urgency classification"""
    PASSIVE = 1  # Can wait, minimize impact
    NORMAL = 2  # Standard execution
    AGGRESSIVE = 3  # Quick execution needed
    IMMEDIATE = 4  # Execute regardless of impact

class MarketState(Enum):
    """Current market state"""
    NORMAL = "NORMAL"
    STRESSED = "STRESSED"
    VOLATILE = "VOLATILE"
    ILLIQUID = "ILLIQUID"
    CLOSING = "CLOSING"  # Near market close

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class MarketConditions:
    """Current market conditions for impact calculation"""
    symbol: str
    bid: float
    ask: float
    mid_price: float
    spread: float
    spread_bps: float  # Spread in basis points
    volume_30d_avg: float  # 30-day average daily volume
    volume_today: float
    volatility_30d: float  # 30-day realized volatility
    volatility_implied: float  # Current implied volatility
    order_book_depth: float  # Total size on book within 1%
    trade_frequency: float  # Trades per minute
    market_cap: Optional[float] = None
    sector_correlation: float = 0.5

@dataclass
class OrderCharacteristics:
    """Order characteristics for impact calculation"""
    symbol: str
    side: str  # BUY or SELL
    total_quantity: int
    order_type: str  # MARKET, LIMIT, etc.
    urgency: OrderUrgency
    duration_minutes: float  # Expected execution duration
    participation_rate: float  # Target % of volume
    limit_price: Optional[float] = None
    is_option: bool = False
    strike: Optional[float] = None
    expiry: Optional[datetime] = None
    option_type: Optional[str] = None  # CALL or PUT

@dataclass
class OptionGreeks:
    """Option Greeks for impact adjustment"""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float = 0.0

@dataclass
class ImpactEstimate:
    """Market impact estimation results"""
    order_id: str
    symbol: str
    model_used: ImpactModel
    temporary_impact_bps: float  # Basis points
    permanent_impact_bps: float
    total_impact_bps: float
    temporary_impact_dollars: float
    permanent_impact_dollars: float
    total_impact_dollars: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    execution_risk_score: float  # 0-100
    recommended_strategy: str
    optimal_duration_minutes: float
    estimated_slippage: float
    break_even_probability: float

@dataclass
class ImpactDecomposition:
    """Detailed impact decomposition"""
    spread_cost: float
    timing_cost: float
    opportunity_cost: float
    market_impact: float
    information_leakage: float
    total_cost: float

@dataclass
class CalibrationData:
    """Historical data for model calibration"""
    symbol: str
    date: datetime
    order_size: int
    participation_rate: float
    duration_minutes: float
    realized_impact_bps: float
    volatility: float
    spread_bps: float
    volume: float

# ==============================================================================
# MARKET IMPACT MODEL
# ==============================================================================

class MarketImpactModel:
    """
    Advanced market impact modeling system
    Predicts and minimizes price impact of large orders
    """
    
    def __init__(self, model_type: ImpactModel = ImpactModel.HYBRID):
        """Initialize market impact model"""
        self.model_type = model_type
        
        # Logging
        if LOCAL_IMPORTS:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger(__name__)
            
        # Model parameters (calibrated)
        self.linear_coefficient = 0.0001  # 1 bp per 1% of ADV
        self.sqrt_coefficient = 0.001
        self.power_law_exponent = 0.6
        
        # Almgren-Chriss parameters
        self.ac_eta = 2.5e-6  # Temporary impact
        self.ac_gamma = 2.5e-7  # Permanent impact
        self.ac_lambda = 1e-5  # Risk aversion
        
        # ML models
        self.ml_models = {}
        if ML_AVAILABLE:
            self._initialize_ml_models()
            
        # Calibration data storage
        self.calibration_history: List[CalibrationData] = []
        self.impact_cache: Dict[str, ImpactEstimate] = {}
        
        # Statistics
        self.total_estimates = 0
        self.avg_prediction_error = 0.0
        
        self.logger.info(f"✅ MarketImpactModel initialized with {model_type.value}")
        
    # ==========================================================================
    # MAIN IMPACT ESTIMATION
    # ==========================================================================
    
    def estimate_impact(self,
                       order: OrderCharacteristics,
                       market: MarketConditions,
                       greeks: Optional[OptionGreeks] = None) -> ImpactEstimate:
        """
        Estimate market impact for an order
        
        Args:
            order: Order characteristics
            market: Current market conditions
            greeks: Option Greeks if applicable
            
        Returns:
            Comprehensive impact estimate
        """
        self.total_estimates += 1
        
        # Calculate base impact using selected model
        if self.model_type == ImpactModel.LINEAR:
            base_impact = self._linear_impact(order, market)
            
        elif self.model_type == ImpactModel.SQUARE_ROOT:
            base_impact = self._square_root_impact(order, market)
            
        elif self.model_type == ImpactModel.ALMGREN_CHRISS:
            base_impact = self._almgren_chriss_impact(order, market)
            
        elif self.model_type == ImpactModel.POWER_LAW:
            base_impact = self._power_law_impact(order, market)
            
        elif self.model_type == ImpactModel.ML_ENSEMBLE and ML_AVAILABLE:
            base_impact = self._ml_ensemble_impact(order, market)
            
        else:  # HYBRID
            base_impact = self._hybrid_impact(order, market)
            
        # Adjust for options if applicable
        if order.is_option and greeks:
            base_impact = self._adjust_for_options(base_impact, order, greeks)
            
        # Decompose into temporary and permanent
        temporary_impact, permanent_impact = self._decompose_impact(
            base_impact, order, market
        )
        
        # Calculate confidence intervals
        lower_bound, upper_bound = self._calculate_confidence_interval(
            base_impact, market.volatility_30d
        )
        
        # Calculate dollar impact
        reference_price = market.mid_price
        position_value = order.total_quantity * reference_price
        
        # Create impact estimate
        estimate = ImpactEstimate(
            order_id=f"{order.symbol}_{datetime.now().strftime('%H%M%S')}",
            symbol=order.symbol,
            model_used=self.model_type,
            temporary_impact_bps=temporary_impact * 10000,
            permanent_impact_bps=permanent_impact * 10000,
            total_impact_bps=base_impact * 10000,
            temporary_impact_dollars=position_value * temporary_impact,
            permanent_impact_dollars=position_value * permanent_impact,
            total_impact_dollars=position_value * base_impact,
            confidence_interval_lower=lower_bound * 10000,
            confidence_interval_upper=upper_bound * 10000,
            execution_risk_score=self._calculate_execution_risk(base_impact, market),
            recommended_strategy=self._recommend_strategy(base_impact, order),
            optimal_duration_minutes=self._calculate_optimal_duration(order, market),
            estimated_slippage=base_impact * reference_price,
            break_even_probability=self._calculate_break_even_prob(base_impact, market)
        )
        
        # Cache estimate
        self.impact_cache[estimate.order_id] = estimate
        
        # Log if impact is significant
        if estimate.total_impact_bps > MAX_ACCEPTABLE_IMPACT_BPS:
            self.logger.warning(
                f"⚠️ High impact estimated: {estimate.total_impact_bps:.1f} bps for {order.symbol}"
            )
            
        return estimate
        
    # ==========================================================================
    # IMPACT MODELS
    # ==========================================================================
    
    def _linear_impact(self, order: OrderCharacteristics, market: MarketConditions) -> float:
        """
        Linear market impact model
        Impact = β * (Order Size / ADV)
        """
        size_ratio = order.total_quantity / market.volume_30d_avg
        impact = self.linear_coefficient * size_ratio
        
        # Adjust for spread
        spread_adjustment = market.spread_bps / 10000
        impact += spread_adjustment * 0.5  # Half spread cost
        
        return impact
        
    def _square_root_impact(self, order: OrderCharacteristics, market: MarketConditions) -> float:
        """
        Square-root market impact model
        Impact = α * σ * sqrt(Q/V)
        """
        size_ratio = order.total_quantity / market.volume_30d_avg
        volatility = market.volatility_30d
        
        impact = self.sqrt_coefficient * volatility * math.sqrt(size_ratio)
        
        # Participation rate adjustment
        if order.participation_rate > 0.1:  # More than 10% participation
            impact *= (1 + (order.participation_rate - 0.1) * 2)
            
        return impact
        
    def _almgren_chriss_impact(self, order: OrderCharacteristics, market: MarketConditions) -> float:
        """
        Almgren-Chriss optimal execution model
        Minimizes combination of impact and risk
        """
        # Parameters
        X = order.total_quantity  # Total shares
        T = order.duration_minutes / 1440  # Convert to days
        sigma = market.volatility_30d
        
        # Daily volume
        V = market.volume_30d_avg
        
        # Temporary impact function
        def h(v):
            return self.ac_eta * v
            
        # Permanent impact function
        def g(v):
            return self.ac_gamma * v
            
        # Calculate optimal trajectory
        n_slices = max(1, int(order.duration_minutes / 5))  # 5-minute slices
        tau = T / n_slices
        
        # Risk aversion parameter
        kappa = self.ac_lambda * sigma * math.sqrt(tau)
        
        # Optimal trading rate
        trading_rate = X / T
        
        # Total impact
        permanent = g(X)
        temporary = h(trading_rate) * math.sqrt(X / V)
        
        total_impact = permanent + temporary
        
        return total_impact
        
    def _power_law_impact(self, order: OrderCharacteristics, market: MarketConditions) -> float:
        """
        Power law impact model
        Impact = α * (Q/V)^β
        """
        size_ratio = order.total_quantity / market.volume_30d_avg
        impact = self.sqrt_coefficient * (size_ratio ** self.power_law_exponent)
        
        # Adjust for market conditions
        if market.volatility_30d > 0.02:  # High volatility
            impact *= 1.2
            
        return impact
        
    def _ml_ensemble_impact(self, order: OrderCharacteristics, market: MarketConditions) -> float:
        """
        Machine learning ensemble impact prediction
        """
        if not ML_AVAILABLE or order.symbol not in self.ml_models:
            # Fallback to hybrid model
            return self._hybrid_impact(order, market)
            
        # Prepare features
        features = self._prepare_ml_features(order, market)
        
        # Get predictions from ensemble
        model = self.ml_models[order.symbol]
        impact_pred = model.predict(features.reshape(1, -1))[0]
        
        # Ensure reasonable bounds
        impact_pred = max(0, min(impact_pred, 0.05))  # Cap at 5%
        
        return impact_pred
        
    def _hybrid_impact(self, order: OrderCharacteristics, market: MarketConditions) -> float:
        """
        Hybrid model combining multiple approaches
        """
        # Get predictions from different models
        linear = self._linear_impact(order, market)
        sqrt = self._square_root_impact(order, market)
        almgren = self._almgren_chriss_impact(order, market)
        
        # Weighted average based on market conditions
        if market.volatility_30d > 0.025:  # High volatility
            # Weight Almgren-Chriss more
            weights = [0.2, 0.3, 0.5]
        elif market.spread_bps > 10:  # Wide spread
            # Weight linear more
            weights = [0.5, 0.3, 0.2]
        else:  # Normal conditions
            weights = [0.33, 0.34, 0.33]
            
        hybrid_impact = (
            weights[0] * linear +
            weights[1] * sqrt +
            weights[2] * almgren
        )
        
        return hybrid_impact
        
    # ==========================================================================
    # OPTIONS ADJUSTMENTS
    # ==========================================================================
    
    def _adjust_for_options(self,
                           base_impact: float,
                           order: OrderCharacteristics,
                           greeks: OptionGreeks) -> float:
        """
        Adjust impact for options based on Greeks
        """
        adjustment_factor = 1.0
        
        # Delta adjustment - higher delta means more stock-like
        delta_adj = 1 + (abs(greeks.delta) - 0.5) * DELTA_IMPACT_MULTIPLIER
        adjustment_factor *= delta_adj
        
        # Gamma adjustment - hedging flows amplify impact
        if greeks.gamma > 0.01:  # Significant gamma
            gamma_adj = 1 + greeks.gamma * GAMMA_IMPACT_MULTIPLIER
            adjustment_factor *= gamma_adj
            
        # Vega adjustment - volatility sensitivity
        if abs(greeks.vega) > 0.5:
            vega_adj = 1 + abs(greeks.vega) * 0.01 * VEGA_IMPACT_MULTIPLIER
            adjustment_factor *= vega_adj
            
        # OTM adjustment - out-of-money has less impact
        if order.strike:
            current_price = base_impact  # This would use actual price
            moneyness = order.strike / current_price
            
            if (order.option_type == "CALL" and moneyness > 1.05) or \
               (order.option_type == "PUT" and moneyness < 0.95):
                adjustment_factor *= OTM_IMPACT_REDUCTION
                
        adjusted_impact = base_impact * adjustment_factor
        
        return adjusted_impact
        
    # ==========================================================================
    # IMPACT DECOMPOSITION
    # ==========================================================================
    
    def _decompose_impact(self,
                         total_impact: float,
                         order: OrderCharacteristics,
                         market: MarketConditions) -> Tuple[float, float]:
        """
        Decompose total impact into temporary and permanent components
        """
        # Factors affecting decomposition
        urgency_factor = order.urgency.value / 4.0
        participation_factor = min(1, order.participation_rate / 0.2)
        
        # Higher urgency = more temporary impact
        temp_ratio = 0.5 + (urgency_factor * 0.3) + (participation_factor * 0.2)
        temp_ratio = min(0.8, temp_ratio)  # Cap at 80% temporary
        
        temporary = total_impact * temp_ratio
        permanent = total_impact * (1 - temp_ratio)
        
        # Apply decay to temporary impact
        decay_factor = math.exp(-IMPACT_DECAY_RATE * order.duration_minutes)
        temporary *= (1 - decay_factor)
        
        return temporary, permanent
        
    def calculate_impact_trajectory(self,
                                   order: OrderCharacteristics,
                                   market: MarketConditions,
                                   n_points: int = 20) -> pd.DataFrame:
        """
        Calculate expected impact trajectory over execution period
        """
        timestamps = []
        cumulative_impact = []
        instantaneous_impact = []
        
        time_step = order.duration_minutes / n_points
        
        for i in range(n_points + 1):
            t = i * time_step
            
            # Cumulative execution fraction
            exec_fraction = (i / n_points)
            
            # Instantaneous impact (decreases as order completes)
            inst_impact = self._instantaneous_impact(
                order.total_quantity * (1 - exec_fraction),
                market
            )
            
            # Cumulative impact with decay
            cum_impact = self._cumulative_impact(
                order.total_quantity * exec_fraction,
                t,
                market
            )
            
            timestamps.append(t)
            instantaneous_impact.append(inst_impact * 10000)  # Convert to bps
            cumulative_impact.append(cum_impact * 10000)
            
        return pd.DataFrame({
            'time_minutes': timestamps,
            'instantaneous_impact_bps': instantaneous_impact,
            'cumulative_impact_bps': cumulative_impact
        })
        
    def _instantaneous_impact(self, remaining_quantity: int, market: MarketConditions) -> float:
        """Calculate instantaneous impact for remaining quantity"""
        if remaining_quantity == 0:
            return 0
            
        size_ratio = remaining_quantity / market.volume_30d_avg
        return self.sqrt_coefficient * math.sqrt(size_ratio) * market.volatility_30d
        
    def _cumulative_impact(self, executed_quantity: int, time_minutes: float, 
                          market: MarketConditions) -> float:
        """Calculate cumulative impact with decay"""
        if executed_quantity == 0:
            return 0
            
        size_ratio = executed_quantity / market.volume_30d_avg
        base_impact = self.sqrt_coefficient * math.sqrt(size_ratio) * market.volatility_30d
        
        # Apply decay
        decay = math.exp(-time_minutes / (TEMPORARY_IMPACT_HALFLIFE / 60))
        
        return base_impact * (PERMANENT_IMPACT_FACTOR + 
                             (1 - PERMANENT_IMPACT_FACTOR) * decay)
        
    # ==========================================================================
    # OPTIMIZATION
    # ==========================================================================
    
    def optimize_execution_schedule(self,
                                   order: OrderCharacteristics,
                                   market: MarketConditions,
                                   risk_aversion: float = 0.5) -> Dict[str, Any]:
        """
        Optimize execution schedule to minimize cost and risk
        """
        # Define objective function (cost + risk)
        def objective(schedule):
            cost = self._calculate_schedule_cost(schedule, order, market)
            risk = self._calculate_schedule_risk(schedule, order, market)
            return cost + risk_aversion * risk
            
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - order.total_quantity}  # Sum to total
        ]
        
        # Bounds (each slice between 0 and total)
        n_slices = max(5, min(20, int(order.duration_minutes / 5)))
        bounds = [(0, order.total_quantity) for _ in range(n_slices)]
        
        # Initial guess (uniform distribution)
        x0 = np.full(n_slices, order.total_quantity / n_slices)
        
        # Optimize
        result = optimize.minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            optimal_schedule = result.x
            optimal_cost = self._calculate_schedule_cost(optimal_schedule, order, market)
            optimal_risk = self._calculate_schedule_risk(optimal_schedule, order, market)
            
            return {
                'schedule': optimal_schedule.tolist(),
                'total_cost_bps': optimal_cost * 10000,
                'risk_bps': optimal_risk * 10000,
                'slices': n_slices,
                'slice_duration_minutes': order.duration_minutes / n_slices
            }
        else:
            # Fallback to uniform
            return {
                'schedule': x0.tolist(),
                'total_cost_bps': 0,
                'risk_bps': 0,
                'slices': n_slices,
                'slice_duration_minutes': order.duration_minutes / n_slices
            }
            
    def _calculate_schedule_cost(self, schedule: np.ndarray, 
                                order: OrderCharacteristics,
                                market: MarketConditions) -> float:
        """Calculate total cost for execution schedule"""
        total_cost = 0
        cumulative_executed = 0
        
        for i, slice_size in enumerate(schedule):
            if slice_size > 0:
                # Impact cost for this slice
                slice_order = OrderCharacteristics(
                    symbol=order.symbol,
                    side=order.side,
                    total_quantity=int(slice_size),
                    order_type=order.order_type,
                    urgency=order.urgency,
                    duration_minutes=order.duration_minutes / len(schedule),
                    participation_rate=order.participation_rate
                )
                
                impact = self._square_root_impact(slice_order, market)
                total_cost += impact * slice_size / order.total_quantity
                
            cumulative_executed += slice_size
            
        return total_cost
        
    def _calculate_schedule_risk(self, schedule: np.ndarray,
                                order: OrderCharacteristics,
                                market: MarketConditions) -> float:
        """Calculate execution risk for schedule"""
        # Risk from unexecuted portion
        variance = 0
        remaining = order.total_quantity
        time_per_slice = order.duration_minutes / len(schedule)
        
        for i, slice_size in enumerate(schedule):
            remaining -= slice_size
            time_remaining = (len(schedule) - i - 1) * time_per_slice
            
            # Variance of remaining position
            if remaining > 0 and time_remaining > 0:
                slice_variance = (remaining ** 2) * (market.volatility_30d ** 2) * \
                               (time_remaining / 1440)  # Convert to daily
                variance += slice_variance
                
        risk = math.sqrt(variance) / order.total_quantity
        return risk
        
    # ==========================================================================
    # ANALYTICS AND HELPERS
    # ==========================================================================
    
    def _calculate_confidence_interval(self, 
                                      base_impact: float,
                                      volatility: float,
                                      confidence: float = 0.95) -> Tuple[float, float]:
        """Calculate confidence interval for impact estimate"""
        # Standard error based on volatility
        std_error = base_impact * volatility * 0.5
        
        # Z-score for confidence level
        z_score = norm.ppf((1 + confidence) / 2)
        
        lower = base_impact - z_score * std_error
        upper = base_impact + z_score * std_error
        
        return max(0, lower), upper
        
    def _calculate_execution_risk(self, impact: float, market: MarketConditions) -> float:
        """Calculate execution risk score (0-100)"""
        risk_score = 0
        
        # Impact component (0-40 points)
        impact_bps = impact * 10000
        if impact_bps < 10:
            impact_score = 0
        elif impact_bps < 30:
            impact_score = 20
        elif impact_bps < 50:
            impact_score = 30
        else:
            impact_score = 40
            
        risk_score += impact_score
        
        # Spread component (0-30 points)
        if market.spread_bps < 5:
            spread_score = 0
        elif market.spread_bps < 10:
            spread_score = 15
        else:
            spread_score = 30
            
        risk_score += spread_score
        
        # Volatility component (0-30 points)
        if market.volatility_30d < 0.01:
            vol_score = 0
        elif market.volatility_30d < 0.02:
            vol_score = 15
        else:
            vol_score = 30
            
        risk_score += vol_score
        
        return min(100, risk_score)
        
    def _recommend_strategy(self, impact: float, order: OrderCharacteristics) -> str:
        """Recommend execution strategy based on impact"""
        impact_bps = impact * 10000
        
        if impact_bps < 5:
            return "AGGRESSIVE - Low impact expected, execute quickly"
        elif impact_bps < 20:
            if order.urgency == OrderUrgency.IMMEDIATE:
                return "ADAPTIVE - Balance speed and impact"
            else:
                return "VWAP - Match market volume pattern"
        elif impact_bps < 50:
            return "ICEBERG - Hide order size, execute patiently"
        else:
            return "PASSIVE - Minimize impact, extend duration"
            
    def _calculate_optimal_duration(self,
                                   order: OrderCharacteristics,
                                   market: MarketConditions) -> float:
        """Calculate optimal execution duration"""
        # Base on participation rate target
        target_participation = 0.1  # 10% of volume
        
        # Daily volume in minutes (6.5 hour trading day)
        volume_per_minute = market.volume_30d_avg / 390
        
        # Minutes needed at target participation
        optimal_minutes = order.total_quantity / (volume_per_minute * target_participation)
        
        # Adjust for urgency
        urgency_multiplier = 2.0 - (order.urgency.value - 1) * 0.3
        optimal_minutes *= urgency_multiplier
        
        # Practical bounds
        return max(5, min(optimal_minutes, 390))  # Between 5 min and full day
        
    def _calculate_break_even_prob(self, impact: float, market: MarketConditions) -> float:
        """Calculate probability that price moves favorably to offset impact"""
        # Simplified model: probability that favorable drift exceeds impact
        drift_per_day = 0.0  # Assume no drift
        vol_per_day = market.volatility_30d
        
        # Standardize impact
        z_score = (impact - drift_per_day) / vol_per_day
        
        # Probability of favorable move
        prob = 1 - norm.cdf(z_score)
        
        return prob
        
    # ==========================================================================
    # ML MODEL MANAGEMENT
    # ==========================================================================
    
    def _initialize_ml_models(self):
        """Initialize machine learning models"""
        if not ML_AVAILABLE:
            return
            
        # Create ensemble models for common symbols
        symbols = ['SPY', 'QQQ', 'IWM']
        
        for symbol in symbols:
            # Random Forest for robustness
            rf = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            
            # Gradient Boosting for accuracy
            gb = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
            
            self.ml_models[symbol] = rf  # Use RF as primary
            
        self.logger.info(f"✅ ML models initialized for {len(self.ml_models)} symbols")
        
    def _prepare_ml_features(self,
                            order: OrderCharacteristics,
                            market: MarketConditions) -> np.ndarray:
        """Prepare features for ML model"""
        features = [
            order.total_quantity / market.volume_30d_avg,  # Size ratio
            order.participation_rate,
            order.duration_minutes,
            order.urgency.value / 4.0,
            market.spread_bps,
            market.volatility_30d,
            market.volatility_implied,
            market.order_book_depth / market.volume_30d_avg,
            market.trade_frequency,
            1 if order.side == "BUY" else -1
        ]
        
        return np.array(features)
        
    def train_ml_model(self, symbol: str, training_data: List[CalibrationData]):
        """Train ML model with historical data"""
        if not ML_AVAILABLE or len(training_data) < MIN_OBSERVATIONS_FOR_CALIBRATION:
            return
            
        # Prepare training data
        X = []
        y = []
        
        for data in training_data:
            features = [
                data.order_size / data.volume,
                data.participation_rate,
                data.duration_minutes,
                data.spread_bps,
                data.volatility
            ]
            X.append(features)
            y.append(data.realized_impact_bps / 10000)  # Convert to decimal
            
        X = np.array(X)
        y = np.array(y)
        
        # Train model
        if symbol not in self.ml_models:
            self.ml_models[symbol] = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            
        self.ml_models[symbol].fit(X, y)
        
        self.logger.info(f"✅ ML model trained for {symbol} with {len(training_data)} samples")
        
    # ==========================================================================
    # CALIBRATION
    # ==========================================================================
    
    def calibrate_model(self, historical_data: List[CalibrationData]):
        """Calibrate model parameters using historical data"""
        if len(historical_data) < MIN_OBSERVATIONS_FOR_CALIBRATION:
            self.logger.warning("Insufficient data for calibration")
            return
            
        # Group by symbol
        symbol_data = {}
        for data in historical_data:
            if data.symbol not in symbol_data:
                symbol_data[data.symbol] = []
            symbol_data[data.symbol].append(data)
            
        # Calibrate per symbol
        for symbol, data_points in symbol_data.items():
            self._calibrate_symbol_parameters(symbol, data_points)
            
            # Train ML model if available
            if ML_AVAILABLE:
                self.train_ml_model(symbol, data_points)
                
        self.logger.info(f"✅ Model calibrated with {len(historical_data)} data points")
        
    def _calibrate_symbol_parameters(self, symbol: str, data_points: List[CalibrationData]):
        """Calibrate parameters for specific symbol"""
        # Calculate average prediction error
        errors = []
        
        for data in data_points:
            # Create order characteristics from historical data
            order = OrderCharacteristics(
                symbol=symbol,
                side="BUY",
                total_quantity=data.order_size,
                order_type="LIMIT",
                urgency=OrderUrgency.NORMAL,
                duration_minutes=data.duration_minutes,
                participation_rate=data.participation_rate
            )
            
            # Create market conditions
            market = MarketConditions(
                symbol=symbol,
                bid=100,  # Placeholder
                ask=100.1,
                mid_price=100.05,
                spread=0.1,
                spread_bps=data.spread_bps,
                volume_30d_avg=data.volume,
                volume_today=data.volume,
                volatility_30d=data.volatility,
                volatility_implied=data.volatility,
                order_book_depth=data.volume * 0.01,
                trade_frequency=100
            )
            
            # Estimate impact
            estimate = self.estimate_impact(order, market)
            
            # Calculate error
            predicted = estimate.total_impact_bps
            actual = data.realized_impact_bps
            error = abs(predicted - actual) / actual if actual > 0 else 0
            errors.append(error)
            
        # Update average error
        self.avg_prediction_error = np.mean(errors) if errors else 0
        
        # Adjust coefficients based on errors
        if self.avg_prediction_error > 0.2:  # More than 20% error
            # Increase coefficients if underestimating
            avg_ratio = np.mean([d.realized_impact_bps for d in data_points]) / \
                       np.mean([self.estimate_impact(
                           OrderCharacteristics(
                               symbol=symbol,
                               side="BUY",
                               total_quantity=d.order_size,
                               order_type="LIMIT",
                               urgency=OrderUrgency.NORMAL,
                               duration_minutes=d.duration_minutes,
                               participation_rate=d.participation_rate
                           ),
                           MarketConditions(
                               symbol=symbol,
                               bid=100,
                               ask=100.1,
                               mid_price=100.05,
                               spread=0.1,
                               spread_bps=d.spread_bps,
                               volume_30d_avg=d.volume,
                               volume_today=d.volume,
                               volatility_30d=d.volatility,
                               volatility_implied=d.volatility,
                               order_book_depth=d.volume * 0.01,
                               trade_frequency=100
                           )
                       ).total_impact_bps for d in data_points])
            
            self.linear_coefficient *= avg_ratio
            self.sqrt_coefficient *= avg_ratio
            
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    
    def get_model_statistics(self) -> Dict[str, Any]:
        """Get model performance statistics"""
        return {
            'model_type': self.model_type.value,
            'total_estimates': self.total_estimates,
            'avg_prediction_error': self.avg_prediction_error,
            'calibration_samples': len(self.calibration_history),
            'ml_models_available': len(self.ml_models),
            'cached_estimates': len(self.impact_cache)
        }
        
    def clear_cache(self):
        """Clear impact estimate cache"""
        self.impact_cache.clear()
        self.logger.info("Impact cache cleared")

    # --------------------------------------------------------------------------
    # STABLE-BASELINES3: RL OPTIMAL EXECUTION TRAJECTORY
    # --------------------------------------------------------------------------

    def create_impact_rl_env(self):
        """
        Create an RL environment for optimal execution trajectory.

        The agent learns to minimize total market impact by choosing
        execution speed and order aggressiveness over time.

        Returns:
            gym.Env instance for SB3 training.
        """
        try:
            import gymnasium as gym
            from gymnasium import spaces
        except ImportError:
            try:
                import gym
                from gym import spaces
            except ImportError:
                self.logger.warning("gym/gymnasium not installed")
                return None

        import numpy as _np

        class MarketImpactEnvironment(gym.Env):
            """
            RL environment for market impact minimization.

            Observation: [remaining_shares_pct, urgency, current_spread,
                         realized_impact, volume_participation, price_momentum,
                         time_elapsed_pct, volatility]
            Action: Continuous [execution_rate] in [0, 1]
            Reward: -permanent_impact - temporary_impact - opportunity_cost
            """
            metadata = {'render_modes': []}

            def __init__(self):
                super().__init__()
                self.observation_space = spaces.Box(
                    low=-5.0, high=5.0, shape=(8,), dtype=_np.float32)
                self.action_space = spaces.Box(
                    low=0.0, high=1.0, shape=(1,), dtype=_np.float32)
                self.step_count = 0
                self.max_steps = 78
                self.total_impact = 0

            def reset(self, seed=None, options=None):
                super().reset(seed=seed)
                self.step_count = 0
                self.remaining = 1.0
                self.total_impact = 0
                self._state = _np.array([
                    1.0,                           # remaining_shares
                    _np.random.uniform(0.3, 1.0),  # urgency
                    _np.random.uniform(0.01, 0.05), # spread
                    0.0,                           # realized_impact
                    0.0,                           # volume_participation
                    _np.random.uniform(-0.3, 0.3), # momentum
                    0.0,                           # time_elapsed
                    _np.random.uniform(0.1, 0.4),  # volatility
                ], dtype=_np.float32)
                return self._state, {}

            def step(self, action):
                self.step_count += 1
                rate = float(action[0])
                executed = min(rate * 0.1, self.remaining)
                self.remaining -= executed

                # Almgren-Chriss impact model
                permanent = 0.5 * executed * self._state[7]  # sigma * executed
                temporary = executed * self._state[2] * (1 + 3 * rate)
                opportunity = self.remaining * self._state[7] * 0.005

                self.total_impact += permanent + temporary
                reward = -(permanent + temporary + opportunity) * 100

                if self.remaining <= 0.01:
                    reward += 20  # completion bonus

                self._state[0] = self.remaining
                self._state[3] = self.total_impact
                self._state[4] = rate
                self._state[6] = self.step_count / self.max_steps
                self._state[2] = _np.clip(
                    self._state[2] + _np.random.normal(0, 0.002), 0.005, 0.1)

                done = self.step_count >= self.max_steps or self.remaining <= 0.01
                return self._state.copy(), float(reward), done, False, {}

        return MarketImpactEnvironment()

    def train_impact_policy(self, total_timesteps: int = 50000) -> Optional[Any]:
        """
        Train a SAC policy for optimal execution trajectory.

        Args:
            total_timesteps: Training steps.

        Returns:
            Trained SB3 model or None.
        """
        env = self.create_impact_rl_env()
        if env is None:
            return None

        try:
            from stable_baselines3 import SAC
            model = SAC('MlpPolicy', env, verbose=0,
                       learning_rate=3e-4, buffer_size=100000)
            model.learn(total_timesteps=total_timesteps)
            self.logger.info(f"Impact RL policy trained (SAC): {total_timesteps} steps")
            return model
        except ImportError:
            self.logger.warning("stable-baselines3 not installed")
            return None

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_impact_model(model_type: ImpactModel = ImpactModel.HYBRID) -> MarketImpactModel:
    """Factory function to create market impact model"""
    return MarketImpactModel(model_type)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("MARKET IMPACT MODEL TEST")
    print("=" * 80)
    
    # Create model
    model = create_impact_model(ImpactModel.HYBRID)
    
    # Test market conditions
    market = MarketConditions(
        symbol="SPY",
        bid=585.45,
        ask=585.55,
        mid_price=585.50,
        spread=0.10,
        spread_bps=1.71,  # 0.10/585.50 * 10000
        volume_30d_avg=75_000_000,
        volume_today=80_000_000,
        volatility_30d=0.012,  # 1.2% daily vol
        volatility_implied=0.015,
        order_book_depth=500_000,
        trade_frequency=100,  # trades per minute
        market_cap=500_000_000_000
    )
    
    # Test orders with different characteristics
    test_orders = [
        OrderCharacteristics(
            symbol="SPY",
            side="BUY",
            total_quantity=100_000,
            order_type="LIMIT",
            urgency=OrderUrgency.NORMAL,
            duration_minutes=60,
            participation_rate=0.10
        ),
        OrderCharacteristics(
            symbol="SPY",
            side="SELL",
            total_quantity=500_000,
            order_type="MARKET",
            urgency=OrderUrgency.AGGRESSIVE,
            duration_minutes=30,
            participation_rate=0.20
        ),
        OrderCharacteristics(
            symbol="SPY",
            side="BUY",
            total_quantity=1_000_000,
            order_type="LIMIT",
            urgency=OrderUrgency.PASSIVE,
            duration_minutes=180,
            participation_rate=0.05
        )
    ]
    
    print("\n📊 Market Impact Estimates:\n")
    
    for i, order in enumerate(test_orders, 1):
        estimate = model.estimate_impact(order, market)
        
        print(f"Order {i}: {order.total_quantity:,} shares, {order.urgency.value} urgency")
        print(f"  Model: {estimate.model_used.value}")
        print(f"  Total Impact: {estimate.total_impact_bps:.1f} bps "
              f"(${estimate.total_impact_dollars:,.0f})")
        print(f"  Temporary: {estimate.temporary_impact_bps:.1f} bps")
        print(f"  Permanent: {estimate.permanent_impact_bps:.1f} bps")
        print(f"  Confidence: [{estimate.confidence_interval_lower:.1f}, "
              f"{estimate.confidence_interval_upper:.1f}] bps")
        print(f"  Execution Risk: {estimate.execution_risk_score:.0f}/100")
        print(f"  Strategy: {estimate.recommended_strategy}")
        print(f"  Optimal Duration: {estimate.optimal_duration_minutes:.0f} minutes")
        print()
    
    # Test trajectory calculation
    print("\n📈 Impact Trajectory for Order 1:")
    trajectory = model.calculate_impact_trajectory(test_orders[0], market, n_points=5)
    print(trajectory.to_string())
    
    # Test optimization
    print("\n🎯 Optimal Execution Schedule for Order 2:")
    optimal = model.optimize_execution_schedule(test_orders[1], market, risk_aversion=0.5)
    print(f"  Slices: {optimal['slices']}")
    print(f"  Cost: {optimal['total_cost_bps']:.1f} bps")
    print(f"  Risk: {optimal['risk_bps']:.1f} bps")
    print(f"  Schedule: {[f'{s:,.0f}' for s in optimal['schedule'][:5]]}...")
    
    # Get statistics
    stats = model.get_model_statistics()
    print("\n📊 Model Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n✅ Market impact model test completed")
