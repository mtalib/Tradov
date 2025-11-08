#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG06_OAuthSetupDialog.py
Purpose: User-friendly OAuth credential setup dialog for IBKR authentication

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-24 Time: 15:00:00

Module Description:
    This module provides a comprehensive dialog for setting up IBKR OAuth
    credentials within the Spyder Dashboard. It guides users through the
    OAuth setup process with clear instructions, validation, and secure
    credential storage.

Module Constants:
    IBKR_PORTAL_URL (str): URL to IBKR Portal for OAuth setup
    CERT_FOLDER (Path): Default folder for certificate storage
    MIN_KEY_LENGTH (int): Minimum length for OAuth keys (default: 10)

Features:
    - Step-by-step OAuth setup wizard
    - Interactive help and instructions
    - Certificate file browser
    - Credential validation
    - Secure storage with confirmation
    - Test authentication capability

Change Log:
    2025-10-24 (v1.0.0):
        - Initial dialog creation
        - OAuth credential input form
        - Certificate file selection
        - Validation and testing
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

# ==============================================================================
# THIRD-PARTY IMPORTS - PySide6
# ==============================================================================
try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
        QLabel, QLineEdit, QPushButton, QFileDialog,
        QTextEdit, QGroupBox, QComboBox, QMessageBox,
        QProgressBar, QTabWidget, QWidget, QCheckBox
    )
    from PySide6.QtCore import Qt, Signal, QThread
    from PySide6.QtGui import QFont, QIcon
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    print("⚠️ PySide6 not available - OAuth Setup Dialog requires GUI")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Conditional import of auth manager
try:
    from SpyderB_Broker.SpyderB03_IBKRAuthManager import (
        IBKRAuthManager, OAuthCredentials, AuthenticationResult
    )
    AUTH_MANAGER_AVAILABLE = True
except ImportError:
    AUTH_MANAGER_AVAILABLE = False
    print("⚠️ IBKRAuthManager not available")

# ==============================================================================
# CONSTANTS
# ==============================================================================
IBKR_PORTAL_URL = "https://portal.interactivebrokers.com"
CERT_FOLDER = Path.home() / ".spyder" / "certs"
MIN_KEY_LENGTH = 10

# ==============================================================================
# AUTHENTICATION TEST WORKER
# ==============================================================================
if PYSIDE6_AVAILABLE:
    class AuthTestWorker(QThread):
        """Worker thread for testing OAuth authentication"""
        
        finished = Signal(bool, str)  # success, message
        
        def __init__(self, auth_manager: 'IBKRAuthManager'):
            super().__init__()
            self.auth_manager = auth_manager
            self.logger = SpyderLogger.get_logger(__name__)
        
        def run(self):
            """Run authentication test"""
            try:
                self.logger.info("Testing OAuth authentication...")
                result = self.auth_manager.authenticate()
                
                if result.success:
                    msg = (f"✅ Authentication successful!\n\n"
                           f"Account Type: {result.account_type.value}\n"
                           f"Accounts: {', '.join(result.accounts)}")
                    self.finished.emit(True, msg)
                else:
                    msg = f"❌ Authentication failed:\n{result.error_message}"
                    self.finished.emit(False, msg)
                    
            except Exception as e:
                self.logger.error(f"Authentication test failed: {e}")
                self.finished.emit(False, f"❌ Error: {str(e)}")

