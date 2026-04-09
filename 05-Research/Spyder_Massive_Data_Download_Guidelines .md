# Spyder: Massive.com Historical Data Download — Guidelines & Specs

> **Purpose:** Step-by-step specifications for a coding agent to build an automated pipeline that downloads historical SPY options data (and supporting datasets) from Massive.com's S3-compatible Flat Files service into the Spyder repo for backtesting.

---

## 1. What Massive.com Provides

Massive.com (formerly Polygon.io) delivers historical U.S. market data as **compressed CSV Flat Files** via an S3-compatible endpoint. Each file contains one full trading day of data across **all tickers** in that asset class. Files are generated after market close and available by ~11:00 AM ET the following day.

### 1.1 Asset Classes & S3 Prefixes

| Asset Class | S3 Prefix | What's Inside |
|---|---|---|
| **Options (OPRA)** | `us_options_opra/` | All U.S. options across all 17 OPRA exchanges |
| **Stocks (SIP)** | `us_stocks_sip/` | All U.S. equities (NYSE, Nasdaq, Cboe, FINRA, dark pools) |
| **Indices** | `us_indices/` | 11,400+ indices (SPX, VIX, DJI, NDX, etc.) sourced from CME, CBOE, Nasdaq |
| **Forex** | `global_forex/` | Global forex pairs |
| **Crypto** | `global_crypto/` | Global cryptocurrency data |

### 1.2 Data Types Per Asset Class

Each prefix contains subdirectories for different data granularities:

| Data Type | Subdirectory Pattern | Description |
|---|---|---|
| **Trades** | `trades_v1/` | Tick-level trade data, nanosecond timestamps |
| **Quotes** | `quotes_v1/` | Top-of-book bid/ask with nanosecond timestamps |
| **Minute Aggregates** | `minute_aggs_v1/` | OHLCV candles per minute |
| **Day Aggregates** | `day_aggs_v1/` | OHLCV candles per day |

### 1.3 S3 Path Format

```
flatfiles/{prefix}/{data_type}/{YYYY}/{MM}/{YYYY-MM-DD}.csv.gz
```

**Examples:**
```
flatfiles/us_options_opra/trades_v1/2026/03/2026-03-17.csv.gz
flatfiles/us_options_opra/quotes_v1/2026/03/2026-03-17.csv.gz
flatfiles/us_options_opra/minute_aggs_v1/2026/03/2026-03-17.csv.gz
flatfiles/us_options_opra/day_aggs_v1/2026/03/2026-03-17.csv.gz
flatfiles/us_stocks_sip/trades_v1/2026/03/2026-03-17.csv.gz
flatfiles/us_indices/day_aggs_v1/2026/03/2026-03-17.csv.gz
```

---

## 2. What You Get (and Don't Get)

### 2.1 Options Data (OPRA) — What You Get

The `us_options_opra/` files contain the **full OPRA feed**: every options trade and quote across all 17 U.S. options exchanges (CBOE, NYSE American, Nasdaq, MIAX, BOX, etc.) for **every** optionable underlying — not just SPY.

**Ticker format is OPRA symbology:**
```
O:SPY260320C00560000
│ │   │     │ │
│ │   │     │ └── Strike price × 1000 (left-padded zeros) → $560.00
│ │   │     └──── C = Call, P = Put
│ │   └────────── Expiration: YYMMDD → 2026-03-20
│ └────────────── Underlying: SPY
└──────────────── Prefix: O: denotes options
```

**Options Trades CSV columns** (expected schema based on Massive/Polygon conventions):
```
ticker, conditions, correction, exchange, id, participant_timestamp, price, sequence_number, sip_timestamp, size
```

**Options Quotes CSV columns** (expected):
```
ticker, ask_exchange, ask_price, ask_size, bid_exchange, bid_price, bid_size, sequence_number, sip_timestamp
```

**Options Minute/Day Aggs CSV columns:**
```
ticker, volume, open, close, high, low, window_start, transactions
```

> **IMPORTANT:** `ask_size` and `bid_size` are reported in **shares** (not round lots) as of Nov 3, 2025 per SEC MDI rules. All timestamps are **Unix nanosecond UTC**.

### 2.2 Stocks Data (SIP) — SPY ETF Underlying

The `us_stocks_sip/` files contain tick-level data for all U.S. equities. You will filter for `SPY` to get the underlying ETF price data for your backtester.

### 2.3 Indices — What's Available and What's NOT

