from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys
from types import ModuleType
import json

import pandas as pd

if "dotenv" not in sys.modules:
    dotenv_stub = ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub

from Tradov.TradovD_Strategies.TradovD30_RegimeGatedSelector import (
    RegimeGatedSelector,
    StrategyType,
)
from Tradov.TradovD_Strategies.TradovD01_BaseStrategy import RiskProfile
from Tradov.TradovD_Strategies.TradovD42_PairTrading import PairTradingStrategy
from Tradov.TradovD_Strategies.TradovD43_DistanceStrategy import DistanceTradingStrategy
from Tradov.TradovD_Strategies.TradovD31_StrategyOrchestrator import StrategyOrchestrator
from Tradov.TradovD_Strategies.TradovD51_PairScanner import PairScanner
from Tradov.TradovD_Strategies.TradovD58_PairScanDecisionAdapter import (
    build_formed_pair_scan_context,
    normalize_pair_scan_context,
)
from Tradov.TradovD_Strategies.TradovD59_PairCorpusPolicy import (
    build_pair_corpus_reload_log_message,
    load_pair_trading_corpus_policy,
)
from Tradov.TradovA_Core.TradovA03_Configuration import reset_config_manager
from Tradov.TradovD_Strategies.TradovD50_PairTypes import (
    CointegrationMethod,
    CointegrationResult,
    PairDefinition,
    PairStatus,
    PairScanResult,
)


class _StubEventManager:
    def __init__(self):
        self.handlers = {}

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def emit(self, *args, **kwargs):
        return None


class _FakeScanner:
    def __init__(self, scan_result: PairScanResult, pair_defs: dict[str, PairDefinition]):
        self.scan_result = scan_result
        self.pair_defs = pair_defs
        self.scan_calls = 0

    def scan(self, price_history=None, **kwargs):
        self.scan_calls += 1
        return self.scan_result

    def get_pair_definitions(self):
        return self.pair_defs


def _coint(pair_key: str, ranking_score: float, rank: int, p_value: float = 0.01) -> CointegrationResult:
    result = CointegrationResult(
        pair_key=pair_key,
        is_cointegrated=True,
        p_value=p_value,
        hedge_ratio=1.25,
        half_life=6.0,
        spread_mean=0.0,
        spread_std=1.2,
        method=CointegrationMethod.BOTH,
        test_statistic=-4.5,
        critical_value=-3.5,
        sample_size=180,
    )
    result.ranking_score = ranking_score
    result.ranking_components = {
        "p_value": 0.8,
        "half_life": 0.6,
        "spread_std": 0.5,
        "sample_size": 0.7,
    }
    result.metadata["rank"] = rank
    return result


def _scan_result(timestamp: datetime | None = None) -> PairScanResult:
    scan = PairScanResult(
        timestamp=timestamp or datetime.now(UTC),
        total_candidates=2,
        validated_pairs=[
            _coint("AAA/BBB", 1.8, 1),
            _coint("CCC/DDD", 1.2, 2),
        ],
        ranked_pairs=[
            _coint("AAA/BBB", 1.8, 1),
            _coint("CCC/DDD", 1.2, 2),
        ],
    )
    scan.build_decision_context(max_age_seconds=300.0, min_rank_score=0.2)
    return scan


def _allowed_scan_result(timestamp: datetime | None = None) -> PairScanResult:
    scan = PairScanResult(
        timestamp=timestamp or datetime.now(UTC),
        total_candidates=1,
        validated_pairs=[
            _coint("SPY/IWM", 1.8, 1),
        ],
        ranked_pairs=[
            _coint("SPY/IWM", 1.8, 1),
        ],
    )
    scan.build_decision_context(max_age_seconds=300.0, min_rank_score=0.2)
    return scan


def test_scan_result_builds_ready_decision_context():
    scan = _scan_result()

    assert scan.decision_state == "ready"
    assert scan.decision_reason == "scan_ready"
    assert scan.best_pair_key == "AAA/BBB"
    assert scan.best_ranking_score == 1.8
    assert scan.best_ranking_components["p_value"] == 0.8
    assert scan.scan_age_seconds >= 0.0


def test_pair_corpus_policy_loads_minimal_allowlist():
    policy = load_pair_trading_corpus_policy()

    assert policy.allows_pair_key("SPY/IWM") is True
    assert policy.allows_pair_key("KO/PEP") is True
    assert policy.allows_pair_key("XOM/CVX") is True
    assert policy.allows_pair_key("AAA/BBB") is False
    assert policy.is_negative_control_pair_key("AAPL/XLU") is True
    assert "Pair corpus policy reloaded" in build_pair_corpus_reload_log_message(policy)


