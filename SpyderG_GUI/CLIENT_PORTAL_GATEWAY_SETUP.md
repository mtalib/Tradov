# IBKR Client Portal Gateway Setup Guide

## Overview

The IBKR Client Portal Gateway is a **local proxy service** that enables HTTPS-based REST and WebSocket communication with Interactive Brokers. It's required for using the IBKR Web API with OAuth 2.0 authentication.

## Architecture

```
Your Application (Spyder Dashboard)
         ↓ HTTPS
https://localhost:5000/v1/api/...
         ↓
Client Portal Gateway (local process)
         ↓ Internal Connection
IBKR Backend Servers
    - Port 4001 (Live Trading)
    - Port 4002 (Paper Trading)
```

### Port Usage

| Port | Type | Purpose |
|------|------|---------|
| 5000 | Local Gateway | Your app communicates with the local gateway via HTTPS |
| 4001 | IBKR Live | Gateway connects to IBKR's live trading backend |
| 4002 | IBKR Paper | Gateway connects to IBKR's paper trading backend |

## Installation Methods

### Method 1: Docker (Recommended)

Docker provides the easiest and most reliable way to run the Client Portal Gateway.

#### Prerequisites
```bash
# Install Docker (if not already installed)
sudo apt update
sudo apt install docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER
# Log out and back in for group change to take effect
```

#### Pull the Official Image
```bash
docker pull ghcr.io/interactivebrokers/cpgw:latest
```

#### Run the Gateway

**For Paper Trading:**
```bash
docker run -d \
  --name ibkr-gateway-paper \
  -p 5000:5000 \
  -e TRADING_MODE=paper \
  ghcr.io/interactivebrokers/cpgw:latest
```

**For Live Trading:**
```bash
docker run -d \
  --name ibkr-gateway-live \
  -p 5000:5000 \
  -e TRADING_MODE=live \
  ghcr.io/interactivebrokers/cpgw:latest
```

#### Verify Gateway is Running
```bash
# Check container status
docker ps | grep ibkr-gateway

# Check logs
docker logs ibkr-gateway-paper

# Test gateway endpoint
curl -k https://localhost:5000/v1/api/one/user
```

### Method 2: Standalone Installation

Download the Client Portal Gateway from IBKR's official website.

#### Download
1. Go to: https://www.interactivebrokers.com/en/trading/ib-api.php
2. Navigate to: **API Software** → **Client Portal Web API**
3. Download the appropriate version for your OS

#### Extract and Configure
```bash
# Extract the downloaded archive
unzip clientportal.gw.zip -d ~/ibkr-gateway
cd ~/ibkr-gateway

# Edit configuration file
nano conf.yaml
```

#### Configuration File (`conf.yaml`)

```yaml
# Port configuration
listenPort: 5000
listenSsl: true

# Trading mode
tradingMode: paper  # or 'live'

# Authentication
authentication:
  oauth:
    enabled: true

# SSL Configuration (optional - uses self-signed cert by default)
ssl:
  cert: /path/to/cert.pem
  key: /path/to/key.pem

# Logging
logging:
  level: INFO

# Session timeout (in seconds)
sessionTimeout: 86400  # 24 hours
```

#### Start the Gateway
```bash
cd ~/ibkr-gateway
./bin/run.sh root/conf.yaml
```

## OAuth 2.0 Setup

### Step 1: Generate RSA Key Pair

The OAuth launcher requires an RSA key pair for JWT authentication.

```bash
cd /home/adam/Projects/Spyder/SpyderG_GUI
bash generate_oauth_keys.sh
```

This creates:
- `~/.spyder/keys/private_key.pem` (keep secure!)
- `~/.spyder/keys/public_key.pem` (upload to IBKR)

### Step 2: Register OAuth Application with IBKR

1. **Log in to IBKR Account Management**
   - Go to: https://www.interactivebrokers.com/sso/Login
   - Use your IBKR credentials

2. **Navigate to API Settings**
   - Click on **Settings** → **API** → **Settings**
   - Look for **OAuth Applications**

3. **Create New OAuth Application**
   - Click **Create New Application**
   - Application Name: `Spyder Trading System`
   - Description: `OAuth authentication for Spyder`
   - Redirect URI: `https://localhost:5000/oauth/callback`

