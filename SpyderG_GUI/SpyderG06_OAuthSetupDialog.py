#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG06_OAuthSetupDialog.py
Purpose: User-friendly OAuth credential setup dialog for IBKR authentication

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-24 Time: 16:15:00

Module Description:
    This module provides a comprehensive dialog for setting up IBKR OAuth
    credentials within the Spyder Dashboard. It guides users through the
    OAuth setup process with clear instructions, validation, and secure
    credential storage.

Module Constants:
    IBKR_PORTAL_URL (str): URL to IBKR OAuth setup portal
    MIN_DIALOG_WIDTH (int): Minimum dialog width in pixels
    MIN_DIALOG_HEIGHT (int): Minimum dialog height in pixels

Dependencies:
    - PySide6: Qt GUI framework
    - SpyderB03_IBKRAuthManager: OAuth authentication management
    - pathlib: File path handling

Change Log:
    2025-10-24 (v1.0.0):
        - Initial module creation
        - OAuth credential input interface
        - Certificate file selection
        - Connection testing functionality
        - Secure credential validation
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox, QFileDialog,
    QTextEdit, QMessageBox, QWidget, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QIcon

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB03_IBKRAuthManager import (
        IBKRAuthManager, OAuthCredentials, AccountType, AuthStatus
    )
    AUTH_MANAGER_AVAILABLE = True
except ImportError:
    AUTH_MANAGER_AVAILABLE = False
    print("⚠️ SpyderB03_IBKRAuthManager not available")

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    SpyderLogger = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
IBKR_PORTAL_URL = "https://portal.interactivebrokers.com"
MIN_DIALOG_WIDTH = 700
MIN_DIALOG_HEIGHT = 800

