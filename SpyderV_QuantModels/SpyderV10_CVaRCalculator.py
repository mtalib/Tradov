#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderV102_CVaRCalculator.py
Group: V_QuantModels
Purpose: Conditional Value at Risk (CVaR) calculator

Description:
This module calculates CVaR for options portfolios, typically
2-3x larger than VaR. It provides multiple calculation methods
(Historical, Parametric, Monte Carlo), comprehensive stress testing,
model backtesting with Kupiec test, and STAR ratio calculations.

Author: Mohamed Talib
Date: 2025-06-13
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime, timedelta

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
import logging
from numba import jit
import warnings
from scipy.stats import norm
import asyncio

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
@dataclass
class RiskMetrics:
    """Comprehensive risk metrics including VaR and CVaR."""
confidence_level: float
time_horizon: int  # days
var: float  # Value at Risk
cvar: float  # Conditional Value at Risk
cvar_var_ratio: float  # CVaR/VaR ratio
expected_shortfall: float
worst_case_loss: float
tail_observations: int
calculation_method: str
portfolio_value: float
@dataclass
class StressTestResult:
    """Results from stress testing scenarios."""
scenario_name: str
scenario_description: str
portfolio_loss: float
var_breach: bool
cvar_breach: bool
affected_positions: List[str]
hedge_recommendation: str
@dataclass
class BacktestResult:
    """VaR/CVaR model backtest results."""
period_start: datetime
period_end: datetime
var_breaches: int
expected_breaches: int
kupiec_test_stat: float
kupiec_p_value: float
model_accurate: bool
cvar_accuracy: float
class SpyderCVaRCalculator:
    """
Implements Conditional Value at Risk for options portfolios.
Features:
    - Multiple calculation methods (Historical, Parametric, Monte Carlo)
- Options-specific adjustments for fat tails
- Stress testing framework
- Model backtesting and validation
- STAR ratio calculation
"""
    def __init__(self, market_data=None, option_pricer=None):
        """Initialize CVaR calculator."""
self.market_data = market_data
self.option_pricer = option_pricer
# Standard confidence levels
self.CONFIDENCE_LEVELS = {
'regulatory': 0.99,    # 99% for regulatory
'standard': 0.95,      # 95% standard
'conservative': 0.975  # 97.5% conservative
}
# Time horizons (days)
self.TIME_HORIZONS = {
'daily': 1,
'weekly': 5,
'biweekly': 10,
'monthly': 21
}
# CVaR/VaR ratio expectations for options
self.EXPECTED_RATIOS = {
'linear': (1.2, 1.5),      # Stocks, futures
'options': (2.0, 3.0),     # Options portfolios
'complex': (2.5, 4.0)      # Complex strategies
}
# Stress test scenarios
self.STRESS_SCENARIOS = {
'market_crash': {
'spy_move': -0.15,     # 15% drop
'vix_spike': 2.5,      # VIX multiplier
'correlation': 0.95    # Correlation spike
},
'volatility_spike': {
'spy_move': -0.05,
'vix_spike': 3.0,
'correlation': 0.8
},
'flash_crash': {
'spy_move': -0.08,
'vix_spike': 4.0,
'correlation': 1.0
},
'slow_bleed': {
'spy_move': -0.20,     # Over 20 days
'vix_spike': 1.5,
'correlation': 0.6
}
}
# Model parameters
self.MODEL_PARAMS = {
'historical_days': 252,    # 1 year of data
'monte_carlo_sims': 10000,
'bootstrap_samples': 1000,
'tail_threshold': 0.10,    # Focus on 10% tail
'min_observations': 100
}
# Cache for performance
self.cache = {}
self.last_calculation = None
async def calculate_portfolio_risk(self, portfolio: List[Dict[str, Any]],
confidence: float = 0.95,
horizon: int = 1,
method: str = 'historical') -> RiskMetrics:
        """
Calculate VaR and CVaR for options portfolio.
Args:
            portfolio: List of positions with details
confidence: Confidence level (e.g., 0.95)
horizon: Time horizon in days
method: 'historical', 'parametric', or 'monte_carlo'
Returns:
            RiskMetrics with VaR, CVaR, and related metrics
"""
logger.info(f"Calculating portfolio risk - Method: {method}, "
f"Confidence: {confidence:.1%}, Horizon: {horizon} days")
# Get portfolio value
portfolio_value = sum(p['market_value'] for p in portfolio)
# Calculate returns based on method
        if method == 'historical':
            returns = await self._calculate_historical_returns(portfolio, horizon)
        elif method == 'parametric':
            returns = await self._calculate_parametric_returns(portfolio, horizon)
        elif method == 'monte_carlo':
            returns = await self._calculate_monte_carlo_returns(portfolio, horizon)
        else:
            raise ValueError(f"Unknown method: {method}")
