#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ93_RunPaper.py
Purpose: Market-hours-aware launcher for the 30-day paper-trading harness

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-03 Time: 00:00:00

Module Description:
    Thin launcher that wraps SpyderR06_PaperTradingHarness and drives
    the session lifecycle:

        1. At market open (or on demand):
               harness.start_session()
        2. Every ``--heartbeat`` seconds during the session:
               harness.check_drawdown()   → log / alert on breach
               harness.update_equity()    → broker equity pull
        3. At market close:
               harness.end_session()      → snapshot written to disk
        4. Progress is printed to stdout and captured by the system logger.

    The 30-day validation clock ticks automatically — each calendar
    session whose snapshot file is saved counts as one day.

Usage:
    # Dry-run (no broker, uses PAPER_STARTING_EQUITY from .env)
    python SpyderQ_Scripts/SpyderQ93_RunPaper.py

    # With explicit snapshot directory
    python SpyderQ_Scripts/SpyderQ93_RunPaper.py \\
        --snapshot-dir /data/paper_trading

    # Headless / CI (forces a single synthetic session and exits)
    python SpyderQ_Scripts/SpyderQ93_RunPaper.py --once

    # Adjust intraday heartbeat interval (seconds)
    python SpyderQ_Scripts/SpyderQ93_RunPaper.py --heartbeat 60

Options:
    --snapshot-dir DIR   Override PAPER_SNAPSHOT_DIR for snapshot storage
    --heartbeat N        Seconds between intraday equity / drawdown checks
                         (default: 300 = 5 minutes)
    --once               Run exactly one market session and exit (useful for CI)
    --no-market-check    Skip NYSE open/close detection; treat every run as
                         market-open (useful for testing outside market hours)
    --verbose            Print verbose progress to stdout

Environment Variables (loaded from .env):
    TRADIER_API_KEY         Tradier bearer token
    TRADIER_ACCOUNT_ID      Tradier account number
    TRADIER_ENVIRONMENT     "sandbox" | "production" (default: sandbox)
    PAPER_STARTING_EQUITY   Fallback equity when broker unavailable (default: 100000)
    PAPER_SNAPSHOT_DIR      Directory for JSON snapshot files
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import argparse
import signal
import sys
import time
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars may already be set

# ==============================================================================
# PATH SETUP
# ==============================================================================
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderR_Runtime.SpyderR06_PaperTradingHarness import (
        PaperTradingHarness,
        create_paper_trading_harness_from_env,
    )
except ImportError as exc:
    sys.exit(
        f"[ERROR] Cannot import SpyderR06_PaperTradingHarness: {exc}\n"
        "Run from the repository root with the venv activated."
    )

try:
    from Spyder.SpyderA_Core.SpyderA04_Scheduler import MarketCalendar

    _HAS_CALENDAR = True
except ImportError:
    _HAS_CALENDAR = False

try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

    _logger = SpyderLogger.get_logger("SpyderQ93_RunPaper")
except ImportError:
    import logging

    _logger = logging.getLogger("SpyderQ93_RunPaper")

# ==============================================================================
# CONSTANTS
# ==============================================================================
_DEFAULT_HEARTBEAT_SECONDS: int = 300   # 5 minutes
_MARKET_POLL_SECONDS: int = 60          # check market open status every minute
_SLEEP_GRANULARITY: int = 5             # granularity for interruptible sleeps


# ==============================================================================
# HELPERS
# ==============================================================================


def _is_market_open(calendar) -> bool:
    """Return True if the NYSE session is currently live."""
    if calendar is None:
        return True          # no calendar → assume open
    try:
        return calendar.is_market_open()
    except Exception as exc:
        _logger.warning("MarketCalendar error: %s — assuming open", exc)
        return True


def _interruptible_sleep(seconds: int, stop_flag: list) -> None:
    """Sleep for *seconds* but wake early if stop_flag[0] is set."""
    elapsed = 0
    while elapsed < seconds:
        if stop_flag[0]:
            return
        time.sleep(min(_SLEEP_GRANULARITY, seconds - elapsed))
        elapsed += _SLEEP_GRANULARITY


def _print_summary(harness: PaperTradingHarness, verbose: bool) -> None:
    """Print a quick 30-day progress snapshot to stdout."""
    summary = harness.get_30d_summary()
    remaining = harness.days_remaining()
    complete = summary.validation_complete

    _logger.info(
        "=== 30-Day Paper Validation Progress ===\n"
        "  Sessions completed : %d / %d\n"
        "  Days remaining     : %d\n"
        "  Total P&L          : $%.2f (%.2f %%)\n"
        "  Annualised Sharpe  : %.3f\n"
        "  Max drawdown       : %.2f %%\n"
        "  Validation         : %s",
        summary.sessions_completed,
        summary.sessions_required,
        remaining,
        summary.total_pnl,
        summary.total_pnl_pct * 100,
        summary.annualised_sharpe,
        summary.max_drawdown_from_peak_pct * 100,
        "COMPLETE ✓" if complete else "in progress …",
    )

    if complete:
        _logger.info(
            "Paper-trading validation COMPLETE. "
            "Review %s before enabling live trading.",
            summary.last_session_date,
        )


# ==============================================================================
# SESSION RUNNER
# ==============================================================================


