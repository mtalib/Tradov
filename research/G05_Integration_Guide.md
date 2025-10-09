# SpyderG05 Gateway Integration - In-Place Modifications

## Strategy: Modify Your Existing G05 File Directly

Keep your complete working `SpyderG05_TradingDashboard.py` file and make these **surgical changes** in VS Code.

---

## CHANGE 1: Add Gateway Imports (after line 193)

**Location:** After the Prometheus imports block (~line 193)

```python
# ==============================================================================
# NEW IMPORTS FOR GATEWAY AUTOMATION
# ==============================================================================
try:
    from SpyderG_GUI.SpyderG14_GatewayControlPanel import (
        create_gateway_dock_widget,
        GatewayControlPanel
    )
    gateway_panel_available = True
    print("✅ Gateway Control Panel available")
except ImportError:
    gateway_panel_available = False
    print("⚠️ Gateway Control Panel not available")

try:
    from SpyderG_GUI.SpyderG15_ClientConnectionManager import (
        ClientConnectionManager,
        ClientStatus
    )
    client_manager_available = True
    print("✅ Client Connection Manager available")
except ImportError:
    client_manager_available = False
    print("⚠️ Client Connection Manager not available")
```

---

## CHANGE 2: Add "connecting" Color (in COLORS dict, ~line 270)

**Location:** Inside the `COLORS` dictionary, add this line after `"automation_active"`

```python
    "automation_active": "#00b8d4",
    "connecting": "#00b8d4",  # NEW: For connecting status
    "grid": "#2a2a2a",
```

---

## CHANGE 3: Add Gateway Attributes to `__init__` (after line 640)

**Location:** In `__init__` method, after the `self._last_gateway_search_log = ""` line

```python
        self._last_gateway_search_log = ""

        # NEW: Gateway control integration
        self.gateway_dock = None
        self.gateway_panel = None
        self.client_manager = None
        self.gateway_control_enabled = False  # User can toggle this
        self.gateway_control_btn = None  # NEW: Gateway control button

        # Try to connect to real Prometheus collector if available
```

---

## CHANGE 4: Update Module Docstring (top of file, ~line 20)

**Location:** Add these lines to the FEATURES section in the module docstring

```python
FEATURES:
    • Automatic real data detection and seamless switching
    • Simulation fallback with monitoring for real data availability
    • Professional signal monitor with 12 indicators including HMM/SKEW
    • Unified Prometheus Metrics table (IB Clients 1-10 + Internal Modules)
    • Market hours awareness and connection health monitoring
    • Custom metrics integration (GEX/DEX/OGL/DIX/SWAN)
    • Enhanced P&L tracking and risk monitoring
    • Professional dark theme with traffic light indicators
    • 30-second heartbeat connection monitoring with visual indicator
    • 🔧 GATEWAY CONTROL: Integrated control panel for Gateway and 8 clients
    • 🔗 CLIENT MANAGEMENT: Sequential connection with proper delays
    • ✅ STATUS UPDATES: Real-time client status in Prometheus table

NEW GATEWAY FEATURES:
    • Dockable Gateway Control Panel (🔧 button in Prometheus header)
    • Automated Gateway launch and client connection
    • 8-client sequential connection with proper delays
    • Client status indicators in Prometheus table (clickable to reconnect)
    • Real-time connection progress tracking
    • Individual client health monitoring
```

---

## CHANGE 5: Replace `create_unified_prometheus_metrics()` Method

**Location:** Find the entire `create_unified_prometheus_metrics()` method (~line 2800)

**Action:** Replace the ENTIRE method with this updated version:

