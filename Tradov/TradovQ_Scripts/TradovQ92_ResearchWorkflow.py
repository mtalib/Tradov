#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovQ_Scripts
Module: TradovQ92_ResearchWorkflow.py
Purpose: Qlib-inspired research workflow runner for repeatable ML experiments
Author: Codex
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    Provides a compact, code-first research workflow for Tradov that mirrors the
    useful parts of Qlib's workflow discipline:

    - dataset contract validation
    - time-ordered train/validation/test splits
    - walk-forward validation
    - holdout evaluation
    - simple backtest-style equity simulation
    - JSON artifact emission for downstream review

    The runner is intentionally small. It does not replace Tradov's production
    strategy stack; it creates a repeatable offline research surface for regime,
    signal, and execution models.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

try:  # pragma: no cover - exercised indirectly via fallback in this environment
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        mean_absolute_error,
        mean_squared_error,
        precision_score,
        r2_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import TimeSeriesSplit
    _SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - fallback for minimal environments
    _SKLEARN_AVAILABLE = False

    def accuracy_score(y_true, y_pred):
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        return float(np.mean(y_true == y_pred))

    def precision_score(y_true, y_pred, zero_division=0):
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        tp = float(np.sum((y_true == 1) & (y_pred == 1)))
        fp = float(np.sum((y_true == 0) & (y_pred == 1)))
        if tp + fp == 0:
            return float(zero_division)
        return tp / (tp + fp)

    def recall_score(y_true, y_pred, zero_division=0):
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        tp = float(np.sum((y_true == 1) & (y_pred == 1)))
        fn = float(np.sum((y_true == 1) & (y_pred == 0)))
        if tp + fn == 0:
            return float(zero_division)
        return tp / (tp + fn)

    def f1_score(y_true, y_pred, zero_division=0):
        precision = precision_score(y_true, y_pred, zero_division=zero_division)
        recall = recall_score(y_true, y_pred, zero_division=zero_division)
        if precision + recall == 0:
            return float(zero_division)
        return 2.0 * precision * recall / (precision + recall)

    def mean_absolute_error(y_true, y_pred):
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        return float(np.mean(np.abs(y_true - y_pred)))

    def mean_squared_error(y_true, y_pred):
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        return float(np.mean((y_true - y_pred) ** 2))

    def r2_score(y_true, y_pred):
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        total_variance = np.sum((y_true - np.mean(y_true)) ** 2)
        if total_variance == 0:
            return 0.0
        residual_variance = np.sum((y_true - y_pred) ** 2)
        return float(1.0 - (residual_variance / total_variance))

    def roc_auc_score(y_true, y_score):
        y_true = np.asarray(y_true, dtype=int)
        y_score = np.asarray(y_score, dtype=float)
        pos = y_score[y_true == 1]
        neg = y_score[y_true == 0]
        if len(pos) == 0 or len(neg) == 0:
            raise ValueError("roc_auc_score requires both classes")
        wins = 0.0
        ties = 0.0
        for score in pos:
            wins += np.sum(score > neg)
            ties += np.sum(score == neg)
        return float((wins + 0.5 * ties) / (len(pos) * len(neg)))

    class TimeSeriesSplit:
        def __init__(self, n_splits: int):
            if n_splits < 2:
                raise ValueError("n_splits must be at least 2")
            self.n_splits = n_splits

        def split(self, X):
            n_samples = len(X)
            test_size = n_samples // (self.n_splits + 1)
            if test_size == 0:
                raise ValueError("insufficient samples for time series split")
            for split_index in range(self.n_splits):
                train_end = test_size * (split_index + 1)
                test_start = train_end
                test_end = test_start + test_size
                if split_index == self.n_splits - 1:
                    test_end = n_samples
                yield np.arange(0, train_end), np.arange(test_start, min(test_end, n_samples))

    class RandomForestClassifier:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            self.majority_class_ = 0
            self.class_prob_ = 0.5

        def fit(self, X, y):
            values, counts = np.unique(np.asarray(y), return_counts=True)
            self.majority_class_ = int(values[np.argmax(counts)])
            self.class_prob_ = float(np.mean(np.asarray(y) == 1))
            return self

        def predict(self, X):
            return np.full(len(X), self.majority_class_, dtype=int)

        def predict_proba(self, X):
            proba = np.column_stack([
                np.full(len(X), 1.0 - self.class_prob_, dtype=float),
                np.full(len(X), self.class_prob_, dtype=float),
            ])
            return proba

    class RandomForestRegressor:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            self.mean_ = 0.0

        def fit(self, X, y):
            self.mean_ = float(np.mean(np.asarray(y, dtype=float)))
            return self

        def predict(self, X):
            return np.full(len(X), self.mean_, dtype=float)

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
    from Tradov.TradovL_ML.TradovL01_MLPredictor import (
        Algorithm as TradovAlgorithm,
        ModelType as TradovModelType,
        PredictionTarget as TradovPredictionTarget,
    )
