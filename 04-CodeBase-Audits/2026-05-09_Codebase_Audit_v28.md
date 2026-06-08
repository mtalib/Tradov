# Tradov Codebase Audit v28
**Date:** 2026-05-09
**Auditor:** GitHub Copilot (GPT-5.4)
**Branch:** `master`
**Baseline:** v27 audit (`2026-05-02_Codebase_Audit_v27.md`)

---

## Executive Summary

This v28 audit focused on the post-v27 trading-path changes that are currently in the working tree, especially the new live-only Tradier policy, R12/D31 execution wiring, C29 market-data routing, G05 operator controls, and S07 market-condition plumbing.

The good news is that the main v27 wiring fixes are still present and the focused regression suites are green when run without the repository-wide coverage gate:

- `TradovT188_R12_OrderManagerWiring.py`
- `TradovT193_D31_DispatchResultHardening.py`
- `TradovT196_R12_LiveOnlyTradierPolicy.py`
- `TradovT197_C29_LiveOnlyPolicy.py`

Focused validation result:
- `21 passed in 12.66s` with `pytest -q --no-cov ...`

The bad news is that there are still real gaps in the live-safety boundary. The highest-risk defect is a policy drift between R12 and B40: R12's new live-only policy rejects only explicit `sandbox`/`paper`, but B40's shared client factory still falls back to `sandbox` for invalid or missing `TRADIER_ENVIRONMENT`. That means a typo can bypass the startup guard and still instantiate a sandbox broker client.

My recommendation is still **HOLD for live launch** until the critical policy drift and the D31 fail-open entry-gate behavior are closed. Paper soak can continue.

### Remediation Addendum — 2026-05-09

The two top blockers identified in this report were remediated immediately after the audit:

1. `R12/B40` live-only env policy drift closed.
   - `R12._validate_live_only_tradier_policy()` now rejects any broker or market-data env that is not `live` or `production`.
   - `B40.create_tradier_client_from_env()` now defaults to `live` and raises on invalid env tokens instead of silently falling back to sandbox.
2. `D31` entry-trust gate fail-open closed for live mode.
   - Missing gate object, missing market conditions, and gate evaluation exceptions now reject the signal in live mode instead of passing it through.

Post-fix validation:
- `pytest -q --no-cov Tradov/TradovT_Testing/TradovT196_R12_LiveOnlyTradierPolicy.py` → `10 passed`
- `pytest -q --no-cov Tradov/TradovT_Testing/TradovT141_D31_EntryTrustGate.py` → `12 passed`
- `pytest -q --no-cov Tradov/TradovT_Testing/TradovT40_TradierClient_Test.py Tradov/TradovT_Testing/TradovT141_D31_EntryTrustGate.py Tradov/TradovT_Testing/TradovT188_R12_OrderManagerWiring.py Tradov/TradovT_Testing/TradovT193_D31_DispatchResultHardening.py Tradov/TradovT_Testing/TradovT196_R12_LiveOnlyTradierPolicy.py Tradov/TradovT_Testing/TradovT197_C29_LiveOnlyPolicy.py` → `63 passed`

Updated launch view after remediation:
- The original `CR-1` and `H-1` items in this report are now closed in the current workspace state.
- The remaining notable hardening item from this audit is `H-2` / the B02 stage-then-commit + single-leg tag persistence gap.
- Recommendation shifts from `HOLD on these blockers` to `resume paper soak, then address B02 ghost-order recovery before increasing live capital size`.

---

## What I Validated

### Verified still intact from v27

1. `R12.start()` now checks the live-only Tradier policy before any component startup.
2. `R12` still wires `OrderManager` in live mode and intentionally skips it in paper mode.
3. `D31` still has the dispatch-result hardening for missing `message` / `error_code` attributes.
4. `B40` still restricts urllib3 retries to idempotent methods only.
5. `C29` rejects explicit sandbox market-data configuration.

### Executable checks run

