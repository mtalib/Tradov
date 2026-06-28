# TRADOV

Tradov is a hybrid live/paper pair-trading and research platform. The current repo combines:

- operator-curated pair-trading and stat-arb surfaces
- immutable per-session runtime context
- availability-aware market-condition handling
- best-effort paired execution and reconciliation
- offline Q92/Q94 research workflows

The current implementation is described in:

- [Trading Decision Workflow (Pair / Stat-Arb) -- v48](/home/adam/Projects/Tradov/01-Overview-Specs/2026-06-19-TRADING_DECISION_WORKFLOW-FULL-v47.md)
- [Tradov System Architecture v4](/home/adam/Projects/Tradov/01-Overview-Specs/2026-06-18-Tradov_System_Architecture-v4.md)

## Current Entry Points

- Console entry point: `tradov=Tradov.TradovA_Core.TradovA01_Main:main`
- Main session owner: `TradovR_Runtime/TradovR12_SessionSupervisor.py`
- Primary orchestrator: `TradovD_Strategies/TradovD31_StrategyOrchestrator.py`
- Pair execution: `TradovB_Broker/TradovB02_PairOrderExecutor.py`
- Pair risk manager: `TradovE_Risk/TradovE26_PairRiskManager.py`
- Market-condition surface: `TradovS_Signals/TradovS07_CustomMetricsOrchestrator.py`
- Research workflow: `TradovQ_Scripts/TradovQ92_ResearchWorkflow.py`
- Pair research workflow: `TradovQ_Scripts/TradovQ94_PairResearchWorkflow.py`

## Operator Commands

The shell launchers automatically prefer `.venv/bin/python` when it exists.

```bash
source .venv/bin/activate
```

Run the research workflow:

```bash
bash ./launch_research_workflow.sh \
  --input path/to/research.csv \
  --timestamp-col timestamp \
  --label-col label \
  --features feature_1,feature_2 \
  --output reports/research_report.json
```

Run pair research:

```bash
bash ./launch_pair_research_workflow.sh \
  --input path/to/pairs.csv \
  --timestamp-col timestamp \
  --price-a-col symbol_a_price \
  --price-b-col symbol_b_price \
  --symbol-a AAA \
  --symbol-b BBB \
  --output reports/pair_research_report.json
```

These workflows are for offline experimentation and model lifecycle management. They do not replace the live broker path.

## Runtime Model

Current runtime behavior is anchored on:

- `TradovU_Utilities/TradovU51_RuntimeContext.py` for immutable per-session mode data
- `TradovU_Utilities/TradovU50_RegimeOverrideStore.py` for persisted regime overrides
- `TradovA_Core/TradovA01_Main.py` for startup and GUI launch
- `TradovR_Runtime/TradovR12_SessionSupervisor.py` for lifecycle ownership

The runtime no longer depends on process-global env rewriting as the primary control boundary.

## Strategy and Risk

The current live trading path is centered on:

- regime detection and strategy selection in D31
- pair risk validation in E26
- pair order routing in B02
- fill and position reconciliation in B03

Current policy points:

- market-condition unavailability is explicit and should not be treated as neutral live state
- live entry gates fail closed when required market-condition data is missing
- pair execution has recovery logic for partial leg submission

## Package Layout

The repo is organized by series:

- `TradovA_Core` - app bootstrap, config, event bus, scheduler
- `TradovB_Broker` - order management, account state, Tradier client, pair executor
- `TradovC_MarketData` - feeds, caches, validation, internals
- `TradovD_Strategies` - pair strategy families, regime selector, orchestration
- `TradovE_Risk` - risk manager, freshness, exposure controls
- `TradovF_Analysis` - indicators, volatility, filters, performance
- `TradovG_GUI` - dashboard and helper surfaces
- `TradovH_Storage` - persistence and trade history
- `TradovL_ML` - regime engine and ML tooling
- `TradovQ_Scripts` - research workflows and thin launchers
- `TradovR_Runtime` - session supervisor, live engine, paper harness
- `TradovS_Signals` - S07 custom metrics and signal surfaces
- `TradovT_Testing` - focused regression tests
- `TradovU_Utilities` - logging, flags, runtime context, stores
- `TradovX_Agents` - LLM agent surfaces
- `TradovY_AutoAgents` - autonomous background agents
- `TradovZ_Communication` - message protocol and cross-module communication

## Notes

- The old registry-driven strategy auto-activation path is retired.
- Market-condition unavailability is explicit and should not be treated as neutral live state.
- Pair trading is a first-class repo surface.
