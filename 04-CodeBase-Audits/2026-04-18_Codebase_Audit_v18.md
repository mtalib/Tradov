# Spyder Codebase Audit v18 — Gap & Implementation Report

> **Date:** 2026-04-18  
> **Branch:** `fix/audit-v14-all`  
> **Scope:** New modules (R14, R15, B20, B21, E00, E24) + D31 concurrency gaps not addressed by v15  
> **Prior status:** v14 (A1–A26 ✅) + v15 (B1–B15 ✅) = 70/70 tests passing

---

## Executive Summary

Post-v15 audit identified **7 findings** (C1–C7) across four newly-added modules and one long-standing concurrency gap in D31. Three findings are BLOCKER/HIGH and must be resolved before live deployment. All seven findings are fixable in a single focused sprint without architectural change.

---

## Findings

### C1 — BLOCKER — `strategy_allocations` unprotected against concurrent mutations (D31)

**File:** `SpyderD31_StrategyOrchestrator.py`  
**Severity:** BLOCKER — live `RuntimeError` crash risk  

**Root cause:** v15 fix B3 added `_strategies_lock` to protect `active_strategies` and `paused_strategies`. The parallel dict `strategy_allocations` (35+ access sites) was never brought under the same lock.

**Mutation sites outside lock:**
| Line | Site | Issue |
|------|------|-------|
| 622 | `add_strategy()` | Writes after lock released |
| 673–675 | `remove_strategy()` | Deletes after lock released |
| 963–982 | `_execute_rebalancing()` | Read-modify-write, no lock |
| 1493–1496 | `_update_allocations_from_optimizer()` | Read-modify-write, no lock |

**Iteration sites in background threads (no snapshot):**  
Lines 792, 955, 1043, 1049, 1090, 1147, 1181, 1229, 1447, 1553, 1666, 2054 — all iterate `strategy_allocations.items()` or `.values()` without holding any lock. A concurrent `add_strategy()` or `remove_strategy()` call causes `RuntimeError: dictionary changed size during iteration`.

**Fix:**
1. In `add_strategy()`: construct the `StrategyAllocation` object before the lock, then perform `self.strategy_allocations[strategy_id] = new_alloc` **inside** the existing `with self._strategies_lock:` block.
2. In `remove_strategy()`: move `del self.strategy_allocations[strategy_id]` and the `freed_capital` read **inside** the `with self._strategies_lock:` block.
3. In all background-thread iteration sites: take a snapshot `with self._strategies_lock: allocs = dict(self.strategy_allocations)` and iterate over `allocs`.

---

### C2 — HIGH — `check_exit()` not implemented by any strategy; ExitMonitor exit-signaling is inert

**Files:** `SpyderR14_ExitMonitor.py`, `SpyderD01_BaseStrategy.py`  
**Severity:** HIGH — core functionality silently non-operational  

**Root cause:** `ExitMonitor._check_position()` calls `strategy.check_exit(view: _PositionView)`. No strategy class (D01 or any subclass) implements `check_exit()`. The `AttributeError` is caught silently in `_check_position()` and the function returns early. The orphan-detection path in ExitMonitor functions correctly; only the strategy-driven exit path is dead.

```python
# ExitMonitor._check_position() — line ~220:
try:
    decision = strategy.check_exit(view)   # <- AttributeError: always raised
except AttributeError:
    return                                  # <- silently swallowed
```

**Fix:** Add a `check_exit()` stub to `BaseStrategy` that returns `None` (hold). Concrete strategies can override to implement profit targets and stop losses. Also update `ExitDecision` import in D01.

---

### C3 — MEDIUM — `create_session_supervisor()` never calls `set_session_supervisor()`; singleton is always `None`

**File:** `SpyderR12_SessionSupervisor.py`  
**Severity:** MEDIUM — dead code path; future regressions when ExitMonitor is extended  

**Root cause:** `create_session_supervisor()` constructs and returns a `SessionSupervisor` instance but never calls `set_session_supervisor(supervisor)`. D31's `add_strategy()` calls `get_session_supervisor()` to notify ExitMonitor via `register_strategy()` — this always returns `None`, so the notification is never sent. The system currently works only because ExitMonitor holds a direct reference to D31's `active_strategies` dict (shared mutable object).

**Fix:** Add `set_session_supervisor(supervisor)` call inside `create_session_supervisor()` before `return`. Add `set_session_supervisor(None)` inside `SessionSupervisor.stop()` to clear the singleton on shutdown.

---

