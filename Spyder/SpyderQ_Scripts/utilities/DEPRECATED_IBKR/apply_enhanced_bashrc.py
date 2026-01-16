#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Unknown
Module: apply_enhanced_bashrc.py
Purpose: Apply Enhanced Bashrc Configuration - Direct Application

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    Apply Enhanced Bashrc Configuration - Direct Application

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from pathlib import Path
from datetime import datetime

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import shutil

def apply_enhanced_bashrc():
    """Apply enhanced bashrc configuration"""

    print("🕷️ SPYDER Enhanced Bashrc Application")
    print("=" * 60)
    print(f"Timestamp: {datetime.now()}")
    print("=" * 60)
    print()

    bashrc_path = Path.home() / ".bashrc"
    backup_dir = Path.home() / ".spyder_backups"

    # Create backup
    print("📦 Creating backup...")
    backup_dir.mkdir(exist_ok=True)

    if bashrc_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"bashrc_backup_enhanced_{timestamp}"
        shutil.copy2(bashrc_path, backup_path)
        print(f"✅ Backup created: {backup_path}")

    # Read current bashrc
    current_content = ""
    if bashrc_path.exists():
        with open(bashrc_path, "r") as f:
            current_content = f.read()

    # Remove old SPYDER configuration if exists
    if (
        "SPYDER" in current_content
        and "TRADING SYSTEM CONFIGURATION" in current_content
    ):
        print("⚠️  Removing old SPYDER configuration...")
        lines = current_content.split("\n")
        new_lines = []
        skip = False

        for line in lines:
            if "SPYDER" in line and "TRADING SYSTEM CONFIGURATION" in line:
                skip = True
                continue
            elif skip and line.strip().startswith("#") and "====" in line:
                skip = False
                continue

            if not skip:
                new_lines.append(line)

        current_content = "\n".join(new_lines).rstrip()

    # Generate enhanced configuration
    enhanced_config = generate_enhanced_config()

    # Combine content
    updated_content = current_content + "\n" + enhanced_config

    # Write to bashrc
    print("📝 Writing enhanced configuration...")
    with open(bashrc_path, "w") as f:
        f.write(updated_content)

    # Set secure permissions
    os.chmod(bashrc_path, 0o600)
    print("🔒 Set secure permissions (600)")

    print("\n" + "=" * 60)
    print("✅ ENHANCED BASHRC APPLIED SUCCESSFULLY!")
    print("=" * 60)
    print()
    print("🚀 NEXT STEPS:")
    print("1. Reload bashrc:")
    print("   source ~/.bashrc")
    print()
    print("2. Launch SPYDER:")
    print("   spyder-launch")
    print()
    print("3. Quick commands available:")
    print("   spyder-paper              # Paper trading launch")
    print("   gateway-nuclear-restart   # Fix stuck Gateway")
    print("   ib-switch tws             # Switch to remote TWS")
    print("   ib-check                  # Test connection")
    print("   spyder-help               # Full command list")
    print()
    print("🎉 Your professional trading environment is ready!")
    print()


def generate_enhanced_config():
    """Generate the enhanced bashrc configuration"""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""
# ============================================================================
# SPYDER ENHANCED TRADING SYSTEM CONFIGURATION
# Generated: {timestamp}
# Support: Dual-mode credentials + Local Gateway + Remote TWS + Nuclear Restart
# ============================================================================

# ============================================================================
# TRADING CREDENTIALS (Configure with your actual credentials)
# ============================================================================
# NOTE: Replace these placeholder values with your actual IB credentials

# Paper Trading Credentials (Safe Mode)
export IB_PAPER_USERNAME="your_paper_username"
export IB_PAPER_PASSWORD="your_paper_password"

# Live Trading Credentials (Real Money - Use with Extreme Caution!)
export IB_LIVE_USERNAME="your_live_username"
export IB_LIVE_PASSWORD="your_live_password"

# Current working credentials (from your current setup)
export IB_USERNAME="mtalib342"
export IB_PASSWORD="Gintaro007$"
export IB_TRADING_MODE="paper"

# ============================================================================
# NETWORK CONFIGURATION - DUAL MODE SUPPORT
# ============================================================================

# Local IB Gateway Configuration
export IB_LOCAL_GATEWAY_PAPER_PORT="4002"
export IB_LOCAL_GATEWAY_LIVE_PORT="4001"

# Remote TWS Configuration
export IB_REMOTE_TWS_HOST="192.168.1.2"
export IB_REMOTE_TWS_PAPER_PORT="7497"
export IB_REMOTE_TWS_LIVE_PORT="7496"

