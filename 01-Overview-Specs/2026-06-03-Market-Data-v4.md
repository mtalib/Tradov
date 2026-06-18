# 2026-06-03 Market Data Report v4
**Date produced:** 2026-06-03
**Reference market snapshot:** ~09:42 ET, 2026-05-22 (intraday, market open)
**Engineering audit and remediation window:** 2026-05-23 to 2026-05-24
**Dashboard state at reference snapshot:** SPY 747.72 (+0.68%), VIX 16.86, REGIME BULL, PMR ARMED
**Reference data sources:** `market_data/live_data.json` (G18, ~09:42 ET) + `market_data/overview_metrics_snapshot.json` (S07, 13:42 UTC)
**Merged sources:** `2026-05-22-Market-Data.md` + `2026-05-24-Market-Data-v2.md`

---

## Purpose

This document merges the original 2026-05-22 market-data snapshot report with the
2026-05-24 freshness-audit update into a single authoritative reference.

It preserves the detailed 2026-05-22 market snapshot, including symbol-by-symbol and
metric-by-metric observations, while also recording the 2026-05-24 findings,
implemented improvements, validation results, and the remaining open issues.

This report does **not** claim that the market values below were all re-captured live
on 2026-05-24. The observed market values remain tied to the 2026-05-22 reference
snapshot. What changed on 2026-05-24 is the documented behavior of the dashboard,
helper boundaries, and strategy fallback paths when upstream data becomes stale.

---

## 1. Executive Summary

At the 2026-05-22 reference snapshot, the dashboard showed a broadly bullish tape:
SPY +0.68%, QQQ +0.82%, IWM +0.56%, VIX 16.86, GEX positive, SWAN green, and no
economic stand-down. However, the follow-up audit found that freshness metadata was
not being carried end-to-end across every consumer surface. Some stale custom metrics
could still be rendered, merged, or replayed as if they were live.

The root issue was downstream propagation, not the complete absence of freshness data.
`HedgerS07_CustomMetricsOrchestrator` already produced bucket quality information.
The missing piece was consistent enforcement in the dashboard, helper boundaries,
breadth dialog, cached restore path, and D31 disk-backed IV enrichment.

### 1.1 Core findings

| Area | Finding | Risk |
|------|---------|------|
| G05 overview widgets | Stale metric entries could fan out into row widgets | Old values looked live |
| G13 signal panel sync | Stale values could remain in `_live` because merges did not clear old keys | Regime/live displays could silently lag |
| G17 breadth dialog | NaN-only stale payloads were ignored, leaving prior breadth numbers on screen | Breadth could appear fresh when stale |
| Cached restart restore | Cached Market Overview metrics could replay without an age gate | Warm restart could resurrect old state |
| D31 strategy fallback | Disk-backed IV/IVR hints could load without a freshness cutoff | Strategy preprocessing could inherit stale hints |

### 1.2 Outcome

The remediation closes those paths. Freshness is now treated as explicit data rather
than a UI inference. Stale values are surfaced as stale, stale signal keys are cleared,
cached overview restore is bounded to a short warm-restart window, and D31 now rejects
old disk-backed IV hints.

---

## 2. Verification Boundary

This v3 report intentionally separates two kinds of assertions:

1. The **reference market snapshot** from 2026-05-22.
2. The **behavioral correctness update** validated on 2026-05-24.

That means statements such as "SPY was 747.72" or "BREADTH bucket age was 6312 s"
are historical snapshot facts, while statements such as "stale breadth now renders as
STALE in G17" or "D31 rejects old IV snapshots older than 180 seconds" are code-path
findings validated after the snapshot.

---

## 3. Implemented Improvements

| Module | Improvement | Outcome |
|--------|-------------|---------|
| `HedgerS07_CustomMetricsOrchestrator` | Formatted custom metric entries now carry `quality_bucket` and `stale` | Downstream consumers receive freshness explicitly |
| `HedgerG05_TradingDashboard` | Stale widgets render unavailable, stale signal-panel keys are cleared, stale liquidity payloads are suppressed, cached restore is limited to 15 minutes | Main dashboard no longer presents stale custom metrics as live |
| `HedgerG106_CustomMetricWidgetUpdateHelper` | Rejects stale entries during widget fanout | Row widgets only update from live values |
| `HedgerG107_CustomMetricSignalPanelSyncHelper` | Treats stale entries as absent and returns keys to clear from `_live` | Signal panel does not keep stale live-state residues |
| `HedgerG108_CustomMetricBreadthDialogSyncHelper` | Emits a stale envelope with NaN breadth values, blank regime, and `stale = true` | Breadth consumers can distinguish stale from missing |
| `HedgerG109_RegimePillStateHelper` | Ignores stale SWAN/DIX-style inputs | Regime pills fall back instead of trusting expired values |
| `HedgerG17_MarketInternalsWidget` | Adds explicit stale rendering for internals panels and dialog-level stale status | Open breadth dialog shows `STALE` instead of retaining old numbers |
| `HedgerD31_StrategyOrchestrator` | Prefers `overview_metrics_snapshot.json`, ignores stale entries, and rejects disk snapshots older than 180 seconds | Strategy preprocessing only consumes fresh IV/IVR hints |
| Focused tests | Added or updated regressions around S07, G05 helper boundaries, G17, and D31 | Freshness behavior is now covered by targeted checks |