# Calculate VaR
var = self._calculate_var(returns, confidence)
        # Calculate CVaR (Expected Shortfall)
cvar = self._calculate_cvar(returns, confidence)
        # Calculate additional metrics
expected_shortfall = cvar  # Same as CVaR
worst_case = np.min(returns)
        tail_obs = len(returns[returns <= -var])
        # Create risk metrics
metrics = RiskMetrics(
confidence_level=confidence,
time_horizon=horizon,
var=var * portfolio_value,
cvar=cvar * portfolio_value,
cvar_var_ratio=cvar / var if var != 0 else 0,
expected_shortfall=expected_shortfall * portfolio_value,
worst_case_loss=worst_case * portfolio_value,
tail_observations=tail_obs,
calculation_method=method,
portfolio_value=portfolio_value
)
# Validate CVaR/VaR ratio
self._validate_cvar_ratio(metrics)
return metrics
    async def _calculate_historical_returns(self, portfolio: List[Dict[str, Any]],
                                          horizon: int) -> np.ndarray:
        """Calculate historical returns for portfolio."""
        if not self.market_data:
            # Generate synthetic returns for demo
            returns = self._generate_synthetic_option_returns(
                n_days=self.MODEL_PARAMS['historical_days'],
n_assets=len(portfolio)
)
# Aggregate to portfolio level
weights = np.array([p['market_value'] for p in portfolio])
weights = weights / weights.sum()
portfolio_returns = returns @ weights
            # Scale to horizon
if horizon > 1:
                # Use overlapping returns for longer horizons
                portfolio_returns = self._scale_returns_to_horizon(
                    portfolio_returns, horizon
                )
return portfolio_returns
    async def _calculate_parametric_returns(self, portfolio: List[Dict[str, Any]],
                                          horizon: int) -> np.ndarray:
        """Calculate parametric returns using fitted distributions."""
        # Calculate portfolio statistics
positions_stats = []
for position in portfolio:
            if position['type'] == 'option':
                # Options have non-normal distributions
stats = await self._get_option_statistics(position)
else:
                stats = await self._get_asset_statistics(position['symbol'])
positions_stats.append(stats)
# Calculate portfolio parameters
weights = np.array([p['market_value'] for p in portfolio])
weights = weights / weights.sum()
# Portfolio mean and variance
means = np.array([s['mean'] for s in positions_stats])
stds = np.array([s['std'] for s in positions_stats])
corr_matrix = await self._get_correlation_matrix(portfolio)
portfolio_mean = np.dot(weights, means)
portfolio_var = weights @ (corr_matrix * np.outer(stds, stds)) @ weights
portfolio_std = np.sqrt(portfolio_var)
# Adjust for options' fat tails using Johnson SU distribution
if any(p['type'] == 'option' for p in portfolio):
            # Fit Johnson SU for better tail modeling
returns = self._generate_johnson_su_returns(
                portfolio_mean, portfolio_std,
skew=-0.5,  # Negative skew for options
kurt=6.0,   # Excess kurtosis
size=10000
)
else:
            # Normal distribution for linear assets
