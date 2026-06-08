# GUI Logging Integration

## Overview

The Tradov trading system now features **automatic integration between Python's logging system and the GUI dashboard**. All log messages (from `logger.info()`, `logger.warning()`, etc.) automatically appear in real-time on the dashboard display panels.

## Benefits

✅ **Real-time monitoring** - See system events as they happen
✅ **No duplicate code** - Single logging call goes to console, file, AND GUI
✅ **Thread-safe** - Uses Qt signals for safe cross-thread communication
✅ **Smart routing** - Automatically routes logs to appropriate dashboard panels
✅ **Configurable** - Control log levels and filtering via environment variables
✅ **No duplicates** - Automatic duplicate detection prevents spam

## Architecture

```
Python Logger
     ↓
logger.info("message")
     ↓
     ├──→ Console (stdout)
     ├──→ File (logs/tradov.log)
     └──→ GUI Dashboard (NEW!)
           ├──→ System Log Panel (infrastructure, connections, errors)
           └──→ Automation Log Panel (strategies, trades, signals)
```

## Dashboard Log Panels

### System Log Panel (Left side, 65% width)
- Infrastructure events
- API connections
- System errors and warnings
- Configuration changes
- Network status

**Example messages:**
```
ℹ️ TradovB40_TradierClient - Connected to Tradier sandbox
⚠️ TradovC25_PolygonDataHandler - WebSocket reconnecting...
❌ TradovB_Broker - Order rejected: insufficient funds
```

### Automation Log Panel (Right panel)
- Trading strategy signals
- Order executions
- Position updates
- Risk alerts
- Signal detections

**Example messages:**
```
ℹ️ TradovD_Strategies - Iron Condor signal detected
ℹ️ TradovE_Risk - Position size validated: $5,000
✅ TradovB_Broker - Order filled: BUY 10 SPY CALL 450 @ $2.50
```

## Configuration

### Environment Variables (.env)

```bash
# Minimum log level for console and file output
LOG_LEVEL=INFO

# Minimum log level for GUI dashboard display
GUI_LOG_LEVEL=INFO
```

### Log Levels

| Level | Priority | Usage |
|-------|----------|-------|
| DEBUG | Lowest | Detailed diagnostic information (verbose) |
| INFO | Normal | General informational messages |
| WARNING | Medium | Warning messages (potential issues) |
| ERROR | High | Error messages (failures) |
| CRITICAL | Highest | Critical failures (system shutdown) |

**Recommendation:**
- Development: `GUI_LOG_LEVEL=DEBUG` (see everything)
- Production: `GUI_LOG_LEVEL=INFO` (normal operation)
- Live Trading: `GUI_LOG_LEVEL=WARNING` (only issues)

## Usage in Code

### Basic Logging

```python
from TradovU_Utilities.TradovU01_Logger import get_logger

logger = get_logger(__name__)

# These automatically appear in GUI now!
logger.info("System initialized successfully")
logger.warning("Market data delayed")
logger.error("Failed to connect to API")
```

### Routing to Automation Log

The system automatically routes logs containing these keywords to the Automation Log panel:

- `automation`
- `strategy`
- `signal`
- `trade`
- `order`
- `execution`
- `position`
- `risk`
- `alert`

**Example:**
```python
# Goes to Automation Log (contains "signal")
logger.info("Iron Condor signal detected")

# Goes to Automation Log (contains "order")
logger.info("Order submitted: BUY SPY 450 CALL")

# Goes to System Log (infrastructure)
logger.info("WebSocket connection established")
```

### Advanced: Custom Routing

```python
from TradovG_GUI.TradovG99_GUILogHandler import FilteredGUILogHandler

# Only show logs from specific modules
handler = FilteredGUILogHandler(
    dashboard,
    include_modules=['TradovB_Broker', 'TradovD_Strategies']
)

# Exclude noisy modules
handler = FilteredGUILogHandler(
    dashboard,
    exclude_modules=['TradovU_Utilities']
)
```

## Implementation Details

### GUILogHandler Class

**Location:** `TradovG_GUI/TradovG99_GUILogHandler.py`

**Features:**
- Thread-safe using Qt signals
- Automatic duplicate detection (prevents log spam)
- Smart routing based on logger name and content
- Color-coded level indicators (🔍 DEBUG, ℹ️ INFO, ⚠️ WARNING, ❌ ERROR, 🔥 CRITICAL)
- Buffer management (prevents memory leaks)

### Integration Points

**Main Application:** `TradovA_Core/TradovA01_Main.py`

```python
# Lines 146, 594-602, 618-626
from TradovG_GUI.TradovG99_GUILogHandler import setup_gui_logging

# After dashboard is created and shown:
gui_log_handler = setup_gui_logging(dashboard, log_level="INFO")
```

## Testing

