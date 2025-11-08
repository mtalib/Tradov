# IBKR Client Portal Web API Wrapper Architecture

## Executive Summary

This document outlines the architecture for implementing IBKR's Client Portal Web API in the SPYDER trading system. The design maintains compatibility with existing SPYDER modules while leveraging IBKR's native API capabilities.

**Key Architecture Features:**
- IBKR Client Portal: HTTP REST API with local gateway, session-based authentication

**Architecture Goals:**
1. Maintain existing SPYDER module interfaces
2. Provide robust session management for IBKR's manual authentication
3. Implement efficient market data handling
4. Ensure seamless order management
5. Create comprehensive error handling and reconnection logic

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│              SPYDER Trading System                       │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │           IBKR API Wrapper                        │  │
│  │                                                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │  │
│  │  │Session      │  │Order        │  │Market     │ │  │
│  │  │Manager      │  │Manager      │  │Data       │ │  │
│  │  │             │  │             │  │Manager    │ │  │
│  │  └─────────────┘  └─────────────┘  └───────────┘ │  │
│  │                                                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │  │
│  │  │Message      │  │Config       │  │Health     │ │  │
│  │  │Translator   │  │Manager      │  │Monitor    │ │  │
│  │  │             │  │             │  │           │ │  │
│  │  └─────────────┘  └─────────────┘  └───────────┘ │  │
│  └───────────────────┬───────────────────────────────┘  │
└──────────────────────┼───────────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────┐
│   IBKR Client Portal Gateway          │
│   (Local Java Application)            │
│                                       │
│  • HTTPS REST API                     │
│  • Session Management                 │
│  • Manual Browser Authentication      │
│  • Local Port 5000                    │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│   Interactive Brokers Backend         │
└───────────────────────────────────────┘
```

---

## 2. Core Components

### 2.1. SessionManager

**Purpose**: Handle IBKR's session management and authentication flow

**Key Responsibilities**:
- Monitor gateway availability
- Track authentication status
- Manage session lifecycle
- Handle re-authentication prompts
- Maintain session health with tickle requests

**Key Features**:
```python
class SessionManager:
    def check_auth_status() -> bool
    def is_gateway_available() -> bool
    def send_tickle() -> bool
    def get_session_info() -> Dict
    def monitor_session_health() -> None
```

### 2.2. OrderManager

**Purpose**: Handle all order operations with IBKR API

**Key Responsibilities**:
- Place orders (equities, options, multi-leg)
- Cancel and modify orders
- Track order status
- Handle order validations
- Manage order history

**Key Features**:
```python
class OrderManager:
    def place_order(order_request) -> str
    def cancel_order(order_id) -> bool
    def modify_order(order_id, modifications) -> bool
    def get_order_status(order_id) -> Dict
    def get_open_orders() -> List[Dict]
    def validate_order(order_request) -> Dict
```

### 2.3. MarketDataManager

**Purpose**: Manage market data retrieval and caching

**Key Responsibilities**:
- Request market data snapshots
- Manage subscription limits
- Cache market data
- Handle real-time updates via webhook
- Provide historical data

**Key Features**:
```python
class MarketDataManager:
    def get_market_snapshot(symbols, fields) -> Dict
    def subscribe_realtime(symbols, callback) -> bool
    def get_historical_data(symbol, period, bar_size) -> List
    def search_contracts(symbol) -> List[Dict]
    def get_option_chain(symbol, expiration) -> Dict
```

### 2.4. MessageTranslator

**Purpose**: Convert between IBKR API format and SPYDER format

**Key Responsibilities**:
- Translate market data messages
- Convert order status updates
- Map position information
- Transform account summaries
- Handle timestamp conversions

**Key Features**:
```python
class MessageTranslator:
    def market_data_to_spyder(ibkr_data) -> MarketDataTick
    def order_to_spyder(ibkr_order) -> Order
    def position_to_spyder(ibkr_position) -> Position
    def account_to_spyder(ibkr_account) -> AccountSummary
```

### 2.5. ConfigManager

**Purpose**: Manage configuration and environment settings

**Key Responsibilities**:
- Load and validate configuration
- Manage environment variables
- Handle account settings
- Store API preferences
- Control feature flags

**Key Features**:
```python
class ConfigManager:
    def get_gateway_config() -> Dict
    def get_account_config() -> Dict
    def get_market_data_config() -> Dict
    def is_production_mode() -> bool
    def update_config(key, value) -> bool
