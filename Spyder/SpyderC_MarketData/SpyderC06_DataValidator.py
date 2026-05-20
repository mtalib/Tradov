#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC06_DataValidator.py
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
import time
import threading
from datetime import datetime, timedelta, UTC
from typing import Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import math
import numpy as np
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

MAX_PRICE_CHANGE_PCT = 0.10        # 10% maximum price change
MAX_VOLUME_SPIKE = 10.0             # 10x average volume
MIN_TICK_SIZE = 0.01                # Minimum tick size
MAX_BID_ASK_SPREAD_PCT = 0.05       # 5% maximum spread
STALE_DATA_THRESHOLD = 30           # 30 seconds for stale data
MIN_MARKET_CAP = 1e9                # $1B minimum market cap

# Trading-critical staleness gate (proactive watcher, not reactive validation)
TRADING_STALE_SECONDS = 5.0                         # block new trades after 5s silence
_TRADING_WATCH_SYMBOLS: frozenset[str] = frozenset({"SPY", "$TICK", "$ADD"})

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
    parameters: dict[str, Any]
    weight: float
    enabled: bool = True

    def validate(self, data: Any) -> tuple[bool, float, str]:
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
    errors: list[str]
    warnings: list[str]
    anomalies: list[AnomalyType]
    metadata: dict[str, Any]
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
    price: float | None
    volume: int | None
    bid: float | None
    ask: float | None
    timestamp: datetime
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def spread(self) -> float | None:
        """Calculate bid-ask spread."""
        if self.bid is not None and self.ask is not None and self.bid > 0:
            return self.ask - self.bid
        return None

    @property
    def spread_pct(self) -> float | None:
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
        if self.error_rate > ERROR_RATE_THRESHOLD or self.consecutive_errors >= CONSECUTIVE_ERRORS_THRESHOLD:  # noqa: E501
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

    def validate(self, data: DataPoint, historical_data: list[DataPoint]) -> tuple[bool, float, str]:  # noqa: E501
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

    def validate(self, data: DataPoint, historical_data: list[DataPoint]) -> tuple[bool, float, str]:  # noqa: E501
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
                if avg_volume > 0 and data.volume > avg_volume * self.parameters['max_volume_spike']:  # noqa: E501
                    return False, 0.6, f"Volume spike detected: {data.volume / avg_volume:.1f}x average"  # noqa: E501

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

    def validate(self, data: DataPoint, historical_data: list[DataPoint]) -> tuple[bool, float, str]:  # noqa: E501
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

    def validate(self, data: DataPoint, historical_data: list[DataPoint]) -> tuple[bool, float, str]:  # noqa: E501
        """Validate timestamp."""
        current_time = datetime.now(UTC)

        # Check if timestamp is too old
        age_seconds = (current_time - data.timestamp).total_seconds()
        if age_seconds > self.parameters['max_age_seconds']:
            return False, 0.3, f"Stale data: {age_seconds:.0f}s old"

        # Check if timestamp is in the future
        if data.timestamp > current_time + timedelta(seconds=self.parameters['future_tolerance_seconds']):  # noqa: E501
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

    def __init__(self, config: dict | None = None):
        """Initialize data validator."""
        self.logger = SpyderLogger.get_logger("DataValidator")
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}
        self.enable_anomaly_detection = self.config.get('enable_anomaly_detection', True)
        self.quality_threshold = self.config.get('quality_threshold', 0.6)

        # Validation rules
        self.validation_rules: list[ValidationRule] = []
        self._initialize_validation_rules()

        # Data storage
        self.quality_metrics: dict[str, QualityMetrics] = {}
        self.historical_data: dict[str, deque] = defaultdict(lambda: deque(maxlen=LOOKBACK_WINDOW))
        self.validation_history: deque = deque(maxlen=1000)

        # Anomaly detection
        self.anomaly_detector: IsolationForest | None = None
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

        # Trading-critical staleness watcher
        self._last_data_time: dict[str, float] = {}
        self._stale_state: dict[str, bool] = {}
        self._stale_watch_symbols: frozenset[str] = frozenset()
        self._stale_threshold: float = TRADING_STALE_SECONDS
        self._stale_watcher_thread: threading.Thread | None = None
        self._stale_watcher_stop = threading.Event()

        # Event manager integration
        self.event_manager = get_event_manager()

        self.logger.debug("Data validator initialized")

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

            # Start proactive staleness watcher for trading-critical symbols
            self.register_staleness_watch(_TRADING_WATCH_SYMBOLS, TRADING_STALE_SECONDS)

            self.logger.debug("Data validator initialized successfully")
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
                self.logger.warning("Failed to initialize anomaly detection: %s", e)
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
            self._stale_watcher_stop.set()

            if self._monitoring_thread and self._monitoring_thread.is_alive():
                self._monitoring_thread.join(timeout=5.0)

            if self._stale_watcher_thread and self._stale_watcher_thread.is_alive():
                self._stale_watcher_thread.join(timeout=3.0)

            self.logger.info("Data validator monitoring stopped")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'stop_monitoring'
            })

    # ==========================================================================
    # VALIDATION METHODS
    # ==========================================================================
    def validate_data(self, data: DataPoint | dict) -> ValidationResult:
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
                status = ValidationStatus.ERROR if quality_score < 0.4 else ValidationStatus.REJECTED  # noqa: E501
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
                timestamp=datetime.now(UTC)
            )

            # Record arrival time for proactive staleness watcher
            if data.symbol in self._stale_watch_symbols:
                self._last_data_time[data.symbol] = time.monotonic()

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
                timestamp=datetime.now(UTC)
            )

    def _detect_statistical_anomalies(self, data: DataPoint, historical: list[DataPoint]) -> list[AnomalyType]:  # noqa: E501
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
            self.logger.debug("Anomaly detection error: %s", e)

        return anomalies

    def _extract_features(self, data: DataPoint, historical: list[DataPoint]) -> list[float] | None:
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
                time.sleep(30)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.error_handler.handle_error(e, {
                    'method': '_monitoring_loop'
                })
                time.sleep(60)  # thread-safe: time.sleep() intentional

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
                    self._emit_quality_alert(symbol, f"Consecutive errors: {metrics.consecutive_errors}")  # noqa: E501

                # Check quality degradation
                if metrics.overall_quality == DataQuality.POOR:
                    self._emit_quality_alert(symbol, "Poor data quality detected")

        self.stats['last_quality_check'] = current_time

    def _cleanup_old_data(self) -> None:
        """Clean up old validation history."""
        cutoff_time = datetime.now(UTC) - timedelta(hours=24)

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
            self.logger.debug("Anomaly model update failed: %s", e)

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _dict_to_datapoint(self, data_dict: dict, data_type: DataType = DataType.EQUITY_TICK) -> DataPoint:  # noqa: E501
        """Convert dictionary to DataPoint."""
        return DataPoint(
            symbol=data_dict.get('symbol', 'UNKNOWN'),
            data_type=data_type,
            price=data_dict.get('price'),
            volume=data_dict.get('volume'),
            bid=data_dict.get('bid'),
            ask=data_dict.get('ask'),
            timestamp=data_dict.get('timestamp', datetime.now(UTC)),
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
                    last_update=datetime.now(UTC),
                    error_rate=0.0,
                    consecutive_errors=0,
                    anomaly_count=0
                )

            metrics = self.quality_metrics[symbol]
            metrics.total_points += 1
            metrics.last_update = datetime.now(UTC)

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
                metrics.error_rate = (metrics.error_points + metrics.rejected_points) / metrics.total_points  # noqa: E501

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
                    'timestamp': datetime.now(UTC).isoformat()
                },
                timestamp=datetime.now(UTC)
            )
            self.event_manager.emit(event)

    # ==========================================================================
    # STALENESS WATCHER — proactive 5-second gate for trading-critical symbols
    # ==========================================================================
    def register_staleness_watch(
        self,
        symbols: frozenset[str],
        threshold_seconds: float = TRADING_STALE_SECONDS,
    ) -> None:
        """Start a 1-second background watcher that emits DATA_STALE/DATA_FRESH
        events when quote silence exceeds *threshold_seconds* for any watched symbol.

        Safe to call multiple times — only one watcher thread is kept alive.
        """
        self._stale_watch_symbols = frozenset(symbols)
        self._stale_threshold = threshold_seconds
        # Initialise tracking state for each symbol
        now = time.monotonic()
        for sym in self._stale_watch_symbols:
            self._last_data_time.setdefault(sym, now)
            self._stale_state.setdefault(sym, False)

        # Stop any existing watcher before (re)starting
        self._stale_watcher_stop.set()
        if self._stale_watcher_thread and self._stale_watcher_thread.is_alive():
            self._stale_watcher_thread.join(timeout=3.0)

        self._stale_watcher_stop.clear()
        self._stale_watcher_thread = threading.Thread(
            target=self._stale_watcher_loop,
            name="DataValidatorStalenessWatcher",
            daemon=True,
        )
        self._stale_watcher_thread.start()
        self.logger.info(
            "Staleness watcher started — symbols=%s threshold=%.1fs",
            sorted(self._stale_watch_symbols),
            threshold_seconds,
        )

    def _stale_watcher_loop(self) -> None:
        """1-second polling loop — emits DATA_STALE/DATA_FRESH on transitions."""
        while not self._stale_watcher_stop.is_set():
            try:
                now = time.monotonic()
                for sym in self._stale_watch_symbols:
                    last = self._last_data_time.get(sym, now)
                    age = now - last
                    currently_stale = age >= self._stale_threshold
                    was_stale = self._stale_state.get(sym, False)
                    if currently_stale != was_stale:
                        self._stale_state[sym] = currently_stale
                        self._emit_stale_event(sym, age, stale=currently_stale)
            except Exception as exc:
                self.logger.debug("Staleness watcher error: %s", exc)
            self._stale_watcher_stop.wait(timeout=1.0)

    def _emit_stale_event(self, symbol: str, age: float, *, stale: bool) -> None:
        """Emit DATA_STALE or DATA_FRESH to the event bus."""
        if not self.event_manager:
            return
        event_type = EventType.DATA_STALE if stale else EventType.DATA_FRESH
        level = "WARNING" if stale else "INFO"
        self.logger.log(
            30 if stale else 20,  # WARNING=30, INFO=20
            "Market data %s for %s (age=%.1fs)",
            "STALE" if stale else "fresh",
            symbol,
            age,
        )
        event = Event(
            event_type=event_type,
            data={
                "symbol": symbol,
                "age_seconds": round(age, 2),
                "threshold_seconds": self._stale_threshold,
                "level": level,
            },
            timestamp=datetime.now(UTC),
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

    def get_validation_stats(self) -> dict[str, Any]:
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
            'success_rate': self.stats['valid_data_points'] / total_validated if total_validated > 0 else 0,  # noqa: E501
            'anomalies_detected': self.stats['anomalies_detected'],
            'symbols_monitored': len(self.quality_metrics),
            'active_rules': len([r for r in self.validation_rules if r.enabled])
        }

    def get_symbol_metrics(self, symbol: str) -> QualityMetrics | None:
        """
        Get quality metrics for specific symbol.

        Args:
            symbol: Symbol to get metrics for

        Returns:
            QualityMetrics if available, None otherwise
        """
        return self.quality_metrics.get(symbol)

    def get_recent_validation_results(self, limit: int = 100) -> list[ValidationResult]:
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
        self.logger.info("Added validation rule: %s", rule.name)

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
def get_data_validator(config: dict | None = None) -> DataValidator:
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
_data_validator_instance: DataValidator | None = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    validator = DataValidator()

    if validator.initialize():

        # Test data point
        test_data = DataPoint(
            symbol="SPY",
            data_type=DataType.EQUITY_TICK,
            price=450.25,
            volume=1000,
            bid=450.20,
            ask=450.30,
            timestamp=datetime.now(UTC),
            source="test"
        )


        # Validate data
        result = validator.validate_data(test_data)


        if result.errors:
            pass
        if result.warnings:
            pass
        if result.anomalies:
            pass

        # Test invalid data
        invalid_data = DataPoint(
            symbol="SPY",
            data_type=DataType.EQUITY_TICK,
            price=-10.0,  # Invalid negative price
            volume=None,
            bid=450.30,   # Bid > Ask (crossed market)
            ask=450.20,
            timestamp=datetime.now(UTC) - timedelta(minutes=5),  # Stale data
            source="test"
        )

        invalid_result = validator.validate_data(invalid_data)


        # Get statistics
        stats = validator.get_validation_stats()

        # Test quality check
        quality = validator.get_data_quality("SPY")

        # Get symbol metrics
        metrics = validator.get_symbol_metrics("SPY")
        if metrics:
            pass

        # Test rule management

        # Disable a rule
        disabled = validator.disable_rule("volume_validation")

        # Re-enable the rule
        enabled = validator.enable_rule("volume_validation")

        # Test with multiple data points to build history
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
                timestamp=datetime.now(UTC) + timedelta(seconds=i),
                source="test"
            )

            result = validator.validate_data(data)
            if i == 9:  # Show result for last point
                pass

        # Test anomaly detection with spike
        spike_data = DataPoint(
            symbol="SPY",
            data_type=DataType.EQUITY_TICK,
            price=base_price * 1.15,  # 15% price spike
            volume=50000,             # 50x volume spike
            bid=base_price * 1.15 - 0.05,
            ask=base_price * 1.15 + 0.05,
            timestamp=datetime.now(UTC),
            source="test"
        )

        spike_result = validator.validate_data(spike_data)

        # Get recent validation results
        recent_results = validator.get_recent_validation_results(5)
        for _, _ in enumerate(recent_results[-3:]):  # Show last 3
            pass

        # Final statistics
        final_stats = validator.get_validation_stats()

        time.sleep(1)  # thread-safe: time.sleep() intentional

        # Cleanup
        validator.cleanup()

    else:
        pass
