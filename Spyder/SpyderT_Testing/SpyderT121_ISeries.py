#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT121_ISeries.py
Purpose: Coverage tests for SpyderI_Integration — key modules (I01, I02, I06, I10)

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
import asyncio
import threading
import unittest
from unittest.mock import patch

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


# ---- Spyder root + SpyderA_Core: set __path__ so real submodule files load --
_spyder_path = os.path.join(_ROOT, "Spyder")
_spyder_pkg = sys.modules.setdefault("Spyder", types.ModuleType("Spyder"))
_spyder_pkg.__path__ = [_spyder_path]
_spyder_pkg.__package__ = "Spyder"

_a_path = os.path.join(_spyder_path, "SpyderA_Core")
_a_pkg = sys.modules.setdefault("Spyder.SpyderA_Core", types.ModuleType("Spyder.SpyderA_Core"))
_a_pkg.__path__ = [_a_path]
_a_pkg.__package__ = "Spyder.SpyderA_Core"
_a_pkg.__file__ = os.path.join(_a_path, "__init__.py")


# ---- SpyderLogger / SpyderErrorHandler stubs --------------------------------
class _Logger:
    @staticmethod
    def get_logger(name=""):
        return logging.getLogger(name)

for _k in ("Spyder.SpyderU_Utilities.SpyderU01_Logger",
           "Spyder.SpyderU_Utilities.SpyderU01_Logger"):
    _m = _ensure_mod(_k)
    _m.SpyderLogger = _Logger

for _k in ("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
           "Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"):
    _m = _ensure_mod(_k)
    _m.SpyderErrorHandler = type("SpyderErrorHandler", (), {})

# ---- I-series package pre-stub ----------------------------------------------
_i_path = os.path.join(_ROOT, "Spyder", "SpyderI_Integration")
_i_pkg = sys.modules.setdefault("Spyder.SpyderI_Integration",
                                  types.ModuleType("Spyder.SpyderI_Integration"))
_i_pkg.__path__ = [_i_path]
_i_pkg.__package__ = "Spyder.SpyderI_Integration"
_i_pkg.__file__ = os.path.join(_i_path, "__init__.py")


# ==============================================================================
# I01 — IntegrationHub
# ==============================================================================
from Spyder.SpyderI_Integration.SpyderI01_IntegrationHub import (
    ModuleState,
    IntegrationLevel,
    HealthStatus,
    IntegrationHub,
)


class TestI01ModuleStateEnum(unittest.TestCase):
    def test_members(self):
        for name in ("UNKNOWN", "DISCOVERED", "LOADING", "LOADED", "INITIALIZING"):
            self.assertTrue(hasattr(ModuleState, name), f"Missing: {name}")


class TestI01IntegrationLevelEnum(unittest.TestCase):
    def test_members(self):
        for name in ("STANDALONE", "BASIC", "INTEGRATED", "ADVANCED", "ECOSYSTEM"):
            self.assertTrue(hasattr(IntegrationLevel, name), f"Missing: {name}")


class TestI01HealthStatusEnum(unittest.TestCase):
    def test_members(self):
        for name in ("HEALTHY", "WARNING", "CRITICAL", "OFFLINE", "UNKNOWN"):
            self.assertTrue(hasattr(HealthStatus, name), f"Missing: {name}")


class TestI01IntegrationHubClass(unittest.TestCase):
    def test_existsÍ(self):
        self.assertTrue(callable(IntegrationHub))


# ==============================================================================
# I02 — EventRouter
# ==============================================================================
from Spyder.SpyderI_Integration.SpyderI02_EventRouter import (
    RoutingStrategy,
    EventPriority,
    HandlerState,
    EventRouter,
)


class TestI02RoutingStrategyEnum(unittest.TestCase):
    def test_members(self):
        for name in ("BROADCAST", "ROUND_ROBIN", "PRIORITY", "FAILOVER"):
            self.assertTrue(hasattr(RoutingStrategy, name), f"Missing: {name}")


class TestI02EventPriorityEnum(unittest.TestCase):
    def test_members(self):
        for name in ("LOW", "NORMAL", "HIGH", "CRITICAL", "URGENT"):
            self.assertTrue(hasattr(EventPriority, name), f"Missing: {name}")


