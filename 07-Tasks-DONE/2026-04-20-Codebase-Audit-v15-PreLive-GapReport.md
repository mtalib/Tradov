# SPYDER Codebase Audit v15 — Pre-Live Gap Report & Coding Specs

**Date:** 2026-04-20
**Reviewer:** Post-v14 full verification pass on branch `refactor/g05-widget-extraction`.
**Scope:** (1) Re-verify all v14 closure claims. (2) Surface new deficiencies. (3) Improvement opportunities. (4) Line-accurate coding specs.
**Verdict:** **48 h paper soak — still GO. Autonomous live trading — still HOLD.** v14's BLOCKER-class concurrency fixes (A1–A8, A11) are confirmed closed. However this audit surfaces **3 new BLOCKER-class bugs** (two race conditions + one event-routing gap) plus **8 HIGH/MEDIUM operational gaps** that must be closed before capital is at risk.

---

## 1. v14 Closure Re-verification

All v14 findings are confirmed closed on disk unless noted:

| v14 ID | File:line | v15 Status |
|---|---|---|
| A1 | [R04:268-271, 890-910, 1976-1992](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L268) | ✅ `_active_positions_lock` declared + used in `_monitor_positions`, `_emergency_close_all_positions`, `get_active_positions_snapshot` |
| A2 | [R04:1800-1817](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1800) | ✅ `_resolve_order_future` fully locked + idempotent |
| A3 | [R04:1912-1948](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1912) | ✅ `_cancel_all_pending_orders` snapshot+pop+KILL_SWITCH escalation |
| A4 | [R13:491](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py#L491) | ✅ `datetime.now(timezone.utc)` |
| A5 | [B03:175](Spyder/SpyderB_Broker/SpyderB03_PositionTracker.py#L175) | ✅ `datetime.now(timezone.utc)` |
| A6 | [E01:660-690](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L660) | ✅ fill_price validated; SYSTEM_ERROR emitted on 0/None price |
| A7 | [R04:1449-1464](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1449) | ✅ `_on_reconciler_partial_fill` locked |
| A8 | [R04:1915-1946](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1915) | ✅ KILL_SWITCH escalation on partial cancel failure |
| A9 | [R13:123+, 233-269, 382-464](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py#L123) | ✅ `_orphaned` map + slow-poll + `ORDER_UN_ORPHANED` emit |
| A10 | [A05:633-637](Spyder/SpyderA_Core/SpyderA05_EventManager.py#L633) | ✅ `drain_deadline` bounded drain |
| A11 | [R04:1811-1817](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1811) | ✅ `fut.done()` guard before `set_result` |
| A12 | [Q14:370-404](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L370) | ✅ Full live-mode preflight: `CLOSE_POSITIONS_ON_EMERGENCY`, `ACCOUNT_PROFILE`, `MAX_DAILY_LOSS`, `MAX_POSITION_SIZE` |
| A13/O1/O9 | [R05](Spyder/SpyderR_Runtime/SpyderR05_LivenessMonitor.py), [Q24](Spyder/SpyderQ_Scripts/SpyderQ24_ProductionWatchdog.py) | ✅ LivenessMonitor + heartbeat file + /healthz + deadman |
| A14 | [B00:128-139](Spyder/SpyderB_Broker/SpyderB00_OrderTypes.py#L128) | ✅ `_VALID_TRANSITIONS` table + `can_transition()` validator |
| A15 | *(repo-wide)* | ✅ `grep raise NotImplementedError` — only T129 doc string remains |
| A16 | [R04:853-882](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L853) | ✅ `_get_positions_cached()` TTL cache |
| A17 | [B40:86](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L86) | ✅ Single `import functools` |
| A18 | [R04:914](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L914) | ✅ `.total_seconds()` |
| A19 | [R04:561](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L561) | ✅ `order = dict(order)` copy |
| A20 | *(B30, E19)* | ✅ B30 TODO removed; E19 constant `AI_RISK_NEUTRAL_PLACEHOLDER = 0.5` named |
| A21 | [R05](Spyder/SpyderR_Runtime/SpyderR05_LivenessMonitor.py) | ✅ heartbeat file written |
| A22 | [E13:127-141, 877, 1466-1479](Spyder/SpyderE_Risk/SpyderE13_DayProfitTarget.py#L127) | ✅ `Money`/`Decimal` P&L accumulator; fallback to float if U48 absent |
| A23 | *(no code)* | ✅ `close_position_verified()` on B40 + R12 `_flatten_positions` uses it |
| A24 | [E01:298-299](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L298), [R04:328](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L328) | ✅ Both subscribe to A03 config reload |
| A25 | [B40:86](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L86) | ✅ Duplicate import removed |
| A26 | [E19:132](Spyder/SpyderE_Risk/SpyderE19_UnifiedRiskCoordinator.py#L132) | ✅ Named constant |
| O7 | [B40:1057-1096](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L1057) | ✅ `close_position_verified` implemented |
| O10 | [R12:206-234](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L206) | ✅ Phased shutdown with `SHUTDOWN_PHASE_N_*` log markers |

---

## 2. New Findings (v15)

### 2.1 BLOCKER — must close before live

| ID | File:line | Finding |
|---|---|---|
| **B1** | [R04:641-656](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L641) | `cancel_order()` reads `self.pending_orders` and calls `del self.pending_orders[order_id]` **without holding `_pending_orders_lock`**. This public method can be called by a strategy or operator while `_cancel_all_pending_orders` / `_resolve_order_future` is running in the monitor thread — classic TOCTOU: check-then-delete races with concurrent pop → `KeyError`. |
| **B2** | [R04:786-787](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L786) | `_load_current_positions()` performs `self.active_positions = {p["symbol"]: p for p in positions}` — **replaces the dict object entirely** without `_active_positions_lock`. If `_monitor_positions` (monitor thread) holds a reference to the old dict and a caller iterates via `get_active_positions_snapshot()` right as `_load_current_positions` runs on startup, the reference is stale. More importantly, `_emergency_close_all_positions` snapshots `self.active_positions` with the lock; if `_load_current_positions` replaced the object between the lock acquisition and the snapshot, it sees empty positions. |
| **B3** | [D31:382-840](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L382) | `StrategyOrchestrator.active_strategies` dict has **zero locking**. `_orchestration_loop` (background thread) calls `detect_strategy_conflicts()` → `list(self.active_strategies.items())`, `_execute_rebalancing()` → iterates `self.active_strategies`, and `_monitoring_loop` (second background thread) iterates via `_monitor_strategy_health()` and `_update_portfolio_metrics()`. Meanwhile `add_strategy()` writes `self.active_strategies[strategy_id] = strategy` and `remove_strategy()` does `del self.active_strategies[strategy_id]` — no coordination. Concurrent mutation during `for strategy_id, strategy in self.active_strategies.items()` raises `RuntimeError: dictionary changed size during iteration`. This kills the orchestration loop mid-session. |

### 2.2 HIGH — strong preference to close before live

| ID | File:line | Finding |
|---|---|---|
| **B4** | [R04:232-244](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L232) | R13 emits `ORDER_UN_ORPHANED` when an orphaned order recovers to `filled`/`cancelled`. R04 **does not subscribe** to `ORDER_UN_ORPHANED`. The orphan entry sits in `_pending_orders` (if it was registered there) and is never cleared; the associated Future is never resolved; the caller of `execute_order` blocks until the 30 s `ORDER_TIMEOUT_SECONDS` fires and receives `status=timeout` even though the order actually filled. |
| **B5** | [R04:676-681](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L676) | `get_execution_status()` reads `len(self.active_positions)` and `len(self.pending_orders)` without either lock. Called by GUI threads and CLI. In CPython `len()` of a dict is atomic due to the GIL, but `active_positions` can be replaced by a dict-reassignment (`_load_current_positions`) at any time, making the length stale or raising `AttributeError` if the name binding is briefly `None`. Semantically broken on non-CPython runtimes (PyPy). |
| **B6** | [D31:534-540](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L534) | `stop_orchestration()` iterates `self.active_strategies.items()` then calls `strategy.stop()` inside the loop. No lock. If `_orchestration_loop` fires concurrently (it can — `orchestration_active = False` is a plain bool, not atomic), two threads can attempt `strategy.stop()` on the same instance simultaneously. |
| **B7** | [D31:382](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L382) | `paused_strategies: set[str]` is also mutated from `pause_strategy()` (adds) and `resume_strategy()` (discards) while the orchestration/monitoring loops read it without coordination. A `RuntimeError` on `set` iteration is possible on CPython 3.12+ (iteration is no longer GIL-protected for sets in specific scenarios). |
| **B8** | [R04:786](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L786) | `_load_current_positions()` is called during `initialize()` (single-threaded), but is also an obvious candidate for a "refresh on reconnect" call during an API panic recovery. If it is ever called post-start, the dict replacement race (B2) is live. Even if not called post-start today, the method is public with no guard — a future caller will hit it. Add a lock guard **now** as a defensive measure. |

### 2.3 MEDIUM — operational hardening

| ID | File:line | Finding |
|---|---|---|
| **B9** | [R05:232-256](Spyder/SpyderR_Runtime/SpyderR05_LivenessMonitor.py#L232) | Deadman fires once (`_deadman_fired = True`) and is never reset. This is correct by design — but if the LivenessMonitor is stopped and restarted (e.g. via a supervisor restart), `_deadman_fired` persists from the prior run because it is an instance variable that survives the restart if the same object is reused. `create_liveness_monitor` creates a fresh instance, so this is low-probability but worth documenting + adding an explicit reset in `start()`. |
| **B10** | [R12:160-190](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L160) | `SessionSupervisor._start_orchestrator()` passes `OrchestrationMode.ADAPTIVE` and `AllocationMethod.RISK_PARITY` as hard-coded defaults. Neither the mode nor the method is configurable via `.env` / CLI. Operator cannot switch to `CONSERVATIVE` or `FIXED` mode without editing source. |
| **B11** | [Q14:482-500](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L482) | `_launch_headless()` calls `create_session_supervisor()` but does not pass `dry_run` or `skip_orphan_sweep` values from `self.args` through to the `SessionSupervisor`. The CLI flags `--dry-run` and `--skip-orphan-sweep` are parsed by Q14 but silently ignored in the headless path. |
| **B12** | [R04:1867-1874](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1867) | `_execute_stop_loss()` calls `self.broker.close_position(position.get("id", symbol), ...)`. For positions sourced from Tradier, the position `id` is an integer string in the Tradier API response. But `active_positions` stores positions by `symbol` key — if the position dict lacks `"id"`, the fallback is the symbol string, which `close_position()` may not accept (it expects a Tradier position ID or symbol depending on caller). Tradier's `close_position` implementation looks up by symbol anyway, but the ambiguous fallback is fragile. |
| **B13** | [E01:292-305](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L292) | `RiskManager.__init__` tries to register config reload callbacks inside a `try/except`. If `SpyderA03_Configuration` raises during import (missing dep, circular import), the error is silently swallowed. Config hot-reload goes dark without any log at WARNING or above. Should log at ERROR with enough context to diagnose. |

### 2.4 LOW — hygiene

| ID | File:line | Finding |
|---|---|---|
| **B14** | [D31:593-594](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L593) | `add_strategy()` writes `self.active_strategies[strategy_id] = strategy` **before** calling `strategy.start()` (line 624). If `strategy.start()` raises, the entry is already in the dict and will be iterated by the orchestration loop for a strategy that never started. Should do: start first, then register. |
| **B15** | [R12:398-411](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L398) | `_start_orchestrator()` does not add the orchestrator to `self._components`, so it is never stopped by the reverse-shutdown loop. Instead `StrategyOrchestrator.stop_orchestration()` must be called manually. If `stop()` is called without `flatten=True`, the orchestrator threads keep running past broker teardown. |

---

## 3. Gate Status (v15)

| Gate | v14 | v15 | Reason |
|---|---|---|---|
| 48 h paper soak | ✅ GO | ✅ GO | New findings are concurrency bugs that are unlikely to manifest on a single-strategy paper session with no concurrent add/remove calls. |
| Live autonomous | ❌ HOLD | ❌ HOLD | B1–B3 (BLOCKER) + B4–B8 (HIGH) must close. Then a fresh 48 h paper soak on the fixed build. |

**Minimum bar for live GO:** close every BLOCKER (§2.1) and HIGH (§2.2). Re-run `pytest SpyderT_Testing/SpyderT129_ProtocolCompliance.py SpyderT_Testing/SpyderT133_BrokerChaos.py` plus a fresh 48 h paper soak.

---

## 4. Opportunities & New Ideas

| ID | Effort | Idea |
|---|---|---|
| **O1** | SMALL | **`ThreadSafeDict` wrapper** — replace `active_strategies` and `strategy_allocations` in D31 with a thin wrapper that takes an `RLock` on every read and write. Same idea as v14 O6 (applied to R04). Eliminates the entire B3/B6/B7 class. |
| **O2** | SMALL | **Env-driven orchestration mode** — read `ORCHESTRATION_MODE` and `ALLOCATION_METHOD` from `.env` in `_start_orchestrator()`. Enables operator control without code changes. |
| **O3** | SMALL | **`--dry-run` / `--skip-orphan-sweep` pass-through** — wire the already-parsed CLI args from Q14 through to `SessionSupervisor.__init__`. Zero new code needed, just pass them. |
| **O4** | MEDIUM | **Orchestrator component registration** — add `self._components.append(self.orchestrator)` in R12 so the shutdown loop handles it automatically, eliminating B15. |
| **O5** | SMALL | **stop-loss `close_position` consistency** — standardise on `symbol` as the primary key in `_execute_stop_loss()`, matching Tradier's `close_position` implementation. Log the Tradier position ID separately for audit. |
| **O6** | SMALL | **Config callback silent-failure logging** — in E01 and any other module that registers config callbacks inside `try/except`, emit a structured `self.logger.error(...)` with the exception so hot-reload gaps are visible in the log. |
| **O7** | MEDIUM | **Chaos test for D31 concurrent mutations** — add a `SpyderT133` (or extend existing) chaos test that runs `add_strategy`, `remove_strategy`, and `pause_strategy` from concurrent threads for 5 s while the orchestration loop is active, asserting no `RuntimeError`. |
| **O8** | SMALL | **`start()` resets `_deadman_fired`** — one-line defensive fix in R05 so restarts are clean. |

---

## 5. Coding Specs (for the coding agent)

### SPEC-B1 — Lock `cancel_order` fully

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:632-656](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L632)

**Change:** wrap the entire body in `_pending_orders_lock`; use `pop` instead of `del` to prevent `KeyError` on concurrent removal; check membership inside the lock.

```python
def cancel_order(self, order_id: str) -> bool:
    """Cancel a pending order.

    B1 (v15): acquire ``_pending_orders_lock`` for the check-then-delete so
    concurrent terminal-event handlers and ``_cancel_all_pending_orders``
    cannot race against this public API.
    """
    try:
        with self._pending_orders_lock:
            if order_id not in self.pending_orders:
                return False
            # Don't hold the lock across the broker call (can block).
            # Snapshot the entry and pop it optimistically.
            entry = self.pending_orders.pop(order_id)

        result = self.broker.cancel_order(order_id)
        if result:
            self.logger.info("Order %s cancelled", order_id)
        else:
            # Broker rejected cancel — put the entry back.
            with self._pending_orders_lock:
                self.pending_orders.setdefault(order_id, entry)
        return bool(result)

    except Exception as e:
        self.logger.error("Error cancelling order %s: %s", order_id, e)
        return False
```

**Acceptance:** T129 `test_cancel_order_concurrent_with_terminal_event` — fire `cancel_order` and `_cancel_all_pending_orders` concurrently for 1 s, assert no `KeyError` and exactly one cancellation attempt per order.

---

### SPEC-B2 — Guard `_load_current_positions` with lock

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:782-789](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L782)

**Change:** update in-place rather than replacing the dict object, under the lock.

```python
def _load_current_positions(self) -> None:
    """Load current positions from broker.

    B2 (v15): update ``active_positions`` in-place under the lock rather
    than replacing the dict object so concurrent readers always see a
    consistent mapping (not a partially-constructed new dict).
    """
    try:
        positions = self.broker.get_positions()
        new_map = {p["symbol"]: p for p in positions}
        with self._active_positions_lock:
            self.active_positions.clear()
            self.active_positions.update(new_map)
        self.logger.info("Loaded %d active positions", len(new_map))
    except Exception as e:
        self.logger.error("Failed to load positions: %s", e)
```

**Acceptance:** T129 `test_load_positions_concurrent_with_emergency_close` — call `_load_current_positions` and `_emergency_close_all_positions` concurrently for 1 s; assert no `AttributeError`, no lost positions.

---

### SPEC-B3 — Add `_strategies_lock` to `StrategyOrchestrator`

**File:** [Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py)

**Minimal approach (lowest-risk change):** add an `RLock` and guard every access site with a snapshot inside the lock, iterate outside.

**`__init__` addition (after line 382):**
```python
self._strategies_lock = threading.RLock()  # B3 (v15): guard active_strategies + paused_strategies
```

**`add_strategy` (around line 590-625) — start before register:**
```python
# B14 (v15): Start BEFORE registering so a failed start leaves no zombie entry.
if self.orchestration_active:
    strategy.start()

with self._strategies_lock:
    self.active_strategies[strategy_id] = strategy
    self.strategy_allocations[strategy_id] = StrategyAllocation(...)
```

**`remove_strategy` (around line 649-661):**
```python
with self._strategies_lock:
    if strategy_id not in self.active_strategies:
        return False
    strategy = self.active_strategies.pop(strategy_id)
    self.strategy_allocations.pop(strategy_id, None)
    freed_capital = ...
# stop outside lock so broker calls don't block readers
if close_positions:
    strategy.close_all_positions()
strategy.stop()
```

**`pause_strategy` / `resume_strategy`:**
```python
with self._strategies_lock:
    if strategy_id not in self.active_strategies:
        return False
    self.active_strategies[strategy_id].pause()
    self.paused_strategies.add(strategy_id)
```

**`stop_orchestration` iteration:**
```python
self.orchestration_active = False
self.shutdown_event.set()
with self._strategies_lock:
    snapshot = list(self.active_strategies.items())
for strategy_id, strategy in snapshot:
    try:
        strategy.stop()
    except Exception as e:
        self.logger.error(...)
```

**All loop iteration sites** — replace `for ... in self.active_strategies.items()` with:
```python
with self._strategies_lock:
    snapshot = list(self.active_strategies.items())
for strategy_id, strategy in snapshot:
    ...
```

Apply the same snapshot pattern to all reads of `self.paused_strategies`.

**Acceptance:** SpyderT `test_orchestrator_concurrent_add_remove` — 10 threads each add/remove 5 strategies for 3 s while orchestration loop runs; assert no `RuntimeError`, `KeyError`, or `AttributeError`.

---

### SPEC-B4 — Subscribe R04 to `ORDER_UN_ORPHANED`

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:232-258](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L232)

**Change 1 — subscribe in `__init__`:**
```python
self._event_manager.subscribe(EventType.ORDER_UN_ORPHANED, self._on_order_un_orphaned)
```

**Change 2 — add handler:**
```python
def _on_order_un_orphaned(self, event) -> None:
    """B4 (v15): R13 recovered an orphaned order — resolve its Future so
    ``execute_order`` callers don't time out unnecessarily.

    R13 emits ORDER_UN_ORPHANED with the same payload as ORDER_FILLED /
    ORDER_CANCELLED so we can reuse _resolve_order_future.
    """
    data = getattr(event, "data", None) or {}
    order_id = str(data.get("order_id") or "")
    if not order_id:
        return
    # Build a synthetic result so waiting callers unblock cleanly.
    terminal_status = data.get("status", "filled")  # R13 sets "filled" or "cancelled"
    result = {
        "status": terminal_status,
        "order_id": order_id,
        "recovered_from_orphan": True,
        "fill_price": data.get("fill_price"),
        "filled_qty": data.get("filled_qty"),
    }
    with self._pending_orders_lock:
        entry = self.pending_orders.get(order_id)
    order = (entry or {}).get("order", {})
    self._resolve_order_future(order_id, order, result)
    self.logger.info(
        "ORDER_UN_ORPHANED: resolved Future for %s (status=%s)", order_id, terminal_status
    )
```

**Acceptance:** T129 `test_unorphaned_order_resolves_future` — register a pending order, simulate R13 emitting ORDER_UN_ORPHANED, assert Future resolves with `recovered_from_orphan=True` before the 30 s timeout.

---

### SPEC-B5 — Lock reads in `get_execution_status`

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:665-688](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L665)

**Change:**
```python
def get_execution_status(self) -> dict[str, Any]:
    with self._pending_orders_lock:
        pending_count = len(self.pending_orders)
    with self._active_positions_lock:
        positions_count = len(self.active_positions)
    ...
    return {
        ...
        "pending_orders": pending_count,
        "active_positions": positions_count,
        ...
    }
```

**Acceptance:** T129 `test_get_execution_status_thread_safe` — call from 5 threads for 1 s while monitor thread runs; assert no exception.

---

### SPEC-B6 — Stop orchestrator before broker in R12 shutdown

**File:** [Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py:416](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L416)

**Change — in `_start_orchestrator()`, register the orchestrator as a component:**
```python
self.orchestrator.start_orchestration()
self._components.append(self.orchestrator)   # B15 (v15): register so stop() handles teardown
```

Also add a `stop()` method to `StrategyOrchestrator` that aliases `stop_orchestration()` so it satisfies the `_Lifecycle` duck-type:
```python
def stop(self) -> None:
    """B15 (v15): _Lifecycle duck-type required by SessionSupervisor."""
    self.stop_orchestration(graceful=True)
```

**Acceptance:** `test_session_supervisor_stop_calls_orchestrator_stop` — assert `stop_orchestration` is called during `supervisor.stop()`.

---

### SPEC-B7 — Wire CLI args through to SessionSupervisor

**File:** [Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py:482-500](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L482)

**Change:**
```python
from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import create_session_supervisor
self._supervisor = create_session_supervisor(
    mode=self.args.mode,
    dry_run=getattr(self.args, "dry_run", False),          # B11 (v15)
    skip_orphan_sweep=getattr(self.args, "skip_orphan_sweep", False),  # B11
)
```

**Acceptance:** `test_launcher_passes_dry_run_to_supervisor` — mock `create_session_supervisor`, assert it is called with `dry_run=True` when `--dry-run` is passed.

---

### SPEC-B8 — Log config-callback registration failures

**File:** [Spyder/SpyderE_Risk/SpyderE01_RiskManager.py:292-305](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L292)

**Change:**
```python
try:
    cfg_mgr = get_configuration()
    cfg_mgr.register_callback("risk_limits.*", self._on_config_reload)
    cfg_mgr.register_callback("risk.*", self._on_config_reload)
    self.logger.info("E01: config reload callbacks registered")
except Exception as exc:
    self.logger.error(            # B13 (v15): was silent; now visible
        "E01: failed to register config reload callbacks — hot-reload DISABLED: %s", exc
    )
```

Apply the same pattern everywhere `register_callback` is called inside a bare `try/except`.

**Acceptance:** unit test `test_e01_logs_config_callback_failure` — mock A03 to raise, assert `logger.error` is called with text containing `hot-reload DISABLED`.

---

### SPEC-B9 — Start strategy before registering in D31 `add_strategy`

**File:** [Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py:590-626](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L590)

**Change (covered by SPEC-B3, but explicit here for clarity):** move `strategy.start()` to before the `with self._strategies_lock: self.active_strategies[strategy_id] = strategy` line. If `strategy.start()` raises, the except block re-raises without ever touching `active_strategies`.

**Acceptance:** `test_add_strategy_start_failure_leaves_no_zombie` — mock `strategy.start()` to raise; assert `strategy_id` is not present in `active_strategies` after the exception.

---

### SPEC-B10 — Env-driven orchestration mode

**File:** [Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py:416-435](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L416)

**Change:**
```python
_mode_map = {
    "adaptive": OrchestrationMode.ADAPTIVE,
    "conservative": OrchestrationMode.CONSERVATIVE,
    "aggressive": OrchestrationMode.AGGRESSIVE,
    "fixed": OrchestrationMode.FIXED,
}
_alloc_map = {
    "risk_parity": AllocationMethod.RISK_PARITY,
    "equal_weight": AllocationMethod.EQUAL_WEIGHT,
    "fixed": AllocationMethod.FIXED,
}
orch_mode = _mode_map.get(
    os.environ.get("ORCHESTRATION_MODE", "adaptive").lower(),
    OrchestrationMode.ADAPTIVE,
)
alloc_method = _alloc_map.get(
    os.environ.get("ALLOCATION_METHOD", "risk_parity").lower(),
    AllocationMethod.RISK_PARITY,
)
self.orchestrator = StrategyOrchestrator(
    base_capital=base_capital,
    orchestration_mode=orch_mode,
    allocation_method=alloc_method,
    event_manager=self.em,
)
```

**Acceptance:** unit test passes with `ORCHESTRATION_MODE=conservative` and asserts `orchestrator.orchestration_mode == OrchestrationMode.CONSERVATIVE`.

---

## 6. Summary Priority Table

| ID | Class | Component | One-line description |
|---|---|---|---|
| B1 | BLOCKER | R04 | `cancel_order` reads/deletes `pending_orders` without lock |
| B2 | BLOCKER | R04 | `_load_current_positions` replaces dict object without lock |
| B3 | BLOCKER | D31 | `active_strategies` / `paused_strategies` have zero locking |
| B4 | HIGH | R04 | No subscriber for `ORDER_UN_ORPHANED` → callers time out |
| B5 | HIGH | R04 | `get_execution_status` reads dicts without locks |
| B6 | HIGH | D31 | `stop_orchestration` iterates without lock |
| B7 | HIGH | D31 | `paused_strategies` set mutated from multiple threads |
| B8 | HIGH | R04 | `_load_current_positions` post-start call race (defensive) |
| B9 | MEDIUM | R05 | `_deadman_fired` not reset on `start()` restart |
| B10 | MEDIUM | R12 | Orchestration mode hard-coded; not env-driven |
| B11 | MEDIUM | Q14 | `--dry-run`/`--skip-orphan-sweep` not passed to supervisor |
| B12 | MEDIUM | R04 | `_execute_stop_loss` ambiguous position ID fallback |
| B13 | MEDIUM | E01 | Config callback registration failure silently swallowed |
| B14 | LOW | D31 | Strategy registered before started (zombie on start failure) |
| B15 | LOW | R12 | Orchestrator not in `_components`; not auto-stopped |