def run_session(
    harness: PaperTradingHarness,
    heartbeat: int,
    no_market_check: bool,
    verbose: bool,
    stop_flag: list,
    calendar=None,
) -> None:
    """
    Drive one full market session.

    Args:
        harness:          Configured PaperTradingHarness instance.
        heartbeat:        Seconds between intraday equity / drawdown checks.
        no_market_check:  If True, skip NYSE schedule detection.
        verbose:          Whether to log extra detail.
        stop_flag:        Single-element list; set [0]=True to abort.
        calendar:         Optional MarketCalendar; None = always-open.
    """
    _logger.info(
        "Starting paper session — day %d / remaining %d",
        harness._store.count_snapshots() + 1,
        harness.days_remaining(),
    )

    if not harness.start_session():
        _logger.error("start_session() returned False — aborting run")
        return

    _logger.info("Session active — equity $%.2f", harness.get_current_metrics()["starting_equity"])

    while not stop_flag[0]:
        if not no_market_check and not _is_market_open(calendar):
            _logger.info("Market closed — ending session")
            break

        # Intraday heartbeat: check drawdown, log metrics, sleep
        alert = harness.check_drawdown()
        if alert is not None:
            _logger.warning(
                "DRAWDOWN ALERT [%s] — %.2f %% (threshold: %.2f %%)",
                alert.level.upper(),
                alert.drawdown_pct * 100,
                alert.threshold_pct * 100,
            )

        if harness.trading_halted:
            _logger.critical(
                "Trading HALTED — daily drawdown limit breached. "
                "Closing session early."
            )
            break

        if verbose:
            m = harness.get_current_metrics()
            _logger.info(
                "Heartbeat — equity $%.2f | trades %d | wins %d | losses %d",
                m.get("current_equity", 0.0),
                m.get("trades_filled", 0),
                m.get("wins", 0),
                m.get("losses", 0),
            )

        _interruptible_sleep(heartbeat, stop_flag)

    snapshot = harness.end_session()
    _logger.info(
        "Session closed — date=%s pnl=$%.2f (%.2f %%) "
        "trades=%d/%d win_rate=%.0f%%",
        snapshot.session_date,
        snapshot.daily_pnl,
        snapshot.daily_pnl_pct * 100,
        snapshot.trades_filled,
        snapshot.trades_placed,
        snapshot.win_rate * 100,
    )


# ==============================================================================
# MARKET-HOURS LOOP
# ==============================================================================


def market_hours_loop(
    harness: PaperTradingHarness,
    heartbeat: int,
    no_market_check: bool,
    verbose: bool,
    once: bool,
    stop_flag: list,
    calendar=None,
) -> None:
    """
    Main loop: wait for market open, run session, wait for next day.

    Args:
        once: If True, run exactly one session then return (useful for CI/testing).
    """
    sessions_run = 0

    while not stop_flag[0]:
        if harness.is_within_validation_window() is False:
            _logger.info("30-day paper validation is COMPLETE. Exiting.")
            break

        # Wait for market open (or skip check)
        if not no_market_check:
            while not stop_flag[0] and not _is_market_open(calendar):
                _logger.debug("Market not yet open — sleeping %ds", _MARKET_POLL_SECONDS)
                _interruptible_sleep(_MARKET_POLL_SECONDS, stop_flag)

        if stop_flag[0]:
            break

        run_session(
            harness=harness,
            heartbeat=heartbeat,
            no_market_check=no_market_check,
            verbose=verbose,
            stop_flag=stop_flag,
            calendar=calendar,
        )
        sessions_run += 1
        _print_summary(harness, verbose)

        if once:
            break

        # Wait for next trading day (sleep 15 minutes after close, re-check)
        _logger.info("Waiting for next trading day …")
        _interruptible_sleep(15 * 60, stop_flag)

    _logger.info("Paper trading launcher exiting — %d session(s) this run.", sessions_run)


# ==============================================================================
# CLI
# ==============================================================================


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="SpyderQ93_RunPaper",
        description="30-day paper-trading harness launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--snapshot-dir",
        metavar="DIR",
        default=None,
        help="Override PAPER_SNAPSHOT_DIR for snapshot storage",
    )
    parser.add_argument(
        "--heartbeat",
        type=int,
        default=_DEFAULT_HEARTBEAT_SECONDS,
        metavar="N",
        help=f"Seconds between intraday checks (default: {_DEFAULT_HEARTBEAT_SECONDS})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run exactly one session and exit (CI / testing)",
    )
    parser.add_argument(
        "--no-market-check",
        action="store_true",
        help="Skip NYSE open/close detection",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print verbose progress on each heartbeat",
    )
    return parser


def main() -> int:
    """Entry point — returns process exit code."""
    args = _build_arg_parser().parse_args()

    snapshot_dir: Path | None = (
        Path(args.snapshot_dir) if args.snapshot_dir else None
    )

    _logger.info(
        "SpyderQ93 — paper-trading launcher starting (heartbeat=%ds, once=%s)",
        args.heartbeat,
        args.once,
    )

    # Build harness from environment
    harness = create_paper_trading_harness_from_env(snapshot_dir=snapshot_dir)
    _logger.info(
        "Harness ready — %d / 30 sessions completed, %d remaining",
        harness._store.count_snapshots(),
        harness.days_remaining(),
    )

    # Optional market calendar
    calendar = None
    if _HAS_CALENDAR and not args.no_market_check:
        try:
            calendar = MarketCalendar()
            _logger.info("MarketCalendar loaded — NYSE schedule active")
        except Exception as exc:
            _logger.warning("MarketCalendar unavailable: %s — continuing without", exc)

    # Graceful shutdown on SIGINT / SIGTERM
    stop_flag: list = [False]

    def _on_signal(signum, _frame):
        _logger.info("Signal %d received — stopping after current session", signum)
        stop_flag[0] = True

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        market_hours_loop(
            harness=harness,
            heartbeat=args.heartbeat,
            no_market_check=args.no_market_check,
            verbose=args.verbose,
            once=args.once,
            stop_flag=stop_flag,
            calendar=calendar,
        )
    except Exception as exc:
        _logger.exception("Unhandled exception in market loop: %s", exc)
        return 1

    return 0


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    sys.exit(main())
