# Spyder — Massive (Polygon) Historical Data Download Guidelines

> **Last Updated:** 2026-03-19
> **Status:** Active
> **Data Source:** Massive REST API (formerly Polygon.io, rebranded Oct 30 2025)
> **Target Module:** `SpyderC_MarketData/SpyderC28_MassiveHistoricalDownloader.py`

---

## 1. What Massive Provides

### 1.1 API Base URL

```
https://api.polygon.io   (canonical — Massive kept the Polygon domain)
```

Authentication: `?apiKey={MASSIVE_API_KEY}` query parameter on every request.

### 1.2 Subscription Capability Matrix

The current Massive subscription supports the following endpoints. This was
verified empirically — **do not assume additional access without testing**.

| Endpoint | Status | Notes |
|---|---|---|
| `/v2/aggs/ticker/{T}/range/{m}/{span}/{from}/{to}` | **✅ Works** | Daily and minute bars for equities AND options |
| `/v3/reference/options/contracts` | **✅ Works** | List option contracts with pagination |
| `/v3/reference/tickers` | **✅ Works** | Ticker lookup and search |
| `/v2/aggs/grouped/locale/us/market/stocks/{date}` | **✅ Works** | All tickers daily bars in one call |
| `/v1/marketstatus/now` | **✅ Works** | Market open/closed status |
| `/v2/last/trade/{T}` | ❌ `NOT_AUTHORIZED` | Tick-level trades |
| `/v2/last/nbbo/{T}` | ❌ `NOT_AUTHORIZED` | Tick-level quotes |
| `/v3/snapshot/options/{underlying}` | ❌ `NOT_AUTHORIZED` | Options chain snapshot |
| S3 flat files (`files.massive.com`) | ❌ `403 Forbidden` | Only `ListObjectsV2` works; `GetObject` blocked |

### 1.3 Available Data via REST API

| Data Type | Endpoint | Granularity | Use Case |
|---|---|---|---|
| **SPY Daily Bars** | `/v2/aggs/.../day/...` | 1 bar/day | Underlying daily OHLCV, backtesting |
| **SPY Minute Bars** | `/v2/aggs/.../minute/...` | ~911 bars/day (incl. extended hours) | Intraday underlying, delta hedging |
| **Options Contract List** | `/v3/reference/options/contracts` | Per expiration, paginated (250/page) | Contract enumeration for iteration |
| **Options Daily Bars** | `/v2/aggs/.../day/...` for `O:` tickers | 1 bar/contract/day | Options screening, daily OHLCV |
| **Options Minute Bars** | `/v2/aggs/.../minute/...` for `O:` tickers | Varies by contract volume | Intraday options bars for backtesting |
| **Index Daily/Minute Bars** | `/v2/aggs/...` for `I:` tickers | Day or minute | VIX, SPX reference levels |

### 1.4 What Is NOT Available

- **Tick-level trades/quotes** — subscription tier blocks these
- **Options chain snapshots** — requires higher tier
- **S3 flat file downloads** — 403 on all download operations (listing works)
- **Market internals** ($TICK, $TRIN, $ADD, $VOLD) — broker-computed, not in any feed

---

## 2. OPRA Options Ticker Format

Massive uses the standard OPRA ticker format for options:

```
O:{UNDERLYING}{YYMMDD}{C|P}{8-digit strike in thousandths}
```

**Examples:**
- `O:SPY260320C00565000` → SPY, 2026-03-20, Call, $565.00
- `O:SPY260321P00582500` → SPY, 2026-03-21, Put, $582.50

**Parsing regex:**
```python
r'^O:([A-Z]+)(\d{6})([CP])(\d{8})$'
#    underlying  YYMMDD  C/P  strike×1000
```

---

## 3. REST API Response Formats

### 3.1 Aggregates (Bars) Response

`GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}?apiKey=...`

