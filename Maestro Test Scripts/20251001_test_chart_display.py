#!/usr/bin/env python3
"""
Simple Chart Alternative Test
Try different approaches to display the chart
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plotly.graph_objects as go
import pandas as pd
import numpy as np
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QTimer


class ChartTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chart Display Test")
        self.setGeometry(100, 100, 1000, 700)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Add status label
        self.status_label = QLabel("🔄 Testing chart display methods...")
        layout.addWidget(self.status_label)

        # Add button to test different methods
        self.test_btn = QPushButton("Test WebEngine Chart")
        self.test_btn.clicked.connect(self.test_webengine)
        layout.addWidget(self.test_btn)

        # Add text area for debugging
        self.debug_text = QTextEdit()
        self.debug_text.setMaximumHeight(100)
        layout.addWidget(self.debug_text)

        # Add WebEngine view
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(400)
        layout.addWidget(self.web_view)

        # Try immediate test
        QTimer.singleShot(1000, self.test_webengine)

    def log(self, msg):
        print(msg)
        self.debug_text.append(msg)

    def test_webengine(self):
        self.log("🎨 Creating simple test chart...")
        self.status_label.setText("🎨 Creating Plotly chart...")

        try:
            # Create very simple chart
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=[1, 2, 3, 4, 5],
                    y=[10, 11, 12, 11, 10],
                    mode="lines+markers",
                    name="Test Data",
                    line=dict(color="#00E676", width=3),
                    marker=dict(size=8),
                )
            )

            fig.update_layout(
                title="🚀 Simple Test Chart",
                paper_bgcolor="white",
                plot_bgcolor="white",
                font=dict(color="black", size=14),
                width=800,
                height=400,
            )

            # Convert to HTML
            html_content = fig.to_html(include_plotlyjs=True)
            self.log(f"📄 HTML length: {len(html_content)}")

            # Test 1: Direct HTML
            self.web_view.setHtml(html_content)
            self.log("🌐 HTML loaded to WebEngine")

            self.status_label.setText("✅ Chart loaded - check if visible")

            # Set a timer to check loading
            QTimer.singleShot(3000, self.check_loading)

        except Exception as e:
            self.log(f"❌ Error: {e}")
            self.status_label.setText(f"❌ Error: {e}")

    def check_loading(self):
        self.log("⏰ Checking if chart loaded...")
        self.status_label.setText("⏰ Chart should be visible now")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    print("🚀 Testing different chart display approaches...")

    window = ChartTestWindow()
    window.show()

    # Auto-exit after 15 seconds
    QTimer.singleShot(15000, app.quit)

    sys.exit(app.exec())
