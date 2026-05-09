# Spyder Codebase Audit v18 — Anomalies, Deficiencies & Enhancement Opportunities

**Date:** 2026-04-16
**Scope:** Full production codebase, audited against Overview v4 (2026-04-14)
**Audit target audience:** Spyder coding agent (GitHub Copilot / Claude)
**Prior baseline:** [2026-04-14_Codebase_Review_v17.md](2026-04-14_Codebase_Review_v17.md), [Overview v4](../01-Overview-Specs/2026-04-14-Spyder-Overview-v4.md)

---

## TL;DR — Top Actionable Findings

| # | Severity | Area | Issue | Fix effort |
|---|:---:|------|-------|:---:|
| 1 | 🔴 CRITICAL | P04 CapitalAllocator | `_update_market_regime` + `_check_tactical_rebalance` use `np.random.choice`/`np.random.random()` in production paths | M |
| 2 | 🔴 CRITICAL | R04 LiveEngine | `_wait_for_execution` busy-waits with `time.sleep(0.1)` blocking the executing thread for up to `ORDER_TIMEOUT_SECONDS` | M |
| 3 | 🟠 HIGH | Regime wiring | E21, M06, P04 all embed their own regime stubs despite L09 being the declared canonical source | M |
| 4 | 🟠 HIGH | T117 test skip | Stale `skipif` "get_risk_manager missing from E01" — entire P01 test class silently skipped even though the symbol now exists | S |
| 5 | 🟠 HIGH | Risk gate drift | A02 TradingEngine still calls `risk_manager.check_trade(dict)` instead of typed `validate_signal(RiskValidationRequest)` | M |
| 6 | 🟠 HIGH | Datetime hygiene | 10+ `datetime.utcnow()` (deprecated in 3.12), pervasive naive `datetime.now()` | M |
| 7 | 🟡 MED | Orphan file | `Spyder/SpyderG_GUI/=2.8.0` — empty pip-redirect artifact | XS |
| 8 | 🟡 MED | Mega-module | G05 TradingDashboard at 6,595 LOC is untestable and fragile | L |
| 9 | 🟡 MED | Mega-module | B40 TradierClient at 3,236 LOC mixes REST/WS/auth/rate-limiting | L |
| 10 | 🟡 MED | `except BaseException` | Swallows `KeyboardInterrupt`/`SystemExit` in G11, I07 (×3), Q80, T09 | S |
| 11 | 🟡 MED | Legacy IB stubs | E13, U05 still carry dead IB module references and `IB = None` stubs | S |
| 12 | 🟡 MED | Filename drift | `SpyderT44_DatabentoClient_Test.py` tests Massive — misleading name | XS |
| 13 | 🟢 LOW | Dead code | G14 legacy dashboard stub still exported in `G_GUI/__init__.py` | XS |

---

## 1. Critical Issues (fix before next live deployment)

### 1.1 🔴 P04 CapitalAllocator uses RNG for regime & rebalance decisions