---

## 4. Data Sources Overview

### 4.1 Tradier REST API

- **URL (live):** `https://api.tradier.com/v1/markets/quotes`
- **Auth:** Bearer token (`TRADIER_API_KEY`)
- **Primary use:** Equity, ETF, and index real-time quotes; historical OHLCV; SPY options chain
- **Confirmed index symbols (current policy):** `VIX`, `ADD`, `TICK`, `TNX`, `XLK`, `XLF`
- **Not confirmed by Tradier docs:** `$TRIN`, `$TRINQ`, `$TICKQ`; these are excluded from `TRADIER_FETCHABLE_SYMBOLS` in C04 and sourced via S11 instead
- **Rate limits:** Token-bucket via `HedgerU40_RateLimiter`; G18 batches all equity symbols into a single call
- **Status at reference snapshot:** Live and healthy

### 4.2 TradingView Playwright scraper (S11)

- **Module:** `HedgerS11_TradingViewInternals`
- **Method:** Playwright headless Chromium scrapes public TradingView symbol pages
- **Symbols scraped:** `USI-TICK`, `USI-TRIN.NY`, `USI-ADD`, `USI-VOLD`, `USI-UVOL`, `USI-DVOL`, and sector ETF breadth
- **Not available via TradingView:** `USI-NYMO` returns 404, so NYMO is computed from ADD EMA instead
- **Update cadence:** On-demand via S07 orchestrator timer, about every 60 seconds
- **Status at reference snapshot:** BREADTH bucket age was 6312 seconds, so breadth was stale at the snapshot
- **v3 behavior update:** stale breadth now propagates to an explicit stale dialog state instead of leaving last-known values on screen

### 4.3 Massive API

- **Client:** `HedgerC27_MassiveClient` / `HedgerC29_DataProviderRouter`
- **Primary use:** Real-time streaming options Greeks, flow, and equity data
- **Env var:** `MASSIVE_API_KEY`
- **Dashboard use:** GEX, DEX, OGL, VEX, and CHEX through the N09 engine wired into S07

### 4.4 yfinance

- **Use:** VIX-family supplements (`^VIX9D`, `^VXV`, `^VVIX`), SWAN components (`^VIX`, `HYG`, `LQD`, `DX-Y.NYB`, `SPY`, `TLT`), and WRS / PSR fallback data
- **Reference note:** `live_data.json` showed VXV with source `yfinance_vix3m`

### 4.5 FINRA ATS (S01)

- **Use:** Off-exchange dark-pool volume for DIX calculation
- **Coverage:** S&P 500 constituents with market caps cached at `~/.hedger/market_caps_cache/`
- **Reference value:** DIX 43.20% at 13:00 UTC (09:00 ET), file `data/dix_history_20260522.json`
- **Recent trend:** 44.4% -> 41.0% -> 41.0% -> 43.2% -> 43.2%

### 4.6 FRED (S09)

- **Module:** `HedgerS09_FREDClient`
- **Reference status:** FRED bucket age was 6312 seconds, so it was stale and using cached prior-session values
- **Series used:** GS2, GS5, GS10, GS30, T10Y2Y, T10Y3M, DFEDTARU
- **Reference current YIELD_10Y:** 4.32 from G18 Tradier TNX while FRED was stale

---

## 5. Data Quality Summary

### 5.1 Quality buckets at 13:42 UTC on 2026-05-22

| Bucket | Status | Age | Data Points |
|--------|--------|-----|-------------|
| GEX | Fresh | 0 s | 105 |
| DEX | Fresh | 0 s | 105 |
| OGL | Fresh | 0 s | 105 |
| VEX | Fresh | 0 s | 105 |
| CHEX | Fresh | 0 s | 105 |
| SKEW | Fresh | 0 s | 105 |
| SWAN | Fresh | 0 s | 105 |
| DIX | Fresh | 0 s | 105 |
| PCA-IV | Fresh | 0 s | 105 |
| PCA-PROXY | Fresh | 0 s | 105 |
| SECTOR_BREADTH | Fresh | 0 s | 210 |
| DEALER_FLOW | Fresh | 0 s | 210 |
| BREADTH | Stale | 6312 s | 0 |
| ECO_CALENDAR | Stale | 6312 s | 0 |
| FRED | Stale | 6312 s | 0 |
| LIQUIDITY | Stale | 6312 s | 0 |
| OPTIONS | Stale | 6312 s | 0 |
| PREDICTION_MARKETS | Stale | 6312 s | 0 |
| SENTIMENT | Stale | 6312 s | 0 |
| VOL_SURFACE | Stale | 6312 s | 0 |
| MARKET_INTEL | Stale | 6312 s | 0 |

