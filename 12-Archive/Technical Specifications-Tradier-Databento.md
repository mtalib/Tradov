# Technical Specifications: Tradier API & Databento Integration

> **Original**: Pre-migration reference spec (2025)
> **Updated**: 2026-02-26 — Gap analysis against implemented Spyder modules

---

## Implementation Status Assessment

The original spec described a standalone trading system built from scratch. Spyder's
existing module architecture has **absorbed the vast majority** of this spec's
requirements into its 24-module series. Below is a mapping of spec sections to
the implementing Spyder modules, followed by remaining gaps.

### Coverage Summary

| Spec Section | Spyder Module(s) | Status |
|---|---|---|
| Tradier REST client | SpyderB40_TradierClient | **Complete** |
| Tradier streaming (SSE) | SpyderB40 (TradierAccountStream) | **Complete** |
| Tradier auth & rate limiting | SpyderU40_RateLimiter, SpyderU41_CircuitBreaker | **Complete** |
| Tradier account balance | B40 `get_account_balance()` | **Complete** |
| Tradier positions | B40 `get_positions()` | **Complete** |
| Tradier order placement | B40 `place_order()`, `place_multileg_order()` | **Complete** |
| Tradier multileg (spreads, IC) | B40 `place_iron_condor()`, `place_credit_spread()` | **Complete** |
| Tradier option chains | B40 `get_option_chain()` with Greeks parsing | **Complete** |
| Tradier option symbol builder | B40 `build_option_symbol()` | **Complete** |
| Databento historical client | SpyderC26_DatabentoClient | **Complete** |
| Databento live streaming | C26 live streaming with async iteration | **Complete** |
| Databento OPRA options | C26 defaults to OPRA.PILLAR dataset | **Complete** |
| Databento nanosecond timestamps | C26 native DBN format handling | **Complete** |
| Databento schema support | C26 MBO, MBP-1, MBP-10, TBBO, OHLCV, trades, definition | **Complete** |
| Data Manager (central hub) | SpyderC01_DataFeed, SpyderI02_EventRouter | **Complete** |
| Qt Signal integration | C26 has PySide6 Signal/Slot integration | **Complete** |
| Options chain UI widget | SpyderG_GUI (options chain display) | **Complete** |
| Real-time chart widget | SpyderG_GUI (charting with pyqtgraph) | **Complete** |
| Account view widget | SpyderG05 dashboard panels | **Complete** |
| Order entry widget | SpyderG_GUI order entry | **Complete** |
| Main window layout | SpyderG05 main dashboard | **Complete** |
| Strategy framework | SpyderD_Strategies (29 strategies) | **Complete** |
| Greeks calculation | SpyderN_OptionsAnalytics, B40 Greeks parsing | **Complete** |
| Configuration / .env | config/config.py, .env | **Complete** |
| Logging | SpyderU01_Logger (not loguru — uses SpyderLogger) | **Complete** |
| Wayland compatibility | PySide6 with QT_QPA_PLATFORM detection | **Partial** |

### Remaining Gaps

| Gap | Priority | Notes |
|---|---|---|
| Position reconciliation | **High** | B40 has `get_positions()` but no automated reconciliation loop comparing broker positions vs. internal state |
| Databento → Tradier symbol mapping | **Medium** | C26 has OSI ↔ Tradier conversion but needs integration test coverage |
| Unified options chain (Tradier chain + Databento real-time) | **Medium** | Spec's `get_current_option_chain()` that merges Tradier definitions with Databento live prices — not fully wired |
| WebSocket reconnection stress test | **Medium** | C26 has reconnection logic but needs real-world validation under network failures |
| Databento bandwidth cost tracking | **Low** | C26 has cost tracking stubs but no dashboard integration |
| Order entry → strategy signal pipeline | **Low** | Manual order entry in GUI exists but strategy → order routing needs live engine (R03) |

---

## Original Spec Reference

The sections below preserve the original spec for reference. Implementation details
are documented in the module files themselves:

- **Tradier Client**: [SpyderB40_TradierClient.py](../Spyder/SpyderB_Broker/SpyderB40_TradierClient.py)
  - REST API: account balance, positions, orders, option chains, expirations, strikes
  - Multileg orders: Iron Condors, credit/debit spreads
  - SSE streaming: TradierAccountStream for real-time fills
  - Option symbol utilities: build/parse OCC format
  - Delta-based strike selection
  - Async wrappers with rate limiting and circuit breaker

- **Databento Client**: [SpyderC26_DatabentoClient.py](../Spyder/SpyderC_MarketData/SpyderC26_DatabentoClient.py)
  - Live streaming via `databento.Live` with async iteration
  - Historical data via `databento.Historical` REST API
  - OPRA.PILLAR dataset for options
  - Multiple schemas: MBO (L3), MBP-1 (L1), MBP-10 (L2), TBBO, OHLCV
  - Nanosecond timestamp handling (native DBN format)
  - Qt Signal/Slot integration for thread-safe UI communication
  - Automatic reconnection with exponential backoff

---

## Gap Implementation Plan

### 1. Position Reconciliation (High Priority)

**Module**: SpyderB40_TradierClient or new SpyderB41_PositionReconciler

```python
class PositionReconciler:
    """
    Periodically reconciles internal position state with Tradier broker.
    
    Detects:
    - Orphaned positions (in broker but not tracked internally)
    - Ghost positions (tracked internally but not in broker)
    - Quantity mismatches
    - Fill notifications missed during disconnects
    """
    
    def reconcile(self) -> ReconciliationReport:
        """Compare internal positions vs. broker positions."""
        broker_positions = self.tradier.get_positions()
        internal_positions = self.portfolio_manager.get_all_positions()
        # ... diff logic ...
```

**Timeline**: Phase 1 (March 2026)

### 2. Unified Options Chain (Medium Priority)

**Module**: SpyderC_MarketData or SpyderN_OptionsAnalytics

```python
def get_live_option_chain(underlying: str = "SPY") -> pd.DataFrame:
    """
    Merge Tradier option chain definitions with Databento real-time prices.
    
    - Tradier provides: strikes, expirations, Greeks, OI, volume
    - Databento provides: real-time bid/ask/last with sub-ms latency
    - Returns: Combined DataFrame with best-of-both data
    """
```

**Timeline**: Phase 1 (April 2026)

### 3. Symbol Mapping Integration Tests (Medium Priority)

**Module**: SpyderT_Testing

```python
def test_databento_to_tradier_symbol_conversion():
    """Verify OSI ↔ Tradier symbol mapping for edge cases."""
    # Weekly expirations, adjusted strikes, mini options, etc.
```

**Timeline**: Phase 1 (March 2026)

---

## Dependencies

All dependencies from the original spec are satisfied:

```
# Already in requirements-trading.txt / requirements-core.txt
databento>=0.44.0         # Market data SDK
requests>=2.31.0          # Tradier REST API
pyside6>=6.6.0            # GUI framework
pandas>=2.0.0             # Data manipulation
numpy>=1.24.0             # Numerical computation
pyarrow>=12.0.0           # Columnar data (Databento)

# Already in requirements-analysis.txt
scipy>=1.11.0             # Quantitative methods

# Already in requirements-dev.txt
pytest>=7.0.0             # Testing framework
```

## Configuration

All configuration is centralized in:

- `.env` — API keys and secrets (gitignored)
- `config/config.py` — System settings, thresholds, feature flags
- Environment variables: `TRADIER_API_KEY`, `TRADIER_ACCOUNT_ID`,
  `TRADIER_ENVIRONMENT`, `DATABENTO_API_KEY`
