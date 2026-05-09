# Trading Decision Workflow (Who Decides, How, and Concurrency)

Last Updated: 2026-04-29
Scope: Current branch behavior (fix/audit-v14-all)
Companion Visual: [Trading Decision - One Page](../01-Overview-Specs/Trading-Decision-One-Page.md)

## Executive Summary

Spyder decision-making happens in layers, not in one module:

1. Market data and analytics layers produce state (SPY, options chain/Greeks, VIX, regime).
2. Strategy-orchestration layers decide which strategy families are active and how capital is allocated.
3. Signal-gating layers decide whether a specific signal is trusted and risk-approved.
4. Execution layers decide how an approved order is routed (mid-walk vs market fallback).

In short:

- "Which strategy should be active?" is primarily decided by D31 (with regime input from L09/C10 and optional Y01/Y02 advisory).
- "Can this exact trade go out?" is decided by E01 risk validation (+ trust gates).
- "How is the order sent?" is decided by D31 dispatch to B02/B40 or LiveEngine.

## End-to-End Decision Flow

```mermaid
flowchart TD
		A[Market Inputs\nSPY quotes, options chain/Greeks, VIX, custom metrics] --> B[Analysis & Regime\nF-series + L09 + C10]
		B --> C[Strategy Universe Control\nD31 StrategyOrchestrator]
		C --> D[Signal Emission\nEventType.STRATEGY_SIGNAL]
		D --> E[Entry Trust Gate\nD31/F09 + S07 conditions]
		E --> F[Risk Gate\nE01 validate_signal]
		F -->|Approved| G[Dispatch\nD31 _dispatch_approved_signal]
		F -->|Rejected| H[Risk Alert + Drop]
		G --> I[Execution\nB02 OrderManager + B40 TradierClient\n(or R04 LiveEngine fallback)]
		I --> J[Fills/State\nOrder lifecycle + telemetry]

		K[Y01/Y02/Y03/Y08 AutoAgents] -.advisory + veto topics.-> C
		L[X03/X04 On-demand agents] -.decision support.-> C
		M[V-series Quant models] -.pricing/risk intelligence.-> C
```

## Detailed Ownership Map

### 1) Market/State Inputs (What the system knows)

- Tradier market data and options chain/Greeks are accessed in B40.
	- Quotes: get_quotes
	- Chains: get_option_chain / get_option_chain_with_greeks
- VIX regime context is provided by C10 VIXAnalyzer and wired into D31 via set_vix_analyzer.
- Regime classification in orchestration prefers L09 UnifiedRegimeEngine when injected, otherwise D31 fallback heuristics.
- Trust-quality conditions come from S07 metrics via A02/D31 trust-gate checks.

Primary references:

- Spyder/SpyderB_Broker/SpyderB40_TradierClient.py
- Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py
- Spyder/SpyderC_MarketData/SpyderC10_VIXAnalyzer.py
- Spyder/SpyderA_Core/SpyderA02_TradingEngine.py

### 2) Strategy Selection (Which strategies are active)

Primary owner: D31 StrategyOrchestrator.

How it decides:

1. Updates market regime (_update_market_regime).
2. Reads regime-to-strategy weight map (_get_regime_strategy_weights).
3. Configures/adjusts active strategy set (_configure_strategies_for_regime and _adaptive_strategy_management).
4. Rebalances capital allocations (_execute_rebalancing and allocation scoring).

Important nuance:

- Y02 StrategyPilot and Y08 MetaOrchestrator provide advisory/coordination through agent-bus topics (market.regime, signals.validated), but D31 remains the direct runtime orchestrator of strategy activation and routing.

Primary references:

- Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py
- Spyder/SpyderY_AutoAgents/SpyderY02_StrategyPilotAgent.py
- Spyder/SpyderY_AutoAgents/SpyderY08_MetaOrchestratorAgent.py

### 3) Trade Eligibility (Should this specific signal execute)

Primary owner: E01 RiskManager via validate_signal.

Pre-risk trust gate:

- D31 _on_strategy_signal first applies entry trust policy checks (_passes_entry_trust_gate).

Risk gate:

- D31 converts raw signal to RiskValidationRequest and calls E01 validate_signal.
- E01 enforces risk limits and decision-quality SLO checks.
- Rejected signals are dropped and surfaced as risk alerts/telemetry.

Primary references:

- Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py
- Spyder/SpyderE_Risk/SpyderE01_RiskManager.py
- Spyder/SpyderA_Core/SpyderA02_TradingEngine.py

### 4) Execution Mechanics (How approved trades are sent)

Primary owner: D31 dispatch + B02/B40 execution path.

Routing logic:

1. If signal has bid/ask and OrderManager is wired, D31 uses mid-price walk path via B02 submit_limit_with_walk.
2. Otherwise, falls back to market-style execution via LiveEngine execute_order path.
3. B40 performs actual broker API calls and order lifecycle management.

Primary references:

- Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py
- Spyder/SpyderB_Broker/SpyderB02_OrderManager.py
- Spyder/SpyderB_Broker/SpyderB40_TradierClient.py
- Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py

## Answering the Three Core Questions

### Q1: Who makes the decision which strategy to execute?

Short answer: D31 StrategyOrchestrator is the runtime decision owner.

Supporting context:

- D31 decides which strategies are active for the current regime and how capital is distributed.
- Y02/Y08 and X03 can influence via recommendations and validations, but they are not the final direct execution authority in the core orchestration loop.
- E01 can veto trade-level signals even if strategy is active.

