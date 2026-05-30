#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderH_Storage
Module: SpyderH05_TradingSessionDB.py
Purpose: Dual-database session manager for live and paper trading records

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-24 Time: 00:00:00

Module Description:
    Provides two identically-schemed SQLite databases — one for live trading
    (spyder_live.db) and one for paper trading (spyder_paper.db) — so all
    P&L, trade, position, and account-snapshot data is persisted in the same
    structure regardless of mode.  Both databases are created automatically on
    first use.

    All analytics code, reporting modules, and dashboard queries can target
    either database through the same TradingSessionDB interface, enabling true
    parity between live and paper trading.

Key Features:
    • Identical schema for live and paper databases
    • Factory class-methods: TradingSessionDB.for_live() / .for_paper()
    • record_trade()            — insert a completed trade record
    • record_account_snapshot() — periodic equity/cash snapshot
    • upsert_position()         — insert or update an open/closed position
    • get_latest_snapshot()     — most recent account state
    • get_trades_today()        — all trades from today (ET)
    • get_open_positions()      — all open positions
    • Thread-safe via RLock + per-call connections (WAL mode)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import os
import sqlite3
import threading
import uuid
from datetime import date, datetime, timedelta, UTC
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    import logging
    SpyderLogger = type("SpyderLogger", (), {
        "get_logger": staticmethod(lambda name: logging.getLogger(name))
    })()

# ==============================================================================
# CONSTANTS
# ==============================================================================
#: Path to the live-trading SQLite database.
LIVE_DB_PATH = Path("data/spyder_live.db")

#: Path to the paper-trading SQLite database.
PAPER_DB_PATH = Path("data/spyder_paper.db")

_PAPER_STATE_SUFFIX = ".paper_state.json"
_PAPER_ACTIVE_SESSION_SUFFIX = ".active_session.json"
_EASTERN_TIMEZONE = ZoneInfo("America/New_York")

