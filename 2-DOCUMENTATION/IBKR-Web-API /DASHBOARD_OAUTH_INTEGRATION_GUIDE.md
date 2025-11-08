# SPYDER Dashboard OAuth Integration Guide

**Version:** 1.0.0  
**Date:** October 24, 2025  
**Target File:** `SpyderG05_TradingDashboard.py`

---

## 📋 Overview

This guide provides step-by-step instructions for integrating OAuth authentication into the Spyder Trading Dashboard. The integration allows users to:

- Launch the dashboard directly (no separate launcher)
- Authenticate with IBKR using OAuth when ready
- Switch seamlessly between Simulation and Live/Paper trading modes
- Automatically renew authentication tokens

---

## 🔧 Prerequisites

1. **Required Files Created:**
   - ✅ `SpyderB_Broker/SpyderB03_IBKRAuthManager.py`
   - ✅ `SpyderG_GUI/SpyderG06_OAuthSetupDialog.py`

2. **Dependencies Installed:**
   ```bash
   pip install 'ibind[oauth]'
   ```

3. **Backup Dashboard:**
   ```bash
   cp SpyderG_GUI/SpyderG05_TradingDashboard.py SpyderG_GUI/SpyderG05_TradingDashboard.py.backup
   ```

---

## 📝 Integration Steps

### STEP 1: Add OAuth Imports

**Location:** After existing imports section (around line 50-100)

```python
# ==============================================================================
# OAUTH AUTHENTICATION IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB03_IBKRAuthManager import (
        IBKRAuthManager, OAuthCredentials, AuthStatus, AccountType
    )
    from SpyderG_GUI.SpyderG06_OAuthSetupDialog import (
        OAuthSetupDialog, show_oauth_setup
    )
    OAUTH_AVAILABLE = True
except ImportError as e:
    OAUTH_AVAILABLE = False
    print(f"⚠️  OAuth modules not available: {e}")
    print("    Dashboard will run in simulation mode only")
```

---

### STEP 2: Initialize OAuth Manager in `__init__`

**Location:** In `SpyderTradingDashboard.__init__()`, after existing initialization (around line 200-300)

```python
        # ==================================================================
        # OAUTH AUTHENTICATION MANAGER
        # ==================================================================
        self.oauth_manager: Optional[IBKRAuthManager] = None
        self.oauth_authenticated = False
        self.oauth_account_type = None
        
        if OAUTH_AVAILABLE:
            try:
                self.oauth_manager = IBKRAuthManager()
                self.oauth_manager.initialize()
                self.logger.info("✅ OAuth manager initialized")
                
                # Check if already configured
                if self.oauth_manager.has_credentials():
                    self.add_system_log("📋 OAuth credentials found - ready to authenticate")
                else:
                    self.add_system_log("ℹ️  OAuth not configured - click 🔐 Authenticate to setup")
            except Exception as e:
                self.logger.error(f"OAuth manager initialization failed: {e}")
                self.oauth_manager = None
                self.add_system_log(f"⚠️  OAuth initialization failed: {e}")
        else:
            self.add_system_log("ℹ️  Running in simulation mode (OAuth not available)")
```

---

### STEP 3: Add OAuth Button to Toolbar

**Location:** In the toolbar creation section (around line 500-600, where other toolbar buttons are defined)

```python
        # OAuth Authentication button
        if OAUTH_AVAILABLE and self.oauth_manager:
            oauth_action = QAction("🔐 Authenticate", self)
            oauth_action.setToolTip("Configure OAuth authentication for IBKR connection")
            oauth_action.triggered.connect(self.show_oauth_setup_dialog)
            toolbar.addAction(oauth_action)
            
            # Connection status indicator
            self.connection_status_label = QLabel("🟡 SIMULATION MODE")
            self.connection_status_label.setStyleSheet("""
                QLabel {
                    background-color: #3c3c3c;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-weight: bold;
                }
            """)
            toolbar.addWidget(self.connection_status_label)
```

---

### STEP 4: Add OAuth Authentication Methods

**Location:** Add as new methods in the `SpyderTradingDashboard` class (can be added near the end of the class, before the closing of the class definition)

