#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG18_MarketDataWorker.py
Purpose: Market data QThread worker (extracted from TradovG05)

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    QObject-based market data worker that runs on its own QThread and fans
    out Tradier quotes, account balances, option chain CPC computation,
    heartbeat status, and 5-minute TRAD chart bars into Qt signals consumed
    by TradovG05_TradingDashboard.

    Relocated from TradovG05 per audit §1/§14/§23 so the dashboard layer no
    longer owns live-data fetch logic. Behavior, signal contract, JSON cache
    schema, and index-proxy math (UUP→DXY, QQQ×37.5 for IXIC) are preserved
    bit-for-bit — this is a mechanical relocation, not a
    MarketDataProtocol integration. Full protocol adoption is deferred until
    TradovC00_MarketDataProtocol's contract can be validated end-to-end
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
import threading
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import QObject, QMutex, QMutexLocker, QTimer, Signal, Slot

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU51_RuntimeContext import (
    RuntimeContext,
    coerce_runtime_context,
)
from Tradov.TradovU_Utilities.TradovU03_DateTimeUtils import (
    ET_TZ,
    LogThrottle,
    is_dashboard_session as _is_dashboard_session,
)
from Tradov.TradovU_Utilities.TradovU49_SymbolCatalog import (
    get_quote_symbol_remap,
    get_realtime_sentinel_symbols,
    get_runtime_quote_symbol_basket,
)


def is_market_hours(now_et: datetime | None = None) -> bool:
    """Return True only when ET time is in session and weekday is Mon-Fri."""
    current_et = now_et or datetime.now(ET_TZ)
    try:
        from Tradov.TradovU_Utilities.TradovU10_TradingCalendar import get_trading_calendar

        return bool(get_trading_calendar().is_market_open(current_et))
    except Exception:
        if current_et.weekday() >= 5:
            return False
        return bool(_is_dashboard_session(current_et))


try:
    from Tradov.TradovB_Broker.TradovB40_TradierClient import (
        TradierClient,
        TradingEnvironment,
    )
    TRADIER_AVAILABLE = True
except ImportError:
    TradierClient = None  # type: ignore
    TradingEnvironment = None  # type: ignore
    TRADIER_AVAILABLE = False

try:
    from Tradov.TradovU_Utilities.TradovU41_CircuitBreaker import (
        tradier_breaker as _tradier_breaker,
    )
    _circuit_breakers_available = True
except ImportError:
    _tradier_breaker = None  # type: ignore
    _circuit_breakers_available = False


logger = TradovLogger.get_logger(__name__)


# ==============================================================================
# CONSTANTS
# ==============================================================================
HEARTBEAT_INTERVAL = 30000        # 30 seconds in milliseconds — check frequency
HEARTBEAT_WARNING_TIME = 20000    # 20 seconds before next check (blue heart)
HEARTBEAT_LOG_INTERVAL = 1800     # 30 minutes between "healthy" log messages

REALTIME_QUOTE_MAX_AGE_SECONDS = 45.0   # Survive 1-2 missed 10-s fast-fetch cycles + Tradier timeout  # noqa: E501
REALTIME_SENTINEL_SYMBOLS = get_realtime_sentinel_symbols()
DIA_REFETCH_MAX_AGE_SECONDS = 20.0
DIRECT_INDEX_REFRESH_SYMBOLS: tuple[str, ...] = ("DIA", "RUT")
PAPER_ACCOUNT_SOURCE_TRADOVBOX_LOCAL = "tradovbox_local"

# Options-chain fetch deduplication.
# The TRAD chain is expensive (~200-400ms, Tradier rate-limited).  Multiple
# callers (heartbeat trigger + fast-fetch overlap, S07 options analytics) can
# request the chain within the same polling window.  We guard with:
#   _CHAIN_LOCK  — only one thread fetches at a time; others wait and read cache.
#   _CHAIN_CACHE — stores (contracts, put_vol, call_vol, expiry) with a TTL.
#   _CHAIN_TTL   — 30 s: safe margin between the ~60 s slow-fetch cycle.
_CHAIN_LOCK: threading.Lock = threading.Lock()
_CHAIN_TTL: float = 30.0
_CHAIN_CACHE: dict = {}  # keys: "contracts", "put_vol", "call_vol", "expiry", "ts"

_VXV_CACHE_TTL_SECONDS: float = 300.0
_VXV_CACHE: dict[str, Any] = {"ts": 0.0, "entry": None}

# RUT historical previous-close cache.
# Tradier returns change=None for RUT; we fetch its prev-day close once per
# session via the historical quotes endpoint so we can derive change/change_pct.
_RUT_PREVCLOSE_CACHE: dict = {"prevclose": 0.0, "date": ""}
_TRAD_PREVDAY_FETCH_CACHE: dict = {"date": ""}
_TRAD_TIMESALES_FETCH_CACHE: dict = {"last_fetch_mono": 0.0}
_TRADIER_CLIENT_CACHE_LOCK: threading.Lock = threading.Lock()
_TRADIER_CLIENT_CACHE: dict[tuple[str, str, str], "TradierClient"] = {}

TRAD_TIMESALES_FETCH_INTERVAL_SECONDS = 60.0
CHART_UNDERLYING_SYMBOL = str(os.getenv("TRADOV_UNDERLYING_SYMBOL", "SPX") or "SPX").strip().upper() or "SPX"


def _is_live_data_warmup_window(now_et: datetime | None = None) -> bool:
    """Return True once the 09:20 ET live-data warmup window has opened."""
    current_et = now_et or datetime.now(ET_TZ)
    if current_et.weekday() >= 5:
        return False
    return current_et.time() >= datetime.strptime("09:20", "%H:%M").time()


