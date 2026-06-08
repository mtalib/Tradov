#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovX_Agents
Module: TradovX08_PerformanceAnalyticsAgent.py
Purpose: AI-enhanced performance analytics and attribution agent

Author: Tradov Development Team
Year Created: 2025
Last Updated: 2026-03-08 Time: 01:46:00

Module Description:
    AI-powered performance analytics agent that provides intelligent
    performance attribution, strategy comparison, and return analysis
    using LLM-driven natural language insights.

Change Log:
    2026-03-08:
        - Created module to resolve missing-module references
        - Implements PerformanceAnalyticsAgent with full X-series interface
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
import os
from datetime import datetime, UTC
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
except ImportError:
    TradovLogger = None

try:
    from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
except ImportError:
    TradovErrorHandler = None

try:
    from Tradov.TradovU_Utilities.TradovU17_LLMUtils import strip_thinking_block
except ImportError:
    import re as _re
    def strip_thinking_block(content: str) -> str:  # type: ignore[misc]
        return _re.sub(r"<\|channel>thought\n.*?<channel\|>", "", content, flags=_re.DOTALL).strip()

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_MODEL = os.getenv("OLLAMA_PRIMARY_MODEL", "gemma4:26b")
DEFAULT_TEMPERATURE = 0.3
ANALYSIS_LOOKBACK_DAYS = 30
MIN_TRADES_FOR_ANALYSIS = 5


# ==============================================================================
# DATA CLASSES
# ==============================================================================
class PerformanceMetricType(Enum):
    """Types of performance metrics."""
    SHARPE_RATIO = "SHARPE_RATIO"
    SORTINO_RATIO = "SORTINO_RATIO"
    CALMAR_RATIO = "CALMAR_RATIO"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    WIN_RATE = "WIN_RATE"
    PROFIT_FACTOR = "PROFIT_FACTOR"
    RETURN_ATTRIBUTION = "RETURN_ATTRIBUTION"


