# Walmart Recession Signal (WRS) — Python Build Specification
## Data Source: Tradier Brokerage API
## Version: 2.0 (corrected luxury proxy strategy)

## Overview

Build a standalone Python module that computes, stores, and plots the **Walmart
Recession Signal (WRS)** — a macro-economic ratio comparing Walmart (WMT) stock
price against a custom-constructed basket of US-listed luxury ADRs and equities
that serves as a proxy for the S&P Global Luxury Index.

A rising ratio signals consumer spending shift toward discount retail,
historically preceding economic downturns.

**Formula:**
```
WRS = Price(WMT) / Price(LUXURY_BASKET)
```

---

## Important Context: Why a Custom Basket?

Paulsen's published WRS uses the S&P Global Luxury Index (~80 constituents).
The direct US-investable proxies are problematic:

| Proxy | Status | Why Rejected |
|---|---|---|
| `SRIWLUXG.SW` | Not available on Tradier | Traded on SIX Swiss Exchange only |
| `GLUX` | Not available on Tradier | European UCITS ETF (Paris/Milan/Swiss) |
| `LUX` (Tema Luxury ETF) | Delisted Aug 2025 | Fund closed — ticker no longer trades |

**Solution:** Construct an equal-weight basket from US-listed ADRs and equities
of major luxury names. This approach:

- Uses only symbols available via Tradier
- Provides 20+ years of history from the anchor name (LVMUY)
- Organically grows as newer names come online (e.g., RACE added at 2016 IPO)
- Matches Paulsen's spirit — "luxury names vs Walmart"

---

## Environment

| Item | Requirement |
|---|---|
| OS | Ubuntu 24.04 LTS |
| Python | 3.11+ |
| Package manager | pip (no conda) |
| Virtual env | `python3 -m venv .venv` |
| IDE | VSCode (.deb) |

---

## Dependencies

```
requests>=2.31
pandas>=2.2
numpy>=1.26
matplotlib>=3.8
python-dotenv>=1.0
schedule>=1.2        # optional auto-refresh daemon
rich>=13.0           # CLI output
```

Install:
```bash
pip install requests pandas numpy matplotlib python-dotenv schedule rich
```

---

## API Credentials

Store in `.env` — never hardcode:

```
TRADIER_TOKEN=your_production_token_here
TRADIER_SANDBOX=false
```

**Get your token:** `https://web.tradier.com/user/api`
→ Preferences (gear icon) → API Access → Account Access

**Base URLs:**
```python
PRODUCTION_URL = "https://api.tradier.com/v1"
SANDBOX_URL    = "https://sandbox.tradier.com/v1"
```

---

## Luxury Basket Composition

All tickers are **US-listed** (NYSE, NASDAQ, or OTC pink sheets) and
available via Tradier's history endpoint:

| Ticker | Company | Exchange | Approx First Trade |
|---|---|---|---|
| `LVMUY` | LVMH Moët Hennessy Louis Vuitton | OTC | 1999 |
| `CFRUY` | Compagnie Financière Richemont | OTC | ~2010 |
| `HESAY` | Hermès International | OTC | ~2012 |
| `PPRUY` | Kering (ex-PPR) | OTC | ~2013 |
| `BURBY` | Burberry Group | OTC | ~2009 |
| `SWGAY` | Swatch Group | OTC | ~2002 |
| `RACE`  | Ferrari N.V. | NYSE | Oct 2015 (IPO) |
| `TPR`   | Tapestry (ex-Coach) | NYSE | 2000 |
| `CPRI`  | Capri Holdings (Michael Kors) | NYSE | Dec 2013 (IPO) |

The basket auto-rebalances: each day's value is the equal-weight mean of
whichever constituents are trading on that date. Early years (2000–2009) are
anchored by LVMUY + TPR; composition grows as new names join.

---

## Module Structure

```
wrs/
├── __init__.py
├── config.py          # constants, tickers, thresholds
├── tradier.py         # Tradier REST client — all HTTP calls
├── data.py            # orchestrate fetches, caching, basket construction
├── signal.py          # WRS ratio and derived metrics
├── chart.py           # matplotlib 3-panel chart
├── cli.py             # rich-formatted terminal report
├── utils.py           # logging, retry, date helpers
└── main.py            # entry point with argparse
```

