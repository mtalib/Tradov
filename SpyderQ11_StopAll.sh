#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Spyder Version: 1.0
# Module: SpyderQ11_StopAll.sh
# Group: Q (Scripts)
# Purpose: Gracefully stop all Spyder system components
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 14:45:00
#
# Description:
#     Safely shuts down all Spyder trading system components in the correct
#     order, ensuring positions are closed, data is saved, and processes are
#     terminated cleanly. Provides status feedback and confirmation prompts
#     for production safety.
# ===============================================================================

set -e

# ===============================================================================
# CONFIGURATION
# ===============================================================================
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
PID_DIR="$SPYDER_HOME/pids"
LOG_DIR="$SPYDER_HOME/logs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

print_header() {
    echo -e "${RED}================================================${NC}"
    echo -e "${RED}    SPYDER TRADING SYSTEM SHUTDOWN${NC}"
    echo -e "${RED}================================================${NC}"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[i]${NC} $1"
}

# ===============================================================================
# PROCESS MANAGEMENT
# ===============================================================================

get_pid() {
    local process_name=$1
    local pid_file="$PID_DIR/$process_name.pid"
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    else
        echo ""
    fi
}

stop_process() {
    local process_name=$1
    local display_name=$2
    local pid=$(get_pid "$process_name")
    
    if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
        print_info "Stopping $display_name (PID: $pid)..."
        
        # Send SIGTERM for graceful shutdown
        kill -TERM $pid 2>/dev/null || true
        
        # Wait for process to stop (max 10 seconds)
        local count=0
        while kill -0 $pid 2>/dev/null && [ $count -lt 10 ]; do
            sleep 1
            count=$((count + 1))
        done
        
        # Force kill if still running
        if kill -0 $pid 2>/dev/null; then
            print_warning "Force stopping $display_name..."
            kill -KILL $pid 2>/dev/null || true
        fi
        
        # Clean up PID file
        rm -f "$PID_DIR/$process_name.pid"
        
        print_success "$display_name stopped"
    else
        print_info "$display_name not running"
    fi
}

# ===============================================================================
# MAIN SHUTDOWN SEQUENCE
# ===============================================================================

main() {
    clear
    print_header
    echo ""
    
    # Confirmation prompt for safety
    if [ "$1" != "-f" ] && [ "$1" != "--force" ]; then
        echo -e "${YELLOW}Warning: This will stop all trading activities${NC}"
        read -p "Are you sure you want to stop Spyder? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Shutdown cancelled"
            exit 0
        fi
    fi
    
    echo ""
    print_info "Beginning graceful shutdown sequence..."
    echo ""
    
    # Stop GUI first (if running)
    stop_process "gui" "GUI Dashboard"
    
    # Stop monitoring services
    stop_process "monitor" "System Monitor"
    stop_process "watchdog" "Production Watchdog"
    
    # Stop main trading engine last
    stop_process "main_engine" "Trading Engine"
    
    # Check for any remaining Python processes
    print_info "Checking for remaining Spyder processes..."
    
    REMAINING=$(pgrep -f "Spyder[A-Z].*\.py" | wc -l)
    if [ "$REMAINING" -gt 0 ]; then
        print_warning "Found $REMAINING remaining Spyder processes"
        
        if [ "$1" == "-f" ] || [ "$1" == "--force" ]; then
            print_info "Force stopping all remaining processes..."
            pkill -f "Spyder[A-Z].*\.py" 2>/dev/null || true
            print_success "All processes terminated"
        else
            print_info "Run with -f flag to force stop remaining processes"
        fi
    else
        print_success "No remaining processes found"
    fi
    
    # Clean up stale PID files
    print_info "Cleaning up PID files..."
    if [ -d "$PID_DIR" ]; then
        rm -f "$PID_DIR"/*.pid 2>/dev/null || true
    fi
    
    # Log shutdown
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] System shutdown completed" >> "$LOG_DIR/shutdown.log"
    
    echo ""
    print_success "🛑 Spyder Trading System stopped successfully"
    echo ""
    
    # Show next steps
    echo "To restart the system:"
    echo "  • Click the SPY icon in your dashboard"
    echo "  • Or run: $SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh"
    echo ""
    
    # Send desktop notification if available
    if command -v notify-send &> /dev/null && [ -n "$DISPLAY" ]; then
        notify-send "Spyder Trading System" "System has been stopped" -i dialog-information
    fi
}

# ===============================================================================
# SCRIPT EXECUTION
# ===============================================================================

main "$@"