def test_repo_config_manager_exposes_pair_corpus_policy():
    from Tradov.TradovA_Core.TradovA03_Configuration import ConfigManager

    cfg = ConfigManager(environment="development")
    policy = cfg.get("autonomous_readiness.pair_corpus_policy")

    assert isinstance(policy, dict)
    assert {f"{item['leg_a']}/{item['leg_b']}" for item in policy["active_pairs"]} == {
        "SPY/IWM",
        "KO/PEP",
        "XOM/CVX",
    }


def test_pair_corpus_policy_hot_reload_updates_allowlist(tmp_path, monkeypatch):
    source_path = Path("config/pair_trading_corpus_v1.json")
    temp_path = tmp_path / "pair_trading_corpus_v1.json"
    temp_path.write_text(source_path.read_text(), encoding="utf-8")

    monkeypatch.setenv("TRADOV_PAIR_CORPUS_POLICY_PATH", str(temp_path))
    reset_config_manager()

    from Tradov.TradovA_Core.TradovA03_Configuration import ConfigManager

    cfg = ConfigManager(environment="development")
    notifications: list[str] = []
    cfg.register_callback(
        "autonomous_readiness.pair_corpus_policy",
        lambda key, _old, _new: notifications.append(key),
    )
    initial_policy = cfg.get("autonomous_readiness.pair_corpus_policy")
    assert {f"{item['leg_a']}/{item['leg_b']}" for item in initial_policy["active_pairs"]} == {
        "SPY/IWM",
        "KO/PEP",
        "XOM/CVX",
    }

    modified = json.loads(temp_path.read_text(encoding="utf-8"))
    modified["active_pairs"] = modified["active_pairs"][:1]
    temp_path.write_text(json.dumps(modified, indent=2), encoding="utf-8")

    cfg._on_config_file_changed(temp_path)
    updated_policy = cfg.get("autonomous_readiness.pair_corpus_policy")
    assert notifications == [
        "autonomous_readiness.pair_corpus_policy",
        "*",
    ]
    assert {f"{item['leg_a']}/{item['leg_b']}" for item in updated_policy["active_pairs"]} == {
        "SPY/IWM",
    }

    reset_config_manager()


def test_pair_scanner_limits_default_universe_to_three_active_pairs():
    scanner = PairScanner(account_size=100000.0)

    pair_keys = set(scanner.get_pair_definitions().keys())
    assert {"SPY/IWM", "KO/PEP", "XOM/CVX"}.issubset(pair_keys)


def test_scan_result_marks_stale_scan_hold():
    stale_scan = _scan_result(timestamp=datetime.now(UTC) - timedelta(minutes=10))
    context = stale_scan.build_decision_context(max_age_seconds=60.0, min_rank_score=0.2)

    assert context.decision_state == "hold"
    assert context.decision_reason == "scan_stale"
    assert context.is_fresh is False


def test_selector_honours_stale_scan_gate():
    selector = RegimeGatedSelector()
    stale_scan = _scan_result(timestamp=datetime.now(UTC) - timedelta(minutes=10))
    consensus = SimpleNamespace(regime=SimpleNamespace(value="sideways_range"), confidence=0.8)

    selection = selector.select_strategy_from_consensus(
        consensus,
        scan_context=stale_scan,
        stale_scan_max_age_seconds=60.0,
    )

    assert selection.selected_strategy is StrategyType.Hold
    assert selection.reason == "scan_stale"


def test_selector_respects_hysteresis_when_switch_is_not_materially_better():
    selector = RegimeGatedSelector()
    scan = _scan_result()
    consensus = SimpleNamespace(regime=SimpleNamespace(value="high_vol"), confidence=0.2)

    selection = selector.select_strategy_from_consensus(
        consensus,
        scan_context=scan,
        current_strategy="DistanceApproach",
        switch_hysteresis=0.5,
    )

    assert selection.selected_strategy is StrategyType.DistanceApproach
    assert selection.reason == "hysteresis_hold"


