#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT50_TradierOrderTests.py
Purpose: Unit tests for TradierClient order execution path — covers gaps left
         by SpyderT40 (option orders, multileg, iron condor, credit spread,
         modify, Greeks chain, option symbol utils, async paths, full lifecycle).

All HTTP calls are intercepted via unittest.mock — zero network I/O.

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-03-03 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytest

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
    GreekData,
    OptionLeg,
    OrderClass,
    OrderDuration,
    OrderSide,
    OrderType,
    TradierAPIError,
    TradierAuthenticationError,
    TradierClient,
    TradierValidationError,
    TradingEnvironment,
    build_option_symbol,
    parse_option_symbol,
)

# ==============================================================================
# CONSTANTS / SHARED FIXTURES
# ==============================================================================
FAKE_API_KEY = "test_api_key_abc123"
FAKE_ACCOUNT = "VA12345678"
EXPIRY = "2026-03-20"
EXPIRY_SHORT = "260320"

ORDER_PLACED_RESPONSE: Dict[str, Any] = {"order": {"id": 999001, "status": "ok"}}
ORDER_STATUS_OPEN: Dict[str, Any] = {
    "order": {
        "id": 999001,
        "status": "open",
        "symbol": "SPY",
        "type": "limit",
        "side": "buy",
        "quantity": 1.0,
        "filled_quantity": 0.0,
        "remaining_quantity": 1.0,
        "avg_fill_price": 0.0,
        "price": 2.50,
        "duration": "day",
        "class": "option",
        "option_symbol": "SPY260320C00560000",
    }
}
ORDER_STATUS_FILLED: Dict[str, Any] = {
    "order": {**ORDER_STATUS_OPEN["order"], "status": "filled", "filled_quantity": 1.0, "avg_fill_price": 2.48}
}
CANCEL_RESPONSE: Dict[str, Any] = {"order": {"id": 999001, "status": "canceled"}}
MODIFY_RESPONSE: Dict[str, Any] = {"order": {"id": 999001, "status": "pending"}}


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def client() -> TradierClient:
    """Return a sandbox TradierClient with no real network calls."""
    return TradierClient(
        api_key=FAKE_API_KEY,
        account_id=FAKE_ACCOUNT,
        environment=TradingEnvironment.SANDBOX,
    )


@pytest.fixture
def mock_request(client: TradierClient):
    """Patch _make_request so no HTTP ever fires."""
    with patch.object(client, "_make_request") as mock:
        yield mock


# ==============================================================================
# OPTION SYMBOL UTILITIES
# ==============================================================================

class TestBuildOptionSymbol:
    """Tests for build_option_symbol()."""

    def test_call_long_form_expiry(self):
        sym = build_option_symbol("SPY", "2026-03-20", "C", 560.0)
        assert sym == "SPY260320C00560000"

    def test_put_short_form_expiry(self):
        sym = build_option_symbol("SPY", "260320", "P", 545.5)
        assert sym == "SPY260320P00545500"

    def test_full_word_call(self):
        sym = build_option_symbol("SPY", "2026-03-20", "call", 560.0)
        assert sym == "SPY260320C00560000"

    def test_full_word_put(self):
        sym = build_option_symbol("SPY", "2026-03-20", "put", 560.0)
        assert sym == "SPY260320P00560000"

    def test_fractional_cent_strike(self):
        # 550.50 → strike_int = 550500 → "00550500"
        sym = build_option_symbol("SPY", "2026-03-20", "C", 550.50)
        assert sym == "SPY260320C00550500"

    def test_invalid_option_type_raises(self):
        with pytest.raises(ValueError, match="option_type"):
            build_option_symbol("SPY", "2026-03-20", "X", 560.0)

    def test_invalid_expiry_format_raises(self):
        with pytest.raises(ValueError):
            build_option_symbol("SPY", "20260320", "C", 560.0)  # 8-char, not supported

    def test_multi_char_ticker(self):
        sym = build_option_symbol("AAPL", "2026-03-20", "C", 200.0)
        assert sym == "AAPL260320C00200000"


