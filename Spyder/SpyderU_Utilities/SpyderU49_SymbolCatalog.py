#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU49_SymbolCatalog.py
Purpose: Canonical market symbol catalog and derived symbol views

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-28 Time: 00:00:00
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FetchRequirement = Literal["quote", "computed", "proxy", "event-only"]


@dataclass(frozen=True)
class SymbolDefinition:
    """Canonical symbol metadata for dashboard, worker, and backend consumers."""

    symbol: str
    display_category: str | None
    visible: bool
    fetch_requirement: FetchRequirement
    provider_symbol: str | None = None
    backend_symbol: str | None = None
    optional: bool = False
    deprecated: bool = False


CATEGORY_ORDER: tuple[str, ...] = (
    "MAJOR INDICES",
    "MARKET INTERNALS",
    "VOLATILITY",
    "OPTIONS ANALYTICS",
    "BONDS & CREDIT",
    "CORRELATIONS",
    "CUSTOM METRICS",
)


# NOTE:
# - provider_symbol is the quote symbol used for direct fetches.
# - symbol is the dashboard/display key after remaps.
# - backend_symbol supports legacy market-data group naming (e.g. TICK-NYSE).
SYMBOL_CATALOG: tuple[SymbolDefinition, ...] = (
    SymbolDefinition("DIA", "MAJOR INDICES", True, "quote", provider_symbol="DIA", backend_symbol="DIA"),
    SymbolDefinition("SPY", "MAJOR INDICES", True, "quote", provider_symbol="SPY", backend_symbol="SPY"),
    SymbolDefinition("SPX", "S&P CORE", False, "quote", provider_symbol="SPX", backend_symbol="SPX"),
    SymbolDefinition("$DJI", None, False, "quote", provider_symbol="$DJI"),
    SymbolDefinition("NDX", None, False, "quote", provider_symbol="NDX"),
    SymbolDefinition("RUT", None, False, "quote", provider_symbol="RUT"),

    SymbolDefinition("VIX", "VOLATILITY", True, "quote", provider_symbol="VIX", backend_symbol="VIX"),
    SymbolDefinition("VIX9D", "VOLATILITY", True, "quote", provider_symbol="VIX9D", backend_symbol="VIX9D"),
    # VXV (CBOE 3-Month Vol) is not available via Tradier; mark optional so a missing
    # quote does not produce a blank/stale widget — the widget will render "N/A" instead.
    SymbolDefinition("VXV", "VOLATILITY", True, "event-only", backend_symbol="VXV", optional=True),
    SymbolDefinition("VVIX", "VOLATILITY", True, "quote", provider_symbol="VVIX", backend_symbol="VVIX"),
    SymbolDefinition("SKEW", "VOLATILITY", True, "quote", provider_symbol="SKEW", backend_symbol="SKEW"),

    SymbolDefinition("$TICK", "MARKET INTERNALS", True, "event-only", backend_symbol="TICK-NYSE"),
    SymbolDefinition("$TRIN", "MARKET INTERNALS", True, "event-only", backend_symbol="TRIN-NYSE"),
    SymbolDefinition("$ADD", "MARKET INTERNALS", True, "event-only", backend_symbol="ADD-NYSE"),
    SymbolDefinition("NYMO", "MARKET INTERNALS", True, "event-only", optional=True),
    SymbolDefinition("$VOLD", "MARKET INTERNALS", True, "event-only", optional=True),
    SymbolDefinition("RVOL", "MARKET INTERNALS", True, "computed", optional=True),

    SymbolDefinition("QQQ", "MAJOR INDICES", True, "quote", provider_symbol="QQQ", backend_symbol="QQQ"),
    SymbolDefinition("IWM", "MAJOR INDICES", True, "quote", provider_symbol="IWM", backend_symbol="IWM"),

    SymbolDefinition("TLT", "BONDS & CREDIT", True, "quote", provider_symbol="TLT", backend_symbol="TLT"),
    SymbolDefinition("HYG", "BONDS & CREDIT", True, "quote", provider_symbol="HYG"),
    SymbolDefinition("LQD", "BONDS & CREDIT", True, "quote", provider_symbol="LQD", backend_symbol="LQD"),
    SymbolDefinition("TNX", "BONDS & CREDIT", True, "event-only", optional=True),

    # DXY is represented by UUP at quote-fetch time.
    SymbolDefinition("DXY", "CORRELATIONS", True, "proxy", provider_symbol="UUP", backend_symbol="DXY"),
    SymbolDefinition("GLD", "CORRELATIONS", True, "quote", provider_symbol="GLD", backend_symbol="GLD"),
    SymbolDefinition("USO", "CORRELATIONS", True, "quote", provider_symbol="USO", backend_symbol="USO"),
    SymbolDefinition("XLK", "CORRELATIONS", True, "quote", provider_symbol="XLK", optional=True),
    SymbolDefinition("XLF", "CORRELATIONS", True, "quote", provider_symbol="XLF", optional=True),

    SymbolDefinition("IVR", "OPTIONS ANALYTICS", True, "event-only", optional=True),
    SymbolDefinition("ATM_IV", "OPTIONS ANALYTICS", True, "event-only", optional=True),
    SymbolDefinition("VRP", "OPTIONS ANALYTICS", True, "event-only", optional=True),
    SymbolDefinition("CPC", "OPTIONS ANALYTICS", True, "computed", backend_symbol="CPC"),

    SymbolDefinition("GEX", "CUSTOM METRICS", True, "event-only", optional=True),
    SymbolDefinition("DEX", "CUSTOM METRICS", True, "event-only", optional=True),
    SymbolDefinition("OGL", "CUSTOM METRICS", True, "event-only", optional=True),
    SymbolDefinition("DIX", "CUSTOM METRICS", True, "event-only", optional=True),
    SymbolDefinition("WRS", "CUSTOM METRICS", True, "computed", optional=True),
    SymbolDefinition("PSR", "CUSTOM METRICS", True, "computed", optional=True),
    SymbolDefinition("SWAN", "CUSTOM METRICS", True, "event-only", optional=True),
    SymbolDefinition("PMR", "CUSTOM METRICS", True, "computed", optional=True),

)


