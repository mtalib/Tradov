#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovR_Runtime
Module: TradovR06_PaperTradingHarness.py
Purpose: 30-day paper-trading validation harness

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-03 Time: 00:00:00

Module Description:
    Automated paper-trading harness that:
                • Uses LIVE Tradier account balances/market snapshots for visibility,
                    while paper fills remain local (TradovBox simulation).
        • Captures one DailySnapshot per trading session → JSON file.
        • Computes rolling Sharpe ratio, max drawdown from rolling peak,
          and win-rate from the accumulated snapshot history.
        • Fires DrawdownAlert records (JSON) at three thresholds:
              WARNING  – 3 % intraday drawdown from session peak equity
              CRITICAL – 5 % intraday drawdown from session peak equity
              HALT     – 7 % intraday drawdown (trading must stop for the day)
        • Tracks a 30-trading-day validation window; days_remaining() > 0 means
          the paper phase is still active.
        • Deliberately lightweight: no Qt, no APScheduler, no async.
          The caller is responsible for the event loop (see TradovQ93_RunPaper).

    Filesystem layout (all under ``snapshot_dir``, default data/paper_trading/):
        snapshots/YYYY-MM-DD.json        – one per trading session
        alerts/YYYY-MM-DDTHH-MM-SS_<level>.json   – one per alert

Usage:
    harness = create_paper_trading_harness_from_env()
    harness.start_session()
    # … trading happens via broker …
    harness.record_trade(pnl=45.00, won=True)
    alert = harness.check_drawdown()
    snapshot = harness.end_session()
    summary  = harness.get_30d_summary()

Change Log:
    2026-03-03:
        - Created (medium-priority item E: paper trading harness)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import logging
import math
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, UTC
from enum import StrEnum
from pathlib import Path

# ==============================================================================
# OPTIONAL BROKER IMPORT
# ==============================================================================
try:
    from Tradov.TradovB_Broker.TradovB40_TradierClient import (
        TradierClient,
        TradingEnvironment,
    )

    HAS_TRADIER = True
except Exception:
    HAS_TRADIER = False
    TradierClient = None  # type: ignore[misc,assignment]
    TradingEnvironment = None  # type: ignore[misc,assignment]

# ==============================================================================
# LOGGER
# ==============================================================================
logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

#: Number of consecutive trading days required for the validation window.
PAPER_TRADING_DAYS_REQUIRED: int = 30

#: US/Eastern timezone offset used for market-hours gating (no pytz dependency).
#: We use a fixed -5 h offset here (EST); callers in DST should use -4 h.
_EASTERN_OFFSET_STD: int = -5
_EASTERN_OFFSET_DST: int = -4

#: Intraday drawdown thresholds (fractional, relative to session peak equity).
_WARN_THRESHOLD: float = 0.03   # 3 %
_CRIT_THRESHOLD: float = 0.05   # 5 %
_HALT_THRESHOLD: float = 0.07   # 7 %

#: Annualisation factor for daily Sharpe.
_TRADING_DAYS_PER_YEAR: float = 252.0

#: Minimum number of daily return observations before Sharpe is meaningful.
_MIN_SHARPE_WINDOW: int = 2


# ==============================================================================
# ENUMS
# ==============================================================================


