#!/usr/bin/env python3
"""Focused regressions for lazy SpyderZ_Communication package exports."""

from __future__ import annotations

import importlib
import sys


_Z_PACKAGE = "Spyder.SpyderZ_Communication"
_Z_HEAVY_SUBMODULES = [
    f"{_Z_PACKAGE}.SpyderZ04_VolatilityEngine",
    f"{_Z_PACKAGE}.SpyderZ05_OrderRouter",
    f"{_Z_PACKAGE}.SpyderZ06_AutoHedger",
]
_Z_RESET_MODULES = [
    _Z_PACKAGE,
    f"{_Z_PACKAGE}.SpyderZ00_BrokerProtocol",
    f"{_Z_PACKAGE}.SpyderZ02_MessageProtocol",
    *_Z_HEAVY_SUBMODULES,
]


def _reset_z_modules() -> None:
    for module_name in _Z_RESET_MODULES:
        sys.modules.pop(module_name, None)

    spyder_pkg = sys.modules.get("Spyder")
    if spyder_pkg is not None and hasattr(spyder_pkg, "SpyderZ_Communication"):
        delattr(spyder_pkg, "SpyderZ_Communication")


def test_z_package_lazy_exports_keep_protocol_surface() -> None:
    _reset_z_modules()

    package = importlib.import_module(_Z_PACKAGE)

    assert "NormalizedOrderRequest" in package.__all__
    assert _Z_HEAVY_SUBMODULES[0] not in sys.modules

    normalized_order_request = package.NormalizedOrderRequest

    assert normalized_order_request.__name__ == "NormalizedOrderRequest"
    assert normalized_order_request.__module__.endswith("SpyderZ00_BrokerProtocol")
    assert _Z_HEAVY_SUBMODULES[0] not in sys.modules


def test_z_package_message_protocol_export_does_not_preload_heavy_modules() -> None:
    _reset_z_modules()

    package = importlib.import_module(_Z_PACKAGE)
    message_protocol = package.SpyderZ02_MessageProtocol

    assert message_protocol.__name__.endswith("SpyderZ02_MessageProtocol")
    assert all(module_name not in sys.modules for module_name in _Z_HEAVY_SUBMODULES)
