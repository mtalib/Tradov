# Tradov Codebase Audit v8 — Autonomous SPY-Options Trading Readiness

**Date:** 2026-04-18
**Scope:** Full wiring audit against the v8 Overview document
**Auditor:** Claude (Opus 4.7)
**Target reader:** Tradov coding agent

---

## 0. Executive Summary

Per the v8 Overview, the April 18 "gap fixes" were supposed to close the
market-data → strategy → risk → execution loop. **They did not.** Most of the
individual modules are correctly implemented, but the **wiring at the top of
the stack (Q14 launcher and R04 LiveEngine) is broken in ways that prevent
autonomous live trading from ever starting, and silently report false "filled"
statuses even when it does start**.

This document lists 11 **CRITICAL** defects that block autonomous operation,
7 **HIGH** defects that will cause silent data corruption or incorrect
behaviour, plus a set of **MEDIUM / opportunity** items.

Each finding carries an implementation spec (S-NN) at the end.

---

## 1. CRITICAL Findings (block autonomous live trading)

### C-01 — GUI path bypasses live-engine startup
**File:** `Tradov/TradovQ_Scripts/TradovQ14_MainLauncher.py:449-468`

`TradovLauncher.launch()` routes as follows:

```python
if self.args.gui and not self.args.headless:    # args.gui defaults to True
    if GUI_AVAILABLE:
        return self.launch_gui()                # shows dashboard & returns
...
return self.launch_system()                     # never reached unless --headless
```

`launch_gui()` only renders the dashboard. It never calls `_start_live_engine()`,
never starts C01 DataFeed, never starts D31 Orchestrator. **Live trading only
starts in `--headless` mode.** The documented invocation
`python TradovQ14_MainLauncher.py --mode live --gui` does not trade.

**Spec:** see S-01.

---

### C-02 — Q14 never starts TradovC01_DataFeed
**File:** `Tradov/TradovQ_Scripts/TradovQ14_MainLauncher.py:366-447`

`_start_live_engine()` constructs `TradierClient`, `RiskManager`,
`LiveEngine`, and `StrategyOrchestrator`, but **never imports or starts
`TradovC01_DataFeed`**. Grep for `DataFeed|create_data_feed|start_feed|MARKET_DATA`
in Q14 returns zero matches.

Consequence: no `EventType.MARKET_DATA` is ever published. D31's
`_on_market_data_event` never fires, strategies never see bars, no signals
are ever generated. The pipeline is disconnected at the very first stage.

**Spec:** see S-02.

---

### C-03 — Q14 creates three independent EventManager instances
**File:** `Tradov/TradovQ_Scripts/TradovQ14_MainLauncher.py:390, 427`

Two explicit `EventManager()` constructions:

- Line 390: `TelegramBot(..., event_manager=EventManager())`
- Line 427: `_event_manager = EventManager()` passed to the orchestrator

A third instance will be created by any default-constructed consumer
(C01, D31, D01) that didn't receive an injected one. A05 does expose a
singleton accessor — `get_event_manager(persist_events=True)` at
`TradovA05_EventManager.py:1066` — **but Q14 does not use it.**

Each EventManager has its own subscriber table and its own worker thread.
A publish on one is never observed by consumers attached to another. This is
why strategies look correctly wired in code review but nothing flows at
runtime.

**Spec:** see S-03.

---

### C-04 — EventManager.start() is never called
`EventManager.__init__` does not start worker threads; they only start on
`start()` (A05:472). No live-path module in Q14 calls `.start()`. Events
publish into queues that nothing drains.

**Spec:** merged into S-03.

---

### C-05 — R04 `_broker_submit` reports acceptance as "filled"
**File:** `Tradov/TradovR_Runtime/TradovR04_LiveEngine.py:1317-1330`

```python
response = broker.place_order(...)
tradier_order_id = (response or {}).get("order", {}).get("id")
return {
    "status": "filled" if tradier_order_id else "rejected",
    ...
}
```

Tradier's `POST /accounts/{id}/orders` returns an order ID **as soon as the
order is queued**, not when it fills. Market orders can sit queued for
hundreds of ms; limit orders can sit queued indefinitely; stop orders may
never trigger. Marking them as "filled" means:

