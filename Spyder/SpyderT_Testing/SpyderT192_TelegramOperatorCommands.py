"""T192 — Telegram operator command controls for halt/resume/flatten.

Focused regression tests for:
- Dual-approval resume flow.
- Correlation ID presence in command responses and audit payloads.

These tests intentionally avoid network calls and construct TelegramBot via
``__new__`` with lightweight stubs.
"""

from __future__ import annotations

import json
import time
import threading
from datetime import datetime, timedelta, timezone, UTC
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from Spyder.SpyderJ_Alerts import SpyderJ05_TelegramBot as tgmod
from Spyder.SpyderJ_Alerts.SpyderJ05_TelegramBot import (
    TelegramBot,
    TelegramMessage,
    MessagePriority,
    MessageType,
)


def _make_bot() -> TelegramBot:
    """Create a minimal TelegramBot instance without running __init__."""
    bot = TelegramBot.__new__(TelegramBot)
    bot.default_chat_id = "chat-1"
    bot._stop_event = threading.Event()
    bot._command_poll_timeout_seconds = 5
    bot._command_poll_request_timeout_seconds = 6
    bot._allowed_user_ids = {111, 222}
    bot._pending_confirms = {}
    bot._resume_dual_approval = True
    bot._resume_pending = None
    bot._pending_file_lock = threading.Lock()
    bot._pending_replay_limit = 200
    bot._pending_max_rows = 2000
    bot._pending_max_age_hours = 168
    bot.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )
    bot.send_message = MagicMock(return_value=True)
    bot._append_command_audit = MagicMock()
    bot.get_stats = MagicMock(
        return_value={
            "is_running": True,
            "queue_size": 0,
            "messages_sent": 0,
        }
    )
    bot._resume_preflight_failed_gates = MagicMock(return_value=[])
    bot.event_manager = SimpleNamespace(emit=MagicMock(return_value=True))
    bot._pl_heartbeat_interval_min = 30
    bot._last_pl_heartbeat_et = None
    bot._last_eod_summary_date = None
    return bot


class TestDualApprovalResume:
    """Dual-approval behavior for /resume in Telegram command path."""

    def test_resume_first_approval_waits_for_second(self):
        bot = _make_bot()
        bot._handle_resume_command = MagicMock()
        bot._resume_pending = {
            "token": "ABC123",
            "expires_at": time.time() + 60,
            "requested_by": 111,
            "approvers": set(),
            "correlation_id": "corr-123",
        }

        bot._handle_confirm_command(
            chat_id="chat-1",
            user_id=111,
            username="op1",
            args=["resume", "ABC123"],
            correlation_id="ignored-correlation",
        )

        bot._handle_resume_command.assert_not_called()
        assert bot._resume_pending is not None
        assert bot._resume_pending["approvers"] == {111}

    def test_resume_second_distinct_approval_executes(self):
        bot = _make_bot()
        bot._handle_resume_command = MagicMock()
        bot._resume_pending = {
            "token": "ABC123",
            "expires_at": time.time() + 60,
            "requested_by": 111,
            "approvers": {111},
            "correlation_id": "corr-xyz",
        }

        bot._handle_confirm_command(
            chat_id="chat-1",
            user_id=222,
            username="op2",
            args=["resume", "ABC123"],
            correlation_id="ignored-correlation",
        )

        bot._handle_resume_command.assert_called_once()
        kwargs = bot._handle_resume_command.call_args.kwargs
        assert kwargs["approved_by"] == [111, 222]
        assert kwargs["correlation_id"] == "corr-xyz"
        assert bot._resume_pending is None


