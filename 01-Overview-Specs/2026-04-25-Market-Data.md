# 2026-04-25-Market-Data
Date: 2026-04-25

## Scope
This report maps each symbol shown in the MARKET OVERVIEW panel to its data source in the current Spyder codebase, then lists symbols used elsewhere in code that are not shown in MARKET OVERVIEW.

Primary reference files:
- Spyder/SpyderG_GUI/SpyderG05_TradingDashboard.py (MARKET_SYMBOLS, S07 widget routing)
- Spyder/SpyderG_GUI/SpyderG18_MarketDataWorker.py (Tradier quote fetch, remaps, computed fields)
- Spyder/SpyderS_Signals/SpyderS07_CustomMetricsOrchestrator.py (S-series metric sources)
- Spyder/SpyderS_Signals/SpyderS11_TradingViewInternals.py (TradingView internals scraping)
- Spyder/SpyderS_Signals/SpyderS09_FREDClient.py (FRED macro series)

## 1) MARKET OVERVIEW Symbols and Source

### S&P CORE
- SPY: Tradier quotes (direct)
- SPX: Tradier quotes (direct)

### VOLATILITY
- VIX: Tradier quotes (direct)
- VIX9D: Tradier quotes (direct)
- VXV: Tradier quotes (direct)
- VVIX: Tradier quotes (direct)

### MARKET INTERNALS
- $TICK: TradingView internals via S11 (USI-TICK), routed through S07
- $TRIN: TradingView internals via S11 (USI-TRIN.NY), routed through S07
- $ADD: TradingView internals via S11 (USI-ADD), routed through S07
- NYMO: Computed in S07 as proxy from ADD/25 (USI-NYMO page unavailable)
- CPC: Computed in G18 from Tradier SPY option-chain put volume / call volume
- SKEW: Tradier SPY options-chain based calculation via S06 (yfinance fallback available in S06)
- $VOLD: TradingView internals via S11 (USI-VOLD), routed through S07
- XLK: Tradier quotes (direct)
- XLF: Tradier quotes (direct)
- TNX: FRED 10Y yield (GS10) via S09, emitted by S07 as YIELD_10Y and mapped in dashboard to TNX
- RVOL: Computed in G18 from Tradier SPY quote volume and average_volume

### MAJOR INDICES
- QQQ: Tradier quotes (direct)
- IWM: Tradier quotes (direct)

### BONDS & CREDIT
- TLT: Tradier quotes (direct)
- HYG: Tradier quotes (direct)
- LQD: Tradier quotes (direct)

### CORRELATIONS
- DXY: Tradier UUP quote remapped to DXY in G18 (_SYMBOL_REMAP)
- GLD: Tradier quotes (direct)
- USO: Tradier quotes (direct)

### OPTIONS ANALYTICS
- IVR: Computed by S07 options analytics from Tradier SPY options chain + rolling IV history
- ATM_IV: Computed by S07 options analytics from Tradier SPY options chain (nearest ATM contracts)
- VRP: Computed by S07 as ATM_IV - HV20 (HV20 from Tradier SPY daily history)

### CUSTOM METRICS
- GEX: S05 calculator (SPY options-chain exposures from N09/N03 internal options pipeline)
- DEX: S05 calculator (same source path as GEX)
- OGL: S05 calculator (same source path as GEX)
- DIX: S01 calculator (FINRA Reg SHO short-volume + market-cap weighting, with yfinance/provider support)
- WRS: S12 macro signal (Tradier primary, yfinance fallback)
- PSR: S13 macro signal (Tradier primary, yfinance fallback)
- SWAN: S03 black-swan composite (C29/Massive quote path first; yfinance fallback; simulated fallback if both unavailable)
- PMR: S08 Pivot Mean-Reversion signal state (strategy/signal state, not a direct market quote)

#### SWAN update behavior (launch vs schedule)

- SWAN is calculated at startup: when S07 orchestrator starts, it runs an immediate background `update_all_metrics()` pass, which includes `_update_swan_metrics()` calling S03 `calculate_swan_score()`.
- SWAN is also continuously refreshed by S07 timer cadence: default every `60s`, with dynamic fast mode at `30s` during high-stress conditions.
- In parallel, S04 Black Swan Scheduler runs formal time-of-day checks at default ET times: `04:00`, `09:15`, `12:00`, `15:45`, `16:30`.
- Late startup is handled explicitly: S07 startup path triggers `run_now("daily_check_0915")`, and S04 also runs missed startup checks for any already-passed MARKET_CHECK tasks.

## 1A) Live Verification Snapshot (2026-04-25)

The following checks were run directly against the current codebase in the project virtualenv to verify that the custom metrics are not just wired, but returning plausible live data.