- `daily_trades` counter is inflated
- `successful_executions` metric is wrong
- Downstream P&L / position-size math is based on fictional fills
- A05 `ORDER_FILLED` consumers (if any) receive lies

B40 exposes `get_order(order_id)` at `TradovB40_TradierClient.py:929` —
**it is never polled.**

**Spec:** see S-05.

---

### C-06 — R04 never updates position state
**File:** `Tradov/TradovR_Runtime/TradovR04_LiveEngine.py` (entire file)

Grep for `PositionTracker|position_tracker` in R04 returns zero matches.
After R04 believes an order filled:

- B03 `PositionTracker` is never notified
- E01 `RiskManager._positions` stays static (validate_signal uses stale state)
- P01 `PortfolioManager` is never updated
- No reconciliation call against Tradier `/accounts/{id}/positions`

Consequence: the risk gate evaluates subsequent signals as if no positions
exist, so position-size limits are unenforceable once the first order goes
through.

**Spec:** see S-06.

---

### C-07 — Paper mode has no execution engine wired
**File:** `Tradov/TradovQ_Scripts/TradovQ14_MainLauncher.py:356-357`

```python
elif self.args.mode == "paper":
    self.log_info("📄 Paper trading mode — using simulated execution")
```

That is the entire paper implementation. There is no R02 PaperEngine, no
R08 paper Qt worker, no simulated execution attached to D31. Per the v8
Overview the codebase contains `TradovR11_PaperStrategyRunner.py` (untracked
in git status) — it is never referenced by the launcher.

**Spec:** see S-07.

---

### C-08 — R04 has no event_manager; cannot publish fills
**File:** `Tradov/TradovR_Runtime/TradovR04_LiveEngine.py` (entire file)

Grep for `event_manager` in R04 returns zero matches. Even once C-05 is
fixed and we know a true fill occurred, R04 cannot publish
`EventType.ORDER_FILLED` because it has no publisher. Downstream consumers
(dashboard, metrics, portfolio, journaling) are therefore blind.

**Spec:** see S-08.

---

### C-09 — D01 BaseStrategy defines shadow Event/EventType/EventManager classes
**File:** `Tradov/TradovD_Strategies/TradovD01_BaseStrategy.py:307-342`

D01 declares local `EventType`, `Event`, and `EventManager` classes that
collide with A05's. The dual-emit at `_process_signal` (lines 792-828)
**only works because D31 injects an A05 EventManager via `add_strategy` at
D31:500**. Any future test or standalone execution that uses
`BaseStrategy` without D31 silently ends up with a dead publisher — no
error, no signal.

The shadow classes are also a subtle correctness trap: a `hasattr(em,
"emit")` check at D01:795 is the only thing routing the signal to the
"real" bus.

**Spec:** see S-09.

---

### C-10 — E01 `validate_signal` accepts `Any`, silently drops malformed requests
**File:** `Tradov/TradovE_Risk/TradovE01_RiskManager.py:599`

```python
def validate_signal(self, request: Any) -> Any:
```

The body assumes `request.quantity`, `request.symbol`, `request.entry_price`,
`request.metadata` all exist. If a caller passes a `dict` (the legacy format
used by older Q modules), `AttributeError` is raised, the `except Exception`
block at line 700 catches it, and returns
`RiskValidationResult(approved=False, violations=["INTERNAL_ERROR"])`. The
signal is silently rejected with a stack trace in the log, not a clear
contract error.

There is a separate compat adapter `check_trade(dict)` at line 742 — but D31
calls `validate_signal`, not `check_trade`, so the adapter is dead unless
legacy code paths are used.

**Spec:** see S-10.

---

### C-11 — No broker-fill reconciliation thread
No background task polls `broker.get_orders()` or consumes the Tradier
streaming account channel. Together with C-05 and C-06 this means the
system has **zero ground truth about its own positions** after startup.

**Spec:** see S-11.

---

## 2. HIGH Findings (correctness / observability)

### H-01 — Q14 "full system startup" doesn't actually startup
`launch_system()` at Q14:337-364 calls `master_controller()` (MasterController)
and then `_start_live_engine()`. If `MasterController.start()` fails (common in
dev environments without all deps), `self.state` stays `STARTING`, the method
returns `show_status()`, and the user sees a status dump rather than any
explicit error. Live engine is still attempted in parallel — confusing UX
and possible double-init in happy paths.