# Current connection settings
export IB_CONNECTION_TYPE="local_gateway"
export IB_GATEWAY_HOST="127.0.0.1"
export IB_DEFAULT_PORT="4002"

# ============================================================================
# SPYDER SYSTEM PATHS
# ============================================================================
export SPYDER_HOME="$HOME/Projects/Spyder"
export SPYDER_LOGS="$HOME/spyder_logs"
export SPYDER_CONFIG="$SPYDER_HOME/config"
export SPYDER_DATA="$SPYDER_HOME/data"

# ============================================================================
# JAVA AND SYSTEM CONFIGURATION
# ============================================================================
export JAVA_HOME="/usr/lib/jvm/java-11-openjdk-amd64"
export PATH="$JAVA_HOME/bin:$PATH"
export DISPLAY=":0"

# IB Gateway Paths
export IB_GATEWAY_DIR="$HOME/Jts/ibgateway/1039"
export IB_TWS_DIR="$HOME/Jts/tws"

# ============================================================================
# SPYDER LAUNCHER FUNCTIONS
# ============================================================================

# Main SPYDER launcher with enhanced GUI
spyder-launch() {{
    echo "🕷️  Launching SPYDER Trading System..."
    cd "$SPYDER_HOME"

    # Activate virtual environment if available
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    fi

    # Launch enhanced GUI launcher
    python3 spyder_launcher_enhanced.py "$@"
}}

# Quick launch modes
spyder-paper() {{
    echo "📄 Starting SPYDER in Paper Trading mode..."
    export SPYDER_TRADING_MODE="paper"
    export SPYDER_CONNECTION_TYPE="local_gateway"
    spyder-launch --mode=paper
}}

spyder-live() {{
    echo "🔴 Starting SPYDER in LIVE Trading mode..."
    echo "⚠️  WARNING: This will use REAL MONEY!"
    read -p "Are you absolutely sure? (yes/no): " confirm

    if [ "$confirm" = "yes" ]; then
        export SPYDER_TRADING_MODE="live"
        export SPYDER_CONNECTION_TYPE="local_gateway"
        spyder-launch --mode=live
    else
        echo "❌ LIVE trading cancelled"
    fi
}}

spyder-remote() {{
    echo "🌐 Starting SPYDER with Remote TWS..."
    export SPYDER_CONNECTION_TYPE="remote_tws"
    export IB_GATEWAY_HOST="$IB_REMOTE_TWS_HOST"
    spyder-launch --connection=remote
}}

# Original launcher for compatibility
spyder-dashboard() {{
    cd "$SPYDER_HOME" && python3 SpyderG_GUI/SpyderG02_GUIEntry.py
}}

# ============================================================================
# GATEWAY MANAGEMENT FUNCTIONS (Including Nuclear Restart!)
# ============================================================================

# Nuclear restart - Your proven method for fixing stuck Gateway!
gateway-nuclear-restart() {{
    echo "🔥 NUCLEAR RESTART: Stopping all Gateway processes..."
    pkill -9 -f ibgateway 2>/dev/null || true
    sleep 3

    echo "🧹 Cleaning temporary files..."
    find "$HOME/Jts" -name "*.lck" -delete 2>/dev/null || true
    find "$HOME/Jts" -name "*.lock" -delete 2>/dev/null || true
    find "$HOME/Jts" -name ".ibgateway*" -delete 2>/dev/null || true

    echo "🚀 Starting fresh Gateway..."
    cd "$HOME/Jts/ibgateway/1039"
    nohup ./ibgateway > /dev/null 2>&1 &

    echo "✅ Nuclear restart complete"
    echo "   Wait 30 seconds for Gateway to fully initialize"
    echo "   Then run: gateway-test"
}}

# Gateway status check
gateway-status() {{
    echo "🔍 IB Gateway Status:"

    # Check processes
    local gateway_pids=$(pgrep -f ibgateway 2>/dev/null || echo "")
    if [ -n "$gateway_pids" ]; then
        echo "✅ Gateway Process: Running (PIDs: $gateway_pids)"
    else
        echo "❌ Gateway Process: Not running"
    fi

    # Check ports
    local port_4002=$(netstat -tlpn 2>/dev/null | grep ":4002" || echo "")
    local port_4001=$(netstat -tlpn 2>/dev/null | grep ":4001" || echo "")

    if [ -n "$port_4002" ]; then
        echo "✅ Paper Port (4002): Listening"
    else
        echo "❌ Paper Port (4002): Not listening"
    fi

    if [ -n "$port_4001" ]; then
        echo "✅ Live Port (4001): Listening"
    else
        echo "❌ Live Port (4001): Not listening"
    fi
}}

