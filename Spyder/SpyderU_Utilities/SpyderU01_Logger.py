#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU01_Logger.py
Purpose: SPYDER - Logger (Fixed Implementation)

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Logger (Fixed Implementation)

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

class SpyderLogger:
    """
    Logger class for Spyder system.
    """

    _loggers = {}
    _initialized = False
    _root_logger = None

    @classmethod
    def initialize_logging(cls, log_level: str = "INFO", log_file: Path | None = None):
        """Initialize logging system."""
        if cls._initialized:
            return

        # Create formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # Setup console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        # Setup root logger
        cls._root_logger = logging.getLogger()
        cls._root_logger.setLevel(getattr(logging, log_level.upper()))
        cls._root_logger.addHandler(console_handler)

        # Setup file handler if specified
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=50 * 1024 * 1024,  # 50 MB per file
                backupCount=10,
            )
            file_handler.setFormatter(formatter)
            cls._root_logger.addHandler(file_handler)

        cls._initialized = True

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get logger instance."""
        if not cls._initialized:
            cls.initialize_logging()

        if name not in cls._loggers:
            logger = logging.getLogger(name)
            # Add set_level method to individual loggers
            logger.set_level = lambda level: logger.setLevel(getattr(logging, level.upper()))
            cls._loggers[name] = logger

        return cls._loggers[name]

    @classmethod
    def set_level(cls, level: str):
        """Set logging level for root logger."""
        if not cls._initialized:
            cls.initialize_logging()

        if cls._root_logger:
            cls._root_logger.setLevel(getattr(logging, level.upper()))

        # Also update all existing loggers
        for logger in cls._loggers.values():
            logger.setLevel(getattr(logging, level.upper()))


# Factory function


def get_logger(name: str = __name__) -> logging.Logger:
    """Get logger instance."""
    return SpyderLogger.get_logger(name)


__all__ = ["SpyderLogger", "get_logger"]
