#!/usr/bin/env python3
from __future__ import annotations

"""
TRADOV - Pair scan decision adapters.

Shared helpers that normalize scan output from pair-trading strategies into a
single decision-context contract for the orchestrator and downstream gates.
"""

from types import SimpleNamespace
from typing import Any


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}, ()):
            return value
    return None


def _scan_age_seconds(scan: Any) -> float:
    try:
        return float(_value(scan, "scan_age_seconds", 0.0) or 0.0)
    except Exception:
        return 0.0


def normalize_pair_scan_context(
    scan_result: Any | None,
    *,
    max_age_seconds: float = 300.0,
    min_rank_score: float = 0.0,
) -> Any | None:
    """Normalize a scan payload into the shared pair-decision contract."""
    if scan_result is None:
        return None

    builder = getattr(scan_result, "build_decision_context", None)
    if callable(builder):
        try:
            return builder(
                max_age_seconds=max_age_seconds,
                min_rank_score=min_rank_score,
            )
        except Exception:
            pass

    decision_state = str(_value(scan_result, "decision_state", "unknown"))
    decision_reason = str(_value(scan_result, "decision_reason", ""))
    best_pair_key = _value(scan_result, "best_pair_key", None)
    best_ranking_score = float(_value(scan_result, "best_ranking_score", 0.0) or 0.0)
    scan_age = _scan_age_seconds(scan_result)
    total_candidates = int(_value(scan_result, "total_candidates", 0) or 0)
    tradeable_count = int(_value(scan_result, "tradeable_count", 0) or 0)

    if decision_state == "unknown":
        pairs = _value(scan_result, "ranked_pairs", None) or _value(scan_result, "validated_pairs", None) or []
        if pairs:
            best = pairs[0]
            best_pair_key = _first_non_empty(best_pair_key, _value(best, "pair_key", None))
            best_ranking_score = float(_value(best, "ranking_score", 0.0) or 0.0)
            total_candidates = len(pairs)
            tradeable_count = int(sum(1 for pair in pairs if _value(pair, "is_tradeable", False)))
            decision_state = "ready"
            decision_reason = "scan_ready"
        else:
            decision_state = "hold"
            decision_reason = "no_tradeable_pairs"

    if scan_age > max_age_seconds:
        decision_state = "hold"
        decision_reason = "scan_stale"
    elif best_ranking_score < min_rank_score:
        decision_state = "hold"
        decision_reason = "rank_below_threshold"

    return SimpleNamespace(
        scan_id=_value(scan_result, "scan_id", ""),
        scan_timestamp=_value(scan_result, "timestamp", None),
        scan_age_seconds=scan_age,
        total_candidates=total_candidates,
        tradeable_count=tradeable_count,
        ranked_pairs=_value(scan_result, "ranked_pairs", None) or [],
        validated_pairs=_value(scan_result, "validated_pairs", None) or [],
        best_pair_key=best_pair_key,
        best_ranking_score=best_ranking_score,
        best_ranking_components=dict(_value(scan_result, "best_ranking_components", {}) or {}),
        is_fresh=scan_age <= max_age_seconds,
        decision_state=decision_state,
        decision_reason=decision_reason,
        min_rank_score=min_rank_score,
        max_age_seconds=max_age_seconds,
    )


def build_formed_pair_scan_context(
    formed_pairs: Any,
    *,
    decision_reason: str = "distance_pairs_ready",
) -> Any:
    """Build a context from already-formed distance pairs.

    Populates ``ranked_pairs``/``validated_pairs`` with lightweight per-pair rows
    so the scanner table can render formed distance pairs. Distance metrics
    (SSD-derived score, spread std) are real; p_value / half_life / hedge_ratio
    are not applicable to the distance approach and are reported as neutral
    placeholders.
    """
    pairs = list(formed_pairs or [])
    if not pairs:
        return SimpleNamespace(
            decision_state="hold",
            decision_reason="no_formed_pairs",
            scan_age_seconds=0.0,
            best_pair_key=None,
            best_ranking_score=0.0,
            total_candidates=0,
            tradeable_count=0,
            ranked_pairs=[],
            validated_pairs=[],
        )

    def _ssd(pair: Any) -> float:
        try:
            value = float(_value(pair, "ssd", float("inf")))
        except (TypeError, ValueError):
            return float("inf")
        return value

    def _score_from_ssd(ssd: float) -> float:
        base = 0.0 if ssd == float("inf") else ssd
        return float(max(0.0, 1.0 / (1.0 + base)))

    rows = []
    for pair in pairs:
        pair_key = _first_non_empty(
            _value(pair, "key", None),
            f"{_value(pair, 'symbol_a', '')}/{_value(pair, 'symbol_b', '')}".strip("/"),
        )
        rows.append(
            SimpleNamespace(
                pair_key=pair_key,
                p_value=1.0,        # n/a for the distance approach
                half_life=0.0,      # n/a for the distance approach
                hedge_ratio=1.0,    # distance uses price normalisation, not a hedge ratio
                ranking_score=_score_from_ssd(_ssd(pair)),
                spread_std=float(_value(pair, "spread_std", 0.0) or 0.0),
                is_tradeable=True,
                metadata=_value(pair, "metadata", {}) or {},
            )
        )
    rows.sort(key=lambda r: r.ranking_score, reverse=True)
    best = rows[0]
    return SimpleNamespace(
        decision_state="ready",
        decision_reason=decision_reason,
        scan_age_seconds=0.0,
        best_pair_key=best.pair_key,
        best_ranking_score=best.ranking_score,
        total_candidates=len(pairs),
        tradeable_count=len(rows),
        ranked_pairs=rows,
        validated_pairs=rows,
    )


__all__ = [
    "normalize_pair_scan_context",
    "build_formed_pair_scan_context",
]
