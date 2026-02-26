#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderY02_StrategyPilotAgent.py
Group: Y (AutoAgents)
Purpose: Autonomous strategy selection, parameter tuning, and signal validation

Author: Mohamed Talib
Date Created: 2026-02-25
Last Updated: 2026-02-25 Time: 12:00:00

Description:
    Active during market hours. Subscribes to signals from the signal pipeline
    (SpyderS) and market regime updates (from Y01). Uses a local LLM to
    validate signal quality, select optimal strategies for the current regime,
    and dynamically tune strategy parameters.

    Wraps SpyderX03_StrategyDirectorAgent with autonomous scheduling and
    LLM-powered reasoning about strategy allocation.

License: All dependencies are MIT/BSD/Apache — AGPL-free.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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
    from Spyder.SpyderX_Agents.SpyderX03_StrategyDirectorAgent import (
        SpyderX03_StrategyDirectorAgent,
    )
    X03_AVAILABLE = True
except ImportError:
    X03_AVAILABLE = False

try:
    from Spyder.SpyderD_Strategies import StrategyRegistry
    STRATEGIES_AVAILABLE = True
except ImportError:
    STRATEGIES_AVAILABLE = False


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SignalValidation:
    """Result of LLM-assisted signal validation."""
    signal_id: str = ""
    signal_source: str = ""
    signal_type: str = ""
    direction: str = ""       # bullish | bearish | neutral
    strength: float = 0.0
    regime_alignment: bool = False
    llm_assessment: str = ""  # LLM's reasoning
    approved: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StrategyAllocation:
    """A strategy allocation decision made by the agent."""
    strategy_name: str = ""
    allocation_pct: float = 0.0
    regime: str = ""
    reasoning: str = ""
    confidence: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


