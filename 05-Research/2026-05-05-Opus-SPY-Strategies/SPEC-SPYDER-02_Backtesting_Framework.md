# SPEC-SPYDER-02 — Backtesting Framework Module

| Field | Value |
|---|---|
| Spec ID | SPEC-SPYDER-02 |
| Module | `spyder/backtest/` (package) |
| Version | 1.0.0 |
| Status | Ready for implementation |
| Depends on | SPEC-SPYDER-04 (Greeks for synthetic chain pricing) |
| Target | Reproducible, slippage-aware backtesting of all Spyder strategies |

---

## 1. Purpose

A purpose-built event-driven backtester for SPY options strategies that:
1. Replays historical options chain data tick-by-tick (or minute bar) with correct expiration semantics.
2. Models bid/ask spreads, commissions, and slippage realistically.
3. Reuses the **same strategy code** that runs live (no duplicate logic).
4. Produces standardized performance reports compatible with the Captova naming and persistence conventions.

The framework wraps `vectorbt` for vectorized lightweight tests and `backtrader` for full event-driven simulation; the abstraction is in our own `BacktestEngine` so strategies don't import either directly.

---

## 2. Why Both Engines

| Engine | Use Case | Strengths | Limits |
|---|---|---|---|
| `vectorbt` | Daily-bar signal research, volatility regime studies, parameter sweeps over thousands of configs | Fast, NumPy-native, great for sweeps | Awkward for multi-leg options, no realistic order book |
| `backtrader` | Full event-driven simulation of multi-leg strategies, intraday tick replay, broker emulation | Faithful to live execution, supports custom analyzers | Slower, single-threaded |
| Custom `BacktestEngine` | Production reference — used to gate live deployment | Reuses live strategy code unchanged, integrates Tradier-shaped data | More code to maintain |

The custom engine is the gatekeeper for live deployment. `vectorbt` and `backtrader` are research tools.

---

## 3. Architecture

```
spyder/backtest/
├── __init__.py
├── engine.py            # BacktestEngine — main event loop
├── clock.py             # SimClock; replaces real wall clock
├── data/
│   ├── chain_loader.py  # Load historical options chains
│   ├── vix_loader.py    # Load historical VIX
│   └── calendar.py      # Historical FOMC/CPI/NFP dates
├── broker_sim.py        # Simulated Tradier (same interface as live)
├── slippage.py          # Slippage models
├── commissions.py       # Commission models
├── analyzers/
│   ├── trade_log.py     # Per-trade record
│   ├── equity_curve.py  # NAV over time
│   ├── drawdown.py      # Max DD, recovery
│   └── greeks_attrib.py # P/L attribution by greek
├── reports/
│   ├── html_report.py   # Standalone HTML with embedded charts
│   └── pdf_report.py    # ReportLab-based PDF (same toolkit as Spyder investor PDF)
└── adapters/
    ├── vectorbt_adapter.py  # For research sweeps
    └── backtrader_adapter.py
```

---

## 4. Core Abstractions

### 4.1 The `Context` Protocol

Strategies depend on a `Context` interface, never on concrete broker or clock. Both live and backtest contexts implement it.

```python
from typing import Protocol

class Context(Protocol):
    clock:    "ClockProtocol"
    market:   "MarketDataProtocol"
    calendar: "CalendarProtocol"
    broker:   "BrokerProtocol"
    portfolio:"PortfolioProtocol"
    log:      "LogProtocol"
```

`live.LiveContext` injects: real `datetime.now`, Tradier REST client, FRED economic calendar.
`backtest.SimContext` injects: `SimClock`, `HistoricalChainLoader`, `SimulatedBroker`.

The strategy module imports neither — it only knows `Context`.

### 4.2 The Event Loop

```python
class BacktestEngine:
    def __init__(
        self,
        start_date: date,
        end_date: date,
        bar_resolution: BarResolution,         # MINUTE | FIVE_SEC | DAILY
        chain_source: ChainDataSource,
        slippage:     SlippageModel,
        commissions:  CommissionModel,
        starting_nav: float,
    ): ...

    def register_strategy(self, factory: Callable[[Context], Strategy]) -> None: ...

    def run(self) -> BacktestResult:
        ctx = SimContext(...)
        strategies = [f(ctx) for f in self._factories]

        for tick in self._tick_iterator():
            ctx.clock.set(tick.timestamp)
            ctx.market.advance_to(tick)
            for strat in strategies:
                strat.on_tick(tick)
            ctx.broker.process_pending_orders(tick)

        return self._build_result()
```

---

## 5. Data Sources

### 5.1 Historical Options Chains

| Source | Coverage | Cost | Notes |
|---|---|---|---|
| CBOE DataShop | Full chains, all strikes, every minute since 2004 | Paid | Gold standard |
| OptionMetrics IvyDB | Daily snapshots, computed greeks | Academic license | Used in most published research |
| Polygon.io options | Trades, quotes, second-resolution | Subscription | Reasonable for last few years |
| ORATS Data API | Daily snapshots with surface fits | Subscription | Tradier uses ORATS for live greeks (matches production) |
| Tradier historical chains | Limited lookback via `/markets/history` per OCC symbol | Included with brokerage | Free but you must enumerate symbols yourself |

