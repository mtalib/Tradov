#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderH_Storage
Module: SpyderH03_MarketDataCache.py
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
import time
import json
from typing import Any, TypeVar
from dataclasses import dataclass, field
from collections import OrderedDict
from enum import Enum
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    LOCAL_IMPORTS = True
except ImportError:
    import logging
    SpyderLogger = type('SpyderLogger', (), {
        'get_logger': staticmethod(lambda name: logging.getLogger(name))
    })()
    LOCAL_IMPORTS = False

# ==============================================================================
# TYPE VARIABLES
# ==============================================================================
T = TypeVar('T')

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_TTL_SECONDS = 60  # 1 minute default TTL
DEFAULT_MAX_SIZE = 10000  # Maximum cache entries
CLEANUP_INTERVAL_SECONDS = 30  # Cleanup interval for expired entries

# TTL presets for different data types
TTL_PRESETS = {
    'quote': 5,           # Quotes expire in 5 seconds
    'bar_1m': 60,         # 1-minute bars expire in 60 seconds
    'bar_5m': 300,        # 5-minute bars expire in 5 minutes
    'bar_1d': 3600,       # Daily bars expire in 1 hour
    'option_chain': 30,   # Option chains expire in 30 seconds
    'greeks': 30,         # Greeks expire in 30 seconds
    'market_status': 60,  # Market status expires in 1 minute
    'historical': 3600,   # Historical data expires in 1 hour
}


# ==============================================================================
# ENUMS
# ==============================================================================
class EvictionPolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"       # Least Recently Used
    LFU = "lfu"       # Least Frequently Used
    FIFO = "fifo"     # First In First Out
    TTL = "ttl"       # Time To Live only


class CacheDataType(Enum):
    """Types of cached market data."""
    QUOTE = "quote"
    BAR = "bar"
    OPTION_CHAIN = "option_chain"
    GREEKS = "greeks"
    MARKET_STATUS = "market_status"
    HISTORICAL = "historical"
    CUSTOM = "custom"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class CacheEntry[T]:
    """Cache entry with metadata."""
    key: str
    value: T
    data_type: CacheDataType
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() > self.expires_at

    def touch(self) -> None:
        """Update access metadata."""
        self.access_count += 1
        self.last_accessed = time.time()


