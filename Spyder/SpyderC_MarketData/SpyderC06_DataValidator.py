#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC06_DataValidator.py
Group: C (Market Data)
Purpose: Data quality and validation checks

Description:
    This module ensures data quality and integrity for the Spyder trading system.
    It validates incoming market data, detects anomalies, handles data gaps,
    and maintains data consistency across all components. The validator prevents
    bad data from affecting trading decisions and alerts when data issues occur.
    Features include real-time validation, statistical anomaly detection, and
    comprehensive data quality scoring.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-06
Last Updated: 2025-07-06 Time: 17:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set, Callable, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto
import statistics
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils, MarketSession
from Spyder.SpyderU_Utilities.SpyderU07_Constants import TimeFrame
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Validation Thresholds
MAX_PRICE_CHANGE_PCT = 0.10        # 10% maximum price change
MAX_VOLUME_SPIKE = 10.0             # 10x average volume
MIN_TICK_SIZE = 0.01                # Minimum tick size
MAX_BID_ASK_SPREAD_PCT = 0.05       # 5% maximum spread
STALE_DATA_THRESHOLD = 30           # 30 seconds for stale data
MIN_MARKET_CAP = 1e9                # $1B minimum market cap

# Statistical Validation
ZSCORE_THRESHOLD = 3.0              # Z-score threshold for outliers
PERCENTILE_THRESHOLD = 0.99         # 99th percentile threshold
LOOKBACK_WINDOW = 100               # Lookback window for statistics
MIN_HISTORY_POINTS = 20             # Minimum history for validation

# Data Quality Scoring
QUALITY_WEIGHTS = {
    'price_validity': 0.25,
    'volume_validity': 0.20,
    'spread_quality': 0.15,
    'timestamp_quality': 0.15,
    'statistical_validity': 0.15,
    'consistency': 0.10
}

# Alert Thresholds
ERROR_RATE_THRESHOLD = 0.05         # 5% error rate threshold
QUALITY_DEGRADATION_THRESHOLD = 0.2 # 20% quality degradation
CONSECUTIVE_ERRORS_THRESHOLD = 5    # 5 consecutive errors

# ==============================================================================
# ENUMS
# ==============================================================================
class DataQuality(Enum):
    """Data quality levels."""
    EXCELLENT = "excellent"     # 95-100% quality score
    GOOD = "good"              # 80-95% quality score
    FAIR = "fair"              # 60-80% quality score
    POOR = "poor"              # 40-60% quality score
    INVALID = "invalid"        # <40% quality score

class ValidationStatus(Enum):
    """Validation result status."""
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"
    REJECTED = "rejected"

class AnomalyType(Enum):
    """Types of data anomalies."""
    PRICE_SPIKE = "price_spike"
    VOLUME_SPIKE = "volume_spike"
    SPREAD_ANOMALY = "spread_anomaly"
    TIMESTAMP_GAP = "timestamp_gap"
    STATISTICAL_OUTLIER = "statistical_outlier"
    CONSISTENCY_ERROR = "consistency_error"
    MISSING_DATA = "missing_data"

class DataType(Enum):
    """Types of market data."""
    EQUITY_TICK = "equity_tick"
    OPTION_QUOTE = "option_quote"
    INDEX_DATA = "index_data"
    VOLUME_DATA = "volume_data"
    FUNDAMENTALS = "fundamentals"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ValidationRule:
    """Data validation rule."""
    name: str
    rule_type: str
    parameters: Dict[str, Any]
    weight: float
    enabled: bool = True
    
    def validate(self, data: Any) -> Tuple[bool, float, str]:
        """
        Validate data against this rule.
        
        Args:
            data: Data to validate
            
        Returns:
            Tuple of (is_valid, confidence, message)
        """
        # This would be implemented by specific rule types
        return True, 1.0, "Rule not implemented"

@dataclass
class ValidationResult:
    """Result of data validation."""
    status: ValidationStatus
    quality_score: float
    confidence: float
    errors: List[str]
    warnings: List[str]
    anomalies: List[AnomalyType]
    metadata: Dict[str, Any]
    timestamp: datetime
    
    @property
    def is_valid(self) -> bool:
        """Check if data is valid for trading."""
        return self.status in [ValidationStatus.VALID, ValidationStatus.WARNING]
    
    @property
    def quality_level(self) -> DataQuality:
        """Get quality level based on score."""
        if self.quality_score >= 0.95:
            return DataQuality.EXCELLENT
        elif self.quality_score >= 0.80:
            return DataQuality.GOOD
        elif self.quality_score >= 0.60:
            return DataQuality.FAIR
        elif self.quality_score >= 0.40:
            return DataQuality.POOR
        else:
            return DataQuality.INVALID