---

## config.py

```python
from pathlib import Path

# Primary asset
WMT_TICKER = "WMT"

# Luxury basket — US-listed only, all available on Tradier
LUXURY_BASKET = [
    "LVMUY",  # LVMH
    "CFRUY",  # Richemont
    "HESAY",  # Hermès
    "PPRUY",  # Kering
    "BURBY",  # Burberry
    "SWGAY",  # Swatch
    "RACE",   # Ferrari (from 2015)
    "TPR",    # Tapestry
    "CPRI",   # Capri Holdings (from 2013)
]

# History parameters
HISTORY_START = "2000-01-01"   # covers dot-com, GFC, COVID cycles
MIN_HISTORY_YEARS = 2          # below this, warn about unreliable stats

# Basket quality thresholds
MIN_BASKET_TICKERS = 3         # minimum alive constituents to compute basket
WARN_BASKET_TICKERS = 5        # warn if fewer than this are alive

# Cache
CACHE_DIR = Path("~/.wrs/cache").expanduser()
CACHE_TTL_HOURS = 4

# Output
OUTPUT_DIR = Path("~/.wrs/output").expanduser()
LOG_DIR = Path("~/.wrs/logs").expanduser()

# NBER recession bands for chart annotation
RECESSION_BANDS = [
    ("2001-03-01", "2001-11-30", "Dot-com"),
    ("2007-12-01", "2009-06-30", "GFC"),
    ("2020-02-01", "2020-04-30", "COVID"),
]

# Signal level thresholds (percentile rank over full history)
SIGNAL_LEVELS = {
    "NORMAL":   (0,   60),
    "CAUTION":  (60,  75),
    "WARNING":  (75,  90),
    "CRITICAL": (90, 100),
}

# Tradier API
TRADIER_PRODUCTION_URL = "https://api.tradier.com/v1"
TRADIER_SANDBOX_URL = "https://sandbox.tradier.com/v1"
REQUEST_TIMEOUT = 10   # seconds
MAX_RETRIES = 3
```

---

## tradier.py — REST Client

