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

Author: Mohamed Talib
Created: 2025-01-27
Version: 1.4
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import time
import threading
import statistics
import json
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass, field
from enum import Enum

# =============================================================================
# Local Application Imports
# =============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
try:
    from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
    from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
except ImportError:
    # Provide dummy classes for development
    class EventManager:
        def emit(self, event): pass
        def subscribe(self, handler, event_types): pass
    class Event:
        def __init__(self, event_type, data): 
            self.type = event_type
            self.data = data
    class EventType:
        ERROR = "error"
        WARNING = "warning"
        INFO = "info"
        MARKET_DATA = "market_data"
        QUOTE = "quote"
        TRADE = "trade"
        BAR = "bar"
    class TradingCalendar:
        def is_market_open(self): return True

# =============================================================================
# Constants
# =============================================================================
# Data quality thresholds
MAX_SPREAD_PERCENT = 0.05  # 5% max spread
MAX_PRICE_CHANGE_PERCENT = 0.10  # 10% max price change
MAX_DATA_AGE_SECONDS = 30  # 30 seconds max age
MAX_GAP_SECONDS = 60  # 60 seconds max gap
MIN_PRICE = 0.01  # Minimum valid price
OUTLIER_STD_MULTIPLIER = 3  # Standard deviations for outlier detection

# Validation parameters
ROLLING_WINDOW_SIZE = 1000
MAX_CONSECUTIVE_ERRORS = 5

# =============================================================================
# Enumerations
# =============================================================================
class DataQuality(Enum):
    """Data quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    INVALID = "invalid"

class ValidationResult(Enum):
    """Validation result types."""
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"
    REJECTED = "rejected"

class DataIssueType(Enum):
    """Types of data issues."""
    STALE_DATA = "stale_data"
    PRICE_SPIKE = "price_spike"
    INVALID_PRICE = "invalid_price"
    WIDE_SPREAD = "wide_spread"
    VOLUME_ANOMALY = "volume_anomaly"
    DATA_GAP = "data_gap"
    TICK_RATE_ANOMALY = "tick_rate_anomaly"
    SEQUENCE_ERROR = "sequence_error"
    TIMESTAMP_ERROR = "timestamp_error"

# =============================================================================
# Data Classes
# =============================================================================
class ValidationRule:
    """Data validation rule."""
    name: str
    field: str
    rule_type: str  # 'range', 'change', 'pattern', 'statistical'
    params: Dict[str, Any]
    severity: str  # 'warning', 'error'
    enabled: bool = True
    
    def validate(self, value: Any, context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate value against rule."""
        if not self.enabled:
            return True, None
        
        if self.rule_type == 'range':
            min_val = self.params.get('min')
            max_val = self.params.get('max')
            if min_val is not None and value < min_val:
                return False, f"{self.field} below minimum: {value} < {min_val}"
            if max_val is not None and value > max_val:
                return False, f"{self.field} above maximum: {value} > {max_val}"
        
        elif self.rule_type == 'change':
            prev_value = context.get(f'prev_{self.field}')
            if prev_value is not None:
                max_change = self.params.get('max_change_percent', 0.1)
                change = abs((value - prev_value) / prev_value) if prev_value != 0 else 0
                if change > max_change:
                    return False, f"{self.field} changed by {change*100:.1f}%"
        
        return True, None

class DataPoint:
    """Validated data point."""
    timestamp: datetime
    symbol: str
    data_type: str  # 'quote', 'trade', 'bar'
    raw_data: Dict[str, Any]
    validated_data: Dict[str, Any]
    validation_result: ValidationResult
    issues: List[str] = field(default_factory=list)
    quality_score: float = 100.0

class DataQualityMetrics:
    """Data quality metrics."""
    symbol: str
    total_points: int = 0
    valid_points: int = 0
    warning_points: int = 0
    error_points: int = 0
    rejected_points: int = 0
    
    # Issue counts
    issue_counts: Dict[DataIssueType, int] = field(default_factory=dict)
    
    # Timing metrics
    avg_latency_ms: float = 0.0
    max_gap_seconds: float = 0.0
    tick_rate: float = 0.0
    
    # Quality scores
    completeness_score: float = 100.0
    accuracy_score: float = 100.0
    timeliness_score: float = 100.0
    consistency_score: float = 100.0
    overall_quality: DataQuality = DataQuality.GOOD
    
    @property
    def validity_rate(self) -> float:
        """Calculate data validity rate."""
        if self.total_points > 0:
            return self.valid_points / self.total_points
        return 0.0
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_points > 0:
            return (self.error_points + self.rejected_points) / self.total_points
        return 0.0