1. `pytest -q --no-cov Tradov/TradovT_Testing/TradovT188_R12_OrderManagerWiring.py Tradov/TradovT_Testing/TradovT193_D31_DispatchResultHardening.py Tradov/TradovT_Testing/TradovT196_R12_LiveOnlyTradierPolicy.py Tradov/TradovT_Testing/TradovT197_C29_LiveOnlyPolicy.py`
   - Result: `21 passed in 12.66s`
2. Direct runtime proof for policy drift:
   - `SessionSupervisor._validate_live_only_tradier_policy()` returned `(True, '')` with `TRADIER_ENVIRONMENT=typo`
   - `create_tradier_client_from_env()` then instantiated `TradingEnvironment.SANDBOX`

Note:
- Running the same focused tests without `--no-cov` trips the repo-wide `fail-under=60` coverage gate. That is tooling noise for slice tests, not a product regression.

---

## Findings

## CRITICAL

### CR-1 — R12 live-only policy can be bypassed by invalid broker env values, and B40 then falls back to sandbox
**Files:**
- `Tradov/TradovR_Runtime/TradovR12_SessionSupervisor.py:392-395, 824-840`
- `Tradov/TradovB_Broker/TradovB40_TradierClient.py:3610-3655`

**Evidence:**
- `R12._start_live_broker()` still builds the broker through `create_tradier_client_from_env()`.
- `R12._validate_live_only_tradier_policy()` only rejects `sandbox` and `paper`.
- `B40.create_tradier_client_from_env()` still does:
  - `os.getenv("TRADIER_ENVIRONMENT", "sandbox")`
  - `TradingEnvironment.LIVE if _env_str in {"live", "production"} else TradingEnvironment.SANDBOX`
- Runtime proof from this audit:
  - `policy (True, '')`
  - `broker_env sandbox`
  - `base_url https://sandbox.tradier.com/v1`

**Impact:**
A typo like `TRADIER_ENVIRONMENT=typo` passes the new startup policy but silently instantiates a sandbox broker client. That undermines the whole live-only Tradier hardening and creates entry-path inconsistency between R12, Q02, C29, and B40.

**Assessment:**
Live-launch blocker.

**Spec:**
1. Change `R12._validate_live_only_tradier_policy()` to accept only `live` or `production` for both broker and market-data envs.
2. Change `B40.create_tradier_client_from_env()` to default to `live`, not `sandbox`, on missing env.
3. Reject invalid env tokens explicitly instead of coercing them to sandbox.
4. Add tests for:
   - `TRADIER_ENVIRONMENT=typo`
   - `TRADIER_ENVIRONMENT=`
   - env unset
5. Audit every `create_tradier_client_from_env()` call site and either pass an explicit environment or rely on the hardened parser.

---

## HIGH

### H-1 — D31 entry-trust gate still fails open when market conditions are missing or the gate raises
**File:**
- `Tradov/TradovD_Strategies/TradovD31_StrategyOrchestrator.py:4593-4658`

**Evidence:**
- Non-dict or absent gate object returns `True`.
- Missing `market_conditions` returns `True` at `4616-4617`.
- Any exception inside the gate logs `"entry trust gate failed open"` and returns `True` at `4657-4658`.

**Impact:**
If S07 data is unavailable, stale, or partially initialized, D31 can bypass the F09 structural trust gate entirely and hand the signal straight to E01. That is the wrong failure mode for a hands-free autonomous system.

**Assessment:**
Live-launch blocker. This is a true safety-boundary issue, not just an observability gap.

**Spec:**
1. Add a policy flag such as `fail_closed_if_entry_gate_unavailable` defaulting to `True` in live mode.
2. Replace the current fail-open returns with explicit gate rejection when:
   - `entry_gate is None`
   - `market_conditions` are unavailable
   - gate evaluation raises
3. Emit a structured risk event such as `entry_trust_gate_unavailable` so the dashboard can distinguish outage from market rejection.
4. Keep existing paper-mode behavior configurable if you want looser local experimentation.
5. Add tests covering:
   - missing `market_conditions`
   - metrics orchestrator exception
   - entry-gate method exception
   - live vs paper policy behavior

---

