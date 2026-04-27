#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE04_DrawdownControl.py
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
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics
import pandas as pd

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    import logging
    SpyderLogger = type('SpyderLogger', (), {
        'get_logger': lambda name: logging.getLogger(name)
    })()

try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    SpyderErrorHandler = type('SpyderErrorHandler', (), {
        'handle_error': lambda self, e, context: logging.warning("Error in %s: %s", context, e)
    })

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Drawdown Thresholds
WARNING_THRESHOLD = 0.05      # 5% - Warning level
CAUTION_THRESHOLD = 0.10      # 10% - Reduce position sizes
CRITICAL_THRESHOLD = 0.15     # 15% - Major risk reduction
EMERGENCY_THRESHOLD = 0.20    # 20% - Stop new trades
SHUTDOWN_THRESHOLD = 0.25     # 25% - Close all positions

# Recovery Thresholds
RECOVERY_START = 0.50         # 50% recovery from max drawdown
RECOVERY_NORMAL = 0.80        # 80% recovery to resume normal trading

# Risk Adjustments
POSITION_SIZE_MULTIPLIERS = {
    'normal': 1.0,
    'warning': 0.9,
    'caution': 0.7,
    'critical': 0.5,
    'emergency': 0.25,
    'shutdown': 0.0
}

# Monitoring
DRAWDOWN_CHECK_INTERVAL = 30  # seconds
RECOVERY_CHECK_INTERVAL = 60  # seconds
HISTORY_LOOKBACK = 252       # Trading days

# ==============================================================================
# ENUMS
# ==============================================================================
class DrawdownState(Enum):
    """Current drawdown state."""
    NORMAL = "normal"
    WARNING = "warning"
    CAUTION = "caution"
    CRITICAL = "critical"
    EMERGENCY = "emergency"
    SHUTDOWN = "shutdown"
    RECOVERY = "recovery"

class RecoveryPhase(Enum):
    """Recovery phase after drawdown."""
    NONE = "none"
    EARLY = "early"
    MIDDLE = "middle"
    LATE = "late"
    COMPLETE = "complete"

class DrawdownAction(Enum):
    """Actions taken during drawdown."""
    NONE = "none"
    REDUCE_SIZE = "reduce_size"
    STOP_NEW_TRADES = "stop_new_trades"
    REDUCE_POSITIONS = "reduce_positions"
    CLOSE_LOSING = "close_losing"
    CLOSE_ALL = "close_all"
    HEDGE = "hedge"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class DrawdownMetrics:
    """Drawdown metrics and statistics."""
    current_drawdown: float
    max_drawdown: float
    drawdown_start_date: datetime | None
    drawdown_start_value: float
    peak_value: float
    peak_date: datetime
    trough_value: float
    trough_date: datetime | None
    days_in_drawdown: int
    recovery_days: int | None = None
    drawdown_state: DrawdownState = DrawdownState.NORMAL
    recovery_phase: RecoveryPhase = RecoveryPhase.NONE

@dataclass
class DrawdownEvent:
    """Record of a drawdown event."""
    event_id: str
    start_date: datetime
    end_date: datetime | None
    start_value: float
    trough_value: float
    end_value: float | None
    max_drawdown: float
    duration_days: int
    recovery_days: int | None
    drawdown_state_reached: DrawdownState
    actions_taken: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class RiskAdjustment:
    """Risk adjustment parameters."""
    position_size_multiplier: float
    max_positions: int
    allow_new_trades: bool
    require_stops: bool
    max_loss_per_trade: float
    allowed_strategies: list[str]
    restrictions: list[str]

@dataclass
class RecoveryPlan:
    """Recovery plan after drawdown."""
    phase: RecoveryPhase
    target_equity: float
    allowed_risk: float
    position_size_multiplier: float
    strategies_allowed: list[str]
    milestones: list[float]
    current_milestone: int

