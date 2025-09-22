# ==============================================================================
# MAIN DASHBOARD CLASS - WITH ENHANCED LOGGING AND AUTO-RECONNECTION
# ==============================================================================
class SpyderTradingDashboard(QMainWindow):
    """Complete dashboard with enhanced logging and auto-reconnection features"""

    def __init__(self):
        super().__init__()

        # Initialize logging
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Initialize enhanced logging
        self.system_logger = ReverseOrderLogger(max_entries=200, update_callback=self._update_system_log_display)
        self.automation_logger = ReverseOrderLogger(max_entries=200, update_callback=self._update_automation_log_display)

        # Connection info - FIXED: Start disconnected
        self.connection_info = ConnectionInfo(
            ib_connected=False,
            connection_mode="DISCONNECTED",
            market_data_status="NONE",
            trading_active=False,
            simulation_mode=False,
        )
        self.market_worker = None
        self.market_thread = None

        # Dashboard data
        self.market_data = {}
        self.positions = []
        self.greek_risks = GreekRisk(45.5, -2.3, -156.8, -245.2)
        self.system_logs = []
        self.automation_logs = []
        self.account_mode = "PAPER"
        self.ib_connected = False  # FIXED: Start disconnected
        self.trading_active = False
        self.auto_connect_attempts = 0

        # Risk parameters
        self.current_risk_params = None
        self.risk_monitoring_active = False

        # Widget storage
        self.symbol_widgets = {}

        # Prometheus metrics attributes
        self.system_components = {}
        self.client_indicators = {}
        self.system_stats = {}
        self.prometheus_timer = None

        # Real data integration attributes
        self.real_data_active = False
        self.data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
        self._real_data_timer = None
        self._check_timer = None
        self._error_count = 0

        # Try to connect to real Prometheus collector if available
        if PROMETHEUS_AVAILABLE:
            self.get_client_status = get_client_status
            self.get_system_metrics = get_system_metrics
        else:
            self.get_client_status = None
            self.get_system_metrics = None

        # Initialize UI
        self.setup_ui()
        self.setup_timers()
        self.load_test_data()
        self.load_default_risk_parameters()

        # Start market worker with enhanced features
        self.start_market_worker()

        # Apply white tooltip styling
        self.setup_white_tooltips()

        # Real data integration (after UI is ready)
        QTimer.singleShot(1000, self.apply_proven_real_data_pattern)

        self.logger.info(
            "Enhanced Dashboard initialized with reverse logging and auto-reconnection"
        )

    def _update_system_log_display(self):
        """Update system log display from enhanced logger"""
        if hasattr(self, 'system_log'):
            recent_entries = self.system_logger.get_recent_entries(20)
            self.system_log.clear()
            self.system_log.append("\n".join(recent_entries))
            
            # Scroll to top since entries are in reverse chronological order
            cursor = self.system_log.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.system_log.setTextCursor(cursor)

    def _update_automation_log_display(self):
        """Update automation log display from enhanced logger"""
        if hasattr(self, 'auto_log'):
            recent_entries = self.automation_logger.get_recent_entries(15)
            self.auto_log.clear()
            self.auto_log.append("\n".join(recent_entries))
            
            # Scroll to top since entries are in reverse chronological order
            cursor = self.auto_log.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.auto_log.setTextCursor(cursor)

    # ==========================================================================
    # REAL DATA INTEGRATION PATTERN (UNCHANGED)
    # ==========================================================================
    def apply_proven_real_data_pattern(self):
        """Apply the proven real data integration pattern from temp_WorkingRealDashboard"""
        try:
            # Check if real data is available
            real_data_available = False

            if self.data_file.exists():
                try:
                    with open(self.data_file, "r") as f:
                        data = json.load(f)
                    spy_price = data.get("SPY", {}).get("last", "N/A")
                    self.add_system_log(f"Real data detected - SPY: ${spy_price}")
                    real_data_available = True
                except:
                    self.add_system_log("Real data file exists but couldn't read it")
            else:
                self.add_system_log("No real data detected - will monitor for availability")

            # Apply the appropriate pattern
            if real_data_available:
                self.add_system_log("Applying proven real data patch...")
                self.apply_real_data_patch()
            else:
                self.add_system_log("Starting with simulation - will switch to real data when available")
                self.setup_real_data_monitoring()

        except Exception as e:
            self.add_system_log(f"Error applying real data pattern: {e}")

    def apply_real_data_patch(self):
        """Apply real data patch using the proven working pattern"""
        try:
            # Stop the original simulation timer
            if hasattr(self, "market_worker"):
                worker = self.market_worker
                if hasattr(worker, "update_timer") and worker.update_timer:
                    worker.update_timer.stop()
                    self.add_system_log("Stopped simulation timer")

            # Slow down automation for real data
            if hasattr(self, "automation_timer"):
                self.automation_timer.setInterval(20000)  # 20 seconds instead of 3

            # Start real data updates
            self._real_data_timer = QTimer()
            self._real_data_timer.timeout.connect(self.update_with_real_data)
            self._real_data_timer.start(1000)  # Update every second

            self.real_data_active = True

            # Initial update
            self.update_with_real_data()

            # Update status
            self.update_status_for_real_data()

            # Log success
            self.add_system_log("REAL MARKET DATA ACTIVE - IB Gateway prices")
            self.add_automation_log("Real-time market data from Interactive Brokers")

            self.add_system_log("Real data patch applied successfully!")

        except Exception as e:
            self.add_system_log(f"Error applying real data patch: {e}")

    def setup_real_data_monitoring(self):
        """Setup monitoring for real data to become available"""

        def check_for_real_data():
            """Check if real data becomes available"""
            if self.real_data_active:
                return  # Already using real data

            if self.data_file.exists():
                try:
                    with open(self.data_file, "r") as f:
                        data = json.load(f)

                    if data:
                        self.add_system_log("Real data detected - switching from simulation!")
                        self._check_timer.stop()
                        self.apply_real_data_patch()
                except:
                    pass

        # Check every 5 seconds for real data
        self._check_timer = QTimer()
        self._check_timer.timeout.connect(check_for_real_data)
        self._check_timer.start(5000)

    def update_with_real_data(self):
        """Update dashboard with real market data"""
        try:
            if not self.data_file.exists():
                return

            with open(self.data_file, "r") as f:
                live_data = json.load(f)

            if not live_data:
                return

            # Update symbol widgets directly
            for symbol, data in live_data.items():
                if symbol in self.symbol_widgets:
                    widget = self.symbol_widgets[symbol]

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
            self.update_toolbar_with_real_data(live_data)

        except Exception as e:
            # Suppress frequent errors in logs
            if not hasattr(self, "_error_count"):
                self._error_count = 0

            self._error_count += 1
            if self._error_count <= 5:  # Only show first 5 errors
                self.add_system_log(f"Real data update error: {e}")

    def update_toolbar_with_real_data(self, live_data):
        """Update toolbar indices with real data"""
        try:
            # Update SPX from SPY (SPY * 10)
            if "SPY" in live_data:
                spy_data = live_data["SPY"]

                if hasattr(self, "spx_value"):
                    self.spx_value.setText(f" {spy_data['last'] * 10:.0f}")

                if hasattr(self, "spx_change"):
                    change = spy_data["change"] * 10
                    pct = spy_data["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.spx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.spx_change.setStyleSheet(f"color: {color};")

            # Update NDX from QQQ (QQQ * 35)
            if "QQQ" in live_data:
                qqq_data = live_data["QQQ"]

                if hasattr(self, "ndx_value"):
                    self.ndx_value.setText(f" {qqq_data['last'] * 35:.0f}")

                if hasattr(self, "ndx_change"):
                    change = qqq_data["change"] * 35
                    pct = qqq_data["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.ndx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.ndx_change.setStyleSheet(f"color: {color};")

            # Update DJI from DIA (DIA * 98)
            if "DIA" in live_data:
                dia_data = live_data["DIA"]

                if hasattr(self, "dji_value"):
                    self.dji_value.setText(f" {dia_data['last'] * 98:.0f}")

                if hasattr(self, "dji_change"):
                    change = dia_data["change"] * 98
                    pct = dia_data["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.dji_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.dji_change.setStyleSheet(f"color: {color};")

        except Exception as e:
            pass  # Suppress toolbar update errors

    def update_status_for_real_data(self):
        """Update status indicators for real data - FIXED to not override IB status"""
        try:
            # Don't override IB connection status - only update data status if needed
            # The IB connection status should always show actual IB Gateway connection
            pass  # Real data integration doesn't change IB connection display

        except Exception as e:
            pass  # Not critical

    def refresh_market_data(self):
        """Enhanced refresh market data - callback for refresh icon click"""
        try:
            if self.real_data_active:
                self.add_system_log("Refreshing real market data...")

                # Force immediate update
                self.update_with_real_data()

                self.add_system_log("Real market data refreshed")

            elif self.market_worker:
                self.add_system_log("Refreshing simulation data...")

                if not self.ib_connected:
                    self.add_system_log("Not connected to IB Gateway - using simulation data")

                self.add_system_log("Market data refresh requested")
            else:
                self.add_system_log("Market worker not available")

        except Exception as e:
            self.logger.error(f"Error refreshing market data: {e}")
            self.add_system_log(f"Refresh error: {e}")

    # ==========================================================================
    # UI CREATION METHODS - FIXED TOOLBAR WITH HEARTBEAT
    # ==========================================================================
    def setup_ui(self):
        """Setup the complete UI"""
        self.setWindowTitle("SPYDER - Autonomous Options Trading System")
        self.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

        self.setStyleSheet(
            f"""
            QMainWindow {{
                background-color: {COLORS['background']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-weight: normal;
            }}
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: {COLORS['background']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
            QPushButton {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 8px;
                border-radius: 3px;
                font-weight: normal;
            }}
            QPushButton:hover {{
                background-color: #2a2a2a;
            }}
            QTableWidget {{
                background-color: {COLORS['panel']};
                alternate-background-color: {COLORS['background']};
                color: {COLORS['text']};
                gridline-color: {COLORS['grid']};
                border: 1px solid {COLORS['border']};
                font-size: 11px;
            }}
            QTableWidgetItem {{
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 5px;
                font-size: 10px;
            }}
            QTextEdit {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
            }}
        """
        )

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(3, 3, 3, 3)
        main_layout.setSpacing(3)

        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        content_splitter = QSplitter(Qt.Horizontal)

        left_panel = self.create_left_panel()
        content_splitter.addWidget(left_panel)

        center_panel = self.create_center_panel()
        content_splitter.addWidget(center_panel)

        right_panel = self.create_right_panel()
        content_splitter.addWidget(right_panel)

        content_splitter.setSizes([340, 970, 610])

        main_layout.addWidget(content_splitter)
        central_widget.setLayout(main_layout)

    def create_toolbar(self) -> QWidget:
        """Create top toolbar with FIXED WIDTH status containers and heartbeat monitor"""
        toolbar = QWidget()
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};"
        )

        layout = QHBoxLayout()

        # SPYDER logo on left
        logo_label = QLabel("S P Y D E R")
        try:
            logo_font = QFont("Michroma", 16, QFont.Normal)
        except:
            logo_font = QFont("Arial", 16, QFont.Normal)
        logo_label.setFont(logo_font)
        logo_label.setStyleSheet(f"color: {COLORS['text']}; letter-spacing: 5px;")
        layout.addWidget(logo_label)

        layout.addStretch(7)

        # Center section with market indices
        center_section = QHBoxLayout()
        center_section.setSpacing(15)

        # DJI
        dji_container = QHBoxLayout()
        dji_container.setSpacing(0)
        dji_label = QLabel("DJI:")
        dji_label.setStyleSheet(f"color: {COLORS['text']};")
        dji_container.addWidget(dji_label)

        self.dji_value = QLabel(" 43,900.42")
        self.dji_value.setStyleSheet(f"color: {COLORS['text']};")
        dji_container.addWidget(self.dji_value)

        self.dji_change = QLabel("  +350.35  +2.3%")
        self.dji_change.setStyleSheet(f"color: {COLORS['positive']};")
        dji_container.addWidget(self.dji_change)

        center_section.addLayout(dji_container)
        center_section.addWidget(QLabel("  ||  "))

        # SPX
        spx_container = QHBoxLayout()
        spx_container.setSpacing(0)
        spx_label = QLabel("SPX:")
        spx_label.setStyleSheet(f"color: {COLORS['text']};")
        spx_container.addWidget(spx_label)

        self.spx_value = QLabel(" 6,876.23")
        self.spx_value.setStyleSheet(f"color: {COLORS['text']};")
        spx_container.addWidget(self.spx_value)

        self.spx_change = QLabel("  +45.43  +1.2%")
        self.spx_change.setStyleSheet(f"color: {COLORS['positive']};")
        spx_container.addWidget(self.spx_change)

        center_section.addLayout(spx_container)
        center_section.addWidget(QLabel("  ||  "))

        # NDX
        ndx_container = QHBoxLayout()
        ndx_container.setSpacing(0)
        ndx_label = QLabel("NDX:")
        ndx_label.setStyleSheet(f"color: {COLORS['text']};")
        ndx_container.addWidget(ndx_label)

        self.ndx_value = QLabel(" 20,275.62")
        self.ndx_value.setStyleSheet(f"color: {COLORS['text']};")
        ndx_container.addWidget(self.ndx_value)

        self.ndx_change = QLabel("  +45.23  +0.78%")
        self.ndx_change.setStyleSheet(f"color: {COLORS['positive']};")
        ndx_container.addWidget(self.ndx_change)

        center_section.addLayout(ndx_container)

        layout.addLayout(center_section)
        layout.addStretch(3)

        # RIGHT SECTION - FIXED WIDTH CONTAINERS WITH HEARTBEAT
        right_section = QHBoxLayout()
        right_section.setSpacing(10)

        right_section.addSpacing(20)
        right_section.addWidget(QLabel(" | "))

        # IB Connection Status (Left Box) - FIXED WIDTH
        self.ib_status_container = QWidget()
        self.ib_status_container.setMinimumWidth(190)
        self.ib_status_container.setMaximumWidth(190)
        self.ib_status_container.setCursor(Qt.PointingHandCursor)
        self.ib_status_container.setToolTip("Click to connect/disconnect IB Gateway")
        self.ib_status_container.setStyleSheet(
            """
            QWidget:hover {
                background-color: #2a2a2a;
                border-radius: 3px;
                padding: 2px;
            }
        """
        )
        ib_status_layout = QHBoxLayout()
        ib_status_layout.setContentsMargins(10, 3, 8, 3)
        ib_status_layout.setSpacing(6)

        self.ib_connection_dot = QLabel("●")
        self.ib_connection_dot.setStyleSheet(
            "color: " + COLORS["negative"] + f"; font-size: 14px;"
        )
        ib_status_layout.addWidget(self.ib_connection_dot)

        self.ib_connection_label = QLabel("IB DISCONNECTED")
        self.ib_connection_label.setStyleSheet(
            "color: " + COLORS["negative"] + f"; font-size: 14px;"
        )
        ib_status_layout.addWidget(self.ib_connection_label)

        self.ib_status_container.setLayout(ib_status_layout)
        self.ib_status_container.mousePressEvent = self.toggle_ib_connection

        # HEARTBEAT MONITOR
        self.heartbeat_container = QWidget()
        self.heartbeat_container.setMinimumWidth(40)
        self.heartbeat_container.setMaximumWidth(40)
        self.heartbeat_container.setToolTip(
            "Connection heartbeat monitor\nGreen Connected  Blue Checking  Red Disconnected"
        )
        heartbeat_layout = QHBoxLayout()
        heartbeat_layout.setContentsMargins(2, 3, 2, 3)
        heartbeat_layout.setSpacing(0)

        self.heartbeat_icon = QLabel("💔")  # Start with red broken heart (disconnected)
        self.heartbeat_icon.setStyleSheet(
            "color: " + COLORS["negative"] + f"; font-size: 16px;"
        )
        self.heartbeat_icon.setAlignment(Qt.AlignCenter)
        heartbeat_layout.addWidget(self.heartbeat_icon)

        self.heartbeat_container.setLayout(heartbeat_layout)

        # Data Status (Right Box with Simulation Toggle)
        self.data_status_container = QWidget()
        self.data_status_container.setMinimumWidth(240)
        self.data_status_container.setMaximumWidth(240)
        self.data_status_container.setToolTip("Current data source and status")
        data_status_layout = QHBoxLayout()
        data_status_layout.setContentsMargins(10, 6, 8, 6)
        data_status_layout.setSpacing(6)

        self.data_status_dot = QLabel("●")
        self.data_status_dot.setStyleSheet(
            "color: " + COLORS["warning"] + f"; font-size: 14px;"
        )
        self.data_status_dot.setAlignment(Qt.AlignVCenter)
        data_status_layout.addWidget(self.data_status_dot)

        self.data_status_label = QLabel("END-OF-DAY DATA")
        self.data_status_label.setStyleSheet(
            "color: " + COLORS["warning"] + f"; font-size: 14px;"
        )
        self.data_status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        data_status_layout.addWidget(self.data_status_label)

        # Add stretch to push simulation button to the right
        data_status_layout.addStretch()

        # Simulation Toggle Button (Blue) - Only visible when IB disconnected
        self.simulation_toggle = QLabel("🔵")
        self.simulation_toggle.setCursor(Qt.PointingHandCursor)
        self.simulation_toggle.setToolTip(
            "CLICK TO DISPLAY SIMULATED DATA WHEN IB IS DISCONNECTED"
        )
        self.simulation_toggle.setStyleSheet(f"font-size: 14px;")
        self.simulation_toggle.setAlignment(Qt.AlignVCenter)
        self.simulation_toggle.mousePressEvent = self.toggle_simulation_mode
        self.simulation_toggle.setVisible(True)  # Start visible since we start disconnected
        data_status_layout.addWidget(self.simulation_toggle)

        self.data_status_container.setLayout(data_status_layout)

        # Add all containers to right section
        right_section.addStretch(1)
        right_section.addWidget(self.ib_status_container)
        right_section.addSpacing(3)
        right_section.addWidget(self.heartbeat_container)
        right_section.addSpacing(3)
        right_section.addWidget(self.data_status_container)
        right_section.addWidget(QLabel(" | "))

        # DATE/TIME
        self.datetime_label = QLabel(datetime.now().strftime("%Y-%m-%d   %H:%M:%S  ET"))
        self.datetime_label.setStyleSheet("font-size: 14px;")
        right_section.addWidget(self.datetime_label)

        layout.addLayout(right_section)

        toolbar.setLayout(layout)
        return toolbar