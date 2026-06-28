#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovQ_Scripts
Module: TradovQ93_ResearchLauncher.py
Purpose: Thin operator launcher for the Q92 research workflow
Author: Codex
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    Provides a stable operator-facing entry point for the Q92 research workflow.
    This launcher intentionally stays thin: it delegates parsing and execution to
    the research workflow module so the CLI surface remains consistent across
    direct use and launcher-driven use.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_DEFAULT_TRADOV_HOME = str(Path(__file__).resolve().parents[2])
TRADOV_HOME = os.environ.get("TRADOV_HOME", _DEFAULT_TRADOV_HOME)
if TRADOV_HOME not in sys.path:
    sys.path.insert(0, TRADOV_HOME)

from Tradov.TradovQ_Scripts.TradovQ92_ResearchWorkflow import main as research_main


def main(argv: list[str] | None = None) -> int:
    return research_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
