# Tradov Codebase Audit v31
**Date:** 2026-06-18
**Auditor:** Codex (GPT-5)
**Branch Audited:** `master`
**Baseline:** v30 audit (`2026-06-18_Codebase_Audit_v30.md`)
**Commit:** `f023834`

---

## Executive Summary

This v31 audit reviewed the current Tradov workspace for hands-free autonomous arbitrage and pair-trading readiness. I focused on the broker execution path, pair-trade orchestration, runtime-mode isolation, market-condition availability semantics, startup observability, and the remaining gaps from v30.

### Overall posture

- The major v30 blockers are materially improved.
- Repository compile validation now passes.
- Live-only broker and market-data policy checks are present and enforced.
- Runtime mode is no longer rewritten globally by `R12` or the dashboard.
- S07 no longer fabricates neutral-looking DIX/SWAN/SKEW defaults inside the core market-condition payload.
- B02 now stamps and propagates caller tags through single-leg and multileg routes.

The remaining issues are execution-safety and consistency gaps rather than obvious syntax or import blockers.

### Launch recommendation

1. Keep paper or dry-run soak as the default.
2. Fix the remaining broker commit semantics.
3. Harden pair-trade timeout handling before increasing live exposure.
4. Finish runtime-context propagation and make every consumer honor S07 availability metadata.

---

## What I Validated

### A. Repository and runtime surface

1. Enumerated the current hot-path modules and the new regression tests.
2. Reviewed the diffs in broker, runtime, signal, GUI, and CI wiring.
3. Ran repository compile validation.
4. Ran focused regressions for the new safety cases.
5. Checked for remaining env-based mode coordination and market-data defaults.

### B. Broker and execution path

1. `B02_OrderManager` submission staging, tag propagation, and timeout reconciliation.
2. `B02_PairOrderExecutor` sequential and concurrent leg submission behavior.
3. `B40_TradierClient` live-only order guard and env resolution.

### C. Runtime and strategy path

1. `R12_SessionSupervisor` runtime context construction and startup receipt emission.
2. `D31_StrategyOrchestrator` runtime-context consumption and entry-gate fail-closed behavior.
3. `S07_CustomMetricsOrchestrator` market-condition availability semantics.

### D. GUI and integration path

1. `G05_TradingDashboard` runtime-mode sync behavior.
2. `G18_MarketDataWorker` runtime mode reads.
3. `I06_AgentMessageBus` runtime-mode reads.
4. GUI helper defaults for SWAN/DIX/SKEW regime rendering.

---

## Executable Checks Run

### Repository compile check

```bash
python -m compileall -q Tradov
```

Result:
- Passed

### Focused regressions

I attempted to run the new safety regressions directly, but the current workspace is missing several optional runtime dependencies needed for full pytest collection:
- `PySide6`
- `colorama`
- timezone support for `US/Eastern` in the current environment

That means the codebase itself compiles, but full local pytest collection is not reproducible in this workspace without the remaining optional packages.

---

## Findings

## HIGH

### H-1 — B02 still stages orders in the main order ledger before broker acknowledgement
**Files:**
- `Tradov/TradovB_Broker/TradovB02_OrderManager.py`

**Evidence:**
- `_stage_submission()` sets `order.state = OrderState.SUBMITTING`, but it also writes the order into both `_pending_submissions` and `_orders` before routing.
- `submit_order()`, `submit_multileg_order()`, `submit_iron_condor()`, and `submit_credit_spread()` all call `_stage_submission()` before broker acknowledgement.
- `_finalize_submission_ack()` only promotes the staged order after broker response.

**Impact:**
- The main `_orders` ledger still contains an order before Tradier has acknowledged it.
- Any consumer that treats `_orders` as the committed order book can see a live-looking record that is not actually broker-confirmed.
- A process crash between stage and ack can still leave a pre-ack order persisted in the primary ledger.

**Recommendation:**
1. Split the data model into a true pending-submission ledger and a committed order ledger.
2. Keep staged orders out of `_orders` until broker acknowledgement is received.
3. Persist submission tags and timestamps in the pending ledger so recovery can still reconcile transport errors.
4. Add tests for crash-before-ack, duplicate submission after timeout, and recovery after transport failure.

**Status:** Open.

### H-2 — Concurrent pair submission does not recover cleanly on timeout or partial acknowledgement
**File:**
- `Tradov/TradovB_Broker/TradovB02_PairOrderExecutor.py`

