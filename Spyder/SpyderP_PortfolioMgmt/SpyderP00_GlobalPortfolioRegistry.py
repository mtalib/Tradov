#!/usr/bin/env python3
"""Lightweight global PortfolioManager registry for startup-sensitive paths."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .SpyderP01_PortfolioManager import PortfolioManager


_global_portfolio_manager: Any = None
_global_portfolio_manager_lock = threading.RLock()


def get_global_portfolio_manager() -> PortfolioManager | None:
    """Get the shared portfolio manager instance."""
    with _global_portfolio_manager_lock:
        return _global_portfolio_manager


def get_portfolio_manager() -> PortfolioManager | None:
    """Backward-compatible alias for the shared portfolio manager accessor."""
    return get_global_portfolio_manager()


def set_global_portfolio_manager(portfolio_manager: PortfolioManager) -> None:
    """Publish the shared portfolio manager instance."""
    global _global_portfolio_manager
    with _global_portfolio_manager_lock:
        _global_portfolio_manager = portfolio_manager


def reset_global_portfolio_manager() -> None:
    """Clear the shared portfolio manager instance."""
    global _global_portfolio_manager
    with _global_portfolio_manager_lock:
        _global_portfolio_manager = None


def create_portfolio_manager(
    initial_capital: float = 100000,
    config: dict[str, Any] | None = None,
) -> PortfolioManager:
    """Create a PortfolioManager lazily so callers avoid importing P01 by default."""
    from .SpyderP01_PortfolioManager import create_portfolio_manager as _create_portfolio_manager

    return _create_portfolio_manager(initial_capital=initial_capital, config=config)