@dataclass
class DataPoint:
    """Standardized data point for validation."""
    symbol: str
    data_type: DataType
    price: Optional[float]
    volume: Optional[int]
    bid: Optional[float]
    ask: Optional[float]
    timestamp: datetime
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def spread(self) -> Optional[float]:
        """Calculate bid-ask spread."""
        if self.bid is not None and self.ask is not None and self.bid > 0:
            return self.ask - self.bid
        return None
    
    @property
    def spread_pct(self) -> Optional[float]:
        """Calculate spread percentage."""
        if self.spread is not None and self.bid is not None and self.bid > 0:
            return self.spread / ((self.bid + self.ask) / 2)
        return None

@dataclass
class QualityMetrics:
    """Data quality metrics for a symbol."""
    symbol: str
    total_points: int
    valid_points: int
    error_points: int
    warning_points: int
    rejected_points: int
    avg_quality_score: float
    current_quality: DataQuality
    last_update: datetime
    error_rate: float
    consecutive_errors: int
    anomaly_count: int
    
    @property
    def overall_quality(self) -> DataQuality:
        """Get overall quality assessment."""
        if self.error_rate > ERROR_RATE_THRESHOLD:
            return DataQuality.POOR
        elif self.consecutive_errors >= CONSECUTIVE_ERRORS_THRESHOLD:
            return DataQuality.POOR
        else:
            return self.current_quality

# ==============================================================================
# VALIDATION RULES
# ==============================================================================
class PriceValidationRule(ValidationRule):
    """Price validation rule."""
    
    def __init__(self):
        super().__init__(
            name="price_validation",
            rule_type="price",
            parameters={
                'max_change_pct': MAX_PRICE_CHANGE_PCT,
                'min_price': 0.01,
                'max_price': 10000.0
            },
            weight=QUALITY_WEIGHTS['price_validity']
        )
    
    def validate(self, data: DataPoint, historical_data: List[DataPoint]) -> Tuple[bool, float, str]:
        """Validate price data."""
        if data.price is None or data.price <= 0:
            return False, 0.0, "Invalid price value"
        
        # Check price range
        if data.price < self.parameters['min_price'] or data.price > self.parameters['max_price']:
            return False, 0.0, f"Price {data.price} outside valid range"
        
        # Check price change if we have history
        if historical_data:
            last_price = historical_data[-1].price
            if last_price and last_price > 0:
                change_pct = abs(data.price - last_price) / last_price
                if change_pct > self.parameters['max_change_pct']:
                    return False, 0.5, f"Price change {change_pct:.1%} exceeds threshold"
        
        return True, 1.0, "Price validation passed"

class VolumeValidationRule(ValidationRule):
    """Volume validation rule."""
    
    def __init__(self):
        super().__init__(
            name="volume_validation",
            rule_type="volume",
            parameters={
                'max_volume_spike': MAX_VOLUME_SPIKE,
                'min_volume': 0
            },
            weight=QUALITY_WEIGHTS['volume_validity']
        )
    
    def validate(self, data: DataPoint, historical_data: List[DataPoint]) -> Tuple[bool, float, str]:
        """Validate volume data."""
        if data.volume is None:
            return True, 0.8, "No volume data"  # Not always required
        
        if data.volume < 0:
            return False, 0.0, "Negative volume"
        
        # Check volume spike
        if historical_data and len(historical_data) >= 10:
            recent_volumes = [d.volume for d in historical_data[-10:] if d.volume is not None]
            if recent_volumes:
                avg_volume = np.mean(recent_volumes)
                if avg_volume > 0 and data.volume > avg_volume * self.parameters['max_volume_spike']:
                    return False, 0.6, f"Volume spike detected: {data.volume / avg_volume:.1f}x average"
        
        return True, 1.0, "Volume validation passed"

class SpreadValidationRule(ValidationRule):
    """Bid-ask spread validation rule."""
    
    def __init__(self):
        super().__init__(
            name="spread_validation",
            rule_type="spread",
            parameters={
                'max_spread_pct': MAX_BID_ASK_SPREAD_PCT
            },
            weight=QUALITY_WEIGHTS['spread_quality']
        )
    
    def validate(self, data: DataPoint, historical_data: List[DataPoint]) -> Tuple[bool, float, str]:
        """Validate bid-ask spread."""
        if data.bid is None or data.ask is None:
            return True, 0.7, "No bid/ask data"
        
        if data.bid <= 0 or data.ask <= 0:
            return False, 0.0, "Invalid bid/ask values"
        
        if data.bid >= data.ask:
            return False, 0.0, "Bid >= Ask (crossed market)"
        
        spread_pct = data.spread_pct
        if spread_pct and spread_pct > self.parameters['max_spread_pct']:
            return False, 0.5, f"Spread {spread_pct:.1%} exceeds threshold"
        
        return True, 1.0, "Spread validation passed"

