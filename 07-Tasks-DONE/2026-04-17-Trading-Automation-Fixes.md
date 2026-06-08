# Paper Trading Automation — Implementation Report

**Date:** 2026-04-17
**Branch:** `refactor/g05-widget-extraction`
**Module:** `Tradov/TradovR_Runtime/TradovR11_PaperStrategyRunner.py`
**Companion launcher:** `Tradov/TradovQ_Scripts/TradovQ93_RunPaper.py`

---

## 1. Executive Summary

This report documents the full implementation lifecycle for the autonomous paper trading runner (`TradovR11_PaperStrategyRunner`), delivered across two sessions on 2026-04-17.

The system autonomously:
- Pulls live SPY + VIX quotes via Tradier (read-only, no live trades placed)
- Selects entry via pluggable strategy adapters with defined risk parameters
- Gates every new entry through four sequential checks: regime → sizing → E01 risk → portfolio Greeks
- Captures per-leg Greeks at fill and enforces portfolio-level exposure ceilings
- Evaluates exits on every tick and records all outcomes to `PaperTradingHarness`

Verified end-to-end against live Tradier data (SPY @ $701.66) before and after each phase.

---

## 2. Architecture

### 2.1 Data Flow

```
Tradier API (read-only)
  └─ get_quotes(["SPY", "VIX"])          ← batched, one call per tick
  └─ get_option_chain_with_greeks(...)    ← per expiry, on-demand

MarketContext(spy_price, now, vix)        ← passed to every adapter

PaperStrategyRunner.tick():
  1. Fetch SPY + VIX (batched)
  2. Build MarketContext
  3. _evaluate_exits() — check all open positions
     └─ adapter.evaluate_exit() → reason string or None
  4. For each adapter (up to max_concurrent / max_open caps):
     a. adapter.regime_gate(ctx)          ← VIX cap check
     b. adapter.evaluate_entry(ctx, runner) → ProposedPosition
     c. _size_position(max_loss)          ← 1% equity risk budget
     d. _risk_gate(proposal, contracts)   ← TradovE01 RiskManager
     e. _greek_gate(proposal, contracts)  ← portfolio delta/gamma/vega caps
     f. Stamp contracts on legs, record position, harness.record_trade()
```

### 2.2 Gate Sequence (Entry)

| Order | Gate | Implementation | Rejects when |
|---|---|---|---|
| 1 | Regime | `StrategyAdapter.regime_gate(ctx)` | VIX > per-strategy cap |
| 2 | Sizing | `_size_position(max_loss)` | Produces contract count; min=1 |
| 3 | E01 Risk | `_risk_gate()` → `RiskManager.validate_signal()` | E01 rejects or clamps qty |
| 4 | Greek | `_greek_gate()` | Portfolio delta/gamma/vega would exceed cap |

### 2.3 Key Classes

| Class | Role |
|---|---|
| `MarketContext` | Tick snapshot: `spy_price`, `now`, `vix` |
| `ProposedPosition` | Adapter's trade proposal (pre-sizing, pre-approval) |
| `SimulatedLeg` | Single option leg with `delta`, `gamma`, `vega`, `theta` captured at fill |
| `SimulatedPosition` | Live position with signed `position_delta`, `position_gamma`, `position_vega` properties |
| `StrategyAdapter` | Base class: `regime_gate()`, `evaluate_entry()`, `evaluate_exit()`, `_leg_with_greeks()` |
| `BullPutAdapter` | Bull-put credit spread (~7–14 DTE, 0.20-Δ short, $5 wing) |
| `ZeroDTEAdapter` | 0DTE iron condor (~0.15-Δ shorts, $5 wings) |
| `PaperStrategyRunner` | Orchestrator; owns all sizing, gating, fills, bookkeeping |

---

## 3. Session 1 — Foundation (prior session, restored from summary)

### 3.1 What was built

The initial prototype replaced a stub with a fully functional autonomous runner:

- **Live data pull:** `TradierClient.get_quotes()` + `get_option_chain_with_greeks()` per tick
- **E01 risk gate:** `RiskValidationRequest` → `RiskManager.validate_signal()` via `get_risk_manager(portfolio_value=equity)` with graceful try/except fallback
- **Dynamic sizing:** `equity × RISK_PCT_PER_TRADE / (max_loss × 100)`, capped at `MAX_CONTRACTS_CAP=10`, further clipped by E01's `max_safe_quantity`
- **StrategyAdapter protocol:** `within_entry_window()`, `evaluate_entry()`, `evaluate_exit()` — base class covers profit target / stop loss / strike threat
- **BullPutAdapter:** DTE 7–14, 0.20-Δ short put, $5 wing, min credit $0.40, adds DTE ≤ 1 time-stop
- **ZeroDTEAdapter:** same-day expiry IC, 0.15-Δ shorts, $5 wings, min total credit $0.50, adds 15:30 hard-close
- **PaperTradingHarness integration:** `harness.record_trade()` on both open and close
- **Helper accessibility:** 9 internal helpers renamed from `_foo` → `foo` to eliminate protected-access warnings from adapter subclasses

### 3.2 Constants introduced (Session 1)

```python
RISK_PCT_PER_TRADE: float = 0.01        # 1% of equity per trade
MAX_CONTRACTS_CAP: int = 10
DEFAULT_STARTING_EQUITY: float = 100_000.0
BP_TARGET_SHORT_DELTA: float = 0.20
BP_WING_WIDTH_DOLLARS: float = 5.0
BP_MIN_CREDIT: float = 0.40
BP_TARGET_DTE_MIN: int = 7
BP_TARGET_DTE_MAX: int = 14
ZDTE_TARGET_SHORT_DELTA: float = 0.15
ZDTE_WING_WIDTH_DOLLARS: float = 5.0
ZDTE_MIN_TOTAL_CREDIT: float = 0.50
PROFIT_TARGET_PCT: float = 0.50
STOP_LOSS_MULTIPLE: float = 2.00
STRIKE_THREAT_PCT: float = 0.005
```

### 3.3 Session 1 smoke test result

```
[ok] risk gate: RiskManager
[ok] adapters: ['BullPutCreditSpread', 'ZeroDTE_IronCondor']
[ok] opened: BullPutCreditSpread x2 | credit=$0.59 max_loss=$4.41
[ok] total dollar risk: $882.00 (0.88% of equity)
[ok] trades_placed: 1
```

---

## 4. Session 2 — Regime Gate + Portfolio Greek Gate

### 4.1 Problem Statement

After Session 1, two safety gaps remained:

1. **No regime filter** — the runner would attempt entries in any VIX environment, including extreme volatility where selling premium has negative expectancy.
2. **No portfolio Greek tracking** — positions were entered without awareness of aggregate directional or volatility exposure. A sequence of directional entries could result in unacceptably large delta or vega exposure at the portfolio level.

### 4.2 Implementation: Regime Gate

**Approach:** Lightweight VIX-based cap on `StrategyAdapter`, preferred over wiring `TradovF10_MarketRegimeDetector` directly because F10 is a heavy stateful class with monitoring threads and ML initialisation — too costly for a per-tick call. The cap constant and the `regime_gate` seam are designed so a future `F10Adapter` subclass can replace the VIX check with full regime classification without changing the runner.

**New constants:**

```python
REGIME_VIX_SYMBOL: str = "VIX"
BP_MAX_VIX: float = 30.0     # block new bull-puts above this
ZDTE_MAX_VIX: float = 35.0   # block new 0DTE ICs above this
```

**New `StrategyAdapter` method:**

```python
def regime_gate(self, ctx: MarketContext) -> str | None:
    """Return reject reason or None to allow.
    Permissive when ctx.vix is None (missing data never blocks trading)."""
    if self.max_vix is None or ctx.vix is None:
        return None
    if ctx.vix > self.max_vix:
        return f"regime_vix_cap (VIX={ctx.vix:.2f} > {self.max_vix:.2f})"
    return None
```

**Adapter class attributes:**

```python
class BullPutAdapter(StrategyAdapter):
    max_vix = BP_MAX_VIX   # 30.0

class ZeroDTEAdapter(StrategyAdapter):
    max_vix = ZDTE_MAX_VIX # 35.0
```

**VIX fetch — batched with SPY:**

```python
def _get_spy_and_vix(self) -> tuple[dict | None, float | None]:
    resp = self._client.get_quotes(["SPY", "VIX"])
    # Parses quote list; returns (spy_dict, vix_last) with SPY-only fallback on error
```

A single Tradier API call now returns both quotes. `MarketContext.vix` carries the result. On fetch failure the fallback returns `(spy_quote, None)` — VIX unknown, regime gate permissive.

### 4.3 Implementation: Portfolio Greek Gate