class TestI02HandlerStateEnum(unittest.TestCase):
    def test_members(self):
        for name in ("HEALTHY", "SLOW", "OVERLOADED", "DISABLED"):
            self.assertTrue(hasattr(HandlerState, name), f"Missing: {name}")


class TestI02EventRouterClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(EventRouter))


# ==============================================================================
# I06 — AgentMessageBus
# ==============================================================================
from Spyder.SpyderI_Integration.SpyderI06_AgentMessageBus import (
    Message,
    MessagePriority,
    MessageType,
    DeliveryMode,
    AgentMessageBus,
    create_message_bus,
)


class TestI06MessagePriorityEnum(unittest.TestCase):
    def test_members(self):
        for name in ("CRITICAL", "HIGH", "NORMAL", "LOW", "BULK"):
            self.assertTrue(hasattr(MessagePriority, name), f"Missing: {name}")


class TestI06MessageTypeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("PUBLISH", "REQUEST", "REPLY", "BROADCAST", "COMMAND"):
            self.assertTrue(hasattr(MessageType, name), f"Missing: {name}")


class TestI06DeliveryModeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("AT_MOST_ONCE", "AT_LEAST_ONCE", "EXACTLY_ONCE"):
            self.assertTrue(hasattr(DeliveryMode, name), f"Missing: {name}")


class TestI06Factory(unittest.TestCase):
    def test_create_message_bus_callable(self):
        self.assertTrue(callable(create_message_bus))