### H-2 — B02 still stages orders before broker acknowledgement, and single-leg paths do not preserve the effective idempotency tag locally
**Files:**
- `Tradov/TradovB_Broker/TradovB02_OrderManager.py:414, 787, 879, 976`
- `Tradov/TradovB_Broker/TradovB02_OrderManager.py:1555-1586`
- `Tradov/TradovB_Broker/TradovB40_TradierClient.py:1129-1135`

**Evidence:**
- Orders are still inserted into `self._orders` before broker confirmation at four submit paths.
- `_route_order()` forwards `tag=order.tag` for multileg only.
- Single-leg option/equity calls to `place_order()` omit `tag=order.tag`.
- B40 now auto-generates a tag if one is missing, but that generated tag is not written back to the local `Order` object.

**Impact:**
The catastrophic duplicate-fill path is reduced by B40 auto-tagging, but local recovery is still weak:
- hung submissions can leave local `PENDING` orders with no broker id
- the local state may not know the actual tag used at the broker for single-leg orders
- reconciliation and operator diagnosis remain brittle

**Assessment:**
Not the top live blocker anymore, but still a real correctness gap.

**Spec:**
1. Finish the stage-then-commit refactor from v27 SPEC-7.
2. Introduce `OrderState.SUBMITTING` and a `_pending_orders` store.
3. Ensure **every** single-leg and multileg path sets `order.tag` before any broker call.
4. Pass `tag=order.tag` explicitly through single-leg `_route_order()` calls.
5. On timeout/hang, reconcile by `tag` before deciding whether the order is ghost, open, or rejected.
6. Add regression coverage for single-leg tag persistence, not just B40 payload generation.

---

## MEDIUM

### M-1 — S07 still fabricates plausible market-condition defaults instead of surfacing data-unavailable state
**File:**
- `Tradov/TradovS_Signals/TradovS07_CustomMetricsOrchestrator.py:2497-2509`

**Evidence:**
`get_current_market_conditions()` returns hardcoded defaults such as:
- `DIX -> 42.5`
- `GEX -> -2.5`
- `SKEW -> 125.5`
- `OGL -> 585.5`

**Impact:**
When upstream metrics are absent, downstream consumers receive credible-looking numbers instead of an explicit unavailable state. That makes outages harder to detect and increases the chance of decisions based on synthetic placeholder values.

**Assessment:**
Not an immediate execution blocker, but a poor failure mode for autonomous trading and operator trust.

**Spec:**
1. Replace synthetic defaults with `float("nan")`, `None`, or explicit status fields.
2. Add a `market_conditions_available` / `source_health` flag to the returned payload.
3. Update D31/F09 consumers to fail closed or degrade explicitly on missing data.
4. Surface this state in G05 so operators see `DATA UNAVAILABLE`, not healthy-looking placeholders.

---

### M-2 — Runtime mode is coordinated through mutable process-wide env vars
**Files:**
- `Tradov/TradovR_Runtime/TradovR12_SessionSupervisor.py:104`
- `Tradov/TradovG_GUI/TradovG05_TradingDashboard.py:3445`
- `Tradov/TradovD_Strategies/TradovD31_StrategyOrchestrator.py:3868-3878, 4795-4809`

**Evidence:**
- R12 sets `os.environ["TRADOV_TRADING_MODE"] = str(mode)` in `__init__`.
- G05 also rewrites `TRADOV_TRADING_MODE` as the UI arms/disarms trading.
- D31 uses that env var as part of its live/paper policy resolution.

**Impact:**
This creates hidden cross-instance coupling inside a single process. A dashboard action, test, or second supervisor instance can change the effective mode seen by unrelated components.

**Assessment:**
Medium risk. Mostly a consistency / test-isolation / multi-entry-path problem today, but it directly touches safety policies.

**Spec:**
1. Stop using environment variables as the mutable runtime coordination channel.
2. Replace with an injected immutable runtime context object shared across R12, D31, G05, and B40 guards.
3. Keep env vars only as startup configuration inputs.
4. Add tests proving one supervisor/dashboard instance cannot alter another instance's mode.

---

## LOW

