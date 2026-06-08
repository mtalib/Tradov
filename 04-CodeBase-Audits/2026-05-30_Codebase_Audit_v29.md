# Tradov Codebase Audit v29
**Date:** 2026-05-30
**Auditor:** GitHub Copilot (GPT-5.3-Codex)
**Branch Audited:** `master`
**Baseline:** v28 audit (`2026-05-09_Codebase_Audit_v28.md`)
**Commit:** `3ed36ec`

---

## Executive Summary

This v29 audit was run on post-merge `master` after PR #60 content was synchronized, with focused validation across live-only policy boundaries, D31 entry/dispatch gates, and new paper multileg routing paths.

Primary outcome:
- The major v28 safety rails are mostly intact (R12 entry-gate fail-closed behavior in live mode, C29 sandbox rejection, D31 dispatch hardening).
- A **critical policy regression was reintroduced in B40** (`create_tradier_client_from_env`) that could still default to sandbox when env is unset. This was found and fixed during this audit pass.
- One significant hardening item remains open: **B02 local order state still stages before broker acknowledgement and single-leg tag propagation is incomplete**.

Updated launch posture after v29 remediation work:
- The B40 live-only default regression is now closed in current workspace state.
- The highest remaining execution-path hardening item is the B02 stage-then-commit/tag persistence gap.
- Recommendation: continue paper soak, complete B02 hardening before increasing live capital size.

---

## What I Validated

### A. Safety/Policy regressions (post-merge)

1. `R12._validate_live_only_tradier_policy()` behavior and startup ordering.
2. `B40.create_tradier_client_from_env()` default/invalid-env behavior.
3. `D31` entry trust gate fail-closed live-path behavior when gate/context unavailable.
4. `C29` live-only market-data policy controls.

### B. New extension/routing surfaces introduced in merged changes

1. Paper butterfly-family routing:
   - calendar spread
   - butterfly
   - broken wing butterfly
   - jade lizard zero
   - put credit spread 7
2. R08 after-hours spread MTM behavior.
3. D31 pin-risk window coverage behavior.

### C. Additional consistency checks

1. Runtime mode propagation channels (`TRADOV_TRADING_MODE`) between R12/G05/D31.
2. S07 market-condition fallback/default values used by downstream trust/risk consumers.
3. B02 submission and local order-state persistence behavior.

---

## Executable Checks Run

### Core safety bundle

```bash
source .venv/bin/activate
pytest -q --no-cov \
  Tradov/TradovT_Testing/TradovT188_R12_OrderManagerWiring.py \
  Tradov/TradovT_Testing/TradovT193_D31_DispatchResultHardening.py \
  Tradov/TradovT_Testing/TradovT196_R12_LiveOnlyTradierPolicy.py \
  Tradov/TradovT_Testing/TradovT197_C29_LiveOnlyPolicy.py \
  Tradov/TradovT_Testing/TradovT141_D31_EntryTrustGate.py \
  Tradov/TradovT_Testing/TradovT40_TradierClient_Test.py
```

Result:
- `76 passed, 1 warning`

### Extension routing bundle

```bash
source .venv/bin/activate
pytest -q --no-cov \
  Tradov/TradovT_Testing/TradovT391_D31_PaperBrokenWingButterflyRouting.py \
  Tradov/TradovT_Testing/TradovT393_D31_PaperButterflyRouting.py \
  Tradov/TradovT_Testing/TradovT389_D31_PaperCalendarSpreadRouting.py \
  Tradov/TradovT_Testing/TradovT401_D31_PaperJadeLizardZeroRouting.py \
  Tradov/TradovT_Testing/TradovT404_D31_PaperPutCreditSpread7Routing.py \
  Tradov/TradovT_Testing/TradovT399_R08_AfterHoursSpreadMtm.py \
  Tradov/TradovT_Testing/TradovT400_D31_PinRiskWindowCoverage.py
```

Result (initial):
- `2 failed, 20 passed` (date-sensitive expiry assertions in two tests)

Result (after deterministic test fix):
- `22 passed, 1 warning`

### B40 policy hardening validation (new)

```bash
source .venv/bin/activate
pytest -q --no-cov \
  Tradov/TradovT_Testing/TradovT40_TradierClient_Test.py \
  Tradov/TradovT_Testing/TradovT196_R12_LiveOnlyTradierPolicy.py
```

Result:
- `38 passed`

---

## Findings

## CRITICAL (Closed During This Audit)

### CR-1 — B40 live-only default regression reopened (unset env -> sandbox), policy bypass path
**Files:**
- `Tradov/TradovB_Broker/TradovB40_TradierClient.py`
- `Tradov/TradovR_Runtime/TradovR12_SessionSupervisor.py`

**What I observed:**
- `R12._validate_live_only_tradier_policy()` defaulted broker env check to `live` when env unset.
- `B40.create_tradier_client_from_env()` still defaulted to `sandbox` when `TRADIER_ENVIRONMENT` unset.
- Runtime proof before fix showed:
  - `policy (True, '')`
  - `broker_env sandbox`
  - `base_url https://sandbox.tradier.com/v1`

**Impact:**
- Startup policy looked compliant while broker factory selected sandbox, reopening the same policy drift class v28 had previously flagged.

**Remediation applied in v29 pass:**
1. B40 factory default changed to `live`.
2. Blank env token treated as `live`.
3. Invalid env tokens now raise `ValueError` (fail-closed).
4. Unit coverage added for unset, blank, and invalid env values.

**Status:**
- Closed in current workspace state.

---

## HIGH (Open)

### H-1 — B02 still stages local orders before acknowledgement and single-leg tag propagation remains incomplete
**File:**
- `Tradov/TradovB_Broker/TradovB02_OrderManager.py`