Massive provides **11,400+ index tickers** prefixed with `I:` (e.g., `I:SPX`, `I:VIX`, `I:DJI`, `I:NDX`). These are sourced from CME Group, CBOE, and Nasdaq.

**Available in Indices Flat Files:**
- S&P 500 (`I:SPX`)
- VIX (`I:VIX`)
- Dow Jones (`I:DJI`)
- Nasdaq Composite / Nasdaq-100 (`I:COMP`, `I:NDX`)
- Thousands of other market/sector/thematic indices

**NOT available from Massive Flat Files:**
- **$TICK (NYSE Tick Index)** — Not a standard exchange index; it's a broker-computed internal
- **$TRIN (Arms Index)** — Same; computed by brokers from advance/decline data
- **$ADD (Advance/Decline Difference)** — Broker-computed, not in OPRA/SIP/Indices feeds
- **$VOLD (Volume Difference)** — Broker-computed

> **For market internals (TICK, TRIN, ADD, VOLD):** These are not available from Massive or from Tradier (our broker). The only viable path is to **compute them from the Massive `us_stocks_sip` trade files**, which contain every tick for every U.S. stock. From this data you can derive advance/decline counts, uptick/downtick counts, and volume differentials per time interval. This is a non-trivial computation but fully doable as a post-processing step in the conversion pipeline.

---

## 3. S3 Connection Configuration

### 3.1 Credentials

| Parameter | Value |
|---|---|
| **Endpoint** | `https://files.massive.com` |
| **Bucket** | `flatfiles` |
| **Signature** | `s3v4` |
| **Access Key** | From Massive Dashboard (S3-specific, not API key) |
| **Secret Key** | From Massive Dashboard (S3-specific, not API key) |

### 3.2 Credential Storage

Store credentials in the Spyder config system. **Never hardcode keys in source files.**

Recommended: use environment variables or a `.env` file excluded from version control.

```bash
# .env (add to .gitignore)
MASSIVE_S3_ACCESS_KEY=your_access_key_here
MASSIVE_S3_SECRET_KEY=your_secret_key_here
```

---

## 4. Datasets to Download for Spyder Backtesting

### 4.1 Priority Matrix

| Priority | Dataset | S3 Prefix | Purpose | Size Estimate/Day |
|---|---|---|---|---|
| **P0** | Options Trades | `us_options_opra/trades_v1/` | Core: reconstruct fills, slippage | ~5-15 GB compressed |
| **P0** | Options Day Aggs | `us_options_opra/day_aggs_v1/` | Daily OHLCV for all option contracts | ~50-200 MB compressed |
| **P1** | Options Minute Aggs | `us_options_opra/minute_aggs_v1/` | Intraday option price bars | ~1-5 GB compressed |
| **P1** | Options Quotes | `us_options_opra/quotes_v1/` | Bid/ask spreads, NBBO reconstruction | ~50-120 GB compressed |
| **P2** | Stock Trades (SPY) | `us_stocks_sip/trades_v1/` | Underlying price for delta hedging | ~1-2 GB compressed |
| **P2** | Stock Minute Aggs | `us_stocks_sip/minute_aggs_v1/` | Underlying OHLCV bars | ~100-300 MB compressed |
| **P3** | Indices Day Aggs | `us_indices/day_aggs_v1/` | VIX, SPX reference levels | ~10-50 MB compressed |
| **P3** | Indices Minute Aggs | `us_indices/minute_aggs_v1/` | Intraday VIX for vol regime detection | ~50-200 MB compressed |

> **WARNING:** Options Quotes files are enormous (the 2024 year totals ~23.5 TB compressed). Download these only if you need NBBO reconstruction. For most backtesting, Trades + Minute Aggs are sufficient.

### 4.2 Recommended Initial Download

Start with a focused dataset to validate the pipeline:

1. **Options Day Aggs** — 1 month of data (small, fast to verify)
2. **Options Minute Aggs** — 1 week (validate intraday capability)
3. **Options Trades** — 1-2 days (validate tick-level processing)
4. **Stock Minute Aggs** — same date range (underlying reference)
5. **Indices Day Aggs** — same date range (VIX/SPX reference)

---

## 5. Local Directory Structure

