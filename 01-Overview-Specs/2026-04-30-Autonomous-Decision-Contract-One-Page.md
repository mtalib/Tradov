# 2026 Autonomous Decision Contract - One-Page Executive Brief

Last Updated: 2026-04-30
Audience: PR reviewers, operators, and stakeholders

## 1) What Changed

We completed a focused pruning pass to reduce decision complexity, strategy collisions, and operational noise.

Key outcomes:
- Decision inputs are now explicitly separated into authoritative trust-gate inputs vs broader regime context.
- Strategy orchestration breadth was reduced (concurrency and horizon caps tightened).
- Autonomous paper execution is running on a narrow, controlled adapter set.
- Signal chatter (GEX/DIX/SWAN periodic updates) was demoted from NORMAL logs to DEBUG.

## 2) Symbols, Signals, and Indicators Now Used

### Active Entry Trust-Gate Inputs (authoritative path)

Core effective symbols:
- SPY, QQQ, IWM, XLK, XLF
- VIX, VIX9D, VVIX
- CPC, RVOL

Core effective custom metrics:
- data_quality_feed
- surface_confidence, surface_age_ms
- term_slope_0_7, rr_25d, fly_25d
- dealer_flow, wall_confidence, flow_imbalance

### Regime Context Inputs (classification layer)

Symbols:
- SPY, VIX, $TICK, $ADD, $TRIN, NYMO, SKEW

Metrics/macros:
- DIX, GEX, SWAN, VEX, CHEX, BREADTH_REGIME
- YIELD_SLOPE, YIELD_INVERTED, YIELD_10Y
- AAII_BULLISH, AAII_BEARISH, NAAIM_EXPOSURE

## 3) What Was Pruned or Downgraded

- Analyzer-dependent checks remain non-authoritative unless dependencies are injected (VIX term-structure analyzer, SKEW analyzer, internals analyzer).
- ES lead-lag decision path was removed from active decision flow.
- Decision-quality SLO narrowed to high-value structure checks (vol_surface + dealer_flow).
- Computed/event-only symbols are excluded from direct quote-basket transport paths.

## 4) Strategy Surface Reduction

### Production orchestration policy (D31)
- MAX_CONCURRENT_STRATEGIES = 2
- MAX_ACTIVE_HORIZON_BUCKETS = 1
- Lean allowlist family in use: BullPutSpread, BearCallSpread, IronCondor, IronButterfly

### Autonomous paper runtime (R11)
- Default active adapters: BullPutCreditSpread + ZeroDTE_IronCondor
- Tick loop flow: exits first, then entry checks under cap/window/cooldown/risk gates
- Simulated fills only; no live order placement in paper mode

## 5) Trading and Execution Workflow

### Core autonomous decision flow (A02/D31 path)
1. Pull market conditions from S07.
2. Apply F09 trust-gate filters.
3. Apply regime/strategy gating (D30/D31).
4. Apply risk validation.
5. Dispatch execution only if all gates pass.

### Paper autonomous execution flow (Q93 -> R06 -> R11)
1. Launch session and attach strategy runner.
2. Fetch batched SPY/VIX quote context each tick.
3. Evaluate exits for open positions.
4. Evaluate entries adapter-by-adapter with hard caps and gates.
5. Simulate fills locally and record outcomes.

## 6) Operational Validation Snapshot

- Paper smoke run completed successfully with strategy opening confirmed.
- Target signal-noise phrases (DIX/SWAN/GEX periodic lines) are absent from captured NORMAL output.
- Modified signal modules pass Python compile checks.

## 7) Why This Matters

This pruning pass improves:
- Determinism and explainability of trade decisions
- Safety posture (reject unsafe trades earlier)
- Debuggability (clear no-entry reasons and cleaner NORMAL logs)
- Runtime stability by reducing competing strategy pressure

## 8) Reference Documents

- Primary report: 01-Overview-Specs/2026-04-30-Autonomous-Decision-Contract.md
- Active contract: 01-Overview-Specs/Autonomous-Decision-Contract.md
