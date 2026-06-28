# Tradov Codebase Audit v32
**Date:** 2026-06-24
**Auditor:** Codex (GPT-5)
**Branch Audited:** `master`
**Baseline:** v31 audit (`2026-06-18_Codebase_Audit_v31.md`)
**Commit:** `f023834`

---

## Executive Summary

This v32 audit reviewed the current Tradov workspace with a focus on hands-free autonomous arbitrage and pair-trading readiness. I concentrated on the code paths that still matter most before live trading: runtime-mode isolation, pair-order lifecycle cleanup, broker cancel/modify fault handling, and verification hygiene.

### Overall posture

- The v31 hardening is real and measurable.
- `python -m compileall -q Tradov` passes.
- The targeted broker and runtime safety regressions pass.
- The S07 market-condition availability tests are present and aligned with the intended fail-closed behavior, although they are skipped in this workspace because `PySide6` is not installed.

The codebase is no longer blocked by syntax or import-stability issues in the areas I checked. The remaining concerns are lifecycle correctness and operational resilience.

### Launch recommendation

1. Do not treat the system as fully hands-free live-ready yet.
2. Remove the remaining process-global runtime-mode mutation.
3. Fix pair-order recovery finalization so recovered orders do not remain active forever.
4. Harden cancel/modify paths against transport failures before increasing live exposure.

---

## What I Validated

### A. Execution boundary

1. `TradovR12_SessionSupervisor` startup and runtime-context handling.
2. `TradovB02_OrderManager` submission, cancel, and modify state transitions.
3. `TradovB02_PairOrderExecutor` sequential and concurrent pair placement.

### B. Signal and UI semantics

1. `TradovS07_CustomMetricsOrchestrator` market-condition availability behavior.
2. GUI helpers that derive regime labels and signal-panel sync plans from S07 payloads.

### C. Verification surface

1. Repository-wide compile validation.
2. Targeted safety regressions for order submission, pair execution, runtime context isolation, and market-condition availability.

---

## Executable Checks Run

### Repository compile check

```bash
python -m compileall -q Tradov
```

Result:
- Passed

### Targeted regression smoke tests

I ran the focused regression set that covers the current hardening work:

```bash
python -m pytest -q -o addopts='' \
  Tradov/TradovT_Testing/TradovT188_B02_OrderManagerSubmissionHardening.py \
  Tradov/TradovT_Testing/TradovT189_PairOrderExecutorSafety.py \
  Tradov/TradovT_Testing/TradovT191_RuntimeContextIsolation.py
```

Result:
- Passed: 8
- Skipped: 0

I also ran the S07 availability regression file:

```bash
python -m pytest -q -o addopts='' Tradov/TradovT_Testing/TradovT190_S07_MarketConditionAvailability.py
```

Result:
- Skipped in this workspace because `PySide6` is not installed

### Verification note

The repository’s default `pytest` invocation is brittle in this workspace because `pytest.ini` injects coverage flags by default. I bypassed those addopts for the smoke tests above so I could verify the runtime-critical paths directly.

---

## Findings

## HIGH

### H-1 - Session startup still mutates process-global trading-mode environment variables
**Files:**
- `Tradov/TradovR_Runtime/TradovR12_SessionSupervisor.py`

**Evidence:**
- `start()` builds a per-session `RuntimeContext` at lines 197-208.
- The same method then writes `self.mode` back into `TRADOV_TRADING_MODE` and `TRADING_MODE` at lines 209-210.
- I verified this behavior by starting a paper dry-run supervisor after clearing those env vars. Even though startup aborted on an unrelated missing dependency, the env vars were still left set to `paper`.

**Impact:**
- Runtime context isolation is incomplete.
- A failed or aborted startup can leave the whole process in a different mode than it started with.
- Multiple sessions or embedded supervisors can still influence one another through process-global state.
- This directly conflicts with the newer context-first architecture and with the runtime-isolation intent already being tested elsewhere.

