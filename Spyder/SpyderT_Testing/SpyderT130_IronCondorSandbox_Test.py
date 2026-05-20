#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT130_IronCondorSandbox_Test.py
Purpose: End-to-end Iron Condor order placement test against the Tradier sandbox

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-04-14 Time: 20:56:00

End-to-end test that confirms the order-placement pipeline works against the
Tradier SANDBOX account.

Steps
-----
1. Connect to Tradier sandbox using .env credentials.
2. Fetch live SPY quote to find current price.
3. Fetch nearest weekly SPY expiration.
4. Fetch the options chain and pick 4 strikes for a standard Iron Condor:
       ~ -16Δ put spread  |  ~ +16Δ call spread   (width = 5 pts each wing)
5. Preview the order (dry-run, no fill, no capital consumed).
6. Optionally place the live sandbox order when --place flag supplied.

Usage
-----
  # Preview only (safe, default):
  python Spyder/SpyderT_Testing/SpyderT130_IronCondorSandbox_Test.py

  # Submit to Tradier sandbox account:
  python Spyder/SpyderT_Testing/SpyderT130_IronCondorSandbox_Test.py --place

  # Submit to the LIVE Tradier account (real money — use with extreme caution):
  python Spyder/SpyderT_Testing/SpyderT130_IronCondorSandbox_Test.py --place --force-live

Requirements
------------
  - .env must contain TRADIER_API_KEY and TRADIER_ACCOUNT_ID
  - TRADIER_ENVIRONMENT must be "sandbox" (or absent — defaults to sandbox)
  - .venv must be active
