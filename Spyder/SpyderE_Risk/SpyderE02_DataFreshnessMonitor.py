#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE02_DataFreshnessMonitor.py
Purpose: DEPRECATED SHIM — renamed to SpyderE24_DataFreshnessMonitor.py
         (P1-3: resolved E02 numeric prefix collision with SpyderE02_PositionSizer)

This file re-exports everything from the canonical module so that any legacy
import paths continue to work during the transition period.
"""
# ruff: noqa: F401
from Spyder.SpyderE_Risk.SpyderE24_DataFreshnessMonitor import (  # noqa: F401
    DataFreshnessMonitor,
    create_freshness_monitor,
)

