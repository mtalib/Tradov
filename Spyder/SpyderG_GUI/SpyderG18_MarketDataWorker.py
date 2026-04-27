#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG18_MarketDataWorker.py
Purpose: Market data QThread worker (extracted from SpyderG05)

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-15

Module Description:
    QObject-based market data worker that runs on its own QThread and fans
    out Tradier quotes, account balances, option chain CPC computation,
    heartbeat status, and 5-minute SPY chart bars into Qt signals consumed
    by SpyderG05_TradingDashboard.

    Relocated from SpyderG05 per audit §1/§14/§23 so the dashboard layer no
    longer owns live-data fetch logic. Behavior, signal contract, JSON cache
    schema, and index-proxy math (UUP→DXY, QQQ×37.5 for IXIC, DIA×100 for
    $DJI) are preserved bit-for-bit — this is a mechanical relocation, not a
    MarketDataProtocol integration. Full protocol adoption is deferred until
    SpyderC00_MarketDataProtocol's contract can be validated end-to-end
    against a live feed in a GUI smoke test.

    This module is also the canonical home for the quote-freshness helpers
    (_coerce_epoch_ms, _freshest_quote_timestamp_ms, _freshest_live_data_timestamp,
    check_api_connection) and REALTIME_SENTINEL_SYMBOLS — G05 imports them
    back from here to avoid duplication.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import random
import threading
import time
from datetime import datetime
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import QObject, QMutex, QMutexLocker, QTimer, Signal, Slot

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import (
    TRADIER_CONNECT_TIME,
    LogThrottle,
    is_dashboard_session as _is_dashboard_session,
    is_tradier_active_window as is_tradier_window,
)


def is_market_hours(now_et: datetime | None = None) -> bool:
    """Return True only when ET time is in session and weekday is Mon-Fri."""
    eastern = pytz.timezone("US/Eastern")  # noqa: F821
    current_et = now_et or datetime.now(eastern)
    if current_et.weekday() >= 5:
        return False
    return bool(_is_dashboard_session(current_et))


try:
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
        TradierClient,
        TradingEnvironment,
    )
    TRADIER_AVAILABLE = True
except ImportError:
    TradierClient = None  # type: ignore
    TradingEnvironment = None  # type: ignore
    TRADIER_AVAILABLE = False

try:
    from Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker import (
        tradier_breaker as _tradier_breaker,
    )
    _circuit_breakers_available = True
except ImportError:
    _tradier_breaker = None  # type: ignore
    _circuit_breakers_available = False


logger = SpyderLogger.get_logger(__name__)


# ==============================================================================
# CONSTANTS
# ==============================================================================
HEARTBEAT_INTERVAL = 30000        # 30 seconds in milliseconds — check frequency
HEARTBEAT_WARNING_TIME = 20000    # 20 seconds before next check (blue heart)
HEARTBEAT_LOG_INTERVAL = 1800     # 30 minutes between "healthy" log messages

REALTIME_QUOTE_MAX_AGE_SECONDS = 45.0   # Survive 1-2 missed 10-s fast-fetch cycles + Tradier timeout  # noqa: E501
REALTIME_SENTINEL_SYMBOLS = ("SPY", "SPX", "QQQ")

# Options-chain fetch deduplication.
# The SPY chain is expensive (~200-400ms, Tradier rate-limited).  Multiple
# callers (heartbeat trigger + fast-fetch overlap, S07 options analytics) can
# request the chain within the same polling window.  We guard with:
#   _CHAIN_LOCK  — only one thread fetches at a time; others wait and read cache.
#   _CHAIN_CACHE — stores (contracts, put_vol, call_vol, expiry) with a TTL.
#   _CHAIN_TTL   — 30 s: safe margin between the ~60 s slow-fetch cycle.
_CHAIN_LOCK: threading.Lock = threading.Lock()
_CHAIN_TTL: float = 30.0
_CHAIN_CACHE: dict = {}  # keys: "contracts", "put_vol", "call_vol", "expiry", "ts"


def _get_cached_chain(
    client: "TradierClient",
) -> "tuple[list, float, float, str] | None":
    """Return (contracts, put_vol, call_vol, expiry) from cache or fresh fetch.

    Thread-safe: at most one thread fetches at a time; others block and then
    read the result that was written by the fetching thread.

    Returns:
        Tuple of (contracts, put_vol, call_vol, expiry_date_str), or None if
        the fetch fails or no valid expiry is found.
    """
    global _CHAIN_CACHE

    with _CHAIN_LOCK:
        # Serve from cache when fresh
        if _CHAIN_CACHE and (time.monotonic() - _CHAIN_CACHE.get("ts", 0.0)) < _CHAIN_TTL:
            return (
                _CHAIN_CACHE["contracts"],
                _CHAIN_CACHE["put_vol"],
                _CHAIN_CACHE["call_vol"],
                _CHAIN_CACHE["expiry"],
            )

        # Cache is stale — fetch fresh chain
        try:
            from datetime import date as _date2  # noqa: PLC0415
            exps_raw = client.get_option_expirations("SPY")
            exp_dates = exps_raw.get("expirations", {}).get("date", [])
            if isinstance(exp_dates, str):
                exp_dates = [exp_dates]
            target_exp = next(
                (d for d in exp_dates if d >= _date2.today().isoformat()),
                exp_dates[0] if exp_dates else None,
            )
            if not target_exp:
                return None
            chain_resp = client.get_option_chain("SPY", target_exp)
            contracts = chain_resp.get("options", {}).get("option", [])
            if isinstance(contracts, dict):
                contracts = [contracts]
            put_vol = sum(
                float(c.get("volume") or 0)
                for c in contracts if c.get("option_type") == "put"
            )
            call_vol = sum(
                float(c.get("volume") or 0)
                for c in contracts if c.get("option_type") == "call"
            )
            _CHAIN_CACHE = {
                "contracts": contracts,
                "put_vol": put_vol,
                "call_vol": call_vol,
                "expiry": target_exp,
                "ts": time.monotonic(),
            }
            return contracts, put_vol, call_vol, target_exp
        except Exception:
            return None

