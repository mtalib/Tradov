#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: Spyder.SpyderU_Utilities
Module: SpyderU43_CorrelationLogger.py
Purpose: Structured logging with correlation IDs flowing through the full trade lifecycle
Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-28 Time: 00:00:00

Module Description:
    Provides structured, correlation-aware logging for the Spyder trading system.
    Correlation IDs (UUID4) are generated at trade-entry boundaries and injected
    automatically into every log record produced within that context, using
    Python's contextvars for safe async / threaded propagation.

    This enables full reconstruction of any trade's lifecycle — from order
    submission through broker acknowledgement, fill, position update, and risk
    check — by filtering logs on a single correlation_id.

    Key components:
        - ContextVar-based context storage (correlation_id, trade_id, session_id,
          strategy_id) for zero-overhead propagation across coroutines and threads.
        - correlation_context(): context manager that sets IDs for a scope and
          cleanly resets them on exit.
        - CorrelationFilter: logging.Filter subclass that stamps every LogRecord
          with the active context IDs.
        - StructuredFormatter: logging.Formatter subclass that emits newline-
          delimited JSON (NDJSON) using orjson when available, json otherwise.
        - setup_correlation_logging(): one-call setup for root logger with a
          rotating file handler (NDJSON) and a human-readable StreamHandler.
        - Convenience helpers: get/set functions for each context variable.

Change Log:
    2026-03-28:
        - Initial creation
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import logging.handlers
import sys
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from collections.abc import Generator

# ==============================================================================
# PYTHON PATH SETUP
# ==============================================================================
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import orjson  # type: ignore[import]
    _ORJSON_AVAILABLE = True
except ImportError:
    import json  # noqa: F401
    _ORJSON_AVAILABLE = False

# ==============================================================================
# CONTEXT VARIABLES
# ==============================================================================
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_trade_id: ContextVar[str] = ContextVar("trade_id", default="")
_session_id: ContextVar[str] = ContextVar("session_id", default="")
_strategy_id: ContextVar[str] = ContextVar("strategy_id", default="")

# ==============================================================================
# CONSTANTS
# ==============================================================================
_LOG_FORMAT_HUMAN = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "[cid=%(correlation_id)s tid=%(trade_id)s] %(message)s"
)
_LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
_ROTATE_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
_ROTATE_BACKUP_COUNT = 5

# ==============================================================================
# MODULE LOGGER
# ==============================================================================
logger = logging.getLogger(__name__)


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def generate_correlation_id() -> str:
    """Return a new UUID4 as a compact hex string (32 chars, no hyphens)."""
    return uuid.uuid4().hex


def get_correlation_id() -> str:
    """Return the correlation ID active in the current context, or ''."""
    return _correlation_id.get()


def get_trade_id() -> str:
    """Return the trade ID active in the current context, or ''."""
    return _trade_id.get()


def get_session_id() -> str:
    """Return the session ID active in the current context, or ''."""
    return _session_id.get()


def get_strategy_id() -> str:
    """Return the strategy ID active in the current context, or ''."""
    return _strategy_id.get()


def set_trade_id(trade_id: str) -> Token:
    """
    Set the trade ID for the current context.

    Returns the Token that can be passed to ``_trade_id.reset(token)``
    if manual cleanup is required outside of correlation_context().
    """
    return _trade_id.set(trade_id)


def set_strategy_id(strategy_id: str) -> Token:
    """
    Set the strategy ID for the current context.

    Returns the Token that can be passed to ``_strategy_id.reset(token)``
    if manual cleanup is required outside of correlation_context().
    """
    return _strategy_id.set(strategy_id)


def set_session_id(session_id: str) -> Token:
    """
    Set the session ID for the current context.

    Returns the Token that can be passed to ``_session_id.reset(token)``
    if manual cleanup is required outside of correlation_context().
    """
    return _session_id.set(session_id)


# ==============================================================================
# CONTEXT MANAGER
# ==============================================================================

