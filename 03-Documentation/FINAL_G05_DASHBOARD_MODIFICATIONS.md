# SpyderG05_TradingDashboard.py - Required Modifications for v3.0 Workflow

## Overview
This document provides the exact code modifications needed for SpyderG05_TradingDashboard.py to support the new dashboard-first workflow where:
1. Dashboard launches immediately
2. Browser opens for IBKR login
3. Dashboard polls for connection status
4. Dashboard switches to live data when connected

## Required Changes

### 1. Add New Command-Line Argument (in main() or __init__)

**Location:** Where command-line arguments are parsed

**Add this code:**
```python
# In the argument parser section, add new mode:
parser.add_argument(
    '--mode',
    type=str,
    choices=['simulation', 'live', 'ibkr-connect'],  # ← Add 'ibkr-connect'
    default='simulation',
    help='Dashboard mode: simulation, live, or ibkr-connect'
)
```

**Purpose:** New `ibkr-connect` mode tells dashboard to:
- Launch in simulation mode initially
- Open browser for IBKR login
- Poll for IBKR connection
- Switch to live mode when connected

---

### 2. Add IBKR Connection Polling Thread

**Location:** In the main dashboard class `__init__` method, after existing initialization

**Add this code:**
```python
# ==============================================================================
# IBKR CONNECTION POLLING (for ibkr-connect mode)
# ==============================================================================
def __init__(self, ...existing params...):
    # ... existing init code ...
    
    # Add these new attributes:
    self.ibkr_mode = args.mode  # Store the mode
    self.ibkr_connected = False
    self.ibkr_account_type = None  # Will be 'PAPER' or 'LIVE'
    self.connection_poll_thread = None
    self.stop_polling = False
    
    # If ibkr-connect mode, start polling
    if self.ibkr_mode == 'ibkr-connect':
        self._start_ibkr_connect_workflow()
```

---

### 3. Add IBKR Connect Workflow Method

**Location:** Add as new method in main dashboard class

**Add this code:**
```python
def _start_ibkr_connect_workflow(self):
    """
    Start IBKR connect workflow:
    1. Open browser for login
    2. Poll for connection
    3. Switch to live data when connected
    """
    import webbrowser
    import threading
    
    try:
        # Update status bar
        self._update_connection_status("🟡 CONNECTING TO IBKR...")
        
        # Open browser to IBKR login page
        login_url = "https://localhost:5000/sso/Login?forwardTo=22&RL=1&ip2loc=on"
        webbrowser.open(login_url)
        self.logger.info("Opened browser for IBKR authentication")
        
        # Start polling thread
        self.connection_poll_thread = threading.Thread(
            target=self._poll_ibkr_connection,
            daemon=True,
            name="IBKR-Connection-Poller"
        )
        self.connection_poll_thread.start()
        self.logger.info("Started IBKR connection polling thread")
        
    except Exception as e:
        self.logger.error(f"Failed to start IBKR connect workflow: {e}")
        self._update_connection_status("❌ IBKR CONNECTION FAILED")
```

---

### 4. Add Connection Polling Method

**Location:** Add as new method in main dashboard class

