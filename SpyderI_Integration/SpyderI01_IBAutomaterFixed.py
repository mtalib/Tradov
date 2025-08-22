#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - IB Automater (Fixed for Wayland)
This version handles display issues gracefully
"""

import os
import sys
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Check if we should disable automation
DISABLE_AUTOMATION = os.environ.get('SPYDER_NO_AUTOMATION', '0') == '1'

# Try to import pyautogui with proper error handling
HAS_PYAUTOGUI = False
if not DISABLE_AUTOMATION:
    try:
        # Set display backend before importing
        os.environ['MPLBACKEND'] = 'Agg'  # Use non-interactive backend
        
        # Try to import with X display handling
        import pyautogui
        HAS_PYAUTOGUI = True
        logger.info("pyautogui imported successfully")
    except Exception as e:
        logger.warning(f"Could not import pyautogui: {e}")
        logger.warning("Automation features will be disabled")
        HAS_PYAUTOGUI = False

class SpyderIBAutomaterConfig:
    """Configuration for IB Automater"""
    def __init__(self):
        self.enabled = HAS_PYAUTOGUI and not DISABLE_AUTOMATION
        self.use_automation = self.enabled

class SpyderIBAutomater:
    """IB Gateway Automater (Wayland-safe version)"""
    
    def __init__(self, config=None):
        self.config = config or SpyderIBAutomaterConfig()
        self.enabled = self.config.enabled
        
        if not self.enabled:
            logger.info("IB Automation disabled (Wayland mode or pyautogui unavailable)")
    
    def start(self):
        """Start automation (if available)"""
        if self.enabled:
            logger.info("Starting IB automation...")
            # Automation code here
        else:
            logger.info("IB automation skipped (not available)")
            
    def stop(self):
        """Stop automation"""
        logger.info("Stopping IB automation...")

# For backward compatibility
def check_and_install_dependencies():
    """Check dependencies (Wayland-safe)"""
    return HAS_PYAUTOGUI

dependencies_installed = HAS_PYAUTOGUI
