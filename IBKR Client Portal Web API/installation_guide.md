# IBKR Client Portal Gateway Installation Guide

This guide will walk you through installing the IBKR Client Portal Gateway and running tests with the SPYDER wrapper.

## Prerequisites

1. Java Runtime Environment (JRE) 8 or higher
2. IBKR account with Client Portal API access
3. Python 3.8 or higher (for SPYDER wrapper)
4. Internet connection

## Step 1: Download IBKR Client Portal Gateway

1. Log in to your IBKR account
2. Navigate to Trading → Workstations → IB Gateway
3. Download the latest version for your operating system
4. Extract the downloaded file to a location of your choice

## Step 2: Configure the Gateway

1. Navigate to the extracted gateway directory
2. Create a configuration file if needed
3. Edit the gateway configuration:

```bash
# Navigate to gateway directory
cd /path/to/ibkr/gateway

# Create a copy of the configuration template
cp ibgateway.yaml ibgateway_config.yaml

# Edit the configuration
nano ibgateway_config.yaml
```

4. Basic configuration settings:
```yaml
# ibgateway_config.yaml
ibkr:
  username: your_ibkr_username
  password: your_ibkr_password
  mode: paper  # or live for production
  port: 5000
```

## Step 3: Start the Gateway

### Option A: Start from Command Line

```bash
# Navigate to gateway directory
cd /path/to/ibkr/gateway

# Start the gateway
./ibgateway &
```

### Option B: Start with Configuration File

```bash
# Start with specific configuration
./ibgateway --config ibgateway_config.yaml &
```

### Option C: Start on Windows

```cmd
# Navigate to gateway directory
cd C:\path\to\ibkr\gateway

# Start the gateway
ibgateway.exe
```

## Step 4: Verify Gateway is Running

1. Open your web browser
2. Navigate to: `https://localhost:5000`
3. You should see the IBKR login page
4. If you see a security warning, it's normal - click "Advanced" and "Proceed"

## Step 5: Authenticate with IBKR

1. Log in to the IBKR Client Portal through your browser
2. Use your regular IBKR username and password
3. Complete any two-factor authentication if required
4. You should see a confirmation that you're logged in

## Step 6: Install Python Dependencies

```bash
# Navigate to SPYDER wrapper directory
cd /path/to/IBKR_Client_Portal_Web_API

# Install dependencies
pip install -r requirements.txt
```

If requirements.txt doesn't exist, install the core dependencies:

```bash
pip install requests pyyaml dataclasses
```

## Step 7: Configure the SPYDER Wrapper

1. Create a configuration file:
```bash
cp config/ibkr_config.yaml.template config/ibkr_config.yaml
```

2. Edit the configuration:
```yaml
# config/ibkr_config.yaml
gateway:
  base_url: "https://localhost:5000"
  api_version: "v1"
  timeout: 30
  verify_ssl: false

session:
  auth_check_interval: 5
  tickle_interval: 60

orders:
  default_timeout: 10
  validate_orders: true

market_data:
  cache_duration: 5
  rate_limit_delay: 0.1

logging:
  level: "INFO"
  file: "ibkr_wrapper.log"
```

3. Set environment variables:
```bash
export IBKR_DEFAULT_ACCOUNT=DU1234567
export IBKR_ENV=paper
export IBKR_LOG_LEVEL=INFO
```

## Step 8: Run the Test Suite

### Basic Connection Test

```bash
# Run the basic test
python -c "
from session.session_manager import SessionManager
import logging

logging.basicConfig(level=logging.INFO)

# Create session manager
session_manager = SessionManager()
session_manager.start()

# Check authentication
if session_manager.check_auth_status():
    print('✅ Successfully connected to IBKR!')
else:
    print('❌ Authentication failed. Please check your login.')

session_manager.stop()
"
```

### Market Data Test

```bash
# Run the market data test
python -c "
from session.session_manager import SessionManager
from market_data.market_data_manager import MarketDataManager
import logging

logging.basicConfig(level=logging.INFO)

# Create managers
session_manager = SessionManager()
market_data_manager = MarketDataManager(session_manager)

session_manager.start()

# Check authentication
if session_manager.check_auth_status():
    print('✅ Authenticated with IBKR')

    # Get market data
    snapshots = market_data_manager.get_market_snapshot(['SPY'])

    if 'SPY' in snapshots:
        snapshot = snapshots['SPY']
        print(f'📈 SPY Data:')
        print(f'   Last Price: {snapshot.last_price}')
        print(f'   Bid: {snapshot.bid}')
        print(f'   Ask: {snapshot.ask}')
        print(f'   Volume: {snapshot.volume}')
    else:
        print('❌ No SPY data received')
else:
    print('❌ Authentication failed')

session_manager.stop()
"
```

### Order Test (Paper Account Only)

```bash
# Run the order test (paper account only)
python -c "
from session.session_manager import SessionManager
from orders.order_manager import OrderManager, OrderRequest
import logging

logging.basicConfig(level=logging.INFO)

# Create managers
session_manager = SessionManager()
order_manager = OrderManager(session_manager)

session_manager.start()

# Check authentication
if session_manager.check_auth_status():
    print('✅ Authenticated with IBKR')

    # Create a test order (will not be executed)
    order_request = OrderRequest(
        account_id='DU1234567',  # Your paper account
        conid=756733,  # SPY
        symbol='SPY',
        side='BUY',
        order_type='LIMIT',
        quantity=1,
        limit_price=1.00  # Unlikely to execute
    )

    # Validate the order
    validation = order_manager.validate_order(order_request)
    if validation.get('valid', False):
        print('✅ Order validation passed')
        print('📝 Order is ready to be placed (not placing actual test order)')
    else:
        print(f'❌ Order validation failed: {validation.get(\"error\")}')
else:
    print('❌ Authentication failed')

session_manager.stop()
"
```

### Full Test Suite

```bash
# Run the complete test suite
python tests/test_ibkr_wrapper.py
```

## Step 9: Troubleshooting

### Gateway Won't Start

1. Check Java installation:
```bash
java -version
```

2. Check gateway logs:
```bash
tail -f /path/to/ibkr/gateway/logs/ibgateway.log
```

3. Verify port 5000 is not in use:
```bash
netstat -an | grep 5000
```

### Authentication Failed

1. Ensure you're logged in via browser: `https://localhost:5000`
2. Check your IBKR account has API access enabled
3. Verify you're using the correct account credentials

### SSL Certificate Errors

1. The gateway uses a self-signed certificate, which is normal
2. In your browser, click "Advanced" and "Proceed to localhost"
3. In the wrapper, SSL verification is disabled by default

### Connection Timeout

1. Increase timeout in configuration:
```yaml
gateway:
  timeout: 60  # Increase from 30 to 60 seconds
```

2. Check firewall settings
3. Verify the gateway is running

## Step 10: Integration with SPYDER

Once tests are passing, integrate the wrapper with SPYDER:

1. Set the environment variable:
```bash
export USE_IBKR_WRAPPER=true
```

2. Update SPYDER configuration to use IBKR
3. Restart SPYDER
4. Monitor logs for any issues

## Next Steps

After successful installation and testing:

1. Review the migration strategy document
2. Plan your production deployment
3. Set up monitoring and alerting
4. Train users on the new authentication flow

## Support

If you encounter issues:

1. Check the IBKR Gateway documentation
2. Review the wrapper logs
3. Run the test suite for specific error messages
4. Check the troubleshooting section in the main README

---

**Note**: Always test with a paper account first before using with live trading.