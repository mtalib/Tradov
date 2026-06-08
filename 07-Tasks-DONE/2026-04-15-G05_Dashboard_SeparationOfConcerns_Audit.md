# G05 Trading Dashboard — Separation-of-Concerns Audit

**Date:** 2026-04-15
**File audited:** [TradovG05_TradingDashboard.py](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py)
**Scope:** Identify work the dashboard performs in-line that belongs in dedicated modules.

---

## Guiding principles for a trading GUI module

A trading GUI should be a **thin observer and dispatcher** — nothing more.
Every finding in this report is an instance of one of these principles being
violated. They are the standard the remediation work should be measured
against.

1. **Display, don't compute.** The GUI renders state it receives. It never
   calculates P&L, Greeks, signals, VWAP, or put/call ratios itself. If a
   number appears on screen, some other module produced it.
2. **Dispatch, don't decide.** Buttons translate user intent into a single
   call against a service (`order_manager.close(id)`, `engine.start()`). The
   GUI never decides *how* to close a position, which side to use, or what
   expiry to roll to.
3. **No I/O of its own.** No broker API calls, no market-data fetches, no
   database reads, no file writes, no `.env` loading, no HTTP, no `yfinance`.
   The GUI subscribes to feeds and publishes commands — that's it. If you
   can't run the system headless with the GUI removed, the GUI owns too much.
4. **No business state.** Positions, orders, cash, risk limits, and strategy
   lifecycle live in services. The GUI caches only what it needs to paint
   the current frame and is safe to close and reopen at any moment without
   losing state.
5. **Async-safe and non-blocking.** The UI thread never blocks on network,
   disk, or computation. Long work runs in workers/services and returns via
   signals. A frozen GUI during a broker timeout is a bug in *where the call
   lives*, not in the timeout.
6. **Fail visibly, fail safely.** When a service is down, the GUI shows it
   (red indicator, disabled button, explicit status) but never silently falls
   back to fake data or bypasses a safety gate. Degraded state must be
   obvious to the trader.
7. **Safety gates are UX, not logic.** Confirmation dialogs, typed-phrase
   gates ("I CONFIRM LIVE TRADING"), and disabled buttons belong in the GUI
   because they capture *human intent*. But the **enforcement** — "can this
   order actually be sent?" — lives in the order manager. The GUI asks; the
   service decides.
8. **One source of truth per datum.** Price, position qty, account equity —
   each has exactly one owner service. The GUI reads it, never caches a
   second copy, and never lets two widgets compute the same value
   independently.
9. **Replaceable.** You should be able to swap the Qt dashboard for a web
   UI, a TUI, or a headless logger without rewriting trading logic. If
   swapping the GUI means rewriting the paper engine, the paper engine is
   in the wrong place.
10. **Testable without a screen.** Services should be unit-testable with no
    Qt, no display, no event loop. The GUI layer is tested separately with
    mock services. If you can't test "close strategy X" without instantiating
    `QMainWindow`, the logic is misplaced.

**The one-line test:** *If I delete the GUI file, does the trading system
still trade correctly when driven by a script?* If no, the GUI has absorbed
responsibilities that belong elsewhere — which is exactly what this audit
found.

---

## Summary

`TradovG05_TradingDashboard.py` is ~3,800 lines and acts as a GUI **and** a
data-fetching engine, trading engine, indicator engine, order manager, and
analytics loader. A GUI module should *display* state and *dispatch* user
actions; the bulk of this file does neither. Every item below is functionality
that should live in a non-GUI module so the dashboard can be swapped, tested
headlessly, or replaced without losing business logic.

---

## 1. Market-data fetching (CRITICAL)

### 1a. Full Tradier quote/balance/chain/bars fetch inside the worker
- **Location:** `ThreadSafeMarketDataWorker._fetch_live_data_from_tradier` —
  [L569-L738](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L569-L738)
- **What it does:** Instantiates `TradierClient` directly, fetches quotes for
  ~14 symbols, pulls account balances (with dual paper/live routing logic),
  fetches the SPY options chain, computes CPC, fetches 5-min bars, and writes
  two JSON cache files.
- **Should live in:** `TradovC_MarketData/` (quote fetching & caching) and
  `TradovB_Broker/TradovB40_TradierClient` wrappers. The GUI should subscribe
  to a `MarketDataFeed` protocol and receive dict updates — nothing more.

