from __future__ import annotations

import pandas as pd

from Tradov.TradovQ_Scripts.TradovQ94_PairResearchWorkflow import (
    PairResearchDatasetContract,
    PairResearchWorkflowRunner,
    register_pair_research_model,
)


class _FakeManager:
    def __init__(self):
        self.calls = []

    def register_model(self, **kwargs):
        self.calls.append(kwargs)
        return "pair-model-123"


def _make_pair_frame(rows: int = 180) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=rows, freq="D", tz="UTC")
    base = pd.Series(range(rows), dtype=float)
    noise = pd.Series([0.1 if i % 2 == 0 else -0.1 for i in range(rows)], dtype=float)
    series_b = base + noise
    series_a = 2.0 * series_b + noise * 0.2
    return pd.DataFrame(
        {
            "timestamp": idx,
            "symbol_a_price": series_a,
            "symbol_b_price": series_b,
        }
    )


def test_pair_research_workflow_reports_tradeable_metrics():
    frame = _make_pair_frame()
    contract = PairResearchDatasetContract(
        timestamp_column="timestamp",
        price_column_a="symbol_a_price",
        price_column_b="symbol_b_price",
        symbol_a="AAA",
        symbol_b="BBB",
        train_fraction=0.6,
        validation_fraction=0.2,
        test_fraction=0.2,
        walk_forward_splits=3,
        minimum_rows=60,
        entry_z=1.0,
        exit_z=0.25,
        stop_z=2.5,
        lookback=30,
    )

    report = PairResearchWorkflowRunner(contract).run(frame)

    assert report.pair_key == "AAA/BBB"
    assert report.row_count == len(frame)
    assert len(report.walk_forward_folds) == 3
    assert report.holdout_metrics["hedge_ratio"] > 0.0
    assert "total_return" in report.backtest_metrics
    assert report.pair_status_before == "candidate"
    assert report.pair_status_after in {"candidate", "validated", "degraded", "retired"}
    assert report.pair_quality_score >= 0.0
    assert report.artifact_path is not None


def test_pair_research_registration_uses_tradov_config_contract():
    frame = _make_pair_frame()
    contract = PairResearchDatasetContract(
        timestamp_column="timestamp",
        price_column_a="symbol_a_price",
        price_column_b="symbol_b_price",
        symbol_a="AAA",
        symbol_b="BBB",
        train_fraction=0.6,
        validation_fraction=0.2,
        test_fraction=0.2,
        walk_forward_splits=3,
        minimum_rows=60,
        entry_z=1.0,
        exit_z=0.25,
        stop_z=2.5,
        lookback=30,
    )
    runner = PairResearchWorkflowRunner(contract)
    report = runner.run(frame)

    manager = _FakeManager()
    model_id = register_pair_research_model(
        manager,
        model={"artifact": "pair"},
        report=report,
        model_name="pair_research_AAA_BBB",
        model_version="20260618",
        contract=contract,
    )

    assert model_id == "pair-model-123"
    assert manager.calls
    payload = manager.calls[0]
    assert payload["name"] == "pair_research_AAA_BBB"
    assert payload["config"].hyperparameters["workflow"] == "q94_pair_research"
    assert payload["metadata"]["pair_key"] == "AAA/BBB"
    assert "pair_status_before" in payload["metadata"]
    assert "pair_quality_score" in payload["metadata"]
