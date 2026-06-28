#!/usr/bin/env python3
from __future__ import annotations

"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovD_Strategies
Module: TradovD30_RegimeGatedSelector.py
Purpose: Compatibility lean selector used by D31 orchestration

This module restores the D30 import surface expected by D31. It provides a
small, deterministic selector that maps the current regime and optional pivot
signal into one of the stat-arb strategy families already hosted by D31.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class StrategyType(Enum):
    Hold = "Hold"
    PairTrading = "PairTrading"
    DistanceApproach = "DistanceApproach"
    PCAStatArb = "PCAStatArb"


@dataclass(frozen=True)
class RegimeSelection:
    selected_strategy: StrategyType | None
    reason: str
    selector_feature_flag: str = "d30_compat"
    scan_state: str = "unknown"
    scan_age_seconds: float | None = None
    scan_rank: int | None = None
    scan_score: float | None = None
    best_pair_key: str | None = None


class RegimeGatedSelector:
    """Compatibility selector for the D31 lean strategy path."""

    def __init__(self, *args: Any, **kwargs: Any):
        self._args = args
        self._kwargs = kwargs

    @staticmethod
    def _regime_name(consensus: Any) -> str:
        regime = getattr(consensus, "regime", None)
        return str(getattr(regime, "value", regime) or "").strip().lower()

    @staticmethod
    def _pivot_strength(pivot_signal: Any) -> float:
        if not isinstance(pivot_signal, dict):
            return 0.0
        for key in ("signal_strength", "confidence", "strength", "score"):
            try:
                return float(pivot_signal.get(key, 0.0) or 0.0)
            except Exception:
                continue
        return 0.0

    @staticmethod
    def _strategy_token(strategy: Any) -> str:
        token = getattr(strategy, "value", strategy)
        return str(token or "").strip().lower()

    @staticmethod
    def _scan_context_value(scan_context: Any, *names: str, default: Any = None) -> Any:
        if scan_context is None:
            return default
        for name in names:
            if isinstance(scan_context, dict) and name in scan_context:
                return scan_context[name]
            if hasattr(scan_context, name):
                return getattr(scan_context, name)
        return default

    @staticmethod
    def _scan_support_score(scan_score: float) -> float:
        # Normalise the scanner's ranking score into a 0..1 support band.
        return max(0.0, min(1.0, scan_score / 2.5))

    def _is_scan_ready(
        self,
        scan_context: Any,
        stale_scan_max_age_seconds: float,
        min_scan_score: float,
    ) -> tuple[bool, str, float, str, str | None]:
        if scan_context is None:
            return True, "no_scan_context", 0.0, "unknown", None

        decision_state = str(self._scan_context_value(scan_context, "decision_state", default="unknown"))
        decision_reason = str(self._scan_context_value(scan_context, "decision_reason", default=""))
        scan_age_seconds = float(self._scan_context_value(scan_context, "scan_age_seconds", default=0.0) or 0.0)
        best_pair_key = self._scan_context_value(scan_context, "best_pair_key", default=None)
        best_score = float(self._scan_context_value(scan_context, "best_ranking_score", default=0.0) or 0.0)
        if decision_state != "ready":
            return False, decision_reason or decision_state or "scan_not_ready", scan_age_seconds, decision_state, best_pair_key
        if scan_age_seconds > stale_scan_max_age_seconds:
            return False, "scan_stale", scan_age_seconds, decision_state, best_pair_key
        if best_score < min_scan_score:
            return False, "scan_rank_too_low", scan_age_seconds, decision_state, best_pair_key
        return True, decision_reason or "scan_ready", scan_age_seconds, decision_state, best_pair_key

    def _selection_score(
        self,
        strategy: StrategyType,
        confidence: float,
        pivot_strength: float,
        scan_score: float,
        regime_name: str,
    ) -> float:
        scan_support = self._scan_support_score(scan_score)
        if strategy is StrategyType.PairTrading:
            return 0.45 * confidence + 0.25 * pivot_strength + 0.30 * scan_support
        if strategy is StrategyType.DistanceApproach:
            range_bonus = 0.25 if ("sideways" in regime_name or "range" in regime_name) else 0.0
            return 0.30 * (1.0 - abs(confidence - 0.5)) + 0.25 * scan_support + range_bonus
        if strategy is StrategyType.PCAStatArb:
            crisis_bonus = 0.40 if ("crisis" in regime_name or "high_vol" in regime_name) else 0.0
            return 0.20 * confidence + 0.20 * scan_support + crisis_bonus
        return 0.0

    def select_strategy_from_consensus(
        self,
        consensus: Any,
        pivot_signal: dict[str, Any] | None = None,
        scan_context: Any | None = None,
        current_strategy: Any | None = None,
        stale_scan_max_age_seconds: float = 300.0,
        min_scan_score: float = 0.15,
        switch_hysteresis: float = 0.10,
    ) -> RegimeSelection:
        regime_name = self._regime_name(consensus)
        confidence = float(getattr(consensus, "confidence", 0.0) or 0.0)
        pivot_strength = self._pivot_strength(pivot_signal)
        scan_ok, scan_reason, scan_age_seconds, scan_state, best_pair_key = self._is_scan_ready(
            scan_context,
            stale_scan_max_age_seconds=stale_scan_max_age_seconds,
            min_scan_score=min_scan_score,
        )
        scan_score = float(self._scan_context_value(scan_context, "best_ranking_score", default=0.0) or 0.0)
        scan_rank = self._scan_context_value(scan_context, "best_rank", default=None)
        if scan_rank is None:
            scan_rank = self._scan_context_value(scan_context, "rank", default=None)
        try:
            scan_rank_int = int(scan_rank) if scan_rank is not None else None
        except Exception:
            scan_rank_int = None

        if not scan_ok:
            return RegimeSelection(
                selected_strategy=StrategyType.Hold,
                reason=scan_reason,
                scan_state=scan_state,
                scan_age_seconds=scan_age_seconds,
                scan_rank=scan_rank_int,
                scan_score=scan_score,
                best_pair_key=best_pair_key if isinstance(best_pair_key, str) else None,
            )

        if "crisis" in regime_name or "high_vol" in regime_name:
            candidate = StrategyType.PCAStatArb
            candidate_reason = "high_volatility_regime"
        elif pivot_strength >= 0.7 or confidence >= 0.7:
            candidate = StrategyType.PairTrading
            candidate_reason = "pivot_or_confidence_supports_pair_trading"
        elif "sideways" in regime_name or "range" in regime_name:
            candidate = StrategyType.DistanceApproach
            candidate_reason = "range_regime_supports_distance_approach"
        else:
            candidate = StrategyType.DistanceApproach
            candidate_reason = "default_distance_approach"

        current_token = self._strategy_token(current_strategy)
        candidate_score = self._selection_score(candidate, confidence, pivot_strength, scan_score, regime_name)
        current_score = self._selection_score(
            StrategyType(current_strategy) if current_token in {t.value.lower() for t in StrategyType} else candidate,
            confidence,
            pivot_strength,
            scan_score,
            regime_name,
        )
        if current_token and current_token != self._strategy_token(candidate):
            if candidate_score < current_score + switch_hysteresis:
                kept = next((item for item in StrategyType if item.value.lower() == current_token), candidate)
                return RegimeSelection(
                    selected_strategy=kept,
                    reason="hysteresis_hold",
                    scan_state=scan_state,
                    scan_age_seconds=scan_age_seconds,
                    scan_rank=scan_rank_int,
                    scan_score=scan_score,
                    best_pair_key=best_pair_key if isinstance(best_pair_key, str) else None,
                )

        return RegimeSelection(
            selected_strategy=candidate,
            reason=candidate_reason,
            scan_state=scan_state,
            scan_age_seconds=scan_age_seconds,
            scan_rank=scan_rank_int,
            scan_score=scan_score,
            best_pair_key=best_pair_key if isinstance(best_pair_key, str) else None,
        )


__all__ = ["RegimeGatedSelector", "StrategyType", "RegimeSelection"]