### H-02 — R04 `_broker_submit` happy path missing for B02
Path 1 at R04 `_broker_submit` uses `result.success` to set "filled". B02
(`TradovB02_BrokerClient`) may also represent acceptance, not fill. Needs
audit parity with C-05 / S-05.

### H-03 — No stop-loss / exit-path monitor
v8 Overview claims "exits are strategy-driven." Grep shows no periodic exit
scanner reading open positions and firing CLOSE signals on SL / TP / time
stops. D-series strategies own their own exits, but once a position exists
(C-06) there is no global watchdog — if a strategy dies after open, the
position lives forever.

### H-04 — Daily-limit gate is read-only
E01 `check_daily_limits` returns `False` when breached, but nothing in R04
polls it between orders. It's only called once at startup by the engine
initialiser (per the gap-fix doc). A breach during the session does not
halt trading.

### H-05 — `_data_stale` flag has no writer in the hot path
E01 `validate_signal` rejects on `self._data_stale`, but nothing in C01 or
R04 sets this flag based on tick-freshness observations. It can only be
flipped by an external supervisor that doesn't exist yet.

### H-06 — Tradier sandbox vs live switch is env-var only
Q14 sets `TRADIER_ENVIRONMENT` from `--mode`, but the client reads the env
once at construction. There is no runtime guard preventing a misconfigured
process from routing sandbox strategies to live URLs, or vice-versa. A
cross-check against the returned `account.type` would catch it.

### H-07 — Telegram confirmation uses a *third* EventManager
Q14:390 injects `EventManager()` into the Telegram bot. Confirmation
callbacks published by the bot do not reach the order-queue on the
orchestrator's EventManager. The human-in-the-loop path is broken by the
same symptom as C-03 — a "yes" from the user cannot unblock a held order.

---

## 3. MEDIUM Findings

- **M-01** R04 uses two broker-submission paths (`submit_order` on B02,
  `place_order` on B40) but no adapter. New brokers mean editing `_broker_submit`.
- **M-02** `TradovQ10_ProtocolComplianceGate.py` exists but is not invoked
  by any launcher path or pre-commit hook per the v8 Overview. It's
  documentation, not enforcement.
- **M-03** Duplicate launcher logic: `launch_system` and `_start_live_engine`
  both try to start things; the ordering of
  `controller.start()` → `_start_live_engine` → `state = RUNNING` is easy to
  break on refactor.
- **M-04** `create_live_engine(...)` doesn't accept an `event_manager` kwarg.
  Should; to fix C-08 cleanly.
- **M-05** No observable heartbeat from R04. A missed 30s heartbeat should
  halt the session.
- **M-06** D01 shadow classes (C-09) should be deleted outright, not
  patched. They add cognitive load and no behavioural value given A05
  injection.

---

## 4. Opportunities / New Modules

### O-01 — `TradovR12_SessionSupervisor`
A tiny lifecycle owner that:
1. Owns the single A05 EventManager (via `get_event_manager`)
2. Starts/stops C01, D31, R04, Telegram in the correct order
3. Runs heartbeats, writes `state.json` atomically
4. Exposes `SIGTERM` / dashboard-button graceful shutdown with position flatten option

Replaces the current `_start_live_engine` soup in Q14. Q14 becomes
argument-parsing + `SessionSupervisor.start(mode)`.

### O-02 — `TradovR13_FillReconciler`
Background task that polls `broker.get_orders()` every N seconds (configurable;
suggested 2s for market, 5s for limit) and publishes `ORDER_FILLED`,
`ORDER_PARTIALLY_FILLED`, `ORDER_CANCELLED`, `ORDER_EXPIRED` events with
ground-truth data. Short-circuits on websocket delivery if Tradier streaming
is enabled.

### O-03 — `TradovE02_DataFreshnessMonitor`
A C01 subscriber that watches tick timestamps and flips
`RiskManager._data_stale` when the last tick is older than threshold
(suggested 3s during RTH). Fixes H-05.

### O-04 — `TradovR14_ExitMonitor`
Periodic scanner over P01 `PortfolioManager` positions. For each position:
- Check strategy-declared SL/TP/time-stop
- Emit CLOSE signal if breached
- Detect orphaned positions (no owning strategy) and emit an alert

