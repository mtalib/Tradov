# Spyder Market Data Research
**Date:** 2026-04-08  
**Author:** Codebase Audit  
**Purpose:** Full inventory of every market data signal Spyder consumes, its current
source, and gaps that need to be filled before a production deployment.

---

## 1. Executive Summary

Spyder's 29-module C-Series (Market Data) and 8-module S-Series (Custom Signals)
consume data from a wide variety of sources.  Two primary providers — **Tradier** and
**Massive** (Polygon.io, rebranded October 2025) — have been integrated into the
codebase.  A third provider, **Databento**, was deleted from disk
(`SpyderC26_DatabentoClient.py` does not exist) but is still referenced by stale
imports in several modules.

After a full codebase audit and live Massive/Polygon documentation review (2026-04-08)
the picture is:

- **Coverage is solid** for SPY equity quotes, options chains with Greeks, broker
  order execution, and the core NYSE breadth internals (TICK, ADD, TRIN, VOLD).
- **Massive is more capable than the original audit assumed.** It co-locates with OPRA
  (all 17 US options exchanges), carries Cboe Global Indices (VIX term structure, SKEW),
  has CME/NYMEX futures connections (in beta), and delivers dark pool prints via ADF
  exchange code `D` on the equity trade feed.
- **Databento is NOT needed.** All capabilities it was previously recommended for are
  already available in Massive or will be when futures exit beta.
- **Three modules are still broken** because their live data paths are stubs or have no
  publisher: C11 FuturesBasis (pending Massive futures GA), C04 MarketInternals (8
  unverified CBOE indices), and C30 OrderFlowAnalyzer (Databento stub must be migrated
  to Massive WebSocket).
- **yfinance scraping** is the unofficial fallback for the VIX term structure and SKEW
  index, but these are likely available via Massive `I:` indices — **pending live API
  verification**.
- **CME futures** (`/ES`, `/NQ`) are available in Massive but the REST API is currently
  in beta / "coming soon". Monitor the Massive product roadmap; no separate CME
  subscription is needed.

---

## 2. Current Data Providers

### 2.1  Tradier  (`SpyderB40_TradierClient`)

**Role:** Dual-purpose — primary **broker** (order execution) and **market-quote** feed.

| Capability | Endpoint |
|---|---|
| Equity quotes (including market-internal indices) | `GET /markets/quotes` |
| SPY options chain with live Greeks | `GET /markets/options/chains` |
| Options expirations + strikes | `GET /markets/options/expirations` |
| Multi-leg order placement (IC, CS, straddle, etc.) | `POST /accounts/{id}/orders` |
| Account balances, positions, order history | `/accounts/{id}/...` |
| Historical OHLCV (daily) | `GET /markets/history` |
| Time & Sales | `GET /markets/timesales` |
| Market clock and calendar | `GET /markets/clock` |

**Market-internal indices available via Tradier quotes API:**

| Tradier Symbol | Description |
|---|---|
| `$TICK` | NYSE TICK (net advancing vs declining issues, 1-second) |
| `$TICKQ` | NASDAQ TICK |
| `$ADD` | NYSE Advance-Decline difference |
| `$TRIN` | NYSE TRIN (Arms Index) — volume-weighted breadth |
| `$TRINQ` | NASDAQ TRIN |
| `VIX` | CBOE VIX spot level |

**What Tradier cannot provide:** futures prices, VIX term structure components (VIX9D,
VVIX, VXV, VXMT), put/call ratios, SKEW index, high-low breadth statistics, DXY,
commodities, or any non-option historical Greek data.

---

### 2.2  Massive / Polygon  (`SpyderC27_MassiveClient`, `SpyderC29_DataProviderRouter`)

**Role:** Primary market-data client for everything beyond what Tradier delivers.

| Capability | Method |
|---|---|
| SPY equity NBBO quote (REST) | `get_quote()` |
| Batch equity quotes | `get_quotes_batch()` |
| SPY options chain snapshot with Greeks | `get_option_chain()` |
| Options expirations | `get_option_expirations()` |
| Equity OHLCV bars (any timeframe, any lookback) | `get_historical_bars()` |
| Per-contract options OHLCV bars | `get_option_bars()` |
| Historical options chains (point-in-time, no survivorship bias) | `get_historical_option_chain()` |
| Options flat files (bulk download) | `download_flat_file()` |
| Market status / holidays | `get_market_status()` |
| NYSE breadth indices | `get_market_internals()` ← **added 2026-04-08** |
| WebSocket: real-time SPY quotes / trades / bars | `start_stream()` |

**NYSE breadth indices available via Massive (`list_snapshot_indices`):**

| Massive Symbol | Spyder Internal Name |
|---|---|
| `I:VOLD` | `VOLD` (NYSE Up/Down Volume) |
| `I:TICK` | `TICK` (duplicate of Tradier `$TICK`) |
| `I:ADD` | `ADD` (duplicate of Tradier `$ADD`) |
| `I:TRIN` | `TRIN` (duplicate of Tradier `$TRIN`) |

