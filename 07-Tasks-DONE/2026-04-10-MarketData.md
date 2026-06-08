# Market Data Requirements — Action Report
**Date:** 2026-04-10
**Status:** Pending implementation
**Context:** Summary of market data decisions made in the April 10, 2026 planning session.

---

## 1. Dashboard Symbol Cleanup

The Market Overview panel (left sidebar, `TradovG06_DashboardData.py`) currently shows symbols that either have no data source or provide redundant/irrelevant information. The following changes were agreed upon.

### 1.1 Symbols to REMOVE

File to edit: `Tradov/TradovG_GUI/TradovG06_DashboardData.py`
Dictionary to edit: `MARKET_SYMBOLS` and `SYMBOL_DESCRIPTIONS`

| Symbol | Category | Reason for Removal |
|--------|----------|--------------------|
| `/ES` | S&P CORE | Tradier does not carry futures. Massive has them in beta only. `TradovC11_FuturesBasis` is a dead stub — no live data flows. Remove from dashboard until Massive futures exit beta. |
| `VXMT` | VOLATILITY | 6-month VIX. Currently returns "---". Overlaps with `VXV` (3-month). Marginal value; yfinance fallback unreliable. Remove until CBOE indices verified via Massive `I:VXMT`. |
| `UVXY` | VOLATILITY | A 2× leveraged VIX ETF — a trading *product*, not a signal. VIX already captures the same information. Not fetched in the code despite being in the symbol list. |
| `PCALL` | MARKET INTERNALS | Total put/call ratio. Currently always "---". Tradier does not expose this directly. No publisher wired to the event bus. Remove until a data source is confirmed. |
| `VUD` | MARKET INTERNALS | Put/call volume ratio. Currently always "---". Overlaps with `CPC`. No live data source available from Tradier or Massive. |
| `DIA` | MAJOR INDICES | Dow Jones ETF. Price-weighted and dominated by a handful of costly single stocks — not a directional signal for SPY algorithmic trading. The key risk-on/off pair is `QQQ/IWM`, not DIA. |

### 1.2 Symbols to KEEP (and why)

**S&P CORE:** `SPY`, `SPX`
**VOLATILITY:** `VIX` ✅ core, `VXV` ✅ term structure ratio, `VVIX` ✅ early warning
**MARKET INTERNALS:** `$TICK` ✅, `$TRIN` ✅, `$ADD` ✅, `CPC` ✅, `SKEW` ✅
**MAJOR INDICES:** `QQQ` ✅, `IWM` ✅
**BONDS & CREDIT:** `TLT` ✅, `LQD` ✅
**CORRELATIONS:** `DXY` ✅, `GLD` ✅
**CUSTOM METRICS:** `GEX` ✅, `DEX` ✅, `OGL` ✅, `DIX` ✅, `SWAN` ✅

---

## 2. Market Data Subscriptions

### 2.1 Paid — Already Have

| Service | Purpose | Notes |
|---------|---------|-------|
| **Tradier** | Broker + primary market data feed | See Section 3 for plan choice |
| **Massive** (Polygon.io) | Extended market data | See Section 4 for viability decision |

### 2.2 Free — Register These

These are called out explicitly in `.env.template` and fill real gaps in the data pipeline:

#### FRED API ← **Most Important**
- **URL:** https://fred.stlouisfed.org/docs/api/api_key.html
- **Cost:** Free
- **What it provides:** Macro economic factors consumed by `TradovC22_FactorDataProvider`:
  - Credit spread (`BAA10Y` — Baa–Treasury yield spread)
  - Term spread (`T10Y3M` — 10-year minus 3-month yield)
  - Real rate (`DFII10` — 10-year TIPS)
  - Inflation breakeven (`T5YIE` — 5-year breakeven)
  - Fama-French factors (SMB, HML, RMW, CMA, MOM)
- **Frequency:** Daily (suitable for factor models and risk models)
- **Action:** Register → add key to `.env` as `FRED_API_KEY=`

