#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderE11_MaxLossProtection.py
Group: E (Risk Management)
Purpose: Critical maximum loss protection and circuit breakers
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 14:30:00

Description:
    This module provides critical maximum loss protection mechanisms including
    daily, weekly, and monthly loss limits, automatic trading suspension when
    limits are breached, account-level circuit breakers, strategy-specific
    limits, and recovery protocols. It acts as the last line of defense to
    protect capital and prevent catastrophic losses.

Key Features:
    - Multi-timeframe loss limits (daily/weekly/monthly/yearly)
    - Real-time P&L tracking and monitoring
    - Automatic trading suspension on breach
    - Strategy-specific loss limits
    - Account-level circuit breakers
    - Graduated response system
    - Recovery protocols and cool-down periods
    - Integration with all trading modules
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import threading
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType, get_event_manager

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default loss limits (percentages of account value)
DEFAULT_DAILY_LIMIT = 2.0  # 2% daily loss limit
DEFAULT_WEEKLY_LIMIT = 5.0  # 5% weekly loss limit
DEFAULT_MONTHLY_LIMIT = 10.0  # 10% monthly loss limit
DEFAULT_YEARLY_LIMIT = 20.0  # 20% yearly loss limit

# Absolute dollar limits (override percentages)
DEFAULT_DAILY_DOLLAR_LIMIT = 10000  # $10,000
DEFAULT_WEEKLY_DOLLAR_LIMIT = 25000  # $25,000
DEFAULT_MONTHLY_DOLLAR_LIMIT = 50000  # $50,000
DEFAULT_YEARLY_DOLLAR_LIMIT = 100000  # $100,000

# Cool-down periods (minutes)
COOLDOWN_MINOR = 15  # 15 minutes for minor breach
COOLDOWN_MAJOR = 60  # 1 hour for major breach
COOLDOWN_CRITICAL = 240  # 4 hours for critical breach
COOLDOWN_EMERGENCY = 1440  # 24 hours for emergency

# Warning thresholds (percentage of limit)
WARNING_THRESHOLD_1 = 0.5  # 50% of limit
WARNING_THRESHOLD_2 = 0.75  # 75% of limit
WARNING_THRESHOLD_3 = 0.9  # 90% of limit

# ==============================================================================
# HELPERS
# ==============================================================================

def _json_default(obj):
    """JSON serialization helper: converts datetime/Enum/dataclass for json.dump."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, '__dataclass_fields__'):
        return asdict(obj)
    return str(obj)


# ==============================================================================
# ENUMS
# ==============================================================================
class LimitType(Enum):
    """Types of loss limits"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    STRATEGY = "strategy"
    POSITION = "position"
    SYMBOL = "symbol"

class BreachSeverity(Enum):
    """Severity levels for limit breaches"""
    WARNING = "warning"  # Approaching limit
    MINOR = "minor"  # Slightly over limit
    MAJOR = "major"  # Significantly over limit
    CRITICAL = "critical"  # Dangerously over limit
    EMERGENCY = "emergency"  # Catastrophic breach

class SystemAction(Enum):
    """Actions taken by the protection system"""
    MONITOR = "monitor"
    WARN = "warn"
    REDUCE_SIZE = "reduce_size"
    STOP_NEW = "stop_new"
    CLOSE_RISKY = "close_risky"
    CLOSE_ALL = "close_all"
    EMERGENCY_STOP = "emergency_stop"

class RecoveryState(Enum):
    """Recovery states after breach"""
    NORMAL = "normal"
    COOLDOWN = "cooldown"
    RESTRICTED = "restricted"
    RECOVERY = "recovery"
    SUSPENDED = "suspended"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class LossLimit:
    """Loss limit configuration"""
    limit_type: LimitType
    limit_name: str
    percentage_limit: float
    dollar_limit: float
    current_loss: float = 0.0
    is_active: bool = True
    last_reset: datetime = field(default_factory=datetime.now)
    breach_count: int = 0

    @property
    def effective_limit(self) -> float:
        """Get the effective limit (smaller of percentage or dollar)"""
        return min(self.percentage_limit, self.dollar_limit) if self.dollar_limit > 0 else self.percentage_limit

    @property
    def utilization(self) -> float:
        """Get current utilization percentage"""
        if self.effective_limit == 0:
            return 0.0
        return abs(self.current_loss) / self.effective_limit * 100

