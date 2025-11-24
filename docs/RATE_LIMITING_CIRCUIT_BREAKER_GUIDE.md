

# Rate Limiting & Circuit Breaker Integration Guide

## Overview

This guide shows how to integrate rate limiting and circuit breakers into the Spyder trading system for resilient API calls.

---

## Components

### 1. Rate Limiter (`SpyderU40_RateLimiter.py`)
**Purpose**: Prevent hitting API rate limits
**Algorithm**: Token bucket
**Use for**: Tradier, Polygon, any rate-limited API

### 2. Circuit Breaker (`SpyderU41_CircuitBreaker.py`)
**Purpose**: Prevent cascading failures
**Pattern**: CLOSED → OPEN → HALF_OPEN → CLOSED
**Use for**: Any external service that can fail

---

## Quick Start

### Rate Limiting Example

```python
from SpyderU_Utilities.SpyderU40_RateLimiter import rate_limit, acquire_tradier

# Method 1: As decorator
@rate_limit(requests_per_second=10)
async def submit_order(symbol, qty):
    # API call here
    pass

# Method 2: Manual acquisition
async def fetch_quote(symbol):
    await acquire_tradier()  # Wait if needed
    return client.get_quote(symbol)

# Method 3: Context manager
async with RateLimiter(requests_per_second=5):
    await make_api_call()
```

### Circuit Breaker Example

```python
from SpyderU_Utilities.SpyderU41_CircuitBreaker import circuit_breaker, tradier_breaker

# Method 1: As decorator
@circuit_breaker(failure_threshold=5, recovery_timeout=60)
async def risky_api_call():
    # Protected API call
    pass

# Method 2: Using pre-configured breaker
@tradier_breaker.decorator
async def tradier_call():
    # Protected with tradier-specific settings
    pass

# Method 3: Context manager
async with tradier_breaker:
    await make_api_call()
```

### Combined Example (Rate Limit + Circuit Breaker)

```python
from SpyderU_Utilities.SpyderU40_RateLimiter import rate_limit
from SpyderU_Utilities.SpyderU41_CircuitBreaker import circuit_breaker

@rate_limit(requests_per_second=10)
@circuit_breaker(failure_threshold=5, recovery_timeout=60)
async def protected_api_call(symbol):
    """
    API call with both rate limiting and circuit breaking.
    Order matters: rate limit first, then circuit breaker.
    """
    response = await client.get_quote(symbol)
    return response
```

---

## Integration Examples

### Tradier Client Integration

```python
# SpyderB_Broker/SpyderB40_TradierClient.py

from SpyderU_Utilities.SpyderU40_RateLimiter import rate_limit, acquire_tradier
from SpyderU_Utilities.SpyderU41_CircuitBreaker import tradier_breaker

class TradierClient:

    @rate_limit(service="tradier")
    @tradier_breaker.decorator
    async def submit_order_protected(self, symbol, qty, side, order_type):
        """
        Submit order with rate limiting and circuit breaker.

        - Rate limit: 10 req/sec (Tradier recommended)
        - Circuit breaker: Opens after 5 failures, retries after 60s
        """
        # Convert sync method to async wrapper
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self.submit_order,  # Original sync method
            symbol, qty, side, order_type
        )
        return result

    async def get_quote_protected(self, symbol):
        """Get quote with protection."""
        await acquire_tradier()  # Rate limit

        async with tradier_breaker:  # Circuit breaker
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self.get_quote,
                symbol
            )
```

### Polygon Handler Integration

```python
# SpyderC_MarketData/SpyderC25_PolygonDataHandler.py

from SpyderU_Utilities.SpyderU40_RateLimiter import acquire_polygon
from SpyderU_Utilities.SpyderU41_CircuitBreaker import polygon_breaker

class PolygonDataHandler:

    async def fetch_historical_data_protected(self, symbol, timeframe):
        """
        Fetch historical data with protection.

        Polygon limits:
        - Starter: 5 requests/minute
        - Business: 100 requests/minute
        """
        # Determine tier from config
        tier = "starter"  # or "business"

        await acquire_polygon(tier=tier)

        async with polygon_breaker:
            return await self._fetch_historical(symbol, timeframe)
```

