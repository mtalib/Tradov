# SPYDER Codebase Audit v13 — Post-v12 Closure Report & Remaining Gaps

**Date:** 2026-04-19
**Author:** Post-v12 verification pass after T129 hardening and emergency-path fixes.
**Scope:** Re-verify previously listed v12 BLOCKERs, confirm regression coverage status, and enumerate what is still open before live autonomous trading.
**Branch reviewed:** `refactor/g05-widget-extraction`

**Verdict:** **READY for 48h paper soak using the live launcher path. NOT READY for live autonomous operation yet.**

The v12 emergency-path blockers are now closed in code and covered by T129. Remaining risk is concentrated in non-blocker operational hardening items (runtime config reload, order-state transition validation, heartbeat/observability, and several P1/P2 resiliency tasks).

---

## 1. Evidence Snapshot (v13)

### Test evidence
- `python -m pytest Spyder/SpyderT_Testing/SpyderT129_ProtocolCompliance.py -q --no-cov`
- Result: all collected tests completed to 100% for T129 (34 tests).

### Code evidence highlights
- B1 (`PaperBroker.close_position`) present at [Spyder/SpyderR_Runtime/SpyderR15_PaperBroker.py:290](Spyder/SpyderR_Runtime/SpyderR15_PaperBroker.py#L290)
- B2 safe stop wiring (`KeyboardInterrupt` + shared stop helper) at [Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py:536](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L536), [Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py:548](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L548)
- B3 async idempotency `tag` in async signature at [Spyder/SpyderB_Broker/SpyderB40_TradierClient.py:2109](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L2109), [Spyder/SpyderB_Broker/SpyderB40_TradierClient.py:2119](Spyder/SpyderB_Broker/SpyderB40_TradierClient.py#L2119)
- B4 `pending_orders` lock at [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:262](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L262)
- B5 `DATA_FRESH` resume path at [Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py:1715](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L1715), [Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py:1745](Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py#L1745)
- N1 kill-switch event + lock file path at [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:246](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L246), [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:1390](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1390), [Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py:368](Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py#L368)
- N2 transient error escalation path references `record_api_server_error` at [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:1520](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1520), [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:1645](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L1645)
- N3 orphan escalation event at [Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py:385](Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py#L385), subscriber at [Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py:253](Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py#L253)

---

## 2. v12 BLOCKER Closure Matrix

| ID | v12 Status | v13 Status | Notes |
|---|---|---|---|
| B1 | open | ✅ closed | `PaperBroker.close_position` implemented and protocol-aligned. |
| B2 | open | ✅ closed | Shared `_safe_stop_supervisor()` used for Ctrl-C/exception paths. |
| B3 | open | ✅ closed | `place_order_async()` now accepts/forwards `tag`. |
| B4 | open | ✅ closed | `pending_orders` operations guarded by `RLock`; concurrent tests pass. |
| B5 | open | ✅ closed | D31 has separate stale/kill pause states and `DATA_FRESH` resume. |
| E13 | open | ✅ closed | Emergency emit call corrected to EventManager API shape. |
| N1 | open | ✅ closed | `threading.Event` kill-switch + persistent kill-lock gate present. |
| N2 | open | ✅ closed | Transient broker failure path increments API error counter. |
| N3 | open | ✅ closed | `ORDER_ORPHANED` emitted and integrated into runtime handling. |
| P1-3 | open | ✅ closed | Orphan sweep guarded/wired from launcher path. |

---

## 3. Remaining Open Gaps (Post-closure)

These items still require implementation before live autonomous mode:

### 3.1 Remaining N-series gaps
- **N4** Runtime config reload wiring is still limited (reload API exists, runtime signal/flow remains incomplete).
- **N5** Order-state transition legality checks are still not centrally enforced.
- **N6** No external heartbeat/uptime notifier for dead-bot detection.
- **N7** Log rollover lacks explicit alerting/escalation.
- **N8** Resume-after-recovery coverage exists for D31 pause flow, but broader system-level stale/fresh recovery scenarios can be expanded.
- **N9** Continue timezone consistency audit to remove remaining naive datetime risk in order/risk paths.
- **N10** `close_position` happy-path exists; post-submit fill verification policy can still be strengthened for exceptional market states.

### 3.2 Remaining P1/P2 backlog from v12
- **P1-2** cold-start signal gating behavior hardening in risk validation.
- **P1-4** PositionTracker persistence + restart reconciliation.
- **P1-5** FillReconciler cadence/profile optimization.
- **P1-6 / P1-7** stricter OCC/strike validation parity between paper/live.
- **P1-12** A05 handler fault telemetry/circuit-breaker hardening.
- **P1-13** boot-time synthetic signal self-test robustness.
- **P2-2 / P2-3 / P2-4 / P2-5** remain as resiliency/performance hardening tasks.

---

## 4. Gate Status (v13)

### 4.1 48h paper soak gate
- **Status:** ✅ **GO**
- Preconditions met:
- v12 critical emergency/shutdown/idempotency blockers closed.
- T129 protocol/compliance regression suite passing.
- Kill-lock and stale-data recovery behaviors are now wired.

### 4.2 Live autonomous gate
- **Status:** ⛔ **HOLD**
- Required before live flip:
- Close remaining high-impact P1/N backlog items in Section 3.
- Run 48h soak without manual intervention on the same launcher path intended for live.
- Capture and review runtime incident logs (orphan events, API panic transitions, stale/fresh cycles).

---

## 5. Recommended Next Fix Order

1. N5 + P1-4 (state correctness on restart and order lifecycle integrity).
2. N6 + N7 (operational observability and alerting).
3. N4 + N9 (runtime config agility and timezone consistency pass).
4. P1-12 + P1-13 (event bus fault handling and startup self-test confidence).
5. N10 + P1-6/P1-7 (close-position verification and paper/live symbol-validation parity).

---

## 6. Proposed v14 Acceptance Criteria

- No open P1 items in emergency/order/risk path.
- No unresolved timezone-naive timestamps in runtime order lifecycle code.
- End-to-end recovery scenario tests for:
- stale feed → recovery resume,
- API transient burst → panic/kill switch,
- restart with kill-lock present,
- orphan escalation with operator-visible telemetry.
- 48h paper soak with zero stuck `pending_orders`, zero unhandled thread exceptions, and deterministic shutdown flatten behavior.
