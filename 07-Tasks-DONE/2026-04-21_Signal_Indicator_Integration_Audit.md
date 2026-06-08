# Tradov Signal & Indicator Integration Audit
**Date:** 2026-04-21  
**Branch:** fix/audit-v14-all  
**Scope:** Are all displayed and hidden indicators wired to trade decisions? Are QuantModels, Agents, and AutoAgents actively used?

---

## EXECUTIVE SUMMARY

Out of ~30 indicators displayed in the Market Overview panel, **only 6 are fully wired** to actual trade go/no-go decisions. The majority are collected, displayed, and calculated — but never consulted before an order is placed.

TradovV (QuantModels), TradovX (Agents), and TradovY (AutoAgents) are **architecturally present but not in the live trade decision hot-path.** They run in parallel but their outputs are not consumed by the D-series strategies or E-series risk managers.

**Severity: HIGH** — the system is trading with a fraction of the intelligence it has available.

---

## PART 1: MARKET OVERVIEW INDICATOR AUDIT

Legend: ✅ Wired | ⚠️ Calculated but not wired | ❌ Not calculated / stub | 🔒 Feature-flagged (off by default)

### 1.1 S&P Core
| Symbol | Status | Notes |
|--------|--------|-------|
| SPY | ✅ Wired | Primary instrument — all strategies |
| SPX | ✅ Wired | Used for options chain indexing |

### 1.2 Volatility
| Symbol | Status | Notes |
|--------|--------|-------|
| VIX | ✅ Wired | D31 regime classification (VIX+trend only); D28 VIXHedging; R11 entry gate (VIX cap) |
| VIX9D | ⚠️ Not wired | Displayed in GUI (C10 VIXAnalyzer) — never read by D/E/F series |
| VXV | ⚠️ Not wired | Displayed — VIX term structure signal ignored by strategies |
| VVIX | ⚠️ Not wired | Displayed — vol-of-vol not used in any position sizing or entry filter |

**Gap:** VIX9D/VXV term structure is a critical premium-selling signal. When VIX9D > VXV (backwardation), premium-selling is risky. This is never checked.

### 1.3 Market Internals
| Symbol | Status | Notes |
|--------|--------|-------|
| $TICK | ⚠️ Not wired | S11 collects it; S08 references it — but no D/E filter uses TICK as gate |
| $TRIN | ⚠️ Not wired | Same as TICK — collected, not consumed |
| $ADD (breadth) | ⚠️ Not wired | F10 has `advance_decline_ratio` field but C04 data never flows into F10 in production |
| NYMO | ⚠️ Not wired | Calculated in S07 (line 907) — emitted to GUI only |
| CPC (Put/Call) | ⚠️ Not wired | S08 has `update_put_call_ratio()` — never called from the entry pipeline |
| SKEW (CBOE) | ⚠️ Not wired | S06 calculates CBOE SKEW; F09 has a SKEW filter type but checks IV skew (not CBOE SKEW) |
| $VOLD (NYSE volume delta) | ⚠️ Not wired | Displayed — not used |
| XLK (Tech ETF) | ⚠️ Not wired | Sector correlation — not fed to any strategy |
| XLF (Financials ETF) | ⚠️ Not wired | Sector correlation — not fed to any strategy |
| TNX (10yr yield) | ⚠️ Not wired | Displayed — interest rate context ignored |
| RVOL (relative volume) | ⚠️ Not wired | Displayed — F09 has a volume filter but uses `volume_ratio` passed in externally |

**Gap:** Market internals ($TICK, $TRIN, NYMO, SKEW, CPC) are the strongest short-term breadth signals available. All of them are being computed but ignored.

### 1.4 Major Indices
| Symbol | Status | Notes |
|--------|--------|-------|
| QQQ | ⚠️ Not wired | Correlation/leadership signal — not used |
| IWM | ⚠️ Not wired | Risk-on/risk-off proxy — not used |