BACKEND_GROUP_ORDER: tuple[str, ...] = (
    "CORE",
    "VOLATILITY",
    "INTERNALS",
    "INDICES",
    "FIXED_INCOME",
    "CORRELATIONS",
)

_BACKEND_GROUP_TO_CATEGORY: dict[str, str] = {
    "CORE": "S&P CORE",
    "VOLATILITY": "VOLATILITY",
    "INTERNALS": "MARKET INTERNALS",
    "INDICES": "MAJOR INDICES",
    "FIXED_INCOME": "BONDS & CREDIT",
    "CORRELATIONS": "CORRELATIONS",
}


def get_symbol_catalog() -> tuple[SymbolDefinition, ...]:
    """Return the canonical symbol catalog."""
    return SYMBOL_CATALOG


def get_market_overview_symbols() -> dict[str, list[str]]:
    """Return visible market-overview symbols grouped by display category."""
    grouped: dict[str, list[str]] = {category: [] for category in CATEGORY_ORDER}
    for definition in SYMBOL_CATALOG:
        if not definition.visible or not definition.display_category:
            continue
        grouped[definition.display_category].append(definition.symbol)

    return {category: symbols for category, symbols in grouped.items() if symbols}


def get_market_overview_symbol_set() -> set[str]:
    """Return the set of all visible market-overview symbols."""
    return {
        symbol
        for symbols in get_market_overview_symbols().values()
        for symbol in symbols
    }


def get_quote_symbol_basket(include_deprecated: bool = True) -> list[str]:
    """Return the canonical quote-fetch basket for worker slow/fast/EOD paths."""
    seen: set[str] = set()
    basket: list[str] = []
    for definition in SYMBOL_CATALOG:
        if definition.fetch_requirement not in {"quote", "proxy"}:
            continue
        if definition.deprecated and not include_deprecated:
            continue
        provider_symbol = definition.provider_symbol or definition.symbol
        if provider_symbol not in seen:
            basket.append(provider_symbol)
            seen.add(provider_symbol)
    return basket


def get_quote_symbol_remap() -> dict[str, str]:
    """Return provider-symbol to display-symbol remaps for proxy symbols."""
    remap: dict[str, str] = {}
    for definition in SYMBOL_CATALOG:
        if definition.fetch_requirement != "proxy":
            continue
        provider_symbol = definition.provider_symbol or definition.symbol
        remap[provider_symbol] = definition.symbol
    return remap


def get_computed_or_event_symbols() -> set[str]:
    """Return symbols that must not be direct quote fetched."""
    return {
        definition.symbol
        for definition in SYMBOL_CATALOG
        if definition.fetch_requirement in {"computed", "event-only"}
    }


def get_optional_symbols() -> set[str]:
    """Return symbols flagged as optional in the canonical catalog."""
    return {
        definition.symbol
        for definition in SYMBOL_CATALOG
        if definition.optional
    }


def get_deprecated_symbols() -> set[str]:
    """Return symbols retained only for backward-compatibility or staged removal."""
    return {
        definition.symbol
        for definition in SYMBOL_CATALOG
        if definition.deprecated
    }