**Approach:** Inline `_greek_gate()` inside `PaperStrategyRunner`, preferred over wiring `TradovE15_GreekLimitsManager` directly because E15 is similarly heavy (monitoring threads, ML regime classifier, Prometheus integration). The cap constants and method signature are designed to be replaced by an E15 delegation call.

**New constants:**

```python
MAX_PORTFOLIO_DELTA: float = 50.0    # |Σ signed delta × 100|
MAX_PORTFOLIO_VEGA: float = 200.0    # |Σ signed vega × 100|
MAX_PORTFOLIO_GAMMA: float = 10.0    # |Σ signed gamma × 100|
```

**Per-leg Greek capture — `SimulatedLeg` extended:**

```python
@dataclass
class SimulatedLeg:
    # ... existing fields ...
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
```

Greeks are populated via `StrategyAdapter._leg_with_greeks()` which reads directly from the Tradier chain quote (the same object used for pricing):

```python
@staticmethod
def _leg_with_greeks(runner, opt, side, strike, option_type, entry_price) -> SimulatedLeg:
    return SimulatedLeg(
        ...,
        delta=float(runner.field_of(opt, "delta", 0.0) or 0.0),
        gamma=float(runner.field_of(opt, "gamma", 0.0) or 0.0),
        vega=float(runner.field_of(opt, "vega", 0.0) or 0.0),
        theta=float(runner.field_of(opt, "theta", 0.0) or 0.0),
    )
```

**`SimulatedPosition` signed Greek properties:**

```python
def _signed_greek(self, greek: str) -> float:
    """Σ(sign × raw_greek × leg.qty); sign = -1 for short, +1 for long."""
    total = 0.0
    for leg in self.legs:
        sign = -1.0 if leg.side == "short" else 1.0
        total += sign * getattr(leg, greek, 0.0) * leg.qty
    return total

@property
def position_delta(self) -> float:
    return self._signed_greek("delta") * 100   # ×100 multiplier

@property
def position_gamma(self) -> float:
    return self._signed_greek("gamma") * 100

@property
def position_vega(self) -> float:
    return self._signed_greek("vega") * 100
```

**`_greek_gate()` — pre-entry portfolio check:**

```python
def _greek_gate(self, proposal: ProposedPosition, contracts: int) -> str | None:
    # Compute proposed position Greeks at sized contracts (legs have qty=0 at this point)
    prop_d = prop_g = prop_v = 0.0
    for leg in proposal.legs:
        sign = -1.0 if leg.side == "short" else 1.0
        prop_d += sign * leg.delta * contracts * 100
        prop_g += sign * leg.gamma * contracts * 100
        prop_v += sign * leg.vega * contracts * 100

    cur_d, cur_g, cur_v = self._portfolio_greeks()
    new_d, new_g, new_v = cur_d + prop_d, cur_g + prop_g, cur_v + prop_v

    if abs(new_d) > MAX_PORTFOLIO_DELTA:
        return f"portfolio_delta_cap (|{new_d:.1f}| > {MAX_PORTFOLIO_DELTA:.1f})"
    if abs(new_g) > MAX_PORTFOLIO_GAMMA:
        return f"portfolio_gamma_cap (|{new_g:.2f}| > {MAX_PORTFOLIO_GAMMA:.2f})"
    if abs(new_v) > MAX_PORTFOLIO_VEGA:
        return f"portfolio_vega_cap (|{new_v:.1f}| > {MAX_PORTFOLIO_VEGA:.1f})"
    return None
```

**`snapshot()` extended** to include current portfolio Greeks:

```python
"portfolio_greeks": {"delta": d, "gamma": g, "vega": v}
```

### 4.4 Bug found and fixed during verification

**Bug:** `position_delta` was double-counting contracts.

- `_signed_greek()` multiplied by `leg.qty`, which equals `self.contracts` after fill.
- `position_delta` then multiplied by `self.contracts` again — squaring the contract count.

**Example:** 2 contracts, short Δ=−0.2015, long Δ=−0.1425:

| Before fix | After fix |
|---|---|
| `(0.2015 − 0.1425) × 100 × 2 × 2 = $23.60` | `(0.2015 − 0.1425) × 100 × 2 = $11.80` |

**Fix:** removed `× self.contracts` from all three position Greek properties (leg.qty already carries the contract count).

**Verified:** `position_delta=11.80` matches hand-calculation exactly.

---

## 5. Verification Results

### 5.1 Regime gate unit tests (6 assertions, all pass)

