#!/usr/bin/env python3
"""
Simple Widget Test - verify basic Qt widget rendering
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont


class SimpleWidgetTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Widget Display Test")
        self.setGeometry(100, 100, 600, 400)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Test widgets with different colors
        widgets = [
            ("🟢 GREEN WIDGET - Chart Area Test", "#2d2d2d", "#00E676"),
            ("🟠 ORANGE WIDGET - Moving Average Test", "#2d2d2d", "#FFB74D"),
            ("🔵 BLUE WIDGET - Dashboard Panel Test", "#2d2d2d", "#00B8D4"),
            ("🟣 PURPLE WIDGET - Accent Color Test", "#2d2d2d", "#9C27B0"),
        ]

        for text, bg_color, border_color in widgets:
            label = QLabel(text)
            label.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {bg_color};
                    border: 3px solid {border_color};
                    border-radius: 8px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 20px;
                    margin: 10px;
                }}
            """
            )
            label.setFont(QFont("Arial", 14))
            layout.addWidget(label)

        # Final test label
        test_label = QLabel(
            "✅ If you can see all 4 colored widgets above, Qt rendering works!\n❌ If this area is blank, there's a Qt/display issue"
        )
        test_label.setStyleSheet(
            """
            QLabel {
                background-color: #1e1e1e;
                border: 2px solid #FFFFFF;
                color: #FFFFFF;
                font-size: 14px;
                padding: 15px;
                margin: 10px;
            }
        """
        )
        layout.addWidget(test_label)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    print("🧪 Testing basic Qt widget rendering...")
    print("💡 You should see 4 colored rectangular widgets")

    window = SimpleWidgetTest()
    window.show()

    # Auto-close after 10 seconds
    QTimer.singleShot(10000, app.quit)

    sys.exit(app.exec())
