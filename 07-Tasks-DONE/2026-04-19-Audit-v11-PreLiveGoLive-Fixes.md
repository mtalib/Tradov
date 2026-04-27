# Codebase Audit v11 — Pre-Live-Go-Live Fixes

**Date Completed:** 2026-04-19  
**Source Audit:** `06-Tasks-TODO/2026-04-18-Codebase-Audit-v11-Pre-LiveGoLive-Report.md`  
**Branch:** `refactor/g05-widget-extraction`  
**Status:** All 9 P0 blockers resolved ✅

---

## Summary

All P0 (blocker) items from the Pre-Live-Go-Live audit were implemented across 8 sequential phases and verified with inline Python test scripts before each phase was marked complete. No P0 item was left open.

---

## Phase 1 — Event Infrastructure (P1-8, P1-9, P1-11)

**Files:** `SpyderA_Core/SpyderA05_EventManager.py`, `SpyderU_Utilities/SpyderU01_Logger.py`, `SpyderQ_Scripts/SpyderQ93_RunPaper.py`

| Item | Fix |
|------|-----|
| P1-11 | Added `import os` to `SpyderA05_EventManager.py` — `_allow_multiple()` referenced `os.environ` without it (latent `NameError`). |
| P1-9 | Swapped `FileHandler` → `RotatingFileHandler(maxBytes=50 MB, backupCount=10)` in `SpyderU01_Logger.py` to prevent unbounded log growth. |
| P1-8 | Added `assert os.environ.get("TRADING_MODE") in ("paper", "sandbox")` guard at the top of `SpyderQ93_RunPaper.py` to hard-fail if accidentally pointed at live mode. |

---

## Phase 2 — Market-Hours Timezone Fix (P0-11, P0-12)

**Files:** `SpyderR_Runtime/SpyderR04_LiveEngine.py`, `SpyderA_Core/SpyderA04_Scheduler.py`

| Item | Fix |
|------|-----|
| P0-11 | Replaced `datetime.now().time()` (naive, local TZ) with `datetime.now(ET).time()` where `ET = ZoneInfo("America/New_York")` in `_is_market_open()` and all related callsites in both R04 and A04. |
| P0-12 | `get_market_close()` added to `SpyderU10_TradingCalendar` and called by `_is_market_open()` — returns 13:00 ET on early-close days, 16:00 ET normally. |

---

## Phase 3 — PositionTracker Wiring (P0-5)

**Files:** `SpyderR_Runtime/SpyderR12_SessionSupervisor.py`

| Item | Fix |
|------|-----|
| P0-5 | `SessionSupervisor._start_position_tracker()` now creates a `PositionTracker` instance and wires it to `LiveEngine` via `engine.set_position_tracker()`. The tracker is registered as a component so `stop()` tears it down in the correct order. |

---

## Phase 4 — `close_position()` Protocol & Implementation (P0-3, P0-4)

**Files:** `SpyderB_Broker/SpyderB21_BrokerProtocol.py`, `SpyderB_Broker/SpyderB40_TradierClient.py`, `SpyderR_Runtime/SpyderR12_SessionSupervisor.py`

| Item | Fix |
|------|-----|
| P0-3 | Added `close_position(symbol, force=False)` abstract method to `BrokerProtocol` (B21). |
| P0-4 | Implemented `TradierClient.close_position(symbol, force=False)` in B40: queries current position via `get_positions()`, derives side (`sell` for long equity, `buy_to_close` for short options), places a market order. Returns `{}` if position is zero and `force=False`. |
| P0-4 | Added `_NullBroker.close_position()` stub returning `{"status": "null_broker"}` in R12. |
| P0-5 | `SessionSupervisor._flatten_positions()` iterates `broker.get_positions()`, normalises the Tradier envelope (single-dict vs list), skips zero-qty entries, and calls `broker.close_position(symbol)` for each live position. |

---

## Phase 5 — EMERGENCY Bridge + Strategy Pause (P0-1, P0-2, P1-1)

**Files:** `SpyderR_Runtime/SpyderR04_LiveEngine.py`, `SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py`

| Item | Fix |
|------|-----|
| P0-1 / P0-2 | Added `_on_emergency_bridge()` to `LiveEngine`. Subscribes to `EventType.EMERGENCY` (emitted by E11/E13 on catastrophic loss) and re-emits `EventType.KILL_SWITCH` so the single kill-switch handler halts all order submission regardless of which event the risk layer fires. |
| P0-2 | Kill-switch check moved **before** the `FillReconciler` guard in `_broker_submit()` — `KILL_SWITCH` raises `RuntimeError("KILL_SWITCH active")` immediately, not the reconciler error. |
| P1-1 | Added `self._paused: bool = False` to `StrategyOrchestrator.__init__`. Added `_on_kill_or_stale()` handler subscribed to both `EventType.KILL_SWITCH` and `EventType.DATA_STALE` — sets `_paused = True`. All signal-dispatch handlers return early while `_paused`. |

