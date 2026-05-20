#!/usr/bin/env python3
"""Focused tests for G69 live-data status helper."""

from Spyder.SpyderG_GUI.SpyderG69_LiveDataStatusHelper import (
    is_live_equivalent_data_status,
)


def test_is_live_equivalent_data_status_accepts_trimmed_case_insensitive_labels() -> None:
    assert is_live_equivalent_data_status("  live - real  ") is True
    assert is_live_equivalent_data_status("REAL-TIME") is True


def test_is_live_equivalent_data_status_rejects_blank_and_delayed_labels() -> None:
    assert is_live_equivalent_data_status("") is False
    assert is_live_equivalent_data_status("delayed") is False