**Verified Massive capabilities not yet wired into Spyder:**
- OPRA options trade prints from all 17 US exchanges — co-located with OPRA, WebSocket channel `T.O:SPY*`, also available as flat files (`download_flat_file(data_type="options_trades")`)
- CBOE Global Indices (VIX term structure, SKEW) — Massive carries Cboe Global Indices (CGI) as a direct data source; tickers likely available as `I:VIX9D`, `I:VVIX`, `I:VXV`, `I:VXMT`, `I:VXN`, `I:RVX`, `I:SKEW` — **requires live API verification; subscription tier (Indices Advanced, $99/mo) may apply**
- CME/NYMEX futures (`/ES`, `/NQ`, crude oil, gold) — Massive has direct CME/CBOT/COMEX/NYMEX connections (co-located Equinix NJ + ORD11 Chicago) but **Futures REST is currently in beta / "coming soon"**; WebSocket streaming status unconfirmed
- Forex currency pairs including possibly DXY — Massive has WebSocket and REST forex feeds
- Dark pool prints (ADF) — US equity trades with exchange code `D` (FINRA ADF) flow through the equity trade WebSocket (`T.SPY` channel)

**Still not covered by Massive:** put/call ratios (PCALL/PCSP/CPCE — computed metrics, not published as indices by exchanges); new-highs/lows breadth (NYHL/NQHL/SPXHILO — unknown if Massive carries these).

---

### 2.3  yfinance  (unofficial fallback)

Used in: C10, C18, C22, S01, S03, S06.  
**Pattern in all files:** Massive (C29) is tried first; yfinance is the `except` branch.

This is **not a sustainable production data source** — it is an unofficial scraper with
no SLA, no historical tick data, ~15-minute delay for some symbols, and Yahoo Finance
actively rate-limits automated access.

| yfinance Symbol | Used By | Purpose |
|---|---|---|
| `^VIX9D` | C10, S03 | 9-day VIX |
| `^VVIX` | C10 | VIX-of-VIX |
| `^VXV` | C10 | 3-month VIX |
| `^VXMT` | C10 | 6-month VIX |
| `^VXN` | S03 | NASDAQ 100 volatility index |
| `^RVX` | S03 | Russell 2000 volatility index |
| `^SKEW` | C22 | CBOE SKEW index |
| `DX-Y.NYB` | C22 | US Dollar Index (DXY) |
| `CL=F` | C22 | WTI crude oil front-month futures |
| `GC=F` | C22 | Gold front-month futures |
| `SPY` | S01, S06, S08 | SPY spot price (fallback) |
| `^VIX` | S03 | VIX (fallback behind Massive) |

---

### 2.4  FRED API  (`fredapi`)

Used in: C22 FactorDataProvider.  All of these are **daily** updated economic series —
suitable for factor models but not for real-time signal generation.

| FRED Series | Factor Name |
|---|---|
| `F-F_Research_Data_Factors` | SMB, HML (Fama-French 3-factor) |
| `F-F_Research_Data_5_Factors_2x3` | RMW, CMA (Fama-French 5-factor) |
| `F-F_Momentum_Factor` | MOM |
| `BAA10Y` | Credit Spread (Baa-Treasury) |
| `T10Y3M` | Term Spread (10yr–3mo) |
| `DFII10` | 10yr Real Rate (TIPS) |
| `T5YIE` | 5yr Inflation Breakeven |

---

### 2.5  Sentiment APIs  (C35 SentimentAnalyzer)

| Provider | Env Var Required | Data |
|---|---|---|
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` | Financial news headlines |
| Finnhub | `FINNHUB_API_KEY` | Company news |
| Yahoo Finance RSS | (none) | Yahoo news feed |
| Reddit OAuth | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | r/wallstreetbets, r/investing |

If the API keys are absent, C35 returns neutral sentiment without error, silently
degrading the signal.

---

### 2.6  FINRA CDN  (S01 DIXCalculator)

- **URL:** `https://cdn.finra.org/equity/regsho/daily/`  
- **Data:** Daily Regulation SHO short sale volume files for each FINRA-reporting venue  
- **Used for:** DIX (Dark Index) calculation — ratio of dark pool volume to total volume  
- **Frequency:** Once per trading day (files published after market close)  
- **Risk:** Direct unauthenticated HTTP fetch with no circuit breaker or retry logic

---

### 2.7  Databento  — REMOVED / DEAD

`SpyderC26_DatabentoClient.py` **does not exist on disk**.  The module registry
(`SpyderI12`) marks it `REMOVED — superseded by SpyderC29_DataProviderRouter`.

Despite this, dead `import` attempts remain in at least the following files (all guarded
with `HAS_DATABENTO = False`):

- `SpyderC01_DataFeed.py`
- `SpyderC30_OrderFlowAnalyzer.py`
- `SpyderF18_MaxPainCalculator.py`
- `SpyderD27_EarningsStrategy.py`
- `SpyderD28_VIXHedging.py`