**Evidence:**
- `_submit_pair_legs()` supports concurrent leg submission, but it returns `(id_a, id_b)` without any recovery path when one leg times out.
- `execute_pair()` treats `id_a is None` as a full leg-A failure and returns `FAILED`.
- If leg A times out while leg B succeeds, the executor can exit as a failure while one leg is already live.
- There is no explicit cancel/flatten recovery path for the concurrent timeout case.

**Impact:**
- A partial pair submission can leave untracked live exposure.
- The concurrent path is still not operationally equivalent to atomic pair execution.
- The current telemetry helps diagnosis, but it does not remove the legging risk.

**Recommendation:**
1. Add explicit partial-ack recovery for concurrent mode.
2. Cancel or flatten the acknowledged leg when the opposite leg times out.
3. Distinguish `leg_a_timeout`, `leg_b_timeout`, and `partial_ack` outcomes from generic failure.
4. Add regression tests for A-only success, B-only success, and one-leg timeout in concurrent mode.

**Status:** Open.

## MEDIUM

### M-1 — Runtime-context adoption is still incomplete outside `R12` and `D31`
**Files:**
- `Tradov/TradovR_Runtime/TradovR12_SessionSupervisor.py`
- `Tradov/TradovD_Strategies/TradovD31_StrategyOrchestrator.py`
- `Tradov/TradovB_Broker/TradovB40_TradierClient.py`
- `Tradov/TradovG_GUI/TradovG18_MarketDataWorker.py`
- `Tradov/TradovI_Integration/TradovI06_AgentMessageBus.py`

**Evidence:**
- `R12` now owns and passes an immutable `RuntimeContext`.
- `D31` uses `runtime_context` when available.
- `B40` still resolves runtime mode from `TRADING_MODE` / `TRADOV_TRADING_MODE`.
- `G18` still reads `TRADOV_TRADING_MODE` directly for live-account balance gating.
- `I06` still resolves mode from config and env rather than a passed runtime context.

**Impact:**
- The process-global env fallback remains a control boundary in several subsystems.
- Multiple sessions, GUIs, or embedded contexts can still influence one another through env-based mode reads.
- The current fix is a good start, but it is not yet a complete isolation model.

**Recommendation:**
1. Pass `RuntimeContext` into B40, G18, and I06.
2. Restrict env reads to startup parsing and legacy fallback only.
3. Add a single helper for "effective trading mode" that prefers context over env.
4. Add isolation tests proving that one session cannot flip another session’s mode.

**Status:** Open from v30, partially improved.

### M-2 — S07 availability semantics are not yet honored consistently by downstream consumers
**Files:**
- `Tradov/TradovS_Signals/TradovS07_CustomMetricsOrchestrator.py`
- `Tradov/TradovG_GUI/TradovG05_TradingDashboard.py`
- `Tradov/TradovG_GUI/TradovG107_CustomMetricSignalPanelSyncHelper.py`
- `Tradov/TradovG_GUI/TradovG109_RegimePillStateHelper.py`
- `Tradov/TradovG_GUI/TradovG13_EnhancedWidgets.py`

**Evidence:**
- `get_current_market_conditions()` now returns `market_conditions_available` plus per-metric availability and freshness.
- The same module still has internal fallbacks that assume `SWAN=1.0` when analyzing update frequency.
- Dashboard and helper code still use neutral-looking defaults such as `SWAN=1.9`, `DIX=42.0`, and `SKEW=120.0` when rendering or deriving regime labels.

**Impact:**
- Missing data can still be rendered or interpreted as a plausible neutral regime in some UI paths.
- Operators may see values that look valid even when the core market-condition payload says the metrics are unavailable.
- The safety improvement exists, but the consumer layer does not yet uniformly respect it.

**Recommendation:**
1. Propagate `market_conditions_available` into the GUI and regime helpers.
2. Replace UI defaults with explicit `--`/`N/A` states when data is unavailable.
3. Make S07 frequency adjustment and regime rendering fail closed when required metrics are stale or missing in live mode.
4. Add tests that prove missing DIX/SWAN/SKEW cannot appear as neutral live-state inputs.

**Status:** Open from v30, partially improved.

## LOW

### L-1 — The new safety regressions still depend on optional runtime packages in this workspace
**Observed packages missing in the current environment:**
- `PySide6`
- `colorama`
- timezone support for `US/Eastern`

