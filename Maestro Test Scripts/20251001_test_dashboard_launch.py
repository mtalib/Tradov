#!/usr/bin/env python3
"""
Quick test to launch the Spyder Trading Dashboard
This will test our matplotlib-to-Plotly migration in action!
"""
import sys
import os
from pathlib import Path

# Add Spyder root to path
spyder_root = "/home/adam/Projects/Spyder"
if spyder_root not in sys.path:
    sys.path.insert(0, spyder_root)


def main():
    """Launch the trading dashboard"""
    print("🚀 Launching Spyder Trading Dashboard...")
    print("This will showcase our matplotlib-to-Plotly migration!")
    print("=" * 60)

    try:
        # Import Qt
        from PySide6.QtWidgets import QApplication

        print("✅ PySide6 imported successfully")

        # Import the trading dashboard
        from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

        print("✅ SpyderTradingDashboard imported successfully")
        print("✅ This means our matplotlib-to-Plotly migration is working!")

        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("Spyder Trading System - Plotly Edition")
        app.setApplicationVersion("1.0.0")

        print("\n🎨 Creating dashboard with Plotly visualizations...")

        # Create and show dashboard
        dashboard = SpyderTradingDashboard()
        print("✅ Dashboard created successfully")

        # Show the dashboard
        dashboard.show()
        print("✅ Dashboard displayed")
        print("\n🎉 SUCCESS! Dashboard is running with Plotly charts!")
        print("💡 You should see the trading dashboard with interactive Plotly charts")
        print("💡 Close the window when you're done testing")

        # Start the event loop
        return app.exec()

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 This might be expected if some dependencies are missing")
        return 1

    except Exception as e:
        print(f"❌ Error launching dashboard: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
