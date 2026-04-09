#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderK_Reports
Module: SpyderK12_InstitutionalTearSheet.py
Purpose: Reusable PyFolio-based institutional tear sheet generator

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-02-26 Time: 15:00:00

Module Description:
    Centralized tear sheet generation using PyFolio and empyrical.
    Provides full, risk, returns, and custom tear sheets for any
    strategy or portfolio. Callable from other K-series reports,
    strategy evaluators, and dashboard components.

    Key Features:
        - Full tear sheet generation (returns, risk, drawdown, positions)
        - Risk-focused tear sheet with VaR, CVaR, tail analysis
        - Returns analysis with rolling Sharpe, alpha/beta decomposition
        - Drawdown waterfall analysis
        - Summary statistics dictionary for programmatic consumption
        - HTML and dict output modes

Change Log:
    2026-02-26:
        - Initial creation as part of Phase 3 institutional library integration
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime
from typing import Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# PYFOLIO / EMPYRICAL IMPORTS (Optional)
# ==============================================================================
try:
    import empyrical
    HAS_EMPYRICAL = True
except ImportError:
    empyrical = None
    HAS_EMPYRICAL = False

try:
    import pyfolio
    HAS_PYFOLIO = True
except ImportError:
    pyfolio = None
    HAS_PYFOLIO = False

try:
    import quantstats as qs
    HAS_QUANTSTATS = True
except ImportError:
    qs = None  # type: ignore[assignment]
    HAS_QUANTSTATS = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    plt = None
    HAS_MATPLOTLIB = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
TRADING_DAYS_PER_YEAR = 252
DEFAULT_RISK_FREE_RATE = 0.05
VAR_CONFIDENCE_LEVELS = [0.95, 0.99]
ROLLING_SHARPE_WINDOW = 63  # ~3 months
ROLLING_BETA_WINDOW = 126   # ~6 months


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class TearSheetConfig:
    """Configuration for tear sheet generation."""
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    rolling_sharpe_window: int = ROLLING_SHARPE_WINDOW
    rolling_beta_window: int = ROLLING_BETA_WINDOW
    benchmark_symbol: str = 'SPY'
    var_confidence: float = 0.95
    output_format: str = 'dict'  # 'dict', 'html', 'png'
    output_dir: str | None = None
    include_positions: bool = False
    include_transactions: bool = False
    title: str = 'SPYDER Strategy Tear Sheet'