**Recommendation:**
1. Stop writing trading mode into process env during `start()`.
2. Pass `RuntimeContext` explicitly into the remaining mode-sensitive consumers.
3. If legacy compatibility requires env variables, confine them to a short-lived wrapper process or restore the previous values on exit and on startup failure.
4. Add a regression that proves `start()` cannot leak mode state after an abort.

**Status:** Open.

## MEDIUM

### M-1 - Partial pair recovery remains tracked as active forever
**Files:**
- `Tradov/TradovB_Broker/TradovB02_PairOrderExecutor.py`

**Evidence:**
- `PairOrderState.RECOVERY` exists at lines 47-57.
- `PairOrder.is_complete` does not treat `RECOVERY` as terminal at lines 85-91.
- `execute_pair()` sets `pair_order.state = PairOrderState.RECOVERY` for partial submissions at lines 177-180 and 200-203.
- `_recover_partial_submission()` also sets `completed_at` while leaving the state as `RECOVERY` at lines 319-325.
- `get_active_orders()` filters on `not v.is_complete` at lines 487-489, so recovered orders remain in the active set even after recovery has finished.

**Impact:**
- Recovered partial submissions never age out of the active-order view.
- Monitoring and operator tooling can show a permanently active pair order that is already done with recovery.
- This can create phantom exposure, duplicate operational attention, and confusion during incident response.
- The state model currently mixes “recovery is happening” and “recovery finished” into one bucket.

**Recommendation:**
1. Split recovery-in-progress from recovery-complete.
2. Treat a fully recovered partial submission as terminal once the cancel/flatten outcome is known.
3. Remove `_order_to_pair` mappings when recovery finishes, the same way they are removed after a full fill.
4. Add a regression that proves `get_active_orders()` becomes empty after a recovered pair submission completes.

**Status:** Open.

### M-2 - Cancel and modify paths still do not handle transport failures
**Files:**
- `Tradov/TradovB_Broker/TradovB02_OrderManager.py`

**Evidence:**
- `cancel_order()` wraps the Tradier call in a `try` block, but only catches `TradierAPIError` at lines 691-705.
- `modify_order()` has the same pattern, catching only `TradierAPIError` at lines 789-797.
- By contrast, the submission path already treats `ConnectionError` and `TimeoutError` as expected failure modes at lines 617-619 and other submission handlers.

**Impact:**
- A cancel or modify network timeout can escape the method instead of being converted into a structured `OrderResult`.
- For cancel, the local order can be left in `PENDING_CANCEL` with no broker-side confirmation.
- For pair recovery, an uncaught timeout during cancel is especially dangerous because the recovery path may assume the leg was handled when it was not.
- The broker layer is therefore still inconsistent about which transport failures are handled and which are considered exceptional.

**Recommendation:**
1. Catch `ConnectionError` and `TimeoutError` in `cancel_order()` and `modify_order()`.
2. On cancel timeout, explicitly reconcile broker state before reverting the local order state.
3. Keep the structured `OrderResult` contract consistent across submit, cancel, and modify.
4. Add tests that simulate timeout during cancel and modify, especially during pair-recovery flows.

**Status:** Open.

## LOW

### L-1 - Default pytest configuration is brittle in this workspace
**Files:**
- `pytest.ini`

**Evidence:**
- `pytest.ini` injects coverage flags and `--strict-config` into the default `addopts` block at lines 15-46.
- In this workspace, a plain `python -m pytest` invocation fails unless I override `addopts`.
- The same configuration also emits a warning about `asyncio_mode` in the current local pytest environment.

**Impact:**
- Local verification is harder than it needs to be.
- New contributors can hit tooling friction before they ever reach the code under test.
- This is not a trading risk, but it is a reproducibility and maintainability gap.

**Recommendation:**
1. Make the coverage addopts conditional on the coverage plugin being installed, or move them into CI-only invocation.
2. Keep the fast smoke path runnable with plain `pytest`.
3. Align local and CI tooling expectations so the same command works in both places.

**Status:** Open.

---

## Positive Observations

