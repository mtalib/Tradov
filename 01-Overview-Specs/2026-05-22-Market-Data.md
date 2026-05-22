# 2026-05-22 Market Data Report
**Date produced:** 2026-05-22  
**Dashboard reference snapshot:** ~09:42 ET, 2026-05-22 (intraday, market open)  
**Dashboard state:** SPY 747.72 (+0.68%), VIX 16.86, REGIME BULL, PMR ARMED  
**Data sources:** `market_data/live_data.json` (G18, ~09:42 ET) + `market_data/overview_metrics_snapshot.json` (S07, 13:42 UTC)

---

## Purpose

This document is the authoritative reference for every symbol and metric displayed on the
Spyder trading dashboard (`SpyderG05_TradingDashboard`).  For each item it records:

- **Data source** (which API / module provides the raw value)
- **Calculation method** (how the value is derived from that source)
- **Update cadence** (how frequently the value refreshes)
- **Observed value** (actual live value as of 09:42 ET on 2026-05-22)
- **Correctness / issues** (any known problems or discrepancies)

The primary reference modules are:

| Module | Role |
|--------|------|
| `SpyderG18_MarketDataWorker` | Background worker that fetches Tradier quotes every 30 s and writes `market_data/live_data.json` |
| `SpyderS07_CustomMetricsOrchestrator` | Orchestrates S-Series custom metrics; emits Qt signals to G05/G10 |
| `SpyderC04_MarketInternals` | Fetches confirmed Tradier index symbols every 5 s; analyses TICK/ADD/TRIN |
| `SpyderS11_TradingViewInternals` | Playwright headless-browser scraper for NYSE breadth internals from TradingView |
| `SpyderC10_VIXAnalyzer` | VIX family regime classification from Tradier / yfinance |
| `SpyderC18_SKEWCalculator` | CBOE SKEW replication from SPY options chain (5-minute update) |
| `SpyderN09_GammaExposure` | GEX/DEX/OGL/VEX/CHEX engine driven by live options chain data |
| `SpyderS01_DIXCalculator` | Dark Index from FINRA ATS off-exchange volume |
| `SpyderS03_BlackSwanIndicator` | 4-component composite tail-risk score (SWAN) |
| `SpyderS12_WRSSignal` | Walmart Recession Signal — macro consumer stress |
| `SpyderS13_PSRSignal` | Pawn Shop Ratio — working-class credit stress |
| `SpyderS09_FREDClient` | FRED macro series (yields, credit spreads) |

---

## 1. Data Sources Overview

### 1.1 Tradier REST API
- **URL (live):** `https://api.tradier.com/v1/markets/quotes`
- **Auth:** Bearer token (`TRADIER_API_KEY`)
- **Primary use:** Equity/ETF/index real-time quotes; historical OHLCV; SPY options chain
- **Confirmed index symbols (current policy):** `VIX`, `ADD`, `TICK`, `TNX`, `XLK`, `XLF`
- **NOT confirmed by Tradier docs:** `$TRIN`, `$TRINQ`, `$TICKQ` — excluded from `TRADIER_FETCHABLE_SYMBOLS` in C04; sourced via S11 only
- **Rate limits:** Token-bucket via `SpyderU40_RateLimiter`; G18 batches all equity symbols into a single call
- **Status:** ✅ Live and healthy as of snapshot

### 1.2 TradingView Playwright Scraper (S11)
- **Module:** `SpyderS11_TradingViewInternals`
- **Method:** Playwright headless Chromium scrapes public TradingView symbol pages
- **Symbols scraped:** `USI-TICK`, `USI-TRIN.NY`, `USI-ADD`, `USI-VOLD`, `USI-UVOL`, `USI-DVOL`; sector ETF breadth
- **NOT available via TradingView:** `USI-NYMO` returns 404 — NYMO is computed from ADD EMA
- **Update:** On-demand via S07 orchestrator timer (~60 s)
- **Status as of snapshot:** BREADTH bucket age = 6312 s (~1.75 h); **stale** as of 09:42 ET last-run