### C4 — MEDIUM — ExitMonitor reads `strategy_map` (= `active_strategies`) without `_strategies_lock`

**File:** `SpyderR14_ExitMonitor.py`  
**Severity:** MEDIUM — formally unsafe; works in CPython due to GIL but will fail on PyPy  

**Root cause:** ExitMonitor's `_sweep_loop` reads `self.strategy_map.get(strategy_id)` where `strategy_map` IS D31's `active_strategies` dict. D31 protects writes to `active_strategies` under `_strategies_lock`. ExitMonitor has no access to this lock and reads without coordination.

**Fix:** ExitMonitor's `_sweep()` method should call `list(self.strategy_map.items())` outside of any lock (safe atomic snapshot via GIL) at the very start of each sweep cycle. This is already effectively a snapshot — formalise it by assigning `items = list(self.strategy_map.items())` at the top of `_sweep()` and iterating `items` instead of the live dict.

---

### C5 — LOW — ExitMonitor `_orphan_alerted` set mutated from multiple threads without a lock

**File:** `SpyderR14_ExitMonitor.py`  
**Severity:** LOW — race condition on set mutation  

**Root cause:** `_orphan_alerted: set[str]` is mutated by the sweep thread (`_handle_orphan` → `add`) and by external calls to `register_strategy()` and `unregister_strategy()` (`discard`). No lock protects these concurrent accesses.

**Fix:** Add `self._orphan_lock = threading.Lock()` in `__init__` and wrap all `_orphan_alerted.add()` and `_orphan_alerted.discard()` calls with it.

---

### C6 — LOW — `cancel_order` in R04 TOCTOU window (B1 spec vs. actual implementation mismatch)

**File:** `SpyderR04_LiveEngine.py`  
**Severity:** LOW — double-cancel to broker possible; gracefully handled  

**Root cause:** The v15 B1 spec called for an optimistic pop before the broker call. The actual implementation checks membership under lock, releases the lock, calls the broker, then re-acquires to pop. Two concurrent callers can both pass the membership check before either pops, resulting in two broker cancel requests for the same order. Tradier rejects the second gracefully; R04 logs a warning.

**Fix (optional):** Align implementation with original B1 spec: pop under lock first; if broker rejects, restore via `setdefault`.

---

### C7 — MEDIUM — `TradierClient.cancel_order` returns `dict`, but `BrokerProtocol` declares `bool`

**File:** `SpyderB_Broker/SpyderB40_TradierClient.py`, `SpyderB21_BrokerProtocol.py`  
**Severity:** MEDIUM — protocol nonconformance; `isinstance(client, BrokerProtocol)` is True due to duck typing, but static analysis tools and runtime type checks will flag the mismatch  

**Root cause:** `BrokerProtocol.cancel_order() -> bool`. `TradierClient.cancel_order()` returns `dict[str, Any]` (the raw Tradier JSON response). `PaperBroker.cancel_order()` correctly returns `bool`. R04 uses `if result:` which is truthy for a non-empty dict, so behaviour is correct — but the type contract is violated.

**Fix:** Add a thin wrapper in `TradierClient.cancel_order()` that returns `bool(raw_result.get("order", {}).get("id"))` instead of the raw dict. The raw dict can still be returned as a `cancel_order_raw()` method for callers that need the full response.

---

## Improvements / Ideas

| # | Description | Impact |
|---|-------------|--------|
| O1 | PaperBroker `get_account_balances()` always returns the initial balance — fills never update `_account_balance`. Add fill-cost accumulation to `_filled_response()`. | Paper P&L accuracy |
| O2 | PaperBroker `close_position()` option-detection uses `any(c in symbol for c in ("C","P"))` which false-positives on equity tickers like "PG", "CP". Use OCC shape regex instead. | Paper mode correctness |
| O3 | ExitMonitor's `check_exit` interface: concrete strategies (D02 IronCondor, D04 ZeroDTE) should override `check_exit()` to implement their specific profit-target and stop-loss logic rather than relying purely on E01/E03. | Capital protection |
| O4 | Add a test specifically for ExitMonitor: orphan detection, exit-signal emission path, and strategy registration lifecycle. | Test coverage |
| O5 | `C06_DataValidator.start_freshness_watcher()` is implemented but never called. Either wire it into SessionSupervisor (de-duplicating E24) or remove it to eliminate dead code confusion. | Code clarity |

---

## Implementation Plan

