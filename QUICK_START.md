# 🚀 Spyder Trading System - Quick Start Guide

**IBKR Web API with OAuth 2.0 Authentication**

---

## ⚡ Prerequisites

Before starting, ensure you have:

- [x] IBKR account (paper or live)
- [x] Python 3.8+ installed
- [x] Basic knowledge of command line
- [x] Text editor for configuration

**Estimated Setup Time**: 30-45 minutes

---

## 📋 Step-by-Step Setup

###  1. Register OAuth App with IBKR (15 minutes)

**Required for:** OAuth 2.0 authentication

1. **Log into IBKR**:
   - Go to: https://www.interactivebrokers.com/
   - Sign in to Account Management

2. **Navigate to API Settings**:
   - Settings → API → OAuth Applications
   - Click "Create New OAuth Application"

3. **Configure Your App**:
   - **Application Name**: `Spyder Trading System`
   - **Description**: `Automated options trading system`
   - **Redirect URI**: Not needed for private_key_jwt
   - **Grant Type**: `client_credentials`
   - **Client Authentication Method**: `private_key_jwt`

4. **Save Your Consumer Key**:
   - After creation, IBKR will provide a **Consumer Key** (Client ID)
   - **SAVE THIS** - you'll need it for `.env` configuration
   - Example: `TESTCONS.DEMO.IBKR`

---

### 2. Generate RSA Key Pair (5 minutes)

**Required for:** JWT token signing

```bash
# Navigate to Spyder directory
cd /home/user/Spyder

# Create keys directory
mkdir -p config/keys

# Generate private key (2048-bit RSA)
openssl genrsa -out config/keys/private_key.pem 2048

# Extract public key
openssl rsa -in config/keys/private_key.pem -pubout -out config/keys/public_key.pem

# Secure private key permissions
chmod 600 config/keys/private_key.pem
chmod 644 config/keys/public_key.pem

# Verify keys were created
ls -lh config/keys/
```

**Expected Output**:
```
-rw------- 1 user user 1.7K Nov  9 12:00 private_key.pem
-rw-r--r-- 1 user user  451 Nov  9 12:00 public_key.pem
```

---

### 3. Upload Public Key to IBKR (5 minutes)

1. **In IBKR Account Management**:
   - Settings → API → OAuth Applications
   - Click on your application name
   - Find "Public Key" section

2. **Upload Public Key**:
   - Click "Add Public Key"
   - Open `config/keys/public_key.pem` in a text editor
   - Copy the entire contents (including `-----BEGIN PUBLIC KEY-----` and `-----END PUBLIC KEY-----`)
   - Paste into IBKR's form
   - Click "Save"

3. **Verify**:
   - You should see your public key listed
   - Status should be "Active"

---

### 4. Configure Environment File (5 minutes)

The `.env` file is already created for you. Update it with your credentials:

```bash
# Edit .env file
nano .env
```

**Update these critical fields**:

```bash
# Trading Mode - START WITH PAPER!
TRADING_MODE=paper

# OAuth 2.0 Credentials
IBKR_OAUTH_CONSUMER_KEY=TESTCONS.DEMO.IBKR  # ← YOUR CONSUMER KEY HERE
IBKR_OAUTH_PRIVATE_KEY_PATH=./config/keys/private_key.pem

# Your IBKR Account ID
# Paper accounts start with "DU" (e.g., DU1234567)
IBKR_ACCOUNT_ID=DU1234567  # ← YOUR PAPER ACCOUNT NUMBER HERE
```

**Save and exit** (Ctrl+X, then Y, then Enter)

---

### 5. Install Dependencies (5 minutes)

```bash
# Activate virtual environment (create if needed)
python3 -m venv .venv
source .venv/bin/activate

# Install core + trading dependencies
pip install -r requirements-core.txt
pip install -r requirements-trading.txt

# Optional: Install analysis dependencies
pip install -r requirements-analysis.txt

# Verify installation
python -c "import requests, jwt, cryptography; print('✓ Dependencies installed')"
```

---

### 6. Validate Configuration (2 minutes)

```bash
# Run validation script
python SpyderQ_Scripts/validate_env.py
```

**Expected Output**:
```
==================== SPYDER .ENV CONFIGURATION VALIDATOR ====================
ℹ Validating IBKR Web API OAuth 2.0 configuration...

✓ .env file found: /home/user/Spyder/.env

============================== TRADING MODE ===============================
✓ Trading Mode: paper (SAFE)

========================= OAUTH 2.0 CONFIGURATION =========================
✓ API URL: https://api.ibkr.com/v1/api (Production)
✓ Token URL: https://api.ibkr.com/v1/oauth2/token
✓ Consumer Key: TESTCONS.D... (configured)
✓ Private Key: ./config/keys/private_key.pem (found)
✓ Auth Method: oauth2

========================== ACCOUNT CONFIGURATION ==========================
✓ Account ID: DU1234567 (PAPER account)

=========================== SYSTEM CONFIGURATION ==========================
ℹ Log Level: INFO
✓ Debug Mode: DISABLED

========================= NOTIFICATIONS (Optional) =========================
ℹ Telegram: Not configured (optional)
ℹ Email: Not configured (optional)

============================ VALIDATION SUMMARY ===========================
✓ CONFIGURATION VALID
  All checks passed! Ready for paper trading.
```

---

### 7. Test OAuth Authentication (5 minutes)

```bash
# Test configuration module
python config/config.py
```

**Expected Output**:
```
🌐 SPYDER IBKR Web API Configuration Loaded
   API URL: https://api.ibkr.com/v1/api
   Auth Method: OAuth 2.0 (private_key_jwt)
   Trading Mode: paper

🔍 Testing Web API Configuration...
Authentication Status: ready
Mode: paper
Message: Web API configuration valid (mode: paper)
✅ Configuration is valid and ready for use
```