```json
{
  "ticker": "O:SPY260321C00580000",
  "queryCount": 198,
  "resultsCount": 198,
  "adjusted": false,
  "results": [
    {
      "v": 12345,         // volume
      "vw": 8.5432,       // VWAP
      "o": 8.50,          // open
      "c": 8.55,          // close
      "h": 8.60,          // high
      "l": 8.45,          // low
      "t": 1710849600000, // Unix ms timestamp (start of bar)
      "n": 87             // number of transactions
    }
  ],
  "status": "OK",
  "request_id": "...",
  "count": 198
}
```

### 3.2 Options Contracts Reference Response

`GET /v3/reference/options/contracts?underlying_ticker=SPY&expiration_date=2026-03-21&limit=250&apiKey=...`

```json
{
  "results": [
    {
      "ticker": "O:SPY260321C00400000",
      "underlying_ticker": "SPY",
      "contract_type": "call",
      "expiration_date": "2026-03-21",
      "strike_price": 400.0,
      "shares_per_contract": 100,
      "exercise_style": "american",
      "primary_exchange": "BATO",
      "cfi": "OCAXXX"
    }
  ],
  "status": "OK",
  "next_url": "https://api.polygon.io/v3/reference/options/contracts?cursor=...&apiKey=..."
}
```

Pagination: follow `next_url` until it is absent. Typically ~528 contracts per SPY expiration date.

---

## 4. Datasets to Download for Spyder Backtesting

### 4.1 Priority Matrix (REST API)

| Priority | Dataset | Method | Purpose | API Calls/Day |
|---|---|---|---|---|
| **P0** | Options Daily Bars | Aggs endpoint per contract | Daily OHLCV for all SPY option contracts | ~500-600 |
| **P1** | Options Minute Bars | Aggs endpoint per contract | Intraday option price bars for backtesting | ~500-600 |
| **P1** | SPY Daily Bars | Single aggs call | Underlying daily OHLCV | 1 |
| **P1** | SPY Minute Bars | Single aggs call | Underlying intraday for delta hedging | 1 |
| **P2** | Index Daily Bars | Aggs per index ticker | VIX, SPX reference levels | 5-6 |
| **P2** | Index Minute Bars | Aggs per index ticker | Intraday VIX for regime detection | 5-6 |
| **P3** | Contract Enumeration | Contracts reference | List all SPY contracts per expiration | 2-3/expiry |

### 4.2 API Call Budget Estimate

For **one trading day** of full SPY options data:
- Contract listing: ~3 paginated calls per expiration × ~5 active expirations = ~15 calls
- Options daily bars: ~500 contracts × 1 call = ~500 calls
- Options minute bars: ~500 contracts × 1 call = ~500 calls
- SPY underlying: 2 calls (daily + minute)
- Indices (VIX, SPX, etc.): ~12 calls

**Total: ~1,030 calls/day at 3 RPS ≈ 5.7 minutes per trading day**

For one year (252 trading days): ~260,000 calls ≈ 24 hours continuous.

### 4.3 Recommended Initial Download

Start with a focused dataset to validate the pipeline:

1. **SPY Daily + Minute Bars** — 1 month (2 API calls total — fast to verify)
2. **Options Contract List** — 1 week (enumerate active contracts)
3. **Options Daily Bars** — 1 week (~2,500 calls, ~14 minutes)
4. **Options Minute Bars** — 1-2 days (~1,000 calls, ~6 minutes)
5. **Index Bars** (VIX, SPX) — same date range

---

## 5. Local Directory Structure

Since we download JSON from the REST API and convert directly to Parquet,
there is no raw CSV.gz stage. The structure is simplified:

```
Spyder-Backtest/
├── parquet/
│   ├── spy_options/
│   │   ├── day_aggs/
│   │   │   └── 2026-03-17.parquet     # All SPY option contracts, daily bars
│   │   └── minute_aggs/
│   │       └── 2026-03-17.parquet     # All SPY option contracts, minute bars
│   ├── spy_underlying/
│   │   ├── day_aggs/
│   │   │   └── 2026-03-17.parquet     # SPY equity daily bars
│   │   └── minute_aggs/
│   │       └── 2026-03-17.parquet     # SPY equity minute bars
│   ├── indices/
│   │   ├── day_aggs/
│   │   │   └── 2026-03-17.parquet     # VIX, SPX, etc. daily bars
│   │   └── minute_aggs/
│   │       └── 2026-03-17.parquet     # VIX, SPX, etc. minute bars
│   └── contracts/
│       └── 2026-03-17.parquet         # Contract reference data snapshot
│
├── checkpoints/
│   └── download_state.json            # Resume state for interrupted downloads
│
└── manifest.json                      # Metadata: date ranges, row counts, last update
```

