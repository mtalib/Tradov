# SPYDER TWS Configuration Guide - Simplified Version

**CRITICAL: Only the essential settings to fix the handshake timeout issue**

## 🚨 Problem Summary
- TCP connection succeeds immediately
- API handshake times out after 4-15 seconds
- Root cause: TWS not sending required handshake messages (nextValidId, managedAccounts)

## ✅ ESSENTIAL TWS SETTINGS (Windows Computer: 192.168.1.4)

### Step 1: Open TWS API Settings
1. Open TWS (Trader Workstation)
2. Go to: **File → Global Configuration → API → Settings**

### Step 2: Configure These EXACT Settings

#### ✅ MUST BE ENABLED:
- **"Enable ActiveX and Socket Clients"** ← CHECK THIS BOX
- **Socket Port**: `7497` (for Paper Trading)

#### ✅ MUST ADD YOUR LINUX IP:
- **"Trusted IPs"** field: Add `192.168.1.9`
  - This is your Linux computer's IP address
  - Prevents connection approval dialogs

#### ❌ CRITICAL - MUST BE DISABLED:
Look for ANY of these settings and UNCHECK/DISABLE them:
- "Download open orders on connection"
- "Download open orders upon connection" 
- "Sync open orders on connect"
- "Retrieve open orders at startup"
- "Auto-download orders"

**Why this matters:** These settings cause TWS to request order history during handshake, which times out and blocks the connection.

#### ⚪ OPTIONAL SETTINGS:
- "Read-Only API": Leave UNCHECKED (unless you only want market data)
- "Allow connections from localhost only": UNCHECK (for remote connections)

### Step 3: Apply and Restart
1. Click **"Apply"** then **"OK"**
2. **RESTART TWS COMPLETELY** (close and reopen)
3. Verify TWS shows "Connected" status (green indicator)

## 🧪 Test the Connection

After configuring TWS, run this test:
```bash
cd /home/adam/Projects/Spyder
python test_maestro_paper_trading.py
```

**Expected Result:**
- Connection should complete in 1-2 seconds
- Should see: "✅ MAESTRO TRIPLE FIX SUCCESS!"

## 🔍 If Still Failing

### Check TWS Status:
1. In TWS, go to **Data → API Connections**
2. You should see your connection attempt listed
3. If no connection appears, the issue is network/firewall

### Check These:
- TWS is logged in (green connection indicator)
- Paper Trading account is active
- No firewall blocking port 7497 on Windows
- Your Linux IP (192.168.1.9) is correctly added to Trusted IPs

### Alternative Diagnostic:
Try connecting from the Windows computer first:
```python
# Run this ON the Windows computer to test localhost
from ib_async import IB
import asyncio

async def test_localhost():
    ib = IB()
    await ib.connectAsync('127.0.0.1', 7497, clientId=99, readonly=True)
    print("Localhost connection successful!")
    ib.disconnect()

asyncio.run(test_localhost())
```

If localhost works but remote fails, it's a network/trusted IP issue.
If localhost also fails, it's a TWS API configuration issue.

## 📞 Success Indicators

When properly configured, you should see:
1. **Immediate TCP connection** (< 100ms)
2. **Quick API handshake** (1-2 seconds)
3. **No timeout errors**
4. **Managed accounts returned**
5. **Server time retrieved successfully**

The key is disabling any order download/sync settings that cause TWS to request large amounts of data during the initial handshake phase.