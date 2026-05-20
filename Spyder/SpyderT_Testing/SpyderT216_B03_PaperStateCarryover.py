#!/usr/bin/env python3
"""Focused tests for paper PositionTracker state carryover handling."""

import json
from pathlib import Path


class _StubBroker:
    def __init__(self, positions=None):
        self._positions = positions if positions is not None else []

    def get_positions(self):
        return self._positions


def _write_state(path: Path) -> None:
    payload = {
        "saved_at": "2026-05-14T00:00:00+00:00",
        "positions": {
            "SPY260515C00580000": {
                "symbol": "SPY260515C00580000",
                "quantity": -1,
                "average_fill_price": 1.3,
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_b03_live_tracker_restores_persisted_state(monkeypatch, tmp_path) -> None:
    from Spyder.SpyderB_Broker.SpyderB03_PositionTracker import PositionTracker

    state_path = tmp_path / "position_tracker_state.json"
    _write_state(state_path)

    tracker = PositionTracker(_StubBroker())
    tracker._state_path = state_path
    monkeypatch.setattr(tracker, "_start_background_threads", lambda: None)
    monkeypatch.setattr(tracker, "_stop_background_threads", lambda: None)

    try:
        tracker.start()
        assert tracker.get_positions()["SPY260515C00580000"]["quantity"] == -1
    finally:
        tracker.stop()


def test_b03_paper_tracker_discards_stale_persisted_state(monkeypatch, tmp_path) -> None:
    from Spyder.SpyderB_Broker.SpyderB03_PositionTracker import PositionTracker

    state_path = tmp_path / "position_tracker_state.json"
    _write_state(state_path)

    tracker = PositionTracker(
        _StubBroker(),
        restore_state_on_start=False,
        persist_state_on_stop=False,
    )
    tracker._state_path = state_path
    monkeypatch.setattr(tracker, "_start_background_threads", lambda: None)
    monkeypatch.setattr(tracker, "_stop_background_threads", lambda: None)

    tracker.start()
    try:
        assert tracker.get_positions() == {}
        assert state_path.exists() is False
        tracker.positions["SPY260515C00580000"] = {
            "symbol": "SPY260515C00580000",
            "quantity": -1,
            "average_fill_price": 1.3,
        }
    finally:
        tracker.stop()

    assert state_path.exists() is False


def test_b03_paper_tracker_record_fill_does_not_persist_runtime_state(tmp_path) -> None:
    from Spyder.SpyderB_Broker.SpyderB03_PositionTracker import PositionTracker

    state_path = tmp_path / "position_tracker_state.json"

    tracker = PositionTracker(
        _StubBroker(),
        restore_state_on_start=False,
        persist_state_on_stop=False,
    )
    tracker._state_path = state_path

    tracker.record_fill(
        {
            "symbol": "SPY260515C00580000",
            "side": "sell_to_open",
            "quantity": 1,
            "fill_price": 1.3,
            "order_id": "PAPER-1",
        }
    )

    assert tracker.get_positions()["SPY260515C00580000"]["quantity"] == -1
    assert state_path.exists() is False