1. `python -m compileall -q Tradov` passes.
2. The targeted broker hardening regressions pass.
3. The runtime-context regression passes, which confirms the new context object is being honored by at least one consumer.
4. The pair-order executor now has explicit partial-recovery logic instead of silently leaving a leg orphaned.
5. S07 availability handling is encoded in the codebase and covered by dedicated tests, even though the GUI dependency is unavailable in this workspace.
6. The repository now has a clear testing surface for the exact failure modes that matter before live use.

---

## Opportunities for Improvement

1. **Finish context-first runtime control**
   - Remove the remaining env-based mode writes and complete `RuntimeContext` propagation to every mode-sensitive subsystem.

2. **Split pair recovery states**
   - Introduce explicit terminal states for recovered partial submissions so operational tooling can distinguish “recovery done” from “still in progress”.

3. **Unify broker transport semantics**
   - Make submit, cancel, and modify all follow the same network-fault contract and return structured results instead of leaking exceptions.

4. **Formalize a forensic execution ledger**
   - Persist caller tag, broker tag, broker id, pair id, strategy id, timestamps, and terminal transition reason in one structured record.

5. **Keep verification friction low**
   - Make local smoke testing runnable with a plain pytest invocation, while leaving coverage enforcement to CI or an explicit local opt-in.

---

## Implementation Plan

### Phase 1 - Runtime isolation
1. Remove `TRADOV_TRADING_MODE` and `TRADING_MODE` writes from `SessionSupervisor.start()`.
2. Thread `RuntimeContext` into the remaining consumers that still read process env for mode decisions.
3. Add a regression that proves startup failure cannot leak a different mode into the process.

### Phase 2 - Pair recovery finalization
1. Split `RECOVERY` into “recovery in progress” and “recovery complete”, or convert successful recovery into a terminal state.
2. Remove pair-order mappings from the active tables once recovery finishes.
3. Add tests for partial ack, cancel success, cancel timeout, and post-recovery cleanup.

### Phase 3 - Broker fault handling
1. Catch and normalize `ConnectionError` and `TimeoutError` in `cancel_order()` and `modify_order()`.
2. Reconcile broker state before reverting local state on cancel timeout.
3. Add transport-failure regressions for both single-leg and pair-recovery flows.

### Phase 4 - Tooling and regression hygiene
1. Make the default pytest command usable without extra local overrides.
2. Keep GUI-heavy tests behind markers so headless validation stays cheap.
3. Document the minimal local test recipe for the runtime-critical subset.

---

## Conclusion

The codebase is materially stronger than the previous audit. The broker staging path, runtime-context adoption, and S07 availability semantics have improved enough that the remaining risks are no longer basic wiring problems. The open issues are now narrower: process-global mode leakage, pair-recovery lifecycle cleanup, and cancel/modify fault normalization.

Those are all fixable, but I would not call the system fully hands-free live-ready until they are addressed and re-verified.

---

## Post-Audit Implementation

The Phase 1 and Phase 2 fixes requested after this audit have now been implemented and smoke-tested in the workspace:

1. `SessionSupervisor.start()` no longer mutates `TRADOV_TRADING_MODE` or `TRADING_MODE`.
2. Recovered pair submissions now count as terminal in `PairOrder.is_complete`, so they drop out of `get_active_orders()`.
3. The focused regressions for runtime isolation and pair recovery pass after the change.

The Phase 3 broker hardening is also now in place:

1. `cancel_order()` and `modify_order()` normalize `ConnectionError` and `TimeoutError` instead of leaking them.
2. Cancel-timeout handling refreshes broker state before deciding whether the order is still live.
3. `TRADIER_STATUS_MAP` now recognizes both `canceled` and `cancelled`.
4. The focused order-manager regressions for cancel timeout reconciliation and modify timeout failure both pass.

Phase 4 is now complete as well:

1. `pytest.ini` no longer forces coverage addopts into every local run.
2. `.github/workflows/ci.yml` now applies the coverage gate explicitly in the full-coverage job.
3. A plain `python -m pytest` smoke run works locally without `--no-cov` or `-o addopts=''`.
