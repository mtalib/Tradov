#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderF05_TrendDetection.py
Group: F (Technical Analysis)
Purpose: Trend detection with ML integration hooks

Description:
    This module detects market trends using multiple methods including moving
    averages, linear regression, and pattern analysis. It includes hooks for
    ML enhancement to combine traditional and machine learning approaches.

Author: Claude AI (Enhanced by Maestro)
Date: 2024-01-07
Version: 2.0 - Added ML integration hooks and adaptive parameters
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
import pandas as pd

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from scipy import signal
from scipy.stats import linregress
from scipy.ndimage import gaussian_filter1d
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    # talib not available - using alternatives
    from .mock_talib import *
    import SpyderF_Analysis.mock_talib as talib
    # talib not available - using alternatives

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderI_Integration.SpyderI03_ConfigManager import ConfigManager
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import FeatureFlags
from Spyder.SpyderM_Monitoring.SpyderM01_SystemMonitor import SystemMonitor
from Spyder.SpyderF_Analysis.SpyderF01_Indicators import TechnicalIndicators

# ==============================================================================
# ENUMS
# ==============================================================================
class TrendDirection(Enum):
    """Trend direction classification."""
    STRONG_UP = "strong_up"
    UP = "up"
    NEUTRAL = "neutral"
    DOWN = "down"
    STRONG_DOWN = "strong_down"

class TrendPhase(Enum):
    """Trend phase in lifecycle."""
    EMERGING = "emerging"
    ESTABLISHED = "established"
    MATURE = "mature"
    EXHAUSTED = "exhausted"
    REVERSING = "reversing"

class TrendTimeframe(Enum):
    """Trend timeframe classification."""
    MICRO = "micro"        # < 1 hour
    SHORT = "short"        # 1-4 hours
    MEDIUM = "medium"      # 4-24 hours
    LONG = "long"          # 1-5 days
    MACRO = "macro"        # > 5 days

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class TrendResult:
    """Complete trend analysis result."""
    direction: TrendDirection
    strength: float  # 0-1
    confidence: float  # 0-1
    phase: TrendPhase
    timeframe: TrendTimeframe
    slope: float
    r_squared: float
    momentum: float
    start_time: Optional[datetime] = None
    duration: Optional[timedelta] = None
    ml_prediction: Optional[Dict] = None
    
    @property
    def is_tradeable(self) -> bool:
        """Check if trend is strong enough to trade."""
        return (self.confidence > 0.6 and 
                self.strength > 0.3 and
                self.phase not in [TrendPhase.EXHAUSTED, TrendPhase.REVERSING])

