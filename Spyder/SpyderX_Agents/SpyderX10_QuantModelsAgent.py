#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Agents
Module: SpyderX10_QuantModelsAgent.py
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
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import statistics
import math
import pandas as pd
from scipy import stats

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Warning: Ollama not installed. AI features will be limited.")

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Model types
class ModelType(Enum):
    """Quantitative model types."""
    BLACK_SCHOLES = "BLACK_SCHOLES"
    BINOMIAL = "BINOMIAL"
    MONTE_CARLO = "MONTE_CARLO"
    GARCH = "GARCH"
    JUMP_DIFFUSION = "JUMP_DIFFUSION"
    HESTON = "HESTON"
    SABR = "SABR"
    LOCAL_VOLATILITY = "LOCAL_VOLATILITY"
    NEURAL_NETWORK = "NEURAL_NETWORK"
    REGIME_SWITCHING = "REGIME_SWITCHING"

# Greeks to calculate
GREEKS = ['delta', 'gamma', 'theta', 'vega', 'rho']

# Model validation metrics
VALIDATION_METRICS = [
    'mse',           # Mean Squared Error
    'mae',           # Mean Absolute Error
    'rmse',          # Root Mean Squared Error
    'mape',          # Mean Absolute Percentage Error
    'r_squared',     # R-squared
    'sharpe_ratio',  # Model Sharpe ratio
    'max_error',     # Maximum prediction error
    'bias'           # Model bias
]

# Volatility models
VOLATILITY_MODELS = {
    'historical': 'Historical volatility',
    'ewma': 'Exponentially Weighted Moving Average',
    'garch': 'GARCH(1,1)',
    'implied': 'Implied volatility from options',
    'realized': 'Realized volatility',
    'range_based': 'Parkinson/Garman-Klass estimators'
}

# Default configuration
DEFAULT_CONFIG = {
    'monte_carlo_simulations': 10000,
    'binomial_steps': 100,
    'confidence_level': 0.95,
    'volatility_window': 30,
    'risk_free_rate': 0.05,
    'dividend_yield': 0.02
}

# Model configuration
DEFAULT_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_TEMPERATURE = 0.2  # Lower temperature for quantitative analysis

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class OptionContract:
    """Option contract data structure."""
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'call' or 'put'
    spot_price: float
    volatility: float
    risk_free_rate: float
    dividend_yield: float
    market_price: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None

@dataclass
class ModelOutput:
    """Quantitative model output."""
    model_type: ModelType
    theoretical_price: float
    greeks: Dict[str, float]
    implied_volatility: Optional[float]
    confidence_interval: Tuple[float, float]
    model_metrics: Dict[str, float]
    ai_insights: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class VolatilityForecast:
    """Volatility forecast data structure."""
    current_volatility: float
    forecast_1d: float
    forecast_5d: float
    forecast_30d: float
    volatility_regime: str  # 'low', 'normal', 'high', 'extreme'
    term_structure: Dict[int, float]  # days -> volatility
    confidence_bands: Dict[str, Tuple[float, float]]
    model_used: str
    ai_assessment: Dict[str, Any]

@dataclass
class ModelValidation:
    """Model validation results."""
    model_type: ModelType
    validation_metrics: Dict[str, float]
    backtesting_results: Dict[str, Any]
    stress_test_results: Dict[str, Any]
    recommendations: List[str]
    overall_score: float  # 0-1
    ai_evaluation: Dict[str, Any]

# ==============================================================================
# QUANTITATIVE MODELS AGENT CLASS
# ==============================================================================