### 1b. Duplicate fast-path fetcher
- **Location:** `_fetch_quotes_fast` — [L740-L865](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L740-L865)
- **Problem:** Re-implements the same Tradier fetch logic with a subset of
  symbols, merges into the same JSON file, and additionally pulls `$TICK`,
  `$ADD`, `$TRIN` from **yfinance** via a throttled counter. The GUI should
  never import `yfinance` or `dotenv`.
- **Should live in:** `TradovC_MarketData/` as a `MarketInternalsFeed`
  provider with yfinance adapter isolated behind the provider protocol.

### 1c. Symbol remap table hardcoded in worker
- **Location:** `_sym_remap` dicts at [L668](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L668) and
  [L782](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L782)
- **Problem:** `VIX9D→VXV`, `UUP→DXY` adapter logic is duplicated in two places
  inside the GUI. Any new proxy will drift.
- **Should live in:** A single `SymbolAdapter` in `TradovC_MarketData/`.

### 1d. Persistent JSON cache written from GUI
- **Problem:** The worker writes `live_data.json` and `spy_5min_chart.json`
  directly. Storage is an `H_Storage` concern; the dashboard is both producer
  and consumer of its own side-channel.
- **Should live in:** `TradovH_Storage/` or the market-data cache layer.

---

## 2. CPC / PCALL computation (HIGH)

- **Location:** [L679-L726](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L679-L726)
- **What it does:** Fetches SPY option expirations, picks the nearest, pulls
  the full chain, sums put vs call volume, derives CPC ratio and change, and
  stamps `PCALL` as an alias.
- **Problem:** This is a derived market metric — it belongs next to the other
  custom metrics (GEX/DEX/DIX/SWAN) that **are** correctly produced by
  `TradovS07_CustomMetricsOrchestrator`. It is the odd one out.
- **Should live in:** `TradovS_Signals/` as a `CPCCalculator` feeding S07.

---

## 3. Chart indicators computed in `update_chart` (HIGH)

- **Location:** `update_chart` — [L2130-L2250](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L2130-L2250)
- **What the view does:**
  - Computes Fibonacci pivot points (P, R1/R2/R3, S1/S2/S3) from loaded bars.
  - Computes 20-period SMA.
  - Computes session VWAP from typical price × volume.
- **Problem:** These are indicator calculations, not rendering. They belong
  wherever the rest of TRADOV's technical analysis lives (there is almost
  certainly an `TradovT_TechnicalAnalysis` or similar — the GUI should ask for
  a precomputed series).
- **Should live in:** A `ChartIndicators` service that returns a dataclass of
  `(pivots, ma20, vwap)` given an OHLCV frame.

---

## 4. Embedded paper trading engine (CRITICAL)

- **Location:** `_PaperTradingWorker` — [L1470-L1760](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L1470-L1760)
- **What it does:** Full trading engine inside the GUI file:
  - Dual-MA momentum strategy (`_generate_signal`)
  - Order execution simulation (`_execute_paper_buy`, `_execute_paper_sell`)
  - Position MTM, cash, realized/unrealized P&L, peak equity, max drawdown
  - Direct Tradier polling loop for SPY prices
- **Problem:** The docstring at the top of the file explicitly claims paper
  trading is delegated to **`TradovR02_PaperEngine`**, yet the real
  implementation is a private class in the GUI module. This is the most
  significant violation in the file.
- **Should live in:** `TradovR_Trading/TradovR02_PaperEngine`. The GUI should
  instantiate it and wire signals only.

---

## 5. Order placement & close logic (HIGH)

### 5a. `close_strategy` builds OCC symbols and submits multileg orders
- **Location:** [L3280-L3430](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L3280-L3430)
- **What it does:** Parses UI leg dicts, infers expiry year from current
  month, maps "Sell Put"/"Buy Call" strings to `OrderSide` enums, builds OCC
  symbols via `build_option_symbol`, and calls `place_multileg_order`
  directly on the Tradier client.
- **Problem:** Option-symbol construction, side inference, and expiry
  rollover logic are trading concerns, not view concerns. The view should
  call `order_manager.close_strategy(strategy_id)`.
