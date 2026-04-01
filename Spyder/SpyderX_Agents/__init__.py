#!/usr/bin/env python3
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

_logger = logging.getLogger(__name__)

# Import each agent with graceful fallback
_import_errors = []

try:
    from .SpyderX01_GreeksAgent import GreeksAgent as SpyderX01_GreeksAgent, create_greeks_agent
except Exception as _e:
    _import_errors.append(f"X01: {_e}")
    SpyderX01_GreeksAgent = None  # type: ignore
    create_greeks_agent = None  # type: ignore

try:
    from .SpyderX02_FlowAgent import SpyderX02_FlowAgent, create_flow_agent
except Exception as _e:
    _import_errors.append(f"X02: {_e}")
    SpyderX02_FlowAgent = None  # type: ignore
    create_flow_agent = None  # type: ignore

try:
    from .SpyderX03_StrategyDirectorAgent import (SpyderX03_StrategyDirectorAgent,
                                                create_strategy_director_agent)
except Exception as _e:
    _import_errors.append(f"X03: {_e}")
    SpyderX03_StrategyDirectorAgent = None  # type: ignore
    create_strategy_director_agent = None  # type: ignore

try:
    from .SpyderX04_RiskGuardianAgent import (SpyderX04_RiskGuardianAgent,
                                            create_risk_guardian_agent)
except Exception as _e:
    _import_errors.append(f"X04: {_e}")
    SpyderX04_RiskGuardianAgent = None  # type: ignore
    create_risk_guardian_agent = None  # type: ignore

try:
    from .SpyderX05_MLResearchAgent import (SpyderX05_MLResearchAgent,
                                            create_ml_research_agent)
except Exception as _e:
    _import_errors.append(f"X05: {_e}")
    SpyderX05_MLResearchAgent = None  # type: ignore
    create_ml_research_agent = None  # type: ignore

try:
    from .SpyderX07_ExecutionStrategyAgent import (
        SpyderX07_ExecutionStrategyAgent, create_execution_strategy_agent)
except Exception as _e:
    _import_errors.append(f"X07: {_e}")
    SpyderX07_ExecutionStrategyAgent = None  # type: ignore
    create_execution_strategy_agent = None  # type: ignore

try:
    from .SpyderX08_PerformanceAnalyticsAgent import (
        SpyderX08_PerformanceAnalyticsAgent, create_performance_analytics_agent)
except Exception as _e:
    _import_errors.append(f"X08: {_e}")
    SpyderX08_PerformanceAnalyticsAgent = None  # type: ignore
    create_performance_analytics_agent = None  # type: ignore

try:
    from .SpyderX09_AlertManagerAgent import (SpyderX09_AlertManagerAgent,
                                            create_alert_manager_agent)
except Exception as _e:
    _import_errors.append(f"X09: {_e}")
    SpyderX09_AlertManagerAgent = None  # type: ignore
    create_alert_manager_agent = None  # type: ignore

try:
    from .SpyderX10_QuantModelsAgent import (SpyderX10_QuantModelsAgent,
                                            create_quant_models_agent)
except Exception as _e:
    _import_errors.append(f"X10: {_e}")
    SpyderX10_QuantModelsAgent = None  # type: ignore
    create_quant_models_agent = None  # type: ignore

try:
    from .SpyderX11_SentimentAnalysisAgent import (
        SpyderX11_SentimentAnalysisAgent, create_sentiment_analysis_agent)
except Exception as _e:
    _import_errors.append(f"X11: {_e}")
    SpyderX11_SentimentAnalysisAgent = None  # type: ignore
    create_sentiment_analysis_agent = None  # type: ignore

try:
    from .SpyderX12_SystemHealthAgent import (SpyderX12_SystemHealthAgent,
                                            create_system_health_agent)
except Exception as _e:
    _import_errors.append(f"X12: {_e}")
    SpyderX12_SystemHealthAgent = None  # type: ignore
    create_system_health_agent = None  # type: ignore

try:
    from .SpyderX13_MarketAnalysisAgent import (SpyderX13_MarketAnalysisAgent,
                                                create_market_analysis_agent)
except Exception as _e:
    _import_errors.append(f"X13: {_e}")
    SpyderX13_MarketAnalysisAgent = None  # type: ignore
    create_market_analysis_agent = None  # type: ignore

if _import_errors:
    for _err in _import_errors:
        _logger.warning(f"Agent import failed: {_err}")

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
AGENT_REGISTRY = {}

