#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderH01_DataAccessLayer.py
Group: H (Data Storage)
Purpose: Unified data access layer consolidating all storage operations

Description:
    This module consolidates the functionality of DatabaseManager, TradeRepository,
    MarketDataCache, and PerformanceAnalytics into a single, cohesive data access
    layer. It provides unified interfaces for all data operations with consistent
    error handling, caching, and transaction management.

Author: Mohamed Talib
Date: 2025-01-17
Version: 2.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sqlite3
import os
import json
import threading
import time
import pickle
import gzip
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from contextlib import contextmanager
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import functools

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from cachetools import TTLCache, LRUCache
import redis

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA03_Configuration import get_config_manager

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Database configuration
DEFAULT_DB_PATH = "data/spyder.db"
BACKUP_DIR = "data/backups"
WAL_MODE = True
BUSY_TIMEOUT = 30000
CACHE_SIZE = -64000
MAX_CONNECTIONS = 10

# Cache configuration
CACHE_TTL = {
    'quote': 5,         # 5 seconds
    'option_chain': 60, # 1 minute
    'historical': 300,  # 5 minutes
    'internals': 30,    # 30 seconds
    'trades': 60,       # 1 minute
    'positions': 10,    # 10 seconds
    'performance': 300  # 5 minutes
}

# Redis configuration
REDIS_KEY_PREFIX = "spyder:"
REDIS_EXPIRE_BUFFER = 60

# ==============================================================================
# ENUMS
# ==============================================================================
class DataType(Enum):
    """Types of data handled by DAL"""
    TRADE = "trade"
    POSITION = "position"
    ORDER = "order"
    MARKET_DATA = "market_data"
    OPTION_CHAIN = "option_chain"
    PERFORMANCE = "performance"
    SYSTEM_EVENT = "system_event"

class CacheLevel(Enum):
    """Cache levels"""
    MEMORY = "memory"
    REDIS = "redis"
    DATABASE = "database"

# ==============================================================================
# DATA MODELS
# ==============================================================================
@dataclass
class Trade:
    """Trade data model"""
    trade_id: str
    strategy: str
    symbol: str
    trade_type: str  # 'long' or 'short'
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    quantity: int = 0
    commission: float = 0.0
    slippage: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    mae: Optional[float] = None
    mfe: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    status: str = "open"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        # Convert datetime to ISO format
        data['entry_time'] = self.entry_time.isoformat()
        if self.exit_time:
            data['exit_time'] = self.exit_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Trade':
        """Create from dictionary"""
        # Convert ISO format to datetime
        data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        if data.get('exit_time'):
            data['exit_time'] = datetime.fromisoformat(data['exit_time'])
        return cls(**data)

@dataclass
class Position:
    """Position data model"""
    position_id: str
    strategy: str
    symbol: str
    position_type: str
    quantity: int
    entry_price: float
    current_price: Optional[float] = None
    open_time: datetime = field(default_factory=datetime.now)
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: str = "open"
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class MarketData:
    """Market data model"""
    symbol: str
    timestamp: datetime
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    implied_volatility: Optional[float] = None
    greeks: Optional[Dict[str, float]] = None

