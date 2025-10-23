# IBKR Web API OAuth - Quick Start Guide

## Complete Setup in 5 Steps

### Step 1: Install Dependencies
```bash
cd /home/adam/Projects/Spyder
source .venv/bin/activate
pip install -r requirements-gui.txt
```

### Step 2: Generate OAuth Keys
```bash
cd SpyderG_GUI
./generate_oauth_keys.sh
```
**Output**: Creates RSA key pair in `~/.spyder/keys/`

### Step 3: Start Client Portal Gateway
```bash
./start_gateway.sh paper
```
**Verify**: `curl -k https://localhost:5000/v1/api/tickle`

### Step 4: Register with IBKR
1. Login: https://www.interactivebrokers.com/sso/Login
2. Go to: Settings → API → OAuth Applications
3. Create application:
   - Name: "Spyder Trading System"
   - Redirect: `https://localhost:5000/oauth/callback`
4. Upload: `~/.spyder/keys/public_key.pem`
5. **Save**: Client ID and Account ID

### Step 5: Launch OAuth Launcher
```bash
cd SpyderG_GUI
python SpyderG08_IBKRLoginLauncher_OAuth.py
```

Configure in GUI:
- **Client ID**: l1234567890 (from IBKR)
- **Account ID**: DU1234567 (from IBKR)
- **Private Key**: `~/.spyder/keys/private_key.pem`
- **Environment**: paper
- Click **Save Configuration**

## Daily Usage

### Start Everything
```bash
# Terminal 1: Start Gateway
cd /home/adam/Projects/Spyder/SpyderG_GUI
./start_gateway.sh paper

# Terminal 2: Launch Spyder
cd /home/adam/Projects/Spyder
source .venv/bin/activate
cd SpyderG_GUI
python SpyderG08_IBKRLoginLauncher_OAuth.py
```

### Stop Everything
```bash
# Stop gateway
./stop_gateway.sh paper

# Dashboard will close when you're done
```

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│  Your Application (Spyder Dashboard)            │
│  - OAuth Launcher                               │
│  - Trading Dashboard                            │
└────────────────┬────────────────────────────────┘
                 │ HTTPS (OAuth JWT)
                 ↓
┌─────────────────────────────────────────────────┐
│  Client Portal Gateway (localhost:5000)         │
│  - Docker Container                             │
│  - OAuth Authentication                         │
│  - REST API Endpoints                           │
└────────────────┬────────────────────────────────┘
                 │ Internal Connection
                 ↓
┌─────────────────────────────────────────────────┐
│  IBKR Backend Servers                           │
│  - Port 4001 (Live Trading)                     │
│  - Port 4002 (Paper Trading)                    │
└─────────────────────────────────────────────────┘
```

## Key Concepts

### Ports
- **5000**: Your app ↔ Local Gateway (HTTPS/REST)
- **4001**: Gateway ↔ IBKR Live (internal)
- **4002**: Gateway ↔ IBKR Paper (internal)

### Authentication Flow
1. **JWT Generation**: OAuth launcher creates JWT signed with private key
2. **Token Request**: Gateway validates JWT and requests access token from IBKR
3. **Access Token**: Gateway receives token and uses for all API calls
4. **Auto Refresh**: Launcher automatically refreshes token before expiration

### Security
- ✅ Private key never leaves your machine
- ✅ JWT tokens expire after 1 hour
- ✅ Gateway uses HTTPS with TLS
- ✅ OAuth 2.0 industry standard

## Troubleshooting

### Gateway Not Running
```bash
# Check if gateway is running
docker ps | grep ibkr-gateway

# View logs
docker logs ibkr-gateway-paper

# Restart
./stop_gateway.sh paper
./start_gateway.sh paper
```

### Authentication Failed
```bash
# Verify keys exist
ls -la ~/.spyder/keys/

# Test gateway connectivity
curl -k https://localhost:5000/v1/api/tickle

# Check OAuth configuration in launcher GUI
```

### Connection Issues
```bash
# Check ports
sudo netstat -tlnp | grep 5000

# Test SSL connection
openssl s_client -connect localhost:5000 -showcerts

