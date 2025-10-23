#!/bin/bash
# ==============================================================================
# SPYDER - Client Portal Gateway Stop Script
# ==============================================================================
# This script stops the IBKR Client Portal Gateway Docker container
# Author: Mohamed Talib
# Date: 2025-10-23
# ==============================================================================

MODE=${1:-paper}  # Default to paper

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "IBKR Client Portal Gateway Stop"
echo "=========================================="
echo ""

# Determine container name based on mode
if [ "$MODE" = "paper" ]; then
    NAME="ibkr-gateway-paper"
    echo "Mode: Paper Trading"
elif [ "$MODE" = "live" ]; then
    NAME="ibkr-gateway-live"
    echo "Mode: Live Trading"
elif [ "$MODE" = "all" ]; then
    echo "Mode: Stopping all gateways"
    echo ""

    # Stop all gateway containers
    for container in ibkr-gateway-paper ibkr-gateway-live; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            echo "Stopping $container..."
            docker stop $container 2>/dev/null
            docker rm $container 2>/dev/null
            echo "${GREEN}✅ $container stopped and removed${NC}"
        else
            echo "${YELLOW}⚠️  $container not found${NC}"
        fi
    done

    echo ""
    echo "${GREEN}✅ All gateways stopped${NC}"
    exit 0
else
    echo "${RED}ERROR: Invalid mode. Use 'paper', 'live', or 'all'${NC}"
    echo "Usage: $0 [paper|live|all]"
    exit 1
fi

echo "Container: $NAME"
echo ""

# Check if container exists
if ! docker ps -a --format '{{.Names}}' | grep -q "^${NAME}$"; then
    echo "${YELLOW}⚠️  Container $NAME does not exist${NC}"
    echo "Nothing to stop."
    exit 0
fi

# Stop container
echo "Stopping container..."
if docker stop $NAME; then
    echo "${GREEN}✅ Container stopped${NC}"
else
    echo "${RED}❌ Failed to stop container${NC}"
    exit 1
fi

# Remove container
echo "Removing container..."
if docker rm $NAME; then
    echo "${GREEN}✅ Container removed${NC}"
else
    echo "${YELLOW}⚠️  Failed to remove container${NC}"
fi

echo ""
echo "=========================================="
echo "${GREEN}✅ Gateway Stopped Successfully${NC}"
echo "=========================================="
echo ""
echo "To start again: ./start_gateway.sh $MODE"