class TestParseOptionSymbol:
    """Tests for parse_option_symbol()."""

    def test_roundtrip_call(self):
        original = "SPY260320C00560000"
        parsed = parse_option_symbol(original)
        assert parsed["underlying"] == "SPY"
        assert parsed["option_type"] == "C"
        assert parsed["strike"] == 560.0
        assert parsed["expiration"] == "260320"
        assert parsed["expiration_date"] == "2026-03-20"
        assert parsed["symbol"] == original

    def test_roundtrip_put(self):
        original = "SPY260320P00545500"
        parsed = parse_option_symbol(original)
        assert parsed["option_type"] == "P"
        assert parsed["strike"] == 545.5

    def test_multi_char_ticker(self):
        parsed = parse_option_symbol("AAPL260320C00200000")
        assert parsed["underlying"] == "AAPL"

    def test_invalid_symbol_raises(self):
        with pytest.raises(ValueError):
            parse_option_symbol("BADINPUT")

    def test_build_then_parse_identity(self):
        sym = build_option_symbol("SPY", EXPIRY, "C", 560.0)
        parsed = parse_option_symbol(sym)
        rebuilt = build_option_symbol(
            parsed["underlying"],
            parsed["expiration_date"],
            parsed["option_type"],
            parsed["strike"],
        )
        assert rebuilt == sym


# ==============================================================================
# GREEK DATA PROPERTIES
# ==============================================================================

class TestGreekDataProperties:
    """Tests for GreekData computed properties."""

    def test_spread_calculation(self):
        g = GreekData(bid=2.40, ask=2.60, mid=2.50)
        assert abs(g.spread - 0.20) < 1e-9

    def test_spread_pct(self):
        g = GreekData(bid=2.40, ask=2.60, mid=2.50)
        assert abs(g.spread_pct - 8.0) < 0.01  # 0.20 / 2.50 * 100 = 8%

    def test_spread_pct_zero_mid(self):
        g = GreekData(bid=0.0, ask=0.0, mid=0.0)
        assert g.spread_pct == 0.0

    def test_zero_spread(self):
        g = GreekData(bid=2.50, ask=2.50, mid=2.50)
        assert g.spread == 0.0

    def test_in_the_money_flag(self):
        g = GreekData(in_the_money=True)
        assert g.in_the_money is True

    def test_greekdata_defaults(self):
        g = GreekData()
        assert g.delta == 0.0
        assert g.gamma == 0.0
        assert g.symbol == ""


# ==============================================================================
# OPTION ORDER PLACEMENT
# ==============================================================================

