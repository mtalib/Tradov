#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC28_MassiveHistoricalDownloader.py
Purpose: Bulk historical data downloader from Massive (Polygon) REST API

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-03-19 Time: 12:00:00

Module Description:
    Downloads historical SPY options, equity, and index data from the
    Massive (formerly Polygon.io) REST API and stores it as Parquet files
    for backtesting.

    Capabilities:
        - SPY daily and minute bars
        - All SPY option contracts daily and minute bars
        - Index bars (VIX, SPX, DJI, NDX, COMP, RUT)
        - Contract enumeration with pagination
        - Checkpoint/resume for crash recovery
        - CLI interface: backfill, daily, single, validate, resume modes

    This module is separate from SpyderC27_MassiveClient (which handles
    live/real-time data). It uses requests directly rather than the
    polygon/massive SDK for full control over pagination and retries.

    Rate limiting: token-bucket at MASSIVE_REST_RPS (default 3 req/s).

Usage:
    python -m SpyderC_MarketData.SpyderC28_MassiveHistoricalDownloader \\
        --mode backfill --start 2025-01-02 --end 2025-12-31

    python -m SpyderC_MarketData.SpyderC28_MassiveHistoricalDownloader \\
        --mode daily

    python -m SpyderC_MarketData.SpyderC28_MassiveHistoricalDownloader \\
        --mode validate --start 2025-01-02 --end 2025-12-31
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import argparse
import json
import os
import re
import sys
import time as _time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import polars as pl
import requests
from dotenv import load_dotenv

try:
    import exchange_calendars as xcals

    _NYSE = xcals.get_calendar("XNYS")
    HAS_CALENDAR = True
except ImportError:
    _NYSE = None
    HAS_CALENDAR = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

    logger = SpyderLogger.get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================
BASE_URL = "https://api.polygon.io"
DEFAULT_RPS = 0.08  # ~5 calls/minute (actual Massive/Polygon API limit)
MAX_RETRIES = 5
RETRY_BASE_DELAY = 15.0  # Long backoff for rate-limited API
CONTRACTS_PAGE_LIMIT = 250
AGGS_RESULT_LIMIT = 50000
DEFAULT_UNDERLYING = "SPY"
INDEX_TICKERS = ["I:NDX", "I:COMP"]

# Parquet subdirectory layout
PARQUET_DIRS = {
    "spy_day": "spy_underlying/day_aggs",
    "spy_minute": "spy_underlying/minute_aggs",
    "options_day": "spy_options/day_aggs",
    "options_minute": "spy_options/minute_aggs",
    "indices_day": "indices/day_aggs",
    "indices_minute": "indices/minute_aggs",
    "contracts": "contracts",
}


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class OptionContract:
    """Parsed OPRA option contract."""

    underlying: str
    expiration: date
    call_put: str
    strike: float


@dataclass
class DownloadState:
    """Checkpoint state for resumable downloads."""

    last_completed_date: str | None = None
    dates_completed: list[str] | None = None
    current_date: str | None = None
    current_phase: str | None = None
    contracts_completed: int = 0
    contracts_total: int = 0
    started_at: str | None = None
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.dates_completed is None:
            self.dates_completed = []
        if self.errors is None:
            self.errors = []


# ==============================================================================
# TOKEN BUCKET RATE LIMITER
# ==============================================================================
class _SlidingWindowLimiter:
    """Sliding-window rate limiter matching Polygon API limits.

    The API enforces N calls per 60-second sliding window.
    Tracks timestamps of recent calls and waits when the
    window is full.
    """

    def __init__(self, calls_per_minute: int = 5) -> None:
        self._max_calls = calls_per_minute
        self._window = 61.0  # seconds (60 + 1s margin)
        self._timestamps: list[float] = []

    def wait(self) -> None:
        """Block until a call slot is available in the current window."""
        now = _time.monotonic()
        # Purge timestamps outside the window
        cutoff = now - self._window
        self._timestamps = [t for t in self._timestamps if t > cutoff]

        if len(self._timestamps) >= self._max_calls:
            # Wait until the oldest timestamp exits the window
            wait_until = self._timestamps[0] + self._window
            sleep_time = wait_until - now
            if sleep_time > 0:
                logger.info(f"  Rate limit: waiting {sleep_time:.0f}s...")
                _time.sleep(sleep_time)  # thread-safe: time.sleep() intentional

        self._timestamps.append(_time.monotonic())


