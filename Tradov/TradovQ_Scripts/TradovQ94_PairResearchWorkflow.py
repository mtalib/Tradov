#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovQ_Scripts
Module: TradovQ94_PairResearchWorkflow.py
Purpose: Pair-trading research workflow with walk-forward validation
Author: Codex
Year Created: 2026
Last Updated: 2026-06-18 Time: 00:00:00

Module Description:
    Research workflow for Tradov pair trading. This complements the live
    D51/D52/D53/D54/D42 stack by providing a repeatable offline pipeline for:

    - pair candidate evaluation
    - hedge-ratio comparison
    - spread-regime validation
    - walk-forward scoring
    - simple spread PnL simulation
    - optional artifact registration

    The workflow intentionally uses the existing Tradov pair dataclasses and
    keeps the live execution path untouched.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

_DEFAULT_TRADOV_HOME = str(Path(__file__).resolve().parents[2])
TRADOV_HOME = os.environ.get("TRADOV_HOME", _DEFAULT_TRADOV_HOME)
if TRADOV_HOME not in sys.path:
    sys.path.insert(0, TRADOV_HOME)

try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
except Exception:  # pragma: no cover - fallback for minimal environments
    import logging

    class _FallbackLogger:
        @staticmethod
        def get_logger(name: str):
            return logging.getLogger(name)

    TradovLogger = _FallbackLogger()

try:
    from Tradov.TradovD_Strategies.TradovD50_PairTypes import (
        CointegrationMethod,
        CointegrationResult,
        PairDefinition,
        PairSide,
        PairStatus,
    )
except Exception:  # pragma: no cover - fallback for minimal environments
    class PairSide(Enum):
        LONG_SHORT = "long_short"
        SHORT_LONG = "short_long"

    class PairStatus(Enum):
        CANDIDATE = "candidate"
        VALIDATED = "validated"
        ACTIVE = "active"
        DEGRADED = "degraded"
        BROKEN = "broken"
        EXCLUDED = "excluded"

    class CointegrationMethod(Enum):
        BOTH = "both"

    @dataclass(frozen=True)
    class PairDefinition:
        symbol_a: str
        symbol_b: str
        sector: str
        pair_type: str
        status: str = PairStatus.CANDIDATE
        entry_z: float = 2.0
        exit_z: float = 0.5
        stop_z: float = 3.5
        max_half_life: int = 30
        size_pct: float = 0.02
        lookback: int = 60

        @property
        def key(self) -> str:
            return f"{self.symbol_a}/{self.symbol_b}"

    @dataclass
    class CointegrationResult:
        pair_key: str
        is_cointegrated: bool
        p_value: float
        hedge_ratio: float
        half_life: float
        spread_mean: float
        spread_std: float
        method: Any
        test_statistic: float
        critical_value: float
        sample_size: int
        timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
        metadata: dict[str, Any] = field(default_factory=dict)
        ranking_score: float = 0.0
        ranking_components: dict[str, float] = field(default_factory=dict)

        @property
        def is_tradeable(self) -> bool:
            return self.is_cointegrated and self.half_life > 0 and self.half_life < 30

try:
    from Tradov.TradovD_Strategies.TradovD54_KalmanHedgeRatio import KalmanHedgeRatio
except Exception:  # pragma: no cover - fallback for minimal environments
    KalmanHedgeRatio = None  # type: ignore[assignment]

try:
    from Tradov.TradovL_ML.TradovL01_MLPredictor import (
        Algorithm as TradovAlgorithm,
        ModelType as TradovModelType,
        PredictionTarget as TradovPredictionTarget,
    )
except Exception:  # pragma: no cover - fallback for minimal environments
    class TradovModelType(Enum):
        SIGNAL = "signal"
        REGIME = "regime"

    class TradovAlgorithm(Enum):
        RANDOM_FOREST = "random_forest"
        ENSEMBLE = "ensemble"

    class TradovPredictionTarget(Enum):
        END_OF_DAY = "eod"

TaskType = Literal["pair_research"]


