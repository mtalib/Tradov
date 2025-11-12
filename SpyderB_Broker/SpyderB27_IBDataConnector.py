#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB27_IBDataConnector.py
Purpose: Real-time IBKR Web API market data integration for dashboard
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-11-12 Time: 18:00:00

Migration Status: Migrated from ib_async (IB Gateway/TWS) to IBKR Web API (OAuth 2.0)
"""

import json
import logging
import random
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Migrated from ib_async to IBKR Web API (OAuth 2.0)
from SpyderB_Broker.ClientPortalAPI.SpyderB09_ClientPortal_MarketData import (
    MarketDataManager,
    MarketDataConfig,
    Quote
)
from SpyderB_Broker.ClientPortalAPI.SpyderB09_ClientPortal_RESTClient import ClientPortalRESTClient
from SpyderB_Broker.ClientPortalAPI.SpyderB09_ClientPortal_Session import SessionManager
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
    Real-time IBKR Web API data connector with singleton pattern.

    MIGRATION NOTE: Migrated from IB Gateway/TWS (ib_async) to IBKR Web API (OAuth 2.0).
    Uses ClientPortal MarketDataManager for real-time quotes instead of IB Gateway connection.

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

        # Initialize instance variables for Web API
        self.market_data_manager = None
        self.rest_client = None
        self.session_manager = None
        self.connected = False
        self.subscriptions: Dict[str, Any] = {}  # Symbol -> conid mapping
        self.logger = logging.getLogger(__name__)
        self.data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
        self.timer = None
        self.last_prices = {}

        print("🔒 IBDataConnector singleton instance created (Web API mode)")

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
                if hasattr(cls._instance, "market_data_manager") and cls._instance.market_data_manager:
                    cls._instance.market_data_manager.stop()
            except:
                pass
        cls._instance = None
        cls._initialized = False
        print("🔓 IBDataConnector singleton reset (Web API)")

    def connect_to_ib(self):
        """Connect to IBKR Web API for market data (migrated from IB Gateway)"""
        # GUARD: Prevent reconnection if already connected
        if self.connected and self.market_data_manager:
            print("⚠️  IBDataConnector already connected to Web API - skipping reconnection")
            return True

        try:
            # Initialize Web API components
            from config.config import get_config
            config = get_config()

            # Create session manager
            self.session_manager = SessionManager(
                consumer_key=config.consumer_key,
                private_key_path=config.private_key_path,
                account_id=config.account_id
            )

            # Create REST client
            self.rest_client = ClientPortalRESTClient(
                base_url=config.api_base_url,
                session_manager=self.session_manager
            )

            # Create market data manager
            md_config = MarketDataConfig(
                enable_websocket=True,
                enable_rest=True,
                cache_quotes=True,
                max_cache_size=1000
            )

            self.market_data_manager = MarketDataManager(
                rest_client=self.rest_client,
                config=md_config
            )

            self.connected = True
            print("✅ Web API market data connector initialized")
            self.connection_status.emit(True, "Web API CONNECTED")

            # Subscribe immediately
            self.subscribe_symbols()

            # Setup timer for updates
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_prices)
            self.timer.start(1000)  # Update every second

            return True

        except Exception as e:
            print(f"❌ Web API connection failed: {e}")
            self.logger.error(f"Failed to connect to Web API: {e}")
            self.connection_status.emit(False, f"Connection failed: {e}")
            return False

    def subscribe_symbols(self):
        """Subscribe to market data via Web API"""
        # Common symbols to track
        symbols = ["SPY", "QQQ", "IWM", "DIA", "TLT", "GLD"]

        if not self.market_data_manager:
            self.error_occurred.emit("Web API client not connected")
            return

        for symbol in symbols:
            try:
                # Search for contract to get conid
                search_result = self.rest_client.search_contracts(symbol)
                if not search_result or len(search_result) == 0:
                    print(f"⚠️  No contract found for {symbol}")
                    continue

                # Get first stock contract (usually the primary listing)
                contract = None
                for result in search_result:
                    if result.get('assetClass') == 'STK':
                        contract = result
                        break

                if not contract:
                    print(f"⚠️  No stock contract found for {symbol}")
                    continue

                conid = contract.get('conid')
                if not conid:
                    print(f"⚠️  No conid for {symbol}")
                    continue

                # Subscribe to market data for this conid
                self.market_data_manager.subscribe_quote(conid)
                self.subscriptions[symbol] = conid
                print(f"✅ Subscribed to {symbol} (conid: {conid})")

            except Exception as e:
                print(f"❌ Failed to subscribe to {symbol}: {e}")
                self.logger.error(f"Subscription failed for {symbol}: {e}")
                self.error_occurred.emit(f"Subscription failed for {symbol}: {e}")

    def update_prices(self):
        """Update prices from Web API"""
        try:
            if not self.market_data_manager:
                return

            updates = {}
            for symbol, conid in self.subscriptions.items():
                # Get latest quote from market data manager
                quote = self.market_data_manager.get_quote(conid)
                if not quote:
                    continue

                # Extract price data from Quote object
                price = _safe_float(quote.last_price)
                if price is None or price == 0:
                    continue

                bid = _safe_float(quote.bid_price) or price
                ask = _safe_float(quote.ask_price) or price
                volume = _safe_int(quote.volume)

                # Calculate change from previous close
                close_price = _safe_float(quote.close_price)
                if close_price is None or close_price == 0:
                    close_price = self.last_prices.get(symbol)

                change = 0.0
                change_pct = 0.0

                if close_price and close_price > 0:
                    change = price - close_price
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

        except Exception as e:
            print(f"Update error: {e}")
            self.logger.error(f"Price update error: {e}")
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
        """Tear down subscriptions and close the Web API connection"""
        try:
            if self.timer and self.timer.isActive():
                self.timer.stop()

            if self.market_data_manager:
                try:
                    self.market_data_manager.stop()
                finally:
                    self.market_data_manager = None

            self.connected = False
            self.subscriptions.clear()
            self.connection_status.emit(False, "Web API DISCONNECTED")
            print("🔌 Web API disconnected")

        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
            self.error_occurred.emit(f"Disconnect error: {e}")


def patch_dashboard_with_ib_data(dashboard):
    """
    Patch dashboard with IBKR Web API real-time data.

    Migration Note: Now uses Web API instead of IB Gateway/TWS.
    """
    print("🔥 Patching dashboard with Web API real-time data...")

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
        dashboard.add_system_log("✅ Web API REAL DATA CONNECTED")

    return connector
