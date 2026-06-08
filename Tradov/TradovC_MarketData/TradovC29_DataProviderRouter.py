#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovC_MarketData
Module: TradovC29_DataProviderRouter.py
Purpose: Data provider selection and routing based on ACTIVE_DATA_PROVIDER

Reads the ACTIVE_DATA_PROVIDER (or DATA_PROVIDER) environment variable and
returns the appropriate market data client.  Currently supports:
    tradier  — TradovB40_TradierClient  (default; primary live market data)

Any code that needs a market data provider should call get_data_provider()
rather than importing a provider directly.  This decouples strategy/risk code
from the underlying data source.

Author: Tradov Dev
Year Created: 2026
Last Updated: 2026-04-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import logging
from enum import StrEnum
from typing import Any

# ==============================================================================
# LOGGER
# ==============================================================================
logger = logging.getLogger(__name__)


def _allow_sandbox_market_data() -> bool:
    """Return True when an env-var token represents an enabled/true value."""
    raw = str(os.environ.get("TRADOV_ALLOW_SANDBOX_MARKET_DATA", "false")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


# ==============================================================================
# PROVIDER ENUM
# ==============================================================================


class DataProvider(StrEnum):
    """Supported market data providers.  Tradier is the sole provider."""

    TRADIER = "tradier"

    @classmethod
    def from_env(cls) -> "DataProvider":
        """
        Read the active provider from environment variables.

        Tradier is the only supported provider.  Any value other than
        ``"tradier"`` is logged as a warning and ignored.

        Returns:
            DataProvider: Always :attr:`TRADIER`.
        """
        raw = (
            os.environ.get("ACTIVE_DATA_PROVIDER")
            or os.environ.get("DATA_PROVIDER")
            or "tradier"
        ).lower().strip()

        if raw not in {"tradier", ""}:
            logger.warning(
                "DATA_PROVIDER='%s' is not supported; Tradier is the only provider.", raw
            )
        return cls.TRADIER


# ==============================================================================
# ROUTER
# ==============================================================================


class DataProviderRouter:
    """
    Runtime data provider router.

    Instantiates and caches the active market data client.  The provider is
    selected once at construction time from the environment; call
    :meth:`reload` to force a re-evaluation (e.g. after changing env vars in
    tests).

    Args:
        api_key: Override the provider API key.  If omitted the appropriate
                 environment variable is read automatically.
        **kwargs: Additional keyword arguments forwarded to the provider
                  constructor.

    Example::

        router = DataProviderRouter()
        client = router.get_client()
        # client is a TradierClient
    """

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        self._api_key = api_key
        self._kwargs = kwargs
        self._provider: DataProvider = DataProvider.from_env()
        self._client: Any | None = None
        logger.debug("DataProviderRouter: provider='%s'", self._provider.value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def provider(self) -> DataProvider:
        """The currently active :class:`DataProvider`."""
        return self._provider

    def get_client(self) -> Any:
        """
        Return the cached market data client, constructing it on first call.

        Returns:
            The provider client instance (e.g., :class:`TradierClient`).
        """
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def reload(self) -> None:
        """
        Re-read the provider from the environment and discard any cached client.

        Useful in tests where the environment is modified between calls.
        """
        self._provider = DataProvider.from_env()
        self._client = None
        logger.info(
            "DataProviderRouter: reloaded, provider='%s'", self._provider.value
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_client(self) -> Any:
        """Construct and return the Tradier client instance."""
        client = self._build_tradier_client()
        logger.debug(
            "DataProviderRouter: built %s client",
            type(client).__name__,
        )
        return client

    def _build_tradier_client(self) -> Any:
        """Construct a TradierClient configured for the active market-data environment."""
        from TradovB_Broker.TradovB40_TradierClient import (  # type: ignore[import]
            TradierClient,
            TradingEnvironment,
        )

        # Market-data routing is live-only by policy.
        market_data_env = (
            os.environ.get("TRADIER_MARKET_DATA_ENVIRONMENT")
            or os.environ.get("TRADIER_ENVIRONMENT")
            or "live"
        ).strip().lower()

        if _allow_sandbox_market_data():
            raise ValueError(
                "TRADOV_ALLOW_SANDBOX_MARKET_DATA=true is not permitted "
                "(live-only market-data policy)."
            )

        if market_data_env not in {"live", "production"}:
            raise ValueError(
                "Live-only market-data policy violation: "
                f"TRADIER_MARKET_DATA_ENVIRONMENT={market_data_env or '<empty>'}. "
                "Use 'live' (or 'production')."
            )

        environment = TradingEnvironment.LIVE
        api_key = (
            self._api_key
            or os.environ.get("TRADIER_LIVE_API_KEY")
            or os.environ.get("TRADIER_API_KEY", "")
        )
        account_id = (
            os.environ.get("TRADIER_LIVE_ACCOUNT_ID")
            or os.environ.get("TRADIER_ACCOUNT_ID", "")
        )

        if not api_key:
            key_hint = "TRADIER_LIVE_API_KEY (or TRADIER_API_KEY)"
            raise ValueError(
                f"Tradier API key not set. Add {key_hint} to your .env file."
            )
        if not account_id:
            account_hint = "TRADIER_LIVE_ACCOUNT_ID (or TRADIER_ACCOUNT_ID)"
            raise ValueError(
                f"Tradier account ID not set. Add {account_hint} to your .env file."
            )

        logger.debug(
            "DataProviderRouter: connecting to Tradier %s environment",
            environment.value,
        )
        return TradierClient(
            api_key=api_key,
            account_id=account_id,
            environment=environment,
            **self._kwargs,
        )


# ==============================================================================
# MODULE-LEVEL FACTORY
# ==============================================================================

# Singleton router — shared across the process unless tests need isolation.
_default_router: DataProviderRouter | None = None


def get_data_provider(
    api_key: str | None = None,
    force_new: bool = False,
    **kwargs: Any,
) -> Any:
    """
    Return the active market data provider client.

    On the first call a :class:`DataProviderRouter` is created and cached
    as a module-level singleton.  Subsequent calls return the same client
    unless *force_new* is ``True``.

    Args:
        api_key: Optional API key override.  Passed to the provider constructor.
        force_new: When ``True``, discard the cached router and create a fresh
                   instance.  Useful in unit tests.
        **kwargs: Forwarded to the provider constructor.

    Returns:
        The active market data client instance.

    Example::

        from TradovC_MarketData.TradovC29_DataProviderRouter import get_data_provider
        client = get_data_provider()
    """
    global _default_router
    if _default_router is None or force_new:
        _default_router = DataProviderRouter(api_key=api_key, **kwargs)
    return _default_router.get_client()


# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================

__all__ = [
    "DataProvider",
    "DataProviderRouter",
    "get_data_provider",
]