# Single canonical remap: Tradier symbol → dashboard widget key.
# §1c: Consolidated from two inline dicts that previously lived independently
# inside _fetch_live_data_from_tradier and _fetch_quotes_fast.
_SYMBOL_REMAP: dict[str, str] = {
    "UUP":   "DXY",   # Invesco USD ETF (~27) proxies DXY (~104) for display
    # NDX, RUT are already the correct widget key names — no remap needed.
    # $DJI confirmed ~15 min delayed on Tradier; DIA*100 used for display instead.
    # NOTE: VIX9D is now a first-class dashboard widget; it stores as "VIX9D" directly.
    # VXV (3-month CBOE vol) is fetched directly from Tradier; falls back to "---" if
    # unavailable on the current data subscription.
}


# ==============================================================================
# QUOTE-FRESHNESS HELPERS
# ==============================================================================
def _coerce_epoch_ms(value) -> int | None:
    """Return an integer epoch-millisecond value when possible."""
    if value in (None, ""):
        return None
    try:
        epoch_ms = int(value)
    except (TypeError, ValueError):
        return None
    return epoch_ms if epoch_ms > 0 else None


def _datetime_from_epoch_ms(value) -> datetime | None:
    """Convert epoch milliseconds to a naive local datetime for age checks."""
    epoch_ms = _coerce_epoch_ms(value)
    if epoch_ms is None:
        return None
    return datetime.fromtimestamp(epoch_ms / 1000)


def _freshest_quote_timestamp_ms(quote: dict) -> int | None:
    """Return the freshest market timestamp carried by a Tradier quote payload."""
    timestamps = [
        _coerce_epoch_ms(quote.get("trade_date")),
        _coerce_epoch_ms(quote.get("bid_date")),
        _coerce_epoch_ms(quote.get("ask_date")),
    ]
    valid = [ts for ts in timestamps if ts is not None]
    return max(valid) if valid else None


def _freshest_live_data_timestamp(live_data: dict) -> datetime | None:
    """Return the freshest timestamp from live data.

    Prefers the wall-clock fetch timestamp written by the worker on each
    successful Tradier call (``_fetch_time_ms``).  This decouples the
    REAL-TIME badge from Tradier's quote timestamps, which can legitimately
    lag behind in quiet markets even with a freshly fetched response.
    Falls back to sentinel-symbol quote timestamps for backward compatibility
    with data files that pre-date the ``_fetch_time_ms`` field.
    """
    # Wall-clock time of last successful Tradier fetch — most reliable indicator.
    fetch_time = _datetime_from_epoch_ms(live_data.get("_fetch_time_ms"))
    if fetch_time is not None:
        return fetch_time

    for symbol in REALTIME_SENTINEL_SYMBOLS:
        quote = live_data.get(symbol)
        if isinstance(quote, dict):
            quote_time = _datetime_from_epoch_ms(quote.get("timestamp_ms"))
            if quote_time is not None:
                return quote_time

    freshest: datetime | None = None
    for quote in live_data.values():
        if not isinstance(quote, dict):
            continue
        quote_time = _datetime_from_epoch_ms(quote.get("timestamp_ms"))
        if quote_time is not None and (freshest is None or quote_time > freshest):
            freshest = quote_time
    return freshest


def check_api_connection():
    """Check if Tradier API is reachable.

    Returns:
        Tuple of (connected: bool, mode: str)
    """
    try:
        if TRADIER_AVAILABLE:
            try:
                from dotenv import load_dotenv
                load_dotenv(override=True)
            except ImportError:
                pass
            api_key = os.environ.get("TRADIER_API_KEY", "")
            account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
            env = os.environ.get("TRADIER_ENVIRONMENT", "sandbox")

            if api_key and account_id:
                env_enum = (
                    TradingEnvironment.LIVE
                    if env.lower() == "live"
                    else TradingEnvironment.SANDBOX
                )
                client = TradierClient(
                    api_key=api_key,
                    account_id=account_id,
                    environment=env_enum,
                )
                if client.test_connection():
                    mode = "SANDBOX" if env.lower() != "live" else "LIVE"
                    return True, f"Tradier API ({mode})"

        return False, "Tradier API not configured"

    except Exception as e:
        return False, f"API check failed: {e}"


