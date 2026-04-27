# Spyder v9 Audit — Autonomous SPY Options Trading Readiness

**Date:** 2026-04-19
**Reviewer:** Claude (Opus 4.7)
**Scope:** Verify the v9-documented wiring actually executes end-to-end. Flag anomalies, deficiencies, and improvement opportunities ahead of enabling fully autonomous order generation.
**Input:** `01-Overview-Specs/2026-04-19-Spyder-Overview-v9.md`
**Implementation session:** 2026-04-19 (Claude Sonnet 4.6 on branch `refactor/g05-widget-extraction`)

---

## Implementation Progress

| Item | Status | Notes |
|------|--------|-------|
| P0-1 | ✅ FIXED | `def _initialize_strategy_registry` header restored in D31 |
| P0-2 | ✅ FIXED | `fill_reconciler=` + `position_tracker=` wired into R12 `create_live_engine` call |
| P0-3 | ✅ FIXED | ExitMonitor attribute, `_start_exit_monitor()`, sequence step 10, module accessors, D31 hook |
| P1-1 | ✅ FIXED | Q10 Gate 5 uses `inspect.signature` two-pass check |
| P1-2 | ✅ FIXED | D31 except block given 10 `None` stubs; `__init__` uses callable guard for `get_event_manager` — `StrategyOrchestrator(event_manager=None)` instantiates cleanlyent_manager` — `StrategyOrchestrator(event_manager=None)` instantiates cleanly |
| P1-3 | ✅ FIXED | Renamed to `SpyderE24_DataFreshnessMonitor.py` (E14 was taken); E02 kept as backward-compat shim |
| P1-4 | ✅ FIXED | Rolling `_peak_session_pnl` drawdown calculation in R04 |
| P1-5 | ✅ FIXED | Both `return "bull_trending"` stubs replaced with `engine.current_regime.value` |
| P2-1 | ✅ FIXED | Q14 dead `_start_live_engine` method (119 lines) deleted; `launch_system()` remains the canonical pathed; `launch_system()` remains the canonical path |
| P2-2 | ✅ FIXED | R15 `place_order` now has explicit `symbol, side, quantity, order_type, limit_price=None, **kwargs` |
| P2-3 | ✅ FIXED | `EndToEndHappyPathTest` class added to T129 (5 tests: PaperBroker ack, FillReconciler tracking, ExitMonitor sweep, orphan alert, D31 instantiation) — all passts: PaperBroker ack, FillReconciler tracking, ExitMonitor sweep, orphan alert, D31 instantiation) — all pass |
| P2-4 | ✅ FIXED | `_NullBroker.place_order` now emits `RISK_VIOLATION` event |
| P2-5 | ✅ FIXED | `slippage_bps: int = 5` added to `PaperBroker.__init__` and `create_paper_broker`; fill price perturbed by `±slippage_bps/10000` (buys fill higher, sells fill lower); `side` stored per-orderker.__init__` and `create_paper_broker`; fill price perturbed by `±slippage_bps/10000` (buys fill higher, sells fill lower); `side` stored per-order |
| O-1  | ✅ FIXED | Gate 6 `check_module_imports()` added to Q10 |
| O-2  | ✅ FIXED | `_boot_orphan_sweep()` added to R12; called after `_running = True` — wraps `exit_monitor._sweep_once()` in try/exceptalled after `_running = True` — wraps `exit_monitor._sweep_once()` in try/except |
| O-3  | ✅ FIXED | `_broker_submit` raises `RuntimeError` when `_reconciler is None` and `mode == TradingMode.LIVE`mode == TradingMode.LIVE` |
| O-4  | ✅ FIXED | `EventType.KILL_SWITCH = "kill_switch"` added to A05 enum; R04 subscribes and sets `_kill_switch_active`; `_broker_submit` refuses all orders when actived to A05 enum; R04 subscribes and sets `_kill_switch_active`; `_broker_submit` refuses all orders when active |
| O-5  | ✅ FIXED | `dry_run: bool = False` added to `SessionSupervisor.__init__` and `create_session_supervisor`; in paper+dry_run mode `place_order` is no-op returning `{"order": {"id": "DRY-RUN-NOOP"}}`it__` and `create_session_supervisor`; in paper+dry_run mode `place_order` is no-op returning `{"order": {"id": "DRY-RUN-NOOP"}}` |
| O-6  | ✅ FIXED | R13 adds `spyder_orders_submitted_total` (in `track()`) + `spyder_fills_detected_total` (at ORDER_FILLED emit); R14 adds `_prom` soft-import + `spyder_exits_emitted_total` + `spyder_orphans_detected_total`l` (in `track()`) + `spyder_fills_detected_total` (at ORDER_FILLED emit); R14 adds `_prom` soft-import + `spyder_exits_emitted_total` + `spyder_orphans_detected_total` |

---

## Verdict

~~**NOT READY for autonomous trading.**~~ All P0 blockers, all P1 items (including P1-2), all P2 items, and all O-series operability improvements are now resolved. The system has working fill reconciliation, automated exits, orphan detection, a kill-switch event contract, slippage-modelled paper fills, a dry-run mode, and an extended Prometheus counter floor. **Ready for a supervised paper-mode run ahead of live deployment.**

---

## P0 — Blockers (system will not trade)

### ✅ P0-1 — D31 StrategyOrchestrator cannot be instantiated — FIXED
**File:** [Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py)
**Evidence:**
- `__init__` calls `self._initialize_strategy_registry()` at line 372.
- `grep "def _initialize_strategy_registry"` in D31 returns **zero matches**.
- Lines 1579–1591 contain the *body* of that method (docstring + `available_strategies` dict assignment + logger call), dangling at class-body indent inside `_generate_final_report`'s `except` block. The `def` header was deleted at some point.

**Consequence:** Every orchestrator construction raises `AttributeError: 'StrategyOrchestrator' object has no attribute '_initialize_strategy_registry'`. SessionSupervisor cannot boot.

**Fix applied:** Re-inserted `def _initialize_strategy_registry(self) -> None:` after the `_generate_final_report` except block; body re-indented to method level. All edited files parse clean via `ast.parse`.

> **Now resolved:** Unit test added in T129 under `EndToEndHappyPathTest` — see P2-3.

---

### ✅ P0-2 — R12 SessionSupervisor never wires FillReconciler to LiveEngine — FIXED
**File:** [Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L335)
**Evidence:**
- `_start_fill_reconciler` (line 308) creates `self.reconciler` successfully.
- `_start_live_engine` (line 335) calls `create_live_engine(self.broker, self.risk, config, event_manager=self.em)` — no `fill_reconciler=` kwarg.
- `SpyderR04_LiveEngine.create_live_engine` and `LiveEngine.__init__` accept `fill_reconciler` (R04:209). When absent, `self._reconciler = None`.
- LiveEngine line 1281: `self._reconciler.track(...)` is guarded by `if self._reconciler is not None` — so orders submitted but **never reconciled**. No `ORDER_FILLED` events are ever emitted in live mode.

**Consequence:** Strategies issue signals, orders reach broker, but PortfolioManager never hears fills → ExitMonitor sees no positions → no closes ever fire → runaway risk.

**Fix applied:** `_start_live_engine` now passes `fill_reconciler=self.reconciler` and `position_tracker=getattr(self, "position_tracker", None)`.

---

### ✅ P0-3 — R14 ExitMonitor is dead code — FIXED
**Files:**
- [Spyder/SpyderR_Runtime/SpyderR14_ExitMonitor.py](Spyder/SpyderR_Runtime/SpyderR14_ExitMonitor.py) — fully implemented, never imported.
- [Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py)

**Evidence:** Grep for `ExitMonitor|create_exit_monitor` across `SpyderR_Runtime/` returns only R14 itself. SessionSupervisor has no corresponding `_start_exit_monitor()` helper. The v9 spec calls R14 "lifecycle-owned by SessionSupervisor" — that ownership does not exist in code.

**Consequence:** No automated exits, no orphan-position alerts, no STRATEGY_SIGNAL(action=close) emissions. Positions only close if a strategy happens to generate a close signal on its own or a human intervenes.

**Fix applied:**
1. `self.exit_monitor: Any = None` added to R12 `__init__`.
2. `_start_exit_monitor()` added — constructs monitor with `portfolio_manager`, `strategy_map`, `event_manager`; calls `.start()`.
3. Step 10 `self._start_exit_monitor()` added to `start()` sequence (after orchestrator step).
4. Module-level `get_session_supervisor()` / `set_session_supervisor()` added for cross-module access.
5. D31 `add_strategy` now calls `get_session_supervisor().exit_monitor.register_strategy(...)` (lazy import, try/except guarded).

---

## P1 — High severity (degraded safety / false-positive CI)

### ✅ P1-1 — Q10 Gate 5 does not actually verify BrokerProtocol — FIXED
**File:** [Spyder/SpyderQ_Scripts/SpyderQ10_ProtocolComplianceGate.py:295](Spyder/SpyderQ_Scripts/SpyderQ10_ProtocolComplianceGate.py#L295)
**Evidence:**
```python
missing = [m for m in _REQUIRED_METHODS if not callable(getattr(cls, m, None))]
```
This is a name-only check. BrokerProtocol is imported at line 261 and then never used. Signatures, return types, and the `@runtime_checkable` contract go unverified. A broker that implements `place_order(foo)` instead of `place_order(symbol, side, quantity, order_type, limit_price=None, **kwargs)` passes Gate 5.

**Fix applied:** Gate 5 now uses a two-pass check: (1) method name presence, (2) `inspect.signature` comparison — `proto_params - impl_params` fails the gate unless the implementation carries a `VAR_KEYWORD` (`**kwargs`) covering the gap.

---

### ✅ P1-2 — Cascade import failures block any bootstrap attempt — FIXED
**Evidence:** Attempted live instantiation of `StrategyOrchestrator(...)` yielded:
- `NameError: get_event_manager` (D31:305)
- 9 other names absent from the `except ImportError` block
- `TypeError` when null stub was called unconditionally

**Fix applied:**
1. 10 `None` stubs added to D31 `except ImportError` block (`SpyderLogger`, `SpyderErrorHandler`, `TradingCalendar`, `PerformanceMetrics`, `BaseStrategy`, `IntegratedConnectivityManager`, `EventManager`, `Event`, `EventType`, `get_event_manager`).
2. `__init__` guards `_gem` with `callable(_gem)` before calling; falls back to direct A05 import.
3. Verified: `StrategyOrchestrator(event_manager=None)` instantiates cleanly with `available_strategies == {}` and `active_strategies == {}`.

---

### ✅ P1-3 — E02 filename collision — FIXED
**Files:**
- `Spyder/SpyderE_Risk/SpyderE02_PositionSizer.py`
- `Spyder/SpyderE_Risk/SpyderE02_DataFreshnessMonitor.py`

**Evidence:** Two modules share the `E02` numeric prefix. Any reference by the v9 docs' naming scheme (e.g. "E02") is ambiguous; any future Q-gate that scans by prefix will either double-count or race on whichever `glob` returns first.

**Fix applied:** Copied to `SpyderE24_DataFreshnessMonitor.py` (E14–E23 were occupied; E24 was the first free slot — note: audit suggested E14). Old E02 file replaced with a backward-compat shim. Active imports in R12 and Q14 updated to E24.

---

### ✅ P1-4 — Portfolio drawdown is a hardcoded stub — FIXED
**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:1152](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1152)
```python
def _calculate_portfolio_drawdown(self) -> float:
    return 0.0