# Quick API connection test
gateway-test() {{
    echo "🧪 Testing Gateway API connection..."

    # Test paper port
    if timeout 3 bash -c "</dev/tcp/127.0.0.1/4002" 2>/dev/null; then
        echo "✅ Paper API (4002): Connected"
        # Try actual API test if ib_async is available
        if command -v python3 >/dev/null; then
            python3 -c "
import asyncio
try:
    from ib_async import IB
    ib = IB()
    asyncio.run(ib.connectAsync('127.0.0.1', 4002, clientId=999))
    print('✅ Paper API: Full handshake successful!')
    print(f'   Accounts: {{ib.managedAccounts()}}')
    ib.disconnect()
except Exception as e:
    print(f'⚠️  Paper API: Socket connected but handshake failed')
" 2>/dev/null || echo "   (Basic socket test only)"
        fi
    else
        echo "❌ Paper API (4002): Connection failed"
    fi

    # Test live port
    if timeout 3 bash -c "</dev/tcp/127.0.0.1/4001" 2>/dev/null; then
        echo "✅ Live API (4001): Connected"
    else
        echo "❌ Live API (4001): Connection failed"
    fi
}}

# Gateway restart (normal)
gateway-restart() {{
    echo "🔄 Restarting IB Gateway (normal)..."
    pkill -f ibgateway 2>/dev/null || true
    sleep 5

    cd "$HOME/Jts/ibgateway/1039"
    nohup ./ibgateway > /dev/null 2>&1 &

    echo "✅ Gateway restarting..."
    echo "   Wait for login and full initialization"
}}

