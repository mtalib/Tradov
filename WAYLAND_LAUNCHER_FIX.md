# Wayland/GNOME Launcher Integration Fix

## Problem Diagnosed

When clicking the Spyder icon on Wayland/GNOME:
1. **Slow launch** - Application takes very long to start
2. **Wrong icon** - Window appears under a separate gear icon instead of the Spyder launcher
3. **Old logs displayed** - Shows cached data from previous sessions
4. **Poor startup notification** - No visual feedback during launch

## Root Cause

**Desktop file name mismatch on Wayland:**

The desktop file expects:
- `StartupWMClass=spyder-trading-system`
- Desktop file name: `spyder-trading-system.desktop`

But the Python application was setting:
- `app.setApplicationName("Spyder Fixed Trading Dashboard")`
- **No desktop file name specified**

On Wayland, Qt applications MUST call `setDesktopFileName()` to match the `.desktop` file, otherwise:
- GNOME can't associate the window with the launcher
- Window appears under generic "gear" icon
- Startup notification fails
- Launch feels slow (no visual feedback)

## Solution Applied

### 1. SpyderG05_TradingDashboard.py (Line 4036-4046)
```python
app = QApplication(sys.argv)
app.setStyle("Fusion")

# CRITICAL: Set desktop file name for Wayland/GNOME integration
# This MUST match the .desktop file name (without .desktop extension)
app.setDesktopFileName("spyder-trading-system")

# Set application identity
app.setApplicationName("spyder-trading-system")
app.setOrganizationName("Spyder Trading System")
```

### 2. SpyderA01_Main.py (Line 708-716)
```python
self.gui_app = QApplication(sys.argv)

# CRITICAL: Set desktop file name for Wayland/GNOME integration
# This ensures the window appears under the launcher icon
self.gui_app.setDesktopFileName("spyder-trading-system")

self.gui_app.setApplicationName(self.config.app_name)
self.gui_app.setApplicationVersion(self.config.version)
```

## Expected Results

After this fix:
✅ **Fast launch** - Proper startup notification shows loading state
✅ **Correct icon** - Window appears under Spyder launcher icon with orange dot
✅ **Fresh logs** - New timestamps, no cached data confusion
✅ **Proper window tracking** - GNOME correctly associates window with launcher

## Wayland vs X11 Differences

**X11 (Old behavior):**
- Window matching based on WM_CLASS property
- More forgiving about mismatches
- `StartupWMClass` in .desktop file is often enough

**Wayland (Requires explicit setup):**
- Requires `app.setDesktopFileName()` call in Qt application
- Desktop file name MUST match exactly
- Application name should also match for consistency
- No fallback to X11-style window matching

## Testing

1. Click Spyder icon in dock
2. Verify:
   - Quick visual feedback (spinner/loading indicator)
   - Window appears under Spyder icon (not separate gear)
   - Orange dot appears under icon when running
   - System logs show CURRENT timestamps

## Files Modified

1. `/home/adam/Projects/Spyder/SpyderG_GUI/SpyderG05_TradingDashboard.py`
   - Added `app.setDesktopFileName("spyder-trading-system")`
   - Changed application name to match desktop file

2. `/home/adam/Projects/Spyder/SpyderA_Core/SpyderA01_Main.py`
   - Added `self.gui_app.setDesktopFileName("spyder-trading-system")`

3. Desktop file already correct:
   - `~/.local/share/applications/spyder-trading-system.desktop`
   - Has `StartupWMClass=spyder-trading-system`

## Related Issues Fixed

- **Issue**: Multiple instances appearing as separate windows
  - **Fix**: Single instance launcher + proper desktop file name

- **Issue**: "Old version" appearing (actually old logs)
  - **Fix**: Proper window association prevents confusion

- **Issue**: Slow launch time
  - **Fix**: Startup notification now works correctly

## References

- Qt Wayland Platform: https://doc.qt.io/qt-6/qguiapplication.html#setDesktopFileName
- GNOME Desktop Files: https://specifications.freedesktop.org/desktop-entry-spec/latest/
- Wayland Application ID: https://wayland.freedesktop.org/
