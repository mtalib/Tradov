from __future__ import annotations

from pathlib import Path

import pandas as pd

from Tradov.TradovQ_Scripts.TradovQ95_PairResearchLauncher import main as launcher_main


def _write_fixture(tmp_path: Path) -> Path:
    rows = 90
    idx = pd.date_range("2026-01-01", periods=rows, freq="D", tz="UTC")
    base = pd.Series(range(rows), dtype=float)
    series_b = base + 0.1
    series_a = 2.0 * series_b
    frame = pd.DataFrame(
        {
            "timestamp": idx,
            "symbol_a_price": series_a,
            "symbol_b_price": series_b,
        }
    )
    path = tmp_path / "pair_research_fixture.csv"
    frame.to_csv(path, index=False)
    return path


def test_pair_research_launcher_delegates_to_workflow(tmp_path, capsys):
    input_path = _write_fixture(tmp_path)
    output_path = tmp_path / "pair_report.json"

    rc = launcher_main(
        [
            "--input",
            str(input_path),
            "--timestamp-col",
            "timestamp",
            "--price-a-col",
            "symbol_a_price",
            "--price-b-col",
            "symbol_b_price",
            "--symbol-a",
            "AAA",
            "--symbol-b",
            "BBB",
            "--minimum-rows",
            "30",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert output_path.exists()
    assert '"pair_key": "AAA/BBB"' in captured.out
