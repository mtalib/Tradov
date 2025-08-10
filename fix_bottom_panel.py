#!/usr/bin/env python3
# ===============================================================================
# SPYDER - Fix Dashboard Bottom Panel Layout
# Purpose: Correct the System Health and Prometheus Metrics display
# Author: Mohamed Talib
# Date: 2025-01-11
# ===============================================================================

"""
This module fixes the bottom-right panel to show:
- System Health (left column)
- Prometheus Metrics with correct client numbering (right columns)
- Proper title without clipping
"""

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

class FixedBottomPanel(QWidget):
    """Fixed bottom panel with System Health and Prometheus Metrics"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()
        
    def setupUI(self):
        """Setup the corrected UI layout"""
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Title Section - Ensure it's not clipped
        title_widget = QWidget()
        title_widget.setFixedHeight(30)
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(10, 5, 10, 5)
        
        title_label = QLabel("AUTONOMOUS AI ACTIVITY")
        title_label.setStyleSheet("""
            QLabel {
                color: #4a90e2;
                font-size: 14px;
                font-weight: bold;
                background-color: #1a1a2e;
                padding: 5px;
            }
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        main_layout.addWidget(title_widget)
        
        # Content Area - Split into two sections
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setSpacing(10)
        
        # =====================================
        # LEFT SIDE: SYSTEM HEALTH
        # =====================================
        system_health_frame = QFrame()
        system_health_frame.setStyleSheet("""
            QFrame {
                background-color: #0a0a1a;
                border: 1px solid #2a2a3a;
                border-radius: 5px;
            }
        """)
        
        health_layout = QVBoxLayout(system_health_frame)
        health_layout.setContentsMargins(10, 10, 10, 10)
        
        # System Health Title
        health_title = QLabel("SYSTEM HEALTH")
        health_title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                padding: 5px;
                background-color: #1a1a2e;
                border: 1px solid #3a3a4a;
            }
        """)
        health_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        health_layout.addWidget(health_title)
        
        # System Health Items
        health_items = [
            ("RISK MANAGER", True),
            ("MARKET DATA", True),
            ("STRATEGY ENGINE", True),
            ("ML MODELS", True),
            ("DATABASE", True)
        ]
        
        for item_name, is_active in health_items:
            item_widget = self.create_health_item(item_name, is_active)
            health_layout.addWidget(item_widget)
        
        # System Health Score
        health_score_widget = QWidget()
        health_score_layout = QHBoxLayout(health_score_widget)
        health_score_layout.setContentsMargins(5, 10, 5, 5)
        
        score_label = QLabel("System Health:")
        score_label.setStyleSheet("color: #8a8a8a; font-size: 11px;")
        health_score_layout.addWidget(score_label)
        
        score_value = QLabel("92/100")
        score_value.setStyleSheet("color: #00ff00; font-size: 11px; font-weight: bold;")
        health_score_layout.addWidget(score_value)
        health_score_layout.addStretch()
        
        health_layout.addWidget(health_score_widget)
        health_layout.addStretch()
        
        # =====================================
        # RIGHT SIDE: PROMETHEUS METRICS
        # =====================================
        prometheus_frame = QFrame()
        prometheus_frame.setStyleSheet("""
            QFrame {
                background-color: #0a0a1a;
                border: 1px solid #2a2a3a;
                border-radius: 5px;
            }
        """)
        
        prometheus_layout = QVBoxLayout(prometheus_frame)
        prometheus_layout.setContentsMargins(10, 10, 10, 10)
        
        # Prometheus Title
        prometheus_title = QLabel("PROMETHEUS METRICS")
        prometheus_title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                padding: 5px;
                background-color: #1a1a2e;
                border: 1px solid #3a3a4a;
            }
        """)
        prometheus_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prometheus_layout.addWidget(prometheus_title)
        
        # Client Grid - Correct numbering 0-8
        client_grid = QGridLayout()
        client_grid.setSpacing(5)
        
        # Correct client names and numbers
        clients = [
            (0, "Admin"),
            (1, "Orders"),
            (2, "Core"),
            (3, "Options"),
            (4, "Volatility"),
            (5, "Internals"),
            (6, "Major ETFs"),
            (7, "Extended Assets"),
            (8, "Sector ETFs")
        ]
        
        # Create two columns of clients
        for i, (client_num, client_name) in enumerate(clients):
            row = i % 5  # 5 rows max
            col = i // 5  # 2 columns
            
            client_widget = self.create_client_item(client_num, client_name)
            client_grid.addWidget(client_widget, row, col)
        
        prometheus_layout.addLayout(client_grid)
        
        # Metrics Summary
        metrics_widget = QWidget()
        metrics_layout = QGridLayout(metrics_widget)
        metrics_layout.setContentsMargins(5, 10, 5, 5)
        metrics_layout.setSpacing(5)
        
        metrics_data = [
            ("Active Clients:", "9/9", "#00ff00"),
            ("Memory:", "48%", "#ffaa00"),
            ("CPU:", "17%", "#00ff00"),
            ("API Calls/Sec:", "127", "#00ff00")
        ]
        
        for i, (label, value, color) in enumerate(metrics_data):
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #8a8a8a; font-size: 10px;")
            value_widget = QLabel(value)
            value_widget.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
            
            row = i // 2
            col = (i % 2) * 2
            metrics_layout.addWidget(label_widget, row, col)
            metrics_layout.addWidget(value_widget, row, col + 1)
        
        prometheus_layout.addWidget(metrics_widget)
        prometheus_layout.addStretch()
        
        # Add both panels to content layout
        content_layout.addWidget(system_health_frame, 1)
        content_layout.addWidget(prometheus_frame, 2)
        
        main_layout.addWidget(content_widget)
        
        # Set the overall style
        self.setStyleSheet("""
            QWidget {
                background-color: #0a0a0a;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
    
    def create_health_item(self, name, is_active):
        """Create a system health item widget"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Status indicator
        indicator = QLabel("●")
        if is_active:
            indicator.setStyleSheet("color: #00ff00; font-size: 12px;")
        else:
            indicator.setStyleSheet("color: #ff0000; font-size: 12px;")
        layout.addWidget(indicator)
        
        # Item name
        label = QLabel(name)
        label.setStyleSheet("color: #ffffff; font-size: 11px;")
        layout.addWidget(label)
        layout.addStretch()
        
        return widget
    
    def create_client_item(self, client_num, client_name):
        """Create a client item widget with correct numbering"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Status indicator (all green for now)
        indicator = QLabel("●")
        indicator.setStyleSheet("color: #00ff00; font-size: 10px;")
        layout.addWidget(indicator)
        
        # Client label with correct number
        label = QLabel(f"CLIENT {client_num}: {client_name}")
        label.setStyleSheet("color: #00ff00; font-size: 10px;")
        layout.addWidget(label)
        layout.addStretch()
        
        return widget


# ===============================================================================
# Integration function to replace existing bottom panel
# ===============================================================================

def integrate_fixed_panel(main_window):
    """
    Function to integrate the fixed panel into the existing dashboard
    Call this from your main dashboard to replace the bottom-right panel
    """
    try:
        # Find the bottom-right area in the main window
        # This depends on your actual dashboard structure
        
        # Method 1: If you have direct access to the layout
        if hasattr(main_window, 'bottom_right_widget'):
            # Replace the existing widget
            old_widget = main_window.bottom_right_widget
            new_widget = FixedBottomPanel()
            
            # Get parent layout
            parent_layout = old_widget.parent().layout()
            if parent_layout:
                # Find position of old widget
                index = parent_layout.indexOf(old_widget)
                # Remove old widget
                parent_layout.removeWidget(old_widget)
                old_widget.deleteLater()
                # Insert new widget
                parent_layout.insertWidget(index, new_widget)
                main_window.bottom_right_widget = new_widget
        
        # Method 2: Search for the widget by looking for specific text
        else:
            # Find all QWidget children
            for widget in main_window.findChildren(QWidget):
                # Look for the Prometheus panel
                if hasattr(widget, 'objectName') and 'prometheus' in widget.objectName().lower():
                    # Replace this widget
                    parent = widget.parent()
                    if parent and parent.layout():
                        new_widget = FixedBottomPanel()
                        layout = parent.layout()
                        layout.replaceWidget(widget, new_widget)
                        widget.deleteLater()
                        break
        
        print("Bottom panel fixed successfully!")
        return True
        
    except Exception as e:
        print(f"Error integrating fixed panel: {e}")
        return False


# ===============================================================================
# Standalone test
# ===============================================================================

if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    # Create test window
    window = QMainWindow()
    window.setWindowTitle("Fixed Bottom Panel Test")
    window.setGeometry(100, 100, 1000, 400)
    
    # Set dark theme
    window.setStyleSheet("""
        QMainWindow {
            background-color: #0a0a0a;
        }
    """)
    
    # Create and set the fixed panel
    panel = FixedBottomPanel()
    window.setCentralWidget(panel)
    
    window.show()
    sys.exit(app.exec())
