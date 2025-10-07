#!/bin/bash
# Spyder Launcher with IB Gateway Management
# This script ensures IB Gateway is running and fully initialized before launching Spyder

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/adam/Projects/Spyder"
VENV_DIR="$PROJECT_DIR/.venv"
GATEWAY_PATH="$HOME/Jts/ibgateway/1039/ibgateway"
GATEWAY_PORT=4002
GATEWAY_INIT_TIMEOUT=60  # seconds to wait for Gateway initialization
CLIENT_ID=2

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Spyder Trading System Launcher${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if Gateway is running
check_gateway_process() {
    if pgrep -f "ibgateway" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to check if Gateway port is listening
check_gateway_port() {
    if ss -tln | grep -q ":$GATEWAY_PORT "; then
        return 0
    else
        return 1
    fi
}

# Function to test Gateway connection
test_gateway_connection() {
    echo -e "${BLUE}Testing Gateway connection...${NC}"

    "$VENV_DIR/bin/python" -c "
from ib_async import IB
import sys

try:
    ib = IB()
    ib.connect('127.0.0.1', $GATEWAY_PORT, clientId=999, timeout=5)
    print('✅ Gateway connection test successful')
    ib.disconnect()
    sys.exit(0)
except Exception as e:
    print(f'❌ Gateway connection test failed: {e}')
    sys.exit(1)
" 2>/dev/null

    return $?
}

# Check if Gateway is already running
echo -e "${BLUE}Step 1: Checking IB Gateway status...${NC}"
if check_gateway_process; then
    echo -e "${GREEN}✅ IB Gateway process is running${NC}"

    if check_gateway_port; then
        echo -e "${GREEN}✅ Port $GATEWAY_PORT is listening${NC}"

        # Test if we can actually connect
        if test_gateway_connection; then
            echo -e "${GREEN}✅ Gateway is fully initialized and accepting connections${NC}"
        else
            echo -e "${YELLOW}⚠️  Gateway is running but not accepting connections yet${NC}"
            echo -e "${YELLOW}    Waiting for Gateway to initialize...${NC}"

            # Wait for Gateway to become ready
            for i in $(seq 1 $GATEWAY_INIT_TIMEOUT); do
                sleep 1
                echo -ne "\r${BLUE}Waiting... ${i}s / ${GATEWAY_INIT_TIMEOUT}s${NC}"
                if test_gateway_connection 2>/dev/null; then
                    echo -e "\n${GREEN}✅ Gateway is now ready!${NC}"
                    break
                fi

                if [ $i -eq $GATEWAY_INIT_TIMEOUT ]; then
                    echo -e "\n${RED}❌ Gateway failed to initialize after ${GATEWAY_INIT_TIMEOUT}s${NC}"
                    echo -e "${YELLOW}Would you like to restart the Gateway? (y/n)${NC}"
                    read -r response
                    if [[ "$response" =~ ^[Yy]$ ]]; then
                        echo -e "${BLUE}Restarting Gateway...${NC}"
                        pkill -f ibgateway
                        sleep 3
                        nohup "$GATEWAY_PATH" > /tmp/ibgateway.log 2>&1 &
                        echo -e "${BLUE}Gateway restarted. Waiting 30 seconds...${NC}"
                        sleep 30
                    else
                        echo -e "${YELLOW}Continuing without Gateway connection...${NC}"
                    fi
                fi
            done
        fi
    else
        echo -e "${YELLOW}⚠️  Gateway process exists but port $GATEWAY_PORT not listening${NC}"
        echo -e "${YELLOW}    Gateway may still be starting up...${NC}"
        sleep 5
    fi
else
    echo -e "${YELLOW}⚠️  IB Gateway is not running${NC}"
    echo -e "${BLUE}Starting IB Gateway...${NC}"

    if [ ! -f "$GATEWAY_PATH" ]; then
        echo -e "${RED}❌ Gateway not found at: $GATEWAY_PATH${NC}"
        echo -e "${YELLOW}Please install IB Gateway or update GATEWAY_PATH in this script${NC}"
        exit 1
    fi

    # Start Gateway
    nohup "$GATEWAY_PATH" > /tmp/ibgateway.log 2>&1 &
    GATEWAY_PID=$!
    echo -e "${GREEN}✅ Gateway started (PID: $GATEWAY_PID)${NC}"

    # Wait for Gateway to initialize
    echo -e "${BLUE}Waiting for Gateway to initialize (this may take 30-60 seconds)...${NC}"

    for i in $(seq 1 $GATEWAY_INIT_TIMEOUT); do
        sleep 1
        echo -ne "\r${BLUE}Initializing... ${i}s / ${GATEWAY_INIT_TIMEOUT}s${NC}"

        # Check if port is listening
        if check_gateway_port; then
            # Port is listening, now test connection
            if test_gateway_connection 2>/dev/null; then
                echo -e "\n${GREEN}✅ Gateway is ready!${NC}"
                break
            fi
        fi

        if [ $i -eq $GATEWAY_INIT_TIMEOUT ]; then
            echo -e "\n${RED}❌ Gateway failed to initialize after ${GATEWAY_INIT_TIMEOUT}s${NC}"
            echo -e "${YELLOW}Spyder will launch but may not connect to Gateway${NC}"
        fi
    done
fi

echo ""
echo -e "${BLUE}Step 2: Launching Spyder Trading Dashboard...${NC}"

# Activate virtual environment and launch Spyder
cd "$PROJECT_DIR"

echo -e "${BLUE}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

echo -e "${BLUE}Starting Spyder application...${NC}"
python SpyderA_Core/SpyderA01_Main.py

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Spyder session ended${NC}"
echo -e "${GREEN}========================================${NC}"