@dataclass
class MultiTimeframeTrend:
    """Trend analysis across multiple timeframes."""
    micro: Optional[TrendResult] = None
    short: Optional[TrendResult] = None
    medium: Optional[TrendResult] = None
    long: Optional[TrendResult] = None
    macro: Optional[TrendResult] = None
    
    @property
    def alignment_score(self) -> float:
        """Score for trend alignment across timeframes."""
        trends = [t for t in [self.micro, self.short, self.medium, self.long, self.macro] if t]
        if not trends:
            return 0.0
        
        # Count aligned trends
        main_direction = max(set([t.direction for t in trends]), 
                           key=[t.direction for t in trends].count)
        aligned = sum(1 for t in trends if t.direction == main_direction)
        
        return aligned / len(trends)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class TrendDetector:
    """
    Advanced trend detection with ML integration capability.
    
    Features:
    - Multiple trend detection methods
    - Multi-timeframe analysis
    - ML prediction integration
    - Adaptive parameter adjustment
    - Trend phase identification
    """
    
    def __init__(self, 
                 config_manager: Optional[ConfigManager] = None,
                 ml_predictor: Optional[Any] = None):
        """Initialize with ML integration."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config_manager = config_manager or ConfigManager()
        self.ml_predictor = ml_predictor  # Optional ML integration
        self.feature_flags = FeatureFlags()
        self.monitor = SystemMonitor()
        
        # Initialize components
        self.indicators = TechnicalIndicators(config_manager)
        
        # Load configuration
        self._load_config()
        
        # Trend cache
        self._trend_cache = {}
        
        self.logger.info("TrendDetector initialized with ML integration hooks")
    
    def _load_config(self):
        """Load configuration."""
        config = self.config_manager.get_config('trend_detection', {})
        
        # Detection parameters
        self.min_trend_strength = config.get('min_trend_strength', 0.2)
        self.min_r_squared = config.get('min_r_squared', 0.5)
        self.smoothing_window = config.get('smoothing_window', 5)
        
        # Timeframe settings (in minutes)
        self.timeframe_periods = config.get('timeframe_periods', {
            'micro': 12,      # 1 hour (5-min bars)
            'short': 48,      # 4 hours
            'medium': 288,    # 24 hours
            'long': 720,      # 3 days
            'macro': 1440     # 5 days
        })
        
        # Feature flags
        self.use_ml_prediction = self.config_manager.is_feature_enabled('ml_trend_prediction')
        self.use_advanced_smoothing = config.get('use_advanced_smoothing', True)
        self.use_momentum_confirmation = config.get('use_momentum_confirmation', True)
        
        # ML integration settings
        self.ml_weight = config.get('ml_weight', 0.3)  # Weight for ML predictions
        self.ml_confidence_threshold = config.get('ml_confidence_threshold', 0.7)
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    
    def detect_trend(self, data: pd.DataFrame, 
                    timeframe: TrendTimeframe = TrendTimeframe.MEDIUM) -> TrendResult:
        """
        Detect trend with optional ML enhancement.
        
        Args:
            data: OHLC DataFrame
            timeframe: Timeframe to analyze
            
        Returns:
            Trend analysis result
        """
        start_time = datetime.now()
        
        try:
            # Get period for timeframe
            period = self.timeframe_periods.get(timeframe.value, 48)
            
            # Ensure enough data
            if len(data) < period:
                self.logger.warning(f"Insufficient data for {timeframe.value} trend")
                return self._create_neutral_trend(timeframe)
            
            # Use recent data for analysis
            analysis_data = data.tail(period).copy()
            
            # Traditional trend detection
            traditional_trend = self._detect_traditional_trend(analysis_data, timeframe)
            
            # ML enhancement if enabled
            if self.use_ml_prediction and self.ml_predictor:
                try:
                    ml_trend = self._get_ml_prediction(analysis_data, timeframe)
                    
                    # Combine predictions
                    combined_trend = self._combine_predictions(
                        traditional_trend, ml_trend
                    )
                    
                    # Record ML usage
                    self.monitor.record_metric('trend.ml_predictions_used', 1)
                    
                    return combined_trend
                    
                except Exception as e:
                    self.logger.warning(f"ML trend prediction failed: {e}")
                    # Fall back to traditional
            
            # Record performance
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.monitor.record_metric('trend.detection_ms', elapsed_ms)
            
            return traditional_trend
            
        except Exception as e:
            self.error_handler.handle_error(e, "Trend detection failed")
            return self._create_neutral_trend(timeframe)
    
    def detect_multi_timeframe(self, data: pd.DataFrame) -> MultiTimeframeTrend:
        """
        Detect trends across multiple timeframes.
        
        Args:
            data: OHLC DataFrame
            
        Returns:
            Multi-timeframe trend analysis
        """
        mtf_trend = MultiTimeframeTrend()
        
        # Analyze each timeframe
        if len(data) >= self.timeframe_periods['micro']:
            mtf_trend.micro = self.detect_trend(data, TrendTimeframe.MICRO)
        
        if len(data) >= self.timeframe_periods['short']:
            mtf_trend.short = self.detect_trend(data, TrendTimeframe.SHORT)
        
        if len(data) >= self.timeframe_periods['medium']:
            mtf_trend.medium = self.detect_trend(data, TrendTimeframe.MEDIUM)
        
        if len(data) >= self.timeframe_periods['long']:
            mtf_trend.long = self.detect_trend(data, TrendTimeframe.LONG)
        
        if len(data) >= self.timeframe_periods['macro']:
            mtf_trend.macro = self.detect_trend(data, TrendTimeframe.MACRO)
        
        return mtf_trend
    
    def identify_trend_changes(self, data: pd.DataFrame, 
                             lookback: int = 20) -> List[Dict]:
        """
        Identify potential trend change points.
        
        Returns:
            List of trend change events
        """
        changes = []
        
        if len(data) < lookback * 2:
            return changes
        
        # Calculate trends over rolling windows
        for i in range(lookback, len(data) - lookback):
            # Previous trend
            prev_data = data.iloc[i-lookback:i]
            prev_trend = self._quick_trend_direction(prev_data)
            
            # Current trend
            curr_data = data.iloc[i:i+lookback]
            curr_trend = self._quick_trend_direction(curr_data)
            
            # Check for change
            if prev_trend != curr_trend and prev_trend != TrendDirection.NEUTRAL:
                change = {
                    'timestamp': data.index[i],
                    'from_trend': prev_trend,
                    'to_trend': curr_trend,
                    'price': data['close'].iloc[i],
                    'confidence': self._calculate_change_confidence(
                        prev_data, curr_data
                    )
                }
                changes.append(change)
        
        return changes
    
    def get_trend_strength_profile(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Get trend strength over time.
        
        Returns:
            DataFrame with trend strength metrics
        """
        if len(data) < 20:
            return pd.DataFrame()
        
        profile = []
        window = 20
        
        for i in range(window, len(data)):
            window_data = data.iloc[i-window:i]
            
            # Calculate metrics
            slope, _, r_value, _, _ = linregress(
                range(len(window_data)), 
                window_data['close'].values
            )
            
            strength = abs(slope) / window_data['close'].mean()
            
            profile.append({
                'timestamp': data.index[i],
                'strength': strength,
                'r_squared': r_value ** 2,
                'direction': 'up' if slope > 0 else 'down',
                'volatility': window_data['close'].std() / window_data['close'].mean()
            })
        
        return pd.DataFrame(profile).set_index('timestamp')
    
    # ==========================================================================
    # TRADITIONAL TREND DETECTION
    # ==========================================================================
    
    def _detect_traditional_trend(self, data: pd.DataFrame, 
                                timeframe: TrendTimeframe) -> TrendResult:
        """Detect trend using traditional methods."""
        # Smooth prices if enabled
        if self.use_advanced_smoothing:
            prices = self._smooth_prices(data['close'].values)
        else:
            prices = data['close'].values
        
        # Linear regression
        x = np.arange(len(prices))
        slope, intercept, r_value, p_value, std_err = linregress(x, prices)
        
        # Calculate trend metrics
        r_squared = r_value ** 2
        relative_slope = slope / np.mean(prices)
        
        # Determine direction
        direction = self._classify_direction(relative_slope, r_squared)
        
        # Calculate strength
        strength = min(abs(relative_slope) * 100, 1.0)
        
        # Calculate confidence
        confidence = self._calculate_confidence(r_squared, p_value, len(prices))
        
        # Identify phase
        phase = self._identify_phase(data, direction, strength)
        
        # Calculate momentum if enabled
        momentum = 0.0
        if self.use_momentum_confirmation:
            momentum = self._calculate_momentum(data)
        
        # Determine start time and duration
        start_time, duration = self._find_trend_bounds(data, direction)
        
        return TrendResult(
            direction=direction,
            strength=strength,
            confidence=confidence,
            phase=phase,
            timeframe=timeframe,
            slope=slope,
            r_squared=r_squared,
            momentum=momentum,
            start_time=start_time,
            duration=duration
        )
    
    def _smooth_prices(self, prices: np.ndarray) -> np.ndarray:
        """Apply advanced smoothing to prices."""
        # Savitzky-Golay filter for smoothing while preserving features
        if len(prices) >= self.smoothing_window:
            from scipy.signal import savgol_filter
            return savgol_filter(prices, self.smoothing_window, 3)
        return prices
    
    def _classify_direction(self, slope: float, r_squared: float) -> TrendDirection:
        """Classify trend direction based on slope and fit."""
        # Adjust thresholds based on R-squared
        threshold_multiplier = r_squared
        
        if abs(slope) < 0.001 * threshold_multiplier:
            return TrendDirection.NEUTRAL
        elif slope > 0.003 * threshold_multiplier:
            return TrendDirection.STRONG_UP
        elif slope > 0.001 * threshold_multiplier:
            return TrendDirection.UP
        elif slope < -0.003 * threshold_multiplier:
            return TrendDirection.STRONG_DOWN
        else:
            return TrendDirection.DOWN
    
    def _calculate_confidence(self, r_squared: float, p_value: float, 
                            n_points: int) -> float:
        """Calculate trend confidence score."""
        # Base confidence from R-squared
        base_confidence = r_squared
        
        # Adjust for statistical significance
        if p_value < 0.01:
            significance_factor = 1.0
        elif p_value < 0.05:
            significance_factor = 0.8
        else:
            significance_factor = 0.5
        
        # Adjust for sample size
        size_factor = min(n_points / 50, 1.0)
        
        confidence = base_confidence * significance_factor * size_factor
        
        return min(confidence, 1.0)
    
    def _identify_phase(self, data: pd.DataFrame, direction: TrendDirection,
                       strength: float) -> TrendPhase:
        """Identify current phase of the trend."""
        if direction == TrendDirection.NEUTRAL:
            return TrendPhase.MATURE
        
        # Calculate momentum indicators
        rsi = self.indicators.rsi(data['close'], 14)
        if len(rsi) < 2:
            return TrendPhase.EMERGING
        
        current_rsi = rsi.iloc[-1]
        rsi_change = rsi.iloc[-1] - rsi.iloc[-5] if len(rsi) >= 5 else 0
        
        # Trend-specific phase detection
        if direction in [TrendDirection.UP, TrendDirection.STRONG_UP]:
            if strength < 0.3 and rsi_change > 0:
                return TrendPhase.EMERGING
            elif strength > 0.5 and current_rsi < 70:
                return TrendPhase.ESTABLISHED
            elif current_rsi > 70 and rsi_change < 0:
                return TrendPhase.EXHAUSTED
            elif current_rsi > 80:
                return TrendPhase.REVERSING
            else:
                return TrendPhase.MATURE
        else:
            # Down trend
            if strength < 0.3 and rsi_change < 0:
                return TrendPhase.EMERGING
            elif strength > 0.5 and current_rsi > 30:
                return TrendPhase.ESTABLISHED
            elif current_rsi < 30 and rsi_change > 0:
                return TrendPhase.EXHAUSTED
            elif current_rsi < 20:
                return TrendPhase.REVERSING
            else:
                return TrendPhase.MATURE
    
    def _calculate_momentum(self, data: pd.DataFrame) -> float:
        """Calculate trend momentum."""
        if len(data) < 10:
            return 0.0
        
        # Rate of change
        roc = (data['close'].iloc[-1] - data['close'].iloc[-10]) / data['close'].iloc[-10]
        
        # Normalize to -1 to 1
        return np.tanh(roc * 100)
    
    def _find_trend_bounds(self, data: pd.DataFrame, 
                         direction: TrendDirection) -> Tuple[Optional[datetime], Optional[timedelta]]:
        """Find when current trend started."""
        if direction == TrendDirection.NEUTRAL:
            return None, None
        
        # Simple approach: find last direction change
        prices = data['close'].values
        
        # Look for trend start
        for i in range(len(prices) - 1, 0, -1):
            local_slope = (prices[i] - prices[i-1]) / prices[i-1]
            
            # Check if direction changed
            if direction in [TrendDirection.UP, TrendDirection.STRONG_UP]:
                if local_slope < 0:
                    start_idx = i
                    break
            else:
                if local_slope > 0:
                    start_idx = i
                    break
        else:
            start_idx = 0
        
        start_time = data.index[start_idx]
        duration = data.index[-1] - start_time
        
        return start_time, duration
    
    # ==========================================================================
    # ML INTEGRATION
    # ==========================================================================
    
    def _get_ml_prediction(self, data: pd.DataFrame, 
                         timeframe: TrendTimeframe) -> Dict:
        """Get ML trend prediction."""
        if not self.ml_predictor:
            return None
        
        try:
            # Prepare features for ML model
            features = self._prepare_ml_features(data)
            
            # Get prediction
            prediction = self.ml_predictor.predict_trend(
                features,
                timeframe=timeframe.value
            )
            
            return prediction
            
        except Exception as e:
            self.logger.error(f"ML prediction error: {e}")
            return None
    
    def _prepare_ml_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for ML model."""
        features = pd.DataFrame(index=data.index)
        
        # Price-based features
        features['returns'] = data['close'].pct_change()
        features['log_returns'] = np.log(data['close'] / data['close'].shift(1))
        
        # Technical indicators
        features['rsi'] = self.indicators.rsi(data['close'], 14)
        features['macd'] = self.indicators.macd(data['close'])['macd']
        
        # Rolling statistics
        for window in [5, 10, 20]:
            features[f'sma_{window}'] = data['close'].rolling(window).mean()
            features[f'std_{window}'] = data['close'].rolling(window).std()
            features[f'skew_{window}'] = data['close'].rolling(window).skew()
        
        # Volume features
        if 'volume' in data.columns:
            features['volume_ratio'] = data['volume'] / data['volume'].rolling(20).mean()
        
        return features.dropna()
    
    def _combine_predictions(self, traditional: TrendResult, 
                           ml_prediction: Dict) -> TrendResult:
        """Combine traditional and ML predictions."""
        # Extract ML results
        ml_direction = TrendDirection(ml_prediction.get('direction', 'neutral'))
        ml_confidence = ml_prediction.get('confidence', 0.5)
        ml_strength = ml_prediction.get('strength', 0.5)
        
        # Only use ML if confidence is high
        if ml_confidence < self.ml_confidence_threshold:
            traditional.ml_prediction = ml_prediction
            return traditional
        
        # Weighted combination
        trad_weight = 1 - self.ml_weight
        ml_weight = self.ml_weight
        
        # Combine confidence
        combined_confidence = (
            trad_weight * traditional.confidence +
            ml_weight * ml_confidence
        )
        
        # Combine strength
        combined_strength = (
            trad_weight * traditional.strength +
            ml_weight * ml_strength
        )
        
        # Direction: use ML if high confidence, otherwise traditional
        if ml_confidence > 0.8:
            combined_direction = ml_direction
        else:
            combined_direction = traditional.direction
        
        # Create combined result
        combined = TrendResult(
            direction=combined_direction,
            strength=combined_strength,
            confidence=combined_confidence,
            phase=traditional.phase,  # Keep traditional phase
            timeframe=traditional.timeframe,
            slope=traditional.slope,
            r_squared=traditional.r_squared,
            momentum=traditional.momentum,
            start_time=traditional.start_time,
            duration=traditional.duration,
            ml_prediction=ml_prediction
        )
        
        return combined
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _create_neutral_trend(self, timeframe: TrendTimeframe) -> TrendResult:
        """Create neutral trend result."""
        return TrendResult(
            direction=TrendDirection.NEUTRAL,
            strength=0.0,
            confidence=0.0,
            phase=TrendPhase.MATURE,
            timeframe=timeframe,
            slope=0.0,
            r_squared=0.0,
            momentum=0.0
        )
    
    def _quick_trend_direction(self, data: pd.DataFrame) -> TrendDirection:
        """Quick trend direction calculation."""
        if len(data) < 2:
            return TrendDirection.NEUTRAL
        
        # Simple slope calculation
        prices = data['close'].values
        slope = (prices[-1] - prices[0]) / len(prices)
        relative_slope = slope / np.mean(prices)
        
        if abs(relative_slope) < 0.001:
            return TrendDirection.NEUTRAL
        elif relative_slope > 0:
            return TrendDirection.UP
        else:
            return TrendDirection.DOWN
    
    def _calculate_change_confidence(self, prev_data: pd.DataFrame,
                                   curr_data: pd.DataFrame) -> float:
        """Calculate confidence in trend change."""
        # Compare slopes
        prev_slope = (prev_data['close'].iloc[-1] - prev_data['close'].iloc[0]) / len(prev_data)
        curr_slope = (curr_data['close'].iloc[-1] - curr_data['close'].iloc[0]) / len(curr_data)
        
        # Slope difference
        slope_diff = abs(curr_slope - prev_slope) / prev_data['close'].mean()
        
        # Convert to confidence (higher difference = higher confidence)
        confidence = min(slope_diff * 100, 1.0)
        
        return confidence


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
if __name__ == "__main__":
    # Create sample data with clear trends
    dates = pd.date_range('2024-01-01', periods=500, freq='5min')
    
    # Generate trending data
    np.random.seed(42)
    prices = []
    price = 585.0
    
    # Create different trend phases
    for i in range(500):
        if i < 100:
            # Strong uptrend
            price += np.random.normal(0.2, 0.3)
        elif i < 200:
            # Consolidation
            price += np.random.normal(0, 0.2)
        elif i < 300:
            # Downtrend
            price -= np.random.normal(0.15, 0.3)
        elif i < 400:
            # Recovery
            price += np.random.normal(0.1, 0.2)
        else:
            # Exhaustion
            price += np.random.normal(0.05, 0.4)
        
        prices.append(price)
    
    data = pd.DataFrame({
        'open': prices,
        'high': [p + abs(np.random.normal(0, 0.2)) for p in prices],
        'low': [p - abs(np.random.normal(0, 0.2)) for p in prices],
        'close': [p + np.random.normal(0, 0.1) for p in prices],
        'volume': np.random.randint(1000, 10000, 500)
    }, index=dates)
    
    # Initialize detector
    config_manager = ConfigManager()
    detector = TrendDetector(config_manager)
    
    # Single timeframe analysis
    print("=== Single Timeframe Trend Analysis ===")
    trend = detector.detect_trend(data.tail(100), TrendTimeframe.MEDIUM)
    
    print(f"Direction: {trend.direction.value}")
    print(f"Strength: {trend.strength:.3f}")
    print(f"Confidence: {trend.confidence:.3f}")
    print(f"Phase: {trend.phase.value}")
    print(f"R-squared: {trend.r_squared:.3f}")
    print(f"Momentum: {trend.momentum:.3f}")
    print(f"Tradeable: {trend.is_tradeable}")
    
    # Multi-timeframe analysis
    print("\n=== Multi-Timeframe Analysis ===")
    mtf = detector.detect_multi_timeframe(data)
    
    for tf in ['micro', 'short', 'medium', 'long', 'macro']:
        trend = getattr(mtf, tf)
        if trend:
            print(f"\n{tf.upper()}:")
            print(f"  Direction: {trend.direction.value}")
            print(f"  Strength: {trend.strength:.3f}")
            print(f"  Phase: {trend.phase.value}")
    
    print(f"\nAlignment Score: {mtf.alignment_score:.2f}")
    
    # Trend changes
    print("\n=== Trend Change Detection ===")
    changes = detector.identify_trend_changes(data.tail(200))
    
    for change in changes[-5:]:  # Last 5 changes
        print(f"\nTime: {change['timestamp']}")
        print(f"From: {change['from_trend'].value} -> To: {change['to_trend'].value}")
        print(f"Price: ${change['price']:.2f}")
        print(f"Confidence: {change['confidence']:.2f}")
    
    # Trend strength profile
    print("\n=== Trend Strength Profile ===")
    profile = detector.get_trend_strength_profile(data.tail(100))
    
    if not profile.empty:
        print(f"Average Strength: {profile['strength'].mean():.4f}")
        print(f"Average R²: {profile['r_squared'].mean():.3f}")
        print(f"Direction Distribution:")
        print(profile['direction'].value_counts())
    
    # Test with ML predictor (mock)
    print("\n=== ML Integration Test ===")
    
    class MockMLPredictor:
        """Mock ML predictor for testing."""
        def predict_trend(self, features, timeframe):
            # Simulate ML prediction
            return {
                'direction': 'up',
                'confidence': 0.85,
                'strength': 0.7,
                'features_used': len(features.columns)
            }
    
    # Create detector with ML
    ml_detector = TrendDetector(config_manager, MockMLPredictor())
    ml_detector.use_ml_prediction = True
    
    ml_trend = ml_detector.detect_trend(data.tail(100), TrendTimeframe.MEDIUM)
    
    print(f"ML-Enhanced Direction: {ml_trend.direction.value}")
    print(f"ML-Enhanced Confidence: {ml_trend.confidence:.3f}")
    if ml_trend.ml_prediction:
        print(f"ML Confidence: {ml_trend.ml_prediction['confidence']:.3f}")
        print(f"Features Used: {ml_trend.ml_prediction.get('features_used', 0)}")