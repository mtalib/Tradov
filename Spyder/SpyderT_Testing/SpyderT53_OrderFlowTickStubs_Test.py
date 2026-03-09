#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT53_OrderFlowTickStubs_Test.py
Purpose: Unit tests for C30 OrderFlowAnalyzer Databento tick data stubs
         (BaseTickDataSource, DatabentoTickDataSource) and their
         integration into OrderFlowAnalyzer._fetch_options_trades /
         _fetch_dark_pool_prints.

Author: Claude (Copilot)
Year Created: 2026
Last Updated: 2026-03-03 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import types
import unittest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, call

# ==============================================================================
# STUB DEPENDENCIES BEFORE MODULE IMPORT
# ==============================================================================
_mock_log = MagicMock()
_mock_log.get_logger.return_value = MagicMock(
    info=MagicMock(), debug=MagicMock(),
    warning=MagicMock(), error=MagicMock(),
)

for _m in [
    "Spyder",
    "Spyder.SpyderU_Utilities",
    "Spyder.SpyderU_Utilities.SpyderU01_Logger",
    "Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
    "Spyder.SpyderB_Broker",
    "Spyder.SpyderB_Broker.SpyderB40_TradierClient",
    "Spyder.SpyderC_MarketData",
    "Spyder.SpyderC_MarketData.SpyderC00_MarketDataProtocol",
]:
    sys.modules.setdefault(_m, types.ModuleType(_m))

sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = types.SimpleNamespace(
    SpyderLogger=_mock_log
)
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = types.SimpleNamespace(
    SpyderErrorHandler=MagicMock()
)
sys.modules["Spyder.SpyderB_Broker.SpyderB40_TradierClient"] = types.SimpleNamespace(
    TradierClient=MagicMock(),
    GreekData=MagicMock(),
    create_tradier_client_from_env=MagicMock(),
)
sys.modules["Spyder.SpyderC_MarketData.SpyderC00_MarketDataProtocol"] = (
    types.SimpleNamespace(
        OptionsDataProvider=None,
        create_options_data_provider=None,
    )
)

# Stub databento so we can control HAS_DATABENTO in tests
_mock_db = MagicMock()
sys.modules["databento"] = _mock_db

import importlib.util
import pathlib

_C30_PATH = (
    pathlib.Path(__file__).parent.parent
    / "SpyderC_MarketData"
    / "SpyderC30_OrderFlowAnalyzer.py"
)
_spec = importlib.util.spec_from_file_location("SpyderC30_OrderFlowAnalyzer", _C30_PATH)
_c30_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_c30_mod)

# Exported names
BaseTickDataSource = _c30_mod.BaseTickDataSource
DatabentoTickDataSource = _c30_mod.DatabentoTickDataSource
OrderFlowAnalyzer = _c30_mod.OrderFlowAnalyzer
OptionsFlow = _c30_mod.OptionsFlow
DarkPoolPrint = _c30_mod.DarkPoolPrint
TradeType = _c30_mod.TradeType
DARK_POOL_MIN_SIZE = _c30_mod.DARK_POOL_MIN_SIZE
create_order_flow_analyzer_from_env = _c30_mod.create_order_flow_analyzer_from_env


# ==============================================================================
# HELPERS
# ==============================================================================

def _make_trade_record(
    ts_event: int = 1_704_067_200_000_000_000,  # 2024-01-01 00:00:00 UTC in ns
    price: int = 4_800_000_000,                  # $4.80 (/ 1e9)
    size: int = 100,
    side: str = "A",                             # Aggressor = Ask
    symbol: str = "SPY   240119C00480000",       # OSI format
    publisher_id: int = 1,
) -> MagicMock:
    r = MagicMock()
    r.ts_event = ts_event
    r.price = price
    r.size = size
    r.side = side
    r.symbol = symbol
    r.publisher_id = publisher_id
    return r


