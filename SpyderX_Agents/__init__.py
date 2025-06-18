#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderX_Agents
Purpose: AI Agent Modules

This package contains AI-enhanced agents that augment or replace traditional
modules with intelligent, adaptive functionality.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.0
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderX01_StrategyDirectorAgent import StrategyDirectorAgent
from .SpyderX02_MarketAnalysisAgent import MarketAnalysisAgent
from .SpyderX03_GreeksCalculatorAgent import GreeksCalculatorAgent
from .SpyderX04_RiskGuardianAgent import RiskGuardianAgent
from .SpyderX05_MLResearchAgent import MLResearchAgent
from .SpyderX06_BacktestingAgent import BacktestingAgent
from .SpyderX07_ExecutionStrategyAgent import ExecutionStrategyAgent
from .SpyderX08_PerformanceAnalyticsAgent import PerformanceAnalyticsAgent
from .SpyderX09_AlertManagerAgent import AlertManagerAgent
from .SpyderX10_QuantModelsAgent import QuantModelsAgent
from .SpyderX11_SentimentAnalysisAgent import SentimentAnalysisAgent
from .SpyderX12_SystemHealthAgent import SystemHealthAgent

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Strategy management
    "StrategyDirectorAgent",
    
    # Market analysis
    "MarketAnalysisAgent",
    "SentimentAnalysisAgent",
    
    # Options analytics
    "GreeksCalculatorAgent",
    
    # Risk management
    "RiskGuardianAgent",
    
    # Machine learning
    "MLResearchAgent",
    
    # Backtesting
    "BacktestingAgent",
    
    # Execution
    "ExecutionStrategyAgent",
    
    # Performance
    "PerformanceAnalyticsAgent",
    
    # Alerts
    "AlertManagerAgent",
    
    # Quantitative models
    "QuantModelsAgent",
    
    # System health
    "SystemHealthAgent",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderX_Agents"
__description__ = "AI-Enhanced Agent Modules"
__version__ = "1.0.0"