#!/bin/bash
# ==============================================================================
# SPYDER OAuth Launcher - Installation Script
# ==============================================================================
# This script installs the required dependencies for the SPYDER OAuth Launcher
# Author: Mohamed Talib
# Date: 2025-10-23
# ==============================================================================

set -e  # Exit on error

echo "=========================================="
echo "SPYDER OAuth Launcher - Installation"
echo "=========================================="
echo ""

# Check if we're in the Spyder project directory
if [ ! -d "/home/adam/Projects/Spyder/.venv" ]; then
    echo "⚠️  WARNING: Expected virtual environment not found at:"
    echo "   /home/adam/Projects/Spyder/.venv"
    echo ""
    echo "Please ensure you're in the Spyder project and have created .venv:"
    echo "   cd /home/adam/Projects/Spyder/"
    echo "   python3 -m venv .venv"
    echo "   source .venv/bin/activate"
    echo ""
    exit 1
fi

# Detect if we're in the correct virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  WARNING: Virtual environment not activated"
    echo ""
    echo "Please activate the Spyder virtual environment first:"
    echo "   cd /home/adam/Projects/Spyder/"
    echo "   source .venv/bin/activate"
    echo ""
    exit 1
elif [[ "$VIRTUAL_ENV" != *"Projects/Spyder/.venv"* ]]; then
    echo "⚠️  WARNING: Wrong virtual environment activated"
    echo "   Current: $VIRTUAL_ENV"
    echo "   Expected: /home/adam/Projects/Spyder/.venv"
    echo ""
    echo "Please activate the correct virtual environment:"
    echo "   cd /home/adam/Projects/Spyder/"
    echo "   source .venv/bin/activate"
    echo ""
    exit 1
else
    echo "✅ Correct virtual environment activated: .venv"
    PIP_FLAGS=""
fi

# Check if pip is available
if ! command -v pip &> /dev/null; then
    echo "❌ ERROR: pip is not installed"
    echo "Please install pip first: sudo apt install python3-pip"
    exit 1
fi

echo "📦 Installing OAuth and Cryptography dependencies..."
echo ""

# Install OAuth dependencies
pip install PyJWT>=2.8.0 --upgrade $PIP_FLAGS
pip install cryptography>=41.0.0 --upgrade $PIP_FLAGS
pip install requests>=2.31.0 --upgrade $PIP_FLAGS

echo ""
echo "✅ OAuth dependencies installed successfully!"
echo ""

# Check if tkinter is available (usually comes with Python)
python3 -c "import tkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  WARNING: tkinter is not installed"
    echo "Please install tkinter: sudo apt install python3-tk"
    echo ""
fi

echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Generate RSA key pair:"
echo "   cd /home/adam/Projects/Spyder/SpyderG_GUI"
echo "   ./generate_oauth_keys.sh"
echo ""
echo "2. Secure your private key:"
echo "   chmod 600 ~/.spyder/keys/private_key.pem"
echo ""
echo "3. Register with IBKR:"
echo "   - Log in to IBKR Account Management"
echo "   - Navigate to Settings → API"
echo "   - Create OAuth application"
echo "   - Upload public_key.pem"
echo "   - Note your Client ID and Account ID"
echo ""
echo "4. Run the launcher:"
echo "   cd /home/adam/Projects/Spyder/SpyderG_GUI"
echo "   python SpyderG08_IBKRLoginLauncher_OAuth.py"
echo ""
echo "📖 See OAUTH_LAUNCHER_README.md for complete documentation"
echo ""