class TimestampValidationRule(ValidationRule):
    """Timestamp validation rule."""
    
    def __init__(self):
        super().__init__(
            name="timestamp_validation",
            rule_type="timestamp",
            parameters={
                'max_age_seconds': STALE_DATA_THRESHOLD,
                'future_tolerance_seconds': 5
            },
            weight=QUALITY_WEIGHTS['timestamp_quality']
        )
    
    def validate(self, data: DataPoint, historical_data: List[DataPoint]) -> Tuple[bool, float, str]:
        """Validate timestamp."""
        current_time = datetime.now()
        
        # Check if timestamp is too old
        age_seconds = (current_time - data.timestamp).total_seconds()
        if age_seconds > self.parameters['max_age_seconds']:
            return False, 0.3, f"Stale data: {age_seconds:.0f}s old"
        
        # Check if timestamp is in the future
        if data.timestamp > current_time + timedelta(seconds=self.parameters['future_tolerance_seconds']):
            return False, 0.0, "Future timestamp"
        
        # Check for reasonable timestamp progression
        if historical_data:
            last_timestamp = historical_data[-1].timestamp
            if data.timestamp < last_timestamp:
                return False, 0.5, "Timestamp regression"
        
        return True, 1.0, "Timestamp validation passed"

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class DataValidator:
    """
    Comprehensive data validation and quality control system.
    
    This class provides real-time data validation including price checks, volume
    validation, spread analysis, timestamp verification, and statistical anomaly
    detection. It maintains quality metrics for all symbols and generates alerts
    when data quality degrades or anomalies are detected.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        validation_rules: List of validation rules
        quality_metrics: Quality metrics by symbol
        historical_data: Historical data for validation
        anomaly_detector: Statistical anomaly detection
        
    Example:
        >>> validator = DataValidator()
        >>> validator.initialize()
        >>> result = validator.validate_data(data_point)
        >>> if result.is_valid:
        >>>     print(f"Data quality: {result.quality_level.value}")
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize data validator."""
        self.logger = SpyderLogger.get_logger("DataValidator")
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config or {}
        self.enable_anomaly_detection = self.config.get('enable_anomaly_detection', True)
        self.quality_threshold = self.config.get('quality_threshold', 0.6)
        
        # Validation rules
        self.validation_rules: List[ValidationRule] = []
        self._initialize_validation_rules()
        
        # Data storage
        self.quality_metrics: Dict[str, QualityMetrics] = {}
        self.historical_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=LOOKBACK_WINDOW))
        self.validation_history: deque = deque(maxlen=1000)
        
        # Anomaly detection
        self.anomaly_detector: Optional[IsolationForest] = None
        self.scaler = StandardScaler()
        self._initialize_anomaly_detection()
        
        # Statistics
        self.stats = {
            'total_validations': 0,
            'valid_data_points': 0,
            'invalid_data_points': 0,
            'anomalies_detected': 0,
            'last_quality_check': time.time()
        }
        
        # Threading
        self._lock = threading.RLock()
        self._monitoring_thread = None
        self._stop_event = threading.Event()
        self.is_monitoring = False
        
        # Event manager integration
        self.event_manager = get_event_manager()
        
        self.logger.info("Data validator initialized")

    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize the data validator.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Register event callbacks
            self._register_event_callbacks()
            
            # Start monitoring if configured
            if self.config.get('auto_monitor', True):
                self.start_monitoring()
            
            self.logger.info("Data validator initialized successfully")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'initialize',
                'class': 'DataValidator'
            })
            return False
    
    def _initialize_validation_rules(self) -> None:
        """Initialize validation rules."""
        self.validation_rules = [
            PriceValidationRule(),
            VolumeValidationRule(),
            SpreadValidationRule(),
            TimestampValidationRule()
        ]
    
    def _initialize_anomaly_detection(self) -> None:
        """Initialize anomaly detection system."""
        if self.enable_anomaly_detection:
            try:
                self.anomaly_detector = IsolationForest(
                    contamination=0.1,  # 10% expected outliers
                    random_state=42,
                    n_estimators=100
                )
            except Exception as e:
                self.logger.warning(f"Failed to initialize anomaly detection: {e}")
                self.enable_anomaly_detection = False
    
    def _register_event_callbacks(self) -> None:
        """Register event manager callbacks."""
        if self.event_manager:
            self.event_manager.subscribe(EventType.MARKET_DATA, self._on_market_data)
            self.event_manager.subscribe(EventType.OPTION_DATA, self._on_option_data)

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start_monitoring(self) -> None:
        """Start continuous data quality monitoring."""
        if self.is_monitoring:
            self.logger.warning("Data validator monitoring already running")
            return
        
        try:
            self.is_monitoring = True
            self._stop_event.clear()
            
            self._monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                name="DataValidatorMonitoring",
                daemon=True
            )
            self._monitoring_thread.start()
            
            self.logger.info("Data validator monitoring started")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'start_monitoring'
            })
            self.is_monitoring = False
    
    def stop_monitoring(self) -> None:
        """Stop data quality monitoring."""
        if not self.is_monitoring:
            return
        
        try:
            self.is_monitoring = False
            self._stop_event.set()
            
            if self._monitoring_thread and self._monitoring_thread.is_alive():
                self._monitoring_thread.join(timeout=5.0)
            
            self.logger.info("Data validator monitoring stopped")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'stop_monitoring'
            })

    # ==========================================================================
    # VALIDATION METHODS
    # ==========================================================================
    def validate_data(self, data: Union[DataPoint, Dict]) -> ValidationResult:
        """
        Validate data point against all rules.
        
        Args:
            data: Data to validate (DataPoint or dict)
            
        Returns:
            ValidationResult with validation outcome
        """
        try:
            # Convert dict to DataPoint if needed
            if isinstance(data, dict):
                data = self._dict_to_datapoint(data)
            
            # Initialize validation result
            errors = []
            warnings = []
            anomalies = []
            quality_scores = []
            
            # Get historical data for this symbol
            historical = list(self.historical_data[data.symbol])
            
            # Run all validation rules
            for rule in self.validation_rules:
                if not rule.enabled:
                    continue
                
                try:
                    is_valid, confidence, message = rule.validate(data, historical)
                    
                    if not is_valid:
                        if confidence < 0.3:
                            errors.append(f"{rule.name}: {message}")
                        else:
                            warnings.append(f"{rule.name}: {message}")
                    
                    quality_scores.append(confidence * rule.weight)
                    
                except Exception as e:
                    errors.append(f"{rule.name}: Validation error - {e}")
                    quality_scores.append(0.0)
            
            # Statistical anomaly detection
            if self.enable_anomaly_detection and len(historical) >= MIN_HISTORY_POINTS:
                anomaly_result = self._detect_statistical_anomalies(data, historical)
                if anomaly_result:
                    anomalies.extend(anomaly_result)
            
            # Calculate overall quality score
            quality_score = sum(quality_scores) if quality_scores else 0.0
            
            # Determine validation status
            if errors:
                status = ValidationStatus.ERROR if quality_score < 0.4 else ValidationStatus.REJECTED
            elif warnings or anomalies:
                status = ValidationStatus.WARNING
            else:
                status = ValidationStatus.VALID
            
            # Create validation result
            result = ValidationResult(
                status=status,
                quality_score=quality_score,
                confidence=min(1.0, quality_score + 0.1),
                errors=errors,
                warnings=warnings,
                anomalies=anomalies,
                metadata={
                    'symbol': data.symbol,
                    'data_type': data.data_type.value,
                    'rules_applied': len([r for r in self.validation_rules if r.enabled])
                },
                timestamp=datetime.now()
            )
            
            # Update statistics and metrics
            self._update_validation_stats(data.symbol, result)
            
            # Store validation history
            self.validation_history.append(result)
            
            # Add to historical data if valid
            if result.is_valid:
                self.historical_data[data.symbol].append(data)
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'validate_data',
                'symbol': getattr(data, 'symbol', 'unknown')
            })
            
            # Return error result
            return ValidationResult(
                status=ValidationStatus.ERROR,
                quality_score=0.0,
                confidence=0.0,
                errors=[f"Validation system error: {e}"],
                warnings=[],
                anomalies=[],
                metadata={},
                timestamp=datetime.now()
            )
    
    def _detect_statistical_anomalies(self, data: DataPoint, historical: List[DataPoint]) -> List[AnomalyType]:
        """Detect statistical anomalies in data."""
        anomalies = []
        
        try:
            if not self.anomaly_detector or len(historical) < MIN_HISTORY_POINTS:
                return anomalies
            
            # Prepare feature vector
            features = self._extract_features(data, historical)
            if not features:
                return anomalies
            
            # Check for price anomalies
            if data.price is not None:
                prices = [d.price for d in historical if d.price is not None]
                if len(prices) >= 10:
                    z_score = abs(stats.zscore(prices + [data.price])[-1])
                    if z_score > ZSCORE_THRESHOLD:
                        anomalies.append(AnomalyType.STATISTICAL_OUTLIER)
            
            # Check for volume anomalies
            if data.volume is not None:
                volumes = [d.volume for d in historical if d.volume is not None]
                if len(volumes) >= 10:
                    z_score = abs(stats.zscore(volumes + [data.volume])[-1])
                    if z_score > ZSCORE_THRESHOLD:
                        anomalies.append(AnomalyType.VOLUME_SPIKE)
            
        except Exception as e:
            self.logger.debug(f"Anomaly detection error: {e}")
        
        return anomalies
    
    def _extract_features(self, data: DataPoint, historical: List[DataPoint]) -> Optional[List[float]]:
        """Extract features for anomaly detection."""
        try:
            features = []
            
            # Price features
            if data.price is not None:
                features.append(data.price)
                
                # Price change from last point
                if historical and historical[-1].price is not None:
                    price_change = (data.price - historical[-1].price) / historical[-1].price
                    features.append(price_change)
            
            # Volume features
            if data.volume is not None:
                features.append(math.log(data.volume + 1))  # Log transform
            
            # Spread features
            if data.spread_pct is not None:
                features.append(data.spread_pct)
            
            return features if len(features) >= 2 else None
            
        except Exception:
            return None

    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    def _on_market_data(self, event: Event) -> None:
        """Handle market data for validation."""
        try:
            data_dict = event.data
            if not data_dict:
                return
            
            # Convert to DataPoint and validate
            data_point = self._dict_to_datapoint(data_dict)
            result = self.validate_data(data_point)
            
            # Emit validation result event if there are issues
            if not result.is_valid:
                self._emit_validation_event(result)
                
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_on_market_data'
            })
    
    def _on_option_data(self, event: Event) -> None:
        """Handle option data for validation."""
        try:
            data_dict = event.data
            if not data_dict:
                return
            
            # Convert to DataPoint and validate
            data_point = self._dict_to_datapoint(data_dict, DataType.OPTION_QUOTE)
            result = self.validate_data(data_point)
            
            # Emit validation result event if there are issues
            if not result.is_valid:
                self._emit_validation_event(result)
                
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_on_option_data'
            })

    # ==========================================================================
    # MONITORING METHODS
    # ==========================================================================
    def _monitoring_loop(self) -> None:
        """Continuous monitoring loop."""
        while not self._stop_event.is_set() and self.is_monitoring:
            try:
                # Check data quality metrics
                self._check_quality_degradation()
                
                # Clean old data
                self._cleanup_old_data()
                
                # Update anomaly detection model
                self._update_anomaly_model()
                
                # Sleep
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'method': '_monitoring_loop'
                })
                time.sleep(60)
    
    def _check_quality_degradation(self) -> None:
        """Check for data quality degradation."""
        current_time = time.time()
        
        # Only check periodically
        if current_time - self.stats['last_quality_check'] < 300:  # 5 minutes
            return
        
        with self._lock:
            for symbol, metrics in self.quality_metrics.items():
                # Check error rate
                if metrics.error_rate > ERROR_RATE_THRESHOLD:
                    self._emit_quality_alert(symbol, f"High error rate: {metrics.error_rate:.1%}")
                
                # Check consecutive errors
                if metrics.consecutive_errors >= CONSECUTIVE_ERRORS_THRESHOLD:
                    self._emit_quality_alert(symbol, f"Consecutive errors: {metrics.consecutive_errors}")
                
                # Check quality degradation
                if metrics.overall_quality == DataQuality.POOR:
                    self._emit_quality_alert(symbol, "Poor data quality detected")
        
        self.stats['last_quality_check'] = current_time
    
    def _cleanup_old_data(self) -> None:
        """Clean up old validation history."""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        # Clean validation history
        while (self.validation_history and 
               self.validation_history[0].timestamp < cutoff_time):
            self.validation_history.popleft()
    
    def _update_anomaly_model(self) -> None:
        """Update anomaly detection model with recent data."""
        if not self.enable_anomaly_detection or not self.anomaly_detector:
            return
        
        try:
            # Collect features from recent data
            all_features = []
            for symbol_data in self.historical_data.values():
                if len(symbol_data) >= 10:
                    for i in range(1, min(len(symbol_data), 50)):  # Use recent 50 points
                        features = self._extract_features(symbol_data[i], list(symbol_data[:i]))
                        if features:
                            all_features.append(features)
            
            # Retrain model if we have enough data
            if len(all_features) >= 100:
                features_array = np.array(all_features)
                self.scaler.fit(features_array)
                scaled_features = self.scaler.transform(features_array)
                self.anomaly_detector.fit(scaled_features)
                
        except Exception as e:
            self.logger.debug(f"Anomaly model update failed: {e}")

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _dict_to_datapoint(self, data_dict: Dict, data_type: DataType = DataType.EQUITY_TICK) -> DataPoint:
        """Convert dictionary to DataPoint."""
        return DataPoint(
            symbol=data_dict.get('symbol', 'UNKNOWN'),
            data_type=data_type,
            price=data_dict.get('price'),
            volume=data_dict.get('volume'),
            bid=data_dict.get('bid'),
            ask=data_dict.get('ask'),
            timestamp=data_dict.get('timestamp', datetime.now()),
            source=data_dict.get('source', 'unknown'),
            metadata=data_dict.get('metadata', {})
        )
    
    def _update_validation_stats(self, symbol: str, result: ValidationResult) -> None:
        """Update validation statistics."""
        with self._lock:
            # Update global stats
            self.stats['total_validations'] += 1
            if result.is_valid:
                self.stats['valid_data_points'] += 1
            else:
                self.stats['invalid_data_points'] += 1
            
            if result.anomalies:
                self.stats['anomalies_detected'] += len(result.anomalies)
            
            # Update symbol-specific metrics
            if symbol not in self.quality_metrics:
                self.quality_metrics[symbol] = QualityMetrics(
                    symbol=symbol,
                    total_points=0,
                    valid_points=0,
                    error_points=0,
                    warning_points=0,
                    rejected_points=0,
                    avg_quality_score=0.0,
                    current_quality=DataQuality.FAIR,
                    last_update=datetime.now(),
                    error_rate=0.0,
                    consecutive_errors=0,
                    anomaly_count=0
                )
            
            metrics = self.quality_metrics[symbol]
            metrics.total_points += 1
            metrics.last_update = datetime.now()
            
            if result.status == ValidationStatus.VALID:
                metrics.valid_points += 1
                metrics.consecutive_errors = 0
            elif result.status == ValidationStatus.WARNING:
                metrics.warning_points += 1
                metrics.consecutive_errors = 0
            elif result.status == ValidationStatus.ERROR:
                metrics.error_points += 1
                metrics.consecutive_errors += 1
            else:  # REJECTED
                metrics.rejected_points += 1
                metrics.consecutive_errors += 1
            
            if result.anomalies:
                metrics.anomaly_count += len(result.anomalies)
            
            # Update rates and averages
            if metrics.total_points > 0:
                metrics.error_rate = (metrics.error_points + metrics.rejected_points) / metrics.total_points
                
                # Calculate weighted average quality score (recent data weighted more)
                recent_weight = 0.7
                metrics.avg_quality_score = (
                    recent_weight * result.quality_score + 
                    (1 - recent_weight) * metrics.avg_quality_score
                )
            
            metrics.current_quality = result.quality_level
    
    def _emit_validation_event(self, result: ValidationResult) -> None:
        """Emit validation result event."""
        if self.event_manager:
            event = Event(
                event_type=EventType.DATA_VALIDATION,
                data={
                    'symbol': result.metadata.get('symbol'),
                    'status': result.status.value,
                    'quality_score': result.quality_score,
                    'quality_level': result.quality_level.value,
                    'errors': result.errors,
                    'warnings': result.warnings,
                    'anomalies': [a.value for a in result.anomalies]
                },
                timestamp=result.timestamp
            )
            self.event_manager.emit(event)
    
    def _emit_quality_alert(self, symbol: str, message: str) -> None:
        """Emit data quality alert."""
        if self.event_manager:
            event = Event(
                event_type=EventType.QUALITY_ALERT,
                data={
                    'symbol': symbol,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                },
                timestamp=datetime.now()
            )
            self.event_manager.emit(event)

    # ==========================================================================
    # PUBLIC API METHODS
    # ==========================================================================
    def get_data_quality(self, symbol: str) -> DataQuality:
        """
        Get current data quality for symbol.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            DataQuality level
        """
        if symbol in self.quality_metrics:
            return self.quality_metrics[symbol].overall_quality
        return DataQuality.INVALID
    
    def is_data_valid(self, symbol: str) -> bool:
        """
        Check if data is currently valid for trading.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if data is valid for trading
        """
        quality = self.get_data_quality(symbol)
        return quality in [DataQuality.EXCELLENT, DataQuality.GOOD, DataQuality.FAIR]
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """
        Get overall validation statistics.
        
        Returns:
            Dictionary with validation statistics
        """
        total_validated = self.stats['total_validations']
        
        return {
            'total_validated': total_validated,
            'valid_data_points': self.stats['valid_data_points'],
            'invalid_data_points': self.stats['invalid_data_points'],
            'success_rate': self.stats['valid_data_points'] / total_validated if total_validated > 0 else 0,
            'anomalies_detected': self.stats['anomalies_detected'],
            'symbols_monitored': len(self.quality_metrics),
            'active_rules': len([r for r in self.validation_rules if r.enabled])
        }
    
    def get_symbol_metrics(self, symbol: str) -> Optional[QualityMetrics]:
        """
        Get quality metrics for specific symbol.
        
        Args:
            symbol: Symbol to get metrics for
            
        Returns:
            QualityMetrics if available, None otherwise
        """
        return self.quality_metrics.get(symbol)
    
    def get_recent_validation_results(self, limit: int = 100) -> List[ValidationResult]:
        """
        Get recent validation results.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of recent ValidationResult objects
        """
        return list(self.validation_history)[-limit:]
    
    def add_validation_rule(self, rule: ValidationRule) -> None:
        """
        Add custom validation rule.
        
        Args:
            rule: ValidationRule to add
        """
        self.validation_rules.append(rule)
        self.logger.info(f"Added validation rule: {rule.name}")
    
    def enable_rule(self, rule_name: str) -> bool:
        """
        Enable validation rule.
        
        Args:
            rule_name: Name of rule to enable
            
        Returns:
            True if rule found and enabled
        """
        for rule in self.validation_rules:
            if rule.name == rule_name:
                rule.enabled = True
                return True
        return False
    
    def disable_rule(self, rule_name: str) -> bool:
        """
        Disable validation rule.
        
        Args:
            rule_name: Name of rule to disable
            
        Returns:
            True if rule found and disabled
        """
        for rule in self.validation_rules:
            if rule.name == rule_name:
                rule.enabled = False
                return True
        return False

    # ==========================================================================
    # CLEANUP METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up data validator resources."""
        try:
            # Stop monitoring
            self.stop_monitoring()
            
            # Clear data structures
            with self._lock:
                self.quality_metrics.clear()
                self.historical_data.clear()
                self.validation_history.clear()
            
            self.logger.info("Data validator cleanup completed")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'cleanup'
            })

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_data_validator(config: Optional[Dict] = None) -> DataValidator:
    """
    Get singleton instance of data validator.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        DataValidator instance
    """
    global _data_validator_instance
    if _data_validator_instance is None:
        _data_validator_instance = DataValidator(config)
    return _data_validator_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Global instance