def test_d31_pair_scan_routing_uses_scan_freshness_and_provenance():
    orch = StrategyOrchestrator(event_manager=_StubEventManager())
    orch._build_d30_consensus = lambda: SimpleNamespace(
        regime=SimpleNamespace(value="high_vol"),
        confidence=0.85,
    )

    fresh_scan = _allowed_scan_result()
    strategy_name, reason = orch.select_strategy_for_pair_scan(scan_result=fresh_scan)

    assert strategy_name == "PCAStatArb"
    assert reason == "high_volatility_regime"

    stale_scan = _scan_result(timestamp=datetime.now(UTC) - timedelta(minutes=10))
    strategy_name, reason = orch.select_strategy_for_pair_scan(scan_result=stale_scan)

    assert strategy_name is None
    assert reason == "pair_not_in_corpus_v1_allowlist"


def test_pair_trading_strategy_pushes_scan_context_to_sink_and_honours_hold_state(monkeypatch):
    monkeypatch.setattr(
        "Tradov.TradovD_Strategies.TradovD42_PairTrading._is_market_hours",
        lambda now=None: True,
    )
    coint = _coint("SPY/IWM", 1.8, 1)
    stale_scan = PairScanResult(
        timestamp=datetime.now(UTC) - timedelta(minutes=10),
        total_candidates=1,
        validated_pairs=[coint],
        ranked_pairs=[coint],
    )
    stale_scan.build_decision_context(max_age_seconds=60.0, min_rank_score=0.2)

    pair_def = PairDefinition(
        symbol_a="SPY",
        symbol_b="IWM",
        sector="ETF",
        pair_type="cross_asset",
        status=PairStatus.VALIDATED,
    )
    strategy = PairTradingStrategy(
        name="PairTradingStrategy_test",
        event_manager=_StubEventManager(),
        risk_profile=RiskProfile(account_size=100000.0),
        config={},
    )
    scanner = _FakeScanner(stale_scan, {pair_def.key: pair_def})
    strategy.scanner = scanner
    strategy._compute_z_score = lambda *args, **kwargs: 2.5  # type: ignore[method-assign]

    seen: list[str] = []
    strategy.set_pair_scan_sink(lambda scan: seen.append(getattr(scan, "decision_state", "")))

    signals = strategy.generate_signals(market_data=pd.DataFrame({"SPY": [100.0], "IWM": [95.0]}))

    assert scanner.scan_calls == 1
    assert seen == ["hold"]
    assert signals == []

    fresh_scan = PairScanResult(
        timestamp=datetime.now(UTC),
        total_candidates=1,
        validated_pairs=[coint],
        ranked_pairs=[coint],
    )
    fresh_scan.build_decision_context(max_age_seconds=60.0, min_rank_score=0.2)
    strategy.scanner = _FakeScanner(fresh_scan, {pair_def.key: pair_def})
    seen.clear()
    signals = strategy.generate_signals(market_data=pd.DataFrame({"SPY": [100.0], "IWM": [95.0]}))

    assert seen == ["ready"]
    assert len(signals) == 1

    blocked_coint = _coint("AAA/BBB", 1.8, 1)
    blocked_scan = PairScanResult(
        timestamp=datetime.now(UTC),
        total_candidates=1,
        validated_pairs=[blocked_coint],
        ranked_pairs=[blocked_coint],
    )
    blocked_scan.build_decision_context(max_age_seconds=60.0, min_rank_score=0.2)
    blocked_pair_def = PairDefinition(
        symbol_a="AAA",
        symbol_b="BBB",
        sector="tech",
        pair_type="stat_arb",
        status=PairStatus.VALIDATED,
    )
    strategy.scanner = _FakeScanner(blocked_scan, {blocked_pair_def.key: blocked_pair_def})
    seen.clear()
    signals = strategy.generate_signals(market_data=pd.DataFrame({"AAA": [100.0], "BBB": [95.0]}))

    assert seen == ["ready"]
    assert signals == []


def test_pair_trading_strategy_halts_scanning_outside_market_hours(monkeypatch):
    pair_def = PairDefinition(
        symbol_a="SPY",
        symbol_b="IWM",
        sector="ETF",
        pair_type="cross_asset",
        status=PairStatus.VALIDATED,
    )
    strategy = PairTradingStrategy(
        name="PairTradingStrategy_test",
        event_manager=_StubEventManager(),
        risk_profile=RiskProfile(account_size=100000.0),
        config={},
    )
    scanner = _FakeScanner(_scan_result(), {pair_def.key: pair_def})
    strategy.scanner = scanner
    strategy._compute_z_score = lambda *args, **kwargs: 2.5  # type: ignore[method-assign]
    monkeypatch.setattr(
        "Tradov.TradovD_Strategies.TradovD42_PairTrading._is_market_hours",
        lambda now=None: False,
    )

    seen: list[str] = []
    strategy.set_pair_scan_sink(lambda scan: seen.append(getattr(scan, "decision_reason", "")))

    signals = strategy.generate_signals(market_data=pd.DataFrame({"SPY": [100.0], "IWM": [95.0]}))

    assert scanner.scan_calls == 0
    assert seen == ["outside_trading_hours"]
    assert signals == []