```
[ok] regime gate: all 6 assertions pass

BullPutCreditSpread @ VIX=99  → regime_vix_cap (VIX=99.00 > 30.00)   ✓ blocked
ZeroDTE_IronCondor  @ VIX=99  → regime_vix_cap (VIX=99.00 > 35.00)   ✓ blocked
BullPutCreditSpread @ VIX=15  → None                                   ✓ allowed
ZeroDTE_IronCondor  @ VIX=15  → None                                   ✓ allowed
BullPutCreditSpread @ VIX=None → None                                  ✓ allowed (permissive)
ZeroDTE_IronCondor  @ VIX=None → None                                  ✓ allowed (permissive)
```

### 5.2 Live tick against Tradier (SPY=$701.66)

```
[ok] adapters: [('BullPutCreditSpread', 30.0), ('ZeroDTE_IronCondor', 35.0)]
[ok] tick: {'spy_price': 701.66, 'open_positions': 1, 'closes_this_tick': 0, 'opens_this_tick': 1}
[ok] snapshot portfolio_greeks: {'delta': 11.80, 'gamma': -0.888, 'vega': -14.64}
[ok] position leg Greeks: short put K=689 d=-0.202 g=0.0173 v=0.301
                           long  put K=684 d=-0.142 g=0.0128 v=0.228
[ok] position_delta=$11.80   expected≈$11.80   ✓ exact match
[ok] position_vega=$-14.64   (short net vega, correct sign for credit spread)
```

All well under portfolio caps: delta 11.80 < 50, gamma 0.888 < 10, vega 14.64 < 200.

---

## 6. Complete Feature State

| Capability | Status | Implementation |
|---|---|---|
| Live SPY market data | ✅ | `TradierClient.get_quotes(["SPY", "VIX"])` batched |
| Live VIX fetch | ✅ | Same batched call; graceful None on failure |
| Live options chain with Greeks | ✅ | `get_option_chain_with_greeks()` per expiry |
| Bull-put credit spread strategy | ✅ | `BullPutAdapter` — 7–14 DTE, 0.20-Δ, $5 wing |
| 0DTE iron condor strategy | ✅ | `ZeroDTEAdapter` — same-day, 0.15-Δ, $5 wings |
| Regime gate (VIX-based) | ✅ | `StrategyAdapter.regime_gate()` with per-strategy caps |
| Dynamic risk-budget sizing | ✅ | 1% equity / max_loss, capped at 10 contracts |
| E01 RiskManager validation | ✅ | `RiskManager.validate_signal()` via `get_risk_manager()` |
| Portfolio Greek gate | ✅ | `_greek_gate()` — delta/gamma/vega ceilings |
| Per-leg Greek capture | ✅ | `SimulatedLeg.delta/gamma/vega/theta` at fill |
| Portfolio Greek aggregation | ✅ | Signed `position_delta/gamma/vega` on `SimulatedPosition` |
| Profit target exit (50%) | ✅ | `StrategyAdapter.evaluate_exit()` base class |
| Stop loss exit (2× credit) | ✅ | `StrategyAdapter.evaluate_exit()` base class |
| Strike threat exit (0.5%) | ✅ | `StrategyAdapter.evaluate_exit()` base class |
| DTE time-stop (BullPut ≤1d) | ✅ | `BullPutAdapter.evaluate_exit()` |
| 0DTE hard-close at 15:30 ET | ✅ | `ZeroDTEAdapter.evaluate_exit()` |
| PaperTradingHarness recording | ✅ | `harness.record_trade()` on open and close |
| Snapshot with portfolio Greeks | ✅ | `runner.snapshot()["portfolio_greeks"]` |
| Per-strategy open-position cap | ✅ | `adapter.max_open` enforced per tick |
| Overall concurrent position cap | ✅ | `DEFAULT_MAX_CONCURRENT=3` |
| Entry time-of-day windows | ✅ | ET-aware, per adapter |
| Cooldown between entry attempts | ✅ | `_cooldown_ok()` per adapter |

---

## 7. Remaining Open Items

### 7.1 Real D-series strategy routing (deferred)

**What:** Replace `BullPutAdapter` / `ZeroDTEAdapter` inline logic with proper `D03Adapter(TradovD03_CreditSpread)` and `D04Adapter(TradovD04_ZeroDTE)` wrappers that delegate entry/exit to the real D-class signal interface.

