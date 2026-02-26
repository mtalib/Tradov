#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderY_AutoAgents/__init__.py
Group: Y (AutoAgents)
Purpose: Package initialization — registers all autonomous agents

Author: Mohamed Talib
Date Created: 2026-02-25
Last Updated: 2026-02-25 Time: 12:00:00

Description:
    The SpyderY_AutoAgents package contains 9 specialist autonomous agents
    powered by a local LLM (Ollama) that run 24/7 to achieve optimal trading
    results without human intervention.

    Unlike SpyderX_Agents (on-demand, stateless), SpyderY agents are:
      - Persistent (maintain state across restarts)
      - Autonomous (tick-based lifecycle, no human trigger)
      - Market-session-aware (adjust behavior by session)
      - LLM-integrated (each agent uses the appropriate model role)
      - Message-bus-connected (pub/sub via SpyderI06_AgentMessageBus)

    Architecture:
      Y00  BaseAutoAgent      — Abstract base class (not directly instantiated)
      Y01  MarketSenseAgent   — 24/7 market awareness and regime synthesis
      Y02  StrategyPilotAgent — Strategy selection and signal validation
      Y03  RiskSentinelAgent  — Risk monitoring with circuit breaker & veto
      Y04  AlphaLearnerAgent  — ML research, model retraining, feature discovery
      Y05  ExecutionOptimizer — Smart order execution and fill optimization
      Y06  NewsSentinelAgent  — News monitoring and sentiment analysis
      Y07  TradeJournalAgent  — Trade journaling and performance attribution
      Y08  MetaOrchestrator   — High-level agent coordination
      Y09  CodeReviewerAgent  — Off-hours code quality auditing
      Y10  AgentScheduler     — Central scheduler managing all agent lifecycles

