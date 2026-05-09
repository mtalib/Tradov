#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: Spyder.SpyderU_Utilities
Module: SpyderU47_OptionalImport.py
Purpose: Canonical helper for optional imports with loud-on-use fallbacks
Author: SPYDER Trading System
Year Created: 2026
Last Updated: 2026-04-14

Module Description:
    Many Spyder modules import platform-specific (fcntl), heavy (torch,
    stable_baselines3, ray), or optional (hnswlib, chromadb) libraries.
    Scattering try/except ImportError blocks across the codebase produces
    silent fallbacks that hide real failures and confuses operators running
    on stripped-down containers.

    This helper centralises the pattern:

        from Spyder.SpyderU_Utilities.SpyderU47_OptionalImport import optional_import
        fcntl = optional_import("fcntl", required_on=("linux", "darwin"))
        torch = optional_import("torch", purpose="deep-learning features")

        if fcntl.available:
            fcntl.module.flock(...)

    The returned `OptionalImport` is truthy when the import succeeded and
    falsy otherwise, so `if fcntl:` works. Attribute access on a missing
    module raises a *loud* ImportError explaining which feature needs it.
"""

from __future__ import annotations

import importlib
import logging
import platform
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

_logger = logging.getLogger(__name__)


@dataclass
class OptionalImport:
    """Result wrapper for :func:`optional_import`.

    Attributes:
        name:     Dotted module name that was attempted.
        module:   The imported module, or None if import failed.
        error:    The ImportError captured, or None on success.
        purpose:  Human-readable description of what the module enables.
    """

    name: str
    module: Any | None = None
    error: BaseException | None = None
    purpose: str = ""
    _warned_on: set[str] = field(default_factory=set)

    @property
    def available(self) -> bool:
        return self.module is not None

    def __bool__(self) -> bool:
        return self.available

    def __getattr__(self, item: str) -> Any:
        # Only hit when `item` is not already a dataclass field
        mod = object.__getattribute__(self, "__dict__").get("module")
        if mod is None:
            raise ImportError(
                f"Optional dependency '{self.name}' is not installed "
                f"(needed for: {self.purpose or 'unspecified feature'}). "
                f"Original error: {self.error}"
            )
        return getattr(mod, item)

    def warn_once(self, key: str = "") -> None:
        """Emit a single warning log the first time a caller notes the absence.

        Use when a feature gracefully degrades rather than failing. Repeated
        calls with the same key are no-ops to keep logs clean.
        """
        if self.available:
            return
        if key in self._warned_on:
            return
        self._warned_on.add(key)
        _logger.warning(
            "Optional dependency '%s' unavailable%s — %s disabled",
            self.name,
            f" ({self.purpose})" if self.purpose else "",
            key or self.purpose or "dependent feature",
        )


def optional_import(
    name: str,
    *,
    purpose: str = "",
    required_on: Iterable[str] | None = None,
) -> OptionalImport:
    """Attempt to import ``name``; return an :class:`OptionalImport` wrapper.

    Args:
        name:         Dotted module name (e.g., ``"fcntl"``, ``"torch.nn"``).
        purpose:      Human description of the feature the module enables;
                      shown in the error message if a consumer tries to use
                      the module when it's missing.
        required_on:  Optional iterable of platform names (matched against
                      ``platform.system().lower()``) where the import is
                      considered mandatory. If the current platform is in
                      this set and the import fails, the underlying
                      ImportError is re-raised immediately.

    Returns:
        ``OptionalImport`` — truthy if the import succeeded.
    """
    try:
        module = importlib.import_module(name)
        return OptionalImport(name=name, module=module, purpose=purpose)
    except ImportError as exc:
        if required_on:
            current = platform.system().lower()
            normalised = {p.lower() for p in required_on}
            if current in normalised:
                raise
        return OptionalImport(name=name, module=None, error=exc, purpose=purpose)
