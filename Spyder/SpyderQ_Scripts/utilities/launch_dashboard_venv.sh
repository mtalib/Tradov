#!/bin/bash
#
# Spyder Trading Dashboard - Virtual Environment Launcher
# Ensures venv is activated and launches dashboard with Tradier API connection
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

# Verify key dependencies are installed
if ! python -c "import requests" 2>/dev/null; then
    echo -e "${RED}❌ requests not found in venv${NC}"
    echo -e "${YELLOW}💡 Install with: pip install -r requirements.txt${NC}"
    exit 1
fi

# Check Tradier API configuration
if [ -f ".env" ]; then
    if grep -q "TRADIER_API_KEY" .env 2>/dev/null; then
        echo -e "${GREEN}📡 Tradier API key configured${NC}"
    else
        echo -e "${YELLOW}⚠️  TRADIER_API_KEY not found in .env${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
fi

# Export environment variables
export DISPLAY=:0
export PYTHONPATH="$SPYDER_DIR:$PYTHONPATH"

# Launch the dashboard
echo -e "${GREEN}🎯 Launching Spyder Dashboard...${NC}"
exec python launch_dashboard_production.py
