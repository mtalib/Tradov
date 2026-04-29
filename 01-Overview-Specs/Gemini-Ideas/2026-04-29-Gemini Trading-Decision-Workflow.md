

This document is a masterpiece of architectural mapping, but because it reflects the current bloated state of the codebase, it requires some strategic demolition to align with our v1.0 Lean Architecture. 

To ensure your system executes cleanly without signal collision or data overfitting, here are the exact changes I suggest making to the `TRADING_DECISION_WORKFLOW.md` document and the underlying code it represents.

### 1. Gut the Regime Weighting Table (Section Q2.1)
The current table still lists the "kitchen sink" of redundant indices and noisy market internals (QQQ, IWM, $TICK, AAII, etc.). We need to rewrite this contract so that `L09` and `D31` only process the minimum viable data payload.

**Suggested Replacement for Q2.1:**
```markdown
| Regime | Primary symbols to weight | Primary metrics to weight | Typical gate emphasis |
|---|---|---|---|
| bull_trend | SPY, VIX | SPY vs 50-EMA, VIX < EMA | Confirm SPY trend; check option chain liquidity; block if VIX accelerates. |
| bear_trend | SPY, VIX | SPY vs 50-EMA, VIX > EMA | Confirm SPY downside structure; tighten risk limits; avoid short-vega structures. |
| range_calm | SPY, VIX, VIX9D | SPY ATR, Contango status | Favor neutral structures (Iron Condors); block if price breaks dynamic volatility bands. |
| high_vol_mean_reversion | SPY, VIX, VIX9D | SPY ATR, term_slope_0_7 | Emphasize vol-shock containment; strict surface_confidence thresholds. |
| crisis_turbulent | VIX, VIX9D | VIX/VIX9D Inversion | Hard-block posture; trigger kill-switch or hedge-only mode; data_quality_feed is critical. |
| event_transition | SPY, VIX | Calendar Proximity | Event-clock caution; reduce trust in aging surface inputs; force size reduction. |
```

### 2. Slash the Concurrency Caps (Section Q3)
Currently, `D31` defines `MAX_CONCURRENT_STRATEGIES = 8` and the engine allows registration of up to 20 strategies. This is far too dangerous for an autonomous options bot in its first live iteration.

**Suggested Changes to Q3:**
* Change `SPYDER_MAX_CONCURRENT_STRATEGIES` from **8** down to **2** (e.g., one directional spread, one neutral spread).
* Change `SPYDER_MAX_ACTIVE_HORIZON_BUCKETS` from **3** down to **1** (e.g., force the bot to only trade the "short" intraday/1DTE bucket so you don't tie up capital in swing trades while testing).

### 3. Mute the "Ghost in the Machine" (The AutoAgents)
The End-to-End flowchart and Section 2 mention `Y01/Y02/Y03/Y08 AutoAgents` and `X03/X04 On-demand agents` injecting advisory vetoes and coordination into `D31`. 

**Suggested Action:** For v1.0, you must mathematically guarantee why a trade was taken or rejected. If an LLM or AutoAgent randomly vetoes a perfectly good setup because it hallucinated a macro-risk, you will never be able to properly backtest or debug the core logic. 
* **Update the doc:** Add a note stating: *"For v1.0 Lean Branch, all Y-series and X-series advisory agents are set to OBSERVE-ONLY mode. They may log telemetry, but `D31` will ignore their veto/advisory flags."*

By making these changes, `D31 StrategyOrchestrator` becomes a purely deterministic engine: it checks the SPY/VIX regime, verifies the options chain data quality, applies a hard risk limit via `E01`, and executes. No guessing, no conflicting signals.

Are you comfortable going into your `config` files and hardcoding the `MAX_CONCURRENT_STRATEGIES` down to 2, or would you prefer we write a script to dynamically lock the unneeded strategies out?
