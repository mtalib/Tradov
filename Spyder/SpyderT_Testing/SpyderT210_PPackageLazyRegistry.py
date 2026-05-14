#!/usr/bin/env python3
"""Focused regressions for lazy SpyderP_PortfolioMgmt package exports."""

from __future__ import annotations

import importlib
import sys


_P_PACKAGE = "Spyder.SpyderP_PortfolioMgmt"
_P_REGISTRY_MODULE = f"{_P_PACKAGE}.SpyderP00_GlobalPortfolioRegistry"
_P_HEAVY_SUBMODULES = [
    f"{_P_PACKAGE}.SpyderP01_PortfolioManager",
    f"{_P_PACKAGE}.SpyderP03_CorrelationAnalyzer",
    f"{_P_PACKAGE}.SpyderP07_RenaissancePositionSizer",
]
_P_RESET_MODULES = [
    _P_PACKAGE,
    _P_REGISTRY_MODULE,
    *_P_HEAVY_SUBMODULES,
]


def _reset_p_modules() -> None:
    for module_name in _P_RESET_MODULES:
        sys.modules.pop(module_name, None)

    spyder_pkg = sys.modules.get("Spyder")
    if spyder_pkg is not None and hasattr(spyder_pkg, "SpyderP_PortfolioMgmt"):
        delattr(spyder_pkg, "SpyderP_PortfolioMgmt")


def test_p_package_import_stays_lazy() -> None:
    _reset_p_modules()

    package = importlib.import_module(_P_PACKAGE)

    assert "PortfolioManager" in package.__all__
    assert all(module_name not in sys.modules for module_name in _P_HEAVY_SUBMODULES)


def test_p_package_registry_helpers_do_not_preload_p01() -> None:
    _reset_p_modules()

    package = importlib.import_module(_P_PACKAGE)
    sentinel = object()

    assert package.get_global_portfolio_manager() is None
    package.set_global_portfolio_manager(sentinel)
    assert package.get_portfolio_manager() is sentinel
    package.reset_global_portfolio_manager()
    assert package.get_global_portfolio_manager() is None
    assert _P_HEAVY_SUBMODULES[0] not in sys.modules


def test_p_package_portfolio_manager_export_loads_only_p01() -> None:
    _reset_p_modules()

    package = importlib.import_module(_P_PACKAGE)
    portfolio_manager = package.PortfolioManager

    assert portfolio_manager.__name__ == "PortfolioManager"
    assert _P_HEAVY_SUBMODULES[0] in sys.modules
    assert _P_HEAVY_SUBMODULES[1] not in sys.modules
    assert _P_HEAVY_SUBMODULES[2] not in sys.modules