# ==============================================================================
# MAIN DIALOG CLASS
# ==============================================================================
if PYSIDE6_AVAILABLE:
    class OAuthSetupDialog(QDialog):
        """
        OAuth credential setup dialog for IBKR authentication.
        
        This dialog provides a user-friendly interface for setting up OAuth
        credentials, including file selection, validation, and testing.
        
        Signals:
            credentials_saved: Emitted when credentials are successfully saved
        """
        
        credentials_saved = Signal(dict)
        
        def __init__(self, auth_manager: Optional['IBKRAuthManager'] = None, parent=None):
            """
            Initialize OAuth Setup Dialog.
            
            Args:
                auth_manager: Optional IBKRAuthManager instance
                parent: Parent widget
            """
            super().__init__(parent)
            
            # Initialize logging
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
            
            # Auth manager
            self.auth_manager = auth_manager
            
            # Test worker
            self.test_worker: Optional[AuthTestWorker] = None
            
            # Setup UI
            self.setWindowTitle("SPYDER - IBKR OAuth Setup")
            self.setMinimumSize(700, 800)
            self.setModal(True)
            
            self._create_ui()
            self._load_existing_credentials()
            
            self.logger.info("OAuth Setup Dialog initialized")
        
        # ======================================================================
        # UI CREATION
        # ======================================================================
        def _create_ui(self):
            """Create the dialog UI"""
            layout = QVBoxLayout(self)
            layout.setSpacing(15)
            
            # Title
            title = QLabel("🔐 IBKR OAuth Authentication Setup")
            title_font = QFont()
            title_font.setPointSize(14)
            title_font.setBold(True)
            title.setFont(title_font)
            title.setAlignment(Qt.AlignCenter)
            layout.addWidget(title)
            
            # Instructions
            instructions = self._create_instructions_widget()
            layout.addWidget(instructions)
            
            # Tab widget for setup and help
            tabs = QTabWidget()
            tabs.addTab(self._create_credentials_tab(), "OAuth Credentials")
            tabs.addTab(self._create_certificates_tab(), "Certificates")
            tabs.addTab(self._create_help_tab(), "Setup Guide")
            layout.addWidget(tabs)
            
            # Buttons
            button_layout = self._create_button_layout()
            layout.addLayout(button_layout)
        
        def _create_instructions_widget(self) -> QGroupBox:
            """Create instructions section"""
            group = QGroupBox("Quick Start")
            layout = QVBoxLayout(group)
            
            instructions = QLabel(
                "To use OAuth authentication with IBKR:\n\n"
                "1️⃣ Go to IBKR Portal and create OAuth Consumer Key\n"
                "2️⃣ Download the encryption and signature certificates\n"
                "3️⃣ Enter your OAuth credentials below\n"
                "4️⃣ Select your certificate files\n"
                "5️⃣ Test the connection\n"
                "6️⃣ Save credentials for automatic authentication"
            )
            instructions.setWordWrap(True)
            layout.addWidget(instructions)
            
            # Portal button
            portal_btn = QPushButton("🌐 Open IBKR Portal")
            portal_btn.clicked.connect(self._open_ibkr_portal)
            layout.addWidget(portal_btn)
            
            return group
        
        def _create_credentials_tab(self) -> QWidget:
            """Create credentials input tab"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            # Account type selection
            account_group = QGroupBox("Account Type")
            account_layout = QFormLayout(account_group)
            
            self.account_type_combo = QComboBox()
            self.account_type_combo.addItems(["PAPER", "LIVE"])
            account_layout.addRow("Account Type:", self.account_type_combo)
            layout.addWidget(account_group)
            
            # OAuth credentials
            creds_group = QGroupBox("OAuth Credentials")
            creds_layout = QFormLayout(creds_group)
            
            self.consumer_key_input = QLineEdit()
            self.consumer_key_input.setPlaceholderText("Enter Consumer Key from IBKR Portal")
            creds_layout.addRow("Consumer Key:*", self.consumer_key_input)
            
            self.consumer_secret_input = QLineEdit()
            self.consumer_secret_input.setEchoMode(QLineEdit.Password)
            self.consumer_secret_input.setPlaceholderText("Enter Consumer Secret")
            
            show_secret_btn = QPushButton("👁")
            show_secret_btn.setMaximumWidth(40)
            show_secret_btn.setCheckable(True)
            show_secret_btn.toggled.connect(
                lambda checked: self.consumer_secret_input.setEchoMode(
                    QLineEdit.Normal if checked else QLineEdit.Password
                )
            )
            
            secret_layout = QHBoxLayout()
            secret_layout.addWidget(self.consumer_secret_input)
            secret_layout.addWidget(show_secret_btn)
            creds_layout.addRow("Consumer Secret:*", secret_layout)
            
            self.oauth_token_input = QLineEdit()
            self.oauth_token_input.setPlaceholderText("Enter OAuth Token")
            creds_layout.addRow("OAuth Token:*", self.oauth_token_input)
            
            self.oauth_secret_input = QLineEdit()
            self.oauth_secret_input.setEchoMode(QLineEdit.Password)
            self.oauth_secret_input.setPlaceholderText("Enter OAuth Token Secret")
            
            show_token_btn = QPushButton("👁")
            show_token_btn.setMaximumWidth(40)
            show_token_btn.setCheckable(True)
            show_token_btn.toggled.connect(
                lambda checked: self.oauth_secret_input.setEchoMode(
                    QLineEdit.Normal if checked else QLineEdit.Password
                )
            )
            
            token_layout = QHBoxLayout()
            token_layout.addWidget(self.oauth_secret_input)
            token_layout.addWidget(show_token_btn)
            creds_layout.addRow("OAuth Token Secret:*", token_layout)
            
            layout.addWidget(creds_group)
            
            return widget
        
        def _create_certificates_tab(self) -> QWidget:
            """Create certificates selection tab"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            cert_group = QGroupBox("Certificate Files")
            cert_layout = QFormLayout(cert_group)
            
            # Encryption certificate
            self.encryption_path_input = QLineEdit()
            self.encryption_path_input.setReadOnly(True)
            self.encryption_path_input.setPlaceholderText("Select encryption certificate (.pem)")
            
            encryption_btn = QPushButton("📁 Browse")
            encryption_btn.clicked.connect(lambda: self._select_certificate('encryption'))
            
            encryption_layout = QHBoxLayout()
            encryption_layout.addWidget(self.encryption_path_input)
            encryption_layout.addWidget(encryption_btn)
            cert_layout.addRow("Encryption Key:*", encryption_layout)
            
            # Signature certificate
            self.signature_path_input = QLineEdit()
            self.signature_path_input.setReadOnly(True)
            self.signature_path_input.setPlaceholderText("Select signature certificate (.pem)")
            
            signature_btn = QPushButton("📁 Browse")
            signature_btn.clicked.connect(lambda: self._select_certificate('signature'))
            
            signature_layout = QHBoxLayout()
            signature_layout.addWidget(self.signature_path_input)
            signature_layout.addWidget(signature_btn)
            cert_layout.addRow("Signature Key:*", signature_layout)
            
            layout.addWidget(cert_group)
            
            # Certificate info
            info_label = QLabel(
                "ℹ️ Certificate files are downloaded from IBKR Portal when\n"
                "you create your OAuth Consumer Key. They should be\n"
                "stored securely (e.g., in ~/.spyder/certs/)."
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet("color: #666; font-style: italic;")
            layout.addWidget(info_label)
            
            layout.addStretch()
            
            return widget
        
        def _create_help_tab(self) -> QWidget:
            """Create help/documentation tab"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            help_text = QTextEdit()
            help_text.setReadOnly(True)
            help_text.setHtml("""
            <h2>📚 OAuth Setup Guide</h2>
            
            <h3>Step 1: Access IBKR Portal</h3>
            <p>Go to <a href="https://portal.interactivebrokers.com">portal.interactivebrokers.com</a> 
            and log in with your IBKR credentials.</p>
            
            <h3>Step 2: Create OAuth Consumer Key</h3>
            <ol>
                <li>Navigate to Settings → API → OAuth Apps</li>
                <li>Click "Create OAuth Consumer Key"</li>
                <li>Follow the prompts to generate your credentials</li>
                <li>Download the encryption and signature certificates</li>
            </ol>
            
            <h3>Step 3: Store Certificates Securely</h3>
            <p>Save your certificate files in a secure location, such as:</p>
            <code>~/.spyder/certs/private_encryption.pem<br>
            ~/.spyder/certs/private_signature.pem</code>
            
            <h3>Step 4: Enter Credentials</h3>
            <p>Enter your OAuth credentials in the "OAuth Credentials" tab:</p>
            <ul>
                <li><b>Consumer Key:</b> From IBKR Portal OAuth settings</li>
                <li><b>Consumer Secret:</b> Generated by IBKR</li>
                <li><b>OAuth Token:</b> Your access token</li>
                <li><b>OAuth Token Secret:</b> Your token secret</li>
            </ul>
            
            <h3>Step 5: Select Certificates</h3>
            <p>Use the "Certificates" tab to select your downloaded certificate files.</p>
            
            <h3>Step 6: Test Connection</h3>
            <p>Click "Test Connection" to verify your OAuth setup works correctly.</p>
            
            <h3>Step 7: Save & Connect</h3>
            <p>Once tested successfully, click "Save & Connect" to store your credentials 
            and enable automatic authentication.</p>
            
            <hr>
            <h3>🔐 Security Notes</h3>
            <ul>
                <li>Credentials are stored locally with restricted file permissions</li>
                <li>Never share your OAuth credentials or certificate files</li>
                <li>Keep your IBKR Portal password secure</li>
                <li>Regularly rotate your OAuth tokens</li>
            </ul>
            
            <hr>
            <h3>❓ Troubleshooting</h3>
            <p><b>Connection fails:</b> Verify your credentials are correct and certificates are valid</p>
            <p><b>Certificate errors:</b> Ensure .pem files are from IBKR and not corrupted</p>
            <p><b>Account type mismatch:</b> Make sure you selected the correct account type (Paper/Live)</p>
            
            <hr>
            <p><i>For more information, visit the 
            <a href="https://www.interactivebrokers.com/en/index.php?f=5041">IBKR API Documentation</a></i></p>
            """)
            layout.addWidget(help_text)
            
            return widget
        
        def _create_button_layout(self) -> QHBoxLayout:
            """Create button layout"""
            layout = QHBoxLayout()
            
            # Test button
            self.test_btn = QPushButton("🧪 Test Connection")
            self.test_btn.clicked.connect(self._test_connection)
            layout.addWidget(self.test_btn)
            
            layout.addStretch()
            
            # Cancel button
            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(self.reject)
            layout.addWidget(cancel_btn)
            
            # Save button
            self.save_btn = QPushButton("💾 Save & Connect")
            self.save_btn.setDefault(True)
            self.save_btn.clicked.connect(self._save_credentials)
            layout.addWidget(self.save_btn)
            
            return layout
        
        # ======================================================================
        # EVENT HANDLERS
        # ======================================================================
        def _open_ibkr_portal(self):
            """Open IBKR Portal in browser"""
            try:
                import webbrowser
                webbrowser.open(IBKR_PORTAL_URL)
                self.logger.info(f"Opened IBKR Portal: {IBKR_PORTAL_URL}")
            except Exception as e:
                self.logger.error(f"Failed to open browser: {e}")
                QMessageBox.warning(
                    self,
                    "Browser Error",
                    f"Could not open browser.\nPlease visit:\n{IBKR_PORTAL_URL}"
                )
        
        def _select_certificate(self, cert_type: str):
            """
            Open file dialog to select certificate.
            
            Args:
                cert_type: 'encryption' or 'signature'
            """
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                f"Select {cert_type.title()} Certificate",
                str(CERT_FOLDER),
                "PEM Files (*.pem);;All Files (*.*)"
            )
            
            if file_path:
                if cert_type == 'encryption':
                    self.encryption_path_input.setText(file_path)
                else:
                    self.signature_path_input.setText(file_path)
                
                self.logger.info(f"Selected {cert_type} certificate: {file_path}")
        
        def _validate_inputs(self) -> tuple[bool, str]:
            """
            Validate all input fields.
            
            Returns:
                Tuple of (is_valid, error_message)
            """
            # Check OAuth credentials
            if len(self.consumer_key_input.text().strip()) < MIN_KEY_LENGTH:
                return False, "Consumer Key is too short or missing"
            
            if len(self.consumer_secret_input.text().strip()) < MIN_KEY_LENGTH:
                return False, "Consumer Secret is too short or missing"
            
            if len(self.oauth_token_input.text().strip()) < MIN_KEY_LENGTH:
                return False, "OAuth Token is too short or missing"
            
            if len(self.oauth_secret_input.text().strip()) < MIN_KEY_LENGTH:
                return False, "OAuth Token Secret is too short or missing"
            
            # Check certificate files
            encryption_path = self.encryption_path_input.text().strip()
            if not encryption_path or not Path(encryption_path).exists():
                return False, "Encryption certificate file not found"
            
            signature_path = self.signature_path_input.text().strip()
            if not signature_path or not Path(signature_path).exists():
                return False, "Signature certificate file not found"
            
            return True, ""
        
        def _test_connection(self):
            """Test OAuth connection"""
            # Validate inputs first
            is_valid, error_msg = self._validate_inputs()
            if not is_valid:
                QMessageBox.warning(self, "Validation Error", error_msg)
                return
            
            if not AUTH_MANAGER_AVAILABLE:
                QMessageBox.warning(
                    self,
                    "Module Not Available",
                    "IBKRAuthManager module is not available.\n"
                    "Please check your installation."
                )
                return
            
            # Disable buttons during test
            self.test_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.test_btn.setText("⏳ Testing...")
            
            try:
                # Create temporary credentials
                temp_creds = OAuthCredentials(
                    consumer_key=self.consumer_key_input.text().strip(),
                    consumer_secret=self.consumer_secret_input.text().strip(),
                    oauth_token=self.oauth_token_input.text().strip(),
                    oauth_token_secret=self.oauth_secret_input.text().strip(),
                    encryption_key_path=self.encryption_path_input.text().strip(),
                    signature_key_path=self.signature_path_input.text().strip(),
                    account_type=self.account_type_combo.currentText()
                )
                
                # Create temporary auth manager for testing
                temp_manager = IBKRAuthManager()
                temp_manager.credentials = temp_creds
                
                # Start test worker
                self.test_worker = AuthTestWorker(temp_manager)
                self.test_worker.finished.connect(self._handle_test_result)
                self.test_worker.start()
                
            except Exception as e:
                self.logger.error(f"Test setup failed: {e}")
                self._handle_test_result(False, f"Test setup failed: {str(e)}")
        
        def _handle_test_result(self, success: bool, message: str):
            """
            Handle test result.
            
            Args:
                success: Whether test was successful
                message: Result message
            """
            # Re-enable buttons
            self.test_btn.setEnabled(True)
            self.save_btn.setEnabled(True)
            self.test_btn.setText("🧪 Test Connection")
            
            # Show result
            if success:
                QMessageBox.information(self, "Test Successful", message)
            else:
                QMessageBox.critical(self, "Test Failed", message)
        
        def _save_credentials(self):
            """Save OAuth credentials"""
            # Validate inputs
            is_valid, error_msg = self._validate_inputs()
            if not is_valid:
                QMessageBox.warning(self, "Validation Error", error_msg)
                return
            
            if not AUTH_MANAGER_AVAILABLE:
                QMessageBox.warning(
                    self,
                    "Module Not Available",
                    "IBKRAuthManager module is not available.\n"
                    "Please check your installation."
                )
                return
            
            try:
                # Create credentials object
                credentials = OAuthCredentials(
                    consumer_key=self.consumer_key_input.text().strip(),
                    consumer_secret=self.consumer_secret_input.text().strip(),
                    oauth_token=self.oauth_token_input.text().strip(),
                    oauth_token_secret=self.oauth_secret_input.text().strip(),
                    encryption_key_path=self.encryption_path_input.text().strip(),
                    signature_key_path=self.signature_path_input.text().strip(),
                    account_type=self.account_type_combo.currentText()
                )
                
                # Save using auth manager
                if self.auth_manager:
                    success = self.auth_manager.save_credentials(credentials)
                    
                    if success:
                        self.logger.info("Credentials saved successfully")
                        
                        # Emit signal with credentials
                        self.credentials_saved.emit({
                            'account_type': credentials.account_type,
                            'consumer_key': credentials.consumer_key[:10] + '...',  # Partial for logging
                        })
                        
                        QMessageBox.information(
                            self,
                            "Success",
                            "OAuth credentials saved successfully!\n\n"
                            "The dashboard will now attempt to authenticate."
                        )
                        
                        self.accept()
                    else:
                        QMessageBox.critical(
                            self,
                            "Save Failed",
                            "Failed to save credentials. Check logs for details."
                        )
                else:
                    QMessageBox.warning(
                        self,
                        "No Auth Manager",
                        "No authentication manager provided.\n"
                        "Credentials cannot be saved."
                    )
                    
            except Exception as e:
                self.logger.error(f"Save credentials failed: {e}")
                self.error_handler.handle_error(e, "_save_credentials")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to save credentials:\n{str(e)}"
                )
        
        def _load_existing_credentials(self):
            """Load existing credentials if available"""
            if not self.auth_manager:
                return
            
            try:
                credentials = self.auth_manager.load_credentials()
                if credentials:
                    self.consumer_key_input.setText(credentials.consumer_key)
                    self.consumer_secret_input.setText(credentials.consumer_secret)
                    self.oauth_token_input.setText(credentials.oauth_token)
                    self.oauth_secret_input.setText(credentials.oauth_token_secret)
                    self.encryption_path_input.setText(credentials.encryption_key_path)
                    self.signature_path_input.setText(credentials.signature_key_path)
                    
                    # Set account type
                    index = self.account_type_combo.findText(credentials.account_type)
                    if index >= 0:
                        self.account_type_combo.setCurrentIndex(index)
                    
                    self.logger.info("Loaded existing credentials")
            except Exception as e:
                self.logger.error(f"Failed to load existing credentials: {e}")

else:
    # Dummy class if PySide6 not available
    class OAuthSetupDialog:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PySide6 not available - OAuth Setup Dialog requires GUI")


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def show_oauth_setup(auth_manager: Optional['IBKRAuthManager'] = None, 
                     parent=None) -> Optional[Dict[str, Any]]:
    """
    Show OAuth setup dialog and return credentials if saved.
    
    Args:
        auth_manager: Optional IBKRAuthManager instance
        parent: Parent widget
        
    Returns:
        Dictionary with credentials info if saved, None otherwise
    """
    if not PYSIDE6_AVAILABLE:
        print("⚠️ PySide6 not available - OAuth Setup Dialog requires GUI")
        return None
    
    dialog = OAuthSetupDialog(auth_manager, parent)
    
    credentials_data = {}
    
    def on_saved(data):
        nonlocal credentials_data
        credentials_data = data
    
    dialog.credentials_saved.connect(on_saved)
    
    result = dialog.exec()
    
    if result == QDialog.Accepted and credentials_data:
        return credentials_data
    
    return None


# ==============================================================================
# MODULE INFO
# ==============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("SpyderG06_OAuthSetupDialog - OAuth Setup Dialog")
    print("=" * 70)
    print(f"PySide6 Available: {PYSIDE6_AVAILABLE}")
    print(f"Auth Manager Available: {AUTH_MANAGER_AVAILABLE}")
    print(f"Default Certificate Folder: {CERT_FOLDER}")
    print("=" * 70)
    
    if PYSIDE6_AVAILABLE and AUTH_MANAGER_AVAILABLE:
        print("\n✅ Ready for OAuth setup")
        print("\nFeatures:")
        print("  • User-friendly credential input")
        print("  • Certificate file selection")
        print("  • Connection testing")
        print("  • Secure credential storage")
        print("  • Built-in setup guide")
    else:
        if not PYSIDE6_AVAILABLE:
            print("\n⚠️ Install PySide6 to use this dialog:")
            print("   pip install PySide6")
        if not AUTH_MANAGER_AVAILABLE:
            print("\n⚠️ Ensure SpyderB03_IBKRAuthManager is available")