**Recommendation:** ORATS for parity with the Tradier live data path; CBOE DataShop if budget allows for tick-level 0DTE realism.

### 5.2 Schema (canonical Parquet layout)

Store on local SSD per Captova local-first principle:

```
~/spyder-data/
├── chains/
│   └── SPY/
│       └── year=2025/
│           └── month=11/
│               └── day=03.parquet     # one file per trading day
├── vix/
│   └── vix_daily.parquet
└── calendar/
    ├── fomc.parquet
    ├── cpi.parquet
    └── nfp.parquet
```

`chains/SPY/year=YYYY/month=MM/day=DD.parquet` columns:

| Column | Type | Notes |
|---|---|---|
| `timestamp_utc` | int64 (epoch ms) | Quote timestamp |
| `occ_symbol` | str | OCC option symbol |
| `expiration` | date | |
| `strike` | float | |
| `option_type` | enum: C, P | |
| `bid` | float | |
| `ask` | float | |
| `mid` | float | |
| `last` | float | |
| `volume` | int | |
| `open_interest` | int | |
| `delta` | float | |
| `gamma` | float | |
| `theta` | float | |
| `vega` | float | |
| `iv` | float | |
| `underlying_price` | float | SPY spot at this timestamp |

Loaders compress to Parquet with Snappy and partition by date for fast range scans.

---

## 6. Slippage Models

```python
from abc import ABC, abstractmethod

class SlippageModel(ABC):
    @abstractmethod
    def apply(self, leg: OrderLeg, quote: Quote) -> float:
        """Returns the actual fill price for one leg."""

class MidPlusFixedSlippage(SlippageModel):
    """Mid price ± fixed dollar amount per contract. Simplest model."""
    def __init__(self, fixed_dollars: float = 0.02): ...

class HalfSpreadSlippage(SlippageModel):
    """Pay half the bid-ask spread. Most realistic for liquid SPY options."""

class WidenedHalfSpreadSlippage(SlippageModel):
    """Pay half the spread × widening factor. Models stress periods."""
    def __init__(self, widen_factor: float = 1.5): ...

class VolumeAwareSlippage(SlippageModel):
    """Slippage scales with order_size / observed_volume."""
```

**Default for production gating:** `WidenedHalfSpreadSlippage(widen_factor=1.5)` — pessimistic enough that strategies passing the gate have realistic edge.

---

## 7. Commission Models

```python
class CommissionModel(ABC):
    @abstractmethod
    def per_leg(self, qty: int) -> float: ...

class TradierStandard(CommissionModel):
    """As of 2026: $0.35 per contract for options, $0 base."""
    def per_leg(self, qty: int) -> float:
        return 0.35 * qty

class TradierProRated(CommissionModel):
    """Pro plan: $0.10 per contract."""
    def per_leg(self, qty: int) -> float:
        return 0.10 * qty
```

A four-leg iron condor at 5 contracts on the standard plan costs `4 × 5 × $0.35 = $7.00` to open and another $7 to close — material for thin 0DTE credits.

---

## 8. Performance Metrics

The `BacktestResult` exposes these computed metrics (every metric is a method, never a property — explicit cost).

| Metric | Definition |
|---|---|
| `total_return_pct()` | `(final_nav - starting_nav) / starting_nav` |
| `cagr()` | Compounded annual growth rate |
| `sharpe_ratio(rf=0.045)` | `(mean_excess_return / std_excess_return) * sqrt(252)` |
| `sortino_ratio(rf=0.045)` | Sharpe variant using downside deviation |
| `max_drawdown_pct()` | Peak-to-trough NAV drop |
| `max_drawdown_duration()` | Calendar days from peak to recovery |
| `win_rate()` | Wins / total trades |
| `expectancy()` | `(win_rate * avg_win) - (loss_rate * avg_loss)` |
| `profit_factor()` | `gross_profit / gross_loss` |
| `avg_win()`, `avg_loss()` | Mean P/L of winning vs losing trades |
| `trades_per_year()` | Trade frequency |
| `kelly_fraction()` | Optimal fraction of capital per trade |
| `var_95()`, `var_99()` | Value at risk over rolling windows |
| `cvar_95()` | Expected shortfall beyond VaR |
| `tail_ratio()` | `abs(p95_return / p5_return)` |

---

## 9. Reference Run (for SPEC-SPYDER-01 validation)

