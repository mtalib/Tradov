#!/usr/bin/env python3
"""
WebEngine Basic Test
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, QTimer


class WebEngineTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WebEngine Basic Test")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Status label
        self.status = QLabel("🔄 Loading WebEngine test...")
        layout.addWidget(self.status)

        # WebEngine view
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        # Load test HTML
        html_path = os.path.join(os.path.dirname(__file__), "webengine_test.html")
        self.web_view.load(QUrl.fromLocalFile(html_path))

        self.status.setText("✅ Test HTML loaded - check if visible")

        # Auto-exit
        QTimer.singleShot(10000, self.close)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WebEngineTestWindow()
    window.show()
    sys.exit(app.exec())
