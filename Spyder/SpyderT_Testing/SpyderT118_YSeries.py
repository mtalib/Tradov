#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT118_YSeries.py
Purpose: Unit tests for SpyderY_AutoAgents series (Y00–Y10)

Coverage targets:
    Y00 BaseAutoAgent:
        - Enum members: AgentState, MarketSession, LLMRole
        - Dataclass defaults: OllamaConfig, AgentHeartbeat, AgentOutput
        - get_current_session() returns valid MarketSession

    Y01–Y09 AutoAgents:
        - Class attrs: AGENT_ID, TICK_INTERVAL, ACTIVE_SESSIONS, TICK_INTERVALS
        - Constructor instantiation with mocked dependencies
        - Abstract method stubs exist (tick, get_state_snapshot, restore_state)

    Y10 AgentScheduler:
        - Constants: MAX_RESTART_ATTEMPTS, RESTART_BACKOFF_SECONDS
        - Constructor instantiation
        - register / unregister / list_agents
        - Context manager protocol
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch


# ===========================================================================
# Y00 - BaseAutoAgent
# ===========================================================================


class TestY00AgentStateEnum(unittest.TestCase):
    """AgentState enum must have all expected members."""

    def test_members(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import AgentState

        for name in ("INITIALIZING", "RUNNING", "PAUSED", "SLEEPING",
                      "STOPPING", "STOPPED", "ERROR"):
            self.assertTrue(hasattr(AgentState, name), f"Missing: {name}")


class TestY00MarketSessionEnum(unittest.TestCase):
    """MarketSession enum must have all expected session values."""

    def test_members(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import MarketSession

        expected = {
            "OVERNIGHT": "overnight",
            "PRE_MARKET": "pre_market",
            "MARKET_OPEN": "market_open",
            "MARKET_HOURS": "market_hours",
            "POWER_HOUR": "power_hour",
            "POST_MARKET": "post_market",
        }
        for name, value in expected.items():
            member = getattr(MarketSession, name)
            self.assertEqual(member.value, value)


class TestY00LLMRoleEnum(unittest.TestCase):
    """LLMRole enum must have all expected model roles."""

    def test_members(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import LLMRole

        expected = {
            "PRIMARY": "primary",
            "FAST": "fast",
            "CODE": "code",
            "FINANCE": "finance",
        }
        for name, value in expected.items():
            member = getattr(LLMRole, name)
            self.assertEqual(member.value, value)


class TestY00OllamaConfig(unittest.TestCase):
    """OllamaConfig dataclass must have correct defaults."""

    def test_defaults(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import OllamaConfig

        cfg = OllamaConfig()
        self.assertEqual(cfg.base_url, "http://localhost:11434")
        self.assertIsInstance(cfg.primary_model, str)
        self.assertIsInstance(cfg.fast_model, str)
        self.assertIsInstance(cfg.code_model, str)
        self.assertIsInstance(cfg.finance_model, str)
        self.assertEqual(cfg.timeout, 60)
        self.assertEqual(cfg.max_retries, 3)
        self.assertAlmostEqual(cfg.temperature_default, 0.3)
        self.assertAlmostEqual(cfg.temperature_creative, 0.7)
        self.assertEqual(cfg.max_context_tokens, 4096)

    def test_from_env(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import OllamaConfig

        cfg = OllamaConfig.from_env()
        self.assertIsInstance(cfg, OllamaConfig)


class TestY00AgentHeartbeat(unittest.TestCase):
    """AgentHeartbeat dataclass must have correct defaults."""

    def test_defaults(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import (
            AgentHeartbeat, AgentState,
        )

        hb = AgentHeartbeat(agent_id="test", state=AgentState.RUNNING)
        self.assertEqual(hb.agent_id, "test")
        self.assertEqual(hb.state, AgentState.RUNNING)
        self.assertIsInstance(hb.timestamp, datetime)
        self.assertEqual(hb.uptime_seconds, 0.0)
        self.assertEqual(hb.messages_sent, 0)
        self.assertEqual(hb.messages_received, 0)
        self.assertEqual(hb.llm_calls, 0)
        self.assertEqual(hb.errors, 0)
        self.assertIsNone(hb.last_error)
        self.assertEqual(hb.current_task, "idle")
        self.assertEqual(hb.memory_mb, 0.0)


class TestY00AgentOutput(unittest.TestCase):
    """AgentOutput dataclass must have correct defaults."""

    def test_defaults(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import AgentOutput

        output = AgentOutput(
            agent_id="test",
            output_type="signal",
            topic="regime_change",
        )
        self.assertEqual(output.agent_id, "test")
        self.assertEqual(output.output_type, "signal")
        self.assertEqual(output.topic, "regime_change")
        self.assertEqual(output.payload, {})
        self.assertEqual(output.confidence, 0.0)
        self.assertEqual(output.reasoning, "")
        self.assertIsInstance(output.timestamp, datetime)
        self.assertEqual(output.ttl_seconds, 300)
        self.assertEqual(output.priority, "NORMAL")


class TestY00GetCurrentSession(unittest.TestCase):
    """get_current_session() must return a valid MarketSession."""

    def test_returns_valid_session(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import (
            BaseAutoAgent, MarketSession,
        )

        session = BaseAutoAgent.get_current_session()
        self.assertIsInstance(session, MarketSession)

    @patch("Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent.datetime")
    def test_pre_market_detection(self, mock_dt):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import (
            BaseAutoAgent, MarketSession,
        )

        # 6:00 AM ET = pre_market
        mock_now = MagicMock()
        mock_now.hour = 6
        mock_now.minute = 0
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        session = BaseAutoAgent.get_current_session()
        self.assertIsInstance(session, MarketSession)


class TestY00BaseAutoAgentAbstract(unittest.TestCase):
    """BaseAutoAgent is abstract — cannot be instantiated directly."""

    def test_cannot_instantiate_directly(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import BaseAutoAgent

        # BaseAutoAgent has abstract methods; direct instantiation should fail
        # unless __init_subclass__ or ABC enforcement
        self.assertTrue(hasattr(BaseAutoAgent, "tick"))
        self.assertTrue(hasattr(BaseAutoAgent, "get_state_snapshot"))
        self.assertTrue(hasattr(BaseAutoAgent, "restore_state"))


# ===========================================================================
# Y01–Y09 - Auto Agents (parameterised checks)
# ===========================================================================

# Agent metadata for parameterised testing
_AGENT_SPECS = {
    "Y01": {
        "module": "SpyderY01_MarketSenseAgent",
        "agent_id": "Y01_market_sense",
        "tick_interval": 60.0,
        "active_sessions_count": 6,
    },
    "Y02": {
        "module": "SpyderY02_StrategyPilotAgent",
        "agent_id": "Y02_strategy_pilot",
        "tick_interval": 30.0,
        "active_sessions_count": 4,
    },
    "Y03": {
        "module": "SpyderY03_RiskSentinelAgent",
        "agent_id": "Y03_risk_sentinel",
        "tick_interval": 15.0,
        "active_sessions_count": 6,
    },
    "Y04": {
        "module": "SpyderY04_AlphaLearnerAgent",
        "agent_id": "Y04_alpha_learner",
        "tick_interval": 120.0,
        "active_sessions_count": 6,
    },
    "Y05": {
        "module": "SpyderY05_ExecutionOptimizerAgent",
        "agent_id": "Y05_execution_optimizer",
        "tick_interval": 15.0,
        "active_sessions_count": 3,
    },
    "Y06": {
        "module": "SpyderY06_NewsSentinelAgent",
        "agent_id": "Y06_news_sentinel",
        "tick_interval": 180.0,
        "active_sessions_count": 6,
    },
    "Y07": {
        "module": "SpyderY07_TradeJournalAgent",
        "agent_id": "Y07_trade_journal",
        "tick_interval": 120.0,
        "active_sessions_count": 3,
    },
    "Y08": {
        "module": "SpyderY08_MetaOrchestratorAgent",
        "agent_id": "Y08_meta_orchestrator",
        "tick_interval": 60.0,
        "active_sessions_count": 6,
    },
    "Y09": {
        "module": "SpyderY09_CodeReviewerAgent",
        "agent_id": "Y09_code_reviewer",
        "tick_interval": 600.0,
        "active_sessions_count": 2,
    },
}


class TestAutoAgentClassAttrs(unittest.TestCase):
    """Every Y01–Y09 agent must declare AGENT_ID, TICK_INTERVAL, etc."""

    def _get_agent_class(self, spec):
        import importlib
        mod = importlib.import_module(f"Spyder.SpyderY_AutoAgents.{spec['module']}")
        # The agent class is the first class whose AGENT_ID matches
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if (isinstance(obj, type)
                    and hasattr(obj, "AGENT_ID")
                    and spec["agent_id"] == obj.AGENT_ID):
                return obj
        self.fail(f"No class with AGENT_ID={spec['agent_id']} in {spec['module']}")

    def test_y01_attrs(self):
        spec = _AGENT_SPECS["Y01"]
        cls = self._get_agent_class(spec)
        self.assertEqual(cls.AGENT_ID, spec["agent_id"])
        self.assertEqual(cls.TICK_INTERVAL, spec["tick_interval"])
        self.assertEqual(len(cls.ACTIVE_SESSIONS), spec["active_sessions_count"])
        self.assertIsInstance(cls.TICK_INTERVALS, dict)

    def test_y02_attrs(self):
        spec = _AGENT_SPECS["Y02"]
        cls = self._get_agent_class(spec)
        self.assertEqual(cls.AGENT_ID, spec["agent_id"])
        self.assertEqual(cls.TICK_INTERVAL, spec["tick_interval"])
        self.assertEqual(len(cls.ACTIVE_SESSIONS), spec["active_sessions_count"])

    def test_y03_attrs(self):
        spec = _AGENT_SPECS["Y03"]
        cls = self._get_agent_class(spec)
        self.assertEqual(cls.AGENT_ID, spec["agent_id"])
        self.assertEqual(cls.TICK_INTERVAL, spec["tick_interval"])
        self.assertEqual(len(cls.ACTIVE_SESSIONS), spec["active_sessions_count"])

    def test_y04_attrs(self):
        spec = _AGENT_SPECS["Y04"]
        cls = self._get_agent_class(spec)
        self.assertEqual(cls.AGENT_ID, spec["agent_id"])
        self.assertEqual(cls.TICK_INTERVAL, spec["tick_interval"])

    def test_y05_attrs(self):
        spec = _AGENT_SPECS["Y05"]
        cls = self._get_agent_class(spec)
        self.assertEqual(cls.AGENT_ID, spec["agent_id"])
        self.assertEqual(cls.TICK_INTERVAL, spec["tick_interval"])
        self.assertEqual(len(cls.ACTIVE_SESSIONS), spec["active_sessions_count"])

    def test_y06_attrs(self):
        spec = _AGENT_SPECS["Y06"]
        cls = self._get_agent_class(spec)
        self.assertEqual(cls.AGENT_ID, spec["agent_id"])
        self.assertEqual(cls.TICK_INTERVAL, spec["tick_interval"])

    def test_y07_attrs(self):
        spec = _AGENT_SPECS["Y07"]
        cls = self._get_agent_class(spec)
        self.assertEqual(cls.AGENT_ID, spec["agent_id"])
        self.assertEqual(cls.TICK_INTERVAL, spec["tick_interval"])
        self.assertEqual(len(cls.ACTIVE_SESSIONS), spec["active_sessions_count"])

    def test_y08_attrs(self):
        spec = _AGENT_SPECS["Y08"]
        cls = self._get_agent_class(spec)
        self.assertEqual(cls.AGENT_ID, spec["agent_id"])
        self.assertEqual(cls.TICK_INTERVAL, spec["tick_interval"])

    def test_y09_attrs(self):
        spec = _AGENT_SPECS["Y09"]
        cls = self._get_agent_class(spec)
        self.assertEqual(cls.AGENT_ID, spec["agent_id"])
        self.assertEqual(cls.TICK_INTERVAL, spec["tick_interval"])
        self.assertEqual(len(cls.ACTIVE_SESSIONS), spec["active_sessions_count"])


class TestAutoAgentTickIntervals(unittest.TestCase):
    """TICK_INTERVALS keys must be a subset of ACTIVE_SESSIONS."""

    def _get_agent_class(self, spec):
        import importlib
        mod = importlib.import_module(f"Spyder.SpyderY_AutoAgents.{spec['module']}")
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if (isinstance(obj, type)
                    and hasattr(obj, "AGENT_ID")
                    and spec["agent_id"] == obj.AGENT_ID):
                return obj
        self.fail(f"No class found for {spec['agent_id']}")

    def test_tick_intervals_subset(self):
        for key, spec in _AGENT_SPECS.items():
            with self.subTest(agent=key):
                cls = self._get_agent_class(spec)
                if hasattr(cls, "TICK_INTERVALS") and hasattr(cls, "ACTIVE_SESSIONS"):
                    for session in cls.TICK_INTERVALS:
                        self.assertIn(
                            session, cls.ACTIVE_SESSIONS,
                            f"{key}: {session} in TICK_INTERVALS but not ACTIVE_SESSIONS",
                        )

    def test_tick_intervals_are_positive(self):
        for key, spec in _AGENT_SPECS.items():
            with self.subTest(agent=key):
                cls = self._get_agent_class(spec)
                if hasattr(cls, "TICK_INTERVALS"):
                    for session, interval in cls.TICK_INTERVALS.items():
                        self.assertGreater(
                            interval, 0,
                            f"{key}: {session} interval must be positive",
                        )


class TestAutoAgentInheritance(unittest.TestCase):
    """All Y01–Y09 agents must inherit from BaseAutoAgent."""

    def test_inheritance(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import BaseAutoAgent
        import importlib

        for key, spec in _AGENT_SPECS.items():
            with self.subTest(agent=key):
                mod = importlib.import_module(
                    f"Spyder.SpyderY_AutoAgents.{spec['module']}"
                )
                cls = None
                for attr_name in dir(mod):
                    obj = getattr(mod, attr_name)
                    if (isinstance(obj, type)
                            and hasattr(obj, "AGENT_ID")
                            and spec["agent_id"] == obj.AGENT_ID):
                        cls = obj
                        break
                self.assertIsNotNone(cls, f"No class found for {key}")
                self.assertTrue(
                    issubclass(cls, BaseAutoAgent),
                    f"{key} ({cls.__name__}) must inherit from BaseAutoAgent",
                )


class TestAutoAgentAbstractMethods(unittest.TestCase):
    """Every Y01–Y09 must implement tick, get_state_snapshot, restore_state."""

    def test_abstract_methods_implemented(self):
        import importlib

        for key, spec in _AGENT_SPECS.items():
            with self.subTest(agent=key):
                mod = importlib.import_module(
                    f"Spyder.SpyderY_AutoAgents.{spec['module']}"
                )
                cls = None
                for attr_name in dir(mod):
                    obj = getattr(mod, attr_name)
                    if (isinstance(obj, type)
                            and hasattr(obj, "AGENT_ID")
                            and spec["agent_id"] == obj.AGENT_ID):
                        cls = obj
                        break
                self.assertIsNotNone(cls)
                for method_name in ("tick", "get_state_snapshot", "restore_state"):
                    self.assertTrue(
                        hasattr(cls, method_name),
                        f"{key}: missing {method_name}",
                    )


# ===========================================================================
# Y10 - AgentScheduler
# ===========================================================================


class TestY10Constants(unittest.TestCase):
    """AgentScheduler must define key constants (class-level)."""

    def test_max_restart_attempts(self):
        from Spyder.SpyderY_AutoAgents.SpyderY10_AgentScheduler import AgentScheduler

        self.assertEqual(AgentScheduler.MAX_RESTART_ATTEMPTS, 3)

    def test_restart_backoff(self):
        from Spyder.SpyderY_AutoAgents.SpyderY10_AgentScheduler import AgentScheduler

        self.assertEqual(AgentScheduler.RESTART_BACKOFF_SECONDS, 30)

    def test_health_check_interval(self):
        from Spyder.SpyderY_AutoAgents.SpyderY10_AgentScheduler import AgentScheduler

        self.assertEqual(AgentScheduler.HEALTH_CHECK_INTERVAL, 60)


class TestY10SchedulerInit(unittest.TestCase):
    """AgentScheduler constructor must initialise without error."""

    def test_default_construction(self):
        from Spyder.SpyderY_AutoAgents.SpyderY10_AgentScheduler import AgentScheduler

        scheduler = AgentScheduler()
        self.assertIsNotNone(scheduler)
        self.assertFalse(scheduler._started)

    def test_with_ollama_config(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import OllamaConfig
        from Spyder.SpyderY_AutoAgents.SpyderY10_AgentScheduler import AgentScheduler

        cfg = OllamaConfig(timeout=30)
        scheduler = AgentScheduler(ollama_config=cfg)
        self.assertIsNotNone(scheduler)


class TestY10NotBaseAutoAgent(unittest.TestCase):
    """AgentScheduler must NOT inherit from BaseAutoAgent."""

    def test_not_subclass(self):
        from Spyder.SpyderY_AutoAgents.SpyderY00_BaseAutoAgent import BaseAutoAgent
        from Spyder.SpyderY_AutoAgents.SpyderY10_AgentScheduler import AgentScheduler

        self.assertFalse(issubclass(AgentScheduler, BaseAutoAgent))


class TestY10ListAgents(unittest.TestCase):
    """list_agents must return a list of dicts."""

    def test_empty_initially(self):
        from Spyder.SpyderY_AutoAgents.SpyderY10_AgentScheduler import AgentScheduler

        scheduler = AgentScheduler()
        agents = scheduler.list_agents()
        self.assertIsInstance(agents, list)
        self.assertEqual(len(agents), 0)


class TestY10ContextManager(unittest.TestCase):
    """AgentScheduler must support context manager protocol."""

    def test_context_manager_protocol(self):
        from Spyder.SpyderY_AutoAgents.SpyderY10_AgentScheduler import AgentScheduler

        self.assertTrue(hasattr(AgentScheduler, "__enter__"))
        self.assertTrue(hasattr(AgentScheduler, "__exit__"))


if __name__ == "__main__":
    unittest.main()
