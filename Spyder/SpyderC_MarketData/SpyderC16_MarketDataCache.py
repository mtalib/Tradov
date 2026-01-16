#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC16_MarketDataCache.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import OrderedDict, defaultdict
from functools import lru_cache

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import sqlite3
import pickle
import gzip
import heapq
import pandas as pd
import numpy as np

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
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, EventType, Event

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
    data: Dict[str, Any]
    priority: int = 3
    ttl: Optional[float] = None
    expiry: Optional[datetime] = None
    access_count: int = 0
    last_access: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.expiry:
            return datetime.now() > self.expiry
        return False
    
    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> 'CachedMarketData':
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
    
    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 event_manager: Optional[EventManager] = None):
        """Initialize Market Data Cache"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = event_manager
        
        # Configuration
        self.config = config or DEFAULT_CACHE_CONFIG
        
        # In-memory cache (OrderedDict for LRU)
        self._memory_cache: OrderedDict[str, CachedMarketData] = OrderedDict()
        self._cache_lock = threading.RLock()
        
        # Priority queue for expiration
        self._expiry_heap: List[Tuple[datetime, str]] = []
        
        # Statistics
        self.stats = CacheStats()
        self._access_times: List[float] = []
        
        # Redis connection (optional)
        self.redis_client: Optional[Any] = None
        if self.config['redis']['enabled'] and REDIS_AVAILABLE:
            self._init_redis()
        
        # SQLite persistence
        self.db_path = self.config['persistence']['db_path']
        if self.config['persistence']['enabled']:
            self._init_database()
        
        # Cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
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
            self.logger.warning(f"Redis connection failed: {e}")
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
            self.logger.error(f"Database initialization failed: {e}")
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
        
        self.logger.info("Market Data Cache stopped")
    
    def put(self, symbol: str, data: Dict[str, Any], 
            priority: Optional[int] = None, ttl: Optional[float] = None) -> bool:
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
            
            # Store tick data in SQLite
            if self.config['persistence']['enabled']:
                self._store_tick_data(symbol, data)
            
            # Track access time
            self._access_times.append((time.time() - start_time) * 1000)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Cache put failed for {symbol}: {e}")
            return False
    
    def get(self, symbol: str, max_age: Optional[float] = None) -> Optional[Dict[str, Any]]:
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
            self.logger.error(f"Failed to get range data: {e}")
            return pd.DataFrame()
    
    def invalidate(self, symbol: Optional[str] = None):
        """
        Invalidate cache entries.
        
        Args:
            symbol: Specific symbol to invalidate (None for all)
        """
        with self._cache_lock:
            if symbol:
                if symbol in self._memory_cache:
                    del self._memory_cache[symbol]
                    self.logger.debug(f"Invalidated cache for {symbol}")
            else:
                self._memory_cache.clear()
                self.logger.info("Invalidated all cache entries")
        
        # Invalidate Redis
        if self.redis_client:
            if symbol:
                self.redis_client.delete(f"spyder:market:{symbol}")
            else:
                # Clear all market data keys
                for key in self.redis_client.scan_iter("spyder:market:*"):
                    self.redis_client.delete(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._cache_lock:
            memory_size = len(self._memory_cache)
        
        # Calculate average access time
        avg_access_time = 0.0
        if self._access_times:
            recent_times = self._access_times[-1000:]  # Last 1000 accesses
            avg_access_time = sum(recent_times) / len(recent_times)
        
        self.stats.memory_size = memory_size
        self.stats.avg_access_time_ms = avg_access_time
        
        return {
            'hit_rate': self.stats.hit_rate,
            'hits': self.stats.hits,
            'misses': self.stats.misses,
            'evictions': self.stats.evictions,
            'memory_size': memory_size,
            'memory_limit': self.config['memory']['max_size'],
            'avg_access_time_ms': avg_access_time,
            'redis_available': self.redis_client is not None,
            'disk_enabled': self.config['persistence']['enabled']
        }
    
    # ==========================================================================
    # MEMORY CACHE OPERATIONS
    # ==========================================================================
    def _store_memory(self, key: str, entry: CachedMarketData):
        """Store entry in memory cache with LRU eviction"""
        # Check size limit
        if len(self._memory_cache) >= self.config['memory']['max_size']:
            # Evict based on priority and age
            self._evict_memory()
        
        # Store entry
        self._memory_cache[key] = entry
        
        # Add to expiry heap if TTL set
        if entry.expiry:
            heapq.heappush(self._expiry_heap, (entry.expiry, key))
    
    def _get_memory(self, key: str) -> Optional[CachedMarketData]:
        """Get entry from memory cache"""
        if key in self._memory_cache:
            # Move to end (most recently used)
            entry = self._memory_cache.pop(key)
            self._memory_cache[key] = entry
            
            # Update access stats
            entry.access_count += 1
            entry.last_access = datetime.now()
            
            return entry
        return None
    
    def _evict_memory(self):
        """Evict entries from memory based on priority and age"""
        # Find candidates for eviction (lowest priority, least recently used)
        candidates = []
        
        for key, entry in self._memory_cache.items():
            score = entry.priority * 1000  # Higher priority = higher score
            if entry.last_access:
                age = (datetime.now() - entry.last_access).total_seconds()
                score -= age  # Older = lower score
            candidates.append((score, key))
        
        # Sort by score (lowest first)
        candidates.sort()
        
        # Evict lowest scoring entries
        evict_count = max(1, len(self._memory_cache) // 10)  # Evict 10%
        
        for _, key in candidates[:evict_count]:
            del self._memory_cache[key]
            self.stats.evictions += 1
    
    # ==========================================================================
    # REDIS OPERATIONS
    # ==========================================================================
    def _store_redis(self, symbol: str, entry: CachedMarketData):
        """Store entry in Redis cache"""
        if not self.redis_client:
            return
        
        try:
            key = f"spyder:market:{symbol}"
            data = pickle.dumps(entry.to_dict())
            
            if self.config['persistence']['compression']:
                data = gzip.compress(data)
            
            ttl = entry.ttl or self.config['redis']['ttl_seconds']
            self.redis_client.setex(key, int(ttl), data)
            
        except Exception as e:
            self.logger.error(f"Redis store failed: {e}")
    
    def _get_redis(self, symbol: str) -> Optional[CachedMarketData]:
        """Get entry from Redis cache"""
        if not self.redis_client:
            return None
        
        try:
            key = f"spyder:market:{symbol}"
            data = self.redis_client.get(key)
            
            if data:
                if self.config['persistence']['compression']:
                    data = gzip.decompress(data)
                
                entry_dict = pickle.loads(data)
                return CachedMarketData.from_dict(entry_dict)
                
        except Exception as e:
            self.logger.error(f"Redis get failed: {e}")
        
        return None
    
    # ==========================================================================
    # DISK OPERATIONS
    # ==========================================================================
    def _store_tick_data(self, symbol: str, data: Dict[str, Any]):
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
            self.logger.error(f"Failed to store tick data: {e}")
    
    def _get_disk(self, symbol: str, max_age: Optional[float]) -> Optional[CachedMarketData]:
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
                    
                    data = pickle.loads(data_blob)
                    return CachedMarketData(
                        symbol=symbol,
                        timestamp=datetime.fromtimestamp(timestamp),
                        data=data
                    )
                    
        except Exception as e:
            self.logger.error(f"Failed to get disk data: {e}")
        
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
                self.logger.error(f"Cleanup error: {e}")
            
            # Wait for next cleanup
            time.sleep(self.config['memory']['cleanup_interval'])
    
    def _cleanup_expired(self):
        """Remove expired entries from memory"""
        now = datetime.now()
        expired_keys = []
        
        with self._cache_lock:
            # Check expiry heap
            while self._expiry_heap and self._expiry_heap[0][0] <= now:
                _, key = heapq.heappop(self._expiry_heap)
                if key in self._memory_cache and self._memory_cache[key].is_expired():
                    expired_keys.append(key)
            
            # Remove expired entries
            for key in expired_keys:
                del self._memory_cache[key]
                self.logger.debug(f"Expired cache entry: {key}")
    
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
                
                # Vacuum to reclaim space
                conn.execute('VACUUM')
                
        except Exception as e:
            self.logger.error(f"Disk cleanup failed: {e}")
    
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
                    
                    self.logger.info(f"Preloaded {symbol} with {len(df)} data points")
                    
            except Exception as e:
                self.logger.error(f"Failed to preload {symbol}: {e}")
    
    def _persist_critical_data(self):
        """Persist critical data before shutdown"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                for key, entry in self._memory_cache.items():
                    if entry.priority <= CACHE_PRIORITY['HIGH']:
                        data_blob = pickle.dumps(entry.data)
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
            self.logger.error(f"Failed to persist critical data: {e}")
    
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
            event = Event(
                EventType.SYSTEM_METRICS,
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
    print("📝 Storing market data...")
    for i in range(100):
        symbol = random.choice(symbols)
        data = {
            'bid': 100 + random.random() * 10,
            'ask': 100 + random.random() * 10,
            'last': 100 + random.random() * 10,
            'volume': random.randint(1000, 10000),
            'timestamp': datetime.now()
        }
        
        cache.put(symbol, data, priority=random.randint(1, 4))
        time.sleep(0.01)
    
    # Retrieve data
    print("\n📊 Retrieving data...")
    for symbol in symbols:
        data = cache.get(symbol)
        if data:
            print(f"{symbol}: {data}")
    
    # Get historical range
    print("\n📈 Historical data...")
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=5)
    
    df = cache.get_range('SPY', start_time, end_time)
    if not df.empty:
        print(f"SPY historical data:\n{df.head()}")
    
    # Show stats
    print("\n📊 Cache Statistics:")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Stop cache
    cache.stop()
    print("\n✅ Cache test completed")