**Impact:**
- I could not complete full pytest collection in this workspace.
- This is a verification limitation rather than a repository syntax defect, but it still matters for reproducibility.

**Recommendation:**
1. Make sure the operator/dev environment installs the full declared dependency set before treating the test suite as reproducible.
2. Keep GUI-heavy tests behind markers so headless CI can still run the safe core subset.

**Status:** Environment-limited verification gap.

---

## Positive Observations

1. `python -m compileall -q Tradov` passes.
2. `R12` now builds and passes an immutable `RuntimeContext` instead of rewriting `TRADOV_TRADING_MODE`.
3. `R12` emits a structured startup routing receipt.
4. `B02` now propagates caller tags through single-leg and multileg routes.
5. `B02` has explicit pending-submission tracking and timeout-by-tag reconciliation.
6. `S07` now exposes explicit availability/freshness metadata rather than fabricating neutral defaults inside the core payload.
7. CI now compiles production modules and aligns fast-test discovery with `TradovT*.py`.
8. The new safety regression files are focused and materially better than the prior ad hoc coverage.

---

## Opportunities for Improvement

1. **Forensic execution ledger**
   - Persist local order id, caller tag, broker tag, broker id, pair id, strategy id, timestamps, and terminal transition reason in one structured record.

2. **Strict autonomous profile**
   - Add a hard live-readiness profile that blocks startup when required compile/import checks or safety tests fail.

3. **Pair-leg guardrails**
   - Add max leg latency, max price drift, and explicit cancel/flatten recovery for concurrent pair submissions.

4. **Context-first runtime architecture**
   - Make `RuntimeContext` the default input for broker, GUI, integration, and message-bus mode decisions.

5. **Availability-aware UI**
   - Render unavailable market metrics as unavailable, not as neutral market-state defaults.

6. **Module inventory gate**
   - Auto-generate a module inventory and fail CI when docs or optional imports reference removed modules without a feature flag.

---

## Implementation Plan

### Sprint A — Broker commit semantics
1. Split the pending-submission and committed-order ledgers.
2. Keep staged orders out of `_orders` until Tradier acknowledgement.
3. Persist tag-based recovery metadata in the pending ledger.
4. Add tests for crash-before-ack and duplicate-submit recovery.

### Sprint B — Pair execution safety
1. Add explicit partial-ack recovery for concurrent pair submissions.
2. Cancel or flatten any acknowledged leg when the companion leg times out.
3. Distinguish timeout, partial-ack, and recovery-failure states in telemetry.
4. Add concurrent failure tests for A-only, B-only, and timeout cases.

### Sprint C — Runtime-context propagation
1. Pass `RuntimeContext` into `B40`, `G18`, and `I06`.
2. Replace env reads with context-first helpers.
3. Remove remaining mode writes from GUI and integration surfaces.
4. Add multi-session isolation tests.

### Sprint D — Availability semantics
1. Update GUI helpers to consume `market_conditions_available`.
2. Remove neutral-looking defaults from unavailable metric paths.
3. Make S07 frequency and regime logic fail closed when required metrics are stale.
4. Add regression tests for unavailable-data rendering and routing.

### Sprint E — Operator readiness
1. Add a single live-readiness command that runs compile, safety tests, and config validation.
2. Wire the readiness check into CI as a non-blocking artifact first, then a gating job.
3. Add a structured execution ledger and a startup routing receipt to the operator dashboard.

---

## Overall Launch Assessment

### GREEN
- Compile validation passes.
- Live-only policy exists in the broker and market-data router.
- Startup observability is improved.
- Tags and reconciliation are now much better than in v30.

### YELLOW
- Runtime-context propagation is incomplete.
- S07 availability is not yet consumed uniformly.
- Pair execution still needs failure-path hardening.

### RED
- The order book still stages before broker acknowledgement.
- Concurrent pair submission can still leave live exposure on partial failure.

## Conclusion

Tradov is noticeably closer to safe autonomous operation than it was in v30, but the final execution-safety work is still not done. The remaining issues are not cosmetic. They are the parts that decide whether a failed transport, a partial pair submission, or a missing market snapshot can leak real exposure into a live account.

The system should remain on paper or limited soak until B02 commit semantics, pair timeout recovery, runtime-context propagation, and availability-aware consumers are fully closed.