---

### 8. Run Authentication Tests (5 minutes)

```bash
# Run OAuth 2.0 authentication tests
pytest SpyderT_Testing/SpyderT23_ClientPortal_Auth_Test.py -v
```

**What this tests**:
- JWT token creation
- OAuth token request
- Token refresh logic
- Error handling

---

### 9. Start Paper Trading! (1 minute)

```bash
# Launch Spyder
python SpyderA_Core/SpyderA01_Main.py
```

**You should see**:
```
🌐 SPYDER IBKR Web API Configuration Loaded
   API URL: https://api.ibkr.com/v1/api
   Auth Method: OAuth 2.0 (private_key_jwt)
   Trading Mode: paper

[INFO] Spyder starting in PAPER mode
[INFO] Authenticating with IBKR Web API...
[INFO] OAuth token acquired successfully
[INFO] Session established (valid for 24 hours)
[INFO] Connected to account: DU1234567
[INFO] Risk limits loaded
[INFO] Ready for trading
```

---

## ✅ Post-Setup Checklist

After successful startup, verify:

- [ ] **Mode**: System is in PAPER mode
- [ ] **Authentication**: OAuth token acquired
- [ ] **Account**: Correct paper account (DU...)
- [ ] **Risk Limits**: Loaded successfully
- [ ] **Logs**: No errors in `logs/spyder_webapi.log`

```bash
# Check logs
tail -f logs/spyder_webapi.log
```

---

## 🔧 Troubleshooting

### Problem: "IBKR_OAUTH_CONSUMER_KEY not set"

**Solution**:
```bash
# Verify .env file exists
ls -la .env

# Check consumer key is set
grep IBKR_OAUTH_CONSUMER_KEY .env

# Re-run validation
python SpyderQ_Scripts/validate_env.py
```

---

### Problem: "Private key file not found"

**Solution**:
```bash
# Check if keys exist
ls -la config/keys/

# Regenerate if missing
openssl genrsa -out config/keys/private_key.pem 2048
chmod 600 config/keys/private_key.pem
```

---

### Problem: "OAuth token request failed"

**Possible Causes**:
1. Consumer key doesn't match IBKR app
2. Public key not uploaded to IBKR
3. IBKR OAuth app not approved
4. Network connectivity issues

**Solution**:
```bash
# 1. Verify consumer key matches IBKR
grep CONSUMER_KEY .env

# 2. Check public key in IBKR (via web interface)

# 3. Test with verbose logging
DEBUG_MODE=true python config/config.py

# 4. Check network
ping api.ibkr.com
```

---

### Problem: "Account ID is placeholder value"

**Solution**:
```bash
# Find your paper account ID:
# 1. Log into IBKR Account Management
# 2. Look for paper trading account (starts with "DU")
# 3. Update .env file

nano .env
# Change: IBKR_ACCOUNT_ID=DU1234567
# To your actual account ID
```

---

## 📚 Next Steps

### 1. Configure Trading Strategies

Edit strategy parameters in `config/config.py`:

```python
STRATEGY_CONFIG = {
    "iron_condor": {
        "enabled": True,
        "delta_short": 0.15,
        ...
    },
}
```

### 2. Adjust Risk Limits

Modify risk limits for your comfort level:

```python
TRADING_CONFIG = {
    "risk_limits": {
        "max_daily_loss": 500,  # Adjust for paper trading
        "max_daily_trades": 20,
        ...
    },
}
```

### 3. Set Up Notifications (Optional)

Add Telegram or email alerts:

```bash
# In .env file
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 4. Run Full System Tests

```bash
# Run comprehensive test suite
pytest SpyderT_Testing/SpyderT27_ClientPortal_Integration_Test.py
```

### 5. Monitor System

```bash
# Watch logs in real-time
tail -f logs/spyder_webapi.log

# Check system metrics
python SpyderM_Monitoring/check_status.py
```

---

## ⚠️ Before Live Trading

**DO NOT switch to live trading until**:

- [ ] System runs stable in paper mode for at least 1 week
- [ ] All tests pass consistently
- [ ] Risk limits are appropriate for your account size
- [ ] You understand all strategy parameters
- [ ] You've validated order execution in paper mode
- [ ] Logs show no errors or warnings
- [ ] You've set up proper monitoring and alerts

**To enable live trading**:

```bash
# In .env file:
TRADING_MODE=live
LIVE_TRADING_CONFIRMED=true  # Explicit confirmation required

# Validate BEFORE starting
python SpyderQ_Scripts/validate_env.py
```

---

## 📞 Support & Resources

- **Documentation**: `2-DOCUMENTATION/IBKR Client Portal Web API/`
- **Test Suite**: `SpyderT_Testing/SpyderT2*_ClientPortal_*.py`
- **Configuration**: `config/config.py`
- **Validation**: `python SpyderQ_Scripts/validate_env.py`
- **Logs**: `logs/spyder_webapi.log`

---

## 🎯 Quick Command Reference

```bash
# Validate configuration
python SpyderQ_Scripts/validate_env.py

# Test OAuth authentication
python config/config.py

# Run tests
pytest SpyderT_Testing/SpyderT23_ClientPortal_Auth_Test.py

# Start system
python SpyderA_Core/SpyderA01_Main.py

# Check logs
tail -f logs/spyder_webapi.log

# Monitor system
python SpyderM_Monitoring/check_status.py
```

---

**🎉 Congratulations! Your Spyder trading system is ready for paper trading!**

---

*Remember: Always start with paper trading. Test thoroughly before considering live trading. This system handles real money - precision and caution are paramount.*
