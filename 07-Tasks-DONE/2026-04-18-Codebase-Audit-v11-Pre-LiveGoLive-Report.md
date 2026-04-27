# SPYDER Codebase Audit v11 — Pre-Live-Go-Live Gap Report

**Date:** 2026-04-18
**Author:** Audit pass following v10 Signal-Path-Fixes (2026-04-18).
**Scope:** Find remaining blockers for hands-free autonomous SPY options trading via Tradier. Excludes items already resolved by v10 implementation (2026-04-18-Audit-v10-Signal-Path-Fixes.md).
**Verdict:** **NOT READY for live autonomous operation.** The signal-path is now healthy end-to-end (v10 is correct), but the **emergency-stop and wind-down paths are broken or missing**. The system can *open* trades autonomously; it cannot reliably *halt* or *close* them. In a real adverse market event the bot will continue trading into the loss.

The issues fall into four clusters:

1. **Kill switch / emergency stop is wired but un-triggerable.** No code emits `KILL_SWITCH`; E11's `EMERGENCY` event has no subscriber; `_emergency_close_all_positions` calls a broker method that does not exist.
2. **Session-supervisor omissions.** `position_tracker` is never created — fills go unrecorded, and close-direction logic silently defaults to BUY. `supervisor.stop()` is called without `flatten=True` on SIGTERM.
3. **Launcher has no live-mode safety gate or preflight checks.** `--mode live` passes through without credential validation, PID lock, API reachability check, or a secondary confirmation.
4. **Scheduler / market-hours logic is timezone-naive and ignores the holiday calendar at runtime.** Black-Friday early close and non-ET servers will trade past the real close.

Each fix is small; the *set* is large. Estimated effort: **2–3 focused days** for P0, **3–5 more** for P1.

---

## 1. Summary Table