**SLO at the reference snapshot:** `overall_quality_ok = true` and
`freshness_ok = false` because 9 of 21 buckets were stale.

**S07 summary text at the snapshot:** *"Market risk is contained (SWAN 1.56). Dark-pool
flow is light (DIX 43.2%). Dealers are long gamma (GEX +0.3B). Skew is compressed at
98. Breadth regime: neutral. News flow: bullish. Social sentiment: neutral."*

### 5.2 Correctness update from the 2026-05-24 audit

The stale buckets above were not the problem by themselves. The problem was that some
consumer paths could still display or reuse values derived from stale sources.

After the fix:

- stale custom metrics are marked unavailable instead of displayed as live;
- stale signal-panel keys are explicitly cleared instead of silently merged forward;
- stale breadth payloads trigger an explicit `STALE` dialog state;
- cached Market Overview restore is limited to a 15-minute warm-restart window;
- D31 disk-backed IV and IVR hints are rejected once older than 180 seconds.

---

## 6. Major Indices

| Symbol | Last | Change | Chg% | Source | Cadence | Notes |
|--------|------|--------|------|--------|---------|-------|
| **SPY** | 747.72 | +5.00 | +0.68% | G18 / Tradier | 30 s | Primary instrument; drives chart (5-minute bars every 60 s) |
| **QQQ** | 720.35 | +5.84 | +0.82% | G18 / Tradier | 30 s | |
| **IWM** | 284.07 | +1.58 | +0.56% | G18 / Tradier | 30 s | |
| **DIA** | 506.36 | +3.25 | +0.65% | G18 / Tradier | 30 s | |

### 6.1 Extended indices (`live_data.json`, not displayed on main overview panel)

| Symbol | Last | Change | Chg% | Notes |
|--------|------|--------|------|-------|
| SPX | 7,494.59 | +48.87 | +0.66% | S&P 500 composite |
| NDX | 29,478.89 | +121.62 | +0.42% | Nasdaq-100 |
| RUT | 2,859.14 | +15.92 | +0.56% | Russell 2000 underlying (IWM proxy) |
| $DJI | 50,285.66 | 0.00 | 0.00% | Tradier DJI change field was returning zero |

### 6.2 Market interpretation

All four major indices were advancing with broad participation (+0.56% to +0.82%).
Tech led the session and small-caps participated but lagged, consistent with a risk-on
but not euphoric tape.

---

## 7. Market Internals

| Symbol | Last | Source | Method | Cadence | Correctness |
|--------|------|--------|--------|---------|-------------|
| **$TICK** | +447 | S11 TradingView | `USI-TICK` page scrape | ~60 s | Moderately positive and within normal intraday range |
| **$TRIN** | 0.79 | S11 TradingView | `USI-TRIN.NY` scrape | ~60 s | TRIN < 1.0, bullish internals |
| **$ADD** | +183 | S11 TradingView | `USI-ADD` scrape | ~60 s | Positive net advances |
| **NYMO** | 0.00 | S07 computed | `EMA19(ADD) - EMA39(ADD)` | Per ADD update | Approximation only; TradingView NYMO not available |
| **$VOLD** | +293.9M | S11 TradingView | `USI-VOLD` page scrape | ~60 s | Positive advancing-minus-declining volume differential |
| **RVOL** | 0.06 | G18 computed | `SPY.volume / SPY.average_volume` | 30 s | Extremely low because the snapshot was early in the session |

### 7.1 Internals interpretation

TICK +447, TRIN 0.79, ADD +183, and VOLD +293.9M all pointed in the same direction:
orderly broad-based buying. RVOL 0.06 confirmed it was still very early in the session.

### 7.2 Participation score (S11)

- **Value:** 65.4%
- **Breadth regime:** `bull`
- **Source:** `HedgerS11_TradingViewInternals` snapshot at 13:44 UTC

### 7.3 Freshness note

If breadth values later become stale, G17 no longer retains the last live numbers on
screen. It now renders the Market Internals dialog explicitly as stale.

---

## 8. Volatility

