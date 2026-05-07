# 2026-05-05 Market Data Report
**Date produced:** 2026-05-05 (updated 2026-05-06)
**Dashboard reference snapshot:** 10:00 ET, 2026-05-06
**Dashboard state:** SPY 729.10 (+0.74%), VIX 17.05, REGIME BULL, ENTRY IDLE

---

## Purpose

This document is the authoritative reference for every symbol and metric displayed on the
Spyder trading dashboard (`SpyderG05_TradingDashboard`).  For each item it records:

- **Data source** (which API / module provides the raw value)
- **Calculation method** (how the value is derived from that source)
- **Update cadence** (how frequently the value refreshes)
- **Correctness / issues** (any known problems observed in the May 6 snapshot or codebase)

The primary reference modules are:

| Module | Role |
|--------|------|
| `SpyderG18_MarketDataWorker` | Background worker that fetches Tradier quotes every 30 s and writes `market_data/live_data.json` |
| `SpyderS07_CustomMetricsOrchestrator` | Orchestrates S-Series custom metrics; emits Qt signals to G05/G10 |
| `SpyderC04_MarketInternals` | Fetches confirmed Tradier index symbols every 5 s; analyses TICK/ADD/TRIN |
| `SpyderS11_TradingViewInternals` | Playwright headless-browser scraper for NYSE breadth internals from TradingView |
| `SpyderC10_VIXAnalyzer` | VIX family regime classification from Tradier / yfinance |
| `SpyderC18_SKEWCalculator` | CBOE SKEW replication from SPY options chain (5-minute update) |
| `SpyderN09_GammaExposure` | Professional GEX engine driven by OPRA real-time data |
| `SpyderS01_DIXCalculator` | Dark Index from FINRA ATS off-exchange volume |
| `SpyderS03_BlackSwanIndicator` | 4-component composite tail-risk score |
| `SpyderS12_WRSSignal` | Walmart Recession Signal — macro consumer stress |
| `SpyderS13_PSRSignal` | Pawn Shop Ratio — working-class credit stress |
| `SpyderS09_FREDClient` | FRED macro series (yields, credit spreads) |

---

## 1. Data Sources Overview

### 1.1 Tradier REST API
- **URL (live):** `https://api.tradier.com/v1/markets/quotes`
- **Auth:** Bearer token in `Authorization` header (`TRADIER_API_KEY`)
- **Primary use:** Equity / ETF / index real-time quotes; historical OHLCV; options chains
- **Confirmed index symbols (April 2026 docs):** `$VIX` → `VIX`, `$ADD` → `ADD`, `$TICK` → `TICK`, `$TNX` → `TNX`, `XLK`, `XLF`
- **NOT confirmed by Tradier docs:** `$TRIN`, `$TRINQ`, `$TICKQ` — explicitly removed from `TRADIER_FETCHABLE_SYMBOLS` in C04 pending confirmation
- **Rate limits:** Token-bucket via `SpyderU40_RateLimiter`; G18 batches equity symbols into a single call

### 1.2 TradingView Playwright Scraper (S11)
- **Module:** `SpyderS11_TradingViewInternals`
- **Method:** Playwright headless Chromium scrapes public TradingView symbol pages
- **Symbols scraped:** `USI-TICK`, `USI-TRIN.NY`, `USI-ADD`, `USI-VOLD`, `USI-UVOL`, `USI-DVOL`
- **NOT available via TradingView:** `USI-NYMO` returns 404 — NYMO is computed, not scraped
- **Update:** On-demand via S07 orchestrator timer

### 1.3 Massive API
- **Client:** `SpyderC27_MassiveClient` / `SpyderC29_DataProviderRouter`
- **Primary use:** Real-time streaming options Greeks, flow, and equity data
- **Env var:** `MASSIVE_API_KEY`
- **Dashboard use:** GEX/DEX/OGL when N09 real-time data is active; $VOLD secondary path

### 1.4 yfinance
- **Version in venv:** 0.2.66
- **Use:** VIX family supplements (^VIX9D, ^VXV, ^VVIX, ^VXMT), SWAN components (^VIX, HYG, LQD, DX-Y.NYB, SPY, TLT), WRS/PSR fallback, DIX S&P 500 constituent market caps
- **Cadence:** On-demand with TTL caching; daily for market-cap data