```

### 2.6. HealthMonitor

**Purpose**: Monitor system health and performance

**Key Responsibilities**:
- Track API response times
- Monitor error rates
- Check gateway connectivity
- Alert on system issues
- Generate health reports

**Key Features**:
```python
class HealthMonitor:
    def check_gateway_health() -> Dict
    def get_api_metrics() -> Dict
    def get_error_statistics() -> Dict
    def generate_health_report() -> Dict
    def set_health_alerts(callbacks) -> None
```

---

## 3. Data Flow Architecture

### 3.1. Authentication Flow

```
1. SPYDER Startup
    ↓
2. Check Gateway Availability (SessionManager)
    ↓
3. Check Authentication Status
    ↓
4. If Not Authenticated → Prompt User
    ↓
5. User Logs In via Browser
    ↓
6. Monitor Session Health
    ↓
7. Start Background Tickle Loop
```

### 3.2. Order Execution Flow

```
1. Strategy Creates Order Request
    ↓
2. Order Manager Validates Request
    ↓
3. Translate to IBKR Format
    ↓
4. Send to IBKR Gateway
    ↓
5. Receive Confirmation
    ↓
6. Update Order Status
    ↓
7. Notify Strategy
```

### 3.3. Market Data Flow

```
1. SPYDER Requests Market Data
    ↓
2. MarketDataManager Checks Cache
    ↓
3. If Cache Miss → Request from IBKR
    ↓
4. Receive Market Data Snapshot
    ↓
5. Translate to SPYDER Format
    ↓
6. Update Cache
    ↓
7. Return to Requester
```

---

## 4. API Compatibility Layer

### 4.1. Legacy to IBKR Method Mapping

| Legacy Method | IBKR Client Portal Method | Notes |
|---------------|---------------------------|-------|
| `place_order()` | `POST /iserver/account/{id}/orders` | Different payload format |
| `cancel_order()` | `DELETE /iserver/account/{id}/orders/{id}` | Direct mapping |
| `get_market_data()` | `GET /iserver/marketdata/snapshot` | Batch requests supported |
| `get_positions()` | `GET /iserver/account/positions/{id}` | Direct mapping |
| `get_account()` | `GET /portfolio/accounts` | Slight response format difference |

### 4.2. Message Format Translation

```python
# Legacy Format → IBKR Format
def translate_order_placement(legacy_order):
    return {
        "orders": [{
            "conid": legacy_order['conid'],
            "orderType": legacy_order['order_type'],
            "side": legacy_order['side'],
            "quantity": legacy_order['quantity'],
            "price": legacy_order.get('price'),
            "tif": "DAY"
        }]
    }

# IBKR Format → Legacy Format
def translate_market_data(ibkr_snapshot):
    return {
        "symbol": ibkr_snapshot['symbol'],
        "last_price": ibkr_snapshot.get('31'),
        "bid": ibkr_snapshot.get('84'),
        "ask": ibkr_snapshot.get('86'),
        "volume": ibkr_snapshot.get('7059'),
        "timestamp": datetime.now()
    }
```

---

## 5. Error Handling Strategy

### 5.1. Error Categories

1. **Connection Errors**: Gateway unavailable, network issues
2. **Authentication Errors**: Session expired, login required
3. **API Errors**: Invalid requests, rate limits
4. **Data Errors**: Missing fields, invalid formats
5. **System Errors**: Resource constraints, timeouts

### 5.2. Error Recovery Mechanisms

```python
class ErrorHandler:
    def handle_connection_error(error):
        # Implement exponential backoff
        # Notify user of gateway issues
        # Attempt automatic reconnection
        pass

    def handle_auth_error(error):
        # Prompt user for re-authentication
        # Pause operations until authenticated
        # Send notifications
        pass

    def handle_api_error(error):
        # Log error details
        # Implement retry logic for transient errors
        # Fail fast for permanent errors
        pass
```

---

## 6. Configuration Management

### 6.1. Configuration Structure

```yaml
# ibkr_config.yaml
gateway:
  base_url: "https://localhost:5000"
  api_version: "v1"
  timeout: 30
  verify_ssl: false