### Test Script

Run the standalone test to verify GUI logging:

```bash
python TradovQ_Scripts/test_gui_logging.py
```

This will:
1. Create a simple dashboard
2. Setup GUI logging
3. Generate test log messages
4. Verify they appear in both panels

### Manual Testing

1. Start Tradov: `python TradovA_Core/TradovA01_Main.py`
2. Watch the System Log panel (bottom left)
3. Watch the Automation Log panel (right panel)
4. Verify startup messages appear
5. Trigger a strategy or order
6. Verify messages appear in appropriate panels

## Troubleshooting

### Logs not appearing in GUI

**Check 1:** Is GUI_LOG_LEVEL set correctly?
```bash
# In .env file
GUI_LOG_LEVEL=INFO  # Not DEBUG or WARNING
```

**Check 2:** Is the log level high enough?
```python
# This won't appear if GUI_LOG_LEVEL=WARNING
logger.info("This is just info")  # Too low

# This will appear
logger.warning("This is a warning")  # High enough
```

**Check 3:** Check console for handler errors
```bash
✅ GUI logging handler connected (level: INFO)  # Should see this
⚠️ Could not setup GUI logging: ...  # If you see this, there's an issue
```

### Too many duplicate messages

The system automatically prevents duplicates, but if you see repeats:

1. Check if multiple loggers are logging the same message
2. Increase duplicate cache size in `GUILogHandler.__init__()`:
```python
self.max_cache_size = 100  # Increase from 50
```

### GUI freezing

If GUI becomes unresponsive with logging:

1. Reduce log level: `GUI_LOG_LEVEL=WARNING`
2. Use filtered handler to exclude noisy modules
3. Check for logging loops (logger calling itself)

## Performance Considerations

### Memory Usage

- **Log buffers:** System log keeps last 100 messages (20 displayed)
- **Automation log:** Keeps last 100 messages (15 displayed)
- **Duplicate cache:** Keeps last 50 message signatures
- **Total overhead:** ~50KB per panel

### CPU Usage

- **Minimal impact:** Qt signals are highly optimized
- **Thread-safe:** No blocking operations
- **Async routing:** Messages queued, not synchronous

### Best Practices

1. **Use appropriate log levels**
   ```python
   # Good
   logger.debug("Detailed calculation: x=123, y=456")  # Only in development
   logger.info("Order submitted")  # Normal operation
   logger.error("API call failed")  # Always visible

   # Bad
   logger.info("Loop iteration 12345")  # Too verbose
   ```

2. **Avoid logging in tight loops**
   ```python
   # Bad
   for i in range(10000):
       logger.info(f"Processing item {i}")  # Floods GUI

   # Good
   logger.info(f"Processing {len(items)} items...")
   for i in range(10000):
       process(i)
   logger.info("Processing complete")
   ```

3. **Use structured messages**
   ```python
   # Good
   logger.info(f"Order filled: {symbol} {qty}@${price}")

   # Bad
   logger.info("filled")  # Not informative
   ```

## Migration Guide

### Replacing print() Statements

**Before:**
```python
print("Connecting to Tradier...")
print(f"Order submitted: {order_id}")
```

**After:**
```python
logger.info("Connecting to Tradier...")
logger.info(f"Order submitted: {order_id}")
```

**Benefits:**
- ✅ Appears in console, file, AND GUI
- ✅ Timestamped automatically
- ✅ Severity level included
- ✅ Module name included
- ✅ Searchable in log files

### Replacing Manual Dashboard Calls

**Before:**
```python
logger.info("Order executed")  # Goes to console/file
dashboard.add_system_log("Order executed")  # Duplicate call for GUI
```

**After:**
```python
logger.info("Order executed")  # Now goes to console, file, AND GUI automatically!
```

## Future Enhancements

Potential improvements for future versions:

1. **Log filtering UI** - Add GUI controls to filter by module or level
2. **Log export** - Button to export displayed logs to file
3. **Log search** - Search functionality within GUI logs
4. **Color coding** - Different colors for different modules
5. **Performance metrics** - Show logging rate and buffer usage
6. **Alert integration** - Route ERROR/CRITICAL to notification system

## References

- **Main Handler:** `TradovG_GUI/TradovG99_GUILogHandler.py`
- **Integration:** `TradovA_Core/TradovA01_Main.py` (lines 146, 594-602, 618-626)
- **Dashboard:** `TradovG_GUI/TradovG05_TradingDashboard.py` (lines 2209, 2433, 3811, 3834)
- **Logger:** `TradovU_Utilities/TradovU01_Logger.py`
- **Config:** `.env.template` (line 88)
- **Test:** `TradovQ_Scripts/test_gui_logging.py`

---

**Last Updated:** 2025-11-24
**Version:** 1.0
**Status:** Production Ready ✅
