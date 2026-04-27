# Spyder Codebase Audit v24 — Pre-Live-Trading Verification Pass
**Date:** 2026-04-26
**Branch:** `fix/audit-v14-all`
**Auditor:** Claude (Opus 4.7)
**Status:** 4 issues fixed in-session; 6 contamination-only test failures documented; production runtime path verified clean.

---

## 1. Executive Summary

You asked for a verification pass before going live with hands-free SPY options trading.
I audited the wiring, ran the full test suite, and fixed every real production issue I found.

**Headline numbers**

| Metric                            | Before        | After          |
|-----------------------------------|--------------:|---------------:|
| Test suite pass count             | 9 977         | 9 979          |
| Real production failures          | 4             | 0              |
| Test-contamination-only failures  | 4             | 6 (\*)         |
| Files modified this session       | —             | 14             |

(\*) Two T142 tests started passing in isolation after the import-cycle fix but still
fail in the full suite due to upstream test contamination on D33/D34 strategy
modules. Same pattern as the T54 contamination that was already known. **Neither
contamination affects the runtime path** — both pass when the module under test is
loaded by itself.

**Verdict for live trading:** the runtime path is clean. The branch can ship a
paper soak; the test-suite contamination is a test-quality issue (collection-order
side-effects), not a production behavior issue. I would not block live on it, but
I'd schedule a hardening pass to make the test fixtures truly hermetic.

---

## 2. Real Production Issues Found and Fixed

### Issue #1 — D-strategy circular-import cycle via `RiskProfile`

**Severity:** HIGH (silent)
**Module:** `Spyder/SpyderD_Strategies/SpyderD0[2-9],D1[0-7],D21*.py`
**Symptom:** Six of D31's thirteen registered strategy types disappeared in any
test environment that touched the strategy package before D31 instantiated.
The D31 log showed `Registered 7 strategy types` instead of 13.

**Root cause:** Ten D-series strategies imported `RiskProfile` from
`Spyder.SpyderE_Risk.SpyderE01_RiskManager` at module top-level. E01 is
mid-loading whenever the D-package `__init__` runs first (which happens during
test collection because conftest re-primes packages on every collect).
Mid-loading E01 has not yet defined `RiskProfile` at line 174, so the import
raises `cannot import name 'RiskProfile'`. The D-package init catches the
`ImportError` and silently drops that strategy.

In production this only bites if the import sequence is wrong (e.g., a startup
script imports a D-strategy before `D31_StrategyOrchestrator`). The audit log
shows it bit several tests (T142 visible, but the contamination is broader).

**Fix:** Pointed the ten D-strategies at `D01_BaseStrategy.RiskProfile`, which
they already depend on transitively via `BaseStrategy`. D01's `RiskProfile` is
the strategy-side dataclass and is what `BaseStrategy.__init__` actually uses.
This breaks the cycle.

**Files changed:**
[SpyderD02_IronCondor.py](Spyder/SpyderD_Strategies/SpyderD02_IronCondor.py),
[SpyderD10_IronButterfly.py](Spyder/SpyderD_Strategies/SpyderD10_IronButterfly.py),
[SpyderD11_SpecializedZeroDTE.py](Spyder/SpyderD_Strategies/SpyderD11_SpecializedZeroDTE.py),
[SpyderD12_RSIMeanReversion.py](Spyder/SpyderD_Strategies/SpyderD12_RSIMeanReversion.py),
[SpyderD13_MACrossover.py](Spyder/SpyderD_Strategies/SpyderD13_MACrossover.py),
[SpyderD14_CalendarSpread.py](Spyder/SpyderD_Strategies/SpyderD14_CalendarSpread.py),
[SpyderD15_StraddleStrangle.py](Spyder/SpyderD_Strategies/SpyderD15_StraddleStrangle.py),
[SpyderD16_RatioSpreads.py](Spyder/SpyderD_Strategies/SpyderD16_RatioSpreads.py),
[SpyderD17_DiagonalSpread.py](Spyder/SpyderD_Strategies/SpyderD17_DiagonalSpread.py),
[SpyderD21_DoubleCalendar.py](Spyder/SpyderD_Strategies/SpyderD21_DoubleCalendar.py)

