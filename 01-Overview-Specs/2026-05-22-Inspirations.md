# Tradov — New Features Added 2026-05-22

Inspired by analysis of the open-source [FinceptTerminal](https://github.com/Swayam2004/FinceptTerminal) project (AGPL-3.0).  All implementations were written independently from scratch — no source code was copied or adapted from that repository.

---

## 1  TradovS17 — Kalshi Prediction Markets Signal

**Module:** `Tradov/TradovS_Signals/TradovS17_PredictionMarkets.py`

### What it does
Fetches live prediction-market probabilities from [Kalshi](https://kalshi.com) and exposes them as S07 metrics so strategies and the dashboard can factor macro-market sentiment into trading decisions.

Two probabilities are tracked:

| Metric key | What it measures |
|---|---|
| `KALSHI_RECESSION_PROB` | Implied probability (0–1) of a US recession in the next 12 months |
| `KALSHI_FED_PAUSE_PROB` | Implied probability (0–1) that the Fed leaves rates unchanged at the next FOMC meeting |
| `KALSHI_AVAILABLE` | `True` when the API key is present and at least one live market was fetched |

### Design highlights
- **TTL-cached (10 minutes)** — one background fetch per cycle; no per-signal API calls.
- **Graceful degradation** — when `KALSHI_API_KEY` is absent or the API is unreachable the module emits `NaN` probabilities and `KALSHI_AVAILABLE=False` rather than raising.
- **Thread-safe singleton** — `get_prediction_markets_client()` uses double-checked locking so the single instance is safely shared across threads.
- **Midpoint pricing** — each market probability is computed as `(bid + ask) / 2 / 100` from Kalshi's cent-denominated order book, which is more robust than relying solely on the last-traded price.
- **Fed-pause fallback** — if a "hold/pause" market is not found directly, the module infers the probability as `1 − (cut probability)`.

### Configuration
```
KALSHI_API_KEY=<your Kalshi REST API key>   # leave blank to disable
```

### Integration
- S07 (`TradovS07_CustomMetricsOrchestrator`) calls `_update_prediction_markets_metrics()` each cycle and exposes formatted entries in `_format_metrics()`.
- Quality tracking slot: `PREDICTION_MARKETS`.
- Success counted in the cycle summary (`/15 sources`).

---

## 2  TradovS18 — Economic Calendar Stand-Down Gate

**Module:** `Tradov/TradovS_Signals/TradovS18_EconomicCalendar.py`

### What it does
Tracks tier-1 macroeconomic events and suppresses new position entries during configurable windows before and after each event.  The gate is enforced in D31's `_evaluate_pre_risk_signal_gates()` so it sits upstream of the risk manager — no signal reaches execution while a stand-down is active.

### Events covered

| Source | Events |
|---|---|
| Hardcoded schedule | FOMC announcements (2025–2026, all at 14:00 ET) |
| Monthly heuristics | NFP (1st Friday 08:30 ET), CPI (mid-month Wednesday 08:30 ET), PPI (Tuesday before CPI 08:30 ET), PCE (last Friday 08:30 ET) |
| Config override | `config/economic_calendar.json` — explicit dates that take precedence over heuristics for the same calendar day |

### Metric keys (emitted via S07)

| Key | Description |
|---|---|
| `ECO_STAND_DOWN` | `True` when entries are currently suppressed |
| `ECO_NEXT_EVENT_NAME` | Name of the nearest upcoming event (e.g. `"FOMC"`, `"NFP"`) |
| `ECO_NEXT_EVENT_MINUTES` | Minutes until that event (negative = past event, still in post-window) |

### Design highlights
- **No external API** — the event schedule is computed locally; no network dependency.
- **Rebuild once per calendar day** — `_ensure_events_built()` only re-generates the event list when the date rolls over, keeping the hot path allocation-free.
- **Closing trades bypass the gate** — `is_stand_down_active()` is only evaluated for opening signals.  Exits are never blocked.
- **Fully configurable windows** — default ±30-minute stand-down window is overridable per-deployment via environment variables.
- **Config-file override schema:**
  ```json
  [
    {"name": "CPI", "datetime_et": "2026-06-11T08:30:00"},
    {"name": "FOMC", "datetime_et": "2026-06-18T14:00:00"}
  ]
  ```

### Configuration
```
TRADOV_ECO_STAND_DOWN_BEFORE_MIN=30    # minutes before event to begin stand-down (default 30)
TRADOV_ECO_STAND_DOWN_AFTER_MIN=30     # minutes after event to end stand-down   (default 30)
TRADOV_ECO_CALENDAR_GATE_ENABLED=1     # set to 0 to disable the gate entirely
```

### Integration
- **S07** calls `_update_eco_calendar_metrics()` each cycle and formats the three metric keys.
- **D31** (`TradovD31_StrategyOrchestrator`) resolves the singleton lazily via `_get_eco_calendar()` and calls `_passes_eco_calendar_gate(signal)` inside `_evaluate_pre_risk_signal_gates()`.  A blocked signal returns stage `"pre_risk"`, reason `"eco_calendar_gate"`, with the event name and timing in the detail field.
- Quality tracking slot: `ECO_CALENDAR`.
- Success counted in the cycle summary (`/15 sources`).

---

## 3  S07 Orchestrator Additions

**Module:** `Tradov/TradovS_Signals/TradovS07_CustomMetricsOrchestrator.py`

Changes made to wire S17 and S18:

- `self.prediction_markets` and `self.eco_calendar` instance vars declared in `__init__`.
- Six new default keys added to `current_metrics`: `KALSHI_RECESSION_PROB`, `KALSHI_FED_PAUSE_PROB`, `KALSHI_AVAILABLE`, `ECO_STAND_DOWN`, `ECO_NEXT_EVENT_NAME`, `ECO_NEXT_EVENT_MINUTES`.
- `_init_calculators()` — lazy-import blocks for S17 and S18 added after the S16 block; both fail safely on `ImportError`.
- `_init_quality_tracking()` — `PREDICTION_MARKETS` and `ECO_CALENDAR` added to the metric-name list.
- `_run_metrics_update_cycle()` — `_update_prediction_markets_metrics()` and `_update_eco_calendar_metrics()` called after the S15 market-intel block.
- Success-count denominator updated from 13 → **15**.
- `_update_prediction_markets_metrics()` and `_update_eco_calendar_metrics()` methods added.
- `_format_metrics()` — formatted entries for all six new keys added.

---

## 4  D31 Gate Addition

**Module:** `Tradov/TradovD_Strategies/TradovD31_StrategyOrchestrator.py`

Changes made:

- `self._eco_calendar: Any | None = None` and `self._eco_calendar_resolved: bool = False` added to `__init__`.
- `_get_eco_calendar()` — lazy resolver that imports `get_economic_calendar` from S18 using the same dual-import pattern (`Tradov.TradovS_Signals.…` with `TradovS_Signals.…` fallback) used by other optional module resolvers.
- `_passes_eco_calendar_gate(signal)` — returns `(True, "")` for closing trades unconditionally; otherwise calls `is_stand_down_active()` and returns the reason string on block.
- `_evaluate_pre_risk_signal_gates()` — eco calendar gate inserted **after** the `paper_startup_regime_wait` check and **before** the `entry_trust_gate` check, so the event window is enforced regardless of market-condition scores.

---

## 5  Configuration File

**File:** `.env.example`

Added a new section documenting all S17/S18 environment variables with descriptions and safe defaults.

---

## Gate Order (Updated)

The complete `_evaluate_pre_risk_signal_gates` sequence after today's changes:

1. `session_window_gate` — outside primary trading hours or broker cutoff
2. `paper_startup_regime_wait` — opening signals deferred until L09 regime engine is ready
3. **`eco_calendar_gate`** ← *new* — stand-down window around tier-1 macro events
4. `entry_trust_gate` — F09 filter checks + regime-policy gating
5. E01 risk manager `validate_signal()` — position sizing, capital, exposure limits
6. Dispatch

---

## Files Changed or Created

| File | Change |
|---|---|
| `Tradov/TradovS_Signals/TradovS17_PredictionMarkets.py` | **Created** |
| `Tradov/TradovS_Signals/TradovS18_EconomicCalendar.py` | **Created** |
| `Tradov/TradovS_Signals/TradovS07_CustomMetricsOrchestrator.py` | Modified — S17/S18 wiring |
| `Tradov/TradovD_Strategies/TradovD31_StrategyOrchestrator.py` | Modified — eco calendar gate |
| `.env.example` | Modified — S17/S18 env vars documented |
