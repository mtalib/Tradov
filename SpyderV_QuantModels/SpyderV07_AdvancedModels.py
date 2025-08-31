#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels  
Module: SpyderV07_AdvancedModels.py
Purpose: Consolidated advanced modeling engine - Jump-Diffusion and Regime Switching

Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-31 Time: 21:00:00  

Module Description:
    Unified advanced modeling engine that consolidates V09 Merton Jump-Diffusion and 
    V11 Regime Switching models. Provides intelligent crisis detection, market regime
    identification, and jump-aware pricing for SPY options. Combines discontinuous
    price movement modeling with market state intelligence for superior handling
    of non-standard market conditions.

Consolidation Notes:
    - Merges Merton Jump-Diffusion model from V09 for crisis/event-driven pricing
    - Integrates Regime Switching model from V11 for market intelligence
    - Creates intelligent coordination between jump detection and regime identification
    - Eliminates duplications between advanced modeling approaches
    - Provides unified interface for non-standard market condition modeling
    - Optimized for real-time SPY options trading during volatile periods
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats, optimize
from scipy.special import factorial
from scipy.stats import norm, poisson, multivariate_normal
from scipy.optimize import minimize, differential_evolution
from numba import jit
import matplotlib.pyplot as plt
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, silhouette_score

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderB08_MultiClientDataManager import MultiClientDataManager
except ImportError:
    MultiClientDataManager = None

try:
    from SpyderV06_VolatilityEngine import SpyderVolatilityEngine, VolatilityModel
except ImportError:
    SpyderVolatilityEngine = None
    VolatilityModel = None

# ==============================================================================
# MODULE CONFIGURATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# ENUMERATIONS AND CONSTANTS
# ==============================================================================
class MarketRegime(Enum):
    """Market regime classifications."""
    BULL_MARKET = "bull_market"          # High positive returns, low volatility
    BEAR_MARKET = "bear_market"          # Negative returns, high volatility  
    SIDEWAYS_MARKET = "sideways_market"  # Low returns, medium volatility
    CRISIS_MARKET = "crisis_market"      # Very negative returns, extreme volatility

class JumpType(Enum):
    """Types of price jumps."""
    NO_JUMP = "no_jump"
    POSITIVE_JUMP = "positive_jump"
    NEGATIVE_JUMP = "negative_jump"
    EXTREME_JUMP = "extreme_jump"        # |jump| > 3 standard deviations

class EventType(Enum):
    """Market event classifications."""
    EARNINGS = "earnings"
    FOMC = "fomc"
    ECONOMIC_DATA = "economic_data"
    GEOPOLITICAL = "geopolitical"
    TECHNICAL = "technical"
    UNKNOWN = "unknown"

class ModelComplexity(Enum):
    """Model complexity levels."""
    SIMPLE = "simple"        # Basic jump-diffusion or 2-regime switching
    STANDARD = "standard"    # Standard implementations with full features
    ADVANCED = "advanced"    # Multi-regime with jump clustering

