# SPEC-TRADOV-04 — Greeks Engine Module

| Field | Value |
|---|---|
| Spec ID | SPEC-TRADOV-04 |
| Module | `tradov/quant/greeks/` (package) |
| Version | 1.0.0 |
| Status | Ready for implementation |
| Depends on | (none — pure computation) |
| Target | Fast, vectorized Black-Scholes greeks and IV inversion for SPY options |

---

## 1. Purpose

A self-contained, dependency-light, NumPy-vectorized Black-Scholes engine that:
1. Computes **delta, gamma, theta, vega, rho** for European options on dividend-paying underlyings.
2. Inverts implied volatility from market prices.
3. Computes **IV Rank** and **IV Percentile** for regime gating.
4. Provides **portfolio-level greeks** for any combination of legs.
5. Validates and normalizes greeks coming from Tradier (which sources from ORATS).

Tradier's chain endpoint already returns greeks. We compute our own anyway because:
- We need consistency between live and backtest (where we're computing from synthetic chains).
- ORATS greeks update asynchronously; for tight 0DTE timing we want fresh values from current quotes.
- We need a consistent IV baseline to compute IV Rank historically.

---

## 2. Model

Black-Scholes for European options on a dividend-paying underlying (SPY pays a quarterly dividend, ~1.3% annualized as of 2026):

```
d1 = [ ln(S/K) + (r - q + σ²/2) * T ] / (σ * √T)
d2 = d1 - σ * √T

Call:  C = S * e^(-q*T) * N(d1)  -  K * e^(-r*T) * N(d2)
Put:   P = K * e^(-r*T) * N(-d2) -  S * e^(-q*T) * N(-d1)
```

where:
- `S` = underlying spot
- `K` = strike
- `T` = time to expiration in years (use 365-day calendar; for sub-day 0DTE use seconds remaining / seconds-in-year)
- `r` = risk-free rate (use 3-month T-bill yield from FRED; refresh daily)
- `q` = continuous dividend yield (use SPY's trailing 12-month dividend / spot)
- `σ` = implied volatility
- `N(.)` = standard normal CDF
- `n(.)` = standard normal PDF

### 2.1 Greeks (continuous-dividend version)

```
Δ_call = e^(-q*T) * N(d1)
Δ_put  = e^(-q*T) * (N(d1) - 1)

Γ      = e^(-q*T) * n(d1) / (S * σ * √T)         # same for call and put

Vega   = S * e^(-q*T) * n(d1) * √T               # raw, per-1.0 vol unit; quote per 1% as Vega/100

Θ_call = - S * e^(-q*T) * n(d1) * σ / (2*√T)
         - r * K * e^(-r*T) * N(d2)
         + q * S * e^(-q*T) * N(d1)
Θ_put  = - S * e^(-q*T) * n(d1) * σ / (2*√T)
         + r * K * e^(-r*T) * N(-d2)
         - q * S * e^(-q*T) * N(-d1)

ρ_call =  K * T * e^(-r*T) * N(d2)
ρ_put  = -K * T * e^(-r*T) * N(-d2)
```

Theta is conventionally quoted "per calendar day" — divide raw theta by 365.

---

## 3. Public API

```python
from dataclasses import dataclass
from typing import Literal
import numpy as np

OptionType = Literal["C", "P"]

@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    theta: float        # per calendar day
    vega:  float        # per 1.0 vol point (i.e., 100% vol = 1.0); divide by 100 for "per 1%"
    rho:   float        # per 1.0 rate point

def black_scholes_price(
    spot: float, strike: float, t_years: float,
    rate: float, dividend_yield: float,
    sigma: float, option_type: OptionType,
) -> float: ...

def black_scholes_greeks(
    spot: float, strike: float, t_years: float,
    rate: float, dividend_yield: float,
    sigma: float, option_type: OptionType,
) -> Greeks: ...

def implied_volatility(
    market_price: float,
    spot: float, strike: float, t_years: float,
    rate: float, dividend_yield: float,
    option_type: OptionType,
    tol: float = 1e-6, max_iter: int = 50,
) -> float: ...
```

All scalar functions have **vectorized counterparts** that accept NumPy arrays. The vectorized form is what backtesting uses to price entire chains in microseconds:

```python
def black_scholes_greeks_vec(
    spot:   np.ndarray | float,
    strike: np.ndarray,
    t_years:np.ndarray,
    rate:   float,
    dividend_yield: float,
    sigma:  np.ndarray,
    option_type: np.ndarray,    # bytes 'C'|'P' or bool array (True=call)
) -> dict[str, np.ndarray]:
    """Returns {'price', 'delta', 'gamma', 'theta', 'vega', 'rho'} arrays."""
```

---

## 4. Implementation Notes

### 4.1 Use SciPy where it exists, hand-roll where it matters

```python
from scipy.stats import norm
from scipy.special import erf

# For hot loops, this is ~2x faster than scipy.stats.norm.cdf:
def _norm_cdf(x: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + erf(x / np.sqrt(2.0)))

def _norm_pdf(x: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * x * x) / np.sqrt(2.0 * np.pi)
```

### 4.2 Implied volatility solver

For inversion, prefer **Brent's method** with `scipy.optimize.brentq` over Newton-Raphson — it doesn't fail at low-vega points (deep ITM/OTM) the way Newton can.

```python
from scipy.optimize import brentq

def implied_volatility(market_price, spot, strike, t_years, rate, q, opt_type, tol=1e-6):
    if market_price <= 0:
        return float("nan")
    intrinsic = max(0.0, (spot - strike) if opt_type == "C" else (strike - spot))
    if market_price < intrinsic - 1e-6:
        return float("nan")  # arbitrage violation in input

    def f(sigma):
        return black_scholes_price(spot, strike, t_years, rate, q, sigma, opt_type) - market_price

    try:
        return brentq(f, a=1e-4, b=5.0, xtol=tol, maxiter=100)
    except ValueError:
        return float("nan")
```

For batch IV inversion across an entire chain, the cost of `brentq` per-strike adds up. The high-performance path uses **Jäckel's "Let's Be Rational"** algorithm (or its `py_lets_be_rational` Python binding), which is 10–100× faster and numerically robust. Recommend including `py_lets_be_rational` as an optional dependency.

### 4.3 0DTE time-to-expiry handling

For 0DTE, `t_years = (seconds_to_4pm_et) / (365 * 86400)` — using a calendar year basis to match Tradier/ORATS conventions. As `t_years → 0`, gamma and theta both blow up; clip to `max(t_years, 1/365/86400 * 60)` (one minute floor) to avoid divide-by-zero.

### 4.4 American vs European

SPY options are **American-style** (early exercise allowed). For typical algorithmic strategies on SPY, the early-exercise premium is small enough that European pricing (Black-Scholes) is acceptable, *except* near ex-dividend dates for ITM calls. For SPY's quarterly dividends:
- Avoid being short ITM calls within 2 trading days of ex-dividend.
- For accurate American option pricing, add a **Bjerksund-Stensland 2002** approximation for cases where the ex-div risk matters. This is a ~10× cost vs Black-Scholes but only needed for specific situations.

---

## 5. Implied Volatility Rank and Percentile

### 5.1 Definitions

- **IV Rank** = `(IV_today - IV_52wk_low) / (IV_52wk_high - IV_52wk_low) * 100`
  - 0 = lowest IV in past year, 100 = highest.
- **IV Percentile** = `(# trading days in past 252 where IV was below today's IV) / 252 * 100`
  - More robust to single outlier high-IV days than IV Rank.

### 5.2 Which IV to use as "the" IV

Use the **30-day constant-maturity ATM IV**. If the chain has expirations at 25 and 35 DTE, linearly interpolate the ATM IV at each expiry to get a constant-maturity 30-day reading. This avoids rolling discontinuities.

```python
def constant_maturity_atm_iv(
    chain_today: ChainSnapshot,
    target_dte: int = 30,
) -> float:
    """Returns the ATM IV at the constant target_dte, interpolating between
       bracketing expirations."""
    expirations = sorted(chain_today.expirations())
    dtes = [(e - chain_today.date).days for e in expirations]

    # Find bracket
    for i, d in enumerate(dtes):
        if d >= target_dte:
            if i == 0:
                return chain_today.atm_iv(expirations[0])
            d_low, d_high = dtes[i-1], dtes[i]
            iv_low  = chain_today.atm_iv(expirations[i-1])
            iv_high = chain_today.atm_iv(expirations[i])
            w = (target_dte - d_low) / (d_high - d_low)
            return iv_low + w * (iv_high - iv_low)
    return chain_today.atm_iv(expirations[-1])
```

### 5.3 Storage for historical IV

Persist daily ATM IV at 30 DTE in SQLite for fast IV Rank computation:

```sql
CREATE TABLE IF NOT EXISTS spy_atm_iv_daily (
    date         TEXT PRIMARY KEY,    -- YYYY-MM-DD
    atm_iv_30d   REAL NOT NULL,
    spot_close   REAL NOT NULL,
    realized_vol_20d REAL,            -- backfilled when 20 days after this row exists
    vrp_30d_minus_20d REAL            -- iv30 - rv20
);
```

Realized volatility (close-to-close, annualized):

```python
def realized_volatility(closes: np.ndarray, window: int = 20) -> float:
    """Close-to-close realized vol, annualized. closes: most recent (window+1) values."""
    log_returns = np.diff(np.log(closes))
    return np.std(log_returns, ddof=1) * np.sqrt(252)
```

---

## 6. Portfolio Greeks

The portfolio-level computation: for any list of legs (each with its sign — long/short — and quantity), aggregate the greeks.

```python
@dataclass
class PositionLeg:
    occ_symbol: str
    quantity:   int    # positive = long, negative = short
    greeks:     Greeks # per-contract

def portfolio_greeks(legs: list[PositionLeg]) -> Greeks:
    # Each contract represents 100 shares; multiply by 100 for dollar greeks
    return Greeks(
        delta = 100.0 * sum(l.quantity * l.greeks.delta for l in legs),
        gamma = 100.0 * sum(l.quantity * l.greeks.gamma for l in legs),
        theta = 100.0 * sum(l.quantity * l.greeks.theta for l in legs),
        vega  = 100.0 * sum(l.quantity * l.greeks.vega  for l in legs),
        rho   = 100.0 * sum(l.quantity * l.greeks.rho   for l in legs),
    )
```

For a 0DTE iron condor, expected portfolio greeks at entry (rough):
- Delta: near zero (within ±5 dollars-per-$1-spot per contract)
- Gamma: negative (short gamma)
- Theta: positive (we receive time decay)
- Vega: negative (we sell vol)

These signs are validation checks — an iron condor with positive vega has been mis-built.

---

## 7. Validating Tradier Greeks

Tradier returns greeks via ORATS. Compare to our own computed greeks; if they disagree by more than 5% on any greek for an ATM option, log a warning. They'll diverge slightly because ORATS uses a fitted IV surface; ours uses single-point inversion from current bid/ask mid. Persistent divergence > 10% indicates a stale ORATS feed.

```python
def validate_tradier_greeks(
    tradier_greeks: Greeks,
    spot: float, strike: float, t_years: float,
    market_mid: float, rate: float, q: float,
    option_type: OptionType,
) -> ValidationReport:
    iv = implied_volatility(market_mid, spot, strike, t_years, rate, q, option_type)
    if not np.isfinite(iv):
        return ValidationReport(ok=False, reason="iv_inversion_failed")
    own = black_scholes_greeks(spot, strike, t_years, rate, q, iv, option_type)
    diffs = {
        "delta": abs(own.delta - tradier_greeks.delta),
        "gamma": abs(own.gamma - tradier_greeks.gamma),
        "theta": abs(own.theta - tradier_greeks.theta),
        "vega":  abs(own.vega  - tradier_greeks.vega),
    }
    return ValidationReport(ok=max(diffs.values()) < 0.05, diffs=diffs)
```

---

## 8. Reference Data

### 8.1 Risk-free rate

Use the **3-month constant-maturity Treasury yield** from FRED series `DGS3MO`. Refresh daily from <https://fred.stlouisfed.org/series/DGS3MO>. Cache for 24 hours; if stale, fall back to the most recent valid value.

### 8.2 Dividend yield

For SPY, compute `q = trailing_12mo_dividend_dollars / current_spot`. SPY's distribution history is published by State Street and is also available from the chain's underlying quote on Tradier. As of 2026, ~1.3%.

For 0DTE specifically, `q` matters very little — it's the *expected dividend over T years*, and `T` is hours. Setting `q=0` for 0DTE is a defensible simplification.

---

## 9. Performance Budget

Target performance on the RTX 4070 dev box (CPU only — no GPU acceleration needed):

| Operation | Budget |
|---|---|
| Single greeks computation | < 5 µs |
| Single IV inversion | < 50 µs |
| Vectorized greeks for 500 strikes | < 200 µs |
| Vectorized IV inversion for 500 strikes | < 5 ms |
| IV Rank computation from cache | < 100 µs |

If profiling shows hot loops, the next optimizations (in order) are: NumPy vectorization (default), Numba JIT (optional dep), Cython (last resort).

---

## 10. Test Plan

### 10.1 Numerical correctness
- `test_call_put_parity` — `C - P = S*e^(-qT) - K*e^(-rT)` to floating-point precision
- `test_greeks_match_haug_textbook_examples` — fixed inputs, fixed expected outputs from Haug's "Complete Guide to Option Pricing Formulas"
- `test_implied_vol_round_trip` — `iv = invert(price(σ))` recovers `σ` to 1e-6 over a grid
- `test_atm_call_delta_near_half_for_zero_drift` — ATM delta ≈ 0.5 when `r=q=0`
- `test_zero_dte_doesnt_explode` — t_years = 60 seconds returns finite greeks
- `test_deep_otm_returns_zero_price_finite_greeks`

### 10.2 Vectorized parity
- Vectorized greeks over 1000 random strikes match the scalar version to 1e-12

### 10.3 Iron condor greeks signs
- For a synthesized 16-delta iron condor: portfolio delta ∈ [-0.1, 0.1], gamma < 0, theta > 0, vega < 0

### 10.4 IV Rank
- Synthetic series with known min/max returns correct IV Rank
- IV Percentile rejects non-trading days from the denominator

---

## 11. Acceptance Criteria

- [ ] All numerical tests pass to 1e-6 precision
- [ ] Vectorized form is at least 50× faster than scalar form for 500-strike chains
- [ ] No SciPy import in the hot path (use the local `_norm_cdf`/`_norm_pdf`)
- [ ] Tradier greeks validation runs as part of the ACTIVE-state heartbeat in SPEC-TRADOV-01
- [ ] FRED rate fetcher caches and falls back gracefully on outage
- [ ] IV Rank cache is populated for the past 252 trading days at first run

---

## 12. Out of Scope

- Stochastic volatility models (Heston, SABR) — Black-Scholes is sufficient for current strategies
- Volatility surface fitting (SVI, SSVI) — ORATS does this; we don't need to
- American option pricing trees / FD methods — only the Bjerksund-Stensland approximation if/when ex-div risk becomes material
- VIX-derivative pricing (VIX options follow a different process) — out of scope for SPY strategies
