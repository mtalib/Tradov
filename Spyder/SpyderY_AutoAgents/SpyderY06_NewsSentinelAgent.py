#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderY06_NewsSentinelAgent.py
Group: Y (AutoAgents)
Purpose: 24/7 news and sentiment monitoring with LLM-powered analysis

Author: Mohamed Talib
Date Created: 2026-02-25
Last Updated: 2026-02-25 Time: 12:00:00

Description:
    Runs 24/7. Monitors news feeds, economic calendars, earnings announcements,
    and social sentiment. Uses the FINANCE LLM to assess impact on SPY and
    options pricing.

    Wraps SpyderX11_SentimentAnalysisAgent with autonomous scheduling and
    enhanced LLM-powered news interpretation.

    Key responsibilities:
    - Real-time news monitoring and categorization
    - Sentiment scoring (market-wide and SPY-specific)
    - Economic event tracking (FOMC, CPI, NFP, etc.)
    - Earnings season monitoring (SPY constituent impact)
    - Breaking news alerts with options impact assessment
    - Historical sentiment context for regime analysis

License: All dependencies are MIT/BSD/Apache — AGPL-free.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
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
    from Spyder.SpyderX_Agents.SpyderX11_SentimentAnalysisAgent import (
        SpyderX11_SentimentAnalysisAgent,
    )
    X11_AVAILABLE = True
except ImportError:
    X11_AVAILABLE = False


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class NewsItem:
    """A news item with sentiment analysis."""
    headline: str = ""
    source: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    category: str = ""        # macro | earnings | fed | geopolitical | sector
    sentiment_score: float = 0.0   # -1.0 (bearish) to 1.0 (bullish)
    spy_impact: str = "none"       # none | low | medium | high | critical
    options_implication: str = ""   # LLM-generated
    processed: bool = False


@dataclass
class EconomicEvent:
    """An upcoming economic event."""
    name: str = ""
    date: str = ""
    time: str = ""
    importance: str = ""    # low | medium | high
    consensus: str = ""
    previous: str = ""
    actual: str = ""
    spy_impact_estimate: str = ""


@dataclass
class SentimentState:
    """Aggregated sentiment state."""
    overall_score: float = 0.0      # -1 to 1
    news_score: float = 0.0
    social_score: float = 0.0
    fear_greed_index: float = 50.0  # 0-100
    trend: str = "neutral"          # improving | deteriorating | neutral
    dominant_theme: str = ""
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