@dataclass
class CacheStatistics:
    """Cache performance statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    current_size: int = 0
    max_size: int = 0
    memory_bytes: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# ==============================================================================
# MARKET DATA CACHE
# ==============================================================================
class MarketDataCache:
    """
    High-performance market data cache with TTL and eviction support.

    Provides efficient caching for market data with automatic expiration,
    configurable eviction policies, and comprehensive statistics tracking.
    """

    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        default_ttl: int = DEFAULT_TTL_SECONDS,
        eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
        auto_cleanup: bool = True
    ):
        """
        Initialize market data cache.

        Args:
            max_size: Maximum number of cache entries
            default_ttl: Default time-to-live in seconds
            eviction_policy: Eviction policy for full cache
            auto_cleanup: Enable automatic cleanup of expired entries
        """
        self.logger = SpyderLogger.get_logger(__name__)

        # Cache configuration
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.eviction_policy = eviction_policy

        # Cache storage
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # Statistics
        self._stats = CacheStatistics(max_size=max_size)

        # Cleanup thread
        self._cleanup_running = False
        self._cleanup_event = threading.Event()
        self._cleanup_thread = None
        if auto_cleanup:
            self._start_cleanup_thread()

        self.logger.info(
            f"MarketDataCache initialized: max_size={max_size}, "
            f"ttl={default_ttl}s, policy={eviction_policy.value}"
        )

    def _start_cleanup_thread(self) -> None:
        """Start background cleanup thread."""
        self._cleanup_running = True
        self._cleanup_event.clear()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="MarketDataCache-Cleanup"
        )
        self._cleanup_thread.start()

    def _cleanup_loop(self) -> None:
        """Background cleanup loop for expired entries."""
        while not self._cleanup_event.wait(CLEANUP_INTERVAL_SECONDS):
            self._remove_expired()

    def _remove_expired(self) -> int:
        """Remove all expired entries."""
        removed = 0
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
                self._stats.expirations += 1

        if removed > 0:
            self.logger.debug("Removed %s expired cache entries", removed)
        return removed

    def _generate_key(
        self,
        symbol: str,
        data_type: CacheDataType,
        suffix: str = ""
    ) -> str:
        """Generate a cache key."""
        key = f"{data_type.value}:{symbol}"
        if suffix:
            key += f":{suffix}"
        return key

    def _get_ttl(self, data_type: CacheDataType) -> int:
        """Get TTL for a data type."""
        return TTL_PRESETS.get(data_type.value, self.default_ttl)

    def _evict_if_needed(self) -> None:
        """Evict entries if cache is full."""
        while len(self._cache) >= self.max_size:
            self._evict_one()

    def _evict_one(self) -> None:
        """Evict one entry based on eviction policy."""
        if not self._cache:
            return

        if self.eviction_policy == EvictionPolicy.LRU:
            # Remove least recently used (first item in OrderedDict)
            key = next(iter(self._cache))
        elif self.eviction_policy == EvictionPolicy.LFU:
            # Remove least frequently used
            key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].access_count
            )
        elif self.eviction_policy == EvictionPolicy.FIFO:
            # Remove first inserted
            key = next(iter(self._cache))
        elif self.eviction_policy == EvictionPolicy.TTL:
            # Remove entry closest to expiration
            key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].expires_at
            )
        else:
            key = next(iter(self._cache))

        del self._cache[key]
        self._stats.evictions += 1
        self.logger.debug("Evicted cache entry: %s", key)

    def set(
        self,
        key: str,
        value: Any,
        data_type: CacheDataType = CacheDataType.CUSTOM,
        ttl: int | None = None
    ) -> None:
        """
        Store a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            data_type: Type of data being cached
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        with self._lock:
            # Remove entry if it exists (to update OrderedDict position)
            if key in self._cache:
                del self._cache[key]
            else:
                self._evict_if_needed()

            # Calculate TTL
            if ttl is None:
                ttl = self._get_ttl(data_type)

            # Create entry
            entry = CacheEntry(
                key=key,
                value=value,
                data_type=data_type,
                expires_at=time.time() + ttl,
                size_bytes=self._estimate_size(value)
            )

            self._cache[key] = entry
            self._stats.current_size = len(self._cache)
            self._stats.memory_bytes += entry.size_bytes

    def get(
        self,
        key: str,
        default: Any = None
    ) -> Any:
        """
        Retrieve a value from the cache.

        Args:
            key: Cache key
            default: Default value if key not found or expired

        Returns:
            Cached value or default
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return default

            if entry.is_expired():
                del self._cache[key]
                self._stats.misses += 1
                self._stats.expirations += 1
                return default

            # Update access metadata
            entry.touch()

            # Move to end for LRU (most recently used)
            if self.eviction_policy == EvictionPolicy.LRU:
                self._cache.move_to_end(key)

            self._stats.hits += 1
            return entry.value

    def get_quote(self, symbol: str) -> dict[str, Any] | None:
        """
        Get cached quote for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Quote data or None
        """
        key = self._generate_key(symbol, CacheDataType.QUOTE)
        return self.get(key)

    def set_quote(self, symbol: str, quote: dict[str, Any]) -> None:
        """
        Cache a quote for a symbol.

        Args:
            symbol: Trading symbol
            quote: Quote data
        """
        key = self._generate_key(symbol, CacheDataType.QUOTE)
        self.set(key, quote, CacheDataType.QUOTE)

    def get_bar(
        self,
        symbol: str,
        timeframe: str = "1m"
    ) -> dict[str, Any] | None:
        """
        Get cached bar data for a symbol.

        Args:
            symbol: Trading symbol
            timeframe: Bar timeframe

        Returns:
            Bar data or None
        """
        key = self._generate_key(symbol, CacheDataType.BAR, timeframe)
        return self.get(key)

    def set_bar(
        self,
        symbol: str,
        bar: dict[str, Any],
        timeframe: str = "1m"
    ) -> None:
        """
        Cache bar data for a symbol.

        Args:
            symbol: Trading symbol
            bar: Bar data
            timeframe: Bar timeframe
        """
        key = self._generate_key(symbol, CacheDataType.BAR, timeframe)
        ttl = TTL_PRESETS.get(f"bar_{timeframe}", self.default_ttl)
        self.set(key, bar, CacheDataType.BAR, ttl)

    def get_option_chain(
        self,
        underlying: str,
        expiration: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get cached option chain.

        Args:
            underlying: Underlying symbol
            expiration: Optional expiration date filter

        Returns:
            Option chain data or None
        """
        suffix = expiration if expiration else "all"
        key = self._generate_key(underlying, CacheDataType.OPTION_CHAIN, suffix)
        return self.get(key)

    def set_option_chain(
        self,
        underlying: str,
        chain: dict[str, Any],
        expiration: str | None = None
    ) -> None:
        """
        Cache option chain data.

        Args:
            underlying: Underlying symbol
            chain: Option chain data
            expiration: Optional expiration date
        """
        suffix = expiration if expiration else "all"
        key = self._generate_key(underlying, CacheDataType.OPTION_CHAIN, suffix)
        self.set(key, chain, CacheDataType.OPTION_CHAIN)

    def get_greeks(self, option_symbol: str) -> dict[str, float] | None:
        """
        Get cached Greeks for an option.

        Args:
            option_symbol: Option symbol

        Returns:
            Greeks data or None
        """
        key = self._generate_key(option_symbol, CacheDataType.GREEKS)
        return self.get(key)

    def set_greeks(
        self,
        option_symbol: str,
        greeks: dict[str, float]
    ) -> None:
        """
        Cache Greeks for an option.

        Args:
            option_symbol: Option symbol
            greeks: Greeks data
        """
        key = self._generate_key(option_symbol, CacheDataType.GREEKS)
        self.set(key, greeks, CacheDataType.GREEKS)

    def get_historical(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = "1d"
    ) -> list[dict[str, Any]] | None:
        """
        Get cached historical data.

        Args:
            symbol: Trading symbol
            start_date: Start date string
            end_date: End date string
            timeframe: Data timeframe

        Returns:
            Historical bars or None
        """
        suffix = f"{start_date}_{end_date}_{timeframe}"
        key = self._generate_key(symbol, CacheDataType.HISTORICAL, suffix)
        return self.get(key)

    def set_historical(
        self,
        symbol: str,
        data: list[dict[str, Any]],
        start_date: str,
        end_date: str,
        timeframe: str = "1d"
    ) -> None:
        """
        Cache historical data.

        Args:
            symbol: Trading symbol
            data: Historical bars
            start_date: Start date string
            end_date: End date string
            timeframe: Data timeframe
        """
        suffix = f"{start_date}_{end_date}_{timeframe}"
        key = self._generate_key(symbol, CacheDataType.HISTORICAL, suffix)
        self.set(key, data, CacheDataType.HISTORICAL)

    def invalidate(self, key: str) -> bool:
        """
        Invalidate (remove) a cache entry.

        Args:
            key: Cache key to invalidate

        Returns:
            True if entry was removed
        """
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                self._stats.memory_bytes -= entry.size_bytes
                del self._cache[key]
                self._stats.current_size = len(self._cache)
                return True
            return False

    def invalidate_symbol(self, symbol: str) -> int:
        """
        Invalidate all cache entries for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Number of entries removed
        """
        with self._lock:
            keys_to_remove = [
                key for key in self._cache
                if f":{symbol}" in key or f":{symbol}:" in key
            ]
            for key in keys_to_remove:
                entry = self._cache[key]
                self._stats.memory_bytes -= entry.size_bytes
                del self._cache[key]

            self._stats.current_size = len(self._cache)
            return len(keys_to_remove)

    def invalidate_type(self, data_type: CacheDataType) -> int:
        """
        Invalidate all entries of a specific data type.

        Args:
            data_type: Type of data to invalidate

        Returns:
            Number of entries removed
        """
        with self._lock:
            keys_to_remove = [
                key for key, entry in self._cache.items()
                if entry.data_type == data_type
            ]
            for key in keys_to_remove:
                entry = self._cache[key]
                self._stats.memory_bytes -= entry.size_bytes
                del self._cache[key]

            self._stats.current_size = len(self._cache)
            return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._stats.current_size = 0
            self._stats.memory_bytes = 0
            self.logger.info("Cache cleared")

    def contains(self, key: str) -> bool:
        """
        Check if key exists and is not expired.

        Args:
            key: Cache key

        Returns:
            True if key exists and is valid
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._cache[key]
                self._stats.expirations += 1
                return False
            return True

    def get_statistics(self) -> CacheStatistics:
        """
        Get cache statistics.

        Returns:
            CacheStatistics object
        """
        with self._lock:
            self._stats.current_size = len(self._cache)
            return CacheStatistics(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                expirations=self._stats.expirations,
                current_size=self._stats.current_size,
                max_size=self._stats.max_size,
                memory_bytes=self._stats.memory_bytes
            )

    def get_keys(self, pattern: str | None = None) -> list[str]:
        """
        Get all cache keys, optionally filtered by pattern.

        Args:
            pattern: Optional pattern to filter keys

        Returns:
            List of cache keys
        """
        with self._lock:
            if pattern:
                return [key for key in self._cache if pattern in key]
            return list(self._cache.keys())

    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of a value in bytes."""
        try:
            if isinstance(value, (dict, list)):
                return len(json.dumps(value))
            elif isinstance(value, str):
                return len(value)
            elif isinstance(value, (int, float)):
                return 8
            elif hasattr(value, '__sizeof__'):
                return value.__sizeof__()
            else:
                return len(str(value))
        except Exception:
            return 100  # Default estimate

    def shutdown(self) -> None:
        """Shutdown the cache and cleanup thread."""
        self._cleanup_running = False
        self._cleanup_event.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        self.clear()
        self.logger.info("MarketDataCache shutdown complete")

    def __len__(self) -> int:
        """Return number of entries in cache."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if key is in cache."""
        return self.contains(key)


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    "MarketDataCache",
    "CacheEntry",
    "CacheStatistics",
    "CacheDataType",
    "EvictionPolicy",
]