---

## Phase 6 — 5xx Error Escalation + Order Idempotency (P0-8, P0-9)

**Files:** `SpyderB_Broker/SpyderB40_TradierClient.py`, `SpyderR_Runtime/SpyderR04_LiveEngine.py`

| Item | Fix |
|------|-----|
| P0-8 | Wrapped `broker.place_order()` in a dedicated `try/except TradierServerError` block inside `_broker_submit()`. On success: `reset_api_error_count()`. On 5xx: `record_api_server_error()` (triggers `EMERGENCY` at `API_PANIC_THRESHOLD = 3` consecutive failures) then re-raises. Non-5xx exceptions fall through to the existing general handler and do **not** increment the counter. |
| P0-9 | Added `tag: str | None = None` parameter to `TradierClient.place_order()` and appended `payload["tag"] = tag` before the API request. In `_broker_submit()`, generates `_tag = f"spyder-{order_id}"` and passes it through — Tradier deduplicates orders with the same tag for ~24 h, preventing duplicate fills on network-timeout retries. |

---

## Phase 7 — `pending_orders` Cleanup (P0-10)

**Files:** `SpyderR_Runtime/SpyderR04_LiveEngine.py`

| Item | Fix |
|------|-----|
| P0-10 | Added `timedelta` to datetime imports. |
| P0-10 | Added `_on_order_terminal_event()` handler subscribed to `EventType.ORDER_CANCELLED`, `ORDER_EXPIRED`, and `ORDER_REJECTED` — calls `del self.pending_orders[order_id]` when the event carries a matching `order_id`. Prevents stuck state and memory leak over multi-day sessions. |
| P0-10 | Added `"submitted_at": datetime.now()` to each `pending_orders` entry at registration time. |
| P0-10 | Added `_gc_pending_orders(max_age: timedelta = timedelta(hours=24))` — evicts entries whose `submitted_at` is older than `max_age`, logging a `WARNING` for each. Called lazily at the start of `execute_order()` before each new registration. |

---

## Phase 8 — SIGTERM Flatten + Live Gate (P0-6, P0-7)

**Files:** `SpyderQ_Scripts/SpyderQ14_MainLauncher.py`

| Item | Fix |
|------|-----|
| P0-6 | Both `_run_headless_loop()` and `_request_shutdown()` now call `supervisor.stop(flatten=(args.mode == "live"))`. Live mode flattens all positions before teardown; paper mode preserves state for inspection. |
| P0-7 | Added `_live_preflight_checks()` — called inside `launch_system()` before any session objects are created when `mode == "live"`: (1) checks `LIVE_TRADING_CONFIRMED=true` env var; (2) checks `TRADIER_API_KEY` and `TRADIER_ACCOUNT_ID` are non-empty; (3) acquires an exclusive `fcntl` PID lock on `/tmp/spyder_trading.lock` — second launcher fails immediately with a clear error. |
| P0-7 | Added `_broker_preflight_check()` — called after `supervisor.start()` in live mode: calls `broker.get_account()` and hard-fails if `buying_power <= 0` or the broker is unreachable. |

---

## Files Changed

| File | Phase(s) |
|------|---------|
| `SpyderA_Core/SpyderA04_Scheduler.py` | 2 |
| `SpyderA_Core/SpyderA05_EventManager.py` | 1 |
| `SpyderB_Broker/SpyderB21_BrokerProtocol.py` | 4 |
| `SpyderB_Broker/SpyderB40_TradierClient.py` | 4, 6 |
| `SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py` | 5 |
| `SpyderQ_Scripts/SpyderQ14_MainLauncher.py` | 8 |
| `SpyderQ_Scripts/SpyderQ93_RunPaper.py` | 1 |
| `SpyderR_Runtime/SpyderR04_LiveEngine.py` | 2, 5, 6, 7 |
| `SpyderR_Runtime/SpyderR12_SessionSupervisor.py` | 3, 4 |
| `SpyderU_Utilities/SpyderU01_Logger.py` | 1 |
| `SpyderU_Utilities/SpyderU10_TradingCalendar.py` | 2 |
