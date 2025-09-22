# ==========================================================================
    # UTILITY METHODS - ENHANCED WITH HEARTBEAT WORKER AND LOGGING
    # ==========================================================================
    def start_market_worker(self):
        """Start the enhanced market worker with heartbeat monitoring and auto-reconnection"""
        try:
            self.market_thread = QThread()
            self.market_worker = ThreadSafeMarketDataWorker()
            self.market_worker.moveToThread(self.market_thread)

            # Connect all signals including new enhanced signals
            self.market_worker.data_updated.connect(self.on_market_data_updated)
            self.market_worker.connection_status_changed.connect(
                self.on_connection_status_changed
            )
            self.market_worker.market_data_status_changed.connect(
                self.on_market_data_status_changed
            )
            self.market_worker.error_occurred.connect(self.on_market_error)
            self.market_worker.heartbeat_received.connect(self.on_heartbeat_received)
            self.market_worker.heartbeat_status_changed.connect(
                self.on_heartbeat_status_changed
            )
            self.market_worker.log_message.connect(
                self.add_system_log
            )  # Direct log messages

            self.market_thread.started.connect(self.market_worker.start)
            self.market_thread.start()

            self.add_system_log(
                "📈 Market data worker started with enhanced logging and auto-reconnection"
            )

        except Exception as e:
            self.logger.error(f"Error starting market worker: {e}")
            self.add_system_log(f"⌐ Market worker error: {e}")

    def setup_timers(self):
        """Setup various timers"""
        # Date/time update timer
        self.datetime_timer = QTimer()
        self.datetime_timer.timeout.connect(self.update_datetime)
        self.datetime_timer.start(1000)

        # Automation activity timer
        self.automation_timer = QTimer()
        self.automation_timer.timeout.connect(self.generate_automation_activity)
        self.automation_timer.start(3000)

        # Greek risk update timer
        self.greek_timer = QTimer()
        self.greek_timer.timeout.connect(self.update_greek_risks)
        self.greek_timer.start(4000)

        # Chart update timer
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self.update_chart)
        self.chart_timer.start(30000)

        # Prometheus metrics simulation timer
        self.prometheus_timer = QTimer()
        self.prometheus_timer.timeout.connect(self.update_prometheus_metrics)
        self.prometheus_timer.start(8000)

    def update_datetime(self):
        """Update date/time display"""
        current_time = datetime.now().strftime("%Y-%m-%d   %H:%M:%S  ET")
        self.datetime_label.setText(current_time)

    def generate_automation_activity(self):
        """Generate automation activity logs using enhanced logger"""
        if not hasattr(self, "automation_activity_count"):
            self.automation_activity_count = 0

        activities = [
            "Scanning options chains for SPY",
            "Analyzing volatility surface patterns",
            "Monitoring delta-gamma hedging flows",
            "Evaluating iron condor opportunities",
            "Checking risk parameter compliance",
            "Calculating position Greeks",
            "Analyzing market microstructure",
            "Monitoring VIX term structure",
            "Evaluating covered call opportunities",
            "Scanning for unusual options activity",
            "Analyzing skew and smile patterns",
            "Monitoring earnings event calendar",
            "Evaluating butterfly spread setups",
            "Checking correlation patterns",
            "Analyzing order flow imbalances",
        ]

        self.automation_activity_count += 1
        activity = activities[self.automation_activity_count % len(activities)]
        self.add_automation_log(activity)

    def update_greek_risks(self):
        """Update Greek risk displays"""
        for name, bar in self.greek_bars.items():
            if name == "delta":
                value = random.uniform(-100, 100)
                status = "HIGH RISK" if abs(value) > 80 else "NORMAL"
            elif name == "gamma":
                value = random.uniform(-10, 10)
                status = "HIGH RISK" if abs(value) > 8 else "NORMAL"
            elif name == "theta":
                value = random.uniform(-400, 0)
                status = "HIGH DECAY" if value < -300 else "NORMAL"
            else:  # vega
                value = random.uniform(-600, 0)
                status = "HIGH RISK" if value < -450 else "NORMAL"

            bar.set_value(value, status)

    def update_prometheus_metrics(self):
        """Update Prometheus metrics simulation"""
        import random

        # Update system components
        for name, indicator in self.system_components.items():
            status = random.choice(["●", "●", "●", "●", "○"])  # 80% green, 20% gray
            if status == "●":
                indicator.setStyleSheet(
                    "color: " + COLORS["positive"] + f"; font-size: 14px;"
                )
            else:
                indicator.setStyleSheet(
                    f"color: {COLORS['text_dim']}; font-size: 14px;"
                )

        # Update client indicators
        for name, indicator in self.client_indicators.items():
            status = random.choice(["●", "●", "●", "○"])  # 75% green, 25% gray
            if status == "●":
                indicator.setStyleSheet(
                    "color: " + COLORS["positive"] + f"; font-size: 14px;"
                )
            else:
                indicator.setStyleSheet(
                    f"color: {COLORS['text_dim']}; font-size: 14px;"
                )

        # Update internal modules
        if hasattr(self, "internal_module_indicators"):
            for name, indicator in self.internal_module_indicators.items():
                if name == "custom_metrics":
                    # Custom metrics stays yellow/warning
                    indicator.setStyleSheet(
                        "color: " + COLORS["warning"] + f"; font-size: 14px;"
                    )
                else:
                    status = random.choice(["●", "●", "●", "○"])  # 75% green, 25% gray
                    if status == "●":
                        indicator.setStyleSheet(
                            "color: " + COLORS["positive"] + f"; font-size: 14px;"
                        )
                    else:
                        indicator.setStyleSheet(
                            f"color: {COLORS['text_dim']}; font-size: 14px;"
                        )

    def load_test_data(self):
        """Load test positions data"""
        test_positions = [
            {
                "date": "08/18",
                "symbol": "SPY",
                "contracts": "10",
                "strikes": "584P/586C",
                "expiry": "08/23",
                "strategy": "Iron Condor",
                "status": "OPEN",
                "cost": "-$2,350",
                "pnl": "+$435",
                "auto_status": "AI MANAGED",
            },
            {
                "date": "08/18",
                "symbol": "SPY",
                "contracts": "5",
                "strikes": "588C",
                "expiry": "08/30",
                "strategy": "Covered Call",
                "status": "OPEN",
                "cost": "+$425",
                "pnl": "+$125",
                "auto_status": "AI MANAGED",
            },
            {
                "date": "08/17",
                "symbol": "SPY",
                "contracts": "20",
                "strikes": "582P/584P/586C/588C",
                "expiry": "08/25",
                "strategy": "Iron Butterfly",
                "status": "CLOSED",
                "cost": "-$4,200",
                "pnl": "+$1,250",
                "auto_status": "AI CLOSED",
            },
        ]

        for i, pos in enumerate(test_positions):
            self.positions_table.insertRow(i)
            self.positions_table.setItem(i, 0, QTableWidgetItem(pos["date"]))
            self.positions_table.setItem(i, 1, QTableWidgetItem(pos["symbol"]))
            self.positions_table.setItem(i, 2, QTableWidgetItem(pos["contracts"]))
            self.positions_table.setItem(i, 3, QTableWidgetItem(pos["strikes"]))
            self.positions_table.setItem(i, 4, QTableWidgetItem(pos["expiry"]))
            self.positions_table.setItem(i, 5, QTableWidgetItem(pos["strategy"]))

            status_item = QTableWidgetItem(pos["status"])
            if pos["status"] == "OPEN":
                status_item.setForeground(QColor(COLORS["positive"]))
            else:
                status_item.setForeground(QColor(COLORS["neutral"]))
            self.positions_table.setItem(i, 6, status_item)

            self.positions_table.setItem(i, 7, QTableWidgetItem(pos["cost"]))

            pnl_item = QTableWidgetItem(pos["pnl"])
            if pos["pnl"].startswith("+"):
                pnl_item.setForeground(QColor(COLORS["positive"]))
            else:
                pnl_item.setForeground(QColor(COLORS["negative"]))
            self.positions_table.setItem(i, 8, pnl_item)

            auto_item = QTableWidgetItem(pos["auto_status"])
            auto_item.setForeground(QColor(COLORS["automation_active"]))
            self.positions_table.setItem(i, 9, auto_item)

    def load_default_risk_parameters(self):
        """Load default risk parameters"""
        self.current_risk_params = {
            "max_position_size": 50000,
            "max_daily_loss": 5000,
            "max_portfolio_delta": 100,
            "max_portfolio_gamma": 50,
            "vix_threshold": 30,
            "correlation_limit": 0.8,
        }

    def show_risk_parameters(self):
        """Show risk parameters dialog"""
        if RISK_DIALOG_AVAILABLE:
            show_risk_parameters_dialog(self)
        else:
            QMessageBox.information(
                self,
                "Risk Parameters",
                "Risk Parameters Configuration\n\n"
                "Max Position Size: $50,000\n"
                "Max Daily Loss: $5,000\n"
                "Max Portfolio Delta: 100\n"
                "Max Portfolio Gamma: 50\n"
                "VIX Threshold: 30\n"
                "Correlation Limit: 0.8",
            )

    def add_system_log(self, message: str):
        """Add message to system log using enhanced logger"""
        # Add to enhanced logger (which handles reverse chronological order)
        self.system_logger.add_entry(message)
        
        # Also add to traditional logs for compatibility
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.system_logs.append(formatted_message)

        # Keep only last 100 entries in traditional log
        if len(self.system_logs) > 100:
            self.system_logs = self.system_logs[-100:]

    def add_automation_log(self, message: str):
        """Add message to automation log using enhanced logger"""
        # Add to enhanced logger (which handles reverse chronological order)
        self.automation_logger.add_entry(message)
        
        # Also add to traditional logs for compatibility
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.automation_logs.append(formatted_message)

        # Keep only last 100 entries in traditional log
        if len(self.automation_logs) > 100:
            self.automation_logs = self.automation_logs[-100:]

    def setup_white_tooltips(self):
        """Setup white tooltips that are actually visible"""
        try:
            # Method 1: Set application-wide stylesheet
            app = QApplication.instance()
            if app:
                current_style = app.styleSheet()
                tooltip_style = """
                QToolTip {
                    color: #ffffff !important;
                    background-color: #1a1a1a !important;
                    border: 2px solid #555555 !important;
                    padding: 8px !important;
                    border-radius: 4px !important;
                    font-size: 12px !important;
                    font-weight: normal !important;
                    opacity: 1.0 !important;
                }
                """
                app.setStyleSheet(current_style + tooltip_style)
                self.add_system_log("White tooltip styling applied")

            # Method 2: Set widget-specific tooltip styling as backup
            widget_style = """
                QWidget {
                    selection-background-color: #2a2a2a;
                }
                QWidget QToolTip {
                    color: white !important;
                    background-color: #1a1a1a !important;
                    border: 2px solid #555555 !important;
                    padding: 8px !important;
                }
            """
            self.setStyleSheet(self.styleSheet() + widget_style)

        except Exception as e:
            self.add_system_log(f"⚠️ Tooltip styling error: {e}")

    def closeEvent(self, event):
        """Enhanced close event handler with enhanced logging cleanup"""
        try:
            # Log shutdown using enhanced loggers
            self.add_system_log("🔥 Enhanced Trading Dashboard shutting down...")
            self.add_automation_log("Dashboard session ended with enhanced logging")

            # Stop real data timer if active
            if hasattr(self, "_real_data_timer") and self._real_data_timer:
                self._real_data_timer.stop()

            # Stop monitoring timer if active
            if hasattr(self, "_check_timer") and self._check_timer:
                self._check_timer.stop()

            # Stop market worker and enhanced features
            if self.market_worker:
                self.market_worker.stop()

            # Stop market thread
            if self.market_thread and self.market_thread.isRunning():
                self.market_thread.quit()
                self.market_thread.wait(3000)

            # Stop all timers
            if hasattr(self, "datetime_timer"):
                self.datetime_timer.stop()
            if hasattr(self, "automation_timer"):
                self.automation_timer.stop()
            if hasattr(self, "greek_timer"):
                self.greek_timer.stop()
            if hasattr(self, "chart_timer"):
                self.chart_timer.stop()
            if hasattr(self, "prometheus_timer"):
                self.prometheus_timer.stop()

            # Accept close event
            event.accept()

        except Exception as e:
            print(f"Error during enhanced dashboard close: {e}")
            event.accept()