"""
UI automation for IB Gateway login and dialog handling
"""

import logging
import time
from pathlib import Path
from typing import Optional, Tuple, List
import cv2
import numpy as np
import pyautogui
from PIL import Image

from .config import IBConfig
from .events import EventEmitter, IBEvent
from .exceptions import UIError, AuthenticationError, TwoFactorError


class UIAutomation:
    """Handles UI automation for IB Gateway"""
    
    def __init__(self, config: IBConfig, event_emitter: EventEmitter):
        self.config = config
        self.event_emitter = event_emitter
        self.logger = logging.getLogger(__name__)
        
        # Configure pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5
        
        # Template images directory
        self.templates_dir = Path(__file__).parent / "templates"
        self.templates_dir.mkdir(exist_ok=True)
    
    def wait_for_login_dialog(self, timeout: float = None) -> bool:
        """Wait for the login dialog to appear"""
        if timeout is None:
            timeout = self.config.ui_timeout
        
        self.logger.info("Waiting for login dialog...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self._find_login_dialog():
                self.logger.info("Login dialog detected")
                return True
            time.sleep(self.config.screenshot_interval)
        
        self.logger.error("Login dialog not found within timeout")
        return False
    
    def perform_login(self) -> bool:
        """Perform automated login"""
        try:
            self.logger.info("Starting automated login...")
            
            # Wait for login dialog
            if not self.wait_for_login_dialog():
                raise UIError("Login dialog not found")
            
            # Enter username
            if not self._enter_username():
                raise UIError("Failed to enter username")
            
            # Enter password
            if not self._enter_password():
                raise UIError("Failed to enter password")
            
            # Click login button
            if not self._click_login_button():
                raise UIError("Failed to click login button")
            
            # Wait for login completion or 2FA prompt
            return self._wait_for_login_completion()
            
        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            raise AuthenticationError(f"Login failed: {e}")
    
    def handle_two_factor_auth(self) -> bool:
        """Handle two-factor authentication"""
        try:
            self.logger.info("Handling two-factor authentication...")
            self.event_emitter.emit(IBEvent.TWO_FACTOR_REQUIRED)
            
            # Wait for 2FA dialog
            if not self._wait_for_2fa_dialog():
                raise TwoFactorError("2FA dialog not found")
            
            # Wait for user to complete 2FA on mobile device
            return self._wait_for_2fa_completion()
            
        except Exception as e:
            self.logger.error(f"2FA handling failed: {e}")
            raise TwoFactorError(f"2FA handling failed: {e}")
    
    def dismiss_dialogs(self) -> int:
        """Dismiss any popup dialogs"""
        dismissed_count = 0
        
        # Common dialog patterns to dismiss
        dialog_patterns = [
            "ok_button",
            "close_button", 
            "dismiss_button",
            "continue_button"
        ]
        
        for pattern in dialog_patterns:
            if self._click_template(pattern):
                dismissed_count += 1
                time.sleep(1)  # Wait between dismissals
        
        if dismissed_count > 0:
            self.logger.info(f"Dismissed {dismissed_count} dialogs")
        
        return dismissed_count
    
    def _find_login_dialog(self) -> bool:
        """Find the login dialog on screen"""
        # Look for login dialog elements
        login_indicators = [
            "username_field",
            "password_field", 
            "login_button",
            "ib_logo"
        ]
        
        for indicator in login_indicators:
            if self._find_template(indicator):
                return True
        
        # Fallback: look for text patterns
        return self._find_text_pattern(["Username", "Password", "Login"])
    
    def _enter_username(self) -> bool:
        """Enter username in the login field"""
        username_field = self._find_template("username_field")
        if username_field:
            pyautogui.click(username_field)
            pyautogui.hotkey('ctrl', 'a')  # Select all
            pyautogui.typewrite(self.config.username)
            return True
        
        # Fallback: try to find by text
        if self._click_near_text("Username"):
            pyautogui.typewrite(self.config.username)
            return True
        
        return False
    
    def _enter_password(self) -> bool:
        """Enter password in the password field"""
        password_field = self._find_template("password_field")
        if password_field:
            pyautogui.click(password_field)
            pyautogui.hotkey('ctrl', 'a')  # Select all
            pyautogui.typewrite(self.config.password)
            return True
        
        # Fallback: try to find by text
        if self._click_near_text("Password"):
            pyautogui.typewrite(self.config.password)
            return True
        
        return False
    
    def _click_login_button(self) -> bool:
        """Click the login button"""
        login_button = self._find_template("login_button")
        if login_button:
            pyautogui.click(login_button)
            return True
        
        # Fallback: try to find by text
        return self._click_text("Login") or self._click_text("Log In")
    
    def _wait_for_login_completion(self) -> bool:
        """Wait for login to complete or 2FA prompt"""
        timeout = self.config.timeout_seconds
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check for 2FA prompt
            if self._find_template("2fa_dialog"):
                return self.handle_two_factor_auth()
            
            # Check for successful login (main window appears)
            if self._find_template("main_window") or self._find_text_pattern(["TWS", "Gateway"]):
                self.event_emitter.emit(IBEvent.LOGIN_COMPLETED)
                return True
            
            # Check for login errors
            if self._find_text_pattern(["Invalid", "Error", "Failed"]):
                raise AuthenticationError("Login failed - invalid credentials")
            
            time.sleep(1)
        
        raise AuthenticationError("Login timeout")
    
    def _wait_for_2fa_dialog(self) -> bool:
        """Wait for 2FA dialog to appear"""
        timeout = 30  # 30 seconds to show 2FA dialog
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self._find_template("2fa_dialog") or self._find_text_pattern(["Two Factor", "2FA"]):
                return True
            time.sleep(1)
        
        return False
    
    def _wait_for_2fa_completion(self) -> bool:
        """Wait for 2FA to be completed"""
        timeout = self.config.two_factor_timeout
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check if 2FA dialog disappeared (success)
            if not self._find_template("2fa_dialog"):
                # Check for main window
                if self._find_template("main_window"):
                    self.event_emitter.emit(IBEvent.LOGIN_COMPLETED)
                    return True
            
            # Check for 2FA timeout/error
            if self._find_text_pattern(["timeout", "expired", "failed"]):
                raise TwoFactorError("2FA timeout or failure")
            
            time.sleep(2)
        
        raise TwoFactorError("2FA completion timeout")
    
    def _find_template(self, template_name: str) -> Optional[Tuple[int, int]]:
        """Find a template image on screen"""
        template_path = self.templates_dir / f"{template_name}.png"
        if not template_path.exists():
            return None
        
        try:
            # Take screenshot
            screenshot = pyautogui.screenshot()
            screenshot_np = np.array(screenshot)
            screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
            
            # Load template
            template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
            
            # Perform template matching
            result = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= self.config.template_match_threshold:
                # Return center of matched region
                h, w = template.shape
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return (center_x, center_y)
            
        except Exception as e:
            self.logger.debug(f"Template matching failed for {template_name}: {e}")
        
        return None
    
    def _click_template(self, template_name: str) -> bool:
        """Click on a template if found"""
        location = self._find_template(template_name)
        if location:
            pyautogui.click(location)
            return True
        return False
    
    def _find_text_pattern(self, patterns: List[str]) -> bool:
        """Find text patterns on screen using OCR"""
        try:
            import pytesseract
            
            # Take screenshot
            screenshot = pyautogui.screenshot()
            
            # Extract text
            text = pytesseract.image_to_string(screenshot)
            text_lower = text.lower()
            
            # Check for patterns
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    return True
            
        except Exception as e:
            self.logger.debug(f"OCR text detection failed: {e}")
        
        return False
    
    def _click_text(self, text: str) -> bool:
        """Click on text if found using OCR"""
        try:
            import pytesseract
            
            # Take screenshot
            screenshot = pyautogui.screenshot()
            
            # Get text boxes
            data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
            
            # Find text and click
            for i, word in enumerate(data['text']):
                if word.lower() == text.lower():
                    x = data['left'][i] + data['width'][i] // 2
                    y = data['top'][i] + data['height'][i] // 2
                    pyautogui.click(x, y)
                    return True
            
        except Exception as e:
            self.logger.debug(f"OCR text clicking failed: {e}")
        
        return False
    
    def _click_near_text(self, text: str, offset_x: int = 100) -> bool:
        """Click near text (useful for input fields next to labels)"""
        try:
            import pytesseract
            
            # Take screenshot
            screenshot = pyautogui.screenshot()
            
            # Get text boxes
            data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
            
            # Find text and click nearby
            for i, word in enumerate(data['text']):
                if text.lower() in word.lower():
                    x = data['left'][i] + data['width'][i] + offset_x
                    y = data['top'][i] + data['height'][i] // 2
                    pyautogui.click(x, y)
                    return True
            
        except Exception as e:
            self.logger.debug(f"OCR near-text clicking failed: {e}")
        
        return False

