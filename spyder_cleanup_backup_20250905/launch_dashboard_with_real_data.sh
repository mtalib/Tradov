#!/bin/bash
# SPYDER - Launch Dashboard with Real IB Market Data

echo "============================================"
echo "   SPYDER DASHBOARD WITH REAL DATA"
echo "============================================"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Project directory
SPYDER_DIR="$HOME/Projects/Spyder"
cd "$SPYDER_DIR"

# Activate virtual environment
source .venv/bin/activate

# Fix X11 access
xhost +local: 2>/dev/null

# Create market data directory
mkdir -p "$SPYDER_DIR/market_data"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${RED}Shutting down...${NC}"
    
    # Kill the data injector if running
    if [ ! -z "$INJECTOR_PID" ]; then
        kill $INJECTOR_PID 2>/dev/null
    fi
    
    # Clean up data files
    rm -f "$SPYDER_DIR/market_data/live_data.json"
    rm -f "$SPYDER_DIR/market_data/data_mode.txt"
    
    echo -e "${GREEN}✅ Cleanup complete${NC}"
    exit 0
}

# Set trap for cleanup
trap cleanup INT TERM EXIT

echo -e "${GREEN}Step 1: Starting Live Data Injector...${NC}"
# Start the data injector in background
python "$SPYDER_DIR/temp_LiveDataInjector.py" &
INJECTOR_PID=$!

# Wait for injector to connect
sleep 3

# Check if injector is running
if ! ps -p $INJECTOR_PID > /dev/null; then
    echo -e "${RED}❌ Data injector failed to start${NC}"
    echo "Check that IB Gateway is running and logged in"
    exit 1
fi

echo -e "${GREEN}✅ Data injector running (PID: $INJECTOR_PID)${NC}"

echo -e "\n${GREEN}Step 2: Launching Trading Dashboard...${NC}"
# Launch the dashboard
python "$SPYDER_DIR/SpyderG_GUI/SpyderG05_TradingDashboard.py" &
DASHBOARD_PID=$!

echo -e "${GREEN}✅ Dashboard launched (PID: $DASHBOARD_PID)${NC}"

echo ""
echo "============================================"
echo -e "${GREEN}   SYSTEM READY!${NC}"
echo "============================================"
echo "• Dashboard is running with REAL market data"
echo "• Data updates every second"
echo "• Press Ctrl+C to stop everything"
echo "============================================"

# Wait for dashboard to close
wait $DASHBOARD_PID

# Cleanup will be called automatically