### Strategy Execution Integration

```python
# SpyderD_Strategies/SpyderD01_BaseStrategy.py

from SpyderU_Utilities.SpyderU40_RateLimiter import MultiRateLimiter
from SpyderU_Utilities.SpyderU41_CircuitBreaker import get_circuit_breaker

class BaseStrategy:

    def __init__(self):
        # Create multi-rate limiter for different operations
        self.rate_limiter = MultiRateLimiter()
        self.rate_limiter.add_limit("orders", requests_per_second=2)
        self.rate_limiter.add_limit("quotes", requests_per_second=10)

        # Create circuit breakers
        self.order_breaker = get_circuit_breaker("orders", failure_threshold=3)
        self.data_breaker = get_circuit_breaker("data", failure_threshold=5)

    async def execute_trade(self, symbol, qty):
        """Execute trade with protection."""
        # Rate limit + circuit breaker for orders
        await self.rate_limiter.acquire("orders")

        async with self.order_breaker:
            return await self.broker.submit_order(symbol, qty)

    async def get_market_data(self, symbol):
        """Get market data with protection."""
        await self.rate_limiter.acquire("quotes")

        async with self.data_breaker:
            return await self.data_feed.get_quote(symbol)
```

---

## Configuration

### Pre-configured Rate Limits

The following limits are pre-configured:

```python
# Tradier: ~10 req/sec recommended
_global_limiters.add_limit("tradier", requests_per_second=10, burst_size=20)

# Polygon Starter: 5 req/min = 0.08 req/sec
_global_limiters.add_limit("polygon_rest", requests_per_second=0.08)

# Polygon Business: 100 req/min = 1.67 req/sec
_global_limiters.add_limit("polygon_business", requests_per_second=1.67)
```

### Pre-configured Circuit Breakers

```python
# Tradier breaker
tradier_breaker = CircuitBreaker(
    name="tradier",
    failure_threshold=5,
    recovery_timeout=60.0,
    timeout=30.0
)

# Polygon breaker
polygon_breaker = CircuitBreaker(
    name="polygon",
    failure_threshold=3,
    recovery_timeout=30.0,
    timeout=10.0
)
```

### Custom Configuration

```python
from SpyderU_Utilities.SpyderU40_RateLimiter import MultiRateLimiter
from SpyderU_Utilities.SpyderU41_CircuitBreaker import CircuitBreaker

# Custom rate limiter
limiter = MultiRateLimiter()
limiter.add_limit("my_api", requests_per_second=5, burst_size=10)

# Custom circuit breaker
breaker = CircuitBreaker(
    name="my_service",
    failure_threshold=10,  # More tolerant
    recovery_timeout=120.0,  # Longer cooldown
    timeout=15.0  # Per-call timeout
)
```

---

## Monitoring

### Check Circuit Breaker Status

```python
from SpyderU_Utilities.SpyderU41_CircuitBreaker import tradier_breaker

# Get statistics
stats = tradier_breaker.get_stats()
print(f"State: {stats['state']}")
print(f"Failures: {stats['failure_count']}")
print(f"Is Open: {stats['is_open']}")
print(f"Time until retry: {stats['time_until_retry']:.1f}s")

# Check state
if tradier_breaker.is_open:
    logger.warning("Tradier circuit is open - service unavailable")
elif tradier_breaker.is_closed:
    logger.info("Tradier circuit is closed - normal operation")
```

### Manual Circuit Reset

```python
# Force reset after manual fix
tradier_breaker.reset()
logger.info("Circuit manually reset")
```

---

## Error Handling

### Circuit Breaker Errors

```python
from SpyderU_Utilities.SpyderU41_CircuitBreaker import CircuitBreakerError

try:
    result = await protected_api_call()
except CircuitBreakerError as e:
    logger.warning(f"Circuit is open: {e}")
    # Fallback logic here
    use_cached_data()
except Exception as e:
    logger.error(f"API call failed: {e}")
    # Other error handling
```

### Rate Limit Handling

Rate limiter automatically waits, no error handling needed:

```python
# This will automatically wait if rate limit exceeded
await acquire_tradier()
result = client.submit_order(...)
```

