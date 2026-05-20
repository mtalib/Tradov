#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderK_Reports
Module: SpyderK13_StrategyPnLLadder.py
Purpose: Live per-strategy P&L attribution ladder during market hours

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-01

Module Description:
    Provides a real-time "strategy P&L ladder" — a ranked, per-strategy
    breakdown of P&L, allocation, and contribution during live trading.

    Data sources:
        • SpyderD31_StrategyOrchestrator — active strategies, allocations,
          strategy-level P&L via get_strategy_performance_attribution()
        • SpyderF17_UnifiedPerformanceEngine — portfolio-level Sharpe, drawdown,
          return attribution via get_current_performance_summary()

    The ladder can be consumed by:
        • The trading dashboard (attach StrategyPnLLadder to a QTimer callback)
        • K02 daily report (call build_ladder() at market close)
        • Any monitoring consumer that calls get_snapshot()

Key Features:
    • Per-strategy: P&L ($), contribution (%), allocation (%), Sharpe, score
    • Portfolio totals row at the bottom
    • Ranked by absolute P&L contribution (descending)
    • Graceful degradation — works without D31 or F17 (returns empty ladder)
    • Thread-safe snapshot via get_snapshot()

Dependencies:
    • SpyderD31_StrategyOrchestrator (optional — guarded)
    • SpyderF17_UnifiedPerformanceEngine (optional — guarded)
    • pandas, numpy (standard Spyder deps)
    • SpyderU01_Logger (graceful fallback)
