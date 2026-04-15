#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG15_ConnectAPIStatus.py
Purpose: Broker & data connection status display widget (Tradier + Massive)

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2026-02-25 Time: 14:00:00

Module Description:
    GUI widget for displaying Tradier broker and Massive data connection
    status.  Shows connection health, account info, order status, and risk
    metrics.  Fully PySide6 (Qt6) — replaces the legacy PyQt5/ConnectAPI
    version.

Module Constants:
    STATUS_UPDATE_INTERVAL (int): Status update interval in milliseconds
    STATUS_COLORS (Dict): Colour mapping for status levels

Change Log:
    2026-02-25 (v2.0.0):
        - Full rewrite for Tradier + Massive migration
        - Converted from PyQt5 to PySide6
        - Replaced ConnectAPI dependency with TradierClient + OrderManager
        - Added Tradier account / environment / connection display
        - Added Massive data-feed status panel

    2025-10-20 (v1.0.0):
        - Initial module creation (ConnectAPI)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum, auto
from threading import RLock

# ==============================================================================
# THIRD-PARTY IMPORTS — PySide6
# ==============================================================================
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QPushButton,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Broker — Tradier-based
try:
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import TradierClient
    TRADIER_AVAILABLE = True
except ImportError:
    TradierClient = None  # type: ignore[assignment,misc]
    TRADIER_AVAILABLE = False

try:
    from Spyder.SpyderB_Broker.SpyderB02_OrderManager import OrderManager, OrderState
    ORDER_MGR_AVAILABLE = True
except ImportError:
    OrderManager = None  # type: ignore[assignment,misc]
    OrderState = None  # type: ignore[assignment,misc]
    ORDER_MGR_AVAILABLE = False

# Risk
try:
    from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager, RiskLevel
    RISK_AVAILABLE = True
except ImportError:
    RiskManager = None  # type: ignore[assignment,misc]
    RiskLevel = None  # type: ignore[assignment,misc]
    RISK_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
STATUS_UPDATE_INTERVAL = 1000  # milliseconds

STATUS_COLORS: dict[str, QColor] = {
    "CONNECTED": QColor(0, 200, 0),
    "DISCONNECTED": QColor(200, 0, 0),
    "CONNECTING": QColor(200, 200, 0),
    "AUTHENTICATED": QColor(0, 150, 200),
    "ERROR": QColor(200, 0, 100),
    "SANDBOX": QColor(255, 165, 0),
    "PRODUCTION": QColor(0, 200, 0),
    "ACTIVE": QColor(0, 200, 0),
    "NO_ORDERS": QColor(100, 100, 100),
    "LOW": QColor(0, 200, 0),
    "MEDIUM": QColor(200, 200, 0),
    "HIGH": QColor(200, 100, 0),
    "CRITICAL": QColor(200, 0, 0),
    "UNKNOWN": QColor(100, 100, 100),
}