class TestOptionOrderPlacement:
    """Single-leg option orders and order lifecycle."""

    def test_place_single_option_buy_to_open(self, mock_request, client):
        """Buy-to-open a call option at limit."""
        mock_request.return_value = ORDER_PLACED_RESPONSE
        opt_sym = build_option_symbol("SPY", EXPIRY, "C", 560.0)

        result = client.place_order(
            symbol=opt_sym,
            side=OrderSide.BUY_TO_OPEN,
            quantity=1,
            order_type=OrderType.LIMIT,
            limit_price=2.50,
            order_class=OrderClass.OPTION,
        )

        assert result["order"]["id"] == 999001
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        payload = call_args[1]["data"]
        assert payload["class"] == "option"
        assert payload["side"] == "buy_to_open"
        assert payload["price"] == 2.50
        assert payload["quantity"] == 1

    def test_place_single_option_sell_to_open(self, mock_request, client):
        """Sell-to-open a put option."""
        mock_request.return_value = ORDER_PLACED_RESPONSE
        opt_sym = build_option_symbol("SPY", EXPIRY, "P", 540.0)

        client.place_order(
            symbol=opt_sym,
            side=OrderSide.SELL_TO_OPEN,
            quantity=2,
            order_type=OrderType.LIMIT,
            limit_price=1.80,
            order_class=OrderClass.OPTION,
        )

        payload = mock_request.call_args[1]["data"]
        assert payload["side"] == "sell_to_open"
        assert payload["quantity"] == 2

    def test_place_option_market_order(self, mock_request, client):
        """Market option order — no price field."""
        mock_request.return_value = ORDER_PLACED_RESPONSE
        client.place_order(
            symbol=build_option_symbol("SPY", EXPIRY, "C", 560.0),
            side=OrderSide.BUY_TO_OPEN,
            quantity=1,
            order_type=OrderType.MARKET,
            order_class=OrderClass.OPTION,
        )
        payload = mock_request.call_args[1]["data"]
        assert "price" not in payload
        assert payload["type"] == "market"

    def test_get_order_status_open(self, mock_request, client):
        mock_request.return_value = ORDER_STATUS_OPEN
        result = client.get_order(999001)
        assert result["order"]["status"] == "open"
        assert mock_request.call_args[0][0] == "GET"
        assert "999001" in mock_request.call_args[0][1]

    def test_get_order_status_filled(self, mock_request, client):
        mock_request.return_value = ORDER_STATUS_FILLED
        result = client.get_order(999001)
        assert result["order"]["status"] == "filled"
        assert result["order"]["avg_fill_price"] == 2.48

    def test_cancel_option_order(self, mock_request, client):
        mock_request.return_value = CANCEL_RESPONSE
        result = client.cancel_order(999001)
        assert result["order"]["status"] == "canceled"
        assert mock_request.call_args[0][0] == "DELETE"

    def test_full_lifecycle_place_check_cancel(self, mock_request, client):
        """Simulate: place → open → cancel lifecycle."""
        mock_request.side_effect = [
            ORDER_PLACED_RESPONSE,
            ORDER_STATUS_OPEN,
            CANCEL_RESPONSE,
        ]
        placed = client.place_order(
            symbol=build_option_symbol("SPY", EXPIRY, "C", 560.0),
            side=OrderSide.BUY_TO_OPEN,
            quantity=1,
            order_type=OrderType.LIMIT,
            limit_price=2.50,
            order_class=OrderClass.OPTION,
        )
        order_id = placed["order"]["id"]
        assert order_id == 999001

        status = client.get_order(order_id)
        assert status["order"]["status"] == "open"

        cancelled = client.cancel_order(order_id)
        assert cancelled["order"]["status"] == "canceled"
        assert mock_request.call_count == 3


# ==============================================================================
# MODIFY ORDER
# ==============================================================================

class TestModifyOrder:
    def test_modify_limit_price(self, mock_request, client):
        mock_request.return_value = MODIFY_RESPONSE
        result = client.modify_order(order_id=999001, price=2.30)
        assert result["order"]["id"] == 999001
        payload = mock_request.call_args[1]["data"]
        assert payload["price"] == "2.3"
        assert mock_request.call_args[0][0] == "PUT"

    def test_modify_type_and_duration(self, mock_request, client):
        mock_request.return_value = MODIFY_RESPONSE
        client.modify_order(order_id=999001, order_type="market", duration="gtc")
        payload = mock_request.call_args[1]["data"]
        assert payload["type"] == "market"
        assert payload["duration"] == "gtc"

    def test_modify_stop_price(self, mock_request, client):
        mock_request.return_value = MODIFY_RESPONSE
        client.modify_order(order_id=999001, stop=550.0)
        payload = mock_request.call_args[1]["data"]
        assert payload["stop"] == "550.0"

    def test_modify_empty_payload_still_calls(self, mock_request, client):
        """An empty modify (no fields) still makes the PUT."""
        mock_request.return_value = MODIFY_RESPONSE
        client.modify_order(order_id=999001)
        assert mock_request.called
        assert mock_request.call_args[0][0] == "PUT"


# ==============================================================================
# MULTILEG ORDERS (2-LEG SPREAD)
# ==============================================================================