returns = np.random.normal(
                portfolio_mean, portfolio_std, 10000
)
# Scale to horizon
if horizon > 1:
            returns = returns * np.sqrt(horizon)
        return returns
    async def _calculate_monte_carlo_returns(self, portfolio: List[Dict[str, Any]],
                                           horizon: int) -> np.ndarray:
        """Calculate returns using Monte Carlo simulation."""
        n_sims = self.MODEL_PARAMS['monte_carlo_sims']
# Initialize arrays
portfolio_values = np.zeros((n_sims, horizon + 1))
portfolio_values[:, 0] = sum(p['market_value'] for p in portfolio)
# Get current market state
spot_price = 450  # Current SPY price
current_vol = 0.18  # Current implied volatility
# Simulate paths
for sim in range(n_sims):
            for t in range(1, horizon + 1):
                # Simulate market moves
daily_return = np.random.normal(0.0005, current_vol / np.sqrt(252))
                spot_price *= (1 + daily_return)
                # Simulate volatility (mean-reverting)
vol_shock = np.random.normal(0, 0.02)
current_vol = 0.18 + 0.5 * (current_vol - 0.18) + vol_shock
current_vol = max(0.05, min(0.50, current_vol))
# Reprice portfolio
portfolio_value = 0
for position in portfolio:
                    if position['type'] == 'option':
                        # Reprice option with new spot and vol
new_price = await self._reprice_option(
position, spot_price, current_vol, t
)
else:
                        # Linear asset
new_price = position['current_price'] * (1 + daily_return)
                    portfolio_value += new_price * position['quantity']
