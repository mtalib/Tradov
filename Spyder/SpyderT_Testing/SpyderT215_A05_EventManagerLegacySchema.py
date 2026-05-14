#!/usr/bin/env python3
"""Focused regression for A05 EventManager legacy event_log schema migration."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventManager, EventType, reset_event_manager


def _create_legacy_event_log(db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                priority INTEGER NOT NULL,
                source TEXT,
                timestamp TIMESTAMP NOT NULL,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute("CREATE INDEX idx_event_type ON event_log(event_type)")
        conn.execute("CREATE INDEX idx_timestamp ON event_log(timestamp)")
        conn.execute("CREATE INDEX idx_source ON event_log(source)")
        conn.commit()


def test_a05_migrates_legacy_event_log_schema_before_batch_persist(tmp_path: Path) -> None:
    db_path = tmp_path / "events.db"
    _create_legacy_event_log(db_path)
    reset_event_manager()

    manager = EventManager(persist_events=True, db_path=db_path)
    event = Event(
        event_type=EventType.INFO,
        source="unit_test",
        data={"status": "ok"},
        metadata={"reason": "legacy_schema"},
    )

    manager._persist_batch([event])
    manager.executor.shutdown(wait=False)
    reset_event_manager()

    with sqlite3.connect(str(db_path)) as conn:
        columns = {
            str(row[1]).strip().lower()
            for row in conn.execute("PRAGMA table_info(event_log)")
        }
        persisted = conn.execute(
            "SELECT data, metadata FROM event_log WHERE event_id = ?",
            (event.event_id,),
        ).fetchone()

    assert "metadata" in columns
    assert persisted is not None
    assert json.loads(str(persisted[0])) == {"status": "ok"}
    assert json.loads(str(persisted[1])) == {"reason": "legacy_schema"}
