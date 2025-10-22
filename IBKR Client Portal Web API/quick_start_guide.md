# Quick Start Guide: IBKR Client Portal Web API

Based on the research reports, I've identified the most efficient path to get your IBKR Client Portal up and running quickly. This guide combines the best practices from existing solutions.

## Recommended Approach: IBeam + Custom Wrapper

For SPYDER's needs, I recommend using **IBeam** for gateway automation combined with our custom wrapper. This approach provides:
- Automated gateway management
- Minimal manual intervention
- Production-ready reliability
- SPYDER-specific optimizations

## Step 1: Install Prerequisites

### Java Runtime Environment
```bash
# Check if Java is installed
java -version

# If not installed, install Java 11+
# Ubuntu/Debian:
sudo apt update
sudo apt install openjdk-11-jdk

# macOS (using Homebrew):
brew install openjdk@11

# Windows:
# Download from https://www.java.com/en/download/
```

### Docker (Recommended for IBeam)
```bash
# Ubuntu/Debian:
sudo apt update
sudo apt install docker.io
sudo systemctl start docker
sudo systemctl enable docker

# macOS:
# Download Docker Desktop from https://www.docker.com/products/docker-desktop

# Windows:
# Download Docker Desktop from https://www.docker.com/products/docker-desktop
```

## Step 2: Install IBeam Gateway Automation

IBeam is a Docker-based solution that automates the IBKR Client Portal Gateway, including login and session management.

### Quick Setup with Docker

1. **Create Environment File:**
```bash
# Create ibeam.env file
cat > ibeam.env << EOF
IBEAM_ACCOUNT=your_paper_username
IBEAM_PASSWORD=your_password
# Optional: Add TOTP secret if you use authenticator app
# IBEAM_KEY=your_totp_secret_key
EOF
```

2. **Run IBeam Container:**
```bash
# Pull IBeam image
docker pull voyz/ibeam

# Run IBeam with your credentials
docker run -d \
  --name ibkr_gateway \
  -p 5000:5000 \
  --env-file ibeam.env \
  voyz/ibeam
```

3. **Verify Gateway is Running:**
```bash
# Check container status
docker ps | grep ibkr_gateway

# Check gateway logs
docker logs ibkr_gateway

# Test gateway health
curl -X GET "https://localhost:5000/v1/api/tickle" -k
```

### Manual Gateway Setup (Alternative)

If you prefer not to use Docker:

1. **Download Client Portal Gateway:**
   - Go to: https://www.interactivebrokers.com/en/trading/ibgateway-download.php
   - Download "clientportal.gw.zip"
   - Extract to: `/home/user/ibkr/clientportal.gw`

2. **Start Gateway:**
```bash
cd /home/user/ibkr/clientportal.gw
./bin/run.sh root/conf.yaml
```

3. **Authenticate via Browser:**
   - Open: https://localhost:5000
   - Login with your IBKR credentials
   - Complete 2FA if required

## Step 3: Install Python Dependencies

```bash
# Navigate to your project directory
cd /path/to/IBKR_Client_Portal_Web_API

# Install Python dependencies
pip install -r requirements.txt
```

If you don't have requirements.txt:
```bash
pip install requests pyyaml dataclasses
```

## Step 4: Configure the Wrapper

1. **Create Configuration File:**
```bash
# Copy template
cp config/ibkr_config.yaml.template config/ibkr_config.yaml

# Edit configuration
nano config/ibkr_config.yaml
```

2. **Update Key Settings:**
```yaml
# config/ibkr_config.yaml
gateway:
  base_url: "https://localhost:5000"
  timeout: 30

accounts:
  default_account: "DU1234567"  # Your paper account ID
  paper_account: "DU1234567"

environment:
  type: "paper"  # Use "production" for live trading
```

3. **Set Environment Variables:**
```bash
export IBKR_DEFAULT_ACCOUNT=DU1234567
export IBKR_ENV=paper
export IBKR_LOG_LEVEL=INFO
```