portfolio_values[sim, t] = portfolio_value
# Calculate returns
        returns = (portfolio_values[:, -1] - portfolio_values[:, 0]) / portfolio_values[:, 0]
        return returns
    def _calculate_var(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate Value at Risk."""
# VaR is the negative of the quantile
var_percentile = (1 - confidence) * 100
var = -np.percentile(returns, var_percentile)
        return var
    def _calculate_cvar(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate Conditional Value at Risk (Expected Shortfall)."""
# Get VaR threshold
var = self._calculate_var(returns, confidence)
        # CVaR is the expected value of losses exceeding VaR
tail_losses = returns[returns <= -var]
        if len(tail_losses) == 0:
            # No observations in tail, use VaR
return var
        cvar = -np.mean(tail_losses)
return cvar
    def _validate_cvar_ratio(self, metrics: RiskMetrics):
        """Validate CVaR/VaR ratio is within expected range."""
ratio = metrics.cvar_var_ratio
# Determine portfolio type
# For now, assume options portfolio
expected_min, expected_max = self.EXPECTED_RATIOS['options']
if ratio < expected_min:
            logger.warning(f"CVaR/VaR ratio {ratio:.2f} below expected "
f"range [{expected_min:.1f}, {expected_max:.1f}]")
elif ratio > expected_max:
            logger.warning(f"CVaR/VaR ratio {ratio:.2f} above expected "
f"range [{expected_min:.1f}, {expected_max:.1f}]")
else:
            logger.info(f"CVaR/VaR ratio {ratio:.2f} within expected range")
async def stress_test_portfolio(self, portfolio: List[Dict[str, Any]],
scenarios: Optional[List[str]] = None) -> List[StressTestResult]:
        """
Run stress tests on portfolio.
Args:
            portfolio: List of positions
scenarios: Specific scenarios to test (default: all)
Returns:
            List of stress test results
"""
if scenarios is None:
            scenarios = list(self.STRESS_SCENARIOS.keys())
results = []
# Get baseline risk metrics
baseline_metrics = await self.calculate_portfolio_risk(
portfolio, confidence=0.95, horizon=1
)
for scenario_name in scenarios:
            if scenario_name not in self.STRESS_SCENARIOS:
                continue
            scenario = self.STRESS_SCENARIOS[scenario_name]
logger.info(f"Running stress test: {scenario_name}")
# Apply scenario shocks
stressed_value = await self._apply_scenario_shocks(
portfolio, scenario
)
# Calculate loss
original_value = baseline_metrics.portfolio_value
portfolio_loss = original_value - stressed_value
loss_pct = portfolio_loss / original_value
# Check if breaches risk limits
var_breach = portfolio_loss > baseline_metrics.var
cvar_breach = portfolio_loss > baseline_metrics.cvar
# Identify most affected positions
affected = await self._identify_affected_positions(
portfolio, scenario
)
# Generate hedge recommendation
hedge_rec = self._generate_hedge_recommendation(
scenario_name, loss_pct, affected
)
result = StressTestResult(
scenario_name=scenario_name,
scenario_description=self._get_scenario_description(scenario_name),
portfolio_loss=portfolio_loss,
var_breach=var_breach,
cvar_breach=cvar_breach,
affected_positions=affected,
hedge_recommendation=hedge_rec
)
results.append(result)
return results
    async def _apply_scenario_shocks(self, portfolio: List[Dict[str, Any]],
scenario: Dict[str, float]) -> float:
        """Apply stress scenario to portfolio."""
stressed_value = 0
# Current market state
current_spy = 450
current_vix = 18
# Shocked market state
shocked_spy = current_spy * (1 + scenario['spy_move'])
shocked_vix = current_vix * scenario['vix_spike']
for position in portfolio:
            if position['type'] == 'option':
                # Reprice option under stressed conditions
shocked_price = await self._reprice_option_stressed(
position, shocked_spy, shocked_vix
)
else:
                # Linear asset moves with market
shocked_price = position['current_price'] * (1 + scenario['spy_move'])
stressed_value += shocked_price * position['quantity']
return stressed_value
    async def backtest_model(self, historical_data: pd.DataFrame,
portfolio_history: List[Dict],
confidence: float = 0.95) -> BacktestResult:
        """
Backtest VaR/CVaR model accuracy.
Args:
            historical_data: Historical returns data
            portfolio_history: Historical portfolio compositions
confidence: Confidence level used
Returns:
            Backtest results with breach statistics
"""
logger.info(f"Backtesting VaR/CVaR model at {confidence:.1%} confidence")
# Track breaches
var_breaches = 0
total_observations = 0
cvar_exceedances = []
# Rolling window backtest
window_size = self.MODEL_PARAMS['historical_days']
for i in range(window_size, len(historical_data)):
            # Get historical window
window_data = historical_data.iloc[i-window_size:i]
# Calculate VaR/CVaR for next period
portfolio = portfolio_history[i] if i < len(portfolio_history) else portfolio_history[-1]
metrics = await self.calculate_portfolio_risk(
portfolio, confidence=confidence, horizon=1
)
# Get actual return
            actual_return = historical_data.iloc[i]['portfolio_return']
            actual_loss = -actual_return * metrics.portfolio_value
            # Check for VaR breach
if actual_loss > metrics.var:
                var_breaches += 1
# If VaR breached, check CVaR accuracy
if actual_loss > 0:
                    cvar_exceedance = actual_loss / metrics.cvar
cvar_exceedances.append(cvar_exceedance)
total_observations += 1
# Kupiec test for VaR accuracy
expected_breaches = total_observations * (1 - confidence)
kupiec_stat, kupiec_p = self._kupiec_test(
var_breaches, total_observations, confidence
)
# CVaR accuracy (should average close to 1.0)
cvar_accuracy = np.mean(cvar_exceedances) if cvar_exceedances else 0
# Model is accurate if Kupiec test passes and CVaR is reasonable
model_accurate = (kupiec_p > 0.05 and 
0.8 <= cvar_accuracy <= 1.2)
return BacktestResult(
            period_start=historical_data.index[0],
period_end=historical_data.index[-1],
var_breaches=var_breaches,
expected_breaches=int(expected_breaches),
kupiec_test_stat=kupiec_stat,
kupiec_p_value=kupiec_p,
model_accurate=model_accurate,
cvar_accuracy=cvar_accuracy
)
    def _kupiec_test(self, actual_breaches: int, total_obs: int,
                    confidence: float) -> Tuple[float, float]:
        """Kupiec likelihood ratio test for VaR model."""
p = 1 - confidence  # Probability of breach
expected = total_obs * p
if actual_breaches == 0:
            return 0, 1.0  # Perfect, no breaches
        # Likelihood ratio statistic
lr = -2 * np.log((p ** actual_breaches * (1 - p) ** (total_obs - actual_breaches)) /
((actual_breaches / total_obs) ** actual_breaches * 
(1 - actual_breaches / total_obs) ** (total_obs - actual_breaches)))
# Chi-square test with 1 degree of freedom
p_value = 1 - stats.chi2.cdf(lr, 1)
return lr, p_value
    def calculate_star_ratio(self, returns: np.ndarray,
                           risk_free_rate: float = 0.02) -> float:
        """
Calculate STAR ratio (Stable Tail Adjusted Return).
STAR = (Expected Return - Risk Free Rate) / CVaR
More robust than Sharpe for non-normal distributions.
"""
expected_return = np.mean(returns)
        excess_return = expected_return - risk_free_rate / 252  # Daily risk-free
        # Calculate 95% CVaR
cvar = self._calculate_cvar(returns, 0.95)
        if cvar == 0:
            return 0
        star_ratio = excess_return / cvar
        # Annualize
star_ratio = star_ratio * np.sqrt(252)
return star_ratio
    def _generate_synthetic_option_returns(self, n_days: int,
                                         n_assets: int) -> np.ndarray:
        """Generate synthetic option returns with realistic characteristics."""
        returns = np.zeros((n_days, n_assets))
        for i in range(n_assets):
            # Base returns with stochastic volatility
            base_vol = 0.30  # Higher vol for options
vol = base_vol
for t in range(n_days):
                # Stochastic volatility
vol = vol + 0.1 * (base_vol - vol) + 0.05 * np.random.normal()
vol = max(0.1, min(0.6, vol))
# Fat-tailed returns using t-distribution
                df = 4  # Degrees of freedom for fat tails
daily_return = stats.t.rvs(df) * vol / np.sqrt(252)
                # Add jump component (5% chance)
if np.random.random() < 0.05:
                    jump = np.random.normal(-0.10, 0.05)  # Negative jumps
daily_return += jump
                returns[t, i] = daily_return
        return returns
    def _generate_johnson_su_returns(self, mean: float, std: float,
                                   skew: float, kurt: float,
size: int) -> np.ndarray:
        """Generate returns using Johnson SU distribution."""
        # Johnson SU parameters from moments
# Simplified approach - in practice use moment matching
gamma = skew / 2  # Shape parameter
delta = 1 / np.sqrt(np.log(1 + (kurt / 3)))  # Shape parameter
# Generate standard normal
z = np.random.normal(0, 1, size)
# Transform to Johnson SU
sinh_inv = np.arcsinh((z - gamma) / delta)
johnson_su = mean + std * np.sinh(delta * sinh_inv + gamma)
return johnson_su
    async def _get_option_statistics(self, position: Dict) -> Dict[str, float]:
        """Get statistical properties of option position."""
# Simplified for demo
# In practice, would use historical option prices
# Options have higher vol and negative skew
if position['option_type'] == 'call':
            return {
                'mean': -0.001,  # Slight negative drift (time decay)
'std': 0.50,     # High volatility
'skew': -1.0,    # Negative skew
'kurt': 4.0      # Excess kurtosis
}
else:  # put
            return {
                'mean': -0.0005,
'std': 0.45,
'skew': -1.5,    # More negative skew for puts
'kurt': 5.0
}
async def _get_correlation_matrix(self, portfolio: List[Dict]) -> np.ndarray:
        """Get correlation matrix for portfolio positions."""
n = len(portfolio)
corr_matrix = np.eye(n)
# Simplified correlation structure
for i in range(n):
            for j in range(i+1, n):
                # Same underlying = high correlation
if (portfolio[i].get('underlying') == portfolio[j].get('underlying')):
                    corr = 0.8
else:
                    corr = 0.3
corr_matrix[i, j] = corr
corr_matrix[j, i] = corr
return corr_matrix
    async def _reprice_option(self, position: Dict, spot: float,
vol: float, days_passed: int) -> float:
        """Reprice option given new market conditions."""
if self.option_pricer:
            return await self.option_pricer.price_option(
                spot=spot,
strike=position['strike'],
time_to_expiry=position['days_to_expiry'] - days_passed,
volatility=vol,
option_type=position['option_type']
)
# Simplified Black-Scholes for demo
S = spot
K = position['strike']
T = max(0, (position['days_to_expiry'] - days_passed) / 365)
r = 0.05
sigma = vol
if T == 0:
            # At expiration
if position['option_type'] == 'call':
                return max(S - K, 0)
            else:
                return max(K - S, 0)
        # Black-Scholes
d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
d2 = d1 - sigma*np.sqrt(T)
if position['option_type'] == 'call':
            price = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
else:
            price = K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
return price
    async def _reprice_option_stressed(self, position: Dict,
shocked_spy: float,
shocked_vix: float) -> float:
        """Reprice option under stressed conditions."""
# Convert VIX to volatility
shocked_vol = shocked_vix / 100
return await self._reprice_option(
            position, shocked_spy, shocked_vol, 0
)
    def _scale_returns_to_horizon(self, daily_returns: np.ndarray,
                                 horizon: int) -> np.ndarray:
        """Scale returns to multi-day horizon."""
        # Use overlapping returns
        horizon_returns = []
        for i in range(len(daily_returns) - horizon + 1):
            # Compound returns over horizon
            horizon_return = np.prod(1 + daily_returns[i:i+horizon]) - 1
            horizon_returns.append(horizon_return)
        return np.array(horizon_returns)
    async def _identify_affected_positions(self, portfolio: List[Dict],
scenario: Dict) -> List[str]:
        """Identify positions most affected by scenario."""
position_impacts = []
for position in portfolio:
            # Calculate position sensitivity
if position['type'] == 'option':
                # Options highly sensitive to vol spikes
impact = abs(position.get('vega', 0)) * (scenario['vix_spike'] - 1)
impact += abs(position.get('delta', 0)) * abs(scenario['spy_move'])
else:
                impact = abs(scenario['spy_move'])
position_impacts.append({
'id': position.get('id', 'unknown'),
'impact': impact
})
# Sort by impact
position_impacts.sort(key=lambda x: x['impact'], reverse=True)
# Return top affected
return [p['id'] for p in position_impacts[:5]]
    def _generate_hedge_recommendation(self, scenario: str,
                                     loss_pct: float,
affected: List[str]) -> str:
        """Generate hedging recommendation based on scenario."""
if 'crash' in scenario:
            if loss_pct > 0.10:
                return "URGENT: Add put protection or reduce position size"
            else:
                return "Consider out-of-money put spreads for tail protection"
        elif 'volatility' in scenario:
            return "Reduce vega exposure through calendar spreads or VIX puts"
        elif 'bleed' in scenario:
            return "Implement systematic theta capture strategies"
        return "Review position sizing and consider diversification"
    def _get_scenario_description(self, scenario_name: str) -> str:
        """Get human-readable scenario description."""
descriptions = {
'market_crash': "Sudden 15% market decline with volatility spike",
'volatility_spike': "Volatility explosion without major price move",
'flash_crash': "Rapid 8% intraday decline and recovery",
'slow_bleed': "Gradual 20% decline over 20 trading days"
}
return descriptions.get(scenario_name, "Custom stress scenario")
    async def _get_option_returns(self, position: Dict, days: int) -> np.ndarray:
        """Get historical returns for option position."""
        # Simplified - would fetch actual option price history
return self._generate_synthetic_option_returns(days, 1).flatten()
    async def _get_stock_returns(self, symbol: str, days: int) -> np.ndarray:
        """Get historical returns for stock."""
        # Simplified - would fetch actual price history
returns = np.random.normal(0.0005, 0.015, days)
        return returns
    async def _get_asset_statistics(self, symbol: str) -> Dict[str, float]:
        """Get statistical properties of asset."""
# Simplified for demo
return {
            'mean': 0.0005,  # Daily return
            'std': 0.015,    # Daily volatility
'skew': -0.3,    # Slight negative skew
'kurt': 1.0      # Slight excess kurtosis
}
    def get_risk_dashboard(self, metrics: RiskMetrics,
                          stress_results: List[StressTestResult]) -> Dict[str, Any]:
        """Generate comprehensive risk dashboard."""
dashboard = {
'current_risk': {
'var_95': metrics.var,
'cvar_95': metrics.cvar,
'cvar_var_ratio': metrics.cvar_var_ratio,
'worst_case': metrics.worst_case_loss,
'risk_utilization': metrics.var / (metrics.portfolio_value * 0.05)  # vs 5% limit
},
'stress_tests': {
'total_scenarios': len(stress_results),
'var_breaches': sum(1 for r in stress_results if r.var_breach),
'cvar_breaches': sum(1 for r in stress_results if r.cvar_breach),
'worst_scenario': max(stress_results, key=lambda x: x.portfolio_loss).scenario_name
if stress_results else None,
                'max_loss': max(r.portfolio_loss for r in stress_results) if stress_results else 0
},
'recommendations': self._generate_risk_recommendations(metrics, stress_results)
}
return dashboard
    def _generate_risk_recommendations(self, metrics: RiskMetrics,
                                     stress_results: List[StressTestResult]) -> List[str]:
        """Generate risk management recommendations."""
recommendations = []
# Check CVaR/VaR ratio
if metrics.cvar_var_ratio > 3.0:
            recommendations.append("High tail risk detected - consider tail hedges")
# Check absolute risk level
if metrics.var > metrics.portfolio_value * 0.05:
            recommendations.append("VaR exceeds 5% of portfolio - reduce position sizes")
# Check stress test results
breach_count = sum(1 for r in stress_results if r.cvar_breach)
if breach_count > len(stress_results) / 2:
            recommendations.append("Portfolio vulnerable to multiple scenarios - increase hedging")
if not recommendations:
            recommendations.append("Risk levels within acceptable parameters")
return recommendations
async def main():
    """Example usage of CVaR calculator."""
# Initialize calculator
cvar_calc = SpyderCVaRCalculator()
# Create sample portfolio
portfolio = [
{
'id': 'SPY_CALL_1',
'type': 'option',
'option_type': 'call',
'underlying': 'SPY',
'strike': 455,
'days_to_expiry': 30,
'quantity': 10,
'current_price': 3.50,
'market_value': 3500,
'delta': 0.45,
'gamma': 0.02,
'vega': 0.15,
'theta': -0.08
},
{
'id': 'SPY_PUT_1',
'type': 'option',
'option_type': 'put',
'underlying': 'SPY',
'strike': 445,
'days_to_expiry': 30,
'quantity': -5,  # Short
'current_price': 3.20,
'market_value': -1600,
'delta': -0.40,
'gamma': 0.02,
'vega': 0.15,
'theta': 0.08
},
{
'id': 'SPY_SHARES',
'type': 'stock',
'symbol': 'SPY',
'quantity': 100,
'current_price': 450,
'market_value': 45000
}
]
print("=== Portfolio Risk Analysis ===")
print(f"Portfolio Value: ${sum(p['market_value'] for p in portfolio):,.2f}")
# Calculate risk metrics using different methods
for method in ['historical', 'parametric', 'monte_carlo']:
        print(f"\n--- {method.title()} Method ---")
metrics = await cvar_calc.calculate_portfolio_risk(
portfolio,
confidence=0.95,
horizon=1,
method=method
)
print(f"95% VaR (1-day): ${metrics.var:,.2f}")
print(f"95% CVaR (1-day): ${metrics.cvar:,.2f}")
print(f"CVaR/VaR Ratio: {metrics.cvar_var_ratio:.2f}")
print(f"Worst Case: ${metrics.worst_case_loss:,.2f}")
# Run stress tests
print("\n=== Stress Testing ===")
stress_results = await cvar_calc.stress_test_portfolio(portfolio)
for result in stress_results:
        print(f"\nScenario: {result.scenario_name}")
print(f"Description: {result.scenario_description}")
print(f"Portfolio Loss: ${result.portfolio_loss:,.2f}")
print(f"VaR Breach: {'Yes' if result.var_breach else 'No'}")
print(f"CVaR Breach: {'Yes' if result.cvar_breach else 'No'}")
print(f"Recommendation: {result.hedge_recommendation}")
# Generate risk dashboard
print("\n=== Risk Dashboard ===")
dashboard = cvar_calc.get_risk_dashboard(metrics, stress_results)
print("\nCurrent Risk Metrics:")
for key, value in dashboard['current_risk'].items():
        if isinstance(value, float):
            if key.startswith('var') or key.startswith('cvar'):
                print(f"  {key}: ${value:,.2f}")
else:
                print(f"  {key}: {value:.2f}")
print("\nStress Test Summary:")
for key, value in dashboard['stress_tests'].items():
        print(f"  {key}: {value}")
print("\nRecommendations:")
for rec in dashboard['recommendations']:
        print(f"  - {rec}")
# Calculate STAR ratio
print("\n=== Performance Metrics ===")
# Generate sample returns for STAR calculation
    returns = np.random.normal(0.001, 0.02, 252)  # Daily returns
    star_ratio = cvar_calc.calculate_star_ratio(returns)
    print(f"STAR Ratio: {star_ratio:.2f}")
# Backtest example (simplified)
print("\n=== Model Backtest ===")
# Create dummy historical data
dates = pd.date_range(end=datetime.now(), periods=500, freq='D')
historical_data = pd.DataFrame({
'portfolio_return': np.random.normal(0.0005, 0.02, 500)
    }, index=dates)
backtest = await cvar_calc.backtest_model(
historical_data,
[portfolio] * 500,  # Same portfolio throughout
confidence=0.95
)
print(f"Period: {backtest.period_start.date()} to {backtest.period_end.date()}")
print(f"VaR Breaches: {backtest.var_breaches} (Expected: {backtest.expected_breaches})")
print(f"Kupiec Test p-value: {backtest.kupiec_p_value:.3f}")
print(f"Model Accurate: {'Yes' if backtest.model_accurate else 'No'}")
print(f"CVaR Accuracy: {backtest.cvar_accuracy:.2f}")
if __name__ == "__main__":
    asyncio.run(main())
# Real implementation would fetch historical data
all_returns = []
        for position in portfolio:
            # Get historical prices for position
if position['type'] == 'option':
                returns = await self._get_option_returns(
                    position, 
self.MODEL_PARAMS['historical_days']
)
else:
                returns = await self._get_stock_returns(
                    position['symbol'],
self.MODEL_PARAMS['historical_days']
)
all_returns.append(returns)
        # Combine returns based on weights
        returns_matrix = np.column_stack(all_returns)
        weights = np.array([p['market_value'] for p in portfolio])
weights = weights / weights.sum()
portfolio_returns = returns_matrix @ weights
        return portfolio_returns