### 1.5 Bonds & Credit
| Symbol | Status | Notes |
|--------|--------|-------|
| TLT | ⚠️ Not wired | Flight-to-safety signal — not used |
| HYG | ⚠️ Not wired | Credit stress indicator — not used |
| LQD | ⚠️ Not wired | Investment grade credit — not used |

### 1.6 Correlations
| Symbol | Status | Notes |
|--------|--------|-------|
| DXY | ⚠️ Not wired | Dollar strength — not used |
| GLD | ⚠️ Not wired | Risk-off/inflation — not used |
| USO | ⚠️ Not wired | Oil/macro signal — not used |

### 1.7 Options Analytics
| Symbol | Status | Notes |
|--------|--------|-------|
| IVR (IV Rank) | ✅ Wired | D04 MIN_IVR=30 gate; D14, D15, D21 all condition on iv_rank |
| ATM_IV | ✅ Wired | D15 StraddleStrangle computes and uses ATM IV |
| VRP (Vol Risk Premium) | ✅ Wired | D22 AdaptiveVolatility uses VRP to select vol-selling vs buying |

### 1.8 Custom Metrics
| Symbol | Status | Notes |
|--------|--------|-------|
| GEX | 🔒 Feature-flagged | R08 uses it behind `TRADOV_REGIME_STRUCTURE=1` env var (off by default); L09 UnifiedRegimeEngine uses it for regime |
| DEX (Delta Exposure) | ⚠️ Not wired | Y01 MarketSenseAgent reads it for reporting — not in trade gate |
| OGL (options gamma line) | ⚠️ Not wired | Displayed — not used in decisions |
| DIX | 🔒 Feature-flagged | R08 uses it behind `TRADOV_REGIME_STRUCTURE=1` (off by default) |
| WRS (Weighted Regime Score) | ⚠️ Not wired | S12 calculates it — only displayed in S07 metrics output |
| PSR (Probabilistic Sharpe) | ⚠️ Not wired | E07 calculates it — used as a REPORTING metric, not a trade gate |
| SWAN (tail-risk index) | ✅ Wired | R08 blocks entries when SWAN ≥ 2.0 — this IS enforced |
| PMR (Pivot Mean Reversion) | ✅ Wired | D34 is a full PMR strategy; S08 generates PMR signals for it |

---

## PART 2: REGIME DETECTION — FRAGMENTED AND SHALLOW

The system has **four separate regime detectors** that don't talk to each other:

| Component | What it uses | Who consumes it |
|-----------|-------------|-----------------|
| D31 `_classify_market_regime()` | VIX + trend_strength only | D31 strategy weights |
| F10 `MarketRegimeDetector` | VIX + advance_decline_ratio | Y01 MarketSenseAgent (advisory), E15 GreekLimitsManager |
| L09 `UnifiedRegimeEngine` | VIX + GEX + SWAN + ML models + S07 | D30 RegimeGatedSelector (only) |
| M06 `HMMRegimeDetector` | Statistical HMM | Monitoring — not used by D-series |

**Critical finding:** D31 StrategyOrchestrator — the primary strategy router — uses the SIMPLEST regime detector (VIX + trend). It does NOT use L09 UnifiedRegimeEngine which has GEX, DIX, SWAN, ML, and HMM.

---

## PART 3: TRADOVV (QUANTMODELS) AUDIT

### Status: **NOT INTEGRATED into live trading hot-path**

| Module | Lines | Is it called in D/E/A/R path? |
|--------|-------|-------------------------------|
| V01 QuantEngine | 945 | ❌ No — no imports in A/D/E/R |
| V02 ModelManager | 1,056 | ❌ No |
| V03 DataInterface | 677 | ❌ No |
| V04 RiskManager | 1,356 | ❌ No — E19 mentions it but doesn't instantiate it |
| V05 PricingEngine | 1,560 | ❌ No — N-series has its own BSM |
| V06 VolatilityEngine | 1,698 | ❌ No — N02 has its own IV engine |
| V07 AdvancedModels | 1,320 | ❌ No |
| V08 AIModels | 1,215 | ❌ No |