- **Should live in:** An `OrderManager` / `StrategyManager` in
  `TradovR_Trading/`.

### 5b. `_fetch_pending_orders`, `_cancel_orders`, `_refresh_positions_table`
- **Location:** [L2860-L3050](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L2860-L3050)
- **Problem:** Directly hits `client.get_orders()`, `client.get_positions()`,
  `client.cancel_order()`. Parses the nested Tradier response shape
  (`orders_node.get("order", [])` + dict-vs-list normalization) inside the GUI.
- **Should live in:** A broker-facing adapter returning typed
  `Order`/`Position` objects.

---

## 6. Account balance dual-routing (MEDIUM)

- **Location:** [L589-L635](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L589-L635)
- **Problem:** The worker contains the business rule "paper mode balances
  come from sandbox credentials, live from production credentials," including
  falling back through `total_equity → total_cash → option_buying_power →
  buying_power`. This is account-management logic, not UI.
- **Should live in:** `TradovB_Broker/` account service.

---

## 7. Environment & secrets handling (MEDIUM)

- **Location:** Every Tradier fetch method calls
  `load_dotenv(override=True)` and reads `TRADIER_API_KEY`,
  `TRADIER_ACCOUNT_ID`, `TRADIER_ENVIRONMENT`, `TRADIER_SANDBOX_*`,
  `TRADING_MODE`, `MARKET_DATA_PROVIDER` inline — repeatedly, on each poll.
- **Problem:** Config reading is scattered; secrets flow through the GUI
  process.
- **Should live in:** A single `Config` / `Settings` object loaded once at
  startup and injected.

---

## 8. Circuit-breaker manipulation (MEDIUM)

- **Location:** `_heartbeat_check` — [L532-L545](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L532-L545)
- **What it does:** Imports `tradier_breaker` / `massive_breaker` singletons
  and calls `_tradier_breaker.reset()` when a heartbeat succeeds.
- **Problem:** The GUI is reaching into a utility singleton to mutate
  cross-cutting state. Breaker reset policy should be owned by whoever
  *trips* the breaker.
- **Should live in:** `TradovU41_CircuitBreaker` itself (auto-reset on
  successful health check) or the health-check service.

---

## 9. Performance analytics loaded inline (LOW)

- **Location:** `_refresh_pnl_table` — [L3180-L3195](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L3180-L3195)
- **Problem:** Imports `TradovH07_PerformanceAnalytics` inside the slot,
  instantiates it, and calls `get_summary_stats()` every time metrics update.
  Imports-inside-methods usually indicate a missing service boundary.
- **Should live in:** Injected at dashboard construction; the slot should
  just read from a cached stats object.

---

## 10. Simulation data generation (LOW — extraction only)

- **Location:** `_init_simulation_data` / `_update_simulation_data` —
  [L866-L960](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L866-L960)
- **Context:** TRADOV exposes **SIMULATED** as a first-class feed choice
  (alongside Tradier and Massive) so the UI can be exercised when no live
  feed is available. The logic itself is legitimate — the issue is purely
  *where it lives*.
- **Should live in:** `TradovC_MarketData/SimulationFeedProvider`
  implementing the same `MarketDataFeed` protocol as the real providers.
  The GUI selects it the same way it selects Tradier or Massive; it does
  not contain the random walk or the hardcoded base prices itself.
- **UX requirement:** Whichever module owns simulated data, the dashboard
  must display an unmistakable **SIMULATED** badge whenever that feed is
  active — see the note at the end of §11 on distinguishability.

---

## Impact summary

| Concern | Severity | LOC moved | Enables |
|---|---|---|---|
| Market-data fetcher (§1, §2) | Critical | ~400 | Headless tests, feed swap |
| Paper engine (§4) | Critical | ~290 | Matches docstring promise; real R02 module |
| Order manager (§5) | High | ~200 | Strategy lifecycle outside GUI |
| Chart indicators (§3) | High | ~120 | Reusable TA service |
| Config/secrets (§7) | Medium | ~30 | One load point, testable |
| Breaker reset (§8) | Medium | ~15 | Policy owned by breaker |
| Analytics load (§9) | Low | ~15 | DI cleanup |

