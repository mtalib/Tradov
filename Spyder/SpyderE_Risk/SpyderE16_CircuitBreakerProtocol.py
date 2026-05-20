#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE16_CircuitBreakerProtocol.py
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
from datetime import datetime, time, UTC
from typing import Any
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

logger = logging.getLogger(__name__)
class CircuitBreakerLevel(Enum):
    """Circuit breaker levels based on S&P 500 decline."""
    NORMAL = "NORMAL"
    LEVEL_1 = "LEVEL_1"  # 7% decline
    LEVEL_2 = "LEVEL_2"  # 13% decline
    LEVEL_3 = "LEVEL_3"  # 20% decline
    PRE_HALT = "PRE_HALT"  # 5% decline (warning)
@dataclass
class CircuitBreakerStatus:
    """Current circuit breaker status."""
    level: CircuitBreakerLevel
    market_decline: float
    halt_active: bool
    halt_end_time: datetime | None
    positions_at_risk: int
    required_actions: list[str]
    order_restrictions: list[str]
@dataclass
class PositionAction:
    """Required action for a position during circuit breaker."""
    symbol: str
    position_id: str
    action: str  # CLOSE, REDUCE, HEDGE, HOLD
    urgency: str  # IMMEDIATE, HIGH, MEDIUM, LOW
    size_adjustment: float  # Percentage to reduce
    reason: str
    estimated_loss: float