**E19 UnifiedRiskCoordinator** claims to coordinate V04+X04 but:
- V04 is mentioned in docstring — not imported or called
- X04 has a `# placeholder` comment with a log warning: `"AI risk placeholder in use — X04 model not wired"`

**F06 GreeksCalculator** references `TradovV09_IVEngine` as the "canonical BSM engine" in a docstring comment only — no actual import.

**Conclusion:** TradovV is a self-contained quant library that runs in isolation. Its output never flows into trade decisions, position sizing, or risk validation.

---

## PART 4: TRADOVX (AGENTS) AUDIT

### Status: **Registered but outputs not consumed by trade engine**

| Agent | Registered in A06? | Output consumed by D/E? |
|-------|--------------------|-----------------------|
| X01 GreeksAgent | ✅ Yes | ❌ No — advisory via message bus only |
| X02 FlowAgent | ✅ Yes | ❌ No |
| X03 StrategyDirectorAgent | ✅ Yes | ❌ No — D31 does NOT subscribe to its output |
| X04 RiskGuardianAgent | ✅ Yes | ❌ Placeholder — E19 has `# AI risk placeholder in use — X04 model not wired` |
| X05 MLResearchAgent | ❌ Not in A06 | ❌ No |
| X06 BacktestingAgent | ❌ Not in A06 | ❌ No |
| X07 ExecutionStrategyAgent | ❌ Not in A06 | ❌ No |
| X09 AlertManagerAgent | ❌ Not in A06 | ❌ No |
| X10 QuantModelsAgent | ❌ Not in A06 | ❌ No |
| X11 SentimentAnalysisAgent | ❌ Not in A06 | ❌ No |
| X12 SystemHealthAgent | ❌ Not in A06 | ❌ No |
| X13 MarketAnalysisAgent | ❌ Not in A06 | ❌ No |
| X14 OrchestratorAgent | ❌ Not in A06 | ❌ No |
| X15 StrategyGeneratorAgent | ❌ Not in A06 | ❌ No |
| X16 MetaCoordinator | ✅ Yes | ❌ No trade decisions routed through it |

**Architecture gap:** X-agents communicate via I06 AgentMessageBus. The D-series StrategyOrchestrator (D31) subscribes to `EventType.MARKET_DATA`, `EventType.STRATEGY_SIGNAL`, and `EventType.RISK_VIOLATION` — but **none of these event types carry X-agent output** back into the trading loop.

---

## PART 5: TRADOVY (AUTOAGENTS) AUDIT

### Status: **Running but outputs not consumed by trading engine**

| Agent | Starts in A06? | Publishes to | D/E subscribes to it? |
|-------|---------------|-------------|----------------------|
| Y01 MarketSenseAgent | ✅ Yes | `market.conditions`, `market.regime_change`, `signals.*` | ❌ No |
| Y02 StrategyPilotAgent | ✅ Yes | `signals.validated`, `strategy.allocation`, `strategy.tuning` | ❌ No |
| Y03 RiskSentinelAgent | ✅ Yes | `risk.alerts`, `risk.circuit_breaker` | ❌ No — D31/E01 don't subscribe |
| Y04 AlphaLearnerAgent | ✅ Yes | Agent message bus | ❌ No |
| Y05 ExecutionOptimizerAgent | ✅ Yes | Agent message bus | ❌ No |
| Y06 NewsSentinelAgent | ✅ Yes | Agent message bus | ❌ No |
| Y07 TradeJournalAgent | ✅ Yes | Writes to storage | ❌ No (logging only) |
| Y08 MetaOrchestratorAgent | ✅ Yes | Manages Y-agents | ❌ No trade impact |
| Y09 CodeReviewerAgent | ✅ Yes | Advisory | ❌ No |
| Y10 AgentScheduler | ✅ Yes | Schedules Y agents | ❌ No |