| Symbol | Last | Change | Chg% | Source | Cadence | Notes |
|--------|------|--------|------|--------|---------|-------|
| **VIX** | 16.86 | +0.10 | +0.60% | G18 / Tradier `VIX` | 30 s | Live; `NORMAL_LOW` regime |
| **VIX9D** | 14.17 | +0.09 | +0.64% | G18 / Tradier `VIX9D` | 30 s | VIX9D below VIX, normal contango |
| **VXV** | 20.00 | -0.76 | -3.66% | yfinance `^VXV` | C10 timer | VIX/VXV = 0.843, normal contango |
| **VVIX** | 92.71 | +0.83 | +0.91% | G18 / Tradier `VVIX` | 30 s | Elevated versus typical, but not alarming |
| **SKEW (G18)** | 136.96 | 0.00 | 0.00% | G18 / Tradier `SKEW` | 30 s | Direct Tradier index quote; no new CBOE intraday print |
| **SKEW (S07/C18)** | 98.33 | --- | --- | S07 `HedgerC18_SKEWCalculator` | 5 min | Intraday options-chain replication |

### 8.1 VIX regime classification (`C10.VIXLevel`)

| Level | Range | Current state |
|-------|-------|---------------|
| EXTREME_LOW | < 10 | |
| LOW | 10-15 | |
| **NORMAL_LOW** | **15-20** | VIX 16.86 |
| NORMAL | 20-25 | |
| ELEVATED | 25-30 | |
| HIGH | 30-40 | |
| EXTREME_HIGH | 40-50 | |
| CRISIS | > 50 | |

### 8.2 VIX term structure

| Ratio | Value | Interpretation |
|-------|-------|---------------|
| VIX9D / VIX | 0.840 | Contango, no near-term stress |
| VIX / VXV | 0.843 | Contango, 30D cheaper than 3M |
| TERM_SLOPE_0_7 | --- | Stale bucket |
| TERM_SLOPE_7_30 | --- | Stale bucket |

### 8.3 SKEW discrepancy note

The dashboard overview displayed `136.96` from the G18 Tradier SKEW quote, while the
S07/C18 options-chain replication produced `98.33`. Both are architecturally correct
for their respective sources. The difference reflects once-daily CBOE index publication
versus an intraday options-chain estimate, not a freshness bug.

---

## 9. Options Analytics

| Symbol | Last | Source | Method | Cadence | Correctness |
|--------|------|--------|--------|---------|-------------|
| **IVR** | 10.02 | S07 `_compute_ivr()` | 52-week IV rank formula | ~60 s | Live; 252 history points |
| **ATM_IV** | 15.23% | S07 `_compute_atm_iv()` | Average of 6 nearest-ATM SPY options with IV > 0 | ~60 s | Live at the snapshot |
| **VRP** | +4.69 | S07 `_compute_hv20()` | `ATM_IV - HV20` | ~60 s | Positive risk premium |
| **CPC** | 0.626 | G18 computed | `total_put_vol / total_call_vol` for nearest SPY expiry | 30 s | Call-heavy / mildly complacent tone |

### 9.1 IV history (`data/cache/spy_iv_history.json`)

| Date | ATM_IV |
|------|--------|
| 2026-05-20 | 14.98% |
| 2026-05-21 | 15.23% |
| 2026-05-22 | 15.23% |

IVR at 10.02 meant current ATM_IV was near the 10th percentile of the trailing
52-week range. This was a low-premium environment.

### 9.2 CPC interpretation

- CPC 0.626 meant more call volume than put volume.
- Historical context: CPC below 0.70 often coincides with near-term complacency, but
  it is not actionable on its own.

### 9.3 Freshness note

D31 now only accepts fresh `ATM_IV` and `IVR` hints from disk and prefers
`overview_metrics_snapshot.json` over weaker fallback paths.

---

## 10. Bonds and Credit

| Symbol | Last | Change | Chg% | Source | Notes |
|--------|------|--------|------|--------|-------|
| **TLT** | 84.53 | +0.31 | +0.37% | G18 / Tradier | 20+ year Treasury ETF |
| **HYG** | 80.00 | +0.10 | +0.13% | G18 / Tradier | High-yield credit; also a SWAN credit component |
| **LQD** | 108.45 | +0.28 | +0.26% | G18 / Tradier | Investment-grade credit; also a SWAN credit component |
| **TNX** | 4.32 | +0.07 | +1.65% | G18 / Tradier + S09 FRED | Tradier TNX was the primary live source while FRED was stale |

### 10.1 Yield curve (`S09 / YIELD` metrics)

| Key | Value | Notes |
|-----|-------|-------|
| YIELD_10Y | 4.32 | TNX from G18 Tradier fetch |
| YIELD_SLOPE | 0.54 | Approximate 10Y - 2Y spread; positive slope |
| YIELD_INVERTED | false | Curve not inverted |