# Verify Docker networking
docker inspect ibkr-gateway-paper | grep IPAddress
```

## Common Commands

```bash
# Gateway management
./start_gateway.sh paper          # Start paper gateway
./start_gateway.sh live           # Start live gateway
./stop_gateway.sh paper           # Stop paper gateway
./stop_gateway.sh all             # Stop all gateways

# View logs
docker logs -f ibkr-gateway-paper # Follow logs
docker logs --tail 100 ibkr-gateway-paper # Last 100 lines

# Container management
docker ps                         # List running containers
docker ps -a                      # List all containers
docker restart ibkr-gateway-paper # Restart gateway
docker rm ibkr-gateway-paper      # Remove container

# Test gateway
curl -k https://localhost:5000/v1/api/tickle          # Health check
curl -k https://localhost:5000/v1/api/one/user        # User info
curl -k https://localhost:5000/v1/api/portfolio/accounts # Accounts

# Key management
./generate_oauth_keys.sh          # Generate new keys
openssl rsa -in ~/.spyder/keys/private_key.pem -text -noout # View key info
cat ~/.spyder/keys/public_key.pem # Display public key
```

## File Locations

```
/home/adam/Projects/Spyder/
├── SpyderG_GUI/
│   ├── SpyderG08_IBKRLoginLauncher_OAuth.py    # OAuth launcher
│   ├── SpyderG05_TradingDashboard.py           # Trading dashboard
│   ├── generate_oauth_keys.sh                   # Key generation script
│   ├── start_gateway.sh                         # Gateway startup
│   ├── stop_gateway.sh                          # Gateway shutdown
│   ├── CLIENT_PORTAL_GATEWAY_SETUP.md          # Detailed setup guide
│   ├── OAUTH_LAUNCHER_README.md                # Launcher documentation
│   └── OAUTH_QUICK_START.md                    # This file
├── config/
│   └── launcher_config_oauth.ini                # OAuth configuration
└── .venv/                                       # Virtual environment

~/.spyder/
└── keys/
    ├── private_key.pem                          # OAuth private key (SECURE!)
    └── public_key.pem                           # OAuth public key
```

## Three Launch Modes

### 1. Dashboard Only
- **Use Case**: Visualization and testing without IBKR connection
- **Requirements**: None
- **Data**: Simulated market data
- **Click**: "🖥️ Launch Dashboard" button

### 2. Paper Trading
- **Use Case**: Safe trading simulation with virtual money
- **Requirements**: OAuth credentials, Gateway running
- **Data**: Live market data, simulated trading
- **Click**: "📄 Launch Paper Trading" button

### 3. Live Trading
- **Use Case**: Real money trading
- **Requirements**: OAuth credentials, Gateway running, funded account
- **Data**: Live market data and trading
- **Click**: "💰 Launch Live Trading" button
- **Warning**: ⚠️ REAL MONEY MODE ⚠️

## Security Best Practices

1. **Protect Private Key**
   ```bash
   chmod 600 ~/.spyder/keys/private_key.pem
   echo "*.pem" >> .gitignore
   ```

2. **Rotate Keys Regularly**
   ```bash
   # Every 90 days
   ./generate_oauth_keys.sh
   # Upload new public key to IBKR
   ```

3. **Monitor Gateway Logs**
   ```bash
   docker logs -f ibkr-gateway-paper | grep -E "(ERROR|WARN)"
   ```

4. **Use Environment Variables**
   ```bash
   export IBKR_CLIENT_ID="l1234567890"
   export IBKR_ACCOUNT_ID="DU1234567"
   ```

5. **Firewall Protection**
   ```bash
   # Gateway only accessible locally
   sudo ufw allow from 127.0.0.1 to any port 5000
   ```

## Need Help?

- **Setup Issues**: See [CLIENT_PORTAL_GATEWAY_SETUP.md](CLIENT_PORTAL_GATEWAY_SETUP.md)
- **Launcher Usage**: See [OAUTH_LAUNCHER_README.md](OAUTH_LAUNCHER_README.md)
- **Implementation Details**: See [OAUTH_LAUNCHER_IMPLEMENTATION_SUMMARY.md](OAUTH_LAUNCHER_IMPLEMENTATION_SUMMARY.md)
- **IBKR API Docs**: https://www.interactivebrokers.com/api/doc.html

---

**Last Updated**: 2025-10-23
**Version**: 1.0.0
**Author**: Mohamed Talib