class TestTelegramStopBehavior:
    """Shutdown of TelegramBot should not wait on avoidable long-poll delays."""

    def test_create_session_accepts_retry_override(self):
        bot = _make_bot()
        bot._build_session = MagicMock(return_value="session")

        session = TelegramBot._create_session(bot, retry_total=0)

        assert session == "session"
        bot._build_session.assert_called_once_with(0)

    def test_stop_closes_sessions_before_waiting_for_threads(self, monkeypatch):
        bot = _make_bot()
        bot.running = True
        bot.send_system_message = MagicMock(return_value=True)

        call_order: list[str] = []

        class _Thread:
            def __init__(self, label: str):
                self.label = label

            def join(self, timeout=None):
                call_order.append(f"join:{self.label}:{timeout is not None}")

        bot.worker_thread = _Thread("worker")
        bot.command_thread = _Thread("command")
        bot.summary_thread = _Thread("summary")
        bot.session = SimpleNamespace(close=lambda: call_order.append("close_session"))
        bot.command_session = SimpleNamespace(
            close=lambda: call_order.append("close_command_session")
        )
        monkeypatch.setenv("SPYDER_TELEGRAM_STOP_TIMEOUT_S", "1.5")

        bot.stop()

        assert bot._stop_event.is_set() is True
        assert call_order[:2] == ["close_session", "close_command_session"]
        assert call_order[2:] == [
            "join:worker:True",
            "join:command:True",
            "join:summary:True",
        ]

    def test_summary_loop_exits_without_work_when_stop_already_requested(self):
        bot = _make_bot()
        bot.running = True
        bot._stop_event.set()
        bot._run_periodic_pl_notifications_once = MagicMock()

        bot._summary_loop()

        bot._run_periodic_pl_notifications_once.assert_not_called()

    def test_command_poll_loop_uses_bounded_poll_session_timeouts(self):
        bot = _make_bot()
        bot.running = True
        bot.bot_token = "token"

        handled_updates: list[dict[str, object]] = []

        def _handle_update(update: dict[str, object]) -> None:
            handled_updates.append(update)
            bot.running = False
            bot._stop_event.set()

        bot._handle_inbound_update = _handle_update

        class _Response:
            def __init__(self, ok=True, result=None):
                self.ok = ok
                self._result = result or []

            def json(self):
                return {"result": self._result}

        session_calls: list[tuple[dict[str, object], int | float | None]] = []

        class _Session:
            def get(self, _url, params=None, timeout=None):
                session_calls.append((dict(params or {}), timeout))
                if params and params.get("timeout") == 0:
                    return _Response(result=[{"update_id": 10}])
                return _Response(
                    result=[
                        {
                            "update_id": 11,
                            "message": {
                                "text": "/status",
                                "from": {"id": 111, "username": "op1"},
                                "chat": {"id": "chat-1"},
                            },
                        }
                    ]
                )

        bot.session = MagicMock()
        bot.command_session = _Session()

        bot._command_poll_loop()

        assert bot.session.get.called is False
        assert session_calls == [
            ({"limit": 1, "timeout": 0}, tgmod.CONNECTION_TIMEOUT),
            (
                {
                    "offset": 11,
                    "timeout": 5,
                    "allowed_updates": ["message"],
                },
                6,
            ),
        ]
        assert len(handled_updates) == 1


class TestCorrelationIdPropagation:
    """Correlation IDs should be present in status/halt responses and audit rows."""

    def test_status_includes_correlation_in_message_and_audit(self, monkeypatch):
        bot = _make_bot()

        # Prevent dependence on real running supervisor.
        monkeypatch.setattr(tgmod, "get_session_supervisor", lambda: None)

        bot._handle_status_command(
            chat_id="chat-1",
            user_id=111,
            username="op1",
            correlation_id="corr-status-1",
        )

        assert bot.send_message.called
        sent_text = bot.send_message.call_args.args[0]
        assert "Correlation: corr-status-1" in sent_text

        audit_payload = bot._append_command_audit.call_args.args[0]
        assert audit_payload["correlation_id"] == "corr-status-1"
        assert audit_payload["command"] == "/status"

    def test_halt_audit_contains_correlation_id(self):
        bot = _make_bot()

        bot._handle_halt_command(
            chat_id="chat-1",
            user_id=111,
            username="op1",
            correlation_id="corr-halt-77",
        )

        audit_payload = bot._append_command_audit.call_args.args[0]
        assert audit_payload["correlation_id"] == "corr-halt-77"
        assert audit_payload["command"] == "/halt"
        assert audit_payload["result"] == "emitted"

    def test_help_audit_contains_correlation_id(self):
        bot = _make_bot()

        update = {
            "update_id": 888,
            "message": {
                "text": "/help",
                "from": {"id": 111, "username": "op1"},
                "chat": {"id": "chat-1"},
            },
        }

        bot._handle_inbound_update(update)

        assert bot.send_message.called
        audit_payload = bot._append_command_audit.call_args.args[0]
        assert audit_payload["command"] == "/help"
        assert audit_payload["authorized"] is True
        assert audit_payload["result"] == "ok"
        assert audit_payload["correlation_id"].startswith("tgcmd-888-")


