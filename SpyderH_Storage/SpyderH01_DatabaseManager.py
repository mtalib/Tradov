#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderH01_DatabaseManager.py
Group: H (Data Storage)
Purpose: SQLite database management

Description:
    This module manages the SQLite database connections, schema creation,
    migrations, and provides a centralized interface for all database
    operations. It handles connection pooling, transaction management,
    and ensures data integrity across the trading system.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sqlite3
import os
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from contextlib import contextmanager
from pathlib import Path
import shutil
import hashlib
from dataclasses import dataclass
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderA_Core.SpyderA03_Configuration import get_config_manager
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler


# Level types for logging and risk management
class LevelType(Enum):
    """Level types used throughout the system."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ==============================================================================
# CONSTANTS
# ==============================================================================
# Database configuration
DEFAULT_DB_PATH = "data/spyder.db"
BACKUP_DIR = "data/backups"
WAL_MODE = True
BUSY_TIMEOUT = 30000  # 30 seconds
CACHE_SIZE = -64000  # 64MB cache

# Connection pool settings
MAX_CONNECTIONS = 10
CONNECTION_TIMEOUT = 30

# Schema version
CURRENT_SCHEMA_VERSION = 1

# ==============================================================================
# ENUMS
# ==============================================================================
class TransactionMode(Enum):
    """Database transaction modes"""
    DEFERRED = "DEFERRED"
    IMMEDIATE = "IMMEDIATE"
    EXCLUSIVE = "EXCLUSIVE"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class DatabaseInfo:
    """Database information"""
    path: str
    size_mb: float
    version: int
    created_at: datetime
    last_backup: Optional[datetime]
    table_count: int
    total_rows: int

# ==============================================================================
# SQL SCHEMA
# ==============================================================================
SCHEMA_SQL = """
-- Schema version table
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Trades table
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    strategy TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trade_type TEXT NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    commission REAL NOT NULL,
    slippage REAL NOT NULL,
    pnl REAL NOT NULL,
    pnl_percent REAL NOT NULL,
    mae REAL,
    mfe REAL,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Positions table
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id TEXT UNIQUE NOT NULL,
    strategy TEXT NOT NULL,
    symbol TEXT NOT NULL,
    position_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL,
    open_time TIMESTAMP NOT NULL,
    close_time TIMESTAMP,
    unrealized_pnl REAL,
    realized_pnl REAL,
    max_profit REAL,
    max_loss REAL,
    status TEXT NOT NULL,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE NOT NULL,
    position_id TEXT,
    strategy TEXT NOT NULL,
    symbol TEXT NOT NULL,
    order_type TEXT NOT NULL,
    action TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    limit_price REAL,
    stop_price REAL,
    filled_price REAL,
    filled_quantity INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    created_time TIMESTAMP NOT NULL,
    filled_time TIMESTAMP,
    cancelled_time TIMESTAMP,
    rejection_reason TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily performance table
CREATE TABLE IF NOT EXISTS daily_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    strategy TEXT,
    starting_equity REAL NOT NULL,
    ending_equity REAL NOT NULL,
    daily_pnl REAL NOT NULL,
    daily_return REAL NOT NULL,
    trades_count INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    gross_profit REAL DEFAULT 0,
    gross_loss REAL DEFAULT 0,
    commission_paid REAL DEFAULT 0,
    slippage_cost REAL DEFAULT 0,
    max_drawdown REAL,
    sharpe_ratio REAL,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, strategy)
);

-- Strategy metrics table
CREATE TABLE IF NOT EXISTS strategy_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT NOT NULL,
    metric_date DATE NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    metric_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(strategy, metric_date, metric_name)
);

-- Market data snapshots table
CREATE TABLE IF NOT EXISTS market_data_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    symbol TEXT NOT NULL,
    price REAL NOT NULL,
    bid REAL,
    ask REAL,
    volume INTEGER,
    volatility REAL,
    option_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System events table
CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TIMESTAMP NOT NULL,
    event_type TEXT NOT NULL,
    event_source TEXT NOT NULL,
    event_data TEXT,
    severity TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_trades_strategy_time ON trades(strategy, entry_time);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, entry_time);
