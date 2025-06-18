#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

SpyderR_Runtime - Runtime Operations Package

This package contains all runtime execution engines:
- Backtesting engine
- Paper trading engine and monitor
- Live trading engine
"""

from .SpyderR01_BacktestEngine import BacktestEngine, create_backtest_engine
from .SpyderR02_PaperEngine import PaperEngine, create_paper_engine
from .SpyderR03_PaperMonitor import PaperMonitor, create_paper_monitor
from .SpyderR04_LiveEngine import LiveEngine, create_live_engine

__all__ = [
    'BacktestEngine', 'create_backtest_engine',
    'PaperEngine', 'create_paper_engine',
    'PaperMonitor', 'create_paper_monitor',
    'LiveEngine', 'create_live_engine'
]
