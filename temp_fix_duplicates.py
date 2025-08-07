#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEMPORARY FILE - Instructions to Fix Duplicate Module Numbers

This file provides instructions to resolve the duplicate G06 modules
and properly integrate the new Prometheus Metrics Display widget.
"""

# ==============================================================================
# CURRENT PROBLEM: DUPLICATE G06 MODULES
# ==============================================================================
"""
Current File Structure (INCORRECT):
------------------------------------
SpyderG_GUI/
├── SpyderG01_MainWindow.py
├── SpyderG02_GUIEntry.py
├── SpyderG03_OptionChainWidget.py
├── SpyderG04_ChartWidget.py
├── SpyderG05_TradingDashboard.py
├── SpyderG06_ClientMonitorPanel.py      ← DUPLICATE NUMBER
├── SpyderG06_RiskParametersDialog.py    ← DUPLICATE NUMBER
├── SpyderG08_DashboardDataBridge.py
└── [Missing G07]

SpyderB_Broker/
├── SpyderB15_PrometheusMetrics.py       ← Backend metrics collector (Client ID 9)
└── ... other B modules
"""

# ==============================================================================
# RECOMMENDED FIX: RENUMBER MODULES
# ==============================================================================
"""
Corrected File Structure (RECOMMENDED):
----------------------------------------
SpyderG_GUI/
├── SpyderG01_MainWindow.py
├── SpyderG02_GUIEntry.py
├── SpyderG03_OptionChainWidget.py
├── SpyderG04_ChartWidget.py
├── SpyderG05_TradingDashboard.py
├── SpyderG06_ClientMonitorPanel.py      ← Keep as G06
├── SpyderG07_PrometheusMetricsDisplay.py ← NEW: GUI for B15 metrics
├── SpyderG08_DashboardDataBridge.py
└── SpyderG09_RiskParametersDialog.py    ← RENAMED from duplicate G06

SpyderB_Broker/
├── SpyderB15_PrometheusMetrics.py       ← Existing backend (unchanged)
└── ... other B modules
"""

# ==============================================================================
# STEP-BY-STEP RENAMING INSTRUCTIONS
# ==============================================================================
print("""
FILE RENAMING INSTRUCTIONS:
===========================

Step 1: Rename the duplicate G06 file
--------------------------------------
OLD: SpyderG06_RiskParametersDialog.py
NEW: SpyderG09_RiskParametersDialog.py

Command (Linux/Mac):
  mv SpyderG06_RiskParametersDialog.py SpyderG09_RiskParametersDialog.py

Command (Windows):
  ren SpyderG06_RiskParametersDialog.py SpyderG09_RiskParametersDialog.py


Step 2: Update the module header in G09
----------------------------------------
Open SpyderG09_RiskParametersDialog.py and update the header:

  Module: SpyderG09_RiskParametersDialog.py  (was G06)
  Last Updated: 2025-08-07 Time: 11:15:00


Step 3: Add the new Prometheus Display module
----------------------------------------------
Save SpyderG07_PrometheusMetricsDisplay.py to SpyderG_GUI/


Step 4: Update imports in SpyderG05_TradingDashboard.py
--------------------------------------------------------
Add to imports section:
  from SpyderG07_PrometheusMetricsDisplay import PrometheusMetricsDisplay

If RiskParametersDialog is imported, update:
  from SpyderG09_RiskParametersDialog import RiskParametersDialog
""")

# ==============================================================================
# MODULE RELATIONSHIPS
# ==============================================================================
"""
Module Relationships After Fix:
================================

SpyderB15_PrometheusMetrics.py (Backend - Group B)
├── Collects metrics using Client ID 9
├── Runs Prometheus HTTP server on port 9090
├── Monitors all 9 clients (0-8) + itself
└── Provides metrics API

     ↓ Provides data to ↓

SpyderG07_PrometheusMetricsDisplay.py (GUI - Group G)
├── Displays metrics from B15
├── Shows client connection status
├── Updates every 2 seconds
└── Integrates into G05_TradingDashboard

     ↓ Integrates into ↓