class TestI06PublishCompatibility(unittest.TestCase):
    def test_publish_accepts_message_object_sync(self):
        bus = AgentMessageBus(config={"persist": False})
        received = threading.Event()
        seen: dict[str, object] = {}
        try:
            def _callback(message: Message):
                seen["topic"] = message.topic
                seen["payload"] = message.payload
                received.set()

            bus.subscribe("phase0-sub-msg", ["phase0.message_object"], _callback)

            msg = Message(
                topic="phase0.message_object",
                sender="phase0_tester",
                priority=MessagePriority.HIGH,
                payload={"ok": True},
            )
            receipt = bus.publish(msg)

            self.assertEqual(str(receipt), msg.id)
            self.assertTrue(received.wait(1.0), "Expected message delivery")
            self.assertEqual(seen.get("topic"), "phase0.message_object")
            self.assertEqual(seen.get("payload"), {"ok": True})
        finally:
            bus.shutdown()

    def test_shadow_validation_flags_missing_required_envelope(self):
        bus = AgentMessageBus(config={"persist": False, "shadow_validation_agent_handoffs": True})
        received = threading.Event()
        seen_headers: dict[str, object] = {}
        try:
            def _callback(message: Message):
                seen_headers.update(message.headers or {})
                received.set()

            bus.subscribe("phase1-sub-missing", ["meta.decisions"], _callback)
            bus.publish(
                topic="meta.decisions",
                payload={"decision_id": "phase1-missing"},
                sender="phase1_sender",
                priority=MessagePriority.HIGH,
            )

            self.assertTrue(received.wait(1.0), "Expected message delivery")
            shadow = (seen_headers.get("shadow_validation") or {}).get("publish", {})
            self.assertTrue(shadow.get("checked"))
            self.assertFalse(shadow.get("valid"))
            self.assertEqual(shadow.get("error"), "missing_agent_handoff_envelope")
        finally:
            bus.shutdown()

    def test_shadow_validation_marks_valid_envelope(self):
        from Spyder.SpyderZ_Communication.SpyderZ02_MessageProtocol import (
            build_agent_handoff_envelope,
        )

        bus = AgentMessageBus(config={"persist": False, "shadow_validation_agent_handoffs": True})
        received = threading.Event()
        seen_headers: dict[str, object] = {}
        try:
            def _callback(message: Message):
                seen_headers.update(message.headers or {})
                received.set()

            bus.subscribe("phase1-sub-valid", ["meta.decisions"], _callback)

            legacy_payload = {
                "decision_id": "phase1-valid",
                "action": "hold",
            }
            envelope = build_agent_handoff_envelope(
                topic="meta.decisions",
                producer_agent_id="phase1_sender",
                schema="AGENT_DECISION_V1",
                handoff_type="decision",
                payload=legacy_payload,
                confidence=0.61,
                reasoning="phase1 validation test",
                decision={
                    "action": "hold",
                    "confidence": 0.61,
                    "reasoning": "phase1 validation test",
                },
                legacy_payload=legacy_payload,
            )

            bus.publish(
                topic="meta.decisions",
                payload={
                    **legacy_payload,
                    "agent_handoff": envelope,
                },
                sender="phase1_sender",
                priority=MessagePriority.HIGH,
            )

            self.assertTrue(received.wait(1.0), "Expected message delivery")
            shadow_publish = (seen_headers.get("shadow_validation") or {}).get("publish", {})
            shadow_consume = (seen_headers.get("shadow_validation") or {}).get("consume", {})
            self.assertTrue(shadow_publish.get("checked"))
            self.assertTrue(shadow_publish.get("valid"))
            self.assertEqual(shadow_publish.get("schema"), "AGENT_DECISION_V1")
            self.assertTrue(shadow_consume.get("valid"))
        finally:
            bus.shutdown()

    def test_publish_topic_payload_sender_is_awaitable(self):
        bus = AgentMessageBus(config={"persist": False})
        received = threading.Event()
        seen: dict[str, object] = {}
        try:
            def _callback(message: Message):
                seen["sender"] = message.sender
                seen["payload"] = message.payload
                received.set()

            bus.subscribe("phase0-sub-topic", ["phase0.topic_style"], _callback)

            receipt = bus.publish(
                topic="phase0.topic_style",
                payload={"value": 7},
                sender="phase0_sender",
                priority=MessagePriority.NORMAL,
            )

            self.assertTrue(hasattr(receipt, "__await__"))

            async def _await_receipt():
                return await receipt

            awaited_id = asyncio.run(_await_receipt())

            self.assertEqual(awaited_id, str(receipt))
            self.assertTrue(received.wait(1.0), "Expected message delivery")
            self.assertEqual(seen.get("sender"), "phase0_sender")
            self.assertEqual(seen.get("payload"), {"value": 7})
        finally:
            bus.shutdown()

    def test_policy_enforcement_allows_execution_advisory_signal(self):
        policy = {
            "enforcement": {
                "paper_mode": True,
                "live_mode": False,
                "default_action_paper": "deny",
                "default_action_live": "allow",
                "enforce_sender_patterns": ["Y[0-9][0-9]_*"],
                "enforce_topic_prefixes": ["signals.", "execution."],
                "enforce_topics": ["signals.validated"],
            },
            "role_bindings": {
                "Y02_*": "execution_advisory",
            },
            "role_permissions": {
                "execution_advisory": {
                    "allow_topics": ["signals.validated"],
                    "allow_actions": ["signal"],
                    "deny_topics": ["execution.*"],
                    "deny_actions": ["execute", "execution_order"],
                }
            },
        }

        bus = AgentMessageBus(
            config={
                "persist": False,
                "shadow_validation_agent_handoffs": False,
                "agent_handoff_policy": policy,
                "trading_mode": "paper",
            }
        )
        received = threading.Event()
        seen_headers: dict[str, object] = {}
        try:
            def _callback(message: Message):
                seen_headers.update(message.headers or {})
                received.set()

            bus.subscribe("phase2-policy-allow", ["signals.validated"], _callback)
            bus.publish(
                topic="signals.validated",
                payload={"output_type": "signal", "validation": {"approved": True}},
                sender="Y02_strategy_pilot",
                priority=MessagePriority.HIGH,
            )

            self.assertTrue(received.wait(1.0), "Expected policy-allowed message delivery")
            policy_header = (seen_headers.get("policy_enforcement") or {}).get("publish", {})
            self.assertTrue(policy_header.get("allowed"))
            self.assertEqual(policy_header.get("reason_code"), "allowed")
            self.assertEqual(bus.policy_enforcement_stats["blocked"], 0)
        finally:
            bus.shutdown()

    def test_policy_enforcement_blocks_disallowed_execution_action(self):
        policy = {
            "enforcement": {
                "paper_mode": True,
                "live_mode": False,
                "default_action_paper": "deny",
                "default_action_live": "allow",
                "enforce_sender_patterns": ["Y[0-9][0-9]_*"],
                "enforce_topic_prefixes": ["signals.", "execution."],
                "enforce_topics": ["signals.validated"],
            },
            "role_bindings": {
                "Y02_*": "execution_advisory",
            },
            "role_permissions": {
                "execution_advisory": {
                    "allow_topics": ["signals.validated", "execution.intent"],
                    "allow_actions": ["signal", "execution_advice"],
                    "deny_topics": ["execution.orders"],
                    "deny_actions": ["execute", "execution_order"],
                }
            },
        }

        bus = AgentMessageBus(
            config={
                "persist": False,
                "shadow_validation_agent_handoffs": False,
                "agent_handoff_policy": policy,
                "trading_mode": "paper",
            }
        )
        received = threading.Event()
        try:
            def _callback(message: Message):
                received.set()

            bus.subscribe("phase2-policy-deny", ["execution.orders"], _callback)
            bus.publish(
                topic="execution.orders",
                payload={"output_type": "execute", "symbol": "SPY"},
                sender="Y02_strategy_pilot",
                priority=MessagePriority.HIGH,
            )

            self.assertFalse(received.wait(0.4), "Blocked message should not be delivered")
            dead_letters = bus.get_dead_letters(limit=1)
            self.assertTrue(dead_letters, "Blocked publish should be sent to dead letter queue")
            self.assertTrue(str(dead_letters[0].get("reason", "")).startswith("policy_denied:"))
            self.assertEqual(bus.policy_enforcement_stats["blocked"], 1)
        finally:
            bus.shutdown()

    def test_trading_mode_does_not_infer_live_from_tradier_environment(self):
        with patch.dict(
            os.environ,
            {
                "TRADIER_ENVIRONMENT": "production",
                "TRADING_MODE": "",
                "SPYDER_TRADING_MODE": "",
            },
            clear=False,
        ):
            bus = AgentMessageBus(
                config={
                    "persist": False,
                    "shadow_validation_agent_handoffs": False,
                }
            )
            try:
                self.assertEqual(bus.trading_mode, "paper")
            finally:
                bus.shutdown()


