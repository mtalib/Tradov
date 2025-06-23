#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Error Handler (Minimal Implementation)
Module: SpyderU02_ErrorHandler.py
"""

import logging
import traceback
from enum import Enum
from typing import Any, Dict, Optional, Callable
from datetime import datetime

class ErrorType(Enum):
    """Error type enumeration."""
    CONNECTION_ERROR = "connection_error"
    ORDER_ERROR = "order_error" 
    DATA_ERROR = "data_error"
    SYSTEM_ERROR = "system_error"
    VALIDATION_ERROR = "validation_error"

class TradingError(Exception):
    """Custom trading exception."""
    def __init__(self, message: str, error_type: ErrorType = ErrorType.SYSTEM_ERROR, details: Dict = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}
        self.timestamp = datetime.now()

class SpyderErrorHandler:
    """
    Error handling and management for Spyder system.
    
    Provides centralized error handling, logging, and recovery mechanisms
    for the trading system.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_callbacks = {}
        self.error_count = 0
        self.last_error = None
        
        self.logger.info("SpyderErrorHandler initialized")
    
    def handle_error(self, error_type: str, message: str, details: Dict = None, 
                    exception: Exception = None):
        """
        Handle an error with logging and optional callbacks.
        
        Args:
            error_type: Type/category of error
            message: Error message
            details: Additional error details
            exception: Original exception if available
        """
        self.error_count += 1
        
        error_info = {
            'type': error_type,
            'message': message,
            'details': details or {},
            'timestamp': datetime.now().isoformat(),
            'count': self.error_count
        }
        
        if exception:
            error_info['exception'] = str(exception)
            error_info['traceback'] = traceback.format_exc()
        
        self.last_error = error_info
        
        # Log the error
        self.logger.error(f"[{error_type}] {message}")
        if details:
            self.logger.error(f"Details: {details}")
        if exception:
            self.logger.error(f"Exception: {exception}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
        
        # Call registered callbacks
        if error_type in self.error_callbacks:
            try:
                self.error_callbacks[error_type](error_info)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
    
    def register_error_callback(self, error_type: str, callback: Callable):
        """Register callback for specific error type."""
        self.error_callbacks[error_type] = callback
        self.logger.debug(f"Registered callback for error type: {error_type}")
    
    def get_error_count(self) -> int:
        """Get total error count."""
        return self.error_count
    
    def get_last_error(self) -> Optional[Dict]:
        """Get last error information."""
        return self.last_error
    
    def reset_error_count(self):
        """Reset error counter."""
        self.error_count = 0
        self.last_error = None
        self.logger.info("Error count reset")
    
    @staticmethod
    def create_trading_error(message: str, error_type: ErrorType = ErrorType.SYSTEM_ERROR, 
                           details: Dict = None) -> TradingError:
        """Create a TradingError instance."""
        return TradingError(message, error_type, details)

# Factory function
def get_error_handler() -> SpyderErrorHandler:
    """Get SpyderErrorHandler instance."""
    return SpyderErrorHandler()

# Module exports
__all__ = [
    'SpyderErrorHandler',
    'TradingError', 
    'ErrorType',
    'get_error_handler'
]