### 1.5 FINRA ATS (S01)
- **Use:** Off-exchange (dark pool) volume by security for DIX calculation
- **Coverage:** All S&P 500 constituents scraped from Wikipedia
- **Cadence:** Daily; cached to `~/.spyder/market_caps_cache/`

### 1.6 FRED (S09)
- **Module:** `SpyderS09_FREDClient`
- **Series used:** GS2, GS5, GS10, GS30 (Treasury yields), T10Y2Y, T10Y3M (spreads), DFEDTARU (fed funds target)
- **Dashboard mapping:** FRED `GS10` → emitted by S07 as `YIELD_10Y` → displayed as `TNX`

---

## 2. Major Indices

| Symbol | Source module | Tradier symbol | Cadence | Notes |
|--------|--------------|---------------|---------|-------|
| **SPY** | G18 | `SPY` | 30 s | Primary instrument; also drives chart data (5-min bars every 60 s) |
| **QQQ** | G18 | `QQQ` | 30 s | |
| **IWM** | G18 | `IWM` | 30 s | Previous-day close for IWM derived from `RUT` historical data (with IWM fallback) |
| **DIA** | G18 | `DIA` | 30 s | ⚠️ Observed STALE in snapshot — DIA sometimes throttled or delayed by Tradier; no known structural wiring issue |

G18 fetches all four symbols in a single batched Tradier `/markets/quotes` call.  Data is
written to `market_data/live_data.json` and read by G05 on the same 30 s heartbeat.

### DJIA display vs DIA
`DIA` is an ETF (approximately 1/100th of the DJIA).  The dashboard receives `DIA` quotes
and displays the change / percent-change directly.

---

## 3. Market Internals

| Symbol | Source | Method | Cadence | Correctness / issues |
|--------|--------|--------|---------|----------------------|
| **$TICK** | Tradier (C04) + S11 TradingView | Tradier: `TICK` index symbol. S11: USI-TICK page scrape | C04: 5 s; S11: on S07 timer | Tradier confirmed. Value showing 1.24 in snapshot is plausible |
| **$ADD** | Tradier (C04) + S11 TradingView | Tradier: `ADD` index symbol. S11: USI-ADD page scrape | C04: 5 s; S11: on S07 timer | Tradier confirmed |
| **$TRIN** | S11 TradingView | USI-TRIN.NY page scrape via Playwright | On S07 timer | ⚠️ **NOT in Tradier confirmed list** — removed from `TRADIER_FETCHABLE_SYMBOLS`. Value in dashboard (1.24) comes from S11 scrape only |
| **NYMO** | S07 computed | Online EMA(19) − EMA(39) approximation applied to the incoming ADD series. Formula: NYMO ≈ EMA₁₉(ADD) − EMA₃₉(ADD) | Recomputed on each ADD update | ⚠️ **Approximation only** — USI-NYMO returns 404 on TradingView; true NYMO requires ~39 bars of history to warm up; shows 0.00 until sufficient ADD observations accumulated |
| **$VOLD** | S11 TradingView | USI-VOLD page scrape via Playwright | On S07 timer | ⚠️ TradingView USI-VOLD has known unsigned-overflow emissions (noted in S11 code); values are sanity-checked in S11 |
| **RVOL** | G18 computed | `SPY.volume / SPY.average_volume` from Tradier quote fields | 30 s | Relies on Tradier returning `average_volume`; falls back to 1.0 if unavailable |

### C04 TRADIER_FETCHABLE_SYMBOLS (confirmed, April 2026)
```python
TRADIER_FETCHABLE_SYMBOLS = {
    "$TICK": "TICK",
    "$ADD":  "ADD",
    "$VIX":  "VIX",
    "XLK":   "XLK",
    "XLF":   "XLF",
    "$TNX":  "TNX",
}
```
`$TRIN`, `$TRINQ`, `$TICKQ` are explicitly **not listed** in Tradier's official index symbol
table and are currently sourced only via S11 TradingView scraping.