```python
from spyder.backtest import BacktestEngine, ChainDataSource
from spyder.backtest.slippage import WidenedHalfSpreadSlippage
from spyder.backtest.commissions import TradierStandard
from spyder.strategies.condor_0dte import CondorStrategy, CondorConfig
from datetime import date

engine = BacktestEngine(
    start_date    = date(2024, 1, 2),
    end_date      = date(2026, 5, 5),
    bar_resolution= BarResolution.MINUTE,
    chain_source  = ChainDataSource.from_local_parquet("~/spyder-data/chains/SPY"),
    slippage      = WidenedHalfSpreadSlippage(widen_factor=1.5),
    commissions   = TradierStandard(),
    starting_nav  = 50_000.0,
)

cfg = CondorConfig()  # defaults
engine.register_strategy(lambda ctx: CondorStrategy(ctx, cfg))

result = engine.run()

result.print_summary()
result.write_html_report("~/spyder-reports/condor_0dte_2024-2026.html")
result.write_pdf_report("~/spyder-reports/condor_0dte_2024-2026.pdf")
result.write_trade_log_csv("~/spyder-reports/condor_0dte_2024-2026_trades.csv")
```

---

## 10. Walk-Forward Validation

Pure backtests overfit. The framework supports walk-forward analysis natively:

```python
from spyder.backtest import WalkForwardRunner

wf = WalkForwardRunner(
    in_sample_months  = 12,
    out_sample_months = 3,
    step_months       = 3,
    optimization_objective = "sortino_ratio",
    parameter_grid = {
        "short_strike_delta":   [0.08, 0.10, 0.12, 0.15],
        "spread_width_dollars": [3.0, 5.0, 10.0],
        "profit_target_pct":    [0.25, 0.40, 0.50],
        "stop_loss_multiple":   [1.5, 2.0, 2.5],
    },
)

wf_result = wf.run(
    strategy_factory = lambda cfg: CondorStrategy,
    config_class     = CondorConfig,
    full_period      = (date(2022, 1, 1), date(2026, 5, 5)),
    chain_source     = ChainDataSource.from_local_parquet(...),
)

# wf_result reports out-of-sample performance only — no peeking.
```

Out-of-sample Sharpe must be ≥ 0.7 of in-sample Sharpe across all windows. If not, the strategy is overfit and is *not* approved for live deployment.

---

## 11. Reproducibility Requirements

Every backtest result must be reproducible bit-for-bit. The framework enforces:

1. All randomness uses an explicit seed stored in the result.
2. Data version (git hash of the parquet snapshot or content hash of the input directory) is stored in the result.
3. Strategy version (git commit) is stored in the result.
4. The exact `CondorConfig` is serialized into the result.
5. Slippage and commission models are serialized by name + params.

```python
@dataclass
class BacktestResult:
    metadata: ResultMetadata
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict
    config_snapshot: dict
    data_hash: str
    strategy_git_sha: str
    seed: int
    runtime_seconds: float
```

---

## 12. Adapters

### 12.1 vectorbt Adapter

For fast parameter sweeps over signal-only research (not full options simulation).

```python
from spyder.backtest.adapters.vectorbt_adapter import VbtSignalSweep

sweep = VbtSignalSweep(
    signal_fn = lambda spy_close, vix: (vix < 25) & (spy_close > spy_close.rolling(50).mean()),
    return_fn = "iron_condor_proxy",  # closed-form approximation
    parameter_grid = {...},
)

heatmap = sweep.run(start=date(2020,1,1), end=date(2026,5,5))
heatmap.plot()
```

### 12.2 backtrader Adapter

For event-driven sanity checks of the custom engine. Should produce within 1% of the custom engine's metrics on identical inputs. Used as a cross-check, not a primary tool.

---

## 13. Test Plan

### 13.1 Engine correctness tests
- `test_clock_advances_monotonically`
- `test_broker_sim_fills_at_correct_slippage`
- `test_broker_sim_charges_correct_commissions`
- `test_chain_loader_returns_correct_quotes_for_timestamp`
- `test_expiring_options_settle_at_intrinsic_value`
- `test_assignment_logic_for_in_the_money_shorts`

### 13.2 Strategy parity tests
- `test_strategy_runs_unchanged_in_live_and_backtest_contexts` — same code, both contexts, identical decision sequence on a deterministic data slice
- `test_persistence_schema_matches_live`

### 13.3 Performance tests
- `test_full_year_minute_resolution_under_60_seconds`
- `test_walk_forward_grid_of_500_configs_under_30_minutes`

### 13.4 Numerical tests
- `test_sharpe_matches_known_reference` (against textbook example with synthetic returns)
- `test_max_drawdown_matches_known_reference`

---

## 14. Acceptance Criteria

- [ ] Strategy modules import nothing from `spyder.backtest` or `spyder.live` directly
- [ ] One year of minute-resolution backtest of SPEC-SPYDER-01 completes in under 60s on the RTX 4070 dev box
- [ ] HTML and PDF reports generate from the same `BacktestResult` object
- [ ] Walk-forward runner produces non-leaking out-of-sample results
- [ ] All metrics match published reference values to ±0.5% on canonical test data
- [ ] Reports include cumulative equity curve, monthly returns heatmap, drawdown chart, P/L histogram, and per-trade greeks attribution

---

## 15. Out of Scope

- Multi-asset portfolio backtesting (single-strategy SPY focus only)
- Live paper trading replay (the live system handles paper via Tradier sandbox)
- Order book simulation (we trust mid-±-half-spread as a sufficient model for liquid SPY options)
- Tax modeling (handled at the reporting layer, not the engine)