@dataclass(frozen=True)
class PairResearchDatasetContract:
    """Declarative contract for pair research inputs."""

    timestamp_column: str
    price_column_a: str
    price_column_b: str
    symbol_a: str = "A"
    symbol_b: str = "B"
    pair_type: str = "equity_equity"
    train_fraction: float = 0.6
    validation_fraction: float = 0.2
    test_fraction: float = 0.2
    walk_forward_splits: int = 3
    minimum_rows: int = 100
    entry_z: float = 2.0
    exit_z: float = 0.5
    stop_z: float = 3.5
    max_half_life: float = 30.0
    lookback: int = 60

    def validate(self) -> None:
        total = self.train_fraction + self.validation_fraction + self.test_fraction
        if not math.isclose(total, 1.0, rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError(f"train/validation/test fractions must sum to 1.0, got {total:.6f}")
        if self.train_fraction <= 0 or self.validation_fraction <= 0 or self.test_fraction <= 0:
            raise ValueError("dataset fractions must all be positive")
        if self.walk_forward_splits < 2:
            raise ValueError("walk_forward_splits must be at least 2")
        if self.minimum_rows < 10:
            raise ValueError("minimum_rows is too small to support a stable workflow")
        if self.lookback < 5:
            raise ValueError("lookback is too small for pair research")

    @property
    def pair_key(self) -> str:
        return f"{self.symbol_a}/{self.symbol_b}"


@dataclass(frozen=True)
class PairResearchFold:
    fold_index: int
    train_rows: int
    validation_rows: int
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    hedge_ratio: float
    half_life: float
    p_value: float
    spread_mean: float
    spread_std: float
    trade_count: int
    exit_count: int
    final_equity: float
    total_return: float
    sharpe_proxy: float
    max_drawdown: float
    hit_rate: float
    method: str
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PairResearchModelConfig:
    """Model manager-compatible config for pair research artifacts."""

    model_type: TradovModelType
    algorithm: TradovAlgorithm
    target: TradovPredictionTarget
    lookback_period: int
    features: list[str] = field(default_factory=list)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    retrain_frequency: int = 7


@dataclass(frozen=True)
class PairResearchArtifact:
    run_id: str
    created_at: str
    pair_key: str
    pair_status_before: str
    pair_status_after: str
    cointegration_method: str
    hedge_ratio_model: str
    hedge_ratio: float
    spread_mean: float
    spread_std: float
    z_entry: float
    z_exit: float
    z_stop: float
    half_life: float
    pair_quality_score: float
    walk_forward_summary: dict[str, float]
    regime_break_flags: list[str] = field(default_factory=list)
    retire_reason: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PairResearchReport:
    run_id: str
    created_at: str
    contract: PairResearchDatasetContract
    pair_key: str
    row_count: int
    walk_forward_folds: list[PairResearchFold]
    holdout_metrics: dict[str, float]
    backtest_metrics: dict[str, float]
    pair_status: str
    method: str
    pair_status_before: str = "candidate"
    pair_status_after: str = "candidate"
    pair_quality_score: float = 0.0
    retire_reason: str | None = None
    artifact_path: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "contract": asdict(self.contract),
            "pair_key": self.pair_key,
            "row_count": self.row_count,
            "pair_status_before": self.pair_status_before,
            "pair_status_after": self.pair_status_after,
            "pair_quality_score": self.pair_quality_score,
            "retire_reason": self.retire_reason,
            "artifact_path": self.artifact_path,
            "walk_forward_folds": [asdict(fold) for fold in self.walk_forward_folds],
            "holdout_metrics": self.holdout_metrics,
            "backtest_metrics": self.backtest_metrics,
            "pair_status": self.pair_status,
            "method": self.method,
            "notes": self.notes,
        }


def _time_series_split_indices(n_rows: int, n_splits: int) -> list[tuple[np.ndarray, np.ndarray]]:
    if n_splits < 2:
        raise ValueError("n_splits must be at least 2")
    test_size = n_rows // (n_splits + 1)
    if test_size <= 0:
        raise ValueError("insufficient rows for time-series splitting")
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    for split_index in range(n_splits):
        train_end = test_size * (split_index + 1)
        test_start = train_end
        test_end = test_start + test_size
        if split_index == n_splits - 1:
            test_end = n_rows
        splits.append((np.arange(0, train_end), np.arange(test_start, min(test_end, n_rows))))
    return splits


def _estimate_half_life(spread: np.ndarray) -> float:
    if len(spread) < 2:
        return 0.0
    lag = spread[:-1]
    diff = np.diff(spread)
    A = np.column_stack([lag, np.ones(len(lag))])
    try:
        beta = np.linalg.lstsq(A, diff, rcond=None)[0]
    except Exception:
        return 0.0
    lam = float(beta[0])
    if lam >= 0:
        return float("inf")
    return float(-np.log(2) / lam)


def _ols_hedge_ratio(series_a: np.ndarray, series_b: np.ndarray) -> tuple[float, np.ndarray]:
    X = np.column_stack([np.ones(len(series_b)), series_b])
    beta = np.linalg.lstsq(X, series_a, rcond=None)[0]
    hedge_ratio = float(beta[1])
    spread = series_a - hedge_ratio * series_b
    return hedge_ratio, spread


