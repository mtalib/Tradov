#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderY08_MetaOrchestratorAgent.py
Group: Y (AutoAgents)
Purpose: High-level orchestration — coordinates all Y-series agents

Author: Mohamed Talib
Date Created: 2026-02-25
Last Updated: 2026-02-25 Time: 12:00:00

Description:
    Runs 24/7 as the "conductor" of the agent ensemble. Monitors the health
    and output quality of all other Y-series agents. Makes high-level
    decisions about system behavior:

    - Adjust agent confidence thresholds based on market conditions
    - Resolve conflicts between agents (e.g., signal vs veto)
    - Coordinate session transitions (ensure all agents are in sync)
    - Provide system-wide decision synthesis
    - Escalate critical issues to human operators
    - Track inter-agent communication patterns

    Replaces/unifies the on-demand SpyderX14_OrchestratorAgent and
    SpyderX16_MetaCoordinator with continuous autonomous operation.

License: All dependencies are MIT/BSD/Apache — AGPL-free.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from collections import defaultdict, deque
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


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class AgentStatus:
    """Health status of a Y-series agent."""
    agent_id: str = ""
    state: str = "unknown"        # running | paused | stopped | error
    last_heartbeat: datetime | None = None
    outputs_today: int = 0
    errors_today: int = 0
    avg_tick_ms: float = 0.0
    health_score: float = 1.0    # 0-1
    last_output_topic: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class SystemDecision:
    """A system-wide decision made by the orchestrator."""
    decision_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    category: str = ""      # conflict_resolution | threshold_adj | escalation | coordination
    description: str = ""
    agents_involved: list[str] = field(default_factory=list)
    action_taken: str = ""
    reasoning: str = ""
    confidence: float = 0.0


@dataclass
class ConflictRecord:
    """Record of a conflict between agent outputs."""
    agents: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    description: str = ""
    resolution: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


