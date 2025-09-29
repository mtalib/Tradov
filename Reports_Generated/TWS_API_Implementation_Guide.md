# TWS API Implementation Guide

## C### 3. Configure TWS f### 4. Test the Connection
Run the test script we just created:
```bash
cd /home/adam/Projects/Spyder
source .venv/bin/activate
python test_tws_api_connection.py
```

### 5. Key Differences: TWS vs IB Gatewaycess
Once TWS is installed and running:
1. Open TWS application
2. Go to: **File > Global Configuration > API > Settings**
3. Check: **"Enable ActiveX and Socket Clients"**
4. Set **Socket port**:
   - `7497` for Paper Trading
   - `7496` for Live Trading
5. Check: **"Read-Only API"** (initially for safety)
6. Click **OK** and restart TWS

### 4. Test the Connections ✅
- **TWS API v10.40.1 Python client** successfully installed in Spyder venv
- **ibapi package** confirmed working with protobuf support
- **Test script** created: `test_tws_api_connection.py`

## Next Steps

### 1. Configure Market Data Subscriptions (REQUIRED FIRST)
**⚠️ CRITICAL: Must be completed before TWS API testing**

1. **Log in to IBKR Client Portal**: https://www.interactivebrokers.com/portal
2. **Navigate to Market Data Subscriptions**:
   - Go to: Settings > Account Settings > Market Data Subscriptions
3. **Configure API-Only Access**:
   - For **each region or exchange** you need data from:
     - Set subscription type to: **"Non-Display (API trading applications)"**
   - This ensures market data feeds are dedicated to API applications
   - Prevents TWS graphical interface from consuming your data subscriptions
4. **Save and Confirm Changes**:
   - Apply all changes and wait for confirmation
   - Changes may take a few minutes to propagate

**Why This Matters:**
- Market data subscriptions have connection limits
- TWS GUI and API applications compete for the same data feeds
- "Non-Display" mode reserves feeds exclusively for API usage
- Required for proper API market data functionality

### 2. Install TWS Application (Not API)
You need to download and install the actual **Trader Workstation (TWS) application**:
- Download from: https://www.interactivebrokers.com/en/trading/tws.php
- Choose **TWS v10.40.1** (same version as API for compatibility)
- Install the application (not the API SDK we already have)

### 2. Configure TWS for API Access
Once TWS is installed and running:
1. Open TWS application
2. Go to: **File > Global Configuration > API > Settings**
3. Check: **"Enable ActiveX and Socket Clients"**
4. Set **Socket port**:
   - `7497` for Paper Trading
   - `7496` for Live Trading
5. Check: **"Read-Only API"** (initially for safety)
6. Click **OK** and restart TWS

### 3. Test the Connection
Run the test script we just created:
```bash
cd /home/adam/Projects/Spyder
source .venv/bin/activate
python test_tws_api_connection.py
```

### 4. Key Differences: TWS vs IB Gateway
| Aspect | IB Gateway | TWS Application |
|--------|------------|----------------|
| Ports | 4001, 4002 | 7496, 7497 |
| Handshake Bug | ❌ v10.40.1 broken | ✅ v10.40.1 working |
| GUI | Minimal | Full interface |
| Resources | Lighter | Heavier |
| API Access | Direct | Through TWS |

### 6. Integration with Spyder System
After confirming connectivity, update your Spyder modules:
- **SpyderB_Broker/**: Update connection parameters (host, port)
- **SpyderC_MarketData/**: Switch from Gateway to TWS API calls
- **SpyderR_Runtime/**: Update threading for TWS compatibility
- **Configuration files**: Update ports and connection settings

## Research Findings Summary
- **Root Cause**: IB Gateway v10.40.1 has confirmed handshake bug on Linux/Ubuntu
- **Solution**: TWS v10.40.1 application does NOT have this bug
- **Evidence**: Research reports confirm TWS handshake works correctly
- **API Client**: Now properly installed and ready for TWS connection

## Important Notes
- TWS API client (ibapi) ✅ **INSTALLED**
- TWS Application ⏳ **NEEDS TO BE DOWNLOADED/INSTALLED**
- The API client connects TO the TWS application
- Gateway is no longer needed for this solution