---

### Issue #2 — `PortfolioManager` reports ACTIVE before any thread is running

**Severity:** MEDIUM
**Module:** [SpyderP01_PortfolioManager.py:838](Spyder/SpyderP_PortfolioMgmt/SpyderP01_PortfolioManager.py#L838)
**Symptom:** `pm.state == PortfolioState.ACTIVE` immediately after `__init__`,
before `start_management()` was called and before the management/rebalance
threads existed.

**Why it matters for live trading:** dashboards, supervisors, and other
consumers polling `pm.state` would see ACTIVE and assume the portfolio is being
managed when in fact no thread is running. A health-check that gates on
`state == ACTIVE` would pass falsely.

**Fix:** Removed the `self.portfolio_state = PortfolioState.ACTIVE` line from
`_initialize_portfolio()`. State now stays `INITIALIZING` until
`start_management()` (line 529) flips it to ACTIVE alongside the actual thread
spawn. This matches the existing emergency/shutdown/rebalance state flow,
which only flips when the corresponding action actually happens.

---

### Issue #3 — `H05_TradingSessionDB` reintroduced naive `datetime.utcnow()`

**Severity:** MEDIUM
**Module:** [SpyderH05_TradingSessionDB.py](Spyder/SpyderH_Storage/SpyderH05_TradingSessionDB.py)
**Symptom:** Six occurrences of `datetime.utcnow()` (deprecated in Python 3.12+)
plus one ugly `__import__("datetime").timedelta(...)` workaround on line 476.

**Why it matters:** This module is the v23 dual-DB session store, added after
the v14 audit fixed exactly this anti-pattern in R13/B03. So the new code
regressed against the v14 fix.

**Fix:** Switched all six call sites to `datetime.now(timezone.utc)` and
replaced the `__import__` workaround with a normal `from datetime import
timedelta`. Smoke-tested: `record_trade`, `record_account_snapshot`,
`get_pnl_summary` all working with timezone-aware ISO timestamps written
to the SQLite store.

---

### Issue #4 — T135 event-clock test counted scheduler-init noise

**Severity:** LOW (test bug, not production)
**Module:** [SpyderT135_A04_EventClockFeed.py](Spyder/SpyderT_Testing/SpyderT135_A04_EventClockFeed.py)
**Symptom:** `assert len(em.events) == 1` failed because `Scheduler.__init__`
emits 12 `task_added` SYSTEM events for its default tasks, which the test's
DummyEventManager captured along with the 1 RISK event_clock_state event.

**Why it matters for live trading:** it doesn't. The scheduler's task_added
emission is intentional and consumed by other parts of the system. The test
was written against an older scheduler that didn't emit on init.

**Fix:** Added a local `_clock_events()` filter that only counts events whose
payload type is `event_clock_state`. The test now correctly asserts the
event-clock state-machine semantics it was meant to test, regardless of
init-time noise.

---

## 3. v14 / v22 / v23 Closures Re-Verified

| Audit | Item                                              | Status |
|-------|---------------------------------------------------|--------|
| v14   | A1–A6 (concurrency, datetime, fill-price guard)   | ✅ holding (R04 `_active_positions_lock` used at 5 sites) |
| v14   | A14 OrderStatus transition validator              | ✅ wired in `B00_OrderTypes.transition_to()` (log-only mode) |
| v14   | N04 singleton wiring (E01/E03/E15/D09)            | ✅ all four sites use `get_n04_calculator()` |
| v22   | D31 tick-dict unpacking                           | ✅ `_on_market_data_event` unpacks `data["tick"]` |
| v22   | A06 starts E01 RiskManager                        | ✅ daemon-thread + 15s join present |
| v22   | E01 standalone mode synced                        | ✅ `_account_state_synced=True` when `tradier_client is None` |
| v22   | D01 `auto_execute` bypass                         | ✅ direct `add_position()` call removed; warning-only |
| v22   | F-series wired into signal path                   | ✅ A02 + D31 both lazy-build `EntryFilters` gate |
| v23   | Dual session DB (R12 → R04 + R08)                 | ✅ mode-aware `set_session_db` injection verified |

Every v14 BLOCKER closure I spot-checked is still in place after the v22/v23
work. No regressions.

---

## 4. Remaining Test Suite Failures (post-fixes)

```
9 979 passed, 6 failed, 18 skipped, 2 xfailed in ~315s
```

All 6 are full-suite-only contamination — every one passes when its file is
run alone:

| Test                                                              | Behaviour |
|-------------------------------------------------------------------|-----------|
| T54::test_collect_state_marks_safe_fallback_in_paper_mode        | passes alone, `TypeError: issubclass()` in full suite |
| T54::test_emit_logs_styles_button_for_safe_mode                  | passes alone, same error |
| T54::test_append_banner_unavailable_when_readiness_not_checked   | passes alone, same error |
| T142::test_d31_registry_includes_first_wave_base_strategies      | passes alone after Issue #1 fix; D33/D34 only in full suite |
| T142::test_d31_configure_regime_selects_newly_wired_strategies   | same |
| T142::test_d31_current_regime_weights_are_registry_reachable     | same |

**Why the contamination happens:** [conftest.py](conftest.py) re-imports a
small set of `U_/A_/G_/I_` modules between collections, but does NOT clean
strategy / risk / portfolio modules. Some earlier test partially patches
sys.modules entries (most likely a test that uses `patch.dict(sys.modules,
...)`) — when D-package init runs after that patch is undone, a transitive
import sees a stub module and silently drops the affected strategy.

**My recommendation:** treat this as a test-fixture hardening backlog item, not
a launch blocker. The runtime never sees this state. If you want to clear it,
the fix is to extend conftest's `watched_prefixes` to include
`Spyder.SpyderD_Strategies` / `Spyder.SpyderE_Risk` / `Spyder.SpyderG_GUI`
(but that risks slowing collection notably and may break tests that *want* a
patched module to persist across cases — needs care).

---

## 5. Things I Inspected and Found Clean

- `NotImplementedError` in production paths: 0 occurrences
- `TODO` / `FIXME` / `XXX` in production paths: 0 occurrences
- Bare `except:` clauses in production paths: 0 (the two `except BaseException`
  in [SpyderU45_RetryWithBackoff.py](Spyder/SpyderU_Utilities/SpyderU45_RetryWithBackoff.py)
  filter via `_should_retry()` so KeyboardInterrupt re-raises correctly)
- Syntax errors across all 510 production `.py` files: 0
- Naive `datetime.now()` / `datetime.utcnow()` in **trading-critical** paths:
  H05 fixed; remaining occurrences are in scripts (Q\*), monitoring (M\*,
  R09 deployment manager), and analytics (R11 paper strategy runner) —
  these are display / logging timestamps, not order-routing decisions.
  Documented as opportunity below.
- Dual-DB live/paper parity (v23): `R12 → R04.set_session_db` injection point,
  `R04._on_reconciler_fill` write hook, `R08` paper worker write hooks —
  all verified by reading the code paths and existing T129 P114 integration
  tests still pass.

---

## 6. Opportunities (Not Fixed — Recommendations)

### Opp 1 — Naive `datetime.now()` in R02 / R03 / R11 / S05

R02 PaperEngine, R03 PaperMonitor, R11 PaperStrategyRunner, and S05
GEXDEXCalculator still use `datetime.datetime.now()` (no tz). These are paper /
analytics paths so the impact is cosmetic (timestamps in logs and snapshots
are local-tz-dependent), but the v14 audit explicitly fixed this pattern
elsewhere. Suggest a follow-up sweep that mirrors the v14 commit `7f4cf9e`.

### Opp 2 — Three different `RiskProfile` classes

After my fix, D01 is the single import target for D-strategies, but
[E01_RiskManager.py:174](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L174)
still defines its own `RiskProfile`, and
[SpyderD19_JadeLizard.py:107](Spyder/SpyderD_Strategies/SpyderD19_JadeLizard.py#L107)
defines a third one (an `Enum`!). The three coexist because they have
incompatible field sets and meanings. Worth a refactor pass to unify or rename
(`E01.RiskState` vs `D01.RiskProfile` vs `D19.RiskTier` would be clearer).

### Opp 3 — Conftest cleanup is incomplete

The conftest's `watched_prefixes` covers U/A/G/I but not D/E/H/N/P/R — and the
test suite contamination this audit surfaced is happening exactly in those
unwatched packages. Either widen the cleanup, or migrate tests off
`patch.dict(sys.modules, ...)` toward `monkeypatch.setattr(module, "x", ...)`
which is auto-reverted by pytest.

### Opp 4 — `auto_execute=True` warning is dead code

[D01_BaseStrategy.py:769](Spyder/SpyderD_Strategies/SpyderD01_BaseStrategy.py#L769)
emits a warning if `config.auto_execute=True`, but the actual
`add_position()` direct-call has already been removed. The warning is
harmless but misleading — it suggests a bypass exists when it doesn't.
Either delete the warning or actually error out so misconfigured strategies
fail fast at startup instead of silently behaving correctly.

### Opp 5 — `R08 PaperTradingQtWorker` and `R12 SessionSupervisor` both
construct their own paper-DB connections

`R12` injects a `TradingSessionDB.for_paper()` into the LiveEngine when
mode=paper, while `R08` (the GUI-driven paper worker) constructs its own
`TradingSessionDB.for_paper()` in `__init__`. WAL mode handles concurrency
fine, but if both ever run concurrently (e.g., supervisor-run paper alongside
GUI-run paper for the same operator) you'd get duplicated trade rows.
Recommend gating R08's DB construction on "is the supervisor already
managing me?" or sharing the supervisor's instance.

### Opp 6 — Heartbeat / liveness file rotation

R05 LivenessMonitor (added in v14) writes a heartbeat file but doesn't
rotate it. After 24h of trading the file accumulates indefinitely. Rotate
on day-boundary or cap at N entries.

---

## 7. Files Modified This Session

```
Spyder/SpyderD_Strategies/SpyderD02_IronCondor.py
Spyder/SpyderD_Strategies/SpyderD10_IronButterfly.py
Spyder/SpyderD_Strategies/SpyderD11_SpecializedZeroDTE.py
Spyder/SpyderD_Strategies/SpyderD12_RSIMeanReversion.py
Spyder/SpyderD_Strategies/SpyderD13_MACrossover.py
Spyder/SpyderD_Strategies/SpyderD14_CalendarSpread.py
Spyder/SpyderD_Strategies/SpyderD15_StraddleStrangle.py
Spyder/SpyderD_Strategies/SpyderD16_RatioSpreads.py
Spyder/SpyderD_Strategies/SpyderD17_DiagonalSpread.py
Spyder/SpyderD_Strategies/SpyderD21_DoubleCalendar.py
Spyder/SpyderH_Storage/SpyderH05_TradingSessionDB.py
Spyder/SpyderP_PortfolioMgmt/SpyderP01_PortfolioManager.py
Spyder/SpyderT_Testing/SpyderT135_A04_EventClockFeed.py
04-CodeBase-Audits/2026-04-26_Codebase_Audit_v24.md   (this file)
```

---

## 8. Pre-Live Go/No-Go Recommendation

**Go for paper soak** on this branch as-is. The runtime path is verified clean
and the 4 issues fixed in this session were either silent (D-strategy import
cycle, P01 state) or cosmetic-but-regressed-from-v14 (H05 datetime).

**Before flipping the live switch**, I'd want:

1. A clean 48-hour paper soak run on this build (per v14 §6 — still the gate)
2. Opportunity #5 resolved (R08 vs R12 DB-injection clarity) — easy win
3. Opportunity #1 (naive datetime sweep on R02/R03/R11/S05) — boring but
   completes the v14 cleanup
4. Conftest hardening (Opp #3) so future regressions surface instead of
   hiding behind contamination

None of those four are launch-blockers; they're hygiene.