#### Barchart OnDemand
- **URL:** https://www.barchart.com/ondemand/free-api-key
- **Cost:** Free tier
- **What it provides:** Market internals not available from Tradier:
  - `$NYMO` (McClellan Oscillator)
  - Additional breadth data where Tradier has gaps
- **Action:** Register → add key to `.env` as `BARCHART_API_KEY=`

### 2.3 Optional — Sentiment Module (C35 degrades gracefully without these)

`TradovC35_SentimentAnalyzer` returns neutral sentiment silently if any key is absent. Add only if you want active sentiment signals.

| Service | Env Var | What it provides | Cost |
|---------|---------|-----------------|------|
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` | Financial news headlines | Free tier |
| Finnhub | `FINNHUB_API_KEY` | Company news | Free tier |
| Reddit OAuth | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | r/wallstreetbets sentiment | Free |

### 2.4 No Registration Required

| Service | How it works |
|---------|-------------|
| **FINRA CDN** | DIX dark index — unauthenticated HTTP fetch from `cdn.finra.org`. Post-market daily. No key needed. |
| **yfinance** | Unofficial fallback for VIX term structure (`^VXV`, `^VVIX` etc.). No key. Fragile — can break without warning if Yahoo changes their API. |

---

## 3. Tradier Subscription Plan Decision

**Recommendation: Pro ($10/month) when ready for live trading.**

| Plan | Cost | Commissions | Verdict |
|------|------|-------------|---------|
| Lite | $0/mo | $0.35 per stock/option contract | ❌ Commissions compound fast with multi-leg strategies (Iron Condor = 4 contracts per trade) |
| **Pro** | **$10/mo** | **Commission-free stocks + equity/ETF options** | **✅ Correct tier for SPY options trading** |
| Pro Plus | $35/mo | Commission-free + reduced index options + futures | ❌ Overkill — SPY is an ETF, not an index; no futures trading yet |

**Why Pro and not Pro Plus:**
- All current strategies target **SPY** (an ETF) — Pro covers equity/ETF options commission-free.
- Pro Plus advantages (reduced index options fees, futures) apply to SPX options and /ES futures — neither is in active use yet.

**When to upgrade to Pro Plus:**
- If SPX 0-DTE strategies are added (index options fee reduction becomes material)
- If Massive futures exit beta and live /ES trading is wired up via C11

**Critical:** Set `TRADIER_ENVIRONMENT=production` in `.env` only **after** the brokerage account is funded. Sandbox always returns delayed data regardless of plan.

---

## 4. Massive — Viability Decision

**Conclusion: Massive is optional for the initial live trading phase. Tradier alone is sufficient for the core trading loop.**

### What Tradier covers fully (no Massive needed)

| Function | Source |
|----------|--------|
| SPY/SPX real-time quotes | Tradier `GET /markets/quotes` |
| SPY options chains with live Greeks and IV | Tradier `GET /markets/options/chains` |
| Order execution (all multi-leg strategies) | Tradier `POST /accounts/{id}/orders` |
| `$TICK`, `$ADD`, `$TRIN`, `VIX` | Tradier quotes API |
| All ETFs: `QQQ`, `IWM`, `TLT`, `LQD`, `GLD`, `DXY` | Tradier quotes API |
| Daily historical OHLCV | Tradier `GET /markets/history` |

### What degrades to yfinance fallback without Massive

These have fallback code — the system won't crash, but the data is unofficial:

| Signal | Impact without Massive |
|--------|----------------------|
| `VIX9D`, `VVIX`, `VXV` (VIX term structure) | Falls to yfinance scrape. Term structure ratio used by Iron Condor sizing and calendar spread valuation. Works but fragile. |
| `VOLD` (NYSE Up/Down Volume) | Falls to zero — no publisher without Massive. |
| `VXN`, `RVX` (NASDAQ/R2K VIX) | Black Swan indicator loses two inputs. Falls to yfinance. |

### What goes completely dark without Massive

| Module | What is Lost |
|--------|-------------|
| `C30 OrderFlowAnalyzer` | OPRA L3 tick data — sweep detection, block print detection, unusual options flow alerts |
| `C11 FuturesBasis` | Already stubbed/dead — no change whether Massive is present or not |
| Historical options chains | ML training data and backtesting with point-in-time options data |
| Dark pool ADF prints (`C12`) | Real-time dark pool venue attribution |

### Recommended approach

1. **Phase 1 — Tradier only:** Run paper trading and initial live trading with Tradier. The core execution loop (signal → size → execute → manage) works fully.
2. **Phase 2 — Add Massive if needed:** If yfinance fallbacks prove unreliable in practice (Yahoo rate-limiting, symbol changes), or if order flow analysis is needed to improve edge, add Massive at that point.
3. **Databento:** Not needed. Confirmed removed from codebase (`TradovC26_DatabentoClient.py` deleted). All Databento use cases are covered by Massive.

---

## 5. Outstanding Technical Tasks (from audit)

These are data pipeline issues identified in `2026-04-08-MarketData-Research.md` that need resolution before full production deployment:

| Priority | Task | File(s) | Effort |
|----------|------|---------|--------|
| P1 | **Verify Massive CBOE indices** — call `list_snapshot_indices(tickers=["I:VIX9D","I:VVIX","I:VXV","I:SKEW"])` with live Massive API key; if valid, wire into C04 and C10 to eliminate yfinance fallbacks | C04, C10, C27 | Low |
| P1 | **Migrate C30 `DatabentoTickDataSource` → `MassiveTickDataSource`** — replace the dead Databento stub with a Massive WebSocket subscriber on `T.O:SPY*` | C30 | Medium |
| P1 | **Fix C12 dark pool filter** — match on `exchange == "D"` (FINRA ADF) instead of ATS name strings (`SIGMA`, `CROSSFINDER`, etc.) | C12 | Low |
| P1 | **Source put/call ratio** — CBOE provides delayed PCALL/CPCE via direct URL, or compute from Massive options volume data; wire publisher to event bus in C04 | C04 | Medium |
| P1 | **Wire SKEW publisher to event bus** — S06 already computes SKEW from options chain data; it should publish to the bus so C04 displays it live | S06, C04 | Low |
| P2 | **Migrate C18 SKEWCalculator** from direct yfinance import to Tradier options chain (same pattern as S06 primary source) | C18 | Low |
| P2 | **Add circuit breaker + retry to FINRA CDN fetch** in S01 DIXCalculator | S01 | Low |
| P2 | **Remove dead Databento import guards** from C01, C30, F18, D27, D28 | Multiple | Low |
| P3 | **Wire Massive futures** (`/ES`, `/NQ`) into C11 when REST API exits beta | C11 | Medium |
| P3 | **Verify and wire DXY via Massive forex** to replace yfinance `DX-Y.NYB` fallback | C22 | Low |

---

## 6. Quick Reference — Environment Variables to Configure

```bash
# === REQUIRED ===
TRADIER_API_KEY=           # From Tradier brokerage account
TRADIER_ACCOUNT_ID=        # From Tradier brokerage account
TRADIER_ENVIRONMENT=sandbox  # Change to: production when live

# === FREE — REGISTER NOW ===
FRED_API_KEY=              # https://fred.stlouisfed.org/docs/api/api_key.html
BARCHART_API_KEY=          # https://www.barchart.com/ondemand/free-api-key

# === PAID — ADD WHEN NEEDED ===
MASSIVE_API_KEY=           # https://massive.com — add if yfinance fallbacks prove unreliable

# === OPTIONAL — SENTIMENT ===
ALPHA_VANTAGE_API_KEY=     # https://www.alphavantage.co/support/#api-key (free tier)
FINNHUB_API_KEY=           # https://finnhub.io/register (free tier)
REDDIT_CLIENT_ID=          # https://www.reddit.com/prefs/apps
REDDIT_CLIENT_SECRET=      # Same app registration as above
```

---

*Report generated from planning session on 2026-04-10. Cross-reference: `05-Research/2026-04-08-MarketData-Research.md`, `05-Research/Market-Data-Reference.md`, `Tradov/TradovG_GUI/TradovG06_DashboardData.py`.*