---

## 4. Volatility

| Symbol | Source module | Method | Cadence | Correctness |
|--------|--------------|--------|---------|-------------|
| **VIX** | G18 + C04 + C10 | Tradier `VIX` index symbol (confirmed TRADIER_FETCHABLE). C10 VIXAnalyzer classifies regime. | G18: 30 s; C04: 5 s | ✅ Confirmed live. Snapshot: 17.05 (NORMAL_LOW regime) |
| **VIX9D** | C10 | yfinance `^VIX9D` (replaced discontinued ^VXST in Jan 2020) | C10 timer | Secondary volatility term node; used for term structure ratio |
| **VXV** | C10 | yfinance `^VXV` (3-month CBOE volatility index) | C10 timer | Used for VIX/VXV term structure ratio (30D vs 3M) |
| **VVIX** | C10 | yfinance `^VVIX` (volatility-of-volatility) | C10 timer | |
| **SKEW** | C18 / S06 | CBOE methodology replication: `SKEW = 100 − 10 × μ₃` where μ₃ = risk-neutral third moment of SPY returns estimated from OTM options chain. Uses 30-DTE target; ±20% moneyness; ≥10 strikes required. Cached to `data/skew/skew_cache.pkl`. | 5 minutes (`UPDATE_INTERVAL = 300 s`) | ⚠️ Change delta shows +0.00 in snapshot — this is normal for SKEW which moves slowly intraday. Snapshot value 138.74 is within normal historical range (100–170) |

### VIX Regime Classification (C10 `VIXLevel` enum)
| Level | Range | Interpretation |
|-------|-------|---------------|
| EXTREME_LOW | < 10 | Extreme complacency |
| LOW | 10 – 15 | Low volatility |
| NORMAL_LOW | 15 – 20 | **Dashboard state (VIX 17.05)** |
| NORMAL | 20 – 25 | Normal volatility |
| ELEVATED | 25 – 30 | Elevated concern |
| HIGH | 30 – 40 | High stress |
| EXTREME_HIGH | 40 – 50 | Extreme stress |
| CRISIS | > 50 | Crisis |

### Term Structure Ratios (C10)
- `VIX9D / VIX` — 9-day vs 30-day: contango = VIX9D < VIX (normal backwardation = stress)
- `VIX / VXV` — 30-day vs 3-month: contango = VIX < VXV (normal)
- `VXV / VXMT` — 3-month vs 6-month

---

## 5. Options Analytics

| Symbol | Source | Method | Cadence | Correctness |
|--------|--------|--------|---------|-------------|
| **CPC** | G18 computed | `CPC = total_put_volume / total_call_volume` for the nearest SPY expiry from Tradier options chain. Cached chain TTL = 30 s (`_CHAIN_TTL`). | 30 s | ✅ Live (confirmed: 1.14 on 2026-04-25 test, 589k put / 517k call volume) |
| **IVR** | S07 `_compute_ivr()` | 52-week IV rank: `(current_IV − min_52w) / (max_52w − min_52w) × 100`. History persisted to `market_data/iv_history.json` (rolling 252-entry window). Returns `nan` with fewer than 5 history points. | S07 timer (~60 s) | ⚠️ Shows 0.00 in snapshot — likely insufficient history entries; will populate after several days of data accumulation |
| **ATM_IV** | S07 `_compute_atm_iv()` | Average of `c.iv × 100` for the 6 nearest-ATM option contracts where `c.iv > 0`. Expressed as annualised percentage. | S07 timer (~60 s) | ✅ Confirmed working (11.25% on 2026-04-25 test) |
| **VRP** | S07 `_compute_hv20()` | `VRP = ATM_IV − HV20`. HV20 = 20-day annualised historical volatility from Tradier SPY daily bars. Returns `nan` when fewer than 22 bars available. | S07 timer (~60 s) | ✅ Confirmed working (−5.18 on 2026-04-25 test — negative VRP = HV > IV, unusual but occurred in low-vol regime) |

### CPC Interpretation
- `CPC > 1.0` — More put volume than call volume; elevated hedging / caution
- `CPC ≈ 0.7 – 0.9` — Normal equities range
- `CPC < 0.7` — Extreme call buying; potential contrarian bearish signal

