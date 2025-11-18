# Tradier + Polygon Account Setup Guide

**Created:** 2025-11-18
**Status:** IN PROGRESS
**Estimated Time:** 1-2 hours

---

## 🎯 Overview

This guide will walk you through setting up your Tradier and Polygon accounts step-by-step. Follow each section carefully and check off items as you complete them.

---

## Part 1: Tradier Brokerage Account Setup

### Step 1.1: Create Tradier Account (15-30 minutes)

**URL:** https://brokerage.tradier.com/signup

**What You'll Need:**
- [ ] Valid email address
- [ ] Social Security Number (SSN) or Tax ID
- [ ] Bank account information (for funding)
- [ ] Government-issued ID (driver's license or passport)
- [ ] Employment information
- [ ] Net worth and income information

**Account Setup:**

1. **Visit Tradier Signup Page**
   - Go to: https://brokerage.tradier.com/signup
   - Click "Open an Account"

2. **Choose Account Type**
   - Select: **"Tradier Pro"** ($10/month)
   - This plan includes:
     - Commission-free equity and ETF options trading
     - API access (sandbox + live)
     - Real-time market data for account holders
     - Professional trading platform

3. **Fill Out Application**
   - Personal information
   - Address and contact details
   - SSN/Tax ID
   - Employment information
   - Financial information (net worth, income)
   - Trading experience

4. **Review and Submit**
   - Review all information carefully
   - E-sign the agreements
   - Submit application

5. **Wait for Approval**
   - **Typical approval time:** 1-2 business days
   - You'll receive email confirmation
   - Check your email for account status updates

**⚠️ Note:** You can proceed with sandbox API setup while waiting for account approval!

### Step 1.2: Enable API Access (5 minutes)

**After Account Approval:**

1. **Log into Tradier Dashboard**
   - URL: https://dash.tradier.com/

2. **Navigate to API Settings**
   - Click on your profile (top-right)
   - Select "API Access" or "Settings"
   - Find "API Applications" section

3. **Generate Sandbox API Token**
   - Click "Create New Application"
   - Name: "Spyder Trading System - Sandbox"
   - Environment: **Sandbox**
   - Click "Generate Token"
   - **COPY AND SAVE THIS TOKEN IMMEDIATELY**
   - Token format: `xxxxxxxxxxxxxxxxxxxxxxxx` (24-32 chars)

4. **Generate Live API Token (Optional - do this later)**
   - Only generate live token after paper trading validation
   - Name: "Spyder Trading System - Live"
   - Environment: **Live**
   - Click "Generate Token"
   - **COPY AND SAVE THIS TOKEN SEPARATELY**

5. **Note Your Account ID**
   - Find your account ID in the dashboard
   - Format: Usually starts with letters, e.g., "VA12345678"
   - **COPY AND SAVE THIS**

**✅ Checklist:**
- [ ] Tradier account created and approved
- [ ] Sandbox API token generated and saved
- [ ] Account ID noted and saved
- [ ] (Optional) Live API token generated and saved

**Save These Credentials:**
```
TRADIER_SANDBOX_API_KEY: ________________________
TRADIER_LIVE_API_KEY: __________________________ (optional for now)
TRADIER_ACCOUNT_ID: ____________________________
```

---

## Part 2: Polygon.io Account Setup

### Step 2.1: Create Polygon Account (10 minutes)

**URL:** https://polygon.io/pricing

**What You'll Need:**
- [ ] Valid email address
- [ ] Credit card (for subscription)

**Account Setup:**

1. **Visit Polygon Pricing Page**
   - Go to: https://polygon.io/pricing
   - Review the plans

2. **Choose Subscription Plan**
   - **Recommended: "Starter" Plan** ($200/month)
   - Includes:
     - Real-time WebSocket streaming
     - Unlimited symbols
     - Historical data access
     - SIP-consolidated data
     - 5 requests/second (REST API)

   - **Alternative: "Developer" Plan** ($29/month - if testing first)
     - Delayed data (15 minutes)
     - Good for initial testing
     - Can upgrade to Starter later

3. **Create Account**
   - Click "Sign Up" or "Get Started"
   - Enter email address
   - Create password
   - Verify email (check inbox)

4. **Enter Payment Information**
   - Add credit card details
   - Billing address
   - Review charges: $200/month for Starter

5. **Confirm Subscription**
   - Review plan details
   - Accept terms of service
   - Complete signup

**⚠️ Note:** You'll be charged immediately. Make sure you're ready to use the API.

### Step 2.2: Get API Key (2 minutes)

1. **Log into Polygon Dashboard**
   - URL: https://polygon.io/dashboard
   - Login with your credentials

2. **Navigate to API Keys**
   - Click "API Keys" in the sidebar
   - Or go to: https://polygon.io/dashboard/api-keys

3. **Copy Your API Key**
   - Your API key will be displayed
   - Format: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` (32-40 chars)
   - **COPY AND SAVE THIS KEY IMMEDIATELY**
   - Click "Show" or "Copy" button

4. **Test API Key (Optional)**
   - Open terminal and run:
   ```bash
   curl "https://api.polygon.io/v2/aggs/ticker/SPY/prev?apiKey=YOUR_API_KEY_HERE"
   ```
   - Should return JSON with SPY price data
   - If you get an error, check your API key

**✅ Checklist:**
- [ ] Polygon account created
- [ ] Starter plan subscription active
- [ ] API key generated and saved
- [ ] API key tested with curl (optional)

**Save This Credential:**
```
POLYGON_API_KEY: ________________________________
```

---

## Part 3: Configure Spyder Environment

### Step 3.1: Create .env File (5 minutes)

**On your system where Spyder is installed:**

1. **Navigate to Spyder directory**
   ```bash
   cd /home/user/Spyder
   ```

2. **Copy template to .env**
   ```bash
   cp .env.tradier_polygon.template .env
   ```

3. **Set secure permissions**
   ```bash
   chmod 600 .env
   ```

4. **Open .env in text editor**
   ```bash
   nano .env
   # or
   vim .env
   # or
   code .env  # VS Code
   ```

### Step 3.2: Fill in Credentials

**Edit the .env file and replace these values:**

```bash
# ==============================================================================
# REQUIRED: Fill in your API credentials
# ==============================================================================

# Tradier Configuration
TRADIER_API_KEY=YOUR_SANDBOX_TOKEN_HERE  # Paste sandbox token from Step 1.2
TRADIER_ACCOUNT_ID=YOUR_ACCOUNT_ID_HERE  # Paste account ID from Step 1.2

# Polygon Configuration
POLYGON_API_KEY=YOUR_POLYGON_KEY_HERE    # Paste API key from Step 2.2

# Trading Mode (IMPORTANT!)
TRADING_MODE=paper  # Keep as "paper" for testing!

# ==============================================================================
# OPTIONAL: Keep these defaults for now
# ==============================================================================

# These are automatically selected based on TRADING_MODE
TRADIER_LIVE_URL=https://api.tradier.com/v1
TRADIER_SANDBOX_URL=https://sandbox.tradier.com/v1

POLYGON_WS_URL=wss://socket.polygon.io/stocks
POLYGON_REST_URL=https://api.polygon.io

# Default symbols to stream
POLYGON_SYMBOLS=SPY,QQQ,VIX

# Enable features
POLYGON_SUBSCRIBE_TRADES=true
POLYGON_SUBSCRIBE_QUOTES=false
POLYGON_SUBSCRIBE_AGGREGATES=true
```

**Example (with fake credentials):**
```bash
TRADIER_API_KEY=A1B2C3D4E5F6G7H8I9J0K1L2M3N4
TRADIER_ACCOUNT_ID=VA12345678
POLYGON_API_KEY=Z9Y8X7W6V5U4T3S2R1Q0P9O8N7M6L5K4
TRADING_MODE=paper
```

5. **Save and close the file**
   - In nano: Ctrl+X, then Y, then Enter
   - In vim: :wq
   - In VS Code: Ctrl+S

### Step 3.3: Verify .env File

**Check that .env is properly configured:**

```bash
# Make sure .env exists
ls -la .env

# Check permissions (should be -rw-------)
ls -la .env | grep "\-rw-------"

# Verify it's not committed to git
git status | grep .env  # Should show nothing or "ignored"
```

**✅ Checklist:**
- [ ] .env file created from template
- [ ] Credentials filled in (Tradier API key, Account ID, Polygon API key)
- [ ] TRADING_MODE set to "paper"
- [ ] File permissions set to 600
- [ ] File not tracked by git

---

## Part 4: Validate Configuration

### Step 4.1: Run Validation Script (5 minutes)

**This script will test your API connections:**

```bash
cd /home/user/Spyder
python SpyderQ_Scripts/validate_tradier_polygon.py
```

**Expected Output:**

```
╔═══════════════════════════════════════════════════════════════════╗
║   SPYDER - Tradier + Polygon Configuration Validation            ║
╚═══════════════════════════════════════════════════════════════════╝

1. Checking Environment Variables
==================================================
✓ TRADIER_API_KEY: A1B2...N4
✓ TRADIER_ACCOUNT_ID: VA12345678
✓ POLYGON_API_KEY: Z9Y8...K4
✓ TRADING_MODE: paper

2. Validating Tradier API Connection
==================================================
ℹ Using SANDBOX environment: https://sandbox.tradier.com/v1
ℹ Testing GET /user/profile...
✓ User profile retrieved: Your Name
✓ Account balances retrieved: $100,000.00 total equity
✓ Positions retrieved successfully
✓ Market data retrieved: SPY @ $450.25
✓ All Tradier API tests passed!

3. Validating Polygon.io API Connection
==================================================
ℹ Testing GET /v2/aggs/ticker/SPY/prev...
✓ Previous day data: O=449.50, H=451.00, L=449.00, C=450.25
✓ Snapshot retrieved: SPY @ $450.25
✓ All Polygon.io API tests passed!

4. Checking System Dependencies
==================================================
✓ requests: installed (HTTP client library)
✓ websocket: installed (WebSocket client library)
✓ PySide6: installed (Qt6 for Python (UI framework))
✓ dotenv: installed (Environment variable loader)

5. Validation Summary
==================================================
✓ Environment Variables: PASSED
✓ Tradier API Connection: PASSED
✓ Polygon.io API Connection: PASSED
✓ System Dependencies: PASSED

✓ ALL VALIDATION CHECKS PASSED!
You are ready to run Spyder with Tradier + Polygon
```

### Step 4.2: Troubleshooting Validation Errors

**If validation fails, check these common issues:**

**Error: "TRADIER_API_KEY environment variable not set"**
- Solution: Check that .env file exists and has correct variable name
- Run: `cat .env | grep TRADIER_API_KEY`

**Error: "Authentication failed: 401"**
- Solution: Check that API key is correct (no extra spaces)
- Verify you're using the sandbox token if TRADING_MODE=paper
- Regenerate token in Tradier dashboard if needed

**Error: "Request failed: 403"**
- Solution: Tradier account may not be approved yet
- Check email for approval status
- Log into Tradier dashboard to verify account status

**Error: "Polygon API returned status: ERROR"**
- Solution: Check that Polygon API key is correct
- Verify subscription is active (log into Polygon dashboard)
- Check for typos in API key

**Error: "Module 'websocket' not found"**
- Solution: Install missing dependency
- Run: `pip install websocket-client`

**Error: "Module 'PySide6' not found"**
- Solution: Install Qt library
- Run: `pip install PySide6`

**✅ Checklist:**
- [ ] Validation script runs without errors
- [ ] All 4 validation sections pass
- [ ] Tradier API connection successful
- [ ] Polygon API connection successful

---

## Part 5: Test API Connections

### Step 5.1: Test Tradier Client Directly (5 minutes)

**Run the Tradier client in test mode:**

```bash
cd /home/user/Spyder
python SpyderB_Broker/SpyderB40_TradierClient.py
```

**Expected Output:**

```
Tradier Client Test
============================================================
✓ Client created: TradierClient(account=VA12345678, env=sandbox)
✓ Connection test passed
✓ User: Your Name
✓ Balance retrieved
✓ Positions retrieved
✓ Quote retrieved for SPY

✓ All tests passed!
```

**What This Tests:**
- Client initialization
- Authentication
- User profile retrieval
- Account balance queries
- Position queries
- Market data queries

### Step 5.2: Test Polygon Handler (Optional - Requires Qt)

**This test requires a GUI environment (Qt). Skip if headless:**

```bash
cd /home/user/Spyder
python SpyderC_MarketData/SpyderC25_PolygonDataHandler.py
```

**Expected Output:**

```
Polygon Data Handler Test
============================================================
Starting handler: PolygonDataHandler(symbols=['SPY'], status=disconnected)
STATUS: connecting
STATUS: connected
STATUS: authenticated
TRADE: SPY @ $450.25, size=100
TRADE: SPY @ $450.26, size=50
TRADE: SPY @ $450.24, size=200
...
```

**Press Ctrl+C to stop**

**What This Tests:**
- WebSocket connection to Polygon
- Authentication
- Trade stream subscription
- Real-time data reception
- Signal emission (Qt)

**✅ Checklist:**
- [ ] Tradier client test passes
- [ ] (Optional) Polygon handler test shows live data

---

## Part 6: Next Steps

**🎉 Congratulations! You've completed the account setup.**

**Your APIs are now configured and ready to use!**

### What You Can Do Now:

**1. Run Unit Tests (Recommended)**
```bash
pytest SpyderT_Testing/SpyderT40_TradierClient_Test.py -v
```

**2. Run Integration Tests**
```bash
pytest SpyderT_Testing/SpyderT42_Integration_Test.py -v
```

**3. Start Paper Trading**
- See: `4-TODO-LIST/NEXT_STEPS_MIGRATION_ROADMAP.md`
- Week 1-2: Paper trading validation
- Monitor performance and stability

**4. Review Migration Timeline**
- Full migration: 2-4 weeks
- Gradual rollout recommended
- Keep IBKR as backup initially

### Important Reminders:

- ⚠️ **Always start in PAPER/SANDBOX mode**
- ⚠️ **Test for minimum 7 days before going live**
- ⚠️ **Never commit .env to git**
- ⚠️ **Keep API keys secure (chmod 600 .env)**
- ⚠️ **Monitor costs (Tradier $10/month + Polygon $200/month)**

### Support Resources:

**Tradier:**
- Docs: https://docs.tradier.com/
- Support: https://brokerage.tradier.com/contact
- Status: https://status.tradier.com/

**Polygon:**
- Docs: https://polygon.io/docs/
- Support: support@polygon.io
- Status: https://status.polygon.io/

---

## 📋 Final Checklist

**Before Proceeding to Migration:**

- [ ] Tradier account created and approved
- [ ] Tradier sandbox API token generated
- [ ] Tradier account ID noted
- [ ] Polygon account created
- [ ] Polygon subscription active (Starter plan)
- [ ] Polygon API key generated
- [ ] .env file created and configured
- [ ] File permissions set (600)
- [ ] Validation script passes all tests
- [ ] Tradier client test passes
- [ ] (Optional) Polygon handler test shows data
- [ ] Unit tests run successfully
- [ ] Ready to begin paper trading

**Once all items are checked, you're ready to proceed with Week 1 of the migration!**

---

**Document Status:** ✅ COMPLETE
**Next Document:** `NEXT_STEPS_MIGRATION_ROADMAP.md` → Week 1: Paper Trading

**Good luck! 🚀**
