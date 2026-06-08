#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovF_Analysis
Module: TradovF01_Indicators.py
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
from typing import Any
from enum import Enum
from datetime import datetime, timedelta, UTC
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovA_Core.TradovA03_Configuration import get_config_manager
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
from Tradov.TradovU_Utilities.TradovU08_Validators import Validators
from Tradov.TradovM_Monitoring.TradovM01_SystemMonitor import SystemMonitor

class TrendDirection(Enum):
    """Trend direction classification."""

    STRONG_UP = "strong_up"
    UP = "up"
    NEUTRAL = "neutral"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


class MarketRegime(Enum):
    """Market regime classification."""

    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"


class SignalType(Enum):
    """Trading signal types."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"


# ==============================================================================
# DATA CLASSES
# ==============================================================================
class IndicatorResult:
    """Container for indicator results."""

    def __init__(
        self,
        name: str,
        value: float | pd.Series,
        signal: SignalType | None = None,
        confidence: float = 0.0,
    ):
        self.name = name
        self.value = value
        self.signal = signal
        self.confidence = confidence
        self.timestamp = datetime.now(UTC)


class MarketProfile:
    """Market profile analysis results."""

    def __init__(self):
        self.trend: TrendDirection = TrendDirection.NEUTRAL
        self.regime: MarketRegime = MarketRegime.RANGING
        self.volatility: float = 0.0
        self.momentum: float = 0.0
        self.volume_profile: str = "normal"
        self.key_levels: list[float] = []


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class TechnicalIndicators:
    """
    Technical indicators calculator with configuration support and validation.

    Features:
    - Configurable parameters for all indicators
    - Input validation for data quality
    - Performance monitoring
    - Caching for expensive calculations
    """

    def __init__(
        self,
        config_manager: Any | None = None,
        monitor: SystemMonitor | None = None,
    ):
        """Initialize with configuration support."""
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()
        self.config_manager = config_manager or get_config_manager()
        self.monitor = monitor or SystemMonitor()
        self.validators = Validators()

        # Load configuration
        self._load_config()

        # Cache for expensive calculations
        self._cache = {}
        self._cache_expiry = {}

        self.logger.info("TechnicalIndicators initialized with configuration support")

    def _load_config(self):
        """Load configuration from ConfigManager."""
        try:
            config = self._get_optional_config_section("indicators")

            # Default periods
            self.default_sma_period = config.get("default_sma_period", 20)
            self.default_ema_period = config.get("default_ema_period", 20)
            self.default_rsi_period = config.get("default_rsi_period", 14)
            self.default_bb_period = config.get("default_bb_period", 20)
            self.default_bb_std = config.get("default_bb_std", 2)
            self.default_macd_fast = config.get("default_macd_fast", 12)
            self.default_macd_slow = config.get("default_macd_slow", 26)
            self.default_macd_signal = config.get("default_macd_signal", 9)

            # Validation parameters
            self.min_data_points = config.get("min_data_points", 2)
            self.max_period = config.get("max_period", 500)
            self.outlier_threshold = config.get("outlier_threshold", 5)  # std devs

            # Performance settings
            self.monitoring_enabled = config.get("enable_monitoring", True)
            self.performance_threshold = config.get("performance_threshold_ms", 100)
            self.cache_ttl_seconds = config.get("cache_ttl_seconds", 300)

            # Feature flags
            self.use_talib = self._is_feature_enabled("use_talib")
            self.use_ml_signals = self._is_feature_enabled("ml_indicator_signals")

        except Exception as e:
            self.logger.warning("Could not load config, using defaults: %s", e)
            self._set_defaults()

    def _get_optional_config_section(self, section_name: str) -> dict[str, Any]:
        """Return a config section from either the A03 singleton or legacy managers."""
        get_config = getattr(self.config_manager, "get_config", None)
        if callable(get_config):
            try:
                section = get_config(section_name)
            except TypeError:
                section = None
            if isinstance(section, dict):
                return section

        for registry_name in ("configs", "config_data"):
            registry = getattr(self.config_manager, registry_name, None)
            if not isinstance(registry, dict):
                continue
            section = registry.get(section_name, {})
            if isinstance(section, dict):
                return section

        return {}

    def _is_feature_enabled(self, key: str) -> bool:
        """Return a feature flag when the config manager exposes that helper."""
        checker = getattr(self.config_manager, "is_feature_enabled", None)
        if not callable(checker):
            return False

        try:
            return bool(checker(key))
        except Exception:
            return False

    def _set_defaults(self):
        """Set default configuration values."""
        self.default_sma_period = 20
        self.default_ema_period = 20
        self.default_rsi_period = 14
        self.default_bb_period = 20
        self.default_bb_std = 2
        self.default_macd_fast = 12
        self.default_macd_slow = 26
        self.default_macd_signal = 9
        self.min_data_points = 2
        self.max_period = 500
        self.outlier_threshold = 5
        self.monitoring_enabled = True
        self.performance_threshold = 100
        self.cache_ttl_seconds = 300
        self.use_talib = False
        self.use_ml_signals = False

    # ==========================================================================
    # MOVING AVERAGES
    # ==========================================================================

    def sma(self, data: pd.Series, period: int | None = None) -> pd.Series:
        """
        Simple Moving Average with validation.

        Args:
            data: Price series
            period: Lookback period

        Returns:
            SMA series
        """
        start_time = pd.Timestamp.now()

        try:
            # Use default if not specified
            period = period or self.default_sma_period

            # Validate inputs
            self._validate_period(period)
            self._validate_data(data, period)

            # Calculate SMA
            result = data.rolling(window=period, min_periods=period).mean()

            # Monitor performance
            self._record_performance("sma", start_time)

            return result

        except Exception as e:
            self.error_handler.handle_error(e, "SMA calculation failed")
            return pd.Series(index=data.index, dtype=float)

    def ema(self, data: pd.Series, period: int | None = None) -> pd.Series:
        """
        Exponential Moving Average with validation.

        Args:
            data: Price series
            period: Lookback period

        Returns:
            EMA series
        """
        start_time = pd.Timestamp.now()

        try:
            period = period or self.default_ema_period

            # Validate inputs
            self._validate_period(period)
            self._validate_data(data, period)

            # Calculate EMA
            result = data.ewm(span=period, adjust=False).mean()

            # Monitor performance
            self._record_performance("ema", start_time)

            return result

        except Exception as e:
            self.error_handler.handle_error(e, "EMA calculation failed")
            return pd.Series(index=data.index, dtype=float)

    def vwap(self, df: pd.DataFrame, period: int | None = None) -> pd.Series:
        """
        Volume Weighted Average Price with validation.

        Args:
            df: DataFrame with 'high', 'low', 'close', 'volume'
            period: Rolling period (None for cumulative)

        Returns:
            VWAP series
        """
        start_time = pd.Timestamp.now()

        try:
            # Validate required columns
            required_cols = ["high", "low", "close", "volume"]
            self._validate_dataframe_columns(df, required_cols)

            # Calculate typical price
            typical_price = (df["high"] + df["low"] + df["close"]) / 3

            # Calculate VWAP
            if period:
                self._validate_period(period)
                pv = typical_price * df["volume"]
                vwap = pv.rolling(period).sum() / df["volume"].rolling(period).sum()
            else:
                pv = (typical_price * df["volume"]).cumsum()
                volume_cum = df["volume"].cumsum()
                vwap = pv / volume_cum

            # Monitor performance
            self._record_performance("vwap", start_time)

            return vwap

        except Exception as e:
            self.error_handler.handle_error(e, "VWAP calculation failed")
            return pd.Series(index=df.index, dtype=float)

    # ==========================================================================
    # MOMENTUM INDICATORS
    # ==========================================================================

    def rsi(self, data: pd.Series, period: int | None = None) -> pd.Series:
        """
        Relative Strength Index with validation.

        Args:
            data: Price series
            period: Lookback period

        Returns:
            RSI series
        """
        start_time = pd.Timestamp.now()

        try:
            period = period or self.default_rsi_period

            # Validate inputs
            self._validate_period(period)
            self._validate_data(data, period)

            # Check cache
            cache_key = f"rsi_{id(data)}_{period}"
            if self._is_cached(cache_key):
                return self._get_cached(cache_key)

            # Calculate RSI
            delta = data.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            # Handle edge cases
            rsi = rsi.fillna(50)  # Neutral RSI for NaN

            # Cache result
            self._cache_result(cache_key, rsi)

            # Monitor performance
            self._record_performance("rsi", start_time)

            return rsi

        except Exception as e:
            self.error_handler.handle_error(e, "RSI calculation failed")
            return pd.Series(index=data.index, dtype=float)

    def macd(
        self,
        data: pd.Series,
        fast: int | None = None,
        slow: int | None = None,
        signal: int | None = None,
    ) -> dict[str, pd.Series]:
        """
        MACD with validation.

        Args:
            data: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line EMA period

        Returns:
            Dictionary with 'macd', 'signal', 'histogram'
        """
        start_time = pd.Timestamp.now()

        try:
            # Use defaults if not specified
            fast = fast or self.default_macd_fast
            slow = slow or self.default_macd_slow
            signal = signal or self.default_macd_signal

            # Validate inputs
            self._validate_period(fast)
            self._validate_period(slow)
            self._validate_period(signal)
            self._validate_data(data, slow)  # Need enough data for slow period

            if fast >= slow:
                raise ValueError(
                    f"Fast period ({fast}) must be less than slow period ({slow})"
                )

            # Calculate MACD
            ema_fast = data.ewm(span=fast, adjust=False).mean()
            ema_slow = data.ewm(span=slow, adjust=False).mean()

            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()
            histogram = macd_line - signal_line

            result = {"macd": macd_line, "signal": signal_line, "histogram": histogram}

            # Monitor performance
            self._record_performance("macd", start_time)

            return result

        except Exception as e:
            self.error_handler.handle_error(e, "MACD calculation failed")
            return {
                "macd": pd.Series(index=data.index, dtype=float),
                "signal": pd.Series(index=data.index, dtype=float),
                "histogram": pd.Series(index=data.index, dtype=float),
            }

    def stochastic(
        self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3
    ) -> dict[str, pd.Series]:
        """
        Stochastic Oscillator with validation.

        Args:
            df: DataFrame with 'high', 'low', 'close'
            k_period: %K period
            d_period: %D smoothing period

        Returns:
            Dictionary with 'k' and 'd' lines
        """
        start_time = pd.Timestamp.now()

        try:
            # Validate inputs
            required_cols = ["high", "low", "close"]
            self._validate_dataframe_columns(df, required_cols)
            self._validate_period(k_period)
            self._validate_period(d_period)

            # Calculate Stochastic
            low_min = df["low"].rolling(window=k_period).min()
            high_max = df["high"].rolling(window=k_period).max()

            k_percent = 100 * ((df["close"] - low_min) / (high_max - low_min))
            d_percent = k_percent.rolling(window=d_period).mean()

            result = {"k": k_percent, "d": d_percent}

            # Monitor performance
            self._record_performance("stochastic", start_time)

            return result

        except Exception as e:
            self.error_handler.handle_error(e, "Stochastic calculation failed")
            return {
                "k": pd.Series(index=df.index, dtype=float),
                "d": pd.Series(index=df.index, dtype=float),
            }

    # ==========================================================================
    # VOLATILITY INDICATORS
    # ==========================================================================

    def bollinger_bands(
        self,
        data: pd.Series,
        period: int | None = None,
        std_dev: float | None = None,
    ) -> dict[str, pd.Series]:
        """
        Bollinger Bands with validation.

        Args:
            data: Price series
            period: Moving average period
            std_dev: Number of standard deviations

        Returns:
            Dictionary with 'upper', 'middle', 'lower' bands
        """
        start_time = pd.Timestamp.now()

        try:
            period = period or self.default_bb_period
            std_dev = std_dev or self.default_bb_std

            # Validate inputs
            self._validate_period(period)
            self._validate_data(data, period)

            if not self.validators.validate_positive_number(std_dev):
                raise ValueError(f"Invalid standard deviation: {std_dev}")

            # Calculate Bollinger Bands
            middle = data.rolling(window=period).mean()
            std = data.rolling(window=period).std()

            upper = middle + (std * std_dev)
            lower = middle - (std * std_dev)

            result = {
                "upper": upper,
                "middle": middle,
                "lower": lower,
                "bandwidth": (upper - lower) / middle,
                "percent_b": (data - lower) / (upper - lower),
            }

            # Monitor performance
            self._record_performance("bollinger_bands", start_time)

            return result

        except Exception as e:
            self.error_handler.handle_error(e, "Bollinger Bands calculation failed")
            return {
                "upper": pd.Series(index=data.index, dtype=float),
                "middle": pd.Series(index=data.index, dtype=float),
                "lower": pd.Series(index=data.index, dtype=float),
                "bandwidth": pd.Series(index=data.index, dtype=float),
                "percent_b": pd.Series(index=data.index, dtype=float),
            }

    def atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Average True Range with validation.

        Args:
            df: DataFrame with 'high', 'low', 'close'
            period: ATR period

        Returns:
            ATR series
        """
        start_time = pd.Timestamp.now()

        try:
            # Validate inputs
            required_cols = ["high", "low", "close"]
            self._validate_dataframe_columns(df, required_cols)
            self._validate_period(period)

            # Calculate True Range
            high_low = df["high"] - df["low"]
            high_close = abs(df["high"] - df["close"].shift())
            low_close = abs(df["low"] - df["close"].shift())

            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(
                axis=1
            )

            # Calculate ATR
            atr = true_range.rolling(window=period).mean()

            # Monitor performance
            self._record_performance("atr", start_time)

            return atr

        except Exception as e:
            self.error_handler.handle_error(e, "ATR calculation failed")
            return pd.Series(index=df.index, dtype=float)

    # ==========================================================================
    # COMPOSITE INDICATORS
    # ==========================================================================

    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all indicators for a DataFrame.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with all indicators added
        """
        start_time = pd.Timestamp.now()

        try:
            # Validate input
            required_cols = ["open", "high", "low", "close", "volume"]
            self._validate_dataframe_columns(df, required_cols)

            # Create a copy to avoid modifying original
            result = df.copy()

            # Moving averages
            result["sma_20"] = self.sma(df["close"], 20)
            result["sma_50"] = self.sma(df["close"], 50)
            result["ema_20"] = self.ema(df["close"], 20)
            result["vwap"] = self.vwap(df)

            # Momentum
            result["rsi"] = self.rsi(df["close"])
            macd_data = self.macd(df["close"])
            result["macd"] = macd_data["macd"]
            result["macd_signal"] = macd_data["signal"]
            result["macd_histogram"] = macd_data["histogram"]

            stoch_data = self.stochastic(df)
            result["stoch_k"] = stoch_data["k"]
            result["stoch_d"] = stoch_data["d"]

            # Volatility
            bb_data = self.bollinger_bands(df["close"])
            result["bb_upper"] = bb_data["upper"]
            result["bb_middle"] = bb_data["middle"]
            result["bb_lower"] = bb_data["lower"]
            result["bb_bandwidth"] = bb_data["bandwidth"]
            result["bb_percent"] = bb_data["percent_b"]

            result["atr"] = self.atr(df)

            # Monitor performance
            self._record_performance("calculate_all_indicators", start_time)

            return result

        except Exception as e:
            self.error_handler.handle_error(e, "Calculate all indicators failed")
            return df

    def get_trading_signals(self, df: pd.DataFrame) -> dict[str, SignalType]:
        """
        Generate trading signals from indicators.

        Args:
            df: DataFrame with indicators

        Returns:
            Dictionary of signals
        """
        signals = {}

        try:
            # Ensure indicators are calculated
            if "rsi" not in df.columns:
                df = self.calculate_all_indicators(df)

            latest = df.iloc[-1]

            # RSI signals
            if latest["rsi"] < 30:
                signals["rsi"] = SignalType.BUY
            elif latest["rsi"] > 70:
                signals["rsi"] = SignalType.SELL
            else:
                signals["rsi"] = SignalType.HOLD

            # MACD signals
            if (
                latest["macd"] > latest["macd_signal"]
                and df["macd"].iloc[-2] <= df["macd_signal"].iloc[-2]
            ):
                signals["macd"] = SignalType.BUY
            elif (
                latest["macd"] < latest["macd_signal"]
                and df["macd"].iloc[-2] >= df["macd_signal"].iloc[-2]
            ):
                signals["macd"] = SignalType.SELL
            else:
                signals["macd"] = SignalType.HOLD

            # Bollinger Bands signals
            if latest["close"] < latest["bb_lower"]:
                signals["bollinger"] = SignalType.BUY
            elif latest["close"] > latest["bb_upper"]:
                signals["bollinger"] = SignalType.SELL
            else:
                signals["bollinger"] = SignalType.HOLD

            # Composite signal
            buy_signals = sum(1 for s in signals.values() if s == SignalType.BUY)
            sell_signals = sum(1 for s in signals.values() if s == SignalType.SELL)

            if buy_signals >= 2:
                signals["composite"] = SignalType.BUY
            elif sell_signals >= 2:
                signals["composite"] = SignalType.SELL
            else:
                signals["composite"] = SignalType.HOLD

            return signals

        except Exception as e:
            self.error_handler.handle_error(e, "Signal generation failed")
            return {"composite": SignalType.HOLD}

    # ------------------------------------------------------------------
    # AnalyticsProviderProtocol stub
    # F01 is an indicator calculator; regime detection lives in F10/L09.
    # This stub lets isinstance(calculator, AnalyticsProviderProtocol) pass.
    # ------------------------------------------------------------------

    def get_current_regime(self, symbol: str = "") -> Any:
        """Protocol stub — regime detection lives in TradovF10 / TradovL09.

        Returns an empty RegimeSnapshot for the requested symbol.
        """
        from Tradov.TradovF_Analysis.TradovF00_AnalysisProtocol import RegimeSnapshot
        return RegimeSnapshot(symbol=symbol)

    # ==========================================================================
    # VALIDATION METHODS
    # ==========================================================================

    def _validate_period(self, period: int):
        """Validate period parameter."""
        if not self.validators.validate_positive_integer(period):
            raise ValueError(f"Period must be a positive integer, got: {period}")

        if period < self.min_data_points:
            raise ValueError(
                f"Period {period} is less than minimum {self.min_data_points}"
            )

        if period > self.max_period:
            raise ValueError(f"Period {period} exceeds maximum {self.max_period}")

    def _validate_data(self, data: pd.Series, min_length: int):
        """Validate input data series."""
        if not isinstance(data, pd.Series):
            raise TypeError(f"Expected pandas Series, got {type(data)}")

        if len(data) < min_length:
            raise ValueError(f"Insufficient data: {len(data)} < {min_length}")

        # Check for excessive NaN values
        nan_ratio = data.isna().sum() / len(data)
        if nan_ratio > 0.5:
            warnings.warn(f"High NaN ratio in data: {nan_ratio:.2%}", stacklevel=2)

        # Check for outliers
        if len(data.dropna()) > 10:
            z_scores = np.abs((data - data.mean()) / data.std())
            outliers = (z_scores > self.outlier_threshold).sum()
            if outliers > 0:
                self.logger.warning("Found %s potential outliers in data", outliers)

    def _validate_dataframe_columns(self, df: pd.DataFrame, required_cols: list[str]):
        """Validate DataFrame has required columns."""
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Expected pandas DataFrame, got {type(df)}")

        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

    # ==========================================================================
    # PERFORMANCE MONITORING
    # ==========================================================================

    def _record_performance(self, indicator_name: str, start_time: pd.Timestamp):
        """Record performance metrics."""
        if not self.monitoring_enabled:
            return

        elapsed_ms = (pd.Timestamp.now() - start_time).total_seconds() * 1000

        # Record metric
        self.monitor.record_metric(
            f"indicators.{indicator_name}.execution_ms", elapsed_ms
        )

        # Log if slow
        if elapsed_ms > self.performance_threshold:
            self.logger.warning(
                f"{indicator_name} calculation slow: {elapsed_ms:.1f}ms"
            )

    # ==========================================================================
    # CACHING METHODS
    # ==========================================================================

    def _is_cached(self, key: str) -> bool:
        """Check if result is cached and valid."""
        if key not in self._cache:
            return False

        expiry = self._cache_expiry.get(key, datetime.min)
        if datetime.now(UTC) > expiry:
            del self._cache[key]
            del self._cache_expiry[key]
            return False

        return True

    def _get_cached(self, key: str) -> Any:
        """Get cached result."""
        return self._cache.get(key)

    def _cache_result(self, key: str, result: Any):
        """Cache a result with TTL."""
        self._cache[key] = result
        self._cache_expiry[key] = datetime.now(UTC) + timedelta(
            seconds=self.cache_ttl_seconds
        )

    def clear_cache(self):
        """Clear all cached results."""
        self._cache.clear()
        self._cache_expiry.clear()
        self.logger.info("Indicator cache cleared")


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
if __name__ == "__main__":
    # Create sample data
    dates = pd.date_range("2024-01-01", periods=100, freq="5min")
    data = pd.DataFrame(
        {
            "open": np.random.randn(100).cumsum() + 585,
            "high": np.random.randn(100).cumsum() + 586,
            "low": np.random.randn(100).cumsum() + 584,
            "close": np.random.randn(100).cumsum() + 585,
            "volume": np.random.randint(1000, 10000, 100),
        },
        index=dates,
    )

    # Ensure high > low
    data["high"] = data[["open", "high", "close"]].max(axis=1)
    data["low"] = data[["open", "low", "close"]].min(axis=1)

    # Initialize indicators
    indicators = TechnicalIndicators(get_config_manager())

    # Calculate individual indicators
    sma = indicators.sma(data["close"], 20)

    rsi = indicators.rsi(data["close"], 14)

    # Calculate all indicators
    full_data = indicators.calculate_all_indicators(data)

    # Generate trading signals
    signals = indicators.get_trading_signals(full_data)
    for _indicator, _signal in signals.items():
        pass

    # Test validation
    try:
        # This should fail - period too large
        indicators.sma(data["close"], 1000)
    except ValueError:
        pass

    try:
        # This should fail - insufficient data
        indicators.sma(data["close"][:5], 20)
    except ValueError:
        pass

    # Performance test
    import time

    # First calculation
    start = time.time()
    indicators.calculate_all_indicators(data)
    first_time = time.time() - start

    # Second calculation (some caching)
    start = time.time()
    indicators.calculate_all_indicators(data)
    second_time = time.time() - start

