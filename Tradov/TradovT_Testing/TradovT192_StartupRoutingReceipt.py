from __future__ import annotations


def test_startup_routing_receipt_contains_effective_context(monkeypatch):
    from Tradov.TradovR_Runtime.TradovR12_SessionSupervisor import SessionSupervisor
    from Tradov.TradovU_Utilities.TradovU49_SymbolCatalog import get_runtime_pair_quote_basket

    monkeypatch.setenv("TRADIER_ENVIRONMENT", "live")
    monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", "live")
    monkeypatch.delenv("FEED_SYMBOLS", raising=False)
    supervisor = SessionSupervisor(mode="paper", dry_run=True)
    supervisor.session_id = "paper-test-session"

    receipt = supervisor._startup_routing_receipt()

    assert receipt["event"] == "startup_effective_routing"
    assert receipt["mode"] == "paper"
    assert receipt["symbols"] == get_runtime_pair_quote_basket()
    assert receipt["pair_feed_coverage_ok"] is True
    assert set(receipt["pair_feed_symbols"]).issubset(set(get_runtime_pair_quote_basket()))
    assert len(receipt["pair_feed_symbols"]) >= 2
    assert receipt["runtime_context"]["mode"] == "paper"
    assert receipt["live_only_policy"]["tradier_environment"] == "live"
    assert receipt["synthetic_market_defaults_allowed"] is False