class SpyderCircuitBreakerProtocol:
    """
    Implements institutional-grade circuit breaker protocols.
    Features:
    - Real-time market decline monitoring
    - Automatic halt detection and response
    - Position-specific de-risking actions
    - Order type restrictions during volatility
    - Recovery protocols post-halt
    """
    def __init__(self, risk_manager=None, order_manager=None):
        """Initialize circuit breaker protocol system."""
        self.risk_manager = risk_manager
        self.order_manager = order_manager
        # Circuit breaker thresholds
        self.THRESHOLDS = {
            'pre_halt': -0.05,      # -5% warning level
            'level_1': -0.07,       # -7% first halt
            'level_2': -0.13,       # -13% second halt
            'level_3': -0.20        # -20% market close
        }
        # Halt durations (minutes)
        self.HALT_DURATIONS = {
            CircuitBreakerLevel.LEVEL_1: 15,
            CircuitBreakerLevel.LEVEL_2: 15,
            CircuitBreakerLevel.LEVEL_3: float('inf')  # Rest of day
        }
        # Time-based restrictions
        self.TIME_RESTRICTIONS = {
            'level_1_cutoff': time(15, 25),  # No Level 1 halt after 3:25 PM
            'level_2_cutoff': time(15, 25),  # No Level 2 halt after 3:25 PM
        }
        # Position management rules by level
        self.POSITION_RULES = {
            CircuitBreakerLevel.PRE_HALT: {
                'max_position_size': 0.75,  # Reduce to 75% max
                'new_positions_allowed': False,
                'close_losing_positions': True,
                'hedge_requirement': 1.25  # 125% hedge ratio
            },
            CircuitBreakerLevel.LEVEL_1: {
                'max_position_size': 0.50,  # Reduce to 50% max
                'new_positions_allowed': False,
                'close_losing_positions': True,
                'hedge_requirement': 1.50  # 150% hedge ratio
            },
            CircuitBreakerLevel.LEVEL_2: {
                'max_position_size': 0.25,  # Reduce to 25% max
                'new_positions_allowed': False,
                'close_all_speculative': True,
                'hedge_requirement': 2.00  # 200% hedge ratio
            },
            CircuitBreakerLevel.LEVEL_3: {
                'flatten_all_positions': True,
                'cancel_all_orders': True
            }
        }
        # Order type restrictions by level
        self.ORDER_RESTRICTIONS = {
            CircuitBreakerLevel.PRE_HALT: ['MARKET'],  # No market orders
            CircuitBreakerLevel.LEVEL_1: ['MARKET', 'STOP_MARKET'],
            CircuitBreakerLevel.LEVEL_2: ['MARKET', 'STOP_MARKET', 'STOP_LIMIT'],
            CircuitBreakerLevel.LEVEL_3: ['ALL']  # Only manual override
        }
        # State tracking
        self.current_level = CircuitBreakerLevel.NORMAL
        self.halt_active = False
        self.halt_start_time = None
        self.market_open_price = None
        self.monitoring_active = True
        self.action_history = []
        self.event_clock_blackout_active = False
        self.event_clock_state: dict[str, Any] = {
            'state': 'clear',
            'allowed_strategies': [],
            'max_size_multiplier': 1.0,
        }
    async def monitor_market_conditions(self, current_price: float,
                                      market_open: float) -> CircuitBreakerStatus:
        """
        Monitor market conditions for circuit breaker triggers.
        Args:
            current_price: Current S&P 500 or SPY price
            market_open: Market open price
        Returns:
            Current circuit breaker status
        """
        if not self.monitoring_active:
            return self._get_current_status()
        # Calculate market decline
        market_decline = (current_price - market_open) / market_open
        # Check time-based restrictions
        current_time = datetime.now(UTC).time()
        # Determine circuit breaker level
        new_level = self._determine_level(market_decline, current_time)
        # Handle level changes
        if new_level != self.current_level:
            await self._handle_level_change(new_level, market_decline)
        # Check if halt should end
        if self.halt_active:
            await self._check_halt_status()
        return self._get_current_status()
    def _determine_level(self, market_decline: float,
                        current_time: time) -> CircuitBreakerLevel:
        """Determine appropriate circuit breaker level."""
        # Level 3 check (always active)
        if market_decline <= self.THRESHOLDS['level_3']:
            return CircuitBreakerLevel.LEVEL_3
        # Level 2 check (time restricted)
        if (market_decline <= self.THRESHOLDS['level_2'] and
            current_time < self.TIME_RESTRICTIONS['level_2_cutoff']):
            return CircuitBreakerLevel.LEVEL_2
        # Level 1 check (time restricted)
        if (market_decline <= self.THRESHOLDS['level_1'] and
            current_time < self.TIME_RESTRICTIONS['level_1_cutoff']):
            return CircuitBreakerLevel.LEVEL_1
        # Pre-halt warning
        if market_decline <= self.THRESHOLDS['pre_halt']:
            return CircuitBreakerLevel.PRE_HALT
        return CircuitBreakerLevel.NORMAL
    async def _handle_level_change(self, new_level: CircuitBreakerLevel,
                                  market_decline: float):
        """Handle circuit breaker level changes."""
        old_level = self.current_level
        # NOTE: state is committed AFTER execution so that a failed
        # _execute_level_protocols() does not leave self.current_level
        # pointing at a level whose position actions never ran.
        logger.warning(f"Circuit breaker level change: {old_level.value} -> "
                      f"{new_level.value} (decline: {market_decline:.2%})")
        # Trigger halt if applicable
        if new_level in [CircuitBreakerLevel.LEVEL_1,
                        CircuitBreakerLevel.LEVEL_2,
                        CircuitBreakerLevel.LEVEL_3]:
            await self._trigger_halt(new_level)
        # Execute position management BEFORE committing state change so that
        # any execution failure keeps current_level consistent with actual
        # position state.
        try:
            await self._execute_level_protocols(new_level)
        except Exception as exc:
            logger.error("Level protocol execution failed for %s: %s", new_level.value, exc)
            raise
        # Commit new level only after protocols executed successfully
        self.current_level = new_level
        # Record action
        self.action_history.append({
            'timestamp': datetime.now(UTC),
            'old_level': old_level,
            'new_level': new_level,
            'market_decline': market_decline
        })
    async def _trigger_halt(self, level: CircuitBreakerLevel):
        """Trigger market halt procedures."""
        self.halt_active = True
        self.halt_start_time = datetime.now(UTC)
        # Calculate halt end time
        halt_duration = self.HALT_DURATIONS.get(level)
        if halt_duration != float('inf'):
            halt_end = self.halt_start_time.timestamp() + (halt_duration * 60)
            self.halt_end_time = datetime.fromtimestamp(halt_end)
        else:
            self.halt_end_time = None  # Market closed
        logger.critical("MARKET HALT TRIGGERED - Level: %s", level.value)
        # Cancel all pending orders
        if self.order_manager:
            await self.order_manager.cancel_all_orders(
                reason=f"Circuit breaker {level.value}"
            )
    async def _execute_level_protocols(self, level: CircuitBreakerLevel):
        """Execute position management protocols for circuit breaker level."""
        rules = self.POSITION_RULES.get(level, {})
        if not rules:
            return
        # Get current positions
        positions = await self._get_current_positions()
        # Level 3: Flatten everything
        if rules.get('flatten_all_positions'):
            await self._flatten_all_positions(positions)
            return
        # Other levels: Selective management
        for position in positions:
            action = self._determine_position_action(position, rules)
            if action.action != 'HOLD':
                await self._execute_position_action(action)
    def _determine_position_action(self, position: dict,
                                  rules: dict) -> PositionAction:
        """Determine required action for a specific position."""
        # Priority 1: Close losing positions
        if rules.get('close_losing_positions') and position['pnl'] < 0:
            return PositionAction(
                symbol=position['symbol'],
                position_id=position['id'],
                action='CLOSE',
                urgency='IMMEDIATE',
                size_adjustment=1.0,
                reason='Losing position in circuit breaker',
                estimated_loss=position['pnl']
            )
        # Priority 2: Close speculative positions
        if (rules.get('close_all_speculative') and
            position.get('strategy_type') == 'speculative'):
            return PositionAction(
                symbol=position['symbol'],
                position_id=position['id'],
                action='CLOSE',
                urgency='HIGH',
                size_adjustment=1.0,
                reason='Speculative position in Level 2',
                estimated_loss=position['pnl']
            )
        # Priority 3: Reduce oversized positions
        max_size = rules.get('max_position_size', 1.0)
        if position['size_ratio'] > max_size:
            reduction = 1.0 - (max_size / position['size_ratio'])
            return PositionAction(
                symbol=position['symbol'],
                position_id=position['id'],
                action='REDUCE',
                urgency='HIGH',
                size_adjustment=reduction,
                reason=f'Position exceeds {max_size:.0%} limit',
                estimated_loss=position['pnl'] * reduction
            )
        # Priority 4: Increase hedges
        hedge_req = rules.get('hedge_requirement', 1.0)
        if position.get('hedge_ratio', 0) < hedge_req:
            return PositionAction(
                symbol=position['symbol'],
                position_id=position['id'],
                action='HEDGE',
                urgency='MEDIUM',
                size_adjustment=hedge_req - position.get('hedge_ratio', 0),
                reason=f'Increase hedge to {hedge_req:.0%}',
                estimated_loss=0
            )
        # Default: Hold
        return PositionAction(
            symbol=position['symbol'],
            position_id=position['id'],
            action='HOLD',
            urgency='LOW',
            size_adjustment=0,
            reason='Position within circuit breaker limits',
            estimated_loss=0
        )
    async def _execute_position_action(self, action: PositionAction):
        """Execute a specific position action."""
        logger.info(f"Executing circuit breaker action: {action.action} for "
                   f"{action.symbol} - {action.reason}")
        if not self.order_manager:
            logger.error("No order manager available for position actions")
            return
        try:
            if action.action == 'CLOSE':
                await self.order_manager.close_position(
                    action.position_id,
                    urgency=action.urgency,
                    reason=action.reason
                )
            elif action.action == 'REDUCE':
                await self.order_manager.reduce_position(
                    action.position_id,
                    reduction_pct=action.size_adjustment,
                    urgency=action.urgency,
                    reason=action.reason
                )
            elif action.action == 'HEDGE':
                await self.order_manager.increase_hedge(
                    action.position_id,
                    target_ratio=action.size_adjustment,
                    urgency=action.urgency
                )
        except Exception as e:
            logger.error("Failed to execute action %s: %s", action.action, str(e))
    def update_event_clock_state(self, state_payload: dict[str, Any] | None) -> None:
        """Update event-clock blackout state consumed from scheduler feed."""
        payload = state_payload or {}
        state = str(payload.get('state', 'clear')).lower()
        self.event_clock_state = {
            'state': state,
            'event_type': payload.get('event_type'),
            'event_id': payload.get('event_id'),
            'allowed_strategies': payload.get('allowed_strategies', []),
            'max_size_multiplier': payload.get('max_size_multiplier', 1.0),
        }
        self.event_clock_blackout_active = state in {'pre', 'live', 'post'}

    async def check_order_restrictions(self, order_type: str, strategy_id: str | None = None) -> tuple[bool, str]:  # noqa: E501
        """
        Check if an order type is allowed under current conditions.
        Args:
            order_type: Type of order (MARKET, LIMIT, etc.)
            strategy_id: Optional strategy identifier for blackout allowlist
        Returns:
            Tuple of (allowed, reason)
        """
        if self.event_clock_blackout_active:
            allowlist = {
                str(s).strip() for s in self.event_clock_state.get('allowed_strategies', [])
                if str(s).strip()
            }
            strategy = str(strategy_id or '').strip()
            if not (strategy and strategy in allowlist):
                event_type = self.event_clock_state.get('event_type') or 'macro_event'
                state = self.event_clock_state.get('state', 'pre')
                return False, f"Event-clock blackout ({state}) active for {event_type}"

        restrictions = self.ORDER_RESTRICTIONS.get(self.current_level, [])
        # Check if all orders restricted
        if 'ALL' in restrictions:
            return False, f"All orders restricted at {self.current_level.value}"
        # Check specific order type
        if order_type in restrictions:
            return False, f"{order_type} orders not allowed at {self.current_level.value}"
        # Check if market is halted
        if self.halt_active:
            return False, "Market currently halted"
        return True, "Order type allowed"
    def get_position_limits(self) -> dict[str, float]:
        """Get current position limits based on circuit breaker level."""
        rules = self.POSITION_RULES.get(self.current_level, {})
        return {
            'max_position_size': rules.get('max_position_size', 1.0),
            'new_positions_allowed': rules.get('new_positions_allowed', True),
            'hedge_requirement': rules.get('hedge_requirement', 1.0)
        }
    async def _check_halt_status(self):
        """Check if halt period has ended."""
        if not self.halt_active or not self.halt_end_time:
            return
        if datetime.now(UTC) >= self.halt_end_time:
            self.halt_active = False
            logger.info("Market halt ended for %s", self.current_level.value)
            # Execute post-halt protocols
            await self._execute_post_halt_protocols()
    async def _execute_post_halt_protocols(self):
        """Execute protocols after halt ends."""
        # Re-evaluate all positions
        positions = await self._get_current_positions()
        # Check if positions need adjustment post-halt
        for position in positions:
            # Re-assess risk with updated market conditions
            if self.risk_manager:
                risk_score = await self.risk_manager.assess_position_risk(
                    position,
                    market_condition='post_halt'
                )
                if risk_score > 0.8:  # High risk threshold
                    logger.warning(f"High risk position post-halt: "
                                 f"{position['symbol']} (score: {risk_score:.2f})")
    async def _flatten_all_positions(self, positions: list[dict]):
        """Emergency flatten all positions (Level 3)."""
        logger.critical("EMERGENCY: Flattening all positions due to Level 3 circuit breaker")
        if not self.order_manager:
            logger.error("No order manager available for emergency flatten")
            return
        for position in positions:
            try:
                await self.order_manager.close_position(
                    position['id'],
                    urgency='IMMEDIATE',
                    reason='Level 3 circuit breaker - market close',
                    force=True  # Override normal restrictions
                )
            except Exception as e:
                logger.error("Failed to flatten position %s: %s", position['id'], str(e))
    async def _get_current_positions(self) -> list[dict]:
        """Get current positions from risk manager."""
        if self.risk_manager:
            return await self.risk_manager.get_all_positions()
        return []
    def _get_current_status(self) -> CircuitBreakerStatus:
        """Get current circuit breaker status."""
        positions = []  # Would get from risk manager
        # Determine required actions based on level
        required_actions = []
        if self.current_level != CircuitBreakerLevel.NORMAL:
            rules = self.POSITION_RULES.get(self.current_level, {})
            if rules.get('close_losing_positions'):
                required_actions.append("Close all losing positions")
            if rules.get('close_all_speculative'):
                required_actions.append("Close all speculative positions")
            if rules.get('flatten_all_positions'):
                required_actions.append("EMERGENCY: Flatten all positions")
        return CircuitBreakerStatus(
            level=self.current_level,
            market_decline=0,  # Would calculate from market data
            halt_active=self.halt_active,
            halt_end_time=self.halt_end_time if self.halt_active else None,
            positions_at_risk=len([p for p in positions if p.get('at_risk', False)]),
            required_actions=required_actions,
            order_restrictions=self.ORDER_RESTRICTIONS.get(self.current_level, [])
        )
    def get_historical_halts(self, days: int = 30) -> pd.DataFrame:
        """Get historical circuit breaker events."""
        if not self.action_history:
            return pd.DataFrame()
        # Convert to DataFrame
        df = pd.DataFrame(self.action_history)
        # Filter by date range
        cutoff_date = datetime.now(UTC) - pd.Timedelta(days=days)
        df = df[df['timestamp'] >= cutoff_date]
        return df
    def get_recovery_analysis(self) -> dict[str, Any]:
        """Analyze recovery patterns after circuit breaker events."""
        halts = self.get_historical_halts(days=365)
        if halts.empty:
            return {'no_historical_data': True}
        # Analyze recovery times and patterns
        recovery_stats = {
            'avg_recovery_days': 0,  # Would calculate from market data
            'typical_rebound_pct': 0,
            'false_bottom_probability': 0,
            'recommended_reentry_delay': '2-3 days'
        }
        return recovery_stats
async def main():
    """Example usage of circuit breaker protocol."""
    # Initialize protocol
    protocol = SpyderCircuitBreakerProtocol()
    # Simulate market conditions
    market_open = 4500.0
    current_prices = [4500, 4450, 4350, 4250, 4150, 3950, 3600]
    for price in current_prices:
        status = await protocol.monitor_market_conditions(price, market_open)
        decline_pct = ((price - market_open) / market_open) * 100
        logging.info(f"\nPrice: ${price:.2f} (Decline: {decline_pct:.1f}%)")
        logging.info("Level: %s", status.level.value)
        logging.info("Halt Active: %s", status.halt_active)
        if status.required_actions:
            logging.info("Required Actions:")
            for action in status.required_actions:
                logging.info("  - %s", action)
        # Check order restrictions
        for order_type in ['MARKET', 'LIMIT']:
            allowed, reason = await protocol.check_order_restrictions(order_type)
            if not allowed:
                logging.info("  %s orders: BLOCKED - %s", order_type, reason)
        await asyncio.sleep(1)  # Simulate time passing
if __name__ == "__main__":
    asyncio.run(main())
# Alias for compatibility
CircuitBreaker = CircuitBreakerLevel