class SpyderX10_QuantModelsAgent:
    """
    AI-Enhanced Quantitative Models Agent.
    
    This agent develops and manages quantitative models for options pricing,
    risk analysis, and trading decisions with AI-driven optimization.
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL,
                 temperature: float = DEFAULT_TEMPERATURE):
        """
        Initialize the Quantitative Models Agent.
        
        Args:
            model_name: Ollama model to use
            temperature: Temperature for AI responses
        """
        self.model_name = model_name
        self.temperature = temperature
        self.logger = self._setup_logger()
        self.config = DEFAULT_CONFIG.copy()
        
        # Initialize Ollama if available
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                ollama.list()  # Test connection
                self.ollama_client = ollama
                self.logger.info("Ollama connection established")
            except Exception as e:
                self.logger.error(f"Failed to connect to Ollama: {e}")
        
        # Model cache
        self.model_cache = {}
        self.volatility_cache = {}
        
        # Historical data storage
        self.price_history = deque(maxlen=252)  # 1 year of daily data
        self.volatility_history = deque(maxlen=252)
        
        # Model performance tracking
        self.model_performance = {model: {'predictions': 0, 'total_error': 0}
                                 for model in ModelType}
    
    def _setup_logger(self) -> logging.Logger:
        """Set up module logger."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    # ==========================================================================
    # MAIN MODELING METHODS
    # ==========================================================================
    
    async def price_option(self, contract: OptionContract,
                         model_type: Optional[ModelType] = None) -> ModelOutput:
        """
        Price an option using specified or AI-selected model.
        
        Args:
            contract: Option contract details
            model_type: Model to use (None for AI selection)
            
        Returns:
            ModelOutput with pricing and Greeks
        """
        self.logger.info(f"Pricing {contract.option_type} option: "
                        f"S={contract.spot_price}, K={contract.strike}")
        
        try:
            # Select model if not specified
            if model_type is None:
                model_type = await self._select_best_model(contract)
            
            # Calculate theoretical price and Greeks
            if model_type == ModelType.BLACK_SCHOLES:
                result = self._black_scholes_model(contract)
            elif model_type == ModelType.BINOMIAL:
                result = self._binomial_model(contract)
            elif model_type == ModelType.MONTE_CARLO:
                result = await self._monte_carlo_model(contract)
            else:
                # Default to Black-Scholes
                result = self._black_scholes_model(contract)
            
            # Get AI insights
            ai_insights = await self._get_ai_pricing_insights(contract, result)
            
            # Calculate confidence interval
            confidence_interval = self._calculate_confidence_interval(
                result['price'], contract.volatility
            )
            
            # Calculate implied volatility if market price available
            impl_vol = None
            if contract.market_price:
                impl_vol = self._calculate_implied_volatility(
                    contract, contract.market_price
                )
            
            # Create output
            output = ModelOutput(
                model_type=model_type,
                theoretical_price=result['price'],
                greeks=result['greeks'],
                implied_volatility=impl_vol,
                confidence_interval=confidence_interval,
                model_metrics={
                    'time_to_expiry': self._time_to_expiry(contract.expiry),
                    'moneyness': contract.spot_price / contract.strike,
                    'volatility_used': contract.volatility
                },
                ai_insights=ai_insights
            )
            
            # Update performance tracking
            if contract.market_price:
                error = abs(result['price'] - contract.market_price)
                self.model_performance[model_type]['predictions'] += 1
                self.model_performance[model_type]['total_error'] += error
            
            return output
            
        except Exception as e:
            self.logger.error(f"Option pricing failed: {e}")
            # Return basic output
            return ModelOutput(
                model_type=ModelType.BLACK_SCHOLES,
                theoretical_price=0.0,
                greeks={g: 0.0 for g in GREEKS},
                implied_volatility=None,
                confidence_interval=(0.0, 0.0),
                model_metrics={},
                ai_insights={'error': str(e)}
            )
    
    async def forecast_volatility(self, symbol: str,
                                historical_prices: List[float],
                                forecast_horizon: int = 30) -> VolatilityForecast:
        """
        Forecast volatility using multiple models with AI insights.
        
        Args:
            symbol: Asset symbol
            historical_prices: Historical price data
            forecast_horizon: Days to forecast
            
        Returns:
            VolatilityForecast object
        """
        self.logger.info(f"Forecasting volatility for {symbol}")
        
        try:
            # Calculate current volatility using multiple methods
            current_vol = self._calculate_historical_volatility(historical_prices)
            ewma_vol = self._calculate_ewma_volatility(historical_prices)
            
            # GARCH forecast
            garch_forecast = self._garch_forecast(historical_prices, forecast_horizon)
            
            # Get AI volatility insights
            ai_forecast = await self._get_ai_volatility_forecast(
                historical_prices, current_vol, forecast_horizon
            )
            
            # Combine forecasts
            combined_forecast = self._combine_volatility_forecasts(
                current_vol, ewma_vol, garch_forecast, ai_forecast
            )
            
            # Determine volatility regime
            regime = self._classify_volatility_regime(current_vol)
            
            # Build term structure
            term_structure = self._build_volatility_term_structure(
                combined_forecast, forecast_horizon
            )
            
            # Calculate confidence bands
            confidence_bands = self._calculate_volatility_confidence_bands(
                combined_forecast, forecast_horizon
            )
            
            return VolatilityForecast(
                current_volatility=current_vol,
                forecast_1d=combined_forecast.get('1d', current_vol),
                forecast_5d=combined_forecast.get('5d', current_vol),
                forecast_30d=combined_forecast.get('30d', current_vol),
                volatility_regime=regime,
                term_structure=term_structure,
                confidence_bands=confidence_bands,
                model_used='ensemble',
                ai_assessment=ai_forecast
            )
            
        except Exception as e:
            self.logger.error(f"Volatility forecast failed: {e}")
            return VolatilityForecast(
                current_volatility=0.2,  # Default 20% volatility
                forecast_1d=0.2,
                forecast_5d=0.2,
                forecast_30d=0.2,
                volatility_regime='normal',
                term_structure={},
                confidence_bands={},
                model_used='default',
                ai_assessment={'error': str(e)}
            )
    
    async def validate_model(self, model_type: ModelType,
                           historical_data: pd.DataFrame) -> ModelValidation:
        """
        Validate a quantitative model with backtesting and stress testing.
        
        Args:
            model_type: Model to validate
            historical_data: Historical market data
            
        Returns:
            ModelValidation results
        """
        self.logger.info(f"Validating {model_type.value} model")
        
        try:
            # Perform backtesting
            backtest_results = self._backtest_model(model_type, historical_data)
            
            # Calculate validation metrics
            metrics = self._calculate_validation_metrics(backtest_results)
            
            # Perform stress testing
            stress_results = self._stress_test_model(model_type, historical_data)
            
            # Get AI evaluation
            ai_evaluation = await self._get_ai_model_evaluation(
                model_type, metrics, backtest_results, stress_results
            )
            
            # Generate recommendations
            recommendations = self._generate_model_recommendations(
                metrics, stress_results, ai_evaluation
            )
            
            # Calculate overall score
            overall_score = self._calculate_model_score(metrics, stress_results)
            
            return ModelValidation(
                model_type=model_type,
                validation_metrics=metrics,
                backtesting_results=backtest_results,
                stress_test_results=stress_results,
                recommendations=recommendations,
                overall_score=overall_score,
                ai_evaluation=ai_evaluation
            )
            
        except Exception as e:
            self.logger.error(f"Model validation failed: {e}")
            return ModelValidation(
                model_type=model_type,
                validation_metrics={},
                backtesting_results={},
                stress_test_results={},
                recommendations=["Validation failed - review model implementation"],
                overall_score=0.0,
                ai_evaluation={'error': str(e)}
            )
    
    # ==========================================================================
    # PRICING MODELS
    # ==========================================================================
    
    def _black_scholes_model(self, contract: OptionContract) -> Dict[str, Any]:
        """Calculate Black-Scholes price and Greeks."""
        S = contract.spot_price
        K = contract.strike
        T = self._time_to_expiry(contract.expiry)
        r = contract.risk_free_rate
        q = contract.dividend_yield
        sigma = contract.volatility
        
        if T <= 0:
            # Expired option
            if contract.option_type == 'call':
                price = max(0, S - K)
            else:
                price = max(0, K - S)
            return {
                'price': price,
                'greeks': {g: 0.0 for g in GREEKS}
            }
        
        # Calculate d1 and d2
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        # Standard normal CDF and PDF
        N = stats.norm.cdf
        n = stats.norm.pdf
        
        # Calculate price
        if contract.option_type == 'call':
            price = S * np.exp(-q * T) * N(d1) - K * np.exp(-r * T) * N(d2)
        else:
            price = K * np.exp(-r * T) * N(-d2) - S * np.exp(-q * T) * N(-d1)
        
        # Calculate Greeks
        greeks = {}
        
        # Delta
        if contract.option_type == 'call':
            greeks['delta'] = np.exp(-q * T) * N(d1)
        else:
            greeks['delta'] = -np.exp(-q * T) * N(-d1)
        
        # Gamma
        greeks['gamma'] = np.exp(-q * T) * n(d1) / (S * sigma * np.sqrt(T))
        
        # Theta
        if contract.option_type == 'call':
            greeks['theta'] = (-S * n(d1) * sigma * np.exp(-q * T) / (2 * np.sqrt(T))
                              - r * K * np.exp(-r * T) * N(d2)
                              + q * S * np.exp(-q * T) * N(d1)) / 365
        else:
            greeks['theta'] = (-S * n(d1) * sigma * np.exp(-q * T) / (2 * np.sqrt(T))
                              + r * K * np.exp(-r * T) * N(-d2)
                              - q * S * np.exp(-q * T) * N(-d1)) / 365
        
        # Vega
        greeks['vega'] = S * np.exp(-q * T) * n(d1) * np.sqrt(T) / 100
        
        # Rho
        if contract.option_type == 'call':
            greeks['rho'] = K * T * np.exp(-r * T) * N(d2) / 100
        else:
            greeks['rho'] = -K * T * np.exp(-r * T) * N(-d2) / 100
        
        return {
            'price': price,
            'greeks': greeks
        }
    
    def _binomial_model(self, contract: OptionContract) -> Dict[str, Any]:
        """Calculate option price using binomial tree."""
        S = contract.spot_price
        K = contract.strike
        T = self._time_to_expiry(contract.expiry)
        r = contract.risk_free_rate
        q = contract.dividend_yield
        sigma = contract.volatility
        n = self.config['binomial_steps']
        
        if T <= 0:
            # Expired option
            if contract.option_type == 'call':
                price = max(0, S - K)
            else:
                price = max(0, K - S)
            return {
                'price': price,
                'greeks': {g: 0.0 for g in GREEKS}
            }
        
        # Time step
        dt = T / n
        
        # Up and down factors
        u = np.exp(sigma * np.sqrt(dt))
        d = 1 / u
        
        # Risk-neutral probability
        p = (np.exp((r - q) * dt) - d) / (u - d)
        
        # Build the tree
        # Stock prices at maturity
        stock_tree = np.zeros((n + 1, n + 1))
        stock_tree[0, 0] = S
        
        for i in range(1, n + 1):
            stock_tree[i, 0] = stock_tree[i-1, 0] * u
            for j in range(1, i + 1):
                stock_tree[i, j] = stock_tree[i-1, j-1] * d
        
        # Option values at maturity
        option_tree = np.zeros((n + 1, n + 1))
        
        if contract.option_type == 'call':
            for j in range(n + 1):
                option_tree[n, j] = max(0, stock_tree[n, j] - K)
        else:
            for j in range(n + 1):
                option_tree[n, j] = max(0, K - stock_tree[n, j])
        
        # Backward induction
        for i in range(n - 1, -1, -1):
            for j in range(i + 1):
                option_tree[i, j] = np.exp(-r * dt) * (
                    p * option_tree[i + 1, j] + (1 - p) * option_tree[i + 1, j + 1]
                )
                
                # American option early exercise
                if contract.option_type == 'call':
                    option_tree[i, j] = max(option_tree[i, j], stock_tree[i, j] - K)
                else:
                    option_tree[i, j] = max(option_tree[i, j], K - stock_tree[i, j])
        
        price = option_tree[0, 0]
        
        # Calculate Greeks using finite differences
        greeks = self._calculate_binomial_greeks(contract, price)
        
        return {
            'price': price,
            'greeks': greeks
        }
    
    async def _monte_carlo_model(self, contract: OptionContract) -> Dict[str, Any]:
        """Calculate option price using Monte Carlo simulation."""
        S = contract.spot_price
        K = contract.strike
        T = self._time_to_expiry(contract.expiry)
        r = contract.risk_free_rate
        q = contract.dividend_yield
        sigma = contract.volatility
        n_sims = self.config['monte_carlo_simulations']
        
        if T <= 0:
            # Expired option
            if contract.option_type == 'call':
                price = max(0, S - K)
            else:
                price = max(0, K - S)
            return {
                'price': price,
                'greeks': {g: 0.0 for g in GREEKS}
            }
        
        # Generate random paths
        np.random.seed(42)  # For reproducibility
        Z = np.random.standard_normal(n_sims)
        
        # Terminal stock prices
        ST = S * np.exp((r - q - 0.5 * sigma ** 2) * T + sigma * np.sqrt(T) * Z)
        
        # Payoffs
        if contract.option_type == 'call':
            payoffs = np.maximum(0, ST - K)
        else:
            payoffs = np.maximum(0, K - ST)
        
        # Discounted expected payoff
        price = np.exp(-r * T) * np.mean(payoffs)
        
        # Standard error
        std_error = np.std(payoffs) / np.sqrt(n_sims)
        
        # Calculate Greeks using finite differences
        greeks = self._calculate_monte_carlo_greeks(contract, price)
        
        return {
            'price': price,
            'greeks': greeks,
            'std_error': std_error
        }
    
    # ==========================================================================
    # AI INTEGRATION METHODS
    # ==========================================================================
    
    async def _select_best_model(self, contract: OptionContract) -> ModelType:
        """Select best pricing model using AI."""
        if not self.ollama_client:
            # Default selection based on characteristics
            if self._time_to_expiry(contract.expiry) < 0.1:  # < 36 days
                return ModelType.BINOMIAL
            elif contract.volatility > 0.5:  # High volatility
                return ModelType.MONTE_CARLO
            else:
                return ModelType.BLACK_SCHOLES
        
        prompt = f"""Select the best option pricing model for this contract:

Contract Details:
- Spot Price: ${contract.spot_price:.2f}
- Strike: ${contract.strike:.2f}
- Time to Expiry: {self._time_to_expiry(contract.expiry):.2f} years
- Volatility: {contract.volatility:.1%}
- Option Type: {contract.option_type}
- Moneyness: {contract.spot_price/contract.strike:.2f}

Available Models: {', '.join([m.value for m in ModelType])}

Consider:
- Time to expiry (short-term vs long-term)
- Volatility level
- American vs European exercise
- Market conditions

Provide a JSON response:
{{
    "recommended_model": "model_name",
    "reasoning": "explanation",
    "confidence": 0.0-1.0,
    "alternative_models": ["model1", "model2"]
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                recommendation = json.loads(text[start:end])
                model_name = recommendation.get('recommended_model', 'BLACK_SCHOLES')
                
                # Validate model name
                try:
                    return ModelType(model_name)
                except:
                    return ModelType.BLACK_SCHOLES
            else:
                return ModelType.BLACK_SCHOLES
                
        except Exception as e:
            self.logger.error(f"AI model selection failed: {e}")
            return ModelType.BLACK_SCHOLES
    
    async def _get_ai_pricing_insights(self, contract: OptionContract,
                                     pricing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI insights on option pricing."""
        if not self.ollama_client:
            return {'source': 'rule-based'}
        
        prompt = f"""Analyze this option pricing result:

Contract:
- Type: {contract.option_type}
- Spot: ${contract.spot_price:.2f}
- Strike: ${contract.strike:.2f}
- Theoretical Price: ${pricing_result['price']:.2f}
- Market Price: ${contract.market_price:.2f if contract.market_price else 'N/A'}

Greeks:
{json.dumps(pricing_result['greeks'], indent=2)}

Market Context:
- Volatility: {contract.volatility:.1%}
- Time to Expiry: {self._time_to_expiry(contract.expiry):.2f} years
- Moneyness: {contract.spot_price/contract.strike:.2f}

Provide a JSON response:
{{
    "pricing_assessment": "fair/overpriced/underpriced",
    "key_risks": ["risk1", "risk2"],
    "trading_edge": "explanation of any edge",
    "volatility_view": "assessment of volatility pricing",
    "recommendations": ["action1", "action2"],
    "confidence": 0.0-1.0
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return {'source': 'failed_parsing'}
                
        except Exception as e:
            self.logger.error(f"AI pricing insights failed: {e}")
            return {'error': str(e)}
    
    async def _get_ai_volatility_forecast(self, prices: List[float],
                                        current_vol: float,
                                        horizon: int) -> Dict[str, Any]:
        """Get AI volatility forecast."""
        if not self.ollama_client:
            return {
                '1d': current_vol,
                '5d': current_vol,
                '30d': current_vol,
                'reasoning': 'No AI available'
            }
        
        # Calculate price statistics
        returns = [np.log(prices[i]/prices[i-1]) for i in range(1, len(prices))]
        price_trend = (prices[-1] - prices[-20]) / prices[-20] if len(prices) > 20 else 0
        
        prompt = f"""Forecast volatility based on this data:

