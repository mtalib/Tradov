#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB33_APIFloodProtection.py
Purpose: Comprehensive API flood protection to prevent Gateway destabilization
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-01 Time: 12:00:00

Module Description:
    This module provides comprehensive flood protection for IB Gateway API calls.
    Prevents excessive reqMktData, reqAccountSummary, and other API calls that
    can destabilize the Gateway and cause disconnections.

    Features:
    - Global rate limiting for all API request types
    - Request deduplication to prevent duplicate subscriptions
    - Burst protection with token bucket algorithm
    - Per-symbol and per-request-type rate limits
    - Automatic request queuing when limits reached
    - Real-time monitoring and metrics
"""

import threading
import time
import logging
from collections import deque, defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Set, List, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid

# ==============================================================================
# CONSTANTS
# ==============================================================================

# IBKR API Rate Limits (Conservative - actual limits may be higher)
API_RATE_LIMITS = {
    "market_data": {
        "limit": 50,  # Max 50 market data requests per window
        "window": 1.0,  # 1 second window
        "burst": 10,  # Allow burst of 10
    },
    "market_data_cancel": {
        "limit": 50,
        "window": 1.0,
        "burst": 10,
    },
    "account_updates": {
        "limit": 10,
        "window": 1.0,
        "burst": 3,
    },
    "historical_data": {
        "limit": 60,
        "window": 600.0,  # 10 minutes
        "burst": 5,
    },
    "orders": {
        "limit": 50,
        "window": 1.0,
        "burst": 10,
    },
}

# Global request limits
MAX_CONCURRENT_MARKET_DATA_SUBSCRIPTIONS = 100
MAX_REQUESTS_PER_SECOND_GLOBAL = 50
MAX_IDENTICAL_REQUESTS_PER_MINUTE = 5

# Deduplication settings
DEDUP_WINDOW_SECONDS = 60  # Consider requests duplicate within 60 seconds
SUBSCRIPTION_CACHE_TTL = 300  # Keep subscription cache for 5 minutes

# Monitoring
METRICS_WINDOW = 300  # 5 minutes metrics window
ALERT_THRESHOLD_VIOLATIONS = 10  # Alert after 10 violations

# ==============================================================================
# ENUMS
# ==============================================================================


class APIRequestType(Enum):
    """Types of API requests"""

    MARKET_DATA = "market_data"
    MARKET_DATA_CANCEL = "market_data_cancel"
    ACCOUNT_UPDATES = "account_updates"
    HISTORICAL_DATA = "historical_data"
    ORDERS = "orders"
    POSITIONS = "positions"
    ACCOUNT_SUMMARY = "account_summary"
    CONTRACT_DETAILS = "contract_details"


class FloodProtectionAction(Enum):
    """Actions taken by flood protection"""

    ALLOWED = "allowed"
    QUEUED = "queued"
    REJECTED = "rejected"
    DEDUPLICATED = "deduplicated"


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class APIRequest:
    """Represents an API request"""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_type: APIRequestType = APIRequestType.MARKET_DATA
    symbol: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    callback: Optional[Callable] = None

    def __hash__(self):
        """Hash for deduplication"""
        return hash(
            (self.request_type.value, self.symbol, tuple(sorted(self.params.items())))
        )

    def matches(self, other: "APIRequest") -> bool:
        """Check if this request matches another (for deduplication)"""
        return (
            self.request_type == other.request_type
            and self.symbol == other.symbol
            and self.params == other.params
        )


@dataclass
class RequestMetrics:
    """Metrics for API requests"""

    total_requests: int = 0
    allowed_requests: int = 0
    queued_requests: int = 0
    rejected_requests: int = 0
    deduplicated_requests: int = 0
    rate_limit_violations: int = 0
    last_violation: Optional[datetime] = None
    request_history: deque = field(default_factory=lambda: deque(maxlen=1000))


@dataclass
class SubscriptionRecord:
    """Record of an active subscription"""

    symbol: str
    request_id: int
    request_type: APIRequestType
    timestamp: datetime
    params: Dict[str, Any] = field(default_factory=dict)
    last_update: Optional[datetime] = None


# ==============================================================================
# TOKEN BUCKET RATE LIMITER
# ==============================================================================


class TokenBucket:
    """Token bucket algorithm for rate limiting with burst support"""

    def __init__(self, rate: float, capacity: int, burst: int = 0):
        """
        Initialize token bucket.

        Args:
            rate: Tokens per second
            capacity: Maximum tokens
            burst: Burst allowance
        """
        self.rate = rate
        self.capacity = capacity
        self.burst = burst
        self.tokens = capacity + burst  # Start with full bucket + burst
        self.last_update = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens available, False otherwise
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Add tokens based on elapsed time
            self.tokens = min(
                self.capacity + self.burst, self.tokens + elapsed * self.rate
            )
            self.last_update = now

            # Try to consume
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_wait_time(self, tokens: int = 1) -> float:
        """Get time to wait for tokens to be available"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            available = min(
                self.capacity + self.burst, self.tokens + elapsed * self.rate
            )

            if available >= tokens:
                return 0.0

            needed = tokens - available
            return needed / self.rate