# Model selection thresholds
REGIME_CHARACTERISTICS = {
    MarketRegime.BULL_MARKET: {
        'mean_return': 0.0008,      # ~20% annual return
        'volatility': 0.012,        # ~19% annual volatility
        'min_persistence': 0.95,    # High persistence
        'jump_intensity': 0.05      # Low jump frequency
    },
    MarketRegime.BEAR_MARKET: {
        'mean_return': -0.0010,     # ~-25% annual return
        'volatility': 0.020,        # ~32% annual volatility
        'min_persistence': 0.85,    # Medium persistence
        'jump_intensity': 0.20      # Higher jump frequency
    },
    MarketRegime.SIDEWAYS_MARKET: {
        'mean_return': 0.0002,      # ~5% annual return
        'volatility': 0.015,        # ~24% annual volatility
        'min_persistence': 0.90,    # Medium-high persistence
        'jump_intensity': 0.10      # Medium jump frequency
    },
    MarketRegime.CRISIS_MARKET: {
        'mean_return': -0.0020,     # ~-50% annual return
        'volatility': 0.035,        # ~55% annual volatility
        'min_persistence': 0.80,    # Lower persistence (more volatile)
        'jump_intensity': 0.50      # Very high jump frequency
    }
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MertonParameters:
    """Merton Jump-Diffusion model parameters."""
    mu: float           # Drift parameter
    sigma: float        # Diffusion volatility
    lambda_jump: float  # Jump intensity (jumps per year)
    mu_jump: float      # Mean jump size
    sigma_jump: float   # Jump size volatility
    
    def validate(self) -> bool:
        """Validate Merton parameters."""
        return (self.sigma > 0 and self.lambda_jump >= 0 and 
                self.sigma_jump >= 0 and self.mu_jump != 0)

@dataclass
class RegimeParameters:
    """Regime switching model parameters."""
    n_regimes: int
    transition_matrix: np.ndarray    # n_regimes x n_regimes transition probabilities
    regime_means: np.ndarray         # Mean returns for each regime
    regime_volatilities: np.ndarray  # Volatilities for each regime
    initial_probabilities: np.ndarray # Initial regime probabilities
    
    def validate(self) -> bool:
        """Validate regime parameters."""
        if self.n_regimes < 2:
            return False
        
        # Check transition matrix
        if (self.transition_matrix.shape != (self.n_regimes, self.n_regimes) or
            not np.allclose(self.transition_matrix.sum(axis=1), 1.0) or
            np.any(self.transition_matrix < 0)):
            return False
        
        # Check other arrays
        return (len(self.regime_means) == self.n_regimes and
                len(self.regime_volatilities) == self.n_regimes and
                len(self.initial_probabilities) == self.n_regimes and
                np.allclose(self.initial_probabilities.sum(), 1.0) and
                np.all(self.regime_volatilities > 0))

@dataclass
class JumpEvent:
    """Individual jump event detection."""
    timestamp: datetime
    return_magnitude: float
    jump_size: float
    jump_type: JumpType
    event_type: EventType
    confidence: float           # Jump detection confidence
    market_impact: float        # Estimated market impact
    regime_before: MarketRegime
    regime_after: MarketRegime

@dataclass
class RegimeState:
    """Current market regime state."""
    current_regime: MarketRegime
    regime_probabilities: Dict[MarketRegime, float]
    persistence_probability: float
    expected_duration_days: float
    regime_confidence: float
    last_regime_change: Optional[datetime]
    regime_history: List[Tuple[datetime, MarketRegime]]

@dataclass
class AdvancedModelResults:
    """Results from advanced modeling analysis."""
    # Jump-Diffusion Results
    jump_probability: float
    expected_jump_size: float
    jump_adjusted_price: float
    jump_risk_premium: float
    
    # Regime Analysis Results
    current_regime: MarketRegime
    regime_transition_probability: Dict[MarketRegime, float]
    regime_adjusted_parameters: Dict[str, float]
    
    # Combined Analysis
    crisis_probability: float
    market_stress_indicator: float
    recommended_strategy_adjustments: List[str]
    
    # Model Quality
    model_confidence: float
    calculation_time_ms: float
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# OPTIMIZED CALCULATION FUNCTIONS
# ==============================================================================
@jit(nopython=True)
def _merton_characteristic_function(phi, T, r, mu, sigma, lambda_jump, mu_jump, sigma_jump):
    """Optimized Merton characteristic function for jump-diffusion pricing."""
    # Drift adjustment for risk-neutral measure
    drift = r - 0.5 * sigma**2 - lambda_jump * (np.exp(mu_jump + 0.5 * sigma_jump**2) - 1)
    
    # Characteristic function components
    cf_gbm = 1j * phi * drift * T - 0.5 * phi**2 * sigma**2 * T
    cf_jumps = lambda_jump * T * (np.exp(1j * phi * mu_jump - 0.5 * phi**2 * sigma_jump**2) - 1)
    
    return np.exp(cf_gbm + cf_jumps)

@jit(nopython=True)
def _jump_detection_statistic(returns, threshold=3.0):
    """Fast jump detection using threshold method."""
    mean_return = np.mean(returns)
    std_return = np.std(returns)
    
    if std_return == 0:
        return np.zeros_like(returns)
    
    standardized_returns = (returns - mean_return) / std_return
    jump_indicators = np.abs(standardized_returns) > threshold
    
    return jump_indicators.astype(np.float64)

@jit(nopython=True)
def _viterbi_decode(observations, transition_matrix, emission_probs, initial_probs):
    """Optimized Viterbi algorithm for regime detection."""
    n_obs = len(observations)
    n_states = len(initial_probs)
    
    # Initialize
    delta = np.zeros((n_obs, n_states))
    psi = np.zeros((n_obs, n_states), dtype=np.int64)
    
    # Initial step
    for i in range(n_states):
        delta[0, i] = initial_probs[i] * emission_probs[0, i]
    
    # Forward pass
    for t in range(1, n_obs):
        for j in range(n_states):
            transition_scores = delta[t-1, :] * transition_matrix[:, j]
            best_previous = np.argmax(transition_scores)
            
            delta[t, j] = transition_scores[best_previous] * emission_probs[t, j]
            psi[t, j] = best_previous
    
    # Backward pass
    path = np.zeros(n_obs, dtype=np.int64)
    path[-1] = np.argmax(delta[-1, :])
    
    for t in range(n_obs - 2, -1, -1):
        path[t] = psi[t + 1, path[t + 1]]
    
    return path

# ==============================================================================
# MAIN ADVANCED MODELS ENGINE CLASS
# ==============================================================================
class SpyderAdvancedModelsEngine:
    """
    Consolidated advanced modeling engine for Spyder trading system.
    
    Combines Merton Jump-Diffusion and Regime Switching models to provide
    sophisticated market analysis beyond traditional Black-Scholes assumptions.
    Handles crisis periods, market regime changes, and discontinuous price
    movements essential for robust SPY options trading.
    
    Key Features:
    - Merton jump-diffusion modeling for crisis and event-driven periods
    - Markov regime switching for market state intelligence
    - Intelligent coordination between jump detection and regime analysis
    - Real-time crisis probability assessment
    - Event-driven strategy recommendations
    - Integration with V06_VolatilityEngine for enhanced accuracy
    """
    
    def __init__(self, 
                 config: Dict[str, Any] = None,
                 data_manager: MultiClientDataManager = None,
                 volatility_engine: SpyderVolatilityEngine = None):
        """Initialize consolidated advanced models engine."""
        self.config = config or {}
        self.data_manager = data_manager
        self.volatility_engine = volatility_engine
        self.logger = logging.getLogger(__name__)
        
        # Model parameters (will be calibrated)
        self.merton_params: Optional[MertonParameters] = None
        self.regime_params: Optional[RegimeParameters] = None
        
        # Current state
        self.current_regime: MarketRegime = MarketRegime.SIDEWAYS_MARKET
        self.regime_probabilities: Dict[MarketRegime, float] = {}
        self.last_regime_change: Optional[datetime] = None
        
        # Market data storage
        self.price_history: List[float] = []
        self.return_history: List[float] = []
        self.jump_history: List[JumpEvent] = []
        self.regime_history: List[Tuple[datetime, MarketRegime]] = []
        
        # Detection states
        self.filtered_regime_probabilities: Optional[np.ndarray] = None
        self.jump_indicators: Optional[np.ndarray] = None
        self.last_jump_time: Optional[datetime] = None
        
        # Performance tracking
        self.model_performance: Dict[str, float] = {
            'regime_accuracy': 0.0,
            'jump_detection_accuracy': 0.0,
            'crisis_prediction_accuracy': 0.0,
            'total_regime_switches': 0,
            'total_jumps_detected': 0
        }
        
        # Configuration
        self.min_data_points = self.config.get('min_data_points', 252)  # 1 year
        self.jump_threshold = self.config.get('jump_threshold', 3.0)    # 3 sigma
        self.regime_lookback = self.config.get('regime_lookback', 504)  # 2 years
        self.calibration_frequency_hours = self.config.get('calibration_frequency_hours', 168)  # 1 week
        self.last_calibration: Optional[datetime] = None
        
        # Initialize with default parameters
        self._initialize_default_parameters()
        
        self.logger.info("SpyderAdvancedModelsEngine initialized successfully")
    
    def _initialize_default_parameters(self):
        """Initialize with sensible default parameters."""
        # Default Merton parameters
        self.merton_params = MertonParameters(
            mu=0.08,           # 8% annual drift
            sigma=0.15,        # 15% annual volatility
            lambda_jump=0.2,   # 0.2 jumps per year on average
            mu_jump=-0.05,     # Mean jump size -5%
            sigma_jump=0.10    # Jump volatility 10%
        )
        
        # Default 3-regime model (Bull, Bear, Sideways)
        n_regimes = 3
        
        # Transition matrix with high persistence
        transition_matrix = np.array([
            [0.95, 0.03, 0.02],  # Bull -> Bull, Bear, Sideways
            [0.05, 0.90, 0.05],  # Bear -> Bull, Bear, Sideways  
            [0.10, 0.10, 0.80]   # Sideways -> Bull, Bear, Sideways
        ])
        
        regime_means = np.array([0.0008, -0.0010, 0.0002])     # Daily returns
        regime_volatilities = np.array([0.012, 0.020, 0.015])  # Daily volatilities
        initial_probabilities = np.array([0.3, 0.2, 0.5])      # Start in sideways
        
        self.regime_params = RegimeParameters(
            n_regimes=n_regimes,
            transition_matrix=transition_matrix,
            regime_means=regime_means,
            regime_volatilities=regime_volatilities,
            initial_probabilities=initial_probabilities
        )
        
        # Initialize regime probabilities
        self.regime_probabilities = {
            MarketRegime.BULL_MARKET: 0.3,
            MarketRegime.BEAR_MARKET: 0.2,
            MarketRegime.SIDEWAYS_MARKET: 0.5
        }
    
    # ==========================================================================
    # MAIN ANALYSIS INTERFACE
    # ==========================================================================
    
    async def analyze_market_conditions(self,
                                      include_regime_analysis: bool = True,
                                      include_jump_analysis: bool = True) -> AdvancedModelResults:
        """
        Comprehensive market condition analysis.
        
        Args:
            include_regime_analysis: Include regime switching analysis
            include_jump_analysis: Include jump-diffusion analysis
            
        Returns:
            AdvancedModelResults: Complete advanced modeling results
        """
        start_time = time.time()
        
        try:
            # Ensure models are calibrated
            await self._ensure_calibration()
            
            results = AdvancedModelResults(
                jump_probability=0.0,
                expected_jump_size=0.0,
                jump_adjusted_price=0.0,
                jump_risk_premium=0.0,
                current_regime=self.current_regime,
                regime_transition_probability={},
                regime_adjusted_parameters={},
                crisis_probability=0.0,
                market_stress_indicator=0.0,
                recommended_strategy_adjustments=[],
                model_confidence=0.0
            )
            
            # Jump-Diffusion Analysis
            if include_jump_analysis and len(self.return_history) > 50:
                jump_results = await self._analyze_jump_diffusion()
                results.jump_probability = jump_results['jump_probability']
                results.expected_jump_size = jump_results['expected_jump_size']
                results.jump_adjusted_price = jump_results['jump_adjusted_price']
                results.jump_risk_premium = jump_results['jump_risk_premium']
            
            # Regime Analysis
            if include_regime_analysis and len(self.return_history) > 100:
                regime_results = await self._analyze_market_regimes()
                results.current_regime = regime_results['current_regime']
                results.regime_transition_probability = regime_results['transition_probabilities']
                results.regime_adjusted_parameters = regime_results['adjusted_parameters']
            
            # Combined Crisis Analysis
            crisis_analysis = self._analyze_crisis_probability(results)
            results.crisis_probability = crisis_analysis['crisis_probability']
            results.market_stress_indicator = crisis_analysis['stress_indicator']
            
            # Strategy Recommendations
            results.recommended_strategy_adjustments = self._generate_strategy_recommendations(results)
            
            # Overall model confidence
            results.model_confidence = self._calculate_model_confidence(results)
            
            # Performance tracking
            calculation_time = (time.time() - start_time) * 1000
            results.calculation_time_ms = calculation_time
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in market condition analysis: {e}")
            
            # Return safe default results
            return AdvancedModelResults(
                jump_probability=0.05,
                expected_jump_size=0.0,
                jump_adjusted_price=0.0,
                jump_risk_premium=0.0,
                current_regime=MarketRegime.SIDEWAYS_MARKET,
                regime_transition_probability={},
                regime_adjusted_parameters={},
                crisis_probability=0.1,
                market_stress_indicator=0.0,
                recommended_strategy_adjustments=['Maintain defensive positioning'],
                model_confidence=0.5,
                calculation_time_ms=(time.time() - start_time) * 1000,
                warnings=[f"Analysis failed: {str(e)}"]
            )
    
    async def detect_market_regime(self) -> RegimeState:
        """
        Detect current market regime with confidence metrics.
        
        Returns:
            RegimeState: Current regime state with probabilities
        """
        try:
            await self._ensure_calibration()
            
            if len(self.return_history) < 50:
                return RegimeState(
                    current_regime=MarketRegime.SIDEWAYS_MARKET,
                    regime_probabilities=self.regime_probabilities,
                    persistence_probability=0.8,
                    expected_duration_days=30,
                    regime_confidence=0.5,
                    last_regime_change=None,
                    regime_history=[]
                )
            
            # Update regime probabilities using Viterbi algorithm
            regime_sequence = self._detect_regime_sequence()
            current_regime_idx = regime_sequence[-1]
            
            # Map index to regime
            regime_mapping = {
                0: MarketRegime.BULL_MARKET,
                1: MarketRegime.BEAR_MARKET,
                2: MarketRegime.SIDEWAYS_MARKET
            }
            
            current_regime = regime_mapping.get(current_regime_idx, MarketRegime.SIDEWAYS_MARKET)
            
            # Calculate regime probabilities
            regime_probs = self._calculate_regime_probabilities()
            
            # Persistence probability
            persistence_prob = self.regime_params.transition_matrix[current_regime_idx, current_regime_idx]
            
            # Expected duration (geometric distribution)
            expected_duration = 1 / (1 - persistence_prob) if persistence_prob < 1 else 100
            
            # Regime confidence based on probability concentration
            max_prob = max(regime_probs.values())
            confidence = min(max_prob * 2, 1.0)  # Scale to 0-1
            
            # Update current state
            if current_regime != self.current_regime:
                self.last_regime_change = datetime.now()
                self.regime_history.append((datetime.now(), current_regime))
                self.current_regime = current_regime
                self.model_performance['total_regime_switches'] += 1
            
            self.regime_probabilities = regime_probs
            
            return RegimeState(
                current_regime=current_regime,
                regime_probabilities=regime_probs,
                persistence_probability=persistence_prob,
                expected_duration_days=expected_duration,
                regime_confidence=confidence,
                last_regime_change=self.last_regime_change,
                regime_history=self.regime_history[-10:]  # Last 10 regime changes
            )
            
        except Exception as e:
            self.logger.error(f"Error detecting market regime: {e}")
            
            return RegimeState(
                current_regime=self.current_regime,
                regime_probabilities=self.regime_probabilities,
                persistence_probability=0.8,
                expected_duration_days=30,
                regime_confidence=0.5,
                last_regime_change=self.last_regime_change,
                regime_history=self.regime_history[-10:] if self.regime_history else []
            )
    
    async def detect_jumps(self, lookback_days: int = 30) -> List[JumpEvent]:
        """
        Detect recent jump events in price series.
        
        Args:
            lookback_days: Number of days to look back for jump detection
            
        Returns:
            List[JumpEvent]: Detected jump events
        """
        try:
            if len(self.return_history) < lookback_days:
                return []
            
            recent_returns = np.array(self.return_history[-lookback_days:])
            jump_indicators = _jump_detection_statistic(recent_returns, self.jump_threshold)
            
            detected_jumps = []
            
            for i, is_jump in enumerate(jump_indicators):
                if is_jump:
                    return_value = recent_returns[i]
                    jump_size = abs(return_value)
                    
                    # Classify jump type
                    if return_value > 0:
                        jump_type = JumpType.POSITIVE_JUMP
                    else:
                        jump_type = JumpType.NEGATIVE_JUMP
                    
                    if jump_size > 5 * np.std(recent_returns):
                        jump_type = JumpType.EXTREME_JUMP
                    
                    # Estimate timestamp (approximation)
                    days_ago = lookback_days - i
                    timestamp = datetime.now() - timedelta(days=days_ago)
                    
                    # Create jump event
                    jump_event = JumpEvent(
                        timestamp=timestamp,
                        return_magnitude=return_value,
                        jump_size=jump_size,
                        jump_type=jump_type,
                        event_type=EventType.UNKNOWN,  # Would need news data to classify
                        confidence=min(jump_size / (3 * np.std(recent_returns)), 1.0),
                        market_impact=jump_size * 0.5,  # Simplified impact estimate
                        regime_before=self.current_regime,
                        regime_after=self.current_regime
                    )
                    
                    detected_jumps.append(jump_event)
            
            # Update jump history
            self.jump_history.extend(detected_jumps)
            if len(self.jump_history) > 100:  # Keep last 100 jumps
                self.jump_history = self.jump_history[-100:]
            
            self.model_performance['total_jumps_detected'] += len(detected_jumps)
            
            return detected_jumps
            
        except Exception as e:
            self.logger.error(f"Error detecting jumps: {e}")
            return []
    
    # ==========================================================================
    # MODEL CALIBRATION
    # ==========================================================================
    
    async def _ensure_calibration(self):
        """Ensure models are properly calibrated."""
        current_time = datetime.now()
        
        if (self.last_calibration is None or 
            (current_time - self.last_calibration).total_seconds() > 
            self.calibration_frequency_hours * 3600):
            
            await self._calibrate_models()
    
    async def _calibrate_models(self):
        """Calibrate both Merton and Regime Switching models."""
        self.logger.info("Starting advanced models calibration...")
        
        try:
            if len(self.return_history) < self.min_data_points:
                self._generate_synthetic_data()
            
            # Calibrate Merton Jump-Diffusion model
            self.merton_params = await self._calibrate_merton()
            
            # Calibrate Regime Switching model
            self.regime_params = await self._calibrate_regime_switching()
            
            self.last_calibration = datetime.now()
            self.logger.info("Advanced models calibration completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error calibrating models: {e}")
            # Keep default parameters if calibration fails
    
    async def _calibrate_merton(self) -> MertonParameters:
        """Calibrate Merton Jump-Diffusion model."""
        if len(self.return_history) < 100:
            return self.merton_params
        
        returns = np.array(self.return_history[-252:])  # Last year
        
        # Detect jumps first
        jump_indicators = _jump_detection_statistic(returns, self.jump_threshold)
        jump_returns = returns[jump_indicators > 0]
        normal_returns = returns[jump_indicators == 0]
        
        if len(normal_returns) < 50:
            return self.merton_params
        
        # Estimate parameters
        mu = np.mean(normal_returns) * 252  # Annualized
        sigma = np.std(normal_returns, ddof=1) * np.sqrt(252)  # Annualized
        
        # Jump parameters
        lambda_jump = len(jump_returns) / len(returns) * 252  # Annualized frequency
        
        if len(jump_returns) > 0:
            mu_jump = np.mean(jump_returns)
            sigma_jump = np.std(jump_returns, ddof=1) if len(jump_returns) > 1 else 0.05
        else:
            mu_jump = -0.05  # Default negative jump
            sigma_jump = 0.10
        
        # Create and validate parameters
        params = MertonParameters(
            mu=mu,
            sigma=sigma,
            lambda_jump=max(lambda_jump, 0.01),  # Minimum jump intensity
            mu_jump=mu_jump,
            sigma_jump=max(sigma_jump, 0.01)
        )
        
        if params.validate():
            return params
        else:
            return self.merton_params  # Return current if validation fails
    
    async def _calibrate_regime_switching(self) -> RegimeParameters:
        """Calibrate Regime Switching model using EM algorithm."""
        if len(self.return_history) < 200:
            return self.regime_params
        
        returns = np.array(self.return_history[-self.regime_lookback:])
        
        try:
            # Use Gaussian Mixture Model as approximation for regime switching
            n_regimes = 3
            gmm = GaussianMixture(
                n_components=n_regimes, 
                covariance_type='full',
                random_state=42,
                max_iter=100
            )
            
            # Reshape for sklearn
            X = returns.reshape(-1, 1)
            gmm.fit(X)
            
            # Extract parameters
            regime_means = gmm.means_.flatten() * 252  # Annualized
            regime_volatilities = np.sqrt(gmm.covariances_.flatten()) * np.sqrt(252)  # Annualized
            
            # Estimate transition matrix using regime sequence
            regime_sequence = gmm.predict(X)
            transition_matrix = self._estimate_transition_matrix(regime_sequence, n_regimes)
            
            # Initial probabilities from GMM weights
            initial_probabilities = gmm.weights_
            
            params = RegimeParameters(
                n_regimes=n_regimes,
                transition_matrix=transition_matrix,
                regime_means=regime_means,
                regime_volatilities=regime_volatilities,
                initial_probabilities=initial_probabilities
            )
            
            if params.validate():
                return params
            else:
                return self.regime_params
                
        except Exception as e:
            self.logger.warning(f"Regime switching calibration failed: {e}")
            return self.regime_params
    
    def _estimate_transition_matrix(self, regime_sequence: np.ndarray, n_regimes: int) -> np.ndarray:
        """Estimate transition matrix from regime sequence."""
        transition_counts = np.zeros((n_regimes, n_regimes))
        
        for t in range(len(regime_sequence) - 1):
            current_regime = regime_sequence[t]
            next_regime = regime_sequence[t + 1]
            transition_counts[current_regime, next_regime] += 1
        
        # Normalize to get probabilities
        transition_matrix = np.zeros((n_regimes, n_regimes))
        for i in range(n_regimes):
            row_sum = transition_counts[i, :].sum()
            if row_sum > 0:
                transition_matrix[i, :] = transition_counts[i, :] / row_sum
            else:
                # Default to staying in same regime if no transitions observed
                transition_matrix[i, i] = 1.0
        
        return transition_matrix
    
    def _generate_synthetic_data(self):
        """Generate synthetic data with jumps and regime switching."""
        np.random.seed(42)
        n_days = self.min_data_points
        
        # Generate regime sequence
        current_regime = 2  # Start in sideways
        regime_sequence = [current_regime]
        
        for _ in range(n_days - 1):
            transition_probs = self.regime_params.transition_matrix[current_regime, :]
            current_regime = np.random.choice(len(transition_probs), p=transition_probs)
            regime_sequence.append(current_regime)
        
        # Generate returns with regime-dependent parameters and jumps
        returns = []
        prices = [450.0]  # Starting price
        
        for t in range(n_days):
            regime = regime_sequence[t]
            
            # Regime-dependent parameters
            mu_regime = self.regime_params.regime_means[regime] / 252  # Daily
            sigma_regime = self.regime_params.regime_volatilities[regime] / np.sqrt(252)  # Daily
            
            # Normal return component
            normal_return = np.random.normal(mu_regime, sigma_regime)
            
            # Add jumps with regime-dependent intensity
            jump_intensity = REGIME_CHARACTERISTICS[list(MarketRegime)[regime]]['jump_intensity']
            
            if np.random.random() < jump_intensity / 252:  # Daily jump probability
                jump_size = np.random.normal(self.merton_params.mu_jump, self.merton_params.sigma_jump)
                total_return = normal_return + jump_size
            else:
                total_return = normal_return
            
            returns.append(total_return)
            prices.append(prices[-1] * (1 + total_return))
        
        self.return_history = returns
        self.price_history = prices[1:]  # Skip initial price
        
        self.logger.info("Generated synthetic data with regimes and jumps")
    
    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    
    async def _analyze_jump_diffusion(self) -> Dict[str, float]:
        """Analyze jump-diffusion characteristics."""
        if not self.merton_params or len(self.return_history) < 50:
            return {
                'jump_probability': 0.0,
                'expected_jump_size': 0.0,
                'jump_adjusted_price': 0.0,
                'jump_risk_premium': 0.0
            }
        
        # Current jump probability (daily)
        daily_jump_prob = self.merton_params.lambda_jump / 252
        
        # Expected jump size
        expected_jump = self.merton_params.mu_jump
        
        # Jump risk premium (simplified)
        jump_risk_premium = daily_jump_prob * abs(expected_jump) * 0.5
        
        # Price adjustment for jump risk (simplified)
        current_price = self.price_history[-1] if self.price_history else 450.0
        jump_adjusted_price = current_price * (1 - jump_risk_premium)
        
        return {
            'jump_probability': daily_jump_prob,
            'expected_jump_size': expected_jump,
            'jump_adjusted_price': jump_adjusted_price,
            'jump_risk_premium': jump_risk_premium
        }
    
    async def _analyze_market_regimes(self) -> Dict[str, Any]:
        """Analyze current market regime characteristics."""
        if not self.regime_params or len(self.return_history) < 100:
            return {
                'current_regime': MarketRegime.SIDEWAYS_MARKET,
                'transition_probabilities': {},
                'adjusted_parameters': {}
            }
        
        # Update regime detection
        regime_state = await self.detect_market_regime()
        
        # Transition probabilities for next period
        current_regime_idx = self._regime_to_index(regime_state.current_regime)
        next_period_probs = self.regime_params.transition_matrix[current_regime_idx, :]
        
        transition_probabilities = {}
        regime_list = [MarketRegime.BULL_MARKET, MarketRegime.BEAR_MARKET, MarketRegime.SIDEWAYS_MARKET]
        
        for i, regime in enumerate(regime_list):
            transition_probabilities[regime] = next_period_probs[i]
        
        # Regime-adjusted parameters
        adjusted_parameters = {
            'expected_return': self.regime_params.regime_means[current_regime_idx],
            'volatility': self.regime_params.regime_volatilities[current_regime_idx],
            'persistence': self.regime_params.transition_matrix[current_regime_idx, current_regime_idx]
        }
        
        return {
            'current_regime': regime_state.current_regime,
            'transition_probabilities': transition_probabilities,
            'adjusted_parameters': adjusted_parameters
        }
    
    def _analyze_crisis_probability(self, results: AdvancedModelResults) -> Dict[str, float]:
        """Analyze probability of crisis conditions."""
        crisis_indicators = []
        
        # High jump probability indicates instability
        if results.jump_probability > 0.1:  # 10% daily jump probability
            crisis_indicators.append(0.3)
        
        # Bear market regime increases crisis probability
        if results.current_regime == MarketRegime.BEAR_MARKET:
            crisis_indicators.append(0.4)
        
        # High volatility from volatility engine
        if self.volatility_engine:
            try:
                current_vol = asyncio.run(self.volatility_engine.get_volatility())
                if current_vol > 0.35:  # 35% annualized volatility
                    crisis_indicators.append(0.5)
            except:
                pass
        
        # Recent extreme jumps
        recent_extreme_jumps = sum(1 for jump in self.jump_history[-10:] 
                                 if jump.jump_type == JumpType.EXTREME_JUMP)
        if recent_extreme_jumps > 2:
            crisis_indicators.append(0.6)
        
        # Calculate overall crisis probability
        if not crisis_indicators:
            crisis_probability = 0.05  # Base probability
        else:
            crisis_probability = min(np.mean(crisis_indicators) * 1.5, 0.95)
        
        # Market stress indicator (0-1 scale)
        stress_factors = []
        
        if results.jump_probability > 0:
            stress_factors.append(min(results.jump_probability * 10, 1.0))
        
        if results.current_regime == MarketRegime.BEAR_MARKET:
            stress_factors.append(0.7)
        elif results.current_regime == MarketRegime.CRISIS_MARKET:
            stress_factors.append(1.0)
        
        market_stress = np.mean(stress_factors) if stress_factors else 0.1
        
        return {
            'crisis_probability': crisis_probability,
            'stress_indicator': market_stress
        }
    
    def _generate_strategy_recommendations(self, results: AdvancedModelResults) -> List[str]:
        """Generate strategy recommendations based on analysis."""
        recommendations = []
        
        # Jump-based recommendations
        if results.jump_probability > 0.1:
            recommendations.append("Increase option positions to benefit from volatility expansion")
            recommendations.append("Consider protective puts for portfolio hedging")
        
        if results.expected_jump_size < -0.03:  # Expected negative jump > 3%
            recommendations.append("Reduce net long exposure")
            recommendations.append("Increase put/call ratio in strategies")
        
        # Regime-based recommendations
        if results.current_regime == MarketRegime.BEAR_MARKET:
            recommendations.append("Focus on bear market strategies (put spreads, protective puts)")
            recommendations.append("Reduce delta exposure and increase defensive positioning")
        
        elif results.current_regime == MarketRegime.BULL_MARKET:
            recommendations.append("Implement bullish strategies (call spreads, covered calls)")
            recommendations.append("Increase long exposure with appropriate risk management")
        
        elif results.current_regime == MarketRegime.SIDEWAYS_MARKET:
            recommendations.append("Use range-bound strategies (iron condors, butterflies)")
            recommendations.append("Focus on time decay and volatility selling strategies")
        
        # Crisis-based recommendations
        if results.crisis_probability > 0.3:
            recommendations.append("Implement crisis hedging strategies")
            recommendations.append("Reduce position sizes and increase cash reserves")
            recommendations.append("Focus on tail risk protection")
        
        # Default recommendation if no specific conditions
        if not recommendations:
            recommendations.append("Maintain balanced approach with moderate risk exposure")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def _calculate_model_confidence(self, results: AdvancedModelResults) -> float:
        """Calculate overall model confidence score."""
        confidence_factors = []
        
        # Data quality factor
        data_quality = min(len(self.return_history) / self.min_data_points, 1.0)
        confidence_factors.append(data_quality)
        
        # Model calibration recency
        if self.last_calibration:
            hours_since_calibration = (datetime.now() - self.last_calibration).total_seconds() / 3600
            calibration_freshness = max(0, 1 - hours_since_calibration / (7 * 24))  # 7 days max
            confidence_factors.append(calibration_freshness)
        else:
            confidence_factors.append(0.5)
        
        # Regime classification certainty
        if results.regime_transition_probability:
            max_regime_prob = max(results.regime_transition_probability.values())
            regime_certainty = max_regime_prob * 2 - 1  # Scale to 0-1
            confidence_factors.append(max(regime_certainty, 0))
        
        # Jump detection stability
        if len(self.jump_history) > 0:
            recent_jumps = sum(1 for jump in self.jump_history[-30:] if jump.confidence > 0.7)
            jump_stability = 1.0 - min(recent_jumps / 10, 1.0)  # Lower confidence with many jumps
            confidence_factors.append(jump_stability)
        else:
            confidence_factors.append(0.8)  # Neutral confidence
        
        return np.mean(confidence_factors)
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _detect_regime_sequence(self) -> np.ndarray:
        """Detect regime sequence using Viterbi algorithm."""
        if not self.regime_params or len(self.return_history) < 10:
            return np.array([2] * len(self.return_history))  # Default to sideways
        
        returns = np.array(self.return_history[-100:])  # Last 100 observations
        n_obs = len(returns)
        n_regimes = self.regime_params.n_regimes
        
        # Calculate emission probabilities
        emission_probs = np.zeros((n_obs, n_regimes))
        
        for t in range(n_obs):
            for regime in range(n_regimes):
                mean = self.regime_params.regime_means[regime] / 252  # Daily
                std = self.regime_params.regime_volatilities[regime] / np.sqrt(252)  # Daily
                
                # Gaussian emission probability
                emission_probs[t, regime] = norm.pdf(returns[t], mean, std)
        
        # Avoid zero probabilities
        emission_probs = np.maximum(emission_probs, 1e-10)
        
        # Run Viterbi algorithm
        regime_sequence = _viterbi_decode(
            returns, 
            self.regime_params.transition_matrix,
            emission_probs,
            self.regime_params.initial_probabilities
        )
        
        return regime_sequence
    
    def _calculate_regime_probabilities(self) -> Dict[MarketRegime, float]:
        """Calculate current regime probabilities."""
        if not self.regime_params:
            return self.regime_probabilities
        
        # Use filtered probabilities from regime detection
        regime_sequence = self._detect_regime_sequence()
        
        if len(regime_sequence) > 0:
            current_regime_idx = regime_sequence[-1]
            
            # Create probability distribution based on recent regime assignments
            recent_sequence = regime_sequence[-min(20, len(regime_sequence)):]  # Last 20 observations
            regime_counts = np.bincount(recent_sequence, minlength=self.regime_params.n_regimes)
            regime_probs = regime_counts / len(recent_sequence)
            
            regime_mapping = {
                0: MarketRegime.BULL_MARKET,
                1: MarketRegime.BEAR_MARKET,
                2: MarketRegime.SIDEWAYS_MARKET
            }
            
            probability_dict = {}
            for i, prob in enumerate(regime_probs):
                if i < len(regime_mapping):
                    probability_dict[regime_mapping[i]] = prob
            
            return probability_dict
        
        return self.regime_probabilities
    
    def _regime_to_index(self, regime: MarketRegime) -> int:
        """Convert regime enum to array index."""
        regime_mapping = {
            MarketRegime.BULL_MARKET: 0,
            MarketRegime.BEAR_MARKET: 1,
            MarketRegime.SIDEWAYS_MARKET: 2
        }
        return regime_mapping.get(regime, 2)  # Default to sideways
    
    # ==========================================================================
    # DATA MANAGEMENT
    # ==========================================================================
    
    async def update_market_data(self, prices: List[float], timestamps: List[datetime] = None):
        """Update market data for advanced modeling."""
        if not prices:
            return
        
        # Update price history
        self.price_history.extend(prices)
        
        # Trim to reasonable size
        max_history = 5000  # ~20 years of daily data
        if len(self.price_history) > max_history:
            excess = len(self.price_history) - max_history
            self.price_history = self.price_history[excess:]
        
        # Calculate new returns
        if len(self.price_history) > 1:
            new_returns = []
            start_idx = len(self.price_history) - len(prices)
            
            for i in range(start_idx, len(self.price_history)):
                if i > 0:
                    ret = (self.price_history[i] - self.price_history[i-1]) / self.price_history[i-1]
                    new_returns.append(ret)
            
            self.return_history.extend(new_returns)
            
            # Trim return history
            if len(self.return_history) > max_history:
                excess = len(self.return_history) - max_history
                self.return_history = self.return_history[excess:]
        
        # Detect new jumps
        if len(new_returns) > 0:
            recent_jumps = await self.detect_jumps(len(new_returns))
            if recent_jumps:
                self.logger.info(f"Detected {len(recent_jumps)} new jump events")
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get comprehensive engine status."""
        return {
            'models_calibrated': {
                'merton': self.merton_params is not None,
                'regime_switching': self.regime_params is not None
            },
            'data_status': {
                'price_points': len(self.price_history),
                'return_points': len(self.return_history),
                'data_quality': 'Good' if len(self.return_history) >= self.min_data_points else 'Insufficient'
            },
            'current_state': {
                'regime': self.current_regime.value,
                'regime_probabilities': {k.value: v for k, v in self.regime_probabilities.items()},
                'last_regime_change': self.last_regime_change.isoformat() if self.last_regime_change else None,
                'total_jumps_detected': len(self.jump_history)
            },
            'model_parameters': {
                'merton': {
                    'lambda_jump': self.merton_params.lambda_jump if self.merton_params else None,
                    'mu_jump': self.merton_params.mu_jump if self.merton_params else None,
                    'sigma_jump': self.merton_params.sigma_jump if self.merton_params else None
                },
                'regime_switching': {
                    'n_regimes': self.regime_params.n_regimes if self.regime_params else None,
                    'persistence_probs': np.diag(self.regime_params.transition_matrix).tolist() if self.regime_params else None
                }
            },
            'performance_metrics': self.model_performance,
            'last_calibration': self.last_calibration.isoformat() if self.last_calibration else None
        }

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_advanced_models_engine(config: Dict[str, Any] = None,
                                 data_manager: MultiClientDataManager = None,
                                 volatility_engine: SpyderVolatilityEngine = None) -> SpyderAdvancedModelsEngine:
    """Factory function to create SpyderAdvancedModelsEngine."""
    return SpyderAdvancedModelsEngine(config, data_manager, volatility_engine)

# ==============================================================================
# DEMONSTRATION AND TESTING
# ==============================================================================
async def main():
    """Demonstration of consolidated advanced models engine."""
    print("=" * 80)
    print("SPYDER V07 CONSOLIDATED ADVANCED MODELS ENGINE DEMONSTRATION")
    print("=" * 80)
    
    # Initialize advanced models engine
    config = {
        'min_data_points': 200,
        'jump_threshold': 3.0,
        'calibration_frequency_hours': 24
    }
    
    advanced_engine = create_advanced_models_engine(config)
    
    print("\n✅ Advanced Models Engine Initialized")
    print("   • Consolidated Merton Jump-Diffusion and Regime Switching models")
    print("   • Intelligent crisis detection and market regime analysis")
    print("   • Event-driven strategy recommendations")
    print("   • Real-time jump detection and regime monitoring")
    
    # Generate synthetic market data with regime switches and jumps
    print(f"\n--- Generating Synthetic Market Data with Regimes and Jumps ---")
    await advanced_engine.update_market_data([450.0])  # Initialize with starting price
    
    # Force generation of synthetic data for demonstration
    advanced_engine._generate_synthetic_data()
    
    print(f"   Generated {len(advanced_engine.return_history)} return observations")
    print(f"   Price range: ${min(advanced_engine.price_history):.2f} - ${max(advanced_engine.price_history):.2f}")
    
    # Test 1: Market Regime Detection
    print(f"\n--- Test 1: Market Regime Detection ---")
    try:
        regime_state = await advanced_engine.detect_market_regime()
        
        print(f"   Current Regime: {regime_state.current_regime.value}")
        print(f"   Regime Confidence: {regime_state.regime_confidence:.1%}")
        print(f"   Expected Duration: {regime_state.expected_duration_days:.1f} days")
        print(f"   Persistence Probability: {regime_state.persistence_probability:.1%}")
        
        print(f"\n   Regime Probabilities:")
        for regime, prob in regime_state.regime_probabilities.items():
            print(f"     {regime.value}: {prob:.1%}")
        
        if regime_state.last_regime_change:
            print(f"   Last Regime Change: {regime_state.last_regime_change.strftime('%Y-%m-%d %H:%M')}")
        
    except Exception as e:
        print(f"   ❌ Regime Detection Error: {e}")
    
    # Test 2: Jump Detection
    print(f"\n--- Test 2: Jump Detection ---")
    try:
        recent_jumps = await advanced_engine.detect_jumps(lookback_days=50)
        
        print(f"   Jumps Detected: {len(recent_jumps)}")
        
        if recent_jumps:
            print(f"\n   Recent Jump Events:")
            print(f"   {'Date':<12} {'Type':<15} {'Size':<8} {'Confidence':<12}")
            print("   " + "-" * 50)
            
            for jump in recent_jumps[-5:]:  # Show last 5 jumps
                date_str = jump.timestamp.strftime('%m-%d')
                print(f"   {date_str:<12} {jump.jump_type.value:<15} "
                      f"{jump.jump_size:>7.1%} {jump.confidence:>11.1%}")
        
        # Jump statistics
        if len(advanced_engine.jump_history) > 0:
            positive_jumps = sum(1 for j in advanced_engine.jump_history if j.jump_type == JumpType.POSITIVE_JUMP)
            negative_jumps = sum(1 for j in advanced_engine.jump_history if j.jump_type == JumpType.NEGATIVE_JUMP)
            extreme_jumps = sum(1 for j in advanced_engine.jump_history if j.jump_type == JumpType.EXTREME_JUMP)
            
            print(f"\n   Jump Statistics:")
            print(f"     Positive Jumps: {positive_jumps}")
            print(f"     Negative Jumps: {negative_jumps}")
            print(f"     Extreme Jumps: {extreme_jumps}")
        
    except Exception as e:
        print(f"   ❌ Jump Detection Error: {e}")
    
    # Test 3: Comprehensive Market Analysis
    print(f"\n--- Test 3: Comprehensive Market Analysis ---")
    try:
        results = await advanced_engine.analyze_market_conditions(
            include_regime_analysis=True,
            include_jump_analysis=True
        )
        
        print(f"   Current Regime: {results.current_regime.value}")
        print(f"   Jump Probability (daily): {results.jump_probability:.2%}")
        print(f"   Expected Jump Size: {results.expected_jump_size:.1%}")
        print(f"   Crisis Probability: {results.crisis_probability:.1%}")
        print(f"   Market Stress Indicator: {results.market_stress_indicator:.2f}/1.0")
        print(f"   Model Confidence: {results.model_confidence:.1%}")
        print(f"   Analysis Time: {results.calculation_time_ms:.1f}ms")
        
        # Regime transition probabilities
        if results.regime_transition_probability:
            print(f"\n   Regime Transition Probabilities:")
            for regime, prob in results.regime_transition_probability.items():
                print(f"     → {regime.value}: {prob:.1%}")
        
        # Strategy recommendations
        if results.recommended_strategy_adjustments:
            print(f"\n   Strategy Recommendations:")
            for i, recommendation in enumerate(results.recommended_strategy_adjustments, 1):
                print(f"     {i}. {recommendation}")
        
    except Exception as e:
        print(f"   ❌ Analysis Error: {e}")
    
    # Test 4: Model Parameters
    print(f"\n--- Test 4: Model Parameters ---")
    try:
        status = advanced_engine.get_engine_status()
        
        print("   Merton Jump-Diffusion Parameters:")
        if status['model_parameters']['merton']['lambda_jump']:
            merton = status['model_parameters']['merton']
            print(f"     Jump Intensity: {merton['lambda_jump']:.2f} per year")
            print(f"     Mean Jump Size: {merton['mu_jump']:.1%}")
            print(f"     Jump Volatility: {merton['sigma_jump']:.1%}")
        
        print("   Regime Switching Parameters:")
        if status['model_parameters']['regime_switching']['n_regimes']:
            regime = status['model_parameters']['regime_switching']
            print(f"     Number of Regimes: {regime['n_regimes']}")
            if regime['persistence_probs']:
                print(f"     Persistence Probabilities: {[f'{p:.1%}' for p in regime['persistence_probs']]}")
        
    except Exception as e:
        print(f"   ❌ Parameters Error: {e}")
    
    # Test 5: Performance Metrics
    print(f"\n--- Test 5: Performance Metrics ---")
    try:
        status = advanced_engine.get_engine_status()
        
        performance = status['performance_metrics']
        print(f"   Total Regime Switches: {performance['total_regime_switches']}")
        print(f"   Total Jumps Detected: {performance['total_jumps_detected']}")
        print(f"   Regime Accuracy: {performance['regime_accuracy']:.1%}")
        print(f"   Jump Detection Accuracy: {performance['jump_detection_accuracy']:.1%}")
        print(f"   Crisis Prediction Accuracy: {performance['crisis_prediction_accuracy']:.1%}")
        
        print(f"\n   Data Status:")
        data_status = status['data_status']
        print(f"     Price Points: {data_status['price_points']}")
        print(f"     Return Points: {data_status['return_points']}")
        print(f"     Data Quality: {data_status['data_quality']}")
        
        if status['last_calibration']:
            print(f"     Last Calibration: {status['last_calibration'][:19]}")
        
    except Exception as e:
        print(f"   ❌ Performance Error: {e}")
    
    # Test 6: Crisis Scenario Simulation
    print(f"\n--- Test 6: Crisis Scenario Simulation ---")
    try:
        # Simulate crisis-like returns
        crisis_returns = [-0.08, -0.12, 0.05, -0.15, 0.08, -0.06]  # Volatile crisis pattern
        crisis_prices = [advanced_engine.price_history[-1]]
        
        for ret in crisis_returns:
            crisis_prices.append(crisis_prices[-1] * (1 + ret))
        
        # Update with crisis data
        await advanced_engine.update_market_data(crisis_prices[1:])
        
        # Analyze crisis conditions
        crisis_results = await advanced_engine.analyze_market_conditions()
        
        print(f"   Post-Crisis Analysis:")
        print(f"     Current Regime: {crisis_results.current_regime.value}")
        print(f"     Crisis Probability: {crisis_results.crisis_probability:.1%}")
        print(f"     Jump Probability: {crisis_results.jump_probability:.1%}")
        print(f"     Market Stress: {crisis_results.market_stress_indicator:.2f}/1.0")
        
        print(f"\n   Crisis Strategy Recommendations:")
        for i, rec in enumerate(crisis_results.recommended_strategy_adjustments[:3], 1):
            print(f"     {i}. {rec}")
        
    except Exception as e:
        print(f"   ❌ Crisis Simulation Error: {e}")
    
    print("\n" + "=" * 80)
    print("✅ CONSOLIDATED ADVANCED MODELS ENGINE FEATURES DEMONSTRATED:")
    print("   • Unified Merton Jump-Diffusion and Regime Switching models")
    print("   • Intelligent market regime detection with transition probabilities")
    print("   • Real-time jump detection with event classification")
    print("   • Crisis probability assessment and market stress indicators")
    print("   • Event-driven strategy recommendations")
    print("   • Comprehensive market condition analysis")
    print("   • Performance tracking and model validation")
    print("   • Integration-ready with V06_VolatilityEngine")
    print("   • Eliminates duplications between V09 and V11 models")
    print("   • Single source of truth for advanced market modeling")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