def _close_cached_tradier_clients() -> int:
    """Close and clear shared Tradier clients held by the market-data worker."""
    with _TRADIER_CLIENT_CACHE_LOCK:
        cached_clients = list(_TRADIER_CLIENT_CACHE.values())
        _TRADIER_CLIENT_CACHE.clear()

    closed_count = 0
    for client in cached_clients:
        close_client = getattr(client, "close", None)
        if not callable(close_client):
            continue
        try:
            close_client()
            closed_count += 1
        except Exception:
            logger.debug("Failed to close cached Tradier client", exc_info=True)

    return closed_count


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
            from datetime import date as _date2  # noqa: PLC0415, timezone
            exps_raw = client.get_option_expirations("TRAD")
            exp_dates = exps_raw.get("expirations", {}).get("date", [])
            if isinstance(exp_dates, str):
                exp_dates = [exp_dates]
            target_exp = next(
                (d for d in exp_dates if d >= _date2.today().isoformat()),
                exp_dates[0] if exp_dates else None,
            )
            if not target_exp:
                return None
            contracts = client.get_option_chain_with_greeks("TRAD", target_exp)
            put_vol = sum(
                float(getattr(c, "volume", 0) or 0)
                for c in contracts if str(getattr(c, "option_type", "")).lower() == "put"
            )
            call_vol = sum(
                float(getattr(c, "volume", 0) or 0)
                for c in contracts if str(getattr(c, "option_type", "")).lower() == "call"
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
_SYMBOL_REMAP: dict[str, str] = get_quote_symbol_remap()
_QUOTE_SYMBOL_BASKET: tuple[str, ...] = tuple(get_runtime_quote_symbol_basket())


def _build_quote_symbol_basket() -> list[str]:
    """Return one canonical quote basket for slow, fast, and EOD fetch paths."""
    return list(_QUOTE_SYMBOL_BASKET)


def _get_vxv_yahoo_symbol() -> str:
    """Return the canonical Yahoo symbol for Tradov's internal VXV key."""
    try:
        from Tradov.TradovC_MarketData.TradovC10_VIXAnalyzer import VIX_SYMBOLS  # noqa: PLC0415

        yahoo_symbol = VIX_SYMBOLS.get("VXV")
        if isinstance(yahoo_symbol, str) and yahoo_symbol.strip():
            return yahoo_symbol
    except Exception:
        pass

    return "^VIX3M"


def _fetch_vxv_live_entry() -> dict[str, Any] | None:
    """Fetch a synthetic VXV live-data entry from Yahoo with a short cache."""
    cached_entry = _VXV_CACHE.get("entry")
    cache_age = time.monotonic() - float(_VXV_CACHE.get("ts", 0.0) or 0.0)
    if isinstance(cached_entry, dict) and cache_age < _VXV_CACHE_TTL_SECONDS:
        return dict(cached_entry)

    try:
        import yfinance as yf  # noqa: PLC0415

        ticker = yf.Ticker(_get_vxv_yahoo_symbol())
        info = ticker.info
        last = float(info.get("regularMarketPrice") or 0.0)
        prev_close = float(info.get("previousClose") or 0.0)
        if last <= 0.0:
            last = prev_close
        if last <= 0.0:
            raise ValueError("Yahoo returned no VXV/VIX3M price")

        change_available = prev_close > 0.0
        change = last - prev_close if change_available else 0.0
        change_pct = ((change / prev_close) * 100.0) if change_available else 0.0
        entry = {
            "last": round(last, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "change_available": change_available,
            "timestamp_ms": int(time.time() * 1000),
            "source": "yfinance_vix3m",
        }
        _VXV_CACHE["entry"] = entry
        _VXV_CACHE["ts"] = time.monotonic()
        return dict(entry)
    except Exception as exc:
        if isinstance(cached_entry, dict):
            logger.debug("VXV Yahoo refresh failed, using cached VXV entry: %s", exc)
            return dict(cached_entry)

        logger.debug("VXV Yahoo fetch failed: %s", exc)
        return None


def _quote_to_live_entry(q: dict) -> tuple[str, dict] | None:
    """Normalize a Tradier quote payload into a live_data entry."""
    sym = q.get("symbol", "")
    last = float(q.get("last") or q.get("close") or 0.0)
    raw_change = q.get("change")
    raw_change_pct = q.get("change_percentage")
    change_available = not (raw_change is None and raw_change_pct is None)
    change = float(raw_change or 0.0)
    change_pct = float(raw_change_pct or 0.0)
    if change == 0.0 and last > 0.0:
        prevclose = float(q.get("prevclose") or 0.0)
        if prevclose > 0.0:
            change = last - prevclose
            change_pct = (change / prevclose) * 100.0
            change_available = True

    timestamp_ms = _freshest_quote_timestamp_ms(q)
    if timestamp_ms is None:
        # Some index symbols (notably NDX/RUT on Tradier) return 0 for
        # trade/bid/ask dates. Use wall-clock fetch time so freshness checks
        # and UI age logic still work.
        timestamp_ms = int(time.time() * 1000)
    if not last:
        return None

    key = _SYMBOL_REMAP.get(sym, sym)
    # Direct index symbols and daily indices get stale Tradier quote timestamps
    # because indices don't "trade" on an exchange — the timestamp reflects the
    # last CBOE/index calculation, not when we polled Tradier.  Override with
    # current wall-clock time so the dashboard freshness indicator reflects our
    # actual polling cadence (30 s), not the index's internal update frequency.
    #   $DJI  — Tradier's Dow Jones quote can lag 15+ minutes intraday
    #   SPX   — same issue for direct S&P 500 index symbol
    #   NDX   — same for NASDAQ-100 index
    #   RUT   — same for Russell 2000 index
    #   SKEW  — daily CBOE index, timestamp is from previous day's close
    _CLOCK_STAMP_SYMBOLS = {"$DJI", "SPX", "NDX", "RUT", "SKEW"}
    if key in _CLOCK_STAMP_SYMBOLS:
        timestamp_ms = int(time.time() * 1000)
    return key, {
        "last": last,
        "change": change,
        "change_pct": change_pct,
        "change_available": change_available,
        "timestamp_ms": timestamp_ms,
    }


def _is_symbol_stale(live_data: dict, symbol: str, reference_epoch_ms: int, max_age_seconds: float) -> bool:
    """Return True when a symbol quote is missing or older than max_age_seconds."""
    entry = live_data.get(symbol)
    if not isinstance(entry, dict):
        return True

    ts_ms = _coerce_epoch_ms(entry.get("timestamp_ms"))
    if ts_ms is None:
        return True

    age_seconds = max(0.0, (reference_epoch_ms - ts_ms) / 1000.0)
    return age_seconds > max_age_seconds


def _refetch_single_symbol_quote(client: "TradierClient", live_data: dict, symbol: str) -> bool:
    """Fetch one symbol directly from Tradier and upsert into live_data."""
    try:
        raw = client.get_quotes([symbol])
        quotes_raw = raw.get("quotes", {}).get("quote", [])
        if isinstance(quotes_raw, dict):
            quotes_raw = [quotes_raw]

        for q in quotes_raw:
            if str(q.get("symbol", "")).upper() != symbol.upper():
                continue
            normalized = _quote_to_live_entry(q)
            if normalized is None:
                continue
            key, entry = normalized
            live_data[key] = entry
            return True
    except Exception:
        return False

    return False


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


def _build_market_data_client() -> "TradierClient | None":
    """Build a Tradier client for market-data reads.

    Market data is always fetched from the LIVE endpoint for both paper
    and live modes.

    Returns:
        Configured TradierClient, or None if Tradier is unavailable or
        credentials are not set.
    """
    if not TRADIER_AVAILABLE or TradierClient is None or TradingEnvironment is None:
        return None
    try:
        from dotenv import load_dotenv  # noqa: PLC0415
        load_dotenv(override=True)

        live_api_key = os.environ.get("TRADIER_LIVE_API_KEY")
        live_account_id = os.environ.get("TRADIER_LIVE_ACCOUNT_ID")
        legacy_account_id = os.environ.get("TRADIER_ACCOUNT_ID")

        api_key = live_api_key or ""
        account_id = live_account_id or legacy_account_id or ""
        api_key_source = "TRADIER_LIVE_API_KEY"
        account_id_source = (
            "TRADIER_LIVE_ACCOUNT_ID" if live_account_id else "TRADIER_ACCOUNT_ID"
        )
        env_enum = TradingEnvironment.LIVE

        if not api_key:
            return None

        logger.info(
            "Market-data credential source selected: api_key=%s account_id=%s",
            api_key_source,
            account_id_source,
        )

        return _get_cached_tradier_client(api_key, account_id, env_enum)
    except Exception:
        return None


def _get_cached_tradier_client(
    api_key: str,
    account_id: str,
    environment: "TradingEnvironment | None",
) -> "TradierClient | None":
    """Return a shared Tradier client for repeated read-only worker fetches."""
    if not TRADIER_AVAILABLE or TradierClient is None or environment is None:
        return None

    environment_name = getattr(environment, "name", str(environment)).upper()
    cache_key = (api_key, account_id, environment_name)

    with _TRADIER_CLIENT_CACHE_LOCK:
        cached_client = _TRADIER_CLIENT_CACHE.get(cache_key)
        if cached_client is not None:
            return cached_client

        client = TradierClient(
            api_key=api_key,
            account_id=account_id,
            environment=environment,
        )
        _TRADIER_CLIENT_CACHE[cache_key] = client
        return client


def _paper_account_balance_source() -> str:
    """Return paper account-balance source policy.

    Fail-closed policy: paper balances are always sourced from local TradovBox
    state/database and never from Tradier sandbox.
    """
    raw_source = str(
        os.environ.get("TRADOV_PAPER_ACCOUNT_SOURCE", PAPER_ACCOUNT_SOURCE_TRADOVBOX_LOCAL)
    ).strip().lower()
    if raw_source in {"tradovbox", "tradovbox_local", "local", "internal", "db"}:
        return PAPER_ACCOUNT_SOURCE_TRADOVBOX_LOCAL
    return PAPER_ACCOUNT_SOURCE_TRADOVBOX_LOCAL


def _tradovbox_paper_state_file() -> Path:
    """Return the paper-state file used by the TradovBox local paper account."""
    state_file = str(os.environ.get("TRADOV_PAPER_ACCOUNT_STATE_FILE", "")).strip()
    if state_file:
        return Path(state_file).expanduser()
    return Path.home() / "Projects/Tradov/market_data/paper_trading_state.json"


def _load_tradovbox_paper_account_snapshot() -> tuple[float, float] | None:
    """Load local TradovBox paper account snapshot as (equity, buying_power)."""
    # Prefer the paper worker's persisted runtime state for freshest values.
    state_path = _tradovbox_paper_state_file()
    if state_path.exists():
        try:
            import json as _json

            with open(state_path, encoding="utf-8") as _sf:
                state = _json.load(_sf)

            cash = float(state.get("_cash", 0.0) or 0.0)
            return cash, cash
        except Exception:
            pass

    # Fall back to the latest paper account snapshot in the H05 paper DB.
    try:
        from Tradov.TradovH_Storage.TradovH05_TradingSessionDB import TradingSessionDB  # noqa: PLC0415

        snapshot = TradingSessionDB.for_paper().get_latest_snapshot()
        if not isinstance(snapshot, dict):
            return None

        equity_raw = snapshot.get("equity")
        if equity_raw is None:
            equity_raw = snapshot.get("cash")

        buying_power_raw = snapshot.get("buying_power")
        if buying_power_raw is None:
            buying_power_raw = snapshot.get("cash")

        if equity_raw is None or buying_power_raw is None:
            return None

        return float(equity_raw), float(buying_power_raw)
    except Exception:
        return None


def _extract_tradier_balance(payload: dict) -> tuple[float, float]:
    """Return (settled_cash, buying_power) from a Tradier balances payload."""
    account_data = payload.get("balances", {}) if isinstance(payload, dict) else {}
    cash = float(account_data.get("total_cash") or 0)
    margin = account_data.get("margin", {})
    option_bp = float(
        margin.get("option_buying_power")
        or account_data.get("buying_power")
        or cash
    )
    return cash, option_bp


BALANCE_SOURCE_LIVE = "live"
BALANCE_SOURCE_PAPER = "paper"


def _emit_balance_update(worker: Any, source: str, equity: float, option_bp: float) -> bool:
    """Emit a balance update while remaining compatible with older 2-arg stubs."""
    signal_obj = getattr(worker, "balance_updated", None)
    emit = getattr(signal_obj, "emit", None)
    if not callable(emit):
        return False

    try:
        emit(source, equity, option_bp)
    except TypeError:
        emit(equity, option_bp)

    return True


def _emit_paper_balance_update(worker: Any) -> bool:
    """Emit the local TradovBox paper balance snapshot when available."""
    local_snapshot = _load_tradovbox_paper_account_snapshot()
    if local_snapshot is None:
        return False

    worker._paper_balance_snapshot_missing_warned = False
    equity, option_bp = local_snapshot
    return _emit_balance_update(worker, BALANCE_SOURCE_PAPER, equity, option_bp)


def _paper_snapshot_gap_requires_warning() -> bool:
    """Return True when a missing paper snapshot indicates unexpected drift."""
    state_path = _tradovbox_paper_state_file()
    if state_path.exists():
        return True

    try:
        from Tradov.TradovH_Storage.TradovH05_TradingSessionDB import TradingSessionDB  # noqa: PLC0415

        db = TradingSessionDB.for_paper()
        if db.get_latest_snapshot() is not None:
            return True
        if db.get_open_positions():
            return True
        return bool(db.get_recent_trades(limit=1))
    except Exception:
        # If we cannot inspect local paper state, preserve the warning.
        return True


def _warn_missing_paper_snapshot(worker: Any) -> None:
    """Emit a single warning when paper balance state should exist but does not."""
    if not _paper_snapshot_gap_requires_warning():
        return
    if bool(getattr(worker, "_paper_balance_snapshot_missing_warned", False)):
        return

    logger.warning(
        "Paper balance unavailable: local TradovBox snapshot missing "
        "(sandbox fallback disabled)."
    )
    worker._paper_balance_snapshot_missing_warned = True


def _emit_live_balance_update(worker: Any) -> bool:
    """Emit the live Tradier balance snapshot when credentials are available."""
    if not TRADIER_AVAILABLE:
        return False

    api_key, account_id, env_enum = _resolve_tradier_client_config()
    if not api_key or not account_id or env_enum is None:
        return False

    client = _get_cached_tradier_client(api_key, account_id, env_enum)
    if client is None:
        return False
    bal = client.get_account_balances()
    equity, option_bp = _extract_tradier_balance(bal)
    return _emit_balance_update(worker, BALANCE_SOURCE_LIVE, equity, option_bp)


def _runtime_trading_mode(runtime_context: RuntimeContext | None = None) -> str:
    """Return the normalized runtime trading mode used by safety guards."""
    if runtime_context is not None:
        return runtime_context.mode
    override = str(os.environ.get("TRADOV_TRADING_MODE", "")).strip().lower()
    if override:
        return override
    return str(os.environ.get("TRADING_MODE", "paper")).strip().lower()


def _live_account_balance_reads_enabled(runtime_context: RuntimeContext | None = None) -> bool:
    """Allow live-account balance reads only when runtime mode is explicitly live."""
    return _runtime_trading_mode(runtime_context) == "live"


def check_api_connection(runtime_context: RuntimeContext | None = None):
    """Check whether the Tradier API is reachable and authenticated.

    This probes a non-market-dependent broker endpoint so the result stays
    meaningful outside regular trading hours.

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
            client = _build_market_data_client()
            if client is not None:
                if client.test_connection():
                    trading_mode = _runtime_trading_mode(runtime_context)
                    mode_label = "PAPER" if trading_mode == "paper" else "LIVE"
                    return True, f"Tradier API ({mode_label})"

                return False, "Tradier API connection test failed"

        return False, "Tradier API not configured"

    except Exception as e:
        message = str(e)
        if "Invalid Access Token" in message or "Authentication failed" in message:
            return False, "Tradier API auth failed: Invalid Access Token"
        return False, f"API check failed: {e}"


def _resolve_tradier_client_config() -> tuple[str, str, "TradingEnvironment"] | tuple[None, None, None]:
    """Resolve Tradier credentials for live-account balance reads only."""
    api_key = os.environ.get("TRADIER_LIVE_API_KEY") or ""
    account_id = (
        os.environ.get("TRADIER_LIVE_ACCOUNT_ID")
        or os.environ.get("TRADIER_ACCOUNT_ID")
        or ""
    )

    if not api_key:
        return None, None, None

    return api_key, account_id, TradingEnvironment.LIVE


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
    balance_updated = Signal(str, float, float)  # (source, settled_cash/equity, buying_power)
    fetch_requested = Signal()       # Trigger full live fetch from GUI thread safely
    fast_fetch_requested = Signal()  # Trigger lightweight quote-only refresh
    eod_snapshot_fetched = Signal(bool)  # True = real EOD prices written to live_data.json

    def __init__(self, quiet_startup: bool = False, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self.logger = TradovLogger.get_logger(__name__)
        self._quiet_startup = bool(quiet_startup)
        self.runtime_context = coerce_runtime_context(runtime_context)

        # FIXED: Start with actual connection check instead of assuming connected
        self.api_connected = False

        self.market_data = {}
        self.data_mutex = QMutex()
        self.client_id = 0  # Dedicated client ID for the dashboard worker
        self.market_hours = is_market_hours()

        # Path to live market data file (shared with dashboard)
        self.data_file = Path.home() / "Projects/Tradov/market_data/live_data.json"

        # Initialize timer references (will be created in start() method)
        self.update_timer = None
        self.market_hours_timer = None
        self.heartbeat_timer = None
        self.heartbeat_warning_timer = None
        self._shutdown_requested = False

        self.last_data_update = {}
        self._healthy_log_throttle = LogThrottle(HEARTBEAT_LOG_INTERVAL)
        self._offline_log_throttle = LogThrottle(HEARTBEAT_LOG_INTERVAL)
        self._event_manager = None
        self._market_data_event_type = None
        self._last_spy_market_data_key = None
        self._paper_balance_snapshot_missing_warned = False

        if not self._quiet_startup:
            logger.info("🔧 Market Data Worker initialized with heartbeat monitoring")
            logger.info("📊 Market: %s", 'OPEN' if self.market_hours else 'CLOSED')

    def _shutdown_in_progress(self) -> bool:
        """Return True once the worker has entered shutdown."""
        return bool(getattr(self, "_shutdown_requested", False))

    def _resolve_market_event_bridge(self):
        """Return the active A05 market-data event bridge."""
        event_manager = getattr(self, "_event_manager", None)
        market_data_event_type = getattr(self, "_market_data_event_type", None)
        if event_manager is not None and market_data_event_type is not None:
            return event_manager, market_data_event_type

        try:
            from Tradov.TradovA_Core.TradovA05_EventManager import EventType, get_event_manager

            event_manager = get_event_manager()
            market_data_event_type = EventType.MARKET_DATA
            self._event_manager = event_manager
            self._market_data_event_type = market_data_event_type
            return event_manager, market_data_event_type
        except Exception as exc:
            self.logger.debug("G18: EventManager unavailable for market-data bridge: %s", exc)
            return None, None

    def _emit_spy_market_data_event(
        self,
        entry: dict[str, Any] | None,
        quote: dict[str, Any] | None = None,
    ) -> None:
        """Publish a normalized TRAD market-data event for A05 consumers."""
        if not isinstance(entry, dict):
            return

        try:
            last = float(entry.get("last") or 0.0)
        except (TypeError, ValueError):
            return
        if last <= 0.0:
            return

        event_manager, market_data_event_type = self._resolve_market_event_bridge()
        if event_manager is None or market_data_event_type is None:
            return

        timestamp_ms = _coerce_epoch_ms(entry.get("timestamp_ms")) or int(time.time() * 1000)
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=UTC)
        event_key = (timestamp_ms, round(last, 6))

        if getattr(self, "_last_spy_market_data_key", None) == event_key:
            return

        tick = {
            "symbol": "TRAD",
            "open": last,
            "high": last,
            "low": last,
            "close": last,
            "price": last,
            "last": last,
        }

        if isinstance(quote, dict):
            for key in ("bid", "ask", "volume"):
                value = quote.get(key)
                if value in (None, ""):
                    continue
                try:
                    tick[key] = float(value)
                except (TypeError, ValueError):
                    continue

        event_payload = {
            "symbol": "TRAD",
            "last": last,
            "price": last,
            "change": float(entry.get("change") or 0.0),
            "change_pct": float(entry.get("change_pct") or 0.0),
            "timestamp_ms": timestamp_ms,
            "timestamp": timestamp,
            "tick": tick,
        }

        for key in ("bid", "ask", "volume"):
            value = tick.get(key)
            if value is not None:
                event_payload[key] = value

        try:
            event_manager.emit(
                market_data_event_type,
                event_payload,
                source=self.__class__.__name__,
            )
            self._last_spy_market_data_key = event_key
        except Exception as exc:
            self.logger.debug("G18: failed to publish TRAD MARKET_DATA bridge event: %s", exc)

    def _heartbeat_check(self):
        """30-second heartbeat check for Tradier API connection"""
        try:
            # Check actual connection
            connected, mode = check_api_connection(self.runtime_context)
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
                    self.connection_status_changed.emit(False, mode or "API DISCONNECTED")
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

        Called at startup (both inside and outside trading window), including the
        quiet launch prewarm, so the account panels are populated as soon as
        credentials are available regardless of whether the market is open.
        """
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)

            trading_mode = _runtime_trading_mode(self.runtime_context)
            paper_snapshot_emitted = _emit_paper_balance_update(self)
            if trading_mode == "paper" and not paper_snapshot_emitted:
                _warn_missing_paper_snapshot(self)

            if _live_account_balance_reads_enabled(self.runtime_context):
                _emit_live_balance_update(self)
        except Exception:
            pass

    def _fetch_live_data_from_tradier(self):
        """Fetch live quotes and account balance from Tradier, write to data_file."""
        try:
            if self._shutdown_in_progress():
                return

            from dotenv import load_dotenv
            load_dotenv(override=True)
            if not TRADIER_AVAILABLE:
                return

            # --- Fetch account balances for the active runtime posture ---
            # TradovBox paper balances stay local-only. Live Tradier balance
            # reads are allowed only when the runtime mode is explicitly live.
            if not bool(getattr(self, "_quiet_startup", False)):
                trading_mode = _runtime_trading_mode(self.runtime_context)
                try:
                    paper_snapshot_emitted = _emit_paper_balance_update(self)
                    if trading_mode == "paper" and not paper_snapshot_emitted:
                        _warn_missing_paper_snapshot(self)

                    if _live_account_balance_reads_enabled(self.runtime_context):
                        _emit_live_balance_update(self)
                except Exception:
                    pass

            if self._shutdown_in_progress():
                return

            # --- Fetch live quotes and write to data_file ---
            symbols = _build_quote_symbol_basket()
            try:
                # Use market-data client (always LIVE endpoint) so both paper and
                # live modes fetch real quotes from api.tradier.com.
                mkt_client = _build_market_data_client()
                if mkt_client is None:
                    logger.warning(
                        "MarketDataWorker quote fetch skipped: LIVE market-data "
                        "credentials/client unavailable",
                    )
                    return
                raw = mkt_client.get_quotes(symbols)
                quotes_raw = raw.get("quotes", {}).get("quote", [])
                if isinstance(quotes_raw, dict):
                    quotes_raw = [quotes_raw]
                live_data = {}
                _spy_q_slow: dict = {}
                # Remap Tradier symbols to dashboard widget keys where needed
                for q in quotes_raw:
                    sym = q.get("symbol", "")
                    normalized = _quote_to_live_entry(q)
                    if normalized is not None:
                        key, entry = normalized
                        live_data[key] = entry
                    if sym == "TRAD":
                        _spy_q_slow = q
                # --- RVOL: relative volume vs expected volume at this session fraction ---
                try:
                    _vol = float(_spy_q_slow.get("volume") or 0.0)
                    _adv = float(_spy_q_slow.get("average_volume") or 0.0)
                    if _vol > 0 and _adv > 0:
                        _now = datetime.now(UTC)
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
                _vxv_entry = _fetch_vxv_live_entry()
                if _vxv_entry is not None:
                    live_data["VXV"] = _vxv_entry
                if live_data:
                    import json as _json
                    import time as _time
                    # Stamp wall-clock fetch time so the REAL-TIME badge uses the
                    # time we successfully called Tradier, not Tradier's quote
                    # timestamps (which can lag in quiet markets).
                    live_data["_fetch_time_ms"] = int(_time.time() * 1000)

                    # Keep sparse index symbols authoritative from direct quotes.
                    for _sym in DIRECT_INDEX_REFRESH_SYMBOLS:
                        _refetch_single_symbol_quote(mkt_client, live_data, _sym)

                    # Patch RUT change/change_pct using cached historical prev-close
                    # when Tradier returns null for those fields (its normal behaviour).
                    # Priority: (1) historical cache, (2) infer from IWM change_pct.
                    _rut_entry = live_data.get("RUT")
                    if isinstance(_rut_entry, dict) and not _rut_entry.get("change_available"):
                        _rut_prev = _RUT_PREVCLOSE_CACHE.get("prevclose", 0.0)
                        _rut_last = _rut_entry.get("last", 0.0)
                        if _rut_prev > 0.0 and _rut_last > 0.0:
                            _rut_chg = _rut_last - _rut_prev
                            _rut_chg_pct = (_rut_chg / _rut_prev) * 100.0
                            live_data["RUT"] = {
                                **_rut_entry,
                                "change": round(_rut_chg, 2),
                                "change_pct": round(_rut_chg_pct, 2),
                                "change_available": True,
                            }
                        else:
                            # Fallback: IWM tracks RUT 1:1 in percentage terms
                            _iwm = live_data.get("IWM", {})
                            if isinstance(_iwm, dict) and _iwm.get("change_available") and _rut_last > 0.0:
                                _iwm_pct = _iwm.get("change_pct", 0.0)
                                _rut_chg_from_iwm = round(_rut_last * _iwm_pct / (100.0 + _iwm_pct), 2)
                                live_data["RUT"] = {
                                    **_rut_entry,
                                    "change": _rut_chg_from_iwm,
                                    "change_pct": round(_iwm_pct, 2),
                                    "change_available": True,
                                }

                    # DIA can occasionally lag or be omitted in basket responses.
                    # Repair with a direct one-symbol quote fetch instead of proxying.
                    if _is_symbol_stale(
                        live_data,
                        "DIA",
                        int(live_data["_fetch_time_ms"]),
                        DIA_REFETCH_MAX_AGE_SECONDS,
                    ):
                        if _refetch_single_symbol_quote(mkt_client, live_data, "DIA"):
                            logger.debug("DIA refreshed via direct single-symbol Tradier quote fetch")

                    self.data_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.data_file, "w") as f:
                        _json.dump(live_data, f)
                    # Keep the EOD snapshot current so closing prices are always
                    # preserved for next-morning startup display.
                    _snapshot_file = self.data_file.parent / "eod_snapshot.json"
                    _snapshot_meta = {
                        "_eod_date": datetime.now(UTC).strftime("%Y-%m-%d"),
                        "_eod_fetched_ts": int(_time.time()),
                    }
                    with open(_snapshot_file, "w") as _sf:
                        _json.dump({**live_data, **_snapshot_meta}, _sf)

                    self._emit_spy_market_data_event(live_data.get("TRAD"), _spy_q_slow)
            except Exception:
                pass

            if self._shutdown_in_progress():
                return

            # --- Compute put/call ratio (CPC) from TRAD options chain ---
            # CBOE does not publish CPC via Tradier; we compute it from TRAD chain volume.
            # CPC = total put volume / total call volume for the nearest expiration.
            # Uses the module-level _get_cached_chain() so concurrent callers share
            # one API round-trip per _CHAIN_TTL window (30 s).
            try:
                chain_result = _get_cached_chain(mkt_client)
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
                        # Persist updated live_data with CPC (_fetch_time_ms already set above)
                        self.data_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(self.data_file, "w") as f:
                            import json as _json3
                            _json3.dump(live_data, f)
            except Exception:
                pass

            if self._shutdown_in_progress():
                return

            # --- Fetch 5-min bars for the configured underlying chart symbol ---
            # Only fetch during regular trading hours (9:30-16:00 ET).
            try:
                from datetime import datetime as _dt
                _et_now = _dt.now(ET_TZ)
                if not is_market_hours(_et_now):
                    raise StopIteration  # skip fetch outside RTH
                _last_chart_fetch = float(_TRAD_TIMESALES_FETCH_CACHE.get("last_fetch_mono", 0.0) or 0.0)
                _now_mono = time.monotonic()
                if (_now_mono - _last_chart_fetch) < TRAD_TIMESALES_FETCH_INTERVAL_SECONDS:
                    raise StopIteration
                # Use the ET session date rather than the host clock date.
                # On a UTC-clocked host, date.today() can already be the next
                # calendar day while the market is still in the prior ET session.
                today_open = f"{_et_now.date().isoformat()} 09:30"
                ts_resp = mkt_client.get_time_sales(
                    CHART_UNDERLYING_SYMBOL, interval="5min", start=today_open, session_filter="open",
                )
                # Guard against Tradier returning {"series": null} early in the
                # session (first few bars not yet available).  series may be None
                # or a string "null"; treat both as "no data yet".
                _series = ts_resp.get("series") if isinstance(ts_resp, dict) else None
                if not isinstance(_series, dict):
                    raise StopIteration  # no bars available yet — try again next heartbeat
                candles_raw = _series.get("data", [])
                if isinstance(candles_raw, dict):
                    candles_raw = [candles_raw]
                # Always advance the throttle timestamp so we don't hammer the API
                # even when bars aren't available yet.
                _TRAD_TIMESALES_FETCH_CACHE["last_fetch_mono"] = _now_mono
                if candles_raw:
                    chart_file = self.data_file.parent / f"{CHART_UNDERLYING_SYMBOL.lower()}_5min_chart.json"
                    with open(chart_file, "w") as f:
                        import json as _json2
                        _json2.dump(candles_raw, f)
            except StopIteration:
                pass  # outside RTH or no bars yet — try again next heartbeat
            except Exception:
                pass

            if self._shutdown_in_progress():
                return

            # --- Fetch previous trading day's daily OHLC for pivot anchoring ---
            # Pivots must use yesterday's H/L/C (fixed for the whole session).
            # We try a 5-day lookback so weekends/holidays are handled correctly.
            try:
                from datetime import date as _date2, timedelta as _td
                _today_str = _date2.today().isoformat()
                if _TRAD_PREVDAY_FETCH_CACHE.get("date") == _today_str:
                    raise StopIteration
                _prev_start = (_date2.today() - _td(days=5)).isoformat()
                _prev_end   = (_date2.today() - _td(days=1)).isoformat()
                _hist_resp = mkt_client.get_historical_quotes(
                    CHART_UNDERLYING_SYMBOL, interval="daily", start=_prev_start, end=_prev_end,
                )
                _hist_day = _hist_resp.get("history", {}).get("day", None)
                if isinstance(_hist_day, list) and _hist_day:
                    _hist_day = _hist_day[-1]   # most recent completed session
                if isinstance(_hist_day, dict) and _hist_day.get("high"):
                    _prev_day_file = self.data_file.parent / f"{CHART_UNDERLYING_SYMBOL.lower()}_prev_day.json"
                    with open(_prev_day_file, "w") as _pf:
                        import json as _json4
                        _json4.dump({
                            "date":  _hist_day.get("date", ""),
                            "high":  float(_hist_day["high"]),
                            "low":   float(_hist_day["low"]),
                            "close": float(_hist_day["close"]),
                        }, _pf)
                    _TRAD_PREVDAY_FETCH_CACHE["date"] = _today_str
            except StopIteration:
                pass
            except Exception:
                pass  # non-critical — pivot fallback is today's intraday range

            if self._shutdown_in_progress():
                return

            # --- Fetch RUT previous-day close for day-change derivation ---
            # Tradier does not return change/prevclose for RUT in its quote
            # endpoint; pull it from historical data once per session.
            try:
                from datetime import date as _date3, timedelta as _td3
                _today_str = _date3.today().isoformat()
                if _RUT_PREVCLOSE_CACHE.get("date") != _today_str:
                    _rut_prev_start = (_date3.today() - _td3(days=5)).isoformat()
                    _rut_prev_end   = (_date3.today() - _td3(days=1)).isoformat()
                    # Try RUT direct first; fall back to IWM (tracks RUT) if Tradier
                    # does not support historical quotes for index symbols.
                    _rut_prevclose_found = False
                    for _rut_hist_sym in ("RUT", "IWM"):
                        try:
                            _rut_hist_resp = mkt_client.get_historical_quotes(
                                _rut_hist_sym, interval="daily",
                                start=_rut_prev_start, end=_rut_prev_end,
                            )
                        except Exception:
                            continue
                        _rut_hist_day = _rut_hist_resp.get("history", {}).get("day", None)
                        if isinstance(_rut_hist_day, list) and _rut_hist_day:
                            _rut_hist_day = _rut_hist_day[-1]
                        if isinstance(_rut_hist_day, dict) and _rut_hist_day.get("close"):
                            _raw_close = float(_rut_hist_day["close"])
                            # IWM closes at ~1/5 of RUT; scale up so delta math
                            # is correct against the raw RUT quote (~2800).
                            if _rut_hist_sym == "IWM" and _raw_close < 500:
                                # Derive scaling factor: RUT / IWM ≈ live ratio
                                _live_rut = (live_data.get("RUT") or {}).get("last", 0.0)
                                _live_iwm = (live_data.get("IWM") or {}).get("last", 0.0)
                                if _live_rut > 0 and _live_iwm > 0:
                                    _scale = _live_rut / _live_iwm
                                    _raw_close = _raw_close * _scale
                                else:
                                    continue  # can't scale without live prices
                            _RUT_PREVCLOSE_CACHE["prevclose"] = round(_raw_close, 2)
                            _RUT_PREVCLOSE_CACHE["date"] = _today_str
                            _rut_prevclose_found = True
                            break
                    if not _rut_prevclose_found:
                        logger.warning("RUT: could not derive prev-close — day change will show as --")
            except Exception:
                pass  # non-critical
        except Exception:
            pass

    def _fetch_quotes_fast(self):
        """Lightweight 10-second quote refresh — prices only, no options chain or chart bars.

        Merges fresh prices into live_data.json so the 1-second _real_data_timer
        picks them up immediately without overwriting CPC or other computed keys.
        """
        try:
            if self._shutdown_in_progress():
                return

            import json as _json
            from dotenv import load_dotenv
            load_dotenv(override=True)
            if not TRADIER_AVAILABLE:
                return
            # Use market-data client (always LIVE endpoint) so both paper and
            # live modes fetch quotes from api.tradier.com.
            client = _build_market_data_client()
            if client is None:
                return
            symbols = _build_quote_symbol_basket()
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
                normalized = _quote_to_live_entry(q)
                if normalized is not None:
                    key, entry = normalized
                    existing[key] = entry
                    updated = True
                if sym == "TRAD":
                    _spy_q_raw = q

            # --- RVOL: relative volume = current session volume / expected volume ---
            # Expected volume = ADV × fraction of trading session elapsed (390 min total).
            try:
                _vol = float(_spy_q_raw.get("volume") or 0.0)
                _adv = float(_spy_q_raw.get("average_volume") or 0.0)
                if _vol > 0 and _adv > 0:
                    _now = datetime.now(UTC)
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

            # Keep sparse index symbols authoritative from direct quotes, even
            # when basket responses are temporarily sparse.
            for _sym in DIRECT_INDEX_REFRESH_SYMBOLS:
                if _refetch_single_symbol_quote(client, existing, _sym):
                    updated = True

            # Patch RUT change/change_pct from historical prev-close cache.
            # Falls back to IWM change_pct when historical cache is unavailable.
            _rut_e = existing.get("RUT")
            if isinstance(_rut_e, dict) and not _rut_e.get("change_available"):
                _rut_p = _RUT_PREVCLOSE_CACHE.get("prevclose", 0.0)
                _rut_last_f = _rut_e.get("last", 0.0)
                if _rut_p > 0.0 and _rut_last_f > 0.0:
                    _rc = _rut_last_f - _rut_p
                    existing["RUT"] = {
                        **_rut_e,
                        "change": round(_rc, 2),
                        "change_pct": round((_rc / _rut_p) * 100.0, 2),
                        "change_available": True,
                    }
                    updated = True
                else:
                    # IWM fallback: RUT and IWM have identical daily %change
                    _iwm_f = existing.get("IWM", {})
                    if isinstance(_iwm_f, dict) and _iwm_f.get("change_available") and _rut_last_f > 0.0:
                        _iwm_pct_f = _iwm_f.get("change_pct", 0.0)
                        _rc_f = round(_rut_last_f * _iwm_pct_f / (100.0 + _iwm_pct_f), 2)
                        existing["RUT"] = {
                            **_rut_e,
                            "change": _rc_f,
                            "change_pct": round(_iwm_pct_f, 2),
                            "change_available": True,
                        }
                        updated = True

            if updated:
                if self._shutdown_in_progress():
                    return

                import time as _time_fast
                existing["_fetch_time_ms"] = int(_time_fast.time() * 1000)

                # Keep DIA direct (no proxy): if batch data is stale/missing, pull DIA alone.
                if _is_symbol_stale(
                    existing,
                    "DIA",
                    int(existing["_fetch_time_ms"]),
                    DIA_REFETCH_MAX_AGE_SECONDS,
                ):
                    if _refetch_single_symbol_quote(client, existing, "DIA"):
                        logger.debug("DIA refreshed in fast-fetch via direct single-symbol Tradier quote fetch")

                self.data_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.data_file, "w") as _f:
                    _json.dump(existing, _f)

                self._emit_spy_market_data_event(existing.get("TRAD"), _spy_q_raw)

            # --- Market internals ($TICK, $ADD, $TRIN, $VOLD) ---
            # Sourced via Playwright/TradingView scraping in TradovS11_TradingViewInternals.py
            # (USI:TICK, USI:ADD, USI:TRIN.NY, USI:VOLD).  Values are published through
            # TradovS07_CustomMetricsOrchestrator and written to live_data.json;
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

            # ── Quiet-window gate (5:00 PM – 9:00 AM ET) ─────────────────────
            # Between 5PM and 9AM ET no external API calls are made.  The last
            # eod_snapshot.json written during the previous trading session is
            # served directly so the dashboard shows genuine closing prices
            # without generating any Tradier or yfinance traffic after hours.
            try:
                from datetime import time as _dt_time  # noqa: PLC0415
                _et_now_t = datetime.now(ET_TZ).time()
                _in_quiet = _et_now_t >= _dt_time(17, 0) or _et_now_t < _dt_time(9, 0)
            except Exception:
                _in_quiet = False
            if _in_quiet:
                _snapshot_file = self.data_file.parent / "eod_snapshot.json"
                if _snapshot_file.exists():
                    try:
                        _cached = _json.loads(_snapshot_file.read_text())
                        # Strip EOD metadata; dashboard reads live_data.json
                        _live_data_out = {
                            k: v for k, v in _cached.items()
                            if not k.startswith("_eod_")
                        }
                        _live_data_out["_fetch_time_ms"] = int(time.time() * 1000)
                        self.data_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(self.data_file, "w") as _f:
                            _json.dump(_live_data_out, _f)
                        self.log_message.emit("📊 EOD data served from previous session's cache")
                        self.market_data_status_changed.emit("EOD")
                        self.eod_snapshot_fetched.emit(True)
                        return
                    except Exception as _cache_err:
                        logger.debug(
                            "📊 EOD cache load failed (%s) — falling back to Tradier API",
                            _cache_err,
                        )
                else:
                    logger.debug(
                        "📊 EOD cache not present — proceeding with API call (first launch or cache cleared)"
                    )
            # ── End quiet-window gate ─────────────────────────────────────────

            if not TRADIER_AVAILABLE:
                self.eod_snapshot_fetched.emit(False)
                return
            # Use market-data client (always LIVE endpoint) so both paper and
            # live modes fetch EOD quotes from api.tradier.com.
            client = _build_market_data_client()
            if client is None:
                logger.warning("📊 EOD snapshot skipped — TRADIER_LIVE_API_KEY / TRADIER_ACCOUNT_ID not set")  # noqa: E501
                self.eod_snapshot_fetched.emit(False)
                return
            symbols = _build_quote_symbol_basket()
            raw = client.get_quotes(symbols)
            quotes_raw = raw.get("quotes", {}).get("quote", [])
            if isinstance(quotes_raw, dict):
                quotes_raw = [quotes_raw]
            live_data: dict = {}
            _vxv_source: str | None = None
            for q in quotes_raw:
                sym = q.get("symbol", "")
                last = float(q.get("last") or q.get("close") or 0.0)
                change = float(q.get("change") or 0.0)
                change_pct = float(q.get("change_percentage") or 0.0)
                # Tradier returns null change for index symbols (e.g. SPX).
                # Fall back to last - prevclose so CHG/CHG% display correctly.
                if change == 0.0 and last > 0.0:
                    prevclose = float(q.get("prevclose") or 0.0)
                    if prevclose > 0.0:
                        change = last - prevclose
                        change_pct = (change / prevclose) * 100.0
                timestamp_ms = _freshest_quote_timestamp_ms(q)
                if last:
                    key = _SYMBOL_REMAP.get(sym, sym)
                    live_data[key] = {
                        "last": last,
                        "change": change,
                        "change_pct": change_pct,
                        "timestamp_ms": timestamp_ms,
                    }
            _vxv_entry = _fetch_vxv_live_entry()
            if _vxv_entry is not None:
                live_data["VXV"] = _vxv_entry
                _vxv_source = str(_vxv_entry.get("source") or "yfinance_vix3m")
            if live_data:
                import time as _time
                _now_ms = int(_time.time() * 1000)
                _snapshot_meta = {
                    "_eod_date": datetime.now(UTC).strftime("%Y-%m-%d"),
                    "_eod_fetched_ts": int(_time.time()),
                }

                # VXV is cataloged as event-only (not fetched from Tradier). When
                # available from a previous persisted snapshot, carry it forward so
                # EOD consumers have continuity across restarts.
                _vxv_fallback_applied = False
                if "VXV" not in live_data:
                    _fallback_paths = (
                        self.data_file.parent / "live_data.json",
                        self.data_file.parent / "eod_snapshot.json",
                    )
                    for _fallback_path in _fallback_paths:
                        try:
                            _payload = _json.loads(_fallback_path.read_text())
                        except (OSError, ValueError, TypeError):
                            continue
                        _vxv_entry = _payload.get("VXV") if isinstance(_payload, dict) else None
                        if not isinstance(_vxv_entry, dict):
                            continue
                        _vxv_last = float(_vxv_entry.get("last") or 0.0)
                        if _vxv_last <= 0.0:
                            continue
                        live_data["VXV"] = {
                            "last": _vxv_last,
                            "change": float(_vxv_entry.get("change") or 0.0),
                            "change_pct": float(_vxv_entry.get("change_pct") or 0.0),
                            "timestamp_ms": _vxv_entry.get("timestamp_ms"),
                            "change_available": bool(_vxv_entry.get("change_available", True)),
                            "source": "cached_vxv_fallback",
                        }
                        _vxv_fallback_applied = True
                        _vxv_source = "cached_vxv_fallback"
                        break

                self.data_file.parent.mkdir(parents=True, exist_ok=True)
                # Include _fetch_time_ms so the toolbar freshness check has a
                # reference time; SPX/$DJI use a 1800 s window so they display
                # even when Tradier returns a lagging index timestamp.
                _live_data_out = {**live_data, "_fetch_time_ms": _now_ms}
                with open(self.data_file, "w") as _f:
                    _json.dump(_live_data_out, _f)
                # Write a dedicated EOD snapshot so the dashboard can display
                # yesterday's closing prices immediately at next startup,
                # before the Tradier API call completes.
                _snapshot_file = self.data_file.parent / "eod_snapshot.json"
                with open(_snapshot_file, "w") as _sf:
                    _json.dump({**_live_data_out, **_snapshot_meta}, _sf)

                # Persist per-symbol EOD close snapshots used by startup workflows
                # and operational audit checks.
                _symbol_prev_files = {
                    "SPY": "spy_prev_day.json",
                    "SPX": "spx_prev_day.json",
                    "$DJI": "dji_prev_day.json",
                    "DIA": "dia_prev_day.json",
                }
                _sidecar_saved: list[str] = []
                _sidecar_skipped: list[str] = []
                for _sym, _fname in _symbol_prev_files.items():
                    _entry = _live_data_out.get(_sym)
                    if not isinstance(_entry, dict):
                        _sidecar_skipped.append(_sym)
                        continue
                    _last = float(_entry.get("last") or 0.0)
                    if _last <= 0.0:
                        _sidecar_skipped.append(_sym)
                        continue
                    _prev_file = self.data_file.parent / _fname
                    with open(_prev_file, "w") as _pf:
                        _json.dump(
                            {
                                "date": _snapshot_meta["_eod_date"],
                                "close": _last,
                                "change": float(_entry.get("change") or 0.0),
                                "change_pct": float(_entry.get("change_pct") or 0.0),
                                "timestamp_ms": _entry.get("timestamp_ms"),
                                "source": "tradier_eod_snapshot",
                            },
                            _pf,
                        )
                    _sidecar_saved.append(_sym)

                logger.info("📊 EOD snapshot: %d symbols saved (%s)", len(live_data), _snapshot_meta["_eod_date"])  # noqa: E501
                logger.info(
                    "📦 EOD sidecars saved=%s skipped=%s",
                    ",".join(sorted(_sidecar_saved)) if _sidecar_saved else "none",
                    ",".join(sorted(_sidecar_skipped)) if _sidecar_skipped else "none",
                )
                if _vxv_fallback_applied:
                    logger.info("📈 EOD VXV fallback applied from cached snapshot")
                elif _vxv_source is not None:
                    logger.info("📈 EOD VXV refreshed from %s", _vxv_source)
                else:
                    logger.info("📈 EOD VXV unavailable (event-only source did not provide cached value)")
                self.market_data_status_changed.emit("EOD")
                self.eod_snapshot_fetched.emit(True)
            else:
                logger.warning("📊 EOD snapshot: Tradier returned no valid prices")
                self.eod_snapshot_fetched.emit(False)
        except Exception as _e:
            logger.warning("📊 EOD snapshot fetch failed: %s", _e)
            self.eod_snapshot_fetched.emit(False)

    def _init_simulation_data(self):
        """Legacy no-op: synthetic quote seeding is disabled."""
        return

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
        self._quiet_startup = bool(getattr(self, "_quiet_startup", False))
        if not self._quiet_startup:
            logger.info("🚀 Starting Thread-Safe Market Data Worker with heartbeat monitoring...")
        self._shutdown_requested = False

        # CRITICAL: Create QTimers in the worker thread, not the main thread
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._emit_data)

        self.market_hours_timer = QTimer(self)
        self.market_hours_timer.timeout.connect(self._check_market_hours)
        self.market_hours_timer.start(60000)

        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self._heartbeat_check)
        self.heartbeat_timer.start(HEARTBEAT_INTERVAL)

        self.heartbeat_warning_timer = QTimer(self)
        self.heartbeat_warning_timer.timeout.connect(self._heartbeat_warning)

        try:
            connected, mode = check_api_connection(self.runtime_context)
            self.api_connected = connected

            if connected:
                self.connection_status_changed.emit(True, f"API CONNECTED ({mode})")
                # Emit "LIVE" or "PAPER" (not "REAL-TIME") so on_market_data_status_changed
                # sets mkt_data_connected = True and turns the TRADIER DATA label green.
                _startup_sandbox = "SANDBOX" in mode.upper() or "PAPER" in mode.upper()
                _startup_mkt = "PAPER" if _startup_sandbox else "LIVE"
                self.market_data_status_changed.emit(_startup_mkt)
                self.heartbeat_status_changed.emit("connected")  # Green heart
                # Defer the first full fetch so the dashboard can finish
                # rendering before network hydration begins.
                QTimer.singleShot(1500, self.fetch_requested.emit)
                if not self._quiet_startup:
                    logger.info("✅ Tradier API connected at startup: %s", mode)
            else:
                self.connection_status_changed.emit(False, mode or "API DISCONNECTED")
                self.market_data_status_changed.emit("NONE")
                self.heartbeat_status_changed.emit("disconnected")  # Red heart
                if not self._quiet_startup:
                    logger.info("❌ Tradier API disconnected at startup: %s", mode)

        except Exception as e:
            if not self._quiet_startup:
                logger.info("⚠️ Startup connection check error: %s", e)
            self.api_connected = False
            self.connection_status_changed.emit(False, f"API DISCONNECTED: {e}")
            self.market_data_status_changed.emit("NONE")
            self.heartbeat_status_changed.emit("error")  # Red heart

        # Always queue balance fetch; queue EOD snapshot outside market hours
        # so the dashboard shows genuine last-close prices when launched pre/post session.
        if not is_market_hours():
            QTimer.singleShot(500, self._fetch_eod_snapshot)
        QTimer.singleShot(2000, self._fetch_balance_only)

    @Slot()
    def run_full_fetch(self):
        """Execute a queued full fetch unless shutdown has already begun."""
        if self._shutdown_in_progress():
            return
        self._fetch_live_data_from_tradier()

    @Slot()
    def run_fast_fetch(self):
        """Execute a queued fast fetch unless shutdown has already begun."""
        if self._shutdown_in_progress():
            return
        self._fetch_quotes_fast()

    def _emit_data(self):
        """Emit current market data"""
        with QMutexLocker(self.data_mutex):
            data_copy = self.market_data.copy()

        if not data_copy:
            return

        self.data_updated.emit(data_copy)

    def _update_simulation_data(self, data: dict):
        """Legacy no-op: synthetic quote generation is disabled."""
        return

    def force_connect(self):
        """Manual connect using the same read-only Tradier probe as startup."""
        logger.info("🔥 Manual connect requested")

        # Check actual connection
        connected, mode = check_api_connection(self.runtime_context)
        self.api_connected = connected

        if connected:
            self.connection_status_changed.emit(True, f"API CONNECTED ({mode})")
            is_sandbox = "SANDBOX" in mode.upper() or "PAPER" in mode.upper()
            market_status = "PAPER" if is_sandbox else "LIVE"
            warmup_window = _is_live_data_warmup_window()
            if not is_market_hours() and not warmup_window:
                market_status = "EOD"
            self.market_data_status_changed.emit(market_status)
            self.heartbeat_status_changed.emit("connected")
            # Hydrate the cached snapshot immediately after a successful manual probe.
            if is_market_hours() or warmup_window:
                self.fetch_requested.emit()
            else:
                self._fetch_eod_snapshot()
                self._fetch_balance_only()
            return True
        self.heartbeat_status_changed.emit("disconnected")
        self.connection_status_changed.emit(False, mode or "API DISCONNECTED")
        self.market_data_status_changed.emit("NONE")
        return False

    def force_disconnect(self):
        """Manual disconnect"""
        logger.info("🔥 Manual disconnect requested")
        self.api_connected = False
        self.connection_status_changed.emit(False, "API DISCONNECTED: manual disconnect")
        self.market_data_status_changed.emit("NONE")

    @Slot()
    def pause_periodic_updates(self):
        """Stop the worker-owned periodic data timer from the worker thread."""
        if self.update_timer:
            self.update_timer.stop()

    @Slot()
    def stop(self):
        """Stop worker and all timers"""
        logger.info("🛑 Stopping worker and heartbeat monitoring...")
        self._shutdown_requested = True
        if self.update_timer:
            self.update_timer.stop()
        if self.market_hours_timer:
            self.market_hours_timer.stop()
        if self.heartbeat_timer:
            self.heartbeat_timer.stop()
        if self.heartbeat_warning_timer:
            self.heartbeat_warning_timer.stop()
        closed_clients = _close_cached_tradier_clients()
        if closed_clients:
            logger.info(
                "Closed %d cached Tradier market-data client(s) during worker shutdown",
                closed_clients,
            )


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
    "_build_quote_symbol_basket",
    "_coerce_epoch_ms",
    "_datetime_from_epoch_ms",
    "_freshest_live_data_timestamp",
    "_freshest_quote_timestamp_ms",
    "_get_cached_chain",
    "check_api_connection",
]
