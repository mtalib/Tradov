# SPEC-SPYDER-01 — 0DTE Iron Condor Strategy Module

| Field | Value |
|---|---|
| Spec ID | SPEC-SPYDER-01 |
| Module | `spyder/strategies/condor_0dte.py` |
| Version | 1.0.0 |
| Status | Ready for implementation |
| Depends on | SPEC-SPYDER-03 (Tradier), SPEC-SPYDER-04 (Greeks) |
| Target | Autonomous SPY 0DTE iron condor execution |

---

## 1. Purpose

Implement a fully autonomous 0DTE iron condor strategy on SPY that:
1. Detects whether the current trading day meets entry criteria (volatility regime, calendar filters).
2. Selects four option strikes (long put, short put, short call, long call) based on delta targets.
3. Submits a single multileg credit order to Tradier.
4. Manages the position with profit target, stop loss, and a hard time-based close.
5. Logs every state transition for auditability and post-trade analysis.

This is the highest-frequency, highest-priority strategy in the Spyder suite.

---

## 2. Strategy Definition

### 2.1 Structure

A 0DTE SPY iron condor is four legs at the same expiration (today's close):

```
Leg 1: BUY  to open  PUT  at strike P_long   (lowest strike)
Leg 2: SELL to open  PUT  at strike P_short
Leg 3: SELL to open  CALL at strike C_short
Leg 4: BUY  to open  CALL at strike C_long   (highest strike)
```

Net credit received = `(short_put_mid + short_call_mid) - (long_put_mid + long_call_mid)`.

### 2.2 Profit Profile

- Maximum profit: net credit, realized if SPY closes between `P_short` and `C_short`.
- Maximum loss: `(spread_width × 100) - net_credit`, realized if SPY closes outside the long strikes.
- Breakevens: `P_short - net_credit` and `C_short + net_credit`.

---

## 3. Configuration Schema

```python
from dataclasses import dataclass
from datetime import time
from typing import Literal

@dataclass(frozen=True)
class CondorConfig:
    # Strike selection
    short_strike_delta: float = 0.10       # absolute delta target per short leg
    spread_width_dollars: float = 3.0      # wing width in $; 3, 5, or 10 typical
    delta_tolerance: float = 0.02          # acceptable deviation from target delta

    # Entry timing
    entry_time: time = time(9, 35)         # ET; let opening volatility settle
    no_entry_after: time = time(11, 30)    # ET; skip if past this and not filled

    # Volatility regime filters (entry gates)
    vix_min: float = 14.0                  # below this, premiums too thin
    vix_max: float = 35.0                  # above this, tail risk too high
    iv_rank_min: float = 30.0              # 0-100 scale

    # Calendar filters
    skip_fomc_days: bool = True
    skip_cpi_days: bool = True
    skip_nfp_days: bool = True
    skip_opex_friday: bool = False         # monthly OpEx Fridays

    # Position management
    profit_target_pct: float = 0.40        # close at 40% of max credit captured
    stop_loss_multiple: float = 2.0        # stop at -2x credit received
    hard_close_time: time = time(15, 0)    # ET; force close all by this time
    hard_close_buffer_minutes: int = 30    # warn this many minutes before

    # Sizing
    max_account_risk_pct: float = 0.02     # 2% of account NAV per trade
    max_concurrent_positions: int = 1      # don't stack 0DTE condors

    # Execution
    use_preview: bool = True               # Tradier preview before live submission
    limit_slippage_pct: float = 0.05       # accept 5% worse than mid for fills
    fill_timeout_seconds: int = 60         # cancel and retry if not filled
```

---

## 4. State Machine

```
                ┌────────────┐
                │   IDLE     │  Waiting for entry window
                └─────┬──────┘
                      │ entry_time reached & gates pass
                      ▼
                ┌────────────┐
                │ EVALUATING │  Pulling chain, computing strikes
                └─────┬──────┘
                      │ strikes valid
                      ▼
                ┌────────────┐
                │ SUBMITTING │  Multileg order in flight
                └─────┬──────┘
            filled    │
                      ▼
                ┌────────────┐
                │   ACTIVE   │  Monitoring P/L, stops, time
                └─────┬──────┘
                      │
        ┌─────────────┼──────────────┬──────────────┐
        │             │              │              │
   profit hit    stop hit       3pm reached    error/escalate
        │             │              │              │
        ▼             ▼              ▼              ▼
   ┌────────┐    ┌────────┐    ┌──────────┐   ┌──────────┐
   │ CLOSING│    │ CLOSING│    │  CLOSING │   │ FAULTED  │
   └────┬───┘    └────┬───┘    └────┬─────┘   └────┬─────┘
        └─────────────┴─────────────┘              │
                      │                            │
                      ▼                            ▼
                ┌──────────┐               ┌──────────────┐
                │  CLOSED  │               │ HUMAN_REVIEW │
                └──────────┘               └──────────────┘
```

### 4.1 State Definitions

| State | Allowed Transitions | Side Effects |
|---|---|---|
| `IDLE` | → `EVALUATING` | None |
| `EVALUATING` | → `SUBMITTING`, → `IDLE` (gates fail) | Strike selection, log decision |
| `SUBMITTING` | → `ACTIVE`, → `FAULTED` | Tradier order placed |
| `ACTIVE` | → `CLOSING`, → `FAULTED` | Periodic P/L check (5s tick) |
| `CLOSING` | → `CLOSED`, → `FAULTED` | Tradier closing order placed |
| `CLOSED` | (terminal for the day) | Persist trade, recompute account stats |
| `FAULTED` | → `HUMAN_REVIEW` | Alert, halt new entries |
| `HUMAN_REVIEW` | (terminal until manual) | Pager/email; no further auto-action |

---

## 5. Algorithm — Entry Gate Logic

```python
def should_enter_today(ctx: Context, cfg: CondorConfig) -> tuple[bool, str]:
    """Returns (decision, reason). reason is logged either way."""

    now = ctx.clock.now_et()
    today = now.date()

    # Time-of-day gate
    if now.time() < cfg.entry_time:
        return False, f"too_early:{now.time()}"
    if now.time() > cfg.no_entry_after:
        return False, f"too_late:{now.time()}"

    # Calendar gates
    if cfg.skip_fomc_days and ctx.calendar.is_fomc_day(today):
        return False, "fomc_day"
    if cfg.skip_cpi_days and ctx.calendar.is_cpi_release(today):
        return False, "cpi_day"
    if cfg.skip_nfp_days and ctx.calendar.is_nfp_release(today):
        return False, "nfp_day"
    if cfg.skip_opex_friday and ctx.calendar.is_opex_friday(today):
        return False, "opex_friday"

    # Market state gates
    vix = ctx.market.vix_spot()
    if vix < cfg.vix_min:
        return False, f"vix_too_low:{vix:.2f}"
    if vix > cfg.vix_max:
        return False, f"vix_too_high:{vix:.2f}"

    iv_rank = ctx.market.spy_iv_rank()
    if iv_rank < cfg.iv_rank_min:
        return False, f"iv_rank_low:{iv_rank:.1f}"

    # Position state gate
    if ctx.portfolio.count_open_0dte_condors() >= cfg.max_concurrent_positions:
        return False, "max_positions_reached"

    # Account state gate
    if ctx.portfolio.is_in_drawdown_lockout():
        return False, "drawdown_lockout"

    return True, "all_gates_passed"
```

---

## 6. Algorithm — Strike Selection

```python
def select_strikes(
    chain: OptionsChain,
    spot: float,
    cfg: CondorConfig,
) -> CondorStrikes | None:
    """
    Selects four strikes for a 0DTE iron condor. Returns None if no valid
    combination meets delta tolerance.

    Strategy:
      1. Find the put with delta closest to -short_strike_delta.
      2. Find the call with delta closest to +short_strike_delta.
      3. Long strikes are short_strike ± spread_width_dollars.
      4. Validate that long strikes exist in the chain (SPY trades $1 strikes).
      5. Validate quoted bid/ask are non-zero on all four legs.
    """

    today_chain = chain.filter(expiration=chain.today_dte_zero())
    if today_chain.is_empty():
        return None

    # Find short put: target delta = -short_strike_delta
    target_put_delta = -cfg.short_strike_delta
    short_put = today_chain.find_put_by_delta(
        target=target_put_delta,
        tolerance=cfg.delta_tolerance,
    )
    if short_put is None:
        return None

    # Find short call: target delta = +short_strike_delta
    target_call_delta = +cfg.short_strike_delta
    short_call = today_chain.find_call_by_delta(
        target=target_call_delta,
        tolerance=cfg.delta_tolerance,
    )
    if short_call is None:
        return None

    # Long strikes are mechanically derived
    long_put_strike  = short_put.strike  - cfg.spread_width_dollars
    long_call_strike = short_call.strike + cfg.spread_width_dollars

    long_put  = today_chain.find_put_by_strike(long_put_strike)
    long_call = today_chain.find_call_by_strike(long_call_strike)
    if long_put is None or long_call is None:
        return None

    # Liquidity sanity check — every leg must have a real two-sided market
    for leg in (short_put, long_put, short_call, long_call):
        if leg.bid <= 0 or leg.ask <= 0 or (leg.ask - leg.bid) > 0.20:
            return None  # reject illiquid or wide-spread strikes

    return CondorStrikes(
        long_put=long_put,
        short_put=short_put,
        short_call=short_call,
        long_call=long_call,
    )
```

---

## 7. Algorithm — Position Sizing

```python
def calculate_quantity(
    strikes: CondorStrikes,
    nav: float,
    cfg: CondorConfig,
) -> int:
    """Returns the number of contracts to trade (>= 1 or 0 if cannot size)."""

    # Net credit per single contract
    credit_per_contract = (
        (strikes.short_put.mid + strikes.short_call.mid)
        - (strikes.long_put.mid  + strikes.long_call.mid)
    )

    # Max loss per single contract = (spread_width * 100) - credit_per_contract
    spread_width = strikes.short_put.strike - strikes.long_put.strike
    max_loss_per_contract = (spread_width * 100) - (credit_per_contract * 100)

    if max_loss_per_contract <= 0:
        return 0  # malformed: would never lose, reject

    # Cap risk per the config
    risk_budget = nav * cfg.max_account_risk_pct
    qty = int(risk_budget // max_loss_per_contract)

    return max(qty, 0)
```

---

## 8. Algorithm — Position Management Loop

```python
async def manage_position(
    pos: ActivePosition,
    ctx: Context,
    cfg: CondorConfig,
) -> None:
    """Runs every TICK_INTERVAL_SECONDS while position is ACTIVE."""

    TICK_INTERVAL_SECONDS = 5

    while pos.state == State.ACTIVE:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        now = ctx.clock.now_et()

        # 1) Mark-to-market
        current_value = ctx.broker.get_position_mtm(pos.order_id)
        pnl = pos.entry_credit - current_value  # both per-contract, signed

        # 2) Profit target
        if pnl >= pos.entry_credit * cfg.profit_target_pct:
            await close_position(pos, ctx, reason="profit_target")
            return

        # 3) Stop loss (premium-based, NOT spy-price-based)
        if pnl <= -pos.entry_credit * cfg.stop_loss_multiple:
            await close_position(pos, ctx, reason="stop_loss")
            return

        # 4) Hard time close
        if now.time() >= cfg.hard_close_time:
            await close_position(pos, ctx, reason="hard_close")
            return

        # 5) Heartbeat log
        if int(now.timestamp()) % 60 == 0:
            ctx.log.heartbeat(pos, pnl, current_value)
```

---

## 9. Tradier Order Construction

The four-leg multileg order payload. See SPEC-SPYDER-03 for full broker module.

```python
def build_open_payload(
    account_id: str,
    strikes: CondorStrikes,
    quantity: int,
    limit_price: float,
) -> dict:
    return {
        "class": "multileg",
        "symbol": "SPY",
        "type": "credit",
        "duration": "day",
        "price": f"{limit_price:.2f}",  # net credit limit
        "option_symbol[0]": strikes.long_put.occ_symbol,
        "side[0]": "buy_to_open",
        "quantity[0]": str(quantity),
        "option_symbol[1]": strikes.short_put.occ_symbol,
        "side[1]": "sell_to_open",
        "quantity[1]": str(quantity),
        "option_symbol[2]": strikes.short_call.occ_symbol,
        "side[2]": "sell_to_open",
        "quantity[2]": str(quantity),
        "option_symbol[3]": strikes.long_call.occ_symbol,
        "side[3]": "buy_to_open",
        "quantity[3]": str(quantity),
    }
```

The corresponding **close** order flips every `_to_open` to `_to_close` and uses `type=debit` with the limit price set to `mid * (1 + slippage_pct)`.

---

## 10. Persistence Schema

SQLite (matches Captova-ARC convention of local-first storage).

```sql
CREATE TABLE IF NOT EXISTS condor_trades (
    trade_id              TEXT PRIMARY KEY,           -- uuid4
    trade_date            TEXT NOT NULL,              -- YYYY-MM-DD
    entry_timestamp_utc   TEXT NOT NULL,
    exit_timestamp_utc    TEXT,
    state                 TEXT NOT NULL,              -- terminal state name

    -- Strikes
    long_put_strike       REAL NOT NULL,
    short_put_strike      REAL NOT NULL,
    short_call_strike     REAL NOT NULL,
    long_call_strike      REAL NOT NULL,
    spread_width          REAL NOT NULL,

    -- Greeks at entry
    short_put_delta       REAL NOT NULL,
    short_call_delta      REAL NOT NULL,
    short_put_iv          REAL NOT NULL,
    short_call_iv         REAL NOT NULL,

    -- Market context at entry
    spy_spot_at_entry     REAL NOT NULL,
    vix_at_entry          REAL NOT NULL,
    iv_rank_at_entry      REAL NOT NULL,

    -- Trade economics
    quantity              INTEGER NOT NULL,
    entry_credit          REAL NOT NULL,              -- per contract
    exit_debit            REAL,                       -- per contract
    realized_pnl_dollars  REAL,                       -- (credit - debit) * qty * 100
    max_loss_dollars      REAL NOT NULL,

    -- Execution
    entry_order_id        TEXT NOT NULL,
    exit_order_id         TEXT,
    exit_reason           TEXT,                       -- profit_target | stop_loss | hard_close | error

    -- Metadata
    config_snapshot_json  TEXT NOT NULL               -- frozen CondorConfig
);

CREATE INDEX idx_condor_trades_date ON condor_trades(trade_date);
CREATE INDEX idx_condor_trades_state ON condor_trades(state);
```

---

## 11. Failure Modes & Handling

| Failure | Detection | Response |
|---|---|---|
| Tradier API timeout on entry | HTTP timeout on submit | Cancel any partial, log, return to IDLE, no retry today |
| Partial fill | `exec_quantity < quantity` after timeout | Cancel remainder, manage filled portion as smaller position |
| One leg unfilled, three filled | Multileg-as-atomic *should* prevent; if observed, escalate | FAULTED → HUMAN_REVIEW |
| VIX data feed stale | timestamp > 5 min old at entry decision | Skip day with reason `data_stale_vix` |
| Greeks data missing | delta is None on any leg | Skip strike, try next valid combination |
| Position closing fails | Close order rejected | Retry once with wider limit; if still fails, escalate |
| Account locked / not enough buying power | preview returns error | Halt strategy, log, notify |
| Unexpected dividend / corporate action | Should not occur for SPY same-day | Treat as FAULTED |
| Network partition during ACTIVE state | No heartbeat for 60s | On reconnect, reconcile via `get_orders` and `get_positions` |

---

## 12. Logging Requirements

Every state transition must emit a structured JSON log line:

```python
{
    "ts":          "2026-05-05T14:32:11.342Z",
    "trade_id":    "8b1c...",
    "module":      "condor_0dte",
    "from_state":  "EVALUATING",
    "to_state":    "SUBMITTING",
    "reason":      "all_gates_passed",
    "context": {
        "spy_spot":     578.42,
        "vix":          16.8,
        "iv_rank":      52.3,
        "credit":       1.20,
        "quantity":     5
    }
}
```

Log destinations: stdout (for systemd journal), rotating file at `~/.spyder/logs/condor_0dte.jsonl`, optional shipping to monitoring backend.

---

## 13. Test Plan

### 13.1 Unit Tests (`tests/strategies/test_condor_0dte.py`)
- `test_should_enter_rejects_pre_entry_time`
- `test_should_enter_rejects_post_cutoff_time`
- `test_should_enter_rejects_low_vix`
- `test_should_enter_rejects_high_vix`
- `test_should_enter_rejects_fomc_day`
- `test_should_enter_passes_with_all_gates_open`
- `test_select_strikes_finds_correct_put_delta`
- `test_select_strikes_finds_correct_call_delta`
- `test_select_strikes_returns_none_when_chain_empty`
- `test_select_strikes_rejects_wide_bid_ask`
- `test_calculate_quantity_caps_at_account_risk`
- `test_calculate_quantity_returns_zero_on_malformed_credit`
- `test_build_open_payload_matches_tradier_schema`

### 13.2 Integration Tests (sandbox required)
- `test_full_lifecycle_paper_account` — IDLE → EVALUATING → SUBMITTING → ACTIVE → CLOSED
- `test_profit_target_triggers_close`
- `test_stop_loss_triggers_close`
- `test_hard_close_at_3pm`
- `test_recovery_after_simulated_network_drop`

### 13.3 Backtest Validation
See SPEC-SPYDER-02. Strategy must show positive expectancy over 500+ historical trading days with realistic slippage and commission models before live deployment.

---

## 14. Acceptance Criteria

- [ ] Module passes all unit tests with 100% line coverage of state machine
- [ ] Module passes all sandbox integration tests for at least 5 consecutive trading days
- [ ] Backtest over the most recent 2 years shows: positive expectancy, max drawdown < 20% of NAV, Sharpe > 1.0
- [ ] All state transitions emit structured logs
- [ ] All trades persisted to SQLite with full snapshot
- [ ] Manual kill-switch (e.g., `~/.spyder/HALT` sentinel file) halts new entries within one tick
- [ ] FOMC, CPI, NFP calendar correctly identified for next 30 days at startup

---

## 15. Out of Scope (for this spec)

- Iron butterfly variant (different strike structure — separate spec).
- Directional bias mode (legging in one side at a time — separate spec).
- Multi-DTE iron condor management — focus is strictly same-day.
- GUI for live monitoring — the GUI module (G-series per Spyder convention) is a consumer of this module's logs and DB, not part of this spec.

---

## 16. References

- 9,100-trade study (Theta Profits, April 2021–February 2026): 40% win rate, 2.2× win/loss ratio, positive expectancy.
- Option Alpha 230k 0DTE trade study: SPY accounts for 81% of 0DTE trades; iron butterflies and credit spreads outperform pure iron condors due to directional bias.
- CBOE: 0DTE represents >45% of SPX/SPY options volume.
- Henry Schwartz (CBOE) 0DTE methodology: "$1 rule" for 10-pt SPX condors mid-day.
