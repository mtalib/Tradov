#!/usr/bin/env python3
"""Focused regressions for the R11 paper-run ZeroDTE profile hook."""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from Spyder.SpyderR_Runtime import SpyderR11_PaperStrategyRunner as _r11


class TestZeroDTEAdapterProfiles(unittest.TestCase):

    def test_mark_profile_overrides_zero_dte_adapter_parameters(self) -> None:
        adapter = _r11.ZeroDTEAdapter(profile_name=_r11.MARK_SPY_PAPER_ZERO_DTE_PROFILE)

        self.assertEqual(adapter.profile_name, _r11.MARK_SPY_PAPER_ZERO_DTE_PROFILE)
        self.assertAlmostEqual(adapter.target_short_delta, 0.12)
        self.assertAlmostEqual(adapter.short_delta_min, 0.07)
        self.assertAlmostEqual(adapter.short_delta_max, 0.20)
        self.assertAlmostEqual(adapter.wing_width_dollars, 1.0)
        self.assertAlmostEqual(adapter.min_total_credit, 0.20)
        self.assertEqual(adapter.entry_start_et, _r11.time(9, 32))
        self.assertEqual(adapter.entry_end_et, _r11.time(14, 30))
        self.assertEqual(adapter.hard_close_et, _r11.time(15, 15))
        self.assertEqual(adapter.max_open, 4)
        self.assertEqual(adapter.max_daily_entries, 8)
        self.assertAlmostEqual(adapter.profit_target_pct, 0.30)
        self.assertAlmostEqual(adapter.stop_loss_multiple, 1.25)
        self.assertIsNone(adapter.threat_buffer_pct)
        self.assertAlmostEqual(adapter.threat_buffer_points, 0.35)
        self.assertAlmostEqual(adapter.risk_pct_per_trade, 0.005)
        self.assertEqual(adapter.max_contracts_cap, 5)

    def test_mark_profile_exit_logic_uses_profile_specific_thresholds(self) -> None:
        adapter = _r11.ZeroDTEAdapter(profile_name=_r11.MARK_SPY_PAPER_ZERO_DTE_PROFILE)
        position = _r11.SimulatedPosition(
            position_id="pos-1",
            strategy=adapter.name,
            opened_at=_r11.datetime(2026, 5, 27, 10, 0),
            expiration=_r11.date(2026, 5, 27),
            legs=[],
            contracts=1,
            credit_received=1.0,
            max_loss=0.8,
            short_put_strike=600.0,
        )
        noon_ctx = _r11.MarketContext(
            spy_price=605.0,
            now=_r11.datetime(2026, 5, 27, 12, 0),
        )
        threat_ctx = _r11.MarketContext(
            spy_price=600.34,
            now=_r11.datetime(2026, 5, 27, 12, 0),
        )

        self.assertEqual(
            adapter.evaluate_exit(position, noon_ctx, cur_debit=0.70),
            "profit_target (30%)",
        )
        self.assertEqual(
            adapter.evaluate_exit(position, noon_ctx, cur_debit=2.25),
            "stop_loss (125% credit)",
        )
        self.assertEqual(
            adapter.evaluate_exit(position, threat_ctx, cur_debit=1.0),
            "short_put_threat @ 600",
        )

    def test_mark_profile_entry_proposal_carries_tighter_sizing_metadata(self) -> None:
        adapter = _r11.ZeroDTEAdapter(profile_name=_r11.MARK_SPY_PAPER_ZERO_DTE_PROFILE)
        today_iso = _r11.date(2026, 5, 27).isoformat()

        class FakeRunner:
            field_of = staticmethod(_r11.PaperStrategyRunner.field_of)
            quote_of = staticmethod(_r11.PaperStrategyRunner.quote_of)
            mid = staticmethod(_r11.PaperStrategyRunner.mid)
            find_put_by_delta = staticmethod(_r11.PaperStrategyRunner.find_put_by_delta)
            find_call_by_delta = staticmethod(_r11.PaperStrategyRunner.find_call_by_delta)
            find_strike = staticmethod(_r11.PaperStrategyRunner.find_strike)

            def get_expirations(self):
                return [today_iso]

            def get_chain_with_greeks(self, expiration):
                self.last_expiration = expiration
                return [
                    {"symbol": "SPYP599", "option_type": "put", "strike": 599.0, "bid": 0.24, "ask": 0.28, "delta": -0.12},
                    {"symbol": "SPYP598", "option_type": "put", "strike": 598.0, "bid": 0.04, "ask": 0.06, "delta": -0.05},
                    {"symbol": "SPYC601", "option_type": "call", "strike": 601.0, "bid": 0.24, "ask": 0.28, "delta": 0.12},
                    {"symbol": "SPYC602", "option_type": "call", "strike": 602.0, "bid": 0.04, "ask": 0.06, "delta": 0.05},
                ]

        runner = FakeRunner()
        ctx = _r11.MarketContext(
            spy_price=600.0,
            now=_r11.datetime(2026, 5, 27, 10, 0),
        )

        proposal = adapter.evaluate_entry(ctx, runner)

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.metadata["profile"], _r11.MARK_SPY_PAPER_ZERO_DTE_PROFILE)
        self.assertAlmostEqual(proposal.metadata["profit_target_pct"], 0.30)
        self.assertAlmostEqual(proposal.metadata["stop_loss_multiple"], 1.25)
        self.assertAlmostEqual(proposal.metadata["threat_buffer_points"], 0.35)
        self.assertAlmostEqual(proposal.metadata["risk_pct_per_trade"], 0.005)
        self.assertEqual(proposal.metadata["max_contracts_cap"], 5)

    def test_mark_profile_entry_searches_in_band_pairs_for_credit_floor(self) -> None:
        adapter = _r11.ZeroDTEAdapter(profile_name=_r11.MARK_SPY_PAPER_ZERO_DTE_PROFILE)
        today_iso = _r11.date(2026, 5, 27).isoformat()

        class FakeRunner:
            field_of = staticmethod(_r11.PaperStrategyRunner.field_of)
            quote_of = staticmethod(_r11.PaperStrategyRunner.quote_of)
            mid = staticmethod(_r11.PaperStrategyRunner.mid)
            find_put_by_delta = staticmethod(_r11.PaperStrategyRunner.find_put_by_delta)
            find_call_by_delta = staticmethod(_r11.PaperStrategyRunner.find_call_by_delta)
            find_strike = staticmethod(_r11.PaperStrategyRunner.find_strike)

            def get_expirations(self):
                return [today_iso]

            def get_chain_with_greeks(self, expiration):
                self.last_expiration = expiration
                return [
                    {"symbol": "SPYP741", "option_type": "put", "strike": 741.0, "bid": 0.21, "ask": 0.22, "delta": -0.0537},
                    {"symbol": "SPYP742", "option_type": "put", "strike": 742.0, "bid": 0.26, "ask": 0.27, "delta": -0.0740},
                    {"symbol": "SPYP743", "option_type": "put", "strike": 743.0, "bid": 0.32, "ask": 0.33, "delta": -0.0995},
                    {"symbol": "SPYP744", "option_type": "put", "strike": 744.0, "bid": 0.40, "ask": 0.41, "delta": -0.1309},
                    {"symbol": "SPYP745", "option_type": "put", "strike": 745.0, "bid": 0.51, "ask": 0.52, "delta": -0.1688},
                    {"symbol": "SPYC754", "option_type": "call", "strike": 754.0, "bid": 0.49, "ask": 0.50, "delta": 0.1973},
                    {"symbol": "SPYC755", "option_type": "call", "strike": 755.0, "bid": 0.31, "ask": 0.32, "delta": 0.1374},
                    {"symbol": "SPYC756", "option_type": "call", "strike": 756.0, "bid": 0.18, "ask": 0.19, "delta": 0.0918},
                    {"symbol": "SPYC757", "option_type": "call", "strike": 757.0, "bid": 0.11, "ask": 0.12, "delta": 0.0587},
                ]

        runner = FakeRunner()
        ctx = _r11.MarketContext(
            spy_price=750.59,
            now=_r11.datetime(2026, 5, 27, 12, 0),
        )

        proposal = adapter.evaluate_entry(ctx, runner)

        self.assertIsNotNone(proposal)
        assert proposal is not None
        self.assertAlmostEqual(proposal.credit_received, 0.21)
        self.assertEqual([leg.strike for leg in proposal.legs], [745.0, 744.0, 754.0, 755.0])
        self.assertEqual([leg.option_type for leg in proposal.legs], ["put", "put", "call", "call"])

    def test_size_position_honors_profile_specific_risk_budget_and_cap(self) -> None:
        runner = _r11.PaperStrategyRunner.__new__(_r11.PaperStrategyRunner)
        runner._harness = MagicMock()
        runner._harness.get_current_metrics.return_value = {"current_equity": 100000.0}
        runner._starting_equity = 100000.0
        runner._cumulative_sim_pnl = 0.0

        contracts = runner._size_position(
            max_loss_per_contract=1.0,
            risk_pct_per_trade=0.005,
            max_contracts_cap=5,
        )

        self.assertEqual(contracts, 5)

    def test_factory_threads_zero_dte_profile_from_env(self) -> None:
        harness = MagicMock()
        fake_client = object()
        fake_risk_manager = SimpleNamespace()
        fake_risk_module = SimpleNamespace(
            get_risk_manager=MagicMock(return_value=fake_risk_manager),
        )

        with patch.dict(
            os.environ,
            {
                "TRADIER_API_KEY": "token",
                "TRADIER_ACCOUNT_ID": "acct",
                "PAPER_STARTING_EQUITY": "123456",
                "SPYDER_ZERO_DTE_PROFILE": _r11.MARK_SPY_PAPER_ZERO_DTE_PROFILE,
            },
            clear=False,
        ), patch.dict(
            sys.modules,
            {"Spyder.SpyderE_Risk.SpyderE01_RiskManager": fake_risk_module},
            clear=False,
        ), patch.object(
            _r11,
            "TradierClient",
            return_value=fake_client,
        ) as mock_client, patch.object(
            _r11,
            "PaperStrategyRunner",
            return_value="runner",
        ) as mock_runner:
            runner = _r11.create_paper_strategy_runner_from_env(harness)

        self.assertEqual(runner, "runner")
        mock_client.assert_called_once()
        mock_runner.assert_called_once()
        self.assertEqual(
            mock_runner.call_args.kwargs["zero_dte_profile"],
            _r11.MARK_SPY_PAPER_ZERO_DTE_PROFILE,
        )
        self.assertEqual(mock_runner.call_args.kwargs["max_concurrent_positions"], 6)
        self.assertEqual(mock_runner.call_args.kwargs["starting_equity"], 123456.0)

    def test_factory_falls_back_to_classic_for_unknown_profile(self) -> None:
        harness = MagicMock()
        fake_risk_module = SimpleNamespace(
            get_risk_manager=MagicMock(return_value=SimpleNamespace()),
        )

        with patch.dict(
            os.environ,
            {
                "TRADIER_API_KEY": "token",
                "TRADIER_ACCOUNT_ID": "acct",
                "SPYDER_ZERO_DTE_PROFILE": "unknown-profile",
            },
            clear=False,
        ), patch.dict(
            sys.modules,
            {"Spyder.SpyderE_Risk.SpyderE01_RiskManager": fake_risk_module},
            clear=False,
        ), patch.object(_r11, "TradierClient", return_value=object()), patch.object(
            _r11,
            "PaperStrategyRunner",
            return_value="runner",
        ) as mock_runner:
            _r11.create_paper_strategy_runner_from_env(harness)

        self.assertEqual(
            mock_runner.call_args.kwargs["zero_dte_profile"],
            _r11.DEFAULT_ZERO_DTE_PROFILE,
        )
        self.assertEqual(mock_runner.call_args.kwargs["max_concurrent_positions"], 3)

    def test_mark_profile_prioritizes_zero_dte_adapter_order(self) -> None:
        runner = _r11.PaperStrategyRunner(
            data_client=MagicMock(),
            harness=MagicMock(),
            zero_dte_profile=_r11.MARK_SPY_PAPER_ZERO_DTE_PROFILE,
        )

        self.assertEqual(
            [adapter.name for adapter in runner._adapters],
            ["ZeroDTE_IronCondor", "BullPutCreditSpread"],
        )

    def test_classic_profile_preserves_bull_put_first_order(self) -> None:
        runner = _r11.PaperStrategyRunner(
            data_client=MagicMock(),
            harness=MagicMock(),
            zero_dte_profile=_r11.DEFAULT_ZERO_DTE_PROFILE,
        )

        self.assertEqual(
            [adapter.name for adapter in runner._adapters],
            ["BullPutCreditSpread", "ZeroDTE_IronCondor"],
        )

    def test_mark_profile_relaxes_gamma_gate_for_mixed_exposure(self) -> None:
        runner = _r11.PaperStrategyRunner(
            data_client=MagicMock(),
            harness=MagicMock(),
            zero_dte_profile=_r11.MARK_SPY_PAPER_ZERO_DTE_PROFILE,
        )
        runner._positions = [
            _r11.SimulatedPosition(
                position_id="zdte-open",
                strategy="ZeroDTE_IronCondor",
                opened_at=_r11.datetime(2026, 5, 27, 12, 0),
                expiration=_r11.date(2026, 5, 27),
                legs=[
                    _r11.SimulatedLeg(
                        option_symbol="SPY260527C00754000",
                        side="short",
                        strike=754.0,
                        option_type="call",
                        entry_price=0.49,
                        qty=5,
                        gamma=0.01986,
                    ),
                ],
                contracts=5,
                credit_received=0.21,
                max_loss=0.79,
            ),
        ]
        proposal = _r11.ProposedPosition(
            strategy="BullPutCreditSpread",
            expiration=_r11.date(2026, 6, 3),
            legs=[
                _r11.SimulatedLeg(
                    option_symbol="SPY260603P00738000",
                    side="short",
                    strike=738.0,
                    option_type="put",
                    entry_price=0.58,
                    qty=0,
                    gamma=0.00488,
                ),
                _r11.SimulatedLeg(
                    option_symbol="SPY260603P00733000",
                    side="long",
                    strike=733.0,
                    option_type="put",
                    entry_price=0.0,
                    qty=0,
                    gamma=0.0,
                ),
            ],
            credit_received=0.58,
            max_loss=4.42,
        )

        self.assertEqual(runner._portfolio_gamma_cap, 11.0)
        self.assertIsNone(runner._greek_gate(proposal, contracts=2))

    def test_classic_profile_still_rejects_same_gamma_mix(self) -> None:
        runner = _r11.PaperStrategyRunner(
            data_client=MagicMock(),
            harness=MagicMock(),
            zero_dte_profile=_r11.DEFAULT_ZERO_DTE_PROFILE,
        )
        runner._positions = [
            _r11.SimulatedPosition(
                position_id="zdte-open",
                strategy="ZeroDTE_IronCondor",
                opened_at=_r11.datetime(2026, 5, 27, 12, 0),
                expiration=_r11.date(2026, 5, 27),
                legs=[
                    _r11.SimulatedLeg(
                        option_symbol="SPY260527C00754000",
                        side="short",
                        strike=754.0,
                        option_type="call",
                        entry_price=0.49,
                        qty=5,
                        gamma=0.01986,
                    ),
                ],
                contracts=5,
                credit_received=0.21,
                max_loss=0.79,
            ),
        ]
        proposal = _r11.ProposedPosition(
            strategy="BullPutCreditSpread",
            expiration=_r11.date(2026, 6, 3),
            legs=[
                _r11.SimulatedLeg(
                    option_symbol="SPY260603P00738000",
                    side="short",
                    strike=738.0,
                    option_type="put",
                    entry_price=0.58,
                    qty=0,
                    gamma=0.00488,
                ),
                _r11.SimulatedLeg(
                    option_symbol="SPY260603P00733000",
                    side="long",
                    strike=733.0,
                    option_type="put",
                    entry_price=0.0,
                    qty=0,
                    gamma=0.0,
                ),
            ],
            credit_received=0.58,
            max_loss=4.42,
        )

        self.assertEqual(runner._portfolio_gamma_cap, 10.0)
        self.assertEqual(
            runner._greek_gate(proposal, contracts=2),
            "portfolio_gamma_cap (|-10.91| > 10.00)",
        )

    def test_tick_max_concurrent_gate_ignores_closed_positions(self) -> None:
        runner = _r11.PaperStrategyRunner.__new__(_r11.PaperStrategyRunner)
        runner._harness = MagicMock()
        runner._positions = [
            _r11.SimulatedPosition(
                position_id="closed-1",
                strategy="TestAdapter",
                opened_at=_r11.datetime(2026, 5, 27, 10, 0),
                expiration=_r11.date(2026, 5, 27),
                legs=[],
                contracts=1,
                credit_received=1.0,
                max_loss=1.0,
                closed_at=_r11.datetime(2026, 5, 27, 10, 5),
            ),
        ]
        runner._max_concurrent = 1
        runner._cumulative_sim_pnl = 0.0
        runner._last_entry_attempt = {}
        runner._entry_cooldown = _r11.timedelta(minutes=5)
        runner._no_entry_summary_interval = _r11.timedelta(seconds=30)
        runner._last_no_entry_summary_ts = None
        runner._daily_entry_counts = {}
        runner._daily_entry_date = None
        runner._get_spy_and_vix = MagicMock(return_value=({"last": 600.0}, 18.0))
        runner._evaluate_exits = MagicMock(return_value=0)
        runner._try_enter = MagicMock(return_value=(False, "no_candidate"))

        class TestAdapter:
            name = "TestAdapter"
            max_open = 4
            max_daily_entries = 8

            @staticmethod
            def within_entry_window(_now):
                return True

        runner._adapters = [TestAdapter()]

        result = runner.tick(now_et=_r11.datetime(2026, 5, 27, 10, 0))

        self.assertEqual(result["open_positions"], 0)
        self.assertEqual(result["top_no_entry_reason"], "TestAdapter:no_candidate")
        runner._try_enter.assert_called_once()

    def test_tick_blocks_after_mark_daily_entry_cap(self) -> None:
        runner = _r11.PaperStrategyRunner.__new__(_r11.PaperStrategyRunner)
        runner._harness = MagicMock()
        runner._positions = []
        runner._max_concurrent = 6
        runner._cumulative_sim_pnl = 0.0
        runner._last_entry_attempt = {}
        runner._entry_cooldown = _r11.timedelta(minutes=5)
        runner._no_entry_summary_interval = _r11.timedelta(seconds=30)
        runner._last_no_entry_summary_ts = None
        runner._daily_entry_counts = {"TestAdapter": 8}
        runner._daily_entry_date = _r11.date(2026, 5, 27)
        runner._get_spy_and_vix = MagicMock(return_value=({"last": 600.0}, 18.0))
        runner._evaluate_exits = MagicMock(return_value=0)
        runner._try_enter = MagicMock(return_value=(True, ""))

        class TestAdapter:
            name = "TestAdapter"
            max_open = 4
            max_daily_entries = 8

            @staticmethod
            def within_entry_window(_now):
                return True

        runner._adapters = [TestAdapter()]

        result = runner.tick(now_et=_r11.datetime(2026, 5, 27, 12, 0))

        self.assertEqual(result["opens_this_tick"], 0)
        self.assertEqual(result["top_no_entry_reason"], "TestAdapter:daily_entry_cap")
        runner._try_enter.assert_not_called()

    def test_tick_returns_per_adapter_no_entry_reasons(self) -> None:
        runner = _r11.PaperStrategyRunner.__new__(_r11.PaperStrategyRunner)
        runner._harness = MagicMock()
        runner._positions = []
        runner._max_concurrent = 6
        runner._cumulative_sim_pnl = 0.0
        runner._last_entry_attempt = {}
        runner._entry_cooldown = _r11.timedelta(minutes=5)
        runner._no_entry_summary_interval = _r11.timedelta(seconds=30)
        runner._last_no_entry_summary_ts = None
        runner._daily_entry_counts = {}
        runner._daily_entry_date = None
        runner._get_spy_and_vix = MagicMock(return_value=({"last": 600.0}, 18.0))
        runner._evaluate_exits = MagicMock(return_value=0)
        runner._try_enter = MagicMock(return_value=(False, "no_candidate"))

        class BullPutAdapter:
            name = "BullPutCreditSpread"
            max_open = 2
            max_daily_entries = 3

            @staticmethod
            def within_entry_window(_now):
                return False

        class ZeroDTEAdapter:
            name = "ZeroDTE_IronCondor"
            max_open = 4
            max_daily_entries = 8

            @staticmethod
            def within_entry_window(_now):
                return True

        runner._adapters = [BullPutAdapter(), ZeroDTEAdapter()]

        result = runner.tick(now_et=_r11.datetime(2026, 5, 27, 12, 0))

        self.assertEqual(
            result["no_entry_reasons_by_adapter"],
            {
                "BullPutCreditSpread": "outside_entry_window",
                "ZeroDTE_IronCondor": "no_candidate",
            },
        )
        self.assertEqual(
            result["no_entry_reason_counts"],
            {
                "BullPutCreditSpread:outside_entry_window": 1,
                "ZeroDTE_IronCondor:no_candidate": 1,
            },
        )
        runner._try_enter.assert_called_once()


if __name__ == "__main__":
    unittest.main()
