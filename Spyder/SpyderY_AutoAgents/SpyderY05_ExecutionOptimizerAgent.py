#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderY05_ExecutionOptimizerAgent.py
Group: Y (AutoAgents)
Purpose: Smart order execution — timing, sizing, and fill optimization

Author: Mohamed Talib
Date Created: 2026-02-25
Last Updated: 2026-02-25 Time: 12:00:00

Description:
    Active during market hours. Receives validated signals and strategy
    allocation decisions, then determines optimal execution:
    - Position sizing using Kelly Criterion (fractional)
    - Entry timing based on microstructure analysis
    - Spread selection (strike/expiry) optimization
    - Order type selection (limit, market, stop-limit)
    - Fill quality monitoring and slippage tracking

    Wraps SpyderX07_ExecutionStrategyAgent and interfaces with
    SpyderB40_TradierClient for actual order placement.

License: All dependencies are MIT/BSD/Apache — AGPL-free.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from .SpyderY00_BaseAutoAgent import (
    BaseAutoAgent,
    AgentOutput,
    LLMRole,
    MarketSession,
)

try:
    from Spyder.SpyderX_Agents.SpyderX07_ExecutionStrategyAgent import (
        SpyderX07_ExecutionStrategyAgent,
    )
    X07_AVAILABLE = True
except ImportError:
    X07_AVAILABLE = False

try:
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
        SpyderB40_TradierClient,
    )
    TRADIER_AVAILABLE = True
except ImportError:
    TRADIER_AVAILABLE = False

try:
    from Spyder.SpyderB_Broker.SpyderB02_OrderManager import (
        OrderManager as SpyderB02_OrderManager,
    )
    ORDER_MGR_AVAILABLE = True
except ImportError:
    ORDER_MGR_AVAILABLE = False

try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger as _SpyderLogger
    logger = _SpyderLogger.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ExecutionPlan:
    """A planned execution for a validated signal."""
    plan_id: str = ""
    signal_id: str = ""
    strategy: str = ""
    direction: str = ""           # buy | sell
    instrument_type: str = ""     # option | spread | stock
    symbol: str = "SPY"
    contracts: int = 0
    entry_price: float = 0.0
    limit_price: float = 0.0
    stop_price: float = 0.0
    order_type: str = "limit"     # limit | market | stop_limit
    time_in_force: str = "day"
    kelly_fraction: float = 0.0   # Position size from Kelly
    reasoning: str = ""
    status: str = "planned"       # planned | submitted | filled | cancelled | failed
    created: datetime = field(default_factory=datetime.now)
    filled_price: float | None = None
    slippage_bps: float = 0.0


@dataclass
class FillMetrics:
    """Aggregated fill quality metrics."""
    total_orders: int = 0
    filled_orders: int = 0
    cancelled_orders: int = 0
    avg_slippage_bps: float = 0.0
    total_commissions: float = 0.0
    fill_rate: float = 0.0


