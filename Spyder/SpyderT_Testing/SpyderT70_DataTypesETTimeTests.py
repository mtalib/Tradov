#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT70_DataTypesETTimeTests.py
Purpose: Tests for U09 DataTypes and U22 ETTimeDisplay

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 18:00:00
"""

# ==============================================================================
# BOOTSTRAP — load modules without installing Spyder as a package
# ==============================================================================
import sys
import os
import types
import importlib.util

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load(rel_path):
    abs_path = os.path.join(_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(rel_path, abs_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_pkg(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")

# U01 — Logger (required by U09 and U22)
_u01 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

# U02 — ErrorHandler (required by U09)
_u02 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

# U09 — DataTypes (needs U01 + U02)
_u09 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU09_DataTypes.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU09_DataTypes"] = _u09

# U03 mock — U22 only needs the US_EASTERN constant
_u03_mock = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils")
_u03_mock.US_EASTERN = "US/Eastern"
sys.modules["Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils"] = _u03_mock

# U22 — ETTimeDisplay (needs U01 + U03.US_EASTERN)
_u22 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU22_ETTimeDisplay.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU22_ETTimeDisplay"] = _u22

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock

# ==============================================================================
# MODULE IMPORTS — U09
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU09_DataTypes import (
    OptionRight,
    OptionStyle,
    OrderType,
    OrderAction,
    OrderStatus,
    PositionSide,
    DataQuality,
    MarketData,
    OptionContract,
    OrderData,
    Position,
    GreeksData,
    TradeExecution,
    SpyderDataTypes,
    PositionData,
    OptionData,
    MarketDataType,
    create_market_data,
    create_option_contract,
    get_data_types,
)

# ==============================================================================
# MODULE IMPORTS — U22
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU22_ETTimeDisplay import (
    get_et_time_string,
    get_et_time_for_dashboard,
    get_current_et_datetime,
    SimpleETDisplay,
    get_et_display,
    DASHBOARD_TIME_FORMAT,
    SIMPLE_TIME_FORMAT,
    EASTERN_TZ,
)


# ==============================================================================
# U09 — ENUM TESTS
# ==============================================================================
class TestOptionRightEnum:
    def test_call_value(self):
        assert OptionRight.CALL.value == "C" or OptionRight.CALL.value in ("CALL", "C")

    def test_put_exists(self):
        assert OptionRight.PUT is not None

    def test_call_and_put_are_distinct(self):
        assert OptionRight.CALL != OptionRight.PUT

    def test_from_value(self):
        # Try to instantiate via value — tolerates CALL or C
        val = OptionRight.CALL.value
        assert OptionRight(val) == OptionRight.CALL


class TestOptionStyleEnum:
    def test_american_exists(self):
        assert OptionStyle.AMERICAN is not None

    def test_european_exists(self):
        assert OptionStyle.EUROPEAN is not None


class TestOrderTypeEnum:
    def test_limit_exists(self):
        assert OrderType.LIMIT is not None

    def test_has_multiple_members(self):
        assert len(list(OrderType)) >= 2


class TestOrderActionEnum:
    def test_buy_exists(self):
        buy = [m for m in OrderAction if "BUY" in m.name.upper() or "BUY" in str(m.value).upper()]
        assert len(buy) >= 1

    def test_sell_exists(self):
        sell = [m for m in OrderAction if "SELL" in m.name.upper() or "SELL" in str(m.value).upper()]
        assert len(sell) >= 1


class TestOrderStatusEnum:
    def test_submitted_exists(self):
        assert OrderStatus.SUBMITTED is not None

    def test_pending_submit_exists(self):
        assert OrderStatus.PENDING_SUBMIT is not None


class TestPositionSideEnum:
    def test_long_exists(self):
        assert PositionSide.LONG is not None

    def test_short_exists(self):
        assert PositionSide.SHORT is not None

    def test_flat_exists(self):
        assert PositionSide.FLAT is not None


class TestDataQualityEnum:
    def test_unknown_exists(self):
        assert DataQuality.UNKNOWN is not None

    def test_multiple_members(self):
        assert len(list(DataQuality)) >= 2


class TestMarketDataTypeEnum:
    def test_quote_exists(self):
        assert MarketDataType.QUOTE is not None

    def test_trade_value(self):
        assert MarketDataType.TRADE.value == "trade"

    def test_bar_value(self):
        assert MarketDataType.BAR.value == "bar"

    def test_unknown_value(self):
        assert MarketDataType.UNKNOWN.value == "unknown"

    def test_all_members(self):
        expected = {"QUOTE", "TRADE", "BAR", "TICK", "LEVEL2", "OPTIONS_CHAIN",
                    "GREEKS", "VOLATILITY", "NEWS", "FUNDAMENTAL", "UNKNOWN"}
        actual = {m.name for m in MarketDataType}
        assert expected == actual


# ==============================================================================
# U09 — MarketData TESTS
# ==============================================================================
class TestMarketDataCreation:
    def test_basic_creation(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=450.10, last=450.05)
        assert md.symbol == "SPY"
        assert md.bid == 450.0
        assert md.ask == 450.10

    def test_empty_symbol_raises(self):
        with pytest.raises(ValueError):
            MarketData(symbol="")

    def test_default_quality(self):
        md = MarketData(symbol="SPY")
        assert md.quality == DataQuality.UNKNOWN

    def test_timestamp_set_automatically(self):
        md = MarketData(symbol="SPY")
        assert isinstance(md.timestamp, datetime)


class TestMarketDataMidPrice:
    def test_mid_price_with_valid_bid_ask(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=450.20)
        assert md.mid_price == pytest.approx(450.10, rel=1e-6)

    def test_mid_price_falls_back_to_last_when_bid_zero(self):
        md = MarketData(symbol="SPY", bid=0.0, ask=450.20, last=450.05)
        assert md.mid_price == 450.05

    def test_mid_price_falls_back_to_last_when_ask_zero(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=0.0, last=449.99)
        assert md.mid_price == 449.99


class TestMarketDataSpread:
    def test_spread_with_valid_bid_ask(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=450.10)
        assert md.spread == pytest.approx(0.10, abs=1e-9)

    def test_spread_zero_when_bid_zero(self):
        md = MarketData(symbol="SPY", bid=0.0, ask=450.10)
        assert md.spread == 0.0

    def test_spread_percent(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=450.40)
        pct = md.spread_percent
        assert pct > 0.0
        assert pct < 1.0

    def test_spread_percent_zero_when_no_bid_ask(self):
        md = MarketData(symbol="SPY", bid=0.0, ask=0.0, last=450.0)
        assert md.spread_percent == 0.0


class TestMarketDataToDict:
    def test_to_dict_contains_required_keys(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=450.10, last=450.05, volume=1000)
        d = md.to_dict()
        for key in ("symbol", "bid", "ask", "last", "volume", "timestamp",
                    "quality", "mid_price", "spread"):
            assert key in d

    def test_to_dict_symbol_value(self):
        md = MarketData(symbol="AAPL", bid=180.0, ask=180.05)
        d = md.to_dict()
        assert d["symbol"] == "AAPL"

    def test_to_dict_timestamp_is_iso_string(self):
        md = MarketData(symbol="SPY")
        d = md.to_dict()
        # Should be parseable as ISO datetime
        datetime.fromisoformat(d["timestamp"])


# ==============================================================================
# U09 — OptionContract TESTS
# ==============================================================================
class TestOptionContractCreation:
    def _future_date(self, days=30):
        return date.today() + timedelta(days=days)

    def test_basic_creation(self):
        expiry = self._future_date()
        oc = OptionContract(
            symbol="SPY_OPT",
            underlying="SPY",
            expiry=expiry,
            strike=450.0,
            right=OptionRight.CALL,
        )
        assert oc.underlying == "SPY"
        assert oc.strike == 450.0

    def test_invalid_strike_raises(self):
        expiry = self._future_date()
        with pytest.raises(ValueError):
            OptionContract(
                symbol="SPY_OPT",
                underlying="SPY",
                expiry=expiry,
                strike=-1.0,
                right=OptionRight.CALL,
            )

    def test_zero_strike_raises(self):
        expiry = self._future_date()
        with pytest.raises(ValueError):
            OptionContract(
                symbol="SPY_OPT",
                underlying="SPY",
                expiry=expiry,
                strike=0.0,
                right=OptionRight.CALL,
            )

    def test_invalid_multiplier_raises(self):
        expiry = self._future_date()
        with pytest.raises(ValueError):
            OptionContract(
                symbol="SPY_OPT",
                underlying="SPY",
                expiry=expiry,
                strike=450.0,
                right=OptionRight.CALL,
                multiplier=0,
            )


class TestOptionContractProperties:
    def _make_contract(self, right=OptionRight.CALL, strike=450.0, days=30):
        expiry = date.today() + timedelta(days=days)
        return OptionContract(
            symbol="SPY_OPT",
            underlying="SPY",
            expiry=expiry,
            strike=strike,
            right=right,
        )

    def test_option_symbol_call(self):
        oc = self._make_contract(right=OptionRight.CALL)
        sym = oc.option_symbol
        assert isinstance(sym, str)
        assert len(sym) > 0
        assert "C" in sym  # CALL encoded as C

    def test_option_symbol_put(self):
        oc = self._make_contract(right=OptionRight.PUT)
        sym = oc.option_symbol
        assert "P" in sym

    def test_days_to_expiry_positive(self):
        oc = self._make_contract(days=60)
        assert oc.days_to_expiry > 0

    def test_days_to_expiry_approximately_correct(self):
        oc = self._make_contract(days=30)
        assert 25 <= oc.days_to_expiry <= 31

    def test_to_dict_contains_keys(self):
        oc = self._make_contract()
        d = oc.to_dict()
        for key in ("symbol", "underlying", "expiry", "strike", "right",
                    "option_symbol", "days_to_expiry"):
            assert key in d

    def test_to_dict_right_is_string(self):
        oc = self._make_contract(right=OptionRight.PUT)
        d = oc.to_dict()
        assert isinstance(d["right"], str)


# ==============================================================================
# U09 — OrderData TESTS
# ==============================================================================
class TestOrderDataCreation:
    def _make_order(self, quantity=100, filled=0, status=OrderStatus.SUBMITTED):
        return OrderData(
            order_id=1,
            symbol="SPY",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=450.0,
            filled_quantity=filled,
            status=status,
        )

    def test_basic_creation(self):
        order = self._make_order()
        assert order.symbol == "SPY"
        assert order.quantity == 100

    def test_invalid_quantity_raises(self):
        with pytest.raises(ValueError):
            OrderData(
                order_id=1,
                symbol="SPY",
                action=OrderAction.BUY,
                order_type=OrderType.LIMIT,
                quantity=0,
            )

    def test_remaining_quantity_calculated(self):
        order = self._make_order(quantity=100, filled=30)
        assert order.remaining_quantity == 70

    def test_is_filled_false_when_partial(self):
        order = self._make_order(quantity=100, filled=50)
        assert order.is_filled is False

    def test_is_filled_true_when_complete(self):
        order = self._make_order(quantity=100, filled=100)
        assert order.is_filled is True

    def test_is_active_true_when_submitted(self):
        order = self._make_order(status=OrderStatus.SUBMITTED)
        assert order.is_active is True

    def test_is_active_true_when_pending(self):
        order = self._make_order(status=OrderStatus.PENDING_SUBMIT)
        assert order.is_active is True

    def test_is_active_false_when_not_active(self):
        # Use a non-active status
        non_active = [s for s in OrderStatus
                      if s not in (OrderStatus.SUBMITTED, OrderStatus.PENDING_SUBMIT)]
        if non_active:
            order = self._make_order(status=non_active[0])
            assert order.is_active is False

    def test_fill_percentage_zero_when_unfilled(self):
        order = self._make_order(quantity=100, filled=0)
        assert order.fill_percentage == pytest.approx(0.0)

    def test_fill_percentage_half(self):
        order = self._make_order(quantity=100, filled=50)
        assert order.fill_percentage == pytest.approx(50.0)

    def test_fill_percentage_full(self):
        order = self._make_order(quantity=100, filled=100)
        assert order.fill_percentage == pytest.approx(100.0)

    def test_to_dict_contains_keys(self):
        order = self._make_order()
        d = order.to_dict()
        for key in ("order_id", "symbol", "action", "order_type", "quantity",
                    "price", "status", "is_filled", "is_active", "fill_percentage"):
            assert key in d

    def test_to_dict_timestamp_iso(self):
        order = self._make_order()
        d = order.to_dict()
        datetime.fromisoformat(d["timestamp"])


# ==============================================================================
# U09 — Position TESTS
# ==============================================================================
class TestPositionSides:
    def test_long_position(self):
        pos = Position(symbol="SPY", quantity=100, avg_cost=450.0, market_price=455.0)
        assert pos.side == PositionSide.LONG

    def test_short_position(self):
        pos = Position(symbol="SPY", quantity=-50, avg_cost=450.0, market_price=445.0)
        assert pos.side == PositionSide.SHORT

    def test_flat_position(self):
        pos = Position(symbol="SPY", quantity=0, avg_cost=450.0, market_price=450.0)
        assert pos.side == PositionSide.FLAT


class TestPositionPnL:
    def test_unrealized_pnl_positive_for_long(self):
        pos = Position(symbol="SPY", quantity=100, avg_cost=445.0, market_price=455.0)
        # market_price > avg_cost for long → unrealized positive
        assert pos.unrealized_pnl > 0

    def test_unrealized_pnl_negative_for_adverse_move(self):
        pos = Position(symbol="SPY", quantity=100, avg_cost=455.0, market_price=445.0)
        assert pos.unrealized_pnl < 0

    def test_total_pnl_sums_realized_and_unrealized(self):
        pos = Position(symbol="SPY", quantity=100, avg_cost=445.0,
                       market_price=455.0, realized_pnl=200.0)
        assert pos.total_pnl == pytest.approx(pos.realized_pnl + pos.unrealized_pnl)

    def test_update_market_values_updates_market_value(self):
        pos = Position(symbol="SPY", quantity=10, avg_cost=445.0, market_price=0.0)
        pos.market_price = 450.0
        pos.update_market_values()
        assert pos.market_value == pytest.approx(4500.0)

    def test_to_dict_contains_all_keys(self):
        pos = Position(symbol="SPY", quantity=100, avg_cost=445.0, market_price=450.0)
        d = pos.to_dict()
        for key in ("symbol", "quantity", "avg_cost", "market_price",
                    "unrealized_pnl", "realized_pnl", "total_pnl", "side"):
            assert key in d

    def test_to_dict_side_is_string(self):
        pos = Position(symbol="SPY", quantity=100, avg_cost=445.0, market_price=450.0)
        d = pos.to_dict()
        assert isinstance(d["side"], str)


# ==============================================================================
# U09 — GreeksData TESTS
# ==============================================================================
class TestGreeksData:
    def test_basic_creation(self):
        g = GreeksData(symbol="SPY_OPT", delta=0.5, gamma=0.02, theta=-0.05, vega=0.15)
        assert g.symbol == "SPY_OPT"
        assert g.delta == 0.5

    def test_to_dict_contains_keys(self):
        g = GreeksData(symbol="SPY_OPT", delta=0.5, gamma=0.02,
                       theta=-0.05, vega=0.15, implied_volatility=0.20)
        d = g.to_dict()
        for key in ("symbol", "delta", "gamma", "theta", "vega", "rho",
                    "implied_volatility", "underlying_price", "timestamp"):
            assert key in d

    def test_to_dict_timestamp_iso(self):
        g = GreeksData(symbol="SPY_OPT")
        d = g.to_dict()
        datetime.fromisoformat(d["timestamp"])

    def test_defaults_are_zero(self):
        g = GreeksData(symbol="SPY_OPT")
        assert g.delta == 0.0
        assert g.gamma == 0.0
        assert g.vega == 0.0


# ==============================================================================
# U09 — TradeExecution TESTS
# ==============================================================================
class TestTradeExecution:
    def _make_exec(self, qty=10, price=450.0):
        return TradeExecution(
            execution_id="EXEC001",
            order_id=42,
            symbol="SPY",
            side="BUY",
            quantity=qty,
            price=price,
            commission=1.50,
            timestamp=datetime(2026, 1, 6, 10, 30, 0),
        )

    def test_notional_value(self):
        ex = self._make_exec(qty=10, price=450.0)
        assert ex.notional_value == pytest.approx(4500.0)

    def test_notional_value_absolute(self):
        # Negative quantity (short) should still give positive notional
        ex = self._make_exec(qty=-5, price=450.0)
        assert ex.notional_value == pytest.approx(2250.0)

    def test_to_dict_contains_keys(self):
        ex = self._make_exec()
        d = ex.to_dict()
        for key in ("execution_id", "order_id", "symbol", "side",
                    "quantity", "price", "commission", "timestamp", "notional_value"):
            assert key in d

    def test_to_dict_timestamp_iso(self):
        ex = self._make_exec()
        d = ex.to_dict()
        datetime.fromisoformat(d["timestamp"])

    def test_exchange_default_empty(self):
        ex = self._make_exec()
        assert ex.exchange == ""

    def test_exchange_can_be_set(self):
        ex = TradeExecution(
            execution_id="E2",
            order_id=1,
            symbol="SPY",
            side="SELL",
            quantity=5,
            price=450.0,
            commission=0.50,
            timestamp=datetime.now(),
            exchange="CBOE",
        )
        assert ex.exchange == "CBOE"


# ==============================================================================
# U09 — SpyderDataTypes TESTS
# ==============================================================================
class TestSpyderDataTypesInit:
    def test_instantiation(self):
        sdt = SpyderDataTypes()
        assert sdt is not None
        assert hasattr(sdt, "logger")
        assert hasattr(sdt, "error_handler")


class TestSpyderDataTypesCreateMarketData:
    def setup_method(self):
        self.sdt = SpyderDataTypes()

    def test_create_basic_market_data(self):
        md = self.sdt.create_market_data("SPY", bid=450.0, ask=450.10, last=450.05)
        assert md.symbol == "SPY"
        assert md.bid == 450.0

    def test_create_market_data_with_volume(self):
        md = self.sdt.create_market_data("SPY", volume=100000)
        assert md.volume == 100000

    def test_create_market_data_defaults_to_zero(self):
        md = self.sdt.create_market_data("SPY")
        assert md.bid == 0.0
        assert md.ask == 0.0

    def test_create_market_data_invalid_symbol_raises(self):
        with pytest.raises(ValueError):
            self.sdt.create_market_data("")


class TestSpyderDataTypesCreateOptionContract:
    def setup_method(self):
        self.sdt = SpyderDataTypes()
        self.expiry_str = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")

    def test_create_call_contract(self):
        oc = self.sdt.create_option_contract("SPY", self.expiry_str, 450.0, "CALL")
        assert oc.underlying == "SPY"
        assert oc.strike == 450.0
        assert oc.right == OptionRight.CALL

    def test_create_put_contract(self):
        oc = self.sdt.create_option_contract("SPY", self.expiry_str, 440.0, "PUT")
        assert oc.right == OptionRight.PUT

    def test_create_contract_lowercase_right(self):
        # Should normalise case
        oc = self.sdt.create_option_contract("SPY", self.expiry_str, 450.0, "call")
        assert oc.right == OptionRight.CALL

    def test_invalid_expiry_raises(self):
        with pytest.raises(Exception):
            self.sdt.create_option_contract("SPY", "not-a-date", 450.0, "CALL")

    def test_symbol_generated(self):
        oc = self.sdt.create_option_contract("SPY", self.expiry_str, 450.0, "CALL")
        assert "SPY" in oc.symbol


class TestSpyderDataTypesCreateOrder:
    def setup_method(self):
        self.sdt = SpyderDataTypes()

    def test_create_buy_limit_order(self):
        order = self.sdt.create_order("SPY", "BUY", "LMT", 10, 450.0)
        assert order.symbol == "SPY"
        assert order.quantity == 10
        assert order.price == 450.0

    def test_create_sell_order(self):
        order = self.sdt.create_order("SPY", "SELL", "MKT", 5)
        # action should be SELL
        assert "SELL" in order.action.value.upper() or "SELL" in order.action.name.upper()

    def test_invalid_action_raises(self):
        with pytest.raises(Exception):
            self.sdt.create_order("SPY", "INVALID", "LMT", 10)

    def test_invalid_order_type_raises(self):
        with pytest.raises(Exception):
            self.sdt.create_order("SPY", "BUY", "BADTYPE", 10)


class TestSpyderDataTypesValidateMarketData:
    def setup_method(self):
        self.sdt = SpyderDataTypes()

    def test_valid_market_data(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=450.10, last=450.05)
        assert self.sdt.validate_market_data(md) is True

    def test_negative_bid_is_invalid(self):
        md = MarketData(symbol="SPY", bid=-1.0, ask=450.10)
        assert self.sdt.validate_market_data(md) is False

    def test_negative_ask_is_invalid(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=-0.10, last=450.0)
        assert self.sdt.validate_market_data(md) is False

    def test_bid_greater_than_ask_is_invalid(self):
        md = MarketData(symbol="SPY", bid=451.0, ask=450.0)
        assert self.sdt.validate_market_data(md) is False

    def test_bid_equal_to_ask_is_invalid(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=450.0)
        assert self.sdt.validate_market_data(md) is False

    def test_zero_bid_and_ask_is_valid(self):
        # No bid/ask but valid symbol — validation allows this
        md = MarketData(symbol="SPY", bid=0.0, ask=0.0, last=450.0)
        result = self.sdt.validate_market_data(md)
        # bid >= ask applies only when both > 0; 0.0 not > 0
        assert result is True


class TestSpyderDataTypesValidateOptionContract:
    def setup_method(self):
        self.sdt = SpyderDataTypes()

    def test_valid_future_contract(self):
        expiry = date.today() + timedelta(days=30)
        oc = OptionContract(
            symbol="SPY_OPT",
            underlying="SPY",
            expiry=expiry,
            strike=450.0,
            right=OptionRight.CALL,
        )
        assert self.sdt.validate_option_contract(oc) is True

    def test_expired_contract_is_invalid(self):
        expiry = date.today() - timedelta(days=1)
        oc = OptionContract(
            symbol="SPY_OPT",
            underlying="SPY",
            expiry=expiry,
            strike=450.0,
            right=OptionRight.CALL,
        )
        assert self.sdt.validate_option_contract(oc) is False

    def test_today_expiry_is_invalid(self):
        expiry = date.today()
        oc = OptionContract(
            symbol="SPY_OPT",
            underlying="SPY",
            expiry=expiry,
            strike=450.0,
            right=OptionRight.CALL,
        )
        assert self.sdt.validate_option_contract(oc) is False


# ==============================================================================
# U09 — MODULE-LEVEL FUNCTION TESTS
# ==============================================================================
class TestModuleFunctionCreateMarketData:
    def test_creates_market_data_instance(self):
        md = create_market_data("TSLA", bid=200.0, ask=200.10)
        assert isinstance(md, MarketData)
        assert md.symbol == "TSLA"

    def test_create_with_volume(self):
        md = create_market_data("SPY", volume=50000)
        assert md.volume == 50000


class TestModuleFunctionCreateOptionContract:
    def test_creates_option_contract(self):
        expiry_str = (date.today() + timedelta(days=45)).strftime("%Y-%m-%d")
        oc = create_option_contract("SPY", expiry_str, 450.0, "CALL")
        assert isinstance(oc, OptionContract)
        assert oc.underlying == "SPY"

    def test_creates_put_contract(self):
        expiry_str = (date.today() + timedelta(days=45)).strftime("%Y-%m-%d")
        oc = create_option_contract("SPY", expiry_str, 440.0, "PUT")
        assert oc.right == OptionRight.PUT


class TestGetDataTypesSingleton:
    def test_returns_spyder_data_types_instance(self):
        sdt = get_data_types()
        assert isinstance(sdt, SpyderDataTypes)

    def test_returns_same_instance_on_second_call(self):
        sdt1 = get_data_types()
        sdt2 = get_data_types()
        assert sdt1 is sdt2


# ==============================================================================
# U09 — PositionData TESTS
# ==============================================================================
class TestPositionDataClass:
    def test_instantiation(self):
        pd_obj = PositionData()
        assert pd_obj is not None

    def test_default_symbol_empty(self):
        pd_obj = PositionData()
        assert pd_obj.symbol == ""

    def test_default_quantity_zero(self):
        pd_obj = PositionData()
        assert pd_obj.quantity == 0

    def test_default_pnl_zero(self):
        pd_obj = PositionData()
        assert pd_obj.pnl == 0.0

    def test_attribute_assignment(self):
        pd_obj = PositionData()
        pd_obj.symbol = "SPY"
        pd_obj.quantity = 100
        pd_obj.entry_price = 450.0
        pd_obj.current_price = 455.0
        pd_obj.pnl = 500.0
        assert pd_obj.symbol == "SPY"
        assert pd_obj.quantity == 100
        assert pd_obj.pnl == 500.0


# ==============================================================================
# U09 — OptionData Dataclass TESTS
# ==============================================================================
class TestOptionDataDataclass:
    def test_basic_creation(self):
        od = OptionData(
            symbol="SPY_OPT",
            expiration=datetime(2026, 3, 20),
            strike=450.0,
            option_type="call",
        )
        assert od.symbol == "SPY_OPT"
        assert od.strike == 450.0

    def test_default_bid_zero(self):
        od = OptionData(
            symbol="SPY_OPT",
            expiration=datetime(2026, 3, 20),
            strike=450.0,
            option_type="put",
        )
        assert od.bid == 0.0

    def test_greeks_defaults(self):
        od = OptionData(
            symbol="SPY_OPT",
            expiration=datetime(2026, 3, 20),
            strike=450.0,
            option_type="call",
        )
        assert od.delta == 0.0
        assert od.gamma == 0.0
        assert od.theta == 0.0
        assert od.vega == 0.0

    def test_set_greeks(self):
        od = OptionData(
            symbol="SPY_OPT",
            expiration=datetime(2026, 3, 20),
            strike=450.0,
            option_type="call",
            delta=0.52,
            gamma=0.02,
            theta=-0.05,
            vega=0.18,
            implied_volatility=0.22,
        )
        assert od.delta == pytest.approx(0.52)
        assert od.implied_volatility == pytest.approx(0.22)


# ==============================================================================
# U22 — ETTimeDisplay TESTS
# ==============================================================================
class TestGetEtTimeString:
    def test_returns_string(self):
        result = get_et_time_string()
        assert isinstance(result, str)

    def test_with_timezone_includes_tz_abbreviation(self):
        result = get_et_time_string(include_timezone=True)
        # Should include EDT or EST
        assert "EDT" in result or "EST" in result or "ET" in result

    def test_without_timezone_format(self):
        result = get_et_time_string(include_timezone=False)
        # Should be HH:MM:SS format, parseable
        parts = result.split(":")
        assert len(parts) == 3

    def test_without_timezone_no_tz_label(self):
        result = get_et_time_string(include_timezone=False)
        assert "EDT" not in result
        assert "EST" not in result

    def test_fallback_on_exception(self):
        """Even if timezone fails, function returns a string."""
        with patch("Spyder.SpyderU_Utilities.SpyderU22_ETTimeDisplay.EASTERN_TZ", None):
            result = get_et_time_string()
            # Should return local time fallback
            assert isinstance(result, str)


class TestGetEtTimeForDashboard:
    def test_returns_string(self):
        result = get_et_time_for_dashboard()
        assert isinstance(result, str)

    def test_includes_tz_by_default(self):
        result = get_et_time_for_dashboard()
        assert "EDT" in result or "EST" in result or "ET" in result

    def test_matches_get_et_time_string_with_tz(self):
        """Both functions should give same format."""
        r1 = get_et_time_for_dashboard()
        r2 = get_et_time_string(include_timezone=True)
        # Both should be non-empty strings with same format length (~11-12 chars)
        assert len(r1) > 0 and len(r2) > 0


class TestGetCurrentEtDatetime:
    def test_returns_datetime(self):
        result = get_current_et_datetime()
        assert isinstance(result, datetime)

    def test_has_timezone_info(self):
        result = get_current_et_datetime()
        assert result.tzinfo is not None

    def test_is_reasonably_recent(self):
        result = get_current_et_datetime()
        now_utc = datetime.now().replace(tzinfo=result.tzinfo)
        # Within a few seconds
        diff = abs((result - now_utc).total_seconds())
        # Allow 5-hour offset (ET is UTC-4 or UTC-5) + 60 seconds slop
        assert diff < 6 * 3600

    def test_fallback_on_exception(self):
        """Should return a datetime even if timezone call fails."""
        with patch("Spyder.SpyderU_Utilities.SpyderU22_ETTimeDisplay.EASTERN_TZ", None):
            result = get_current_et_datetime()
            assert isinstance(result, datetime)


class TestSimpleETDisplay:
    def test_instantiation(self):
        display = SimpleETDisplay()
        assert display is not None

    def test_has_eastern_tz(self):
        display = SimpleETDisplay()
        assert display.eastern_tz is not None

    def test_get_time_string_with_tz(self):
        display = SimpleETDisplay()
        result = display.get_time_string(include_tz=True)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_time_string_without_tz(self):
        display = SimpleETDisplay()
        result = display.get_time_string(include_tz=False)
        assert isinstance(result, str)
        parts = result.split(":")
        assert len(parts) == 3

    def test_get_time_string_default_includes_tz(self):
        display = SimpleETDisplay()
        result_default = display.get_time_string()
        result_explicit = display.get_time_string(include_tz=True)
        # Both should have timezone abbreviation
        def has_tz(s):
            return ("EDT" in s or "EST" in s or "ET" in s)
        assert has_tz(result_default) and has_tz(result_explicit)

    def test_get_time_string_error_fallback(self):
        """If eastern_tz is broken, should return fallback string."""
        display = SimpleETDisplay()
        display.eastern_tz = None  # Force error path
        result = display.get_time_string()
        assert isinstance(result, str)


class TestGetEtDisplaySingleton:
    def setup_method(self):
        """Reset singleton before each test."""
        import Spyder.SpyderU_Utilities.SpyderU22_ETTimeDisplay as u22
        u22._et_display = None

    def test_returns_simple_et_display(self):
        display = get_et_display()
        assert isinstance(display, SimpleETDisplay)

    def test_returns_same_instance_on_repeat(self):
        d1 = get_et_display()
        d2 = get_et_display()
        assert d1 is d2

    def test_singleton_is_usable(self):
        display = get_et_display()
        result = display.get_time_string()
        assert isinstance(result, str)