class DrawdownLevel(StrEnum):
    """Severity levels for intraday drawdown alerts."""

    WARNING = "warning"    # 3 % — log and notify, continue trading
    CRITICAL = "critical"  # 5 % — log and notify, reduce size
    HALT = "halt"          # 7 % — log and notify, stop trading for the day


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class DailySnapshot:
    """
    Immutable record of a single paper-trading session.

    All monetary values are in USD.  Percentages are expressed as decimals
    (e.g. 0.0150 means 1.50 %).
    """

    # --- Identity ---
    session_date: str          # ISO-8601 date, e.g. "2026-03-03"
    captured_at: str           # ISO-8601 datetime UTC, e.g. "2026-03-03T21:00:00Z"

    # --- Account ---
    starting_equity: float     # Equity at session open (from broker API)
    ending_equity: float       # Equity at session close (from broker API)
    peak_equity: float         # Highest intraday equity observed

    # --- P&L ---
    daily_pnl: float           # ending_equity - starting_equity
    daily_pnl_pct: float       # daily_pnl / starting_equity
    cumulative_pnl: float      # Sum of daily_pnl across all sessions so far
    cumulative_pnl_pct: float  # cumulative_pnl / initial_equity (first session)

    # --- Trades ---
    trades_placed: int
    trades_filled: int
    wins: int
    losses: int
    win_rate: float            # wins / (wins + losses), 0.0 if no closed trades

    # --- Risk metrics ---
    max_intraday_drawdown_pct: float  # Worst intraday drawdown (positive = loss)
    rolling_sharpe: float             # Annualised Sharpe over last N sessions
    max_drawdown_from_peak_pct: float # Max drawdown from equity peak to trough

    # --- Session ---
    session_day_number: int           # 1-based count of paper-trading sessions
    days_remaining: int               # PAPER_TRADING_DAYS_REQUIRED - session_day_number
    open_positions: int               # Positions still open at session end
    session_duration_minutes: float   # Wall-clock length of the session

    def to_json(self) -> str:
        """Serialise to a compact JSON string."""
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "DailySnapshot":
        """Deserialise from JSON string."""
        return cls(**json.loads(raw))


@dataclass
class DrawdownAlert:
    """
    Record of a drawdown threshold breach during a session.

    Serialised to the ``alerts/`` subdirectory as a JSON file so that
    other processes (e.g. the notification daemon) can tail the directory.
    """

    triggered_at: str          # ISO-8601 datetime UTC
    session_date: str          # ISO-8601 date
    level: str                 # DrawdownLevel value
    current_equity: float
    peak_equity: float
    drawdown_pct: float        # current deficit as a positive decimal
    threshold_pct: float       # the threshold that was crossed
    message: str               # Human-readable summary

    def to_json(self) -> str:
        """Serialise to a compact JSON string."""
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "DrawdownAlert":
        """Deserialise from JSON string."""
        return cls(**json.loads(raw))


@dataclass
class HarnessSummary:
    """
    Aggregate metrics over the full (or partial) paper-trading window.

    Returned by :meth:`PaperTradingHarness.get_30d_summary`.
    """

    sessions_completed: int
    sessions_required: int
    total_trading_days: int
    first_session_date: str
    last_session_date: str

    initial_equity: float
    final_equity: float
    total_pnl: float
    total_pnl_pct: float

    total_trades: int
    total_wins: int
    total_losses: int
    overall_win_rate: float

    annualised_sharpe: float
    max_drawdown_pct: float           # Worst single-day drawdown observed
    max_drawdown_from_peak_pct: float # Portfolio-level max drawdown

    best_day_pnl: float
    worst_day_pnl: float
    average_daily_pnl: float
    positive_days: int
    negative_days: int

    validation_complete: bool
    days_remaining: int

    def to_json(self) -> str:
        """Serialise to a compact JSON string."""
        return json.dumps(asdict(self), indent=2)


# ==============================================================================
# SNAPSHOT STORE
# ==============================================================================