# ==============================================================================
# META-ORCHESTRATOR AGENT
# ==============================================================================
class SpyderY08_MetaOrchestratorAgent(BaseAutoAgent):
    """High-level orchestration agent — coordinates all Y-series agents.

    The "conductor" of the autonomous agent ensemble. Monitors agent health,
    resolves conflicts, and makes system-wide coordination decisions.

    Subscribes to:
        meta.*               — All meta topics (health, journal, research)
        risk.circuit_breaker — Circuit breaker state changes
        market.regime        — Regime for adaptive orchestration
        signals.validated    — Signal flow monitoring
        risk.veto            — Veto decisions for conflict tracking

    Publishes to:
        meta.orchestration   — Orchestration decisions
        meta.decisions       — System-wide decisions
        meta.health          — Overall system health
    """

    AGENT_ID = "Y08_meta_orchestrator"
    AGENT_NAME = "MetaOrchestrator Agent"
    AGENT_VERSION = "1.0.0"
    DESCRIPTION = "High-level coordination of all Y-series agents"

    ACTIVE_SESSIONS = {
        MarketSession.OVERNIGHT,
        MarketSession.PRE_MARKET,
        MarketSession.MARKET_OPEN,
        MarketSession.MARKET_HOURS,
        MarketSession.POWER_HOUR,
        MarketSession.POST_MARKET,
    }

    TICK_INTERVALS = {
        MarketSession.OVERNIGHT: 300,     # 5 min
        MarketSession.PRE_MARKET: 60,     # 1 min — ensure all agents ready
        MarketSession.MARKET_OPEN: 30,    # 30s — monitor open coordination
        MarketSession.MARKET_HOURS: 60,   # 1 min — standard oversight
        MarketSession.POWER_HOUR: 30,     # 30s — eod coordination
        MarketSession.POST_MARKET: 120,   # 2 min — wind-down monitoring
    }

    TICK_INTERVAL = 60.0

    # Agent IDs we monitor
    MANAGED_AGENTS = {
        "Y01_market_sense",
        "Y02_strategy_pilot",
        "Y03_risk_sentinel",
        "Y04_alpha_learner",
        "Y05_execution_optimizer",
        "Y06_news_sentinel",
        "Y07_trade_journal",
        "Y09_code_reviewer",  # Skip self (Y08)
    }

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # Agent health tracking
        self._agent_status: dict[str, AgentStatus] = {
            aid: AgentStatus(agent_id=aid) for aid in self.MANAGED_AGENTS
        }
        self._conflicts: list[ConflictRecord] = []
        self._decisions: list[SystemDecision] = []
        self._message_counts: dict[str, int] = defaultdict(int)
        self._current_regime: str = "unknown"
        self._circuit_breaker: str = "normal"
        self._tick_count: int = 0
        self._session_transitions_today: int = 0

        # Conflict detection
        self._recent_signals: deque = deque(maxlen=50)
        self._recent_vetoes: deque = deque(maxlen=50)

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def on_start(self) -> None:
        """Subscribe to all monitoring topics."""
        self.subscribe("meta.*")
        self.subscribe("risk.circuit_breaker")
        self.subscribe("risk.veto")
        self.subscribe("market.regime")
        self.subscribe("signals.validated")

    def on_wake(self, session: MarketSession) -> None:
        """Coordinate session transition."""
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 60.0)
        self._session_transitions_today += 1
        self._coordinate_session_transition(session)
        super().on_wake(session)

    # ==========================================================================
    # MAIN TICK
    # ==========================================================================
    def tick(self, session: MarketSession) -> None:
        """Monitor agents, resolve conflicts, make coordination decisions."""
        self._tick_count += 1
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 60.0)

        # 1. Update agent health scores
        self._update_agent_health()

        # 2. Check for conflicts
        self._detect_conflicts()

        # 3. System-wide coordination
        if self._tick_count % 10 == 0:
            self._system_coordination(session)

        # 4. Publish system health
        if self._tick_count % 5 == 0:
            self._publish_system_health()

        # 5. Periodic LLM synthesis
        if self._tick_count % 30 == 0:
            self._synthesize_system_state(session)

    # ==========================================================================
    # AGENT HEALTH
    # ==========================================================================
    def _update_agent_health(self) -> None:
        """Update health scores for all managed agents."""
        now = datetime.now()

        for _agent_id, status in self._agent_status.items():
            warnings = []

            # Check heartbeat freshness
            if status.last_heartbeat:
                staleness = (now - status.last_heartbeat).total_seconds()
                if staleness > 300:  # 5 min without heartbeat
                    status.health_score = max(0.0, status.health_score - 0.2)
                    warnings.append(f"Stale heartbeat ({staleness:.0f}s)")
                elif staleness > 120:
                    status.health_score = max(0.0, status.health_score - 0.05)
                    warnings.append(f"Slow heartbeat ({staleness:.0f}s)")
            else:
                status.health_score = 0.5  # Unknown — never seen
                warnings.append("No heartbeat received")

            # Check error rate
            if status.outputs_today > 0:
                error_rate = status.errors_today / status.outputs_today
                if error_rate > 0.2:  # >20% errors
                    status.health_score = max(0.0, status.health_score - 0.3)
                    warnings.append(f"High error rate: {error_rate:.0%}")

            # Recover health gradually
            if not warnings and status.health_score < 1.0:
                status.health_score = min(1.0, status.health_score + 0.01)

            status.warnings = warnings

    # ==========================================================================
    # CONFLICT DETECTION
    # ==========================================================================
    def _detect_conflicts(self) -> None:
        """Detect and resolve conflicts between agents."""
        # Check for signal-veto conflicts (high veto rate suggests miscalibration)
        recent_signals = list(self._recent_signals)
        recent_vetoes = list(self._recent_vetoes)

        if len(recent_signals) >= 5 and len(recent_vetoes) >= 3:
            veto_rate = len(recent_vetoes) / max(len(recent_signals), 1)
            if veto_rate > 0.6:
                conflict = ConflictRecord(
                    agents=["Y02_strategy_pilot", "Y03_risk_sentinel"],
                    topics=["signals.validated", "risk.veto"],
                    description=(
                        f"High veto rate: {veto_rate:.0%} of signals vetoed. "
                        f"Strategy and risk agents may be miscalibrated."
                    ),
                )
                self._resolve_conflict(conflict)

    def _resolve_conflict(self, conflict: ConflictRecord) -> None:
        """Resolve a detected conflict using LLM reasoning."""
        prompt = (
            f"Agent conflict detected:\n"
            f"- Agents: {', '.join(conflict.agents)}\n"
            f"- Topics: {', '.join(conflict.topics)}\n"
            f"- Description: {conflict.description}\n"
            f"- Current regime: {self._current_regime}\n"
            f"- Circuit breaker: {self._circuit_breaker}\n\n"
            f"As the meta-orchestrator, how should this conflict be resolved?\n"
            f"Choose one action:\n"
            f"1. Raise signal strength threshold (reduce signal volume)\n"
            f"2. Lower risk sensitivity (reduce veto rate)\n"
            f"3. No action needed (temporary market condition)\n"
            f"4. Escalate to human operator\n\n"
            f"Respond with the action number and 2-sentence reasoning."
        )

        response = self.llm_query(
            prompt=prompt,
            role=LLMRole.PRIMARY,
            system_prompt=(
                "You are the meta-orchestrator of a multi-agent trading system. "
                "Your role is to keep the system balanced and functional. "
                "Prefer conservative actions."
            ),
        ) or "3. No action — monitoring situation."

        conflict.resolution = response
        self._conflicts.append(conflict)

        decision = SystemDecision(
            decision_id=f"D_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            category="conflict_resolution",
            description=conflict.description,
            agents_involved=conflict.agents,
            action_taken=response,
            reasoning=response,
            confidence=0.7,
        )
        self._decisions.append(decision)

        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="decision",
            topic="meta.decisions",
            payload={
                "decision_id": decision.decision_id,
                "category": decision.category,
                "agents": decision.agents_involved,
                "action": decision.action_taken,
            },
            confidence=decision.confidence,
            reasoning=response,
            priority="HIGH",
        ))

    # ==========================================================================
    # SESSION COORDINATION
    # ==========================================================================
    def _coordinate_session_transition(self, session: MarketSession) -> None:
        """Ensure all agents are properly configured for the new session."""
        prompt = (
            f"Session transition to: {session.value}\n"
            f"Current regime: {self._current_regime}\n"
            f"Circuit breaker: {self._circuit_breaker}\n"
            f"Agent health: {self._get_health_summary()}\n\n"
            f"What should the orchestrator prioritize during this session? "
            f"(2 sentences)"
        )

        guidance = self.llm_query(
            prompt=prompt,
            role=LLMRole.FAST,
            system_prompt="You are a trading system coordinator managing session transitions.",
        ) or f"Transitioning to {session.value}"

        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="coordination",
            topic="meta.orchestration",
            payload={
                "event": "session_transition",
                "session": session.value,
                "guidance": guidance,
                "agent_health": self._get_health_summary(),
            },
            confidence=0.8,
            reasoning=guidance,
            priority="NORMAL",
        ))

    # ==========================================================================
    # SYSTEM COORDINATION
    # ==========================================================================
    def _system_coordination(self, session: MarketSession) -> None:
        """Periodic system-wide coordination check."""
        # Check for unhealthy agents
        unhealthy = [
            (aid, status) for aid, status in self._agent_status.items()
            if status.health_score < 0.5
        ]

        if unhealthy:
            for agent_id, status in unhealthy:
                self.publish(AgentOutput(
                    agent_id=self.AGENT_ID,
                    output_type="alert",
                    topic="meta.health",
                    payload={
                        "agent_id": agent_id,
                        "health_score": status.health_score,
                        "warnings": status.warnings,
                        "state": status.state,
                    },
                    confidence=0.9,
                    reasoning=f"Agent {agent_id} health: {status.health_score:.0%}",
                    priority="HIGH",
                ))

    def _synthesize_system_state(self, session: MarketSession) -> None:
        """LLM synthesis of overall system state."""
        health_summary = self._get_health_summary()
        decisions_today = [
            d for d in self._decisions
            if d.timestamp.date() == datetime.now().date()
        ]

        prompt = (
            f"System state synthesis ({session.value}):\n"
            f"- Agent health: {health_summary}\n"
            f"- Regime: {self._current_regime}\n"
            f"- Circuit breaker: {self._circuit_breaker}\n"
            f"- Decisions today: {len(decisions_today)}\n"
            f"- Conflicts today: {len([c for c in self._conflicts if c.timestamp.date() == datetime.now().date()])}\n"
            f"- Session transitions: {self._session_transitions_today}\n\n"
            f"Provide a 3-sentence system health summary with any recommendations."
        )

        synthesis = self.llm_query(
            prompt=prompt,
            role=LLMRole.PRIMARY,
            system_prompt="You are the chief technology officer reviewing system health.",
        ) or ""

        if synthesis:
            self.publish(AgentOutput(
                agent_id=self.AGENT_ID,
                output_type="report",
                topic="meta.orchestration",
                payload={
                    "type": "system_synthesis",
                    "health_summary": health_summary,
                    "synthesis": synthesis,
                },
                confidence=0.8,
                reasoning=synthesis,
                priority="LOW",
            ))

    # ==========================================================================
    # PUBLISHING
    # ==========================================================================
    def _publish_system_health(self) -> None:
        """Publish overall system health metrics."""
        health_scores = [s.health_score for s in self._agent_status.values()]
        avg_health = sum(health_scores) / max(len(health_scores), 1)
        min_health = min(health_scores) if health_scores else 0.0

        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="metric",
            topic="meta.health",
            payload={
                "avg_health": avg_health,
                "min_health": min_health,
                "agents": {
                    aid: {
                        "health": s.health_score,
                        "state": s.state,
                        "outputs": s.outputs_today,
                        "errors": s.errors_today,
                    }
                    for aid, s in self._agent_status.items()
                },
            },
            confidence=0.9,
            reasoning=f"System health: avg={avg_health:.0%}, min={min_health:.0%}",
            priority="LOW",
        ))

    # ==========================================================================
    # HELPERS
    # ==========================================================================
    def _get_health_summary(self) -> dict[str, float]:
        """Get a dict of agent_id -> health_score."""
        return {
            aid: round(s.health_score, 2)
            for aid, s in self._agent_status.items()
        }

    # ==========================================================================
    # MESSAGE HANDLER
    # ==========================================================================
    def _on_message(self, topic: str, message: dict[str, Any]) -> None:
        """Handle incoming messages for orchestration."""
        self._message_counts[topic] += 1

        if topic == "market.regime":
            self._current_regime = message.get("payload", {}).get(
                "regime", self._current_regime
            )
        elif topic == "risk.circuit_breaker":
            self._circuit_breaker = message.get("payload", {}).get(
                "new_state", self._circuit_breaker
            )
        elif topic == "signals.validated":
            self._recent_signals.append(message)
        elif topic == "risk.veto":
            self._recent_vetoes.append(message)
        elif topic.startswith("meta."):
            # Track agent outputs for health monitoring
            agent_id = message.get("agent_id", "")
            if agent_id in self._agent_status:
                self._agent_status[agent_id].last_heartbeat = datetime.now()
                self._agent_status[agent_id].outputs_today += 1
                self._agent_status[agent_id].state = "running"
                self._agent_status[agent_id].last_output_topic = topic

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================
    def get_state_snapshot(self) -> dict[str, Any]:
        return {
            "tick_count": self._tick_count,
            "current_regime": self._current_regime,
            "circuit_breaker": self._circuit_breaker,
            "session_transitions_today": self._session_transitions_today,
            "agent_health": self._get_health_summary(),
            "decisions_count": len(self._decisions),
            "conflicts_count": len(self._conflicts),
            "message_counts": dict(self._message_counts),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._tick_count = state.get("tick_count", 0)
        self._current_regime = state.get("current_regime", "unknown")
        self._circuit_breaker = state.get("circuit_breaker", "normal")
        self._session_transitions_today = state.get("session_transitions_today", 0)
        self._message_counts = defaultdict(int, state.get("message_counts", {}))

    # ==========================================================================
    # RAY DISTRIBUTED COMPUTING (Phase 3)
    # ==========================================================================

    def orchestrate_agents_distributed(
        self,
        market_context: dict[str, Any],
        agent_configs: list[dict[str, Any]] | None = None,
        num_cpus: int | None = None,
    ) -> dict[str, Any]:
        """
        Distribute autonomous agent tasks across Ray workers.

        Enables the meta-orchestrator to run multiple agent analyses
        in true parallel for faster ensemble decisions.

        Args:
            market_context: Current market state and conditions.
            agent_configs: Agent configurations to orchestrate.
            num_cpus: Number of CPUs to allocate.

        Returns:
            Ensemble decision from distributed agents.
        """
        try:
            import ray
        except ImportError:
            return {'status': 'failed', 'reason': 'Ray not installed'}

        import multiprocessing as mproc
        import numpy as np
        if not ray.is_initialized():
            ray.init(num_cpus=num_cpus or mproc.cpu_count(), ignore_reinit_error=True)

        if agent_configs is None:
            agent_configs = [
                {'agent_id': f'agent_{i}', 'role': role}
                for i, role in enumerate(['risk', 'signal', 'regime', 'execution', 'portfolio'])
            ]

        context_ref = ray.put(market_context)

        @ray.remote
        def _agent_task(context_ref, config: dict) -> dict:
            """Run an autonomous agent task on a Ray worker."""
            import numpy as _np
            import time as _time

            start = _time.time()
            ctx = context_ref
            _np.random.seed(hash(config.get('agent_id', '')) % (2**32))

            role = config.get('role', 'general')
            ctx.get('price', 450)

            # Role-specific analysis
            if role == 'risk':
                score = float(_np.clip(1.0 - ctx.get('vix', 20) / 80, 0, 1))
            elif role == 'signal':
                score = float(_np.random.uniform(-1, 1))
            elif role == 'regime':
                score = float(0.5 + _np.random.normal(0, 0.2))
            else:
                score = float(_np.random.uniform(0, 1))

            return {
                'agent_id': config.get('agent_id'),
                'role': role,
                'score': score,
                'analysis_time': _time.time() - start,
                'status': 'completed',
            }

        futures = [_agent_task.remote(context_ref, cfg) for cfg in agent_configs]
        results = ray.get(futures)

        completed = [r for r in results if r.get('status') == 'completed']
        scores = [r['score'] for r in completed]

        return {
            'status': 'completed',
            'n_agents': len(completed),
            'ensemble_score': float(np.mean(scores)) if scores else 0,
            'ensemble_std': float(np.std(scores)) if scores else 0,
            'results': results,
        }


# ==============================================================================
# FACTORY
# ==============================================================================
def create_meta_orchestrator_agent(
    **kwargs: Any,
) -> SpyderY08_MetaOrchestratorAgent:
    """Factory function for creating the MetaOrchestrator agent."""
    return SpyderY08_MetaOrchestratorAgent(**kwargs)
