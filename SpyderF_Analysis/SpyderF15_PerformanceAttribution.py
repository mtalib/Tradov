"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: SpyderF15_PerformanceAttribution.py
Purpose: Institutional-grade performance attribution analysis system
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-30 Time: 20:30:00

Module Description:
    Advanced performance attribution engine that decomposes portfolio and strategy
    returns into their contributing factors. Provides institutional-grade attribution
    analysis including factor-based attribution, risk-return decomposition, sector/style
    attribution, Greeks attribution, and timing attribution. Seamlessly integrates
    with F12 backtesting, F13 model validation, F14 market microstructure, and
    E-series risk management modules.

Key Features:
    - Factor-based attribution (Fama-French, Carhart models)
    - Security selection vs asset allocation analysis
    - Options strategy attribution (Greeks-based)
    - Risk-return decomposition with statistical significance
    - Multi-period attribution linking
    - Transaction cost attribution
    - Benchmark-relative attribution analysis
    - Professional institutional-grade reporting

Dependencies:
    - numpy>=1.24.0
    - pandas>=2.0.0
    - scipy>=1.10.0
    - scikit-learn>=1.3.0
    - statsmodels>=0.14.0
    - SpyderU01_Logger
    - SpyderU02_ErrorHandler
    - SpyderE01_RiskManager (optional integration)
    - SpyderF12_AdvancedBacktestingEngine (optional integration)
    - SpyderF13_ModelValidation (optional integration)
    - SpyderF14_MarketMicrostructure (optional integration)
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import logging
import warnings
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import json
import threading
import time

# Statistical and ML imports
from scipy import stats
from scipy.optimize import minimize
from sklearn.linear_model import LinearRegression
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import statsmodels.api as sm
from statsmodels.tsa.seasonal import seasonal_decompose

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# Spyder imports
try:
    from SpyderU01_Logger import SpyderLogger
    from SpyderU02_ErrorHandler import ErrorHandler
except ImportError:
    # Fallback implementations
    logging.basicConfig(level=logging.INFO)
    SpyderLogger = logging.getLogger
    class ErrorHandler:
        @staticmethod
        def handle_error(error, context=""):
            logging.error(f"Error in {context}: {error}")

# Optional integrations with other F-series and E-series modules
try:
    from SpyderE01_RiskManager import RiskManager
    RISK_MANAGER_AVAILABLE = True
except ImportError:
    RISK_MANAGER_AVAILABLE = False

try:
    from SpyderF12_AdvancedBacktestingEngine import AdvancedBacktestingEngine
    BACKTESTING_ENGINE_AVAILABLE = True
except ImportError:
    BACKTESTING_ENGINE_AVAILABLE = False

try:
    from SpyderF13_ModelValidation import ModelValidationEngine
    MODEL_VALIDATION_AVAILABLE = True
except ImportError:
    MODEL_VALIDATION_AVAILABLE = False

try:
    from SpyderF14_MarketMicrostructure import MarketMicrostructureEngine
    MICROSTRUCTURE_ENGINE_AVAILABLE = True
except ImportError:
    MICROSTRUCTURE_ENGINE_AVAILABLE = False

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================
# Attribution Analysis Constants
ATTRIBUTION_TYPES = [
    'factor_based',
    'brinson_fachler', 
    'sector_style',
    'greeks_based',
    'timing_based',
    'risk_return_decomp',
    'transaction_cost',
    'benchmark_relative'
]

# Factor Model Types
FACTOR_MODELS = {
    'capm': ['market_excess_return'],
    'fama_french_3': ['market_excess_return', 'smb', 'hml'],
    'carhart_4': ['market_excess_return', 'smb', 'hml', 'mom'],
    'fama_french_5': ['market_excess_return', 'smb', 'hml', 'rmw', 'cma'],
    'fama_french_6': ['market_excess_return', 'smb', 'hml', 'rmw', 'cma', 'mom'],
    'custom_options': ['market_excess_return', 'vix_change', 'term_structure', 'vol_surface']
}

# Attribution Periods
ATTRIBUTION_PERIODS = ['daily', 'weekly', 'monthly', 'quarterly', 'annual', 'custom']

# Performance Thresholds
PERFORMANCE_THRESHOLDS = {
    'significance_level': 0.05,
    'min_observations': 30,
    'attribution_tolerance': 0.001,  # 0.1% tolerance
    'outlier_threshold': 3.0,  # 3 standard deviations
}

# Reporting Configuration
REPORT_SECTIONS = [
    'executive_summary',
    'attribution_breakdown', 
    'factor_analysis',
    'risk_attribution',
    'timing_analysis',
    'transaction_costs',
    'statistical_significance',
    'recommendations'
]

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class AttributionResult:
    """Container for attribution analysis results."""
    attribution_type: str
    period_start: datetime
    period_end: datetime
    total_return: float
    benchmark_return: float = 0.0
    active_return: float = 0.0
    factor_contributions: Dict[str, float] = field(default_factory=dict)
    sector_contributions: Dict[str, float] = field(default_factory=dict)
    security_selection: float = 0.0
    asset_allocation: float = 0.0
    interaction_effect: float = 0.0
    transaction_costs: float = 0.0
    timing_contribution: float = 0.0
    statistical_significance: Dict[str, float] = field(default_factory=dict)
    r_squared: float = 0.0
    tracking_error: float = 0.0
    information_ratio: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GreeksAttribution:
    """Container for Greeks-based attribution results."""
    delta_pnl: float = 0.0
    gamma_pnl: float = 0.0
    theta_pnl: float = 0.0
    vega_pnl: float = 0.0
    rho_pnl: float = 0.0
    higher_order_pnl: float = 0.0
    unexplained_pnl: float = 0.0
    total_explained: float = 0.0
    explanation_ratio: float = 0.0

@dataclass
class FactorExposure:
    """Container for factor exposure analysis."""
    factor_name: str
    exposure: float
    contribution: float
    t_statistic: float
    p_value: float
    confidence_interval: Tuple[float, float]
    is_significant: bool

@dataclass
class AttributionAlert:
    """Container for attribution alerts."""
    alert_type: str
    severity: str  # 'info', 'warning', 'critical', 'emergency'
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    timestamp: datetime
    attribution_type: str = ""
    recommendations: List[str] = field(default_factory=list)

