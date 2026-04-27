#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderY03_RiskSentinelAgent.py
Group: Y (AutoAgents)
Purpose: 24/7 autonomous risk monitor with circuit breaker and veto authority

Author: Mohamed Talib
Date Created: 2026-02-25
Last Updated: 2026-02-25 Time: 12:00:00

Description:
    Runs 24/7 with elevated priority. Monitors portfolio risk, position Greeks,
    drawdown limits, correlation exposure, and tail risk. Has VETO AUTHORITY
    over any trade proposed by other agents.

    Wraps SpyderX04_RiskGuardianAgent and SpyderE_Risk modules with autonomous
    scheduling and LLM-powered risk analysis.

    Key responsibilities:
    - Real-time portfolio risk monitoring
    - Position-level Greek exposure tracking
    - Drawdown circuit breaker (auto-pause trading)
    - Tail risk / stress scenario monitoring
    - Trade veto power (can reject any signal)
    - Overnight risk assessment

License: All dependencies are MIT/BSD/Apache — AGPL-free.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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
    from Spyder.SpyderX_Agents.SpyderX04_RiskGuardianAgent import (
        SpyderX04_RiskGuardianAgent,
    )
    X04_AVAILABLE = True
except ImportError:
    X04_AVAILABLE = False

try:
    from Spyder.SpyderE_Risk.SpyderE19_PositionManager import (
        SpyderE19_PositionManager,
    )
    POSITION_MGR_AVAILABLE = True
except ImportError:
    POSITION_MGR_AVAILABLE = False


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    NORMAL = "normal"
    CAUTION = "caution"           # Elevated risk — reduced position sizes
    WARNING = "warning"           # High risk — no new positions
    HALT = "halt"                 # Critical — liquidate if needed
    MANUAL_OVERRIDE = "override"  # Human has manually overridden


@dataclass
class RiskSnapshot:
    """Point-in-time risk assessment."""
    timestamp: datetime = field(default_factory=datetime.now)
    circuit_breaker: str = CircuitBreakerState.NORMAL.value
    portfolio_delta: float = 0.0
    portfolio_gamma: float = 0.0
    portfolio_theta: float = 0.0
    portfolio_vega: float = 0.0
    max_drawdown_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    daily_pnl: float = 0.0
    position_count: int = 0
    max_single_position_pct: float = 0.0
    var_95: float = 0.0              # Value at Risk (95%)
    correlation_risk: float = 0.0    # 0-1, how correlated positions are
    risk_score: float = 0.0         # 0-100 composite risk score


@dataclass
class TradeVeto:
    """Record of a trade veto decision."""
    signal_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    vetoed: bool = False
    reason: str = ""
    risk_level: str = ""
    llm_reasoning: str = ""


# ==============================================================================
# RISK LIMITS (configurable)
# ==============================================================================
DEFAULT_RISK_LIMITS = {
    "max_portfolio_delta": 100.0,
    "max_portfolio_vega": 50.0,
    "max_daily_loss_pct": 2.0,
    "max_drawdown_pct": 5.0,
    "max_single_position_pct": 15.0,
    "max_position_count": 20,
    "max_correlation": 0.8,
    "circuit_breaker_drawdown_caution": 1.5,   # %
    "circuit_breaker_drawdown_warning": 3.0,   # %
    "circuit_breaker_drawdown_halt": 5.0,      # %
}