_data_validator_instance: Optional[DataValidator] = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("🔍 Testing Data Validator...")
    
    validator = DataValidator()
    
    if validator.initialize():
        print("✅ Data Validator initialized successfully")
        
        # Test data point
        test_data = DataPoint(
            symbol="SPY",
            data_type=DataType.EQUITY_TICK,
            price=450.25,
            volume=1000,
            bid=450.20,
            ask=450.30,
            timestamp=datetime.now(),
            source="test"
        )
        
        print(f"📊 Testing data point: {test_data.symbol} @ ${test_data.price}")
        
        # Validate data
        result = validator.validate_data(test_data)
        
        print(f"📋 Validation Result:")
        print(f"  Status: {result.status.value}")
        print(f"  Quality Score: {result.quality_score:.2f}")
        print(f"  Quality Level: {result.quality_level.value}")
        print(f"  Is Valid: {result.is_valid}")
        
        if result.errors:
            print(f"  Errors: {result.errors}")
        if result.warnings:
            print(f"  Warnings: {result.warnings}")
        if result.anomalies:
            print(f"  Anomalies: {[a.value for a in result.anomalies]}")
        
        # Test invalid data
        invalid_data = DataPoint(
            symbol="SPY",
            data_type=DataType.EQUITY_TICK,
            price=-10.0,  # Invalid negative price
            volume=None,
            bid=450.30,   # Bid > Ask (crossed market)
            ask=450.20,
            timestamp=datetime.now() - timedelta(minutes=5),  # Stale data
            source="test"
        )
        
        print(f"\n🚫 Testing invalid data point...")
        invalid_result = validator.validate_data(invalid_data)
        
        print(f"📋 Invalid Data Result:")
        print(f"  Status: {invalid_result.status.value}")
        print(f"  Quality Score: {invalid_result.quality_score:.2f}")
        print(f"  Errors: {invalid_result.errors}")
        
        # Get statistics
        stats = validator.get_validation_stats()
        print(f"\n📈 Validation Statistics:")
        print(f"  Total Validated: {stats['total_validated']}")
        print(f"  Success Rate: {stats['success_rate']:.1%}")
        print(f"  Symbols Monitored: {stats['symbols_monitored']}")
        print(f"  Active Rules: {stats['active_rules']}")
        
        # Test quality check
        quality = validator.get_data_quality("SPY")
        print(f"\n🎯 SPY Data Quality: {quality.value}")
        print(f"  Is Valid for Trading: {validator.is_data_valid('SPY')}")
        
        # Get symbol metrics
        metrics = validator.get_symbol_metrics("SPY")
        if metrics:
            print(f"\n📊 SPY Quality Metrics:")
            print(f"  Total Points: {metrics.total_points}")
            print(f"  Valid Points: {metrics.valid_points}")
            print(f"  Error Rate: {metrics.error_rate:.1%}")
            print(f"  Avg Quality Score: {metrics.avg_quality_score:.2f}")
            print(f"  Current Quality: {metrics.current_quality.value}")
            print(f"  Consecutive Errors: {metrics.consecutive_errors}")
        
        # Test rule management
        print(f"\n⚙️ Testing Rule Management:")
        print(f"  Total Rules: {len(validator.validation_rules)}")
        
        # Disable a rule
        disabled = validator.disable_rule("volume_validation")
        print(f"  Disabled volume validation: {disabled}")
        
        # Re-enable the rule
        enabled = validator.enable_rule("volume_validation")
        print(f"  Re-enabled volume validation: {enabled}")
        
        # Test with multiple data points to build history
        print(f"\n📈 Testing with multiple data points...")
        base_price = 450.0
        for i in range(10):
            price = base_price + (i * 0.25)  # Gradual price increase
            volume = 1000 + (i * 100)
            
            data = DataPoint(
                symbol="SPY",
                data_type=DataType.EQUITY_TICK,
                price=price,
                volume=volume,
                bid=price - 0.05,
                ask=price + 0.05,
                timestamp=datetime.now() + timedelta(seconds=i),
                source="test"
            )
            
            result = validator.validate_data(data)
            if i == 9:  # Show result for last point
                print(f"  Final validation - Score: {result.quality_score:.2f}, Status: {result.status.value}")
        
        # Test anomaly detection with spike
        print(f"\n🚨 Testing anomaly detection...")
        spike_data = DataPoint(
            symbol="SPY",
            data_type=DataType.EQUITY_TICK,
            price=base_price * 1.15,  # 15% price spike
            volume=50000,             # 50x volume spike
            bid=base_price * 1.15 - 0.05,
            ask=base_price * 1.15 + 0.05,
            timestamp=datetime.now(),
            source="test"
        )
        
        spike_result = validator.validate_data(spike_data)
        print(f"  Spike Result:")
        print(f"    Status: {spike_result.status.value}")
        print(f"    Quality Score: {spike_result.quality_score:.2f}")
        print(f"    Anomalies: {[a.value for a in spike_result.anomalies]}")
        print(f"    Errors: {spike_result.errors}")
        
        # Get recent validation results
        recent_results = validator.get_recent_validation_results(5)
        print(f"\n📋 Recent Validation Results ({len(recent_results)}):")
        for i, result in enumerate(recent_results[-3:]):  # Show last 3
            print(f"  {i+1}. {result.metadata.get('symbol', 'N/A')}: {result.status.value} "
                  f"(Score: {result.quality_score:.2f})")
        
        # Final statistics
        final_stats = validator.get_validation_stats()
        print(f"\n📊 Final Statistics:")
        print(f"  Total Validations: {final_stats['total_validated']}")
        print(f"  Success Rate: {final_stats['success_rate']:.1%}")
        print(f"  Anomalies Detected: {final_stats['anomalies_detected']}")
        
        time.sleep(1)
        
        # Cleanup
        validator.cleanup()
        print("🧹 Cleanup completed")
        
    else:
        print("❌ Data Validator initialization failed")