---

## 6. Bonds & Credit

| Symbol | Source | Tradier symbol | Notes |
|--------|--------|---------------|-------|
| **TLT** | G18 | `TLT` | 20+ year Treasury ETF; duration proxy |
| **HYG** | G18 | `HYG` | High-yield credit; also used in SWAN credit stress component |
| **LQD** | G18 | `LQD` | Investment-grade credit; used in SWAN HYG/LQD ratio |
| **TNX** | C04 / S09 | `TNX` (Tradier `$TNX`) + FRED `GS10` | Two parallel sources: C04 Tradier 5s fetch; S09 FRED daily as YIELD_10Y. G05 reads whichever is fresher |

All bonds fetched by G18 via Tradier quotes on 30 s heartbeat.

---

## 7. Correlations & Sector Proxies

| Symbol | Source | Method | Notes |
|--------|--------|--------|-------|
| **DXY** | G18 | Tradier `UUP` quote remapped via `_SYMBOL_REMAP["DXY"] = "UUP"` | UUP (Invesco DB US Dollar ETF) tracks USD index. Not a true DXY index quote |
| **GLD** | G18 | Tradier `GLD` | SPDR Gold Shares |
| **USO** | G18 | Tradier `USO` | US Oil Fund |
| **XLK** | G18 + C04 | Tradier `XLK` | Tech sector ETF; confirmed in TRADIER_FETCHABLE_SYMBOLS |
| **XLF** | G18 + C04 | Tradier `XLF` | Financials ETF; confirmed in TRADIER_FETCHABLE_SYMBOLS. Also denominator in PSR |

---

## 8. Custom Metrics

### 8.1 GEX — Net Gamma Exposure

| Attribute | Value |
|-----------|-------|
| **Primary engine** | `SpyderN09_GammaExposure` |
| **Data source** | `OPRAGreeksHandler` + `OptionChainManager` (real-time OPRA feed) |
| **Formula** | `GEX = Σ_strikes [ Γᵢ × OI_call_i × S² × 0.01 × 100 ] − Σ_strikes [ Γᵢ × OI_put_i × S² × 0.01 × 100 ]` (market maker convention: calls positive, puts negative) |
| **Price range** | ±20% of spot price in $0.50 increments |
| **Key levels** | `zero_gamma` = strike where net GEX changes sign (dealer hedging flip level) |
| **Thresholds** | `HIGH_GEX_THRESHOLD = $1B`; `VOLATILITY_SUPPRESSION_LEVEL = $500M` |
| **Update cadence** | 60 s (`GEX_UPDATE_INTERVAL`) |
| **Dashboard display** | Raw value ÷ 1e9, shown as "$B" |
| **Secondary path** | `SpyderS05_GEXDEXCalculator` — 68-line stub/placeholder, produces zeros |
| **⚠️ Issue** | Dashboard shows GEX = -0.0B because S05 stub is currently the wired S07 source. N09 calculates GEX correctly but is not yet connected to the S07 orchestrator. |

### 8.2 DEX — Delta Exposure

| Attribute | Value |
|-----------|-------|
| **Source** | `SpyderS05_GEXDEXCalculator` (stub) |
| **Status** | ⚠️ **Placeholder only** — 68-line stub, no live computation |
| **Dashboard display** | Raw value ÷ 1e6, shown as "M$" |
| **Observed value** | 0 M$ |

### 8.3 OGL — Open-Interest Gamma Level

| Attribute | Value |
|-----------|-------|
| **Source** | `SpyderS05_GEXDEXCalculator` (stub) |
| **Status** | ⚠️ **Placeholder only** |
| **Observed value** | 0 |

### 8.4 DIX — Dark Index

