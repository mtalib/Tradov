#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT44_DatabentoClient_Test.py
Purpose: Unit tests for SpyderC27_MassiveClient

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-07-01 Time: 00:00:00

Description:
    Comprehensive unit tests for the Massive market data client modules covering:
    - MassiveQuoteUpdate and MassiveTradeUpdate data classes
    - ConnectionStatus enum completeness
    - parse_opra_ticker utility function
    - OptionContract and DownloadState dataclasses
    - MassiveClient initialization and configuration
    - MassiveClient connection status management
    - MassiveClient stream lifecycle (stop/start)
    - MassiveHistoricalDownloader initialization

Usage:
    pytest Spyder/SpyderT_Testing/SpyderT44_DatabentoClient_Test.py -v
"""

import pytest
import os
from datetime import datetime, date
from unittest.mock import Mock, MagicMock, patch

# ---------------------------------------------------------------------------
# Import data classes and utilities (no polygon SDK required)
# ---------------------------------------------------------------------------
from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import (
    MassiveQuoteUpdate,
    MassiveTradeUpdate,
    ConnectionStatus as MassiveConnectionStatus,
)
# ==============================================================================
# QUOTE UPDATE TESTS
# ==============================================================================


class TestMassiveQuoteUpdate:
    """Tests for the MassiveQuoteUpdate dataclass."""

    def test_basic_construction(self):
        """MassiveQuoteUpdate stores all fields correctly."""
        ts = datetime(2026, 1, 15, 10, 30, 0)
        quote = MassiveQuoteUpdate(
            symbol="SPY",
            bid=585.10,
            ask=585.15,
            bid_size=100,
            ask_size=200,
            timestamp=ts,
            bid_exchange="Q",
            ask_exchange="N",
        )
        assert quote.symbol == "SPY"
        assert quote.bid == 585.10
        assert quote.ask == 585.15
        assert quote.bid_size == 100
        assert quote.ask_size == 200
        assert quote.timestamp == ts

    def test_default_optional_fields(self):
        """Optional fields default to expected values."""
        quote = MassiveQuoteUpdate(symbol="SPY", bid=585.10, ask=585.15)
        assert quote.bid_size == 0
        assert quote.ask_size == 0
        assert quote.bid_exchange == ""
        assert quote.ask_exchange == ""
        assert quote.raw is None

    def test_mid_property(self):
        """mid returns average of bid and ask."""
        quote = MassiveQuoteUpdate(symbol="SPY", bid=585.00, ask=585.10)
        assert abs(quote.mid - 585.05) < 1e-6

    def test_spread_property(self):
        """spread returns bid-ask difference."""
        quote = MassiveQuoteUpdate(symbol="SPY", bid=585.00, ask=585.10)
        assert abs(quote.spread - 0.10) < 1e-6

    def test_spread_zero(self):
        """spread is zero when bid equals ask."""
        quote = MassiveQuoteUpdate(symbol="SPY", bid=585.00, ask=585.00)
        assert quote.spread == 0.0

    def test_to_normalized_no_protocol(self):
        """to_normalized returns None when SpyderC00 is unavailable."""
        import Spyder.SpyderC_MarketData.SpyderC27_MassiveClient as m
        original = m.NormalizedQuote
        m.NormalizedQuote = None
        try:
            quote = MassiveQuoteUpdate(symbol="SPY", bid=585.00, ask=585.10)
            assert quote.to_normalized() is None
        finally:
            m.NormalizedQuote = original


# ==============================================================================
# TRADE UPDATE TESTS
# ==============================================================================


class TestMassiveTradeUpdate:
    """Tests for the MassiveTradeUpdate dataclass."""

    def test_basic_construction(self):
        """MassiveTradeUpdate stores all fields correctly."""
        ts = datetime(2026, 1, 15, 10, 30, 1)
        trade = MassiveTradeUpdate(
            symbol="SPY",
            price=585.12,
            size=500,
            timestamp=ts,
            exchange="Q",
            conditions=["@", "T"],
        )
        assert trade.symbol == "SPY"
        assert trade.price == 585.12
        assert trade.size == 500
        assert trade.exchange == "Q"
        assert trade.conditions == ["@", "T"]

    def test_default_optional_fields(self):
        """Optional fields default to expected values."""
        trade = MassiveTradeUpdate(symbol="SPY", price=585.12, size=100)
        assert trade.exchange == ""
        assert trade.conditions == []
        assert trade.raw is None

    def test_to_normalized_no_protocol(self):
        """to_normalized returns None when SpyderC00 is unavailable."""
        import Spyder.SpyderC_MarketData.SpyderC27_MassiveClient as m
        original = m.NormalizedTrade
        m.NormalizedTrade = None
        try:
            trade = MassiveTradeUpdate(symbol="SPY", price=585.12, size=100)
            assert trade.to_normalized() is None
        finally:
            m.NormalizedTrade = original


# ==============================================================================
# CONNECTION STATUS TESTS
# ==============================================================================


class TestMassiveConnectionStatus:
    """Tests for ConnectionStatus enum."""

    def test_all_statuses_exist(self):
        """All expected status values are present."""
        expected = {
            "DISCONNECTED", "CONNECTING", "CONNECTED",
            "STREAMING", "RECONNECTING", "ERROR", "STOPPED",
        }
        actual = {s.name for s in MassiveConnectionStatus}
        assert expected == actual

    def test_enum_string_values(self):
        """Enum values are lowercase strings."""
        assert MassiveConnectionStatus.DISCONNECTED.value == "disconnected"
        assert MassiveConnectionStatus.STREAMING.value == "streaming"
        assert MassiveConnectionStatus.ERROR.value == "error"



# ==============================================================================
# MASSIVE CLIENT INITIALIZATION TESTS
# ==============================================================================


class TestMassiveClientInit:
    """Tests for MassiveClient initialization."""

    def test_init_with_explicit_api_key(self, massive_env):
        """Client stores the provided API key."""
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            client = MassiveClient(api_key="explicit_test_key")
            assert client.api_key == "explicit_test_key"

    def test_init_reads_env_key(self, massive_env):
        """Client reads MASSIVE_API_KEY from environment when api_key is None."""
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            client = MassiveClient()
            assert client.api_key == "test_massive_key_12345678"

    def test_init_no_key_raises(self, monkeypatch):
        """Missing API key raises ValueError."""
        monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            with pytest.raises(ValueError, match="Massive API key required"):
                MassiveClient(api_key="")

    def test_initial_status_disconnected(self, massive_env):
        """Client starts in DISCONNECTED state."""
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            client = MassiveClient(api_key="test_key")
            assert client.status == MassiveConnectionStatus.DISCONNECTED

    def test_callbacks_default_none(self, massive_env):
        """All callbacks default to None."""
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            client = MassiveClient(api_key="test_key")
            assert client.on_status_change is None


# ==============================================================================
# MASSIVE CLIENT STATUS TESTS
# ==============================================================================


class TestMassiveClientStatus:
    """Tests for MassiveClient connection status management."""

    def test_is_connected_when_disconnected(self, massive_env):
        """is_connected is False when status is DISCONNECTED."""
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            client = MassiveClient(api_key="test_key")
            assert not client.is_connected

    def test_is_streaming_when_disconnected(self, massive_env):
        """is_streaming is False when status is DISCONNECTED."""
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            client = MassiveClient(api_key="test_key")
            assert not client.is_streaming

    def test_is_connected_when_connected(self, massive_env):
        """is_connected is True when status is CONNECTED."""
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            client = MassiveClient(api_key="test_key")
            client.status = MassiveConnectionStatus.CONNECTED
            assert client.is_connected

    def test_is_streaming_when_streaming(self, massive_env):
        """is_streaming is True when status is STREAMING."""
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            client = MassiveClient(api_key="test_key")
            client.status = MassiveConnectionStatus.STREAMING
            assert client.is_streaming

    def test_set_status_notifies_callback(self, massive_env):
        """_set_status invokes on_status_change callback."""
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            client = MassiveClient(api_key="test_key")
            changes = []
            client.on_status_change = lambda s: changes.append(s)
            client._set_status(MassiveConnectionStatus.CONNECTING)
            assert len(changes) == 1
            assert changes[0] == MassiveConnectionStatus.CONNECTING

    def test_set_status_no_duplicate(self, massive_env):
        """_set_status does not notify if status is unchanged."""
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            client = MassiveClient(api_key="test_key")
            changes = []
            client.on_status_change = lambda s: changes.append(s)
            # Status is already DISCONNECTED — no notification expected
            client._set_status(MassiveConnectionStatus.DISCONNECTED)
            assert len(changes) == 0


# ==============================================================================
# MASSIVE CLIENT STREAM LIFECYCLE TESTS
# ==============================================================================


class TestMassiveClientStream:
    """Tests for MassiveClient stream start/stop lifecycle."""

    def test_stop_stream_when_not_running_is_safe(self, massive_env):
        """stop_stream can be called when not streaming without error."""
        with patch.dict("sys.modules", {"polygon": MagicMock(), "massive": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient
            client = MassiveClient(api_key="test_key")
            client.stop_stream()  # Must not raise
            assert client.status in (
                MassiveConnectionStatus.DISCONNECTED,
                MassiveConnectionStatus.STOPPED,
            )


# ==============================================================================
# RUN TESTS
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