```python
    def create_unified_prometheus_metrics(self) -> QWidget:
        """Create the unified Prometheus Metrics table (8 clients in 4x2 grid + 2 empty rows)"""
        container = QWidget()
        container.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLORS["panel"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 5px;
            }}
        """
        )
        container.setFixedHeight(200)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(2)

        # Title with Gateway button
        title_layout = QHBoxLayout()
        
        title_label = QLabel("PROMETHEUS METRICS MONITOR")
        title_label.setStyleSheet(
            f"""
            color: {COLORS["text"]};
            font-size: 14px;
            font-weight: normal;
            padding-bottom: 1px;
        """
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # Gateway Control Button
        self.gateway_control_btn = QPushButton("🔧")
        self.gateway_control_btn.setFixedSize(30, 30)
        self.gateway_control_btn.setToolTip("Show/Hide Gateway Control Panel")
        self.gateway_control_btn.clicked.connect(self.toggle_gateway_control)
        title_layout.addWidget(self.gateway_control_btn)
        
        main_layout.addLayout(title_layout)
        main_layout.addSpacing(8)

        # Create the 6x4 grid (5 data rows + 1 header row)
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setContentsMargins(0, 0, 0, 0)

        # Column headers
        headers = [
            "SYSTEM HEALTH",
            "IB CLIENTS 1-4",
            "IB CLIENTS 5-8",
            "INTERNAL MODULES",
        ]
        for col, header in enumerate(headers):
            header_label = QLabel(header)
            header_label.setStyleSheet(
                f"""
                color: {COLORS["cyan"]};
                font-size: 13px;
                font-weight: normal;
                padding: 2px;
                border-bottom: 1px solid {COLORS["border"]};
            """
            )
            header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(header_label, 0, col)

        # System Components (Column 1)
        components = [
            ("RISK MANAGER", "●"),
            ("MARKET DATA", "●"),
            ("STRATEGY ENGINE", "●"),
            ("ML MODELS", "●"),
            ("DATABASE", "●"),
        ]

        for row, (name, status) in enumerate(components, start=1):
            component_widget = QWidget()
            component_layout = QHBoxLayout()
            component_layout.setContentsMargins(5, 1, 5, 1)
            component_layout.setSpacing(3)

            indicator = QLabel(status)
            indicator.setStyleSheet(
                "color: " + COLORS["positive"] + f"; font-size: 14px;"
            )
            component_layout.addWidget(indicator)

            label = QLabel(name)
            label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
            component_layout.addWidget(label)
            component_layout.addStretch()

            component_widget.setLayout(component_layout)
            self.system_components[name] = indicator
            grid.addWidget(component_widget, row, 0)

        # IB Clients 1-4 (Column 2) - UPDATED TO 4 CLIENTS + 1 EMPTY
        client_1_4_types = ["Orders", "Admin", "Core", "Options"]
        for row in range(1, 6):  # 5 rows total
            if row <= 4:  # First 4 rows are clients
                client_widget = QWidget()
                client_layout = QHBoxLayout()
                client_layout.setContentsMargins(5, 1, 5, 1)
                client_layout.setSpacing(3)

                indicator = QLabel("●")
                indicator.setStyleSheet(
                    "color: " + COLORS["neutral"] + f"; font-size: 14px;"
                )
                indicator.setCursor(Qt.CursorShape.PointingHandCursor)
                indicator.setToolTip(f"Click to connect Client {row}")
                client_layout.addWidget(indicator)

                label = QLabel(f"CLIENT {row}: {client_1_4_types[row - 1]}")
                label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
                client_layout.addWidget(label)
                client_layout.addStretch()

                client_widget.setLayout(client_layout)
                
                # Store indicator for status updates
                self.client_indicators[f"CLIENT {row}"] = indicator
                
                # Make clickable for reconnection
                indicator.mousePressEvent = lambda e, cid=row: self.reconnect_client(cid)
                
                grid.addWidget(client_widget, row, 1)
            else:
                # Row 5 is empty
                empty_widget = QWidget()
                grid.addWidget(empty_widget, row, 1)

        # IB Clients 5-8 (Column 3) - UPDATED TO 4 CLIENTS + 1 EMPTY
        client_5_8_types = ["Volatility", "Major ETFs", "Extended", "International"]
        for row in range(1, 6):  # 5 rows total
            if row <= 4:  # First 4 rows are clients
                client_num = row + 4  # Client 5, 6, 7, 8
                client_widget = QWidget()
                client_layout = QHBoxLayout()
                client_layout.setContentsMargins(5, 1, 5, 1)
                client_layout.setSpacing(3)

                indicator = QLabel("●")
                indicator.setStyleSheet(
                    "color: " + COLORS["neutral"] + f"; font-size: 14px;"
                )
                indicator.setCursor(Qt.CursorShape.PointingHandCursor)
                indicator.setToolTip(f"Click to connect Client {client_num}")
                client_layout.addWidget(indicator)

                label = QLabel(f"CLIENT {client_num}: {client_5_8_types[row - 1]}")
                label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
                client_layout.addWidget(label)
                client_layout.addStretch()

                client_widget.setLayout(client_layout)
                
                # Store indicator for status updates
                self.client_indicators[f"CLIENT {client_num}"] = indicator
                
                # Make clickable for reconnection
                indicator.mousePressEvent = lambda e, cid=client_num: self.reconnect_client(cid)
                
                grid.addWidget(client_widget, row, 2)
            else:
                # Row 5 is empty
                empty_widget = QWidget()
                grid.addWidget(empty_widget, row, 2)

        # Internal Modules (Column 4) - UNCHANGED
        internal_modules = [
            ("Custom Metrics", "custom_metrics"),
            ("Risk Calculator", "risk_calc"),
            ("ML Engine", "ml_engine"),
            ("Options Analyzer", "options"),
            ("Performance", "performance"),
        ]

        for row, (module_name, module_key) in enumerate(internal_modules, start=1):
            module_widget = QWidget()
            module_layout = QHBoxLayout()
            module_layout.setContentsMargins(5, 1, 5, 1)
            module_layout.setSpacing(3)

            indicator = QLabel("●")
            if module_key == "custom_metrics":
                indicator.setStyleSheet(
                    "color: " + COLORS["warning"] + f"; font-size: 14px;"
                )
            else:
                indicator.setStyleSheet(
                    "color: " + COLORS["positive"] + f"; font-size: 14px;"
                )
            module_layout.addWidget(indicator)

            label = QLabel(module_name)
            label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
            module_layout.addWidget(label)
            module_layout.addStretch()

            module_widget.setLayout(module_layout)
            if not hasattr(self, "internal_module_indicators"):
                self.internal_module_indicators = {}
            self.internal_module_indicators[module_key] = indicator
            grid.addWidget(module_widget, row, 3)

        # Set equal column stretch
        for col in range(4):
            grid.setColumnStretch(col, 1)

        # Set row heights
        for row in range(1, 6):
            grid.setRowMinimumHeight(row, 24)

        main_layout.addLayout(grid)
        main_layout.addStretch()

        container.setLayout(main_layout)
        return container
```