| Metric | Module / Path | Live Result | Notes |
|---|---|---|---|
| CPC | G18 market worker chain aggregation | `1.140055` | Put vol = `589241`, call vol = `516853`, expiry = `2026-04-27`, 352 contracts |
| SKEW | S06 | `100.4100` | 256 strikes, spot = `713.98`, confidence = `0.5106`, expiry = `2026-05-22`; S06 simulated fallback disabled here |
| GEX / DEX / OGL | S05 | `4.0997 B$` / `2104.9660 M$` / `720.0000` | 176 strikes, data source = `SpyderB40_TradierClient` |
| ATM_IV / IVR / VRP | S07 options analytics | `11.2533` / `21.6387` / `-5.1806` | Verified through `_update_options_analytics_metrics()`, `ok=True`, no updater errors |
| DIX | S01 | `0.485083` / `48.5083%` | Date = `20260424`, 501 symbols |
| WRS | S12 | `0.016408` | Percentile rank = `80.28%`, z-score = `1.9705`, signal = `WARNING`, date = `2026-04-24`, no error |
| PSR | S13 | `4.878646` | Percentile rank = `92.28%`, z-score = `2.6759`, signal = `CRITICAL`, FCFS = `219.0`, EZPW = `31.86`, XLF = `51.42`, date = `2026-04-24`, no error |
| SWAN | S03 | `1.62` | Status = `GREEN`, data quality = `good` |
| PMR | S08 | Neutral valid result | `direction=none`, `score=0`, `fired=False`; execution path confirmed, but PMR is strategy state rather than direct feed data |

Additional yfinance proof for Spyder fallback paths:

- yfinance version installed in the Spyder venv: `0.2.66`
- Live quote fetches succeeded for `^VIX`, `SPY`, `HYG`, `LQD`, and `DX-Y.NYB`
- S03/SWAN successfully completed with `data_quality = good`, confirming real upstream data rather than simulated fallback output
- The S07 options-analytics live check succeeded even though full orchestrator construction also logged an unrelated DIX scheduler init error (`SpyderDIXCalculator` name resolution inside S02). That wiring issue did not prevent IVR / ATM_IV / VRP from updating successfully

## 2) Symbols Used in Codebase but Not Shown in MARKET OVERVIEW

The symbols below are used by market-data/signal modules but are not listed as rows in MARKET OVERVIEW.

### A) Market data worker / chart / proxy symbols
- /ES (simulation baseline only)
- VXMT (simulation baseline)
- UVXY (fetched in market worker lists)
- PCALL (alias/companion to CPC in market worker)
- DIA (used as proxy for DJIA display behavior)
- UUP (raw Tradier symbol remapped to DXY)
- RUT (Russell index feed symbol)
- NDX (mentioned in index/proxy comments)
- IXIC (mentioned in index/proxy comments)

### B) FRED macro series identifiers (not dashboard symbols)
- GS2, GS5, GS10, GS30
- DFEDTARU
- T10Y2Y, T10Y3M
- DTWEXBGS
- VIXCLS

### C) S12 WRS basket symbols (not MARKET OVERVIEW rows)
- WMT
- LVMUY, CFRUY, HESAY, PPRUY, BURBY, SWGAY, RACE, TPR, CPRI

### D) S13 PSR component symbols (not MARKET OVERVIEW rows)
- FCFS
- EZPW

### E) S03 SWAN internal component symbols (partly separate from panel rows)
- ^VIX, ^VIX9D, ^VXN, ^RVX
- DX-Y.NYB

## 3) Readiness Gap Matrix (Autonomous SPY Options)

The current stack is strong for paper/autonomous validation, but the gaps below are the highest-impact items for live-capital robustness.

| Priority | Gap (Missing or Under-modeled) | Why It Matters for Live Trading | Likely Owner Module(s) | Acceptance Criteria |
|---|---|---|---|---|
| P0 | Options liquidity quality by strike/expiry (spread %, staleness, top-of-book size, depth proxy, OI change) | Prevents fills in structurally bad contracts and reduces hidden slippage | C03/C30, N03/N07, B40, S07 aggregator | Pre-trade gate blocks contracts breaching liquidity thresholds; 30-day reject/slippage reduction vs baseline |
| P0 | Execution telemetry (slippage vs mid, fill latency, partial-fill %, cancel/replace %, reject %) | Autonomous system fails in production if execution quality is not measured and fed back into gating | B02/B40, M04/M05, K04, R02/R04 | Telemetry persisted per order and surfaced in dashboard/reports; strategy sizing responds to degraded execution regime |
| P0 | Event-risk clock and blackout windows (CPI, FOMC, NFP, OpEx + pre/post buffers) | Major event windows dominate short-DTE option behavior and can invalidate normal signal edges | A04 scheduler, F09 entry filters, E16 circuit breaker, S07 | Configurable event calendar with enforced no-trade/reduced-risk windows; all violations logged and tested |
| P1 | Vol surface structure (0DTE/1DTE/7DTE/30DTE term nodes, 25d RR, fly/convexity, slope drift) | Improves strike selection and regime labeling beyond single ATM-IV snapshots | N06/N08/N12, S07 options analytics, F08/F10 | Surface metrics update intraday; strategy/risk rules consume thresholds for entry/position size |
| P1 | Dealer-flow structure beyond aggregate GEX (zero-gamma path, call/put walls with confidence, vanna/charm pressure proxy) | Better identifies pin/break dynamics and intraday reversal odds | N09/N11, C30, S05 extension | Directional gate uses wall/zero-gamma context; measurable reduction in false entries on trend days |
| P1 | Cross-asset lead/lag execution context (ES front month, optional MES) | Futures often lead SPY micro-moves around key levels and event prints | C11/C15, F14, S07 | Lead/lag signal available with latency stats; entry filter can require confirmation in fast markets |
| P2 | Sector rotation breadth expansion (defensive vs cyclical spread panel beyond XLK/XLF) | Improves macro-state discrimination and helps avoid one-factor regime errors | C13/C22, F10, G05/G20 | Composite sector breadth score published and used as secondary regime input |
| P2 | Data quality SLOs by metric (freshness, completeness, fallback provenance) | Autonomy requires explicit trust policy for each feed/metric | E24 DataFreshnessMonitor, S07 quality tracking, M01 monitoring | Per-metric SLO dashboard with alerting; strategy disables affected edges when SLOs fail |

