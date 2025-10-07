#!/bin/bash
# IB Gateway Reset Script
# Cleanly restart IB Gateway and clear all stale connections

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}IB Gateway Reset Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Stop Gateway
echo -e "${BLUE}Step 1: Stopping IB Gateway...${NC}"
if pgrep -f "ibgateway" > /dev/null; then
    pkill -f "ibgateway"
    echo -e "${GREEN}✅ Gateway process terminated${NC}"
    sleep 2
else
    echo -e "${YELLOW}⚠️  Gateway was not running${NC}"
fi

# Step 2: Check for stale connections
echo -e "${BLUE}Step 2: Checking for stale connections...${NC}"
STALE_CONN=$(ss -tnp 2>/dev/null | grep -c ":4002" || true)
if [ "$STALE_CONN" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Found $STALE_CONN stale connection(s) on port 4002${NC}"
    echo -e "${BLUE}Listing stale connections:${NC}"
    ss -tnp 2>/dev/null | grep ":4002" | head -10
    echo ""
    echo -e "${YELLOW}These will be cleared when the owning processes exit${NC}"
else
    echo -e "${GREEN}✅ No stale connections${NC}"
fi

# Step 3: Wait for port to be free
echo -e "${BLUE}Step 3: Waiting for port 4002 to be free...${NC}"
for i in {1..10}; do
    if ss -tln | grep -q ":4002 "; then
        echo -ne "\r${YELLOW}Port still in use... waiting ${i}s${NC}"
        sleep 1
    else
        echo -e "\n${GREEN}✅ Port 4002 is free${NC}"
        break
    fi

    if [ $i -eq 10 ]; then
        echo -e "\n${YELLOW}⚠️  Port may still be in TIME_WAIT state, but proceeding...${NC}"
    fi
done

# Step 4: Restart Gateway
echo -e "${BLUE}Step 4: Starting IB Gateway...${NC}"
GATEWAY_PATH="$HOME/ibgateway/ibgateway"

if [ ! -f "$GATEWAY_PATH" ]; then
    echo -e "${RED}❌ Gateway not found at: $GATEWAY_PATH${NC}"
    echo -e "${YELLOW}Please update GATEWAY_PATH in this script${NC}"
    exit 1
fi

nohup "$GATEWAY_PATH" > /tmp/ibgateway_restart.log 2>&1 &
GATEWAY_PID=$!
echo -e "${GREEN}✅ Gateway started (PID: $GATEWAY_PID)${NC}"

# Step 5: Wait for Gateway to initialize
echo -e "${BLUE}Step 5: Waiting for Gateway to initialize (30-60 seconds)...${NC}"
echo -e "${YELLOW}This is normal - Gateway needs time to fully start up${NC}"
echo ""

for i in {1..60}; do
    sleep 1
    echo -ne "\r${BLUE}Initializing... ${i}s / 60s${NC}"

    # Check if port is listening
    if ss -tln | grep -q ":4002 "; then
        # Port is listening, wait a bit more for API to be ready
        if [ $i -ge 20 ]; then
            echo -e "\n${GREEN}✅ Port is listening, testing connection...${NC}"

            # Test if we can connect
            if timeout 5 bash -c 'cat < /dev/null > /dev/tcp/127.0.0.1/4002' 2>/dev/null; then
                echo -e "${GREEN}✅ Gateway is ready and accepting connections!${NC}"
                echo ""
                echo -e "${GREEN}========================================${NC}"
                echo -e "${GREEN}Gateway Reset Complete${NC}"
                echo -e "${GREEN}========================================${NC}"
                echo ""
                echo -e "${BLUE}You can now launch Spyder:${NC}"
                echo -e "  ./launch_spyder_with_gateway.sh"
                echo -e "  ${YELLOW}OR${NC}"
                echo -e "  python test_gateway_connection.py  ${YELLOW}# to verify${NC}"
                exit 0
            fi
        fi
    fi

    if [ $i -eq 60 ]; then
        echo -e "\n${YELLOW}⚠️  Gateway may not be fully initialized yet${NC}"
        echo -e "${YELLOW}Check the Gateway UI to ensure it's logged in${NC}"
        echo -e "${YELLOW}Then try: python test_gateway_connection.py${NC}"
    fi
done
