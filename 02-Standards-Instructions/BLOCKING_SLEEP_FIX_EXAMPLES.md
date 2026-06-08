# Fixing Blocking time.sleep() Calls in Async Functions

## Overview

This document provides examples and patterns for fixing the **15 files** identified with `time.sleep()` calls inside `async def` functions. These blocking calls prevent the entire event loop from processing other operations, causing performance degradation and UI freezes.

---

## Files Requiring Fixes

1. `TradovB_Broker/TradovB02_OrderManager.py`
2. `TradovC_MarketData/TradovC02_MarketDataFeed.py`
3. `TradovC_MarketData/TradovC14_UltraLowLatencyFeed.py`
4. `TradovC_MarketData/TradovC23_RealTimeDataOptimizer.py`
5. `TradovE_Risk/TradovE01_RiskManager.py`
6. `TradovE_Risk/TradovE07_RealTimeStressTesting.py`
7. `TradovE_Risk/TradovE10_CorrelationRiskManager.py`
8. `TradovE_Risk/TradovE14_PortfolioOptimizer.py`
9. `TradovF_Analysis/TradovF13_ModelValidation.py`
10. `TradovF_Analysis/TradovF14_MarketMicrostructure.py`
11. `TradovL_ML/TradovL17_FederatedLearning.py`
12. `TradovQ_Scripts/TradovQ91_MonitoringUtilities.py`
13. (Additional files from comprehensive analysis)

---

## The Problem

### ❌ Blocking Pattern

```python
import time
import asyncio

async def check_connection(self):
    """Check connection periodically."""
    while self.running:
        # ❌ BLOCKS ENTIRE EVENT LOOP
        time.sleep(5.0)  # Nothing else can run during this 5 seconds!

        # Check connection
        status = await self._check_status()
        self.logger.info(f"Status: {status}")
```

**Impact:**
- All other async operations freeze for 5 seconds
- WebSocket connections timeout
- API calls pile up
- GUI becomes unresponsive
- Poor performance and user experience

### ✅ Correct Pattern

```python
import asyncio

async def check_connection(self):
    """Check connection periodically."""
    while self.running:
        # ✅ YIELDS CONTROL TO EVENT LOOP
        await asyncio.sleep(5.0)  # Other operations can run!

        # Check connection
        status = await self._check_status()
        self.logger.info(f"Status: {status}")
```

**Benefits:**
- Event loop continues processing other operations
- WebSocket connections stay alive
- API calls process immediately
- GUI remains responsive
- Excellent performance

---

## Fix Pattern #1: Simple Sleep Replacement

### Before

```python
async def retry_operation(self, operation, max_retries=3):
    """Retry operation with backoff."""
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            if attempt < max_retries - 1:
                delay = 2 ** attempt  # Exponential backoff
                self.logger.warning(f"Retry {attempt + 1}, waiting {delay}s")
                time.sleep(delay)  # ❌ BLOCKS EVENT LOOP
            else:
                raise
```

### After

```python
async def retry_operation(self, operation, max_retries=3):
    """Retry operation with backoff."""
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            if attempt < max_retries - 1:
                delay = 2 ** attempt  # Exponential backoff
                self.logger.warning(f"Retry {attempt + 1}, waiting {delay}s")
                await asyncio.sleep(delay)  # ✅ NON-BLOCKING
            else:
                raise
```

**Changes:**
- `time.sleep(delay)` → `await asyncio.sleep(delay)`

---

## Fix Pattern #2: Periodic Monitoring Loop

### Before

```python
async def monitor_prices(self):
    """Monitor prices and alert on changes."""
    while self.running:
        # Fetch current prices
        prices = await self.fetch_prices()

        # Check for alerts
        self.check_alerts(prices)

        # Wait before next check
        time.sleep(10.0)  # ❌ BLOCKS EVENT LOOP
```

### After

```python
async def monitor_prices(self):
    """Monitor prices and alert on changes."""
    while self.running:
        # Fetch current prices
        prices = await self.fetch_prices()

        # Check for alerts
        self.check_alerts(prices)

        # Wait before next check
        await asyncio.sleep(10.0)  # ✅ NON-BLOCKING
```

**Changes:**
- `time.sleep(10.0)` → `await asyncio.sleep(10.0)`

---

## Fix Pattern #3: Rate Limiting

### Before

```python
async def fetch_with_rate_limit(self, urls):
    """Fetch multiple URLs with rate limiting."""
    results = []

    for url in urls:
        # Fetch URL
        result = await self.fetch_url(url)
        results.append(result)

        # Rate limit: 1 request per second
        time.sleep(1.0)  # ❌ BLOCKS EVENT LOOP

    return results
```

### After

```python
async def fetch_with_rate_limit(self, urls):
    """Fetch multiple URLs with rate limiting."""
    results = []

    for url in urls:
        # Fetch URL
        result = await self.fetch_url(url)
        results.append(result)

        # Rate limit: 1 request per second
        await asyncio.sleep(1.0)  # ✅ NON-BLOCKING

    return results
```

**Changes:**
- `time.sleep(1.0)` → `await asyncio.sleep(1.0)`

---

## Fix Pattern #4: Timeout with Fallback

### Before

```python
async def connect_with_timeout(self):
    """Connect with timeout and retry."""
    try:
        await self.connect()
    except TimeoutError:
        self.logger.warning("Connection timeout, retrying...")
        time.sleep(2.0)  # ❌ BLOCKS EVENT LOOP
        await self.connect()
```

### After

```python
async def connect_with_timeout(self):
    """Connect with timeout and retry."""
    try:
        await self.connect()
    except TimeoutError:
        self.logger.warning("Connection timeout, retrying...")
        await asyncio.sleep(2.0)  # ✅ NON-BLOCKING
        await self.connect()
```

