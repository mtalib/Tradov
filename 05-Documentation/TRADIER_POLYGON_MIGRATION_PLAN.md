# Spyder Migration Plan: IBKR Web API → Tradier + Polygon

**Migration Type:** Major architectural change
**Estimated Effort:** 10-14 business days
**Risk Level:** Medium (significant code changes, but clear separation of concerns)
**Target Date:** Start immediately
**Author:** Claude (Maestro)
**Created:** 2025-11-18

---

## Executive Summary

This document outlines the complete migration plan for transitioning the Spyder trading system from IBKR Client Portal Web API to a hybrid Tradier (execution) + Polygon.io (market data) architecture.

### Key Benefits
- **40% code reduction**: Remove complex OAuth, session management, rate limiting
- **No session timeouts**: Stateless REST API eliminates auto-tickle
- **Better data quality**: SIP-consolidated, <50ms latency WebSocket streaming
- **$0 commissions**: Commission-free equity/ETF options on Tradier
- **Simpler architecture**: Modern REST/WebSocket APIs, excellent documentation

### Cost Comparison
| Provider | Current (IBKR) | New (Tradier+Polygon) |
|----------|----------------|----------------------|
| Base Fee | $0 | $10/month (Tradier Pro) |
| Commissions | ~$0.65/contract | $0 (equity/ETF options) |
| Data Feed | Included (limited) | $200/month (Polygon real-time) |
| **Monthly Cost** | Variable (commission-based) | **$210/month flat** |

---

## 1. Current Architecture Analysis

### 1.1 IBKR Integration Components (To Be Removed/Replaced)

#### ClientPortalAPI Modules (9 modules - DELETE ALL)
```
SpyderB_Broker/ClientPortalAPI/
├── SpyderB09_ClientPortal_Auth.py              ❌ DELETE (OAuth complexity)
├── SpyderB09_ClientPortal_Session.py           ❌ DELETE (session management)
├── SpyderB09_ClientPortal_RateLimiter.py       ❌ DELETE (adaptive rate limiting)
├── SpyderB09_ClientPortal_RESTClient.py        ❌ REPLACE with TradierClient
├── SpyderB09_ClientPortal_WebSocket.py         ❌ DELETE (not needed)
├── SpyderB09_ClientPortal_MarketData.py        ❌ REPLACE with Polygon handler
├── SpyderB09_ClientPortal_OrderManagement.py   ❌ REPLACE with Tradier orders
└── SpyderB09_ClientPortal_Examples.py          ❌ DELETE (examples)
```

#### Supporting Modules (To Be Modified/Removed)
```
SpyderB_Broker/
├── SpyderB03_IBKRAuthManager.py                ❌ DELETE (OAuth manager)
├── SpyderB09_IBClientPortal.py                 ❌ DELETE (main IBKR interface)
├── SpyderB27_IBDataConnector.py                ❌ DELETE (IBKR data connector)
├── SpyderB28_IBKRConnectionTester.py           ❌ DELETE (connection testing)
├── SpyderB29_EnhancedConnectionManager.py      ❌ DELETE (complex connection logic)
├── SpyderB30_IBConnectionPool.py               ❌ DELETE (connection pooling)
├── SpyderB32_IBKRSessionManager.py             ❌ DELETE (session management)
├── SpyderB33_IBKRMarketDataManager.py          ❌ REPLACE with Polygon handler
├── SpyderB34_IBKRConfigManager.py              ⚠️  MODIFY (config for Tradier/Polygon)
└── SpyderB36_IBKROrderManager.py               ❌ REPLACE with Tradier order manager
```

#### Market Data Modules (To Be Modified)
```
SpyderC_MarketData/
├── SpyderC01_DataFeed.py                       ⚠️  MODIFY (change data source)
├── SpyderC02_MarketDataFeed.py                 ⚠️  MODIFY (Polygon integration)
├── SpyderC20_MarketDataHub.py                  ⚠️  MODIFY (new data hub)
└── SpyderC16_MarketDataCache.py                ✅ KEEP (data agnostic)
```

### 1.2 Dependencies Analysis