@contextmanager
def correlation_context(
    trade_id: str = "",
    strategy_id: str = "",
    session_id: str = "",
    correlation_id: str = "",
) -> Generator[str]:
    """
    Context manager that establishes a correlation scope for structured logging.

    All log records emitted inside this block will carry the provided IDs.
    A new UUID4 correlation_id is auto-generated when none is supplied.

    Parameters
    ----------
    trade_id:
        Identifier for the specific trade (e.g. "TRD-001").
    strategy_id:
        Identifier for the originating strategy (e.g. "IronCondor").
    session_id:
        Identifier for the trading session (e.g. "SESSION-2026-03-28").
    correlation_id:
        Optional explicit correlation ID.  Defaults to a fresh UUID4 hex.

    Yields
    ------
    str
        The active correlation_id for this scope (useful for storing or logging).

    Example
    -------
    >>> with correlation_context(trade_id="TRD-001", strategy_id="IronCondor") as cid:
    ...     logger.info("Order submitted")   # LogRecord includes cid automatically
    ...     logger.info("Order filled")
    """
    cid = correlation_id if correlation_id else generate_correlation_id()

    token_cid = _correlation_id.set(cid)
    token_tid = _trade_id.set(trade_id)
    token_sid = _session_id.set(session_id)
    token_strat = _strategy_id.set(strategy_id)

    try:
        yield cid
    finally:
        _correlation_id.reset(token_cid)
        _trade_id.reset(token_tid)
        _session_id.reset(token_sid)
        _strategy_id.reset(token_strat)


# ==============================================================================
# CORRELATION FILTER
# ==============================================================================

class CorrelationFilter(logging.Filter):
    """
    Logging filter that injects active correlation context into every LogRecord.

    Attach this filter to any handler or logger to ensure that every record
    carries the fields ``correlation_id``, ``trade_id``, ``session_id``, and
    ``strategy_id``.  Fields default to empty string when no context is active.

    Example
    -------
    >>> handler = logging.StreamHandler()
    >>> handler.addFilter(CorrelationFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id.get()
        record.trade_id = _trade_id.get()
        record.session_id = _session_id.get()
        record.strategy_id = _strategy_id.get()
        return True  # never suppress; only annotate


# ==============================================================================
# STRUCTURED (JSON) FORMATTER
# ==============================================================================

class StructuredFormatter(logging.Formatter):
    """
    Formats log records as newline-delimited JSON (NDJSON).

    Each line is a self-contained JSON object with the following fields:

    ``timestamp``
        ISO-8601 UTC timestamp with microseconds, e.g. ``"2026-03-28T12:00:00.123456Z"``.
    ``level``
        Log level name: ``"INFO"``, ``"WARNING"``, etc.
    ``logger``
        Logger name (``record.name``).
    ``message``
        Formatted log message.
    ``correlation_id``
        Active correlation ID from context (empty string if none).
    ``trade_id``
        Active trade ID from context (empty string if none).
    ``session_id``
        Active session ID from context (empty string if none).
    ``strategy_id``
        Active strategy ID from context (empty string if none).
    ``module``
        Source module filename (e.g. ``"SpyderB40_TradierClient"``)
    ``line``
        Line number in source file.
    ``exc_info``
        Formatted exception traceback string, present only when an exception
        is attached to the record.

    Uses ``orjson`` when available for speed; falls back to the stdlib ``json``
    module transparently.

    Example
    -------
    >>> formatter = StructuredFormatter()
    >>> handler = logging.FileHandler("trade.log")
    >>> handler.setFormatter(formatter)
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dumps(obj: Any) -> str:
        if _ORJSON_AVAILABLE:
            return orjson.dumps(obj).decode("utf-8")  # type: ignore[union-attr]
        import json as _json
        return _json.dumps(obj, ensure_ascii=False, default=str)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def format(self, record: logging.LogRecord) -> str:
        # Ensure message is rendered (handles % formatting)
        record.getMessage()

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=UTC
            ).isoformat(timespec="microseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", ""),
            "trade_id": getattr(record, "trade_id", ""),
            "session_id": getattr(record, "session_id", ""),
            "strategy_id": getattr(record, "strategy_id", ""),
            "module": record.filename,
            "line": record.lineno,
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload["exc_info"] = record.exc_text

        return self._dumps(payload)


# ==============================================================================
# SETUP FUNCTION
# ==============================================================================

