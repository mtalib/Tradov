# IBKR Client Portal Web API Wrapper for SPYDER

## Overview

This repository contains a comprehensive wrapper for IBKR's Client Portal Web API for the SPYDER trading system. The wrapper provides a unified interface for all trading operations while handling the complexities of IBKR's REST API and manual authentication flow.

## Key Features

- **Simplified Architecture**: Single connection vs. 8-client IB Gateway
- **Robust Session Management**: Handles IBKR's manual authentication flow
- **Comprehensive Trading Support**: Orders, market data, positions, and accounts
- **Message Translation**: Converts between IBKR and SPYDER formats
- **Flexible Configuration**: Environment variables and configuration files
- **Extensive Testing**: Unit tests, integration tests, and performance benchmarks
- **Migration Support**: Complete migration strategy and tools

## Architecture

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
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│   Interactive Brokers Backend         │
└───────────────────────────────────────┘
```

## Components

### 1. SessionManager (`session/session_manager.py`)

Handles IBKR's session management and authentication flow.

**Key Features:**
- Gateway availability monitoring
- Authentication status tracking
- Session health monitoring
- Automatic reconnection handling
- Tickle requests to keep session alive

**Usage:**
```python
from IBKR_Client_Portal_Web_API.session.session_manager import SessionManager, SessionConfig

config = SessionConfig(
    base_url="https://localhost:5000",
    auth_check_interval=5,
    tickle_interval=60
)

session_manager = SessionManager(config)
session_manager.start()

# Check authentication status
if session_manager.check_auth_status():
    print("Authenticated with IBKR")
else:
    print("Please login via browser: https://localhost:5000")
```

### 2. OrderManager (`orders/order_manager.py`)

Manages all order operations with IBKR API.

**Key Features:**
- Order placement (equities, options, multi-leg)
- Order cancellation and modification
- Order status tracking
- Order validation before submission
- Order history management

**Usage:**
```python
from IBKR_Client_Portal_Web_API.orders.order_manager import OrderManager, OrderRequest, OrderConfig

config = OrderConfig(validate_orders=True)
order_manager = OrderManager(session_manager, config)

# Create order request
order_request = OrderRequest(
    account_id="DU1234567",
    conid=756733,  # SPY
    symbol="SPY",
    side="BUY",
    order_type="LIMIT",
    quantity=100,
    limit_price=450.0
)

# Place order
order_id = order_manager.place_order(order_request)
print(f"Order placed: {order_id}")

# Cancel order
order_manager.cancel_order(order_id, "DU1234567")
```

### 3. MarketDataManager (`market_data/market_data_manager.py`)

Manages market data retrieval and caching.

**Key Features:**
- Real-time market data snapshots
- Historical data retrieval
- Option chain data
- Contract search and details
- Market data caching
- Rate limit handling

**Usage:**
```python
from IBKR_Client_Portal_Web_API.market_data.market_data_manager import MarketDataManager, MarketDataConfig

config = MarketDataConfig(cache_duration=5)
market_data_manager = MarketDataManager(session_manager, config)

# Get market data snapshots
snapshots = market_data_manager.get_market_snapshot(['SPY', 'QQQ'])
for symbol, snapshot in snapshots.items():
    print(f"{symbol}: {snapshot.last_price} (Bid: {snapshot.bid}, Ask: {snapshot.ask})")

# Get historical data
historical = market_data_manager.get_historical_data('SPY', '1d', '1hour')
print(f"Historical data points: {len(historical)}")
```

### 4. MessageTranslator (`translation/message_translator.py`)

Converts between IBKR API format and SPYDER format.

**Key Features:**
- Market data format translation
- Order status translation
- Position information translation
- Account summary translation
- Timestamp normalization

**Usage:**
```python
from IBKR_Client_Portal_Web_API.translation.message_translator import MessageTranslator

translator = MessageTranslator()

# Translate market data
ibkr_data = {
    '31': '450.25',  # Last price
    '84': '450.20',  # Bid
    '86': '450.30',  # Ask
    '7059': '1000000'  # Volume
}

tick = translator.translate_market_data(ibkr_data, 'SPY')
print(f"Translated tick: {tick.symbol} - {tick.last_price}")
```

### 5. ConfigManager (`config/config_manager.py`)

Manages configuration from multiple sources.

**Key Features:**
- Configuration loading from files and environment
- Configuration validation
- Runtime configuration updates
- Default configuration management

**Usage:**
```python
from IBKR_Client_Portal_Web_API.config.config_manager import ConfigManager

# Create config manager
config_manager = ConfigManager('ibkr_config.yaml')

# Get configuration
config = config_manager.get_config()
print(f"Gateway URL: {config.gateway.base_url}")

# Update configuration
updates = {
    'gateway': {
        'timeout': 45
    }
}
config_manager.update_config(updates)
```

## Installation

### Prerequisites

1. Python 3.8 or higher
2. IBKR Client Portal Gateway (download from IBKR)
3. IBKR account with API access

### Setup

1. Clone the repository:
```bash
git clone https://github.com/your-org/IBKR_Client_Portal_Web_API.git
cd IBKR_Client_Portal_Web_API
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start IBKR Client Portal Gateway:
```bash
# Navigate to gateway installation directory
cd /path/to/ibkr/gateway
./gateway.sh
```