---

## CHANGE 6: Add New Gateway Control Methods

**Location:** Add these 4 NEW methods right BEFORE the `closeEvent()` method (~line 3900)

```python
    # ==========================================================================
    # GATEWAY CONTROL INTEGRATION
    # ==========================================================================
    def toggle_gateway_control(self):
        """Toggle Gateway Control Panel visibility"""
        if not gateway_panel_available:
            QMessageBox.information(
                self,
                "Gateway Control",
                "Gateway Control Panel is not available.\n\n"
                "This feature requires SpyderG14_GatewayControlPanel module."
            )
            return
        
        if self.gateway_dock is None:
            # Create dock widget
            self.gateway_dock = create_gateway_dock_widget(self)
            self.gateway_panel = self.gateway_dock.widget()
            
            # Connect signals
            self.gateway_panel.clients_connected.connect(self.on_gateway_clients_connected)
            
            # Add to main window
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.gateway_dock)
            
            self.add_system_log("🔧 Gateway Control Panel opened")
        else:
            # Toggle visibility
            if self.gateway_dock.isVisible():
                self.gateway_dock.hide()
                self.add_system_log("🔧 Gateway Control Panel hidden")
            else:
                self.gateway_dock.show()
                self.add_system_log("🔧 Gateway Control Panel shown")

    @Slot(int)
    def on_gateway_clients_connected(self, count: int):
        """Handle clients connected signal from Gateway panel"""
        self.add_system_log(f"✅ {count}/8 clients connected via Gateway panel")
        
        # Update client indicators in Prometheus table
        if self.gateway_panel and self.gateway_panel.client_thread:
            manager = self.gateway_panel.client_thread.manager
            if manager:
                for client_id in range(1, 9):
                    status = manager.get_client_status(client_id)
                    if status:
                        self.update_client_indicator(client_id, status.status)

    def update_client_indicator(self, client_id: int, status):
        """Update client indicator in Prometheus table"""
        indicator_key = f"CLIENT {client_id}"
        
        if indicator_key in self.client_indicators:
            indicator = self.client_indicators[indicator_key]
            
            if status == ClientStatus.CONNECTED:
                indicator.setStyleSheet(f"color: {COLORS['positive']}; font-size: 14px;")
                indicator.setToolTip(f"Client {client_id}: Connected")
            elif status == ClientStatus.CONNECTING:
                indicator.setStyleSheet(f"color: {COLORS['connecting']}; font-size: 14px;")
                indicator.setToolTip(f"Client {client_id}: Connecting...")
            elif status == ClientStatus.ERROR:
                indicator.setStyleSheet(f"color: {COLORS['negative']}; font-size: 14px;")
                indicator.setToolTip(f"Client {client_id}: Error")
            else:  # DISCONNECTED
                indicator.setStyleSheet(f"color: {COLORS['neutral']}; font-size: 14px;")
                indicator.setToolTip(f"Client {client_id}: Click to connect")

    def reconnect_client(self, client_id: int):
        """Reconnect a specific client when indicator is clicked"""
        if not gateway_panel_available or not self.gateway_panel:
            self.add_system_log(f"⚠️ Gateway panel not available to reconnect Client {client_id}")
            return
        
        if not self.gateway_panel.gateway_running:
            QMessageBox.warning(
                self,
                "Gateway Not Running",
                "Please start Gateway first before connecting clients."
            )
            return
        
        self.add_system_log(f"🔄 Reconnecting Client {client_id}...")
        
        # Use the client manager from gateway panel
        if self.gateway_panel.client_thread and self.gateway_panel.client_thread.manager:
            manager = self.gateway_panel.client_thread.manager
            
            # Update indicator to connecting
            self.update_client_indicator(client_id, ClientStatus.CONNECTING)
            
            # Reconnect in background
            import threading
            def reconnect_thread():
                success = manager.reconnect_client(client_id)
                if success:
                    self.add_system_log(f"✅ Client {client_id} reconnected")
                else:
                    self.add_system_log(f"❌ Client {client_id} reconnection failed")
            
            thread = threading.Thread(target=reconnect_thread, daemon=True)
            thread.start()
```

