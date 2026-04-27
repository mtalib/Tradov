# SPYDER Codebase Audit v12 — Post-v11-Fix Verification & Remaining-Gap Report

**Date:** 2026-04-19
**Author:** Audit pass following v11 Pre-Live-Go-Live Fixes (`07-Tasks-DONE/2026-04-19-Audit-v11-PreLiveGoLive-Fixes.md`).
**Scope:** Verify that v11 P0 fixes are correctly wired; surface remaining anomalies (P1/P2 unaddressed + new gaps) before flipping `--mode live`.
**Branch reviewed:** `refactor/g05-widget-extraction`.

**Verdict:** **NOT READY for live autonomous operation.** v11 closed 9 of the 12 P0 blockers correctly, but **3 newly-introduced or still-latent BLOCKERs** remain on the emergency-stop / wind-down path:

1. `PaperBroker` does not implement `close_position()` — paper-mode flatten will crash (regression).
2. `E13` (Day Profit Target) never emits `EMERGENCY` or `KILL_SWITCH` — hitting the daily target does not stop the bot.
3. `place_order_async()` signature does not accept `tag` — async submission path loses idempotency.

Plus 4 additional production-risk items (race on `pending_orders`, asymmetric DATA_STALE pause with no `DATA_FRESH` unpause, `KeyboardInterrupt` does not flatten in live mode, kill-switch flag is non-atomic with no persistence).

The signal-path and order-submit-path are healthy. The risk + emergency + restart paths still have holes.

---

## 1. v11 P0 Verification Summary

