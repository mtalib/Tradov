def create_right_panel(self) -> QWidget:
        """Create right panel with controls and metrics"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(5, 5, 5, 5)

        # Control buttons
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("START TRADING")
        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['positive']}; color: black;"
        )
        self.start_btn.setToolTip("Start automated trading")
        self.start_btn.clicked.connect(self.start_trading)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("STOP TRADING")
        self.stop_btn.setStyleSheet(f"background-color: {COLORS['warning']};")
        self.stop_btn.setToolTip("Stop trading but keep orders and positions")
        self.stop_btn.clicked.connect(self.stop_trading)
        button_layout.addWidget(self.stop_btn)

        self.emergency_btn = QPushButton("EMERGENCY CLOSE")
        self.emergency_btn.setStyleSheet(f"background-color: {COLORS['negative']};")
        self.emergency_btn.setToolTip(
            "Close all orders and positions, stop trading, and disconnect from IB"
        )
        self.emergency_btn.clicked.connect(self.emergency_close)
        button_layout.addWidget(self.emergency_btn)

        layout.addLayout(button_layout)

        # Account info
        account_group = QGroupBox("")
        account_layout = QVBoxLayout()

        table_widget = QWidget()
        table_widget.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; padding: 5px;"
        )
        table_layout = QGridLayout()
        table_layout.setContentsMargins(8, -2, 8, 8)
        table_layout.setHorizontalSpacing(10)
        table_layout.setVerticalSpacing(6)

        cell_style = f"padding: 5px 10px; background-color: {COLORS['background']}; border: 1px solid {COLORS['border']};"

        # Account row
        account_label = QLabel("ACCOUNT")
        account_label.setStyleSheet(cell_style)
        table_layout.addWidget(account_label, 0, 0)

        account_value = QLabel("DU5361048")
        account_value.setStyleSheet(cell_style)
        table_layout.addWidget(account_value, 0, 1)

        mode_label = QLabel("MODE: PAPER")
        mode_label.setStyleSheet(cell_style + f"color: {COLORS['orange']};")
        table_layout.addWidget(mode_label, 0, 2)

        self.risk_params_btn = QPushButton("RISK LEVELS")
        self.risk_params_btn.setStyleSheet(f"background-color: #0066CC; color: white;")
        self.risk_params_btn.setToolTip(
            "Configure global and strategy-specific risk parameters"
        )
        self.risk_params_btn.clicked.connect(self.show_risk_parameters)
        table_layout.addWidget(self.risk_params_btn, 0, 3)

        # Separator
        spacer_label = QLabel("")
        spacer_label.setFixedHeight(20)
        table_layout.addWidget(spacer_label, 1, 0, 1, 4)

        # Financial data rows
        settled_label = QLabel("SETTLED CASH")
        settled_label.setStyleSheet(cell_style)
        table_layout.addWidget(settled_label, 2, 0)

        self.settled_value = QLabel("$21,800,000.00")
        self.settled_value.setStyleSheet(cell_style + "text-align: right;")
        self.settled_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        table_layout.addWidget(self.settled_value, 2, 1)

        realized_label = QLabel("REALIZED P&L")
        realized_label.setStyleSheet(cell_style)
        table_layout.addWidget(realized_label, 2, 2)

        self.realized_value = QLabel("$2,030,450.00")
        self.realized_value.setStyleSheet(
            cell_style + f"color: {COLORS['positive']}; text-align: right;"
        )
        self.realized_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        table_layout.addWidget(self.realized_value, 2, 3)

        buying_label = QLabel("BUYING POWER")
        buying_label.setStyleSheet(cell_style)
        table_layout.addWidget(buying_label, 3, 0)

        self.buying_value = QLabel("$20,450,000.00")
        self.buying_value.setStyleSheet(cell_style + "text-align: right;")
        self.buying_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        table_layout.addWidget(self.buying_value, 3, 1)

        unrealized_label = QLabel("UNREALIZED P&L")
        unrealized_label.setStyleSheet(cell_style)
        table_layout.addWidget(unrealized_label, 3, 2)

        self.unrealized_value = QLabel("$1,385,000.00")
        self.unrealized_value.setStyleSheet(
            cell_style + f"color: {COLORS['positive']}; text-align: right;"
        )
        self.unrealized_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        table_layout.addWidget(self.unrealized_value, 3, 3)

        table_widget.setLayout(table_layout)
        account_layout.addWidget(table_widget)
        account_group.setLayout(account_layout)
        layout.addWidget(account_group)

        # P&L Performance
        pnl_group = QGroupBox("P&L PERFORMANCE")
        pnl_layout = QVBoxLayout()
        pnl_layout.setContentsMargins(5, 1, 5, 1)
        pnl_layout.setSpacing(1)

        self.pnl_table = self.create_pnl_table()
        self.pnl_table.setFixedHeight(122)
        pnl_layout.addWidget(self.pnl_table)

        pnl_group.setLayout(pnl_layout)
        layout.addWidget(pnl_group)

        # Risk Monitor
        risk_group = QGroupBox("RISK MONITOR")
        risk_layout = QVBoxLayout()
        risk_layout.setSpacing(2)

        self.greek_bars = {
            "delta": GreekBar("Delta", -100, 100),
            "gamma": GreekBar("Gamma", -10, 10),
            "theta": GreekBar("Theta", -400, 0),
            "vega": GreekBar("Vega", -600, 0),
        }

        for bar in self.greek_bars.values():
            risk_layout.addWidget(bar)

        risk_group.setLayout(risk_layout)
        layout.addWidget(risk_group)

        # Autonomous AI Activity
        auto_group = QGroupBox("AUTONOMOUS AI ACTIVITY")
        auto_group.setStyleSheet(
            f"""
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 12px;
                padding-top: 5px;
                background-color: {COLORS['background']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                top: -2px;
            }}
        """
        )
        auto_layout = QVBoxLayout()
        auto_layout.setContentsMargins(5, 5, 5, 5)
        auto_layout.setSpacing(0)

        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setFixedHeight(140)
        self.auto_log.setStyleSheet(
            f"""
            QTextEdit {{
                font-family: monospace;
                font-size: 13px;
                color: {COLORS['cyan']};
                padding: 1px;
                border: 1px solid {COLORS['border']};
                background-color: {COLORS['panel']};
                margin: 0px;
            }}
        """
        )
        self.auto_log.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.auto_log.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        auto_layout.addWidget(self.auto_log)
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)

        # Unified Prometheus Metrics
        metrics_widget = self.create_unified_prometheus_metrics()
        layout.addWidget(metrics_widget)

        panel.setLayout(layout)
        return panel

    def create_pnl_table(self) -> QTableWidget:
        """Create P&L performance table"""
        table = QTableWidget(4, 8)

        headers = [
            "PERIOD",
            "PROFIT & LOSS",
            "WIN RATE",
            "AVG WIN/LOSS",
            "PROFIT-F",
            "SHARP",
            "SORTINO",
            "CALMAR",
        ]
        table.setHorizontalHeaderLabels(headers)

        # Add sample data
        periods = ["TODAY", "WEEK", "MONTH", "YEAR"]
        data = [
            ("+$850.00", "75%", "$425/$120", "1.65", "1.85", "2.12", "1.95"),
            ("+$3,200.00", "68%", "$380/$150", "1.52", "1.92", "2.05", "2.18"),
            ("+$12,500.00", "72%", "$450/$180", "1.78", "2.15", "2.35", "2.62"),
            ("+$240,000,000.00", "70%", "$500/$200", "1.85", "2.35", "2.58", "3.15"),
        ]

        for row, (period, values) in enumerate(zip(periods, data)):
            table.setItem(row, 0, QTableWidgetItem(period))

            pnl_item = QTableWidgetItem(values[0])
            pnl_item.setTextAlignment(Qt.AlignRight)
            pnl_item.setForeground(QColor(COLORS["positive"]))
            table.setItem(row, 1, pnl_item)

            win_rate_item = QTableWidgetItem(values[1])
            win_rate_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 2, win_rate_item)

            avg_item = QTableWidgetItem(values[2])
            avg_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 3, avg_item)

            profit_factor_item = QTableWidgetItem(values[3])
            profit_factor_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 4, profit_factor_item)

            sharp_ratio_item = QTableWidgetItem(values[4])
            sharp_ratio_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 5, sharp_ratio_item)

            sortino_ratio_item = QTableWidgetItem(values[5])
            sortino_ratio_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 6, sortino_ratio_item)

            calmar_ratio_item = QTableWidgetItem(values[6])
            calmar_ratio_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 7, calmar_ratio_item)

        table.setStyleSheet("font-size: 13px;")
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(22)

        # Set column widths
        table.setColumnWidth(0, 60)  # PERIOD
        table.setColumnWidth(1, 120)  # P&L
        table.setColumnWidth(2, 60)  # WIN RATE
        table.setColumnWidth(3, 120)  # AVG WIN/LOSS
        table.setColumnWidth(4, 65)  # PROFIT-F
        table.setColumnWidth(5, 55)  # SHARP
        table.setColumnWidth(6, 65)  # SORTINO
        table.setColumnWidth(7, 65)  # CALMAR

        table.setFixedWidth(610)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        return table

    def create_unified_prometheus_metrics(self) -> QWidget:
        """Create the unified Prometheus Metrics table (6x4 grid)"""
        container = QWidget()
        container.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
            }}
        """
        )
        container.setFixedHeight(200)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(2)

        # Title
        title_label = QLabel("PROMETHEUS METRICS MONITOR")
        title_label.setStyleSheet(
            f"""
            color: {COLORS['text']};
            font-size: 14px;
            font-weight: normal;
            padding-bottom: 1px;
        """
        )
        title_label.setAlignment(Qt.AlignLeft)
        main_layout.addWidget(title_label)

        main_layout.addSpacing(8)

        # Create the 6x4 grid
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setContentsMargins(0, 0, 0, 0)

        # Column headers
        headers = [
            "SYSTEM HEALTH",
            "IB CLIENTS 1-5",
            "IB CLIENTS 6-10",
            "INTERNAL MODULES",
        ]
        for col, header in enumerate(headers):
            header_label = QLabel(header)
            header_label.setStyleSheet(
                f"""
                color: {COLORS['cyan']};
                font-size: 13px;
                font-weight: normal;
                padding: 2px;
                border-bottom: 1px solid {COLORS['border']};
            """
            )
            header_label.setAlignment(Qt.AlignCenter)
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

        # IB Clients 1-5 (Column 2)
        client_1_5_types = ["Orders", "Admin", "Core", "Options", "Volatility"]
        for row in range(1, 6):
            client_widget = QWidget()
            client_layout = QHBoxLayout()
            client_layout.setContentsMargins(5, 1, 5, 1)
            client_layout.setSpacing(3)

            indicator = QLabel("●")
            indicator.setStyleSheet(
                "color: " + COLORS["positive"] + f"; font-size: 14px;"
            )
            client_layout.addWidget(indicator)

            label = QLabel(f"CLIENT {row}: {client_1_5_types[row-1]}")
            label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
            client_layout.addWidget(label)
            client_layout.addStretch()

            client_widget.setLayout(client_layout)
            self.client_indicators[f"CLIENT {row}"] = indicator
            grid.addWidget(client_widget, row, 1)

        # IB Clients 6-10 (Column 3)
        client_6_10_types = [
            "Internals",
            "Major ETFs",
            "Extended",
            "Sector ETFs",
            "International",
        ]
        for row in range(1, 6):
            client_num = row + 5
            client_widget = QWidget()
            client_layout = QHBoxLayout()
            client_layout.setContentsMargins(5, 1, 5, 1)
            client_layout.setSpacing(3)

            indicator = QLabel("●")
            indicator.setStyleSheet(
                "color: " + COLORS["positive"] + f"; font-size: 14px;"
            )
            client_layout.addWidget(indicator)

            label = QLabel(f"CLIENT {client_num}: {client_6_10_types[row-1]}")
            label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
            client_layout.addWidget(label)
            client_layout.addStretch()

            client_widget.setLayout(client_layout)
            self.client_indicators[f"CLIENT {client_num}"] = indicator
            grid.addWidget(client_widget, row, 2)

        # Internal Modules (Column 4)
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