# Spyder Codebase Audit v19 — 2026-04-22

> **Status:** Audit complete. Critical fixes implemented. Remaining items specced for coding agent.
> **Branch:** `fix/audit-v14-all`
> **Prior baseline:** Audit v18 — all C1–C7 findings confirmed fixed, 70/70 tests passing.

---

## Executive Summary

This audit covered the complete signal-to-execution wiring chain for the Spyder autonomous SPY options trading system. The primary goal was to confirm all decision-making signals are properly connected before live deployment.

**Key finding:** The system has **two independent trading pipelines**:

| Path | Entry | Engine | Status |
|------|-------|--------|--------|
| **GUI mode** | `A01_Main` → `G05_TradingDashboard` | `R08_PaperTradingQtWorker` | ✅ Functional for paper trading |
| **Headless/CLI mode** | `A06_MasterController` | `D31_StrategyOrchestrator` | 🔴 Was broken; now fixed |

Three **critical bugs** were found in the headless path and fixed in this session. Five **medium/low-priority gaps** remain and are specced below.

---

## Dual-Path Architecture

### GUI Path (A01 → G05 → R08)

```
A01_Main (entry point)
  └─ G05_TradingDashboard
       ├─ S07_CustomMetricsOrchestrator  → regime metrics (DIX, GEX, SWAN)
       ├─ E01_RiskManager               → signal validation
       └─ R08_PaperTradingQtWorker
            ├─ Signal: MA(5)/MA(20) crossover + S08 pivot MR
            ├─ Regime gate: S07 metrics (SWAN ≥ 2.0 blocks entry)
            ├─ Risk gate: E01_RiskManager.validate_signal()
            └─ Execution: B40_TradierClient (paper spreads / condors)
```

**Status:** This path works. E01 risk, S07 regime metrics, and S08 pivot MR signals are all properly wired.

### Headless Path (A06 → D31 → B02 → B40)

```
A06_MasterController (CLI orchestrator)
  ├─ L09_UnifiedRegimeEngine           → ML regime classification
  ├─ D31_StrategyOrchestrator          → signal generation + risk validation
  │    ├─ E01_RiskManager (singleton)  → pre-trade risk check
  │    ├─ I06_AgentMessageBus          → Y01 regime updates
  │    └─ B02_OrderManager             → order execution (mid-price walk)
  └─ Y10_AgentScheduler               → Y01–Y09 autonomous agents
```

**Status:** Was broken (D31 and L09 were stub dicts). Now fixed.

---

## Bugs Fixed in This Session

### FIX-1 (CRITICAL): D31_StrategyOrchestrator — Missing Factory in A06

**File:** `Spyder/SpyderA_Core/SpyderA06_MasterController.py`

**Problem:** `_initialize_component("D31_StrategyOrchestrator")` fell through to the generic stub:
```python
return {"module_id": "D31_StrategyOrchestrator", "status": "initialized"}
```
A plain `dict` was stored in `self.components["D31_StrategyOrchestrator"]`. When `_enable_trading()` retrieved it and called `hasattr(component, "start_orchestration")` → `False`. The orchestration loop never started. **The headless engine could not trade.**

**Fix applied:** Added a proper factory block before the generic stub:
```python
if module_id == "D31_StrategyOrchestrator":
    from SpyderD_Strategies.SpyderD31_StrategyOrchestrator import StrategyOrchestrator
    orchestrator = StrategyOrchestrator(
        base_capital=base_capital,
        event_manager=_event_mgr,
        regime_engine=l09_engine,   # L09 injected if available
    )
    return orchestrator
```

---

### FIX-2 (CRITICAL): L09_RegimeClassifier — Missing Factory in A06

**File:** `Spyder/SpyderA_Core/SpyderA06_MasterController.py`

**Problem:** Same stub-dict fallback for `"L09_RegimeClassifier"`. D31 received no `regime_engine` argument, so it fell back to the inline heuristic regime detector instead of the ML-powered `UnifiedRegimeEngine`.

**Fix applied:** Added factory:
```python
if module_id == "L09_RegimeClassifier":
    from SpyderL_ML.SpyderL09_UnifiedRegimeEngine import UnifiedRegimeEngine
    return UnifiedRegimeEngine()
```

