#!/bin/bash
# ==============================================================================
# SPYDER OAuth Launcher - RSA Key Generation Script
# ==============================================================================
# This script generates an RSA key pair for IBKR OAuth authentication
# Author: Mohamed Talib
# Date: 2025-10-23
# ==============================================================================

set -e  # Exit on error

echo "=========================================="
echo "SPYDER OAuth - RSA Key Generation"
echo "=========================================="
echo ""

# Check if openssl is available
if ! command -v openssl &> /dev/null; then
    echo "❌ ERROR: openssl is not installed"
    echo "Please install openssl: sudo apt install openssl"
    exit 1
fi

# Set key directory
KEY_DIR="$HOME/.spyder/keys"
PRIVATE_KEY="$KEY_DIR/private_key.pem"
PUBLIC_KEY="$KEY_DIR/public_key.pem"

# Create directory if it doesn't exist
if [ ! -d "$KEY_DIR" ]; then
    echo "📁 Creating secure key directory: $KEY_DIR"
    mkdir -p "$KEY_DIR"
    chmod 700 "$KEY_DIR"
    echo "✅ Directory created with secure permissions (700)"
    echo ""
fi

# Check if keys already exist
if [ -f "$PRIVATE_KEY" ] || [ -f "$PUBLIC_KEY" ]; then
    echo "⚠️  WARNING: Key files already exist!"
    echo "   Private key: $PRIVATE_KEY"
    echo "   Public key:  $PUBLIC_KEY"
    echo ""
    read -p "Do you want to overwrite them? (yes/no): " response
    if [ "$response" != "yes" ]; then
        echo "Aborted. Existing keys preserved."
        exit 0
    fi
    echo ""
fi

# Generate private key
echo "🔐 Generating RSA private key..."
openssl genpkey -algorithm RSA -out "$PRIVATE_KEY" -pkeyopt rsa_keygen_bits:2048 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Private key generated: $PRIVATE_KEY"
else
    echo "❌ ERROR: Failed to generate private key"
    exit 1
fi

# Secure private key
chmod 600 "$PRIVATE_KEY"
echo "✅ Private key secured with permissions (600)"
echo ""

# Extract public key
echo "🔓 Extracting public key..."
openssl rsa -pubout -in "$PRIVATE_KEY" -out "$PUBLIC_KEY" 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Public key extracted: $PUBLIC_KEY"
else
    echo "❌ ERROR: Failed to extract public key"
    exit 1
fi

chmod 644 "$PUBLIC_KEY"
echo "✅ Public key secured with permissions (644)"
echo ""

# Display key information
echo "=========================================="
echo "RSA Key Pair Generated Successfully!"
echo "=========================================="
echo ""
echo "📄 Files created:"
echo "   Private key: $PRIVATE_KEY"
echo "   Public key:  $PUBLIC_KEY"
echo ""
echo "🔐 Key Information:"
openssl rsa -in "$PRIVATE_KEY" -text -noout 2>&1 | grep "Private-Key"
echo ""

echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. Keep your PRIVATE KEY secure!"
echo "   ⚠️  NEVER share or commit this file to version control"
echo "   Location: $PRIVATE_KEY"
echo ""
echo "2. Register your PUBLIC KEY with IBKR:"
echo "   a. Log in to IBKR Account Management"
echo "   b. Navigate to Settings → API"
echo "   c. Create a new OAuth application"
echo "   d. Upload this file: $PUBLIC_KEY"
echo "   e. Note your Client ID (starts with 'l')"
echo "   f. Note your Account ID (format: DU1234567)"
echo ""
echo "3. Use the OAuth Launcher:"
echo "   python SpyderG_GUI/SpyderG08_IBKRLoginLauncher_OAuth.py"
echo ""
echo "📖 See OAUTH_LAUNCHER_README.md for complete documentation"
echo ""

# Display public key content for easy upload
echo "=========================================="
echo "Public Key Content (for IBKR upload)"
echo "=========================================="
echo ""
cat "$PUBLIC_KEY"
echo ""
echo "=========================================="
echo ""
