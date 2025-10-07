# CRITICAL FIX: Wrong Launcher Being Used

## Problem Discovered

**You had TWO Spyder icons in your dock launching DIFFERENT applications!**

### Running Processes Found:
1. ✅ **Correct**: `python -u SpyderA_Core/SpyderA01_Main.py` (has Gateway polling)
2. ❌ **Wrong**: `python SpyderQ_Scripts/SpyderQ14_MainLauncher_DockFixed.py` (OLD version, no polling!)

### Desktop Files Found:
1. ✅ `~/.local/share/applications/spyder-trading.desktop` - **CORRECT** (uses SpyderA01_Main.py)
2. ❌ `~/.local/share/applications/spyder-trading-system.desktop` - **WRONG** (uses old wrapper)

## Root Cause

The **second desktop file** (`spyder-trading-system.desktop`) was calling:
```bash
/home/adam/Projects/Spyder/spyder_paper_wrapper.sh
```

Which contained:
```bash
python SpyderQ_Scripts/SpyderQ14_MainLauncher_DockFixed.py --mode paper --gui
```

**This is the OLD launcher that doesn't have the Gateway polling mechanism!**

## Fix Applied

### 1. Updated `spyder_paper_wrapper.sh`:
**Before:**
```bash
#!/bin/bash
cd /home/adam/Projects/Spyder
source .venv/bin/activate
python SpyderQ_Scripts/SpyderQ14_MainLauncher_DockFixed.py --mode paper --gui
```

**After:**
```bash
#!/bin/bash
cd /home/adam/Projects/Spyder
source .venv/bin/activate
python SpyderA_Core/SpyderA01_Main.py
```

### 2. Updated Icon Path:
Changed icon path in `spyder-trading-system.desktop` from absolute path to use the icon we moved to `.local`:
```ini
Icon=spyder-trading
```

### 3. Killed Old Process:
```bash
kill 1938923  # Killed the old SpyderQ14 process
```

## Which Icon to Use

You have **TWO** Spyder icons in your dock:

| Icon Name | File | Launcher | Status |
|-----------|------|----------|--------|
| **Spyder Trading Dashboard** | spyder-trading.desktop | SpyderA01_Main.py | ✅ **USE THIS** |
| **Spyder Options Trading System** | spyder-trading-system.desktop | spyder_paper_wrapper.sh → SpyderA01_Main.py | ✅ Now fixed |

**Both should now work correctly** because the wrapper has been updated!

## How to Identify the Correct Icon

Look for:
- 🔵 **"Spyder Trading Dashboard"** - Direct launcher
- 🔵 **"Spyder Options Trading System"** - Uses wrapper (now fixed)

## Testing the Fix

### Step 1: Kill All Spyder Processes
```bash
pkill -f SpyderA01_Main.py
pkill -f SpyderQ14_MainLauncher
```

### Step 2: Ensure Gateway is Running
```bash
pgrep -f ibgateway  # Should show PID
netstat -tuln | grep 4002  # Should show LISTEN
```

### Step 3: Launch from Icon
Click either "Spyder Trading Dashboard" or "Spyder Options Trading System"

### Step 4: Verify Correct Process
```bash
ps aux | grep -i spyder | grep python
# Should show: python SpyderA_Core/SpyderA01_Main.py
# Should NOT show: SpyderQ14_MainLauncher_DockFixed.py
```

### Step 5: Check for Polling
In the Dashboard, you should see:
- If Gateway running: "🟢 IB CONNECTED" (immediate connection)
- If Gateway not running: "🔍 SEARCHING..." (polling active)

## Log Signatures

### ✅ Correct Launcher (SpyderA01_Main.py):
```
🚀 Starting SPYDER with PROVEN race condition fix...
✅ Core systems initialized successfully!
✅ GUI started successfully - race condition fix PROVEN!
```

### ❌ Wrong Launcher (SpyderQ14):
```
✅ GUI initialized via SpyderG01 bridge to SpyderG05
🔥 Real data detected - SPY: $XXX.X
🔌 Disconnected from IB Gateway
```

If you see "SpyderG01 bridge", you're running the WRONG version!

## Files Updated

1. ✅ `/home/adam/Projects/Spyder/spyder_paper_wrapper.sh` - Now uses SpyderA01_Main.py
2. ✅ `~/.local/share/applications/spyder-trading-system.desktop` - Icon path updated
3. ✅ Desktop database updated

## Next Steps

1. ✅ **Remove the duplicate icon from dock** (keep only one)
2. ✅ **Test the remaining icon** - Should launch SpyderA01_Main.py
3. ✅ **Verify Gateway polling works** - Check Dashboard shows "SEARCHING..." or "CONNECTED"

## Recommended: Keep Only One Icon

You should decide which icon to keep:

### Option A: Keep "Spyder Trading Dashboard" (Recommended)
- Direct launcher, no wrapper
- Simpler, less complexity
- Remove: spyder-trading-system.desktop

### Option B: Keep "Spyder Options Trading System"
- Has multiple launch modes (Paper/Live/Dashboard/Status)
- More flexible
- Uses wrapper (but now fixed)
- Remove: spyder-trading.desktop

## To Remove an Icon:

```bash
# Remove the duplicate desktop file
rm ~/.local/share/applications/spyder-trading-system.desktop
# OR
rm ~/.local/share/applications/spyder-trading.desktop

# Update database
update-desktop-database ~/.local/share/applications

# Remove from dock by right-clicking and selecting "Remove from Favorites"
```

---

**Status**: ✅ Fixed - Both icons now launch the correct version
**Date**: October 2, 2025
**Critical Issue**: User was unknowingly clicking the WRONG icon that launched the OLD launcher without Gateway polling!