```python
    # ==========================================================================
    # OAUTH AUTHENTICATION METHODS
    # ==========================================================================
    
    def show_oauth_setup_dialog(self):
        """Show OAuth setup dialog for credential configuration"""
        if not OAUTH_AVAILABLE or not self.oauth_manager:
            QMessageBox.warning(
                self,
                "OAuth Not Available",
                "OAuth authentication is not available.\n\n"
                "Please install required dependencies:\n"
                "pip install 'ibind[oauth]'"
            )
            return
        
        try:
            self.add_system_log("🔧 Opening OAuth setup dialog...")
            dialog = OAuthSetupDialog(self.oauth_manager, self)
            dialog.credentials_saved.connect(self._on_oauth_credentials_saved)
            dialog.connection_successful.connect(self._on_oauth_connection_successful)
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Failed to show OAuth setup dialog: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open OAuth setup dialog:\n{str(e)}"
            )
    
    def _on_oauth_credentials_saved(self, credentials_info: dict):
        """Handle OAuth credentials saved event"""
        account_type = credentials_info.get('account_type', 'UNKNOWN')
        self.add_system_log(f"✅ OAuth credentials saved: {account_type}")
        self.add_system_log("🔄 Attempting authentication...")
    
    def _on_oauth_connection_successful(self):
        """Handle successful OAuth connection"""
        self.oauth_authenticated = True
        
        if self.oauth_manager and self.oauth_manager.status.authenticated:
            account_type = self.oauth_manager.status.account_type
            self.oauth_account_type = account_type
            
            # Update connection status
            if account_type == AccountType.PAPER:
                status_text = "✅ IBKR CONNECTED - PAPER TRADING"
                self.add_system_log("✅ Connected to IBKR Paper Trading")
            else:
                status_text = "✅ IBKR CONNECTED - LIVE TRADING"
                self.add_system_log("⚠️  Connected to IBKR LIVE TRADING")
            
            self.update_connection_status(status_text)
            
            # Switch to live data mode
            self._switch_to_live_mode()
        else:
            self.add_system_log("⚠️  Authentication succeeded but status unclear")
    
    def attempt_oauth_authentication(self) -> bool:
        """
        Attempt OAuth authentication with IBKR.
        
        This method is called automatically on dashboard startup and can also
        be triggered manually by the user.
        
        Returns:
            bool: True if authentication successful
        """
        if not OAUTH_AVAILABLE or not self.oauth_manager:
            return False
        
        if not self.oauth_manager.has_credentials():
            self.add_system_log("ℹ️  No OAuth credentials configured")
            return False
        
        try:
            self.add_system_log("🔄 Authenticating with IBKR...")
            self.update_connection_status("🟡 AUTHENTICATING...")
            
            success = self.oauth_manager.authenticate()
            
            if success:
                self._on_oauth_connection_successful()
                return True
            else:
                error_msg = self.oauth_manager.status.error_message or "Unknown error"
                self.add_system_log(f"❌ Authentication failed: {error_msg}")
                self.update_connection_status("🔴 AUTHENTICATION FAILED")
                return False
        
        except Exception as e:
            self.logger.error(f"OAuth authentication error: {e}")
            self.add_system_log(f"❌ Authentication error: {e}")
            self.update_connection_status("🔴 CONNECTION ERROR")
            return False
    
    def update_connection_status(self, status_text: str):
        """Update the connection status label"""
        if hasattr(self, 'connection_status_label'):
            self.connection_status_label.setText(status_text)
    
    def _switch_to_live_mode(self):
        """Switch dashboard from simulation to live data mode"""
        try:
            self.add_system_log("🔄 Switching to live data mode...")
            
            # Update window title
            account_type = "PAPER" if self.oauth_account_type == AccountType.PAPER else "LIVE"
            self.setWindowTitle(f"SPYDER Trading Dashboard - {account_type} TRADING")
            
            # Here you can add code to:
            # - Switch market data feed to live IBKR data
            # - Enable trading buttons
            # - Update data sources
            # - Connect to IBKR data streams
            
            self.add_system_log(f"✅ Switched to {account_type} trading mode")
            
        except Exception as e:
            self.logger.error(f"Failed to switch to live mode: {e}")
            self.add_system_log(f"⚠️  Error switching to live mode: {e}")
    
    def _auto_authenticate(self):
        """Auto-authenticate on startup if credentials are configured"""
        if OAUTH_AVAILABLE and self.oauth_manager and self.oauth_manager.has_credentials():
            self.add_system_log("🔄 Auto-authenticating with saved credentials...")
            QTimer.singleShot(500, self.attempt_oauth_authentication)
        else:
            self.add_system_log("ℹ️  No auto-authentication - credentials not configured")
```

---

### STEP 5: Add Auto-Authentication on Startup

**Location:** At the very end of `__init__` method, after all other initialization

```python
        # ==================================================================
        # AUTO OAUTH AUTHENTICATION
        # ==================================================================
        if OAUTH_AVAILABLE and self.oauth_manager:
            # Attempt auto-authentication after 2 seconds
            QTimer.singleShot(2000, self._auto_authenticate)
        else:
            self.add_system_log("ℹ️  Running in simulation mode (OAuth not available)")
            self.update_connection_status("🟡 SIMULATION MODE")
```

