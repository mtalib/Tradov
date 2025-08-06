#!/bin/bash
# Setup script for IB Gateway Watchdog Service

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "IB Gateway Watchdog Service Setup"
echo "================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please run without sudo first${NC}"
   exit 1
fi

# Create logs directory
mkdir -p ~/Projects/Spyder/logs

case "$1" in
    install)
        echo "Installing IB Watchdog service..."
        
        # Copy service file
        sudo cp ib-watchdog.service /etc/systemd/system/
        
        # Reload systemd
        sudo systemctl daemon-reload
        
        # Enable service
        sudo systemctl enable ib-watchdog.service
        
        echo -e "${GREEN}✅ Service installed successfully${NC}"
        echo "Commands:"
        echo "  Start:   sudo systemctl start ib-watchdog"
        echo "  Stop:    sudo systemctl stop ib-watchdog"
        echo "  Status:  sudo systemctl status ib-watchdog"
        echo "  Logs:    sudo journalctl -u ib-watchdog -f"
        ;;
        
    start)
        echo "Starting IB Watchdog..."
        sudo systemctl start ib-watchdog
        sleep 2
        sudo systemctl status ib-watchdog --no-pager
        ;;
        
    stop)
        echo "Stopping IB Watchdog..."
        sudo systemctl stop ib-watchdog
        ;;
        
    status)
        sudo systemctl status ib-watchdog --no-pager
        ;;
        
    logs)
        echo "Showing recent logs (Ctrl+C to exit)..."
        sudo journalctl -u ib-watchdog -f
        ;;
        
    uninstall)
        echo "Uninstalling IB Watchdog service..."
        sudo systemctl stop ib-watchdog
        sudo systemctl disable ib-watchdog
        sudo rm /etc/systemd/system/ib-watchdog.service
        sudo systemctl daemon-reload
        echo -e "${GREEN}✅ Service uninstalled${NC}"
        ;;
        
    *)
        echo "Usage: $0 {install|start|stop|status|logs|uninstall}"
        echo ""
        echo "  install    - Install the systemd service"
        echo "  start      - Start the watchdog service"
        echo "  stop       - Stop the watchdog service"
        echo "  status     - Show service status"
        echo "  logs       - Show live logs"
        echo "  uninstall  - Remove the service"
        exit 1
        ;;
esac
