# SPYDER OAuth Launcher - User Guide

## Overview

The SPYDER OAuth Launcher (`SpyderG08_IBKRLoginLauncher_OAuth.py`) is an enhanced GUI launcher that provides secure OAuth 2.0 with JWT authentication for the IBKR Web API. This eliminates the need for browser-based authentication and provides a more secure, programmatic authentication method suitable for automated trading systems.

## Features

### Three Launch Modes

1. **Dashboard Only** - Visualization mode without IBKR connection
   - Uses simulated market data
   - Perfect for testing and analysis
   - No authentication required

2. **IBKR Web API - Paper Trading** - Safe simulation environment
   - OAuth 2.0 with JWT authentication
   - Virtual money trading
   - All features available without financial risk
   - Requires OAuth configuration

3. **IBKR Web API - Live Trading** - Real money trading
   - OAuth 2.0 with JWT authentication
   - Requires verified IBKR Live Trading account
   - ⚠️ **REAL MONEY MODE** ⚠️
   - Exercise extreme caution

### Security Features

- **OAuth 2.0 with JWT** - Industry-standard secure authentication
- **Private Key Authentication** - No credential transmission over network
- **Stateless Authentication** - Each request is cryptographically authenticated
- **Session Timeout Protection** - Automatic security timeout after 30 minutes
- **Secure Configuration Storage** - Private keys are never saved to disk
- **Access Token Management** - Automatic token refresh before expiration

## Prerequisites

### 1. Install Required Dependencies

```bash
# Install OAuth and cryptography dependencies
pip install PyJWT>=2.8.0 cryptography>=41.0.0 requests>=2.31.0

# Or install all GUI requirements
pip install -r requirements-gui.txt
```

### 2. Set Up IBKR Client Portal Gateway

**IMPORTANT**: The IBKR Web API requires the Client Portal Gateway to be running locally. This acts as a proxy between your application and IBKR's servers.

📖 **See [CLIENT_PORTAL_GATEWAY_SETUP.md](CLIENT_PORTAL_GATEWAY_SETUP.md) for complete setup instructions**

Quick start:
```bash
# Using Docker (recommended)
./start_gateway.sh paper   # For paper trading
./start_gateway.sh live    # For live trading
```

The gateway runs on `https://localhost:5000` and proxies your API calls to IBKR.

### 3. Generate RSA Key Pair for OAuth

Use the provided script to generate your OAuth keys:

```bash
cd SpyderG_GUI
./generate_oauth_keys.sh
```

This creates:
- `~/.spyder/keys/private_key.pem` (keep secure!)
- `~/.spyder/keys/public_key.pem` (upload to IBKR)

### 4. Register OAuth Application with IBKR

1. Log in to your IBKR account
2. Navigate to **Account Management** → **Settings** → **API** → **OAuth Applications**
3. Create a new OAuth application:
   - Application Name: "SPYDER Trading System"
   - Redirect URI: `https://localhost:5000/oauth/callback`
   - Upload your `~/.spyder/keys/public_key.pem` file
4. Note your **Client ID** (starts with 'l' followed by numbers)
5. Note your **Account ID** (format: DU1234567 for paper, U1234567 for live)

## Usage

### Starting the Launcher

```bash
# From the Spyder root directory
cd /home/adam/Projects/Spyder/
source .venv/bin/activate
python SpyderG_GUI/SpyderG08_IBKRLoginLauncher_OAuth.py
```

### Configuration

#### For Paper Trading:

1. Select "IBKR Web API – Paper Trading (OAuth 2.0)"
2. Enter your OAuth credentials:
   - **CLIENT ID**: Your OAuth client ID from IBKR (e.g., `l123456789`)
   - **ACCOUNT ID**: Your paper trading account ID (e.g., `DU1234567`)
   - **PRIVATE KEY**: Browse to your `private_key.pem` file
   - **ENVIRONMENT**: Select "Paper"
3. Check "Remember configuration" to save settings (private key path not saved)
4. Click **CONNECT** to authenticate
5. Once connected, click **🚀 LAUNCH** to start the system

#### For Live Trading:

1. Select "IBKR Web API – Live Trading (OAuth 2.0)"
2. Enter your OAuth credentials:
   - **CLIENT ID**: Your OAuth client ID from IBKR
   - **ACCOUNT ID**: Your live trading account ID
   - **PRIVATE KEY**: Browse to your `private_key.pem` file
   - **ENVIRONMENT**: Select "Live"
3. Check "Remember configuration" to save settings (private key path not saved)
4. Click **CONNECT** to authenticate
5. Confirm the warning about real money trading
6. Once connected, click **🚀 LAUNCH** to start the system

#### For Dashboard Only:

1. Select "Dashboard Only – Visualization Mode"
2. Click **🚀 LAUNCH** (no authentication needed)

## OAuth 2.0 Authentication Flow

### How It Works

