# Threading Guide for Spyder Trading System

## Overview

The Spyder trading system uses three primary threading approaches:
1. **asyncio** - For I/O-bound operations, API calls, and async workflows
2. **threading.Thread** - For CPU-bound background tasks
3. **QThread** - For GUI updates and Qt signal/slot integration

This guide explains when to use each approach and documents best practices based on lessons learned during development.

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [asyncio: Asynchronous I/O](#asyncio-asynchronous-io)
3. [threading.Thread: Standard Python Threading](#threadingthread-standard-python-threading)
4. [QThread: Qt Threading](#qthread-qt-threading)
5. [Common Pitfalls & Anti-Patterns](#common-pitfalls--anti-patterns)
6. [Integration Patterns](#integration-patterns)
7. [Debugging Threading Issues](#debugging-threading-issues)

---

## Quick Reference

| Use Case | Threading Model | Example |
|----------|----------------|---------|
| API calls (Tradier, Polygon) | asyncio | Order submission, market data requests |
| WebSocket connections | asyncio | Polygon.io real-time streaming |
| GUI updates | QThread | Dashboard data updates, charts |
| Qt timers/signals | QThread | Periodic updates in GUI |
| Heavy calculations | threading.Thread | Backtesting, model training |
| Database I/O | asyncio | Async database operations |
| File I/O | asyncio | Reading/writing large files |

---

## asyncio: Asynchronous I/O

### When to Use

✅ **Perfect for:**
- API calls (REST, WebSocket)
- Network I/O operations
- Multiple concurrent I/O operations
- Operations with waiting/idle time

❌ **Not suitable for:**
- CPU-intensive calculations
- Blocking library calls
- Operations without async support

### Basic Pattern

```python
import asyncio
from SpyderU_Utilities.SpyderU01_Logger import get_logger

logger = get_logger(__name__)

async def fetch_market_data(symbol: str) -> dict:
    """Fetch market data asynchronously."""
    logger.info(f"Fetching data for {symbol}")

    # ✅ Good: Use await for I/O operations
    await asyncio.sleep(0.1)  # Simulate network delay

    # Return result
    return {"symbol": symbol, "price": 450.25}

# Run async function
async def main():
    result = await fetch_market_data("SPY")
    logger.info(f"Result: {result}")

# Execute
asyncio.run(main())
```

### ✅ CORRECT: Non-Blocking Sleep

```python
async def monitor_connection(self):
    """Monitor connection health with periodic checks."""
    while self.running:
        # ✅ Good: Yields control to event loop
        await asyncio.sleep(30)
        await self._check_connection_health()
```

### ❌ INCORRECT: Blocking Sleep

```python
async def monitor_connection(self):
    """Monitor connection health with periodic checks."""
    while self.running:
        # ❌ BAD: Blocks entire event loop!
        time.sleep(30)  # All other async operations freeze
        await self._check_connection_health()
```

**Impact of blocking sleep:**
- Entire event loop freezes
- No other async functions can run
- WebSocket connections timeout
- GUI becomes unresponsive
- API calls pile up

### Working with Tradier API

```python
from SpyderB_Broker.SpyderB40_TradierClient import TradierClient

async def submit_order_async(client: TradierClient, symbol: str, qty: int):
    """Submit order using asyncio integration."""
    # Tradier client has sync methods, run in executor
    loop = asyncio.get_event_loop()

    # ✅ Good: Run blocking call in thread pool
    result = await loop.run_in_executor(
        None,  # Default executor
        client.submit_order,
        symbol,
        qty,
        "buy",
        "market"
    )

    return result
```

### Multiple Concurrent Operations

```python
async def fetch_multiple_quotes(symbols: list[str]):
    """Fetch quotes for multiple symbols concurrently."""
    # ✅ Good: Run all fetches concurrently
    tasks = [fetch_quote(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle results
    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            logger.error(f"Failed to fetch {symbol}: {result}")
        else:
            logger.info(f"{symbol}: {result}")

    return results
```

---

## threading.Thread: Standard Python Threading

### When to Use

✅ **Perfect for:**
- CPU-intensive calculations
- Background tasks that don't need async
- Operations with blocking libraries
- Long-running background processes

❌ **Not suitable for:**
- GUI updates (use QThread instead)
- When coordinating with asyncio
- When you need Qt signals

### Basic Pattern

```python
import threading
from SpyderU_Utilities.SpyderU01_Logger import get_logger

logger = get_logger(__name__)

class BackgroundProcessor:
    """Process data in background thread."""

    def __init__(self):
        self.running = False
        self.thread = None
        self.data_lock = threading.Lock()
        self.results = []

    def start(self):
        """Start background processing."""
        if self.running:
            return

        self.running = True
        # ✅ Good: Use daemon thread for background work
        self.thread = threading.Thread(
            target=self._process_loop,
            daemon=True,
            name="BackgroundProcessor"
        )
        self.thread.start()
        logger.info("Background processor started")

    def stop(self):
        """Stop background processing."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
            logger.info("Background processor stopped")

    def _process_loop(self):
        """Main processing loop (runs in background thread)."""
        while self.running:
            try:
                # Do CPU-intensive work
                result = self._process_data()

                # ✅ Good: Use lock for shared data
                with self.data_lock:
                    self.results.append(result)

                # Don't spin too fast
                import time
                time.sleep(1.0)  # OK in threading.Thread

            except Exception as e:
                logger.error(f"Processing error: {e}")

    def _process_data(self) -> dict:
        """Process data (CPU-intensive)."""
        # Simulate heavy calculation
        import time
        time.sleep(0.5)
        return {"processed": True}
```

### Thread Safety with Locks

```python
from threading import Lock, RLock

class ThreadSafeCache:
    """Thread-safe cache using Lock."""

    def __init__(self):
        self._cache = {}
        self._lock = Lock()

    def get(self, key: str) -> Any:
        """Get value from cache (thread-safe)."""
        # ✅ Good: Use context manager for automatic release
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: Any):
        """Set value in cache (thread-safe)."""
        with self._lock:
            self._cache[key] = value

    def update_multiple(self, updates: dict):
        """Update multiple values atomically."""
        with self._lock:
            self._cache.update(updates)
```

---

## QThread: Qt Threading

### When to Use

✅ **Perfect for:**
- GUI updates from background threads
- Qt signals/slots integration
- QTimer in worker threads
- Data processing for GUI display

❌ **Not suitable for:**
- Non-Qt applications
- When asyncio is better suited
- Simple background tasks (use threading.Thread)

### ✅ CORRECT Pattern: Worker Object + moveToThread

**Reference**: See `/home/user/Spyder/2-DOCUMENTATION/FIXES_AND_BUGS/BUGFIX_QTIMER_THREADING_20251002.md`

```python
from PySide6.QtCore import QObject, QThread, Signal, QTimer

class DataWorker(QObject):
    """Worker that runs in separate thread."""

    # Signals for thread-safe communication
    data_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        # ✅ CRITICAL: Don't create QTimer here!
        # QTimer must be created in the thread where it will run
        self.timer = None
        self.running = False

    def start(self):
        """
        Start worker (called via thread.started signal).
        This method runs in the worker thread!
        """
        # ✅ Good: Create QTimer in worker thread
        self.timer = QTimer()
        self.timer.timeout.connect(self._fetch_data)
        self.timer.start(1000)  # Update every second
        self.running = True

    def stop(self):
        """Stop worker."""
        self.running = False
        if self.timer:
            self.timer.stop()

    def _fetch_data(self):
        """Fetch data periodically (runs in worker thread)."""
        try:
            # Simulate data fetch
            data = {"timestamp": datetime.now(), "value": 42}

            # ✅ Good: Emit signal to communicate with main thread
            self.data_ready.emit(data)

        except Exception as e:
            self.error_occurred.emit(str(e))


class MainWindow(QMainWindow):
    """Main window that uses worker thread."""

    def __init__(self):
        super().__init__()

        # Create thread and worker
        self.thread = QThread()
        self.worker = DataWorker()

        # ✅ CRITICAL: Move worker to thread BEFORE connecting signals
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.start)
        self.worker.data_ready.connect(self._on_data_ready)
        self.worker.error_occurred.connect(self._on_error)

        # Start thread
        self.thread.start()

    def _on_data_ready(self, data: dict):
        """Handle data from worker (runs in main/GUI thread)."""
        # ✅ Safe to update GUI here
        self.update_display(data)

    def _on_error(self, error: str):
        """Handle error from worker."""
        logger.error(f"Worker error: {error}")

    def closeEvent(self, event):
        """Clean up on window close."""
        # ✅ Good: Proper thread cleanup
        self.worker.stop()
        self.thread.quit()
        self.thread.wait(5000)  # Wait up to 5 seconds
        event.accept()
```

### ❌ INCORRECT Pattern: Creating QTimer in __init__

```python
class DataWorker(QObject):
    """INCORRECT worker implementation."""

    def __init__(self):
        super().__init__()
        # ❌ BAD: QTimer created in main thread
        self.timer = QTimer()  # Will fail when worker moves to another thread
        self.timer.timeout.connect(self._fetch_data)
```

**Error you'll get:**
```
QObject::startTimer: Timers cannot be started from another thread
```

---

## Common Pitfalls & Anti-Patterns

### 1. ❌ time.sleep() in async functions

```python
# ❌ BAD: Blocks event loop
async def wait_and_fetch(self):
    time.sleep(1.0)  # Freezes everything!
    return await self.fetch_data()

# ✅ GOOD: Properly yields control
async def wait_and_fetch(self):
    await asyncio.sleep(1.0)  # Other tasks can run
    return await self.fetch_data()
```

### 2. ❌ Creating multiple event loops

```python
# ❌ BAD: Creates conflicting event loops
def start_async_operation():
    loop = asyncio.new_event_loop()  # Creates new loop
    asyncio.set_event_loop(loop)
    loop.run_until_complete(operation())

# ✅ GOOD: Use existing loop
async def start_async_operation():
    await operation()  # Uses current event loop
```

### 3. ❌ Qt objects in wrong thread

```python
# ❌ BAD: QTimer created before moveToThread
class Worker(QObject):
    def __init__(self):
        super().__init__()
        self.timer = QTimer()  # Wrong thread!

# ✅ GOOD: QTimer created in worker thread
class Worker(QObject):
    def __init__(self):
        super().__init__()
        self.timer = None

    def start(self):
        self.timer = QTimer()  # Correct thread!
```

### 4. ❌ Missing thread synchronization

```python
# ❌ BAD: Race condition
class UnsafeCounter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1  # Not atomic!

# ✅ GOOD: Thread-safe with Lock
class SafeCounter:
    def __init__(self):
        self.count = 0
        self.lock = threading.Lock()

    def increment(self):
        with self.lock:
            self.count += 1
```

### 5. ❌ Daemon threads without cleanup

```python
# ❌ BAD: Daemon thread may be killed mid-operation
def start_processor():
    thread = threading.Thread(target=process_data, daemon=True)
    thread.start()
    # Thread may be killed before completing

# ✅ GOOD: Proper shutdown mechanism
class Processor:
    def __init__(self):
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)

    def _run(self):
        while self.running:
            process_data()
```

---

## Integration Patterns

### asyncio + Qt (qasync)

**Reference**: See `/home/user/Spyder/2-DOCUMENTATION/FIXES_AND_BUGS/ASYNCIO_EVENT_LOOP_FIX_SUMMARY.md`

```python
import asyncio
import sys
from PySide6.QtWidgets import QApplication
import qasync

async def async_operation():
    """Async operation that integrates with Qt."""
    await asyncio.sleep(1.0)
    return "Result"

def main():
    app = QApplication(sys.argv)

    # ✅ Good: Use qasync for Qt + asyncio integration
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Create window
    window = MainWindow()
    window.show()

    # Run event loop
    with loop:
        loop.run_forever()
```

### ThreadPoolExecutor with asyncio

```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

class DataProcessor:
    """Process data using thread pool."""

    def __init__(self, max_workers=4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def process_async(self, data: list):
        """Process data asynchronously using thread pool."""
        loop = asyncio.get_event_loop()

        # ✅ Good: Run CPU-bound work in thread pool
        tasks = [
            loop.run_in_executor(self.executor, self._process_item, item)
            for item in data
        ]

        results = await asyncio.gather(*tasks)
        return results

    def _process_item(self, item):
        """CPU-intensive processing (runs in thread pool)."""
        # Heavy calculation here
        return item * 2

    def shutdown(self):
        """Clean up thread pool."""
        self.executor.shutdown(wait=True)
```

---

## Debugging Threading Issues

### Enable asyncio Debug Mode

```python
import asyncio
import warnings

# Enable asyncio debug mode
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
loop = asyncio.new_event_loop()
loop.set_debug(True)

# Show warnings for blocking calls
warnings.simplefilter('always', ResourceWarning)
```

### Detect Blocking Calls

```python
import asyncio

async def monitor_loop():
    """Monitor event loop for slow operations."""
    loop = asyncio.get_running_loop()

    # Set slow callback threshold (in seconds)
    loop.slow_callback_duration = 0.1  # Warn if callback takes > 100ms

    # Monitor
    while True:
        await asyncio.sleep(1.0)
```

### Thread Naming for Debugging

```python
import threading

# Name threads for easier debugging
thread = threading.Thread(
    target=worker_function,
    name="MarketDataProcessor",  # ✅ Good: Named thread
    daemon=True
)
thread.start()

# Later, when debugging:
for thread in threading.enumerate():
    print(f"Thread: {thread.name}, Alive: {thread.is_alive()}")
```

### Deadlock Detection

```python
import threading
from contextlib import contextmanager

@contextmanager
def timeout_lock(lock, timeout=5.0):
    """Acquire lock with timeout to detect deadlocks."""
    acquired = lock.acquire(timeout=timeout)

    if not acquired:
        raise TimeoutError(f"Failed to acquire lock within {timeout}s - possible deadlock")

    try:
        yield
    finally:
        lock.release()

# Usage
lock = threading.Lock()

with timeout_lock(lock, timeout=2.0):
    # Critical section
    process_data()
```

---

## Best Practices Summary

### ✅ Do:
1. Use `await asyncio.sleep()` in async functions
2. Create QTimer/QObject in the thread where they'll run
3. Use locks for shared data between threads
4. Name threads for debugging
5. Implement proper thread shutdown
6. Use `daemon=True` for background threads
7. Handle exceptions in thread functions
8. Use signals for Qt thread communication

### ❌ Don't:
1. Use `time.sleep()` in async functions
2. Create QTimer before `moveToThread()`
3. Access shared data without locks
4. Create multiple event loops unnecessarily
5. Mix threading models without clear integration
6. Forget to clean up threads on shutdown
7. Use bare `except:` in thread functions
8. Call GUI methods from non-GUI threads directly

---

## Reference Implementations

### Excellent Examples in Codebase:
1. **QThread Pattern**: `SpyderG05_TradingDashboard.py` (Lines 425-489)
   - Proper worker object with `moveToThread()`
   - QTimer created in worker thread
   - Clean signal/slot communication

2. **asyncio Integration**: `SpyderG05_TradingDashboard.py` (Lines 4380-4386)
   - qasync event loop integration
   - Qt + asyncio coordination

3. **Thread Safety**: `SpyderX_Agents/` (All agent files)
   - Consistent Lock usage
   - Thread-safe data access

### Documented Fixes:
- **BUGFIX_QTIMER_THREADING_20251002.md** - QTimer threading fix
- **ASYNCIO_EVENT_LOOP_FIX_SUMMARY.md** - asyncio + Qt integration

---

## Getting Help

### Common Error Messages:

**"QObject::startTimer: Timers cannot be started from another thread"**
→ Create QTimer in worker thread's `start()` method, not `__init__()`

**"Task attached to a different loop"**
→ Use qasync for Qt + asyncio integration

**"RuntimeError: This event loop is already running"**
→ Don't call `asyncio.run()` inside an already-running loop

**Blocking/frozen GUI**
→ Check for `time.sleep()` in async functions or GUI thread

---

**Last Updated**: 2025-11-24
**Version**: 1.0
**Status**: Production Guidelines ✅
