# SPYDER Desktop Integration - Installation Guide

## 🎯 Quick Fix Summary

**Problem:** Dashboard creates separate gear icon instead of orange dot under SPYDER icon  
**Solution:** Update desktop file + pass environment variable from launcher to dashboard

---

## 📋 Step-by-Step Installation

### Step 2: Update SpyderG08_EnhancedLauncher.py

**File:** `/home/adam/Projects/Spyder/SpyderG_GUI/SpyderG08_EnhancedLauncher.py`

**Find this method** (around line 850):

```python
def launch_spyder_dashboard(self) -> bool:
    """Launch SPYDER Dashboard GUI."""
    try:
        dashboard_options = [
            SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
            SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
            SPYDER_HOME / "launch_dashboard_production.py",
        ]
        
        for dashboard_script in dashboard_options:
            if dashboard_script.exists():
                self.logger.info(f"Launching dashboard: {dashboard_script}")
                os.chdir(SPYDER_HOME)
                subprocess.Popen([sys.executable, str(dashboard_script)], 
                               start_new_session=True)
                return True
```

**Replace with:**

```python
def launch_spyder_dashboard(self) -> bool:
    """Launch SPYDER Dashboard GUI with desktop integration."""
    try:
        dashboard_options = [
            SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
            SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
            SPYDER_HOME / "launch_dashboard_production.py",
        ]
        
        for dashboard_script in dashboard_options:
            if dashboard_script.exists():
                self.logger.info(f"Launching dashboard: {dashboard_script}")
                os.chdir(SPYDER_HOME)
                
                # CRITICAL: Pass desktop file name via environment
                env = os.environ.copy()
                env['SPYDER_DESKTOP_FILE_NAME'] = 'spyder-trading'
                
                subprocess.Popen(
                    [sys.executable, str(dashboard_script)],
                    env=env,
                    start_new_session=True
                )
                
                self.logger.info("✅ Dashboard launched with desktop integration")
                return True
```

---

### Step 3: Update Dashboard Entry Points

#### Update SpyderG02_GUIEntry.py (Recommended)

**File:** `/home/adam/Projects/Spyder/SpyderG_GUI/SpyderG02_GUIEntry.py`

**Add import at top if not present:**
```python
import os
```

**Find the `main()` function and update:**

```python
def main():
    """Main entry point for SPYDER Trading Dashboard"""
    
    print("=" * 70)
    print("🕷️ SPYDER TRADING DASHBOARD")
    print("=" * 70)
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # CRITICAL: Desktop Integration for GNOME/Wayland
    desktop_file_name = os.environ.get('SPYDER_DESKTOP_FILE_NAME', 'spyder-trading')
    app.setDesktopFileName(desktop_file_name)
    print(f"✅ Desktop integration: {desktop_file_name}")
    
    # Create and show dashboard
    dashboard = SpyderTradingDashboard()
    dashboard.show()
    
    print("✅ Dashboard launched successfully")
    print("=" * 70)
    
    return app.exec()
```

---

### Step 4: Test the Fix

```bash
# 1. Close all SPYDER windows
pkill -f SpyderG08
pkill -f SpyderG02
pkill -f SpyderA01

# 2. Clear any lock files
rm -f /tmp/spyder_launcher.lock
rm -f /tmp/spyder_gateway_control.lock

# 3. Click the SPYDER icon in your application launcher
# Should open the launcher window

# 4. In the launcher, click "Dashboard Only" or "Smart Launch"
# Dashboard should appear with ORANGE DOT under SPYDER icon

# 5. Check for gear icon - should NOT appear!

# 6. Try clicking SPYDER icon again
# Should show "Already Running" warning
```

---

## 🔍 Verification Checklist

After implementation, verify these points:

- [ ] Desktop file updated with `StartupWMClass=spyder-trading`
- [ ] Desktop file paths updated to use `SpyderG08_EnhancedLauncher.py`
- [ ] Desktop database updated (`update-desktop-database`)
- [ ] SpyderG08 passes `SPYDER_DESKTOP_FILE_NAME` environment variable
- [ ] SpyderG02 (or SpyderA01) calls `app.setDesktopFileName()`
- [ ] Test: Click launcher icon - opens launcher window ✅
- [ ] Test: Launch dashboard - orange dot appears under SPYDER icon ✅
- [ ] Test: No gear icon appears ✅
- [ ] Test: Click launcher icon again - shows "Already Running" ✅

---

## 🐛 Troubleshooting

### Dashboard still creates gear icon

**Check 1: Desktop file name**
```bash
grep StartupWMClass ~/.local/share/applications/spyder-trading.desktop
# Should output: StartupWMClass=spyder-trading
```

**Check 2: Environment variable is passed**
Add debug print in SpyderG08:
```python
print(f"🐛 Setting SPYDER_DESKTOP_FILE_NAME in environment")
env['SPYDER_DESKTOP_FILE_NAME'] = 'spyder-trading'
print(f"🐛 Environment: {env.get('SPYDER_DESKTOP_FILE_NAME')}")
```

**Check 3: Dashboard receives environment variable**
Add debug print in SpyderG02:
```python
print(f"🐛 SPYDER_DESKTOP_FILE_NAME from env: {os.environ.get('SPYDER_DESKTOP_FILE_NAME', 'NOT SET')}")
print(f"🐛 Applying desktop file name: {desktop_file_name}")
```

### Can still launch multiple instances

**Check: Singleton lock is working**
```bash
# After launching, check lock file exists
ls -la /tmp/spyder_launcher.lock

# Should contain PID of running launcher
cat /tmp/spyder_launcher.lock
```

**Fix: Verify lock is acquired in SpyderG08**
```python
# Should see in main():
if not singleton.acquire():
    print("⚠️ Launcher already running!")
    sys.exit(0)
```

### Orange dot doesn't appear

**Check: Desktop file is recognized**
```bash
# Verify GNOME knows about the desktop file
desktop-file-validate ~/.local/share/applications/spyder-trading.desktop

# Should output nothing (no errors)
```

**Check: Window class matches**
```bash
# While dashboard is running, check window class
xprop WM_CLASS

# Click on dashboard window
# Should output: "spyder-trading", "spyder-trading"
```

---

## 📊 Final Verification

Once everything is installed, the workflow should be:

1. **Click SPYDER icon** → Launcher opens (no duplicate allowed)
2. **Configure settings** → Select paper/live, connection type, IBC preference
3. **Click launch button** → Dashboard spawns
4. **Check taskbar** → Single SPYDER icon with **orange dot** ✅
5. **No gear icon** ✅
6. **Click SPYDER icon again** → "Already Running" warning ✅

---

## 🎉 Success!

Once you see:
- ✅ Single SPYDER icon
- ✅ Orange dot indicator when dashboard is running
- ✅ No gear icons
- ✅ "Already Running" warning on second click

**Your desktop integration is working perfectly!** 🎊

---

## 📝 Notes

- The `spyder-trading` name must match in 3 places:
  1. Desktop file: `StartupWMClass=spyder-trading`
  2. Launcher: `env['SPYDER_DESKTOP_FILE_NAME'] = 'spyder-trading'`
  3. Dashboard: `app.setDesktopFileName('spyder-trading')`

- This fix works specifically for **GNOME/Wayland** environments
- For other desktop environments (KDE, XFCE), different approaches may be needed
- The singleton lock prevents multiple launcher instances
- The desktop file name groups windows under the launcher icon

---

**Remember:** After making changes, always restart GNOME Shell or log out/in for desktop file changes to fully take effect!

```bash
# Quick restart GNOME Shell (Wayland)
# Press Alt+F2, type 'r', press Enter

# Or log out and log back in
```