# ==============================================================================
# REPOSITORY INTERFACES
# ==============================================================================
class TradeRepository:
    """Trade data repository interface"""
    
    def __init__(self, dal: 'DataAccessLayer'):
        self.dal = dal
        self.logger = SpyderLogger(__name__)
        
    async def create(self, trade: Trade) -> str:
        """Create a new trade"""
        query = """
            INSERT INTO trades (
                trade_id, strategy, symbol, trade_type, entry_time,
                exit_time, entry_price, exit_price, quantity, commission,
                slippage, pnl, pnl_percent, mae, mfe, metadata, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            trade.trade_id, trade.strategy, trade.symbol, trade.trade_type,
            trade.entry_time, trade.exit_time, trade.entry_price, trade.exit_price,
            trade.quantity, trade.commission, trade.slippage, trade.pnl,
            trade.pnl_percent, trade.mae, trade.mfe,
            json.dumps(trade.metadata) if trade.metadata else None,
            trade.status
        )
        
        with self.dal.transaction() as conn:
            conn.execute(query, params)
            
        # Invalidate cache
        self.dal.cache_delete(f"trades:*")
        self.dal.cache_delete(f"positions:{trade.symbol}")
        
        self.logger.info(f"Trade created: {trade.trade_id}")
        return trade.trade_id
        
    async def update(self, trade: Trade) -> bool:
        """Update existing trade"""
        query = """
            UPDATE trades SET
                exit_time = ?, exit_price = ?, pnl = ?, pnl_percent = ?,
                mae = ?, mfe = ?, metadata = ?, status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE trade_id = ?
        """
        
        params = (
            trade.exit_time, trade.exit_price, trade.pnl, trade.pnl_percent,
            trade.mae, trade.mfe,
            json.dumps(trade.metadata) if trade.metadata else None,
            trade.status, trade.trade_id
        )
        
        with self.dal.transaction() as conn:
            cursor = conn.execute(query, params)
            
        # Invalidate cache
        self.dal.cache_delete(f"trade:{trade.trade_id}")
        self.dal.cache_delete(f"trades:*")
        
        return cursor.rowcount > 0
        
    async def get_by_id(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID"""
        # Check cache first
        cache_key = f"trade:{trade_id}"
        cached = self.dal.cache_get(cache_key, DataType.TRADE)
        if cached:
            return Trade.from_dict(cached)
            
        # Query database
        query = "SELECT * FROM trades WHERE trade_id = ?"
        row = self.dal.fetch_one(query, (trade_id,))
        
        if row:
            trade = self._row_to_trade(row)
            # Cache result
            self.dal.cache_set(cache_key, trade.to_dict(), DataType.TRADE)
            return trade
            
        return None
        
    async def get_active_trades(self) -> List[Trade]:
        """Get all active trades"""
        cache_key = "trades:active"
        cached = self.dal.cache_get(cache_key, DataType.TRADE)
        if cached:
            return [Trade.from_dict(t) for t in cached]
            
        query = """
            SELECT * FROM trades 
            WHERE status = 'open' 
            ORDER BY entry_time DESC
        """
        
        rows = self.dal.fetch_all(query)
        trades = [self._row_to_trade(row) for row in rows]
        
        # Cache results
        self.dal.cache_set(
            cache_key,
            [t.to_dict() for t in trades],
            DataType.TRADE
        )
        
        return trades
        
    async def get_trades_by_criteria(
        self,
        strategy: Optional[str] = None,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Trade]:
        """Get trades by criteria"""
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
            
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
            
        if start_date:
            query += " AND entry_time >= ?"
            params.append(start_date)
            
        if end_date:
            query += " AND entry_time <= ?"
            params.append(end_date)
            
        query += " ORDER BY entry_time DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
            
        rows = self.dal.fetch_all(query, tuple(params))
        return [self._row_to_trade(row) for row in rows]
        
    def _row_to_trade(self, row: sqlite3.Row) -> Trade:
        """Convert database row to Trade object"""
        data = dict(row)
        # Parse metadata
        if data.get('metadata'):
            data['metadata'] = json.loads(data['metadata'])
        return Trade(**data)