| ID | Severity | Area | One-line problem |
|---|---|---|---|
| **P0-1** | Blocker | Emergency | No code emits `KILL_SWITCH` — manual halt is impossible. |
| **P0-2** | Blocker | Emergency | `E11.EMERGENCY` event has **zero subscribers** — catastrophic-loss breach does not halt trading. |
| **P0-3** | Blocker | Emergency | `TradierClient.close_position` does not exist — `_emergency_close_all_positions` is a silent no-op in live mode. |
| **P0-4** | Blocker | Emergency | `SessionSupervisor._flatten_positions` is a TODO stub (logs "manual intervention may be required"). |
| **P0-5** | Blocker | Reconciliation | `SessionSupervisor` never creates a `PositionTracker` — fills are unrecorded; close-direction fallback defaults to BUY for short positions. |
| **P0-6** | Blocker | Launcher | `Q14.supervisor.stop()` is called without `flatten=True` — SIGTERM exits with open positions. |
| **P0-7** | Blocker | Launcher | `Q14` runs `--mode live` with no credential-validation, no PID lock, no `LIVE_TRADING_CONFIRMED` gate, no broker health check. |
| **P0-8** | Blocker | Broker | `_broker_submit` does not call `record_api_server_error()` on Tradier 5xx — **API panic mode never triggers**. |
| **P0-9** | Blocker | Broker | Orders carry no `client_order_id`/`tag` — a retried submission on network timeout can double-fill. |
| **P0-10** | Blocker | Broker | `pending_orders` dict is never cleaned on `ORDER_CANCELLED`/`ORDER_EXPIRED`/timeout — stuck state + memory leak. |
| **P0-11** | Blocker | Scheduler | `R04._is_market_open` uses naive `datetime.now().time()` — on any non-ET server the check is wrong (closes on boundaries). |
| **P0-12** | Blocker | Scheduler | Scheduler hard-codes 16:00 close and ignores the `TradingCalendar.early_closes` map — Black-Friday / holiday early closes not honored at runtime. |
| **P1-1** | High | Strategy | `D31` does not halt signal emission on `KILL_SWITCH` or `DATA_STALE`, so strategies keep firing into a silenced engine. |
| **P1-2** | High | Risk | `E01.validate_signal` silently approves when `_positions` + account state are empty — the first few signals after boot bypass checks. |
| **P1-3** | High | Reconciliation | `R14` orphan sweep runs unconditionally at boot; if active_strategies is empty or loads slowly, existing broker positions are auto-closed. |
| **P1-4** | High | Reconciliation | `PositionTracker` has no persistence. After a restart state is empty; any fill missed during the outage is lost forever. |
| **P1-5** | High | Reconciliation | `R13` FillReconciler poll cadence (2–5 s) can miss sub-second option fills. No dead-letter queue on poll failures. |
| **P1-6** | High | Broker | `TradierClient.build_option_symbol` does not validate strike tick size. Typos reach Tradier and are rejected with cryptic errors. |
| **P1-7** | High | Broker | `PaperBroker.place_order` accepts any symbol/side/qty — masks OCC validation bugs that will surface in live. |
| **P1-8** | High | Config | `Q93_RunPaper` does not assert `TRADING_MODE in {"paper","sandbox"}` — misconfigured env can route paper run to live endpoint. |
| **P1-9** | High | Config | `SpyderU01_Logger` uses bare `FileHandler` (no rotation) — an autonomous bot will fill the disk. |
| **P1-10** | High | Config | No PID/lock file — two launchers against the same Tradier account silently double-trade. |
| **P1-11** | High | Events | `A05_EventManager._allow_multiple()` uses `os.environ` but `os` is never imported — latent `NameError` on any code path that constructs a second instance. |
| **P1-12** | High | Events | Handler exceptions in `A05` are swallowed; there is no dead-letter queue and no per-handler circuit breaker. A crashing risk-alert handler becomes invisible. |
| **P1-13** | High | Observability | Boot-time synthetic-signal self-test (audit-v10 I-6) was never implemented. A stealth regression of the v10 signal-path fix will not be caught at startup. |
| **P2-1** | Medium | Config | `Q14` silently overrides `TRADIER_ENVIRONMENT` when `--mode live` even if the user explicitly set it — a sandbox key + `--mode live` will target the live URL. |
| **P2-2** | Medium | Risk | `E01` data-stale gate blocks *new* entries only; existing positions are not flattened if stale data persists. |
| **P2-3** | Medium | Broker | Partial fills are computed correctly in `B02_OrderManager` but no `ORDER_PARTIALLY_FILLED` event is emitted — downstream risk recalculation never runs. |
| **P2-4** | Medium | Events | `A05` ASYNC handler calls `asyncio.run()` inside a sync worker thread — deadlock / nested-loop hazard under load. |
| **P2-5** | Medium | Hygiene | 1,689 naive `datetime.now()` calls remain (Q10 Gate 4). Any one of them used for TTL/stale-data comparisons against aware timestamps will compute the wrong delta. |

---

## 2. P0 Blockers — Detail & Fix Recipes

### P0-1 / P0-2 — Kill switch is wired but un-triggerable; `EMERGENCY` has no subscriber

[Spyder/SpyderA_Core/SpyderA05_EventManager.py](Spyder/SpyderA_Core/SpyderA05_EventManager.py) defines `EventType.KILL_SWITCH` (line ~148); [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:233](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L233) subscribes `_on_kill_switch`. **No module emits it** (`rg "emit.*KILL_SWITCH"` returns zero hits).

