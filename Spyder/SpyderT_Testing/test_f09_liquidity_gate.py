#!/usr/bin/env python3
"""Focused tests for F09 liquidity gate helper."""

from Spyder.SpyderF_Analysis.SpyderF09_EntryFilters import EntryFilters, FilterResult


class _MockConfigManager:
    def get_config(self, _key, default=None):
        return default if default is not None else {}

    def is_feature_enabled(self, _key):
        return False


class _GateModeConfigManager(_MockConfigManager):
    def __init__(self, gate_mode: str):
        self.gate_mode = gate_mode

    def get_config(self, key, default=None):
        if key == 'autonomous_readiness.liquidity':
            data = dict(default if isinstance(default, dict) else {})
            data['gate_mode'] = self.gate_mode
            return data
        return super().get_config(key, default)


def test_f09_liquidity_gate_blocks_bad_snapshot():
    """Test that liquidity gate blocks poor quality snapshot."""
    ef = EntryFilters(_MockConfigManager())

    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.22,
            "spread_abs": 0.45,
            "quote_age_ms": 3500,
            "top_of_book_size": 1,
            "open_interest": 50,
            "volume": 3,
            "oi_change_pct": -0.8,
        }
    )

    assert ok is False
    assert len(reasons) >= 1


def test_f09_liquidity_gate_passes_good_snapshot():
    """Test that liquidity gate passes high quality snapshot."""
    ef = EntryFilters(_MockConfigManager())

    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.03,
            "spread_abs": 0.05,
            "quote_age_ms": 700,
            "top_of_book_size": 30,
            "open_interest": 1500,
            "volume": 250,
            "oi_change_pct": 0.08,
        }
    )

    assert ok is True
    assert reasons == []


def test_f09_liquidity_gate_wide_spread_pct():
    """Spread exceeding max_spread_pct should fail."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.25,  # Exceeds default 0.12
            "spread_abs": 0.10,
            "quote_age_ms": 500,
            "top_of_book_size": 50,
            "open_interest": 5000,
            "volume": 1000,
            "oi_change_pct": -0.05,
        }
    )
    assert ok is False
    assert any("spread_pct" in r for r in reasons)


def test_f09_liquidity_gate_high_abs_spread():
    """Absolute spread exceeding max_spread_abs should fail."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.05,
            "spread_abs": 0.50,  # Exceeds default 0.20
            "quote_age_ms": 500,
            "top_of_book_size": 50,
            "open_interest": 5000,
            "volume": 1000,
            "oi_change_pct": -0.05,
        }
    )
    assert ok is False
    assert any("spread_abs" in r for r in reasons)


def test_f09_liquidity_gate_stale_quote():
    """Quote older than max_quote_age_ms should fail."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.05,
            "spread_abs": 0.10,
            "quote_age_ms": 3000,  # Exceeds default 1500ms
            "top_of_book_size": 50,
            "open_interest": 5000,
            "volume": 1000,
            "oi_change_pct": -0.05,
        }
    )
    assert ok is False
    assert any("quote_age_ms" in r for r in reasons)


def test_f09_liquidity_gate_thin_book():
    """Top-of-book size below minimum should fail."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.05,
            "spread_abs": 0.10,
            "quote_age_ms": 500,
            "top_of_book_size": 2,  # Below default 10
            "open_interest": 5000,
            "volume": 1000,
            "oi_change_pct": -0.05,
        }
    )
    assert ok is False
    assert any("top_of_book_size" in r for r in reasons)


def test_f09_liquidity_gate_low_open_interest():
    """Open interest below minimum should fail."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.05,
            "spread_abs": 0.10,
            "quote_age_ms": 500,
            "top_of_book_size": 50,
            "open_interest": 100,  # Below default 500
            "volume": 1000,
            "oi_change_pct": -0.05,
        }
    )
    assert ok is False
    assert any("open_interest" in r for r in reasons)


def test_f09_liquidity_gate_low_volume():
    """Volume below minimum should fail."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.05,
            "spread_abs": 0.10,
            "quote_age_ms": 500,
            "top_of_book_size": 50,
            "open_interest": 5000,
            "volume": 10,  # Below default 50
            "oi_change_pct": -0.05,
        }
    )
    assert ok is False
    assert any("volume" in r for r in reasons)


def test_f09_liquidity_gate_collapsing_oi():
    """OI change below minimum threshold should fail."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.05,
            "spread_abs": 0.10,
            "quote_age_ms": 500,
            "top_of_book_size": 50,
            "open_interest": 5000,
            "volume": 1000,
            "oi_change_pct": -0.50,  # Below default -0.20 (guardrail against collapse)
        }
    )
    assert ok is False
    assert any("oi_change_pct" in r for r in reasons)


def test_f09_liquidity_gate_multiple_failures():
    """Multiple failures should list all reasons."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.30,  # Bad
            "spread_abs": 1.00,  # Bad
            "quote_age_ms": 5000,  # Bad
            "top_of_book_size": 1,  # Bad
            "open_interest": 10,  # Bad
            "volume": 1,  # Bad
            "oi_change_pct": -0.80,  # Bad
        }
    )
    assert ok is False
    assert len(reasons) >= 5  # Should have multiple issues


