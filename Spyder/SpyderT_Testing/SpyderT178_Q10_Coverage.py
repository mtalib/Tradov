#!/usr/bin/env python3
"""Coverage tests for SpyderQ10_ProtocolComplianceGate."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from Spyder.SpyderQ_Scripts import SpyderQ10_ProtocolComplianceGate as q10


def test_file_has_ungated_rng_filters_main_and_allowed(tmp_path):
    py_file = tmp_path / "sample_rng.py"
    py_file.write_text(
        """
def create_sample_data():
    x = np.random.rand()

def unsafe_rng():
    y = np.random.rand()

if __name__ == '__main__':
    z = np.random.rand()
""".strip()
        + "\n",
        encoding="utf-8",
    )

    hits = q10._file_has_ungated_rng(py_file)
    assert len(hits) == 1
    assert hits[0][0] == 5
    assert "np.random" in hits[0][1]


def test_check_no_rng_in_production_pass_and_fail(monkeypatch):
    monkeypatch.setattr(q10, "_RNG_SCAN_PACKAGES", [])
    assert q10.check_no_rng_in_production() is True

    monkeypatch.setattr(q10, "_RNG_SCAN_PACKAGES", ["SpyderT_Testing"])
    monkeypatch.setattr(
        q10,
        "_file_has_ungated_rng",
        lambda _path: [(42, "np.random.rand()")],
    )
    assert q10.check_no_rng_in_production() is False


def test_datetime_hygiene_gates(tmp_path, monkeypatch):
    prod_dir = tmp_path / "Spyder" / "SpyderA_Core"
    prod_dir.mkdir(parents=True)
    good_file = prod_dir / "good.py"
    good_file.write_text("from datetime import datetime, timezone\nnow = datetime.now(timezone.utc)\n", encoding="utf-8")

    monkeypatch.setattr(q10, "_SPYDER_ROOT", tmp_path / "Spyder")
    assert q10.check_no_datetime_utcnow() is True
    assert q10.check_no_naive_datetime_now() is True

    bad_utcnow = prod_dir / "bad_utcnow.py"
    bad_utcnow.write_text("from datetime import datetime\nvalue = datetime.utcnow()\n", encoding="utf-8")
    assert q10.check_no_datetime_utcnow() is False

    bad_now = prod_dir / "bad_now.py"
    bad_now.write_text("from datetime import datetime\nvalue = datetime.now()\n", encoding="utf-8")
    assert q10.check_no_naive_datetime_now() is False


def test_check_broker_protocol_compliance_success(monkeypatch):
    class _Protocol:
        def place_order(self, symbol, quantity, **kwargs):
            return None

    class _GoodBroker:
        def place_order(self, symbol, quantity, **kwargs):
            return None

        def get_order(self):
            return None

        def cancel_order(self):
            return None

        def get_positions(self):
            return []

        def get_account_balances(self):
            return {}

    def _import_module(name: str):
        if name == "Spyder.SpyderB_Broker.SpyderB21_BrokerProtocol":
            return SimpleNamespace(BrokerProtocol=_Protocol)
        if name in (
            "Spyder.SpyderB_Broker.SpyderB40_TradierClient",
            "Spyder.SpyderR_Runtime.SpyderR15_PaperBroker",
        ):
            class_name = "TradierClient" if "B40" in name else "PaperBroker"
            return SimpleNamespace(**{class_name: _GoodBroker})
        return importlib.import_module(name)

    monkeypatch.setattr("importlib.import_module", _import_module)
    assert q10.check_broker_protocol_compliance() is True


def test_check_broker_protocol_compliance_failures(monkeypatch):
    class _Protocol:
        def place_order(self, symbol, quantity):
            return None

    class _MissingMethods:
        def place_order(self, symbol, quantity):
            return None

    class _MissingParams:
        def place_order(self):
            return None

        def get_order(self):
            return None

        def cancel_order(self):
            return None

        def get_positions(self):
            return []

        def get_account_balances(self):
            return {}

    def _import_module_missing(name: str):
        if name == "Spyder.SpyderB_Broker.SpyderB21_BrokerProtocol":
            return SimpleNamespace(BrokerProtocol=_Protocol)
        if "B40" in name:
            return SimpleNamespace(TradierClient=_MissingMethods)
        if "R15" in name:
            return SimpleNamespace(PaperBroker=_MissingParams)
        return importlib.import_module(name)

    monkeypatch.setattr("importlib.import_module", _import_module_missing)
    assert q10.check_broker_protocol_compliance() is False


def test_check_module_imports(monkeypatch):
    monkeypatch.setattr(q10, "_SMOKE_TEST_MODULES", ["ok.mod", "bad.mod"])

    def _import_module(name: str):
        if name == "bad.mod":
            raise RuntimeError("boom")
        return SimpleNamespace()

    monkeypatch.setattr("importlib.import_module", _import_module)
    assert q10.check_module_imports() is False

    monkeypatch.setattr(q10, "_SMOKE_TEST_MODULES", ["ok.mod"])
    assert q10.check_module_imports() is True


def test_check_strategy_orchestrator_health_success(monkeypatch):
    class _EventType:
        STRATEGY_SIGNAL = "strategy_signal"

    class _EventManager:
        def __init__(self):
            self.is_running = False
            self.handlers = {_EventType.STRATEGY_SIGNAL: []}

        def start(self):
            self.is_running = True

    event_manager = _EventManager()

    class _StrategyOrchestrator:
        def __init__(self, event_manager):
            event_manager.handlers[_EventType.STRATEGY_SIGNAL].append("handler")

    d31_module = SimpleNamespace(
        SPYDER_MODULES_AVAILABLE=True,
        StrategyOrchestrator=_StrategyOrchestrator,
    )

    def _import_module(name: str):
        if name == "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator":
            return d31_module
        return importlib.import_module(name)

    monkeypatch.setattr("importlib.import_module", _import_module)

    fake_a05 = ModuleType("Spyder.SpyderA_Core.SpyderA05_EventManager")
    fake_a05.get_event_manager = lambda: event_manager
    fake_a05.EventType = _EventType
    monkeypatch.setitem(sys.modules, "Spyder.SpyderA_Core.SpyderA05_EventManager", fake_a05)

    assert q10.check_strategy_orchestrator_health() is True


def test_check_strategy_orchestrator_health_fail(monkeypatch):
    d31_module = SimpleNamespace(SPYDER_MODULES_AVAILABLE=False, StrategyOrchestrator=object)

    def _import_module(name: str):
        if name == "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator":
            return d31_module
        return importlib.import_module(name)

    monkeypatch.setattr("importlib.import_module", _import_module)

    fake_a05 = ModuleType("Spyder.SpyderA_Core.SpyderA05_EventManager")
    fake_a05.get_event_manager = lambda: SimpleNamespace(is_running=True, handlers={"strategy_signal": []})
    fake_a05.EventType = SimpleNamespace(STRATEGY_SIGNAL="strategy_signal")
    monkeypatch.setitem(sys.modules, "Spyder.SpyderA_Core.SpyderA05_EventManager", fake_a05)

    assert q10.check_strategy_orchestrator_health() is False


def test_main_exit_codes(monkeypatch):
    monkeypatch.setattr(q10, "check_no_rng_in_production", lambda: True)
    monkeypatch.setattr(q10, "check_no_datetime_utcnow", lambda: True)
    monkeypatch.setattr(q10, "check_no_naive_datetime_now", lambda: True)
    monkeypatch.setattr(q10, "check_broker_protocol_compliance", lambda: True)
    monkeypatch.setattr(q10, "check_module_imports", lambda: True)
    monkeypatch.setattr(q10, "check_strategy_orchestrator_health", lambda: True)

    class _ResultOK:
        failures = []
        errors = []

        def wasSuccessful(self):
            return True

    class _ResultFail:
        failures = ["x"]
        errors = ["y"]

        def wasSuccessful(self):
            return False

    class _Loader:
        def loadTestsFromModule(self, _module):
            return object()

    class _RunnerOK:
        def __init__(self, verbosity):
            self.verbosity = verbosity

        def run(self, _suite):
            return _ResultOK()

    class _RunnerFail:
        def __init__(self, verbosity):
            self.verbosity = verbosity

        def run(self, _suite):
            return _ResultFail()

    testing_pkg = importlib.import_module("Spyder.SpyderT_Testing")
    fake_suite = ModuleType("SpyderT129_ProtocolCompliance")
    monkeypatch.setattr(testing_pkg, "SpyderT129_ProtocolCompliance", fake_suite, raising=False)

    monkeypatch.setattr(q10.unittest, "TestLoader", lambda: _Loader())
    monkeypatch.setattr(q10.unittest, "TextTestRunner", _RunnerOK)
    assert q10.main() == 0

    monkeypatch.setattr(q10.unittest, "TextTestRunner", _RunnerFail)
    assert q10.main() == 1