### 1.3 Massive API
- **Client:** `SpyderC27_MassiveClient` / `SpyderC29_DataProviderRouter`
- **Primary use:** Real-time streaming options Greeks, flow, and equity data
- **Env var:** `MASSIVE_API_KEY`
- **Dashboard use:** GEX/DEX/OGL/VEX/CHEX (N09 engine now wired to S07)

### 1.4 yfinance
- **Use:** VIX family supplements (^VIX9D, ^VXV, ^VVIX), SWAN components (^VIX, HYG, LQD, DX-Y.NYB, SPY, TLT), WRS/PSR fallback
- **VXV source in live_data.json confirms:** `"source": "yfinance_vix3m"` at timestamp 1779457289225

### 1.5 FINRA ATS (S01)
- **Use:** Off-exchange (dark pool) volume by security for DIX calculation
- **Coverage:** S&P 500 constituents; market caps cached at `~/.spyder/market_caps_cache/`
- **Today's value:** DIX 43.20% at 13:00 UTC (09:00 ET); file `data/dix_history_20260522.json`
- **Recent trend:** 44.4% (05/18) → 41.0% (05/19) → 41.0% (05/20) → 43.2% (05/21) → 43.2% (05/22)

### 1.6 FRED (S09)
- **Module:** `SpyderS09_FREDClient`
- **Status:** FRED bucket age = 6312 s (~1.75 h); **stale** — uses cached prior-session values
- **Series used:** GS2, GS5, GS10, GS30, T10Y2Y, T10Y3M, DFEDTARU
- **Current YIELD_10Y:** 4.32 (from G18 Tradier TNX; FRED path is stale)

---

## 2. Data Quality Summary (13:42 UTC)

| Bucket | Status | Age | Data Points |
|--------|--------|-----|-------------|
| GEX | ✅ Fresh | 0 s | 105 |
| DEX | ✅ Fresh | 0 s | 105 |
| OGL | ✅ Fresh | 0 s | 105 |
| VEX | ✅ Fresh | 0 s | 105 |
| CHEX | ✅ Fresh | 0 s | 105 |
| SKEW | ✅ Fresh | 0 s | 105 |
| SWAN | ✅ Fresh | 0 s | 105 |
| DIX | ✅ Fresh | 0 s | 105 |
| PCA-IV | ✅ Fresh | 0 s | 105 |
| PCA-PROXY | ✅ Fresh | 0 s | 105 |
| SECTOR_BREADTH | ✅ Fresh | 0 s | 210 |
| DEALER_FLOW | ✅ Fresh | 0 s | 210 |
| **BREADTH** | ⚠️ Stale | 6312 s | 0 |
| **ECO_CALENDAR** | ⚠️ Stale | 6312 s | 0 |
| **FRED** | ⚠️ Stale | 6312 s | 0 |
| **LIQUIDITY** | ⚠️ Stale | 6312 s | 0 |
| **OPTIONS** | ⚠️ Stale | 6312 s | 0 |
| **PREDICTION_MARKETS** | ⚠️ Stale | 6312 s | 0 |
| **SENTIMENT** | ⚠️ Stale | 6312 s | 0 |
| **VOL_SURFACE** | ⚠️ Stale | 6312 s | 0 |
| **MARKET_INTEL** | ⚠️ Stale | 6312 s | 0 |

**SLO:** `overall_quality_ok = true` (≥0.75); `freshness_ok = false` (9/21 buckets stale).  
Overall system narrative (S07 text): *"Market risk is contained (SWAN 1.56). Dark-pool flow is light (DIX 43.2%). Dealers are long gamma (GEX +0.3B). Skew is compressed at 98. Breadth regime: neutral. News flow: bullish. Social sentiment: neutral."*

---

## 3. Major Indices