Total: roughly **1,000 lines** of non-view code currently embedded in the
dashboard. After extraction, `TradovG05_TradingDashboard.py` should shrink to
widgets, layout, Qt signal wiring, and slot handlers that call service
methods — everything else should be replaceable behind an interface.

---

## Recommended next steps

1. **Verify `TradovR02_PaperEngine` exists.** The docstring claims it; if it
   does, `_PaperTradingWorker` should be deleted and the GUI should import
   R02. If R02 doesn't exist, create it by lifting `_PaperTradingWorker`
   verbatim — this is the highest-value extraction.
2. **Define a `MarketDataFeed` protocol** (quotes + chain + bars + internals)
   and move `_fetch_live_data_from_tradier` / `_fetch_quotes_fast` behind it.
   Drop `yfinance` and `dotenv` imports from the GUI module entirely.
3. **Move CPC into S07** so all custom metrics have one owner.
4. **Extract `ChartIndicators`** — trivial win; the functions are pure.
5. **Create an `OrderManager`** that owns `close_strategy`, pending-order
   fetch, cancellation, and OCC-symbol construction. The GUI calls it with
   a strategy ID and gets signals back.

---

# Second-pass findings (2026-04-15)

A thorough re-sweep of the full 6,738-line file surfaced a second cluster
of violations — some more deceptive than the first pass, because they
fabricate display state rather than merely mislocate logic. The file is
**actually 6,738 lines**, not the ~3,800 estimated in the first pass.

---

## 11. Fake UI content presented as real (CRITICAL)

This is the most serious category — the GUI manufactures data that looks
authentic to the trader. None of it should survive into a shipping build.

### 11a. Rotating fake AI activity log
- **Location:** `generate_automation_activity` —
  [L5678-L5703](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L5678-L5703)