class TestNegativePaths:
    """Negative/abuse paths for Telegram operator command controls."""

    def test_unauthorized_command_rejected_and_audited_with_correlation(self):
        bot = _make_bot()

        update = {
            "update_id": 777,
            "message": {
                "text": "/halt",
                "from": {"id": 999, "username": "intruder"},
                "chat": {"id": "chat-unauth"},
            },
        }

        bot._handle_inbound_update(update)

        assert bot.send_message.called
        sent_text = bot.send_message.call_args.args[0]
        assert "Unauthorized operator command" in sent_text
        assert "Correlation: tgcmd-777-" in sent_text

        audit_payload = bot._append_command_audit.call_args.args[0]
        assert audit_payload["command"] == "/halt"
        assert audit_payload["authorized"] is False
        assert audit_payload["result"] == "rejected"
        assert audit_payload["correlation_id"].startswith("tgcmd-777-")

    def test_confirm_expired_token_is_rejected(self):
        bot = _make_bot()

        bot._pending_confirms[111] = {
            "action": "halt",
            "token": "ABC123",
            "expires_at": time.time() - 1,
            "username": "op1",
            "correlation_id": "corr-expired-1",
        }

        bot._handle_confirm_command(
            chat_id="chat-1",
            user_id=111,
            username="op1",
            args=["halt", "ABC123"],
            correlation_id="corr-ignored",
        )

        assert 111 not in bot._pending_confirms
        assert bot.send_message.called
        sent_text = bot.send_message.call_args.args[0]
        assert "Confirmation token expired" in sent_text

    def test_resume_duplicate_approver_is_blocked(self):
        bot = _make_bot()
        bot._handle_resume_command = MagicMock()
        bot._resume_pending = {
            "token": "ABC123",
            "expires_at": time.time() + 60,
            "requested_by": 111,
            "approvers": {111},
            "correlation_id": "corr-resume-dup",
        }

        bot._handle_confirm_command(
            chat_id="chat-1",
            user_id=111,
            username="op1",
            args=["resume", "ABC123"],
            correlation_id="corr-ignored",
        )

        bot._handle_resume_command.assert_not_called()
        assert bot._resume_pending is not None
        assert bot._resume_pending["approvers"] == {111}
        assert bot.send_message.called
        sent_text = bot.send_message.call_args.args[0]
        assert "already recorded" in sent_text

    def test_resume_invalid_token_is_rejected(self):
        bot = _make_bot()
        bot._handle_resume_command = MagicMock()
        bot._resume_pending = {
            "token": "ABC123",
            "expires_at": time.time() + 60,
            "requested_by": 111,
            "approvers": set(),
            "correlation_id": "corr-resume-invalid",
        }

        bot._handle_confirm_command(
            chat_id="chat-1",
            user_id=222,
            username="op2",
            args=["resume", "WRONG1"],
            correlation_id="corr-ignored",
        )

        bot._handle_resume_command.assert_not_called()
        assert bot._resume_pending is not None
        assert bot._resume_pending["approvers"] == set()
        assert bot.send_message.called
        sent_text = bot.send_message.call_args.args[0]
        assert "Invalid resume confirmation token" in sent_text


class TestTradeCloseNotifications:
    """Per-trade close alert behavior for Telegram notifications."""

    def test_position_closed_event_sends_trade_closed_alert(self):
        bot = _make_bot()
        bot.send_trade_closed = MagicMock(return_value=True)

        event = SimpleNamespace(
            source="CreditSpread",
            data={
                "position_id": "pos-123",
                "symbol": "SPY",
                "position_type": "SHORT",
                "position_size": 2,
                "entry_price": 2.5,
                "exit_price": 1.25,
                "realized_pnl": 250.0,
                "exit_reason": "profit target",
            },
        )

        bot._handle_position_closed_event(event)

        bot.send_trade_closed.assert_called_once()
        kwargs = bot.send_trade_closed.call_args.kwargs
        assert kwargs["symbol"] == "SPY"
        assert kwargs["strategy"] == "CreditSpread"
        assert kwargs["quantity"] == 2
        assert kwargs["pnl"] == 250.0
        assert kwargs["reason"] == "profit target"

    def test_position_closed_event_is_deduplicated(self):
        bot = _make_bot()
        bot.send_trade_closed = MagicMock(return_value=True)

        event = SimpleNamespace(
            source="ZeroDTE",
            data={
                "position_id": "pos-dup-1",
                "symbol": "SPY",
                "realized_pnl": -80.0,
                "exit_reason": "stop loss",
            },
        )

        bot._handle_position_closed_event(event)
        bot._handle_position_closed_event(event)

        # Duplicate close events for the same position should only alert once.
        bot.send_trade_closed.assert_called_once()