**Add this code:**
```python
def _poll_ibkr_connection(self):
    """
    Poll IBKR API for authentication status.
    When connected, switch dashboard to live mode.
    """
    import time
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    base_url = "https://localhost:5000"
    session = requests.Session()
    session.verify = False
    
    max_wait_time = 300  # 5 minutes
    poll_interval = 3  # Check every 3 seconds
    elapsed_time = 0
    
    self.logger.info("Polling for IBKR authentication...")
    
    while elapsed_time < max_wait_time and not self.stop_polling:
        try:
            # Check authentication status
            response = session.get(
                f"{base_url}/v1/api/iserver/auth/status",
                timeout=5
            )
            
            if response.status_code == 200:
                status = response.json()
                
                if status.get('authenticated', False):
                    # Successfully authenticated!
                    self.logger.info("✅ IBKR authentication successful!")
                    
                    # Determine if Paper or Live trading
                    account_type = self._determine_account_type(session, base_url)
                    self.ibkr_account_type = account_type
                    self.ibkr_connected = True
                    
                    # Update status on main thread
                    self._update_connection_status(
                        f"✅ IBKR CONNECTED - {account_type} TRADING"
                    )
                    
                    # Switch dashboard to live mode
                    self._switch_to_live_mode()
                    
                    return  # Exit polling loop
            
            # Update countdown status
            remaining = max_wait_time - elapsed_time
            if elapsed_time % 9 == 0:  # Update every 9 seconds
                self._update_connection_status(
                    f"🟡 WAITING FOR IBKR LOGIN... ({remaining}s remaining)"
                )
            
        except Exception as e:
            self.logger.debug(f"Polling error (will retry): {e}")
        
        time.sleep(poll_interval)
        elapsed_time += poll_interval
    
    # Timeout or stopped
    if not self.ibkr_connected:
        self.logger.warning("IBKR authentication timeout")
        self._update_connection_status("⏱️ IBKR CONNECTION TIMEOUT")
```

---

### 5. Add Account Type Detection Method

**Location:** Add as new method in main dashboard class

**Add this code:**
```python
def _determine_account_type(self, session, base_url: str) -> str:
    """
    Determine if connected to Paper or Live account.
    
    Args:
        session: requests.Session object
        base_url: Base URL for IBKR API
        
    Returns:
        str: 'PAPER' or 'LIVE'
    """
    try:
        # Get account info
        response = session.get(
            f"{base_url}/v1/api/portfolio/accounts",
            timeout=5
        )
        
        if response.status_code == 200:
            accounts = response.json()
            
            # Paper accounts typically have 'DU' prefix
            if accounts and len(accounts) > 0:
                account_id = accounts[0].get('accountId', '')
                if account_id.startswith('DU'):
                    return 'PAPER'
                else:
                    return 'LIVE'
        
        # Default to PAPER if can't determine
        return 'PAPER'
        
    except Exception as e:
        self.logger.warning(f"Could not determine account type: {e}")
        return 'PAPER'
```

---

### 6. Add Live Mode Switching Method

**Location:** Add as new method in main dashboard class

**Add this code:**
```python
def _switch_to_live_mode(self):
    """
    Switch dashboard from simulation to live IBKR data.
    This is called when IBKR connection is established.
    """
    try:
        self.logger.info("Switching dashboard to live IBKR data mode...")
        
        # Update internal mode
        self.ibkr_mode = 'live'
        
        # Initialize IBKR connection manager (if not already done)
        if not hasattr(self, 'ibkr_manager') or self.ibkr_manager is None:
            from SpyderB_Broker.SpyderB33_IBKRWebAPIConnection import IBKRWebAPIConnection
            self.ibkr_manager = IBKRWebAPIConnection()
        
        # Stop simulation data if running
        if hasattr(self, 'simulation_timer') and self.simulation_timer:
            self.simulation_timer.stop()
            self.logger.info("Stopped simulation data timer")
        
        # Start live data feed
        self._start_live_data_feed()
        
        # Update UI elements to show live mode
        self._update_ui_for_live_mode()
        
        self.logger.info("✅ Dashboard switched to live mode successfully")
        
    except Exception as e:
        self.logger.error(f"Failed to switch to live mode: {e}")
        self._update_connection_status(f"❌ LIVE MODE SWITCH FAILED: {e}")
```

---

### 7. Add Connection Status Update Method

**Location:** Add as new method in main dashboard class

