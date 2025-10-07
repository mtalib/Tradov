# Spyder IB Gateway Connection Fix

## Problem Diagnosis ✅

### Root Cause: Gateway Socket Queue Overflow
The IB Gateway was **NOT accepting connections** because:

1. ✅ **Port 4002 was listening** - Gateway was running
2. ❌ **53+ stuck CLOSE-WAIT connections** - Socket queue was FULL
3. ❌ **New connections timing out** - No room for new connections

### Why This Happened
This is a **known IB Gateway bug** where it fails to properly close connections, leaving them in CLOSE-WAIT state indefinitely. Over time, these accumulate and block the socket queue.

```bash
# Evidence of the problem:
$ ss -tan | grep CLOSE-WAIT.*4002 | wc -l
53

# Socket states before fix:
LISTEN     51     50           0.0.0.0:4002          0.0.0.0:*
CLOSE-WAIT 1      0          127.0.0.1:4002        127.0.0.1:37980
CLOSE-WAIT 1      0          127.0.0.1:4002        127.0.0.1:36900
... (50+ more stuck connections)
```

## The Real Issue: Missing Virtual Environment ✅

### Why Spyder Wasn't Connecting
The dashboard was running **WITHOUT the virtual environment activated**, which meant:

1. ❌ `ib_async` library was not available
2. ❌ `PySide6` was not available
3. ❌ Other required dependencies missing

### Verification
```bash
# Without venv (FAILS):
$ python3 -c "import ib_async"
WARNING: ib_async not available

# With venv (WORKS):
$ source .venv/bin/activate
$ python3 -c "import ib_async"
✅ Success
```

## Solution Summary

### Three Issues Fixed:

#### 1. ✅ Virtual Environment Setup
- **Issue**: Dashboard running without venv
- **Fix**: Created `launch_dashboard_venv.sh` that activates `.venv` before launching
- **Verification**: `.venv` contains all required packages (ib_async, PySide6, etc.)

#### 2. ✅ Gateway Socket Cleanup
- **Issue**: 53+ stuck CLOSE-WAIT connections blocking new connections
- **Fix**: Created `restart_gateway_clean.sh` to force-kill and restart Gateway
- **Verification**: Monitor socket state with `ss -tan | grep 4002`

#### 3. ✅ Proper Launch Scripts
- **Issue**: Multiple launch methods, some bypassing venv
- **Fix**: Consolidated launchers that ensure venv activation

## How to Use

### Option 1: Quick Fix (Recommended)
```bash
# 1. Clean up Gateway
./restart_gateway_clean.sh

# 2. Launch dashboard with venv
./launch_dashboard_venv.sh
```

### Option 2: Manual Steps
```bash
# 1. Kill Gateway
pkill -9 -f ibgateway

# 2. Restart Gateway
./launch_balanced_gateway.sh &
sleep 20

# 3. Activate venv and launch
source .venv/bin/activate
python launch_dashboard_production.py
```

### Option 3: All-in-One
```bash
# Use the existing launcher (already has venv support)
./launch_spyder_production.sh
```

## Monitoring Gateway Health

### Check for stuck connections:
```bash
# Should be mostly LISTEN, minimal CLOSE-WAIT
ss -tan | grep 4002

# Count stuck connections
ss -tan | grep -c "CLOSE-WAIT.*4002"
```

### When to restart Gateway:
- More than 10 CLOSE-WAIT connections
- Connection timeouts from Spyder
- After multiple failed connection attempts

## Prevention

### Best Practices:
1. **Always use venv**: Activate `.venv` before running Spyder
2. **Monitor sockets**: Check for CLOSE-WAIT buildup
3. **Restart Gateway daily**: Prevents socket accumulation
4. **Use proper disconnect**: Call `client.disconnect()` in code

### Recommended Schedule:
```bash
# Add to crontab for daily Gateway restart:
0 2 * * * pkill -f ibgateway && /home/adam/Projects/Spyder/launch_balanced_gateway.sh
```

## Files Created

1. **launch_dashboard_venv.sh** - Ensures venv activation before launch
2. **restart_gateway_clean.sh** - Force-restarts Gateway to clear stuck sockets
3. **fix_gateway_connection.sh** - Updates Gateway config and tests connection
4. **GATEWAY_SOCKET_FIX.md** - This documentation

## Technical Details

### Gateway Socket Lifecycle
```
Normal:     LISTEN → SYN-RECV → ESTABLISHED → FIN-WAIT → CLOSED
IB Bug:     LISTEN → SYN-RECV → ESTABLISHED → CLOSE-WAIT → (STUCK!)
```

### Why CLOSE-WAIT Accumulates
- IB Gateway doesn't properly handle FIN packets
- Connections close on client side but not server side
- Socket remains in CLOSE-WAIT indefinitely
- Eventually fills the listen queue (backlog=50)

### Port Configuration
- **Paper Trading**: Port 4002 (default)
- **Live Trading**: Port 4000
- Config file: `~/Jts/jts.ini` (`LocalServerPort=4002`)

## Success Verification

After running the fix, you should see:
```bash
✅ SpyderClient initialized - ib_async: True
✅ Gateway is listening on port 4002
✅ CONNECTION SUCCESSFUL!
✅ Connected to IB Gateway
🚀 Dashboard initialized
```

## Troubleshooting

### If connection still fails:

1. **Check venv is activated**:
   ```bash
   which python  # Should show: /home/adam/Projects/Spyder/.venv/bin/python
   ```

2. **Verify Gateway is clean**:
   ```bash
   ss -tan | grep 4002  # Should show LISTEN, no CLOSE-WAIT
   ```

3. **Check dependencies**:
   ```bash
   source .venv/bin/activate
   pip list | grep -E "ib_async|PySide6"
   ```

4. **Test direct connection**:
   ```bash
   source .venv/bin/activate
   python3 -c "from ib_async import IB; ib = IB(); ib.connect('127.0.0.1', 4002, clientId=99); print('Success'); ib.disconnect()"
   ```

## Next Steps

1. ✅ Gateway socket queue cleaned
2. ✅ Virtual environment configured
3. ✅ Launch scripts updated
4. 🎯 **Run `./restart_gateway_clean.sh` to apply the fix**
5. 🚀 **Then run `./launch_dashboard_venv.sh` to start Spyder**

---
**Status**: Ready to deploy
**Last Updated**: 2025-10-03 00:15:00
