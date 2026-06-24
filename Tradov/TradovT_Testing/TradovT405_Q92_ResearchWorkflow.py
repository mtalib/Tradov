from __future__ import annotations

import pandas as pd

from Tradov.TradovQ_Scripts.TradovQ92_ResearchWorkflow import (
    ResearchDatasetContract,
    ResearchWorkflowRunner,
)


def _make_frame(rows: int = 180) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=rows, freq="D", tz="UTC")
    feature_1 = pd.Series(range(rows), dtype=float)
    feature_2 = feature_1.rolling(5, min_periods=1).mean()
    future_return = (feature_1.diff().fillna(0.0) / 100.0).shift(-1).fillna(0.0)
    label = (future_return > 0).astype(int)
    return pd.DataFrame(
        {
            "timestamp": index,
            "feature_1": feature_1,
            "feature_2": feature_2,
            "label": label,
            "realized_return": future_return,
        }
    )


def test_research_workflow_runs_and_emits_holdout_metrics():
    frame = _make_frame()
    contract = ResearchDatasetContract(
        timestamp_column="timestamp",
        feature_columns=["feature_1", "feature_2"],
        label_column="label",
        return_column="realized_return",
        task_type="classification",
        train_fraction=0.6,
        validation_fraction=0.2,
        test_fraction=0.2,
        walk_forward_splits=3,
        minimum_rows=50,
    )

    report = ResearchWorkflowRunner(contract).run(frame)

    assert report.row_count == len(frame)
    assert report.feature_count == 2
    assert report.holdout_metrics["accuracy"] >= 0.0
    assert "total_return" in report.backtest_metrics
    assert len(report.walk_forward_folds) == 3


def test_dataset_contract_requires_valid_fractions():
    contract = ResearchDatasetContract(
        timestamp_column="timestamp",
        feature_columns=["feature_1"],
        label_column="label",
        train_fraction=0.5,
        validation_fraction=0.3,
        test_fraction=0.3,
    )

    try:
        contract.validate()
    except ValueError as exc:
        assert "sum to 1.0" in str(exc)
    else:
        raise AssertionError("expected contract validation to fail")
