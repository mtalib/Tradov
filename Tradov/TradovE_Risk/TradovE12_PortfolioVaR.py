#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System

Tradov Version: 1.0
Module: TradovE12_PortfolioVaR.py
Group: E (Risk Management)
Purpose: Portfolio Value at Risk (VaR) calculations and stress testing
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 18:00:00

Description:
    This module provides comprehensive Value at Risk (VaR) calculations for
    portfolio risk assessment. It implements multiple VaR methodologies including
    Historical, Parametric, and Monte Carlo simulation. Features include Component
    VaR for position-level risk attribution, Marginal VaR for trade impact analysis,
    Conditional VaR (CVaR) for tail risk, and sophisticated stress testing scenarios.

Key Features:
    - Multiple VaR calculation methods (Historical, Parametric, Monte Carlo)
    - Component VaR for risk attribution
    - Marginal VaR for incremental risk
    - Conditional VaR (Expected Shortfall)
    - Stress testing and scenario analysis
    - VaR backtesting and validation
    - Greeks-based VaR for options
    - Correlation-adjusted portfolio VaR
    - Real-time VaR updates
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, UTC
from typing import Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum
import threading
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from scipy import stats  # noqa: E402
from scipy.stats import norm, t, chi2, jarque_bera  # noqa: E402
from sklearn.covariance import LedoitWolf  # noqa: E402

# ==============================================================================
# TRADOV IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger  # noqa: E402
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler  # noqa: E402
from Tradov.TradovI_Integration.TradovI06_AgentMessageBus import MessagePriority  # noqa: E402

# ==============================================================================
# CONSTANTS
# ==============================================================================
# VaR parameters
DEFAULT_CONFIDENCE_LEVELS = [0.95, 0.99, 0.999]  # 95%, 99%, 99.9%
DEFAULT_TIME_HORIZON = 1  # 1 day VaR
LOOKBACK_PERIOD = 252  # 1 year of daily data
MONTE_CARLO_SIMULATIONS = 10000
BOOTSTRAP_SAMPLES = 1000

# Risk thresholds
VAR_WARNING_THRESHOLD = 0.05  # 5% of portfolio
VAR_CRITICAL_THRESHOLD = 0.10  # 10% of portfolio
CVAR_MULTIPLIER = 1.5  # CVaR typically 1.5x VaR

# Stress test scenarios
STRESS_SCENARIOS = {
    'BLACK_MONDAY': {'TRAD': -0.20, 'VIX': 2.5, 'correlation': 1.0},
    'FLASH_CRASH': {'TRAD': -0.09, 'VIX': 1.8, 'correlation': 0.9},
    'COVID_CRASH': {'TRAD': -0.12, 'VIX': 3.0, 'correlation': 0.95},
    'LEHMAN': {'TRAD': -0.15, 'VIX': 2.2, 'correlation': 0.85},
    'TAPER_TANTRUM': {'TRAD': -0.06, 'VIX': 1.5, 'correlation': 0.7},
    'RATE_SHOCK': {'TRAD': -0.08, 'rates': 0.5, 'correlation': 0.6}
}

# Greeks for options VaR
GREEKS_WEIGHTS = {
    'delta': 1.0,
    'gamma': 0.5,
    'vega': 0.3,
    'theta': -0.1,  # Theta is positive for portfolio
    'rho': 0.2
}

# ==============================================================================
# HELPERS
# ==============================================================================

