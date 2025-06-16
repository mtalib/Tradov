#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderH03_MarketDataCache.py
Group: H (Data Storage)
Purpose: Market data caching layer

Description:
    This module provides a high-performance caching layer for market data
    to reduce API calls and improve system responsiveness. It implements
    a multi-tier caching strategy with in-memory cache for hot data and
    disk-based cache for historical data. The cache supports real-time
    price updates, options chain data, and market internals with automatic
    expiration and memory management.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import json
import pickle
import gzip
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from dataclasses import dataclass, field
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
from collections import defaultdict
from cachetools import TTLCache, LRUCache
import redis
import functools

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA03_Configuration import get_config_manager
class CacheType(Enum):
    """Types of cached data"""
    QUOTE = "quote"
    OPTION_CHAIN = "option_chain"
    HISTORICAL = "historical"
    MARKET_INTERNALS = "internals"
    VOLUME_PROFILE = "volume_profile"
    CUSTOM = "custom"

class CacheStatus(Enum):
    """Cache entry status"""
    HIT = "hit"
    MISS = "miss"
    EXPIRED = "expired"
    ERROR = "error"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class CacheEntry:
    """Cache entry container"""
    key: str
    data: Any
    timestamp: datetime
    ttl: int
    cache_type: CacheType
    size_bytes: int = 0
    access_count: int = 0
    last_access: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class CacheStats:
    """Cache statistics"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_size_mb: float = 0.0
    item_count: int = 0
    eviction_count: int = 0
    error_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

# ==============================================================================
# MARKET DATA CACHE CLASS
# ==============================================================================
class MarketDataCache:
    """
    High-performance market data cache implementation.
    
    Features:
    - Multi-tier caching (memory + Redis)
    - Automatic expiration and eviction
    - Memory management
    - Cache warming
    - Statistics tracking
    """
    
    def __init__(self):
        """Initialize market data cache"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = get_config_manager()
        
        # In-memory caches by type
        self._caches: Dict[CacheType, TTLCache] = {
            CacheType.QUOTE: TTLCache(maxsize=1000, ttl=QUOTE_TTL),
            CacheType.OPTION_CHAIN: TTLCache(maxsize=100, ttl=OPTION_CHAIN_TTL),
            CacheType.HISTORICAL: TTLCache(maxsize=50, ttl=HISTORICAL_TTL),
            CacheType.MARKET_INTERNALS: TTLCache(maxsize=100, ttl=MARKET_INTERNALS_TTL),
            CacheType.VOLUME_PROFILE: TTLCache(maxsize=50, ttl=DEFAULT_TTL),
            CacheType.CUSTOM: TTLCache(maxsize=500, ttl=DEFAULT_TTL)
        }
        
        # LRU cache for overflow
        self._lru_cache = LRUCache(maxsize=MAX_CACHE_ITEMS)
        
        # Redis connection (optional)
        self._redis_client = self._init_redis()
        
        # Statistics
        self._stats = CacheStats()
        self._stats_lock = threading.RLock()
        
        # Memory management
        self._memory_limit_mb = self.config.get('cache.memory_limit_mb', MAX_MEMORY_MB)
        self._current_size_bytes = 0
        
        # Cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="CacheCleanup"
        )
        self._running = True
        self._cleanup_thread.start()
        
        # Cache callbacks
        self._miss_callbacks: Dict[CacheType, List[Callable]] = defaultdict(list)
        
        self.logger.info("MarketDataCache initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - CACHE OPERATIONS
    # ==========================================================================
    def get(self, key: str, cache_type: CacheType = CacheType.CUSTOM) -> Optional[Any]:
        """
        Get data from cache.
        
        Args:
            key: Cache key
            cache_type: Type of cache
            
        Returns:
            Cached data or None
        """
        with self._stats_lock:
            self._stats.total_requests += 1
        
        # Try memory cache first
        cache = self._caches.get(cache_type)
        if cache:
            try:
                data = cache[key]
                self._record_hit()
                return data
            except KeyError:
                pass
        
        # Try LRU cache
        if key in self._lru_cache:
            data = self._lru_cache[key]
            self._record_hit()
            return data
        
        # Try Redis if available
        if self._redis_client:
            data = self._get_from_redis(key, cache_type)
            if data is not None:
                # Promote to memory cache
                self._caches[cache_type][key] = data
                self._record_hit()
                return data
        
        # Cache miss
        self._record_miss()
        self._trigger_miss_callbacks(key, cache_type)
        return None
    
    def set(self, key: str, data: Any, cache_type: CacheType = CacheType.CUSTOM,
            ttl: Optional[int] = None) -> bool:
        """
        Set data in cache.
        
        Args:
            key: Cache key
            data: Data to cache
            cache_type: Type of cache
            ttl: Time to live in seconds
            
        Returns:
            Success status
        """
        if ttl is None:
            ttl = self._get_default_ttl(cache_type)
        
        try:
            # Check memory limit
            size_bytes = self._estimate_size(data)
            if not self._check_memory_limit(size_bytes):
                self._evict_to_make_space(size_bytes)
            
            # Store in memory cache
            cache = self._caches.get(cache_type)
            if cache:
                cache[key] = data
            else:
                self._lru_cache[key] = data
            
            # Store in Redis if available
            if self._redis_client:
                self._set_in_redis(key, data, cache_type, ttl)
            
            # Update size tracking
            self._current_size_bytes += size_bytes
            
            with self._stats_lock:
                self._stats.item_count += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Cache set error: {str(e)}")
            with self._stats_lock:
                self._stats.error_count += 1
            return False
    
    def delete(self, key: str, cache_type: Optional[CacheType] = None) -> bool:
        """
        Delete data from cache.
        
        Args:
            key: Cache key
            cache_type: Type of cache (None for all)
            
        Returns:
            Success status
        """
        deleted = False
        
        if cache_type:
            # Delete from specific cache
            cache = self._caches.get(cache_type)
            if cache and key in cache:
                del cache[key]
                deleted = True
        else:
            # Delete from all caches
            for cache in self._caches.values():
                if key in cache:
                    del cache[key]
                    deleted = True
            
            if key in self._lru_cache:
                del self._lru_cache[key]
                deleted = True
        
        # Delete from Redis
        if self._redis_client:
            redis_key = self._make_redis_key(key, cache_type)
            self._redis_client.delete(redis_key)
        
        if deleted:
            with self._stats_lock:
                self._stats.item_count -= 1
        
        return deleted
    
    def clear(self, cache_type: Optional[CacheType] = None) -> None:
        """
        Clear cache.
        
        Args:
            cache_type: Type of cache to clear (None for all)
        """
        if cache_type:
            cache = self._caches.get(cache_type)
            if cache:
                cache.clear()
        else:
            for cache in self._caches.values():
                cache.clear()
            self._lru_cache.clear()
        
        # Clear Redis
        if self._redis_client and not cache_type:
            pattern = f"{REDIS_KEY_PREFIX}*"
            for key in self._redis_client.scan_iter(match=pattern):
                self._redis_client.delete(key)
        
        self._current_size_bytes = 0
        with self._stats_lock:
            self._stats.item_count = 0
    
    # ==========================================================================
    # PUBLIC METHODS - SPECIALIZED CACHING
    # ==========================================================================
    def cache_quote(self, symbol: str, quote_data: Dict[str, Any]) -> bool:
        """
        Cache quote data with appropriate TTL.
        
        Args:
            symbol: Stock/option symbol
            quote_data: Quote data dictionary
            
        Returns:
            Success status
        """
        key = f"quote:{symbol}"
        return self.set(key, quote_data, CacheType.QUOTE, QUOTE_TTL)
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get cached quote data.
        
        Args:
            symbol: Stock/option symbol
            
        Returns:
            Quote data or None
        """
        key = f"quote:{symbol}"
        return self.get(key, CacheType.QUOTE)
    
    def cache_option_chain(self, underlying: str, expiry: str, 
                          chain_data: pd.DataFrame) -> bool:
        """
        Cache option chain data.
        
        Args:
            underlying: Underlying symbol
            expiry: Expiration date
            chain_data: Option chain DataFrame
            
        Returns:
            Success status
        """
        key = f"chain:{underlying}:{expiry}"
        return self.set(key, chain_data, CacheType.OPTION_CHAIN, OPTION_CHAIN_TTL)
    
    def get_option_chain(self, underlying: str, expiry: str) -> Optional[pd.DataFrame]:
        """
        Get cached option chain.
        
        Args:
            underlying: Underlying symbol
            expiry: Expiration date
            
        Returns:
            Option chain DataFrame or None
        """
        key = f"chain:{underlying}:{expiry}"
        return self.get(key, CacheType.OPTION_CHAIN)
    
    def cache_historical_data(self, symbol: str, timeframe: str, 
                            data: pd.DataFrame) -> bool:
        """
        Cache historical price data.
        
        Args:
            symbol: Symbol
            timeframe: Timeframe (1m, 5m, 1h, 1d)
            data: Historical data DataFrame
            
        Returns:
            Success status
        """
        key = f"hist:{symbol}:{timeframe}"
        return self.set(key, data, CacheType.HISTORICAL, HISTORICAL_TTL)
    
    def get_historical_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get cached historical data.
        
        Args:
            symbol: Symbol
            timeframe: Timeframe
            
        Returns:
            Historical data DataFrame or None
        """
        key = f"hist:{symbol}:{timeframe}"
        return self.get(key, CacheType.HISTORICAL)
    
    # ==========================================================================
    # PUBLIC METHODS - CACHE MANAGEMENT
    # ==========================================================================
    def register_miss_callback(self, cache_type: CacheType, callback: Callable) -> None:
        """
        Register callback for cache misses.
        
        Args:
            cache_type: Cache type
            callback: Callback function(key, cache_type)
        """
        self._miss_callbacks[cache_type].append(callback)
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        with self._stats_lock:
            stats = CacheStats(
                total_requests=self._stats.total_requests,
                cache_hits=self._stats.cache_hits,
                cache_misses=self._stats.cache_misses,
                total_size_mb=self._current_size_bytes / 1024 / 1024,
                item_count=self._stats.item_count,
                eviction_count=self._stats.eviction_count,
                error_count=self._stats.error_count
            )
        return stats
    
    def warm_cache(self, symbols: List[str], data_types: List[CacheType]) -> None:
        """
        Warm cache with frequently used data.
        
        Args:
            symbols: List of symbols
            data_types: List of data types to cache
        """
        self.logger.info(f"Warming cache for {len(symbols)} symbols")
        
        for cache_type in data_types:
            for callback in self._miss_callbacks.get(cache_type, []):
                for symbol in symbols:
                    try:
                        # Generate appropriate key
                        if cache_type == CacheType.QUOTE:
                            key = f"quote:{symbol}"
                        elif cache_type == CacheType.HISTORICAL:
                            key = f"hist:{symbol}:1d"
                        else:
                            key = symbol
                        
                        # Trigger callback to load data
                        callback(key, cache_type)
                        
                    except Exception as e:
                        self.logger.error(f"Cache warming error for {symbol}: {str(e)}")
    
    # ==========================================================================
    # PRIVATE METHODS - REDIS OPERATIONS
    # ==========================================================================
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
            
            # Test connection
            client.ping()
            
            self.logger.info("Redis cache connected")
            return client
            
        except Exception as e:
            self.logger.warning(f"Redis connection failed: {str(e)}")
            return None
    
    def _make_redis_key(self, key: str, cache_type: Optional[CacheType]) -> str:
        """Generate Redis key"""
        if cache_type:
            return f"{REDIS_KEY_PREFIX}{cache_type.value}:{key}"
        return f"{REDIS_KEY_PREFIX}generic:{key}"
    
    def _get_from_redis(self, key: str, cache_type: CacheType) -> Optional[Any]:
        """Get data from Redis"""
        if not self._redis_client:
            return None
        
        try:
            redis_key = self._make_redis_key(key, cache_type)
            data = self._redis_client.get(redis_key)
            
            if data:
                # Decompress and unpickle
                data = gzip.decompress(data)
                return pickle.loads(data)
                
        except Exception as e:
            self.logger.error(f"Redis get error: {str(e)}")
            
        return None
    
    def _set_in_redis(self, key: str, data: Any, cache_type: CacheType, ttl: int) -> None:
        """Set data in Redis"""
        if not self._redis_client:
            return
        
        try:
            redis_key = self._make_redis_key(key, cache_type)
            
            # Pickle and compress
            pickled = pickle.dumps(data)
            compressed = gzip.compress(pickled, compresslevel=1)
            
            # Set with expiration
            self._redis_client.setex(
                redis_key,
                ttl + REDIS_EXPIRE_BUFFER,
                compressed
            )
            
        except Exception as e:
            self.logger.error(f"Redis set error: {str(e)}")
    
    # ==========================================================================
    # PRIVATE METHODS - MEMORY MANAGEMENT
    # ==========================================================================
    def _estimate_size(self, obj: Any) -> int:
        """Estimate object size in bytes"""
        try:
            if isinstance(obj, pd.DataFrame):
                return obj.memory_usage(deep=True).sum()
            elif isinstance(obj, dict):
                return len(pickle.dumps(obj))
            elif isinstance(obj, (list, tuple)):
                return sum(self._estimate_size(item) for item in obj)
            else:
                return len(pickle.dumps(obj))
        except:
            return 1024  # Default 1KB
    
    def _check_memory_limit(self, new_size: int) -> bool:
        """Check if adding new data would exceed memory limit"""
        total_size = self._current_size_bytes + new_size
        limit_bytes = self._memory_limit_mb * 1024 * 1024
        return total_size <= limit_bytes
    
    def _evict_to_make_space(self, required_bytes: int) -> None:
        """Evict old entries to make space"""
        self.logger.debug(f"Evicting entries to free {required_bytes} bytes")
        
        freed_bytes = 0
        evicted = 0
        
        # Start with custom cache (lowest priority)
        for cache_type in [CacheType.CUSTOM, CacheType.VOLUME_PROFILE, 
                          CacheType.HISTORICAL]:
            cache = self._caches[cache_type]
            
            # Get oldest entries
            while freed_bytes < required_bytes and len(cache) > 0:
                # TTLCache doesn't provide direct access to oldest
                # So we clear a portion
                to_remove = max(1, len(cache) // 4)
                for _ in range(to_remove):
                    if len(cache) > 0:
                        cache.popitem()
                        evicted += 1
                        freed_bytes += 1024  # Rough estimate
        
        self._current_size_bytes = max(0, self._current_size_bytes - freed_bytes)
        
        with self._stats_lock:
            self._stats.eviction_count += evicted
    
    # ==========================================================================
    # PRIVATE METHODS - STATISTICS
    # ==========================================================================
    def _record_hit(self) -> None:
        """Record cache hit"""
        with self._stats_lock:
            self._stats.cache_hits += 1
    
    def _record_miss(self) -> None:
        """Record cache miss"""
        with self._stats_lock:
            self._stats.cache_misses += 1
    
    def _trigger_miss_callbacks(self, key: str, cache_type: CacheType) -> None:
        """Trigger callbacks for cache miss"""
        for callback in self._miss_callbacks.get(cache_type, []):
            try:
                callback(key, cache_type)
            except Exception as e:
                self.logger.error(f"Cache miss callback error: {str(e)}")
    
    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _get_default_ttl(self, cache_type: CacheType) -> int:
        """Get default TTL for cache type"""
        ttl_map = {
            CacheType.QUOTE: QUOTE_TTL,
            CacheType.OPTION_CHAIN: OPTION_CHAIN_TTL,
            CacheType.HISTORICAL: HISTORICAL_TTL,
            CacheType.MARKET_INTERNALS: MARKET_INTERNALS_TTL,
            CacheType.VOLUME_PROFILE: DEFAULT_TTL,
            CacheType.CUSTOM: DEFAULT_TTL
        }
        return ttl_map.get(cache_type, DEFAULT_TTL)
    
    def _cleanup_loop(self) -> None:
        """Background cleanup thread"""
        while self._running:
            try:
                time.sleep(CLEANUP_INTERVAL)
                
                # Log statistics
                stats = self.get_stats()
                self.logger.info(
                    f"Cache stats - Hit rate: {stats.hit_rate:.2%}, "
                    f"Items: {stats.item_count}, "
                    f"Size: {stats.total_size_mb:.1f}MB"
                )
                
                # Clean expired entries (handled by TTLCache automatically)
                
            except Exception as e:
                self.logger.error(f"Cleanup error: {str(e)}")
    
    def shutdown(self) -> None:
        """Shutdown cache and cleanup"""
        self.logger.info("Shutting down MarketDataCache")
        
        self._running = False
        
        if self._redis_client:
            self._redis_client.close()
        
        self.clear()
        
        self.logger.info("MarketDataCache shutdown complete")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_cache_instance: Optional[MarketDataCache] = None

def get_market_data_cache() -> MarketDataCache:
    """
    Get singleton instance of market data cache.
    
    Returns:
        MarketDataCache instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = MarketDataCache()
    return _cache_instance

# ==============================================================================
# CACHE DECORATORS
# ==============================================================================
def cache_result(cache_type: CacheType = CacheType.CUSTOM, ttl: Optional[int] = None):
    """
    Decorator to cache function results.
    
    Args:
        cache_type: Type of cache
        ttl: Time to live
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cache = get_market_data_cache()
            result = cache.get(key, cache_type)
            
            if result is None:
                # Cache miss - call function
                result = func(*args, **kwargs)
                
                # Cache the result
                if result is not None:
                    cache.set(key, result, cache_type, ttl)
            
            return result
        
        return wrapper
    return decorator

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test the cache
    cache = get_market_data_cache()
    
    # Test basic operations
    print("Testing MarketDataCache...")
    
    # Set and get
    cache.set("test_key", {"value": 123}, CacheType.CUSTOM)
    result = cache.get("test_key", CacheType.CUSTOM)
    print(f"Cache get result: {result}")
    
    # Test quote caching
    cache.cache_quote("SPY", {
        "bid": 450.10,
        "ask": 450.15,
        "last": 450.12,
        "volume": 1000000
    })
    
    quote = cache.get_quote("SPY")
    print(f"Cached quote: {quote}")
    
    # Test statistics
    stats = cache.get_stats()
    print(f"\nCache statistics:")
    print(f"  Total requests: {stats.total_requests}")
    print(f"  Cache hits: {stats.cache_hits}")
    print(f"  Hit rate: {stats.hit_rate:.2%}")
    print(f"  Items: {stats.item_count}")
    print(f"  Size: {stats.total_size_mb:.2f} MB")
    
    # Cleanup
    cache.shutdown()
