#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderU01_Logger.py
Group: U (Utilities)
Purpose: Centralized logging system

Description:
This module provides a centralized logging system for the entire Spyder
trading platform. It implements structured logging with multiple output
handlers, log rotation, performance logging, and integration with external
logging services. The logger supports different log levels, custom formatting,
and automatic archival of old logs. It includes special handlers for trading
events, performance metrics, and error tracking.

Author: Mohamed Talib
Created: 2025-01-27
Version: 1.4
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from functools import wraps
import traceback
import threading
import queue
from dataclasses import dataclass
from enum import Enum
import gzip
import shutil

# =============================================================================
# Third-Party Imports
# =============================================================================
try:
    import colorlog
    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False
    print("Warning: colorlog not available. Install with: pip install colorlog")

try:
    from pythonjsonlogger import jsonlogger
    HAS_JSONLOGGER = True
except ImportError:
    HAS_JSONLOGGER = False
    print("Warning: python-json-logger not available. Install with: pip install python-json-logger")

# =============================================================================
# Constants
# =============================================================================
# Log directories
LOG_BASE_DIR = Path.home() / ".spyder" / "logs"
TRADE_LOG_DIR = LOG_BASE_DIR / "trades"
PERFORMANCE_LOG_DIR = LOG_BASE_DIR / "performance"
ERROR_LOG_DIR = LOG_BASE_DIR / "errors"
ARCHIVE_DIR = LOG_BASE_DIR / "archive"

# Log file settings
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 10
LOG_RETENTION_DAYS = 30

# Log format
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DETAILED_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s"
JSON_FORMAT = "%(timestamp)s %(level)s %(name)s %(message)s"

# Performance logging
PERFORMANCE_LOG_INTERVAL = 60  # seconds


# =============================================================================
# Enumerations
# =============================================================================
class LogLevel(Enum):
    """Extended log levels."""

    TRACE = 5
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL
    TRADE = 25  # Custom level for trade logs
    PERFORMANCE = 26  # Custom level for performance logs


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class LogConfig:
    """
    Logger configuration.

    Attributes:
        name: Logger name
        level: Log level
        handlers: List of handler types
        format: Log format
        propagate: Whether to propagate to parent
        filters: Log filters
    """

    name: str
    level: LogLevel = LogLevel.INFO
    handlers: List[str] = None
    format: str = DEFAULT_FORMAT
    propagate: bool = True
    filters: List[str] = None


# =============================================================================
# Custom Formatters
# =============================================================================
if HAS_JSONLOGGER:
    class CustomJsonFormatter(jsonlogger.JsonFormatter):
        """Custom JSON formatter with additional fields."""

        def add_fields(self, log_record, record, message_dict):
            super().add_fields(log_record, record, message_dict)
            log_record["timestamp"] = datetime.utcnow().isoformat()
            log_record["level"] = record.levelname
            log_record["module"] = record.module
            log_record["function"] = record.funcName
            log_record["line"] = record.lineno

            # Add custom fields if present
            if hasattr(record, "trade_id"):
                log_record["trade_id"] = record.trade_id
            if hasattr(record, "strategy"):
                log_record["strategy"] = record.strategy
            if hasattr(record, "performance_metrics"):
                log_record["performance_metrics"] = record.performance_metrics


# =============================================================================
# Custom Handlers
# =============================================================================
class PerformanceLogHandler(logging.Handler):
    """Handler for performance metrics logging."""

    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        self.metrics_buffer = []
        self.last_flush = datetime.now()
        self._lock = threading.Lock()

    def emit(self, record):
        """Emit a log record."""
        try:
            with self._lock:
                if hasattr(record, "performance_metrics"):
                    self.metrics_buffer.append(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "metrics": record.performance_metrics,
                        }
                    )

                    # Flush if buffer is full or time elapsed
                    if (
                        len(self.metrics_buffer) >= 100
                        or (datetime.now() - self.last_flush).seconds
                        >= PERFORMANCE_LOG_INTERVAL
                    ):
                        self._flush_metrics()
        except Exception:
            self.handleError(record)

    def _flush_metrics(self):
        """Flush metrics to file."""
        if not self.metrics_buffer:
            return

        try:
            with open(self.filename, "a") as f:
                for metric in self.metrics_buffer:
                    f.write(json.dumps(metric) + "\n")

            self.metrics_buffer.clear()
            self.last_flush = datetime.now()
        except Exception as e:
            print(f"Error flushing performance metrics: {e}")