SpyderG05_TradingDashboard.py (Main Dashboard)
├── Contains PrometheusMetricsDisplay widget
├── Shows next to System Health panel
└── Updates automatically from B15 data
"""

# ==============================================================================
# INTEGRATION CODE FOR G05_TradingDashboard
# ==============================================================================
def integration_example():
    """
    Example of how to integrate G07 into G05_TradingDashboard
    """
    
    # In SpyderG05_TradingDashboard.py, modify create_right_panel():
    
    code = '''
    def create_right_panel(self) -> QWidget:
        """Create right panel with Prometheus Metrics"""
        
        # ... existing code ...
        
        # Create container for System Health and Prometheus Metrics
        monitoring_container = QWidget()
        monitoring_layout = QHBoxLayout()
        monitoring_layout.setSpacing(5)
        monitoring_layout.setContentsMargins(0, 0, 0, 0)
        
        # LEFT: System Health (narrower)
        health_group = QGroupBox("SYSTEM HEALTH")
        health_group.setFixedWidth(180)
        health_layout = QVBoxLayout()
        health_layout.setSpacing(2)
        
        self.health_indicators = {
            "risk_manager": QLabel("● RISK MANAGER"),
            "market_data": QLabel("● MARKET DATA"),
            "strategy_engine": QLabel("● STRATEGY ENGINE"),
            "ml_models": QLabel("● ML MODELS"),
            "database": QLabel("● DATABASE"),
        }
        
        for indicator in self.health_indicators.values():
            indicator.setStyleSheet(f"color: {COLORS['positive']}; font-size: 10px;")
            health_layout.addWidget(indicator)
        
        health_group.setLayout(health_layout)
        monitoring_layout.addWidget(health_group)
        
        # RIGHT: Prometheus Metrics from G07
        self.prometheus_widget = PrometheusMetricsDisplay()
        self.prometheus_widget.setFixedWidth(420)
        
        # Connect signals
        self.prometheus_widget.metrics_updated.connect(
            self.on_prometheus_metrics_updated
        )
        
        monitoring_layout.addWidget(self.prometheus_widget)
        monitoring_container.setLayout(monitoring_layout)
        layout.addWidget(monitoring_container)
        
        # ... rest of the code ...
    '''
    
    return code

# ==============================================================================
# BENEFITS OF THIS ARCHITECTURE
# ==============================================================================
print("""

ARCHITECTURE BENEFITS:
======================

1. SEPARATION OF CONCERNS:
   - B15: Backend metrics collection (data layer)
   - G07: GUI display widget (presentation layer)
   - G05: Main dashboard (integration layer)

2. CLEAN MODULE NUMBERING:
   - No duplicate numbers
   - Sequential ordering maintained
   - Clear group separation (B vs G)

3. DATA FLOW:
   - B15 collects real metrics from IB Gateway
   - G07 fetches and displays metrics
   - G05 integrates everything seamlessly

4. CLIENT ID MANAGEMENT:
   - Clients 0-8: Trading operations
   - Client 9: Dedicated Prometheus metrics
   - No conflicts or overlaps

5. FALLBACK CAPABILITY:
   - If B15 is unavailable, G07 simulates data
   - Dashboard continues to function
   - No crashes or errors
""")

# ==============================================================================
# VERIFICATION CHECKLIST
# ==============================================================================
print("""

VERIFICATION CHECKLIST:
=======================

After making changes, verify:

□ SpyderG06_ClientMonitorPanel.py exists (only one G06)
□ SpyderG09_RiskParametersDialog.py exists (renamed from duplicate G06)
□ SpyderG07_PrometheusMetricsDisplay.py added to SpyderG_GUI/
□ SpyderB15_PrometheusMetrics.py unchanged in SpyderB_Broker/
□ G05_TradingDashboard imports G07 correctly
□ No import errors when running dashboard
□ Prometheus Metrics widget appears in dashboard
□ Client status indicators update properly
□ System metrics (CPU, Memory) display correctly

""")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("MODULE DUPLICATE FIX AND INTEGRATION GUIDE")
    print("="*70)
    print("\nThis guide shows how to:")
    print("1. Fix the duplicate G06 modules")
    print("2. Properly number the new Prometheus Display widget as G07")
    print("3. Integrate G07 with the existing B15 backend")
    print("4. Add the widget to G05_TradingDashboard")
    print("\nPlease follow the steps above to resolve the duplicates.")
    print("="*70)
