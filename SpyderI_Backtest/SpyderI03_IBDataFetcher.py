#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderI02_IBDataFetcher.py
Group: I (Backtesting)
Purpose: Fetch historical options data from Interactive Brokers

Description:
    This module fetches real historical data from Interactive Brokers
    for use in backtesting. While this provides more realistic data
    than synthetic generation, remember that options backtesting still
    has significant limitations and should be used for logic testing only.

Author: Mohamed Talib
Date: 2025-05-31
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import pandas as pd
import numpy as np

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from ibapi.contract import Contract
from ibapi.order import Order
import backtrader as bt

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderB_Broker.SpyderB01_IBClient import SpyderIBClient

# ==============================================================================
# CONSTANTS
# ==============================================================================
# IB historical data limitations
MAX_HISTORICAL_DAYS = 365  # 1 year max for options
RATE_LIMIT_DELAY = 10  # Seconds between requests to avoid pacing violations

# Bar sizes available from IB
BAR_SIZES = {
    '1 secs': '1 S',
    '5 secs': '5 S',
    '10 secs': '10 S',
    '15 secs': '15 S',
    '30 secs': '30 S',
    '1 min': '1 M',
    '2 mins': '2 M',
    '3 mins': '3 M',
    '5 mins': '5 M',
    '10 mins': '10 M',
    '15 mins': '15 M',
    '20 mins': '20 M',
    '30 mins': '30 M',
    '1 hour': '1 H',
    '2 hours': '2 H',
    '3 hours': '3 H',
    '4 hours': '4 H',
    '8 hours': '8 H',
    '1 day': '1 D',
    '1 week': '1 W',
    '1 month': '1 M'
}

# What to show options
WHAT_TO_SHOW = {
    'trades': 'TRADES',
    'midpoint': 'MIDPOINT',
    'bid': 'BID',
    'ask': 'ASK',
    'bid_ask': 'BID_ASK',
    'volatility': 'HISTORICAL_VOLATILITY',
    'option_iv': 'OPTION_IMPLIED_VOLATILITY'
}

# ==============================================================================
# DATA STRUCTURES
# ==============