| Attribute | Value |
|-----------|-------|
| **Source** | `SpyderS01_DIXCalculator` |
| **Primary data** | FINRA ATS (Alternative Trading System) off-exchange print reports |
| **Formula** | `DIX = Σᵢ(dark_pool_dollar_volume_i) / Σᵢ(total_dollar_volume_i)` across all S&P 500 constituents |
| **Universe** | S&P 500 constituents; list scraped from Wikipedia (`SP500_WIKI_URL`) |
| **Market caps** | yfinance with advisory lock file (`~/.spyder/market_caps_cache/market_caps_fetch.lock`) |
| **Cadence** | Daily; FINRA data typically available ~09:00 ET next business day |
| **Interpretation** | DIX > 45% = institutional buying signal; DIX < 40% = neutral/selling |
| **Fallback** | `_calculate_dix_simulated()` when no real data |
| **Live value (2026-04-25)** | 0.485 (48.5%) — institutional buying signal |

### 8.5 WRS — Walmart Recession Signal

| Attribute | Value |
|-----------|-------|
| **Source** | `SpyderS12_WRSSignal` |
| **Formula** | `WRS = Price(WMT) / LUXURY_INDEX` |
| **Luxury basket** | LVMUY, CFRUY, HESAY, PPRUY, BURBY, SWGAY, RACE, TPR, CPRI (9 ADR constituents; equal-weight daily-return compounding from base 100 to avoid inception bias) |
| **Interpretation** | WRS rising → consumers trading down; macro stress indicator. Classified by expanding percentile: NORMAL (0–60th), CAUTION (60–75th), WARNING (75–90th), CRITICAL (90–100th) |
| **Primary data** | Tradier REST `/markets/history`; yfinance fallback |
| **Cadence** | Daily close; 4-hour TTL cache at `~/.spyder/wrs_cache/` |
| **Dashboard scaling** | Raw ratio (÷ 1.0) |
| **Live value (2026-04-25)** | 0.016, percentile 80.28%, signal **WARNING** |
| **Dashboard value (May 6)** | 0.02 — raw ratio; appears very small because WMT ($80) ÷ LUXURY_INDEX (base 100 index) |

### 8.6 PSR — Pawn Shop Ratio

| Attribute | Value |
|-----------|-------|
| **Source** | `SpyderS13_PSRSignal` |
| **Formula** | `PSR = (Price(FCFS) + Price(EZPW)) / Price(XLF)` |
| **Components** | FCFS = FirstCash Holdings (largest US/LatAm pawn operator, NASDAQ); EZPW = EZCORP Inc (second-largest); XLF = Financial Select Sector SPDR |
| **Interpretation** | PSR rising → working-class credit exhaustion leading indicator (leads official recession data by months). Dual-signal with WRS: WRS HIGH + PSR HIGH → confirmed systemic crisis, maximum bearish posture |
| **Primary data** | Tradier primary; yfinance fallback |
| **Cadence** | Daily close; 4-hour TTL cache at `~/.spyder/psr_cache/` |
| **Dashboard scaling** | Raw ratio (÷ 1.0) |
| **Live value (2026-04-25)** | 4.88, percentile 92.28%, signal **CRITICAL** |

### 8.7 SWAN — Black Swan Composite Score

| Attribute | Value |
|-----------|-------|
| **Source** | `SpyderS03_BlackSwanIndicator` |
| **Scale** | 1.0 (benign) to 5.0 (extreme tail risk) |
| **Formula** | `Score = Σ(component_i × weight_i)` + momentum adjustment (+0.2 if 5-period slope > 0.2) |

#### SWAN Component Weights

| Component | Weight | Instrument | Scoring |
|-----------|--------|-----------|---------|
| Volatility (VIX) | 35% | `^VIX` | <12→1.0, 12–20→1.5–2.0, 20–30→2.0–3.0, 30–40→3.0–4.0, >40→4.0–5.0 |
| Credit Stress (HYG/LQD ratio) | 25% | `HYG`, `LQD` | ratio 0.69–0.73→1.0 (normal), >0.73→rising stress, <0.69→tight |
| Liquidity (DXY) | 20% | `DX-Y.NYB` | >110→3.0+, 105–110→2.0–3.0, ≤105→1.5 |
| Market Internals (SPY momentum) | 20% | `SPY` | Simplified placeholder (fixed 1.5 pending market internals integration) |