def _json_default(obj):
    """JSON serialization helper: converts datetime/Enum/dataclass for json.dump."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, '__dataclass_fields__'):
        return asdict(obj)
    return str(obj)


# ==============================================================================
# ENUMS
# ==============================================================================
class VaRMethod(Enum):
    """VaR calculation methods"""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"
    CORNISH_FISHER = "cornish_fisher"
    FILTERED_HISTORICAL = "filtered_historical"
    GARCH = "garch"

class StressTestType(Enum):
    """Types of stress tests"""
    HISTORICAL = "historical"
    HYPOTHETICAL = "hypothetical"
    SENSITIVITY = "sensitivity"
    REVERSE = "reverse"
    FACTOR = "factor"

class RiskMeasure(Enum):
    """Risk measurement types"""
    VAR = "var"
    CVAR = "cvar"
    COMPONENT_VAR = "component_var"
    MARGINAL_VAR = "marginal_var"
    INCREMENTAL_VAR = "incremental_var"
    STRESSED_VAR = "stressed_var"

class BacktestResult(Enum):
    """VaR backtest outcomes"""
    GREEN = "green"  # Within expected range
    YELLOW = "yellow"  # Warning zone
    RED = "red"  # Model failure

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VaRResult:
    """Value at Risk calculation result"""
    method: VaRMethod
    confidence_level: float
    time_horizon: int  # Days
    portfolio_value: float
    var_amount: float  # Dollar VaR
    var_percentage: float  # Percentage VaR
    cvar_amount: float  # Conditional VaR
    cvar_percentage: float
    calculation_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_breach: bool = False
    breach_severity: str | None = None

@dataclass
class ComponentVaR:
    """Component VaR for individual positions"""
    position_id: str
    strategy_id: str
    position_value: float
    standalone_var: float
    component_var: float  # Contribution to portfolio VaR
    marginal_var: float  # Impact of small change
    var_contribution_pct: float  # Percentage contribution
    correlation_effect: float  # Diversification benefit

@dataclass
class StressTestResult:
    """Stress test scenario result"""
    scenario_name: str
    scenario_type: StressTestType
    portfolio_impact: float  # Dollar impact
    portfolio_impact_pct: float  # Percentage impact
    var_under_stress: float
    cvar_under_stress: float
    worst_positions: list[tuple[str, float]]  # position_id, impact
    recovery_time_estimate: int  # Days to recover

@dataclass
class BacktestReport:
    """VaR model backtest report"""
    method: VaRMethod
    confidence_level: float
    test_period: tuple[datetime, datetime]
    total_observations: int
    var_breaches: int
    expected_breaches: int
    breach_rate: float
    kupiec_test: tuple[float, float]  # statistic, p-value
    christoffersen_test: tuple[float, float]  # statistic, p-value
    result: BacktestResult
    model_quality: str  # Good, Warning, Failed

@dataclass
class PortfolioRiskMetrics:
    """Comprehensive portfolio risk metrics"""
    total_var_95: float
    total_var_99: float
    total_cvar_95: float
    total_cvar_99: float
    component_vars: list[ComponentVaR]
    correlation_matrix: np.ndarray | None
    diversification_ratio: float
    concentration_risk: float
    tail_risk_measure: float
    stress_test_results: list[StressTestResult]
    last_update: datetime = field(default_factory=lambda: datetime.now(UTC))

# ==============================================================================
# MAIN PORTFOLIO VAR CLASS
# ==============================================================================
class PortfolioVaR:
    """
    Portfolio Value at Risk calculation and management system.

    Provides comprehensive VaR analysis including multiple calculation methods,
    component attribution, stress testing, and backtesting capabilities.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize Portfolio VaR system"""
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()
        self.config = config or {}

        # Portfolio data
        self.portfolio_value = self.config.get('portfolio_value', 1000000)
        self.positions = {}  # position_id -> position data
        self.position_returns = defaultdict(lambda: deque(maxlen=LOOKBACK_PERIOD))
        self.portfolio_returns = deque(maxlen=LOOKBACK_PERIOD)

        # VaR parameters
        self.confidence_levels = self.config.get('confidence_levels', DEFAULT_CONFIDENCE_LEVELS)
        self.time_horizon = self.config.get('time_horizon', DEFAULT_TIME_HORIZON)

        # Risk matrices
        self.correlation_matrix = None
        self.covariance_matrix = None
        self.last_matrix_update = None

        # VaR results cache
        self.current_var = {}  # method -> VaRResult
        self.component_vars = []
        self.stress_results = []

        # Backtesting
        self.backtest_history = deque(maxlen=252)
        self.var_breach_history = deque(maxlen=100)

        # Risk limits
        self.var_limits = {
            0.95: self.config.get('var_limit_95', 0.05),  # 5% limit
            0.99: self.config.get('var_limit_99', 0.10),  # 10% limit
        }

        # Integration
        self.max_loss_protection = None
        self.allocator = None
        self.message_bus = None

        # Threading
        self._lock = threading.RLock()
        self._shutdown = threading.Event()

        # Initialize components
        self._initialize_risk_models()
        self._load_historical_data()

        self.logger.info("Portfolio VaR system initialized")

    def _initialize_risk_models(self):
        """Initialize risk models and parameters"""
        # Initialize shrinkage estimator for covariance
        self.cov_estimator = LedoitWolf()

        # Initialize GARCH model parameters (simplified)
        self.garch_params = {
            'omega': 0.00001,  # Long-term variance
            'alpha': 0.1,  # ARCH parameter
            'beta': 0.85  # GARCH parameter
        }

        self.logger.info("Risk models initialized")

    def _load_historical_data(self):
        """Load historical VaR and backtest data"""
        try:
            history_file = Path("data/risk/var_history.json")
            # Backward-compat: migrate from legacy .pkl if .json not present
            if not history_file.exists():
                legacy = history_file.with_suffix('.pkl')
                if legacy.exists():
                    import joblib as _joblib
                    with open(legacy, 'rb') as _f:
                        _data = _joblib.load(_f)
                    history_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(history_file, 'w', encoding='utf-8') as _f:
                        json.dump(_data, _f, default=_json_default, indent=2)
            if history_file.exists():
                with open(history_file, encoding='utf-8') as f:
                    data = json.load(f)
                    self.backtest_history = deque(data['backtests'], maxlen=252)
                    self.var_breach_history = deque(data['breaches'], maxlen=100)
                    self.logger.info("Loaded %s historical VaR records", len(self.backtest_history))
        except Exception as e:
            self.logger.warning("Could not load VaR history: %s", e)

    def update_position(
        self,
        position_id: str,
        strategy_id: str,
        value: float,
        greeks: dict[str, float] | None = None,
        returns_history: list[float] | None = None
    ):
        """
        Update position data for VaR calculation.

        Args:
            position_id: Unique position identifier
            strategy_id: Strategy this position belongs to
            value: Current position value
            greeks: Option Greeks if applicable
            returns_history: Historical returns
        """
        with self._lock:
            self.positions[position_id] = {
                'strategy_id': strategy_id,
                'value': value,
                'greeks': greeks or {},
                'last_update': datetime.now(UTC)
            }

            if returns_history:
                self.position_returns[position_id].extend(returns_history)

            self.logger.debug(f"Updated position {position_id}: ${value:,.0f}")

    def calculate_var(
        self,
        method: VaRMethod = VaRMethod.HISTORICAL,
        confidence_level: float = 0.99,
        time_horizon: int = 1
    ) -> VaRResult:
        """
        Calculate portfolio VaR using specified method.

        Args:
            method: VaR calculation method
            confidence_level: Confidence level (e.g., 0.99 for 99%)
            time_horizon: Time horizon in days

        Returns:
            VaRResult with calculated values
        """
        with self._lock:
            try:
                self.logger.info(f"Calculating {method.value} VaR at {confidence_level:.1%} confidence")  # noqa: E501

                # Get portfolio returns
                returns = self._get_portfolio_returns()

                if len(returns) < 30:
                    self.logger.warning("Insufficient data for VaR calculation")
                    return self._create_default_var_result(method, confidence_level)

                # Calculate VaR based on method
                if method == VaRMethod.HISTORICAL:
                    var_pct, cvar_pct = self._calculate_historical_var(returns, confidence_level)

                elif method == VaRMethod.PARAMETRIC:
                    var_pct, cvar_pct = self._calculate_parametric_var(returns, confidence_level)

                elif method == VaRMethod.MONTE_CARLO:
                    var_pct, cvar_pct = self._calculate_monte_carlo_var(returns, confidence_level)

                elif method == VaRMethod.CORNISH_FISHER:
                    var_pct, cvar_pct = self._calculate_cornish_fisher_var(returns, confidence_level)  # noqa: E501

                elif method == VaRMethod.FILTERED_HISTORICAL:
                    var_pct, cvar_pct = self._calculate_filtered_historical_var(returns, confidence_level)  # noqa: E501

                else:  # GARCH
                    var_pct, cvar_pct = self._calculate_garch_var(returns, confidence_level)

                # Scale for time horizon
                if time_horizon > 1:
                    var_pct *= np.sqrt(time_horizon)
                    cvar_pct *= np.sqrt(time_horizon)

                # Convert to dollar amounts
                var_amount = self.portfolio_value * abs(var_pct)
                cvar_amount = self.portfolio_value * abs(cvar_pct)

                # Check for breaches
                is_breach = abs(var_pct) > self.var_limits.get(confidence_level, 0.10)
                breach_severity = None
                if is_breach:
                    if abs(var_pct) > 0.15:
                        breach_severity = "CRITICAL"
                    elif abs(var_pct) > 0.10:
                        breach_severity = "HIGH"
                    else:
                        breach_severity = "MEDIUM"

                # Create result
                result = VaRResult(
                    method=method,
                    confidence_level=confidence_level,
                    time_horizon=time_horizon,
                    portfolio_value=self.portfolio_value,
                    var_amount=var_amount,
                    var_percentage=abs(var_pct),
                    cvar_amount=cvar_amount,
                    cvar_percentage=abs(cvar_pct),
                    is_breach=is_breach,
                    breach_severity=breach_severity
                )

                # Cache result
                self.current_var[method] = result

                # Send alert if breach
                if is_breach:
                    self._send_var_breach_alert(result)

                return result

            except Exception as e:
                self.logger.error("VaR calculation failed: %s", e)
                self.error_handler.handle_error(e, {"method": method.value})
                return self._create_default_var_result(method, confidence_level)

    def _get_portfolio_returns(self) -> np.ndarray:
        """Get portfolio returns from position returns"""
        if len(self.portfolio_returns) > 0:
            return np.array(self.portfolio_returns)

        # Calculate from position returns
        portfolio_returns = []

        # Get minimum common length
        min_length = min(len(returns) for returns in self.position_returns.values()) if self.position_returns else 0  # noqa: E501

        if min_length > 0:
            # Weight by position values
            total_value = sum(pos['value'] for pos in self.positions.values())

            for i in range(min_length):
                weighted_return = 0
                for pos_id, pos_data in self.positions.items():
                    if pos_id in self.position_returns:
                        weight = pos_data['value'] / total_value if total_value > 0 else 0
                        weighted_return += weight * self.position_returns[pos_id][i]

                portfolio_returns.append(weighted_return)

        return np.array(portfolio_returns) if portfolio_returns else np.array([])

    def _calculate_historical_var(
        self,
        returns: np.ndarray,
        confidence_level: float
    ) -> tuple[float, float]:
        """Calculate Historical VaR"""
        # Sort returns
        sorted_returns = np.sort(returns)

        # Find VaR percentile
        var_index = int((1 - confidence_level) * len(sorted_returns))
        var = sorted_returns[var_index]

        # Calculate CVaR (average of returns worse than VaR)
        cvar = np.mean(sorted_returns[:var_index]) if var_index > 0 else var

        return var, cvar

    def _calculate_parametric_var(
        self,
        returns: np.ndarray,
        confidence_level: float
    ) -> tuple[float, float]:
        """Calculate Parametric (Variance-Covariance) VaR"""
        # Calculate mean and standard deviation
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Calculate VaR using normal distribution
        z_score = norm.ppf(1 - confidence_level)
        var = mean_return + z_score * std_return

        # Calculate CVaR for normal distribution
        pdf_z = norm.pdf(z_score)
        cvar = mean_return - std_return * pdf_z / (1 - confidence_level)

        return var, cvar

    def _calculate_monte_carlo_var(
        self,
        returns: np.ndarray,
        confidence_level: float
    ) -> tuple[float, float]:
        """Calculate Monte Carlo VaR"""
        # Fit distribution parameters
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Check for fat tails using Jarque-Bera test
        jb_stat, jb_pvalue = jarque_bera(returns)

        if jb_pvalue < 0.05:  # Non-normal, use t-distribution
            # Fit t-distribution
            df, loc, scale = t.fit(returns)
            simulated_returns = t.rvs(df, loc=loc, scale=scale, size=MONTE_CARLO_SIMULATIONS)
        else:
            # Use normal distribution
            simulated_returns = np.random.normal(mean_return, std_return, MONTE_CARLO_SIMULATIONS)

        # Calculate VaR from simulated returns
        sorted_sim = np.sort(simulated_returns)
        var_index = int((1 - confidence_level) * len(sorted_sim))
        var = sorted_sim[var_index]

        # Calculate CVaR
        cvar = np.mean(sorted_sim[:var_index]) if var_index > 0 else var

        return var, cvar

    def _calculate_cornish_fisher_var(
        self,
        returns: np.ndarray,
        confidence_level: float
    ) -> tuple[float, float]:
        """Calculate Cornish-Fisher VaR (adjusts for skewness and kurtosis)"""
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        skewness = stats.skew(returns)
        excess_kurtosis = stats.kurtosis(returns)

        # Standard normal quantile
        z = norm.ppf(1 - confidence_level)

        # Cornish-Fisher expansion
        cf_z = (z +
                (z**2 - 1) * skewness / 6 +
                (z**3 - 3*z) * excess_kurtosis / 24 -
                (2*z**3 - 5*z) * skewness**2 / 36)

        # Calculate VaR
        var = mean_return + cf_z * std_return

        # Approximate CVaR (simplified)
        cvar = var * CVAR_MULTIPLIER

        return var, cvar

    def _calculate_filtered_historical_var(
        self,
        returns: np.ndarray,
        confidence_level: float
    ) -> tuple[float, float]:
        """Calculate Filtered Historical Simulation VaR"""
        # Apply EWMA volatility adjustment
        lambda_param = 0.94  # Decay factor

        # Calculate EWMA volatility
        weights = np.array([(1 - lambda_param) * lambda_param**i
                          for i in range(len(returns)-1, -1, -1)])
        weights /= weights.sum()

        # Adjust returns by current volatility
        current_vol = np.sqrt(np.sum(weights * returns**2))
        long_term_vol = np.std(returns)

        # Scale historical returns
        scaled_returns = returns * (current_vol / long_term_vol)

        # Calculate VaR on scaled returns
        return self._calculate_historical_var(scaled_returns, confidence_level)

    def _calculate_garch_var(
        self,
        returns: np.ndarray,
        confidence_level: float
    ) -> tuple[float, float]:
        """Calculate GARCH-based VaR"""
        # Simplified GARCH(1,1) implementation
        omega = self.garch_params['omega']
        alpha = self.garch_params['alpha']
        beta = self.garch_params['beta']

        # Initialize variance
        variance = np.var(returns)

        # GARCH variance forecast
        for ret in returns[-10:]:  # Use last 10 returns
            variance = omega + alpha * ret**2 + beta * variance

        # Next period volatility
        next_vol = np.sqrt(variance)

        # Calculate VaR
        z_score = norm.ppf(1 - confidence_level)
        var = np.mean(returns) + z_score * next_vol

        # CVaR approximation
        cvar = var * CVAR_MULTIPLIER

        return var, cvar

    def calculate_component_var(self) -> list[ComponentVaR]:
        """
        Calculate Component VaR for all positions.

        Returns:
            List of ComponentVaR for each position
        """
        with self._lock:
            try:
                component_vars = []

                # Get portfolio VaR
                portfolio_var = self.calculate_var(VaRMethod.PARAMETRIC, 0.99)

                # Calculate correlation matrix if needed
                if self.last_matrix_update is None or \
                   (datetime.now(UTC) - self.last_matrix_update).days > 7:
                    self._update_correlation_matrix()

                total_value = sum(pos['value'] for pos in self.positions.values())

                for pos_id, pos_data in self.positions.items():
                    # Calculate standalone VaR
                    pos_returns = np.array(self.position_returns[pos_id]) if pos_id in self.position_returns else np.array([])  # noqa: E501

                    if len(pos_returns) > 30:
                        standalone_var = abs(np.percentile(pos_returns, 1)) * pos_data['value']
                    else:
                        standalone_var = pos_data['value'] * 0.05  # Default 5%

                    # Calculate component VaR (simplified)
                    weight = pos_data['value'] / total_value if total_value > 0 else 0
                    component_var_amount = portfolio_var.var_amount * weight

                    # Calculate marginal VaR
                    marginal_var = component_var_amount / pos_data['value'] if pos_data['value'] > 0 else 0  # noqa: E501

                    # Diversification effect
                    correlation_effect = 1 - (component_var_amount / standalone_var) if standalone_var > 0 else 0  # noqa: E501

                    component = ComponentVaR(
                        position_id=pos_id,
                        strategy_id=pos_data['strategy_id'],
                        position_value=pos_data['value'],
                        standalone_var=standalone_var,
                        component_var=component_var_amount,
                        marginal_var=marginal_var,
                        var_contribution_pct=component_var_amount / portfolio_var.var_amount if portfolio_var.var_amount > 0 else 0,  # noqa: E501
                        correlation_effect=correlation_effect
                    )

                    component_vars.append(component)

                # Sort by contribution
                component_vars.sort(key=lambda x: x.component_var, reverse=True)

                # Cache results
                self.component_vars = component_vars

                return component_vars

            except Exception as e:
                self.logger.error("Component VaR calculation failed: %s", e)
                return []

    def _update_correlation_matrix(self):
        """Update correlation and covariance matrices"""
        try:
            # Collect returns data
            positions = list(self.positions.keys())
            returns_matrix = []

            for pos_id in positions:
                if pos_id in self.position_returns:
                    returns_matrix.append(list(self.position_returns[pos_id]))

            if len(returns_matrix) > 1:
                returns_df = pd.DataFrame(returns_matrix).T

                # Calculate correlation
                self.correlation_matrix = returns_df.corr().values

                # Calculate covariance with shrinkage
                self.covariance_matrix, _ = self.cov_estimator.fit(returns_df.values)

                self.last_matrix_update = datetime.now(UTC)

        except Exception as e:
            self.logger.error("Matrix update failed: %s", e)

    def run_stress_tests(
        self,
        scenarios: dict[str, dict] | None = None
    ) -> list[StressTestResult]:
        """
        Run stress test scenarios on portfolio.

        Args:
            scenarios: Custom scenarios or use defaults

        Returns:
            List of StressTestResult
        """
        with self._lock:
            try:
                scenarios = scenarios or STRESS_SCENARIOS
                results = []

                for scenario_name, scenario_params in scenarios.items():
                    self.logger.info("Running stress test: %s", scenario_name)

                    # Calculate scenario impact
                    impact = self._calculate_scenario_impact(scenario_params)

                    # Calculate stressed VaR
                    stressed_returns = self._apply_scenario_to_returns(scenario_params)
                    stressed_var, stressed_cvar = self._calculate_historical_var(stressed_returns, 0.99)  # noqa: E501

                    # Find worst affected positions
                    worst_positions = self._find_worst_positions(scenario_params)

                    # Estimate recovery time
                    recovery_time = self._estimate_recovery_time(abs(impact))

                    result = StressTestResult(
                        scenario_name=scenario_name,
                        scenario_type=StressTestType.HISTORICAL,
                        portfolio_impact=impact * self.portfolio_value,
                        portfolio_impact_pct=impact,
                        var_under_stress=abs(stressed_var) * self.portfolio_value,
                        cvar_under_stress=abs(stressed_cvar) * self.portfolio_value,
                        worst_positions=worst_positions[:5],  # Top 5
                        recovery_time_estimate=recovery_time
                    )

                    results.append(result)

                # Cache results
                self.stress_results = results

                # Send alerts for severe impacts
                for result in results:
                    if abs(result.portfolio_impact_pct) > 0.15:
                        self._send_stress_test_alert(result)

                return results

            except Exception as e:
                self.logger.error("Stress testing failed: %s", e)
                return []

    def _calculate_scenario_impact(self, scenario: dict) -> float:
        """Calculate portfolio impact of scenario"""
        # Simplified impact calculation
        spy_impact = scenario.get('TRAD', 0)
        vix_multiplier = scenario.get('VIX', 1)

        # Base impact from market move
        base_impact = spy_impact

        # Adjust for volatility
        if vix_multiplier > 1:
            base_impact *= (1 + (vix_multiplier - 1) * 0.2)

        # Adjust for correlation
        correlation = scenario.get('correlation', 0.5)
        base_impact *= (0.5 + correlation * 0.5)

        return base_impact

    def _apply_scenario_to_returns(self, scenario: dict) -> np.ndarray:
        """Apply stress scenario to historical returns"""
        returns = self._get_portfolio_returns()

        if len(returns) == 0:
            return np.array([])

        # Apply scenario shock
        shock = scenario.get('TRAD', 0)
        vol_mult = scenario.get('VIX', 1)

        # Scale returns by scenario
        stressed_returns = returns * vol_mult
        stressed_returns = stressed_returns + shock

        return stressed_returns

    def _find_worst_positions(self, scenario: dict) -> list[tuple[str, float]]:
        """Find positions most affected by scenario"""
        worst = []

        for pos_id, pos_data in self.positions.items():
            # Calculate position-specific impact
            impact = scenario.get('TRAD', 0) * pos_data['value']

            # Adjust for Greeks if options
            if 'greeks' in pos_data and pos_data['greeks']:
                greeks = pos_data['greeks']

                # Delta impact
                if 'delta' in greeks:
                    impact *= abs(greeks['delta'])

                # Vega impact from volatility
                if 'vega' in greeks and 'VIX' in scenario:
                    vega_impact = greeks['vega'] * (scenario['VIX'] - 1) * 0.01
                    impact += vega_impact * pos_data['value']

            worst.append((pos_id, impact))

        # Sort by impact
        worst.sort(key=lambda x: abs(x[1]), reverse=True)

        return worst

    def _estimate_recovery_time(self, impact: float) -> int:
        """Estimate recovery time in days"""
        # Simple heuristic
        if impact < 0.05:
            return 5
        elif impact < 0.10:
            return 20
        elif impact < 0.15:
            return 60
        else:
            return 120

    def backtest_var(
        self,
        method: VaRMethod,
        confidence_level: float,
        test_period: int = 252
    ) -> BacktestReport:
        """
        Backtest VaR model accuracy.

        Args:
            method: VaR method to test
            confidence_level: Confidence level
            test_period: Days to test

        Returns:
            BacktestReport with test results
        """
        try:
            returns = self._get_portfolio_returns()

            if len(returns) < test_period + 30:
                self.logger.warning("Insufficient data for backtesting")
                return self._create_default_backtest_report(method, confidence_level)

            breaches = 0
            breach_dates = []

            # Rolling VaR calculation
            for i in range(test_period):
                # Calculate VaR on historical window
                historical_returns = returns[i:i+252] if i+252 < len(returns) else returns[i:]

                if method == VaRMethod.HISTORICAL:
                    var, _ = self._calculate_historical_var(historical_returns, confidence_level)
                elif method == VaRMethod.PARAMETRIC:
                    var, _ = self._calculate_parametric_var(historical_returns, confidence_level)
                else:
                    var, _ = self._calculate_historical_var(historical_returns, confidence_level)

                # Check if next day's return breaches VaR
                if i+252 < len(returns):
                    next_return = returns[i+252]
                    if next_return < var:
                        breaches += 1
                        breach_dates.append(i)

            # Calculate statistics
            breach_rate = breaches / test_period
            expected_breaches = test_period * (1 - confidence_level)
            1 - confidence_level

            # Kupiec test (unconditional coverage)
            kupiec_stat, kupiec_pval = self._kupiec_test(
                breaches, test_period, confidence_level
            )

            # Christoffersen test (conditional coverage)
            christ_stat, christ_pval = self._christoffersen_test(
                breach_dates, test_period, confidence_level
            )

            # Determine result
            if kupiec_pval > 0.05 and christ_pval > 0.05:
                result = BacktestResult.GREEN
                quality = "Good"
            elif kupiec_pval > 0.01 or christ_pval > 0.01:
                result = BacktestResult.YELLOW
                quality = "Warning"
            else:
                result = BacktestResult.RED
                quality = "Failed"

            report = BacktestReport(
                method=method,
                confidence_level=confidence_level,
                test_period=(datetime.now(UTC) - timedelta(days=test_period), datetime.now(UTC)),
                total_observations=test_period,
                var_breaches=breaches,
                expected_breaches=int(expected_breaches),
                breach_rate=breach_rate,
                kupiec_test=(kupiec_stat, kupiec_pval),
                christoffersen_test=(christ_stat, christ_pval),
                result=result,
                model_quality=quality
            )

            # Store in history
            self.backtest_history.append(report)

            return report

        except Exception as e:
            self.logger.error("Backtesting failed: %s", e)
            return self._create_default_backtest_report(method, confidence_level)

    def _kupiec_test(
        self,
        breaches: int,
        total: int,
        confidence: float
    ) -> tuple[float, float]:
        """Kupiec unconditional coverage test"""
        expected_rate = 1 - confidence
        observed_rate = breaches / total

        if breaches == 0 or breaches == total:
            return 0, 1  # Perfect or terrible model

        # Likelihood ratio statistic
        lr = -2 * np.log(
            (expected_rate**breaches * (1-expected_rate)**(total-breaches)) /
            (observed_rate**breaches * (1-observed_rate)**(total-breaches))
        )

        # Chi-square test with 1 degree of freedom
        p_value = 1 - chi2.cdf(lr, 1)

        return lr, p_value

    def _christoffersen_test(
        self,
        breach_dates: list[int],
        total: int,
        confidence: float
    ) -> tuple[float, float]:
        """Christoffersen conditional coverage test"""
        if len(breach_dates) < 2:
            return 0, 1

        # Count transitions
        n00 = n01 = n10 = n11 = 0

        for i in range(1, total):
            prev_breach = (i-1) in breach_dates
            curr_breach = i in breach_dates

            if not prev_breach and not curr_breach:
                n00 += 1
            elif not prev_breach and curr_breach:
                n01 += 1
            elif prev_breach and not curr_breach:
                n10 += 1
            else:  # prev_breach and curr_breach
                n11 += 1

        # Transition probabilities
        p01 = n01 / (n00 + n01) if (n00 + n01) > 0 else 0
        p11 = n11 / (n10 + n11) if (n10 + n11) > 0 else 0
        p = (n01 + n11) / total

        # Likelihood ratio statistic
        if p01 > 0 and p11 > 0 and p > 0:
            lr = -2 * np.log(
                (p**(n01+n11) * (1-p)**(n00+n10)) /
                (p01**n01 * (1-p01)**n00 * p11**n11 * (1-p11)**n10)
            )
        else:
            lr = 0

        # Chi-square test with 1 degree of freedom
        p_value = 1 - chi2.cdf(lr, 1)

        return lr, p_value

    def get_risk_report(self) -> PortfolioRiskMetrics:
        """Get comprehensive risk metrics report"""
        # Calculate all VaR measures
        var_95 = self.calculate_var(VaRMethod.HISTORICAL, 0.95)
        var_99 = self.calculate_var(VaRMethod.HISTORICAL, 0.99)

        # Calculate component VaRs
        component_vars = self.calculate_component_var()

        # Calculate diversification ratio
        if component_vars:
            sum_standalone = sum(c.standalone_var for c in component_vars)
            portfolio_var = var_99.var_amount
            div_ratio = sum_standalone / portfolio_var if portfolio_var > 0 else 1
        else:
            div_ratio = 1

        # Calculate concentration risk (Herfindahl index)
        if self.positions:
            total_value = sum(pos['value'] for pos in self.positions.values())
            weights = [pos['value']/total_value for pos in self.positions.values()]
            concentration = sum(w**2 for w in weights)
        else:
            concentration = 0

        # Tail risk measure
        returns = self._get_portfolio_returns()
        if len(returns) > 100:
            tail_risk = abs(np.percentile(returns, 1) / np.percentile(returns, 5))
        else:
            tail_risk = 1

        # Run stress tests if not recent
        if not self.stress_results or \
           (datetime.now(UTC) - self.stress_results[0].calculation_time).days > 7:
            stress_results = self.run_stress_tests()
        else:
            stress_results = self.stress_results

        return PortfolioRiskMetrics(
            total_var_95=var_95.var_amount,
            total_var_99=var_99.var_amount,
            total_cvar_95=var_95.cvar_amount,
            total_cvar_99=var_99.cvar_amount,
            component_vars=component_vars,
            correlation_matrix=self.correlation_matrix,
            diversification_ratio=div_ratio,
            concentration_risk=concentration,
            tail_risk_measure=tail_risk,
            stress_test_results=stress_results
        )

    def _create_default_var_result(
        self,
        method: VaRMethod,
        confidence_level: float
    ) -> VaRResult:
        """Create default VaR result when calculation fails"""
        return VaRResult(
            method=method,
            confidence_level=confidence_level,
            time_horizon=1,
            portfolio_value=self.portfolio_value,
            var_amount=self.portfolio_value * 0.05,
            var_percentage=0.05,
            cvar_amount=self.portfolio_value * 0.075,
            cvar_percentage=0.075,
            is_breach=False,
            breach_severity=None
        )

    def _create_default_backtest_report(
        self,
        method: VaRMethod,
        confidence_level: float
    ) -> BacktestReport:
        """Create default backtest report"""
        return BacktestReport(
            method=method,
            confidence_level=confidence_level,
            test_period=(datetime.now(UTC) - timedelta(days=252), datetime.now(UTC)),
            total_observations=0,
            var_breaches=0,
            expected_breaches=0,
            breach_rate=0,
            kupiec_test=(0, 1),
            christoffersen_test=(0, 1),
            result=BacktestResult.YELLOW,
            model_quality="No Data"
        )

    def _send_var_breach_alert(self, result: VaRResult):
        """Send VaR breach alert via message bus"""
        if self.message_bus:
            self.message_bus.publish(
                topic="risk.var_breach",
                sender="PortfolioVaR",
                priority=MessagePriority.CRITICAL,
                payload={
                    'var_amount': result.var_amount,
                    'var_percentage': result.var_percentage,
                    'confidence_level': result.confidence_level,
                    'severity': result.breach_severity,
                    'timestamp': result.calculation_time.isoformat()
                },
            )

    def _send_stress_test_alert(self, result: StressTestResult):
        """Send stress test alert for severe scenarios"""
        if self.message_bus:
            self.message_bus.publish(
                topic="risk.stress_test",
                sender="PortfolioVaR",
                priority=MessagePriority.HIGH,
                payload={
                    'scenario': result.scenario_name,
                    'impact': result.portfolio_impact,
                    'impact_pct': result.portfolio_impact_pct,
                    'recovery_days': result.recovery_time_estimate
                },
            )

    def shutdown(self):
        """Shutdown VaR system and save state"""
        self._shutdown.set()

        # Save history
        try:
            history_file = Path("data/risk/var_history.json")
            history_file.parent.mkdir(parents=True, exist_ok=True)

            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'backtests': list(self.backtest_history),
                    'breaches': list(self.var_breach_history),
                    'timestamp': datetime.now(UTC)
                }, f, default=_json_default, indent=2)

            self.logger.info("VaR history saved")
        except Exception as e:
            self.logger.error("Failed to save VaR history: %s", e)

        self.logger.info("Portfolio VaR shutdown complete")

    # ==========================================================================
    # RAY DISTRIBUTED COMPUTING (Phase 3)
    # ==========================================================================

    def calculate_distributed_monte_carlo_var(
        self,
        returns: np.ndarray,
        confidence_level: float = 0.99,
        n_simulations: int = MONTE_CARLO_SIMULATIONS,
        num_cpus: int | None = None
    ) -> dict[str, Any]:
        """
        Calculate Monte Carlo VaR using Ray distributed computing.

        Distributes simulation batches across Ray workers for near-linear
        speedup on large simulation counts.

        Args:
            returns: Historical return series.
            confidence_level: VaR confidence level (e.g., 0.99).
            n_simulations: Total number of Monte Carlo simulations.
            num_cpus: Number of CPUs to allocate.

        Returns:
            Dictionary with VaR, CVaR, and distribution statistics.
        """
        try:
            import ray
        except ImportError:
            self.logger.warning("Ray not available, using sequential Monte Carlo VaR")
            var, cvar = self._calculate_monte_carlo_var(returns, confidence_level)
            return {'var': var, 'cvar': cvar, 'backend': 'sequential'}

        import multiprocessing as mproc
        if not ray.is_initialized():
            ray.init(num_cpus=num_cpus or mproc.cpu_count(), ignore_reinit_error=True)

        n_workers = num_cpus or mproc.cpu_count()
        chunk_size = n_simulations // n_workers
        remainder = n_simulations % n_workers

        # Fit distribution parameters once
        mean_ret = float(np.mean(returns))
        std_ret = float(np.std(returns))
        jb_stat, jb_pvalue = jarque_bera(returns)
        use_t = jb_pvalue < 0.05

        if use_t:
            from scipy.stats import t as t_dist
            df_t, loc_t, scale_t = t_dist.fit(returns)
            dist_params = {'type': 't', 'df': df_t, 'loc': loc_t, 'scale': scale_t}
        else:
            dist_params = {'type': 'normal', 'mean': mean_ret, 'std': std_ret}

        params_ref = ray.put(dist_params)

        @ray.remote
        def _simulate_var_chunk(params_ref, n_sims: int, seed: int) -> list[float]:
            """Generate Monte Carlo VaR simulations on a Ray worker."""
            import numpy as _np
            _np.random.seed(seed)
            params = params_ref

            if params['type'] == 't':
                from scipy.stats import t as _t
                sims = _t.rvs(params['df'], loc=params['loc'],
                              scale=params['scale'], size=n_sims)
            else:
                sims = _np.random.normal(params['mean'], params['std'], n_sims)

            return sims.tolist()

        self.logger.info("Ray VaR: %s simulations across %s workers", n_simulations, n_workers)
        import time
        start_time = time.time()

        futures = []
        for i in range(n_workers):
            n = chunk_size + (1 if i < remainder else 0)
            futures.append(_simulate_var_chunk.remote(params_ref, n, seed=42 + i))

        chunk_results = ray.get(futures)
        all_sims = []
        for chunk in chunk_results:
            all_sims.extend(chunk)

        sim_array = np.sort(np.array(all_sims))
        var_index = int((1 - confidence_level) * len(sim_array))
        var_value = float(sim_array[var_index])
        cvar_value = float(np.mean(sim_array[:var_index])) if var_index > 0 else var_value

        computation_time = time.time() - start_time

        results = {
            'var': var_value,
            'cvar': cvar_value,
            'confidence_level': confidence_level,
            'n_simulations': len(all_sims),
            'distribution_type': dist_params['type'],
            'backend': 'ray',
            'num_workers': n_workers,
            'computation_time': computation_time,
            'percentiles': {
                'p1': float(np.percentile(sim_array, 1)),
                'p5': float(np.percentile(sim_array, 5)),
                'p10': float(np.percentile(sim_array, 10)),
                'p50': float(np.percentile(sim_array, 50)),
                'p90': float(np.percentile(sim_array, 90)),
                'p95': float(np.percentile(sim_array, 95)),
                'p99': float(np.percentile(sim_array, 99)),
            },
            'statistics': {
                'mean': float(np.mean(sim_array)),
                'std': float(np.std(sim_array)),
                'skew': float(pd.Series(sim_array).skew()),
                'kurtosis': float(pd.Series(sim_array).kurtosis()),
            },
        }

        self.logger.info(f"Ray VaR complete: VaR={var_value:.4f}, CVaR={cvar_value:.4f}, "
                          f"{computation_time:.2f}s")
        return results

    # --------------------------------------------------------------------------
    # RISKFOLIO-LIB: EXTENDED RISK MEASURES
    # --------------------------------------------------------------------------

    def compute_extended_risk_measures(
        self,
        returns_data: pd.DataFrame,
        confidence: float = 0.95,
    ) -> dict[str, Any]:
        """
        Compute extended risk measures using RiskFolio-Lib.

        Adds CDaR (Conditional Drawdown at Risk), EVaR (Entropic VaR),
        and UCI (Ulcer Index) beyond standard VaR/CVaR.

        Args:
            returns_data: DataFrame of portfolio returns.
            confidence: Confidence level for risk measures.

        Returns:
            Dictionary of extended risk measures.
        """
        try:
            import riskfolio as rp
        except ImportError:
            self.logger.warning("riskfolio not installed — using basic risk measures")
            return {'status': 'riskfolio_not_installed'}

        port = rp.Portfolio(returns=returns_data)
        port.assets_stats(method_mu='hist', method_cov='ledoit_wolf')

        1 - confidence
        risk_measures = {}

        # Compute equal-weight portfolio risk for each measure
        n = returns_data.shape[1]
        np.ones((n, 1)) / n

        measures = ['MV', 'CVaR', 'CDaR', 'UCI', 'MDD']
        measure_names = {
            'MV': 'mean_variance',
            'CVaR': 'conditional_var',
            'CDaR': 'conditional_drawdown_at_risk',
            'UCI': 'ulcer_index',
            'MDD': 'max_drawdown',
        }

        for rm in measures:
            try:
                opt_weights = port.optimization(
                    model='Classic', rm=rm, obj='MinRisk',
                    rf=0.05 / 252, hist=True)
                if opt_weights is not None and not opt_weights.empty:
                    risk_measures[f'{measure_names[rm]}_optimal_weights'] = {
                        col: float(opt_weights.loc[col].iloc[0])
                        for col in opt_weights.index
                    }
            except Exception as e:
                self.logger.debug("Risk measure %s failed: %s", rm, e)
                risk_measures[f'{measure_names[rm]}_optimal_weights'] = None

        risk_measures['confidence'] = confidence
        risk_measures['n_assets'] = n
        risk_measures['_backend'] = 'riskfolio'

        self.logger.info("Extended risk measures: %s computed", len(measures))
        return risk_measures


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_portfolio_var(config: dict[str, Any] | None = None) -> PortfolioVaR:
    """Create and initialize PortfolioVaR instance"""
    return PortfolioVaR(config)


# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":
    # Test configuration
    config = {
        'portfolio_value': 1000000,
        'var_limit_95': 0.05,
        'var_limit_99': 0.10
    }

    # Create VaR system
    var_system = create_portfolio_var(config)


    # Add test positions

    positions = [
        ('POS001', 'D02_IronCondor', 200000),
        ('POS002', 'D05_Straddle', 150000),
        ('POS003', 'D04_ZeroDTE', 100000),
        ('POS004', 'D14_CalendarSpread', 250000),
        ('POS005', 'D03_CreditSpread', 300000)
    ]

    # Generate fake returns
    for pos_id, strategy, value in positions:
        # Simulate returns with different risk profiles
        if 'ZeroDTE' in strategy:
            returns = np.random.normal(-0.001, 0.03, 252)  # Higher risk
        elif 'Straddle' in strategy:
            returns = np.random.normal(0.0005, 0.025, 252)
        else:
            returns = np.random.normal(0.001, 0.015, 252)  # Lower risk

        var_system.update_position(pos_id, strategy, value, returns_history=list(returns))

    # Store portfolio returns for testing
    var_system.portfolio_returns.extend(np.random.normal(0.0005, 0.02, 252))

    # Calculate VaR using different methods

    methods = [
        VaRMethod.HISTORICAL,
        VaRMethod.PARAMETRIC,
        VaRMethod.MONTE_CARLO,
        VaRMethod.CORNISH_FISHER
    ]

    for method in methods:
        result = var_system.calculate_var(method, 0.99)
        if result.is_breach:
            pass

    # Calculate Component VaR

    components = var_system.calculate_component_var()
    for _comp in components[:3]:
        pass

    # Run stress tests

    stress_results = var_system.run_stress_tests()
    for _ in stress_results[:3]:
        pass

    # Backtest VaR model

    backtest = var_system.backtest_var(VaRMethod.HISTORICAL, 0.99, test_period=100)

    # Get comprehensive risk report

    metrics = var_system.get_risk_report()

    # Shutdown
    var_system.shutdown()
