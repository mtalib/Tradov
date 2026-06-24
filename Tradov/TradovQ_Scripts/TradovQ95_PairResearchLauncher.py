#!/usr/bin/env python3
"""Thin operator launcher for the Q94 pair research workflow."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_DEFAULT_TRADOV_HOME = str(Path(__file__).resolve().parents[2])
TRADOV_HOME = os.environ.get("TRADOV_HOME", _DEFAULT_TRADOV_HOME)
if TRADOV_HOME not in sys.path:
    sys.path.insert(0, TRADOV_HOME)

from Tradov.TradovQ_Scripts.TradovQ94_PairResearchWorkflow import main as pair_research_main


def main(argv: list[str] | None = None) -> int:
    return pair_research_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
