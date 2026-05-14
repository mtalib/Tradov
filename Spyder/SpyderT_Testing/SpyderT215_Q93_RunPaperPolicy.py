#!/usr/bin/env python3
"""Focused regressions for the Q93 paper-launcher trading-mode gate."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


def test_q93_main_rejects_sandbox_trading_mode(monkeypatch) -> None:
    from Spyder.SpyderQ_Scripts import SpyderQ93_RunPaper as q93

    monkeypatch.setenv("TRADING_MODE", "sandbox")
    monkeypatch.setattr(sys, "argv", ["SpyderQ93_RunPaper", "--once", "--no-market-check"])

    build_harness = MagicMock(side_effect=AssertionError("harness should not be built"))
    market_loop = MagicMock()
    monkeypatch.setattr(q93, "create_paper_trading_harness_from_env", build_harness)
    monkeypatch.setattr(q93, "market_hours_loop", market_loop)

    with pytest.raises(SystemExit) as excinfo:
        q93.main()

    assert str(excinfo.value).startswith(
        "[ERROR] SpyderQ93_RunPaper requires TRADING_MODE=paper"
    )
    build_harness.assert_not_called()
    market_loop.assert_not_called()