# ==============================================================================
# STRATEGY PILOT AGENT
# ==============================================================================
class SpyderY02_StrategyPilotAgent(BaseAutoAgent):
    """Autonomous strategy selection and signal validation agent.

    Active during market hours. Validates incoming signals against the
    current regime, selects strategy allocations, and tunes parameters
    dynamically using a local LLM.

    Subscribes to:
        signals.*           — Raw signals from the signal pipeline
        market.regime       — Current regime from Y01 MarketSense
        market.analysis     — Full market context from Y01

    Publishes to:
        signals.validated   — Approved signals with LLM reasoning
        strategy.allocation — Current strategy allocation decisions
        strategy.tuning     — Parameter adjustments
    """

    AGENT_ID = "Y02_strategy_pilot"
    AGENT_NAME = "StrategyPilot Agent"
    AGENT_VERSION = "1.0.0"
    DESCRIPTION = "Strategy selection, signal validation, and parameter tuning"

    # Market hours only (including open/power hour)
    ACTIVE_SESSIONS = {
        MarketSession.PRE_MARKET,
        MarketSession.MARKET_OPEN,
        MarketSession.MARKET_HOURS,
        MarketSession.POWER_HOUR,
    }

    TICK_INTERVALS = {
        MarketSession.PRE_MARKET: 120,    # 2 min — strategy prep
        MarketSession.MARKET_OPEN: 15,    # 15s — rapid signal validation
        MarketSession.MARKET_HOURS: 30,   # 30s — standard operations
        MarketSession.POWER_HOUR: 20,     # 20s — end-of-day positioning
    }

    TICK_INTERVAL = 30.0

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # Internal state
        self._current_regime: str = "unknown"
        self._regime_confidence: float = 0.0
        self._pending_signals: List[Dict[str, Any]] = []
        self._validated_signals: List[SignalValidation] = []
        self._current_allocation: List[StrategyAllocation] = []
        self._signal_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"received": 0, "approved": 0, "rejected": 0}
        )
        self._tick_count: int = 0

        # X-agent delegate
        self._x03_agent: Optional[Any] = None
        if X03_AVAILABLE:
            try:
                self._x03_agent = SpyderX03_StrategyDirectorAgent()
            except Exception:
                pass

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def on_start(self) -> None:
        """Subscribe to signal and market topics."""
        self.subscribe("signals.*")
        self.subscribe("market.regime")
        self.subscribe("market.analysis")

    def on_wake(self, session: MarketSession) -> None:
        """Prepare for market session."""
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 30.0)

        # Pre-market: generate strategy plan for the day
        if session == MarketSession.PRE_MARKET:
            self._generate_daily_strategy_plan()

        super().on_wake(session)

    # ==========================================================================
    # MAIN TICK
    # ==========================================================================
    def tick(self, session: MarketSession) -> None:
        """Process pending signals and adjust strategy allocation."""
        self._tick_count += 1
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 30.0)

        # Process any pending signals from the message bus
        self._process_pending_signals(session)

        # Periodically re-evaluate strategy allocation
        if self._tick_count % 10 == 0:
            self._evaluate_allocation(session)

        # Power hour: prepare EOD positioning
        if session == MarketSession.POWER_HOUR and self._tick_count % 5 == 0:
            self._eod_positioning_analysis()

    # ==========================================================================
    # SIGNAL VALIDATION
    # ==========================================================================
    def _process_pending_signals(self, session: MarketSession) -> None:
        """Validate pending signals using LLM + quantitative checks."""
        if not self._pending_signals:
            return

        signals_to_process = self._pending_signals[:5]  # Batch of 5
        self._pending_signals = self._pending_signals[5:]

        for signal in signals_to_process:
            validation = self._validate_signal(signal, session)
            self._validated_signals.append(validation)

            source = signal.get("source", "unknown")
            self._signal_stats[source]["received"] += 1

            if validation.approved:
                self._signal_stats[source]["approved"] += 1
                self._publish_validated_signal(validation, signal)
            else:
                self._signal_stats[source]["rejected"] += 1

    def _validate_signal(
        self, signal: Dict[str, Any], session: MarketSession
    ) -> SignalValidation:
        """Validate a signal using regime alignment and LLM reasoning."""
        validation = SignalValidation(
            signal_id=signal.get("id", "unknown"),
            signal_source=signal.get("source", "unknown"),
            signal_type=signal.get("type", "unknown"),
            direction=signal.get("direction", "neutral"),
            strength=signal.get("strength", 0.0),
        )

        # Check regime alignment
        direction = signal.get("direction", "neutral")
        if self._current_regime in ("bull_quiet", "bull_volatile") and direction == "bullish":
            validation.regime_alignment = True
        elif self._current_regime in ("bear_quiet", "bear_volatile") and direction == "bearish":
            validation.regime_alignment = True
        elif self._current_regime == "neutral":
            validation.regime_alignment = True  # Neutral allows both

        # LLM validation — only for signals above minimum strength
        strength = signal.get("strength", 0.0)
        if strength >= 0.3:
            prompt = (
                f"Signal validation request:\n"
                f"- Source: {signal.get('source', '?')}\n"
                f"- Type: {signal.get('type', '?')}\n"
                f"- Direction: {direction}\n"
                f"- Strength: {strength:.2f}\n"
                f"- Current regime: {self._current_regime} "
                f"(confidence: {self._regime_confidence:.0%})\n"
                f"- Session: {session.value}\n"
                f"- Regime aligned: {validation.regime_alignment}\n\n"
                f"Should this signal be approved for trading? "
                f"Answer YES or NO with a 2-sentence justification."
            )

            response = self.llm_query(
                prompt=prompt,
                role=LLMRole.PRIMARY,
                system_prompt=(
                    "You are a signal validator for a SPY options trading system. "
                    "Only approve signals that are aligned with the current regime, "
                    "have sufficient strength, and are appropriate for the session. "
                    "Be conservative — reject marginal signals."
                ),
            ) or ""

            validation.llm_assessment = response
            validation.approved = (
                response.upper().startswith("YES")
                and validation.regime_alignment
                and strength >= 0.5
            )
        else:
            validation.llm_assessment = "Below minimum strength threshold"
            validation.approved = False

        return validation

    # ==========================================================================
    # STRATEGY ALLOCATION
    # ==========================================================================
    def _evaluate_allocation(self, session: MarketSession) -> None:
        """Re-evaluate strategy allocation based on current regime."""
        if not self._current_regime or self._current_regime == "unknown":
            return

        # Basic allocation from X03 if available
        base_allocation = {}
        if self._x03_agent:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(
                    self._x03_agent.select_strategy(regime=self._current_regime)
                )
                loop.close()
                if result:
                    base_allocation = getattr(result, "allocation", {})
            except Exception:
                pass

        # LLM enhancement of allocation
        recent_approvals = sum(
            1 for v in self._validated_signals[-20:] if v.approved
        )
        recent_rejections = sum(
            1 for v in self._validated_signals[-20:] if not v.approved
        )

        prompt = (
            f"Current regime: {self._current_regime} "
            f"(confidence: {self._regime_confidence:.0%})\n"
            f"Session: {session.value}\n"
            f"Base allocation from quant model: {base_allocation}\n"
            f"Recent signal approvals: {recent_approvals}/{recent_approvals + recent_rejections}\n\n"
            f"Recommend strategy allocation percentages for:\n"
            f"1. Iron Condors (range-bound)\n"
            f"2. Vertical Spreads (directional)\n"
            f"3. Calendar Spreads (vol play)\n"
            f"4. Butterflies (precise targeting)\n"
            f"5. Cash reserve\n\n"
            f"Output as JSON: {{\"iron_condor\": X, \"vertical\": X, "
            f"\"calendar\": X, \"butterfly\": X, \"cash\": X}} where values sum to 100."
        )

        allocation_response = self.llm_query_json(
            prompt=prompt,
            role=LLMRole.PRIMARY,
            system_prompt=(
                "You are a portfolio allocation specialist for SPY options. "
                "Allocate capital across strategies based on regime, signal quality, "
                "and session. Always maintain minimum 10% cash reserve."
            ),
        ) or {}

        if allocation_response:
            self._current_allocation = [
                StrategyAllocation(
                    strategy_name=name,
                    allocation_pct=float(pct),
                    regime=self._current_regime,
                    confidence=self._regime_confidence,
                )
                for name, pct in allocation_response.items()
            ]

            self.publish(AgentOutput(
                agent_id=self.AGENT_ID,
                output_type="decision",
                topic="strategy.allocation",
                payload=allocation_response,
                confidence=self._regime_confidence,
                reasoning=f"Allocation for {self._current_regime} regime in {session.value}",
                priority="NORMAL",
            ))

    # ==========================================================================
    # DAILY PLANNING
    # ==========================================================================
    def _generate_daily_strategy_plan(self) -> None:
        """Pre-market: generate a strategy plan for the day."""
        prompt = (
            f"Pre-market strategy planning:\n"
            f"- Last known regime: {self._current_regime}\n"
            f"- Regime confidence: {self._regime_confidence:.0%}\n"
            f"- Yesterday's signal approval rate: "
            f"{self._get_yesterday_approval_rate():.0%}\n\n"
            f"Outline a 3-point strategy priority list for today's SPY options "
            f"trading session."
        )

        plan = self.llm_query(
            prompt=prompt,
            role=LLMRole.PRIMARY,
            system_prompt=(
                "You are a senior options strategist preparing the daily trading plan. "
                "Be specific, actionable, and concise."
            ),
        ) or "Plan generation unavailable."

        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="report",
            topic="strategy.plan",
            payload={"plan": plan, "date": datetime.now().strftime("%Y-%m-%d")},
            confidence=0.7,
            reasoning=plan,
            priority="NORMAL",
            ttl_seconds=43200,  # 12 hours
        ))

    def _eod_positioning_analysis(self) -> None:
        """Power hour: analyze end-of-day positioning needs."""
        prompt = (
            f"Power hour positioning analysis:\n"
            f"- Current regime: {self._current_regime}\n"
            f"- Today's signals approved: "
            f"{sum(1 for v in self._validated_signals if v.approved and v.timestamp.date() == datetime.now().date())}\n"
            f"- Current allocation: {[a.strategy_name + ':' + str(a.allocation_pct) + '%' for a in self._current_allocation]}\n\n"
            f"Should any positions be adjusted before close? "
            f"Consider overnight risk, theta decay, and next-day catalysts."
        )

        analysis = self.llm_query(
            prompt=prompt,
            role=LLMRole.PRIMARY,
            system_prompt="You are analyzing end-of-day positioning for a SPY options portfolio.",
        ) or ""

        if analysis:
            self.publish(AgentOutput(
                agent_id=self.AGENT_ID,
                output_type="recommendation",
                topic="strategy.eod",
                payload={"analysis": analysis},
                confidence=0.6,
                reasoning=analysis,
                priority="HIGH",
                ttl_seconds=3600,
            ))

    # ==========================================================================
    # PUBLISHING
    # ==========================================================================
    def _publish_validated_signal(
        self, validation: SignalValidation, original_signal: Dict[str, Any]
    ) -> None:
        """Publish an approved signal."""
        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="signal",
            topic="signals.validated",
            payload={
                "original_signal": original_signal,
                "validation": {
                    "signal_id": validation.signal_id,
                    "approved": validation.approved,
                    "regime_alignment": validation.regime_alignment,
                    "llm_assessment": validation.llm_assessment,
                },
            },
            confidence=validation.strength,
            reasoning=validation.llm_assessment,
            priority="HIGH",
        ))

    # ==========================================================================
    # HELPERS
    # ==========================================================================
    def _get_yesterday_approval_rate(self) -> float:
        """Calculate yesterday's signal approval rate."""
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).date()
        yesterday_signals = [
            v for v in self._validated_signals
            if v.timestamp.date() == yesterday
        ]
        if not yesterday_signals:
            return 0.0
        approved = sum(1 for v in yesterday_signals if v.approved)
        return approved / len(yesterday_signals)

    # ==========================================================================
    # MESSAGE HANDLER
    # ==========================================================================
    def _on_message(self, topic: str, message: Dict[str, Any]) -> None:
        """Handle incoming bus messages."""
        if topic == "market.regime":
            payload = message.get("payload", {})
            self._current_regime = payload.get("regime", self._current_regime)
            self._regime_confidence = payload.get(
                "confidence", self._regime_confidence
            )
        elif topic.startswith("signals.") and topic != "signals.validated":
            self._pending_signals.append(message)

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================
    def get_state_snapshot(self) -> Dict[str, Any]:
        """Return state for persistence."""
        return {
            "current_regime": self._current_regime,
            "regime_confidence": self._regime_confidence,
            "tick_count": self._tick_count,
            "signal_stats": dict(self._signal_stats),
            "current_allocation": [
                {
                    "strategy": a.strategy_name,
                    "pct": a.allocation_pct,
                    "regime": a.regime,
                }
                for a in self._current_allocation
            ],
        }

    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore state from persistence."""
        self._current_regime = state.get("current_regime", "unknown")
        self._regime_confidence = state.get("regime_confidence", 0.0)
        self._tick_count = state.get("tick_count", 0)
        self._signal_stats = defaultdict(
            lambda: {"received": 0, "approved": 0, "rejected": 0},
            state.get("signal_stats", {}),
        )


# ==============================================================================
# FACTORY
# ==============================================================================
def create_strategy_pilot_agent(**kwargs: Any) -> SpyderY02_StrategyPilotAgent:
    """Factory function for creating the StrategyPilot agent."""
    return SpyderY02_StrategyPilotAgent(**kwargs)