def test_distance_strategy_pushes_scan_context_to_sink_and_honours_hold_state():
    pair = SimpleNamespace(
        key="SPY/IWM",
        symbol_a="SPY",
        symbol_b="IWM",
        ssd=1.5,
        z_score=lambda price_a, price_b: 2.5,
        spread=lambda price_a, price_b: price_a - price_b,
    )

    strategy = DistanceTradingStrategy(
        name="DistanceTradingStrategy_test",
        event_manager=_StubEventManager(),
        risk_profile=RiskProfile(account_size=100000.0),
        config={"formation": 2, "reformation_interval": 999},
    )
    strategy._maybe_form_pairs = lambda: None  # type: ignore[method-assign]
    strategy.formed_pairs = {pair.key: pair}

    seen: list[str] = []
    strategy.set_pair_scan_sink(lambda scan: seen.append(getattr(scan, "decision_state", "")))

    signals = strategy.generate_signals(market_data=pd.DataFrame({"SPY": [100.0], "IWM": [95.0]}))

    assert seen == ["ready"]
    assert len(signals) == 1

    strategy.formed_pairs = {}
    seen.clear()
    signals = strategy.generate_signals(market_data=pd.DataFrame({"SPY": [100.0], "IWM": [95.0]}))

    assert seen == ["hold"]
    assert signals == []


def test_distance_strategy_requests_pair_wide_frame_from_orchestrator():
    strategy = DistanceTradingStrategy(
        name="DistanceTradingStrategy_test",
        event_manager=_StubEventManager(),
        risk_profile=RiskProfile(account_size=100000.0),
        config={"formation": 2, "reformation_interval": 999},
    )

    assert StrategyOrchestrator._strategy_needs_pair_price_frame(strategy) is True


def test_pair_signals_route_to_pair_executor():
    orch = StrategyOrchestrator(event_manager=_StubEventManager())
    orch._live_engine = object()
    orch._pair_executor = type(
        "_StubPairExecutor",
        (),
        {
            "__init__": lambda self: setattr(self, "calls", []),
            "execute_pair": lambda self, signal: self.calls.append(signal) or SimpleNamespace(
                pair_key=signal.pair_key,
                state=SimpleNamespace(value="both_submitted"),
            ),
        },
    )()
    orch._pair_executor.calls = []

    signal = {
        "signal_id": "sig-1",
        "symbol": "AAA/BBB",
        "strategy_id": "PairTradingStrategy_test",
        "strategy_type": "pair_trading",
        "action": "buy",
        "side": "buy",
        "quantity": 10,
        "price": 1.0,
        "confidence": 0.9,
        "pair_key": "AAA/BBB",
        "pair_side": "long_short",
        "symbol_a": "AAA",
        "symbol_b": "BBB",
        "quantity_a": 10,
        "quantity_b": 12,
    }

    orch._dispatch_approved_signal(signal)

    assert len(orch._pair_executor.calls) == 1
    routed = orch._pair_executor.calls[0]
    assert routed.pair_key == "AAA/BBB"
    assert routed.symbol_a == "AAA"
    assert routed.symbol_b == "BBB"
    assert routed.quantity_a == 10
    assert routed.quantity_b == 12


def test_shared_scan_adapter_normalizes_both_scan_shapes():
    coint = _coint("AAA/BBB", 2.0, 1)
    raw_scan = {
        "scan_id": "scan-1",
        "timestamp": datetime.now(UTC),
        "ranked_pairs": [coint],
    }
    normalized = normalize_pair_scan_context(raw_scan, max_age_seconds=300.0, min_rank_score=0.1)
    assert normalized.decision_state == "ready"
    assert normalized.best_pair_key == "AAA/BBB"

    formed = build_formed_pair_scan_context([SimpleNamespace(key="AAA/BBB", ssd=1.0)])
    assert formed.decision_state == "ready"
    assert formed.best_pair_key == "AAA/BBB"