class SnapshotStore:
    """
    File-backed store for :class:`DailySnapshot` and :class:`DrawdownAlert`.

    Directory layout::

        <root>/
            snapshots/YYYY-MM-DD.json
            alerts/YYYY-MM-DDTHH-MM-SS_<level>.json
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        self._root = Path(root_dir) if root_dir else Path("data") / "paper_trading"
        self._snapshots_dir = self._root / "snapshots"
        self._alerts_dir = self._root / "alerts"
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._alerts_dir.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def save_snapshot(self, snapshot: DailySnapshot) -> Path:
        """
        Persist *snapshot* to ``snapshots/YYYY-MM-DD.json``.

        Returns:
            Path to the written file.
        """
        path = self._snapshots_dir / f"{snapshot.session_date}.json"
        path.write_text(snapshot.to_json(), encoding="utf-8")
        logger.info("Saved daily snapshot → %s", path)
        return path

    def load_snapshot(self, session_date: date) -> DailySnapshot | None:
        """
        Load the snapshot for *session_date*, or ``None`` if absent.

        Args:
            session_date: The calendar date of the session.

        Returns:
            :class:`DailySnapshot` or ``None``.
        """
        path = self._snapshots_dir / f"{session_date.isoformat()}.json"
        if not path.exists():
            return None
        try:
            return DailySnapshot.from_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load snapshot %s: %s", path, exc)
            return None

    def list_snapshots(
        self,
        start: date | None = None,
        end: date | None = None,
    ) -> list[DailySnapshot]:
        """
        Return all snapshots in ``[start, end]`` (inclusive), sorted by date.

        Args:
            start: Earliest date to include (``None`` = no lower bound).
            end:   Latest date to include   (``None`` = no upper bound).

        Returns:
            Sorted list of :class:`DailySnapshot` objects.
        """
        snapshots: list[DailySnapshot] = []
        for p in sorted(self._snapshots_dir.glob("*.json")):
            try:
                snap_date = date.fromisoformat(p.stem)
            except ValueError:
                continue
            if start and snap_date < start:
                continue
            if end and snap_date > end:
                continue
            snap = self.load_snapshot(snap_date)
            if snap is not None:
                snapshots.append(snap)
        return snapshots

    def count_snapshots(self) -> int:
        """Number of snapshot files on disk."""
        return sum(1 for _ in self._snapshots_dir.glob("*.json"))

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def save_alert(self, alert: DrawdownAlert) -> Path:
        """
        Persist *alert* to ``alerts/<timestamp>_<level>.json``.

        Returns:
            Path to the written file.
        """
        safe_ts = alert.triggered_at.replace(":", "-").replace(" ", "T")
        filename = f"{safe_ts}_{alert.level}.json"
        path = self._alerts_dir / filename
        path.write_text(alert.to_json(), encoding="utf-8")
        logger.warning(
            "Drawdown alert [%s] %.1f %% — saved → %s",
            alert.level.upper(),
            alert.drawdown_pct * 100,
            path,
        )
        return path

    def list_alert_files(self, session_date: date | None = None) -> list[Path]:
        """Return alert JSON paths, optionally filtered by date prefix."""
        if session_date is None:
            return sorted(self._alerts_dir.glob("*.json"))
        prefix = session_date.isoformat()
        return sorted(self._alerts_dir.glob(f"{prefix}*.json"))


# ==============================================================================
# METRICS CALCULATOR
# ==============================================================================


class MetricsCalculator:
    """
    Stateless helper for paper-trading performance computations.

    All methods are class methods (no instance state) for easy mocking in tests.
    """

    @classmethod
    def rolling_sharpe(
        cls,
        daily_returns: list[float],
        window: int = 20,
        risk_free_daily: float = 0.0,
    ) -> float:
        """
        Annualised Sharpe ratio over the most recent *window* observations.

        Args:
            daily_returns:    List of daily P&L-as-fraction-of-equity returns.
                              E.g. [0.0050, -0.0030, 0.0070, …]
            window:           Number of most-recent days to use.
            risk_free_daily:  Daily risk-free rate (default 0.0).

        Returns:
            Annualised Sharpe, or 0.0 if fewer than
            :data:`_MIN_SHARPE_WINDOW` observations are available.
        """
        obs = daily_returns[-window:] if len(daily_returns) > window else daily_returns
        if len(obs) < _MIN_SHARPE_WINDOW:
            return 0.0
        excess = [r - risk_free_daily for r in obs]
        mean = sum(excess) / len(excess)
        variance = sum((r - mean) ** 2 for r in excess) / (len(excess) - 1)
        std = math.sqrt(variance)
        if std == 0.0:
            return 0.0
        return (mean / std) * math.sqrt(_TRADING_DAYS_PER_YEAR)

    @classmethod
    def max_drawdown(cls, equity_series: list[float]) -> float:
        """
        Maximum drawdown over an equity curve (peak-to-trough, as a positive
        decimal).

        Args:
            equity_series: Time-ordered list of equity values.

        Returns:
            Maximum drawdown fraction (0.0 if trivial series).
        """
        if len(equity_series) < 2:
            return 0.0
        peak = equity_series[0]
        max_dd = 0.0
        for equity in equity_series:
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = (peak - equity) / peak
                max_dd = max(max_dd, dd)
        return max_dd

    @classmethod
    def win_rate(cls, wins: int, total: int) -> float:
        """
        Win rate as a fraction in ``[0.0, 1.0]``.

        Args:
            wins:  Number of winning trades.
            total: Total number of closed trades (wins + losses).

        Returns:
            Fraction of winning trades; 0.0 if *total* is 0.
        """
        if total <= 0:
            return 0.0
        return wins / total

    @classmethod
    def build_summary(
        cls,
        snapshots: list[DailySnapshot],
        sessions_required: int = PAPER_TRADING_DAYS_REQUIRED,
    ) -> HarnessSummary:
        """
        Aggregate a list of *snapshots* into a :class:`HarnessSummary`.

        Args:
            snapshots:         All daily snapshots in chronological order.
            sessions_required: Target number of sessions (default 30).

        Returns:
            :class:`HarnessSummary` with aggregated metrics.
        """
        n = len(snapshots)
        if n == 0:
            return HarnessSummary(
                sessions_completed=0,
                sessions_required=sessions_required,
                total_trading_days=0,
                first_session_date="",
                last_session_date="",
                initial_equity=0.0,
                final_equity=0.0,
                total_pnl=0.0,
                total_pnl_pct=0.0,
                total_trades=0,
                total_wins=0,
                total_losses=0,
                overall_win_rate=0.0,
                annualised_sharpe=0.0,
                max_drawdown_pct=0.0,
                max_drawdown_from_peak_pct=0.0,
                best_day_pnl=0.0,
                worst_day_pnl=0.0,
                average_daily_pnl=0.0,
                positive_days=0,
                negative_days=0,
                validation_complete=False,
                days_remaining=sessions_required,
            )

        first = snapshots[0]
        last = snapshots[-1]
        initial_equity = first.starting_equity
        final_equity = last.ending_equity
        total_pnl = sum(s.daily_pnl for s in snapshots)
        total_pnl_pct = total_pnl / initial_equity if initial_equity > 0 else 0.0

        total_trades = sum(s.trades_filled for s in snapshots)
        total_wins = sum(s.wins for s in snapshots)
        total_losses = sum(s.losses for s in snapshots)
        overall_win_rate = cls.win_rate(total_wins, total_wins + total_losses)

        daily_returns = [s.daily_pnl_pct for s in snapshots]
        annualised_sharpe = cls.rolling_sharpe(daily_returns, window=n)

        daily_pnls = [s.daily_pnl for s in snapshots]
        max_dd_pct = max((s.max_intraday_drawdown_pct for s in snapshots), default=0.0)

        equity_series = [snapshots[0].starting_equity] + [s.ending_equity for s in snapshots]
        max_dd_from_peak = cls.max_drawdown(equity_series)

        best_day = max(daily_pnls)
        worst_day = min(daily_pnls)
        avg_daily = total_pnl / n
        positive_days = sum(1 for p in daily_pnls if p > 0)
        negative_days = sum(1 for p in daily_pnls if p < 0)

        days_remaining = max(0, sessions_required - n)
        validation_complete = n >= sessions_required

        return HarnessSummary(
            sessions_completed=n,
            sessions_required=sessions_required,
            total_trading_days=n,
            first_session_date=first.session_date,
            last_session_date=last.session_date,
            initial_equity=initial_equity,
            final_equity=final_equity,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            total_trades=total_trades,
            total_wins=total_wins,
            total_losses=total_losses,
            overall_win_rate=overall_win_rate,
            annualised_sharpe=annualised_sharpe,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_from_peak_pct=max_dd_from_peak,
            best_day_pnl=best_day,
            worst_day_pnl=worst_day,
            average_daily_pnl=avg_daily,
            positive_days=positive_days,
            negative_days=negative_days,
            validation_complete=validation_complete,
            days_remaining=days_remaining,
        )


# ==============================================================================
# HARNESS
# ==============================================================================


class PaperTradingHarness:
    """
    30-day paper-trading validation harness using LIVE Tradier market data.

    The caller is responsible for calling :meth:`start_session` at market open
    and :meth:`end_session` at market close.  Intraday, call
    :meth:`record_trade` after each fill and :meth:`check_drawdown` periodically
    (e.g. every minute).

    Args:
        broker_client:      Tradier client configured for LIVE mode.
                            ``None`` is accepted (for testing); ``start_session``
                            will still work but equity will be seeded from
                            ``starting_equity_override``.
        snapshot_store:     Filesystem store for snapshots and alerts.
        starting_equity_override:
                            If provided, used as the starting equity when the
                            broker client is ``None`` or the API call fails.
        sessions_required:  Number of consecutive sessions for validation
                            (default :data:`PAPER_TRADING_DAYS_REQUIRED`).
        warn_threshold:     Intraday drawdown for WARNING alert  (default 0.03).
        crit_threshold:     Intraday drawdown for CRITICAL alert (default 0.05).
        halt_threshold:     Intraday drawdown for HALT alert     (default 0.07).
    """

    def __init__(
        self,
        broker_client=None,
        snapshot_store: SnapshotStore | None = None,
        starting_equity_override: float = 100_000.0,
        sessions_required: int = PAPER_TRADING_DAYS_REQUIRED,
        warn_threshold: float = _WARN_THRESHOLD,
        crit_threshold: float = _CRIT_THRESHOLD,
        halt_threshold: float = _HALT_THRESHOLD,
    ) -> None:
        self._client = broker_client
        self._store = snapshot_store or SnapshotStore()
        self._equity_override = starting_equity_override
        self._sessions_required = sessions_required
        self._warn_threshold = warn_threshold
        self._crit_threshold = crit_threshold
        self._halt_threshold = halt_threshold

        # --- Session state (reset each day) ---
        self._session_active: bool = False
        self._session_date: date | None = None
        self._session_start_time: datetime | None = None
        self._starting_equity: float = 0.0
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._worst_intraday_dd: float = 0.0
        self._trades_placed: int = 0
        self._trades_filled: int = 0
        self._session_wins: int = 0
        self._session_losses: int = 0
        self._halt_fired: bool = False

        # --- Persistent across sessions ---
        self._initial_equity: float = 0.0   # first-ever session start equity
        self._cumulative_pnl: float = 0.0

        # --- Fired alert levels this session (prevents duplicate alerts) ---
        self._fired_levels: set = set()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(self) -> bool:
        """
        Begin a new paper-trading session.

        Queries the broker for the current account equity; falls back to
        ``starting_equity_override`` if the broker is unavailable.

        Returns:
            ``True`` if the session was started successfully.
        """
        self._session_date = date.today()
        self._session_start_time = datetime.now(tz=UTC)

        equity = self._fetch_equity()
        self._starting_equity = equity
        self._peak_equity = equity
        self._current_equity = equity
        self._worst_intraday_dd = 0.0
        self._trades_placed = 0
        self._trades_filled = 0
        self._session_wins = 0
        self._session_losses = 0
        self._halt_fired = False
        self._fired_levels = set()
        self._session_active = True

        # First session initialises the baseline equity
        if self._initial_equity == 0.0:
            self._initial_equity = equity

        logger.info(
            "Paper session started — date=%s equity=%.2f",
            self._session_date.isoformat(),
            equity,
        )
        return True

    def end_session(self, open_positions: int = 0) -> DailySnapshot:
        """
        Close the current session and persist a :class:`DailySnapshot`.

        Args:
            open_positions: Number of positions still open at session end.

        Returns:
            The :class:`DailySnapshot` written to disk.

        Raises:
            RuntimeError: If called without a prior :meth:`start_session`.
        """
        if not self._session_active:
            raise RuntimeError("end_session() called without an active session")

        ending_equity = self._fetch_equity()
        self._session_active = False

        daily_pnl = ending_equity - self._starting_equity
        daily_pnl_pct = daily_pnl / self._starting_equity if self._starting_equity > 0 else 0.0
        self._cumulative_pnl += daily_pnl

        initial = self._initial_equity if self._initial_equity > 0 else ending_equity
        cumulative_pnl_pct = self._cumulative_pnl / initial if initial > 0 else 0.0

        # Rolling Sharpe from all snapshots + today
        all_snaps = self._store.list_snapshots()
        prior_returns = [s.daily_pnl_pct for s in all_snaps]
        all_returns = prior_returns + [daily_pnl_pct]
        sharpe = MetricsCalculator.rolling_sharpe(all_returns, window=20)

        # Max drawdown from peak using stored equity curve
        equity_series = (
            [s.starting_equity for s in all_snaps]
            + [s.ending_equity for s in all_snaps[-1:]]
            + [ending_equity]
        )
        dd_from_peak = MetricsCalculator.max_drawdown(equity_series)

        session_day = len(all_snaps) + 1  # 1-based (before saving today's)
        days_rem = max(0, self._sessions_required - session_day)

        now_utc = datetime.now(tz=UTC)
        duration_minutes = (
            (now_utc - self._session_start_time).total_seconds() / 60.0
            if self._session_start_time
            else 0.0
        )

        total_closed = self._session_wins + self._session_losses
        win_rate = MetricsCalculator.win_rate(self._session_wins, total_closed)

        snapshot = DailySnapshot(
            session_date=self._session_date.isoformat(),
            captured_at=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            starting_equity=self._starting_equity,
            ending_equity=ending_equity,
            peak_equity=self._peak_equity,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            cumulative_pnl=self._cumulative_pnl,
            cumulative_pnl_pct=cumulative_pnl_pct,
            trades_placed=self._trades_placed,
            trades_filled=self._trades_filled,
            wins=self._session_wins,
            losses=self._session_losses,
            win_rate=win_rate,
            max_intraday_drawdown_pct=self._worst_intraday_dd,
            rolling_sharpe=sharpe,
            max_drawdown_from_peak_pct=dd_from_peak,
            session_day_number=session_day,
            days_remaining=days_rem,
            open_positions=open_positions,
            session_duration_minutes=duration_minutes,
        )

        self._store.save_snapshot(snapshot)

        logger.info(
            "Paper session ended — date=%s pnl=%.2f (%.2f %%) day=%d/%d",
            snapshot.session_date,
            daily_pnl,
            daily_pnl_pct * 100,
            session_day,
            self._sessions_required,
        )
        return snapshot

    # ------------------------------------------------------------------
    # Intraday operations
    # ------------------------------------------------------------------

    def update_equity(self, current_equity: float) -> None:
        """
        Update the harness with the latest account equity.

        Call this periodically (e.g. once per minute) so that
        :meth:`check_drawdown` has fresh data.

        Args:
            current_equity: Current account equity in USD.
        """
        self._current_equity = current_equity
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity
        if self._peak_equity > 0:
            dd = (self._peak_equity - current_equity) / self._peak_equity
            self._worst_intraday_dd = max(self._worst_intraday_dd, dd)

    def record_trade(
        self,
        pnl: float,
        placed: bool = True,
        filled: bool = True,
        won: bool | None = None,
    ) -> None:
        """
        Register a trade outcome in the current session.

        Args:
            pnl:    Realised P&L of the trade (positive = profit).
            placed: Whether the order was placed (default True).
            filled: Whether the order was filled (default True).
            won:    ``True`` = winning trade, ``False`` = losing trade,
                    ``None`` = not yet closed (P&L not tracked in win/loss).
        """
        if placed:
            self._trades_placed += 1
        if filled:
            self._trades_filled += 1
        if won is True:
            self._session_wins += 1
        elif won is False:
            self._session_losses += 1

    def check_drawdown(self) -> DrawdownAlert | None:
        """
        Test the current equity against drawdown thresholds.

        Only one alert per level is fired per session (idempotent).

        Returns:
            A persisted :class:`DrawdownAlert` if a new threshold was crossed,
            ``None`` otherwise.
        """
        if not self._session_active or self._starting_equity <= 0:
            return None

        dd = (self._peak_equity - self._current_equity) / self._peak_equity if self._peak_equity > 0 else 0.0  # noqa: E501

        level: DrawdownLevel | None = None
        threshold: float = 0.0

        if dd >= self._halt_threshold and DrawdownLevel.HALT not in self._fired_levels:
            level = DrawdownLevel.HALT
            threshold = self._halt_threshold
        elif dd >= self._crit_threshold and DrawdownLevel.CRITICAL not in self._fired_levels:
            level = DrawdownLevel.CRITICAL
            threshold = self._crit_threshold
        elif dd >= self._warn_threshold and DrawdownLevel.WARNING not in self._fired_levels:
            level = DrawdownLevel.WARNING
            threshold = self._warn_threshold

        if level is None:
            return None

        self._fired_levels.add(level)
        if level == DrawdownLevel.HALT:
            self._halt_fired = True

        now_utc = datetime.now(tz=UTC)
        alert = DrawdownAlert(
            triggered_at=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            session_date=self._session_date.isoformat() if self._session_date else "",
            level=level.value,
            current_equity=self._current_equity,
            peak_equity=self._peak_equity,
            drawdown_pct=dd,
            threshold_pct=threshold,
            message=(
                f"[{level.value.upper()}] Intraday drawdown {dd * 100:.2f} % "
                f"exceeded {threshold * 100:.0f} % threshold. "
                f"Peak equity: {self._peak_equity:.2f}, "
                f"Current equity: {self._current_equity:.2f}."
            ),
        )
        self._store.save_alert(alert)
        return alert

    # ------------------------------------------------------------------
    # Status / metrics queries
    # ------------------------------------------------------------------

    @property
    def trading_halted(self) -> bool:
        """``True`` if the HALT threshold was crossed this session."""
        return self._halt_fired

    def get_current_metrics(self) -> dict:
        """
        Return a snapshot of the current intraday state as a plain dict.

        Returns:
            Dictionary with keys: ``session_date``, ``starting_equity``,
            ``current_equity``, ``peak_equity``, ``unrealised_pnl``,
            ``unrealised_pnl_pct``, ``worst_intraday_drawdown_pct``,
            ``trades_placed``, ``trades_filled``, ``wins``, ``losses``,
            ``win_rate``, ``trading_halted``.
        """
        up = self._current_equity - self._starting_equity
        up_pct = up / self._starting_equity if self._starting_equity > 0 else 0.0
        total = self._session_wins + self._session_losses
        return {
            "session_date": self._session_date.isoformat() if self._session_date else "",
            "session_active": self._session_active,
            "starting_equity": self._starting_equity,
            "current_equity": self._current_equity,
            "peak_equity": self._peak_equity,
            "unrealised_pnl": up,
            "unrealised_pnl_pct": up_pct,
            "worst_intraday_drawdown_pct": self._worst_intraday_dd,
            "trades_placed": self._trades_placed,
            "trades_filled": self._trades_filled,
            "wins": self._session_wins,
            "losses": self._session_losses,
            "win_rate": MetricsCalculator.win_rate(self._session_wins, total),
            "trading_halted": self._halt_fired,
        }

    def get_30d_summary(self) -> HarnessSummary:
        """
        Aggregate all persisted snapshots into a :class:`HarnessSummary`.

        Returns:
            :class:`HarnessSummary` — includes ``validation_complete`` flag.
        """
        snapshots = self._store.list_snapshots()
        return MetricsCalculator.build_summary(snapshots, self._sessions_required)

    def is_within_validation_window(self) -> bool:
        """``True`` if fewer than ``sessions_required`` sessions are on disk."""
        return self._store.count_snapshots() < self._sessions_required

    def days_remaining(self) -> int:
        """Number of sessions still needed to complete the 30-day window."""
        return max(0, self._sessions_required - self._store.count_snapshots())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_equity(self) -> float:
        """
        Query Tradier for the current account equity.

        Falls back to ``_equity_override`` if the client is unavailable or
        raises.

        Returns:
            Account equity in USD.
        """
        if self._client is None:
            return self._equity_override
        try:
            balances = self._client.get_account_balances()
            # Tradier returns {"balances": {"total_equity": …}} or similar
            bal_data = balances.get("balances", balances)
            equity = float(
                bal_data.get("total_equity")
                or bal_data.get("equity")
                or bal_data.get("net_value")
                or self._equity_override
            )
            return equity
        except Exception as exc:
            logger.warning("Could not fetch equity from broker: %s — using override", exc)
            return self._equity_override


# ==============================================================================
# FACTORY
# ==============================================================================


def create_paper_trading_harness_from_env(
    snapshot_dir: Path | None = None,
) -> "PaperTradingHarness":
    """
    Build a :class:`PaperTradingHarness` from environment variables.

    Reads:
        ``TRADIER_LIVE_API_KEY``    – broker authentication token.
        ``TRADIER_ACCOUNT_ID`` – account number.
        ``TRADIER_LIVE_ACCOUNT_ID`` (optional override).
        ``PAPER_STARTING_EQUITY`` – override starting equity (default 100 000).
        ``PAPER_SNAPSHOT_DIR``    – root directory for snapshots/alerts.

    If ``TRADIER_LIVE_API_KEY`` is absent **or** the ``tradier`` package is not
    installed, the harness is created with ``broker_client=None`` (dry-run
    mode — equity stays at the override value).

    Args:
        snapshot_dir: Override for the snapshot root directory.

    Returns:
        Ready-to-use :class:`PaperTradingHarness`.
    """
    api_key = os.environ.get("TRADIER_LIVE_API_KEY", "")
    account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
    account_id = os.environ.get("TRADIER_LIVE_ACCOUNT_ID", "").strip() or account_id
    starting_equity = float(os.environ.get("PAPER_STARTING_EQUITY", "100000.0"))

    env_snapshot_dir = os.environ.get("PAPER_SNAPSHOT_DIR", "")
    root = (
        snapshot_dir
        if snapshot_dir
        else (Path(env_snapshot_dir) if env_snapshot_dir else None)
    )
    store = SnapshotStore(root_dir=root)

    client = None
    if HAS_TRADIER and api_key and account_id:
        try:
            configured_env = (os.environ.get("TRADIER_ENVIRONMENT", "live") or "live").strip().lower()
            if configured_env != "live":
                logger.warning(
                    "PaperTradingHarness forcing LIVE market-data endpoint "
                    "(TRADIER_ENVIRONMENT=%s ignored)",
                    configured_env,
                )
            client = TradierClient(
                api_key=api_key,
                account_id=account_id,
                environment=TradingEnvironment.LIVE,
            )
            logger.info("PaperTradingHarness: Tradier LIVE client initialised")
        except Exception as exc:
            logger.warning(
                "PaperTradingHarness: Tradier client init failed (%s) — dry-run mode", exc
            )
    else:
        if not HAS_TRADIER:
            logger.info("PaperTradingHarness: tradier package not available — dry-run mode")
        elif not api_key:
            logger.info("PaperTradingHarness: TRADIER_LIVE_API_KEY not set — dry-run mode")

    return PaperTradingHarness(
        broker_client=client,
        snapshot_store=store,
        starting_equity_override=starting_equity,
    )