class PositionRepository:
    """Position data repository interface"""
    
    def __init__(self, dal: 'DataAccessLayer'):
        self.dal = dal
        self.logger = SpyderLogger(__name__)
        
    async def update_position(
        self,
        symbol: str,
        quantity: int,
        avg_price: float,
        strategy: str
    ) -> str:
        """Update or create position"""
        position_id = f"{strategy}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        query = """
            INSERT INTO positions (
                position_id, strategy, symbol, position_type,
                quantity, entry_price, open_time, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(strategy, symbol) DO UPDATE SET
                quantity = ?, entry_price = ?, updated_at = CURRENT_TIMESTAMP
        """
        
        position_type = "long" if quantity > 0 else "short"
        
        params = (
            position_id, strategy, symbol, position_type,
            quantity, avg_price, datetime.now(), "open",
            quantity, avg_price
        )
        
        with self.dal.transaction() as conn:
            conn.execute(query, params)
            
        # Invalidate cache
        self.dal.cache_delete("positions:*")
        
        return position_id
        
    async def get_all_positions(self) -> List[Position]:
        """Get all open positions"""
        cache_key = "positions:all"
        cached = self.dal.cache_get(cache_key, DataType.POSITION)
        if cached:
            return [Position(**p) for p in cached]
            
        query = """
            SELECT p.*, md.price as current_price
            FROM positions p
            LEFT JOIN (
                SELECT symbol, price,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) as rn
                FROM market_data_snapshots
            ) md ON p.symbol = md.symbol AND md.rn = 1
            WHERE p.status = 'open' AND p.quantity != 0
        """
        
        rows = self.dal.fetch_all(query)
        positions = []
        
        for row in rows:
            data = dict(row)
            if data.get('metadata'):
                data['metadata'] = json.loads(data['metadata'])
            positions.append(Position(**data))
            
        # Cache results
        self.dal.cache_set(
            cache_key,
            [asdict(p) for p in positions],
            DataType.POSITION
        )
        
        return positions


class MarketDataRepository:
    """Market data repository interface"""
    
    def __init__(self, dal: 'DataAccessLayer'):
        self.dal = dal
        self.logger = SpyderLogger(__name__)
        
    async def save_tick(self, data: MarketData):
        """Save market data tick"""
        query = """
            INSERT INTO market_data_snapshots (
                timestamp, symbol, price, bid, ask, volume,
                open_interest, implied_volatility, greeks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            data.timestamp, data.symbol, data.price, data.bid, data.ask,
            data.volume, data.open_interest, data.implied_volatility,
            json.dumps(data.greeks) if data.greeks else None
        )
        
        self.dal.execute(query, params)
        
        # Update cache
        cache_key = f"market:latest:{data.symbol}"
        self.dal.cache_set(cache_key, asdict(data), DataType.MARKET_DATA)
        
    async def get_latest(self, symbol: str) -> Optional[MarketData]:
        """Get latest market data for symbol"""
        cache_key = f"market:latest:{symbol}"
        cached = self.dal.cache_get(cache_key, DataType.MARKET_DATA)
        if cached:
            return MarketData(**cached)
            
        query = """
            SELECT * FROM market_data_snapshots
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """
        
        row = self.dal.fetch_one(query, (symbol,))
        if row:
            data = dict(row)
            if data.get('greeks'):
                data['greeks'] = json.loads(data['greeks'])
            market_data = MarketData(**data)
            
            # Cache result
            self.dal.cache_set(cache_key, asdict(market_data), DataType.MARKET_DATA)
            return market_data
            
        return None


