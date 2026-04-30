# 2026 Autonomous Decision Contract Report

Last Updated: 2026-04-30
Owner: Spyder Core Trading Architecture
Status: Active (Current Branch Reality + Pruning Summary)

## 1. Purpose

This report consolidates the recent pruning work across symbols, signals, indicators, and strategy surface area, and documents the current trading and execution workflow now in use.

It is intended to be the single read for:
- What inputs are authoritative for autonomous decisions
- What was de-scoped or downgraded from authoritative use
- Which strategies remain active/allowed
- How a trade moves from data to execution

## 2. Source of Truth Used For This Report

Primary specifications and code/runtime references:
- 01-Overview-Specs/Autonomous-Decision-Contract.md
- 01-Overview-Specs/Gemini-Ideas/2026-04-29-Gemini Master-Spec.md
- 01-Overview-Specs/Gemini-Ideas/2026 04 29 Gemini Trimming.md
- 01-Overview-Specs/Gemini-Ideas/2026-04-29 Gemini Indicators-Signals.md
- 01-Overview-Specs/Gemini-Ideas/2026 04 29 Gemini Options-Strategies.md
- Spyder/SpyderA_Core/SpyderA02_TradingEngine.py
- Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py
- Spyder/SpyderF_Analysis/SpyderF09_EntryFilters.py
- Spyder/SpyderR_Runtime/SpyderR11_PaperStrategyRunner.py
- 01-Overview-Specs/2026-04-30-TRADING_DECISION_WORKFLOW-FULL-v3.md

## 3. Executive Pruning Summary

Recent pruning reduced complexity in three ways:

1. Decision authority was narrowed.
- Active trust-gate and regime inputs are explicit and documented.
- Analyzer-dependent hooks are no longer treated as authoritative unless dependencies are injected.

2. Strategy concurrency and horizon breadth were reduced.
- D31 now enforces MAX_CONCURRENT_STRATEGIES = 2.
- D31 now enforces MAX_ACTIVE_HORIZON_BUCKETS = 1.

3. Runtime strategy surface for paper autonomy is narrow and controlled.
- Paper runner ships with two default adapters enabled: BullPutCreditSpread and ZeroDTE_IronCondor.

## 4. Symbols, Signals, and Indicators Now Used

### 4.1 Active Entry Trust-Gate Inputs (A02 and D31 through F09)

Effective symbol inputs currently wired:
- SPY
- QQQ
- IWM
- XLK
- XLF
- VIX
- VIX9D
- VVIX
- CPC
- RVOL

Effective custom metric inputs currently wired:
- data_quality_feed
- surface_confidence
- surface_age_ms
- term_slope_0_7
- rr_25d
- fly_25d
- dealer_flow
- wall_confidence
- flow_imbalance

### 4.2 Regime Inputs (L09 + S07)

Regime symbol inputs currently used:
- SPY
- VIX
- $TICK
- $ADD
- $TRIN
- NYMO
- SKEW

Regime custom metrics and macro inputs currently used:
- DIX
- GEX
- SWAN
- VEX
- CHEX
- BREADTH_REGIME
- YIELD_SLOPE
- YIELD_INVERTED
- YIELD_10Y
- AAII_BULLISH
- AAII_BEARISH
- NAAIM_EXPOSURE

## 5. What Was Pruned, Downgraded, or De-Scoped

### 5.1 De-Scoped From Authoritative Entry Gating (unless explicitly injected)

These checks are callable in F09 but non-authoritative without analyzer injection in A02/D31 construction:
- VIX term structure analyzer path (C10 dependency)
- CBOE SKEW analyzer path (S06 dependency)
- Market internals analyzer path (C04 dependency)

Current construction remains:
- EntryFilters(config_manager) in A02
- EntryFilters(config_manager) in D31

### 5.2 Strategy-Surface Pruning