L09 is initialized in the "ML Engine" startup phase (before "Trading Strategies"), so it is available when the D31 factory runs and looks up `self.components.get("L09_RegimeClassifier")`.

---

### FIX-3 (CRITICAL): D31 OrderManager Never Wired

**File:** `Spyder/SpyderA_Core/SpyderA06_MasterController.py` — `_enable_trading()`

**Problem:** `D31_StrategyOrchestrator.set_order_manager()` was never called by A06. D31's `_on_strategy_signal` has three execution paths:
1. `_order_manager.submit_limit_with_walk()` — if set
2. `_live_engine.execute_order()` — fallback
3. Log CRITICAL + drop signal — if neither set

Without `set_order_manager()`, **every approved signal was dropped** with a CRITICAL log entry.

**Fix applied:** Added wiring block in `_enable_trading()`, after `order_mgr.start()` and before `start_orchestration()`:
```python
orchestrator = self.components.get("D31_StrategyOrchestrator")
if orchestrator is not None and hasattr(orchestrator, "set_order_manager"):
    if order_mgr is not None and hasattr(order_mgr, "submit_limit_with_walk"):
        orchestrator.set_order_manager(order_mgr)
        logger.info("D31: OrderManager wired for mid-price-walk execution")
```

---

## Remaining Gaps — Spec for Coding Agent

### SPEC-4 (HIGH): Add A04_Scheduler to A06 Startup Sequence

**File:** `Spyder/SpyderA_Core/SpyderA06_MasterController.py`

**Problem:** `SpyderA04_Scheduler` (APScheduler-based task scheduler) is **never started** in A06. Scheduled tasks — data refresh every 5 minutes, risk checks every 15 minutes, EOD reports — never run in headless mode.

**Specification:**

1. Add a new `StartupSequence` phase to `_get_startup_sequence()`, inserted after "Options Analytics" (non-critical):
   ```python
   StartupSequence(
       phase="Task Scheduler",
       modules=["A04_Scheduler"],
       parallel=False,
       timeout=20,
       critical=False,
   ),
   ```

2. Add factory in `_initialize_component()`:
   ```python
   if module_id == "A04_Scheduler":
       from SpyderA_Core.SpyderA04_Scheduler import Scheduler
       try:
           from SpyderA_Core.SpyderA05_EventManager import get_event_manager as _gem
           event_mgr = _gem()
       except Exception:
           event_mgr = None
       if event_mgr is None:
           logger.warning("A04: EventManager not available — scheduler not started")
           return None
       scheduler = Scheduler(event_manager=event_mgr)
       scheduler.schedule_data_update(interval_minutes=5)
       scheduler.schedule_risk_check(interval_minutes=15)
       scheduler.start()
       logger.info("A04 Scheduler started with data_update(5m) and risk_check(15m)")
       return scheduler
   ```

3. Add graceful shutdown in `_shutdown()`: call `scheduler.stop()` if `A04_Scheduler` is in components.

---

### SPEC-5 (HIGH): Wire R04_LiveEngine as D31 Fallback Execution

**File:** `Spyder/SpyderA_Core/SpyderA06_MasterController.py`

**Problem:** `SpyderR04_LiveEngine` is not in A06's startup sequence. D31's `set_live_engine()` is never called. If B02_OrderManager fails to start, **all approved signals are dropped** with no fallback.

**Specification:**

1. Add `"R04_LiveEngine"` to the "Order Management" startup phase:
   ```python
   StartupSequence(
       phase="Order Management",
       modules=["B02_OrderManager", "B03_PositionTracker", "R04_LiveEngine"],
       ...
   )
   ```

2. Add factory:
   ```python
   if module_id == "R04_LiveEngine":
       from SpyderR_Runtime.SpyderR04_LiveEngine import LiveEngine
       b40 = self.components.get("B01_SpyderClient")
       engine = LiveEngine(broker_client=b40 if b40 else None)
       logger.info("R04 LiveEngine initialized")
       return engine
   ```

3. In `_enable_trading()`, after `set_order_manager()`, add:
   ```python
   live_engine = self.components.get("R04_LiveEngine")
   if orchestrator is not None and hasattr(orchestrator, "set_live_engine"):
       if live_engine is not None:
           orchestrator.set_live_engine(live_engine)
           logger.info("D31: LiveEngine wired as fallback execution path")
   ```

