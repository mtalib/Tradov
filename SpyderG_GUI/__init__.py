#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System
SpyderG_GUI Package
"""

# Try to import modules but don't fail if they're not available
modules = []

try:
    from .SpyderG05_TradingDashboard import *
    modules.append('SpyderG05_TradingDashboard')
except ImportError as e:
    print(f"⚠️ SpyderG05_TradingDashboard not available: {e}")

try:
    from .SpyderG07_PrometheusMetricsDisplay import get_client_status, get_system_metrics
    modules.append('SpyderG07_PrometheusMetricsDisplay')
except ImportError as e:
    print(f"⚠️ SpyderG07_PrometheusMetricsDisplay not available: {e}")

try:
    from .SpyderG09_RiskParametersDialog import RiskParametersDialog, show_risk_parameters_dialog
    modules.append('SpyderG09_RiskParametersDialog')
except ImportError as e:
    print(f"⚠️ SpyderG09_RiskParametersDialog not available: {e}")

try:
    from .SpyderG12_SignalInfoDialog import SignalInfoDialog
    modules.append('SpyderG12_SignalInfoDialog')
except ImportError as e:
    print(f"⚠️ SpyderG12_SignalInfoDialog not available: {e}")

print(f"SpyderG_GUI: {len(modules)} modules available")