Fixes H-03.

### O-05 — `TradovB21_BrokerRouter` (interface narrowing)
Single `BrokerProtocol` with `submit_order`, `get_order`, `cancel_order`,
`get_positions`, `get_account`. R04 depends only on the protocol. B02, B40,
and any future broker implement it. Fixes M-01, makes paper mode trivial
(`TradovR02_PaperBroker` implements the protocol).

### O-06 — Dashboard parity
G05 already subscribes to `MARKET_DATA` and `CUSTOM_METRIC_UPDATE`. Extend
to subscribe to `ORDER_SUBMITTED`, `ORDER_FILLED`, `POSITION_UPDATED`,
`RISK_VIOLATION`. The data exists on the bus once C-03 and C-08 are fixed;
this is zero new code beyond a handful of slot wirings.

---

## 5. Implementation Specs

Each spec is a self-contained task for the coding agent. Specs are ordered
so that earlier ones unblock later ones. Assume a new feature branch
`fix/audit-v8-autonomous-pipeline` cut off `master`.

---

### S-01 — Fix Q14 launch routing so live mode always starts the engine
**Touches:** `TradovQ14_MainLauncher.py`

Change `launch()` to decouple GUI presence from headlessness of the trading
loop:

```python
def launch(self):
    self._log_startup_info()

    if self.args.status:    return self.show_status()
    if self.args.module:    return self.run_specific_module(self.args.module)
    if self.args.shutdown:  return self._request_shutdown()

    # 1. Always start the trading backend when mode is live|paper
    backend_ok = self._start_backend(self.args.mode)  # new method, see S-03
    if not backend_ok:
        return False

    # 2. Optionally attach the dashboard on top
    if self.args.gui and not self.args.headless and GUI_AVAILABLE:
        return self._run_gui_attached_to_backend()    # new method
    # headless → block on SIGTERM / KeyboardInterrupt
    return self._run_headless_loop()
```

**Acceptance:**
- `python TradovQ14_MainLauncher.py --mode live` (no flags) starts C01, D31, R04.
- `--gui` attaches the dashboard to the *already-running* backend.
- `--headless` does the same without the Qt app.
- Integration test: mocked broker, run `--mode paper --headless`, assert one
  `MARKET_DATA` → `STRATEGY_SIGNAL` → `ORDER_SUBMITTED` chain completes.

---

### S-02 — Start C01 DataFeed inside the backend bootstrap
**Touches:** `TradovQ14_MainLauncher.py` (new `_start_backend`),
`TradovC01_DataFeed.py` (verify `start()` is idempotent).

Inside `_start_backend(mode)`:

```python
from Tradov.TradovA_Core.TradovA05_EventManager import get_event_manager
from Tradov.TradovC_MarketData.TradovC01_DataFeed import create_data_feed

em = get_event_manager(persist_events=True)
em.start()

feed = create_data_feed(event_manager=em, symbols=["SPY", "SPX", "VIX"])
if not feed.start():
    self.log_error("DataFeed failed to start")
    return False
```

**Acceptance:**
- Running in `--mode paper --headless` produces `MARKET_DATA` events at
  expected cadence. Confirm by attaching a debug subscriber and asserting
  ≥1 event / 60s during RTH.

---

### S-03 — Enforce a single EventManager via `get_event_manager()`
**Touches:** `TradovQ14_MainLauncher.py`, `TradovJ05_TelegramBot.py` (callsite
only), any place that defaults to `EventManager()`.

**Rule:** outside unit tests, A05 `EventManager` must be instantiated **only**
inside `get_event_manager()`. All modules receive it via constructor
injection.

Grep-and-audit list (all must be changed to accept the shared instance):

- `TradovC01_DataFeed.py:529` (`self.event_manager = event_manager or EventManager()`)
- `TradovD31_StrategyOrchestrator.py:305`
- `TradovD01_BaseStrategy.py:342` area (delete shadow class — see S-09)
- Q14:390, Q14:427 (remove both fresh instantiations)

For runtime safety, add a module-level assertion in A05:

```python
_EM_SINGLETON_LOCK_MSG = (
    "Multiple EventManager instances detected. Use get_event_manager()."
)

class EventManager:
    _constructed_count = 0

    def __init__(self, ...):
        EventManager._constructed_count += 1
        if EventManager._constructed_count > 1 and not _allow_multiple():
            warnings.warn(_EM_SINGLETON_LOCK_MSG, RuntimeWarning, stacklevel=2)
```

`_allow_multiple()` reads `TRADOV_ALLOW_MULTIPLE_EM=1` so tests can opt in.

**Acceptance:**
- Unit test: `get_event_manager() is get_event_manager()`.
- Integration test: boot the full backend, assert only one EventManager
  exists (`gc.get_objects()` filter).
- `em.start()` is called exactly once.

---

### S-05 — Replace instant-"filled" with real fill polling / streaming
**Touches:** `TradovR04_LiveEngine.py` around line 1317; new
`TradovR13_FillReconciler.py` per O-02.

Replace the block at R04:1317-1330 with:

```python
response = broker.place_order(...)
tradier_order_id = (response or {}).get("order", {}).get("id")
if not tradier_order_id:
    return {"status": "rejected", "raw": response}
return {
    "status": "accepted",   # NOT "filled"
    "order_id": order.get("order_id"),
    "tradier_order_id": tradier_order_id,
    "raw": response,
}
```

Then introduce `TradovR13_FillReconciler`:

- Poll `broker.get_order(tradier_order_id)` on a `ThreadPoolExecutor`.
- Status mapping: `filled` → publish `ORDER_FILLED` with actual fill price,
  qty, timestamp. `partially_filled` → `ORDER_PARTIALLY_FILLED`.
  `rejected`/`canceled`/`expired` → matching event. Unknown statuses logged
  and retried with exponential backoff up to 60s.
- Prefer Tradier account-stream WebSocket if credentials available; fall
  back to HTTP polling.

R04 only increments `daily_trades` / `successful_executions` on a true
`ORDER_FILLED` event, not on acceptance.

**Acceptance:**
- Unit test: acceptance → no `ORDER_FILLED` emitted until reconciler
  reports filled.
- Integration (sandbox): place a limit order far from market; assert
  acceptance status and *no* metrics increment until manually cancelled;
  on cancel, `ORDER_CANCELLED` is emitted.

---

### S-06 — Wire PositionTracker into R04's fill path
**Touches:** `TradovR04_LiveEngine.py`, `TradovB03_PositionTracker.py`.

R04 subscribes to its own `ORDER_FILLED` (or receives a direct callback
from S-11 reconciler) and calls `position_tracker.record_fill(fill)`.

B03 needs `record_fill(Fill)` if absent. B03 publishes `POSITION_UPDATED`.

E01 `RiskManager` subscribes to `POSITION_UPDATED` and updates
`self._positions` under `_risk_lock`.

**Acceptance:**
- Unit test: simulate 2 buys and a sell; E01 `_positions["SPY250620C00450000"].quantity`
  matches net.
- `validate_signal` correctly rejects when stacked quantity exceeds
  `max_position_size`.

---

### S-07 — Wire a real paper execution engine
**Touches:** `TradovQ14_MainLauncher.py`, existing `TradovR11_PaperStrategyRunner.py`.

Paper mode must instantiate a paper broker that implements the broker
protocol from O-05 and plug it into R04 in place of B40. Simulated fills
run on the same `_broker_submit` path, producing real `ORDER_FILLED`
events once S-05/S-11 land.

**Acceptance:**
- `--mode paper --headless` produces end-to-end fills and `POSITION_UPDATED`
  events, identical wire format to `--mode live`, with no Tradier calls.

---

### S-08 — Give R04 an EventManager and publish order lifecycle events
**Touches:** `TradovR04_LiveEngine.py`, `create_live_engine(...)`.

Add `event_manager` kwarg to `create_live_engine` and store on the engine.
Emit:
- `ORDER_SUBMITTED` on `_broker_submit` acceptance
- `ORDER_FILLED` / `ORDER_PARTIALLY_FILLED` / `ORDER_CANCELLED` / `ORDER_REJECTED`
  on reconciler callbacks
- `RISK_VIOLATION` when `validate_signal` rejects (currently swallowed in D31)

Fixes C-08 and H-07 together.

**Acceptance:**
- Subscribe a test consumer, run the paper loop, observe exactly one
  `ORDER_SUBMITTED` followed by terminal state event per order.

