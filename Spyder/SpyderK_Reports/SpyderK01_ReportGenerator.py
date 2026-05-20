#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderK_Reports
Module: SpyderK01_ReportGenerator.py
Purpose: Formal base interface for all K-series report generators — enums,
         shared dataclasses, ``ReportGeneratorProtocol`` (structural typing),
         and ``BaseReportGenerator`` ABC.

Provides:
    ReportFormat             — output format enum (HTML, JSON, CSV, PDF, EXCEL, TEXT)
    ReportType               — report category enum (DAILY, PERFORMANCE, RISK, …)
    ReportMetadata           — lightweight header stamped on every generated report
    ReportRequest            — caller-supplied parameters describing a report run
    ReportResult             — typed container wrapping the report payload + metadata
    ReportGeneratorProtocol  — ``@runtime_checkable`` Protocol describing the public
                               interface every K-series generator must satisfy
    BaseReportGenerator      — optional ABC base class providing logger, error handler,
                               and ``_stamp_metadata()`` helper; concrete classes may
                               inherit or simply satisfy the Protocol structurally

Design note:
    No other K-series class is *required* to inherit from ``BaseReportGenerator``.
    Structural subtyping via ``ReportGeneratorProtocol`` is sufficient for type
    checking.  The ABC exists solely as a convenience for new generators.

Author: Spyder Dev
Year Created: 2025
Last Updated: 2026-04-02 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, UTC
from enum import Enum
from typing import Any, Protocol, runtime_checkable

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    try:
        from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
        from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    except ImportError:
        class SpyderLogger:  # type: ignore[no-redef]
            @staticmethod
            def get_logger(name: str) -> logging.Logger:
                return logging.getLogger(name)

        class SpyderErrorHandler:  # type: ignore[no-redef]
            pass

# ==============================================================================
# ENUMS
# ==============================================================================


class ReportFormat(Enum):
    """Supported report output formats."""

    HTML = "html"
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    EXCEL = "excel"
    TEXT = "text"
    MARKDOWN = "markdown"


class ReportType(Enum):
    """K-series report categories."""

    DAILY = "daily"
    PERFORMANCE = "performance"
    RISK = "risk"
    EXECUTION = "execution"
    PORTFOLIO = "portfolio"
    STRATEGY = "strategy"
    ML_PERFORMANCE = "ml_performance"
    REGULATORY = "regulatory"
    SHARPE = "sharpe"
    TEAR_SHEET = "tear_sheet"
    STRATEGY_PNL = "strategy_pnl"
    CUSTOM = "custom"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class ReportMetadata:
    """Lightweight header stamped on every generated report.

    Attributes:
        report_id:      UUID identifying this specific report run.
        report_type:    Category of the report (see :class:`ReportType`).
        generator_name: Class name of the generator that produced the report.
        generated_at:   UTC timestamp of report generation.
        period_start:   Start of the data window covered by the report.
        period_end:     End of the data window covered by the report.
        format:         Output format of the report payload.
        version:        Generator version string.
    """

    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    report_type: ReportType = ReportType.CUSTOM
    generator_name: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    period_start: date | None = None
    period_end: date | None = None
    format: ReportFormat = ReportFormat.JSON
    version: str = "1.0.0"


@dataclass
class ReportRequest:
    """Caller-supplied parameters describing a report run.

    Attributes:
        report_type:  Category of report to generate.
        format:       Desired output format.
        start_date:   Start of the reporting period (``None`` → use default).
        end_date:     End of the reporting period (``None`` → today).
        parameters:   Arbitrary key–value options passed through to the generator.
        output_path:  Optional filesystem path to write the report to.
    """

    report_type: ReportType = ReportType.DAILY
    format: ReportFormat = ReportFormat.JSON
    start_date: date | None = None
    end_date: date | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    output_path: str | None = None