## Step 5: Run Basic Tests

### Test 1: Connection Test
```bash
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
    print('❌ Authentication failed. Check IBeam logs.')

session_manager.stop()
"
```

### Test 2: Market Data Test
```bash
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

### Test 3: Order Validation Test (Paper Account Only)
```bash
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

## Step 6: Run Full Test Suite

```bash
# Run the complete test suite
python tests/test_ibkr_wrapper.py
```

## Troubleshooting Common Issues

### Issue: IBeam Container Won't Start

**Symptoms:**
- Container exits immediately
- Logs show authentication errors

**Solutions:**
1. Check your credentials:
```bash
# Verify environment file
cat ibbeam.env

# Test with new credentials
docker rm -f ibkr_gateway
docker run -d --name ibkr_gateway --env-file ibeam.env voyz/ibeam
```

2. Check container logs:
```bash
docker logs ibkr_gateway
```

3. Ensure paper account credentials (not live account)

### Issue: SSL Certificate Warnings

**Symptoms:**
- Browser shows "Your connection is not private"
- Python shows SSL verification errors

**Solutions:**
- This is expected (self-signed certificate)
- In browser: Click "Advanced" → "Proceed to localhost"
- In Python: SSL verification is disabled in wrapper

### Issue: Authentication Fails

**Symptoms:**
- "Not authenticated" errors
- Need to re-authenticate frequently

**Solutions:**
1. Check IBeam is running:
```bash
docker ps | grep ibkr_gateway
```

2. Restart IBeam:
```bash
docker restart ibkr_gateway
```

3. Check if using correct credentials (paper vs. live)

### Issue: Market Data Errors (10089)

**Symptoms:**
- Error 10089 - "Requested market data requires additional subscription"

**Solutions:**
1. Log into IBKR Client Portal
2. Go to Account Management → Market Data Subscriptions
3. Subscribe to "US Equity and Options Add-On Streaming Bundle"
4. Wait for subscription activation (may take several hours)

### Issue: Port Conflicts

**Symptoms:**
- "Address already in use" errors
- Gateway won't start

**Solutions:**
1. Check what's using port 5000:
```bash
lsof -i :5000
```

2. Kill the process:
```bash
kill -9 <PID>
```

3. Or use a different port in gateway configuration

## Next Steps

Once tests are passing:

1. **Integrate with SPYDER:**
   - Set `USE_IBKR_WRAPPER=true` in your SPYDER environment
   - Update SPYDER configuration to use IBKR wrapper
   - Restart SPYDER

2. **Monitor Performance:**
   - Check wrapper logs regularly
   - Monitor API call frequency
   - Track authentication status

3. **Plan Production Deployment:**
   - Set up monitoring and alerting
   - Document procedures
   - Train team on new authentication flow

## Quick Reference

### Essential Commands

```bash
# Start IBeam
docker run -d --name ibkr_gateway -p 5000:5000 --env-file ibeam.env voyz/ibeam

# Check IBeam logs
docker logs ibkr_gateway

# Restart IBeam
docker restart ibkr_gateway

# Test connection
curl -X GET "https://localhost:5000/v1/api/tickle" -k

# Run SPYDER with IBKR wrapper
USE_IBKR_WRAPPER=true python spyder_main.py
```

### Key Configuration Files

- `ibeam.env` - IBeam credentials
- `config/ibkr_config.yaml` - Wrapper configuration
- `ibkr_wrapper.log` - Wrapper logs

### Important URLs

- IBKR Gateway: https://localhost:5000
- IBKR Client Portal: https://www.interactivebrokers.com/sso/Login
- IBeam Repository: https://github.com/Voyz/ibeam

---

**Need Help?**
- Check the troubleshooting section above
- Review the full installation guide: `installation_guide.md`
- Examine the migration strategy: `migration_strategy.md`