---

### S-09 — Delete D01 shadow EventManager / EventType / Event classes
**Touches:** `TradovD01_BaseStrategy.py:307-342` and `_process_signal`.

1. Delete the three local classes.
2. Remove the dual-emit at `_process_signal`. Replace with unconditional
   `self.event_manager.publish(Event(EventType.STRATEGY_SIGNAL, ...))`.
3. Require `event_manager` in `BaseStrategy.__init__` (no default). Failing
   fast is better than silent no-op.

**Acceptance:**
- Full test suite passes.
- `grep -n "class EventManager" Tradov/TradovD_Strategies/` returns nothing.

---

### S-10 — Tighten E01 `validate_signal` typing and input validation
**Touches:** `TradovE01_RiskManager.py:599`.

```python
from Tradov.TradovE_Risk.TradovE00_RiskProtocol import (
    RiskValidationRequest, RiskValidationResult,
)

def validate_signal(self, request: RiskValidationRequest) -> RiskValidationResult:
    if not isinstance(request, RiskValidationRequest):
        raise TypeError(
            f"validate_signal expects RiskValidationRequest, got {type(request).__name__}"
        )
    ...
```

Legacy `dict` callers route through `check_trade` as today. `except
Exception` block stays as a defence-in-depth for unexpected errors, but no
longer masks type mismatches.

**Acceptance:**
- Unit test asserts `TypeError` on dict input (D31 callers already use
  `RiskValidationRequest` per v8 gap-fix).

---

### S-11 — Fill reconciliation background worker
**Touches:** New `TradovR_Runtime/TradovR13_FillReconciler.py`, R04 init.

Spec:
- Singleton service owned by `SessionSupervisor` (O-01).
- Accepts registrations `reconciler.track(order_id, tradier_order_id)` on every
  accepted order.
- Poll cadence: 2s for MARKET/STOP, 5s for LIMIT.
- Publishes lifecycle events on the shared EventManager.
- Drops the registration once a terminal state is reached.
- Instruments itself to `TradovB15_PrometheusMetrics`:
  `fill_detection_latency_ms`, `reconciler_poll_total`,
  `reconciler_fill_miss_total`.

**Acceptance:**
- Sandbox integration: place 5 limit orders at varying prices, confirm
  each transitions through ACCEPTED → (FILLED | CANCELLED) with
  latency ≤ poll cadence + 500ms.

---

### S-12 — (Covers O-01) SessionSupervisor
New `TradovR_Runtime/TradovR12_SessionSupervisor.py`. Owns lifecycle:

```python
class SessionSupervisor:
    def __init__(self, mode: Literal["paper", "live"]):
        self.em = get_event_manager(persist_events=True)
        self.mode = mode
        self.components: list[Lifecycle] = []

    def start(self) -> bool:
        self.em.start()
        broker = self._build_broker()
        risk   = get_risk_manager()
        feed   = create_data_feed(event_manager=self.em, symbols=[...])
        engine = create_live_engine(broker, risk, cfg, event_manager=self.em)
        orch   = StrategyOrchestrator(event_manager=self.em, ...)
        orch.set_live_engine(engine)
        reco   = FillReconciler(broker=broker, event_manager=self.em)
        self.components = [feed, engine, orch, reco]
        for c in self.components:
            if not c.start(): return self._abort(f"{c.__class__.__name__} failed to start")
        return True

    def stop(self, flatten: bool = False):
        if flatten: self._flatten_positions()
        for c in reversed(self.components):
            try: c.stop()
            except Exception: pass
        self.em.stop()
```

Q14 becomes ~20 lines: parse args, construct `SessionSupervisor`, handle
signals.

**Acceptance:**
- `--mode paper --headless` starts and stops cleanly via `SIGTERM`.
- Startup failure in any one component aborts the whole session with a
  clear error, not a half-running system.

---

### S-13 — DataFreshnessMonitor (O-03)
Small C01 subscriber that records last-tick timestamp per symbol and flips
`risk_manager._data_stale` when the freshest symbol is older than N
seconds. Default N = 3 during RTH, 30 outside. Publishes
`DATA_STALE` / `DATA_FRESH` transitions.

**Acceptance:**
- Unit test: synthetic ticks, stall input, assert transition at 3.0s ± 0.2s.

