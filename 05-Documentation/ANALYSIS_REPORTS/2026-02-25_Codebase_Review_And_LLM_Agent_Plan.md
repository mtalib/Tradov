# Spyder Trading System — Codebase Review & Local LLM Agent Integration Plan

**Date:** February 25, 2026  
**Scope:** Full codebase audit, license compliance (AGPL-free), improvement opportunities, and a plan for 24/7 local LLM-powered agents  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Assessment](#2-current-architecture-assessment)
3. [Critical Bugs & Issues](#3-critical-bugs--issues)
4. [License Compliance (AGPL-Free Audit)](#4-license-compliance-agpl-free-audit)
5. [Improvement Opportunities](#5-improvement-opportunities)
6. [Local LLM Agent Strategy — The 24/7 Trading Brain](#6-local-llm-agent-strategy--the-247-trading-brain)
7. [Implementation Roadmap](#7-implementation-roadmap)
8. [Recommended LLM Models & Hardware](#8-recommended-llm-models--hardware)

---

## 1. Executive Summary

Spyder is a sophisticated algorithmic trading system with **24 modules** (A–Z), **16 specialized agents** (X01–X16), **18+ options strategies**, and a comprehensive ML stack. The system has strong bones — the risk coordination layer (E19), agent message bus (I06), and backtesting engine (F12) are well-designed. However, the system suffers from three critical gaps:

1. **The agent bus is built but unwired** — strategies don't publish to the message bus, agents don't subscribe to strategy signals, and the orchestration layers (X14, X16) aren't registered in the package.

2. **LLM integration is shallow** — Ollama is imported in 10+ agents but used inconsistently (different model names, no unified configuration, most calls are for explanation text rather than decision-making).

3. **Import-level bugs prevent agents from loading** — syntax errors, `@dataclass`-on-`Enum` conflicts, and mismatched class names mean several agents crash on import.

**The opportunity:** By fixing these foundations and deploying purpose-built local LLM agents that run 24/7, Spyder can evolve from a manually-supervised trading system to an autonomous, self-improving trading intelligence platform — all using permissively-licensed, locally-hosted models with zero AGPL exposure.

---

## 2. Current Architecture Assessment

### Module Health Summary

| Module | Files | Status | Notes |
|--------|-------|--------|-------|
| **SpyderA_Core** | 8 | ✅ Solid | Main entry, trading engine, scheduler — battle-tested |
| **SpyderB_Broker** | 11 | ✅ Solid | Tradier integration, order management working |
| **SpyderC_MarketData** | 10 | ✅ Solid | Polygon.io feeds, caching, SPY-specific handling |
| **SpyderD_Strategies** | 28 | ⚠️ Mixed | 18+ strategies implemented but not wired to agents |
| **SpyderE_Risk** | 18 | ✅ Strong | Best in class — E19 coordinator is excellent |
| **SpyderF_Analysis** | 21 | ✅ Good | Renaissance indicators, backtesting, regime detection |
| **SpyderG_GUI** | ~10 | ✅ Working | PySide6 dashboard functional |
| **SpyderH_Storage** | ~5 | ✅ Basic | Data persistence layer |
| **SpyderI_Integration** | 6 | ⚠️ Underused | Message bus exists but mostly unwired |
| **SpyderL_ML** | 14 | ⚠️ Mixed | Strong models (LSTM, RF, RL) but some broken/aspirational |
| **SpyderN_OptionsAnalytics** | 13 | ✅ Complete | Greeks, vol surface, flow tracking |
| **SpyderO_TradingIntelligence** | 3 | ✅ Basic | Scanners and optimizers |
| **SpyderP_PortfolioMgmt** | 5 | ✅ Good | Multi-strategy allocation |
| **SpyderS_Signals** | 7 | ⚠️ Under-exported | DIX/GEX/SKEW calculators — only 1 of 7 exported |
| **SpyderV_QuantModels** | 8 | ❌ Broken | `__init__.py` references nonexistent modules/variables |
| **SpyderX_Agents** | 16 | ⚠️ Critical | Good agent code but import bugs, missing registrations |
| **SpyderZ_Communication** | 7 | ✅ Good | ZeroMQ, order routing, hedging |

### Agent System Assessment

The SpyderX agent system has **16 agents** covering the full trading lifecycle:

| Agent | Purpose | LLM? | State |
|-------|---------|-------|-------|
| X01 GreeksAgent | Options Greeks analysis & risk scoring | sklearn/GPT-2 | ✅ Complete (3619 lines) |
| X02 FlowAgent | Options flow & institutional activity | Ollama | ✅ Substantial |
| X03 StrategyDirector | Strategy selection & management | Ollama | ✅ Complete |
| X04 RiskGuardian | AI-enhanced risk management | Ollama | ✅ Complete |
| X05 MLResearch | AutoML feature engineering & prediction | Ollama + sklearn | ✅ Substantial |
| X06 Backtesting | AI-enhanced backtesting & optimization | Ollama | ✅ Substantial |
| X07 ExecutionStrategy | Order execution optimization | Ollama | ✅ Complete (simulated) |
| X09 AlertManager | Intelligent alerting & prioritization | Ollama | ✅ Substantial |
| X10 QuantModels | Quant options modeling suite | Ollama | ✅ Substantial |
| X11 SentimentAnalysis | Multi-source NLP sentiment | FinBERT/RoBERTa | ✅ Substantial |
| X12 SystemHealth | System monitoring & diagnostics | Ollama | ✅ Substantial |
| X13 MarketAnalysis | Regime detection & pattern recognition | Ollama | ❌ Syntax error |
| X14 Orchestrator | Meta-learning agent coordinator | PyTorch/PPO RL | ⚠️ Import bug |
| X15 StrategyGenerator | Genetic strategy evolution | None (GA) | ⚠️ Mock fitness |
| X16 MetaCoordinator | Higher-level orchestration | None | ⚠️ Not registered |

---

## 3. Critical Bugs & Issues

### Priority 1 — Import-Breaking Bugs

| # | Location | Issue | Impact |
|---|----------|-------|--------|
| 1 | `SpyderX13_MarketAnalysisAgent.py:28` | Docstring fragment leaked into code: `from historical patterns to improve prediction accuracy.` | **X13 won't import** — breaks everything depending on it |
| 2 | `SpyderX14_OrchestratorAgent.py` | `@dataclass` decorator on `Enum` subclass (`AgentState`) | **X14 won't import** — `TypeError` at module load |
| 3 | `SpyderV_QuantModels/__init__.py` | References undefined variables (`OPTIONS_MODELS_AVAILABLE`), nonexistent modules (V09, V10), and wrong class names (`SpyderV08_MachineLearning` vs `SpyderV08_AIModels`) | **Package import raises `NameError`** |
| 4 | `SpyderL01_MLPredictor.py` | `ModelConfig`, `Prediction`, `ModelPerformance` use `field()` but lack `@dataclass` decorator | **Runtime errors** when instantiating |

### Priority 2 — Registration & Wiring Gaps

| # | Issue | Impact |
|---|-------|--------|
| 5 | X14, X15, X16 not registered in `SpyderX_Agents/__init__.py` | Orchestration agents unreachable via package API |
| 6 | Class name mismatches (X11: `EnhancedSentimentAnalysisAgent` vs registered `SpyderX11_SentimentAnalysisAgent`) | Import failures when cross-referencing |
| 7 | Strategies (D12, D22, D30) don't publish to AgentMessageBus (I06) | Agent system is disconnected from strategy signals |
| 8 | Strategy Orchestrator (D12) doesn't import any X-series agent | No AI validation of strategy decisions |
| 9 | `SpyderS_Signals/__init__.py` only exports 1 of 7 modules | Signal calculators (DIX, GEX, SKEW) inaccessible |

### Priority 3 — Dependency & Configuration Issues

| # | Issue | Impact |
|---|-------|--------|
| 10 | Undeclared deps: `gym`, `stable-baselines3`, `grpcio`, `flask`, `schedule` | Install failures on fresh environments |
| 11 | `gym` library is deprecated (replaced by `gymnasium`) | Future incompatibility |
| 12 | Ollama model inconsistency: some agents use `"llama3"`, others `"llama3.2:3b-instruct-q4_K_M"` | No unified model configuration |
| 13 | Duplicate `ModelType` enum in L01 and L18 | Import ambiguity |
| 14 | Duplicate regime detection (E12 HMM + F10 GARCH) with no ensemble | Conflicting regime signals |
| 15 | X07 ExecutionStrategy is entirely simulated — not connected to Tradier | No AI-optimized live execution |

---

## 4. License Compliance (AGPL-Free Audit)

### Result: ✅ AGPL-FREE

A comprehensive scan of all requirements files and source imports found **zero AGPL-licensed dependencies**.

### Full License Inventory

| License | Packages |
|---------|----------|
| **MIT** | ollama, lightgbm, shap, PySide6 (LGPL→MIT for Python bindings), stable-baselines3, gym, psutil, schedule, praw, tweepy, textblob, flask |
| **BSD** | numpy, pandas, scikit-learn, scipy, PyTorch, joblib, psutil |
| **Apache 2.0** | TensorFlow, XGBoost, Transformers (HuggingFace), cryptography, grpcio, aiohttp |
| **LGPL v3** | PySide6 (C++ bindings — dynamically linked, compliant) |
| **LGPL v2.1** | gensim (used in X11 SentimentAnalysis only) |

### Watch Items

1. **gensim (LGPL-2.1):** Used only in `SpyderX11_SentimentAnalysisAgent.py` for LDA topic modeling. LGPL is NOT AGPL — it's fine as long as gensim is dynamically linked (standard pip install). If concerned, gensim's LDA functionality can be replaced with `scikit-learn.decomposition.LatentDirichletAllocation` (BSD) with no functionality loss.

2. **PySide6 (LGPL v3):** Standard dynamic linking via pip is fully compliant. No static compilation or modification of Qt source required.

3. **Ollama (MIT):** The Ollama server and Python client are MIT-licensed. The **models themselves** (Llama 3, Mistral, etc.) have their own licenses — Meta's Llama 3 Community License and Apache 2.0 (Mistral) are both permissive for commercial use. Avoid models with restrictive licenses (e.g., some fine-tuned models on HuggingFace).

### Recommendation

Replace `gensim` with `sklearn.decomposition.LatentDirichletAllocation` in X11 to achieve a **100% MIT/BSD/Apache-only dependency stack** (excluding LGPL-compliant PySide6 dynamic linking).

---

## 5. Improvement Opportunities

### 5.1 Architecture Improvements

#### A. Wire the Agent Message Bus (HIGH PRIORITY)
The `SpyderI06_AgentMessageBus` is a well-engineered pub/sub system with topic routing, priority queues, circuit breakers, and exactly-once delivery. It's the nervous system of the agent architecture — but almost nothing is connected to it.

**Action items:**
- Add `message_bus.publish("signals.strategy", signal)` calls to `BaseStrategy.emit_signal()`
- Subscribe X03 (StrategyDirector) to `signals.*` for AI validation
- Subscribe X04 (RiskGuardian) to `signals.risk` for risk enrichment
- Publish regime changes from E12/F10 to `market.regime`
- Subscribe D30 (RegimeGatedSelector) to `market.regime`

#### B. Unify Regime Detection
Two independent regime detectors (E12 HMM, F10 GARCH) generate potentially conflicting signals. Create a lightweight ensemble layer:

```python
class RegimeEnsemble:
    """Combines HMM + GARCH regime signals with LLM arbitration."""
    def get_regime(self) -> RegimePrediction:
        hmm_regime = self.hmm_detector.predict()
        garch_regime = self.garch_detector.predict()
        if hmm_regime.regime == garch_regime.regime:
            return hmm_regime  # Consensus
        # LLM arbitration for disagreements
        return self.llm_resolve(hmm_regime, garch_regime, market_context)
```

#### C. Register Missing Agents
X14 (Orchestrator), X15 (StrategyGenerator), and X16 (MetaCoordinator) must be added to `SpyderX_Agents/__init__.py` with proper class name mappings.

#### D. Connect Execution Agent to Tradier
X07 (ExecutionStrategy) has a complete TWAP/VWAP/Iceberg execution framework but routes to `asyncio.sleep()` instead of the actual Tradier API. Wire it to `SpyderB40_TradierClient`.

### 5.2 Code Quality Improvements

1. **Split D12 StrategyOrchestrator** (1,931 lines) — separate GUI widgets, orchestration logic, and analytics into distinct files
2. **Fix all import bugs** (Section 3, Priority 1) before any new development
3. **Declare missing dependencies** in requirements files (`gym`→`gymnasium`, `stable-baselines3`, `grpcio`, `flask`, `schedule`)
4. **Standardize Ollama model configuration** — use a single config entry (e.g., `OLLAMA_MODEL` in `.env`) instead of hardcoded model names across 10+ agents
5. **Add `@dataclass` decorators** to L01 classes
6. **Export all S-series signals** from `SpyderS_Signals/__init__.py`

### 5.3 Trading Logic Improvements

1. **Strategy → Agent validation loop:** Before executing any trade, route the signal through X03 (strategy validation) → X04 (risk check) → X07 (execution optimization). Currently these are disconnected.

2. **Adaptive indicator parameters:** F21 Renaissance indicators use static thresholds (z-score ±2.0, IV percentile 25/75). These should adapt to regime — wider in high-vol, tighter in low-vol.

3. **Strategy fitness evaluation:** X15 StrategyGenerator uses mock random fitness. Connect it to F12 AdvancedBacktestingEngine for real fitness scoring.

4. **Federated learning rationalization:** L17 (1,605 lines) implements federated learning for a single-user system. Either remove it or repurpose it as a multi-strategy knowledge-sharing layer where each strategy "node" shares learned parameters.

---

## 6. Local LLM Agent Strategy — The 24/7 Trading Brain

### Vision

Deploy a constellation of specialized local LLM-powered agents that operate autonomously 24/7, each responsible for a specific domain of trading intelligence. These agents communicate via the existing AgentMessageBus, learn continuously from market data and trade outcomes, and collectively form an adaptive trading brain that improves over time.

**Key principle:** Each agent has a **quantitative foundation** (math/ML) with an **LLM overlay** (reasoning/explanation/adaptation). The LLM never makes raw trading decisions — it interprets, validates, and adapts the quantitative outputs.

### 6.1 Agent Architecture (Local LLM-Powered)

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT MESSAGE BUS (I06)                       │
│  Topics: market.* | signals.* | risk.* | execution.* | meta.*   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ MARKET LAYER │  │STRATEGY LAYER│  │   EXECUTION LAYER    │   │
│  │              │  │              │  │                      │   │
│  │ MarketSense  │  │ StrategyPilot│  │ ExecutionOptimizer   │   │
│  │ Agent        │──│ Agent        │──│ Agent                │   │
│  │ (24/7)       │  │ (market hrs) │  │ (market hrs)         │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│          │                 │                    │                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  RISK LAYER  │  │ LEARNING     │  │   META LAYER         │   │
│  │              │  │ LAYER        │  │                      │   │
│  │ RiskSentinel │  │ AlphaLearner │  │ MetaOrchestrator     │   │
│  │ Agent        │  │ Agent        │  │ Agent                │   │
│  │ (24/7)       │  │ (24/7)       │  │ (24/7)               │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│          │                 │                    │                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  NEWS LAYER  │  │ JOURNAL LAYER│  │  SELF-IMPROVEMENT    │   │
│  │              │  │              │  │  LAYER               │   │
│  │ NewsSentinel │  │ TradeJournal │  │ CodeReviewer         │   │
│  │ Agent        │  │ Agent        │  │ Agent                │   │
│  │ (24/7)       │  │ (post-market)│  │ (off-hours)          │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│               ┌─────────────────────────┐                       │
│               │   LOCAL LLM ENGINE      │                       │
│               │   Ollama + llama3.1:8b   │                       │
│               │   (or Mistral 7B)       │                       │
│               └─────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 The Nine Specialist Agents

---

#### Agent 1: MarketSense Agent (24/7)
**Enhances:** X13 MarketAnalysis  
**Schedule:** Runs continuously — pre-market, during market, post-market, overnight  
**Purpose:** Maintain a living mental model of the market

**What it does:**
- **Pre-market (4:00–9:30 AM ET):** Analyzes overnight futures, European market closes, Asian session results, pre-market volume patterns, gap analysis
- **Market hours (9:30 AM–4:00 PM ET):** Real-time regime monitoring, unusual volume detection, sector rotation tracking, intraday pattern recognition
- **Post-market (4:00–8:00 PM ET):** End-of-day summary, key level calculations for next day, after-hours earnings reaction analysis
- **Overnight:** Macro event monitoring (central bank decisions, geopolitical events), correlation analysis, historical pattern matching for next-day scenarios

**LLM role:** Synthesizes quantitative signals (HMM regime, GARCH vol, VIX term structure, GEX/DEX levels) into a coherent market narrative. Example output:
> "Market is transitioning from Chop to Bull regime (HMM 72% confidence). VIX term structure in contango supports premium selling. However, GEX flip point at 585 suggests dealer hedging could amplify moves above that level. Recommend: favor credit spread strategies but keep position sizes at 75% normal until regime confirmation exceeds 85%."

**Publishes to:** `market.regime`, `market.analysis`, `market.levels`

---

#### Agent 2: StrategyPilot Agent (Market Hours)
**Enhances:** X03 StrategyDirector + D12 StrategyOrchestrator  
**Schedule:** Active during market hours, reviews during post-market  
**Purpose:** AI copilot for strategy selection and signal validation

**What it does:**
- Subscribes to all strategy signals via `signals.*` topic
- For each signal, queries the LLM with full context (regime, portfolio state, recent performance, Greeks exposure)
- Provides confidence-adjusted recommendations: STRONG_BUY → HOLD → AVOID spectrum
- Manages strategy portfolio allocation dynamically based on regime
- Detects strategy conflicts (e.g., iron condor signal + straddle signal simultaneously)
- Learns from recent trade outcomes to adjust strategy preferences

**LLM role:** Acts as a "second opinion" before trade execution. Doesn't override quantitative signals but enriches them with contextual reasoning:
> "Iron Condor signal at 82% confidence. However, earnings for NVDA tomorrow could cause SPY correlation spike. Recommending: delay entry until post-earnings, or reduce size to 50% and widen wings by 5 strikes."

**Publishes to:** `signals.validated`, `strategy.allocation`

---

#### Agent 3: RiskSentinel Agent (24/7)
**Enhances:** X04 RiskGuardian + E19 UnifiedRiskCoordinator  
**Schedule:** Continuous — risk never sleeps  
**Purpose:** Always-on risk monitoring with predictive threat detection

**What it does:**
- **Real-time:** Portfolio Greeks monitoring, margin utilization tracking, correlation shifts, tail risk estimation
- **Predictive:** Uses overnight futures and VIX futures to predict opening risk exposure
- **Scenario planning:** Runs Monte Carlo stress tests every 30 minutes during market hours
- **Circuit breaker:** Autonomous authority to halt trading if risk thresholds are breached
- **Position-level monitoring:** Tracks each position's P&L trajectory, time decay curve, and distance from adjustment triggers

**LLM role:** Translates raw risk metrics into actionable intelligence:
> "ALERT: Portfolio delta has drifted to -45 (target: neutral ±15). Two short put positions (Mar 28 575P, Mar 28 570P) are both accelerating toward adjustment triggers. Combined: these represent 62% of total portfolio risk. Recommended action: Roll the 575P down to 565P to reduce delta by 12, or add a long call spread to neutralize."

**Publishes to:** `risk.assessment`, `risk.alerts`, `risk.circuit_breaker`

---

#### Agent 4: AlphaLearner Agent (24/7)
**Enhances:** X05 MLResearch + L18 EnhancedMLIntegration  
**Schedule:** Runs continuously — ML training is compute-intensive and benefits from off-hours cycles  
**Purpose:** Continuous model improvement and alpha discovery

**What it does:**
- **Feature engineering:** Discovers new predictive features from market microstructure data (order flow imbalance, options skew momentum, GEX acceleration)
- **Model training:** Walk-forward cross-validation with regime-aware sample weighting
- **Alpha research:** Tests hypotheses automatically: "Does VIX term structure slope predict next-day SPY direction?"
- **Model validation:** Tracks live prediction accuracy, detects model drift, triggers retraining
- **Strategy evolution:** Interfaces with X15 StrategyGenerator but uses real backtested fitness instead of mock scores

**LLM role:** Generates research hypotheses and interprets model results:
> "Research finding: Random Forest feature importance shows 'options_skew_5min_change' has risen from rank #15 to rank #3 over the last month. This corresponds with the increase in 0DTE trading volume. Hypothesis: dealer hedging flows from 0DTE options are creating short-term predictive signals via gamma exposure mechanics. Recommend: add 0DTE GEX features to the entry timing model."

**Publishes to:** `meta.research`, `signals.ml_prediction`, `meta.model_performance`

---

#### Agent 5: ExecutionOptimizer Agent (Market Hours)
**Enhances:** X07 ExecutionStrategy → connected to B40 TradierClient  
**Schedule:** Active during market hours  
**Purpose:** Minimize execution costs through intelligent order management

**What it does:**
- Receives validated trade signals from StrategyPilot
- Analyzes current bid/ask spreads, volume, and market impact estimates
- Selects optimal execution algorithm (TWAP, VWAP, Iceberg, Sniper)
- Times entries to optimal intraday windows (e.g., avoiding first 15 minutes, targeting power hour)
- Monitors fill quality and slippage in real-time
- Learns from historical execution data to improve timing

**LLM role:** Provides execution reasoning:
> "Executing iron condor via 4-leg simultaneous order. Current SPY spread is $0.01 (tight). Market depth shows 5,000+ contracts at best bid/ask. Recommendation: submit as limit order at mid-price, expect fill within 30 seconds. If not filled in 60 seconds, walk price by $0.01."

**Publishes to:** `execution.plan`, `execution.filled`, `execution.stats`

---

#### Agent 6: NewsSentinel Agent (24/7)
**Enhances:** X11 SentimentAnalysis + C09 NewsManager  
**Schedule:** Continuous  
**Purpose:** Natural language processing of market-moving events

**What it does:**
- Monitors RSS feeds, financial news APIs, and social media for SPY-relevant events
- Classifies news as: irrelevant, noise, notable, significant, critical
- Detects earnings surprises for SPY constituents with > 1% index weight
- Tracks Fed communication for policy signal changes
- Identifies unusual sentiment shifts that precede market moves
- Generates trading-relevant summaries (not raw news)

**LLM role:** This is the agent that benefits most from LLM capabilities:
> "FED COMMUNICATION: Powell's testimony used 'patient' 3 times (up from 1 in January). Historical pattern: when 'patient' frequency increases, VIX drops 8% over next 5 sessions. This supports premium-selling strategies. However, CPI data tomorrow could override — recommend waiting until 8:30 AM release."

**Technology:** Use FinBERT (already in X11) for sentiment scoring, augmented by a local LLM for contextual interpretation. Replace gensim (LGPL) with sklearn's LatentDirichletAllocation (BSD) for topic modeling.

**Publishes to:** `market.news`, `market.sentiment`, `signals.news_driven`

---

#### Agent 7: TradeJournal Agent (Post-Market)
**NEW agent — does not exist in current codebase**  
**Schedule:** Post-market (4:30–6:00 PM ET) and weekends  
**Purpose:** Automated trade review and performance attribution

**What it does:**
- Reviews every trade closed today: entry signal source, execution quality, P&L, holding period
- Attributes P&L to factors: was the win from correct direction, or from theta decay despite wrong direction?
- Identifies patterns: "3 of last 5 losing trades were opened on Monday mornings — investigate overnight gap risk"
- Compares actual performance to backtest expectations
- Generates weekly/monthly performance reports with LLM narrative
- Detects behavioral biases: revenge trading, overtrading after wins, premature exits

**LLM role:** Creates an AI trading journal:
> "**Daily Review — Feb 25, 2026**
> - 3 trades closed: +$420 (Iron Condor), -$180 (Credit Spread), +$95 (Calendar Spread)
> - Net: +$335 | Win rate: 67% | Average holding: 3.2 days
> - Attribution: $290 from theta decay, $120 from delta (directional), -$75 from vega (vol contraction hurt the calendar)
> - Pattern alert: Credit spread loss was due to entry during first 15 minutes — high slippage. Recommend: enforce 15-minute opening wait rule.
> - Strategy comparison: Iron Condors are outperforming by 2.3x this month vs. 3-month average. Regime analysis confirms: low-vol chop market favors IC strategies."

**Publishes to:** `meta.journal`, `meta.performance`, `meta.behavioral_alert`

---

#### Agent 8: MetaOrchestrator Agent (24/7)
**Enhances:** X14 Orchestrator + X16 MetaCoordinator (unified into one clean implementation)  
**Schedule:** Continuous  
**Purpose:** Master coordinator that manages all other agents

**What it does:**
- Monitors health and output quality of all agents
- Dynamically adjusts agent weights based on recent accuracy
- Resolves conflicts between agents (e.g., MarketSense says "bullish" but RiskSentinel says "too exposed")
- Manages agent scheduling: which agents are active, sleeping, or in maintenance mode
- Implements "wisdom of crowds" — weighs agent consensus for key decisions
- Detects when an agent is degrading (e.g., ML model drift in AlphaLearner)

**LLM role:** High-level synthesis and conflict resolution:
> "Conflict detected: StrategyPilot recommends new iron condor entry, but RiskSentinel reports portfolio is at 85% margin utilization. Resolution: block new entry (RiskSentinel has veto on margin > 80%). MarketSense confirms regime still supports IC strategy — queue entry for execution after Mar 28 positions expire (3 days)."

**Publishes to:** `meta.orchestration`, `meta.health`, `meta.decisions`

---

#### Agent 9: CodeReviewer Agent (Off-Hours — NEW CONCEPT)
**NEW agent — most innovative addition**  
**Schedule:** Overnight and weekends  
**Purpose:** Self-improving codebase through automated analysis

**What it does:**
- Analyzes strategy performance data and identifies code-level improvements
- Reviews backtesting results and suggests parameter adjustments
- Generates test cases for edge scenarios that caused unexpected losses
- Proposes new strategy variations based on learned patterns
- Validates risk model calibration against realized outcomes
- Creates implementation tickets for the human developer

**LLM role:** Uses code-capable LLM (e.g., Qwen2.5-Coder-7B or DeepSeek-Coder-V2-Lite) for code analysis:
> "**Overnight Analysis — Feb 25, 2026**
> 1. SpyderD03_CreditSpread: stop_loss_pct=30% triggered 3 times this week. Backtesting 25% shows better risk-adjusted returns. Suggest parameter change.
> 2. SpyderE01_RiskManager: MAX_MARGIN_UTILIZATION=80% is consistent with performance data. No change recommended.
> 3. New test case needed: D04_ZeroDTE handling of VIX > 30 with < 2 hours to expiry. Last week's loss ($430) occurred in this scenario with no specific test coverage.
> 4. Strategy idea: D22_AdaptiveVolatility currently ignores VIX futures term structure. Adding term structure slope as a feature could improve regime change detection by ~15% (based on historical data analysis)."

**Publishes to:** `meta.code_review`, `meta.improvements`

**Safety:** This agent NEVER modifies code directly. It generates recommendations and creates documentation that a human developer (you) reviews and implements.

---

### 6.3 Unified LLM Configuration

Replace the scattered model name hardcoding with a single configuration:

```python
# config/config.py or .env
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_PRIMARY_MODEL = "llama3.1:8b-instruct-q5_K_M"     # General reasoning
OLLAMA_FAST_MODEL = "llama3.2:3b-instruct-q4_K_M"          # Quick responses
OLLAMA_CODE_MODEL = "qwen2.5-coder:7b-instruct-q5_K_M"     # Code analysis
OLLAMA_FINANCE_MODEL = "mistral:7b-instruct-v0.3-q5_K_M"   # Financial reasoning
OLLAMA_TIMEOUT = 30                                          # seconds
OLLAMA_MAX_RETRIES = 3
OLLAMA_TEMPERATURE_DEFAULT = 0.3
OLLAMA_TEMPERATURE_CREATIVE = 0.7
```

### 6.4 Agent Communication Protocol

All agents communicate via the existing `AgentMessageBus` (I06) with standardized message format:

```python
@dataclass
class AgentMessage:
    agent_id: str               # "MarketSense", "RiskSentinel", etc.
    message_type: str           # "analysis", "signal", "alert", "decision"
    topic: str                  # Bus topic for routing
    priority: MessagePriority   # CRITICAL, HIGH, NORMAL, LOW, BULK
    payload: dict              # Agent-specific data
    confidence: float          # 0.0 - 1.0
    reasoning: str             # LLM-generated explanation
    timestamp: datetime
    ttl_seconds: int           # Time-to-live
    requires_ack: bool         # Whether recipient must acknowledge
    correlation_id: str        # For request-reply patterns
```

### 6.5 Agent Scheduling System

```
SCHEDULE OVERVIEW (all times ET):

┌─ OVERNIGHT (8pm - 4am) ──────────────────────────────────────┐
│ Active: MarketSense, RiskSentinel, AlphaLearner, NewsSentinel│
│         CodeReviewer, MetaOrchestrator                        │
│ Tasks:  ML training, research, code analysis, overnight      │
│         futures monitoring, macro event watch                 │
└──────────────────────────────────────────────────────────────┘

┌─ PRE-MARKET (4am - 9:30am) ─────────────────────────────────┐
│ Active: ALL agents wake up by 8:30am                         │
│ Tasks:  Gap analysis, overnight summary, strategy prep,      │
│         risk preview, news digest, execution readiness        │
└──────────────────────────────────────────────────────────────┘

┌─ MARKET HOURS (9:30am - 4pm) ───────────────────────────────┐
│ Active: ALL agents at full capacity                          │
│ Tasks:  Real-time monitoring, signal validation, execution,  │
│         risk management, news processing, trade management   │
└──────────────────────────────────────────────────────────────┘

┌─ POST-MARKET (4pm - 8pm) ───────────────────────────────────┐
│ Active: TradeJournal, MarketSense, RiskSentinel, AlphaLearner│
│         MetaOrchestrator, NewsSentinel                        │
│ Tasks:  Trade review, journal generation, EOD analysis,      │
│         performance attribution, model retraining prep        │
└──────────────────────────────────────────────────────────────┘
```

---

## 7. Implementation Roadmap

### Phase 1: Fix Foundations (Week 1-2)
**Goal:** Get the existing system working correctly

| Task | Effort | Priority |
|------|--------|----------|
| Fix X13 syntax error (docstring fragment) | 10 min | P0 |
| Fix X14 `@dataclass` on `Enum` bug | 10 min | P0 |
| Fix L01 missing `@dataclass` decorators | 10 min | P0 |
| Fix V_QuantModels `__init__.py` | 1 hour | P0 |
| Register X14, X15, X16 in `SpyderX_Agents/__init__.py` | 30 min | P1 |
| Fix class name mismatches (X11, X15, X16) | 30 min | P1 |
| Declare missing dependencies in requirements | 30 min | P1 |
| Replace `gym` with `gymnasium` | 2 hours | P1 |
| Standardize Ollama model config in `.env` | 1 hour | P1 |
| Export all S-series signals in `__init__.py` | 15 min | P2 |

### Phase 2: Wire the Nervous System (Week 3-4)
**Goal:** Connect strategies ↔ agents ↔ risk via the message bus

| Task | Effort | Priority |
|------|--------|----------|
| Add message bus publishing to `BaseStrategy.emit_signal()` | 2 hours | P0 |
| Subscribe X03 StrategyDirector to `signals.*` | 3 hours | P0 |
| Subscribe X04 RiskGuardian to `risk.*` | 3 hours | P0 |
| Connect D12 Orchestrator to agent outputs | 4 hours | P1 |
| Create RegimeEnsemble (E12 + F10 → LLM arbitration) | 6 hours | P1 |
| Connect X07 ExecutionStrategy to B40 TradierClient | 8 hours | P1 |
| Unify X14/X16 into single MetaOrchestrator | 8 hours | P2 |

### Phase 3: Deploy Core LLM Agents (Week 5-8)
**Goal:** Launch the first wave of local LLM-powered agents

| Task | Effort | Priority |
|------|--------|----------|
| Implement unified LLM config system | 4 hours | P0 |
| Build MarketSense Agent (enhance X13) | 16 hours | P0 |
| Build RiskSentinel Agent (enhance X04 + E19) | 16 hours | P0 |
| Build StrategyPilot Agent (enhance X03 + D12) | 16 hours | P1 |
| Build NewsSentinel Agent (enhance X11 + C09) | 12 hours | P1 |
| Replace gensim with sklearn LDA in X11 | 2 hours | P1 |
| Agent scheduling system implementation | 8 hours | P1 |

### Phase 4: Advanced Agents (Week 9-12)
**Goal:** Deploy learning and self-improvement agents

| Task | Effort | Priority |
|------|--------|----------|
| Build ExecutionOptimizer (connect X07 → B40) | 16 hours | P1 |
| Build AlphaLearner Agent (enhance X05 + L18) | 20 hours | P1 |
| Build TradeJournal Agent (new) | 16 hours | P2 |
| Build MetaOrchestrator Agent (unified X14/X16) | 16 hours | P2 |
| Build CodeReviewer Agent (new) | 20 hours | P3 |
| Connect X15 StrategyGenerator to F12 backtester | 8 hours | P3 |

### Phase 5: Continuous Learning Loop (Week 13+)
**Goal:** Close the feedback loop for self-improvement

| Task | Effort | Priority |
|------|--------|----------|
| Implement trade outcome → agent weight adjustment | 12 hours | P1 |
| Build agent performance dashboard (GUI) | 16 hours | P2 |
| Implement agent-level A/B testing framework | 12 hours | P2 |
| Historical backtest of agent ensemble vs. non-agent | 8 hours | P2 |
| Document operational runbook | 8 hours | P3 |

---

## 8. Recommended LLM Models & Hardware

### Model Selection (ALL AGPL-free)

| Role | Model | License | Size | Quant | RAM | Use Case |
|------|-------|---------|------|-------|-----|----------|
| **Primary Reasoning** | Llama 3.1 8B Instruct | Meta Community (permissive) | 8B | Q5_K_M | 6 GB | Market analysis, risk reasoning, strategy validation |
| **Fast Responses** | Llama 3.2 3B Instruct | Meta Community (permissive) | 3B | Q4_K_M | 2.5 GB | Quick explanations, alert summaries |
| **Code Analysis** | Qwen 2.5 Coder 7B | Apache 2.0 | 7B | Q5_K_M | 5.5 GB | Code review, test generation, parameter analysis |
| **Financial Reasoning** | Mistral 7B Instruct v0.3 | Apache 2.0 | 7B | Q5_K_M | 5.5 GB | Financial report analysis, Fed communication parsing |
| **Sentiment** | FinBERT (already in X11) | Apache 2.0 | 110M | Full | 0.5 GB | Sentiment classification (keep current implementation) |

**Alternative fully Apache-2.0 stack (if Meta Community License is a concern):**

| Role | Model | License | Size |
|------|-------|---------|------|
| Primary | Mistral 7B Instruct v0.3 | Apache 2.0 | 7B |
| Fast | Phi-3.5 Mini Instruct | MIT | 3.8B |
| Code | Qwen 2.5 Coder 7B | Apache 2.0 | 7B |

### Hardware Requirements

**Minimum (run 1-2 agents simultaneously):**
- 16 GB RAM
- NVIDIA GPU with 8 GB VRAM (RTX 3060/4060) or Apple M2/M3 with 16 GB unified
- 50 GB SSD for models

**Recommended (run all agents 24/7):**
- 32 GB RAM
- NVIDIA GPU with 12+ GB VRAM (RTX 3060 12GB / RTX 4070) or Apple M3 Pro with 36 GB unified
- 100 GB SSD for models + data
- UPS for 24/7 operation

**Optimal (full constellation with concurrent inference):**
- 64 GB RAM
- NVIDIA GPU with 24 GB VRAM (RTX 4090) or dual GPU setup
- 200 GB NVMe SSD
- UPS + network redundancy

### Ollama Setup

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull recommended models
ollama pull llama3.1:8b-instruct-q5_K_M
ollama pull llama3.2:3b-instruct-q4_K_M
ollama pull qwen2.5-coder:7b-instruct-q5_K_M
ollama pull mistral:7b-instruct-v0.3-q5_K_M

# Verify
ollama list
```

### Cost Comparison

| Approach | Monthly Cost | Latency | Privacy | AGPL Risk |
|----------|-------------|---------|---------|-----------|
| **Local Ollama (recommended)** | $0 (electricity only) | 50-500ms | ✅ Full | ✅ None |
| OpenAI GPT-4 API | $200-2000+ | 500-2000ms | ❌ Data sent externally | ✅ None |
| Anthropic Claude API | $150-1500+ | 500-2000ms | ❌ Data sent externally | ✅ None |
| AWS Bedrock | $100-1000+ | 200-1000ms | ⚠️ AWS hosted | ✅ None |

**Recommendation:** Local Ollama provides zero ongoing cost, zero latency penalty for most use cases (50-500ms is faster than API calls), complete data privacy (trading strategies never leave your machine), and zero licensing risk. The quality tradeoff vs GPT-4 is acceptable because the agents use LLMs for reasoning/explanation overlaid on quantitative foundations — the math does the heavy lifting.

---

## Appendix A: Key Files to Modify

| File | Changes Needed |
|------|---------------|
| `Spyder/SpyderX_Agents/__init__.py` | Register X14, X15, X16; fix class name mappings |
| `Spyder/SpyderX_Agents/SpyderX13_MarketAnalysisAgent.py:28` | Remove leaked docstring fragment |
| `Spyder/SpyderX_Agents/SpyderX14_OrchestratorAgent.py` | Remove `@dataclass` from `AgentState(Enum)` |
| `Spyder/SpyderL_ML/SpyderL01_MLPredictor.py` | Add `@dataclass` to `ModelConfig`, `Prediction`, `ModelPerformance` |
| `Spyder/SpyderV_QuantModels/__init__.py` | Rewrite to match actual module files |
| `Spyder/SpyderD_Strategies/SpyderD01_BaseStrategy.py` | Add message bus publishing in `emit_signal()` |
| `Spyder/SpyderS_Signals/__init__.py` | Export S01-S06 modules |
| `config/config.py` or `.env` | Add unified Ollama configuration block |
| `requirements.txt` | Add `gymnasium`, `stable-baselines3`, `schedule` |
| `Spyder/SpyderX_Agents/SpyderX11_SentimentAnalysisAgent.py` | Replace `gensim` with `sklearn.decomposition.LatentDirichletAllocation` |

## Appendix B: AGPL-Free Guarantee

This report has verified that:
1. **Zero AGPL dependencies** exist in any requirements file
2. **Zero AGPL imports** exist in any source file
3. All recommended LLM models use **Meta Community, Apache 2.0, or MIT** licenses
4. **Ollama** server and client are **MIT** licensed
5. The one LGPL dependency (**gensim**) can be replaced with BSD-licensed sklearn equivalent
6. **PySide6** (LGPL v3) is used via standard dynamic linking, which is LGPL-compliant

The system can operate with a **100% MIT/BSD/Apache-only** dependency stack after replacing gensim with sklearn LDA.
