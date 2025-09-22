def create_left_panel(self) -> QWidget:
        """Create left panel with market overview"""
        panel = QGroupBox("MARKET OVERVIEW")
        panel.setStyleSheet(f"background-color: {COLORS['background']};")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 10, 0, 0)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 0, 5, 0)

        symbol_header = QLabel("SYMBOL")
        symbol_header.setFixedWidth(60)
        symbol_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        last_header = QLabel("LAST")
        last_header.setFixedWidth(70)
        last_header.setAlignment(Qt.AlignRight)
        last_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        chg_header = QLabel("CHG")
        chg_header.setFixedWidth(55)
        chg_header.setAlignment(Qt.AlignRight)
        chg_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        chg_pct_header = QLabel("CHG%")
        chg_pct_header.setFixedWidth(55)
        chg_pct_header.setAlignment(Qt.AlignRight)
        chg_pct_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        header_layout.addWidget(symbol_header)
        header_layout.addWidget(last_header)
        header_layout.addWidget(chg_header)
        header_layout.addWidget(chg_pct_header)
        header.setLayout(header_layout)

        layout.addWidget(header)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(separator)

        # Scroll area for symbols
        scroll_area = QScrollArea()
        scroll_area.setStyleSheet(f"background-color: {COLORS['background']};")
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet(f"background-color: {COLORS['background']};")
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(1)

        # Create symbol widgets - ALL SYMBOLS
        self.symbol_widgets = {}
        for category, symbols in MARKET_SYMBOLS.items():
            cat_label = QLabel(category)
            cat_label.setStyleSheet(
                f"color: {COLORS['cyan']}; font-size: 14px; padding: 5px 0px 2px 10px; font-weight: normal;"
            )
            scroll_layout.addWidget(cat_label)

            for symbol in symbols:
                widget = MarketSymbolWidget(symbol, category)
                widget.setStyleSheet(f"background-color: {COLORS['background']};")
                self.symbol_widgets[symbol] = widget
                scroll_layout.addWidget(widget)

        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)
        panel.setLayout(layout)
        return panel

    def create_center_panel(self) -> QWidget:
        """Create center panel"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Market regime indicator
        regime_widget = QWidget()
        regime_widget.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};"
        )
        regime_widget.setFixedHeight(40)
        regime_layout = QHBoxLayout()

        regime_layout.addStretch()

        center_container = QHBoxLayout()
        center_container.setSpacing(20)

        regime_section = QHBoxLayout()
        regime_section.setSpacing(5)
        regime_label = QLabel("MARKET REGIME: ")
        regime_label.setStyleSheet(f"color: {COLORS['text']};")
        regime_section.addWidget(regime_label)

        regime_value = QLabel("Low Volatility - Range Bound")
        regime_value.setStyleSheet(f"color: {COLORS['cyan']};")
        regime_section.addWidget(regime_value)

        center_container.addLayout(regime_section)

        separator_label = QLabel("|")
        separator_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        center_container.addWidget(separator_label)

        strategy_section = QHBoxLayout()
        strategy_section.setSpacing(5)
        strategy_label = QLabel("CURRENT ACTIVE STRATEGY: ")
        strategy_label.setStyleSheet(f"color: {COLORS['text']};")
        strategy_section.addWidget(strategy_label)

        strategy_value = QLabel("Iron Condor")
        strategy_value.setStyleSheet(f"color: {COLORS['cyan']};")
        strategy_section.addWidget(strategy_value)

        center_container.addLayout(strategy_section)

        regime_layout.addLayout(center_container)
        regime_layout.addStretch()

        regime_widget.setLayout(regime_layout)
        layout.addWidget(regime_widget)

        # Create the chart widget
        self.create_chart()
        layout.addWidget(self.chart_widget, 2)

        # Positions table
        positions_group = QGroupBox("ORDERS & POSITIONS")
        positions_layout = QVBoxLayout()

        self.positions_table = self.create_positions_table()
        self.positions_table.setMaximumHeight(190)
        self.positions_table.setMinimumHeight(190)
        positions_layout.addWidget(self.positions_table)

        positions_group.setLayout(positions_layout)
        layout.addWidget(positions_group, 1)

        # System logs with Signal Monitor Panel
        logs_container = QWidget()
        logs_container_layout = QHBoxLayout()
        logs_container_layout.setSpacing(5)
        logs_container_layout.setContentsMargins(0, 0, 0, 0)

        # System logs (left side)
        logs_group = QGroupBox("SYSTEM LOG")
        logs_layout = QVBoxLayout()

        self.system_log = QTextEdit()
        self.system_log.setReadOnly(True)
        self.system_log.setMaximumHeight(150)
        self.system_log.setStyleSheet(f"font-family: monospace; font-size: 13px;")

        logs_layout.addWidget(self.system_log)
        logs_group.setLayout(logs_layout)

        # Signal Monitor Panel (right side)
        signal_group = QGroupBox("SIGNAL MONITOR")
        signal_group.setStyleSheet(
            f"QGroupBox {{ color: {COLORS['text']}; font-weight: normal; }}"
        )
        signal_layout = QVBoxLayout()
        signal_layout.setContentsMargins(5, 5, 5, 5)

        self.signal_panel = SignalMonitorPanel()
        signal_layout.addWidget(self.signal_panel)
        signal_group.setLayout(signal_layout)

        logs_container_layout.addWidget(logs_group, 65)
        logs_container_layout.addWidget(signal_group, 35)

        logs_container.setLayout(logs_container_layout)
        layout.addWidget(logs_container, 1)

        panel.setLayout(layout)
        return panel

    def create_chart(self):
        """Create the SPY chart widget"""
        self.chart_widget = QWidget()
        self.chart_widget.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};"
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.figure.patch.set_facecolor(COLORS["panel"])

        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.canvas)

        self.chart_widget.setLayout(layout)

        # Draw initial chart
        self.update_chart()

    def update_chart(self):
        """Update the SPY chart with candlesticks and indicators"""
        self.figure.clear()

        # Create sample OHLC data
        periods = 100
        dates = pd.date_range(end=datetime.now(), periods=periods, freq="5min")

        # Generate realistic OHLC data
        spy_price = (
            self.market_data["SPY"]["last"] if "SPY" in self.market_data else 585
        )

        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        current_price = spy_price - 2

        for _ in range(periods):
            # Random walk
            change = random.random() * 0.5 - 0.25
            current_price += change

            # OHLC
            open_price = current_price
            high = current_price + random.random() * 0.3
            low = current_price - random.random() * 0.3
            close = low + random.random() * (high - low)
            volume = random.randint(1000000, 5000000)

            opens.append(open_price)
            highs.append(high)
            lows.append(low)
            closes.append(close)
            volumes.append(volume)

            current_price = close

        # Calculate indicators
        prev_high = max(highs) + random.uniform(0.5, 1.5)
        prev_low = min(lows) - random.uniform(0.5, 1.5)
        prev_close = closes[-1] + random.uniform(-1, 1)

        # Fibonacci Daily Pivot Points
        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = (2 * pivot) - prev_low
        r2 = pivot + (prev_high - prev_low)
        r3 = prev_high + 2 * (pivot - prev_low)
        s1 = (2 * pivot) - prev_high
        s2 = pivot - (prev_high - prev_low)
        s3 = prev_low - 2 * (pivot - prev_low)

        # 20-period Moving Average
        ma_20 = []
        for i in range(len(closes)):
            if i < 19:
                ma_20.append(None)
            else:
                ma_20.append(sum(closes[i - 19 : i + 1]) / 20)

        # VWAP
        vwap = []
        cumulative_pv = 0
        cumulative_volume = 0
        for i in range(len(closes)):
            typical_price = (highs[i] + lows[i] + closes[i]) / 3
            cumulative_pv += typical_price * volumes[i]
            cumulative_volume += volumes[i]
            vwap.append(cumulative_pv / cumulative_volume)

        # Create plot
        ax = self.figure.add_subplot(111)
        ax.yaxis.tick_left()
        ax.yaxis.set_label_position("left")

        # Set background color
        ax.set_facecolor(COLORS["panel"])

        # Plot Fibonacci Daily Pivot Points
        ax.axhline(
            y=pivot,
            color="#FFFF00",
            linewidth=1.5,
            linestyle="-",
            alpha=0.7,
            label="Pivot",
            zorder=1,
        )
        ax.axhline(
            y=r1,
            color="#00FF41",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="R1",
            zorder=1,
        )
        ax.axhline(
            y=r2,
            color="#00FF41",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="R2",
            zorder=1,
        )
        ax.axhline(
            y=r3,
            color="#00FF41",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="R3",
            zorder=1,
        )
        ax.axhline(
            y=s1,
            color="#FF1744",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="S1",
            zorder=1,
        )
        ax.axhline(
            y=s2,
            color="#FF1744",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="S2",
            zorder=1,
        )
        ax.axhline(
            y=s3,
            color="#FF1744",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="S3",
            zorder=1,
        )

        # Plot 20-period Moving Average
        ma_x = [i for i, val in enumerate(ma_20) if val is not None]
        ma_y = [val for val in ma_20 if val is not None]
        ax.plot(
            ma_x,
            ma_y,
            color="#00B8D4",
            linewidth=1.5,
            alpha=0.8,
            label="MA(20)",
            zorder=2,
        )

        # Plot VWAP
        ax.plot(
            range(len(vwap)),
            vwap,
            color="#BF00FF",
            linewidth=1.5,
            alpha=0.9,
            label="VWAP",
            zorder=2,
        )

        # Plot candlesticks
        for i in range(len(dates)):
            color = COLORS["positive"] if closes[i] >= opens[i] else COLORS["negative"]

            # High-Low line
            ax.plot([i, i], [lows[i], highs[i]], color=color, linewidth=1, zorder=3)

            # Open-Close box
            height = abs(closes[i] - opens[i])
            bottom = min(opens[i], closes[i])

            rect = patches.Rectangle(
                (i - 0.3, bottom),
                0.6,
                height,
                facecolor=color,
                edgecolor=color,
                alpha=0.9,
                zorder=3,
            )
            ax.add_patch(rect)

        # Add pivot level labels on the right
        ax.text(
            len(dates),
            pivot,
            f" P: {pivot:.2f}",
            color="#FFFF00",
            fontsize=9,
            va="center",
        )
        ax.text(
            len(dates), r1, f" R1: {r1:.2f}", color="#00FF41", fontsize=8, va="center"
        )
        ax.text(
            len(dates), r2, f" R2: {r2:.2f}", color="#00FF41", fontsize=8, va="center"
        )
        ax.text(
            len(dates), r3, f" R3: {r3:.2f}", color="#00FF41", fontsize=8, va="center"
        )
        ax.text(
            len(dates), s1, f" S1: {s1:.2f}", color="#FF1744", fontsize=8, va="center"
        )
        ax.text(
            len(dates), s2, f" S2: {s2:.2f}", color="#FF1744", fontsize=8, va="center"
        )
        ax.text(
            len(dates), s3, f" S3: {s3:.2f}", color="#FF1744", fontsize=8, va="center"
        )

        # Styling
        ax.set_title("SPY - 5 min", color=COLORS["text"], fontsize=12, pad=10)
        ax.set_xlim(-1, len(dates))
        ax.grid(True, alpha=0.2, color=COLORS["grid"], zorder=0)

        # Format x-axis with time labels
        num_labels = 6
        indices = np.linspace(0, len(dates) - 1, num_labels, dtype=int)
        ax.set_xticks(indices)

        time_labels = []
        for idx in indices:
            time_str = dates[idx].strftime("%H:%M")
            time_labels.append(time_str)

        ax.set_xticklabels(time_labels, fontsize=9)

        # Style axes
        ax.tick_params(colors="#FFFFFF")
        for spine in ax.spines.values():
            spine.set_color(COLORS["border"])

        # Adjust layout
        self.figure.tight_layout()
        self.canvas.draw()

    def create_positions_table(self) -> QTableWidget:
        """Create positions table"""
        table = QTableWidget()

        columns = [
            "DATE",
            "SYMBOL",
            "CNTR",
            "STRIKES",
            "EXPIRY",
            "STRATEGY",
            "STATUS",
            "COST",
            "P&L",
            "AUTO STATUS",
        ]

        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setStyleSheet("font-size: 11px;")

        # Set column widths
        table.setColumnWidth(0, 75)  # DATE
        table.setColumnWidth(1, 55)  # SYMBOL
        table.setColumnWidth(2, 45)  # CNTR
        table.setColumnWidth(3, 135)  # STRIKES
        table.setColumnWidth(4, 65)  # EXPIRY
        table.setColumnWidth(5, 150)  # STRATEGY
        table.setColumnWidth(6, 70)  # STATUS
        table.setColumnWidth(7, 95)  # COST
        table.setColumnWidth(8, 95)  # P&L
        table.setColumnWidth(9, 130)  # AUTO STATUS

        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        table.verticalHeader().setDefaultSectionSize(22)
        table.setMinimumHeight(190)
        table.setMaximumHeight(190)

        return table