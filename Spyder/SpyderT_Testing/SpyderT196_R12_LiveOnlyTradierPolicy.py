#!/usr/bin/env python3
"""T196 - R12 must fail fast on any sandbox Tradier request."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor


@pytest.fixture(autouse=True)
def _baseline_live_env(monkeypatch):
    """Set baseline env to policy-compliant values for each test."""
    monkeypatch.setenv("TRADIER_ENVIRONMENT", "live")
    monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", "live")
    monkeypatch.delenv("SPYDER_ALLOW_SANDBOX_MARKET_DATA", raising=False)


class TestLiveOnlyTradierPolicy:
    """Regression guard for startup policy gate."""

    def test_validate_policy_accepts_live_only_configuration(self):
        sv = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)

        ok, detail = sv._validate_live_only_tradier_policy()

        assert ok is True
        assert detail == ""

    @pytest.mark.parametrize(
        "env_key,env_value,expected_fragment",
        [
            ("TRADIER_ENVIRONMENT", "sandbox", "TRADIER_ENVIRONMENT=sandbox"),
            (
                "TRADIER_MARKET_DATA_ENVIRONMENT",
                "sandbox",
                "TRADIER_MARKET_DATA_ENVIRONMENT=sandbox",
            ),
            ("TRADIER_ENVIRONMENT", "paper", "TRADIER_ENVIRONMENT=paper"),
            ("TRADIER_ENVIRONMENT", "typo", "TRADIER_ENVIRONMENT=typo"),
            (
                "TRADIER_MARKET_DATA_ENVIRONMENT",
                "paper",
                "TRADIER_MARKET_DATA_ENVIRONMENT=paper",
            ),
            (
                "TRADIER_MARKET_DATA_ENVIRONMENT",
                "typo",
                "TRADIER_MARKET_DATA_ENVIRONMENT=typo",
            ),
            ("TRADIER_ENVIRONMENT", "", "TRADIER_ENVIRONMENT="),
        ],
    )
    def test_validate_policy_rejects_sandbox_or_paper_tradier_routes(
        self,
        monkeypatch,
        env_key,
        env_value,
        expected_fragment,
    ):
        monkeypatch.setenv(env_key, env_value)
        sv = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)

        ok, detail = sv._validate_live_only_tradier_policy()

        assert ok is False
        assert expected_fragment in detail

    def test_validate_policy_rejects_sandbox_escape_hatch(self, monkeypatch):
        monkeypatch.setenv("SPYDER_ALLOW_SANDBOX_MARKET_DATA", "true")
        sv = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)

        ok, detail = sv._validate_live_only_tradier_policy()

        assert ok is False
        assert "SPYDER_ALLOW_SANDBOX_MARKET_DATA=true" in detail

    def test_start_aborts_before_component_start_when_policy_violated(self, monkeypatch):
        monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", "sandbox")

        sv = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        sv._start_event_manager = MagicMock(return_value=True)

        ok = sv.start()

        assert ok is False
        sv._start_event_manager.assert_not_called()