| Symbol | Last | Change | Chg% | Source | Cadence | Notes |
|--------|------|--------|------|--------|---------|-------|
| **SPY** | 747.72 | +5.00 | +0.68% | G18 / Tradier | 30 s | Primary instrument; drives chart (5-min bars every 60 s) |
| **QQQ** | 720.35 | +5.84 | +0.82% | G18 / Tradier | 30 s | |
| **IWM** | 284.07 | +1.58 | +0.56% | G18 / Tradier | 30 s | |
| **DIA** | 506.36 | +3.25 | +0.65% | G18 / Tradier | 30 s | |

### Extended indices (live_data.json, not displayed on main overview panel)

| Symbol | Last | Change | Chg% | Notes |
|--------|------|--------|------|-------|
| SPX | 7,494.59 | +48.87 | +0.66% | S&P 500 composite |
| NDX | 29,478.89 | +121.62 | +0.42% | Nasdaq-100 |
| RUT | 2,859.14 | +15.92 | +0.56% | Russell 2000 underlying (IWM proxy) |
| $DJI | 50,285.66 | 0.00 | 0.00% | ⚠️ Change not available — Tradier DJI index change field returning zero |

### Market interpretation
All four major indices are advancing with broad participation (+0.56% to +0.82%). Tech (QQQ +0.82%) is the session leader.  Small-caps (IWM/RUT +0.56%) are participating but lagging, consistent with a risk-on but not euphoric tape.

---

## 4. Market Internals

| Symbol | Last | Source | Method | Cadence | Correctness |
|--------|------|--------|--------|---------|-------------|
| **$TICK** | +447 | S11 TradingView | USI-TICK page scrape | ~60 s | ✅ Moderately positive; well within normal intraday range (±1000) |
| **$TRIN** | 0.79 | S11 TradingView | USI-TRIN.NY scrape | ~60 s | ✅ TRIN < 1.0 = advancing volume outpacing advancing issues count; bullish internals |
| **$ADD** | +183 | S11 TradingView | USI-ADD scrape | ~60 s | ✅ Positive net advances; moderate breadth |
| **NYMO** | 0.00 | S07 computed | Online EMA₁₉(ADD) − EMA₃₉(ADD) | Per ADD update | ⚠️ **Approximation only** — USI-NYMO not available on TradingView; shows zero until EMA warms up over ~39 sessions |
| **$VOLD** | +293.9M | S11 TradingView | USI-VOLD page scrape | ~60 s | ✅ Positive volume differential (+293.9M advancing volume above declining); meaningfully bullish |
| **RVOL** | 0.06 | G18 computed | `SPY.volume / SPY.average_volume` | 30 s | ⚠️ Extremely low (0.06) — likely early in the session (~09:42 ET) before volume develops; will normalise toward 1.0 by midday |

### Internals interpretation
TICK +447, TRIN 0.79, ADD +183, VOLD +293.9M all point in the same direction: orderly broad-based buying.  No stress signal anywhere in internals.  RVOL 0.06 confirms it is very early in the session.

### Participation Score (S11)
- **Value:** 65.4% (sector ETF participation; 65.4% of sectors advancing)
- **Breadth Regime:** `bull` (from `BREADTH_REGIME` key)
- **Source:** `SpyderS11_TradingViewInternals` snapshot at 13:44 UTC

---

## 5. Volatility

