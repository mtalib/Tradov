#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderY07_TradeJournalAgent.py
Group: Y (AutoAgents)
Purpose: Automated trade journaling, performance attribution, and learning

Author: Mohamed Talib
Date Created: 2026-02-25
Last Updated: 2026-02-25 Time: 12:00:00

Description:
    Primarily active post-market. Maintains a comprehensive trade journal
    with LLM-generated analysis of every trade. Performs daily, weekly,
    and monthly performance attribution.

    This is a NEW agent (no X-series equivalent). It fills the critical gap
    of systematic trade review and learning from outcomes.

    Key responsibilities:
    - Log every trade with full context (regime, signals, sentiment)
    - Generate LLM narrative for each trade outcome
    - Daily P&L breakdown with performance attribution
    - Weekly performance review with pattern identification
    - Monthly strategy effectiveness analysis
    - Learning extraction — what worked and what didn't
    - Publish actionable insights to meta.performance

License: All dependencies are MIT/BSD/Apache — AGPL-free.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from collections import defaultdict
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
class TradeEntry:
    """A single trade journal entry."""
    trade_id: str = ""
    symbol: str = "SPY"
    strategy: str = ""
    direction: str = ""
    entry_time: str = ""
    exit_time: str = ""
    entry_price: float = 0.0
    exit_price: float = 0.0
    contracts: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    regime_at_entry: str = ""
    regime_at_exit: str = ""
    signal_source: str = ""
    signal_strength: float = 0.0
    sentiment_at_entry: float = 0.0
    vix_at_entry: float = 0.0
    hold_duration_minutes: int = 0
    slippage_bps: float = 0.0
    narrative: str = ""    # LLM-generated analysis
    lessons: str = ""      # LLM-extracted lessons
    tags: list[str] = field(default_factory=list)


@dataclass
class DailyPerformance:
    """Daily performance summary."""
    date: str = ""
    total_pnl: float = 0.0
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    by_strategy: dict[str, float] = field(default_factory=dict)
    narrative: str = ""