class TestMultilegOrders:
    """Tests for place_multileg_order."""

    def _make_spread_legs(self) -> list:
        return [
            OptionLeg(
                option_symbol=build_option_symbol("SPY", EXPIRY, "P", 540.0),
                side=OrderSide.SELL_TO_OPEN,
                quantity=1,
            ),
            OptionLeg(
                option_symbol=build_option_symbol("SPY", EXPIRY, "P", 535.0),
                side=OrderSide.BUY_TO_OPEN,
                quantity=1,
            ),
        ]

    def test_place_credit_spread_multileg(self, mock_request, client):
        mock_request.return_value = ORDER_PLACED_RESPONSE
        legs = self._make_spread_legs()

        result = client.place_multileg_order(
            symbol="SPY",
            legs=legs,
            order_type="credit",
            price=1.50,
        )

        assert result["order"]["id"] == 999001
        payload = mock_request.call_args[1]["data"]
        assert payload["class"] == "multileg"
        assert payload["symbol"] == "SPY"
        assert payload["type"] == "credit"
        assert payload["price"] == "1.5"
        assert payload["option_symbol[0]"] == "SPY260320P00540000"
        assert payload["side[0]"] == "sell_to_open"
        assert payload["option_symbol[1]"] == "SPY260320P00535000"
        assert payload["side[1]"] == "buy_to_open"

    def test_multileg_debit_price_required(self, client):
        legs = self._make_spread_legs()
        with pytest.raises(ValueError, match="price is required"):
            client.place_multileg_order("SPY", legs, order_type="debit", price=None)

    def test_multileg_credit_price_required(self, client):
        legs = self._make_spread_legs()
        with pytest.raises(ValueError, match="price is required"):
            client.place_multileg_order("SPY", legs, order_type="credit", price=None)

    def test_multileg_market_no_price_needed(self, mock_request, client):
        mock_request.return_value = ORDER_PLACED_RESPONSE
        legs = self._make_spread_legs()
        # Should not raise — market type doesn't require price
        client.place_multileg_order("SPY", legs, order_type="market")
        payload = mock_request.call_args[1]["data"]
        assert "price" not in payload

    def test_multileg_empty_legs_raises(self, client):
        with pytest.raises(ValueError, match="At least one"):
            client.place_multileg_order("SPY", [], order_type="market")

    def test_multileg_with_tag(self, mock_request, client):
        mock_request.return_value = ORDER_PLACED_RESPONSE
        legs = self._make_spread_legs()
        client.place_multileg_order("SPY", legs, order_type="market", tag="strategy_x")
        payload = mock_request.call_args[1]["data"]
        assert payload["tag"] == "strategy_x"

    def test_multileg_leg_quantity_string_encoded(self, mock_request, client):
        """Tradier expects quantity as string in multileg payload."""
        mock_request.return_value = ORDER_PLACED_RESPONSE
        legs = self._make_spread_legs()
        client.place_multileg_order("SPY", legs, order_type="market")
        payload = mock_request.call_args[1]["data"]
        # quantity must be string "1"
        assert payload["quantity[0]"] == "1"
        assert payload["quantity[1]"] == "1"


# ==============================================================================
# IRON CONDOR
# ==============================================================================