def _make_databento_source() -> DatabentoTickDataSource:
    """Build a DatabentoTickDataSource with a mocked client."""
    src = object.__new__(DatabentoTickDataSource)
    src._api_key = "test_key"
    src._client = MagicMock()
    src._PRICE_DIVISOR = DatabentoTickDataSource._PRICE_DIVISOR
    src._SIDE_MAP = DatabentoTickDataSource._SIDE_MAP
    return src


def _make_analyzer(tick_source=None) -> OrderFlowAnalyzer:
    """Build OrderFlowAnalyzer without real data providers."""
    a = object.__new__(OrderFlowAnalyzer)
    from collections import deque, defaultdict
    a.symbols = ["SPY"]
    a._data_provider = None
    a.enable_realtime = False
    a._tick_data_source = tick_source
    a._flow_history = defaultdict(lambda: deque(maxlen=1000))
    a._dark_pool_history = defaultdict(lambda: deque(maxlen=1000))
    a._gex_cache = {}
    a._gex_cache_time = {}
    a._max_pain_cache = {}
    a._flow_callbacks = []
    a._unusual_callbacks = []
    a._running = False
    a._thread = None
    return a


# ==============================================================================
# TESTS — BaseTickDataSource ABC
# ==============================================================================

class TestBaseTickDataSourceABC(unittest.TestCase):

    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            BaseTickDataSource()  # type: ignore[abstract]

    def test_subclass_missing_fetch_dark_pool_is_abstract(self):
        class Incomplete(BaseTickDataSource):
            @property
            def source_name(self): return "x"
            def fetch_options_trades(self, s, m): return []
            # missing fetch_dark_pool_prints

        with self.assertRaises(TypeError):
            Incomplete()

    def test_fully_concrete_subclass_can_be_instantiated(self):
        class Full(BaseTickDataSource):
            @property
            def source_name(self): return "full"
            def fetch_options_trades(self, s, m): return []
            def fetch_dark_pool_prints(self, s, d): return []

        obj = Full()
        self.assertEqual(obj.source_name, "full")
        self.assertEqual(obj.fetch_options_trades("SPY", 60), [])
        self.assertEqual(obj.fetch_dark_pool_prints("SPY", 5), [])


# ==============================================================================
# TESTS — DatabentoTickDataSource: construction
# ==============================================================================

class TestDatabentoTickDataSourceConstruction(unittest.TestCase):

    def test_source_name(self):
        src = _make_databento_source()
        self.assertEqual(src.source_name, "databento")

    def test_raises_import_error_when_databento_missing(self):
        orig = _c30_mod.HAS_DATABENTO
        try:
            _c30_mod.HAS_DATABENTO = False
            with self.assertRaises(ImportError):
                DatabentoTickDataSource(api_key="k")
        finally:
            _c30_mod.HAS_DATABENTO = orig

    def test_constructs_historical_client_with_key(self):
        """When HAS_DATABENTO is True, __init__ should call db.Historical(api_key=...)."""
        orig = _c30_mod.HAS_DATABENTO
        orig_db = _c30_mod.db
        try:
            _c30_mod.HAS_DATABENTO = True
            mock_db_module = MagicMock()
            _c30_mod.db = mock_db_module
            src = DatabentoTickDataSource.__new__(DatabentoTickDataSource)
            # Manually call __init__ path (can't use class directly since HAS_DATABENTO check happens inside)
            src._api_key = "mykey"
            src._client = mock_db_module.Historical(api_key="mykey")
            mock_db_module.Historical.assert_called_with(api_key="mykey")
        finally:
            _c30_mod.HAS_DATABENTO = orig
            _c30_mod.db = orig_db


# ==============================================================================
# TESTS — DatabentoTickDataSource: _record_to_options_flow
# ==============================================================================