"""

import argparse
import os
import sys
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.manual  # Interactive CLI sandbox — excluded from CI

# ---------------------------------------------------------------------------
# Path setup — allow running from repo root or SpyderT_Testing/
# ---------------------------------------------------------------------------
# The file lives at <project_root>/Spyder/SpyderT_Testing/<file>.py so we
# need 3 dirname levels to reach <project_root> where the `Spyder` package
# directory lives.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=True)
except ImportError:
    pass  # python-dotenv not installed; rely on shell env

from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
    TradierClient,
    TradierAPIError,
    TradingEnvironment,
    build_option_symbol,
    OrderDuration,
)

# ============================================================
# Helpers
# ============================================================

def _require_sandbox_for_place(client: TradierClient, force_live: bool) -> None:
    """Abort live order placement unless --force-live is explicitly supplied."""
    if client.environment not in (TradingEnvironment.SANDBOX, TradingEnvironment.PAPER):
        if not force_live:
            print(
                "[ABORT] TRADIER_ENVIRONMENT=live — placing a real order requires --force-live.\n"
                "        Use --force-live ONLY if you understand this submits a real order."
            )
            sys.exit(1)
        print(
            "[WARN]  --force-live is set. This order will be submitted to the LIVE Tradier account."
        )


def _nearest_friday(after: date | None = None) -> date:
    """Return the nearest upcoming Friday (or today if today is Friday)."""
    today = after or date.today()
    days_ahead = (4 - today.weekday()) % 7  # 4 = Friday
    if days_ahead == 0 and today.weekday() != 4:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def _get_spy_price(client: TradierClient) -> float:
    """Return the last SPY price from Tradier."""
    resp = client.get_quotes(["SPY"])
    quote = resp.get("quotes", {}).get("quote", {})
    price = float(quote.get("last") or quote.get("close") or 0.0)
    if not price:
        raise RuntimeError("Could not fetch SPY price from Tradier")
    return price


def _get_nearest_expiration(client: TradierClient, symbol: str) -> str:
    """Return the nearest available weekly expiration (YYYY-MM-DD)."""
    resp = client.get_option_expirations(symbol)
    dates = resp.get("expirations", {}).get("date", [])
    if not dates:
        raise RuntimeError("No expirations returned from Tradier")
    if isinstance(dates, str):
        dates = [dates]
    today = date.today()
    # Pick the first expiration that is at least 1 day away
    for d in sorted(dates):
        exp = date.fromisoformat(d)
        if exp > today:
            return d
    raise RuntimeError("No future expiration found")


def _pick_condor_strikes(
    client: TradierClient,
    symbol: str,
    expiration: str,
    spot: float,
    wing_width: float = 5.0,
    short_offset: float = 10.0,
) -> tuple[float, float, float, float]:
    """
    Pick 4 strikes for an Iron Condor centred on `spot`.

    Returns (put_buy, put_sell, call_sell, call_buy) — all rounded to the
    nearest available strike from the Tradier chain.

    Strategy:
      short_put  ≈ spot − short_offset     (sells downside premium)
      long_put   ≈ short_put − wing_width  (limits loss)
      short_call ≈ spot + short_offset
      long_call  ≈ short_call + wing_width
    """
    resp = client.get_option_strikes(symbol, expiration)
    strikes_raw = resp.get("strikes", {}).get("strike", [])
    if isinstance(strikes_raw, (int, float, str)):
        strikes_raw = [strikes_raw]
    available = sorted(float(s) for s in strikes_raw)

    if not available:
        raise RuntimeError("No strikes returned from Tradier")

    def nearest(target: float) -> float:
        return min(available, key=lambda s: abs(s - target))

    short_put  = nearest(spot - short_offset)
    long_put   = nearest(short_put - wing_width)
    short_call = nearest(spot + short_offset)
    long_call  = nearest(short_call + wing_width)

    return long_put, short_put, short_call, long_call


# ============================================================
# Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Paper Iron Condor order test")
    parser.add_argument(
        "--place",
        action="store_true",
        help="Submit the order to the sandbox account (default: preview only)",
    )
    parser.add_argument(
        "--wing-width", type=float, default=5.0,
        help="Strike width per wing in points (default: 5)",
    )
    parser.add_argument(
        "--short-offset", type=float, default=10.0,
        help="Distance from spot to short strikes in points (default: 10)",
    )
    parser.add_argument(
        "--price", type=float, default=None,
        help="Net credit limit price. If omitted, uses market order.",
    )
    parser.add_argument(
        "--force-live",
        action="store_true",
        help="Allow placing a real order when TRADIER_ENVIRONMENT=live (dangerous).",
    )
    args = parser.parse_args()

    # -- Credentials --------------------------------------------------------
    # Prefer dedicated sandbox keys; fall back to the generic TRADIER_API_KEY.
    sandbox_key  = os.environ.get("TRADIER_SANDBOX_API_KEY", "")
    sandbox_acct = os.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "")

    if sandbox_key and sandbox_acct:
        api_key    = sandbox_key
        account_id = sandbox_acct
        is_sandbox = True
    else:
        api_key    = os.environ.get("TRADIER_API_KEY", "")
        account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
        env_str    = os.environ.get("TRADIER_ENVIRONMENT", "sandbox").lower()
        is_sandbox = env_str in ("sandbox", "paper")

    if not api_key or not account_id:
        print("[ERROR] No Tradier credentials found in .env")
        sys.exit(1)

    environment = TradingEnvironment.SANDBOX if is_sandbox else TradingEnvironment.LIVE

    client = TradierClient(
        api_key=api_key,
        account_id=account_id,
        environment=environment,
    )
    env_label = "SANDBOX (sandbox.tradier.com)" if is_sandbox else "LIVE (api.tradier.com)"
    print(f"[INFO] Tradier environment: {env_label}")

    # -- Connection check ---------------------------------------------------
    print("=" * 60)
    print("  Spyder — Paper Iron Condor Test")
    print("=" * 60)
    ok = client.test_connection()
    if not ok:
        print("[ERROR] Tradier sandbox connection failed — check credentials")
        sys.exit(1)
    print("[OK]  Tradier sandbox connected")

    # -- Market data --------------------------------------------------------
    spot = _get_spy_price(client)
    print(f"[OK]  SPY last price: ${spot:.2f}")

    expiration = _get_nearest_expiration(client, "SPY")
    print(f"[OK]  Nearest expiration: {expiration}")

    put_buy, put_sell, call_sell, call_buy = _pick_condor_strikes(
        client, "SPY", expiration, spot,
        wing_width=args.wing_width,
        short_offset=args.short_offset,
    )
    print(
        f"[OK]  Iron Condor strikes: "
        f"P{put_buy:.0f}/{put_sell:.0f}  |  C{call_sell:.0f}/{call_buy:.0f}"
    )

    # Build human-readable symbols for inspection
    syms = {
        "Long put  (protection)": build_option_symbol("SPY", expiration, "P", put_buy),
        "Short put (premium)   ": build_option_symbol("SPY", expiration, "P", put_sell),
        "Short call (premium)  ": build_option_symbol("SPY", expiration, "C", call_sell),
        "Long call (protection)": build_option_symbol("SPY", expiration, "C", call_buy),
    }
    print("\nOption symbols:")
    for label, sym in syms.items():
        print(f"  {label}: {sym}")

    # -- Preview (dry-run) --------------------------------------------------
    order_type = "credit" if args.price is not None else "market"
    # Tradier's preview endpoint requires a price even for inspection.
    # Use the user-supplied price or fall back to $1.00 for the preview only.
    preview_price = args.price if args.price is not None else 1.00
    print(f"\nPreviewing Iron Condor (order_type=credit, preview_price=${preview_price:.2f}) ...")

    try:
        preview = client.preview_iron_condor(
            symbol="SPY",
            expiration=expiration,
            put_buy_strike=put_buy,
            put_sell_strike=put_sell,
            call_sell_strike=call_sell,
            call_buy_strike=call_buy,
            quantity=1,
            price=preview_price,
        )
        print("[OK]  Preview response:")
        import json
        print(json.dumps(preview, indent=2))
    except TradierAPIError as e:
        print(f"[WARN] Preview failed: {e}")
        print("       (Tradier sandbox sometimes rejects previews for illiquid chains.)")

    # -- Place order --------------------------------------------------------
    if not args.place:
        print("\n[INFO] Preview-only mode. Re-run with --place to submit the order.")
        if not is_sandbox:
            print("[INFO] To place on live account add --place --force-live (real money!).")
        return

    _require_sandbox_for_place(client, getattr(args, "force_live", False))
    print(f"\nPlacing Iron Condor order in {'SANDBOX' if is_sandbox else 'LIVE'} ...")
    try:
        result = client.place_iron_condor(
            symbol="SPY",
            expiration=expiration,
            put_buy_strike=put_buy,
            put_sell_strike=put_sell,
            call_sell_strike=call_sell,
            call_buy_strike=call_buy,
            quantity=1,
            order_type=order_type,
            price=args.price,
            duration=OrderDuration.DAY,
        )
        import json
        print("[OK]  Order placed! Response:")
        print(json.dumps(result, indent=2))

        order_id = result.get("order", {}).get("id")
        if order_id:
            print(f"\n[OK]  Order ID: {order_id}")
            # Fetch the order back to confirm it was recorded
            order_status = client.get_order(order_id)
            print("Order status:")
            print(json.dumps(order_status, indent=2))
    except TradierAPIError as e:
        print(f"[ERROR] Order placement failed: {e}")
        sys.exit(1)

    print("\n[DONE] Test complete.")


if __name__ == "__main__":
    main()
