#!/bin/bash

echo "======================================================="
echo "SPYDER - IB Gateway Launcher"
echo "======================================================="

# Check if IB Gateway is installed
GATEWAY_DIR="$HOME/Jts"
if [ ! -d "$GATEWAY_DIR" ]; then
    echo "❌ IB Gateway not found at $GATEWAY_DIR"
    echo "Please install IB Gateway first:"
    echo "  wget https://download2.interactivebrokers.com/installers/ibgateway/latest-standalone/ibgateway-latest-standalone-linux-x64.sh"
    echo "  chmod +x ibgateway-latest-standalone-linux-x64.sh"
    echo "  ./ibgateway-latest-standalone-linux-x64.sh"
    exit 1
fi

# Find the Gateway executable
GATEWAY_EXEC=$(find "$GATEWAY_DIR" -name "ibgateway" -type f | head -1)
if [ -z "$GATEWAY_EXEC" ]; then
    echo "❌ IB Gateway executable not found"
    exit 1
fi

echo "✅ Starting IB Gateway..."
echo "📱 Please approve 2FA on your mobile device when prompted"
echo "🔌 API will be available on port 4001 (paper) or 4000 (live)"
echo ""

# Start IB Gateway
"$GATEWAY_EXEC"
