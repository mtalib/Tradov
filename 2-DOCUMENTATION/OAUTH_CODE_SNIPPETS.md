# 🚀 Quick Reference: OAuth Integration Code Snippets

This file contains ready-to-copy code snippets for integrating OAuth into SpyderG05_TradingDashboard.py

---

## 📋 SNIPPET 1: OAuth Imports (Add after existing imports)

```python
# ==============================================================================
# OAUTH AUTHENTICATION IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB03_IBKRAuthManager import (
        IBKRAuthManager, AuthStatus, AccountType
    )
    from SpyderG_GUI.SpyderG06_OAuthSetupDialog import (
        OAuthSetupDialog, show_oauth_setup
    )
    OAUTH_AVAILABLE = True
except ImportError:
    OAUTH_AVAILABLE = False
    print("⚠️ OAuth modules not available - Dashboard will run in simulation only")
```

---

## 📋 SNIPPET 2: OAuth Manager Init (Add in `__init__` method)

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
    except Exception as e:
        self.logger.error(f"OAuth manager initialization failed: {e}")
        self.oauth_manager = None
```

---

## 📋 SNIPPET 3: OAuth Authentication Method (New method)

```python
def attempt_oauth_authentication(self) -> bool:
    """Attempt OAuth authentication with IBKR."""
    if not OAUTH_AVAILABLE or not self.oauth_manager:
        self.add_system_log("⚠️ OAuth not available - running in simulation mode")
        return False
    
    try:
        self.add_system_log("🔐 Attempting OAuth authentication...")
        self.update_connection_status("🟡 AUTHENTICATING WITH IBKR...")
        
        result = self.oauth_manager.authenticate()
        
        if result.success:
            self.oauth_authenticated = True
            self.oauth_account_type = result.account_type
            
            account_type_str = result.account_type.value if result.account_type else "UNKNOWN"
            accounts_str = ", ".join(result.accounts) if result.accounts else "None"
            
            self.add_system_log(f"✅ OAuth authentication successful!")
            self.add_system_log(f"   Account Type: {account_type_str}")
            self.add_system_log(f"   Accounts: {accounts_str}")
            
            status_text = f"✅ IBKR CONNECTED - {account_type_str} TRADING"
            self.update_connection_status(status_text)
            self.account_mode = account_type_str
            
            return True
        else:
            error_msg = result.error_message or "Unknown error"
            self.add_system_log(f"❌ OAuth authentication failed: {error_msg}")
            self.update_connection_status("❌ AUTHENTICATION FAILED - SIMULATION MODE")
            
            if result.status == AuthStatus.NOT_CONFIGURED:
                self.add_system_log("💡 No OAuth credentials found - showing setup dialog")
                QTimer.singleShot(1000, self.show_oauth_setup_dialog)
            
            return False
            
    except Exception as e:
        self.logger.error(f"OAuth authentication error: {e}")
        self.error_handler.handle_error(e, "attempt_oauth_authentication")
        self.add_system_log(f"❌ OAuth authentication error: {str(e)}")
        self.update_connection_status("❌ AUTHENTICATION ERROR - SIMULATION MODE")
        return False
```

---

## 📋 SNIPPET 4: OAuth Setup Dialog Methods (New methods)

```python
def show_oauth_setup_dialog(self):
    """Show OAuth setup dialog for credential configuration."""
    if not OAUTH_AVAILABLE:
        QMessageBox.warning(
            self,
            "OAuth Not Available",
            "OAuth authentication modules are not available.\nPlease check your installation."
        )
        return
    
    try:
        self.add_system_log("🔧 Opening OAuth setup dialog...")
        dialog = OAuthSetupDialog(self.oauth_manager, self)
        dialog.credentials_saved.connect(self._on_oauth_credentials_saved)
        dialog.exec()
    except Exception as e:
        self.logger.error(f"Failed to show OAuth setup dialog: {e}")
        QMessageBox.critical(self, "Error", f"Failed to open OAuth setup dialog:\n{str(e)}")

def _on_oauth_credentials_saved(self, credentials_info: dict):
    """Handle OAuth credentials saved event."""
    self.add_system_log(f"✅ OAuth credentials saved: {credentials_info.get('account_type', 'UNKNOWN')}")
    self.add_system_log("🔄 Attempting authentication with new credentials...")
    QTimer.singleShot(500, self.attempt_oauth_authentication)
