#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderK_Reports
Module: SpyderK06_PortfolioAnalytics.py
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
from datetime import datetime, timedelta, date, timezone
from typing import Any
from dataclasses import dataclass, asdict
from enum import Enum
import json
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import skew, kurtosis
from scipy.cluster import hierarchy

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import get_data_access_layer
from Spyder.SpyderE_Risk.SpyderE06_RiskMetrics import RiskMetrics
from Spyder.SpyderN_OptionsAnalytics.SpyderN03_GreeksCalculator import GreeksCalculator

RISK_CONCENTRATION_THRESHOLD = 0.15  # 15% of portfolio risk
CORRELATION_HIGH_THRESHOLD = 0.7
CORRELATION_EXTREME_THRESHOLD = 0.9

# Portfolio limits
MAX_SINGLE_POSITION_WEIGHT = 0.25  # 25% max weight
MIN_POSITION_COUNT = 5  # Minimum positions for diversification
OPTIMAL_POSITION_COUNT = 15  # Optimal number of positions

# Stress test scenarios
STRESS_SCENARIOS = {
    'market_crash': {
        'name': 'Market Crash (-20%)',
        'spy_move': -0.20,
        'vix_spike': 2.0,
        'correlation_increase': 0.3
    },
    'flash_crash': {
        'name': 'Flash Crash (-10%)',
        'spy_move': -0.10,
        'vix_spike': 1.5,
        'correlation_increase': 0.2
    },
    'gradual_decline': {
        'name': 'Gradual Decline (-5%)',
        'spy_move': -0.05,
        'vix_spike': 1.2,
        'correlation_increase': 0.1
    },
    'volatility_spike': {
        'name': 'Volatility Spike',
        'spy_move': 0.0,
        'vix_spike': 1.8,
        'correlation_increase': 0.15
    },
    'rally': {
        'name': 'Market Rally (+10%)',
        'spy_move': 0.10,
        'vix_spike': 0.7,
        'correlation_increase': -0.1
    }
}

# Factor models
RISK_FACTORS = ['delta', 'gamma', 'vega', 'theta', 'rho']

# ==============================================================================
# ENUMS
# ==============================================================================
class PortfolioMetric(Enum):
    """Portfolio performance metrics"""
    TOTAL_VALUE = "total_value"
    DAILY_PNL = "daily_pnl"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    VAR_95 = "var_95"
    CVAR_95 = "cvar_95"
    BETA = "beta"
    ALPHA = "alpha"
    INFORMATION_RATIO = "information_ratio"

class RiskAttribution(Enum):
    """Risk attribution categories"""
    MARKET_RISK = "market_risk"
    SPECIFIC_RISK = "specific_risk"
    VOLATILITY_RISK = "volatility_risk"
    TIME_DECAY_RISK = "time_decay_risk"
    CORRELATION_RISK = "correlation_risk"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PortfolioPosition:
    """Single position in portfolio"""
    symbol: str
    position_type: str  # 'option' or 'stock'
    quantity: int
    entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    weight: float
    option_details: dict[str, Any] | None = None
    greeks: dict[str, float] | None = None

@dataclass
class CorrelationAnalysis:
    """Correlation analysis results"""
    correlation_matrix: pd.DataFrame
    average_correlation: float
    max_correlation_pair: tuple[str, str, float]
    clustering_groups: list[list[str]]
    eigenvalues: np.ndarray
    concentration_ratio: float  # First eigenvalue / sum of eigenvalues

@dataclass
class RiskAttributionResult:
    """Risk attribution analysis results"""
    total_risk: float
    risk_contributions: dict[str, float]
    risk_percentages: dict[str, float]
    marginal_contributions: dict[str, float]
    concentration_metrics: dict[str, float]

@dataclass
class FactorExposure:
    """Factor exposure analysis"""
    factor_loadings: dict[str, float]
    factor_contributions: dict[str, float]
    r_squared: float
    specific_risk: float
    systematic_risk: float

@dataclass
class StressTestResult:
    """Stress test scenario result"""
    scenario_name: str
    portfolio_impact: float
    position_impacts: dict[str, float]
    worst_positions: list[tuple[str, float]]
    var_impact: float
    margin_requirement_change: float

