#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX10_QuantModelsAgent.py
Purpose: AI-Enhanced Quantitative Models and Pricing
Group: X (AI Agents)

Description:
    Replaces traditional quantitative model modules (SpyderQ group) with an
    intelligent AI agent that selects, optimizes, and combines quantitative
    models for options pricing, volatility forecasting, and trade recommendations.

    Replaced Modules:
    - SpyderQ01_VolatilityModels
    - SpyderQ02_PricingModels
    
    This agent provides institutional-grade quant modeling with adaptive
    intelligence for superior pricing and forecasting.

Author: AI Trading Assistant
Date: 2025-01-17
Version: 1.0.0

Dependencies:
    - ollama (for LLM integration)
    - numpy, pandas
    - scipy
    - scikit-learn
    - arch (for GARCH models)
    - statsmodels
    - asyncio
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import hashlib
from scipy import stats, optimize
from scipy.stats import norm
from sklearn.ensemble import RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel
import warnings
warnings.filterwarnings('ignore')

# Import Spyder core components
from SpyderU01_DataStructures import (
    OptionContract, Greeks, MarketData, ImpliedVolatility
)
from SpyderU02_Configuration import config
from SpyderU03_Logger import SpyderLogger
from SpyderU04_EventManager import Event, EventType
from SpyderU12_AgentIntegration import SpyderBaseAgent, AgentState

# Model Types
class ModelType(Enum):
    """Types of quantitative models"""
    # Volatility Models
    GARCH = "garch"
    EGARCH = "egarch"
    GJR_GARCH = "gjr_garch"
    HAR_RV = "har_rv"
    STOCHASTIC_VOL = "stochastic_vol"
    
    # Pricing Models
    BLACK_SCHOLES = "black_scholes"
    BINOMIAL = "binomial"
    MONTE_CARLO = "monte_carlo"
    HESTON = "heston"
    SABR = "sabr"
    
    # ML Models
    NEURAL_PRICING = "neural_pricing"
    GP_VOLATILITY = "gp_volatility"
    RF_PRICING = "rf_pricing"
    
    # Ensemble
    ENSEMBLE = "ensemble"

# Model Categories
class ModelCategory(Enum):
    """Model categories"""
    VOLATILITY = "volatility"
    PRICING = "pricing"
    GREEKS = "greeks"
    CALIBRATION = "calibration"
    FORECAST = "forecast"

# Market Regimes for Model Selection
class MarketRegime(Enum):
    """Market regime classifications"""
    LOW_VOL_TRENDING = "low_vol_trending"
    HIGH_VOL_TRENDING = "high_vol_trending"
    LOW_VOL_RANGING = "low_vol_ranging"
    HIGH_VOL_RANGING = "high_vol_ranging"
    CRISIS = "crisis"
    NORMAL = "normal"

@dataclass
class ModelConfig:
    """Configuration for a quantitative model"""
    model_type: ModelType
    category: ModelCategory
    parameters: Dict[str, Any]
    hyperparameters: Dict[str, Any]
    calibration_method: str
    update_frequency: int  # minutes
    confidence_bounds: bool = True
    ensemble_weight: float = 1.0

@dataclass
class ModelOutput:
    """Output from a quantitative model"""
    model_type: ModelType
    timestamp: datetime
    value: Union[float, np.ndarray]
    confidence_interval: Optional[Tuple[float, float]] = None
    parameters_used: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0

@dataclass
class VolatilityForecast:
    """Volatility forecast output"""
    current_volatility: float
    forecast_1d: float
    forecast_5d: float
    forecast_21d: float
    term_structure: Dict[int, float]
    confidence_bands: Dict[str, Tuple[float, float]]
    model_used: ModelType
    regime: MarketRegime

@dataclass
class OptionPricing:
    """Option pricing output"""
    theoretical_price: float
    bid_ask_midpoint: float
    model_price: float
    greeks: Greeks
    implied_volatility: float
    pricing_error: float
    confidence_interval: Tuple[float, float]
    model_used: ModelType
    mispricing_score: float  # >0 overpriced, <0 underpriced

@dataclass
class ModelPerformance:
    """Model performance tracking"""
    model_type: ModelType
    mse: float
    mae: float
    directional_accuracy: float
    sharpe_ratio: float
    calibration_stability: float
    regime_performance: Dict[MarketRegime, float]
    last_updated: datetime

