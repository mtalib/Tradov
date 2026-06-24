from __future__ import annotations

from pathlib import Path

import pandas as pd

from Tradov.TradovQ_Scripts.TradovQ93_ResearchLauncher import main as launcher_main


def _write_fixture(tmp_path: Path) -> Path:
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=60, freq="D", tz="UTC"),
            "feature_1": [float(i) for i in range(60)],
            "label": [i % 2 for i in range(60)],
            "realized_return": [0.01 if i % 2 == 0 else -0.01 for i in range(60)],
        }
    )
    path = tmp_path / "research_fixture.csv"
    frame.to_csv(path, index=False)
    return path


def test_research_launcher_delegates_to_workflow(tmp_path, capsys):
    input_path = _write_fixture(tmp_path)
    output_path = tmp_path / "report.json"

    rc = launcher_main(
        [
            "--input",
            str(input_path),
            "--timestamp-col",
            "timestamp",
            "--label-col",
            "label",
            "--features",
            "feature_1",
            "--return-col",
            "realized_return",
            "--minimum-rows",
            "30",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert output_path.exists()
    assert '"run_id":' in captured.out