### Practical Readiness Summary

- Sufficient today for: paper-trading validation and controlled autonomous testing.
- Not yet sufficient alone for: resilient live-capital deployment at institutional reliability.
- Minimum recommended live-readiness bundle: all `P0` items + at least first two `P1` items.

### 3A) P0 Implementation Map (Classes/Functions + Proposed Config Keys)

#### P0-1) Options Liquidity Quality Gate

Primary integration points:
- `Spyder/SpyderS_Signals/SpyderS07_CustomMetricsOrchestrator.py`
	- `_update_options_analytics_metrics()`
	- Extend metric payload to include per-candidate strike liquidity diagnostics.
- `Spyder/SpyderF_Analysis/SpyderF09_EntryFilters.py`
	- Add pre-trade hard gate for spread quality + quote freshness + OI/volume.
- `Spyder/SpyderB_Broker/SpyderB02_OrderManager.py`
	- Enforce final pre-submit liquidity sanity check.

Proposed config keys:
- `liquidity.max_spread_pct`
- `liquidity.max_spread_abs`
- `liquidity.min_top_of_book_size`
- `liquidity.max_quote_age_ms`
- `liquidity.min_open_interest`
- `liquidity.min_volume`
- `liquidity.min_oi_change_pct`

Suggested rollout:
1. Emit diagnostics in S07 only (observe mode).
2. Turn on soft warning in F09 (no blocks).
3. Promote to hard gate in F09 + B02 after baseline stats stabilize.

#### P0-2) Execution Telemetry + Feedback Loop

Primary integration points:
- `Spyder/SpyderB_Broker/SpyderB02_OrderManager.py`
	- Record submit time, acknowledge time, fill time, partial-fill lifecycle.
- `Spyder/SpyderB_Broker/SpyderB40_TradierClient.py`
	- Capture raw order/quote snapshots around execution for slippage attribution.
- `Spyder/SpyderK_Reports/SpyderK04_ExecutionAnalytics.py`
	- Aggregate slippage/latency/reject metrics by strategy and market regime.
- `Spyder/SpyderG_GUI/SpyderG05_TradingDashboard.py`
	- Display live execution health panel (latency/slippage/reject trend).

Proposed config keys:
- `execution.max_slippage_bps`
- `execution.max_fill_latency_ms`
- `execution.max_partial_fill_ratio`
- `execution.max_reject_rate_5m`
- `execution.degrade_size_multiplier`
- `execution.halt_on_quality_breach`

Suggested rollout:
1. Persist telemetry only (no control impact).
2. Add warning thresholds in dashboard/reporting.
3. Feed thresholds into dynamic sizing / temporary trade halt logic.

#### P0-3) Event-Risk Clock + Blackout Windows

Primary integration points:
- `Spyder/SpyderA_Core/SpyderA04_Scheduler.py`
	- Register event calendar jobs and pre/post event windows.
- `Spyder/SpyderF_Analysis/SpyderF09_EntryFilters.py`
	- Gate entries by event proximity and strategy sensitivity.
- `Spyder/SpyderE_Risk/SpyderE16_CircuitBreakerProtocol.py`
	- Activate event-mode risk profile / temporary circuit breaker states.
- `Spyder/SpyderS_Signals/SpyderS07_CustomMetricsOrchestrator.py`
	- Publish `event_risk_state` metric for all downstream consumers.

Proposed config keys:
- `event_clock.enabled`
- `event_clock.sources`
- `event_clock.blackout_pre_minutes`
- `event_clock.blackout_post_minutes`
- `event_clock.high_impact_only`
- `event_clock.allowlist_strategies`
- `event_clock.max_size_multiplier_during_event`

Suggested rollout:
1. Event state broadcast and logging only.
2. Soft blocks on highest-impact events.
3. Full blackout enforcement + reduced-risk mode around configured windows.

#### Recommended Implementation Order (P0)

1. P0-2 Execution telemetry (establish baseline truth first).
2. P0-1 Liquidity gate (use telemetry baseline to set thresholds).
3. P0-3 Event-risk clock (final hard-risk wrapper for autonomous live mode).

### 3B) P0 Test Plan Matrix (Unit -> Integration -> Paper -> Live-Sandbox)

#### P0-1) Options Liquidity Quality Gate

