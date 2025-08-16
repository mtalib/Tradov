#!/bin/bash
#
# Spyder Trading Control Center
# Simple interface to manage scheduled trading automation
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Paths
SPYDER_PATH="$HOME/Spyder"
VENV_PATH="$HOME/.venv"
PID_FILE="/tmp/spyder_scheduler.pid"
LOG_DIR="$HOME/.spyder/logs"

# Get current time in ET
get_et_time() {
    TZ='America/New_York' date '+%I:%M %p ET'
}

# Check if scheduler is running
is_scheduler_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 $PID 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# Check if IB Gateway is running
is_gateway_running() {
    pgrep -f "ibgateway" > /dev/null
    return $?
}

# Check if dashboard is running
is_dashboard_running() {
    pgrep -f "SpyderG05_TradingDashboard" > /dev/null
    return $?
}

# Show status
show_status() {
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}     SPYDER TRADING SYSTEM STATUS              ${NC}"
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${CYAN}Current Time:${NC} $(get_et_time)"
    echo -e "${CYAN}Schedule:${NC} 4:00 AM - 5:00 PM ET (Mon-Fri)"
    echo ""
    
    # Scheduler status
    if is_scheduler_running; then
        PID=$(cat "$PID_FILE")
        echo -e "${GREEN}✓${NC} Scheduler:  ${GREEN}RUNNING${NC} (PID: $PID)"
    else
        echo -e "${RED}✗${NC} Scheduler:  ${RED}STOPPED${NC}"
    fi
    
    # Gateway status
    if is_gateway_running; then
        echo -e "${GREEN}✓${NC} IB Gateway: ${GREEN}RUNNING${NC}"
    else
        echo -e "${YELLOW}○${NC} IB Gateway: ${YELLOW}NOT RUNNING${NC}"
    fi
    
    # Dashboard status
    if is_dashboard_running; then
        echo -e "${GREEN}✓${NC} Dashboard:  ${GREEN}RUNNING${NC}"
    else
        echo -e "${YELLOW}○${NC} Dashboard:  ${YELLOW}NOT RUNNING${NC}"
    fi
    
    echo ""
    
    # Check cron jobs
    if crontab -l 2>/dev/null | grep -q "Spyder Trading"; then
        echo -e "${GREEN}✓${NC} Cron jobs:  ${GREEN}CONFIGURED${NC}"
    else
        echo -e "${YELLOW}○${NC} Cron jobs:  ${YELLOW}NOT CONFIGURED${NC}"
    fi
    
    # Check systemd service
    if systemctl is-enabled spyder-scheduler.service &>/dev/null; then
        echo -e "${GREEN}✓${NC} Systemd:    ${GREEN}ENABLED${NC}"
    else
        echo -e "${YELLOW}○${NC} Systemd:    ${YELLOW}NOT ENABLED${NC}"
    fi
}

# Start scheduler
start_scheduler() {
    if is_scheduler_running; then
        echo -e "${YELLOW}Scheduler is already running${NC}"
        return
    fi
    
    echo -e "${GREEN}Starting scheduler...${NC}"
    
    # Activate virtual environment and start
    cd "$SPYDER_PATH"
    source "$VENV_PATH/bin/activate"
    
    # Start in background
    nohup python3 SpyderI02_IBScheduledAutomation.py > "$LOG_DIR/scheduler_manual.log" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    
    if is_scheduler_running; then
        echo -e "${GREEN}✓ Scheduler started successfully${NC}"
    else
        echo -e "${RED}✗ Failed to start scheduler${NC}"
    fi
}

# Stop scheduler
stop_scheduler() {
    if ! is_scheduler_running; then
        echo -e "${YELLOW}Scheduler is not running${NC}"
    else
        echo -e "${YELLOW}Stopping scheduler...${NC}"
        PID=$(cat "$PID_FILE")
        kill -TERM $PID
        rm -f "$PID_FILE"
        echo -e "${GREEN}✓ Scheduler stopped${NC}"
    fi
    
    # Also stop gateway and dashboard
    if is_gateway_running; then
        echo -e "${YELLOW}Stopping IB Gateway...${NC}"
        pkill -f "ibgateway"
    fi
    
    if is_dashboard_running; then
        echo -e "${YELLOW}Stopping Dashboard...${NC}"
        pkill -f "SpyderG05_TradingDashboard"
    fi
}

