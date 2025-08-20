#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV01_QuantEngine.py
Purpose: Main quantitative models orchestrator and integration engine

Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-20 Time: 12:00:00  

Module Description:
    Central orchestrator for all quantitative models in the Spyder system.
    Integrates Heston pricing, CVaR risk management, and other quant models
    with the SpyderB08 data feeds. Provides unified interface for pricing,
    risk calculation, and model coordination across the trading system.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import queue

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    # Import SpyderB08 for data feeds
    from SpyderB08_MultiClientDataManager import MultiClientDataManager
    from SpyderB08_MultiClientDataManager import ClientPurpose
except ImportError:
    print("⚠️  SpyderB08 not available - running in standalone mode")
    MultiClientDataManager = None
    ClientPurpose = None

try:
    # Import the discovered quantitative models
    from SpyderQ01_HestonModel import SpyderHestonModel
    from SpyderQ02_CVaRCalculator import SpyderCVaRCalculator
    QUANT_MODELS_AVAILABLE = True
except ImportError:
    print("⚠️  Quantitative models not found - will use placeholders")
    SpyderHestonModel = None
    SpyderCVaRCalculator = None
    QUANT_MODELS_AVAILABLE = False

# ==============================================================================
# CONFIGURATION CONSTANTS
# ==============================================================================
class ModelType(Enum):
    """Available quantitative model types."""
    HESTON = "heston"
    CVAR = "cvar"
    BLACK_SCHOLES = "black_scholes"
    SABR = "sabr"
    LOCAL_VOL = "local_vol"
    JUMP_DIFFUSION = "jump_diffusion"
    GARCH = "garch"
    PCA_VOL = "pca_vol"
    REGIME_SWITCHING = "regime_switching"

class DataSource(Enum):
    """Data source types from SpyderB08."""
    CORE_DATA = 3           # Client 3: Core market data
    SPY_OPTIONS = 4         # Client 4: SPY options chains
    MARKET_INTERNALS = 6    # Client 6: VUD + market internals
    INTERNATIONAL = 10      # Client 10: International markets

