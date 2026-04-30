# 2026-04-29 Real-Time Simulation Report

## Purpose

This report summarizes how Spyder currently performs real-time paper simulation using live market data, simulated execution, internal trade recording, and optional deferred sandbox replay.

## High-Level Model

Spyder uses a split-plane paper architecture:

1. Data plane is real-time Tradier market data (quotes and option chains).
2. Execution plane is simulated locally (no immediate broker order placement).
3. Accounting plane records trade outcomes in paper harness/session storage.
4. Optional replay plane posts deferred close-leg orders to Tradier sandbox later.

This gives realistic signal timing and option pricing behavior while keeping live money risk at zero.

## Runtime Flow

### 1) Launcher and Session Lifecycle

- The paper launcher starts and controls session lifecycle.
- It creates the paper harness and, when enabled, attaches the autonomous strategy runner.
- During session heartbeats it runs:
  - drawdown checks,
  - equity updates,
  - strategy tick loop.

Primary module:
- Spyder/SpyderQ_Scripts/SpyderQ93_RunPaper.py

### 2) Market Data Source (Real-Time)

- The strategy runner uses Tradier as a read-only data client.
- It pulls live SPY and VIX quote context and option chain data.
- In paper mode, this is used for decisioning and simulated fill pricing.

Primary module:
- Spyder/SpyderR_Runtime/SpyderR11_PaperStrategyRunner.py

### 3) Simulated Order/Fill Engine

- Entries and exits are generated from strategy adapters (Bull Put and 0DTE Iron Condor by default).
- Fills are simulated locally from quote-derived mid prices with slippage modeling.
- No Tradier place_order path is used for immediate execution in this flow.

Primary module:
- Spyder/SpyderR_Runtime/SpyderR11_PaperStrategyRunner.py

### 4) Paper Trade Recording

- Every simulated open/close updates harness trade counters and PnL state.
- Session-level snapshots and alerts are persisted in paper-trading storage.

Primary modules:
- Spyder/SpyderR_Runtime/SpyderR06_PaperTradingHarness.py
- Spyder/SpyderH_Storage/SpyderH05_TradingSessionDB.py

## Deferred Sandbox Replay (New)

A deferred replay path is now implemented so simulated trades can be mirrored to sandbox later:

1. On simulated close, each leg is queued as a pending replay order.
2. Queue is persisted to disk (JSON queue file).
3. On session-end flush, pending records are submitted to Tradier sandbox with idempotent tags.
4. Replay results are written to a reconciliation report (sent/failed/pending counts).

Primary module:
- Spyder/SpyderR_Runtime/SpyderR16_PaperSandboxReplay.py

Wiring points:
- Enqueue on close: Spyder/SpyderR_Runtime/SpyderR11_PaperStrategyRunner.py
- End-of-session flush/report log: Spyder/SpyderQ_Scripts/SpyderQ93_RunPaper.py

## Safety and Controls

- Launcher blocks accidental live-trading mode for paper script runs.
- Strategy runner preflight enforces paper/sandbox mode unless explicit live confirmation is set.
- Deferred replay refuses non-sandbox replay environments.
- Replay is feature-flagged and disabled by default.

Replay enable flag:
- SPYDER_DEFERRED_SANDBOX_REPLAY_ENABLED=true

## Current Outcome

The current behavior matches the intended model:

- Real-time data and strategy timing are preserved.
- Execution remains simulated-first and locally auditable.
- Trade lifecycle is recorded internally during paper sessions.
- Sandbox posting is optional, deferred, and report-backed for reconciliation.
