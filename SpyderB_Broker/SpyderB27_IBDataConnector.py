#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB27_IBDataConnector.py
Purpose: Real-time IB Gateway market data integration for dashboard
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-12 Time: 21:30:00
"""

import json
import logging
import random
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ib_async import IB, Stock, Ticker
from PySide6.QtCore import QObject, Signal, QTimer


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


class IBDataConnector(QObject):
    """
    Real-time IB Gateway data connector with singleton pattern.
    Ensures only ONE connection to IB Gateway for market data.

    IMPORTANT: This is a singleton managed by the dashboard.
    DO NOT call __init__ directly - use get_instance() class method.
    """

    _instance = None  # Singleton instance
    _initialized = False  # Track initialization state

    data_received = Signal(dict)
    connection_status = Signal(bool, str)
    error_occurred = Signal(str)

    def __new__(cls):
        """Singleton pattern - only one instance allowed"""
        if cls._instance is None:
            cls._instance = super(IBDataConnector, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once (prevent re-initialization)
        if IBDataConnector._initialized:
            return

        super().__init__()

        # Mark class as initialized (not instance, to survive Qt deletion)
        IBDataConnector._initialized = True

        # Initialize instance variables
        self.ib = None
        self.connected = False
        self.subscriptions: Dict[str, Ticker] = {}
        self.logger = logging.getLogger(__name__)
        self.data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
        self.timer = None
        self.last_prices = {}

        print("🔒 IBDataConnector singleton instance created")

    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton for testing or restart scenarios"""
        if cls._instance is not None:
            try:
                if hasattr(cls._instance, "ib") and cls._instance.ib:
                    cls._instance.ib.disconnect()
            except:
                pass
        cls._instance = None
        cls._initialized = False
        print("🔓 IBDataConnector singleton reset")

    def connect_to_ib(self):
        """Connect to native IB Gateway with minimal production client ID"""
        # GUARD: Prevent reconnection if already connected
        if self.connected and self.ib and self.ib.isConnected():
            print(
                f"⚠️  IBDataConnector already connected (Client 3) - skipping reconnection"
            )
            return True

        try:
            # PRODUCTION MODE: Use dedicated client ID 3 for market data worker
            # Official client IDs: 1-10 reserved for production use
            client_id = 3

            self.ib = IB()

            # SUPPRESS INFORMATIONAL MESSAGES
            # Override error handler to filter farm data and connection messages
            # Based on IBKR API best practices for reducing terminal noise
            def error_handler(reqId, errorCode, errorString, contract):
                """Filter out informational messages that flood the API"""
                # Suppress farm connection and other informational messages
                # (IBKR sends these automatically - cannot be disabled at Gateway)
                ignored_codes = {2104, 2106, 2107, 2108, 2119, 2158, 2103}

                if errorCode not in ignored_codes:
                    # Log other messages at appropriate level
                    if errorCode >= 2000:  # Informational/warning range
                        self.logger.debug(f"IB Info [{errorCode}]: {errorString}")
                    elif errorCode < 1000:  # Error range
                        self.logger.error(f"IB Error [{errorCode}]: {errorString}")
                        self.error_occurred.emit(f"IB Error {errorCode}: {errorString}")

            # Attach error handler to suppress message flooding
            self.ib.errorEvent += error_handler

            # PRODUCTION: Minimize initial message flooding
            # Connect without requesting account data (readonly mode + no account)
            # Increased timeout to 20s to handle Gateway load from Client 2
            self.ib.connect(
                "127.0.0.1", 4002, clientId=client_id, readonly=True, timeout=20
            )

            self.connected = True
            print(f"✅ Market data client {client_id} connected (readonly mode)")
            self.connection_status.emit(True, f"IB CONNECTED (client {client_id})")

            # Subscribe immediately
            self.subscribe_symbols()

            # Setup timer for updates
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_prices)
            self.timer.start(1000)  # Update every second

            return True

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.connection_status.emit(False, f"Connection failed: {e}")
            return False

    def subscribe_symbols(self):
        """Subscribe to market data"""
        symbols = {
            "SPY": Stock("SPY", "SMART", "USD"),
            "QQQ": Stock("QQQ", "SMART", "USD"),
            "IWM": Stock("IWM", "SMART", "USD"),
            "DIA": Stock("DIA", "SMART", "USD"),
            "TLT": Stock("TLT", "SMART", "USD"),
            "GLD": Stock("GLD", "SMART", "USD"),
        }

        if not self.ib:
            self.error_occurred.emit("IB client not connected")
            return

        for symbol, contract in symbols.items():
            try:
                self.ib.qualifyContracts(contract)
                ticker = self.ib.reqMktData(contract, "", False, False)
                self.subscriptions[symbol] = ticker
                print(f"✅ Subscribed to {symbol}")
            except Exception as e:
                print(f"❌ Failed {symbol}: {e}")
                self.error_occurred.emit(f"Subscription failed for {symbol}: {e}")

    def update_prices(self):
        """Update prices from IB"""
        try:
            if not self.ib:
                return

            self.ib.sleep(0)  # Process IB events

            updates = {}
            for symbol, ticker in self.subscriptions.items():
                price = _safe_float(getattr(ticker, "last", None))
                if price is None:
                    price = _safe_float(getattr(ticker, "close", None))
                if price is None:
                    market_price = getattr(ticker, "marketPrice", None)
                    if callable(market_price):
                        price = _safe_float(market_price())
                if price is None:
                    continue

                bid = _safe_float(getattr(ticker, "bid", None)) or price
                ask = _safe_float(getattr(ticker, "ask", None)) or price
                volume = _safe_int(getattr(ticker, "volume", None))

                close_price = _safe_float(getattr(ticker, "close", None))
                if close_price is None:
                    close_price = self.last_prices.get(symbol)
                change = 0.0
                change_pct = 0.0

                if close_price:
                    change = price - close_price
                    if close_price:
                        change_pct = ((price / close_price) - 1.0) * 100.0

                updates[symbol] = {
                    "symbol": symbol,
                    "last": float(price),
                    "bid": float(bid),
                    "ask": float(ask),
                    "volume": volume,
                    "change": float(change),
                    "change_pct": float(change_pct),
                    "timestamp": datetime.now().isoformat(),
                }

            if not updates:
                return

            self.last_prices.update(
                {symbol: data["last"] for symbol, data in updates.items()}
            )
            self._write_to_file(updates)
            self.data_received.emit(updates)

            # PRODUCTION MODE: Suppress debug market data print statements
            # for symbol, data in updates.items():
            #     print(f"📊 {symbol}: ${data['last']:.2f}")

        except Exception as e:
            print(f"Update error: {e}")
            self.error_occurred.emit(f"Update error: {e}")

    def _write_to_file(self, updates: dict):
        """Persist the latest market data to the shared JSON file"""
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)

            existing = {}
            if self.data_file.exists():
                try:
                    with open(self.data_file, "r") as fh:
                        existing = json.load(fh) or {}
                except Exception:
                    existing = {}

            existing.update(updates)

            with tempfile.NamedTemporaryFile(
                "w", delete=False, dir=self.data_file.parent, suffix=".tmp"
            ) as tmp:
                json.dump(existing, tmp, indent=2)
                tmp_path = Path(tmp.name)

            tmp_path.replace(self.data_file)

        except Exception as e:
            self.logger.error(f"Failed to write live data file: {e}")
            self.error_occurred.emit(f"Failed to write live data file: {e}")

    def disconnect(self):
        """Tear down subscriptions and close the IB connection"""
        try:
            if self.timer and self.timer.isActive():
                self.timer.stop()

            if self.ib:
                try:
                    self.ib.disconnect()
                finally:
                    self.ib = None

            self.connected = False
            self.subscriptions.clear()
            self.connection_status.emit(False, "IB DISCONNECTED")

        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
            self.error_occurred.emit(f"Disconnect error: {e}")


def patch_dashboard_with_ib_data(dashboard):
    """Simple patch function"""
    print("🔥 Patching dashboard with IB data...")

    connector = IBDataConnector()

    def update_ui(data):
        for symbol, info in data.items():
            if symbol in dashboard.symbol_widgets:
                widget = dashboard.symbol_widgets[symbol]
                widget.price_label.setText(f"{info['last']:.2f}")

                change = info["change"]
                pct = info["change_pct"]

                color = "#00ff41" if change >= 0 else "#ff1744"
                widget.change_label.setText(f"{change:+.2f}")
                widget.change_label.setStyleSheet(f"color: {color};")
                widget.pct_label.setText(f"{pct:+.2f}%")
                widget.pct_label.setStyleSheet(f"color: {color};")

    connector.data_received.connect(update_ui)

    if connector.connect_to_ib():
        dashboard.add_system_log("✅ IB REAL DATA CONNECTED")

    return connector