License: All dependencies are MIT/BSD/Apache — AGPL-free.
"""

# ==============================================================================
# BASE CLASS & UTILITIES
# ==============================================================================
from .SpyderY00_BaseAutoAgent import (
    BaseAutoAgent,
    AgentOutput,
    AgentHeartbeat,
    AgentState,
    LLMRole,
    MarketSession,
    OllamaConfig,
)

# ==============================================================================
# AGENT IMPORTS
# ==============================================================================
from .SpyderY01_MarketSenseAgent import (
    SpyderY01_MarketSenseAgent,
    create_market_sense_agent,
)
from .SpyderY02_StrategyPilotAgent import (
    SpyderY02_StrategyPilotAgent,
    create_strategy_pilot_agent,
)
from .SpyderY03_RiskSentinelAgent import (
    SpyderY03_RiskSentinelAgent,
    create_risk_sentinel_agent,
)
from .SpyderY04_AlphaLearnerAgent import (
    SpyderY04_AlphaLearnerAgent,
    create_alpha_learner_agent,
)
from .SpyderY05_ExecutionOptimizerAgent import (
    SpyderY05_ExecutionOptimizerAgent,
    create_execution_optimizer_agent,
)
from .SpyderY06_NewsSentinelAgent import (
    SpyderY06_NewsSentinelAgent,
    create_news_sentinel_agent,
)
from .SpyderY07_TradeJournalAgent import (
    SpyderY07_TradeJournalAgent,
    create_trade_journal_agent,
)
from .SpyderY08_MetaOrchestratorAgent import (
    SpyderY08_MetaOrchestratorAgent,
    create_meta_orchestrator_agent,
)
from .SpyderY09_CodeReviewerAgent import (
    SpyderY09_CodeReviewerAgent,
    create_code_reviewer_agent,
)

# ==============================================================================
# SCHEDULER
# ==============================================================================
from .SpyderY10_AgentScheduler import AgentScheduler

# ==============================================================================
# AGENT REGISTRY
# ==============================================================================
AGENT_REGISTRY = {
    "Y01": {
        "class": SpyderY01_MarketSenseAgent,
        "factory": create_market_sense_agent,
        "name": "MarketSense Agent",
        "description": "24/7 market awareness — regime synthesis and narrative generation",
        "sessions": "ALL",
        "priority": 2,
        "capabilities": [
            "regime_detection",
            "market_narrative",
            "level_tracking",
            "daily_brief",
        ],
    },
    "Y02": {
        "class": SpyderY02_StrategyPilotAgent,
        "factory": create_strategy_pilot_agent,
        "name": "StrategyPilot Agent",
        "description": "Strategy selection, signal validation, and parameter tuning",
        "sessions": "MARKET_HOURS",
        "priority": 3,
        "capabilities": [
            "signal_validation",
            "strategy_allocation",
            "parameter_tuning",
            "eod_positioning",
        ],
    },
    "Y03": {
        "class": SpyderY03_RiskSentinelAgent,
        "factory": create_risk_sentinel_agent,
        "name": "RiskSentinel Agent",
        "description": "24/7 risk monitoring with circuit breaker and trade veto",
        "sessions": "ALL",
        "priority": 1,  # HIGHEST priority — risk overrides everything
        "capabilities": [
            "portfolio_risk",
            "circuit_breaker",
            "trade_veto",
            "stress_testing",
            "drawdown_monitoring",
        ],
    },
    "Y04": {
        "class": SpyderY04_AlphaLearnerAgent,
        "factory": create_alpha_learner_agent,
        "name": "AlphaLearner Agent",
        "description": "ML research, model retraining, and feature discovery",
        "sessions": "ALL",
        "priority": 5,
        "capabilities": [
            "ml_prediction",
            "model_retraining",
            "feature_engineering",
            "hyperparameter_optimization",
            "drift_detection",
        ],
    },
    "Y05": {
        "class": SpyderY05_ExecutionOptimizerAgent,
        "factory": create_execution_optimizer_agent,
        "name": "ExecutionOptimizer Agent",
        "description": "Smart order execution with Kelly sizing and fill optimization",
        "sessions": "MARKET_HOURS",
        "priority": 2,
        "capabilities": [
            "kelly_sizing",
            "order_execution",
            "fill_monitoring",
            "slippage_tracking",
        ],
    },
    "Y06": {
        "class": SpyderY06_NewsSentinelAgent,
        "factory": create_news_sentinel_agent,
        "name": "NewsSentinel Agent",
        "description": "24/7 news monitoring with LLM-powered sentiment analysis",
        "sessions": "ALL",
        "priority": 4,
        "capabilities": [
            "news_monitoring",
            "sentiment_scoring",
            "economic_calendar",
            "breaking_news_alerts",
        ],
    },
    "Y07": {
        "class": SpyderY07_TradeJournalAgent,
        "factory": create_trade_journal_agent,
        "name": "TradeJournal Agent",
        "description": "Automated trade journaling with performance attribution",
        "sessions": "POST_MARKET",
        "priority": 6,
        "capabilities": [
            "trade_logging",
            "daily_summary",
            "weekly_review",
            "lesson_extraction",
            "performance_attribution",
        ],
    },
    "Y08": {
        "class": SpyderY08_MetaOrchestratorAgent,
        "factory": create_meta_orchestrator_agent,
        "name": "MetaOrchestrator Agent",
        "description": "High-level coordination of all Y-series agents",
        "sessions": "ALL",
        "priority": 1,  # Same as risk — meta-level control
        "capabilities": [
            "agent_health_monitoring",
            "conflict_resolution",
            "session_coordination",
            "system_synthesis",
        ],
    },
    "Y09": {
        "class": SpyderY09_CodeReviewerAgent,
        "factory": create_code_reviewer_agent,
        "name": "CodeReviewer Agent",
        "description": "Off-hours code quality auditing (read-only)",
        "sessions": "OFF_HOURS",
        "priority": 9,  # Lowest — runs when nothing else needs resources
        "capabilities": [
            "bug_detection",
            "security_review",
            "performance_review",
            "code_quality",
            "dependency_audit",
        ],
    },
}


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================
def create_all_agents(**kwargs):
    """Create instances of all 9 agents with shared configuration.

    Args:
        **kwargs: Shared configuration passed to all agent constructors.
                  Common keys: ollama_config, message_bus, state_dir

    Returns:
        Dict[str, BaseAutoAgent]: Mapping of agent_id to agent instance
    """
    agents = {}
    for reg_id, reg in AGENT_REGISTRY.items():
        factory = reg["factory"]
        agent = factory(**kwargs)
        agents[agent.AGENT_ID] = agent
    return agents


def create_scheduler(**kwargs) -> AgentScheduler:
    """Create an AgentScheduler pre-loaded with all 9 agents.

    Args:
        **kwargs: Configuration passed to AgentScheduler constructor.
                  Common keys: ollama_config, message_bus, state_dir

    Returns:
        AgentScheduler: Ready-to-run scheduler with all agents registered
    """
    scheduler = AgentScheduler(**kwargs)
    for reg_id, reg in AGENT_REGISTRY.items():
        scheduler.register(reg["class"])
    return scheduler


def get_agent_info() -> dict:
    """Get a summary of all registered agents."""
    return {
        reg_id: {
            "name": reg["name"],
            "description": reg["description"],
            "sessions": reg["sessions"],
            "priority": reg["priority"],
            "capabilities": reg["capabilities"],
        }
        for reg_id, reg in AGENT_REGISTRY.items()
    }


# ==============================================================================
# PUBLIC API
# ==============================================================================
__all__ = [
    # Base
    "BaseAutoAgent",
    "AgentOutput",
    "AgentHeartbeat",
    "AgentState",
    "LLMRole",
    "MarketSession",
    "OllamaConfig",
    # Agents
    "SpyderY01_MarketSenseAgent",
    "SpyderY02_StrategyPilotAgent",
    "SpyderY03_RiskSentinelAgent",
    "SpyderY04_AlphaLearnerAgent",
    "SpyderY05_ExecutionOptimizerAgent",
    "SpyderY06_NewsSentinelAgent",
    "SpyderY07_TradeJournalAgent",
    "SpyderY08_MetaOrchestratorAgent",
    "SpyderY09_CodeReviewerAgent",
    # Factories
    "create_market_sense_agent",
    "create_strategy_pilot_agent",
    "create_risk_sentinel_agent",
    "create_alpha_learner_agent",
    "create_execution_optimizer_agent",
    "create_news_sentinel_agent",
    "create_trade_journal_agent",
    "create_meta_orchestrator_agent",
    "create_code_reviewer_agent",
    # Scheduler
    "AgentScheduler",
    # Registry & Helpers
    "AGENT_REGISTRY",
    "create_all_agents",
    "create_scheduler",
    "get_agent_info",
]