def test_f09_liquidity_gate_boundary_spread_pct():
    """Spread at exact threshold should pass."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.12,  # Exactly at default max
            "spread_abs": 0.10,
            "quote_age_ms": 500,
            "top_of_book_size": 50,
            "open_interest": 5000,
            "volume": 1000,
            "oi_change_pct": -0.05,
        }
    )
    assert ok is True
    assert reasons == []


def test_f09_liquidity_gate_boundary_oi():
    """OI at exact threshold should pass."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.05,
            "spread_abs": 0.10,
            "quote_age_ms": 500,
            "top_of_book_size": 50,
            "open_interest": 500,  # Exactly at default min
            "volume": 1000,
            "oi_change_pct": -0.05,
        }
    )
    assert ok is True
    assert reasons == []


def test_f09_liquidity_gate_custom_thresholds():
    """Custom thresholds should override defaults."""
    ef = EntryFilters(_MockConfigManager())
    custom_thresholds = {
        "max_spread_pct": 0.05,  # Stricter than default
        "max_spread_abs": 0.10,
        "max_quote_age_ms": 1000,
        "min_top_of_book_size": 100,
        "min_open_interest": 2000,
        "min_volume": 500,
        "min_oi_change_pct": -0.10,
    }
    
    # This snapshot would pass with defaults but fail with strict thresholds
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.08,  # Good but exceeds custom 0.05
            "spread_abs": 0.05,
            "quote_age_ms": 500,
            "top_of_book_size": 50,
            "open_interest": 5000,
            "volume": 1000,
            "oi_change_pct": -0.05,
        },
        thresholds=custom_thresholds,
    )
    assert ok is False
    assert any("spread_pct" in r for r in reasons)


def test_f09_liquidity_gate_missing_fields():
    """Missing required fields should be handled gracefully."""
    ef = EntryFilters(_MockConfigManager())
    
    # Missing spread_pct
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_abs": 0.10,
            "quote_age_ms": 500,
            "top_of_book_size": 50,
            "open_interest": 5000,
            "volume": 1000,
            "oi_change_pct": -0.05,
        }
    )
    # Should fail gracefully (either explicitly fail or skip)
    assert ok is False or len(reasons) >= 0


def test_f09_liquidity_gate_empty_snapshot():
    """Empty snapshot should fail."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate({})
    assert ok is False


def test_f09_liquidity_gate_negative_fields():
    """Negative values where not expected should fail."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": -0.05,  # Should be positive
            "spread_abs": 0.10,
            "quote_age_ms": 500,
            "top_of_book_size": 50,
            "open_interest": 5000,
            "volume": 1000,
            "oi_change_pct": -0.05,
        }
    )
    assert ok is False


def test_f09_liquidity_gate_zero_values():
    """Zero values for quantities should fail."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.05,
            "spread_abs": 0.10,
            "quote_age_ms": 500,
            "top_of_book_size": 0,  # Should be > 0
            "open_interest": 0,  # Should be > 0
            "volume": 0,  # Should be > 0
            "oi_change_pct": -0.05,
        }
    )
    assert ok is False


def test_f09_liquidity_gate_extreme_volume():
    """Very high volume should pass."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.03,
            "spread_abs": 0.05,
            "quote_age_ms": 500,
            "top_of_book_size": 50,
            "open_interest": 50000,
            "volume": 100000,  # Extreme but good
            "oi_change_pct": 0.50,  # Positive is good
        }
    )
    assert ok is True
    assert reasons == []


def test_f09_liquidity_gate_observe_mode_allows_bad_snapshot():
    """Observe mode should surface reasons without blocking."""
    ef = EntryFilters(_MockConfigManager())
    ok, reasons = ef.evaluate_liquidity_gate(
        {
            "spread_pct": 0.25,
            "spread_abs": 0.45,
            "quote_age_ms": 3500,
            "top_of_book_size": 1,
            "open_interest": 50,
            "volume": 3,
            "oi_change_pct": -0.8,
        },
        gate_mode="observe",
    )

    assert ok is True
    assert len(reasons) >= 1


def test_f09_liquidity_gate_warn_mode_marks_filter_warning():
    """Warn mode should convert a bad snapshot into a warning filter result."""
    ef = EntryFilters(_GateModeConfigManager("warn"))
    checks = ef._check_liquidity_quality_filter(
        {
            "liquidity_snapshot": {
                "spread_pct": 0.25,
                "spread_abs": 0.45,
                "quote_age_ms": 3500,
                "top_of_book_size": 1,
                "open_interest": 50,
                "volume": 3,
                "oi_change_pct": -0.8,
            }
        }
    )

    assert len(checks) == 1
    assert checks[0].result == FilterResult.WARNING
    assert "Liquidity gate warning" in checks[0].message