**Why deferred:** D03/D04 require `EventManager + RiskProfile + OHLCV DataFrame + their own chain provider`. Plugging them in properly touches 5+ modules and is a 1–2 day refactor. The real value of D-class integration is their coupling to `TradovL07_PaperTradeLearner` and `TradovL08_EntryOptimizer` — those dependencies don't yet exist in the paper runner. Defer until ML integration is ready.

**Seam:** `StrategyAdapter.evaluate_entry()` is the natural extension point. A future `D03Adapter(StrategyAdapter)` wraps the D-class signal output with no changes to the runner.

### 7.2 TradovF09_EntryFilters (deferred)

**What:** Pre-entry filter set — spread quality, volume confirmation, news guard, extended time-of-day rules.

**Why deferred:** The current time-of-day + delta/credit checks cover the critical cases. F09 is additive.

**Seam:** `StrategyAdapter.within_entry_window()` can be expanded to accept the `MarketContext` and consult F09 without changing the runner.

### 7.3 TradovE03_StopLossManager (deferred)

**What:** Replace inline stop logic in `StrategyAdapter.evaluate_exit()` with E03 delegation — trailing stops, time-based stops, Greeks-based stops.

**Why deferred:** Current stops (profit target 50%, stop 200%, strike threat 0.5%, DTE/time stops) cover the primary cases. E03 is additive.

**Seam:** `StrategyAdapter.evaluate_exit()` — replace return value logic with `E03StopLossManager.check(pos, ctx)`.

### 7.4 TradovR02_PaperEngine (intentionally skipped)

**Why:** R02 adds an abstraction layer that duplicates what `PaperTradingHarness` already does (record trades, track P&L). Our inline fill model (mid ± $0.02 slippage) gives full control with less code. Only worth revisiting if `OrderManager` event integration is needed for another subsystem.

### 7.5 Full TradovF10_MarketRegimeDetector integration (future)

**What:** Replace the VIX cap in `regime_gate()` with a call to `MarketRegimeDetector.get_current_regime()` for composite regime classification (trend + volatility + liquidity + breadth).

**Why deferred:** F10 is heavy at startup (monitoring threads, GARCH model, VIX history deque). The VIX cap achieves the primary safety goal. F10 integration is the natural next step when per-tick regime state becomes required for strategy selection.

**Seam:** Subclass `StrategyAdapter` and override `regime_gate()`:

```python
class F10RegimeAdapter(BullPutAdapter):
    def __init__(self, regime_detector: MarketRegimeDetector):
        self._f10 = regime_detector

    def regime_gate(self, ctx: MarketContext) -> str | None:
        state = self._f10.get_current_regime()
        if state and state.volatility_regime in {MarketRegime.HIGH_VOLATILITY, MarketRegime.EXTREME_VOLATILITY}:
            return f"regime_f10_block ({state.volatility_regime.value})"
        return super().regime_gate(ctx)
```

### 7.6 Full TradovE15_GreekLimitsManager integration (future)

**What:** Replace inline `_greek_gate()` with `GreekLimitsManager.check_strategy_violations()`.

**Why deferred:** E15 has monitoring threads, ML regime classifier, and Prometheus integration. The inline cap logic achieves identical safety semantics. E15 integration adds dynamic VIX-scaled limit adjustment — useful but not blocking.

**Seam:** Replace `_greek_gate()` body with `self._greek_limits_manager.check_strategy_violations(proposal.strategy)`.

---

## 8. How to Run

```bash
# Paper mode (live data, simulated execution)
source .venv/bin/activate
python Tradov/TradovQ_Scripts/TradovQ93_RunPaper.py --with-strategies --verbose --heartbeat 60

# Optional env override for starting equity
PAPER_STARTING_EQUITY=50000 python Tradov/TradovQ_Scripts/TradovQ93_RunPaper.py --with-strategies
```

**Environment variables read:**

| Variable | Default | Purpose |
|---|---|---|
| `TRADIER_API_KEY` | required | Tradier auth token |
| `TRADIER_ACCOUNT_ID` | required | Account for position/balance queries |
| `TRADIER_ENVIRONMENT` | `live` | `live` (data) or `sandbox` |
| `TRADING_MODE` | `paper` | Must be `paper`; safety guard prevents live fills |
| `PAPER_STARTING_EQUITY` | `100000.0` | Starting equity for sizing calculations |

---

## 9. Files Modified

| File | Nature |
|---|---|
| `Tradov/TradovR_Runtime/TradovR11_PaperStrategyRunner.py` | All implementation |
| `Tradov/TradovQ_Scripts/TradovQ93_RunPaper.py` | Unchanged — factory signature preserved |
