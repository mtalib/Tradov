#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderI13_IBAutomaterUI.py
Group: I (Integration)
Purpose: UI automation for IB Gateway login, dialog handling, and 2FA support
Author: Mohamed Talib
Date Created: 2025-08-15
Last Updated: 2025-08-15 Time: 14:45:00

Description:
    This module provides comprehensive UI automation for Interactive Brokers Gateway
    including automated login with credential entry, two-factor authentication handling,
    dialog detection and management using computer vision. Uses template matching and
    OCR for robust UI element detection across different screen resolutions and themes.
    Integrates seamlessly with SpyderI12_IBAutomaterCore for complete automation.
"""

import logging
import time
import base64
import os
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import threading

# UI Automation and Computer Vision
try:
    import pyautogui
    import cv2
    import numpy as np
    from PIL import Image, ImageGrab
    UI_AUTOMATION_AVAILABLE = True
except ImportError as e:
    UI_AUTOMATION_AVAILABLE = False
    _import_error = str(e)

# OCR Support (optional)
try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Import core IBAutomater components
try:
    from SpyderI12_IBAutomaterCore import IBEvent, EventEmitter, IBConfig, UIError, AuthenticationError, TwoFactorError
except ImportError:
    # Define basic classes if core module not available
    class IBEvent(Enum):
        LOGIN_COMPLETED = "login_completed"
        TWO_FACTOR_REQUIRED = "two_factor_required"
        UI_DIALOG_DETECTED = "ui_dialog_detected"
        ERROR_DATA_RECEIVED = "error_data_received"
    
    class UIError(Exception):
        pass
    
    class AuthenticationError(Exception):
        pass
    
    class TwoFactorError(Exception):
        pass

# ================================================================================================
# UI AUTOMATION CONFIGURATION
# ================================================================================================

@dataclass
class UIConfig:
    """Configuration for UI automation"""
    screenshot_interval: float = 1.0
    ui_timeout: float = 120.0
    template_match_threshold: float = 0.8
    ocr_confidence_threshold: int = 60
    click_delay: float = 0.5
    type_delay: float = 0.1
    retry_attempts: int = 3
    debug_screenshots: bool = False
    templates_directory: str = "ui_templates"

class DialogType(Enum):
    """Types of dialogs that can be detected"""
    LOGIN = "login"
    TWO_FACTOR = "two_factor"
    ERROR = "error"
    WARNING = "warning"
    CONFIGURATION = "configuration"
    SECURITY_NOTICE = "security_notice"
    UPDATE_NOTIFICATION = "update_notification"

class UIElement(Enum):
    """UI elements that can be detected"""
    USERNAME_FIELD = "username_field"
    PASSWORD_FIELD = "password_field"
    LOGIN_BUTTON = "login_button"
    TWO_FACTOR_FIELD = "two_factor_field"
    TWO_FACTOR_BUTTON = "two_factor_button"
    OK_BUTTON = "ok_button"
    CANCEL_BUTTON = "cancel_button"
    CLOSE_BUTTON = "close_button"
    ERROR_MESSAGE = "error_message"
    API_STATUS = "api_status"

# ================================================================================================
# TEMPLATE STORAGE AND MANAGEMENT
# ================================================================================================

class TemplateManager:
    """Manages UI template images for element detection"""
    
    def __init__(self, templates_dir: str):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(exist_ok=True)
        self.templates: Dict[str, np.ndarray] = {}
        self.logger = logging.getLogger(f"{__name__}.TemplateManager")
        
        # Create default templates if they don't exist
        self._create_default_templates()
    
    def load_template(self, name: str) -> Optional[np.ndarray]:
        """Load a template image"""
        if name in self.templates:
            return self.templates[name]
        
        template_path = self.templates_dir / f"{name}.png"
        if template_path.exists():
            try:
                template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
                if template is not None:
                    self.templates[name] = template
                    self.logger.debug(f"Loaded template: {name}")
                    return template
            except Exception as e:
                self.logger.error(f"Error loading template {name}: {e}")
        
        return None
    
    def save_template(self, name: str, image: np.ndarray):
        """Save a template image"""
        template_path = self.templates_dir / f"{name}.png"
        try:
            cv2.imwrite(str(template_path), image)
            self.templates[name] = image
            self.logger.debug(f"Saved template: {name}")
        except Exception as e:
            self.logger.error(f"Error saving template {name}: {e}")
    
    def _create_default_templates(self):
        """Create default template images (placeholder implementation)"""
        # This would typically contain base64 encoded template images
        # For now, we'll use a placeholder system
        default_templates = {
            "login_button": self._create_text_template("Log In"),
            "username_field": self._create_text_template("User Name"),
            "password_field": self._create_text_template("Password"),
            "two_factor_button": self._create_text_template("Submit"),
            "ok_button": self._create_text_template("OK"),
            "cancel_button": self._create_text_template("Cancel"),
        }
        
        for name, template in default_templates.items():
            if not (self.templates_dir / f"{name}.png").exists():
                self.save_template(name, template)
    
    def _create_text_template(self, text: str) -> np.ndarray:
        """Create a simple text-based template (placeholder)"""
        # Create a simple 100x30 template with text
        template = np.ones((30, 100, 3), dtype=np.uint8) * 240
        cv2.putText(template, text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        return template

# ================================================================================================
# SCREEN CAPTURE AND ANALYSIS
# ================================================================================================

class ScreenAnalyzer:
    """Analyzes screen content for UI element detection"""
    
    def __init__(self, config: UIConfig, template_manager: TemplateManager):
        self.config = config
        self.template_manager = template_manager
        self.logger = logging.getLogger(f"{__name__}.ScreenAnalyzer")
        
        # Configure pyautogui if available
        if UI_AUTOMATION_AVAILABLE:
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = self.config.click_delay
    
    def take_screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """Take a screenshot of the screen or specified region"""
        if not UI_AUTOMATION_AVAILABLE:
            self.logger.error("UI automation libraries not available")
            return None
        
        try:
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            
            # Convert PIL image to OpenCV format
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            # Save debug screenshot if enabled
            if self.config.debug_screenshots:
                debug_path = Path("debug_screenshots")
                debug_path.mkdir(exist_ok=True)
                timestamp = int(time.time())
                cv2.imwrite(str(debug_path / f"screenshot_{timestamp}.png"), screenshot_cv)
            
            return screenshot_cv
            
        except Exception as e:
            self.logger.error(f"Error taking screenshot: {e}")
            return None
    
    def find_element(self, element_name: str, screenshot: Optional[np.ndarray] = None) -> Optional[Tuple[int, int, int, int]]:
        """Find a UI element using template matching"""
        if not UI_AUTOMATION_AVAILABLE:
            return None
        
        if screenshot is None:
            screenshot = self.take_screenshot()
            if screenshot is None:
                return None
        
        template = self.template_manager.load_template(element_name)
        if template is None:
            self.logger.warning(f"Template not found: {element_name}")
            return None
        
        try:
            # Perform template matching
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= self.config.template_match_threshold:
                # Get template dimensions
                h, w = template.shape[:2]
                
                # Return bounding box (x, y, width, height)
                x, y = max_loc
                return (x, y, w, h)
            else:
                self.logger.debug(f"Element {element_name} not found (confidence: {max_val:.3f})")
                return None
                
        except Exception as e:
            self.logger.error(f"Error finding element {element_name}: {e}")
            return None
    
    def find_text(self, text: str, screenshot: Optional[np.ndarray] = None) -> Optional[Tuple[int, int, int, int]]:
        """Find text on screen using OCR"""
        if not OCR_AVAILABLE:
            self.logger.warning("OCR not available - install pytesseract")
            return None
        
        if screenshot is None:
            screenshot = self.take_screenshot()
            if screenshot is None:
                return None
        
        try:
            # Convert to RGB for pytesseract
            rgb_image = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)
            
            # Get text data with bounding boxes
            data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
            
            # Search for the specified text
            for i, detected_text in enumerate(data['text']):
                if text.lower() in detected_text.lower() and int(data['conf'][i]) > self.config.ocr_confidence_threshold:
                    x = data['left'][i]
                    y = data['top'][i]
                    w = data['width'][i]
                    h = data['height'][i]
                    return (x, y, w, h)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding text '{text}': {e}")
            return None
    
    def detect_dialog_type(self, screenshot: Optional[np.ndarray] = None) -> Optional[DialogType]:
        """Detect the type of dialog currently displayed"""
        if screenshot is None:
            screenshot = self.take_screenshot()
            if screenshot is None:
                return None
        
        # Check for login dialog
        if self.find_element("username_field", screenshot) and self.find_element("password_field", screenshot):
            return DialogType.LOGIN
        
        # Check for 2FA dialog
        if self.find_text("two factor", screenshot) or self.find_text("authentication", screenshot):
            return DialogType.TWO_FACTOR
        
        # Check for error dialog
        if self.find_text("error", screenshot) or self.find_text("failed", screenshot):
            return DialogType.ERROR
        
        # Check for security notice
        if self.find_text("security notice", screenshot) or self.find_text("risk disclosure", screenshot):
            return DialogType.SECURITY_NOTICE
        
        return None

# ================================================================================================
# UI INTERACTION ENGINE
# ================================================================================================

class UIInteractor:
    """Handles UI interactions like clicking and typing"""
    
    def __init__(self, config: UIConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.UIInteractor")
    
    def click_element(self, bounds: Tuple[int, int, int, int], offset: Tuple[int, int] = (0, 0)) -> bool:
        """Click on a UI element"""
        if not UI_AUTOMATION_AVAILABLE:
            self.logger.error("UI automation not available")
            return False
        
        try:
            x, y, w, h = bounds
            # Click in the center of the element plus offset
            click_x = x + w // 2 + offset[0]
            click_y = y + h // 2 + offset[1]
            
            self.logger.debug(f"Clicking at ({click_x}, {click_y})")
            pyautogui.click(click_x, click_y)
            time.sleep(self.config.click_delay)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error clicking element: {e}")
            return False
    
    def type_text(self, text: str, clear_first: bool = True) -> bool:
        """Type text into the currently focused field"""
        if not UI_AUTOMATION_AVAILABLE:
            self.logger.error("UI automation not available")
            return False
        
        try:
            if clear_first:
                # Clear the field first
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.1)
            
            # Type the text with delay
            for char in text:
                pyautogui.write(char)
                time.sleep(self.config.type_delay)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error typing text: {e}")
            return False
    
    def press_key(self, key: str) -> bool:
        """Press a keyboard key"""
        if not UI_AUTOMATION_AVAILABLE:
            self.logger.error("UI automation not available")
            return False
        
        try:
            pyautogui.press(key)
            time.sleep(self.config.click_delay)
            return True
        except Exception as e:
            self.logger.error(f"Error pressing key {key}: {e}")
            return False
    
    def press_hotkey(self, *keys) -> bool:
        """Press a hotkey combination"""
        if not UI_AUTOMATION_AVAILABLE:
            self.logger.error("UI automation not available")
            return False
        
        try:
            pyautogui.hotkey(*keys)
            time.sleep(self.config.click_delay)
            return True
        except Exception as e:
            self.logger.error(f"Error pressing hotkey {keys}: {e}")
            return False

# ================================================================================================
# MAIN UI AUTOMATION CLASS
# ================================================================================================

class IBGatewayUIAutomation:
    """
    Main UI automation class for IB Gateway
    
    Provides comprehensive UI automation including:
    - Automated login with credential entry
    - Two-factor authentication handling
    - Dialog detection and management
    - Error handling and recovery
    """
    
    def __init__(self, ib_config: 'IBConfig', event_emitter: Optional['EventEmitter'] = None):
        """
        Initialize UI automation
        
        Args:
            ib_config: IB Gateway configuration
            event_emitter: Event emitter for notifications
        """
        self.ib_config = ib_config
        self.event_emitter = event_emitter
        self.logger = logging.getLogger(f"{__name__}.IBGatewayUIAutomation")
        
        # Check if UI automation is available
        if not UI_AUTOMATION_AVAILABLE:
            self.logger.error(f"UI automation libraries not available: {_import_error}")
            raise RuntimeError("UI automation dependencies not installed")
        
        # Initialize UI configuration
        self.ui_config = UIConfig()
        
        # Initialize components
        self.template_manager = TemplateManager(self.ui_config.templates_directory)
        self.screen_analyzer = ScreenAnalyzer(self.ui_config, self.template_manager)
        self.ui_interactor = UIInteractor(self.ui_config)
        
        # State tracking
        self._login_in_progress = False
        self._two_factor_in_progress = False
        self._automation_lock = threading.Lock()
        
        self.logger.info("UI automation initialized")
    
    # ==============================================================================================
    # PUBLIC INTERFACE
    # ==============================================================================================
    
    def wait_for_login_dialog(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for the login dialog to appear
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if login dialog is detected, False otherwise
        """
        if timeout is None:
            timeout = self.ui_config.ui_timeout
        
        self.logger.info("Waiting for login dialog...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            dialog_type = self.screen_analyzer.detect_dialog_type()
            
            if dialog_type == DialogType.LOGIN:
                self.logger.info("Login dialog detected")
                if self.event_emitter:
                    self.event_emitter.emit(IBEvent.UI_DIALOG_DETECTED, {"type": "login"})
                return True
            
            time.sleep(self.ui_config.screenshot_interval)
        
        self.logger.error("Login dialog not found within timeout")
        return False
    
    def perform_login(self) -> bool:
        """
        Perform automated login
        
        Returns:
            True if login was successful, False otherwise
        """
        with self._automation_lock:
            if self._login_in_progress:
                self.logger.warning("Login already in progress")
                return False
            
            self._login_in_progress = True
        
        try:
            self.logger.info("Starting automated login...")
            
            # Wait for login dialog
            if not self.wait_for_login_dialog():
                raise UIError("Login dialog not found")
            
            # Take screenshot for analysis
            screenshot = self.screen_analyzer.take_screenshot()
            if screenshot is None:
                raise UIError("Could not capture screen")
            
            # Enter username
            if not self._enter_username(screenshot):
                raise UIError("Failed to enter username")
            
            # Enter password
            if not self._enter_password(screenshot):
                raise UIError("Failed to enter password")
            
            # Click login button
            if not self._click_login_button(screenshot):
                raise UIError("Failed to click login button")
            
            # Wait for login completion or 2FA prompt
            result = self._wait_for_login_result()
            
            if result == "success":
                self.logger.info("Login completed successfully")
                if self.event_emitter:
                    self.event_emitter.emit(IBEvent.LOGIN_COMPLETED, {"success": True})
                return True
            elif result == "two_factor":
                self.logger.info("Two-factor authentication required")
                if self.event_emitter:
                    self.event_emitter.emit(IBEvent.TWO_FACTOR_REQUIRED, {})
                return self.handle_two_factor_authentication()
            else:
                raise AuthenticationError("Login failed")
                
        except Exception as e:
            self.logger.error(f"Login automation failed: {e}")
            if self.event_emitter:
                self.event_emitter.emit(IBEvent.ERROR_DATA_RECEIVED, f"Login failed: {e}")
            return False
        finally:
            self._login_in_progress = False
    
    def handle_two_factor_authentication(self, timeout: float = 180.0) -> bool:
        """
        Handle two-factor authentication
        
        Args:
            timeout: Maximum time to wait for 2FA completion
            
        Returns:
            True if 2FA was successful, False otherwise
        """
        with self._automation_lock:
            if self._two_factor_in_progress:
                self.logger.warning("2FA already in progress")
                return False
            
            self._two_factor_in_progress = True
        
        try:
            self.logger.info("Handling two-factor authentication...")
            
            # Wait for 2FA dialog
            start_time = time.time()
            two_factor_dialog_found = False
            
            while time.time() - start_time < 30:  # Wait up to 30 seconds for 2FA dialog
                dialog_type = self.screen_analyzer.detect_dialog_type()
                if dialog_type == DialogType.TWO_FACTOR:
                    two_factor_dialog_found = True
                    break
                time.sleep(self.ui_config.screenshot_interval)
            
            if not two_factor_dialog_found:
                raise TwoFactorError("2FA dialog not found")
            
            # Notify user that 2FA is required
            self.logger.info("Please complete 2FA authentication on your mobile device")
            if self.event_emitter:
                self.event_emitter.emit(IBEvent.TWO_FACTOR_REQUIRED, {
                    "message": "Please approve the login request on your IBKR Mobile app",
                    "timeout": timeout
                })
            
            # Wait for 2FA completion
            return self._wait_for_two_factor_completion(timeout)
            
        except Exception as e:
            self.logger.error(f"2FA handling failed: {e}")
            if self.event_emitter:
                self.event_emitter.emit(IBEvent.ERROR_DATA_RECEIVED, f"2FA failed: {e}")
            return False
        finally:
            self._two_factor_in_progress = False
    
    def dismiss_dialogs(self) -> bool:
        """
        Dismiss any popup dialogs that might interfere with automation
        
        Returns:
            True if dialogs were handled, False otherwise
        """
        try:
            self.logger.info("Checking for dialogs to dismiss...")
            screenshot = self.screen_analyzer.take_screenshot()
            
            if screenshot is None:
                return False
            
            dialogs_handled = 0
            
            # Look for common dialog buttons
            dialog_buttons = ["ok_button", "cancel_button", "close_button"]
            
            for button_name in dialog_buttons:
                button_bounds = self.screen_analyzer.find_element(button_name, screenshot)
                if button_bounds:
                    self.logger.info(f"Found {button_name}, clicking...")
                    if self.ui_interactor.click_element(button_bounds):
                        dialogs_handled += 1
                        time.sleep(1)  # Wait for dialog to close
                        break  # Only handle one dialog at a time
            
            # Check for security notices or risk disclosures
            if self.screen_analyzer.find_text("security notice", screenshot) or \
               self.screen_analyzer.find_text("risk disclosure", screenshot):
                # Try to find and click OK button
                ok_bounds = self.screen_analyzer.find_text("OK", screenshot)
                if ok_bounds:
                    self.ui_interactor.click_element(ok_bounds)
                    dialogs_handled += 1
            
            if dialogs_handled > 0:
                self.logger.info(f"Handled {dialogs_handled} dialog(s)")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error dismissing dialogs: {e}")
            return False
    
    def is_gateway_ready(self) -> bool:
        """
        Check if the gateway is ready for API connections
        
        Returns:
            True if gateway appears ready, False otherwise
        """
        try:
            screenshot = self.screen_analyzer.take_screenshot()
            if screenshot is None:
                return False
            
            # Look for indicators that the gateway is ready
            ready_indicators = [
                "API server listening",
                "Gateway ready",
                "Connected",
                "Logged in"
            ]
            
            for indicator in ready_indicators:
                if self.screen_analyzer.find_text(indicator, screenshot):
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking gateway status: {e}")
            return False
    
    # ==============================================================================================
    # PRIVATE METHODS
    # ==============================================================================================
    
    def _enter_username(self, screenshot: np.ndarray) -> bool:
        """Enter username in the login dialog"""
        username_bounds = self.screen_analyzer.find_element("username_field", screenshot)
        
        if not username_bounds:
            # Try finding username field by text
            username_bounds = self.screen_analyzer.find_text("User Name", screenshot)
        
        if username_bounds:
            # Click on username field
            if self.ui_interactor.click_element(username_bounds):
                # Type username
                return self.ui_interactor.type_text(self.ib_config.username)
        
        return False
    
    def _enter_password(self, screenshot: np.ndarray) -> bool:
        """Enter password in the login dialog"""
        password_bounds = self.screen_analyzer.find_element("password_field", screenshot)
        
        if not password_bounds:
            # Try finding password field by text
            password_bounds = self.screen_analyzer.find_text("Password", screenshot)
        
        if password_bounds:
            # Click on password field
            if self.ui_interactor.click_element(password_bounds):
                # Type password
                return self.ui_interactor.type_text(self.ib_config.password)
        
        return False
    
    def _click_login_button(self, screenshot: np.ndarray) -> bool:
        """Click the login button"""
        login_bounds = self.screen_analyzer.find_element("login_button", screenshot)
        
        if not login_bounds:
            # Try finding login button by text
            login_bounds = self.screen_analyzer.find_text("Log In", screenshot)
        
        if login_bounds:
            return self.ui_interactor.click_element(login_bounds)
        
        return False
    
    def _wait_for_login_result(self, timeout: float = 30.0) -> str:
        """
        Wait for login result
        
        Returns:
            "success", "two_factor", or "failed"
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            screenshot = self.screen_analyzer.take_screenshot()
            if screenshot is None:
                continue
            
            dialog_type = self.screen_analyzer.detect_dialog_type()
            
            # Check for 2FA requirement
            if dialog_type == DialogType.TWO_FACTOR:
                return "two_factor"
            
            # Check for error messages
            if dialog_type == DialogType.ERROR:
                return "failed"
            
            # Check if login dialog is gone (success)
            if dialog_type != DialogType.LOGIN:
                # Login dialog disappeared, likely successful
                return "success"
            
            time.sleep(self.ui_config.screenshot_interval)
        
        return "failed"
    
    def _wait_for_two_factor_completion(self, timeout: float) -> bool:
        """Wait for two-factor authentication to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            screenshot = self.screen_analyzer.take_screenshot()
            if screenshot is None:
                continue
            
            dialog_type = self.screen_analyzer.detect_dialog_type()
            
            # Check if 2FA dialog is gone (success)
            if dialog_type != DialogType.TWO_FACTOR:
                # Check for error
                if dialog_type == DialogType.ERROR:
                    return False
                
                # 2FA completed successfully
                self.logger.info("Two-factor authentication completed")
                return True
            
            time.sleep(self.ui_config.screenshot_interval)
        
        # Timeout
        raise TwoFactorError("Two-factor authentication timed out")

# ================================================================================================
# CONVENIENCE FUNCTIONS
# ================================================================================================

def create_ui_automator(ib_config: 'IBConfig', event_emitter: Optional['EventEmitter'] = None) -> IBGatewayUIAutomation:
    """
    Create a UI automator with default settings
    
    Args:
        ib_config: IB Gateway configuration
        event_emitter: Event emitter for notifications
        
    Returns:
        Configured UI automation instance
    """
    return IBGatewayUIAutomation(ib_config, event_emitter)

def check_ui_automation_availability() -> Tuple[bool, List[str]]:
    """
    Check if UI automation dependencies are available
    
    Returns:
        Tuple of (availability, missing_packages)
    """
    missing_packages = []
    
    if not UI_AUTOMATION_AVAILABLE:
        missing_packages.extend(["pyautogui", "opencv-python", "pillow", "numpy"])
    
    if not OCR_AVAILABLE:
        missing_packages.append("pytesseract")
    
    return len(missing_packages) == 0, missing_packages

# ================================================================================================
# MAIN EXECUTION
# ================================================================================================

if __name__ == "__main__":
    # Example usage and testing
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('spyder_ui_automation.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # Check UI automation availability
    available, missing = check_ui_automation_availability()
    
    if not available:
        logger.error(f"UI automation not available. Missing packages: {missing}")
        logger.info("Install with: pip install pyautogui opencv-python pillow numpy pytesseract")
        sys.exit(1)
    
    logger.info("UI automation dependencies available")
    
    # Test template manager
    try:
        template_manager = TemplateManager("test_templates")
        logger.info("Template manager initialized successfully")
        
        # Test screen analyzer
        ui_config = UIConfig()
        screen_analyzer = ScreenAnalyzer(ui_config, template_manager)
        
        # Take a test screenshot
        screenshot = screen_analyzer.take_screenshot()
        if screenshot is not None:
            logger.info(f"Screenshot captured: {screenshot.shape}")
        
        logger.info("UI automation test completed successfully")
        
    except Exception as e:
        logger.error(f"UI automation test failed: {e}")
        sys.exit(1)