---

## Best Practices

### 1. Apply Rate Limiting First

```python
# ✅ Good: Rate limit before circuit breaker
@rate_limit(requests_per_second=10)
@circuit_breaker(failure_threshold=5)
async def api_call():
    pass

# ❌ Bad: Circuit breaker before rate limit
@circuit_breaker(failure_threshold=5)
@rate_limit(requests_per_second=10)
async def api_call():
    pass
```

**Why**: Rate limiting prevents hitting limits, circuit breaker handles failures.

### 2. Use Pre-configured Breakers for Known Services

```python
# ✅ Good: Use pre-configured breaker
from SpyderU_Utilities.SpyderU41_CircuitBreaker import tradier_breaker

@tradier_breaker.decorator
async def call():
    pass

# ❌ Less good: Create new breaker each time
@circuit_breaker(failure_threshold=5)  # Creates new instance
async def call():
    pass
```

### 3. Set Appropriate Thresholds

```python
# Critical services: More tolerant
critical_breaker = CircuitBreaker(
    failure_threshold=10,  # Allow more failures
    recovery_timeout=120.0  # Longer cooldown
)

# Optional services: Less tolerant
optional_breaker = CircuitBreaker(
    failure_threshold=3,  # Quick failure
    recovery_timeout=30.0  # Quick retry
)
```

### 4. Monitor Circuit States

```python
# Log circuit breaker events
import logging
logging.getLogger("SpyderU_Utilities.SpyderU41_CircuitBreaker").setLevel(logging.INFO)

# Will log:
# - Circuit opened (too many failures)
# - Circuit entering half-open (testing recovery)
# - Circuit closed (recovered)
```

---

## Testing

### Test Rate Limiting

```python
import asyncio
from SpyderU_Utilities.SpyderU40_RateLimiter import RateLimiter

async def test_rate_limiting():
    limiter = RateLimiter(requests_per_second=5)

    start = asyncio.get_event_loop().time()

    for i in range(10):
        await limiter.acquire()
        print(f"Request {i} at {asyncio.get_event_loop().time() - start:.2f}s")

    # Should take ~2 seconds (10 requests at 5/sec)

asyncio.run(test_rate_limiting())
```

### Test Circuit Breaker

```python
import asyncio
from SpyderU_Utilities.SpyderU41_CircuitBreaker import CircuitBreaker, CircuitBreakerError

async def test_circuit_breaker():
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5.0)

    async def failing_call():
        raise Exception("API error")

    # Generate failures
    for i in range(5):
        try:
            await breaker.call(failing_call)
        except Exception:
            print(f"Call {i} failed")

    # Should be open now
    assert breaker.is_open
    print(f"Circuit opened after {i+1} failures")

    # Try call - should fail immediately
    try:
        await breaker.call(failing_call)
    except CircuitBreakerError as e:
        print(f"Circuit is open: {e}")

asyncio.run(test_circuit_breaker())
```

---

## Migration Path

### Phase 1: Add to New Code
- Use rate limiting and circuit breakers in all new API integrations
- Start with high-traffic endpoints

### Phase 2: Wrap Existing Clients
- Create async wrappers for TradierClient
- Add protection to PolygonDataHandler
- Protect strategy execution

### Phase 3: Full Integration
- All external API calls protected
- Monitor circuit breaker states
- Tune thresholds based on production data

---

## Troubleshooting

### Issue: Requests Too Slow

**Symptom**: Rate limiting causing delays
**Solution**: Check if rate too low
```python
# Increase rate
limiter = RateLimiter(requests_per_second=20)  # Was 10
```

### Issue: Circuit Opens Too Quickly

**Symptom**: Circuit opens after minor issues
**Solution**: Increase failure threshold
```python
breaker = CircuitBreaker(failure_threshold=10)  # Was 5
```

### Issue: Circuit Takes Too Long to Recover

**Symptom**: Circuit stays open too long
**Solution**: Reduce recovery timeout
```python
breaker = CircuitBreaker(recovery_timeout=30.0)  # Was 60.0
```

---

**Last Updated**: 2025-11-24
**Version**: 1.0
**Status**: Ready for Integration ✅
