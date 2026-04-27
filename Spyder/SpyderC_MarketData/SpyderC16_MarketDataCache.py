#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC16_MarketDataCache.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    Multi-tier market data cache (memory → Redis → SQLite) designed for
    real-time streaming data with EventManager integration.

    Note: SpyderH03_MarketDataCache provides a simpler in-memory-only cache
    with typed get/set methods (quote, bar, option_chain, greeks). For general
    caching, prefer H03. Use C16 only when persistence or Redis is required.

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import sqlite3
import json
import gzip
import pandas as pd

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, EventType, Event
from Spyder.SpyderH_Storage.SpyderH03_MarketDataCache import (
    MarketDataCache as L1MarketDataCache,
    CacheDataType,
)

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Cache Configuration
DEFAULT_CACHE_CONFIG = {
    'memory': {
        'max_size': 10000,  # Maximum items in memory
        'ttl_seconds': 5,   # Default TTL
        'cleanup_interval': 60  # Cleanup interval in seconds
    },
    'persistence': {
        'enabled': True,
        'db_path': 'spyder_market_cache.db',
        'retention_days': 30,
        'compression': True
    },
    'redis': {
        'enabled': False,
        'host': 'localhost',
        'port': 6379,
        'db': 0,
        'ttl_seconds': 300
    },
    'preload': {
        'enabled': True,
        'symbols': ['SPY', 'VIX', 'SPX', '/ES'],
        'lookback_minutes': 390  # Trading day
    }
}

# Cache priorities
CACHE_PRIORITY = {
    'CRITICAL': 1,
    'HIGH': 2,
    'MEDIUM': 3,
    'LOW': 4
}

# Data types for structured storage
TICK_FIELDS = [
    'bid', 'ask', 'last', 'bid_size', 'ask_size', 'last_size',
    'high', 'low', 'open', 'close', 'volume', 'vwap'
]

# ==============================================================================
# ENUMS
# ==============================================================================
class CacheLevel(Enum):
    """Cache storage levels"""
    MEMORY = "memory"
    REDIS = "redis"
    DISK = "disk"