```python
import time
import requests
from typing import Optional


class TradierAPIError(Exception):
    """Raised on non-200 Tradier API response."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{status_code}] {message}")


class DataUnavailableError(Exception):
    """Raised when a symbol returns empty/null history."""


class TradierClient:
    """
    Thin wrapper around Tradier REST API.
    All methods return parsed Python objects.
    """

    def __init__(self, token: str, sandbox: bool = False):
        base = TRADIER_SANDBOX_URL if sandbox else TRADIER_PRODUCTION_URL
        self.base_url = base
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

    def get_history(
        self,
        symbol: str,
        start: str,
        end: Optional[str] = None,
        interval: str = "daily",
    ) -> list[dict]:
        """
        Fetch OHLCV history for a symbol.

        Endpoint: GET /v1/markets/history
        Tradier supports FULL-LIFETIME history — no pagination needed.
        A single call with start=2000-01-01 returns all bars.

        Args:
            symbol   : e.g. "WMT", "LVMUY"
            start    : "YYYY-MM-DD" (inclusive)
            end      : "YYYY-MM-DD" (defaults to today)
            interval : "daily" | "weekly" | "monthly"

        Returns:
            List of dicts with keys:
              date, open, high, low, close, volume
            Note: 'close' is already adjusted for splits/dividends.

        Raises:
            TradierAPIError     : HTTP 4xx/5xx (after retries)
            DataUnavailableError : symbol returns null/empty history
        """
        from datetime import date
        end = end or date.today().isoformat()

        data = self._request("GET", "/markets/history", params={
            "symbol": symbol,
            "interval": interval,
            "start": start,
            "end": end,
            "session_filter": "all",
        })

        # Tradier returns {"history": null} for unknown symbols
        if not data.get("history"):
            raise DataUnavailableError(
                f"No history returned for {symbol} "
                f"(range: {start} → {end})"
            )

        days = data["history"]["day"]
        # Normalise single-day response (dict) to list
        return [days] if isinstance(days, dict) else days

    def get_quote(self, symbol: str) -> dict:
        """
        Real-time quote for a single symbol.
        Endpoint: GET /v1/markets/quotes?symbols={symbol}
        """
        data = self._request("GET", "/markets/quotes", params={
            "symbols": symbol,
            "greeks": "false",
        })
        if not data.get("quotes") or not data["quotes"].get("quote"):
            raise DataUnavailableError(f"No quote returned for {symbol}")
        quote = data["quotes"]["quote"]
        return quote if isinstance(quote, dict) else quote[0]

    def get_quotes(self, symbols: list[str]) -> list[dict]:
        """
        Real-time quotes for multiple symbols (batched).
        Endpoint: GET /v1/markets/quotes?symbols=SYM1,SYM2,...
        Always returns a list even for single-symbol requests.
        """
        data = self._request("GET", "/markets/quotes", params={
            "symbols": ",".join(symbols),
            "greeks": "false",
        })
        if not data.get("quotes") or not data["quotes"].get("quote"):
            return []
        quote = data["quotes"]["quote"]
        return [quote] if isinstance(quote, dict) else quote

    def market_clock(self) -> dict:
        """
        GET /v1/markets/clock
        Returns: {"state": "open"|"closed"|"premarket"|"postmarket",
                  "description": str, "next_change": ISO datetime, ...}
        """
        data = self._request("GET", "/markets/clock")
        return data.get("clock", {})

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
    ) -> dict:
        """
        Execute HTTP request with retry logic:
          - 401 Unauthorized → fail immediately (bad token)
          - 429 Rate Limited → wait Retry-After seconds, then retry
          - 5xx Server Error → exponential backoff (2s, 4s, 8s)
          - Network timeout → retry up to MAX_RETRIES times
        """
        url = f"{self.base_url}{endpoint}"
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(
                    method, url, params=params, timeout=REQUEST_TIMEOUT,
                )

                if response.status_code == 401:
                    raise TradierAPIError(
                        401,
                        "Invalid token. Check TRADIER_TOKEN in .env"
                    )

                if response.status_code == 429:
                    wait = int(response.headers.get("Retry-After", "5"))
                    time.sleep(wait)
                    continue

                if response.status_code >= 500:
                    time.sleep(2 ** (attempt + 1))
                    last_error = TradierAPIError(
                        response.status_code, response.text
                    )
                    continue

                response.raise_for_status()
                return response.json()

            except requests.Timeout:
                last_error = TimeoutError(f"Request to {url} timed out")
                time.sleep(2 ** (attempt + 1))
            except requests.RequestException as e:
                last_error = e
                time.sleep(2 ** (attempt + 1))

        raise TradierAPIError(
            0, f"Max retries exceeded: {last_error}"
        )
```

---

## data.py — Fetch, Cache, and Basket Construction