@dataclass
class OptimizationSuggestion:
    """Portfolio optimization suggestion"""
    suggestion_type: str
    description: str
    expected_improvement: dict[str, float]
    positions_affected: list[str]
    implementation_steps: list[str]
    priority: int  # 1-5, 1 being highest

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class PortfolioAnalytics:
    """
    Portfolio-level analytics and optimization engine.

    This class provides comprehensive portfolio analysis including correlation
    matrices, risk attribution, factor exposures, stress testing, and optimization
    suggestions to improve risk-adjusted returns.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        dal: Data access layer for portfolio data
        risk_metrics: Risk metrics calculator
        greeks_calc: Greeks calculator for options

    Example:
        >>> analytics = PortfolioAnalytics()
        >>> analysis = analytics.analyze_portfolio()
        >>> analytics.generate_portfolio_report(analysis, 'portfolio_report.pdf')
    """

    def __init__(self):
        """Initialize the portfolio analytics module."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.dal = get_data_access_layer()
        self.risk_metrics = RiskMetrics()
        self.greeks_calc = GreeksCalculator()

        # Caches
        self.position_cache: dict[str, PortfolioPosition] = {}
        self.correlation_cache: CorrelationAnalysis | None = None
        self.factor_cache: dict[str, FactorExposure] = {}

        self.logger.info("PortfolioAnalytics initialized")

    # ==========================================================================
    # CORE ANALYSIS METHODS
    # ==========================================================================
    def get_portfolio_positions(self) -> list[PortfolioPosition]:
        """
        Get current portfolio positions with full details.

        Returns:
            List of PortfolioPosition objects
        """
        try:
            # Get positions from DAL
            positions_data = self.dal.get_portfolio_positions()

            positions = []
            total_value = sum(p['market_value'] for p in positions_data)

            for pos_data in positions_data:
                # Calculate position weight
                weight = pos_data['market_value'] / total_value if total_value > 0 else 0

                # Get Greeks for options
                greeks = None
                if pos_data['position_type'] == 'option':
                    greeks = self._calculate_position_greeks(pos_data)

                position = PortfolioPosition(
                    symbol=pos_data['symbol'],
                    position_type=pos_data['position_type'],
                    quantity=pos_data['quantity'],
                    entry_price=pos_data['entry_price'],
                    current_price=pos_data['current_price'],
                    market_value=pos_data['market_value'],
                    unrealized_pnl=pos_data['unrealized_pnl'],
                    weight=weight,
                    option_details=pos_data.get('option_details'),
                    greeks=greeks
                )

                positions.append(position)
                self.position_cache[position.symbol] = position

            return positions

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'get_portfolio_positions'
            })
            return []

    def calculate_correlation_matrix(self, lookback_days: int = 60) -> CorrelationAnalysis:
        """
        Calculate correlation matrix for portfolio positions.

        Args:
            lookback_days: Number of days for correlation calculation

        Returns:
            CorrelationAnalysis object with results
        """
        try:
            positions = self.get_portfolio_positions()

            if len(positions) < 2:
                self.logger.warning("Insufficient positions for correlation analysis")
                return self._empty_correlation_analysis()

            # Get price history for all positions
            symbols = [p.symbol for p in positions]
            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_days)

            price_data = self.dal.get_price_history(symbols, start_date, end_date)

            # Calculate returns
            returns_df = pd.DataFrame()
            for symbol in symbols:
                if symbol in price_data:
                    prices = pd.Series(price_data[symbol])
                    returns = prices.pct_change().dropna()
                    returns_df[symbol] = returns

            # Calculate correlation matrix
            corr_matrix = returns_df.corr()

            # Find highest correlation pair
            corr_values = corr_matrix.values
            np.fill_diagonal(corr_values, 0)  # Ignore diagonal
            max_corr_idx = np.unravel_index(np.argmax(np.abs(corr_values)), corr_values.shape)
            max_corr_pair = (
                corr_matrix.index[max_corr_idx[0]],
                corr_matrix.index[max_corr_idx[1]],
                corr_values[max_corr_idx[0], max_corr_idx[1]]
            )

            # Hierarchical clustering
            linkage = hierarchy.linkage(
                hierarchy.distance.squareform(1 - corr_matrix),
                method='average'
            )
            clusters = hierarchy.fcluster(linkage, 0.3, criterion='distance')

            # Group positions by cluster
            clustering_groups = defaultdict(list)
            for idx, cluster in enumerate(clusters):
                clustering_groups[cluster].append(symbols[idx])
            clustering_groups = list(clustering_groups.values())

            # Calculate eigenvalues for concentration
            eigenvalues = np.linalg.eigvals(corr_matrix)
            eigenvalues = np.sort(eigenvalues)[::-1]
            concentration_ratio = eigenvalues[0] / np.sum(eigenvalues)

            analysis = CorrelationAnalysis(
                correlation_matrix=corr_matrix,
                average_correlation=corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean(),  # noqa: E501
                max_correlation_pair=max_corr_pair,
                clustering_groups=clustering_groups,
                eigenvalues=eigenvalues,
                concentration_ratio=concentration_ratio
            )

            self.correlation_cache = analysis
            return analysis

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'calculate_correlation_matrix',
                'lookback_days': lookback_days
            })
            return self._empty_correlation_analysis()

    def calculate_risk_attribution(self) -> RiskAttributionResult:
        """
        Calculate risk attribution across portfolio positions.

        Returns:
            RiskAttributionResult with detailed risk breakdown
        """
        try:
            positions = self.get_portfolio_positions()

            if not positions:
                return self._empty_risk_attribution()

            # Get portfolio returns
            portfolio_returns = self._get_portfolio_returns(30)
            portfolio_std = portfolio_returns.std() * np.sqrt(252)  # Annualized

            # Calculate individual position risks
            position_risks = {}
            position_weights = {}

            for position in positions:
                pos_returns = self._get_position_returns(position.symbol, 30)
                pos_risk = pos_returns.std() * np.sqrt(252)
                position_risks[position.symbol] = pos_risk
                position_weights[position.symbol] = position.weight

            # Calculate marginal contributions to risk
            marginal_contributions = {}
            total_marginal = 0

            for position in positions:
                # Marginal VaR contribution
                marginal_var = self._calculate_marginal_var(position.symbol)
                marginal_contributions[position.symbol] = marginal_var
                total_marginal += abs(marginal_var)

            # Normalize to get risk contributions
            risk_contributions = {}
            risk_percentages = {}

            for symbol, marginal in marginal_contributions.items():
                contribution = abs(marginal) / total_marginal if total_marginal > 0 else 0
                risk_contributions[symbol] = contribution * portfolio_std
                risk_percentages[symbol] = contribution

            # Calculate concentration metrics
            sorted_contributions = sorted(risk_percentages.values(), reverse=True)
            concentration_metrics = {
                'top_1_concentration': sorted_contributions[0] if sorted_contributions else 0,
                'top_3_concentration': sum(sorted_contributions[:3]) if len(sorted_contributions) >= 3 else sum(sorted_contributions),  # noqa: E501
                'top_5_concentration': sum(sorted_contributions[:5]) if len(sorted_contributions) >= 5 else sum(sorted_contributions),  # noqa: E501
                'herfindahl_index': sum(c**2 for c in risk_percentages.values())
            }

            return RiskAttributionResult(
                total_risk=portfolio_std,
                risk_contributions=risk_contributions,
                risk_percentages=risk_percentages,
                marginal_contributions=marginal_contributions,
                concentration_metrics=concentration_metrics
            )

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'calculate_risk_attribution'
            })
            return self._empty_risk_attribution()

    def analyze_factor_exposure(self) -> dict[str, FactorExposure]:
        """
        Analyze portfolio exposure to risk factors.

        Returns:
            Dictionary mapping factor names to exposure analysis
        """
        try:
            positions = self.get_portfolio_positions()

            # Aggregate Greeks across portfolio
            portfolio_greeks = defaultdict(float)
            portfolio_value = sum(p.market_value for p in positions)

            for position in positions:
                if position.greeks:
                    for greek, value in position.greeks.items():
                        # Weight by position size
                        weighted_greek = value * position.market_value / portfolio_value
                        portfolio_greeks[greek] += weighted_greek

            # Analyze each factor
            factor_exposures = {}

            # Delta exposure (market direction)
            delta_exposure = FactorExposure(
                factor_loadings={'SPY': portfolio_greeks.get('delta', 0)},
                factor_contributions={'directional_risk': abs(portfolio_greeks.get('delta', 0)) * 0.01},  # 1% move  # noqa: E501
                r_squared=0.0,  # Would need regression analysis
                specific_risk=0.0,
                systematic_risk=abs(portfolio_greeks.get('delta', 0)) * 0.15  # Assume 15% annual vol  # noqa: E501
            )
            factor_exposures['delta'] = delta_exposure

            # Gamma exposure (convexity)
            gamma_exposure = FactorExposure(
                factor_loadings={'SPY_squared': portfolio_greeks.get('gamma', 0)},
                factor_contributions={'convexity_risk': abs(portfolio_greeks.get('gamma', 0)) * 0.0001},  # 1% move squared  # noqa: E501
                r_squared=0.0,
                specific_risk=0.0,
                systematic_risk=abs(portfolio_greeks.get('gamma', 0)) * 0.01
            )
            factor_exposures['gamma'] = gamma_exposure

            # Vega exposure (volatility)
            vega_exposure = FactorExposure(
                factor_loadings={'VIX': portfolio_greeks.get('vega', 0)},
                factor_contributions={'volatility_risk': abs(portfolio_greeks.get('vega', 0)) * 0.01},  # 1 vol point  # noqa: E501
                r_squared=0.0,
                specific_risk=0.0,
                systematic_risk=abs(portfolio_greeks.get('vega', 0)) * 0.05
            )
            factor_exposures['vega'] = vega_exposure

            # Theta exposure (time decay)
            theta_exposure = FactorExposure(
                factor_loadings={'time': portfolio_greeks.get('theta', 0)},
                factor_contributions={'time_decay': portfolio_greeks.get('theta', 0)},  # Daily decay  # noqa: E501
                r_squared=1.0,  # Time decay is deterministic
                specific_risk=0.0,
                systematic_risk=0.0
            )
            factor_exposures['theta'] = theta_exposure

            # Cache results
            self.factor_cache = factor_exposures

            return factor_exposures

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'analyze_factor_exposure'
            })
            return {}

    def run_stress_tests(self) -> list[StressTestResult]:
        """
        Run stress test scenarios on portfolio.

        Returns:
            List of StressTestResult objects for each scenario
        """
        try:
            positions = self.get_portfolio_positions()
            results = []

            for _scenario_key, scenario in STRESS_SCENARIOS.items():
                # Calculate impact on each position
                position_impacts = {}
                total_impact = 0

                for position in positions:
                    impact = self._calculate_position_stress_impact(position, scenario)
                    position_impacts[position.symbol] = impact
                    total_impact += impact * position.weight

                # Find worst affected positions
                sorted_impacts = sorted(
                    position_impacts.items(),
                    key=lambda x: x[1]
                )
                worst_positions = sorted_impacts[:5]  # Top 5 worst

                # Calculate VaR impact
                var_normal = self._calculate_portfolio_var()
                var_stressed = var_normal * (1 + scenario['vix_spike'] * 0.5)
                var_impact = var_stressed - var_normal

                # Estimate margin requirement change
                margin_change = total_impact * 0.3  # Rough estimate

                result = StressTestResult(
                    scenario_name=scenario['name'],
                    portfolio_impact=total_impact,
                    position_impacts=position_impacts,
                    worst_positions=worst_positions,
                    var_impact=var_impact,
                    margin_requirement_change=margin_change
                )

                results.append(result)

            return results

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'run_stress_tests'
            })
            return []

    def generate_optimization_suggestions(self) -> list[OptimizationSuggestion]:
        """
        Generate portfolio optimization suggestions.

        Returns:
            List of OptimizationSuggestion objects
        """
        try:
            suggestions = []

            # Get current analytics
            positions = self.get_portfolio_positions()
            correlation = self.calculate_correlation_matrix()
            self.calculate_risk_attribution()
            factor_exposure = self.analyze_factor_exposure()

            # 1. Check position concentration
            concentrated_positions = [
                p for p in positions
                if p.weight > MAX_SINGLE_POSITION_WEIGHT
            ]

            if concentrated_positions:
                suggestion = OptimizationSuggestion(
                    suggestion_type="Reduce Concentration",
                    description=f"Found {len(concentrated_positions)} positions exceeding {MAX_SINGLE_POSITION_WEIGHT*100}% weight limit",  # noqa: E501
                    expected_improvement={
                        'concentration_risk': -0.15,
                        'portfolio_volatility': -0.05
                    },
                    positions_affected=[p.symbol for p in concentrated_positions],
                    implementation_steps=[
                        "Identify positions with weight > 25%",
                        "Gradually reduce position sizes",
                        "Reallocate to other strategies",
                        "Monitor impact on P&L"
                    ],
                    priority=1
                )
                suggestions.append(suggestion)

            # 2. Check correlation clusters
            if correlation.max_correlation_pair[2] > CORRELATION_EXTREME_THRESHOLD:
                suggestion = OptimizationSuggestion(
                    suggestion_type="Reduce Correlation",
                    description=f"Extreme correlation ({correlation.max_correlation_pair[2]:.2f}) between {correlation.max_correlation_pair[0]} and {correlation.max_correlation_pair[1]}",  # noqa: E501
                    expected_improvement={
                        'correlation_risk': -0.20,
                        'diversification_ratio': 0.10
                    },
                    positions_affected=list(correlation.max_correlation_pair[:2]),
                    implementation_steps=[
                        "Consider closing one of the highly correlated positions",
                        "Replace with uncorrelated strategy",
                        "Use different strike/expiration combinations",
                        "Add hedging positions"
                    ],
                    priority=2
                )
                suggestions.append(suggestion)

            # 3. Check diversification
            if len(positions) < MIN_POSITION_COUNT:
                suggestion = OptimizationSuggestion(
                    suggestion_type="Increase Diversification",
                    description=f"Portfolio has only {len(positions)} positions, below minimum of {MIN_POSITION_COUNT}",  # noqa: E501
                    expected_improvement={
                        'diversification_ratio': 0.25,
                        'specific_risk': -0.10
                    },
                    positions_affected=[],
                    implementation_steps=[
                        "Add 2-3 new uncorrelated strategies",
                        "Consider different option structures",
                        "Diversify across expiration dates",
                        "Monitor correlation impact"
                    ],
                    priority=1
                )
                suggestions.append(suggestion)

            # 4. Check Greek exposures
            if 'delta' in factor_exposure:
                delta_exposure = factor_exposure['delta'].factor_loadings.get('SPY', 0)
                if abs(delta_exposure) > 0.5:
                    suggestion = OptimizationSuggestion(
                        suggestion_type="Hedge Delta Exposure",
                        description=f"High directional exposure (Delta: {delta_exposure:.2f})",
                        expected_improvement={
                            'directional_risk': -0.30,
                            'portfolio_stability': 0.15
                        },
                        positions_affected=[],
                        implementation_steps=[
                            "Add delta-neutral spreads",
                            "Consider protective puts/calls",
                            "Implement dynamic hedging",
                            "Set delta limits"
                        ],
                        priority=2
                    )
                    suggestions.append(suggestion)

            # 5. Check Theta income
            if 'theta' in factor_exposure:
                theta_income = factor_exposure['theta'].factor_loadings.get('time', 0)
                if theta_income < 0:  # Paying theta
                    suggestion = OptimizationSuggestion(
                        suggestion_type="Optimize Theta Income",
                        description=f"Portfolio is paying time decay (Theta: ${theta_income:.2f}/day)",  # noqa: E501
                        expected_improvement={
                            'income_generation': 0.20,
                            'theta_capture': abs(theta_income) * 252
                        },
                        positions_affected=[],
                        implementation_steps=[
                            "Shift to net credit strategies",
                            "Sell premium in high IV environment",
                            "Reduce long option exposure",
                            "Monitor theta/gamma ratio"
                        ],
                        priority=3
                    )
                    suggestions.append(suggestion)

            # Sort by priority
            suggestions.sort(key=lambda x: x.priority)

            return suggestions

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_optimization_suggestions'
            })
            return []

    # ==========================================================================
    # REPORTING METHODS
    # ==========================================================================
    def generate_portfolio_report(self, output_path: str, format: str = 'html') -> bool:
        """
        Generate comprehensive portfolio analytics report.

        Args:
            output_path: Path for output file
            format: Output format ('html', 'pdf', 'json')

        Returns:
            True if successful, False otherwise
        """
        try:
            # Gather all analytics
            positions = self.get_portfolio_positions()
            correlation = self.calculate_correlation_matrix()
            risk_attribution = self.calculate_risk_attribution()
            factor_exposure = self.analyze_factor_exposure()
            stress_tests = self.run_stress_tests()
            suggestions = self.generate_optimization_suggestions()

            # Calculate portfolio metrics
            metrics = self._calculate_portfolio_metrics()

            # Generate charts
            charts = self._generate_portfolio_charts(
                positions, correlation, risk_attribution, stress_tests
            )

            # Compile report data
            report_data = {
                'report_date': datetime.now(timezone.utc).isoformat(),
                'portfolio_summary': {
                    'total_value': sum(p.market_value for p in positions),
                    'position_count': len(positions),
                    'unrealized_pnl': sum(p.unrealized_pnl for p in positions),
                    'metrics': metrics
                },
                'positions': [asdict(p) for p in positions],
                'correlation_analysis': {
                    'average_correlation': correlation.average_correlation,
                    'max_correlation': correlation.max_correlation_pair,
                    'concentration_ratio': correlation.concentration_ratio,
                    'correlation_matrix': correlation.correlation_matrix.to_dict()
                },
                'risk_attribution': asdict(risk_attribution),
                'factor_exposure': {k: asdict(v) for k, v in factor_exposure.items()},
                'stress_tests': [asdict(st) for st in stress_tests],
                'optimization_suggestions': [asdict(s) for s in suggestions],
                'charts': charts
            }

            # Export report
            if format == 'html':
                return self._export_html_portfolio_report(report_data, output_path)
            elif format == 'pdf':
                return self._export_pdf_portfolio_report(report_data, output_path)
            elif format == 'json':
                return self._export_json_portfolio_report(report_data, output_path)
            else:
                self.logger.error("Unsupported format: %s", format)
                return False

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_portfolio_report',
                'output_path': output_path,
                'format': format
            })
            return False

    # ==========================================================================
    # PRIVATE HELPER METHODS
    # ==========================================================================
    def _calculate_position_greeks(self, position_data: dict[str, Any]) -> dict[str, float]:
        """Calculate Greeks for an option position."""
        try:
            if position_data['position_type'] != 'option':
                return {}

            option_details = position_data.get('option_details', {})

            # Use Greeks calculator
            greeks = self.greeks_calc.calculate_greeks(
                underlying_price=option_details.get('underlying_price', 500),
                strike=option_details.get('strike', 500),
                time_to_expiry=option_details.get('days_to_expiry', 30) / 365,
                volatility=option_details.get('implied_volatility', 0.15),
                risk_free_rate=0.05,
                option_type=option_details.get('option_type', 'call')
            )

            # Scale by position size
            scaled_greeks = {}
            for greek, value in greeks.items():
                scaled_greeks[greek] = value * position_data['quantity'] * 100  # Options are 100 shares  # noqa: E501

            return scaled_greeks

        except Exception:
            return {}

    def _get_portfolio_returns(self, lookback_days: int) -> pd.Series:
        """Get historical portfolio returns."""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_days)

            # Get portfolio value history
            portfolio_values = self.dal.get_portfolio_value_history(start_date, end_date)

            if not portfolio_values:
                return pd.Series()

            # Convert to Series and calculate returns
            values_series = pd.Series(portfolio_values)
            returns = values_series.pct_change().dropna()

            return returns

        except Exception:
            return pd.Series()

    def _get_position_returns(self, symbol: str, lookback_days: int) -> pd.Series:
        """Get historical returns for a position."""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_days)

            # Get price history
            price_data = self.dal.get_price_history([symbol], start_date, end_date)

            if symbol not in price_data:
                return pd.Series()

            prices = pd.Series(price_data[symbol])
            returns = prices.pct_change().dropna()

            return returns

        except Exception:
            return pd.Series()

    def _calculate_marginal_var(self, symbol: str, confidence: float = 0.95) -> float:
        """Calculate marginal VaR contribution of a position."""
        try:
            # Get portfolio returns with and without the position
            portfolio_returns = self._get_portfolio_returns(30)

            # This is a simplified calculation
            # In practice, would need to recalculate portfolio without position
            position = self.position_cache.get(symbol)
            if not position:
                return 0.0

            # Approximate marginal VaR
            portfolio_var = np.percentile(portfolio_returns, (1 - confidence) * 100)
            marginal_var = portfolio_var * position.weight

            return marginal_var

        except Exception:
            return 0.0

    def _calculate_portfolio_var(self, confidence: float = 0.95) -> float:
        """Calculate portfolio Value at Risk."""
        try:
            returns = self._get_portfolio_returns(30)

            if returns.empty:
                return 0.0

            # Calculate VaR
            var = np.percentile(returns, (1 - confidence) * 100)

            # Scale to portfolio value
            portfolio_value = sum(p.market_value for p in self.get_portfolio_positions())
            var_dollars = abs(var) * portfolio_value

            return var_dollars

        except Exception:
            return 0.0

    def _calculate_position_stress_impact(self, position: PortfolioPosition,
                                        scenario: dict[str, Any]) -> float:
        """Calculate impact of stress scenario on a position."""
        try:
            impact = 0.0

            # Market move impact
            if position.greeks and 'delta' in position.greeks:
                delta_impact = position.greeks['delta'] * scenario['spy_move']
                impact += delta_impact

            # Volatility impact
            if position.greeks and 'vega' in position.greeks:
                vega_impact = position.greeks['vega'] * (scenario['vix_spike'] - 1) * 10  # 10 vol points  # noqa: E501
                impact += vega_impact

            # Gamma impact (second order)
            if position.greeks and 'gamma' in position.greeks:
                gamma_impact = 0.5 * position.greeks['gamma'] * (scenario['spy_move'] ** 2)
                impact += gamma_impact

            # Express as percentage of position value
            impact_pct = impact / position.market_value if position.market_value != 0 else 0

            return impact_pct

        except Exception:
            return 0.0

    def _calculate_portfolio_metrics(self) -> dict[str, float]:
        """Calculate comprehensive portfolio metrics."""
        try:
            returns = self._get_portfolio_returns(252)  # 1 year

            if returns.empty:
                return {}

            # Basic statistics
            metrics = {
                'daily_return': returns.mean(),
                'annual_return': returns.mean() * 252,
                'volatility': returns.std() * np.sqrt(252),
                'skewness': skew(returns),
                'kurtosis': kurtosis(returns)
            }

            # Risk-adjusted returns
            risk_free_rate = 0.05 / 252  # Daily
            excess_returns = returns - risk_free_rate

            metrics['sharpe_ratio'] = (excess_returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0  # noqa: E501

            # Downside deviation for Sortino
            downside_returns = returns[returns < 0]
            downside_std = downside_returns.std() if len(downside_returns) > 0 else returns.std()
            metrics['sortino_ratio'] = (excess_returns.mean() / downside_std) * np.sqrt(252) if downside_std > 0 else 0  # noqa: E501

            # Maximum drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            metrics['max_drawdown'] = drawdown.min()

            # VaR and CVaR
            var_95 = np.percentile(returns, 5)
            metrics['var_95'] = var_95
            metrics['cvar_95'] = returns[returns <= var_95].mean()

            return metrics

        except Exception as e:
            self.logger.error("Error calculating metrics: %s", e)
            return {}

    def _generate_portfolio_charts(self, positions: list[PortfolioPosition],
                                 correlation: CorrelationAnalysis,
                                 risk_attribution: RiskAttributionResult,
                                 stress_tests: list[StressTestResult]) -> dict[str, Any]:
        """Generate portfolio visualization charts."""
        charts = {}

        try:
            # 1. Position weights pie chart
            fig_weights = go.Figure(data=[go.Pie(
                labels=[p.symbol for p in positions],
                values=[p.weight for p in positions],
                hole=0.3,
                textposition='inside',
                textinfo='percent+label'
            )])

            fig_weights.update_layout(
                title='Portfolio Composition by Weight',
                showlegend=True
            )

            charts['position_weights'] = fig_weights.to_json()

            # 2. Correlation heatmap
            if not correlation.correlation_matrix.empty:
                fig_corr = go.Figure(data=go.Heatmap(
                    z=correlation.correlation_matrix.values,
                    x=correlation.correlation_matrix.columns,
                    y=correlation.correlation_matrix.index,
                    colorscale='RdBu',
                    zmid=0,
                    text=np.round(correlation.correlation_matrix.values, 2),
                    texttemplate='%{text}',
                    textfont={"size": 10}
                ))

                fig_corr.update_layout(
                    title='Position Correlation Matrix',
                    xaxis_title='',
                    yaxis_title=''
                )

                charts['correlation_heatmap'] = fig_corr.to_json()

            # 3. Risk attribution bar chart
            if risk_attribution.risk_percentages:
                sorted_risks = sorted(
                    risk_attribution.risk_percentages.items(),
                    key=lambda x: x[1],
                    reverse=True
                )

                fig_risk = go.Figure(data=[go.Bar(
                    x=[x[0] for x in sorted_risks],
                    y=[x[1] * 100 for x in sorted_risks],
                    text=[f'{x[1]*100:.1f}%' for x in sorted_risks],
                    textposition='auto'
                )])

                fig_risk.update_layout(
                    title='Risk Contribution by Position',
                    xaxis_title='Position',
                    yaxis_title='Risk Contribution (%)',
                    showlegend=False
                )

                charts['risk_attribution'] = fig_risk.to_json()

            # 4. Stress test waterfall chart
            if stress_tests:
                # Use worst case scenario
                worst_scenario = min(stress_tests, key=lambda x: x.portfolio_impact)

                # Get top 5 worst positions
                worst_positions = worst_scenario.worst_positions[:5]

                fig_stress = go.Figure(go.Waterfall(
                    x=[p[0] for p in worst_positions] + ['Portfolio Total'],
                    y=[p[1] * 100 for p in worst_positions] + [worst_scenario.portfolio_impact * 100],  # noqa: E501
                    text=[f'{p[1]*100:.1f}%' for p in worst_positions] + [f'{worst_scenario.portfolio_impact*100:.1f}%'],  # noqa: E501
                    textposition="outside",
                    connector={"line": {"color": "rgb(63, 63, 63)"}}
                ))

                fig_stress.update_layout(
                    title=f'Stress Test Impact: {worst_scenario.scenario_name}',
                    xaxis_title='Position',
                    yaxis_title='Impact (%)',
                    showlegend=False
                )

                charts['stress_test'] = fig_stress.to_json()

            # 5. Greeks exposure radar chart
            greeks_data = defaultdict(float)
            for position in positions:
                if position.greeks:
                    for greek, value in position.greeks.items():
                        greeks_data[greek] += abs(value)

            if greeks_data:
                categories = list(greeks_data.keys())
                values = list(greeks_data.values())

                # Normalize values for radar chart
                max_val = max(values) if values else 1
                normalized_values = [v / max_val * 100 for v in values]

                fig_greeks = go.Figure()

                fig_greeks.add_trace(go.Scatterpolar(
                    r=normalized_values,
                    theta=categories,
                    fill='toself',
                    name='Greeks Exposure'
                ))

                fig_greeks.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100]
                        )
                    ),
                    title='Greeks Exposure Profile (Normalized)',
                    showlegend=False
                )

                charts['greeks_exposure'] = fig_greeks.to_json()

        except Exception as e:
            self.logger.error("Error generating charts: %s", e)

        return charts

    def _empty_correlation_analysis(self) -> CorrelationAnalysis:
        """Return empty correlation analysis."""
        return CorrelationAnalysis(
            correlation_matrix=pd.DataFrame(),
            average_correlation=0.0,
            max_correlation_pair=('', '', 0.0),
            clustering_groups=[],
            eigenvalues=np.array([]),
            concentration_ratio=0.0
        )

    def _empty_risk_attribution(self) -> RiskAttributionResult:
        """Return empty risk attribution."""
        return RiskAttributionResult(
            total_risk=0.0,
            risk_contributions={},
            risk_percentages={},
            marginal_contributions={},
            concentration_metrics={}
        )

    def _export_html_portfolio_report(self, report_data: dict[str, Any],
                                    output_path: str) -> bool:
        """Export portfolio report as HTML."""
        try:
            # HTML template
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Portfolio Analytics Report - {report_date}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h1, h2, h3 {{ color: #333; }}
                    .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
                    .metric-value {{ font-size: 24px; font-weight: bold; color: #0066cc; }}
                    .metric-label {{ font-size: 14px; color: #666; }}
                    .risk-high {{ color: #dc3545; }}
                    .risk-medium {{ color: #ffc107; }}
                    .risk-low {{ color: #28a745; }}
                    table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    .suggestion {{ background: #e8f4f8; padding: 15px; margin: 10px 0; border-left: 4px solid #0066cc; }}
                    .suggestion h4 {{ margin-top: 0; }}
                    .chart-container {{ margin: 20px 0; }}
                </style>
            </head>
            <body>
                <h1>Portfolio Analytics Report</h1>
                <p>Generated: {report_date}</p>

                <div class="summary">
                    <h2>Portfolio Summary</h2>
                    <div class="metric">
                        <div class="metric-value">${total_value:,.2f}</div>
                        <div class="metric-label">Total Value</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{position_count}</div>
                        <div class="metric-label">Positions</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${unrealized_pnl:,.2f}</div>
                        <div class="metric-label">Unrealized P&L</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{sharpe_ratio:.2f}</div>
                        <div class="metric-label">Sharpe Ratio</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{max_drawdown:.1%}</div>
                        <div class="metric-label">Max Drawdown</div>
                    </div>
                </div>

                <h2>Risk Analysis</h2>
                <div class="risk-section">
                    <h3>Correlation Analysis</h3>
                    <p>Average Correlation: <strong>{avg_correlation:.2f}</strong></p>
                    <p>Highest Correlation: <strong>{max_corr_symbols}</strong> ({max_corr_value:.2f})</p>
                    <p>Concentration Ratio: <strong>{concentration_ratio:.2f}</strong></p>
                </div>

                <div class="risk-section">
                    <h3>Risk Attribution</h3>
                    <p>Total Portfolio Risk: <strong>{total_risk:.1%}</strong> annualized</p>
                    <p>Top Risk Contributor: <strong>{top_risk_position}</strong> ({top_risk_pct:.1%})</p>
                </div>

                <h2>Stress Test Results</h2>
                {stress_test_html}

                <h2>Optimization Suggestions</h2>
                {suggestions_html}

                <h2>Position Details</h2>
                {positions_table}

                <div class="chart-container">
                    <h3>Analytics Charts</h3>
                    <p>Interactive charts are available in the full dashboard view.</p>
                </div>
            </body>
            </html>
            """  # noqa: E501

            # Extract metrics
            metrics = report_data['portfolio_summary'].get('metrics', {})

            # Format stress tests
            stress_test_html = self._format_stress_tests_html(report_data.get('stress_tests', []))

            # Format suggestions
            suggestions_html = self._format_suggestions_html(report_data.get('optimization_suggestions', []))  # noqa: E501

            # Format positions table
            positions_table = self._format_positions_table_html(report_data.get('positions', []))

            # Get top risk position
            risk_attr = report_data.get('risk_attribution', {})
            risk_pcts = risk_attr.get('risk_percentages', {})
            top_risk = max(risk_pcts.items(), key=lambda x: x[1]) if risk_pcts else ('N/A', 0)

            # Get correlation data
            corr_data = report_data.get('correlation_analysis', {})
            max_corr = corr_data.get('max_correlation', ('', '', 0))

            # Fill template
            html_content = html_template.format(
                report_date=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                total_value=report_data['portfolio_summary']['total_value'],
                position_count=report_data['portfolio_summary']['position_count'],
                unrealized_pnl=report_data['portfolio_summary']['unrealized_pnl'],
                sharpe_ratio=metrics.get('sharpe_ratio', 0),
                max_drawdown=metrics.get('max_drawdown', 0),
                avg_correlation=corr_data.get('average_correlation', 0),
                max_corr_symbols=f"{max_corr[0]} - {max_corr[1]}",
                max_corr_value=max_corr[2],
                concentration_ratio=corr_data.get('concentration_ratio', 0),
                total_risk=risk_attr.get('total_risk', 0),
                top_risk_position=top_risk[0],
                top_risk_pct=top_risk[1] * 100,
                stress_test_html=stress_test_html,
                suggestions_html=suggestions_html,
                positions_table=positions_table
            )

            # Write to file
            with open(output_path, 'w') as f:
                f.write(html_content)

            self.logger.info("Portfolio report exported to %s", output_path)
            return True

        except Exception as e:
            self.logger.error("Error exporting HTML report: %s", e)
            return False

    def _export_pdf_portfolio_report(self, report_data: dict[str, Any],
                                   output_path: str) -> bool:
        """Export portfolio report as PDF."""
        self.logger.warning("PDF export not yet implemented")
        return False

    def _export_json_portfolio_report(self, report_data: dict[str, Any],
                                    output_path: str) -> bool:
        """Export portfolio report as JSON."""
        try:
            with open(output_path, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)

            self.logger.info("JSON report exported to %s", output_path)
            return True

        except Exception as e:
            self.logger.error("Error exporting JSON report: %s", e)
            return False

    def _format_stress_tests_html(self, stress_tests: list[dict]) -> str:
        """Format stress test results as HTML."""
        if not stress_tests:
            return "<p>No stress test results available.</p>"

        html = "<table><tr><th>Scenario</th><th>Portfolio Impact</th><th>Worst Position</th><th>VaR Impact</th></tr>"  # noqa: E501

        for test in stress_tests:
            worst_pos = test['worst_positions'][0] if test['worst_positions'] else ('N/A', 0)
            impact_class = 'risk-high' if test['portfolio_impact'] < -0.1 else 'risk-medium' if test['portfolio_impact'] < -0.05 else 'risk-low'  # noqa: E501

            html += f"""
            <tr>
                <td>{test['scenario_name']}</td>
                <td class="{impact_class}">{test['portfolio_impact']*100:.1f}%</td>
                <td>{worst_pos[0]} ({worst_pos[1]*100:.1f}%)</td>
                <td>${test['var_impact']:,.0f}</td>
            </tr>
            """

        html += "</table>"
        return html

    def _format_suggestions_html(self, suggestions: list[dict]) -> str:
        """Format optimization suggestions as HTML."""
        if not suggestions:
            return "<p>No optimization suggestions at this time.</p>"

        html = ""
        for suggestion in suggestions:
            html += f"""
            <div class="suggestion">
                <h4>{suggestion['suggestion_type']} (Priority: {suggestion['priority']})</h4>
                <p>{suggestion['description']}</p>
                <p><strong>Expected Improvement:</strong></p>
                <ul>
            """

            for metric, improvement in suggestion['expected_improvement'].items():
                html += f"<li>{metric}: {improvement:+.1%}</li>"

            html += "</ul><p><strong>Implementation Steps:</strong></p><ol>"

            for step in suggestion['implementation_steps']:
                html += f"<li>{step}</li>"

            html += "</ol></div>"

        return html

    def _format_positions_table_html(self, positions: list[dict]) -> str:
        """Format positions as HTML table."""
        if not positions:
            return "<p>No positions in portfolio.</p>"

        html = """
        <table>
            <tr>
                <th>Symbol</th>
                <th>Type</th>
                <th>Quantity</th>
                <th>Entry Price</th>
                <th>Current Price</th>
                <th>Market Value</th>
                <th>Unrealized P&L</th>
                <th>Weight</th>
            </tr>
        """

        for pos in positions:
            pnl_class = 'risk-low' if pos['unrealized_pnl'] > 0 else 'risk-high'

            html += f"""
            <tr>
                <td>{pos['symbol']}</td>
                <td>{pos['position_type']}</td>
                <td>{pos['quantity']}</td>
                <td>${pos['entry_price']:.2f}</td>
                <td>${pos['current_price']:.2f}</td>
                <td>${pos['market_value']:,.2f}</td>
                <td class="{pnl_class}">${pos['unrealized_pnl']:,.2f}</td>
                <td>{pos['weight']*100:.1f}%</td>
            </tr>
            """

        html += "</table>"
        return html

    # --------------------------------------------------------------------------
    # PYFOLIO / EMPYRICAL INTEGRATION
    # --------------------------------------------------------------------------

    def generate_pyfolio_tearsheet(self, returns: pd.Series,
                                   benchmark_returns: pd.Series | None = None,
                                   ) -> dict[str, Any]:
        """
        Generate institutional-grade portfolio analytics using PyFolio/empyrical.

        Args:
            returns: Strategy daily return series.
            benchmark_returns: Optional benchmark return series.

        Returns:
            Dictionary of institutional performance metrics.
        """
        try:
            import empyrical
        except ImportError:
            self.logger.warning("empyrical not installed — using fallback")
            return self._fallback_portfolio_metrics(returns)

        rf_daily = 0.05 / 252
        metrics: dict[str, Any] = {
            'annual_return': float(empyrical.annual_return(returns)),
            'annual_volatility': float(empyrical.annual_volatility(returns)),
            'sharpe_ratio': float(empyrical.sharpe_ratio(returns, risk_free=rf_daily)),
            'sortino_ratio': float(empyrical.sortino_ratio(returns)),
            'calmar_ratio': float(empyrical.calmar_ratio(returns)),
            'max_drawdown': float(empyrical.max_drawdown(returns)),
            'omega_ratio': float(empyrical.omega_ratio(returns)),
            'tail_ratio': float(empyrical.tail_ratio(returns)),
            'stability': float(empyrical.stability_of_timeseries(returns)),
            'var_95': float(np.percentile(returns, 5)),
            'cumulative_return': float(empyrical.cum_returns_final(returns)),
        }

        if benchmark_returns is not None:
            idx = returns.index.intersection(benchmark_returns.index)
            if len(idx) > 10:
                r, b = returns.loc[idx], benchmark_returns.loc[idx]
                metrics['alpha'] = float(empyrical.alpha(r, b, rf_daily))
                metrics['beta'] = float(empyrical.beta(r, b))
                metrics['information_ratio'] = float(empyrical.excess_sharpe(r, b))
                metrics['capture_ratio'] = float(empyrical.capture(r, b))

        self.logger.info(f"PyFolio tearsheet: Sharpe={metrics['sharpe_ratio']:.4f}")
        return metrics

    def _fallback_portfolio_metrics(self, returns: pd.Series) -> dict[str, Any]:
        """Fallback metrics without empyrical."""
        cum = (1 + returns).cumprod()
        return {
            'annual_return': float(cum.iloc[-1] ** (252 / len(returns)) - 1),
            'sharpe_ratio': float(returns.mean() / (returns.std() + 1e-8) * np.sqrt(252)),
            'max_drawdown': float(((cum - cum.expanding().max()) / cum.expanding().max()).min()),
            '_backend': 'fallback',
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_portfolio_analytics() -> PortfolioAnalytics:
    """
    Get singleton instance of PortfolioAnalytics.

    Returns:
        PortfolioAnalytics instance
    """
    global _analytics_instance
    if _analytics_instance is None:
        _analytics_instance = PortfolioAnalytics()
    return _analytics_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_analytics_instance: PortfolioAnalytics | None = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Example usage
    analytics = get_portfolio_analytics()

    # Generate comprehensive portfolio report
    success = analytics.generate_portfolio_report("portfolio_report.html", format='html')

    if success:

        # Print some analytics
        correlation = analytics.calculate_correlation_matrix()

        risk_attr = analytics.calculate_risk_attribution()

        suggestions = analytics.generate_optimization_suggestions()
        for _suggestion in suggestions[:3]:
            pass
