#!/usr/bin/env python3
"""Focused regressions for explicit paper-start authorization in R12."""

from unittest.mock import MagicMock

from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor
from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import authorize_paper_session_start


def _build_logger_mock() -> MagicMock:
    return MagicMock()


def test_r12_paper_start_requires_explicit_authorization(monkeypatch) -> None:
    supervisor = SessionSupervisor(mode="paper", dry_run=False, skip_orphan_sweep=True)
    supervisor.logger = _build_logger_mock()

    validate_policy = MagicMock(return_value=(True, ""))
    start_event_manager = MagicMock(return_value=True)

    monkeypatch.setattr(supervisor, "_validate_live_only_tradier_policy", validate_policy)
    monkeypatch.setattr(supervisor, "_start_event_manager", start_event_manager)

    assert supervisor.start() is False

    validate_policy.assert_not_called()
    start_event_manager.assert_not_called()
    supervisor.logger.critical.assert_any_call(
        "R12_PAPER_START_GATE %s reason=%s mode=%s session_id=%s",
        "blocked",
        "explicit_authorization_required",
        "paper",
        supervisor.session_id,
    )


def test_r12_authorized_paper_start_reaches_startup_pipeline(monkeypatch) -> None:
    supervisor = SessionSupervisor(mode="paper", dry_run=False, skip_orphan_sweep=True)
    supervisor.logger = _build_logger_mock()

    validate_policy = MagicMock(return_value=(True, ""))
    start_event_manager = MagicMock(return_value=False)
    abort = MagicMock(return_value=False)

    monkeypatch.setattr(supervisor, "_validate_live_only_tradier_policy", validate_policy)
    monkeypatch.setattr(supervisor, "_start_event_manager", start_event_manager)
    monkeypatch.setattr(supervisor, "_abort", abort)

    authorize_paper_session_start(supervisor)

    assert supervisor.start() is False

    validate_policy.assert_called_once_with()
    start_event_manager.assert_called_once_with()
    abort.assert_called_once_with("EventManager")
    assert supervisor._spyder_paper_start_authorized is False
    supervisor.logger.debug.assert_any_call(
        "R12_PAPER_START_GATE %s reason=%s mode=%s session_id=%s",
        "allowed",
        "explicit_authorization",
        "paper",
        supervisor.session_id,
    )