class TestIronCondor:
    """Tests for place_iron_condor()."""

    def test_iron_condor_creates_four_legs(self, mock_request, client):
        mock_request.return_value = ORDER_PLACED_RESPONSE

        result = client.place_iron_condor(
            symbol="SPY",
            expiration=EXPIRY,
            put_buy_strike=535.0,
            put_sell_strike=540.0,
            call_sell_strike=570.0,
            call_buy_strike=575.0,
            quantity=1,
            order_type="credit",
            price=2.00,
        )

        assert result["order"]["id"] == 999001
        payload = mock_request.call_args[1]["data"]
        assert payload["class"] == "multileg"
        assert payload["type"] == "credit"
        assert payload["price"] == "2.0"
        assert payload["tag"] == "iron_condor"
        # Leg 0: buy P535
        assert payload["option_symbol[0]"] == build_option_symbol("SPY", EXPIRY, "P", 535.0)
        assert payload["side[0]"] == "buy_to_open"
        # Leg 1: sell P540
        assert payload["option_symbol[1]"] == build_option_symbol("SPY", EXPIRY, "P", 540.0)
        assert payload["side[1]"] == "sell_to_open"
        # Leg 2: sell C570
        assert payload["option_symbol[2]"] == build_option_symbol("SPY", EXPIRY, "C", 570.0)
        assert payload["side[2]"] == "sell_to_open"
        # Leg 3: buy C575
        assert payload["option_symbol[3]"] == build_option_symbol("SPY", EXPIRY, "C", 575.0)
        assert payload["side[3]"] == "buy_to_open"

    def test_iron_condor_exact_leg_count(self, mock_request, client):
        """Verify exactly 4 legs are built — not 3, not 5."""
        mock_request.return_value = ORDER_PLACED_RESPONSE
        client.place_iron_condor(
            "SPY", EXPIRY, 535, 540, 570, 575, price=2.00
        )
        payload = mock_request.call_args[1]["data"]
        leg_indices = {k.split("[")[1].rstrip("]") for k in payload if k.startswith("option_symbol[")}
        assert leg_indices == {"0", "1", "2", "3"}

    def test_iron_condor_without_price(self, client):
        """credit type without price should raise."""
        with pytest.raises(ValueError, match="price is required"):
            client.place_iron_condor(
                "SPY", EXPIRY, 535, 540, 570, 575,
                order_type="credit", price=None,
            )

    def test_iron_condor_strike_ordering_in_symbols(self, mock_request, client):
        """Put strikes lower, call strikes higher — verify OCC symbols correct."""
        mock_request.return_value = ORDER_PLACED_RESPONSE
        client.place_iron_condor(
            "SPY", EXPIRY, 530, 535, 565, 570, price=2.50
        )
        payload = mock_request.call_args[1]["data"]
        parsed_legs = [
            parse_option_symbol(payload[f"option_symbol[{i}]"]) for i in range(4)
        ]
        # First two legs are puts
        assert parsed_legs[0]["option_type"] == "P"
        assert parsed_legs[1]["option_type"] == "P"
        # Last two are calls
        assert parsed_legs[2]["option_type"] == "C"
        assert parsed_legs[3]["option_type"] == "C"
        # Put buy < put sell
        assert parsed_legs[0]["strike"] < parsed_legs[1]["strike"]
        # Call sell < call buy
        assert parsed_legs[2]["strike"] < parsed_legs[3]["strike"]


# ==============================================================================
# CREDIT SPREAD
# ==============================================================================

class TestCreditSpread:
    """Tests for place_credit_spread()."""

    def test_bull_put_spread(self, mock_request, client):
        """Sell higher P, buy lower P → bull put credit spread."""
        mock_request.return_value = ORDER_PLACED_RESPONSE
        client.place_credit_spread(
            symbol="SPY",
            expiration=EXPIRY,
            sell_strike=540.0,
            buy_strike=535.0,
            option_type="P",
            quantity=1,
            price=1.50,
        )
        payload = mock_request.call_args[1]["data"]
        assert payload["class"] == "multileg"
        assert payload["type"] == "credit"
        # Leg 0 = short (sell_to_open), Leg 1 = long (buy_to_open)
        assert payload["side[0]"] == "sell_to_open"
        assert payload["side[1]"] == "buy_to_open"

    def test_bear_call_spread(self, mock_request, client):
        """Sell lower C, buy higher C → bear call credit spread."""
        mock_request.return_value = ORDER_PLACED_RESPONSE
        client.place_credit_spread(
            symbol="SPY",
            expiration=EXPIRY,
            sell_strike=570.0,
            buy_strike=575.0,
            option_type="C",
            quantity=1,
            price=1.20,
        )
        payload = mock_request.call_args[1]["data"]
        sell_sym = parse_option_symbol(payload["option_symbol[0]"])
        buy_sym = parse_option_symbol(payload["option_symbol[1]"])
        assert sell_sym["option_type"] == "C"
        assert buy_sym["option_type"] == "C"


# ==============================================================================
# GET ALL ORDERS
# ==============================================================================

