from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from Tradov.TradovQ_Scripts.TradovQ92_ResearchWorkflow import (
    ResearchDatasetContract,
    ResearchWorkflowRunner,
    register_research_model,
)


class _FakeManager:
    def __init__(self):
        self.calls = []

    def register_model(self, **kwargs):
        self.calls.append(kwargs)
        return "model-123"


def _make_frame(rows: int = 120) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=rows, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": index,
            "feature_1": [float(i) for i in range(rows)],
            "label": [i % 2 for i in range(rows)],
            "realized_return": [0.01 if i % 2 == 0 else -0.01 for i in range(rows)],
        }
    )


def test_research_model_registration_uses_tradov_config_contract():
    frame = _make_frame()
    contract = ResearchDatasetContract(
        timestamp_column="timestamp",
        feature_columns=["feature_1"],
        label_column="label",
        return_column="realized_return",
        walk_forward_splits=3,
        minimum_rows=50,
    )
    runner = ResearchWorkflowRunner(contract)
    report = runner.run(frame)

    manager = _FakeManager()
    model_id = register_research_model(
        manager,
        model=runner.model,
        report=report,
        model_name="research_signal",
        model_version="20260618",
        contract=contract,
    )

    assert model_id == "model-123"
    assert manager.calls
    payload = manager.calls[0]
    assert payload["name"] == "research_signal"
    assert payload["version"] == "20260618"
    assert payload["config"].features == ["feature_1"]
    assert payload["metadata"]["contract"]["label_column"] == "label"
    assert payload["metadata"]["walk_forward_folds"]