class TestPeriodicPLReporting:
    """Periodic heartbeat/EOD summary reporting behavior."""

    def test_heartbeat_respects_interval(self, monkeypatch):
        bot = _make_bot()
        bot.send_message = MagicMock(return_value=True)

        monkeypatch.setattr(tgmod, "get_session_supervisor", lambda: None)

        et = ZoneInfo("America/New_York")
        bot._run_periodic_pl_notifications_once(
            now_et=datetime(2026, 5, 5, 10, 0, tzinfo=et)
        )
        bot._run_periodic_pl_notifications_once(
            now_et=datetime(2026, 5, 5, 10, 10, tzinfo=et)
        )
        bot._run_periodic_pl_notifications_once(
            now_et=datetime(2026, 5, 5, 10, 31, tzinfo=et)
        )

        assert bot.send_message.call_count == 2
        first_msg = bot.send_message.call_args_list[0].args[0]
        assert "P/L HEARTBEAT" in first_msg

    def test_eod_summary_sent_once_per_day(self, monkeypatch):
        bot = _make_bot()
        bot.send_message = MagicMock(return_value=True)

        monkeypatch.setattr(tgmod, "get_session_supervisor", lambda: None)

        et = ZoneInfo("America/New_York")
        bot._run_periodic_pl_notifications_once(
            now_et=datetime(2026, 5, 5, 16, 17, tzinfo=et)
        )
        bot._run_periodic_pl_notifications_once(
            now_et=datetime(2026, 5, 5, 16, 18, tzinfo=et)
        )

        assert bot.send_message.call_count == 1
        sent_msg = bot.send_message.call_args.args[0]
        assert "EOD P/L SUMMARY" in sent_msg


class TestSystemEventCompatibility:
    """Compatibility tests for generic SYSTEM telegram forwarding."""

    def test_telegram_send_accepts_text_payload(self):
        bot = _make_bot()
        bot.send_message = MagicMock(return_value=True)

        event = SimpleNamespace(data={"type": "telegram_send", "text": "hello from text"})
        bot._handle_system_event(event)

        bot.send_message.assert_called_once_with("hello from text")

    def test_telegram_send_accepts_message_payload(self):
        bot = _make_bot()
        bot.send_message = MagicMock(return_value=True)

        event = SimpleNamespace(data={"type": "telegram_send", "message": "hello from message"})
        bot._handle_system_event(event)

        bot.send_message.assert_called_once_with("hello from message")


class TestAllowedUserEnvCompatibility:
    """Environment key compatibility for operator user whitelist."""

    def test_load_allowed_user_ids_from_primary_key(self, monkeypatch):
        bot = _make_bot()
        monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "101, 202")
        monkeypatch.delenv("TELEGRAM_APPROVED_USER_IDS", raising=False)

        ids = bot._load_allowed_user_ids()
        assert ids == {101, 202}

    def test_load_allowed_user_ids_from_alias_key(self, monkeypatch):
        bot = _make_bot()
        monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
        monkeypatch.setenv("TELEGRAM_APPROVED_USER_IDS", "303, 404")

        ids = bot._load_allowed_user_ids()
        assert ids == {303, 404}

    def test_primary_key_takes_precedence_over_alias(self, monkeypatch):
        bot = _make_bot()
        monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "505")
        monkeypatch.setenv("TELEGRAM_APPROVED_USER_IDS", "606")

        ids = bot._load_allowed_user_ids()
        assert ids == {505}