4. Configure the wrapper:
```bash
# Copy configuration template
cp config/ibkr_config.yaml.template config/ibkr_config.yaml

# Edit configuration
nano config/ibkr_config.yaml
```

5. Set environment variables:
```bash
export IBKR_DEFAULT_ACCOUNT=DU1234567
export IBKR_ENV=production
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `IBKR_GATEWAY_URL` | Gateway base URL | `https://localhost:5000` |
| `IBKR_DEFAULT_ACCOUNT` | Default account ID | None |
| `IBKR_PAPER_ACCOUNT` | Paper trading account | None |
| `IBKR_ENV` | Environment (production/certification) | `production` |
| `IBKR_LOG_LEVEL` | Logging level | `INFO` |
| `USE_IBKR_WRAPPER` | Enable IBKR wrapper | `true` |

### Configuration File

Create `ibkr_config.yaml`:

```yaml
gateway:
  base_url: "https://localhost:5000"
  api_version: "v1"
  timeout: 30
  verify_ssl: false

session:
  auth_check_interval: 5
  tickle_interval: 60
  max_auth_wait: 300

orders:
  default_timeout: 10
  validate_orders: true
  order_cache_duration: 300

market_data:
  cache_duration: 5
  rate_limit_delay: 0.1
  default_fields: ["31", "84", "86"]

logging:
  level: "INFO"
  file: "ibkr_wrapper.log"
```

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_ibkr_wrapper.py

# Run with coverage
python -m pytest tests/ --cov=IBKR_Client_Portal_Web_API
```

### Test Categories

1. **Unit Tests**: Test individual components
2. **Integration Tests**: Test component interactions
3. **Performance Tests**: Measure performance benchmarks
4. **End-to-End Tests**: Test complete workflows

## Migration from Legacy Systems

### Quick Start

1. Install the IBKR wrapper
2. Set the environment variable:
```bash
export USE_IBKR_WRAPPER=true
```
3. Update your SPYDER configuration
4. Run the migration script:
```bash
python scripts/migrate_from_legacy.py
```

### Detailed Migration

See `migration_strategy.md` for a comprehensive migration guide.

## API Reference

### SessionManager

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `start()` | Start session manager | None | bool |
| `stop()` | Stop session manager | None | None |
| `check_auth_status()` | Check authentication | None | bool |
| `is_gateway_available()` | Check gateway availability | None | bool |
| `send_tickle()` | Send tickle request | None | bool |
| `get_session_info()` | Get session information | None | SessionInfo |
| `get_status()` | Get status information | None | Dict |

### OrderManager

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `place_order()` | Place an order | OrderRequest | str |
| `cancel_order()` | Cancel an order | order_id, account_id | bool |
| `modify_order()` | Modify an order | order_id, modifications, account_id | bool |
| `get_order_status()` | Get order status | order_id, account_id | Order |
| `get_open_orders()` | Get open orders | account_id | List[Order] |
| `validate_order()` | Validate order | OrderRequest | Dict |
| `get_order_history()` | Get order history | account_id, days | List[Order] |

### MarketDataManager

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `get_market_snapshot()` | Get market data | symbols, fields | Dict |
| `get_historical_data()` | Get historical data | symbol, period, bar_size | List |
| `search_contracts()` | Search contracts | symbol, sec_type | List |
| `get_option_chain()` | Get option chain | symbol, expiration | Dict |

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Ensure you're logged in via browser: `https://localhost:5000`
   - Check account credentials
   - Verify gateway is running

2. **Connection Timeout**
   - Increase timeout in configuration
   - Check network connectivity
   - Verify gateway URL

3. **Order Rejected**
   - Check account permissions
   - Verify order parameters
   - Check market hours

4. **Market Data Missing**
   - Verify market data subscriptions
   - Check symbol mappings
   - Ensure authenticated

### Debug Mode

Enable debug logging:
```bash
export IBKR_LOG_LEVEL=DEBUG
```

## Performance

### Benchmarks

- Market data retrieval: < 100ms for 10 symbols
- Order placement: < 200ms
- Order status check: < 100ms
- Authentication check: < 50ms

### Optimization Tips

1. Use caching for market data
2. Batch requests when possible
3. Optimize polling intervals
4. Monitor API rate limits

## Support

### Documentation

- [Architecture Guide](IBKR_API_Wrapper_Architecture.md)
- [Migration Strategy](migration_strategy.md)
- [API Reference](docs/api_reference.md)

### Contact

- Email: support@spyder-trading.com
- Documentation: https://docs.spyder-trading.com
- Issues: https://github.com/your-org/IBKR_Client_Portal_Web_API/issues

## Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Code Style

Follow PEP 8 style guidelines. Use the provided linting configuration:
```bash
flake8 IBKR_Client_Portal_Web_API/
black IBKR_Client_Portal_Web_API/
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

### Version 1.0.0 (2025-10-21)

- Initial release
- Complete IBKR Client Portal Web API wrapper
- Session management
- Order management
- Market data management
- Message translation
- Configuration management
- Testing framework
- Migration strategy

---

**Note**: This wrapper is designed specifically for the SPYDER trading system. While it can be adapted for other use cases, some features may be SPYDER-specific.