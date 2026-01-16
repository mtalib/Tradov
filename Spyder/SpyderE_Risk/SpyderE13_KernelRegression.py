#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Series: SpyderE_Risk
Module: SpyderE13_KernelRegression.py
Purpose: Kernel Regression for Non-Parametric Trend Estimation
Author: SPYDER Team
Date Created: 2025-01-04
Last Updated: 2025-01-04

Description:
    Implements Kernel Regression (Nadaraya-Watson estimator) for
    non-parametric trend estimation and mean reversion analysis,
    inspired by Renaissance Technologies' quantitative framework.
    
    Kernel Regression provides:
    - Smooth trend estimation without parametric assumptions
    - Dynamic envelope for mean reversion signals
    - Bandwidth optimization via cross-validation
    - Local trend analysis at each point
    - Robust to non-linear patterns
    
    Based on Renaissance research, Kernel Regression excels at
    identifying local trends and mean reversion opportunities
    in noisy market data, providing superior signal-to-noise
    ratio compared to linear regression.

Key Features:
    - Nadaraya-Watson Kernel Regression
    - Multiple kernel functions (Gaussian, Epanechnikov, Triangular)
    - Bandwidth optimization (Silverman's rule, cross-validation)
    - Dynamic envelope calculation (±1σ, ±2σ)
    - Mean reversion signal generation
    - Local trend strength analysis
    - Confidence intervals

Dependencies:
    - numpy, pandas for data processing
    - scipy for kernel functions and optimization
    - scikit-learn for cross-validation

References:
    - Nadaraya, E. (1964) "On Estimating Regression"
    - Watson, G. (1964) "Smooth Regression Analysis"
    - Silverman, B. (1986) "Density Estimation for Statistics and Data Analysis"
    - Renaissance Technologies research on kernel methods
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize_scalar

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    # Fallback logging if custom modules not available
    import logging
    SpyderLogger = logging.getLogger
    SpyderErrorHandler = type('SpyderErrorHandler', (), {
        'handle_error': lambda self, e, context: logging.error(f"[{context}] {e}")
    })

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Kernel Types
class KernelType(Enum):
    """Kernel function types for regression."""
    GAUSSIAN = "gaussian"  # Standard normal kernel
    EPANECHNIKOV = "epanechnikov"  # Parabolic kernel
    TRIANGULAR = "triangular"  # Triangular kernel
    UNIFORM = "uniform"  # Uniform kernel

# Bandwidth Selection Methods
class BandwidthMethod(Enum):
    """Bandwidth selection methods."""
    SILVERMAN = "silverman"  # Silverman's rule of thumb
    SCOTT = "scott"  # Scott's rule
    CROSS_VALIDATION = "cross_validation"  # Leave-one-out CV
    MANUAL = "manual"  # User-specified

# Mean Reversion Signal Types
class SignalType(Enum):
    """Mean reversion signal types."""
    BUY = "buy"  # Price below lower envelope
    SELL = "sell"  # Price above upper envelope
    HOLD = "hold"  # Price within envelope
    STRONG_BUY = "strong_buy"  # Price far below lower envelope
    STRONG_SELL = "strong_sell"  # Price far above upper envelope

# Default Configuration
DEFAULT_BANDWIDTH = 0.1  # Default bandwidth parameter
DEFAULT_SIGMA_LEVEL = 1.0  # Default sigma level for envelope
MIN_OBSERVATIONS = 20  # Minimum observations for regression

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class KernelRegressionResult:
    """Results from kernel regression."""
    trend: np.ndarray  # Estimated trend values
    residuals: np.ndarray  # Residuals (actual - trend)
    bandwidth: float  # Bandwidth used
    kernel_type: KernelType  # Kernel function used
    bandwidth_method: BandwidthMethod  # Bandwidth selection method
    cv_score: Optional[float] = None  # Cross-validation score
    fit_time: float = 0.0  # Time to fit model (seconds)

@dataclass
class EnvelopeAnalysis:
    """Envelope analysis for mean reversion."""
    upper_envelope: np.ndarray  # Upper envelope (trend + σ)
    lower_envelope: np.ndarray  # Lower envelope (trend - σ)
    sigma: float  # Standard deviation of residuals
    z_scores: np.ndarray  # Z-scores of price relative to trend
    mean_reversion_potential: float  # Potential for mean reversion

@dataclass
class MeanReversionSignal:
    """Mean reversion trading signal."""
    timestamp: datetime
    signal_type: SignalType  # Type of signal
    price: float  # Current price
    trend: float  # Trend value at current point
    upper_envelope: float  # Upper envelope
    lower_envelope: float  # Lower envelope
    z_score: float  # Z-score of price
    confidence: float  # Confidence in signal
    expected_reversion: Optional[float] = None  # Expected reversion amount
    reason: str = ""  # Explanation for signal

@dataclass
class LocalTrendMetrics:
    """Local trend metrics at each point."""
    trend_strength: float  # Strength of local trend (0-1)
    trend_direction: str  # "up", "down", or "flat"
    curvature: float  # Second derivative (curvature)
    momentum: float  # First derivative (momentum)
    volatility: float  # Local volatility

# ==============================================================================
# KERNEL FUNCTIONS
# ==============================================================================

def gaussian_kernel(u: np.ndarray) -> np.ndarray:
    """
    Gaussian kernel function.
    
    K(u) = (1/√(2π)) * exp(-u²/2)
    
    Args:
        u: Normalized distances
        
    Returns:
        Kernel weights
    """
    return (1.0 / np.sqrt(2.0 * np.pi)) * np.exp(-0.5 * u**2)

def epanechnikov_kernel(u: np.ndarray) -> np.ndarray:
    """
    Epanechnikov kernel function (optimal MSE).
    
    K(u) = 0.75 * (1 - u²) for |u| ≤ 1, else 0
    
    Args:
        u: Normalized distances
        
    Returns:
        Kernel weights
    """
    weights = np.zeros_like(u)
    mask = np.abs(u) <= 1.0
    weights[mask] = 0.75 * (1.0 - u[mask]**2)
    return weights

def triangular_kernel(u: np.ndarray) -> np.ndarray:
    """
    Triangular kernel function.
    
    K(u) = (1 - |u|) for |u| ≤ 1, else 0
    
    Args:
        u: Normalized distances
        
    Returns:
        Kernel weights
    """
    weights = np.zeros_like(u)
    mask = np.abs(u) <= 1.0
    weights[mask] = 1.0 - np.abs(u[mask])
    return weights

def uniform_kernel(u: np.ndarray) -> np.ndarray:
    """
    Uniform kernel function.
    
    K(u) = 0.5 for |u| ≤ 1, else 0
    
    Args:
        u: Normalized distances
        
    Returns:
        Kernel weights
    """
    weights = np.zeros_like(u)
    mask = np.abs(u) <= 1.0
    weights[mask] = 0.5
    return weights

# Kernel function mapping
KERNEL_FUNCTIONS = {
    KernelType.GAUSSIAN: gaussian_kernel,
    KernelType.EPANECHNIKOV: epanechnikov_kernel,
    KernelType.TRIANGULAR: triangular_kernel,
    KernelType.UNIFORM: uniform_kernel
}

# ==============================================================================
# MAIN CLASS
# ==============================================================================

class KernelRegression:
    """
    Kernel Regression (Nadaraya-Watson Estimator) for Trend Estimation.
    
    Inspired by Renaissance Technologies' quantitative framework, this module
    implements non-parametric kernel regression for smooth trend estimation
    and mean reversion analysis.
    
    Key Concepts:
        - Nadaraya-Watson Estimator: Weighted average of nearby points
        - Kernel Function: Determines weight decay with distance
        - Bandwidth: Controls smoothness (larger = smoother)
        - Mean Reversion: Price tends to return to trend
        - Envelope: Dynamic bands around trend for signals
    
    Example:
        >>> kr = KernelRegression(kernel_type=KernelType.GAUSSIAN)
        >>> kr.fit(prices, bandwidth_method=BandwidthMethod.SILVERMAN)
        >>> signal = kr.generate_signal(current_price)
        >>> print(f"Signal: {signal.signal_type.value}, Z-score: {signal.z_score:.2f}")
    """
    
    def __init__(self,
                 kernel_type: KernelType = KernelType.GAUSSIAN,
                 bandwidth_method: BandwidthMethod = BandwidthMethod.SILVERMAN,
                 bandwidth: float = DEFAULT_BANDWIDTH):
        """
        Initialize Kernel Regression model.
        
        Args:
            kernel_type: Type of kernel function
            bandwidth_method: Method for selecting bandwidth
            bandwidth: Manual bandwidth (if method is MANUAL)
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.kernel_type = kernel_type
        self.bandwidth_method = bandwidth_method
        self.bandwidth = bandwidth
        
        # Kernel function
        self.kernel_func = KERNEL_FUNCTIONS.get(kernel_type, gaussian_kernel)
        
        # Model storage
        self.result: Optional[KernelRegressionResult] = None
        self.envelope: Optional[EnvelopeAnalysis] = None
        self.is_fitted: bool = False
        
        # Data storage
        self.x: Optional[np.ndarray] = None  # Input values (time)
        self.y: Optional[np.ndarray] = None  # Output values (price)
        self.n_observations: int = 0
        
        self.logger.info(
            f"KernelRegression initialized: kernel={kernel_type.value}, "
            f"bandwidth_method={bandwidth_method.value}"
        )
    
    def fit(self, 
           prices: pd.Series,
           bandwidth_method: Optional[BandwidthMethod] = None,
           bandwidth: Optional[float] = None,
           optimize_bandwidth: bool = True) -> KernelRegressionResult:
        """
        Fit kernel regression model to price data.
        
        Args:
            prices: Time series of prices
            bandwidth_method: Bandwidth selection method (overrides init)
            bandwidth: Manual bandwidth (if method is MANUAL)
            optimize_bandwidth: Whether to optimize bandwidth via CV
            
        Returns:
            KernelRegressionResult with fitted model
        """
        try:
            self.logger.info("Fitting Kernel Regression model...")
            
            # Validate input
            if prices is None or len(prices) < MIN_OBSERVATIONS:
                self.logger.error(
                    f"Insufficient data: need at least {MIN_OBSERVATIONS} observations"
                )
                raise ValueError(f"Need at least {MIN_OBSERVATIONS} observations")
            
            # Store data
            self.y = prices.values.astype(float)
            self.n_observations = len(self.y)
            self.x = np.arange(self.n_observations)  # Time indices
            
            # Update configuration
            if bandwidth_method is not None:
                self.bandwidth_method = bandwidth_method
            if bandwidth is not None:
                self.bandwidth = bandwidth
            
            # Select bandwidth
            if self.bandwidth_method == BandwidthMethod.SILVERMAN:
                self.bandwidth = self._silverman_bandwidth(self.y)
            elif self.bandwidth_method == BandwidthMethod.SCOTT:
                self.bandwidth = self._scott_bandwidth(self.y)
            elif self.bandwidth_method == BandwidthMethod.CROSS_VALIDATION and optimize_bandwidth:
                self.bandwidth = self._optimize_bandwidth_cv(self.x, self.y)
            elif self.bandwidth_method == BandwidthMethod.MANUAL:
                # Use provided bandwidth
                pass
            
            # Fit model
            start_time = datetime.now()
            trend = self._nadaraya_watson(self.x, self.y, self.bandwidth)
            end_time = datetime.now()
            fit_time = (end_time - start_time).total_seconds()
            
            # Calculate residuals
            residuals = self.y - trend
            
            # Calculate CV score if optimized
            cv_score = None
            if optimize_bandwidth and self.bandwidth_method == BandwidthMethod.CROSS_VALIDATION:
                cv_score = self._calculate_cv_score(self.x, self.y, self.bandwidth)
            
            # Store result
            self.result = KernelRegressionResult(
                trend=trend,
                residuals=residuals,
                bandwidth=self.bandwidth,
                kernel_type=self.kernel_type,
                bandwidth_method=self.bandwidth_method,
                cv_score=cv_score,
                fit_time=fit_time
            )
            
            # Calculate envelope
            self.envelope = self._calculate_envelope(trend, residuals)
            
            # Mark as fitted
            self.is_fitted = True
            
            self.logger.info(
                f"Kernel Regression fitted: bandwidth={self.bandwidth:.4f}, "
                f"fit_time={fit_time:.3f}s"
            )
            
            return self.result
            
        except Exception as e:
            self.error_handler.handle_error(e, "KernelRegression.fit")
            raise
    
    def _nadaraya_watson(self, 
                        x: np.ndarray, 
                        y: np.ndarray, 
                        h: float) -> np.ndarray:
        """
        Nadaraya-Watson kernel regression estimator.
        
        ŷ(x) = Σ K((x - xi)/h) * yi / Σ K((x - xi)/h)
        
        Args:
            x: Input values (time)
            y: Output values (price)
            h: Bandwidth
            
        Returns:
            Estimated trend values
        """
        n = len(x)
        trend = np.zeros(n)
        
        for i in range(n):
            # Calculate normalized distances
            u = (x - x[i]) / h
            
            # Calculate kernel weights
            weights = self.kernel_func(u)
            
            # Normalize weights
            weight_sum = np.sum(weights)
            
            if weight_sum > 0:
                # Weighted average
                trend[i] = np.sum(weights * y) / weight_sum
            else:
                # Fallback to nearest neighbor
                trend[i] = y[i]
        
        return trend
    
    def _silverman_bandwidth(self, y: np.ndarray) -> float:
        """
        Silverman's rule of thumb for bandwidth selection.
        
        h = 0.9 * min(σ, IQR/1.34) * n^(-1/5)
        
        Args:
            y: Data values
            
        Returns:
            Bandwidth
        """
        n = len(y)
        std_dev = np.std(y, ddof=1)
        
        # Interquartile range
        q75, q25 = np.percentile(y, [75, 25])
        iqr = q75 - q25
        
        # Silverman's rule
        h = 0.9 * min(std_dev, iqr / 1.34) * (n ** (-1.0 / 5.0))
        
        return h
    
    def _scott_bandwidth(self, y: np.ndarray) -> float:
        """
        Scott's rule for bandwidth selection.
        
        h = 1.06 * σ * n^(-1/5)
        
        Args:
            y: Data values
            
        Returns:
            Bandwidth
        """
        n = len(y)
        std_dev = np.std(y, ddof=1)
        
        # Scott's rule
        h = 1.06 * std_dev * (n ** (-1.0 / 5.0))
        
        return h
    
    def _optimize_bandwidth_cv(self, 
                             x: np.ndarray, 
                             y: np.ndarray) -> float:
        """
        Optimize bandwidth using leave-one-out cross-validation.
        
        Minimizes: CV(h) = (1/n) * Σ (yi - ŷ^(-i)(xi))²
        
        Args:
            x: Input values
            y: Output values
            
        Returns:
            Optimal bandwidth
        """
        self.logger.debug("Optimizing bandwidth via cross-validation...")
        
        # Define objective function (negative CV score)
        def objective(h):
            return self._calculate_cv_score(x, y, h)
        
        # Optimize bandwidth (search range: 0.01 to 1.0)
        result = minimize_scalar(
            objective,
            bounds=(0.01, 1.0),
            method='bounded'
        )
        
        if result.success:
            optimal_h = result.x
            self.logger.debug(f"Optimal bandwidth: {optimal_h:.4f}")
            return optimal_h
        else:
            self.logger.warning("Bandwidth optimization failed, using Silverman's rule")
            return self._silverman_bandwidth(y)
    
    def _calculate_cv_score(self, 
                          x: np.ndarray, 
                          y: np.ndarray, 
                          h: float) -> float:
        """
        Calculate leave-one-out cross-validation score.
        
        Args:
            x: Input values
            y: Output values
            h: Bandwidth
            
        Returns:
            CV score (MSE)
        """
        n = len(x)
        cv_errors = []
        
        for i in range(n):
            # Leave out observation i
            x_train = np.delete(x, i)
            y_train = np.delete(y, i)
            x_test = x[i]
            y_test = y[i]
            
            # Predict using Nadaraya-Watson
            u = (x_train - x_test) / h
            weights = self.kernel_func(u)
            weight_sum = np.sum(weights)
            
            if weight_sum > 0:
                y_pred = np.sum(weights * y_train) / weight_sum
            else:
                y_pred = y_train[-1]  # Fallback
            
            # Calculate error
            cv_errors.append((y_test - y_pred) ** 2)
        
        # Return mean squared error
        return np.mean(cv_errors)
    
    def _calculate_envelope(self, 
                          trend: np.ndarray, 
                          residuals: np.ndarray,
                          sigma_level: float = DEFAULT_SIGMA_LEVEL) -> EnvelopeAnalysis:
        """
        Calculate envelope around trend for mean reversion signals.
        
        Envelope = trend ± σ_level * σ_residuals
        
        Args:
            trend: Trend values
            residuals: Residuals
            sigma_level: Number of standard deviations for envelope
            
        Returns:
            EnvelopeAnalysis
        """
        # Calculate standard deviation of residuals
        sigma = np.std(residuals, ddof=1)
        
        # Calculate envelope
        upper_envelope = trend + sigma_level * sigma
        lower_envelope = trend - sigma_level * sigma
        
        # Calculate z-scores
        z_scores = residuals / sigma
        
        # Calculate mean reversion potential (inverse of absolute z-score)
        mean_reversion_potential = 1.0 / (1.0 + np.abs(z_scores))
        
        return EnvelopeAnalysis(
            upper_envelope=upper_envelope,
            lower_envelope=lower_envelope,
            sigma=sigma,
            z_scores=z_scores,
            mean_reversion_potential=mean_reversion_potential
        )
    
    def predict(self, x_new: np.ndarray) -> np.ndarray:
        """
        Predict trend values at new points.
        
        Args:
            x_new: New input values
            
        Returns:
            Predicted trend values
        """
        if not self.is_fitted or self.result is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        return self._nadaraya_watson(x_new, self.y, self.bandwidth)
    
    def generate_signal(self, 
                       current_price: float,
                       current_index: int = -1,
                       sigma_level: float = DEFAULT_SIGMA_LEVEL) -> MeanReversionSignal:
        """
        Generate mean reversion trading signal.
        
        Args:
            current_price: Current price
            current_index: Index in time series (default: last)
            sigma_level: Sigma level for envelope
            
        Returns:
            MeanReversionSignal
        """
        if not self.is_fitted or self.result is None or self.envelope is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Get current values
        if current_index == -1:
            current_index = self.n_observations - 1
        
        trend = self.result.trend[current_index]
        upper = self.envelope.upper_envelope[current_index]
        lower = self.envelope.lower_envelope[current_index]
        z_score = self.envelope.z_scores[current_index]
        
        # Determine signal type based on price position
        if current_price > upper * 1.02:  # > 2% above upper envelope
            signal_type = SignalType.STRONG_SELL
            reason = f"Price {current_price:.2f} > 2% above upper envelope {upper:.2f}"
        elif current_price > upper:
            signal_type = SignalType.SELL
            reason = f"Price {current_price:.2f} above upper envelope {upper:.2f}"
        elif current_price < lower * 0.98:  # < 2% below lower envelope
            signal_type = SignalType.STRONG_BUY
            reason = f"Price {current_price:.2f} < 2% below lower envelope {lower:.2f}"
        elif current_price < lower:
            signal_type = SignalType.BUY
            reason = f"Price {current_price:.2f} below lower envelope {lower:.2f}"
        else:
            signal_type = SignalType.HOLD
            reason = f"Price {current_price:.2f} within envelope [{lower:.2f}, {upper:.2f}]"
        
        # Calculate confidence based on z-score
        confidence = min(1.0, abs(z_score) / 2.0)
        
        # Calculate expected reversion (distance to trend)
        expected_reversion = abs(current_price - trend)
        
        return MeanReversionSignal(
            timestamp=datetime.now(),
            signal_type=signal_type,
            price=current_price,
            trend=trend,
            upper_envelope=upper,
            lower_envelope=lower,
            z_score=z_score,
            confidence=confidence,
            expected_reversion=expected_reversion,
            reason=reason
        )
    
    def calculate_local_trend_metrics(self) -> LocalTrendMetrics:
        """
        Calculate local trend metrics.
        
        Returns:
            LocalTrendMetrics
        """
        if not self.is_fitted or self.result is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        trend = self.result.trend
        residuals = self.result.residuals
        
        # First derivative (momentum)
        momentum = np.gradient(trend)
        
        # Second derivative (curvature)
        curvature = np.gradient(momentum)
        
        # Trend strength (normalized momentum)
        trend_strength = np.abs(momentum) / (np.std(residuals) + 1e-10)
        trend_strength = np.clip(trend_strength, 0, 1)
        
        # Trend direction
        avg_momentum = np.mean(momentum[-5:])  # Last 5 periods
        if avg_momentum > 0.01:
            direction = "up"
        elif avg_momentum < -0.01:
            direction = "down"
        else:
            direction = "flat"
        
        # Local volatility
        volatility = np.std(residuals[-20:])  # Last 20 periods
        
        return LocalTrendMetrics(
            trend_strength=np.mean(trend_strength),
            trend_direction=direction,
            curvature=np.mean(curvature[-5:]),
            momentum=avg_momentum,
            volatility=volatility
        )
    
    def get_envelope_bounds(self, 
                          sigma_level: float = DEFAULT_SIGMA_LEVEL) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get envelope bounds for visualization or analysis.
        
        Args:
            sigma_level: Number of standard deviations
            
        Returns:
            Tuple of (upper_envelope, lower_envelope)
        """
        if not self.is_fitted or self.envelope is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        sigma = self.envelope.sigma
        trend = self.result.trend
        
        upper = trend + sigma_level * sigma
        lower = trend - sigma_level * sigma
        
        return upper, lower
    
    def get_fit_summary(self) -> Dict[str, Any]:
        """
        Get summary of fitted model.
        
        Returns:
            Dictionary with fit summary
        """
        if not self.is_fitted or self.result is None:
            return {}
        
        return {
            'kernel_type': self.result.kernel_type.value,
            'bandwidth_method': self.result.bandwidth_method.value,
            'bandwidth': self.result.bandwidth,
            'n_observations': self.n_observations,
            'residual_std': np.std(self.result.residuals),
            'cv_score': self.result.cv_score,
            'fit_time': self.result.fit_time,
            'envelope_sigma': self.envelope.sigma if self.envelope else None,
            'mean_reversion_potential': np.mean(self.envelope.mean_reversion_potential) if self.envelope else None
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_sample_price_data(n_periods: int = 252, 
                            trend_strength: float = 0.001,
                            noise_std: float = 0.02) -> pd.Series:
    """
    Create sample price data for testing.
    
    Args:
        n_periods: Number of periods to generate
        trend_strength: Strength of underlying trend
        noise_std: Standard deviation of noise
        
    Returns:
        Series with sample prices
    """
    np.random.seed(42)
    
    # Generate prices with trend and noise
    dates = pd.date_range(end=datetime.now(), periods=n_periods, freq='D')
    
    # Generate returns with trend
    returns = np.random.normal(trend_strength, noise_std, n_periods)
    
    # Add some mean reversion
    for i in range(1, n_periods):
        if abs(returns[i-1]) > 2 * noise_std:
            returns[i] = -0.5 * returns[i-1]  # Partial mean reversion
    
    # Calculate prices
    prices = 100 * np.cumprod(1 + returns)
    
    return pd.Series(prices, index=dates, name='Price')


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("📈 SPYDER KERNEL REGRESSION")
    print("=" * 70)
    print("Nadaraya-Watson Estimator for Trend Estimation")
    print("Inspired by Renaissance Technologies")
    print()
    
    # Create sample data
    print("\n1. Creating sample price data...")
    prices = create_sample_price_data(n_periods=252)
    print(f"   Generated: {len(prices)} days of prices")
    print(f"   Price range: [{prices.min():.2f}, {prices.max():.2f}]")
    
    # Test different kernels
    kernels = [KernelType.GAUSSIAN, KernelType.EPANECHNIKOV, KernelType.TRIANGULAR]
    
    for kernel_type in kernels:
        print(f"\n2. Testing {kernel_type.value.upper()} kernel...")
        
        # Create kernel regression
        kr = KernelRegression(kernel_type=kernel_type)
        
        # Fit model
        result = kr.fit(prices, bandwidth_method=BandwidthMethod.SILVERMAN)
        
        print(f"   ✅ Model fitted")
        print(f"   Bandwidth: {result.bandwidth:.4f}")
        print(f"   Residual Std: {np.std(result.residuals):.4f}")
        print(f"   Fit Time: {result.fit_time:.3f}s")
        
        # Generate signal
        current_price = prices.iloc[-1]
        signal = kr.generate_signal(current_price)
        
        print(f"\n   Current Signal:")
        print(f"   Price: {signal.price:.2f}")
        print(f"   Trend: {signal.trend:.2f}")
        print(f"   Signal: {signal.signal_type.value.upper()}")
        print(f"   Z-Score: {signal.z_score:.2f}")
        print(f"   Confidence: {signal.confidence:.2%}")
        print(f"   Reason: {signal.reason}")
        
        # Get local trend metrics
        metrics = kr.calculate_local_trend_metrics()
        print(f"\n   Local Trend Metrics:")
        print(f"   Direction: {metrics.trend_direction}")
        print(f"   Strength: {metrics.trend_strength:.2f}")
        print(f"   Momentum: {metrics.momentum:.4f}")
        print(f"   Volatility: {metrics.volatility:.4f}")
        
        # Get fit summary
        summary = kr.get_fit_summary()
        print(f"\n   Fit Summary:")
        for key, value in summary.items():
            print(f"   {key}: {value}")
    
    print("\n" + "=" * 70)
    print("✅ Kernel Regression Test Completed Successfully")
    print("=" * 70)