"""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    _log = SpyderLogger.get_logger(__name__)
except ImportError:
    _log = logging.getLogger(__name__)

try:
    D31_AVAILABLE = True
except (ImportError, NameError):
    D31_AVAILABLE = False
    _log.debug("D31 StrategyOrchestrator not available — K13 will return empty ladder")

try:
    from SpyderF_Analysis.SpyderF17_UnifiedPerformanceEngine import (
        get_unified_performance_engine,
    )
    F17_AVAILABLE = True
except (ImportError, NameError):
    F17_AVAILABLE = False
    _log.debug("F17 UnifiedPerformanceEngine not available — K13 will omit portfolio metrics")


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class StrategyRow:
    """One row in the P&L ladder."""
    rank:              int
    strategy_id:       str
    strategy_name:     str
    strategy_type:     str
    allocation_pct:    float   # fraction of portfolio, e.g. 0.15 = 15%
    allocated_capital: float   # dollar amount
    pnl:               float   # unrealised + realised P&L ($)
    contribution_pct:  float   # strategy P&L / portfolio total P&L (%)
    performance_score: float   # D31 composite score (0-1)
    risk_score:        float   # D31 risk score (0-1; lower = safer)
    health_score:      float   # D31 health score (0-1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank":              self.rank,
            "strategy_id":       self.strategy_id,
            "strategy_name":     self.strategy_name,
            "strategy_type":     self.strategy_type,
            "allocation_pct":    round(self.allocation_pct * 100, 2),
            "allocated_capital": round(self.allocated_capital, 2),
            "pnl":               round(self.pnl, 2),
            "contribution_pct":  round(self.contribution_pct, 4),
            "performance_score": round(self.performance_score, 4),
            "risk_score":        round(self.risk_score, 4),
            "health_score":      round(self.health_score, 4),
        }


@dataclass
class PnLLadderSnapshot:
    """Full ladder snapshot at a point in time."""
    timestamp:         datetime = field(default_factory=lambda: datetime.now(UTC))
    rows:              list[StrategyRow] = field(default_factory=list)
    portfolio_pnl:     float = 0.0
    portfolio_daily_pnl: float = 0.0
    total_strategies:  int = 0
    sharpe_ratio:      float | None = None
    max_drawdown:      float | None = None
    total_return:      float | None = None
    regime_context:    str = ""
    source:            str = "D31"     # "D31", "F17", "hybrid", "empty"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":          self.timestamp.isoformat(),
            "portfolio_pnl":      round(self.portfolio_pnl, 2),
            "portfolio_daily_pnl": round(self.portfolio_daily_pnl, 2),
            "total_strategies":   self.total_strategies,
            "sharpe_ratio":       self.sharpe_ratio,
            "max_drawdown":       self.max_drawdown,
            "total_return":       self.total_return,
            "regime_context":     self.regime_context,
            "source":             self.source,
            "rows":               [r.to_dict() for r in self.rows],
        }

    def to_dataframe(self) -> pd.DataFrame:
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        if not self.rows:
            return pd.DataFrame()
        return pd.DataFrame([r.to_dict() for r in self.rows])

    def formatted_table(self, width: int = 120) -> str:
        """Return a fixed-width ASCII table suitable for logging / CLI output."""
        if not self.rows:
            return "Strategy P&L Ladder: no active strategies"
        header = (
            f"{'Rank':>4}  {'Strategy':<28}  {'Type':<16}  "
            f"{'Alloc%':>7}  {'Capital':>10}  {'P&L ($)':>12}  "
            f"{'Contrib%':>9}  {'Score':>6}  {'Risk':>5}  {'Health':>6}"
        )
        sep = "-" * len(header)
        lines = [
            f"Strategy P&L Ladder — {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Portfolio P&L: ${self.portfolio_pnl:>10,.2f}  |  "
            f"Daily P&L: ${self.portfolio_daily_pnl:>10,.2f}  |  "
            f"Strategies: {self.total_strategies}",
            sep, header, sep,
        ]
        for r in self.rows:
            lines.append(
                f"{r.rank:>4}  {r.strategy_name:<28}  {r.strategy_type:<16}  "
                f"{r.allocation_pct*100:>6.1f}%  "
                f"${r.allocated_capital:>9,.0f}  "
                f"${r.pnl:>11,.2f}  "
                f"{r.contribution_pct*100:>8.2f}%  "
                f"{r.performance_score:>6.3f}  "
                f"{r.risk_score:>5.3f}  "
                f"{r.health_score:>6.3f}"
            )
        if self.sharpe_ratio is not None:
            lines.append(sep)
            lines.append(
                f"Sharpe: {self.sharpe_ratio:.3f}  |  "
                f"MaxDD: {(self.max_drawdown or 0)*100:.2f}%  |  "
                f"TotalReturn: {(self.total_return or 0)*100:.2f}%  |  "
                f"Regime: {self.regime_context}"
            )
        return "\n".join(lines)


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class StrategyPnLLadder:
    """
    Real-time per-strategy P&L attribution ladder.

    Usage::

        ladder = StrategyPnLLadder(orchestrator=my_d31_orchestrator)
        snapshot = ladder.build_ladder()
        print(snapshot.formatted_table())

        # Or call get_snapshot() for the last cached result:
        snapshot = ladder.get_snapshot()
    """

    def __init__(
        self,
        orchestrator: Any | None = None,
        performance_engine: Any | None = None,
    ) -> None:
        """
        Args:
            orchestrator:       D31 StrategyOrchestrator instance (or None to
                                try importing a singleton at first call).
            performance_engine: F17 UnifiedPerformanceEngine instance (optional).
        """
        self._orchestrator   = orchestrator
        self._perf_engine    = performance_engine
        self._lock           = threading.Lock()
        # Keep a non-null snapshot so read-only consumers can always render safely.
        self._last_snapshot: PnLLadderSnapshot = PnLLadderSnapshot(source="empty")
        self._log            = _log

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_ladder(self) -> PnLLadderSnapshot:
        """
        Build and cache a fresh P&L ladder snapshot from D31 + F17.

        Returns an empty snapshot if no orchestrator is available.
        """
        orchestrator = self._get_orchestrator()
        if orchestrator is None:
            snapshot = PnLLadderSnapshot(source="empty")
            with self._lock:
                self._last_snapshot = snapshot
            return snapshot

        snapshot = self._build_from_d31(orchestrator)
        self._enrich_from_f17(snapshot)

        with self._lock:
            self._last_snapshot = snapshot

        self._log.debug(
            "P&L ladder built: %d strategies, portfolio P&L $%.2f",
            snapshot.total_strategies, snapshot.portfolio_pnl,
        )
        return snapshot

    def get_snapshot(self) -> PnLLadderSnapshot:
        """Return the last cached snapshot (always available)."""
        with self._lock:
            return self._last_snapshot

    def log_ladder(self) -> None:
        """Build and log the current ladder at INFO level."""
        snapshot = self.build_ladder()
        self._log.info("\n%s", snapshot.formatted_table())

    # ------------------------------------------------------------------
    # D31 integration
    # ------------------------------------------------------------------

    def _get_orchestrator(self) -> Any | None:
        if self._orchestrator is not None:
            return self._orchestrator
        if not D31_AVAILABLE:
            return None
        return None   # caller must inject orchestrator explicitly

    def _build_from_d31(self, orchestrator: Any) -> PnLLadderSnapshot:
        try:
            status = orchestrator.get_status()
            portfolio_pnl       = float(status.get("total_pnl", 0.0))
            portfolio_daily_pnl = float(status.get("daily_pnl", 0.0))
            n_strategies        = int(status.get("active_strategies", 0))
        except Exception as exc:
            self._log.error("Failed to read D31 status: %s", exc, exc_info=True)
            return PnLLadderSnapshot(source="empty")

        rows: list[StrategyRow] = []
        try:
            df = orchestrator.get_strategy_performance_attribution()
            if df is None or (HAS_PANDAS and df.empty):
                return PnLLadderSnapshot(
                    portfolio_pnl=portfolio_pnl,
                    portfolio_daily_pnl=portfolio_daily_pnl,
                    total_strategies=n_strategies,
                    source="D31",
                )

            # Build rows
            for i, row_data in enumerate(_iter_df(df)):
                pnl  = float(row_data.get("strategy_pnl", 0.0))
                alloc = float(row_data.get("allocation", 0.0))
                contrib = (pnl / portfolio_pnl) if portfolio_pnl else 0.0
                rows.append(StrategyRow(
                    rank=i + 1,
                    strategy_id=str(row_data.get("strategy_id", f"S{i+1}")),
                    strategy_name=str(row_data.get("strategy_name", "Unknown")),
                    strategy_type=str(row_data.get("strategy_type", "")),
                    allocation_pct=alloc,
                    allocated_capital=float(row_data.get("allocated_capital", 0.0)),
                    pnl=pnl,
                    contribution_pct=contrib,
                    performance_score=float(row_data.get("performance_score", 0.0)),
                    risk_score=float(row_data.get("risk_score", 0.0)),
                    health_score=float(row_data.get("health_score", 0.0)),
                ))

            # Sort by absolute P&L descending and re-rank
            rows.sort(key=lambda r: abs(r.pnl), reverse=True)
            for idx, r in enumerate(rows):
                r.rank = idx + 1

        except Exception as exc:
            self._log.error("Failed to build attribution rows from D31: %s", exc, exc_info=True)

        return PnLLadderSnapshot(
            rows=rows,
            portfolio_pnl=portfolio_pnl,
            portfolio_daily_pnl=portfolio_daily_pnl,
            total_strategies=n_strategies,
            source="D31",
        )

    # ------------------------------------------------------------------
    # F17 enrichment
    # ------------------------------------------------------------------

    def _enrich_from_f17(self, snapshot: PnLLadderSnapshot) -> None:
        """Add portfolio-level Sharpe / drawdown / return from F17 if available."""
        engine = self._get_perf_engine()
        if engine is None:
            return
        try:
            summary = engine.get_current_performance_summary()
            if "error" in summary:
                return
            perf = summary.get("performance_summary", {})
            snapshot.sharpe_ratio   = perf.get("sharpe_ratio")
            snapshot.max_drawdown   = perf.get("max_drawdown")
            snapshot.total_return   = perf.get("total_return")
            snapshot.regime_context = str(summary.get("regime_context", ""))
            snapshot.source = "hybrid"
        except Exception as exc:
            self._log.debug("F17 enrichment skipped: %s", exc)

    def _get_perf_engine(self) -> Any | None:
        if self._perf_engine is not None:
            return self._perf_engine
        if not F17_AVAILABLE:
            return None
        try:
            return get_unified_performance_engine()
        except Exception:
            return None


# ==============================================================================
# HELPERS
# ==============================================================================

def _iter_df(df: Any):
    """Yield row dicts from a DataFrame or list-of-dicts."""
    if HAS_PANDAS and isinstance(df, pd.DataFrame):
        for _, row in df.iterrows():
            yield row.to_dict()
    elif isinstance(df, list):
        yield from df


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================

_ladder: StrategyPnLLadder | None = None
_ladder_lock = threading.Lock()


def get_ladder(
    orchestrator: Any | None = None,
    performance_engine: Any | None = None,
) -> StrategyPnLLadder:
    """Return the module-level StrategyPnLLadder singleton."""
    global _ladder
    with _ladder_lock:
        if _ladder is None:
            _ladder = StrategyPnLLadder(
                orchestrator=orchestrator,
                performance_engine=performance_engine,
            )
    return _ladder