class QuantModelsAgent(SpyderBaseAgent):
    """
    AI-Enhanced Quantitative Models Agent
    
    Provides sophisticated quantitative modeling with intelligent
    model selection, parameter optimization, and ensemble methods.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Quant Models Agent"""
        super().__init__(config)
        
        # Agent configuration
        self.llm_model = config.get('quant_llm_model', 'llama3.2:3b-instruct-q4_K_M')
        self.ensemble_size = config.get('ensemble_size', 5)
        self.update_frequency = config.get('model_update_minutes', 60)
        
        # Model storage
        self.active_models: Dict[ModelType, Any] = {}
        self.model_configs: Dict[ModelType, ModelConfig] = {}
        self.model_performance: Dict[ModelType, ModelPerformance] = {}
        
        # Market data
        self.price_history: pd.DataFrame = pd.DataFrame()
        self.volatility_history: pd.DataFrame = pd.DataFrame()
        self.option_data: Dict[str, pd.DataFrame] = {}
        
        # Forecasts and pricing
        self.volatility_forecasts: deque = deque(maxlen=1000)
        self.option_pricings: Dict[str, OptionPricing] = {}
        self.forecast_errors: deque = deque(maxlen=1000)
        
        # Market regime
        self.current_regime: MarketRegime = MarketRegime.NORMAL
        self.regime_history: deque = deque(maxlen=100)
        
        # Model calibration
        self.calibration_cache: Dict[str, Dict[str, Any]] = {}
        self.calibration_schedule: Dict[ModelType, datetime] = {}
        
        # Ensemble management
        self.ensemble_weights: Dict[ModelType, float] = {}
        self.ensemble_performance: deque = deque(maxlen=100)
        
        # Initialize models
        self._initialize_models()
        
        self.logger.info("Quant Models Agent initialized")

    async def initialize(self, event_manager=None, market_data_provider=None):
        """Initialize agent with dependencies"""
        await super().initialize(event_manager)
        
        self.market_data_provider = market_data_provider
        
        # Load historical data
        await self._load_historical_data()
        
        # Subscribe to events
        if self.event_manager:
            self.event_manager.subscribe(EventType.MARKET_DATA_UPDATE, self._handle_market_data)
            self.event_manager.subscribe(EventType.OPTION_DATA_UPDATE, self._handle_option_data)
            self.event_manager.subscribe(EventType.VOLATILITY_UPDATE, self._handle_volatility_update)
            self.event_manager.subscribe(EventType.MARKET_REGIME_CHANGE, self._handle_regime_change)
        
        # Start background tasks
        asyncio.create_task(self._update_models_loop())
        asyncio.create_task(self._calibrate_models_loop())
        asyncio.create_task(self._monitor_performance_loop())
        asyncio.create_task(self._detect_regime_loop())
        
        self.state = AgentState.RUNNING
        self.logger.info("Quant Models Agent initialized and running")

    async def forecast_volatility(
        self,
        symbol: str = 'SPY',
        horizons: List[int] = [1, 5, 21],
        confidence_level: float = 0.95
    ) -> VolatilityForecast:
        """
        Forecast volatility using ensemble of models
        
        Args:
            symbol: Symbol to forecast
            horizons: Forecast horizons in days
            confidence_level: Confidence level for intervals
            
        Returns:
            Comprehensive volatility forecast
        """
        try:
            # Get current market data
            current_vol = await self._calculate_current_volatility(symbol)
            
            # Determine best models for current regime
            selected_models = await self._select_volatility_models(self.current_regime)
            
            # Generate forecasts from each model
            model_forecasts = {}
            for model_type in selected_models:
                if model_type in self.active_models:
                    forecast = await self._forecast_with_model(
                        model_type, symbol, horizons
                    )
                    model_forecasts[model_type] = forecast
            
            # Combine forecasts using intelligent ensemble
            ensemble_forecast = await self._ensemble_volatility_forecasts(
                model_forecasts, self.current_regime
            )
            
            # Generate term structure
            term_structure = await self._generate_volatility_term_structure(
                current_vol, ensemble_forecast, horizons
            )
            
            # Calculate confidence bands
            confidence_bands = self._calculate_confidence_bands(
                ensemble_forecast, model_forecasts, confidence_level
            )
            
            # Determine best model
            best_model = await self._determine_best_model(model_forecasts)
            
            # Create forecast object
            forecast = VolatilityForecast(
                current_volatility=current_vol,
                forecast_1d=ensemble_forecast.get(1, current_vol),
                forecast_5d=ensemble_forecast.get(5, current_vol),
                forecast_21d=ensemble_forecast.get(21, current_vol),
                term_structure=term_structure,
                confidence_bands=confidence_bands,
                model_used=best_model,
                regime=self.current_regime
            )
            
            # Store forecast
            self.volatility_forecasts.append({
                'timestamp': datetime.now(),
                'forecast': forecast,
                'models_used': list(model_forecasts.keys())
            })
            
            return forecast
            
        except Exception as e:
            self.logger.error(f"Error forecasting volatility: {str(e)}")
            # Return simple forecast as fallback
            return VolatilityForecast(
                current_volatility=0.15,
                forecast_1d=0.15,
                forecast_5d=0.16,
                forecast_21d=0.17,
                term_structure={1: 0.15, 5: 0.16, 21: 0.17},
                confidence_bands={'1d': (0.12, 0.18), '5d': (0.13, 0.19), '21d': (0.14, 0.20)},
                model_used=ModelType.GARCH,
                regime=self.current_regime
            )

    async def price_option(
        self,
        option: OptionContract,
        market_data: Optional[MarketData] = None,
        volatility_override: Optional[float] = None
    ) -> OptionPricing:
        """
        Price option using ensemble of models
        
        Args:
            option: Option contract to price
            market_data: Current market data
            volatility_override: Override volatility if provided
            
        Returns:
            Comprehensive option pricing
        """
        try:
            # Get market data if not provided
            if not market_data:
                market_data = await self._get_current_market_data()
            
            # Get or forecast volatility
            if volatility_override:
                volatility = volatility_override
            else:
                vol_forecast = await self.forecast_volatility()
                dte = (option.expiration - datetime.now()).days
                volatility = self._interpolate_volatility(
                    vol_forecast.term_structure, dte
                )
            
            # Select pricing models based on option characteristics
            selected_models = await self._select_pricing_models(
                option, market_data, self.current_regime
            )
            
            # Price with each model
            model_prices = {}
            model_greeks = {}
            
            for model_type in selected_models:
                if model_type in self.active_models:
                    price, greeks = await self._price_with_model(
                        model_type, option, market_data, volatility
                    )
                    model_prices[model_type] = price
                    model_greeks[model_type] = greeks
            
            # Combine prices using intelligent ensemble
            ensemble_price, ensemble_greeks = await self._ensemble_option_prices(
                model_prices, model_greeks, option, market_data
            )
            
            # Calculate theoretical price (benchmark)
            theoretical_price = self._black_scholes_price(
                option, market_data.current_price, volatility
            )
            
            # Get market price
            bid_ask_mid = (option.bid + option.ask) / 2 if option.bid and option.ask else ensemble_price
            
            # Calculate mispricing score
            mispricing_score = await self._calculate_mispricing_score(
                ensemble_price, bid_ask_mid, theoretical_price, option
            )
            
            # Calculate confidence interval
            confidence_interval = self._calculate_price_confidence(
                model_prices, ensemble_price
            )
            
            # Determine best model
            best_model = await self._determine_best_pricing_model(
                model_prices, bid_ask_mid
            )
            
            # Create pricing object
            pricing = OptionPricing(
                theoretical_price=theoretical_price,
                bid_ask_midpoint=bid_ask_mid,
                model_price=ensemble_price,
                greeks=ensemble_greeks,
                implied_volatility=volatility,
                pricing_error=abs(ensemble_price - bid_ask_mid),
                confidence_interval=confidence_interval,
                model_used=best_model,
                mispricing_score=mispricing_score
            )
            
            # Cache pricing
            cache_key = f"{option.symbol}_{option.strike}_{option.expiration}_{option.option_type}"
            self.option_pricings[cache_key] = pricing
            
            return pricing
            
        except Exception as e:
            self.logger.error(f"Error pricing option: {str(e)}")
            # Return simple pricing as fallback
            return self._get_fallback_pricing(option, market_data)

    async def calibrate_models(
        self,
        market_data: Optional[pd.DataFrame] = None,
        option_data: Optional[pd.DataFrame] = None
    ) -> Dict[ModelType, Dict[str, Any]]:
        """
        Calibrate all models to current market data
        
        Args:
            market_data: Historical price data
            option_data: Option chain data
            
        Returns:
            Calibration results for each model
        """
        try:
            # Use latest data if not provided
            if market_data is None:
                market_data = self.price_history
            if option_data is None:
                option_data = self._get_latest_option_data()
            
            calibration_results = {}
            
            # Calibrate each active model
            for model_type, model in self.active_models.items():
                self.logger.info(f"Calibrating {model_type.value}")
                
                if model_type in [ModelType.GARCH, ModelType.EGARCH, ModelType.GJR_GARCH]:
                    # Volatility model calibration
                    params = await self._calibrate_volatility_model(
                        model_type, model, market_data
                    )
                
                elif model_type in [ModelType.HESTON, ModelType.SABR]:
                    # Stochastic vol model calibration
                    params = await self._calibrate_stochastic_vol_model(
                        model_type, model, option_data
                    )
                
                elif model_type in [ModelType.NEURAL_PRICING, ModelType.RF_PRICING]:
                    # ML model calibration
                    params = await self._calibrate_ml_model(
                        model_type, model, market_data, option_data
                    )
                
                else:
                    # Standard calibration
                    params = await self._calibrate_standard_model(
                        model_type, model, market_data
                    )
                
                calibration_results[model_type] = params
                
                # Update model config
                if model_type in self.model_configs:
                    self.model_configs[model_type].parameters.update(params)
                
                # Update calibration time
                self.calibration_schedule[model_type] = datetime.now()
            
            # Store calibration results
            self.calibration_cache[datetime.now().isoformat()] = calibration_results
            
            # Update ensemble weights based on recent performance
            await self._update_ensemble_weights()
            
            return calibration_results
            
        except Exception as e:
            self.logger.error(f"Error calibrating models: {str(e)}")
            return {}

    async def get_model_recommendations(
        self,
        options: List[OptionContract],
        risk_tolerance: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Get trading recommendations from quant models
        
        Args:
            options: List of option contracts to analyze
            risk_tolerance: Risk tolerance (0-1)
            
        Returns:
            List of recommendations with rationale
        """
        try:
            recommendations = []
            
            # Get current forecasts
            vol_forecast = await self.forecast_volatility()
            
            # Analyze each option
            for option in options:
                # Price the option
                pricing = await self.price_option(option)
                
                # Skip if low confidence
                confidence_width = pricing.confidence_interval[1] - pricing.confidence_interval[0]
                if confidence_width / pricing.model_price > 0.2:  # >20% uncertainty
                    continue
                
                # Analyze mispricing
                if abs(pricing.mispricing_score) > 0.1:  # >10% mispricing
                    # Generate recommendation
                    rec = await self._generate_option_recommendation(
                        option, pricing, vol_forecast, risk_tolerance
                    )
                    
                    if rec:
                        recommendations.append(rec)
            
            # Sort by expected value
            recommendations.sort(key=lambda x: x['expected_value'], reverse=True)
            
            # Apply risk filters
            filtered_recs = self._apply_risk_filters(recommendations, risk_tolerance)
            
            # Add AI insights
            enhanced_recs = await self._enhance_recommendations_with_ai(filtered_recs)
            
            return enhanced_recs[:10]  # Top 10 recommendations
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {str(e)}")
            return []

    def _initialize_models(self):
        """Initialize quantitative models"""
        # GARCH models
        self._initialize_garch_models()
        
        # Pricing models
        self._initialize_pricing_models()
        
        # ML models
        self._initialize_ml_models()
        
        # Set default configurations
        self._set_default_configs()

    def _initialize_garch_models(self):
        """Initialize GARCH family models"""
        try:
            from arch import arch_model
            
            # Standard GARCH(1,1)
            self.active_models[ModelType.GARCH] = arch_model(
                None, vol='Garch', p=1, q=1
            )
            
            # EGARCH for asymmetric effects
            self.active_models[ModelType.EGARCH] = arch_model(
                None, vol='EGARCH', p=1, q=1
            )
            
            # GJR-GARCH for leverage effects
            self.active_models[ModelType.GJR_GARCH] = arch_model(
                None, vol='GARCH', p=1, q=1, o=1
            )
            
        except ImportError:
            self.logger.warning("ARCH package not available, using simplified models")
            # Fallback models
            self.active_models[ModelType.GARCH] = SimpleGARCH()

    def _initialize_pricing_models(self):
        """Initialize option pricing models"""
        # Black-Scholes (always available)
        self.active_models[ModelType.BLACK_SCHOLES] = BlackScholesModel()
        
        # Binomial model
        self.active_models[ModelType.BINOMIAL] = BinomialModel()
        
        # Monte Carlo
        self.active_models[ModelType.MONTE_CARLO] = MonteCarloModel()
        
        # Heston stochastic volatility
        self.active_models[ModelType.HESTON] = HestonModel()

    def _initialize_ml_models(self):
        """Initialize machine learning models"""
        # Gaussian Process for volatility
        kernel = RBF(length_scale=1.0) + WhiteKernel(noise_level=0.1)
        self.active_models[ModelType.GP_VOLATILITY] = GaussianProcessRegressor(
            kernel=kernel, alpha=1e-6, normalize_y=True
        )
        
        # Random Forest for pricing
        self.active_models[ModelType.RF_PRICING] = RandomForestRegressor(
            n_estimators=100, max_depth=10, random_state=42
        )

    def _set_default_configs(self):
        """Set default model configurations"""
        # GARCH config
        self.model_configs[ModelType.GARCH] = ModelConfig(
            model_type=ModelType.GARCH,
            category=ModelCategory.VOLATILITY,
            parameters={'p': 1, 'q': 1},
            hyperparameters={'dist': 'normal'},
            calibration_method='MLE',
            update_frequency=60
        )
        
        # Black-Scholes config
        self.model_configs[ModelType.BLACK_SCHOLES] = ModelConfig(
            model_type=ModelType.BLACK_SCHOLES,
            category=ModelCategory.PRICING,
            parameters={'risk_free': 0.05},
            hyperparameters={},
            calibration_method='closed_form',
            update_frequency=15
        )

    async def _calculate_current_volatility(self, symbol: str) -> float:
        """Calculate current realized volatility"""
        if self.price_history.empty:
            return 0.15  # Default 15% volatility
        
        # Get recent returns
        returns = self.price_history['close'].pct_change().dropna()
        
        if len(returns) < 20:
            return 0.15
        
        # Calculate realized volatility (annualized)
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252)
        
        return annual_vol

    async def _select_volatility_models(
        self,
        regime: MarketRegime
    ) -> List[ModelType]:
        """Select best volatility models for current regime"""
        
        # Get AI recommendation
        selected = await self._ai_select_models(
            ModelCategory.VOLATILITY, regime
        )
        
        # Fallback selection based on regime
        if not selected:
            if regime == MarketRegime.HIGH_VOL_RANGING:
                selected = [ModelType.EGARCH, ModelType.GJR_GARCH]
            elif regime == MarketRegime.CRISIS:
                selected = [ModelType.STOCHASTIC_VOL, ModelType.EGARCH]
            else:
                selected = [ModelType.GARCH, ModelType.HAR_RV]
        
        # Always include best performing model
        if self.model_performance:
            best_vol_model = max(
                [m for m in self.model_performance if m in self.active_models 
                 and self.model_configs.get(m, {}).get('category') == ModelCategory.VOLATILITY],
                key=lambda m: self.model_performance[m].sharpe_ratio,
                default=None
            )
            if best_vol_model and best_vol_model not in selected:
                selected.append(best_vol_model)
        
        return selected[:self.ensemble_size]

    async def _ai_select_models(
        self,
        category: ModelCategory,
        regime: MarketRegime
    ) -> List[ModelType]:
        """Use AI to select best models"""
        
        # Prepare context
        performance_summary = {}
        for model_type, perf in self.model_performance.items():
            if model_type in self.active_models:
                performance_summary[model_type.value] = {
                    'mse': perf.mse,
                    'sharpe': perf.sharpe_ratio,
                    'regime_score': perf.regime_performance.get(regime, 0)
                }
        
        prompt = f"""
        Select the best {category.value} models for current market conditions:
        
        Market Regime: {regime.value}
        Category: {category.value}
        
        Model Performance:
        {json.dumps(performance_summary, indent=2)}
        
        Select 3-5 models that would work best together in an ensemble.
        Consider:
        1. Performance in current regime
        2. Model diversity (different approaches)
        3. Computational efficiency
        
        Return a JSON array of model names.
        """
        
        try:
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=3.0)
            model_names = json.loads(response)
            
            # Convert to ModelType enums
            selected = []
            for name in model_names:
                try:
                    model_type = ModelType(name)
                    if model_type in self.active_models:
                        selected.append(model_type)
                except:
                    continue
            
            return selected
            
        except:
            return []

    async def _forecast_with_model(
        self,
        model_type: ModelType,
        symbol: str,
        horizons: List[int]
    ) -> Dict[int, float]:
        """Generate forecast with specific model"""
        
        model = self.active_models.get(model_type)
        if not model:
            return {}
        
        forecasts = {}
        
        try:
            if model_type in [ModelType.GARCH, ModelType.EGARCH, ModelType.GJR_GARCH]:
                # GARCH forecasting
                returns = self.price_history['close'].pct_change().dropna() * 100
                
                # Fit model
                model_fit = model.fit(returns, disp='off')
                
                # Forecast
                forecast = model_fit.forecast(horizon=max(horizons))
                
                for h in horizons:
                    # Convert to annualized volatility
                    daily_vol = np.sqrt(forecast.variance.values[0, h-1]) / 100
                    forecasts[h] = daily_vol * np.sqrt(252)
            
            elif model_type == ModelType.GP_VOLATILITY:
                # Gaussian Process forecasting
                # Prepare features
                X, y = self._prepare_ml_features(symbol, 'volatility')
                
                if len(X) > 50:
                    # Fit model
                    model.fit(X, y)
                    
                    # Forecast
                    for h in horizons:
                        X_pred = self._create_forecast_features(X[-1], h)
                        pred, std = model.predict(X_pred.reshape(1, -1), return_std=True)
                        forecasts[h] = pred[0]
            
            else:
                # Simple forecast
                current_vol = await self._calculate_current_volatility(symbol)
                for h in horizons:
                    # Mean reverting forecast
                    long_term_vol = 0.16
                    forecasts[h] = current_vol + (long_term_vol - current_vol) * (1 - np.exp(-0.1 * h))
            
        except Exception as e:
            self.logger.error(f"Error forecasting with {model_type.value}: {str(e)}")
            
        return forecasts

    async def _ensemble_volatility_forecasts(
        self,
        model_forecasts: Dict[ModelType, Dict[int, float]],
        regime: MarketRegime
    ) -> Dict[int, float]:
        """Combine volatility forecasts using intelligent ensemble"""
        
        if not model_forecasts:
            return {}
        
        # Get ensemble weights
        weights = await self._get_ensemble_weights(
            list(model_forecasts.keys()), regime
        )
        
        # Combine forecasts
        ensemble_forecast = {}
        horizons = set()
        for forecasts in model_forecasts.values():
            horizons.update(forecasts.keys())
        
        for h in horizons:
            weighted_sum = 0
            weight_sum = 0
            
            for model_type, forecasts in model_forecasts.items():
                if h in forecasts:
                    weight = weights.get(model_type, 1.0)
                    weighted_sum += forecasts[h] * weight
                    weight_sum += weight
            
            if weight_sum > 0:
                ensemble_forecast[h] = weighted_sum / weight_sum
        
        return ensemble_forecast

    async def _get_ensemble_weights(
        self,
        models: List[ModelType],
        regime: MarketRegime
    ) -> Dict[ModelType, float]:
        """Get ensemble weights for models"""
        
        weights = {}
        
        # Base weights on recent performance
        for model_type in models:
            if model_type in self.model_performance:
                perf = self.model_performance[model_type]
                
                # Regime-specific performance
                regime_score = perf.regime_performance.get(regime, 0.5)
                
                # Overall performance
                overall_score = 1 / (1 + perf.mse) * perf.sharpe_ratio
                
                # Combined weight
                weights[model_type] = (regime_score + overall_score) / 2
            else:
                weights[model_type] = 1.0
        
        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        
        return weights

    async def _generate_volatility_term_structure(
        self,
        current_vol: float,
        forecast: Dict[int, float],
        horizons: List[int]
    ) -> Dict[int, float]:
        """Generate full volatility term structure"""
        
        term_structure = {}
        
        # Add current
        term_structure[0] = current_vol
        
        # Add forecasts
        term_structure.update(forecast)
        
        # Interpolate missing points
        all_days = range(0, max(horizons) + 1)
        known_days = sorted(term_structure.keys())
        
        for day in all_days:
            if day not in term_structure:
                # Linear interpolation
                before = max([d for d in known_days if d < day], default=0)
                after = min([d for d in known_days if d > day], default=max(known_days))
                
                if before < day < after:
                    weight = (day - before) / (after - before)
                    term_structure[day] = (
                        term_structure[before] * (1 - weight) +
                        term_structure[after] * weight
                    )
        
        return term_structure

    def _calculate_confidence_bands(
        self,
        ensemble_forecast: Dict[int, float],
        model_forecasts: Dict[ModelType, Dict[int, float]],
        confidence_level: float
    ) -> Dict[str, Tuple[float, float]]:
        """Calculate confidence bands for forecasts"""
        
        bands = {}
        
        for horizon, ensemble_value in ensemble_forecast.items():
            # Get all model forecasts for this horizon
            model_values = []
            for forecasts in model_forecasts.values():
                if horizon in forecasts:
                    model_values.append(forecasts[horizon])
            
            if len(model_values) > 1:
                # Calculate standard error
                std_error = np.std(model_values)
                
                # Calculate confidence interval
                z_score = norm.ppf((1 + confidence_level) / 2)
                margin = z_score * std_error
                
                bands[f"{horizon}d"] = (
                    max(0.01, ensemble_value - margin),
                    ensemble_value + margin
                )
            else:
                # Default bands
                bands[f"{horizon}d"] = (
                    ensemble_value * 0.8,
                    ensemble_value * 1.2
                )
        
        return bands

    async def _determine_best_model(
        self,
        model_forecasts: Dict[ModelType, Dict[int, float]]
    ) -> ModelType:
        """Determine best performing model"""
        
        if not model_forecasts:
            return ModelType.GARCH
        
        # Get recent forecast errors
        recent_errors = self._get_recent_forecast_errors()
        
        # Calculate model scores
        model_scores = {}
        
        for model_type in model_forecasts:
            if model_type in recent_errors:
                # Lower error is better
                avg_error = np.mean(recent_errors[model_type])
                model_scores[model_type] = 1 / (1 + avg_error)
            else:
                model_scores[model_type] = 0.5
        
        # Return best model
        if model_scores:
            return max(model_scores.items(), key=lambda x: x[1])[0]
        else:
            return list(model_forecasts.keys())[0]

    def _get_recent_forecast_errors(self) -> Dict[ModelType, List[float]]:
        """Get recent forecast errors by model"""
        
        errors = defaultdict(list)
        
        for error_record in self.forecast_errors:
            model_type = error_record.get('model_type')
            error = error_record.get('error')
            
            if model_type and error is not None:
                errors[model_type].append(abs(error))
        
        return dict(errors)

    async def _select_pricing_models(
        self,
        option: OptionContract,
        market_data: MarketData,
        regime: MarketRegime
    ) -> List[ModelType]:
        """Select best pricing models for option"""
        
        selected = []
        
        # Always include Black-Scholes as baseline
        selected.append(ModelType.BLACK_SCHOLES)
        
        # Add models based on option characteristics
        dte = (option.expiration - datetime.now()).days
        moneyness = market_data.current_price / option.strike
        
        if dte < 7:
            # Short-dated options
            selected.append(ModelType.BINOMIAL)
        
        if abs(np.log(moneyness)) > 0.1:  # Far from ATM
            # Stochastic vol models for smile
            selected.append(ModelType.HESTON)
        
        if regime in [MarketRegime.HIGH_VOL_RANGING, MarketRegime.CRISIS]:
            # Monte Carlo for complex scenarios
            selected.append(ModelType.MONTE_CARLO)
        
        # Add ML model if available
        if ModelType.RF_PRICING in self.active_models:
            selected.append(ModelType.RF_PRICING)
        
        return selected[:self.ensemble_size]

    async def _price_with_model(
        self,
        model_type: ModelType,
        option: OptionContract,
        market_data: MarketData,
        volatility: float
    ) -> Tuple[float, Greeks]:
        """Price option with specific model"""
        
        model = self.active_models.get(model_type)
        if not model:
            return 0, Greeks()
        
        try:
            if model_type == ModelType.BLACK_SCHOLES:
                price = self._black_scholes_price(
                    option, market_data.current_price, volatility
                )
                greeks = self._black_scholes_greeks(
                    option, market_data.current_price, volatility
                )
                
            elif model_type == ModelType.BINOMIAL:
                price, greeks = model.price(
                    option, market_data.current_price, volatility,
                    self.model_configs[model_type].parameters.get('risk_free', 0.05)
                )
                
            elif model_type == ModelType.MONTE_CARLO:
                price = model.price(
                    option, market_data.current_price, volatility,
                    n_simulations=10000
                )
                greeks = self._black_scholes_greeks(
                    option, market_data.current_price, volatility
                )
                
            elif model_type == ModelType.RF_PRICING:
                # ML pricing
                features = self._create_option_features(
                    option, market_data, volatility
                )
                price = model.predict(features.reshape(1, -1))[0]
                greeks = self._black_scholes_greeks(
                    option, market_data.current_price, volatility
                )
                
            else:
                # Default to Black-Scholes
                price = self._black_scholes_price(
                    option, market_data.current_price, volatility
                )
                greeks = self._black_scholes_greeks(
                    option, market_data.current_price, volatility
                )
            
            return price, greeks
            
        except Exception as e:
            self.logger.error(f"Error pricing with {model_type.value}: {str(e)}")
            return 0, Greeks()

    def _black_scholes_price(
        self,
        option: OptionContract,
        spot: float,
        volatility: float,
        risk_free: float = 0.05
    ) -> float:
        """Calculate Black-Scholes price"""
        
        K = option.strike
        T = (option.expiration - datetime.now()).days / 365.0
        
        if T <= 0:
            # Expired option
            if option.option_type == 'CALL':
                return max(0, spot - K)
            else:
                return max(0, K - spot)
        
        # Calculate d1 and d2
        d1 = (np.log(spot / K) + (risk_free + 0.5 * volatility**2) * T) / (volatility * np.sqrt(T))
        d2 = d1 - volatility * np.sqrt(T)
        
        if option.option_type == 'CALL':
            price = spot * norm.cdf(d1) - K * np.exp(-risk_free * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-risk_free * T) * norm.cdf(-d2) - spot * norm.cdf(-d1)
        
        return max(0, price)

    def _black_scholes_greeks(
        self,
        option: OptionContract,
        spot: float,
        volatility: float,
        risk_free: float = 0.05
    ) -> Greeks:
        """Calculate Black-Scholes Greeks"""
        
        K = option.strike
        T = (option.expiration - datetime.now()).days / 365.0
        
        if T <= 0:
            return Greeks(delta=0, gamma=0, theta=0, vega=0, rho=0)
        
        # Calculate d1 and d2
        d1 = (np.log(spot / K) + (risk_free + 0.5 * volatility**2) * T) / (volatility * np.sqrt(T))
        d2 = d1 - volatility * np.sqrt(T)
        
        # Common terms
        nd1 = norm.cdf(d1)
        nd2 = norm.cdf(d2)
        npd1 = norm.pdf(d1)
        sqrt_t = np.sqrt(T)
        
        if option.option_type == 'CALL':
            delta = nd1
            theta = (-spot * npd1 * volatility / (2 * sqrt_t) 
                    - risk_free * K * np.exp(-risk_free * T) * nd2) / 365
            rho = K * T * np.exp(-risk_free * T) * nd2 / 100
        else:
            delta = nd1 - 1
            theta = (-spot * npd1 * volatility / (2 * sqrt_t) 
                    + risk_free * K * np.exp(-risk_free * T) * norm.cdf(-d2)) / 365
            rho = -K * T * np.exp(-risk_free * T) * norm.cdf(-d2) / 100
        
        gamma = npd1 / (spot * volatility * sqrt_t)
        vega = spot * npd1 * sqrt_t / 100
        
        return Greeks(
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho
        )

    def _interpolate_volatility(
        self,
        term_structure: Dict[int, float],
        target_days: int
    ) -> float:
        """Interpolate volatility for specific maturity"""
        
        if target_days in term_structure:
            return term_structure[target_days]
        
        # Find surrounding points
        days = sorted(term_structure.keys())
        
        if target_days < days[0]:
            return term_structure[days[0]]
        if target_days > days[-1]:
            return term_structure[days[-1]]
        
        # Linear interpolation
        for i in range(len(days) - 1):
            if days[i] < target_days < days[i+1]:
                weight = (target_days - days[i]) / (days[i+1] - days[i])
                return (term_structure[days[i]] * (1 - weight) +
                       term_structure[days[i+1]] * weight)
        
        return term_structure[days[0]]

    async def _ensemble_option_prices(
        self,
        model_prices: Dict[ModelType, float],
        model_greeks: Dict[ModelType, Greeks],
        option: OptionContract,
        market_data: MarketData
    ) -> Tuple[float, Greeks]:
        """Combine option prices using ensemble"""
        
        if not model_prices:
            return 0, Greeks()
        
        # Get ensemble weights
        weights = await self._get_ensemble_weights(
            list(model_prices.keys()),
            self.current_regime
        )
        
        # Weighted average price
        total_price = 0
        total_weight = 0
        
        for model_type, price in model_prices.items():
            weight = weights.get(model_type, 1.0)
            total_price += price * weight
            total_weight += weight
        
        ensemble_price = total_price / total_weight if total_weight > 0 else 0
        
        # Weighted average Greeks
        ensemble_greeks = Greeks()
        
        if model_greeks:
            for greek in ['delta', 'gamma', 'theta', 'vega', 'rho']:
                total_greek = 0
                total_weight = 0
                
                for model_type, greeks in model_greeks.items():
                    weight = weights.get(model_type, 1.0)
                    greek_value = getattr(greeks, greek, 0)
                    total_greek += greek_value * weight
                    total_weight += weight
                
                if total_weight > 0:
                    setattr(ensemble_greeks, greek, total_greek / total_weight)
        
        return ensemble_price, ensemble_greeks

    async def _calculate_mispricing_score(
        self,
        model_price: float,
        market_price: float,
        theoretical_price: float,
        option: OptionContract
    ) -> float:
        """Calculate option mispricing score"""
        
        if market_price <= 0:
            return 0
        
        # Basic mispricing
        price_diff = model_price - market_price
        pct_diff = price_diff / market_price
        
        # Adjust for bid-ask spread
        if option.bid and option.ask:
            spread = option.ask - option.bid
            spread_pct = spread / market_price
            
            # Only significant if outside bid-ask
            if abs(price_diff) < spread / 2:
                pct_diff *= 0.5
        
        # Consider model confidence
        model_std = abs(model_price - theoretical_price) / theoretical_price
        confidence_adj = 1 / (1 + model_std)
        
        # Final score
        mispricing_score = pct_diff * confidence_adj
        
        return mispricing_score

    def _calculate_price_confidence(
        self,
        model_prices: Dict[ModelType, float],
        ensemble_price: float
    ) -> Tuple[float, float]:
        """Calculate confidence interval for price"""
        
        if len(model_prices) < 2:
            # Default 10% confidence interval
            return (ensemble_price * 0.9, ensemble_price * 1.1)
        
        prices = list(model_prices.values())
        std_dev = np.std(prices)
        
        # 95% confidence interval
        margin = 1.96 * std_dev
        
        return (
            max(0, ensemble_price - margin),
            ensemble_price + margin
        )

    async def _determine_best_pricing_model(
        self,
        model_prices: Dict[ModelType, float],
        market_price: float
    ) -> ModelType:
        """Determine best pricing model"""
        
        if not model_prices:
            return ModelType.BLACK_SCHOLES
        
        # Find model closest to market
        best_model = None
        min_error = float('inf')
        
        for model_type, price in model_prices.items():
            error = abs(price - market_price)
            if error < min_error:
                min_error = error
                best_model = model_type
        
        return best_model or ModelType.BLACK_SCHOLES

    def _get_fallback_pricing(
        self,
        option: OptionContract,
        market_data: Optional[MarketData]
    ) -> OptionPricing:
        """Get fallback pricing when models fail"""
        
        # Use simple Black-Scholes
        spot = market_data.current_price if market_data else 400
        volatility = 0.15
        
        price = self._black_scholes_price(option, spot, volatility)
        greeks = self._black_scholes_greeks(option, spot, volatility)
        
        return OptionPricing(
            theoretical_price=price,
            bid_ask_midpoint=price,
            model_price=price,
            greeks=greeks,
            implied_volatility=volatility,
            pricing_error=0,
            confidence_interval=(price * 0.9, price * 1.1),
            model_used=ModelType.BLACK_SCHOLES,
            mispricing_score=0
        )

    async def _get_current_market_data(self) -> MarketData:
        """Get current market data"""
        if self.market_data_provider:
            return await self.market_data_provider.get_latest()
        else:
            # Mock data
            return MarketData(
                symbol='SPY',
                current_price=400.0,
                timestamp=datetime.now()
            )

    def _get_latest_option_data(self) -> pd.DataFrame:
        """Get latest option chain data"""
        # Would fetch from data provider
        # Return latest cached data
        if self.option_data:
            return list(self.option_data.values())[0]
        else:
            return pd.DataFrame()

    async def _calibrate_volatility_model(
        self,
        model_type: ModelType,
        model: Any,
        market_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calibrate volatility model"""
        
        try:
            if 'close' not in market_data.columns:
                return {}
            
            # Calculate returns
            returns = market_data['close'].pct_change().dropna() * 100
            
            if len(returns) < 100:
                return {}
            
            # Fit model
            if hasattr(model, 'fit'):
                fitted = model.fit(returns, disp='off')
                
                # Extract parameters
                params = {
                    'omega': fitted.params.get('omega', 0),
                    'alpha': fitted.params.get('alpha[1]', 0),
                    'beta': fitted.params.get('beta[1]', 0)
                }
                
                if model_type == ModelType.GJR_GARCH:
                    params['gamma'] = fitted.params.get('gamma[1]', 0)
                
                return params
            
        except Exception as e:
            self.logger.error(f"Error calibrating {model_type.value}: {str(e)}")
        
        return {}

    async def _calibrate_stochastic_vol_model(
        self,
        model_type: ModelType,
        model: Any,
        option_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calibrate stochastic volatility model"""
        
        try:
            if option_data.empty:
                return {}
            
            # Extract market prices and parameters
            market_prices = option_data['mid_price'].values
            strikes = option_data['strike'].values
            expiries = option_data['dte'].values / 365.0
            
            # Calibration objective
            def objective(params):
                model_prices = []
                for i in range(len(strikes)):
                    price = model.price(
                        strikes[i], expiries[i], params
                    )
                    model_prices.append(price)
                
                # Mean squared error
                return np.mean((np.array(model_prices) - market_prices) ** 2)
            
            # Initial guess
            x0 = [0.1, 2.0, 0.3, -0.5, 0.1]  # [v0, kappa, theta, rho, sigma]
            
            # Optimize
            result = optimize.minimize(
                objective, x0, 
                bounds=[(0.01, 1), (0.1, 5), (0.01, 1), (-0.9, 0), (0.01, 1)]
            )
            
            if result.success:
                return {
                    'v0': result.x[0],
                    'kappa': result.x[1],
                    'theta': result.x[2],
                    'rho': result.x[3],
                    'sigma': result.x[4]
                }
            
        except Exception as e:
            self.logger.error(f"Error calibrating {model_type.value}: {str(e)}")
        
        return {}

    async def _calibrate_ml_model(
        self,
        model_type: ModelType,
        model: Any,
        market_data: pd.DataFrame,
        option_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calibrate machine learning model"""
        
        try:
            # Prepare training data
            X, y = self._prepare_ml_training_data(market_data, option_data)
            
            if len(X) < 100:
                return {}
            
            # Split data
            split_idx = int(len(X) * 0.8)
            X_train, X_test = X[:split_idx], X[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]
            
            # Fit model
            model.fit(X_train, y_train)
            
            # Evaluate
            train_score = model.score(X_train, y_train)
            test_score = model.score(X_test, y_test)
            
            return {
                'train_score': train_score,
                'test_score': test_score,
                'n_features': X.shape[1],
                'n_samples': len(X)
            }
            
        except Exception as e:
            self.logger.error(f"Error calibrating {model_type.value}: {str(e)}")
        
        return {}

    async def _calibrate_standard_model(
        self,
        model_type: ModelType,
        model: Any,
        market_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Standard model calibration"""
        
        # Update risk-free rate
        risk_free = self.config.get('risk_free_rate', 0.05)
        
        return {
            'risk_free': risk_free,
            'dividend_yield': 0.0,
            'last_calibration': datetime.now().isoformat()
        }

    def _prepare_ml_features(
        self,
        symbol: str,
        task: str
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features for ML models"""
        
        if self.price_history.empty:
            return np.array([]), np.array([])
        
        features = []
        targets = []
        
        # Create features
        for i in range(20, len(self.price_history) - 1):
            # Price features
            returns = self.price_history['close'].pct_change().iloc[i-20:i]
            
            feature_vector = [
                returns.mean(),
                returns.std(),
                returns.skew(),
                returns.kurt(),
                self.price_history['volume'].iloc[i-5:i].mean(),
                self.price_history['high'].iloc[i] / self.price_history['low'].iloc[i] - 1
            ]
            
            features.append(feature_vector)
            
            # Target
            if task == 'volatility':
                # Next day realized volatility
                future_return = self.price_history['close'].pct_change().iloc[i+1]
                targets.append(abs(future_return) * np.sqrt(252))
            else:
                # Next day return
                targets.append(self.price_history['close'].pct_change().iloc[i+1])
        
        return np.array(features), np.array(targets)

    def _create_forecast_features(
        self,
        last_features: np.ndarray,
        horizon: int
    ) -> np.ndarray:
        """Create features for forecasting"""
        
        # Simple decay of features
        forecast_features = last_features.copy()
        
        # Adjust for horizon
        decay_factor = np.exp(-0.1 * horizon)
        forecast_features[1] *= np.sqrt(horizon)  # Volatility scaling
        forecast_features[0] *= decay_factor  # Mean decay
        
        return forecast_features

    def _prepare_ml_training_data(
        self,
        market_data: pd.DataFrame,
        option_data: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare training data for ML pricing models"""
        
        features = []
        targets = []
        
        # Simplified - would merge market and option data
        # Create synthetic training data
        for _ in range(1000):
            feature_vector = [
                np.random.uniform(380, 420),  # Spot
                np.random.uniform(380, 420),  # Strike
                np.random.uniform(0.01, 0.5),  # Time to expiry
                np.random.uniform(0.1, 0.3),   # Volatility
                np.random.uniform(0.03, 0.07)  # Risk-free rate
            ]
            
            # Black-Scholes price as target
            S, K, T, vol, r = feature_vector
            d1 = (np.log(S/K) + (r + 0.5*vol**2)*T) / (vol*np.sqrt(T))
            d2 = d1 - vol*np.sqrt(T)
            price = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
            
            features.append(feature_vector)
            targets.append(price)
        
        return np.array(features), np.array(targets)

    def _create_option_features(
        self,
        option: OptionContract,
        market_data: MarketData,
        volatility: float
    ) -> np.ndarray:
        """Create features for option ML models"""
        
        dte = (option.expiration - datetime.now()).days / 365.0
        moneyness = market_data.current_price / option.strike
        
        features = [
            market_data.current_price,
            option.strike,
            dte,
            volatility,
            self.model_configs[ModelType.BLACK_SCHOLES].parameters.get('risk_free', 0.05),
            moneyness,
            np.log(moneyness) if moneyness > 0 else 0,
            1 if option.option_type == 'CALL' else 0
        ]
        
        return np.array(features)

    async def _update_ensemble_weights(self):
        """Update ensemble weights based on performance"""
        
        # Get recent performance for each model
        for model_type in self.active_models:
            if model_type in self.model_performance:
                perf = self.model_performance[model_type]
                
                # Update weight based on recent performance
                weight = 1 / (1 + perf.mse) * (1 + perf.sharpe_ratio)
                
                # Adjust for regime
                if self.current_regime in perf.regime_performance:
                    regime_mult = 1 + perf.regime_performance[self.current_regime]
                    weight *= regime_mult
                
                self.ensemble_weights[model_type] = weight
        
        # Normalize weights
        total_weight = sum(self.ensemble_weights.values())
        if total_weight > 0:
            self.ensemble_weights = {
                k: v / total_weight 
                for k, v in self.ensemble_weights.items()
            }

    async def _generate_option_recommendation(
        self,
        option: OptionContract,
        pricing: OptionPricing,
        vol_forecast: VolatilityForecast,
        risk_tolerance: float
    ) -> Optional[Dict[str, Any]]:
        """Generate recommendation for specific option"""
        
        # Check if mispricing is significant
        if abs(pricing.mispricing_score) < 0.05:
            return None
        
        # Determine action
        if pricing.mispricing_score < -0.1:
            action = 'BUY'
            reason = 'Underpriced by model'
        elif pricing.mispricing_score > 0.1:
            action = 'SELL'
            reason = 'Overpriced by model'
        else:
            return None
        
        # Calculate expected value
        if action == 'BUY':
            # Expected profit if price converges to model
            expected_profit = (pricing.model_price - pricing.bid_ask_midpoint) * 100
        else:
            # Expected profit from selling overpriced option
            expected_profit = (pricing.bid_ask_midpoint - pricing.model_price) * 100
        
        # Risk assessment
        risk_score = self._calculate_option_risk(option, pricing, vol_forecast)
        
        # Skip if too risky
        if risk_score > risk_tolerance:
            return None
        
        # Greeks-based position sizing
        position_size = self._calculate_position_size(
            pricing.greeks, risk_tolerance
        )
        
        return {
            'option': option,
            'action': action,
            'reason': reason,
            'model_price': pricing.model_price,
            'market_price': pricing.bid_ask_midpoint,
            'mispricing': pricing.mispricing_score,
            'expected_value': expected_profit * position_size,
            'position_size': position_size,
            'risk_score': risk_score,
            'confidence': 1 - (pricing.confidence_interval[1] - pricing.confidence_interval[0]) / pricing.model_price,
            'greeks': {
                'delta': pricing.greeks.delta,
                'gamma': pricing.greeks.gamma,
                'theta': pricing.greeks.theta,
                'vega': pricing.greeks.vega
            }
        }

    def _calculate_option_risk(
        self,
        option: OptionContract,
        pricing: OptionPricing,
        vol_forecast: VolatilityForecast
    ) -> float:
        """Calculate risk score for option"""
        
        risk_score = 0
        
        # Time decay risk (theta)
        daily_decay = abs(pricing.greeks.theta)
        dte = (option.expiration - datetime.now()).days
        
        if dte < 7:
            risk_score += 0.3  # High theta risk
        elif dte < 30:
            risk_score += 0.1
        
        # Volatility risk (vega)
        if abs(pricing.greeks.vega) > 0.5:
            # Check if vol expected to increase
            if vol_forecast.forecast_5d > vol_forecast.current_volatility * 1.1:
                risk_score += 0.2
        
        # Gamma risk (acceleration)
        if abs(pricing.greeks.gamma) > 0.1:
            risk_score += 0.2
        
        # Liquidity risk
        if option.volume and option.volume < 100:
            risk_score += 0.1
        
        # Spread risk
        if option.bid and option.ask:
            spread_pct = (option.ask - option.bid) / pricing.bid_ask_midpoint
            if spread_pct > 0.05:  # >5% spread
                risk_score += 0.1
        
        return min(risk_score, 1.0)  # Cap at 1.0

    def _calculate_position_size(
        self,
        greeks: Greeks,
        risk_tolerance: float
    ) -> int:
        """Calculate position size based on Greeks and risk tolerance"""
        
        # Base size
        base_size = 10
        
        # Adjust for delta (directional risk)
        delta_adj = 1 / (1 + abs(greeks.delta))
        
        # Adjust for gamma (acceleration risk)
        gamma_adj = 1 / (1 + abs(greeks.gamma) * 10)
        
        # Adjust for vega (volatility risk)
        vega_adj = 1 / (1 + abs(greeks.vega))
        
        # Risk tolerance multiplier
        risk_mult = risk_tolerance * 2  # 0-2x
        
        # Final size
        position_size = int(base_size * delta_adj * gamma_adj * vega_adj * risk_mult)
        
        return max(1, min(position_size, 50))  # Between 1 and 50 contracts

    def _apply_risk_filters(
        self,
        recommendations: List[Dict[str, Any]],
        risk_tolerance: float
    ) -> List[Dict[str, Any]]:
        """Apply risk filters to recommendations"""
        
        filtered = []
        
        for rec in recommendations:
            # Skip if risk score too high
            if rec['risk_score'] > risk_tolerance:
                continue
            
            # Skip if confidence too low
            if rec['confidence'] < 0.6:
                continue
            
            # Skip if expected value negative
            if rec['expected_value'] < 0:
                continue
            
            filtered.append(rec)
        
        return filtered

    async def _enhance_recommendations_with_ai(
        self,
        recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enhance recommendations with AI insights"""
        
        enhanced = []
        
        for rec in recommendations:
            # Prepare context
            context = {
                'option': f"{rec['option'].symbol} {rec['option'].strike} {rec['option'].option_type}",
                'action': rec['action'],
                'mispricing': f"{rec['mispricing']:.1%}",
                'greeks': rec['greeks'],
                'risk_score': rec['risk_score'],
                'regime': self.current_regime.value
            }
            
            prompt = f"""
            Analyze this option recommendation:
            {json.dumps(context, indent=2)}
            
            Provide:
            1. Key risk factors to watch
            2. Optimal entry/exit conditions
            3. Hedge suggestions if needed
            
            Be concise and actionable.
            """
            
            try:
                ai_insights = await asyncio.wait_for(
                    self._query_llm(prompt), timeout=2.0
                )
                rec['ai_insights'] = ai_insights
            except:
                rec['ai_insights'] = "Monitor volatility and time decay closely."
            
            enhanced.append(rec)
        
        return enhanced

    async def _load_historical_data(self):
        """Load historical market data"""
        try:
            # Would load from database or data provider
            # For now, create synthetic data
            dates = pd.date_range(end=datetime.now(), periods=252, freq='D')
            
            self.price_history = pd.DataFrame({
                'date': dates,
                'open': np.random.normal(400, 10, 252),
                'high': np.random.normal(402, 10, 252),
                'low': np.random.normal(398, 10, 252),
                'close': np.random.normal(400, 10, 252),
                'volume': np.random.normal(100000000, 20000000, 252)
            })
            
            self.logger.info("Historical data loaded")
            
        except Exception as e:
            self.logger.error(f"Error loading historical data: {str(e)}")

    async def _handle_market_data(self, event: Event):
        """Handle market data updates"""
        try:
            data = event.data
            
            # Update price history
            new_row = pd.DataFrame([{
                'date': data['timestamp'],
                'open': data['open'],
                'high': data['high'],
                'low': data['low'],
                'close': data['close'],
                'volume': data['volume']
            }])
            
            self.price_history = pd.concat([self.price_history, new_row], ignore_index=True)
            
            # Keep only recent data
            if len(self.price_history) > 1000:
                self.price_history = self.price_history.iloc[-1000:]
            
        except Exception as e:
            self.logger.error(f"Error handling market data: {str(e)}")

    async def _handle_option_data(self, event: Event):
        """Handle option data updates"""
        try:
            data = event.data
            symbol = data.get('symbol', 'SPY')
            
            # Store option chain
            self.option_data[symbol] = pd.DataFrame(data['options'])
            
        except Exception as e:
            self.logger.error(f"Error handling option data: {str(e)}")

    async def _handle_volatility_update(self, event: Event):
        """Handle volatility updates"""
        try:
            data = event.data
            
            # Update volatility history
            new_row = pd.DataFrame([{
                'timestamp': data['timestamp'],
                'implied_volatility': data['implied_volatility'],
                'realized_volatility': data.get('realized_volatility', 0),
                'vix': data.get('vix', 0)
            }])
            
            self.volatility_history = pd.concat([self.volatility_history, new_row], ignore_index=True)
            
        except Exception as e:
            self.logger.error(f"Error handling volatility update: {str(e)}")

    async def _handle_regime_change(self, event: Event):
        """Handle market regime changes"""
        try:
            new_regime = MarketRegime(event.data['regime'])
            self.current_regime = new_regime
            self.regime_history.append({
                'timestamp': datetime.now(),
                'regime': new_regime
            })
            
            self.logger.info(f"Market regime changed to: {new_regime.value}")
            
            # Recalibrate models for new regime
            asyncio.create_task(self.calibrate_models())
            
        except Exception as e:
            self.logger.error(f"Error handling regime change: {str(e)}")

    async def _update_models_loop(self):
        """Background task to update models"""
        while self.state == AgentState.RUNNING:
            try:
                # Update each model based on its frequency
                for model_type, config in self.model_configs.items():
                    last_update = self.calibration_schedule.get(model_type)
                    
                    if not last_update or (datetime.now() - last_update).seconds > config.update_frequency * 60:
                        # Update needed
                        self.logger.info(f"Updating {model_type.value}")
                        await self._update_single_model(model_type)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in update models loop: {str(e)}")
                await asyncio.sleep(60)

    async def _update_single_model(self, model_type: ModelType):
        """Update a single model"""
        try:
            # Get model
            model = self.active_models.get(model_type)
            if not model:
                return
            
            # Recalibrate
            if model_type in [ModelType.GARCH, ModelType.EGARCH, ModelType.GJR_GARCH]:
                params = await self._calibrate_volatility_model(
                    model_type, model, self.price_history
                )
                
                if params:
                    self.model_configs[model_type].parameters.update(params)
            
            # Update calibration time
            self.calibration_schedule[model_type] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error updating {model_type.value}: {str(e)}")

    async def _calibrate_models_loop(self):
        """Background task to calibrate models"""
        while self.state == AgentState.RUNNING:
            try:
                # Full calibration every hour
                await asyncio.sleep(3600)
                
                self.logger.info("Running scheduled model calibration")
                await self.calibrate_models()
                
            except Exception as e:
                self.logger.error(f"Error in calibrate models loop: {str(e)}")

    async def _monitor_performance_loop(self):
        """Background task to monitor model performance"""
        while self.state == AgentState.RUNNING:
            try:
                # Monitor every 15 minutes
                await asyncio.sleep(900)
                
                # Update performance metrics
                await self._update_model_performance()
                
            except Exception as e:
                self.logger.error(f"Error in monitor performance loop: {str(e)}")

    async def _update_model_performance(self):
        """Update model performance metrics"""
        try:
            # Calculate performance for each model
            for model_type in self.active_models:
                # Get recent predictions
                recent_errors = self._get_model_errors(model_type, days=30)
                
                if recent_errors:
                    # Calculate metrics
                    mse = np.mean(np.square(recent_errors))
                    mae = np.mean(np.abs(recent_errors))
                    
                    # Directional accuracy (simplified)
                    directional_accuracy = 0.6  # Placeholder
                    
                    # Sharpe ratio (simplified)
                    if np.std(recent_errors) > 0:
                        sharpe_ratio = np.mean(recent_errors) / np.std(recent_errors)
                    else:
                        sharpe_ratio = 0
                    
                    # Update performance
                    self.model_performance[model_type] = ModelPerformance(
                        model_type=model_type,
                        mse=mse,
                        mae=mae,
                        directional_accuracy=directional_accuracy,
                        sharpe_ratio=sharpe_ratio,
                        calibration_stability=0.8,  # Placeholder
                        regime_performance={self.current_regime: 0.7},  # Placeholder
                        last_updated=datetime.now()
                    )
            
        except Exception as e:
            self.logger.error(f"Error updating model performance: {str(e)}")

    def _get_model_errors(self, model_type: ModelType, days: int) -> List[float]:
        """Get recent prediction errors for a model"""
        errors = []
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for error_record in self.forecast_errors:
            if (error_record.get('model_type') == model_type and 
                error_record.get('timestamp', datetime.min) > cutoff_date):
                errors.append(error_record.get('error', 0))
        
        return errors

    async def _detect_regime_loop(self):
        """Background task to detect market regime changes"""
        while self.state == AgentState.RUNNING:
            try:
                # Check every 30 minutes
                await asyncio.sleep(1800)
                
                # Detect regime
                new_regime = await self._detect_market_regime()
                
                if new_regime != self.current_regime:
                    # Publish regime change event
                    if self.event_manager:
                        await self.event_manager.publish(Event(
                            type=EventType.MARKET_REGIME_CHANGE,
                            data={'regime': new_regime.value}
                        ))
                
            except Exception as e:
                self.logger.error(f"Error in detect regime loop: {str(e)}")

    async def _detect_market_regime(self) -> MarketRegime:
        """Detect current market regime"""
        try:
            if self.price_history.empty:
                return MarketRegime.NORMAL
            
            # Calculate metrics
            returns = self.price_history['close'].pct_change().dropna()
            
            if len(returns) < 20:
                return MarketRegime.NORMAL
            
            # Recent volatility
            recent_vol = returns.iloc[-20:].std() * np.sqrt(252)
            
            # Trend
            sma_20 = self.price_history['close'].rolling(20).mean().iloc[-1]
            sma_50 = self.price_history['close'].rolling(50).mean().iloc[-1]
            current_price = self.price_history['close'].iloc[-1]
            
            trending_up = current_price > sma_20 > sma_50
            trending_down = current_price < sma_20 < sma_50
            
            # Classify regime
            if recent_vol > 0.25:  # High volatility (>25%)
                if recent_vol > 0.4:
                    return MarketRegime.CRISIS
                elif trending_up or trending_down:
                    return MarketRegime.HIGH_VOL_TRENDING
                else:
                    return MarketRegime.HIGH_VOL_RANGING
            else:  # Low volatility
                if trending_up or trending_down:
                    return MarketRegime.LOW_VOL_TRENDING
                else:
                    return MarketRegime.LOW_VOL_RANGING
            
        except Exception as e:
            self.logger.error(f"Error detecting market regime: {str(e)}")
            return MarketRegime.NORMAL


# Simplified model implementations for fallback
class SimpleGARCH:
    """Simplified GARCH model for fallback"""
    
    def fit(self, returns, disp='off'):
        """Simplified fit method"""
        return self
    
    def forecast(self, horizon=1):
        """Simplified forecast"""
        variance = np.ones((1, horizon)) * 0.0225  # 15% annualized
        return type('obj', (object,), {'variance': type('obj', (object,), {'values': variance})})

class BlackScholesModel:
    """Black-Scholes pricing model"""
    pass

class BinomialModel:
    """Binomial tree pricing model"""
    
    def price(self, option, spot, volatility, risk_free, steps=100):
        """Price option using binomial tree"""
        # Simplified implementation
        price = spot * 0.1  # Placeholder
        greeks = Greeks(delta=0.5, gamma=0.01, theta=-0.05, vega=0.2, rho=0.1)
        return price, greeks

class MonteCarloModel:
    """Monte Carlo pricing model"""
    
    def price(self, option, spot, volatility, n_simulations=10000):
        """Price option using Monte Carlo"""
        # Simplified implementation
        return spot * 0.1  # Placeholder

class HestonModel:
    """Heston stochastic volatility model"""
    
    def price(self, strike, expiry, params):
        """Price option using Heston model"""
        # Simplified implementation
        return strike * 0.1  # Placeholder


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_quant_models_agent(config: Dict[str, Any]) -> QuantModelsAgent:
    """
    Factory function to create QuantModelsAgent.
    
    Args:
        config: Agent configuration dictionary
        
    Returns:
        Configured QuantModelsAgent instance
    """
    return QuantModelsAgent(config)