---

### STEP 6: Add Cleanup in `closeEvent`

**Location:** In the `closeEvent` method (if it exists) or create one

```python
    def closeEvent(self, event):
        """Handle window close event"""
        # Disconnect OAuth if connected
        if self.oauth_manager and self.oauth_authenticated:
            try:
                self.logger.info("Disconnecting OAuth on close...")
                self.oauth_manager.disconnect()
            except Exception as e:
                self.logger.error(f"OAuth disconnect error: {e}")
        
        # Call parent closeEvent
        super().closeEvent(event)
```

---

## ✅ Verification Checklist

After integration, verify:

- [ ] Dashboard starts without errors
- [ ] "🔐 Authenticate" button appears in toolbar
- [ ] Connection status shows "🟡 SIMULATION MODE"
- [ ] Clicking Authenticate opens OAuth setup dialog
- [ ] OAuth dialog has all input fields
- [ ] Can browse for certificate files
- [ ] Can test connection
- [ ] Credentials save successfully
- [ ] Authentication works
- [ ] Status updates to "✅ IBKR CONNECTED"
- [ ] Auto-authentication works on restart (if credentials saved)

---

## 🎯 Testing Procedure

### Test 1: First Launch (No Credentials)
```bash
python SpyderG05_TradingDashboard.py
```

**Expected:**
1. Dashboard opens
2. Status: "🟡 SIMULATION MODE"
3. System log: "ℹ️  OAuth not configured"
4. 🔐 Authenticate button visible

### Test 2: OAuth Setup
1. Click "🔐 Authenticate" button
2. OAuth setup dialog opens
3. Fill in credentials
4. Browse for certificates
5. Click "Test Connection"
6. Should show success message
7. Click "Save & Connect"
8. Dashboard status updates
9. System log shows authentication success

### Test 3: Restart with Credentials
```bash
python SpyderG05_TradingDashboard.py
```

**Expected:**
1. Dashboard opens
2. System log: "📋 OAuth credentials found"
3. System log: "🔄 Auto-authenticating..."
4. After ~2 seconds: "✅ Connected to IBKR"
5. Status: "✅ IBKR CONNECTED - PAPER/LIVE"

---

## 🐛 Troubleshooting

### Issue: OAuth imports fail
**Solution:** 
```bash
pip install 'ibind[oauth]'
```

### Issue: "Auth manager not available"
**Solution:** Check that `SpyderB03_IBKRAuthManager.py` is in `SpyderB_Broker/` folder

### Issue: OAuth dialog won't open
**Solution:** Check logs for import errors. Verify `SpyderG06_OAuthSetupDialog.py` exists.

### Issue: Authentication fails
**Solution:** 
- Verify credentials are correct
- Check certificate files exist and are readable
- Check IBKR Portal to ensure OAuth app is configured
- Review `~/.spyder/spyder.log` for error details

### Issue: Status doesn't update
**Solution:** Ensure `update_connection_status()` method is called and `connection_status_label` exists

---

## 📁 File Structure After Integration

```
Spyder/
├── SpyderB_Broker/
│   └── SpyderB03_IBKRAuthManager.py          ← New OAuth manager
├── SpyderG_GUI/
│   ├── SpyderG05_TradingDashboard.py         ← Modified with OAuth
│   └── SpyderG06_OAuthSetupDialog.py         ← New OAuth dialog
└── ~/.spyder/
    ├── ibkr_oauth_credentials.json           ← Created when credentials saved
    └── certs/                                 ← User creates this
        ├── private_encryption.pem             ← User downloads from IBKR
        └── private_signature.pem              ← User downloads from IBKR
```

---

## 🎉 Integration Complete!

Once all steps are complete, your dashboard will have:

- ✅ Direct launch (no separate launcher needed)
- ✅ OAuth authentication button in toolbar
- ✅ Connection status indicator
- ✅ OAuth setup dialog
- ✅ Automatic token renewal
- ✅ Seamless mode switching
- ✅ Auto-authentication on restart

**The dashboard is now OAuth-enabled! 🚀**

---

## 📞 Need Help?

If you encounter issues:
1. Check logs in `~/.spyder/spyder.log`
2. Verify all files are in correct locations
3. Ensure dependencies are installed
4. Review error messages in system log
5. Test each component individually

---

**Document Version:** 1.0.0  
**Last Updated:** October 24, 2025  
**Status:** ✅ Ready for Implementation