`SpyderC30_OrderFlowAnalyzer.py` additionally contains a complete
`DatabentoTickDataSource` class (stub, untested) targeting:
- `OPRA.PILLAR / trades` — for real-time OPRA options trade prints
- `DBEQ.BASIC / trades` — for dark pool prints

**These stubs should be replaced with a `MassiveTickDataSource`** that subscribes to
the Massive options trades WebSocket (`T.O:SPY*` channel) and/or uses
`download_flat_file(data_type="options_trades")` for historical data. Massive
co-locates with OPRA and delivers the same trade-level data from all 17 exchanges —
no Databento subscription is needed.

---

## 3. Module-by-Module Data Gap Analysis

### 3.1  C04 MarketInternals

**Primary consumer of breadth data.**

| Symbol | Description | Source | Status |
|---|---|---|---|
| `TICK` | NYSE TICK | Tradier `$TICK` | ✅ Live |
| `TICKI` | NASDAQ TICK | Tradier `$TICKQ` | ✅ Live |
| `ADD` | NYSE Advance-Decline | Tradier `$ADD` | ✅ Live |
| `TRIN` | NYSE TRIN (Arms Index) | Tradier `$TRIN` | ✅ Live |
| `TRINQ` | NASDAQ TRIN | Tradier `$TRINQ` | ✅ Live |
| `VIX` | CBOE VIX | Tradier `VIX` | ✅ Live |
| `VOLD` | NYSE Up/Down Volume | Massive `I:VOLD` | ✅ Live (wired 2026-04-08) |
| `VIX9D` | 9-day VIX | Event bus — **no publisher** | ❌ Always 0 |
| `PCALL` | Equity put/call ratio | Event bus — **no publisher** | ❌ Always 0 |
| `PCSP` | SPX put/call ratio | Event bus — **no publisher** | ❌ Always 0 |
| `CPCE` | CBOE equity put/call (CPCE) | Event bus — **no publisher** | ❌ Always 0 |
| `SKEW` | CBOE SKEW index | Event bus — **no publisher** | ❌ Always 0 |
| `SPXHILO` | SPX new highs–lows | Event bus — **no publisher** | ❌ Always 0 |
| `NYHL` | NYSE new highs–lows | Event bus — **no publisher** | ❌ Always 0 |
| `NQHL` | NASDAQ new highs–lows | Event bus — **no publisher** | ❌ Always 0 |

**8 of 15 internals are always zero.** These feed into breadth scoring in F-Series and
the Black Swan indicator.

---

### 3.2  C10 VIXAnalyzer

| Symbol | Source | Status |
|---|---|---|
| `VIX` | Tradier (real-time) | ✅ Live |
| `VIX9D` | yfinance `^VIX9D` | ⚠️ Unofficial scrape |
| `VIX` of VIX (`VVIX`) | yfinance `^VVIX` | ⚠️ Unofficial scrape |
| `VXV` (3-month) | yfinance `^VXV` | ⚠️ Unofficial scrape |
| `VXMT` (6-month) | yfinance `^VXMT` | ⚠️ Unofficial scrape |

VIX term structure is essential for Iron Condor sizing, calendar spread valuation, and
regime detection.  Four of five components rely on yfinance scraping.

---

### 3.3  C11 FuturesBasis  ← **Effectively Dead**

This module calculates the ES/SPY arbitrage basis, fair value spread, and carry trade
opportunities.  Both live-data methods are empty stubs:

```python
def _fetch_live_es_data(self) -> ESFuturesData:
    """Fetch live ES futures data from Databento"""
    pass  # Implementation for live ES data fetching

def _fetch_live_spy_data(self) -> SPYData:
    """Fetch live SPY data from Databento"""
    pass  # Implementation for live SPY data fetching
```

The module always falls through to simulated random-walk data.  The risk-free rate is
also hard-coded rather than pulled from FRED or a real-time source.

**Root cause:** CME E-mini ES futures require a CME Group data subscription.  Neither
Tradier nor Massive carries real-time `/ES` prices.

---

### 3.4  C12 DarkPoolFlow

Passive module — it classifies trades fed to it by other modules.  It does not pull data
itself.  Trade venue attribution comes via Massive WebSocket's `T.*` tape (trade)
events, which carry an exchange code.  

The `DARK_POOL_VENUES` list (`SIGMA`, `CROSSFINDER`, `LIQUIDNET`, etc.) are
**ATS names** not exchange codes — the Massive WebSocket delivers SIP exchange codes
(`P`, `Q`, `N`, `D`, etc.).  FINRA ADF dark pool prints arrive with **exchange code
`D`**.  The fix is straightforward: update `C12` to match `exchange == "D"` in
addition to (or instead of) ATS name strings.  No new data source is needed.

---

### 3.5  C18 SKEWCalculator  (and S06)

C18 imports yfinance directly and has not been migrated to C29/Massive:

```python
import yfinance as yf
spy = yf.Ticker("SPY")
chain = spy.option_chain(expiry)
```

