#!/bin/bash
# Monitor Gateway startup and test API readiness

echo "🔍 Checking IB Gateway status..."
echo ""

# Check if Gateway process is running
if pgrep -f "java.*GWClient" > /dev/null; then
    PID=$(pgrep -f "java.*GWClient")
    echo "✅ Gateway process running (PID: $PID)"
else
    echo "❌ Gateway process NOT running"
    echo "   → Please start IB Gateway"
    exit 1
fi

# Check if port 4002 is listening
if ss -tuln | grep -q ":4002"; then
    echo "✅ Gateway port 4002 is LISTENING"
else
    echo "❌ Gateway port 4002 NOT listening"
    echo "   → Gateway starting up, please wait..."
    exit 1
fi

# Test if API is accepting connections
echo ""
echo "🧪 Testing API connection..."
RESULT=$(python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(1); result = s.connect_ex(('127.0.0.1', 4002)); s.close(); print(result)" 2>/dev/null)

if [ "$RESULT" = "0" ]; then
    echo "✅ Gateway API is READY and accepting connections!"
    echo ""
    echo "🚀 You can now launch Spyder dashboard"
    echo "   → Click the Spyder icon OR run: ./launch_spyder_single.sh"
    exit 0
elif [ "$RESULT" = "11" ]; then
    echo "⚠️  Gateway running but NOT logged in (EAGAIN error)"
    echo "   → Please complete Gateway login"
    echo "   → Then run this script again to verify"
    exit 1
elif [ "$RESULT" = "111" ]; then
    echo "❌ Gateway refusing connections"
    echo "   → Check Gateway logs for errors"
    exit 1
else
    echo "❌ Unknown connection error (code: $RESULT)"
    exit 1
fi