@dataclass
class ReportResult:
    """Typed container returned by every :class:`ReportGeneratorProtocol`.

    Attributes:
        metadata: :class:`ReportMetadata` header for this run.
        payload:  The actual report content — format depends on ``metadata.format``.
                  Typically ``dict[str, Any]`` for JSON or ``str`` for HTML/TEXT.
        success:  ``True`` when the report was generated without errors.
        errors:   List of error / warning strings accumulated during generation.
    """

    metadata: ReportMetadata = field(default_factory=ReportMetadata)
    payload: Any = None
    success: bool = True
    errors: list[str] = field(default_factory=list)


# ==============================================================================
# PROTOCOL — structural typing contract for all K-series generators
# ==============================================================================


@runtime_checkable
class ReportGeneratorProtocol(Protocol):
    """Structural typing Protocol defining the public interface every K-series
    report generator must satisfy.

    All concrete K-series classes (K02–K13) satisfy this Protocol structurally;
    no explicit inheritance is required.

    Example::

        from SpyderK01_ReportGenerator import ReportGeneratorProtocol, ReportRequest

        def dispatch_report(generator: ReportGeneratorProtocol, request: ReportRequest):
            result = generator.generate_report(request)
            if not result.success:
                raise RuntimeError(result.errors)
            return result.payload
    """

    def generate_report(self, request: ReportRequest) -> ReportResult:
        """Generate a report according to *request* and return a :class:`ReportResult`.

        Args:
            request: :class:`ReportRequest` describing the desired report.

        Returns:
            :class:`ReportResult` containing the report payload and metadata.
        """
        ...

    def get_summary(self) -> dict[str, Any]:
        """Return a brief summary dict describing the generator's current state.

        Returns:
            Dict with at minimum ``{"generator": str, "report_type": str}``.
        """
        ...


# ==============================================================================
# ABSTRACT BASE CLASS — optional convenience base for new generators
# ==============================================================================


class BaseReportGenerator(ABC):
    """Optional ABC providing common infrastructure for K-series generators.

    Concrete classes may inherit this ABC **or** simply satisfy
    :class:`ReportGeneratorProtocol` structurally — both are acceptable.

    Provides:
        - ``self.logger``         — module-scoped :class:`SpyderLogger` instance
        - ``self.error_handler``  — :class:`SpyderErrorHandler` instance
        - ``_stamp_metadata()``   — fills :class:`ReportMetadata` from a request
        - ``generate_report()``   — abstract; subclasses must implement
        - ``get_summary()``       — abstract; subclasses must implement
    """

    def __init__(self) -> None:
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def generate_report(self, request: ReportRequest) -> ReportResult:
        """Generate a report according to *request*.

        Args:
            request: :class:`ReportRequest` with type, format, period, and options.

        Returns:
            :class:`ReportResult` containing the payload and generation metadata.
        """

    @abstractmethod
    def get_summary(self) -> dict[str, Any]:
        """Return a brief dict summarising the generator's current state."""

    # ------------------------------------------------------------------
    # Helpers available to subclasses
    # ------------------------------------------------------------------

    def _stamp_metadata(
        self,
        request: ReportRequest,
        generator_name: str = "",
        version: str = "1.0.0",
    ) -> ReportMetadata:
        """Build a :class:`ReportMetadata` header from *request*.

        Args:
            request:        The originating :class:`ReportRequest`.
            generator_name: Override for the generator class name field.
            version:        Generator version string.

        Returns:
            Populated :class:`ReportMetadata` instance.
        """
        return ReportMetadata(
            report_type=request.report_type,
            generator_name=generator_name or self.__class__.__name__,
            generated_at=datetime.now(UTC),
            period_start=request.start_date,
            period_end=request.end_date or date.today(),
            format=request.format,
            version=version,
        )


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    "ReportFormat",
    "ReportType",
    "ReportMetadata",
    "ReportRequest",
    "ReportResult",
    "ReportGeneratorProtocol",
    "BaseReportGenerator",
    # Legacy alias — keeps existing import sites working
    "ReportGenerator",
]

# Backward-compat alias so existing `from SpyderK01 import ReportGenerator` works
ReportGenerator = BaseReportGenerator
