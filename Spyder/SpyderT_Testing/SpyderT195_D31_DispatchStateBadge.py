"""T195 — D31 ``get_dispatch_state()`` powers the G05 DISPATCH pill.

Implements the v9 §10.4 hardening item #3: "Add a dashboard badge sourced from
latest D31 decision-drop reason (execution truth), not only pill-derived state."

State machine (priority: ERROR > BLOCKED > FLOWING > IDLE), bounded by the
``DISPATCH_STATE_RECENCY_S`` window (120s by default):

    FLOWING — successful dispatch within recency window
    IDLE    — no signal events within recency window
    BLOCKED — guardrail drop within recency window, no fresher dispatch
    ERROR   — ``dispatch_exception`` within recency window
"""

from __future__ import annotations

import importlib

import pytest


class _StubEM:
    def subscribe(self, *a, **k): return None
    def emit(self, *a, **k): return None
    def publish(self, *a, **k): return None
    def unsubscribe(self, *a, **k): return None


@pytest.fixture
def orc(tmp_path):
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    instance = mod.StrategyOrchestrator(event_manager=_StubEM())
    # Redirect decision audit log to an isolated temp directory so tests do
    # not pollute the production logs/decisions/ JSONL files.
    instance._signal_drop_audit_dir = str(tmp_path)
    return instance


def _signal(strategy_type="bull_put_spread"):
    return {"strategy_type": strategy_type, "symbol": "SPY"}


# ---------------------------------------------------------------------------
# Baseline state on a fresh orchestrator
# ---------------------------------------------------------------------------

def test_idle_when_no_events(orc):
    state = orc.get_dispatch_state()
    assert state["state"] == "IDLE"
    assert state["age_s"] is None
    assert "120" in state["reason"]


# ---------------------------------------------------------------------------
# FLOWING — successful dispatch
# ---------------------------------------------------------------------------

def test_flowing_after_dispatch_submitted(orc):
    orc._record_signal_dispatch_outcome("dispatch_submitted", signal=_signal())
    state = orc.get_dispatch_state()
    assert state["state"] == "FLOWING"
    assert "bull_put_spread" in state["reason"]
    assert state["age_s"] is not None
    assert state["age_s"] >= 0.0


def test_dispatch_rejected_does_not_count_as_flowing(orc):
    # Rejected by broker — not a successful dispatch.
    orc._record_signal_dispatch_outcome("dispatch_rejected", signal=_signal())
    state = orc.get_dispatch_state()
    assert state["state"] == "IDLE"


# ---------------------------------------------------------------------------
# BLOCKED — guardrail drops
# ---------------------------------------------------------------------------

def test_blocked_after_risk_gate_drop(orc):
    orc._record_signal_drop("risk_gate", "risk_state_cold", signal=_signal())
    state = orc.get_dispatch_state()
    assert state["state"] == "BLOCKED"
    assert state["reason"] == "risk_gate:risk_state_cold"


def test_blocked_after_entry_trust_gate_drop(orc):
    orc._record_signal_drop(
        "entry_trust_gate",
        "Weekend - markets closed",
        signal=_signal(),
    )
    state = orc.get_dispatch_state()
    assert state["state"] == "BLOCKED"
    assert "Weekend" in state["reason"]


def test_orchestrator_paused_drop_is_blocked(orc):
    orc._record_signal_drop("orchestrator", "orchestrator_paused", signal=_signal())
    state = orc.get_dispatch_state()
    assert state["state"] == "BLOCKED"


# ---------------------------------------------------------------------------
# ERROR — dispatch_exception is special-cased
# ---------------------------------------------------------------------------

def test_dispatch_exception_is_error_not_blocked(orc):
    orc._record_signal_drop(
        "dispatch",
        "dispatch_exception",
        signal=_signal(),
        detail="SimpleNamespace has no attribute 'message'",
    )
    state = orc.get_dispatch_state()
    assert state["state"] == "ERROR"
    assert "dispatch_exception" in state["reason"]


def test_error_priority_over_blocked(orc):
    # Drop first, then dispatch exception — ERROR must win.
    orc._record_signal_drop("risk_gate", "risk_state_cold", signal=_signal())
    orc._record_signal_drop(
        "dispatch",
        "dispatch_exception",
        signal=_signal(),
        detail="boom",
    )
    state = orc.get_dispatch_state()
    assert state["state"] == "ERROR"


def test_error_priority_over_flowing(orc):
    # Successful dispatch then exception — ERROR must win, since it implies
    # the *next* signal failed even if a previous one succeeded.
    orc._record_signal_dispatch_outcome("dispatch_submitted", signal=_signal())
    orc._record_signal_drop(
        "dispatch",
        "dispatch_exception",
        signal=_signal(),
        detail="boom",
    )
    state = orc.get_dispatch_state()
    assert state["state"] == "ERROR"