# ==============================================================================
# TRADE JOURNAL AGENT
# ==============================================================================
class SpyderY07_TradeJournalAgent(BaseAutoAgent):
    """Automated trade journaling and performance attribution agent.

    Primarily active post-market. Records, analyzes, and learns from
    every trade using LLM-powered narrative generation.

    Subscribes to:
        execution.filled     — Completed trades from Y05
        execution.metrics    — Fill quality data
        market.regime        — Regime context
        market.sentiment     — Sentiment context
        risk.assessment      — Risk context

    Publishes to:
        meta.journal         — Trade journal entries
        meta.performance     — Performance summaries and insights
        meta.lessons         — Extracted lessons and patterns
    """

    AGENT_ID = "Y07_trade_journal"
    AGENT_NAME = "TradeJournal Agent"
    AGENT_VERSION = "1.0.0"
    DESCRIPTION = "Automated trade journaling with LLM-powered analysis and learning"

    # Primarily post-market, but listens during market hours too
    ACTIVE_SESSIONS = {
        MarketSession.MARKET_HOURS,
        MarketSession.POWER_HOUR,
        MarketSession.POST_MARKET,
    }

    TICK_INTERVALS = {
        MarketSession.MARKET_HOURS: 300,  # 5 min — log new fills
        MarketSession.POWER_HOUR: 120,    # 2 min — log eod fills
        MarketSession.POST_MARKET: 60,    # 1 min — main analysis window
    }

    TICK_INTERVAL = 120.0

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # Journal
        self._pending_fills: list[dict[str, Any]] = []
        self._trade_entries: list[TradeEntry] = []
        self._daily_summaries: list[DailyPerformance] = []
        self._current_regime: str = "unknown"
        self._current_sentiment: float = 0.0
        self._tick_count: int = 0
        self._daily_summary_generated: bool = False
        self._weekly_review_day: int = 4  # Friday

        # Performance tracking
        self._cumulative_pnl: float = 0.0
        self._strategy_pnl: dict[str, float] = defaultdict(float)
        self._regime_pnl: dict[str, float] = defaultdict(float)

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def on_start(self) -> None:
        """Subscribe to trade and context topics."""
        self.subscribe("execution.filled")
        self.subscribe("execution.metrics")
        self.subscribe("market.regime")
        self.subscribe("market.sentiment")
        self.subscribe("risk.assessment")

    def on_wake(self, session: MarketSession) -> None:
        """Session preparation."""
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 120.0)

        if session == MarketSession.POST_MARKET:
            self._daily_summary_generated = False

        super().on_wake(session)

    # ==========================================================================
    # MAIN TICK
    # ==========================================================================
    def tick(self, session: MarketSession) -> None:
        """Process fills and generate analysis."""
        self._tick_count += 1
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 120.0)

        # 1. Process new fills into journal entries
        self._process_fills()

        # 2. Post-market: generate daily summary
        if session == MarketSession.POST_MARKET and not self._daily_summary_generated:
            self._generate_daily_summary()
            self._daily_summary_generated = True

            # Weekly review on Fridays
            if datetime.now().weekday() == self._weekly_review_day:
                self._generate_weekly_review()

    # ==========================================================================
    # FILL PROCESSING
    # ==========================================================================
    def _process_fills(self) -> None:
        """Convert filled orders into journal entries with LLM analysis."""
        if not self._pending_fills:
            return

        for fill in self._pending_fills:
            entry = self._create_journal_entry(fill)
            entry.narrative = self._generate_trade_narrative(entry)
            self._trade_entries.append(entry)

            # Update cumulative tracking
            self._cumulative_pnl += entry.pnl
            self._strategy_pnl[entry.strategy] += entry.pnl
            self._regime_pnl[entry.regime_at_entry] += entry.pnl

            # Publish journal entry
            self.publish(AgentOutput(
                agent_id=self.AGENT_ID,
                output_type="journal",
                topic="meta.journal",
                payload={
                    "trade_id": entry.trade_id,
                    "strategy": entry.strategy,
                    "direction": entry.direction,
                    "pnl": entry.pnl,
                    "pnl_pct": entry.pnl_pct,
                    "regime": entry.regime_at_entry,
                    "narrative": entry.narrative,
                    "tags": entry.tags,
                },
                confidence=0.9,
                reasoning=entry.narrative,
                priority="LOW",
            ))

        self._pending_fills.clear()

    def _create_journal_entry(self, fill: dict[str, Any]) -> TradeEntry:
        """Create a journal entry from a fill event."""
        payload = fill.get("payload", {})
        return TradeEntry(
            trade_id=payload.get("plan_id", f"T_{datetime.now().strftime('%H%M%S')}"),
            direction=payload.get("direction", "unknown"),
            entry_price=payload.get("entry_price", 0.0),
            exit_price=payload.get("filled_price", 0.0),
            contracts=payload.get("contracts", 0),
            pnl=payload.get("pnl", 0.0),
            slippage_bps=payload.get("slippage_bps", 0.0),
            regime_at_entry=self._current_regime,
            sentiment_at_entry=self._current_sentiment,
            entry_time=payload.get("entry_time", datetime.now().isoformat()),
            exit_time=payload.get("exit_time", datetime.now().isoformat()),
            strategy=payload.get("strategy", "unknown"),
            signal_source=payload.get("signal_source", "unknown"),
        )

    # ==========================================================================
    # NARRATIVE GENERATION
    # ==========================================================================
    def _generate_trade_narrative(self, entry: TradeEntry) -> str:
        """Generate LLM narrative for a trade."""
        outcome = "winner" if entry.pnl > 0 else "loser" if entry.pnl < 0 else "breakeven"

        prompt = (
            f"Trade journal entry:\n"
            f"- ID: {entry.trade_id}\n"
            f"- Strategy: {entry.strategy}\n"
            f"- Direction: {entry.direction}\n"
            f"- P&L: ${entry.pnl:.2f} ({entry.pnl_pct:+.1f}%)\n"
            f"- Outcome: {outcome}\n"
            f"- Regime at entry: {entry.regime_at_entry}\n"
            f"- Sentiment at entry: {entry.sentiment_at_entry:+.2f}\n"
            f"- Slippage: {entry.slippage_bps:.1f} bps\n"
            f"- Contracts: {entry.contracts}\n\n"
            f"Write a 3-sentence trade analysis:\n"
            f"1. What happened and why\n"
            f"2. Was the entry/exit timing good?\n"
            f"3. Key takeaway for future similar trades"
        )

        return self.llm_query(
            prompt=prompt,
            role=LLMRole.PRIMARY,
            system_prompt=(
                "You are a senior trading coach reviewing a SPY options trade. "
                "Be constructive, specific, and focused on learnable insights."
            ),
        ) or f"Trade {entry.trade_id}: {outcome}, P&L ${entry.pnl:.2f}"

    # ==========================================================================
    # DAILY SUMMARY
    # ==========================================================================
    def _generate_daily_summary(self) -> None:
        """Generate end-of-day performance summary."""
        today = datetime.now().strftime("%Y-%m-%d")
        today_trades = [
            t for t in self._trade_entries
            if t.entry_time.startswith(today)
        ]

        if not today_trades:
            return

        # Calculate metrics
        wins = [t for t in today_trades if t.pnl > 0]
        losses = [t for t in today_trades if t.pnl < 0]
        total_pnl = sum(t.pnl for t in today_trades)

        perf = DailyPerformance(
            date=today,
            total_pnl=total_pnl,
            trade_count=len(today_trades),
            win_count=len(wins),
            loss_count=len(losses),
            win_rate=len(wins) / max(len(today_trades), 1),
            avg_win=sum(t.pnl for t in wins) / max(len(wins), 1),
            avg_loss=sum(t.pnl for t in losses) / max(len(losses), 1),
            best_trade=max(t.pnl for t in today_trades) if today_trades else 0,
            worst_trade=min(t.pnl for t in today_trades) if today_trades else 0,
        )

        # Profit factor
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        perf.profit_factor = gross_profit / max(gross_loss, 0.01)

        # By strategy
        for t in today_trades:
            perf.by_strategy[t.strategy] = (
                perf.by_strategy.get(t.strategy, 0.0) + t.pnl
            )

        # Generate narrative
        prompt = (
            f"Daily trading performance review ({today}):\n"
            f"- Total P&L: ${total_pnl:+.2f}\n"
            f"- Trades: {perf.trade_count} ({perf.win_count}W / {perf.loss_count}L)\n"
            f"- Win rate: {perf.win_rate:.0%}\n"
            f"- Profit factor: {perf.profit_factor:.2f}\n"
            f"- Best trade: ${perf.best_trade:+.2f}\n"
            f"- Worst trade: ${perf.worst_trade:+.2f}\n"
            f"- By strategy: {perf.by_strategy}\n"
            f"- Cumulative P&L: ${self._cumulative_pnl:+.2f}\n\n"
            f"Write a 5-sentence daily review:\n"
            f"1. Overall assessment\n"
            f"2. What worked best\n"
            f"3. What needs improvement\n"
            f"4. Strategy-specific observation\n"
            f"5. Actionable lesson for tomorrow"
        )

        perf.narrative = self.llm_query(
            prompt=prompt,
            role=LLMRole.PRIMARY,
            system_prompt=(
                "You are a professional trading performance analyst. Write a daily "
                "review that is constructive, data-driven, and actionable."
            ),
        ) or f"Daily P&L: ${total_pnl:+.2f}, Win rate: {perf.win_rate:.0%}"

        self._daily_summaries.append(perf)

        # Publish
        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="report",
            topic="meta.performance",
            payload={
                "type": "daily_summary",
                "date": today,
                "total_pnl": total_pnl,
                "trade_count": perf.trade_count,
                "win_rate": perf.win_rate,
                "profit_factor": perf.profit_factor,
                "by_strategy": perf.by_strategy,
                "narrative": perf.narrative,
            },
            confidence=0.9,
            reasoning=perf.narrative,
            priority="NORMAL",
            ttl_seconds=86400,
        ))

        # Extract lessons
        self._extract_daily_lessons(today_trades, perf)

    # ==========================================================================
    # WEEKLY REVIEW
    # ==========================================================================
    def _generate_weekly_review(self) -> None:
        """Weekly performance review with pattern identification."""
        week_summaries = self._daily_summaries[-5:]  # Last 5 trading days
        if not week_summaries:
            return

        total_pnl = sum(d.total_pnl for d in week_summaries)
        total_trades = sum(d.trade_count for d in week_summaries)
        avg_win_rate = (
            sum(d.win_rate for d in week_summaries) / len(week_summaries)
        )

        daily_breakdown = "\n".join(
            f"  {d.date}: ${d.total_pnl:+.2f} ({d.trade_count} trades, {d.win_rate:.0%} WR)"
            for d in week_summaries
        )

        prompt = (
            f"Weekly trading performance review:\n"
            f"- Week P&L: ${total_pnl:+.2f}\n"
            f"- Total trades: {total_trades}\n"
            f"- Average win rate: {avg_win_rate:.0%}\n"
            f"- Daily breakdown:\n{daily_breakdown}\n"
            f"- Cumulative P&L: ${self._cumulative_pnl:+.2f}\n"
            f"- Strategy P&L: {dict(self._strategy_pnl)}\n"
            f"- Regime P&L: {dict(self._regime_pnl)}\n\n"
            f"Write a comprehensive weekly review (6-7 sentences):\n"
            f"1. Overall week assessment\n"
            f"2. Best performing strategy and why\n"
            f"3. Worst performing strategy and why\n"
            f"4. Regime analysis — which regimes were profitable?\n"
            f"5. Pattern identified this week\n"
            f"6. Top 3 improvements for next week"
        )

        review = self.llm_query(
            prompt=prompt,
            role=LLMRole.PRIMARY,
            system_prompt=(
                "You are a hedge fund performance analyst conducting a weekly "
                "portfolio review. Be thorough, data-driven, and prescriptive."
            ),
        ) or "Weekly review unavailable."

        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="report",
            topic="meta.performance",
            payload={
                "type": "weekly_review",
                "week_pnl": total_pnl,
                "total_trades": total_trades,
                "avg_win_rate": avg_win_rate,
                "strategy_pnl": dict(self._strategy_pnl),
                "narrative": review,
            },
            confidence=0.85,
            reasoning=review,
            priority="NORMAL",
            ttl_seconds=604800,  # 7 days
        ))

    # ==========================================================================
    # LESSON EXTRACTION
    # ==========================================================================
    def _extract_daily_lessons(
        self, trades: list[TradeEntry], perf: DailyPerformance
    ) -> None:
        """Extract actionable lessons from today's trades."""
        trade_summaries = "\n".join(
            f"- {t.strategy} {t.direction}: ${t.pnl:+.2f} "
            f"(regime: {t.regime_at_entry}, signal: {t.signal_strength:.2f})"
            for t in trades[:10]
        )

        prompt = (
            f"Extract learning from today's trades:\n"
            f"{trade_summaries}\n\n"
            f"Overall: ${perf.total_pnl:+.2f}, WR: {perf.win_rate:.0%}\n\n"
            f"Identify the TOP 3 actionable lessons. For each:\n"
            f"1. The observation (what happened)\n"
            f"2. The insight (why it matters)\n"
            f"3. The rule (concrete trading rule to follow)"
        )

        lessons = self.llm_query(
            prompt=prompt,
            role=LLMRole.PRIMARY,
            system_prompt="You are a trading psychologist extracting behavioral lessons.",
        ) or ""

        if lessons:
            self.publish(AgentOutput(
                agent_id=self.AGENT_ID,
                output_type="insight",
                topic="meta.lessons",
                payload={
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "lessons": lessons,
                },
                confidence=0.7,
                reasoning=lessons,
                priority="LOW",
                ttl_seconds=604800,
            ))

    # ==========================================================================
    # MESSAGE HANDLER
    # ==========================================================================
    def _on_message(self, topic: str, message: dict[str, Any]) -> None:
        """Handle incoming messages."""
        if topic == "execution.filled":
            self._pending_fills.append(message)
        elif topic == "market.regime":
            self._current_regime = message.get("payload", {}).get(
                "regime", self._current_regime
            )
        elif topic == "market.sentiment":
            self._current_sentiment = message.get("payload", {}).get(
                "overall_score", self._current_sentiment
            )

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================
    def get_state_snapshot(self) -> dict[str, Any]:
        return {
            "tick_count": self._tick_count,
            "cumulative_pnl": self._cumulative_pnl,
            "strategy_pnl": dict(self._strategy_pnl),
            "regime_pnl": dict(self._regime_pnl),
            "trade_count": len(self._trade_entries),
            "daily_summaries_count": len(self._daily_summaries),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._tick_count = state.get("tick_count", 0)
        self._cumulative_pnl = state.get("cumulative_pnl", 0.0)
        self._strategy_pnl = defaultdict(float, state.get("strategy_pnl", {}))
        self._regime_pnl = defaultdict(float, state.get("regime_pnl", {}))


# ==============================================================================
# FACTORY
# ==============================================================================
def create_trade_journal_agent(**kwargs: Any) -> SpyderY07_TradeJournalAgent:
    """Factory function for creating the TradeJournal agent."""
    return SpyderY07_TradeJournalAgent(**kwargs)