**Evidence:**
- Local state write occurs before broker acknowledgement in multiple submit paths (`self._orders[order.order_id] = order` prior to route/ack).
- `_route_order()` passes `tag=order.tag` for multileg only.
- Single-leg option/equity `place_order()` calls still omit `tag=order.tag`.

**Impact:**
- Timeout/hang and partial-failure recovery remains brittle.
- Single-leg forensic correlation is weaker than multileg paths.
- Residual ghost-order diagnosis complexity remains elevated.

**Recommendation:**
1. Complete stage-then-commit refactor.
2. Add `SUBMITTING` + pending submission store.
3. Require explicit tag assignment for all order classes before route.
4. Pass `tag=order.tag` through all single-leg routes.
5. Reconcile timeouts by tag before terminal reject.

---

## MEDIUM (Open)

### M-1 — S07 still emits plausible synthetic defaults in `get_current_market_conditions`
**File:**
- `Tradov/TradovS_Signals/TradovS07_CustomMetricsOrchestrator.py`

**Evidence:**
- Defaults remain hard-coded to realistic values (examples: `DIX=42.5`, `GEX=-2.5`, `SKEW=125.5`, `OGL=585.5`) when absent.

**Impact:**
- Missing upstream data can still appear numerically plausible to downstream trust logic and operators.

**Recommendation:**
1. Replace these defaults with `nan`/`None` and explicit availability status.
2. Keep stale/unavailable status first-class in payload contract.
3. Ensure entry/risk paths degrade explicitly based on availability, not synthetic numerics.

---

### M-2 — Runtime mode still coordinated via mutable process environment
**Files:**
- `Tradov/TradovR_Runtime/TradovR12_SessionSupervisor.py`
- `Tradov/TradovG_GUI/TradovG05_TradingDashboard.py`
- `Tradov/TradovD_Strategies/TradovD31_StrategyOrchestrator.py`

**Evidence:**
- R12 and G05 continue to write `os.environ["TRADOV_TRADING_MODE"]` at runtime.
- D31 and broker safety surfaces consume this mutable channel.

**Impact:**
- Cross-instance coupling risk remains (tests, multi-supervisor contexts, GUI/runtime timing races).

**Recommendation:**
1. Introduce immutable runtime context object passed by reference.
2. Restrict env vars to startup inputs only.
3. Add isolation tests proving one runtime cannot mutate another runtime’s mode semantics.

---

## LOW (Closed During This Audit)

### L-1 — Two extension routing tests were date-sensitive and non-deterministic on weekends/holidays
**Files:**
- `Tradov/TradovT_Testing/TradovT391_D31_PaperBrokenWingButterflyRouting.py`
- `Tradov/TradovT_Testing/TradovT393_D31_PaperButterflyRouting.py`

**Issue:**
- Tests assumed OCC symbols always use `today` YYMMDD, but runtime legitimately normalizes to nearest listed expiration.

**Fix applied:**
- Assertions now validate option type/strike structure and consistent expiry token across legs, independent of date roll behavior.

**Status:**
- Closed; extension suite now deterministic (`22 passed`).

---

## Opportunities for Improvement

1. Add startup effective-routing self-audit event.
- Emit run mode, broker env, market-data env, entry-gate fail mode, and synthetic-default flags in one startup record.

2. Introduce strict autonomous profile switch.
- Single switch that enforces live-only envs, fail-closed gates, no synthetic defaults, and unresolved-context execution block.

3. Build submission forensic ledger keyed by local id + tag + broker id.
- Include retries, timeout reconciliation steps, and terminal classification for post-incident replay.

4. Add no-network unit mode for D32 leg-construction tests.
- Keep deterministic contract tests independent from live expiration-chain availability.

---

## Implementation Plan (Open Items)

### Sprint A — B02 execution-hardening (highest priority)
1. Add `OrderState.SUBMITTING` and pending map.
2. Stage locally as submitting, commit to active only after broker ack.
3. Enforce and propagate tags across all route paths.
4. Add timeout-by-tag reconciliation path.
5. Add focused tests for single-leg tag persistence and submission hangs.

### Sprint B — market-condition availability semantics
1. Remove plausible hardcoded defaults in S07 market-conditions API.
2. Add explicit `market_conditions_available` and per-metric health bits.
3. Update F09/D31 readers to key on availability flags.

### Sprint C — runtime mode channel hardening
1. Introduce runtime context object.
2. Remove runtime env mutation writes from G05/R12.
3. Preserve env only for startup parsing.

---

## Overall Launch Assessment (v29)

### GREEN
- R12 live-only gate present and exercised.
- D31 entry-trust fail-closed path in live mode covered.
- C29 explicit sandbox rejection covered.
- D31 dispatch hardening and paper multileg extension routes covered.

### YELLOW
- B02 submission state and single-leg tag propagation hardening remains incomplete.
- S07 synthetic defaults still weaken strict unavailable-state semantics.
- Runtime mode env mutability remains.

### RED
- None currently open after v29 in-turn B40 remediation.

**Recommendation:**
1. Continue paper soak on current baseline.
2. Prioritize Sprint A (B02 stage-then-commit/tag propagation) before live capital increase.
3. Complete Sprint B and C for stronger autonomous safety posture.

---

## Conclusion

v29 confirms meaningful progress and good focused-suite health on merged master. A critical B40 policy regression was detected and corrected during this pass, and extension routing tests were stabilized for deterministic validation. The most important remaining engineering risk is now concentrated in B02 submission semantics and single-leg correlation fidelity, followed by S07 availability semantics and runtime-mode channel design.