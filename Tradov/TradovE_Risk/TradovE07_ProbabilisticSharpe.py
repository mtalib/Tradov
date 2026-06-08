#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovE_Risk
Module: TradovE07_ProbabilisticSharpe.py
Purpose: Probabilistic Sharpe Ratio and Advanced Sharpe Analytics

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-01-16

Module Description:
    Implements advanced Sharpe Ratio calculations including:
    - Probabilistic Sharpe Ratio (PSR)
    - Sharpe Ratio confidence intervals
    - Minimum track record length
    - Deflated Sharpe Ratio (accounts for multiple testing bias)
    - Options-adjusted Sharpe (accounts for skewness and kurtosis)

References:
    - Bailey, D. H., & López de Prado, M. (2012). "The Sharpe Ratio Efficient Frontier"
    - Opdyke, J. D. (2007). "Comparing Sharpe ratios: So where are the p-values?"
    - Pézier, J., & White, A. (2006). "The Relative Merits of Investable Hedge Fund Indices"

Change Log:
    2026-01-16:
        - Initial implementation
        - Added probabilistic Sharpe Ratio
        - Added confidence intervals
        - Added options-adjusted Sharpe
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
    from TradovE_Risk.TradovE06_RiskMetrics import DEFAULT_RISK_FREE_RATE, TRADING_DAYS_PER_YEAR
except ImportError:
    import logging
    TradovLogger = type('TradovLogger', (), {
        'get_logger': staticmethod(lambda name: logging.getLogger(name))
    })()
    DEFAULT_RISK_FREE_RATE = 0.045
    TRADING_DAYS_PER_YEAR = 252

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Confidence levels
DEFAULT_CONFIDENCE_LEVEL = 0.95  # 95% confidence
HIGH_CONFIDENCE_LEVEL = 0.99     # 99% confidence

# Minimum periods for reliable estimation
MIN_PERIODS_PSR = 30
RECOMMENDED_PERIODS_PSR = 100

# Benchmark Sharpe ratios
BENCHMARK_SHARPE = 0.0  # Null hypothesis: Sharpe = 0
MARKET_BENCHMARK_SHARPE = 0.5  # Compare against market

# Multiple testing adjustment
DEFAULT_NUM_TRIALS = 1  # Number of strategies tested

# ==============================================================================
# ENUMS
# ==============================================================================
class AdjustmentType(Enum):
    """Types of Sharpe adjustments."""
    STANDARD = "standard"
    PROBABILISTIC = "probabilistic"
    OPTIONS_ADJUSTED = "options_adjusted"
    DEFLATED = "deflated"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SharpeConfidenceInterval:
    """Sharpe Ratio with confidence intervals."""
    sharpe_ratio: float
    lower_bound: float
    upper_bound: float
    confidence_level: float
    standard_error: float
    num_observations: int
    is_significant: bool  # Whether significantly different from zero

@dataclass
class ProbabilisticSharpeResult:
    """Probabilistic Sharpe Ratio results."""
    sharpe_ratio: float
    probabilistic_sharpe_ratio: float  # Probability Sharpe > benchmark
    benchmark_sharpe: float
    confidence_interval: SharpeConfidenceInterval
    min_track_record_length: int  # Periods needed for statistical significance
    num_observations: int
    skewness: float
    kurtosis: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

@dataclass
class OptionsAdjustedSharpe:
    """Options-adjusted Sharpe Ratio accounting for higher moments."""
    standard_sharpe: float
    adjusted_sharpe: float  # Pézier-White adjusted
    skewness: float
    excess_kurtosis: float
    adjustment_factor: float
    num_observations: int
    notes: str = ""

@dataclass
class DeflatedSharpeResult:
    """Deflated Sharpe Ratio (accounts for multiple testing)."""
    observed_sharpe: float
    deflated_sharpe: float
    num_trials: int  # Number of strategies tested
    variance_sharpe_estimates: float
    is_significant: bool
    p_value: float