| Test Level | What to Validate | Pass Criteria |
|---|---|---|
| Unit | Spread %, quote-age, top-of-book size, OI/volume threshold evaluators | Deterministic pass/fail at boundary values; no false positives on exact threshold |
| Integration | S07 diagnostics -> F09 gate -> B02 pre-submit block path | Orders with poor liquidity are blocked with explicit reason codes logged |
| Paper | Replay low-liquidity windows (open/close, lunch lull, event spikes) | Lower rejected/poor-fill attempts vs baseline without reducing valid opportunity count disproportionately |
| Live-Sandbox | Tradier sandbox order attempts under gate constraints | No submits on blocked contracts; telemetry records gate decisions and downstream outcomes |

#### P0-2) Execution Telemetry + Feedback Loop

| Test Level | What to Validate | Pass Criteria |
|---|---|---|
| Unit | Slippage/latency math, partial-fill ratio, reject-rate rolling windows | Metric calculations match fixture truth tables and edge cases |
| Integration | B02/B40 capture -> persistence -> K04 analytics -> G05 dashboard | Every order has complete lifecycle telemetry; no null critical fields |
| Paper | Strategy runs with telemetry-only then telemetry-driven sizing | Sizing reduction activates only when configured thresholds are exceeded |
| Live-Sandbox | Real API interaction timing and fill state transitions | Latency/slippage panels update in near real-time; no crashes on partial/replace states |

#### P0-3) Event-Risk Clock + Blackout Windows

| Test Level | What to Validate | Pass Criteria |
|---|---|---|
| Unit | Event window resolver (`pre`, `post`, overlap, timezone handling) | Correct event-state transitions for boundary timestamps |
| Integration | A04 event jobs -> S07 event state -> F09 gate -> E16 risk mode | Entry filters and breaker mode switch correctly during blackout windows |
| Paper | Historical CPI/FOMC/NFP days replay with event windows enabled | New entries suppressed/reduced per policy; no policy violations in logs |
| Live-Sandbox | Upcoming scheduled event simulation with active session | System enters/exits blackout state on time with audit trail and no orphan state |

#### Cross-Cutting Non-Functional Gates (All P0)

| Category | Requirement | Pass Criteria |
|---|---|---|
| Observability | Structured logs for gate decisions and reason codes | 100% of blocked actions have machine-parseable reason tags |
| Resilience | Fallback behavior on missing data/feed hiccups | Fails safe (block/reduce risk) without process crash |
| Performance | No material UI or loop blocking from added checks | Update loop latency remains within existing operational tolerance |
| Regression Safety | Existing strategy behavior outside gated conditions | No unexpected behavior drift in non-event, liquid baseline sessions |

#### Exit-to-Live Checklist (Minimum)

1. All unit and integration suites green for three consecutive CI runs.
2. Paper run with P0 enabled for at least 10 trading sessions, with stable telemetry completeness.
3. Live-sandbox run through at least one high-impact event window (CPI or FOMC) with zero blackout-policy violations.
4. Sign-off report includes before/after metrics: reject rate, slippage distribution, and policy-block reason distribution.

### 3C) Initial Default Thresholds (Starter Values)

These defaults are intentionally conservative for first live-sandbox rollout. They should be tuned after telemetry baseline is established.

#### Liquidity Gate Defaults (P0-1)

| Config Key | Starter Default | Notes |
|---|---|---|
| `liquidity.max_spread_pct` | `0.12` | Max bid/ask spread as % of option mid-price |
| `liquidity.max_spread_abs` | `0.20` | Max absolute spread in dollars per contract |
| `liquidity.max_quote_age_ms` | `1500` | Quote older than this is considered stale |
| `liquidity.min_top_of_book_size` | `10` | Minimum displayed contracts at best quote (if feed supports size) |
| `liquidity.min_open_interest` | `500` | Minimum OI per leg |
| `liquidity.min_volume` | `50` | Minimum same-day volume per leg |
| `liquidity.min_oi_change_pct` | `-0.20` | Guardrail against collapsing interest (optional; disable if unavailable) |

#### Execution Telemetry Defaults (P0-2)

| Config Key | Starter Default | Notes |
|---|---|---|
| `execution.max_slippage_bps` | `25` | Max acceptable slippage vs mid at decision time |
| `execution.max_fill_latency_ms` | `2500` | Fill latency threshold before degraded mode |
| `execution.max_partial_fill_ratio` | `0.40` | Partial fills / total fills over rolling window |
| `execution.max_reject_rate_5m` | `0.08` | Rejects per submits over last 5 minutes |
| `execution.degrade_size_multiplier` | `0.50` | Position-size multiplier in degraded mode |
| `execution.halt_on_quality_breach` | `true` | Hard stop on severe sustained execution degradation |

#### Event-Risk Clock Defaults (P0-3)

| Config Key | Starter Default | Notes |
|---|---|---|
| `event_clock.enabled` | `true` | Enables event blackout/risk state engine |
| `event_clock.sources` | `"calendar+manual"` | Start with deterministic schedule + operator overrides |
| `event_clock.high_impact_only` | `true` | CPI/FOMC/NFP/OpEx first, expand later |
| `event_clock.blackout_pre_minutes` | `30` | Block/reduce entries before event release |
| `event_clock.blackout_post_minutes` | `30` | Block/reduce entries after release |
| `event_clock.max_size_multiplier_during_event` | `0.25` | If trading allowed, use strongly reduced size |
| `event_clock.allowlist_strategies` | `[]` | Empty list means no exemptions by default |

