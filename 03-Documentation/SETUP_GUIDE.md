# TRADOV OAuth Launcher - Complete Setup Guide

> ⛔ **DEPRECATED:** This guide describes IBKR OAuth setup which is no longer used.  
> Tradov migrated to **Tradier API** (February 2026). See:
> - [ACCOUNT_SETUP_GUIDE.md](./ACCOUNT_SETUP_GUIDE.md) - Current Tradier setup
> - [IBKR_TO_TRADIER_MIGRATION_GUIDE.md](../09-Implementation-History/IBKR_TO_TRADIER_MIGRATION_GUIDE.md) - Migration guide

**Status:** ⚠️ **ARCHIVED - HISTORICAL REFERENCE ONLY**

---

## Issues Encountered & Solutions

### Issue 1: Externally-Managed Python Environment

**Error**: `externally-managed-environment` when running pip install

**Cause**: Ubuntu 24.04+ uses Python 3.13 with PEP 668 protection to prevent breaking system packages.

**Solutions** (Choose ONE):

#### Option A: Use Virtual Environment (RECOMMENDED)

```bash
# Create virtual environment
python3 -m venv ~/tradov_venv

# Activate it
source ~/tradov_venv/bin/activate

# Install dependencies
cd /home/adam/Projects/Tradov/TradovG_GUI
./install_oauth_launcher.sh

# Run launcher (with venv activated)
python TradovG08_IBKRLoginLauncher_OAuth.py
```

To use this permanently:
```bash
# Add to ~/.bashrc
echo 'alias tradov-venv="source ~/tradov_venv/bin/activate"' >> ~/.bashrc
source ~/.bashrc

# Then just run:
tradov-venv
```

#### Option B: Install System-Wide (NOT RECOMMENDED)

```bash
# Use --break-system-packages flag (risky!)
pip install PyJWT cryptography requests --break-system-packages
```

#### Option C: Use pipx for Application

```bash
# Install pipx
sudo apt install pipx

# This won't work directly for the launcher, but good to know
```

### Issue 2: OpenSSL Key Generation Error

**Error**: `genpkey: Unknown option or cipher: pkcs8`

**Cause**: Incorrect openssl syntax. The `-pkcs8` flag doesn't exist; PKCS#8 format is the default for `genpkey`.

**Fixed in**: `generate_oauth_keys.sh` now uses:
```bash
openssl genpkey -algorithm RSA -out private_key.pem -pkeyopt rsa_keygen_bits:2048
```

### Issue 3: PySide6 Not Installed

**Error**: `ModuleNotFoundError: No module named 'PySide6'`

**Cause**: Dashboard requires PySide6 GUI framework

**Solution**:
```bash
# Activate virtual environment first
source ~/tradov_venv/bin/activate

# Install GUI requirements
pip install -r /home/adam/Projects/Tradov/requirements-gui.txt
```

### Issue 4: Tkinter Callback Error

**Error**: `_tkinter.TclError: can't invoke "grab" command: application has been destroyed`

**Cause**: Trying to show messagebox after launcher window was destroyed

**Fixed**: Reordered operations to show message before closing window

---

## Complete Setup Instructions

### Step 1: Activate Your Existing Virtual Environment

```bash
# Navigate to project directory
cd /home/adam/Projects/Tradov/

# Activate the existing .venv
source .venv/bin/activate

# Verify activation
which python  # Should show: /home/adam/Projects/Tradov/.venv/bin/python
```

### Step 2: Install All Dependencies

```bash
cd /home/adam/Projects/Tradov

# Install core dependencies
pip install -r requirements-core.txt

# Install GUI dependencies (includes OAuth libraries)
pip install -r requirements-gui.txt

# Or install just OAuth dependencies
pip install PyJWT>=2.8.0 cryptography>=41.0.0 requests>=2.31.0
```

### Step 3: Generate RSA Key Pair

```bash
cd /home/adam/Projects/Tradov/TradovG_GUI

# Run the fixed key generation script
./generate_oauth_keys.sh
```

This will create:
- Private key: `~/.tradov/keys/private_key.pem` (keep secure!)
- Public key: `~/.tradov/keys/public_key.pem` (upload to IBKR)

### Step 4: Register with IBKR