# ---------------------------------------------------------------------------
# FLOWING vs BLOCKED priority: most recent event wins within window
# ---------------------------------------------------------------------------

def test_drop_then_dispatch_is_flowing(orc):
    """A guardrail drop followed by a successful dispatch means the system
    has recovered — pill should show FLOWING, not BLOCKED."""
    orc._record_signal_drop("risk_gate", "risk_state_cold", signal=_signal())
    orc._record_signal_dispatch_outcome("dispatch_submitted", signal=_signal())
    state = orc.get_dispatch_state()
    assert state["state"] == "FLOWING"


def test_dispatch_then_drop_is_blocked(orc):
    """A successful dispatch followed by a fresher drop means a new signal
    was just blocked — pill should show BLOCKED."""
    orc._record_signal_dispatch_outcome("dispatch_submitted", signal=_signal())
    orc._record_signal_drop("risk_gate", "risk_state_cold", signal=_signal())
    state = orc.get_dispatch_state()
    assert state["state"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Recency window — events older than 120s collapse to IDLE
# ---------------------------------------------------------------------------

def test_blocked_collapses_to_idle_after_recency(orc):
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    orc._record_signal_drop("risk_gate", "risk_state_cold", signal=_signal())
    # Backdate the event past the recency window.
    orc._last_drop_event["monotonic_ts"] -= mod.DISPATCH_STATE_RECENCY_S + 1.0
    state = orc.get_dispatch_state()
    assert state["state"] == "IDLE"


def test_flowing_collapses_to_idle_after_recency(orc):
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    orc._record_signal_dispatch_outcome("dispatch_submitted", signal=_signal())
    orc._last_dispatch_ok_ts -= mod.DISPATCH_STATE_RECENCY_S + 1.0
    state = orc.get_dispatch_state()
    assert state["state"] == "IDLE"


def test_error_collapses_to_idle_after_recency(orc):
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    orc._record_signal_drop(
        "dispatch",
        "dispatch_exception",
        signal=_signal(),
        detail="boom",
    )
    orc._last_dispatch_error["monotonic_ts"] -= mod.DISPATCH_STATE_RECENCY_S + 1.0
    state = orc.get_dispatch_state()
    assert state["state"] == "IDLE"


# ---------------------------------------------------------------------------
# Strategy capture
# ---------------------------------------------------------------------------

def test_strategy_type_captured_from_signal(orc):
    orc._record_signal_dispatch_outcome(
        "dispatch_submitted",
        signal={"strategy_type": "iron_condor", "symbol": "SPY"},
    )
    state = orc.get_dispatch_state()
    assert state["state"] == "FLOWING"
    assert "iron_condor" in state["reason"]


def test_dispatch_without_strategy_type_falls_back_to_unknown(orc):
    orc._record_signal_dispatch_outcome("dispatch_submitted", signal=None)
    state = orc.get_dispatch_state()
    assert state["state"] == "FLOWING"
    assert "unknown" in state["reason"]


# ---------------------------------------------------------------------------
# Pre-risk gate helper contract
# ---------------------------------------------------------------------------

def test_pre_risk_helper_session_window_reject_shape(orc):
    orc._passes_session_window_gate = lambda _signal: (False, "zero_dte_short_cutoff")
    orc._passes_entry_trust_gate = lambda _signal: (True, "")

    allowed, stage, reason, detail = orc._evaluate_pre_risk_signal_gates(_signal())

    assert allowed is False
    assert stage == "pre_risk"
    assert reason == "session_window_gate"
    assert detail == "zero_dte_short_cutoff"


def test_pre_risk_helper_entry_trust_reject_shape(orc):
    orc._passes_session_window_gate = lambda _signal: (True, "")
    orc._passes_entry_trust_gate = lambda _signal: (False, "market_structure_untrusted")

    allowed, stage, reason, detail = orc._evaluate_pre_risk_signal_gates(_signal())

    assert allowed is False
    assert stage == "pre_risk"
    assert reason == "entry_trust_gate"
    assert detail == "market_structure_untrusted"


def test_pre_risk_drop_reason_surfaces_as_blocked_state_reason(orc):
    orc._record_signal_drop(
        "pre_risk",
        "session_window_gate",
        signal=_signal(),
        detail="zero_dte_short_cutoff",
    )

    state = orc.get_dispatch_state()

    assert state["state"] == "BLOCKED"
    assert state["reason"] == "pre_risk:session_window_gate"