TNX rising while equities advanced suggested a growth-driven rates move rather than a
risk-off flight to safety. HYG and LQD also confirmed benign credit conditions.

---

## 11. Correlations and Sector Proxies

| Symbol | Last | Change | Chg% | Source | Notes |
|--------|------|--------|------|--------|-------|
| **UUP (DXY proxy)** | 27.77 | +0.05 | +0.16% | G18 / Tradier `UUP` | A proxy only, not the true DXY index |
| **GLD** | 414.74 | -2.25 | -0.54% | G18 / Tradier | Gold lower alongside a slightly stronger dollar |
| **USO** | 142.22 | -0.32 | -0.23% | G18 / Tradier | Oil modestly lower |
| **XLK** | 180.92 | +2.32 | +1.30% | G18 / Tradier | Tech leading |
| **XLF** | 52.05 | +0.32 | +0.62% | G18 / Tradier | Financials participating |

---

## 12. Custom Metrics

### 12.1 GEX - Net Gamma Exposure

| Attribute | Value |
|-----------|-------|
| **Value** | +0.264B (+$264M) |
| **Formatted display** | `+0.3B` |
| **Source** | N09 GammaExposure engine wired into S07 |
| **Data feed** | OPTIONS chain via `HedgerB40_TradierClient` |
| **Interpretation** | Dealers were net long gamma, implying volatility suppression |
| **GEX_REGIME** | `moderate_positive` |
| **Zero gamma level** | N/A (`ZERO_GAMMA = ---`) |
| **Wall confidence** | 0.00 |
| **Freshness** | Age 0 s, 105 data points |

### 12.2 DEX - Delta Exposure

| Attribute | Value |
|-----------|-------|
| **Value** | +687.0M |
| **Formatted display** | `687M` |
| **Source** | N09 engine |
| **Interpretation** | Supportive long-delta dealer posture |
| **Freshness** | Age 0 s |

### 12.3 OGL - Open-Interest Gamma Level

| Attribute | Value |
|-----------|-------|
| **Value** | 735.00 |
| **Formatted display** | `735.00` |
| **Source** | `LIQUIDITY_DIAGNOSTICS` anchor strike from S07 |
| **Interpretation** | Highest open-interest strike for the current SPY expiry was 735 |
| **Liquidity candidates at 735** | 6 candidates evaluated; all failed spread gates |
| **Freshness** | Age 0 s |

### 12.4 VEX - Vanna Exposure

| Attribute | Value |
|-----------|-------|
| **Value** | +13.6M |
| **Formatted display** | `13.6M` |
| **Source** | N09 engine |
| **Interpretation** | Positive vanna tailwind on vol compression |
| **Freshness** | Age 0 s |

### 12.5 CHEX - Charm Exposure

| Attribute | Value |
|-----------|-------|
| **Value** | -307,146 |
| **Formatted display** | `-307146.08` |
| **Source** | N09 engine |
| **Interpretation** | Mild time-decay headwind |
| **Freshness** | Age 0 s |

### 12.6 DIX - Dark Index

| Attribute | Value |
|-----------|-------|
| **Value** | 43.20% |
| **Status** | BULLISH (threshold >= 43%) |
| **Source** | `HedgerS01_DIXCalculator` |
| **Primary data** | FINRA ATS off-exchange prints; computed at 09:00 ET daily |
| **Formula** | `DIX = sum(dark_dollar_volume) / sum(total_dollar_volume)` across the S&P 500 |
| **File** | `data/dix_history_20260522.json` |
| **5-day trend** | 44.4% -> 41.0% -> 41.0% -> 43.2% -> 43.2% |
| **Interpretation** | Slightly light but not bearish institutional flow |

### 12.7 PCA-Proxy - Market Factor Proxy

| Attribute | Value |
|-----------|-------|
| **Value** | +0.585 |
| **Change** | -1.804 (-75.5% from prior) |
| **Regime band** | `Balanced` |
| **Regime color** | `#9bb` |
| **Regime note** | "The common factor is present, but internal breadth is still mixed." |
| **Method** | PCA on 11 SPDR sector ETFs with PC1 as a market-factor proxy |
| **Details** | `PC1_score = 0.679`, `PC2_abs = 0.641`, `explained_variance = 36.1%`, `spectral_gap = 2.35`, `confidence = 0.451` |
| **History window** | 20 sessions (2026-04-24 -> 2026-05-21) |
| **Source** | Tradier live sector ETF quotes |
| **Freshness** | Timestamp 11:58 UTC |

### 12.8 PCA-IV - IV Surface Factor