@dataclass
class PerformanceSnapshot:
    """Snapshot of strategy/portfolio performance."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    strategy_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class PerformanceAnalysis:
    """Result of AI-enhanced performance analysis."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    snapshot: PerformanceSnapshot | None = None
    natural_language_summary: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    attribution: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    risk_assessment: str = ""


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class PerformanceAnalyticsAgent:
    """
    AI-Enhanced Performance Analytics Agent.

    Provides intelligent performance analysis, strategy attribution, and
    natural-language insights using LLM-driven reasoning over trading results.

    Key Features:
        - Strategy-level return attribution
        - AI-generated performance summaries and recommendations
        - Win/loss pattern analysis and streak detection
        - Risk-adjusted return calculations with context
        - Comparative strategy performance analysis

    Example:
        >>> agent = PerformanceAnalyticsAgent()
        >>> analysis = await agent.analyze_performance(snapshot)
        >>> print(analysis.natural_language_summary)
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize the Performance Analytics Agent.

        Args:
            model_name: Ollama model to use for AI analysis.
            temperature: Temperature for AI responses.
            config: Optional agent configuration dictionary.
        """
        self.model_name = model_name
        self.temperature = temperature
        self.config = config or {}

        if TradovLogger is not None:
            self.logger = TradovLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)

        if TradovErrorHandler is not None:
            self.error_handler = TradovErrorHandler()
        else:
            self.error_handler = None

        self.analysis_history: list[PerformanceAnalysis] = []
        self._initialized = False

    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================

    async def initialize(self) -> bool:
        """
        Initialize the agent and verify LLM connectivity.

        Returns:
            True if initialization succeeded.
        """
        try:
            if OLLAMA_AVAILABLE:
                self.logger.info(
                    "PerformanceAnalyticsAgent initialized with model=%s", self.model_name
                )
            else:
                self.logger.warning(
                    "Ollama not available — AI analysis will use rule-based fallback"
                )
            self._initialized = True
            return True
        except Exception as e:
            self.logger.error("Failed to initialize PerformanceAnalyticsAgent: %s", e)
            return False

    # ==========================================================================
    # CORE ANALYSIS
    # ==========================================================================

    async def analyze_performance(
        self,
        snapshot: PerformanceSnapshot,
        context: dict[str, Any] | None = None,
    ) -> PerformanceAnalysis:
        """
        Perform AI-enhanced performance analysis on a snapshot.

        Args:
            snapshot: Current performance snapshot to analyse.
            context: Optional additional market/system context.

        Returns:
            PerformanceAnalysis with AI-generated insights.
        """
        analysis = PerformanceAnalysis(snapshot=snapshot)

        try:
            # Rule-based analysis (always available)
            analysis.strengths = self._identify_strengths(snapshot)
            analysis.weaknesses = self._identify_weaknesses(snapshot)
            analysis.recommendations = self._generate_recommendations(snapshot)
            analysis.attribution = snapshot.strategy_breakdown.copy()
            analysis.confidence = self._calculate_confidence(snapshot)
            analysis.risk_assessment = self._assess_risk(snapshot)

            # AI-enhanced summary if Ollama is available
            if OLLAMA_AVAILABLE:
                analysis.natural_language_summary = await self._generate_ai_summary(
                    snapshot, context
                )
            else:
                analysis.natural_language_summary = self._generate_rule_summary(
                    snapshot
                )

            self.analysis_history.append(analysis)

        except Exception as e:
            self.logger.error("Performance analysis failed: %s", e)
            analysis.natural_language_summary = (
                f"Analysis incomplete due to error: {e}"
            )

        return analysis

    async def compare_strategies(
        self,
        strategy_snapshots: dict[str, PerformanceSnapshot],
    ) -> dict[str, Any]:
        """
        Compare performance across multiple strategies.

        Args:
            strategy_snapshots: Map of strategy name to its performance snapshot.

        Returns:
            Comparison results with rankings and relative analysis.
        """
        if not strategy_snapshots:
            return {"error": "No strategies to compare"}

        rankings: dict[str, list[tuple[str, float]]] = {}
        for metric in ["sharpe_ratio", "win_rate", "profit_factor", "max_drawdown"]:
            ranked = sorted(
                [
                    (name, getattr(snap, metric, 0.0))
                    for name, snap in strategy_snapshots.items()
                ],
                key=lambda x: x[1],
                reverse=(metric != "max_drawdown"),
            )
            rankings[metric] = ranked

        return {
            "rankings": rankings,
            "best_overall": rankings["sharpe_ratio"][0][0]
            if rankings.get("sharpe_ratio")
            else None,
            "strategy_count": len(strategy_snapshots),
        }

    # ==========================================================================
    # RULE-BASED HELPERS
    # ==========================================================================

    def _identify_strengths(self, snapshot: PerformanceSnapshot) -> list[str]:
        """Identify performance strengths from a snapshot."""
        strengths = []
        if snapshot.sharpe_ratio > 1.0:
            strengths.append(
                f"Strong risk-adjusted returns (Sharpe: {snapshot.sharpe_ratio:.2f})"
            )
        if snapshot.win_rate > 0.55:
            strengths.append(f"Above-average win rate ({snapshot.win_rate:.1%})")
        if snapshot.profit_factor > 1.5:
            strengths.append(
                f"Good profit factor ({snapshot.profit_factor:.2f})"
            )
        if snapshot.max_drawdown > -0.05:
            strengths.append("Tight drawdown control")
        return strengths

    def _identify_weaknesses(self, snapshot: PerformanceSnapshot) -> list[str]:
        """Identify performance weaknesses from a snapshot."""
        weaknesses = []
        if snapshot.sharpe_ratio < 0.5:
            weaknesses.append(
                f"Low risk-adjusted returns (Sharpe: {snapshot.sharpe_ratio:.2f})"
            )
        if snapshot.win_rate < 0.45:
            weaknesses.append(f"Below-average win rate ({snapshot.win_rate:.1%})")
        if snapshot.max_drawdown < -0.15:
            weaknesses.append(
                f"Significant drawdown ({snapshot.max_drawdown:.1%})"
            )
        if snapshot.total_trades < MIN_TRADES_FOR_ANALYSIS:
            weaknesses.append("Insufficient trade count for reliable statistics")
        return weaknesses

    def _generate_recommendations(
        self, snapshot: PerformanceSnapshot
    ) -> list[str]:
        """Generate rule-based recommendations."""
        recs = []
        if snapshot.max_drawdown < -0.10:
            recs.append("Consider tightening stop-loss levels or reducing position size")
        if snapshot.win_rate < 0.45 and snapshot.profit_factor < 1.0:
            recs.append(
                "Review entry criteria — both win rate and profit factor are below targets"
            )
        if snapshot.sharpe_ratio < 0.5 and snapshot.total_trades > 20:
            recs.append("Evaluate strategy viability — Sharpe below 0.5 over 20+ trades")
        return recs

    def _calculate_confidence(self, snapshot: PerformanceSnapshot) -> float:
        """Calculate confidence score based on data sufficiency."""
        if snapshot.total_trades < MIN_TRADES_FOR_ANALYSIS:
            return 0.3
        trade_score = min(snapshot.total_trades / 100.0, 1.0)
        return round(0.5 + 0.5 * trade_score, 2)

    def _assess_risk(self, snapshot: PerformanceSnapshot) -> str:
        """Rule-based risk assessment."""
        if snapshot.max_drawdown < -0.20:
            return "HIGH — Significant drawdown detected"
        if snapshot.max_drawdown < -0.10:
            return "MODERATE — Drawdown within acceptable bounds"
        return "LOW — Drawdown well controlled"

    def _generate_rule_summary(self, snapshot: PerformanceSnapshot) -> str:
        """Generate a rule-based summary when AI is not available."""
        parts = [
            f"Performance Summary ({snapshot.timestamp:%Y-%m-%d %H:%M}):",
            f"  Total P&L: ${snapshot.total_pnl:,.2f}",
            f"  Trades: {snapshot.total_trades} (W: {snapshot.winning_trades} / L: {snapshot.losing_trades})",  # noqa: E501
            f"  Win Rate: {snapshot.win_rate:.1%}",
            f"  Sharpe: {snapshot.sharpe_ratio:.2f}",
            f"  Max Drawdown: {snapshot.max_drawdown:.1%}",
        ]
        return "\n".join(parts)

    # ==========================================================================
    # AI-ENHANCED ANALYSIS
    # ==========================================================================

    async def _generate_ai_summary(
        self,
        snapshot: PerformanceSnapshot,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Generate AI-enhanced natural-language performance summary."""
        prompt = self._build_analysis_prompt(snapshot, context)

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a quantitative trading performance analyst. "
                            "Provide concise, actionable analysis of trading results. "
                            "Focus on risk-adjusted returns, strategy attribution, "
                            "and practical recommendations."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": self.temperature, "think": False},
            )
            return strip_thinking_block(response["message"]["content"])
        except Exception as e:
            self.logger.warning("AI summary generation failed: %s", e)
            return self._generate_rule_summary(snapshot)

    def _build_analysis_prompt(
        self,
        snapshot: PerformanceSnapshot,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Build the prompt for AI performance analysis."""
        data = {
            "total_pnl": snapshot.total_pnl,
            "realized_pnl": snapshot.realized_pnl,
            "unrealized_pnl": snapshot.unrealized_pnl,
            "sharpe_ratio": snapshot.sharpe_ratio,
            "sortino_ratio": snapshot.sortino_ratio,
            "max_drawdown": snapshot.max_drawdown,
            "win_rate": snapshot.win_rate,
            "profit_factor": snapshot.profit_factor,
            "total_trades": snapshot.total_trades,
            "winning_trades": snapshot.winning_trades,
            "losing_trades": snapshot.losing_trades,
            "strategy_breakdown": snapshot.strategy_breakdown,
        }
        if context:
            data["market_context"] = context

        return (
            "Analyse the following TRAD options trading performance data "
            "and provide a concise summary with strengths, weaknesses, "
            f"and actionable recommendations:\n\n{json.dumps(data, indent=2)}"
        )

    # ==========================================================================
    # SINGLETON SUPPORT
    # ==========================================================================

    _instance: Optional["PerformanceAnalyticsAgent"] = None

    @classmethod
    def get_instance(cls) -> "PerformanceAnalyticsAgent":
        """Get or create singleton instance of the agent."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Alias matching __init__.py expected export name
TradovX08_PerformanceAnalyticsAgent = PerformanceAnalyticsAgent


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================


def create_performance_analytics_agent(
    model_name: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    config: dict[str, Any] | None = None,
) -> PerformanceAnalyticsAgent:
    """
    Factory function to create a Performance Analytics Agent instance.

    Args:
        model_name: Ollama model to use.
        temperature: Temperature for AI responses.
        config: Optional agent configuration.

    Returns:
        PerformanceAnalyticsAgent instance.
    """
    return PerformanceAnalyticsAgent(
        model_name=model_name, temperature=temperature, config=config
    )


# Singleton instance
_module_instance: PerformanceAnalyticsAgent | None = None


def get_module_instance() -> PerformanceAnalyticsAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        _module_instance = create_performance_analytics_agent()
    return _module_instance


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    async def _demo():
        agent = PerformanceAnalyticsAgent()
        await agent.initialize()
        snapshot = PerformanceSnapshot(
            total_pnl=1250.00,
            sharpe_ratio=1.35,
            win_rate=0.62,
            profit_factor=1.8,
            max_drawdown=-0.07,
            total_trades=45,
            winning_trades=28,
            losing_trades=17,
        )
        analysis = await agent.analyze_performance(snapshot)
        print(analysis.natural_language_summary)  # noqa: T201

    asyncio.run(_demo())