S06 has been migrated (Massive → yfinance fallback).  C18 should follow the same
pattern using Tradier's `get_option_chain()` as primary.

---

### 3.6  C22 FactorDataProvider

Stable for factor models (daily).  Main concern: `DOLLAR_INDEX`, `OIL_PRICE`, and
`GOLD_PRICE` are pulled from yfinance (`DX-Y.NYB`, `CL=F`, `GC=F`).  If real-time
macro cross-asset hedging is needed (e.g., for `SpyderD28_VIXHedging`), these would
need to move to a real-time source.

---

### 3.7  C30 OrderFlowAnalyzer  (OPRA L3 ticks)

Contains a complete `DatabentoTickDataSource` stub targeting OPRA tick-level options
data.  Currently inert because:
1. `SpyderC26_DatabentoClient.py` was deleted
2. C30 imports `databento` Python package directly — if the package isn't installed,
   `HAS_DATABENTO = False` and the stub is unreachable
3. The stub has never been run against a live Databento subscription

OPRA options trade data is available directly from Massive (co-located with OPRA,
all 17 exchanges).  **The fix is to replace `DatabentoTickDataSource` in C30 with a
`MassiveTickDataSource`** that subscribes to the Massive options trades WebSocket
(`T.O:SPY*` channel).  This provides the same trade-level data — symbol, size, price,
exchange, timestamp — without any Databento dependency.

---

### 3.8  C35 SentimentAnalyzer

Four external providers, four separate API keys.  If absent from `.env`, sentiment
returns neutral silently.  No Redis/SQLite caching of sentiment scores currently wired
to the event bus.

---

### 3.9  S01 DIXCalculator

Fetches FINRA short-sale volume files from a public CDN over HTTP.  Data is **daily**
(post-market).  The Wikipedia scrape for the S&P 500 component list is extremely fragile
(HTML table format changes break parsing silently).  Consider replacing with a static
JSON file updated quarterly or the Massive snapshot API.

---

### 3.10  S03 BlackSwanIndicator

| Symbol | Meaning | Source |
|---|---|---|
| `^VIX` | CBOE VIX | Massive → Tradier |
| `^VIX9D` | 9-day VIX | Massive → yfinance fallback |
| `^VXN` | NASDAQ 100 VIX | yfinance only — **no Massive equivalent** |
| `^RVX` | Russell 2000 VIX | yfinance only — **no Massive equivalent** |

VXN and RVX are published by CBOE.  Massive carries Cboe Global Indices (CGI) as a
direct data partner, meaning `I:VXN` and `I:RVX` are likely available via Massive’s
indices snapshot API — **pending live API verification**.  If confirmed, the yfinance
fallback for these symbols can be eliminated.

---

## 4. Massive — The Case for Extending Integration

Databento was removed from the codebase (C26 deleted) and **does not need to be
re-integrated**.  Research into the Massive/Polygon platform (conducted 2026-04-08)
reveals that Massive already provides direct access to OPRA options trade prints, CBOE
Global Indices (VIX term structure and SKEW), CME/NYMEX futures (in beta), forex, and
dark pool prints via exchange codes.  The gaps are substantially narrower than the
original audit assumed.

### 4.1  OPRA Options Trade Prints

Massive **co-locates with the Options Price Reporting Authority (OPRA)** and processes
data from all 17 US options exchanges (~3 TB/day).  Real-time options trade prints are
available via:

- **WebSocket:** Subscribe to `T.O:SPY241220C00600000`-style channels (or wildcard
  `O:*` patterns) for every executed options trade including price, size, exchange, and
  timestamp.
- **Flat files:** `download_flat_file(data_type="options_trades")` yields
  `files.polygon.io/v1/options/trades/{date}.csv.gz` — full historical tick-level
  options trades.

The `DatabentoTickDataSource` stub in `SpyderC30_OrderFlowAnalyzer` must be replaced
with a `MassiveTickDataSource` that uses the C27 options trade WebSocket.  No Databento
subscription is required.

### 4.2  CBOE Global Indices (VIX Term Structure, SKEW)

Massive explicitly lists **Cboe Global Indices (CGI)** as a direct exchange data
partner, covering 10,000+ indices.  The following tickers are in all likelihood
available via the `list_snapshot_indices()` REST endpoint and indices WebSocket:

| Likely Massive Symbol | Index | Status |
|---|---|---|
| `I:VIX9D` | CBOE VIX 9-day | ⚠️ Probable — not yet verified via live API |
| `I:VVIX` | CBOE VIX-of-VIX | ⚠️ Probable — not yet verified via live API |
| `I:VXV` | CBOE VIX 3-month | ⚠️ Probable — not yet verified via live API |
| `I:VXMT` | CBOE VIX 6-month | ⚠️ Probable — not yet verified via live API |
| `I:VXN` | CBOE NASDAQ-100 VIX | ⚠️ Probable — not yet verified via live API |
| `I:RVX` | CBOE Russell 2000 VIX | ⚠️ Probable — not yet verified via live API |
| `I:SKEW` | CBOE SKEW Index | ⚠️ Probable — not yet verified via live API |