| Symbol | Last | Change | Chg% | Source | Cadence | Notes |
|--------|------|--------|------|--------|---------|-------|
| **VIX** | 16.86 | +0.10 | +0.60% | G18 / Tradier `VIX` | 30 s | ✅ Live. NORMAL_LOW regime (15–20 band) |
| **VIX9D** | 14.17 | +0.09 | +0.64% | G18 / Tradier `VIX9D` | 30 s | ✅ VIX9D (14.17) < VIX (16.86) → normal contango |
| **VXV** | 20.00 | −0.76 | −3.66% | yfinance `^VXV` | C10 timer | ✅ VIX/VXV = 0.843 → front-month cheap vs 3-month; contango (normal) |
| **VVIX** | 92.71 | +0.83 | +0.91% | G18 / Tradier `VVIX` | 30 s | Volatility-of-volatility; elevated vs typical (85–90) but not alarming |
| **SKEW (G18)** | 136.96 | 0.00 | 0.00% | G18 / Tradier `SKEW` | 30 s | Direct Tradier SKEW index quote; stale change = no new CBOE print yet |
| **SKEW (S07/C18)** | 98.33 | — | — | S07 `SpyderC18_SKEWCalculator` | 5 min | ⚠️ **Discrepancy vs G18 value** — C18 replicates CBOE SKEW from SPY options chain; 98.33 is a compressed OTM skew reading vs the 136.96 Tradier index quote |

### VIX Regime Classification (C10 `VIXLevel` enum)
| Level | Range | Current state |
|-------|-------|---------------|
| EXTREME_LOW | < 10 | |
| LOW | 10–15 | |
| **NORMAL_LOW** | **15–20** | ← VIX 16.86 |
| NORMAL | 20–25 | |
| ELEVATED | 25–30 | |
| HIGH | 30–40 | |
| EXTREME_HIGH | 40–50 | |
| CRISIS | > 50 | |

### VIX Term Structure
| Ratio | Value | Interpretation |
|-------|-------|---------------|
| VIX9D / VIX | 0.840 | Contango (VIX9D < VIX) — normal; no near-term stress |
| VIX / VXV | 0.843 | Contango (VIX < VXV) — normal; 30D cheaper than 3M |
| TERM_SLOPE_0_7 | --- | Stale bucket |
| TERM_SLOPE_7_30 | --- | Stale bucket |