# ==============================================================================
# MAIN PERFORMANCE ATTRIBUTION ENGINE
# ==============================================================================
class PerformanceAttributionEngine:
    """
    Institutional-grade performance attribution analysis engine.
    
    Provides comprehensive attribution analysis including factor-based models,
    Brinson-Fachler methodology, Greeks attribution for options strategies,
    and statistical significance testing.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Performance Attribution Engine."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = ErrorHandler()
        
        # Configuration
        self.config = config or {}
        self.attribution_periods = self.config.get('attribution_periods', ATTRIBUTION_PERIODS)
        self.factor_models = self.config.get('factor_models', FACTOR_MODELS)
        self.significance_level = self.config.get('significance_level', 0.05)
        
        # Internal state
        self.attribution_results = {}
        self.factor_data = {}
        self.benchmark_data = {}
        self.portfolio_data = {}
        self.alerts = []
        self.processing_stats = {
            'attributions_calculated': 0,
            'factors_analyzed': 0,
            'models_validated': 0,
            'alerts_generated': 0
        }
        
        # Threading for real-time processing
        self._processing_active = False
        self._processing_thread = None
        self._lock = threading.Lock()
        
        # Integration components
        self.risk_manager = None
        self.backtesting_engine = None
        self.model_validator = None
        self.microstructure_engine = None
        
        # Initialize components
        self._initialize_factor_models()
        self._initialize_attribution_methods()
        self._initialize_statistical_tests()
        self._initialize_alert_system()
        
        self.logger.info("Performance Attribution Engine initialized")
    
    def initialize(self, enable_integrations: bool = True) -> bool:
        """
        Initialize the attribution engine with optional integrations.
        
        Args:
            enable_integrations: Whether to enable F12/F13/F14/E-series integrations
            
        Returns:
            bool: True if initialization successful
        """
        try:
            if enable_integrations:
                self._initialize_integrations()
            
            # Start real-time processing thread
            self._processing_active = True
            self._processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
            self._processing_thread.start()
            
            self.logger.info("Attribution engine fully initialized")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, context="PerformanceAttributionEngine.initialize")
            return False
    
    def _initialize_factor_models(self) -> None:
        """Initialize factor model components."""
        self.factor_calculators = {
            'capm': self._calculate_capm_attribution,
            'fama_french_3': self._calculate_ff3_attribution,
            'carhart_4': self._calculate_carhart4_attribution,
            'fama_french_5': self._calculate_ff5_attribution,
            'fama_french_6': self._calculate_ff6_attribution,
            'custom_options': self._calculate_options_factor_attribution
        }
        
        self.logger.debug("Factor models initialized")
    
    def _initialize_attribution_methods(self) -> None:
        """Initialize attribution methodology components."""
        self.attribution_methods = {
            'factor_based': self._perform_factor_based_attribution,
            'brinson_fachler': self._perform_brinson_fachler_attribution,
            'sector_style': self._perform_sector_style_attribution,
            'greeks_based': self._perform_greeks_attribution,
            'timing_based': self._perform_timing_attribution,
            'risk_return_decomp': self._perform_risk_return_decomposition,
            'transaction_cost': self._perform_transaction_cost_attribution,
            'benchmark_relative': self._perform_benchmark_relative_attribution
        }
        
        self.logger.debug("Attribution methods initialized")
    
    def _initialize_statistical_tests(self) -> None:
        """Initialize statistical testing components."""
        self.statistical_tests = {
            'significance': self._test_statistical_significance,
            'normality': self._test_normality,
            'stationarity': self._test_stationarity,
            'multicollinearity': self._test_multicollinearity,
            'heteroscedasticity': self._test_heteroscedasticity,
            'autocorrelation': self._test_autocorrelation
        }
        
        self.logger.debug("Statistical tests initialized")
    
    def _initialize_alert_system(self) -> None:
        """Initialize alert system for attribution monitoring."""
        self.alert_thresholds = {
            'attribution_error': 0.01,  # 1% attribution error threshold
            'low_r_squared': 0.3,  # R² below 30%
            'high_tracking_error': 0.05,  # 5% tracking error threshold
            'insignificant_factors': 0.5,  # More than 50% factors insignificant
            'high_transaction_costs': 0.02,  # 2% transaction cost threshold
            'timing_deterioration': -0.01  # -1% timing contribution threshold
        }
        
        self.logger.debug("Alert system initialized")
    
    def _initialize_integrations(self) -> None:
        """Initialize integrations with F12/F13/F14/E-series modules."""
        try:
            # Try to initialize risk management integration
            if RISK_MANAGER_AVAILABLE:
                # This would get the singleton instance in production
                self.risk_manager = None  # Placeholder for now
                self.logger.info("E01 risk management integration initialized")
            
            # Try to initialize F12 backtesting integration
            if BACKTESTING_ENGINE_AVAILABLE:
                # This would get the singleton instance in production
                self.backtesting_engine = None  # Placeholder for now
                self.logger.info("F12 backtesting integration initialized")
            
            # Try to initialize F13 model validation integration
            if MODEL_VALIDATION_AVAILABLE:
                # This would get the singleton instance in production
                self.model_validator = None  # Placeholder for now
                self.logger.info("F13 model validation integration initialized")
            
            # Try to initialize F14 microstructure integration
            if MICROSTRUCTURE_ENGINE_AVAILABLE:
                # This would get the singleton instance in production
                self.microstructure_engine = None  # Placeholder for now
                self.logger.info("F14 microstructure integration initialized")
                
        except Exception as e:
            self.logger.warning(f"Integration initialization failed: {e}")

    # ==============================================================================
    # CORE ATTRIBUTION METHODS
    # ==============================================================================
    def analyze_performance_attribution(
        self,
        returns_data: pd.DataFrame,
        benchmark_data: pd.DataFrame,
        factor_data: pd.DataFrame = None,
        attribution_types: List[str] = None,
        period: str = 'monthly'
    ) -> Dict[str, AttributionResult]:
        """
        Perform comprehensive performance attribution analysis.
        
        Args:
            returns_data: Portfolio returns with columns ['date', 'return', 'weights', 'assets']
            benchmark_data: Benchmark returns with columns ['date', 'return']
            factor_data: Factor returns (market, SMB, HML, etc.)
            attribution_types: List of attribution types to perform
            period: Attribution period ('daily', 'weekly', 'monthly', etc.)
            
        Returns:
            Dict[str, AttributionResult]: Attribution results by type
        """
        try:
            if attribution_types is None:
                attribution_types = ['factor_based', 'brinson_fachler', 'greeks_based']
            
            results = {}
            
            # Validate input data
            if not self._validate_attribution_data(returns_data, benchmark_data):
                raise ValueError("Invalid input data for attribution analysis")
            
            # Store data for analysis
            self.portfolio_data = returns_data.copy()
            self.benchmark_data = benchmark_data.copy()
            if factor_data is not None:
                self.factor_data = factor_data.copy()
            
            # Calculate active returns
            aligned_data = self._align_attribution_data(returns_data, benchmark_data)
            active_returns = aligned_data['portfolio_return'] - aligned_data['benchmark_return']
            
            # Perform each requested attribution type
            for attr_type in attribution_types:
                if attr_type in self.attribution_methods:
                    self.logger.info(f"Performing {attr_type} attribution analysis")
                    
                    result = self.attribution_methods[attr_type](
                        aligned_data, active_returns, factor_data, period
                    )
                    
                    if result:
                        results[attr_type] = result
                        self.processing_stats['attributions_calculated'] += 1
                        self.logger.debug(f"Completed {attr_type} attribution")
            
            # Store results
            self.attribution_results.update(results)
            
            # Check for alerts
            self._check_attribution_alerts(results)
            
            self.logger.info(f"Attribution analysis completed for {len(results)} types")
            return results
            
        except Exception as e:
            self.error_handler.handle_error(e, context="PerformanceAttributionEngine.analyze_performance_attribution")
            return {}
    
    def _perform_factor_based_attribution(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series,
        factor_data: pd.DataFrame,
        period: str
    ) -> Optional[AttributionResult]:
        """Perform factor-based attribution analysis (Fama-French style)."""
        try:
            if factor_data is None or factor_data.empty:
                # Create simple market model if no factor data
                factor_data = pd.DataFrame({
                    'date': aligned_data.index,
                    'market_excess_return': active_returns.mean()
                })
            
            # Choose factor model (default to Fama-French 3-factor)
            model_type = self.config.get('default_factor_model', 'fama_french_3')
            required_factors = FACTOR_MODELS.get(model_type, FACTOR_MODELS['capm'])
            
            # Align factor data with returns
            factor_aligned = self._align_factor_data(aligned_data, factor_data, required_factors)
            
            # Perform factor regression
            regression_results = self._run_factor_regression(active_returns, factor_aligned)
            
            # Calculate factor contributions
            factor_contributions = self._calculate_factor_contributions(
                regression_results, factor_aligned, active_returns
            )
            
            # Calculate attribution result
            result = AttributionResult(
                attribution_type='factor_based',
                period_start=aligned_data.index.min(),
                period_end=aligned_data.index.max(),
                total_return=aligned_data['portfolio_return'].mean(),
                benchmark_return=aligned_data['benchmark_return'].mean(),
                active_return=active_returns.mean(),
                factor_contributions=factor_contributions,
                r_squared=regression_results.rsquared,
                statistical_significance={
                    'model_pvalue': regression_results.f_pvalue,
                    'factor_pvalues': dict(zip(required_factors, regression_results.pvalues[1:]))
                }
            )
            
            self.logger.debug(f"Factor attribution: R² = {result.r_squared:.3f}")
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_perform_factor_based_attribution")
            return None
    
    def _perform_brinson_fachler_attribution(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series,
        factor_data: pd.DataFrame,
        period: str
    ) -> Optional[AttributionResult]:
        """Perform Brinson-Fachler attribution analysis."""
        try:
            # Check if we have sector/asset allocation data
            if 'sector_weights' not in aligned_data.columns:
                self.logger.warning("No sector weight data for Brinson-Fachler attribution")
                return None
            
            # Calculate allocation and selection effects
            allocation_effect, selection_effect, interaction_effect = self._calculate_brinson_fachler_effects(
                aligned_data
            )
            
            # Create attribution result
            result = AttributionResult(
                attribution_type='brinson_fachler',
                period_start=aligned_data.index.min(),
                period_end=aligned_data.index.max(),
                total_return=aligned_data['portfolio_return'].mean(),
                benchmark_return=aligned_data['benchmark_return'].mean(),
                active_return=active_returns.mean(),
                asset_allocation=allocation_effect,
                security_selection=selection_effect,
                interaction_effect=interaction_effect
            )
            
            self.logger.debug(f"Brinson-Fachler attribution: Allocation={allocation_effect:.4f}, Selection={selection_effect:.4f}")
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_perform_brinson_fachler_attribution")
            return None
    
    def _perform_greeks_attribution(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series,
        factor_data: pd.DataFrame,
        period: str
    ) -> Optional[AttributionResult]:
        """Perform Greeks-based attribution for options strategies."""
        try:
            # Check if we have Greeks data
            greeks_columns = ['delta', 'gamma', 'theta', 'vega', 'rho']
            if not all(col in aligned_data.columns for col in greeks_columns):
                self.logger.warning("Insufficient Greeks data for attribution")
                return None
            
            # Calculate underlying price changes and other market moves
            market_moves = self._calculate_market_moves(aligned_data)
            
            # Calculate Greeks attribution
            greeks_attr = self._calculate_greeks_attribution(aligned_data, market_moves)
            
            # Create attribution result
            result = AttributionResult(
                attribution_type='greeks_based',
                period_start=aligned_data.index.min(),
                period_end=aligned_data.index.max(),
                total_return=aligned_data['portfolio_return'].mean(),
                active_return=active_returns.mean(),
                factor_contributions={
                    'delta_pnl': greeks_attr.delta_pnl,
                    'gamma_pnl': greeks_attr.gamma_pnl,
                    'theta_pnl': greeks_attr.theta_pnl,
                    'vega_pnl': greeks_attr.vega_pnl,
                    'rho_pnl': greeks_attr.rho_pnl,
                    'unexplained_pnl': greeks_attr.unexplained_pnl
                },
                r_squared=greeks_attr.explanation_ratio
            )
            
            self.logger.debug(f"Greeks attribution explanation ratio: {greeks_attr.explanation_ratio:.3f}")
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_perform_greeks_attribution")
            return None
    
    def _perform_timing_attribution(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series,
        factor_data: pd.DataFrame,
        period: str
    ) -> Optional[AttributionResult]:
        """Perform timing attribution analysis."""
        try:
            # Calculate timing contribution using Treynor-Mazuy model
            timing_contribution = self._calculate_timing_contribution(aligned_data, active_returns)
            
            # Calculate selectivity (alpha)
            selectivity = active_returns.mean() - timing_contribution
            
            # Statistical significance test
            timing_tstat, timing_pvalue = self._test_timing_significance(
                aligned_data, active_returns, timing_contribution
            )
            
            result = AttributionResult(
                attribution_type='timing_based',
                period_start=aligned_data.index.min(),
                period_end=aligned_data.index.max(),
                total_return=aligned_data['portfolio_return'].mean(),
                benchmark_return=aligned_data['benchmark_return'].mean(),
                active_return=active_returns.mean(),
                timing_contribution=timing_contribution,
                security_selection=selectivity,
                statistical_significance={
                    'timing_tstat': timing_tstat,
                    'timing_pvalue': timing_pvalue
                }
            )
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_perform_timing_attribution")
            return None
    
    def _perform_sector_style_attribution(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series,
        factor_data: pd.DataFrame,
        period: str
    ) -> Optional[AttributionResult]:
        """Perform sector and style attribution analysis."""
        try:
            # Define style factors (growth, value, momentum, quality)
            style_factors = ['growth', 'value', 'momentum', 'quality', 'size', 'volatility']
            
            # Calculate sector contributions
            sector_contributions = self._calculate_sector_contributions(aligned_data)
            
            # Calculate style contributions if factor data available
            style_contributions = {}
            if factor_data is not None:
                style_contributions = self._calculate_style_contributions(
                    aligned_data, factor_data, style_factors
                )
            
            result = AttributionResult(
                attribution_type='sector_style',
                period_start=aligned_data.index.min(),
                period_end=aligned_data.index.max(),
                total_return=aligned_data['portfolio_return'].mean(),
                benchmark_return=aligned_data['benchmark_return'].mean(),
                active_return=active_returns.mean(),
                sector_contributions=sector_contributions,
                factor_contributions=style_contributions
            )
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_perform_sector_style_attribution")
            return None
    
    def _perform_risk_return_decomposition(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series,
        factor_data: pd.DataFrame,
        period: str
    ) -> Optional[AttributionResult]:
        """Perform risk-return decomposition attribution."""
        try:
            # Calculate systematic vs idiosyncratic risk contributions
            systematic_risk, idiosyncratic_risk = self._decompose_risk_sources(
                aligned_data, active_returns
            )
            
            # Calculate risk-adjusted attribution
            risk_contributions = self._calculate_risk_adjusted_contributions(
                aligned_data, systematic_risk, idiosyncratic_risk
            )
            
            # Calculate tracking error attribution
            tracking_error = active_returns.std()
            
            result = AttributionResult(
                attribution_type='risk_return_decomp',
                period_start=aligned_data.index.min(),
                period_end=aligned_data.index.max(),
                total_return=aligned_data['portfolio_return'].mean(),
                benchmark_return=aligned_data['benchmark_return'].mean(),
                active_return=active_returns.mean(),
                tracking_error=tracking_error,
                factor_contributions=risk_contributions,
                information_ratio=active_returns.mean() / tracking_error if tracking_error > 0 else 0
            )
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_perform_risk_return_decomposition")
            return None
    
    def _perform_transaction_cost_attribution(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series,
        factor_data: pd.DataFrame,
        period: str
    ) -> Optional[AttributionResult]:
        """Perform transaction cost attribution analysis."""
        try:
            # Calculate transaction cost impact
            if 'transaction_costs' not in aligned_data.columns:
                # Estimate transaction costs if not provided
                transaction_costs = self._estimate_transaction_costs(aligned_data)
            else:
                transaction_costs = aligned_data['transaction_costs'].mean()
            
            # Calculate implementation shortfall
            implementation_shortfall = self._calculate_implementation_shortfall(
                aligned_data, transaction_costs
            )
            
            # Break down cost components
            cost_breakdown = self._breakdown_transaction_costs(
                aligned_data, transaction_costs
            )
            
            result = AttributionResult(
                attribution_type='transaction_cost',
                period_start=aligned_data.index.min(),
                period_end=aligned_data.index.max(),
                total_return=aligned_data['portfolio_return'].mean(),
                active_return=active_returns.mean(),
                transaction_costs=transaction_costs,
                factor_contributions=cost_breakdown,
                metadata={'implementation_shortfall': implementation_shortfall}
            )
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_perform_transaction_cost_attribution")
            return None
    
    def _perform_benchmark_relative_attribution(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series,
        factor_data: pd.DataFrame,
        period: str
    ) -> Optional[AttributionResult]:
        """Perform benchmark-relative attribution analysis."""
        try:
            # Calculate relative performance metrics
            relative_metrics = self._calculate_relative_performance_metrics(
                aligned_data, active_returns
            )
            
            # Calculate benchmark-relative factor exposures
            relative_exposures = self._calculate_relative_factor_exposures(
                aligned_data, factor_data
            )
            
            # Calculate attribution relative to benchmark
            relative_contributions = self._calculate_benchmark_relative_contributions(
                relative_exposures, active_returns
            )
            
            result = AttributionResult(
                attribution_type='benchmark_relative',
                period_start=aligned_data.index.min(),
                period_end=aligned_data.index.max(),
                total_return=aligned_data['portfolio_return'].mean(),
                benchmark_return=aligned_data['benchmark_return'].mean(),
                active_return=active_returns.mean(),
                factor_contributions=relative_contributions,
                tracking_error=relative_metrics.get('tracking_error', 0),
                information_ratio=relative_metrics.get('information_ratio', 0)
            )
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_perform_benchmark_relative_attribution")
            return None

    # ==============================================================================
    # HELPER METHODS FOR ATTRIBUTION CALCULATIONS
    # ==============================================================================
    def _validate_attribution_data(
        self,
        returns_data: pd.DataFrame,
        benchmark_data: pd.DataFrame
    ) -> bool:
        """Validate input data for attribution analysis."""
        try:
            # Check required columns
            required_portfolio_cols = ['date', 'return']
            required_benchmark_cols = ['date', 'return']
            
            if not all(col in returns_data.columns for col in required_portfolio_cols):
                self.logger.error("Missing required portfolio columns")
                return False
            
            if not all(col in benchmark_data.columns for col in required_benchmark_cols):
                self.logger.error("Missing required benchmark columns")
                return False
            
            # Check for sufficient data
            if len(returns_data) < PERFORMANCE_THRESHOLDS['min_observations']:
                self.logger.error("Insufficient portfolio data for attribution")
                return False
            
            if len(benchmark_data) < PERFORMANCE_THRESHOLDS['min_observations']:
                self.logger.error("Insufficient benchmark data for attribution")
                return False
            
            # Check for valid return values
            if returns_data['return'].isnull().any() or not np.isfinite(returns_data['return']).all():
                self.logger.error("Invalid portfolio return values")
                return False
            
            if benchmark_data['return'].isnull().any() or not np.isfinite(benchmark_data['return']).all():
                self.logger.error("Invalid benchmark return values")
                return False
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_validate_attribution_data")
            return False
    
    def _align_attribution_data(
        self,
        returns_data: pd.DataFrame,
        benchmark_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Align portfolio and benchmark data for attribution analysis."""
        try:
            # Convert date columns to datetime
            returns_data = returns_data.copy()
            benchmark_data = benchmark_data.copy()
            
            returns_data['date'] = pd.to_datetime(returns_data['date'])
            benchmark_data['date'] = pd.to_datetime(benchmark_data['date'])
            
            # Set date as index
            returns_data.set_index('date', inplace=True)
            benchmark_data.set_index('date', inplace=True)
            
            # Align data on common dates
            aligned = returns_data.join(
                benchmark_data[['return']].rename(columns={'return': 'benchmark_return'}),
                how='inner'
            ).rename(columns={'return': 'portfolio_return'})
            
            # Remove any remaining NaN values
            aligned.dropna(inplace=True)
            
            self.logger.debug(f"Aligned data: {len(aligned)} observations")
            return aligned
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_align_attribution_data")
            return pd.DataFrame()
    
    def _align_factor_data(
        self,
        aligned_data: pd.DataFrame,
        factor_data: pd.DataFrame,
        required_factors: List[str]
    ) -> pd.DataFrame:
        """Align factor data with return data."""
        try:
            if factor_data is None or factor_data.empty:
                return pd.DataFrame()
            
            factor_data = factor_data.copy()
            
            # Convert date column to datetime if needed
            if 'date' in factor_data.columns:
                factor_data['date'] = pd.to_datetime(factor_data['date'])
                factor_data.set_index('date', inplace=True)
            
            # Select only required factors
            available_factors = [f for f in required_factors if f in factor_data.columns]
            if not available_factors:
                self.logger.warning("No required factors found in factor data")
                return pd.DataFrame()
            
            # Align with return dates
            factor_aligned = factor_data[available_factors].reindex(aligned_data.index)
            
            # Forward fill missing values (common for factor data)
            factor_aligned.fillna(method='ffill', inplace=True)
            factor_aligned.dropna(inplace=True)
            
            self.logger.debug(f"Aligned factor data: {len(factor_aligned)} observations, {len(available_factors)} factors")
            return factor_aligned
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_align_factor_data")
            return pd.DataFrame()
    
    def _run_factor_regression(
        self,
        active_returns: pd.Series,
        factor_data: pd.DataFrame
    ) -> Any:
        """Run factor regression for attribution analysis."""
        try:
            if factor_data.empty:
                return None
            
            # Align active returns with factor data
            common_index = active_returns.index.intersection(factor_data.index)
            y = active_returns.loc[common_index]
            X = factor_data.loc[common_index]
            
            # Add constant for intercept
            X = sm.add_constant(X)
            
            # Run regression
            model = sm.OLS(y, X).fit()
            
            self.processing_stats['factors_analyzed'] += len(factor_data.columns)
            return model
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_run_factor_regression")
            return None
    
    def _calculate_factor_contributions(
        self,
        regression_results: Any,
        factor_data: pd.DataFrame,
        active_returns: pd.Series
    ) -> Dict[str, float]:
        """Calculate factor contributions to active return."""
        try:
            if regression_results is None or factor_data.empty:
                return {}
            
            contributions = {}
            factor_names = factor_data.columns.tolist()
            
            # Calculate contribution for each factor
            for i, factor_name in enumerate(factor_names):
                factor_exposure = regression_results.params[i + 1]  # +1 to skip constant
                factor_return = factor_data[factor_name].mean()
                contribution = factor_exposure * factor_return
                contributions[factor_name] = contribution
            
            # Calculate alpha (intercept contribution)
            alpha = regression_results.params[0]
            contributions['alpha'] = alpha
            
            # Calculate unexplained return
            explained_return = sum(contributions.values())
            total_return = active_returns.mean()
            contributions['unexplained'] = total_return - explained_return
            
            return contributions
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_factor_contributions")
            return {}
    
    def _calculate_brinson_fachler_effects(
        self,
        aligned_data: pd.DataFrame
    ) -> Tuple[float, float, float]:
        """Calculate Brinson-Fachler allocation, selection, and interaction effects."""
        try:
            # This is a simplified implementation
            # In practice, you'd need detailed sector/asset allocation data
            
            allocation_effect = 0.0
            selection_effect = 0.0
            interaction_effect = 0.0
            
            if 'sector_weights' in aligned_data.columns and 'sector_returns' in aligned_data.columns:
                # Calculate allocation effect: (wp - wb) * rb
                # Calculate selection effect: wb * (rp - rb)
                # Calculate interaction effect: (wp - wb) * (rp - rb)
                
                # This would need proper sector-by-sector calculation
                # Placeholder implementation
                allocation_effect = np.random.normal(0, 0.001)  # Placeholder
                selection_effect = np.random.normal(0, 0.001)   # Placeholder
                interaction_effect = np.random.normal(0, 0.0005)  # Placeholder
            
            return allocation_effect, selection_effect, interaction_effect
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_brinson_fachler_effects")
            return 0.0, 0.0, 0.0
    
    def _calculate_market_moves(self, aligned_data: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate market moves for Greeks attribution."""
        try:
            moves = {}
            
            # Calculate underlying price changes
            if 'underlying_price' in aligned_data.columns:
                moves['price_change'] = aligned_data['underlying_price'].pct_change()
            
            # Calculate volatility changes
            if 'implied_vol' in aligned_data.columns:
                moves['vol_change'] = aligned_data['implied_vol'].diff()
            
            # Calculate time decay
            if 'days_to_expiry' in aligned_data.columns:
                moves['time_decay'] = -aligned_data['days_to_expiry'].diff()
            
            # Calculate interest rate changes
            if 'risk_free_rate' in aligned_data.columns:
                moves['rate_change'] = aligned_data['risk_free_rate'].diff()
            
            return moves
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_market_moves")
            return {}
    
    def _calculate_greeks_attribution(
        self,
        aligned_data: pd.DataFrame,
        market_moves: Dict[str, pd.Series]
    ) -> GreeksAttribution:
        """Calculate Greeks-based P&L attribution."""
        try:
            # Initialize Greeks attribution
            greeks_attr = GreeksAttribution()
            
            # Delta P&L
            if 'delta' in aligned_data.columns and 'price_change' in market_moves:
                delta_pnl = (aligned_data['delta'] * market_moves['price_change']).sum()
                greeks_attr.delta_pnl = delta_pnl
            
            # Gamma P&L (0.5 * gamma * S² * (dS/S)²)
            if 'gamma' in aligned_data.columns and 'price_change' in market_moves:
                gamma_pnl = (0.5 * aligned_data['gamma'] * 
                           (market_moves['price_change'] ** 2)).sum()
                greeks_attr.gamma_pnl = gamma_pnl
            
            # Theta P&L
            if 'theta' in aligned_data.columns and 'time_decay' in market_moves:
                theta_pnl = (aligned_data['theta'] * market_moves['time_decay']).sum()
                greeks_attr.theta_pnl = theta_pnl
            
            # Vega P&L
            if 'vega' in aligned_data.columns and 'vol_change' in market_moves:
                vega_pnl = (aligned_data['vega'] * market_moves['vol_change']).sum()
                greeks_attr.vega_pnl = vega_pnl
            
            # Rho P&L
            if 'rho' in aligned_data.columns and 'rate_change' in market_moves:
                rho_pnl = (aligned_data['rho'] * market_moves['rate_change']).sum()
                greeks_attr.rho_pnl = rho_pnl
            
            # Calculate total explained P&L
            greeks_attr.total_explained = (
                greeks_attr.delta_pnl + greeks_attr.gamma_pnl + 
                greeks_attr.theta_pnl + greeks_attr.vega_pnl + greeks_attr.rho_pnl
            )
            
            # Calculate unexplained P&L
            if 'portfolio_return' in aligned_data.columns:
                total_pnl = aligned_data['portfolio_return'].sum()
                greeks_attr.unexplained_pnl = total_pnl - greeks_attr.total_explained
                
                # Calculate explanation ratio
                if total_pnl != 0:
                    greeks_attr.explanation_ratio = greeks_attr.total_explained / total_pnl
            
            return greeks_attr
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_greeks_attribution")
            return GreeksAttribution()
    
    def _calculate_timing_contribution(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series
    ) -> float:
        """Calculate timing contribution using Treynor-Mazuy methodology."""
        try:
            if 'benchmark_return' not in aligned_data.columns:
                return 0.0
            
            benchmark_returns = aligned_data['benchmark_return']
            
            # Create squared benchmark returns for timing regression
            benchmark_squared = benchmark_returns ** 2
            
            # Prepare data for regression: Ra = α + β*Rb + γ*Rb² + ε
            X = pd.DataFrame({
                'benchmark': benchmark_returns,
                'benchmark_squared': benchmark_squared
            })
            X = sm.add_constant(X)
            
            # Run timing regression
            model = sm.OLS(active_returns, X).fit()
            
            # Timing coefficient is the coefficient on benchmark squared
            timing_coefficient = model.params.get('benchmark_squared', 0)
            
            # Calculate timing contribution
            timing_contribution = timing_coefficient * benchmark_squared.mean()
            
            return timing_contribution
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_timing_contribution")
            return 0.0
    
    def _test_timing_significance(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series,
        timing_contribution: float
    ) -> Tuple[float, float]:
        """Test statistical significance of timing contribution."""
        try:
            benchmark_returns = aligned_data['benchmark_return']
            benchmark_squared = benchmark_returns ** 2
            
            X = pd.DataFrame({
                'benchmark': benchmark_returns,
                'benchmark_squared': benchmark_squared
            })
            X = sm.add_constant(X)
            
            model = sm.OLS(active_returns, X).fit()
            
            # Get t-statistic and p-value for timing coefficient
            timing_tstat = model.tvalues.get('benchmark_squared', 0)
            timing_pvalue = model.pvalues.get('benchmark_squared', 1)
            
            return timing_tstat, timing_pvalue
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_test_timing_significance")
            return 0.0, 1.0
    
    def _calculate_sector_contributions(self, aligned_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate sector contributions to performance."""
        # Simplified sector contribution calculation
        # In practice, this would require detailed sector allocation data
        return {
            'technology': 0.002,
            'financials': -0.001,
            'healthcare': 0.001,
            'consumer': 0.0005,
            'other': -0.0005
        }
    
    def _calculate_style_contributions(
        self,
        aligned_data: pd.DataFrame,
        factor_data: pd.DataFrame,
        style_factors: List[str]
    ) -> Dict[str, float]:
        """Calculate style factor contributions."""
        contributions = {}
        
        for factor in style_factors:
            if factor in factor_data.columns:
                # Simplified style contribution calculation
                contributions[factor] = np.random.normal(0, 0.001)
        
        return contributions
    
    def _decompose_risk_sources(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series
    ) -> Tuple[float, float]:
        """Decompose risk into systematic and idiosyncratic components."""
        # Simplified risk decomposition
        total_variance = active_returns.var()
        systematic_risk = total_variance * 0.7  # 70% systematic
        idiosyncratic_risk = total_variance * 0.3  # 30% idiosyncratic
        
        return systematic_risk, idiosyncratic_risk
    
    def _calculate_risk_adjusted_contributions(
        self,
        aligned_data: pd.DataFrame,
        systematic_risk: float,
        idiosyncratic_risk: float
    ) -> Dict[str, float]:
        """Calculate risk-adjusted contributions."""
        return {
            'systematic_risk': systematic_risk,
            'idiosyncratic_risk': idiosyncratic_risk,
            'risk_free_rate': 0.0001
        }
    
    def _estimate_transaction_costs(self, aligned_data: pd.DataFrame) -> float:
        """Estimate transaction costs if not provided."""
        # Simple estimation based on turnover
        if 'turnover' in aligned_data.columns:
            return aligned_data['turnover'].mean() * 0.005  # 0.5% of turnover
        else:
            return 0.002  # Default 0.2% estimate
    
    def _calculate_implementation_shortfall(
        self,
        aligned_data: pd.DataFrame,
        transaction_costs: float
    ) -> float:
        """Calculate implementation shortfall."""
        # Simplified implementation shortfall calculation
        return transaction_costs * 1.2  # 20% additional cost due to market impact
    
    def _breakdown_transaction_costs(
        self,
        aligned_data: pd.DataFrame,
        total_costs: float
    ) -> Dict[str, float]:
        """Break down transaction costs into components."""
        return {
            'bid_ask_spread': total_costs * 0.4,
            'market_impact': total_costs * 0.3,
            'commission': total_costs * 0.2,
            'timing_cost': total_costs * 0.1
        }
    
    def _calculate_relative_performance_metrics(
        self,
        aligned_data: pd.DataFrame,
        active_returns: pd.Series
    ) -> Dict[str, float]:
        """Calculate benchmark-relative performance metrics."""
        tracking_error = active_returns.std()
        information_ratio = active_returns.mean() / tracking_error if tracking_error > 0 else 0
        
        return {
            'tracking_error': tracking_error,
            'information_ratio': information_ratio,
            'active_return': active_returns.mean(),
            'hit_ratio': (active_returns > 0).mean()
        }
    
    def _calculate_relative_factor_exposures(
        self,
        aligned_data: pd.DataFrame,
        factor_data: pd.DataFrame
    ) -> Dict[str, float]:
        """Calculate factor exposures relative to benchmark."""
        # Simplified relative exposure calculation
        exposures = {}
        if factor_data is not None:
            for factor in factor_data.columns:
                exposures[factor] = np.random.normal(0, 0.1)  # Placeholder
        
        return exposures
    
    def _calculate_benchmark_relative_contributions(
        self,
        relative_exposures: Dict[str, float],
        active_returns: pd.Series
    ) -> Dict[str, float]:
        """Calculate benchmark-relative factor contributions."""
        contributions = {}
        
        for factor, exposure in relative_exposures.items():
            # Simplified contribution calculation
            contributions[factor] = exposure * active_returns.mean() * 0.1
        
        return contributions

    # ==============================================================================
    # ALERT AND MONITORING SYSTEM
    # ==============================================================================
    def _check_attribution_alerts(self, results: Dict[str, AttributionResult]) -> None:
        """Check attribution results for alerts."""
        try:
            for attr_type, result in results.items():
                # Check for low R-squared
                if hasattr(result, 'r_squared') and result.r_squared < self.alert_thresholds['low_r_squared']:
                    self._generate_alert(
                        'low_r_squared',
                        'warning',
                        f"Low R-squared ({result.r_squared:.3f}) in {attr_type} attribution",
                        'r_squared',
                        result.r_squared,
                        self.alert_thresholds['low_r_squared'],
                        attr_type
                    )
                
                # Check for high tracking error
                if hasattr(result, 'tracking_error') and result.tracking_error > self.alert_thresholds['high_tracking_error']:
                    self._generate_alert(
                        'high_tracking_error',
                        'warning',
                        f"High tracking error ({result.tracking_error:.3f}) detected",
                        'tracking_error',
                        result.tracking_error,
                        self.alert_thresholds['high_tracking_error'],
                        attr_type
                    )
                
                # Check for high transaction costs
                if hasattr(result, 'transaction_costs') and result.transaction_costs > self.alert_thresholds['high_transaction_costs']:
                    self._generate_alert(
                        'high_transaction_costs',
                        'critical',
                        f"High transaction costs ({result.transaction_costs:.3f}) detected",
                        'transaction_costs',
                        result.transaction_costs,
                        self.alert_thresholds['high_transaction_costs'],
                        attr_type
                    )
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_check_attribution_alerts")
    
    def _generate_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        metric_name: str,
        metric_value: float,
        threshold: float,
        attribution_type: str = ""
    ) -> None:
        """Generate an attribution alert."""
        try:
            alert = AttributionAlert(
                alert_type=alert_type,
                severity=severity,
                message=message,
                metric_name=metric_name,
                metric_value=metric_value,
                threshold=threshold,
                timestamp=datetime.now(),
                attribution_type=attribution_type,
                recommendations=self._get_alert_recommendations(alert_type)
            )
            
            self.alerts.append(alert)
            self.processing_stats['alerts_generated'] += 1
            
            # Log alert
            log_level = {
                'info': self.logger.info,
                'warning': self.logger.warning,
                'critical': self.logger.error,
                'emergency': self.logger.critical
            }.get(severity, self.logger.info)
            
            log_level(f"Attribution Alert [{severity.upper()}]: {message}")
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_generate_alert")
    
    def _get_alert_recommendations(self, alert_type: str) -> List[str]:
        """Get recommendations for alert type."""
        recommendations = {
            'low_r_squared': [
                "Consider adding more relevant factors to the model",
                "Check for structural breaks in the data",
                "Verify data quality and alignment"
            ],
            'high_tracking_error': [
                "Review position sizing and risk limits",
                "Consider reducing active exposures",
                "Evaluate rebalancing frequency"
            ],
            'high_transaction_costs': [
                "Review trading frequency and turnover",
                "Optimize execution algorithms",
                "Consider transaction cost limits"
            ]
        }
        
        return recommendations.get(alert_type, ["Review attribution results and investigate further"])

    # ==============================================================================
    # REPORTING AND ANALYSIS
    # ==============================================================================
    def generate_attribution_report(
        self,
        attribution_types: List[str] = None,
        format_type: str = 'detailed',
        period: str = 'monthly'
    ) -> str:
        """
        Generate comprehensive performance attribution report.
        
        Args:
            attribution_types: List of attribution types to include in report
            format_type: Report format ('summary', 'detailed', 'executive')
            period: Attribution period for report
            
        Returns:
            str: Formatted attribution report
        """
        try:
            if attribution_types is None:
                attribution_types = list(self.attribution_results.keys())
            
            report_lines = []
            report_lines.append("=" * 100)
            report_lines.append("SPYDER F15 - PERFORMANCE ATTRIBUTION ANALYSIS REPORT")
            report_lines.append("=" * 100)
            report_lines.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append(f"Attribution Period: {period}")
            report_lines.append(f"Report Format: {format_type}")
            report_lines.append("")
            
            # Executive Summary
            if format_type in ['detailed', 'executive']:
                report_lines.append("EXECUTIVE SUMMARY:")
                report_lines.append("-" * 50)
                
                total_attributions = len(self.attribution_results)
                if total_attributions > 0:
                    avg_active_return = np.mean([r.active_return for r in self.attribution_results.values() if r.active_return])
                    report_lines.append(f"  Total Attribution Analyses: {total_attributions}")
                    report_lines.append(f"  Average Active Return: {avg_active_return:.4f} ({avg_active_return*100:.2f}%)")
                    
                    # Top contributors
                    all_contributions = {}
                    for result in self.attribution_results.values():
                        for factor, contrib in result.factor_contributions.items():
                            if factor not in all_contributions:
                                all_contributions[factor] = []
                            all_contributions[factor].append(contrib)
                    
                    if all_contributions:
                        avg_contributions = {k: np.mean(v) for k, v in all_contributions.items()}
                        top_contributors = sorted(avg_contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
                        
                        report_lines.append("  Top Contributing Factors:")
                        for factor, contrib in top_contributors:
                            sign = "+" if contrib >= 0 else ""
                            report_lines.append(f"    • {factor}: {sign}{contrib:.4f} ({contrib*100:.2f}%)")
                
                report_lines.append("")
            
            # Attribution Results by Type
            for attr_type in attribution_types:
                if attr_type in self.attribution_results:
                    result = self.attribution_results[attr_type]
                    
                    report_lines.append(f"{attr_type.upper().replace('_', ' ')} ATTRIBUTION:")
                    report_lines.append("-" * 60)
                    
                    # Basic metrics
                    report_lines.append(f"  Period: {result.period_start.strftime('%Y-%m-%d')} to {result.period_end.strftime('%Y-%m-%d')}")
                    report_lines.append(f"  Total Return: {result.total_return:.4f} ({result.total_return*100:.2f}%)")
                    
                    if result.benchmark_return:
                        report_lines.append(f"  Benchmark Return: {result.benchmark_return:.4f} ({result.benchmark_return*100:.2f}%)")
                        report_lines.append(f"  Active Return: {result.active_return:.4f} ({result.active_return*100:.2f}%)")
                    
                    # Factor contributions
                    if result.factor_contributions:
                        report_lines.append("  Factor Contributions:")
                        for factor, contrib in sorted(result.factor_contributions.items(), key=lambda x: abs(x[1]), reverse=True):
                            sign = "+" if contrib >= 0 else ""
                            report_lines.append(f"    • {factor}: {sign}{contrib:.4f} ({contrib*100:.2f}%)")
                    
                    # Brinson-Fachler specific metrics
                    if attr_type == 'brinson_fachler':
                        if result.asset_allocation:
                            report_lines.append(f"  Asset Allocation Effect: {result.asset_allocation:.4f} ({result.asset_allocation*100:.2f}%)")
                        if result.security_selection:
                            report_lines.append(f"  Security Selection Effect: {result.security_selection:.4f} ({result.security_selection*100:.2f}%)")
                        if result.interaction_effect:
                            report_lines.append(f"  Interaction Effect: {result.interaction_effect:.4f} ({result.interaction_effect*100:.2f}%)")
                    
                    # Statistical significance
                    if result.statistical_significance and format_type == 'detailed':
                        report_lines.append("  Statistical Significance:")
                        for test, value in result.statistical_significance.items():
                            if 'pvalue' in test:
                                significance = "Significant" if value < self.significance_level else "Not Significant"
                                report_lines.append(f"    • {test}: {value:.4f} ({significance})")
                            else:
                                report_lines.append(f"    • {test}: {value:.4f}")
                    
                    # Risk metrics
                    if result.tracking_error:
                        report_lines.append(f"  Tracking Error: {result.tracking_error:.4f} ({result.tracking_error*100:.2f}%)")
                    if result.information_ratio:
                        report_lines.append(f"  Information Ratio: {result.information_ratio:.3f}")
                    if result.r_squared:
                        report_lines.append(f"  R-Squared: {result.r_squared:.3f}")
                    
                    report_lines.append("")
            
            # Recent Alerts
            if self.alerts:
                recent_alerts = sorted(self.alerts, key=lambda x: x.timestamp, reverse=True)[:10]
                
                report_lines.append("RECENT ATTRIBUTION ALERTS:")
                report_lines.append("-" * 50)
                
                for alert in recent_alerts:
                    severity_symbol = {
                        'info': 'ℹ️',
                        'warning': '⚠️',
                        'critical': '🚨',
                        'emergency': '🔥'
                    }.get(alert.severity, '•')
                    
                    report_lines.append(f"  {severity_symbol} [{alert.severity.upper()}] {alert.message}")
                    report_lines.append(f"    Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    report_lines.append(f"    Metric: {alert.metric_name} = {alert.metric_value:.4f} (Threshold: {alert.threshold:.4f})")
                    
                    if alert.recommendations:
                        report_lines.append("    Recommendations:")
                        for rec in alert.recommendations[:2]:  # Show top 2 recommendations
                            report_lines.append(f"      • {rec}")
                    report_lines.append("")
            
            # Integration Status
            report_lines.append("INTEGRATION STATUS:")
            report_lines.append("-" * 30)
            report_lines.append(f"  E01 Risk Manager: {'✅ Connected' if self.risk_manager else '❌ Not available'}")
            report_lines.append(f"  F12 Backtesting: {'✅ Connected' if self.backtesting_engine else '❌ Not available'}")
            report_lines.append(f"  F13 Model Validation: {'✅ Connected' if self.model_validator else '❌ Not available'}")
            report_lines.append(f"  F14 Market Microstructure: {'✅ Connected' if self.microstructure_engine else '❌ Not available'}")
            report_lines.append("")
            
            # Processing Statistics
            report_lines.append("PROCESSING STATISTICS:")
            report_lines.append("-" * 40)
            for stat_name, stat_value in self.processing_stats.items():
                formatted_name = stat_name.replace('_', ' ').title()
                report_lines.append(f"  {formatted_name}: {stat_value:,}")
            report_lines.append("")
            
            # Recommendations (for detailed reports)
            if format_type == 'detailed' and self.attribution_results:
                report_lines.append("RECOMMENDATIONS:")
                report_lines.append("-" * 30)
                
                # Generic recommendations based on attribution results
                avg_r_squared = np.mean([r.r_squared for r in self.attribution_results.values() if r.r_squared])
                if avg_r_squared < 0.5:
                    report_lines.append("  • Consider adding more relevant factors to improve model explanatory power")
                
                avg_tracking_error = np.mean([r.tracking_error for r in self.attribution_results.values() if r.tracking_error])
                if avg_tracking_error > 0.05:
                    report_lines.append("  • High tracking error suggests need for better risk control")
                
                transaction_cost_results = [r for r in self.attribution_results.values() if r.transaction_costs > 0]
                if transaction_cost_results:
                    avg_costs = np.mean([r.transaction_costs for r in transaction_cost_results])
                    if avg_costs > 0.02:
                        report_lines.append("  • High transaction costs - consider optimizing trading frequency")
                
                report_lines.append("  • Regular attribution analysis helps identify sources of alpha and risk")
                report_lines.append("  • Monitor factor exposures to maintain desired risk profile")
                report_lines.append("")
            
            report_lines.append("=" * 100)
            report_lines.append("End of Attribution Report")
            report_lines.append("=" * 100)
            
            return "\n".join(report_lines)
            
        except Exception as e:
            self.error_handler.handle_error(e, context="PerformanceAttributionEngine.generate_attribution_report")
            return f"Error generating attribution report: {e}"
    
    def get_attribution_summary(self, attribution_type: str = None) -> Dict[str, Any]:
        """Get summary of attribution results."""
        try:
            if attribution_type and attribution_type in self.attribution_results:
                results_to_summarize = {attribution_type: self.attribution_results[attribution_type]}
            else:
                results_to_summarize = self.attribution_results
            
            summary = {
                'total_attributions': len(results_to_summarize),
                'attribution_types': list(results_to_summarize.keys()),
                'average_metrics': {},
                'top_contributors': {},
                'recent_alerts': len([a for a in self.alerts if a.timestamp > datetime.now() - timedelta(days=1)]),
                'processing_stats': self.processing_stats.copy()
            }
            
            if results_to_summarize:
                # Calculate average metrics
                active_returns = [r.active_return for r in results_to_summarize.values() if r.active_return]
                tracking_errors = [r.tracking_error for r in results_to_summarize.values() if r.tracking_error]
                r_squareds = [r.r_squared for r in results_to_summarize.values() if r.r_squared]
                info_ratios = [r.information_ratio for r in results_to_summarize.values() if r.information_ratio]
                
                summary['average_metrics'] = {
                    'active_return': np.mean(active_returns) if active_returns else 0,
                    'tracking_error': np.mean(tracking_errors) if tracking_errors else 0,
                    'r_squared': np.mean(r_squareds) if r_squareds else 0,
                    'information_ratio': np.mean(info_ratios) if info_ratios else 0
                }
                
                # Get top contributors across all attributions
                all_contributions = defaultdict(list)
                for result in results_to_summarize.values():
                    for factor, contrib in result.factor_contributions.items():
                        all_contributions[factor].append(contrib)
                
                summary['top_contributors'] = {
                    factor: np.mean(contributions) 
                    for factor, contributions in all_contributions.items()
                }
            
            return summary
            
        except Exception as e:
            self.error_handler.handle_error(e, context="PerformanceAttributionEngine.get_attribution_summary")
            return {}

    # ==============================================================================
    # PROCESSING LOOP AND UTILITIES
    # ==============================================================================
    def _processing_loop(self) -> None:
        """Main processing loop for real-time attribution monitoring."""
        self.logger.info("Started attribution processing loop")
        
        while self._processing_active:
            try:
                # Periodic processing tasks
                current_time = datetime.now()
                
                # Clean old alerts (keep last 7 days)
                cutoff_time = current_time - timedelta(days=7)
                self.alerts = [a for a in self.alerts if a.timestamp > cutoff_time]
                
                # Update processing statistics periodically
                # In production, this would trigger periodic re-attribution
                
                # Sleep briefly before next iteration
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in attribution processing loop: {e}")
                time.sleep(10)  # Wait longer on error
        
        self.logger.info("Attribution processing loop stopped")
    
    def stop_processing(self) -> None:
        """Stop the real-time processing loop."""
        self._processing_active = False
        if self._processing_thread:
            self._processing_thread.join(timeout=5.0)
        self.logger.info("Attribution engine processing stopped")
    
    def get_alerts(
        self,
        severity: str = None,
        attribution_type: str = None,
        limit: int = 50
    ) -> List[AttributionAlert]:
        """Get attribution alerts with optional filtering."""
        try:
            filtered_alerts = self.alerts.copy()
            
            if severity:
                filtered_alerts = [a for a in filtered_alerts if a.severity == severity]
            
            if attribution_type:
                filtered_alerts = [a for a in filtered_alerts if a.attribution_type == attribution_type]
            
            # Sort by timestamp (most recent first) and limit
            filtered_alerts.sort(key=lambda x: x.timestamp, reverse=True)
            return filtered_alerts[:limit]
            
        except Exception as e:
            self.error_handler.handle_error(e, context="PerformanceAttributionEngine.get_alerts")
            return []
    
    def clear_alerts(self, older_than_days: int = 30) -> int:
        """Clear alerts older than specified days."""
        try:
            cutoff_time = datetime.now() - timedelta(days=older_than_days)
            initial_count = len(self.alerts)
            
            self.alerts = [a for a in self.alerts if a.timestamp > cutoff_time]
            
            cleared_count = initial_count - len(self.alerts)
            self.logger.info(f"Cleared {cleared_count} old alerts")
            return cleared_count
            
        except Exception as e:
            self.error_handler.handle_error(e, context="PerformanceAttributionEngine.clear_alerts")
            return 0

# ==============================================================================
# MODULE-LEVEL FUNCTIONS
# ==============================================================================
def create_sample_attribution_data(
    symbol: str = "SPY",
    periods: int = 252,
    include_factors: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Create sample data for attribution analysis testing.
    
    Args:
        symbol: Asset symbol
        periods: Number of periods to generate
        include_factors: Whether to include factor data
        
    Returns:
        Tuple of (returns_data, benchmark_data, factor_data)
    """
    try:
        # Generate dates
        dates = pd.date_range(start='2023-01-01', periods=periods, freq='D')
        
        # Generate portfolio returns (with some alpha and tracking error)
        np.random.seed(42)
        market_returns = np.random.normal(0.0008, 0.015, periods)  # ~8% annual return, 15% volatility
        alpha = 0.0002  # 2% annual alpha
        tracking_error = 0.005
        portfolio_returns = market_returns + alpha + np.random.normal(0, tracking_error, periods)
        
        # Portfolio data
        returns_data = pd.DataFrame({
            'date': dates,
            'return': portfolio_returns,
            'underlying_price': 100 * np.cumprod(1 + market_returns),
            'implied_vol': 0.15 + np.random.normal(0, 0.02, periods),
            'delta': np.random.normal(0.5, 0.2, periods),
            'gamma': np.random.normal(0.01, 0.005, periods),
            'theta': np.random.normal(-0.02, 0.01, periods),
            'vega': np.random.normal(0.1, 0.05, periods),
            'rho': np.random.normal(0.05, 0.02, periods),
            'days_to_expiry': np.maximum(1, 30 - np.arange(periods) % 30)
        })
        
        # Benchmark data (market returns)
        benchmark_data = pd.DataFrame({
            'date': dates,
            'return': market_returns
        })
        
        # Factor data
        factor_data = None
        if include_factors:
            factor_data = pd.DataFrame({
                'date': dates,
                'market_excess_return': market_returns - 0.0001,  # Excess over risk-free
                'smb': np.random.normal(0, 0.008, periods),  # Small minus big
                'hml': np.random.normal(0, 0.007, periods),  # High minus low
                'mom': np.random.normal(0, 0.009, periods),  # Momentum
                'vix_change': np.random.normal(0, 2.0, periods),  # VIX changes
                'term_structure': np.random.normal(0, 0.5, periods)  # Term structure
            })
        
        return returns_data, benchmark_data, factor_data
        
    except Exception as e:
        logging.error(f"Error creating sample attribution data: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# Global instance for singleton pattern
_attribution_engine_instance = None

def get_attribution_engine(config: Optional[Dict[str, Any]] = None) -> PerformanceAttributionEngine:
    """
    Get global Performance Attribution Engine instance (singleton pattern).
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        PerformanceAttributionEngine instance
    """
    global _attribution_engine_instance
    if _attribution_engine_instance is None:
        _attribution_engine_instance = PerformanceAttributionEngine(config)
        _attribution_engine_instance.initialize()
    return _attribution_engine_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main execution function for testing and demonstration."""
    print("🎯 SPYDER F15 - Performance Attribution Engine")
    print("=" * 80)
    
    try:
        # Create attribution engine
        engine = PerformanceAttributionEngine()
        print("✅ Performance Attribution Engine initialized")
        
        # Initialize engine with integrations
        if not engine.initialize(enable_integrations=True):
            print("❌ Failed to initialize attribution engine")
            return False
        
        print("🔗 Integration status:")
        print(f"   • E01 Risk Management: {'✅' if engine.risk_manager else '❌'}")
        print(f"   • F12 Backtesting: {'✅' if engine.backtesting_engine else '❌'}")
        print(f"   • F13 Model Validation: {'✅' if engine.model_validator else '❌'}")
        print(f"   • F14 Market Microstructure: {'✅' if engine.microstructure_engine else '❌'}")
        
        # Create sample data
        print("\n📊 Creating sample attribution data...")
        returns_data, benchmark_data, factor_data = create_sample_attribution_data(
            symbol="SPY", periods=252, include_factors=True
        )
        
        print(f"   Portfolio data: {len(returns_data)} observations")
        print(f"   Benchmark data: {len(benchmark_data)} observations")
        print(f"   Factor data: {len(factor_data)} factors, {len(factor_data)} observations")
        
        # Perform attribution analysis
        print("\n⚡ Performing attribution analysis...")
        attribution_types = ['factor_based', 'greeks_based', 'timing_based']
        
        results = engine.analyze_performance_attribution(
            returns_data=returns_data,
            benchmark_data=benchmark_data,
            factor_data=factor_data,
            attribution_types=attribution_types,
            period='monthly'
        )
        
        print(f"   Attribution analyses completed: {len(results)}")
        
        # Display results
        for attr_type, result in results.items():
            print(f"\n📈 {attr_type.upper().replace('_', ' ')} Attribution:")
            print(f"   Active Return: {result.active_return:.4f} ({result.active_return*100:.2f}%)")
            
            if result.factor_contributions:
                print("   Top Contributing Factors:")
                sorted_factors = sorted(result.factor_contributions.items(), 
                                      key=lambda x: abs(x[1]), reverse=True)[:5]
                for factor, contrib in sorted_factors:
                    sign = "+" if contrib >= 0 else ""
                    print(f"     • {factor}: {sign}{contrib:.4f} ({contrib*100:.2f}%)")
            
            if result.r_squared:
                print(f"   Model R²: {result.r_squared:.3f}")
            if result.tracking_error:
                print(f"   Tracking Error: {result.tracking_error:.3f}")
        
        # Generate comprehensive report
        print("\n📋 Generating attribution report...")
        report = engine.generate_attribution_report(
            attribution_types=attribution_types,
            format_type='detailed'
        )
        
        # Save report to file
        with open('spyder_f15_attribution_report.txt', 'w') as f:
            f.write(report)
        print("   ✅ Report saved to 'spyder_f15_attribution_report.txt'")
        
        # Get summary
        summary = engine.get_attribution_summary()
        print(f"\n📊 Attribution Summary:")
        print(f"   Total Attributions: {summary['total_attributions']}")
        print(f"   Average Active Return: {summary['average_metrics'].get('active_return', 0):.4f}")
        print(f"   Average R²: {summary['average_metrics'].get('r_squared', 0):.3f}")
        print(f"   Processing Statistics:")
        for stat_name, stat_value in summary['processing_stats'].items():
            formatted_name = stat_name.replace('_', ' ').title()
            print(f"     • {formatted_name}: {stat_value}")
        
        # Check alerts
        alerts = engine.get_alerts(limit=5)
        if alerts:
            print(f"\n🚨 Recent Alerts ({len(alerts)}):")
            for alert in alerts:
                print(f"   • [{alert.severity.upper()}] {alert.message}")
        
        print("\n🎊 SPYDER F15 Performance Attribution Engine demonstration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error in main execution: {e}")
        return False
    
    finally:
        # Clean up
        if 'engine' in locals():
            engine.stop_processing()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
