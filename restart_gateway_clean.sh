#!/bin/bash
#
# IB Gateway Emergency Restart - Fix Stuck CLOSE-WAIT Connections
#
# Problem: Gateway has 53+ stuck CLOSE-WAIT connections blocking new connections
# Solution: Restart Gateway to clear the socket queue
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${RED}🚨 IB GATEWAY SOCKET QUEUE IS FULL!${NC}"
echo ""
echo "Stuck connections found:"
ss -tan | grep -c "CLOSE-WAIT.*4002" | xargs echo "  - CLOSE-WAIT sockets:"
echo ""

# Step 1: Kill Gateway (forceful)
echo -e "${YELLOW}1️⃣  Force-killing IB Gateway (PID 2402825)...${NC}"
kill -9 2402825 2>/dev/null || pkill -9 -f "ibgateway" || echo "Gateway already stopped"
sleep 3

# Verify Gateway is dead
if pgrep -f "ibgateway" > /dev/null; then
    echo -e "${RED}❌ Gateway still running! Trying harder...${NC}"
    pkill -9 -f "java.*ibgateway"
    sleep 2
fi

# Step 2: Verify sockets are cleared
echo -e "${YELLOW}2️⃣  Checking if sockets are cleared...${NC}"
REMAINING=$(ss -tan | grep -c "4002" || echo "0")
echo "  Remaining sockets: $REMAINING"

if [ "$REMAINING" -gt 1 ]; then
    echo -e "${YELLOW}⚠️  Some sockets still lingering (will timeout naturally)${NC}"
fi

# Step 3: Start fresh Gateway
echo -e "${YELLOW}3️⃣  Starting fresh IB Gateway...${NC}"
cd /home/adam/Projects/Spyder

# Use the balanced launcher
if [ -f "./launch_balanced_gateway.sh" ]; then
    ./launch_balanced_gateway.sh &
    GATEWAY_PID=$!
    echo "  Gateway started with PID: $GATEWAY_PID"
else
    echo -e "${RED}❌ launch_balanced_gateway.sh not found${NC}"
    exit 1
fi

# Step 4: Wait for Gateway to initialize
echo -e "${YELLOW}4️⃣  Waiting for Gateway to initialize (20 seconds)...${NC}"
for i in {1..20}; do
    echo -n "."
    sleep 1

    # Check if listening
    if netstat -tuln 2>/dev/null | grep -q ":4002.*LISTEN"; then
        echo ""
        echo -e "${GREEN}✅ Gateway is listening!${NC}"
        break
    fi
done
echo ""

# Step 5: Verify clean socket state
echo -e "${YELLOW}5️⃣  Verifying socket state...${NC}"
LISTEN_COUNT=$(ss -tan | grep -c "LISTEN.*4002" || echo "0")
CLOSE_WAIT_COUNT=$(ss -tan | grep -c "CLOSE-WAIT.*4002" || echo "0")

echo "  LISTEN sockets: $LISTEN_COUNT"
echo "  CLOSE-WAIT sockets: $CLOSE_WAIT_COUNT"

if [ "$LISTEN_COUNT" -ge 1 ] && [ "$CLOSE_WAIT_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ Gateway socket state is CLEAN!${NC}"
else
    echo -e "${YELLOW}⚠️  Socket state not optimal yet${NC}"
fi

# Step 6: Test connection
echo -e "${YELLOW}6️⃣  Testing connection from venv...${NC}"
cd /home/adam/Projects/Spyder
source .venv/bin/activate

python3 << 'EOF'
from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient, IBConfig
import sys

try:
    c = IBConfig()
    c.client_id = 88
    c.timeout = 10
    client = SpyderClient(config=c)

    print("Attempting connection...")
    if client.connect_sync():
        print("✅ CONNECTION SUCCESSFUL!")
        print("Gateway is ready for Spyder Dashboard!")
        client.disconnect()
        sys.exit(0)
    else:
        print("❌ Connection failed - Gateway may need more time")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 SUCCESS! Gateway is ready!${NC}"
    echo -e "${YELLOW}💡 Launch dashboard with: ./launch_dashboard_venv.sh${NC}"
else
    echo ""
    echo -e "${RED}❌ Connection still failing${NC}"
    echo -e "${YELLOW}💡 Gateway may need more initialization time. Wait 30 seconds and try:${NC}"
    echo "   source .venv/bin/activate && python launch_dashboard_production.py"
fi