class DataGranularity(Enum):
    """Data granularity levels"""
    TICK = "tick"
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAILY = "daily"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class CachedMarketData:
    """Cached market data entry"""
    symbol: str
    timestamp: datetime
    data: dict[str, Any]
    priority: int = 3
    ttl: float | None = None
    expiry: datetime | None = None
    access_count: int = 0
    last_access: datetime | None = None

    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.expiry:
            return datetime.now() > self.expiry
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'priority': self.priority,
            'ttl': self.ttl,
            'expiry': self.expiry.isoformat() if self.expiry else None,
            'access_count': self.access_count,
            'last_access': self.last_access.isoformat() if self.last_access else None
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CachedMarketData':
        """Create from dictionary"""
        return cls(
            symbol=data['symbol'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            data=data['data'],
            priority=data.get('priority', 3),
            ttl=data.get('ttl'),
            expiry=datetime.fromisoformat(data['expiry']) if data.get('expiry') else None,
            access_count=data.get('access_count', 0),
            last_access=datetime.fromisoformat(data['last_access']) if data.get('last_access') else None
        )

@dataclass
class CacheStats:
    """Cache performance statistics"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_size: int = 0
    disk_size: int = 0
    avg_access_time_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class MarketDataCache:
    """
    High-performance market data cache with multi-tiered storage.

    Provides fast in-memory caching with optional Redis and SQLite persistence
    for historical data storage and recovery.
    """

    def __init__(self, config: dict[str, Any] | None = None,
                 event_manager: EventManager | None = None):
        """Initialize Market Data Cache"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = event_manager

        # Configuration
        self.config = config or DEFAULT_CACHE_CONFIG

        # L1 cache ownership is delegated to H03.
        self._cache_lock = threading.RLock()
        self._l1_cache = L1MarketDataCache(
            max_size=self.config['memory']['max_size'],
            default_ttl=int(self.config['memory']['ttl_seconds']),
            auto_cleanup=True,
        )

        # Statistics
        self.stats = CacheStats()
        self._access_times: list[float] = []
        self._l1_hits = 0
        self._l2_hits = 0
        self._l3_hits = 0
        self._redis_fallbacks = 0

        # Redis connection (optional)
        self.redis_client: Any | None = None
        if self.config['redis']['enabled'] and REDIS_AVAILABLE:
            self._init_redis()

        # SQLite persistence
        self.db_path = self.config['persistence']['db_path']
        if self.config['persistence']['enabled']:
            self._init_database()

        # Cleanup thread
        self._cleanup_thread: threading.Thread | None = None
        self._running = False

        self.logger.info("Market Data Cache initialized")

    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=self.config['redis']['host'],
                port=self.config['redis']['port'],
                db=self.config['redis']['db'],
                decode_responses=False  # We'll handle encoding
            )
            self.redis_client.ping()
            self.logger.info("Redis cache connected")
        except Exception as e:
            self.logger.warning("Redis connection failed: %s", e, exc_info=True)
            self.redis_client = None

    def _init_database(self):
        """Initialize SQLite database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS market_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        data BLOB NOT NULL,
                        priority INTEGER DEFAULT 3,
                        created_at REAL DEFAULT (julianday('now')),
                        UNIQUE(symbol, timestamp)
                    )
                ''')

                # Create indices
                conn.execute('CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON market_data(symbol, timestamp)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON market_data(created_at)')

                # Tick data table for high-frequency storage
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS tick_data (
                        symbol TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        bid REAL,
                        ask REAL,
                        last REAL,
                        bid_size INTEGER,
                        ask_size INTEGER,
                        last_size INTEGER,
                        volume INTEGER,
                        PRIMARY KEY (symbol, timestamp)
                    )
                ''')

                conn.commit()
                self.logger.info("SQLite database initialized")

        except Exception as e:
            self.logger.error("Database initialization failed: %s", e, exc_info=True)
            raise

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def start(self):
        """Start the cache system"""
        self._running = True

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self._cleanup_thread.start()

        # Preload data if configured
        if self.config['preload']['enabled']:
            self._preload_cache()

        self.logger.info("Market Data Cache started")

    def stop(self):
        """Stop the cache system"""
        self._running = False

        # Wait for cleanup thread
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)

        # Persist important data
        self._persist_critical_data()

        # Close connections
        if self.redis_client:
            self.redis_client.close()

        # Stop delegated L1 cache thread
        self._l1_cache.shutdown()

        self.logger.info("Market Data Cache stopped")

    def put(self, symbol: str, data: dict[str, Any],
            priority: int | None = None, ttl: float | None = None) -> bool:
        """
        Store market data in cache.

        Args:
            symbol: Market symbol
            data: Market data dictionary
            priority: Cache priority (1-4)
            ttl: Time to live in seconds

        Returns:
            Success status
        """
        start_time = time.time()

        try:
            # Create cache entry
            ttl = ttl or self.config['memory']['ttl_seconds']
            priority = priority or CACHE_PRIORITY.get(data.get('tier', 'MEDIUM'), 3)

            entry = CachedMarketData(
                symbol=symbol,
                timestamp=datetime.now(),
                data=data,
                priority=priority,
                ttl=ttl,
                expiry=datetime.now() + timedelta(seconds=ttl) if ttl else None
            )

            # Store in memory
            with self._cache_lock:
                self._store_memory(symbol, entry)

            # Store in Redis if available
            if self.redis_client:
                self._store_redis(symbol, entry)
            elif self.config['redis']['enabled']:
                self._redis_fallbacks += 1

            # Store tick data in SQLite
            if self.config['persistence']['enabled']:
                self._store_tick_data(symbol, data)

            # Track access time
            self._access_times.append((time.time() - start_time) * 1000)

            return True

        except Exception as e:
            self.logger.error("Cache put failed for %s: %s", symbol, e, exc_info=True)
            return False

    def get(self, symbol: str, max_age: float | None = None) -> dict[str, Any] | None:
        """
        Retrieve market data from cache.

        Args:
            symbol: Market symbol
            max_age: Maximum age in seconds (optional)

        Returns:
            Market data or None if not found/expired
        """
        start_time = time.time()

        # Check memory cache first
        with self._cache_lock:
            entry = self._get_memory(symbol)

        if entry and not entry.is_expired():
            if max_age:
                age = (datetime.now() - entry.timestamp).total_seconds()
                if age > max_age:
                    entry = None

            if entry:
                self.stats.hits += 1
                self._l1_hits += 1
                self._access_times.append((time.time() - start_time) * 1000)
                return entry.data

        # Check Redis
        if self.redis_client and not entry:
            entry = self._get_redis(symbol)
            if entry:
                # Promote to memory cache
                with self._cache_lock:
                    self._store_memory(symbol, entry)
                self.stats.hits += 1
                self._l2_hits += 1
                self._access_times.append((time.time() - start_time) * 1000)
                return entry.data

        # Check disk
        if self.config['persistence']['enabled'] and not entry:
            entry = self._get_disk(symbol, max_age)
            if entry:
                # Promote to memory cache
                with self._cache_lock:
                    self._store_memory(symbol, entry)
                self.stats.hits += 1
                self._l3_hits += 1
                self._access_times.append((time.time() - start_time) * 1000)
                return entry.data

        # Cache miss
        self.stats.misses += 1
        self._access_times.append((time.time() - start_time) * 1000)
        return None

    def get_range(self, symbol: str, start_time: datetime,
                  end_time: datetime, granularity: DataGranularity = DataGranularity.TICK) -> pd.DataFrame:
        """
        Get historical data range from cache.

        Args:
            symbol: Market symbol
            start_time: Start timestamp
            end_time: End timestamp
            granularity: Data granularity

        Returns:
            DataFrame with historical data
        """
        if not self.config['persistence']['enabled']:
            return pd.DataFrame()

        try:
            with sqlite3.connect(self.db_path) as conn:
                if granularity == DataGranularity.TICK:
                    query = '''
                        SELECT timestamp, bid, ask, last, bid_size, ask_size,
                               last_size, volume
                        FROM tick_data
                        WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
                        ORDER BY timestamp
                    '''
                    df = pd.read_sql_query(
                        query,
                        conn,
                        params=(symbol, start_time.timestamp(), end_time.timestamp())
                    )

                    if not df.empty:
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                        df.set_index('timestamp', inplace=True)

                    return df
                else:
                    # Aggregate data based on granularity
                    return self._aggregate_tick_data(symbol, start_time, end_time, granularity)

        except Exception as e:
            self.logger.error("Failed to get range data: %s", e, exc_info=True)
            return pd.DataFrame()

    def invalidate(self, symbol: str | None = None):
        """
        Invalidate cache entries.

        Args:
            symbol: Specific symbol to invalidate (None for all)
        """
        with self._cache_lock:
            if symbol:
                if symbol in self._l1_cache:
                    self._l1_cache.invalidate(symbol)
                    self.logger.debug("Invalidated cache for %s", symbol)
            else:
                self._l1_cache.clear()
                self.logger.info("Invalidated all cache entries")

        # Invalidate Redis
        if self.redis_client:
            if symbol:
                self.redis_client.delete(f"spyder:market:{symbol}")
            else:
                # Clear all market data keys
                for key in self.redis_client.scan_iter("spyder:market:*"):
                    self.redis_client.delete(key)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        with self._cache_lock:
            memory_size = len(self._l1_cache)

        # Calculate average access time
        avg_access_time = 0.0
        if self._access_times:
            recent_times = self._access_times[-1000:]  # Last 1000 accesses
            avg_access_time = sum(recent_times) / len(recent_times)

        self.stats.memory_size = memory_size
        self.stats.avg_access_time_ms = avg_access_time

        mode = "local_only"
        redis_available = self.redis_client is not None
        if self.config['redis']['enabled'] and redis_available:
            mode = "local_plus_redis"
        elif self.config['redis']['enabled'] and not redis_available:
            mode = "degraded"

        return {
            'mode': mode,
            'hit_rate': self.stats.hit_rate,
            'hits': self.stats.hits,
            'misses': self.stats.misses,
            'evictions': self.stats.evictions,
            'memory_size': memory_size,
            'memory_limit': self.config['memory']['max_size'],
            'avg_access_time_ms': avg_access_time,
            'redis_available': redis_available,
            'tier_hits': {
                'l1': self._l1_hits,
                'l2_redis': self._l2_hits,
                'l3_disk': self._l3_hits,
            },
            'redis_fallbacks': self._redis_fallbacks,
            'disk_enabled': self.config['persistence']['enabled']
        }

    # ==========================================================================
    # MEMORY CACHE OPERATIONS
    # ==========================================================================
    def _store_memory(self, key: str, entry: CachedMarketData):
        """Store entry in delegated H03 L1 cache."""
        ttl = int(entry.ttl or self.config['memory']['ttl_seconds'])
        self._l1_cache.set(key, entry, data_type=CacheDataType.CUSTOM, ttl=ttl)

    def _get_memory(self, key: str) -> CachedMarketData | None:
        """Get entry from delegated H03 L1 cache."""
        entry = self._l1_cache.get(key)
        if isinstance(entry, CachedMarketData):
            entry.access_count += 1
            entry.last_access = datetime.now()
            return entry
        return None

    def _evict_memory(self):
        """Compatibility no-op: H03 owns eviction."""
        return

    # ==========================================================================
    # REDIS OPERATIONS
    # ==========================================================================
    def _store_redis(self, symbol: str, entry: CachedMarketData):
        """Store entry in Redis cache"""
        if not self.redis_client:
            return

        try:
            key = f"spyder:market:{symbol}"
            data = json.dumps(entry.to_dict()).encode()

            if self.config['persistence']['compression']:
                data = gzip.compress(data)

            ttl = entry.ttl or self.config['redis']['ttl_seconds']
            self.redis_client.setex(key, int(ttl), data)

        except Exception as e:
            self.logger.error("Redis store failed: %s", e, exc_info=True)

    def _get_redis(self, symbol: str) -> CachedMarketData | None:
        """Get entry from Redis cache"""
        if not self.redis_client:
            return None

        try:
            key = f"spyder:market:{symbol}"
            data = self.redis_client.get(key)

            if data:
                if self.config['persistence']['compression']:
                    data = gzip.decompress(data)

                entry_dict = json.loads(data)
                return CachedMarketData.from_dict(entry_dict)

        except Exception as e:
            self.logger.error("Redis get failed: %s", e, exc_info=True)

        return None

    # ==========================================================================
    # DISK OPERATIONS
    # ==========================================================================
    def _store_tick_data(self, symbol: str, data: dict[str, Any]):
        """Store tick data in SQLite"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO tick_data
                    (symbol, timestamp, bid, ask, last, bid_size, ask_size, last_size, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    datetime.now().timestamp(),
                    data.get('bid'),
                    data.get('ask'),
                    data.get('last'),
                    data.get('bid_size'),
                    data.get('ask_size'),
                    data.get('last_size'),
                    data.get('volume')
                ))

        except Exception as e:
            self.logger.error("Failed to store tick data: %s", e, exc_info=True)

    def _get_disk(self, symbol: str, max_age: float | None) -> CachedMarketData | None:
        """Get latest entry from disk"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = '''
                    SELECT data, timestamp FROM market_data
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                '''

                if max_age:
                    min_timestamp = (datetime.now() - timedelta(seconds=max_age)).timestamp()
                    query = '''
                        SELECT data, timestamp FROM market_data
                        WHERE symbol = ? AND timestamp >= ?
                        ORDER BY timestamp DESC
                        LIMIT 1
                    '''
                    result = conn.execute(query, (symbol, min_timestamp)).fetchone()
                else:
                    result = conn.execute(query, (symbol,)).fetchone()

                if result:
                    data_blob, timestamp = result
                    if self.config['persistence']['compression']:
                        data_blob = gzip.decompress(data_blob)

                    data = json.loads(data_blob)
                    return CachedMarketData(
                        symbol=symbol,
                        timestamp=datetime.fromtimestamp(timestamp),
                        data=data
                    )

        except Exception as e:
            self.logger.error("Failed to get disk data: %s", e, exc_info=True)

        return None

    # ==========================================================================
    # CLEANUP AND MAINTENANCE
    # ==========================================================================
    def _cleanup_loop(self):
        """Background cleanup thread"""
        while self._running:
            try:
                # Clean expired entries
                self._cleanup_expired()

                # Clean old disk data
                if self.config['persistence']['enabled']:
                    self._cleanup_disk()

                # Update stats
                self._update_stats()

            except Exception as e:
                self.logger.error("Cleanup error: %s", e, exc_info=True)

            # Wait for next cleanup
            time.sleep(self.config['memory']['cleanup_interval'])  # thread-safe: time.sleep() intentional

    def _cleanup_expired(self):
        """Compatibility no-op: H03 handles expiration cleanup."""
        return

    def _cleanup_disk(self):
        """Clean old data from disk"""
        try:
            retention_days = self.config['persistence']['retention_days']
            cutoff = datetime.now() - timedelta(days=retention_days)

            with sqlite3.connect(self.db_path) as conn:
                # Clean market_data table
                conn.execute(
                    'DELETE FROM market_data WHERE created_at < ?',
                    (cutoff.timestamp(),)
                )

                # Clean tick_data table
                conn.execute(
                    'DELETE FROM tick_data WHERE timestamp < ?',
                    (cutoff.timestamp(),)
                )

                # VACUUM cannot run inside a transaction.
                conn.commit()
                conn.execute('VACUUM')

        except Exception as e:
            self.logger.error("Disk cleanup failed: %s", e, exc_info=True)

    # ==========================================================================
    # CACHE WARMING
    # ==========================================================================
    def _preload_cache(self):
        """Preload cache with recent data"""
        symbols = self.config['preload']['symbols']
        lookback = self.config['preload']['lookback_minutes']

        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=lookback)

        for symbol in symbols:
            try:
                # Load recent data
                df = self.get_range(symbol, start_time, end_time)

                if not df.empty:
                    # Cache latest data point
                    latest = df.iloc[-1].to_dict()
                    self.put(symbol, latest, priority=CACHE_PRIORITY['HIGH'])

                    self.logger.info("Preloaded %s with %s data points", symbol, len(df))

            except Exception as e:
                self.logger.error("Failed to preload %s: %s", symbol, e, exc_info=True)

    def _persist_critical_data(self):
        """Persist critical data before shutdown"""
        try:
            if not self.config['persistence']['enabled']:
                return

            with sqlite3.connect(self.db_path) as conn:
                for key in self._l1_cache.get_keys():
                    entry = self._l1_cache.get(key)
                    if not isinstance(entry, CachedMarketData):
                        continue

                    if entry.priority <= CACHE_PRIORITY['HIGH']:
                        data_blob = json.dumps(entry.data).encode()
                        if self.config['persistence']['compression']:
                            data_blob = gzip.compress(data_blob)

                        conn.execute('''
                            INSERT OR REPLACE INTO market_data
                            (symbol, timestamp, data, priority)
                            VALUES (?, ?, ?, ?)
                        ''', (
                            entry.symbol,
                            entry.timestamp.timestamp(),
                            data_blob,
                            entry.priority
                        ))

                conn.commit()

        except Exception as e:
            self.logger.error("Failed to persist critical data: %s", e, exc_info=True)

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _aggregate_tick_data(self, symbol: str, start_time: datetime,
                           end_time: datetime, granularity: DataGranularity) -> pd.DataFrame:
        """Aggregate tick data to specified granularity"""
        # Get tick data
        df = self.get_range(symbol, start_time, end_time, DataGranularity.TICK)

        if df.empty:
            return df

        # Determine resampling frequency
        freq_map = {
            DataGranularity.SECOND: '1S',
            DataGranularity.MINUTE: '1T',
            DataGranularity.HOUR: '1H',
            DataGranularity.DAILY: '1D'
        }

        freq = freq_map.get(granularity, '1T')

        # Resample
        agg_rules = {
            'bid': 'last',
            'ask': 'last',
            'last': 'last',
            'bid_size': 'last',
            'ask_size': 'last',
            'last_size': 'sum',
            'volume': 'sum'
        }

        return df.resample(freq).agg(agg_rules).dropna()

    def _update_stats(self):
        """Update cache statistics"""
        # Calculate disk size
        if self.config['persistence']['enabled'] and os.path.exists(self.db_path):
            self.stats.disk_size = os.path.getsize(self.db_path)

        # Publish stats event if event manager available
        if self.event_manager:
            metrics_event_type = getattr(EventType, 'SYSTEM_METRICS', EventType.INFO)
            event = Event(
                metrics_event_type,
                {
                    'component': 'MarketDataCache',
                    'stats': self.get_stats()
                }
            )
            self.event_manager.publish(event)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the cache system
    import random

    # Initialize cache
    cache = MarketDataCache()
    cache.start()

    # Test data
    symbols = ['SPY', 'VIX', 'QQQ', 'IWM', 'TLT']

    # Store some data
    for _i in range(100):
        symbol = random.choice(symbols)
        data = {
            'bid': 100 + random.random() * 10,
            'ask': 100 + random.random() * 10,
            'last': 100 + random.random() * 10,
            'volume': random.randint(1000, 10000),
            'timestamp': datetime.now()
        }

        cache.put(symbol, data, priority=random.randint(1, 4))
        time.sleep(0.01)  # thread-safe: time.sleep() intentional

    # Retrieve data
    for symbol in symbols:
        data = cache.get(symbol)
        if data:
            pass

    # Get historical range
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=5)

    df = cache.get_range('SPY', start_time, end_time)
    if not df.empty:
        pass

    # Show stats
    stats = cache.get_stats()
    for _key, _value in stats.items():
        pass

    # Stop cache
    cache.stop()