if SpyderX01_GreeksAgent is not None:
    AGENT_REGISTRY["greeks"] = {
        "class": SpyderX01_GreeksAgent,
        "factory": create_greeks_agent,
        "description": "AI-enhanced Greeks analysis and risk assessment",
        "capabilities": ["greeks_calculation", "risk_assessment", "position_analysis"],
    }
if SpyderX02_FlowAgent is not None:
    AGENT_REGISTRY["flow"] = {
        "class": SpyderX02_FlowAgent,
        "factory": create_flow_agent,
        "description": "Options flow analysis and smart money detection",
        "capabilities": ["flow_analysis", "sweep_detection", "institutional_tracking"],
    }
if SpyderX03_StrategyDirectorAgent is not None:
    AGENT_REGISTRY["strategy_director"] = {
        "class": SpyderX03_StrategyDirectorAgent,
        "factory": create_strategy_director_agent,
        "description": "AI-enhanced strategy selection and management",
        "capabilities": ["strategy_selection", "parameter_optimization", "multi_strategy_management"],
    }
if SpyderX04_RiskGuardianAgent is not None:
    AGENT_REGISTRY["risk_guardian"] = {
        "class": SpyderX04_RiskGuardianAgent,
        "factory": create_risk_guardian_agent,
        "description": "AI-enhanced risk management and control",
        "capabilities": ["risk_monitoring", "position_sizing", "circuit_breaker"],
    }
if SpyderX05_MLResearchAgent is not None:
    AGENT_REGISTRY["ml_research"] = {
        "class": SpyderX05_MLResearchAgent,
        "factory": create_ml_research_agent,
        "description": "AutoML and dynamic model management",
        "capabilities": ["automl", "feature_engineering", "model_selection", "continuous_learning"],
    }
if SpyderX07_ExecutionStrategyAgent is not None:
    AGENT_REGISTRY["execution"] = {
        "class": SpyderX07_ExecutionStrategyAgent,
        "factory": create_execution_strategy_agent,
        "description": "Smart order routing and execution optimization",
        "capabilities": ["order_routing", "liquidity_prediction", "market_impact_minimization"],
    }
if SpyderX08_PerformanceAnalyticsAgent is not None:
    AGENT_REGISTRY["performance"] = {
        "class": SpyderX08_PerformanceAnalyticsAgent,
        "factory": create_performance_analytics_agent,
        "description": "Deep performance insights and reporting",
        "capabilities": ["performance_analysis", "attribution", "natural_language_reports"],
    }
if SpyderX09_AlertManagerAgent is not None:
    AGENT_REGISTRY["alerts"] = {
        "class": SpyderX09_AlertManagerAgent,
        "factory": create_alert_manager_agent,
        "description": "Intelligent alert filtering and delivery",
        "capabilities": ["alert_prioritization", "channel_routing", "fatigue_reduction"],
    }
if SpyderX10_QuantModelsAgent is not None:
    AGENT_REGISTRY["quant_models"] = {
        "class": SpyderX10_QuantModelsAgent,
        "factory": create_quant_models_agent,
        "description": "Quantitative models and pricing",
        "capabilities": ["options_pricing", "volatility_forecasting", "model_optimization"],
    }
if SpyderX11_SentimentAnalysisAgent is not None:
    AGENT_REGISTRY["sentiment"] = {
        "class": SpyderX11_SentimentAnalysisAgent,
        "factory": create_sentiment_analysis_agent,
        "description": "Market sentiment analysis from multiple sources",
        "capabilities": ["news_analysis", "social_media_monitoring", "event_impact_prediction"],
    }
if SpyderX12_SystemHealthAgent is not None:
    AGENT_REGISTRY["system_health"] = {
        "class": SpyderX12_SystemHealthAgent,
        "factory": create_system_health_agent,
        "description": "System monitoring and optimization",
        "capabilities": ["performance_monitoring", "anomaly_detection", "resource_optimization"],
    }
if SpyderX13_MarketAnalysisAgent is not None:
    AGENT_REGISTRY["market_analysis"] = {
        "class": SpyderX13_MarketAnalysisAgent,
        "factory": create_market_analysis_agent,
        "description": "Market pattern recognition and regime detection",
        "capabilities": ["pattern_recognition", "regime_detection", "trend_analysis"],
    }

# ==============================================================================
# PACKAGE INITIALIZATION
# ==============================================================================

# Set up package logger
logger = logging.getLogger(__name__)
logger.info(f"{__package_name__} package initialized (v{__version__})")

# Log available agents
logger.info(f"Available AI agents: {list(AGENT_REGISTRY.keys())}")