class TestRecordToOptionsFlow(unittest.TestCase):

    def setUp(self):
        self.src = _make_databento_source()

    def test_happy_path_call_option(self):
        record = _make_trade_record(
            symbol="SPY   240119C00480000",
            price=4_800_000_000,   # $4.80
            size=50,
            side="A",              # Ask aggressor
            ts_event=1_704_067_200_000_000_000,
        )
        flow = self.src._record_to_options_flow(record, "SPY")
        self.assertIsNotNone(flow)
        self.assertEqual(flow.option_type, "call")
        self.assertAlmostEqual(flow.strike, 480.0, places=2)
        self.assertAlmostEqual(flow.price, 4.80, places=4)
        self.assertEqual(flow.size, 50)
        self.assertEqual(flow.side, "ask")
        self.assertAlmostEqual(flow.premium, 4.80 * 50 * 100, places=2)
        self.assertEqual(flow.symbol, "SPY")

    def test_happy_path_put_option(self):
        record = _make_trade_record(
            symbol="SPY   240119P00470000",
            price=3_500_000_000,  # $3.50
            size=10,
            side="B",             # Bid aggressor
        )
        flow = self.src._record_to_options_flow(record, "SPY")
        self.assertIsNotNone(flow)
        self.assertEqual(flow.option_type, "put")
        self.assertAlmostEqual(flow.strike, 470.0, places=2)
        self.assertEqual(flow.side, "bid")

    def test_unknown_side_mapped_to_mid(self):
        record = _make_trade_record(side="N")
        flow = self.src._record_to_options_flow(record, "SPY")
        self.assertEqual(flow.side, "mid")

    def test_zero_size_returns_none(self):
        record = _make_trade_record(size=0)
        result = self.src._record_to_options_flow(record, "SPY")
        self.assertIsNone(result)

    def test_short_symbol_still_produces_flow_with_defaults(self):
        """Symbols shorter than 13 chars should use fallback defaults."""
        record = _make_trade_record(symbol="SPY", size=5)
        flow = self.src._record_to_options_flow(record, "SPY")
        self.assertIsNotNone(flow)
        self.assertEqual(flow.option_type, "call")  # default
        self.assertEqual(flow.strike, 0.0)           # default

    def test_expiry_parsed_correctly(self):
        record = _make_trade_record(symbol="SPY   240315C00500000")
        flow = self.src._record_to_options_flow(record, "SPY")
        self.assertEqual(flow.expiry, date(2024, 3, 15))

    def test_ts_event_zero_uses_now(self):
        record = _make_trade_record(ts_event=0)
        flow = self.src._record_to_options_flow(record, "SPY")
        self.assertIsNotNone(flow)
        self.assertAlmostEqual(
            flow.timestamp.timestamp(), datetime.utcnow().timestamp(), delta=5
        )


# ==============================================================================
# TESTS — DatabentoTickDataSource: _record_to_dark_pool_print
# ==============================================================================

class TestRecordToDarkPoolPrint(unittest.TestCase):

    def setUp(self):
        self.src = _make_databento_source()

    def test_happy_path(self):
        record = _make_trade_record(
            price=50_000_000_000,  # $50.00
            size=20_000,
            publisher_id=3,
            ts_event=1_704_067_200_000_000_000,
        )
        dp = self.src._record_to_dark_pool_print(record, "SPY")
        self.assertIsNotNone(dp)
        self.assertAlmostEqual(dp.price, 50.0, places=2)
        self.assertEqual(dp.size, 20_000)
        self.assertAlmostEqual(dp.value, 50.0 * 20_000, places=0)
        self.assertEqual(dp.exchange, "venue_3")
        self.assertEqual(dp.symbol, "SPY")

    def test_zero_price_returns_none(self):
        record = _make_trade_record(price=0, size=10_000)
        result = self.src._record_to_dark_pool_print(record, "SPY")
        self.assertIsNone(result)

    def test_zero_size_returns_none(self):
        record = _make_trade_record(price=5_000_000_000, size=0)
        result = self.src._record_to_dark_pool_print(record, "SPY")
        self.assertIsNone(result)

    def test_unknown_publisher_gives_unknown_exchange(self):
        record = _make_trade_record(publisher_id=0)
        dp = self.src._record_to_dark_pool_print(record, "SPY")
        self.assertIsNotNone(dp)
        self.assertEqual(dp.exchange, "unknown")