| SWAN level | Score range | Dashboard colour |
|-----------|-------------|-----------------|
| GREEN | ≤ 1.95 | Green |
| YELLOW | 1.96 – 2.95 | Yellow |
| RED | ≥ 3.00 | Red |

| Attribute | Value |
|-----------|-------|
| **Primary data** | yfinance (`^VIX`, `HYG`, `LQD`, `TLT`, `SPY`, `DX-Y.NYB`) |
| **Fallback** | `_calculate_swan_simulated()` when all feeds unavailable |
| **Scheduled updates** | 04:00, 09:15, 12:00, 15:45, 16:30 ET via S04 BlackSwanScheduler |
| **Continuous updates** | S07 timer: 60 s normal, 30 s high-stress, 300 s calm |
| **Cache TTL** | 60 s |
| **Live value (2026-04-25)** | 1.62, status GREEN |
| **⚠️ Note** | Market Internals component is a fixed 1.5 placeholder — does not use live TICK/TRIN/ADD data |

### 8.8 PMR — Pivot Mean-Reversion

| Attribute | Value |
|-----------|-------|
| **Source** | `SpyderS08_PivotMR` (strategy signal state) |
| **Type** | Not a market data feed — this is a strategy activation flag |
| **Formula** | Price proximity to floor-trader pivot levels (derived from previous day's H/L/C) |
| **Gate** | Controlled by env var `SPYDER_PIVOT_MR_ENABLED=1`; default is **disabled** |
| **Dashboard state** | `ARMED` = strategy is ready but env var is not set to "1" |
| **Previous day pivots** | Computed from `market_data/spy_prev_day.json` (written by G18 from Tradier historical data once per session) |
| **Dashboard display** | Dashboard scaling ÷ 1.0; displays directional signal (BULLISH/BEARISH/NEUTRAL) when enabled |

---

## 9. Signal Monitor Panel

The Signal Monitor (right-side column in G05) displays 14 indicators fed primarily from C04,
S07, and F10 market regime modules.

| Indicator | Source module | What it measures |
|-----------|--------------|-----------------|
| TICK | C04 MarketInternals / S07 | NYSE Tick Index (up-ticks minus down-ticks) |
| TRIN | C04 / S07 | Arms Index (advance/decline ratio of volume vs issues) |
| ADD | C04 / S07 | NYSE Advance-Decline line |
| NYMO | S07 computed | McClellan Oscillator approximation (EMA₁₉ − EMA₃₉ of ADD) |
| VIX | C10 / G18 | CBOE Volatility Index |
| SKEW | C18 / S06 | CBOE SKEW replication from options chain |
| VIX9D | C10 | 9-day CBOE volatility (yfinance ^VIX9D) |
| HYG | G18 | High-yield bond ETF (credit risk proxy) |
| IVR | S07 | IV Rank (52-week percentile) |
| ATM_IV | S07 | At-the-money implied volatility (SPY nearest-expiry) |
| VRP | S07 | Volatility Risk Premium (ATM_IV − HV20) |
| CPC | G18 | Put/Call Ratio (computed from SPY chain volume) |
| GEX | S05 / N09 | Net Gamma Exposure |
| DIX | S01 | Dark Index (dark pool sentiment) |

---

## 10. Pivot Levels (Chart Overlays)

The SPY 5-minute intraday chart displays floor-trader pivot levels derived from the
**previous session's** high, low, and close (fixed for the entire trading day):

- **Data source:** G18 fetches `SPY` 5-day daily history from Tradier once per session
- **Output:** `market_data/spy_prev_day.json` (high, low, close)
- **Levels displayed:** P (pivot), R1, R2, R3, S1, S2, S3 (Fibonacci/Standard)
- **Colours:** P=Yellow, R levels=Red shades, S levels=Green shades
- **Fallback:** If `spy_prev_day.json` is unavailable, all pivot levels collapse to last-close

---

## 11. Data Flow Architecture

```
Tradier REST API
    │
    ├── G18 (30s heartbeat)
    │   ├── equity batch: SPY, QQQ, IWM, DIA, TLT, HYG, LQD, GLD, USO, XLK, XLF
    │   ├── remaps: UUP → DXY
    │   ├── computed: CPC (put/call from chain), RVOL (volume/avg_volume)
    │   └── writes: market_data/live_data.json, spy_5min_chart.json, spy_prev_day.json
    │
    ├── C04 (5s loop during market hours)
    │   ├── confirmed symbols: TICK, ADD, VIX, XLK, XLF, TNX
    │   └── analysis: TICK extremes, breadth, TRIN, RVOL, VOLD from Massive fallback
    │
    └── S07 CustomMetricsOrchestrator (Qt timer, 60/30/300s adaptive)
        ├── S11 TradingView Playwright → TICK, TRIN, ADD, VOLD (scrape)
        │   └── NYMO proxy computed from ADD EMA(19) − EMA(39)
        ├── S01 DIXCalculator → DIX (FINRA ATS, daily)
        ├── S03 BlackSwanIndicator → SWAN (yfinance, ~60s)
        ├── S05 GEXDEXCalculator → GEX, DEX, OGL (stub — zeros)
        ├── N09 GammaExposure → GEX (OPRA, 60s) [NOT YET WIRED TO S07]
        ├── C18/S06 SKEWCalculator → SKEW (SPY chain, 5min)
        ├── S07 _compute_atm_iv / _compute_ivr / _compute_hv20 → ATM_IV, IVR, VRP
        ├── S12 WRSSignal → WRS (Tradier/yfinance, daily)
        ├── S13 PSRSignal → PSR (Tradier/yfinance, daily)
        └── emits: MetricSnapshot Qt signal → G10 (widget) + G05 (dashboard update)

yfinance
    ├── C10 VIXAnalyzer: ^VIX9D, ^VXV, ^VVIX, ^VXMT
    ├── S03 SWAN: ^VIX, HYG, LQD, DX-Y.NYB, SPY
    └── S12/S13 fallback paths

FINRA ATS
    └── S01 DIXCalculator: daily off-exchange volume by S&P 500 constituent

FRED API
    └── S09 FREDClient: GS10 → YIELD_10Y → TNX overlay in dashboard

G05 TradingDashboard
    ├── reads live_data.json (30s)
    └── receives MetricSnapshot Qt signals from S07 (60s adaptive)
```

---

## 12. Known Issues and Observations (2026-05-06 Snapshot)

| Symbol / Issue | Severity | Root Cause | Status |
|----------------|----------|------------|--------|
| **DIA STALE** | Low | Tradier quote age exceeded staleness threshold on that heartbeat; likely a transient Tradier delay for DIA specifically | Monitor; expected to self-recover |
| **GEX = -0.0B** | Medium | S05_GEXDEXCalculator is a 68-line stub (placeholder). The real GEX engine (N09) is not wired to S07 orchestrator. | Open — requires N09 → S07 integration |
| **DEX = 0M, OGL = 0** | Medium | Same root cause as GEX — S05 stub only | Open — same fix |
| **NYMO = 0.00** | Low | NYMO is computed from ADD EMA; requires ~39 ADD observations to warm up the slow EMA. Shows 0.00 until sufficient bars accumulated. USI-NYMO is unavailable on TradingView (404). | Expected; will populate after EMA warm-up period |
| **IVR = 0.00** | Low | `_compute_ivr()` returns NaN / 0 with fewer than 5 entries in `market_data/iv_history.json`. History builds over time. | Expected; populates after several days running |
| **PMR = ARMED** | Informational | `SPYDER_PIVOT_MR_ENABLED` env var is not set to "1". Strategy is loaded and armed but not active. | By design; set env var to activate |
| **$TRIN showing value** | Note | Despite C04 comment that $TRIN is not in Tradier confirmed list, a value appears — this comes from S11 TradingView scrape | Correct behaviour; S11 is the authorised source for $TRIN |
| **SKEW change = +0.00** | Informational | SKEW is relatively stable intraday; delta from previous read is zero | Normal behaviour; no action required |
| **SWAN market internals component = fixed 1.5** | Low | Market Internals weight in SWAN (20%) uses a hardcoded placeholder value rather than live TICK/TRIN/ADD data | Known limitation; improvement tracked in backlog |
| **DXY is UUP proxy, not true DXY** | Low | Tradier does not directly expose the DXY index; UUP ETF is used as proxy | Known; acceptable for trading signals |

---

## 13. Symbols Used Internally But Not Displayed

The following symbols are used in data pipelines, risk models, or ML feature engineering
but are not shown as named rows on the main dashboard:

### Market proxies
- `UUP` — raw Tradier symbol remapped to DXY display
- `VXMT` — 6-month CBOE volatility; used in C10 term structure
- `UVXY` — leveraged VIX proxy; fetched in some market worker variants
- `PCALL` — alias companion to CPC in some market worker code paths
- `RUT` — Russell 2000 index; previous-day close for IWM change calculation
- `NDX` / `IXIC` — mentioned in index/proxy comments
- `WMT` — Walmart (WRS numerator); not separately displayed
- `FCFS`, `EZPW` — PSR components; not separately displayed

### FRED macro identifiers (not Tradier symbols)
- `GS2`, `GS5`, `GS10`, `GS30` — Treasury yields by tenor
- `DFEDTARU` — Federal funds target rate
- `T10Y2Y`, `T10Y3M` — yield curve spreads
- `DTWEXBGS` — broad dollar index
- `VIXCLS` — closing VIX

### WRS luxury basket (9 ADRs — inputs to WRS, not separate dashboard rows)
`LVMUY`, `CFRUY`, `HESAY`, `PPRUY`, `BURBY`, `SWGAY`, `RACE`, `TPR`, `CPRI`

### SWAN inputs (not separate rows)
`^VIX`, `^VIX9D`, `^VXN`, `^RVX`, `DX-Y.NYB`, `HYG`, `LQD`, `TLT`

---

## 14. Readiness Gap Matrix

| Priority | Gap | Why it matters for live trading | Likely owner | Acceptance criteria |
|----------|-----|-------------------------------|--------------|---------------------|
| **P0** | Wire N09 GEX to S07 orchestrator | GEX = 0 is useless for gamma-risk gating; N09 has correct engine already | S07, N09 | GEX non-zero in dashboard; zero-gamma level visible on chart |
| **P0** | DEX live computation | Delta exposure essential for directional position sizing | S05 extension or N09 | DEX non-zero; value in MetricSnapshot |
| **P0** | Options liquidity quality by strike/expiry | Prevents fills in structurally bad contracts | C03/C30, N03/N07, B40 | Pre-trade gate blocks bad-liquidity contracts |
| **P0** | Execution telemetry | Slippage vs mid, fill latency, partial-fill % | B02/B40, M04/M05, K04 | Telemetry persisted per order |
| **P0** | Event-risk blackout calendar | FOMC, CPI, NFP, OpEx windows dominate 0-DTE behaviour | A04, F09, E16 | Configurable calendar with enforced no-trade windows |
| **P1** | Vol surface term structure (0DTE/1DTE/7DTE/30DTE) | Improves strike selection beyond single ATM-IV snapshots | N06/N08/N12, S07 | Surface nodes update intraday |
| **P1** | Confirmed $TRIN from Tradier or reliable API | TradingView scrape is brittle; TRIN is key internal | C04 | Tradier confirmation or alternative API source |
| **P1** | NYMO true calculation | EMA proxy accumulates over runtime only; no seeded history | S07 | Seeded from historical breadth data; accurate vs NYSE $NYMO |
| **P2** | SWAN market internals component (live TICK/TRIN/ADD) | Fixed 1.5 weight dampens SWAN sensitivity to intraday stress | S03 | Component uses live C04/S07 breadth data |
| **P2** | Data quality SLOs per metric | Autonomy requires explicit trust policy for each feed | E24, S07, M01 | Per-metric SLO dashboard with alerting |

---

*Report generated from source-code audit of the Spyder codebase (branch `fix/audit-v14-all`).*
*Reference modules verified on 2026-05-06 against SpyderC04, SpyderC10, SpyderC18, SpyderG05, SpyderG18, SpyderN09, SpyderS01, SpyderS03, SpyderS05, SpyderS07, SpyderS11, SpyderS12, SpyderS13.*