@dataclass
class BreachEvent:
    """Record of a limit breach"""
    timestamp: datetime
    limit_type: LimitType
    limit_name: str
    severity: BreachSeverity
    loss_amount: float
    limit_amount: float
    action_taken: SystemAction
    positions_affected: list[str]
    recovery_required: bool = True

@dataclass
class RecoveryPlan:
    """Recovery plan after breach"""
    breach_event: BreachEvent
    recovery_state: RecoveryState
    cooldown_minutes: int
    cooldown_end: datetime
    restrictions: list[str]
    allowed_actions: list[str]
    monitoring_level: str

@dataclass
class ProtectionStatus:
    """Current protection system status"""
    is_active: bool
    trading_allowed: bool
    new_positions_allowed: bool
    current_state: RecoveryState
    active_limits: list[LossLimit]
    breached_limits: list[LossLimit]
    warnings: list[str]
    last_update: datetime

# ==============================================================================
# MAIN MAX LOSS PROTECTION CLASS
# ==============================================================================
class MaxLossProtection:
    """
    Maximum Loss Protection System.

    Provides comprehensive loss protection with multiple timeframes,
    automatic trading suspension, and recovery protocols.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize Max Loss Protection"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}

        # Event manager for notifications
        self.event_manager = get_event_manager()

        # Threading
        self._lock = threading.RLock()
        self._shutdown = threading.Event()

        # Loss limits
        self.limits = {}
        self.strategy_limits = {}
        self.symbol_limits = {}

        # Tracking
        self.current_pnl = 0.0
        self.account_value = self.config.get('account_value', 1000000)
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.monthly_pnl = 0.0
        self.yearly_pnl = 0.0

        # Breach tracking
        self.breach_history = deque(maxlen=1000)
        self.active_breaches = []
        self.recovery_plans = []

        # Status
        self.protection_status = ProtectionStatus(
            is_active=True,
            trading_allowed=True,
            new_positions_allowed=True,
            current_state=RecoveryState.NORMAL,
            active_limits=[],
            breached_limits=[],
            warnings=[],
            last_update=datetime.now()
        )

        # Position tracking
        self.position_pnl = defaultdict(float)
        self.strategy_pnl = defaultdict(float)
        self.symbol_pnl = defaultdict(float)

        # Initialize limits
        self._initialize_limits()

        # Load historical data
        self._load_history()

        self.logger.info("Max Loss Protection initialized")

    def _initialize_limits(self):
        """Initialize default loss limits"""
        # Time-based limits
        self.limits['daily'] = LossLimit(
            limit_type=LimitType.DAILY,
            limit_name="Daily Loss Limit",
            percentage_limit=self.config.get('daily_limit_pct', DEFAULT_DAILY_LIMIT),
            dollar_limit=self.config.get('daily_limit_dollar', DEFAULT_DAILY_DOLLAR_LIMIT)
        )

        self.limits['weekly'] = LossLimit(
            limit_type=LimitType.WEEKLY,
            limit_name="Weekly Loss Limit",
            percentage_limit=self.config.get('weekly_limit_pct', DEFAULT_WEEKLY_LIMIT),
            dollar_limit=self.config.get('weekly_limit_dollar', DEFAULT_WEEKLY_DOLLAR_LIMIT)
        )

        self.limits['monthly'] = LossLimit(
            limit_type=LimitType.MONTHLY,
            limit_name="Monthly Loss Limit",
            percentage_limit=self.config.get('monthly_limit_pct', DEFAULT_MONTHLY_LIMIT),
            dollar_limit=self.config.get('monthly_limit_dollar', DEFAULT_MONTHLY_DOLLAR_LIMIT)
        )

        self.limits['yearly'] = LossLimit(
            limit_type=LimitType.YEARLY,
            limit_name="Yearly Loss Limit",
            percentage_limit=self.config.get('yearly_limit_pct', DEFAULT_YEARLY_LIMIT),
            dollar_limit=self.config.get('yearly_limit_dollar', DEFAULT_YEARLY_DOLLAR_LIMIT)
        )

        # Update active limits
        self.protection_status.active_limits = list(self.limits.values())

        self.logger.info("Initialized %s loss limits", len(self.limits))

    def _load_history(self):
        """Load historical breach data"""
        try:
            history_file = Path("data/risk/breach_history.json")
            # Backward-compat: migrate from legacy .pkl if .json not present
            if not history_file.exists():
                legacy = history_file.with_suffix('.pkl')
                if legacy.exists():
                    import joblib as _joblib
                    with open(legacy, 'rb') as _f:
                        _data = _joblib.load(_f)
                    history_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(history_file, 'w', encoding='utf-8') as _f:
                        json.dump(_data, _f, default=_json_default, indent=2)
            if history_file.exists():
                with open(history_file, encoding='utf-8') as f:
                    data = json.load(f)
                    self.breach_history = deque(data['breaches'], maxlen=1000)
                    self.logger.info("Loaded %s historical breaches", len(self.breach_history))
        except Exception as e:
            self.logger.warning("Could not load breach history: %s", e)

    def _save_history(self):
        """Save breach history"""
        try:
            history_file = Path("data/risk/breach_history.json")
            history_file.parent.mkdir(parents=True, exist_ok=True)

            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'breaches': list(self.breach_history),
                    'timestamp': datetime.now()
                }, f, default=_json_default, indent=2)
        except Exception as e:
            self.logger.error("Could not save breach history: %s", e)

    def update_pnl(
        self,
        total_pnl: float,
        position_pnl: dict[str, float] | None = None,
        strategy_pnl: dict[str, float] | None = None,
        symbol_pnl: dict[str, float] | None = None
    ) -> ProtectionStatus:
        """
        Update P&L and check for breaches.

        Args:
            total_pnl: Total current P&L
            position_pnl: P&L by position
            strategy_pnl: P&L by strategy
            symbol_pnl: P&L by symbol

        Returns:
            Current protection status
        """
        with self._lock:
            try:
                # Update P&L tracking
                self.current_pnl = total_pnl

                if position_pnl:
                    self.position_pnl.update(position_pnl)
                if strategy_pnl:
                    self.strategy_pnl.update(strategy_pnl)
                if symbol_pnl:
                    self.symbol_pnl.update(symbol_pnl)

                # Update time-based P&L
                self._update_timeframe_pnl()

                # Check all limits
                breaches = self._check_all_limits()

                # Handle any breaches
                if breaches:
                    self._handle_breaches(breaches)

                # Check for warnings
                self._check_warnings()

                # Update status
                self._update_status()

                return self.protection_status

            except Exception as e:
                self.logger.error("Error updating P&L: %s", e)
                self.error_handler.handle_error(e, {"method": "update_pnl"})
                return self.protection_status

    def _update_timeframe_pnl(self):
        """Update timeframe-based P&L"""
        now = datetime.now()

        # Daily P&L (reset at midnight)
        if now.date() != self.limits['daily'].last_reset.date():
            self.daily_pnl = self.current_pnl
            self.limits['daily'].last_reset = now
            self.limits['daily'].current_loss = 0
        else:
            daily_change = self.current_pnl - self.daily_pnl
            if daily_change < 0:
                self.limits['daily'].current_loss = abs(daily_change)

        # Weekly P&L (reset on Monday)
        week_start = now - timedelta(days=now.weekday())
        if week_start.date() > self.limits['weekly'].last_reset.date():
            self.weekly_pnl = self.current_pnl
            self.limits['weekly'].last_reset = week_start
            self.limits['weekly'].current_loss = 0
        else:
            weekly_change = self.current_pnl - self.weekly_pnl
            if weekly_change < 0:
                self.limits['weekly'].current_loss = abs(weekly_change)

        # Monthly P&L (reset on 1st)
        if now.month != self.limits['monthly'].last_reset.month:
            self.monthly_pnl = self.current_pnl
            self.limits['monthly'].last_reset = now
            self.limits['monthly'].current_loss = 0
        else:
            monthly_change = self.current_pnl - self.monthly_pnl
            if monthly_change < 0:
                self.limits['monthly'].current_loss = abs(monthly_change)

        # Yearly P&L (reset on Jan 1)
        if now.year != self.limits['yearly'].last_reset.year:
            self.yearly_pnl = self.current_pnl
            self.limits['yearly'].last_reset = now
            self.limits['yearly'].current_loss = 0
        else:
            yearly_change = self.current_pnl - self.yearly_pnl
            if yearly_change < 0:
                self.limits['yearly'].current_loss = abs(yearly_change)

    def _check_all_limits(self) -> list[tuple[LossLimit, BreachSeverity]]:
        """Check all limits for breaches"""
        breaches = []

        for _limit_key, limit in self.limits.items():
            if not limit.is_active:
                continue

            # Calculate effective limit based on account value
            if limit.percentage_limit > 0:
                pct_limit = self.account_value * (limit.percentage_limit / 100)
            else:
                pct_limit = float('inf')

            dollar_limit = limit.dollar_limit if limit.dollar_limit > 0 else float('inf')
            effective_limit = min(pct_limit, dollar_limit)

            # Check for breach
            if limit.current_loss > effective_limit:
                severity = self._determine_severity(limit.current_loss, effective_limit)
                breaches.append((limit, severity))
                self.logger.warning(
                    f"{limit.limit_name} BREACHED: Loss ${limit.current_loss:.2f} > "
                    f"Limit ${effective_limit:.2f} (Severity: {severity.value})"
                )

        # Check strategy limits
        for strategy, limit in self.strategy_limits.items():
            if strategy in self.strategy_pnl:
                loss = abs(min(0, self.strategy_pnl[strategy]))
                if loss > limit['max_loss']:
                    severity = self._determine_severity(loss, limit['max_loss'])
                    strategy_limit = LossLimit(
                        limit_type=LimitType.STRATEGY,
                        limit_name=f"Strategy: {strategy}",
                        percentage_limit=0,
                        dollar_limit=limit['max_loss'],
                        current_loss=loss
                    )
                    breaches.append((strategy_limit, severity))

        return breaches

    def _determine_severity(self, loss: float, limit: float) -> BreachSeverity:
        """Determine breach severity"""
        if limit == 0:
            return BreachSeverity.EMERGENCY

        ratio = loss / limit

        if ratio < 1.0:
            return BreachSeverity.WARNING
        elif ratio < 1.1:
            return BreachSeverity.MINOR
        elif ratio < 1.25:
            return BreachSeverity.MAJOR
        elif ratio < 1.5:
            return BreachSeverity.CRITICAL
        else:
            return BreachSeverity.EMERGENCY

    def _handle_breaches(self, breaches: list[tuple[LossLimit, BreachSeverity]]):
        """Handle limit breaches"""
        for limit, severity in breaches:
            # Create breach event
            breach_event = BreachEvent(
                timestamp=datetime.now(),
                limit_type=limit.limit_type,
                limit_name=limit.limit_name,
                severity=severity,
                loss_amount=limit.current_loss,
                limit_amount=limit.effective_limit,
                action_taken=self._determine_action(severity),
                positions_affected=self._get_affected_positions(limit)
            )

            # Record breach
            self.breach_history.append(breach_event)
            self.active_breaches.append(breach_event)
            limit.breach_count += 1

            # Take action
            self._execute_action(breach_event)

            # Create recovery plan
            recovery_plan = self._create_recovery_plan(breach_event)
            self.recovery_plans.append(recovery_plan)

            # Send notifications
            self._send_breach_notification(breach_event)

            # Update breached limits
            if limit not in self.protection_status.breached_limits:
                self.protection_status.breached_limits.append(limit)

    def _determine_action(self, severity: BreachSeverity) -> SystemAction:
        """Determine action based on severity"""
        action_map = {
            BreachSeverity.WARNING: SystemAction.WARN,
            BreachSeverity.MINOR: SystemAction.STOP_NEW,
            BreachSeverity.MAJOR: SystemAction.CLOSE_RISKY,
            BreachSeverity.CRITICAL: SystemAction.CLOSE_ALL,
            BreachSeverity.EMERGENCY: SystemAction.EMERGENCY_STOP
        }
        return action_map.get(severity, SystemAction.MONITOR)

    def _execute_action(self, breach_event: BreachEvent):
        """Execute protective action"""
        action = breach_event.action_taken

        if action == SystemAction.WARN:
            self.logger.warning("WARNING: %s approaching limit", breach_event.limit_name)

        elif action == SystemAction.STOP_NEW:
            self.protection_status.new_positions_allowed = False
            self.logger.warning("New position opening DISABLED")

        elif action == SystemAction.CLOSE_RISKY:
            self.protection_status.new_positions_allowed = False
            self._close_risky_positions()
            self.logger.warning("Closing risky positions")

        elif action == SystemAction.CLOSE_ALL:
            self.protection_status.trading_allowed = False
            self._close_all_positions()
            self.logger.critical("CLOSING ALL POSITIONS")

        elif action == SystemAction.EMERGENCY_STOP:
            self.protection_status.trading_allowed = False
            self.protection_status.is_active = False
            self._emergency_stop()
            self.logger.critical("EMERGENCY STOP - ALL TRADING HALTED")

    def _close_risky_positions(self):
        """Close positions with highest risk"""
        # This would interface with position manager
        risky_positions = []

        # Find positions with largest losses
        for position_id, pnl in self.position_pnl.items():
            if pnl < -1000:  # Positions with >$1000 loss
                risky_positions.append(position_id)

        # Send close orders
        for position_id in risky_positions:
            self.event_manager.emit(Event(
                EventType.RISK_EVENT,
                {
                    'action': 'close_position',
                    'position_id': position_id,
                    'reason': 'max_loss_protection'
                }
            ))

    def _close_all_positions(self):
        """Close all open positions"""
        # Send emergency close event
        self.event_manager.emit(Event(
            EventType.RISK_EVENT,
            {
                'action': 'close_all_positions',
                'reason': 'max_loss_breach',
                'urgency': 'immediate'
            }
        ))

    def _emergency_stop(self):
        """Emergency stop all trading"""
        # Send emergency stop event
        self.event_manager.emit(Event(
            EventType.EMERGENCY,
            {
                'action': 'emergency_stop',
                'reason': 'catastrophic_loss',
                'require_manual_restart': True
            }
        ))

        # Save state for post-mortem
        self._save_emergency_state()

    def _save_emergency_state(self):
        """Save system state for analysis"""
        try:
            emergency_file = Path(f"data/risk/emergency_{datetime.now():%Y%m%d_%H%M%S}.json")
            emergency_file.parent.mkdir(parents=True, exist_ok=True)

            state = {
                'timestamp': datetime.now().isoformat(),
                'current_pnl': self.current_pnl,
                'limits': {k: asdict(v) for k, v in self.limits.items()},
                'active_breaches': [asdict(b) for b in self.active_breaches],
                'position_pnl': dict(self.position_pnl),
                'strategy_pnl': dict(self.strategy_pnl),
                'symbol_pnl': dict(self.symbol_pnl)
            }

            with open(emergency_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)

            self.logger.info("Emergency state saved to %s", emergency_file)

        except Exception as e:
            self.logger.error("Failed to save emergency state: %s", e)

    def _get_affected_positions(self, limit: LossLimit) -> list[str]:
        """Get positions affected by limit breach"""
        affected = []

        if limit.limit_type == LimitType.STRATEGY:
            # Get positions for this strategy
            strategy_name = limit.limit_name.replace("Strategy: ", "")
            # This would query position manager for strategy positions
            affected = [f"pos_{strategy_name}_1", f"pos_{strategy_name}_2"]
        else:
            # All positions affected for time-based limits
            affected = list(self.position_pnl.keys())

        return affected

    def _create_recovery_plan(self, breach_event: BreachEvent) -> RecoveryPlan:
        """Create recovery plan after breach"""
        # Determine cooldown period
        cooldown_map = {
            BreachSeverity.WARNING: 0,
            BreachSeverity.MINOR: COOLDOWN_MINOR,
            BreachSeverity.MAJOR: COOLDOWN_MAJOR,
            BreachSeverity.CRITICAL: COOLDOWN_CRITICAL,
            BreachSeverity.EMERGENCY: COOLDOWN_EMERGENCY
        }

        cooldown_minutes = cooldown_map.get(breach_event.severity, COOLDOWN_MINOR)
        cooldown_end = datetime.now() + timedelta(minutes=cooldown_minutes)

        # Determine restrictions
        restrictions = []
        allowed_actions = []

        if breach_event.severity == BreachSeverity.WARNING:
            restrictions = ["increased_monitoring"]
            allowed_actions = ["all_trading"]
        elif breach_event.severity == BreachSeverity.MINOR:
            restrictions = ["no_new_positions", "reduced_size"]
            allowed_actions = ["close_only", "hedging"]
        elif breach_event.severity == BreachSeverity.MAJOR:
            restrictions = ["no_new_positions", "close_risky"]
            allowed_actions = ["close_only"]
        elif breach_event.severity == BreachSeverity.CRITICAL:
            restrictions = ["no_trading", "close_all"]
            allowed_actions = ["emergency_close"]
        else:  # EMERGENCY
            restrictions = ["full_suspension"]
            allowed_actions = []

        return RecoveryPlan(
            breach_event=breach_event,
            recovery_state=RecoveryState.COOLDOWN,
            cooldown_minutes=cooldown_minutes,
            cooldown_end=cooldown_end,
            restrictions=restrictions,
            allowed_actions=allowed_actions,
            monitoring_level="high"
        )

    def _check_warnings(self):
        """Check for warning conditions"""
        warnings = []

        for _limit_key, limit in self.limits.items():
            if not limit.is_active:
                continue

            utilization = limit.utilization

            if utilization >= WARNING_THRESHOLD_3 * 100:
                warnings.append(f"⚠️ CRITICAL: {limit.limit_name} at {utilization:.1f}%")
            elif utilization >= WARNING_THRESHOLD_2 * 100:
                warnings.append(f"⚠️ HIGH: {limit.limit_name} at {utilization:.1f}%")
            elif utilization >= WARNING_THRESHOLD_1 * 100:
                warnings.append(f"⚠️ {limit.limit_name} at {utilization:.1f}%")

        self.protection_status.warnings = warnings

    def _update_status(self):
        """Update protection status"""
        with self._lock:
            # Check recovery plans
            active_plans = [p for p in self.recovery_plans
                          if p.cooldown_end > datetime.now()]

            if active_plans:
                # Use most restrictive plan
                most_restrictive = max(active_plans,
                                      key=lambda p: p.breach_event.severity.value)
                self.protection_status.current_state = most_restrictive.recovery_state
            else:
                self.protection_status.current_state = RecoveryState.NORMAL

            # Update trading permissions based on active breaches
            if self.active_breaches:
                latest_breach = self.active_breaches[-1]
                if latest_breach.severity in [BreachSeverity.CRITICAL, BreachSeverity.EMERGENCY]:
                    self.protection_status.trading_allowed = False
                elif latest_breach.severity == BreachSeverity.MAJOR:
                    self.protection_status.new_positions_allowed = False

            self.protection_status.last_update = datetime.now()

    def _send_breach_notification(self, breach_event: BreachEvent):
        """Send breach notification"""
        self.event_manager.emit(Event(
            EventType.ALERT,
            {
                'severity': breach_event.severity.value,
                'message': f"LOSS LIMIT BREACH: {breach_event.limit_name}",
                'details': {
                    'loss': breach_event.loss_amount,
                    'limit': breach_event.limit_amount,
                    'action': breach_event.action_taken.value
                }
            }
        ))

    def add_strategy_limit(self, strategy_name: str, max_loss: float):
        """Add strategy-specific loss limit"""
        self.strategy_limits[strategy_name] = {
            'max_loss': max_loss,
            'current_loss': 0.0,
            'is_active': True
        }
        self.logger.info("Added loss limit for strategy %s: $%s", strategy_name, max_loss)

    def add_symbol_limit(self, symbol: str, max_loss: float):
        """Add symbol-specific loss limit"""
        self.symbol_limits[symbol] = {
            'max_loss': max_loss,
            'current_loss': 0.0,
            'is_active': True
        }
        self.logger.info("Added loss limit for symbol %s: $%s", symbol, max_loss)

    def can_open_position(self, strategy: str = None, symbol: str = None) -> tuple[bool, str]:
        """
        Check if new position can be opened.

        Returns:
            Tuple of (allowed, reason)
        """
        if not self.protection_status.trading_allowed:
            return False, "Trading suspended due to loss limit breach"

        if not self.protection_status.new_positions_allowed:
            return False, "New positions disabled due to loss limit warning"

        # Check strategy limit
        if strategy and strategy in self.strategy_limits:
            limit = self.strategy_limits[strategy]
            if self.strategy_pnl.get(strategy, 0) <= -limit['max_loss']:
                return False, f"Strategy {strategy} has reached loss limit"

        # Check symbol limit
        if symbol and symbol in self.symbol_limits:
            limit = self.symbol_limits[symbol]
            if self.symbol_pnl.get(symbol, 0) <= -limit['max_loss']:
                return False, f"Symbol {symbol} has reached loss limit"

        # Check if in cooldown
        if self.protection_status.current_state == RecoveryState.COOLDOWN:
            return False, "System in cooldown period"

        return True, "Position opening allowed"

    def reset_limits(self, limit_type: str = None):
        """Reset loss limits (use with caution)"""
        if limit_type:
            if limit_type in self.limits:
                self.limits[limit_type].current_loss = 0
                self.limits[limit_type].last_reset = datetime.now()
                self.logger.info("Reset %s limit", limit_type)
        else:
            # Reset all limits
            for limit in self.limits.values():
                limit.current_loss = 0
                limit.last_reset = datetime.now()
            self.logger.info("Reset all limits")

    def get_status_report(self) -> dict[str, Any]:
        """Get comprehensive status report"""
        return {
            'protection_active': self.protection_status.is_active,
            'trading_allowed': self.protection_status.trading_allowed,
            'new_positions_allowed': self.protection_status.new_positions_allowed,
            'current_state': self.protection_status.current_state.value,
            'current_pnl': self.current_pnl,
            'limits': {
                name: {
                    'current_loss': limit.current_loss,
                    'limit': limit.effective_limit,
                    'utilization': f"{limit.utilization:.1f}%",
                    'breaches': limit.breach_count
                }
                for name, limit in self.limits.items()
            },
            'active_breaches': len(self.active_breaches),
            'warnings': self.protection_status.warnings,
            'recovery_plans': len([p for p in self.recovery_plans
                                  if p.cooldown_end > datetime.now()])
        }

    def emergency_override(self, admin_password: str) -> bool:
        """
        Emergency override (requires admin password).

        SECURITY: Password must be set via EMERGENCY_OVERRIDE_PASSWORD environment variable.
        Never hardcode passwords in source code.

        Args:
            admin_password: Password provided by administrator

        Returns:
            bool: True if override successful, False otherwise
        """
        import os

        # Load password from environment variable (NEVER hardcode!)
        expected_password = os.environ.get("EMERGENCY_OVERRIDE_PASSWORD")

        if not expected_password:
            self.logger.error("EMERGENCY_OVERRIDE_PASSWORD not configured in environment")
            return False

        if admin_password == expected_password:
            self.logger.critical("EMERGENCY OVERRIDE ACTIVATED")

            # Reset all states
            self.protection_status.is_active = True
            self.protection_status.trading_allowed = True
            self.protection_status.new_positions_allowed = True
            self.protection_status.current_state = RecoveryState.NORMAL
            self.active_breaches.clear()
            self.recovery_plans.clear()

            return True

        self.logger.warning("Invalid emergency override attempt")
        return False

    def shutdown(self):
        """Shutdown protection system"""
        self._shutdown.set()
        self._save_history()
        self.logger.info("Max Loss Protection shutdown complete")


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_max_loss_protection(config: dict[str, Any] | None = None) -> MaxLossProtection:
    """Create and initialize MaxLossProtection instance"""
    return MaxLossProtection(config)


# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":
    # Test configuration
    config = {
        'account_value': 100000,
        'daily_limit_pct': 2.0,
        'daily_limit_dollar': 2000,
        'weekly_limit_pct': 5.0,
        'weekly_limit_dollar': 5000
    }

    # Create protection system
    protection = create_max_loss_protection(config)


    # Simulate P&L updates
    test_pnls = [
        -500,   # Small loss
        -1000,  # Moderate loss
        -1500,  # Approaching daily limit
        -2100,  # Breach daily limit
    ]

    for pnl in test_pnls:
        status = protection.update_pnl(pnl)


        if status.warnings:
            for _warning in status.warnings:
                pass

    # Get status report
    report = protection.get_status_report()

    # Check if position can be opened
    can_open, reason = protection.can_open_position("IronCondor", "SPY")

    # Shutdown
    protection.shutdown()