**Current IBKR Dependencies:**
- OAuth authentication flow
- Session management (auto-tickle every 4 minutes)
- Rate limiter (50 req/sec OAuth, 100 req/sec CP Gateway)
- Connection pooling
- RSA key pair management
- JWT token creation/validation

**New Tradier + Polygon Dependencies:**
- Simple Bearer token authentication
- WebSocket client (websocket-client library)
- No session management needed
- No rate limiting (generous limits)
- Standard HTTP requests library

---

## 2. New Architecture Design

### 2.1 Module Structure

```
SpyderB_Broker/
├── SpyderB40_TradierClient.py          ✨ NEW - Simple REST client for Tradier
├── SpyderB41_TradierOrderManager.py    ✨ NEW - Order placement and management
├── SpyderB42_TradierAccountManager.py  ✨ NEW - Account/position management
└── SpyderB43_TradierConfig.py          ✨ NEW - Tradier configuration

SpyderC_MarketData/
├── SpyderC25_PolygonDataHandler.py     ✨ NEW - WebSocket streaming from Polygon
├── SpyderC26_PolygonRESTAPI.py         ✨ NEW - Polygon REST API (historical data)
└── SpyderC27_PolygonConfig.py          ✨ NEW - Polygon configuration

SpyderT_Testing/
├── SpyderT40_TradierClient_Test.py     ✨ NEW - Unit tests for Tradier
├── SpyderT41_PolygonHandler_Test.py    ✨ NEW - Unit tests for Polygon
└── SpyderT42_Integration_Test.py       ✨ NEW - End-to-end integration test
```

### 2.2 Data Flow Diagram

**OLD (IBKR):**
```
IBKR OAuth → Session Manager → Rate Limiter → REST/WebSocket →
Auto-Tickle → MarketData/Orders → Strategy Engine
```

**NEW (Tradier + Polygon):**
```
┌──────────────────────────────────────────────────────────┐
│                   SPYDER SYSTEM                           │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  ┌────────────────────────┐  ┌─────────────────────────┐ │
│  │  Polygon WebSocket     │  │  Tradier REST API       │ │
│  │  (Market Data)         │  │  (Order Execution)      │ │
│  └──────────┬─────────────┘  └──────────┬──────────────┘ │
│             │                            │                 │
│             ▼                            ▼                 │
│  ┌──────────────────────┐  ┌─────────────────────────┐  │
│  │ PolygonDataHandler   │  │  TradierClient          │  │
│  │ (SpyderC25)          │  │  (SpyderB40)            │  │
│  └──────────┬───────────┘  └──────────┬──────────────┘  │
│             │                          │                  │
│             │                          │                  │
│             ▼                          ▼                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │         MarketDataHub (SpyderC20)                 │   │
│  │         - Real-time quotes                        │   │
│  │         - Trade data                              │   │
│  │         - Aggregates (1s, 1m, 5m)                │   │
│  └──────────────────┬───────────────────────────────┘   │
│                     │                                     │
│                     ▼                                     │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Strategy Engine (SpyderD)                 │   │
│  │         - Analyzes market data                    │   │
│  │         - Generates trade signals                 │   │
│  └──────────────────┬───────────────────────────────┘   │
│                     │                                     │
│                     ▼                                     │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Risk Manager (SpyderE)                    │   │
│  │         - Validates signals                       │   │
│  │         - Position sizing                         │   │
│  └──────────────────┬───────────────────────────────┘   │
│                     │                                     │
│                     ▼                                     │
│  ┌──────────────────────────────────────────────────┐   │
│  │         TradierOrderManager (SpyderB41)           │   │
│  │         - Places orders via Tradier API          │   │
│  │         - Tracks order status                     │   │
│  └───────────────────────────────────────────────────┘  │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 2.3 Configuration Changes

**OLD (.env):**
```bash
# IBKR OAuth Configuration
IBKR_CONSUMER_KEY=xxxxxxxxxxxxxx
IBKR_PRIVATE_KEY_PATH=/path/to/private_key.pem
IBKR_ACCOUNT_ID=U1234567
IBKR_API_URL=https://api.ibkr.com/v1
IBKR_AUTH_METHOD=oauth
TRADING_MODE=paper
```

**NEW (.env):**
```bash
# Tradier Configuration
TRADIER_API_KEY=your_access_token_here
TRADIER_ACCOUNT_ID=your_account_id_here
TRADIER_BASE_URL=https://api.tradier.com/v1
TRADIER_SANDBOX_URL=https://sandbox.tradier.com/v1
TRADING_MODE=paper  # paper or live

