#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Spyder Version: 1.0
# Module: SpyderQ20_Status.sh
# Group: Q (Scripts)
# Purpose: Comprehensive system status checker for all Spyder components
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 15:00:00
#
# Description:
#     Checks the status of all Spyder system components including IB Gateway,
#     trading engine, GUI dashboard, monitoring services, and Prometheus metrics.
#     Integrates with dashboard modules to provide real-time status information
#     compatible with SpyderG05_TradingDashboard and SpyderG07_PrometheusMetrics.
# ===============================================================================

set -e

# ===============================================================================
# CONFIGURATION
# ===============================================================================
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
PID_DIR="$SPYDER_HOME/pids"
LOG_DIR="$SPYDER_HOME/logs"
CONFIG_FILE="$SPYDER_HOME/.env"

# Dashboard modules
DASHBOARD_MODULE="SpyderG05_TradingDashboard"
MONITOR_MODULE="SpyderG06_ClientMonitorPanel"
METRICS_MODULE="SpyderG07_PrometheusMetricsDisplay"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Status icons
CHECK="✓"
CROSS="✗"
WARNING="⚠"
INFO="ℹ"

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           SPYDER TRADING SYSTEM STATUS CHECK              ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
}

print_section() {
    local title=$1
    echo -e "\n${CYAN}═══ $title ═══${NC}"
}

print_status() {
    local component=$1
    local status=$2
    local details=$3
    
    if [ "$status" = "running" ]; then
        echo -e "${GREEN}[${CHECK}]${NC} $component: ${GREEN}RUNNING${NC} $details"
    elif [ "$status" = "stopped" ]; then
        echo -e "${RED}[${CROSS}]${NC} $component: ${RED}STOPPED${NC} $details"
    elif [ "$status" = "warning" ]; then
        echo -e "${YELLOW}[${WARNING}]${NC} $component: ${YELLOW}WARNING${NC} $details"
    else
        echo -e "${CYAN}[${INFO}]${NC} $component: $details"
    fi
}

get_pid() {
    local process_name=$1
    local pid_file="$PID_DIR/$process_name.pid"
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    else
        echo ""
    fi
}