def setup_correlation_logging(
    log_file: str | None = None,
    level: int = logging.INFO,
) -> None:
    """
    Configure the root logger for correlation-aware, structured logging.

    Attaches:
    - A ``StreamHandler`` with human-readable formatting for console output.
    - Optionally, a ``RotatingFileHandler`` writing NDJSON (one JSON object
      per line) when ``log_file`` is provided.

    Both handlers receive a :class:`CorrelationFilter` so that every record
    carries the active correlation context.

    This function is idempotent: calling it more than once will not add
    duplicate handlers.

    Parameters
    ----------
    log_file:
        Filesystem path for the structured (NDJSON) log file.  When ``None``,
        file logging is disabled.  Parent directories are created automatically.
    level:
        Minimum log level for the root logger (default ``logging.INFO``).

    Example
    -------
    >>> setup_correlation_logging(log_file="logs/spyder_trades.log")
    """
    root = logging.getLogger()
    root.setLevel(level)

    correlation_filter = CorrelationFilter()
    structured_formatter = StructuredFormatter()

    # ------------------------------------------------------------------
    # Console / StreamHandler — human-readable
    # ------------------------------------------------------------------
    # Avoid adding duplicate handlers when called more than once
    has_stream = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    )
    if not has_stream:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(level)
        stream_handler.addFilter(correlation_filter)
        # Human-readable formatter that respects the injected fields
        stream_handler.setFormatter(
            logging.Formatter(fmt=_LOG_FORMAT_HUMAN, datefmt=_LOG_DATE_FORMAT)
        )
        root.addHandler(stream_handler)

    # ------------------------------------------------------------------
    # File handler — structured NDJSON (rotating)
    # ------------------------------------------------------------------
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Avoid duplicate file handlers for the same path
        has_file = any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            and getattr(h, "baseFilename", None) == str(log_path.resolve())
            for h in root.handlers
        )
        if not has_file:
            file_handler = logging.handlers.RotatingFileHandler(
                filename=str(log_path),
                maxBytes=_ROTATE_MAX_BYTES,
                backupCount=_ROTATE_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.addFilter(correlation_filter)
            file_handler.setFormatter(structured_formatter)
            root.addHandler(file_handler)

    logger.debug(
        "Correlation logging configured | file=%s level=%s orjson=%s",
        log_file,
        logging.getLevelName(level),
        _ORJSON_AVAILABLE,
    )


# ==============================================================================
# DEMO / SELF-TEST
# ==============================================================================

if __name__ == "__main__":
    setup_correlation_logging(log_file="logs/correlation_demo.log", level=logging.DEBUG)

    demo_logger = logging.getLogger("SpyderU43.Demo")

    # -----------------------------------------------------------------------
    # 1. Log outside any correlation context — IDs will be empty strings
    # -----------------------------------------------------------------------
    demo_logger.info("System startup — no active trade context")

    # -----------------------------------------------------------------------
    # 2. Basic correlation context
    # -----------------------------------------------------------------------
    with correlation_context(trade_id="TRD-001", strategy_id="IronCondor") as cid:
        demo_logger.info("Order submitted | symbol=SPY expiry=2026-04-17 strike=500/505")
        demo_logger.info("Broker ACK received | broker_order_id=TRAD-99887766")

        # Simulate a nested call that updates the trade leg
        tok = set_trade_id("TRD-001-LEG-CALL")
        try:
            demo_logger.info("Fill confirmed | side=BUY qty=1 price=2.35")
        finally:
            _trade_id.reset(tok)

        demo_logger.info("Position updated | net_delta=-0.04 net_theta=12.50")
        demo_logger.info("Risk check passed | margin_used=1250.00 max_loss=500.00")
        demo_logger.info(
            "Trade lifecycle complete | correlation_id=%s", get_correlation_id()
        )

    # -----------------------------------------------------------------------
    # 3. Exception capture
    # -----------------------------------------------------------------------
    with correlation_context(trade_id="TRD-002", strategy_id="CoveredCall"):
        try:
            raise ValueError("Simulated broker rejection: margin insufficient")
        except ValueError:
            demo_logger.exception("Order rejected — exception captured in structured log")

    # -----------------------------------------------------------------------
    # 4. Session-level context
    # -----------------------------------------------------------------------
    with correlation_context(
        session_id="SESSION-2026-03-28-AM",
        strategy_id="DailyOpen",
    ):
        demo_logger.info("Morning session started")
        with correlation_context(
            trade_id="TRD-003",
            strategy_id="DailyOpen",
            session_id="SESSION-2026-03-28-AM",
        ):
            demo_logger.info("Trade TRD-003 entered within morning session")
        demo_logger.info("Morning session checkpoint logged")

    # -----------------------------------------------------------------------
    # 5. Verify context is clean after exit
    # -----------------------------------------------------------------------
    assert get_correlation_id() == "", "correlation_id leaked out of context"
    assert get_trade_id() == "", "trade_id leaked out of context"
    demo_logger.info("Context isolation verified — all IDs reset after exit")

    print("\nDemo complete.  Check logs/correlation_demo.log for NDJSON output.")  # noqa: T201