---

### SPEC-6 (MEDIUM): Integrate E19_UnifiedRiskCoordinator as Background Portfolio Monitor

**File:** `Spyder/SpyderA_Core/SpyderA06_MasterController.py` and `Spyder/SpyderE_Risk/SpyderE19_UnifiedRiskCoordinator.py`

**Problem:** `SpyderE19_UnifiedRiskCoordinator` is never instantiated and never called. Portfolio-level risk (VaR, CVaR, correlation risk, Greeks aggregation) is never monitored at runtime. Only E01's per-signal checks run.

**Constraint:** E19's primary API is `async` (`calculate_unified_risk_profile` is a coroutine). D31's signal handler is synchronous. These cannot be directly integrated.

**Specification:**

1. Add `"E19_UnifiedRiskCoordinator"` to the "Risk Management" startup phase (non-critical).

2. Add factory:
   ```python
   if module_id == "E19_UnifiedRiskCoordinator":
       from SpyderE_Risk.SpyderE19_UnifiedRiskCoordinator import UnifiedRiskCoordinator
       coordinator = UnifiedRiskCoordinator()
       logger.info("E19 UnifiedRiskCoordinator initialized")
       return coordinator
   ```

3. Add a **background monitoring thread** in `_enable_trading()`:
   ```python
   e19 = self.components.get("E19_UnifiedRiskCoordinator")
   if e19 is not None:
       import asyncio, threading
       def _e19_monitor():
           loop = asyncio.new_event_loop()
           asyncio.set_event_loop(loop)
           while self.trading_enabled:
               try:
                   profile = loop.run_until_complete(
                       e19.calculate_unified_risk_profile()
                   )
                   if profile and getattr(profile, "breach_count", 0) > 0:
                       logger.warning("E19 portfolio risk breach: %s", profile)
               except Exception as exc:
                   logger.debug("E19 monitor error: %s", exc)
               time.sleep(60)   # check every minute
           loop.close()
       threading.Thread(target=_e19_monitor, daemon=True, name="E19-monitor").start()
       logger.info("E19 portfolio risk monitor started (60s interval)")
   ```

4. **Do NOT** block D31's synchronous signal path with E19 calls.

---

### SPEC-7 (MEDIUM): R08 Signal Quality — Add RSI Confirmation to `_generate_signal()`

**File:** `Spyder/SpyderR_Runtime/SpyderR08_PaperTradingQtWorker.py`

**Problem:** `_generate_signal()` uses only a dual MA(5)/MA(20) crossover. The worker already has `_rsi_from_prices()` implemented but unused in the signal path. Trading into overbought/oversold extremes with pure MA crossover generates false entries.

**Specification:**

Replace `_generate_signal()` with an RSI-confirmed version:

```python
def _generate_signal(self) -> str | None:
    """Dual MA crossover with RSI confirmation on poll-interval prices.

    Rules:
    - MA(5) > MA(20) by MOMENTUM_THRESHOLD → BUY candidate
      → Confirm: RSI not overbought (RSI ≤ 72) — avoids chasing extended moves
    - MA(5) < MA(20) by MOMENTUM_THRESHOLD → SELL candidate
      → Confirm: RSI not oversold (RSI ≥ 28) — avoids shorting a bounce

    When RSI is unavailable (insufficient history), falls back to pure MA.
    """
    prices = self._price_history
    if len(prices) < self.LONG_MA_WINDOW:
        return None

    short_ma = sum(prices[-self.SHORT_MA_WINDOW:]) / self.SHORT_MA_WINDOW
    long_ma = sum(prices[-self.LONG_MA_WINDOW:]) / self.LONG_MA_WINDOW

    if long_ma <= 0:
        return None

    ratio = (short_ma - long_ma) / long_ma
    rsi = self._rsi_from_prices(prices)   # None if < 15 bars

    if ratio > self.MOMENTUM_THRESHOLD:
        if rsi is None or rsi <= 72:
            return "BUY"
        return None   # overbought — skip
    if ratio < -self.MOMENTUM_THRESHOLD:
        if rsi is None or rsi >= 28:
            return "SELL"
        return None   # oversold — skip
    return None
```