```python
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


def get_wmt_prices(
    client: TradierClient,
    start: str = HISTORY_START,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.Series:
    """
    Fetch WMT adjusted-close series via Tradier.
    Returns pd.Series with DatetimeIndex, name='WMT'.
    """
    cache_key = f"WMT_{start}"
    if use_cache:
        cached = load_cached(cache_key)
        if cached is not None:
            return cached

    bars = client.get_history("WMT", start=start, end=end)
    series = _bars_to_series(bars, name="WMT")

    save_cache(cache_key, series)
    return series


def get_luxury_basket(
    client: TradierClient,
    start: str = HISTORY_START,
    end: str | None = None,
    use_cache: bool = True,
) -> tuple[pd.Series, dict]:
    """
    Build the luxury basket from US-listed ADRs and equities.

    Strategy:
      1. Fetch history for each ticker in LUXURY_BASKET
      2. For each ticker's series, rebase to 100 at its own first trading day
      3. Align all rebased series on a common DatetimeIndex
      4. At each date, compute equal-weight arithmetic mean of whichever
         tickers have data on that date
      5. Require at least MIN_BASKET_TICKERS alive on a given date

    Returns:
        (series, metadata)
        series   : pd.Series of basket value over time, name='LUXURY'
        metadata : {
            "available_tickers": [...],
            "missing_tickers":   [...],
            "first_date":        "2000-01-03",
            "last_date":         "2026-04-17",
            "composition_timeline": {
                "2000": 2, "2010": 3, "2013": 5, "2016": 7, ...
            }
        }
    """
    series_dict = {}
    missing = []

    for ticker in LUXURY_BASKET:
        cache_key = f"{ticker}_{start}"
        if use_cache:
            cached = load_cached(cache_key)
            if cached is not None:
                series_dict[ticker] = cached
                continue

        try:
            bars = client.get_history(ticker, start=start, end=end)
            s = _bars_to_series(bars, name=ticker)
            # Rebase each ticker to 100 at its own first observation
            s = (s / s.iloc[0]) * 100.0
            series_dict[ticker] = s
            save_cache(cache_key, s)
            log.info(f"Basket: {ticker} fetched ({len(s)} bars)")
        except DataUnavailableError:
            missing.append(ticker)
            log.warning(f"Basket: {ticker} unavailable, skipping")

    if len(series_dict) < MIN_BASKET_TICKERS:
        raise DataUnavailableError(
            f"Basket has only {len(series_dict)} tickers "
            f"(need >={MIN_BASKET_TICKERS}). Missing: {missing}"
        )

    if len(series_dict) < WARN_BASKET_TICKERS:
        log.warning(
            f"Basket is thin: only {len(series_dict)} of "
            f"{len(LUXURY_BASKET)} tickers available"
        )

    # Align all series on union of dates; mean ignores NaN
    df = pd.concat(series_dict.values(), axis=1)
    df.columns = list(series_dict.keys())
    basket = df.mean(axis=1, skipna=True).rename("LUXURY")

    # Build composition timeline (how many names alive per year)
    yearly_counts = df.notna().groupby(df.index.year).any().sum(axis=1)
    composition = yearly_counts.to_dict()

    metadata = {
        "available_tickers": list(series_dict.keys()),
        "missing_tickers":   missing,
        "first_date":        basket.index.min().date().isoformat(),
        "last_date":         basket.index.max().date().isoformat(),
        "composition_timeline": composition,
    }

    return basket, metadata


def align_series(wmt: pd.Series, luxury: pd.Series) -> pd.DataFrame:
    """
    Inner-join WMT and LUXURY on DatetimeIndex.
    Drop rows where either is NaN.
    Forward-fill gaps of up to 3 days only (handles single-day
    missing prints without masking real data gaps).
    """
    df = pd.concat([wmt, luxury], axis=1)
    df.columns = ["wmt", "luxury"]
    df = df.ffill(limit=3).dropna()
    return df


def _bars_to_series(bars: list[dict], name: str) -> pd.Series:
    """Convert Tradier history response to pd.Series of close prices."""
    idx = pd.DatetimeIndex([b["date"] for b in bars])
    values = [float(b["close"]) for b in bars]
    return pd.Series(values, index=idx, name=name).sort_index()


def load_cached(key: str) -> pd.Series | None:
    """Load from ~/.wrs/cache/<key>.csv if fresh; else None."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.csv"
    if not path.exists():
        return None
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    if age > timedelta(hours=CACHE_TTL_HOURS):
        return None
    s = pd.read_csv(path, index_col=0, parse_dates=True).squeeze("columns")
    s.name = key.split("_")[0]
    return s


def save_cache(key: str, series: pd.Series) -> None:
    """Save series to ~/.wrs/cache/<key>.csv with metadata header."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.csv"
    series.to_csv(path, header=True)
```

---

## signal.py — WRS Computation