### L-1 — G05 truncates entry-block reason and also uses the truncated value for the tooltip
**File:**
- `Tradov/TradovG_GUI/TradovG05_TradingDashboard.py:7171-7174, 7191`

**Evidence:**
- The label text is truncated to 64 chars.
- `_update_entry_block_compact_label()` sets `label.setToolTip(message)` where `message` is the already-truncated compact text.

**Impact:**
Operators cannot inspect the full gate reason from the compact toolbar label, which weakens troubleshooting when entry trust gate blocks are repetitive or compound.

**Assessment:**
Low severity, but worth fixing because this is exactly the kind of detail operators need during soak.

**Spec:**
1. Pass both `compact_display` and `full_detail` to `_update_entry_block_compact_label()`.
2. Keep the label compact, but set the tooltip to the full rejection detail.
3. Consider a click-to-expand dialog or side-panel history for repeated block reasons.

---

## Opportunities For Improvement

### 1. Add a startup "effective routing matrix" self-audit
At startup, emit one structured record showing:
- run mode
- broker environment
- market-data environment
- whether OrderManager mid-walk is enabled
- whether entry-trust gate is fail-open or fail-closed
- whether synthetic market-condition defaults are in play

This would make pre-launch verification dramatically faster.

### 2. Add a strict autonomous mode preset
Introduce one config preset such as `AUTONOMOUS_STRICT_MODE=true` that forces:
- live-only env validation
- fail-closed entry gate
- fail-closed market-conditions availability
- no synthetic defaults
- no execution when mode context is unresolved

That gives you one explicit production posture instead of spreading safety across many local checks.

### 3. Add an order-submission forensic trail keyed by local order id and broker tag
You already log dispatch and signal-drop outcomes. Extend that to record:
- local order id
- broker tag
- broker order id
- submission attempt count
- recovery result after timeout

That would close the observability gap around the remaining B02 ghost-order problem.

---

## Overall Launch Assessment

### GREEN
- R12 policy check runs before component start.
- R12 live-mode OrderManager wiring still works.
- Paper-mode mid-walk bypass still works.
- D31 dispatch-result hardening is intact.
- C29 explicit sandbox rejection is intact.
- B40 retry-method hardening is intact.

### RED
- R12/B40 live-only policy drift on invalid env tokens.
- D31 entry-trust gate fail-open on missing/unhealthy context.

### YELLOW
- B02 stage-then-commit and ghost-order recovery remain incomplete.
- S07 synthetic defaults still mask missing metrics.
- Runtime mode still depends on mutable process-wide env state.

**Recommendation:**
1. Hold live launch until `CR-1` and `H-1` are fixed and revalidated.
2. Continue paper soak after those fixes using the existing R12/D31/C29 regression suites plus new env-typo and gate-unavailable tests.
3. Treat `H-2` as the next hardening sprint item before increasing capital size.

---

## Suggested Validation After Fixes

```bash
source .venv/bin/activate
pytest -q --no-cov \
  Tradov/TradovT_Testing/TradovT188_R12_OrderManagerWiring.py \
  Tradov/TradovT_Testing/TradovT193_D31_DispatchResultHardening.py \
  Tradov/TradovT_Testing/TradovT196_R12_LiveOnlyTradierPolicy.py \
  Tradov/TradovT_Testing/TradovT197_C29_LiveOnlyPolicy.py

source .venv/bin/activate
python - <<'PY'
import os
from Tradov.TradovR_Runtime.TradovR12_SessionSupervisor import SessionSupervisor
cases = ["live", "production", "", "typo", "sandbox", "paper"]
for value in cases:
    os.environ["TRADIER_ENVIRONMENT"] = value
    os.environ["TRADIER_MARKET_DATA_ENVIRONMENT"] = "live"
    sv = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    print(value, sv._validate_live_only_tradier_policy())
PY
```

---

## Conclusion

v27 materially improved the execution wiring, and the main regression tests covering that work are green. But the current code still has two production-facing safety gaps: the invalid-env bypass in the live-only policy boundary, and the fail-open entry-trust gate. Those are both fixable with relatively contained changes and should be resolved before autonomous live trading begins.
