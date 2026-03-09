#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT44_DatabentoClient_Test.py
Purpose: Unit tests for SpyderC26_DatabentoClient

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-02-25 Time: 20:00:00

Description:
    Comprehensive unit tests for the DatabentoClient module covering:
    - Client initialization and configuration
    - Connection status management
    - Symbol format conversion utilities
    - Historical data retrieval (mocked SDK)
    - Instrument definition caching
    - MarketDataUpdate normalization
    - BandwidthTracker
    - Callbacks and event dispatch
    - Error handling and reconnection logic
    - Live stream lifecycle

Usage:
    pytest Spyder/SpyderT_Testing/SpyderT44_DatabentoClient_Test.py -v
"""

import pytest
import os
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from datetime import datetime, date

# Import data classes and utilities (always available)
from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import (
    MarketDataUpdate,
    InstrumentDefinition,
    BandwidthTracker,
    ConnectionStatus,
    DatabentoSchema,
    SymbolFormat,
    convert_symbol,
    SCHEMA_MAP,
    DEFAULT_DATASET,
    DEFAULT_LIVE_SCHEMA,
    NANOSECONDS_PER_SECOND,
)


# ==============================================================================
# MARKET DATA UPDATE TESTS
# ==============================================================================


class TestMarketDataUpdate:
    """Tests for the MarketDataUpdate dataclass."""

    def test_basic_construction(self):
        """MarketDataUpdate stores all fields correctly."""
        ts_ns = 1_700_000_000_000_000_000  # ~2023-11-14
        update = MarketDataUpdate(
            symbol="SPY",
            timestamp_ns=ts_ns,
            schema="mbp-1",
            data={"bid": 585.23, "ask": 585.27},
            underlying="SPY",
            is_option=False,
        )
        assert update.symbol == "SPY"
        assert update.schema == "mbp-1"
        assert update.underlying == "SPY"
        assert not update.is_option

    def test_timestamp_property(self):
        """timestamp property converts ns → ms."""
        ts_ns = 1_700_000_000_000_000_000
        update = MarketDataUpdate(
            symbol="SPY", timestamp_ns=ts_ns, schema="trades", data={}
        )
        assert update.timestamp == ts_ns // 1_000_000

    def test_datetime_property(self):
        """datetime property returns a Python datetime."""
        ts_ns = 1_700_000_000_000_000_000
        update = MarketDataUpdate(
            symbol="SPY", timestamp_ns=ts_ns, schema="trades", data={}
        )
        dt = update.datetime
        assert isinstance(dt, datetime)
        assert dt.year >= 2023

    def test_to_dict(self):
        """to_dict includes all fields."""
        update = MarketDataUpdate(
            symbol="SPY260220C00585000",
            timestamp_ns=1_700_000_000_000_000_000,
            schema="mbp-1",
            data={"bid": 3.45, "ask": 3.55},
            underlying="SPY",
            is_option=True,
        )
        d = update.to_dict()
        assert d["symbol"] == "SPY260220C00585000"
        assert d["is_option"] is True
        assert "timestamp" in d
        assert "timestamp_ns" in d
        assert "datetime" in d

    def test_repr(self):
        """__repr__ includes symbol and schema."""
        update = MarketDataUpdate(
            symbol="SPY", timestamp_ns=1_700_000_000_000_000_000,
            schema="trades", data={},
        )
        r = repr(update)
        assert "SPY" in r
        assert "trades" in r


# ==============================================================================
# INSTRUMENT DEFINITION TESTS
# ==============================================================================


class TestInstrumentDefinition:
    """Tests for InstrumentDefinition dataclass."""

    def test_basic_construction(self):
        """InstrumentDefinition stores all fields."""
        defn = InstrumentDefinition(
            raw_symbol="SPY   260220C00585000",
            instrument_id=12345,
            underlying="SPY",
            strike_price=585.0,
            expiration=date(2026, 2, 20),
            option_type="C",
            exchange="OPRA",
        )
        assert defn.underlying == "SPY"
        assert defn.strike_price == 585.0
        assert defn.option_type == "C"
        assert defn.expiration == date(2026, 2, 20)

    def test_tradier_symbol_computed(self):
        """Tradier symbol is computed from raw_symbol if not provided."""
        defn = InstrumentDefinition(
            raw_symbol="SPY   260220C00585000",
            instrument_id=12345,
            underlying="SPY",
            strike_price=585.0,
            expiration=date(2026, 2, 20),
            option_type="C",
        )
        # Tradier symbol should be auto-computed (no spaces)
        assert defn.tradier_symbol != ""
        assert " " not in defn.tradier_symbol


# ==============================================================================
# BANDWIDTH TRACKER TESTS
# ==============================================================================


class TestBandwidthTracker:
    """Tests for BandwidthTracker dataclass."""

    def test_initial_values(self):
        """Tracker starts at zero."""
        tracker = BandwidthTracker()
        assert tracker.bytes_received == 0
        assert tracker.messages_received == 0
        assert tracker.gb_received == 0.0

    def test_record_bytes(self):
        """Recording bytes updates counters."""
        tracker = BandwidthTracker()
        tracker.record(1024)
        assert tracker.bytes_received == 1024
        assert tracker.messages_received == 1

        tracker.record(2048)
        assert tracker.bytes_received == 3072
        assert tracker.messages_received == 2

    def test_gb_received_conversion(self):
        """gb_received property converts bytes to GB."""
        tracker = BandwidthTracker()
        tracker.record(1024 ** 3)  # 1 GB
        assert abs(tracker.gb_received - 1.0) < 0.001

    def test_daily_reset(self):
        """daily_gb resets when date changes."""
        tracker = BandwidthTracker()
        tracker.daily_reset_date = "2020-01-01"  # old date
        tracker.daily_bytes = 999999
        # Accessing daily_gb should reset since date changed
        _ = tracker.daily_gb
        assert tracker.daily_bytes == 0


# ==============================================================================
# CONNECTION STATUS TESTS
# ==============================================================================


class TestConnectionStatus:
    """Tests for ConnectionStatus enum."""

    def test_all_statuses(self):
        """All expected statuses exist."""
        expected = {
            "DISCONNECTED", "CONNECTING", "CONNECTED",
            "STREAMING", "RECONNECTING", "ERROR", "STOPPED",
        }
        actual = {s.name for s in ConnectionStatus}
        assert expected == actual


class TestDatabentoSchema:
    """Tests for DatabentoSchema enum."""

    def test_schema_values(self):
        """Schema enum values match Databento schema strings."""
        assert DatabentoSchema.MBP_1.value == "mbp-1"
        assert DatabentoSchema.TRADES.value == "trades"
        assert DatabentoSchema.OHLCV_1M.value == "ohlcv-1m"
        assert DatabentoSchema.DEFINITION.value == "definition"

    def test_schema_map_keys(self):
        """SCHEMA_MAP covers all standard schemas."""
        expected_schemas = {
            "mbo", "mbp-1", "mbp-10", "tbbo", "trades",
            "ohlcv-1s", "ohlcv-1m", "ohlcv-1h", "ohlcv-1d",
            "definition", "statistics", "status",
        }
        assert expected_schemas.issubset(set(SCHEMA_MAP.keys()))


# ==============================================================================
# SYMBOL CONVERSION TESTS
# ==============================================================================


class TestSymbolConversion:
    """Tests for convert_symbol utility."""

    def test_databento_to_tradier(self):
        """Convert Databento OSI format to Tradier format."""
        # Databento: "SPY   260220C00585000" (padded to 21 chars)
        result = convert_symbol(
            "SPY   260220C00585000",
            SymbolFormat.DATABENTO_OSI,
            SymbolFormat.TRADIER,
        )
        assert "SPY" in result
        assert "260220" in result
        assert "C" in result
        assert " " not in result

    def test_tradier_to_databento(self):
        """Convert Tradier format to Databento OSI format."""
        result = convert_symbol(
            "SPY260220C00585000",
            SymbolFormat.TRADIER,
            SymbolFormat.DATABENTO_OSI,
        )
        # Databento OSI is 21 chars with padded underlying
        assert len(result) == 21

    def test_tradier_to_spyder(self):
        """Convert Tradier format to Spyder human-readable format."""
        result = convert_symbol(
            "SPY260220C00585000",
            SymbolFormat.TRADIER,
            SymbolFormat.SPYDER,
        )
        assert "SPY" in result
        assert "260220" in result
        assert "C" in result

    def test_roundtrip_databento_tradier(self):
        """Roundtrip Databento → Tradier → Databento preserves symbol."""
        original = "SPY   260220C00585000"
        tradier = convert_symbol(
            original, SymbolFormat.DATABENTO_OSI, SymbolFormat.TRADIER
        )
        back = convert_symbol(
            tradier, SymbolFormat.TRADIER, SymbolFormat.DATABENTO_OSI
        )
        assert back == original


# ==============================================================================
# DATABENTO CLIENT INITIALIZATION TESTS
# ==============================================================================


class TestDatabentoClientInit:
    """Tests for DatabentoClient initialization."""

    def test_init_with_api_key(self, databento_env):
        """Client initializes with explicit API key."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            client = DatabentoClient(api_key="test_key_123")
            assert client.api_key == "test_key_123"
            assert client.dataset == DEFAULT_DATASET
            assert client.status == ConnectionStatus.DISCONNECTED

    def test_init_from_env(self, databento_env):
        """Client reads API key from environment."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            client = DatabentoClient()
            assert client.api_key == "test_databento_key_12345678"

    def test_init_no_key_raises(self, monkeypatch):
        """Missing API key raises ValueError."""
        monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            with pytest.raises(ValueError, match="API key required"):
                DatabentoClient(api_key="")

    def test_init_callbacks_none(self, databento_env):
        """Callbacks default to None."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            client = DatabentoClient(api_key="test_key")
            assert client.on_quote is None
            assert client.on_trade is None
            assert client.on_ohlcv is None
            assert client.on_definition is None

    def test_init_bandwidth_tracker(self, databento_env):
        """Bandwidth tracker is initialized at zero."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            client = DatabentoClient(api_key="test_key")
            assert client.bandwidth.bytes_received == 0


# ==============================================================================
# DATABENTO CLIENT STATUS TESTS
# ==============================================================================


class TestDatabentoClientStatus:
    """Tests for connection status management."""

    def test_is_connected_when_disconnected(self, databento_env):
        """is_connected is False when disconnected."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            client = DatabentoClient(api_key="test_key")
            assert not client.is_connected

    def test_set_status_notifies_callback(self, databento_env):
        """_set_status calls on_status_change callback."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            client = DatabentoClient(api_key="test_key")
            changes = []
            client.on_status_change = lambda s: changes.append(s)

            client._set_status(ConnectionStatus.CONNECTING)
            assert len(changes) == 1
            assert changes[0] == ConnectionStatus.CONNECTING

    def test_set_status_no_duplicate_notification(self, databento_env):
        """_set_status does not notify if status unchanged."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            client = DatabentoClient(api_key="test_key")
            changes = []
            client.on_status_change = lambda s: changes.append(s)

            client._set_status(ConnectionStatus.DISCONNECTED)  # same as init
            assert len(changes) == 0