**Next step:** Call `list_snapshot_indices(tickers=["I:VIX9D","I:VVIX","I:SKEW"])` with
the live Massive API key.  If confirmed, add these to `_MASSIVE_INTERNALS_MAP` in
`SpyderC27_MassiveClient.py` and wire into C04 and C10, eliminating all yfinance
fallbacks.  Note: real-time index streaming requires the **Indices Advanced** plan
($99/mo).

### 4.3  CME / NYMEX Futures (Beta)

Massive has direct connections to CME, CBOT, COMEX, and NYMEX, physically co-located
at Equinix NJ (NY4/NY5) and ORD11 (Chicago).  Contracts for `/ES`, `/NQ`, crude oil
(CL), and gold (GC) are in the platform.

**Limitation:** "Futures REST access is currently in beta and coming soon."  WebSocket
streaming availability is unconfirmed.

Action: Monitor the Massive product roadmap (`massive.com/product-roadmap`).  When
futures exit beta, wire `/ES` and `/NQ` into `SpyderC11_FuturesBasis` directly via C27
without any CME subscription.  `C11` should remain stubbed (returning simulated data)
until that point.

### 4.4  Dark Pool Prints

US equity trade events delivered by the Massive real-time WebSocket (`T.SPY` channel)
carry an exchange code field.  Trades executed on FINRA's Alternative Display Facility
(ADF) arrive with **exchange code `D`**.  This covers the dark pool print detection use
case in `SpyderC12_DarkPoolFlow`.

Current issue: `C12` filters against ATS names (`SIGMA`, `CROSSFINDER`, `LIQUIDNET`)
rather than exchange codes.  Fix: match on `exchange == "D"` instead of (or in addition
to) ATS name strings.

---

## 5. Complete Symbol Inventory

The table below lists every market data symbol Spyder needs, its ideal source, its
current source, and whether a gap exists.

### Legend
- ✅ **Live** — real-time data flowing from a supported provider
- ⚠️ **Degraded** — working but unofficial/delayed (yfinance) or daily-only
- ❌ **Missing** — no data flowing; module receives 0 or runs on simulation

---

### 5.1  SPY / Equity Core

| Symbol | Description | Needs | Tradier | Massive | yfinance | Gap? |
|---|---|---|---|---|---|---|
| `SPY` | S&P 500 ETF | Real-time NBBO | ✅ quotes | ✅ WebSocket + REST | ✅ fallback | **None** |
| `SPX` | S&P 500 Index | Real-time | ✅ quotes | ✅ | — | **None** |
| `DIA` | Dow ETF | Real-time | ✅ quotes | ✅ | — | **None** |
| `QQQ` | NASDAQ ETF | Real-time | ✅ quotes | ✅ | — | **None** |
| `IWM` | Russell 2000 ETF | Real-time | ✅ quotes | ✅ | — | **None** |
| `TLT` | 20yr Treasury ETF | Real-time | ✅ quotes | ✅ | — | **None** |
| `LQD` | IG Corporate Bond ETF | Real-time | ✅ quotes | ✅ | — | **None** |
| `UVXY` | VIX 1.5x ETF | Real-time | ✅ quotes | ✅ | — | **None** (not fetched in code despite being in SYMBOL_GROUPS) |

---

### 5.2  SPY / SPX Options Chain

| Data Point | Description | Tradier | Massive | Gap? |
|---|---|---|---|---|
| Options chain (all strikes, one expiry) | Strikes, bids, asks | ✅ | ✅ | **None** |
| Pre-computed Greeks (delta, theta, vega, gamma, rho) | Per-contract | ✅ | ✅ | **None** |
| Implied volatility (per contract) | Per-contract | ✅ | ✅ | **None** |
| Historical options chains (point-in-time) | Backtesting | ❌ | ✅ flat files | **None for backtest** |
| OPRA options trade prints (symbol, size, price, exchange, timestamp) | Flow analysis (C30) | ❌ | ✅ WebSocket `T.O:*` + flat files (co-located with OPRA) | ⚠️ **Available — C30 needs migration from Databento stub to MassiveTickDataSource** |

---

### 5.3  Futures

| Symbol | Description | Tradier | Massive | Gap? |
|---|---|---|---|---|
| `/ES` | E-mini S&P 500 futures (front-month) | ❌ | ⚠️ Beta/coming soon | ❌ **Gap (Massive beta)** |
| `/NQ` | E-mini NASDAQ futures | ❌ | ⚠️ Beta/coming soon | ❌ **Gap (Massive beta)** |
| `CL=F` | WTI Crude Oil front-month | ❌ | ⚠️ Beta/coming soon | ⚠️ yfinance + Massive beta |
| `GC=F` | Gold front-month | ❌ | ⚠️ Beta/coming soon | ⚠️ yfinance + Massive beta |

---

### 5.4  VIX / Volatility Indices