# Polygon Configuration
POLYGON_API_KEY=your_polygon_api_key_here
POLYGON_WS_URL=wss://socket.polygon.io/stocks
POLYGON_REST_URL=https://api.polygon.io
```

---

## 3. Detailed Implementation Plan

### Phase 1: Setup & Configuration (Day 1-2)

#### Day 1: Account Setup
- [ ] Sign up for Tradier Pro account ($10/month)
  - URL: https://brokerage.tradier.com/signup
  - Enable API access in account settings
  - Generate API access token (sandbox + live)
  - Note account ID

- [ ] Sign up for Polygon.io real-time plan ($200/month)
  - URL: https://polygon.io/pricing
  - Choose "Starter" plan with real-time WebSocket access
  - Generate API key
  - Test API access with curl

- [ ] Verify API credentials
  ```bash
  # Test Tradier
  curl -H "Authorization: Bearer YOUR_TOKEN" \
    https://sandbox.tradier.com/v1/user/profile

  # Test Polygon
  curl "https://api.polygon.io/v2/aggs/ticker/SPY/prev?apiKey=YOUR_KEY"
  ```

#### Day 2: Configuration Management
- [ ] Update `.env.template` with Tradier/Polygon variables
- [ ] Create `config/tradier_config.py`
- [ ] Create `config/polygon_config.py`
- [ ] Update `config/config.py` to load new providers
- [ ] Create validation script: `SpyderQ_Scripts/validate_tradier_polygon.py`

### Phase 2: Build Core Modules (Day 3-5)

#### Day 3: Tradier Client Module
- [ ] Create `SpyderB40_TradierClient.py`
  - Simple Bearer token authentication
  - GET/POST methods for Tradier API
  - Error handling for HTTP status codes
  - Connection pooling (requests.Session)
  - Logging integration

- [ ] Create `SpyderB41_TradierOrderManager.py`
  - place_order() - market, limit, stop orders
  - cancel_order() - cancel pending orders
  - get_order_status() - track order lifecycle
  - Error handling and retry logic

- [ ] Create `SpyderB42_TradierAccountManager.py`
  - get_profile() - user profile
  - get_balances() - account balances
  - get_positions() - current positions
  - get_history() - trade history

#### Day 4: Polygon Data Handler Module
- [ ] Create `SpyderC25_PolygonDataHandler.py`
  - WebSocket connection to Polygon
  - Authentication via API key
  - Subscribe to trade/quote streams for SPY
  - Message parsing and normalization
  - Qt Signal/Slot integration for thread safety
  - Automatic reconnection logic

- [ ] Create `SpyderC26_PolygonRESTAPI.py`
  - Historical data retrieval (aggregates)
  - Snapshots (current prices)
  - Options chain data
  - Rate limiting (5 req/sec free tier)

#### Day 5: Integration with Existing Modules
- [ ] Modify `SpyderC01_DataFeed.py`
  - Add Polygon as new DataSource enum
  - Route market data through PolygonDataHandler
  - Maintain backward compatibility

- [ ] Modify `SpyderC20_MarketDataHub.py`
  - Accept data from Polygon format
  - Normalize data structure
  - Emit events to strategy engine

- [ ] Update `SpyderB02_OrderManager.py`
  - Route orders to TradierOrderManager
  - Handle Tradier-specific order responses

### Phase 3: Testing Infrastructure (Day 6-7)

#### Day 6: Unit Tests
- [ ] Create `SpyderT40_TradierClient_Test.py`
  - Test authentication
  - Test order placement (sandbox)
  - Test account queries
  - Test error handling

- [ ] Create `SpyderT41_PolygonHandler_Test.py`
  - Test WebSocket connection
  - Test data parsing
  - Test reconnection logic
  - Test signal emission

#### Day 7: Integration Tests
- [ ] Create `SpyderT42_Integration_Test.py`
  - End-to-end data flow test
  - Polygon data → Strategy → Tradier execution
  - Verify latency < 100ms
  - Test paper trading workflow

- [ ] Run existing test suite
  - Fix broken tests due to IBKR removal
  - Update mock objects for new architecture

### Phase 4: Migration Execution (Day 8-10)

#### Day 8: Archive IBKR Modules
- [ ] Create backup branch: `archive/ibkr-web-api`
- [ ] Move IBKR modules to `ARCHIVED/` folder
- [ ] Delete ClientPortalAPI/ directory
- [ ] Remove IBKR-specific dependencies from requirements.txt
- [ ] Update .gitignore if needed

#### Day 9: Configuration Migration
- [ ] Update `.env` with Tradier/Polygon credentials
- [ ] Remove IBKR OAuth keys and certificates
- [ ] Run validation: `python SpyderQ_Scripts/validate_tradier_polygon.py`
- [ ] Test configuration loading

#### Day 10: Integration and Testing
- [ ] Run full test suite
- [ ] Test paper trading end-to-end
- [ ] Monitor logs for errors
- [ ] Benchmark latency and performance
- [ ] Verify data quality (compare with IBKR historical)

### Phase 5: Deployment & Monitoring (Day 11-14)

#### Day 11: Paper Trading Validation
- [ ] Run paper trading for full trading day
- [ ] Monitor order execution times
- [ ] Verify data accuracy (Polygon vs actual fills)
- [ ] Check for any gaps in data stream
- [ ] Validate strategy behavior

#### Day 12: Performance Optimization
- [ ] Profile code for bottlenecks
- [ ] Optimize WebSocket message processing
- [ ] Tune buffer sizes and polling intervals
- [ ] Test under high-frequency scenarios

#### Day 13: Documentation
- [ ] Update README.md with new architecture
- [ ] Document Tradier API integration
- [ ] Document Polygon API integration
- [ ] Create troubleshooting guide
- [ ] Update QUICK_START.md

#### Day 14: Final Validation & Go-Live Decision
- [ ] Review all test results
- [ ] Validate with small live trades (if approved)
- [ ] Create rollback plan if needed
- [ ] Final sign-off from stakeholders
- [ ] Switch to live trading (or remain in paper mode)

---

## 4. Risk Analysis & Mitigation

### Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Data format incompatibility** | Medium | High | Build robust data normalization layer |
| **Polygon WebSocket disconnection** | Low | High | Implement auto-reconnect with exponential backoff |
| **Tradier API downtime** | Low | High | Implement retry logic, monitor status page |
| **Missing features in Tradier** | Medium | Medium | Validate feature parity before migration |
| **Performance degradation** | Low | Medium | Benchmark before/after, optimize as needed |
| **Strategy behaves differently** | Medium | High | Extensive paper trading before live |

### Rollback Plan

If critical issues arise:

1. **Immediate Rollback** (within 24 hours):
   - Restore from `archive/ibkr-web-api` branch
   - Revert configuration changes
   - Resume IBKR connection

2. **Gradual Rollback** (1-7 days):
   - Run Tradier+Polygon in parallel with IBKR
   - Compare results
   - Switch back if Tradier underperforms

3. **Permanent Rollback** (>7 days):
   - Document issues encountered
   - Re-evaluate alternative solutions
   - Keep Tradier codebase for future attempts

---

## 5. Code Deletion Checklist

### Files to DELETE

```
✅ SpyderB_Broker/ClientPortalAPI/                    (entire directory)
✅ SpyderB_Broker/SpyderB03_IBKRAuthManager.py
✅ SpyderB_Broker/SpyderB09_IBClientPortal.py
✅ SpyderB_Broker/SpyderB27_IBDataConnector.py
✅ SpyderB_Broker/SpyderB28_IBKRConnectionTester.py
✅ SpyderB_Broker/SpyderB29_EnhancedConnectionManager.py
✅ SpyderB_Broker/SpyderB30_IBConnectionPool.py
✅ SpyderB_Broker/SpyderB32_IBKRSessionManager.py
✅ SpyderB_Broker/SpyderB33_IBKRMarketDataManager.py
✅ SpyderB_Broker/SpyderB36_IBKROrderManager.py
✅ SpyderQ_Scripts/validate_env.py                    (IBKR OAuth validation)
✅ SpyderT_Testing/SpyderT23_ClientPortal_Auth_Test.py
✅ SpyderT_Testing/SpyderT24_ClientPortal_RateLimiter_Test.py
✅ SpyderT_Testing/SpyderT25_ClientPortal_Session_Test.py
✅ SpyderT_Testing/SpyderT26_ClientPortal_RESTClient_Test.py
✅ SpyderT_Testing/SpyderT27_ClientPortal_Integration_Test.py
```

### Estimated Lines of Code Reduction

- **ClientPortalAPI modules**: ~1,500 lines
- **IBKR support modules**: ~3,000 lines
- **IBKR test modules**: ~800 lines
- **OAuth/session management**: ~600 lines

**Total LOC Reduction**: **~5,900 lines** (40% of broker/data infrastructure)

---

## 6. Success Criteria

### Functional Requirements
✅ All market data arrives via Polygon WebSocket with <100ms latency
✅ Orders execute successfully via Tradier API
✅ No session timeout issues during trading hours
✅ Strategy behavior matches IBKR baseline (backtesting comparison)
✅ All existing tests pass with new architecture

### Performance Requirements
✅ Market data latency: <50ms (Polygon → Strategy)
✅ Order execution latency: <500ms (Signal → Tradier confirmation)
✅ WebSocket uptime: >99.9% during trading hours
✅ Zero data gaps during normal market conditions

### Quality Requirements
✅ Code coverage: >80% for new modules
✅ Zero critical bugs in paper trading (7-day period)
✅ Documentation complete for all new modules
✅ Clean git history with descriptive commits

---

## 7. Post-Migration Tasks

### Week 1 After Go-Live
- [ ] Monitor daily performance metrics
- [ ] Compare execution quality (IBKR vs Tradier)
- [ ] Analyze cost savings (commissions)
- [ ] Gather user feedback on system reliability

### Month 1 After Go-Live
- [ ] Performance review and optimization
- [ ] Final cleanup of IBKR references
- [ ] Create case study document
- [ ] Share lessons learned

---

## 8. Appendix

### A. API Rate Limits

| Provider | Rate Limit | Notes |
|----------|------------|-------|
| **Tradier** | No official limit | Recommend <100 req/min to be safe |
| **Polygon (Starter)** | 5 req/sec (REST) | WebSocket has no limit |
| **Polygon (Advanced)** | Unlimited (REST) | Upgrade if needed |

### B. Data Quality Comparison

| Metric | IBKR Web API | Polygon.io |
|--------|--------------|------------|
| Latency | 100-500ms | 20-50ms |
| Tick-by-tick | Yes (limited symbols) | Yes (all US equities) |
| Aggregates | 1m, 5m, 15m, 30m, 1h | 1s, 1m, 5m, 15m, 30m, 1h, 1d |
| Historical Data | Limited | Extensive (years of data) |
| Market Data Type | Consolidated | SIP-consolidated |

### C. Cost-Benefit Analysis

**One-Time Costs:**
- Development time: ~80-100 hours @ developer rate
- Testing and validation: ~20-30 hours

**Recurring Costs:**
- Tradier Pro: $10/month
- Polygon Starter: $200/month
- **Total**: $210/month

**Cost Savings:**
- Commissions: ~$50-200/month (depends on trading volume)
- Developer maintenance: ~10-20 hours/month (simpler codebase)

**Break-even:** 1-2 months for high-frequency traders

---

## 9. Next Steps

1. **Approval to Proceed**: Get stakeholder sign-off on migration plan
2. **Create Branch**: `git checkout -b feature/tradier-polygon-migration`
3. **Setup Accounts**: Tradier Pro + Polygon.io
4. **Start Development**: Begin with Phase 1 (Setup & Configuration)

**Ready to begin migration!** 🚀

---

**Document Version**: 1.0
**Last Updated**: 2025-11-18
**Status**: READY FOR IMPLEMENTATION