class TestZ02AgentHandoffSchemas(unittest.TestCase):
    def test_decision_envelope_validation(self):
        from Spyder.SpyderZ_Communication.SpyderZ02_MessageProtocol import (
            build_agent_handoff_envelope,
            validate_agent_handoff_envelope,
        )

        payload = {"action": "buy", "strategy": "IronCondor"}
        envelope = build_agent_handoff_envelope(
            topic="meta.decisions",
            producer_agent_id="Y08_meta_orchestrator",
            schema="AGENT_DECISION_V1",
            handoff_type="decision",
            payload=payload,
            confidence=0.75,
            reasoning="validated by tests",
            decision={
                "action": "buy",
                "confidence": 0.75,
                "reasoning": "validated by tests",
            },
            legacy_payload=payload,
        )

        valid, error = validate_agent_handoff_envelope(envelope, "AGENT_DECISION_V1")
        self.assertTrue(valid)
        self.assertIsNone(error)


# ==============================================================================
# I10 — DiagnosticsEngine_Types
# ==============================================================================
from Spyder.SpyderI_Integration.SpyderI10_DiagnosticsEngine_Types import (
    HealthStatus as DiagHealthStatus,
    DiagnosticCategory,
    ProblemSeverity,
    SystemMetrics,
    NetworkMetrics,
    DiagnosticIssue,
)


class TestI10DiagHealthStatusEnum(unittest.TestCase):
    def test_members(self):
        for name in ("EXCELLENT", "GOOD", "WARNING", "CRITICAL", "FAILING"):
            self.assertTrue(hasattr(DiagHealthStatus, name), f"Missing: {name}")


class TestI10DiagnosticCategoryEnum(unittest.TestCase):
    def test_members(self):
        for name in ("SYSTEM", "NETWORK", "MODULES", "INTEGRATION", "PERFORMANCE"):
            self.assertTrue(hasattr(DiagnosticCategory, name), f"Missing: {name}")


class TestI10ProblemSeverityEnum(unittest.TestCase):
    def test_members(self):
        for name in ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"):
            self.assertTrue(hasattr(ProblemSeverity, name), f"Missing: {name}")


class TestI10Dataclasses(unittest.TestCase):
    def test_system_metrics_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(SystemMetrics))

    def test_network_metrics_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(NetworkMetrics))

    def test_diagnostic_issue_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(DiagnosticIssue))


# ==============================================================================
if __name__ == "__main__":
    unittest.main()