### SKEW Discrepancy Note
The dashboard overview panel displays `136.96` (sourced from G18's Tradier SKEW quote, which carries a stale `+0.00` change because CBOE does not publish intraday SKEW updates).  The S07 orchestrator's C18 calculation from the live SPY options chain produces `98.33`, indicating compressed OTM downside skew relative to ATM — consistent with VOLD positive and a risk-on tape.  Both values are architecturally correct for their respective sources; the discrepancy reflects CBOE's once-daily SKEW publication vs. the intraday options-chain replication.

---

## 6. Options Analytics

| Symbol | Last | Source | Method | Cadence | Correctness |
|--------|------|--------|--------|---------|-------------|
| **IVR** | 10.02 | S07 `_compute_ivr()` | 52-week IV rank: `(ATM_IV − min_52w) / (max_52w − min_52w) × 100` | ~60 s | ✅ Live. 252 history points — sufficient window. Low rank (10) indicates IV is near the bottom of its 52-week range |
| **ATM_IV** | 15.23% | S07 `_compute_atm_iv()` | Average of 6 nearest-ATM SPY options where IV > 0 | ~60 s | ✅ Live. Matches last history entry: `{"date":"2026-05-22","iv":15.23}` |
| **VRP** | +4.69 | S07 `_compute_hv20()` | `ATM_IV (15.23%) − HV20 (~10.54%)` | ~60 s | ✅ Live. Positive VRP = IV > realized vol; options are fairly priced with modest risk premium — normal for a non-stress environment |
| **CPC** | 0.626 | G18 computed | `total_put_vol / total_call_vol` for nearest SPY expiry | 30 s | ✅ Live. CPC 0.626 < 0.70 → elevated call buying vs puts; mildly bullish/complacent tone |

### IV History (252 entries, `data/cache/spy_iv_history.json`)
| Date | ATM_IV |
|------|--------|
| 2026-05-20 | 14.98% |
| 2026-05-21 | 15.23% |
| 2026-05-22 | 15.23% |

**IVR at 10.02** means current ATM_IV (15.23%) is near the 10th percentile of the trailing 52-week range.  This is a low-premium environment.

### CPC Interpretation
- CPC 0.626 = more call volume than put volume; market participants are leaning bullish/hedging less
- Historical context: CPC < 0.70 often coincides with near-term complacency; not an actionable signal alone

---

## 7. Bonds & Credit

| Symbol | Last | Change | Chg% | Source | Notes |
|--------|------|--------|------|--------|-------|
| **TLT** | 84.53 | +0.31 | +0.37% | G18 / Tradier | 20+ year Treasury ETF |
| **HYG** | 80.00 | +0.10 | +0.13% | G18 / Tradier | High-yield credit; also SWAN credit component |
| **LQD** | 108.45 | +0.28 | +0.26% | G18 / Tradier | Investment-grade credit; also SWAN HYG/LQD ratio |
| **TNX** | 4.32 | +0.07 | +1.65% | G18 / Tradier + S09 FRED | 10-year yield %; Tradier TNX index is primary live source; FRED GS10 is stale |

### Yield Curve (S09 / YIELD metrics)
| Key | Value | Notes |
|-----|-------|-------|
| YIELD_10Y | 4.32 | TNX from G18 Tradier fetch |
| YIELD_SLOPE | 0.54 | Approximate 10Y − 2Y spread; positive → curve not inverted |
| YIELD_INVERTED | false | Curve is positively sloped |

TNX rising +1.65% on the day while equities advance suggests a growth-driven rate move rather than a risk-off flight to safety.  HYG +0.13% and LQD +0.26% confirm credit spreads are benign.

---

## 8. Correlations & Sector Proxies

| Symbol | Last | Change | Chg% | Source | Notes |
|--------|------|--------|------|--------|-------|
| **UUP (DXY proxy)** | 27.77 | +0.05 | +0.16% | G18 / Tradier `UUP` | Remapped via `_SYMBOL_REMAP["DXY"] = "UUP"`; not a true DXY index |
| **GLD** | 414.74 | −2.25 | −0.54% | G18 / Tradier | Gold declining with USD slightly higher and risk-on appetite |
| **USO** | 142.22 | −0.32 | −0.23% | G18 / Tradier | Oil modestly lower; no energy stress signal |
| **XLK** | 180.92 | +2.32 | +1.30% | G18 / Tradier | Tech leading; confirms QQQ outperformance |
| **XLF** | 52.05 | +0.32 | +0.62% | G18 / Tradier | Financials participating |

---

## 9. Custom Metrics

### 9.1 GEX — Net Gamma Exposure

| Attribute | Value |
|-----------|-------|
| **Value** | +0.264B (+$264M) |
| **Formatted display** | `+0.3B` |
| **Source** | N09 GammaExposure engine (now wired to S07 orchestrator) |
| **Data feed** | OPTIONS chain via `SpyderB40_TradierClient` |
| **Interpretation** | Dealers are net long gamma → they sell rallies and buy dips → volatility suppression expected |
| **GEX_REGIME** | `moderate_positive` (from `DEALER_FLOW` key) |
| **Zero gamma level** | N/A (no zero-gamma strike resolved at this snapshot — `ZERO_GAMMA` = `---`) |
| **Wall confidence** | 0.00 (no strong call or put wall identified) |
| **Freshness** | ✅ Age 0 s, 105 data points |

### 9.2 DEX — Delta Exposure

| Attribute | Value |
|-----------|-------|
| **Value** | +687.0M ($687M delta exposure) |
| **Formatted display** | `687M` |
| **Source** | N09 engine (previously stub; now live) |
| **Interpretation** | Dealers are carrying significant long delta; supportive of upside |
| **Freshness** | ✅ Age 0 s |

### 9.3 OGL — Open-Interest Gamma Level (Anchor Strike)

| Attribute | Value |
|-----------|-------|
| **Value** | 735.00 |
| **Formatted display** | `735.00` |
| **Source** | `LIQUIDITY_DIAGNOSTICS` anchor strike from S07 |
| **Interpretation** | Highest open-interest strike for today's SPY expiry (2026-05-22 0DTE) is 735 |
| **Liquidity candidates at 735** | 6 candidates evaluated; all failing spread gates (spread_abs > 0.20 for calls; spread_pct > 0.12 for puts) — gate pressure in 0DTE options today |
| **Freshness** | ✅ Age 0 s |

### 9.4 VEX — Vanna Exposure

| Attribute | Value |
|-----------|-------|
| **Value** | +13.6M |
| **Formatted display** | `13.6M` |
| **Source** | N09 engine |
| **Interpretation** | Positive vanna: as IV falls, dealers buy delta (tailwind for upside moves on vol compression) |
| **Freshness** | ✅ Age 0 s |

### 9.5 CHEX — Charm Exposure

| Attribute | Value |
|-----------|-------|
| **Value** | −307,146 |
| **Formatted display** | `−307146.08` |
| **Source** | N09 engine |
| **Interpretation** | Negative charm: as time passes intraday, dealers lose delta (slight headwind from time decay toward close) |
| **Freshness** | ✅ Age 0 s |

### 9.6 DIX — Dark Index

| Attribute | Value |
|-----------|-------|
| **Value** | 43.20% |
| **Status** | BULLISH (threshold ≥ 43%) |
| **Source** | `SpyderS01_DIXCalculator` |
| **Primary data** | FINRA ATS off-exchange prints; computed at 09:00 ET daily |
| **Formula** | `DIX = Σ(dark_dollar_volume) / Σ(total_dollar_volume)` across S&P 500 |
| **File** | `data/dix_history_20260522.json` at timestamp 13:00 UTC |
| **5-day trend** | 44.4% → 41.0% → 41.0% → 43.2% → **43.2%** (recovering from mid-week dip) |
| **Interpretation** | DIX is at the bullish threshold. Dark-pool participation is slightly light but not bearish; consistent with the system narrative |

### 9.7 PCA-Proxy — Market Factor Proxy

| Attribute | Value |
|-----------|-------|
| **Value** | +0.585 |
| **Change** | −1.804 (−75.5% from prior) |
| **Regime band** | `Balanced` |
| **Regime color** | `#9bb` (teal/neutral) |
| **Regime note** | "The common factor is present, but internal breadth is still mixed." |
| **Method** | PCA on 11 SPDR sector ETFs (XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLK, XLU); PC1 score as market-factor proxy |
| **Details** | PC1_score = 0.679; PC2_abs = 0.641; explained_variance = 36.1%; spectral_gap = 2.35; confidence = 0.451 |
| **History window** | 20 sessions (2026-04-24 → 2026-05-21) |
| **Source** | Tradier live sector ETF quotes |
| **Freshness** | ✅ Timestamp 11:58 UTC (live-seeded) |

### 9.8 PCA-IV — IV Surface Factor

| Attribute | Value |
|-----------|-------|
| **Value** | −1.339 |
| **Change** | −0.001 (negligible) |
| **Regime band** | `Surface twist` |
| **Regime color** | `#f2b134` (amber/caution) |
| **Regime note** | "Secondary curvature and skew effects are large relative to the main IV factor." |
| **Method** | PCA on 7 SPY IV surface features (level, front_curve, back_curve, curve_butterfly, term_twist, skew, convexity) |
| **Details** | PC1_score = −1.502; PC2_abs = 1.135; explained_variance = 39.2%; feature_skew = −1.937; feature_level = 0.147 |
| **Phase** | `live-seeding` (readiness 50%; 60 of 120 target snapshots accumulated since 2026-02-17) |
| **History path** | `data/cache/pca_iv_surface_history/spy_iv_surface_features.jsonl` |
| **Last snapshot** | 2026-05-10 (stored 60 snapshots) |
| **Freshness** | ✅ Age 0 s |

### 9.9 WRS — Walmart Recession Signal

| Attribute | Value |
|-----------|-------|
| **Raw value** | 0.01534 |
| **Formatted display** | `0.02` |
| **Formula** | `WRS = Price(WMT) / LUXURY_INDEX` |
| **Luxury basket** | LVMUY, CFRUY, HESAY, PPRUY, BURBY, SWGAY, RACE, TPR, CPRI (9 ADRs; equal-weight daily-return compounding, base 100) |
| **Primary data** | Tradier REST `/markets/history`; yfinance fallback |
| **Cache** | `~/.spyder/wrs_cache/` — individual CSV per constituent (10 tickers cached) |
| **Cadence** | Daily close; 4-hour TTL |
| **Note** | Raw ratio appears small (≈0.015) because WMT (~$80) ÷ LUXURY_INDEX (base-100 compounded series) |

### 9.10 PSR — Pawn Shop Ratio

| Attribute | Value |
|-----------|-------|
| **Value** | 5.020 |
| **Formula** | `PSR = (Price(FCFS) + Price(EZPW)) / Price(XLF)` |
| **Components** | FCFS = FirstCash Holdings; EZPW = EZCORP; XLF = Financial Sector SPDR |
| **Interpretation** | Tracks working-class credit exhaustion; leads recession data by months. PSR elevated alongside WRS would signal systemic stress. Current value alone is not alarming. |
| **Source** | Tradier primary; yfinance fallback |

### 9.11 SWAN — Black Swan Indicator

| Attribute | Value |
|-----------|-------|
| **Value** | 1.56 |
| **Status** | GREEN |
| **Alert level** | LOW |
| **Formula** | 4-component composite: volatility_score, credit_stress_score, liquidity_score, market_internals_score |
| **Most recent component scores (2026-05-20 CSV)** | volatility=1.85, credit_stress=1.09, liquidity=1.50, market_internals=1.90 |
| **Interpretation** | SWAN < 2.0 = low tail-risk environment; GREEN. No black-swan precursors. |
| **Source** | `SpyderS03_BlackSwanIndicator` |
| **Freshness** | ✅ Age 0 s |

### 9.12 PMR — Paper Mode Relay

| Attribute | Value |
|-----------|-------|
| **Value** | ARMED |
| **Trading mode** | PAPER |
| **Interpretation** | Strategy engine is armed and ready to place paper trades |

---

## 10. Hidden / Background Metrics

These metrics are computed and stored in `overview_metrics_snapshot.json` but do not appear on the main dashboard overview panel.

### 10.1 Sentiment & Survey Data

| Metric | Value | Source | Notes |
|--------|-------|--------|-------|
| AAII Bullish % | 22.6% | AAII weekly survey | ⚠️ Formatted as `nan%` (display bug — value present but formatter failing) |
| NAAIM Exposure | 77.34 | NAAIM weekly survey | ⚠️ Formatted as `nan` (same display bug pattern) |

AAII bullish at 22.6% is historically very low (average ~38%). Combined with NAAIM at 77.34 (managers are invested but retail is bearish), this is a classic contrarian-bullish setup: professional money is deployed despite deep retail pessimism.

### 10.2 News Flow

| Metric | Value | Notes |
|--------|-------|-------|
| NEWS_FLOW_VERDICT | **Bullish** | Aggregate news flow scoring |
| NEWS_FLOW_EQUITIES | 0.249 | Normalized equity news sentiment score |
| NEWS_FLOW_HEADLINE | "WEC Energy Group stock: steady regulated utility with dividend focus" | Current leading headline |
| NEWS_FLOW_MACRO | --- | Stale / no macro news event captured |

### 10.3 Economic Calendar

| Metric | Value | Notes |
|--------|-------|-------|
| ECO_NEXT_EVENT_NAME | PCE | Next scheduled macro event |
| ECO_NEXT_EVENT_MINUTES | 10,008 min (~6.9 days) | Next PCE release is ~1 week away |
| ECO_STAND_DOWN | `false` (`clear`) | No economic stand-down in effect |

### 10.4 Dealer Flow & Gamma Walls

| Metric | Value | Notes |
|--------|-------|-------|
| DEALER_FLOW regime | `moderate_positive` | Dealer net positioning direction |
| DEALER_FLOW dealer_position | `unknown` | Specific position not resolved |
| ZERO_GAMMA | --- | Zero-gamma strike not resolved (wall confidence = 0.00) |
| WALL_CONFIDENCE | 0.00 | No dominant call or put wall detected |
| VANNA_PRESSURE | --- | Stale (OPTIONS bucket stale) |
| CHARM_PRESSURE | --- | Stale |
| FLOW_IMBALANCE | --- | Stale |
| RR_25D | --- | 25-delta risk reversal; stale |
| FLY_25D | --- | 25-delta butterfly; stale |

### 10.5 Sector Breadth (S11)

| Metric | Value | Notes |
|--------|-------|-------|
| BREADTH_REGIME | `bull` | Computed from sector participation |
| PARTICIPATION_SCORE | 65.4% | 65.4% of sectors advancing |
| SECTOR_ADV_DEC | 183 | Matches $ADD value — sectors advancing over declining |
| BREADTH_CYCLICAL | --- | TradingView scrape returned NaN |
| BREADTH_DEFENSIVE | --- | TradingView scrape returned NaN |
| BREADTH_SPREAD | --- | TradingView scrape returned NaN |
| SECTOR_MOMENTUM_DISPERSION | --- | Not calculated |
| Source | `SpyderS11_TradingViewInternals` snapshot at 13:44 UTC |

### 10.6 IV Term Structure Detail

| Metric | Value | Notes |
|--------|-------|-------|
| ATM_IV_0DTE | --- | Not computed this session (OPTIONS bucket stale) |
| ATM_IV_1DTE | --- | Stale |
| ATM_IV_7DTE | --- | Stale |
| ATM_IV_30DTE | --- | Stale |
| TERM_SLOPE_0_7 | --- | Stale |
| TERM_SLOPE_7_30 | --- | Stale |
| SURFACE_CONFIDENCE | --- | Stale (VOL_SURFACE bucket age 6312 s) |
| SURFACE_AGE_MS | --- | Stale |

---

## 11. Overall Market Interpretation (09:42 ET, 2026-05-22)

| Dimension | Signal | Reading |
|-----------|--------|---------|
| Price | All four major indices advancing | Bullish |
| Breadth | TICK +447, ADD +183, VOLD +293.9M, TRIN 0.79 | Bullish |
| Sector participation | 65.4%, BREADTH_REGIME = bull | Bullish |
| Volatility | VIX 16.86 NORMAL_LOW; term structure in contango | Neutral / Benign |
| Credit | HYG/LQD both rising; spreads not widening | Bullish |
| Bonds | TLT +0.37%, TNX +1.65% (rates rising with equities) | Growth-driven move |
| Gamma regime | GEX +0.3B (dealers long gamma) → volatility suppression | Bullish / Range-bound |
| Dark pools | DIX 43.2% at threshold; institutional flow neutral-to-light | Neutral |
| Options sentiment | CPC 0.626 (call-heavy), IVR 10 (low IV rank) | Complacent / Bullish |
| Tail risk | SWAN 1.56 GREEN | Low |
| Macro | ECO_STAND_DOWN = false; PCE in ~7 days | No near-term catalyst |
| News | Bullish | Bullish |
| Survey sentiment | AAII Bullish 22.6% (contrarian bullish) | Bullish contrarian |
| Professional positioning | NAAIM 77.34 (deployed) | Bullish |

**System PMR:** ARMED (paper mode)  
**S07 summary text:** *"Market risk is contained (SWAN 1.56). Dark-pool flow is light (DIX 43.2%). Dealers are long gamma (GEX +0.3B). Skew is compressed at 98. Breadth regime: neutral. News flow: bullish. Social sentiment: neutral."*