```
Spyder/
└── data/
    └── massive/
        ├── raw/                          # Downloaded .csv.gz files (mirror S3 structure)
        │   ├── us_options_opra/
        │   │   ├── trades_v1/
        │   │   │   └── 2026/03/2026-03-17.csv.gz
        │   │   ├── quotes_v1/
        │   │   ├── minute_aggs_v1/
        │   │   └── day_aggs_v1/
        │   ├── us_stocks_sip/
        │   │   ├── trades_v1/
        │   │   └── minute_aggs_v1/
        │   └── us_indices/
        │       ├── day_aggs_v1/
        │       └── minute_aggs_v1/
        │
        ├── parquet/                      # Converted + filtered Parquet files
        │   ├── spy_options/
        │   │   ├── trades/
        │   │   │   └── 2026-03-17.parquet
        │   │   ├── quotes/
        │   │   ├── minute_aggs/
        │   │   └── day_aggs/
        │   ├── spy_underlying/
        │   │   ├── trades/
        │   │   └── minute_aggs/
        │   └── indices/
        │       ├── day_aggs/
        │       └── minute_aggs/
        │
        ├── download_log.json             # Track what's been downloaded
        └── manifest.json                 # Metadata about available data range
```

---

## 6. Implementation Specifications

### 6.1 Dependencies

```bash
pip install boto3 polars pyarrow python-dotenv --break-system-packages
```

Or in the Spyder `.venv`:
```bash
source .venv/bin/activate
pip install boto3 polars pyarrow python-dotenv
```

### 6.2 Module Structure

Create a new module: `SpyderX_DataPipeline/` (or integrate into `SpyderC_MarketData/`).

```
SpyderX_DataPipeline/
├── __init__.py
├── config.py              # S3 credentials, paths, dataset definitions
├── downloader.py          # Boto3 S3 download logic
├── converter.py           # CSV.gz → filtered Parquet conversion
├── pipeline.py            # Orchestrates download + convert + validate
├── scheduler.py           # Cron/systemd scheduling for daily updates
└── utils.py               # Date ranges, trading calendar, logging
```

### 6.3 S3 Client Initialization

```python
import boto3
from botocore.config import Config
from dotenv import load_dotenv
import os

load_dotenv()

def get_s3_client():
    """Initialize Massive.com S3-compatible client."""
    session = boto3.Session(
        aws_access_key_id=os.getenv('MASSIVE_S3_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('MASSIVE_S3_SECRET_KEY'),
    )
    return session.client(
        's3',
        endpoint_url='https://files.massive.com',
        config=Config(signature_version='s3v4'),
    )

BUCKET = 'flatfiles'
```

### 6.4 Download Logic

```python
import os
from datetime import date, timedelta

def build_s3_key(prefix: str, data_type: str, dt: date) -> str:
    """Build the S3 object key for a given dataset and date."""
    return f"{prefix}/{data_type}/{dt.year}/{dt.month:02d}/{dt.isoformat()}.csv.gz"

def download_file(s3_client, s3_key: str, local_path: str, skip_existing: bool = True) -> bool:
    """
    Download a single file from Massive S3.
    
    Returns True if file was downloaded, False if skipped.
    Raises exception on failure.
    """
    if skip_existing and os.path.exists(local_path):
        return False
    
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    # Check if the object exists before downloading
    try:
        s3_client.head_object(Bucket=BUCKET, Key=s3_key)
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            # File doesn't exist (weekend/holiday)
            return False
        raise
    
    s3_client.download_file(BUCKET, s3_key, local_path)
    return True

def download_date_range(
    s3_client,
    prefix: str,
    data_type: str,
    start_date: date,
    end_date: date,
    local_base: str,
) -> list[str]:
    """Download all files in a date range. Returns list of downloaded paths."""
    downloaded = []
    current = start_date
    while current <= end_date:
        # Skip weekends
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue
        
        s3_key = build_s3_key(prefix, data_type, current)
        local_path = os.path.join(local_base, s3_key.replace('/', os.sep))
        
        try:
            if download_file(s3_client, s3_key, local_path):
                downloaded.append(local_path)
                print(f"Downloaded: {s3_key}")
            else:
                print(f"Skipped (exists or not available): {s3_key}")
        except Exception as e:
            print(f"ERROR downloading {s3_key}: {e}")
        
        current += timedelta(days=1)
    
    return downloaded
```

### 6.5 Listing Available Files

Use the S3 paginator to discover what files are available before downloading:

```python
def list_available_files(s3_client, prefix: str, data_type: str, year: int = None, month: int = None) -> list[str]:
    """List all available files for a given dataset. Optionally filter by year/month."""
    search_prefix = f"{prefix}/{data_type}/"
    if year:
        search_prefix += f"{year}/"
        if month:
            search_prefix += f"{month:02d}/"
    
    paginator = s3_client.get_paginator('list_objects_v2')
    keys = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=search_prefix):
        for obj in page.get('Contents', []):
            keys.append(obj['Key'])
    return keys
```

