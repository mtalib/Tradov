#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE04_DrawdownControl.py
Group: E (Risk Management)
Purpose: Maximum drawdown monitoring

Description:
    This module monitors and controls portfolio drawdown, implementing various
    risk reduction strategies when drawdown thresholds are exceeded. It tracks
    peak equity, calculates rolling drawdowns, and adjusts trading behavior.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import math
import statistics

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Drawdown thresholds
WARNING_DRAWDOWN = 0.05      # 5% drawdown warning
REDUCE_RISK_DRAWDOWN = 0.10  # 10% reduce position sizes
PAUSE_NEW_DRAWDOWN = 0.15    # 15% pause new positions
STOP_ALL_DRAWDOWN = 0.20     # 20% stop all trading

# Recovery parameters
MIN_RECOVERY_RATIO = 0.50    # Recover 50% of drawdown before full size
GRADUAL_RECOVERY_STEPS = 5   # Number of steps to return to full size

# Time-based parameters
DRAWDOWN_LOOKBACK_DAYS = 252  # 1 year for max drawdown calculation
RECOVERY_TIME_LIMIT = 90      # 90 days maximum recovery time
SHORT_TERM_WINDOW = 20        # 20 days for short-term drawdown

# Risk adjustments
SIZE_REDUCTION_FACTORS = {
    0.05: 1.0,   # No reduction under 5%
    0.10: 0.75,  # 25% reduction at 10%
    0.15: 0.50,  # 50% reduction at 15%
    0.20: 0.0    # No new positions at 20%
}

# ==============================================================================
# ENUMS
# ==============================================================================
class DrawdownState(Enum):
    """Current drawdown state"""
    NORMAL = auto()
    WARNING = auto()
    RISK_REDUCTION = auto()
    NEW_POSITIONS_PAUSED = auto()
    TRADING_STOPPED = auto()
    RECOVERING = auto()

class RecoveryPhase(Enum):
    """Recovery phase after drawdown"""
    INITIAL = auto()
    GRADUAL = auto()
    FINAL = auto()
    COMPLETE = auto()

class DrawdownType(Enum):
    """Types of drawdown measurements"""
    PORTFOLIO = auto()
    STRATEGY = auto()
    DAILY = auto()
    WEEKLY = auto()
    MONTHLY = auto()
    ROLLING = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class DrawdownMetrics:
    """Drawdown metrics and statistics"""
    current_drawdown: float
    max_drawdown: float
    drawdown_start: Optional[datetime]
    drawdown_trough: Optional[datetime]
    peak_value: float
    trough_value: float
    current_value: float
    days_in_drawdown: int
    recovery_ratio: float
    time_to_recovery: Optional[int] = None
    
    @property
    def drawdown_duration(self) -> Optional[timedelta]:
        """Get drawdown duration"""
        if self.drawdown_start:
            end = self.drawdown_trough or datetime.now()
            return end - self.drawdown_start
        return None

class DrawdownEvent:
    """Drawdown event record"""
    event_id: str
    start_date: datetime
    end_date: Optional[datetime]
    peak_value: float
    trough_value: float
    max_drawdown: float
    duration_days: int
    recovery_days: Optional[int]
    trigger_threshold: float
    actions_taken: List[str]

class DrawdownControl:
    """Drawdown control configuration"""
    max_allowed_drawdown: float = 0.20
    warning_threshold: float = WARNING_DRAWDOWN
    risk_reduction_threshold: float = REDUCE_RISK_DRAWDOWN
    pause_threshold: float = PAUSE_NEW_DRAWDOWN
    stop_threshold: float = STOP_ALL_DRAWDOWN
    use_gradual_recovery: bool = True
    use_time_limits: bool = True
    track_strategy_drawdowns: bool = True
    
class RecoveryPlan:
    """Recovery plan after drawdown"""
    phase: RecoveryPhase
    current_step: int
    total_steps: int
    size_multiplier: float
    restrictions: List[str]
    target_equity: float
    estimated_time: int  # Days

