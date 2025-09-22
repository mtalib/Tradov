# ==============================================================================
# ENHANCED REAL DATA INTEGRATION FUNCTIONS
# ==============================================================================
def apply_real_data_patch_to_dashboard(dashboard, data_file):
    """Apply real data patch to existing dashboard using proven pattern"""

    def update_with_real_data():
        """Update dashboard with real market data"""
        try:
            if not data_file.exists():
                return

            with open(data_file, "r") as f:
                live_data = json.load(f)

            if not live_data:
                return

            # Update symbol widgets directly
            for symbol, data in live_data.items():
                if symbol in dashboard.symbol_widgets:
                    widget = dashboard.symbol_widgets[symbol]

                    # Update price
                    if hasattr(widget, "price_label"):
                        widget.price_label.setText(f"{data['last']:.2f}")

                    # Update change with color
                    if hasattr(widget, "change_label"):
                        change = data["change"]
                        sign = "+" if change >= 0 else ""
                        widget.change_label.setText(f"{sign}{change:.2f}")
                        color = "#00ff41" if change >= 0 else "#ff1744"
                        widget.change_label.setStyleSheet(f"color: {color};")

                    # Update percentage with color
                    if hasattr(widget, "pct_label"):
                        pct = data["change_pct"]
                        sign = "+" if pct >= 0 else ""
                        widget.pct_label.setText(f"{sign}{pct:.2f}%")
                        color = "#00ff41" if pct >= 0 else "#ff1744"
                        widget.pct_label.setStyleSheet(f"color: {color};")

            # Update toolbar indices
            update_toolbar_with_real_data_helper(dashboard, live_data)

        except Exception as e:
            print(f"Error updating real data: {e}")

    # Stop original simulation
    try:
        if hasattr(dashboard, "market_worker"):
            worker = dashboard.market_worker
            if hasattr(worker, "update_timer") and worker.update_timer:
                worker.update_timer.stop()
                print("Stopped simulation timer")

        if hasattr(dashboard, "automation_timer"):
            dashboard.automation_timer.setInterval(20000)  # Slow down automation

    except Exception as e:
        print(f"Could not stop simulation: {e}")

    # Start real data updates
    dashboard._real_data_timer = QTimer()
    dashboard._real_data_timer.timeout.connect(update_with_real_data)
    dashboard._real_data_timer.start(1000)  # Update every second

    # Initial update
    update_with_real_data()

    # Add log entries using enhanced loggers
    dashboard.add_system_log("REAL MARKET DATA ACTIVE - IB Gateway prices")
    dashboard.add_automation_log("Real-time market data from Interactive Brokers")

    print("Real data patch applied successfully!")


def setup_real_data_monitoring_for_dashboard(dashboard, data_file):
    """Setup monitoring for real data to become available (proven pattern)"""

    def check_for_real_data():
        """Check if real data becomes available"""
        if getattr(dashboard, "real_data_active", False):
            return  # Already using real data

        if data_file.exists():
            try:
                with open(data_file, "r") as f:
                    data = json.load(f)

                if data:
                    print("Real data detected - switching from simulation!")
                    dashboard.add_system_log(
                        "Real data detected - switching from simulation!"
                    )
                    dashboard._check_timer.stop()
                    apply_real_data_patch_to_dashboard(dashboard, data_file)
                    dashboard.real_data_active = True
            except:
                pass

    # Check every 5 seconds for real data
    dashboard._check_timer = QTimer()
    dashboard._check_timer.timeout.connect(check_for_real_data)
    dashboard._check_timer.start(5000)