---

## CHANGE 7: Update `closeEvent()` Method

**Location:** Find the `closeEvent()` method (~line 3950)

**Action:** Add this code at the VERY BEGINNING of the try block (right after `try:`):

```python
    def closeEvent(self, event):
        """Enhanced close event handler with real data cleanup, heartbeat monitoring, and Gateway control"""
        try:
            # NEW: Cleanup Gateway control
            if self.gateway_panel:
                if self.gateway_panel.client_thread:
                    self.gateway_panel.client_thread.stop()
                    self.gateway_panel.client_thread.wait(2000)
                
                if self.gateway_panel.gateway_thread:
                    self.gateway_panel.gateway_thread.stop()
                    self.gateway_panel.gateway_thread.wait(2000)
            
            # ... rest of existing closeEvent code continues here ...
```

---

## CHANGE 8: Update Main Function Banner (optional)

**Location:** In the `main()` function (~line 4050), update the banner:

```python
    print("=" * 70)
    print("🔥 SPYDER G05 - ENHANCED DASHBOARD WITH GATEWAY CONTROL")
    print("=" * 70)
    print("🔧 Gateway Control Panel integration")
    print("🔗 8-client connection management")
    print("💔💚💙 30-second heartbeat monitoring")
    print("📊 Clean 4-status data display")
    print("🎯 Clickable client indicators for reconnection")
    print("=" * 70)
```

---

## Summary of Changes

1. ✅ **Add Gateway imports** (2 new import blocks)
2. ✅ **Add "connecting" color** (1 line in COLORS dict)
3. ✅ **Add Gateway attributes to __init__** (5 new attributes)
4. ✅ **Update module docstring** (add Gateway features)
5. ✅ **Replace `create_unified_prometheus_metrics()`** (entire method with 8 clients + Gateway button)
6. ✅ **Add 4 new Gateway methods** (toggle, on_connected, update_indicator, reconnect)
7. ✅ **Update `closeEvent()`** (add Gateway cleanup)
8. ✅ **Update main banner** (optional cosmetic)

## Testing After Changes

```bash
python SpyderG05_TradingDashboard.py
```

Expected results:
- Dashboard opens normally
- 🔧 button appears in Prometheus Metrics header
- Click 🔧 → Gateway Control Panel opens as dockable widget
- Client indicators show in Prometheus table (8 clients in 4x2 grid)
- Click indicators → reconnect individual clients

All changes are **backward compatible** - dashboard works perfectly even if G14/G15 modules aren't available.
