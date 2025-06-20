#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU11_FeatureFlags.py
Group: U (Utilities)
Purpose: Feature toggle management for gradual rollout

Description:
    This module provides a centralized feature flag management system that allows
    for safe deployment of new features, A/B testing, and gradual rollout of
    trading strategies. It supports runtime toggling, persistence, and monitoring
    of feature usage.

Author: Mohamed Talib
Date: 2025-06-06
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from enum import Enum, auto
from dataclasses import dataclass, field
import threading
from pathlib import Path
import hashlib
import random

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import Event, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# File paths
DEFAULT_FLAGS_FILE = Path.home() / ".spyder" / "feature_flags.json"
FLAGS_BACKUP_DIR = Path.home() / ".spyder" / "flags_backup"

# Feature categories
CATEGORY_STRATEGY = "strategy"
CATEGORY_RISK = "risk"
CATEGORY_UI = "ui"
CATEGORY_DATA = "data"
CATEGORY_EXPERIMENTAL = "experimental"

# ==============================================================================
# ENUMS
# ==============================================================================
class FeatureState(Enum):
    """Feature flag states"""
    DISABLED = "disabled"
    ENABLED = "enabled"
    PERCENTAGE = "percentage"  # Partial rollout
    AB_TEST = "ab_test"       # A/B testing
    SCHEDULED = "scheduled"    # Time-based

class RolloutStrategy(Enum):
    """Rollout strategies"""
    IMMEDIATE = auto()
    GRADUAL = auto()
    SCHEDULED = auto()
    USER_BASED = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class FeatureFlag:
    """Feature flag configuration"""
    name: str
    description: str
    category: str
    state: FeatureState
    enabled: bool = False
    
    # Rollout configuration
    percentage: float = 0.0  # For percentage rollout
    ab_group: str = "control"  # For A/B testing
    schedule_start: Optional[datetime] = None
    schedule_end: Optional[datetime] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"
    
    # Usage tracking
    usage_count: int = 0
    last_used: Optional[datetime] = None
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    conflicts_with: List[str] = field(default_factory=list)
    
    # Override capability
    override_key: Optional[str] = None  # For emergency override
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'state': self.state.value,
            'enabled': self.enabled,
            'percentage': self.percentage,
            'ab_group': self.ab_group,
            'schedule_start': self.schedule_start.isoformat() if self.schedule_start else None,
            'schedule_end': self.schedule_end.isoformat() if self.schedule_end else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'created_by': self.created_by,
            'usage_count': self.usage_count,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'depends_on': self.depends_on,
            'conflicts_with': self.conflicts_with,
            'override_key': self.override_key
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureFlag':
        """Create from dictionary"""
        # Parse dates
        if data.get('schedule_start'):
            data['schedule_start'] = datetime.fromisoformat(data['schedule_start'])
        if data.get('schedule_end'):
            data['schedule_end'] = datetime.fromisoformat(data['schedule_end'])
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('updated_at'):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if data.get('last_used'):
            data['last_used'] = datetime.fromisoformat(data['last_used'])
        
        # Parse state
        data['state'] = FeatureState(data['state'])
        
        return cls(**data)

@dataclass
class FeatureUsage:
    """Feature usage tracking"""
    feature_name: str
    timestamp: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    outcome: Optional[str] = None  # For A/B testing

