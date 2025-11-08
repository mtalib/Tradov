# SPYDER OAuth Authentication - Complete Setup Guide

**Version:** 1.0.0  
**Date:** October 24, 2025  
**For:** Dashboard-Integrated OAuth (No Launcher)

---

## 🎯 Overview

This guide walks you through setting up OAuth authentication for the SPYDER Trading Dashboard, allowing direct, secure connection to Interactive Brokers without requiring IB Gateway or browser-based login.

**Key Features:**
- ✅ No separate launcher - OAuth integrated into dashboard
- ✅ One-click authentication from toolbar
- ✅ Automatic token renewal
- ✅ Support for both Paper and Live trading
- ✅ Secure credential storage

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [IBKR OAuth Configuration](#ibkr-oauth-configuration)
4. [First-Time Setup](#first-time-setup)
5. [Daily Usage](#daily-usage)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### 1. System Requirements

- **Operating System:** Ubuntu 25.04 (or similar Linux)
- **Python:** 3.13.3 or higher
- **IBKR Account:** Active Pro account with API access
- **Account Funding:** Account must be funded (demo accounts don't support live data)

### 2. SPYDER Installation

Ensure SPYDER is installed and working:

```bash
cd /home/adam/Projects/Spyder
source .venv/bin/activate
python SpyderG_GUI/SpyderG05_TradingDashboard.py
```

If dashboard opens successfully, you're ready to proceed.

---

## Installation

### Step 1: Install OAuth Dependencies

```bash
cd /home/adam/Projects/Spyder
source .venv/bin/activate

# Install ibind with OAuth support
pip install 'ibind[oauth]'

# Verify installation
python -c "from ibind import IbkrClient; print('✅ ibind installed successfully')"
```

### Step 2: Copy OAuth Files

Place the OAuth module files in your SPYDER directory:

```bash
# Copy OAuth Authentication Manager
cp SpyderB03_IBKRAuthManager.py SpyderB_Broker/

# Copy OAuth Setup Dialog
cp SpyderG06_OAuthSetupDialog.py SpyderG_GUI/

# Verify files are in place
ls -l SpyderB_Broker/SpyderB03_IBKRAuthManager.py
ls -l SpyderG_GUI/SpyderG06_OAuthSetupDialog.py
```

### Step 3: Integrate OAuth into Dashboard

Follow the integration guide (`DASHBOARD_OAUTH_INTEGRATION_GUIDE.md`) to add OAuth support to your dashboard. Or, if you have a pre-integrated version, simply replace your dashboard file:

```bash
# Backup current dashboard
cp SpyderG_GUI/SpyderG05_TradingDashboard.py SpyderG_GUI/SpyderG05_TradingDashboard.py.backup

# Use the OAuth-integrated version
# (Apply the code snippets from DASHBOARD_OAUTH_INTEGRATION_GUIDE.md)
```

### Step 4: Create Certificate Directory

```bash
# Create directory for OAuth certificates
mkdir -p ~/.spyder/certs
chmod 700 ~/.spyder/certs

# Verify directory
ls -ld ~/.spyder/certs
```

---

## IBKR OAuth Configuration

### Step 1: Access IBKR Portal

1. Go to https://portal.interactivebrokers.com
2. Log in with your IBKR credentials

### Step 2: Navigate to OAuth Settings

1. Click your username (top right)
2. Select **"Settings & Account"**
3. Navigate to **"API"** section
4. Click **"OAuth Apps"**

### Step 3: Create OAuth Application

1. Click **"Create OAuth Consumer Key"**
2. Fill in application details:
   - **Application Name:** `SPYDER Trading System`
   - **Application Type:** `Desktop Application`
   - **Redirect URI:** `http://localhost:8080/callback` (required but not used)
3. Click **"Create"**

### Step 4: Get OAuth Credentials

After creation, you'll see:

- **Consumer Key** (starts with uppercase letters/numbers)
- **Consumer Secret** (long alphanumeric string)

⚠️ **IMPORTANT:** Copy these immediately - the Consumer Secret is only shown once!

### Step 5: Generate OAuth Token

1. Still in OAuth Apps section
2. Find your newly created app
3. Click **"Generate OAuth Token"**
4. You'll receive:
   - **OAuth Token**
   - **OAuth Token Secret**

⚠️ **IMPORTANT:** Save these securely - they're only shown once!

### Step 6: Download Certificates

1. In the same OAuth app details
2. Click **"Download Encryption Key"**
   - Saves as: `private_encryption.pem`
3. Click **"Download Signature Key"**
   - Saves as: `private_signature.pem`

4. Move certificates to SPYDER directory:

```bash
mv ~/Downloads/private_encryption.pem ~/.spyder/certs/
mv ~/Downloads/private_signature.pem ~/.spyder/certs/
chmod 600 ~/.spyder/certs/*.pem

# Verify
ls -l ~/.spyder/certs/
```

---

## First-Time Setup

### Step 1: Launch Dashboard

```bash
cd /home/adam/Projects/Spyder
source .venv/bin/activate
python SpyderG_GUI/SpyderG05_TradingDashboard.py
```

**Expected:** Dashboard opens showing "🟡 SIMULATION MODE"

### Step 2: Open OAuth Setup

1. Look for **🔐 Authenticate** button in the toolbar
2. Click it to open the OAuth Setup Dialog

### Step 3: Configure OAuth Credentials

In the OAuth Setup Dialog:

1. **Account Type:** Select `PAPER TRADING` or `LIVE TRADING`

2. **Consumer Key:** Paste from IBKR Portal

3. **Consumer Secret:** Paste from IBKR Portal

4. **OAuth Token:** Paste from IBKR Portal

5. **OAuth Token Secret:** Paste from IBKR Portal

6. **Encryption Certificate:**
   - Click **Browse...**
   - Navigate to `~/.spyder/certs/`
   - Select `private_encryption.pem`

7. **Signature Certificate:**
   - Click **Browse...**
   - Navigate to `~/.spyder/certs/`
   - Select `private_signature.pem`

### Step 4: Test Connection

1. Click **🧪 Test Connection** button
2. Wait for test to complete (5-10 seconds)
3. Should see: "✅ Connection successful!"

If test fails:
- Verify all credentials are correct
- Check certificate files are readable
- Ensure IBKR account is active
- Check your network connection

### Step 5: Save & Connect

1. Click **💾 Save & Connect** button
2. Credentials are saved securely
3. Authentication begins automatically
4. Should see: "✅ Authentication successful!"
5. Dialog closes
6. Dashboard status updates to: "✅ IBKR CONNECTED - PAPER/LIVE"

**🎉 Setup Complete!** Your dashboard is now connected to IBKR.

---

## Daily Usage

### Starting SPYDER with OAuth

```bash
cd /home/adam/Projects/Spyder
source .venv/bin/activate
python SpyderG_GUI/SpyderG05_TradingDashboard.py
```

**What happens:**
1. Dashboard opens
2. System log shows: "📋 OAuth credentials found"
3. After ~2 seconds: "🔄 Auto-authenticating..."
4. Connection status updates: "✅ IBKR CONNECTED"
5. Dashboard switches to live data mode
6. Ready to trade!

**No manual authentication needed!** OAuth automatically reconnects using saved credentials.

### Monitoring Connection Status

Watch the toolbar status indicator:

- 🟡 **SIMULATION MODE** - Not connected, using simulated data
- 🟡 **AUTHENTICATING...** - Connecting to IBKR
- ✅ **IBKR CONNECTED - PAPER TRADING** - Connected to paper trading
- ✅ **IBKR CONNECTED - LIVE TRADING** - Connected to live trading
- 🔴 **AUTHENTICATION FAILED** - Connection failed
- 🔴 **CONNECTION ERROR** - Network or system error

### Re-authenticating

If connection drops or you need to reconnect:

1. Click **🔐 Authenticate** button
2. OAuth dialog opens with saved credentials pre-filled
3. Click **💾 Save & Connect**
4. Connection re-establishes

### Switching Between Paper and Live

To switch account types:

1. Click **🔐 Authenticate** button
2. Select different account type
3. Enter credentials for that account
4. Click **Save & Connect**
5. Dashboard switches to new mode

---

## Troubleshooting

### Problem: "OAuth modules not available"

**Cause:** `ibind` library not installed

**Solution:**
```bash
cd /home/adam/Projects/Spyder
source .venv/bin/activate
pip install 'ibind[oauth]'
```

### Problem: "Auth manager initialization failed"

**Cause:** `SpyderB03_IBKRAuthManager.py` not found

**Solution:**
```bash
# Verify file exists
ls -l SpyderB_Broker/SpyderB03_IBKRAuthManager.py

# If missing, copy it
cp SpyderB03_IBKRAuthManager.py SpyderB_Broker/
```

### Problem: "Failed to load OAuth setup dialog"

**Cause:** `SpyderG06_OAuthSetupDialog.py` not found

**Solution:**
```bash
# Verify file exists
ls -l SpyderG_GUI/SpyderG06_OAuthSetupDialog.py

# If missing, copy it
cp SpyderG06_OAuthSetupDialog.py SpyderG_GUI/
```

### Problem: "Authentication failed: Invalid credentials"

**Cause:** Incorrect OAuth credentials

**Solution:**
1. Verify credentials in IBKR Portal
2. Re-copy Consumer Key, Consumer Secret, OAuth Token, OAuth Token Secret
3. Ensure no extra spaces or characters
4. Try generating new OAuth token in IBKR Portal

### Problem: "Certificate file not found"

**Cause:** Certificate files missing or path incorrect

**Solution:**
```bash
# Check certificates exist
ls -l ~/.spyder/certs/

# If missing, re-download from IBKR Portal
# Move to correct location
mv ~/Downloads/private_*.pem ~/.spyder/certs/
chmod 600 ~/.spyder/certs/*.pem
```

### Problem: "Connection test failed"

**Possible causes and solutions:**

1. **Network issue:**
   - Check internet connection
   - Try: `ping portal.interactivebrokers.com`

2. **IBKR services down:**
   - Check IBKR status page
   - Try again later

3. **Account not active:**
   - Verify account is funded
   - Check account status in IBKR Portal

4. **API not enabled:**
   - Go to IBKR Portal → Settings → API
   - Ensure API access is enabled

### Problem: "Token expired"

**Cause:** OAuth tokens typically expire after 24 hours

**Solution:**
- Dashboard automatically renews tokens
- If renewal fails, click **🔐 Authenticate** to reconnect
- If persistent, generate new OAuth token in IBKR Portal

### Problem: Auto-authentication doesn't work

**Cause:** Credentials not saved or corrupted

**Solution:**
```bash
# Check credentials file exists
ls -l ~/.spyder/ibkr_oauth_credentials.json

# If exists, verify it's not corrupted
cat ~/.spyder/ibkr_oauth_credentials.json

# If corrupted, delete and re-setup
rm ~/.spyder/ibkr_oauth_credentials.json
# Then setup again through dashboard
```

### Problem: "Permission denied" when accessing certificates

**Cause:** Certificate file permissions too restrictive

**Solution:**
```bash
# Fix permissions
chmod 600 ~/.spyder/certs/*.pem

# Verify
ls -l ~/.spyder/certs/
```

---

## Security Best Practices

### 1. Protect Your Credentials

- ✅ Never share Consumer Secret, OAuth Token Secret, or certificates
- ✅ Don't commit credentials to version control
- ✅ Use restrictive file permissions (600)
- ✅ Store backups in encrypted storage

### 2. Secure Your System

- ✅ Use strong system password
- ✅ Enable disk encryption
- ✅ Keep system updated
- ✅ Use firewall

### 3. Monitor Your Account

- ✅ Regularly check IBKR account activity
- ✅ Enable two-factor authentication on IBKR account
- ✅ Review API access logs in IBKR Portal
- ✅ Immediately revoke access if compromised

### 4. Certificate Management

- ✅ Keep certificates in `~/.spyder/certs/` only
- ✅ Never copy to USB drives or cloud storage
- ✅ Don't email certificates
- ✅ Generate new certificates if system compromised

### 5. Credential Rotation

Consider rotating credentials periodically:

1. Generate new OAuth token in IBKR Portal every 90 days
2. Delete old token in IBKR Portal
3. Update credentials in SPYDER dashboard
4. Test connection

---

## Advanced Configuration

### Custom Credential Storage Location

By default, credentials are stored in `~/.spyder/ibkr_oauth_credentials.json`

To use a custom location:

```python
# In your code
auth_manager = IBKRAuthManager(config_path="/path/to/custom/location.json")
```

### Logging Configuration

OAuth authentication logs to the SPYDER system log:

```bash
# View logs
tail -f ~/.spyder/spyder.log | grep -i oauth

# Or in dashboard system log panel
```

### Multiple Accounts

To switch between multiple IBKR accounts:

1. Each account needs separate OAuth credentials
2. Save credentials for each account
3. Switch by re-running OAuth setup with different credentials
4. Dashboard will authenticate with most recently saved credentials

---

## FAQ

**Q: Do I need IB Gateway?**  
A: No! OAuth authentication connects directly to IBKR without requiring IB Gateway.

**Q: Can I use this with demo account?**  
A: No. Demo accounts don't support real-time market data or OAuth authentication. You need a funded Pro account.

**Q: How long do OAuth tokens last?**  
A: OAuth tokens typically last 24 hours. SPYDER automatically renews them before expiration.

**Q: What happens if my internet disconnects?**  
A: SPYDER will detect the disconnection and attempt to reconnect automatically. If reconnection fails, you may need to manually re-authenticate.

**Q: Can I run SPYDER on multiple computers?**  
A: Yes, but you'll need to setup OAuth on each computer separately. Credentials don't sync automatically.

**Q: Is my data secure?**  
A: Yes. Credentials are stored locally with restrictive permissions. Authentication uses industry-standard OAuth 1.0a protocol with cryptographic signatures.

**Q: Can I share my SPYDER installation with others?**  
A: Never share your OAuth credentials or certificates. Each user should setup their own OAuth authentication with their IBKR account.

**Q: What if I forget to save credentials?**  
A: If you close the OAuth dialog without saving, you'll need to enter credentials again next time. Always click "Save & Connect" to persist credentials.

**Q: How do I completely remove OAuth?**  
A: Delete the credentials file and certificates:
```bash
rm ~/.spyder/ibkr_oauth_credentials.json
rm ~/.spyder/certs/private_*.pem
```

---

## Support Resources

### IBKR Documentation
- OAuth Setup: https://www.interactivebrokers.com/en/trading/oauth.php
- API Documentation: https://www.interactivebrokers.com/api/doc.html
- Portal: https://portal.interactivebrokers.com

### SPYDER Resources
- System Logs: `~/.spyder/spyder.log`
- Integration Guide: `DASHBOARD_OAUTH_INTEGRATION_GUIDE.md`
- OAuth Manager Code: `SpyderB_Broker/SpyderB03_IBKRAuthManager.py`

### Get Help
1. Check system logs for error messages
2. Review this guide's troubleshooting section
3. Verify all prerequisites are met
4. Test each component individually

---

## Summary

**Setup Time:** ~15-20 minutes  
**Complexity:** Medium  
**Result:** Seamless OAuth authentication integrated into SPYDER dashboard

**Benefits:**
- ✅ No separate launcher needed
- ✅ No IB Gateway required
- ✅ No browser-based login
- ✅ Automatic reconnection
- ✅ Secure credential storage
- ✅ Support for Paper and Live trading

**Your SPYDER dashboard is now OAuth-enabled and ready for trading! 🚀**

---

**Document Version:** 1.0.0  
**Last Updated:** October 24, 2025  
**Status:** ✅ Production Ready
