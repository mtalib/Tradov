#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Package: SpyderX_Agents
Purpose: AI Agent Modules

This package contains AI-enhanced agents that augment or replace traditional
modules with intelligent, adaptive functionality.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-06-19 Time: 15:00
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
import logging

from .SpyderX01_GreeksAgent import SpyderX01_GreeksAgent, create_greeks_agent
from .SpyderX02_FlowAgent import SpyderX02_FlowAgent, create_flow_agent
from .SpyderX03_StrategyDirectorAgent import (SpyderX03_StrategyDirectorAgent,
                                            create_strategy_director_agent)
from .SpyderX04_RiskGuardianAgent import (SpyderX04_RiskGuardianAgent,
                                        create_risk_guardian_agent)
from .SpyderX05_MLResearchAgent import (SpyderX05_MLResearchAgent,
                                        create_ml_research_agent)
from .SpyderX06_BacktestingAgent import (SpyderX06_BacktestingAgent,
                                        create_backtesting_agent)
from .SpyderX07_ExecutionStrategyAgent import (
    SpyderX07_ExecutionStrategyAgent, create_execution_strategy_agent)
from .SpyderX08_PerformanceAnalyticsAgent import (
    SpyderX08_PerformanceAnalyticsAgent, create_performance_analytics_agent)
from .SpyderX09_AlertManagerAgent import (SpyderX09_AlertManagerAgent,
                                        create_alert_manager_agent)
from .SpyderX10_QuantModelsAgent import (SpyderX10_QuantModelsAgent,
                                        create_quant_models_agent)
from .SpyderX11_SentimentAnalysisAgent import (
    SpyderX11_SentimentAnalysisAgent, create_sentiment_analysis_agent)
from .SpyderX12_SystemHealthAgent import (SpyderX12_SystemHealthAgent,
                                        create_system_health_agent)
from .SpyderX13_MarketAnalysisAgent import (SpyderX13_MarketAnalysisAgent,
                                            create_market_analysis_agent)

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Greeks Agent
    "SpyderX01_GreeksAgent",
    "create_greeks_agent",
    # Flow Agent
    "SpyderX02_FlowAgent",
    "create_flow_agent",
    # Strategy Director Agent
    "SpyderX03_StrategyDirectorAgent",
    "create_strategy_director_agent",
    # Risk Guardian Agent
    "SpyderX04_RiskGuardianAgent",
    "create_risk_guardian_agent",
    # ML Research Agent
    "SpyderX05_MLResearchAgent",
    "create_ml_research_agent",
    # Backtesting Agent
    "SpyderX06_BacktestingAgent",
    "create_backtesting_agent",
    # Execution Strategy Agent
    "SpyderX07_ExecutionStrategyAgent",
    "create_execution_strategy_agent",
    # Performance Analytics Agent
    "SpyderX08_PerformanceAnalyticsAgent",
    "create_performance_analytics_agent",
    # Alert Manager Agent
    "SpyderX09_AlertManagerAgent",
    "create_alert_manager_agent",
    # Quant Models Agent
    "SpyderX10_QuantModelsAgent",
    "create_quant_models_agent",
    # Sentiment Analysis Agent
    "SpyderX11_SentimentAnalysisAgent",
    "create_sentiment_analysis_agent",
    # System Health Agent
    "SpyderX12_SystemHealthAgent",
    "create_system_health_agent",
    # Market Analysis Agent
    "SpyderX13_MarketAnalysisAgent",
    "create_market_analysis_agent",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderX_Agents"
__description__ = "AI-Enhanced Trading Agents"
__version__ = "1.0.0"

# ==============================================================================
# AGENT REGISTRY
# ==============================================================================
# Registry of available agents and their capabilities
AGENT_REGISTRY = {
    "greeks": {
        "class": SpyderX01_GreeksAgent,
        "factory": create_greeks_agent,
        "description": "AI-enhanced Greeks analysis and risk assessment",
        "capabilities": ["greeks_calculation", "risk_assessment", "position_analysis"],
    },
    "flow": {
        "class": SpyderX02_FlowAgent,
        "factory": create_flow_agent,
        "description": "Options flow analysis and smart money detection",
        "capabilities": ["flow_analysis", "sweep_detection", "institutional_tracking"],
    },
    "strategy_director": {
        "class": SpyderX03_StrategyDirectorAgent,
        "factory": create_strategy_director_agent,
        "description": "AI-enhanced strategy selection and management",
        "capabilities": [
            "strategy_selection",
            "parameter_optimization",
            "multi_strategy_management",
        ],
    },
    "risk_guardian": {
        "class": SpyderX04_RiskGuardianAgent,
        "factory": create_risk_guardian_agent,
        "description": "AI-enhanced risk management and control",
        "capabilities": ["risk_monitoring", "position_sizing", "circuit_breaker"],
    },
    "ml_research": {
        "class": SpyderX05_MLResearchAgent,
        "factory": create_ml_research_agent,
        "description": "AutoML and dynamic model management",
        "capabilities": ["automl", "feature_engineering", "model_selection", "continuous_learning"],
    },
    "backtesting": {
        "class": SpyderX06_BacktestingAgent,
        "factory": create_backtesting_agent,
        "description": "AI-enhanced backtesting and strategy validation",
        "capabilities": ["hypothesis_generation", "parameter_optimization", "performance_analysis"],
    },
    "execution": {
        "class": SpyderX07_ExecutionStrategyAgent,
        "factory": create_execution_strategy_agent,
        "description": "Smart order routing and execution optimization",
        "capabilities": ["order_routing", "liquidity_prediction", "market_impact_minimization"],
    },
    "performance": {
        "class": SpyderX08_PerformanceAnalyticsAgent,
        "factory": create_performance_analytics_agent,
        "description": "Deep performance insights and reporting",
        "capabilities": ["performance_analysis", "attribution", "natural_language_reports"],
    },
    "alerts": {
        "class": SpyderX09_AlertManagerAgent,
        "factory": create_alert_manager_agent,
        "description": "Intelligent alert filtering and delivery",
        "capabilities": ["alert_prioritization", "channel_routing", "fatigue_reduction"],
    },
    "quant_models": {
        "class": SpyderX10_QuantModelsAgent,
        "factory": create_quant_models_agent,
        "description": "Quantitative models and pricing",
        "capabilities": ["options_pricing", "volatility_forecasting", "model_optimization"],
    },
    "sentiment": {
        "class": SpyderX11_SentimentAnalysisAgent,
        "factory": create_sentiment_analysis_agent,
        "description": "Market sentiment analysis from multiple sources",
        "capabilities": ["news_analysis", "social_media_monitoring", "event_impact_prediction"],
    },
    "system_health": {
        "class": SpyderX12_SystemHealthAgent,
        "factory": create_system_health_agent,
        "description": "System monitoring and optimization",
        "capabilities": ["performance_monitoring", "anomaly_detection", "resource_optimization"],
    },
    "market_analysis": {
        "class": SpyderX13_MarketAnalysisAgent,
        "factory": create_market_analysis_agent,
        "description": "Market pattern recognition and regime detection",
        "capabilities": ["pattern_recognition", "regime_detection", "trend_analysis"],
    },
}

# ==============================================================================
# PACKAGE INITIALIZATION
# ==============================================================================

# Set up package logger
logger = logging.getLogger(__name__)
logger.info(f"{__package_name__} package initialized (v{__version__})")

# Log available agents
logger.info(f"Available AI agents: {list(AGENT_REGISTRY.keys())}")