### 6.6 CSV.gz → Parquet Conversion (with SPY Filtering)

```python
import polars as pl

# Filter patterns for SPY-related options tickers
SPY_OPTIONS_FILTER = "O:SPY"
SPY_STOCK_FILTER = "SPY"
# For indices, keep VIX, SPX and a few useful benchmarks
INDICES_KEEP = ["I:SPX", "I:VIX", "I:DJI", "I:NDX", "I:COMP", "I:RUT"]

def convert_to_parquet(
    csv_gz_path: str,
    parquet_path: str,
    ticker_filter: str | list[str] | None = None,
    ticker_prefix_filter: str | None = None,
) -> int:
    """
    Convert a compressed CSV to filtered Parquet.
    
    Args:
        csv_gz_path: Path to the .csv.gz file
        parquet_path: Output .parquet path
        ticker_filter: Exact ticker(s) to keep
        ticker_prefix_filter: Ticker prefix to match (e.g., "O:SPY")
    
    Returns:
        Number of rows in the output file.
    """
    # Use Polars lazy scan for memory efficiency on large files
    df = pl.read_csv(csv_gz_path)
    
    # Apply ticker filter
    if ticker_prefix_filter:
        df = df.filter(pl.col("ticker").str.starts_with(ticker_prefix_filter))
    elif ticker_filter:
        if isinstance(ticker_filter, str):
            ticker_filter = [ticker_filter]
        df = df.filter(pl.col("ticker").is_in(ticker_filter))
    
    if len(df) == 0:
        print(f"WARNING: No matching rows in {csv_gz_path}")
        return 0
    
    os.makedirs(os.path.dirname(parquet_path), exist_ok=True)
    df.write_parquet(parquet_path, compression="zstd")
    
    return len(df)


def convert_options_day(csv_gz_path: str, parquet_dir: str, dt: date) -> int:
    """Convert options day aggs, filtering for SPY options only."""
    return convert_to_parquet(
        csv_gz_path,
        os.path.join(parquet_dir, "spy_options", "day_aggs", f"{dt.isoformat()}.parquet"),
        ticker_prefix_filter=SPY_OPTIONS_FILTER,
    )

def convert_options_trades(csv_gz_path: str, parquet_dir: str, dt: date) -> int:
    """Convert options trades, filtering for SPY options only."""
    return convert_to_parquet(
        csv_gz_path,
        os.path.join(parquet_dir, "spy_options", "trades", f"{dt.isoformat()}.parquet"),
        ticker_prefix_filter=SPY_OPTIONS_FILTER,
    )

def convert_stock_minute_aggs(csv_gz_path: str, parquet_dir: str, dt: date) -> int:
    """Convert stock minute aggs, filtering for SPY only."""
    return convert_to_parquet(
        csv_gz_path,
        os.path.join(parquet_dir, "spy_underlying", "minute_aggs", f"{dt.isoformat()}.parquet"),
        ticker_filter=SPY_STOCK_FILTER,
    )

def convert_indices(csv_gz_path: str, parquet_dir: str, dt: date, data_type: str = "day_aggs") -> int:
    """Convert indices data, keeping only relevant indices."""
    return convert_to_parquet(
        csv_gz_path,
        os.path.join(parquet_dir, "indices", data_type, f"{dt.isoformat()}.parquet"),
        ticker_filter=INDICES_KEEP,
    )
```

### 6.7 Memory Considerations for Large Files

Options Trades and Quotes files can be extremely large (multi-GB compressed, tens of GB uncompressed). For these:

```python
def convert_large_file_chunked(
    csv_gz_path: str,
    parquet_path: str,
    ticker_prefix: str,
    chunk_size: int = 5_000_000,
) -> int:
    """
    Stream-convert large CSV.gz files using Polars batched reader.
    Avoids loading entire file into memory.
    """
    reader = pl.read_csv_batched(csv_gz_path, batch_size=chunk_size)
    total_rows = 0
    first_batch = True
    
    while True:
        batches = reader.next_batches(1)
        if not batches:
            break
        
        batch = batches[0]
        filtered = batch.filter(pl.col("ticker").str.starts_with(ticker_prefix))
        
        if len(filtered) > 0:
            if first_batch:
                filtered.write_parquet(parquet_path, compression="zstd")
                first_batch = False
            else:
                # Append: read existing, concat, rewrite
                # For truly huge datasets, consider writing to multiple part files
                existing = pl.read_parquet(parquet_path)
                combined = pl.concat([existing, filtered])
                combined.write_parquet(parquet_path, compression="zstd")
            
            total_rows += len(filtered)
    
    return total_rows
```

