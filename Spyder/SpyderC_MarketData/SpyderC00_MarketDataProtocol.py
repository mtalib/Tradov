#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC00_MarketDataProtocol.py
Purpose: Provider-agnostic Protocol for options-query market data access

Defines OptionsDataProvider — a structural typing Protocol satisfied by any
object that implements get_quotes(), get_option_chain_with_greeks(), and
get_option_expirations().  TradierClient already satisfies it without
modification.

When Databento is subscribed, write a thin DatabentoMarketDataAdapter that
implements the same three methods, then set MARKET_DATA_PROVIDER=databento in
.env — no changes to F18, D27, D28, or C30 required.

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-03-03 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import logging
from typing import Any

try:
    from typing import Protocol, runtime_checkable
except ImportError:                                     # Python < 3.8 fallback
    from typing_extensions import Protocol, runtime_checkable  # type: ignore[assignment]

# ==============================================================================
# LOGGER
# ==============================================================================
logger = logging.getLogger(__name__)

# ==============================================================================
# PROTOCOL DEFINITION
# ==============================================================================


@runtime_checkable
class OptionsDataProvider(Protocol):
    """
    Structural typing Protocol for REST-style options query providers.

    Any object implementing all three methods satisfies this Protocol without
    needing to inherit from it.  TradierClient (SpyderB40) already satisfies it.

    Future: DatabentoMarketDataAdapter will satisfy it when Databento is active.

    Methods:
        get_quotes: Retrieve current market quotes for one or more symbols.
        get_option_chain_with_greeks: Retrieve full options chain with Greeks.
        get_option_expirations: Retrieve available expiration dates for a symbol.
    """

    def get_quotes(self, symbols: list[str]) -> dict[str, Any]:
        """Return current quote data for one or more symbols."""
        ...

    def get_option_chain_with_greeks(
        self,
        symbol: str,
        expiration: str,
        option_type: str | None = None,
    ) -> list:
        """Return options chain (calls and/or puts) with Greeks for a given expiry."""
        ...

    def get_option_expirations(self, symbol: str) -> dict[str, Any]:
        """Return available option expiration dates for a symbol."""
        ...


# ==============================================================================
# FACTORY
# ==============================================================================


def create_options_data_provider() -> Any:
    """
    Factory that returns an OptionsDataProvider based on MARKET_DATA_PROVIDER.

    Environment Variables:
        MARKET_DATA_PROVIDER: "tradier" (default) or "databento"

    Returns:
        TradierClient when MARKET_DATA_PROVIDER=tradier (or unset).

    Raises:
        NotImplementedError: When MARKET_DATA_PROVIDER=databento (coming soon).
        RuntimeError: If the selected provider cannot be instantiated.
    """
    provider_name = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower().strip()

    if provider_name == "databento":
        # TODO: return DatabentoMarketDataAdapter() once the Databento
        # subscription is active and the adapter class is implemented.
        raise NotImplementedError(
            "Databento adapter not yet implemented. "
            "Set MARKET_DATA_PROVIDER=tradier or implement "
            "SpyderC00_MarketDataProtocol.DatabentoMarketDataAdapter."
        )

    # Default: Tradier
    try:
        from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
            create_tradier_client_from_env,
        )
        return create_tradier_client_from_env()
    except Exception as exc:
        raise RuntimeError(
            f"Could not create TradierClient as OptionsDataProvider: {exc}"
        ) from exc


# ==============================================================================
# EXPORTS
# ==============================================================================
__all__ = [
    "OptionsDataProvider",
    "create_options_data_provider",
]