**Most critical gap:** Y03 RiskSentinelAgent claims "VETO AUTHORITY over any trade proposed by other agents" — but it publishes veto decisions to `risk.circuit_breaker` on the AgentMessageBus. **E01 RiskManager and D31 StrategyOrchestrator do not subscribe to the AgentMessageBus.** The veto goes nowhere.

**Y02 StrategyPilotAgent** validates signals and publishes `signals.validated` — but D31 does not wait for or consume validated signals. Signals go directly from strategies → E01 → broker.

---

## PART 6: WIRING SUMMARY MATRIX

```
Signal/Component      → Calculated  → Displayed  → Affects Trade Decision
──────────────────────────────────────────────────────────────────────────
VIX                       YES          YES          YES (simple gate)
VIX9D                     YES          YES          NO
VXV                       YES          YES          NO
VVIX                      YES          YES          NO
$TICK                     YES          YES          NO
$TRIN                     YES          YES          NO
$ADD / breadth            YES          YES          NO
NYMO                      YES          YES          NO
CPC (Put/Call)            YES          YES          NO
CBOE SKEW                 YES          YES          NO
$VOLD                     YES          YES          NO
XLK/XLF                  YES          YES          NO
TNX (10yr)                YES          YES          NO
RVOL                      YES          YES          NO
QQQ/IWM                   YES          YES          NO
TLT/HYG/LQD               YES          YES          NO
DXY/GLD/USO               YES          YES          NO
IVR (IV Rank)             YES          YES          YES (strategy condition)
ATM_IV                    YES          YES          YES (D15 strategy)
VRP                       YES          YES          YES (D22 strategy)
GEX                       YES          YES          PARTIAL (feature-flagged off)
DEX                       YES          YES          NO
OGL                       YES          YES          NO
DIX                       YES          YES          PARTIAL (feature-flagged off)
WRS                       YES          YES          NO
PSR                       YES          YES          NO (reporting only)
SWAN                      YES          YES          YES (R08 paper engine gate)
PMR signals               YES          YES          YES (D34 strategy)
──────────────────────────────────────────────────────────────────────────
TradovV QuantModels        YES          NO           NO
TradovX Agents             YES          NO           NO (placeholder)
TradovY AutoAgents         YES          NO           NO (bus gap)
```

---

## PART 7: IMPLEMENTATION PLAN

Priority is ordered by impact on trade quality and risk management.

---

### PHASE 1 — Critical Safety Fixes (1-2 weeks)

#### P1-A: Wire Y03 RiskSentinelAgent veto to E01 RiskManager
**Problem:** Y03 has veto authority but publishes to a bus nobody reads.  
**Fix:** Add an AgentMessageBus subscription in `TradovE01_RiskManager` that sets a `_agent_veto_active` flag. The existing `validate_signal()` method checks this flag.

```python
# In TradovE01_RiskManager.__init__():
if self.agent_message_bus:
    self.agent_message_bus.subscribe("risk.circuit_breaker", self._on_agent_circuit_breaker)

def _on_agent_circuit_breaker(self, message: dict) -> None:
    state = message.get("circuit_breaker_state", "normal")
    self._y03_veto = (state in ("warning", "halt"))
```

**Files:** `TradovE_Risk/TradovE01_RiskManager.py`, `TradovY_AutoAgents/TradovY03_RiskSentinelAgent.py`

---

#### P1-B: Enable GEX/DIX regime gate by default (remove env-var flag)
**Problem:** `TRADOV_REGIME_STRUCTURE=1` must be set manually; it defaults off.  
**Fix:** Flip the default to `1` in `TradovR08_PaperTradingQtWorker._regime_preferred_direction()`. Add the same logic to `TradovR04_LiveEngine` (currently missing entirely).

**Files:** `TradovR_Runtime/TradovR08_PaperTradingQtWorker.py`, `TradovR_Runtime/TradovR04_LiveEngine.py`

---

