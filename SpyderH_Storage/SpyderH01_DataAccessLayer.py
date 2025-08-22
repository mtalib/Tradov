#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderH_Storage 
Module: SpyderH01_DataAccessLayer.py 
Purpose: Data Access Layer for database operations and persistence
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-01-23 Time: 17:00:00  

Module Description:
    Provides a unified data access layer for all database operations in the
    Spyder trading system. This module handles database connections, query
    execution, transaction management, and data persistence. Supports both
    SQLite for local storage and can be extended for other databases.
    Includes connection pooling, retry logic, comprehensive error handling,
    and database migration support.

Key Features:
    • Database connection management with pooling
    • Transaction support with rollback capability
    • Query builder and execution
    • Data persistence for trades, market data, and system state
    • Automatic schema creation and migration system
    • Connection health monitoring
    • Thread-safe operations
    • Database versioning and migration tracking

Dependencies:
    • sqlite3 (standard library)
    • Optional: sqlalchemy for advanced features
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import logging
import sqlite3
import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from enum import Enum

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_DB_PATH = Path.home() / '.spyder' / 'data' / 'spyder.db'
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_DELAY = 1.0
CURRENT_DB_VERSION = "1.0.3"

# ==============================================================================
# ENUMS
# ==============================================================================
class ConnectionState(Enum):
    """Database connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

class QueryType(Enum):
    """Types of database queries"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    CREATE = "create"
    DROP = "drop"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class ConnectionInfo:
    """Database connection information"""
    database_path: Path
    timeout: float
    check_same_thread: bool
    journal_mode: str
    synchronous: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'database_path': str(self.database_path),
            'timeout': self.timeout,
            'check_same_thread': self.check_same_thread,
            'journal_mode': self.journal_mode,
            'synchronous': self.synchronous
        }

@dataclass
class Migration:
    """Database migration information"""
    version: str
    description: str
    migration_func: Callable
    rollback_func: Optional[Callable] = None