# ==============================================================================
# SCHEMA
# ==============================================================================
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id        TEXT    PRIMARY KEY,
    timestamp       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    symbol          TEXT    NOT NULL,
    strategy        TEXT    NOT NULL DEFAULT '',
    trade_type      TEXT    NOT NULL,
    side            TEXT    NOT NULL,
    quantity        INTEGER NOT NULL,
    price           REAL    NOT NULL,
    commission      REAL    NOT NULL DEFAULT 0.0,
    slippage        REAL    NOT NULL DEFAULT 0.0,
    realized_pnl    REAL    NOT NULL DEFAULT 0.0,
    order_id        TEXT,
    expiration      TEXT,
    strike          REAL,
    option_type     TEXT,
    notes           TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE TABLE IF NOT EXISTS positions (
    position_id     TEXT    PRIMARY KEY,
    symbol          TEXT    NOT NULL,
    strategy        TEXT    NOT NULL DEFAULT '',
    quantity        INTEGER NOT NULL,
    entry_price     REAL    NOT NULL,
    current_price   REAL,
    unrealized_pnl  REAL    NOT NULL DEFAULT 0.0,
    realized_pnl    REAL    NOT NULL DEFAULT 0.0,
    status          TEXT    NOT NULL DEFAULT 'OPEN',
    opened_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    closed_at       TEXT,
    delta           REAL,
    gamma           REAL,
    theta           REAL,
    vega            REAL,
    expiration      TEXT,
    strike          REAL,
    option_type     TEXT,
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    snapshot_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    cash            REAL    NOT NULL,
    equity          REAL    NOT NULL,
    buying_power    REAL    NOT NULL,
    realized_pnl    REAL    NOT NULL DEFAULT 0.0,
    unrealized_pnl  REAL    NOT NULL DEFAULT 0.0,
    total_trades    INTEGER NOT NULL DEFAULT 0,
    winning_trades  INTEGER NOT NULL DEFAULT 0,
    losing_trades   INTEGER NOT NULL DEFAULT 0,
    max_drawdown    REAL    NOT NULL DEFAULT 0.0
);
"""

_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_trades_timestamp  ON trades(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_trades_symbol     ON trades(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_positions_status  ON positions(status)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_ts      ON account_snapshots(timestamp)",
]


# ==============================================================================
# TRADING SESSION DATABASE
# ==============================================================================
class TradingSessionDB:
    """
    Lightweight, thread-safe SQLite session database for a single trading mode.

    Both live and paper instances share identical schema so all analytics,
    reports, and dashboard queries are fully portable between modes.

    Usage::

        live_db  = TradingSessionDB.for_live()
        paper_db = TradingSessionDB.for_paper()

        paper_db.record_trade(symbol="SPY", trade_type="STO", side="sell",
                              quantity=1, price=2.55, realized_pnl=255.0)
    """

    def __init__(self, db_path: Path) -> None:
        """
        Initialize session database at *db_path*.

        Args:
            db_path: Filesystem path for the SQLite file. Parent directory is
                     created automatically if it does not exist.
        """
        self.db_path = db_path
        self.logger = SpyderLogger.get_logger(__name__)
        self._lock = threading.RLock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._warn_if_unexpected_paper_reset()
        self.logger.debug("TradingSessionDB ready: %s", db_path)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def for_live(cls) -> "TradingSessionDB":
        """Return a TradingSessionDB backed by the live-trading database."""
        return cls(LIVE_DB_PATH)

    @classmethod
    def for_paper(cls) -> "TradingSessionDB":
        """Return a TradingSessionDB backed by the paper-trading database."""
        return cls(PAPER_DB_PATH)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a WAL-mode connection with Row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _is_paper_db(self) -> bool:
        """Return True when this DB is the paper-trading ledger."""
        return "paper" in self.db_path.stem.lower()

    def _init_schema(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self._lock, self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)
            for idx_sql in _INDEXES_SQL:
                conn.execute(idx_sql)
            conn.commit()

    def _paper_state_path(self) -> Path:
        """Return the sidecar file storing paper DB audit state."""
        return self.db_path.with_suffix(_PAPER_STATE_SUFFIX)

    def _paper_active_session_path(self) -> Path:
        """Return the sidecar file marking an active paper session."""
        return self.db_path.with_suffix(_PAPER_ACTIVE_SESSION_SUFFIX)

    def _load_sidecar_json(self, path: Path, *, label: str) -> dict[str, Any]:
        """Load a small JSON sidecar file, returning an empty dict on failure."""
        if not path.exists():
            return {}

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.logger.warning("Could not read %s %s: %s", label, path, exc)
            return {}

        return dict(payload) if isinstance(payload, dict) else {}

    def _write_sidecar_json(self, path: Path, payload: dict[str, Any]) -> None:
        """Write a JSON sidecar file atomically."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)

    def _get_primary_table_counts(self) -> dict[str, int]:
        """Return row counts for the primary paper-session tables."""
        with self._connect() as conn:
            return {
                "trades": int(conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]),
                "positions": int(conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]),
                "account_snapshots": int(
                    conn.execute("SELECT COUNT(*) FROM account_snapshots").fetchone()[0]
                ),
            }

    def _record_paper_activity(self, activity: str) -> None:
        """Persist the last observed paper DB write so surprise wipes are detectable."""
        if not self._is_paper_db():
            return

        state = self._load_sidecar_json(self._paper_state_path(), label="paper DB state")
        state.update(
            {
                "schema": 1,
                "db_path": str(self.db_path),
                "expected_empty": False,
                "last_activity": str(activity or "write"),
                "last_activity_at": datetime.now(UTC).isoformat(),
            }
        )
        self._write_sidecar_json(self._paper_state_path(), state)

    def _mark_expected_paper_reset(
        self,
        *,
        reason: str,
        actor: str,
        cleared_counts: dict[str, int],
    ) -> None:
        """Persist metadata for an intentional paper DB reset."""
        if not self._is_paper_db():
            return

        state = self._load_sidecar_json(self._paper_state_path(), label="paper DB state")
        state.update(
            {
                "schema": 1,
                "db_path": str(self.db_path),
                "expected_empty": True,
                "last_reset_at": datetime.now(UTC).isoformat(),
                "last_reset_reason": str(reason or "unspecified"),
                "last_reset_actor": str(actor or "unknown"),
                "last_reset_cleared_counts": dict(cleared_counts),
            }
        )
        self._write_sidecar_json(self._paper_state_path(), state)

    def _load_active_paper_session(self) -> dict[str, Any]:
        """Return the last active paper-session marker payload, if any."""
        if not self._is_paper_db():
            return {}
        return self._load_sidecar_json(
            self._paper_active_session_path(),
            label="paper active-session marker",
        )

    def _warn_if_unexpected_paper_reset(self) -> None:
        """Log when a paper DB is suddenly empty after prior recorded activity."""
        if not self._is_paper_db():
            return

        state = self._load_sidecar_json(self._paper_state_path(), label="paper DB state")
        if not state or state.get("expected_empty"):
            return

        last_activity_at = str(state.get("last_activity_at") or "").strip()
        if not last_activity_at:
            return

        counts = self._get_primary_table_counts()
        if any(counts.values()):
            return

        self.logger.warning(
            "Paper session DB %s is empty on startup after prior activity at %s without an explicit reset marker; it may have been cleared outside TradingSessionDB",
            self.db_path,
            last_activity_at,
        )

    def _carryover_manifest_path(self) -> Path:
        """Return the companion manifest path used for paper restart carryover."""
        return self.db_path.with_suffix(".carryover_manifest.json")

    @staticmethod
    def _parse_expiration_date(value: Any) -> date | None:
        """Parse an ISO expiration date, returning None when unavailable."""
        normalized_value = str(value or "").strip()
        if not normalized_value:
            return None

        try:
            return datetime.fromisoformat(normalized_value).date()
        except ValueError:
            return None

    @classmethod
    def _extract_occ_expiration_date(cls, symbol: Any) -> date | None:
        """Parse the expiration date encoded in an OCC option symbol."""
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return None

        idx = 0
        while idx < len(normalized_symbol) and not normalized_symbol[idx].isdigit():
            idx += 1

        if idx == 0 or idx + 15 > len(normalized_symbol):
            return None

        expiration_token = normalized_symbol[idx:idx + 6]
        option_type = normalized_symbol[idx + 6:idx + 7]
        strike_token = normalized_symbol[idx + 7:idx + 15]
        if not (
            expiration_token.isdigit()
            and option_type in {"C", "P"}
            and strike_token.isdigit()
        ):
            return None

        try:
            return datetime.strptime(expiration_token, "%y%m%d").date()
        except ValueError:
            return None

    @classmethod
    def _resolve_position_expiration_date(cls, position_row: dict[str, Any]) -> date | None:
        """Resolve an option expiration date from explicit metadata or OCC symbol."""
        expiration_date = cls._parse_expiration_date(position_row.get("expiration"))
        if expiration_date is not None:
            return expiration_date
        return cls._extract_occ_expiration_date(position_row.get("symbol"))

    @classmethod
    def _is_resume_eligible_paper_position(
        cls,
        position_row: dict[str, Any],
        *,
        reference_time: datetime | None = None,
    ) -> bool:
        """Return True when a paper position is eligible for restart carryover."""
        expiration_date = cls._resolve_position_expiration_date(position_row)
        if expiration_date is None:
            return True

        current_utc = cls._normalize_reference_time(reference_time)
        current_et_date = current_utc.astimezone(_EASTERN_TIMEZONE).date()
        return expiration_date > current_et_date

    @classmethod
    def _is_display_eligible_paper_position(
        cls,
        position_row: dict[str, Any],
        *,
        reference_time: datetime | None = None,
    ) -> bool:
        """Return True when a paper position should remain visible in the dashboard.

        Dashboard visibility is intentionally broader than restart eligibility:
        manifest-backed positions that expire today should still be shown so the
        operator can see and manually manage them, even though automation should
        not resume them as carryover strategies.
        """
        expiration_date = cls._resolve_position_expiration_date(position_row)
        if expiration_date is None:
            return True

        current_utc = cls._normalize_reference_time(reference_time)
        current_et_date = current_utc.astimezone(_EASTERN_TIMEZONE).date()
        return expiration_date >= current_et_date

    def _get_manifest_backed_paper_open_positions(
        self,
        *,
        allow_expiring_today: bool,
    ) -> list[dict[str, Any]]:
        """Return manifest-backed paper OPEN rows filtered for one visibility policy."""
        open_rows = self.get_open_positions()
        if "paper" not in self.db_path.stem.lower():
            return open_rows

        manifest_rows = self._load_paper_carryover_manifest()
        if not manifest_rows:
            return []

        manifest_by_symbol = {
            str(row.get("symbol") or "").strip(): row
            for row in manifest_rows
            if str(row.get("symbol") or "").strip()
        }
        eligible: list[dict[str, Any]] = []
        for row in open_rows:
            symbol = str(row.get("symbol") or "").strip()
            manifest_row = manifest_by_symbol.get(symbol)
            if manifest_row is None:
                continue

            carryover_row = dict(row)
            if not str(carryover_row.get("expiration") or "").strip():
                carryover_row["expiration"] = manifest_row.get("expiration")

            eligibility_fn = (
                self._is_display_eligible_paper_position
                if allow_expiring_today
                else self._is_resume_eligible_paper_position
            )
            if not eligibility_fn(carryover_row):
                continue
            if self._matches_carryover_manifest(row, manifest_row):
                eligible.append(row)

        return eligible

    def _load_paper_carryover_manifest(self) -> list[dict[str, Any]]:
        """Load the last graceful-shutdown paper carryover manifest."""
        if "paper" not in self.db_path.stem.lower():
            return []

        manifest_path = self._carryover_manifest_path()
        if not manifest_path.exists():
            return []

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.logger.warning("Could not read paper carryover manifest %s: %s", manifest_path, exc)
            return []

        positions = payload.get("positions") if isinstance(payload, dict) else []
        if not isinstance(positions, list):
            return []
        return [dict(row) for row in positions if isinstance(row, dict)]

    def save_paper_carryover_manifest(
        self,
        positions: list[dict[str, Any]],
        *,
        session_id: str = "",
    ) -> None:
        """Persist which paper positions were actually active at shutdown."""
        if "paper" not in self.db_path.stem.lower():
            return

        manifest_rows: list[dict[str, Any]] = []
        for raw_position in positions:
            if not isinstance(raw_position, dict):
                continue
            if not self._is_resume_eligible_paper_position(raw_position):
                continue
            symbol = str(raw_position.get("symbol") or "").strip()
            strategy = str(raw_position.get("strategy") or "").strip()
            position_id = str(raw_position.get("position_id") or "").strip()
            opened_at = str(raw_position.get("opened_at") or "").strip()
            expiration = str(raw_position.get("expiration") or "").strip()
            try:
                quantity = int(raw_position.get("quantity") or 0)
            except (TypeError, ValueError):
                quantity = 0
            if not symbol or quantity == 0:
                continue
            manifest_rows.append(
                {
                    "symbol": symbol,
                    "position_id": position_id,
                    "strategy": strategy,
                    "quantity": quantity,
                    "opened_at": opened_at,
                    "expiration": expiration,
                }
            )

        if not manifest_rows:
            self.clear_paper_carryover_manifest()
            return

        manifest_path = self._carryover_manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": 1,
            "saved_at": datetime.now(UTC).isoformat(),
            "session_id": str(session_id or ""),
            "positions": manifest_rows,
        }
        tmp_path = manifest_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(manifest_path)

    def clear_paper_carryover_manifest(self) -> None:
        """Remove the last graceful-shutdown paper carryover manifest."""
        manifest_path = self._carryover_manifest_path()
        try:
            if manifest_path.exists():
                manifest_path.unlink()
        except Exception as exc:
            self.logger.warning("Could not clear paper carryover manifest %s: %s", manifest_path, exc)

    def mark_paper_session_active(self, session_id: str, *, owner: str = "") -> None:
        """Record that a paper trading session is currently active.

        Args:
            session_id: Runtime session identifier.
            owner: Optional component label marking the session active.
        """
        if not self._is_paper_db():
            return

        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return

        payload = {
            "schema": 1,
            "session_id": normalized_session_id,
            "owner": str(owner or ""),
            "pid": os.getpid(),
            "marked_at": datetime.now(UTC).isoformat(),
        }
        self._write_sidecar_json(self._paper_active_session_path(), payload)

    def clear_paper_session_active(self, *, reason: str = "") -> None:
        """Clear the active paper-session marker.

        Args:
            reason: Optional operator or lifecycle reason for clearing the marker.
        """
        if not self._is_paper_db():
            return

        marker_path = self._paper_active_session_path()
        try:
            if marker_path.exists():
                marker_path.unlink()
        except Exception as exc:
            self.logger.warning("Could not clear paper active-session marker %s: %s", marker_path, exc)
            return

        if reason:
            state = self._load_sidecar_json(self._paper_state_path(), label="paper DB state")
            state.update(
                {
                    "schema": 1,
                    "last_session_clear_reason": str(reason),
                    "last_session_cleared_at": datetime.now(UTC).isoformat(),
                }
            )
            self._write_sidecar_json(self._paper_state_path(), state)

    def has_active_paper_session_marker(self) -> bool:
        """Return True when the paper DB currently has an active-session marker."""
        if not self._is_paper_db():
            return False

        active_session = self._load_active_paper_session()
        return bool(str(active_session.get("session_id") or "").strip())

    @classmethod
    def _parse_iso_timestamp_utc(cls, value: Any) -> datetime | None:
        """Return an aware UTC datetime parsed from an ISO timestamp string."""
        normalized_value = str(value or "").strip()
        if not normalized_value:
            return None

        try:
            parsed = datetime.fromisoformat(normalized_value)
        except ValueError:
            return None

        return cls._normalize_reference_time(parsed)

    def purge_stale_paper_open_positions(self, *, actor: str = "") -> dict[str, Any]:
        """Delete stale paper OPEN rows that predate the current active session.

        Only rows older than the current paper active-session marker are removed,
        and only when no carryover manifest exists. This preserves legitimate
        carryover rows and current-session positions while cleaning orphaned
        pre-session state that can otherwise linger in H05 indefinitely.
        """
        if not self._is_paper_db():
            raise RuntimeError("purge_stale_paper_open_positions() is only valid for the paper DB")

        manifest_rows = self._load_paper_carryover_manifest()
        if manifest_rows:
            return {
                "deleted_positions": 0,
                "cutoff": "",
                "session_id": "",
            }

        active_session = self._load_active_paper_session()
        cutoff = self._parse_iso_timestamp_utc(active_session.get("marked_at"))
        session_id = str(active_session.get("session_id") or "").strip()
        if cutoff is None:
            return {
                "deleted_positions": 0,
                "cutoff": "",
                "session_id": session_id,
            }

        stale_position_ids: list[str] = []
        for row in self.get_open_positions():
            position_id = str(row.get("position_id") or "").strip()
            opened_at = self._parse_iso_timestamp_utc(row.get("opened_at"))
            if not position_id or opened_at is None:
                continue
            if opened_at < cutoff:
                stale_position_ids.append(position_id)

        if not stale_position_ids:
            return {
                "deleted_positions": 0,
                "cutoff": cutoff.isoformat(),
                "session_id": session_id,
            }

        with self._lock, self._connect() as conn:
            conn.executemany(
                "DELETE FROM positions WHERE position_id = ?",
                [(position_id,) for position_id in stale_position_ids],
            )
            conn.commit()
            self._record_paper_activity("purge_stale_paper_open_positions")

        self.logger.warning(
            "Purged stale paper OPEN rows before active session: path=%s actor=%s session_id=%s cutoff=%s deleted=%s",
            self.db_path,
            actor or "unknown",
            session_id or "unknown",
            cutoff.isoformat(),
            len(stale_position_ids),
        )
        return {
            "deleted_positions": len(stale_position_ids),
            "cutoff": cutoff.isoformat(),
            "session_id": session_id,
        }

    def reset_paper_ledger(
        self,
        *,
        reason: str,
        actor: str = "",
        allow_if_session_active: bool = False,
    ) -> dict[str, int]:
        """Clear paper-session tables with an audit marker and active-session guard.

        Args:
            reason: Human-readable reason for the reset.
            actor: Optional caller or operator label.
            allow_if_session_active: When True, bypass the active-session guard.

        Returns:
            A map of row counts that were cleared from each primary table.

        Raises:
            RuntimeError: If called for a non-paper DB or while a paper session is active.
        """
        if not self._is_paper_db():
            raise RuntimeError("reset_paper_ledger() is only valid for the paper DB")

        active_session = self._load_active_paper_session()
        active_session_id = str(active_session.get("session_id") or "").strip()
        if active_session_id and not allow_if_session_active:
            raise RuntimeError(
                f"Cannot reset paper DB while session {active_session_id} is marked active"
            )

        with self._lock:
            with self._connect() as conn:
                cleared_counts = {
                    "trades": int(conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]),
                    "positions": int(conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]),
                    "account_snapshots": int(
                        conn.execute("SELECT COUNT(*) FROM account_snapshots").fetchone()[0]
                    ),
                }
                conn.execute("DELETE FROM trades")
                conn.execute("DELETE FROM positions")
                conn.execute("DELETE FROM account_snapshots")
                conn.execute("DELETE FROM sqlite_sequence WHERE name = 'account_snapshots'")
                conn.commit()
            self.clear_paper_carryover_manifest()
            self._mark_expected_paper_reset(
                reason=reason,
                actor=actor,
                cleared_counts=cleared_counts,
            )

        self.logger.warning(
            "Paper session DB reset: path=%s actor=%s reason=%s cleared=%s",
            self.db_path,
            actor or "unknown",
            reason,
            cleared_counts,
        )
        return cleared_counts

    @staticmethod
    def _matches_carryover_manifest(
        position_row: dict[str, Any],
        manifest_row: dict[str, Any],
    ) -> bool:
        """Return True when an H05 position row matches the last active manifest row."""
        if str(position_row.get("symbol") or "").strip() != str(manifest_row.get("symbol") or "").strip():
            return False

        row_position_id = str(position_row.get("position_id") or "").strip()
        manifest_position_id = str(manifest_row.get("position_id") or "").strip()
        if manifest_position_id and row_position_id and row_position_id != manifest_position_id:
            return False

        try:
            row_quantity = int(position_row.get("quantity") or 0)
            manifest_quantity = int(manifest_row.get("quantity") or 0)
        except (TypeError, ValueError):
            return False
        if row_quantity != manifest_quantity:
            return False

        row_strategy = str(position_row.get("strategy") or "").strip()
        manifest_strategy = str(manifest_row.get("strategy") or "").strip()
        if manifest_strategy and row_strategy and row_strategy != manifest_strategy:
            return False

        row_opened_at = str(position_row.get("opened_at") or "").strip()
        manifest_opened_at = str(manifest_row.get("opened_at") or "").strip()
        if manifest_opened_at:
            if not row_opened_at:
                return False
            try:
                row_opened_dt = datetime.fromisoformat(row_opened_at)
                manifest_opened_dt = datetime.fromisoformat(manifest_opened_at)
            except ValueError:
                if row_opened_at != manifest_opened_at:
                    return False
            else:
                if row_opened_dt != manifest_opened_dt:
                    return False

        return True

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def record_trade(
        self,
        *,
        symbol: str,
        trade_type: str,
        side: str,
        quantity: int,
        price: float,
        commission: float = 0.0,
        slippage: float = 0.0,
        realized_pnl: float = 0.0,
        strategy: str = "",
        order_id: str | None = None,
        expiration: str | None = None,
        strike: float | None = None,
        option_type: str | None = None,
        notes: str = "",
        timestamp: datetime | None = None,
    ) -> str:
        """
        Insert a completed trade record into the database.

        Args:
            symbol:       Instrument ticker (e.g. "SPY", "SPY241220P550").
            trade_type:   Action code — BTO, STO, BTC, STC, BUY, SELL, etc.
            side:         "buy" or "sell".
            quantity:     Number of shares/contracts.
            price:        Fill price per share/contract.
            commission:   Commission paid (default 0.0).
            slippage:     Slippage incurred vs. mid (default 0.0).
            realized_pnl: Realized P&L for closing trades (default 0.0).
            strategy:     Strategy name (e.g. "BullPutSpread").
            order_id:     Broker order ID for cross-reference.
            expiration:   Options expiration date string (YYYY-MM-DD).
            strike:       Options strike price.
            option_type:  "call" or "put".
            notes:        Free-text annotation.
            timestamp:    UTC trade timestamp (defaults to utcnow).

        Returns:
            The generated trade_id (UUID string).
        """
        trade_id = str(uuid.uuid4())
        ts = (timestamp or datetime.now(UTC)).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                    INSERT INTO trades
                        (trade_id, timestamp, symbol, strategy, trade_type, side,
                         quantity, price, commission, slippage, realized_pnl,
                         order_id, expiration, strike, option_type, notes)
                    VALUES
                        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    trade_id, ts, symbol, strategy, trade_type, side,
                    quantity, price, commission, slippage, realized_pnl,
                    order_id, expiration, strike, option_type, notes,
                ),
            )
            conn.commit()
            self._record_paper_activity("record_trade")
        return trade_id

    def record_account_snapshot(
        self,
        *,
        cash: float,
        equity: float,
        buying_power: float,
        realized_pnl: float = 0.0,
        unrealized_pnl: float = 0.0,
        total_trades: int = 0,
        winning_trades: int = 0,
        losing_trades: int = 0,
        max_drawdown: float = 0.0,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Insert a periodic account-state snapshot.

        Args:
            cash:           Available cash balance.
            equity:         Total portfolio equity (cash + open positions MTM).
            buying_power:   Remaining buying power.
            realized_pnl:   Cumulative realized P&L for the session.
            unrealized_pnl: Current mark-to-market unrealized P&L.
            total_trades:   Total trades executed so far.
            winning_trades: Number of winning trades.
            losing_trades:  Number of losing trades.
            max_drawdown:   Maximum drawdown fraction (0.0–1.0).
            timestamp:      UTC timestamp (defaults to utcnow).
        """
        ts = (timestamp or datetime.now(UTC)).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                    INSERT INTO account_snapshots
                        (timestamp, cash, equity, buying_power, realized_pnl,
                         unrealized_pnl, total_trades, winning_trades,
                         losing_trades, max_drawdown)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    ts, cash, equity, buying_power, realized_pnl,
                    unrealized_pnl, total_trades, winning_trades,
                    losing_trades, max_drawdown,
                ),
            )
            conn.commit()
            self._record_paper_activity("record_account_snapshot")

    def upsert_position(
        self,
        *,
        position_id: str,
        symbol: str,
        strategy: str = "",
        quantity: int,
        entry_price: float,
        current_price: float | None = None,
        unrealized_pnl: float = 0.0,
        realized_pnl: float = 0.0,
        status: str = "OPEN",
        opened_at: datetime | None = None,
        closed_at: datetime | None = None,
        delta: float | None = None,
        gamma: float | None = None,
        theta: float | None = None,
        vega: float | None = None,
        expiration: str | None = None,
        strike: float | None = None,
        option_type: str | None = None,
    ) -> None:
        """
        Insert or update a position record.

        Existing rows are updated in-place when *position_id* already exists;
        new rows are inserted otherwise.

        Args:
            position_id:   Unique identifier for the position (e.g. spread id).
            symbol:        Instrument ticker.
            strategy:      Strategy name.
            quantity:      Signed quantity (positive = long, negative = short).
            entry_price:   Average entry price.
            current_price: Latest mark price (None = not yet quoted).
            unrealized_pnl: Current unrealized P&L.
            realized_pnl:  Accumulated realized P&L on partial/full closes.
            status:        "OPEN" or "CLOSED".
            opened_at:     Position open timestamp (defaults to utcnow).
            closed_at:     Position close timestamp (None if still open).
            delta/gamma/theta/vega: Current Greeks.
            expiration:    Options expiry date string.
            strike:        Options strike.
            option_type:   "call" or "put".
        """
        opened_ts = (opened_at or datetime.now(UTC)).isoformat()
        closed_ts = closed_at.isoformat() if closed_at else None
        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                    INSERT INTO positions
                        (position_id, symbol, strategy, quantity, entry_price,
                         current_price, unrealized_pnl, realized_pnl, status,
                         opened_at, closed_at, delta, gamma, theta, vega,
                         expiration, strike, option_type, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(position_id) DO UPDATE SET
                        strategy       = excluded.strategy,
                        quantity       = excluded.quantity,
                        entry_price    = CASE
                            WHEN excluded.entry_price > 0 THEN excluded.entry_price
                            ELSE positions.entry_price
                        END,
                        opened_at      = CASE
                            WHEN upper(COALESCE(excluded.status, '')) = 'OPEN'
                                 AND upper(COALESCE(positions.status, '')) != 'OPEN'
                            THEN excluded.opened_at
                            WHEN upper(COALESCE(excluded.status, '')) = 'OPEN'
                                 AND upper(COALESCE(positions.status, '')) = 'OPEN'
                                 AND COALESCE(julianday(excluded.opened_at), 0.0)
                                     > COALESCE(julianday(positions.updated_at), 0.0)
                            THEN excluded.opened_at
                            ELSE positions.opened_at
                        END,
                        current_price  = excluded.current_price,
                        unrealized_pnl = excluded.unrealized_pnl,
                        realized_pnl   = excluded.realized_pnl,
                        status         = excluded.status,
                        closed_at      = excluded.closed_at,
                        delta          = excluded.delta,
                        gamma          = excluded.gamma,
                        theta          = excluded.theta,
                        vega           = excluded.vega,
                        expiration     = COALESCE(excluded.expiration, positions.expiration),
                        strike         = COALESCE(excluded.strike, positions.strike),
                        option_type    = COALESCE(excluded.option_type, positions.option_type),
                        updated_at     = excluded.updated_at
                    """,
                (
                    position_id, symbol, strategy, quantity, entry_price,
                    current_price, unrealized_pnl, realized_pnl, status,
                    opened_ts, closed_ts, delta, gamma, theta, vega,
                    expiration, strike, option_type, now,
                ),
            )
            conn.commit()
            self._record_paper_activity("upsert_position")

    def rekey_open_position(
        self,
        *,
        old_position_id: str,
        new_position_id: str,
        new_symbol: str,
        expiration: str | None = None,
        strike: float | None = None,
        option_type: str | None = None,
    ) -> bool:
        """Rename an OPEN position row after repairing an internal paper option symbol."""
        old_position_id = str(old_position_id or "").strip()
        new_position_id = str(new_position_id or "").strip()
        new_symbol = str(new_symbol or "").strip()
        if not old_position_id or not new_position_id or not new_symbol:
            return False

        updated_at = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as conn:
                existing = conn.execute(
                    "SELECT position_id FROM positions WHERE position_id = ? AND status = 'OPEN'",
                    (old_position_id,),
                ).fetchone()
                if existing is None:
                    return False

                conflict = conn.execute(
                    "SELECT position_id FROM positions WHERE position_id = ? AND position_id != ? LIMIT 1",
                    (new_position_id, old_position_id),
                ).fetchone()
                if conflict is not None:
                    raise RuntimeError(
                        f"Cannot rekey OPEN position to existing position_id {new_position_id}"
                    )

                conn.execute(
                    """
                    UPDATE positions
                    SET position_id = ?,
                        symbol = ?,
                        expiration = COALESCE(?, expiration),
                        strike = COALESCE(?, strike),
                        option_type = COALESCE(?, option_type),
                        updated_at = ?
                    WHERE position_id = ?
                      AND status = 'OPEN'
                    """,
                    (
                        new_position_id,
                        new_symbol,
                        expiration,
                        strike,
                        option_type,
                        updated_at,
                        old_position_id,
                    ),
                )
                conn.commit()
                self._record_paper_activity("rekey_open_position")

        return True

    def delete_open_position(self, *, position_id: str) -> bool:
        """Delete one OPEN position row by id."""
        normalized_position_id = str(position_id or "").strip()
        if not normalized_position_id:
            return False

        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM positions WHERE position_id = ? AND status = 'OPEN'",
                (normalized_position_id,),
            )
            conn.commit()
            deleted = int(getattr(cursor, "rowcount", 0) or 0) > 0
            if deleted:
                self._record_paper_activity("delete_open_position")

        return deleted

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_latest_snapshot(self) -> dict[str, Any] | None:
        """
        Return the most recent account snapshot, or None if none exists.

        Returns:
            Dict with all account_snapshots columns, or None.
        """
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM account_snapshots ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _normalize_reference_time(reference_time: datetime | None = None) -> datetime:
        """Return an aware UTC datetime for date-bucket calculations."""
        current = reference_time or datetime.now(UTC)
        if current.tzinfo is None:
            return current.replace(tzinfo=UTC)
        return current.astimezone(UTC)

    @classmethod
    def _eastern_day_window_utc(
        cls,
        reference_time: datetime | None = None,
    ) -> tuple[datetime, datetime]:
        """Return UTC bounds for the Eastern trading day containing reference_time."""
        current_utc = cls._normalize_reference_time(reference_time)
        current_et = current_utc.astimezone(_EASTERN_TIMEZONE)
        start_et = current_et.replace(hour=0, minute=0, second=0, microsecond=0)
        end_et = start_et + timedelta(days=1)
        return start_et.astimezone(UTC), end_et.astimezone(UTC)

    @classmethod
    def _eastern_period_start_utc(
        cls,
        period: str,
        reference_time: datetime | None = None,
    ) -> datetime:
        """Return the UTC timestamp for the Eastern start of the requested period."""
        current_utc = cls._normalize_reference_time(reference_time)
        current_et = current_utc.astimezone(_EASTERN_TIMEZONE)
        if period == "day":
            start_et = current_et.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_of_day = current_et.replace(hour=0, minute=0, second=0, microsecond=0)
            start_et = start_of_day - timedelta(days=start_of_day.weekday())
        elif period == "month":
            start_et = current_et.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "year":
            start_et = current_et.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported period for ET bucket: {period}")
        return start_et.astimezone(UTC)

    def get_trades_today(self) -> list[dict[str, Any]]:
        """
        Return all trades whose timestamp falls on today's ET date up to now.

        Returns:
            List of trade dicts ordered by ascending timestamp.
        """
        now_utc = self._normalize_reference_time()
        start_utc, _ = self._eastern_day_window_utc(now_utc)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trades "
                "WHERE datetime(timestamp) >= datetime(?) "
                "AND datetime(timestamp) <= datetime(?) "
                "ORDER BY datetime(timestamp), timestamp",
                (start_utc.isoformat(), now_utc.isoformat()),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_trades(self, limit: int = 3) -> list[dict[str, Any]]:
        """
        Return the most recent trades across all dates.

        Args:
            limit: Maximum number of rows to return (minimum 1).

        Returns:
            List of trade dicts ordered by descending timestamp.
        """
        safe_limit = max(1, int(limit))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def has_trade_history_for_symbol(self, symbol: str) -> bool:
        """Return True when at least one trade exists for the symbol."""
        normalized_symbol = str(symbol or "").strip()
        if not normalized_symbol:
            return False

        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM trades WHERE symbol = ? LIMIT 1",
                (normalized_symbol,),
            ).fetchone()
        return row is not None

    def get_latest_position_for_symbol(self, symbol: str) -> dict[str, Any] | None:
        """Return the most recently updated position row for the symbol."""
        normalized_symbol = str(symbol or "").strip()
        if not normalized_symbol:
            return None

        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM positions
                WHERE symbol = ?
                ORDER BY COALESCE(julianday(updated_at), 0.0) DESC,
                         COALESCE(julianday(opened_at), 0.0) DESC
                LIMIT 1
                """,
                (normalized_symbol,),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_open_positions(self) -> list[dict[str, Any]]:
        """
        Return all positions with status = 'OPEN', ordered by open time.

        Returns:
            List of position dicts.
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM positions WHERE status = 'OPEN' ORDER BY opened_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_active_paper_open_positions(self) -> list[dict[str, Any]]:
        """Return paper OPEN rows attributable to carryover or the active session.

        During an active paper session the dashboard should show two classes of
        persisted OPEN rows:
        - manifest-backed carryover positions from the prior graceful shutdown
        - positions opened during the current active session

        Raw pre-session leftovers that predate the current active-session marker
        are excluded so stale H05 rows do not reappear as ghost paper trades.
        Returned rows are copied and annotated with `_paper_open_origin` so the
        GUI can present current-session and carryover rows with truthful labels.
        """
        open_rows = self.get_open_positions()
        if not self._is_paper_db():
            return open_rows

        selected_rows: list[dict[str, Any]] = []
        seen_keys: set[str] = set()

        def _row_key(row: dict[str, Any]) -> str:
            position_id = str(row.get("position_id") or "").strip()
            if position_id:
                return position_id
            return (
                f"{row.get('symbol', '')}:{row.get('opened_at', '')}:{row.get('quantity', '')}"
            )

        def _append(row: dict[str, Any], *, origin: str) -> None:
            row_copy = dict(row)
            key = _row_key(row_copy)
            if key in seen_keys:
                return
            seen_keys.add(key)
            row_copy["_paper_open_origin"] = origin
            selected_rows.append(row_copy)

        for row in self.get_resume_eligible_open_positions():
            _append(row, origin="carryover")

        active_session = self._load_active_paper_session()
        cutoff = self._parse_iso_timestamp_utc(active_session.get("marked_at"))
        if cutoff is None:
            for row in open_rows:
                _append(row, origin="active_session")
            return selected_rows

        for row in open_rows:
            opened_at = self._parse_iso_timestamp_utc(row.get("opened_at"))
            updated_at = self._parse_iso_timestamp_utc(row.get("updated_at"))
            if (
                opened_at is None
                or opened_at >= cutoff
                or (updated_at is not None and updated_at >= cutoff)
            ):
                _append(row, origin="active_session")

        return selected_rows

    def get_resume_eligible_open_positions(self) -> list[dict[str, Any]]:
        """Return paper open positions that were confirmed active at last shutdown."""
        return self._get_manifest_backed_paper_open_positions(allow_expiring_today=False)

    def get_display_eligible_paper_open_positions(self) -> list[dict[str, Any]]:
        """Return manifest-backed paper OPEN rows that should stay visible in the UI.

        This preserves operator visibility for overnight positions that expire
        today without widening the stricter `get_resume_eligible_open_positions`
        gate used by automation.
        """
        return self._get_manifest_backed_paper_open_positions(allow_expiring_today=True)

    def get_pnl_summary(self) -> dict[str, float]:
        """
        Compute realized P&L totals grouped by TODAY / WEEK / MONTH / YEAR in ET.

        Returns:
            Dict with keys: today, week, month, year (all floats).
        """
        now_utc = self._normalize_reference_time()
        today_start = self._eastern_period_start_utc("day", now_utc)
        week_start = self._eastern_period_start_utc("week", now_utc)
        month_start = self._eastern_period_start_utc("month", now_utc)
        year_start = self._eastern_period_start_utc("year", now_utc)

        with self._lock, self._connect() as conn:
            def _sum(since: datetime) -> float:
                row = conn.execute(
                    "SELECT COALESCE(SUM(realized_pnl), 0.0) FROM trades "
                    "WHERE datetime(timestamp) >= datetime(?) "
                    "AND datetime(timestamp) <= datetime(?)",
                    (since.isoformat(), now_utc.isoformat()),
                ).fetchone()
                return float(row[0]) if row else 0.0

            return {
                "today": _sum(today_start),
                "week": _sum(week_start),
                "month": _sum(month_start),
                "year": _sum(year_start),
            }