class TearSheetType(Enum):
    """Types of tear sheets available."""
    FULL = 'full'
    RETURNS = 'returns'
    RISK = 'risk'
    DRAWDOWN = 'drawdown'
    SUMMARY = 'summary'


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class InstitutionalTearSheet:
    """
    PyFolio-based institutional tear sheet generator.

    Provides standardized performance analytics for any strategy
    or portfolio return series. Uses empyrical for metrics and
    optionally pyfolio for full tear sheet visualizations.

    Args:
        config: Tear sheet configuration.
    """

    def __init__(self, config: TearSheetConfig | None = None):
        self.config = config or TearSheetConfig()
        self.logger = SpyderLogger("K12_InstitutionalTearSheet")
        self.error_handler = SpyderErrorHandler()

    # ==========================================================================
    # CORE METRICS (empyrical-based)
    # ==========================================================================

    def compute_return_metrics(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series | None = None,
    ) -> dict[str, float]:
        """
        Compute comprehensive return metrics using empyrical.

        Args:
            returns: Strategy daily return series (non-cumulative).
            benchmark_returns: Optional benchmark return series.

        Returns:
            Dictionary of return metrics.
        """
        if not HAS_EMPYRICAL:
            return self._fallback_return_metrics(returns)

        rf = self.config.risk_free_rate / TRADING_DAYS_PER_YEAR
        metrics: dict[str, float] = {}

        try:
            metrics['annual_return'] = float(empyrical.annual_return(returns))
            metrics['annual_volatility'] = float(empyrical.annual_volatility(returns))
            metrics['sharpe_ratio'] = float(empyrical.sharpe_ratio(
                returns, risk_free=rf))
            metrics['sortino_ratio'] = float(empyrical.sortino_ratio(
                returns, required_return=rf))
            metrics['calmar_ratio'] = float(empyrical.calmar_ratio(returns))
            metrics['max_drawdown'] = float(empyrical.max_drawdown(returns))
            metrics['omega_ratio'] = float(empyrical.omega_ratio(
                returns, required_return=rf))
            metrics['tail_ratio'] = float(empyrical.tail_ratio(returns))
            metrics['stability'] = float(empyrical.stability_of_timeseries(returns))
            metrics['skew'] = float(returns.skew())
            metrics['kurtosis'] = float(returns.kurtosis())
            metrics['cumulative_return'] = float(empyrical.cum_returns_final(returns))

            # Downside metrics
            metrics['downside_risk'] = float(
                empyrical.downside_risk(returns, required_return=rf))

            # Value at Risk
            metrics['var_95'] = float(np.percentile(returns, 5))
            metrics['cvar_95'] = float(returns[returns <= np.percentile(returns, 5)].mean()
                                       if len(returns[returns <= np.percentile(returns, 5)]) > 0
                                       else 0)
            metrics['var_99'] = float(np.percentile(returns, 1))
            metrics['cvar_99'] = float(returns[returns <= np.percentile(returns, 1)].mean()
                                       if len(returns[returns <= np.percentile(returns, 1)]) > 0
                                       else 0)

            # Benchmark-relative metrics
            if benchmark_returns is not None and len(benchmark_returns) > 0:
                idx = returns.index.intersection(benchmark_returns.index)
                if len(idx) > 10:
                    r_aligned = returns.loc[idx]
                    b_aligned = benchmark_returns.loc[idx]
                    metrics['alpha'] = float(empyrical.alpha(r_aligned, b_aligned, rf))
                    metrics['beta'] = float(empyrical.beta(r_aligned, b_aligned))
                    metrics['information_ratio'] = float(
                        empyrical.excess_sharpe(r_aligned, b_aligned))
                    tracking_diff = r_aligned - b_aligned
                    metrics['tracking_error'] = float(
                        tracking_diff.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
                    metrics['capture_ratio'] = float(
                        empyrical.capture(r_aligned, b_aligned))
                    metrics['up_capture'] = float(
                        empyrical.up_capture(r_aligned, b_aligned))
                    metrics['down_capture'] = float(
                        empyrical.down_capture(r_aligned, b_aligned))

            # quantstats supplement: additional institutional metrics not in empyrical
            if HAS_QUANTSTATS and len(returns) >= 30:
                try:
                    metrics['qs_sharpe'] = float(qs.stats.sharpe(returns))
                    metrics['qs_sortino'] = float(qs.stats.sortino(returns))
                    metrics['qs_max_drawdown'] = float(qs.stats.max_drawdown(returns))
                    metrics['qs_cagr'] = float(qs.stats.cagr(returns))
                    metrics['qs_volatility'] = float(qs.stats.volatility(returns))
                    metrics['qs_win_rate'] = float(qs.stats.win_rate(returns))
                    metrics['qs_best'] = float(qs.stats.best(returns))
                    metrics['qs_worst'] = float(qs.stats.worst(returns))
                    metrics['qs_avg_win'] = float(qs.stats.avg_win(returns))
                    metrics['qs_avg_loss'] = float(qs.stats.avg_loss(returns))
                    metrics['qs_payoff_ratio'] = float(qs.stats.payoff_ratio(returns))
                    metrics['qs_profit_factor'] = float(qs.stats.profit_factor(returns))
                    metrics['qs_serenity_index'] = float(qs.stats.serenity_index(returns))
                    metrics['qs_kelly_criterion'] = float(qs.stats.kelly_criterion(returns))
                except Exception as _qs_err:
                    self.logger.debug("quantstats enrichment skipped: %s", _qs_err)

        except Exception as e:
            self.logger.error("Error computing return metrics: %s", e)
            return self._fallback_return_metrics(returns)

        return metrics

    def _fallback_return_metrics(self, returns: pd.Series) -> dict[str, float]:
        """Compute basic metrics without empyrical."""
        if len(returns) == 0:
            return {'status': 'empty_returns'}

        ann_factor = np.sqrt(TRADING_DAYS_PER_YEAR)
        daily_rf = self.config.risk_free_rate / TRADING_DAYS_PER_YEAR

        excess = returns - daily_rf
        cumulative = (1 + returns).cumprod()
        peak = cumulative.expanding().max()
        drawdowns = (cumulative - peak) / peak

        return {
            'annual_return': float((cumulative.iloc[-1]) ** (252 / len(returns)) - 1),
            'annual_volatility': float(returns.std() * ann_factor),
            'sharpe_ratio': float(excess.mean() / (returns.std() + 1e-8) * ann_factor),
            'max_drawdown': float(drawdowns.min()),
            'cumulative_return': float(cumulative.iloc[-1] - 1),
            'var_95': float(np.percentile(returns, 5)),
            'skew': float(returns.skew()),
            'kurtosis': float(returns.kurtosis()),
            '_backend': 'fallback',
        }

    # ==========================================================================
    # DRAWDOWN ANALYSIS
    # ==========================================================================

    def compute_drawdown_analysis(self, returns: pd.Series) -> dict[str, Any]:
        """
        Detailed drawdown analysis with top-N waterfall table.

        Args:
            returns: Daily return series.

        Returns:
            Drawdown statistics and waterfall data.
        """
        cumulative = (1 + returns).cumprod()
        peak = cumulative.expanding().max()
        drawdowns = (cumulative - peak) / peak

        # Create drawdown table
        dd_series = drawdowns.copy()
        dd_periods = []
        in_dd = False
        start = None
        max_dd = 0
        trough_date = None

        for _i, (date, val) in enumerate(dd_series.items()):
            if val < 0 and not in_dd:
                in_dd = True
                start = date
                max_dd = val
                trough_date = date
            elif val < 0 and in_dd:
                if val < max_dd:
                    max_dd = val
                    trough_date = date
            elif val >= 0 and in_dd:
                dd_periods.append({
                    'start': start,
                    'trough': trough_date,
                    'end': date,
                    'max_drawdown': float(max_dd),
                    'duration': (date - start).days,
                    'recovery': (date - trough_date).days,
                })
                in_dd = False
                max_dd = 0

        if in_dd:
            dd_periods.append({
                'start': start,
                'trough': trough_date,
                'end': None,
                'max_drawdown': float(max_dd),
                'duration': (dd_series.index[-1] - start).days,
                'recovery': None,
            })

        # Sort by severity
        dd_periods.sort(key=lambda x: x['max_drawdown'])
        top_5 = dd_periods[:5]

        return {
            'max_drawdown': float(drawdowns.min()),
            'max_drawdown_date': str(drawdowns.idxmin()),
            'n_drawdown_periods': len(dd_periods),
            'avg_drawdown': float(np.mean([d['max_drawdown'] for d in dd_periods]))
                            if dd_periods else 0,
            'avg_drawdown_duration': float(
                np.mean([d['duration'] for d in dd_periods if d['duration']]
                        )) if dd_periods else 0,
            'avg_recovery_days': float(
                np.mean([d['recovery'] for d in dd_periods if d['recovery'] is not None]
                        )) if dd_periods else 0,
            'top_5_drawdowns': [
                {k: str(v) if isinstance(v, (pd.Timestamp, datetime)) else v
                 for k, v in d.items()}
                for d in top_5
            ],
            'current_drawdown': float(drawdowns.iloc[-1]),
        }

    # ==========================================================================
    # ROLLING METRICS
    # ==========================================================================

    def compute_rolling_metrics(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series | None = None,
    ) -> dict[str, Any]:
        """
        Compute rolling performance metrics.

        Args:
            returns: Daily return series.
            benchmark_returns: Optional benchmark returns.

        Returns:
            Rolling Sharpe ratio, volatility, and beta series.
        """
        rf_daily = self.config.risk_free_rate / TRADING_DAYS_PER_YEAR
        window = self.config.rolling_sharpe_window

        excess = returns - rf_daily
        rolling_mean = excess.rolling(window=window).mean()
        rolling_std = returns.rolling(window=window).std()
        rolling_sharpe = (rolling_mean / (rolling_std + 1e-8)) * np.sqrt(TRADING_DAYS_PER_YEAR)

        rolling_vol = rolling_std * np.sqrt(TRADING_DAYS_PER_YEAR)

        result: dict[str, Any] = {
            'rolling_sharpe': rolling_sharpe.dropna().to_dict(),
            'rolling_volatility': rolling_vol.dropna().to_dict(),
            'sharpe_window': window,
        }

        if benchmark_returns is not None:
            beta_window = self.config.rolling_beta_window
            idx = returns.index.intersection(benchmark_returns.index)
            if len(idx) > beta_window:
                r = returns.loc[idx]
                b = benchmark_returns.loc[idx]
                cov = r.rolling(beta_window).cov(b)
                var = b.rolling(beta_window).var()
                rolling_beta = cov / (var + 1e-12)
                result['rolling_beta'] = rolling_beta.dropna().to_dict()
                result['beta_window'] = beta_window

        return result

    # ==========================================================================
    # FULL TEAR SHEET
    # ==========================================================================

    def generate_full_tearsheet(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series | None = None,
        positions: pd.DataFrame | None = None,
        transactions: pd.DataFrame | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a full institutional tear sheet.

        Args:
            returns: Strategy daily return series.
            benchmark_returns: Benchmark daily returns.
            positions: Optional position data.
            transactions: Optional transaction data.
            title: Tear sheet title.

        Returns:
            Complete tear sheet data including all metrics.
        """
        title = title or self.config.title
        self.logger.info("Generating full tear sheet: %s", title)

        result: dict[str, Any] = {
            'title': title,
            'generated_at': datetime.now().isoformat(),
            'data_range': {
                'start': str(returns.index[0]),
                'end': str(returns.index[-1]),
                'trading_days': len(returns),
            },
            'empyrical_available': HAS_EMPYRICAL,
            'pyfolio_available': HAS_PYFOLIO,
        }

        # Return metrics
        result['return_metrics'] = self.compute_return_metrics(
            returns, benchmark_returns)

        # Drawdown analysis
        result['drawdown_analysis'] = self.compute_drawdown_analysis(returns)

        # Rolling metrics
        result['rolling_metrics'] = self.compute_rolling_metrics(
            returns, benchmark_returns)

        # Monthly returns table
        result['monthly_returns'] = self._monthly_returns_table(returns)

        # Distribution stats
        result['distribution'] = {
            'best_day': float(returns.max()),
            'worst_day': float(returns.min()),
            'avg_daily_return': float(returns.mean()),
            'positive_days': int((returns > 0).sum()),
            'negative_days': int((returns < 0).sum()),
            'win_rate': float((returns > 0).sum() / len(returns)),
            'avg_win': float(returns[returns > 0].mean()) if (returns > 0).any() else 0,
            'avg_loss': float(returns[returns < 0].mean()) if (returns < 0).any() else 0,
            'profit_factor': float(
                abs(returns[returns > 0].sum() / (returns[returns < 0].sum() + 1e-12))
            ),
        }

        self.logger.info("Tear sheet generated: Sharpe=%s", result['return_metrics'].get('sharpe_ratio', 'N/A'))
        return result

    def generate_risk_tearsheet(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series | None = None,
    ) -> dict[str, Any]:
        """
        Generate a risk-focused tear sheet.

        Args:
            returns: Strategy daily return series.
            benchmark_returns: Benchmark returns.

        Returns:
            Risk metrics including VaR, CVaR, and tail analysis.
        """
        self.logger.info("Generating risk tear sheet")

        metrics = self.compute_return_metrics(returns, benchmark_returns)
        drawdown = self.compute_drawdown_analysis(returns)

        # Parametric VaR (normal approximation)
        daily_mean = returns.mean()
        daily_std = returns.std()
        from scipy.stats import norm
        try:
            parametric_var_95 = float(daily_mean - norm.ppf(0.95) * daily_std)
            parametric_var_99 = float(daily_mean - norm.ppf(0.99) * daily_std)
        except Exception:
            parametric_var_95 = float(np.percentile(returns, 5))
            parametric_var_99 = float(np.percentile(returns, 1))

        # Tail analysis
        left_tail = returns[returns < returns.quantile(0.05)]
        right_tail = returns[returns > returns.quantile(0.95)]

        return {
            'title': 'Risk Tear Sheet',
            'generated_at': datetime.now().isoformat(),
            'var_historical': {
                'var_95': metrics.get('var_95', 0),
                'cvar_95': metrics.get('cvar_95', 0),
                'var_99': metrics.get('var_99', 0),
                'cvar_99': metrics.get('cvar_99', 0),
            },
            'var_parametric': {
                'var_95': parametric_var_95,
                'var_99': parametric_var_99,
            },
            'drawdown': drawdown,
            'tail_analysis': {
                'left_tail_mean': float(left_tail.mean()) if len(left_tail) > 0 else 0,
                'left_tail_std': float(left_tail.std()) if len(left_tail) > 0 else 0,
                'right_tail_mean': float(right_tail.mean()) if len(right_tail) > 0 else 0,
                'tail_ratio': metrics.get('tail_ratio', 0),
            },
            'volatility': {
                'annual': metrics.get('annual_volatility', 0),
                'downside_risk': metrics.get('downside_risk', 0),
            },
            'stability': metrics.get('stability', 0),
        }

    def generate_returns_tearsheet(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series | None = None,
    ) -> dict[str, Any]:
        """
        Generate a returns-focused tear sheet.

        Args:
            returns: Strategy daily return series.
            benchmark_returns: Benchmark returns.

        Returns:
            Returns analysis with cumulative, rolling, and factor exposure.
        """
        self.logger.info("Generating returns tear sheet")

        metrics = self.compute_return_metrics(returns, benchmark_returns)
        rolling = self.compute_rolling_metrics(returns, benchmark_returns)

        # Cumulative returns
        (1 + returns).cumprod()

        # Annual returns by year
        annual_by_year = {}
        for year in returns.index.year.unique():
            yr_returns = returns[returns.index.year == year]
            annual_by_year[int(year)] = float((1 + yr_returns).prod() - 1)

        return {
            'title': 'Returns Tear Sheet',
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'annual_return': metrics.get('annual_return', 0),
                'cumulative_return': metrics.get('cumulative_return', 0),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'sortino_ratio': metrics.get('sortino_ratio', 0),
                'calmar_ratio': metrics.get('calmar_ratio', 0),
                'omega_ratio': metrics.get('omega_ratio', 0),
            },
            'annual_returns_by_year': annual_by_year,
            'monthly_returns': self._monthly_returns_table(returns),
            'rolling': rolling,
            'benchmark_relative': {
                'alpha': metrics.get('alpha'),
                'beta': metrics.get('beta'),
                'information_ratio': metrics.get('information_ratio'),
                'tracking_error': metrics.get('tracking_error'),
                'up_capture': metrics.get('up_capture'),
                'down_capture': metrics.get('down_capture'),
            } if benchmark_returns is not None else None,
        }

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _monthly_returns_table(self, returns: pd.Series) -> dict[str, dict[str, float]]:
        """Build a year x month returns matrix."""
        monthly = returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)
        result: dict[str, dict[str, float]] = {}
        for date, ret in monthly.items():
            year = str(date.year)
            month = str(date.month)
            if year not in result:
                result[year] = {}
            result[year][month] = round(float(ret), 6)
        return result

    def _save_figure(self, fig, name: str) -> str | None:
        """Save a matplotlib figure if configured."""
        if not HAS_MATPLOTLIB or not self.config.output_dir:
            return None

        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{name}.png"
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return str(path)

    # ==========================================================================
    # COMPARISON TEAR SHEET
    # ==========================================================================

    def compare_strategies(
        self,
        strategy_returns: dict[str, pd.Series],
        benchmark_returns: pd.Series | None = None,
    ) -> dict[str, Any]:
        """
        Compare multiple strategies side-by-side.

        Args:
            strategy_returns: {name: returns_series} dictionary.
            benchmark_returns: Optional benchmark for alpha/beta.

        Returns:
            Comparison table with metrics for each strategy.
        """
        self.logger.info("Comparing %s strategies", len(strategy_returns))

        comparison: dict[str, dict[str, float]] = {}
        for name, returns in strategy_returns.items():
            comparison[name] = self.compute_return_metrics(returns, benchmark_returns)

        # Rank strategies by Sharpe
        rankings = sorted(
            comparison.items(),
            key=lambda x: x[1].get('sharpe_ratio', 0),
            reverse=True,
        )

        return {
            'title': 'Strategy Comparison',
            'generated_at': datetime.now().isoformat(),
            'n_strategies': len(strategy_returns),
            'strategies': comparison,
            'rankings_by_sharpe': [r[0] for r in rankings],
            'best_strategy': rankings[0][0] if rankings else None,
            'best_sharpe': rankings[0][1].get('sharpe_ratio', 0) if rankings else 0,
        }

    # ==========================================================================
    # PORTFOLIO TEAR SHEET
    # ==========================================================================

    def generate_portfolio_tearsheet(
        self,
        returns: pd.Series,
        positions: pd.DataFrame,
        transactions: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        """
        Generate a portfolio-level tear sheet with position analytics.

        Args:
            returns: Portfolio daily return series.
            positions: Position DataFrame (date x asset weights).
            transactions: Optional transaction log.

        Returns:
            Portfolio analytics including concentration and turnover.
        """
        full = self.generate_full_tearsheet(returns)

        # Position analytics
        position_stats = {}
        if len(positions) > 0:
            position_stats = {
                'n_assets': int(positions.shape[1]),
                'avg_positions': float(
                    (positions != 0).sum(axis=1).mean()),
                'max_positions': int(
                    (positions != 0).sum(axis=1).max()),
                'concentration_hhi': float(
                    (positions.iloc[-1] ** 2).sum()),
            }

        # Turnover
        turnover = {}
        if len(positions) > 1:
            daily_turnover = positions.diff().abs().sum(axis=1) / 2
            turnover = {
                'avg_daily_turnover': float(daily_turnover.mean()),
                'annual_turnover': float(daily_turnover.mean() * TRADING_DAYS_PER_YEAR),
            }

        full['position_analytics'] = position_stats
        full['turnover'] = turnover
        full['title'] = 'Portfolio Tear Sheet'

        return full

    # ==========================================================================
    # SUMMARY
    # ==========================================================================

    def get_summary(self) -> dict[str, Any]:
        """Get tear sheet generator status."""
        return {
            'pyfolio_available': HAS_PYFOLIO,
            'empyrical_available': HAS_EMPYRICAL,
            'matplotlib_available': HAS_MATPLOTLIB,
            'config': {
                'risk_free_rate': self.config.risk_free_rate,
                'rolling_sharpe_window': self.config.rolling_sharpe_window,
                'benchmark': self.config.benchmark_symbol,
            },
        }


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_institutional_tearsheet(
    config: TearSheetConfig | None = None,
) -> InstitutionalTearSheet:
    """Create an InstitutionalTearSheet instance."""
    return InstitutionalTearSheet(config)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_instance: InstitutionalTearSheet | None = None


def get_institutional_tearsheet() -> InstitutionalTearSheet:
    """Get singleton instance."""
    global _instance
    if _instance is None:
        _instance = InstitutionalTearSheet()
    return _instance


# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":

    ts = create_institutional_tearsheet()
    summary = ts.get_summary()

    # Generate test data
    np.random.seed(42)
    dates = pd.date_range('2022-01-01', periods=504, freq='B')
    strategy_returns = pd.Series(
        np.random.randn(504) * 0.01 + 0.0003,
        index=dates,
        name='strategy',
    )
    benchmark_returns = pd.Series(
        np.random.randn(504) * 0.008 + 0.0002,
        index=dates,
        name='benchmark',
    )

    full = ts.generate_full_tearsheet(
        strategy_returns, benchmark_returns,
        title='Test Strategy')
    rm = full['return_metrics']

    risk = ts.generate_risk_tearsheet(strategy_returns)

    comp = ts.compare_strategies({
        'Momentum': strategy_returns,
        'Mean Reversion': pd.Series(np.random.randn(504) * 0.012 + 0.0001,
                                    index=dates),
        'Vol Trading': pd.Series(np.random.randn(504) * 0.015 + 0.0004,
                                 index=dates),
    })