Also add RSI to the `_dec` decision log dict:
```python
_dec["rsi"] = round(rsi, 2) if rsi is not None else None
```

---

### SPEC-8 (LOW): Fix Pre-Existing Test API Drift

**Files:** Various T-Series test modules

**Problem:** Multiple test files fail at collection or runtime due to API drift:

| Test File | Failure | Root Cause |
|-----------|---------|------------|
| `SpyderT46_RiskManager_Test.py` | `test_07_blocked_total_exposure` | `RiskManager._orders` attribute not present on mock |
| `SpyderT46_RiskManager_Test.py` | `test_17_get_status_all_keys` | `RiskManager.get_status()` method does not exist |
| `SpyderT46_RiskManager_Test.py` | `test_18_get_metrics_check_rate` | `RiskManager.get_metrics()` method does not exist |
| `SpyderT47_StrategyUnit_Test.py` | `test_12/13/14` | `EventType.SIGNAL_GENERATED` and `Event.create()` do not exist |
| `SpyderT40_TradierClient_Test.py` | `test_cancel_order` | `cancel_order()` returns bool, test expects subscriptable |
| `SpyderT106_ACore.py` | Collection error | Import `UnitTestFramework` name changed |
| `SpyderT113_BSeries.py` | Collection error | Same framework import issue |

**Specification:**

For each failing test, either:
a) **Add the missing method to the production class** if it was removed by mistake, OR
b) **Update the test** to match the current API if the production class intentionally changed

Priority fixes:
- Add `get_status()` and `get_metrics()` to `SpyderE01_RiskManager` if these are useful monitoring APIs
- Add `EventType.SIGNAL_GENERATED` to `SpyderA05_EventManager` if it was accidentally removed
- Fix `SpyderT40`'s `cancel_order` test to handle bool return

---

## Signal Wiring Summary — Final State

### Headless Path (after fixes)

```
Market Data → C01_DataFeed
                 ↓
F-Series analysis → D31_StrategyOrchestrator
                       ├─ L09 regime engine (ML) — NOW PROPERLY INJECTED ✅
                       ├─ Y01 regime updates (I06 bus) — already working ✅
                       ├─ E01 risk validation (singleton) — already working ✅
                       └─ B02_OrderManager — NOW PROPERLY WIRED ✅
                              ↓
                       B40_TradierClient → Tradier API
```

### GUI Path (unchanged, confirmed working)

```
S07 Custom Metrics → G05 Dashboard → R08 paper worker
                                        ├─ MA+S08 signal ✅
                                        ├─ S07 regime gate ✅
                                        ├─ E01 risk gate ✅
                                        └─ B40_TradierClient (direct) ✅
```

---

## Test Results

| Test File | Before | After |
|-----------|--------|-------|
| `T40_TradierClient_Test` | 80/81 pass | 80/81 pass (unchanged) |
| `T43_OrderManager_Test` | all pass | all pass (unchanged) |
| `T46_RiskManager_Test` | 13 fail (pre-existing) | 13 fail (unchanged — API drift) |
| `T47_StrategyUnit_Test` | 3 fail (pre-existing) | 3 fail (unchanged — API drift) |

Our changes introduced **zero new test failures**.

---

## Files Changed

| File | Change |
|------|--------|
| `Spyder/SpyderA_Core/SpyderA06_MasterController.py` | Added L09 factory, D31 factory, `set_order_manager()` wiring in `_enable_trading()` |

---

## Deployment Readiness

| Component | Status |
|-----------|--------|
| GUI paper trading (R08) | ✅ Ready — set `SPYDER_OPTIONS_LIVE_PAPER=1` |
| Headless engine (A06/D31) | ✅ Ready after fixes — test in sandbox first |
| Live trading | ⚠️ Set `TRADIER_ENVIRONMENT=production` only after sandbox validation |
| Autonomous agents (Y-series) | ✅ Started by Y10_AgentScheduler in A06 |
| ML regime detection (L09) | ✅ Injected into D31 at startup |
| Portfolio risk (E19) | ⚠️ Not yet integrated — use SPEC-6 to add background monitoring |
| APScheduler jobs (A04) | ⚠️ Not yet integrated — use SPEC-4 to enable scheduled tasks |