# Gateway logs viewer
gateway-logs() {{
    echo "📋 IB Gateway Logs:"
    local log_dir="$HOME/Jts/ibgateway/1039/logs"

    if [ -d "$log_dir" ]; then
        echo "Recent log files:"
        ls -lt "$log_dir"/*.log 2>/dev/null | head -5
        echo ""
        echo "To follow latest log:"
        echo "  tail -f $log_dir/ibgateway-$(date +%Y%m%d).log"
    else
        echo "⚠️  Log directory not found: $log_dir"
    fi
}}

# ============================================================================
# CONNECTION MODE SWITCHING
# ============================================================================

# Switch between local and remote
ib-switch() {{
    case "$1" in
        "gateway"|"local")
            echo "🏠 Switching to Local IB Gateway mode"
            export IB_CONNECTION_TYPE="local_gateway"
            export IB_GATEWAY_HOST="127.0.0.1"
            ;;
        "tws"|"remote")
            echo "🌐 Switching to Remote TWS mode"
            export IB_CONNECTION_TYPE="remote_tws"
            export IB_GATEWAY_HOST="$IB_REMOTE_TWS_HOST"
            ;;
        *)
            echo "Usage: ib-switch [gateway|tws]"
            echo "  gateway/local  - Use local IB Gateway"
            echo "  tws/remote     - Use remote TWS"
            return 1
            ;;
    esac

    echo "✅ Connection mode updated"
    echo "   Current mode: $IB_CONNECTION_TYPE"
    echo "   Current host: $IB_GATEWAY_HOST"
}}

# Check current connection configuration
ib-check() {{
    echo "🔍 Current IB Connection Configuration:"
    echo "   Mode: ${{IB_CONNECTION_TYPE:-local_gateway}}"
    echo "   Host: ${{IB_GATEWAY_HOST:-127.0.0.1}}"
    echo "   Trading: ${{SPYDER_TRADING_MODE:-paper}}"
    echo ""

    # Test current connection
    local host="${{IB_GATEWAY_HOST:-127.0.0.1}}"
    local port

    if [[ "${{SPYDER_TRADING_MODE:-paper}}" == "paper" ]]; then
        if [[ "${{IB_CONNECTION_TYPE:-local_gateway}}" == "local_gateway" ]]; then
            port="$IB_LOCAL_GATEWAY_PAPER_PORT"
        else
            port="$IB_REMOTE_TWS_PAPER_PORT"
        fi
    else
        if [[ "${{IB_CONNECTION_TYPE:-local_gateway}}" == "local_gateway" ]]; then
            port="$IB_LOCAL_GATEWAY_LIVE_PORT"
        else
            port="$IB_REMOTE_TWS_LIVE_PORT"
        fi
    fi

    if timeout 3 bash -c "</dev/tcp/$host/$port" 2>/dev/null; then
        echo "✅ Connection test: PASSED ($host:$port)"
    else
        echo "❌ Connection test: FAILED ($host:$port)"
    fi
}}

# ============================================================================
# SPYDER UTILITY FUNCTIONS
# ============================================================================

# Navigate to SPYDER
spyder() {{
    cd "$SPYDER_HOME"
    if [ -d ".venv" ]; then
        echo "💡 Virtual environment available. Run 'spyder-env' to activate."
    fi
}}

# Activate SPYDER virtual environment
spyder-env() {{
    if [ -d "$SPYDER_HOME/.venv" ]; then
        source "$SPYDER_HOME/.venv/bin/activate"
        echo "🐍 SPYDER virtual environment activated"
    else
        echo "❌ Virtual environment not found at $SPYDER_HOME/.venv"
    fi
}}

# SPYDER status check
spyder-status() {{
    echo "🕷️  SPYDER System Status:"

    # Check processes
    local spyder_pids=$(pgrep -f -i spyder 2>/dev/null || echo "")
    if [ -n "$spyder_pids" ]; then
        echo "✅ SPYDER Processes: Running (PIDs: $spyder_pids)"
    else
        echo "⚪ SPYDER Processes: Not running"
    fi

    # Check directories
    if [ -d "$SPYDER_HOME" ]; then
        echo "✅ SPYDER Home: $SPYDER_HOME"
    else
        echo "❌ SPYDER Home: Not found at $SPYDER_HOME"
    fi

    if [ -d "$SPYDER_LOGS" ]; then
        echo "✅ SPYDER Logs: $SPYDER_LOGS"
    else
        echo "⚪ SPYDER Logs: Directory not created yet"
    fi
}}

# ============================================================================
# COMPREHENSIVE HELP SYSTEM
# ============================================================================

spyder-help() {{
    cat << 'EOF'
🕷️  SPYDER ENHANCED TRADING SYSTEM - Command Reference
========================================================

🚀 MAIN LAUNCHERS:
  spyder-launch         Enhanced GUI launcher (recommended)
  spyder-paper          Quick Paper trading launch
  spyder-live           Quick Live trading launch (with confirmation)
  spyder-remote         Remote TWS connection launch
  spyder-dashboard      Original dashboard launcher

🔥 GATEWAY MANAGEMENT:
  gateway-nuclear-restart    Nuclear restart (fixes stuck Gateway)
  gateway-restart            Normal Gateway restart
  gateway-status            Show Gateway process and port status
  gateway-test              Test API connection (paper + live ports)
  gateway-logs              View Gateway log files

🌐 CONNECTION SWITCHING:
  ib-switch gateway         Switch to Local IB Gateway mode
  ib-switch tws             Switch to Remote TWS mode
  ib-check                  Show current connection config + test

🕷️  SPYDER UTILITIES:
  spyder                    Navigate to SPYDER directory
  spyder-env                Activate Python virtual environment
  spyder-status             Show SPYDER system status
  spyder-help               Show this help

💡 EXAMPLES:
  spyder-launch             # Start enhanced GUI launcher
  gateway-nuclear-restart   # Fix stuck Gateway (your proven method!)
  ib-switch tws             # Switch to remote TWS mode
  spyder-paper              # Quick paper trading launch
  ib-check                  # Test current connection

📋 CURRENT CONFIGURATION:
  Default Mode: Paper Trading
  Local Gateway: 127.0.0.1 (Ports: 4002/4001)
  Remote TWS:    192.168.1.2 (Ports: 7497/7496)

🔒 SECURITY NOTE:
  Update IB_PAPER_USERNAME, IB_PAPER_PASSWORD, IB_LIVE_USERNAME,
  and IB_LIVE_PASSWORD with your actual credentials in ~/.bashrc

🔥 NUCLEAR RESTART:
  Your proven method for fixing Gateway stuck states!
  Use: gateway-nuclear-restart

EOF
}}

# ============================================================================
# INITIALIZATION
# ============================================================================

# Set default connection mode if not already set
export IB_CONNECTION_TYPE="${{IB_CONNECTION_TYPE:-local_gateway}}"
export IB_GATEWAY_HOST="${{IB_GATEWAY_HOST:-127.0.0.1}}"
export SPYDER_TRADING_MODE="${{SPYDER_TRADING_MODE:-paper}}"

# Show welcome message on first load
if [ -z "$SPYDER_ENHANCED_WELCOME_SHOWN" ]; then
    export SPYDER_ENHANCED_WELCOME_SHOWN=1
    echo ""
    echo "🕷️  SPYDER Enhanced Trading System loaded!"
    echo "   🚀 Quick start: spyder-launch"
    echo "   🔥 Gateway fix: gateway-nuclear-restart"
    echo "   🌐 Switch mode: ib-switch tws"
    echo "   ❓ Full help:   spyder-help"
    echo ""
fi

"""


if __name__ == "__main__":
    try:
        apply_enhanced_bashrc()
        print("🎉 Success! Your enhanced trading environment is ready!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