| Attribute | Value |
|-----------|-------|
| **Value** | -1.339 |
| **Change** | -0.001 |
| **Regime band** | `Surface twist` |
| **Regime color** | `#f2b134` |
| **Regime note** | "Secondary curvature and skew effects are large relative to the main IV factor." |
| **Method** | PCA on 7 SPY IV surface features |
| **Details** | `PC1_score = -1.502`, `PC2_abs = 1.135`, `explained_variance = 39.2%`, `feature_skew = -1.937`, `feature_level = 0.147` |
| **Phase** | `live-seeding` with 60 of 120 target snapshots accumulated |
| **History path** | `data/cache/pca_iv_surface_history/spy_iv_surface_features.jsonl` |
| **Last snapshot** | 2026-05-10 |
| **Freshness** | Age 0 s |

### 12.9 WRS - Walmart Recession Signal

| Attribute | Value |
|-----------|-------|
| **Raw value** | 0.01534 |
| **Formatted display** | `0.02` |
| **Formula** | `WRS = Price(WMT) / LUXURY_INDEX` |
| **Luxury basket** | LVMUY, CFRUY, HESAY, PPRUY, BURBY, SWGAY, RACE, TPR, CPRI |
| **Primary data** | Tradier `/markets/history`; yfinance fallback |
| **Cache** | `~/.hedger/wrs_cache/` |
| **Cadence** | Daily close with 4-hour TTL |
| **Note** | Raw ratio appears small because WMT is divided by a base-100 compounded luxury index |

### 12.10 PSR - Pawn Shop Ratio

| Attribute | Value |
|-----------|-------|
| **Value** | 5.020 |
| **Formula** | `PSR = (Price(FCFS) + Price(EZPW)) / Price(XLF)` |
| **Components** | FCFS, EZPW, XLF |
| **Interpretation** | Tracks working-class credit exhaustion; current level alone is not alarming |
| **Source** | Tradier primary; yfinance fallback |

### 12.11 SWAN - Black Swan Indicator

| Attribute | Value |
|-----------|-------|
| **Value** | 1.56 |
| **Status** | GREEN |
| **Alert level** | LOW |
| **Formula** | Four-component composite: volatility, credit stress, liquidity, and market internals |
| **Most recent component scores** | `volatility = 1.85`, `credit_stress = 1.09`, `liquidity = 1.50`, `market_internals = 1.90` |
| **Interpretation** | Low tail-risk environment |
| **Source** | `HedgerS03_BlackSwanIndicator` |
| **Freshness** | Age 0 s |

### 12.12 PMR - Paper Mode Relay

| Attribute | Value |
|-----------|-------|
| **Value** | ARMED |
| **Trading mode** | PAPER |
| **Interpretation** | Strategy engine was armed and ready to place paper trades |

### 12.13 Freshness note for custom metrics

These formatted entries now carry freshness metadata from S07, and stale values no
longer flow through G05, G106, G107, G108, or G109 as ordinary live readings.

---

## 13. Hidden and Background Metrics

These metrics are computed and stored in `overview_metrics_snapshot.json` but do not
appear on the main dashboard overview panel.

### 13.1 Sentiment and survey data

| Metric | Value | Source | Notes |
|--------|-------|--------|-------|
| AAII Bullish % | 22.6% | AAII weekly survey | Displayed as `nan%` due to a formatter bug |
| NAAIM Exposure | 77.34 | NAAIM weekly survey | Displayed as `nan` due to the same formatter pattern |

AAII bullish at 22.6% was historically very low. Combined with NAAIM at 77.34, this
looked like a contrarian-bullish setup: professional money deployed while retail mood
was still bearish.

### 13.2 News flow

| Metric | Value | Notes |
|--------|-------|-------|
| NEWS_FLOW_VERDICT | **Bullish** | Aggregate news-flow score |
| NEWS_FLOW_EQUITIES | 0.249 | Normalized equity news sentiment |
| NEWS_FLOW_HEADLINE | "WEC Energy Group stock: steady regulated utility with dividend focus" | Reference leading headline |
| NEWS_FLOW_MACRO | --- | Stale or uncaptured macro event |

### 13.3 Economic calendar

| Metric | Value | Notes |
|--------|-------|-------|
| ECO_NEXT_EVENT_NAME | PCE | Next scheduled macro event |
| ECO_NEXT_EVENT_MINUTES | 10,008 min (~6.9 days) | Next PCE release was about one week away |
| ECO_STAND_DOWN | `false` (`clear`) | No economic stand-down in effect |

### 13.4 Dealer flow and gamma walls

