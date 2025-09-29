# Getting TWS (Trader Workstation) Installed and Running

## Current Status ✅
- **TWS API v10.40.1 Python client** successfully installed in Spyder venv
- **ibapi package** confirmed working with protobuf support
- **Test script** created: `test_tws_api_connection.py`

## Step 1: Download TWS Application

You need the actual **Trader Workstation application** (not the API we already have):

### Download Options:
1. **Direct Download**: https://www.interactivebrokers.com/en/trading/tws.php
2. **Choose Your Platform**:
   - Linux (your system)
   - Look for TWS v10.40.1 specifically (matches your API version)

### What You're Looking For:
- File name will be something like: `tws-latest-linux-x64.sh` or `tws-10.40-linux-x64.sh`
- This is an installer script for Linux
- Size: Usually 200-300MB

## Step 2: Install TWS

Once downloaded, install TWS:

```bash
# Make the installer executable
chmod +x tws-*-linux-x64.sh

# Run the installer
./tws-*-linux-x64.sh
```

### Installation Notes:
- Installer will create a directory (usually `~/Jts` or similar)
- TWS will install its own Java runtime
- Installation includes the TWS application executable

## Step 3: Launch TWS

After installation:

```bash
# Navigate to TWS installation directory
cd ~/Jts  # or wherever it installed

# Launch TWS
./tws
```

### What You Should See:
- TWS login window appears
- **Red TWS icon** in your system tray/taskbar
- Login screen asking for your IBKR credentials

## Step 4: Login and Initial Setup

1. **Login** with your Interactive Brokers credentials
2. **Choose Account Type**:
   - Paper Trading (recommended for testing)
   - Live Trading (for actual trading)
3. **TWS Main Interface** should appear

## Step 5: Verify TWS is Running

You'll know TWS is properly running when you see:
- ✅ **Red TWS icon** in system tray
- ✅ TWS main trading interface window
- ✅ Connection status shows "Connected"
- ✅ Market data feeds are active (if subscribed)

## Next Steps (After TWS is Running):

1. **Configure API Settings** in TWS
2. **Set up Market Data Subscriptions** in Client Portal
3. **Test API Connection** with our test script
4. **Integrate with Spyder System**

---

## Troubleshooting

### If Download Fails:
- Try alternative download mirrors on IB website
- Check your internet connection
- Verify you're logged into IBKR account

### If Installation Fails:
- Check file permissions: `ls -la tws-*-linux-x64.sh`
- Try running with sudo if needed: `sudo ./tws-*-linux-x64.sh`
- Check available disk space: `df -h`

### If TWS Won't Start:
- Check Java installation: `java -version`
- Look for error messages in terminal
- Try starting from TWS installation directory

Let me know when you see the red TWS icon - that means we're ready for the next steps!