class TestGetOrders:
    def test_get_orders_returns_list(self, mock_request, client):
        mock_request.return_value = {
            "orders": {
                "order": [
                    {"id": 1001, "status": "open"},
                    {"id": 1002, "status": "filled"},
                ]
            }
        }
        result = client.get_orders()
        assert "orders" in result
        assert mock_request.call_args[0][0] == "GET"
        assert "orders" in mock_request.call_args[0][1]

    def test_get_orders_correct_account(self, mock_request, client):
        mock_request.return_value = {"orders": {}}
        client.get_orders()
        assert FAKE_ACCOUNT in mock_request.call_args[0][1]


# ==============================================================================
# OPTION CHAIN WITH GREEKS
# ==============================================================================

class TestOptionChainWithGreeks:
    """Tests for get_option_chain_with_greeks and _parse_greeks_from_chain."""

    def _chain_response(self, n_options: int = 2) -> Dict[str, Any]:
        options = [
            {
                "symbol": f"SPY260320C{str(560 + i * 5).zfill(8)}000",
                "underlying": "SPY",
                "strike": 560.0 + i * 5,
                "expiration_date": "2026-03-20",
                "option_type": "call",
                "bid": 2.40 + i * 0.10,
                "ask": 2.60 + i * 0.10,
                "last": 2.50 + i * 0.10,
                "volume": 100 + i * 50,
                "open_interest": 1000 + i * 200,
                "greeks": {
                    "delta": 0.45 - i * 0.05,
                    "gamma": 0.02,
                    "theta": -0.05,
                    "vega": 0.10,
                    "rho": 0.01,
                    "mid_iv": 0.18 + i * 0.01,
                },
                "in_the_money": False,
            }
            for i in range(n_options)
        ]
        return {"options": {"option": options}}

    def test_returns_list_of_greek_data(self, mock_request, client):
        mock_request.return_value = self._chain_response(3)
        result = client.get_option_chain_with_greeks("SPY", EXPIRY)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(g, GreekData) for g in result)

    def test_greeks_parsed_correctly(self, mock_request, client):
        mock_request.return_value = self._chain_response(1)
        result = client.get_option_chain_with_greeks("SPY", EXPIRY)
        g = result[0]
        assert g.delta == pytest.approx(0.45)
        assert g.gamma == pytest.approx(0.02)
        assert g.theta == pytest.approx(-0.05)
        assert g.vega == pytest.approx(0.10)
        assert g.bid == pytest.approx(2.40)
        assert g.ask == pytest.approx(2.60)

    def test_mid_computed_from_bid_ask(self, mock_request, client):
        mock_request.return_value = self._chain_response(1)
        result = client.get_option_chain_with_greeks("SPY", EXPIRY)
        g = result[0]
        assert g.mid == pytest.approx((g.bid + g.ask) / 2, abs=0.01)

    def test_single_option_dict_coerced_to_list(self, client):
        """Tradier sometimes returns a single option as a dict, not a list."""
        single_option = {
            "options": {
                "option": {  # dict, not list
                    "symbol": "SPY260320C00560000",
                    "underlying": "SPY",
                    "strike": 560.0,
                    "expiration_date": "2026-03-20",
                    "option_type": "call",
                    "bid": 2.40,
                    "ask": 2.60,
                    "last": 2.50,
                    "volume": 100,
                    "open_interest": 1000,
                    "greeks": {
                        "delta": 0.45, "gamma": 0.02, "theta": -0.05,
                        "vega": 0.10, "rho": 0.01, "mid_iv": 0.18,
                    },
                    "in_the_money": False,
                }
            }
        }
        with patch.object(client, "_make_request", return_value=single_option):
            result = client.get_option_chain_with_greeks("SPY", EXPIRY)
        assert len(result) == 1

    def test_empty_chain_returns_empty_list(self, mock_request, client):
        mock_request.return_value = {"options": {}}
        result = client.get_option_chain_with_greeks("SPY", EXPIRY)
        assert result == []

    def test_option_type_filter_passed_to_api(self, mock_request, client):
        mock_request.return_value = self._chain_response(1)
        client.get_option_chain_with_greeks("SPY", EXPIRY, option_type="call")
        params = mock_request.call_args[1]["params"]
        assert params.get("option_type") == "call"

    def test_no_option_type_filter_omits_param(self, mock_request, client):
        mock_request.return_value = self._chain_response(1)
        client.get_option_chain_with_greeks("SPY", EXPIRY)
        params = mock_request.call_args[1]["params"]
        assert "option_type" not in params

    def test_underlying_tagged_on_each_option(self, mock_request, client):
        mock_request.return_value = self._chain_response(2)
        result = client.get_option_chain_with_greeks("SPY", EXPIRY)
        assert all(g.underlying == "SPY" for g in result)