From broad library toward lean execution:
- Core orchestrators retained as authority: D30 + D31
- Lean strategy family emphasis retained: Bull Put, Bear Call, Iron Condor, Iron Butterfly
- Hard caps now actively limit simultaneous strategy exposure and horizon sprawl

### 5.3 Data/Signal Pruning and Governance Outcomes

Repository-level governance and recent cleanups:
- Canonical symbol governance centralized (SpyderU49 policy usage)
- Computed/event-only symbols excluded from direct quote baskets (for quote transport hygiene)
- DIA/RUT removed from canonical quote basket wiring; dashboard uses proxies where needed
- ES lead-lag pipeline removed from active decision path
- F09 lead-lag requirement removed from data-quality required buckets
- E01 decision-quality SLO narrowed to vol_surface + dealer_flow

### 5.4 Logging Noise Pruning (Operational)

Signal chatter moved out of NORMAL/INFO stream to DEBUG in S-series metric modules (GEX/DIX/SWAN update lines and related periodic status lines). This preserves actionable NORMAL logs for lifecycle/risk/execution visibility.

## 6. Strategies Now Active and Allowed

### 6.1 D31 Orchestrator Policy (Core Runtime)

- MAX_CONCURRENT_STRATEGIES = 2
- MAX_ACTIVE_HORIZON_BUCKETS = 1
- Lean allowlist present for:
  - BullPutSpread
  - BearCallSpread
  - IronCondor
  - IronButterfly

### 6.2 R11 Paper Autonomous Runtime (Current Operational Path)

Default enabled adapters:
- BullPutCreditSpread
- ZeroDTE_IronCondor

Global paper cap:
- max_concurrent_positions defaults to 3 in R11 unless launcher/config overrides

Important distinction:
- D31 sets production orchestration policy caps.
- R11 is the current autonomous paper execution harness and can run independently with its own adapter set and limits.

## 7. Trading and Execution Workflow (Current)

## 7.1 Core Autonomous Decision Pipeline (A02/D31 path)

1. Market conditions are fetched from S07.
2. Entry trust-gate is applied through F09 EntryFilters.
3. Regime context and strategy selection are handled by D30/D31 orchestration logic.
4. Risk validation is applied (E-series risk controls).
5. Execution dispatch proceeds through broker/order infrastructure when approved.

Practical policy outcome:
- System is intentionally more likely to reject an unsafe trade than force an entry.
- Data-quality and structure gates are first-class blockers.

## 7.2 Autonomous Paper Execution Pipeline (Q93 -> R06 -> R11)

1. Q93 launcher starts paper session and attaches R11 runner.
2. R11 tick loop fetches batched SPY + VIX quotes.
3. R11 evaluates exits for open simulated positions first.
4. R11 evaluates entries adapter-by-adapter under:
   - global concurrent cap
   - per-strategy open cap
   - entry window checks
   - cooldown
   - risk gate checks
5. Simulated fills are applied locally; no live order placement.
6. Closed trades are recorded into paper harness accounting.

Safety behavior:
- R11 refuses startup in live mode unless explicit live confirmation flag is present.
- Data fetch failures degrade safely (skip opens when quote context is unavailable).

## 8. Regime-to-Strategy Intent (Lean Contract Direction)

The active architecture direction remains six-regime gating with defined-risk strategy mapping and hard halts in crisis/event transition states. This aligns with the pruning objective: fewer moving parts, stronger determinism, tighter risk explainability.

## 9. Current-State Conclusion

The system has materially reduced decision entropy:
- Fewer authoritative gates than before (clear active vs non-authoritative paths)
- Lower strategy concurrency and horizon complexity in D31
- Narrower autonomous paper strategy surface in R11
- Cleaner operational logs (signal telemetry demoted to DEBUG)

Net effect:
- Better auditability
- Faster root-cause analysis for no-entry/entry decisions
- Lower collision risk across competing strategies
- Improved safety posture for autonomous operation
