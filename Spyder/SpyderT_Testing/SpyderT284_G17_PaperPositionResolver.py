#!/usr/bin/env python3
"""Focused tests for G17 paper position resolver selection policy."""

from Spyder.SpyderG_GUI.SpyderG17_PaperPositionResolver import load_paper_open_positions


class _ManifestAwareDB:
    def __init__(self) -> None:
        self.active_calls = 0
        self.resume_calls = 0
        self.open_calls = 0

    def get_active_paper_open_positions(self):
        self.active_calls += 1
        return [{"symbol": "SPY", "quantity": -1, "_paper_open_origin": "active_session"}]

    def get_resume_eligible_open_positions(self):
        self.resume_calls += 1
        return []

    def get_open_positions(self):
        self.open_calls += 1
        return [{"symbol": "SPY", "quantity": -1}]


class _LegacyDB:
    def __init__(self) -> None:
        self.open_calls = 0

    def get_open_positions(self):
        self.open_calls += 1
        return [{"symbol": "SPY", "quantity": -1}]


def test_load_paper_open_positions_prefers_active_session_rows_while_active() -> None:
    db = _ManifestAwareDB()

    rows = load_paper_open_positions(db, trading_active=True)

    assert rows == [{"symbol": "SPY", "quantity": -1, "_paper_open_origin": "active_session"}]
    assert db.active_calls == 1
    assert db.resume_calls == 0
    assert db.open_calls == 0


def test_load_paper_open_positions_uses_manifest_eligible_rows_when_inactive() -> None:
    db = _ManifestAwareDB()

    rows = load_paper_open_positions(db, trading_active=False)

    assert rows == []
    assert db.active_calls == 0
    assert db.resume_calls == 1
    assert db.open_calls == 0


def test_load_paper_open_positions_falls_back_to_open_rows_without_manifest_api() -> None:
    db = _LegacyDB()

    rows = load_paper_open_positions(db, trading_active=True)

    assert rows == [{"symbol": "SPY", "quantity": -1, "_paper_open_origin": "active_session"}]
    assert db.open_calls == 1