#### P1-C: Wire VIX term structure (VIX9D / VXV) to premium-selling gate
**Problem:** Selling premium in VIX backwardation (VIX9D > VXV) is high-risk — not checked.  
**Fix:** Add a `vix_term_structure_check` to `TradovF09_EntryFilters._check_volatility_filters()`:

```python
vix9d = params.get('vix9d', vix)
vxv = params.get('vxv', vix)
if vix9d > vxv and strategy_type in PREMIUM_SELLING_STRATEGIES:
    # Backwardation — block premium selling
    checks.append(FilterCheck(FAIL, "VIX backwardation: VIX9D > VXV"))
```

**Files:** `TradovF_Analysis/TradovF09_EntryFilters.py`, strategy callers that invoke `assess_entry()`

---

### PHASE 2 — Market Internals Integration (2-3 weeks)

#### P2-A: Wire $TICK, $TRIN, NYMO into F09 EntryFilters
**Problem:** These breadth signals are collected but never consulted.  
**Fix:** Add `FilterType.BREADTH` to F09, checking TICK/TRIN/NYMO thresholds:

| Filter | PASS condition | FAIL condition |
|--------|---------------|----------------|
| $TICK | -500 to +800 | < -800 (selling panic) or > +1000 (exhaustion) |
| $TRIN | 0.5 to 1.5 | > 2.0 (heavy distribution) |
| NYMO | -60 to +60 | < -80 (oversold panic) |

The C04 MarketInternals data should be passed through S07 (already has NYMO) to the entry params dict.

**Files:** `TradovF_Analysis/TradovF09_EntryFilters.py`, `TradovS_Signals/TradovS07_CustomMetricsOrchestrator.py`

---

#### P2-B: Wire CBOE SKEW (S06) into F09 EntryFilters
**Problem:** F09 has a `FilterType.SKEW` but it checks IV skew (term skew), not the CBOE SKEW index (tail-risk).  
**Fix:** Add a CBOE SKEW check — when SKEW > 145 (extreme tail-risk), block Iron Condors and credit spreads; allow only directional hedges.

**Files:** `TradovF_Analysis/TradovF09_EntryFilters.py`

---

#### P2-C: Wire CPC (Put/Call Ratio) as contrarian signal
**Problem:** CPC is collected by S08 but not used.  
**Fix:** Integrate CPC into F09 or D30 RegimeGatedSelector as a contrarian sentiment gate:
- CPC > 1.2 → extreme fear → contrarian bullish bias (allow bull-put spreads)
- CPC < 0.5 → extreme complacency → add hedge bias

**Files:** `TradovF_Analysis/TradovF09_EntryFilters.py` or `TradovD_Strategies/TradovD30_RegimeGatedSelector.py`

---

### PHASE 3 — Regime Unification (2-3 weeks)

#### P3-A: Replace D31's simple VIX+trend regime classifier with L09 UnifiedRegimeEngine
**Problem:** D31 StrategyOrchestrator uses a 4-line classifier; L09 has HMM, ML, GEX, DIX, SWAN.  
**Fix:** In D31 `_classify_market_regime()`, add soft-import of L09 and use its regime if available:

```python
def _classify_market_regime(self, vix_level: float, ...) -> MarketRegime:
    try:
        regime = self._l09_engine.get_regime()
        return _map_l09_to_d31_regime(regime)
    except Exception:
        # Fallback to simple VIX+trend
        ...
```

**Files:** `TradovD_Strategies/TradovD31_StrategyOrchestrator.py`, `TradovL_ML/TradovL09_UnifiedRegimeEngine.py`

---

#### P3-B: Feed C04 MarketInternals into F10 MarketRegimeDetector
**Problem:** F10 has `advance_decline_ratio` in its data model but C04 is never wired to it.  
**Fix:** In `TradovA08_FSeriesOrchestrator`, connect C04 data output to F10's `market_data` dict update.

