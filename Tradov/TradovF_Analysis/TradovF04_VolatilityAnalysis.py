#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovF_Analysis
Module: TradovF04_VolatilityAnalysis.py
Purpose: TRADOV - Automated TRAD Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    TRADOV - Automated TRAD Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta, UTC
from typing import Any
from enum import Enum, auto
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import math
import pandas as pd
import numpy as np
from scipy import stats
from arch import arch_model

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler

TRADING_DAYS_YEAR = 252
TRADING_HOURS_DAY = 6.5
MINUTES_PER_YEAR = TRADING_DAYS_YEAR * TRADING_HOURS_DAY * 60

# Standard windows for volatility
VOL_WINDOWS = [5, 10, 20, 30, 60, 90]
DEFAULT_WINDOW = 20

# Volatility regimes
LOW_VOL_THRESHOLD = 0.10      # 10% annualized
NORMAL_VOL_LOW = 0.10
NORMAL_VOL_HIGH = 0.20
HIGH_VOL_THRESHOLD = 0.25      # 25% annualized
EXTREME_VOL_THRESHOLD = 0.35   # 35% annualized

# VIX levels
VIX_LOW = 12
VIX_NORMAL_LOW = 12
VIX_NORMAL_HIGH = 20
VIX_HIGH = 25
VIX_EXTREME = 35

# GARCH parameters
GARCH_P = 1  # GARCH lag order
GARCH_Q = 1  # ARCH lag order
MIN_GARCH_OBSERVATIONS = 100

# Correlation parameters
CORRELATION_WINDOW = 20
MIN_CORRELATION_OBSERVATIONS = 10

# ==============================================================================
# ENUMS
# ==============================================================================
class VolatilityMethod(Enum):
    """Volatility calculation methods"""
    CLOSE_TO_CLOSE = auto()
    PARKINSON = auto()
    GARMAN_KLASS = auto()
    ROGERS_SATCHELL = auto()
    YANG_ZHANG = auto()
    GARCH = auto()
    EWMA = auto()

class VolatilityRegime(Enum):
    """Volatility regime classification"""
    LOW = auto()
    NORMAL = auto()
    ELEVATED = auto()
    HIGH = auto()
    EXTREME = auto()

class VolatilityTrend(Enum):
    """Volatility trend direction"""
    INCREASING = auto()
    STABLE = auto()
    DECREASING = auto()
    VOLATILE = auto()

class VIXRegime(Enum):
    """VIX regime classification"""
    COMPLACENT = auto()
    NORMAL = auto()
    ANXIOUS = auto()
    FEARFUL = auto()
    PANIC = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class VolatilityMetrics:
    """Comprehensive volatility metrics"""
    current_volatility: float
    historical_volatilities: dict[int, float]  # window -> volatility
    volatility_of_volatility: float
    volatility_regime: VolatilityRegime
    volatility_trend: VolatilityTrend
    volatility_percentile: float
    term_structure: dict[int, float]
    method_used: VolatilityMethod
    calculation_time: datetime

class VIXAnalysis:
    """VIX correlation analysis"""
    vix_level: float
    vix_regime: VIXRegime
    spy_vix_correlation: float
    vix_trend: float
    vix_percentile: float
    term_structure_slope: float
    contango: bool
    risk_on_off: str  # 'risk-on' or 'risk-off'

class VolatilityForecast:
    """Volatility forecast"""
    forecast_horizon: int  # days
    point_forecast: float
    confidence_intervals: dict[float, tuple[float, float]]  # level -> (lower, upper)
    forecast_method: str
    model_parameters: dict[str, Any]

class VolatilityAnalysisResult:
    """Complete volatility analysis result"""
    metrics: VolatilityMetrics
    vix_analysis: VIXAnalysis | None
    forecasts: dict[int, VolatilityForecast]  # horizon -> forecast
    regime_probabilities: dict[VolatilityRegime, float]
    trading_implications: list[str]

