#!/usr/bin/env python3
"""
Debug Plotly Chart Display
Test if Plotly charts can be displayed in QWebEngineView
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plotly.graph_objects as go
import pandas as pd
import numpy as np
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from datetime import datetime


class PlotlyTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plotly Chart Test")
        self.setGeometry(100, 100, 800, 600)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create layout
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Create WebEngine view
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        # Create and display chart
        self.create_test_chart()

    def create_test_chart(self):
        print("🎨 Creating test Plotly chart...")

        try:
            # Generate sample data
            dates = pd.date_range(start="2025-09-29", periods=50, freq="T")
            prices = 580 + np.cumsum(np.random.randn(50) * 0.1)

            # Create figure
            fig = go.Figure()

            # Add price line
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=prices,
                    mode="lines",
                    name="SPY Price",
                    line=dict(color="#00E676", width=2),
                )
            )

            # Update layout
            fig.update_layout(
                title="📈 SPY Test Chart",
                paper_bgcolor="rgba(45, 45, 45, 1)",
                plot_bgcolor="rgba(30, 30, 30, 1)",
                font=dict(color="#FFFFFF"),
                xaxis=dict(gridcolor="rgba(128, 128, 128, 0.2)"),
                yaxis=dict(gridcolor="rgba(128, 128, 128, 0.2)", title="Price ($)"),
                margin=dict(l=60, r=20, t=60, b=60),
            )

            # Convert to HTML
            html_content = fig.to_html(include_plotlyjs=True)

            print(f"📄 HTML content length: {len(html_content)} characters")
            print("🌐 Loading HTML into WebEngine...")

            # Load into WebEngine
            self.web_view.setHtml(html_content)

            print("✅ Test chart loaded successfully!")

        except Exception as e:
            print(f"❌ Test chart failed: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    print("🚀 Starting Plotly chart test...")

    window = PlotlyTestWindow()
    window.show()

    print("✅ Test window displayed")
    print("💡 Check if you can see the Plotly chart in the window")

    # Run for 10 seconds then exit
    from PySide6.QtCore import QTimer

    timer = QTimer()
    timer.timeout.connect(app.quit)
    timer.start(10000)  # 10 seconds

    sys.exit(app.exec())