---

### S-14 — ExitMonitor (O-04)
Periodic (1s) sweep of open positions from P01. For each position, asks
the owning strategy for `check_exit(position) -> ExitDecision | None`. If
the decision is `CLOSE`, emit a `STRATEGY_SIGNAL` with action=close. If
the position has no owning strategy, emit `RISK_ALERT("ORPHAN_POSITION", ...)`.

**Acceptance:**
- Unit test: position whose strategy returns `CLOSE` → close signal emitted
  exactly once.
- Integration: kill a strategy mid-flight, orphan alert fires within 2s.

---

### S-15 — BrokerProtocol + router (O-05)
Single `Tradov/TradovB_Broker/TradovB00_BrokerProtocol.py` (may already
exist — verify) with:

```python
class BrokerProtocol(Protocol):
    def submit_order(self, order: OrderRequest) -> OrderAck: ...
    def get_order(self, broker_order_id: str) -> OrderStatus: ...
    def cancel_order(self, broker_order_id: str) -> bool: ...
    def get_positions(self) -> list[Position]: ...
    def get_account(self) -> AccountSnapshot: ...
```

B02, B40, and a new `TradovR02_PaperBroker` all implement it. R04 accepts
`broker: BrokerProtocol` and deletes the two-path `_broker_submit` branch.

**Acceptance:**
- `_broker_submit` becomes 10 lines with no broker-specific branching.
- Swap `--mode live` ↔ `--mode paper` changes only which broker is
  constructed.

---

### S-16 — Q10 protocol-compliance gate wired to pre-commit + CI
`TradovQ10_ProtocolComplianceGate.py` should run on every commit and PR.
Add `.pre-commit-config.yaml` hook and a GitHub Actions step (or
equivalent) that fails if any `D_Strategies`, `E_Risk`, `R_Runtime`, or
`B_Broker` module violates its protocol.

**Acceptance:**
- Intentionally break one protocol contract in a test branch; CI fails.

---

## 6. Suggested Landing Order

1. **S-03** (single EventManager) — precondition for all event-based tests.
2. **S-09** (delete D01 shadow classes) — cleans up the thicket.
3. **S-10** (tighten validate_signal) — type safety.
4. **S-08** (R04 event_manager) — enables fill events.
5. **S-05 + S-11** (real fill detection) — ground truth.
6. **S-06** (position tracking) — depends on real fills.
7. **S-02** (DataFeed startup) — now data has somewhere to go.
8. **S-13** (DataFreshnessMonitor) — closes the staleness loop.
9. **S-12** (SessionSupervisor) — replaces launcher soup.
10. **S-01** (launch routing) — now safe to restructure Q14.
11. **S-07** (paper engine) — leverages S-15 if landed.
12. **S-15** (broker protocol) — can land in parallel with S-07.
13. **S-14** (ExitMonitor) — nice-to-have, not blocking.
14. **S-16** (CI gate) — always last, gates future regressions.

Each spec should land as its own PR with unit + (where listed) integration
tests. Total estimated work: **~12-18 PRs**, landable in **~2 calendar
weeks** by a single focused agent.

---

## 7. Test Plan Overview

- **Unit:** each spec ships with the unit tests listed above.
- **Integration rig:** `tests/integration/test_autonomous_paper_loop.py` —
  spins up the full paper pipeline with a mock market data generator,
  asserts the full MARKET_DATA → STRATEGY_SIGNAL → ORDER_FILLED →
  POSITION_UPDATED → dashboard-observed chain completes within 5s and
  state is consistent.
- **Sandbox:** `tests/live/test_tradier_sandbox_loop.py` (gated on
  `TRADOV_RUN_SANDBOX=1`) — runs the real Tradier sandbox loop for 60s,
  places and cancels 5 orders, asserts no "filled" metric increments on
  canceled orders.
- **Soak:** run the paper loop for 4 hours, assert no EventManager queue
  growth, no thread leak, heartbeat present throughout.

---

## 8. Out-of-Scope for This Audit

- Strategy logic quality (D series internals) — separate audit.
- Options analytics correctness (V09 IV, Greeks) — separate audit.
- GUI architecture beyond the wiring points in O-06.
- Performance tuning; correctness first.