```

---

## 📋 SNIPPET 5: Auto-Authentication (Add at end of `__init__`)

```python
# ==================================================================
# AUTO OAUTH AUTHENTICATION
# ==================================================================
if OAUTH_AVAILABLE and self.oauth_manager:
    QTimer.singleShot(2000, self._auto_authenticate)
else:
    self.add_system_log("ℹ️ Running in simulation mode (OAuth not available)")
    self.update_connection_status("🟡 SIMULATION MODE")
```

---

## 📋 SNIPPET 6: Auto-Authenticate Method (New method)

```python
def _auto_authenticate(self):
    """Auto-authenticate on startup if credentials are configured."""
    if not self.oauth_manager:
        return
    
    credentials = self.oauth_manager.load_credentials()
    
    if credentials:
        self.add_system_log("🔑 Found saved OAuth credentials - authenticating...")
        self.attempt_oauth_authentication()
    else:
        self.add_system_log("ℹ️ No OAuth credentials configured")
        self.add_system_log("💡 Click 'Authenticate' button to set up OAuth")
        self.update_connection_status("🟡 SIMULATION MODE - NOT AUTHENTICATED")
```

---

## 📋 SNIPPET 7: OAuth Button in Toolbar (Add to toolbar setup)

```python
# OAuth Authentication button
if OAUTH_AVAILABLE:
    self.oauth_btn = QPushButton("🔐 Authenticate")
    self.oauth_btn.setToolTip("Configure and authenticate with IBKR OAuth")
    self.oauth_btn.clicked.connect(self.show_oauth_setup_dialog)
    self.oauth_btn.setStyleSheet("""
        QPushButton {
            background-color: #2a2a2a;
            color: #4CAF50;
            border: 1px solid #4CAF50;
            padding: 5px 15px;
            border-radius: 3px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #4CAF50;
            color: black;
        }
    """)
    toolbar_layout.addWidget(self.oauth_btn)
    
    # OAuth status indicator
    self.oauth_status_label = QLabel("🔓 Not Authenticated")
    self.oauth_status_label.setStyleSheet("color: #999; padding: 5px;")
    toolbar_layout.addWidget(self.oauth_status_label)
```

---

## 📋 SNIPPET 8: Enhanced Connection Status Update (Modify existing method)

```python
def update_connection_status(self, status_text: str):
    """Update connection status display."""
    if hasattr(self, 'connection_status_label'):
        self.connection_status_label.setText(status_text)
    
    # Update OAuth status indicator
    if hasattr(self, 'oauth_status_label'):
        if self.oauth_authenticated:
            account_str = self.oauth_account_type.value if self.oauth_account_type else "UNKNOWN"
            self.oauth_status_label.setText(f"🔐 {account_str}")
            self.oauth_status_label.setStyleSheet("color: #4CAF50; padding: 5px; font-weight: bold;")
        else:
            self.oauth_status_label.setText("🔓 Simulation")
            self.oauth_status_label.setStyleSheet("color: #999; padding: 5px;")
```

---

## 🎯 Application Order

1. **Add imports** (Snippet 1) - Top of file
2. **Add OAuth manager init** (Snippet 2) - In `__init__` method (early)
3. **Add OAuth button** (Snippet 7) - In toolbar/UI setup
4. **Add auto-authentication** (Snippet 5) - At end of `__init__`
5. **Add all new methods** (Snippets 3, 4, 6, 8) - Anywhere in class

---

## ✅ Verification Checklist

After adding all snippets:
- [ ] No syntax errors
- [ ] Imports at top of file
- [ ] OAuth manager initialized in `__init__`
- [ ] OAuth button visible in toolbar
- [ ] Auto-authentication at end of `__init__`
- [ ] All new methods added to class
- [ ] Connection status update enhanced
- [ ] Code follows GLM-Specs format

---

## 🚀 Quick Test

After implementation:
```bash
# Test dashboard launch
python ~/Projects/Spyder/SpyderG_GUI/SpyderG05_TradingDashboard.py

# Expected behavior:
# ✅ Dashboard opens in <1 second
# ✅ Shows "SIMULATION MODE" initially
# ✅ OAuth button visible in toolbar
# ✅ System log shows initialization messages
# ✅ Click OAuth button → Setup dialog opens
```

---

## 📝 Notes

- All code follows GLM-Specs Python format standards
- Error handling included in all methods
- Logging statements for debugging
- Graceful fallback to simulation mode
- User-friendly status updates
- Type hints for clarity

**Ready to integrate!** 🎉
