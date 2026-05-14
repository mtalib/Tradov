#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB06_DashboardOrderManager.py
Purpose: Dashboard-facing order management (audit §5 extraction)

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-16

Module Description:
    Extracted from SpyderG05_TradingDashboard per the 2026-04-15
    separation-of-concerns audit (§5):

        "_fetch_pending_orders, _cancel_orders, _refresh_positions […]  
         directly hits client.get_orders(), client.get_positions(),  
         client.cancel_order(). Parses the nested Tradier response shape  
         inside the GUI. Should live in a broker-facing adapter."

    DashboardOrderManager owns:
      - Fetching pending/open orders from Tradier.
      - Cancelling orders (single or batch).
      - Fetching open positions.
      - Building OCC option symbols and submitting multileg close orders.

    The GUI (SpyderG05) calls these methods and receives plain Python data
    structures or raises typed exceptions.  No Qt imports live here.
"""  # noqa: W291

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging  # noqa: F401
import os  # noqa: F401
from datetime import UTC, datetime

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

try:
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
        OptionLeg,
        OrderDuration,
        OrderSide,
        TradierAPIError,
        TradierClient,
        TradingEnvironment,
        build_option_symbol,
        create_tradier_client_from_env,
    )
    TRADIER_AVAILABLE = True
except ImportError:
    TradierClient = None  # type: ignore
    TradierAPIError = Exception  # type: ignore
    OptionLeg = None  # type: ignore
    OrderSide = None  # type: ignore
    OrderDuration = None  # type: ignore
    build_option_symbol = None  # type: ignore
    TradingEnvironment = None  # type: ignore
    create_tradier_client_from_env = None  # type: ignore
    TRADIER_AVAILABLE = False

logger = SpyderLogger.get_logger(__name__)

# Status strings Tradier considers "pending"
_PENDING_STATUSES = {"open", "partially_filled", "pending"}


# ==============================================================================
# HELPER
# ==============================================================================

def _get_client_for_env(
    existing_client: "TradierClient | None",
    use_live: bool,
) -> "TradierClient | None":
    """Return a usable TradierClient.

    Re-uses *existing_client* when already provided; otherwise attempts lazy
    creation from environment variables.

    Args:
        existing_client: Already-constructed client, or None.
        use_live:        True → LIVE environment, False → retained for
                         backwards compatibility but still resolves to LIVE
                         under current policy.

    Returns:
        A TradierClient instance, or None when Tradier is unavailable or env
        vars are missing.
    """
    if not TRADIER_AVAILABLE or create_tradier_client_from_env is None:
        return None
    if existing_client is not None:
        return existing_client
    env = TradingEnvironment.LIVE
    try:
        return create_tradier_client_from_env(environment=env)
    except Exception as exc:
        logger.warning("Could not create Tradier client: %s", exc)
        return None


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class DashboardOrderManager:
    """Broker-layer facade for order and position operations.

    Owns all Tradier API calls related to orders and positions so that the
    dashboard layer never touches the client directly.

    Args:
        client:   An already-constructed TradierClient, or None.  When None
                  the manager will attempt lazy creation from env vars on the
                  first call that needs a client.
        use_live: Whether to target the LIVE endpoint when creating a client
                  lazily. False is retained for backwards compatibility but
                  still resolves to LIVE under current policy.
    """

    def __init__(
        self,
        client: "TradierClient | None" = None,
        use_live: bool = True,
    ) -> None:
        self._client = client
        self._use_live = use_live

    # ------------------------------------------------------------------
    # CLIENT ACCESS
    # ------------------------------------------------------------------

    def set_client(self, client: "TradierClient | None") -> None:
        """Replace the underlying TradierClient (e.g. when mode switches)."""
        self._client = client

    def set_live(self, use_live: bool) -> None:
        """Set lazy client policy; sandbox selection is disabled."""
        self._use_live = use_live

    def _client_or_none(self) -> "TradierClient | None":
        client = _get_client_for_env(self._client, self._use_live)
        if client is not None:
            self._client = client  # cache for re-use
        return client

    # ------------------------------------------------------------------
    # ORDER FETCHING
    # ------------------------------------------------------------------

    def fetch_pending_orders(self) -> list[dict]:
        """Fetch open/pending orders from Tradier.

        Returns:
            List of raw Tradier order dicts whose status is in
            {open, partially_filled, pending}.  Empty list on any failure.
        """
        client = self._client_or_none()
        if not client:
            return []
        try:
            response = client.get_orders()
            orders_node = response.get("orders")
            if not orders_node or orders_node == "null":
                return []
            order_list = orders_node.get("order", [])
            if isinstance(order_list, dict):
                order_list = [order_list]
            return [o for o in order_list if o.get("status", "").lower() in _PENDING_STATUSES]
        except Exception as exc:
            logger.warning("Could not fetch orders from Tradier: %s", exc)
            return []

    # ------------------------------------------------------------------
    # ORDER CANCELLATION
    # ------------------------------------------------------------------

    def cancel_orders(self, orders: list[dict]) -> tuple[int, int]:
        """Cancel each order in *orders* via Tradier.

        Args:
            orders: List of Tradier order dicts (must have 'id' key).

        Returns:
            Tuple of (success_count, fail_count).
        """
        client = self._client_or_none()
        if not client:
            return 0, len(orders)
        success = fail = 0
        for order in orders:
            try:
                order_id = int(order.get("id", 0))
                if order_id:
                    client.cancel_order(order_id)
                    success += 1
                    logger.info("Cancelled order #%d", order_id)
                else:
                    fail += 1
                    logger.warning("Order dict missing id: %s", order)
            except Exception as exc:
                fail += 1
                logger.warning("Failed to cancel order #%s: %s", order.get("id"), exc)
        return success, fail

    def cancel_order_by_id(self, order_id: int) -> None:
        """Cancel a single order by Tradier order ID.

        Args:
            order_id: Tradier order ID to cancel.

        Raises:
            RuntimeError: If no Tradier client is available.
            TradierAPIError: Propagated from the client on API-level errors.
        """
        client = self._client_or_none()
        if not client:
            raise RuntimeError("No Tradier client available")
        client.cancel_order(order_id)
        logger.info("Cancelled order #%d", order_id)

    # ------------------------------------------------------------------
    # POSITION FETCHING
    # ------------------------------------------------------------------

    def fetch_orders_and_positions(self) -> dict:
        """Fetch pending orders and open positions in one call.

        Returns:
            Dict with keys 'pending_orders' (list[dict]) and
            'open_positions' (list[dict]).  Both empty on failure.
        """
        client = self._client_or_none()
        if not client:
            return {"pending_orders": [], "open_positions": []}

        pending_orders: list[dict] = []
        open_positions: list[dict] = []

        try:
            orders_resp = client.get_orders()
            orders_node = orders_resp.get("orders")
            if orders_node and orders_node != "null":
                order_list = orders_node.get("order", [])
                if isinstance(order_list, dict):
                    order_list = [order_list]
                pending_orders = [
                    o for o in order_list
                    if o.get("status", "").lower() in _PENDING_STATUSES
                ]
        except Exception as exc:
            logger.warning("Could not fetch orders: %s", exc)

        try:
            pos_resp = client.get_positions()
            pos_node = pos_resp.get("positions")
            if pos_node and pos_node != "null":
                pos_list = pos_node.get("position", [])
                if isinstance(pos_list, dict):
                    pos_list = [pos_list]
                open_positions = list(pos_list)
        except Exception as exc:
            logger.warning("Could not fetch positions: %s", exc)

        return {"pending_orders": pending_orders, "open_positions": open_positions}

    # ------------------------------------------------------------------
    # STRATEGY CLOSE (MULTILEG)
    # ------------------------------------------------------------------

    def build_close_legs(
        self,
        legs_data: list[dict],
    ) -> list["OptionLeg"]:
        """Parse UI leg dicts into OptionLeg objects for place_multileg_order.

        Leg dict keys expected:
            leg    — e.g. "Sell Put" or "Buy Call"
            strike — e.g. "$580P" or "$600C"
            cntr   — e.g. "10"
            expiry — e.g. "03/07" (MM/DD; year inferred from current date)

        Args:
            legs_data: List of leg dicts from the strategy tree widget.

        Returns:
            List of OptionLeg objects (close side is the inverse of open side).

        Raises:
            ValueError: On any parsing failure (invalid quantity, bad strike, etc.).
        """
        if OptionLeg is None or build_option_symbol is None:
            raise RuntimeError("TradierClient module is unavailable")

        current_year = datetime.now(UTC).year
        current_month = datetime.now(UTC).month
        option_legs: list = []

        for leg_dict in legs_data:
            leg_label: str = leg_dict["leg"]
            strike_raw: str = leg_dict["strike"]
            cntr_raw: str = leg_dict["cntr"]
            expiry_raw: str = leg_dict["expiry"]

            # --- Validate quantity ---
            try:
                quantity = int(cntr_raw.strip())
            except ValueError:
                raise ValueError(
                    f"Invalid contract count '{cntr_raw}' for leg '{leg_label}'"
                ) from None
            if quantity <= 0:
                raise ValueError(
                    f"Contract count must be positive, got {quantity} for leg '{leg_label}'"
                )

            # --- Parse strike: strip leading "$", trailing C/P ---
            clean_strike = strike_raw.lstrip("$")
            if not clean_strike:
                raise ValueError(f"Empty strike value for leg '{leg_label}'")
            opt_type_char = clean_strike[-1].upper()
            if opt_type_char not in ("C", "P"):
                raise ValueError(
                    f"Cannot determine option type from strike '{strike_raw}' "
                    f"for leg '{leg_label}'; expected trailing 'C' or 'P'"
                )
            try:
                strike_price = float(clean_strike[:-1])
            except ValueError:
                raise ValueError(
                    f"Cannot parse strike price from '{strike_raw}' for leg '{leg_label}'"
                ) from None

            # --- Parse expiry: MM/DD → YYYY-MM-DD (roll to next year if past) ---
            exp_parts = expiry_raw.strip().split("/")
            if len(exp_parts) != 2:
                raise ValueError(
                    f"Unexpected expiry format '{expiry_raw}' for leg '{leg_label}'; "
                    "expected MM/DD"
                )
            exp_month, exp_day = int(exp_parts[0]), int(exp_parts[1])
            exp_year = current_year
            if exp_month < current_month:
                exp_year += 1
            expiration_str = f"{exp_year}-{exp_month:02d}-{exp_day:02d}"

            # --- Determine close side (inverse of open side) ---
            leg_lower = leg_label.lower()
            if leg_lower.startswith("sell"):
                close_side = OrderSide.BUY_TO_CLOSE
            elif leg_lower.startswith("buy"):
                close_side = OrderSide.SELL_TO_CLOSE
            else:
                raise ValueError(
                    f"Cannot determine order side from leg label '{leg_label}'; "
                    "expected label beginning with 'Sell' or 'Buy'"
                )

            # --- Build OCC option symbol ---
            occ_symbol = build_option_symbol(
                "SPY", expiration_str, opt_type_char, strike_price,
            )
            option_legs.append(OptionLeg(
                option_symbol=occ_symbol,
                side=close_side,
                quantity=quantity,
            ))

        return option_legs

    def submit_multileg_close(
        self,
        strategy_name: str,
        legs_data: list[dict],
    ) -> dict:
        """Build option legs and submit a market close order to Tradier.

        Args:
            strategy_name: Human-readable strategy label (for logging).
            legs_data:     List of UI leg dicts — see build_close_legs().

        Returns:
            The raw Tradier API response dict.

        Raises:
            RuntimeError:   When Tradier module is unavailable or no client can
                            be created.
            ValueError:     On leg-parsing failures (invalid quantity, strike, etc.).
            TradierAPIError: Propagated from the client on API-level errors.
        """
        client = self._client_or_none()
        if not client:
            raise RuntimeError("No Tradier client available for order submission")

        option_legs = self.build_close_legs(legs_data)

        logger.info(
            "Submitting market close for '%s' (%d legs)", strategy_name, len(option_legs)
        )
        response = client.place_multileg_order(
            symbol="SPY",
            legs=option_legs,
            order_type="market",
            duration=OrderDuration.DAY,
        )
        order_id = (
            response.get("order", {}).get("id")
            or response.get("id")
        )
        logger.info(
            "Close order submitted for '%s': order_id=%s", strategy_name, order_id
        )
        return response