**File:** [Spyder/SpyderP_PortfolioMgmt/SpyderP04_CapitalAllocator.py](../Spyder/SpyderP_PortfolioMgmt/SpyderP04_CapitalAllocator.py#L1152-L1160)

```python
def _update_market_regime(self):
    regimes = list(MarketRegime)
    probabilities = [0.3, 0.2, 0.3, 0.15, 0.02, 0.03]
    self.current_regime = np.random.choice(regimes, p=probabilities)
    self.regime_confidence = np.random.uniform(0.6, 0.9)
```

And at line 1365:

```python
def _check_tactical_rebalance(self) -> bool:
    # For now, simple random check
    return np.random.random() < 0.05  # 5% chance
```

Both are called from live code paths ([L758](../Spyder/SpyderP_PortfolioMgmt/SpyderP04_CapitalAllocator.py#L758), [L944](../Spyder/SpyderP_PortfolioMgmt/SpyderP04_CapitalAllocator.py#L944)), not behind any demo-mode guard. `_adjust_for_regime` and downstream Kelly scaling then multiply a real capital figure by a regime-conditional factor derived from coin-flips.

**Fix:**
1. Route `_update_market_regime` to `SpyderL_ML.SpyderL09_UnifiedRegimeEngine.get_current_regime()` (the canonical source per Overview §1).
2. Replace `_check_tactical_rebalance` with an explicit rule: trigger on regime transition, correlation-matrix shift > configurable threshold, or allocator drift > band.
3. Add a unit test (T117) that asserts `CapitalAllocator` does not import `numpy.random` (or patches it and fails on call).

### 1.2 🔴 R04 LiveEngine blocks on order confirmation

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py](../Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1236-L1248)

```python
def _wait_for_execution(self, order_id: str, timeout: int = ORDER_TIMEOUT_SECONDS) -> dict[str, Any]:
    import time as _time
    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        if order_id in self.pending_orders:
            entry = self.pending_orders[order_id]
            result = entry.get("result")
            if result is not None:
                return result
        _time.sleep(0.1)
    return {"status": "timeout", ...}
```

This is a 100 ms busy-poll held open for the full `ORDER_TIMEOUT_SECONDS` window on the strategy orchestrator's thread, while the Tradier client is fundamentally async. Under any signal burst this multiplies tail latency by the polling granularity × the number of concurrent orders and can interleave badly with the PySide6 event loop.

**Fix:**
- Replace the poll with a `concurrent.futures.Future` (or `asyncio.Event`) stored in `pending_orders[order_id]["future"]`, and have the WS/REST callback that populates `entry["result"]` call `future.set_result(result)`.
- The caller then uses `future.result(timeout=ORDER_TIMEOUT_SECONDS)` — zero wake-up cost until the fill arrives.
- Add a T116 test that asserts total wall time ≈ fill latency (not polling granularity).

### 1.3 🔴 Simulated RNG in other "production" risk/allocation paths

Other grep-confirmed uses of `np.random.*` inside non-demo methods to audit:

| File | Line | Context |
|------|-----:|---------|
| [SpyderE10_CorrelationRiskManager.py](../Spyder/SpyderE_Risk/SpyderE10_CorrelationRiskManager.py#L1736) | 1736 | `market_loading = 0.3 + 0.4 * np.random.random()` for factor decomposition |
| [SpyderE19_UnifiedRiskCoordinator.py](../Spyder/SpyderE_Risk/SpyderE19_UnifiedRiskCoordinator.py#L714) | 714 | `np.random.random() < 0.1` — "10% chance of anomaly" |
| [SpyderE21_HMMRegimeDetector.py](../Spyder/SpyderE_Risk/SpyderE21_HMMRegimeDetector.py#L958) | 958 | Regime-change coin flip (legacy path) |
| [SpyderM06_HMMRegimeDetector.py](../Spyder/SpyderM_Monitoring/SpyderM06_HMMRegimeDetector.py#L1459-L1476) | 1459–1476 | Synthetic OHLCV generation — verify this is demo-only |
| [SpyderP07_RenaissancePositionSizer.py](../Spyder/SpyderP_PortfolioMgmt/SpyderP07_RenaissancePositionSizer.py#L647-L655) | 647–655 | Synthetic win/loss simulation |

**Action:** Classify each occurrence:
1. **Demo/self-test** → move into `if __name__ == "__main__":` block or delete.
2. **Production Monte Carlo** → use a module-scope `rng = np.random.default_rng(seed)` (seedable) and remove global state.
3. **Placeholder for real data** → wire to real source and delete the placeholder.

Add a ruff/grep CI gate that fails if `np.random.` appears outside `__main__`, test files, or explicitly-whitelisted Monte Carlo modules.

---

## 2. High-Severity Issues

### 2.1 🟠 Canonical regime enforcement is only partial

Overview §1 declares **L09 UnifiedRegimeEngine** the "single source of truth for market regime classification." In practice:

- F10 was defanged (returns `None` — good).
- V02 has its internal `MarketRegimeDetector` marked legacy.
- **E21, M06 still expose functional regime classifiers** that other modules could latch onto.
- **P04 does not consult L09 at all** (see §1.1).

**Fix:** Extend the T129 protocol-compliance suite with an assertion that every production module's regime accessor ultimately resolves through `SpyderL09_UnifiedRegimeEngine.get_instance()`. Wire P04, E19 (`_check_tactical_rebalance`), and the strategy-rotation path in P06 explicitly.

### 2.2 🟠 T117 stale skip hides real test coverage

**File:** [Spyder/SpyderT_Testing/SpyderT117_PSeries.py](../Spyder/SpyderT_Testing/SpyderT117_PSeries.py#L90-L97)

```python
# P01 has a pre-existing broken import (get_risk_manager missing from E01)
try:
    from Spyder.SpyderP_PortfolioMgmt import SpyderP01_PortfolioManager
    P01_AVAILABLE = True
except ImportError:
    P01_AVAILABLE = False

_skip_p01 = pytest.mark.skipif(not P01_AVAILABLE, reason="P01 unavailable (get_risk_manager missing)")
```

`get_risk_manager` is [present in E01 at line 1019](../Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L1019). The import now succeeds, so `_skip_p01` never triggers — but the comment is wrong and leaves a booby-trap: if the conditional import ever silently breaks again (e.g. via test-bootstrap pollution, already documented in repo memory), the skip would silently hide failures.

**Fix:**
1. Delete the try/except — import unconditionally.
2. Delete the misleading comment.
3. If P01 ever has a real optional dependency, gate it explicitly.

### 2.3 🟠 A02 TradingEngine bypasses typed E00 protocol

**File:** [Spyder/SpyderA_Core/SpyderA02_TradingEngine.py](../Spyder/SpyderA_Core/SpyderA02_TradingEngine.py#L1231)

```python
result = self.risk_manager.check_trade(risk_check)
```

`check_trade` is the legacy dict-adapter that internally calls `validate_signal`. The E00 Protocol is Spyder's declared typed boundary; using the dict adapter in the primary trading engine silently disables typing benefits and Protocol conformance.

**Fix:** Convert `risk_check` (already built as a dict) into `RiskValidationRequest` at the A02 call site and invoke `validate_signal` directly. Keep the `check_trade` adapter only for the legacy callers in K09 until those are migrated.

### 2.4 🟠 Datetime hygiene

- `datetime.utcnow()` — **deprecated in Python 3.12** — found in K01, C27 (×3), C35, S08 (×4). Breaks on 3.13+ with warnings.
- Bare `datetime.now()` (naive timestamp, no tz) used in ~40+ production sites (sampled across K02, K06, K08, K11, P07, Q90, Q92). This hurts any log or persisted timestamp that needs to reconcile across sessions or DST boundaries, and will cause subtle bugs around the 2 a.m. daylight-savings fold.

**Fix:**
1. Extend `SpyderU03_DateTimeUtils` with `now_utc()` and `now_et()` helpers.
2. Replace all `datetime.utcnow()` → `datetime.now(timezone.utc)` (or `now_utc()`).
3. Add a ruff custom rule (or grep-based CI gate in Q-Series) banning `datetime.now()`/`utcnow()` outside tests and Q-series scripts.

### 2.5 🟠 Orchestrator never observes rejected signals

D31 routes signals through `validate_signal()` and publishes a `RISK_ALERT` event on rejection (per Overview §6). Verified in code. However, there is no **metric counter** in B15/M04 for risk rejections, so rejection rate is invisible on Prometheus dashboards. This is the most important telemetry for a risk gate.

**Fix:** Add `spyder_risk_rejections_total{strategy, rejection_reason}` counter in M04 TradingMetrics, increment from D31 on every reject, and expose on the G07 Prometheus Metrics Display.

---

## 3. Medium-Severity Issues

### 3.1 🟡 `except BaseException` usage

Swallows `KeyboardInterrupt` and `SystemExit`:

- [SpyderG11_SkewMonitorDialog.py:232](../Spyder/SpyderG_GUI/SpyderG11_SkewMonitorDialog.py#L232)
- [SpyderI07_SyntaxValidator.py:432, 526, 534, 542](../Spyder/SpyderI_Integration/SpyderI07_SyntaxValidator.py#L432)
- [SpyderQ80_VerifyDashboardIntegration.py:219](../Spyder/SpyderQ_Scripts/SpyderQ80_VerifyDashboardIntegration.py#L219)
- [SpyderT09_TestDashboard.py:1863](../Spyder/SpyderT_Testing/SpyderT09_TestDashboard.py#L1863)

**Fix:** Narrow to `except Exception:` (or the specific subclasses). I07 is a syntax validator that may legitimately want to catch import failures at module load — use `except (ImportError, SyntaxError):` there.

### 3.2 🟡 G05 TradingDashboard mega-module (6,595 LOC)

Largest production module in the codebase. It imports at least G17, G18, G19 at runtime (per grep) and holds positions, P&L, Greeks, orders, signals, logs, market internals, and agent status all in one class.

**Refactor plan (propose, do not rush):**
- `G05a_DashboardLayout` — Qt widget hierarchy + docks (< 1,500 LOC).
- `G05b_DashboardController` — event routing + refresh timers + state (< 1,500 LOC).
- `G05c_DashboardPresenters` — per-panel view-model binding (split by tab; each < 800 LOC).
- Move the ~800 LOC of inline data-bridge code into existing `G06_DashboardData` / `G08_DashboardDataBridge`.

### 3.3 🟡 B40 TradierClient mega-module (3,236 LOC)

Mixes: OAuth + token refresh, REST endpoints, WS streaming, rate-limiting, retry with backoff, sandbox/live mode selection, account/positions/balances, options-chain fetch. Any bug in WS handling risks the REST path (shared session, shared lock).

**Refactor plan:**
- `B40a_TradierAuth` — token/env, Bearer header construction.
- `B40b_TradierREST` — all REST verbs.
- `B40c_TradierStream` — WS/SSE client.
- `B40_TradierClient` — thin facade composing the above.

### 3.4 🟡 Orphan/legacy artifacts

- **`Spyder/SpyderG_GUI/=2.8.0`** — empty file from a mistyped `pip install pyqtgraph=2.8.0` (missing second `=`). Delete it.
- **`SpyderG14_Dashboard.py`** (128 LOC) — "legacy stub" still imported in `SpyderG_GUI/__init__.py`. Either promote to a real component or delete and remove the import.
- **`SpyderT44_DatabentoClient_Test.py`** — filename retained for "legacy reasons" per the v4 overview, but tests the Massive client. Rename to `SpyderT44_MassiveClient_Test.py` and update the catalogue.
- **`SpyderE13_DayProfitTarget.py` lines 61–64** — `IB = None  # type: ignore` stubs for long-removed Interactive Brokers modules. Delete.
- **`SpyderU05_NetworkUtils.py` IB_ENDPOINTS** (lines 65–69) — dead IB gateway/TWS config.
- **`SpyderQ01_FixExceptionHandling.py:133-134`** — literal `except:/pass` — fine (lint example strings) but should be kept as a triple-quoted string literal not a real `except:` clause to avoid self-triggering any future scanner.

### 3.5 🟡 yfinance external-dependency risk

S01 DIX, S05 GEX/DEX, S08 ShortSqueezeDetector all depend on yfinance. yfinance has:
- No SLA, frequent rate-limit 429s.
- Repeatedly scraped/changed response shapes.
- ToS grey area for commercial use.

**Fix:**
1. Add a `ProviderHealth` score in C29 DataProviderRouter.
2. For DIX market-caps (S01), preserve the daily disk cache more aggressively and refuse to start the system without a recent (< 7-day) cache file present. Today an initial cold start requires ~6 min of yfinance hits.
3. Consider an alternate source: Tradier does not provide market caps, but Financial Modeling Prep / Polygon reference endpoints do — add one as a fallback.

### 3.6 🟡 Prometheus fragmentation

Trading metrics live in both `SpyderB15_PrometheusMetrics` and `SpyderM04_TradingMetrics`, with the HTTP endpoint in `M08`. Duplicate counter registration risks `ValueError: Duplicated timeseries in CollectorRegistry` at import-order-dependent times.

**Fix:** Route all Prometheus registrations through a single `MetricsRegistry` in M04, with B15 exporting *definitions* only (not registering). The M08 endpoint already binds to that registry — consolidate.

---

## 4. Low-Severity / Cosmetic

1. `SpyderJ02_EmailNotifier.py:786` — a demo block has `password='encrypted_password'  # Would be encrypted`. Harmless string literal, but flagged by any secrets scanner. Change to `password='<REPLACE_ME>'`.
2. `Spyder/SpyderQ_Scripts/SpyderQ01_FixExceptionHandling.py` contains literal `except:` that's actual code, not a docstring. Its intent is to be caught by *itself*. Consider wrapping as `textwrap.dedent` string.
3. Overview v4 missing entries: **G17_MarketInternalsWidget**, **G18_MarketDataWorker**, **G19_ChartIndicators** (all referenced by G05 at runtime). Update the overview catalogue.
4. `SpyderB30_SPYOptionsChainManager.py:878` — `# TODO: Reinitialize with new expiration`. Only surviving TODO in the production tree; worth tracking as a ticket.
5. `SpyderT130_IronCondorSandbox_Test.py` contains ~30 `print()` calls — it's an interactive CLI sandbox test, but tag it `@pytest.mark.manual` so CI never imports it.

---

## 5. Enhancement Opportunities (new ideas)

### 5.1 🧭 Closed-loop risk gate CI

Extend `SpyderQ10_ProtocolComplianceGate` to also fail if:
- Any strategy file imports `SpyderB40_TradierClient` directly (should route through D31 + B02 OrderManager).
- Any production module under P/E imports `numpy.random` at module top-level.
- Any production module has a naive `datetime.now()` (regex gate, whitelist-by-comment).

### 5.2 🧭 Paper-to-live promotion gate

Today the switch from paper → live is done manually via `Q93_RunPaper` vs `Q14_MainLauncher`. Add `SpyderQ15_PromotionGate` that, given a strategy id:
1. Reads paper results from H04 TradeRepository.
2. Requires: ≥ N_TRADES paper trades, Sharpe ≥ S_MIN, max-DD ≤ DD_MAX over the paper window.
3. Emits a signed "promotion token" stored in H07 that the live engine refuses to run without.

### 5.3 🧭 Autonomous ML drift → model pause

K08 MLPerformanceReport already detects drift. Wire Y04 AlphaLearnerAgent to:
- On drift detection for model `m`, call L11 ModelManager to mark `m` as `paused`.
- Publish `MODEL_PAUSED` event on I02 EventRouter.
- Let D31 skip any signal whose `ml_model_id` is paused.
- Operator must manually unpause (or autonomous Y09 CodeReviewer proposes a retrain PR).

### 5.4 🧭 Dealer flow telemetry tier

N09 GammaExposure and S05 GEX/DEX compute dealer hedging flows but don't feed back into strategy sizing. A natural enhancement:
- Publish net-GEX flip level to E15 GreekLimitsManager.
- Scale portfolio-vega hard limit as a function of distance from flip (tighter near the zero-gamma level, where dealer hedging amplifies moves).

### 5.5 🧭 Multi-provider data router health scoring

C29 DataProviderRouter is currently a static switch. Extend it to:
- Track (latency, error_rate, 429_count, schema_mismatch_count) per provider on a rolling 5-minute window.
- Expose a health score 0-1.
- On a provider score drop below threshold, auto-failover (Tradier ↔ Massive) and emit a J-Series alert.

### 5.6 🧭 Secrets hygiene

Add a `pre-commit` config with:
- `detect-secrets` or `gitleaks` scan.
- A custom hook enforcing `SpyderU46_SecretsManager` is the only import path for any API key.

### 5.7 🧭 GUI cross-thread lint

Per repo memory ([pyside6-cross-thread-gotchas](../../.copilot-memories/repo/pyside6-cross-thread-gotchas.md) equivalent), add a grep-based CI gate banning `.connect(lambda` patterns outside whitelisted files. These reliably cause cross-thread QObject bugs on PySide6.

### 5.8 🧭 Observability of Y-Series autonomous agents

Y08 MetaOrchestrator monitors agent liveness, but there's no Prometheus histogram of per-agent task latency. Add `spyder_yagent_task_latency_seconds{agent}` to M04, scraped by M08, charted on the G32 AgentHealthDashboard.

### 5.9 🧭 Tradier rate-limit smoothing

Currently B40 retries with exponential backoff. Add a token-bucket pre-limiter sized to Tradier's published 120 req/min so bursts from G18 MarketDataWorker do not compete with order-execution traffic from R04.

### 5.10 🧭 Regulatory report hashing

K09 RegulatoryReports produces trade confirmations but does not hash-chain them. Add a SHA-256 chain over daily report output stored in H04 — cheap insurance for audit integrity and aligned with NYSE CAT expectations.

---

## 6. Recommended Execution Order for the Coding Agent

1. **Safety-first hotfixes** (small, branch `fix/random-in-prod`):
   - Delete `=2.8.0` orphan file.
   - Remove T117 stale skip (§2.2).
   - Replace P04 RNG paths with L09 + rule-based rebalance (§1.1).
   - Remove `np.random.random()` from E19 `_check_tactical_*` paths (§1.3).
2. **Correctness** (`fix/live-engine-async`):
   - Replace R04 poll-loop with Future (§1.2).
   - Migrate A02 `check_trade` → typed `validate_signal` (§2.3).
   - Add risk-rejection Prometheus counter (§2.5).
3. **Hygiene** (`chore/datetime-and-lint`):
   - `datetime.utcnow()` → `datetime.now(UTC)`; add U03 helpers (§2.4).
   - Narrow `except BaseException` → `except Exception` (§3.1).
   - Delete legacy IB stubs (§3.4).
   - Rename T44 Databento→Massive (§3.4).
4. **Refactor** (large, separate PRs each):
   - G05 decomposition (§3.2).
   - B40 decomposition (§3.3).
5. **New capabilities** (each a separate feature branch):
   - Paper→live promotion gate (§5.2).
   - Provider-health router (§5.5).
   - ML drift → auto-pause (§5.3).
   - Dealer-flow-aware vega limits (§5.4).

---

## 7. Acceptance Criteria Snapshot

Before any live-deployment sign-off following this audit, CI must show:
- `SpyderQ10_ProtocolComplianceGate` green, with the regime-source and np.random gates added.
- T117 running P01 tests without skip.
- Zero occurrences of `datetime.utcnow()` in production modules.
- Zero occurrences of `np.random.` in `SpyderE_Risk/`, `SpyderP_PortfolioMgmt/` outside `__main__` blocks and seeded Monte Carlo modules.
- Prometheus scrape output contains `spyder_risk_rejections_total` and `spyder_yagent_task_latency_seconds`.
- `git ls-files` shows no path matching `=*` or other non-python artifacts in `SpyderG_GUI/`.

---

*Prepared by Claude (Spyder coding agent) — 2026-04-16*
*Next review recommended after hotfix batch 1 (§6.1) merges.*