```python
import numpy as np
import pandas as pd


def compute_wrs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input:  DataFrame with columns ['wmt', 'luxury']
    Output: DataFrame with original columns plus:
      wrs          : Raw ratio = wmt / luxury
      wrs_30d_ma   : 30-day simple moving average
      wrs_90d_ma   : 90-day simple moving average
      wrs_pct_rank : Expanding percentile rank (0–100)
      wrs_zscore   : 252-day rolling z-score
      yoy_change   : Year-over-year change (absolute)
    """
    out = df.copy()
    out["wrs"] = out["wmt"] / out["luxury"]

    out["wrs_30d_ma"] = out["wrs"].rolling(30, min_periods=20).mean()
    out["wrs_90d_ma"] = out["wrs"].rolling(90, min_periods=60).mean()

    # Expanding percentile rank (not rolling — matches Paulsen's "all-time" framing)
    out["wrs_pct_rank"] = (
        out["wrs"].expanding().rank(pct=True) * 100
    )

    # Rolling 1-year z-score
    rolling = out["wrs"].rolling(252, min_periods=120)
    out["wrs_zscore"] = (out["wrs"] - rolling.mean()) / rolling.std()

    # YoY change in raw WRS
    out["yoy_change"] = out["wrs"] - out["wrs"].shift(252)

    return out


def get_current_reading(df: pd.DataFrame) -> dict:
    """
    Most-recent-row summary dict with signal level.
    """
    last = df.iloc[-1]
    pct = float(last["wrs_pct_rank"])

    for level, (lo, hi) in SIGNAL_LEVELS.items():
        if lo <= pct < hi or (level == "CRITICAL" and pct >= 90):
            signal_level = level
            break

    return {
        "date":         df.index[-1].date().isoformat(),
        "wrs":          float(last["wrs"]),
        "wrs_30d_ma":   float(last["wrs_30d_ma"]),
        "wrs_90d_ma":   float(last["wrs_90d_ma"]),
        "wrs_pct_rank": pct,
        "wrs_zscore":   float(last["wrs_zscore"]),
        "yoy_change":   float(last["yoy_change"]),
        "signal_level": signal_level,
    }


def detect_crossovers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Dates where wrs_30d_ma crosses wrs_90d_ma.
    Returns DataFrame: [date, direction ('up'|'down'), wrs_value]
    'up' = 30d rising above 90d = worsening signal.
    """
    diff = df["wrs_30d_ma"] - df["wrs_90d_ma"]
    sign = np.sign(diff)
    crossover_mask = sign != sign.shift(1)
    crossovers = df.loc[crossover_mask].copy()
    crossovers["direction"] = np.where(
        diff[crossover_mask] > 0, "up", "down"
    )
    return crossovers[["wrs", "direction"]].rename(
        columns={"wrs": "wrs_value"}
    )
```

---

## chart.py — 3-Panel Visualisation

**Panel 1 — WRS Ratio + Moving Averages**
- Raw `wrs` (thin grey line)
- `wrs_30d_ma` (amber, 2px)
- `wrs_90d_ma` (cyan dashed, 2px)
- RECESSION_BANDS shaded translucent red with text labels
- 'up' crossovers marked with vertical red dashed lines

**Panel 2 — Percentile Rank**
- Area chart of `wrs_pct_rank` (y-axis 0–100)
- Horizontal threshold lines at 60 (green), 75 (amber), 90 (red)
- Region above 90 filled red, alpha=0.3

**Panel 3 — WMT vs Luxury Basket (normalised)**
- Both series rebased to 100 at HISTORY_START
- WMT blue, LUXURY gold, legend

**Config:**
```python
plt.style.use("dark_background")
FIGURE_SIZE = (16, 12)
DPI = 100
```

**Title format:**
```
Walmart Recession Signal (WRS) | {date}
Value: {wrs:.5f}  |  Rank: {pct:.1f}%  |  {signal_icon} {signal_level}
```

Signal icons: `✅` NORMAL, `⚠️` CAUTION, `🔶` WARNING, `🚨` CRITICAL.

**Output:** Save to `~/.wrs/output/wrs_{YYYYMMDD}.png`.
Support `show: bool = False` param for `plt.show()`.

---

## cli.py — Rich Terminal Report

```python
def print_report(
    reading: dict,
    basket_metadata: dict,
    df: pd.DataFrame,
) -> None:
    """
    Print formatted report using rich.
    Colour-code signal level:
      NORMAL   → green
      CAUTION  → yellow
      WARNING  → dark_orange
      CRITICAL → red bold
    """
```

**Output:**
```
┌────────────────────────────────────────────────┐
│       WALMART RECESSION SIGNAL (WRS)           │
│       As of: 2026-04-17                        │
├────────────────────────────────────────────────┤
│  WRS Value        :  0.0305                    │
│  30-Day MA        :  0.0291                    │
│  90-Day MA        :  0.0268                    │
│  YoY Change       :  +28.0 bps                 │
│  Percentile Rank  :  94.2%                     │
│  Z-Score (252d)   :  2.41                      │
│  Signal Level     :  🚨 CRITICAL               │
├────────────────────────────────────────────────┤
│  Luxury Basket    :  8 of 9 tickers            │
│  Missing          :  MONCF                     │
│  Data Range       :  2000-01-03 → 2026-04-17   │
│  Last Crossover   :  2026-01-14 (↑ up)         │
│  Data Provider    :  Tradier                   │
└────────────────────────────────────────────────┘
```

