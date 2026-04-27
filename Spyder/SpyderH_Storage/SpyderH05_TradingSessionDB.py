#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
    • get_trades_today()        — all trades from today (UTC)
    • get_open_positions()      — all open positions
    • Thread-safe via RLock + per-call connections (WAL mode)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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
        self.logger.info("TradingSessionDB ready: %s", db_path)

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

    def _init_schema(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self._lock:
            with self._connect() as conn:
                conn.executescript(_SCHEMA_SQL)
                for idx_sql in _INDEXES_SQL:
                    conn.execute(idx_sql)
                conn.commit()

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
        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        with self._lock:
            with self._connect() as conn:
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
        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        with self._lock:
            with self._connect() as conn:
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
        opened_ts = (opened_at or datetime.now(timezone.utc)).isoformat()
        closed_ts = closed_at.isoformat() if closed_at else None
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO positions
                        (position_id, symbol, strategy, quantity, entry_price,
                         current_price, unrealized_pnl, realized_pnl, status,
                         opened_at, closed_at, delta, gamma, theta, vega,
                         expiration, strike, option_type, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(position_id) DO UPDATE SET
                        current_price  = excluded.current_price,
                        unrealized_pnl = excluded.unrealized_pnl,
                        realized_pnl   = excluded.realized_pnl,
                        status         = excluded.status,
                        closed_at      = excluded.closed_at,
                        delta          = excluded.delta,
                        gamma          = excluded.gamma,
                        theta          = excluded.theta,
                        vega           = excluded.vega,
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

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_latest_snapshot(self) -> dict[str, Any] | None:
        """
        Return the most recent account snapshot, or None if none exists.

        Returns:
            Dict with all account_snapshots columns, or None.
        """
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM account_snapshots ORDER BY timestamp DESC LIMIT 1"
                ).fetchone()
        return dict(row) if row else None

    def get_trades_today(self) -> list[dict[str, Any]]:
        """
        Return all trades whose timestamp falls on today (UTC date).

        Returns:
            List of trade dicts ordered by ascending timestamp.
        """
        today = datetime.now(timezone.utc).date().isoformat()
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE date(timestamp) = ? ORDER BY timestamp",
                    (today,),
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
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?",
                    (safe_limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_open_positions(self) -> list[dict[str, Any]]:
        """
        Return all positions with status = 'OPEN', ordered by open time.

        Returns:
            List of position dicts.
        """
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM positions WHERE status = 'OPEN' ORDER BY opened_at"
                ).fetchall()
        return [dict(r) for r in rows]

    def get_pnl_summary(self) -> dict[str, float]:
        """
        Compute realized P&L totals grouped by TODAY / WEEK / MONTH / YEAR.

        Returns:
            Dict with keys: today, week, month, year (all floats).
        """
        now = datetime.now(timezone.utc)
        today_str = now.date().isoformat()
        week_start = (now.date() - timedelta(days=now.weekday())).isoformat()
        month_start = now.date().replace(day=1).isoformat()
        year_start = now.date().replace(month=1, day=1).isoformat()

        with self._lock:
            with self._connect() as conn:
                def _sum(since: str) -> float:
                    row = conn.execute(
                        "SELECT COALESCE(SUM(realized_pnl), 0.0) FROM trades "
                        "WHERE date(timestamp) >= ?",
                        (since,),
                    ).fetchone()
                    return float(row[0]) if row else 0.0

                return {
                    "today": _sum(today_str),
                    "week": _sum(week_start),
                    "month": _sum(month_start),
                    "year": _sum(year_start),
                }