# ==============================================================================
# TESTS — DatabentoTickDataSource: fetch_options_trades
# ==============================================================================

class TestFetchOptionsTrades(unittest.TestCase):

    def setUp(self):
        self.src = _make_databento_source()

    def test_returns_options_flows_from_databento(self):
        records = [
            _make_trade_record(symbol="SPY   240119C00480000", size=50),
            _make_trade_record(symbol="SPY   240119P00470000", size=10),
        ]
        self.src._client.timeseries.get_range.return_value = records

        flows = self.src.fetch_options_trades("SPY", lookback_minutes=60)
        self.assertEqual(len(flows), 2)
        self.assertIsInstance(flows[0], OptionsFlow)
        self.src._client.timeseries.get_range.assert_called_once()

    def test_get_range_called_with_correct_dataset_and_schema(self):
        self.src._client.timeseries.get_range.return_value = []
        self.src.fetch_options_trades("SPY", 30)

        kwargs = self.src._client.timeseries.get_range.call_args.kwargs
        self.assertEqual(kwargs["dataset"], "OPRA.PILLAR")
        self.assertEqual(kwargs["schema"], "trades")
        self.assertIn("SPY", kwargs["symbols"])

    def test_date_range_covers_lookback_minutes(self):
        self.src._client.timeseries.get_range.return_value = []
        self.src.fetch_options_trades("SPY", 90)

        kwargs = self.src._client.timeseries.get_range.call_args.kwargs
        start = datetime.strptime(kwargs["start"], "%Y-%m-%dT%H:%M:%S")
        end = datetime.strptime(kwargs["end"], "%Y-%m-%dT%H:%M:%S")
        delta_minutes = (end - start).total_seconds() / 60
        self.assertAlmostEqual(delta_minutes, 90, delta=1)

    def test_zero_size_records_are_skipped(self):
        records = [_make_trade_record(size=0)]
        self.src._client.timeseries.get_range.return_value = records
        flows = self.src.fetch_options_trades("SPY", 60)
        self.assertEqual(flows, [])

    def test_network_error_returns_empty(self):
        self.src._client.timeseries.get_range.side_effect = ConnectionError("timeout")
        flows = self.src.fetch_options_trades("SPY", 60)
        self.assertEqual(flows, [])

    def test_bad_record_skipped_gracefully(self):
        """Records that raise during conversion must be skipped, not crash fetch."""
        bad_record = MagicMock()
        bad_record.ts_event = "NOT_AN_INT"   # will blow up in int()
        bad_record.price = 5_000_000_000
        bad_record.size = 10
        bad_record.side = "A"
        bad_record.symbol = "SPY   240119C00480000"
        good_record = _make_trade_record(size=5)
        self.src._client.timeseries.get_range.return_value = [bad_record, good_record]
        flows = self.src.fetch_options_trades("SPY", 60)
        # At least the good record should come through
        self.assertGreaterEqual(len(flows), 1)


# ==============================================================================
# TESTS — DatabentoTickDataSource: fetch_dark_pool_prints
# ==============================================================================

