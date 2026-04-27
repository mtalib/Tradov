#!/usr/bin/env python3
"""Focused low-coverage tests for utility and monitoring stubs."""

from __future__ import annotations

import importlib.util
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from Spyder.SpyderI_Integration import SpyderI05_DiagnosticsEngine_Analyzers as i05
from Spyder.SpyderM_Monitoring import SpyderM08_HealthEndpoint as m08
from Spyder.SpyderQ_Scripts import SpyderQ25_SystemMonitor as q25
from Spyder.SpyderU_Utilities import SpyderU44_ShutdownCoordinator as u44


def _load_b20_module():
    module_path = Path(__file__).resolve().parents[1] / "SpyderB_Broker" / "SpyderB20_IntegratedConnectivityManager.py"
    spec = importlib.util.spec_from_file_location("_spyder_b20_isolated", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _DummyClient:
    def __init__(self, *, connected: bool = True, raise_on_connect: bool = False) -> None:
        self.connected = connected
        self.raise_on_connect = raise_on_connect
        self.connect_calls = 0
        self.disconnect_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1
        if self.raise_on_connect:
            raise RuntimeError("connect failed")
        self.connected = True

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False

    def heartbeat(self) -> bool:
        return self.connected

    def is_connected(self) -> bool:
        return self.connected


class _ProcOk:
    def num_fds(self) -> int:
        return 11


class _ProcNoFds:
    def num_fds(self) -> int:
        raise RuntimeError("no fds")


class _PsutilForSystemMonitor:
    @staticmethod
    def cpu_percent(interval: float = 0.0) -> float:
        return 12.5

    @staticmethod
    def virtual_memory():
        return SimpleNamespace(percent=55.5, used=500 * 1024 * 1024)

    @staticmethod
    def disk_usage(path: str):
        return SimpleNamespace(percent=44.0)

    @staticmethod
    def Process():
        return _ProcOk()


class _PsutilForAnalyzer:
    class NoSuchProcess(Exception):
        pass

    class AccessDenied(Exception):
        pass

    @staticmethod
    def virtual_memory():
        return SimpleNamespace(percent=96.0, available=200 * 1024 * 1024)

    @staticmethod
    def disk_usage(path: str):
        return SimpleNamespace(percent=94.0)

    @staticmethod
    def Process():
        return SimpleNamespace(num_threads=lambda: 501, open_files=lambda: [1, 2])

    @staticmethod
    def cpu_percent(interval: float = 0.0) -> float:
        return 97.0


def test_u44_shutdown_coordinator_callback_and_thread_stop(monkeypatch):
    monkeypatch.setattr(u44.atexit, "register", lambda _cb: None)

    coordinator = u44.ShutdownCoordinator()
    callback_fired = []
    coordinator.register_cleanup(lambda: callback_fired.append(True))

    thread_reached = threading.Event()

    def _worker() -> None:
        stop_event = coordinator.make_stop_event()
        while not stop_event.is_set():
            thread_reached.set()
            stop_event.wait(0.01)

    worker = coordinator.register_thread(threading.Thread(target=_worker, daemon=True), name="test-worker")
    assert worker.name == "test-worker"
    worker.start()
    assert thread_reached.wait(0.5)

    coordinator.shutdown(timeout=0.5)

    assert callback_fired == [True]
    assert coordinator.is_stopping() is True
    assert worker.is_alive() is False

    # Idempotent second shutdown path.
    coordinator.shutdown(timeout=0.01)


def test_u44_get_shutdown_coordinator_singleton(monkeypatch):
    monkeypatch.setattr(u44.atexit, "register", lambda _cb: None)
    u44._coordinator = None

    first = u44.get_shutdown_coordinator()
    second = u44.get_shutdown_coordinator()

    assert first is second


def test_b20_connect_disconnect_and_status_happy_path():
    b20 = _load_b20_module()
    broker = _DummyClient(connected=False)
    data = _DummyClient(connected=False)
    mgr = b20.IntegratedConnectivityManager(broker_client=broker, data_client=data)

    assert mgr.get_status()["state"] == "disconnected"
    assert mgr.connect() is True
    assert mgr.get_status()["state"] == "connected"
    assert mgr.is_connected() is True

    status = mgr.get_status()
    assert status["state"] == "connected"
    assert status["is_connected"] is True

    assert mgr.heartbeat() is True

    mgr.disconnect()
    assert mgr.get_status()["state"] == "disconnected"
    assert broker.disconnect_calls == 1
    assert data.disconnect_calls == 1


def test_b20_connect_failure_sets_error_state():
    b20 = _load_b20_module()
    broker = _DummyClient(raise_on_connect=True)
    mgr = b20.IntegratedConnectivityManager(broker_client=broker)

    assert mgr.connect() is False
    assert mgr.get_status()["state"] == "error"


def test_b20_heartbeat_handles_exceptions():
    b20 = _load_b20_module()

    class _BrokenClient:
        def heartbeat(self) -> bool:
            raise RuntimeError("boom")

    mgr = b20.IntegratedConnectivityManager(broker_client=_BrokenClient())
    assert mgr.heartbeat() is False


def test_m08_health_aggregate_and_health_response():
    endpoint = m08.HealthEndpoint(host="127.0.0.1", port=18888)
    endpoint.register_probe("ok_probe", lambda: True)
    endpoint.register_probe("bad_probe", lambda: False)

    body, code = endpoint._build_health_response()

    assert code == 503
    assert body["status"] == "unhealthy"
    assert body["series"]["ok_probe"] == "healthy"
    assert body["series"]["bad_probe"] == "unhealthy"


def test_m08_ready_and_metrics_without_psutil(monkeypatch):
    endpoint = m08.HealthEndpoint(host="127.0.0.1", port=18889)
    endpoint.register_ready_gate("gate_ok", lambda: True)
    endpoint.register_ready_gate("gate_err", lambda: (_ for _ in ()).throw(RuntimeError("x")))

    body, code = endpoint._build_ready_response()
    assert code == 503
    assert body["gates"]["gate_ok"] == "ready"
    assert body["gates"]["gate_err"] == "not_ready"

    monkeypatch.setattr(m08, "_PSUTIL_AVAILABLE", False)
    metrics = endpoint._build_metrics_response()
    assert "cpu_percent" not in metrics
    assert "uptime_seconds" in metrics


def test_m08_get_health_endpoint_singleton():
    m08._endpoint_instance = None

    first = m08.get_health_endpoint(host="127.0.0.1", port=18890)
    second = m08.get_health_endpoint(host="0.0.0.0", port=19999)

    assert first is second


def test_q25_snapshot_without_psutil(monkeypatch):
    monkeypatch.setattr(q25, "HAS_PSUTIL", False)

    monitor = q25.SystemMonitor(interval=0.01)
    snap = monitor.snapshot()

    assert snap.cpu_percent == 0.0
    assert snap.memory_percent == 0.0


def test_q25_snapshot_with_psutil_and_summary(monkeypatch):
    monkeypatch.setattr(q25, "HAS_PSUTIL", True)
    monkeypatch.setattr(q25, "psutil", _PsutilForSystemMonitor)

    monitor = q25.SystemMonitor(interval=0.01)
    snap = monitor.snapshot()

    assert snap.cpu_percent == 12.5
    assert snap.memory_percent == 55.5
    assert snap.open_file_handles == 11

    summary = monitor.get_summary()
    assert summary["psutil_available"] is True
    assert summary["cpu_percent"] == 12.5


def test_q25_snapshot_handles_num_fds_exception(monkeypatch):
    class _PsutilBadProc(_PsutilForSystemMonitor):
        @staticmethod
        def Process():
            return _ProcNoFds()

    monkeypatch.setattr(q25, "HAS_PSUTIL", True)
    monkeypatch.setattr(q25, "psutil", _PsutilBadProc)

    monitor = q25.SystemMonitor(interval=0.01)
    snap = monitor.snapshot()

    assert snap.open_file_handles == 0


def test_q25_start_and_stop_collects_samples(monkeypatch):
    monkeypatch.setattr(q25, "HAS_PSUTIL", False)

    monitor = q25.SystemMonitor(interval=0.01)
    monitor.start()
    time.sleep(0.03)
    monitor.stop()

    assert monitor.is_running is False
    assert monitor.get_latest() is not None


def test_i05_snapshot_without_psutil(monkeypatch):
    monkeypatch.setattr(i05, "_PSUTIL_AVAILABLE", False)

    manager = i05.AnalysisManager(config={"analysis_history_size": 5})
    summary = manager.analyze_performance()

    assert summary["status"] == "psutil_unavailable"
    assert len(manager._history) == 1


def test_i05_threshold_checks_and_trend_detection(monkeypatch):
    monkeypatch.setattr(i05, "_PSUTIL_AVAILABLE", True)
    monkeypatch.setattr(i05, "psutil", _PsutilForAnalyzer)

    manager = i05.AnalysisManager(config={"analysis_history_size": 10})
    perf = manager.analyze_performance()
    assert perf["status"] == "ok"

    # Force a clear growth trend and run advanced checks.
    manager._history = [
        {"memory_percent": 40.0, "cpu_percent": 10.0, "disk_percent": 50.0, "thread_count": 20},
        {"memory_percent": 42.0, "cpu_percent": 15.0, "disk_percent": 50.0, "thread_count": 20},
        {"memory_percent": 44.0, "cpu_percent": 20.0, "disk_percent": 50.0, "thread_count": 20},
        {"memory_percent": 60.0, "cpu_percent": 97.0, "disk_percent": 94.0, "thread_count": 501},
        {"memory_percent": 90.0, "cpu_percent": 97.0, "disk_percent": 94.0, "thread_count": 501},
    ]

    issues = manager.run_advanced_analysis()
    titles = {issue.title for issue in issues}

    assert "High CPU utilisation" in titles
    assert "High memory utilisation" in titles
    assert "Disk space critically low" in titles
    assert "High thread count" in titles
    assert "Memory growth trend detected" in titles


def test_i05_snapshot_handles_psutil_exceptions(monkeypatch):
    class _PsutilRaises(_PsutilForAnalyzer):
        class NoSuchProcess(Exception):
            pass

        class AccessDenied(Exception):
            pass

        @staticmethod
        def virtual_memory():
            raise _PsutilRaises.AccessDenied("denied")

    monkeypatch.setattr(i05, "_PSUTIL_AVAILABLE", True)
    monkeypatch.setattr(i05, "psutil", _PsutilRaises)

    manager = i05.AnalysisManager()
    snap = manager._snapshot()

    assert snap["status"].startswith("error:")


def test_i05_make_issue_populates_shape():
    issue = i05.AnalysisManager._make_issue(
        category=i05.DiagnosticCategory.PERFORMANCE,
        severity=i05.ProblemSeverity.MEDIUM,
        title="x",
        description="y",
        components=["system"],
        symptoms=["symptom"],
    )

    assert issue.title == "x"
    assert issue.recommendations == []
    assert issue.issue_id


def test_q25_run_trims_history(monkeypatch):
    monitor = q25.SystemMonitor(interval=0.0)
    monitor._snapshots = [q25.SystemSnapshot() for _ in range(1001)]

    call_count = {"n": 0}

    def _fake_wait(_interval: float) -> bool:
        call_count["n"] += 1
        monitor._stop_event.set()
        return True

    monkeypatch.setattr(monitor._stop_event, "wait", _fake_wait)
    monkeypatch.setattr(monitor, "snapshot", lambda: q25.SystemSnapshot(cpu_percent=1.0))

    monitor._run()

    assert call_count["n"] == 1
    assert len(monitor._snapshots) == 1000


def test_q25_get_latest_none_when_empty():
    monitor = q25.SystemMonitor()
    assert monitor.get_latest() is None


def test_m08_start_stop_with_fake_http_server(monkeypatch):
    class _FakeServer:
        def __init__(self, *_args, **_kwargs) -> None:
            self.health_endpoint = None
            self.stopped = False

        def serve_forever(self) -> None:
            return

        def shutdown(self) -> None:
            self.stopped = True

    monkeypatch.setattr(m08, "HTTPServer", _FakeServer)

    endpoint = m08.HealthEndpoint(host="127.0.0.1", port=18891)
    endpoint.start()
    endpoint.stop()

    assert endpoint._server is None
