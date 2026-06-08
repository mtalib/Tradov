# Tradov — SPY Options Algorithmic Trading Specification Package

A coherent five-document specification for building an autonomous SPY 0DTE iron condor trading system on Python 3.11+ / Ubuntu / Tradier.

The original strategy reference (`SPY_Options_Algo_Strategies_Report.md`) is the catalog. This package is the **build plan** for the highest-priority strategy in that catalog.

---

## Document Map

| Spec | Title | Purpose | Read order |
|---|---|---|---|
| [SPEC-TRADOV-01](./SPEC-TRADOV-01_0DTE_IronCondor.md) | 0DTE Iron Condor Strategy Module | The strategy itself: state machine, entry gates, strike selection, position management | 4th |
| [SPEC-TRADOV-02](./SPEC-TRADOV-02_Backtesting_Framework.md) | Backtesting Framework | Reproducible event-driven backtester that gates live deployment | 3rd |
| [SPEC-TRADOV-03](./SPEC-TRADOV-03_Tradier_Integration.md) | Tradier Broker Integration | REST + WebSocket client; multileg orders; audit; reconciliation | 2nd |
| [SPEC-TRADOV-04](./SPEC-TRADOV-04_Greeks_Engine.md) | Greeks Engine | Black-Scholes pricing/greeks/IV, IV Rank, portfolio greeks | 1st (foundation) |
| [SPEC-TRADOV-05](./SPEC-TRADOV-05_Agent_Tasks.md) | Coding Agent Task Tickets | Atomic, sized tickets to implement specs 01–04 in dependency order | 5th — execution |

Read in order 04 → 03 → 02 → 01 → 05 to mirror the dependency graph.

---

## Build Order at a Glance

```
Phase 0  Repo skeleton                           1 ticket   (~30 min)
Phase 1  Greeks engine                           4 tickets  (~3 h, ends with GATE Q04)
Phase 2  Tradier broker                          5 tickets  (~5 h, ends with GATE B05)
Phase 3  Backtest foundation                     4 tickets  (~5 h, ends with GATE D04)
Phase 4  The 0DTE iron condor strategy           4 tickets  (~4 h, ends with GATE S04)
Phase 5  Live wiring + 5-day sandbox soak        3 tickets  (~2 h + 5 trading days, ends with GATE L03)
Phase 6  Production cutover                      Human-only  (deliberately not agent-executable)
```

Five gates require human review before downstream work proceeds. Each gate exists where a wrong-but-plausible mistake would silently corrupt everything that follows.

---

## Design Principles

1. **One protocol, two implementations.** Strategies depend on `Context` and `BrokerProtocol`. The live and backtest contexts are interchangeable. The strategy code that survives a backtest is *literally* the same file that runs live.
2. **Local-first persistence.** SQLite + Parquet on the dev box. Matches the Captova-ARC convention. No cloud dependency for trading logic.
3. **Audit everything.** Every Tradier API call is persisted (token-scrubbed). Every state transition logs a structured JSON line. Every trade snapshots its full config.
4. **Gates over tests alone.** Tests prove the code does what it says. Gates ensure a human reviews the *thing* itself — sample reports, sandbox lifecycles, walk-forward validation — before risk compounds.
5. **Production safety is layered.** Three independent guards prevent accidental live trades: config-load check, environment-variable confirmation, per-order quantity ceiling.
6. **Greeks computed locally.** We use Tradier's ORATS-sourced greeks for cross-validation, not as the source of truth. Live and backtest both compute their own from current quotes.

---

## What This Specification Doesn't Cover

- **Other strategies** (Wheel, gamma scalping, calendar spreads, VRP) — the strategy catalog has the parameters; building those is a separate sub-package per strategy. The framework here is designed to host them; each new strategy gets its own SPEC-TRADOV-NN file mirroring the structure of SPEC-01.
- **GUI** — Tradov's lettered convention reserves G for GUI. A PySide6 monitoring dashboard is a *consumer* of the persistence layer, not part of the trading system. It can be added later without touching strategies.
- **Capital allocation across strategies** — Once multiple strategies coexist, a portfolio manager layer sits above them. Out of scope for the first build.
- **Tax accounting** — A reporting layer reads the persistence DB and produces 1099-friendly outputs. Not a trading concern.
- **Regulatory compliance review** — A human responsibility before going live. No software substitutes for it.

---

## Risk Disclaimer

Options trading carries substantial risk of loss. The strategies described — particularly 0DTE iron condors with negative gamma — can lose multiples of the credit collected on a single trade if the underlying breaches a short strike near expiration. Backtested performance does not predict future results, and walk-forward validation can still overfit to a regime that ends the day production starts. Every gate in this specification exists for a reason. None of this constitutes financial advice.