except Exception:  # pragma: no cover - fallback for minimal environments
    class TradovModelType(str, Enum):
        DIRECTION = "direction"
        VOLATILITY = "volatility"
        PRICE = "price"
        SIGNAL = "signal"
        REGIME = "regime"

    class TradovAlgorithm(str, Enum):
        RANDOM_FOREST = "random_forest"
        XGBOOST = "xgboost"
        LIGHTGBM = "lightgbm"
        LSTM = "lstm"
        ENSEMBLE = "ensemble"

    class TradovPredictionTarget(str, Enum):
        NEXT_CANDLE = "next_candle"
        FIVE_MINUTES = "5min"
        FIFTEEN_MINUTES = "15min"
        ONE_HOUR = "1h"
        END_OF_DAY = "eod"


TaskType = Literal["classification", "regression"]


@dataclass(frozen=True)
class ResearchDatasetContract:
    """Declarative contract for a research dataset."""

    timestamp_column: str
    feature_columns: list[str]
    label_column: str
    return_column: str | None = None
    task_type: TaskType = "classification"
    train_fraction: float = 0.6
    validation_fraction: float = 0.2
    test_fraction: float = 0.2
    walk_forward_splits: int = 3
    minimum_rows: int = 100

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


@dataclass(frozen=True)
class WalkForwardFold:
    fold_index: int
    train_rows: int
    validation_rows: int
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchWorkflowReport:
    """Result bundle emitted by a research run."""

    run_id: str
    created_at: str
    contract: ResearchDatasetContract
    row_count: int
    feature_count: int
    walk_forward_folds: list[WalkForwardFold]
    holdout_metrics: dict[str, float]
    backtest_metrics: dict[str, float]
    model_name: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "contract": asdict(self.contract),
            "row_count": self.row_count,
            "feature_count": self.feature_count,
            "walk_forward_folds": [asdict(fold) for fold in self.walk_forward_folds],
            "holdout_metrics": self.holdout_metrics,
            "backtest_metrics": self.backtest_metrics,
            "model_name": self.model_name,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ResearchModelConfig:
    """Model manager-compatible config for research artifacts."""

    model_type: TradovModelType
    algorithm: TradovAlgorithm
    target: TradovPredictionTarget
    lookback_period: int
    features: list[str] = field(default_factory=list)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    retrain_frequency: int = 7


def _safe_enum_value(enum_or_value: Any) -> Any:
    return getattr(enum_or_value, "value", enum_or_value)


def build_research_model_config(
    contract: ResearchDatasetContract,
    *,
    model_type: str = "signal",
    algorithm: str = "random_forest",
    target: str = "next_candle",
) -> ResearchModelConfig:
    """Build a Tradov MLModelManager-compatible config for a research run."""

    return ResearchModelConfig(
        model_type=TradovModelType(model_type),
        algorithm=TradovAlgorithm(algorithm),
        target=TradovPredictionTarget(target),
        lookback_period=max(1, contract.walk_forward_splits),
        features=list(contract.feature_columns),
        hyperparameters={
            "workflow": "q92_research",
            "task_type": contract.task_type,
            "train_fraction": contract.train_fraction,
            "validation_fraction": contract.validation_fraction,
            "test_fraction": contract.test_fraction,
            "minimum_rows": contract.minimum_rows,
        },
        retrain_frequency=max(1, contract.walk_forward_splits),
    )