```
**Consequence:** Any gate that reads drawdown (E11 MaxLoss, E13 DayProfitTarget, risk manager pre-trade check) sees zero drawdown forever. Kill-switch by drawdown does not exist.

**Fix applied:** `__init__` now initialises `self._peak_session_pnl: float = 0.0`. `_calculate_portfolio_drawdown` tracks a rolling peak via `current_session.total_pnl`; formula: `(peak - current) / peak` when peak > 0; falls back to `min(daily_loss / max_daily_loss, 1.0)` otherwise.

---

### ✅ P1-5 — D25 regime detector returns hardcoded labels — FIXED
**File:** [Spyder/SpyderD_Strategies/SpyderD25_UnifiedCreditSpreadEngine.py](Spyder/SpyderD_Strategies/SpyderD25_UnifiedCreditSpreadEngine.py)
- Line 569: `return "bull_trending"  # Example`
- Line 1313: `return "bull_trending"  # Placeholder`

**Consequence:** Credit-spread regime routing is deterministic rather than market-driven. The L09 UnifiedRegimeEngine canonicalization documented in the audit index does not reach D25's direct callers.

**Fix applied:** Both stubs replaced with `engine.current_regime.value` (or `None`). `MarketAnalysisEngine._get_current_regime` (sync) calls `get_unified_regime_engine()`. `UnifiedCreditSpreadEngine._get_current_regime` (async) reads `self.regime_engine.current_regime`.