class TestPendingQueueDurability:
    """Durable pending queue and replay behavior for delivery failures."""

    def test_failed_delivery_persists_message(self, tmp_path):
        bot = _make_bot()
        bot._pending_queue_file = tmp_path / "pending_messages.jsonl"

        msg = TelegramMessage(
            content="hello",
            chat_id="chat-1",
            priority=MessagePriority.NORMAL,
            message_type=MessageType.SYSTEM,
        )
        bot._handle_failed_delivery(msg, "unit_test_failure")

        assert bot._pending_queue_file.exists()
        lines = bot._pending_queue_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert "unit_test_failure" in lines[0]
        assert "hello" in lines[0]

    def test_eod_summary_failure_triggers_high_alert(self, tmp_path):
        bot = _make_bot()
        bot._pending_queue_file = tmp_path / "pending_messages.jsonl"
        bot.send_alert = MagicMock(return_value=True)

        msg = TelegramMessage(
            content="📅 <b>EOD P/L SUMMARY</b>\nDelivery test",
            chat_id="chat-1",
            priority=MessagePriority.HIGH,
            message_type=MessageType.SUMMARY,
        )
        bot._handle_failed_delivery(msg, "retry_budget_exhausted")

        bot.send_alert.assert_called_once()
        kwargs = bot.send_alert.call_args.kwargs
        assert kwargs["severity"] == "warning"
        assert "EOD" in kwargs["title"]

    def test_replay_pending_messages_keeps_failures(self, tmp_path):
        bot = _make_bot()
        bot._pending_queue_file = tmp_path / "pending_messages.jsonl"

        msg1 = TelegramMessage(
            content="first",
            chat_id="chat-1",
            priority=MessagePriority.NORMAL,
            message_type=MessageType.SYSTEM,
        )
        msg2 = TelegramMessage(
            content="second",
            chat_id="chat-1",
            priority=MessagePriority.NORMAL,
            message_type=MessageType.SYSTEM,
        )
        bot._persist_pending_message(msg1, "f1")
        bot._persist_pending_message(msg2, "f2")

        bot._send_message_now = MagicMock(side_effect=[True, False])
        bot._replay_pending_messages(limit=10)

        assert bot._pending_queue_file.exists()
        remaining = bot._pending_queue_file.read_text(encoding="utf-8").splitlines()
        assert len(remaining) == 1
        assert "second" in remaining[0]

    def test_pending_retention_prunes_expired_and_overflow(self, tmp_path):
        bot = _make_bot()
        bot._pending_queue_file = tmp_path / "pending_messages.jsonl"
        bot._pending_max_rows = 2
        bot._pending_max_age_hours = 1

        now = datetime.now(UTC)
        rows = [
            {
                "content": "expired",
                "chat_id": "chat-1",
                "priority": "NORMAL",
                "message_type": "SYSTEM",
                "parse_mode": "HTML",
                "disable_notification": False,
                "retry_count": 0,
                "timestamp": now.isoformat(),
                "persisted_at": (now - timedelta(hours=2)).isoformat(),
            },
            {
                "content": "keep-1",
                "chat_id": "chat-1",
                "priority": "NORMAL",
                "message_type": "SYSTEM",
                "parse_mode": "HTML",
                "disable_notification": False,
                "retry_count": 0,
                "timestamp": now.isoformat(),
                "persisted_at": now.isoformat(),
            },
            {
                "content": "keep-2",
                "chat_id": "chat-1",
                "priority": "NORMAL",
                "message_type": "SYSTEM",
                "parse_mode": "HTML",
                "disable_notification": False,
                "retry_count": 0,
                "timestamp": now.isoformat(),
                "persisted_at": now.isoformat(),
            },
            {
                "content": "keep-3",
                "chat_id": "chat-1",
                "priority": "NORMAL",
                "message_type": "SYSTEM",
                "parse_mode": "HTML",
                "disable_notification": False,
                "retry_count": 0,
                "timestamp": now.isoformat(),
                "persisted_at": now.isoformat(),
            },
        ]
        bot._pending_queue_file.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

        bot._enforce_pending_retention()

        kept = [json.loads(line) for line in bot._pending_queue_file.read_text(encoding="utf-8").splitlines()]
        assert len(kept) == 2
        assert kept[0]["content"] == "keep-2"
        assert kept[1]["content"] == "keep-3"

    def test_restart_replay_flow_replays_persisted_messages(self, tmp_path):
        bot1 = _make_bot()
        queue_file = tmp_path / "pending_messages.jsonl"
        bot1._pending_queue_file = queue_file

        msg = TelegramMessage(
            content="restart-replay",
            chat_id="chat-1",
            priority=MessagePriority.NORMAL,
            message_type=MessageType.SYSTEM,
        )
        bot1._persist_pending_message(msg, "network_down")
        assert queue_file.exists()

        bot2 = _make_bot()
        bot2._pending_queue_file = queue_file
        bot2._send_message_now = MagicMock(return_value=True)

        bot2._replay_pending_messages(limit=10)

        bot2._send_message_now.assert_called_once()
        replayed_msg = bot2._send_message_now.call_args.args[0]
        assert replayed_msg.content == "restart-replay"
        assert not queue_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