#### Stress-Mode Escalation Defaults (Cross-Cutting)

| Condition | Suggested Action |
|---|---|
| 1 threshold breach (single domain) | Warn + telemetry tag only |
| 2 concurrent breaches | Apply `degrade_size_multiplier` |
| 3+ concurrent breaches or sustained 10 min | Temporary entry halt + circuit-breaker event |

#### Tuning Guidance

1. Keep defaults unchanged for first 10 paper sessions to build stable baseline distributions.
2. Tune one domain at a time (`liquidity` then `execution` then `event_clock`) to avoid confounded results.
3. Any threshold loosening must include before/after evidence for slippage, reject rate, and realized risk drift.

### 3D) YAML / ENV Config Snippet Examples

The snippets below are starter templates aligned with section `3C`. Adapt key names to your final config loader conventions.

#### YAML Example (recommended)

```yaml
autonomous_readiness:
	liquidity:
		enabled: true
		max_spread_pct: 0.12
		max_spread_abs: 0.20
		max_quote_age_ms: 1500
		min_top_of_book_size: 10
		min_open_interest: 500
		min_volume: 50
		min_oi_change_pct: -0.20

	execution:
		enabled: true
		max_slippage_bps: 25
		max_fill_latency_ms: 2500
		max_partial_fill_ratio: 0.40
		max_reject_rate_5m: 0.08
		degrade_size_multiplier: 0.50
		halt_on_quality_breach: true

	event_clock:
		enabled: true
		sources: "calendar+manual"
		high_impact_only: true
		blackout_pre_minutes: 30
		blackout_post_minutes: 30
		max_size_multiplier_during_event: 0.25
		allowlist_strategies: []

	escalation:
		warn_on_single_breach: true
		degrade_on_two_breaches: true
		halt_on_three_breaches: true
		sustained_breach_minutes: 10
```

#### ENV Example (flat key mapping)

```bash
# Liquidity gate
SPYDER_LIQUIDITY_ENABLED=true
SPYDER_LIQUIDITY_MAX_SPREAD_PCT=0.12
SPYDER_LIQUIDITY_MAX_SPREAD_ABS=0.20
SPYDER_LIQUIDITY_MAX_QUOTE_AGE_MS=1500
SPYDER_LIQUIDITY_MIN_TOP_OF_BOOK_SIZE=10
SPYDER_LIQUIDITY_MIN_OPEN_INTEREST=500
SPYDER_LIQUIDITY_MIN_VOLUME=50
SPYDER_LIQUIDITY_MIN_OI_CHANGE_PCT=-0.20

# Execution quality controls
SPYDER_EXECUTION_ENABLED=true
SPYDER_EXECUTION_MAX_SLIPPAGE_BPS=25
SPYDER_EXECUTION_MAX_FILL_LATENCY_MS=2500
SPYDER_EXECUTION_MAX_PARTIAL_FILL_RATIO=0.40
SPYDER_EXECUTION_MAX_REJECT_RATE_5M=0.08
SPYDER_EXECUTION_DEGRADE_SIZE_MULTIPLIER=0.50
SPYDER_EXECUTION_HALT_ON_QUALITY_BREACH=true

# Event-risk clock
SPYDER_EVENT_CLOCK_ENABLED=true
SPYDER_EVENT_CLOCK_SOURCES=calendar+manual
SPYDER_EVENT_CLOCK_HIGH_IMPACT_ONLY=true
SPYDER_EVENT_CLOCK_BLACKOUT_PRE_MINUTES=30
SPYDER_EVENT_CLOCK_BLACKOUT_POST_MINUTES=30
SPYDER_EVENT_CLOCK_MAX_SIZE_MULTIPLIER_DURING_EVENT=0.25
SPYDER_EVENT_CLOCK_ALLOWLIST_STRATEGIES=

# Escalation logic
SPYDER_ESCALATION_WARN_ON_SINGLE_BREACH=true
SPYDER_ESCALATION_DEGRADE_ON_TWO_BREACHES=true
SPYDER_ESCALATION_HALT_ON_THREE_BREACHES=true
SPYDER_ESCALATION_SUSTAINED_BREACH_MINUTES=10
```

#### Suggested Parsing / Precedence

1. Load YAML defaults first.
2. Override with ENV values for deployment-specific tuning.
3. Validate numeric ranges at startup (fail fast on invalid values).
4. Emit an effective-config snapshot to logs at boot for auditability.

### 3E) Startup Validation Rules (Fail-Fast)

Use these validation rules before enabling autonomous trading. Any `ERROR` rule failure should block startup in live mode.

#### Liquidity Validation Rules

