#!/usr/bin/env python3
"""
Minimal Dashboard Test - No excessive logging, single connection
"""

import sys
import os
import logging
import warnings
from pathlib import Path

# Suppress all warnings and reduce logging immediately
warnings.filterwarnings("ignore")
logging.getLogger().setLevel(logging.ERROR)

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    print("🧪 MINIMAL DASHBOARD TEST")
    print("=" * 40)
    print("✅ Testing with single connection, no logging flood")

    try:
        from PySide6.QtWidgets import (
            QApplication,
            QMainWindow,
            QLabel,
            QVBoxLayout,
            QWidget,
        )
        from PySide6.QtCore import QTimer
        import ib_async

        print("✅ Modules imported")

        # Create minimal Qt app
        app = QApplication(sys.argv)

        # Create simple window with connection test
        window = QMainWindow()
        window.setWindowTitle("SPYDER - Minimal Test")
        window.setGeometry(100, 100, 400, 200)

        central_widget = QWidget()
        layout = QVBoxLayout()

        status_label = QLabel("Testing Gateway connection...")
        layout.addWidget(status_label)

        central_widget.setLayout(layout)
        window.setCentralWidget(central_widget)

        # Test Gateway connection
        async def test_connection():
            try:
                ib = ib_async.IB()
                await ib.connectAsync("127.0.0.1", 4002, clientId=500, timeout=30)

                accounts = ib.managedAccounts()
                status_label.setText(f"✅ CONNECTED! Accounts: {accounts}")
                print(f"✅ Connection successful: {accounts}")

                # Test market data
                spy = ib_async.Stock("SPY", "SMART", "USD")
                ticker = ib.reqMktData(spy, "", False, False)

                import asyncio

                await asyncio.sleep(2)

                if ticker.last and ticker.last > 0:
                    price_text = f"📈 SPY: ${ticker.last:.2f}"
                    status_label.setText(f"✅ LIVE DATA: {price_text}")
                    print(f"✅ Live data: {price_text}")

                ib.cancelMktData(spy)
                ib.disconnect()

            except Exception as e:
                status_label.setText(f"❌ Connection failed: {e}")
                print(f"❌ Connection error: {e}")

        # Run connection test
        import asyncio

        asyncio.create_task(test_connection())

        window.show()
        print("✅ Minimal test window displayed")

        # Timer to close automatically
        def auto_close():
            print("🔄 Auto-closing in 30 seconds...")
            window.close()

        timer = QTimer()
        timer.timeout.connect(auto_close)
        timer.start(30000)  # 30 seconds

        return app.exec()

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
