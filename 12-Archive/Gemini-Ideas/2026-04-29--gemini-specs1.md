# Master Specification: Spyder v1.0 Lean Autonomous Architecture
**Date:** April 29, 2026
**Target Platform:** Ubuntu / Wayland / Python / PySide6

**Agent Directive:** This document supersedes all previous complex feature integrations. You are to refactor the current codebase to match this strict, deterministic, "Minimum Viable Signal Set" architecture. Remove or comment out any conflicting logic.

## 1. System Philosophy & Architecture Core
* **The Prime Rule:** The system must be more eager to stop trading than to trade.
* **Decoupling:** The PySide6 application acts ONLY as an observability dashboard. The trading logic (`SpyderA02_TradingEngine.py`, `SpyderD31_StrategyOrchestrator.py`) runs headless and does not depend on the UI thread.
* **Determinism:** For v1.0, all AutoAgents (`Y-series`, `X-series`) are forced into **OBSERVE-ONLY** mode. They may log telemetry, but the Orchestrator (`D31`) MUST ignore all agent vetoes and advisory flags to ensure mathematically traceable backtesting.

## 2. The Minimum Viable Data Payload
**AGENT DIRECTIVE:** Strip out all market internals (e.g., `$TICK`, `$ADD`, `NYMO`), redundant indices (`QQQ`, `IWM`), and opaque custom metrics (`DIX`, `GEX`) from the autonomous routing layer.

The Strategy Engine is ONLY permitted to consume:
1. **SPY Price Data:** OHLCV (Trend, Realized Volatility).
2. **VIX Price Data:** OHLCV (Base volatility regime).
3. **VIX Term Structure:** `VIX9D`, `VXV` (Crisis/backwardation detection).
4. **Macro/Rates:** `TNX` (10-year yield) and `DXY` (Dollar Index).
5. **Option Chain Analytics:** `IVR`, `ATM_IV`, `VRP`, Bid/Ask, and core Greeks (Delta, Gamma, Theta).

## 3. The 6-Regime Master Logic & Strategy Mapping
**AGENT DIRECTIVE:** Update `SpyderL09_UnifiedRegimeEngine.py` and `SpyderD30_RegimeGatedSelector.py` to use ONLY the following deterministic logic for regime classification and strategy gating.

| Regime | Mathematical Trigger Logic | Permitted Strategy (`D31`) |
| :--- | :--- | :--- |
| **1. Bull Trend** | SPY > 50-EMA **AND** VIX < 50-EMA | `SpyderD06_BullPutSpread` |
| **2. Bear Trend** | SPY < 50-EMA **AND** VIX > 50-EMA | `SpyderD07_BearCallSpread` |
| **3. Range / Calm** | SPY within ATR bands **AND** VIX Contango | `SpyderD02_IronCondor` |
| **4. High-Vol Mean Rev.** | SPY ATR Elevated **AND** VIX > 80th PCTL | `SpyderD10_IronButterfly` |
| **5. Crisis / Turbulent** | `VIX9D` > `VIX` (Term Structure Inversion) | **HARD HALT / KILL-SWITCH** |
| **6. Event / Transition** | Calendar Proximity (e.g., ±30 mins of FOMC) | **HARD HALT / NO TRADE** |

## 4. Execution & Concurrency Caps
**AGENT DIRECTIVE:** Modify `SpyderD31_StrategyOrchestrator.py` and configuration defaults to strictly limit exposure.
* Set `SPYDER_MAX_CONCURRENT_STRATEGIES = 2` (Down from 8).
* Set `SPYDER_MAX_ACTIVE_HORIZON_BUCKETS = 1` (Enforce short/intraday bucket only).

## 5. P0 Safety Gates (Implementation Required)
**AGENT DIRECTIVE:** Implement the following Hard Trust-Gates in `SpyderF09_EntryFilters.py` and `SpyderB02_OrderManager.py`. If any condition fails, the trade is dropped.

### Config Schema:
```json
{
  "autonomous_readiness": {
    "liquidity": {
      "max_spread_pct": 0.12,
      "max_spread_abs": 0.20,
      "max_quote_age_ms": 1500,
      "min_open_interest": 500,
      "min_volume": 50
    },
    "execution": {
      "max_slippage_bps": 25,
      "max_fill_latency_ms": 2500,
      "halt_on_quality_breach": true
    },
    "event_clock": {
      "enabled": true,
      "blackout_pre_minutes": 30,
      "blackout_post_minutes": 30
    }
  }
}