1. **JWT Generation**: The client application generates a JSON Web Token (JWT) signed with your private key
2. **Client Assertion**: The JWT is sent as a `client_assertion` to the IBKR authorization server
3. **Server Validation**: IBKR validates the JWT using your registered public key
4. **Access Token**: Upon successful validation, you receive an access token
5. **API Calls**: The access token is used in subsequent HTTPS REST API calls
6. **Token Refresh**: Tokens are automatically refreshed before expiration (typically 24 hours)

### Security Benefits

- **No Credential Transmission**: Eliminates transmission of sensitive login credentials
- **No Persistent Secrets**: No need to maintain persistent session secrets
- **Cryptographic Authentication**: Each request is signed with your private key
- **Ideal for Automation**: Perfect for web and cloud environments

## Configuration Files

### Launcher Configuration

The launcher saves your preferences to:
```
~/Projects/Spyder/config/launcher_config_oauth.ini
```

**Saved Settings:**
- Last selected launch mode
- Client IDs (if "Remember configuration" is checked)
- Account IDs (if "Remember configuration" is checked)
- Environment preference (paper/live)
- Session timestamp

**NOT Saved (for security):**
- Private key file paths
- Access tokens
- Private keys themselves

### Session Timeout

- Default timeout: **30 minutes** of inactivity
- After timeout, you must re-enter your private key path
- This prevents unauthorized access if you leave your system unattended

## Troubleshooting

### Connection Issues

**Problem**: "Failed to connect to IBKR Trading via OAuth"

**Solutions**:
1. Verify your Client ID is correct (starts with 'l')
2. Verify your Account ID is correct (format: DU1234567)
3. Ensure your private key file is valid and accessible
4. Confirm your environment matches your account type
5. Check your network connection
6. Verify IBKR API services are available

### Private Key Issues

**Problem**: "Invalid private key format" or "Cannot read private key file"

**Solutions**:
1. Ensure the key was generated correctly:
   ```bash
   openssl genpkey -algorithm RSA -out private_key.pem -pkcs8
   ```
2. Verify file permissions (should be readable)
3. Check that the file is not corrupted
4. Ensure it's an RSA key (not EC or other algorithm)

### Token Expiration

**Problem**: "Access token expired"

**Solution**: The system automatically refreshes tokens. If you see this error:
1. Click **CONNECT** again to re-authenticate
2. Check the logs for more details
3. Verify your system clock is synchronized

### Import Errors

**Problem**: "Unable to import 'jwt'" or "Unable to import 'cryptography'"

**Solution**:
```bash
pip install PyJWT cryptography requests
```

## Command-Line Arguments

The launcher passes configuration to the main system:

```bash
# Paper Trading
python SpyderG05_TradingDashboard.py \
    --mode paper \
    --client_id l123456789 \
    --account_id DU1234567 \
    --private_key ~/.spyder/keys/private_key.pem \
    --environment paper \
    --api oauth

# Live Trading
python SpyderG05_TradingDashboard.py \
    --mode live \
    --client_id l123456789 \
    --account_id DU9876543 \
    --private_key ~/.spyder/keys/private_key.pem \
    --environment live \
    --api oauth

# Dashboard Only
python SpyderG05_TradingDashboard.py --mode visualization
```

## Security Best Practices

### Private Key Management

1. **Never share your private key** - Treat it like a password
2. **Store securely** - Use restricted file permissions (chmod 600)
3. **Never commit to version control** - Add to .gitignore
4. **Regular rotation** - Rotate keys periodically for better security
5. **Backup safely** - Keep encrypted backups in secure locations

### Access Control

1. **Use Paper Trading first** - Always test with paper trading
2. **Monitor sessions** - Don't leave the system unattended
3. **Review logs regularly** - Check for unauthorized access attempts
4. **Limit system access** - Only run on trusted systems
5. **Use session timeout** - Keep the 30-minute timeout enabled

### OAuth Token Security

1. **Tokens are temporary** - They expire after 24 hours
2. **Not stored persistently** - Tokens are not saved to disk
3. **Automatic refresh** - System handles token refresh automatically
4. **Revoke if compromised** - Contact IBKR immediately if compromised

## Version Information

- **Current Version**: 2.0.0
- **Build Date**: 2025-10-23
- **Author**: Mohamed Talib
- **Module**: SpyderG08_IBKRLoginLauncher_OAuth.py

## Related Documentation

- **IBKR OAuth Documentation**: https://www.interactivebrokers.com/api/
- **JWT Standard**: https://jwt.io/
- **OAuth 2.0 Specification**: https://oauth.net/2/

## Support

For issues or questions:
1. Check the logs in `~/spyder_logs/`
2. Review this documentation
3. Consult IBKR API documentation
4. Contact system administrator

---

**⚠️ Important Security Notice**

This launcher handles sensitive authentication credentials. Always:
- Keep your private key secure
- Never share your OAuth credentials
- Monitor your trading activity
- Use paper trading for testing
- Exercise extreme caution with live trading

**Live trading involves real money and financial risk. Trade responsibly.**