# ==============================================================================
# PROBABILISTIC SHARPE RATIO CALCULATOR
# ==============================================================================
class ProbabilisticSharpeCalculator:
    """
    Calculates Probabilistic Sharpe Ratio and advanced Sharpe metrics.

    The Probabilistic Sharpe Ratio (PSR) estimates the probability that the
    true Sharpe Ratio exceeds a benchmark, accounting for estimation uncertainty.

    Features:
    - Probabilistic Sharpe Ratio (PSR)
    - Confidence intervals for Sharpe
    - Minimum track record length
    - Options-adjusted Sharpe (accounts for skewness/kurtosis)
    - Deflated Sharpe (accounts for multiple testing)

    Attributes:
        logger: Module logger
        risk_free_rate: Risk-free rate for calculations
    """

    def __init__(self, risk_free_rate: float = DEFAULT_RISK_FREE_RATE):
        """
        Initialize Probabilistic Sharpe calculator.

        Args:
            risk_free_rate: Annual risk-free rate
        """
        self.logger = TradovLogger.get_logger(__name__)
        self.risk_free_rate = risk_free_rate

        self.logger.info("ProbabilisticSharpeCalculator initialized")

    # ==========================================================================
    # PROBABILISTIC SHARPE RATIO
    # ==========================================================================
    def calculate_probabilistic_sharpe(
        self,
        returns: list[float],
        benchmark_sharpe: float = BENCHMARK_SHARPE,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        periods_per_year: int = TRADING_DAYS_PER_YEAR
    ) -> ProbabilisticSharpeResult:
        """
        Calculate Probabilistic Sharpe Ratio.

        PSR estimates the probability that the estimated Sharpe Ratio is greater
        than a benchmark Sharpe, accounting for estimation uncertainty and
        higher moments of the return distribution.

        Args:
            returns: List of period returns
            benchmark_sharpe: Benchmark Sharpe to test against
            confidence_level: Confidence level for intervals
            periods_per_year: Annualization factor

        Returns:
            ProbabilisticSharpeResult with all calculations
        """
        if len(returns) < MIN_PERIODS_PSR:
            self.logger.warning("Insufficient data for PSR: %s < %s", len(returns), MIN_PERIODS_PSR)
            return self._create_empty_psr_result()

        # Calculate standard Sharpe ratio
        sharpe = self._calculate_sharpe(returns, periods_per_year)

        # Calculate higher moments
        skewness = self._calculate_skewness(returns)
        kurtosis = self._calculate_kurtosis(returns)

        # Calculate confidence interval
        ci = self.calculate_sharpe_confidence_interval(
            returns,
            confidence_level,
            periods_per_year
        )

        # Calculate PSR
        # PSR = Probability that true Sharpe > benchmark Sharpe
        n = len(returns)

        # Standard error of Sharpe ratio (accounting for higher moments)
        # SE(SR) = sqrt[(1 + 0.5*SR^2 - Skew*SR + (Kurt-1)/4*SR^2) / n]
        sr_variance = (
            1 +
            0.5 * sharpe**2 -
            skewness * sharpe +
            (kurtosis - 1) / 4 * sharpe**2
        ) / n

        sr_std_error = math.sqrt(max(0, sr_variance))

        # Z-score for PSR
        if sr_std_error > 0:
            z_score = (sharpe - benchmark_sharpe) / sr_std_error
            # PSR is the CDF of standard normal at z_score
            psr = stats.norm.cdf(z_score)
        else:
            psr = 0.5  # No information

        # Minimum track record length
        # MTL = minimum observations needed for statistical significance
        mtl = self._calculate_min_track_record_length(
            sharpe,
            benchmark_sharpe,
            skewness,
            kurtosis,
            confidence_level
        )

        return ProbabilisticSharpeResult(
            sharpe_ratio=sharpe,
            probabilistic_sharpe_ratio=psr,
            benchmark_sharpe=benchmark_sharpe,
            confidence_interval=ci,
            min_track_record_length=mtl,
            num_observations=n,
            skewness=skewness,
            kurtosis=kurtosis
        )

    def calculate_sharpe_confidence_interval(
        self,
        returns: list[float],
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        periods_per_year: int = TRADING_DAYS_PER_YEAR
    ) -> SharpeConfidenceInterval:
        """
        Calculate confidence interval for Sharpe Ratio.

        Args:
            returns: List of period returns
            confidence_level: Confidence level (e.g., 0.95 for 95%)
            periods_per_year: Annualization factor

        Returns:
            SharpeConfidenceInterval object
        """
        if len(returns) < MIN_PERIODS_PSR:
            return self._create_empty_ci()

        # Calculate Sharpe ratio
        sharpe = self._calculate_sharpe(returns, periods_per_year)

        # Calculate standard error
        n = len(returns)
        skewness = self._calculate_skewness(returns)
        kurtosis = self._calculate_kurtosis(returns)

        # Adjusted standard error (accounts for non-normality)
        sr_variance = (
            1 +
            0.5 * sharpe**2 -
            skewness * sharpe +
            (kurtosis - 1) / 4 * sharpe**2
        ) / n

        sr_std_error = math.sqrt(max(0, sr_variance))

        # Calculate confidence interval
        # Using t-distribution for small samples
        if n < 30:
            t_critical = stats.t.ppf((1 + confidence_level) / 2, n - 1)
        else:
            t_critical = stats.norm.ppf((1 + confidence_level) / 2)

        margin_of_error = t_critical * sr_std_error

        lower_bound = sharpe - margin_of_error
        upper_bound = sharpe + margin_of_error

        # Check if significantly different from zero
        is_significant = lower_bound > 0 or upper_bound < 0

        return SharpeConfidenceInterval(
            sharpe_ratio=sharpe,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            confidence_level=confidence_level,
            standard_error=sr_std_error,
            num_observations=n,
            is_significant=is_significant
        )

    # ==========================================================================
    # OPTIONS-ADJUSTED SHARPE RATIO
    # ==========================================================================
    def calculate_options_adjusted_sharpe(
        self,
        returns: list[float],
        periods_per_year: int = TRADING_DAYS_PER_YEAR
    ) -> OptionsAdjustedSharpe:
        """
        Calculate options-adjusted Sharpe Ratio.

        For options trading, returns often have significant skewness and kurtosis.
        This adjustment (Pézier-White) accounts for investor preference for
        positive skewness and aversion to excess kurtosis.

        Adjusted SR = SR * [1 + (Skew/6)*SR - (ExcessKurt/24)*SR^2]

        Args:
            returns: List of period returns
            periods_per_year: Annualization factor

        Returns:
            OptionsAdjustedSharpe object
        """
        if len(returns) < MIN_PERIODS_PSR:
            return self._create_empty_options_sharpe()

        # Standard Sharpe
        standard_sharpe = self._calculate_sharpe(returns, periods_per_year)

        # Higher moments
        skewness = self._calculate_skewness(returns)
        excess_kurtosis = self._calculate_kurtosis(returns) - 3  # Excess over normal

        # Pézier-White adjustment
        # Adjustment = 1 + (Skew/6)*SR - (ExcessKurt/24)*SR^2
        adjustment_factor = (
            1 +
            (skewness / 6) * standard_sharpe -
            (excess_kurtosis / 24) * standard_sharpe**2
        )

        adjusted_sharpe = standard_sharpe * adjustment_factor

        # Generate notes
        notes = []
        if skewness > 0.5:
            notes.append("Positive skew improves risk-adjusted returns")
        elif skewness < -0.5:
            notes.append("Negative skew (tail risk) reduces risk-adjusted returns")

        if excess_kurtosis > 1:
            notes.append("High kurtosis (fat tails) indicates elevated tail risk")

        return OptionsAdjustedSharpe(
            standard_sharpe=standard_sharpe,
            adjusted_sharpe=adjusted_sharpe,
            skewness=skewness,
            excess_kurtosis=excess_kurtosis,
            adjustment_factor=adjustment_factor,
            num_observations=len(returns),
            notes="; ".join(notes)
        )

    # ==========================================================================
    # DEFLATED SHARPE RATIO
    # ==========================================================================
    def calculate_deflated_sharpe(
        self,
        returns: list[float],
        num_trials: int = DEFAULT_NUM_TRIALS,
        variance_sharpe_estimates: float | None = None,
        periods_per_year: int = TRADING_DAYS_PER_YEAR,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    ) -> DeflatedSharpeResult:
        """
        Calculate Deflated Sharpe Ratio.

        When multiple strategies are tested, the maximum observed Sharpe Ratio
        is upward biased. The Deflated Sharpe Ratio adjusts for this multiple
        testing bias.

        Args:
            returns: List of period returns
            num_trials: Number of strategies tested
            variance_sharpe_estimates: Variance of Sharpe estimates across trials
            periods_per_year: Annualization factor
            confidence_level: Confidence level for significance test

        Returns:
            DeflatedSharpeResult object
        """
        if len(returns) < MIN_PERIODS_PSR:
            return self._create_empty_deflated_sharpe()

        # Observed Sharpe
        observed_sharpe = self._calculate_sharpe(returns, periods_per_year)

        # If variance not provided, estimate from data
        if variance_sharpe_estimates is None:
            # Conservative estimate: assume some variation
            variance_sharpe_estimates = 0.1 * observed_sharpe**2

        # Expected maximum Sharpe under null (all trials are noise)
        # E[max SR] ≈ sqrt(2*log(N) * Var(SR))
        expected_max_sharpe = math.sqrt(
            2 * math.log(num_trials) * variance_sharpe_estimates
        )

        # Deflated Sharpe = (Observed - Expected Max) / SE
        n = len(returns)
        skewness = self._calculate_skewness(returns)
        kurtosis = self._calculate_kurtosis(returns)

        # Standard error
        sr_variance = (
            1 +
            0.5 * observed_sharpe**2 -
            skewness * observed_sharpe +
            (kurtosis - 1) / 4 * observed_sharpe**2
        ) / n

        sr_std_error = math.sqrt(max(0, sr_variance))

        # Deflated Sharpe
        if sr_std_error > 0:
            deflated_sharpe = (observed_sharpe - expected_max_sharpe) / sr_std_error

            # P-value (probability of observing this Sharpe by chance)
            p_value = 1 - stats.norm.cdf(deflated_sharpe)
        else:
            deflated_sharpe = 0
            p_value = 1.0

        # Is significant?
        is_significant = p_value < (1 - confidence_level)

        return DeflatedSharpeResult(
            observed_sharpe=observed_sharpe,
            deflated_sharpe=deflated_sharpe,
            num_trials=num_trials,
            variance_sharpe_estimates=variance_sharpe_estimates,
            is_significant=is_significant,
            p_value=p_value
        )

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _calculate_sharpe(
        self,
        returns: list[float],
        periods_per_year: int = TRADING_DAYS_PER_YEAR
    ) -> float:
        """Calculate standard Sharpe ratio."""
        if not returns:
            return 0.0

        excess_returns = [r - (self.risk_free_rate / periods_per_year) for r in returns]

        mean_excess = np.mean(excess_returns)
        std_excess = np.std(excess_returns, ddof=1)

        if std_excess == 0:
            return 0.0

        sharpe = (mean_excess / std_excess) * math.sqrt(periods_per_year)

        return sharpe

    def _calculate_skewness(self, returns: list[float]) -> float:
        """Calculate skewness of returns."""
        if len(returns) < 3:
            return 0.0

        return float(stats.skew(returns, bias=False))

    def _calculate_kurtosis(self, returns: list[float]) -> float:
        """Calculate kurtosis of returns (Fisher=False means total kurtosis)."""
        if len(returns) < 4:
            return 3.0  # Normal distribution kurtosis

        return float(stats.kurtosis(returns, bias=False, fisher=False))

    def _calculate_min_track_record_length(
        self,
        sharpe_ratio: float,
        benchmark_sharpe: float,
        skewness: float,
        kurtosis: float,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    ) -> int:
        """
        Calculate minimum track record length for statistical significance.

        This is the minimum number of observations needed to be confident
        that the Sharpe Ratio exceeds the benchmark.
        """
        # Z-score for confidence level
        z_score = stats.norm.ppf(confidence_level)

        # Variance of Sharpe estimate
        sr_variance_per_period = (
            1 +
            0.5 * sharpe_ratio**2 -
            skewness * sharpe_ratio +
            (kurtosis - 1) / 4 * sharpe_ratio**2
        )

        # Required n such that: (SR - SR_benchmark) > z * SE(SR)
        # SE(SR) = sqrt(sr_variance / n)
        # Solving for n:
        if sharpe_ratio <= benchmark_sharpe:
            return 999999  # Would never be significant

        denominator = (sharpe_ratio - benchmark_sharpe)**2
        if denominator == 0:
            return 999999

        min_n = (z_score**2 * sr_variance_per_period) / denominator

        return max(MIN_PERIODS_PSR, int(math.ceil(min_n)))

    def _create_empty_psr_result(self) -> ProbabilisticSharpeResult:
        """Create empty PSR result."""
        return ProbabilisticSharpeResult(
            sharpe_ratio=0.0,
            probabilistic_sharpe_ratio=0.0,
            benchmark_sharpe=0.0,
            confidence_interval=self._create_empty_ci(),
            min_track_record_length=999999,
            num_observations=0,
            skewness=0.0,
            kurtosis=3.0
        )

    def _create_empty_ci(self) -> SharpeConfidenceInterval:
        """Create empty confidence interval."""
        return SharpeConfidenceInterval(
            sharpe_ratio=0.0,
            lower_bound=0.0,
            upper_bound=0.0,
            confidence_level=DEFAULT_CONFIDENCE_LEVEL,
            standard_error=0.0,
            num_observations=0,
            is_significant=False
        )

    def _create_empty_options_sharpe(self) -> OptionsAdjustedSharpe:
        """Create empty options-adjusted Sharpe."""
        return OptionsAdjustedSharpe(
            standard_sharpe=0.0,
            adjusted_sharpe=0.0,
            skewness=0.0,
            excess_kurtosis=0.0,
            adjustment_factor=1.0,
            num_observations=0,
            notes="Insufficient data"
        )

    def _create_empty_deflated_sharpe(self) -> DeflatedSharpeResult:
        """Create empty deflated Sharpe."""
        return DeflatedSharpeResult(
            observed_sharpe=0.0,
            deflated_sharpe=0.0,
            num_trials=0,
            variance_sharpe_estimates=0.0,
            is_significant=False,
            p_value=1.0
        )

# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================
def calculate_probabilistic_sharpe(
    returns: list[float],
    benchmark_sharpe: float = BENCHMARK_SHARPE,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE
) -> ProbabilisticSharpeResult:
    """
    Quick calculation of Probabilistic Sharpe Ratio.

    Args:
        returns: List of returns
        benchmark_sharpe: Benchmark to test against
        risk_free_rate: Risk-free rate

    Returns:
        ProbabilisticSharpeResult
    """
    calculator = ProbabilisticSharpeCalculator(risk_free_rate)
    return calculator.calculate_probabilistic_sharpe(returns, benchmark_sharpe)

def calculate_options_adjusted_sharpe(
    returns: list[float],
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE
) -> OptionsAdjustedSharpe:
    """
    Quick calculation of options-adjusted Sharpe Ratio.

    Args:
        returns: List of returns
        risk_free_rate: Risk-free rate

    Returns:
        OptionsAdjustedSharpe
    """
    calculator = ProbabilisticSharpeCalculator(risk_free_rate)
    return calculator.calculate_options_adjusted_sharpe(returns)

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    'ProbabilisticSharpeCalculator',
    'ProbabilisticSharpeResult',
    'SharpeConfidenceInterval',
    'OptionsAdjustedSharpe',
    'DeflatedSharpeResult',
    'calculate_probabilistic_sharpe',
    'calculate_options_adjusted_sharpe',
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    # Create calculator
    calculator = ProbabilisticSharpeCalculator()

    # Generate sample options returns (with negative skew, high kurtosis)
    np.random.seed(42)

    # Simulate options returns: positive drift, negative skew, fat tails
    base_returns = np.random.normal(0.001, 0.02, 250)
    # Add occasional large losses (negative skew)
    base_returns[np.random.choice(250, 10)] -= np.random.uniform(0.05, 0.15, 10)
    # Add occasional large wins
    base_returns[np.random.choice(250, 5)] += np.random.uniform(0.03, 0.08, 5)

    returns = base_returns.tolist()

    # Test 1: Probabilistic Sharpe Ratio

    psr_result = calculator.calculate_probabilistic_sharpe(returns)


    # Test 2: Options-Adjusted Sharpe

    options_sharpe = calculator.calculate_options_adjusted_sharpe(returns)


    # Test 3: Deflated Sharpe Ratio

    # Simulate testing 50 strategies
    deflated = calculator.calculate_deflated_sharpe(
        returns,
        num_trials=50,
        variance_sharpe_estimates=0.05
    )


    # Interpretation

    if psr_result.probabilistic_sharpe_ratio > 0.95 or psr_result.probabilistic_sharpe_ratio > 0.80:
        pass
    else:
        pass

    if psr_result.num_observations < psr_result.min_track_record_length:
        pass
    else:
        pass

    if options_sharpe.adjusted_sharpe < options_sharpe.standard_sharpe:
        pass
    else:
        pass