4. **Upload Public Key**
   - Click **Add Public Key**
   - Upload: `~/.spyder/keys/public_key.pem`
   - Or copy/paste the contents of the file

5. **Note Your Credentials**
   ```
   Client ID: l1234567890  (starts with 'l')
   Account ID: DU1234567   (starts with 'DU' for paper, 'U' for live)
   ```

### Step 3: Configure OAuth Launcher

1. **Start the Client Portal Gateway** (see above)

2. **Launch the OAuth Launcher**
   ```bash
   cd /home/adam/Projects/Spyder
   source .venv/bin/activate
   cd SpyderG_GUI
   python SpyderG08_IBKRLoginLauncher_OAuth.py
   ```

3. **Configure OAuth Settings**
   - **Client ID**: Enter the Client ID from IBKR (starts with 'l')
   - **Account ID**: Enter your Account ID (DU format for paper)
   - **Private Key Path**: Should auto-populate to `~/.spyder/keys/private_key.pem`
   - **Environment**: Select `paper` or `live`
   - Check **Remember Configuration** if desired
   - Click **Save Configuration**

## Testing the Connection

### 1. Verify Gateway is Running
```bash
# Using curl
curl -k https://localhost:5000/v1/api/one/user

# Or using Python
python -c "
import requests
import urllib3
urllib3.disable_warnings()
response = requests.get('https://localhost:5000/v1/api/one/user', verify=False)
print(f'Status: {response.status_code}')
print(f'Response: {response.text}')
"
```

Expected response:
```json
{
  "authenticated": false,
  "competing": false,
  "connected": false,
  "message": "",
  "MAC": "xx:xx:xx:xx:xx:xx",
  "serverInfo": {
    "serverName": "JifN19053",
    "serverVersion": "Build 10.25.0p, Dec 2 2024 5:42:09 PM"
  }
}
```

### 2. Test OAuth Authentication

Once the gateway is running and you've configured OAuth:

```bash
cd /home/adam/Projects/Spyder
source .venv/bin/activate
cd SpyderG_GUI

# Test JWT generation
python -c "
from SpyderG08_IBKRLoginLauncher_OAuth import IBKROAuthManager
import sys

manager = IBKROAuthManager()
client_id = 'YOUR_CLIENT_ID'
private_key_path = '~/.spyder/keys/private_key.pem'

jwt_token = manager.generate_jwt(client_id, private_key_path)
if jwt_token:
    print('✅ JWT token generated successfully')
    print(f'Token (first 50 chars): {jwt_token[:50]}...')
else:
    print('❌ Failed to generate JWT token')
    sys.exit(1)
"
```

## Running the Complete System

### For Paper Trading

```bash
# Terminal 1: Start Client Portal Gateway (Docker)
docker run -d \
  --name ibkr-gateway-paper \
  -p 5000:5000 \
  -e TRADING_MODE=paper \
  ghcr.io/interactivebrokers/cpgw:latest

# Terminal 2: Launch Spyder with OAuth
cd /home/adam/Projects/Spyder
source .venv/bin/activate
cd SpyderG_GUI
python SpyderG08_IBKRLoginLauncher_OAuth.py

# In the GUI:
# 1. Configure Paper Trading credentials
# 2. Click "Launch Paper Trading"
```

### For Live Trading

```bash
# Terminal 1: Start Client Portal Gateway (Docker)
docker run -d \
  --name ibkr-gateway-live \
  -p 5000:5000 \
  -e TRADING_MODE=live \
  ghcr.io/interactivebrokers/cpgw:latest

# Terminal 2: Launch Spyder with OAuth
cd /home/adam/Projects/Spyder
source .venv/bin/activate
cd SpyderG_GUI
python SpyderG08_IBKRLoginLauncher_OAuth.py

# In the GUI:
# 1. Configure Live Trading credentials
# 2. Click "Launch Live Trading"
# 3. Confirm the warning about real money trading
```

## Troubleshooting

### Gateway Not Starting

**Issue**: Gateway container exits immediately
```bash
docker logs ibkr-gateway-paper
```

**Common causes**:
- Port 5000 already in use
- Invalid configuration
- Missing environment variables