- **What it does:** A QTimer rotates through a hardcoded list of 15
  plausible-sounding strings ("Scanning options chains for SPY",
  "Analyzing volatility surface patterns", "Monitoring delta-gamma hedging
  flows", …) and writes one to the automation log every tick.
- **Problem:** The log pretends an AI is actively analyzing markets. No
  analysis is occurring. A trader watching the log has no way to know the
  system is idle.
- **Should live in:** Delete entirely. Automation log entries must come
  from a real automation service emitting real events.

### 11b. Fake test strategies loaded at startup
- **Location:** `load_test_data` —
  [L5744-L6172](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L5744-L6172)
  — called unconditionally from the constructor at
  [L2170](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L2170).
- **What it does:** Loads three hardcoded fake strategies (IRON CONDOR,
  COVERED CALL, IRON BUTTERFLY) with fake timestamps, fake legs, fake
  P&L, fake strikes, into the positions tree on every startup.
- **Problem:** A freshly-launched dashboard shows fabricated open
  positions. This is the single most dangerous display bug in the file —
  a trader could act on positions that do not exist.
- **Should live in:** Delete entirely. Positions come from the broker.

### 11c. Hardcoded-green Prometheus indicators
- **Location:** `update_prometheus_metrics` —
  [L5717-L5742](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L5717-L5742)
- **What it does:** A QTimer forces every system component indicator,
  every client indicator, and every internal-module indicator to the
  "positive" (green) color, regardless of actual health state. Only
  `custom_metrics` is hardcoded yellow.
- **Problem:** Violates principle #6 ("Fail visibly"). The health panel
  always reads green, so a trader cannot see when a subsystem fails. This
  is worse than no indicator at all.
- **Should live in:** Each indicator should subscribe to a health-check
  signal from the component it represents and update only on real events.

### 11d. Greeks stuck at 0.0
- **Location:** `update_greek_risks` —
  [L5705-L5715](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L5705-L5715)
- **What it does:** A QTimer writes 0.0 to delta/gamma/theta/vega bars
  every tick. The docstring admits "shows 0.0 until live position data is
  wired."
- **Problem:** The *timer* is the smell — periodically overwriting display
  state with zeros is worse than showing "—" once. When the SIMULATED
  feed is active, Greeks should come from the simulation provider
  (computed from the simulated positions), not from a hardcoded 0.0
  writer in the view. When Tradier/Massive is active, they should come
  from the real portfolio.
- **Should live in:** A `PortfolioGreeks` service that subscribes to
  whichever feed/positions source is active. If neither is available,
  the widget shows "—", not a fabricated number.

### 11e. Hardcoded market-regime & strategy labels
- **Problem:** Several places in the dashboard display strings like "Low
  Volatility - Range Bound" and "Iron Condor" as the current market
  regime/recommended strategy. These are not derived from any regime
  detector — they are literals.
- **Should live in:** A regime-detection service (one already exists per
  the April-14 audit note about "regime detector sprawl"). The GUI should
  render whatever label that service publishes.

### Note on the SIMULATED feed

TRADOV has a legitimate **SIMULATED** feed option that produces
plausible-looking data without a live connection. That is *not* fake
content in the §11 sense — it's a real provider behind the
`MarketDataFeed` protocol, selected explicitly by the user.

The distinction that matters:

- ✅ **Legitimate:** A `SimulationFeedProvider` that publishes quotes,
  bars, chain, positions, and Greeks through the same interface as
  Tradier/Massive. The GUI doesn't know or care it's simulated.
- ❌ **Fake content (§11a–c, §11e):** Hardcoded strings or widget values
  fabricated inside the GUI module, unrelated to any selected feed.
  These remain deletions regardless of whether SIMULATED is active.

**Hard UX requirement:** whenever the SIMULATED feed is active, the
dashboard must display an unmistakable badge — e.g., a large amber
"SIMULATED" chip in the toolbar, mode-indicator copy changed to
"SIMULATED DATA", and every panel that shows prices tinted or labeled
accordingly. The one-second test: *a trader glancing at the screen
must recognize within one second that no real money and no real market
data are in play.* If they can't, the simulated mode becomes a
deception risk even though its data pipeline is legitimate.

---

## 12. `_paper_worker` attribute-access bug (HIGH — real defect)

- **Location:** `_start_paper_trading` creates `self._paper_worker` at
  [L5051](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L5051);
  `_stop_paper_trading` reads it unguarded at
  [L5068](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L5068);
  `stop_trading` reads it at
  [L5252](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L5252).
- **Problem:** `self._paper_worker` is never initialized in `__init__`.
  Calling `stop_trading` before `_start_paper_trading` (e.g., if a user
  clicks STOP while paper engine failed to start, or on a window close
  before trading began) raises `AttributeError`. Same for
  `self._paper_thread`.
- **Fix:** Initialize both to `None` in `__init__`, or guard with
  `getattr(self, "_paper_worker", None)`.
- **Severity:** Real runtime crash path — not a style issue.

---

## 13. Trading calendar embedded in GUI module (HIGH)

- **Location:** Module-level constants and functions —
  [L351-L370](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L351-L370):
  `MARKET_OPEN_TIME`, `MARKET_CLOSE_TIME`, `TRADIER_CONNECT_TIME`,
  `REALTIME_QUOTE_MAX_AGE_SECONDS`, `is_market_hours()`,
  `is_tradier_window()`.
- **Problem:** Trading-session arithmetic is used *everywhere* in the
  system (paper engine, broker adapter, strategy runner). Defining it in
  the GUI means every non-GUI caller has to import from
  `TradovG_GUI/TradovG05_TradingDashboard.py` — a circular-dependency
  magnet.
- **Should live in:** `TradovU_Utilities/` or
  `TradovC_MarketData/TradingCalendar`.

---

## 14. Index-proxy math duplicated in GUI (HIGH)

- **Location:** `update_toolbar_with_real_data` —
  [L2449-L2522](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L2449-L2522)
  AND the module-level helper `update_toolbar_with_real_data_helper` —
  [L6451](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L6451).
- **What it does:** Hardcodes the proxies SPX = SPY × 10, COMP = QQQ ×
  37.5, DJI = DIA × 100, RUT = IWM × 10, with inline comments explaining
  Tradier index-feed quirks (delayed $DJI, missing IXIC, RUT change=None).
  The IWM→RUT change-percent borrowing logic is also in the view.
- **Problem:** This is market-data adapter logic. If Tradier fixes $DJI
  tomorrow, or if a different broker provides real indices, two copies of
  the table must change. The trader-facing number comes from arithmetic
  the GUI invented.
- **Should live in:** `TradovC_MarketData/IndexProxyAdapter` — returns a
  proper `QuoteDict` for `SPX/COMP/DJI/RUT` regardless of feed. The GUI
  reads `live_data["SPX"]` and renders.

---

## 15. Duplicate module-level "real data patch" functions (HIGH)

- **Location:**
  - `apply_real_data_patch_to_dashboard(dashboard, data_file)` —
    [L6332](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L6332)
  - `update_toolbar_with_real_data_helper(dashboard, live_data)` —
    [L6451](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L6451)
- **Problem:** These are module-level functions that take the dashboard
  as a parameter and mutate its widgets. They duplicate instance methods
  (`update_toolbar_with_real_data`) and introduce a second injection
  pathway for live data — the in-worker signal and the file-polling
  module function race each other. Called from
  [L6440](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L6440) and
  [L6557](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L6557).
- **Should live in:** Delete. One signal path, one code path.

---

## 16. Parallel connection-state mirrors (HIGH)

- **Location:** `determine_data_status` —
  [L5358](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L5358)
  and multiple fields on the dashboard instance.
- **Problem:** The GUI maintains several separately-mutable flags that
  represent the same underlying truth:
  - `self.api_connected` (broker-exec link)
  - `self.mkt_data_connected` (market-data link)
  - `self.connection_info.api_connected` (duplicate of the first)
  - `self._freshest_live_data_timestamp` + `REALTIME_QUOTE_MAX_AGE_SECONDS`
    staleness check inside `determine_data_status`
- Code in several slots updates one flag without the others. Staleness
  detection (how old is the latest quote, is the feed live?) is a
  feed-provider concern, not a view concern.
- **Should live in:** A single `ConnectionState` published by the feed
  provider. The GUI subscribes and reads.

---

## 17. Hardcoded risk parameters (HIGH)

- **Location:** `load_default_risk_parameters` —
  [L6173](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L6173),
  called from [L2171](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L2171).
- **Problem:** Max position size, max daily loss, stop loss, Kelly
  fraction, etc. are written as literals into the GUI's risk-panel
  widgets at startup. Risk limits are an **enforcement** concern owned
  by the order manager / risk service (principle #7: "safety gates are
  UX, not logic").
- **Should live in:** `TradovR_Trading/RiskManager` — publishes current
  limits; GUI reads to populate the panel.

---

## 18. Mode-switch policy mixed with UX (HIGH)

- **Location:** `_on_mode_btn_clicked` —
  [L4625-L4800+](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L4625)
- **What it does:** Implements the full PAPER↔LIVE state machine: checks
  `trading_active`, fetches pending orders from the broker, cancels them,
  checks open positions, requires typed confirmation, and finally flips
  `self.trading_mode`. Dialogs and decisions are interleaved.
- **Problem:** Per principle #7, the *prompts* belong in the GUI but the
  *gates* belong in the trading service. An `OrderManager.can_switch_to(
  LIVE)` method should return a list of blockers. The GUI renders them as
  dialogs.
- **Should live in:** Move the `trading_active / pending_orders /
  open_positions` checks into the trading service; GUI only handles the
  typed confirmation UX.

---

## 19. Dead / legacy connection code (HIGH)

Several code paths are clearly vestigial and should be deleted before
they confuse future readers:

- `check_and_connect_gateway` — references a "gateway" concept from a
  prior IBKR integration (removed per commit `cde9c3c`).
- `create_api_connection` — imports nothing real, pure stub.
- `_deprecated_gateway_*` methods — name tells the story.
- Module-level `apply_real_data_patch_to_dashboard` +
  `update_toolbar_with_real_data_helper` — see §15.
- `TradovErrorHandler` imported at top of file but not referenced.
- Simulation data with hardcoded Feb-2026 prices (SPY 585.25, etc.) in
  `_init_simulation_data` (already noted in §10 but worth reiterating:
  the constants are stale and should either come from a config file or
  be removed with the whole sim path).

**Should live in:** `git rm`. Dead code that references removed
subsystems actively misleads anyone reading the file.

---

## 20. Silent exception swallowing (HIGH)

- **Pattern:** Multiple `except Exception: pass` and
  `except Exception as e: self.logger.debug(…)` blocks throughout the
  worker (e.g., [L2521-L2522](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L2521-L2522)).
- **Problem:** A failing toolbar update or feed parse is reduced to a
  DEBUG log the trader never sees. Combined with §11c's all-green
  indicators, the system actively hides failures. The worker also has an
  `_error_count` counter that *suppresses* error logging after N
  failures — the opposite of what a trading surface should do.
- **Should live in:** Errors in feed parsing must reach a health channel
  that turns the relevant indicator red. Exceptions in view code should
  at minimum log at WARNING, never DEBUG.

---

## 21. S07 orchestrator lifecycle owned by GUI (HIGH)

- **Location:** `_on_custom_metrics_updated` slot + the `QTimer.singleShot`
  chain that starts the custom-metrics orchestrator.
- **Problem:** The GUI starts, stops, and polls
  `TradovS07_CustomMetricsOrchestrator`. The slot also applies hardcoded
  unit scaling (GEX × 1e9, DEX × 1e6) before displaying — unit conversion
  is a metric-layer concern, and the orchestrator should publish values
  in display units or ship a formatter.
- **Should live in:** Orchestrator runs as a service under the app's
  service container, not under the dashboard. GUI subscribes to its
  signal and renders.

---

## 22. `_heartbeat_check` is a 100-line god-method (HIGH)

- **Location:** `_heartbeat_check` —
  [L559](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L559) onward.
- **Problem:** Single method mixes: market-hours check, Tradier probe,
  circuit-breaker reset (§8), staleness check, indicator-color update,
  feed-provider selection, and log emission. Each of those is a separate
  responsibility.
- **Should live in:** A `HealthMonitor` service that emits
  `health_changed(component, state)` signals. GUI subscribes and colors
  indicators. Breaker reset moves to the breaker module.

---

## 23. File I/O from the GUI thread (HIGH)

- **Pattern:** `update_with_real_data` and the
  `apply_real_data_patch_to_dashboard` path both read JSON cache files
  from the GUI thread. The worker also writes them. Hardcoded paths are
  duplicated at module scope and inside worker methods.
- **Problem:** Principle #5 (non-blocking UI) and principle #3 (no I/O
  of its own). A slow disk or a held lock freezes the UI.
- **Should live in:** The file cache is a market-data storage concern.
  The GUI never touches the filesystem.

---

## 24. Context-menu action stubs (MEDIUM)

- **Location:** `_on_close_position`, `_on_roll_position`,
  `_on_adjust_position` — [L3835-L3850](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L3835-L3850)
- **Problem:** These slots only call `self.logger.info("… requested")`.
  The right-click menu invites the trader to take an action that silently
  does nothing. Either wire them to the real order manager or remove
  them from the menu.
- **Should live in:** `OrderManager.close_position(strategy_id)`.
  GUI's slot becomes a one-liner.

---

## 25. Manual log ring-buffer (MEDIUM)

- **Pattern:** `add_system_log` and `add_automation_log` manually trim
  the log widget to a max size. This is a reasonable thing to do, but
  the trimming policy and max-size constants are duplicated between the
  two methods and should be factored into a `RingLogWidget` subclass.
- **Should live in:** Widget-level concern — acceptable in the GUI but
  deserves its own small class.

---

## 26. App-wide theme injection from dashboard class (MEDIUM)

- **Location:** `setup_white_tooltips` —
  [L6247](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L6247),
  called from [L2182](../Tradov/TradovG_GUI/TradovG05_TradingDashboard.py#L2182).
- **Problem:** The dashboard sets a **QApplication-wide** stylesheet
  from its own constructor. Two dashboards in the same process would
  fight; a future dialog that styled itself would be overridden. Theme
  is an app-level concern.
- **Should live in:** The Qt app bootstrap (wherever `QApplication` is
  created). The dashboard gets a styled app, not the other way around.

---

## Updated impact summary

### Re-baseline note (2026-04-16)

The live file was re-checked against this audit before Phase 1 cleanup work
continued. Several items in the original quick-win list had already been fixed
or deleted in the current codebase, so the table and priority list below must be
read as a re-baselined view, not a verbatim carry-forward of the first pass.

What changed during re-validation:

- The `_paper_worker` / `_paper_thread` initializer defect from §12 is no longer
  active; both are already initialized in `__init__`.
- The specific duplicate helper / patch targets called out in §15 were not found
  in the current file.
- Several legacy dead-code anchors from §19 were already absent; the remaining
  low-risk cleanup was narrower and centered on deceptive fallback text and
  misleading automation/status language.
- The immediate integrity fix set was reduced to truthful HMM/SKEW fallback
  dialogs, truthful automation log text, removal of an unused `random` import,
  removal of an obsolete client-manager stub block, and removal of the default
  fabricated simulation baseline message.

| Concern | Severity | Notes |
|---|---|---|
| Fake UI content (§11) | **High** | The current file no longer matches the original worst-case description; the remaining deceptive fallback/log strings were the real Phase 1 integrity target and have now been cleaned up. |
| Market-data fetcher (§1, §2) | Critical | First-pass finding |
| Paper engine embedded (§4) | Critical | First-pass finding |
| `_paper_worker` crash (§12) | Resolved | Historical finding; the current file already initializes `_paper_worker` and `_paper_thread` to `None`. |
| Trading calendar in GUI (§13) | High | Circular-dep magnet |
| Index-proxy math (§14) | High | Display data invented in view |
| Duplicate "patch" functions (§15) | Stale | The specific duplicate patch/helper targets from the first pass were not present in the current file during re-baselining. |
| Connection-state mirrors (§16) | High | Multiple sources of truth |
| Hardcoded risk params (§17) | High | Enforcement logic in view |
| Mode-switch policy (§18) | High | Gates not separated from UX |
| Dead/legacy code (§19) | Medium | Some legacy targets were already gone; the remaining low-risk cleanup was limited to obsolete stubs and misleading strings. |
| Silent exception swallowing (§20) | High | Hides failures |
| S07 lifecycle (§21) | High | Service owned by view |
| `_heartbeat_check` god-method (§22) | High | 100-line mixed responsibility |
| File I/O from GUI (§23) | High | UI-thread disk access |
| Order manager (§5) | High | First-pass finding |
| Chart indicators (§3) | High | First-pass finding |
| Context-menu stubs (§24) | Medium | Right-click does nothing |
| Log ring-buffer (§25) | Medium | Minor factoring |
| Theme injection (§26) | Medium | App-level concern in view |
| Config/secrets (§7) | Medium | First-pass finding |
| Account dual-routing (§6) | Medium | First-pass finding |
| Breaker reset (§8) | Medium | First-pass finding |
| Analytics import (§9) | Low | First-pass finding |
| Simulation data (§10) | Low | First-pass finding |

The original shrink estimate is directionally useful, but the deletion-first
phase should be recalculated from the live file rather than from stale helper
targets. The remaining work is still substantial, but the next pass should be
driven by current service-boundary violations, not by assuming all earlier
quick wins are still present.

---

## Priority order for remediation

The order below reflects both *severity* and *prerequisite chains* — do
the deletions before the extractions, because deletion shrinks the
surface area that extraction has to preserve.

1. **Finish the integrity pass from the live file.** Treat deceptive fallback
  dialogs, misleading automation/status text, and fabricated default-state UI
  messages as the first cleanup class. Do not assume the stale helper names
  from §11/§15/§19 still exist.
2. **Re-audit connection-state ownership (§16)** against the current file and
  identify the smallest path to a single source of truth for API/data/trading
  status.
3. **Extract §13 trading calendar and §23 file I/O** into service/util layers.
  These are still concrete non-GUI responsibilities in the dashboard.
4. **Verify / create `TradovR02_PaperEngine`** (first-pass §4) and move
  `_PaperTradingWorker` into it.
5. **Create `MarketDataFeed` protocol** (first-pass §1) and move the
  Tradier fetch, any remaining index-proxy math (§14), and JSON cache I/O
  (§23) behind it.
6. **Create `HealthMonitor`** and move `_heartbeat_check` (§22),
  circuit-breaker reset (first-pass §8), and indicator coloring into it.
7. **Move risk-parameter loading (§17), S07 lifecycle (§21), and
  mode-switch gates (§18)** into their owning services.
8. **Final polish:** theme injection (§26), context-menu stubs (§24),
  log ring-buffer (§25).

After step 8, re-run the one-line test: *Delete G05 and drive the
system from a script — does it still trade?* If yes, the dashboard has
been reduced to its proper role.