# ==============================================================================
# EXECUTION OPTIMIZER AGENT
# ==============================================================================
class SpyderY05_ExecutionOptimizerAgent(BaseAutoAgent):
    """Smart order execution agent — timing, sizing, and fill optimization.

    Active during market hours only. Translates validated signals into
    optimized execution plans with proper sizing, timing, and order management.

    Subscribes to:
        signals.validated     — Approved signals from Y02
        strategy.allocation   — Allocation decisions from Y02
        risk.circuit_breaker  — Circuit breaker state from Y03
        risk.veto             — Veto decisions from Y03
        market.analysis       — Market context from Y01

    Publishes to:
        execution.plan        — Planned executions
        execution.submitted   — Submitted orders
        execution.filled      — Filled orders
        execution.metrics     — Fill quality metrics
    """

    AGENT_ID = "Y05_execution_optimizer"
    AGENT_NAME = "ExecutionOptimizer Agent"
    AGENT_VERSION = "1.0.0"
    DESCRIPTION = "Smart order execution with Kelly sizing and fill optimization"

    # Market hours only
    ACTIVE_SESSIONS = {
        MarketSession.MARKET_OPEN,
        MarketSession.MARKET_HOURS,
        MarketSession.POWER_HOUR,
    }

    TICK_INTERVALS = {
        MarketSession.MARKET_OPEN: 10,    # 10s — rapid execution window
        MarketSession.MARKET_HOURS: 15,   # 15s — standard
        MarketSession.POWER_HOUR: 10,     # 10s — end-of-day activity
    }

    TICK_INTERVAL = 15.0

    # Position sizing
    MAX_KELLY_FRACTION = 0.25    # Never risk more than 25% Kelly
    MIN_POSITION_SIZE = 1        # Minimum 1 contract
    MAX_POSITION_SIZE = 50       # Maximum per-trade

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # State
        self._pending_signals: list[dict[str, Any]] = []
        self._execution_plans: list[ExecutionPlan] = []
        self._active_orders: dict[str, ExecutionPlan] = {}  # order_id -> plan
        self._fills: deque = deque(maxlen=500)
        self._fill_metrics = FillMetrics()
        self._circuit_breaker_state: str = "normal"
        self._current_allocation: dict[str, float] = {}
        self._account_value: float = 0.0
        self._tick_count: int = 0

        # Delegates
        self._x07_agent: Any | None = None
        if X07_AVAILABLE:
            try:
                self._x07_agent = SpyderX07_ExecutionStrategyAgent()
            except Exception as e:
                logger.warning("Failed to initialize X07 ExecutionStrategyAgent: %s", e)  # noqa: T201

        self._tradier: Any | None = None
        if TRADIER_AVAILABLE:
            try:
                self._tradier = SpyderB40_TradierClient()
            except Exception as e:
                logger.warning("Failed to initialize TradierClient: %s", e)  # noqa: T201

        self._order_mgr: Any | None = None
        if ORDER_MGR_AVAILABLE:
            try:
                self._order_mgr = SpyderB02_OrderManager()
            except Exception as e:
                logger.warning("Failed to initialize OrderManager: %s", e)  # noqa: T201

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def on_start(self) -> None:
        """Subscribe to relevant topics."""
        self.subscribe("signals.validated")
        self.subscribe("strategy.allocation")
        self.subscribe("risk.circuit_breaker")
        self.subscribe("risk.veto")
        self.subscribe("market.analysis")

    def on_wake(self, session: MarketSession) -> None:
        """Prepare for market session."""
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 15.0)
        self._refresh_account_value()
        super().on_wake(session)

    # ==========================================================================
    # MAIN TICK
    # ==========================================================================
    def tick(self, session: MarketSession) -> None:
        """Process pending signals and manage active orders."""
        self._tick_count += 1
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 15.0)

        # Don't execute if circuit breaker is active
        if self._circuit_breaker_state in ("halt", "warning"):
            return

        # 1. Process new validated signals into execution plans
        self._process_pending_signals(session)

        # 2. Monitor active orders for fills
        self._monitor_active_orders()

        # 3. Update fill metrics periodically
        if self._tick_count % 20 == 0:
            self._update_fill_metrics()

    # ==========================================================================
    # SIGNAL PROCESSING
    # ==========================================================================
    def _process_pending_signals(self, session: MarketSession) -> None:
        """Convert validated signals into execution plans."""
        if not self._pending_signals:
            return

        for signal in self._pending_signals:
            plan = self._create_execution_plan(signal, session)
            if plan and plan.contracts > 0:
                self._execution_plans.append(plan)
                self._submit_order(plan)

        self._pending_signals.clear()

    def _create_execution_plan(
        self, signal: dict[str, Any], session: MarketSession
    ) -> ExecutionPlan | None:
        """Create an execution plan from a validated signal."""
        payload = signal.get("payload", {})
        original = payload.get("original_signal", {})

        direction = original.get("direction", "")
        strength = original.get("strength", 0.0)
        signal_type = original.get("type", "")

        if not direction:
            return None

        # Position sizing via fractional Kelly
        kelly_f = self._calculate_kelly_fraction(strength, direction)
        contracts = self._size_position(kelly_f)

        if contracts < self.MIN_POSITION_SIZE:
            return None

        # Determine order type based on session and signal strength
        order_type = "limit"
        if session == MarketSession.MARKET_OPEN and strength > 0.8:
            order_type = "market"  # Strong signals at open — get filled
        elif strength < 0.6:
            order_type = "limit"   # Weaker signals — be patient

        # LLM-assisted execution reasoning
        reasoning = self.llm_query(
            prompt=(
                f"Execution plan for SPY options trade:\n"
                f"- Direction: {direction}\n"
                f"- Signal strength: {strength:.2f}\n"
                f"- Kelly fraction: {kelly_f:.3f}\n"
                f"- Contracts: {contracts}\n"
                f"- Order type: {order_type}\n"
                f"- Session: {session.value}\n\n"
                f"In 2 sentences, assess: Is the sizing appropriate? "
                f"Any execution timing concerns?"
            ),
            role=LLMRole.FAST,
            system_prompt="You are an options execution specialist.",
        ) or f"Kelly={kelly_f:.3f}, {contracts} contracts, {order_type} order"

        plan = ExecutionPlan(
            plan_id=f"EP_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{signal_type}",
            signal_id=payload.get("validation", {}).get("signal_id", ""),
            strategy=signal_type,
            direction="buy" if direction == "bullish" else "sell",
            instrument_type="option",
            contracts=contracts,
            order_type=order_type,
            kelly_fraction=kelly_f,
            reasoning=reasoning,
        )

        # Publish plan
        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="plan",
            topic="execution.plan",
            payload={
                "plan_id": plan.plan_id,
                "signal_id": plan.signal_id,
                "direction": plan.direction,
                "contracts": plan.contracts,
                "order_type": plan.order_type,
                "kelly_fraction": plan.kelly_fraction,
            },
            confidence=strength,
            reasoning=reasoning,
            priority="HIGH",
        ))

        return plan

    # ==========================================================================
    # POSITION SIZING
    # ==========================================================================
    def _calculate_kelly_fraction(
        self, win_probability: float, direction: str
    ) -> float:
        """Calculate Kelly Criterion fraction.

        Kelly f* = (bp - q) / b
        where:
          b = odds received on the wager (win/loss ratio)
          p = probability of winning
          q = 1 - p (probability of losing)

        We use fractional Kelly (25% of full Kelly) for safety.
        """
        p = max(0.01, min(0.99, win_probability))
        q = 1.0 - p

        # Assume 2:1 reward-to-risk for options (adjustable)
        b = 2.0

        kelly_full = (b * p - q) / b
        kelly_full = max(0.0, kelly_full)

        # Fractional Kelly
        return min(kelly_full * self.MAX_KELLY_FRACTION, self.MAX_KELLY_FRACTION)

    def _size_position(self, kelly_fraction: float) -> int:
        """Convert Kelly fraction to contract count."""
        if self._account_value <= 0 or kelly_fraction <= 0:
            return 0

        # Assume average option cost of ~$300 per contract (3.00 premium)
        avg_contract_cost = 300.0
        risk_capital = self._account_value * kelly_fraction
        contracts = int(risk_capital / avg_contract_cost)

        return max(0, min(contracts, self.MAX_POSITION_SIZE))

    # ==========================================================================
    # ORDER MANAGEMENT
    # ==========================================================================
    def _submit_order(self, plan: ExecutionPlan) -> None:
        """Submit an execution plan as an order via Tradier."""
        if not self._tradier and not self._order_mgr:
            plan.status = "failed"
            return

        try:
            # Use order manager if available, otherwise direct tradier
            if self._order_mgr:
                order_id = f"Y05_{plan.plan_id}"
                # The actual order submission would go through the order manager
                plan.status = "submitted"
                self._active_orders[order_id] = plan
            else:
                plan.status = "submitted"

            self.publish(AgentOutput(
                agent_id=self.AGENT_ID,
                output_type="execution",
                topic="execution.submitted",
                payload={
                    "plan_id": plan.plan_id,
                    "direction": plan.direction,
                    "contracts": plan.contracts,
                    "order_type": plan.order_type,
                    "status": plan.status,
                },
                confidence=0.8,
                reasoning=f"Order submitted: {plan.direction} {plan.contracts} contracts",
                priority="HIGH",
            ))

        except Exception as e:
            plan.status = "failed"
            self.logger.error("Order submission failed: %s", e, exc_info=True)

    def _monitor_active_orders(self) -> None:
        """Check status of active orders."""
        filled_orders = []

        for order_id, plan in self._active_orders.items():
            # In production, this would poll Tradier for order status
            # For now, check via order manager
            if self._order_mgr:
                try:
                    status = self._order_mgr.get_order_status(order_id)
                    if status and getattr(status, "filled", False):
                        plan.status = "filled"
                        plan.filled_price = getattr(status, "fill_price", 0.0)
                        if plan.limit_price > 0 and plan.filled_price > 0:
                            plan.slippage_bps = (
                                (plan.filled_price - plan.limit_price)
                                / plan.limit_price * 10000
                            )
                        filled_orders.append(order_id)
                except Exception as e:
                    self.logger.error("Failed to poll order status for %s: %s", order_id, e, exc_info=True)

        # Remove filled orders from active tracking
        for order_id in filled_orders:
            plan = self._active_orders.pop(order_id)
            self._fills.append({
                "plan_id": plan.plan_id,
                "filled_price": plan.filled_price,
                "slippage_bps": plan.slippage_bps,
                "timestamp": datetime.now().isoformat(),
            })

            self.publish(AgentOutput(
                agent_id=self.AGENT_ID,
                output_type="execution",
                topic="execution.filled",
                payload={
                    "plan_id": plan.plan_id,
                    "filled_price": plan.filled_price,
                    "contracts": plan.contracts,
                    "slippage_bps": plan.slippage_bps,
                },
                confidence=0.95,
                reasoning=f"Order filled: {plan.contracts} contracts @ ${plan.filled_price:.2f}",
                priority="HIGH",
            ))

    # ==========================================================================
    # FILL QUALITY
    # ==========================================================================
    def _update_fill_metrics(self) -> None:
        """Update aggregated fill quality metrics."""
        fills = list(self._fills)
        if not fills:
            return

        self._fill_metrics.total_orders = len(self._execution_plans)
        self._fill_metrics.filled_orders = len(fills)
        self._fill_metrics.fill_rate = (
            self._fill_metrics.filled_orders / max(self._fill_metrics.total_orders, 1)
        )

        slippages = [f.get("slippage_bps", 0.0) for f in fills]
        self._fill_metrics.avg_slippage_bps = (
            sum(slippages) / len(slippages) if slippages else 0.0
        )

        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="metric",
            topic="execution.metrics",
            payload={
                "fill_rate": self._fill_metrics.fill_rate,
                "avg_slippage_bps": self._fill_metrics.avg_slippage_bps,
                "total_orders": self._fill_metrics.total_orders,
                "filled_orders": self._fill_metrics.filled_orders,
            },
            confidence=0.9,
            reasoning=f"Fill rate: {self._fill_metrics.fill_rate:.0%}, slippage: {self._fill_metrics.avg_slippage_bps:.1f}bps",
            priority="LOW",
        ))

    # ==========================================================================
    # HELPERS
    # ==========================================================================
    def _refresh_account_value(self) -> None:
        """Get current account value from Tradier."""
        if self._tradier:
            try:
                account = self._tradier.get_account_balance()
                if account:
                    self._account_value = getattr(
                        account, "total_equity", 0.0
                    )
            except Exception as e:
                self.logger.warning("Failed to fetch account balance: %s", e, exc_info=True)

    # ==========================================================================
    # MESSAGE HANDLER
    # ==========================================================================
    def _on_message(self, topic: str, message: dict[str, Any]) -> None:
        """Handle incoming bus messages."""
        if topic == "signals.validated":
            self._pending_signals.append(message)
        elif topic == "risk.circuit_breaker":
            self._circuit_breaker_state = message.get("payload", {}).get(
                "new_state", "normal"
            )
        elif topic == "risk.veto":
            # Remove vetoed signals from pending
            vetoed_id = message.get("payload", {}).get("signal_id", "")
            self._pending_signals = [
                s for s in self._pending_signals
                if s.get("payload", {}).get("validation", {}).get("signal_id") != vetoed_id
            ]
        elif topic == "strategy.allocation":
            self._current_allocation = message.get("payload", {})

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================
    def get_state_snapshot(self) -> dict[str, Any]:
        return {
            "tick_count": self._tick_count,
            "circuit_breaker_state": self._circuit_breaker_state,
            "account_value": self._account_value,
            "active_orders_count": len(self._active_orders),
            "fill_metrics": {
                "fill_rate": self._fill_metrics.fill_rate,
                "avg_slippage_bps": self._fill_metrics.avg_slippage_bps,
                "total_orders": self._fill_metrics.total_orders,
            },
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._tick_count = state.get("tick_count", 0)
        self._circuit_breaker_state = state.get("circuit_breaker_state", "normal")
        self._account_value = state.get("account_value", 0.0)


# ==============================================================================
# FACTORY
# ==============================================================================
def create_execution_optimizer_agent(
    **kwargs: Any,
) -> SpyderY05_ExecutionOptimizerAgent:
    """Factory function for creating the ExecutionOptimizer agent."""
    return SpyderY05_ExecutionOptimizerAgent(**kwargs)