# Force start (immediate trading session)
force_start() {
    echo -e "${GREEN}Force starting trading session...${NC}"
    
    cd "$SPYDER_PATH"
    source "$VENV_PATH/bin/activate"
    
    # Create a temporary Python script to force start
    python3 << 'EOF'
import sys
sys.path.insert(0, ".")
from SpyderI02_IBScheduledAutomation import TradingSessionManager, ScheduledTradingConfig
import logging

logging.basicConfig(level=logging.INFO)

config = ScheduledTradingConfig()
config.load_credentials()

manager = TradingSessionManager(config)
manager._start_trading_session()

print("\nTrading session started manually")
print("Press Ctrl+C to stop")

try:
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    manager._stop_trading_session()
    print("\nTrading session stopped")
EOF
}

# View logs
view_logs() {
    echo -e "${BLUE}${BOLD}Recent Log Entries:${NC}"
    echo ""
    
    # Find today's log
    TODAY=$(date +%Y%m%d)
    LOG_FILE="$LOG_DIR/scheduler_$TODAY.log"
    
    if [ -f "$LOG_FILE" ]; then
        tail -n 20 "$LOG_FILE"
    else
        # Show any recent log
        LATEST_LOG=$(ls -t "$LOG_DIR"/*.log 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            tail -n 20 "$LATEST_LOG"
        else
            echo "No log files found"
        fi
    fi
}

# Main menu
show_menu() {
    clear
    echo -e "${BLUE}${BOLD}"
    echo "╔═══════════════════════════════════════════════╗"
    echo "║       SPYDER TRADING CONTROL CENTER          ║"
    echo "╚═══════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${CYAN}Current Time:${NC} $(get_et_time)"
    echo ""
    
    # Quick status
    if is_scheduler_running; then
        echo -e "Status: ${GREEN}● SCHEDULER ACTIVE${NC}"
    else
        echo -e "Status: ${RED}● SCHEDULER INACTIVE${NC}"
    fi
    
    echo ""
    echo -e "${BOLD}Options:${NC}"
    echo "  1) Show detailed status"
    echo "  2) Start scheduler"
    echo "  3) Stop scheduler"
    echo "  4) Force start trading NOW"
    echo "  5) View recent logs"
    echo "  6) Configure schedule"
    echo "  7) Test IB connection"
    echo "  0) Exit"
    echo ""
    read -p "Enter choice: " choice
    
    case $choice in
        1)
            clear
            show_status
            ;;
        2)
            start_scheduler
            ;;
        3)
            stop_scheduler
            ;;
        4)
            force_start
            ;;
        5)
            clear
            view_logs
            ;;
        6)
            ./setup_scheduler.sh
            ;;
        7)
            echo -e "${YELLOW}Testing IB Gateway connection...${NC}"
            cd "$SPYDER_PATH"
            source "$VENV_PATH/bin/activate"
            python3 -c "
from SpyderI01_IBAutomaterFullIntegration import SpyderIBAutomater, SpyderIBAutomaterConfig
config = SpyderIBAutomaterConfig()
config.load_credentials()
print(f'Credentials loaded: {bool(config.username)}')
"
            ;;
        0)
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            ;;
    esac
    
    if [ "$choice" != "0" ]; then
        echo ""
        read -p "Press Enter to continue..."
        show_menu
    fi
}

# Handle command line arguments
case "${1:-}" in
    status)
        show_status
        ;;
    start)
        start_scheduler
        ;;
    stop)
        stop_scheduler
        ;;
    force)
        force_start
        ;;
    logs)
        view_logs
        ;;
    *)
        show_menu
        ;;
esac