class TradeLogHandler(logging.Handler):
    """Handler for trade-specific logging."""

    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        if HAS_JSONLOGGER:
            self.setFormatter(CustomJsonFormatter())

    def emit(self, record):
        """Emit a trade log record."""
        try:
            if record.levelno == LogLevel.TRADE.value:
                with open(self.filename, "a") as f:
                    f.write(self.format(record) + "\n")
        except Exception:
            self.handleError(record)


# =============================================================================
# Class Definitions
# =============================================================================
class SpyderLogger:
    """
    Centralized logging system for Spyder.

    This class provides a comprehensive logging solution with support for
    multiple output formats, custom log levels, performance tracking, and
    automatic log rotation and archival.

    Attributes:
        _loggers (Dict): Cache of logger instances
        _configs (Dict): Logger configurations
        _handlers (Dict): Shared handlers
        _log_queue (Queue): Asynchronous logging queue
        _worker_thread (Thread): Log processing thread
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the logging system."""
        if not SpyderLogger._initialized:
            self._loggers: Dict[str, logging.Logger] = {}
            self._configs: Dict[str, LogConfig] = {}
            self._handlers: Dict[str, logging.Handler] = {}
            self._log_queue = queue.Queue(maxsize=10000)
            self._stop_event = threading.Event()

            # Create directories
            self._create_directories()

            # Add custom log levels
            self._add_custom_levels()

            # Initialize default handlers
            self._init_default_handlers()

            # Start async logging worker
            self._worker_thread = threading.Thread(
                target=self._process_log_queue, name="Logger-Worker", daemon=True
            )
            self._worker_thread.start()

            # Schedule log rotation
            self._schedule_log_rotation()

            SpyderLogger._initialized = True

    def _create_directories(self) -> None:
        """Create log directories."""
        directories = [
            LOG_BASE_DIR,
            TRADE_LOG_DIR,
            PERFORMANCE_LOG_DIR,
            ERROR_LOG_DIR,
            ARCHIVE_DIR,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _add_custom_levels(self) -> None:
        """Add custom log levels."""
        # Add TRADE level
        logging.addLevelName(LogLevel.TRADE.value, "TRADE")

        # Add PERFORMANCE level
        logging.addLevelName(LogLevel.PERFORMANCE.value, "PERFORMANCE")

        # Add TRACE level
        logging.addLevelName(LogLevel.TRACE.value, "TRACE")

    def _init_default_handlers(self) -> None:
        """Initialize default log handlers."""
        # Console handler with color
        console_handler = logging.StreamHandler(sys.stdout)
        
        if HAS_COLORLOG:
            console_formatter = colorlog.ColoredFormatter(
                "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                    "TRADE": "blue",
                    "PERFORMANCE": "magenta",
                },
            )
        else:
            console_formatter = logging.Formatter(DEFAULT_FORMAT)
            
        console_handler.setFormatter(console_formatter)
        self._handlers["console"] = console_handler

        # Main file handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_BASE_DIR / "spyder.log", maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT
        )
        file_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
        self._handlers["file"] = file_handler

        # Error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            ERROR_LOG_DIR / "errors.log",
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
        self._handlers["error"] = error_handler

        # JSON file handler for structured logs
        if HAS_JSONLOGGER:
            json_handler = logging.handlers.RotatingFileHandler(
                LOG_BASE_DIR / "spyder.json",
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
            )
            json_handler.setFormatter(CustomJsonFormatter())
            self._handlers["json"] = json_handler

        # Trade log handler
        trade_handler = TradeLogHandler(
            str(TRADE_LOG_DIR / f"trades_{datetime.now().strftime('%Y%m%d')}.json")
        )
        self._handlers["trade"] = trade_handler

        # Performance log handler
        performance_handler = PerformanceLogHandler(
            str(PERFORMANCE_LOG_DIR / f"performance_{datetime.now().strftime('%Y%m%d')}.json")
        )
        self._handlers["performance"] = performance_handler

    # =========================================================================
    # Public Methods
    # =========================================================================

    @classmethod
    def get_logger(
        cls, name: str, config: Optional[LogConfig] = None
    ) -> logging.Logger:
        """
        Get or create a logger instance.

        Args:
            name: Logger name (usually __name__)
            config: Optional logger configuration

        Returns:
            Logger instance
        """
        instance = cls()

        if name in instance._loggers:
            return instance._loggers[name]

        # Create new logger
        logger = logging.getLogger(name)

        # Apply configuration
        if config:
            instance._configs[name] = config
            logger.setLevel(config.level.value)
            logger.propagate = config.propagate

            # Add handlers
            handlers = config.handlers or ["console", "file", "error"]
            for handler_name in handlers:
                if handler_name in instance._handlers:
                    logger.addHandler(instance._handlers[handler_name])
        else:
            # Default configuration
            logger.setLevel(logging.INFO)
            logger.addHandler(instance._handlers["console"])
            logger.addHandler(instance._handlers["file"])
            logger.addHandler(instance._handlers["error"])

        # Add to cache
        instance._loggers[name] = logger

        return logger

    def log_trade(self, trade_data: Dict[str, Any]) -> None:
        """
        Log trade information.

        Args:
            trade_data: Trade details
        """
        logger = self.get_logger("trades")

        # Create log record with trade level
        record = logging.LogRecord(
            name="trades",
            level=LogLevel.TRADE.value,
            pathname="",
            lineno=0,
            msg=f"Trade executed: {trade_data.get('trade_id')}",
            args=(),
            exc_info=None,
        )

        # Add trade data to record
        for key, value in trade_data.items():
            setattr(record, key, value)

        logger.handle(record)

    def log_performance(self, metrics: Dict[str, Any]) -> None:
        """
        Log performance metrics.

        Args:
            metrics: Performance metrics
        """
        logger = self.get_logger("performance")

        # Create log record with performance level
        record = logging.LogRecord(
            name="performance",
            level=LogLevel.PERFORMANCE.value,
            pathname="",
            lineno=0,
            msg="Performance metrics",
            args=(),
            exc_info=None,
        )

        record.performance_metrics = metrics
        logger.handle(record)

    def log_exception(
        self,
        logger_name: str,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log exception with full traceback.

        Args:
            logger_name: Logger to use
            exception: Exception to log
            context: Additional context
        """
        logger = self.get_logger(logger_name)

        error_data = {
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "traceback": traceback.format_exc(),
            "context": context or {},
        }

        logger.error(f"Exception occurred: {exception}", extra=error_data)

    def set_log_level(self, logger_name: str, level: Union[LogLevel, int]) -> None:
        """
        Set log level for a logger.

        Args:
            logger_name: Logger name
            level: New log level
        """
        if logger_name in self._loggers:
            if isinstance(level, LogLevel):
                level = level.value
            self._loggers[logger_name].setLevel(level)

    def add_handler(self, logger_name: str, handler: logging.Handler) -> None:
        """
        Add handler to logger.

        Args:
            logger_name: Logger name
            handler: Handler to add
        """
        if logger_name in self._loggers:
            self._loggers[logger_name].addHandler(handler)

    def rotate_logs(self) -> None:
        """Manually rotate all log files."""
        for handler in self._handlers.values():
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                handler.doRollover()

    def archive_old_logs(self) -> None:
        """Archive old log files."""
        cutoff_date = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)

        for log_dir in [
            LOG_BASE_DIR,
            TRADE_LOG_DIR,
            PERFORMANCE_LOG_DIR,
            ERROR_LOG_DIR,
        ]:
            for log_file in log_dir.glob("*.log*"):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    # Compress and move to archive
                    archive_name = ARCHIVE_DIR / f"{log_file.name}.gz"

                    with open(log_file, "rb") as f_in:
                        with gzip.open(archive_name, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)

                    log_file.unlink()

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _process_log_queue(self) -> None:
        """Process asynchronous log queue."""
        while not self._stop_event.is_set():
            try:
                # Get log record from queue with timeout
                record = self._log_queue.get(timeout=1)

                if record is None:  # Poison pill
                    break

                # Process log record
                logger_name = record.name
                if logger_name in self._loggers:
                    self._loggers[logger_name].handle(record)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing log queue: {e}")

    def _schedule_log_rotation(self) -> None:
        """Schedule automatic log rotation."""
        # This would typically use a scheduler
        # Simplified for this example
        pass

    def shutdown(self) -> None:
        """Shutdown logging system."""
        # Stop worker thread
        self._stop_event.set()
        self._log_queue.put(None)  # Poison pill

        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)

        # Flush all handlers
        for handler in self._handlers.values():
            handler.flush()
            handler.close()

        # Clear caches
        self._loggers.clear()
        self._handlers.clear()


# =============================================================================
# Logging Decorators
# =============================================================================
def log_execution_time(logger_name: str = None):
    """
    Decorator to log function execution time.

    Args:
        logger_name: Logger to use (defaults to function module)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = SpyderLogger.get_logger(logger_name or func.__module__)

            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.now() - start_time).total_seconds()

                logger.debug(
                    f"{func.__name__} executed in {execution_time:.3f} seconds"
                )

                return result
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"{func.__name__} failed after {execution_time:.3f} seconds: {str(e)}"
                )
                raise

        return wrapper

    return decorator