**Files:** `TradovA_Core/TradovA08_FSeriesOrchestrator.py`, `TradovC_MarketData/TradovC04_MarketInternals.py`

---

### PHASE 4 — Y-AutoAgent Loop Closure (3-4 weeks)

#### P4-A: Wire Y02 StrategyPilotAgent validated signals into D31
**Problem:** Y02 publishes `signals.validated` but D31 doesn't subscribe.  
**Approach:** D31 should have an optional `_y02_signal_queue` that receives validated signals. When Y02 approves/rejects a pending signal, D31 respects it with a configurable timeout (if Y02 doesn't respond in N seconds, proceed without approval).

**Files:** `TradovD_Strategies/TradovD31_StrategyOrchestrator.py`, `TradovY_AutoAgents/TradovY02_StrategyPilotAgent.py`

---

#### P4-B: Wire Y01 MarketSenseAgent regime output to D31
**Problem:** Y01 calls F10 and publishes regime changes — D31 ignores them.  
**Fix:** D31 subscribes to `market.regime_change` on the AgentMessageBus and updates `market_regime.current_regime` accordingly.

**Files:** `TradovD_Strategies/TradovD31_StrategyOrchestrator.py`

---

### PHASE 5 — Agent Intelligence Activation (4-6 weeks)

#### P5-A: Wire X04 RiskGuardian into E19 UnifiedRiskCoordinator (remove placeholder)
**Problem:** E19 has a clearly marked `# placeholder` that returns static values.  
**Fix:** Call `X04_RiskGuardianAgent.analyze_risk(positions, portfolio_metrics)` and use the `ai_risk_score` in E19's risk aggregation. Weight it at 10-15% of total risk score initially.

**Files:** `TradovE_Risk/TradovE19_UnifiedRiskCoordinator.py`, `TradovX_Agents/TradovX04_RiskGuardianAgent.py`

---

#### P5-B: Wire X03 StrategyDirector recommendations into D31
**Problem:** X03 generates strategy recommendations but D31 ignores them.  
**Fix:** D31 queries X03 once per regime update and uses its output to bias `_get_regime_strategy_weights()`.

**Files:** `TradovD_Strategies/TradovD31_StrategyOrchestrator.py`, `TradovX_Agents/TradovX03_StrategyDirectorAgent.py`

---

#### P5-C: Wire X01 GreeksAgent into E15 GreekLimitsManager
**Problem:** X01 analyses Greeks exposure but E15 runs its own independent calculation.  
**Fix:** After each position update, E15 queries X01 for hedge recommendations. X01's output can be used to auto-generate hedge orders when Greeks drift.

**Files:** `TradovE_Risk/TradovE15_GreekLimitsManager.py`, `TradovX_Agents/TradovX01_GreeksAgent.py`

---

### PHASE 6 — QuantModels Integration (4-6 weeks)

#### P6-A: Replace N-series BSM with V05 PricingEngine
**Problem:** N-series has its own pricing engine; V05 has Heston, SABR, jump-diffusion — never used.  
**Fix:** In `TradovN01_OptionsPricer`, add optional V05 call for enhanced pricing when model is available.

#### P6-B: Wire V06 VolatilityEngine into F08 VolatilityRegime
**Problem:** F08 uses simple HV calculations; V06 has GARCH, EGARCH, HAR-RV — never called.  
**Fix:** F08 should attempt V06 for a GARCH-based volatility forecast, falling back to its own HV if unavailable.

#### P6-C: Wire V04 RiskManager into E19 as second opinion
**Problem:** E19 claims to use V04 in its docstring but doesn't import or call it.  
**Fix:** E19 should call `V04.scenario_analysis(positions, shocks)` during the risk assessment cycle.

---

## PART 8: QUICK WINS TABLE

| Priority | Change | Risk | Effort | Impact |
|----------|--------|------|--------|--------|
| 🔴 P1 | Enable GEX/DIX regime by default (flip env var) | LOW | 30 min | HIGH |
| 🔴 P1 | Y03 veto → E01 subscription | LOW | 2 hrs | HIGH |
| 🔴 P1 | VIX term structure (VIX9D/VXV) gate in F09 | LOW | 3 hrs | HIGH |
| 🟠 P2 | CBOE SKEW gate in F09 (block IC when SKEW>145) | LOW | 2 hrs | MEDIUM |
| 🟠 P2 | Wire TICK/TRIN/NYMO to F09 breadth filter | MEDIUM | 1 day | HIGH |
| 🟠 P2 | CPC contrarian signal in D30 | LOW | 3 hrs | MEDIUM |
| 🟡 P3 | D31 → L09 regime integration | MEDIUM | 2 days | HIGH |
| 🟡 P3 | C04 → F10 wiring in A08 | LOW | 1 day | MEDIUM |
| 🔵 P4 | Y01 regime → D31 subscription | MEDIUM | 1 day | MEDIUM |
| 🔵 P4 | Y02 signal validation loop | HIGH | 3 days | HIGH |
| 🟣 P5 | X04 placeholder → real call | HIGH | 3 days | HIGH |
| 🟣 P6 | V05/V06 integration | HIGH | 1 week | MEDIUM |

---

## PART 9: FILES TO MODIFY

| File | Change |
|------|--------|
| `TradovE_Risk/TradovE01_RiskManager.py` | Subscribe to Y03 veto on AgentMessageBus |
| `TradovF_Analysis/TradovF09_EntryFilters.py` | Add TICK, TRIN, NYMO, CBOE SKEW, VIX9D/VXV filters |
| `TradovR_Runtime/TradovR08_PaperTradingQtWorker.py` | Enable TRADOV_REGIME_STRUCTURE by default |
| `TradovR_Runtime/TradovR04_LiveEngine.py` | Add GEX/DIX/SWAN regime logic (currently missing entirely) |
| `TradovD_Strategies/TradovD31_StrategyOrchestrator.py` | Replace simple regime with L09; subscribe to Y01/Y02 bus |
| `TradovE_Risk/TradovE19_UnifiedRiskCoordinator.py` | Remove X04 placeholder; call real X04 agent |
| `TradovA_Core/TradovA08_FSeriesOrchestrator.py` | Wire C04 → F10 data flow |
| `TradovY_AutoAgents/TradovY03_RiskSentinelAgent.py` | Ensure circuit_breaker message format is standardised |
| `TradovD_Strategies/TradovD30_RegimeGatedSelector.py` | Add CPC contrarian signal |

---

## PART 10: NORTH STAR ARCHITECTURE (TARGET STATE)

```
Market Data (C-series)
    │
    ├── C04 MarketInternals ($TICK, $TRIN, $ADD) ──────────────┐
    ├── C10 VIXAnalyzer (VIX, VIX9D, VXV, VVIX) ──────────────┤
    ├── C18 SKEWCalculator ──────────────────────────────────────┤
    └── S07 CustomMetricsOrchestrator (GEX,DIX,SWAN,WRS,PSR)────┤
                                                                 ↓
                                                    F10 MarketRegimeDetector
                                                    L09 UnifiedRegimeEngine
                                                                 │
                              Y01 MarketSenseAgent ──────────────┤
                              (regime confirmation)              ↓
                                                    D31 StrategyOrchestrator
                                                    (regime-gated weights)
                                                                 │
                                              Y02 StrategyPilot validates ←────┐
                                                                 ↓             │
                                                    D-series strategies        │
                                                    (generate signals)         │
                                                                 │             │
                                                                 └─────────────┘
                                                    F09 EntryFilters
                                                    (VIX,TICK,TRIN,NYMO,
                                                     SKEW,CPC,VIX9D/VXV)
                                                                 ↓
                                                    E01 RiskManager
                                                    + Y03 veto subscription
                                                    + X04 AI risk layer
                                                    + E19 Unified coordinator
                                                                 ↓
                                                    B40 TradierClient (execute)
```
