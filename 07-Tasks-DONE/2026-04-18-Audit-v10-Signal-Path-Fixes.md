# Audit v10 — Signal Path Fixes Implementation Report

**Date:** 2026-04-18
**Branch:** `refactor/g05-widget-extraction`
**Source audit:** `04-CodeBase-Audits/2026-04-19-Codebase-Audit-v10-Post-v9-Verification.md`
**Primary modules changed:**
- `Tradov/TradovD_Strategies/TradovD31_StrategyOrchestrator.py`
- `Tradov/TradovR_Runtime/TradovR14_ExitMonitor.py`
- `Tradov/TradovR_Runtime/TradovR04_LiveEngine.py`
- `Tradov/TradovQ_Scripts/TradovQ10_ProtocolComplianceGate.py`
- `Tradov/TradovT_Testing/TradovT129_ProtocolCompliance.py`

---

## 1. Executive Summary

This report documents the full implementation of all items from the v10 post-verification audit. The audit identified the system as **NOT READY** due to two P0 defects that silently dropped every strategy signal before it could reach the broker. The session resolved all 9 audit items across two priority tiers (P0/P1) plus four observability/improvement items (O/I).

**Root cause (P0-A):** Three stale imports in a single `try` block inside `TradovD31_StrategyOrchestrator` caused the entire soft-import block to fail, leaving `TRADOV_MODULES_AVAILABLE = False`. As a result, `EventType` was `None`, all event subscriptions were silently skipped, and no strategy signal ever reached the risk gate. The audit correctly identified `PerformanceMetrics` as one culprit; investigation found a second: `StrategySignal` and `StrategyState` imported from `TradovD01_BaseStrategy`, neither of which exist in that module.

**Root cause (P0-B):** The `_on_strategy_signal` handler passed a raw `dict` directly to `RiskManager.validate_signal()`. E01 enforces `isinstance(request, RiskValidationRequest)` at line 666 and raises `TypeError` on any other type. Every signal that made it past P0-A was immediately dropped at P0-B.

**Root cause (P1-B):** `TradovR14_ExitMonitor._emit_close_signal` emitted `{"action": "close", "quantity": view.quantity}` with no `"side"` key and a potentially negative `quantity` for short positions. `TradovR04_LiveEngine._broker_submit` resolved the missing side by mapping every non-buy action to `OrderSide.SELL`, causing short-position close orders to be submitted as additional shorts.

After fixes, the full signal path is verified end-to-end: `EventType.STRATEGY_SIGNAL` subscription registers, `RiskValidationRequest` is constructed and passes E01, and the correct close direction is resolved for both long and short positions. All 15 T129 tests pass.

---

## 2. Audit Item Inventory

| ID | Priority | Description | Status |
|---|---|---|---|
| P0-A | Critical | D31 soft-import failure → `TRADOV_MODULES_AVAILABLE = False` → no subscriptions | ✅ Fixed |
| P0-B | Critical | Raw dict passed to `validate_signal()` → `TypeError` → every signal dropped | ✅ Fixed |
| P1-B | High | Short-position close emitted as SELL instead of BUY | ✅ Fixed |
| P1-A | High | Q10 Gate 5 false-positive on `TradierClient` (`**kwargs` VAR_KEYWORD param) | ✅ Fixed |
| O-7 | Observability | Missing end-to-end regression test for the P0-A/P0-B signal path | ✅ Added |
| O-8/I-5 | Observability | No CI gate for D31 import health or subscription wiring | ✅ Added |
| I-1 | Improvement | Soft-import fallback logged at `INFO` — invisible in production monitoring | ✅ Fixed |
| I-4 | Improvement | No Prometheus counters for silently dropped signals | ✅ Added |

---

## 3. P0-A — D31 Import Failure and Subscription Wiring

### 3.1 Root Cause (deeper than audit noted)

The audit flagged `PerformanceMetrics` (imported from `TradovU15_PerformanceMetrics`) as the failing import. Verification against `TradovU15` confirmed it exports `PerformanceCalculator` and `PerformanceReport` — not `PerformanceMetrics`. A second failing import was found in the **same** `try` block:

```python
from TradovD_Strategies.TradovD01_BaseStrategy import BaseStrategy, StrategySignal, StrategyState
```

`TradovD01_BaseStrategy` exports `TradingSignal`, not `StrategySignal`, and has no `StrategyState`. Both `StrategySignal` and `StrategyState` were marked `# noqa: F401` (unused), so linting never surfaced the import error. Because both bad imports were inside a single `try` block, either one failing caused `TRADOV_MODULES_AVAILABLE = False` and `EventType = None`.

A third issue was found during subscription setup: `_setup_event_subscriptions` subscribed to `EventType.RISK_ALERT`, which does not exist in the EventType enum. Valid risk-related events include `RISK`, `RISK_LIMIT_BREACH`, `RISK_VIOLATION`, and `ALERT`. The entire subscription block was inside one `try`, so this caused all three subscriptions (`MARKET_DATA`, `STRATEGY_SIGNAL`, `RISK_ALERT`) to fail silently.

### 3.2 Fixes Applied

1. **Removed** `from TradovU_Utilities.TradovU15_PerformanceMetrics import PerformanceMetrics # noqa: F401` — the name does not exist.
2. **Removed** `PerformanceMetrics = None` from the fallback stub.
3. **Changed** D01 import from `BaseStrategy, StrategySignal, StrategyState` → `BaseStrategy` only (the other two were unused).
4. **Fixed** `EventType.RISK_ALERT` → `EventType.RISK_VIOLATION` in `_setup_event_subscriptions`.
5. **Added** `global EventType` re-import guard at the top of `_setup_event_subscriptions` — if the soft-import fallback left `EventType = None`, a direct re-import is attempted before subscriptions are registered.

### 3.3 Verification

```python
from Tradov.TradovD_Strategies.TradovD31_StrategyOrchestrator import (
    TRADOV_MODULES_AVAILABLE, StrategyOrchestrator
)
from Tradov.TradovA_Core.TradovA05_EventManager import get_event_manager, EventType

print(TRADOV_MODULES_AVAILABLE)   # True

em = get_event_manager(); em.start()
before = len(em.handlers.get(EventType.STRATEGY_SIGNAL, []))  # 0
orch = StrategyOrchestrator(event_manager=em)
after  = len(em.handlers.get(EventType.STRATEGY_SIGNAL, []))  # 1
```

Result: `TRADOV_MODULES_AVAILABLE: True`, `STRATEGY_SIGNAL handlers: 1`, `MARKET_DATA handlers: 1`.

---

## 4. P0-B — RiskValidationRequest Construction

### 4.1 Root Cause

`_on_strategy_signal` contained:

```python
result = risk_manager.validate_signal(signal)   # signal is a raw dict
```

`TradovE01_RiskManager.validate_signal()` (line 666) enforces:

```python
if not isinstance(request, RiskValidationRequest):
    raise TypeError(...)
```

Every call therefore raised `TypeError`, which was caught by the outer `except Exception`, causing the signal to be silently dropped with an `ERROR` log entry.

### 4.2 Fix Applied

Replaced the raw call with a full `RiskValidationRequest` construction block that maps the signal dict to the canonical `BoundarySignalType` enum and populates all typed fields before crossing the D↔E series boundary.

**Action map:**

| Signal `action` / `side` | `BoundarySignalType` |
|---|---|
| `buy`, `buy_to_open`, `buy_to_close` | `BUY` |
| `sell`, `sell_to_open`, `sell_to_close` | `SELL` |
| `close` | `CLOSE` |
| `adjust` | `ADJUST` |
| `hold` | `HOLD` |
| (default) | `BUY` |

**Field mapping:**

| `RiskValidationRequest` field | Source in signal dict |
|---|---|
| `symbol` | `signal["symbol"]` |
| `quantity` | `int(float(signal["quantity"] or 0))` |
| `signal_type` | `_ACTION_MAP[action or side]` |
| `strategy_id` | `signal["strategy_id"]` |
| `entry_price` | `signal["price"] or signal["limit_price"] or signal["entry_price"]` |
| `stop_loss` | `signal["stop_loss"]` |
| `take_profit` | `signal["take_profit"]` |
| `confidence` | `signal["confidence"]` |
| `metadata` | all keys not in the known set |