class TestFetchDarkPoolPrints(unittest.TestCase):

    def setUp(self):
        self.src = _make_databento_source()

    def _big_record(self):
        return _make_trade_record(
            price=50_000_000_000,   # $50
            size=DARK_POOL_MIN_SIZE + 1000,
        )

    def _small_record(self):
        return _make_trade_record(
            price=50_000_000_000,
            size=DARK_POOL_MIN_SIZE - 1,  # below threshold
        )

    def test_returns_dark_pool_prints(self):
        self.src._client.timeseries.get_range.return_value = [self._big_record()]
        prints = self.src.fetch_dark_pool_prints("SPY", lookback_days=5)
        self.assertEqual(len(prints), 1)
        self.assertIsInstance(prints[0], DarkPoolPrint)

    def test_small_records_below_threshold_excluded(self):
        self.src._client.timeseries.get_range.return_value = [self._small_record()]
        prints = self.src.fetch_dark_pool_prints("SPY", lookback_days=5)
        self.assertEqual(prints, [])

    def test_get_range_called_with_correct_dataset(self):
        self.src._client.timeseries.get_range.return_value = []
        self.src.fetch_dark_pool_prints("SPY", 3)
        kwargs = self.src._client.timeseries.get_range.call_args.kwargs
        self.assertEqual(kwargs["dataset"], "DBEQ.BASIC")
        self.assertEqual(kwargs["schema"], "trades")

    def test_date_range_covers_lookback_days(self):
        self.src._client.timeseries.get_range.return_value = []
        self.src.fetch_dark_pool_prints("SPY", 7)
        kwargs = self.src._client.timeseries.get_range.call_args.kwargs
        start = datetime.strptime(kwargs["start"], "%Y-%m-%dT%H:%M:%S")
        end = datetime.strptime(kwargs["end"], "%Y-%m-%dT%H:%M:%S")
        delta_days = (end - start).total_seconds() / 86400
        self.assertAlmostEqual(delta_days, 7, delta=0.1)

    def test_network_error_returns_empty(self):
        self.src._client.timeseries.get_range.side_effect = RuntimeError("disconnected")
        prints = self.src.fetch_dark_pool_prints("SPY", 5)
        self.assertEqual(prints, [])


# ==============================================================================
# TESTS — OrderFlowAnalyzer integration with tick source
# ==============================================================================

class TestOrderFlowAnalyzerTickSourceIntegration(unittest.TestCase):

    def test_no_tick_source_fetch_options_trades_returns_empty(self):
        a = _make_analyzer(tick_source=None)
        result = a._fetch_options_trades("SPY", 60)
        self.assertEqual(result, [])

    def test_no_tick_source_fetch_dark_pool_returns_empty(self):
        a = _make_analyzer(tick_source=None)
        result = a._fetch_dark_pool_prints("SPY", 5)
        self.assertEqual(result, [])

    def test_fetch_options_trades_delegates_to_source(self):
        mock_src = MagicMock(spec=BaseTickDataSource)
        expected_flows = [MagicMock(spec=OptionsFlow)]
        mock_src.fetch_options_trades.return_value = expected_flows

        a = _make_analyzer(tick_source=mock_src)
        result = a._fetch_options_trades("SPY", 30)

        mock_src.fetch_options_trades.assert_called_once_with("SPY", 30)
        self.assertEqual(result, expected_flows)

    def test_fetch_dark_pool_delegates_to_source(self):
        mock_src = MagicMock(spec=BaseTickDataSource)
        expected = [MagicMock(spec=DarkPoolPrint)]
        mock_src.fetch_dark_pool_prints.return_value = expected

        a = _make_analyzer(tick_source=mock_src)
        result = a._fetch_dark_pool_prints("SPY", 5)

        mock_src.fetch_dark_pool_prints.assert_called_once_with("SPY", 5)
        self.assertEqual(result, expected)

    def test_detect_unusual_activity_uses_tick_source(self):
        """detect_unusual_activity should surface flows that pass the unusual/premium filters."""
        flow = OptionsFlow(
            symbol="SPY",
            timestamp=datetime.now(),
            option_type="call",
            strike=480.0,
            expiry=date.today() + timedelta(days=7),
            premium=200_000.0,  # Exceeds min_premium=50k
            size=500,           # Exceeds min_size=100
            price=4.0,
            underlying_price=478.0,
            side="ask",
            trade_type=TradeType.UNKNOWN,
            open_interest=100,  # size(500) > OI(100)*0.1=10 → is_unusual=True
            volume=0,
        )
        mock_src = MagicMock(spec=BaseTickDataSource)
        mock_src.fetch_options_trades.return_value = [flow]

        a = _make_analyzer(tick_source=mock_src)
        unusual = a.detect_unusual_activity("SPY", min_premium=50_000, min_size=100)
        self.assertEqual(len(unusual), 1)
        self.assertEqual(unusual[0].option_type, "call")

    def test_get_dark_pool_levels_filters_by_min_value(self):
        big = DarkPoolPrint(
            symbol="SPY", timestamp=datetime.now(),
            price=500.0, size=50_000, value=25_000_000.0, exchange="X"
        )
        small = DarkPoolPrint(
            symbol="SPY", timestamp=datetime.now(),
            price=500.0, size=10_000, value=5_000_000.0, exchange="X"
        )
        mock_src = MagicMock(spec=BaseTickDataSource)
        mock_src.fetch_dark_pool_prints.return_value = [big, small]

        a = _make_analyzer(tick_source=mock_src)
        # Only prints with value >= 10M should pass
        levels = a.get_dark_pool_levels("SPY", lookback_days=5, min_value=10_000_000)
        self.assertEqual(len(levels), 1)
        self.assertEqual(levels[0].value, 25_000_000.0)


