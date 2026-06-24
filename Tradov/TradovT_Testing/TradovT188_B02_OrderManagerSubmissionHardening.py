from __future__ import annotations

from Tradov.TradovB_Broker.TradovB02_OrderManager import (
    Order,
    OrderManager,
    OrderState,
    SecurityType,
)
from Tradov.TradovB_Broker.TradovB40_TradierClient import TradingEnvironment


class _FakeTradier:
    def __init__(
        self,
        *,
        response=None,
        error=None,
        cancel_error=None,
        modify_error=None,
        orders_response=None,
        order_response=None,
    ):
        self.response = response or {"order": {"id": 12345}}
        self.error = error
        self.cancel_error = cancel_error if cancel_error is not None else error
        self.modify_error = modify_error if modify_error is not None else error
        self.orders_response = orders_response or {"orders": {"order": []}}
        self.order_response = order_response or {"order": {"id": 12345, "status": "open"}}
        self.environment = TradingEnvironment.LIVE
        self.place_order_calls = []
        self.place_multileg_calls = []
        self.get_order_calls = []

    def place_order(self, **kwargs):
        self.place_order_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response

    def place_multileg_order(self, **kwargs):
        self.place_multileg_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response

    def cancel_order(self, order_id):
        if self.cancel_error is not None:
            raise self.cancel_error
        return {"cancel": {"id": order_id}}

    def modify_order(self, **kwargs):
        if self.modify_error is not None:
            raise self.modify_error
        return {"order": {"id": kwargs.get("order_id", 0)}}

    def get_orders(self):
        return self.orders_response

    def get_order(self, order_id):
        self.get_order_calls.append(order_id)
        return self.order_response


def test_single_leg_order_persists_and_routes_caller_tag():
    broker = _FakeTradier(response={"order": {"id": 987}})
    manager = OrderManager(tradier_client=broker)
    order = Order(
        symbol="SPY",
        side="buy",
        quantity=1,
        security_type=SecurityType.EQUITY,
        tag="caller-tag-1",
    )

    result = manager.submit_order(order)

    assert result.success is True
    assert result.tradier_order_id == 987
    assert broker.place_order_calls[0]["tag"] == "caller-tag-1"
    assert manager._orders[order.order_id].tag == "caller-tag-1"
    assert manager._orders[order.order_id].state is OrderState.OPEN
    assert order.order_id not in manager._pending_submissions


def test_single_leg_order_generates_local_tag_before_route():
    broker = _FakeTradier()
    manager = OrderManager(tradier_client=broker)
    order = Order(symbol="SPY", side="buy", quantity=1, security_type=SecurityType.EQUITY)

    result = manager.submit_order(order)

    assert result.success is True
    assert order.tag
    assert broker.place_order_calls[0]["tag"] == order.tag


def test_submission_without_broker_id_clears_pending_and_rejects():
    broker = _FakeTradier(response={"order": {}})
    manager = OrderManager(tradier_client=broker)
    order = Order(symbol="SPY", side="buy", quantity=1, security_type=SecurityType.EQUITY)

    result = manager.submit_order(order)

    assert result.success is False
    assert manager._orders[order.order_id].state is OrderState.REJECTED
    assert order.order_id not in manager._pending_submissions


def test_timeout_reconciles_by_tag_before_rejecting():
    broker = _FakeTradier(
        error=TimeoutError("timed out"),
        orders_response={"orders": {"order": {"id": 7788, "tag": "known-tag"}}},
    )
    manager = OrderManager(tradier_client=broker)
    order = Order(
        symbol="SPY",
        side="buy",
        quantity=1,
        security_type=SecurityType.EQUITY,
        tag="known-tag",
    )

    result = manager.submit_order(order)

    assert result.success is True
    assert result.tradier_order_id == 7788
    assert manager._orders[order.order_id].state is OrderState.OPEN
    assert order.order_id not in manager._pending_submissions


def test_cancel_timeout_reconciles_cancelled_broker_state():
    broker = _FakeTradier(
        cancel_error=TimeoutError("timed out"),
        order_response={"order": {"id": 991, "status": "cancelled"}},
    )
    manager = OrderManager(tradier_client=broker)
    order = Order(
        symbol="SPY",
        side="buy",
        quantity=1,
        security_type=SecurityType.EQUITY,
    )
    manager._orders[order.order_id] = order
    order.tradier_order_id = 991
    order.state = OrderState.OPEN

    result = manager.cancel_order(order.order_id)

    assert result.success is True
    assert result.operation == "cancel"
    assert broker.get_order_calls == [order.tradier_order_id]
    assert manager._orders[order.order_id].state is OrderState.CANCELLED


def test_modify_timeout_returns_structured_failure():
    broker = _FakeTradier(error=TimeoutError("timed out"))
    manager = OrderManager(tradier_client=broker)
    order = Order(
        symbol="SPY",
        side="buy",
        quantity=1,
        security_type=SecurityType.EQUITY,
    )
    manager._orders[order.order_id] = order
    order.tradier_order_id = 992
    order.state = OrderState.OPEN

    result = manager.modify_order(order.order_id, price=101.25)

    assert result.success is False
    assert result.error_code == "MODIFY_FAILED"
    assert broker.get_order_calls == [order.tradier_order_id]
    assert manager._orders[order.order_id].warning_message == "timed out"