def register_research_model(
    manager: Any,
    *,
    model: Any,
    report: ResearchWorkflowReport,
    model_name: str,
    model_version: str,
    contract: ResearchDatasetContract,
    model_type: str = "signal",
    algorithm: str = "random_forest",
    target: str = "next_candle",
) -> str:
    """
    Register a research artifact with the existing Tradov model manager.

    The manager only needs to expose ``register_model`` with the standard Tradov
    signature; this keeps the workflow testable with a fake manager.
    """

    config = build_research_model_config(
        contract,
        model_type=model_type,
        algorithm=algorithm,
        target=target,
    )
    performance_metrics = {
        **{key: float(value) for key, value in report.holdout_metrics.items()},
        **{f"backtest_{key}": float(value) for key, value in report.backtest_metrics.items()},
    }
    metadata = {
        "workflow": "q92_research",
        "run_id": report.run_id,
        "created_at": report.created_at,
        "row_count": report.row_count,
        "feature_count": report.feature_count,
        "walk_forward_folds": [asdict(fold) for fold in report.walk_forward_folds],
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


class ResearchWorkflowRunner:
    """
    Qlib-inspired offline research workflow.

    The runner expects a time-ordered dataframe containing features, a label
    column, and optionally a realized return column used to simulate a simple
    long/short strategy on the holdout set.
    """

    def __init__(
        self,
        contract: ResearchDatasetContract,
        *,
        model: Any | None = None,
        random_state: int = 42,
    ) -> None:
        contract.validate()
        self.contract = contract
        self.random_state = random_state
        self.model = model or self._build_default_model()
        self.logger = TradovLogger.get_logger(__name__)
        self.last_registered_model_id: str | None = None

    def _build_default_model(self) -> Any:
        if self.contract.task_type == "regression":
            return RandomForestRegressor(
                n_estimators=200,
                random_state=self.random_state,
                n_jobs=-1,
            )
        return RandomForestClassifier(
            n_estimators=200,
            random_state=self.random_state,
            n_jobs=-1,
        )

    def prepare_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        missing = [column for column in [self.contract.timestamp_column, self.contract.label_column, *self.contract.feature_columns] if column not in frame.columns]
        if missing:
            raise KeyError(f"missing required columns: {missing}")
        if len(frame) < self.contract.minimum_rows:
            raise ValueError(
                f"insufficient rows for research workflow: {len(frame)} < {self.contract.minimum_rows}"
            )

        prepared = frame.copy()
        prepared[self.contract.timestamp_column] = pd.to_datetime(
            prepared[self.contract.timestamp_column],
            utc=True,
            errors="coerce",
        )
        prepared = prepared.dropna(subset=[self.contract.timestamp_column])
        prepared = prepared.sort_values(self.contract.timestamp_column).reset_index(drop=True)

        numeric_columns = [*self.contract.feature_columns, self.contract.label_column]
        if self.contract.return_column:
            numeric_columns.append(self.contract.return_column)
        for column in numeric_columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

        prepared = prepared.dropna(subset=[self.contract.label_column, *self.contract.feature_columns])
        if self.contract.return_column:
            prepared = prepared.dropna(subset=[self.contract.return_column])
        prepared = prepared.reset_index(drop=True)
        if len(prepared) < self.contract.minimum_rows:
            raise ValueError(
                f"insufficient clean rows for research workflow: {len(prepared)} < {self.contract.minimum_rows}"
            )
        return prepared

    def run(self, frame: pd.DataFrame) -> ResearchWorkflowReport:
        prepared = self.prepare_frame(frame)
        train_frame, validation_frame, test_frame = self._split_holdout(prepared)
        folds = self._run_walk_forward(prepared.iloc[: len(train_frame) + len(validation_frame)].copy())

        fitted = self._clone_model()
        fitted.fit(train_frame[self.contract.feature_columns], train_frame[self.contract.label_column])

        holdout_metrics, backtest_metrics = self._evaluate_holdout(fitted, test_frame)

        report = ResearchWorkflowReport(
            run_id=f"research-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
            created_at=datetime.now(UTC).isoformat(),
            contract=self.contract,
            row_count=len(prepared),
            feature_count=len(self.contract.feature_columns),
            walk_forward_folds=folds,
            holdout_metrics=holdout_metrics,
            backtest_metrics=backtest_metrics,
            model_name=type(fitted).__name__,
        )
        self.logger.info(
            "Research workflow complete: rows=%s features=%s holdout=%s",
            report.row_count,
            report.feature_count,
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
        model_type: str = "signal",
        algorithm: str = "random_forest",
        target: str = "next_candle",
    ) -> ResearchWorkflowReport:
        """Run the workflow and optionally register the fitted model artifact."""

        prepared = self.prepare_frame(frame)
        train_frame, validation_frame, test_frame = self._split_holdout(prepared)
        folds = self._run_walk_forward(prepared.iloc[: len(train_frame) + len(validation_frame)].copy())

        fitted = self._clone_model()
        fitted.fit(train_frame[self.contract.feature_columns], train_frame[self.contract.label_column])

        holdout_metrics, backtest_metrics = self._evaluate_holdout(fitted, test_frame)
        notes: list[str] = []

        report = ResearchWorkflowReport(
            run_id=f"research-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
            created_at=datetime.now(UTC).isoformat(),
            contract=self.contract,
            row_count=len(prepared),
            feature_count=len(self.contract.feature_columns),
            walk_forward_folds=folds,
            holdout_metrics=holdout_metrics,
            backtest_metrics=backtest_metrics,
            model_name=type(fitted).__name__,
            notes=notes,
        )

        try:
            resolved_manager = manager or self._resolve_model_manager()
            if resolved_manager is None:
                notes.append("model_registry_unavailable")
            else:
                resolved_name = model_name or f"research_{self.contract.label_column}"
                resolved_version = model_version or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
                model_id = register_research_model(
                    resolved_manager,
                    model=fitted,
                    report=report,
                    model_name=resolved_name,
                    model_version=resolved_version,
                    contract=self.contract,
                    model_type=model_type,
                    algorithm=algorithm,
                    target=target,
                )
                self.last_registered_model_id = model_id
                notes.append(f"registered_model_id={model_id}")
        except Exception as exc:
            self.last_registered_model_id = None
            notes.append(f"model_registry_failed={exc.__class__.__name__}")
            self.logger.warning("Model registry integration failed: %s", exc)

        self.logger.info(
            "Research workflow complete: rows=%s features=%s holdout=%s",
            report.row_count,
            report.feature_count,
            holdout_metrics,
        )
        return report

    def _clone_model(self) -> Any:
        if self.contract.task_type == "regression":
            return RandomForestRegressor(
                n_estimators=200,
                random_state=self.random_state,
                n_jobs=-1,
            )
        return RandomForestClassifier(
            n_estimators=200,
            random_state=self.random_state,
            n_jobs=-1,
        )

    def _resolve_model_manager(self) -> Any | None:
        try:
            from Tradov.TradovL_ML.TradovL11_MLModelManager import get_model_manager

            return get_model_manager()
        except Exception as exc:  # pragma: no cover - optional dependency path
            self.logger.debug("Model manager unavailable: %s", exc)
            return None

    def _split_holdout(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        n_rows = len(frame)
        train_end = max(1, int(n_rows * self.contract.train_fraction))
        validation_end = max(train_end + 1, int(n_rows * (self.contract.train_fraction + self.contract.validation_fraction)))
        validation_end = min(validation_end, n_rows - 1)
        train_frame = frame.iloc[:train_end].copy()
        validation_frame = frame.iloc[train_end:validation_end].copy()
        test_frame = frame.iloc[validation_end:].copy()
        if test_frame.empty:
            raise ValueError("holdout test split is empty; reduce train/validation fractions")
        if validation_frame.empty:
            raise ValueError("validation split is empty; adjust dataset fractions")
        return train_frame, validation_frame, test_frame

    def _run_walk_forward(self, frame: pd.DataFrame) -> list[WalkForwardFold]:
        if len(frame) < 2 * self.contract.walk_forward_splits:
            return []

        splitter = TimeSeriesSplit(n_splits=self.contract.walk_forward_splits)
        folds: list[WalkForwardFold] = []
        for fold_index, (train_idx, validation_idx) in enumerate(splitter.split(frame), start=1):
            train_slice = frame.iloc[train_idx]
            validation_slice = frame.iloc[validation_idx]
            if train_slice.empty or validation_slice.empty:
                continue
            model = self._clone_model()
            model.fit(train_slice[self.contract.feature_columns], train_slice[self.contract.label_column])
            metrics = self._evaluate_predictions(
                model,
                validation_slice[self.contract.feature_columns],
                validation_slice[self.contract.label_column],
            )
            folds.append(
                WalkForwardFold(
                    fold_index=fold_index,
                    train_rows=len(train_slice),
                    validation_rows=len(validation_slice),
                    train_start=train_slice[self.contract.timestamp_column].iloc[0].isoformat(),
                    train_end=train_slice[self.contract.timestamp_column].iloc[-1].isoformat(),
                    validation_start=validation_slice[self.contract.timestamp_column].iloc[0].isoformat(),
                    validation_end=validation_slice[self.contract.timestamp_column].iloc[-1].isoformat(),
                    metrics=metrics,
                )
            )
        return folds

    def _evaluate_holdout(self, model: Any, test_frame: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
        metrics = self._evaluate_predictions(
            model,
            test_frame[self.contract.feature_columns],
            test_frame[self.contract.label_column],
        )
        backtest_metrics = self._simulate_backtest(model, test_frame)
        return metrics, backtest_metrics

    def _evaluate_predictions(
        self,
        model: Any,
        features: pd.DataFrame,
        labels: pd.Series,
    ) -> dict[str, float]:
        predictions = model.predict(features)
        metrics: dict[str, float] = {}

        if self.contract.task_type == "regression":
            metrics["mae"] = float(mean_absolute_error(labels, predictions))
            metrics["rmse"] = float(math.sqrt(mean_squared_error(labels, predictions)))
            metrics["r2"] = float(r2_score(labels, predictions))
            metrics["directional_accuracy"] = float(np.mean(np.sign(predictions) == np.sign(labels)))
            return metrics

        metrics["accuracy"] = float(accuracy_score(labels, predictions))
        metrics["precision"] = float(precision_score(labels, predictions, zero_division=0))
        metrics["recall"] = float(recall_score(labels, predictions, zero_division=0))
        metrics["f1"] = float(f1_score(labels, predictions, zero_division=0))
        if hasattr(model, "predict_proba") and len(np.unique(labels)) == 2:
            probabilities = model.predict_proba(features)[:, 1]
            try:
                metrics["roc_auc"] = float(roc_auc_score(labels, probabilities))
            except ValueError:
                metrics["roc_auc"] = float("nan")
        return metrics

    def _simulate_backtest(self, model: Any, test_frame: pd.DataFrame) -> dict[str, float]:
        if self.contract.return_column is None:
            return {}

        returns = test_frame[self.contract.return_column].astype(float).to_numpy()
        if self.contract.task_type == "regression":
            raw_signal = np.asarray(model.predict(test_frame[self.contract.feature_columns]), dtype=float)
            signal = np.where(raw_signal >= 0.0, 1.0, -1.0)
        else:
            if hasattr(model, "predict_proba"):
                raw_signal = model.predict_proba(test_frame[self.contract.feature_columns])[:, 1]
                signal = np.where(raw_signal >= 0.5, 1.0, -1.0)
            else:
                signal = np.asarray(model.predict(test_frame[self.contract.feature_columns]), dtype=float)
                signal = np.where(signal > 0, 1.0, -1.0)

        strategy_returns = signal * returns
        equity_curve = np.cumprod(1.0 + strategy_returns)
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak

        return {
            "total_return": float(equity_curve[-1] - 1.0),
            "annualized_return_proxy": float(np.mean(strategy_returns) * 252.0),
            "sharpe_proxy": float(
                np.mean(strategy_returns) / np.std(strategy_returns, ddof=1)
                if len(strategy_returns) > 1 and np.std(strategy_returns, ddof=1) > 0
                else 0.0
            ),
            "max_drawdown": float(np.min(drawdown)),
            "hit_rate": float(np.mean(strategy_returns > 0)),
        }


def _load_dataframe(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path)
    if suffix in {".parquet"}:
        return pd.read_parquet(path)
    if suffix in {".json"}:
        return pd.read_json(path)
    raise ValueError(f"unsupported input format: {path.suffix}")


def _parse_features(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a Tradov research workflow.",
        epilog=(
            "Boundary: this launcher is for Qlib-style research automation only; "
            "it does not control live trading, broker execution, or pair-trading logic."
        ),
    )
    parser.add_argument("--input", required=True, help="Path to CSV, parquet, or JSON data.")
    parser.add_argument("--timestamp-col", required=True, help="Timestamp column name.")
    parser.add_argument("--label-col", required=True, help="Label column name.")
    parser.add_argument("--features", required=True, help="Comma-separated feature columns.")
    parser.add_argument("--return-col", default=None, help="Optional realized return column.")
    parser.add_argument(
        "--task",
        choices=("classification", "regression"),
        default="classification",
        help="Modeling task type.",
    )
    parser.add_argument("--train-fraction", type=float, default=0.6)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--walk-forward-splits", type=int, default=3)
    parser.add_argument("--minimum-rows", type=int, default=100)
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    parser.add_argument(
        "--register-model",
        action="store_true",
        help="Register the fitted artifact with the Tradov model manager.",
    )
    parser.add_argument("--model-name", default=None, help="Registry name for the fitted model.")
    parser.add_argument("--model-version", default=None, help="Registry version for the fitted model.")
    parser.add_argument(
        "--model-type",
        default="signal",
        choices=("direction", "volatility", "price", "signal", "regime"),
        help="Tradov model type for registration.",
    )
    parser.add_argument(
        "--algorithm",
        default="random_forest",
        choices=("random_forest", "xgboost", "lightgbm", "lstm", "ensemble"),
        help="Algorithm label recorded in the registry.",
    )
    parser.add_argument(
        "--prediction-target",
        default="next_candle",
        choices=("next_candle", "5min", "15min", "1h", "eod"),
        help="Prediction target label recorded in the registry.",
    )
    return parser


def run_from_args(argv: list[str] | None = None) -> ResearchWorkflowReport:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    dataset = _load_dataframe(Path(args.input))
    contract = ResearchDatasetContract(
        timestamp_column=args.timestamp_col,
        feature_columns=_parse_features(args.features),
        label_column=args.label_col,
        return_column=args.return_col,
        task_type=args.task,
        train_fraction=args.train_fraction,
        validation_fraction=args.validation_fraction,
        test_fraction=args.test_fraction,
        walk_forward_splits=args.walk_forward_splits,
        minimum_rows=args.minimum_rows,
    )

    runner = ResearchWorkflowRunner(contract)
    if args.register_model or args.model_name or args.model_version:
        report = runner.run_and_register(
            dataset,
            model_name=args.model_name,
            model_version=args.model_version,
            model_type=args.model_type,
            algorithm=args.algorithm,
            target=args.prediction_target,
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
