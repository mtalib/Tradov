#!/bin/bash
#
# Fix IB Gateway Port Issue and Reconnect Spyder
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🔧 Fixing IB Gateway Port Configuration${NC}"

# Step 1: Kill existing Gateway
echo -e "${YELLOW}1️⃣  Stopping current Gateway...${NC}"
pkill -f "ibgateway" || echo "No Gateway running"
sleep 2

# Step 2: Update config to use port 4002 for paper trading
echo -e "${YELLOW}2️⃣  Updating Gateway config to use port 4002...${NC}"
sed -i 's/LocalServerPort=4000/LocalServerPort=4002/' ~/Jts/jts.ini

# Verify change
CURRENT_PORT=$(grep "LocalServerPort" ~/Jts/jts.ini | cut -d= -f2)
echo -e "${GREEN}✅ Gateway configured for port: $CURRENT_PORT${NC}"

# Step 3: Restart Gateway
echo -e "${YELLOW}3️⃣  Restarting IB Gateway...${NC}"
cd /home/adam/Projects/Spyder
./launch_balanced_gateway.sh &

# Wait for Gateway to start
echo -e "${YELLOW}⏳ Waiting for Gateway to start (15 seconds)...${NC}"
sleep 15

# Step 4: Verify Gateway is listening
if netstat -tuln | grep -q ":4002"; then
    echo -e "${GREEN}✅ Gateway is listening on port 4002${NC}"
else
    echo -e "${RED}❌ Gateway not listening on port 4002${NC}"
    exit 1
fi

# Step 5: Test connection
echo -e "${YELLOW}4️⃣  Testing connection...${NC}"
cd /home/adam/Projects/Spyder
source .venv/bin/activate

timeout 10 python3 << 'EOF' || echo "Connection test timed out"
from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient, IBConfig
import sys

try:
    c = IBConfig()
    c.client_id = 99
    c.timeout = 5
    client = SpyderClient(config=c)

    if client.connect_sync():
        print("✅ CONNECTION SUCCESSFUL!")
        client.disconnect()
        sys.exit(0)
    else:
        print("❌ Connection failed")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}🎉 Gateway is ready! You can now launch Spyder Dashboard${NC}"
    echo -e "${YELLOW}💡 Run: ./launch_dashboard_venv.sh${NC}"
else
    echo -e "${RED}❌ Gateway connection still failing${NC}"
    echo -e "${YELLOW}💡 Check Gateway logs or try manual restart${NC}"
fi