# ==============================================================================
# NEWS SENTINEL AGENT
# ==============================================================================
class SpyderY06_NewsSentinelAgent(BaseAutoAgent):
    """24/7 news and sentiment monitoring agent.

    Continuously monitors news, economic events, and sentiment. Uses the
    FINANCE LLM to interpret news impact on SPY options.

    Subscribes to:
        market.data          — Market data for correlation with news
        market.regime        — Regime for news context

    Publishes to:
        market.news          — Processed news items
        market.sentiment     — Aggregated sentiment state
        signals.news_driven  — Trading signals from news events
        market.economic_cal  — Upcoming economic events
    """

    AGENT_ID = "Y06_news_sentinel"
    AGENT_NAME = "NewsSentinel Agent"
    AGENT_VERSION = "1.0.0"
    DESCRIPTION = "24/7 news monitoring with LLM-powered sentiment analysis"

    ACTIVE_SESSIONS = {
        MarketSession.OVERNIGHT,
        MarketSession.PRE_MARKET,
        MarketSession.MARKET_OPEN,
        MarketSession.MARKET_HOURS,
        MarketSession.POWER_HOUR,
        MarketSession.POST_MARKET,
    }

    TICK_INTERVALS = {
        MarketSession.OVERNIGHT: 600,     # 10 min — watch for overnight news
        MarketSession.PRE_MARKET: 120,    # 2 min — pre-market news critical
        MarketSession.MARKET_OPEN: 60,    # 1 min — news during open
        MarketSession.MARKET_HOURS: 180,  # 3 min — standard
        MarketSession.POWER_HOUR: 120,    # 2 min — late-day news
        MarketSession.POST_MARKET: 300,   # 5 min — after-hours news
    }

    TICK_INTERVAL = 180.0

    # Major economic events that require special attention
    HIGH_IMPACT_EVENTS = {
        "FOMC", "CPI", "NFP", "PPI", "GDP", "PCE",
        "Retail Sales", "ISM Manufacturing", "Jobless Claims",
    }

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # State
        self._news_queue: deque = deque(maxlen=200)
        self._processed_news: deque = deque(maxlen=500)
        self._sentiment_state = SentimentState()
        self._economic_calendar: list[EconomicEvent] = []
        self._current_regime: str = "unknown"
        self._tick_count: int = 0
        self._daily_news_count: int = 0
        self._alerts_sent_today: int = 0

        # Delegate
        self._x11_agent: Any | None = None
        if X11_AVAILABLE:
            try:
                self._x11_agent = SpyderX11_SentimentAnalysisAgent()
            except Exception as e:
                logging.getLogger(__name__).warning("Failed to initialize X11 SentimentAnalysisAgent: %s", e)  # noqa: E501

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def on_start(self) -> None:
        """Subscribe to relevant topics."""
        self.subscribe("market.data")
        self.subscribe("market.regime")

    def on_wake(self, session: MarketSession) -> None:
        """Session preparation."""
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 180.0)

        if session == MarketSession.PRE_MARKET:
            self._daily_news_count = 0
            self._alerts_sent_today = 0
            self._generate_pre_market_briefing()

        super().on_wake(session)

    # ==========================================================================
    # MAIN TICK
    # ==========================================================================
    def tick(self, session: MarketSession) -> None:
        """Main news monitoring loop."""
        self._tick_count += 1
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 180.0)

        # 1. Fetch new news (from X11 delegate or simulated)
        self._fetch_news()

        # 2. Process pending news through LLM
        self._process_news_queue(session)

        # 3. Update aggregated sentiment
        self._update_sentiment_state()

        # 4. Check for economic events
        if self._tick_count % 10 == 0:
            self._check_economic_calendar()

        # 5. Publish sentiment state
        self._publish_sentiment()

    # ==========================================================================
    # NEWS FETCHING
    # ==========================================================================
    def _fetch_news(self) -> None:
        """Fetch latest news from available sources."""
        if self._x11_agent:
            try:
                # v27 SPEC-15: AsyncBridge avoids RuntimeError under nested loop.
                from Spyder.SpyderU_Utilities.SpyderU50_AsyncBridge import run_coro_in_thread
                news = run_coro_in_thread(
                    self._x11_agent.get_latest_news(symbol="SPY")
                )

                if news:
                    for item in news if isinstance(news, list) else [news]:
                        self._news_queue.append(NewsItem(
                            headline=getattr(item, "headline", str(item)),
                            source=getattr(item, "source", "unknown"),
                            category=getattr(item, "category", "general"),
                        ))
            except Exception as e:
                logging.getLogger(__name__).warning("News fetch failed: %s", e)

    # ==========================================================================
    # NEWS PROCESSING
    # ==========================================================================
    def _process_news_queue(self, session: MarketSession) -> None:
        """Process pending news items through LLM analysis."""
        items_to_process = []
        while self._news_queue and len(items_to_process) < 3:
            item = self._news_queue.popleft()
            if not item.processed:
                items_to_process.append(item)

        if not items_to_process:
            return

        for item in items_to_process:
            self._analyze_news_item(item, session)
            item.processed = True
            self._processed_news.append(item)
            self._daily_news_count += 1

            # Publish high-impact news
            if item.spy_impact in ("high", "critical"):
                self._publish_news_alert(item)

            # Generate trading signal for critical news
            if item.spy_impact == "critical" and abs(item.sentiment_score) >= 0.6:
                self._generate_news_signal(item)

    def _analyze_news_item(
        self, item: NewsItem, session: MarketSession
    ) -> None:
        """Analyze a single news item using the LLM."""
        prompt = (
            f"News analysis for SPY options trading system:\n"
            f"Headline: \"{item.headline}\"\n"
            f"Source: {item.source}\n"
            f"Category: {item.category}\n"
            f"Current regime: {self._current_regime}\n"
            f"Session: {session.value}\n\n"
            f"Respond in JSON format:\n"
            f"{{\n"
            f"  \"sentiment_score\": <float -1.0 to 1.0>,\n"
            f"  \"spy_impact\": \"<none|low|medium|high|critical>\",\n"
            f"  \"category\": \"<macro|earnings|fed|geopolitical|sector|technical>\",\n"
            f"  \"options_implication\": \"<1-2 sentence implication for SPY options>\"\n"
            f"}}"
        )

        response = self.llm_query_json(
            prompt=prompt,
            role=LLMRole.FINANCE,
            system_prompt=(
                "You are a financial news analyst specializing in SPY and S&P 500 "
                "options. Analyze news for its impact on SPY price and options "
                "volatility. Be precise with sentiment scores."
            ),
        ) or {}

        if response:
            item.sentiment_score = float(response.get("sentiment_score", 0.0))
            item.spy_impact = response.get("spy_impact", "none")
            item.category = response.get("category", item.category)
            item.options_implication = response.get("options_implication", "")

    # ==========================================================================
    # SENTIMENT AGGREGATION
    # ==========================================================================
    def _update_sentiment_state(self) -> None:
        """Update aggregated sentiment from recent news."""
        recent_news = [
            n for n in self._processed_news
            if n.timestamp > datetime.now(UTC) - timedelta(hours=4)
        ]

        if not recent_news:
            return

        # Weighted average — more recent news has higher weight
        total_weight = 0.0
        weighted_score = 0.0
        for i, item in enumerate(recent_news):
            weight = 1.0 + (i / len(recent_news))  # Recent items weighted higher
            if item.spy_impact in ("high", "critical"):
                weight *= 2.0  # High-impact news weighted 2x
            weighted_score += item.sentiment_score * weight
            total_weight += weight

        if total_weight > 0:
            self._sentiment_state.news_score = weighted_score / total_weight

        # Overall score (could blend with social sentiment)
        self._sentiment_state.overall_score = self._sentiment_state.news_score

        # Determine trend
        older_news = [
            n for n in self._processed_news
            if n.timestamp > datetime.now(UTC) - timedelta(hours=12)
            and n.timestamp < datetime.now(UTC) - timedelta(hours=4)
        ]
        if older_news:
            older_score = sum(n.sentiment_score for n in older_news) / len(older_news)
            if self._sentiment_state.news_score > older_score + 0.1:
                self._sentiment_state.trend = "improving"
            elif self._sentiment_state.news_score < older_score - 0.1:
                self._sentiment_state.trend = "deteriorating"
            else:
                self._sentiment_state.trend = "neutral"

        # Dominant theme
        categories = [n.category for n in recent_news if n.category]
        if categories:
            from collections import Counter
            self._sentiment_state.dominant_theme = Counter(categories).most_common(1)[0][0]

        self._sentiment_state.last_updated = datetime.now(UTC)

    # ==========================================================================
    # ECONOMIC CALENDAR
    # ==========================================================================
    def _check_economic_calendar(self) -> None:
        """Check for upcoming high-impact economic events."""
        # In production, this would fetch from an economic calendar API
        # For now, publish any tracked events
        upcoming = [
            e for e in self._economic_calendar
            if e.date >= datetime.now(UTC).strftime("%Y-%m-%d")
        ]

        for event in upcoming:
            if event.name in self.HIGH_IMPACT_EVENTS:
                self.publish(AgentOutput(
                    agent_id=self.AGENT_ID,
                    output_type="alert",
                    topic="market.economic_cal",
                    payload={
                        "event": event.name,
                        "date": event.date,
                        "time": event.time,
                        "importance": event.importance,
                        "consensus": event.consensus,
                    },
                    confidence=0.9,
                    reasoning=f"Upcoming: {event.name} on {event.date}",
                    priority="HIGH",
                    ttl_seconds=86400,
                ))

    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def _generate_news_signal(self, item: NewsItem) -> None:
        """Generate a trading signal from critical news."""
        direction = "bullish" if item.sentiment_score > 0 else "bearish"
        strength = min(abs(item.sentiment_score), 1.0)

        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="signal",
            topic="signals.news_driven",
            payload={
                "direction": direction,
                "strength": strength,
                "source": f"news:{item.source}",
                "type": "news_driven",
                "headline": item.headline,
                "category": item.category,
                "id": f"news_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
            },
            confidence=strength * 0.8,  # Discount news signals slightly
            reasoning=item.options_implication,
            priority="HIGH",
            ttl_seconds=1800,  # 30 min TTL for news signals
        ))

    # ==========================================================================
    # PRE-MARKET BRIEFING
    # ==========================================================================
    def _generate_pre_market_briefing(self) -> None:
        """Generate overnight news summary for pre-market."""
        overnight_news = [
            n for n in self._processed_news
            if n.timestamp > datetime.now(UTC) - timedelta(hours=14)
        ]

        if not overnight_news:
            return

        headlines = "\n".join(
            f"- [{n.category}] {n.headline} (sentiment: {n.sentiment_score:+.2f})"
            for n in overnight_news[-10:]  # Last 10 items
        )

        prompt = (
            f"Pre-market news briefing:\n"
            f"Overnight news ({len(overnight_news)} items, showing latest 10):\n"
            f"{headlines}\n\n"
            f"Overall overnight sentiment: {self._sentiment_state.overall_score:+.2f}\n"
            f"Trend: {self._sentiment_state.trend}\n\n"
            f"Provide a 4-sentence pre-market briefing covering:\n"
            f"1. Key overnight developments\n"
            f"2. Sentiment bias for the open\n"
            f"3. Expected vol impact\n"
            f"4. Key risks for today"
        )

        briefing = self.llm_query(
            prompt=prompt,
            role=LLMRole.FINANCE,
            system_prompt=(
                "You are a senior market analyst writing the pre-market news briefing "
                "for an automated SPY options trading system."
            ),
        ) or "Pre-market briefing unavailable."

        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="report",
            topic="market.news",
            payload={
                "type": "pre_market_briefing",
                "briefing": briefing,
                "overnight_count": len(overnight_news),
                "sentiment": self._sentiment_state.overall_score,
            },
            confidence=0.75,
            reasoning=briefing,
            priority="NORMAL",
            ttl_seconds=43200,
        ))

    # ==========================================================================
    # PUBLISHING
    # ==========================================================================
    def _publish_news_alert(self, item: NewsItem) -> None:
        """Publish a high-impact news alert."""
        self._alerts_sent_today += 1
        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="alert",
            topic="market.news",
            payload={
                "headline": item.headline,
                "source": item.source,
                "category": item.category,
                "sentiment_score": item.sentiment_score,
                "spy_impact": item.spy_impact,
                "options_implication": item.options_implication,
            },
            confidence=abs(item.sentiment_score),
            reasoning=item.options_implication,
            priority="HIGH",
        ))

    def _publish_sentiment(self) -> None:
        """Publish aggregated sentiment state."""
        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="metric",
            topic="market.sentiment",
            payload={
                "overall_score": self._sentiment_state.overall_score,
                "news_score": self._sentiment_state.news_score,
                "trend": self._sentiment_state.trend,
                "dominant_theme": self._sentiment_state.dominant_theme,
                "news_count_today": self._daily_news_count,
            },
            confidence=0.7,
            reasoning=(
                f"Sentiment: {self._sentiment_state.overall_score:+.2f} "
                f"({self._sentiment_state.trend})"
            ),
            priority="LOW",
        ))

    # ==========================================================================
    # MESSAGE HANDLER
    # ==========================================================================
    def _on_message(self, topic: str, message: dict[str, Any]) -> None:
        """Handle incoming bus messages."""
        if topic == "market.regime":
            self._current_regime = message.get("payload", {}).get(
                "regime", self._current_regime
            )

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================
    def get_state_snapshot(self) -> dict[str, Any]:
        return {
            "tick_count": self._tick_count,
            "daily_news_count": self._daily_news_count,
            "alerts_sent_today": self._alerts_sent_today,
            "sentiment": {
                "overall": self._sentiment_state.overall_score,
                "trend": self._sentiment_state.trend,
                "dominant_theme": self._sentiment_state.dominant_theme,
            },
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._tick_count = state.get("tick_count", 0)
        self._daily_news_count = state.get("daily_news_count", 0)
        self._alerts_sent_today = state.get("alerts_sent_today", 0)
        sentiment = state.get("sentiment", {})
        self._sentiment_state.overall_score = sentiment.get("overall", 0.0)
        self._sentiment_state.trend = sentiment.get("trend", "neutral")
        self._sentiment_state.dominant_theme = sentiment.get("dominant_theme", "")


# ==============================================================================
# FACTORY
# ==============================================================================
def create_news_sentinel_agent(**kwargs: Any) -> SpyderY06_NewsSentinelAgent:
    """Factory function for creating the NewsSentinel agent."""
    return SpyderY06_NewsSentinelAgent(**kwargs)
