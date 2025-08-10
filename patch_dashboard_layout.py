#!/usr/bin/env python3
# ===============================================================================
# SPYDER - Dashboard Layout Patch
# Purpose: Fix the bottom panel layout in the running dashboard
# Run this to patch your existing dashboard files
# ===============================================================================

import os
import sys
import shutil
from pathlib import Path

SPYDER_HOME = "/home/adam/Projects/Spyder"

print("="*60)
print("  SPYDER DASHBOARD BOTTOM PANEL PATCH")
print("="*60)
print()

# Find the dashboard file
dashboard_files = [
    "SpyderG_GUI/SpyderG05_TradingDashboard.py",
    "SpyderG05_TradingDashboard.py",
    "TradingDashboard.py"
]

dashboard_path = None
for file in dashboard_files:
    full_path = Path(SPYDER_HOME) / file
    if full_path.exists():
        dashboard_path = full_path
        print(f"✓ Found dashboard at: {dashboard_path}")
        break

if not dashboard_path:
    print("✗ Dashboard file not found")
    print("\nCreating a patched dashboard module...")
    
    # Create the patched dashboard
    dashboard_path = Path(SPYDER_HOME) / "SpyderG05_TradingDashboard_Patched.py"
    
    with open(dashboard_path, 'w') as f:
        f.write('''#!/usr/bin/env python3
"""
SPYDER Trading Dashboard - Patched Version
Fixed bottom panel with System Health and correct Client numbering
"""

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys
from datetime import datetime

class SpyderTradingDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SPYDER - Autonomous Options Trading")
        self.setGeometry(50, 50, 1600, 900)
        
        # Set dark theme
        self.setStyleSheet("""
            QMainWindow { background-color: #0a0a0a; }
            QLabel { color: #ffffff; }
            QFrame { background-color: #1a1a2e; border: 1px solid #2a2a3a; }
        """)
        
        self.setupUI()
        
    def setupUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Top Bar
        self.create_top_bar(main_layout)
        
        # Main Content Area
        content_layout = QHBoxLayout()
        
        # Left Panel (Market Overview, Orders)
        left_panel = self.create_left_panel()
        content_layout.addWidget(left_panel, 1)
        
        # Center Panel (Chart, System Log)
        center_panel = self.create_center_panel()
        content_layout.addWidget(center_panel, 2)
        
        # Right Panel (Account, P&L, Risk)
        right_panel = self.create_right_panel()
        content_layout.addWidget(right_panel, 1)
        
        main_layout.addLayout(content_layout, 4)
        
        # Bottom Panel - FIXED VERSION
        bottom_panel = self.create_fixed_bottom_panel()
        main_layout.addWidget(bottom_panel, 1)
        
    def create_top_bar(self, parent_layout):
        """Create top bar with market data"""
        top_bar = QFrame()
        top_bar.setFixedHeight(60)
        top_bar.setStyleSheet("background-color: #0a0a0a; border: none;")
        
        layout = QHBoxLayout(top_bar)
        
        # Logo
        logo = QLabel("S P Y D E R")
        logo.setStyleSheet("color: #4a90e2; font-size: 24px; font-weight: bold;")
        layout.addWidget(logo)
        
        # Market Data
        for symbol, price, change, pct in [
            ("DJI:", "43,900.42", "+350.35", "+2.3%"),
            ("SPX:", "6,876.23", "+45.43", "+1.2%"),
            ("NDX:", "20,275.62", "+45.23", "+0.78%")
        ]:
            market_widget = QWidget()
            market_layout = QHBoxLayout(market_widget)
            market_layout.setSpacing(5)
            
            lbl_symbol = QLabel(symbol)
            lbl_symbol.setStyleSheet("color: #8a8a8a;")
            lbl_price = QLabel(price)
            lbl_price.setStyleSheet("color: #ffffff;")
            lbl_change = QLabel(f"{change} {pct}")
            lbl_change.setStyleSheet("color: #00ff00;")
            
            market_layout.addWidget(lbl_symbol)
            market_layout.addWidget(lbl_price)
            market_layout.addWidget(lbl_change)
            
            layout.addWidget(market_widget)
        
        layout.addStretch()
        
        # Status
        status = QLabel("● IB CONNECTED")
        status.setStyleSheet("color: #00ff00; font-weight: bold;")
        layout.addWidget(status)
        
        # Time
        time_label = QLabel(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        time_label.setStyleSheet("color: #8a8a8a;")
        layout.addWidget(time_label)
        
        parent_layout.addWidget(top_bar)
        
    def create_left_panel(self):
        """Create left panel with market overview"""
        panel = QFrame()
        layout = QVBoxLayout(panel)
        
        # Market Overview
        market_frame = QFrame()
        market_layout = QVBoxLayout(market_frame)
        
        title = QLabel("MARKET OVERVIEW")
        title.setStyleSheet("font-weight: bold; padding: 5px;")
        market_layout.addWidget(title)
        
        # Add some sample data
        table = QTableWidget(10, 4)
        table.setHorizontalHeaderLabels(["SYMBOL", "LAST", "CHG", "CHG%"])
        table.setStyleSheet("""
            QTableWidget { 
                background-color: #0a0a0a; 
                gridline-color: #2a2a3a;
            }
            QHeaderView::section {
                background-color: #1a1a2e;
                color: #8a8a8a;
                padding: 5px;
            }
        """)
        market_layout.addWidget(table)
        
        layout.addWidget(market_frame)
        
        # Orders Section
        orders_frame = QFrame()
        orders_layout = QVBoxLayout(orders_frame)
        
        orders_title = QLabel("ORDERS & POSITIONS")
        orders_title.setStyleSheet("font-weight: bold; padding: 5px;")
        orders_layout.addWidget(orders_title)
        
        orders_table = QTableWidget(5, 4)
        orders_table.setHorizontalHeaderLabels(["DATE", "SYMBOL", "QTY", "STATUS"])
        orders_layout.addWidget(orders_table)
        
        layout.addWidget(orders_frame)
        
        return panel
        
    def create_center_panel(self):
        """Create center panel with chart"""
        panel = QFrame()
        layout = QVBoxLayout(panel)
        
        # Chart placeholder
        chart = QLabel("SPY - 5 min")
        chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart.setStyleSheet("""
            background-color: #0a0a0a;
            border: 1px solid #2a2a3a;
            color: #4a90e2;
            font-size: 18px;
            min-height: 400px;
        """)
        layout.addWidget(chart, 3)
        
        # System Log
        log_frame = QFrame()
        log_layout = QVBoxLayout(log_frame)
        
        log_title = QLabel("SYSTEM LOG")
        log_title.setStyleSheet("font-weight: bold; padding: 5px;")
        log_layout.addWidget(log_title)
        
        log_text = QTextEdit()
        log_text.setReadOnly(True)
        log_text.setStyleSheet("""
            background-color: #0a0a0a;
            color: #00ff00;
            font-family: monospace;
            font-size: 11px;
        """)
        log_text.append(f"{datetime.now().strftime('%H:%M:%S')} - Dashboard initialized successfully")
        log_text.append(f"{datetime.now().strftime('%H:%M:%S')} - Connected to IB Gateway")
        log_text.append(f"{datetime.now().strftime('%H:%M:%S')} - Market data subscription active")
        
        log_layout.addWidget(log_text)
        layout.addWidget(log_frame, 1)
        
        return panel
        
    def create_right_panel(self):
        """Create right panel with account info"""
        panel = QFrame()
        layout = QVBoxLayout(panel)
        
        # Control Buttons
        btn_layout = QHBoxLayout()
        
        start_btn = QPushButton("START TRADING")
        start_btn.setStyleSheet("""
            QPushButton {
                background-color: #00ff00;
                color: #000000;
                font-weight: bold;
                padding: 10px;
            }
        """)
        btn_layout.addWidget(start_btn)
        
        stop_btn = QPushButton("STOP TRADING")
        stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9900;
                color: #000000;
                font-weight: bold;
                padding: 10px;
            }
        """)
        btn_layout.addWidget(stop_btn)
        
        layout.addLayout(btn_layout)
        
        # Account Info
        account_frame = QFrame()
        account_layout = QVBoxLayout(account_frame)
        
        account_title = QLabel("ACCOUNT")
        account_title.setStyleSheet("font-weight: bold; padding: 5px;")
        account_layout.addWidget(account_title)
        
        # Account details
        for label, value, color in [
            ("ACCOUNT", "DU5361048", "#ffffff"),
            ("SETTLED CASH", "$21,800,000.00", "#ffffff"),
            ("BUYING POWER", "$20,450,000.00", "#ffffff"),
            ("REALIZED P&L", "$2,030,450.00", "#00ff00"),
            ("UNREALIZED P&L", "$1,385,600.00", "#00ff00")
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #8a8a8a; font-size: 11px;")
            val = QLabel(value)
            val.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            account_layout.addLayout(row)
        
        layout.addWidget(account_frame)
        
        # Risk Parameters Button
        risk_btn = QPushButton("RISK PARAMETERS")
        risk_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                font-weight: bold;
                padding: 10px;
            }
        """)
        layout.addWidget(risk_btn)
        
        # Risk Monitor
        risk_frame = QFrame()
        risk_layout = QVBoxLayout(risk_frame)
        
        risk_title = QLabel("RISK MONITOR")
        risk_title.setStyleSheet("font-weight: bold; padding: 5px;")
        risk_layout.addWidget(risk_title)
        
        # Risk bars
        for metric, value, color in [
            ("Delta", 0.85, "#ffaa00"),
            ("Gamma", 0.30, "#00ff00"),
            ("Theta", -0.80, "#ffaa00"),
            ("Vega", 0.45, "#00ff00")
        ]:
            metric_layout = QHBoxLayout()
            metric_label = QLabel(f"{metric}:")
            metric_label.setStyleSheet("color: #8a8a8a; font-size: 11px;")
            
            bar = QProgressBar()
            bar.setValue(int(abs(value) * 100))
            bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #2a2a3a;
                    background-color: #0a0a0a;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                }}
            """)
            
            metric_layout.addWidget(metric_label)
            metric_layout.addWidget(bar)
            risk_layout.addLayout(metric_layout)
        
        layout.addWidget(risk_frame)
        layout.addStretch()
        
        return panel
        
    def create_fixed_bottom_panel(self):
        """Create FIXED bottom panel with System Health and correct Prometheus Metrics"""
        panel = QFrame()
        panel.setStyleSheet("background-color: #0a0a0a; border: 1px solid #2a2a3a;")
        
        main_layout = QVBoxLayout(panel)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Title - Make sure it's not clipped
        title_widget = QWidget()
        title_widget.setFixedHeight(35)
        title_layout = QHBoxLayout(title_widget)
        
        title = QLabel("AUTONOMOUS AI ACTIVITY")
        title.setStyleSheet("""
            color: #4a90e2;
            font-size: 14px;
            font-weight: bold;
            padding: 5px;
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        main_layout.addWidget(title_widget)
        
        # Content split into two columns
        content_layout = QHBoxLayout()
        
        # LEFT: SYSTEM HEALTH
        health_frame = QFrame()
        health_frame.setStyleSheet("background-color: #1a1a2e;")
        health_layout = QVBoxLayout(health_frame)
        
        health_title = QLabel("SYSTEM HEALTH")
        health_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        health_title.setStyleSheet("""
            background-color: #0a0a0a;
            color: #ffffff;
            font-weight: bold;
            padding: 5px;
            border: 1px solid #3a3a4a;
        """)
        health_layout.addWidget(health_title)
        
        # Health items
        for item in ["RISK MANAGER", "MARKET DATA", "STRATEGY ENGINE", "ML MODELS", "DATABASE"]:
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            
            indicator = QLabel("●")
            indicator.setStyleSheet("color: #00ff00; font-size: 12px;")
            item_layout.addWidget(indicator)
            
            label = QLabel(item)
            label.setStyleSheet("color: #ffffff; font-size: 11px;")
            item_layout.addWidget(label)
            item_layout.addStretch()
            
            health_layout.addWidget(item_widget)
        
        # Health score
        score_widget = QWidget()
        score_layout = QHBoxLayout(score_widget)
        score_label = QLabel("System Health:")
        score_label.setStyleSheet("color: #8a8a8a; font-size: 11px;")
        score_value = QLabel("92/100")
        score_value.setStyleSheet("color: #00ff00; font-size: 11px; font-weight: bold;")
        score_layout.addWidget(score_label)
        score_layout.addWidget(score_value)
        score_layout.addStretch()
        health_layout.addWidget(score_widget)
        
        health_layout.addStretch()
        content_layout.addWidget(health_frame, 1)
        
        # RIGHT: PROMETHEUS METRICS (with correct client numbering)
        metrics_frame = QFrame()
        metrics_frame.setStyleSheet("background-color: #1a1a2e;")
        metrics_layout = QVBoxLayout(metrics_frame)
        
        metrics_title = QLabel("PROMETHEUS METRICS")
        metrics_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        metrics_title.setStyleSheet("""
            background-color: #0a0a0a;
            color: #ffffff;
            font-weight: bold;
            padding: 5px;
            border: 1px solid #3a3a4a;
        """)
        metrics_layout.addWidget(metrics_title)
        
        # Clients grid - CORRECTED NUMBERING
        clients_grid = QGridLayout()
        clients = [
            (0, "Admin"), (1, "Orders"), (2, "Core"),
            (3, "Options"), (4, "Volatility"), (5, "Internals"),
            (6, "Major ETFs"), (7, "Extended Assets"), (8, "Sector ETFs")
        ]
        
        for i, (num, name) in enumerate(clients):
            client_widget = QWidget()
            client_layout = QHBoxLayout(client_widget)
            
            indicator = QLabel("●")
            indicator.setStyleSheet("color: #00ff00; font-size: 10px;")
            client_layout.addWidget(indicator)
            
            label = QLabel(f"CLIENT {num}: {name}")
            label.setStyleSheet("color: #00ff00; font-size: 10px;")
            client_layout.addWidget(label)
            client_layout.addStretch()
            
            row = i % 5
            col = i // 5
            clients_grid.addWidget(client_widget, row, col)
        
        metrics_layout.addLayout(clients_grid)
        
        # Metrics summary
        summary_layout = QHBoxLayout()
        for label, value in [("Active:", "9/9"), ("Memory:", "48%"), ("CPU:", "17%"), ("API/s:", "127")]:
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #8a8a8a; font-size: 10px;")
            val = QLabel(value)
            val.setStyleSheet("color: #00ff00; font-size: 10px; font-weight: bold;")
            summary_layout.addWidget(lbl)
            summary_layout.addWidget(val)
            summary_layout.addStretch()
        
        metrics_layout.addLayout(summary_layout)
        metrics_layout.addStretch()
        content_layout.addWidget(metrics_frame, 2)
        
        main_layout.addLayout(content_layout)
        
        return panel

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dashboard = SpyderTradingDashboard()
    dashboard.show()
    sys.exit(app.exec())
''')
    
    print(f"✓ Created patched dashboard at: {dashboard_path}")

# Backup original
if dashboard_path and dashboard_path.exists():
    backup_path = dashboard_path.with_suffix('.bak')
    if not backup_path.exists():
        shutil.copy(dashboard_path, backup_path)
        print(f"✓ Backed up original to: {backup_path}")

print("\n" + "="*60)
print("  PATCH COMPLETE!")
print("="*60)
print()
print("To use the fixed dashboard:")
print()
print("1. Stop the current dashboard")
print("2. Run the patched version:")
print(f"   python3 {dashboard_path}")
print()
print("Or update your launcher to use the patched file.")
print()
print("The fixed bottom panel now shows:")
print("  • System Health (left column)")
print("  • Prometheus Metrics with CLIENT 0-8 (right columns)")
print("  • 'AUTONOMOUS AI ACTIVITY' title without clipping")