**Solutions**:
```bash
# Check if port is in use
sudo netstat -tlnp | grep 5000

# Kill process using port 5000
sudo kill -9 $(sudo lsof -t -i:5000)

# Try different port
docker run -d \
  --name ibkr-gateway-paper \
  -p 5001:5000 \
  -e TRADING_MODE=paper \
  ghcr.io/interactivebrokers/cpgw:latest
```

### SSL Certificate Errors

**Issue**: `SSL: CERTIFICATE_VERIFY_FAILED`

**Solution**: The gateway uses self-signed certificates by default. You need to:

1. **Accept the certificate in browser**:
   - Visit: https://localhost:5000
   - Click "Advanced" → "Proceed to localhost (unsafe)"

2. **Or disable SSL verification in code** (development only):
   ```python
   import urllib3
   urllib3.disable_warnings()
   response = requests.get(url, verify=False)
   ```

### OAuth Authentication Fails

**Issue**: `401 Unauthorized` or `Invalid JWT`

**Checklist**:
1. ✅ Client Portal Gateway is running
2. ✅ Public key uploaded to IBKR Account Management
3. ✅ Client ID and Account ID are correct
4. ✅ Private key file exists and is readable
5. ✅ JWT token is properly formatted

**Debug**:
```bash
# Verify private key
openssl rsa -in ~/.spyder/keys/private_key.pem -text -noout

# Verify public key matches
openssl rsa -in ~/.spyder/keys/private_key.pem -pubout
diff - ~/.spyder/keys/public_key.pem
```

### Connection Timeout

**Issue**: Requests to `localhost:5000` timeout

**Solutions**:
```bash
# Check gateway is listening
curl -k https://localhost:5000/v1/api/tickle

# Check firewall
sudo ufw status
sudo ufw allow 5000/tcp

# Check Docker networking
docker inspect ibkr-gateway-paper | grep IPAddress
```

### Token Expiration

**Issue**: `Access token expired`

**Solution**: The OAuth launcher automatically refreshes tokens. If issues persist:

1. Check token expiration time in configuration
2. Verify refresh token is valid
3. Re-authenticate through the launcher

## Advanced Configuration

### Custom Gateway Configuration

Create a custom `conf.yaml`:

```yaml
# Custom Client Portal Gateway Configuration
listenPort: 5000
listenSsl: true
tradingMode: paper

# OAuth settings
authentication:
  oauth:
    enabled: true
    tokenExpiry: 3600  # 1 hour
    refreshWindow: 300  # Refresh 5 minutes before expiry

# CORS for web apps
cors:
  enabled: true
  allowedOrigins:
    - https://localhost:3000

# Rate limiting
rateLimit:
  enabled: true
  requestsPerMinute: 60

# Logging
logging:
  level: DEBUG
  file: /var/log/ibkr-gateway.log
```

Run with custom config:
```bash
docker run -d \
  --name ibkr-gateway-paper \
  -p 5000:5000 \
  -v $(pwd)/conf.yaml:/root/conf.yaml \
  ghcr.io/interactivebrokers/cpgw:latest
```

### Multiple Gateway Instances

Run both paper and live gateways simultaneously:

```bash
# Paper on port 5000
docker run -d \
  --name ibkr-gateway-paper \
  -p 5000:5000 \
  -e TRADING_MODE=paper \
  ghcr.io/interactivebrokers/cpgw:latest

# Live on port 5001
docker run -d \
  --name ibkr-gateway-live \
  -p 5001:5000 \
  -e TRADING_MODE=live \
  ghcr.io/interactivebrokers/cpgw:latest
```

Update OAuth launcher to use appropriate port for each mode.