1. Log in to [IBKR Account Management](https://www.interactivebrokers.com/)
2. Navigate to **Settings** → **API Settings**
3. Click **Create Application** for OAuth
4. Fill in details:
   - Application Name: "TRADOV Trading System"
   - Application Type: "Desktop/Mobile"
5. Upload your public key: `~/.tradov/keys/public_key.pem`
6. **Note your Client ID** (starts with 'l', e.g., `l123456789`)
7. **Note your Account ID** (format: `DU1234567`)

### Step 5: Run the Launcher

```bash
# Make sure virtual environment is activated
source ~/tradov_venv/bin/activate

# Run the launcher
cd /home/adam/Projects/Tradov/TradovG_GUI
python TradovG08_IBKRLoginLauncher_OAuth.py
```

---

## Quick Start Commands

```bash
# Activate existing venv
cd /home/adam/Projects/Tradov/
source .venv/bin/activate

# Install dependencies (one-time)
pip install -r requirements-gui.txt

# Generate keys (one-time)
cd TradovG_GUI
./generate_oauth_keys.sh

# Daily usage
cd /home/adam/Projects/Tradov/
source .venv/bin/activate
cd TradovG_GUI
python TradovG08_IBKRLoginLauncher_OAuth.py
```

---

## Troubleshooting

### Problem: "pip: command not found"

**Solution**:
```bash
sudo apt update
sudo apt install python3-pip python3-venv
```

### Problem: "openssl: command not found"

**Solution**:
```bash
sudo apt install openssl
```

### Problem: Virtual environment doesn't activate

**Check**:
```bash
# Make sure you're using 'source', not 'bash'
source ~/tradov_venv/bin/activate  # Correct
bash ~/tradov_venv/bin/activate    # Wrong!

# Verify activation
echo $VIRTUAL_ENV  # Should show path to venv
which python       # Should show venv python
```

### Problem: Dashboard won't launch

**Check PySide6**:
```bash
source ~/tradov_venv/bin/activate
pip list | grep PySide6

# If not installed:
pip install PySide6>=6.5.0
```

### Problem: "ERROR: No matching distribution found for qtwebengine"

**Cause**: The package `qtwebengine` doesn't exist as a standalone pip package.

**Solution**: QtWebEngine is included in PySide6 6.5+, no separate install needed.

**Fixed**: Remove `qtwebengine>=5.15.0` from `requirements-gui.txt`

If you still see this error:
```bash
# Edit requirements-gui.txt and remove the qtwebengine line
# Then reinstall
source ~/tradov_venv/bin/activate
pip install -r ~/Projects/Tradov/requirements-gui.txt
```

### Problem: Import errors for jwt/cryptography

**Install OAuth dependencies**:
```bash
source ~/tradov_venv/bin/activate
pip install PyJWT cryptography requests
```

---

## Virtual Environment Best Practices

### Auto-Activation

Add to `~/.bashrc`:
```bash
# TRADOV Virtual Environment
alias tradov='cd /home/adam/Projects/Tradov && source .venv/bin/activate'
alias tradov-launch='cd /home/adam/Projects/Tradov && source .venv/bin/activate && python TradovG_GUI/TradovG08_IBKRLoginLauncher_OAuth.py'
```

Then simply run:
```bash
tradov-launch
```

### Deactivation

When done:
```bash
deactivate
```

### Checking Venv Status

```bash
# Check if in venv
if [ -n "$VIRTUAL_ENV" ]; then
    echo "In virtual environment: $VIRTUAL_ENV"
else
    echo "Not in virtual environment"
fi
```

---

## Security Reminders

✅ **Always use virtual environment** - Isolates dependencies
✅ **Keep private key secure** - Never share or commit to Git
✅ **Use paper trading first** - Test before risking real money
✅ **Regular key rotation** - Change keys periodically
✅ **Monitor sessions** - Check for unauthorized access

---

## System Requirements

- **OS**: Ubuntu 20.04+ (or compatible Linux)
- **Python**: 3.9+ (tested on 3.13)
- **Dependencies**:
  - PyJWT >= 2.8.0
  - cryptography >= 41.0.0
  - requests >= 2.31.0
  - PySide6 >= 6.5.0 (for dashboard)
  - tkinter (usually included with Python)

---

## Support

For issues:
1. Check logs in `~/tradov_logs/`
2. Review this setup guide
3. See `OAUTH_LAUNCHER_README.md` for detailed usage
4. Verify all dependencies are installed in venv

---

**Last Updated**: October 23, 2025
**Version**: 2.0.0