**Key design decisions:**
- One Parquet file per date per data type — easy to reason about, resume, and validate
- All SPY option contracts for a date are in a single file (not per-contract files)
- Parquet uses `zstd` compression (best balance of size and read speed)
- No raw intermediate files — REST JSON is converted in-memory to Parquet

---

## 6. Implementation Specifications

### 6.1 Dependencies

```bash
source .venv/bin/activate
pip install polars pyarrow requests python-dotenv exchange-calendars
```

- **polars** — DataFrame library (5-10x faster than pandas for I/O)
- **pyarrow** — Parquet read/write backend
- **requests** — HTTP client for REST API calls
- **python-dotenv** — Load `.env` credentials
- **exchange-calendars** — NYSE trading calendar for holiday detection

### 6.2 Module Location

```
Spyder/SpyderC_MarketData/SpyderC28_MassiveHistoricalDownloader.py
```

Single-file module following Spyder naming conventions. No separate package — all
download, conversion, validation, and CLI logic in one file.

### 6.3 Core Algorithm

```
for each trading_day in date_range:
    if checkpoint says day is complete → skip

    1. Fetch SPY daily bars  ──→ append to day_aggs parquet
    2. Fetch SPY minute bars ──→ append to minute_aggs parquet
    3. Fetch index bars (VIX, SPX, …) ──→ append to indices parquet
    4. List all SPY option contracts active on this date
       (paginate /v3/reference/options/contracts)
    5. For each contract:
       a. Fetch daily bars   ──→ accumulate
       b. Fetch minute bars  ──→ accumulate
    6. Write accumulated options data to parquet (one file per date)
    7. Update checkpoint

    Rate limit: 3 requests/second (configurable via MASSIVE_REST_RPS)
```

### 6.4 REST API Calls

**Fetch bars:**
```python
GET /v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}?adjusted=false&sort=asc&limit=50000&apiKey=...
GET /v2/aggs/ticker/{ticker}/range/1/minute/{from}/{to}?adjusted=false&sort=asc&limit=50000&apiKey=...
```

**List contracts:**
```python
GET /v3/reference/options/contracts?underlying_ticker=SPY&expiration_date={date}&limit=250&apiKey=...
# Follow next_url for pagination
```

**Response field mapping to Parquet columns:**

| REST Field | Parquet Column | Type | Description |
|---|---|---|---|
| `results[].o` | `open` | Float64 | Open price |
| `results[].h` | `high` | Float64 | High price |
| `results[].l` | `low` | Float64 | Low price |
| `results[].c` | `close` | Float64 | Close price |
| `results[].v` | `volume` | Int64 | Volume |
| `results[].vw` | `vwap` | Float64 | VWAP |
| `results[].t` | `timestamp` | Datetime(ms) | Bar start time (UTC) |
| `results[].n` | `transactions` | Int64 | Number of transactions |
| (added) | `ticker` | Utf8 | Ticker symbol |

### 6.5 Rate Limiting

Use a **token bucket** rate limiter. Default: 3 requests/second (configurable via
`MASSIVE_REST_RPS` env var). Wait before each request if the bucket is empty.

Implement exponential backoff on HTTP 429 (Too Many Requests) or 5xx errors.
Retry up to 3 times with delays of 1s, 2s, 4s.

### 6.6 Checkpoint / Resume Logic

Maintain `Spyder-Backtest/checkpoints/download_state.json`:

```json
{
  "last_completed_date": "2026-03-14",
  "dates_completed": ["2026-03-10", "2026-03-11", ...],
  "current_date": "2026-03-17",
  "current_phase": "options_minute_bars",
  "contracts_completed": 342,
  "contracts_total": 528,
  "started_at": "2026-03-19T10:30:00",
  "errors": []
}
```