### 4.3 Verification (end-to-end with strict mock)

```python
# Strict mock — raises if not RiskValidationRequest
dispatched = []
def strict_validate(req):
    assert isinstance(req, RiskValidationRequest), f"Expected RVR, got {type(req)}"
    dispatched.append(req)
    return {"approved": True}

risk.validate_signal = strict_validate
em.emit(EventType.STRATEGY_SIGNAL, data={"action": "buy", "symbol": "SPY", ...})
# Result: validate_signal called: 1, dispatched: 1 — PASSED
```

---

## 5. P1-B — Short-Position Close Direction

### 5.1 Root Cause

`TradovR14_ExitMonitor._emit_close_signal` emitted:

```python
data={
    "action": "close",
    "quantity": view.quantity,   # may be negative for shorts
    ...
}
```

No `"side"` key was present. `TradovR04_LiveEngine._broker_submit` resolved direction as:

```python
side = OrderSide.BUY if side_str in ("buy", ...) else OrderSide.SELL
```

Since `"close"` is not in the buy-action set, it fell to `OrderSide.SELL` unconditionally. A short position (quantity < 0) would be submitted as an additional short rather than a buy-to-close.

### 5.2 Fix Applied

**R14 `_emit_close_signal`** — add `"side"` key derived from position sign and always emit `abs(quantity)`:

```python
close_side = "sell" if (view.quantity or 0) > 0 else "buy"
self.em.emit(
    event_type=EventType.STRATEGY_SIGNAL,
    data={
        "action": "close",
        "side": close_side,          # NEW
        "quantity": abs(view.quantity),   # always positive magnitude
        ...
    },
)
```

**R04 `_broker_submit`** — resolve `"close"` via position tracker instead of defaulting to SELL:

```python
if side_str == "close":
    _qty = 0.0
    _pt = getattr(self, "_position_tracker", None)
    if _pt is not None:
        try:
            _pos = _pt.get_position(order.get("symbol", ""))
            _qty = float(getattr(_pos, "quantity", 0.0) or 0.0)
        except Exception:
            _qty = 0.0
    # Long (qty > 0) → SELL; Short (qty ≤ 0) → BUY
    side = OrderSide.SELL if _qty > 0 else OrderSide.BUY
else:
    side = OrderSide.BUY if side_str in ("buy", ...) else OrderSide.SELL
```

R14 now sets the explicit `"side"` key, which takes priority in R04's `order.get("side", order.get("action", "buy"))` lookup. The position-tracker fallback in R04 handles legacy close signals from other emitters.

### 5.3 Verification

```python
# Long position (qty > 0) → should emit side='sell'
mon._sweep_once()
assert emitted[-1]["side"] == "sell"    # PASSED

# Short position (qty < 0) → should emit side='buy'
mon2._sweep_once()
assert emitted[-1]["side"] == "buy"     # PASSED

# R04 passthrough for explicit side key
order = {"symbol": "SPY", "side": "buy", "action": "close", "quantity": 2}
# side_str = "buy" → OrderSide.BUY → correct (buy-to-close short)  # PASSED
```

---

## 6. P1-A — Q10 Gate 5 VAR_KEYWORD False-Positive

### 6.1 Root Cause

Gate 5 built the set of required broker protocol params as:

```python
proto_params = set(inspect.signature(BrokerProtocol.place_order).parameters) - {"self"}
```

`BrokerProtocol.place_order` declares `**kwargs` (a `VAR_KEYWORD` parameter). Its string name `"kwargs"` was included in `proto_params`. `TradierClient.place_order` uses explicit positional params and no `**kwargs`, so `missing_params = {"kwargs"}` — triggering a Gate 5 FAIL on a perfectly compliant implementation.

### 6.2 Fix Applied

Filter `VAR_KEYWORD` and `VAR_POSITIONAL` kinds from the protocol's parameter set before computing the diff:

```python
proto_params = {
    name
    for name, p in proto_sig.parameters.items()
    if name != "self"
    and p.kind not in (
        inspect.Parameter.VAR_POSITIONAL,
        inspect.Parameter.VAR_KEYWORD,
    )
}
```