def get_worker_live_data_keys() -> set[str]:
    """Return the expected base live_data keys written directly by G18.

    This covers quote/proxy symbols after remap plus worker-computed metrics.
    Event-only/custom-metric producers may append additional keys at runtime.
    """
    remap = get_quote_symbol_remap()
    keys = {
        remap.get(provider_symbol, provider_symbol)
        for provider_symbol in get_quote_symbol_basket(include_deprecated=False)
    }
    # v27 fix: VXV (CBOE 3-Month Vol) is event-only at the catalog level
    # because Tradier doesn't quote it directly, but it IS written to live_data
    # by an event/derived producer (G18 worker emits a synthetic VXV when
    # available). Include it in the worker keys set so widget-binding stays
    # consistent and T183 catalog test matches reality.
    keys.update({"CPC", "RVOL", "VXV"})
    return keys


def get_realtime_sentinel_symbols() -> tuple[str, ...]:
    """Return symbols used to determine realtime freshness health."""
    return ("SPY", "SPX", "QQQ")


def get_backend_symbol_groups() -> dict[str, list[str]]:
    """Return backend symbol groups for C01/C17 defaults."""
    groups: dict[str, list[str]] = {group_name: [] for group_name in BACKEND_GROUP_ORDER}

    for definition in SYMBOL_CATALOG:
        if not definition.display_category:
            continue
        backend_symbol = definition.backend_symbol
        if not backend_symbol:
            continue

        for group_name, category in _BACKEND_GROUP_TO_CATEGORY.items():
            if definition.display_category != category:
                continue
            groups[group_name].append(backend_symbol)
            break

    return groups


def build_default_symbol_config() -> dict:
    """Build C17-compatible default symbol configuration from canonical policy."""
    backend_groups = get_backend_symbol_groups()

    return {
        "visible_symbols": {
            "S&P_CORE": {
                "symbols": backend_groups["CORE"],
                "update_frequency": 1,
                "priority": "CRITICAL",
            },
            "VOLATILITY": {
                "symbols": backend_groups["VOLATILITY"],
                "update_frequency": 5,
                "priority": "HIGH",
            },
            "MARKET_INTERNALS": {
                "symbols": backend_groups["INTERNALS"],
                "update_frequency": 5,
                "priority": "HIGH",
            },
            "MAJOR_INDICES": {
                "symbols": backend_groups["INDICES"],
                "update_frequency": 5,
                "priority": "MEDIUM",
            },
            "BONDS_CREDIT": {
                "symbols": backend_groups["FIXED_INCOME"],
                "update_frequency": 15,
                "priority": "LOW",
            },
            "CORRELATIONS": {
                "symbols": backend_groups["CORRELATIONS"],
                "update_frequency": 15,
                "priority": "LOW",
            },
        },
        "hidden_symbols": {
            "VIX_FUTURES": {"symbols": ["VX"], "update_frequency": 5, "priority": "MEDIUM"},
            "ADDITIONAL_INTERNALS": {
                "symbols": [
                    "ADVN-NYSE",
                    "DECN-NYSE",
                    "UVOL-NYSE",
                    "DVOL-NYSE",
                    "VOLD-NYSE",
                    "NYHL-NYSE",
                ],
                "update_frequency": 5,
                "priority": "MEDIUM",
            },
            "SECTOR_ETFS": {
                "symbols": [
                    "XLF",
                    "XLK",
                    "XLE",
                    "XLV",
                    "XLI",
                    "XLY",
                    "XLP",
                    "XLU",
                    "XLRE",
                    "XLC",
                    "XLB",
                ],
                "update_frequency": 30,
                "priority": "LOW",
            },
        },
        "custom_metrics": {
            "GEX": {"update_frequency": 60, "priority": "HIGH"},
            "DEX": {"update_frequency": 60, "priority": "HIGH"},
            "OGL": {"update_frequency": 60, "priority": "HIGH"},
            "DIX": {"update_frequency": 300, "priority": "MEDIUM"},
            "SWAN": {"update_frequency": 60, "priority": "CRITICAL"},
            "WRS": {"update_frequency": 60, "priority": "MEDIUM"},
            "PSR": {"update_frequency": 60, "priority": "MEDIUM"},
            "PMR": {"update_frequency": 60, "priority": "MEDIUM"},
        },
    }


__all__ = [
    "CATEGORY_ORDER",
    "SYMBOL_CATALOG",
    "SymbolDefinition",
    "build_default_symbol_config",
    "get_deprecated_symbols",
    "get_backend_symbol_groups",
    "get_computed_or_event_symbols",
    "get_market_overview_symbol_set",
    "get_market_overview_symbols",
    "get_optional_symbols",
    "get_quote_symbol_basket",
    "get_quote_symbol_remap",
    "get_realtime_sentinel_symbols",
    "get_symbol_catalog",
    "get_worker_live_data_keys",
]
