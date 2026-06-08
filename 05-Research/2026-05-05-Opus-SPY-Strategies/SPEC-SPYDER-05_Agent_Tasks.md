# SPEC-TRADOV-05 — Coding Agent Task Tickets

| Field | Value |
|---|---|
| Spec ID | SPEC-TRADOV-05 |
| Purpose | Atomic, agent-executable tickets to implement SPEC-TRADOV-01 through 04 |
| Format | Each ticket is self-contained: branch name, files, acceptance test, time estimate |
| Convention | Ticket IDs use Tradov lettered series: D=Data, B=Broker, Q=Quant, S=Strategy, T=Tests |

---

## How To Use This Spec

Each ticket below is sized to be a **single agent run** of 30–90 minutes. Tickets are ordered so each one's dependencies are already complete. The agent should:

1. Read the linked SPEC section.
2. Create the branch.
3. Implement the listed files.
4. Run the listed acceptance test.
5. Open a PR with the listed PR description template filled in.
6. Stop and wait for human review before proceeding to the next ticket.

Tickets marked **GATE** must be human-approved before subsequent tickets begin.

---

## Phase 0 — Repo Setup (1 ticket)

### TICKET S00 — Initialize Tradov Repo Structure

| Field | Value |
|---|---|
| Branch | `init/repo-skeleton` |
| Time estimate | 30 min |
| Depends on | none |

**Files to create:**

```
tradov/
├── pyproject.toml
├── README.md
├── .gitignore
├── .env.example
├── ruff.toml
├── pytest.ini
├── src/tradov/__init__.py
├── src/tradov/types/__init__.py
├── src/tradov/quant/__init__.py
├── src/tradov/quant/greeks/__init__.py
├── src/tradov/broker/__init__.py
├── src/tradov/broker/tradier/__init__.py
├── src/tradov/strategies/__init__.py
├── src/tradov/backtest/__init__.py
├── src/tradov/live/__init__.py
├── src/tradov/cli/__init__.py
├── tests/__init__.py
├── tests/quant/
├── tests/broker/
├── tests/strategies/
├── tests/backtest/
└── tests/integration/
```

**`pyproject.toml` essentials:**

```toml
[project]
name = "tradov"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26",
    "scipy>=1.11",
    "pandas>=2.1",
    "httpx>=0.27",
    "websockets>=12",
    "pydantic>=2.5",
    "tenacity>=8.2",
    "tomli>=2.0; python_version < '3.11'",
]

[project.optional-dependencies]
backtest = ["vectorbt>=0.26", "backtrader>=1.9.78", "pyarrow>=14"]
fast = ["py_lets_be_rational>=1.0.1", "numba>=0.59"]
dev = ["pytest>=7.4", "pytest-asyncio>=0.23", "pytest-cov>=4.1", "ruff>=0.3", "mypy>=1.8"]
```

**Acceptance:** `pip install -e ".[dev]"` succeeds; `pytest -q` runs and reports zero tests; `ruff check src tests` passes.

**PR description template:**
```
Initial repo skeleton per SPEC-TRADOV-05 ticket S00.
- Layout follows lettered-module convention (Q=Quant, B=Broker, S=Strategy)
- Python 3.11+ minimum
- No code yet — only structure and tooling config
```

---

## Phase 1 — Greeks Engine (4 tickets)

### TICKET Q01 — Black-Scholes Pricing & Greeks (Scalar)

| Field | Value |
|---|---|
| Branch | `quant/q01-bs-scalar` |
| Time estimate | 60 min |
| Depends on | S00 |
| Spec section | SPEC-TRADOV-04 §2, §3, §4 |

**Files:**
- `src/tradov/quant/greeks/black_scholes.py`
- `src/tradov/quant/greeks/types.py`  (the `Greeks` dataclass and `OptionType`)
- `tests/quant/test_black_scholes.py`

**Implement:**
- `_norm_cdf`, `_norm_pdf` (using `scipy.special.erf`, not `scipy.stats.norm`)
- `black_scholes_price(spot, strike, t_years, rate, dividend_yield, sigma, option_type) -> float`
- `black_scholes_greeks(...) -> Greeks`
- `implied_volatility(...) -> float` using `scipy.optimize.brentq`