---

## P2 — Medium severity (tech debt / clarity)

### ✅ P2-1 — Q14 MainLauncher contains dead `_start_live_engine` — FIXED
**File:** [Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py)

**Fix applied:** Entire `_start_live_engine` method body (119 lines, formerly lines 354–472) deleted. `launch_system()` via `SessionSupervisor` remains the sole canonical boot path. Syntax verified clean.

### ✅ P2-2 — R15 PaperBroker `place_order` signature drifts from protocol — FIXED
**File:** [Spyder/SpyderR_Runtime/SpyderR15_PaperBroker.py](Spyder/SpyderR_Runtime/SpyderR15_PaperBroker.py)

**Fix applied:** Signature updated to `(self, symbol: str = "", side: Any = None, quantity: int = 1, order_type: Any = None, limit_price: float | None = None, **kwargs: Any)`. Body updated to prefer explicit params with kwargs fallback.

### ✅ P2-3 — T129 does not test the orchestrator→broker happy path — FIXED
**File:** [Spyder/SpyderT_Testing/SpyderT129_ProtocolCompliance.py](Spyder/SpyderT_Testing/SpyderT129_ProtocolCompliance.py)

**Fix applied:** `EndToEndHappyPathTest(unittest.TestCase)` class appended with 5 tests:
1. `test_paper_broker_place_order_returns_ack`
2. `test_fill_reconciler_tracks_paper_order` (uses `reconciler.tracked_count` property)
3. `test_exit_monitor_sweep_with_registered_position`
4. `test_exit_monitor_orphan_position_emits_event`
5. `test_strategy_orchestrator_instantiates_and_has_registry`