| Priority | Finding | File(s) | Effort |
|----------|---------|---------|--------|
| 1 | C1 — `strategy_allocations` lock | D31 | ~30 min |
| 2 | C3 — `set_session_supervisor()` | R12 | 5 min |
| 3 | C2 — `check_exit` stub | D01 | 5 min |
| 4 | C5 — `_orphan_alerted` lock | R14 | 5 min |
| 5 | C7 — `cancel_order` return type | B40 | 10 min |
| 6 | C4 — ExitMonitor snapshot | R14 | 5 min |
| 7 | O2 — PaperBroker option detection | R15 | 10 min |
| — | Run full test suite | — | — |

---

## Status After v18

| Finding | Status |
|---------|--------|
| C1 | ✅ Fixed |
| C2 | ✅ Fixed |
| C3 | ✅ Fixed |
| C4 | ✅ Fixed |
| C5 | ✅ Fixed |
| C6 | Accepted (low severity; broker handles gracefully) |
| C7 | ✅ Fixed |
| O1 | Deferred (paper-trading accuracy; not a live-trading blocker) |
| O2 | ✅ Fixed |
| O5 | Deferred (dead code; no impact) |

---

## Section 8 — Dashboard Market Internals Extension (2026-04-21)

**Branch:** `fix/audit-v14-all`  
**Test result:** 70/70 ✅  

Added five new symbols to the MARKET INTERNALS panel in `SpyderG05_TradingDashboard.py` to support 0-DTE SPY mean-reversion abort gates: `$VOLD`, `XLK`, `XLF`, `TNX`, `RVOL`. All five were wired to the panel in the prior sprint but received no data (displayed `---,--`). Root cause: two isolated data paths — the S07/S11 breadth path and the G18 JSON file path — with no bridge for the new symbols.

### Changes

#### `SpyderS11_TradingViewInternals.py`
- Added `"vold": "https://www.tradingview.com/symbols/USI-VOLD/"` to `_SYMBOLS`.
- Added `"vold": float("nan")` to `_stub()` return dict so the contract is consistent whether or not scraping succeeds.

#### `SpyderS07_CustomMetricsOrchestrator.py`
- `_update_tv_breadth_metrics()`: added `"VOLD"` to the cache-serve fallback list (both the TTL-skip path and both error-fallback paths); extracted `snap.get("vold", float("nan"))` into `updated_metrics["VOLD"]`.
- `_format_metrics()`: added `"VOLD"` entry (value, formatted as `:.0f`, breadth quality score) after the `"BREADTH_REGIME"` block so the key appears in the dict emitted by `metrics_updated`.

#### `SpyderG05_TradingDashboard.py`
- `_S07_METRIC_ROUTING`: fixed the dead `"YIELD_10Y": ("10Y", 1.0)` route — corrected to `("TNX", 1.0)` so S07's FRED 10-year yield flows to the `TNX` widget. Removed the redundant `"TNX": ("TNX", 1.0)` entry (S07 never emits the key `"TNX"` directly).

#### `SpyderG18_MarketDataWorker.py`
- `_fetch_live_data_from_tradier()`: added `"XLK"`, `"XLF"` to the Tradier symbol list; added SPY quote capture (`_spy_q_slow`) and RVOL computation (session-fraction-adjusted relative volume); RVOL written as `"RVOL"` key into `live_data`.
- `_fetch_quotes_fast()`: same additions — `"XLK"`, `"XLF"` appended to symbol list; SPY quote captured; RVOL computed and merged into `existing` before the JSON write.
- `_fetch_eod_snapshot()`: added `"XLK"`, `"XLF"` to the EOD symbol list so closing prices are preserved for next-morning startup.

### Data Flow Summary

| Symbol | Data path |
|--------|-----------|
| **XLK, XLF** | Tradier `get_quotes()` in G18 → `live_data.json` → `update_with_real_data()` → widget |
| **TNX** | FRED via S07 `_update_fred_metrics()` emits `YIELD_10Y` → `_S07_METRIC_ROUTING["YIELD_10Y"] → ("TNX", 1.0)` → `_on_custom_metrics_updated()` → widget |
| **RVOL** | SPY `volume`/`average_volume` from Tradier quote in G18, divided by session fraction → `"RVOL"` in `live_data.json` → `update_with_real_data()` → widget |
| **$VOLD** | TradingView USI:VOLD scraped by S11 → S07 `_update_tv_breadth_metrics()` emits `VOLD` → `_S07_METRIC_ROUTING["VOLD"] → ("$VOLD", 1.0)` → `_on_custom_metrics_updated()` → widget |