Meanwhile [Spyder/SpyderE_Risk/SpyderE11_MaxLossProtection.py:605](Spyder/SpyderE_Risk/SpyderE11_MaxLossProtection.py#L605) emits `EventType.EMERGENCY` on catastrophic loss breach. **No module subscribes to `EMERGENCY`** (`rg "subscribe.*EMERGENCY"` returns zero hits). So the risk-engine's strongest signal is consumed by nothing.

**Fix (one of):**
1. Have `E11` and `E13` emit `KILL_SWITCH` directly (not `EMERGENCY`); payload includes `reason`, `severity`, `initiator`.
2. Add a small bridge handler at `R04` startup that subscribes to `EMERGENCY` and re-emits `KILL_SWITCH`.

**Acceptance:**
- Synthetic test: force `E11` to emit `EMERGENCY` → `R04._kill_switch_active` becomes `True` within 100 ms → subsequent `_broker_submit` raises `RuntimeError("KILL_SWITCH is active …")`.
- Add a T129 regression test that exercises this path.

### P0-3 / P0-4 — Emergency close and flatten are no-ops

[Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:1573](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1573) calls `self.broker.close_position(...)` inside `_emergency_close_all_positions`. Grep: `TradierClient` exposes `place_order` and `place_order_async` only — **no `close_position` method exists**. The call raises `AttributeError`, which the `except Exception` swallows.

[Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py:450–466](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L450-L466) `_flatten_positions` logs a warning and returns — the comment literally reads *"full flatten not yet implemented — manual intervention may be required"*.

**Fix:**
1. Implement `TradierClient.close_position(symbol, urgency="IMMEDIATE", reason: str) -> dict` that:
   - Looks up the current position quantity via `get_positions`.
   - Places an offsetting market order (`BUY` to close shorts, `SELL` to close longs) via `place_order(order_type=MARKET, tag=f"close-{symbol}-{uuid}")`.
   - Returns `{"status", "tradier_order_id"}`.
2. Replace `_flatten_positions` in R12 with: iterate `broker.get_positions()`, submit close-orders through the live engine so the same risk/observability paths are used.

**Acceptance:** paper-broker integration test opens a short credit spread, triggers `KILL_SWITCH`, asserts a BUY offsetting order reaches the broker within 2 s, asserts `get_positions()` returns empty.

### P0-5 — `SessionSupervisor` never creates a `PositionTracker`

[Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py:360](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L360) passes `position_tracker=getattr(self, "position_tracker", None)` — the attribute is never assigned. `LiveEngine` receives `None`. Consequences:
- [R04:1266–1270](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1266-L1270) skips `record_fill` → strategy-level position state never updates from fills.
- [R04:1421–1429](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1421-L1429) close-direction resolver reads `_qty = 0.0` from the missing tracker → long-position close falls through to `OrderSide.BUY` which **re-opens** the long instead of closing it. This triggers only for legacy close-signals that do not carry an explicit `"side"` key; R14's fix in v10 sets `"side"`, but any other emitter (manual CLI, Telegram, GUI close button) falls into this hole.

**Fix:** Add `_start_position_tracker()` to R12, called **before** `_start_live_engine`:

```python
def _start_position_tracker(self) -> None:
    from Spyder.SpyderB_Broker.SpyderB03_PositionTracker import create_position_tracker
    self.position_tracker = create_position_tracker(
        broker=self.broker, event_manager=self.em,
    )
    self.position_tracker.start()
    self._components.append(self.position_tracker)

# in start() just after _start_broker / before _start_fill_reconciler:
self._start_position_tracker()
```

Also change `_start_live_engine` to pass `position_tracker=self.position_tracker` (not `getattr`).

**Acceptance:** emit a synthetic `ORDER_FILLED` → `self.position_tracker.get_position(symbol).quantity` reflects it within 50 ms.

### P0-6 — `Q14` exits without flattening

[Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py:370,392](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L370) call `supervisor.stop()` (default `flatten=False`). On SIGTERM the process exits with positions open — the bot cannot safely survive a host reboot or deploy.

**Fix:** `supervisor.stop(flatten=(self._mode == "live"))`. Paper mode should NOT flatten (keeps state for dev inspection); live mode must.

**Acceptance:** SIGTERM handler integration test in T129: open a position → send SIGTERM → broker shows zero positions within 5 s.

### P0-7 — Launcher has no live-mode gate, no credentials check, no PID lock

[Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py):
- `--mode live` is accepted with no secondary confirmation.
- `SpyderA03_Configuration.validate_startup_config()` exists and is thorough, but **Q14 never calls it**. Missing `TRADIER_API_KEY` / `TRADIER_ACCOUNT_ID` doesn't hard-fail.
- No PID file. Two launchers against the same account silently double-trade.
- No pre-trade broker health check (Tradier reachable, buying_power > 0, market state).

**Fix (in the launcher, before `supervisor.start()`):**
```python
# 1. Live-mode gate
if args.mode == "live" and os.environ.get("LIVE_TRADING_CONFIRMED") != "true":
    sys.exit("❌ Live trading requires LIVE_TRADING_CONFIRMED=true in the env.")

# 2. Credential + config validation
from Spyder.SpyderA_Core.SpyderA03_Configuration import validate_startup_config
ok, errors = validate_startup_config(mode=args.mode)
if not ok:
    sys.exit(f"❌ Config validation failed: {errors}")

# 3. Single-instance lock
import fcntl
_lock = open("/tmp/spyder_trading.lock", "w")
try:
    fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit("❌ Another Spyder launcher is already running.")

# 4. After start(), preflight broker
acct = supervisor.broker.get_account()
if not acct or float(acct.get("buying_power", 0)) <= 0:
    supervisor.stop(); sys.exit("❌ Broker unreachable or zero buying power.")
```

### P0-8 — 5xx from Tradier does not escalate to API panic mode

[Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:1402–1470](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1402-L1470) `_broker_submit` catches exceptions but does not call `self.record_api_server_error()`. The `API_PANIC_THRESHOLD` logic (L633) is effectively dead.

**Fix:** wrap `broker.place_order(...)` in a try block:
```python
try:
    response = broker.place_order(...)
    self.reset_api_error_count()
except _TradierServerError:
    self.record_api_server_error()   # triggers emergency_stop_all at threshold
    raise
```

### P0-9 — No order idempotency

`TradierClient.place_order` does not send a client-side `tag`. Tradier supports `tag` as an idempotency key for ~24 h. On a retry after network timeout, the same order can be submitted twice, producing a duplicate fill.

**Fix:** generate `tag = f"spyder-{order_id}"` (order_id is already unique per engine call) and pass through to Tradier. Broker protocol already accepts `**kwargs`, so the hop is straightforward.

### P0-10 — `pending_orders` never cleaned

[R04:506](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L506) adds the entry; only `_on_reconciler_fill` reads from it. There is no handler for `ORDER_CANCELLED`, `ORDER_EXPIRED`, `ORDER_REJECTED`, or submission-timeout that removes the entry. Stuck state compounds over days; memory leaks; metrics report inflated "successful_executions" over time.

**Fix:** subscribe `EventType.ORDER_CANCELLED` / `ORDER_EXPIRED` / `ORDER_REJECTED` → `del self.pending_orders[order_id]`. Add a nightly GC that evicts entries older than `max_age = timedelta(hours=24)`.

### P0-11 / P0-12 — Market-hours logic is timezone-naive and ignores the calendar

[R04:1144–1147](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1144-L1147):
```python
def _is_market_open(self) -> bool:
    now = datetime.now().time()       # naive, local tz
    return MARKET_OPEN <= now <= MARKET_CLOSE
```
On a UTC server this opens at 05:30 UTC and closes at 12:00 UTC — wrong. Same pattern appears in `SpyderA04_Scheduler.py` (lines 206, 714). `TradingCalendar` is correctly tz-aware in `SpyderU10_TradingCalendar.py` but the runtime consumers don't use it.

**Fix:**
1. `from zoneinfo import ZoneInfo; ET = ZoneInfo("America/New_York")`. Replace all `datetime.now()` used for market-hours with `datetime.now(ET)`.
2. Fetch close time dynamically: `close_time = trading_calendar.get_market_close(today)` (returns 13:00 ET on Black Friday, 16:00 ET normally).
3. Scheduler cron tasks should be rebuilt each market day from `TradingCalendar`, not hard-coded.

**Acceptance:** T129 test parametrized over `(now, server_tz)` pairs asserting `is_market_open()` returns the right answer.

---

## 3. P1 Items — Short Descriptions

- **P1-1** — [D31:_on_market_data_event](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py): subscribe `KILL_SWITCH` and `DATA_STALE`; set `self._paused = True`; return early from signal handlers while paused.
- **P1-2** — [E01:validate_signal](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py): when `self._positions` is empty AND `AccountManager` state is not yet synced, **reject** the signal with `rejection_reason="risk_state_cold"` rather than silently approving.
- **P1-3** — [R12:_boot_orphan_sweep](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L416-L429): guard with `if not self.orchestrator.active_strategies: log.warning(...); return`. Add `--skip-orphan-sweep` flag for warm restarts.
- **P1-4** — [B03_PositionTracker](Spyder/SpyderB_Broker/SpyderB03_PositionTracker.py): add `save_state()` to JSON on each fill; `load_state()` on start; **reconcile on start via `broker.get_positions()` and warn on divergence** rather than trust either side alone.
- **P1-5** — [R13_FillReconciler](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py): drop poll cadence to 1.0 s for options. Add a dead-letter log for orders that exceed `MAX_CONSECUTIVE_ERRORS`.
- **P1-6 / P1-7** — Add OCC strike-tick validation (`strike % 0.05 == 0`) in `TradierClient.build_option_symbol` **and** in `PaperBroker.place_order` so paper-mode catches the same mistakes.
- **P1-8** — [Q93_RunPaper](Spyder/SpyderQ_Scripts/SpyderQ93_RunPaper.py): assert `os.environ.get("TRADING_MODE") in ("paper","sandbox")` before `create_paper_trading_harness_from_env()`.
- **P1-9** — [SpyderU01_Logger](Spyder/SpyderU_Utilities/SpyderU01_Logger.py): swap `FileHandler` → `RotatingFileHandler(maxBytes=50*1024*1024, backupCount=10)`.
- **P1-10** — already covered in P0-7 fix recipe (PID lock).
- **P1-11** — [A05_EventManager.py:24](Spyder/SpyderA_Core/SpyderA05_EventManager.py#L24): add `import os` to the stdlib-imports block. `_allow_multiple()` at line 389 references `os.environ` without it — latent `NameError`.
- **P1-12** — [A05:_dispatch](Spyder/SpyderA_Core/SpyderA05_EventManager.py): on handler exception, emit `EventType.SYSTEM_ERROR` with `handler_name` + `event_type` + traceback; keep an in-memory ring of last-100 handler crashes reachable via `get_handler_errors()`.
- **P1-13** — `R12.start()` after boot-orphan-sweep: emit a synthetic `STRATEGY_SIGNAL` with `dry_run=True`; assert an `ORDER_FILLED` equivalent or `ORDER_REJECTED (reason=dry_run)` arrives within 3 s. Fail start if not.

---

## 4. P2 Items — Polish

- **P2-1** Q14 should only override `TRADIER_ENVIRONMENT` if not explicitly set by the user; log warning on override.
- **P2-2** On `DATA_STALE` lasting > N minutes, flatten existing positions (configurable per-strategy).
- **P2-3** Emit `ORDER_PARTIALLY_FILLED` on each exec_quantity delta, not only on terminal FILLED.
- **P2-4** Refactor ASYNC handler dispatch in `A05` to run on a shared `asyncio.new_event_loop` per thread, not `asyncio.run()` per event.
- **P2-5** Complete the `datetime.now()` → `now_utc()` / `now_et()` migration; 1,689 sites remain.

---

## 5. New Ideas (not gaps, but worth discussing)

1. **Per-strategy budget circuit breaker.** Each strategy gets a daily-loss budget; on breach, just that strategy is paused (not the whole engine). Enables hands-off operation without one bad strategy killing the day.
2. **Slack/Telegram heartbeat.** Every 15 min the supervisor posts `positions, daily_pnl, api_errors, uptime`. Fail-loud if the heartbeat stops — operator's phone tells them the bot is dead, no dashboard needed.
3. **Shadow-fill mode.** For 1–2 weeks in live mode run `dry_run=True` with full real-time signal flow; compare against paper broker fills. Any divergence surfaces live-only bugs (OCC format, Tradier quirks) without real money at risk.
4. **Daily P&L reconciliation job.** End-of-day cron that pulls Tradier's official `get_account()` P&L and compares with `PositionTracker.get_daily_pnl()`. Divergence > $10 → alert + pause next day.
5. **Per-order audit log.** Append-only SQLite log of `(event, order_id, symbol, side, qty, price, timestamp, source)` for every state transition. Post-mortem becomes trivial and regulatory-friendly.
6. **Chaos test fixture.** Seed the paper broker with random 5xx / rate-limit / partial-fill / out-of-order fills; run the full loop for an hour; assert no stuck orders, no unreconciled positions, no leaks in `pending_orders`. Should be a CI gate.

---

## 6. Ready-for-Autonomous-Trading Gate v2

Before flipping `--mode live` with `LIVE_TRADING_CONFIRMED=true`, **all** of the following must hold:

- [ ] P0-1 / P0-2 — `EMERGENCY` from E11/E13 triggers `KILL_SWITCH`; R04 halts new orders; T129 regression test exists.
- [ ] P0-3 / P0-4 — `TradierClient.close_position` implemented; `_flatten_positions` actually closes all positions; paper-broker integration test passes on a short credit spread.
- [ ] P0-5 — `PositionTracker` created in `SessionSupervisor`; fills are recorded; close-direction works without needing R14's explicit `"side"`.
- [ ] P0-6 — `Q14` calls `supervisor.stop(flatten=True)` in live mode; SIGTERM test leaves zero positions.
- [ ] P0-7 — `LIVE_TRADING_CONFIRMED` gate, `validate_startup_config` call, PID lock, and preflight broker check all present in the launcher.
- [ ] P0-8 — `_broker_submit` catches `TradierServerError` → `record_api_server_error()`. API panic mode triggers at threshold.
- [ ] P0-9 — every order includes `tag=f"spyder-{order_id}"`.
- [ ] P0-10 — `pending_orders` cleanup on CANCELLED/EXPIRED/REJECTED plus 24-h GC.
- [ ] P0-11 / P0-12 — all market-hours checks use ET; scheduler consults `TradingCalendar` for actual close.
- [ ] P1-11 — `import os` added to `A05_EventManager`.
- [ ] P1-13 — boot-time synthetic signal self-test implemented and failing the start on round-trip failure.
- [ ] 48 h of continuous paper-mode operation with `spyder_signals_dropped_total` flat, `spyder_orders_submitted_total` growing monotonically, no stuck `pending_orders`, no unreconciled positions.

Until these boxes are checked, the system can open trades autonomously but cannot safely halt or close them. **Do not go live.**

---

## 7. Suggested Fix Order for the Coding Agent

1. **P1-11** — one-liner `import os` in `A05`. Trivial to include first.
2. **P0-11 / P0-12** — timezone fix. Touches many lines but mechanical; get it done while context is fresh.
3. **P0-5** — create `PositionTracker` in `R12`. Unlocks P0-10 and P1-4.
4. **P0-3 / P0-4** — `close_position` + real `_flatten_positions`. Needed for everything else in emergency.
5. **P0-1 / P0-2** — bridge `EMERGENCY` → `KILL_SWITCH` (or move E11/E13 to emit `KILL_SWITCH` directly).
6. **P0-8** — wrap `_broker_submit` with `record_api_server_error`.
7. **P0-9** — add `tag` to `place_order`.
8. **P0-10** — clean `pending_orders` on terminal events.
9. **P0-6 / P0-7** — launcher gates + `flatten=True` on stop.
10. **P1-1 … P1-13** in the order listed.
11. Add T129 regression tests for each P0 as they land.
12. Run 48 h paper-mode soak test. Then re-read this report's gate checklist. Then go live.