# ==============================================================================
# DRAWDOWN CONTROLLER CLASS
# ==============================================================================
class DrawdownController:
    """
    Monitors and controls portfolio drawdown.
    
    Implements multiple levels of risk reduction based on drawdown severity
    and manages the recovery process back to normal trading.
    """
    
    def __init__(
        self,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: Optional[DrawdownControl] = None
    ):
        """
        Initialize drawdown controller.
        
        Args:
            event_manager: Event manager for notifications
            risk_profile: Risk profile configuration
            config: Drawdown control configuration
        """
        self.event_manager = event_manager
        self.risk_profile = risk_profile
        self.config = config or DrawdownControl()
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # State tracking
        self.current_state = DrawdownState.NORMAL
        self.peak_equity = 0.0
        self.equity_curve: List[Tuple[datetime, float]] = []
        
        # Drawdown metrics
        self.portfolio_metrics = self._initialize_metrics()
        self.strategy_metrics: Dict[str, DrawdownMetrics] = {}
        
        # Drawdown history
        self.drawdown_events: List[DrawdownEvent] = []
        self.current_event: Optional[DrawdownEvent] = None
        
        # Recovery tracking
        self.recovery_plan: Optional[RecoveryPlan] = None
        self.recovery_start_equity = 0.0
        
        # Performance tracking
        self.state_changes: List[Dict[str, Any]] = []
        self.risk_adjustments: List[Dict[str, Any]] = []
        
        # Register event handlers
        self._register_event_handlers()
        
        self.logger.info("DrawdownController initialized")
    
    # ==========================================================================
    # EQUITY UPDATES
    # ==========================================================================
    def update_equity(
        self,
        current_equity: float,
        timestamp: Optional[datetime] = None
    ) -> DrawdownMetrics:
        """
        Update equity and calculate drawdown.
        
        Args:
            current_equity: Current portfolio equity
            timestamp: Update timestamp
            
        Returns:
            Updated drawdown metrics
        """
        timestamp = timestamp or datetime.now()
        
        try:
            # Update equity curve
            self.equity_curve.append((timestamp, current_equity))
            self._limit_equity_history()
            
            # Update peak equity
            if current_equity > self.peak_equity:
                self.peak_equity = current_equity
                
                # Check if recovering from drawdown
                if self.current_state == DrawdownState.RECOVERING:
                    self._complete_recovery()
            
            # Calculate drawdown
            self.portfolio_metrics = self._calculate_drawdown_metrics(
                current_equity,
                timestamp
            )
            
            # Check state transitions
            new_state = self._determine_state(self.portfolio_metrics.current_drawdown)
            if new_state != self.current_state:
                self._handle_state_change(new_state, self.portfolio_metrics)
            
            # Update recovery progress if in recovery
            if self.recovery_plan:
                self._update_recovery_progress(current_equity)
            
            # Emit metrics update
            self._emit_metrics_update()
            
            return self.portfolio_metrics
            
        except Exception as e:
            self.logger.error(f"Error updating equity: {e}")
            self.error_handler.handle_error(e, "update_equity")
            return self.portfolio_metrics
    
    def update_strategy_equity(
        self,
        strategy: str,
        strategy_equity: float,
        timestamp: Optional[datetime] = None
    ) -> Optional[DrawdownMetrics]:
        """
        Update equity for a specific strategy.
        
        Args:
            strategy: Strategy name
            strategy_equity: Strategy equity value
            timestamp: Update timestamp
            
        Returns:
            Strategy drawdown metrics
        """
        if not self.config.track_strategy_drawdowns:
            return None
        
        timestamp = timestamp or datetime.now()
        
        # Initialize if needed
        if strategy not in self.strategy_metrics:
            self.strategy_metrics[strategy] = self._initialize_metrics()
        
        # Update strategy peak
        metrics = self.strategy_metrics[strategy]
        if strategy_equity > metrics.peak_value:
            metrics.peak_value = strategy_equity
        
        # Calculate strategy drawdown
        metrics.current_value = strategy_equity
        if metrics.peak_value > 0:
            metrics.current_drawdown = (metrics.peak_value - strategy_equity) / metrics.peak_value
        
        return metrics
    
    # ==========================================================================
    # DRAWDOWN CALCULATION
    # ==========================================================================
    def _calculate_drawdown_metrics(
        self,
        current_equity: float,
        timestamp: datetime
    ) -> DrawdownMetrics:
        """Calculate comprehensive drawdown metrics"""
        metrics = self.portfolio_metrics
        
        # Update current value
        metrics.current_value = current_equity
        
        # Calculate current drawdown
        if self.peak_equity > 0:
            metrics.current_drawdown = (self.peak_equity - current_equity) / self.peak_equity
        else:
            metrics.current_drawdown = 0
        
        # Update peak and trough
        metrics.peak_value = self.peak_equity
        if metrics.current_drawdown > 0:
            if metrics.drawdown_start is None:
                # New drawdown started
                metrics.drawdown_start = timestamp
                metrics.trough_value = current_equity
            elif current_equity < metrics.trough_value:
                # New trough
                metrics.trough_value = current_equity
                metrics.drawdown_trough = timestamp
        else:
            # No drawdown
            metrics.drawdown_start = None
            metrics.drawdown_trough = None
            metrics.trough_value = current_equity
        
        # Calculate maximum drawdown
        metrics.max_drawdown = self._calculate_max_drawdown()
        
        # Calculate days in drawdown
        if metrics.drawdown_start:
            metrics.days_in_drawdown = (timestamp - metrics.drawdown_start).days
        else:
            metrics.days_in_drawdown = 0
        
        # Calculate recovery ratio
        if metrics.peak_value > metrics.trough_value:
            recovery_needed = metrics.peak_value - metrics.trough_value
            recovery_achieved = current_equity - metrics.trough_value
            metrics.recovery_ratio = recovery_achieved / recovery_needed if recovery_needed > 0 else 0
        else:
            metrics.recovery_ratio = 1.0
        
        return metrics
    
    def _calculate_max_drawdown(self, window_days: Optional[int] = None) -> float:
        """Calculate maximum drawdown over period"""
        if len(self.equity_curve) < 2:
            return 0
        
        window_days = window_days or DRAWDOWN_LOOKBACK_DAYS
        cutoff_date = datetime.now() - timedelta(days=window_days)
        
        # Filter equity curve
        relevant_curve = [(t, v) for t, v in self.equity_curve if t >= cutoff_date]
        if not relevant_curve:
            return 0
        
        # Calculate running maximum and drawdowns
        values = [v for _, v in relevant_curve]
        running_max = np.maximum.accumulate(values)
        drawdowns = (running_max - values) / running_max
        
        return float(np.max(drawdowns))
    
    def calculate_rolling_drawdowns(
        self,
        windows: List[int] = [20, 60, 252]
    ) -> Dict[int, float]:
        """
        Calculate rolling drawdowns for multiple windows.
        
        Args:
            windows: List of window sizes in days
            
        Returns:
            Dictionary of window -> max drawdown
        """
        rolling_drawdowns = {}
        
        for window in windows:
            dd = self._calculate_max_drawdown(window)
            rolling_drawdowns[window] = dd
        
        return rolling_drawdowns
    
    # ==========================================================================
    # STATE MANAGEMENT
    # ==========================================================================
    def _determine_state(self, current_drawdown: float) -> DrawdownState:
        """Determine appropriate state based on drawdown"""
        if current_drawdown >= self.config.stop_threshold:
            return DrawdownState.TRADING_STOPPED
        elif current_drawdown >= self.config.pause_threshold:
            return DrawdownState.NEW_POSITIONS_PAUSED
        elif current_drawdown >= self.config.risk_reduction_threshold:
            return DrawdownState.RISK_REDUCTION
        elif current_drawdown >= self.config.warning_threshold:
            return DrawdownState.WARNING
        elif self.recovery_plan is not None:
            return DrawdownState.RECOVERING
        else:
            return DrawdownState.NORMAL
    
    def _handle_state_change(
        self,
        new_state: DrawdownState,
        metrics: DrawdownMetrics
    ) -> None:
        """Handle state transitions"""
        old_state = self.current_state
        self.current_state = new_state
        
        # Log state change
        self.state_changes.append({
            'timestamp': datetime.now(),
            'old_state': old_state.name,
            'new_state': new_state.name,
            'drawdown': metrics.current_drawdown,
            'equity': metrics.current_value
        })
        
        # Take appropriate actions
        actions = []
        
        if new_state == DrawdownState.WARNING:
            actions.append("Drawdown warning issued")
            self._emit_warning(metrics)
            
        elif new_state == DrawdownState.RISK_REDUCTION:
            actions.append("Risk reduction activated")
            self._activate_risk_reduction(metrics)
            
        elif new_state == DrawdownState.NEW_POSITIONS_PAUSED:
            actions.append("New positions paused")
            self._pause_new_positions(metrics)
            
        elif new_state == DrawdownState.TRADING_STOPPED:
            actions.append("Trading stopped")
            self._stop_trading(metrics)
            
        elif new_state == DrawdownState.RECOVERING:
            actions.append("Recovery phase started")
            self._start_recovery(metrics)
        
        # Record drawdown event
        if new_state != DrawdownState.NORMAL and not self.current_event:
            self._start_drawdown_event(metrics, actions)
        
        # Emit state change event
        self._emit_state_change(old_state, new_state, actions)
        
        self.logger.info(f"State changed from {old_state.name} to {new_state.name}")
    
    # ==========================================================================
    # RISK CONTROLS
    # ==========================================================================
    def get_position_size_multiplier(self) -> float:
        """
        Get current position size multiplier based on drawdown.
        
        Returns:
            Position size multiplier (0.0 to 1.0)
        """
        if self.current_state == DrawdownState.TRADING_STOPPED:
            return 0.0
        
        # Get base multiplier from drawdown level
        base_multiplier = 1.0
        for threshold, multiplier in sorted(SIZE_REDUCTION_FACTORS.items()):
            if self.portfolio_metrics.current_drawdown >= threshold:
                base_multiplier = multiplier
        
        # Apply recovery plan if active
        if self.recovery_plan:
            base_multiplier *= self.recovery_plan.size_multiplier
        
        return base_multiplier
    
    def can_open_new_position(self, strategy: Optional[str] = None) -> bool:
        """
        Check if new positions can be opened.
        
        Args:
            strategy: Optional strategy to check
            
        Returns:
            True if new positions allowed
        """
        # Check portfolio level
        if self.current_state in [
            DrawdownState.NEW_POSITIONS_PAUSED,
            DrawdownState.TRADING_STOPPED
        ]:
            return False
        
        # Check strategy level if specified
        if strategy and strategy in self.strategy_metrics:
            strategy_dd = self.strategy_metrics[strategy].current_drawdown
            if strategy_dd >= self.config.pause_threshold:
                return False
        
        # Check recovery restrictions
        if self.recovery_plan and "no_new_positions" in self.recovery_plan.restrictions:
            return False
        
        return True
    
    def get_risk_adjustments(self) -> Dict[str, Any]:
        """Get current risk adjustments"""
        return {
            'state': self.current_state.name,
            'drawdown': self.portfolio_metrics.current_drawdown,
            'size_multiplier': self.get_position_size_multiplier(),
            'new_positions_allowed': self.can_open_new_position(),
            'recovery_phase': self.recovery_plan.phase.name if self.recovery_plan else None,
            'restrictions': self.recovery_plan.restrictions if self.recovery_plan else []
        }
    
    # ==========================================================================
    # ACTIONS
    # ==========================================================================
    def _activate_risk_reduction(self, metrics: DrawdownMetrics) -> None:
        """Activate risk reduction measures"""
        self.risk_adjustments.append({
            'timestamp': datetime.now(),
            'action': 'risk_reduction',
            'drawdown': metrics.current_drawdown,
            'size_reduction': 1 - self.get_position_size_multiplier()
        })
        
        self.logger.warning(f"Risk reduction activated at {metrics.current_drawdown:.1%} drawdown")
    
    def _pause_new_positions(self, metrics: DrawdownMetrics) -> None:
        """Pause opening new positions"""
        self.risk_adjustments.append({
            'timestamp': datetime.now(),
            'action': 'pause_new_positions',
            'drawdown': metrics.current_drawdown
        })
        
        self.logger.warning(f"New positions paused at {metrics.current_drawdown:.1%} drawdown")
    
    def _stop_trading(self, metrics: DrawdownMetrics) -> None:
        """Stop all trading"""
        self.risk_adjustments.append({
            'timestamp': datetime.now(),
            'action': 'stop_trading',
            'drawdown': metrics.current_drawdown
        })
        
        # Create drawdown event if not exists
        if not self.current_event:
            self._start_drawdown_event(metrics, ["Trading stopped due to maximum drawdown"])
        
        self.logger.error(f"Trading stopped at {metrics.current_drawdown:.1%} drawdown")
    
    # ==========================================================================
    # RECOVERY
    # ==========================================================================
    def _start_recovery(self, metrics: DrawdownMetrics) -> None:
        """Start recovery phase"""
        if not self.config.use_gradual_recovery:
            # Immediate full recovery
            self.recovery_plan = RecoveryPlan(
                phase=RecoveryPhase.COMPLETE,
                current_step=1,
                total_steps=1,
                size_multiplier=1.0,
                restrictions=[],
                target_equity=self.peak_equity,
                estimated_time=30
            )
        else:
            # Gradual recovery
            recovery_target = metrics.trough_value + (
                (self.peak_equity - metrics.trough_value) * MIN_RECOVERY_RATIO
            )
            
            self.recovery_plan = RecoveryPlan(
                phase=RecoveryPhase.INITIAL,
                current_step=1,
                total_steps=GRADUAL_RECOVERY_STEPS,
                size_multiplier=0.5,
                restrictions=["reduced_size", "conservative_only"],
                target_equity=recovery_target,
                estimated_time=60
            )
            
            self.recovery_start_equity = metrics.current_value
        
        self.logger.info("Started recovery phase")
    
    def _update_recovery_progress(self, current_equity: float) -> None:
        """Update recovery plan progress"""
        if not self.recovery_plan:
            return
        
        # Calculate progress
        recovery_progress = (current_equity - self.recovery_start_equity) / (
            self.recovery_plan.target_equity - self.recovery_start_equity
        )
        
        # Update phase
        if recovery_progress >= 1.0:
            if self.recovery_plan.phase == RecoveryPhase.INITIAL:
                # Move to gradual phase
                self.recovery_plan.phase = RecoveryPhase.GRADUAL
                self.recovery_plan.target_equity = self.peak_equity * 0.95
                self.recovery_plan.restrictions = ["reduced_size"]
            elif self.recovery_plan.phase == RecoveryPhase.GRADUAL:
                # Move to final phase
                self.recovery_plan.phase = RecoveryPhase.FINAL
                self.recovery_plan.target_equity = self.peak_equity
                self.recovery_plan.restrictions = []
            else:
                # Complete recovery
                self._complete_recovery()
        
        # Update size multiplier
        if self.recovery_plan.phase == RecoveryPhase.GRADUAL:
            step_progress = recovery_progress * self.recovery_plan.total_steps
            current_step = min(int(step_progress) + 1, self.recovery_plan.total_steps)
            self.recovery_plan.current_step = current_step
            self.recovery_plan.size_multiplier = 0.5 + (0.5 * current_step / self.recovery_plan.total_steps)
    
    def _complete_recovery(self) -> None:
        """Complete recovery process"""
        if self.recovery_plan:
            self.recovery_plan.phase = RecoveryPhase.COMPLETE
            self.recovery_plan = None
        
        # End drawdown event
        if self.current_event:
            self._end_drawdown_event()
        
        self.current_state = DrawdownState.NORMAL
        self.logger.info("Recovery completed, returning to normal trading")
    
    # ==========================================================================
    # EVENTS
    # ==========================================================================
    def _start_drawdown_event(
        self,
        metrics: DrawdownMetrics,
        actions: List[str]
    ) -> None:
        """Start a new drawdown event"""
        self.current_event = DrawdownEvent(
            event_id=f"DD_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_date=metrics.drawdown_start or datetime.now(),
            end_date=None,
            peak_value=metrics.peak_value,
            trough_value=metrics.trough_value,
            max_drawdown=metrics.current_drawdown,
            duration_days=0,
            recovery_days=None,
            trigger_threshold=self.config.warning_threshold,
            actions_taken=actions
        )
        
        self.drawdown_events.append(self.current_event)
    
    def _end_drawdown_event(self) -> None:
        """End current drawdown event"""
        if self.current_event:
            self.current_event.end_date = datetime.now()
            self.current_event.duration_days = (
                self.current_event.end_date - self.current_event.start_date
            ).days
            
            if self.portfolio_metrics.drawdown_trough:
                self.current_event.recovery_days = (
                    self.current_event.end_date - self.portfolio_metrics.drawdown_trough
                ).days
            
            self.current_event = None
    
    def _register_event_handlers(self) -> None:
        """Register event handlers"""
        self.event_manager.subscribe(
            self._handle_portfolio_update,
            event_filter=lambda e: e.type == EventType.PORTFOLIO,
            subscriber_id="drawdown_controller"
        )
    
    def _handle_portfolio_update(self, event: Event) -> None:
        """Handle portfolio update events"""
        if event.data.get('action') == 'value_update':
            equity = event.data.get('total_value')
            if equity:
                self.update_equity(equity)
    
    def _emit_state_change(
        self,
        old_state: DrawdownState,
        new_state: DrawdownState,
        actions: List[str]
    ) -> None:
        """Emit state change event"""
        self.event_manager.emit(Event(
            EventType.RISK,
            {
                'action': 'drawdown_state_change',
                'old_state': old_state.name,
                'new_state': new_state.name,
                'drawdown': self.portfolio_metrics.current_drawdown,
                'actions': actions,
                'risk_adjustments': self.get_risk_adjustments()
            }
        ))
    
    def _emit_warning(self, metrics: DrawdownMetrics) -> None:
        """Emit drawdown warning"""
        self.event_manager.emit(Event(
            EventType.ALERT,
            {
                'type': 'drawdown_warning',
                'level': 'warning',
                'drawdown': metrics.current_drawdown,
                'peak_value': metrics.peak_value,
                'current_value': metrics.current_value,
                'message': f"Portfolio drawdown reached {metrics.current_drawdown:.1%}"
            }
        ))
    
    def _emit_metrics_update(self) -> None:
        """Emit metrics update event"""
        self.event_manager.emit(Event(
            EventType.RISK,
            {
                'action': 'drawdown_metrics_update',
                'portfolio_drawdown': self.portfolio_metrics.current_drawdown,
                'max_drawdown': self.portfolio_metrics.max_drawdown,
                'state': self.current_state.name,
                'size_multiplier': self.get_position_size_multiplier()
            }
        ))
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _initialize_metrics(self) -> DrawdownMetrics:
        """Initialize drawdown metrics"""
        return DrawdownMetrics(
            current_drawdown=0.0,
            max_drawdown=0.0,
            drawdown_start=None,
            drawdown_trough=None,
            peak_value=0.0,
            trough_value=0.0,
            current_value=0.0,
            days_in_drawdown=0,
            recovery_ratio=0.0
        )
    
    def _limit_equity_history(self) -> None:
        """Limit equity curve history"""
        max_points = DRAWDOWN_LOOKBACK_DAYS * 24  # Hourly data for a year
        if len(self.equity_curve) > max_points:
            self.equity_curve = self.equity_curve[-max_points:]
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def get_drawdown_stats(self) -> Dict[str, Any]:
        """Get comprehensive drawdown statistics"""
        return {
            'current_drawdown': self.portfolio_metrics.current_drawdown,
            'max_drawdown': self.portfolio_metrics.max_drawdown,
            'state': self.current_state.name,
            'days_in_drawdown': self.portfolio_metrics.days_in_drawdown,
            'recovery_ratio': self.portfolio_metrics.recovery_ratio,
            'total_events': len(self.drawdown_events),
            'active_event': self.current_event is not None,
            'rolling_drawdowns': self.calculate_rolling_drawdowns()
        }
    
    def get_drawdown_history(self) -> List[DrawdownEvent]:
        """Get historical drawdown events"""
        return self.drawdown_events.copy()
    
    def reset_drawdown_tracking(self) -> None:
        """Reset drawdown tracking (use with caution)"""
        self.peak_equity = 0.0
        self.equity_curve.clear()
        self.portfolio_metrics = self._initialize_metrics()
        self.current_state = DrawdownState.NORMAL
        self.recovery_plan = None
        
        self.logger.warning("Drawdown tracking reset")

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test drawdown controller
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile
    
    # Initialize
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.10,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.02
    )
    
    # Create controller
    controller = DrawdownController(event_manager, risk_profile)
    
    # Simulate equity curve
    print("DRAWDOWN CONTROLLER TEST")
    print("=" * 50)
    
    # Starting equity
    equity = 100000
    controller.update_equity(equity)
    
    # Simulate trading with drawdown
    equity_values = [
        100000, 102000, 104000, 103000, 101000,  # Initial gains
        99000, 97000, 95000, 94000, 93000,       # Drawdown begins
        92000, 91000, 90000, 89000, 88000,       # Deeper drawdown
        89000, 90000, 91000, 92000, 93000,       # Recovery begins
        94000, 95000, 96000, 97000, 98000,       # Continuing recovery
        99000, 100000, 101000, 102000, 103000    # Full recovery
    ]
    
    for i, equity in enumerate(equity_values):
        metrics = controller.update_equity(equity)
        
        print(f"\nUpdate {i+1}:")
        print(f"  Equity: ${equity:,}")
        print(f"  Drawdown: {metrics.current_drawdown:.1%}")
        print(f"  State: {controller.current_state.name}")
        print(f"  Size Multiplier: {controller.get_position_size_multiplier():.1%}")
        
        # Show risk adjustments at key points
        if metrics.current_drawdown > 0.05 and i == 10:
            adjustments = controller.get_risk_adjustments()
            print(f"\n  Risk Adjustments:")
            for key, value in adjustments.items():
                print(f"    {key}: {value}")
    
    # Final statistics
    print("\n" + "=" * 50)
    print("FINAL STATISTICS")
    stats = controller.get_drawdown_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2%}")
        else:
            print(f"{key}: {value}")
    
    # Drawdown events
    print("\nDRAWDOWN EVENTS:")
    for event in controller.get_drawdown_history():
        print(f"\n{event.event_id}:")
        print(f"  Max Drawdown: {event.max_drawdown:.1%}")
        print(f"  Duration: {event.duration_days} days")
        print(f"  Recovery: {event.recovery_days} days" if event.recovery_days else "  Recovery: In progress")
        print(f"  Actions: {', '.join(event.actions_taken)}")