# ==============================================================================
# DRAWDOWN CONTROLLER CLASS
# ==============================================================================
class DrawdownController:
    """
    Controls portfolio drawdown and manages recovery.

    Monitors equity curve for drawdowns, implements risk reduction strategies
    at various thresholds, and manages the recovery process. Thread-safe
    implementation with comprehensive tracking and reporting.

    Attributes:
        current_metrics: Current drawdown metrics
        current_state: Current drawdown state
        peak_equity: Historical peak equity value

    Example:
        >>> controller = DrawdownController(initial_equity=100000)
        >>> metrics = controller.update_equity(95000)
        >>> if metrics.drawdown_state == DrawdownState.CAUTION:
        ...     adjustments = controller.get_risk_adjustments()
        ...     # Apply risk adjustments
    """

    def __init__(self, initial_equity: float = 100_000.0, config: dict[str, Any] | None = None):
        """
        Initialize drawdown controller.

        Args:
            initial_equity: Starting equity value
            config: Optional configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}
        self.initial_equity = initial_equity

        # Thresholds (configurable)
        self.warning_threshold = self.config.get('warning_threshold', WARNING_THRESHOLD)
        self.caution_threshold = self.config.get('caution_threshold', CAUTION_THRESHOLD)
        self.critical_threshold = self.config.get('critical_threshold', CRITICAL_THRESHOLD)
        self.emergency_threshold = self.config.get('emergency_threshold', EMERGENCY_THRESHOLD)
        self.shutdown_threshold = self.config.get('shutdown_threshold', SHUTDOWN_THRESHOLD)

        # State management with thread safety
        self._lock = threading.RLock()

        # Current state
        self.peak_equity = initial_equity
        self.current_equity = initial_equity
        self.current_metrics = self._create_initial_metrics()
        self.current_state = DrawdownState.NORMAL
        self.recovery_plan: RecoveryPlan | None = None

        # History tracking
        self.equity_history: deque = deque(maxlen=HISTORY_LOOKBACK * 2)
        self.equity_history.append((datetime.now(), initial_equity))

        self.drawdown_history: deque = deque(maxlen=1000)
        self.state_history: deque = deque(maxlen=1000)
        self.action_history: deque = deque(maxlen=1000)

        # Current drawdown event
        self.current_event: DrawdownEvent | None = None
        self.completed_events: list[DrawdownEvent] = []

        # Monitoring
        self._monitoring_active = False
        self._monitor_thread: threading.Thread | None = None

        # Callbacks
        self._state_change_callbacks: list[callable] = []
        self._action_callbacks: list[callable] = []

        self.logger.info(f"DrawdownController initialized with equity: ${initial_equity:,.2f}")

    # ==========================================================================
    # PUBLIC METHODS - EQUITY UPDATES
    # ==========================================================================
    def update_equity(self, current_equity: float) -> DrawdownMetrics:
        """
        Update current equity and calculate drawdown metrics.

        Args:
            current_equity: Current portfolio equity

        Returns:
            Updated drawdown metrics
        """
        with self._lock:
            self.current_equity = current_equity
            timestamp = datetime.now()

            # Add to history
            self.equity_history.append((timestamp, current_equity))

            # Update peak if new high
            if current_equity > self.peak_equity:
                self.peak_equity = current_equity
                self.current_metrics.peak_value = current_equity
                self.current_metrics.peak_date = timestamp

            # Calculate drawdown
            drawdown = self._calculate_drawdown(current_equity)

            # Update metrics
            self._update_metrics(current_equity, drawdown, timestamp)

            # Check state change
            new_state = self._determine_state(drawdown)
            if new_state != self.current_state:
                self._handle_state_change(self.current_state, new_state)
                self.current_state = new_state

            # Track drawdown event
            self._track_drawdown_event(drawdown, timestamp)

            # Check recovery
            if self.current_state == DrawdownState.RECOVERY:
                self._update_recovery_progress()

            return self.current_metrics

    def get_risk_adjustments(self) -> RiskAdjustment:
        """
        Get current risk adjustments based on drawdown state.

        Returns:
            Risk adjustment parameters
        """
        with self._lock:
            multiplier = POSITION_SIZE_MULTIPLIERS.get(
                self.current_state.value, 1.0
            )

            # Determine allowed strategies based on state
            if self.current_state == DrawdownState.SHUTDOWN:
                allowed_strategies = []
            elif self.current_state in [DrawdownState.EMERGENCY, DrawdownState.CRITICAL]:
                allowed_strategies = ['defensive', 'hedging']
            elif self.current_state == DrawdownState.CAUTION:
                allowed_strategies = ['defensive', 'neutral', 'hedging']
            else:
                allowed_strategies = ['all']

            # Max positions based on state
            max_positions_map = {
                DrawdownState.NORMAL: 10,
                DrawdownState.WARNING: 8,
                DrawdownState.CAUTION: 6,
                DrawdownState.CRITICAL: 4,
                DrawdownState.EMERGENCY: 2,
                DrawdownState.SHUTDOWN: 0,
                DrawdownState.RECOVERY: 5
            }

            max_positions = max_positions_map.get(self.current_state, 10)

            # Build restrictions list
            restrictions = []
            if self.current_state.value in ['critical', 'emergency', 'shutdown']:
                restrictions.append("No new aggressive positions")
                restrictions.append("Mandatory stop losses")
                restrictions.append("Reduced leverage only")

            if self.current_state == DrawdownState.EMERGENCY:
                restrictions.append("Close losing positions")
                restrictions.append("No overnight holds")

            return RiskAdjustment(
                position_size_multiplier=multiplier,
                max_positions=max_positions,
                allow_new_trades=self.current_state != DrawdownState.SHUTDOWN,
                require_stops=self.current_state.value in ['caution', 'critical', 'emergency'],
                max_loss_per_trade=0.01 if self.current_state.value in ['critical', 'emergency'] else 0.02,
                allowed_strategies=allowed_strategies,
                restrictions=restrictions
            )

    def get_position_size_multiplier(self) -> float:
        """Get position size multiplier for current state."""
        with self._lock:
            if self.recovery_plan:
                return self.recovery_plan.position_size_multiplier
            return POSITION_SIZE_MULTIPLIERS.get(self.current_state.value, 1.0)

    def should_allow_new_trade(self, strategy: str = None) -> bool:
        """
        Check if new trades are allowed.

        Args:
            strategy: Optional strategy type to check

        Returns:
            True if trade is allowed
        """
        with self._lock:
            # No trades in shutdown
            if self.current_state == DrawdownState.SHUTDOWN:
                return False

            # Check recovery plan
            if self.recovery_plan and strategy:
                return strategy in self.recovery_plan.strategies_allowed

            # Check risk adjustments
            adjustments = self.get_risk_adjustments()

            if not adjustments.allow_new_trades:
                return False

            if strategy and adjustments.allowed_strategies:
                if 'all' not in adjustments.allowed_strategies:
                    return strategy in adjustments.allowed_strategies

            return True

    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    def _create_initial_metrics(self) -> DrawdownMetrics:
        """Create initial metrics object."""
        return DrawdownMetrics(
            current_drawdown=0.0,
            max_drawdown=0.0,
            drawdown_start_date=None,
            drawdown_start_value=self.initial_equity,
            peak_value=self.initial_equity,
            peak_date=datetime.now(),
            trough_value=self.initial_equity,
            trough_date=None,
            days_in_drawdown=0
        )

    def _calculate_drawdown(self, current_equity: float) -> float:
        """Calculate current drawdown percentage."""
        if self.peak_equity <= 0:
            return 0.0

        return (self.peak_equity - current_equity) / self.peak_equity

    def _update_metrics(self, current_equity: float, drawdown: float, timestamp: datetime) -> None:
        """Update drawdown metrics."""
        metrics = self.current_metrics

        # Update current drawdown
        metrics.current_drawdown = drawdown

        # Update max drawdown
        if drawdown > metrics.max_drawdown:
            metrics.max_drawdown = drawdown
            metrics.trough_value = current_equity
            metrics.trough_date = timestamp

        # Track drawdown start
        if drawdown > 0.001 and metrics.drawdown_start_date is None:  # 0.1% threshold
            metrics.drawdown_start_date = timestamp
            metrics.drawdown_start_value = self.peak_equity

        # Track drawdown end
        if drawdown < 0.001 and metrics.drawdown_start_date is not None:
            # Drawdown ended
            if metrics.trough_date:
                metrics.recovery_days = (timestamp - metrics.trough_date).days

        # Calculate days in drawdown
        if metrics.drawdown_start_date:
            metrics.days_in_drawdown = (timestamp - metrics.drawdown_start_date).days

        # Update state
        metrics.drawdown_state = self._determine_state(drawdown)

    def _determine_state(self, drawdown: float) -> DrawdownState:
        """Determine drawdown state based on current drawdown."""
        if drawdown >= self.shutdown_threshold:
            return DrawdownState.SHUTDOWN
        elif drawdown >= self.emergency_threshold:
            return DrawdownState.EMERGENCY
        elif drawdown >= self.critical_threshold:
            return DrawdownState.CRITICAL
        elif drawdown >= self.caution_threshold:
            return DrawdownState.CAUTION
        elif drawdown >= self.warning_threshold:
            return DrawdownState.WARNING
        elif self.current_state in [DrawdownState.CAUTION, DrawdownState.CRITICAL,
                                   DrawdownState.EMERGENCY] and drawdown < self.warning_threshold:
            return DrawdownState.RECOVERY
        else:
            return DrawdownState.NORMAL

    # ==========================================================================
    # PRIVATE METHODS - STATE MANAGEMENT
    # ==========================================================================
    def _handle_state_change(self, old_state: DrawdownState, new_state: DrawdownState) -> None:
        """Handle drawdown state change."""
        self.logger.warning("Drawdown state change: %s -> %s", old_state.value, new_state.value)

        # Record state change
        self.state_history.append({
            'timestamp': datetime.now(),
            'old_state': old_state.value,
            'new_state': new_state.value,
            'drawdown': self.current_metrics.current_drawdown,
            'equity': self.current_equity
        })

        # Take actions based on new state
        actions = self._determine_actions(new_state)
        for action in actions:
            self._execute_action(action)

        # Setup recovery plan if entering recovery
        if new_state == DrawdownState.RECOVERY:
            self._create_recovery_plan()

        # Clear recovery plan if back to normal
        if new_state == DrawdownState.NORMAL and self.recovery_plan:
            self.recovery_plan = None
            self.logger.info("Recovery complete - resuming normal trading")

        # Execute callbacks
        for callback in self._state_change_callbacks:
            try:
                callback(old_state, new_state, self.current_metrics)
            except Exception as e:
                self.logger.error("State change callback error: %s", e)

    def _determine_actions(self, state: DrawdownState) -> list[DrawdownAction]:
        """Determine actions to take for a state."""
        actions_map = {
            DrawdownState.NORMAL: [],
            DrawdownState.WARNING: [DrawdownAction.NONE],
            DrawdownState.CAUTION: [DrawdownAction.REDUCE_SIZE],
            DrawdownState.CRITICAL: [
                DrawdownAction.REDUCE_SIZE,
                DrawdownAction.REDUCE_POSITIONS
            ],
            DrawdownState.EMERGENCY: [
                DrawdownAction.STOP_NEW_TRADES,
                DrawdownAction.CLOSE_LOSING
            ],
            DrawdownState.SHUTDOWN: [
                DrawdownAction.STOP_NEW_TRADES,
                DrawdownAction.CLOSE_ALL
            ],
            DrawdownState.RECOVERY: [DrawdownAction.REDUCE_SIZE]
        }

        return actions_map.get(state, [])

    def _execute_action(self, action: DrawdownAction) -> None:
        """Execute a drawdown action."""
        self.logger.info("Executing drawdown action: %s", action.value)

        # Record action
        self.action_history.append({
            'timestamp': datetime.now(),
            'action': action.value,
            'state': self.current_state.value,
            'drawdown': self.current_metrics.current_drawdown,
            'equity': self.current_equity
        })

        # Execute callbacks for action
        for callback in self._action_callbacks:
            try:
                callback(action, self.current_metrics)
            except Exception as e:
                self.logger.error("Action callback error: %s", e)

    # ==========================================================================
    # PRIVATE METHODS - DRAWDOWN TRACKING
    # ==========================================================================
    def _track_drawdown_event(self, drawdown: float, timestamp: datetime) -> None:
        """Track drawdown events."""
        # Start new event if entering drawdown
        if drawdown > 0.01 and self.current_event is None:  # 1% threshold
            self.current_event = DrawdownEvent(
                event_id=f"DD_{timestamp.strftime('%Y%m%d_%H%M%S')}",
                start_date=timestamp,
                end_date=None,
                start_value=self.peak_equity,
                trough_value=self.current_equity,
                end_value=None,
                max_drawdown=drawdown,
                duration_days=0,
                recovery_days=None,
                drawdown_state_reached=self.current_state,
                actions_taken=[]
            )

        # Update current event
        if self.current_event:
            self.current_event.trough_value = min(
                self.current_event.trough_value,
                self.current_equity
            )
            self.current_event.max_drawdown = max(
                self.current_event.max_drawdown,
                drawdown
            )
            self.current_event.duration_days = (
                timestamp - self.current_event.start_date
            ).days

            # Track worst state reached
            state_severity = {
                DrawdownState.NORMAL: 0,
                DrawdownState.WARNING: 1,
                DrawdownState.CAUTION: 2,
                DrawdownState.CRITICAL: 3,
                DrawdownState.EMERGENCY: 4,
                DrawdownState.SHUTDOWN: 5
            }

            if state_severity.get(self.current_state, 0) > \
               state_severity.get(self.current_event.drawdown_state_reached, 0):
                self.current_event.drawdown_state_reached = self.current_state

            # Complete event if recovered
            if drawdown < 0.001:  # Back to peak
                self.current_event.end_date = timestamp
                self.current_event.end_value = self.current_equity
                self.current_event.recovery_days = (
                    timestamp - self.current_event.start_date
                ).days - self.current_event.duration_days

                # Add to completed events
                self.completed_events.append(self.current_event)
                self.drawdown_history.append(asdict(self.current_event))

                self.logger.info(
                    f"Drawdown event completed: {self.current_event.event_id} "
                    f"(Max: {self.current_event.max_drawdown:.1%}, "
                    f"Duration: {self.current_event.duration_days} days)"
                )

                self.current_event = None

    # ==========================================================================
    # PRIVATE METHODS - RECOVERY
    # ==========================================================================
    def _create_recovery_plan(self) -> None:
        """Create recovery plan after drawdown."""
        # Calculate recovery milestones
        trough = self.current_metrics.trough_value
        peak = self.peak_equity

        milestones = [
            trough + (peak - trough) * 0.25,  # 25% recovery
            trough + (peak - trough) * 0.50,  # 50% recovery
            trough + (peak - trough) * 0.75,  # 75% recovery
            peak                               # Full recovery
        ]

        self.recovery_plan = RecoveryPlan(
            phase=RecoveryPhase.EARLY,
            target_equity=peak,
            allowed_risk=0.01,  # 1% risk during recovery
            position_size_multiplier=0.5,
            strategies_allowed=['defensive', 'neutral'],
            milestones=milestones,
            current_milestone=0
        )

        self.logger.info("Recovery plan created with 4 milestones")

    def _update_recovery_progress(self) -> None:
        """Update recovery progress."""
        if not self.recovery_plan:
            return

        plan = self.recovery_plan

        # Check milestone progress
        for i, milestone in enumerate(plan.milestones):
            if self.current_equity >= milestone and i > plan.current_milestone:
                plan.current_milestone = i
                self.logger.info(f"Recovery milestone {i+1}/4 reached: ${milestone:,.2f}")

                # Update recovery phase
                if i == 0:
                    plan.phase = RecoveryPhase.EARLY
                    plan.position_size_multiplier = 0.6
                elif i == 1:
                    plan.phase = RecoveryPhase.MIDDLE
                    plan.position_size_multiplier = 0.7
                    plan.strategies_allowed.append('momentum')
                elif i == 2:
                    plan.phase = RecoveryPhase.LATE
                    plan.position_size_multiplier = 0.85
                    plan.allowed_risk = 0.015
                elif i == 3:
                    plan.phase = RecoveryPhase.COMPLETE
                    self.current_state = DrawdownState.NORMAL

    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    def get_drawdown_stats(self) -> dict[str, Any]:
        """Get comprehensive drawdown statistics."""
        with self._lock:
            # Calculate statistics from history
            if self.completed_events:
                avg_drawdown = statistics.mean(
                    e.max_drawdown for e in self.completed_events
                )
                avg_duration = statistics.mean(
                    e.duration_days for e in self.completed_events
                )
                avg_recovery = statistics.mean(
                    e.recovery_days for e in self.completed_events
                    if e.recovery_days is not None
                )
            else:
                avg_drawdown = avg_duration = avg_recovery = 0

            return {
                'current_drawdown': self.current_metrics.current_drawdown,
                'max_drawdown': self.current_metrics.max_drawdown,
                'days_in_drawdown': self.current_metrics.days_in_drawdown,
                'current_state': self.current_state.value,
                'peak_equity': self.peak_equity,
                'current_equity': self.current_equity,
                'total_events': len(self.completed_events),
                'avg_drawdown': avg_drawdown,
                'avg_duration_days': avg_duration,
                'avg_recovery_days': avg_recovery,
                'worst_drawdown': max(
                    (e.max_drawdown for e in self.completed_events),
                    default=0
                ),
                'in_recovery': self.recovery_plan is not None,
                'recovery_progress': self._get_recovery_progress()
            }

    def _get_recovery_progress(self) -> float:
        """Get recovery progress percentage."""
        if not self.recovery_plan:
            return 1.0

        trough = self.current_metrics.trough_value
        peak = self.peak_equity

        if peak <= trough:
            return 1.0

        return (self.current_equity - trough) / (peak - trough)

    def get_drawdown_history(self) -> list[DrawdownEvent]:
        """Get historical drawdown events."""
        with self._lock:
            return self.completed_events.copy()

    def get_state_history(self, hours: int = 24) -> list[dict[str, Any]]:
        """
        Get recent state change history.

        Args:
            hours: Number of hours to look back

        Returns:
            List of state changes
        """
        with self._lock:
            cutoff = datetime.now() - timedelta(hours=hours)
            return [
                s for s in self.state_history
                if s['timestamp'] >= cutoff
            ]

    def get_equity_curve(self) -> pd.DataFrame:
        """Get equity curve as DataFrame."""
        with self._lock:
            if not self.equity_history:
                return pd.DataFrame()

            timestamps, values = zip(*self.equity_history, strict=False)
            return pd.DataFrame({
                'timestamp': timestamps,
                'equity': values
            })

    # ==========================================================================
    # PUBLIC METHODS - CONFIGURATION
    # ==========================================================================
    def update_thresholds(self, thresholds: dict[str, float]) -> None:
        """
        Update drawdown thresholds.

        Args:
            thresholds: Dictionary of threshold values
        """
        with self._lock:
            if 'warning' in thresholds:
                self.warning_threshold = thresholds['warning']
            if 'caution' in thresholds:
                self.caution_threshold = thresholds['caution']
            if 'critical' in thresholds:
                self.critical_threshold = thresholds['critical']
            if 'emergency' in thresholds:
                self.emergency_threshold = thresholds['emergency']
            if 'shutdown' in thresholds:
                self.shutdown_threshold = thresholds['shutdown']

            self.logger.info("Drawdown thresholds updated: %s", thresholds)

    def register_state_change_callback(self, callback: callable) -> None:
        """Register callback for state changes."""
        self._state_change_callbacks.append(callback)

    def register_action_callback(self, callback: callable) -> None:
        """Register callback for actions."""
        self._action_callbacks.append(callback)

    def reset_peak(self) -> None:
        """Reset peak equity (use with caution)."""
        with self._lock:
            self.peak_equity = self.current_equity
            self.current_metrics = self._create_initial_metrics()
            self.current_state = DrawdownState.NORMAL
            self.recovery_plan = None

            self.logger.warning(f"Peak equity reset to ${self.current_equity:,.2f}")

    # ==========================================================================
    # PUBLIC METHODS - MONITORING
    # ==========================================================================
    def start_monitoring(self) -> None:
        """Start drawdown monitoring thread."""
        if not self._monitoring_active:
            self._monitoring_active = True
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="DrawdownMonitor",
                daemon=True
            )
            self._monitor_thread.start()
            self.logger.info("Drawdown monitoring started")

    def stop_monitoring(self) -> None:
        """Stop monitoring thread."""
        if self._monitoring_active:
            self._monitoring_active = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5)
            self.logger.info("Drawdown monitoring stopped")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                # Periodic checks could go here
                # For now, just sleep
                threading.Event().wait(DRAWDOWN_CHECK_INTERVAL)

            except Exception as e:
                self.logger.error("Monitoring error: %s", e)
                self.error_handler.handle_error(e, {"method": "_monitoring_loop"})

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_drawdown_controller(initial_equity: float, config: dict[str, Any] | None = None) -> DrawdownController:
    """
    Create drawdown controller instance.

    Args:
        initial_equity: Starting equity
        config: Optional configuration

    Returns:
        DrawdownController instance
    """
    return DrawdownController(initial_equity, config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    # Initialize controller
    controller = create_drawdown_controller(initial_equity=100000)

    # Register callbacks
    def on_state_change(old_state, new_state, metrics):
        pass

    def on_action(action, metrics):
        pass

    controller.register_state_change_callback(on_state_change)
    controller.register_action_callback(on_action)

    # Simulate trading with drawdown

    equity_values = [
        100000, 102000, 104000, 103000, 101000,  # Initial gains
        99000, 97000, 95000, 94000, 93000,       # Drawdown begins
        92000, 91000, 90000, 89000, 88000,       # Deeper drawdown
        87000, 85000, 83000, 82000, 80000,       # Critical drawdown
        81000, 82000, 83000, 84000, 85000,       # Recovery begins
        87000, 89000, 91000, 93000, 95000,       # Continuing recovery
        97000, 99000, 100000, 101000, 103000,    # Full recovery
        105000                                     # New high
    ]

    for _i, equity in enumerate(equity_values):
        metrics = controller.update_equity(equity)


        # Show risk adjustments
        adjustments = controller.get_risk_adjustments()

        if adjustments.restrictions:
            for _restriction in adjustments.restrictions:
                pass

        # Check if new trades allowed
        if not controller.should_allow_new_trade():
            pass

    # Show final statistics

    stats = controller.get_drawdown_stats()

    # Show drawdown events
    events = controller.get_drawdown_history()
    if events:
        for _event in events:
            pass