**Acceptance test (`test_black_scholes.py`):**
- Put-call parity holds to 1e-10 over 100 random parameter combos
- Haug textbook reference: `C(S=60, K=65, T=0.25, r=0.08, q=0, σ=0.30) == 2.1334...` (assert to 1e-4)
- ATM delta ≈ 0.5 for `r=q=0`
- IV round-trip: `invert(price(σ=0.20)) == 0.20` to 1e-6
- 0DTE handling: `t_years = 60/(365*86400)` returns finite greeks (no NaN, no inf)

---

### TICKET Q02 — Vectorized Black-Scholes

| Field | Value |
|---|---|
| Branch | `quant/q02-bs-vectorized` |
| Time estimate | 45 min |
| Depends on | Q01 |
| Spec section | SPEC-TRADOV-04 §3 (vectorized API), §9 (perf budget) |

**Files:**
- `src/tradov/quant/greeks/black_scholes_vec.py`
- `tests/quant/test_black_scholes_vec.py`
- `tests/quant/test_perf_budget.py`

**Implement:**
- `black_scholes_price_vec(spot, strike, t_years, rate, q, sigma, option_type) -> np.ndarray`
- `black_scholes_greeks_vec(...) -> dict[str, np.ndarray]`

**Acceptance:**
- Parity test: vectorized over 1000 random inputs matches scalar to 1e-12
- Perf test: 500-strike chain greeks compute in < 200 µs on the dev box (warn-only, don't fail CI)

---

### TICKET Q03 — IV Rank & Realized Vol

| Field | Value |
|---|---|
| Branch | `quant/q03-iv-rank` |
| Time estimate | 45 min |
| Depends on | Q01 |
| Spec section | SPEC-TRADOV-04 §5 |

**Files:**
- `src/tradov/quant/greeks/iv_metrics.py`
- `src/tradov/quant/greeks/iv_cache.py`  (SQLite cache per §5.3)
- `tests/quant/test_iv_metrics.py`

**Implement:**
- `realized_volatility(closes: np.ndarray, window: int = 20) -> float`
- `iv_rank(today_iv: float, history: np.ndarray) -> float`
- `iv_percentile(today_iv: float, history: np.ndarray) -> float`
- `constant_maturity_atm_iv(chain_today, target_dte=30) -> float`
- `IvCache` class with the schema from SPEC-04 §5.3

**Acceptance:**
- Synthetic IV series with known min/max gives correct rank
- IV percentile of the median value is ~50

---

### TICKET Q04 — Portfolio Greeks & Tradier Validation **GATE**

| Field | Value |
|---|---|
| Branch | `quant/q04-portfolio-greeks` |
| Time estimate | 45 min |
| Depends on | Q02 |
| Spec section | SPEC-TRADOV-04 §6, §7 |

**Files:**
- `src/tradov/quant/greeks/portfolio.py`
- `tests/quant/test_portfolio_greeks.py`

**Implement:**
- `portfolio_greeks(legs: list[PositionLeg]) -> Greeks`
- `validate_tradier_greeks(...) -> ValidationReport`

**Acceptance:**
- Iron condor greeks have correct signs (delta near 0, gamma < 0, theta > 0, vega < 0) on synthetic ATM 16-delta condor
- Validation report flags > 5% mismatches

🛑 **GATE Q04**: Human reviews the Greeks engine before broker work begins. Confirm sign conventions, test coverage, and that `Greeks` dataclass matches what the broker layer will produce.

---

## Phase 2 — Tradier Broker (5 tickets)

### TICKET B01 — Config, Auth, OCC Symbol

| Field | Value |
|---|---|
| Branch | `broker/b01-config-occ` |
| Time estimate | 45 min |
| Depends on | S00 |
| Spec section | SPEC-TRADOV-03 §3, §5 |

**Files:**
- `src/tradov/broker/tradier/config.py`
- `src/tradov/broker/tradier/occ.py`
- `tests/broker/test_config.py`
- `tests/broker/test_occ.py`

**Implement:**
- `TradierEnv`, `TradierConfig`, secrets loader from `~/.tradov/secrets.toml`
- `OccSymbol` with `parse` and `encode`
- Production-safe guards (env var check, file path check)

**Acceptance:**
- 1000-iteration round-trip: `OccSymbol.parse(s.encode()) == s`
- Production config without `TRADOV_PROD_CONFIRMED=1` raises
- Token never appears in `repr(config)`

---

### TICKET B02 — REST Client Foundation

| Field | Value |
|---|---|
| Branch | `broker/b02-rest-foundation` |
| Time estimate | 60 min |
| Depends on | B01 |
| Spec section | SPEC-TRADOV-03 §4, §9, §10 |

**Files:**
- `src/tradov/broker/tradier/rest.py`           (httpx-based client)
- `src/tradov/broker/tradier/rate_limiter.py`
- `src/tradov/broker/tradier/errors.py`
- `tests/broker/test_rate_limiter.py`
- `tests/broker/test_retry.py`

**Implement:**
- `TradierRestClient` with auth headers, base URL switching
- Token bucket rate limiter
- Retry with exponential backoff + full jitter
- Error class hierarchy (`TradierError` and subclasses), `is_retryable`

**Acceptance:**
- Rate limiter holds at configured rate under 100-call burst
- Retry sequence: 429 → 429 → 200 succeeds; 401 raises immediately

---

### TICKET B03 — Market Data Endpoints

| Field | Value |
|---|---|
| Branch | `broker/b03-market-data` |
| Time estimate | 60 min |
| Depends on | B02, Q01 |
| Spec section | SPEC-TRADOV-03 §6 |

**Files:**
- `src/tradov/broker/tradier/market_data.py`
- `src/tradov/broker/tradier/models.py`        (Pydantic models for chain, quote, etc.)
- `tests/broker/test_market_data_sandbox.py`   (network test, marked `@pytest.mark.sandbox`)

**Implement:**
- `MarketDataClient.get_chain(underlying, expiration) -> OptionChain`
- `MarketDataClient.get_expirations(underlying) -> list[date]`
- `MarketDataClient.get_zero_dte_expiration(underlying) -> date | None`
- `MarketDataClient.get_quotes(symbols: list[str]) -> list[Quote]`
- `MarketDataClient.get_clock() -> MarketClock`

**Acceptance (sandbox):**
- `get_chain("SPY", next_friday)` returns ≥ 50 strikes with non-null greeks
- `get_zero_dte_expiration("SPY")` returns today's date when run during a 0DTE-listing trading day, else None
- `get_clock()` returns `state="open"` during RTH

---

### TICKET B04 — Trading Endpoints (Multileg)

| Field | Value |
|---|---|
| Branch | `broker/b04-trading-multileg` |
| Time estimate | 90 min |
| Depends on | B03 |
| Spec section | SPEC-TRADOV-03 §7 |

**Files:**
- `src/tradov/broker/tradier/trading.py`
- `src/tradov/broker/tradier/protocol.py`     (the `BrokerProtocol`)
- `tests/broker/test_multileg_payload.py`
- `tests/broker/test_trading_sandbox.py`

**Implement:**
- `TradingClient.get_balances()`, `.get_positions()`, `.get_orders()`
- `TradingClient.place_iron_condor(legs, qty, limit_credit, preview=True) -> OrderResponse`
- `TradingClient.close_iron_condor(order_id, limit_debit) -> OrderResponse`
- `TradingClient.cancel_order(order_id)`
- `BrokerProtocol` (matches simulator's interface)

**Acceptance (sandbox):**
- Place 1-contract preview iron condor on SPY → preview returns ok=true
- Place 1-contract live iron condor on SPY → fills (sandbox auto-fills) → close fills → reconcile shows zero open
- Multileg payload byte-equality to canonical Tradier example (regression test)

---

### TICKET B05 — Streaming, Audit DB, Reconciliation **GATE**

| Field | Value |
|---|---|
| Branch | `broker/b05-streaming-audit` |
| Time estimate | 75 min |
| Depends on | B04 |
| Spec section | SPEC-TRADOV-03 §6.3, §11, §12 |

**Files:**
- `src/tradov/broker/tradier/streaming.py`
- `src/tradov/broker/tradier/audit.py`
- `src/tradov/broker/tradier/reconcile.py`
- `tests/broker/test_streaming_sandbox.py`
- `tests/broker/test_audit.py`
- `tests/broker/test_reconcile.py`

**Implement:**
- `StreamingClient` for market and account events (websockets)
- Async audit DB writer (queue + background task)
- Token redaction in audit
- `reconcile()` returning `ReconciliationReport`

**Acceptance:**
- Stream 4 SPY OCC symbols for 30s → ≥10 quote updates received
- Audit DB enqueue p99 latency < 1ms
- No token in any audit row (regex check)
- Reconcile correctly identifies a seeded discrepancy

🛑 **GATE B05**: Human reviews the broker layer end-to-end. Run a full open→close iron condor in sandbox manually, verify audit DB has all calls, verify reconcile is clean.

---

## Phase 3 — Backtest Foundation (4 tickets)

### TICKET D01 — Historical Data Loaders

| Field | Value |
|---|---|
| Branch | `data/d01-loaders` |
| Time estimate | 75 min |
| Depends on | S00 |
| Spec section | SPEC-TRADOV-02 §5 |

**Files:**
- `src/tradov/backtest/data/chain_loader.py`
- `src/tradov/backtest/data/vix_loader.py`
- `src/tradov/backtest/data/calendar.py`
- `tests/backtest/test_loaders.py`

**Implement:**
- Parquet writers and readers for the schema in SPEC-02 §5.2
- `ChainDataSource.from_local_parquet(path)`
- `VixDataSource` (daily series)
- `EconomicCalendar` with FOMC/CPI/NFP loading from CSVs (seed with 2022–2026 dates committed to repo)

**Acceptance:**
- Round-trip 1 day's worth of synthetic chain data through Parquet without loss
- Calendar correctly identifies known FOMC dates from 2024–2026

---

### TICKET D02 — Sim Clock, Sim Context, Sim Broker

| Field | Value |
|---|---|
| Branch | `backtest/d02-sim-context` |
| Time estimate | 90 min |
| Depends on | D01, B04 |
| Spec section | SPEC-TRADOV-02 §4 |

**Files:**
- `src/tradov/backtest/clock.py`
- `src/tradov/backtest/sim_context.py`
- `src/tradov/backtest/broker_sim.py`
- `src/tradov/backtest/slippage.py`
- `src/tradov/backtest/commissions.py`
- `tests/backtest/test_broker_sim.py`

**Implement:**
- `SimClock` (settable now, monotonic advance)
- `SimContext` implementing the `Context` protocol
- `SimulatedBroker` implementing `BrokerProtocol` (same interface as `TradingClient`)
- Slippage models per SPEC-02 §6
- Commission models per SPEC-02 §7

**Acceptance:**
- Place a simulated iron condor → fills at correct slippage-adjusted price
- Commissions applied per leg correctly
- `SimulatedBroker` and `TradingClient` are interchangeable behind `BrokerProtocol` (mypy check)

---

### TICKET D03 — Backtest Engine & Result Object

| Field | Value |
|---|---|
| Branch | `backtest/d03-engine` |
| Time estimate | 90 min |
| Depends on | D02 |
| Spec section | SPEC-TRADOV-02 §4, §8, §11 |

**Files:**
- `src/tradov/backtest/engine.py`
- `src/tradov/backtest/result.py`
- `src/tradov/backtest/analyzers/equity_curve.py`
- `src/tradov/backtest/analyzers/drawdown.py`
- `src/tradov/backtest/analyzers/trade_log.py`
- `tests/backtest/test_engine.py`
- `tests/backtest/test_metrics.py`

**Implement:**
- `BacktestEngine` event loop
- `BacktestResult` with all metrics from SPEC-02 §8
- Reproducibility metadata (seed, data hash, git SHA)

**Acceptance:**
- Engine runs an empty strategy over a synthetic 1-month chain in < 1s
- Sharpe matches textbook example to 1e-4
- Max drawdown matches textbook example exactly

---

### TICKET D04 — HTML & PDF Report Generators **GATE**

| Field | Value |
|---|---|
| Branch | `backtest/d04-reports` |
| Time estimate | 75 min |
| Depends on | D03 |
| Spec section | SPEC-TRADOV-02 §9 |

**Files:**
- `src/tradov/backtest/reports/html_report.py`
- `src/tradov/backtest/reports/pdf_report.py`
- `tests/backtest/test_reports.py`

**Implement:**
- HTML report with embedded Plotly equity curve, monthly heatmap, drawdown chart
- PDF report using ReportLab (matches the Tradov investor PDF toolkit)

**Acceptance:**
- Both reports generate from a fixture `BacktestResult` without error
- HTML opens correctly in Firefox; PDF opens correctly in Evince

🛑 **GATE D04**: Human reviews a generated report end-to-end on a fixture run. Confirm visual fidelity and metric correctness.

---

## Phase 4 — The Strategy (4 tickets)

### TICKET S01 — CondorConfig & Strike Selection

| Field | Value |
|---|---|
| Branch | `strategy/s01-config-strikes` |
| Time estimate | 60 min |
| Depends on | Q04, B04, D03 |
| Spec section | SPEC-TRADOV-01 §3, §6 |

**Files:**
- `src/tradov/strategies/condor_0dte/config.py`
- `src/tradov/strategies/condor_0dte/strikes.py`
- `tests/strategies/test_strike_selection.py`

**Acceptance:** all unit tests in SPEC-01 §13.1 for strike selection pass.

---

### TICKET S02 — Entry Gates & Position Sizing

| Field | Value |
|---|---|
| Branch | `strategy/s02-gates-sizing` |
| Time estimate | 60 min |
| Depends on | S01 |
| Spec section | SPEC-TRADOV-01 §5, §7 |

**Files:**
- `src/tradov/strategies/condor_0dte/gates.py`
- `src/tradov/strategies/condor_0dte/sizing.py`
- `tests/strategies/test_gates.py`
- `tests/strategies/test_sizing.py`

**Acceptance:** all unit tests in SPEC-01 §13.1 for gates and sizing pass.

---

### TICKET S03 — State Machine & Position Manager

| Field | Value |
|---|---|
| Branch | `strategy/s03-state-machine` |
| Time estimate | 90 min |
| Depends on | S02 |
| Spec section | SPEC-TRADOV-01 §4, §8, §11 |

**Files:**
- `src/tradov/strategies/condor_0dte/states.py`
- `src/tradov/strategies/condor_0dte/strategy.py`     (the `CondorStrategy` orchestrator)
- `src/tradov/strategies/condor_0dte/persistence.py`  (SQLite per SPEC-01 §10)
- `tests/strategies/test_state_machine.py`
- `tests/strategies/test_full_lifecycle.py`

**Acceptance:**
- State machine forbids invalid transitions
- Full lifecycle test (using `SimulatedBroker`) goes IDLE → ... → CLOSED
- Failure injection: simulated network drop during ACTIVE → recovers via reconcile

---

### TICKET S04 — Backtest Validation Run **GATE**

| Field | Value |
|---|---|
| Branch | `strategy/s04-backtest-validation` |
| Time estimate | 60 min (compute time variable) |
| Depends on | S03, D04 |
| Spec section | SPEC-TRADOV-01 §14, SPEC-TRADOV-02 §10 |

**Files:**
- `scripts/run_condor_validation.py`
- `reports/condor_0dte_validation.html` (output, not committed)
- `reports/condor_0dte_validation.pdf` (output, not committed)

**Run:**
- 2-year backtest of `CondorStrategy` with default `CondorConfig` over real chain data
- Walk-forward: 12-month in-sample, 3-month out-of-sample, 3-month step

**Acceptance gate:**
- [ ] Backtest expectancy is positive
- [ ] Max drawdown < 20% of NAV
- [ ] Sharpe ≥ 1.0
- [ ] Out-of-sample Sharpe ≥ 0.7 × in-sample Sharpe across all walk-forward windows
- [ ] HTML and PDF reports generated

🛑 **GATE S04**: Human reviews the backtest report. **No live trading until this gate passes.** If it fails, return to S01–S03 for parameter or logic adjustments.

---

## Phase 5 — Live Wiring (3 tickets)

### TICKET L01 — Live Context & Live Calendar Service

| Field | Value |
|---|---|
| Branch | `live/l01-live-context` |
| Time estimate | 60 min |
| Depends on | B05 |
| Spec section | SPEC-TRADOV-02 §4.1 (Context protocol) |

**Files:**
- `src/tradov/live/context.py`
- `src/tradov/live/economic_calendar.py`  (FRED + ICS feeds)
- `tests/live/test_live_context.py`

**Acceptance:** `LiveContext` is interchangeable with `SimContext` behind the `Context` protocol; mypy in strict mode passes.

---

### TICKET L02 — CLI Runner & Kill Switch

| Field | Value |
|---|---|
| Branch | `live/l02-cli-runner` |
| Time estimate | 75 min |
| Depends on | L01, S03 |
| Spec section | SPEC-TRADOV-01 §14 (kill switch) |

**Files:**
- `src/tradov/cli/run_condor.py`
- `src/tradov/live/kill_switch.py`
- `systemd/tradov-condor.service`             (unit file for Ubuntu)
- `tests/live/test_kill_switch.py`

**Implement:**
- `python -m tradov.cli.run_condor --env=sandbox --config=path/to.toml`
- Kill switch via `~/.tradov/HALT` sentinel file (checked every tick)
- Graceful shutdown on SIGINT/SIGTERM that closes positions before exit

**Acceptance:**
- Touching `~/.tradov/HALT` halts new entries within one tick
- SIGTERM during ACTIVE state triggers controlled close, not abrupt exit

---

### TICKET L03 — Sandbox Soak Test (5 trading days) **GATE**

| Field | Value |
|---|---|
| Branch | `live/l03-soak-test` |
| Time estimate | 5 trading days elapsed |
| Depends on | L02 |
| Spec section | SPEC-TRADOV-01 §14 |

**Run:**
- `tradov-condor.service` running against Tradier sandbox for 5 consecutive trading days
- Monitor logs, audit DB, reconciliation reports daily

**Acceptance gate:**
- [ ] No FAULTED states across all 5 days
- [ ] All open→close lifecycles completed without manual intervention
- [ ] Audit DB grows correctly; no token leaks
- [ ] Reconciliation clean every morning at startup
- [ ] Daily P/L matches the persisted `condor_trades` table to the cent

🛑 **GATE L03**: Human reviews 5-day sandbox results. Decide on production deployment.

---

## Phase 6 — Production Deployment (out of scope for the first build)

The production cutover is deliberately **not** an agent-executable ticket. It requires:

1. Live broker account with options approval at the appropriate level.
2. A regulatory and tax review by a human (not Claude — see standard disclaimer).
3. Initial capital allocation decision.
4. A graduated position-size ramp (1 contract → 2 → 5 → standard) over multiple weeks.
5. Daily review by the operator for the first month.

---

## Summary Diagram — Ticket Dependency Graph

```
S00
 ├──► Q01 ─► Q02 ─► Q04 ──╮
 │     └──► Q03           │
 │                        │
 ├──► B01 ─► B02 ─► B03 ─►├──► B04 ─► B05 ──╮
 │                        │                  │
 └──► D01 ─► D02 ─► D03 ─►│                  │
                          │                  │
                          ▼                  │
                         S01 ─► S02 ─► S03 ──┤
                                              │
                                       D04 ──►│
                                              ▼
                                             S04 ──╮
                                                    │
                                              L01 ──┤
                                                    ▼
                                              L02 ──► L03 ──► (production)
```

GATEs (🛑): Q04, B05, D04, S04, L03.

Total estimate: roughly **18–22 hours** of agent work, plus 5 trading days of soak time before production. Each agent run produces a single PR; humans review each gate before downstream tickets begin.