| Key | Type | Allowed Range | Severity on Violation |
|---|---|---|---|
| `liquidity.max_spread_pct` | float | `0.01` to `0.50` | ERROR |
| `liquidity.max_spread_abs` | float | `0.01` to `2.00` | ERROR |
| `liquidity.max_quote_age_ms` | int | `100` to `10000` | ERROR |
| `liquidity.min_top_of_book_size` | int | `1` to `1000` | WARN (if feed has no size support) else ERROR |
| `liquidity.min_open_interest` | int | `0` to `1000000` | ERROR |
| `liquidity.min_volume` | int | `0` to `1000000` | ERROR |
| `liquidity.min_oi_change_pct` | float | `-1.00` to `1.00` | WARN (optional metric) |

#### Execution Validation Rules

| Key | Type | Allowed Range | Severity on Violation |
|---|---|---|---|
| `execution.max_slippage_bps` | float | `1` to `200` | ERROR |
| `execution.max_fill_latency_ms` | int | `100` to `20000` | ERROR |
| `execution.max_partial_fill_ratio` | float | `0.00` to `1.00` | ERROR |
| `execution.max_reject_rate_5m` | float | `0.00` to `1.00` | ERROR |
| `execution.degrade_size_multiplier` | float | `0.10` to `1.00` | ERROR |
| `execution.halt_on_quality_breach` | bool | `true|false` | ERROR |

#### Event Clock Validation Rules

| Key | Type | Allowed Range / Set | Severity on Violation |
|---|---|---|---|
| `event_clock.enabled` | bool | `true|false` | ERROR |
| `event_clock.sources` | str | one of `calendar`, `manual`, `calendar+manual` | WARN (fallback to `manual`) |
| `event_clock.high_impact_only` | bool | `true|false` | ERROR |
| `event_clock.blackout_pre_minutes` | int | `0` to `240` | ERROR |
| `event_clock.blackout_post_minutes` | int | `0` to `240` | ERROR |
| `event_clock.max_size_multiplier_during_event` | float | `0.00` to `1.00` | ERROR |
| `event_clock.allowlist_strategies` | list[str] | each item must map to known strategy id | WARN (drop unknown ids) |

#### Cross-Field Consistency Rules

1. `execution.degrade_size_multiplier` must be less than or equal to `1.0` and greater than or equal to `event_clock.max_size_multiplier_during_event` when event mode is intended to be most restrictive.
2. If `execution.halt_on_quality_breach=true`, at least one of `execution.max_slippage_bps`, `execution.max_fill_latency_ms`, or `execution.max_reject_rate_5m` must be explicitly set.
3. If `event_clock.enabled=true`, both blackout windows (`pre` and `post`) cannot be zero simultaneously.

#### Startup Behavior Policy

1. Parse config and ENV.
2. Validate all keys against type and range rules.
3. Apply safe fallbacks only for `WARN` cases.
4. If any `ERROR` remains:
	- `paper` mode: start with automation disabled and show operator warning.
	- `live` mode: abort startup and require config correction.
5. Log a single startup validation report containing:
	- effective values,
	- warnings/fallbacks applied,
	- blocking errors (if any).

### 3F) Validation Function Pseudocode (Implementation Blueprint)

Suggested placement:
- Configuration load path in [Spyder/SpyderA_Core/SpyderA03_Configuration.py](Spyder/SpyderA_Core/SpyderA03_Configuration.py)
- Invoked before enabling automation/trading loops.

