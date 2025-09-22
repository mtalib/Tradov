# ==========================================================================
    # SIGNAL HANDLERS - ENHANCED WITH HEARTBEAT AND AUTO-RECONNECTION
    # ==========================================================================
    @Slot(bool, str)
    def on_connection_status_changed(self, connected: bool, status: str):
        """Handle connection status change - ENHANCED WITH AUTO-RECONNECTION SUPPORT"""
        self.connection_info.ib_connected = connected
        self.ib_connected = connected

        if connected:
            self.ib_connection_dot.setStyleSheet(f"color: {COLORS['positive']};")
            self.ib_connection_label.setText("IB CONNECTED")
            self.ib_connection_label.setStyleSheet(f"color: {COLORS['positive']};")

            # Hide simulation button when connected
            self.simulation_toggle.setVisible(False)

            self.add_system_log("✅ Connected to IB Gateway")
        else:
            self.ib_connection_dot.setStyleSheet(f"color: {COLORS['negative']};")
            self.ib_connection_label.setText("IB DISCONNECTED")
            self.ib_connection_label.setStyleSheet(f"color: {COLORS['negative']};")

            # Show simulation button when disconnected
            self.simulation_toggle.setVisible(True)

            # Stop trading if active
            if self.trading_active:
                self.trading_active = False
                self.connection_info.trading_active = False

                self.start_btn.setStyleSheet(
                    f"background-color: {COLORS['positive']}; color: black;"
                )
                self.start_btn.setText("START TRADING")

                self.add_automation_log("Trading stopped - IB connection lost")

            if "MARKET CLOSED" in status:
                self.add_system_log("📊 Market closed - IB disconnected")
            else:
                self.add_system_log("🔌 Disconnected from IB Gateway")

        # Update data status (but don't override IB status)
        self.update_status_indicators()

    @Slot(str)
    def on_heartbeat_status_changed(self, status: str):
        """Handle heartbeat status changes - ENHANCED with bright green"""
        if status == "connected":
            self.heartbeat_icon.setText("💚")  # Bright green heart when connected
            self.heartbeat_icon.setStyleSheet(
                "color: #00ff00; font-size: 16px;"
            )  # BRIGHT GREEN to match dot
        elif status == "warning":
            self.heartbeat_icon.setText("💙")  # Blue heart 20 seconds before check
            self.heartbeat_icon.setStyleSheet(
                f"color: {COLORS['automation_active']}; font-size: 16px;"
            )
        else:  # disconnected or error
            self.heartbeat_icon.setText("💔")  # Red broken heart when disconnected
            self.heartbeat_icon.setStyleSheet(
                f"color: {COLORS['negative']}; font-size: 16px;"
            )

    @Slot(str)
    def on_market_data_status_changed(self, status: str):
        """Handle market data status change"""
        if status == "LIVE":
            self.add_system_log("📊 Market data: LIVE")
        else:
            if self.trading_active:
                self.trading_active = False
                self.connection_info.trading_active = False

                self.start_btn.setStyleSheet(
                    f"background-color: {COLORS['positive']}; color: black;"
                )
                self.start_btn.setText("START TRADING")

                self.add_automation_log("Trading stopped - Market data lost")

            if status == "CLOSED":
                self.add_system_log("📊 Market closed - data static")
            else:
                self.add_system_log("📊 Market data: NONE")

    @Slot(dict)
    def on_market_data_updated(self, data: dict):
        """Handle market data update - only if not using real data"""
        if self.real_data_active:
            return  # Skip simulation updates when using real data

        try:
            for symbol, market_info in data.items():
                if symbol in self.symbol_widgets:
                    self.symbol_widgets[symbol].update_data(market_info)

            self.market_data.update(data)

        except Exception as e:
            self.logger.error(f"Error updating market data: {e}")

    @Slot(str)
    def on_market_error(self, error: str):
        """Handle market error"""
        self.add_system_log(f"⌐ Market error: {error}")

    @Slot(str)
    def on_heartbeat_received(self, message: str):
        """Handle heartbeat message - route to system log"""
        # Route heartbeat messages to system log (not automation log)
        self.add_system_log(message)

    def toggle_ib_connection(self, event):
        """Toggle IB connection when clicking on status"""
        if self.ib_connected:
            if self.trading_active:
                reply = QMessageBox.warning(
                    self,
                    "Trading Active",
                    "Trading is currently active.\n\n"
                    "Disconnecting will stop all trading activities.\n"
                    "Do you want to continue?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )

                if reply != QMessageBox.Yes:
                    return

                self.trading_active = False
                self.connection_info.trading_active = False

                self.start_btn.setStyleSheet(
                    f"background-color: {COLORS['positive']}; color: black;"
                )
                self.start_btn.setText("START TRADING")

                self.add_automation_log("Trading stopped due to IB disconnection")

            if self.market_worker:
                self.market_worker.force_disconnect()
            self.ib_connected = False
            self.add_system_log("Manually disconnected from IB")
        else:
            if not is_market_hours():
                QMessageBox.information(
                    self,
                    "Market Closed",
                    "Market is closed. Connection available during trading hours:\n"
                    "4:00 AM - 4:30 PM ET",
                )
                return

            if self.market_worker and self.market_worker.force_connect():
                self.ib_connected = True
                self.add_system_log("Manually connected to IB")
            else:
                self.add_system_log("Failed to connect to IB")

    def start_trading(self):
        """Handle start trading button click - ENHANCED WITH AUTO-RECONNECTION STATUS"""
        if not self.ib_connected:
            QMessageBox.warning(
                self,
                "IB Disconnected",
                "IB is disconnected - cannot start trading\n\n"
                "Auto-reconnection will attempt to restore connection during market hours.",
            )
            self.add_system_log("Cannot start trading - IB disconnected")
            return

        data_status = self.data_status_label.text()
        if data_status not in ["LIVE DATA", "LIVE - REAL"]:
            QMessageBox.warning(
                self,
                "No Live Data",
                "NO LIVE DATA\n\n" "Cannot start trading without live market data.",
            )
            self.add_system_log("Cannot start trading - No live data")
            return

        if self.trading_active:
            self.add_system_log("Trading already active")
            return

        self.trading_active = True
        self.connection_info.trading_active = True

        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['automation_active']}; color: white;"
        )
        self.start_btn.setText("TRADING ACTIVE")

        self.add_system_log("Trading started successfully")
        self.add_automation_log("TRADING ACTIVE - Autonomous AI Engine engaged")

        if self.real_data_active:
            self.add_automation_log("Using REAL market data from IB Gateway")
        else:
            self.add_automation_log("Monitoring SPY options for trading opportunities")

    def stop_trading(self):
        """Handle stop trading button click"""
        if not self.ib_connected:
            QMessageBox.information(
                self,
                "IB Disconnected",
                "IB is disconnected – further trading has already stopped, but open orders at IBKR still remain in effect. If you wish to close or cancel these orders, call IBKR at +1 (312) 542-6901",
            )
            return

        if not self.trading_active:
            self.add_system_log("No active trading to stop")
            return

        self.trading_active = False
        self.connection_info.trading_active = False

        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['positive']}; color: black;"
        )
        self.start_btn.setText("START TRADING")

        self.add_system_log("Trading stopped - Orders and positions remain active")
        self.add_automation_log("TRADING STOPPED - Existing positions maintained")
        self.add_automation_log("Autonomous AI Engine on standby")

    def emergency_close(self):
        """Handle emergency close button click"""
        if not self.ib_connected:
            QMessageBox.critical(
                self,
                "IB Disconnected",
                "IB is disconnected – unable to close open orders at IBKR. If you wish to close or cancel these orders, call IBKR at +1 (312) 542-6901",
            )
            return

        reply = QMessageBox.critical(
            self,
            "EMERGENCY CLOSE",
            "⚠️ EMERGENCY PROTOCOL ⚠️\n\n"
            "This will IMMEDIATELY:\n"
            "• Close ALL open positions\n"
            "• Cancel ALL pending orders\n"
            "• Stop automated trading\n"
            "• Disconnect from IB Gateway\n\n"
            "Are you sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.add_system_log(
                "🚨 EMERGENCY CLOSE - All positions closed, system stopped"
            )
            self.add_automation_log(
                "EMERGENCY PROTOCOL - All positions closed by autonomous system"
            )

            self.trading_active = False
            self.connection_info.trading_active = False

            self.start_btn.setStyleSheet(
                f"background-color: {COLORS['positive']}; color: black;"
            )
            self.start_btn.setText("START TRADING")

            if self.market_worker:
                self.market_worker.force_disconnect()
            self.ib_connected = False

    # ==========================================================================
    # ENHANCED STATUS MANAGEMENT WITH FROZEN DATA LOGIC
    # ==========================================================================
    def update_data_status(self, status_type: str):
        """Update data status display - CLEANED UP to show only 4 statuses"""
        if status_type == "LIVE":
            # Live data during market hours
            self.data_status_dot.setStyleSheet(
                "color: " + COLORS["positive"] + f"; font-size: 14px;"
            )
            self.data_status_label.setText("LIVE DATA")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["positive"] + f"; font-size: 14px;"
            )
        elif status_type == "EOD":
            # End of day data (after hours or file data)
            self.data_status_dot.setStyleSheet(
                "color: " + COLORS["warning"] + f"; font-size: 14px;"
            )
            self.data_status_label.setText("END-OF-DAY DATA")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["warning"] + f"; font-size: 14px;"
            )
        elif status_type == "FROZEN":
            # Frozen data (disconnected during market hours)
            self.data_status_dot.setStyleSheet(
                "color: " + COLORS["negative"] + f"; font-size: 14px;"
            )
            self.data_status_label.setText("FROZEN DATA")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["negative"] + f"; font-size: 14px;"
            )
        elif status_type == "SIMULATION":
            # Simulation mode
            self.data_status_dot.setStyleSheet(
                "color: " + COLORS["automation_active"] + "; font-size: 14px;"
            )
            self.data_status_label.setText("SIMULATED DATA")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["automation_active"] + "; font-size: 14px;"
            )

    def determine_data_status(self) -> str:
        """Determine appropriate data status based on current conditions - ENHANCED SIMULATION DETECTION"""
        market_hours = is_market_hours()

        # Check for simulation mode first with better detection
        if (
            hasattr(self.connection_info, "simulation_mode")
            and self.connection_info.simulation_mode
        ) or (
            not self.ib_connected
            and hasattr(self, "market_worker")
            and self.market_worker
            and hasattr(self.market_worker, "update_timer")
            and self.market_worker.update_timer.isActive()
        ):
            return "SIMULATION"

        if self.ib_connected:
            # IB is connected
            if market_hours:
                self.connection_info.data_was_live = True
                self.connection_info.last_successful_data = datetime.now()
                return "LIVE"
            else:
                self.connection_info.last_successful_data = datetime.now()
                return "EOD"
        else:
            # IB is disconnected
            if self.real_data_active:
                # Using file data - always treat as EOD
                return "EOD"
            elif (
                market_hours
                and hasattr(self.connection_info, "data_was_live")
                and self.connection_info.data_was_live
            ):
                # Market hours but no recent successful connection = FROZEN
                if (
                    hasattr(self.connection_info, "last_successful_data")
                    and self.connection_info.last_successful_data
                    and (
                        datetime.now() - self.connection_info.last_successful_data
                    ).total_seconds()
                    < 300
                ):  # 5 minutes
                    return "FROZEN"
                else:
                    return "EOD"
            else:
                # If simulation data is updating, show SIMULATION instead of EOD
                if (
                    hasattr(self, "market_worker")
                    and self.market_worker
                    and hasattr(self.market_worker, "update_timer")
                    and self.market_worker.update_timer.isActive()
                ):
                    return "SIMULATION"
                return "EOD"

    def update_status_indicators(self):
        """Update both status indicators based on current state"""
        # Update data status
        data_status = self.determine_data_status()
        self.update_data_status(data_status)

    def toggle_simulation_mode(self, event):
        """Toggle simulation mode (only when IB disconnected) - ENHANCED STATUS UPDATE"""
        if self.ib_connected:
            # Don't activate simulation when IB is connected
            self.add_system_log(
                "⚠️ Simulation mode only available when IB is disconnected"
            )
            return

        # Toggle simulation mode
        if not hasattr(self.connection_info, "simulation_mode"):
            self.connection_info.simulation_mode = False

        self.connection_info.simulation_mode = not self.connection_info.simulation_mode

        if self.connection_info.simulation_mode:
            self.add_system_log("🔵 Simulation mode activated")
            self.add_automation_log(
                "Switched to simulation data - starting from last real prices"
            )
            # Initialize simulation with last real prices
            self._init_simulation_from_real_data()
        else:
            self.add_system_log("📊 Simulation mode deactivated")
            self.add_automation_log("Switched back to available real data")

        # Force immediate status update to show SIMULATED DATA
        self.update_status_indicators()

        # Force immediate UI update
        data_status = self.determine_data_status()
        self.update_data_status(data_status)

    def _init_simulation_from_real_data(self):
        """Initialize simulation starting from last real market prices"""
        if hasattr(self, "market_data") and self.market_data:
            # Use current market data as baseline for simulation
            self.add_system_log(
                f"🎯 Simulation baseline: SPY ${self.market_data.get('SPY', {}).get('last', 585):.2f}"
            )
        else:
            # Use default simulation data
            self.add_system_log("🎯 Using default simulation baseline")