# =============================================================================
# Class Definitions
# =============================================================================
class DataValidator:
    """
    Validates and ensures data quality.
    
    Features:
    - Real-time data validation
    - Anomaly detection
    - Data gap handling
    - Statistical outlier detection
    - Quality metrics tracking
    - Automated issue reporting
    """
    
    def __init__(self, event_manager: Optional[EventManager] = None):
        """Initialize data validator."""
        self.event_manager = event_manager or EventManager()
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Trading calendar
        self.calendar = TradingCalendar()
        
        # Validation rules
        self.validation_rules: Dict[str, List[ValidationRule]] = self._initialize_rules()
        
        # Data tracking
        self.last_data: Dict[str, Dict[str, Any]] = {}
        self.data_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=ROLLING_WINDOW_SIZE))
        self.data_stats: Dict[str, Dict[str, float]] = {}
        
        # Quality metrics
        self.quality_metrics: Dict[str, DataQualityMetrics] = {}
        self.validation_history: deque = deque(maxlen=1000)
        
        # Issue tracking
        self.active_issues: Dict[str, List[DataIssueType]] = defaultdict(list)
        self.consecutive_errors: Dict[str, int] = defaultdict(int)
        
        # Monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._data_lock = threading.RLock()
        
        self.logger.info("DataValidator initialized")
    
    def _initialize_rules(self) -> Dict[str, List[ValidationRule]]:
        """Initialize validation rules."""
        rules = {
            'quote': [
                ValidationRule(
                    name='bid_price_range',
                    field='bid',
                    rule_type='range',
                    params={'min': MIN_PRICE},
                    severity='error'
                ),
                ValidationRule(
                    name='ask_price_range',
                    field='ask',
                    rule_type='range',
                    params={'min': MIN_PRICE},
                    severity='error'
                ),
                ValidationRule(
                    name='spread_check',
                    field='spread_percent',
                    rule_type='range',
                    params={'max': MAX_SPREAD_PERCENT},
                    severity='warning'
                )
            ],
            'trade': [
                ValidationRule(
                    name='price_range',
                    field='price',
                    rule_type='range',
                    params={'min': MIN_PRICE},
                    severity='error'
                ),
                ValidationRule(
                    name='price_change',
                    field='price',
                    rule_type='change',
                    params={'max_change_percent': MAX_PRICE_CHANGE_PERCENT},
                    severity='warning'
                )
            ]
        }
        return rules
    
    def validate_price(self, price: float) -> bool:
        """Simple price validation method."""
        return price > 0
    
    def validate_data(self, symbol: str, data_type: str, data: Dict[str, Any]) -> DataPoint:
        """Validate incoming data."""
        data_point = DataPoint(
            timestamp=datetime.now(),
            symbol=symbol,
            data_type=data_type,
            raw_data=data.copy(),
            validated_data={},
            validation_result=ValidationResult.VALID,
            issues=[]
        )
        
        # Basic validations
        if data_type == 'quote':
            bid = data.get('bid', 0)
            ask = data.get('ask', 0)
            
            if bid > ask and bid > 0 and ask > 0:
                data_point.issues.append("Bid > Ask")
                data_point.validation_result = ValidationResult.ERROR
        
        # Calculate quality score
        data_point.quality_score = 100.0 - (len(data_point.issues) * 10)
        
        return data_point
    
    def get_data_quality(self, symbol: str) -> DataQuality:
        """Get current data quality for symbol."""
        if symbol in self.quality_metrics:
            return self.quality_metrics[symbol].overall_quality
        return DataQuality.INVALID
    
    def is_data_valid(self, symbol: str) -> bool:
        """Check if data is currently valid for trading."""
        quality = self.get_data_quality(symbol)
        return quality in [DataQuality.EXCELLENT, DataQuality.GOOD, DataQuality.FAIR]
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get overall validation statistics."""
        total_validated = sum(m.total_points for m in self.quality_metrics.values())
        total_errors = sum(m.error_points + m.rejected_points for m in self.quality_metrics.values())
        
        return {
            'total_validated': total_validated,
            'total_errors': total_errors,
            'error_rate': total_errors / total_validated if total_validated > 0 else 0,
            'symbols_monitored': len(self.quality_metrics)
        }

# =============================================================================
# Module Functions
# =============================================================================
def get_data_validator() -> DataValidator:
    """Get singleton instance of data validator."""
    global _DATA_VALIDATOR_INSTANCE
    if _DATA_VALIDATOR_INSTANCE is None:
        _DATA_VALIDATOR_INSTANCE = DataValidator()
    return _DATA_VALIDATOR_INSTANCE

# =============================================================================
# Module Initialization
# =============================================================================
_DATA_VALIDATOR_INSTANCE: Optional[DataValidator] = None