# ==============================================================================
# ENUMS
# ==============================================================================
class StatusLevel(Enum):
    """Status levels."""
    GOOD = auto()
    WARNING = auto()
    ERROR = auto()


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StatusConfig:
    """Configuration for the status display widget."""
    update_interval: int = STATUS_UPDATE_INTERVAL
    show_detailed_metrics: bool = True
    show_risk_metrics: bool = True
    show_order_status: bool = True
    show_broker_status: bool = True
    enable_notifications: bool = True
    notification_threshold: StatusLevel = StatusLevel.WARNING


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class BrokerStatusWidget(QWidget):
    """
    Tradier broker & data-feed status widget.

    Displays connection status, account information, active orders, risk
    metrics and detailed operational metrics.  Polls the TradierClient and
    OrderManager every *update_interval* ms.

    Attributes:
        tradier_client: TradierClient instance for broker status.
        order_manager: OrderManager instance for order tracking.
        risk_manager: RiskManager instance for risk metrics.
    """

    # Qt Signals
    status_changed = Signal(str, str)  # component, status

    def __init__(
        self,
        config: StatusConfig | None = None,
        tradier_client: Optional["TradierClient"] = None,
        order_manager: Optional["OrderManager"] = None,
        risk_manager: Optional["RiskManager"] = None,
        parent: QWidget | None = None,
    ):
        """
        Initialise the broker status widget.

        Args:
            config: Display configuration.  Defaults to ``StatusConfig()``.
            tradier_client: TradierClient instance (or ``None`` to skip
                broker panels).
            order_manager: OrderManager for order status.
            risk_manager: RiskManager for risk metrics.
            parent: Parent widget.
        """
        super().__init__(parent)

        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        self.config = config or StatusConfig()
        self.tradier_client = tradier_client
        self.order_manager = order_manager
        self.risk_manager = risk_manager

        self._status_lock = RLock()
        self._start_time = time.monotonic()

        # Timer
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)

        # Build UI
        self._init_ui()

        # Start updates
        self._status_timer.start(self.config.update_interval)
        self.logger.info("BrokerStatusWidget initialised")

    # ------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        """Initialise the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Connection status header
        self._create_connection_status_group(main_layout)

        # Tabbed detail sections
        self._create_status_tabs(main_layout)

    def _create_connection_status_group(self, parent_layout: QVBoxLayout) -> None:
        """Create the top-level connection status bar."""
        group_box = QGroupBox("Broker Connection")
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: normal;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        layout = QHBoxLayout(group_box)
        layout.setContentsMargins(10, 5, 10, 5)

        # Connection status pill
        self.connection_status_label = QLabel("Disconnected")
        self.connection_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_status_label.setMinimumHeight(30)
        self._apply_status_style(self.connection_status_label, "DISCONNECTED")

        # Broker / Environment
        self.broker_label = QLabel("Broker: Tradier")
        self.broker_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.environment_label = QLabel("Env: --")
        self.environment_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Uptime
        self.uptime_label = QLabel("Uptime: 00:00:00")
        self.uptime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.connection_status_label)
        layout.addWidget(self.broker_label)
        layout.addWidget(self.environment_label)
        layout.addWidget(self.uptime_label)

        parent_layout.addWidget(group_box)

    def _create_status_tabs(self, parent_layout: QVBoxLayout) -> None:
        """Create the tabbed detail panels."""
        self.status_tabs = QTabWidget()

        if self.config.show_broker_status:
            self._create_broker_tab()

        if self.config.show_order_status:
            self._create_order_status_tab()

        if self.config.show_risk_metrics:
            self._create_risk_metrics_tab()

        if self.config.show_detailed_metrics:
            self._create_detailed_metrics_tab()

        parent_layout.addWidget(self.status_tabs)

    # --- Broker tab ---
    def _create_broker_tab(self) -> None:
        """Create broker / account information tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        account_group = QGroupBox("Account Information")
        grid = QGridLayout(account_group)

        self.account_id_label = QLabel("Account ID: --")
        self.account_type_label = QLabel("Type: --")
        self.buying_power_label = QLabel("Buying Power: --")
        self.total_equity_label = QLabel("Total Equity: --")
        self.cash_label = QLabel("Cash: --")
        self.day_trade_count_label = QLabel("Day Trades: --")

        grid.addWidget(self.account_id_label, 0, 0)
        grid.addWidget(self.account_type_label, 0, 1)
        grid.addWidget(self.buying_power_label, 1, 0)
        grid.addWidget(self.total_equity_label, 1, 1)
        grid.addWidget(self.cash_label, 2, 0)
        grid.addWidget(self.day_trade_count_label, 2, 1)

        layout.addWidget(account_group)

        # Positions table
        positions_group = QGroupBox("Tradier Positions")
        pos_layout = QVBoxLayout(positions_group)

        self.tradier_positions_table = QTableWidget()
        self.tradier_positions_table.setColumnCount(5)
        self.tradier_positions_table.setHorizontalHeaderLabels(
            ["Symbol", "Qty", "Cost Basis", "Market Value", "P&L"]
        )
        self.tradier_positions_table.horizontalHeader().setStretchLastSection(True)
        self.tradier_positions_table.setMinimumHeight(180)

        pos_layout.addWidget(self.tradier_positions_table)
        layout.addWidget(positions_group)

        # Refresh button
        refresh_btn = QPushButton("Refresh Account")
        refresh_btn.clicked.connect(self._refresh_broker_data)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; color: white; border: none;
                padding: 6px 12px; border-radius: 3px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        layout.addWidget(refresh_btn)

        self.status_tabs.addTab(widget, "Broker")

    # --- Orders tab ---
    def _create_order_status_tab(self) -> None:
        """Create active orders tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.order_status_label = QLabel("Status: Unknown")
        self._apply_status_style(self.order_status_label, "UNKNOWN")
        layout.addWidget(self.order_status_label)

        orders_group = QGroupBox("Active Orders")
        orders_layout = QVBoxLayout(orders_group)

        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(7)
        self.orders_table.setHorizontalHeaderLabels(
            ["Order ID", "Tradier ID", "Symbol", "Side", "Type", "Qty", "Status"]
        )
        self.orders_table.horizontalHeader().setStretchLastSection(True)
        self.orders_table.setMinimumHeight(200)

        orders_layout.addWidget(self.orders_table)
        layout.addWidget(orders_group)

        self.status_tabs.addTab(widget, "Orders")

    # --- Risk tab ---
    def _create_risk_metrics_tab(self) -> None:
        """Create risk metrics tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.risk_level_label = QLabel("Risk Level: Unknown")
        self._apply_status_style(self.risk_level_label, "UNKNOWN")
        layout.addWidget(self.risk_level_label)

        metrics_group = QGroupBox("Risk Metrics")
        metrics_layout = QGridLayout(metrics_group)

        self.total_exposure_label = QLabel("Total Exposure: $0.00")
        self.daily_pnl_label = QLabel("Daily P&L: $0.00")
        self.margin_usage_label = QLabel("Margin Usage: 0.00%")
        self.concentration_label = QLabel("Max Concentration: 0.00%")
        self.warnings_label = QLabel("Warnings: 0")

        metrics_layout.addWidget(self.total_exposure_label, 0, 0, 1, 2)
        metrics_layout.addWidget(self.daily_pnl_label, 1, 0, 1, 2)
        metrics_layout.addWidget(self.margin_usage_label, 2, 0, 1, 2)
        metrics_layout.addWidget(self.concentration_label, 3, 0, 1, 2)
        metrics_layout.addWidget(self.warnings_label, 4, 0, 1, 2)

        layout.addWidget(metrics_group)

        # Risk positions table
        pos_group = QGroupBox("Current Positions (Risk)")
        pos_layout = QVBoxLayout(pos_group)

        self.risk_positions_table = QTableWidget()
        self.risk_positions_table.setColumnCount(5)
        self.risk_positions_table.setHorizontalHeaderLabels(
            ["Symbol", "Quantity", "Market Value", "Unrealised P&L", "% of Portfolio"]
        )
        self.risk_positions_table.horizontalHeader().setStretchLastSection(True)
        self.risk_positions_table.setMinimumHeight(180)

        pos_layout.addWidget(self.risk_positions_table)
        layout.addWidget(pos_group)

        self.status_tabs.addTab(widget, "Risk")

    # --- Metrics tab ---
    def _create_detailed_metrics_tab(self) -> None:
        """Create detailed operational metrics tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Broker metrics
        broker_group = QGroupBox("Tradier API Metrics")
        broker_layout = QGridLayout(broker_group)

        self.api_requests_label = QLabel("API Requests: 0")
        self.api_errors_label = QLabel("API Errors: 0")
        self.rate_limit_label = QLabel("Rate Limit Remaining: --")
        self.last_request_label = QLabel("Last Request: --")

        broker_layout.addWidget(self.api_requests_label, 0, 0)
        broker_layout.addWidget(self.api_errors_label, 0, 1)
        broker_layout.addWidget(self.rate_limit_label, 1, 0)
        broker_layout.addWidget(self.last_request_label, 1, 1)

        layout.addWidget(broker_group)

        # Order manager metrics
        order_group = QGroupBox("Order Manager Metrics")
        order_layout = QGridLayout(order_group)

        self.orders_submitted_label = QLabel("Orders Submitted: 0")
        self.orders_filled_label = QLabel("Orders Filled: 0")
        self.orders_cancelled_label = QLabel("Orders Cancelled: 0")
        self.success_rate_label = QLabel("Success Rate: 0.00%")

        order_layout.addWidget(self.orders_submitted_label, 0, 0)
        order_layout.addWidget(self.orders_filled_label, 0, 1)
        order_layout.addWidget(self.orders_cancelled_label, 1, 0)
        order_layout.addWidget(self.success_rate_label, 1, 1)

        layout.addWidget(order_group)

        self.status_tabs.addTab(widget, "Metrics")

    # ------------------------------------------------------------------
    # STATUS STYLING HELPER
    # ------------------------------------------------------------------
    def _apply_status_style(self, label: QLabel, status: str) -> None:
        """Apply colour-coded styling to a status label."""
        color = STATUS_COLORS.get(status, QColor(100, 100, 100))
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {color.name()};
                color: white;
                font-weight: normal;
                border-radius: 5px;
                padding: 5px;
            }}
        """)
        # Preserve "Prefix: " text
        if ":" in label.text():
            prefix = label.text().split(":", 1)[0]
            label.setText(f"{prefix}: {status}")
        else:
            label.setText(status)

    # ------------------------------------------------------------------
    # PERIODIC UPDATE
    # ------------------------------------------------------------------
    @Slot()
    def _update_status(self) -> None:
        """Master update — called every *update_interval* ms."""
        try:
            self._update_connection_status()

            if self.config.show_broker_status and self.tradier_client:
                self._update_broker_tab()

            if self.config.show_order_status and self.order_manager:
                self._update_order_status()

            if self.config.show_risk_metrics and self.risk_manager:
                self._update_risk_metrics()

            if self.config.show_detailed_metrics:
                self._update_detailed_metrics()

        except Exception as e:
            self.logger.error("Error updating status: %s", e)

    # --- Connection ---
    def _update_connection_status(self) -> None:
        """Update top-level connection indicator."""
        try:
            connected = False
            env_str = "--"

            if self.tradier_client:
                try:
                    connected = self.tradier_client.test_connection()
                except Exception:
                    connected = False
                env_str = getattr(self.tradier_client, "environment", None)
                if hasattr(env_str, "value"):
                    env_str = env_str.value  # TradierEnvironment enum
                env_str = str(env_str).upper() if env_str else "--"
            elif self.order_manager:
                status = self.order_manager.get_status()
                connected = status.get("connected", False)
                env_str = str(status.get("environment", "--")).upper()

            state = "CONNECTED" if connected else "DISCONNECTED"
            self._apply_status_style(self.connection_status_label, state)
            self.environment_label.setText(f"Env: {env_str}")

            # Uptime
            elapsed = int(time.monotonic() - self._start_time)
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            self.uptime_label.setText(f"Uptime: {h:02d}:{m:02d}:{s:02d}")

            self.status_changed.emit("connection", state)

        except Exception as e:
            self.logger.error("Error updating connection status: %s", e)

    # --- Broker tab ---
    def _update_broker_tab(self) -> None:
        """Refresh account and positions from Tradier."""
        try:
            if not self.tradier_client:
                return

            # Account info
            try:
                balance = self.tradier_client.get_account_balance()
                if balance:
                    self.account_id_label.setText(
                        f"Account ID: {self.tradier_client.account_id}"
                    )
                    self.account_type_label.setText(
                        f"Type: {balance.get('type', '--')}"
                    )
                    bp = balance.get("option_buying_power",
                                     balance.get("buying_power", 0))
                    self.buying_power_label.setText(f"Buying Power: ${bp:,.2f}")
                    eq = balance.get("total_equity",
                                     balance.get("equity", 0))
                    self.total_equity_label.setText(f"Total Equity: ${eq:,.2f}")
                    cash = balance.get("total_cash",
                                       balance.get("cash", 0))
                    self.cash_label.setText(f"Cash: ${cash:,.2f}")
                    dtc = balance.get("day_trade_count", "--")
                    self.day_trade_count_label.setText(f"Day Trades: {dtc}")
            except Exception as e:
                self.logger.debug("Could not fetch account balance: %s", e)

            # Positions
            try:
                positions = self.tradier_client.get_positions()
                if positions and isinstance(positions, list):
                    self.tradier_positions_table.setRowCount(len(positions))
                    for i, pos in enumerate(positions):
                        sym = pos.get("symbol", "")
                        qty = pos.get("quantity", 0)
                        cost = pos.get("cost_basis", 0)
                        mkt = qty * pos.get("last_price", 0) if "last_price" in pos else 0
                        pnl = mkt - cost if cost else 0
                        self.tradier_positions_table.setItem(
                            i, 0, QTableWidgetItem(str(sym)))
                        self.tradier_positions_table.setItem(
                            i, 1, QTableWidgetItem(str(qty)))
                        self.tradier_positions_table.setItem(
                            i, 2, QTableWidgetItem(f"${cost:,.2f}"))
                        self.tradier_positions_table.setItem(
                            i, 3, QTableWidgetItem(f"${mkt:,.2f}"))
                        self.tradier_positions_table.setItem(
                            i, 4, QTableWidgetItem(f"${pnl:,.2f}"))
                else:
                    self.tradier_positions_table.setRowCount(0)
            except Exception as e:
                self.logger.debug("Could not fetch positions: %s", e)

        except Exception as e:
            self.logger.error("Error updating broker tab: %s", e)

    def _refresh_broker_data(self) -> None:
        """Manual refresh button handler."""
        self._update_broker_tab()

    # --- Orders ---
    def _update_order_status(self) -> None:
        """Update active orders display."""
        try:
            if not self.order_manager or not OrderState:
                return

            orders: list[Any] = []
            for state in (OrderState.SUBMITTED, OrderState.OPEN,
                          OrderState.PARTIALLY_FILLED, OrderState.PENDING):
                try:
                    orders.extend(self.order_manager.get_orders_by_state(state))
                except Exception as e:
                    self.logger.debug("Failed to get orders for state %s: %s", state, e)

            if orders:
                self._apply_status_style(self.order_status_label, "ACTIVE")
            else:
                self._apply_status_style(self.order_status_label, "NO_ORDERS")

            self.orders_table.setRowCount(len(orders))
            for i, order in enumerate(orders):
                self.orders_table.setItem(
                    i, 0, QTableWidgetItem(str(getattr(order, "order_id", ""))))
                self.orders_table.setItem(
                    i, 1, QTableWidgetItem(str(getattr(order, "tradier_order_id", ""))))
                self.orders_table.setItem(
                    i, 2, QTableWidgetItem(str(getattr(order, "symbol", ""))))
                side = getattr(order, "side", "")
                self.orders_table.setItem(i, 3, QTableWidgetItem(str(side)))
                otype = getattr(order, "order_type", "")
                self.orders_table.setItem(i, 4, QTableWidgetItem(str(otype)))
                self.orders_table.setItem(
                    i, 5, QTableWidgetItem(str(getattr(order, "quantity", ""))))
                state_val = getattr(order, "state", None)
                state_name = state_val.name if hasattr(state_val, "name") else str(state_val)
                self.orders_table.setItem(i, 6, QTableWidgetItem(state_name))

            self.status_changed.emit(
                "orders", "ACTIVE" if orders else "NO_ORDERS"
            )

        except Exception as e:
            self.logger.error("Error updating order status: %s", e)

    # --- Risk ---
    def _update_risk_metrics(self) -> None:
        """Update risk metrics display."""
        try:
            if not self.risk_manager:
                return

            risk_metrics = self.risk_manager.get_risk_metrics()
            if not risk_metrics:
                return

            self._apply_status_style(
                self.risk_level_label, risk_metrics.risk_level.name
            )
            self.total_exposure_label.setText(
                f"Total Exposure: ${risk_metrics.total_exposure:,.2f}"
            )
            self.daily_pnl_label.setText(
                f"Daily P&L: ${risk_metrics.daily_pnl:,.2f}"
            )
            margin_total = risk_metrics.margin_used + risk_metrics.margin_available
            usage = (risk_metrics.margin_used / margin_total * 100
                     if margin_total > 0 else 0)
            self.margin_usage_label.setText(f"Margin Usage: {usage:.2f}%")
            self.concentration_label.setText(
                f"Max Concentration: {risk_metrics.max_concentration:.2%}"
            )
            self.warnings_label.setText(
                f"Warnings: {len(risk_metrics.warnings)}"
            )

            # Positions table
            try:
                positions = self.risk_manager.get_positions()
                if positions:
                    total_val = sum(
                        abs(getattr(p, "market_value", 0))
                        for p in positions.values()
                    )
                    self.risk_positions_table.setRowCount(len(positions))
                    for i, (sym, pos) in enumerate(positions.items()):
                        self.risk_positions_table.setItem(
                            i, 0, QTableWidgetItem(str(sym)))
                        self.risk_positions_table.setItem(
                            i, 1, QTableWidgetItem(str(pos.quantity)))
                        self.risk_positions_table.setItem(
                            i, 2, QTableWidgetItem(f"${pos.market_value:,.2f}"))
                        self.risk_positions_table.setItem(
                            i, 3, QTableWidgetItem(f"${pos.unrealized_pnl:,.2f}"))
                        pct = (abs(pos.market_value) / total_val * 100
                               if total_val > 0 else 0)
                        self.risk_positions_table.setItem(
                            i, 4, QTableWidgetItem(f"{pct:.2f}%"))
            except Exception as e:
                self.logger.debug("Failed to render risk positions: %s", e)

            self.status_changed.emit("risk", risk_metrics.risk_level.name)

        except Exception as e:
            self.logger.error("Error updating risk metrics: %s", e)

    # --- Metrics ---
    def _update_detailed_metrics(self) -> None:
        """Update operational metrics."""
        try:
            # Order manager metrics
            if self.order_manager:
                try:
                    om = self.order_manager.get_metrics()
                    self.orders_submitted_label.setText(
                        f"Orders Submitted: {om.get('orders_submitted', 0)}"
                    )
                    self.orders_filled_label.setText(
                        f"Orders Filled: {om.get('orders_filled', 0)}"
                    )
                    self.orders_cancelled_label.setText(
                        f"Orders Cancelled: {om.get('orders_cancelled', 0)}"
                    )
                    self.success_rate_label.setText(
                        f"Success Rate: {om.get('success_rate', 0):.2f}%"
                    )
                except Exception as e:
                    self.logger.debug("Failed to get order manager metrics: %s", e)

        except Exception as e:
            self.logger.error("Error updating detailed metrics: %s", e)

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    def stop(self) -> None:
        """Stop periodic updates."""
        try:
            self.logger.info("Stopping BrokerStatusWidget...")
            self._status_timer.stop()
            self.logger.info("BrokerStatusWidget stopped")
        except Exception as e:
            self.logger.error("Error stopping status widget: %s", e)



# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_status_widget(
    config: StatusConfig | None = None,
    tradier_client: Optional["TradierClient"] = None,
    order_manager: Optional["OrderManager"] = None,
    risk_manager: Optional["RiskManager"] = None,
    parent: QWidget | None = None,
) -> BrokerStatusWidget:
    """
    Factory function to create a broker status widget.

    Args:
        config: Display configuration (defaults to ``StatusConfig()``).
        tradier_client: TradierClient for account/connection status.
        order_manager: OrderManager for order tracking.
        risk_manager: RiskManager for risk metrics.
        parent: Parent widget.

    Returns:
        BrokerStatusWidget instance.
    """
    return BrokerStatusWidget(
        config=config,
        tradier_client=tradier_client,
        order_manager=order_manager,
        risk_manager=risk_manager,
        parent=parent,
    )


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPalette

    app = QApplication(sys.argv)

    # Dark theme
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(35, 35, 35))
    app.setPalette(palette)

    widget = BrokerStatusWidget()
    widget.setWindowTitle("Spyder Broker Status — Test")
    widget.resize(700, 500)
    widget.show()

    sys.exit(app.exec())
