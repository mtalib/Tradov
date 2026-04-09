#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT128_ZSeries.py
Purpose: Coverage tests for SpyderZ_Communication — key modules (Z00, Z01, Z02)

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-04-03 Time: 00:00:00
"""

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
import os
import sys
import types
import logging
import unittest
from unittest.mock import MagicMock

logging.disable(logging.CRITICAL)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _ensure_mod(key):
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        anc = ".".join(parts[:i])
        if anc not in sys.modules:
            sys.modules[anc] = types.ModuleType(anc)
    return sys.modules[key]


# ---- Spyder utility stubs ---------------------------------------------------
class _Logger:
    @staticmethod
    def get_logger(name=""):
        return logging.getLogger(name)

for _k in ("Spyder.SpyderU_Utilities.SpyderU01_Logger",
           "SpyderU_Utilities.SpyderU01_Logger"):
    _m = _ensure_mod(_k)
    _m.SpyderLogger = _Logger

for _k in ("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
           "SpyderU_Utilities.SpyderU02_ErrorHandler"):
    _m = _ensure_mod(_k)
    _m.SpyderErrorHandler = type("SpyderErrorHandler", (), {})

# ---- zmq stub (Z01 imports zmq at module level) -----------------------------
if "zmq" not in sys.modules:
    _zmq = types.ModuleType("zmq")
    _zmq.Context = MagicMock
    _zmq.Socket = MagicMock
    _zmq.PUB = 1
    _zmq.SUB = 2
    _zmq.PUSH = 8
    _zmq.PULL = 7
    _zmq.REQ = 3
    _zmq.REP = 4
    _zmq.DEALER = 5
    _zmq.ROUTER = 6
    _zmq.SUBSCRIBE = 6
    _zmq.NOBLOCK = 1
    _zmq.EAGAIN = 11
    _zmq.ZMQError = type("ZMQError", (Exception,), {})
    _zmq.Again = type("Again", (Exception,), {})
    sys.modules["zmq"] = _zmq

# ---- Z-series package pre-stub ----------------------------------------------
_z_path = os.path.join(_ROOT, "Spyder", "SpyderZ_Communication")
_z_pkg = sys.modules.setdefault("Spyder.SpyderZ_Communication",
                                  types.ModuleType("Spyder.SpyderZ_Communication"))
_z_pkg.__path__ = [_z_path]
_z_pkg.__package__ = "Spyder.SpyderZ_Communication"
_z_pkg.__file__ = os.path.join(_z_path, "__init__.py")


# ==============================================================================
# Z00 — BrokerProtocol (pure Protocol + enums + dataclasses)
# ==============================================================================
from Spyder.SpyderZ_Communication.SpyderZ00_BrokerProtocol import (
    OrderSide,
    OrderType,
    NormalizedOrderRequest,
    NormalizedOrderResult,
    BrokerClientProtocol,
    OrderRouterProtocol,
)


class TestZ00OrderSideEnum(unittest.TestCase):
    def test_members(self):
        for name in ("BUY", "SELL", "BUY_TO_OPEN", "BUY_TO_CLOSE",
                     "SELL_TO_OPEN", "SELL_TO_CLOSE"):
            self.assertTrue(hasattr(OrderSide, name), f"Missing: {name}")


class TestZ00OrderTypeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("MARKET", "LIMIT", "STOP", "STOP_LIMIT", "DEBIT", "CREDIT"):
            self.assertTrue(hasattr(OrderType, name), f"Missing: {name}")


class TestZ00Dataclasses(unittest.TestCase):
    def test_order_request_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(NormalizedOrderRequest))

    def test_order_result_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(NormalizedOrderResult))

    def test_order_request_fields(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(NormalizedOrderRequest)}
        for name in ("symbol", "side", "order_type", "quantity"):
            self.assertIn(name, fields)


class TestZ00Protocols(unittest.TestCase):
    def test_broker_protocol_callable(self):
        self.assertTrue(callable(BrokerClientProtocol))

    def test_order_router_protocol_callable(self):
        self.assertTrue(callable(OrderRouterProtocol))


# ==============================================================================
# Z01 — ZeroMQIntegration
# ==============================================================================
from Spyder.SpyderZ_Communication.SpyderZ01_ZeroMQIntegration import (
    MessageType,
    ConnectionState,
    CircuitBreakerState,
    SpyderMessage,
    SpyderPublisher,
    SpyderSubscriber,
)


class TestZ01MessageTypeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("MARKET_DATA", "TRADE_ORDER", "TRADE_FILL",
                     "RISK_UPDATE", "STRATEGY_SIGNAL", "SYSTEM_STATUS"):
            self.assertTrue(hasattr(MessageType, name), f"Missing: {name}")


class TestZ01ConnectionStateEnum(unittest.TestCase):
    def test_members(self):
        for name in ("DISCONNECTED", "CONNECTING", "CONNECTED", "RECONNECTING", "FAILED"):
            self.assertTrue(hasattr(ConnectionState, name), f"Missing: {name}")


class TestZ01CircuitBreakerStateEnum(unittest.TestCase):
    def test_members(self):
        for name in ("CLOSED", "OPEN", "HALF_OPEN"):
            self.assertTrue(hasattr(CircuitBreakerState, name), f"Missing: {name}")


class TestZ01SpyderMessage(unittest.TestCase):
    def test_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(SpyderMessage))


class TestZ01PublisherSubscriber(unittest.TestCase):
    def test_publisher_callable(self):
        self.assertTrue(callable(SpyderPublisher))

    def test_subscriber_callable(self):
        self.assertTrue(callable(SpyderSubscriber))


# ==============================================================================
# Z02 — MessageProtocol
# ==============================================================================
from Spyder.SpyderZ_Communication.SpyderZ02_MessageProtocol import (
    SerializationFormat,
    MessageCategory,
    ValidationLevel,
    MessageMetadata,
    ProtocolMessage,
    SchemaValidator,
    SerializationManager,
)


class TestZ02SerializationFormatEnum(unittest.TestCase):
    def test_members(self):
        for name in ("JSON", "MSGPACK", "COMPRESSED_JSON"):
            self.assertTrue(hasattr(SerializationFormat, name), f"Missing: {name}")


class TestZ02MessageCategoryEnum(unittest.TestCase):
    def test_members(self):
        for name in ("MARKET", "TRADE", "RISK", "SYSTEM", "STRATEGY", "ACCOUNT"):
            self.assertTrue(hasattr(MessageCategory, name), f"Missing: {name}")


class TestZ02ValidationLevelEnum(unittest.TestCase):
    def test_members(self):
        for name in ("NONE", "BASIC", "STANDARD", "STRICT"):
            self.assertTrue(hasattr(ValidationLevel, name), f"Missing: {name}")


class TestZ02Dataclasses(unittest.TestCase):
    def test_message_metadata_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(MessageMetadata))

    def test_protocol_message_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(ProtocolMessage))


class TestZ02Classes(unittest.TestCase):
    def test_schema_validator_callable(self):
        self.assertTrue(callable(SchemaValidator))

    def test_serialization_manager_callable(self):
        self.assertTrue(callable(SerializationManager))


# ==============================================================================
if __name__ == "__main__":
    unittest.main()
