# Spyder — Complete Market Data Reference

> **Last Updated:** March 17, 2026  
> **Author:** Generated from source code analysis  
> **Scope:** All symbols, feeds, datasets, schemas, and external data sources used by the Spyder trading system

---

## Table of Contents

1. [Primary Trading Instruments](#1-primary-trading-instruments)
2. [Market Internals](#2-market-internals)
3. [Volatility Symbols](#3-volatility-symbols)
4. [Futures & Index Symbols](#4-futures--index-symbols)
5. [Options Data & OPRA](#5-options-data--opra)
6. [Sector ETFs & Index Components](#6-sector-etfs--index-components)
7. [Dark Pool & Order Flow Signals](#7-dark-pool--order-flow-signals)
8. [Sentiment & News Data Sources](#8-sentiment--news-data-sources)
9. [Databento Datasets & Schemas](#9-databento-datasets--schemas)
10. [Tradier API Endpoints](#10-tradier-api-endpoints)
11. [Third-Party API Endpoints](#11-third-party-api-endpoints)
12. [Option Symbol Format Reference](#12-option-symbol-format-reference)
13. [Missing / Planned Symbols](#13-missing--planned-symbols)
14. [Environment Variable Reference](#14-environment-variable-reference)

---

## 1. Primary Trading Instruments

| Symbol | Description | Format | Source Module |
|--------|-------------|--------|---------------|
| `SPY` | SPDR S&P 500 ETF Trust — primary trading instrument | Plain ticker | All modules |
| `SPX` | S&P 500 Index (cash) — reference index | Plain ticker | `SpyderU07_Constants.py` |
| `VIX` | CBOE Volatility Index — referenced as index | Plain ticker | `SpyderU07_Constants.py`, `SpyderC04_MarketInternals.py` |

**Key constants** (from `SpyderU07_Constants.py`):
```python
PRIMARY_SYMBOL   = "SPY"
OPTION_SYMBOLS   = ["SPY"]
INDEX_SYMBOLS    = ["SPX", "VIX"]
OPTION_MULTIPLIER = 100          # Standard 100-share multiplier
```

---

## 2. Market Internals

All symbols below are defined in `SpyderC_MarketData/SpyderC04_MarketInternals.py`.
**Live data source: Tradier API** — fetched every 5 seconds via `get_quotes()` using the `$`-prefixed symbols. The remaining symbols (VOLD, VIX9D, put/call ratios, etc.) are updated via event-bus broadcast from other modules.

| Internal Key | Tradier Symbol | Exchange | Description | Source |
|-------------|----------------|----------|-------------|--------|
| `TICK` | `$TICK` | NYSE | NYSE Tick Index — net uptick minus downtick stocks | ✅ Tradier live |
| `TICKI` | `$TICKQ` | NASDAQ | Nasdaq Tick Index | ✅ Tradier live |
| `ADD` | `$ADD` | NYSE | NYSE Advance/Decline Line — breadth indicator | ✅ Tradier live |
| `TRIN` | `$TRIN` | NYSE | Arms Index (TRIN) — price × volume breadth | ✅ Tradier live |
| `TRINQ` | `$TRINQ` | NASDAQ | Nasdaq Arms Index | ✅ Tradier live |
| `VIX` | `VIX` | CBOE | 30-day implied volatility index | ✅ Tradier live |
| `VOLD` | `NYSE:VOLD` | NYSE | NYSE Up/Down Volume ratio | ⚠️ Event-bus only |
| `VIX9D` | `INDEX:VIX9D` | CBOE | 9-day implied volatility index | ⚠️ Event-bus only |
| `PCALL` | `INDEX:PCALL` | CBOE | Put/Call Ratio — All options | ⚠️ Event-bus only |
| `PCSP` | `INDEX:PCSP` | CBOE | Put/Call Ratio — SPX options only | ⚠️ Event-bus only |
| `CPCE` | `INDEX:CPCE` | CBOE | CBOE Equity Put/Call Ratio | ⚠️ Event-bus only |
| `SKEW` | `INDEX:SKEW` | CBOE | CBOE SKEW Index — tail risk measure | ⚠️ Event-bus only |
| `SPXHILO` | `NYSE:SPXHILO` | NYSE | S&P 500 New 52-week Highs/Lows | ⚠️ Event-bus only |
| `NYHL` | `NYSE:NYHL` | NYSE | NYSE New 52-week Highs/Lows | ⚠️ Event-bus only |
| `NQHL` | `NASDAQ:NQHL` | NASDAQ | Nasdaq New 52-week Highs/Lows | ⚠️ Event-bus only |

> ✅ = fetched directly from Tradier every 5 seconds  
> ⚠️ = passive — only updated if another module publishes a `MARKET_DATA` event with that symbol

### Market Internals Thresholds

| Symbol | Bullish Threshold | Bearish Threshold | Extreme High | Extreme Low |
|--------|-------------------|-------------------|-------------|------------|
| TICK | > +600 | < -600 | +1000 | -1000 |
| TRIN | < 0.7 | > 1.3 | — | — |
| VIX | < 15 (low regime) | > 25 (high regime) | 50 | 10 |

---

## 3. Volatility Symbols

### 3a. VIX Term Structure

All defined in `SpyderC_MarketData/SpyderC10_VIXAnalyzer.py`.  
**Primary VIX** is fetched via Tradier (real-time, authenticated). Extended term-structure symbols use yfinance as Tradier does not carry them — they are slowly-moving and acceptable for regime classification purposes.

| Key | yfinance Symbol | Description | Tenor | Live Source |
|-----|----------------|-------------|-------|-------------|
| `VIX` | `^VIX` | CBOE Volatility Index | 30-day | ✅ Tradier (`VIX`) with yfinance fallback |
| `VIX9D` | `^VIX9D` | CBOE 9-Day Volatility Index | 9-day | ⚠️ yfinance only |
| `VVIX` | `^VVIX` | Volatility of VIX ("vol of vol") | 30-day | ⚠️ yfinance only |
| `VXV` | `^VXV` | CBOE 3-Month Volatility Index | 90-day | ⚠️ yfinance only |
| `VXMT` | `^VXMT` | CBOE 6-Month Volatility Index | 180-day | ⚠️ yfinance only |
| `VXST` | `^VXST` | CBOE Short-Term Volatility Index | 9-day (alias) | ⚠️ yfinance only |

### 3b. VIX Term Structure Pairs

Defined in `SpyderC10_VIXAnalyzer.py` as `TERM_STRUCTURE_PAIRS`. Used to detect contango vs. backwardation:

| Near Leg | Far Leg | Signal |
|----------|---------|--------|
| `VIX9D` | `VIX` | Short-term vs 30-day slope |
| `VIX` | `VXV` | 30-day vs 3-month slope |
| `VXV` | `VXMT` | 3-month vs 6-month slope |

### 3c. VIX Regime Thresholds

| Regime | VIX Range | Classification |
|--------|-----------|----------------|
| Extreme Low | < 10 | Complacency |
| Low | 10 – 15 | Low volatility |
| Normal | 15 – 25 | Normal regime |
| High | 25 – 30 | Elevated risk |
| Extreme High | > 30 | Crisis/spike |

### 3d. SKEW & CBOE Derived Metrics

Computed from live options chain data — not externally fetched as a streaming symbol:

| Metric | Source | Module |
|--------|--------|--------|
| SKEW Index (replicated) | SPY options OTM put/call IV surface | `SpyderC18_SKEWCalculator.py`, `SpyderS06_SKEWCalculator.py` |
| GEX (Gamma Exposure) | SPY options OI × gamma | `SpyderN09_GammaExposure.py`, `SpyderS05_GEXDEXCalculator.py` |
| DEX (Delta Exposure) | SPY options OI × delta | `SpyderS05_GEXDEXCalculator.py` |
| OGL (Options Gravity Level) | Strike with max |GEX| | `SpyderS05_GEXDEXCalculator.py` |
| Max Pain | OI-weighted strike gravity | `SpyderF18_MaxPainCalculator.py` |

---

## 4. Futures & Index Symbols

### 4a. E-mini S&P 500 Futures (ES)

Defined in `SpyderC_MarketData/SpyderC11_FuturesBasis.py`:

| Property | Value |
|----------|-------|
| Contract multiplier | $50 per point |
| Tick size | 0.25 points |
| Tick value | $12.50 per tick |
| Contract months | March (H), June (M), September (U), December (Z) |

**ES/SPY arbitrage pairs tracked:**
- `BUY_ES_SELL_SPY` — ES cheap, SPY rich
- `SELL_ES_BUY_SPY` — ES rich, SPY cheap

### 4b. SPY Equity (basis counterpart)

| Property | Value |
|----------|-------|
| Multiplier | 1 (ETF shares) |
| Tick size | $0.01 |

> **Note:** NQ (Nasdaq futures), RTY (Russell futures), YM (Dow futures), MES (Micro E-mini), and /NQ prefix formats are **not currently implemented** in the system.

---

## 5. Options Data & OPRA

### 5a. SPY Options Chain Specifications

Managed by `SpyderB_Broker/SpyderB30_SPYOptionsChainManager.py`:

| Chain Type | DTE | Strikes Either Side | Refresh Frequency |
|-----------|-----|---------------------|--------------------|
| `0DTE` | 0 days | 10 | Every 1 minute |
| `1DTE` | 1 day | 10 | Every 5 minutes |
| `WEEKLY` | 7 days | 20 | Every 15 minutes |
| `MONTHLY` | 30 days | 30 | Every 60 minutes |

**Chain constants:**
- Strike interval: `$1.00` (SPY standard)
- Option multiplier: `100` shares per contract
- Risk-free rate: `5.0%` (for pricing models)
- Dividend yield: `2.0%` (for pricing models)

### 5b. Default DTE Ladder

Used across `SpyderC03_OptionChain.py` and `SpyderC07_OPRAFeed.py`:

```
0, 1, 2, 3, 5, 7, 14, 21, 30, 45, 60, 90, 120 days
```

### 5c. OPRA Exchange Codes

Defined in `SpyderC_MarketData/SpyderC07_OPRAFeed.py`. Note: OPRA feed is now **replaced by Databento `OPRA.PILLAR`** for live streaming:

| Code | Exchange | Code | Exchange |
|------|----------|------|----------|
| `A` | AMEX | `B` | BOX Options |
| `C` | CBOE | `H` | ISE Gemini |
| `I` | ISE (Nasdaq) | `M` | MIAX |
| `N` | NYSE Options | `O` | OPRA |
| `P` | PHLX | `Q` | Nasdaq PHLX |
| `T` | BATS Options | `W` | CBOE BZX |
| `X` | PHLX (alt) | `Z` | BATS BZX |

### 5d. Greeks Computed for Every Contract

From `SpyderN_OptionsAnalytics/SpyderN04_OptionsGreeksCalculator.py`:

| Greek | Symbol | Description |
|-------|--------|-------------|
| Delta | Δ | Price sensitivity to underlying |
| Gamma | Γ | Delta sensitivity to underlying |
| Theta | Θ | Time decay per day |
| Vega | ν | Sensitivity to 1% IV change |
| Rho | ρ | Sensitivity to interest rates |
| Charm | dΔ/dt | Delta decay over time |
| Vanna | dΔ/dσ | Delta sensitivity to IV |
| Volga | dν/dσ | Vega sensitivity to IV (vomma) |

---

## 6. Sector ETFs & Index Components

### 6a. S&P 500 Components (Sample Stub)

`SpyderC_MarketData/SpyderC13_IndexComponents.py` uses a hardcoded demo subset pending live data integration:

| Symbol | Company | Sector |
|--------|---------|--------|
| `AAPL` | Apple Inc. | Technology |
| `MSFT` | Microsoft Corp. | Technology |
| `AMZN` | Amazon.com Inc. | Consumer Discretionary |
| `GOOGL` | Alphabet Inc. | Technology |
| `META` | Meta Platforms | Technology |
| `BRK.B` | Berkshire Hathaway | Financials |
| `JPM` | JPMorgan Chase | Financials |
| `JNJ` | Johnson & Johnson | Healthcare |
| `V` | Visa Inc. | Financials |
| `PG` | Procter & Gamble | Consumer Staples |
| `XOM` | Exxon Mobil | Energy |
| `UNH` | UnitedHealth Group | Healthcare |
| `HD` | Home Depot | Consumer Discretionary |
| `MA` | Mastercard | Financials |
| `BAC` | Bank of America | Financials |

> The full S&P 500 list is fetched dynamically at runtime from Wikipedia for DIX calculations.

### 6b. Sector Rotation Regimes

| Regime | Leading Sectors |
|--------|----------------|
| `RISK_ON` | Technology, Consumer Discretionary |
| `DEFENSIVE` | Utilities, Consumer Staples |
| `CYCLICAL` | Financials, Industrials |
| `COMMODITY` | Energy, Materials |
| `MIXED` | No clear leadership |

### 6c. Sector ETFs Referenced (Mock/Stub Only)

These symbols appear **only** in the display-only dashboard launcher (`launch_spyder_dashboard_direct.py`) as mock test data — they are **not used for trading**:

| Symbol | Description |
|--------|-------------|
| `XLF` | Financial Select Sector SPDR |
| `XLK` | Technology Select Sector SPDR |
| `TLT` | iShares 20+ Year Treasury Bond ETF |

> **Gap:** Full sector ETF suite (XLE, XLV, XLI, XLY, XLP, XLU, XLRE, XLB, XLC) is not yet integrated as live data sources.

---

## 7. Dark Pool & Order Flow Signals

### 7a. DIX — Dark Index

**Source:** `SpyderS_Signals/SpyderS01_DIXCalculator.py`

| Property | Value |
|----------|-------|
| Data source | FINRA RegSho daily files |
| Base URL | `https://cdn.finra.org/equity/regsho/daily/` |
| File prefix | `CNMSshvol*.txt` |
| Symbol universe | S&P 500 (fetched from Wikipedia at runtime) |
| Market cap data | `yfinance` |
| DIX High threshold | > 0.45 (bullish signal) |
| DIX Low threshold | < 0.40 (bearish signal) |

### 7b. Dark Pool Venue Names

Tracked in `SpyderC_MarketData/SpyderC12_DarkPoolFlow.py`:

| Venue | Type |
|-------|------|
| `SIGMA` | Bank-sponsored ATS |
| `CROSSFINDER` | Credit Suisse ATS |
| `LIQUIDNET` | Institutional buy-side |
| `POSIT` | ITG (Virtu) |
| `BLOCKCROSS` | SunGard (now FIS) |
| `INSTINET` | Nomura |
| `ITG_POSIT` | Virtu |
| `UBS_PIN` | UBS |
| `MS_POOL` | Morgan Stanley |
| `BARX` | Barclays |

**Block trade thresholds:**
- Minimum block size: 10,000 shares
- Minimum block value: $500,000

---

## 8. Sentiment & News Data Sources

### 8a. News RSS Feeds

Defined in `SpyderC_MarketData/SpyderC09_NewsManager.py`:

| Source | URL |
|--------|-----|
| Bloomberg | `https://www.bloomberg.com/feeds/news` |
| Reuters | `https://www.reuters.com/feeds/news` |
| CNBC | `https://www.cnbc.com/id/100003114/device/rss/rss.html` |
| MarketWatch | `https://feeds.marketwatch.com/marketwatch/topstories/` |
| Wall Street Journal | `https://feeds.a.dj.com/rss/RSSMarketsMain.xml` |
| Federal Reserve | `https://www.federalreserve.gov/feeds/press_all.xml` |
| Yahoo Finance RSS | `https://feeds.finance.yahoo.com/rss/2.0/headline` |

### 8b. News Keyword Filters

| Category | Keywords |
|----------|----------|
| Market | `spy`, `s&p 500`, `stock market`, `wall street`, `nasdaq`, `dow jones` |
| Fed/Macro | `federal reserve`, `fomc`, `powell`, `interest rate`, `monetary policy`, `inflation`, `employment`, `gdp`, `economic data` |
| Crisis | `crash`, `plunge`, `collapse`, `emergency`, `halt`, `circuit breaker` |
| Earnings | `earnings`, `revenue`, `guidance`, `profit`, `loss`, `beat`, `miss` |

### 8c. Sentiment NLP Models & Source Weights

From `SpyderC_MarketData/SpyderC35_SentimentAnalyzer.py`:

| Model | Type | Ensemble Weight |
|-------|------|-----------------|
| `ProsusAI/finbert` | HuggingFace Transformers | 0.5 |
| VADER | Rule-based lexicon | 0.3 |
| TextBlob | Statistical NLP | 0.2 |

| Source Type | Score Weight |
|------------|--------------|
| News Articles | 1.5 |
| Reddit Posts | 1.0 |
| Twitter/X | 1.0 |
| SEC Filings | 2.0 |
| Analyst Reports | 2.0 |

### 8d. Reddit Sources

```
Subreddits: wallstreetbets, options, stocks, investing
User Agent: SpyderBot/1.0
API Base:   https://oauth.reddit.com
```

### 8e. Third-Party News APIs

| Provider | Endpoint | Auth |
|----------|----------|------|
| Alpha Vantage | `https://www.alphavantage.co/query` | `ALPHA_VANTAGE_API_KEY` |
| Finnhub | `https://finnhub.io/api/v1/company-news` | `FINNHUB_API_KEY` |
| Reddit OAuth | `https://oauth.reddit.com` | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` |

---

## 9. Databento Datasets & Schemas

### 9a. Datasets in Use

| Dataset ID | Exchange | Description | Usage |
|-----------|----------|-------------|-------|
| `OPRA.PILLAR` | OPRA | U.S. options market (all 16 exchanges) | **Primary live options feed** |
| `XNAS.ITCH` | NASDAQ | NASDAQ equities ITCH feed | Equity data feed |

### 9b. Data Schemas

| Schema | Description | Default? |
|--------|-------------|---------|
| `mbo` | Level 3 — market-by-order (full book) | — |
| `mbp-1` | Level 1 — top of book (best bid/ask) | ✅ Live default |
| `mbp-10` | Level 2 — 10 levels of depth | — |
| `tbbo` | Trade + best bid/offer snapshot | — |
| `trades` | Trade-only feed | — |
| `ohlcv-1s` | 1-second OHLCV bars | — |
| `ohlcv-1m` | 1-minute OHLCV bars | ✅ Historical default |
| `ohlcv-1h` | 1-hour OHLCV bars | — |
| `ohlcv-1d` | 1-day OHLCV bars | — |
| `definition` | Instrument definitions (options chain mapping) | — |
| `statistics` | Exchange statistics | — |
| `status` | Trading status messages | — |

### 9c. Databento Client Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `HEARTBEAT_INTERVAL_S` | 30 seconds | Live feed keepalive |
| `SLOW_READER_BEHAVIOR` | `"skip"` | Drop messages if reader falls behind |
| `LIVE_COMPRESSION` | `"zstd"` | Zstandard compression for live stream |
| `FIXED_PRICE_SCALE` | 1,000,000,000 | Nano-dollar integer prices (÷ 1e9 = dollars) |

---

## 10. Tradier API Endpoints

| Mode | Base URL |
|------|----------|
| **Sandbox** | `https://sandbox.tradier.com/v1` |
| **Live** | `https://api.tradier.com/v1` |

**Authentication:** Bearer token in `Authorization` header  
**Mode control:** `TRADIER_ENVIRONMENT=sandbox|production`

### Key Tradier Endpoints Used

| Endpoint | Description |
|----------|-------------|
| `GET /v1/markets/quotes` | Real-time quotes |
| `GET /v1/markets/options/chains` | Options chain |
| `GET /v1/markets/options/expirations` | Expiration dates |
| `GET /v1/markets/options/strikes` | Available strikes |
| `GET /v1/markets/history` | Historical OHLCV |
| `GET /v1/accounts/{id}/positions` | Account positions |
| `GET /v1/accounts/{id}/balances` | Account balances |
| `GET /v1/accounts/{id}/orders` | Order history |
| `POST /v1/accounts/{id}/orders` | Place order |
| `DELETE /v1/accounts/{id}/orders/{orderId}` | Cancel order |
| `GET /v1/markets/clock` | Market status / clock |
| `GET /v1/markets/calendar` | Market calendar |
| `WebSocket wss://stream.tradier.com/v1/markets/events` | Streaming quotes |

---

## 11. Third-Party API Endpoints

| Provider | Base URL | Auth Env Var | Used For |
|----------|----------|-------------|----------|
| Tradier | `https://api.tradier.com/v1` | `TRADIER_API_KEY` | Order execution, market data |
| Databento | `https://hist.databento.com` | `DATABENTO_API_KEY` | Market data (historical + live) |
| Alpha Vantage | `https://www.alphavantage.co/query` | `ALPHA_VANTAGE_API_KEY` | News sentiment |
| Finnhub | `https://finnhub.io/api/v1` | `FINNHUB_API_KEY` | Company news |
| Reddit | `https://oauth.reddit.com` | `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Social sentiment |
| FINRA RegSho | `https://cdn.finra.org/equity/regsho/daily/` | None (public) | DIX calculation |
| Wikipedia | `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies` | None (public) | S&P 500 component list |
| yfinance | (Yahoo Finance backend) | None | VIX term structure, DIX market cap |

> **Polygon.io:** Fully removed. Migration to Databento is complete. Any legacy references are migration notes only.

---

## 12. Option Symbol Format Reference

Three canonical formats used across the system, with automatic conversion available:

| Format Name | Example | Description |
|-------------|---------|-------------|
| `databento_osi` | `SPY   260220C00550000` | OSI 21-char space-padded (Databento native) |
| `tradier` | `SPY260220C00550000` | Tradier compact format |
| `spyder` | `SPY_260220_C_550.00` | Spyder internal display format |

**Decoding key:**
```
SPY   260220 C  00550000
 │      │    │     │
 │      │    │     └─ Strike price × 1000 (00550000 = $550.00)
 │      │    └─ Option type: C = Call, P = Put
 │      └─ Expiration: YYMMDD (260220 = Feb 20, 2026)
 └─ Underlying symbol (space-padded to 6 chars in OSI)
```

---

## 13. Missing / Planned Symbols

The following symbols are **referenced in strategy logic or documentation** but do **not yet have live data feed integration**:

| Category | Symbols | Status |
|----------|---------|--------|
| Index volatility | `VXN` (Nasdaq VIX), `VXD` (DJIA VIX), `RVX` (Russell VIX) | Not implemented |
| Commodity volatility | `GVZ` (Gold VIX), `OVX` (Oil VIX) | Not implemented |
| VIX Futures | `VX1`, `VX2`, `/VX` (near/far month) | Not implemented |
| Micro Futures | `/MES`, `/MNQ`, `/M2K` | Not implemented |
| CME Databento | `GLBX.MDP3` dataset | Not integrated |
| Full sector ETFs | `XLE`, `XLV`, `XLI`, `XLY`, `XLP`, `XLU`, `XLRE`, `XLB`, `XLC` | Not integrated |
| Crypto correlation | `BTC-USD`, `ETH-USD` | Not implemented |
| Bond yield proxies | `TNX` (10-yr yield), `TYX` (30-yr), `IRX` (13-wk) | Not implemented |
| CBOE indices | `SDEX` (S&P fear), `VXEEM`, `VXSLV` | Not implemented |
| SEC filings | EDGAR 8-K/10-K/10-Q structured data | Stub only |
| COT report data | CFTC Commitments of Traders | Not implemented |

---

## 14. Environment Variable Reference

All API credentials and data source configuration:

| Variable | Description | Required |
|----------|-------------|---------|
| `TRADIER_API_KEY` | Tradier Bearer token | ✅ Yes |
| `TRADIER_ACCOUNT_ID` | Tradier account number | ✅ Yes |
| `TRADIER_ENVIRONMENT` | `sandbox` or `production` | ✅ Yes |
| `DATABENTO_API_KEY` | Databento API key | ✅ Yes |
| `DATABENTO_DATASET` | Default dataset (default: `OPRA.PILLAR`) | Optional |
| `DATABENTO_LIVE_SCHEMA` | Live feed schema (default: `mbp-1`) | Optional |
| `DATABENTO_HIST_SCHEMA` | Historical schema (default: `ohlcv-1m`) | Optional |
| `DATABENTO_UNDERLYINGS` | CSV list of underlyings (default: `SPY`) | Optional |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage news API key | Optional |
| `FINNHUB_API_KEY` | Finnhub news API key | Optional |
| `REDDIT_CLIENT_ID` | Reddit OAuth app client ID | Optional |
| `REDDIT_CLIENT_SECRET` | Reddit OAuth app secret | Optional |

---

## Quick-Reference: All Symbols at a Glance

```
EQUITY & ETF
  SPY, SPX, VIX

MARKET INTERNALS (NYSE/NASDAQ prefix format)
  NYSE:TICK     NASDAQ:TICKI    NYSE:ADD      NYSE:VOLD
  NYSE:TRIN     INDEX:VIX       INDEX:VIX9D   INDEX:PCALL
  INDEX:PCSP    INDEX:CPCE      INDEX:SKEW
  NYSE:SPXHILO  NYSE:NYHL       NASDAQ:NQHL

VOLATILITY (yfinance ^ prefix)
  ^VIX  ^VIX9D  ^VVIX  ^VXV  ^VXMT  ^VXST

DERIVED / COMPUTED (not streamed, computed from SPY options)
  GEX  DEX  OGL  SKEW(replicated)  MaxPain

FUTURES
  ES (E-mini S&P 500) vs SPY basis only

OPTIONS
  SPY options chain — all expirations — DTE 0/1/2/3/5/7/14/21/30/45/60/90/120
  OPRA — all 14 US options exchanges via Databento OPRA.PILLAR

DATABENTO DATASETS
  OPRA.PILLAR   XNAS.ITCH

S&P 500 COMPONENTS (sample / runtime-fetched)
  AAPL  MSFT  AMZN  GOOGL  META  BRK.B  JPM
  JNJ   V     PG    XOM    UNH   HD     MA  BAC
  (+ full S&P 500 fetched from Wikipedia for DIX)

SENTIMENT SOURCES
  News RSS: Bloomberg, Reuters, CNBC, MarketWatch, WSJ, Federal Reserve
  APIs: Alpha Vantage, Finnhub, Reddit (wsb, options, stocks, investing)
  Models: FinBERT (0.5), VADER (0.3), TextBlob (0.2)

DARK POOL VENUES
  SIGMA  CROSSFINDER  LIQUIDNET  POSIT  BLOCKCROSS
  INSTINET  ITG_POSIT  UBS_PIN  MS_POOL  BARX
```

---

*This document is auto-derived from source code analysis. Update when new data sources or symbols are integrated.*