# ==============================================================================
# MAIN FLOOD PROTECTION CLASS
# ==============================================================================


class APIFloodProtection:
    """
    Comprehensive API flood protection system.

    Prevents excessive API calls from destabilizing IB Gateway through:
    - Rate limiting per request type
    - Global rate limiting
    - Request deduplication
    - Burst protection
    - Request queuing
    """

    def __init__(self):
        """Initialize flood protection"""
        self.logger = logging.getLogger(__name__)

        # Token buckets for each request type
        self.rate_limiters: Dict[APIRequestType, TokenBucket] = {}
        for req_type, config in API_RATE_LIMITS.items():
            api_type = APIRequestType(req_type)
            self.rate_limiters[api_type] = TokenBucket(
                rate=config["limit"] / config["window"],
                capacity=config["limit"],
                burst=config["burst"],
            )

        # Global rate limiter
        self.global_limiter = TokenBucket(
            rate=MAX_REQUESTS_PER_SECOND_GLOBAL,
            capacity=MAX_REQUESTS_PER_SECOND_GLOBAL,
            burst=10,
        )

        # Active subscriptions tracking
        self.active_subscriptions: Dict[str, SubscriptionRecord] = {}
        self.subscription_lock = threading.Lock()

        # Request deduplication
        self.recent_requests: deque = deque(maxlen=10000)
        self.request_times: Dict[int, datetime] = {}
        self.dedup_lock = threading.Lock()

        # Metrics
        self.metrics = RequestMetrics()
        self.per_type_metrics: Dict[APIRequestType, RequestMetrics] = defaultdict(
            RequestMetrics
        )

        # Request queue for when limits are reached
        self.request_queue: deque = deque(maxlen=1000)
        self.queue_lock = threading.Lock()

        self.logger.info("🛡️ API Flood Protection initialized")

    # ==========================================================================
    # PUBLIC API - REQUEST CHECKING
    # ==========================================================================

    def check_request(self, request: APIRequest) -> Tuple[FloodProtectionAction, str]:
        """
        Check if request is allowed.

        Args:
            request: API request to check

        Returns:
            Tuple of (action, reason)
        """
        self.metrics.total_requests += 1
        self.per_type_metrics[request.request_type].total_requests += 1

        # Check if duplicate subscription
        if request.request_type == APIRequestType.MARKET_DATA:
            if self._is_duplicate_subscription(request):
                self.metrics.deduplicated_requests += 1
                self.per_type_metrics[request.request_type].deduplicated_requests += 1
                return (
                    FloodProtectionAction.DEDUPLICATED,
                    f"Already subscribed to {request.symbol}",
                )

        # Check if duplicate request (within dedup window)
        if self._is_duplicate_request(request):
            self.metrics.deduplicated_requests += 1
            self.per_type_metrics[request.request_type].deduplicated_requests += 1
            return (
                FloodProtectionAction.DEDUPLICATED,
                "Duplicate request within deduplication window",
            )

        # Check global rate limit
        if not self.global_limiter.consume():
            wait_time = self.global_limiter.get_wait_time()
            self.metrics.rate_limit_violations += 1
            self.metrics.last_violation = datetime.now()

            if wait_time < 1.0:  # Queue if wait is short
                self.metrics.queued_requests += 1
                self.per_type_metrics[request.request_type].queued_requests += 1
                self._queue_request(request)
                return (
                    FloodProtectionAction.QUEUED,
                    f"Global rate limit reached, queued (wait: {wait_time:.2f}s)",
                )
            else:
                self.metrics.rejected_requests += 1
                self.per_type_metrics[request.request_type].rejected_requests += 1
                return (
                    FloodProtectionAction.REJECTED,
                    f"Global rate limit exceeded (wait: {wait_time:.2f}s)",
                )

        # Check request-type specific rate limit
        limiter = self.rate_limiters.get(request.request_type)
        if limiter and not limiter.consume():
            wait_time = limiter.get_wait_time()
            self.metrics.rate_limit_violations += 1
            self.metrics.last_violation = datetime.now()

            if wait_time < 1.0:  # Queue if wait is short
                self.metrics.queued_requests += 1
                self.per_type_metrics[request.request_type].queued_requests += 1
                self._queue_request(request)
                return (
                    FloodProtectionAction.QUEUED,
                    f"{request.request_type.value} rate limit reached, queued",
                )
            else:
                self.metrics.rejected_requests += 1
                self.per_type_metrics[request.request_type].rejected_requests += 1
                return (
                    FloodProtectionAction.REJECTED,
                    f"{request.request_type.value} rate limit exceeded",
                )

        # Request is allowed
        self.metrics.allowed_requests += 1
        self.per_type_metrics[request.request_type].allowed_requests += 1
        self._record_request(request)

        return (FloodProtectionAction.ALLOWED, "Request approved")

    def register_subscription(
        self,
        symbol: str,
        request_id: int,
        request_type: APIRequestType = APIRequestType.MARKET_DATA,
        params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Register an active subscription.

        Args:
            symbol: Trading symbol
            request_id: Request ID from IB
            request_type: Type of request
            params: Additional parameters

        Returns:
            True if registered, False if duplicate
        """
        with self.subscription_lock:
            if symbol in self.active_subscriptions:
                self.logger.debug(f"Subscription already exists for {symbol}")
                return False

            self.active_subscriptions[symbol] = SubscriptionRecord(
                symbol=symbol,
                request_id=request_id,
                request_type=request_type,
                timestamp=datetime.now(),
                params=params or {},
            )

            self.logger.debug(
                f"📊 Registered subscription: {symbol} (req_id: {request_id})"
            )
            return True

    def unregister_subscription(self, symbol: str) -> bool:
        """
        Unregister a subscription.

        Args:
            symbol: Trading symbol

        Returns:
            True if unregistered, False if not found
        """
        with self.subscription_lock:
            if symbol in self.active_subscriptions:
                del self.active_subscriptions[symbol]
                self.logger.debug(f"📊 Unregistered subscription: {symbol}")
                return True
            return False

    def get_active_subscriptions(self) -> List[str]:
        """Get list of active subscriptions"""
        with self.subscription_lock:
            return list(self.active_subscriptions.keys())

    def is_subscribed(self, symbol: str) -> bool:
        """Check if already subscribed to a symbol"""
        with self.subscription_lock:
            return symbol in self.active_subscriptions

    # ==========================================================================
    # PRIVATE METHODS - DEDUPLICATION
    # ==========================================================================

    def _is_duplicate_subscription(self, request: APIRequest) -> bool:
        """Check if subscription already exists"""
        if not request.symbol:
            return False

        with self.subscription_lock:
            return request.symbol in self.active_subscriptions

    def _is_duplicate_request(self, request: APIRequest) -> bool:
        """Check if request is duplicate within dedup window"""
        with self.dedup_lock:
            now = datetime.now()
            request_hash = hash(request)

            # Clean old requests
            cutoff = now - timedelta(seconds=DEDUP_WINDOW_SECONDS)
            self.request_times = {
                h: t for h, t in self.request_times.items() if t > cutoff
            }

            # Check if duplicate
            if request_hash in self.request_times:
                last_time = self.request_times[request_hash]
                if (now - last_time).total_seconds() < DEDUP_WINDOW_SECONDS:
                    return True

            # Not a duplicate, record it
            self.request_times[request_hash] = now
            return False

    def _record_request(self, request: APIRequest):
        """Record request in history"""
        with self.dedup_lock:
            self.recent_requests.append(request)
            self.metrics.request_history.append(
                {
                    "timestamp": request.timestamp,
                    "type": request.request_type.value,
                    "symbol": request.symbol,
                }
            )

    # ==========================================================================
    # PRIVATE METHODS - QUEUING
    # ==========================================================================

    def _queue_request(self, request: APIRequest):
        """Queue request for later processing"""
        with self.queue_lock:
            if len(self.request_queue) < 1000:
                self.request_queue.append(request)
                self.logger.debug(
                    f"⏳ Queued request: {request.request_type.value} "
                    f"for {request.symbol}"
                )
            else:
                self.logger.warning("⚠️ Request queue full, rejecting request")

    def process_queued_requests(self) -> int:
        """
        Process queued requests.

        Returns:
            Number of requests processed
        """
        processed = 0

        with self.queue_lock:
            while self.request_queue:
                request = self.request_queue.popleft()

                # Try to process
                action, reason = self.check_request(request)
                if action == FloodProtectionAction.ALLOWED:
                    if request.callback:
                        try:
                            request.callback()
                        except Exception as e:
                            self.logger.error(f"Error processing queued request: {e}")
                    processed += 1
                elif action != FloodProtectionAction.QUEUED:
                    # If still can't process and not queued again, give up
                    break

        if processed > 0:
            self.logger.info(f"✅ Processed {processed} queued requests")

        return processed

    # ==========================================================================
    # MONITORING AND METRICS
    # ==========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """Get flood protection metrics"""
        with self.subscription_lock:
            active_subs = len(self.active_subscriptions)

        with self.queue_lock:
            queue_size = len(self.request_queue)

        return {
            "total_requests": self.metrics.total_requests,
            "allowed_requests": self.metrics.allowed_requests,
            "queued_requests": self.metrics.queued_requests,
            "rejected_requests": self.metrics.rejected_requests,
            "deduplicated_requests": self.metrics.deduplicated_requests,
            "rate_limit_violations": self.metrics.rate_limit_violations,
            "last_violation": self.metrics.last_violation,
            "active_subscriptions": active_subs,
            "queue_size": queue_size,
            "allow_rate": (
                self.metrics.allowed_requests / self.metrics.total_requests * 100
                if self.metrics.total_requests > 0
                else 0
            ),
        }

    def get_subscription_count(self) -> int:
        """Get number of active subscriptions"""
        with self.subscription_lock:
            return len(self.active_subscriptions)

    def get_status_summary(self) -> str:
        """Get human-readable status summary"""
        metrics = self.get_metrics()

        return f"""
🛡️ API Flood Protection Status
═══════════════════════════════════════════════════════════
Total Requests:     {metrics['total_requests']:,}
✅ Allowed:         {metrics['allowed_requests']:,} ({metrics['allow_rate']:.1f}%)
⏳ Queued:          {metrics['queued_requests']:,}
❌ Rejected:        {metrics['rejected_requests']:,}
🔄 Deduplicated:    {metrics['deduplicated_requests']:,}
⚠️  Rate Violations: {metrics['rate_limit_violations']:,}
📊 Active Subs:     {metrics['active_subscriptions']:,} / {MAX_CONCURRENT_MARKET_DATA_SUBSCRIPTIONS}
📋 Queue Size:      {metrics['queue_size']:,}
═══════════════════════════════════════════════════════════
        """.strip()

    def reset_metrics(self):
        """Reset metrics"""
        self.metrics = RequestMetrics()
        self.per_type_metrics.clear()
        self.logger.info("📊 Metrics reset")


# ==============================================================================
# SINGLETON INSTANCE
# ==============================================================================

_flood_protection_instance: Optional[APIFloodProtection] = None
_instance_lock = threading.Lock()


def get_flood_protection() -> APIFloodProtection:
    """Get singleton flood protection instance"""
    global _flood_protection_instance

    with _instance_lock:
        if _flood_protection_instance is None:
            _flood_protection_instance = APIFloodProtection()
        return _flood_protection_instance


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("SPYDER API Flood Protection System")
    print("=" * 70)
    print()

    # Test flood protection
    protection = get_flood_protection()

    print("Testing rate limiting...")
    allowed = 0
    rejected = 0
    deduplicated = 0

    # Simulate rapid requests
    for i in range(200):
        request = APIRequest(
            request_type=APIRequestType.MARKET_DATA,
            symbol="SPY" if i % 10 == 0 else f"TEST{i}",  # Some duplicates
            params={"test": True},
        )

        action, reason = protection.check_request(request)

        if action == FloodProtectionAction.ALLOWED:
            allowed += 1
        elif action == FloodProtectionAction.REJECTED:
            rejected += 1
        elif action == FloodProtectionAction.DEDUPLICATED:
            deduplicated += 1

    print(f"\nResults after 200 requests:")
    print(f"  ✅ Allowed:      {allowed}")
    print(f"  ❌ Rejected:     {rejected}")
    print(f"  🔄 Deduplicated: {deduplicated}")
    print()
    print(protection.get_status_summary())
