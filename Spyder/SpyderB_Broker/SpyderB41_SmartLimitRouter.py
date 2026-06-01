#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB41_SmartLimitRouter.py
Purpose: Smart limit routing helper for SPX/SPXW multileg entries.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class SmartLimitRouter:
    """Walk a multileg credit order from near-mid toward bid, then abandon."""

    def __init__(
        self,
        *,
        step: float = 0.05,
        step_interval_s: float = 5.0,
        max_walk_s: float = 30.0,
        poll_interval_s: float = 1.0,
    ) -> None:
        self.step = step
        self.step_interval_s = step_interval_s
        self.max_walk_s = max_walk_s
        self.poll_interval_s = poll_interval_s

    def work_credit_order(
        self,
        *,
        submit_fn: Callable[[float], dict[str, Any]],
        modify_fn: Callable[[int, float], dict[str, Any]],
        cancel_fn: Callable[[int], Any],
        poll_fn: Callable[[int], tuple[str, float | None]],
        mid_credit: float,
        log_fn: Callable[[str], None],
    ) -> tuple[int | None, bool, float]:
        """Return (order_id, filled, fill_price)."""

        asked = round(mid_credit + 0.01, 2)
        order = submit_fn(asked)
        order_id_raw = order.get("id")
        if order_id_raw is None:
            log_fn("SmartLimitRouter: submit returned no order id.")
            return None, False, asked

        order_id = int(order_id_raw)
        deadline = time.monotonic() + self.max_walk_s
        next_step = time.monotonic() + self.step_interval_s

        while time.monotonic() < deadline:
            status, fill = poll_fn(order_id)
            if status == "filled":
                return order_id, True, (fill if fill is not None else asked)
            if status in {"canceled", "rejected", "expired"}:
                log_fn(f"SmartLimitRouter: order {order_id} ended as {status}.")
                return order_id, False, asked

            if time.monotonic() >= next_step:
                asked = round(max(asked - self.step, 0.05), 2)
                try:
                    modify_fn(order_id, asked)
                    log_fn(f"SmartLimitRouter: walking order {order_id} to {asked:.2f}")
                except Exception as exc:  # noqa: BLE001
                    log_fn(f"SmartLimitRouter: modify failed for {order_id}: {exc}")
                next_step = time.monotonic() + self.step_interval_s

            time.sleep(self.poll_interval_s)

        try:
            cancel_fn(order_id)
        except Exception:  # noqa: BLE001
            pass
        return order_id, False, asked
