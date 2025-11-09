#!/bin/bash
#
# Spyder Trading Dashboard - Virtual Environment Launcher
# Ensures venv is activated and launches dashboard with IB Gateway connection
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Navigate to Spyder directory
SPYDER_DIR="/home/adam/Projects/Spyder"
cd "$SPYDER_DIR" || {
    echo -e "${RED}❌ Failed to navigate to $SPYDER_DIR${NC}"
    exit 1
}

echo -e "${GREEN}🚀 Starting Spyder Dashboard with venv${NC}"

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ Virtual environment not found at .venv${NC}"
    echo -e "${YELLOW}💡 Create it with: python3 -m venv .venv${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}🔧 Activating virtual environment...${NC}"
source .venv/bin/activate

# Verify ib_async is installed
if ! python -c "import ib_async" 2>/dev/null; then
    echo -e "${RED}❌ ib_async not found in venv${NC}"
    echo -e "${YELLOW}💡 Install with: pip install ib_async${NC}"
    exit 1
fi

# Check if IB Gateway is running
if ! pgrep -f "ibgateway" > /dev/null; then
    echo -e "${YELLOW}⚠️  IB Gateway not running${NC}"
    echo -e "${YELLOW}💡 Start it first or use: ./launch_spyder_with_gateway.sh${NC}"
    # Uncomment the line below to auto-start Gateway
    # ./launch_balanced_gateway.sh &
    # sleep 10
fi

# Check Gateway port
GATEWAY_PORT=$(grep "LocalServerPort" ~/Jts/jts.ini 2>/dev/null | cut -d= -f2 || echo "4002")
echo -e "${GREEN}📡 Gateway configured on port: $GATEWAY_PORT${NC}"

# Export environment variables
export DISPLAY=:0
export PYTHONPATH="$SPYDER_DIR:$PYTHONPATH"

# Launch the dashboard
echo -e "${GREEN}🎯 Launching Spyder Dashboard...${NC}"
exec python launch_dashboard_production.py