check_process_by_pid() {
    local pid=$1
    if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

check_port() {
    local port=$1
    nc -z localhost $port 2>/dev/null
    return $?
}

format_uptime() {
    local pid=$1
    if [ -n "$pid" ]; then
        local etimes=$(ps -o etimes= -p $pid 2>/dev/null | tr -d ' ')
        if [ -n "$etimes" ]; then
            local days=$((etimes / 86400))
            local hours=$(((etimes % 86400) / 3600))
            local minutes=$(((etimes % 3600) / 60))
            local seconds=$((etimes % 60))
            
            if [ $days -gt 0 ]; then
                echo "${days}d ${hours}h ${minutes}m"
            elif [ $hours -gt 0 ]; then
                echo "${hours}h ${minutes}m ${seconds}s"
            elif [ $minutes -gt 0 ]; then
                echo "${minutes}m ${seconds}s"
            else
                echo "${seconds}s"
            fi
        fi
    fi
}

get_memory_usage() {
    local pid=$1
    if [ -n "$pid" ] && check_process_by_pid $pid; then
        ps -o rss= -p $pid | awk '{printf "%.1f MB", $1/1024}'
    else
        echo "N/A"
    fi
}

# ===============================================================================
# IB GATEWAY STATUS
# ===============================================================================

check_ib_gateway() {
    print_section "IB Gateway Connection"
    
    # Check if IB Gateway process is running
    local gateway_running=false
    if pgrep -f "ibgateway" > /dev/null 2>&1; then
        gateway_running=true
    fi
    
    # Check ports
    local paper_port_open=false
    local live_port_open=false
    
    if check_port 4002; then
        paper_port_open=true
    fi
    
    if check_port 4001; then
        live_port_open=true
    fi
    
    # Report status
    if [ "$gateway_running" = true ]; then
        print_status "IB Gateway Process" "running" ""
        
        if [ "$paper_port_open" = true ]; then
            print_status "Paper Trading Port (4002)" "running" ""
        else
            print_status "Paper Trading Port (4002)" "stopped" ""
        fi
        
        if [ "$live_port_open" = true ]; then
            print_status "Live Trading Port (4001)" "running" ""
        else
            print_status "Live Trading Port (4001)" "stopped" ""
        fi
    else
        print_status "IB Gateway" "stopped" "- Not detected"
    fi
}

# ===============================================================================
# TRADING ENGINE STATUS
# ===============================================================================

check_trading_engine() {
    print_section "Trading Engine"
    
    local main_pid=$(get_pid "main_engine")
    
    if check_process_by_pid "$main_pid"; then
        local uptime=$(format_uptime $main_pid)
        local memory=$(get_memory_usage $main_pid)
        print_status "SpyderA01_Main" "running" "(PID: $main_pid, Uptime: $uptime, Memory: $memory)"
        
        # Check for recent errors in log
        if [ -f "$LOG_DIR/system/main.log" ]; then
            local error_count=$(tail -n 100 "$LOG_DIR/system/main.log" 2>/dev/null | grep -c "ERROR" || true)
            if [ $error_count -gt 0 ]; then
                print_status "Recent Errors" "warning" "- $error_count errors in last 100 lines"
            fi
        fi
    else
        print_status "SpyderA01_Main" "stopped" ""
    fi
}

# ===============================================================================
# GUI DASHBOARD STATUS
# ===============================================================================

check_gui_dashboard() {
    print_section "GUI Dashboard"
    
    local gui_pid=$(get_pid "gui")
    
    if check_process_by_pid "$gui_pid"; then
        local uptime=$(format_uptime $gui_pid)
        local memory=$(get_memory_usage $gui_pid)
        print_status "$DASHBOARD_MODULE" "running" "(PID: $gui_pid, Uptime: $uptime, Memory: $memory)"
        
        # Check for PyQt6 display
        if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
            print_status "Display Server" "running" "($DISPLAY)"
        else
            print_status "Display Server" "warning" "- No display detected"
        fi
    else
        print_status "$DASHBOARD_MODULE" "stopped" ""
    fi
}

# ===============================================================================
# MONITORING SERVICES STATUS
# ===============================================================================

check_monitoring_services() {
    print_section "Monitoring Services"
    
    # Watchdog
    local watchdog_pid=$(get_pid "watchdog")
    if check_process_by_pid "$watchdog_pid"; then
        local uptime=$(format_uptime $watchdog_pid)
        print_status "Production Watchdog" "running" "(PID: $watchdog_pid, Uptime: $uptime)"
    else
        print_status "Production Watchdog" "stopped" ""
    fi
    
    # System Monitor
    local monitor_pid=$(get_pid "monitor")
    if check_process_by_pid "$monitor_pid"; then
        local uptime=$(format_uptime $monitor_pid)
        print_status "System Monitor" "running" "(PID: $monitor_pid, Uptime: $uptime)"
    else
        print_status "System Monitor" "stopped" ""
    fi
}

# ===============================================================================
# PROMETHEUS METRICS STATUS
# ===============================================================================

check_prometheus_metrics() {
    print_section "Prometheus Metrics (Multi-Client)"
    
    # Check if Prometheus port is open
    if check_port 9090; then
        print_status "Prometheus Exporter" "running" "(Port 9090)"
        
        # Try to get metrics from endpoint
        if command -v curl &> /dev/null; then
            local response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9090/metrics 2>/dev/null || echo "000")
            if [ "$response" = "200" ]; then
                print_status "Metrics Endpoint" "running" "- Responding"
                
                # Get client status if possible
                local client_count=$(curl -s http://localhost:9090/metrics 2>/dev/null | grep -c "ib_client_connected" || echo "0")
                if [ $client_count -gt 0 ]; then
                    print_status "Active IB Clients" "info" "- $client_count clients monitored"
                fi
            else
                print_status "Metrics Endpoint" "warning" "- Not responding (HTTP $response)"
            fi
        fi
    else
        print_status "Prometheus Exporter" "stopped" "(Port 9090 closed)"
    fi
    
    # Check individual client connections (0-8)
    echo -e "\n  ${CYAN}Client Connections:${NC}"
    local clients=("Admin" "Orders" "Core" "Options" "Volatility" "Internals" "Major ETFs" "Extended" "Sector ETFs")
    
    for i in {0..8}; do
        # This would check actual client status in production
        # For now, simulate based on presence of client process
        local client_status="unknown"
        if check_port 9090; then
            # In production, would query actual metrics
            client_status="active"
        fi
        
        if [ "$client_status" = "active" ]; then
            echo -e "    ${GREEN}●${NC} CLIENT $i: ${clients[$i]}"
        else
            echo -e "    ${RED}○${NC} CLIENT $i: ${clients[$i]}"
        fi
    done
}

# ===============================================================================
# SYSTEM RESOURCES
# ===============================================================================

check_system_resources() {
    print_section "System Resources"
    
    # CPU usage
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    print_status "CPU Usage" "info" "- ${cpu_usage}%"
    
    # Memory usage
    local mem_info=$(free -m | awk 'NR==2{printf "%.1f%% (Used: %sMB / Total: %sMB)", $3*100/$2, $3, $2}')
    print_status "Memory Usage" "info" "- $mem_info"
    
    # Disk usage for Spyder directory
    local disk_usage=$(df -h "$SPYDER_HOME" | awk 'NR==2{printf "%s (Used: %s / Total: %s)", $5, $3, $2}')
    print_status "Disk Usage" "info" "- $disk_usage"
    
    # Python virtual environment
    if [ -d "$SPYDER_HOME/spyder_venv" ]; then
        print_status "Virtual Environment" "running" "- $SPYDER_HOME/spyder_venv"
    else
        print_status "Virtual Environment" "stopped" "- Not found"
    fi
}

# ===============================================================================
# LOG FILES STATUS
# ===============================================================================

check_log_files() {
    print_section "Log Files"
    
    if [ -d "$LOG_DIR" ]; then
        # Check log sizes
        local total_size=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
        print_status "Log Directory" "info" "- Total size: $total_size"
        
        # Check recent log activity
        local recent_logs=$(find "$LOG_DIR" -type f -name "*.log" -mmin -5 2>/dev/null | wc -l)
        if [ $recent_logs -gt 0 ]; then
            print_status "Recent Activity" "running" "- $recent_logs log files updated in last 5 minutes"
        else
            print_status "Recent Activity" "warning" "- No recent log updates"
        fi
        
        # Check for critical errors
        local critical_errors=$(grep -r "CRITICAL\|FATAL" "$LOG_DIR" --include="*.log" 2>/dev/null | wc -l || echo "0")
        if [ $critical_errors -gt 0 ]; then
            print_status "Critical Errors" "warning" "- $critical_errors found in logs"
        else
            print_status "Critical Errors" "running" "- None found"
        fi
    else
        print_status "Log Directory" "stopped" "- Not found"
    fi
}

# ===============================================================================
# CONFIGURATION STATUS
# ===============================================================================

check_configuration() {
    print_section "Configuration"
    
    if [ -f "$CONFIG_FILE" ]; then
        print_status "Configuration File" "running" "- $CONFIG_FILE"
        
        # Check key configuration items
        if grep -q "ENABLE_LIVE_TRADING=true" "$CONFIG_FILE" 2>/dev/null; then
            print_status "Trading Mode" "warning" "- LIVE TRADING ENABLED"
        else
            print_status "Trading Mode" "info" "- Paper trading"
        fi
        
        if grep -q "ENABLE_GUI=true" "$CONFIG_FILE" 2>/dev/null; then
            print_status "GUI Mode" "info" "- Enabled"
        else
            print_status "GUI Mode" "info" "- Disabled"
        fi
    else
        print_status "Configuration File" "stopped" "- Not found (using defaults)"
    fi
}

# ===============================================================================
# SUMMARY GENERATION
# ===============================================================================

generate_summary() {
    print_section "System Summary"
    
    local total_components=0
    local running_components=0
    
    # Count components
    [ -n "$(get_pid "main_engine")" ] && [ -n "$(kill -0 $(get_pid "main_engine") 2>/dev/null && echo "1")" ] && ((running_components++))
    ((total_components++))
    
    [ -n "$(get_pid "gui")" ] && [ -n "$(kill -0 $(get_pid "gui") 2>/dev/null && echo "1")" ] && ((running_components++))
    ((total_components++))
    
    [ -n "$(get_pid "watchdog")" ] && [ -n "$(kill -0 $(get_pid "watchdog") 2>/dev/null && echo "1")" ] && ((running_components++))
    ((total_components++))
    
    [ -n "$(get_pid "monitor")" ] && [ -n "$(kill -0 $(get_pid "monitor") 2>/dev/null && echo "1")" ] && ((running_components++))
    ((total_components++))
    
    pgrep -f "ibgateway" > /dev/null 2>&1 && ((running_components++))
    ((total_components++))
    
    # Calculate health score
    local health_score=$((running_components * 100 / total_components))
    
    echo -e "\n${CYAN}──────────────────────────────────────────────${NC}"
    echo -e "Components Running: ${GREEN}$running_components${NC} / $total_components"
    
    if [ $health_score -ge 80 ]; then
        echo -e "System Health: ${GREEN}${health_score}%${NC} - HEALTHY"
    elif [ $health_score -ge 60 ]; then
        echo -e "System Health: ${YELLOW}${health_score}%${NC} - DEGRADED"
    else
        echo -e "System Health: ${RED}${health_score}%${NC} - CRITICAL"
    fi
    
    # Provide recommendations
    if [ $running_components -lt $total_components ]; then
        echo -e "\n${YELLOW}Recommendations:${NC}"
        
        if ! pgrep -f "ibgateway" > /dev/null 2>&1; then
            echo "  • Start IB Gateway: ~/Jts/ibgateway/1039/ibgateway"
        fi
        
        if [ -z "$(get_pid "main_engine")" ] || ! check_process_by_pid "$(get_pid "main_engine")"; then
            echo "  • Start Trading Engine: $SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh"
        fi
        
        if [ -z "$(get_pid "gui")" ] || ! check_process_by_pid "$(get_pid "gui")"; then
            echo "  • GUI not running - check display settings"
        fi
    fi
    
    echo -e "${CYAN}──────────────────────────────────────────────${NC}"
}

# ===============================================================================
# JSON OUTPUT (Optional)
# ===============================================================================

output_json() {
    # Output status in JSON format for integration with other tools
    cat << EOF
{
    "timestamp": "$(date -Iseconds)",
    "system": {
        "health_score": $health_score,
        "components_running": $running_components,
        "components_total": $total_components
    },
    "components": {
        "ib_gateway": $(pgrep -f "ibgateway" > /dev/null 2>&1 && echo "true" || echo "false"),
        "trading_engine": $(check_process_by_pid "$(get_pid "main_engine")" && echo "true" || echo "false"),
        "gui_dashboard": $(check_process_by_pid "$(get_pid "gui")" && echo "true" || echo "false"),
        "watchdog": $(check_process_by_pid "$(get_pid "watchdog")" && echo "true" || echo "false"),
        "system_monitor": $(check_process_by_pid "$(get_pid "monitor")" && echo "true" || echo "false"),
        "prometheus": $(check_port 9090 && echo "true" || echo "false")
    }
}
EOF
}

# ===============================================================================
# MAIN EXECUTION
# ===============================================================================

main() {
    # Check for JSON output flag
    if [ "$1" = "--json" ]; then
        output_json
        exit 0
    fi
    
    # Clear screen for better visibility (optional)
    if [ "$1" != "--no-clear" ]; then
        clear
    fi
    
    # Display header
    print_header
    echo -e "Timestamp: $(date '+%Y-%m-%d %H:%M:%S ET')"
    
    # Run all checks
    check_ib_gateway
    check_trading_engine
    check_gui_dashboard
    check_monitoring_services
    check_prometheus_metrics
    check_system_resources
    check_log_files
    check_configuration
    
    # Generate summary
    generate_summary
    
    echo ""
}

# ===============================================================================
# SCRIPT EXECUTION
# ===============================================================================

main "$@"