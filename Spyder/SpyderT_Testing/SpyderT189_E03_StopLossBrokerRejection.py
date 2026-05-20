"""SPEC-13 — E03 stop-loss must surface broker rejection, not silently downgrade.

Audit reference: 2026-05-02_Codebase_Audit_v27.md → SPEC-13.

The bug: ``StopLossManager._submit_stop_to_broker`` (E03:992-995) catches any
exception during broker submission and does:

    stop_order.status = StopStatus.ACTIVE  # Fallback to manual monitoring

The position is now *believed* to have a working stop while the broker has
nothing. Combined with manual ``check_stop_hit`` (E03:460) only firing when
wired to a tick stream, a transient broker error during entry can leave an
unstopped position — directly translating to unbounded loss in live trading.

Required behavior after SPEC-13:
- Submit failure (Exception) → ``stop_order.status = StopStatus.REJECTED``
  (NOT ``ACTIVE``).
- A ``RISK_ALERT`` event is emitted on the EventManager so operators see the
  failure.
- Optional: configurable retry (e.g. 3 attempts with backoff) before
  marking REJECTED.
- Existing path where ``broker_client is None`` (simulated mode) still maps
  to ``ACTIVE`` for back-compat.

These tests are RED until SPEC-13 ships.
"""

from __future__ import annotations

from datetime import datetime, timezone, UTC
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from Spyder.SpyderE_Risk.SpyderE03_StopLossManager import (
    PositionSide,
    StopOrder,
    StopStatus,
    StopType,
)


def _make_manager(broker_client=None, event_manager=None):
    """Construct a StopLossManager with the provided broker / event-manager."""
    from Spyder.SpyderE_Risk.SpyderE03_StopLossManager import StopLossManager

    return StopLossManager(
        broker_client=broker_client, event_manager=event_manager
    )


def _make_stop_order() -> StopOrder:
    return StopOrder(
        order_id="STOP-1",
        position_id="POS-1",
        stop_type=StopType.TRAILING,
        stop_price=495.0,
        original_stop=495.0,
        activation_price=None,
        quantity=10,
        side=PositionSide.LONG,
        status=StopStatus.PENDING,
        created_at=datetime.now(UTC),
        last_updated=datetime.now(UTC),
    )


class TestBrokerRejectionSurfaces:
    """SPEC-13: a broker submission failure must NOT silently downgrade to ACTIVE."""

    def test_broker_exception_marks_rejected_not_active(self):
        """When broker raises, status must become REJECTED, not ACTIVE."""
        broker = MagicMock()
        broker.place_order.side_effect = ConnectionError("Tradier down")
        em = MagicMock()
        mgr = _make_manager(broker_client=broker, event_manager=em)

        stop_order = _make_stop_order()
        result = mgr._submit_stop_to_broker(stop_order)

        assert result is False, (
            "_submit_stop_to_broker must return False on broker exception."
        )
        assert stop_order.status == StopStatus.REJECTED, (
            f"SPEC-13: a broker submission failure MUST set status to REJECTED, "
            f"not silently downgrade to ACTIVE (current behavior). "
            f"Got status={stop_order.status!r}. "
            f"Silent ACTIVE downgrade leaves the position believing it has a stop "
            f"while the broker has nothing — direct path to unbounded loss."
        )

    def test_broker_rejection_emits_risk_alert(self):
        """A risk-alert event must be emitted so operators see the failure."""
        broker = MagicMock()
        broker.place_order.side_effect = ConnectionError("Tradier down")
        em = MagicMock()
        mgr = _make_manager(broker_client=broker, event_manager=em)

        stop_order = _make_stop_order()
        mgr._submit_stop_to_broker(stop_order)

        # Look for any event-bus emit/publish call referencing a risk-alert / stop-rejection.
        all_calls = (
            list(em.emit.call_args_list)
            + list(em.publish.call_args_list)
        )
        # Stringify for a tolerant match (event-bus API differs across versions).
        flat = " ".join(str(c) for c in all_calls).lower()
        assert any(
            tok in flat for tok in ("risk_alert", "risk_violation", "stop_rejected", "stop_order_failed", "stop_loss_rejected")
        ), (
            "SPEC-13: a stop-submission failure must emit a RISK_ALERT (or "
            "equivalent) event on the EventManager. Operators currently get "
            "no signal that a position is unstopped. "
            f"Saw event-manager calls: {all_calls}"
        )


class TestSimulatedModePreserved:
    """Regression guard: when broker_client is None, ACTIVE mapping must remain."""

    def test_no_broker_client_still_marks_active(self):
        """Backwards compat: simulated/standalone runs without a broker stay ACTIVE."""
        mgr = _make_manager(broker_client=None, event_manager=None)
        stop_order = _make_stop_order()

        result = mgr._submit_stop_to_broker(stop_order)

        assert result is True
        assert stop_order.status == StopStatus.ACTIVE, (
            "Regression guard: when no broker is wired (simulation/test mode), "
            "the ACTIVE-on-no-client path must remain — only EXCEPTION cases "
            "should be downgraded by SPEC-13."
        )


class TestSuccessfulSubmissionStillWorks:
    """Regression guard: SPEC-13 must not break the happy path."""

    def test_successful_submission_marks_submitted(self):
        broker = MagicMock()
        broker.place_order.return_value = "TRADIER-99999"
        mgr = _make_manager(broker_client=broker, event_manager=None)
        stop_order = _make_stop_order()

        result = mgr._submit_stop_to_broker(stop_order)

        assert result is True
        assert stop_order.broker_order_id == "TRADIER-99999"
        assert stop_order.status == StopStatus.SUBMITTED, (
            f"Happy path: successful submission must yield SUBMITTED, got {stop_order.status!r}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