# ==============================================================================
# MAIN DATA ACCESS LAYER CLASS
# ==============================================================================
class DataAccessLayer:
    """
    Unified data access layer for all storage operations.
    
    This class consolidates database, caching, and repository functionality
    into a single, cohesive interface.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
        
    def __init__(self):
        """Initialize the data access layer"""
        if hasattr(self, '_initialized'):
            return
            
        self.logger = SpyderLogger(__name__)
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
        
        # In-memory caches by type
        self._memory_caches: Dict[DataType, TTLCache] = {
            DataType.TRADE: TTLCache(maxsize=1000, ttl=CACHE_TTL['trades']),
            DataType.POSITION: TTLCache(maxsize=100, ttl=CACHE_TTL['positions']),
            DataType.MARKET_DATA: TTLCache(maxsize=1000, ttl=CACHE_TTL['quote']),
            DataType.OPTION_CHAIN: TTLCache(maxsize=100, ttl=CACHE_TTL['option_chain']),
            DataType.PERFORMANCE: TTLCache(maxsize=50, ttl=CACHE_TTL['performance'])
        }
        
        # LRU cache for overflow
        self._lru_cache = LRUCache(maxsize=5000)
        
        # Redis client (optional)
        self._redis_client = self._init_redis()
        
        # Initialize repositories
        self.trades = TradeRepository(self)
        self.positions = PositionRepository(self)
        self.market_data = MarketDataRepository(self)
        
        # Initialize database schema
        self._initialize_database()
        
        self._initialized = True
        self.logger.info("DataAccessLayer initialized")
        
    # ==========================================================================
    # DATABASE CONNECTION MANAGEMENT
    # ==========================================================================
    @contextmanager
    def get_connection(self):
        """Get database connection from pool"""
        thread_id = threading.get_ident()
        
        try:
            with self._connection_lock:
                if thread_id not in self._connections:
                    self._connections[thread_id] = self._create_connection()
                    
                conn = self._connections[thread_id]
                
            yield conn
            
        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            raise
            
    @contextmanager
    def transaction(self):
        """Execute operations in a transaction"""
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Transaction failed: {str(e)}")
                raise
                
    def execute(self, query: str, params: Optional[Tuple] = None) -> sqlite3.Cursor:
        """Execute a query"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor
            
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[sqlite3.Row]:
        """Fetch single row"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchone()
            
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[sqlite3.Row]:
        """Fetch all rows"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()
            
    def fetch_dataframe(self, query: str, params: Optional[Tuple] = None) -> pd.DataFrame:
        """Fetch results as DataFrame"""
        with self.get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)
            
    # ==========================================================================
    # CACHING LAYER
    # ==========================================================================
    def cache_get(self, key: str, data_type: DataType) -> Optional[Any]:
        """Get from cache"""
        # Try memory cache first
        cache = self._memory_caches.get(data_type)
        if cache and key in cache:
            return cache[key]
            
        # Try LRU cache
        if key in self._lru_cache:
            return self._lru_cache[key]
            
        # Try Redis
        if self._redis_client:
            return self._get_from_redis(key, data_type)
            
        return None
        
    def cache_set(self, key: str, data: Any, data_type: DataType, ttl: Optional[int] = None):
        """Set in cache"""
        if ttl is None:
            ttl = CACHE_TTL.get(data_type.value, 300)
            
        # Store in memory cache
        cache = self._memory_caches.get(data_type)
        if cache:
            cache[key] = data
        else:
            self._lru_cache[key] = data
            
        # Store in Redis if available
        if self._redis_client:
            self._set_in_redis(key, data, data_type, ttl)
            
    def cache_delete(self, pattern: str):
        """Delete cache entries matching pattern"""
        # Handle wildcards
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            
            # Clear from memory caches
            for cache in self._memory_caches.values():
                keys_to_delete = [k for k in cache.keys() if k.startswith(prefix)]
                for k in keys_to_delete:
                    del cache[k]
                    
            # Clear from LRU cache
            keys_to_delete = [k for k in self._lru_cache.keys() if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._lru_cache[k]
                
            # Clear from Redis
            if self._redis_client:
                for key in self._redis_client.scan_iter(match=f"{REDIS_KEY_PREFIX}{pattern}"):
                    self._redis_client.delete(key)
        else:
            # Delete specific key
            for cache in self._memory_caches.values():
                if pattern in cache:
                    del cache[pattern]
                    
            if pattern in self._lru_cache:
                del self._lru_cache[pattern]
                
            if self._redis_client:
                self._redis_client.delete(f"{REDIS_KEY_PREFIX}{pattern}")
                
    # ==========================================================================
    # SPECIALIZED DATA ACCESS METHODS
    # ==========================================================================
    def get_performance_metrics(
        self,
        strategy: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get performance metrics with caching"""
        cache_key = f"performance:{strategy}:{start_date}:{end_date}"
        cached = self.cache_get(cache_key, DataType.PERFORMANCE)
        if cached:
            return cached
            
        # Calculate performance metrics
        query = """
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                MAX(pnl) as max_win,
                MIN(pnl) as max_loss,
                SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as gross_profit,
                SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END) as gross_loss
            FROM trades
            WHERE status = 'closed'
        """
        
        params = []
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
            
        if start_date:
            query += " AND exit_time >= ?"
            params.append(start_date)
            
        if end_date:
            query += " AND exit_time <= ?"
            params.append(end_date)
            
        row = self.fetch_one(query, tuple(params) if params else None)
        
        if row:
            metrics = dict(row)
            
            # Calculate additional metrics
            if metrics['total_trades'] > 0:
                metrics['win_rate'] = metrics['winning_trades'] / metrics['total_trades']
                metrics['profit_factor'] = (
                    metrics['gross_profit'] / metrics['gross_loss']
                    if metrics['gross_loss'] > 0 else float('inf')
                )
            else:
                metrics['win_rate'] = 0
                metrics['profit_factor'] = 0
                
            # Cache results
            self.cache_set(cache_key, metrics, DataType.PERFORMANCE)
            return metrics
            
        return {}
        
    def get_option_chain(self, underlying: str, expiry: str) -> Optional[pd.DataFrame]:
        """Get option chain data"""
        cache_key = f"chain:{underlying}:{expiry}"
        cached = self.cache_get(cache_key, DataType.OPTION_CHAIN)
        if cached:
            return pd.DataFrame(cached)
            
        query = """
            SELECT * FROM option_chains
            WHERE underlying = ? AND expiry = ?
            ORDER BY strike
        """
        
        df = self.fetch_dataframe(query, (underlying, expiry))
        
        if not df.empty:
            # Cache as dict for serialization
            self.cache_set(cache_key, df.to_dict('records'), DataType.OPTION_CHAIN)
            
        return df if not df.empty else None
        
    # ==========================================================================
    # BACKUP AND MAINTENANCE
    # ==========================================================================
    def backup_database(self, tag: Optional[str] = None) -> str:
        """Create database backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"spyder_backup_{timestamp}"
        
        if tag:
            backup_name += f"_{tag}"
            
        backup_path = os.path.join(self.backup_dir, f"{backup_name}.db")
        
        try:
            import shutil
            with self.get_connection() as conn:
                # Use SQLite backup API
                backup_conn = sqlite3.connect(backup_path)
                conn.backup(backup_conn)
                backup_conn.close()
                
            # Compress backup
            shutil.make_archive(backup_path, 'gzip', self.backup_dir, f"{backup_name}.db")
            os.remove(backup_path)
            
            compressed_path = f"{backup_path}.gz"
            self.logger.info(f"Database backed up to {compressed_path}")
            
            return compressed_path
            
        except Exception as e:
            self.logger.error(f"Backup failed: {str(e)}")
            raise
            
    def vacuum_database(self):
        """Vacuum database to reclaim space"""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
        self.logger.info("Database vacuumed")
        
    def check_integrity(self) -> Tuple[bool, List[str]]:
        """Check database integrity"""
        errors = []
        
        result = self.fetch_all("PRAGMA integrity_check")
        for row in result:
            if row[0] != 'ok':
                errors.append(row[0])
                
        is_valid = len(errors) == 0
        
        if is_valid:
            self.logger.info("Database integrity check passed")
        else:
            self.logger.error(f"Database integrity check failed: {errors}")
            
        return is_valid, errors
        
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _create_connection(self) -> sqlite3.Connection:
        """Create new database connection"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
            isolation_level=None,
            check_same_thread=False
        )
        
        # Enable row factory
        conn.row_factory = sqlite3.Row
        
        # Set pragmas
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT}")
        conn.execute("PRAGMA foreign_keys=ON")
        
        if WAL_MODE:
            conn.execute("PRAGMA journal_mode=WAL")
            
        return conn
        
    def _initialize_database(self):
        """Initialize database schema"""
        # Combined schema from all modules
        schema_sql = """
        -- Schema version table
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        );

        -- Trades table (from DatabaseManager + TradeRepository)
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT UNIQUE NOT NULL,
            strategy TEXT NOT NULL,
            symbol TEXT NOT NULL,
            trade_type TEXT NOT NULL,
            entry_time TIMESTAMP NOT NULL,
            exit_time TIMESTAMP,
            entry_price REAL NOT NULL,
            exit_price REAL,
            quantity INTEGER NOT NULL,
            commission REAL DEFAULT 0,
            slippage REAL DEFAULT 0,
            pnl REAL DEFAULT 0,
            pnl_percent REAL DEFAULT 0,
            mae REAL,
            mfe REAL,
            metadata TEXT,
            status TEXT DEFAULT 'open',
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
            unrealized_pnl REAL DEFAULT 0,
            realized_pnl REAL DEFAULT 0,
            max_profit REAL,
            max_loss REAL,
            status TEXT NOT NULL DEFAULT 'open',
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(strategy, symbol)
        );

        -- Market data table (from MarketDataCache)
        CREATE TABLE IF NOT EXISTS market_data_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            bid REAL,
            ask REAL,
            volume INTEGER,
            open_interest INTEGER,
            implied_volatility REAL,
            greeks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Option chains table
        CREATE TABLE IF NOT EXISTS option_chains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            underlying TEXT NOT NULL,
            expiry TEXT NOT NULL,
            strike REAL NOT NULL,
            option_type TEXT NOT NULL,
            bid REAL,
            ask REAL,
            last REAL,
            volume INTEGER,
            open_interest INTEGER,
            implied_volatility REAL,
            greeks TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(underlying, expiry, strike, option_type)
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

        -- Daily performance table (from PerformanceAnalytics)
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
        CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
        CREATE INDEX IF NOT EXISTS idx_positions_strategy_status ON positions(strategy, status);
        CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data_snapshots(symbol, timestamp);
        CREATE INDEX IF NOT EXISTS idx_orders_strategy_status ON orders(strategy, status);
        CREATE INDEX IF NOT EXISTS idx_daily_performance_date ON daily_performance(date);
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
        
        with self.transaction() as conn:
            conn.executescript(schema_sql)
            
        self.logger.info("Database schema initialized")
        
    def _init_redis(self) -> Optional[redis.Redis]:
        """Initialize Redis connection"""
        if not self.config.get('cache.use_redis', False):
            return None
            
        try:
            client = redis.Redis(
                host=self.config.get('cache.redis_host', 'localhost'),
                port=self.config.get('cache.redis_port', 6379),
                db=self.config.get('cache.redis_db', 0),
                decode_responses=False
            )
            client.ping()
            self.logger.info("Redis cache connected")
            return client
        except Exception as e:
            self.logger.warning(f"Redis connection failed: {str(e)}")
            return None
            
    def _get_from_redis(self, key: str, data_type: DataType) -> Optional[Any]:
        """Get from Redis cache"""
        if not self._redis_client:
            return None
            
        try:
            redis_key = f"{REDIS_KEY_PREFIX}{data_type.value}:{key}"
            data = self._redis_client.get(redis_key)
            
            if data:
                data = gzip.decompress(data)
                return pickle.loads(data)
                
        except Exception as e:
            self.logger.error(f"Redis get error: {str(e)}")
            
        return None
        
    def _set_in_redis(self, key: str, data: Any, data_type: DataType, ttl: int):
        """Set in Redis cache"""
        if not self._redis_client:
            return
            
        try:
            redis_key = f"{REDIS_KEY_PREFIX}{data_type.value}:{key}"
            pickled = pickle.dumps(data)
            compressed = gzip.compress(pickled, compresslevel=1)
            
            self._redis_client.setex(
                redis_key,
                ttl + REDIS_EXPIRE_BUFFER,
                compressed
            )
        except Exception as e:
            self.logger.error(f"Redis set error: {str(e)}")
            
    def close_all_connections(self):
        """Close all database connections"""
        with self._connection_lock:
            for conn in self._connections.values():
                conn.close()
            self._connections.clear()
            
        if self._redis_client:
            self._redis_client.close()
            
        self.logger.info("All connections closed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_dal_instance: Optional[DataAccessLayer] = None

def get_data_access_layer() -> DataAccessLayer:
    """Get singleton instance of data access layer"""
    global _dal_instance
    if _dal_instance is None:
        _dal_instance = DataAccessLayer()
    return _dal_instance

# ==============================================================================
# DECORATORS
# ==============================================================================
def cache_result(data_type: DataType = DataType.PERFORMANCE, ttl: Optional[int] = None):
    """Decorator to cache function results"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            key_hash = hashlib.md5(key.encode()).hexdigest()
            
            # Try cache
            dal = get_data_access_layer()
            result = dal.cache_get(key_hash, data_type)
            
            if result is None:
                # Cache miss - call function
                result = await func(*args, **kwargs)
                if result is not None:
                    dal.cache_set(key_hash, result, data_type, ttl)
                    
            return result
            
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            key_hash = hashlib.md5(key.encode()).hexdigest()
            
            # Try cache
            dal = get_data_access_layer()
            result = dal.cache_get(key_hash, data_type)
            
            if result is None:
                # Cache miss - call function
                result = func(*args, **kwargs)
                if result is not None:
                    dal.cache_set(key_hash, result, data_type, ttl)
                    
            return result
            
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator

# ==============================================================================
# USAGE EXAMPLE
# ==============================================================================
async def example_usage():
    """Example usage of the consolidated DAL"""
    # Get DAL instance
    dal = get_data_access_layer()
    
    # Create a trade
    trade = Trade(
        trade_id="T20250117_001",
        strategy="iron_condor",
        symbol="SPY_20250201C550",
        trade_type="short",
        entry_time=datetime.now(),
        entry_price=5.50,
        quantity=10
    )
    
    # Save trade
    await dal.trades.create(trade)
    print(f"Trade created: {trade.trade_id}")
    
    # Get latest market data
    market_data = await dal.market_data.get_latest("SPY")
    if market_data:
        print(f"SPY Price: {market_data.price}")
        
    # Get performance metrics
    metrics = dal.get_performance_metrics(strategy="iron_condor")
    print(f"Win rate: {metrics.get('win_rate', 0):.2%}")
    
    # Transaction example
    with dal.transaction() as conn:
        conn.execute("UPDATE trades SET status = ? WHERE trade_id = ?", ("closed", trade.trade_id))
        conn.execute("INSERT INTO system_events (event_time, event_type, event_source) VALUES (?, ?, ?)",
                    (datetime.now(), "trade_closed", "example"))
        
    # Get all positions
    positions = await dal.positions.get_all_positions()
    print(f"Active positions: {len(positions)}")
    
    # Backup database
    backup_path = dal.backup_database("example")
    print(f"Backup created: {backup_path}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())