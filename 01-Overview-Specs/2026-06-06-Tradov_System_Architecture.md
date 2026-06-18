# Tradov: Multi-Agent LLM Trading Platform

## Architecture & Design Document

**Version:** 1.0
**Date:** 2026-06-06
**Author:** Tradov Team

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [How Tradov Uses TradingAgents](#2-how-tradov-uses-tradingagents)
3. [System Architecture](#3-system-architecture)
4. [Boot Sequence](#4-boot-sequence)
5. [Agent System](#5-agent-system)
6. [Signal Layer](#6-signal-layer)
7. [Strategy Layer](#7-strategy-layer)
8. [Risk Management](#8-risk-management)
9. [Broker Integration](#9-broker-integration)
10. [ML/AI Layer](#10-mlai-layer)
11. [Market Data Pipeline](#11-market-data-pipeline)
12. [GUI Dashboard](#12-gui-dashboard)
13. [Pair Trading](#13-pair-trading)
14. [Multi-Strategy Coexistence](#14-multi-strategy-coexistence)
15. [Configuration & Deployment](#15-configuration--deployment)

---

## 1. Executive Summary

Tradov is a production-grade, multi-agent stock and ETF trading platform that combines two trading paradigms into a single system:

- **Directional Equity/ETF Trading** — the primary strategy that trades stocks and ETFs based on regime detection, volatility analysis, and market-context signals.
- **Statistical Arbitrage (Pair Trading)** — a secondary strategy that exploits mean-reverting spreads between cointegrated equity and ETF pairs using Kalman filter hedge ratios and z-score entry/exit.

Legacy option-derived analytics and symbols still exist in a few modules for context, but they are not part of the active execution path.

The system is built on top of the architectural patterns from [TradingAgents](https://github.com/tauricresearch/tradingagents), an open-source LangGraph-based multi-agent framework. Tradov adapts TradingAgents' agent-debate-decision pipeline into a real-time, 24/7 trading system with live broker integration, GUI monitoring, and institutional-grade risk management.

### Key Numbers

| Metric | Value |
|--------|-------|
| Production modules | 200+ |
| Test files | 200+ |
| Agent classes | 31 (20 X-series + 11 Y-series) |
| Signal sources | 14 (S01-S18) |
| Strategies | 27 (D01-D42) |
| Risk checks | 10 gates |
| LLM providers | 11 (OpenAI, Anthropic, Google, xAI, Ollama, etc.) |
| Code lines | ~150,000 |

---

## 2. How Tradov Uses TradingAgents

### What is TradingAgents?

[TradingAgents](https://github.com/tauricresearch/tradingagents) is an open-source project by Tauric Research that implements a **multi-agent debate pipeline** for trading decisions. Its architecture models a real-world trading firm:

```
Market Analyst → Sentiment Analyst → News Analyst → Fundamentals Analyst
    → Bull Researcher vs Bear Researcher (debate)
    → Research Manager (judge)
    → Trader (propose)
    → Aggressive vs Conservative vs Neutral Debators (risk debate)
    → Portfolio Manager (final decision)
```

Key design patterns from TradingAgents:

| Pattern | Description |
|---------|-------------|
| **LangGraph StateGraph** | Directed Acyclic Graph workflow — agents execute as nodes, state flows through edges |
| **Two-tier LLM** | `deep_thinking_llm` for complex reasoning (GPT-5.5), `quick_thinking_llm` for fast tasks (GPT-5.4-mini) |
| **Structured output** | Pydantic schemas for agent responses, with free-text fallback |
| **Tool-augmented agents** | Analysts call data-fetching tools via LangGraph `ToolNode` |
| **Debate loops** | Bull vs Bear researchers, and risk debators, argue in controlled rounds |
| **Agent state flow** | Single `AgentState` TypedDict passed through every node |
| **Memory/learning** | Persistent decision log with post-trade reflections |
| **Factory pattern** | Every agent created by a `create_*` function injected with its LLM instance |

### What Tradov Adopted

Tradov adopted the **architectural patterns** and **agent role taxonomy** from TradingAgents, but rebuilt everything for production trading:

| TradingAgents Concept | Tradov Implementation |
|---|---|
| `TradingAgentsGraph` orchestrator | `TradovX25_TradingGraph` — same LangGraph StateGraph topology |
| Market Analyst | `TradovX01_MarketAnalystAgent` |
| Sentiment Analyst | `TradovX02_SentimentAnalystAgent` |
| News Analyst | `TradovX03_NewsAnalystAgent` |
| Fundamentals Analyst | `TradovX05_FundamentalsAnalystAgent` |
| Bull Researcher | `TradovX06_BullResearcherAgent` |
| Bear Researcher | `TradovX10_BearResearcherAgent` |
| Research Manager | `TradovX15_ResearchManagerAgent` |
| Trader | `TradovX17_TraderAgent` |
| Aggressive Debator | `TradovX18_AggressiveDebatorAgent` |
| Conservative Debator | `TradovX19_ConservativeDebatorAgent` |
| Portfolio Manager | `TradovX20_PortfolioManagerAgent` |
| `AgentState` TypedDict | `TradovX21_AgentStates` |
| Two-tier LLM | `TradovX22_DefaultConfig` + `TradovX23_LLMClientFactory` |
| Memory/learning | `TradovX24_MemoryLog` |
| `GraphSetup` + `Propagator` | `TradovX25_TradingGraph` |

### What Tradov Added Beyond TradingAgents

TradingAgents is a **research framework** — it produces trading recommendations but doesn't execute trades. Tradov extends it into a **production trading system**:

| Capability | TradingAgents | Tradov |
|---|---|---|
| Broker integration | None | Tradier REST API (B40) with real order execution |
| Live trading | None | Paper + Live modes via SessionSupervisor (R12) |
| GUI | None | PySide6 dashboard with 130 widget files (G-series) |
| Real-time data | yfinance only | Tradier API + yfinance + Alpha Vantage + TradingView scraping |
| Risk management | Debate-based only | 10-gate risk pipeline (E01) with circuit breakers, position limits, Greek caps |
| Regime detection | None | UnifiedRegimeEngine (L09) — ML ensemble + signal consensus |
| Pair trading | None | Full stat-arb pipeline: cointegration → Kalman filter → z-score execution |
| 24/7 agents | None | Y-series autonomous agents (Y01-Y10) with scheduling and health monitoring |
| Signal layer | None | 14 signal sources (S-series) — DIX, GEX, Black Swan, PCA, FRED, etc. |
| Strategy orchestration | None | D31 StrategyOrchestrator — regime-aware capital allocation |
| Position tracking | None | Fill-driven tracking (B03) with pair position groups |
| Event system | None | Central pub/sub EventManager (A05) with 20+ event types |
| Multi-strategy isolation | None | Per-strategy risk buckets, capital ring-fencing, cross-strategy conflict detection |

---

## 3. System Architecture

Tradov is organized into 20 module series, each prefixed with `Tradov` and a letter code:

```
Tradov/
├── TradovA_Core/          — Core engine, configuration, events, scheduler
├── TradovB_Broker/        — Broker integration, order management, execution
├── TradovC_MarketData/    — Market data feeds, validation, caching
├── TradovD_Strategies/    — Trading strategies, orchestration, pair discovery
├── TradovE_Risk/          — Risk management, position sizing, circuit breakers
├── TradovF_Analysis/      — Technical analysis, indicators, entry filters
├── TradovG_GUI/           — PySide6 dashboard (130 files)
├── TradovH_Storage/       — Data access layer, session database
├── TradovI_Integration/   — Message bus, module registry
├── TradovJ_Alerts/        — Alert management, Telegram bot
├── TradovK_Reports/       — Reporting, analytics
├── TradovL_ML/            — ML models, regime engine, predictors
├── TradovM_Monitoring/    — System monitoring
├── TradovO_TradingIntelligence/ — Higher-order trading logic
├── TradovP_PortfolioMgmt/ — Capital allocation, portfolio management
├── TradovQ_Scripts/       — CLI launchers, utilities
├── TradovR_Runtime/       — Live engine, paper broker, session supervisor
├── TradovS_Signals/       — Signal computation (DIX, GEX, PCA, Black Swan)
├── TradovU_Utilities/     — Logger, error handler, constants, symbol catalog
├── TradovV_QuantModels/   — Quantitative models
├── TradovX_Agents/        — On-demand LLM agents (TradingAgents-style)
├── TradovY_AutoAgents/    — Autonomous 24/7 agents (daemons)
└── TradovZ_Communication/ — Inter-module communication
```

### Data Flow Overview

```
                           ┌─────────────────────┐
                           │   Market Data Feeds  │
                           │ (Tradier, yfinance,  │
                           │  Alpha Vantage, TV)  │
                           └──────────┬──────────┘
                                      │
                           ┌──────────▼──────────┐
                           │    C01 DataFeed      │
                           │  C06 DataValidator   │
                           │  C16 Cache           │
                           └──────────┬──────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                  │
          ┌─────────▼──────┐ ┌───────▼────────┐ ┌──────▼───────┐
          │  S-Signals      │ │  L-ML Layer    │ │  X-Agents    │
          │ (DIX,GEX,SWAN,  │ │  L09 Regime    │ │  (LLM debate │
          │  PCA,VIX,...)   │ │  L01 Predictor │ │   pipeline)  │
          └─────────┬──────┘ └───────┬────────┘ └──────┬───────┘
                    │                 │                  │
                    └─────────────────┼─────────────────┘
                                      │
                           ┌──────────▼──────────┐
                           │  D31 Orchestrator    │
                           │  (strategy dispatch) │
                           └──────────┬──────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                  │
          ┌─────────▼──────┐ ┌───────▼────────┐        │
          │  D42 Pair       │ │  D03-D26       │        │
          │  Trading        │ │  Options        │        │
          │  Strategy       │ │  Strategies     │        │
          └─────────┬──────┘ └───────┬────────┘        │
                    │                 │                  │
                    └─────────────────┼─────────────────┘
                                      │
                           ┌──────────▼──────────┐
                           │  E01 Risk Manager    │
                           │  (10-gate pipeline)  │
                           └──────────┬──────────┘
                                      │
                           ┌──────────▼──────────┐
                           │  B02 Order Manager   │
                           │  B40 Tradier Client  │
                           └──────────┬──────────┘
                                      │
                           ┌──────────▼──────────┐
                           │     Tradier API      │
                           │   (live execution)   │
                           └─────────────────────┘
```

---

## 4. Boot Sequence

Tradov boots through a carefully ordered sequence managed by `TradovA01_Main` and `TradovR12_SessionSupervisor`:

### Phase 1: Application Start (`TradovA01_Main.py`)

1. **Logging** — `TradovLogger.initialize_logging()` → DEBUG+ to `~/kill/logs/tradov_YYYYMMDD.log`
2. **Capability report** — checks for PySide6, sklearn, hmmlearn, zmq, QuantLib, uvloop
3. **Core systems init:**
   - `EventManager` (A05) singleton — central pub/sub bus
   - Optional Telegram bot (J05)
   - Optional SessionSupervisor autostart
   - TradingAgents LLM pipeline (`TradovX25_TradingGraph`)
4. **GUI start** — lazy-loads PySide6, creates `TradovG05_TradingDashboard`, defers heavy init to after first paint

### Phase 2: Session Start (`TradovR12_SessionSupervisor.py`)

When the operator clicks "Start Trading":

```
 1. EventManager         (A05)  — shared event bus
 2. DataFeed             (C01)  — market data stream
 3. DataFreshnessMonitor (E24)  — stale data detection
 4. Broker               (B40 live / R15 paper)
 5. FillReconciler       (R13)  — background fill polling
 6. PositionTracker      (B03)  — fill-driven position tracking
 7. RiskManager          (E01)  — fail-closed risk gates
 8. LiveEngine           (R04)  — order routing + session DB
 9. StrategyOrchestrator (D31)  — strategy allocation + regime engine
10. ExitMonitor          (R14)  — monitors positions for exit conditions
11. LivenessMonitor      (R05)  — heartbeat + /healthz
12. Boot orphan sweep    — reconcile pre-existing broker positions
13. Boot self-test       — synthetic dry-run ORDER_REJECTED validation
```

Each step aborts and rolls back on failure. Shutdown is reverse order with optional position flattening.

---

## 5. Agent System

Tradov has two agent layers, inspired by TradingAgents' analyst→researcher→debate→manager pipeline.

### X-Series: On-Demand LLM Agents

These mirror TradingAgents' agent roles exactly. They are stateless utilities invoked on demand through the LangGraph pipeline.

| Agent | TradingAgents Equivalent | Role |
|-------|-------------------------|------|
| X01 MarketAnalyst | Market Analyst | Technical analysis — price action, indicators, regime |
| X02 SentimentAnalyst | Sentiment Analyst | Social media, options flow sentiment |
| X03 NewsAnalyst | News Analyst | Headline parsing, event impact |
| X05 FundamentalsAnalyst | Fundamentals Analyst | Earnings, valuation, financials |
| X06 BullResearcher | Bull Researcher | Construct bullish thesis from analyst reports |
| X10 BearResearcher | Bear Researcher | Construct bearish thesis from analyst reports |
| X15 ResearchManager | Research Manager | Judge bull/bear debate, produce investment plan |
| X17 Trader | Trader | Convert research into trade proposal (action, qty, price) |
| X18 AggressiveDebator | Aggressive Debator | Argue for aggressive positioning |
| X19 ConservativeDebator | Conservative Debator | Argue for caution |
| X20 PortfolioManager | Portfolio Manager | Final authority — approve/reject based on debate |

#### Trading Graph Pipeline (X25)

The X25 `TradovTradingGraph` wires agents into a sequential LangGraph `StateGraph`:

```
X01 MarketAnalyst → X02 SentimentAnalyst → X03 NewsAnalyst → X05 FundamentalsAnalyst
    → X06 BullResearcher + X10 BearResearcher (debate rounds)
    → X15 ResearchManager (judge, produce structured plan)
    → X17 Trader (propose action, entry, stop-loss, sizing)
    → X18 AggressiveDebator + X19 ConservativeDebator (risk debate)
    → X20 PortfolioManager (final approval with memory context)
```

Two LLM tiers:
- `quick_think` (e.g., gpt-5.4-mini) — analysts, debators
- `deep_think` (e.g., gpt-5.5) — research manager, portfolio manager

### Y-Series: Autonomous 24/7 Daemons

These are Tradov's addition — persistent background agents that run continuously:

| Agent | Role |
|-------|------|
| Y01 MarketSense | Continuously monitors market conditions |
| Y02 StrategyPilot | Autonomous strategy execution |
| Y03 RiskSentinel | 24/7 risk monitoring with circuit-breaker veto to E01 |
| Y04 AlphaLearner | Discovers and validates trading alphas |
| Y05 ExecutionOptimizer | Minimizes slippage and market impact |
| Y06 NewsSentinel | Real-time news event detection |
| Y07 TradeJournal | Automated trade logging and reflection |
| Y08 MetaOrchestrator | Coordinates all Y-agents, resolves conflicts |
| Y09 CodeReviewer | Automated code quality checks |
| Y10 AgentScheduler | Starts/stops agents, market-hours gating, crash recovery |

### X16 MetaCoordinator

The `MetaCoordinator` sits above the individual agents and resolves conflicts:

- **Weighted voting** — base weights × regime multiplier × performance multiplier
- **Risk-priority resolution** — in crisis, X04 RiskGuardian gets 1.5x weight, sentiment reduced to 0.3x
- **Critical agent veto** — X04 can veto any BUY with confidence > 0.8
- **Ray distributed computing** support for parallel agent analysis

---

## 6. Signal Layer

The signal layer computes 14 independent market signals that feed into regime detection, risk management, and strategy decisions:

| Signal | Module | What It Measures |
|--------|--------|-----------------|
| **DIX** (Dark Index) | S01 | Dark pool short-sale activity from market microstructure feeds |
| **Black Swan** | S03 | Composite tail-risk score (1-5): volatility + credit + liquidity + internals |
| **GEX/DEX/OGL** | S07 | Legacy market-context signals derived from dealer positioning and exposure analytics |
| **SKEW** | S06 | Tail-risk expectation signal used as market context |
| **Market Breadth** | S11 | $TICK, $ADD, $TRIN, $NYMO scraped from TradingView |
| **PCA-PROXY** | S14 | Sector ETF eigenfactor rotation signal |
| **PCA-IV** | S14 | SPY implied-volatility surface shape via PCA |
| **FRED Macro** | S09 | Fed rates, yield curve inversions, DXY |
| **Sentiment** | S10 | AAII bull/bear %, NAAIM exposure index |
| **WRS** (Walmart Recession) | S12 | WMT vs luxury basket — consumer down-trading |
| **PSR** (Pawn Shop Ratio) | S13 | (FCFS + EZPW) / XLF — credit cycle exhaustion |
| **Market Intel** | S15 | Social sentiment + news sentiment aggregation |
| **Market Snapshot** | S16 | LLM-generated 60-word market context paragraph |
| **Economic Calendar** | S18 | FOMC, CPI, NFP events with stand-down gates |

---

## 7. Strategy Layer

### Base Strategy (D01)

All strategies inherit from `BaseStrategy` which defines:
- `TradingSignal`, `StrategyPosition`, `PerformanceMetrics`
- Required methods: `initialize()`, `generate_signals()`, `on_position_update()`

### Strategy Catalog

Legacy options strategy modules remain in the repository for historical reference, but the active deployment is stock/ETF-only.

| Strategy | Module | Type |
|----------|--------|------|
| Long Equity | D02 | Directional equity |
| Directional Trade | D03 | Directional equity/ETF |
| Day Trade | D04 | Intraday |
| Spread Position | D05 | Legacy options spread |
| Bull Put Spread | D06 | Legacy defined-risk credit spread |
| Bear Call Spread | D07 | Legacy defined-risk credit spread |
| Opening Range Breakout | D08 | Intraday pattern |
| Greeks-Based | D09 | Legacy Greeks-driven |
| Iron Condor | D10 | Legacy neutral options spread |
| Calendar Spread | D14 | Legacy time spread |
| Ratio Spreads | D16 | Legacy ratio spread |
| Diagonal Spread | D17 | Legacy diagonal spread |
| Evolved Directional | D18 | ML-enhanced directional |
| Jade Lizard | D19 | Legacy option combination |
| Double Calendar | D21 | Legacy dual-expiration spread |
| Adaptive Volatility | D22 | Volatility-adaptive |
| Gamma Scalper | D26 | Legacy gamma hedging |
| **Pair Trading** | **D42** | **Statistical arbitrage** |

### Strategy Orchestrator (D31)

The `StrategyOrchestrator` allocates capital across active strategies using:
- **OrchestrationMode:** ADAPTIVE / CONSERVATIVE / AGGRESSIVE
- **AllocationMethod:** RISK_PARITY / EQUAL_WEIGHT / PERFORMANCE_BASED / KELLY_CRITERION
- **Regime integration:** L09 UnifiedRegimeEngine adjusts allocation weights by market regime

---

## 8. Risk Management

### 10-Gate Decision Pipeline

Every trade signal must pass through 10 sequential gates before execution:

| Gate | Component | What It Checks |
|------|-----------|---------------|
| **1. Cold-start** | E01 | Rejects all signals until first account sync |
| **2. Data staleness** | E01 + E24 | Blocks entries when market data is stale; auto-FLATTEN after 5 min |
| **3. Agent veto** | E01 + Y03 | Y03 RiskSentinel circuit breaker (normal → caution → warning → halt) |
| **4. Decision quality SLO** | E01 | Rejects if vol-surface/dealer-flow data is absent or low-confidence |
| **5. Strategy gate** | A02 | Only whitelisted strategies may trade |
| **6. Regime gate** | A02 | Hard-halt on crisis/event regimes |
| **7. Per-strategy bucket** | E01 | Caps each strategy's exposure and daily-loss share |
| **8. Cross-strategy conflict** | E01 | Detects opposing positions on the same underlying from different strategies |
| **9. Portfolio risk** | E01 | Position size, total exposure, daily loss, concentration, margin, Greek caps |
| **10. Execution gate** | A02 | Enforces LIMIT orders, enqueues to priority queue |

### Default Risk Limits

| Limit | Value |
|-------|-------|
| Max position size | 1,000 contracts |
| Max total exposure | $100,000 |
| Max daily loss | $10,000 |
| Max concentration | 30% per symbol |
| Max margin usage | 80% |
| Pair trading exposure | 20% of global (ring-fenced) |
| Pair trading daily loss | 30% of global (ring-fenced) |

---

## 9. Broker Integration

### Tradier API (B40)

Tradov uses Tradier Brokerage as its sole execution provider:

- **Auth:** Bearer token (stateless), session token refresh at 4.5 min TTL
- **Markets:** Real-time quotes for account holders and order routing
- **Orders:** Market, limit, stop, stop-limit; single-leg and multileg; OCO/OTO/OTOCO contingent
- **Streaming:** SSE for account events, WebSocket for market data
- **Preview:** Dry-run order validation before submission

### Order Manager (B02)

The OrderManager sits between strategies and the TradierClient:
- Thread-safe order state machine: PENDING → SUBMITTED → OPEN → FILLED
- SSE streaming for real-time fill notifications
- Order state persistence to disk (JSON)
- Liquidity feed with configurable thresholds

### Smart Limit Router (B41)

Routes limit orders with mid-price walking for better fill rates on spreads.

---

## 10. ML/AI Layer

### UnifiedRegimeEngine (L09)

The canonical regime detector — a 2,400-line module that consolidates:
- **ML ensemble:** Random Forest + SVC classifier
- **Signal analysis:** DIX, GEX, SWAN, SKEW from S07
- **Quantitative models:** V07 volatility models
- **Performance attribution:** F15 analysis

Output: regime label (BULL/BEAR/RANGE/VOLATILE/CRISIS/EVENT) with confidence score and stability analysis (5-min minimum duration, 2-min flip cooldown).

### Other ML Modules

| Module | Purpose |
|--------|---------|
| L01 MLPredictor | Ensemble predictions (LSTM + RandomForest + XGBoost) |
| L07 PaperTradeLearner | Paper trading ML feedback loop |
| L08 EntryOptimizer | Entry timing optimization |
| L10 FeatureEngineering | Feature pipeline |
| L13 LSTMPricer | LSTM price prediction |
| L17 FederatedLearning | Federated learning framework |
| L19 RLTrainingPipeline | Reinforcement learning |

---

## 11. Market Data Pipeline

### Data Sources

| Source | Type | Data |
|--------|------|------|
| **Tradier API** | Primary | Real-time quotes, account events, market data |
| **Yahoo Finance** | Secondary | Historical prices, VIX term structure |
| **Alpha Vantage** | Tertiary | Fundamentals, technicals, news |
| **TradingView** | Scraped | $TICK, $ADD, $TRIN, $NYMO (via Playwright) |
| **FRED** | API | Fed rates, yield curves, DXY |
| **SqueezeMetrics** | API | DIX/GEX dark pool data |

### Data Validation (C06)

Multi-layer validation with quality scoring:

| Layer | Check |
|-------|-------|
| Basic | Max price change 10%, max volume spike 10x, bid-ask spread <5%, stale data (30s) |
| Statistical | Z-score outlier detection (3.0σ), IsolationForest anomaly detection |
| Quality scoring | Composite: price (25%) + volume (20%) + spread (15%) + timestamp (15%) + statistical (15%) + consistency (10%) |

Quality levels: EXCELLENT (95-100%), GOOD (80-95%), FAIR (60-80%), POOR (40-60%), INVALID (<40%).

### Symbol Universe (U49)

Managed by `TradovU49_SymbolCatalog`:

| Group | Count | Examples |
|-------|-------|---------|
| SPY (core) | 1 | SPY |
| INDEX | 6 | SPX, VIX, VIX9D, VVIX, VXV, VXMT |
| SECTOR ETFS | 11 | XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLRE, XLU, XLV |
| PAIR EQUITIES | 50 | AAPL, MSFT, GOOGL, META, AMZN, JPM, BAC, HD, LOW, etc. |
| PAIR ETFS | 30 | XLK, XLF, XLE, VDE, KBE, KRE, XOP, IWM, etc. |

---

## 12. GUI Dashboard

### Main Dashboard (G05)

A 9,600-line PySide6 application with the following panels:

| Panel | Description |
|-------|-------------|
| **Regime Pill Bar** | 5-field display: REGIME / STRESS / STANCE / GATE / DISPATCH |
| **Chart Widget** | Plotly candlestick charts with technical indicators |
| **Signal Monitor** | 12 indicators: HMM/SKEW, GEX/DEX/OGL/DIX/SWAN, custom metrics |
| **Account Panel** | Balances, positions, buying power |
| **P&L Metrics** | Daily P&L, trade analytics, strip-level breakdown |
| **Positions Tree** | Paper trading positions with spread structure |
| **Decision Log** | Full decision flow traces from the 5-gate pipeline |
| **Agent Health** | Y-agent status, LLM response times |
| **Pair Trading** | Pair positions, spread charts, scanner results |

### Regime Pills

The five pill indicators show the system's complete execution state at a glance:

| Pill | Source | Values |
|------|--------|--------|
| **REGIME** | S07 / L09 | BULL / BEAR / RANGE / VOLATILE / CRISIS / EVENT |
| **STRESS** | S07 | LOW / MEDIUM / HIGH / CRISIS / UNKNOWN |
| **STANCE** | D31 | BULLISH / CHOPPY / CRISIS |
| **GATE** | D31 | Bull Trend / Bear Trend / Range Calm / High Vol / Crisis / Event |
| **DISPATCH** | D31 | FLOWING / IDLE / BLOCKED / ERROR / HALT |

---

## 13. Pair Trading

Tradov includes a complete statistical arbitrage pipeline spanning four module series:

### Pipeline Overview

```
D51 PairScanner  →  D52 CointegrationEngine  →  D53 OUProcessFitter  →  D54 KalmanHedgeRatio
       │                        │                         │                        │
       └────────────────────────┴─────────────────────────┴────────────────────────┘
                                            │
                                    D42 PairTradingStrategy
                                            │
                                    E26 PairRiskManager
                                            │
                                    B02 PairOrderExecutor
                                            │
                                    B03 PairPositionTracker
```

### Discovery Phase

**D51 PairScanner** — Scans 80 symbols (50 equities + 30 ETFs) for cointegrated pairs:
- Engle-Granger and Johansen tests (D52)
- Benjamini-Hochberg FDR correction (α=0.05) to control false discoveries
- Weekly scan schedule

**D52 CointegrationEngine** — Statistical tests:
- Engle-Granger two-step via `statsmodels.coint`
- Johansen trace/eigen test
- Output: hedge ratio, half-life, spread statistics, p-value

**D53 OUProcessFitter** — Mean-reversion modeling:
- Ornstein-Uhlenbeck MLE (ArbitrageLab when available, manual fallback)
- Provides half-life, entry/exit thresholds (Avellaneda-Lee model)
- Rejects pairs with half-life > 30 days

**D54 KalmanHedgeRatio** — Dynamic hedge ratios:
- Time-varying hedge ratio via pykalman Kalman filter (random-walk state model)
- Rolling OLS fallback
- Produces: hedge ratios, spread series, z-scores

### Strategy Phase

**D42 PairTradingStrategy** — Entry/exit logic:
- **Entry:** z-score ≥ 2.0 (2.5 = STRONG signal, 2.0 = MODERATE)
- **Exit:** z-score ≤ 0.5 (mean reversion target)
- **Stop:** z-score ≥ 3.5 (divergence stop)
- **Time exit:** position age > 3× half-life
- **Max positions:** 10 simultaneous pairs

Configuration via environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `TRADOV_PAIR_ENTRY_Z` | 2.0 | Z-score threshold to open |
| `TRADOV_PAIR_EXIT_Z` | 0.5 | Z-score threshold to close |
| `TRADOV_PAIR_STOP_Z` | 3.5 | Z-score stop loss |
| `TRADOV_PAIR_LOOKBACK` | 60 | Lookback window (days) |
| `TRADOV_PAIR_MAX_HALF_LIFE` | 30 | Max acceptable half-life (days) |
| `TRADOV_PAIR_SIZE_PCT` | 0.02 | Position size as % of account |
| `TRADOV_PAIR_MAX_OPEN` | 10 | Max simultaneous open pairs |

### Execution Phase

**B02 PairOrderExecutor** — Coordinated dual-leg execution:
- Places both legs simultaneously via separate single-leg orders
- If leg B fails, auto-closes leg A to prevent orphans
- 30-second timeout per pair order
- State machine: PENDING → LEG_A_SUBMITTED → BOTH_SUBMITTED → BOTH_FILLED

**B03 PairPositionTracker** — Position group management:
- Tracks pair positions as unified groups with both-leg state
- Computes aggregated P&L across all open pairs
- Net dollar exposure per symbol across all pairs
- Sector-level concentration summaries

### Risk Phase

**E26 PairRiskManager** — Pair-specific risk checks:

| Limit | Value |
|-------|-------|
| Max pair notional | $50,000 per pair |
| Max total pair notional | $200,000 |
| Max pairs per sector | 3 |
| Max open pairs | 10 |
| Beta neutrality | ±0.15 deviation |
| Cointegration stability | p-value < 0.10 |

---

## 14. Multi-Strategy Coexistence

Running pair trading alongside directional equity/ETF trading requires careful isolation to prevent the two strategies from interfering with each other. Tradov implements four layers of protection:

### Layer 1: Strategy Whitelist (A02)

Only explicitly permitted strategies can pass through the strategy gate:

```python
DEFAULT_PERMITTED_PIPELINE_STRATEGIES = (
    "long_equity",
    "directional_trade",
    "day_trade",
    "opening_range_breakout",
    "pair_trading",
)
```

### Layer 2: Capital Ring-Fencing (P04)

Each strategy gets a hard cap on capital allocation. Pair trading is capped at 20% of total capital:

```python
STRATEGY_RING_FENCES = {
    "pair_trading": 0.20,  # 20% max
}
```

The `CapitalAllocator._apply_constraints()` method enforces these caps before proportional scaling, ensuring pair trading can never consume more than its ring-fenced budget regardless of Kelly criterion calculations.

### Layer 3: Per-Strategy Risk Buckets (E01)

Each strategy type gets its own slice of the global risk limits:

```python
STRATEGY_BUCKET_DEFAULTS = {
    "pair_trading": {
        "max_exposure_fraction": 0.20,   # 20% of global $100K = $20K
        "max_daily_loss_fraction": 0.30,  # 30% of global $10K = $3K
    },
}
```

If pair trading hits its $20K exposure cap or $3K daily-loss cap, pair trades are blocked — but directional trading continues with its full budget.

### Layer 4: Cross-Strategy Conflict Detection (E01)

When a pair trade involves individual symbols (e.g., long AAPL as one leg), the risk manager decomposes the composite pair symbol into its constituent legs and checks whether another strategy already holds an opposing position:

```
Pair strategy: LONG AAPL / SHORT MSFT  →  decomposes to ["AAPL", "MSFT"]
Directional strategy: already SHORT AAPL  →  CONFLICT DETECTED
```

The conflict is logged as a warning and flagged as a `CROSS_STRATEGY_CONFLICT` violation. It does not block the trade (since opposing positions can be intentional hedges), but ensures the operator is aware.

### Isolation Summary

```
┌─────────────────────────────────────────────────────────┐
│                    Total Account                         │
│  ┌────────────────────────┐  ┌────────────────────────┐ │
│  │   Directional Trading   │  │     Pair Trading       │ │
│  │                        │  │                        │ │
│  │  Capital: up to 80%    │  │  Capital: capped 20%   │ │
│  │  Exposure: $80K        │  │  Exposure: $20K ring   │ │
│  │  Daily loss: $7K       │  │  Daily loss: $3K ring  │ │
│  │                        │  │                        │ │
│  │  Strategies: D02-D26   │  │  Strategy: D42         │ │
│  │  Instruments: equities │  │  Instruments: equities │ │
│  └────────────────────────┘  └────────────────────────┘ │
│                                                         │
│  Cross-strategy conflict detector: monitors for         │
│  opposing positions on the same underlying              │
└─────────────────────────────────────────────────────────┘
```

---

## 15. Configuration & Deployment

### Environment Variables (key settings)

| Variable | Default | Purpose |
|----------|---------|---------|
| `TRADING_MODE` | `paper` | `paper` or `live` |
| `TRADIER_API_KEY` | — | Tradier Bearer token (required) |
| `TRADIER_ENVIRONMENT` | `live` | Always live; paper uses internal ledger |
| `TRADOV_ENABLE_PAIR_TRADING` | `false` | Enable pair trading dashboard and signals |
| `TRADOV_PAIR_ENTRY_Z` | `2.0` | Pair z-score entry threshold |
| `TRADOV_PAIR_EXIT_Z` | `0.5` | Pair z-score exit threshold |
| `TRADOV_PAIR_MAX_OPEN` | `10` | Max simultaneous pair positions |
| `TRADOV_LLM_PROVIDER` | `openai` | LLM provider for X-agents |
| `TRADOV_LLM_QUICK_MODEL` | `gpt-4o-mini` | Fast LLM for analysts/debators |
| `TRADOV_LLM_DEEP_MODEL` | `gpt-4o` | Powerful LLM for managers |

### Trading Modes

| Mode | Order Execution | Market Data | Use Case |
|------|----------------|-------------|----------|
| **Paper** | Internal `PaperBroker` ledger | Live Tradier data | Strategy development, testing |
| **Live** | Tradier API (real orders) | Live Tradier data | Production trading |

### Project Structure

```
Tradov/
├── .env                    — API keys and configuration
├── .venv/                  — Python virtual environment
├── config/                 — Configuration modules
├── data/                   — Runtime data, caches, PCA history
├── logs/                   — Application logs
├── conftest.py             — Pytest configuration
├── requirements.txt        — Master requirements
├── requirements-core.txt   — Core dependencies
├── requirements-trading.txt — Trading dependencies
├── requirements-analysis.txt — Analysis dependencies
├── requirements-ai.txt     — AI/LLM dependencies
├── setup.py                — Package installation
├── pytest.ini              — Test configuration
├── ruff.toml               — Linter configuration
└── Tradov/                 — Main package (20 series)
```

---

## References

- **TradingAgents:** https://github.com/tauricresearch/tradingagents
- **Tradier API:** https://docs.tradier.com/
- **LangGraph:** https://github.com/langchain-ai/langgraph
- **PySide6:** https://doc.qt.io/qtforpython-6/
- **pykalman:** https://pykalman.github.io/
- **ArbitrageLab:** https://github.com/Auquan/auquantoolbox
