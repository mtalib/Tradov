# Spyder Dock Launcher Setup Guide

> ⛔ **DEPRECATED:** This guide contains references to IB Gateway which is no longer used.  
> See [IB_GATEWAY_DEPRECATED.md](../IB_GATEWAY_DEPRECATED.md) for migration information.

**Date:** October 2, 2025
**Status:** ⚠️ **ARCHIVED - HISTORICAL REFERENCE ONLY**

---

## 🎯 Available Launchers

You have **3 launcher options** to choose from:

### Option 1: Smart Launcher (Recommended) ⭐
**File:** `/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh`

**What it does:**
- Checks if Gateway is running
- Shows helpful status messages
- Handles errors gracefully
- Calls `launch_spyder_smart.sh` → `SpyderA01_Main.py`

**Use when:** You want the best user experience with helpful messages

### Option 2: Direct Launcher (Simplest) 🚀
**File:** `/home/adam/Projects/Spyder/launch_spyder_direct.sh`

**What it does:**
- Goes straight to `SpyderA01_Main.py`
- No extra checks or messages
- Fastest startup

**Use when:** You want minimal overhead and know Gateway is ready

### Option 3: Gateway-Aware Launcher (Complete) 🔍
**File:** `/home/adam/Projects/Spyder/launch_spyder_with_gateway.sh`

**What it does:**
- Checks Gateway status thoroughly
- Waits for Gateway if needed
- Tests connection before launching
- Most comprehensive

**Use when:** You want maximum reliability and automatic Gateway detection

---

## 📋 Current Dock Icon Setup

Your dock icon currently points to:
```
/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh
```

This is **CORRECT** ✅ - It uses the smart launcher.

---

## 🔧 How to Update Your Dock Icon (If Needed)

### Method 1: Via File Manager
1. Right-click on Spyder dock icon
2. Select "Properties" or "Edit"
3. Find the "Command" field
4. Ensure it contains:
   ```
   /home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh
   ```
5. Save changes

### Method 2: Via Desktop File (Linux)
If your dock uses `.desktop` files:

1. Find your desktop file:
   ```bash
   # Common locations:
   ls ~/.local/share/applications/*.desktop | grep -i spyder
   ls ~/Desktop/*.desktop | grep -i spyder
   ```

2. Edit the file:
   ```bash
   nano ~/.local/share/applications/spyder.desktop
   ```

3. Update the `Exec=` line to one of these:

   **Option A (Smart):**
   ```
   Exec=/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh
   ```

   **Option B (Direct):**
   ```
   Exec=/home/adam/Projects/Spyder/launch_spyder_direct.sh
   ```

   **Option C (Complete):**
   ```
   Exec=/home/adam/Projects/Spyder/launch_spyder_with_gateway.sh
   ```

4. Save and reload:
   ```bash
   # Refresh desktop database
   update-desktop-database ~/.local/share/applications/
   ```

---

## ✅ Verification Steps

### 1. Check Script Permissions
```bash
ls -la "/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh"
# Should show: -rwxrwxr-x (executable)

ls -la /home/adam/Projects/Spyder/launch_spyder_*.sh
# All should show: -rwxrwxr-x (executable)
```

### 2. Test Direct Execution
```bash
# Test the wrapper
"/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh"

# Or test directly
/home/adam/Projects/Spyder/launch_spyder_direct.sh
```

### 3. Check What Your Dock Icon Calls
```bash
# If using .desktop file:
grep "Exec=" ~/.local/share/applications/spyder.desktop

# Should output something like:
# Exec=/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh
```

---

## 🚀 Usage Instructions

### Scenario 1: Gateway Already Running
1. Click dock icon
2. Spyder launches and connects automatically
3. Dashboard shows "🟢 IB CONNECTED"

### Scenario 2: Gateway Not Running
1. Click dock icon
2. Spyder shows: "⚠️ IB Gateway not detected - launching in simulation mode"
3. Dashboard shows "🔴 IB DISCONNECTED"
4. Start Gateway: `~/ibgateway/ibgateway &`
5. Wait 60 seconds
6. In Dashboard, click "IB CONNECT" button
7. Dashboard shows "🟢 IB CONNECTED"

---

## 🔍 Troubleshooting

### Issue: Dock icon launches wrong version

**Diagnosis:**
```bash
# When you click dock icon, check which process starts:
ps aux | grep -E "Spyder.*\.py" | grep -v grep
```

**If you see `SpyderQ14_MainLauncher_DockFixed.py`:**
- Your dock icon is outdated
- Follow "How to Update Your Dock Icon" above

**If you see `SpyderA01_Main.py`:**
- ✅ Correct! This is what you want

### Issue: "Permission denied" when clicking icon

**Fix:**
```bash
chmod +x "/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh"
chmod +x /home/adam/Projects/Spyder/launch_spyder_*.sh
```

### Issue: Nothing happens when clicking icon

**Diagnosis:**
```bash
# Check if wrapper exists
ls -la "/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh"

# Test manually
"/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh"

# Check for errors
cat /tmp/spyder_launch.log
```

---

## 📝 Quick Reference

### All Launcher Files:

| File | Type | Use Case |
|------|------|----------|
| `20250823_spyder_paper_wrapper.sh` | Wrapper | **Current dock icon** - Calls smart launcher |
| `launch_spyder_smart.sh` | Smart | Checks Gateway, shows messages |
| `launch_spyder_direct.sh` | Direct | Simplest, straight to main |
| `launch_spyder_with_gateway.sh` | Complete | Full Gateway management |

### Quick Commands:

```bash
# Test current dock launcher
"/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh"

# Use direct launcher
/home/adam/Projects/Spyder/launch_spyder_direct.sh

# Use smart launcher
/home/adam/Projects/Spyder/launch_spyder_smart.sh

# Use complete launcher
/home/adam/Projects/Spyder/launch_spyder_with_gateway.sh

# Check what's running
ps aux | grep -E "Spyder|ibgateway" | grep -v grep
```

---

## ✅ Summary

**Your Current Setup:**
- ✅ Dock icon: Points to wrapper script
- ✅ Wrapper: Calls smart launcher
- ✅ Smart launcher: Checks Gateway, uses `SpyderA01_Main.py`
- ✅ Main launcher: Has retry logic and proper connection handling

**What Changed:**
- ❌ **OLD:** `SpyderQ14_MainLauncher_DockFixed.py` (broken)
- ✅ **NEW:** `SpyderA01_Main.py` (working with retry logic)

**Everything is already configured correctly!** Just click your dock icon and it will work. 🎉

---

**Status:** ✅ **DOCK LAUNCHER READY**
**All Scripts:** ✅ Executable and Updated
**Connection Logic:** ✅ Proven and Working