All 12 T129 tests pass (6.01 s).

### ✅ P2-4 — `_NullBroker` silent fallback in R12 — FIXED

**Fix applied:** `_NullBroker.place_order` now emits a `RISK_VIOLATION` event via `get_event_manager()` with `type="NULL_BROKER_ORDER"` and a descriptive message (emit wrapped in bare `except` so it never raises inside a broker call). Returns `{"status": "null_broker"}` — distinguishable from normal responses.

### ✅ P2-5 — PaperBroker fill pricing lacks slippage model — FIXED
**File:** [Spyder/SpyderR_Runtime/SpyderR15_PaperBroker.py](Spyder/SpyderR_Runtime/SpyderR15_PaperBroker.py)

**Fix applied:**
- `slippage_bps: int = 5` added to `PaperBroker.__init__` and `create_paper_broker`.
- `place_order` stores `side` per-order dict.
- `_filled_response` applies `raw_price * (1 ± slippage_bps / 10000)` — buys fill higher, sells lower.
- Default of 5 bps is non-breaking.

---

## New Ideas / Opportunities

### ✅ O-1 — Gate 6: Import smoke test — FIXED
**Fix applied:** `check_module_imports()` added to Q10. Iterates `_SMOKE_TEST_MODULES` (8 key modules), calls `importlib.import_module` on each, prints `OK`/`FAIL` per module. Wired into `main()` after Gate 5.

### ✅ O-2 — Orphan-position drill on every boot — FIXED
**File:** [Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py)

**Fix applied:** `_boot_orphan_sweep()` added; called immediately after `self._running = True` in `start()`. Wraps `self.exit_monitor._sweep_once()` in try/except — failures are logged but never re-raise. Surfaces pre-existing broker positions from before a crash on every restart.

### ✅ O-3 — Runtime invariant: every order-submit must have a reconciler — FIXED
**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py)

**Fix applied:** `_broker_submit` raises `RuntimeError` when `self._reconciler is None and self.mode == TradingMode.LIVE`. Would have surfaced P0-2 at boot rather than silently orphaning orders.

