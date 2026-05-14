# Spyder Trading Decision - One Page Visual

Last Updated: 2026-05-10
Scope: Current workflow snapshot (v19)
Detailed Walkthrough: [Trading Decision Workflow](./2026-05-10-TRADING_DECISION_WORKFLOW-FULL-v19.md)

## At a Glance

- Strategy-set decision owner: D31 StrategyOrchestrator.
- Trade-level approval owner: E01 RiskManager (validate_signal).
- Execution routing owner: D31 dispatch into B02/B40 (or LiveEngine fallback).
- Agent role: X/Y agents are advisory and coordination-heavy; Y03 can veto via risk topics.
- PCA-Proxy / PCA-IV role: S07/S14 custom-metric observability only; they are not hard regime triggers or execution gates in the current workflow.

## Decision Pipeline (Visual)

```mermaid
flowchart LR
    subgraph S1[State Formation]
        A1[SPY + Options Quotes/Chain\nB40 TradierClient]
        A2[VIX + Regime Inputs\nC10 + L09]
        A3[Custom Metrics / Trust Context\nS07 metrics + PCA observability + F09 checks]
    end

    subgraph S2[Portfolio Decision]
        B1[D31 Update Regime]
        B2[D31 Select Strategy Mix\nRegime weight map]
        B3[D31 Allocate/Rebalance Capital]
    end

    subgraph S3[Signal Decision]
        C1[Strategy emits signal\nEventType.STRATEGY_SIGNAL]
        C2[D31 Entry Trust Gate]
        C3[E01 validate_signal]
        C4{Approved?}
    end

    subgraph S4[Execution Decision]
        D1[Mid-walk route\nB02 submit_limit_with_walk]
        D2[Fallback route\nR04 execute_order]
        D3[B40 Broker API execution\norders/fills/status]
    end

    A1 --> B1
    A2 --> B1
    A3 --> C2
    B1 --> B2 --> B3 --> C1 --> C2 --> C3 --> C4
    C4 -->|Yes| D1 --> D3
    C4 -->|Yes, no quote/walk path| D2 --> D3
    C4 -->|No| X1[Drop + Risk Alert]

    Y1[Y01/Y02/Y08\nregime + validation advisory] -.-> B1
    Y2[Y03 RiskSentinel\nveto authority topics] -.-> C3
    X3[X03/X04\nstrategy/risk guidance] -.-> B2
    V1[V-series QuantModels\npricing/risk intelligence] -.-> B2
```

## Who Decides What

1. Which strategy executes:
D31 StrategyOrchestrator decides active strategy set and allocation.

2. How the decision is made:
Regime classification -> regime-to-strategy mapping -> trust gate -> E01 risk validation -> execution route selection.

3. How many strategies can run simultaneously:
- Hard orchestration cap in D31: MAX_CONCURRENT_STRATEGIES = 2 (override: SPYDER_MAX_CONCURRENT_STRATEGIES).
- Hard horizon-bucket cap in D31: MAX_ACTIVE_HORIZON_BUCKETS = 2 (override: SPYDER_MAX_ACTIVE_HORIZON_BUCKETS).
- Engine registration cap in A02 (default): max_strategies = 20.
- Practical active count is at most 2 at once: one long-term/swing strategy and one intraday/0DTE strategy, still constrained further by regime map, capital, E01 risk gates, and runtime circuit-breakers.

## Current Branch Data-Provider Reality

- OPRA-vetter toggle exists in B40 via SPYDER_OPRA_REQUIRE_VETTER.
- C29 DataProviderRouter is currently Tradier-only in code.
- Massive/C27 routing is not active at the expected path in this branch snapshot.

## Fast Operational Check

1. D31 regime and allocation state.
2. D31 dropped-signal and rejection telemetry.
3. E01 rejection reasons.
4. B02 route used (mid-walk vs fallback).
5. B40 broker response and fill lifecycle.