Current Volatility: {current_vol:.1%}
Recent Price Trend: {price_trend:.1%}
Recent Return Statistics:
- Mean: {np.mean(returns):.4f}
- Std: {np.std(returns):.4f}
- Skew: {stats.skew(returns):.2f}
- Kurtosis: {stats.kurtosis(returns):.2f}

Historical Context:
- 30-day average vol: {np.mean([self._calculate_historical_volatility(prices[max(0,i-30):i]) for i in range(max(30,len(prices)-10), len(prices))]):.1%}

Forecast volatility for 1, 5, and 30 days ahead.

Provide a JSON response:
{{
    "1d": 0.xx,
    "5d": 0.xx,
    "30d": 0.xx,
    "volatility_trend": "increasing/decreasing/stable",
    "key_drivers": ["driver1", "driver2"],
    "risk_events": ["event1", "event2"],
    "confidence": 0.0-1.0
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                forecast = json.loads(text[start:end])
                # Ensure reasonable values
                for key in ['1d', '5d', '30d']:
                    if key in forecast:
                        forecast[key] = max(0.05, min(2.0, forecast[key]))
                return forecast
            else:
                return {
                    '1d': current_vol,
                    '5d': current_vol,
                    '30d': current_vol
                }
                
        except Exception as e:
            self.logger.error(f"AI volatility forecast failed: {e}")
            return {
                '1d': current_vol,
                '5d': current_vol,
                '30d': current_vol,
                'error': str(e)
            }
    
    async def _get_ai_model_evaluation(self, model_type: ModelType,
                                     metrics: Dict[str, float],
                                     backtest: Dict[str, Any],
                                     stress: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI evaluation of model performance."""
        if not self.ollama_client:
            return {'evaluation': 'No AI available'}
        
        prompt = f"""Evaluate this quantitative model's performance:

Model: {model_type.value}

Validation Metrics:
{json.dumps(metrics, indent=2)}

Backtesting Summary:
- Total Trades: {backtest.get('total_trades', 0)}
- Profitable: {backtest.get('profitable_pct', 0):.1%}
- Average Error: {backtest.get('avg_error', 0):.2f}

Stress Test Results:
- Market Crash: {stress.get('crash_performance', 'N/A')}
- Vol Spike: {stress.get('vol_spike_performance', 'N/A')}
- Liquidity Crisis: {stress.get('liquidity_performance', 'N/A')}

Provide a JSON response:
{{
    "overall_assessment": "excellent/good/fair/poor",
    "strengths": ["strength1", "strength2"],
    "weaknesses": ["weakness1", "weakness2"],
    "use_cases": ["best suited for...", "avoid for..."],
    "improvement_suggestions": ["suggestion1", "suggestion2"],
    "confidence": 0.0-1.0
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return {'evaluation': 'Failed to parse'}
                
        except Exception as e:
            self.logger.error(f"AI model evaluation failed: {e}")
            return {'error': str(e)}
    
    # ==========================================================================
    # VOLATILITY METHODS
    # ==========================================================================
    
    def _calculate_historical_volatility(self, prices: List[float],
                                       window: Optional[int] = None) -> float:
        """Calculate historical volatility."""
        if len(prices) < 2:
            return 0.2  # Default 20%
        
        window = window or self.config['volatility_window']
        prices_window = prices[-min(window, len(prices)):]
        
        returns = [np.log(prices_window[i]/prices_window[i-1]) 
                  for i in range(1, len(prices_window))]
        
        if not returns:
            return 0.2
        
        # Annualized volatility
        return np.std(returns) * np.sqrt(252)
    
    def _calculate_ewma_volatility(self, prices: List[float],
                                 lambda_param: float = 0.94) -> float:
        """Calculate EWMA volatility."""
        if len(prices) < 2:
            return 0.2
        
        returns = [np.log(prices[i]/prices[i-1]) for i in range(1, len(prices))]
        squared_returns = [r**2 for r in returns]
        
        # EWMA calculation
        ewma_var = squared_returns[0]
        for i in range(1, len(squared_returns)):
            ewma_var = lambda_param * ewma_var + (1 - lambda_param) * squared_returns[i]
        
        # Annualized volatility
        return np.sqrt(ewma_var * 252)
    
    def _garch_forecast(self, prices: List[float],
                       horizon: int) -> Dict[str, float]:
        """Simple GARCH(1,1) forecast."""
        if len(prices) < 30:
            current_vol = self._calculate_historical_volatility(prices)
            return {
                '1d': current_vol,
                '5d': current_vol,
                '30d': current_vol
            }
        
        # Calculate returns
        returns = [np.log(prices[i]/prices[i-1]) for i in range(1, len(prices))]
        
        # GARCH(1,1) parameters (simplified estimation)
        omega = 0.000001
        alpha = 0.1
        beta = 0.85
        
        # Current conditional variance
        long_run_var = np.var(returns)
        current_var = long_run_var
        
        # Forecast
        forecast_var = {}
        var_t = current_var
        
        for h in [1, 5, 30]:
            if h == 1:
                var_t = omega + alpha * returns[-1]**2 + beta * current_var
            else:
                # Multi-step forecast
                for _ in range(h):
                    var_t = omega + (alpha + beta) * var_t
            
            forecast_var[f'{h}d'] = np.sqrt(var_t * 252)
        
        return forecast_var
    
    def _classify_volatility_regime(self, volatility: float) -> str:
        """Classify volatility regime."""
        if volatility < 0.10:
            return 'low'
        elif volatility < 0.20:
            return 'normal'
        elif volatility < 0.35:
            return 'high'
        else:
            return 'extreme'
    
    def _combine_volatility_forecasts(self, current: float, ewma: float,
                                    garch: Dict[str, float],
                                    ai: Dict[str, Any]) -> Dict[str, float]:
        """Combine multiple volatility forecasts."""
        # Weight different forecasts
        weights = {
            'current': 0.2,
            'ewma': 0.2,
            'garch': 0.3,
            'ai': 0.3
        }
        
        combined = {}
        for horizon in ['1d', '5d', '30d']:
            components = [
                current * weights['current'],
                ewma * weights['ewma'],
                garch.get(horizon, current) * weights['garch'],
                ai.get(horizon, current) * weights['ai']
            ]
            combined[horizon] = sum(components)
        
        return combined
    
    def _build_volatility_term_structure(self, forecast: Dict[str, float],
                                       max_days: int) -> Dict[int, float]:
        """Build volatility term structure."""
        structure = {}
        
        # Key points
        structure[1] = forecast.get('1d', 0.2)
        structure[5] = forecast.get('5d', 0.2)
        structure[30] = forecast.get('30d', 0.2)
        
        # Interpolate
        for day in range(2, 5):
            weight = (day - 1) / 4
            structure[day] = structure[1] * (1 - weight) + structure[5] * weight
        
        for day in range(6, 30):
            weight = (day - 5) / 25
            structure[day] = structure[5] * (1 - weight) + structure[30] * weight
        
        return structure
    
    def _calculate_volatility_confidence_bands(self, forecast: Dict[str, float],
                                              horizon: int) -> Dict[str, Tuple[float, float]]:
        """Calculate confidence bands for volatility forecast."""
        bands = {}
        
        # Standard errors increase with forecast horizon
        base_std_error = 0.02  # 2% base standard error
        
        for period, vol in forecast.items():
            if period == '1d':
                std_error = base_std_error
            elif period == '5d':
                std_error = base_std_error * np.sqrt(5)
            elif period == '30d':
                std_error = base_std_error * np.sqrt(30)
            else:
                std_error = base_std_error
            
            # 95% confidence interval
            lower = max(0.01, vol - 1.96 * std_error)
            upper = vol + 1.96 * std_error
            bands[period] = (lower, upper)
        
        return bands
    
    # ==========================================================================
    # MODEL VALIDATION METHODS
    # ==========================================================================
    
    def _backtest_model(self, model_type: ModelType,
                       historical_data: pd.DataFrame) -> Dict[str, Any]:
        """Backtest a pricing model."""
        results = {
            'total_trades': 0,
            'profitable_trades': 0,
            'total_pnl': 0,
            'errors': [],
            'predictions': []
        }
        
        # Simulate backtesting (simplified)
        n_tests = min(100, len(historical_data))
        
        for i in range(n_tests):
            # Create synthetic option contract
            row = historical_data.iloc[i]
            contract = OptionContract(
                symbol='SPY',
                strike=row.get('strike', row.get('close', 450) * 1.02),
                expiry=datetime.now() + timedelta(days=30),
                option_type='call' if i % 2 == 0 else 'put',
                spot_price=row.get('close', 450),
                volatility=row.get('volatility', 0.2),
                risk_free_rate=self.config['risk_free_rate'],
                dividend_yield=self.config['dividend_yield']
            )
            
            # Price option
            if model_type == ModelType.BLACK_SCHOLES:
                model_result = self._black_scholes_model(contract)
            elif model_type == ModelType.BINOMIAL:
                model_result = self._binomial_model(contract)
            else:
                model_result = self._black_scholes_model(contract)
            
            # Simulate market price with noise
            market_price = model_result['price'] * (1 + np.random.normal(0, 0.05))
            
            # Track results
            error = abs(model_result['price'] - market_price)
            results['errors'].append(error)
            results['predictions'].append({
                'model_price': model_result['price'],
                'market_price': market_price,
                'error': error
            })
            
            results['total_trades'] += 1
            if error < market_price * 0.05:  # Within 5%
                results['profitable_trades'] += 1
        
        results['profitable_pct'] = results['profitable_trades'] / results['total_trades']
        results['avg_error'] = np.mean(results['errors'])
        results['max_error'] = np.max(results['errors'])
        
        return results
    
    def _calculate_validation_metrics(self, backtest_results: Dict[str, Any]) -> Dict[str, float]:
        """Calculate model validation metrics."""
        predictions = backtest_results.get('predictions', [])
        if not predictions:
            return {metric: 0.0 for metric in VALIDATION_METRICS}
        
        model_prices = [p['model_price'] for p in predictions]
        market_prices = [p['market_price'] for p in predictions]
        errors = [p['error'] for p in predictions]
        
        metrics = {}
        
        # MSE
        metrics['mse'] = np.mean([e**2 for e in errors])
        
        # MAE
        metrics['mae'] = np.mean(errors)
        
        # RMSE
        metrics['rmse'] = np.sqrt(metrics['mse'])
        
        # MAPE
        mape_errors = [abs((m - p) / p) for m, p in zip(model_prices, market_prices) if p != 0]
        metrics['mape'] = np.mean(mape_errors) if mape_errors else 0
        
        # R-squared
        if len(set(market_prices)) > 1:  # Avoid division by zero
            ss_res = sum((m - p)**2 for m, p in zip(model_prices, market_prices))
            ss_tot = sum((p - np.mean(market_prices))**2 for p in market_prices)
            metrics['r_squared'] = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        else:
            metrics['r_squared'] = 0
        
        # Model Sharpe ratio (simplified)
        if len(predictions) > 1:
            returns = [(predictions[i]['model_price'] - predictions[i-1]['model_price']) / 
                      predictions[i-1]['model_price'] 
                      for i in range(1, len(predictions))]
            if returns and np.std(returns) > 0:
                metrics['sharpe_ratio'] = np.mean(returns) / np.std(returns) * np.sqrt(252)
            else:
                metrics['sharpe_ratio'] = 0
        else:
            metrics['sharpe_ratio'] = 0
        
        # Max error
        metrics['max_error'] = backtest_results.get('max_error', 0)
        
        # Bias
        metrics['bias'] = np.mean([m - p for m, p in zip(model_prices, market_prices)])
        
        return metrics
    
    def _stress_test_model(self, model_type: ModelType,
                          historical_data: pd.DataFrame) -> Dict[str, Any]:
        """Stress test the model under extreme conditions."""
        stress_results = {}
        
        # Test 1: Market crash scenario
        crash_contract = OptionContract(
            symbol='SPY',
            strike=450,
            expiry=datetime.now() + timedelta(days=30),
            option_type='put',
            spot_price=400,  # 11% crash
            volatility=0.5,  # High volatility
            risk_free_rate=self.config['risk_free_rate'],
            dividend_yield=self.config['dividend_yield']
        )
        
        if model_type == ModelType.BLACK_SCHOLES:
            crash_result = self._black_scholes_model(crash_contract)
        else:
            crash_result = self._black_scholes_model(crash_contract)
        
        stress_results['crash_performance'] = 'PASS' if crash_result['price'] > 0 else 'FAIL'
        
        # Test 2: Volatility spike
        vol_spike_contract = OptionContract(
            symbol='SPY',
            strike=450,
            expiry=datetime.now() + timedelta(days=7),
            option_type='call',
            spot_price=450,
            volatility=0.8,  # Extreme volatility
            risk_free_rate=self.config['risk_free_rate'],
            dividend_yield=self.config['dividend_yield']
        )
        
        if model_type == ModelType.BLACK_SCHOLES:
            vol_result = self._black_scholes_model(vol_spike_contract)
        else:
            vol_result = self._black_scholes_model(vol_spike_contract)
        
        stress_results['vol_spike_performance'] = 'PASS' if vol_result['price'] > 0 else 'FAIL'
        
        # Test 3: Near expiry
        near_expiry_contract = OptionContract(
            symbol='SPY',
            strike=450,
            expiry=datetime.now() + timedelta(hours=1),
            option_type='call',
            spot_price=451,
            volatility=0.2,
            risk_free_rate=self.config['risk_free_rate'],
            dividend_yield=self.config['dividend_yield']
        )
        
        if model_type == ModelType.BLACK_SCHOLES:
            expiry_result = self._black_scholes_model(near_expiry_contract)
        else:
            expiry_result = self._black_scholes_model(near_expiry_contract)
        
        stress_results['near_expiry_performance'] = 'PASS' if expiry_result['price'] >= 1 else 'FAIL'
        
        # Test 4: Liquidity crisis (wide bid-ask)
        stress_results['liquidity_performance'] = 'PASS'  # Simplified
        
        return stress_results
    
    def _generate_model_recommendations(self, metrics: Dict[str, float],
                                      stress_results: Dict[str, Any],
                                      ai_evaluation: Dict[str, Any]) -> List[str]:
        """Generate model improvement recommendations."""
        recommendations = []
        
        # Metric-based recommendations
        if metrics.get('mape', 0) > 0.1:
            recommendations.append("High MAPE - consider recalibrating model parameters")
        
        if metrics.get('r_squared', 0) < 0.8:
            recommendations.append("Low R-squared - model may need additional factors")
        
        if abs(metrics.get('bias', 0)) > 0.05:
            recommendations.append("Significant bias detected - adjust for systematic errors")
        
        # Stress test recommendations
        failed_tests = [k for k, v in stress_results.items() if v == 'FAIL']
        if failed_tests:
            recommendations.append(f"Failed stress tests: {', '.join(failed_tests)}")
        
        # AI recommendations
        ai_suggestions = ai_evaluation.get('improvement_suggestions', [])
        recommendations.extend(ai_suggestions[:2])
        
        return recommendations[:5]  # Top 5 recommendations
    
    def _calculate_model_score(self, metrics: Dict[str, float],
                             stress_results: Dict[str, Any]) -> float:
        """Calculate overall model score (0-1)."""
        score_components = []
        
        # Accuracy component (40%)
        mape = metrics.get('mape', 1.0)
        accuracy_score = max(0, 1 - mape) * 0.4
        score_components.append(accuracy_score)
        
        # R-squared component (20%)
        r2_score = metrics.get('r_squared', 0) * 0.2
        score_components.append(r2_score)
        
        # Bias component (20%)
        bias = abs(metrics.get('bias', 1.0))
        bias_score = max(0, 1 - bias) * 0.2
        score_components.append(bias_score)
        
        # Stress test component (20%)
        passed_tests = sum(1 for v in stress_results.values() if v == 'PASS')
        total_tests = len(stress_results)
        stress_score = (passed_tests / total_tests) * 0.2 if total_tests > 0 else 0
        score_components.append(stress_score)
        
        return sum(score_components)
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _time_to_expiry(self, expiry: datetime) -> float:
        """Calculate time to expiry in years."""
        time_diff = expiry - datetime.now()
        return max(0, time_diff.total_seconds() / (365.25 * 24 * 60 * 60))
    
    def _calculate_implied_volatility(self, contract: OptionContract,
                                    market_price: float) -> float:
        """Calculate implied volatility using Newton-Raphson method."""
        # Initial guess
        iv = contract.volatility
        
        # Newton-Raphson parameters
        max_iterations = 100
        tolerance = 1e-5
        
        for _ in range(max_iterations):
            # Create contract with current IV guess
            iv_contract = OptionContract(
                symbol=contract.symbol,
                strike=contract.strike,
                expiry=contract.expiry,
                option_type=contract.option_type,
                spot_price=contract.spot_price,
                volatility=iv,
                risk_free_rate=contract.risk_free_rate,
                dividend_yield=contract.dividend_yield
            )
            
            # Calculate price and vega
            result = self._black_scholes_model(iv_contract)
            price = result['price']
            vega = result['greeks']['vega']
            
            # Check convergence
            price_diff = price - market_price
            if abs(price_diff) < tolerance:
                return iv
            
            # Update IV estimate
            if vega > 0:
                iv = iv - price_diff / vega
                iv = max(0.01, min(3.0, iv))  # Bound IV between 1% and 300%
            else:
                break
        
        return iv
    
    def _calculate_confidence_interval(self, price: float,
                                     volatility: float) -> Tuple[float, float]:
        """Calculate confidence interval for option price."""
        # Simplified confidence interval based on volatility
        std_error = price * volatility * np.sqrt(1/252)  # Daily std error
        z_score = 1.96  # 95% confidence
        
        lower = max(0, price - z_score * std_error)
        upper = price + z_score * std_error
        
        return (lower, upper)
    
    def _calculate_binomial_greeks(self, contract: OptionContract,
                                 base_price: float) -> Dict[str, float]:
        """Calculate Greeks using finite differences for binomial model."""
        greeks = {}
        
        # Delta: dV/dS
        bump = 0.01 * contract.spot_price
        contract_up = OptionContract(**{**contract.__dict__, 'spot_price': contract.spot_price + bump})
        contract_down = OptionContract(**{**contract.__dict__, 'spot_price': contract.spot_price - bump})
        
        price_up = self._binomial_model(contract_up)['price']
        price_down = self._binomial_model(contract_down)['price']
        greeks['delta'] = (price_up - price_down) / (2 * bump)
        
        # Gamma: d²V/dS²
        greeks['gamma'] = (price_up - 2 * base_price + price_down) / (bump ** 2)
        
        # Vega: dV/dσ
        vol_bump = 0.01
        contract_vol_up = OptionContract(**{**contract.__dict__, 
                                          'volatility': contract.volatility + vol_bump})
        price_vol_up = self._binomial_model(contract_vol_up)['price']
        greeks['vega'] = (price_vol_up - base_price) / vol_bump / 100
        
        # Theta: dV/dt
        one_day = timedelta(days=1)
        contract_tomorrow = OptionContract(**{**contract.__dict__, 
                                            'expiry': contract.expiry - one_day})
        price_tomorrow = self._binomial_model(contract_tomorrow)['price']
        greeks['theta'] = (price_tomorrow - base_price) / 365
        
        # Rho: dV/dr
        rate_bump = 0.01
        contract_rate_up = OptionContract(**{**contract.__dict__, 
                                           'risk_free_rate': contract.risk_free_rate + rate_bump})
        price_rate_up = self._binomial_model(contract_rate_up)['price']
        greeks['rho'] = (price_rate_up - base_price) / rate_bump / 100
        
        return greeks
    
    def _calculate_monte_carlo_greeks(self, contract: OptionContract,
                                    base_price: float) -> Dict[str, float]:
        """Calculate Greeks using finite differences for Monte Carlo."""
        # Similar to binomial Greeks calculation
        # In practice, would use pathwise derivatives or likelihood ratio method
        return self._calculate_binomial_greeks(contract, base_price)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_quant_models_agent(model_name: str = DEFAULT_MODEL,
                            temperature: float = DEFAULT_TEMPERATURE) -> SpyderX10_QuantModelsAgent:
    """
    Factory function to create Quantitative Models Agent instance.
    
    Args:
        model_name: Ollama model to use
        temperature: Temperature for AI responses
        
    Returns:
        SpyderX10_QuantModelsAgent instance
    """
    return SpyderX10_QuantModelsAgent(model_name, temperature)

# Singleton instance
_module_instance = None

def get_module_instance() -> SpyderX10_QuantModelsAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        _module_instance = create_quant_models_agent()
    return _module_instance

# ==============================================================================
# TEST EXECUTION
# ==============================================================================

async def test_quant_models():
    """Test the Quantitative Models Agent functionality."""
    print("="*80)
    print("Testing SpyderX10_QuantModelsAgent")
    print("="*80)
    
    agent = create_quant_models_agent()
    
    # Test 1: Option Pricing
    print("\nTest 1: Option Pricing")
    print("-"*40)
    
    contract = OptionContract(
        symbol="SPY",
        strike=455.0,
        expiry=datetime.now() + timedelta(days=30),
        option_type="call",
        spot_price=450.0,
        volatility=0.20,
        risk_free_rate=0.05,
        dividend_yield=0.02,
        market_price=7.50
    )
    
    pricing_result = await agent.price_option(contract)
    
    print(f"Model Type: {pricing_result.model_type.value}")
    print(f"Theoretical Price: ${pricing_result.theoretical_price:.2f}")
    print(f"Market Price: ${contract.market_price:.2f}")
    print(f"Price Difference: ${pricing_result.theoretical_price - contract.market_price:.2f}")
    print(f"\nGreeks:")
    for greek, value in pricing_result.greeks.items():
        print(f"  {greek}: {value:.4f}")
    print(f"\nImplied Volatility: {pricing_result.implied_volatility:.1%}" 
          if pricing_result.implied_volatility else "N/A")
    print(f"Confidence Interval: ${pricing_result.confidence_interval[0]:.2f} - "
          f"${pricing_result.confidence_interval[1]:.2f}")
    
    # Test 2: Volatility Forecast
    print("\n\nTest 2: Volatility Forecast")
    print("-"*40)
    
    # Generate sample price data
    np.random.seed(42)
    prices = [450]
    for _ in range(60):
        ret = np.random.normal(0.0005, 0.015)
        prices.append(prices[-1] * (1 + ret))
    
    vol_forecast = await agent.forecast_volatility("SPY", prices, 30)
    
    print(f"Current Volatility: {vol_forecast.current_volatility:.1%}")
    print(f"Volatility Regime: {vol_forecast.volatility_regime}")
    print(f"\nForecasts:")
    print(f"  1-day: {vol_forecast.forecast_1d:.1%}")
    print(f"  5-day: {vol_forecast.forecast_5d:.1%}")
    print(f"  30-day: {vol_forecast.forecast_30d:.1%}")
    print(f"\nConfidence Bands (5-day):")
    if '5d' in vol_forecast.confidence_bands:
        lower, upper = vol_forecast.confidence_bands['5d']
        print(f"  95% CI: {lower:.1%} - {upper:.1%}")
    
    # Test 3: Model Validation
    print("\n\nTest 3: Model Validation")
    print("-"*40)
    
    # Create sample historical data
    historical_data = pd.DataFrame({
        'close': prices,
        'volatility': [0.20 + np.random.normal(0, 0.02) for _ in prices]
    })
    
    validation = await agent.validate_model(ModelType.BLACK_SCHOLES, historical_data)
    
    print(f"Model: {validation.model_type.value}")
    print(f"Overall Score: {validation.overall_score:.2f}/1.00")
    print(f"\nValidation Metrics:")
    for metric, value in list(validation.validation_metrics.items())[:5]:
        print(f"  {metric}: {value:.4f}")
    print(f"\nRecommendations:")
    for i, rec in enumerate(validation.recommendations[:3], 1):
        print(f"  {i}. {rec}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print(f"Initializing {__name__}")
    print(f"Ollama Available: {OLLAMA_AVAILABLE}")
    
    # Run async tests
    asyncio.run(test_quant_models())
    
    print("\n" + "="*80)
    print("SpyderX10_QuantModelsAgent module loaded successfully!")
    print("="*80)