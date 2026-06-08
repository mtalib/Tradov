---
description: "Use when editing broker, market-data, startup, strategy, risk, runtime, or launch code in Tradov. Covers paper-vs-live safety, current Tradier policy, and execution-path boundaries."
applyTo:
  - "Tradov/TradovA_Core/**/*.py"
  - "Tradov/TradovB_Broker/**/*.py"
  - "Tradov/TradovC_MarketData/**/*.py"
  - "Tradov/TradovD_Strategies/**/*.py"
  - "Tradov/TradovE_Risk/**/*.py"
  - "Tradov/TradovQ_Scripts/**/*.py"
  - "Tradov/TradovR_Runtime/**/*.py"
  - "config/**/*.py"
---
# Trading Path Guidelines

- Preserve the main path: market data -> analysis and signals -> strategies -> risk -> runtime and broker. Do not bypass risk checks or call broker execution directly from UI code unless that path already exists.
- Default to paper-safe behavior. The current repo policy is live Tradier data and endpoints plus local paper execution; do not reintroduce sandbox Tradier routing or `TRADING_MODE=sandbox` support.
- When paper mode is involved, follow the paper engine or local PaperBroker path. Be cautious with `OrderManager` or direct broker wiring in paper mode unless a paper-capable adapter already exists.
- Start broker and market-data changes from the primary surfaces: [TradovB40_TradierClient](../../Tradov/TradovB_Broker/TradovB40_TradierClient.py), [TradovC27_MassiveClient](../../Tradov/TradovC_MarketData/TradovC27_MassiveClient.py), [TradovC29_DataProviderRouter](../../Tradov/TradovC_MarketData/TradovC29_DataProviderRouter.py), [TradovR02_PaperEngine](../../Tradov/TradovR_Runtime/TradovR02_PaperEngine.py), and [TradovR04_LiveEngine](../../Tradov/TradovR_Runtime/TradovR04_LiveEngine.py).
- Preserve retries, rate limiting, circuit breakers, and mode validation when changing external calls or startup configuration.
- Pair policy changes with focused regressions in `Tradov/TradovT_Testing`; prefer the narrowest `pytest` target first, then `ruff check` on touched files.
- References: [Trading Decision Workflow v34](../../01-Overview-Specs/2026-05-18-TRADING_DECISION_WORKFLOW-FULL-v34.md), [Live Launch Checklist](../../01-Overview-Specs/2026-04-25-Live-Launch-Checklist.md), and [Rate Limiting and Circuit Breakers](../../02-Standards-Instructions/RATE_LIMITING_CIRCUIT_BREAKER_GUIDE.md).