# ==============================================================================
# VOLATILITY ANALYZER CLASS
# ==============================================================================
class VolatilityAnalyzer:
    """
    Analyzes market volatility using multiple methods.

    Provides comprehensive volatility analysis including historical volatility,
    GARCH modeling, VIX correlation, and regime identification.
    """

    def __init__(self):
        """Initialize volatility analyzer"""
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()

        # Configuration
        self.default_method = VolatilityMethod.YANG_ZHANG
        self.use_garch = True
        self.analyze_vix = True

        # Historical data storage
        self.volatility_history: list[tuple[datetime, float]] = []
        self.regime_history: list[tuple[datetime, VolatilityRegime]] = []

        # Suppress arch warnings
        warnings.filterwarnings('ignore', category=RuntimeWarning)

        self.logger.info("VolatilityAnalyzer initialized")

    # ==========================================================================
    # MAIN ANALYSIS
    # ==========================================================================
    def analyze(
        self,
        data: pd.DataFrame,
        vix_data: pd.DataFrame | None = None
    ) -> VolatilityAnalysisResult:
        """
        Perform comprehensive volatility analysis.

        Args:
            data: OHLCV DataFrame for TRAD
            vix_data: Optional VIX data

        Returns:
            Complete volatility analysis
        """
        try:
            # Calculate volatility metrics
            metrics = self.calculate_volatility_metrics(data)

            # VIX analysis if available
            vix_analysis = None
            if vix_data is not None and self.analyze_vix:
                vix_analysis = self._analyze_vix(data, vix_data)

            # Generate forecasts
            forecasts = {}
            if self.use_garch and len(data) >= MIN_GARCH_OBSERVATIONS:
                for horizon in [1, 5, 10]:
                    forecast = self._forecast_volatility_garch(data, horizon)
                    if forecast:
                        forecasts[horizon] = forecast

            # Calculate regime probabilities
            regime_probs = self._calculate_regime_probabilities(metrics, vix_analysis)

            # Generate trading implications
            implications = self._generate_trading_implications(metrics, vix_analysis, forecasts)

            # Update history
            self._update_history(metrics)

            return VolatilityAnalysisResult(
                metrics=metrics,
                vix_analysis=vix_analysis,
                forecasts=forecasts,
                regime_probabilities=regime_probs,
                trading_implications=implications
            )

        except Exception as e:
            self.logger.error("Error in volatility analysis: %s", e)
            self.error_handler.handle_error(e, "analyze")
            return self._get_default_analysis()

    def calculate_volatility(
        self,
        data: pd.DataFrame,
        window: int = DEFAULT_WINDOW,
        method: VolatilityMethod | None = None
    ) -> dict[str, float]:
        """
        Calculate volatility using specified method.

        Args:
            data: OHLCV DataFrame
            window: Lookback window
            method: Volatility calculation method

        Returns:
            Dictionary with volatility metrics
        """
        method = method or self.default_method

        if method == VolatilityMethod.CLOSE_TO_CLOSE:
            vol = self._close_to_close_volatility(data, window)
        elif method == VolatilityMethod.PARKINSON:
            vol = self._parkinson_volatility(data, window)
        elif method == VolatilityMethod.GARMAN_KLASS:
            vol = self._garman_klass_volatility(data, window)
        elif method == VolatilityMethod.ROGERS_SATCHELL:
            vol = self._rogers_satchell_volatility(data, window)
        elif method == VolatilityMethod.YANG_ZHANG:
            vol = self._yang_zhang_volatility(data, window)
        elif method == VolatilityMethod.EWMA:
            vol = self._ewma_volatility(data, window)
        else:
            vol = self._close_to_close_volatility(data, window)

        return {
            'volatility': vol,
            'annualized': vol * math.sqrt(TRADING_DAYS_YEAR),
            'method': method.name,
            'window': window
        }

    def calculate_volatility_metrics(self, data: pd.DataFrame) -> VolatilityMetrics:
        """Calculate comprehensive volatility metrics"""
        # Calculate volatility using multiple windows
        historical_vols = {}
        for window in VOL_WINDOWS:
            if len(data) >= window:
                vol_data = self.calculate_volatility(data, window)
                historical_vols[window] = vol_data['annualized']

        # Current volatility (20-day)
        current_vol = historical_vols.get(20, 0.15)  # Default 15%

        # Volatility of volatility
        if len(self.volatility_history) >= 20:
            recent_vols = [v for _, v in self.volatility_history[-20:]]
            vol_of_vol = np.std(recent_vols) if len(recent_vols) > 1 else 0
        else:
            vol_of_vol = 0.05  # Default 5%

        # Volatility regime
        regime = self._classify_volatility_regime(current_vol)

        # Volatility trend
        trend = self._analyze_volatility_trend(historical_vols)

        # Volatility percentile
        percentile = self._calculate_volatility_percentile(current_vol)

        # Term structure
        term_structure = self._calculate_term_structure(historical_vols)

        return VolatilityMetrics(
            current_volatility=current_vol,
            historical_volatilities=historical_vols,
            volatility_of_volatility=vol_of_vol,
            volatility_regime=regime,
            volatility_trend=trend,
            volatility_percentile=percentile,
            term_structure=term_structure,
            method_used=self.default_method,
            calculation_time=datetime.now(UTC)
        )

    # ==========================================================================
    # VOLATILITY CALCULATION METHODS
    # ==========================================================================
    def _close_to_close_volatility(self, data: pd.DataFrame, window: int) -> float:
        """Traditional close-to-close volatility"""
        if len(data) < window:
            return 0.15 / math.sqrt(TRADING_DAYS_YEAR)  # Default

        returns = np.log(data['close'] / data['close'].shift(1))
        return float(returns.rolling(window).std().iloc[-1])

    def _parkinson_volatility(self, data: pd.DataFrame, window: int) -> float:
        """Parkinson volatility estimator"""
        if len(data) < window:
            return 0.15 / math.sqrt(TRADING_DAYS_YEAR)

        hl = np.log(data['high'] / data['low'])
        factor = 1 / (4 * math.log(2))

        vol = np.sqrt(factor * (hl ** 2).rolling(window).mean()).iloc[-1]
        return float(vol)

    def _garman_klass_volatility(self, data: pd.DataFrame, window: int) -> float:
        """Garman-Klass volatility estimator"""
        if len(data) < window:
            return 0.15 / math.sqrt(TRADING_DAYS_YEAR)

        hl = np.log(data['high'] / data['low'])
        co = np.log(data['close'] / data['open'])

        vol = np.sqrt(
            0.5 * (hl ** 2).rolling(window).mean() -
            (2 * math.log(2) - 1) * (co ** 2).rolling(window).mean()
        ).iloc[-1]

        return float(vol)

    def _rogers_satchell_volatility(self, data: pd.DataFrame, window: int) -> float:
        """Rogers-Satchell volatility estimator"""
        if len(data) < window:
            return 0.15 / math.sqrt(TRADING_DAYS_YEAR)

        hc = np.log(data['high'] / data['close'])
        ho = np.log(data['high'] / data['open'])
        lc = np.log(data['low'] / data['close'])
        lo = np.log(data['low'] / data['open'])

        rs = np.sqrt((hc * ho + lc * lo).rolling(window).mean()).iloc[-1]
        return float(rs)

    def _yang_zhang_volatility(self, data: pd.DataFrame, window: int) -> float:
        """Yang-Zhang volatility estimator"""
        if len(data) < window:
            return 0.15 / math.sqrt(TRADING_DAYS_YEAR)

        # Overnight volatility
        oc = np.log(data['open'] / data['close'].shift(1))
        overnight_var = (oc ** 2).rolling(window).mean()

        # Open-to-close volatility
        co = np.log(data['close'] / data['open'])
        open_close_var = (co ** 2).rolling(window).mean()

        # Rogers-Satchell component
        rs_vol = self._rogers_satchell_volatility(data, window)

        # Combine components (simplified)
        k = 0.34 / (1 + (window + 1) / (window - 1))

        yz_var = overnight_var + k * open_close_var + (1 - k) * rs_vol ** 2
        yz_vol = np.sqrt(yz_var).iloc[-1]

        return float(yz_vol)

    def _ewma_volatility(self, data: pd.DataFrame, window: int) -> float:
        """Exponentially weighted moving average volatility"""
        if len(data) < window:
            return 0.15 / math.sqrt(TRADING_DAYS_YEAR)

        returns = np.log(data['close'] / data['close'].shift(1))

        # Lambda parameter (RiskMetrics uses 0.94)
        lambda_param = 0.94

        # EWMA variance
        ewma_var = returns.ewm(alpha=1-lambda_param, min_periods=window).var()
        ewma_vol = np.sqrt(ewma_var).iloc[-1]

        return float(ewma_vol)

    # ==========================================================================
    # GARCH MODELING
    # ==========================================================================
    def _forecast_volatility_garch(
        self,
        data: pd.DataFrame,
        horizon: int
    ) -> VolatilityForecast | None:
        """Forecast volatility using GARCH model"""
        try:
            # Prepare returns
            returns = 100 * data['close'].pct_change().dropna()

            if len(returns) < MIN_GARCH_OBSERVATIONS:
                return None

            # Fit GARCH model
            model = arch_model(returns, vol='Garch', p=GARCH_P, q=GARCH_Q)
            res = model.fit(disp='off', show_warning=False)

            # Generate forecast
            forecasts = res.forecast(horizon=horizon)

            # Extract variance forecasts
            variance_forecast = forecasts.variance.iloc[-1].values
            vol_forecast = np.sqrt(variance_forecast) / 100  # Convert back from percentage

            # Annualize
            annual_vol_forecast = vol_forecast * math.sqrt(TRADING_DAYS_YEAR)

            # Confidence intervals (simplified)
            ci_90 = (
                annual_vol_forecast * 0.8,
                annual_vol_forecast * 1.2
            )
            ci_95 = (
                annual_vol_forecast * 0.75,
                annual_vol_forecast * 1.25
            )

            return VolatilityForecast(
                forecast_horizon=horizon,
                point_forecast=float(annual_vol_forecast[horizon-1]),
                confidence_intervals={
                    0.90: ci_90,
                    0.95: ci_95
                },
                forecast_method='GARCH(1,1)',
                model_parameters={
                    'omega': float(res.params['omega']),
                    'alpha': float(res.params['alpha[1]']),
                    'beta': float(res.params['beta[1]'])
                }
            )

        except Exception as e:
            self.logger.error("GARCH forecast error: %s", e)
            return None

    # ==========================================================================
    # VIX ANALYSIS
    # ==========================================================================
    def _analyze_vix(
        self,
        spy_data: pd.DataFrame,
        vix_data: pd.DataFrame
    ) -> VIXAnalysis | None:
        """Analyze VIX and its relationship with TRAD"""
        try:
            # Align data
            aligned = pd.DataFrame({
                'spy_close': spy_data['close'],
                'vix_close': vix_data['close']
            }).dropna()

            if len(aligned) < MIN_CORRELATION_OBSERVATIONS:
                return None

            # Current VIX level
            vix_level = float(aligned['vix_close'].iloc[-1])

            # VIX regime
            vix_regime = self._classify_vix_regime(vix_level)

            # TRAD-VIX correlation
            correlation = aligned['spy_close'].pct_change().corr(
                aligned['vix_close'].pct_change()
            )

            # VIX trend
            if len(aligned) >= 20:
                vix_returns = aligned['vix_close'].pct_change().dropna()
                vix_trend = float(vix_returns.rolling(20).mean().iloc[-1])
            else:
                vix_trend = 0.0

            # VIX percentile
            vix_percentile = stats.percentileofscore(
                aligned['vix_close'].values,
                vix_level
            )

            # Term structure (would need VIX futures data)
            term_structure_slope = 0.0  # Placeholder

            # Contango/Backwardation (simplified)
            contango = vix_level < 20  # Simplified assumption

            # Risk on/off
            risk_on_off = 'risk-on' if vix_level < 20 else 'risk-off'

            return VIXAnalysis(
                vix_level=vix_level,
                vix_regime=vix_regime,
                spy_vix_correlation=float(correlation),
                vix_trend=vix_trend,
                vix_percentile=vix_percentile,
                term_structure_slope=term_structure_slope,
                contango=contango,
                risk_on_off=risk_on_off
            )

        except Exception as e:
            self.logger.error("VIX analysis error: %s", e)
            return None

    # ==========================================================================
    # REGIME ANALYSIS
    # ==========================================================================
    def _classify_volatility_regime(self, volatility: float) -> VolatilityRegime:
        """Classify volatility regime"""
        if volatility < LOW_VOL_THRESHOLD:
            return VolatilityRegime.LOW
        elif volatility < NORMAL_VOL_HIGH:
            return VolatilityRegime.NORMAL
        elif volatility < HIGH_VOL_THRESHOLD:
            return VolatilityRegime.ELEVATED
        elif volatility < EXTREME_VOL_THRESHOLD:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME

    def _classify_vix_regime(self, vix_level: float) -> VIXRegime:
        """Classify VIX regime"""
        if vix_level < VIX_LOW:
            return VIXRegime.COMPLACENT
        elif vix_level < VIX_NORMAL_HIGH:
            return VIXRegime.NORMAL
        elif vix_level < VIX_HIGH:
            return VIXRegime.ANXIOUS
        elif vix_level < VIX_EXTREME:
            return VIXRegime.FEARFUL
        else:
            return VIXRegime.PANIC

    def _analyze_volatility_trend(
        self,
        historical_vols: dict[int, float]
    ) -> VolatilityTrend:
        """Analyze volatility trend"""
        if len(historical_vols) < 2:
            return VolatilityTrend.STABLE

        # Get short-term and long-term volatilities
        short_windows = [w for w in [5, 10] if w in historical_vols]
        long_windows = [w for w in [20, 30, 60] if w in historical_vols]

        if not short_windows or not long_windows:
            return VolatilityTrend.STABLE

        short_vol = sum(historical_vols[w] for w in short_windows) / len(short_windows)
        long_vol = sum(historical_vols[w] for w in long_windows) / len(long_windows)

        # Calculate trend
        ratio = short_vol / long_vol

        if ratio > 1.2:
            return VolatilityTrend.INCREASING
        elif ratio < 0.8:
            return VolatilityTrend.DECREASING
        else:
            # Check volatility of volatility
            vols = list(historical_vols.values())
            cv = np.std(vols) / np.mean(vols) if np.mean(vols) > 0 else 0

            if cv > 0.3:
                return VolatilityTrend.VOLATILE
            else:
                return VolatilityTrend.STABLE

    def _calculate_volatility_percentile(self, current_vol: float) -> float:
        """Calculate volatility percentile based on history"""
        if len(self.volatility_history) < 20:
            # Default percentiles based on typical TRAD volatility
            if current_vol < 0.10:
                return 20.0
            elif current_vol < 0.15:
                return 40.0
            elif current_vol < 0.20:
                return 60.0
            elif current_vol < 0.25:
                return 80.0
            else:
                return 90.0

        historical_vols = [v for _, v in self.volatility_history]
        return float(stats.percentileofscore(historical_vols, current_vol))

    def _calculate_term_structure(
        self,
        historical_vols: dict[int, float]
    ) -> dict[int, float]:
        """Calculate volatility term structure"""
        term_structure = {}

        # Normalize to 30-day volatility
        base_vol = historical_vols.get(30, historical_vols.get(20, 0.15))

        for window, vol in historical_vols.items():
            if base_vol > 0:
                term_structure[window] = vol / base_vol
            else:
                term_structure[window] = 1.0

        return term_structure

    def _calculate_regime_probabilities(
        self,
        metrics: VolatilityMetrics,
        vix_analysis: VIXAnalysis | None
    ) -> dict[VolatilityRegime, float]:
        """Calculate regime probabilities"""
        probs = {regime: 0.0 for regime in VolatilityRegime}

        # Current regime gets base probability
        probs[metrics.volatility_regime] = 0.5

        # Adjust based on trend
        if metrics.volatility_trend == VolatilityTrend.INCREASING:
            # Higher probability of moving to higher regime
            if metrics.volatility_regime == VolatilityRegime.LOW:
                probs[VolatilityRegime.NORMAL] = 0.3
            elif metrics.volatility_regime == VolatilityRegime.NORMAL:
                probs[VolatilityRegime.ELEVATED] = 0.3
            elif metrics.volatility_regime == VolatilityRegime.ELEVATED:
                probs[VolatilityRegime.HIGH] = 0.3
        elif metrics.volatility_trend == VolatilityTrend.DECREASING:
            # Higher probability of moving to lower regime
            if metrics.volatility_regime == VolatilityRegime.EXTREME:
                probs[VolatilityRegime.HIGH] = 0.3
            elif metrics.volatility_regime == VolatilityRegime.HIGH:
                probs[VolatilityRegime.ELEVATED] = 0.3
            elif metrics.volatility_regime == VolatilityRegime.ELEVATED:
                probs[VolatilityRegime.NORMAL] = 0.3

        # Adjust based on VIX if available
        if vix_analysis:
            if vix_analysis.vix_regime == VIXRegime.PANIC:
                probs[VolatilityRegime.EXTREME] += 0.2
            elif vix_analysis.vix_regime == VIXRegime.COMPLACENT:
                probs[VolatilityRegime.LOW] += 0.2

        # Normalize probabilities
        total = sum(probs.values())
        if total > 0:
            probs = {k: v/total for k, v in probs.items()}

        return probs

    # ==========================================================================
    # TRADING IMPLICATIONS
    # ==========================================================================
    def _generate_trading_implications(
        self,
        metrics: VolatilityMetrics,
        vix_analysis: VIXAnalysis | None,
        forecasts: dict[int, VolatilityForecast]
    ) -> list[str]:
        """Generate trading implications from analysis"""
        implications = []

        # Regime-based implications
        if metrics.volatility_regime == VolatilityRegime.LOW:
            implications.append("Low volatility: Consider selling premium strategies (iron condors, credit spreads)")  # noqa: E501
            implications.append("Risk: Potential volatility expansion, keep positions small")
        elif metrics.volatility_regime == VolatilityRegime.NORMAL:
            implications.append("Normal volatility: Balanced approach, both premium selling and buying viable")  # noqa: E501
        elif metrics.volatility_regime == VolatilityRegime.ELEVATED:
            implications.append("Elevated volatility: Premium selling attractive, wider strikes recommended")  # noqa: E501
            implications.append("Consider volatility mean reversion strategies")
        elif metrics.volatility_regime == VolatilityRegime.HIGH:
            implications.append("High volatility: Focus on premium selling, avoid naked options")
            implications.append("Consider debit spreads for directional plays")
        else:  # EXTREME
            implications.append("Extreme volatility: Reduce position sizes significantly")
            implications.append("Focus on defined risk strategies only")

        # Trend-based implications
        if metrics.volatility_trend == VolatilityTrend.INCREASING:
            implications.append("Volatility rising: Consider long volatility strategies")
            implications.append("Widen strikes on credit spreads")
        elif metrics.volatility_trend == VolatilityTrend.DECREASING:
            implications.append("Volatility falling: Premium selling opportunities")
            implications.append("Consider volatility compression strategies")

        # VIX-based implications
        if vix_analysis:
            if vix_analysis.vix_regime == VIXRegime.COMPLACENT:
                implications.append("VIX low: Market complacency, consider hedges")
            elif vix_analysis.vix_regime == VIXRegime.PANIC:
                implications.append("VIX extreme: Wait for volatility to settle before entering new positions")  # noqa: E501

            if vix_analysis.contango:
                implications.append("VIX in contango: Favorable for short volatility strategies")
            else:
                implications.append("VIX in backwardation: Caution on short volatility")

        # Forecast-based implications
        if forecasts:
            # Get 5-day forecast if available
            forecast = forecasts.get(5)
            if forecast:
                if forecast.point_forecast > metrics.current_volatility * 1.1:
                    implications.append("Volatility forecast rising: Adjust position sizing down")
                elif forecast.point_forecast < metrics.current_volatility * 0.9:
                    implications.append("Volatility forecast falling: Opportunity for premium selling")  # noqa: E501

        # Percentile-based implications
        if metrics.volatility_percentile > 80:
            implications.append("Volatility in high percentile: Mean reversion likely")
        elif metrics.volatility_percentile < 20:
            implications.append("Volatility in low percentile: Prepare for potential spike")

        return implications

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _update_history(self, metrics: VolatilityMetrics) -> None:
        """Update historical records"""
        self.volatility_history.append(
            (metrics.calculation_time, metrics.current_volatility)
        )
        self.regime_history.append(
            (metrics.calculation_time, metrics.volatility_regime)
        )

        # Keep only last 252 days
        cutoff_date = datetime.now(UTC) - timedelta(days=252)
        self.volatility_history = [
            (dt, vol) for dt, vol in self.volatility_history
            if dt > cutoff_date
        ]
        self.regime_history = [
            (dt, regime) for dt, regime in self.regime_history
            if dt > cutoff_date
        ]

    def _get_default_analysis(self) -> VolatilityAnalysisResult:
        """Get default analysis for error cases"""
        default_metrics = VolatilityMetrics(
            current_volatility=0.15,
            historical_volatilities={20: 0.15},
            volatility_of_volatility=0.05,
            volatility_regime=VolatilityRegime.NORMAL,
            volatility_trend=VolatilityTrend.STABLE,
            volatility_percentile=50.0,
            term_structure={20: 1.0},
            method_used=VolatilityMethod.CLOSE_TO_CLOSE,
            calculation_time=datetime.now(UTC)
        )

        return VolatilityAnalysisResult(
            metrics=default_metrics,
            vix_analysis=None,
            forecasts={},
            regime_probabilities={regime: 0.2 for regime in VolatilityRegime},
            trading_implications=["Unable to perform full analysis, using defaults"]
        )

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def get_regime_history(
        self,
        days: int = 30
    ) -> list[tuple[datetime, VolatilityRegime]]:
        """Get regime history for specified days"""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        return [(dt, regime) for dt, regime in self.regime_history if dt > cutoff]

    def get_volatility_cone(
        self,
        data: pd.DataFrame,
        percentiles: list[float] = None
    ) -> dict[int, dict[float, float]]:
        """
        Calculate volatility cone for different time periods.

        Args:
            data: Historical price data
            percentiles: Percentiles to calculate

        Returns:
            Volatility cone data
        """
        if percentiles is None:
            percentiles = [10, 25, 50, 75, 90]
        cone = {}

        for window in VOL_WINDOWS:
            if len(data) < window * 2:
                continue

            # Calculate rolling volatility
            returns = np.log(data['close'] / data['close'].shift(1))
            rolling_vol = returns.rolling(window).std() * np.sqrt(TRADING_DAYS_YEAR)

            # Calculate percentiles
            cone[window] = {}
            for pct in percentiles:
                cone[window][pct] = float(np.percentile(rolling_vol.dropna(), pct))

        return cone

    def analyze_intraday_volatility(
        self,
        intraday_data: pd.DataFrame
    ) -> dict[str, float]:
        """
        Analyze intraday volatility patterns.

        Args:
            intraday_data: Intraday OHLCV data

        Returns:
            Intraday volatility metrics
        """
        if len(intraday_data) < 30:
            return {'error': 'Insufficient intraday data'}

        # Calculate returns
        returns = intraday_data['close'].pct_change().dropna()

        # Time-based volatility
        intraday_data['hour'] = pd.to_datetime(intraday_data.index).hour
        hourly_vol = returns.groupby(intraday_data['hour']).std()

        # Opening hour volatility
        open_vol = hourly_vol.get(9, 0) if 9 in hourly_vol else 0

        # Closing hour volatility
        close_vol = hourly_vol.get(15, 0) if 15 in hourly_vol else 0

        # Mid-day volatility
        midday_vols = [hourly_vol.get(h, 0) for h in range(11, 14) if h in hourly_vol]
        midday_vol = np.mean(midday_vols) if midday_vols else 0

        return {
            'opening_volatility': float(open_vol),
            'midday_volatility': float(midday_vol),
            'closing_volatility': float(close_vol),
            'volatility_ratio': float(close_vol / open_vol) if open_vol > 0 else 1.0,
            'average_intraday_vol': float(returns.std())
        }

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test volatility analyzer
    analyzer = VolatilityAnalyzer()

    # Create sample data
    dates = pd.date_range(start='2025-01-01', periods=100, freq='D')
    np.random.seed(42)

    # Generate realistic OHLCV data
    close_prices = 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, 100)))

    data = pd.DataFrame({
        'open': close_prices * (1 + np.random.uniform(-0.005, 0.005, 100)),
        'high': close_prices * (1 + np.random.uniform(0, 0.01, 100)),
        'low': close_prices * (1 - np.random.uniform(0, 0.01, 100)),
        'close': close_prices,
        'volume': np.random.randint(1000000, 5000000, 100)
    }, index=dates)

    # Create sample VIX data
    vix_data = pd.DataFrame({
        'close': 15 + 5 * np.random.randn(100)
    }, index=dates)

    # Perform analysis
    result = analyzer.analyze(data, vix_data)


    if result.vix_analysis:
        pass

    for _implication in result.trading_implications:
        pass

    # Test volatility cone
    cone = analyzer.get_volatility_cone(data)
    for _window, percentiles in cone.items():
        if 50 in percentiles:
            pass
