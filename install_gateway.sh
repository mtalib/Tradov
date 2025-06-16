#!/bin/bash

echo "======================================================="
echo "SPYDER - IB Gateway Installer/Launcher"
echo "======================================================="

# Check if IB Gateway is already installed
GATEWAY_DIR="$HOME/Jts"
if [ -d "$GATEWAY_DIR" ]; then
    echo "✅ IB Gateway appears to be installed at $GATEWAY_DIR"
else
    echo "❌ IB Gateway not found, proceeding with installation..."
    echo ""
    
    # Download IB Gateway
    echo "Downloading IB Gateway installer..."
    wget -O ibgateway-installer.sh "https://download2.interactivebrokers.com/installers/ibgateway/latest-standalone/ibgateway-latest-standalone-linux-x64.sh"
    
    # Make executable
    chmod +x ibgateway-installer.sh
    
    # Run installer
    echo "Running installer... Follow the prompts."
    echo "Use these settings:"
    echo "- Install for current user only"
    echo "- Accept license agreement"
    echo "- Select Paper Trading for testing"
    echo ""
    ./ibgateway-installer.sh
fi

echo ""
echo "======================================================="
echo "IB GATEWAY SETUP INSTRUCTIONS"
echo "======================================================="
echo "1. Login to IB Gateway with your credentials:"
echo "   Username: mtalib342"
echo "   Password: ********"
echo ""
echo "2. Approve 2FA on your mobile device when prompted"
echo ""
echo "3. Once logged in, configure API settings:"
echo "   - Go to Settings > API > Settings"
echo "   - Enable API"
echo "   - Set port to 4001 (paper) or 4000 (live)"
echo "   - Check 'Allow connections from localhost'"
echo "   - Save settings"
echo ""
echo "4. Gateway will now be available for API connections"
echo "======================================================="
echo ""
echo "Starting Gateway now..."

# Try to find and start Gateway
gateway_path=$(find "$GATEWAY_DIR" -name "ibgateway" -type f | head -1)
if [ -n "$gateway_path" ]; then
    echo "Found Gateway at: $gateway_path"
    echo "Launching IB Gateway..."
    "$gateway_path" &
    echo "When Gateway starts, login and configure API as instructed above"
else
    echo "❌ Could not find Gateway executable"
    echo "Please start IB Gateway manually from your applications menu"
fi