```python
def validate_autonomous_readiness_config(config: dict, mode: str) -> dict:
	"""
	Validate P0 autonomous-readiness config blocks.

	Returns:
		{
			"ok": bool,
			"effective": dict,
			"warnings": list[str],
			"errors": list[str],
		}
	"""
	effective = deepcopy(config)
	warnings = []
	errors = []

	# 1) Apply env overrides to effective config
	effective = apply_env_overrides(effective)

	# 2) Helper validators
	def require_bool(path):
		v = get_path(effective, path)
		if not isinstance(v, bool):
			errors.append(f"{path} must be bool")

	def require_int_range(path, lo, hi, severity="ERROR", fallback=None):
		v = get_path(effective, path)
		if not isinstance(v, int) or v < lo or v > hi:
			msg = f"{path} out of range [{lo}, {hi}]"
			if severity == "WARN" and fallback is not None:
				warnings.append(msg + f"; fallback={fallback}")
				set_path(effective, path, fallback)
			elif severity == "WARN":
				warnings.append(msg)
			else:
				errors.append(msg)

	def require_float_range(path, lo, hi, severity="ERROR", fallback=None):
		v = get_path(effective, path)
		if not isinstance(v, (int, float)) or float(v) < lo or float(v) > hi:
			msg = f"{path} out of range [{lo}, {hi}]"
			if severity == "WARN" and fallback is not None:
				warnings.append(msg + f"; fallback={fallback}")
				set_path(effective, path, fallback)
			elif severity == "WARN":
				warnings.append(msg)
			else:
				errors.append(msg)

	# 3) Liquidity rules
	require_float_range("autonomous_readiness.liquidity.max_spread_pct", 0.01, 0.50)
	require_float_range("autonomous_readiness.liquidity.max_spread_abs", 0.01, 2.00)
	require_int_range("autonomous_readiness.liquidity.max_quote_age_ms", 100, 10000)
	require_int_range("autonomous_readiness.liquidity.min_top_of_book_size", 1, 1000)
	require_int_range("autonomous_readiness.liquidity.min_open_interest", 0, 1_000_000)
	require_int_range("autonomous_readiness.liquidity.min_volume", 0, 1_000_000)
	require_float_range("autonomous_readiness.liquidity.min_oi_change_pct", -1.00, 1.00, severity="WARN")

	# 4) Execution rules
	require_float_range("autonomous_readiness.execution.max_slippage_bps", 1, 200)
	require_int_range("autonomous_readiness.execution.max_fill_latency_ms", 100, 20000)
	require_float_range("autonomous_readiness.execution.max_partial_fill_ratio", 0.00, 1.00)
	require_float_range("autonomous_readiness.execution.max_reject_rate_5m", 0.00, 1.00)
	require_float_range("autonomous_readiness.execution.degrade_size_multiplier", 0.10, 1.00)
	require_bool("autonomous_readiness.execution.halt_on_quality_breach")

	# 5) Event-clock rules
	require_bool("autonomous_readiness.event_clock.enabled")
	sources = get_path(effective, "autonomous_readiness.event_clock.sources")
	if sources not in {"calendar", "manual", "calendar+manual"}:
		warnings.append("autonomous_readiness.event_clock.sources invalid; fallback=manual")
		set_path(effective, "autonomous_readiness.event_clock.sources", "manual")
	require_bool("autonomous_readiness.event_clock.high_impact_only")
	require_int_range("autonomous_readiness.event_clock.blackout_pre_minutes", 0, 240)
	require_int_range("autonomous_readiness.event_clock.blackout_post_minutes", 0, 240)
	require_float_range("autonomous_readiness.event_clock.max_size_multiplier_during_event", 0.00, 1.00)

	# 6) Cross-field consistency
	degrade = get_path(effective, "autonomous_readiness.execution.degrade_size_multiplier")
	event_mult = get_path(effective, "autonomous_readiness.event_clock.max_size_multiplier_during_event")
	if isinstance(degrade, (int, float)) and isinstance(event_mult, (int, float)):
		if float(degrade) < float(event_mult):
			errors.append("execution.degrade_size_multiplier should be >= event_clock.max_size_multiplier_during_event")

	pre = get_path(effective, "autonomous_readiness.event_clock.blackout_pre_minutes")
	post = get_path(effective, "autonomous_readiness.event_clock.blackout_post_minutes")
	evt_enabled = get_path(effective, "autonomous_readiness.event_clock.enabled")
	if evt_enabled is True and pre == 0 and post == 0:
		errors.append("event_clock.enabled=true requires non-zero pre or post blackout window")

	# 7) Mode-specific fail policy
	ok = len(errors) == 0
	if not ok and mode == "paper":
		# paper can start in safe mode (automation disabled)
		set_path(effective, "automation.enabled", False)
		warnings.append("paper mode: blocking errors present, automation disabled")
		ok = True
	elif not ok and mode == "live":
		# live must fail fast
		ok = False

	return {
		"ok": ok,
		"effective": effective,
		"warnings": warnings,
		"errors": errors,
	}
```

#### Startup Hook (Suggested)

1. Load base config and `.env`.
2. Call `validate_autonomous_readiness_config(config, mode)`.
3. Emit a single structured startup report (`warnings`, `errors`, effective values).
4. If `ok=false` in live mode: abort startup before trading engine/bootstrap.
5. If paper-mode safe fallback was applied: start with automation disabled and UI warning banner.

## Notes
- MARKET OVERVIEW row membership comes from MARKET_SYMBOLS in Spyder/SpyderG_GUI/SpyderG05_TradingDashboard.py.
- Some metrics are direct quotes (Tradier), others are computed/derived (S07/S05/S01/S03/S12/S13).
- DXY is displayed as DXY but is sourced from Tradier UUP and remapped (`UUP -> DXY`) as an ETF proxy because Tradier does not provide a direct DXY index quote.
- The verification snapshot above reflects one live test run on 2026-04-25; values will drift with market conditions and daily dataset refresh timing.

## 4) Missing Feed Matrix (Implementation-Ready)

This matrix converts the remaining readiness gaps into concrete feed contracts.