| Metric | Value | Notes |
|--------|-------|-------|
| DEALER_FLOW regime | `moderate_positive` | Dealer net-positioning direction |
| DEALER_FLOW dealer_position | `unknown` | Specific position not resolved |
| ZERO_GAMMA | --- | Zero-gamma strike not resolved |
| WALL_CONFIDENCE | 0.00 | No dominant call or put wall detected |
| VANNA_PRESSURE | --- | Stale because OPTIONS bucket was stale |
| CHARM_PRESSURE | --- | Stale |
| FLOW_IMBALANCE | --- | Stale |
| RR_25D | --- | Stale |
| FLY_25D | --- | Stale |

### 13.5 Sector breadth (S11)

| Metric | Value | Notes |
|--------|-------|-------|
| BREADTH_REGIME | `bull` | Computed from sector participation |
| PARTICIPATION_SCORE | 65.4% | 65.4% of sectors advancing |
| SECTOR_ADV_DEC | 183 | Matches `$ADD` value |
| BREADTH_CYCLICAL | --- | TradingView scrape returned NaN |
| BREADTH_DEFENSIVE | --- | TradingView scrape returned NaN |
| BREADTH_SPREAD | --- | TradingView scrape returned NaN |
| SECTOR_MOMENTUM_DISPERSION | --- | Not calculated |
| Source | `HedgerS11_TradingViewInternals` snapshot at 13:44 UTC |

### 13.6 IV term structure detail

| Metric | Value | Notes |
|--------|-------|-------|
| ATM_IV_0DTE | --- | Not computed because OPTIONS bucket was stale |
| ATM_IV_1DTE | --- | Stale |
| ATM_IV_7DTE | --- | Stale |
| ATM_IV_30DTE | --- | Stale |
| TERM_SLOPE_0_7 | --- | Stale |
| TERM_SLOPE_7_30 | --- | Stale |
| SURFACE_CONFIDENCE | --- | Stale because VOL_SURFACE bucket age was 6312 s |
| SURFACE_AGE_MS | --- | Stale |

---

## 14. Findings by Surface

### 14.1 Overview widgets and Market Overview cache

The main G05 dashboard fanout accepted formatted custom metrics without a hard stale
check. That meant stale entries could continue to populate displayed rows. In addition,
the cached restore path for `overview_metrics_snapshot.json` could replay old Market
Overview values after a restart with no short-window freshness guard.

**Resolution:** G05 now marks stale values unavailable, clears prior-value state where
needed, and only restores cached Market Overview metrics when the snapshot file exists
and is no more than 15 minutes old.

### 14.2 Signal panel live values

Suppressing stale updates alone was not enough for the G13 signal panel because its
state merged into a persistent `_live` mapping. If a value became stale and the key was
simply omitted, the old value could remain visible.

**Resolution:** G107 now returns `clear_live_keys`, and G05 removes those stale keys so
the signal panel state reflects current freshness instead of last-known-good residue.

### 14.3 Breadth dialog stale rendering

The breadth helper could return NaN-style stale payloads, but G17 ignored those and
left prior breadth values on screen. This was the last stale-display edge found in the
audit.

**Resolution:** G108 now emits `stale = true` with the breadth payload, and G17 sets
each panel to an explicit `STALE` state with a waiting message and yellow indicator.

### 14.4 Regime pill safety

Regime pill logic could infer live status from values that were structurally present but
already stale at the S07 layer.

**Resolution:** G109 now ignores stale metric entries and falls back to live-safe logic
instead of trusting expired SWAN or DIX style inputs.

### 14.5 Strategy IV and IVR enrichment

D31 could enrich `market_df` using disk-backed IV values without verifying whether the
snapshot was still fresh enough for live-decision use.

**Resolution:** D31 now prefers `overview_metrics_snapshot.json`, accepts `value` or
`last`, rejects entries marked stale, and rejects any disk snapshot older than 180
seconds.

---

## 15. Focused Validation

The following checks were run against the touched freshness and strategy paths.

### 15.1 Focused freshness tests

| Validation slice | Result |
|------------------|--------|
| `HedgerT161_S07_BreadthQualityFeed.py` | Passed |
| `HedgerT320_G05_CustomMetricBreadthDialogSync.py` + `HedgerT321_G108_CustomMetricBreadthDialogSyncHelper.py` + `HedgerT387_G17_MarketInternalsStaleBreadth.py` | Passed (7 tests) |
| `HedgerT386_D31_LiveOptionsSnapshotAgeGate.py` | Passed |
| `HedgerT141_D31_EntryTrustGate.py` + `HedgerT147_F09_DecisionPathControls.py` + `HedgerT386_D31_LiveOptionsSnapshotAgeGate.py` | Passed (33 tests) |

### 15.2 Broader touched-slice regression

The broader custom-metrics regression slice passed for the freshness work itself and
stopped only on one known unrelated failure:

- `HedgerT217_G05_OffHoursCacheRestore.py::test_apply_proven_real_data_pattern_logs_dia_and_vxv_detail`

That failure pre-dated the final stale-breadth fix and was not part of the market-data
freshness issue addressed here.

### 15.3 Lint

`ruff check` passed on all touched production and test files after the final G17 / T387
newline fix.

### 15.4 Sunday off-hours startup observation

An additional manual startup observation was captured on Sunday, 2026-05-24 at
06:59:54 ET, outside market hours.

| Observed log line | Interpretation |
|-------------------|----------------|
| `Startup readiness validated (mode=PAPER, warnings=0, errors=0)` | Startup gate passed cleanly in paper mode |
| `Skipped cached Market Overview metrics older than 15m` | The new warm-restart age gate was exercised in a real off-hours startup path |
| `Connected to Tradier API` | Broker connectivity was available even though the market was closed |
| `HMM not available - using fallback classifier` | Optional HMM dependency was absent; the risk stack fell back to its non-HMM classifier |
| `Dashboard initialized` / `HEDGEX DASHBOARD STARTED` | GUI startup completed successfully |

This off-hours observation materially supports the cache-freshness remediation: on a
Sunday startup, Hedger did not replay stale Market Overview metrics older than 15
minutes. That is the expected behavior for the G05 cached restore boundary added in
this remediation.

---

## 16. Overall Market Interpretation (Reference Snapshot)

| Dimension | Signal | Reading |
|-----------|--------|---------|
| Price | All four major indices advancing | Bullish |
| Breadth | TICK +447, ADD +183, VOLD +293.9M, TRIN 0.79 | Bullish |
| Sector participation | 65.4%, `BREADTH_REGIME = bull` | Bullish |
| Volatility | VIX 16.86 `NORMAL_LOW`; term structure in contango | Neutral / benign |
| Credit | HYG and LQD both rising; spreads not widening | Bullish |
| Bonds | TLT +0.37%, TNX +1.65% | Growth-driven move |
| Gamma regime | GEX +0.3B, dealers long gamma | Bullish / range-bound |
| Dark pools | DIX 43.2% at threshold | Neutral |
| Options sentiment | CPC 0.626, IVR 10 | Complacent / bullish |
| Tail risk | SWAN 1.56 GREEN | Low |
| Macro | `ECO_STAND_DOWN = false`, PCE in about 7 days | No near-term catalyst |
| News | Bullish | Bullish |
| Survey sentiment | AAII Bullish 22.6% | Bullish contrarian |
| Professional positioning | NAAIM 77.34 | Bullish |

**System PMR:** ARMED (paper mode)
**S07 summary text:** *"Market risk is contained (SWAN 1.56). Dark-pool flow is
light (DIX 43.2%). Dealers are long gamma (GEX +0.3B). Skew is compressed at 98.
Breadth regime: neutral. News flow: bullish. Social sentiment: neutral."*

### 16.1 Updated interpretation

The market interpretation of the 2026-05-22 snapshot remains unchanged. What changed
in v3 is operational trust in the display and fallback paths:

- stale values are surfaced as stale instead of appearing live;
- restart cache replay is constrained to a short warm-restart boundary;
- strategy IV enrichment no longer trusts old disk snapshots;
- breadth stale-state is visible instead of silently sticky.

That materially improves operator confidence that the dashboard and downstream strategy
paths reflect current data quality rather than last-known-good residue.

---

## 17. Remaining Issues and Non-Goals

The freshness remediation did not attempt to solve every issue observed in the original
report.

| Item | Status | Note |
|------|--------|------|
| AAII / NAAIM formatter displays `nan` | Still open | The raw values are present, but formatting is still wrong |
| HMM not available on observed Sunday startup | Known environment limitation | The system fell back to the non-HMM regime classifier; this is separate from the market-data freshness path |
| SKEW source discrepancy (Tradier vs C18) | Expected | Architectural dual-source difference, not a freshness bug |
| Off-hours log assertion in `HedgerT217_G05_OffHoursCacheRestore` | Pre-existing unrelated failure | Did not block the freshness fix |
| Upstream stale buckets (FRED, ECO, SENTIMENT, VOL_SURFACE, and others) | Depends on providers / runtime cadence | v3 prevents stale presentation leaks but does not fabricate fresh upstream data |

---

## 18. Suggested Follow-Up

1. Capture a fresh intraday screenshot-and-snapshot pass during the next market session to update the observed values under the new freshness-safe behavior.
2. Fix the separate AAII / NAAIM formatting defect so the hidden sentiment metrics render numerically instead of `nan`.
3. If desired, run a broader GUI regression slice or the full pytest suite for additional confidence beyond the focused freshness path.