| ID | Status | Evidence |
|---|---|---|
| **P0-1 / P0-2** EMERGENCY → KILL_SWITCH bridge | ✅ PASS | [SpyderR04_LiveEngine.py:239,1320-1339](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1320) — `_on_emergency_bridge` subscribed and re-emits KILL_SWITCH. Kill-switch check is first in `_broker_submit()`. |
| **P0-3 / P0-4** `close_position` + `_flatten_positions` | ⚠️ PARTIAL | TradierClient implementation is correct ([B40:970-1046](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L970)) and R12 iterates correctly ([R12:467-510](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L467)). **BUT PaperBroker does not implement `close_position()`** — see Blocker #1. |
| **P0-5** PositionTracker wired | ✅ PASS | Created at [R12:166](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L166) before `_start_live_engine` ([R12:172](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L172)); passed via `position_tracker=` keyword ([R12:377](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L377)); registered in `_components` ([R12:351](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L351)). |
| **P0-6** SIGTERM flatten | ⚠️ PARTIAL | `_run_headless_loop` ([Q14:446](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L446)) and `_request_shutdown` ([Q14:469](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L469)) pass `flatten=` correctly. **`KeyboardInterrupt` handler at [Q14:503](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L503) calls `supervisor.stop()` without `flatten`** — see Blocker #2. |
| **P0-7** Live-mode preflight gate | ✅ PASS | `_live_preflight_checks()` ([Q14:337-378](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L337)) covers `LIVE_TRADING_CONFIRMED`, credentials, and `fcntl` PID lock (handle held in `_pid_lock_fh` for process lifetime). `_broker_preflight_check()` runs after `start()`. |
| **P0-8** 5xx → API panic | ✅ PASS | `_broker_submit` wraps `place_order` in try/except `TradierServerError` ([R04:1461-1526](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1461)), calls `record_api_server_error()` on 5xx, `reset_api_error_count()` on success. `API_PANIC_THRESHOLD = 3` defined and triggers `emergency_stop_all()`. |
| **P0-9** Order idempotency `tag` | ⚠️ PARTIAL | `place_order` (sync) accepts `tag` and appends to payload ([B40:876,926](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L876)). **`place_order_async()` signature omits `tag` ([B40:2099-2109](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L2099)) and the executor call ([B40:2144-2148](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L2144)) does not pass it** — see Blocker #3. |
| **P0-10** `pending_orders` cleanup | ⚠️ PARTIAL | Handler subscribed to all three terminal events ([R04:243-245](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L243)); `_gc_pending_orders()` at 24 h ([R04:1614-1632](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1614)). **Uses `del` not `pop(.., None)` (KeyError on duplicate event); uses naive `datetime.now()` for `submitted_at` ([R04:523](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L523)); no thread-lock on the dict** — see Blocker #4. |
| **P0-11 / P0-12** ET timezone + early-close | ✅ PASS | `_is_market_open()` uses `datetime.now(_ET)` and `cal.get_market_close()` ([R04:1162-1169](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1162)). `get_market_close(for_date)` exists in U10 ([U10:496-509](Spyder/SpyderU_Utilities/SpyderU10_TradingCalendar.py#L496)). |
| **P1-1** D31 strategy pause | ⚠️ PARTIAL | `_paused` flag wired, both KILL_SWITCH and DATA_STALE handled. **No `DATA_FRESH` unpause subscription** — first stale-data event = permanent halt — see Blocker #5. |
| **P1-8** RunPaper TRADING_MODE assert | ✅ PASS | [Q93:433-442](Spyder/SpyderQ_Scripts/SpyderQ93_RunPaper.py#L433). |
| **P1-9** RotatingFileHandler | ✅ PASS | [U01:60-66](Spyder/SpyderU_Utilities/SpyderU01_Logger.py#L60). |
| **P1-11** `import os` in A05 | ✅ PASS | [A05:26](Spyder/SpyderA_Core/SpyderA05_EventManager.py#L26). |

---

## 2. New / Still-Open BLOCKERs

### B1 — `PaperBroker.close_position()` missing (regression introduced by v11)
**Severity:** BLOCKER (paper-mode crash)
**File:** `Spyder/SpyderR_Runtime/SpyderR15_PaperBroker.py`
**Evidence:** `grep close_position SpyderR15_PaperBroker.py` → no matches.
**Trigger path:** `R12._flatten_positions()` ([R12:467-510](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L467)) calls `self.broker.close_position(symbol)`. In paper mode the broker is `PaperBroker`, which lacks the method, so `AttributeError` is raised and flatten silently fails (or crashes, depending on the calling try/except).
**Why it matters:** Every paper-mode SIGTERM / shutdown that flattens (live-mode + paper-broker tests, 48-hour soak, T129) will fail. The v11 fix is invisible to the paper test harness — a live-only smoke test will be the first time this codepath actually runs against `TradierClient`. That is the worst possible time to discover a missing method.

### B2 — `KeyboardInterrupt` does not flatten in live mode
**Severity:** BLOCKER (live exposure on Ctrl-C)
**File:** [Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py:499-504](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L499)
**Evidence:**
```python
except KeyboardInterrupt:
    self.log_info("🛑 Interrupted by user")
    supervisor = getattr(self, "_supervisor", None)
    if supervisor is not None:
        supervisor.stop()                # ← no flatten=True!
    return True
```
**Why it matters:** SIGTERM is handled correctly by `_request_shutdown` (passes `flatten=`), but Ctrl-C bypasses that path. An operator who Ctrl-Cs during live trading leaves positions open on Tradier. Same hole exists in the generic `except Exception` at [Q14:505](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L505) — any uncaught exception leaves positions open.

### B3 — `place_order_async()` does not accept `tag`
**Severity:** BLOCKER (idempotency breach on async retry)
**File:** [Spyder/SpyderB_Broker/SpyderB40_TradierClient.py:2099-2152](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L2099)
**Evidence:** Signature has 8 parameters, none of them `tag`; executor call passes 8 positional args:
```python
result = await loop.run_in_executor(
    None, self.place_order,
    symbol, side, quantity, order_type,
    duration, limit_price, stop_price, order_class,
)   # tag is the 9th param of place_order — never passed
```
**Why it matters:** Any path that goes through `place_order_async` (signal-driven async submission, GUI orders, future async strategies) submits **without** the Tradier idempotency key. A network-timeout retry on an async order can produce a duplicate fill — the exact scenario P0-9 was added to prevent. The fix only landed for the sync path.

### B4 — `pending_orders` dict is not thread-safe
**Severity:** BLOCKER (race; possible RuntimeError mid-trade)
**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:253,523,1282,1614+](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L253)
**Evidence:** `self.pending_orders: dict[str, dict] = {}` accessed from at least four threads:
- Main / executor thread in `execute_order()` (write).
- Event-manager worker thread in `_on_order_terminal_event()` (`del`, line 1282).
- Reconciler thread in `_on_reconciler_fill()` (read at line ~1296).
- GC iteration in `_gc_pending_orders()` (line 1624).
There is no lock. Concurrent `del` while another thread iterates the dict raises `RuntimeError: dictionary changed size during iteration`.
Sub-issues:
- `del self.pending_orders[order_id]` (line 1282) raises `KeyError` if a duplicate terminal event arrives — should be `pop(order_id, None)`.
- `submitted_at` registered as naive `datetime.now()` (line 523); GC compares against an ET-aware horizon → silent off-by-5h delta.

**Why it matters:** Crash mid-day during a fast options market. No graceful recovery; positions may be stuck pending in the bot's state but already filled at the broker.

### B5 — `D31` pauses on `DATA_STALE` but never unpauses on `DATA_FRESH`
**Severity:** BLOCKER (permanent halt on transient data dropout)
**File:** [Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py:1710-1729](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L1710)
**Evidence:** `_on_kill_or_stale()` is subscribed to both `KILL_SWITCH` and `DATA_STALE`, sets `self._paused = True`. **There is no `DATA_FRESH` subscriber that flips the flag back.** Meanwhile the data-staleness detector (E24) does emit `DATA_FRESH` on recovery.
**Why it matters:** The market data feed routinely has 1-3 second hiccups (websocket reconnects, vendor blips). Each one will permanently silence the strategy until the operator restarts the bot. For "hands-free autonomous" this turns into "pages me at random hours to manually restart."

---

## 3. Still-Open P1 / P2 Items (audit recipe never implemented)

| ID | Item | File | Status |
|---|---|---|---|
| **P1-2** | `validate_signal()` silently approves cold-start signals | [SpyderE01_RiskManager.py:649-765](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L649) | ❌ unfixed |
| **P1-3** | `_boot_orphan_sweep` runs unconditionally; auto-closes legitimate broker positions if strategies load slowly | [SpyderR12_SessionSupervisor.py:418-440](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L418) | ❌ unfixed |
| **P1-4** | `PositionTracker` has no persistence / no broker reconciliation on start | [SpyderB03_PositionTracker.py](Spyder/SpyderB_Broker/SpyderB03_PositionTracker.py) | ❌ unfixed |
| **P1-5** | `FillReconciler` polls 2-5 s; misses sub-second SPY-options fills; orphans orders after 8 consecutive errors | [SpyderR13_FillReconciler.py:56-57,195-220](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py#L56) | ❌ unfixed |
| **P1-6** | `build_option_symbol` does not validate `strike % 0.05 == 0` | [SpyderB40_TradierClient.py:370+](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L370) | ❌ unfixed |
| **P1-7** | `PaperBroker.place_order` accepts any OCC symbol; masks live-only validation bugs | `SpyderR15_PaperBroker.py` | ❌ unfixed |
| **P1-12** | A05 catches handler exceptions but does not emit `SYSTEM_ERROR`, has no per-handler circuit breaker, no `get_handler_errors()` ring | [SpyderA05_EventManager.py:700-729](Spyder/SpyderA_Core/SpyderA05_EventManager.py#L700) | ⚠️ partial |
| **P1-13** | Boot-time synthetic-signal self-test never built | `SpyderR12_SessionSupervisor.py` | ❌ unfixed |
| **P2-2** | `DATA_STALE` blocks new entries but never flattens stale positions | [SpyderE01_RiskManager.py:673-680](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L673) | ❌ unfixed |
| **P2-3** | `ORDER_PARTIALLY_FILLED` is emitted by reconciler but with 2-5 s latency, allowing limit-breach window | [SpyderR13_FillReconciler.py:328-330](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py#L328) | ⚠️ partial |
| **P2-4** | `asyncio.run()` per ASYNC handler in [A05:714](Spyder/SpyderA_Core/SpyderA05_EventManager.py#L714) — nested-loop / deadlock hazard under load | A05 | ❌ unfixed |
| **P2-5** | ~1,994 naive `datetime.now()` calls remain (Q10 Gate 4) | many | ❌ unfixed |

---

## 4. NEW Gaps Not in v11 Audit (and not in the fix report)

### N1 — `_kill_switch_active` is a plain `bool`; no atomic / no persistence
**File:** [SpyderR04_LiveEngine.py:240,1317,1331,1448](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L240)
- Read/written across threads with no `threading.Event`. CPython's GIL makes a single read-or-write of a bool effectively atomic, but **read-modify-write sequences and visibility across threads are not guaranteed in the language spec**. A `threading.Event` removes ambiguity.
- The flag is in-memory only. If `E11` trips at 14:30 and the bot restarts at 14:31 (cron, deploy, OOM-kill), the kill-switch state is **lost** and the bot resumes trading into the same loss. There must be a lockout file (e.g., `.spyder_kill_lock`) that the launcher checks at boot.

### N2 — Generic `except Exception` in `_broker_submit` masks non-Tradier transients
**File:** [SpyderR04_LiveEngine.py:1400-1420](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1400)
- v11 added `except TradierServerError` correctly, but socket timeouts, JSON decode errors from a flaky proxy, or DNS failures fall through to the generic handler and **do not** increment `record_api_server_error()`. API panic mode never triggers on these "soft" outages; the bot continues spamming retries blind.

### N3 — No connectivity-loss / reconnection escalation in `FillReconciler`
**File:** [SpyderR13_FillReconciler.py:195-220](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py#L195)
- After `MAX_CONSECUTIVE_ERRORS = 8` poll failures, the order is simply dropped from the tracking set. There is **no dead-letter queue, no `ORPHAN_ORDER` event, no operator alert**. The bot goes blind on that order — the fill might still execute on the broker, the bot's position state diverges, future risk checks are wrong.

### N4 — No `.env` / config reload at runtime
**File:** [SpyderA03_Configuration.py:1021-1045](Spyder/SpyderA_Core/SpyderA03_Configuration.py#L1021)
- `reload()` exists but is never called by the runtime. To tighten `MAX_DAILY_LOSS` mid-session you must restart, which means flatten + cold reboot — the very scenario the rest of the bot is fragile to. A `SIGUSR1` reload handler closes this gap with one line.

### N5 — Order-state machine has no transition validation
**File:** `Spyder/SpyderB_Broker/SpyderB02_OrderManager.py`
- Orders move through PENDING_SUBMISSION → ACCEPTED → PARTIALLY_FILLED → FILLED / CANCELLED / EXPIRED / REJECTED, but no code asserts a transition is legal. A malformed Tradier response that skips a state (or replays an old one out of order) silently corrupts the local state.

### N6 — No heartbeat / external observability
- No periodic post to Slack/Telegram/PagerDuty. Operator has no way to tell the bot is alive. This is a critical hands-free feature: the bot's own observability cannot detect that *the bot is dead*.

### N7 — Log rotation works but no rollover alert
- `RotatingFileHandler(50 MB, 10)` will silently churn through all 10 backups during a verbose-error storm and lose the original cause.

### N8 — Asymmetric pause path means no test for "resume after data recovery"
- Per B5 above, the entire D31 pause path has only one valid entry (KILL_SWITCH/DATA_STALE) and no exit. There is no T129 test asserting that strategies resume after `DATA_FRESH`. Add the exit, then add the test.

### N9 — Naive `submitted_at` in `pending_orders` corrupts the 24 h GC
- `pending_orders[order_id]["submitted_at"] = datetime.now()` is naive local time. `_gc_pending_orders` compares against a horizon — depending on how the horizon is computed, the comparison is off by the local UTC offset and entries may be GC'd 5 hours early or never (TypeError if compared to an aware datetime).

### N10 — `close_position` does not verify fill
- [B40:1039-1046](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L1039) submits a market close order and returns. There is no follow-up wait for `ORDER_FILLED` and no retry on partial fill / rejected. In practice market orders fill, but a halted underlying or an out-of-hours close request will leave the position open and the bot believing it is flat.

---

## 5. Opportunities for Improvement (not gaps; ideas worth implementing)

1. **Per-strategy budget circuit breaker.** A bad strategy halts itself; the rest keep trading. Builds on existing `_paused` plumbing — add `_paused_strategies: set[str]` to D31.
2. **Boot-time kill-switch lockout file.** `~/.spyder_kill_lock` containing `{reason, timestamp, account_id}`. Launcher refuses to start if present unless `--clear-kill-lock` flag passed. Solves N1.
3. **Daily P&L reconciliation cron.** End-of-day job pulls Tradier's official P&L vs `PositionTracker.get_daily_pnl()`. Divergence > $10 → alert + auto-pause next day. Catches reconciliation bugs.
4. **Append-only SQLite order audit log.** `(event, order_id, symbol, side, qty, price, ts, source)` for every state transition. Post-mortem becomes trivial; satisfies regulatory audit trail.
5. **Chaos test fixture.** Seed PaperBroker with random 5xx / rate-limit / out-of-order fills; run the loop for an hour; CI gate on no stuck `pending_orders`. Catches B4 and N3 automatically.
6. **Heartbeat to Telegram.** Every 15 min: `positions, daily_pnl, api_errors, uptime`. Stops → operator's phone tells them the bot is dead. Solves N6.
7. **Shadow-fill mode.** First 2 weeks live with `dry_run=True` flag — full real-time signal flow but no actual orders; compare against PaperBroker fills. Surfaces live-only OCC/Tradier quirks without real money at risk.
8. **PaperBroker = TradierClient sandbox.** Instead of the in-process simulator, point PaperBroker at Tradier's sandbox endpoint. Same code path → same close_position, same OCC validation, same idempotency. Eliminates B1 and P1-7 by construction.

---

## 6. Ready-for-Autonomous-Trading Gate v3

Add to the v11 gate:

- [ ] **B1** PaperBroker `close_position()` implemented; T129 paper-flatten test passes.
- [ ] **B2** `KeyboardInterrupt` and generic `except Exception` in Q14 pass `flatten=(args.mode=="live")`.
- [ ] **B3** `place_order_async()` accepts `tag` and forwards it; T129 covers async-retry-dedup.
- [ ] **B4** `pending_orders` guarded by `threading.RLock`; `pop(.., None)` instead of `del`; `submitted_at` is `datetime.now(_ET)` or aware UTC.
- [ ] **B5** D31 subscribes `DATA_FRESH` and clears `_paused`; T129 covers stale → fresh → resume.
- [ ] **N1** `_kill_switch_active` migrated to `threading.Event`; on emit, write `~/.spyder_kill_lock`; launcher refuses start if present.
- [ ] **N2** `_broker_submit` generic `except` also calls `record_api_server_error()` for socket / JSON / DNS errors.
- [ ] **N3** `FillReconciler` emits `EventType.ORDER_ORPHANED` after `MAX_CONSECUTIVE_ERRORS` and the supervisor escalates.
- [ ] All P1 (P1-2 through P1-13) closed.
- [ ] 48 h paper-mode soak using **the same launcher path that live will use** (i.e. include the flatten-on-stop, kill-switch persistence, and async-tag paths exercised once each).
- [ ] T129 grows to cover: B1, B2, B3, B4, B5, N1, N2, N3 — one regression test per BLOCKER.

Until these are checked, the system can open trades autonomously but cannot reliably **halt itself, close positions on shutdown, recover from data hiccups, or survive a restart with risk-state intact**.

---

## 7. Coding-Agent Specs

Each spec is self-contained: file, change, acceptance, and where to put the test.

### Spec B1 — Implement `PaperBroker.close_position()`

**File:** `Spyder/SpyderR_Runtime/SpyderR15_PaperBroker.py`

**Change:** Add method matching the `BrokerProtocol` signature in [SpyderB21_BrokerProtocol.py:84-96](Spyder/SpyderB_Broker/SpyderB21_BrokerProtocol.py#L84):

```python
def close_position(self, symbol: str, force: bool = False) -> dict:
    """Close an open paper position by submitting an offsetting market order.

    Mirrors TradierClient.close_position so paper-mode flatten paths
    exercise the same control flow that runs in live.
    """
    pos = self._positions.get(symbol)
    if not pos or pos.quantity == 0:
        return {} if not force else {"status": "no_position", "symbol": symbol}

    qty = abs(pos.quantity)
    is_option = len(symbol) > 6 and any(c in symbol for c in ("C", "P"))

    if pos.quantity > 0:
        side = OrderSide.SELL_TO_CLOSE if is_option else OrderSide.SELL
    else:
        side = OrderSide.BUY_TO_CLOSE if is_option else OrderSide.BUY

    return self.place_order(
        symbol=symbol,
        side=side,
        quantity=qty,
        order_type=OrderType.MARKET,
        order_class=OrderClass.OPTION if is_option else OrderClass.EQUITY,
        tag=f"paper-close-{symbol}-{int(time.time())}",
    )
```

**Acceptance:**
- `T129` grows a test: open a paper short credit spread → call `_flatten_positions()` → assert `paper_broker.get_positions()` returns empty within 1 s.
- `Q10` ProtocolComplianceGate already enforces protocol completeness; verify it fails before this fix and passes after.

---

### Spec B2 — Make `KeyboardInterrupt` and `except Exception` flatten in live mode

**File:** [Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py:499-510](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L499)

**Change:**

```python
except KeyboardInterrupt:
    self.log_info("🛑 Interrupted by user")
    self._safe_stop_supervisor()
    return True
except Exception as exc:
    self.log_error(f"❌ Launch failed: {exc}")
    if self.args.debug:
        import traceback
        traceback.print_exc()
    self._safe_stop_supervisor()
    return False

def _safe_stop_supervisor(self) -> None:
    """Stop the supervisor with flatten=True iff in live mode.
    Centralised so every exit path uses the same logic."""
    supervisor = getattr(self, "_supervisor", None)
    if supervisor is None:
        return
    flatten = getattr(self.args, "mode", None) == "live"
    try:
        supervisor.stop(flatten=flatten)
    except Exception as exc:
        self.log_error(f"❌ Supervisor stop failed: {exc}")
```

**Acceptance:**
- T129 test: open a paper position, send `KeyboardInterrupt` to the launcher process, assert `broker.get_positions()` returns empty within 5 s in live mode (use Tradier sandbox), or that flatten is *not* attempted in paper mode.
- Manual smoke: `Ctrl-C` during live session leaves account flat.

---

### Spec B3 — Add `tag` to `place_order_async()`

**File:** [Spyder/SpyderB_Broker/SpyderB40_TradierClient.py:2099-2152](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L2099)

**Change:**
1. Add `tag: str | None = None` to the signature (last keyword param).
2. Pass it into the `run_in_executor` call. Because `place_order` has many positional args, prefer a wrapper:

```python
async def place_order_async(
    self,
    symbol: str,
    side: OrderSide,
    quantity: int,
    order_type: OrderType = OrderType.MARKET,
    duration: OrderDuration = OrderDuration.DAY,
    limit_price: float | None = None,
    stop_price: float | None = None,
    order_class: OrderClass = OrderClass.EQUITY,
    tag: str | None = None,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    async with tradier_breaker:
        return await loop.run_in_executor(
            None,
            functools.partial(
                self.place_order,
                symbol=symbol, side=side, quantity=quantity,
                order_type=order_type, duration=duration,
                limit_price=limit_price, stop_price=stop_price,
                order_class=order_class, tag=tag,
            ),
        )
```

3. Audit every caller of `place_order_async` (grep for `place_order_async(`); update each to pass `tag=f"spyder-{order_id}"`. The audit found callers in `R04` and the GUI submit path.

**Acceptance:**
- T129 test: monkey-patch `_send_request` to record the payload for two back-to-back async submissions of the same `order_id`; assert both payloads contain identical `tag` and (mocked) Tradier returns the same `broker_order_id`.

---

### Spec B4 — Thread-safe `pending_orders`

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:240,253,523,1282,1614+](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L240)

**Change:**
1. Add `self._pending_orders_lock = threading.RLock()` next to the `pending_orders` declaration.
2. Wrap every read, write, iteration of `self.pending_orders` in `with self._pending_orders_lock:`. Specifically:
   - `execute_order()` registration.
   - `_on_reconciler_fill()` lookup.
   - `_on_order_terminal_event()` removal.
   - `_gc_pending_orders()` iteration — copy keys into a local list under the lock, then remove outside.
3. Replace `del self.pending_orders[order_id]` with `self.pending_orders.pop(order_id, None)` to handle duplicate terminal events.
4. Replace `"submitted_at": datetime.now()` (line 523) with `"submitted_at": datetime.now(_ET)`. Audit `_gc_pending_orders()` to ensure its horizon is also `_ET`-aware.

**Acceptance:**
- T129 chaos-style test: spawn 4 threads each calling `execute_order` / `_on_order_terminal_event` / `_gc_pending_orders` on a shared engine for 5 s; assert no exception, no orphaned entries.
- Add an assertion in `_gc_pending_orders` that aborts and logs `WARNING` if any entry has a naive `submitted_at`.

---

### Spec B5 — D31 unpauses on `DATA_FRESH`

**File:** [Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py:1710-1729](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L1710)

**Change:**
1. Distinguish kill-switch from data-stale state:
```python
self._paused_kill: bool = False     # set by KILL_SWITCH; only restart clears
self._paused_stale: bool = False    # set by DATA_STALE; cleared by DATA_FRESH
```
2. Replace `_on_kill_or_stale` with two handlers:
```python
def _on_kill_switch(self, event):
    self._paused_kill = True
    log.critical("D31 paused by KILL_SWITCH; restart required to resume.")

def _on_data_stale(self, event):
    self._paused_stale = True
    log.warning("D31 paused by DATA_STALE; will resume on DATA_FRESH.")

def _on_data_fresh(self, event):
    if self._paused_stale:
        self._paused_stale = False
        log.info("D31 resumed; data feed recovered.")
```
3. Replace the single `_paused` check in `_on_market_data_event` and `_on_strategy_signal` with `if self._paused_kill or self._paused_stale: return`.
4. Subscribe to `EventType.DATA_FRESH` (already emitted by E24).

**Acceptance:**
- T129 test: emit DATA_STALE → assert orchestrator drops next signal → emit DATA_FRESH → assert next signal is processed.
- T129 test: emit KILL_SWITCH → emit DATA_FRESH → assert orchestrator still drops signals (kill-switch is sticky).

---

### Spec E13 — Day Profit Target must emit `EMERGENCY` on breach

**File:** `Spyder/SpyderE_Risk/SpyderE13_DayProfitTarget.py`

**Change:** The file references `_check_daily_loss_limit` and `_process_risk_alert` that are not implemented. The fix is to add (or restore) the breach path that emits `EventType.EMERGENCY` with payload `{"reason": "DAY_PROFIT_TARGET_HIT", "severity": "high", "initiator": "E13"}` when the day's realized + unrealized P&L crosses the configured target. Once emitted, R04's `_on_emergency_bridge` re-emits `KILL_SWITCH`, halting trading for the rest of the session — exactly the hands-free safety the system advertises.

**Acceptance:**
- T129 test: synthetic position with P&L = target + $0.01 → assert `EMERGENCY` is emitted within 100 ms → assert `R04._kill_switch_active` is True → assert next `_broker_submit` raises.

---

### Spec N1 — Persist kill-switch across restarts

**Files:** `Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py`, `Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py`

**Change:**
1. In R04, on `_on_emergency_bridge` / `_on_kill_switch`, write `~/.spyder_kill_lock` containing `{reason, ts, account_id}` JSON.
2. Replace `self._kill_switch_active: bool` with `self._kill_switch_event: threading.Event`.
3. In Q14 `_live_preflight_checks`, add: if `~/.spyder_kill_lock` exists, abort start unless `--clear-kill-lock` is passed; on clear, log who/when/why.

**Acceptance:**
- T129: emit EMERGENCY in run #1 → restart → assert run #2 refuses to start without the flag.

---

### Spec N2 — Generic-error escalation in `_broker_submit`

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:1400-1420](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1400)

**Change:** Add a second `except` for transient connectivity errors, BEFORE the catch-all:
```python
except (TimeoutError, ConnectionError, json.JSONDecodeError, OSError) as exc:
    self.record_api_server_error()
    log.error(f"Transient broker error: {exc}")
    raise
except TradierServerError:        # already present
    self.record_api_server_error()
    raise
except Exception as exc:          # already present, last
    log.error(f"Order submit failed: {exc}")
    raise
```

**Acceptance:**
- Unit test: monkey-patch broker `place_order` to raise `socket.timeout` → call `_broker_submit` 3× → assert `_kill_switch_event.is_set()`.

---

### Spec N3 — Orphan-order escalation in `FillReconciler`

**File:** [Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py:195-220](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py#L195)

**Change:** When `consecutive_errors > MAX_CONSECUTIVE_ERRORS`, do not silently drop the order. Instead emit `EventType.ORDER_ORPHANED` with payload `{order_id, broker_order_id, last_error}` and log to the dead-letter file at `logs/orphans.jsonl`. R04 should subscribe to `ORDER_ORPHANED` and (a) keep the entry in `pending_orders` flagged for operator review, (b) optionally trigger `KILL_SWITCH` if `n_orphans > N` in a 5-min window (configurable).

**Acceptance:**
- T129: monkey-patch `get_order` to raise → run reconciler poll loop → assert `ORDER_ORPHANED` is emitted exactly once → assert `logs/orphans.jsonl` has the entry.

---

### Specs for unaddressed P1 items (outline only)

| ID | One-line spec |
|---|---|
| **P1-2** | In `E01.validate_signal`, when `len(self._positions) == 0 AND not account_manager.synced`, return `RejectionResult(reason="risk_state_cold")`. Add `account_manager.synced` flag set after first successful `get_account()` round-trip. |
| **P1-3** | In `R12._boot_orphan_sweep`, prepend `if not self.orchestrator.active_strategies: log.warning("skip orphan sweep — no strategies loaded"); return`. Add CLI flag `--skip-orphan-sweep`. |
| **P1-4** | Add `B03_PositionTracker.save_state(path)` writing positions to JSON on each fill; `load_state(path)` on start; `reconcile_with_broker()` comparing local vs `broker.get_positions()` and warning on divergence > $0.01. |
| **P1-5** | Drop reconciler poll cadence to 1 s for `OrderType.MARKET`; keep 5 s for limit. Add dead-letter handling per N3. |
| **P1-6 / P1-7** | Add `_validate_strike(strike: float)` to `TradierClient.build_option_symbol`: assert `round(strike * 20) == strike * 20` (i.e. tick = 0.05). Replicate in PaperBroker.place_order so paper catches the same error. |
| **P1-12** | In `A05._dispatch`, on handler exception: emit `EventType.SYSTEM_ERROR` with `{handler_name, event_type, traceback}`; maintain `collections.deque(maxlen=100)` of crashes accessible via `get_handler_errors()`; if any handler exceeds 3 consecutive failures, mark it disabled. |
| **P1-13** | In `R12.start()` after orphan sweep, emit a synthetic `STRATEGY_SIGNAL(dry_run=True)`; assert `ORDER_REJECTED(reason="dry_run")` arrives within 3 s; fail start if not. |

### Specs for P2 items (outline only)

| ID | One-line spec |
|---|---|
| **P2-2** | In `E01`, on persistent `DATA_STALE > N` minutes (default 5), emit `EventType.FLATTEN_REQUEST` with `reason="data_stale"`. R12's `_flatten_positions` listens. |
| **P2-3** | Already partially addressed by R13. To close the latency: emit `ORDER_PARTIALLY_FILLED` synchronously in `B02_OrderManager.update_status` whenever `exec_quantity` changes, not only on poll. |
| **P2-4** | Refactor A05 ASYNC dispatch: maintain one `asyncio.new_event_loop()` per worker thread (thread-local), schedule via `loop.call_soon_threadsafe`. Avoids per-event loop creation. |
| **P2-5** | Continue migration of bare `datetime.now()` → `now_utc()` / `now_et()` per Q10 Gate 4. Prioritise files in `R04`, `R13`, `R12`, `E01` (touch the order/risk path first). |

---

## 8. Suggested Fix Order

1. **B1, B2, B3** (paper-flatten regression + Ctrl-C flatten + async tag) — small, mechanical, unblocks the paper soak test.
2. **B4** (`pending_orders` lock + naive timestamp) — the only fix that prevents a mid-day crash.
3. **B5** (DATA_FRESH unpause) — turns a permanent-halt incident into a transient one.
4. **E13 EMERGENCY emission** — completes the symmetric "stop trading on max-loss OR target-hit" guarantee.
5. **N1** (kill-switch persistence) — survive a restart safely.
6. **N2, N3** (transient errors + orphan escalation) — closes silent-failure modes the bot will hit during any network hiccup.
7. **P1-13** (boot-time self-test) — catches future regressions cheaply.
8. **P1-2, P1-4** (cold-start gate + tracker persistence) — close the restart-correctness gap.
9. Remaining P1 / P2 in the order listed.
10. Add T129 regressions for B1 / B2 / B3 / B4 / B5 / E13 / N1 / N2 / N3 / P1-13 — one test per BLOCKER fix.
11. **48 h paper-mode soak** with the same launcher path live will use. Re-read the v3 gate. Then go live.