CREATE INDEX IF NOT EXISTS idx_positions_strategy_status ON positions(strategy, status);
CREATE INDEX IF NOT EXISTS idx_orders_strategy_status ON orders(strategy, status);
CREATE INDEX IF NOT EXISTS idx_daily_performance_date ON daily_performance(date);
CREATE INDEX IF NOT EXISTS idx_strategy_metrics_lookup ON strategy_metrics(strategy, metric_date, metric_name);
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data_snapshots(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_system_events_time ON system_events(event_time);

-- Create triggers for updated_at
CREATE TRIGGER IF NOT EXISTS update_trades_timestamp 
AFTER UPDATE ON trades
BEGIN
    UPDATE trades SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_positions_timestamp 
AFTER UPDATE ON positions
BEGIN
    UPDATE positions SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_orders_timestamp 
AFTER UPDATE ON orders
BEGIN
    UPDATE orders SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
"""

# ==============================================================================
# DATABASE MANAGER CLASS
# ==============================================================================
class DatabaseManager:
    """
    Centralized SQLite database manager.
    
    Features:
    - Connection pooling
    - Transaction management
    - Schema versioning and migrations
    - Automatic backups
    - Performance optimization
    - Thread-safe operations
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize database manager"""
        if hasattr(self, '_initialized'):
            return
        
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = get_config_manager()
        
        # Database configuration
        self.db_path = self.config.get('database.path', DEFAULT_DB_PATH)
        self.backup_dir = self.config.get('database.backup_dir', BACKUP_DIR)
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Connection pool
        self._connections: Dict[int, sqlite3.Connection] = {}
        self._connection_lock = threading.Lock()
        
        # Initialize database
        self._initialize_database()
        
        self._initialized = True
        self.logger.info(f"DatabaseManager initialized with database at {self.db_path}")
    
    # ==========================================================================
    # PUBLIC METHODS - CONNECTION MANAGEMENT
    # ==========================================================================
    @contextmanager
    def get_connection(self):
        """
        Get a database connection from the pool.
        
        Yields:
            sqlite3.Connection: Database connection
        """
        thread_id = threading.get_ident()
        
        try:
            # Get or create connection for this thread
            with self._connection_lock:
                if thread_id not in self._connections:
                    self._connections[thread_id] = self._create_connection()
                
                conn = self._connections[thread_id]
            
            yield conn
            
        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            raise
    
    @contextmanager
    def transaction(self, mode: TransactionMode = TransactionMode.DEFERRED):
        """
        Execute operations in a transaction.
        
        Args:
            mode: Transaction mode
            
        Yields:
            sqlite3.Connection: Database connection
        """
        with self.get_connection() as conn:
            try:
                conn.execute(f"BEGIN {mode.value}")
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Transaction failed: {str(e)}")
                raise
    
    # ==========================================================================
    # PUBLIC METHODS - QUERY EXECUTION
    # ==========================================================================
    def execute(self, query: str, params: Optional[Tuple] = None) -> sqlite3.Cursor:
        """
        Execute a single query.
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Cursor with results
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
    
    def executemany(self, query: str, params_list: List[Tuple]) -> int:
        """
        Execute multiple queries.
        
        Args:
            query: SQL query
            params_list: List of parameter tuples
            
        Returns:
            Number of affected rows
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            return cursor.rowcount
    
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[sqlite3.Row]:
        """
        Fetch a single row.
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Row or None
        """
        cursor = self.execute(query, params)
        return cursor.fetchone()
    
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[sqlite3.Row]:
        """
        Fetch all rows.
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            List of rows
        """
        cursor = self.execute(query, params)
        return cursor.fetchall()
    
    def fetch_dataframe(self, query: str, params: Optional[Tuple] = None) -> pd.DataFrame:
        """
        Fetch results as pandas DataFrame.
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            DataFrame with results
        """
        with self.get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)
    
    # ==========================================================================
    # PUBLIC METHODS - SCHEMA MANAGEMENT
    # ==========================================================================
    def get_schema_version(self) -> int:
        """Get current schema version"""
        try:
            result = self.fetch_one(
                "SELECT MAX(version) as version FROM schema_version"
            )
            return result['version'] if result and result['version'] else 0
        except:
            return 0
    
    def apply_migration(self, version: int, sql: str, description: str) -> bool:
        """
        Apply a schema migration.
        
        Args:
            version: Migration version
            sql: Migration SQL
            description: Migration description
            
        Returns:
            Success status
        """
        try:
            current_version = self.get_schema_version()
            
            if version <= current_version:
                self.logger.info(f"Migration {version} already applied")
                return True
            
            with self.transaction(TransactionMode.EXCLUSIVE) as conn:
                # Apply migration
                conn.executescript(sql)
                
                # Record migration
                conn.execute(
                    "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                    (version, description)
                )
            
            self.logger.info(f"Applied migration {version}: {description}")
            return True
            
        except Exception as e:
            self.logger.error(f"Migration {version} failed: {str(e)}")
            return False
    
    # ==========================================================================
    # PUBLIC METHODS - BACKUP AND MAINTENANCE
    # ==========================================================================
    def backup_database(self, tag: Optional[str] = None) -> str:
        """
        Create a database backup.
        
        Args:
            tag: Optional tag for the backup
            
        Returns:
            Backup file path
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"spyder_backup_{timestamp}"
        
        if tag:
            backup_name += f"_{tag}"
        
        backup_path = os.path.join(self.backup_dir, f"{backup_name}.db")
        
        try:
            with self.get_connection() as conn:
                # Use SQLite backup API
                backup_conn = sqlite3.connect(backup_path)
                conn.backup(backup_conn)
                backup_conn.close()
            
            # Compress the backup
            shutil.make_archive(backup_path, 'gzip', self.backup_dir, f"{backup_name}.db")
            os.remove(backup_path)
            
            compressed_path = f"{backup_path}.gz"
            self.logger.info(f"Database backed up to {compressed_path}")
            
            # Clean old backups
            self._clean_old_backups()
            
            return compressed_path
            
        except Exception as e:
            self.logger.error(f"Backup failed: {str(e)}")
            raise
    
    def vacuum_database(self) -> None:
        """Vacuum database to reclaim space"""
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
            self.logger.info("Database vacuumed successfully")
        except Exception as e:
            self.logger.error(f"Vacuum failed: {str(e)}")
    
    def analyze_database(self) -> None:
        """Update database statistics for query optimization"""
        try:
            with self.get_connection() as conn:
                conn.execute("ANALYZE")
            self.logger.info("Database analyzed successfully")
        except Exception as e:
            self.logger.error(f"Analyze failed: {str(e)}")
    
    def get_database_info(self) -> DatabaseInfo:
        """Get database information"""
        # Get file size
        size_bytes = os.path.getsize(self.db_path)
        size_mb = size_bytes / 1024 / 1024
        
        # Get creation time
        created_at = datetime.fromtimestamp(os.path.getctime(self.db_path))
        
        # Get schema version
        version = self.get_schema_version()
        
        # Count tables
        tables = self.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        table_count = len(tables)
        
        # Count total rows
        total_rows = 0
        for table in tables:
            count = self.fetch_one(f"SELECT COUNT(*) as count FROM {table['name']}")
            total_rows += count['count'] if count else 0
        
        # Get last backup
        last_backup = self._get_last_backup_time()
        
        return DatabaseInfo(
            path=self.db_path,
            size_mb=size_mb,
            version=version,
            created_at=created_at,
            last_backup=last_backup,
            table_count=table_count,
            total_rows=total_rows
        )
    
    # ==========================================================================
    # PUBLIC METHODS - DATA INTEGRITY
    # ==========================================================================
    def check_integrity(self) -> Tuple[bool, List[str]]:
        """
        Check database integrity.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        try:
            # Run integrity check
            result = self.fetch_all("PRAGMA integrity_check")
            
            for row in result:
                if row[0] != 'ok':
                    errors.append(row[0])
            
            # Check foreign keys
            fk_result = self.fetch_all("PRAGMA foreign_key_check")
            for row in fk_result:
                errors.append(f"Foreign key violation in table {row[0]}")
            
            is_valid = len(errors) == 0
            
            if is_valid:
                self.logger.info("Database integrity check passed")
            else:
                self.logger.error(f"Database integrity check failed: {errors}")
            
            return is_valid, errors
            
        except Exception as e:
            self.logger.error(f"Integrity check error: {str(e)}")
            return False, [str(e)]
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _initialize_database(self) -> None:
        """Initialize database with schema"""
        try:
            with self.transaction(TransactionMode.EXCLUSIVE) as conn:
                # Enable WAL mode for better concurrency
                if WAL_MODE:
                    conn.execute("PRAGMA journal_mode=WAL")
                
                # Set performance pragmas
                conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT}")
                conn.execute(f"PRAGMA cache_size={CACHE_SIZE}")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA temp_store=MEMORY")
                
                # Create schema
                conn.executescript(SCHEMA_SQL)
                
                # Record initial schema version
                if self.get_schema_version() == 0:
                    conn.execute(
                        "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                        (CURRENT_SCHEMA_VERSION, "Initial schema")
                    )
            
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Database initialization failed: {str(e)}")
            raise
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=CONNECTION_TIMEOUT,
            isolation_level=None,  # Autocommit mode
            check_same_thread=False
        )
        
        # Enable row factory for dict-like access
        conn.row_factory = sqlite3.Row
        
        # Set pragmas for this connection
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT}")
        conn.execute("PRAGMA foreign_keys=ON")
        
        return conn
    
    def _clean_old_backups(self) -> None:
        """Clean old backup files"""
        retention_days = self.config.get('database.backup_retention_days', 30)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        for filename in os.listdir(self.backup_dir):
            if filename.startswith('spyder_backup_') and filename.endswith('.gz'):
                filepath = os.path.join(self.backup_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                if file_time < cutoff_date:
                    os.remove(filepath)
                    self.logger.info(f"Removed old backup: {filename}")
    
    def _get_last_backup_time(self) -> Optional[datetime]:
        """Get timestamp of last backup"""
        backup_files = [
            f for f in os.listdir(self.backup_dir)
            if f.startswith('spyder_backup_') and f.endswith('.gz')
        ]
        
        if not backup_files:
            return None
        
        latest_backup = max(backup_files)
        filepath = os.path.join(self.backup_dir, latest_backup)
        return datetime.fromtimestamp(os.path.getmtime(filepath))
    
    def close_all_connections(self) -> None:
        """Close all database connections"""
        with self._connection_lock:
            for conn in self._connections.values():
                conn.close()
            self._connections.clear()
        
        self.logger.info("All database connections closed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_database_manager: Optional[DatabaseManager] = None

def get_database_manager() -> DatabaseManager:
    """
    Get singleton instance of database manager.
    
    Returns:
        DatabaseManager instance
    """
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager()
    return _database_manager

# ==============================================================================
# MIGRATION UTILITIES
# ==============================================================================
def apply_all_migrations() -> None:
    """Apply all pending database migrations"""
    db = get_database_manager()
    
    # Define migrations here
    migrations = [
        # Example migration format:
        # (version, sql, description)
    ]
    
    for version, sql, description in migrations:
        db.apply_migration(version, sql, description)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test database manager
    db = get_database_manager()
    
    # Get database info
    info = db.get_database_info()
    print(f"Database: {info.path}")
    print(f"Size: {info.size_mb:.2f} MB")
    print(f"Version: {info.version}")
    print(f"Tables: {info.table_count}")
    print(f"Total rows: {info.total_rows}")
    
    # Check integrity
    is_valid, errors = db.check_integrity()
    print(f"\nIntegrity check: {'PASSED' if is_valid else 'FAILED'}")
    if errors:
        for error in errors:
            print(f"  - {error}")
    
    # Test backup
    backup_path = db.backup_database("test")
    print(f"\nBackup created: {backup_path}")
    
    # Close connections
    db.close_all_connections()