| Symbol | Description | Tradier | Massive | yfinance | Gap? |
|---|---|---|---|---|---|
| `VIX` | CBOE VIX (30-day) | ✅ | ✅ `I:VIX` | ✅ | **None** |
| `VIX9D` | CBOE VIX 9-day | ❌ | ⚠️ Probable `I:VIX9D` (verify) | ⚠️ fallback | ⚠️ Likely Massive — needs API verification |
| `VVIX` | VIX of VIX | ❌ | ⚠️ Probable `I:VVIX` (verify) | ⚠️ fallback | ⚠️ Likely Massive — needs API verification |
| `VXV` | CBOE 3-month VIX | ❌ | ⚠️ Probable `I:VXV` (verify) | ⚠️ fallback | ⚠️ Likely Massive — needs API verification |
| `VXMT` | CBOE 6-month VIX | ❌ | ⚠️ Probable `I:VXMT` (verify) | ⚠️ fallback | ⚠️ Likely Massive — needs API verification |
| `VXN` | CBOE NASDAQ VIX | ❌ | ⚠️ Probable `I:VXN` (verify) | ⚠️ fallback | ⚠️ Likely Massive — needs API verification |
| `RVX` | CBOE Russell 2000 VIX | ❌ | ⚠️ Probable `I:RVX` (verify) | ⚠️ fallback | ⚠️ Likely Massive — needs API verification |

---

### 5.5  Market Internals / Breadth

| Symbol | Description | Tradier | Massive | Gap? |
|---|---|---|---|---|
| `$TICK` / `TICK` | NYSE TICK | ✅ | ✅ `I:TICK` | **None** |
| `$TICKQ` / `TICKI` | NASDAQ TICK | ✅ | — | **None (Tradier)** |
| `$ADD` / `ADD` | NYSE Advance-Decline | ✅ | ✅ `I:ADD` | **None** |
| `$TRIN` / `TRIN` | NYSE Arms Index | ✅ | ✅ `I:TRIN` | **None** |
| `$TRINQ` / `TRINQ` | NASDAQ Arms Index | ✅ | — | **None (Tradier)** |
| `VOLD` | NYSE Up/Down Volume | ❌ | ✅ `I:VOLD` | **None** (wired 2026-04-08) |
| `VIX9D` | 9-day VIX (breadth use) | ❌ | ⚠️ Probable `I:VIX9D` | ⚠️ Likely Massive — verify |
| `PCALL` | Equity put/call ratio | ❌ | ❌ | ❌ **Gap — CBOE subscription or compute from options data** |
| `PCSP` | SPX put/call ratio | ❌ | ❌ | ❌ **Gap — CBOE subscription or compute from options data** |
| `CPCE` | CBOE equity P/C (CPCE) | ❌ | ❌ | ❌ **Gap — CBOE subscription or compute from options data** |
| `SKEW` | CBOE SKEW index | ❌ | ⚠️ Probable `I:SKEW` | ⚠️ Likely Massive — verify |
| `SPXHILO` | SPX new highs–new lows | ❌ | ❌ | ❌ **Gap** |
| `NYHL` | NYSE new highs–new lows | ❌ | ❌ | ❌ **Gap** |
| `NQHL` | NASDAQ new highs–new lows | ❌ | ❌ | ❌ **Gap** |

---

### 5.6  Macro / Cross-Asset

| Symbol | Description | Tradier | Massive | FRED | yfinance | Gap? |
|---|---|---|---|---|---|---|
| `DX-Y.NYB` / DXY | US Dollar Index | ❌ | ⚠️ Likely via Massive forex | ❌ | ⚠️ Degraded (yfinance) — verify Massive forex ticker |
| `CL=F` | WTI Crude Oil | ❌ | ⚠️ Beta/coming soon | ❌ | ⚠️ Degraded (yfinance) + Massive beta |
| `GC=F` | Gold | ❌ | ⚠️ Beta/coming soon | ❌ | ⚠️ Degraded (yfinance) + Massive beta |
| Credit Spread (`BAA10Y`) | Baa–Treasury yield spread | — | — | ✅ daily | — | **None for daily** |
| Term Spread (`T10Y3M`) | 10yr–3mo spread | — | — | ✅ daily | — | **None for daily** |
| Real Rate (`DFII10`) | 10yr TIPS real rate | — | — | ✅ daily | — | **None for daily** |
| Inflation Breakeven (`T5YIE`) | 5yr breakeven | — | — | ✅ daily | — | **None for daily** |

---

### 5.7  Dark Pool / Short Volume

| Data Point | Description | Source | Frequency | Gap? |
|---|---|---|---|---|
| DIX (Dark Index) | Dark pool volume ratio | FINRA CDN (S01) | Daily (post-market) | **None (daily)** |
| Dark pool venue prints | Per-trade venue attribution (ADF = exchange code `D`) | Massive WebSocket `T.*` tape | Real-time | ✅ ADF = exchange code `D`; fix C12 to match on `exchange=="D"` |
| Dark pool block trades (bulk historical) | Large prints, historical | Massive flat files (`download_flat_file()`) | Daily batch | ✅ Available via Massive flat files |