On startup, read the checkpoint and resume from where it left off. This prevents
re-downloading data after an interruption (network error, restart, etc.).

---

## 7. Timestamp Handling

REST API returns timestamps as **Unix milliseconds (UTC)**.

Convert to Eastern Time for market-hours alignment:

```python
import polars as pl

def add_eastern_time(df: pl.DataFrame, ts_column: str = "timestamp") -> pl.DataFrame:
    """Add Eastern Time column from millisecond UTC timestamps."""
    return df.with_columns(
        pl.col(ts_column)
        .cast(pl.Datetime("ms"))
        .dt.replace_time_zone("UTC")
        .dt.convert_time_zone("America/New_York")
        .alias("datetime_et")
    )
```

---

## 8. OPRA Ticker Parsing Utility

```python
import re
from dataclasses import dataclass
from datetime import date

@dataclass
class OptionContract:
    underlying: str
    expiration: date
    call_put: str       # 'C' or 'P'
    strike: float

def parse_opra_ticker(ticker: str) -> OptionContract:
    """
    Parse an OPRA option ticker symbol.
    Format: O:{UNDERLYING}{YYMMDD}{C|P}{STRIKE×1000 padded to 8 digits}
    Example: O:SPY260320C00560000 → SPY, 2026-03-20, Call, $560.00
    """
    match = re.match(r'^O:([A-Z]+)(\d{6})([CP])(\d{8})$', ticker)
    if not match:
        raise ValueError(f"Invalid OPRA ticker: {ticker}")

    underlying = match.group(1)
    exp_str = match.group(2)
    cp = match.group(3)
    strike_raw = match.group(4)

    expiration = date(
        year=2000 + int(exp_str[:2]),
        month=int(exp_str[2:4]),
        day=int(exp_str[4:6]),
    )
    strike = int(strike_raw) / 1000.0

    return OptionContract(
        underlying=underlying,
        expiration=expiration,
        call_put=cp,
        strike=strike,
    )
```

---

## 9. Validation & Integrity Checks

After downloading and converting, validate each Parquet file:

```python
def validate_parquet(parquet_path: str) -> dict:
    """Run basic integrity checks on a Parquet file."""
    df = pl.read_parquet(parquet_path)
    checks = {
        "file": parquet_path,
        "row_count": len(df),
        "columns": df.columns,
        "null_counts": {col: df[col].null_count() for col in df.columns},
        "file_size_mb": round(os.path.getsize(parquet_path) / (1024 * 1024), 2),
    }

    if "ticker" in df.columns:
        tickers = df["ticker"].unique().to_list()
        checks["unique_tickers"] = len(tickers)
        checks["all_spy"] = all(
            t.startswith("O:SPY") or t in ("SPY", "I:SPX", "I:VIX", "I:DJI", "I:NDX", "I:COMP", "I:RUT")
            for t in tickers
        )
    checks["status"] = "EMPTY" if checks["row_count"] == 0 else "OK"
    return checks
```

---

## 10. Error Handling & Resilience

The downloader must implement:

1. **Retry with exponential backoff** on HTTP 429, 5xx, and network errors (up to 3 retries)
2. **Skip weekends and holidays** — use `exchange-calendars` NYSE calendar
3. **Checkpoint/resume** — save state after each completed date for crash recovery
4. **Graceful degradation** — if a contract returns empty bars, log and continue (many
   deep OTM contracts have zero volume)
5. **Logging** — use `SpyderLogger` (never `print()`) for all output
6. **Progress reporting** — log percentage complete, ETA, and current contract ticker

---

## 11. CLI Interface

The downloader supports the following CLI modes:

```bash
# Backfill a date range
python -m SpyderC_MarketData.SpyderC28_MassiveHistoricalDownloader \
    --mode backfill --start 2025-01-02 --end 2025-12-31

# Download yesterday's data (for daily cron)
python -m SpyderC_MarketData.SpyderC28_MassiveHistoricalDownloader \
    --mode daily

# Download specific date
python -m SpyderC_MarketData.SpyderC28_MassiveHistoricalDownloader \
    --mode single --date 2026-03-17

# Validate existing data
python -m SpyderC_MarketData.SpyderC28_MassiveHistoricalDownloader \
    --mode validate --start 2025-01-02 --end 2025-12-31

# Resume interrupted download (reads checkpoint automatically)
python -m SpyderC_MarketData.SpyderC28_MassiveHistoricalDownloader \
    --mode resume
```

---

## 12. Performance Notes

- **Rate limit:** 3 REST calls/second by default (configurable via `MASSIVE_REST_RPS`)
- **Per-day download time:** ~5-6 minutes at 3 RPS (dominated by per-contract option bar fetches)
- **Per-year download time:** ~24 hours at 3 RPS (~260,000 API calls)
- **Parquet compression:** Use `zstd` for best size/speed balance
- **Disk usage estimate** (after Parquet conversion, SPY options only):
  - Options Daily Bars: ~2-10 MB/day → ~500 MB - 2.5 GB/year
  - Options Minute Bars: ~10-50 MB/day → ~2.5 - 12.5 GB/year
  - SPY Underlying (daily+minute): ~1 MB/day → ~250 MB/year
  - Indices: ~1 MB/day → ~250 MB/year
- **Memory:** Polars DataFrames are efficient; a full day of options data (~500 contracts
  × ~200 bars each = ~100K rows) fits easily in memory
- **Parallelism:** The module is single-threaded by design to respect rate limits.
  Do not add parallelism without confirming higher RPS is allowed.

---

## 13. Agent Task Checklist

1. **[x] Store credentials** in `.env` — `MASSIVE_API_KEY`, `BACKTEST_DATA_ROOT`
2. **[x] Create directory structure** under `Spyder-Backtest/`
3. **[ ] Implement `SpyderC28_MassiveHistoricalDownloader.py`**
   - REST API client (requests-based, rate-limited)
   - Contract enumeration with pagination
   - Bar fetching for equities, options, and indices
   - Parquet conversion via polars
   - Checkpoint/resume logic
   - CLI interface with argparse
   - Validation mode
4. **[ ] Test with 1 day** of Options Daily Bars (smallest dataset, ~500 API calls)
5. **[ ] Expand** to full backfill of desired date range
6. **[ ] Integrate** Parquet reader into `SpyderR_Runtime` backtesting engine

---

## 14. Integration with Existing SpyderC27_MassiveClient

The new `SpyderC28_MassiveHistoricalDownloader` is **separate** from the existing
`SpyderC27_MassiveClient`. Key differences:

| Aspect | C27 MassiveClient | C28 HistoricalDownloader |
|---|---|---|
| **Purpose** | Live/real-time market data | Bulk historical data download |
| **HTTP Client** | `polygon` SDK (`RESTClient`) | `requests` (direct REST calls) |
| **Rate Limit** | Token bucket (real-time) | Token bucket (bulk download) |
| **Output** | pandas DataFrames (in memory) | Parquet files (on disk) |
| **Resume** | N/A | Checkpoint/resume JSON |
| **CLI** | No | argparse CLI |

The downloader uses `requests` directly rather than the `polygon`/`massive` SDK to
avoid SDK version issues and to have full control over pagination, retries, and URL
construction.

---

## 15. Project-Wide Documentation Update Required

The Spyder project has migrated from **Interactive Brokers to Tradier** as its broker.
The following project documents and modules contain stale IB references that need updating:

| Area | What Needs Changing |
|---|---|
| **Project Overview / README** | Replace "Interactive Brokers" references with "Tradier" |
| **SpyderB_Broker** | Verify implementation targets Tradier API, not IB TWS/Gateway |
| **SpyderC_MarketData** | If any feeds use IB, reroute to Tradier or Massive |
| **Order Management** | IB-specific concepts (TWS smart routing) → Tradier REST API |
| **Market Internals** | IB pseudo-tickers ($TICK, $TRIN) → compute from data or remove |
