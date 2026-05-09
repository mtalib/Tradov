#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderH02_DatabaseManager.py
Group: H (Storage)
Purpose: Comprehensive SQLite database management for trading data
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 12:00:00

Description:
    This module provides comprehensive database management for the Spyder trading
    system using SQLite. It handles all database operations including trades,
    positions, market data, performance metrics, and system logs. Features
    thread-safe operations, automatic backups, data integrity checks, and
    optimized queries for high-frequency trading data retrieval.

Key Features:
    - Thread-safe SQLite operations with connection pooling
    - Automatic database backup and recovery
    - Optimized indexing for fast queries
    - Data compression for historical records
    - Transaction management with rollback support
    - Performance metrics tracking
    - Audit trail for all trading activities
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sqlite3
import json
import gzip
import math
import shutil
import threading
import queue
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from enum import Enum
import hashlib
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False
    logging.info("⚠️ Local imports not available - using standard logging")

# ==============================================================================
# CONSTANTS
# ==============================================================================
DATABASE_PATH = Path("data/spyder_trading.db")
BACKUP_PATH = Path("data/backups")
MAX_CONNECTIONS = 10
BACKUP_INTERVAL_HOURS = 6
VACUUM_INTERVAL_DAYS = 7
MAX_BACKUP_FILES = 30

# Table names
# Columns permitted in update_position() — prevents SQL column-name injection
_ALLOWED_POSITION_COLUMNS: frozenset[str] = frozenset({
    "symbol", "strategy", "quantity", "entry_price", "current_price",
    "unrealized_pnl", "realized_pnl", "status", "opened_at", "closed_at",
    "delta", "gamma", "theta", "vega",
})

TABLES = {
    "trades": "trades",
    "positions": "positions",
    "orders": "orders",
    "market_data": "market_data",
    "option_chains": "option_chains",
    "greeks": "greeks",
    "performance": "performance",
    "risk_metrics": "risk_metrics",
    "strategies": "strategies",
    "alerts": "alerts",
    "system_logs": "system_logs",
    "audit_trail": "audit_trail",
    "ml_predictions": "ml_predictions"
}