### Q2: How is the decision made?

Decision stack:

1. Market regime + volatility context (L09/C10 + SPY/VIX features).
2. Regime-weighted strategy mapping and allocation in D31.
3. Signal-level trust gate (entry conditions and S07 quality checks).
4. Typed risk validation in E01 (validate_signal).
5. Execution method selection (mid-walk vs fallback) and broker submission.

This means strategy selection is portfolio-level, while approval is trade-level.

### Q2.1: How are symbols/metrics weighted across the six regimes?

This section mirrors the policy-aligned mapping in
`01-Overview-Specs/Autonomous-Decision-Contract.md` so both docs stay consistent.

| Regime | Primary symbols to weight | Primary metrics to weight | Typical gate emphasis |
|---|---|---|---|
| bull_trend | SPY, QQQ, XLK, VIX, VIX9D | BREADTH_REGIME, GEX, DIX, dealer_flow, flow_imbalance | Confirm SPY-relative leadership (QQQ/XLK), reject weak participation (RVOL), guard against short-term vol stress (VIX9D/VIX) |
| bear_trend | SPY, IWM, XLF, VIX, VVIX | BREADTH_REGIME, SWAN, CHEX, wall_confidence, dealer_flow | Confirm downside breadth/financial weakness (IWM/XLF), tighten CPC/VVIX stress checks, require strong data_quality_feed |
| range_calm | SPY, VIX, VIX9D, CPC | GEX, DIX, BREADTH_REGIME, rr_25d, fly_25d | Favor neutral participation and stable vol-of-vol; block if cross-index confirmation or surface quality deteriorates |
| high_vol_mean_reversion | SPY, VIX, VIX9D, VVIX, SKEW | SWAN, VEX, CHEX, rr_25d, fly_25d, term_slope_0_7 | Emphasize vol-shock containment, skew/term-structure quality, and stricter surface_confidence/surface_age_ms thresholds |
| crisis_turbulent | SPY, VIX, VVIX, $TICK, $ADD, $TRIN | SWAN, CHEX, BREADTH_REGIME, YIELD_INVERTED, YIELD_SLOPE | Prefer hard-block posture; strongest dependence on data_quality_feed, stress metrics, and internals where available |
| event_transition | SPY, VIX, VIX9D, QQQ, IWM, XLK, XLF | BREADTH_REGIME, DIX, GEX, YIELD_10Y, AAII_BULLISH, AAII_BEARISH, NAAIM_EXPOSURE | Event-clock style caution: maintain confirmation gates, reduce trust in stale/aging surface inputs, and avoid over-reliance on any single macro print |

Interpretation:

- Section 1 inputs remain the active A02/D31 entry trust-gate contract.
- Section 2 inputs remain the broader regime-classification contract.
- This mapping defines weighting intent by regime, not an additional gate list.

### Q2.2: What role does HMM play in regime classification?

Hidden Markov Model (HMM) is a regime-inference method used inside the regime stack. It is not itself a raw market input. Only explicit downstream HMM outputs that are exported and consumed by decision logic should be listed in this contract.

The regime stack may use HMM / Markov-switching methods internally (`SpyderL09_UnifiedRegimeEngine`, `SpyderE21_HMMRegimeDetector`, `SpyderM06_HMMRegimeDetector`). These are implementation details of how `regime_label` and `regime_confidence` are derived — they are not additional contract keys.

### Q3: How many strategies can execute at the same time?

Current branch reality:

- D31 defines MAX_CONCURRENT_STRATEGIES = 8 (intended orchestration cap).
- D31 now hard-enforces this cap in `add_strategy` (configurable via SPYDER_MAX_CONCURRENT_STRATEGIES).
- D31 also enforces horizon-bucket diversification with MAX_ACTIVE_HORIZON_BUCKETS = 3 (configurable via SPYDER_MAX_ACTIVE_HORIZON_BUCKETS).
- A02 TradingEngine enforces max_strategies default of 20 for registered strategies.

Important implementation note:

- Strategy admission can now fail immediately when either the concurrent strategy cap or the horizon-bucket cap is exceeded.
- Bucket classification defaults to `ultra_short` (0DTE/ZeroDTE), `short` (intraday/1DTE class), and `swing` (calendar/diagonal/longer decay), with optional per-strategy override via `config['horizon_bucket']`.

Operational interpretation:

- Hard orchestrated active-set cap: 8 by default.
- Hard active horizon-bucket cap: 3 by default.
- Engine registration hard cap (default): 20.
- Actual tradable/approved concurrent activity can be lower due to E01 risk checks and circuit-breaker states.

## OPRA / Data-Provider Note (Current Branch)

You referenced OPRA pricing and Massive.

On this branch:

- B40 contains OPRA-vetter controls (SPYDER_OPRA_REQUIRE_VETTER).
- C29 DataProviderRouter currently routes to Tradier as sole active provider in code.
- C27 Massive client is not present at the expected path in this workspace snapshot.

So the workflow above is intentionally documented to match current implemented routing, not historical module inventory text.

## Practical Monitoring Checklist

When you want to verify decision behavior in runtime, inspect these in order:

1. D31 regime state and allocation map.
2. D31 signal drop counters / risk-rejection telemetry.
3. E01 validate_signal rejection reasons.
4. B02 order routing path (mid-walk vs fallback).
5. B40 broker responses and fill lifecycle.
6. Y03 veto and Y08 conflict-resolution topics for autonomous-agent influence.