# ==============================================================================
# ERROR HANDLING — ORDER PATHS
# ==============================================================================

class TestOrderErrorHandling:
    """Error propagation tests specific to order endpoints."""

    def test_place_order_auth_failure(self, mock_request, client):
        mock_request.side_effect = TradierAuthenticationError("401 Unauthorized")
        with pytest.raises(TradierAuthenticationError):
            client.place_order("SPY", OrderSide.BUY, 10, order_class=OrderClass.EQUITY)

    def test_place_order_validation_failure(self, mock_request, client):
        mock_request.side_effect = TradierValidationError("400 Bad Request")
        with pytest.raises(TradierValidationError):
            client.place_order("SPY", OrderSide.BUY, 10, order_class=OrderClass.EQUITY)

    def test_cancel_order_not_found(self, mock_request, client):
        mock_request.side_effect = TradierAPIError("404 Not Found")
        with pytest.raises(TradierAPIError):
            client.cancel_order(999999)

    def test_modify_order_fills_before_modify(self, mock_request, client):
        """If order filled before modify arrives, API returns validation error."""
        mock_request.side_effect = TradierValidationError("Order already filled")
        with pytest.raises(TradierValidationError):
            client.modify_order(999001, price=2.10)


# ==============================================================================
# ASYNC ORDER PATHS
# ==============================================================================

class TestAsyncOrderPaths:
    """Tests for async wrappers (place_order_async, cancel_order_async)."""

    def test_place_order_async(self, client):
        async def _run():
            with patch.object(
                client, "_make_request", return_value=ORDER_PLACED_RESPONSE
            ):
                result = await client.place_order_async(
                    symbol=build_option_symbol("SPY", EXPIRY, "C", 560.0),
                    side=OrderSide.BUY_TO_OPEN,
                    quantity=1,
                    order_type=OrderType.LIMIT,
                    limit_price=2.50,
                    order_class=OrderClass.OPTION,
                )
                assert result["order"]["id"] == 999001

        asyncio.run(_run())

    def test_cancel_order_async(self, client):
        async def _run():
            with patch.object(
                client, "_make_request", return_value=CANCEL_RESPONSE
            ):
                result = await client.cancel_order_async(999001)
                assert result["order"]["status"] == "canceled"

        asyncio.run(_run())

    def test_place_order_async_propagates_auth_error(self, client):
        async def _run():
            with patch.object(
                client,
                "_make_request",
                side_effect=TradierAuthenticationError("401"),
            ):
                with pytest.raises(TradierAuthenticationError):
                    await client.place_order_async(
                        symbol="SPY",
                        side=OrderSide.BUY,
                        quantity=10,
                    )

        asyncio.run(_run())


# ==============================================================================
# OPTION LEG DATACLASS
# ==============================================================================

class TestOptionLegDataclass:
    def test_option_leg_fields(self):
        sym = build_option_symbol("SPY", EXPIRY, "C", 560.0)
        leg = OptionLeg(option_symbol=sym, side=OrderSide.SELL_TO_OPEN, quantity=2)
        assert leg.option_symbol == sym
        assert leg.side == OrderSide.SELL_TO_OPEN
        assert leg.quantity == 2

    def test_option_leg_equality(self):
        sym = "SPY260320C00560000"
        leg1 = OptionLeg(sym, OrderSide.BUY_TO_OPEN, 1)
        leg2 = OptionLeg(sym, OrderSide.BUY_TO_OPEN, 1)
        assert leg1 == leg2
