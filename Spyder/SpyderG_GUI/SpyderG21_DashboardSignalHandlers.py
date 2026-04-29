#!/usr/bin/env python3
"""Signal-handler helpers for SpyderG05_TradingDashboard.

Series: SpyderG_GUI
Module: SpyderG21_DashboardSignalHandlers.py
Purpose: Extract slot/controller signal handling out of SpyderG05_TradingDashboard
"""

import os
from datetime import datetime
from typing import Any

import pytz

from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import is_dashboard_session as _is_dashboard_session  # noqa: E501


def is_market_hours(now_et: datetime | None = None) -> bool:
    """Return True only when ET time is in session and weekday is Mon-Fri."""
    current_et = now_et or datetime.now(pytz.timezone("US/Eastern"))
    if current_et.weekday() >= 5:
        return False
    return bool(_is_dashboard_session(current_et))


def handle_connection_status_changed(dashboard: Any, connected: bool, status: str) -> None:
    """Handle Tradier execution API connection status changes."""
    dashboard.connection_info.api_connected = connected
    dashboard.api_connected = connected

    if connected:
        market_open = bool(is_market_hours())
        exec_color = COLORS["positive"] if market_open else COLORS["warning"]
        dashboard.api_connection_label.setText("TRADIER EXEC")
        dashboard.api_connection_label.setStyleSheet(f"color: {exec_color};")
        if hasattr(dashboard, "api_connect_icon") and dashboard.api_connect_icon:
            dashboard.api_connect_icon.setStyleSheet(
                f"color: {exec_color}; font-size: 13px;",
            )
            dashboard.api_connect_icon.setToolTip("Click to disconnect from Tradier API")

        dashboard.add_system_log("✅ Connected to Tradier API")
        dashboard._refresh_positions_table()

        if (
            hasattr(dashboard, "data_status_label")
            and dashboard.data_status_label.text() == "FROZEN"
        ):
            # Use TRADING_MODE (not TRADIER_ENVIRONMENT) to determine the correct
            # label — TRADIER_ENVIRONMENT can be "live" even when running paper.
            trading_mode = os.getenv("TRADING_MODE", "paper").lower()
            resolved_status = "PAPER" if trading_mode == "paper" else "LIVE"
            dashboard.mkt_data_connected = True
            dashboard.update_data_status(resolved_status)
            provider = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
            dashboard._apply_mkt_provider_display(provider)
    else:
        dashboard.api_connection_label.setText("TRADIER EXEC")
        dashboard.api_connection_label.setStyleSheet(f"color: {COLORS['negative']};")
        if hasattr(dashboard, "api_connect_icon") and dashboard.api_connect_icon:
            dashboard.api_connect_icon.setStyleSheet(
                f"color: {COLORS['negative']}; font-size: 13px;",
            )
            dashboard.api_connect_icon.setToolTip("Click to connect to Tradier API")

        if dashboard.trading_active:
            dashboard.trading_active = False
            dashboard.connection_info.trading_active = False
            dashboard.start_btn.setStyleSheet(
                f"background-color: {COLORS['positive']}; color: black;",
            )
            dashboard.start_btn.setText("START TRADING")
            dashboard.add_automation_log("Trading stopped - API connection lost")

        if "MARKET CLOSED" in status:
            dashboard.add_system_log("📊 Market closed - API disconnected")
        else:
            dashboard.add_system_log("🔌 Disconnected from Tradier API")

    dashboard.update_status_indicators()


def handle_heartbeat_status_changed(dashboard: Any, status: str) -> None:
    """Handle heartbeat status updates for toolbar connection colors."""
    if status in ("disconnected", "error", "offline"):
        if hasattr(dashboard, "api_connection_label"):
            dashboard.api_connection_label.setStyleSheet(f"color: {COLORS['negative']};")
        if hasattr(dashboard, "api_connect_icon") and dashboard.api_connect_icon:
            dashboard.api_connect_icon.setStyleSheet(
                f"color: {COLORS['negative']}; font-size: 13px;",
            )
        if hasattr(dashboard, "mkt_provider_label"):
            dashboard.mkt_provider_label.setStyleSheet(
                f"color: {COLORS['negative']}; font-size: 14px;",
            )
        if hasattr(dashboard, "mkt_connect_icon") and dashboard.mkt_connect_icon:
            dashboard.mkt_connect_icon.setStyleSheet(
                f"color: {COLORS['negative']}; font-size: 13px;",
            )
    elif status == "connected":
        exec_color = COLORS["positive"] if getattr(dashboard, "api_connected", False) else COLORS["negative"]  # noqa: E501
        if hasattr(dashboard, "api_connection_label"):
            dashboard.api_connection_label.setStyleSheet(f"color: {exec_color};")
        if hasattr(dashboard, "api_connect_icon") and dashboard.api_connect_icon:
            dashboard.api_connect_icon.setStyleSheet(f"color: {exec_color}; font-size: 13px;")
        provider = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
        dashboard._apply_mkt_provider_display(provider)


def handle_market_data_status_changed(dashboard: Any, status: str) -> None:
    """Handle market-data connectivity status and provider indicator state."""
    was_connected = dashboard.mkt_data_connected
    if status in ("LIVE", "PAPER"):
        dashboard.mkt_data_connected = True
        resolved_status = dashboard.determine_data_status()
        dashboard.update_data_status(resolved_status)
        dashboard.connection_info.market_data_status = resolved_status
    elif status == "EOD":
        dashboard.mkt_data_connected = True
        dashboard.update_data_status("EOD")
        dashboard.connection_info.market_data_status = "EOD"
    else:
        dashboard.mkt_data_connected = False
        dashboard.connection_info.market_data_status = "NONE"
        if dashboard.trading_active:
            dashboard.trading_active = False
            dashboard.connection_info.trading_active = False
            dashboard.start_btn.setStyleSheet(
                f"background-color: {COLORS['positive']}; color: black;",
            )
            dashboard.start_btn.setText("START TRADING")
            dashboard.add_automation_log("Trading stopped - Market data lost")

    if was_connected != dashboard.mkt_data_connected:
        provider = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
        dashboard._apply_mkt_provider_display(provider)


def handle_market_data_updated(dashboard: Any, data: dict) -> None:
    """Handle market data updates from the market worker thread."""
    if dashboard.real_data_active:
        return

    try:
        for symbol, market_info in data.items():
            if symbol in dashboard.symbol_widgets:
                dashboard.symbol_widgets[symbol].update_data(market_info)

        dashboard.market_data.update(data)

        if dashboard.signal_panel is not None:
            signal_payload: dict[str, Any] = {}
            for symbol in ("VIX", "SKEW", "GEX", "DEX", "OGL", "DIX", "SWAN"):
                entry = data.get(symbol)
                if isinstance(entry, dict) and entry.get("last") is not None:
                    signal_payload[symbol] = entry["last"]
            if signal_payload:
                dashboard.signal_panel.update_live_data(signal_payload)

    except Exception as exc:
        dashboard.logger.exception("Error updating market data: %s", exc)


def handle_market_error(dashboard: Any, error: str) -> None:
    """Route market-worker error messages into the system log."""
    dashboard.add_system_log(f"❌ Market error: {error}")


def handle_heartbeat_received(dashboard: Any, message: str) -> None:
    """Route heartbeat messages into the system log."""
    lowered = (message or "").lower()
    benign = (
        "api healthy" in lowered
        or "still disconnected" in lowered
        or "outside market hours" in lowered
    )
    if benign:
        return
    dashboard.add_system_log(message)  # noqa: W292