def update_toolbar_with_real_data_helper(dashboard, live_data):
    """Update toolbar indices with real data (proven pattern)"""
    try:
        # Update SPX from SPY (SPY * 10)
        if "SPY" in live_data:
            spy_data = live_data["SPY"]

            if hasattr(dashboard, "spx_value"):
                dashboard.spx_value.setText(f" {spy_data['last'] * 10:.0f}")

            if hasattr(dashboard, "spx_change"):
                change = spy_data["change"] * 10
                pct = spy_data["change_pct"]
                sign = "+" if change >= 0 else ""
                dashboard.spx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                color = "#00ff41" if change >= 0 else "#ff1744"
                dashboard.spx_change.setStyleSheet(f"color: {color};")

        # Update NDX from QQQ (QQQ * 35)
        if "QQQ" in live_data:
            qqq_data = live_data["QQQ"]

            if hasattr(dashboard, "ndx_value"):
                dashboard.ndx_value.setText(f" {qqq_data['last'] * 35:.0f}")

            if hasattr(dashboard, "ndx_change"):
                change = qqq_data["change"] * 35
                pct = qqq_data["change_pct"]
                sign = "+" if change >= 0 else ""
                dashboard.ndx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                color = "#00ff41" if change >= 0 else "#ff1744"
                dashboard.ndx_change.setStyleSheet(f"color: {color};")

        # Update DJI from DIA (DIA * 98)
        if "DIA" in live_data:
            dia_data = live_data["DIA"]

            if hasattr(dashboard, "dji_value"):
                dashboard.dji_value.setText(f" {dia_data['last'] * 98:.0f}")

            if hasattr(dashboard, "dji_change"):
                change = dia_data["change"] * 98
                pct = dia_data["change_pct"]
                sign = "+" if change >= 0 else ""
                dashboard.dji_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                color = "#00ff41" if change >= 0 else "#ff1744"
                dashboard.dji_change.setStyleSheet(f"color: {color};")

    except Exception as e:
        pass  # Suppress toolbar update errors


def update_status_for_real_data_helper(dashboard):
    """Update status indicators for real data - FIXED to not override IB status"""
    try:
        # Real data integration should not change IB connection display
        # IB status should always reflect actual IB Gateway connection
        pass  # Don't override IB connection status

    except Exception as e:
        pass  # Not critical


# ==============================================================================
# STANDALONE FUNCTIONS FOR EXTERNAL USE
# ==============================================================================
def create_spyder_trading_dashboard():
    """Factory function to create SpyderTradingDashboard instance"""
    return SpyderTradingDashboard()


def get_dashboard_with_real_data_integration():
    """Create dashboard with real data integration pre-configured"""
    dashboard = SpyderTradingDashboard()
    return dashboard


def apply_external_real_data_patch(dashboard, data_file_path=None):
    """Apply real data patch from external module"""
    if data_file_path is None:
        data_file_path = Path.home() / "Projects/Spyder/market_data/live_data.json"

    data_file = Path(data_file_path)

    if data_file.exists():
        try:
            with open(data_file, "r") as f:
                data = json.load(f)

            if data:
                apply_real_data_patch_to_dashboard(dashboard, data_file)
                update_status_for_real_data_helper(dashboard)
                dashboard.real_data_active = True
                return True
        except Exception as e:
            print(f"Error applying external real data patch: {e}")

    return False


def create_enhanced_dashboard_with_logging():
    """Create dashboard with enhanced logging and auto-reconnection features"""
    return SpyderTradingDashboard()


def get_enhanced_logger_dashboard():
    """Get dashboard instance with enhanced reverse chronological logging"""
    dashboard = SpyderTradingDashboard()
    return dashboard


# ==============================================================================
# MAIN EXECUTION - FOR STANDALONE TESTING
# ==============================================================================
def main():
    """Main function for standalone testing with enhanced features"""
    print("=" * 70)
    print("SPYDER G05 - ENHANCED WITH LOGGING & AUTO-RECONNECTION")
    print("=" * 70)
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    try:
        # Create enhanced dashboard
        dashboard = SpyderTradingDashboard()
        
        # Log startup with enhanced logging
        dashboard.add_system_log("Enhanced Trading Dashboard with reverse chronological logging initialized")
        dashboard.add_automation_log("Auto-reconnection manager active")
        
        # INTEGRATE REAL IB DATA
        try:
            from SpyderB_Broker.SpyderB27_IBDataConnector import patch_dashboard_with_ib_data
            patch_dashboard_with_ib_data(dashboard)
            dashboard.add_system_log("Real IB market data connector integrated!")
            print("Real IB market data connector integrated!")
        except Exception as e:
            dashboard.add_system_log(f"Could not integrate IB data: {e}")
            print(f"Could not integrate IB data: {e}")
        
        # Show dashboard
        dashboard.show()
        
        return app.exec()
        
    except Exception as e:
        print(f"\nStartup error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())