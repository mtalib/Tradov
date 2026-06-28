#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: Tradov.TradovU_Utilities
Module: TradovU49_SymbolCatalog.py
Purpose: Canonical market symbol catalog and derived symbol views

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07
"""

from __future__ import annotations

from dataclasses import dataclass
import os
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
    "CUSTOM METRICS",
    "VOLATILITY",
    "OPTIONS ANALYTICS",
    "BONDS & CREDIT",
    "CORRELATIONS",
    "PAIR EQUITIES",
    "PAIR ETFS",
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
    # TNX (10-Year Treasury Yield) is sourced exclusively from FRED via
    # TradovS09_FREDClient → TradovS07_CustomMetricsOrchestrator → metrics_updated
    # signal → _on_custom_metrics_updated → widget.update_data().
    # Tradier's equity-quotes endpoint does NOT serve $TNX, so "proxy" was wrong:
    # it needlessly added $TNX to G18's quote basket (wasted call, never returned).
    # "event-only" keeps TNX visible in the Market Overview but excludes it from
    # every Tradier quote fetch.
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
    SymbolDefinition("PCA-PROXY", "CUSTOM METRICS", True, "event-only", optional=True),
    SymbolDefinition("PCA-IV", "CUSTOM METRICS", True, "event-only", optional=True),
    SymbolDefinition("WRS", "CUSTOM METRICS", True, "computed", optional=True),
    SymbolDefinition("PSR", "CUSTOM METRICS", True, "computed", optional=True),
    SymbolDefinition("SWAN", "CUSTOM METRICS", True, "event-only", optional=True),
    SymbolDefinition("PMR", "CUSTOM METRICS", True, "computed", optional=True),

    # ── PAIR TRADING EQUITIES (50 stocks across 10 sectors) ──
    # Technology
    SymbolDefinition("AAPL", "PAIR EQUITIES", True, "quote", provider_symbol="AAPL"),
    SymbolDefinition("MSFT", "PAIR EQUITIES", True, "quote", provider_symbol="MSFT"),
    SymbolDefinition("GOOGL", "PAIR EQUITIES", True, "quote", provider_symbol="GOOGL"),
    SymbolDefinition("META", "PAIR EQUITIES", True, "quote", provider_symbol="META"),
    SymbolDefinition("AMZN", "PAIR EQUITIES", True, "quote", provider_symbol="AMZN"),
    # Financials
    SymbolDefinition("JPM", "PAIR EQUITIES", True, "quote", provider_symbol="JPM"),
    SymbolDefinition("BAC", "PAIR EQUITIES", True, "quote", provider_symbol="BAC"),
    SymbolDefinition("WFC", "PAIR EQUITIES", True, "quote", provider_symbol="WFC"),
    SymbolDefinition("GS", "PAIR EQUITIES", True, "quote", provider_symbol="GS"),
    SymbolDefinition("MS", "PAIR EQUITIES", True, "quote", provider_symbol="MS"),
    # Healthcare
    SymbolDefinition("JNJ", "PAIR EQUITIES", True, "quote", provider_symbol="JNJ"),
    SymbolDefinition("UNH", "PAIR EQUITIES", True, "quote", provider_symbol="UNH"),
    SymbolDefinition("PFE", "PAIR EQUITIES", True, "quote", provider_symbol="PFE"),
    SymbolDefinition("MRK", "PAIR EQUITIES", True, "quote", provider_symbol="MRK"),
    SymbolDefinition("ABBV", "PAIR EQUITIES", True, "quote", provider_symbol="ABBV"),
    # Energy
    SymbolDefinition("XOM", "PAIR EQUITIES", True, "quote", provider_symbol="XOM"),
    SymbolDefinition("CVX", "PAIR EQUITIES", True, "quote", provider_symbol="CVX"),
    SymbolDefinition("COP", "PAIR EQUITIES", True, "quote", provider_symbol="COP"),
    SymbolDefinition("SLB", "PAIR EQUITIES", True, "quote", provider_symbol="SLB"),
    SymbolDefinition("EOG", "PAIR EQUITIES", True, "quote", provider_symbol="EOG"),
    # Industrials
    SymbolDefinition("CAT", "PAIR EQUITIES", True, "quote", provider_symbol="CAT"),
    SymbolDefinition("GE", "PAIR EQUITIES", True, "quote", provider_symbol="GE"),
    SymbolDefinition("MMM", "PAIR EQUITIES", True, "quote", provider_symbol="MMM"),
    SymbolDefinition("HON", "PAIR EQUITIES", True, "quote", provider_symbol="HON"),
    SymbolDefinition("BA", "PAIR EQUITIES", True, "quote", provider_symbol="BA"),
    # Consumer Discretionary
    SymbolDefinition("HD", "PAIR EQUITIES", True, "quote", provider_symbol="HD"),
    SymbolDefinition("LOW", "PAIR EQUITIES", True, "quote", provider_symbol="LOW"),
    SymbolDefinition("TSLA", "PAIR EQUITIES", True, "quote", provider_symbol="TSLA"),
    SymbolDefinition("NKE", "PAIR EQUITIES", True, "quote", provider_symbol="NKE"),
    SymbolDefinition("TGT", "PAIR EQUITIES", True, "quote", provider_symbol="TGT"),
    # Consumer Staples
    SymbolDefinition("PG", "PAIR EQUITIES", True, "quote", provider_symbol="PG"),
    SymbolDefinition("KO", "PAIR EQUITIES", True, "quote", provider_symbol="KO"),
    SymbolDefinition("PEP", "PAIR EQUITIES", True, "quote", provider_symbol="PEP"),
    SymbolDefinition("COST", "PAIR EQUITIES", True, "quote", provider_symbol="COST"),
    SymbolDefinition("WMT", "PAIR EQUITIES", True, "quote", provider_symbol="WMT"),
    # Materials
    SymbolDefinition("LIN", "PAIR EQUITIES", True, "quote", provider_symbol="LIN"),
    SymbolDefinition("APD", "PAIR EQUITIES", True, "quote", provider_symbol="APD"),
    SymbolDefinition("SHW", "PAIR EQUITIES", True, "quote", provider_symbol="SHW"),
    SymbolDefinition("DD", "PAIR EQUITIES", True, "quote", provider_symbol="DD"),
    SymbolDefinition("NEM", "PAIR EQUITIES", True, "quote", provider_symbol="NEM"),
    # Utilities
    SymbolDefinition("NEE", "PAIR EQUITIES", True, "quote", provider_symbol="NEE"),
    SymbolDefinition("DUK", "PAIR EQUITIES", True, "quote", provider_symbol="DUK"),
    SymbolDefinition("SO", "PAIR EQUITIES", True, "quote", provider_symbol="SO"),
    SymbolDefinition("D", "PAIR EQUITIES", True, "quote", provider_symbol="D"),
    SymbolDefinition("AEP", "PAIR EQUITIES", True, "quote", provider_symbol="AEP"),
    # Communication Services
    SymbolDefinition("DIS", "PAIR EQUITIES", True, "quote", provider_symbol="DIS"),
    SymbolDefinition("NFLX", "PAIR EQUITIES", True, "quote", provider_symbol="NFLX"),
    SymbolDefinition("CMCSA", "PAIR EQUITIES", True, "quote", provider_symbol="CMCSA"),
    SymbolDefinition("T", "PAIR EQUITIES", True, "quote", provider_symbol="T"),
    SymbolDefinition("VZ", "PAIR EQUITIES", True, "quote", provider_symbol="VZ"),

    # ── PAIR TRADING ETFS (30 ETFs for sector/asset-class pairs) ──
    # Sector ETFs (Select SPDR)
    SymbolDefinition("XLK", "PAIR ETFS", True, "quote", provider_symbol="XLK"),
    SymbolDefinition("XLF", "PAIR ETFS", True, "quote", provider_symbol="XLF"),
    SymbolDefinition("XLE", "PAIR ETFS", True, "quote", provider_symbol="XLE"),
    SymbolDefinition("XLV", "PAIR ETFS", True, "quote", provider_symbol="XLV"),
    SymbolDefinition("XLI", "PAIR ETFS", True, "quote", provider_symbol="XLI"),
    SymbolDefinition("XLY", "PAIR ETFS", True, "quote", provider_symbol="XLY"),
    SymbolDefinition("XLP", "PAIR ETFS", True, "quote", provider_symbol="XLP"),
    SymbolDefinition("XLU", "PAIR ETFS", True, "quote", provider_symbol="XLU"),
    SymbolDefinition("XLRE", "PAIR ETFS", True, "quote", provider_symbol="XLRE"),
    SymbolDefinition("XLC", "PAIR ETFS", True, "quote", provider_symbol="XLC"),
    SymbolDefinition("XLB", "PAIR ETFS", True, "quote", provider_symbol="XLB"),
    # Vanguard Sector ETFs (natural pairs with SPDRs)
    SymbolDefinition("VGT", "PAIR ETFS", True, "quote", provider_symbol="VGT"),
    SymbolDefinition("VFH", "PAIR ETFS", True, "quote", provider_symbol="VFH"),
    SymbolDefinition("VDE", "PAIR ETFS", True, "quote", provider_symbol="VDE"),
    SymbolDefinition("VHT", "PAIR ETFS", True, "quote", provider_symbol="VHT"),
    SymbolDefinition("VIS", "PAIR ETFS", True, "quote", provider_symbol="VIS"),
    SymbolDefinition("VCR", "PAIR ETFS", True, "quote", provider_symbol="VCR"),
    SymbolDefinition("VDC", "PAIR ETFS", True, "quote", provider_symbol="VDC"),
    SymbolDefinition("VPU", "PAIR ETFS", True, "quote", provider_symbol="VPU"),
    SymbolDefinition("VNQ", "PAIR ETFS", True, "quote", provider_symbol="VNQ"),
    SymbolDefinition("VOX", "PAIR ETFS", True, "quote", provider_symbol="VOX"),
    # iShares Sector ETFs
    SymbolDefinition("IYW", "PAIR ETFS", True, "quote", provider_symbol="IYW"),
    SymbolDefinition("IYF", "PAIR ETFS", True, "quote", provider_symbol="IYF"),
    SymbolDefinition("IYE", "PAIR ETFS", True, "quote", provider_symbol="IYE"),
    SymbolDefinition("IYH", "PAIR ETFS", True, "quote", provider_symbol="IYH"),
    SymbolDefinition("IYJ", "PAIR ETFS", True, "quote", provider_symbol="IYJ"),
    # Broad-market / factor ETFs
    SymbolDefinition("RSP", "PAIR ETFS", True, "quote", provider_symbol="RSP"),
    SymbolDefinition("QQQE", "PAIR ETFS", True, "quote", provider_symbol="QQQE"),
    SymbolDefinition("SPYV", "PAIR ETFS", True, "quote", provider_symbol="SPYV"),
    SymbolDefinition("SPYG", "PAIR ETFS", True, "quote", provider_symbol="SPYG"),
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


def get_active_pair_corpus_symbols() -> list[str]:
    """Return ordered symbols from the active pair bundle or corpus policy.

    Runtime hydration should stay narrow. Prefer the selected bundle if one is
    configured, otherwise fall back to the best-fit bundle for the current
    policy context, and only then fall back to the legacy active-pairs corpus.
    """
    try:
        from Tradov.TradovD_Strategies.TradovD59_PairCorpusPolicy import (  # noqa: PLC0415
            load_pair_trading_corpus_policy,
        )
    except Exception:
        return []

    try:
        policy = load_pair_trading_corpus_policy()
    except Exception:
        return []

    # Prefer the selected bundle, then the best bundle, before widening to the
    # older active-pairs corpus. This keeps runtime hydration aligned with the
    # small bundle set used by the scanner.
    bundle_name = str(getattr(policy, "active_bundle_name", "") or "").strip()
    bundle_keys: tuple[str, ...] = ()
    if bundle_name:
        bundle_keys = policy.get_bundle_pair_keys(bundle_name)
    if not bundle_keys:
        selection = policy.select_bundle()
        if selection is not None:
            bundle_keys = tuple(selection.pair_keys)

    if bundle_keys:
        seen: set[str] = set()
        basket: list[str] = []
        for pair_key in bundle_keys:
            for symbol in pair_key.split("/", 1):
                normalized = str(symbol or "").strip().upper()
                if not normalized or normalized in seen:
                    continue
                basket.append(normalized)
                seen.add(normalized)
        if basket:
            return basket

    seen: set[str] = set()
    basket: list[str] = []
    for entry in getattr(policy, "active_pairs", ()) or ():
        for symbol in (getattr(entry, "leg_a", None), getattr(entry, "leg_b", None)):
            normalized = str(symbol or "").strip().upper()
            if not normalized or normalized in seen:
                continue
            basket.append(normalized)
            seen.add(normalized)
    return basket


def get_runtime_quote_symbol_basket(include_deprecated: bool = True) -> list[str]:
    """Return the runtime hydration basket: core dashboard quotes plus active pairs."""
    active_pair_symbols = set(get_active_pair_corpus_symbols())
    if not active_pair_symbols:
        active_pair_symbols = set(get_runtime_pair_quote_basket())

    seen: set[str] = set()
    basket: list[str] = []
    for definition in SYMBOL_CATALOG:
        if definition.fetch_requirement not in {"quote", "proxy"}:
            continue
        if definition.deprecated and not include_deprecated:
            continue
        provider_symbol = (definition.provider_symbol or definition.symbol).strip().upper()
        if provider_symbol in seen:
            continue

        category = str(definition.display_category or "")
        if category not in {"PAIR EQUITIES", "PAIR ETFS"} or provider_symbol in active_pair_symbols:
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
    return ("SPX", "QQQ", "VIX")


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
            "PCA-PROXY": {"update_frequency": 300, "priority": "MEDIUM"},
            "PCA-IV": {"update_frequency": 300, "priority": "LOW"},
            "SWAN": {"update_frequency": 60, "priority": "CRITICAL"},
            "WRS": {"update_frequency": 60, "priority": "MEDIUM"},
            "PSR": {"update_frequency": 60, "priority": "MEDIUM"},
            "PMR": {"update_frequency": 60, "priority": "MEDIUM"},
        },
    }


PAIR_EQUITY_SECTORS: dict[str, tuple[str, ...]] = {
    "Technology": ("AAPL", "MSFT", "GOOGL", "META", "AMZN"),
    "Financials": ("JPM", "BAC", "WFC", "GS", "MS"),
    "Healthcare": ("JNJ", "UNH", "PFE", "MRK", "ABBV"),
    "Energy": ("XOM", "CVX", "COP", "SLB", "EOG"),
    "Industrials": ("CAT", "GE", "MMM", "HON", "BA"),
    "Consumer Discretionary": ("HD", "LOW", "TSLA", "NKE", "TGT"),
    "Consumer Staples": ("PG", "KO", "PEP", "COST", "WMT"),
    "Materials": ("LIN", "APD", "SHW", "DD", "NEM"),
    "Utilities": ("NEE", "DUK", "SO", "D", "AEP"),
    "Communication Services": ("DIS", "NFLX", "CMCSA", "T", "VZ"),
}

DEFAULT_PAIR_DEFINITIONS: tuple[tuple[str, str, str, str], ...] = (
    # Equity pairs (same sector)
    ("HD", "LOW", "Consumer Discretionary", "equity"),
    ("JPM", "BAC", "Financials", "equity"),
    ("XOM", "CVX", "Energy", "equity"),
    ("PG", "KO", "Consumer Staples", "equity"),
    ("JNJ", "UNH", "Healthcare", "equity"),
    ("AAPL", "MSFT", "Technology", "equity"),
    ("GOOGL", "META", "Technology", "equity"),
    ("PEP", "KO", "Consumer Staples", "equity"),
    ("COST", "WMT", "Consumer Staples", "equity"),
    ("CAT", "GE", "Industrials", "equity"),
    # ETF pairs (SPDR ↔ Vanguard)
    ("XLE", "VDE", "Energy", "etf"),
    ("XLF", "VFH", "Financials", "etf"),
    ("XLK", "VGT", "Technology", "etf"),
    ("XLV", "VHT", "Healthcare", "etf"),
    ("XLI", "VIS", "Industrials", "etf"),
    ("XLY", "VCR", "Consumer Discretionary", "etf"),
    ("XLP", "VDC", "Consumer Staples", "etf"),
    ("XLU", "VPU", "Utilities", "etf"),
    ("XLRE", "VNQ", "Real Estate", "etf"),
    ("XLC", "VOX", "Communication Services", "etf"),
    # Cross-asset / thematic
    ("XLF", "XLE", "Cross-Sector", "cross_asset"),
    ("XLK", "XLV", "Tech vs Healthcare", "cross_asset"),
    ("XLY", "XLP", "Discretionary vs Staples", "cross_asset"),
    ("XLE", "XLU", "Energy vs Utilities", "cross_asset"),
    ("XLF", "XLI", "Financials vs Industrials", "cross_asset"),
)


def get_pair_equity_symbols() -> set[str]:
    return {
        definition.symbol
        for definition in SYMBOL_CATALOG
        if definition.display_category == "PAIR EQUITIES"
    }


def get_pair_etf_symbols() -> set[str]:
    return {
        definition.symbol
        for definition in SYMBOL_CATALOG
        if definition.display_category == "PAIR ETFS"
    }


def get_pair_universe() -> set[str]:
    return get_pair_equity_symbols() | get_pair_etf_symbols()


def get_core_pair_equity_symbols() -> list[str]:
    """Return the ordered symbol basket for the core equity pair set."""
    seen: set[str] = set()
    basket: list[str] = []
    for sym_a, sym_b, _sector, pair_type in DEFAULT_PAIR_DEFINITIONS:
        if pair_type != "equity":
            continue
        for symbol in (sym_a, sym_b):
            if symbol not in seen:
                basket.append(symbol)
                seen.add(symbol)
    return basket


def get_core_pair_universe() -> set[str]:
    """Return the reduced runtime pair universe used while fd stability is under review."""
    return set(get_core_pair_equity_symbols())


def get_core_pair_quote_basket() -> list[str]:
    """Return the reduced runtime quote basket for the core pair universe."""
    return get_core_pair_equity_symbols()


def _runtime_pair_universe_mode() -> str:
    """Return the configured runtime pair-universe mode."""
    mode = str(os.environ.get("TRADOV_PAIR_UNIVERSE_MODE", "core")).strip().lower()
    if mode in {"full", "all", "extended"}:
        return "full"
    return "core"


def get_runtime_pair_universe_mode() -> str:
    """Return the active runtime pair-universe mode."""
    return _runtime_pair_universe_mode()


def get_runtime_pair_equity_symbols() -> list[str]:
    """Return the active runtime equity symbol basket."""
    active_pair_symbols = get_active_pair_corpus_symbols()
    if active_pair_symbols:
        return active_pair_symbols
    if _runtime_pair_universe_mode() == "full":
        return sorted(get_pair_equity_symbols())
    return get_core_pair_equity_symbols()


def get_runtime_pair_universe() -> set[str]:
    """Return the active runtime pair universe."""
    active_pair_symbols = set(get_active_pair_corpus_symbols())
    if active_pair_symbols:
        return active_pair_symbols
    if _runtime_pair_universe_mode() == "full":
        return get_pair_universe()
    return get_core_pair_universe()


def get_runtime_pair_quote_basket() -> list[str]:
    """Return the active runtime quote basket."""
    if _runtime_pair_universe_mode() == "full":
        return get_pair_quote_basket()
    return get_core_pair_quote_basket()


def get_pair_quote_basket() -> list[str]:
    seen: set[str] = set()
    basket: list[str] = []
    for definition in SYMBOL_CATALOG:
        if definition.display_category not in {"PAIR EQUITIES", "PAIR ETFS"}:
            continue
        if definition.fetch_requirement not in {"quote", "proxy"}:
            continue
        provider_symbol = definition.provider_symbol or definition.symbol
        if provider_symbol not in seen:
            basket.append(provider_symbol)
            seen.add(provider_symbol)
    return basket


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
    "PAIR_EQUITY_SECTORS",
    "DEFAULT_PAIR_DEFINITIONS",
    "get_pair_equity_symbols",
    "get_pair_etf_symbols",
    "get_core_pair_equity_symbols",
    "get_core_pair_universe",
    "get_core_pair_quote_basket",
    "get_runtime_pair_universe_mode",
    "get_runtime_pair_equity_symbols",
    "get_runtime_pair_universe",
    "get_runtime_pair_quote_basket",
    "get_pair_universe",
    "get_pair_quote_basket",
]