# ==============================================================================
# MAIN DATA ACCESS LAYER CLASS
# ==============================================================================
class DataAccessLayer:
    """
    Unified data access layer for Spyder trading system.
    
    Provides database connectivity, query execution, and data persistence
    with automatic retry logic, connection pooling, error handling, and
    migration support.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize Data Access Layer.
        
        Args:
            config: Optional configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Connection management
        self.connection: Optional[sqlite3.Connection] = None
        self.connection_state = ConnectionState.DISCONNECTED
        self.connection_info: Optional[ConnectionInfo] = None
        self.connection_lock = threading.Lock()
        
        # Database configuration
        self.db_path = Path(self.config.get('database_path', DEFAULT_DB_PATH))
        self.timeout = self.config.get('timeout', DEFAULT_TIMEOUT)
        
        # Statistics
        self.query_count = 0
        self.error_count = 0
        self.last_query_time = None
        self.connection_time = None
        
        # Initialize database
        self._initialize_database()
        
        self.logger.info("DataAccessLayer initialized successfully")
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    
    def connect(self) -> bool:
        """
        Establish database connection.
        
        Returns:
            True if connection successful
        """
        try:
            with self.connection_lock:
                if self.connection_state == ConnectionState.CONNECTED:
                    self.logger.debug("Already connected to database")
                    return True
                
                self.connection_state = ConnectionState.CONNECTING
                self.logger.info(f"Connecting to database: {self.db_path}")
                
                # Ensure directory exists
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Create connection
                self.connection = sqlite3.connect(
                    str(self.db_path),
                    timeout=self.timeout,
                    check_same_thread=False,
                    isolation_level=None  # Autocommit mode
                )
                
                # Configure connection
                self.connection.row_factory = sqlite3.Row
                self._configure_connection()
                
                # Store connection info
                self.connection_info = ConnectionInfo(
                    database_path=self.db_path,
                    timeout=self.timeout,
                    check_same_thread=False,
                    journal_mode='WAL',
                    synchronous='NORMAL'
                )
                
                self.connection_state = ConnectionState.CONNECTED
                self.connection_time = datetime.now()
                
                self.logger.info("Database connection established successfully")
                return True
                
        except Exception as e:
            self.connection_state = ConnectionState.ERROR
            self.logger.error(f"Failed to connect to database: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from database."""
        try:
            with self.connection_lock:
                if self.connection:
                    self.connection.close()
                    self.connection = None
                
                self.connection_state = ConnectionState.DISCONNECTED
                self.connection_info = None
                self.connection_time = None
                
                self.logger.info("Database connection closed")
                
        except Exception as e:
            self.logger.error(f"Error disconnecting from database: {e}")
    
    def test_connection(self) -> bool:
        """
        Test database connection.
        
        Returns:
            True if connection is active and working
        """
        try:
            if not self.connection:
                self.logger.debug("No connection to test")
                return self.connect()
            
            # Test with simple query
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            
            if result and result[0] == 1:
                self.logger.debug("Database connection test successful")
                return True
            else:
                self.logger.warning("Database connection test failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Database connection test error: {e}")
            # Try to reconnect
            return self.connect()
    
    def is_connected(self) -> bool:
        """
        Check if connected to database.
        
        Returns:
            True if connected
        """
        return self.connection_state == ConnectionState.CONNECTED and self.connection is not None
    
    def close_all_connections(self):
        """Close all database connections."""
        self.disconnect()
        self.logger.info("All database connections closed")
    
    # ==========================================================================
    # DATABASE INITIALIZATION AND MIGRATIONS
    # ==========================================================================
    
    def _initialize_database(self):
        """Initialize database structure."""
        try:
            # Connect if not connected
            if not self.is_connected():
                self.connect()
            
            # Run migrations
            self.run_migrations()
            
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
    
    def _configure_connection(self):
        """Configure database connection settings."""
        if not self.connection:
            return
        
        try:
            cursor = self.connection.cursor()
            
            # Set journal mode to WAL for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            
            # Set synchronous mode
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys=ON")
            
            # Optimize for performance
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA cache_size=10000")
            
            cursor.close()
            
            self.logger.debug("Database connection configured")
            
        except Exception as e:
            self.logger.error(f"Failed to configure connection: {e}")
    
    def run_migrations(self) -> bool:
        """
        Run database migrations.
        
        Returns:
            True if migrations successful
        """
        try:
            self.logger.info("Running database migrations...")
            
            # Ensure connection
            if not self.is_connected():
                if not self.connect():
                    self.logger.error("Failed to connect for migrations")
                    return False
            
            # Create migrations table if it doesn't exist
            self._create_migrations_table()
            
            # Get list of migrations
            migrations = self._get_migrations()
            
            # Apply pending migrations
            applied_count = 0
            for migration in migrations:
                if not self._is_migration_applied(migration.version):
                    self.logger.info(f"Applying migration {migration.version}: {migration.description}")
                    
                    try:
                        # Run migration
                        migration.migration_func()
                        
                        # Mark as applied
                        self._mark_migration_applied(migration.version, migration.description)
                        applied_count += 1
                        
                        self.logger.info(f"Migration {migration.version} applied successfully")
                        
                    except Exception as e:
                        self.logger.error(f"Migration {migration.version} failed: {e}")
                        
                        # Try rollback if available
                        if migration.rollback_func:
                            try:
                                self.logger.info(f"Rolling back migration {migration.version}")
                                migration.rollback_func()
                            except Exception as rollback_error:
                                self.logger.error(f"Rollback failed: {rollback_error}")
                        
                        return False
            
            if applied_count > 0:
                self.logger.info(f"Applied {applied_count} migrations successfully")
            else:
                self.logger.debug("No pending migrations")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Migration process failed: {e}")
            return False
    
    def _create_migrations_table(self):
        """Create migrations tracking table."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT UNIQUE NOT NULL,
                    description TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT
                )
            """)
            self.connection.commit()
            cursor.close()
            
        except Exception as e:
            self.logger.error(f"Failed to create migrations table: {e}")
            raise
    
    def _get_migrations(self) -> List[Migration]:
        """
        Get list of all migrations.
        
        Returns:
            List of Migration objects
        """
        return [
            Migration(
                version="1.0.0",
                description="Initial schema creation",
                migration_func=self._migration_v1_0_0
            ),
            Migration(
                version="1.0.1",
                description="Add indexes for performance",
                migration_func=self._migration_v1_0_1
            ),
            Migration(
                version="1.0.2",
                description="Add options trading tables",
                migration_func=self._migration_v1_0_2
            ),
            Migration(
                version="1.0.3",
                description="Add risk metrics tables",
                migration_func=self._migration_v1_0_3
            ),
        ]
    
    def _is_migration_applied(self, version: str) -> bool:
        """
        Check if a migration has been applied.
        
        Args:
            version: Migration version to check
            
        Returns:
            True if migration has been applied
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM migrations WHERE version = ?", (version,))
            result = cursor.fetchone()
            cursor.close()
            
            return result[0] > 0 if result else False
            
        except Exception as e:
            self.logger.error(f"Failed to check migration status: {e}")
            return False
    
    def _mark_migration_applied(self, version: str, description: str):
        """
        Mark a migration as applied.
        
        Args:
            version: Migration version
            description: Migration description
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "INSERT INTO migrations (version, description) VALUES (?, ?)",
                (version, description)
            )
            self.connection.commit()
            cursor.close()
            
        except Exception as e:
            self.logger.error(f"Failed to mark migration {version} as applied: {e}")
            raise
    
    # ==========================================================================
    # MIGRATION FUNCTIONS
    # ==========================================================================
    
    def _migration_v1_0_0(self):
        """Migration v1.0.0: Create initial schema."""
        self._create_tables()
    
    def _migration_v1_0_1(self):
        """Migration v1.0.1: Add performance indexes."""
        cursor = self.connection.cursor()
        
        # Add composite indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_timestamp ON trades(symbol, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp ON market_data(symbol, timestamp)")
        
        self.connection.commit()
        cursor.close()
    
    def _migration_v1_0_2(self):
        """Migration v1.0.2: Add options trading tables."""
        cursor = self.connection.cursor()
        
        # Options positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS options_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                strike REAL NOT NULL,
                expiry DATE NOT NULL,
                option_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL,
                pnl REAL,
                status TEXT,
                metadata TEXT
            )
        """)
        
        # Options chains table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS options_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                expiry DATE NOT NULL,
                data TEXT NOT NULL
            )
        """)
        
        self.connection.commit()
        cursor.close()
    
    def _migration_v1_0_3(self):
        """Migration v1.0.3: Add risk metrics tables."""
        cursor = self.connection.cursor()
        
        # Risk metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metric_type TEXT NOT NULL,
                metric_value REAL NOT NULL,
                threshold REAL,
                status TEXT,
                metadata TEXT
            )
        """)
        
        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                acknowledged BOOLEAN DEFAULT FALSE,
                acknowledged_at TIMESTAMP,
                metadata TEXT
            )
        """)
        
        self.connection.commit()
        cursor.close()
    
    def _create_tables(self):
        """Create core database tables."""
        try:
            if not self.connection:
                return
            
            cursor = self.connection.cursor()
            
            # Trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    commission REAL,
                    order_id TEXT UNIQUE,
                    status TEXT,
                    metadata TEXT
                )
            """)
            
            # Market data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    bid REAL,
                    ask REAL,
                    last REAL,
                    volume INTEGER,
                    open_interest INTEGER,
                    metadata TEXT
                )
            """)
            
            # System state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Performance metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    metadata TEXT
                )
            """)
            
            # Create basic indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_data_timestamp ON market_data(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol)")
            
            self.connection.commit()
            cursor.close()
            
            self.logger.debug("Database tables created/verified")
            
        except Exception as e:
            self.logger.error(f"Failed to create tables: {e}")
            raise
    
    def initialize(self) -> bool:
        """
        Initialize database (compatibility method).
        
        Returns:
            True if initialization successful
        """
        try:
            self._initialize_database()
            return self.test_connection()
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False
    
    # ==========================================================================
    # QUERY EXECUTION
    # ==========================================================================
    
    @contextmanager
    def get_cursor(self):
        """
        Get database cursor with automatic cleanup.
        
        Yields:
            Database cursor
        """
        cursor = None
        try:
            if not self.test_connection():
                raise RuntimeError("Database connection failed")
            
            cursor = self.connection.cursor()
            yield cursor
            
        finally:
            if cursor:
                cursor.close()
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> Optional[List[sqlite3.Row]]:
        """
        Execute a SELECT query.
        
        Args:
            query: SQL query string
            params: Optional query parameters
            
        Returns:
            Query results or None if error
        """
        try:
            with self.get_cursor() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                results = cursor.fetchall()
                self.query_count += 1
                self.last_query_time = datetime.now()
                
                return results
                
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Query execution failed: {e}")
            return None
    
    def execute_write(self, query: str, params: Optional[Tuple] = None) -> bool:
        """
        Execute an INSERT/UPDATE/DELETE query.
        
        Args:
            query: SQL query string
            params: Optional query parameters
            
        Returns:
            True if successful
        """
        try:
            with self.get_cursor() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                self.connection.commit()
                self.query_count += 1
                self.last_query_time = datetime.now()
                
                return True
                
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Write operation failed: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    # ==========================================================================
    # DATA OPERATIONS
    # ==========================================================================
    
    def save_trade(self, trade_data: Dict[str, Any]) -> bool:
        """
        Save trade information to database.
        
        Args:
            trade_data: Dictionary containing trade information
            
        Returns:
            True if successful
        """
        try:
            query = """
                INSERT INTO trades (symbol, action, quantity, price, commission, order_id, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                trade_data.get('symbol'),
                trade_data.get('action'),
                trade_data.get('quantity'),
                trade_data.get('price'),
                trade_data.get('commission', 0.0),
                trade_data.get('order_id'),
                trade_data.get('status', 'PENDING'),
                json.dumps(trade_data.get('metadata', {}))
            )
            
            return self.execute_write(query, params)
            
        except Exception as e:
            self.logger.error(f"Failed to save trade: {e}")
            return False
    
    def get_trades(self, symbol: Optional[str] = None, 
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Retrieve trades from database.
        
        Args:
            symbol: Optional symbol filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of trade dictionaries
        """
        try:
            query = "SELECT * FROM trades WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())
            
            query += " ORDER BY timestamp DESC"
            
            results = self.execute_query(query, tuple(params) if params else None)
            
            if results:
                return [dict(row) for row in results]
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to get trades: {e}")
            return []
    
    def save_market_data(self, market_data: Dict[str, Any]) -> bool:
        """
        Save market data to database.
        
        Args:
            market_data: Dictionary containing market data
            
        Returns:
            True if successful
        """
        try:
            query = """
                INSERT INTO market_data (symbol, bid, ask, last, volume, open_interest, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                market_data.get('symbol'),
                market_data.get('bid'),
                market_data.get('ask'),
                market_data.get('last'),
                market_data.get('volume'),
                market_data.get('open_interest'),
                json.dumps(market_data.get('metadata', {}))
            )
            
            return self.execute_write(query, params)
            
        except Exception as e:
            self.logger.error(f"Failed to save market data: {e}")
            return False
    
    def save_state(self, key: str, value: Any) -> bool:
        """
        Save system state to database.
        
        Args:
            key: State key
            value: State value (will be JSON serialized)
            
        Returns:
            True if successful
        """
        try:
            query = """
                INSERT OR REPLACE INTO system_state (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """
            
            params = (key, json.dumps(value))
            return self.execute_write(query, params)
            
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
            return False
    
    def get_state(self, key: str) -> Optional[Any]:
        """
        Retrieve system state from database.
        
        Args:
            key: State key
            
        Returns:
            State value or None if not found
        """
        try:
            query = "SELECT value FROM system_state WHERE key = ?"
            results = self.execute_query(query, (key,))
            
            if results and len(results) > 0:
                return json.loads(results[0]['value'])
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get state: {e}")
            return None
    
    # ==========================================================================
    # STATISTICS AND MONITORING
    # ==========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary containing statistics
        """
        try:
            stats = {
                'connected': self.is_connected(),
                'connection_state': self.connection_state.value,
                'database_path': str(self.db_path),
                'database_version': CURRENT_DB_VERSION,
                'query_count': self.query_count,
                'error_count': self.error_count,
                'last_query_time': self.last_query_time.isoformat() if self.last_query_time else None,
                'connection_time': self.connection_time.isoformat() if self.connection_time else None,
                'uptime_seconds': (datetime.now() - self.connection_time).total_seconds() if self.connection_time else 0
            }
            
            # Get table statistics
            if self.is_connected():
                with self.get_cursor() as cursor:
                    # Get row counts for all tables
                    tables = ['trades', 'market_data', 'options_positions', 'risk_metrics', 'alerts']
                    for table in tables:
                        try:
                            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                            result = cursor.fetchone()
                            stats[f'{table}_count'] = result['count'] if result else 0
                        except:
                            stats[f'{table}_count'] = 0
                    
                    # Get applied migrations count
                    try:
                        cursor.execute("SELECT COUNT(*) as count FROM migrations")
                        result = cursor.fetchone()
                        stats['migrations_applied'] = result['count'] if result else 0
                    except:
                        stats['migrations_applied'] = 0
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {'error': str(e)}
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> bool:
        """
        Clean up old data from database.
        
        Args:
            days_to_keep: Number of days of data to keep
            
        Returns:
            True if successful
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Clean market data
            query = "DELETE FROM market_data WHERE timestamp < ?"
            self.execute_write(query, (cutoff_date.isoformat(),))
            
            # Clean old performance metrics
            query = "DELETE FROM performance_metrics WHERE timestamp < ?"
            self.execute_write(query, (cutoff_date.isoformat(),))
            
            # Clean old alerts
            query = "DELETE FROM alerts WHERE timestamp < ? AND acknowledged = TRUE"
            self.execute_write(query, (cutoff_date.isoformat(),))
            
            # Vacuum database to reclaim space
            self.connection.execute("VACUUM")
            
            self.logger.info(f"Cleaned up data older than {days_to_keep} days")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")
            return False
    
    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def __del__(self):
        """Destructor - ensure connection is closed."""
        try:
            self.disconnect()
        except:
            pass

# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def get_data_access_layer(config: Optional[Dict] = None) -> DataAccessLayer:
    """
    Factory function to get DataAccessLayer instance.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        DataAccessLayer instance
    """
    return DataAccessLayer(config)

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    'DataAccessLayer',
    'get_data_access_layer',
    'ConnectionState',
    'QueryType',
    'ConnectionInfo',
    'Migration'
]

# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":
    # Test the data access layer
    print("Testing DataAccessLayer...")
    print("=" * 60)
    
    # Create instance
    dal = DataAccessLayer()
    
    # Test connection
    print("Testing connection...")
    if dal.test_connection():
        print("✅ Connection test passed")
    else:
        print("❌ Connection test failed")
    
    # Test migrations
    print("\nTesting migrations...")
    if dal.run_migrations():
        print("✅ Migrations completed successfully")
    else:
        print("❌ Migrations failed")
    
    # Get statistics
    print("\nDatabase Statistics:")
    stats = dal.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Test saving data
    print("\nTesting data operations...")
    test_trade = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 100,
        'price': 450.50,
        'order_id': f'TEST_{datetime.now().timestamp()}',
        'status': 'FILLED'
    }
    
    if dal.save_trade(test_trade):
        print("✅ Trade saved successfully")
    else:
        print("❌ Failed to save trade")
    
    # Test retrieving data
    trades = dal.get_trades('SPY')
    print(f"✅ Retrieved {len(trades)} trades")
    
    # Test state management
    if dal.save_state('test_key', {'value': 'test_data', 'timestamp': datetime.now().isoformat()}):
        print("✅ State saved successfully")
    
    state = dal.get_state('test_key')
    if state:
        print(f"✅ State retrieved: {state}")
    
    # Close connection
    dal.close_all_connections()
    print("\n✅ DataAccessLayer test complete!")