# Help text
HELP_TEXT = """
<h3>IBKR OAuth Setup Guide</h3>

<h4>Step 1: Get OAuth Credentials from IBKR</h4>
<ol>
<li>Go to <a href="https://portal.interactivebrokers.com">IBKR Portal</a></li>
<li>Navigate to: <b>Settings → API → OAuth Apps</b></li>
<li>Click <b>"Create OAuth Consumer Key"</b></li>
<li>Copy the generated credentials</li>
</ol>

<h4>Step 2: Download Certificates</h4>
<ol>
<li>In the same OAuth Apps section</li>
<li>Download <b>Encryption Certificate</b> (private_encryption.pem)</li>
<li>Download <b>Signature Certificate</b> (private_signature.pem)</li>
<li>Save both to a secure location (e.g., ~/.spyder/certs/)</li>
</ol>

<h4>Step 3: Enter Credentials Here</h4>
<ol>
<li>Select your account type (Paper or Live)</li>
<li>Paste your Consumer Key and Secret</li>
<li>Paste your OAuth Token and Secret</li>
<li>Browse to select your certificate files</li>
<li>Click "Test Connection" to verify</li>
<li>Click "Save & Connect" to authenticate</li>
</ol>

<h4>Security Notes:</h4>
<ul>
<li>Credentials are stored encrypted locally</li>
<li>Never share your OAuth secrets</li>
<li>Keep certificate files secure (chmod 600)</li>
<li>Tokens automatically renew</li>
</ul>
"""

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class OAuthSetupDialog(QDialog):
    """
    OAuth credential setup dialog for IBKR authentication.
    
    This dialog provides a user-friendly interface for configuring OAuth
    credentials, selecting certificate files, testing connections, and
    saving configurations securely.
    
    Signals:
        credentials_saved: Emitted when credentials are successfully saved
        connection_successful: Emitted when OAuth connection succeeds
    """
    
    # Signals
    credentials_saved = Signal(dict)  # Emits credential info when saved
    connection_successful = Signal()  # Emits when connection succeeds
    
    def __init__(self, auth_manager: Optional[IBKRAuthManager] = None, parent: Optional[QWidget] = None):
        """
        Initialize the OAuth setup dialog.
        
        Args:
            auth_manager: Optional OAuth authentication manager instance
            parent: Optional parent widget
        """
        super().__init__(parent)
        
        # Setup logger
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)
        
        # Auth manager
        self.auth_manager = auth_manager
        if not self.auth_manager and AUTH_MANAGER_AVAILABLE:
            self.auth_manager = IBKRAuthManager()
            self.auth_manager.initialize()
        
        # Setup UI
        self._setup_ui()
        self._load_existing_credentials()
        
        self.logger.info("OAuth setup dialog initialized")
    
    # ==========================================================================
    # UI SETUP
    # ==========================================================================
    
    def _setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("IBKR OAuth Authentication Setup")
        self.setMinimumSize(MIN_DIALOG_WIDTH, MIN_DIALOG_HEIGHT)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("🔐 IBKR OAuth Configuration")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Configure OAuth credentials for IBKR API authentication")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666; font-size: 10pt;")
        main_layout.addWidget(subtitle)
        
        # Credential form
        main_layout.addWidget(self._create_credential_form())
        
        # Help section (collapsible)
        main_layout.addWidget(self._create_help_section())
        
        # Status area
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        self.status_text.setPlaceholderText("Connection status will appear here...")
        main_layout.addWidget(self.status_text)
        
        # Buttons
        main_layout.addWidget(self._create_button_panel())
        
        # Apply dark theme styling
        self._apply_styling()
    
    def _create_credential_form(self) -> QGroupBox:
        """Create the credential input form"""
        group = QGroupBox("OAuth Credentials")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # Account type selector
        self.account_type_combo = QComboBox()
        self.account_type_combo.addItems(["PAPER TRADING", "LIVE TRADING"])
        self.account_type_combo.setToolTip("Select Paper Trading for simulation or Live Trading for real money")
        form_layout.addRow("Account Type:", self.account_type_combo)
        
        # Consumer key
        self.consumer_key_input = QLineEdit()
        self.consumer_key_input.setPlaceholderText("Enter Consumer Key from IBKR Portal")
        self.consumer_key_input.setToolTip("Consumer Key from IBKR OAuth settings")
        form_layout.addRow("Consumer Key:", self.consumer_key_input)
        
        # Consumer secret
        self.consumer_secret_input = QLineEdit()
        self.consumer_secret_input.setPlaceholderText("Enter Consumer Secret")
        self.consumer_secret_input.setEchoMode(QLineEdit.Password)
        self.consumer_secret_input.setToolTip("Consumer Secret from IBKR OAuth settings")
        form_layout.addRow("Consumer Secret:", self.consumer_secret_input)
        
        # OAuth token
        self.oauth_token_input = QLineEdit()
        self.oauth_token_input.setPlaceholderText("Enter OAuth Token")
        self.oauth_token_input.setToolTip("OAuth Token from IBKR Portal")
        form_layout.addRow("OAuth Token:", self.oauth_token_input)
        
        # OAuth token secret
        self.oauth_token_secret_input = QLineEdit()
        self.oauth_token_secret_input.setPlaceholderText("Enter OAuth Token Secret")
        self.oauth_token_secret_input.setEchoMode(QLineEdit.Password)
        self.oauth_token_secret_input.setToolTip("OAuth Token Secret from IBKR Portal")
        form_layout.addRow("OAuth Token Secret:", self.oauth_token_secret_input)
        
        # Encryption certificate
        cert_layout1 = QHBoxLayout()
        self.encryption_cert_input = QLineEdit()
        self.encryption_cert_input.setPlaceholderText("Select encryption certificate file...")
        self.encryption_cert_input.setReadOnly(True)
        cert_btn1 = QPushButton("Browse...")
        cert_btn1.clicked.connect(self._browse_encryption_cert)
        cert_layout1.addWidget(self.encryption_cert_input)
        cert_layout1.addWidget(cert_btn1)
        form_layout.addRow("Encryption Cert:", cert_layout1)
        
        # Signature certificate
        cert_layout2 = QHBoxLayout()
        self.signature_cert_input = QLineEdit()
        self.signature_cert_input.setPlaceholderText("Select signature certificate file...")
        self.signature_cert_input.setReadOnly(True)
        cert_btn2 = QPushButton("Browse...")
        cert_btn2.clicked.connect(self._browse_signature_cert)
        cert_layout2.addWidget(self.signature_cert_input)
        cert_layout2.addWidget(cert_btn2)
        form_layout.addRow("Signature Cert:", cert_layout2)
        
        group.setLayout(form_layout)
        return group
    
    def _create_help_section(self) -> QGroupBox:
        """Create collapsible help section"""
        group = QGroupBox("Setup Instructions")
        layout = QVBoxLayout()
        
        # Toggle button
        toggle_btn = QPushButton("▼ Show Setup Guide")
        toggle_btn.setCheckable(True)
        toggle_btn.setStyleSheet("text-align: left; padding: 5px;")
        
        # Help text
        help_display = QTextEdit()
        help_display.setReadOnly(True)
        help_display.setHtml(HELP_TEXT)
        help_display.setMaximumHeight(300)
        help_display.setVisible(False)
        help_display.setOpenExternalLinks(True)
        
        # Toggle functionality
        def toggle_help():
            is_visible = help_display.isVisible()
            help_display.setVisible(not is_visible)
            toggle_btn.setText("▲ Hide Setup Guide" if not is_visible else "▼ Show Setup Guide")
        
        toggle_btn.clicked.connect(toggle_help)
        
        layout.addWidget(toggle_btn)
        layout.addWidget(help_display)
        
        group.setLayout(layout)
        return group
    
    def _create_button_panel(self) -> QWidget:
        """Create button panel"""
        panel = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(10)
        
        # Open IBKR Portal button
        self.portal_btn = QPushButton("🌐 Open IBKR Portal")
        self.portal_btn.setToolTip("Open IBKR Portal in browser to get OAuth credentials")
        self.portal_btn.clicked.connect(self._open_ibkr_portal)
        layout.addWidget(self.portal_btn)
        
        layout.addStretch()
        
        # Test connection button
        self.test_btn = QPushButton("🧪 Test Connection")
        self.test_btn.setToolTip("Test OAuth connection with provided credentials")
        self.test_btn.clicked.connect(self._test_connection)
        layout.addWidget(self.test_btn)
        
        # Save button
        self.save_btn = QPushButton("💾 Save & Connect")
        self.save_btn.setToolTip("Save credentials and authenticate with IBKR")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save_and_connect)
        layout.addWidget(self.save_btn)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)
        
        panel.setLayout(layout)
        return panel
    
    def _apply_styling(self):
        """Apply dark theme styling"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QGroupBox {
                border: 2px solid #3c3c3c;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: #00ff88;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                padding: 5px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #00ff88;
            }
            QComboBox {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                padding: 5px;
                color: #ffffff;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
                margin-right: 5px;
            }
            QPushButton {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                padding: 8px 15px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
                border: 1px solid #00ff88;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
            QPushButton:default {
                background-color: #00ff88;
                color: #000000;
                font-weight: bold;
            }
            QPushButton:default:hover {
                background-color: #00dd77;
            }
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                padding: 5px;
                color: #ffffff;
            }
        """)
    
    # ==========================================================================
    # FUNCTIONALITY
    # ==========================================================================
    
    def _load_existing_credentials(self):
        """Load existing credentials if available"""
        if not self.auth_manager or not self.auth_manager.has_credentials():
            return
        
        try:
            creds = self.auth_manager.credentials
            if creds:
                # Set account type
                index = 0 if creds.account_type == AccountType.PAPER else 1
                self.account_type_combo.setCurrentIndex(index)
                
                # Set credentials
                self.consumer_key_input.setText(creds.consumer_key)
                self.consumer_secret_input.setText(creds.consumer_secret)
                self.oauth_token_input.setText(creds.oauth_token)
                self.oauth_token_secret_input.setText(creds.oauth_token_secret)
                self.encryption_cert_input.setText(creds.encryption_cert_path)
                self.signature_cert_input.setText(creds.signature_cert_path)
                
                self._add_status("✅ Loaded existing credentials", "green")
        
        except Exception as e:
            self.logger.error(f"Failed to load existing credentials: {e}")
    
    def _browse_encryption_cert(self):
        """Browse for encryption certificate file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Encryption Certificate",
            str(Path.home() / ".spyder" / "certs"),
            "Certificate Files (*.pem *.crt);;All Files (*)"
        )
        if file_path:
            self.encryption_cert_input.setText(file_path)
    
    def _browse_signature_cert(self):
        """Browse for signature certificate file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Signature Certificate",
            str(Path.home() / ".spyder" / "certs"),
            "Certificate Files (*.pem *.crt);;All Files (*)"
        )
        if file_path:
            self.signature_cert_input.setText(file_path)
    
    def _open_ibkr_portal(self):
        """Open IBKR portal in browser"""
        try:
            import webbrowser
            webbrowser.open(IBKR_PORTAL_URL)
            self._add_status("🌐 Opened IBKR Portal in browser", "blue")
        except Exception as e:
            self.logger.error(f"Failed to open browser: {e}")
            QMessageBox.warning(self, "Error", f"Could not open browser:\n{str(e)}")
    
    def _validate_inputs(self) -> tuple[bool, str]:
        """
        Validate all input fields.
        
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        # Check all required fields
        if not self.consumer_key_input.text().strip():
            return False, "Consumer Key is required"
        
        if not self.consumer_secret_input.text().strip():
            return False, "Consumer Secret is required"
        
        if not self.oauth_token_input.text().strip():
            return False, "OAuth Token is required"
        
        if not self.oauth_token_secret_input.text().strip():
            return False, "OAuth Token Secret is required"
        
        if not self.encryption_cert_input.text().strip():
            return False, "Encryption Certificate is required"
        
        if not self.signature_cert_input.text().strip():
            return False, "Signature Certificate is required"
        
        # Check certificate files exist
        enc_cert = self.encryption_cert_input.text()
        if not os.path.exists(enc_cert):
            return False, f"Encryption certificate not found: {enc_cert}"
        
        sig_cert = self.signature_cert_input.text()
        if not os.path.exists(sig_cert):
            return False, f"Signature certificate not found: {sig_cert}"
        
        return True, ""
    
    def _create_credentials_object(self) -> OAuthCredentials:
        """Create OAuthCredentials object from form inputs"""
        account_type = (AccountType.PAPER if self.account_type_combo.currentIndex() == 0 
                       else AccountType.LIVE)
        
        return OAuthCredentials(
            consumer_key=self.consumer_key_input.text().strip(),
            consumer_secret=self.consumer_secret_input.text().strip(),
            oauth_token=self.oauth_token_input.text().strip(),
            oauth_token_secret=self.oauth_token_secret_input.text().strip(),
            encryption_cert_path=self.encryption_cert_input.text().strip(),
            signature_cert_path=self.signature_cert_input.text().strip(),
            account_type=account_type
        )
    
    def _test_connection(self):
        """Test OAuth connection with provided credentials"""
        # Validate inputs
        valid, error = self._validate_inputs()
        if not valid:
            QMessageBox.warning(self, "Validation Error", error)
            return
        
        if not self.auth_manager:
            QMessageBox.critical(self, "Error", "Auth manager not available")
            return
        
        try:
            self._add_status("🔄 Testing connection...", "blue")
            self.test_btn.setEnabled(False)
            
            # Create credentials
            creds = self._create_credentials_object()
            
            # Save temporarily
            self.auth_manager.save_credentials(creds)
            
            # Test authentication
            QTimer.singleShot(100, lambda: self._perform_test_authentication())
            
        except Exception as e:
            self.logger.error(f"Test connection error: {e}")
            self._add_status(f"❌ Test failed: {str(e)}", "red")
            self.test_btn.setEnabled(True)
    
    def _perform_test_authentication(self):
        """Perform the actual test authentication"""
        try:
            success = self.auth_manager.authenticate()
            
            if success:
                # Test connection
                test_ok, message = self.auth_manager.test_connection()
                
                if test_ok:
                    self._add_status(f"✅ Connection successful! {message}", "green")
                    QMessageBox.information(
                        self,
                        "Connection Successful",
                        f"OAuth connection established successfully!\n\n{message}"
                    )
                else:
                    self._add_status(f"⚠️ Authentication succeeded but connection test failed: {message}", "orange")
                
                # Disconnect after test
                self.auth_manager.disconnect()
            else:
                error_msg = self.auth_manager.status.error_message or "Unknown error"
                self._add_status(f"❌ Authentication failed: {error_msg}", "red")
                QMessageBox.critical(
                    self,
                    "Connection Failed",
                    f"OAuth authentication failed:\n\n{error_msg}"
                )
        
        except Exception as e:
            self.logger.error(f"Test authentication error: {e}")
            self._add_status(f"❌ Error: {str(e)}", "red")
        
        finally:
            self.test_btn.setEnabled(True)
    
    def _save_and_connect(self):
        """Save credentials and authenticate"""
        # Validate inputs
        valid, error = self._validate_inputs()
        if not valid:
            QMessageBox.warning(self, "Validation Error", error)
            return
        
        if not self.auth_manager:
            QMessageBox.critical(self, "Error", "Auth manager not available")
            return
        
        try:
            self._add_status("💾 Saving credentials...", "blue")
            self.save_btn.setEnabled(False)
            
            # Create and save credentials
            creds = self._create_credentials_object()
            if not self.auth_manager.save_credentials(creds):
                raise Exception("Failed to save credentials")
            
            self._add_status("✅ Credentials saved", "green")
            
            # Authenticate
            self._add_status("🔄 Authenticating with IBKR...", "blue")
            success = self.auth_manager.authenticate()
            
            if success:
                self._add_status("✅ Authentication successful!", "green")
                
                # Emit signals
                self.credentials_saved.emit({
                    'account_type': creds.account_type.value,
                    'consumer_key': creds.consumer_key
                })
                self.connection_successful.emit()
                
                # Show success and close
                QMessageBox.information(
                    self,
                    "Success",
                    "OAuth credentials saved and authenticated successfully!\n\n"
                    "The dashboard will now connect to IBKR."
                )
                
                self.accept()
            else:
                error_msg = self.auth_manager.status.error_message or "Unknown error"
                self._add_status(f"❌ Authentication failed: {error_msg}", "red")
                QMessageBox.critical(
                    self,
                    "Authentication Failed",
                    f"Failed to authenticate with IBKR:\n\n{error_msg}\n\n"
                    "Please check your credentials and try again."
                )
                self.save_btn.setEnabled(True)
        
        except Exception as e:
            self.logger.error(f"Save and connect error: {e}")
            self._add_status(f"❌ Error: {str(e)}", "red")
            QMessageBox.critical(self, "Error", f"An error occurred:\n\n{str(e)}")
            self.save_btn.setEnabled(True)
    
    def _add_status(self, message: str, color: str = "white"):
        """Add a status message to the status text area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        colored_message = f'<span style="color: {color};">[{timestamp}] {message}</span>'
        self.status_text.append(colored_message)
        
        # Auto-scroll to bottom
        cursor = self.status_text.textCursor()
        cursor.movePosition(cursor.End)
        self.status_text.setTextCursor(cursor)


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def show_oauth_setup(auth_manager: Optional[IBKRAuthManager] = None, 
                     parent: Optional[QWidget] = None) -> bool:
    """
    Show the OAuth setup dialog and return whether setup was successful.
    
    Args:
        auth_manager: Optional OAuth authentication manager
        parent: Optional parent widget
        
    Returns:
        bool: True if setup completed successfully
    """
    dialog = OAuthSetupDialog(auth_manager, parent)
    return dialog.exec() == QDialog.Accepted


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    
    print("=" * 70)
    print("SpyderG06_OAuthSetupDialog - OAuth Setup Dialog")
    print("=" * 70)
    print(f"Auth Manager Available: {AUTH_MANAGER_AVAILABLE}")
    print("=" * 70)
    
    # Test the dialog
    app = QApplication(sys.argv)
    
    if AUTH_MANAGER_AVAILABLE:
        auth_manager = IBKRAuthManager()
        auth_manager.initialize()
        dialog = OAuthSetupDialog(auth_manager)
        dialog.show()
        sys.exit(app.exec())
    else:
        print("⚠️ Auth manager not available - cannot test dialog")