def _simple_cointegration_proxy(
    pair_key: str,
    series_a: np.ndarray,
    series_b: np.ndarray,
) -> CointegrationResult:
    hedge_ratio, spread = _ols_hedge_ratio(series_a, series_b)
    spread_mean = float(np.mean(spread))
    spread_std = float(np.std(spread, ddof=1))
    if spread_std < 1e-10:
        spread_std = 1.0
    half_life = _estimate_half_life(spread)
    corr = np.corrcoef(series_a, series_b)[0, 1] if len(series_a) > 1 else 0.0
    corr = float(np.nan_to_num(corr))
    p_value = float(max(0.0, min(1.0, 0.5 * (1.0 - abs(corr)))))
    return CointegrationResult(
        pair_key=pair_key,
        is_cointegrated=half_life > 0 and half_life < 30 and p_value <= 0.05,
        p_value=p_value,
        hedge_ratio=hedge_ratio,
        half_life=half_life,
        spread_mean=spread_mean,
        spread_std=spread_std,
        method=CointegrationMethod.BOTH,
        test_statistic=float(corr),
        critical_value=0.0,
        sample_size=len(series_a),
        metadata={"fallback": True},
        ranking_score=1.0 - p_value,
        ranking_components={"correlation": abs(corr)},
    )


def _simulate_spread_strategy(
    spreads: np.ndarray,
    train_mean: float,
    train_std: float,
    contract: PairResearchDatasetContract,
) -> tuple[dict[str, float], int, int]:
    if train_std < 1e-10:
        train_std = 1.0

    position = 0
    equity = 1.0
    peak = 1.0
    pnl_values: list[float] = []
    entries = 0
    exits = 0
    prev_spread = spreads[0] if len(spreads) else 0.0

    for spread in spreads[1:]:
        z_score = (spread - train_mean) / train_std
        if position == 0 and abs(z_score) >= contract.entry_z:
            position = -1 if z_score > 0 else 1
            entries += 1
        elif position != 0 and (abs(z_score) <= contract.exit_z or abs(z_score) >= contract.stop_z):
            position = 0
            exits += 1

        spread_delta = spread - prev_spread
        proxy_return = position * (-spread_delta / max(train_std, 1e-6)) * 0.01
        pnl_values.append(proxy_return)
        equity *= 1.0 + proxy_return
        peak = max(peak, equity)
        prev_spread = spread

    returns = np.asarray(pnl_values, dtype=float)
    if len(returns) > 1 and np.std(returns, ddof=1) > 0:
        sharpe_proxy = float(np.mean(returns) / np.std(returns, ddof=1))
    else:
        sharpe_proxy = 0.0
    drawdown = 0.0
    running_equity = 1.0
    peak_equity = 1.0
    for value in returns:
        running_equity *= 1.0 + value
        peak_equity = max(peak_equity, running_equity)
        drawdown = min(drawdown, (running_equity - peak_equity) / peak_equity)

    metrics = {
        "final_equity": float(equity),
        "total_return": float(equity - 1.0),
        "sharpe_proxy": sharpe_proxy,
        "max_drawdown": float(drawdown),
        "hit_rate": float(np.mean(np.asarray(pnl_values) > 0)) if pnl_values else 0.0,
        "trade_count": int(entries),
        "exit_count": int(exits),
    }
    return metrics, entries, exits


