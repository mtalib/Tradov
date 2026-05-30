#!/usr/bin/env python3
"""Focused tests for G17 paper position resolver selection and grouping policy."""

from Spyder.SpyderG_GUI.SpyderG17_PaperPositionResolver import (
    load_paper_open_positions,
    restore_paper_spreads_from_positions,
)


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


class _DisplayEligibleDB:
    def __init__(self) -> None:
        self.display_calls = 0
        self.active_calls = 0

    def get_display_eligible_paper_open_positions(self):
        self.display_calls += 1
        return [{"position_id": "carry-1", "symbol": "SPY260528C00748000", "quantity": 10}]

    def get_active_paper_open_positions(self):
        self.active_calls += 1
        return [{"position_id": "active-1", "symbol": "SPY260530P00730000", "quantity": -1, "_paper_open_origin": "active_session"}]

    def get_resume_eligible_open_positions(self):
        return []


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


def test_load_paper_open_positions_uses_display_eligible_rows_when_inactive() -> None:
    db = _DisplayEligibleDB()

    rows = load_paper_open_positions(db, trading_active=False)

    assert rows == [{
        "position_id": "carry-1",
        "symbol": "SPY260528C00748000",
        "quantity": 10,
        "_paper_open_origin": "carryover",
    }]
    assert db.display_calls == 1
    assert db.active_calls == 0


def test_load_paper_open_positions_merges_display_eligible_carryover_while_active() -> None:
    db = _DisplayEligibleDB()

    rows = load_paper_open_positions(db, trading_active=True)

    assert rows == [
        {
            "position_id": "carry-1",
            "symbol": "SPY260528C00748000",
            "quantity": 10,
            "_paper_open_origin": "carryover",
        },
        {
            "position_id": "active-1",
            "symbol": "SPY260530P00730000",
            "quantity": -1,
            "_paper_open_origin": "active_session",
        },
    ]
    assert db.display_calls == 1
    assert db.active_calls == 1


def test_restore_paper_spreads_from_positions_rebuilds_broken_wing_butterfly() -> None:
    restored, leftovers = restore_paper_spreads_from_positions(
        [
            {
                "position_id": "paper:SPY260526P00600000",
                "symbol": "SPY260526P00600000",
                "quantity": 1,
                "entry_price": 0.90,
                "unrealized_pnl": 5.0,
                "strategy_id": "BrokenWingButterfly",
                "status": "OPEN",
                "opened_at": "2026-05-26T13:51:09+00:00",
                "expiration": "2026-05-26",
                "strike": 600.0,
                "option_type": "put",
            },
            {
                "position_id": "paper:SPY260526P00599000",
                "symbol": "SPY260526P00599000",
                "quantity": -2,
                "entry_price": 1.35,
                "unrealized_pnl": -12.0,
                "strategy_id": "BrokenWingButterfly",
                "status": "OPEN",
                "opened_at": "2026-05-26T13:51:09+00:00",
                "expiration": "2026-05-26",
                "strike": 599.0,
                "option_type": "put",
            },
            {
                "position_id": "paper:SPY260526P00596000",
                "symbol": "SPY260526P00596000",
                "quantity": 1,
                "entry_price": 0.40,
                "unrealized_pnl": 7.0,
                "strategy_id": "BrokenWingButterfly",
                "status": "OPEN",
                "opened_at": "2026-05-26T13:51:10+00:00",
                "expiration": "2026-05-26",
                "strike": 596.0,
                "option_type": "put",
            },
        ]
    )

    assert leftovers == []
    assert len(restored) == 1
    assert restored[0]["structure"] == "BROKEN_WING_BUTTERFLY"
    assert [leg["symbol"] for leg in restored[0]["legs"]] == [
        "SPY260526P00600000",
        "SPY260526P00599000",
        "SPY260526P00596000",
    ]


def test_restore_paper_spreads_from_positions_rebuilds_iron_butterfly() -> None:
    restored, leftovers = restore_paper_spreads_from_positions(
        [
            {
                "position_id": "paper:SPY260619P00594000",
                "symbol": "SPY260619P00594000",
                "quantity": 1,
                "entry_price": 0.40,
                "unrealized_pnl": -3.0,
                "strategy_id": "IronButterfly",
                "status": "OPEN",
                "opened_at": "2026-05-26T13:51:09+00:00",
                "expiration": "2026-06-19",
                "strike": 594.0,
                "option_type": "put",
            },
            {
                "position_id": "paper:SPY260619P00599000",
                "symbol": "SPY260619P00599000",
                "quantity": -1,
                "entry_price": 1.28,
                "unrealized_pnl": 8.0,
                "strategy_id": "IronButterfly",
                "status": "OPEN",
                "opened_at": "2026-05-26T13:51:09+00:00",
                "expiration": "2026-06-19",
                "strike": 599.0,
                "option_type": "put",
            },
            {
                "position_id": "paper:SPY260619C00599000",
                "symbol": "SPY260619C00599000",
                "quantity": -1,
                "entry_price": 1.32,
                "unrealized_pnl": 6.0,
                "strategy_id": "IronButterfly",
                "status": "OPEN",
                "opened_at": "2026-05-26T13:51:10+00:00",
                "expiration": "2026-06-19",
                "strike": 599.0,
                "option_type": "call",
            },
            {
                "position_id": "paper:SPY260619C00604000",
                "symbol": "SPY260619C00604000",
                "quantity": 1,
                "entry_price": 0.44,
                "unrealized_pnl": -4.0,
                "strategy_id": "IronButterfly",
                "status": "OPEN",
                "opened_at": "2026-05-26T13:51:10+00:00",
                "expiration": "2026-06-19",
                "strike": 604.0,
                "option_type": "call",
            },
        ]
    )

    assert leftovers == []
    assert len(restored) == 1
    assert restored[0]["structure"] == "IRON_BUTTERFLY"
    assert [leg["symbol"] for leg in restored[0]["legs"]] == [
        "SPY260619P00594000",
        "SPY260619P00599000",
        "SPY260619C00599000",
        "SPY260619C00604000",
    ]
