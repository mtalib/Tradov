#!/bin/bash
# Spyder Trading Dashboard Launcher with Smart Gateway Connection
# Works regardless of whether Gateway is launched first or Spyder is launched first

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPYDER_DIR="/home/adam/Projects/Spyder"

cd "$SPYDER_DIR"
source .venv/bin/activate

# Function to check if Gateway is running
check_gateway() {
    if nc -z -w2 127.0.0.1 4002 2>/dev/null; then
        return 0  # Gateway is running
    elif nc -z -w2 127.0.0.1 4001 2>/dev/null; then
        return 0  # Gateway is running on live port
    else
        return 1  # Gateway not running
    fi
}

echo "============================================================"
echo "SPYDER Trading Dashboard Launcher"
echo "============================================================"
echo ""

# Check if Gateway is running
if check_gateway; then
    echo "✅ IB Gateway detected - launching with connection..."
    echo ""
else
    echo "⚠️  IB Gateway not detected"
    echo "📊 Launching Spyder in simulation mode"
    echo "💡 Tip: Start Gateway and click 'IB CONNECT' button to connect"
    echo ""
fi

# Launch Spyder with the proven retry logic
python SpyderA_Core/SpyderA01_Main.py

exit_code=$?

if [ $exit_code -eq 134 ]; then
    echo ""
    echo "❌ Spyder crashed (Exit 134 - SIGABRT)"
    echo "💡 This usually means:"
    echo "   1. Qt/GUI issue"
    echo "   2. Connection timeout"
    echo "   3. Memory issue"
    echo ""
    echo "Try:"
    echo "   - Restart Gateway: pkill -f ibgateway && ~/ibgateway/ibgateway &"
    echo "   - Check logs: tail -100 /tmp/spyder_launch.log"
fi

exit $exit_code