# ==============================================================================
# OPRA TICKER PARSER
# ==============================================================================
_OPRA_RE = re.compile(r"^O:([A-Z]+)(\d{6})([CP])(\d{8})$")


def parse_opra_ticker(ticker: str) -> OptionContract:
    """
    Parse an OPRA option ticker symbol.

    Args:
        ticker: OPRA ticker (e.g., "O:SPY260320C00565000").

    Returns:
        Parsed OptionContract dataclass.

    Raises:
        ValueError: If the ticker format is invalid.
    """
    m = _OPRA_RE.match(ticker)
    if not m:
        raise ValueError(f"Invalid OPRA ticker: {ticker}")
    return OptionContract(
        underlying=m.group(1),
        expiration=date(
            year=2000 + int(m.group(2)[:2]),
            month=int(m.group(2)[2:4]),
            day=int(m.group(2)[4:6]),
        ),
        call_put=m.group(3),
        strike=int(m.group(4)) / 1000.0,
    )


# ==============================================================================
# MAIN DOWNLOADER CLASS
# ==============================================================================
class MassiveHistoricalDownloader:
    """
    Bulk historical data downloader from Massive (Polygon) REST API.

    Downloads SPY equity, options, and index data and stores as Parquet
    files in the configured backtest data directory.

    NOTE: The Massive/Polygon API has a strict limit of 5 calls/minute.
    Options data download is slow by design (~12s per API call).
    Use strike_range to limit contracts to near-the-money strikes.

    Args:
        api_key: Massive API key. Falls back to MASSIVE_API_KEY env var.
        data_root: Root directory for Parquet output. Falls back to
                   BACKTEST_DATA_ROOT env var.
        rps: Requests per second rate limit (default 0.08 = 5/min).
        strike_range: Download options within ±N strikes of ATM (default 50).
                      Set to 0 for all strikes.
    """

    def __init__(
        self,
        api_key: str | None = None,
        data_root: str | None = None,
        rps: float | None = None,
        strike_range: float = 50.0,
        max_dte: int = 45,
    ) -> None:
        self._api_key = api_key or os.environ.get("MASSIVE_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "Massive API key required. Set MASSIVE_API_KEY or pass api_key."
            )

        self._data_root = Path(
            data_root
            or os.environ.get("BACKTEST_DATA_ROOT", "")
            or "Spyder-Backtest"
        )
        self._strike_range = strike_range
        self._max_dte = max_dte

        rps = rps or float(os.environ.get("MASSIVE_REST_RPS", str(DEFAULT_RPS)))
        calls_per_min = max(1, round(rps * 60)) if rps > 0 else 5
        self._bucket = _SlidingWindowLimiter(calls_per_min)

        self._session = requests.Session()
        self._session.params = {"apiKey": self._api_key}  # type: ignore[assignment]

        self._checkpoint_dir = self._data_root / "checkpoints"
        self._checkpoint_path = self._checkpoint_dir / "download_state.json"

        # Ensure directories exist
        for subdir in PARQUET_DIRS.values():
            (self._data_root / "parquet" / subdir).mkdir(parents=True, exist_ok=True)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self._call_count = 0
        logger.info(
            f"MassiveHistoricalDownloader initialized "
            f"(data_root={self._data_root}, rps={rps})"
        )

    def close(self) -> None:
        """Close the HTTP session and release resources."""
        if self._session:
            self._session.close()
            logger.info("MassiveHistoricalDownloader session closed")

    def __enter__(self) -> "MassiveHistoricalDownloader":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    # ==========================================================================
    # HTTP HELPERS
    # ==========================================================================

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Make a rate-limited GET request with retries.

        Args:
            url: Full URL or path (will be prefixed with BASE_URL if relative).
            params: Additional query parameters.

        Returns:
            Parsed JSON response dict.

        Raises:
            requests.HTTPError: After all retries exhausted.
        """
        if url.startswith("/"):
            url = BASE_URL + url

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            self._bucket.wait()
            self._call_count += 1
            try:
                resp = self._session.get(url, params=params, timeout=30)
                if resp.status_code == 429:
                    wait = RETRY_BASE_DELAY * (2 ** (attempt + 1))
                    logger.warning(f"Rate limited (429). Waiting {wait}s...")
                    _time.sleep(wait)  # thread-safe: time.sleep() intentional
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"Request error (attempt {attempt + 1}/{MAX_RETRIES}): "
                        f"{exc}. Retrying in {wait}s..."
                    )
                    _time.sleep(wait)  # thread-safe: time.sleep() intentional

        if last_exc is not None:
            raise last_exc
        raise requests.HTTPError(f"Rate limited after {MAX_RETRIES} retries: {url}")

    # ==========================================================================
    # TRADING CALENDAR
    # ==========================================================================

    @staticmethod
    def is_trading_day(dt: date) -> bool:
        """Check if a date is a NYSE trading day."""
        if dt.weekday() >= 5:
            return False
        if HAS_CALENDAR and _NYSE is not None:
            import pandas as pd

            try:
                return _NYSE.is_session(pd.Timestamp(dt))
            except Exception:
                return dt.weekday() < 5
        return True

    def _trading_days(self, start: date, end: date) -> list[date]:
        """Return list of trading days in [start, end]."""
        days = []
        current = start
        while current <= end:
            if self.is_trading_day(current):
                days.append(current)
            current += timedelta(days=1)
        return days

    # ==========================================================================
    # DATA FETCHING
    # ==========================================================================

    def fetch_bars(
        self,
        ticker: str,
        timespan: str,
        start: date,
        end: date,
        adjusted: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Fetch OHLCV bars for a ticker.

        Args:
            ticker: Symbol (e.g., "SPY", "O:SPY260321C00580000", "I:VIX").
            timespan: "day" or "minute".
            start: Start date (inclusive).
            end: End date (inclusive).
            adjusted: Whether to request split-adjusted data.

        Returns:
            List of bar dicts with keys: o, h, l, c, v, vw, t, n.
        """
        url = (
            f"/v2/aggs/ticker/{ticker}/range/1/{timespan}"
            f"/{start.isoformat()}/{end.isoformat()}"
        )
        params = {
            "adjusted": str(adjusted).lower(),
            "sort": "asc",
            "limit": str(AGGS_RESULT_LIMIT),
        }
        data = self._get(url, params)
        return data.get("results", [])

    def fetch_contracts(
        self,
        underlying: str,
        expiration_date: date | None = None,
        as_of_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        List all option contracts for an underlying, with pagination.

        Args:
            underlying: Underlying ticker (e.g., "SPY").
            expiration_date: Filter by specific expiration date.
            as_of_date: Show contracts as they existed on this date.

        Returns:
            List of contract dicts with ticker, strike_price, contract_type, etc.
        """
        params: dict[str, Any] = {
            "underlying_ticker": underlying,
            "limit": str(CONTRACTS_PAGE_LIMIT),
        }
        if expiration_date:
            params["expiration_date"] = expiration_date.isoformat()
        if as_of_date:
            params["as_of"] = as_of_date.isoformat()

        all_contracts: list[dict[str, Any]] = []
        url: str | None = f"/v3/reference/options/contracts"

        while url:
            data = self._get(url, params if url.startswith("/") else None)
            results = data.get("results", [])
            all_contracts.extend(results)
            next_url = data.get("next_url")
            if next_url:
                url = next_url
            else:
                url = None

        return all_contracts

    def fetch_active_expirations(
        self,
        underlying: str,
        target_date: date,
    ) -> list[date]:
        """
        Discover all option expirations that were active on a given date.

        Fetches contracts as-of the target date with no expiration filter,
        then extracts unique expiration dates.

        Args:
            underlying: Underlying ticker (e.g., "SPY").
            target_date: The trading date to query.

        Returns:
            Sorted list of unique expiration dates.
        """
        contracts = self.fetch_contracts(
            underlying, as_of_date=target_date
        )
        exps = set()
        for c in contracts:
            exp_str = c.get("expiration_date", "")
            if exp_str:
                try:
                    exps.add(date.fromisoformat(exp_str))
                except ValueError:
                    pass
        return sorted(exps)

    # ==========================================================================
    # PARQUET WRITING
    # ==========================================================================

    def _bars_to_df(
        self, bars: list[dict[str, Any]], ticker: str
    ) -> pl.DataFrame:
        """Convert REST API bar results to a polars DataFrame."""
        if not bars:
            return pl.DataFrame(
                schema={
                    "ticker": pl.Utf8,
                    "timestamp": pl.Datetime("ms"),
                    "open": pl.Float64,
                    "high": pl.Float64,
                    "low": pl.Float64,
                    "close": pl.Float64,
                    "volume": pl.Int64,
                    "vwap": pl.Float64,
                    "transactions": pl.Int64,
                }
            )

        rows = []
        for bar in bars:
            rows.append(
                {
                    "ticker": ticker,
                    "open": bar.get("o"),
                    "high": bar.get("h"),
                    "low": bar.get("l"),
                    "close": bar.get("c"),
                    "volume": bar.get("v", 0),
                    "vwap": bar.get("vw"),
                    "timestamp_ms": bar.get("t", 0),
                    "transactions": bar.get("n", 0),
                }
            )

        df = pl.DataFrame(rows)
        df = df.with_columns(
            pl.col("open").cast(pl.Float64),
            pl.col("high").cast(pl.Float64),
            pl.col("low").cast(pl.Float64),
            pl.col("close").cast(pl.Float64),
            pl.col("volume").cast(pl.Int64),
            pl.col("vwap").cast(pl.Float64),
            pl.col("transactions").cast(pl.Int64),
            pl.col("timestamp_ms").cast(pl.Datetime("ms")).alias("timestamp"),
        ).drop("timestamp_ms")
        return df

    def _write_parquet(
        self, df: pl.DataFrame, subdir: str, filename: str
    ) -> Path:
        """Write a DataFrame to a Parquet file under data_root/parquet/."""
        path = self._data_root / "parquet" / subdir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(str(path), compression="zstd")
        return path

    # ==========================================================================
    # CHECKPOINT / RESUME
    # ==========================================================================

    def _load_checkpoint(self) -> DownloadState:
        """Load checkpoint state from disk."""
        if self._checkpoint_path.exists():
            with open(self._checkpoint_path) as f:
                data = json.load(f)
            return DownloadState(**data)
        return DownloadState()

    def _save_checkpoint(self, state: DownloadState) -> None:
        """Persist checkpoint state to disk."""
        with open(self._checkpoint_path, "w") as f:
            json.dump(
                {
                    "last_completed_date": state.last_completed_date,
                    "dates_completed": state.dates_completed,
                    "current_date": state.current_date,
                    "current_phase": state.current_phase,
                    "contracts_completed": state.contracts_completed,
                    "contracts_total": state.contracts_total,
                    "started_at": state.started_at,
                    "errors": state.errors,
                },
                f,
                indent=2,
            )

    # ==========================================================================
    # DOWNLOAD PIPELINE — ONE DAY
    # ==========================================================================

    def download_day(
        self,
        target_date: date,
        skip_underlying: bool = False,
        skip_indices: bool = False,
        skip_options: bool = False,
    ) -> dict[str, Any]:
        """
        Download all data for a single trading day.

        Args:
            target_date: The trading day to download.
            skip_underlying: Skip SPY equity bars.
            skip_indices: Skip index bars (VIX, SPX, etc.).
            skip_options: Skip option contract bars.

        Returns:
            Summary dict with row counts and file paths.
        """
        date_str = target_date.isoformat()
        summary: dict[str, Any] = {"date": date_str, "files": {}, "errors": []}

        # --- SPY underlying ---
        if not skip_underlying:
            for timespan, key in [("day", "spy_day"), ("minute", "spy_minute")]:
                try:
                    bars = self.fetch_bars(
                        DEFAULT_UNDERLYING, timespan, target_date, target_date
                    )
                    df = self._bars_to_df(bars, DEFAULT_UNDERLYING)
                    if len(df) > 0:
                        path = self._write_parquet(
                            df, PARQUET_DIRS[key], f"{date_str}.parquet"
                        )
                        summary["files"][key] = {
                            "path": str(path),
                            "rows": len(df),
                        }
                        logger.info(
                            f"  {DEFAULT_UNDERLYING} {timespan}: {len(df)} bars"
                        )
                    else:
                        logger.info(
                            f"  {DEFAULT_UNDERLYING} {timespan}: no bars"
                        )
                except Exception as exc:
                    msg = f"{DEFAULT_UNDERLYING} {timespan}: {exc}"
                    logger.error(f"  ERROR {msg}")
                    summary["errors"].append(msg)

        # --- Indices ---
        if not skip_indices:
            for timespan, key in [("day", "indices_day"), ("minute", "indices_minute")]:
                all_index_dfs: list[pl.DataFrame] = []
                for idx_ticker in INDEX_TICKERS:
                    try:
                        bars = self.fetch_bars(
                            idx_ticker, timespan, target_date, target_date
                        )
                        df = self._bars_to_df(bars, idx_ticker)
                        if len(df) > 0:
                            all_index_dfs.append(df)
                            logger.info(
                                f"  {idx_ticker} {timespan}: {len(df)} bars"
                            )
                    except Exception as exc:
                        msg = f"{idx_ticker} {timespan}: {exc}"
                        logger.warning(f"  WARN {msg}")
                        summary["errors"].append(msg)

                if all_index_dfs:
                    combined = pl.concat(all_index_dfs)
                    path = self._write_parquet(
                        combined, PARQUET_DIRS[key], f"{date_str}.parquet"
                    )
                    summary["files"][key] = {
                        "path": str(path),
                        "rows": len(combined),
                    }

        # --- Options contracts ---
        if not skip_options:
            self._download_options_for_day(target_date, summary)

        return summary

    @staticmethod
    def _generate_target_expirations(
        target_date: date,
        max_dte: int = 45,
    ) -> list[date]:
        """Generate likely SPY option expiration dates near target_date.

        SPY has Mon/Wed/Fri weekly expirations plus monthly (3rd Friday).
        This generates candidate dates without an API call.

        Args:
            target_date: The trading date.
            max_dte: Maximum days-to-expiration to include.

        Returns:
            Sorted list of candidate expiration dates.
        """
        expirations = set()
        for offset in range(max_dte + 1):
            candidate = target_date + timedelta(days=offset)
            # SPY has Mon/Wed/Fri expirations
            if candidate.weekday() in (0, 2, 4):  # Mon, Wed, Fri
                expirations.add(candidate)
        return sorted(expirations)

    def _download_options_for_day(
        self,
        target_date: date,
        summary: dict[str, Any],
    ) -> None:
        """Fetch SPY option contract bars for a single day.

        Uses per-expiration contract queries to minimize API calls.
        Filters contracts to those within ±strike_range of ATM price.
        At 5 calls/min, efficiency is critical.
        """
        date_str = target_date.isoformat()

        # 0. Get ATM reference price (reuse from already-downloaded SPY daily)
        atm_price: float | None = None
        spy_day_path = (
            self._data_root / "parquet" / PARQUET_DIRS["spy_day"]
            / f"{date_str}.parquet"
        )
        if spy_day_path.exists():
            try:
                spy_df = pl.read_parquet(str(spy_day_path))
                if len(spy_df) > 0:
                    atm_price = spy_df["close"][0]
            except Exception as exc:
                logger.warning(f"  Failed to read ATM price from {spy_day_path}: {exc}")
        if atm_price is None:
            try:
                bars = self.fetch_bars(
                    DEFAULT_UNDERLYING, "day", target_date, target_date
                )
                if bars:
                    atm_price = bars[0].get("c", bars[0].get("o"))
            except Exception as exc:
                logger.warning(f"  Failed to fetch ATM price via API: {exc}")

        # 1. Generate target expirations to fetch
        # For backtesting, we want: 0DTE + next few expirations (up to 30 days)
        target_expirations = self._generate_target_expirations(
            target_date, max_dte=self._max_dte
        )
        logger.info(
            f"  Options for {date_str}: ATM={atm_price}, "
            f"checking {len(target_expirations)} expirations"
        )

        # 2. Fetch contracts per expiration (1 API call each for <250 contracts)
        active_contracts: list[dict[str, Any]] = []
        for exp in target_expirations:
            try:
                contracts = self.fetch_contracts(
                    DEFAULT_UNDERLYING,
                    expiration_date=exp,
                    as_of_date=target_date,
                )
                # Filter by strike range
                for c in contracts:
                    if self._strike_range > 0 and atm_price is not None:
                        strike = c.get("strike_price", 0)
                        if abs(strike - atm_price) > self._strike_range:
                            continue
                    active_contracts.append(c)
                logger.info(
                    f"    Exp {exp}: {len(contracts)} total, "
                    f"{sum(1 for c in contracts if self._strike_range == 0 or atm_price is None or abs(c.get('strike_price', 0) - (atm_price or 0)) <= self._strike_range)} in range"
                )
            except Exception as exc:
                logger.warning(f"    Exp {exp}: error listing contracts: {exc}")
                summary["errors"].append(f"contracts {exp}: {exc}")

        total = len(active_contracts)
        if total == 0:
            logger.info("  No option contracts found within filter criteria")
            return

        est_calls = total * 2
        est_minutes = est_calls / 5
        logger.info(
            f"  {total} contracts to download, "
            f"~{est_calls} API calls, ~{est_minutes:.0f} minutes"
        )

        # 2. Fetch bars for each contract
        day_dfs: list[pl.DataFrame] = []
        minute_dfs: list[pl.DataFrame] = []

        for idx, contract in enumerate(active_contracts, 1):
            ticker = contract.get("ticker", "")
            if not ticker:
                continue

            if idx % 50 == 0 or idx == total:
                pct = (idx / total) * 100
                logger.info(
                    f"  Options progress: {idx}/{total} ({pct:.0f}%) — "
                    f"API calls: {self._call_count}"
                )

            # Daily bars
            try:
                bars = self.fetch_bars(
                    ticker, "day", target_date, target_date
                )
                df = self._bars_to_df(bars, ticker)
                if len(df) > 0:
                    day_dfs.append(df)
            except Exception as exc:
                logger.warning(f"  {ticker} day bars failed: {exc}")
                summary["errors"].append(f"{ticker} day: {exc}")

            # Minute bars
            try:
                bars = self.fetch_bars(
                    ticker, "minute", target_date, target_date
                )
                df = self._bars_to_df(bars, ticker)
                if len(df) > 0:
                    minute_dfs.append(df)
            except Exception as exc:
                logger.warning(f"  {ticker} minute bars failed: {exc}")
                summary["errors"].append(f"{ticker} minute: {exc}")

        # 3. Write combined Parquet files
        if day_dfs:
            combined = pl.concat(day_dfs)
            path = self._write_parquet(
                combined, PARQUET_DIRS["options_day"], f"{date_str}.parquet"
            )
            summary["files"]["options_day"] = {
                "path": str(path),
                "rows": len(combined),
                "contracts": len(day_dfs),
            }
            logger.info(
                f"  Options daily: {len(combined)} bars from "
                f"{len(day_dfs)} contracts"
            )

        if minute_dfs:
            combined = pl.concat(minute_dfs)
            path = self._write_parquet(
                combined, PARQUET_DIRS["options_minute"], f"{date_str}.parquet"
            )
            summary["files"]["options_minute"] = {
                "path": str(path),
                "rows": len(combined),
                "contracts": len(minute_dfs),
            }
            logger.info(
                f"  Options minute: {len(combined)} bars from "
                f"{len(minute_dfs)} contracts"
            )

        # Save contract reference data
        if active_contracts:
            contract_df = pl.DataFrame(active_contracts)
            self._write_parquet(
                contract_df, PARQUET_DIRS["contracts"], f"{date_str}.parquet"
            )

    # ==========================================================================
    # DOWNLOAD PIPELINE — DATE RANGE
    # ==========================================================================

    def download_range(
        self,
        start: date,
        end: date,
        resume: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Download data for a range of trading days.

        Args:
            start: First date (inclusive).
            end: Last date (inclusive).
            resume: Whether to skip already-completed dates from checkpoint.

        Returns:
            List of per-day summary dicts.
        """
        trading_days = self._trading_days(start, end)
        logger.info(
            f"Download range: {start} to {end} ({len(trading_days)} trading days)"
        )

        state = self._load_checkpoint() if resume else DownloadState()
        if not state.started_at:
            state.started_at = datetime.now().isoformat()
        completed_set = set(state.dates_completed or [])

        summaries: list[dict[str, Any]] = []
        for i, day in enumerate(trading_days, 1):
            day_str = day.isoformat()
            if day_str in completed_set:
                logger.info(
                    f"[{i}/{len(trading_days)}] {day_str} — already complete, skipping"
                )
                continue

            logger.info(
                f"[{i}/{len(trading_days)}] Downloading {day_str}..."
            )
            state.current_date = day_str
            state.current_phase = "started"
            self._save_checkpoint(state)

            try:
                summary = self.download_day(day)
                summaries.append(summary)

                state.dates_completed.append(day_str)  # type: ignore[union-attr]
                state.last_completed_date = day_str
                state.current_phase = "complete"
                self._save_checkpoint(state)

                if summary["errors"]:
                    logger.warning(
                        f"  {day_str} completed with "
                        f"{len(summary['errors'])} errors"
                    )
            except KeyboardInterrupt:
                logger.info("Download interrupted by user. State saved.")
                state.current_phase = "interrupted"
                self._save_checkpoint(state)
                raise
            except Exception as exc:
                logger.error(f"  FATAL error on {day_str}: {exc}")
                state.errors.append(f"{day_str}: {exc}")  # type: ignore[union-attr]
                self._save_checkpoint(state)

        logger.info(
            f"Download complete. {len(summaries)} days processed, "
            f"{self._call_count} total API calls."
        )
        return summaries

    # ==========================================================================
    # DAILY MODE — DOWNLOAD YESTERDAY
    # ==========================================================================

    def download_yesterday(self) -> dict[str, Any] | None:
        """Download data for the most recent completed trading day."""
        today = date.today()
        candidate = today - timedelta(days=1)
        # Walk backwards to find last trading day
        for _ in range(7):
            if self.is_trading_day(candidate):
                break
            candidate -= timedelta(days=1)

        if not self.is_trading_day(candidate):
            logger.warning("Could not find a recent trading day.")
            return None

        logger.info(f"Daily mode: downloading {candidate.isoformat()}")
        return self.download_day(candidate)

    # ==========================================================================
    # VALIDATION
    # ==========================================================================

    def validate_range(self, start: date, end: date) -> list[dict[str, Any]]:
        """
        Validate Parquet files for a date range.

        Args:
            start: First date.
            end: Last date.

        Returns:
            List of validation result dicts per date.
        """
        trading_days = self._trading_days(start, end)
        results: list[dict[str, Any]] = []

        for day in trading_days:
            day_str = day.isoformat()
            day_result: dict[str, Any] = {"date": day_str, "files": {}}

            for key, subdir in PARQUET_DIRS.items():
                path = (
                    self._data_root
                    / "parquet"
                    / subdir
                    / f"{day_str}.parquet"
                )
                if path.exists():
                    try:
                        df = pl.read_parquet(str(path))
                        file_size = path.stat().st_size / (1024 * 1024)
                        info: dict[str, Any] = {
                            "exists": True,
                            "rows": len(df),
                            "columns": df.columns,
                            "size_mb": round(file_size, 2),
                        }
                        if "ticker" in df.columns:
                            info["unique_tickers"] = df["ticker"].n_unique()
                        day_result["files"][key] = info
                    except Exception as exc:
                        day_result["files"][key] = {
                            "exists": True,
                            "error": str(exc),
                        }
                else:
                    day_result["files"][key] = {"exists": False}

            results.append(day_result)

        return results

    # ==========================================================================
    # MANIFEST
    # ==========================================================================

    def update_manifest(self) -> None:
        """Scan parquet directory and write a manifest.json summary."""
        manifest: dict[str, Any] = {"updated_at": datetime.now().isoformat()}

        for key, subdir in PARQUET_DIRS.items():
            dir_path = self._data_root / "parquet" / subdir
            files = sorted(dir_path.glob("*.parquet"))
            if files:
                dates = [f.stem for f in files]
                manifest[key] = {
                    "count": len(files),
                    "first_date": dates[0],
                    "last_date": dates[-1],
                    "total_size_mb": round(
                        sum(f.stat().st_size for f in files) / (1024 * 1024), 2
                    ),
                }
            else:
                manifest[key] = {"count": 0}

        manifest_path = self._data_root / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Manifest updated: {manifest_path}")


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================


def _parse_date(s: str) -> date:
    """Parse an ISO date string."""
    return date.fromisoformat(s)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Massive Historical Data Downloader for Spyder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backfill one month
  %(prog)s --mode backfill --start 2025-03-01 --end 2025-03-31

  # Download yesterday's data
  %(prog)s --mode daily

  # Download a specific date
  %(prog)s --mode single --date 2026-03-17

  # Resume an interrupted backfill
  %(prog)s --mode resume

  # Validate existing data
  %(prog)s --mode validate --start 2025-01-02 --end 2025-12-31
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["backfill", "daily", "single", "validate", "resume"],
        required=True,
        help="Download mode",
    )
    parser.add_argument(
        "--start", type=_parse_date, help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", type=_parse_date, help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--date", type=_parse_date, help="Specific date for single mode"
    )
    parser.add_argument(
        "--data-root",
        help="Override BACKTEST_DATA_ROOT",
    )
    parser.add_argument(
        "--rps",
        type=float,
        help="Requests per second (overrides MASSIVE_REST_RPS)",
    )
    parser.add_argument(
        "--strike-range",
        type=float,
        default=50.0,
        help="Download options within ±N of ATM price (default: 50, 0=all)",
    )
    parser.add_argument(
        "--max-dte",
        type=int,
        default=45,
        help="Max days-to-expiration for options (default: 45)",
    )
    parser.add_argument(
        "--skip-underlying",
        action="store_true",
        help="Skip SPY equity bars",
    )
    parser.add_argument(
        "--skip-indices",
        action="store_true",
        help="Skip index bars (NDX, COMP)",
    )
    parser.add_argument(
        "--skip-options",
        action="store_true",
        help="Skip options data (only download equity and indices)",
    )

    args = parser.parse_args()

    # Load .env
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(str(env_path))

    with MassiveHistoricalDownloader(
        data_root=args.data_root,
        rps=args.rps,
        strike_range=args.strike_range,
        max_dte=args.max_dte,
    ) as downloader:

        if args.mode == "backfill":
            if not args.start or not args.end:
                parser.error("--start and --end required for backfill mode")
            downloader.download_range(args.start, args.end)
            downloader.update_manifest()

        elif args.mode == "daily":
            downloader.download_yesterday()
            downloader.update_manifest()

        elif args.mode == "single":
            if not args.date:
                parser.error("--date required for single mode")
            summary = downloader.download_day(
                args.date,
                skip_underlying=args.skip_underlying,
                skip_indices=args.skip_indices,
                skip_options=args.skip_options,
            )
            logger.info(f"Summary: {json.dumps(summary, indent=2, default=str)}")
            downloader.update_manifest()

        elif args.mode == "resume":
            state = downloader._load_checkpoint()
            if not state.current_date and not state.dates_completed:
                logger.error("No checkpoint found. Use --mode backfill instead.")
                sys.exit(1)
            # Determine range from checkpoint
            if state.dates_completed:
                first = date.fromisoformat(state.dates_completed[0])
            elif state.current_date:
                first = date.fromisoformat(state.current_date)
            else:
                logger.error("Cannot determine start date from checkpoint.")
                sys.exit(1)
            # Default end to today
            end = date.today()
            logger.info(f"Resuming from checkpoint: {first} to {end}")
            downloader.download_range(first, end, resume=True)
            downloader.update_manifest()

        elif args.mode == "validate":
            if not args.start or not args.end:
                parser.error("--start and --end required for validate mode")
            results = downloader.validate_range(args.start, args.end)
            for r in results:
                day_files = r["files"]
                has_data = any(
                    v.get("exists") and v.get("rows", 0) > 0
                    for v in day_files.values()
                )
                status = "OK" if has_data else "MISSING"
                logger.info(f"  {r['date']}: {status}")
                for key, info in day_files.items():
                    if info.get("exists") and info.get("rows", 0) > 0:
                        logger.info(
                            f"    {key}: {info['rows']} rows, "
                            f"{info.get('size_mb', '?')} MB"
                        )


if __name__ == "__main__":
    main()
