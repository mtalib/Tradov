# Tradov Trading Decision - One Page Visual

Last Updated: 2026-06-23
Scope: Current workflow snapshot (v49)
Detailed Walkthrough: [Trading Decision Workflow](./2026-06-23-TRADING_DECISION_WORKFLOW-FULL-v50.md)

## At a Glance

- Strategy-set decision owner: D31 StrategyOrchestrator.
- Signal approval owner: E26 PairRiskManager plus E01 validation gates.
- Execution routing owner: D31 dispatch into B02/B40 pair execution.
- Default session feed now falls back to the pair-quote basket when `FEED_SYMBOLS` is unset.
- Startup routing now reports pair-feed coverage so operators can tell whether scans can actually form.
- Pair-trading signals route through the coordinated pair executor before any single-leg fallback.
- Distance-based stat-arb still needs its formation warmup before it emits actionable signals.
- Agent role: X/Y agents are advisory and coordination-heavy; Y03 can veto via risk topics.
- PCA-Proxy / PCA-IV role: S07/S14 custom-metric observability only; they are not hard regime triggers or execution gates in the current workflow.

## Decision Pipeline (Visual)

```mermaid
flowchart LR
    subgraph S1[State Formation]
        A1[Pair prices + market data\nC01/C29 + B40]
        A2[Regime inputs + market context\nS07 + L09]
        A3[Custom Metrics / Trust Context\nS07 metrics + PCA observability + F09 checks]
        A4[Startup routing receipt\nPair-feed coverage + session context]
    end

    subgraph S2[Portfolio Decision]
        B1[D31 Update Regime]
        B2[D31 Select Stat-Arb Family\nCompatibility selector]
        B3[D31 Allocate/Rebalance Capital]
    end

    subgraph S3[Signal Decision]
        C1[Strategy emits signal\nEventType.STRATEGY_SIGNAL]
        C2[D31 Entry Trust Gate]
        C3[E01 validate_signal]
        C4{Approved?}
    end

    subgraph S4[Execution Decision]
        D1[Pair route\nB02 PairOrderExecutor]
        D2[Recovery route\nB03 / E26 reconciliation]
        D3[B40 Broker API execution\norders/fills/status]
    end

    A1 --> B1
    A2 --> B1
    A3 --> C2
    A4 -.-> B1
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
- Hard orchestration cap in D31: MAX_CONCURRENT_STRATEGIES = 3 (override: TRADOV_MAX_CONCURRENT_STRATEGIES).
- Hard horizon-bucket cap in D31: MAX_ACTIVE_HORIZON_BUCKETS = 2 (override: TRADOV_MAX_ACTIVE_HORIZON_BUCKETS).
- Pair-trading open-pair cap: 3 (configurable via `PAIR_TRADING_MAX_OPEN`).
- Practical active count is constrained by the global concurrency cap, the pair open-pair cap, risk gates, and runtime circuit-breakers.

## Current Branch Data-Provider Reality

- C29 DataProviderRouter is currently Tradier-only in code.
- Massive/C27 routing is not active at the expected path in this branch snapshot.

## Fast Operational Check

1. D31 regime and allocation state.
2. D31 dropped-signal and rejection telemetry.
3. E01 rejection reasons.
4. B02 route used (mid-walk vs fallback).
5. B40 broker response and fill lifecycle.