authentication:
  auto_refresh: true
  refresh_interval: 3600
  tickle_interval: 60

accounts:
  default_account: "DU1234567"
  paper_account: "DU7654321"

market_data:
  default_fields: ["31", "84", "86"]  # Last, Bid, Ask
  cache_duration: 5  # seconds
  max_subscriptions: 100

orders:
  default_tif: "DAY"
  validate_before_submit: true
  timeout: 10

logging:
  level: "INFO"
  file: "ibkr_wrapper.log"
  max_size: "10MB"
```

### 6.2. Environment Variables

```bash
# IBKR Configuration
IBKR_GATEWAY_URL=https://localhost:5000
IBKR_DEFAULT_ACCOUNT=DU1234567
IBKR_PAPER_ACCOUNT=DU7654321
IBKR_LOG_LEVEL=INFO

# Migration Control
USE_IBKR_WRAPPER=true
IBKR_ENV=production  # certification/production
```

---

## 7. Testing Strategy

### 7.1. Unit Testing

- Test each component independently
- Mock IBKR gateway responses
- Validate error handling
- Test configuration loading

### 7.2. Integration Testing

- Test component interactions
- Validate end-to-end flows
- Test with actual IBKR gateway
- Verify message translations

### 7.3. Performance Testing

- Measure API response times
- Test under load
- Validate caching effectiveness
- Monitor resource usage

---

## 8. Migration Path

### 8.1. Phase 1: Core Implementation
1. Implement SessionManager
2. Implement OrderManager
3. Implement MessageTranslator
4. Create basic tests

### 8.2. Phase 2: Integration
1. Integrate with SPYDER modules
2. Implement MarketDataManager
3. Add comprehensive error handling
4. Create integration tests

### 8.3. Phase 3: Testing & Validation
1. Parallel operation with legacy system
2. Data consistency validation
3. Performance benchmarking
4. User acceptance testing

### 8.4. Phase 4: Production Cutover
1. Gradual migration
2. Monitor performance
3. Keep rollback capability
4. Full deployment

---

## 9. Security Considerations

### 9.1. Authentication Security
- Never store credentials in code
- Use environment variables for sensitive data
- Implement secure session management
- Handle 2FA requirements gracefully

### 9.2. Network Security
- Validate SSL certificates in production
- Implement request timeouts
- Rate limit API calls
- Log security events

### 9.3. Data Security
- Encrypt sensitive configuration
- Secure market data cache
- Audit order access
- Implement data retention policies

---

## 10. Monitoring & Observability

### 10.1. Key Metrics
- API response times
- Error rates by type
- Order execution success rate
- Market data latency
- Session health metrics

### 10.2. Alerting
- Gateway disconnection
- Authentication failures
- High error rates
- Order submission failures
- Performance degradation

---

## 11. File Structure

```
IBKR_Client_Portal_Wrapper/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── config_manager.py
│   └── ibkr_config.yaml
├── session/
│   ├── __init__.py
│   └── session_manager.py
├── orders/
│   ├── __init__.py
│   └── order_manager.py
├── market_data/
│   ├── __init__.py
│   └── market_data_manager.py
├── translation/
│   ├── __init__.py
│   └── message_translator.py
├── monitoring/
│   ├── __init__.py
│   └── health_monitor.py
├── utils/
│   ├── __init__.py
│   ├── error_handler.py
│   └── retry_handler.py
└── tests/
    ├── __init__.py
    ├── test_session_manager.py
    ├── test_order_manager.py
    ├── test_market_data_manager.py
    └── test_integration.py
```

---

## 12. Next Steps

1. **Immediate**: Implement SessionManager for authentication handling
2. **Week 1**: Implement OrderManager with basic order operations
3. **Week 2**: Implement MarketDataManager for data retrieval
4. **Week 3**: Create MessageTranslator for format conversion
5. **Week 4**: Integration testing and validation
6. **Week 5**: Production deployment and monitoring

---

## Conclusion

This architecture provides a robust foundation for implementing IBKR's Client Portal Web API while maintaining compatibility with existing SPYDER modules. The modular design allows for incremental implementation and testing, reducing migration risk while ensuring system reliability.

The key challenge is handling IBKR's manual authentication requirement, which is addressed through comprehensive session management and user notification systems. The architecture provides clear separation of concerns and maintains the flexibility to adapt to future API changes.