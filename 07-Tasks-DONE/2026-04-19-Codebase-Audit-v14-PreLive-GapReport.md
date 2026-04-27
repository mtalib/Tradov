# SPYDER Codebase Audit v14 — Pre-Live GoLive Gap Report & Coding Specs

**Date:** 2026-04-19
**Reviewer:** Post-v13 verification pass on branch `refactor/g05-widget-extraction`.
**Scope:** (1) Re-verify v13 closure claims. (2) Surface *new* deficiencies not listed in v12/v13. (3) Propose improvement opportunities. (4) Give the coding agent line-accurate specs to close each new gap.
**Verdict:** **48 h paper soak on the live launcher path — still GO. Autonomous live trading — still HOLD.** v13's emergency-path closures hold up under re-verification, but this audit surfaces **6 new BLOCKER-class concurrency and datetime bugs** plus **9 HIGH-class operational gaps** that must close before capital is at risk.

---

## 1. v13 Closure Re-verification (all confirmed)

All v13 "closed" items still match the code on disk:

| ID | File:line | Status |
|---|---|---|
| B1 | [R15:290](Spyder/SpyderR_Runtime/SpyderR15_PaperBroker.py#L290) | ✅ `close_position()` present and protocol-aligned |
| B2 | [Q14:536,548](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L536) | ✅ Shared `_safe_stop_supervisor()` on all exit paths |
| B3 | [B40:2119](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L2119) | ✅ `tag` param forwarded in async wrapper |
| B4 | [R04:262](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L262) | ⚠️ Lock **declared** but **not used everywhere** — see A1/A2/A5/A15/A21 below |
| B5 | [D31:1715,1745](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L1715) | ✅ `DATA_FRESH` resume wired |
| N1 | [R04:1390](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1390), [Q14:368](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L368) | ✅ Kill-lock file + launcher gate |
| N2 | [R04:1520,1645](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1520) | ✅ `record_api_server_error()` on transient faults |
| N3 | [R13:385](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py#L385), [R04:253](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L253) | ✅ `ORDER_ORPHANED` emit + subscriber |
| P1-12 | [A05:782-787](Spyder/SpyderA_Core/SpyderA05_EventManager.py#L782) | ✅ Handler circuit-break after 3 consecutive errors — **reclassify v13 N-list as closed** |

**Action for v14:** B4 is the most important false-positive. The lock object exists but is used only in 3 of the ~10 pending_orders access sites; gaps listed below as A1/A2/A5/A15/A21.

---

## 2. New Findings (not in v12/v13)

### 2.1 BLOCKER — must close before live

| ID | File:line | Finding |
|---|---|---|
| **A1** | [R04:786](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L786), [R04:1799](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1799) | `active_positions` dict is mutated by `_monitor_positions()` **and** `_emergency_close_all_positions()` with **no lock at all**. B4's lock is `pending_orders`-only; `active_positions` has none. Grep confirms: only 2 mutation sites, both unguarded. |
| **A2** | [R04:1652-1662](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1652) | `_resolve_order_future()` reads then writes `self.pending_orders` **outside** `_pending_orders_lock`. B4 added the lock at registration (line 529) and GC (line 1735) but the hot-path fill callback skipped it. Race: fill callback and emergency cancel can both mutate entry simultaneously. |
| **A3** | [R04:1763-1772](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1763) | `_cancel_all_pending_orders()` iterates `list(pending_orders.keys())` then `del self.pending_orders[order_id]` outside the lock. If broker.cancel_order() is slow, a concurrent terminal-event handler may pop the same key first → `KeyError`, emergency cancel partially runs, **some orders remain pending**. |
| **A4** | [R13:376](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py#L376) | `datetime.utcnow().isoformat() + "Z"` — naive UTC string. Violates the Q10 production gate for `datetime.utcnow()`. Orphan dead-letter timestamps will diverge from everything else in the system (tz-aware ET). Audit-trail correlation silently breaks. |
| **A5** | [B03:175](Spyder/SpyderB_Broker/SpyderB03_PositionTracker.py#L175) | Same naive UTC bug inside `PositionTracker.save_state()`. Persisted position snapshot is load-tz-ambiguous; restart reconciliation cannot reliably age-out state. |
| **A6** | [E01:621,623](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L621) | `float(data.get("fill_price") or 0.0)` silently substitutes **$0.00 as average_fill_price** when a fill event lacks a price. A 0-price position makes unrealized P&L on a $5 credit spread look like +$500 per contract — **risk limits bypass undetected**. |

**Why these are BLOCKERs for autonomous live:** A1–A3 can corrupt order state during a panic shutdown (the exact window where you need reliability most). A4/A5 break the v3-audit timezone invariant the Q10 gate was meant to enforce. A6 can trick E11 `MaxLossProtection` / E13 `DayProfitTarget` into allowing unbounded position accumulation.

### 2.2 HIGH — strong preference to close before live

| ID | File:line | Finding |
|---|---|---|
| **A7** | [R04:1326-1328](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1326) | `_on_reconciler_partial_fill` reads `pending_orders` outside lock. Check-then-act pattern for metrics increment; race with terminal-event handler pops the key mid-check. |
| **A8** | [R04:1763-1772](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1763) | `_cancel_all_pending_orders()` does not track which cancellations failed. A broker 5xx on one order is logged but the order stays flagged "pending internally" with no retry → on process restart the kill-lock exists but the orphan detector has no record. |
| **A9** | [R13:220-264](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py#L220) | Once an order hits `MAX_CONSECUTIVE_ERRORS` and is `_drop()`ped from `_tracked`, there is **no path back**. If the broker recovers, the real fill event is never re-emitted and the position is orphaned forever in the reconciler's view. |
| **A10** | [A05:630-637](Spyder/SpyderA_Core/SpyderA05_EventManager.py#L630) | `event_queue.join()` has **no timeout**. If a worker thread is wedged (e.g. holding a broker HTTP socket in a 30 s read), `EventManager.stop()` hangs forever → launcher cannot write the kill-lock on panic. |
| **A11** | [R04:1654-1662](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1654) | No idempotency guard on `fut.set_result()`: if the fill callback fires twice (it can — async retry + sync callback), the second `set_result` raises `InvalidStateError`, currently swallowed silently; metrics skew. |
| **A12** | [Q14](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py) | `TRADIER_API_KEY`/`TRADIER_ACCOUNT_ID` are enforced at Q14:358-365 for live mode, but there is **no preflight check** for `CLOSE_POSITIONS_ON_EMERGENCY`, `ACCOUNT_PROFILE`, `MAX_DAILY_LOSS`, etc. Operator can launch live with emergency-close disabled and never know. |
| **A13** | *(no heartbeat file in repo)* | **Dead-bot detection missing.** `grep heartbeat_file|watchdog_ping` returns 0 hits. Q70_Watchdog.service exists but nothing writes a liveness file for an external observer. If the bot wedges with positions open, nobody notices for hours. |
| **A14** | [B00:81+](Spyder/SpyderB_Broker/SpyderB00_OrderTypes.py#L81) | `OrderStatus` is a plain enum — **no transition legality table**. Nothing prevents `FILLED → SUBMITTED`, `CANCELLED → FILLED`, etc. Under a broker replay or double-event scenario this corrupts the state machine silently. (v13 N5 still open.) |
| **A15** | [R11:259,303](Spyder/SpyderR_Runtime/SpyderR11_PaperStrategyRunner.py#L259), [L16:309+](Spyder/SpyderL_ML/SpyderL16_OptionsAdjustmentRL.py#L309) | 8 × `raise NotImplementedError` in code paths reachable from live/paper runners. Carried over from the April 14 v3 audit as still-open L16 RL stubs. If any code path in D31 probes the RL adjustment methods, the engine dies. |

### 2.3 MEDIUM — operational hardening

| ID | File:line | Finding |
|---|---|---|
| **A16** | [R04:775](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L775) | `_monitor_positions()` calls `self.broker.get_positions()` on every 1 s tick with no caching/backoff. Risk: Tradier rate-limit at 60/min is burnt entirely by monitoring alone; no budget for order placement. |
| **A17** | [B40:86-87](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L86) | `import functools` appears on two consecutive lines. Cosmetic but symptomatic of conflict-merge residue. |
| **A18** | [R04:791-803](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L791) | Heartbeat checker uses `(now - last_heartbeat).seconds` — the `.seconds` attr loses sign and day-overflow information; a clock skew or day-boundary tick produces wildly wrong deltas. Use `.total_seconds()`. |
| **A19** | [R04:522,534](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L522) | `order["timestamp"]` **mutates the caller's dict** inside `execute_order()`. If the strategy retains the order for logging, it sees the engine-injected timestamp and not its own. Use a copy. |
| **A20** | [B30:878](Spyder/SpyderB_Broker/SpyderB30_SPYOptionsChainManager.py#L878), [E19:697](Spyder/SpyderE_Risk/SpyderE19_UnifiedRiskCoordinator.py#L697) | `TODO: Reinitialize with new expiration` in the options-chain cache invalidation path; `ai_risk_score: 0.5 # neutral placeholder` in unified risk coordinator. Both reachable from live. |
| **A21** | *(search confirmed)* | No `heartbeat_file` / external liveness ping. v13 N6 still open. |
| **A22** | [E01:621,623](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L621) | P&L accumulation uses `float` throughout. Over 100+ trades, sub-cent rounding drift can cause E13 `DayProfitTarget` to trigger 1–3 ¢ off its configured limit. Use `decimal.Decimal` at the P&L boundary. |
| **A23** | *(no code)* | No central `OrderStatus` transition validator; each component decides what legal means. |
| **A24** | *(no code)* | No runtime config **push** path. A03 has `reload()` and callbacks, but R04/E01 do not subscribe — hot-reload is half-wired. v13 N4 still open. |

### 2.4 LOW — style/hygiene

| ID | File:line | Finding |
|---|---|---|
| **A25** | [B40:86-87](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L86) | Duplicate `import functools`. |
| **A26** | [E19:697](Spyder/SpyderE_Risk/SpyderE19_UnifiedRiskCoordinator.py#L697) | Hardcoded `0.5` neutral placeholder — at minimum rename to a named constant and document the assumption. |

---

## 3. Opportunities & New Ideas

| ID | Effort | Idea |
|---|---|---|
| **O1** | SMALL | Add a read-only `/healthz` HTTP endpoint on the SessionSupervisor exposing: kill-switch state, broker connected, reconciler tracked count, last event-loop tick ts. Watchdog can scrape instead of guessing from logs. |
| **O2** | MEDIUM | Build a **paper-vs-live parity harness**: replay a canned Tradier event stream against both `R15 PaperBroker` and a mocked `B40 TradierClient`, assert same `ORDER_*` event sequence. Catches protocol drift (v12's B1/B3) at CI time. |
| **O3** | MEDIUM | Add a **broker-fault chaos harness** (T* test): inject 5xx bursts, TCP resets, delayed fills, double-fill events; assert no crash, no double-position, kill-switch triggers at expected thresholds. Makes P2 resiliency tasks testable. |
| **O4** | SMALL | Wrap all P&L math in a `Money` type (internally `Decimal` scaled to ¢). Single place to enforce rounding. Kills A22 class of bugs permanently. |
| **O5** | SMALL | Add a **correlation_id** column to every event payload (strategy_signal → order_id → broker_order_id → fill → position update). Already half-implemented in U43; finish the chain so one grep explains any trade end-to-end. |
| **O6** | SMALL | Replace `self.active_positions` **and** `self.pending_orders` with a thin `ThreadSafeDict` wrapper that takes the lock automatically. Eliminates the entire class of "forgot the lock" bugs (A1–A3, A7). |
| **O7** | SMALL | `close_position_verified()` on the broker protocol: submit the close, then poll fills until confirmed within N seconds, else re-submit or emit KILL_SWITCH. Closes v13 N10. |
| **O8** | MEDIUM | Weekly scheduled **soak test cron** (cron + GitHub Actions runner): 48 h paper loop with synthetic market-data replay, posts pass/fail to a dashboard. Pre-live gate becomes automatic. |
| **O9** | SMALL | **Deadman timer**: if `EventManager._process_events()` doesn't process an event in N seconds during market hours, emit KILL_SWITCH. Catches wedged event bus that A10 can cause. |
| **O10** | SMALL | Add a **structured shutdown sequence** to SessionSupervisor with explicit phases: (1) stop new orders, (2) cancel pending, (3) flatten positions, (4) stop threads, (5) persist state, (6) write kill-lock. Today these are intermixed and order is implicit. |

---

## 4. Gate Status (v14)

| Gate | v13 | v14 | Reason |
|---|---|---|---|
| 48 h paper soak | ✅ GO | ✅ GO | v13 closures hold; new findings don't impair paper. |
| Live autonomous | ❌ HOLD | ❌ HOLD | A1–A6 (BLOCKER) must close; then A7–A15 before first live session. |

**Minimum bar for live GO:** close every BLOCKER (§2.1) and HIGH (§2.2), plus complete a fresh 48 h paper soak on the *post-fix* build.

---

## 5. Coding Specs (for the coding agent)

Each spec is self-contained: file:line target, exact change, acceptance test. Fix order matches risk-weighted priority.

### SPEC-A1 — Add `_active_positions_lock` and guard all access

**Files:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py)
**Sites:** __init__ (~line 263), [`_monitor_positions`:786](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L786), [`_emergency_close_all_positions`:1785-1805](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1785), [`_load_current_positions`](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py) (whatever line assigns the dict).

**Change:**
```python
# __init__
self.active_positions: dict[str, Any] = {}
self._active_positions_lock = threading.RLock()  # A1

# _monitor_positions (line 775ff)
positions = self.broker.get_positions()
new_syms = {p["symbol"] for p in positions}
with self._active_positions_lock:
    # Purge symbols the broker no longer reports (handles stale-state leak)
    for stale_sym in set(self.active_positions) - new_syms:
        self.active_positions.pop(stale_sym, None)
    for position in positions:
        if self._should_trigger_stop_loss(position):
            self._execute_stop_loss(position)
        self.active_positions[position["symbol"]] = position

# _emergency_close_all_positions
with self._active_positions_lock:
    symbols = list(self.active_positions.keys())
# ... iterate outside the lock so broker.close_position() doesn't block readers
```

**Acceptance:**
- New T129 test: `test_monitor_and_emergency_close_are_thread_safe` — run both in parallel for 1 s, assert no `KeyError`, no lost positions.
- Grep gate: `active_positions\[` not appearing outside a `with self._active_positions_lock:` block.

---

### SPEC-A2 — Lock `_resolve_order_future` fully

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:1652-1662](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1652)

**Change:**
```python
def _resolve_order_future(self, order_id: str, order: dict[str, Any], result: dict[str, Any]) -> None:
    """Store result in pending_orders and signal the associated Future."""
    with self._pending_orders_lock:  # A2
        entry = self.pending_orders.get(order_id)
        if entry is None:
            self.pending_orders[order_id] = {"order": order, "result": result}
            return
        entry["result"] = result
        fut = entry.get("future")
    # Setting Future result outside lock is safe and avoids holding lock
    # across user callbacks.
    if fut is not None and not fut.done():  # A11 — idempotency guard
        try:
            fut.set_result(result)
        except concurrent.futures.InvalidStateError:
            self.logger.warning("Future already resolved for order %s", order_id)
```

**Acceptance:** T129 test `test_resolve_order_future_idempotent`: call twice concurrently, assert no exception, result unchanged.

---

### SPEC-A3 — Safe cancel-all-pending with failure tracking

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:1763-1772](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1763)

**Change:**
```python
def _cancel_all_pending_orders(self) -> list[str]:
    """Cancel every pending order via the broker.

    Returns the list of order_ids that failed to cancel so callers can
    decide whether to escalate (A8).
    """
    with self._pending_orders_lock:
        order_ids = list(self.pending_orders.keys())

    failed: list[str] = []
    for order_id in order_ids:
        try:
            self.broker.cancel_order(order_id)
        except Exception as exc:
            self.logger.error("Failed to cancel order %s: %s", order_id, exc, exc_info=True)
            failed.append(order_id)
            continue
        with self._pending_orders_lock:
            self.pending_orders.pop(order_id, None)  # A3: pop, not del
        self.logger.info("Cancelled pending order %s", order_id)

    if failed:
        self.logger.critical("Cancel-all left %d orders uncancelled: %s", len(failed), failed)
        # Escalate: failed cancellations during emergency = KILL_SWITCH
        self._event_manager.emit(
            EventType.KILL_SWITCH,
            {"reason": "cancel_all_partial_failure", "failed_order_ids": failed},
            source="LiveEngine",
        )
    return failed
```

Also update [line 1327](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1327) (`_on_reconciler_partial_fill`) to take the lock for its check.

**Acceptance:** T129 `test_cancel_all_escalates_on_partial_failure`: mock broker raising on 1/3 orders, assert KILL_SWITCH fires with correct `failed_order_ids`.

---

### SPEC-A4 + A5 — Eliminate remaining `datetime.utcnow()` in prod

**Files:**
- [Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py:376](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py#L376)
- [Spyder/SpyderB_Broker/SpyderB03_PositionTracker.py:175](Spyder/SpyderB_Broker/SpyderB03_PositionTracker.py#L175)

**Change (both):** replace `datetime.utcnow().isoformat() + "Z"` with `datetime.now(timezone.utc).isoformat()`. Add `from datetime import timezone` if missing.

**Acceptance:** Q10 `ProtocolComplianceGate` passes Gate 3 with zero exceptions; `grep datetime.utcnow()` returns only Q10 itself.

---

### SPEC-A6 — Reject fills without a valid price

**File:** [Spyder/SpyderE_Risk/SpyderE01_RiskManager.py:618-626](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L618)

**Change:**
```python
fill_price = data.get("fill_price")
if fill_price is None or float(fill_price) <= 0.0:
    self.logger.error(
        "_on_position_updated: rejecting fill for %s with invalid price %r",
        symbol, fill_price,
    )
    self._emit_system_error("risk_manager", f"invalid fill_price for {symbol}")
    return
fp = float(fill_price)
self._positions[symbol] = Position(
    symbol=symbol,
    quantity=int(qty),
    market_price=fp,
    market_value=fp * int(qty) * 100.0,  # options multiplier
    average_fill_price=fp,
    unrealized_pnl=0.0,
    realized_pnl=0.0,
)
```

Apply the same check in the `existing` branch (line 615) for `market_price` updates.

**Acceptance:** T129 `test_risk_rejects_zero_fill_price`: emit ORDER_FILLED with `fill_price=0`, assert no position created and `SYSTEM_ERROR` emitted.

---

### SPEC-A7 — Lock `_on_reconciler_partial_fill` check

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:1322-1328](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1322)

**Change:**
```python
def _on_reconciler_partial_fill(self, event) -> None:
    if getattr(event, "source", None) != "FillReconciler":
        return
    order_id = (event.data or {}).get("order_id")
    if not order_id:
        return
    with self._pending_orders_lock:
        if order_id in self.pending_orders:
            self.metrics.successful_executions += 1
```

---

### SPEC-A9 — Recover from orphaned → healthy transitions

**File:** [Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py)

**Change:** don't `_drop()` on orphan — move the entry to an `_orphaned` map with a longer probe cadence (e.g. 60 s). If a subsequent probe returns a terminal status, emit the real `ORDER_FILLED`/`ORDER_CANCELLED` and drop *then*. Also emit a `ORDER_UN_ORPHANED` event so R04 can clear the orphan flag on the entry.

**Acceptance:** T129 `test_orphan_recovers_to_filled`: inject 8 consecutive errors then a `filled` response, assert `ORDER_FILLED` is emitted exactly once.

---

### SPEC-A10 — Bounded queue drain on EventManager stop

**File:** [Spyder/SpyderA_Core/SpyderA05_EventManager.py:629-637](Spyder/SpyderA_Core/SpyderA05_EventManager.py#L629)

**Change:**
```python
# A10: Bounded drain — do not join() without a deadline.
drain_deadline = time.monotonic() + min(timeout, 2.0)
for q in (self.event_queue, self.priority_queue,
          self._persist_queue if self.persist_events else None):
    if q is None:
        continue
    while not q.empty() and time.monotonic() < drain_deadline:
        try:
            q.get_nowait()
            q.task_done()
        except queue.Empty:
            break
    remaining = q.qsize()
    if remaining:
        self.logger.warning("EventManager.stop: %d events dropped from %s on timeout",
                            remaining, type(q).__name__)
```

**Acceptance:** T129 `test_event_manager_stop_bounded`: enqueue 1M events with a slow handler, assert `stop(timeout=2)` returns within 3 s.

---

### SPEC-A12 — Extended preflight check for live mode

**File:** [Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py:355-400](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L355)

**Change:** after credential check, add a block that validates all live-critical env vars and config values. Fail fast:

```python
LIVE_REQUIRED = {
    "CLOSE_POSITIONS_ON_EMERGENCY": ("true", "emergency stop will NOT flatten"),
    "MAX_DAILY_LOSS": (None, "day-loss kill-switch needs a bound"),
    "MAX_POSITION_SIZE": (None, "un-bounded position sizing"),
    "ACCOUNT_PROFILE": ("live", "mode is live but profile is not"),
}
violations = []
for var, (expected, msg) in LIVE_REQUIRED.items():
    val = os.environ.get(var)
    if val is None or (expected is not None and val.lower() != expected):
        violations.append(f"{var}={val!r}: {msg}")
if violations:
    self.log_error("❌ Live preflight failed:\n  - " + "\n  - ".join(violations))
    return False
```

**Acceptance:** Q14 unit test `test_live_preflight_rejects_missing_emergency_close`.

---

### SPEC-A13 + O1 + O9 — Liveness heartbeat + /healthz + deadman

**New file:** `Spyder/SpyderR_Runtime/SpyderR05_LivenessMonitor.py`

**Behavior:**
1. Spawn a thread in `SessionSupervisor.start()` that writes `~/.spyder_heartbeat` every 2 s with `{ts, kill_switch, broker_connected, pending_orders_count, tracked_orders_count, last_event_processed_ts}`.
2. Expose the same payload at `http://127.0.0.1:$SPYDER_HEALTHZ_PORT/healthz` (default 9876, loopback only).
3. Deadman: if `(now - last_event_processed_ts) > DEADMAN_SECONDS` during market hours, emit `EventType.KILL_SWITCH` with reason `deadman`.
4. `Q24_ProductionWatchdog.py` reads `~/.spyder_heartbeat` and restarts / alerts if stale > 30 s.

**Acceptance:** T129 `test_deadman_fires_when_event_loop_wedged`: mock last_event_ts to `now - 120 s`, assert KILL_SWITCH fires.

---

### SPEC-A14 — Order state transition validator

**File:** [Spyder/SpyderB_Broker/SpyderB00_OrderTypes.py](Spyder/SpyderB_Broker/SpyderB00_OrderTypes.py)

**Change:** Add a class-level `_VALID_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]]` and a `validate_transition(src, dst) -> bool` staticmethod. Callers that update `order.status` must route through a helper `order.transition_to(new_status)` that raises `IllegalOrderTransition` on violation. All internal state changes must go through this path.

**Transitions to allow:**
```
PENDING      → {SUBMITTED, REJECTED, CANCELLED}
SUBMITTED    → {ACCEPTED, REJECTED, CANCELLED}
ACCEPTED     → {PARTIALLY_FILLED, FILLED, CANCELLED, EXPIRED}
PARTIALLY_FILLED → {FILLED, CANCELLED, EXPIRED}
FILLED, REJECTED, CANCELLED, EXPIRED → {} (terminal)
```

**Acceptance:** T129 parametrised test covers all 24 transitions.

---

### SPEC-A15 — Close or gate the L16/R11 NotImplementedError stubs

**Files:**
- [Spyder/SpyderR_Runtime/SpyderR11_PaperStrategyRunner.py:259,303](Spyder/SpyderR_Runtime/SpyderR11_PaperStrategyRunner.py#L259)
- [Spyder/SpyderL_ML/SpyderL16_OptionsAdjustmentRL.py:309-477](Spyder/SpyderL_ML/SpyderL16_OptionsAdjustmentRL.py#L309)

**Change:** Either (a) provide a safe no-op default that logs "RL adjustment disabled — feature flag off" and returns `None`, *and* gate the call sites with `if not self.config.rl_enabled: return`, or (b) remove the dead entry points entirely. Do not ship live code that can raise `NotImplementedError` in a hot path.

**Acceptance:** `grep NotImplementedError Spyder/Spyder[DEHLRS]*` returns zero hits in runtime-reachable files.

---

### SPEC-A16 — Cache broker.get_positions in the monitor loop

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:771-789](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L771)

**Change:** add TTL cache (5 s default) on `broker.get_positions()`; invalidate on any `ORDER_FILLED`/`POSITION_UPDATED` event.

**Acceptance:** load test — 600 monitor ticks/min yields ≤ 12 broker calls.

---

### SPEC-A18 — `.total_seconds()` in heartbeat delta

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:794](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L794)

**Change:** `if (now - self.last_heartbeat).total_seconds() > HEARTBEAT_INTERVAL:`

---

### SPEC-A19 — Don't mutate caller's order dict

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:521-536](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L521)

**Change:** copy before stamping: `order = dict(order)`; `order["timestamp"] = datetime.now(_ET)`; …

**Acceptance:** T129 `test_execute_order_does_not_mutate_input`.

---

### SPEC-A20 — Close the production TODOs

**Files:**
- [Spyder/SpyderB_Broker/SpyderB30_SPYOptionsChainManager.py:878](Spyder/SpyderB_Broker/SpyderB30_SPYOptionsChainManager.py#L878) — implement the expiration-roll init; add a T129 test covering Monday-after-expiry.
- [Spyder/SpyderE_Risk/SpyderE19_UnifiedRiskCoordinator.py:697](Spyder/SpyderE_Risk/SpyderE19_UnifiedRiskCoordinator.py#L697) — either wire to X04 model or gate behind `if self.config.ai_risk_enabled`; do not ship a silent hardcoded `0.5`.

---

### SPEC-A22 + O4 — `Money` Decimal wrapper for P&L

**New file:** `Spyder/SpyderU_Utilities/SpyderU44_Money.py`

**Behavior:** thin wrapper around `decimal.Decimal` with cents-scaled int representation, `__add__/__sub__/__mul__` returning `Money`, `.to_float()` for display boundaries only. Replace float P&L fields on `Position`, `RiskMetrics`, `DayProfitTarget` with `Money`.

**Acceptance:** E13 day-loss test comparing float vs. Decimal over 10 000 synthetic fills shows the Decimal path stays within ≤ 1 ¢ of the analytical total; float path drifts ≥ 10 ¢.

---

### SPEC-A23 + O7 — `close_position_verified` on BrokerProtocol

**File:** [Spyder/SpyderB_Broker/SpyderB21_BrokerProtocol.py](Spyder/SpyderB_Broker/SpyderB21_BrokerProtocol.py)

**Change:** Add `close_position_verified(symbol, timeout_s=10) -> dict` that (1) submits the close, (2) awaits a `ORDER_FILLED` for that `broker_order_id` via a local Future, (3) returns `{"status": "verified", "fill_price": ...}` or `{"status": "unverified", ...}`. On unverified, emit `KILL_SWITCH`.

Update `R15 PaperBroker` and `B40 TradierClient` implementations. `SessionSupervisor._flatten_positions` must call the verified variant.

---

### SPEC-A24 — Push config changes to live components

**Files:** [Spyder/SpyderA_Core/SpyderA03_Configuration.py:1077-1085](Spyder/SpyderA_Core/SpyderA03_Configuration.py#L1077), `R04`, `E01`.

**Change:** R04 and E01 each register a `register_reload_callback("*")` on init that re-reads the fields they actually care about (risk limits, timeouts, profile). Add `reload_config_safe()` on each that logs which fields changed. Deny reload of structural fields (account_id, env) — require restart.

**Acceptance:** T129 `test_risk_manager_hot_reload_updates_max_daily_loss`.

---

### SPEC-O2 — Paper/live protocol parity harness

**New file:** `Spyder/SpyderT_Testing/SpyderT130_BrokerProtocolParity.py`

**Behavior:** canned sequence of 30 `{method, args, kwargs}` tuples. For each, call on both `R15 PaperBroker` and a mocked `B40 TradierClient` (with deterministic fake responses). Assert returned shapes match (same keys, same types). Run as part of Q10 gate.

---

### SPEC-O10 — Ordered shutdown sequence

**File:** `Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py`

**Change:** Formalise `stop(flatten=bool)` as an explicit pipeline:

```python
def stop(self, flatten: bool) -> None:
    phases = [
        ("halt_new_orders",  lambda: self.engine.set_state(ExecutionState.HALTED)),
        ("cancel_pending",   lambda: self.engine._cancel_all_pending_orders()),
        ("flatten_positions", lambda: self.engine._emergency_close_all_positions()) if flatten else None,
        ("stop_reconciler",  lambda: self.reconciler.stop()),
        ("stop_event_mgr",   lambda: self.event_manager.stop(timeout=3.0)),
        ("persist_state",    lambda: self.position_tracker.save_state()),
    ]
    for name, fn in filter(None, phases):
        try:
            fn()
            self.logger.info("shutdown phase %s OK", name)
        except Exception as exc:
            self.logger.critical("shutdown phase %s failed: %s", name, exc, exc_info=True)
```

**Acceptance:** log inspection in paper-soak test confirms strict ordering.

---

## 6. v14 → v15 Acceptance Criteria

A v15 "GO for live" must demonstrate:

1. All §2.1 (BLOCKER) specs merged; Q10 + T129 green.
2. All §2.2 (HIGH) specs merged.
3. **Fresh 48 h paper soak** on post-fix build: zero unhandled exceptions, zero stuck `pending_orders`, zero stuck `active_positions`, clean ordered shutdown.
4. **New chaos-harness test** (SPEC-O3) passing.
5. **Heartbeat file** (SPEC-A13) observed by an external watchdog for the whole soak.
6. **Zero** `datetime.utcnow()` hits in production code (Q10 Gate 3 clean, no exceptions).
7. **Zero** runtime-reachable `NotImplementedError` (grep gate).

---

## 7. Recommended Fix Order

1. **Day 1** — SPEC-A1, A2, A3, A7, A11 (concurrency, single session, single PR).
2. **Day 1** — SPEC-A4, A5 (datetime, trivial).
3. **Day 2** — SPEC-A6, A19, A18 (risk & order hygiene).
4. **Day 2** — SPEC-A12 (launcher preflight).
5. **Day 3** — SPEC-A10, A15, A20 (event manager, stubs, TODOs).
6. **Day 4** — SPEC-A13/O1/O9 (liveness + /healthz + deadman).
7. **Day 5** — SPEC-A14, A23/O7, A24 (state machine, verified close, hot-reload).
8. **Day 6** — SPEC-A9, A22/O4 (orphan recovery, Money).
9. **Day 7-8** — SPEC-O2, O3, O10 (harnesses, shutdown).
10. **Day 9-10** — Fresh 48 h paper soak → v15 verdict.