### 6.3 Result

```
[Q10] Gate 5: OK   — Tradov.TradovB_Broker.TradovB40_TradierClient.TradierClient satisfies BrokerProtocol
[Q10] Gate 5: OK   — Tradov.TradovR_Runtime.TradovR15_PaperBroker.PaperBroker satisfies BrokerProtocol
[Q10] Gate 5: BrokerProtocol compliance OK
```

---

## 7. O-7 — End-to-End Regression Tests (T129)

### 7.1 Tests Added to `EndToEndHappyPathTest`

Three new test methods were added to `TradovT129_ProtocolCompliance.EndToEndHappyPathTest`:

| Test | What it verifies |
|---|---|
| `test_strategy_orchestrator_modules_available` | `TRADOV_MODULES_AVAILABLE is True` — catches any return of P0-A |
| `test_strategy_orchestrator_subscribes_to_events` | After construction, `STRATEGY_SIGNAL` handler count increases — catches broken subscription wiring |
| `test_strategy_signal_dispatched_through_risk_gate` | Full O-7 test: emits a signal dict, a strict mock validates `isinstance(req, RiskValidationRequest)`, sets a threading.Event, waits 2 s — catches any return of P0-B |

### 7.2 Result

```
======================== 15 passed, 1 warning in 29.99s ========================
```

All 15 T129 tests pass. The coverage failure (`20.32% < 60%`) is a global pytest threshold unrelated to these tests.

---

## 8. O-8/I-5 — Q10 Gate 7 (Orchestrator Smoke)

A new `check_strategy_orchestrator_health()` function was added to `TradovQ10_ProtocolComplianceGate` and wired into `main()` as **Gate 7**. It runs two checks on every CI gate invocation:

1. **Import health** — imports D31 and asserts `TRADOV_MODULES_AVAILABLE is True`. A soft-import fallback active in production would have been invisible to all prior gates.
2. **Subscription smoke** — instantiates `StrategyOrchestrator(event_manager=em)` and asserts the `STRATEGY_SIGNAL` handler count increases. This directly replays the P0-A failure mode.

```
[Q10] Gate 7: OK   — D31 TRADOV_MODULES_AVAILABLE is True
[Q10] Gate 7: OK   — D31 registered STRATEGY_SIGNAL subscription
```

---

## 9. I-1 — Loud Fallbacks

The soft-import fallback log level in D31 was changed from `logging.info` to `logging.critical`, and a `TRADOV_STRICT_IMPORTS=1` escape hatch was added:

```python
except ImportError as e:
    logging.critical(
        "CRITICAL — D31 soft-import failed; strategy signal routing is DISABLED: %s. "
        "Set TRADOV_STRICT_IMPORTS=1 to raise on startup.",
        e,
    )
    import os as _os
    if _os.environ.get("TRADOV_STRICT_IMPORTS") == "1":
        raise
    TRADOV_MODULES_AVAILABLE = False
```

A production deployment running with log aggregation (e.g. Grafana Loki, CloudWatch) now surfaces an import failure as a CRITICAL alert rather than a silent INFO entry. Setting `TRADOV_STRICT_IMPORTS=1` in staging converts the silent failure to a hard startup crash, enabling pre-deployment detection.

---

## 10. I-4 — Prometheus Drop Counters

Two new Prometheus metrics were added at module level in D31:

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `spyder_signals_dropped_total` | Counter | `stage`, `reason` | Incremented at each early-return drop point in `_on_strategy_signal` |
| `spyder_subscriptions_active` | Gauge | — | Set to the count of `STRATEGY_SIGNAL` handlers after subscription setup |

`_count_drop(stage, reason)` is called at four drop points:

| `stage` | `reason` | Condition |
|---|---|---|
| `pre_risk` | `empty_event` | `event.data` is falsy |
| `pre_risk` | `no_risk_gate` | No `risk_manager` could be found or it lacks `validate_signal` |
| `pre_risk` | `rvr_import_failed` | `RiskValidationRequest` import failed in both package paths |
| `pre_risk` | `rvr_build_failed` | `RiskValidationRequest(...)` constructor raised |