def _mean_or_zero(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(np.mean(np.asarray(values, dtype=float)))


def _load_dataframe(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".json":
        return pd.read_json(path)
    raise ValueError(f"unsupported input format: {path.suffix}")


def _parse_features(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_research_model_config(contract: PairResearchDatasetContract) -> PairResearchModelConfig:
    return PairResearchModelConfig(
        model_type=TradovModelType.SIGNAL,
        algorithm=TradovAlgorithm.ENSEMBLE,
        target=TradovPredictionTarget.END_OF_DAY,
        lookback_period=contract.lookback,
        features=[
            "spread",
            "hedge_ratio",
            "z_score",
            "half_life",
            "p_value",
        ],
        hyperparameters={
            "workflow": "q94_pair_research",
            "pair_key": contract.pair_key,
            "entry_z": contract.entry_z,
            "exit_z": contract.exit_z,
            "stop_z": contract.stop_z,
            "max_half_life": contract.max_half_life,
        },
        retrain_frequency=max(1, contract.walk_forward_splits),
    )


def register_pair_research_model(
    manager: Any,
    *,
    model: Any,
    report: PairResearchReport,
    model_name: str,
    model_version: str,
    contract: PairResearchDatasetContract,
) -> str:
    config = build_research_model_config(contract)
    performance_metrics = {
        **{key: float(value) for key, value in report.holdout_metrics.items()},
        **{f"backtest_{key}": float(value) for key, value in report.backtest_metrics.items()},
    }
    metadata = {
        "workflow": "q94_pair_research",
        "run_id": report.run_id,
        "created_at": report.created_at,
        "pair_key": report.pair_key,
        "row_count": report.row_count,
        "pair_status_before": report.pair_status_before,
        "pair_status_after": report.pair_status_after,
        "pair_status": report.pair_status,
        "pair_quality_score": report.pair_quality_score,
        "retire_reason": report.retire_reason,
        "artifact_path": report.artifact_path,
        "method": report.method,
        "contract": asdict(report.contract),
        "notes": list(report.notes),
    }
    return manager.register_model(
        model=model,
        name=model_name,
        version=model_version,
        config=config,
        performance_metrics=performance_metrics,
        metadata=metadata,
    )


class PairResearchWorkflowRunner:
    """Offline pair-trading research workflow."""

    def __init__(
        self,
        contract: PairResearchDatasetContract,
        *,
        random_state: int = 42,
    ) -> None:
        contract.validate()
        self.contract = contract
        self.random_state = random_state
        self.logger = TradovLogger.get_logger(__name__)
        self.last_registered_model_id: str | None = None
        self._artifact_dir = Path(TRADOV_HOME) / ".tradov" / "pair-research"

    def prepare_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        required = [self.contract.timestamp_column, self.contract.price_column_a, self.contract.price_column_b]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise KeyError(f"missing required columns: {missing}")
        if len(frame) < self.contract.minimum_rows:
            raise ValueError(
                f"insufficient rows for pair research: {len(frame)} < {self.contract.minimum_rows}"
            )

        prepared = frame.copy()
        prepared[self.contract.timestamp_column] = pd.to_datetime(
            prepared[self.contract.timestamp_column],
            utc=True,
            errors="coerce",
        )
        prepared = prepared.dropna(subset=[self.contract.timestamp_column])
        prepared = prepared.sort_values(self.contract.timestamp_column).reset_index(drop=True)
        for column in [self.contract.price_column_a, self.contract.price_column_b]:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
        prepared = prepared.dropna(subset=[self.contract.price_column_a, self.contract.price_column_b])
        prepared = prepared.reset_index(drop=True)
        if len(prepared) < self.contract.minimum_rows:
            raise ValueError(
                f"insufficient clean rows for pair research: {len(prepared)} < {self.contract.minimum_rows}"
            )
        return prepared

    def _fit_snapshot(self, series_a: np.ndarray, series_b: np.ndarray) -> tuple[CointegrationResult, dict[str, float], str]:
        pair_key = self.contract.pair_key
        fallback = _simple_cointegration_proxy(pair_key, series_a, series_b)
        method = "fallback_proxy"

        try:
            from Tradov.TradovD_Strategies.TradovD52_CointegrationEngine import CointegrationEngine

            engine = CointegrationEngine(max_half_life=self.contract.max_half_life)
            candidate = engine.test(series_a, series_b, pair_key=pair_key)
            if candidate.is_tradeable:
                fallback = candidate
                method = getattr(candidate.method, "value", str(candidate.method))
        except Exception as exc:
            fallback.metadata["engine_error"] = exc.__class__.__name__

        try:
            if KalmanHedgeRatio is not None:
                kalman = KalmanHedgeRatio(lookback=self.contract.lookback)
                kalman_result = kalman.fit(series_a, series_b)
                spread_mean = float(kalman_result.spread_mean)
                spread_std = float(kalman_result.spread_std or fallback.spread_std)
                hedge_ratio = float(kalman_result.latest_ratio())
                if math.isfinite(spread_std) and spread_std > 0:
                    z_scores = kalman_result.z_scores
                else:
                    z_scores = np.zeros(len(series_a), dtype=float)
            else:
                raise RuntimeError("KalmanHedgeRatio unavailable")
        except Exception:
            hedge_ratio = float(fallback.hedge_ratio)
            spread = series_a - hedge_ratio * series_b
            spread_mean = float(np.mean(spread))
            spread_std = float(np.std(spread, ddof=1))
            if spread_std < 1e-10:
                spread_std = 1.0
            z_scores = (spread - spread_mean) / spread_std

        stats = {
            "hedge_ratio": hedge_ratio,
            "spread_mean": spread_mean,
            "spread_std": spread_std,
            "p_value": float(fallback.p_value),
            "half_life": float(fallback.half_life),
            "z_last": float(z_scores[-1]) if len(z_scores) else 0.0,
        }
        return fallback, stats, method

    def _compare_hedge_ratios(
        self,
        train_frame: pd.DataFrame,
        validation_frame: pd.DataFrame,
        test_frame: pd.DataFrame,
    ) -> dict[str, Any]:
        sections = {
            "train": train_frame,
            "validation": validation_frame,
            "test": test_frame,
        }
        comparison: dict[str, Any] = {"models": {}, "hedge_ratio_std": 0.0}
        ratios: list[float] = []

        for name, section in sections.items():
            if section.empty:
                continue
            series_a = section[self.contract.price_column_a].to_numpy(dtype=float)
            series_b = section[self.contract.price_column_b].to_numpy(dtype=float)
            hedge_ratio, spread = _ols_hedge_ratio(series_a, series_b)
            spread_std = float(np.std(spread, ddof=1)) if len(spread) > 1 else 0.0
            ratios.append(float(hedge_ratio))
            comparison["models"][name] = {
                "hedge_ratio": float(hedge_ratio),
                "spread_std": spread_std,
                "spread_mean": float(np.mean(spread)),
            }

        if ratios:
            comparison["hedge_ratio_std"] = float(np.std(np.asarray(ratios, dtype=float), ddof=1)) if len(ratios) > 1 else 0.0
        comparison["hedge_ratio_stability"] = float(1.0 / (1.0 + comparison["hedge_ratio_std"]))
        return comparison

    def _compute_pair_quality_score(
        self,
        *,
        cointegration_p_value: float,
        half_life: float,
        hedge_ratio_stability: float,
        spread_std: float,
        liquidity_score: float,
        event_risk_score: float,
        tradeable: bool,
    ) -> float:
        p_component = 1.0 - float(np.clip(cointegration_p_value, 0.0, 1.0))
        half_life_component = 1.0 / (1.0 + max(half_life, 0.0))
        spread_component = 1.0 / (1.0 + max(spread_std, 0.0))
        liquidity_component = float(np.clip(liquidity_score, 0.0, 1.0))
        event_component = 1.0 - float(np.clip(event_risk_score, 0.0, 1.0))
        stability_component = float(np.clip(hedge_ratio_stability, 0.0, 1.0))
        tradeable_bonus = 0.1 if tradeable else 0.0
        score = (
            0.30 * p_component
            + 0.20 * half_life_component
            + 0.15 * stability_component
            + 0.10 * spread_component
            + 0.15 * liquidity_component
            + 0.10 * event_component
            + tradeable_bonus
        )
        return float(max(0.0, min(1.0, score)))

    def _build_pair_lifecycle_recommendation(
        self,
        report: PairResearchReport,
        comparison: dict[str, Any],
    ) -> tuple[str, str | None]:
        tradeable = report.holdout_metrics.get("tradeable", 0.0) > 0
        quality = report.pair_quality_score
        hedge_stability = float(comparison.get("hedge_ratio_stability", 0.0))
        half_life = float(report.holdout_metrics.get("half_life", 0.0))

        if not tradeable:
            return "retired", "not_tradeable"
        if quality >= 0.75 and hedge_stability >= 0.5 and half_life <= self.contract.max_half_life:
            return "validated", None
        if quality >= 0.5:
            return "degraded", "borderline_quality"
        return "candidate", "insufficient_quality"

    def _build_artifact(
        self,
        report: PairResearchReport,
        comparison: dict[str, Any],
        method: str,
    ) -> PairResearchArtifact:
        walk_forward_summary = {
            "mean_return": _mean_or_zero([fold.total_return for fold in report.walk_forward_folds]),
            "sharpe_proxy": _mean_or_zero([fold.sharpe_proxy for fold in report.walk_forward_folds]),
            "max_drawdown": float(min([fold.max_drawdown for fold in report.walk_forward_folds], default=0.0)),
            "hit_rate": _mean_or_zero([fold.hit_rate for fold in report.walk_forward_folds]),
            "trade_count": float(sum(fold.trade_count for fold in report.walk_forward_folds)),
        }
        return PairResearchArtifact(
            run_id=report.run_id,
            created_at=report.created_at,
            pair_key=report.pair_key,
            pair_status_before=report.pair_status_before,
            pair_status_after=report.pair_status_after,
            cointegration_method=method,
            hedge_ratio_model="kalman_or_ols",
            hedge_ratio=float(report.holdout_metrics.get("hedge_ratio", 0.0)),
            spread_mean=float(report.holdout_metrics.get("spread_mean", 0.0)),
            spread_std=float(report.holdout_metrics.get("spread_std", 0.0)),
            z_entry=self.contract.entry_z,
            z_exit=self.contract.exit_z,
            z_stop=self.contract.stop_z,
            half_life=float(report.holdout_metrics.get("half_life", 0.0)),
            pair_quality_score=report.pair_quality_score,
            walk_forward_summary=walk_forward_summary,
            regime_break_flags=[],
            retire_reason=report.retire_reason,
            notes=list(report.notes),
        )

    def _persist_report(self, report: PairResearchReport, artifact: PairResearchArtifact) -> Path:
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self._artifact_dir / f"{report.pair_key.replace('/', '_')}.jsonl"
        payload = artifact.to_dict()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return path

    def _load_previous_reports(self, pair_key: str) -> list[dict[str, Any]]:
        path = self._artifact_dir / f"{pair_key.replace('/', '_')}.jsonl"
        if not path.exists():
            return []
        reports: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                reports.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return reports

    def _run_walk_forward(self, frame: pd.DataFrame) -> list[PairResearchFold]:
        folds: list[PairResearchFold] = []
        splits = _time_series_split_indices(len(frame), self.contract.walk_forward_splits)
        for fold_index, (train_idx, validation_idx) in enumerate(splits, start=1):
            train_slice = frame.iloc[train_idx]
            validation_slice = frame.iloc[validation_idx]
            if train_slice.empty or validation_slice.empty:
                continue
            train_series_a = train_slice[self.contract.price_column_a].to_numpy(dtype=float)
            train_series_b = train_slice[self.contract.price_column_b].to_numpy(dtype=float)
            validation_series_a = validation_slice[self.contract.price_column_a].to_numpy(dtype=float)
            validation_series_b = validation_slice[self.contract.price_column_b].to_numpy(dtype=float)

            snapshot, stats, method = self._fit_snapshot(train_series_a, train_series_b)
            val_spread = validation_series_a - stats["hedge_ratio"] * validation_series_b
            metrics, trade_count, exit_count = _simulate_spread_strategy(
                val_spread,
                stats["spread_mean"],
                stats["spread_std"],
                self.contract,
            )
            folds.append(
                PairResearchFold(
                    fold_index=fold_index,
                    train_rows=len(train_slice),
                    validation_rows=len(validation_slice),
                    train_start=train_slice[self.contract.timestamp_column].iloc[0].isoformat(),
                    train_end=train_slice[self.contract.timestamp_column].iloc[-1].isoformat(),
                    validation_start=validation_slice[self.contract.timestamp_column].iloc[0].isoformat(),
                    validation_end=validation_slice[self.contract.timestamp_column].iloc[-1].isoformat(),
                    hedge_ratio=stats["hedge_ratio"],
                    half_life=stats["half_life"],
                    p_value=stats["p_value"],
                    spread_mean=stats["spread_mean"],
                    spread_std=stats["spread_std"],
                    trade_count=trade_count,
                    exit_count=exit_count,
                    final_equity=metrics["final_equity"],
                    total_return=metrics["total_return"],
                    sharpe_proxy=metrics["sharpe_proxy"],
                    max_drawdown=metrics["max_drawdown"],
                    hit_rate=metrics["hit_rate"],
                    method=method,
                    notes=[f"cointegration_tradeable={snapshot.is_tradeable}"],
                )
            )
        return folds

    def _evaluate_holdout(self, train_frame: pd.DataFrame, test_frame: pd.DataFrame) -> tuple[dict[str, float], dict[str, float], str]:
        train_a = train_frame[self.contract.price_column_a].to_numpy(dtype=float)
        train_b = train_frame[self.contract.price_column_b].to_numpy(dtype=float)
        test_a = test_frame[self.contract.price_column_a].to_numpy(dtype=float)
        test_b = test_frame[self.contract.price_column_b].to_numpy(dtype=float)

        snapshot, stats, method = self._fit_snapshot(train_a, train_b)
        holdout_spread = test_a - stats["hedge_ratio"] * test_b
        backtest_metrics, _, _ = _simulate_spread_strategy(
            holdout_spread,
            stats["spread_mean"],
            stats["spread_std"],
            self.contract,
        )

        holdout_metrics = {
            "hedge_ratio": stats["hedge_ratio"],
            "half_life": stats["half_life"],
            "p_value": stats["p_value"],
            "spread_mean": stats["spread_mean"],
            "spread_std": stats["spread_std"],
            "tradeable": 1.0 if snapshot.is_tradeable else 0.0,
            "z_last": stats["z_last"],
        }
        return holdout_metrics, backtest_metrics, method

    def run(self, frame: pd.DataFrame) -> PairResearchReport:
        prepared = self.prepare_frame(frame)
        train_frame, validation_frame, test_frame = self._split_holdout(prepared)
        folds = self._run_walk_forward(prepared.iloc[: len(train_frame) + len(validation_frame)].copy())
        holdout_metrics, backtest_metrics, method = self._evaluate_holdout(train_frame, test_frame)
        comparison = self._compare_hedge_ratios(train_frame, validation_frame, test_frame)
        quality_score = self._compute_pair_quality_score(
            cointegration_p_value=holdout_metrics["p_value"],
            half_life=holdout_metrics["half_life"],
            hedge_ratio_stability=float(comparison.get("hedge_ratio_stability", 0.0)),
            spread_std=holdout_metrics["spread_std"],
            liquidity_score=1.0,
            event_risk_score=0.0,
            tradeable=holdout_metrics["tradeable"] > 0,
        )
        pair_status_after, retire_reason = self._build_pair_lifecycle_recommendation(
            PairResearchReport(
                run_id="preview",
                created_at=datetime.now(UTC).isoformat(),
                contract=self.contract,
                pair_key=self.contract.pair_key,
                row_count=len(prepared),
                walk_forward_folds=folds,
                holdout_metrics=holdout_metrics,
                backtest_metrics=backtest_metrics,
                pair_status="candidate",
                method=method,
            ),
            comparison,
        )
        pair_status_before = "candidate"
        pair_status = pair_status_after

        report = PairResearchReport(
            run_id=f"pair-research-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
            created_at=datetime.now(UTC).isoformat(),
            contract=self.contract,
            pair_key=self.contract.pair_key,
            row_count=len(prepared),
            walk_forward_folds=folds,
            holdout_metrics=holdout_metrics,
            backtest_metrics=backtest_metrics,
            pair_status=pair_status,
            method=method,
            pair_status_before=pair_status_before,
            pair_status_after=pair_status_after,
            pair_quality_score=quality_score,
            retire_reason=retire_reason,
            notes=[
                f"hedge_ratio_stability={comparison.get('hedge_ratio_stability', 0.0):.4f}",
                f"pair_quality_score={quality_score:.4f}",
            ],
        )
        artifact = self._build_artifact(report, comparison, method)
        artifact_path = self._persist_report(report, artifact)
        report = replace(report, artifact_path=str(artifact_path))
        self.logger.info(
            "Pair research complete: pair=%s rows=%s holdout=%s",
            report.pair_key,
            report.row_count,
            holdout_metrics,
        )
        return report

    def run_and_register(
        self,
        frame: pd.DataFrame,
        *,
        manager: Any | None = None,
        model_name: str | None = None,
        model_version: str | None = None,
    ) -> PairResearchReport:
        prepared = self.prepare_frame(frame)
        train_frame, validation_frame, test_frame = self._split_holdout(prepared)
        folds = self._run_walk_forward(prepared.iloc[: len(train_frame) + len(validation_frame)].copy())
        holdout_metrics, backtest_metrics, method = self._evaluate_holdout(train_frame, test_frame)
        comparison = self._compare_hedge_ratios(train_frame, validation_frame, test_frame)
        quality_score = self._compute_pair_quality_score(
            cointegration_p_value=holdout_metrics["p_value"],
            half_life=holdout_metrics["half_life"],
            hedge_ratio_stability=float(comparison.get("hedge_ratio_stability", 0.0)),
            spread_std=holdout_metrics["spread_std"],
            liquidity_score=1.0,
            event_risk_score=0.0,
            tradeable=holdout_metrics["tradeable"] > 0,
        )
        pair_status_after, retire_reason = self._build_pair_lifecycle_recommendation(
            PairResearchReport(
                run_id="preview",
                created_at=datetime.now(UTC).isoformat(),
                contract=self.contract,
                pair_key=self.contract.pair_key,
                row_count=len(prepared),
                walk_forward_folds=folds,
                holdout_metrics=holdout_metrics,
                backtest_metrics=backtest_metrics,
                pair_status="candidate",
                method=method,
            ),
            comparison,
        )
        pair_status_before = "candidate"
        pair_status = pair_status_after
        notes: list[str] = []

        report = PairResearchReport(
            run_id=f"pair-research-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
            created_at=datetime.now(UTC).isoformat(),
            contract=self.contract,
            pair_key=self.contract.pair_key,
            row_count=len(prepared),
            walk_forward_folds=folds,
            holdout_metrics=holdout_metrics,
            backtest_metrics=backtest_metrics,
            pair_status=pair_status,
            method=method,
            pair_status_before=pair_status_before,
            pair_status_after=pair_status_after,
            pair_quality_score=quality_score,
            retire_reason=retire_reason,
            notes=notes,
        )
        artifact = self._build_artifact(report, comparison, method)
        artifact_path = self._persist_report(report, artifact)
        report = replace(report, artifact_path=str(artifact_path))

        try:
            resolved_manager = manager or self._resolve_model_manager()
            if resolved_manager is None:
                notes.append("model_registry_unavailable")
            else:
                resolved_name = model_name or f"pair_research_{self.contract.symbol_a}_{self.contract.symbol_b}"
                resolved_version = model_version or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
                artifact = {
                    "pair_key": report.pair_key,
                    "method": report.method,
                    "holdout_metrics": report.holdout_metrics,
                    "backtest_metrics": report.backtest_metrics,
                    "walk_forward_folds": [asdict(fold) for fold in report.walk_forward_folds],
                }
                model_id = register_pair_research_model(
                    resolved_manager,
                    model=artifact,
                    report=report,
                    model_name=resolved_name,
                    model_version=resolved_version,
                    contract=self.contract,
                )
                self.last_registered_model_id = model_id
                notes.append(f"registered_model_id={model_id}")
        except Exception as exc:
            self.last_registered_model_id = None
            notes.append(f"model_registry_failed={exc.__class__.__name__}")
            self.logger.warning("Pair model registry integration failed: %s", exc)

        self.logger.info(
            "Pair research complete: pair=%s rows=%s holdout=%s",
            report.pair_key,
            report.row_count,
            holdout_metrics,
        )
        return report

    def _resolve_model_manager(self) -> Any | None:
        try:
            from Tradov.TradovL_ML.TradovL11_MLModelManager import get_model_manager

            return get_model_manager()
        except Exception as exc:  # pragma: no cover - optional dependency path
            self.logger.debug("Pair model manager unavailable: %s", exc)
            return None

    def _split_holdout(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        n_rows = len(frame)
        train_end = max(1, int(n_rows * self.contract.train_fraction))
        validation_end = max(train_end + 1, int(n_rows * (self.contract.train_fraction + self.contract.validation_fraction)))
        validation_end = min(validation_end, n_rows - 1)
        train_frame = frame.iloc[:train_end].copy()
        validation_frame = frame.iloc[train_end:validation_end].copy()
        test_frame = frame.iloc[validation_end:].copy()
        if validation_frame.empty:
            raise ValueError("validation split is empty; adjust dataset fractions")
        if test_frame.empty:
            raise ValueError("holdout test split is empty; reduce train/validation fractions")
        return train_frame, validation_frame, test_frame


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a Tradov pair-trading research workflow.",
        epilog=(
            "Boundary: this launcher is for research automation only; "
            "it does not place trades or replace the live D42/E26/B02/B03 pair stack."
        ),
    )
    parser.add_argument("--input", required=True, help="Path to CSV, parquet, or JSON data.")
    parser.add_argument("--timestamp-col", required=True, help="Timestamp column name.")
    parser.add_argument("--price-a-col", required=True, help="Price column for symbol A.")
    parser.add_argument("--price-b-col", required=True, help="Price column for symbol B.")
    parser.add_argument("--symbol-a", default="A", help="Display symbol for A.")
    parser.add_argument("--symbol-b", default="B", help="Display symbol for B.")
    parser.add_argument("--pair-type", default="equity_equity", help="Pair type label.")
    parser.add_argument("--train-fraction", type=float, default=0.6)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--walk-forward-splits", type=int, default=3)
    parser.add_argument("--minimum-rows", type=int, default=100)
    parser.add_argument("--entry-z", type=float, default=2.0)
    parser.add_argument("--exit-z", type=float, default=0.5)
    parser.add_argument("--stop-z", type=float, default=3.5)
    parser.add_argument("--max-half-life", type=float, default=30.0)
    parser.add_argument("--lookback", type=int, default=60)
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    parser.add_argument(
        "--register-model",
        action="store_true",
        help="Register the fitted artifact with the Tradov model manager.",
    )
    parser.add_argument("--model-name", default=None, help="Registry name for the fitted model.")
    parser.add_argument("--model-version", default=None, help="Registry version for the fitted model.")
    return parser


def run_from_args(argv: list[str] | None = None) -> PairResearchReport:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    dataset = _load_dataframe(Path(args.input))
    contract = PairResearchDatasetContract(
        timestamp_column=args.timestamp_col,
        price_column_a=args.price_a_col,
        price_column_b=args.price_b_col,
        symbol_a=args.symbol_a,
        symbol_b=args.symbol_b,
        pair_type=args.pair_type,
        train_fraction=args.train_fraction,
        validation_fraction=args.validation_fraction,
        test_fraction=args.test_fraction,
        walk_forward_splits=args.walk_forward_splits,
        minimum_rows=args.minimum_rows,
        entry_z=args.entry_z,
        exit_z=args.exit_z,
        stop_z=args.stop_z,
        max_half_life=args.max_half_life,
        lookback=args.lookback,
    )

    runner = PairResearchWorkflowRunner(contract)
    if args.register_model or args.model_name or args.model_version:
        report = runner.run_and_register(
            dataset,
            model_name=args.model_name,
            model_version=args.model_version,
        )
    else:
        report = runner.run(dataset)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    if runner.last_registered_model_id:
        print(f"[registry] registered_model_id={runner.last_registered_model_id}")

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return report


def main(argv: list[str] | None = None) -> int:
    run_from_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