# ==============================================================================
# FEATURE FLAGS MANAGER CLASS
# ==============================================================================
class FeatureFlagsManager:
    """
    Centralized feature flag management system.
    
    Features:
    - Runtime feature toggling
    - Percentage-based rollout
    - A/B testing support
    - Scheduled features
    - Usage tracking and analytics
    - Emergency override capability
    - Persistent storage
    """
    
    def __init__(self, flags_file: Optional[Path] = None, event_manager=None):
        """
        Initialize feature flags manager.
        
        Args:
            flags_file: Path to flags configuration file
            event_manager: Event manager for notifications
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = event_manager
        
        # Storage
        self.flags_file = flags_file or DEFAULT_FLAGS_FILE
        self.flags: Dict[str, FeatureFlag] = {}
        self.usage_log: List[FeatureUsage] = []
        
        # Ensure directories exist
        self.flags_file.parent.mkdir(parents=True, exist_ok=True)
        FLAGS_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Callbacks
        self.change_callbacks: Dict[str, List[Callable]] = {}
        
        # Session management
        self.session_id = self._generate_session_id()
        self.user_id = os.environ.get('USER', 'default')
        
        # Load flags
        self._load_flags()
        
        # Initialize default flags
        self._initialize_default_flags()
        
        self.logger.info("FeatureFlagsManager initialized")
    
    # ==========================================================================
    # FLAG MANAGEMENT
    # ==========================================================================
    def is_enabled(self, feature_name: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if a feature is enabled.
        
        Args:
            feature_name: Name of the feature
            context: Optional context for decision
            
        Returns:
            bool: True if feature is enabled
        """
        with self._lock:
            flag = self.flags.get(feature_name)
            if not flag:
                self.logger.warning(f"Unknown feature flag: {feature_name}")
                return False
            
            # Track usage
            self._track_usage(feature_name, context)
            
            # Check dependencies
            if not self._check_dependencies(flag):
                return False
            
            # Check conflicts
            if self._has_conflicts(flag):
                return False
            
            # Check based on state
            if flag.state == FeatureState.DISABLED:
                return False
            elif flag.state == FeatureState.ENABLED:
                return flag.enabled
            elif flag.state == FeatureState.PERCENTAGE:
                return self._check_percentage(flag, context)
            elif flag.state == FeatureState.AB_TEST:
                return self._check_ab_test(flag, context)
            elif flag.state == FeatureState.SCHEDULED:
                return self._check_schedule(flag)
            
            return False
    
    def enable(self, feature_name: str, percentage: float = 100.0) -> bool:
        """
        Enable a feature.
        
        Args:
            feature_name: Name of the feature
            percentage: Rollout percentage (0-100)
            
        Returns:
            bool: Success status
        """
        with self._lock:
            flag = self.flags.get(feature_name)
            if not flag:
                self.logger.error(f"Feature not found: {feature_name}")
                return False
            
            # Update flag
            flag.enabled = True
            if percentage < 100:
                flag.state = FeatureState.PERCENTAGE
                flag.percentage = percentage
            else:
                flag.state = FeatureState.ENABLED
                flag.percentage = 100.0
            
            flag.updated_at = datetime.now()
            
            # Save and notify
            self._save_flags()
            self._notify_change(feature_name, True)
            
            self.logger.info(f"Feature enabled: {feature_name} ({percentage}%)")
            return True
    
    def disable(self, feature_name: str) -> bool:
        """
        Disable a feature.
        
        Args:
            feature_name: Name of the feature
            
        Returns:
            bool: Success status
        """
        with self._lock:
            flag = self.flags.get(feature_name)
            if not flag:
                self.logger.error(f"Feature not found: {feature_name}")
                return False
            
            # Update flag
            flag.enabled = False
            flag.state = FeatureState.DISABLED
            flag.updated_at = datetime.now()
            
            # Save and notify
            self._save_flags()
            self._notify_change(feature_name, False)
            
            self.logger.info(f"Feature disabled: {feature_name}")
            return True
    
    def create_flag(self, name: str, description: str, category: str,
                   enabled: bool = False, **kwargs) -> FeatureFlag:
        """
        Create a new feature flag.
        
        Args:
            name: Feature name
            description: Feature description
            category: Feature category
            enabled: Initial state
            **kwargs: Additional parameters
            
        Returns:
            FeatureFlag: Created flag
        """
        with self._lock:
            if name in self.flags:
                raise ValueError(f"Feature flag already exists: {name}")
            
            flag = FeatureFlag(
                name=name,
                description=description,
                category=category,
                state=FeatureState.ENABLED if enabled else FeatureState.DISABLED,
                enabled=enabled,
                **kwargs
            )
            
            self.flags[name] = flag
            self._save_flags()
            
            self.logger.info(f"Created feature flag: {name}")
            return flag
    
    def schedule_feature(self, feature_name: str, start: datetime, end: datetime) -> bool:
        """
        Schedule a feature for specific time period.
        
        Args:
            feature_name: Feature name
            start: Start time
            end: End time
            
        Returns:
            bool: Success status
        """
        with self._lock:
            flag = self.flags.get(feature_name)
            if not flag:
                return False
            
            flag.state = FeatureState.SCHEDULED
            flag.schedule_start = start
            flag.schedule_end = end
            flag.updated_at = datetime.now()
            
            self._save_flags()
            
            self.logger.info(f"Scheduled feature {feature_name}: {start} to {end}")
            return True
    
    def setup_ab_test(self, feature_name: str, control_percentage: float = 50.0) -> bool:
        """
        Setup A/B test for a feature.
        
        Args:
            feature_name: Feature name
            control_percentage: Percentage for control group
            
        Returns:
            bool: Success status
        """
        with self._lock:
            flag = self.flags.get(feature_name)
            if not flag:
                return False
            
            flag.state = FeatureState.AB_TEST
            flag.percentage = control_percentage
            flag.updated_at = datetime.now()
            
            self._save_flags()
            
            self.logger.info(f"Setup A/B test for {feature_name}: {control_percentage}% control")
            return True
    
    # ==========================================================================
    # CHECKING LOGIC
    # ==========================================================================
    def _check_percentage(self, flag: FeatureFlag, context: Optional[Dict[str, Any]]) -> bool:
        """Check percentage-based rollout"""
        # Use consistent hashing for user
        user_hash = hashlib.md5(self.user_id.encode()).hexdigest()
        user_value = int(user_hash[:8], 16) % 100
        
        return user_value < flag.percentage
    
    def _check_ab_test(self, flag: FeatureFlag, context: Optional[Dict[str, Any]]) -> bool:
        """Check A/B test assignment"""
        # Consistent assignment based on user
        user_hash = hashlib.md5(self.user_id.encode()).hexdigest()
        user_value = int(user_hash[:8], 16) % 100
        
        if user_value < flag.percentage:
            flag.ab_group = "control"
            return False
        else:
            flag.ab_group = "treatment"
            return True
    
    def _check_schedule(self, flag: FeatureFlag) -> bool:
        """Check scheduled feature"""
        now = datetime.now()
        
        if flag.schedule_start and now < flag.schedule_start:
            return False
        
        if flag.schedule_end and now > flag.schedule_end:
            return False
        
        return flag.enabled
    
    def _check_dependencies(self, flag: FeatureFlag) -> bool:
        """Check if dependencies are met"""
        for dep in flag.depends_on:
            if not self.is_enabled(dep):
                return False
        return True
    
    def _has_conflicts(self, flag: FeatureFlag) -> bool:
        """Check for conflicts"""
        for conflict in flag.conflicts_with:
            if self.is_enabled(conflict):
                return True
        return False
    
    # ==========================================================================
    # USAGE TRACKING
    # ==========================================================================
    def _track_usage(self, feature_name: str, context: Optional[Dict[str, Any]]) -> None:
        """Track feature usage"""
        usage = FeatureUsage(
            feature_name=feature_name,
            timestamp=datetime.now(),
            user_id=self.user_id,
            session_id=self.session_id,
            context=context or {}
        )
        
        self.usage_log.append(usage)
        
        # Update flag usage stats
        flag = self.flags.get(feature_name)
        if flag:
            flag.usage_count += 1
            flag.last_used = datetime.now()
    
    def get_usage_stats(self, feature_name: Optional[str] = None) -> pd.DataFrame:
        """
        Get usage statistics.
        
        Args:
            feature_name: Optional specific feature
            
        Returns:
            DataFrame with usage stats
        """
        if feature_name:
            usage_data = [u for u in self.usage_log if u.feature_name == feature_name]
        else:
            usage_data = self.usage_log
        
        if not usage_data:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'feature': u.feature_name,
                'timestamp': u.timestamp,
                'user_id': u.user_id,
                'session_id': u.session_id,
                'outcome': u.outcome
            }
            for u in usage_data
        ])
        
        return df
    
    # ==========================================================================
    # CALLBACKS AND NOTIFICATIONS
    # ==========================================================================
    def register_callback(self, feature_name: str, callback: Callable[[str, bool], None]) -> None:
        """
        Register callback for feature changes.
        
        Args:
            feature_name: Feature to monitor
            callback: Callback function(feature_name, enabled)
        """
        if feature_name not in self.change_callbacks:
            self.change_callbacks[feature_name] = []
        
        self.change_callbacks[feature_name].append(callback)
    
    def _notify_change(self, feature_name: str, enabled: bool) -> None:
        """Notify callbacks of feature change"""
        # Call registered callbacks
        for callback in self.change_callbacks.get(feature_name, []):
            try:
                callback(feature_name, enabled)
            except Exception as e:
                self.logger.error(f"Error in feature callback: {e}")
        
        # Emit event if available
        if self.event_manager:
            self.event_manager.emit(Event(
                EventType.SYSTEM,
                {
                    'type': 'feature_flag_changed',
                    'feature': feature_name,
                    'enabled': enabled,
                    'timestamp': datetime.now()
                }
            ))
    
    # ==========================================================================
    # PERSISTENCE
    # ==========================================================================
    def _load_flags(self) -> None:
        """Load flags from file"""
        if not self.flags_file.exists():
            return
        
        try:
            with open(self.flags_file, 'r') as f:
                data = json.load(f)
            
            for flag_data in data.get('flags', []):
                flag = FeatureFlag.from_dict(flag_data)
                self.flags[flag.name] = flag
            
            self.logger.info(f"Loaded {len(self.flags)} feature flags")
            
        except Exception as e:
            self.logger.error(f"Error loading flags: {e}")
    
    def _save_flags(self) -> None:
        """Save flags to file"""
        try:
            # Create backup
            if self.flags_file.exists():
                backup_file = FLAGS_BACKUP_DIR / f"flags_backup_{datetime.now():%Y%m%d_%H%M%S}.json"
                self.flags_file.rename(backup_file)
            
            # Save current flags
            data = {
                'version': '1.0',
                'updated_at': datetime.now().isoformat(),
                'flags': [flag.to_dict() for flag in self.flags.values()]
            }
            
            with open(self.flags_file, 'w') as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            self.logger.error(f"Error saving flags: {e}")
    
    # ==========================================================================
    # DEFAULT FLAGS
    # ==========================================================================
    def _initialize_default_flags(self) -> None:
        """Initialize default feature flags"""
        default_flags = [
            # Strategy flags
            ('day_of_week_sizing', 'Monday position sizing (1-5%, others 0.5-2.5%)', 
             CATEGORY_STRATEGY, True),
            ('optimal_entry_window', 'Restrict entries to 10:15-11:40 AM', 
             CATEGORY_STRATEGY, True),
            ('time_based_exit', 'Exit positions at 12:00 PM', 
             CATEGORY_STRATEGY, True),
            ('iron_butterfly_strategy', 'Enable Iron Butterfly strategy', 
             CATEGORY_STRATEGY, False),
            ('directional_spreads', 'Enable directional credit spreads', 
             CATEGORY_STRATEGY, False),
            ('zero_dte_trading', 'Enable 0DTE trading', 
             CATEGORY_STRATEGY, False),
            
            # Risk flags
            ('enhanced_entry_filters', 'Use IVP, gap, RSI filters', 
             CATEGORY_RISK, True),
            ('volatility_regime_filter', 'Enable volatility regime detection', 
             CATEGORY_RISK, False),
            ('max_daily_trades', 'Enforce maximum daily trade limit', 
             CATEGORY_RISK, True),
            
            # UI flags
            ('day_of_week_dashboard', 'Show day-of-week performance in dashboard', 
             CATEGORY_UI, True),
            ('advanced_analytics', 'Enable advanced analytics views', 
             CATEGORY_UI, False),
            
            # Experimental
            ('ml_entry_optimization', 'Use ML for entry timing', 
             CATEGORY_EXPERIMENTAL, False),
            ('options_flow_analysis', 'Enable options flow analysis', 
             CATEGORY_EXPERIMENTAL, False),
        ]
        
        for name, description, category, enabled in default_flags:
            if name not in self.flags:
                self.create_flag(name, description, category, enabled)
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        return hashlib.md5(f"{datetime.now()}{random.random()}".encode()).hexdigest()[:16]
    
    def get_all_flags(self) -> Dict[str, FeatureFlag]:
        """Get all feature flags"""
        with self._lock:
            return self.flags.copy()
    
    def get_enabled_features(self) -> List[str]:
        """Get list of enabled features"""
        with self._lock:
            return [name for name, flag in self.flags.items() 
                   if self.is_enabled(name)]
    
    def export_configuration(self, filepath: Path) -> None:
        """Export current configuration"""
        with self._lock:
            data = {
                'exported_at': datetime.now().isoformat(),
                'flags': [flag.to_dict() for flag in self.flags.values()],
                'enabled_features': self.get_enabled_features()
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
    
    def import_configuration(self, filepath: Path) -> None:
        """Import configuration from file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        with self._lock:
            self.flags.clear()
            for flag_data in data.get('flags', []):
                flag = FeatureFlag.from_dict(flag_data)
                self.flags[flag.name] = flag
            
            self._save_flags()

# ==============================================================================
# GLOBAL INSTANCE
# ==============================================================================
_feature_flags_instance: Optional[FeatureFlagsManager] = None

def get_feature_flags() -> FeatureFlagsManager:
    """Get singleton instance of feature flags manager"""
    global _feature_flags_instance
    if _feature_flags_instance is None:
        _feature_flags_instance = FeatureFlagsManager()
    return _feature_flags_instance

# ==============================================================================
# DECORATOR
# ==============================================================================
def feature_flag(flag_name: str, default: bool = False):
    """
    Decorator to conditionally execute functions based on feature flags.
    
    Args:
        flag_name: Name of the feature flag
        default: Default behavior if flag doesn't exist
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            flags = get_feature_flags()
            if flags.is_enabled(flag_name):
                return func(*args, **kwargs)
            elif default:
                return func(*args, **kwargs)
            else:
                return None
        return wrapper
    return decorator

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test feature flags
    flags = FeatureFlagsManager()
    
    # Check default flags
    print("Default Feature Flags:")
    for name, flag in flags.get_all_flags().items():
        status = "ENABLED" if flags.is_enabled(name) else "DISABLED"
        print(f"  {name}: {status}")
    
    # Test enabling/disabling
    print("\nTesting flag operations:")
    flags.disable('day_of_week_sizing')
    print(f"day_of_week_sizing: {flags.is_enabled('day_of_week_sizing')}")
    
    flags.enable('day_of_week_sizing', percentage=50)
    print(f"day_of_week_sizing (50%): {flags.is_enabled('day_of_week_sizing')}")
    
    # Test A/B testing
    flags.setup_ab_test('ml_entry_optimization', control_percentage=50)
    print(f"ml_entry_optimization (A/B): {flags.is_enabled('ml_entry_optimization')}")
    
    # Test scheduling
    start = datetime.now() + timedelta(minutes=1)
    end = datetime.now() + timedelta(hours=1)
    flags.schedule_feature('options_flow_analysis', start, end)
    print(f"options_flow_analysis (scheduled): {flags.is_enabled('options_flow_analysis')}")
    
    # Test decorator
    @feature_flag('day_of_week_sizing')
    def test_function():
        return "Function executed!"
    
    result = test_function()
    print(f"\nDecorator test: {result}")
    
    # Export configuration
    flags.export_configuration(Path("feature_flags_export.json"))
    print("\nConfiguration exported to feature_flags_export.json")


class FeatureFlags:
    """Feature flags for enabling/disabling features."""
    
    def __init__(self):
        self.features = {}
    
    def is_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled."""
        return self.features.get(feature, False)
    
    def enable(self, feature: str):
        """Enable a feature."""
        self.features[feature] = True
    
    def disable(self, feature: str):
        """Disable a feature."""
        self.features[feature] = False

# ==============================================================================
# SPYDERX MIGRATION FEATURE FLAGS
# ==============================================================================
# Added for gradual SpyderF to SpyderX migration
SPYDERX_FEATURE_FLAGS = {
    "USE_AI_GREEKS": False,  # Start disabled
    "USE_AI_RISK": False,
    "USE_AI_MARKET_ANALYSIS": True,  # Start with low-risk features
    "ENABLE_SPYDERX_SHADOW": True,  # Run in shadow mode
    "LOG_AI_DIVERGENCE": True,  # Log differences between F and X
    "AI_CONFIDENCE_THRESHOLD": 0.8,  # Minimum confidence for AI decisions
}

# Helper function to check SpyderX features
def is_spyderx_enabled(feature: str) -> bool:
    """Check if a SpyderX feature is enabled"""
    return SPYDERX_FEATURE_FLAGS.get(feature, False)

# Migration tracking
MIGRATION_STATUS = {
    "spyderf_modules_active": [
        "SpyderF01_Indicators",
        "SpyderF02_PriceAction", 
        "SpyderF03_SupportResistance",
        "SpyderF04_VolatilityAnalysis",
        "SpyderF05_TrendDetection",
        "SpyderF06_GreeksCalculator",
        "SpyderF07_GapAnalyzer",
        "SpyderF08_VolatilityRegime",
        "SpyderF09_EntryFilters",
        "SpyderF10_MarketRegimeDetector"
    ],
    "spyderx_modules_shadow": [
        "SpyderX13_MarketAnalysisAgent",
        "SpyderX01_GreeksAgent"
    ],
    "spyderx_modules_active": []
}