def log_function_call(
    logger_name: str = None, log_args: bool = True, log_result: bool = False
):
    """
    Decorator to log function calls.

    Args:
        logger_name: Logger to use
        log_args: Whether to log arguments
        log_result: Whether to log result
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = SpyderLogger.get_logger(logger_name or func.__module__)

            # Log function call
            if log_args:
                logger.debug(
                    f"Calling {func.__name__} with args={args}, kwargs={kwargs}"
                )
            else:
                logger.debug(f"Calling {func.__name__}")

            try:
                result = func(*args, **kwargs)

                if log_result:
                    logger.debug(f"{func.__name__} returned: {result}")

                return result
            except Exception as e:
                logger.error(f"{func.__name__} raised exception: {str(e)}")
                raise

        return wrapper

    return decorator


# =============================================================================
# Module Functions
# =============================================================================
def setup_logging(config_file: Optional[str] = None) -> None:
    """
    Setup logging system from configuration file.

    Args:
        config_file: Path to logging configuration
    """
    if config_file and os.path.exists(config_file):
        with open(config_file, "r") as f:
            config = json.load(f)

        # Apply configuration
        for logger_config in config.get("loggers", []):
            SpyderLogger.get_logger(logger_config["name"], LogConfig(**logger_config))


def get_trade_logger() -> logging.Logger:
    """Get trade-specific logger."""
    logger = SpyderLogger.get_logger("trades")
    logger.addHandler(SpyderLogger()._handlers["trade"])
    return logger


def get_performance_logger() -> logging.Logger:
    """Get performance-specific logger."""
    logger = SpyderLogger.get_logger("performance")
    logger.addHandler(SpyderLogger()._handlers["performance"])
    return logger


# =============================================================================
# Module Initialization & Backward Compatibility
# =============================================================================
# Create default logger instance
_default_logger = None

# BACKWARD COMPATIBILITY: Alias for old Logger class name
Logger = SpyderLogger

# Global logger instances cache
_logger_cache = {}


def get_logger(
    name: str = __name__, level: str = "INFO", log_file: Optional[str] = None
) -> logging.Logger:
    """
    Get or create a logger instance.

    Args:
        name: Logger name (usually __name__)
        level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        log_file: Optional log file path

    Returns:
        logging.Logger instance
    """
    # Check cache first
    cache_key = f"{name}_{level}_{log_file}"
    if cache_key in _logger_cache:
        return _logger_cache[cache_key]

    # Create config
    config = LogConfig(name=name)
    
    # Map string level to LogLevel enum
    if isinstance(level, str):
        try:
            config.level = LogLevel[level]
        except KeyError:
            config.level = LogLevel.INFO

    # Create logger using the class method
    logger = SpyderLogger.get_logger(name, config)
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
        logger.addHandler(file_handler)
    
    # Cache the logger
    _logger_cache[cache_key] = logger

    return logger


# =============================================================================
# Simple Logger Creation Function for Quick Use
# =============================================================================
def create_logger(name: str = None) -> logging.Logger:
    """
    Create a simple logger with default settings.
    
    Args:
        name: Logger name (defaults to module name)
        
    Returns:
        logging.Logger instance
    """
    if name is None:
        # Get the calling module's name
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get('__name__', 'spyder')
    
    return get_logger(name)


# =============================================================================
# Initialize Default Logger on Module Load
# =============================================================================
# This ensures basic logging works even without explicit initialization
_default_logger = get_logger('spyder')