| Priority | Missing Feed | Producer Module(s) | Primary Consumer Module(s) | Required Fields (Schema Keys) | Cadence | Fail Policy |
|---|---|---|---|---|---|---|
| P0 | Contract micro-liquidity | `SpyderC03_OptionChain`, `SpyderN03_OptionsChainManager`, `SpyderS07_CustomMetricsOrchestrator` | `SpyderF09_EntryFilters`, `SpyderB02_OrderManager`, `SpyderE01_RiskManager` | `symbol`, `expiry`, `strike`, `right`, `bid`, `ask`, `mid`, `spread_abs`, `spread_pct`, `quote_age_ms`, `bid_size`, `ask_size`, `top_of_book_size`, `open_interest`, `volume`, `oi_change_pct`, `snapshot_ts` | 1-5s intraday | Block entry on threshold breach |
| P0 | Execution quality telemetry | `SpyderB02_OrderManager`, `SpyderB40_TradierClient` | `SpyderE01_RiskManager`, `SpyderK04_ExecutionAnalytics`, `SpyderG05_TradingDashboard` | `order_id`, `strategy_id`, `symbol`, `decision_ts`, `submit_ts`, `ack_ts`, `fill_ts`, `decision_mid`, `submit_limit`, `avg_fill_price`, `slippage_bps`, `fill_latency_ms`, `partial_fill_ratio`, `reject_flag`, `reject_reason`, `cancel_replace_count`, `session_id` | Per order lifecycle event | Degrade size / halt per configured rules |
| P0 | Event-risk clock | `SpyderA04_Scheduler`, `SpyderS07_CustomMetricsOrchestrator` | `SpyderF09_EntryFilters`, `SpyderE16_CircuitBreakerProtocol`, `SpyderG05_TradingDashboard` | `event_id`, `event_type`, `importance`, `source`, `event_time_et`, `blackout_pre_minutes`, `blackout_post_minutes`, `state` (`pre`/`live`/`post`/`clear`), `allowed_strategies`, `max_size_multiplier`, `published_ts` | 1 min scheduler + immediate on transition | Hard block/reduce risk in blackout state |
| P1 | Vol surface structure | `SpyderN06_VolatilitySurfaceBuilder`, `SpyderN08_VolatilitySurface`, `SpyderS07_CustomMetricsOrchestrator` | `SpyderD31_StrategyOrchestrator`, `SpyderE09_VolatilityRiskManager`, `SpyderF10_MarketRegimeDetector` | `underlying`, `atm_iv_0dte`, `atm_iv_1dte`, `atm_iv_7dte`, `atm_iv_30dte`, `term_slope_0_7`, `term_slope_7_30`, `rr_25d`, `fly_25d`, `surface_confidence`, `surface_age_ms`, `snapshot_ts` | 30-60s | Disable vol-sensitive entries if stale/low confidence |
| P1 | Dealer-flow structure | `SpyderN09_GammaExposure`, `SpyderN11_OptionsGreeksFlow`, `SpyderS05_GEXDEXCalculator` | `SpyderF09_EntryFilters`, `SpyderD30_RegimeGatedSelector`, `SpyderE15_GreekLimitsManager` | `zero_gamma_level`, `spot_to_zero_gamma_pct`, `call_wall_levels`, `put_wall_levels`, `wall_confidence`, `net_gex`, `net_dex`, `vanna_pressure`, `charm_pressure`, `flow_imbalance_score`, `snapshot_ts` | 30-60s | Tighten entries when confidence low / pressure extreme |
| P1 | ES lead-lag context | `SpyderC11_FuturesBasis`, `SpyderC15_MicrostructureAnalyzer`, `SpyderS07_CustomMetricsOrchestrator` | `SpyderF14_MarketMicrostructure`, `SpyderF09_EntryFilters`, `SpyderD04_ZeroDTE` | `es_price`, `spy_price`, `basis_bps`, `lead_lag_ms`, `es_impulse_score`, `confirm_direction`, `confirm_confidence`, `snapshot_ts` | 1-5s | Require confirmation in fast regime |
| P2 | Sector breadth expansion | `SpyderC13_IndexComponents`, `SpyderC22_FactorDataProvider`, `SpyderS07_CustomMetricsOrchestrator` | `SpyderF10_MarketRegimeDetector`, `SpyderD30_RegimeGatedSelector`, `SpyderG05_TradingDashboard` | `breadth_defensive`, `breadth_cyclical`, `breadth_spread`, `sector_adv_dec`, `sector_momentum_dispersion`, `participation_score`, `snapshot_ts` | 30-60s | Reduce risk on low participation/dispersion stress |
| P2 | Data quality/provenance SLO feed | `SpyderS07_CustomMetricsOrchestrator`, `SpyderM01_SystemMonitor` | `SpyderE01_RiskManager`, `SpyderG05_TradingDashboard`, `SpyderK05_RiskReport` | `metric_name`, `freshness_ms`, `completeness_pct`, `source` (`tradier`/`massive`/`fred`/`yfinance`/`simulated`), `fallback_active`, `quality_score`, `slo_status`, `evaluated_ts` | 10-30s | Disable affected strategy edges when SLO fails |

### 4A) Unified Feed Envelope (Recommended)

Use a common envelope for all added feeds so routing and persistence are uniform:

```json
{
	"feed": "liquidity|execution|event_clock|vol_surface|dealer_flow|lead_lag|breadth|quality",
	"version": "1.0",
	"mode": "paper|live|backtest",
	"session_id": "string",
	"published_ts": "2026-04-25T09:31:12.123-04:00",
	"data": {
		"...feed-specific fields...": "..."
	}
}
```

### 4B) Implementation Sequence (Delta from Section 3)

1. Add `execution` feed contract first (fastest path to measurable live safety).
2. Add `liquidity` feed contract and wire hard blocks in `F09` + `B02`.
3. Add `event_clock` feed transitions and enforce blackout policy.
4. Add `vol_surface` + `dealer_flow` for improved signal quality.
5. Add `quality` SLO feed and gate all strategy edges on freshness/provenance.