> **Alternative for very large files:** Write partitioned Parquet (one file per expiration date or per hour) using `pl.DataFrame.write_parquet` with hive partitioning, or use `pyarrow.parquet.ParquetWriter` in append mode.

---

## 7. Timestamp Handling

All Massive timestamps are **Unix nanoseconds in UTC**. Convert to Eastern Time for market-hours alignment:

```python
import polars as pl

def add_eastern_time(df: pl.DataFrame, ts_column: str = "sip_timestamp") -> pl.DataFrame:
    """Add a human-readable Eastern Time column from nanosecond UTC timestamps."""
    return df.with_columns(
        (pl.col(ts_column) // 1_000_000)  # ns → ms
        .cast(pl.Datetime("ms"))
        .dt.replace_time_zone("UTC")
        .dt.convert_time_zone("America/New_York")
        .alias("datetime_et")
    )
```

For `window_start` in aggregates, same logic applies.

---

## 8. OPRA Ticker Parsing Utility

Essential for backtesting: parse the OPRA ticker into its components.

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
    match = re.match(
        r'^O:([A-Z]+)(\d{6})([CP])(\d{8})$',
        ticker
    )
    if not match:
        raise ValueError(f"Invalid OPRA ticker: {ticker}")
    
    underlying = match.group(1)
    exp_str = match.group(2)   # YYMMDD
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

## 9. Daily Update Scheduler

For keeping data current after the initial backfill:

```python
# daily_update.sh — run via cron at 12:00 PM ET (after 11 AM availability)
# crontab entry:
# 0 12 * * 1-5 /path/to/Spyder/.venv/bin/python /path/to/Spyder/SpyderX_DataPipeline/pipeline.py --mode daily
```

The `pipeline.py --mode daily` should:
1. Determine yesterday's trading date (skip weekends/holidays)
2. Download all configured datasets for that date
3. Convert to filtered Parquet
4. Update `download_log.json`
5. Log results and any errors

For a proper trading calendar (handling market holidays), use the `exchange_calendars` or `pandas_market_calendars` package:

```bash
pip install exchange-calendars
```

```python
import exchange_calendars as xcals

nyse = xcals.get_calendar('XNYS')

def is_trading_day(dt: date) -> bool:
    """Check if a date is a valid NYSE trading day."""
    import pandas as pd
    return nyse.is_session(pd.Timestamp(dt))
```

---

## 10. Validation & Integrity Checks

After downloading and converting, validate the data:

```python
def validate_parquet(parquet_path: str, expected_date: date) -> dict:
    """Run basic integrity checks on a converted Parquet file."""
    df = pl.read_parquet(parquet_path)
    
    checks = {
        "file": parquet_path,
        "row_count": len(df),
        "columns": df.columns,
        "null_counts": {col: df[col].null_count() for col in df.columns},
        "ticker_sample": df["ticker"].unique().head(10).to_list(),
        "all_spy": all(t.startswith("O:SPY") or t == "SPY" for t in df["ticker"].unique().to_list()),
    }
    
    # Check file size is reasonable
    file_size_mb = os.path.getsize(parquet_path) / (1024 * 1024)
    checks["file_size_mb"] = round(file_size_mb, 2)
    
    if checks["row_count"] == 0:
        checks["status"] = "EMPTY"
    elif not checks["all_spy"]:
        checks["status"] = "FILTER_LEAK"
    else:
        checks["status"] = "OK"
    
    return checks
```

---

## 11. Subscription Plan Requirements

Options Flat Files access depends on the Massive subscription tier:

| Dataset | Minimum Plan | Notes |
|---|---|---|
| Options Trades | Options Developer+ | End-of-day access |
| Options Quotes | Options Advanced+ | Very large files; all history |
| Options Minute Aggs | Options Starter+ | Check plan for history depth |
| Options Day Aggs | Options Starter+ | Check plan for history depth |
| Stocks Trades | Stocks Starter+ | |
| Stocks Minute Aggs | Stocks Starter+ | |
| Indices Day Aggs | Indices plan required | Separate subscription |
| Indices Minute Aggs | Indices plan required | Separate subscription |

