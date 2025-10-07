#!/bin/bash
#
# IB Gateway Connection Test & Wait Script
# Waits for Gateway API to be fully initialized before allowing connections
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🔍 Testing IB Gateway API Readiness${NC}"
echo ""

# Step 1: Check if port is listening
echo -e "${YELLOW}Step 1: Checking if port 4002 is listening...${NC}"
if ! netstat -tuln | grep -q ":4002.*LISTEN"; then
    echo -e "${RED}❌ Port 4002 is NOT listening${NC}"
    echo -e "${YELLOW}💡 Start Gateway first: ./launch_balanced_gateway.sh${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Port 4002 is LISTENING${NC}"
echo ""

# Step 2: Wait for API to be ready (not just port)
echo -e "${YELLOW}Step 2: Waiting for Gateway API to initialize...${NC}"
echo -e "${YELLOW}(Port listening ≠ API ready. Gateway needs ~30-60 seconds after port opens)${NC}"
echo ""

MAX_WAIT=60
WAIT_INTERVAL=5
total_wait=0

cd /home/adam/Projects/Spyder
source .venv/bin/activate

while [ $total_wait -lt $MAX_WAIT ]; do
    echo -e "${YELLOW}Testing API connection (attempt $(($total_wait / $WAIT_INTERVAL + 1)))...${NC}"

    # Try actual API connection
    if timeout 10 python3 << 'EOF' 2>/dev/null
import asyncio
from ib_async import IB

async def test():
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', 4002, clientId=99, timeout=8)
        print("SUCCESS")
        await ib.disconnectAsync()
        return True
    except:
        return False

result = asyncio.run(test())
exit(0 if result else 1)
EOF
    then
        echo -e "${GREEN}✅ Gateway API is READY!${NC}"
        echo -e "${GREEN}✅ Handshake completed successfully${NC}"
        echo ""
        echo -e "${GREEN}🎉 You can now connect with Client IDs 1-10${NC}"
        exit 0
    fi

    total_wait=$((total_wait + WAIT_INTERVAL))
    if [ $total_wait -lt $MAX_WAIT ]; then
        echo -e "${YELLOW}   API not ready yet, waiting ${WAIT_INTERVAL} more seconds...${NC}"
        sleep $WAIT_INTERVAL
    fi
done

echo ""
echo -e "${RED}❌ Gateway API did not become ready after ${MAX_WAIT} seconds${NC}"
echo -e "${YELLOW}💡 Possible issues:${NC}"
echo "   1. Gateway is still initializing (wait longer)"
echo "   2. Account needs API permissions enabled (contact IBKR)"
echo "   3. Gateway configuration issue (check ~/Jts/jts.ini)"
echo ""
echo -e "${YELLOW}💡 Manual check:${NC}"
echo "   Check Gateway GUI - is it logged in and showing 'Connected'?"
exit 1