**Add this code:**
```python
def _update_connection_status(self, status_text: str):
    """
    Update connection status bar (thread-safe).
    
    Args:
        status_text: Status message to display
    """
    try:
        # Use QTimer.singleShot for thread-safe GUI update
        from PySide6.QtCore import QTimer
        
        def update_ui():
            if hasattr(self, 'status_bar') and self.status_bar:
                self.status_bar.showMessage(status_text)
            
            # Also update any connection status label if exists
            if hasattr(self, 'connection_status_label') and self.connection_status_label:
                self.connection_status_label.setText(status_text)
                
                # Color-code the status
                if '✅' in status_text or 'CONNECTED' in status_text:
                    self.connection_status_label.setStyleSheet(
                        "color: #00ff88; font-weight: bold;"
                    )
                elif '🟡' in status_text or 'CONNECTING' in status_text or 'WAITING' in status_text:
                    self.connection_status_label.setStyleSheet(
                        "color: #ffaa00; font-weight: bold;"
                    )
                elif '❌' in status_text or 'FAILED' in status_text or 'TIMEOUT' in status_text:
                    self.connection_status_label.setStyleSheet(
                        "color: #ff4444; font-weight: bold;"
                    )
        
        QTimer.singleShot(0, update_ui)
        
    except Exception as e:
        self.logger.error(f"Failed to update connection status: {e}")
```

---

### 8. Add UI Updates for Live Mode

**Location:** Add as new method in main dashboard class

**Add this code:**
```python
def _update_ui_for_live_mode(self):
    """Update UI elements to reflect live mode."""
    try:
        # Update window title
        if hasattr(self, 'setWindowTitle'):
            account_type = self.ibkr_account_type or 'UNKNOWN'
            self.setWindowTitle(f"SPYDER Dashboard - LIVE ({account_type})")
        
        # Update data mode indicator if exists
        if hasattr(self, 'data_mode_label') and self.data_mode_label:
            account_type = self.ibkr_account_type or 'UNKNOWN'
            self.data_mode_label.setText(f"DATA MODE: LIVE - {account_type}")
            self.data_mode_label.setStyleSheet("color: #00ff88; font-weight: bold;")
        
        # Enable trading buttons if they exist
        if hasattr(self, 'enable_trading_controls'):
            self.enable_trading_controls(True)
        
    except Exception as e:
        self.logger.error(f"Failed to update UI for live mode: {e}")
```

---

### 9. Add Live Data Feed Starter

**Location:** Add as new method in main dashboard class

**Add this code:**
```python
def _start_live_data_feed(self):
    """Start receiving live market data from IBKR."""
    try:
        # Start data worker thread for SPY
        if hasattr(self, 'start_market_data_worker'):
            self.start_market_data_worker('SPY')
        
        # Request additional market data as needed
        # This depends on your existing data management structure
        
        self.logger.info("Live data feed started")
        
    except Exception as e:
        self.logger.error(f"Failed to start live data feed: {e}")
```

---

### 10. Update Cleanup Method

**Location:** In your existing cleanup or closeEvent method

**Add this code:**
```python
def closeEvent(self, event):
    """Handle window close event - add IBKR polling cleanup."""
    # Stop IBKR polling if running
    if hasattr(self, 'stop_polling'):
        self.stop_polling = True
    
    if hasattr(self, 'connection_poll_thread') and self.connection_poll_thread:
        if self.connection_poll_thread.is_alive():
            self.logger.info("Stopping IBKR connection polling thread...")
            # Give it 2 seconds to finish
            self.connection_poll_thread.join(timeout=2)
    
    # ... existing cleanup code ...
    
    event.accept()
```

---

## UI Enhancement Suggestions

### Add Connection Status Widget (Optional but Recommended)

Add this to your UI setup where you want the connection status displayed:

```python
def _create_connection_status_widget(self):
    """Create connection status display widget."""
    from PySide6.QtWidgets import QLabel, QFrame
    from PySide6.QtCore import Qt
    
    # Create frame
    status_frame = QFrame()
    status_frame.setFrameShape(QFrame.StyledPanel)
    
    # Create label
    self.connection_status_label = QLabel("🔴 SIMULATION MODE")
    self.connection_status_label.setAlignment(Qt.AlignCenter)
    self.connection_status_label.setStyleSheet("""
        QLabel {
            background-color: #1a1a2e;
            color: #888888;
            padding: 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
    """)
    
    # Add to layout
    # (Add to your main layout wherever appropriate)
    
    return status_frame
```