## Docker Compose Setup (Recommended for Production)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  ibkr-gateway-paper:
    image: ghcr.io/interactivebrokers/cpgw:latest
    container_name: ibkr-gateway-paper
    ports:
      - "5000:5000"
    environment:
      - TRADING_MODE=paper
    volumes:
      - ./conf-paper.yaml:/root/conf.yaml
      - ./logs:/var/log
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-k", "https://localhost:5000/v1/api/tickle"]
      interval: 30s
      timeout: 10s
      retries: 3

  ibkr-gateway-live:
    image: ghcr.io/interactivebrokers/cpgw:latest
    container_name: ibkr-gateway-live
    ports:
      - "5001:5000"
    environment:
      - TRADING_MODE=live
    volumes:
      - ./conf-live.yaml:/root/conf.yaml
      - ./logs:/var/log
    restart: unless-stopped
    profiles:
      - live  # Only start when explicitly specified
    healthcheck:
      test: ["CMD", "curl", "-k", "https://localhost:5000/v1/api/tickle"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Usage:
```bash
# Start paper gateway only
docker-compose up -d ibkr-gateway-paper

# Start both paper and live
docker-compose --profile live up -d

# View logs
docker-compose logs -f

# Stop all
docker-compose down
```

## Gateway Management Scripts

### Start Gateway Script

Create `start_gateway.sh`:
```bash
#!/bin/bash
MODE=${1:-paper}  # Default to paper

if [ "$MODE" = "paper" ]; then
    PORT=5000
    NAME="ibkr-gateway-paper"
elif [ "$MODE" = "live" ]; then
    PORT=5001
    NAME="ibkr-gateway-live"
else
    echo "Usage: $0 [paper|live]"
    exit 1
fi

echo "Starting IBKR Client Portal Gateway in $MODE mode on port $PORT..."

docker run -d \
  --name $NAME \
  -p $PORT:5000 \
  -e TRADING_MODE=$MODE \
  --restart unless-stopped \
  ghcr.io/interactivebrokers/cpgw:latest

sleep 3
docker ps | grep $NAME

echo ""
echo "✅ Gateway started successfully!"
echo "   Mode: $MODE"
echo "   Port: $PORT"
echo "   URL: https://localhost:$PORT"
echo ""
echo "Test with: curl -k https://localhost:$PORT/v1/api/tickle"
```

Make executable:
```bash
chmod +x start_gateway.sh
./start_gateway.sh paper
```

### Stop Gateway Script

Create `stop_gateway.sh`:
```bash
#!/bin/bash
MODE=${1:-paper}

if [ "$MODE" = "paper" ]; then
    NAME="ibkr-gateway-paper"
elif [ "$MODE" = "live" ]; then
    NAME="ibkr-gateway-live"
else
    echo "Usage: $0 [paper|live]"
    exit 1
fi

echo "Stopping $NAME..."
docker stop $NAME
docker rm $NAME
echo "✅ Gateway stopped and removed"
```

Make executable:
```bash
chmod +x stop_gateway.sh
./stop_gateway.sh paper
```

## Security Best Practices

### 1. Protect Your Private Key
```bash
# Secure permissions
chmod 600 ~/.spyder/keys/private_key.pem
chmod 700 ~/.spyder/keys

# Never commit to version control
echo "*.pem" >> .gitignore
echo ".spyder/keys/" >> .gitignore
```

### 2. Use Environment Variables
```bash
# Don't hardcode credentials
export IBKR_CLIENT_ID="l1234567890"
export IBKR_ACCOUNT_ID="DU1234567"
export IBKR_KEY_PATH="~/.spyder/keys/private_key.pem"
```

### 3. Rotate Keys Regularly
```bash
# Generate new key pair every 90 days
cd /home/adam/Projects/Spyder/SpyderG_GUI
bash generate_oauth_keys.sh

# Upload new public key to IBKR
# Update OAuth launcher configuration
```

### 4. Monitor Gateway Logs
```bash
# Watch for suspicious activity
docker logs -f ibkr-gateway-paper | grep -E "(ERROR|WARN|UNAUTHORIZED)"
```

### 5. Network Security
```bash
# Firewall rules (gateway should only be accessible locally)
sudo ufw deny 5000/tcp
sudo ufw allow from 127.0.0.1 to any port 5000
```

## References

- **IBKR Client Portal API Documentation**: https://www.interactivebrokers.com/api/doc.html
- **OAuth 2.0 Specification**: https://oauth.net/2/
- **JWT (JSON Web Tokens)**: https://jwt.io/
- **Docker Documentation**: https://docs.docker.com/

## Support

For issues with:
- **OAuth Launcher**: Check `OAUTH_LAUNCHER_README.md`
- **Client Portal Gateway**: Contact IBKR API Support
- **Docker**: https://docs.docker.com/get-support/

---

**Last Updated**: 2025-10-23
**Version**: 1.0.0
**Author**: Mohamed Talib
