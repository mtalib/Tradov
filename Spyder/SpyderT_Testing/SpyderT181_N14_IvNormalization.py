#!/usr/bin/env python3
"""
Regression tests for N14 IV normalization behavior.
"""

from dataclasses import dataclass

from Spyder.SpyderN_OptionsAnalytics.SpyderN14_OptionsDataVetter import (
    OptionsDataVetter,
    VetReason,
)


@dataclass
class _DummyGreek:
    symbol: str = "SPY260630C00600000"
    strike: float = 600.0
    option_type: str = "call"
    bid: float = 0.0
    ask: float = 0.0
    open_interest: int = 10
    volume: int = 10
    delta: float = 0.25
    gamma: float = 0.05
    theta: float = -0.1
    vega: float = 0.2
    iv: float = 0.3


class TestN14IvNormalization:
    def test_percent_style_iv_is_normalized_and_accepted(self):
        vetter = OptionsDataVetter(bsm_check=False)
        contract = _DummyGreek(iv=45.0)

        accepted = vetter.vet([contract])

        assert len(accepted) == 1
        assert abs(contract.iv - 0.45) < 1e-9

    def test_extreme_iv_still_rejected_after_normalization_attempt(self):
        vetter = OptionsDataVetter(bsm_check=False)
        contract = _DummyGreek(iv=800.0)

        detailed = vetter.vet_detailed([contract])

        assert len(detailed.accepted) == 0
        assert len(detailed.rejected) == 1
        assert detailed.rejected[0][1] == VetReason.IV_OUT_OF_BOUNDS