---

## Summary of Changes

### Files Modified:
1. **SpyderG05_TradingDashboard.py** - Main dashboard (10 modifications)

### New Features Added:
1. ✅ New `ibkr-connect` mode command-line argument
2. ✅ IBKR connection polling thread
3. ✅ Automatic browser launch for login
4. ✅ Real-time connection status updates
5. ✅ Account type detection (Paper vs Live)
6. ✅ Automatic mode switching when connected
7. ✅ Thread-safe GUI updates
8. ✅ Clean shutdown handling

### User Experience Flow:
```
1. User clicks LAUNCH in launcher
   ↓
2. Dashboard opens IMMEDIATELY (simulation mode)
   Status: "🟡 CONNECTING TO IBKR..."
   ↓
3. Browser opens to IBKR login page
   ↓
4. Dashboard polls every 3 seconds for auth
   Status updates countdown: "🟡 WAITING FOR IBKR LOGIN... (297s)"
   ↓
5. User logs in and chooses Paper/Live
   ↓
6. Dashboard detects authentication
   Status: "✅ IBKR CONNECTED - PAPER TRADING"
   ↓
7. Dashboard switches to live data automatically
   Window title updates
   Trading controls enabled
```

---

## Testing Checklist

### Before Testing:
- [ ] Backup SpyderG05_TradingDashboard.py
- [ ] Add all 10 code modifications
- [ ] Verify imports are available
- [ ] Check logger is initialized

### Test Scenarios:
1. **Dashboard Only Mode:**
   ```bash
   python SpyderG05_TradingDashboard.py --mode simulation
   ```
   - [ ] Dashboard opens in simulation mode
   - [ ] Status shows "SIMULATION MODE"
   - [ ] No browser opens

2. **IBKR Connect Mode:**
   ```bash
   python SpyderG05_TradingDashboard.py --mode ibkr-connect
   ```
   - [ ] Dashboard opens immediately
   - [ ] Status shows "CONNECTING TO IBKR..."
   - [ ] Browser opens to IBKR login
   - [ ] After login, status updates to "CONNECTED"
   - [ ] Dashboard switches to live data

3. **Connection Timeout:**
   - [ ] Launch with ibkr-connect but don't log in
   - [ ] Wait 5 minutes
   - [ ] Status should show "CONNECTION TIMEOUT"
   - [ ] Dashboard remains in simulation mode

---

## Integration with Launcher

The launcher (v3.0) will call the dashboard with:

```python
# Dashboard Only mode:
python SpyderG05_TradingDashboard.py --mode simulation

# Dashboard + IBKR mode:
python SpyderG05_TradingDashboard.py --mode ibkr-connect
```

---

## Troubleshooting

### Issue: Browser doesn't open
**Solution:** Check webbrowser module is available and gateway is running on port 5000

### Issue: Connection never detected
**Solution:** 
- Verify gateway is running: `curl -k https://localhost:5000/v1/api/one/user`
- Check dashboard logs for polling errors
- Ensure requests module is installed: `pip install requests`

### Issue: Dashboard freezes during polling
**Solution:** Polling runs in separate thread - check logs for exceptions

### Issue: Can't determine account type
**Solution:** Dashboard defaults to PAPER if detection fails - safe fallback

---

## Notes

- All modifications are **additive** - no existing code needs to be removed
- Thread-safe GUI updates using QTimer.singleShot
- Graceful degradation if connection fails
- Clean shutdown of polling thread
- Comprehensive error handling and logging

---

## Questions?

If you encounter any issues implementing these modifications:
1. Check the logs in ~/spyder_logs/
2. Verify all imports are available
3. Test each modification incrementally
4. Use the testing checklist above

**This design provides a much better user experience!** 🚀