**Changes:**
- `time.sleep(2.0)` → `await asyncio.sleep(2.0)`

---

## Fix Pattern #5: Initialization Delay

### Before

```python
async def initialize(self):
    """Initialize system with staged startup."""
    # Start component A
    await self.start_component_a()

    # Wait for stabilization
    time.sleep(1.0)  # ❌ BLOCKS EVENT LOOP

    # Start component B
    await self.start_component_b()

    # Wait for stabilization
    time.sleep(1.0)  # ❌ BLOCKS EVENT LOOP

    self.logger.info("Initialization complete")
```

### After

```python
async def initialize(self):
    """Initialize system with staged startup."""
    # Start component A
    await self.start_component_a()

    # Wait for stabilization
    await asyncio.sleep(1.0)  # ✅ NON-BLOCKING

    # Start component B
    await self.start_component_b()

    # Wait for stabilization
    await asyncio.sleep(1.0)  # ✅ NON-BLOCKING

    self.logger.info("Initialization complete")
```

**Changes:**
- All `time.sleep()` → `await asyncio.sleep()`

---

## Search and Replace Pattern

### Step 1: Find All Occurrences

```bash
# Search for time.sleep in async functions
grep -n "async def" TradovE_Risk/TradovE01_RiskManager.py
grep -n "time.sleep" TradovE_Risk/TradovE01_RiskManager.py
```

### Step 2: Verify Context

For each `time.sleep()` found:
1. Verify it's inside an `async def` function
2. Verify the function uses `await` (confirming it's actually async)
3. If both true, it needs fixing

### Step 3: Apply Fix

**Manual replacement:**
```python
# Find:
time.sleep(

# Replace with:
await asyncio.sleep(
```

**Important:** Only replace if inside `async def` function!

### Step 4: Verify Imports

Ensure the file imports asyncio:
```python
import asyncio
```

If not present, add it at the top of the file.

---

## Testing After Fixes

### 1. Syntax Check

```bash
python -m py_compile TradovE_Risk/TradovE01_RiskManager.py
```

### 2. Run Module

```bash
python TradovE_Risk/TradovE01_RiskManager.py
```

### 3. Check for Warnings

Enable asyncio debug mode:
```python
import asyncio
asyncio.run(main(), debug=True)
```

### 4. Monitor Performance

- Verify WebSocket connections don't timeout
- Check GUI responsiveness
- Monitor API call latency

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Replacing in Non-Async Functions

```python
# This is OK - not an async function
def sync_function(self):
    time.sleep(1.0)  # ✅ OK in sync functions

# This needs fixing - async function
async def async_function(self):
    time.sleep(1.0)  # ❌ BAD in async functions
```

### ❌ Mistake 2: Forgetting await

```python
async def bad_example(self):
    asyncio.sleep(1.0)  # ❌ Missing await - doesn't actually sleep!

async def good_example(self):
    await asyncio.sleep(1.0)  # ✅ Correct
```

### ❌ Mistake 3: Using time.sleep for Very Short Delays

```python
async def bad_short_delay(self):
    time.sleep(0.001)  # ❌ Even short sleeps block event loop

async def good_short_delay(self):
    await asyncio.sleep(0.001)  # ✅ Always use async sleep
```

---

## Validation Checklist

Before committing fixes:

- [ ] All `time.sleep()` in `async def` replaced with `await asyncio.sleep()`
- [ ] `import asyncio` added if not present
- [ ] Syntax check passes (`python -m py_compile`)
- [ ] Module runs without errors
- [ ] No new asyncio warnings
- [ ] Performance improved (no UI freezes)
- [ ] WebSocket connections remain stable
- [ ] Tests pass

---

## Bulk Fix Script (Optional)

For automated bulk fixing:

```python
#!/usr/bin/env python3
"""
Automated fix for blocking sleep() in async functions.
USE WITH CAUTION - Review changes carefully!
"""

import re
from pathlib import Path

def fix_file(file_path: Path):
    """Fix blocking sleep in async functions."""
    content = file_path.read_text()

    # Track if we're in an async function
    in_async = False
    fixed_lines = []
    import_added = False

    for line in content.split('\n'):
        # Check if entering async function
        if 'async def' in line:
            in_async = True

        # Check if exiting function (dedented)
        if in_async and line and not line[0].isspace() and 'async def' not in line:
            in_async = False

        # Fix time.sleep in async context
        if in_async and 'time.sleep(' in line:
            line = line.replace('time.sleep(', 'await asyncio.sleep(')

            # Ensure asyncio import exists
            if not import_added and 'import asyncio' not in content:
                fixed_lines.insert(0, 'import asyncio')
                import_added = True

        fixed_lines.append(line)

    # Write back
    file_path.write_text('\n'.join(fixed_lines))
    print(f"✅ Fixed: {file_path}")

# Usage (run with caution!)
# fix_file(Path('TradovE_Risk/TradovE01_RiskManager.py'))
```

---

## Next Steps

1. **Review this document**
2. **Pick a file to fix** (start with utilities, not core modules)
3. **Apply the fix pattern**
4. **Test thoroughly**
5. **Commit with descriptive message**
6. **Repeat for remaining files**

**Recommended order:**
1. TradovQ_Scripts/* (utilities first - lower risk)
2. TradovL_ML/* (ML modules - isolated)
3. TradovF_Analysis/* (analysis modules)
4. TradovE_Risk/* (risk modules - test carefully)
5. TradovC_MarketData/* (market data - critical)
6. TradovB_Broker/* (broker - most critical, test extensively)

---

**Status**: Ready for implementation
**Priority**: HIGH - Performance impact
**Estimated Time**: 15-30 minutes per file
**Risk Level**: Low (simple, mechanical change)

---

**Last Updated**: 2025-11-24