---

## main.py — Entry Point

```bash
# Standard run: fetch, compute, print report, save chart
python main.py

# Force cache refresh
python main.py --refresh

# Show chart interactively
python main.py --show

# Custom output path
python main.py --output ~/Desktop/wrs_today.png

# Sandbox mode (Tradier paper environment)
python main.py --sandbox

# Daemon: run every 4h during market hours, log rotation
python main.py --daemon

# Diagnostic: dump basket composition timeline
python main.py --diagnostics
```

**Daemon requirements:**
- Use `schedule` library
- Fire every 4h only when `TradierClient.market_clock()` returns
  `state in ("open", "premarket")`
- Log to `~/.wrs/logs/wrs.log` with `RotatingFileHandler`
  (maxBytes=5MB, backupCount=3)
- Exit gracefully on SIGTERM/SIGINT with cleanup

---

## Error Handling Matrix

| Scenario | Behaviour |
|---|---|
| 401 Unauthorized | Fail immediately, message directs user to check `.env` |
| 429 Rate Limited | Honour `Retry-After` header, retry |
| 5xx Server Error | Exponential backoff (2s, 4s, 8s), 3 retries |
| Network timeout | Retry up to MAX_RETRIES with backoff |
| Tradier returns `{"history": null}` | Raise `DataUnavailableError`, skip that ticker |
| Basket has < 3 alive tickers | Raise `DataUnavailableError` — can't compute |
| Basket has 3-4 alive tickers | Compute with warning about thin composition |
| WMT history unavailable | Fatal — cannot proceed |
| Cache miss + network down | Raise with guidance |
| History < 2 years | Warn: percentile rank and z-score unreliable |
| Insufficient trading overlap between WMT & basket | Warn, proceed with intersection |

---

## Testing

```
tests/
├── test_tradier.py            # mock requests, test retry logic, 401/429/5xx
├── test_data.py               # basket construction, cache behaviour
├── test_signal.py             # known input → expected WRS values
├── test_chart.py              # smoke test: PNG renders without error
├── test_cli.py                # report formatting snapshot
└── fixtures/
    ├── tradier_history_WMT.json     # sample Tradier response
    ├── tradier_history_LVMUY.json
    ├── tradier_quote.json
    └── sample_basket.csv
```

```bash
pytest tests/ -v --cov=wrs
```

---

## Implementation Notes for Coding Agent

### Tradier-specific
- History endpoint returns full lifetime — single call with `start=2000-01-01`
  retrieves everything, no pagination needed
- `close` field in history is **already adjusted** for splits/dividends
- `history.day` can be a dict (single day) or list (multiple days) —
  always normalise
- `history` itself may be `null` for unknown symbols — check before indexing
- Quotes endpoint: `quotes.quote` can be dict or list — same normalisation

### Basket construction
- **Rebase each ticker to 100 at its own first trading day**, then average
  — do not align start dates before rebasing, or you'll distort early years
- Equal-weight arithmetic mean with `skipna=True` lets newer tickers join
  the basket organically without breaking historical continuity
- Composition timeline in metadata is useful for explaining basket evolution
  to end users (e.g., "pre-2015 basket is just 5 names")

### General
- All paths via `pathlib.Path` with `.expanduser()` — no raw string paths
- `logging` internally; `rich` only for final CLI output
- `tradier.py` is the ONLY module making HTTP calls
- Use pandas 2.x idioms: `.ffill()` not `fillna(method='ffill')`
- WRS ratio uses price levels directly (not log returns) — matches Paulsen
- Rate limit: Tradier free accounts ~120 req/min; basket fetch is 10 symbols
  (WMT + 9 luxury), well within limits even without caching

### What's deliberately NOT in scope
- Trading execution (this is a *signal*, not a strategy)
- Options chain data (irrelevant for macro signal)
- Real-time streaming (daily close is sufficient for WRS)
- Alerts/notifications (add as separate module if needed)
