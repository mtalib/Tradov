# SPYDER Codebase Audit v10 — Post-v9 Verification

**Date:** 2026-04-19
**Author:** Audit pass following v9 (`2026-04-19-Codebase-Audit-v9-Autonomous-Trading-Readiness.md`)
**Scope:** Verify v9's "ready for autonomous trading" claim end-to-end. Identify remaining anomalies, deficiencies, improvement opportunities.
**Verdict:** **NOT READY for autonomous hands-free trading.** Two new P0 defects silently drop every signal. Strategies emit → orchestrator discards → broker never sees an order. This reaches the same end-state as pre-v9, masked by a green T129 run.

---

## 1. Executive Summary

v9 verified structural wiring (SessionSupervisor start order, ExitMonitor boot, FillReconciler attach, kill switch, Prometheus counters, Q10 Gate 6, T129). All of those claims hold.

What v9 did **not** test: the actual **signal → risk → broker** dispatch path inside [SpyderD31_StrategyOrchestrator.py](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py). That path is broken in two independent ways, either of which alone is sufficient to block autonomous trading:

1. A stale import at D31:79 triggers the soft-import fallback, which sets `EventType = None`. D31 then raises `AttributeError` the first time it tries to subscribe — swallowed by an outer `try/except`. **The orchestrator receives zero events.**
2. Even if subscriptions worked, `_on_strategy_signal` at D31:1697 passes a raw dict to `risk_manager.validate_signal()`, which since E00 boundary-types was added **requires** a `RiskValidationRequest` and raises `TypeError` otherwise. The exception is caught and `return`-ed silently. **Every signal is dropped.**

Two additional defects were found:

3. [Q10 Gate 5](Spyder/SpyderQ_Scripts/SpyderQ10_ProtocolComplianceGate.py#L312-L327) has a false-positive on `TradierClient` (treats the protocol's `**kwargs` as a required param). This also means v9's acceptance criterion "Q10 exits 0" is not actually met.
4. [R04 `_broker_submit` side mapping](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1413-L1418) maps `action="close"` → `SELL` unconditionally. For short-premium structures (credit spreads, short straddles, iron condors) this will *add* to the short position instead of closing it.

v9's green tests pass because T129's `EndToEndHappyPathTest` validates ExitMonitor sweep mechanics and D31 *instantiation*, but never drives a signal through the risk gate to a (paper) broker.

---

## 2. What v9 Got Right (verified)

| Claim | File / Line | Verified |
|---|---|---|
| P0-1 `_initialize_strategy_registry` exists | [D31:1617](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L1617) | ✅ |
| P0-2 Reconciler + PositionTracker wired into LiveEngine | [R12:359](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L359) | ✅ |
| P0-3 ExitMonitor lifecycle + boot orphan sweep | [R12:394-429](Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py#L394-L429) | ✅ |
| P1-3 E24 DataFreshnessMonitor + E02 shim | — | ✅ |
| P1-5 D25 regime wiring | — | ✅ |
| P2-1 Q14 `_start_live_engine` removed | — | ✅ |
| O-1 Q10 Gate 6 import smoke test | [Q10:344-383](Spyder/SpyderQ_Scripts/SpyderQ10_ProtocolComplianceGate.py#L344-L383) | ✅ |
| O-3 `_broker_submit` reconciler guard | [R04:1391-1395](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1391-L1395) | ✅ |
| O-4 KILL_SWITCH in A05 + R04 | [R04:1396-1401](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1396-L1401) | ✅ |
| O-5 `dry_run=True` in SessionSupervisor | — | ✅ |
| O-6 Prometheus counters in R13/R14 | [R13:169,274](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py), [R14:254,291](Spyder/SpyderR_Runtime/SpyderR14_ExitMonitor.py) | ✅ |
| T129 12 tests pass | — | ✅ (but inadequate coverage — see §4) |

---

## 3. New Defects (MISSED by v9)

### P0-A — D31 import fallback disables all event subscriptions **[CRITICAL]**

**File:** [Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py:79](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L79)

```python
from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics  # noqa: F401
```

`SpyderU15_PerformanceMetrics` exports `PerformanceCalculator` and `PerformanceReport` — there is no symbol `PerformanceMetrics`. The import raises `ImportError`, the whole `try` block at D31:75-99 aborts, and the `except ImportError` at D31:100-116 runs:

```python
EventType = None  # type: ignore[assignment]
```

Then in `_setup_event_subscriptions` at D31:1632-1642:

```python
try:
    if self.event_manager:
        self.event_manager.subscribe(EventType.MARKET_DATA, self._on_market_data_event)
        # ^^^^^^^^^^^^^^^^^^^^^ AttributeError: 'NoneType' has no attribute 'MARKET_DATA'
        ...
except Exception as e:
    self.logger.error("Error setting up event subscriptions: %s", e, exc_info=True)
```

The error is logged and swallowed. `self.event_manager` is valid (re-acquired at D31:319-331 via direct `from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager`) but `EventType` stays `None`. **D31 never subscribes to any event** — no `MARKET_DATA`, no `STRATEGY_SIGNAL`, no `RISK_ALERT`.

Confirmed by running:
```python
from Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator import SPYDER_MODULES_AVAILABLE
# → False
```

**Consequences:**
- Strategies that emit signals via `D01_BaseStrategy` `self.event_manager.emit(EventType.STRATEGY_SIGNAL, ...)` have no listener in D31.
- Market data never reaches strategies through D31's fan-out at D31:1667-1673 (individual strategies only get ticks if they subscribed themselves — most do not).
- ExitMonitor's close signals are never acted upon.
- **Net effect: strategy-driven autonomous trading is non-functional even though all other wiring is correct.**

**Fix (preferred):**

```python
# D31:79 — remove the dead import (PerformanceMetrics is not referenced)
# from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics  # noqa: F401
```

Also remove the fallback stub at D31:110 (`PerformanceMetrics = None`). A grep confirms the name is unused elsewhere in D31.

**Defensive hardening:** harden `_setup_event_subscriptions` so a future silent fallback cannot disable it:

```python
def _setup_event_subscriptions(self):
    global EventType
    if EventType is None:
        try:
            from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType as _ET
            EventType = _ET
        except Exception:
            self.logger.critical("D31: EventType unavailable — event subscriptions DISABLED")
            return
    try:
        if self.event_manager:
            self.event_manager.subscribe(EventType.MARKET_DATA, self._on_market_data_event)
            self.event_manager.subscribe(EventType.STRATEGY_SIGNAL, self._on_strategy_signal)
            self.event_manager.subscribe(EventType.RISK_ALERT, self._on_risk_alert)
    except Exception as e:
        self.logger.error("Error setting up event subscriptions: %s", e, exc_info=True)
```

**Acceptance:** `SPYDER_MODULES_AVAILABLE` is `True` after a fresh import; after `StrategyOrchestrator(...)` construction, `event_manager._subscribers[EventType.STRATEGY_SIGNAL]` contains `_on_strategy_signal`.

---

### P0-B — `_on_strategy_signal` passes `dict` to `validate_signal`; E01 now rejects it **[CRITICAL]**

**File:** [Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py:1697](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L1697)

```python
try:
    result = risk_manager.validate_signal(signal)   # `signal` is a raw dict
except Exception as exc:
    self.logger.error("Risk validate_signal raised: %s", exc, exc_info=True)
    return                                          # ← every signal dropped silently
```

`BaseStrategy` emits `signal.to_dict()` at [D01:728](Spyder/SpyderD_Strategies/SpyderD01_BaseStrategy.py#L728) and ExitMonitor emits a dict at [R14:278](Spyder/SpyderR_Runtime/SpyderR14_ExitMonitor.py#L278). Both therefore arrive as dicts. Meanwhile E01 at [E01:666](Spyder/SpyderE_Risk/SpyderE01_RiskManager.py#L666) now enforces:

```python
if not isinstance(request, RiskValidationRequest):
    raise TypeError(f"validate_signal expects RiskValidationRequest, got {type(request).__name__}")
```

Confirmed: `rm.validate_signal({'action': 'close', ...})` raises `TypeError: validate_signal expects RiskValidationRequest, got dict`. The `except Exception` swallows it, the handler `return`s, no dispatch happens.

**Fix:** Construct a `RiskValidationRequest` from the dict. Use the R11 pattern at [R11:798-812](Spyder/SpyderR_Runtime/SpyderR11_PaperStrategyRunner.py#L798-L812) as a reference:

```python
# D31:_on_strategy_signal — replace line ~1697
from Spyder.SpyderE_Risk.SpyderE00_RiskProtocol import RiskValidationRequest

try:
    request = RiskValidationRequest(
        signal_id=signal.get("signal_id", f"sig-{int(time.time() * 1e6)}"),
        strategy_id=signal.get("strategy_id", "unknown"),
        symbol=signal.get("symbol", ""),
        action=signal.get("action", "buy"),
        quantity=float(signal.get("quantity", 0.0) or 0.0),
        price=float(signal.get("price") or signal.get("limit_price") or 0.0),
        metadata={k: v for k, v in signal.items() if k not in {
            "signal_id", "strategy_id", "symbol", "action", "quantity", "price"
        }},
    )
    result = risk_manager.validate_signal(request)
except Exception as exc:
    self.logger.error("Risk validate_signal raised: %s", exc, exc_info=True)
    return
```

(Exact `RiskValidationRequest` field names should be verified against `SpyderE00_RiskProtocol`; adjust as necessary.)

**Consider also:** R04 `LiveEngine.process_signal`/`_broker_submit` already performs its own risk check before submission. Risk-validating twice (D31 pre-dispatch + R04 pre-submit) is defensible (defense-in-depth), but only if D31 is actually called. Confirm with the risk team that the double gate is intended; if not, D31 should skip validation and act as a pure dispatcher to R04.

**Acceptance:** Emit a synthetic `STRATEGY_SIGNAL` dict on the event bus with a paper broker attached → `PaperBroker._orders` grows by 1 → ORDER_FILLED event fires within `fill_delay_s + 0.5s`.

---

### P1-A — Q10 Gate 5 false-positive on `TradierClient`

**File:** [Spyder/SpyderQ_Scripts/SpyderQ10_ProtocolComplianceGate.py:312-327](Spyder/SpyderQ_Scripts/SpyderQ10_ProtocolComplianceGate.py#L312-L327)

Running Q10 today:
```
[Q10] Gate 5: FAIL — Spyder.SpyderB_Broker.SpyderB40_TradierClient.TradierClient.place_order missing params: {'kwargs'}
[Q10] Gate 5: OK — PaperBroker satisfies BrokerProtocol
```

Cause: [B21:43-51](Spyder/SpyderB_Broker/SpyderB21_BrokerProtocol.py#L43-L51) declares `place_order(..., **kwargs)`. Gate 5 inspects the protocol's `inspect.signature(...)` and collects every parameter name — including `kwargs` (the VAR_KEYWORD name). `TradierClient.place_order` at [B40:866-876](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L866-L876) has no `**kwargs`, so the set diff reports `{'kwargs'}` missing. This is backwards: a protocol `**kwargs` is a *relaxation* (any extra kw is allowed), not a *requirement*.

**Fix:** When building `proto_params`, filter out `VAR_KEYWORD` and `VAR_POSITIONAL`:

```python
# Q10:~312
proto_sig = inspect.signature(getattr(BrokerProtocol, method_name))
proto_params = {
    name for name, p in proto_sig.parameters.items()
    if name != "self" and p.kind not in (
        inspect.Parameter.VAR_POSITIONAL,
        inspect.Parameter.VAR_KEYWORD,
    )
}
impl_sig = inspect.signature(getattr(impl_cls, method_name))
impl_has_var_kw = any(
    p.kind == inspect.Parameter.VAR_KEYWORD for p in impl_sig.parameters.values()
)
impl_params = {name for name, p in impl_sig.parameters.items() if name != "self"}

missing = proto_params - impl_params
# If impl has **kwargs it can absorb any protocol param of the same name, so
# only complain about params the impl explicitly lacks and cannot absorb:
if impl_has_var_kw:
    missing = set()  # or keep names the protocol marks as positional-only
```

**Bonus:** note that `BrokerProtocol.place_order`'s signature (from B21:43-51) uses positional parameters `symbol, side, quantity, order_type`, which TradierClient matches — the gate should pass cleanly once `kwargs` is excluded.

**Acceptance:** `python -m Spyder.SpyderQ_Scripts.SpyderQ10_ProtocolComplianceGate` — Gate 5 reports OK for both `TradierClient` and `PaperBroker`; exit code reflects only legitimate failures.

---

### P1-B — R04 `_broker_submit` side mapping breaks short-position closes

**File:** [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:1413-1418](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1413-L1418)

```python
side_str = str(order.get("side", order.get("action", "buy"))).lower()
side = (
    OrderSide.BUY
    if side_str in ("buy", "buy_to_open", "buy_to_close")
    else OrderSide.SELL
)
```

ExitMonitor emits `{"action": "close", ...}` regardless of long/short direction. `"close"` isn't in the BUY set → mapped to `SELL`. For **long** positions this happens to be correct (sell-to-close). For **short-premium** strategies (credit spreads, short straddles, iron condors — the bread-and-butter of SPYDER) this **doubles the short exposure** at the intended exit moment. Worst possible time to be wrong.

**Fix:** Resolve direction from position state before mapping:

```python
# Inside _broker_submit, after computing side_str:
if side_str == "close":
    qty = 0.0
    pt = self._position_tracker
    if pt is not None:
        try:
            pos = pt.get_position(order["symbol"])
            qty = float(getattr(pos, "quantity", 0.0) or 0.0)
        except Exception:
            qty = 0.0
    # Long (qty > 0) → SELL to close. Short (qty < 0) → BUY to close.
    side = OrderSide.SELL if qty > 0 else OrderSide.BUY
else:
    side = (
        OrderSide.BUY
        if side_str in ("buy", "buy_to_open", "buy_to_close")
        else OrderSide.SELL
    )
```

Also update [R14 `_emit_close_signal`](Spyder/SpyderR_Runtime/SpyderR14_ExitMonitor.py#L271-L290) so the close signal carries the sign of the current quantity, freeing R04 from re-querying the position tracker:

```python
# R14 ~line 285:
data={
    "signal_id": signal_id,
    "action": "close",
    "side": "sell" if view.quantity > 0 else "buy",   # NEW
    "symbol": view.symbol,
    "strategy_id": strategy_id,
    "quantity": abs(view.quantity),                    # always positive magnitude
    "reason": "exit_monitor",
    "unrealized_pnl": view.unrealized_pnl,
},
```

Then R04 can trust `order["side"]` when present and only fall back to the position-tracker lookup if missing.

**Acceptance:** Paper-broker integration test: open a short credit spread (quantity < 0) → ExitMonitor fires CLOSE → BUY order reaches the broker. Repeat with a long position → SELL order reaches the broker.

---

## 4. Coverage Gaps (Why v9 Didn't Catch This)

T129's `EndToEndHappyPathTest` validates:
- ExitMonitor sweep mechanics in isolation (orphan detection, close emission).
- SessionSupervisor start-order and component lifecycle.
- D31 *instantiation* with a real EventManager.

It does **not** drive a `STRATEGY_SIGNAL` end-to-end through D31 → RiskManager → LiveEngine → Broker. Two lines of test code would have caught both P0-A and P0-B.

### O-7 (NEW) — Add one end-to-end dispatch test

Suggested placement: [T129](Spyder/SpyderT_Testing/SpyderT129_ProtocolCompliance.py).

```python
def test_strategy_signal_reaches_broker(self):
    """
    STRATEGY_SIGNAL → D31._on_strategy_signal → RiskManager.validate_signal
    → LiveEngine.process_signal → PaperBroker.place_order → ORDER_FILLED.

    Fails on P0-A (EventType is None, so D31 never subscribes) and
    on P0-B (validate_signal dict → TypeError → signal dropped).
    """
    em = get_event_manager()
    broker = PaperBroker(event_manager=em, fill_delay_s=0.0)
    reconciler = FillReconciler(broker=broker, event_manager=em, poll_cadence_market=0.05)
    engine = LiveEngine(mode=TradingMode.PAPER, broker=broker, fill_reconciler=reconciler, ...)
    risk = RiskManager(...)   # real or minimally-configured
    orch = StrategyOrchestrator(event_manager=em, risk_manager=risk)
    engine.start(); reconciler.start()

    filled = threading.Event()
    em.subscribe(EventType.ORDER_FILLED, lambda _ev: filled.set())

    em.emit(EventType.STRATEGY_SIGNAL, {
        "signal_id": "t-1", "strategy_id": "test", "symbol": "SPY",
        "action": "buy", "quantity": 1, "price": 500.0,
    }, source="test")

    assert filled.wait(timeout=2.0), "STRATEGY_SIGNAL did not reach the broker"
```

### O-8 (NEW) — Q10 Gate 7: Orchestrator construction smoke test

Instantiate `StrategyOrchestrator` with a real EventManager and a stub risk manager; fail the gate if **any** ERROR-level log is emitted during construction *or* if the orchestrator does not hold subscriptions for `MARKET_DATA`, `STRATEGY_SIGNAL`, `RISK_ALERT` after `__init__`. This would have tripped on P0-A without needing a broker or signal.

---

## 5. Improvement Opportunities

### I-1 — Make soft-import fallbacks loud, not silent
The `try/except ImportError` at D31:100-116 is the direct cause of P0-A being invisible for this long. Every fallback should at minimum emit `logger.critical` with the failed imports and the disabled features. Better: raise in non-test contexts, because a D31 that can't see `EventType` has no reason to run.

```python
except ImportError as e:
    logging.critical(
        "D31 soft-import fallback activated — orchestrator will NOT function. Cause: %s", e
    )
    if os.getenv("SPYDER_STRICT_IMPORTS", "1") == "1":
        raise
```

### I-2 — Unify the signal schema
Three emitters (`D01_BaseStrategy`, `R14_ExitMonitor`, `D31` internal) construct signal dicts with slightly different keys (`action` vs `side`, `price` vs `limit_price`, presence/absence of `signal_id`). A single `StrategySignal` dataclass in A05 — with a `.to_dict()` for wire format and a `.to_risk_request()` for E01 — would eliminate the entire class of "wrong field name" bugs this audit uncovered.

### I-3 — Make risk-gate placement a decision, not an accident
Currently the system has two risk gates: D31 (pre-dispatch) and R04 `LiveEngine` (pre-submit). Both silently skip if their inputs are malformed. Pick one as authoritative, document it, and have the other either delegate or be removed. Double-gating with silent failure modes is worse than single-gating.

### I-4 — Prometheus counters for the invisible drops
Add `spyder_signals_dropped_total{stage=...,reason=...}` — incremented in D31 whenever a signal is discarded (no risk manager, validate raised, validate returned False). Also `spyder_subscriptions_active{event_type=...}` gauge set at startup. This makes future P0-A/P0-B regressions catchable from Grafana rather than by reading code.

### I-5 — CI-gate the import health of every orchestration module
Extend [Q10 Gate 6](Spyder/SpyderQ_Scripts/SpyderQ10_ProtocolComplianceGate.py#L344-L383): after importing each module, assert its `SPYDER_MODULES_AVAILABLE` flag (where defined) is `True`. This would fail immediately on the stale `PerformanceMetrics` import at D31:79.

### I-6 — Boot-time self-test
In `SessionSupervisor.start()`, after all components are up and before accepting external traffic, emit a synthetic `STRATEGY_SIGNAL` with a `dry_run=True` marker and require an `ORDER_FILLED` (or a dry-run equivalent event) within a timeout. Fail startup loudly if the round-trip does not complete. This is the run-time analogue of O-7.

---

## 6. Suggested Fix Order for the Coding Agent

1. **P0-A** — D31:79 remove `PerformanceMetrics` import; D31:110 remove the stub; harden `_setup_event_subscriptions` (re-import `EventType` on `None`). Verify `SPYDER_MODULES_AVAILABLE is True`.
2. **P0-B** — D31:1697 build a `RiskValidationRequest` before calling `validate_signal`. Decide (with the risk team) whether D31 even needs to validate, since R04 already does.
3. **O-7** — Add the end-to-end dispatch test to T129. Without it, P0-A/P0-B will regress.
4. **P1-B** — R14 include `side` in close signal; R04 `_broker_submit` resolve close direction from position sign.
5. **P1-A** — Q10 Gate 5 exclude VAR_KEYWORD names from the protocol param set; re-run Q10 to confirm exit 0.
6. **I-5 / O-8** — Strengthen Q10 with an import-health assertion and an Orchestrator construction smoke test.
7. **I-1, I-4** — Loud fallbacks + Prometheus drop counters.
8. **I-2, I-3** — Longer-lived refactors (unified signal schema, single risk gate).
9. **I-6** — Boot-time self-test in SessionSupervisor.

---

## 7. Ready-for-Autonomous-Trading Gate

Before enabling hands-free live trading, **all of the following must hold**:

- [ ] P0-A fixed; `SPYDER_MODULES_AVAILABLE is True` verified in CI.
- [ ] P0-B fixed; `validate_signal` is called with the correct type.
- [ ] O-7 end-to-end test added and passing.
- [ ] P1-B fixed; short-close behavior verified with a paper-broker integration test on a credit spread.
- [ ] P1-A fixed; `python -m Spyder.SpyderQ_Scripts.SpyderQ10_ProtocolComplianceGate` exits 0.
- [ ] Gate 4 (datetime hygiene) resolved or explicitly waived with risk sign-off.
- [ ] At least 48 hours of continuous paper-mode operation where `spyder_signals_dropped_total` stayed flat while `spyder_orders_submitted_total` and `spyder_fills_detected_total` grew monotonically.

Until the first three boxes are checked, the system will silently refuse to trade and the v9 "ready" claim is incorrect.