# ==============================================================================
# THREAD-SAFE MARKET DATA WORKER
# ==============================================================================
class ThreadSafeMarketDataWorker(QObject):
    """Thread-safe market data worker with real API connection detection and heartbeat monitoring"""

    data_updated = Signal(dict)
    connection_status_changed = Signal(bool, str)
    market_data_status_changed = Signal(str)
    error_occurred = Signal(str)
    heartbeat_received = Signal(str)
    heartbeat_status_changed = Signal(str)  # New signal for heartbeat status
    log_message = Signal(str)  # New signal for log messages
    balance_updated = Signal(float, float)  # (equity/settled, buying_power)
    fetch_requested = Signal()       # Trigger full live fetch from GUI thread safely
    fast_fetch_requested = Signal()  # Trigger lightweight quote-only refresh
    eod_snapshot_fetched = Signal(bool)  # True = real EOD prices written to live_data.json

    def __init__(self):
        super().__init__()
        self.logger = SpyderLogger.get_logger(__name__)

        # FIXED: Start with actual connection check instead of assuming connected
        self.api_connected = False

        self.market_data = {}
        self.data_mutex = QMutex()
        self.client_id = 0  # Dedicated client ID for the dashboard worker
        self.market_hours = is_market_hours()

        # Path to live market data file (shared with dashboard)
        self.data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"

        # Initialize timer references (will be created in start() method)
        self.update_timer = None
        self.market_hours_timer = None
        self.heartbeat_timer = None
        self.heartbeat_warning_timer = None

        self.last_data_update = {}
        self._healthy_log_throttle = LogThrottle(HEARTBEAT_LOG_INTERVAL)
        self._offline_log_throttle = LogThrottle(HEARTBEAT_LOG_INTERVAL)
        self._init_simulation_data()

        logger.info("🔧 Market Data Worker initialized with heartbeat monitoring")
        logger.info("📊 Market: %s", 'OPEN' if self.market_hours else 'CLOSED')

    def _heartbeat_check(self):
        """30-second heartbeat check for Tradier API connection"""
        # Stay quiet outside the 9:20 AM – 4:30 PM ET trading window
        if not is_tradier_window():
            if self.api_connected:
                # Transition to disconnected when window closes
                self.api_connected = False
                self.connection_status_changed.emit(False, "OUTSIDE TRADING HOURS")
                self.market_data_status_changed.emit("NONE")

            # Always signal offline so toolbar labels stay red
            self.heartbeat_status_changed.emit("offline")

            # Emit calm ❤️ message at startup and every 30 minutes thereafter
            if self._offline_log_throttle.should_emit():
                self.heartbeat_received.emit(
                    "❤️ Tradier inactive - outside market hours (9:20 AM – 4:30 PM ET)"
                )
            return

        try:
            # Check actual connection
            connected, mode = check_api_connection()
            previous_status = self.api_connected
            self.api_connected = connected

            # Emit heartbeat status based on connection
            if connected:
                self.heartbeat_status_changed.emit("connected")  # Green heart
                if not previous_status:
                    # Connection restored — first heartbeat of the day or reconnect
                    _is_sandbox = "SANDBOX" in mode.upper() or "PAPER" in mode.upper()
                    _mkt_status = "PAPER" if _is_sandbox else "LIVE"
                    self.connection_status_changed.emit(True, f"API CONNECTED ({mode})")
                    self.market_data_status_changed.emit(_mkt_status)
                    self.heartbeat_received.emit(
                        f"💚 Heartbeat: Tradier API connection restored ({mode})",
                    )
                else:
                    # Healthy status at most once per interval; failures fire immediately.
                    if self._healthy_log_throttle.should_emit():
                        self.heartbeat_received.emit(
                            f"💚 Heartbeat: Tradier API healthy ({mode})",
                        )
                # Reset offline throttle so next outside-hours period fires immediately
                self._offline_log_throttle.reset()
                # Emit the correct market data status every heartbeat so the label
                # switches from REAL-TIME to EOD promptly after 4:00 PM ET close.
                _mkt_open = is_market_hours()
                if _mkt_open:
                    _mkt_data_status = "PAPER" if ("SANDBOX" in mode.upper() or "PAPER" in mode.upper()) else "LIVE"  # noqa: E501
                else:
                    _mkt_data_status = "EOD"
                self.market_data_status_changed.emit(_mkt_data_status)
                # Health probe succeeded — let the breaker decide whether a
                # reset is warranted (policy lives inside U41 CircuitBreaker).
                if _circuit_breakers_available and _tradier_breaker is not None:
                    if _tradier_breaker.reset_if_open():
                        logger.info("🔄 Tradier circuit breaker auto-reset (API confirmed healthy)")
                # Refresh Tradier quotes every heartbeat (30 s) during market hours.
                # This keeps live_data.json fresh (→ EOD label transitions to REAL-TIME)
                # and rewrites spy_5min_chart.json (→ candlestick chart updates).
                if _mkt_open:
                    self.fetch_requested.emit()
            else:
                self.heartbeat_status_changed.emit("disconnected")  # Red heart
                if previous_status:
                    # Connection lost
                    self.connection_status_changed.emit(False, "API DISCONNECTED")
                    self.heartbeat_received.emit(
                        "💔 Heartbeat: Tradier API connection lost",
                    )
                else:
                    self.heartbeat_received.emit(
                        "💔 Heartbeat: Tradier API still disconnected",
                    )

            # Start warning timer for blue heart (10 seconds before next check)
            if self.heartbeat_warning_timer:
                self.heartbeat_warning_timer.start(HEARTBEAT_WARNING_TIME)

        except Exception as e:
            self.heartbeat_status_changed.emit("error")  # Red heart
            self.heartbeat_received.emit(f"💔 Heartbeat error: {e}")

    def _heartbeat_warning(self):
        """Show blue heart 20 seconds before next heartbeat check"""
        self.heartbeat_status_changed.emit("warning")  # Blue heart
        if self.heartbeat_warning_timer:
            self.heartbeat_warning_timer.stop()

    def _fetch_balance_only(self):
        """Fetch account balance from Tradier without touching quotes or market-hours guards.

        Called at startup (both inside and outside trading window) so the account
        section (SETTLED CASH, BUYING POWER) is populated as soon as credentials
        are available, regardless of whether the market is open.
        """
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
            if not TRADIER_AVAILABLE:
                return
            api_key = os.environ.get("TRADIER_API_KEY", "")
            account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
            env_str = os.environ.get("TRADIER_ENVIRONMENT", "sandbox")
            if not api_key or not account_id:
                return
            env_enum = (
                TradingEnvironment.LIVE
                if env_str.lower() == "live"
                else TradingEnvironment.SANDBOX
            )
            trading_mode = os.environ.get("TRADING_MODE", "paper").lower()

            # Prefer sandbox-specific creds in paper mode; fall back to main creds.
            if trading_mode == "paper":
                paper_key = os.environ.get("TRADIER_SANDBOX_API_KEY", "") or api_key
                paper_acct = os.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "") or account_id
                client = TradierClient(
                    api_key=paper_key,
                    account_id=paper_acct,
                    environment=TradingEnvironment.SANDBOX,
                )
            else:
                client = TradierClient(api_key=api_key, account_id=account_id, environment=env_enum)

            bal = client.get_account_balances()
            account_data = bal.get("balances", {})
            equity = float(account_data.get("total_equity") or 0)
            cash = float(account_data.get("total_cash") or 0)
            margin = account_data.get("margin", {})
            option_bp = float(
                margin.get("option_buying_power")
                or account_data.get("buying_power")
                or cash
            )
            # Always emit — even a zero balance is valid data (new account).
            self.balance_updated.emit(equity, option_bp)
        except Exception:
            pass

    def _fetch_live_data_from_tradier(self):
        """Fetch live quotes and account balance from Tradier, write to data_file."""
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
            if not TRADIER_AVAILABLE:
                return
            api_key = os.environ.get("TRADIER_API_KEY", "")
            account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
            env_str = os.environ.get("TRADIER_ENVIRONMENT", "sandbox")
            if not api_key or not account_id:
                return
            env_enum = (
                TradingEnvironment.LIVE
                if env_str.lower() == "live"
                else TradingEnvironment.SANDBOX
            )
            client = TradierClient(api_key=api_key, account_id=account_id, environment=env_enum)

            # --- Fetch account balance ---
            # Always fetch balance from the account that matches TRADING_MODE:
            #   paper → sandbox API with sandbox credentials (VA... account, $100k virtual)
            #   live  → live API with live credentials
            # This keeps market data quotes (live API) separate from paper balance.
            trading_mode = os.environ.get("TRADING_MODE", "paper").lower()
            try:
                if trading_mode == "paper":
                    # Prefer sandbox-specific creds; fall back to main creds so the
                    # balance always loads even when TRADIER_SANDBOX_* vars are absent.
                    paper_key = os.environ.get("TRADIER_SANDBOX_API_KEY", "") or api_key
                    paper_acct = os.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "") or account_id
                    paper_client = TradierClient(
                        api_key=paper_key,
                        account_id=paper_acct,
                        environment=TradingEnvironment.SANDBOX,
                    )
                    bal = paper_client.get_account_balances()
                    account_data = bal.get("balances", {})
                    equity = float(account_data.get("total_equity") or 0)
                    cash = float(account_data.get("total_cash") or 0)
                    margin = account_data.get("margin", {})
                    option_bp = float(
                        margin.get("option_buying_power")
                        or account_data.get("buying_power")
                        or cash
                    )
                    # Always emit — a zero balance is valid for a new/empty account.
                    self.balance_updated.emit(equity, option_bp)
                else:
                    # Live trading: fetch from live account
                    bal = client.get_account_balances()
                    account_data = bal.get("balances", {})
                    equity = float(account_data.get("total_equity") or 0)
                    cash = float(account_data.get("total_cash") or 0)
                    margin = account_data.get("margin", {})
                    option_bp = float(
                        margin.get("option_buying_power")
                        or account_data.get("buying_power")
                        or cash
                    )
                    # Always emit — a zero balance is valid for a new/empty account.
                    self.balance_updated.emit(equity, option_bp)
            except Exception:
                pass

            # --- Fetch live quotes and write to data_file ---
            symbols = [
                "SPY", "SPX", "VIX", "VIX9D", "VXV",   # S&P core + volatility (VIX confirmed on Tradier LIVE; $VIX is unmatched)  # noqa: E501
                "VVIX", "UVXY",                           # Volatility ETFs
                "SKEW",                                   # CBOE SKEW index
                "DIA", "QQQ", "IWM",                      # Major index ETFs
                "TLT", "HYG", "LQD", "GLD", "USO",         # Bonds & credit + correlations
                "UUP",                                    # USD Index ETF (DXY proxy; Tradier: no DXY)  # noqa: E501
                # NOTE: $DJI confirmed ~15 min delayed on Tradier (April 2026 testing).
                # DIA ETF * 100 is used instead — real-time, tracks within 0.3%.
                "RUT",                                    # Russell 2000 index (bare symbol confirmed on Tradier)  # noqa: E501
                # NOTE: NASDAQ Composite (IXIC) is NOT available on Tradier.
                # QQQ ETF * 37.5 is used as a Composite proxy (~23,079 vs actual ~23,111).
                # NDX (NASDAQ 100, ~25,358) is a different, unrelated index.
                # NOTE: $TICK, $ADD, $TRIN all confirmed unmatched on Tradier LIVE API (April 2026).
                # NYSE market internals are not available on current Tradier data subscription.
                "XLK", "XLF",                            # Sector ETFs for 0-DTE abort gates
            ]
            try:
                raw = client.get_quotes(symbols)
                quotes_raw = raw.get("quotes", {}).get("quote", [])
                if isinstance(quotes_raw, dict):
                    quotes_raw = [quotes_raw]
                live_data = {}
                _spy_q_slow: dict = {}
                # Remap Tradier symbols to dashboard widget keys where needed
                for q in quotes_raw:
                    sym = q.get("symbol", "")
                    last = float(q.get("last") or q.get("close") or 0.0)
                    change = float(q.get("change") or 0.0)
                    change_pct = float(q.get("change_percentage") or 0.0)
                    timestamp_ms = _freshest_quote_timestamp_ms(q)
                    if last:
                        key = _SYMBOL_REMAP.get(sym, sym)
                        live_data[key] = {
                            "last": last,
                            "change": change,
                            "change_pct": change_pct,
                            "timestamp_ms": timestamp_ms,
                        }
                    if sym == "SPY":
                        _spy_q_slow = q
                # --- RVOL: relative volume vs expected volume at this session fraction ---
                try:
                    _vol = float(_spy_q_slow.get("volume") or 0.0)
                    _adv = float(_spy_q_slow.get("average_volume") or 0.0)
                    if _vol > 0 and _adv > 0:
                        _now = datetime.now()
                        _open_dt = _now.replace(hour=9, minute=30, second=0, microsecond=0)
                        _elapsed_min = max((_now - _open_dt).total_seconds() / 60.0, 1.0)
                        _session_frac = min(_elapsed_min / 390.0, 1.0)
                        _rvol = round(_vol / (_adv * _session_frac), 2)
                        live_data["RVOL"] = {
                            "last": _rvol,
                            "change": 0.0,
                            "change_pct": 0.0,
                            "timestamp_ms": None,
                        }
                except Exception:
                    pass
                if live_data:
                    import json as _json
                    import time as _time
                    # Stamp wall-clock fetch time so the REAL-TIME badge uses the
                    # time we successfully called Tradier, not Tradier's quote
                    # timestamps (which can lag in quiet markets).
                    live_data["_fetch_time_ms"] = int(_time.time() * 1000)
                    self.data_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.data_file, "w") as f:
                        _json.dump(live_data, f)
                    # Keep the EOD snapshot current so closing prices are always
                    # preserved for next-morning startup display.
                    _snapshot_file = self.data_file.parent / "eod_snapshot.json"
                    _snapshot_meta = {
                        "_eod_date": datetime.now().strftime("%Y-%m-%d"),
                        "_eod_fetched_ts": int(_time.time()),
                    }
                    with open(_snapshot_file, "w") as _sf:
                        _json.dump({**live_data, **_snapshot_meta}, _sf)
            except Exception:
                pass

            # --- Compute put/call ratio (CPC) from SPY options chain ---
            # CBOE does not publish CPC via Tradier; we compute it from SPY chain volume.
            # CPC = total put volume / total call volume for the nearest expiration.
            # Uses the module-level _get_cached_chain() so concurrent callers share
            # one API round-trip per _CHAIN_TTL window (30 s).
            try:
                chain_result = _get_cached_chain(client)
                if chain_result is not None:
                    _contracts, put_vol, call_vol, _target_exp = chain_result
                    if call_vol > 0:
                        cpc = put_vol / call_vol
                        prev_cpc = live_data.get("CPC", {}).get("last", cpc)
                        cpc_change = cpc - prev_cpc
                        live_data["CPC"] = {
                            "last": round(cpc, 3),
                            "change": round(cpc_change, 3),
                            "change_pct": round(cpc_change / prev_cpc * 100 if prev_cpc else 0, 2),
                        }
                        # PCALL: same ratio — SPY is the primary equity index proxy.
                        live_data["PCALL"] = live_data["CPC"]
                        # Persist updated live_data with CPC (_fetch_time_ms already set above)
                        self.data_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(self.data_file, "w") as f:
                            import json as _json3
                            _json3.dump(live_data, f)
            except Exception:
                pass

            # --- Fetch 5-min SPY bars for chart ---
            # Only fetch after 9:30 AM ET — start="09:30" is invalid if market hasn't opened yet
            try:
                import pytz as _pytz
                from datetime import date as _date, datetime as _dt
                _et_now = _dt.now(_pytz.timezone("US/Eastern"))
                _market_open_et = _et_now.replace(hour=9, minute=30, second=0, microsecond=0)
                if _et_now < _market_open_et:
                    raise StopIteration  # skip fetch — bars don't exist yet
                today_open = f"{_date.today().isoformat()} 09:30"
                ts_resp = client.get_time_sales(
                    "SPY", interval="5min", start=today_open, session_filter="open",
                )
                candles_raw = (
                    ts_resp.get("series", {}).get("data", [])
                )
                if isinstance(candles_raw, dict):
                    candles_raw = [candles_raw]
                if candles_raw:
                    chart_file = self.data_file.parent / "spy_5min_chart.json"
                    with open(chart_file, "w") as f:
                        import json as _json2
                        _json2.dump(candles_raw, f)
            except StopIteration:
                pass  # before 9:30 ET — no bars yet
            except Exception:
                pass

            # --- Fetch previous trading day's daily OHLC for pivot anchoring ---
            # Pivots must use yesterday's H/L/C (fixed for the whole session).
            # We try a 5-day lookback so weekends/holidays are handled correctly.
            try:
                from datetime import date as _date2, timedelta as _td
                _prev_start = (_date2.today() - _td(days=5)).isoformat()
                _prev_end   = (_date2.today() - _td(days=1)).isoformat()
                _hist_resp = client.get_historical_quotes(
                    "SPY", interval="daily", start=_prev_start, end=_prev_end,
                )
                _hist_day = _hist_resp.get("history", {}).get("day", None)
                if isinstance(_hist_day, list) and _hist_day:
                    _hist_day = _hist_day[-1]   # most recent completed session
                if isinstance(_hist_day, dict) and _hist_day.get("high"):
                    _prev_day_file = self.data_file.parent / "spy_prev_day.json"
                    with open(_prev_day_file, "w") as _pf:
                        import json as _json4
                        _json4.dump({
                            "date":  _hist_day.get("date", ""),
                            "high":  float(_hist_day["high"]),
                            "low":   float(_hist_day["low"]),
                            "close": float(_hist_day["close"]),
                        }, _pf)
            except Exception:
                pass  # non-critical — pivot fallback is today's intraday range
        except Exception:
            pass

    def _fetch_quotes_fast(self):
        """Lightweight 10-second quote refresh — prices only, no options chain or chart bars.

        Merges fresh prices into live_data.json so the 1-second _real_data_timer
        picks them up immediately without overwriting CPC or other computed keys.
        """
        try:
            import json as _json
            from dotenv import load_dotenv
            load_dotenv(override=True)
            if not TRADIER_AVAILABLE:
                return
            api_key = os.environ.get("TRADIER_API_KEY", "")
            account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
            env_str = os.environ.get("TRADIER_ENVIRONMENT", "sandbox")
            if not api_key or not account_id:
                return
            env_enum = (
                TradingEnvironment.LIVE
                if env_str.lower() == "live"
                else TradingEnvironment.SANDBOX
            )
            client = TradierClient(api_key=api_key, account_id=account_id, environment=env_enum)
            symbols = [
                "SPY", "SPX", "VIX", "VIX9D", "VXV", "VVIX", "UVXY", "SKEW",
                "DIA", "QQQ", "IWM", "TLT", "HYG", "LQD", "GLD", "UUP",
                # $DJI excluded: ~15 min delayed on Tradier; DIA*100 used for display
                "RUT",   # Russell 2000 bare symbol — confirmed on Tradier (not $RUT)
                # NASDAQ Composite (IXIC) not available on Tradier; QQQ*37.5 proxy used instead
                # $TICK/$ADD/$TRIN: Yahoo Finance removed ^TICK/^ADD/^TRIN (404 as of 2025);
                # Tradier requires an index data add-on; route via SpyderC27_MassiveClient once enabled  # noqa: E501
                "XLK", "XLF",   # Sector ETFs for 0-DTE abort gates
            ]
            raw = client.get_quotes(symbols)
            quotes_raw = raw.get("quotes", {}).get("quote", [])
            if isinstance(quotes_raw, dict):
                quotes_raw = [quotes_raw]

            # Load existing file to preserve CPC and other computed keys
            existing: dict = {}
            if self.data_file.exists():
                try:
                    with open(self.data_file) as _f:
                        existing = _json.load(_f)
                except Exception:
                    pass

            updated = False
            _spy_q_raw: dict = {}
            for q in quotes_raw:
                sym = q.get("symbol", "")
                last = float(q.get("last") or q.get("close") or 0.0)
                change = float(q.get("change") or 0.0)
                change_pct = float(q.get("change_percentage") or 0.0)
                timestamp_ms = _freshest_quote_timestamp_ms(q)
                if last:
                    key = _SYMBOL_REMAP.get(sym, sym)
                    existing[key] = {
                        "last": last,
                        "change": change,
                        "change_pct": change_pct,
                        "timestamp_ms": timestamp_ms,
                    }
                    updated = True
                if sym == "SPY":
                    _spy_q_raw = q

            # --- RVOL: relative volume = current session volume / expected volume ---
            # Expected volume = ADV × fraction of trading session elapsed (390 min total).
            try:
                _vol = float(_spy_q_raw.get("volume") or 0.0)
                _adv = float(_spy_q_raw.get("average_volume") or 0.0)
                if _vol > 0 and _adv > 0:
                    _now = datetime.now()
                    _open_dt = _now.replace(hour=9, minute=30, second=0, microsecond=0)
                    _elapsed_min = max((_now - _open_dt).total_seconds() / 60.0, 1.0)
                    _session_frac = min(_elapsed_min / 390.0, 1.0)
                    _rvol = round(_vol / (_adv * _session_frac), 2)
                    existing["RVOL"] = {
                        "last": _rvol,
                        "change": 0.0,
                        "change_pct": 0.0,
                        "timestamp_ms": None,
                    }
                    updated = True
            except Exception:
                pass

            if updated:
                import time as _time_fast
                existing["_fetch_time_ms"] = int(_time_fast.time() * 1000)
                self.data_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.data_file, "w") as _f:
                    _json.dump(existing, _f)

            # --- Market internals ($TICK, $ADD, $TRIN, $VOLD) ---
            # Sourced via Playwright/TradingView scraping in SpyderS11_TradingViewInternals.py
            # (USI:TICK, USI:ADD, USI:TRIN.NY, USI:VOLD).  Values are published through
            # SpyderS07_CustomMetricsOrchestrator and written to live_data.json;
            # this worker does not need to fetch them separately.
        except Exception:
            pass

    def _fetch_eod_snapshot(self):
        """Fetch last-trade prices from Tradier outside market hours.

        Called once at startup when the trading window is closed.  Writes real
        closing/last prices to live_data.json so the dashboard can display
        genuine EOD data rather than hardcoded simulation values.

        Emits eod_snapshot_fetched(True) on success, eod_snapshot_fetched(False)
        when credentials are missing or the API call fails.
        """
        try:
            from dotenv import load_dotenv  # noqa: PLC0415
            import json as _json  # noqa: PLC0415
            load_dotenv(override=True)
            if not TRADIER_AVAILABLE:
                self.eod_snapshot_fetched.emit(False)
                return
            api_key = os.environ.get("TRADIER_API_KEY", "")
            account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
            env_str = os.environ.get("TRADIER_ENVIRONMENT", "sandbox")
            if not api_key or not account_id:
                logger.warning("📊 EOD snapshot skipped — TRADIER_API_KEY / TRADIER_ACCOUNT_ID not set")  # noqa: E501
                self.eod_snapshot_fetched.emit(False)
                return
            env_enum = (
                TradingEnvironment.LIVE
                if env_str.lower() == "live"
                else TradingEnvironment.SANDBOX
            )
            client = TradierClient(api_key=api_key, account_id=account_id, environment=env_enum)
            symbols = [
                "SPY", "SPX", "VIX", "VIX9D", "VXV", "VVIX", "UVXY", "SKEW",
                "DIA", "QQQ", "IWM", "TLT", "HYG", "LQD", "GLD", "USO", "UUP", "RUT",
                "XLK", "XLF",   # Sector ETFs for 0-DTE abort gates
            ]
            raw = client.get_quotes(symbols)
            quotes_raw = raw.get("quotes", {}).get("quote", [])
            if isinstance(quotes_raw, dict):
                quotes_raw = [quotes_raw]
            live_data: dict = {}
            for q in quotes_raw:
                sym = q.get("symbol", "")
                last = float(q.get("last") or q.get("close") or 0.0)
                change = float(q.get("change") or 0.0)
                change_pct = float(q.get("change_percentage") or 0.0)
                timestamp_ms = _freshest_quote_timestamp_ms(q)
                if last:
                    key = _SYMBOL_REMAP.get(sym, sym)
                    live_data[key] = {
                        "last": last,
                        "change": change,
                        "change_pct": change_pct,
                        "timestamp_ms": timestamp_ms,
                    }
            if live_data:
                import time as _time
                _snapshot_meta = {
                    "_eod_date": datetime.now().strftime("%Y-%m-%d"),
                    "_eod_fetched_ts": int(_time.time()),
                }
                self.data_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.data_file, "w") as _f:
                    _json.dump(live_data, _f)
                # Write a dedicated EOD snapshot so the dashboard can display
                # yesterday's closing prices immediately at next startup,
                # before the Tradier API call completes.
                _snapshot_file = self.data_file.parent / "eod_snapshot.json"
                with open(_snapshot_file, "w") as _sf:
                    _json.dump({**live_data, **_snapshot_meta}, _sf)
                logger.info("📊 EOD snapshot: %d symbols saved (%s)", len(live_data), _snapshot_meta["_eod_date"])  # noqa: E501
                self.market_data_status_changed.emit("EOD")
                self.eod_snapshot_fetched.emit(True)
            else:
                logger.warning("📊 EOD snapshot: Tradier returned no valid prices")
                self.eod_snapshot_fetched.emit(False)
        except Exception as _e:
            logger.warning("📊 EOD snapshot fetch failed: %s", _e)
            self.eod_snapshot_fetched.emit(False)

    def _init_simulation_data(self):
        """Initialize simulation data with all symbols"""
        base_prices = {
            "SPY": 585.25,
            "SPX": 5850.75,
            "/ES": 5852.50,
            "VIX": 15.32,
            "VIX9D": 14.8,
            "VXV": 16.2,
            "VXMT": 17.5,
            "VVIX": 82.45,
            "UVXY": 22.18,
            "$TICK": 234,
            "$TRIN": 0.85,
            "$ADD": 1245,
            "CPC": 0.95,
            "PCALL": 0.88,
            "SKEW": 125.5,
            "DIA": 425.33,
            "QQQ": 485.92,
            "IWM": 225.18,
            "TLT": 92.45,
            "HYG": 78.50,
            "LQD": 105.32,
            "DXY": 103.25,
            "GLD": 195.67,
            "GEX": -2500000000,
            "DEX": 850000000,
            "OGL": 585.50,
            "DIX": 42.5,
            "SWAN": 1.85,
            "IVR": 45.0,
            "ATM_IV": 15.5,
            "VRP": 2.3,
        }

        with QMutexLocker(self.data_mutex):
            for symbol, price in base_prices.items():
                self.market_data[symbol] = {
                    "symbol": symbol,
                    "last": price,
                    "change": 0,
                    "change_pct": 0,
                    "timestamp": datetime.now(),
                }
                self.last_data_update[symbol] = datetime.now()

    def _check_market_hours(self):
        """Check if market hours status has changed"""
        current_market_hours = is_market_hours()

        if current_market_hours != self.market_hours:
            self.market_hours = current_market_hours
            logger.info(
                "📊 Market hours changed: %s", 'OPEN' if self.market_hours else 'CLOSED',
            )

            if not self.market_hours:
                if self.api_connected:
                    self.market_data_status_changed.emit("NONE")

    @Slot()
    def start(self):
        """Start the worker: create QTimers in worker thread and emit initial connection status."""
        logger.info("🚀 Starting Thread-Safe Market Data Worker with heartbeat monitoring...")

        # CRITICAL: Create QTimers in the worker thread, not the main thread
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._emit_data)
        self.update_timer.start(2000)

        self.market_hours_timer = QTimer()
        self.market_hours_timer.timeout.connect(self._check_market_hours)
        self.market_hours_timer.start(60000)

        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._heartbeat_check)
        self.heartbeat_timer.start(HEARTBEAT_INTERVAL)

        self.heartbeat_warning_timer = QTimer()
        self.heartbeat_warning_timer.timeout.connect(self._heartbeat_warning)

        # Only attempt initial connection if within the trading window
        if not is_tradier_window():
            import pytz as _pytz
            _et_now = datetime.now(_pytz.timezone("US/Eastern"))
            _open_str = TRADIER_CONNECT_TIME.strftime("%I:%M %p")
            logger.info("🕐 Outside trading window — Tradier will connect at %s ET", _open_str)
            self.connection_status_changed.emit(False, "WAITING FOR MARKET")
            self.market_data_status_changed.emit("NONE")
            self.heartbeat_status_changed.emit("disconnected")
            self.heartbeat_received.emit(
                "❤️ Tradier inactive - outside market hours (9:20 AM – 4:30 PM ET)"
            )
            # Fetch real last-trade prices so the dashboard shows genuine EOD data
            # rather than hardcoded simulation values.  Run after a short delay so
            # all Qt signal connections are established before the emit fires.
            QTimer.singleShot(500, self._fetch_eod_snapshot)
            # Also fetch account balance — not gated by market hours so the
            # account section populates even when launched before/after market.
            QTimer.singleShot(2000, self._fetch_balance_only)
            return

        try:
            connected, mode = check_api_connection()
            self.api_connected = connected

            if connected:
                self.connection_status_changed.emit(True, f"API CONNECTED ({mode})")
                # Emit "LIVE" or "PAPER" (not "REAL-TIME") so on_market_data_status_changed
                # sets mkt_data_connected = True and turns the TRADIER DATA label green.
                _startup_sandbox = "SANDBOX" in mode.upper() or "PAPER" in mode.upper()
                _startup_mkt = "PAPER" if _startup_sandbox else "LIVE"
                self.market_data_status_changed.emit(_startup_mkt)
                self.heartbeat_status_changed.emit("connected")  # Green heart
                logger.info("✅ Tradier API connected at startup: %s", mode)
            else:
                self.connection_status_changed.emit(False, "API DISCONNECTED")
                self.market_data_status_changed.emit("NONE")
                self.heartbeat_status_changed.emit("disconnected")  # Red heart
                logger.info("❌ Tradier API disconnected at startup")

        except Exception as e:
            logger.info("⚠️ Startup connection check error: %s", e)
            self.api_connected = False
            self.connection_status_changed.emit(False, "API DISCONNECTED")
            self.market_data_status_changed.emit("NONE")
            self.heartbeat_status_changed.emit("error")  # Red heart

    def _emit_data(self):
        """Emit current market data"""
        with QMutexLocker(self.data_mutex):
            data_copy = self.market_data.copy()

        self._update_simulation_data(data_copy)
        self.data_updated.emit(data_copy)

    def _update_simulation_data(self, data: dict):
        """Update simulation data with realistic market movements"""
        if not is_market_hours():
            return

        current_time = datetime.now()

        for symbol, market_info in data.items():
            if symbol not in ["GEX", "DEX", "OGL", "DIX", "SWAN"]:
                old_price = market_info["last"]
                change = random.uniform(-0.5, 0.5)
                new_price = old_price + change
                change_pct = (change / old_price * 100) if old_price != 0 else 0

                market_info.update(
                    {
                        "last": new_price,
                        "change": change,
                        "change_pct": change_pct,
                        "timestamp": current_time,
                    },
                )

            with QMutexLocker(self.data_mutex):
                self.last_data_update[symbol] = current_time

    def force_connect(self):
        """Manual connect - now checks actual connection"""
        logger.info("🔥 Manual connect requested")
        if not is_market_hours():
            logger.info("📊 Cannot connect - market is closed")
            return False

        # Check actual connection
        connected, mode = check_api_connection()
        self.api_connected = connected

        if connected:
            self.connection_status_changed.emit(True, f"API CONNECTED ({mode})")
            is_sandbox = "SANDBOX" in mode.upper() or "PAPER" in mode.upper()
            self.market_data_status_changed.emit("PAPER" if is_sandbox else "LIVE")
            return True
        self.connection_status_changed.emit(False, "API DISCONNECTED")
        self.market_data_status_changed.emit("NONE")
        return False

    def force_disconnect(self):
        """Manual disconnect"""
        logger.info("🔥 Manual disconnect requested")
        self.api_connected = False
        self.connection_status_changed.emit(False, "API DISCONNECTED")
        self.market_data_status_changed.emit("NONE")

    def stop(self):
        """Stop worker and all timers"""
        logger.info("🛑 Stopping worker and heartbeat monitoring...")
        if self.update_timer:
            self.update_timer.stop()
        if self.market_hours_timer:
            self.market_hours_timer.stop()
        if self.heartbeat_timer:
            self.heartbeat_timer.stop()
        if self.heartbeat_warning_timer:
            self.heartbeat_warning_timer.stop()


__all__ = [
    "HEARTBEAT_INTERVAL",
    "HEARTBEAT_LOG_INTERVAL",
    "HEARTBEAT_WARNING_TIME",
    "REALTIME_QUOTE_MAX_AGE_SECONDS",
    "REALTIME_SENTINEL_SYMBOLS",
    "ThreadSafeMarketDataWorker",
    "_CHAIN_CACHE",
    "_CHAIN_LOCK",
    "_CHAIN_TTL",
    "_coerce_epoch_ms",
    "_datetime_from_epoch_ms",
    "_freshest_live_data_timestamp",
    "_freshest_quote_timestamp_ms",
    "_get_cached_chain",
    "check_api_connection",
]
