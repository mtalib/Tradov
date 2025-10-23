#!/bin/bash
# ==============================================================================
# SPYDER - Client Portal Gateway Startup Script
# ==============================================================================
# This script starts the IBKR Client Portal Gateway using Docker
# Author: Mohamed Talib
# Date: 2025-10-23
# ==============================================================================

set -e  # Exit on error

MODE=${1:-paper}  # Default to paper

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "IBKR Client Portal Gateway Startup"
echo "=========================================="
echo ""

# Determine port and container name based on mode
if [ "$MODE" = "paper" ]; then
    PORT=5000
    NAME="ibkr-gateway-paper"
    echo "Mode: ${GREEN}Paper Trading${NC}"
elif [ "$MODE" = "live" ]; then
    PORT=5001
    NAME="ibkr-gateway-live"
    echo "Mode: ${RED}Live Trading${NC}"
else
    echo "${RED}ERROR: Invalid mode. Use 'paper' or 'live'${NC}"
    echo "Usage: $0 [paper|live]"
    exit 1
fi

echo "Container: $NAME"
echo "Port: $PORT"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "${RED}❌ ERROR: Docker is not installed${NC}"
    echo "Please install Docker: sudo apt install docker.io"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "${RED}❌ ERROR: Docker daemon is not running${NC}"
    echo "Start Docker: sudo systemctl start docker"
    exit 1
fi

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${NAME}$"; then
    echo "${YELLOW}⚠️  Container $NAME already exists${NC}"

    # Check if it's running
    if docker ps --format '{{.Names}}' | grep -q "^${NAME}$"; then
        echo "${GREEN}✅ Container is already running${NC}"
        echo ""
        echo "Gateway URL: https://localhost:$PORT"
        echo ""
        echo "To restart: docker restart $NAME"
        echo "To stop: docker stop $NAME"
        echo "To view logs: docker logs -f $NAME"
        exit 0
    else
        echo "Starting existing container..."
        docker start $NAME
        sleep 3

        if docker ps --format '{{.Names}}' | grep -q "^${NAME}$"; then
            echo "${GREEN}✅ Container started successfully!${NC}"
        else
            echo "${RED}❌ Failed to start container${NC}"
            echo "Check logs: docker logs $NAME"
            exit 1
        fi
    fi
else
    # Pull latest image (using ibeam - community-maintained IBKR gateway)
    echo "Pulling latest IBKR Gateway image (ibeam)..."
    if docker pull voyz/ibeam:latest; then
        echo "${GREEN}✅ Image pulled successfully${NC}"
    else
        echo "${YELLOW}⚠️  Failed to pull latest image, using cached version${NC}"
    fi
    echo ""

    # Check if credentials are set
    if [ -z "$IBEAM_ACCOUNT" ] || [ -z "$IBEAM_PASSWORD" ]; then
        echo "${YELLOW}⚠️  WARNING: IBKR credentials not set${NC}"
        echo ""
        echo "You need to set environment variables:"
        echo "  export IBEAM_ACCOUNT='your_username'"
        echo "  export IBEAM_PASSWORD='your_password'"
        echo ""
        echo "Or pass them directly:"
        echo "  IBEAM_ACCOUNT=user IBEAM_PASSWORD=pass ./start_gateway.sh $MODE"
        echo ""
        read -p "Continue anyway? (you'll need to authenticate manually) [y/N]: " response
        if [ "$response" != "y" ] && [ "$response" != "Y" ]; then
            echo "Aborted."
            exit 1
        fi
    fi

    # Start new container
    echo "Starting IBKR Client Portal Gateway (ibeam)..."
    docker run -d \
      --name $NAME \
      -p $PORT:5000 \
      -e IBEAM_ACCOUNT="${IBEAM_ACCOUNT}" \
      -e IBEAM_PASSWORD="${IBEAM_PASSWORD}" \
      -e IBEAM_TRADING_MODE="$MODE" \
      --restart unless-stopped \
      voyz/ibeam:latest    if [ $? -ne 0 ]; then
        echo "${RED}❌ Failed to start container${NC}"
        exit 1
    fi

    # Wait for container to start
    echo "Waiting for gateway to initialize..."
    sleep 5
fi

# Verify container is running
if docker ps --format '{{.Names}}' | grep -q "^${NAME}$"; then
    echo ""
    echo "=========================================="
    echo "${GREEN}✅ Gateway Started Successfully!${NC}"
    echo "=========================================="
    echo ""
    echo "Mode: $MODE"
    echo "Port: $PORT"
    echo "URL: https://localhost:$PORT"
    echo ""
    echo "Container Info:"
    docker ps --filter "name=$NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "Next Steps:"
    echo "1. Test gateway: curl -k https://localhost:$PORT/v1/api/tickle"
    echo "2. Launch OAuth launcher: python SpyderG08_IBKRLoginLauncher_OAuth.py"
    echo ""
    echo "Useful Commands:"
    echo "  View logs: docker logs -f $NAME"
    echo "  Stop: docker stop $NAME"
    echo "  Restart: docker restart $NAME"
    echo "  Remove: docker stop $NAME && docker rm $NAME"
else
    echo ""
    echo "${RED}❌ Gateway failed to start${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "1. Check logs: docker logs $NAME"
    echo "2. Check port availability: sudo netstat -tlnp | grep $PORT"
    echo "3. Try removing and recreating: docker rm $NAME && $0 $MODE"
    exit 1
fi