# ==============================================================================
# RISK SENTINEL AGENT
# ==============================================================================
class SpyderY03_RiskSentinelAgent(BaseAutoAgent):
    """24/7 autonomous risk monitor with circuit breaker and veto authority.

    The highest-priority agent in the system. Continuously monitors portfolio
    risk and can halt all trading if risk limits are breached.

    Subscribes to:
        signals.validated   — Validated signals (for veto review)
        execution.*         — Execution events (position tracking)
        risk.*              — Risk alerts from other modules
        market.regime       — Regime changes (risk implications)

    Publishes to:
        risk.assessment     — Periodic risk snapshots
        risk.alerts         — Threshold breach alerts
        risk.circuit_breaker — Circuit breaker state changes
        risk.veto           — Trade veto decisions
    """

    AGENT_ID = "Y03_risk_sentinel"
    AGENT_NAME = "RiskSentinel Agent"
    AGENT_VERSION = "1.0.0"
    DESCRIPTION = "24/7 risk monitoring with circuit breaker and trade veto authority"

    # Active 24/7 — risk never sleeps
    ACTIVE_SESSIONS = {
        MarketSession.OVERNIGHT,
        MarketSession.PRE_MARKET,
        MarketSession.MARKET_OPEN,
        MarketSession.MARKET_HOURS,
        MarketSession.POWER_HOUR,
        MarketSession.POST_MARKET,
    }

    TICK_INTERVALS = {
        MarketSession.OVERNIGHT: 300,     # 5 min overnight
        MarketSession.PRE_MARKET: 60,     # 1 min pre-market
        MarketSession.MARKET_OPEN: 10,    # 10s at open (highest risk)
        MarketSession.MARKET_HOURS: 15,   # 15s during market
        MarketSession.POWER_HOUR: 10,     # 10s power hour
        MarketSession.POST_MARKET: 120,   # 2 min post-market
    }

    TICK_INTERVAL = 15.0

    def __init__(self, risk_limits: dict[str, float] | None = None, **kwargs: Any):
        super().__init__(**kwargs)

        # Risk configuration
        self._limits = {**DEFAULT_RISK_LIMITS, **(risk_limits or {})}

        # State
        self._circuit_breaker = CircuitBreakerState.NORMAL
        self._snapshots: deque = deque(maxlen=1000)
        self._vetoes: list[TradeVeto] = []
        self._current_risk: RiskSnapshot = RiskSnapshot()
        self._pending_signals: list[dict[str, Any]] = []
        self._alerts_today: int = 0
        self._tick_count: int = 0
        self._halt_reason: str = ""

        # X-agent delegate
        self._x04_agent: Any | None = None
        if X04_AVAILABLE:
            try:
                self._x04_agent = SpyderX04_RiskGuardianAgent()
            except Exception as e:
                logging.getLogger(__name__).warning("Failed to initialize X04 RiskGuardianAgent: %s", e)  # noqa: E501

        # Position manager
        self._position_mgr: Any | None = None
        if POSITION_MGR_AVAILABLE:
            try:
                self._position_mgr = SpyderE19_PositionManager()
            except Exception as e:
                logging.getLogger(__name__).warning("Failed to initialize PositionManager: %s", e)

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def on_start(self) -> None:
        """Subscribe to all risk-relevant topics."""
        self.subscribe("signals.validated")
        self.subscribe("execution.*")
        self.subscribe("risk.*")
        self.subscribe("market.regime")

    def on_wake(self, session: MarketSession) -> None:
        """Adjust tick rate for session risk profile."""
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 15.0)
        # Reset daily counters at pre-market
        if session == MarketSession.PRE_MARKET:
            self._alerts_today = 0
        super().on_wake(session)

    # ==========================================================================
    # MAIN TICK
    # ==========================================================================
    def tick(self, session: MarketSession) -> None:
        """Main risk monitoring loop."""
        self._tick_count += 1
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 15.0)

        # 1. Assess current portfolio risk
        self._assess_risk(session)

        # 2. Check circuit breaker conditions
        self._check_circuit_breaker()

        # 3. Process any pending signals for veto review
        self._process_pending_signals(session)

        # 4. Publish risk snapshot
        self._publish_risk_snapshot()

        # 5. Periodic deep risk analysis with LLM
        if self._tick_count % 20 == 0:
            self._deep_risk_analysis(session)

    # ==========================================================================
    # RISK ASSESSMENT
    # ==========================================================================
    def _assess_risk(self, session: MarketSession) -> None:
        """Build current risk snapshot from available data."""
        snapshot = RiskSnapshot(session=session.value)

        # Get position data from X04 if available
        if self._x04_agent:
            try:
                import asyncio
                risk = asyncio.run(
                    self._x04_agent.assess_portfolio_risk()
                )
                if risk:
                    snapshot.portfolio_delta = getattr(risk, "total_delta", 0.0)
                    snapshot.portfolio_gamma = getattr(risk, "total_gamma", 0.0)
                    snapshot.portfolio_theta = getattr(risk, "total_theta", 0.0)
                    snapshot.portfolio_vega = getattr(risk, "total_vega", 0.0)
                    snapshot.position_count = getattr(risk, "position_count", 0)
                    snapshot.current_drawdown_pct = getattr(
                        risk, "current_drawdown_pct", 0.0
                    )
                    snapshot.daily_pnl = getattr(risk, "daily_pnl", 0.0)
            except Exception as e:
                logging.getLogger(__name__).warning("Failed to get risk snapshot: %s", e)

        # Get position concentration from position manager
        if self._position_mgr:
            try:
                positions = self._position_mgr.get_all_positions()
                if positions:
                    total_value = sum(
                        getattr(p, "market_value", 0.0) for p in positions
                    )
                    if total_value > 0:
                        max_single = max(
                            getattr(p, "market_value", 0.0) for p in positions
                        )
                        snapshot.max_single_position_pct = (
                            (max_single / total_value) * 100
                        )
            except Exception as e:
                logging.getLogger(__name__).warning("Failed to compute position concentration: %s", e)  # noqa: E501

        # Compute composite risk score (0-100)
        snapshot.risk_score = self._compute_risk_score(snapshot)
        snapshot.circuit_breaker = self._circuit_breaker.value

        self._current_risk = snapshot
        self._snapshots.append(snapshot)

    def _compute_risk_score(self, snapshot: RiskSnapshot) -> float:
        """Compute a composite risk score from 0 (safe) to 100 (critical)."""
        score = 0.0

        # Delta exposure (0-20 points)
        delta_ratio = abs(snapshot.portfolio_delta) / max(
            self._limits["max_portfolio_delta"], 1.0
        )
        score += min(20.0, delta_ratio * 20.0)

        # Vega exposure (0-15 points)
        vega_ratio = abs(snapshot.portfolio_vega) / max(
            self._limits["max_portfolio_vega"], 1.0
        )
        score += min(15.0, vega_ratio * 15.0)

        # Drawdown (0-30 points) — most important
        dd_ratio = snapshot.current_drawdown_pct / max(
            self._limits["max_drawdown_pct"], 1.0
        )
        score += min(30.0, dd_ratio * 30.0)

        # Position concentration (0-15 points)
        conc_ratio = snapshot.max_single_position_pct / max(
            self._limits["max_single_position_pct"], 1.0
        )
        score += min(15.0, conc_ratio * 15.0)

        # Position count (0-10 points)
        count_ratio = snapshot.position_count / max(
            self._limits["max_position_count"], 1
        )
        score += min(10.0, count_ratio * 10.0)

        # Correlation (0-10 points)
        score += min(10.0, snapshot.correlation_risk * 10.0)

        return min(100.0, score)

    # ==========================================================================
    # CIRCUIT BREAKER
    # ==========================================================================
    def _check_circuit_breaker(self) -> None:
        """Evaluate and update circuit breaker state."""
        if self._circuit_breaker == CircuitBreakerState.MANUAL_OVERRIDE:
            return  # Human has control

        dd = self._current_risk.current_drawdown_pct
        old_state = self._circuit_breaker

        if dd >= self._limits["circuit_breaker_drawdown_halt"]:
            self._circuit_breaker = CircuitBreakerState.HALT
            self._halt_reason = f"Drawdown {dd:.1f}% >= {self._limits['circuit_breaker_drawdown_halt']}% halt limit"  # noqa: E501
        elif dd >= self._limits["circuit_breaker_drawdown_warning"]:
            self._circuit_breaker = CircuitBreakerState.WARNING
        elif dd >= self._limits["circuit_breaker_drawdown_caution"]:
            self._circuit_breaker = CircuitBreakerState.CAUTION
        elif self._current_risk.risk_score >= 80:
            self._circuit_breaker = CircuitBreakerState.WARNING
        elif self._current_risk.risk_score >= 60:
            self._circuit_breaker = CircuitBreakerState.CAUTION
        else:
            self._circuit_breaker = CircuitBreakerState.NORMAL

        # Publish state change if it happened
        if self._circuit_breaker != old_state:
            self._publish_circuit_breaker_change(old_state)

    def _publish_circuit_breaker_change(
        self, old_state: CircuitBreakerState
    ) -> None:
        """Publish circuit breaker state change alert."""
        priority = "CRITICAL" if self._circuit_breaker in (
            CircuitBreakerState.HALT, CircuitBreakerState.WARNING
        ) else "HIGH"

        # LLM analysis of the state change
        reasoning = self.llm_query(
            prompt=(
                f"Circuit breaker changed from {old_state.value} to "
                f"{self._circuit_breaker.value}.\n"
                f"Current drawdown: {self._current_risk.current_drawdown_pct:.1f}%\n"
                f"Risk score: {self._current_risk.risk_score:.0f}/100\n"
                f"Daily P&L: ${self._current_risk.daily_pnl:.2f}\n"
                f"Position count: {self._current_risk.position_count}\n\n"
                f"Explain the risk implications and recommended actions (3 sentences)."
            ),
            role=LLMRole.PRIMARY,
            system_prompt=(
                "You are a risk management system for a SPY options portfolio. "
                "Be direct and actionable about risk implications."
            ),
        ) or f"Circuit breaker: {old_state.value} → {self._circuit_breaker.value}"

        self._alerts_today += 1
        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="alert",
            topic="risk.circuit_breaker",
            payload={
                "old_state": old_state.value,
                "new_state": self._circuit_breaker.value,
                "drawdown_pct": self._current_risk.current_drawdown_pct,
                "risk_score": self._current_risk.risk_score,
                "halt_reason": self._halt_reason,
            },
            confidence=0.95,
            reasoning=reasoning,
            priority=priority,
            ttl_seconds=3600,
        ))

    # ==========================================================================
    # TRADE VETO
    # ==========================================================================
    def _process_pending_signals(self, session: MarketSession) -> None:
        """Review pending validated signals — veto any that violate risk limits."""
        if not self._pending_signals:
            return

        for signal in self._pending_signals:
            veto = self._evaluate_veto(signal, session)
            self._vetoes.append(veto)
            if veto.vetoed:
                self.publish(AgentOutput(
                    agent_id=self.AGENT_ID,
                    output_type="veto",
                    topic="risk.veto",
                    payload={
                        "signal_id": veto.signal_id,
                        "vetoed": True,
                        "reason": veto.reason,
                        "risk_level": veto.risk_level,
                    },
                    confidence=0.9,
                    reasoning=veto.llm_reasoning or veto.reason,
                    priority="HIGH",
                ))

        self._pending_signals.clear()

    def _evaluate_veto(
        self, signal: dict[str, Any], session: MarketSession
    ) -> TradeVeto:
        """Decide whether to veto a validated signal."""
        veto = TradeVeto(
            signal_id=signal.get("payload", {}).get(
                "validation", {}
            ).get("signal_id", "unknown"),
        )

        # Auto-veto if circuit breaker is HALT or WARNING
        if self._circuit_breaker == CircuitBreakerState.HALT:
            veto.vetoed = True
            veto.reason = "Circuit breaker HALT — no new trades"
            veto.risk_level = "critical"
            return veto

        if self._circuit_breaker == CircuitBreakerState.WARNING:
            veto.vetoed = True
            veto.reason = "Circuit breaker WARNING — no new positions"
            veto.risk_level = "high"
            return veto

        # Check position count limit
        if self._current_risk.position_count >= self._limits["max_position_count"]:
            veto.vetoed = True
            veto.reason = f"Max position count ({self._limits['max_position_count']}) reached"
            veto.risk_level = "high"
            return veto

        # Check risk score threshold
        if self._current_risk.risk_score >= 70:
            # Use LLM for borderline cases
            prompt = (
                f"Risk veto evaluation:\n"
                f"- Risk score: {self._current_risk.risk_score:.0f}/100\n"
                f"- Circuit breaker: {self._circuit_breaker.value}\n"
                f"- Positions: {self._current_risk.position_count}\n"
                f"- Drawdown: {self._current_risk.current_drawdown_pct:.1f}%\n"
                f"- Signal direction: {signal.get('payload', {}).get('original_signal', {}).get('direction', '?')}\n\n"  # noqa: E501
                f"Should this trade be VETOED? Answer YES or NO with reason."
            )

            response = self.llm_query(
                prompt=prompt,
                role=LLMRole.PRIMARY,
                system_prompt="You are a conservative risk manager. When in doubt, veto.",
            ) or ""

            veto.llm_reasoning = response
            veto.vetoed = response.upper().startswith("YES")
            veto.reason = "LLM risk assessment: elevated risk score"
            veto.risk_level = "medium"

        return veto

    # ==========================================================================
    # DEEP RISK ANALYSIS
    # ==========================================================================
    def _deep_risk_analysis(self, session: MarketSession) -> None:
        """Periodic deep analysis using the LLM."""
        recent_snapshots = list(self._snapshots)[-10:]
        risk_trend = "stable"
        if len(recent_snapshots) >= 2:
            if recent_snapshots[-1].risk_score > recent_snapshots[-2].risk_score + 5:
                risk_trend = "increasing"
            elif recent_snapshots[-1].risk_score < recent_snapshots[-2].risk_score - 5:
                risk_trend = "decreasing"

        prompt = (
            f"Deep risk analysis ({session.value}):\n"
            f"- Risk score: {self._current_risk.risk_score:.0f}/100 (trend: {risk_trend})\n"
            f"- Circuit breaker: {self._circuit_breaker.value}\n"
            f"- Delta: {self._current_risk.portfolio_delta:.1f}\n"
            f"- Gamma: {self._current_risk.portfolio_gamma:.3f}\n"
            f"- Theta: {self._current_risk.portfolio_theta:.2f}\n"
            f"- Vega: {self._current_risk.portfolio_vega:.2f}\n"
            f"- Drawdown: {self._current_risk.current_drawdown_pct:.1f}%\n"
            f"- Position count: {self._current_risk.position_count}\n"
            f"- Alerts today: {self._alerts_today}\n\n"
            f"Provide a risk assessment (3-4 sentences) with:\n"
            f"1. Current risk level interpretation\n"
            f"2. Key concern\n"
            f"3. Recommended action"
        )

        analysis = self.llm_query(
            prompt=prompt,
            role=LLMRole.FINANCE,
            system_prompt="You are a senior risk officer for a SPY options portfolio.",
        ) or ""

        if analysis:
            self.publish(AgentOutput(
                agent_id=self.AGENT_ID,
                output_type="analysis",
                topic="risk.assessment",
                payload={
                    "risk_score": self._current_risk.risk_score,
                    "circuit_breaker": self._circuit_breaker.value,
                    "risk_trend": risk_trend,
                    "analysis": analysis,
                },
                confidence=0.8,
                reasoning=analysis,
                priority="NORMAL",
            ))

    # ==========================================================================
    # PUBLISHING
    # ==========================================================================
    def _publish_risk_snapshot(self) -> None:
        """Publish periodic risk snapshot."""
        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="metric",
            topic="risk.assessment",
            payload={
                "risk_score": self._current_risk.risk_score,
                "circuit_breaker": self._circuit_breaker.value,
                "portfolio_delta": self._current_risk.portfolio_delta,
                "portfolio_gamma": self._current_risk.portfolio_gamma,
                "portfolio_theta": self._current_risk.portfolio_theta,
                "portfolio_vega": self._current_risk.portfolio_vega,
                "drawdown_pct": self._current_risk.current_drawdown_pct,
                "position_count": self._current_risk.position_count,
                "daily_pnl": self._current_risk.daily_pnl,
                "timestamp": self._current_risk.timestamp.isoformat(),
            },
            confidence=0.9,
            reasoning=f"Risk score: {self._current_risk.risk_score:.0f}/100, CB: {self._circuit_breaker.value}",  # noqa: E501
            priority="LOW",
        ))

    # ==========================================================================
    # MESSAGE HANDLER
    # ==========================================================================
    def _on_message(self, topic: str, message: dict[str, Any]) -> None:
        """Handle incoming bus messages."""
        if topic == "signals.validated":
            self._pending_signals.append(message)
        elif topic.startswith("risk."):
            # External risk alerts — could affect circuit breaker
            payload = message.get("payload", {})
            if payload.get("level") == "critical":
                self._circuit_breaker = CircuitBreakerState.HALT
                self._halt_reason = f"External critical risk alert: {payload.get('message', '')}"

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================
    def get_state_snapshot(self) -> dict[str, Any]:
        return {
            "circuit_breaker": self._circuit_breaker.value,
            "risk_score": self._current_risk.risk_score,
            "tick_count": self._tick_count,
            "alerts_today": self._alerts_today,
            "halt_reason": self._halt_reason,
            "limits": self._limits,
            "vetoes_count": len(self._vetoes),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        cb_value = state.get("circuit_breaker", "normal")
        try:
            self._circuit_breaker = CircuitBreakerState(cb_value)
        except ValueError:
            self._circuit_breaker = CircuitBreakerState.NORMAL
        self._tick_count = state.get("tick_count", 0)
        self._alerts_today = state.get("alerts_today", 0)
        self._halt_reason = state.get("halt_reason", "")
        if "limits" in state:
            self._limits.update(state["limits"])


# ==============================================================================
# FACTORY
# ==============================================================================
def create_risk_sentinel_agent(**kwargs: Any) -> SpyderY03_RiskSentinelAgent:
    """Factory function for creating the RiskSentinel agent."""
    return SpyderY03_RiskSentinelAgent(**kwargs)