### ✅ O-4 — Structured kill-switch event — FIXED
**Files:** [Spyder/SpyderA_Core/SpyderA05_EventManager.py](Spyder/SpyderA_Core/SpyderA05_EventManager.py), [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py)

**Fix applied:**
- `KILL_SWITCH = "kill_switch"` added to `EventType` enum in A05 under `# System control events`.
- R04 `__init__` subscribes and initialises `self._kill_switch_active: bool = False`.
- `_on_kill_switch` sets the flag and logs `CRITICAL`.
- `_broker_submit` raises `RuntimeError` when `_kill_switch_active` is `True`.
- Any module can now emit `EventType.KILL_SWITCH` for a clean, observable halt.

### ✅ O-5 — Dry-run flag at SessionSupervisor — FIXED
**File:** [Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py)

**Fix applied:**
- `dry_run: bool = False` added to `__init__` and `create_session_supervisor`.
- `start()` logs a prominent `WARNING` when active.
- In paper + dry_run mode, `broker.place_order` is monkey-patched to a no-op returning `{"order": {"id": "DRY-RUN-NOOP"}}` and logging each suppressed call.

### ✅ O-6 — Prometheus counter on P0/P1 paths — FIXED
**Files:** [Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py), [Spyder/SpyderR_Runtime/SpyderR14_ExitMonitor.py](Spyder/SpyderR_Runtime/SpyderR14_ExitMonitor.py)

**Fix applied (all via the existing `_inc_counter` / soft-import pattern):**
- `spyder_orders_submitted_total` — R13 `track()`, each order registered
- `spyder_fills_detected_total` — R13 at `ORDER_FILLED` emit
- `spyder_exits_emitted_total` — R14 `_emit_close_signal()` after each close event
- `spyder_orphans_detected_total` — R14 `_handle_orphan()` on first alert per position

R14 gains `self._prom` soft-import block and `_inc_counter` helper matching R13's pattern.

---

## Suggested Fix Order

1. ✅ **P0-1** (D31 `_initialize_strategy_registry`) — fixed.
2. ✅ **P1-2** (import chain) — fixed: `StrategyOrchestrator(event_manager=None)` instantiates cleanly.
3. ✅ **P0-2** (R12 → fill_reconciler wiring) — fixed.
4. ✅ **P0-3** (R12 → ExitMonitor instantiation) — fixed.
5. ✅ **P1-1** (Q10 Gate 5 strengthening) — fixed.
6. ✅ **P1-3** (E02 collision rename → E24) — fixed.
7. ✅ **P1-4** (real drawdown calc) — fixed.
8. ✅ **P1-5** (regime wiring in D25) — fixed.
9. ✅ **P2-2**, ✅ **P2-4** — fixed in same PR.
10. ✅ **P2-1** — Q14 dead `_start_live_engine` removed.
11. ✅ **P2-3** — T129 `EndToEndHappyPathTest` (5 tests, all pass).
12. ✅ **P2-5** — PaperBroker slippage model added.
13. ✅ **O-1** — Gate 6 added.
14. ✅ **O-2** — Boot-time orphan sweep wired in R12.
15. ✅ **O-3** — `_broker_submit` reconciler guard added.
16. ✅ **O-4** — `EventType.KILL_SWITCH` introduced in A05 + R04.
17. ✅ **O-5** — `dry_run=True` mode in SessionSupervisor.
18. ✅ **O-6** — Prometheus counters extended in R13 and R14.

## Acceptance Criteria for Closing This Audit

| Criterion | Status |
|-----------|--------|
| `python -m Spyder.SpyderQ_Scripts.SpyderQ10_ProtocolComplianceGate` exits 0 | ⏳ Not yet run end-to-end (all prereqs now met) |
| `StrategyOrchestrator(config={}, event_manager=None)` instantiates successfully | ✅ Verified: instantiates cleanly with `available_strategies == {}` |
| 60 s paper-mode run emits ≥1 `ORDER_FILLED` observed by PortfolioManager | ⏳ Not yet run (all wiring in place) |
| ≥1 ExitMonitor sweep completes without error | ⏳ Not yet run (boot sweep wired; T129 sweep test passes) |
| T129 grows by at least the P2-3 integration test | ✅ Done: 5 new tests, 12 total, all pass |
| Q10 Gate 6 (import smoke test) present | ✅ Done |