> Verify your specific plan's data recency and history depth in the Massive Dashboard before building download ranges.

---

## 12. Error Handling & Resilience

The agent must implement:

1. **Retry with backoff** on transient S3 errors (network timeouts, 503s)
2. **Skip weekends and holidays** — don't log failures for non-trading days
3. **Checksum verification** — compare downloaded file size against S3 `Content-Length`
4. **Partial download recovery** — if a download is interrupted, delete the partial file and retry
5. **Disk space checks** — before downloading, verify sufficient free space (Options Quotes can be 100+ GB/day)
6. **Download log** — maintain `download_log.json` with status per file to enable resume after interruption

```python
import json
from datetime import datetime

LOG_PATH = "data/massive/download_log.json"

def log_download(s3_key: str, local_path: str, status: str, rows: int = 0):
    """Append to the download log."""
    log = []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            log = json.load(f)
    
    log.append({
        "s3_key": s3_key,
        "local_path": local_path,
        "status": status,
        "rows_after_filter": rows,
        "timestamp": datetime.now().isoformat(),
    })
    
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)
```

---

## 13. Performance Notes

- **Download speed:** S3 downloads have no rate limits, but bandwidth depends on your connection. Expect 50-200 MB/s on a good connection.
- **Polars vs Pandas:** Use **Polars** for all CSV reading and filtering. It is 5-10x faster than Pandas on large files and uses less memory.
- **Parquet compression:** Use `zstd` compression for the best balance of size and read speed.
- **Disk usage estimate:** After filtering for SPY only, expect roughly:
  - Options Day Aggs: ~5-20 MB/day → ~1-5 GB/year
  - Options Minute Aggs: ~50-200 MB/day → ~12-50 GB/year
  - Options Trades (SPY only): ~200 MB - 2 GB/day → ~50-500 GB/year
  - Underlying (SPY stock): ~1-5 MB/day
  - Indices: ~1-5 MB/day

---

## 14. Summary: Agent Task Checklist

1. **[ ] Create `.env`** with `MASSIVE_S3_ACCESS_KEY` and `MASSIVE_S3_SECRET_KEY` placeholders
2. **[ ] Install dependencies** (`boto3`, `polars`, `pyarrow`, `python-dotenv`, `exchange-calendars`)
3. **[ ] Create directory structure** under `Spyder/data/massive/`
4. **[ ] Implement `downloader.py`** with S3 client, date-range download, file listing
5. **[ ] Implement `converter.py`** with SPY filtering and Parquet conversion (standard + chunked)
6. **[ ] Implement `pipeline.py`** orchestrating download → convert → validate → log
7. **[ ] Implement `utils.py`** with OPRA ticker parser, timestamp conversion, trading calendar
8. **[ ] Implement `scheduler.py`** for daily cron-based updates
9. **[ ] Test with 1 day** of Options Day Aggs (smallest dataset)
10. **[ ] Expand** to full backfill of desired date range
11. **[ ] Add CLI interface** (`argparse`) for `--mode backfill --start 2024-01-01 --end 2024-12-31`
12. **[ ] Integrate** Parquet reader into `SpyderC_MarketData` for the backtesting engine

---

## 15. Project-Wide Documentation Update Required

The Spyder project has migrated from **Interactive Brokers to Tradier** as its broker. The following project documents and modules contain stale IB references that need updating:

| Area | What Needs Changing |
|---|---|
| **Project Overview / README** | Replace "Interactive Brokers" references with "Tradier" throughout; update Technology Stack section |
| **SpyderB_Broker** | Module description says "All broker interactions isolated to one module" — verify the implementation targets Tradier's API, not IB's TWS/Gateway |
| **System Architecture** | References to "Direct market access and execution" via IB API need updating to reflect Tradier's REST/streaming API model |
| **SpyderC_MarketData** | If any real-time data feeds are sourced from IB, these need rerouting to Tradier or Massive WebSocket |
| **Order Management** | IB-specific concepts (e.g., TWS smart routing, partial fills handling via IB API) should be reviewed against Tradier's order API |
| **Market Internals** | Any code referencing IB pseudo-tickers ($TICK, $TRIN) for real-time internals needs replacement — either compute from SIP data or remove |

> **Action for coding agent:** When working on any Spyder module, flag and correct any remaining IB references. The broker is **Tradier** — all execution, account management, and real-time market data for live trading flows through the Tradier API.