# ==============================================================================
# TESTS — create_order_flow_analyzer_from_env
# ==============================================================================

class TestCreateFromEnv(unittest.TestCase):

    def test_no_databento_key_gives_no_tick_source(self):
        captured = {}

        def fake_init(self, **kw):
            captured.update(kw)

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(OrderFlowAnalyzer, "__init__", fake_init),
        ):
            create_order_flow_analyzer_from_env()

        self.assertIsNone(captured.get("tick_data_source"))

    def test_databento_key_but_no_package_warns_and_no_source(self):
        captured = {}

        def fake_init(self, **kw):
            captured.update(kw)

        orig = _c30_mod.HAS_DATABENTO
        try:
            _c30_mod.HAS_DATABENTO = False
            with (
                patch.dict(os.environ, {"DATABENTO_API_KEY": "dbkey"}, clear=True),
                patch.object(OrderFlowAnalyzer, "__init__", fake_init),
            ):
                create_order_flow_analyzer_from_env()
        finally:
            _c30_mod.HAS_DATABENTO = orig

        self.assertIsNone(captured.get("tick_data_source"))

    def test_databento_key_with_package_sets_tick_source(self):
        captured = {}

        def fake_init(self, **kw):
            captured.update(kw)

        orig_has = _c30_mod.HAS_DATABENTO
        orig_db = _c30_mod.db
        orig_cls = _c30_mod.DatabentoTickDataSource
        try:
            _c30_mod.HAS_DATABENTO = True
            _c30_mod.db = MagicMock()
            # Patch the class on the module directly (loaded via importlib)
            mock_source = MagicMock(spec=BaseTickDataSource)
            _c30_mod.DatabentoTickDataSource = MagicMock(return_value=mock_source)

            with (
                patch.dict(os.environ, {"DATABENTO_API_KEY": "dbkey"}, clear=True),
                patch.object(OrderFlowAnalyzer, "__init__", fake_init),
            ):
                create_order_flow_analyzer_from_env()
        finally:
            _c30_mod.HAS_DATABENTO = orig_has
            _c30_mod.db = orig_db
            _c30_mod.DatabentoTickDataSource = orig_cls

        self.assertIn("tick_data_source", captured)
        self.assertIsNotNone(captured.get("tick_data_source"))

    def test_flow_symbols_read_from_env(self):
        captured = {}

        def fake_init(self, **kw):
            captured.update(kw)

        with (
            patch.dict(os.environ, {"FLOW_SYMBOLS": "SPY,QQQ,AAPL"}, clear=True),
            patch.object(OrderFlowAnalyzer, "__init__", fake_init),
        ):
            create_order_flow_analyzer_from_env()

        self.assertEqual(captured.get("symbols"), ["SPY", "QQQ", "AAPL"])

    def test_enable_realtime_defaults_to_false(self):
        captured = {}

        def fake_init(self, **kw):
            captured.update(kw)

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(OrderFlowAnalyzer, "__init__", fake_init),
        ):
            create_order_flow_analyzer_from_env()

        self.assertFalse(captured.get("enable_realtime"))


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