Falls back to no-op stubs when `prometheus_client` is not installed. Handles duplicate metric registration (module reload in tests) by catching `ValueError` and retrieving the existing collector from `REGISTRY`.

---

## 11. Final Q10 Gate Status

```
[Q10] RNG gate OK — no unguarded np.random in production packages
[Q10] Protocol compliance OK
[Q10] Gate 5: OK   — TradierClient satisfies BrokerProtocol
[Q10] Gate 5: OK   — PaperBroker satisfies BrokerProtocol
[Q10] Gate 5: BrokerProtocol compliance OK
[Q10] Gate 6: OK   — TradovD31_StrategyOrchestrator
[Q10] Gate 6: OK   — TradovR12_SessionSupervisor
[Q10] Gate 6: OK   — TradovR13_FillReconciler
[Q10] Gate 6: OK   — TradovR14_ExitMonitor
[Q10] Gate 6: OK   — TradovR15_PaperBroker
[Q10] Gate 6: OK   — TradovE01_RiskManager
[Q10] Gate 6: OK   — TradovE24_DataFreshnessMonitor
[Q10] Gate 6: OK   — TradovB21_BrokerProtocol
[Q10] Gate 6: OK   — TradovA05_EventManager
[Q10] Gate 6: all module imports OK
[Q10] Gate 7: OK   — D31 TRADOV_MODULES_AVAILABLE is True
[Q10] Gate 7: OK   — D31 registered STRATEGY_SIGNAL subscription
```

Pre-existing warnings (datetime.utcnow() × 5, datetime.now() naive × 1689) are out of scope for this session and unchanged.

---

## 12. Signal Path — Before / After

### Before (broken)

```
EventManager.emit(STRATEGY_SIGNAL)
  └─ _on_strategy_signal() [NEVER CALLED — no subscription registered]
       ↑ TRADOV_MODULES_AVAILABLE = False
       ↑ EventType = None
       ↑ _setup_event_subscriptions() failed silently on RISK_ALERT
```

### After (working)

```
EventManager.emit(STRATEGY_SIGNAL)
  └─ _on_strategy_signal(event)
       ├─ signal = event.data          [not empty]
       ├─ risk_manager = get_risk_manager()
       ├─ Build RiskValidationRequest  [typed boundary crossing]
       ├─ risk_manager.validate_signal(rvr)
       │    ├─ approved → _dispatch_approved_signal(signal)
       │    └─ rejected → RISK_VIOLATION event + Prometheus counter
       └─ [drop path] _count_drop(stage, reason) → Prometheus
```

### Short-position close — before / after

```
Before:  ExitMonitor → {"action": "close", "quantity": -2}
         LiveEngine  → side_str = "close" → else → OrderSide.SELL  [WRONG — doubles short]

After:   ExitMonitor → {"action": "close", "side": "buy", "quantity": 2}
         LiveEngine  → side_str = "buy" → OrderSide.BUY             [CORRECT — buy-to-close]
```

---

## 13. Files Modified

| File | Nature of change |
|---|---|
| `Tradov/TradovD_Strategies/TradovD31_StrategyOrchestrator.py` | P0-A (remove stale imports, fix RISK_ALERT → RISK_VIOLATION, add re-import guard), P0-B (RiskValidationRequest construction), I-1 (critical log + TRADOV_STRICT_IMPORTS), I-4 (Prometheus counters + _count_drop) |
| `Tradov/TradovR_Runtime/TradovR14_ExitMonitor.py` | P1-B (add `"side"` key, use `abs(quantity)` in `_emit_close_signal`) |
| `Tradov/TradovR_Runtime/TradovR04_LiveEngine.py` | P1-B (resolve `"close"` direction via position tracker in `_broker_submit`) |
| `Tradov/TradovQ_Scripts/TradovQ10_ProtocolComplianceGate.py` | P1-A (filter VAR_KEYWORD from Gate 5 proto_params), O-8/I-5 (add Gate 7 `check_strategy_orchestrator_health`) |
| `Tradov/TradovT_Testing/TradovT129_ProtocolCompliance.py` | O-7 (3 new tests: modules-available, subscription registered, end-to-end risk-gate dispatch) |