# ==============================================================================
# ENUMS
# ==============================================================================
class OrderStatus(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class PositionStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PARTIAL = "PARTIAL"
    EXPIRED = "EXPIRED"

class TradeType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    BUY_TO_OPEN = "BTO"
    SELL_TO_OPEN = "STO"
    BUY_TO_CLOSE = "BTC"
    SELL_TO_CLOSE = "STC"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class Trade:
    """Trade record structure"""
    trade_id: int | None = None
    timestamp: datetime = None
    symbol: str = ""
    strategy: str = ""
    trade_type: str = ""
    quantity: int = 0
    price: float = 0.0
    commission: float = 0.0
    pnl: float = 0.0
    order_id: str = ""
    execution_time_ms: int = 0
    slippage: float = 0.0
    notes: str = ""

@dataclass
class Position:
    """Position record structure"""
    position_id: int | None = None
    symbol: str = ""
    strategy: str = ""
    quantity: int = 0
    entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: str = PositionStatus.OPEN.value
    opened_at: datetime = None
    closed_at: datetime | None = None
    greeks: dict[str, float] = None

@dataclass
class MarketDataPoint:
    """Market data record"""
    timestamp: datetime
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    bid_size: int
    ask_size: int
    implied_volatility: float | None = None

# ==============================================================================
# DATABASE MANAGER
# ==============================================================================
class DatabaseManager:
    """
    Comprehensive database manager for Spyder trading system
    Handles all database operations with thread safety and optimization
    """

    def __init__(self, db_path: Path | None = None):
        """Initialize database manager"""
        self.db_path = db_path or DATABASE_PATH
        self.backup_path = BACKUP_PATH

        # Logging
        if LOCAL_IMPORTS:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger(__name__)

        # Thread safety
        self.lock = threading.RLock()
        self.connection_pool = queue.Queue(maxsize=MAX_CONNECTIONS)

        # Statistics
        self.query_count = 0
        self.write_count = 0
        self.last_backup = None
        self.last_vacuum = None

        # Initialize database
        self._setup_connection_pool()
        self._initialize_database()

        self.logger.info("✅ DatabaseManager initialized: %s", self.db_path)

    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================

    def _initialize_database(self):
        """Initialize database and create tables"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_path.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            self._create_tables(conn)
            self._create_indexes(conn)
            self._enable_wal_mode(conn)

    def _create_tables(self, conn: sqlite3.Connection):
        """Create all database tables"""
        cursor = conn.cursor()

        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                commission REAL DEFAULT 0,
                pnl REAL DEFAULT 0,
                order_id TEXT,
                execution_time_ms INTEGER,
                slippage REAL DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                position_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL,
                unrealized_pnl REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                status TEXT DEFAULT 'OPEN',
                opened_at TIMESTAMP NOT NULL,
                closed_at TIMESTAMP,
                delta REAL,
                gamma REAL,
                theta REAL,
                vega REAL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                order_type TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                limit_price REAL,
                stop_price REAL,
                status TEXT NOT NULL,
                filled_quantity INTEGER DEFAULT 0,
                avg_fill_price REAL,
                commission REAL DEFAULT 0,
                submitted_at TIMESTAMP,
                filled_at TIMESTAMP,
                cancelled_at TIMESTAMP,
                notes TEXT
            )
        """)

        # Market data table (partitioned by date for performance)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                bid REAL,
                ask REAL,
                last REAL,
                volume INTEGER,
                bid_size INTEGER,
                ask_size INTEGER,
                implied_volatility REAL,
                date TEXT GENERATED ALWAYS AS (date(timestamp)) STORED
            )
        """)

        # Option chains table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS option_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                underlying TEXT NOT NULL,
                expiration DATE NOT NULL,
                strike REAL NOT NULL,
                option_type TEXT NOT NULL,
                bid REAL,
                ask REAL,
                last REAL,
                volume INTEGER,
                open_interest INTEGER,
                implied_volatility REAL,
                delta REAL,
                gamma REAL,
                theta REAL,
                vega REAL
            )
        """)

        # Performance metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                strategy TEXT NOT NULL,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                gross_pnl REAL DEFAULT 0,
                net_pnl REAL DEFAULT 0,
                commission_paid REAL DEFAULT 0,
                max_drawdown REAL DEFAULT 0,
                sharpe_ratio REAL,
                win_rate REAL,
                avg_win REAL,
                avg_loss REAL,
                profit_factor REAL
            )
        """)

        # Risk metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                portfolio_delta REAL,
                portfolio_gamma REAL,
                portfolio_theta REAL,
                portfolio_vega REAL,
                var_95 REAL,
                var_99 REAL,
                max_loss_potential REAL,
                margin_used REAL,
                buying_power REAL,
                leverage REAL
            )
        """)

        # System logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level TEXT NOT NULL,
                module TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT
            )
        """)

        # Audit trail table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action TEXT NOT NULL,
                table_name TEXT,
                record_id TEXT,
                old_values TEXT,
                new_values TEXT,
                user TEXT DEFAULT 'system',
                ip_address TEXT,
                checksum TEXT
            )
        """)

        conn.commit()
        self.logger.info("✅ Database tables created")

    def _create_indexes(self, conn: sqlite3.Connection):
        """Create indexes for optimized queries"""
        cursor = conn.cursor()

        # Trades indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy)")

        # Positions indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)")

        # Orders indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_timestamp ON orders(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")

        # Market data indexes (compound for time-series queries)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp
            ON market_data(symbol, timestamp DESC)
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_data_date ON market_data(date)")

        # Option chains indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_option_chains_lookup
            ON option_chains(underlying, expiration, strike, option_type)
        """)

        conn.commit()
        self.logger.info("✅ Database indexes created")

    def _enable_wal_mode(self, conn: sqlite3.Connection):
        """Enable Write-Ahead Logging for better concurrency"""
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        conn.commit()

    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================

    def _setup_connection_pool(self):
        """Setup connection pool for thread safety"""
        for _ in range(MAX_CONNECTIONS):
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            self.connection_pool.put(conn)

    @contextmanager
    def _get_connection(self):
        """Get connection from pool with context manager"""
        conn = self.connection_pool.get()
        try:
            yield conn
        finally:
            self.connection_pool.put(conn)

    # ==========================================================================
    # TRADING DATA OPERATIONS
    # ==========================================================================

    @staticmethod
    def _validate_finite(value: float, name: str) -> None:
        """Reject NaN, Inf, and (for prices) negative values."""
        if not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be numeric, got {type(value).__name__}")
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"{name} must be finite, got {value}")

    def insert_trade(self, trade: Trade) -> int:
        """Insert trade record"""
        self._validate_finite(trade.price, "price")
        if trade.price < 0:
            raise ValueError(f"price must be non-negative, got {trade.price}")
        self._validate_finite(trade.commission, "commission")
        self._validate_finite(trade.pnl, "pnl")
        with self.lock, self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                    INSERT INTO trades (
                        timestamp, symbol, strategy, trade_type, quantity,
                        price, commission, pnl, order_id, execution_time_ms,
                        slippage, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                trade.timestamp, trade.symbol, trade.strategy,
                trade.trade_type, trade.quantity, trade.price,
                trade.commission, trade.pnl, trade.order_id,
                trade.execution_time_ms, trade.slippage, trade.notes
            ))

            trade_id = cursor.lastrowid
            self.write_count += 1

            # Audit trail
            self._audit_log(conn, "INSERT", "trades", trade_id, None, asdict(trade))

            return trade_id

    def get_trades(self,
                   symbol: str | None = None,
                   strategy: str | None = None,
                   start_date: datetime | None = None,
                   end_date: datetime | None = None,
                   limit: int = 1000) -> list[dict]:
        """Get trades with filters"""
        with self._get_connection() as conn:
            query = "SELECT * FROM trades WHERE 1=1"
            params = []

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            if strategy:
                query += " AND strategy = ?"
                params.append(strategy)
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.cursor()
            cursor.execute(query, params)

            self.query_count += 1
            return [dict(row) for row in cursor.fetchall()]

    def update_position(self, position_id: int, updates: dict[str, Any]):
        """Update position record"""
        with self.lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # Validate column names against allowlist — prevents column-name injection
            invalid_columns = set(updates.keys()) - _ALLOWED_POSITION_COLUMNS
            if invalid_columns:
                raise ValueError(
                    f"update_position: column(s) not permitted: {sorted(invalid_columns)}"
                )

            # Get old values for audit
            cursor.execute("SELECT * FROM positions WHERE position_id = ?", (position_id,))
            old_values = dict(cursor.fetchone()) if cursor.fetchone() else None

            # Build update query
            set_clause = ", ".join([f"{k} = ?" for k in updates])
            values = list(updates.values())
            values.append(position_id)

            cursor.execute(f"""
                    UPDATE positions
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE position_id = ?
                """, values)

            self.write_count += 1

            # Audit trail
            self._audit_log(conn, "UPDATE", "positions", position_id, old_values, updates)

    # ==========================================================================
    # MARKET DATA OPERATIONS
    # ==========================================================================

    def insert_market_data_batch(self, data_points: list[MarketDataPoint]):
        """Insert batch of market data efficiently"""
        for dp in data_points:
            for field in ("bid", "ask", "last"):
                self._validate_finite(getattr(dp, field), field)
        with self.lock, self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.executemany("""
                    INSERT INTO market_data (
                        timestamp, symbol, bid, ask, last, volume,
                        bid_size, ask_size, implied_volatility
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                (dp.timestamp, dp.symbol, dp.bid, dp.ask, dp.last,
                 dp.volume, dp.bid_size, dp.ask_size, dp.implied_volatility)
                for dp in data_points
            ])

            self.write_count += len(data_points)

    def get_latest_market_data(self, symbol: str) -> dict | None:
        """Get latest market data for symbol"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM market_data
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (symbol,))

            self.query_count += 1
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_market_data_range(self,
                             symbol: str,
                             start_time: datetime,
                             end_time: datetime,
                             interval_seconds: int = 60) -> pd.DataFrame:
        """Get market data for time range with optional resampling"""
        with self._get_connection() as conn:
            query = """
                SELECT * FROM market_data
                WHERE symbol = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """

            df = pd.read_sql_query(
                query,
                conn,
                params=(symbol, start_time, end_time),
                parse_dates=['timestamp']
            )

            self.query_count += 1

            # Resample if interval specified
            if interval_seconds > 0 and not df.empty:
                df.set_index('timestamp', inplace=True)
                df = df.resample(f'{interval_seconds}S').agg({
                    'bid': 'last',
                    'ask': 'last',
                    'last': 'last',
                    'volume': 'sum',
                    'bid_size': 'last',
                    'ask_size': 'last',
                    'implied_volatility': 'mean'
                }).dropna()

            return df

    # ==========================================================================
    # PERFORMANCE ANALYTICS
    # ==========================================================================

    def calculate_daily_performance(self, date: datetime, strategy: str | None = None):
        """Calculate and store daily performance metrics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Base query for trades
            query = """
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(pnl) as gross_pnl,
                    SUM(pnl - commission) as net_pnl,
                    SUM(commission) as commission_paid,
                    AVG(CASE WHEN pnl > 0 THEN pnl ELSE NULL END) as avg_win,
                    AVG(CASE WHEN pnl < 0 THEN pnl ELSE NULL END) as avg_loss
                FROM trades
                WHERE DATE(timestamp) = DATE(?)
            """

            params = [date]
            if strategy:
                query += " AND strategy = ?"
                params.append(strategy)

            cursor.execute(query, params)
            metrics = dict(cursor.fetchone())

            # Calculate additional metrics
            if metrics['total_trades'] > 0:
                metrics['win_rate'] = metrics['winning_trades'] / metrics['total_trades']

                if metrics['avg_loss'] and metrics['avg_loss'] != 0:
                    metrics['profit_factor'] = abs(metrics['avg_win'] / metrics['avg_loss'])
                else:
                    metrics['profit_factor'] = None

            # Store in performance table
            cursor.execute("""
                INSERT OR REPLACE INTO performance (
                    date, strategy, total_trades, winning_trades, losing_trades,
                    gross_pnl, net_pnl, commission_paid, win_rate, avg_win,
                    avg_loss, profit_factor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date, strategy or 'ALL',
                metrics['total_trades'], metrics['winning_trades'],
                metrics['losing_trades'], metrics['gross_pnl'],
                metrics['net_pnl'], metrics['commission_paid'],
                metrics.get('win_rate'), metrics['avg_win'],
                metrics['avg_loss'], metrics.get('profit_factor')
            ))

    def get_performance_summary(self,
                               start_date: datetime,
                               end_date: datetime,
                               strategy: str | None = None) -> pd.DataFrame:
        """Get performance summary for date range"""
        with self._get_connection() as conn:
            query = """
                SELECT * FROM performance
                WHERE date BETWEEN ? AND ?
            """
            params = [start_date, end_date]

            if strategy:
                query += " AND strategy = ?"
                params.append(strategy)

            df = pd.read_sql_query(query, conn, params=params, parse_dates=['date'])
            self.query_count += 1

            return df

    # ==========================================================================
    # BACKUP AND MAINTENANCE
    # ==========================================================================

    def backup_database(self) -> Path:
        """Create database backup"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_path / f"spyder_backup_{timestamp}.db"

        with self.lock:
            shutil.copy2(self.db_path, backup_file)

            # Compress backup
            with open(backup_file, 'rb') as f_in, gzip.open(f"{backup_file}.gz", 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

            backup_file.unlink()  # Remove uncompressed file

            self.last_backup = datetime.now(timezone.utc)
            self.logger.info("✅ Database backed up: %s.gz", backup_file)

            # Cleanup old backups
            self._cleanup_old_backups()

            return Path(f"{backup_file}.gz")

    def _cleanup_old_backups(self):
        """Remove old backup files"""
        backups = sorted(self.backup_path.glob("spyder_backup_*.gz"))

        if len(backups) > MAX_BACKUP_FILES:
            for old_backup in backups[:-MAX_BACKUP_FILES]:
                old_backup.unlink()
                self.logger.info("Removed old backup: %s", old_backup)

    def vacuum_database(self):
        """Vacuum database to reclaim space and optimize"""
        with self.lock, self._get_connection() as conn:
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
            self.last_vacuum = datetime.now(timezone.utc)
            self.logger.info("✅ Database vacuumed and analyzed")

    def get_database_stats(self) -> dict[str, Any]:
        """Get database statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {
                'database_size_mb': self.db_path.stat().st_size / (1024 * 1024),
                'query_count': self.query_count,
                'write_count': self.write_count,
                'last_backup': self.last_backup,
                'last_vacuum': self.last_vacuum,
                'tables': {}
            }

            # Get row counts for each table
            _allowed_tables = frozenset(TABLES.values())
            for table_name in TABLES.values():
                if table_name not in _allowed_tables:
                    continue
                try:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                    stats['tables'][table_name] = cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    stats['tables'][table_name] = 0

            return stats

    # ==========================================================================
    # AUDIT AND LOGGING
    # ==========================================================================

    @staticmethod
    def _json_default(obj: Any) -> str:
        """JSON serializer for objects not handled by default json."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def _audit_log(self, conn: sqlite3.Connection, action: str, table_name: str,
                   record_id: Any, old_values: dict | None, new_values: dict | None):
        """Create audit trail entry"""
        cursor = conn.cursor()

        # Create checksum for integrity
        checksum_data = f"{action}{table_name}{record_id}{old_values}{new_values}"
        checksum = hashlib.sha256(checksum_data.encode()).hexdigest()[:16]

        cursor.execute("""
            INSERT INTO audit_trail (
                action, table_name, record_id, old_values, new_values, checksum
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            action, table_name, str(record_id),
            json.dumps(old_values, default=self._json_default) if old_values else None,
            json.dumps(new_values, default=self._json_default) if new_values else None,
            checksum
        ))

    def log_system_event(self, level: str, module: str, message: str, details: dict | None = None):
        """Log system event to database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_logs (level, module, message, details)
                VALUES (?, ?, ?, ?)
            """, (level, module, message, json.dumps(details) if details else None))

    # ==========================================================================
    # CLEANUP
    # ==========================================================================

    def close(self):
        """Close all database connections"""
        while not self.connection_pool.empty():
            conn = self.connection_pool.get()
            conn.close()

        self.logger.info("DatabaseManager closed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_database_manager(db_path: Path | None = None) -> DatabaseManager:
    """Factory function to create database manager"""
    return DatabaseManager(db_path)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


    # Create database manager
    db_manager = create_database_manager()

    # Test trade insertion
    test_trade = Trade(
        timestamp=datetime.now(timezone.utc),
        symbol="SPY",
        strategy="IronCondor",
        trade_type="BTO",
        quantity=10,
        price=585.50,
        commission=1.30,
        pnl=250.00,
        order_id="TEST001",
        execution_time_ms=125,
        slippage=0.05,
        notes="Test trade"
    )

    trade_id = db_manager.insert_trade(test_trade)

    # Test market data
    test_data = MarketDataPoint(
        timestamp=datetime.now(timezone.utc),
        symbol="SPY",
        bid=585.45,
        ask=585.55,
        last=585.50,
        volume=1000000,
        bid_size=100,
        ask_size=150,
        implied_volatility=0.15
    )

    db_manager.insert_market_data_batch([test_data])

    # Get latest market data
    latest = db_manager.get_latest_market_data("SPY")

    # Calculate performance
    db_manager.calculate_daily_performance(datetime.now(timezone.utc))

    # Get database stats
    stats = db_manager.get_database_stats()
    for _table, _count in stats['tables'].items():
        pass

    # Backup database
    backup_path = db_manager.backup_database()

    # Close
    db_manager.close()