# Model configuration
QUANT_CONFIG = {
    'heston': {
        'calibration_frequency': 'daily',      # Daily recalibration
        'rmse_target': 0.15,                  # 15% RMSE target
        'max_iterations': 500
    },
    'cvar': {
        'confidence_levels': [0.95, 0.99],    # 95% and 99% confidence
        'methods': ['historical', 'parametric', 'monte_carlo'],
        'horizon_days': [1, 5, 21]           # Daily, weekly, monthly
    },
    'risk_limits': {
        'max_var_pct': 0.05,                 # Max 5% portfolio VaR
        'max_cvar_ratio': 3.0,               # CVaR/VaR ratio limit
        'stress_test_frequency': 'hourly'
    }
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketData:
    """Market data structure for quant models."""
    spot_price: float
    options_chain: pd.DataFrame
    historical_prices: pd.DataFrame
    volatility_surface: Optional[pd.DataFrame] = None
    risk_free_rate: float = 0.05
    dividend_yield: float = 0.02
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ModelOutput:
    """Standardized model output structure."""
    model_type: ModelType
    results: Dict[str, Any]
    confidence: float
    timestamp: datetime
    execution_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RiskMetrics:
    """Comprehensive risk metrics."""
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    cvar_var_ratio: float
    max_drawdown: float
    sharpe_ratio: float
    portfolio_value: float
    stress_test_results: Dict[str, float] = field(default_factory=dict)

@dataclass
class QuantEngineStatus:
    """Engine status and health metrics."""
    is_running: bool
    models_active: List[str]
    last_update: datetime
    error_count: int
    performance_metrics: Dict[str, float] = field(default_factory=dict)

# ==============================================================================
# MAIN QUANTITATIVE ENGINE CLASS
# ==============================================================================
class SpyderQuantEngine:
    """
    Main quantitative models engine for Spyder trading system.
    
    Orchestrates pricing models (Heston, SABR), risk models (CVaR, EVT),
    and integrates with SpyderB08 data feeds for real-time quantitative
    analysis and trading decision support.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the quantitative engine."""
        self.config = config or QUANT_CONFIG
        self.logger = self._setup_logging()
        
        # Core components
        self.data_manager = None
        self.models = {}
        self.market_data = None
        self.risk_metrics = None
        
        # Threading and async
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.data_queue = queue.Queue()
        self.is_running = False
        self.update_thread = None
        
        # Performance tracking
        self.performance_stats = {
            'models_executed': 0,
            'avg_execution_time': 0.0,
            'errors': 0,
            'last_calibration': None
        }
        
        # Initialize models
        self._initialize_models()
        
        self.logger.info("🚀 SpyderQuantEngine initialized")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the quant engine."""
        logger = logging.getLogger('SpyderQuantEngine')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _initialize_models(self):
        """Initialize available quantitative models."""
        self.logger.info("🔧 Initializing quantitative models...")
        
        if QUANT_MODELS_AVAILABLE:
            try:
                # Initialize Heston model
                self.models[ModelType.HESTON] = SpyderHestonModel(
                    risk_free_rate=self.config.get('risk_free_rate', 0.05)
                )
                self.logger.info("✅ Heston model initialized")
                
                # Initialize CVaR calculator
                self.models[ModelType.CVAR] = SpyderCVaRCalculator()
                self.logger.info("✅ CVaR calculator initialized")
                
            except Exception as e:
                self.logger.error(f"❌ Error initializing quant models: {e}")
        else:
            self.logger.warning("⚠️  Running with placeholder models")
            self._initialize_placeholder_models()

    def _initialize_placeholder_models(self):
        """Initialize placeholder models when real ones aren't available."""
        # Simple placeholder implementations
        class PlaceholderHeston:
            def price_option(self, *args, **kwargs):
                return 5.0  # Dummy price
            
            def calibrate(self, *args, **kwargs):
                return {"rmse": 0.12, "convergence": True}
        
        class PlaceholderCVaR:
            async def calculate_portfolio_risk(self, *args, **kwargs):
                return type('RiskMetrics', (), {
                    'var': 1000, 'cvar': 2500, 'cvar_var_ratio': 2.5
                })()
        
        self.models[ModelType.HESTON] = PlaceholderHeston()
        self.models[ModelType.CVAR] = PlaceholderCVaR()

    async def start(self) -> bool:
        """Start the quantitative engine."""
        try:
            self.logger.info("🚀 Starting SpyderQuantEngine...")
            
            # Connect to SpyderB08 data manager if available
            if MultiClientDataManager:
                self.data_manager = MultiClientDataManager()
                data_start = self.data_manager.start()
                if not data_start:
                    self.logger.warning("⚠️  SpyderB08 connection failed - continuing standalone")
            
            # Start background data processing
            self.is_running = True
            self.update_thread = threading.Thread(
                target=self._background_update_loop,
                daemon=True
            )
            self.update_thread.start()
            
            self.logger.info("✅ SpyderQuantEngine started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start engine: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the quantitative engine."""
        try:
            self.logger.info("🛑 Stopping SpyderQuantEngine...")
            
            self.is_running = False
            
            if self.update_thread:
                self.update_thread.join(timeout=5)
            
            if self.data_manager:
                self.data_manager.stop()
            
            self.executor.shutdown(wait=True)
            
            self.logger.info("✅ SpyderQuantEngine stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping engine: {e}")
            return False

    def _background_update_loop(self):
        """Background thread for continuous model updates."""
        while self.is_running:
            try:
                # Update market data
                self._update_market_data()
                
                # Recalibrate models if needed
                self._check_recalibration()
                
                # Update risk metrics
                asyncio.run(self._update_risk_metrics())
                
                # Sleep for update interval
                threading.Event().wait(30)  # 30-second updates
                
            except Exception as e:
                self.logger.error(f"Error in background loop: {e}")
                self.performance_stats['errors'] += 1

    def _update_market_data(self):
        """Update market data from SpyderB08 feeds."""
        try:
            if not self.data_manager:
                return
            
            # Get SPY spot price (from core data client)
            spot_data = self.data_manager.get_client_data(DataSource.CORE_DATA.value)
            
            # Get options chain (from SPY options client)
            options_data = self.data_manager.get_client_data(DataSource.SPY_OPTIONS.value)
            
            # Get market internals (from VUD + internals client)
            internals_data = self.data_manager.get_client_data(DataSource.MARKET_INTERNALS.value)
            
            # Update market data structure
            self.market_data = MarketData(
                spot_price=spot_data.get('SPY', {}).get('price', 450.0),
                options_chain=pd.DataFrame(options_data.get('options', [])),
                historical_prices=pd.DataFrame(spot_data.get('historical', [])),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error updating market data: {e}")

    def _check_recalibration(self):
        """Check if models need recalibration."""
        try:
            current_time = datetime.now()
            last_cal = self.performance_stats.get('last_calibration')
            
            # Daily recalibration
            if (not last_cal or 
                (current_time - last_cal).days >= 1):
                
                self.logger.info("🔄 Starting daily model recalibration...")
                self._calibrate_heston_model()
                self.performance_stats['last_calibration'] = current_time
                
        except Exception as e:
            self.logger.error(f"Error in recalibration check: {e}")

    def _calibrate_heston_model(self):
        """Calibrate Heston model to current market data."""
        try:
            if ModelType.HESTON not in self.models or not self.market_data:
                return
            
            heston_model = self.models[ModelType.HESTON]
            
            # Create calibration data (simplified)
            market_data = []
            if not self.market_data.options_chain.empty:
                for _, row in self.market_data.options_chain.head(20).iterrows():
                    market_data.append({
                        'strike': row.get('strike', 450),
                        'maturity': 0.25,  # 3 months
                        'price': row.get('mid_price', 5.0),
                        'type': 'call',
                        'spot': self.market_data.spot_price
                    })
            
            if market_data:
                result = heston_model.calibrate(market_data)
                self.logger.info(f"📊 Heston calibration: RMSE={result.rmse:.2f}%")
            
        except Exception as e:
            self.logger.error(f"Error calibrating Heston model: {e}")

    async def _update_risk_metrics(self):
        """Update portfolio risk metrics."""
        try:
            if ModelType.CVAR not in self.models:
                return
            
            cvar_calc = self.models[ModelType.CVAR]
            
            # Create sample portfolio (in real system, get from position manager)
            sample_portfolio = [
                {
                    'id': 'SPY_CALL_1',
                    'type': 'option',
                    'option_type': 'call',
                    'strike': 455,
                    'days_to_expiry': 30,
                    'quantity': 10,
                    'market_value': 3500
                }
            ]
            
            # Calculate risk metrics
            metrics = await cvar_calc.calculate_portfolio_risk(
                sample_portfolio,
                confidence=0.95,
                horizon=1
            )
            
            self.risk_metrics = RiskMetrics(
                var_95=metrics.var,
                var_99=metrics.var * 1.3,  # Approximation
                cvar_95=metrics.cvar,
                cvar_99=metrics.cvar * 1.2,  # Approximation
                cvar_var_ratio=metrics.cvar_var_ratio,
                max_drawdown=0.0,  # Would calculate from historical data
                sharpe_ratio=1.5,  # Would calculate from returns
                portfolio_value=metrics.portfolio_value
            )
            
        except Exception as e:
            self.logger.error(f"Error updating risk metrics: {e}")

    async def price_option(self, symbol: str, strike: float, 
                          expiry: datetime, option_type: str,
                          model_type: ModelType = ModelType.HESTON) -> ModelOutput:
        """Price an option using specified model."""
        start_time = datetime.now()
        
        try:
            if model_type not in self.models:
                raise ValueError(f"Model {model_type.value} not available")
            
            model = self.models[model_type]
            
            # Calculate time to expiry
            tte = (expiry - datetime.now()).days / 365.0
            
            # Get current spot price
            spot = self.market_data.spot_price if self.market_data else 450.0
            
            # Price the option
            if model_type == ModelType.HESTON:
                price = model.price_option(spot, strike, tte, option_type)
                greeks = model.calculate_greeks(spot, strike, tte, option_type)
            else:
                price = 5.0  # Placeholder
                greeks = {'delta': 0.5, 'gamma': 0.02, 'vega': 0.15}
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return ModelOutput(
                model_type=model_type,
                results={
                    'price': price,
                    'greeks': greeks
                },
                confidence=0.95,
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            self.logger.error(f"Error pricing option: {e}")
            raise

    async def calculate_portfolio_risk(self, portfolio: List[Dict[str, Any]]) -> RiskMetrics:
        """Calculate comprehensive portfolio risk metrics."""
        try:
            if ModelType.CVAR not in self.models:
                return self.risk_metrics or RiskMetrics(0, 0, 0, 0, 0, 0, 0, 0)
            
            cvar_calc = self.models[ModelType.CVAR]
            
            # Calculate risk using multiple methods
            futures = []
            for method in ['historical', 'parametric', 'monte_carlo']:
                future = self.executor.submit(
                    asyncio.run,
                    cvar_calc.calculate_portfolio_risk(
                        portfolio, confidence=0.95, method=method
                    )
                )
                futures.append((method, future))
            
            # Collect results
            results = {}
            for method, future in futures:
                try:
                    results[method] = future.result(timeout=30)
                except Exception as e:
                    self.logger.warning(f"Risk calculation failed for {method}: {e}")
            
            # Use best result (or average)
            if results:
                best_result = list(results.values())[0]
                return RiskMetrics(
                    var_95=best_result.var,
                    var_99=best_result.var * 1.3,
                    cvar_95=best_result.cvar,
                    cvar_99=best_result.cvar * 1.2,
                    cvar_var_ratio=best_result.cvar_var_ratio,
                    max_drawdown=0.0,
                    sharpe_ratio=1.5,
                    portfolio_value=best_result.portfolio_value
                )
            
            return self.risk_metrics or RiskMetrics(0, 0, 0, 0, 0, 0, 0, 0)
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio risk: {e}")
            return RiskMetrics(0, 0, 0, 0, 0, 0, 0, 0)

    def get_status(self) -> QuantEngineStatus:
        """Get current engine status."""
        return QuantEngineStatus(
            is_running=self.is_running,
            models_active=list(self.models.keys()),
            last_update=datetime.now(),
            error_count=self.performance_stats['errors'],
            performance_metrics=self.performance_stats.copy()
        )

    def get_model_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostics from all models."""
        diagnostics = {}
        
        try:
            # Heston model diagnostics
            if ModelType.HESTON in self.models:
                heston = self.models[ModelType.HESTON]
                if hasattr(heston, 'get_model_diagnostics'):
                    diagnostics['heston'] = heston.get_model_diagnostics()
            
            # CVaR model diagnostics
            if ModelType.CVAR in self.models:
                diagnostics['cvar'] = {
                    'last_calculation': self.risk_metrics.timestamp if self.risk_metrics else None,
                    'current_var': self.risk_metrics.var_95 if self.risk_metrics else 0
                }
            
            # Engine performance
            diagnostics['engine'] = {
                'uptime_seconds': (datetime.now() - datetime.now()).total_seconds(),
                'models_executed': self.performance_stats['models_executed'],
                'error_rate': self.performance_stats['errors'] / max(1, self.performance_stats['models_executed'])
            }
            
        except Exception as e:
            self.logger.error(f"Error getting diagnostics: {e}")
        
        return diagnostics

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_quant_engine(config: Dict[str, Any] = None) -> SpyderQuantEngine:
    """Factory function to create SpyderQuantEngine."""
    return SpyderQuantEngine(config)

# ==============================================================================
# MODULE TESTING
# ==============================================================================
async def test_quant_engine():
    """Test the quantitative engine functionality."""
    print("🧪 TESTING SPYDER QUANT ENGINE")
    print("=" * 50)
    
    # Create engine
    engine = create_quant_engine()
    
    # Test 1: Start engine
    print("\n📡 Test 1: Starting engine...")
    start_success = await engine.start()
    print(f"✅ Engine started: {start_success}")
    
    # Test 2: Check status
    print("\n📊 Test 2: Checking status...")
    status = engine.get_status()
    print(f"✅ Status: Running={status.is_running}, Models={len(status.models_active)}")
    
    # Test 3: Price an option
    print("\n💰 Test 3: Pricing option...")
    try:
        expiry = datetime.now() + timedelta(days=30)
        result = await engine.price_option("SPY", 455, expiry, "call")
        print(f"✅ Option price: ${result.results['price']:.2f}")
        print(f"✅ Delta: {result.results['greeks']['delta']:.3f}")
    except Exception as e:
        print(f"❌ Pricing failed: {e}")
    
    # Test 4: Calculate portfolio risk
    print("\n📈 Test 4: Calculating portfolio risk...")
    portfolio = [
        {
            'id': 'TEST_CALL',
            'type': 'option',
            'option_type': 'call',
            'strike': 455,
            'quantity': 10,
            'market_value': 3500
        }
    ]
    
    try:
        risk = await engine.calculate_portfolio_risk(portfolio)
        print(f"✅ 95% VaR: ${risk.var_95:,.2f}")
        print(f"✅ 95% CVaR: ${risk.cvar_95:,.2f}")
        print(f"✅ CVaR/VaR Ratio: {risk.cvar_var_ratio:.2f}")
    except Exception as e:
        print(f"❌ Risk calculation failed: {e}")
    
    # Test 5: Get diagnostics
    print("\n🔍 Test 5: Getting diagnostics...")
    diagnostics = engine.get_model_diagnostics()
    print(f"✅ Diagnostics available for {len(diagnostics)} components")
    
    # Test 6: Stop engine
    print("\n🛑 Test 6: Stopping engine...")
    stop_success = await engine.stop()
    print(f"✅ Engine stopped: {stop_success}")
    
    print("\n🎯 QUANT ENGINE TEST COMPLETE")

if __name__ == "__main__":
    asyncio.run(test_quant_engine())