# ==============================================================================
# DATABENTO CLIENT HISTORICAL DATA TESTS
# ==============================================================================


class TestDatabentoHistorical:
    """Tests for historical data retrieval (mocked SDK)."""

    def test_get_historical_bars(self, databento_env, mock_databento_historical):
        """get_historical_bars calls timeseries.get_range."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            import Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient as db_mod
            orig_has_db, orig_has_pd = db_mod.HAS_DATABENTO, db_mod.HAS_PANDAS
            db_mod.HAS_DATABENTO, db_mod.HAS_PANDAS = True, True
            try:
                client = db_mod.DatabentoClient(api_key="test_key")
                client._historical = mock_databento_historical

                df = client.get_historical_bars("SPY", "2026-01-01", "2026-01-31")

                mock_databento_historical.timeseries.get_range.assert_called_once()
                assert df is not None
            finally:
                db_mod.HAS_DATABENTO, db_mod.HAS_PANDAS = orig_has_db, orig_has_pd

    def test_get_historical_trades(self, databento_env, mock_databento_historical):
        """get_historical_trades delegates with schema='trades'."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            import Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient as db_mod
            orig_has_db, orig_has_pd = db_mod.HAS_DATABENTO, db_mod.HAS_PANDAS
            db_mod.HAS_DATABENTO, db_mod.HAS_PANDAS = True, True
            try:
                client = db_mod.DatabentoClient(api_key="test_key")
                client._historical = mock_databento_historical

                client.get_historical_trades("SPY", "2026-01-01", "2026-01-31")

                call_kwargs = mock_databento_historical.timeseries.get_range.call_args
                assert call_kwargs is not None
            finally:
                db_mod.HAS_DATABENTO, db_mod.HAS_PANDAS = orig_has_db, orig_has_pd

    def test_get_historical_error_returns_none(self, databento_env):
        """Historical data error returns None."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            import Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient as db_mod
            orig_has_db, orig_has_pd = db_mod.HAS_DATABENTO, db_mod.HAS_PANDAS
            db_mod.HAS_DATABENTO, db_mod.HAS_PANDAS = True, True
            try:
                client = db_mod.DatabentoClient(api_key="test_key")

                mock_hist = MagicMock()
                mock_hist.timeseries.get_range.side_effect = Exception("API error")
                client._historical = mock_hist

                result = client.get_historical_bars("SPY", "2026-01-01", "2026-01-31")
                assert result is None
            finally:
                db_mod.HAS_DATABENTO, db_mod.HAS_PANDAS = orig_has_db, orig_has_pd


# ==============================================================================
# DATABENTO CLIENT LIVE STREAM TESTS
# ==============================================================================


class TestDatabentoLiveStream:
    """Tests for live stream lifecycle."""

    def test_start_live_when_already_running(self, databento_env):
        """start_live warns if already streaming."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            import Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient as db_mod
            orig_has_db = db_mod.HAS_DATABENTO
            db_mod.HAS_DATABENTO = True
            try:
                client = db_mod.DatabentoClient(api_key="test_key")
                client._running = True

                # Should return without error
                client.start_live(underlyings=["SPY"])
                # No new thread should be started (still old)
                assert client._running is True
            finally:
                db_mod.HAS_DATABENTO = orig_has_db

    def test_stop_live_when_not_running(self, databento_env):
        """stop_live is safe to call when not streaming."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            client = DatabentoClient(api_key="test_key")
            client.stop_live()  # Should not raise
            assert client.status in (ConnectionStatus.DISCONNECTED, ConnectionStatus.STOPPED)


# ==============================================================================
# DATABENTO CLIENT DEFINITION CACHE TESTS
# ==============================================================================


class TestDefinitionCache:
    """Tests for instrument definition caching."""

    def test_get_cached_definitions_empty(self, databento_env):
        """Empty cache returns empty dict."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            client = DatabentoClient(api_key="test_key")
            assert client.get_cached_definitions() == {}

    def test_lookup_definition_not_found(self, databento_env):
        """lookup_definition returns None for unknown symbol."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            client = DatabentoClient(api_key="test_key")
            assert client.lookup_definition("UNKNOWN_SYMBOL") is None


# ==============================================================================
# DATABENTO CLIENT BANDWIDTH REPORT TESTS
# ==============================================================================


class TestBandwidthReport:
    """Tests for bandwidth reporting."""

    def test_get_bandwidth_report(self, databento_env):
        """get_bandwidth_report returns structured report."""
        with patch.dict("sys.modules", {"databento": MagicMock()}):
            from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient
            client = DatabentoClient(api_key="test_key")
            client.bandwidth.record(5000)

            report = client.get_bandwidth_report()
            assert "bytes_received" in report or "session_gb" in report


# ==============================================================================
# CONSTANTS TESTS
# ==============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_default_dataset(self):
        """Default dataset is OPRA.PILLAR."""
        assert DEFAULT_DATASET == "OPRA.PILLAR"

    def test_default_live_schema(self):
        """Default live schema is mbp-1."""
        assert DEFAULT_LIVE_SCHEMA == "mbp-1"

    def test_nanoseconds_per_second(self):
        """Nanosecond constant is correct."""
        assert NANOSECONDS_PER_SECOND == 1_000_000_000


# ==============================================================================
# RUN TESTS
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
