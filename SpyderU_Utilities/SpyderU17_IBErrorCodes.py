#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU17_IBErrorCodes.py
Group: U (Utilities)
Purpose: Comprehensive IB API error code handling and resolution

Description:
    This module provides a centralized repository of Interactive Brokers API
    error codes, their meanings, and recommended resolution steps. It helps
    the system intelligently handle different error conditions and provides
    automated recovery guidance based on the architecture document best practices.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-28
Last Updated: 2025-06-28 Time: 19:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Error categories
ERROR_CATEGORY_INFO = "INFORMATIONAL"
ERROR_CATEGORY_WARNING = "WARNING"
ERROR_CATEGORY_CRITICAL = "CRITICAL"
ERROR_CATEGORY_FATAL = "FATAL"

# ==============================================================================
# ENUMS
# ==============================================================================


class ErrorCategory(Enum):
    """Error category enumeration"""

    INFORMATIONAL = "INFORMATIONAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class ErrorAction(Enum):
    """Recommended actions for errors"""

    NONE = "NONE"
    LOG_ONLY = "LOG_ONLY"
    RETRY = "RETRY"
    RECONNECT = "RECONNECT"
    RESUBSCRIBE = "RESUBSCRIBE"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class ErrorDefinition:
    """Error definition with resolution steps"""

    code: int
    message: str
    category: ErrorCategory
    action: ErrorAction
    resolutions: List[str]
    auto_recoverable: bool = False


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class IBErrorCodes:
    """
    Comprehensive IB API error code handling.

    This class provides a centralized repository of IB error codes,
    their meanings, categories, and resolution steps. It helps the
    system handle errors intelligently and recover automatically
    where possible.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        error_definitions: Dictionary of error definitions

    Example:
        >>> error_mgr = IBErrorCodes()
        >>> if error_mgr.is_critical(1100):
        >>>     actions = error_mgr.get_resolution(1100)
    """

    def __init__(self):
        """Initialize the IB error codes manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Initialize error definitions
        self.error_definitions = self._initialize_error_definitions()

        self.logger.info(f"{self.__class__.__name__} initialized")

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def get_error_info(self, error_code: int) -> Optional[ErrorDefinition]:
        """
        Get complete error information.

        Args:
            error_code: IB API error code

        Returns:
            ErrorDefinition or None if not found
        """
        return self.error_definitions.get(error_code)

    def is_informational(self, error_code: int) -> bool:
        """
        Check if error code is informational (not an actual error).

        Args:
            error_code: IB API error code

        Returns:
            bool: True if informational
        """
        error_def = self.get_error_info(error_code)
        return error_def and error_def.category == ErrorCategory.INFORMATIONAL

    def is_critical(self, error_code: int) -> bool:
        """
        Check if error code is critical and requires action.

        Args:
            error_code: IB API error code

        Returns:
            bool: True if critical
        """
        error_def = self.get_error_info(error_code)
        return error_def and error_def.category in [ErrorCategory.CRITICAL, ErrorCategory.FATAL]

    def is_auto_recoverable(self, error_code: int) -> bool:
        """
        Check if error can be automatically recovered.

        Args:
            error_code: IB API error code

        Returns:
            bool: True if auto-recoverable
        """
        error_def = self.get_error_info(error_code)
        return error_def and error_def.auto_recoverable

    def get_resolution(self, error_code: int) -> List[str]:
        """
        Get recommended resolution steps for an error code.

        Args:
            error_code: IB API error code

        Returns:
            List of resolution steps
        """
        error_def = self.get_error_info(error_code)
        return error_def.resolutions if error_def else []

    def get_action(self, error_code: int) -> ErrorAction:
        """
        Get recommended action for an error code.

        Args:
            error_code: IB API error code

        Returns:
            Recommended ErrorAction
        """
        error_def = self.get_error_info(error_code)
        return error_def.action if error_def else ErrorAction.LOG_ONLY

    def get_category(self, error_code: int) -> ErrorCategory:
        """
        Get error category.

        Args:
            error_code: IB API error code

        Returns:
            ErrorCategory
        """
        error_def = self.get_error_info(error_code)
        return error_def.category if error_def else ErrorCategory.WARNING

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _initialize_error_definitions(self) -> Dict[int, ErrorDefinition]:
        """Initialize comprehensive error definitions."""
        definitions = {}

        # Informational codes (2000-2999)
        definitions[2104] = ErrorDefinition(
            code=2104,
            message="Market data farm connection is OK",
            category=ErrorCategory.INFORMATIONAL,
            action=ErrorAction.NONE,
            resolutions=[],
            auto_recoverable=True,
        )

        definitions[2106] = ErrorDefinition(
            code=2106,
            message="HMDS data farm connection is OK",
            category=ErrorCategory.INFORMATIONAL,
            action=ErrorAction.NONE,
            resolutions=[],
            auto_recoverable=True,
        )

        definitions[2158] = ErrorDefinition(
            code=2158,
            message="Sec-def data farm connection is OK",
            category=ErrorCategory.INFORMATIONAL,
            action=ErrorAction.NONE,
            resolutions=[],
            auto_recoverable=True,
        )

        # Connection errors (500-599)
        definitions[502] = ErrorDefinition(
            code=502,
            message="Couldn't connect to TWS",
            category=ErrorCategory.CRITICAL,
            action=ErrorAction.RECONNECT,
            resolutions=[
                "Verify 'Enable ActiveX and Socket Clients' is checked in Gateway/TWS",
                "Double-check port number in Gateway and Python connect() call",
                "Check firewall rules for port access",
                "Ensure IB Gateway/TWS is running",
            ],
            auto_recoverable=True,
        )

        definitions[504] = ErrorDefinition(
            code=504,
            message="Not connected",
            category=ErrorCategory.CRITICAL,
            action=ErrorAction.RETRY,
            resolutions=[
                "Ensure application waits for nextValidId callback before sending requests",
                "Implement robust connection lifecycle management",
                "Check connection status before making requests",
            ],
            auto_recoverable=True,
        )

        # Connection lost (1100-1199)
        definitions[1100] = ErrorDefinition(
            code=1100,
            message="Connectivity between IB and TWS has been lost",
            category=ErrorCategory.CRITICAL,
            action=ErrorAction.RECONNECT,
            resolutions=[
                "Trigger automated reconnection logic",
                "Perform full state reconciliation after reconnection",
                "Check internet connectivity",
                "Verify IB servers are not down",
            ],
            auto_recoverable=True,
        )

        definitions[1101] = ErrorDefinition(
            code=1101,
            message="Connectivity between IB and TWS has been restored - data lost",
            category=ErrorCategory.WARNING,
            action=ErrorAction.RESUBSCRIBE,
            resolutions=[
                "Re-subscribe to all market data",
                "Request current positions",
                "Verify open orders status",
            ],
            auto_recoverable=True,
        )

        definitions[1102] = ErrorDefinition(
            code=1102,
            message="Connectivity between IB and TWS has been restored - data maintained",
            category=ErrorCategory.INFORMATIONAL,
            action=ErrorAction.LOG_ONLY,
            resolutions=["Verify data integrity", "Check for any missed updates"],
            auto_recoverable=True,
        )

        # Request errors (200-399)
        definitions[200] = ErrorDefinition(
            code=200,
            message="No security definition has been found for the request",
            category=ErrorCategory.WARNING,
            action=ErrorAction.RETRY,
            resolutions=[
                "Use TWS contract description tool to find exact parameters",
                "Verify symbol, secType, exchange, and currency",
                "Check if contract is expired",
                "Use reqContractDetails to search for valid contracts",
            ],
            auto_recoverable=False,
        )

        definitions[321] = ErrorDefinition(
            code=321,
            message="Error validating request",
            category=ErrorCategory.WARNING,
            action=ErrorAction.LOG_ONLY,
            resolutions=[
                "Use reqContractDetails to verify contract parameters",
                "Check all order fields against documentation",
                "Ensure all required fields are populated",
                "Verify data types match API requirements",
            ],
            auto_recoverable=False,
        )

        # Market data errors (160-169)
        definitions[162] = ErrorDefinition(
            code=162,
            message="Historical Market Data Service error",
            category=ErrorCategory.WARNING,
            action=ErrorAction.RETRY,
            resolutions=[
                "Verify market data subscriptions in Client Portal",
                "Use reqMarketDataType(3) for delayed data in testing",
                "Check if symbol has historical data available",
                "Reduce request frequency to avoid rate limits",
            ],
            auto_recoverable=True,
        )

        # Order errors (103-199)
        definitions[103] = ErrorDefinition(
            code=103,
            message="Duplicate order ID",
            category=ErrorCategory.WARNING,
            action=ErrorAction.RETRY,
            resolutions=[
                "Use unique order IDs",
                "Implement order ID management system",
                "Check for race conditions in order placement",
            ],
            auto_recoverable=True,
        )

        definitions[110] = ErrorDefinition(
            code=110,
            message="The price does not conform to the minimum price variation for this contract",
            category=ErrorCategory.WARNING,
            action=ErrorAction.LOG_ONLY,
            resolutions=[
                "Round price to valid tick size",
                "Check contract specifications for minimum tick",
                "Use contract details to get price increment",
            ],
            auto_recoverable=False,
        )

        # Account and permissions (430-449)
        definitions[430] = ErrorDefinition(
            code=430,
            message="You must subscribe for real-time data",
            category=ErrorCategory.WARNING,
            action=ErrorAction.LOG_ONLY,
            resolutions=[
                "Subscribe to market data in Account Management",
                "Use delayed data for testing",
                "Check account permissions",
            ],
            auto_recoverable=False,
        )

        return definitions

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start the error codes manager."""
        self.logger.info("IB Error Codes manager started")

    def stop(self) -> None:
        """Stop the error codes manager."""
        self.logger.info("IB Error Codes manager stopped")

    def cleanup(self) -> None:
        """Clean up manager resources."""
        self.logger.info("IB Error Codes manager cleanup completed")


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def get_error_manager() -> IBErrorCodes:
    """
    Get singleton instance of the error codes manager.

    Returns:
        IBErrorCodes instance
    """
    global _error_manager_instance
    if "_error_manager_instance" not in globals():
        _error_manager_instance = IBErrorCodes()
    return _error_manager_instance


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_error_manager_instance: Optional[IBErrorCodes] = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    error_mgr = IBErrorCodes()

    print("✅ IB Error Codes Module Test")
    print("-" * 60)

    # Test various error codes
    test_codes = [2104, 502, 1100, 200, 162]

    for code in test_codes:
        info = error_mgr.get_error_info(code)
        if info:
            print(f"\nError {code}: {info.message}")
            print(f"  Category: {info.category.value}")
            print(f"  Action: {info.action.value}")
            print(f"  Auto-recoverable: {info.auto_recoverable}")

            if info.resolutions:
                print("  Resolutions:")
                for resolution in info.resolutions:
                    print(f"    - {resolution}")

    # Test helper methods
    print("\n" + "-" * 60)
    print("Helper method tests:")
    print(f"Is 2104 informational? {error_mgr.is_informational(2104)}")
    print(f"Is 1100 critical? {error_mgr.is_critical(1100)}")
    print(f"Is 502 auto-recoverable? {error_mgr.is_auto_recoverable(502)}")

    print("\n✅ All tests passed")
