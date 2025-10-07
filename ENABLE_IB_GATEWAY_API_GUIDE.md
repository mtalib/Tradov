# 🕷️ SPYDER - Enable IB Gateway API Guide

**Date:** 2025-10-07  
**Status:** ✅ IB Gateway Running | ❌ API Not Enabled  
**Issue:** No clients visible in IB Gateway - API access not configured

---

## 🔍 Current Situation

- ✅ **IB Gateway is running** (PID: 258098)
- ✅ **Configuration file is correct** (`jts.ini`)
- ✅ **Paper mode configured** (port 4002)
- ❌ **API access is not enabled** in Gateway GUI
- ❌ **No clients can connect** to Gateway

**Error Message:** `"Enable ActiveX and Socket EClients" is not enabled`

---

## 🎯 Solution: Enable API Through IB Gateway Interface

### Step 1: Open IB Gateway Configuration
1. **Look for the IB Gateway window** on your desktop
2. If not visible, click on the IB Gateway icon in your taskbar/dock
3. The Gateway should show a login screen or main interface

### Step 2: Access API Settings
1. In IB Gateway, click **"Configure"** in the menu bar
2. Select **"Settings"** from the dropdown menu
3. In the Settings window, look for the **"API"** section in the left sidebar
4. Click on **"Settings"** under the API section

### Step 3: Enable API Access
In the API Settings dialog:

1. ✅ **Check the box**: "Enable ActiveX and Socket Clients"
2. ✅ **Verify Socket Port**: Should be set to `4002`
3. ✅ **Check Read-Only API**: Should be **UNCHECKED** (we need full access)
4. ✅ **Trusted IP Addresses**: Add or verify these IPs:
   ```
   127.0.0.1
   192.168.1.0/24
   0.0.0.0
   ```

### Step 4: Apply Settings
1. Click **"OK"** to save the API settings
2. Click **"OK"** to close the main Settings window
3. **Restart IB Gateway** when prompted (or manually restart)

### Step 5: Verify API is Active
After restart, you should see:
- **"API"** status indicator in Gateway interface
- **Socket port 4002** should be listening
- Ready to accept client connections

---

## 🚀 Quick Test After Enabling API

Run this command to test if API is working:

```bash
cd /home/adam/Projects/Spyder
python3 test_simple_gateway_connection.py
```

**Expected Result:**
```
✅ Successfully connected to Paper port!
✅ Received next valid order ID: XXXX
```

---

## 🎯 Launch SPYDER After API is Enabled

Once API is working, launch your trading system:

```bash
# Option 1: Use the connection selector GUI
python3 launch_connection_selector.py

# Option 2: Direct Gateway launch (paper mode)
./launch_spyder_gateway.sh --mode=paper

# Option 3: Quick launch (auto-detects best connection)
./quick_launch_spyder.sh
```

---

## 🔧 Alternative: Manual API Configuration

If GUI access is difficult, you can try this automated approach:

```bash
# Stop Gateway
pkill -f ibgateway

# Wait for clean shutdown
sleep 5

# Edit configuration directly
nano /home/adam/Jts/jts.ini

# Ensure these settings in [IBGateway] section:
ApiOnly=true
ReadOnlyApi=false
LocalServerPort=4002
SocketPort=4002
TrustedIPs=127.0.0.1,192.168.1.0/24,0.0.0.0
allowOrigSub=1

# Start Gateway
/home/adam/Jts/ibgateway/1039/ibgateway &
```

---

## 📊 Expected Client Behavior

Once API is enabled, you should see in IB Gateway:

1. **Client Connections Panel**: Shows active API clients
2. **8 Connected Clients** (Universal 8-Client System):
   - Client 100: Order Execution
   - Client 101: Admin & News
   - Client 102-107: Market Data
3. **Real-time data requests** being processed
4. **No error messages** about socket clients

---

## ❗ Troubleshooting

### If API Still Doesn't Work:

1. **Check Firewall**: Ensure port 4002 isn't blocked
2. **Verify Login**: Make sure you're logged into paper trading account
3. **Restart Computer**: Sometimes required for network changes
4. **Contact IB Support**: If persistent API issues

### Common Issues:

- **"Socket client not allowed"** → Check Trusted IPs
- **"Connection refused"** → API not enabled in GUI
- **"Port already in use"** → Another process using port 4002
- **"Permission denied"** → Run Gateway as proper user

---

## 🎉 Success Indicators

You'll know it's working when:

- ✅ Test connection script succeeds
- ✅ Clients appear in IB Gateway interface
- ✅ SPYDER dashboard launches successfully
- ✅ Market data starts flowing
- ✅ Universal 8-Client Manager shows all connections

---

**Next Steps:** Once API is enabled, launch SPYDER and verify all 8 clients connect successfully to start receiving market data and enable trading functionality.