---

### 5.8  Options Flow (L3)

| Data Point | Description | Source | Gap? |
|---|---|---|---|
| OPRA trade prints | Every options trade: symbol, size, price, exchange, timestamp | Massive WebSocket `T.O:*` (co-located with OPRA) + flat files | ⚠️ **Available — C30 `DatabentoTickDataSource` must be replaced with `MassiveTickDataSource`** |
| Sweep detection | Multi-exchange aggressive orders | Requires OPRA prints | ⚠️ Blocked until C30 migration complete |
| Block print detection | Single large options trades | Requires OPRA prints | ⚠️ Blocked until C30 migration complete |
| Unusual options activity (volume vs OI) | Available without L3 | Tradier + Massive option chain | ✅ Working |

---

### 5.9  Factor Model Data (daily, C22)

| Series | Provider | Gap? |
|---|---|---|
| MKT (excess return) | Massive → yfinance | **None** |
| SMB, HML | FRED (`F-F_Research_Data_Factors`) | **None (daily)** |
| RMW, CMA | FRED (`F-F_Research_Data_5_Factors_2x3`) | **None (daily)** |
| MOM | FRED (`F-F_Momentum_Factor`) | **None (daily)** |
| VIX level/term (VIX_TERM factor) | yfinance `^VIX9D` required | ⚠️ Degraded |
| SKEW factor | yfinance `^SKEW` | ⚠️ Degraded |
| DXY factor | yfinance `DX-Y.NYB` | ⚠️ Degraded |
| Oil factor | yfinance `CL=F` | ⚠️ Degraded |
| Gold factor | yfinance `GC=F` | ⚠️ Degraded |

---

### 5.10  Sentiment / News (C35)

| Data Type | Provider | API Key | Gap? |
|---|---|---|---|
| Financial news headlines | Alpha Vantage | `ALPHA_VANTAGE_API_KEY` | ⚠️ Key required |
| Company news | Finnhub | `FINNHUB_API_KEY` | ⚠️ Key required |
| News RSS | Yahoo Finance | None | ⚠️ Unofficial |
| Reddit sentiment | Reddit OAuth | `REDDIT_CLIENT_ID/SECRET` | ⚠️ Keys required |

---

## 6. Recommended Action Matrix

### Priority 1 — Critical (breaks strategies silently)

| Action | Files | Effort |
|---|---|---|
| Verify Massive CBOE indices — call `list_snapshot_indices(tickers=["I:VIX9D","I:VVIX","I:VXV","I:VXMT","I:VXN","I:RVX","I:SKEW"])` with live API key; if valid, add to `_MASSIVE_INTERNALS_MAP` and wire to C04, C10, S03 | C04, C10, C27, S03 | Low |
| Migrate C30 `DatabentoTickDataSource` → `MassiveTickDataSource` using Massive options trades WebSocket (`T.O:SPY*`) | C30 | Medium |
| Fix C12 dark pool filter: match on `exchange == "D"` (ADF) instead of ATS names | C12 | Low |
| Source put/call ratio data — CBOE provides delayed PCALL/CPCE via direct URL; or compute from Massive options volume/OI data | C04, S03 | Medium |
| Implement SKEW publisher — S06 already computes SKEW; publish to event bus (and once `I:SKEW` verified, replace with live Massive feed) | S06, C04 | Low |
| Fix C11 FuturesBasis — document that Massive futures are in beta; leave stub active but non-crashing; re-enable when Massive futures exit beta | C11 | Low |

### Priority 2 — Important (degrades strategy quality)

| Action | Files | Effort |
|---|---|---|
| Migrate C18 SKEWCalculator from yfinance to Tradier options chain | C18 | Low |
| Add circuit breaker + retry to FINRA CDN fetch in S01 | S01 | Low |
| Replace Wikipedia S&P 500 scrape in S01 with static quarterly JSON | S01 | Low |
| Remove all dead Databento import guards | C01, C30, F18, D27, D28 | Low |

### Priority 3 — Future (expand coverage)

| Action | Benefit | Requires |
|---|---|---|
| Wire Massive futures (`/ES`, `/NQ`) when REST API exits beta | Enable C11 FuturesBasis with real ES data | Monitor Massive product roadmap |
| Verify and wire DXY via Massive forex (`C:EURUSD` basket or forex ticker) | Replace yfinance for DXY | Live Massive API test |
| Source NYHL / NQHL / SPXHILO | Complete breadth picture | Verify if Massive carries these indices via `list_snapshot_indices()` |
| Replace remaining yfinance fallbacks with Massive CBOE index tickers | Eliminate unofficial scraping | Subject to Section 4.2 verification result |

---

## 7. Provider Recommendation Framework

When evaluating providers, these are the must-have capabilities in priority order:

1. **SPY options chain with real-time Greeks** — currently ✅ Massive + Tradier (both covered)
2. **VIX term structure (VIX9D, VVIX, VXV, VXMT)** — currently ⚠️ yfinance; **⚠️ probable via Massive `I:` indices — verify first**
3. **Put/call ratios (PCALL, CPCE, PCSP)** — currently ❌ missing; CBOE provides delayed data via direct URL or compute from Massive options data
4. **CBOE SKEW index** — currently ❌ missing (S06 computes locally); **⚠️ probable via Massive `I:SKEW` — verify**
5. **CME E-mini ES futures real-time** — currently ❌ C11 is dead; **⚠️ Massive has CME feed (beta / coming soon)**
6. **OPRA options trade prints** — currently ❌ (C30 uses Databento stub); **✅ Massive WebSocket `T.O:*` is the solution — migrate C30**
7. **Dark pool venue prints** — currently ⚠️ (ATS name mismatch); **✅ ADF = exchange code `D` in Massive trade stream — fix C12**
8. **Tradier (keep)** — unique value: broker execution + `$TICK`/`$ADD`/`$TRIN` real-time

**Massive covers items 1, 6, 7 today** (with code changes). **Massive likely also covers items 2 and 4** (pending `I:` index verification). **Item 5 is coming soon** (Massive futures beta). **Item 3 requires a separate CBOE data source or computation from existing Massive options data.**

**Databento is NOT needed.** All capabilities it was considered for are
either already available in Massive or will be when futures exit beta.

**Massive** is the right primary market data provider. The action is to extend
the existing C27 integration, not to add a second provider.

**Tradier** must be retained as the broker and should continue to be the source of
`$TICK`, `$ADD`, `$TRIN` (real-time, free with broker account) and SPY/SPX options
chains (alternative to Massive).

---

## 8. Complete Symbol Reference for Provider Research

The following consolidated list is designed to be sent to any data provider when asking
"can you cover these?"

### Currently Covered (Tradier + Massive combined) ✅

```
# Equity (real-time)
SPY, SPX, DIA, QQQ, IWM, TLT, LQD, UVXY

# Options chains
SPY options (all expirations, all strikes, Greeks, IV)

# Order execution
Market, limit, stop, multi-leg, iron condor, credit spread (via Tradier)

# Market internals
$TICK (NYSE TICK)
$TICKQ (NASDAQ TICK)
$ADD (NYSE Advance-Decline)
$TRIN (NYSE Arms Index)
$TRINQ (NASDAQ Arms Index)
VIX (CBOE 30-day VIX spot)
VOLD (NYSE Up/Down Volume, via Massive I:VOLD)

# Historical
OHLCV bars (any timeframe) for SPY and other US equities
Historical SPY options chains (flat files)
```

### Currently Degraded — yfinance Scraping Only ⚠️

```
# VIX term structure (CBOE indices) — likely available via Massive I: indices (verify)
^VIX9D    — CBOE VIX 9-day           (probably I:VIX9D in Massive — unverified)
^VVIX     — CBOE VIX-of-VIX          (probably I:VVIX in Massive — unverified)
^VXV      — CBOE VIX 3-month         (probably I:VXV in Massive — unverified)
^VXMT     — CBOE VIX 6-month         (probably I:VXMT in Massive — unverified)
^VXN      — CBOE NASDAQ 100 VIX      (probably I:VXN in Massive — unverified)
^RVX      — CBOE Russell 2000 VIX    (probably I:RVX in Massive — unverified)
^SKEW     — CBOE SKEW Index          (probably I:SKEW in Massive — unverified)

# Macro / cross-asset
DX-Y.NYB / DXY   — US Dollar Index
CL=F              — WTI Crude Oil (available in Massive futures — beta/coming soon)
GC=F              — Gold (available in Massive futures — beta/coming soon)
```

### Available in Massive — Not Yet Wired 🔧

```
# OPRA options trade prints (all 17 exchanges)
T.O:SPY*  — Massive WebSocket real-time options trades
          — or download_flat_file(data_type="options_trades") for historical
          — Action: replace DatabentoTickDataSource in C30 with MassiveTickDataSource

# Dark pool (ADF) prints
exchange=D — ADF trades already in Massive equity trade WebSocket T.SPY
           — Action: fix C12 to filter on exchange code 'D' not ATS names
```

### Currently Missing — No Source at All ❌

```
# Market internals (breadth) — computed metrics, no exchange publishes these as indices
PCALL     — CBOE Total Equity Put/Call Ratio
PCSP      — CBOE S&P 500 Put/Call Ratio
CPCE      — CBOE Equity Put/Call (CPCE index)
SPXHILO   — S&P 500 New Highs minus New Lows (unknown if Massive carries)
NYHL      — NYSE New Highs minus New Lows    (unknown if Massive carries)
NQHL      — NASDAQ New Highs minus New Lows   (unknown if Massive carries)

# Futures (real-time) — Massive has CME feed; REST in beta / coming soon
/ES       — CME E-mini S&P 500 Futures (Massive beta — not yet GA)
/NQ       — CME E-mini NASDAQ-100 Futures (Massive beta — not yet GA)
```

---

*End of report.*
