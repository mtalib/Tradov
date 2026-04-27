#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB20_IntegratedConnectivityManager.py
Purpose: Integrated connectivity manager for broker and data-feed connections.

Author: Spyder Team
Year Created: 2025
Last Updated: 2026-04-18 Time: 00:00:00

Module Description:
    Provides ConnectivityState enum and IntegratedConnectivityManager class
    used by SpyderD31_StrategyOrchestrator and other modules that need a
    unified view of broker/data-feed connectivity.

    This is a functional stub.  Replace with full implementation (TLS handshake,
    heartbeat monitoring, reconnect back-off) when a dedicated connectivity layer
    is required.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
from enum import Enum
from typing import Any

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


# ==============================================================================
# ENUMS
# ==============================================================================


class ConnectivityState(Enum):
    """Lifecycle states for a managed connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    DEGRADED = "degraded"
    RECONNECTING = "reconnecting"
    ERROR = "error"


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class IntegratedConnectivityManager:
    """Manages connectivity state for broker and data-feed clients.

    Args:
        broker_client: Optional broker client instance (e.g. B40 TradierClient).
        data_client: Optional market-data client instance (e.g. C27 MassiveClient).
        config: Optional configuration dict.

    Example:
        >>> mgr = IntegratedConnectivityManager(broker_client=tradier)
        >>> mgr.connect()
        True
        >>> mgr.is_connected()
        True
    """

    def __init__(
        self,
        broker_client: Any = None,
        data_client: Any = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.logger = SpyderLogger.get_logger(__name__)
        self.broker_client = broker_client
        self.data_client = data_client
        self.config = config or {}

        self._state = ConnectivityState.DISCONNECTED
        self._lock = threading.Lock()

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------

    @property
    def state(self) -> ConnectivityState:
        """Current connectivity state."""
        with self._lock:
            return self._state

    # --------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------

    def connect(self) -> bool:
        """Attempt to connect all managed clients.

        Returns:
            True if all clients connected successfully, False otherwise.
        """
        with self._lock:
            try:
                self._state = ConnectivityState.CONNECTING

                # Connect broker client if present
                if self.broker_client is not None:
                    if hasattr(self.broker_client, "connect"):
                        self.broker_client.connect()
                    elif not hasattr(self.broker_client, "is_connected"):
                        self.logger.warning(
                            "Broker client has no connect() or is_connected() — "
                            "assuming already connected"
                        )

                # Connect data client if present
                if self.data_client is not None:
                    if hasattr(self.data_client, "connect"):
                        self.data_client.connect()

                self._state = ConnectivityState.CONNECTED
                self.logger.info("IntegratedConnectivityManager: connected")
                return True

            except Exception as exc:
                self._state = ConnectivityState.ERROR
                self.logger.error("Connection failed: %s", exc, exc_info=True)
                return False

    def disconnect(self) -> None:
        """Disconnect all managed clients."""
        with self._lock:
            try:
                if self.broker_client is not None and hasattr(self.broker_client, "disconnect"):
                    self.broker_client.disconnect()
                if self.data_client is not None and hasattr(self.data_client, "disconnect"):
                    self.data_client.disconnect()
                self._state = ConnectivityState.DISCONNECTED
                self.logger.info("IntegratedConnectivityManager: disconnected")
            except Exception as exc:
                self.logger.error("Disconnect error: %s", exc, exc_info=True)
                self._state = ConnectivityState.ERROR

    def is_connected(self) -> bool:
        """Return True if the manager is in a connected/authenticated state."""
        return self._state in (
            ConnectivityState.CONNECTED,
            ConnectivityState.AUTHENTICATED,
        )

    def get_state(self) -> ConnectivityState:
        """Return the current ConnectivityState."""
        return self.state

    def heartbeat(self) -> bool:
        """Perform a connectivity health-check.

        Returns:
            True if all reachable clients report healthy, False otherwise.
        """
        try:
            broker_ok = True
            if self.broker_client is not None and hasattr(self.broker_client, "heartbeat"):
                broker_ok = bool(self.broker_client.heartbeat())
            elif self.broker_client is not None and hasattr(self.broker_client, "is_connected"):
                broker_ok = bool(self.broker_client.is_connected())

            data_ok = True
            if self.data_client is not None and hasattr(self.data_client, "is_connected"):
                data_ok = bool(self.data_client.is_connected())

            return broker_ok and data_ok
        except Exception as exc:
            self.logger.warning("Heartbeat error: %s", exc)
            return False

    def get_status(self) -> dict[str, Any]:
        """Return a status summary dict for monitoring dashboards."""
        return {
            "state": self._state.value,
            "is_connected": self.is_connected(),
            "broker_client": type(self.broker_client).__name__ if self.broker_client else None,
            "data_client": type(self.data_client).__name__ if self.data_client else None,
        }
