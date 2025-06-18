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
Last Updated: 2025-01-27 Time: 19:45
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderX01_GreeksAgent import SpyderX01_GreeksAgent, create_greeks_agent
from .SpyderX02_FlowAgent import SpyderX02_FlowAgent, create_flow_agent

# Future imports will be added as agents are developed:
from .SpyderX03_StrategyAgent import SpyderX03_StrategyAgent, create_strategy_agent
# from .SpyderX04_RiskAgent import SpyderX04_RiskAgent, create_risk_agent
# from .SpyderX05_ExecutionAgent import SpyderX05_ExecutionAgent, create_execution_agent
# from .SpyderX06_PerformanceAgent import SpyderX06_PerformanceAgent, create_performance_agent


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
    
    # Future agents
    # "SpyderX03_StrategyAgent",
    # "create_strategy_agent",
    # "SpyderX04_RiskAgent",
    # "create_risk_agent",
    # "SpyderX05_ExecutionAgent",
    # "create_execution_agent",
    # "SpyderX06_PerformanceAgent",
    # "create_performance_agent",
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
        "capabilities": ["greeks_calculation", "risk_assessment", "position_analysis"]
    },
    "flow": {
        "class": SpyderX02_FlowAgent,
        "factory": create_flow_agent,
        "description": "Options flow analysis and smart money detection",
        "capabilities": ["flow_analysis", "sweep_detection", "institutional_tracking"]
    },
    # Future agents will be added here
}

# ==============================================================================
# PACKAGE INITIALIZATION
# ==============================================================================
import logging

# Set up package logger
logger = logging.getLogger(__name__)
logger.info(f"{__package_name__} package initialized (v{__version__})")

# Log available agents
logger.info(f"Available AI agents: {list(AGENT_REGISTRY.keys())}")
