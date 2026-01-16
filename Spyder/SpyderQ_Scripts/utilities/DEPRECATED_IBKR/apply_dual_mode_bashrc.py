#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Unknown
Module: apply_dual_mode_bashrc.py
Purpose: SPYDER - Apply Dual-Mode Bashrc Configuration

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Apply Dual-Mode Bashrc Configuration

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

def backup_current_bashrc():
    """Backup the current .bashrc file"""
    bashrc_path = Path.home() / ".bashrc"

    if not bashrc_path.exists():
        print("⚠️  No existing .bashrc found - will create new one")
        return None

    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path.home() / f".bashrc.backup_{timestamp}"

    try:
        shutil.copy2(bashrc_path, backup_path)
        print(f"✅ Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return None


def create_dual_mode_bashrc():
    """Create the new dual-mode bashrc configuration"""

    bashrc_content = """#!/bin/bash
# ~/.bashrc - SPYDER Dual-Mode Configuration
# Ubuntu 25.04 64-bit + GNOME 48 + Wayland
# Author: Mohamed Talib & SPYDER AI System
# Created: 2025-08-26
# Updated: 2025-10-07 - Added dual-mode IB configuration
# Supports both Local IB Gateway AND Remote TWS for maximum flexibility

# ===============================================================================
# INTERACTIVE SHELL CHECK
# ===============================================================================
case $- in
    *i*) ;;
      *) return;;
esac

# ===============================================================================
# SHELL OPTIONS AND HISTORY
# ===============================================================================
shopt -s histappend
shopt -s checkwinsize
HISTCONTROL=ignoreboth
HISTSIZE=1000
HISTFILESIZE=2000

# ===============================================================================
# PROMPT CONFIGURATION
# ===============================================================================
if [ -z "${debian_chroot:-}" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

case "$TERM" in
    xterm-color|*-256color) color_prompt=yes;;
esac

if [ -n "$force_color_prompt" ]; then
    if [ -x /usr/bin/tput ] && tput setaf 1 >&/dev/null; then
        color_prompt=yes
    else
        color_prompt=
    fi
fi

if [ "$color_prompt" = yes ]; then
    PS1='${debian_chroot:+($debian_chroot)}\\[\\033[01;32m\\]\\u@\\h\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ '
else
    PS1='${debian_chroot:+($debian_chroot)}\\u@\\h:\\w\\$ '
fi
unset color_prompt force_color_prompt

case "$TERM" in
xterm*|rxvt*)
    PS1="\\[\\e]0;${debian_chroot:+($debian_chroot)}\\u@\\h: \\w\\a\\]$PS1"
    ;;
*)
    ;;
esac

# ===============================================================================
# ENVIRONMENT VARIABLES - CORE SYSTEM
# ===============================================================================
export PATH="$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export EDITOR="nano"
export VISUAL="code"

# Development tools paths
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"

# ===============================================================================
# DEVELOPMENT TOOLS CONFIGURATION
# ===============================================================================
# Node.js and package managers
export NPM_CONFIG_PREFIX="$HOME/.npm-global"
export PATH="$HOME/.npm-global/bin:$PATH"

# Python environment management
if command -v pyenv 1>/dev/null 2>&1; then
    eval "$(pyenv init -)"
fi

# ===============================================================================
# SPYDER PROJECT DIRECTORIES
# ===============================================================================
export SPYDER_HOME="$HOME/Projects/Spyder"
export SPYDER_LOGS="$SPYDER_HOME/logs"
export SPYDER_DATA="$SPYDER_HOME/data"
export SPYDER_CONFIG="$SPYDER_HOME/config"

# ===============================================================================
# API KEYS AND CREDENTIALS
# ===============================================================================
# Preserve existing credentials or use placeholders
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-sk-ant-api03-your_key_here}"
export IB_USERNAME="${IB_USERNAME:-your_ib_username}"
export IB_PASSWORD="${IB_PASSWORD:-your_ib_password}"
export GEMINI_API_KEY="${GEMINI_API_KEY:-your_gemini_key_here}"
export GEMINI_MODEL="gemini-2.5-pro"

# ===============================================================================
# SPYDER DUAL-MODE IB CONFIGURATION
# ===============================================================================
# This configuration supports BOTH local IB Gateway AND remote TWS
# Switch between modes using environment variable: IB_CONNECTION_MODE

# Set default connection mode (change this to switch modes)
export IB_CONNECTION_MODE="${IB_CONNECTION_MODE:-gateway}"  # Options: "gateway" or "tws"

# ===============================================================================
# IB GATEWAY VERSION CONFIGURATION
# ===============================================================================
export TWS_MAJOR_VRSN="1039"
export IB_GATEWAY_VERSION="10.39"

# ===============================================================================
# LOCAL IB GATEWAY CONFIGURATION
# ===============================================================================
# Local Gateway Settings
export IB_GATEWAY_HOST_LOCAL="127.0.0.1"
export IB_GATEWAY_PORT_PAPER_LOCAL="4002"    # IB Gateway Paper Port
export IB_GATEWAY_PORT_LIVE_LOCAL="4001"     # IB Gateway Live Port

# Local Gateway Installation Paths
export IB_GATEWAY_DIR="$HOME/Jts/ibgateway/1039"
export IB_JTS_INI="$HOME/Jts/jts.ini"
export IB_GATEWAY_EXECUTABLE="$IB_GATEWAY_DIR/ibgateway"

# ===============================================================================
# REMOTE TWS CONFIGURATION
# ===============================================================================
# Remote TWS Settings (Updated IP: 192.168.1.2)
export IB_REMOTE_TWS_HOST="192.168.1.2"
export IB_TWS_PORT_PAPER="7497"              # TWS Paper Trading Port
export IB_TWS_PORT_LIVE="7496"               # TWS Live Trading Port

# Remote TWS Connection Settings
export IB_WINDOWS_COMPUTER="192.168.1.2"
export IB_CONNECTION_TIMEOUT="30"
export IB_RECONNECTION_ATTEMPTS="5"
export IB_NETWORK_LATENCY_BUFFER="5"

# ===============================================================================
# DYNAMIC MODE SWITCHING
# ===============================================================================
# Set active configuration based on IB_CONNECTION_MODE
if [ "$IB_CONNECTION_MODE" = "gateway" ]; then
    # LOCAL IB GATEWAY MODE
    export IB_CONNECTION_TYPE="local_gateway"
    export IB_HOST="$IB_GATEWAY_HOST_LOCAL"
    export IB_PORT_PAPER="$IB_GATEWAY_PORT_PAPER_LOCAL"
    export IB_PORT_LIVE="$IB_GATEWAY_PORT_LIVE_LOCAL"
    export IB_DEFAULT_PORT="$IB_PORT_PAPER"
    export IB_MODE_DESCRIPTION="Local IB Gateway"
else
    # REMOTE TWS MODE
    export IB_CONNECTION_TYPE="remote_tws"
    export IB_HOST="$IB_REMOTE_TWS_HOST"
    export IB_PORT_PAPER="$IB_TWS_PORT_PAPER"
    export IB_PORT_LIVE="$IB_TWS_PORT_LIVE"
    export IB_DEFAULT_PORT="$IB_PORT_PAPER"
    export IB_MODE_DESCRIPTION="Remote TWS"
fi

# ===============================================================================
# COMMON IB SETTINGS (BOTH MODES)
# ===============================================================================
# Default to paper trading (safety first!)
export IB_TRADING_MODE="paper"

# Universal 8-Client ID Allocation (SPYDER Architecture)
export IB_ORDER_EXECUTION_CLIENT="100"    # Client 1: Order Execution & Primary Trading
export IB_ADMIN_NEWS_CLIENT="101"         # Client 2: Administrative & News Feeds
export IB_CORE_DATA_CLIENT="102"          # Client 3: Core Market Data
export IB_SPY_OPTIONS_CLIENT="103"        # Client 4: SPY Options Chains
export IB_VOLATILITY_CLIENT="104"         # Client 5: Volatility + Market Internals
export IB_MAJOR_INDICES_CLIENT="105"      # Client 6: Major Indices
export IB_EXTENDED_SECTORS_CLIENT="106"   # Client 7: Extended Assets + Sectors
export IB_INTERNATIONAL_CLIENT="107"      # Client 8: International Markets

# Legacy client IDs for backward compatibility
export IB_MASTER_CLIENT="$IB_ADMIN_NEWS_CLIENT"
export IB_DASHBOARD_CLIENT="$IB_CORE_DATA_CLIENT"
export IB_TEST_CLIENT="999"               # High ID for testing

# IB Data Subscription Settings
export IB_MARKET_DATA_TYPE="3"            # 3=delayed, 1=live (requires subscription)
export IB_PREFERRED_SERVER="zdc1.ibllc.com"  # Zurich server

# ===============================================================================
# SPYDER TRADING SYSTEM CONFIGURATION
# ===============================================================================
# Spyder System Settings
export SPYDER_ENV="development"           # development, testing, production
export SPYDER_LOG_LEVEL="INFO"           # DEBUG, INFO, WARNING, ERROR, CRITICAL
export SPYDER_DATABASE="$SPYDER_HOME/data/spyder.db"

# Spyder Trading Parameters
export SPYDER_MAX_POSITIONS="10"
export SPYDER_MAX_DAILY_TRADES="50"
export SPYDER_RISK_LIMIT="10000"         # Maximum risk per day in USD

# Spyder Performance Settings
export SPYDER_ENABLE_CACHE="true"
export SPYDER_CACHE_TTL="300"            # Cache time-to-live in seconds
export SPYDER_THREAD_POOL_SIZE="10"

# ===============================================================================
# STANDARD UBUNTU ALIASES
# ===============================================================================
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias dir='dir --color=auto'
    alias vdir='vdir --color=auto'
    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# Some more ls aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

# Safety aliases
alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'

# Useful shortcuts
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias ~='cd ~'
alias -- -='cd -'

# System monitoring shortcuts
alias df='df -h'
alias du='du -h'
alias free='free -h'
alias ports='netstat -tulanp'

# Network shortcuts
alias myip='curl -s ifconfig.me && echo'
alias speedtest='curl -s https://raw.githubusercontent.com/sivel/speedtest-cli/master/speedtest.py | python3 -'

# Simple notification alias
alias notify='notify-send "Command completed" "$(date)"'

# ===============================================================================
# GIT ALIASES
# ===============================================================================
alias gs='git status'
alias ga='git add'
alias gc='git commit -m'
alias gp='git push'
alias gl='git log --oneline'
alias gd='git diff'
alias gb='git branch'
alias gco='git checkout'

# ===============================================================================
# PYTHON DEVELOPMENT ALIASES
# ===============================================================================
alias py='python3'
alias pip='pip3'
alias venv='python3 -m venv'
alias activate='source venv/bin/activate'

# ===============================================================================
# SPYDER PROJECT ALIASES
# ===============================================================================
alias cdspyder='cd $SPYDER_HOME'
alias spyder-logs='tail -f $SPYDER_LOGS/spyder.log'
alias spyder-test='cd $SPYDER_HOME && python -m pytest'
alias spyder-run='cd $SPYDER_HOME && python SpyderA01_Main.py'

# ===============================================================================
# IB CONNECTION TESTING ALIASES (DUAL-MODE)
# ===============================================================================
# Mode switching aliases
alias ib-mode-gateway='export IB_CONNECTION_MODE="gateway"; source ~/.bashrc; echo "🏪 Switched to Local IB Gateway mode"'
alias ib-mode-tws='export IB_CONNECTION_MODE="tws"; source ~/.bashrc; echo "🌐 Switched to Remote TWS mode"'
alias ib-mode='echo "Current mode: $IB_CONNECTION_MODE ($IB_MODE_DESCRIPTION)"; echo "Host: $IB_HOST:$IB_DEFAULT_PORT"'

# Universal testing aliases (adapt to current mode)
alias ib-test='python $SPYDER_HOME/test_simple_gateway_connection.py'
alias ib-test-advanced='python $SPYDER_HOME/test_direct_connection.py'
alias ib-trigger='python $SPYDER_HOME/trigger_connections_simple.py'
alias ib-ports='netstat -tuln | grep -E ":(4001|4002|7496|7497)"'
alias ib-status='python $SPYDER_HOME/SpyderQ_Scripts/SpyderQ22_CheckIBStatus.py 2>/dev/null || echo "Status script not found"'

# Launch aliases
alias spyder-launch='python $SPYDER_HOME/launch_connection_selector.py'
alias spyder-dashboard='python $SPYDER_HOME/launch_dashboard_with_proactive_connections.py'
alias spyder-gateway='$SPYDER_HOME/launch_spyder_gateway.sh --mode=paper'
alias spyder-tws='$SPYDER_HOME/launch_spyder_tws.sh --mode=paper'

# ===============================================================================
# USEFUL FUNCTIONS
# ===============================================================================
# Function to create a backup with timestamp
backup() {
    if [ $# -eq 0 ]; then
        echo "Usage: backup <file_or_directory>"
        return 1
    fi
    cp -r "$1" "${1}.backup.$(date +%Y%m%d_%H%M%S)"
}

# Function to extract various archive formats
extract() {
    if [ -f "$1" ] ; then
        case $1 in
            *.tar.bz2)   tar xjf "$1"     ;;
            *.tar.gz)    tar xzf "$1"     ;;
            *.bz2)       bunzip2 "$1"     ;;
            *.rar)       unrar x "$1"     ;;
            *.gz)        gunzip "$1"      ;;
            *.tar)       tar xf "$1"      ;;
            *.tbz2)      tar xjf "$1"     ;;
            *.tgz)       tar xzf "$1"     ;;
            *.zip)       unzip "$1"       ;;
            *.Z)         uncompress "$1"  ;;
            *.7z)        7z x "$1"        ;;
            *)           echo "'$1' cannot be extracted via extract()" ;;
        esac
    else
        echo "'$1' is not a valid file"
    fi
}

# Function to check IB connectivity (adapts to current mode)
ib-check() {
    echo "🔍 Checking IB connectivity..."
    echo "=========================================="
    echo "🎯 Current Mode: $IB_CONNECTION_MODE ($IB_MODE_DESCRIPTION)"
    echo "🌐 Target Host: $IB_HOST:$IB_DEFAULT_PORT"
    echo ""

    # Check network connectivity
    if ping -c 1 "$IB_HOST" >/dev/null 2>&1; then
        echo "✅ Host $IB_HOST is reachable"
    else
        echo "❌ Host $IB_HOST is not reachable"
        if [ "$IB_CONNECTION_MODE" = "tws" ]; then
            echo "   Check if Windows computer is online"
        fi
        return 1
    fi

    # Check port connectivity
    if nc -zv "$IB_HOST" "$IB_DEFAULT_PORT" 2>/dev/null; then
        echo "✅ Port $IB_DEFAULT_PORT is accessible"
    else
        echo "❌ Port $IB_DEFAULT_PORT is not accessible"
        if [ "$IB_CONNECTION_MODE" = "gateway" ]; then
            echo "   Check if IB Gateway is running locally"
        else
            echo "   Check if TWS is running on Windows computer"
        fi
    fi

    echo ""
    echo "🔧 Environment:"
    echo "   IB_CONNECTION_MODE=$IB_CONNECTION_MODE"
    echo "   IB_HOST=$IB_HOST"
    echo "   IB_DEFAULT_PORT=$IB_DEFAULT_PORT"
    echo "   IB_TRADING_MODE=$IB_TRADING_MODE"
    echo ""
    echo "🧪 Quick Tests:"
    echo "   ib-test          # Basic connection test"
    echo "   ib-test-advanced # Comprehensive test"
    echo "   ib-trigger       # Trigger connections"
    echo "   spyder-launch    # Launch SPYDER dashboard"
}

# Function to switch IB modes easily
ib-switch() {
    if [ "$1" = "gateway" ] || [ "$1" = "tws" ]; then
        export IB_CONNECTION_MODE="$1"
        source ~/.bashrc
        echo "🔄 Switched to $1 mode"
        ib-check
    else
        echo "Usage: ib-switch [gateway|tws]"
        echo "Current mode: $IB_CONNECTION_MODE"
    fi
}

# ===============================================================================
# BASH COMPLETION
# ===============================================================================
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  elif [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
  fi
fi

# ===============================================================================
# FINAL SETUP
# ===============================================================================
# Display SPYDER status on login
echo "🕷️ SPYDER Trading System Environment Loaded"
echo "   Connection Mode: $IB_CONNECTION_MODE ($IB_MODE_DESCRIPTION)"
echo "   Target: $IB_HOST:$IB_DEFAULT_PORT (${IB_TRADING_MODE})"
echo "   Run 'ib-check' to verify connectivity"
echo "   Run 'ib-switch [gateway|tws]' to change modes"

# ===============================================================================
# END OF .bashrc
# ===============================================================================
"""
    return bashrc_content


def apply_new_bashrc():
    """Apply the new bashrc configuration"""
    bashrc_path = Path.home() / ".bashrc"

    try:
        # Get the new content
        new_content = create_dual_mode_bashrc()

        # Write to .bashrc
        with open(bashrc_path, "w") as f:
            f.write(new_content)

        print(f"✅ New dual-mode bashrc applied to {bashrc_path}")
        return True

    except Exception as e:
        print(f"❌ Failed to apply new bashrc: {e}")
        return False


def show_summary():
    """Show configuration summary and usage instructions"""

    print("\n" + "=" * 60)
    print("🎯 DUAL-MODE BASHRC CONFIGURATION APPLIED")
    print("=" * 60)

    print("\n📋 Available Modes:")
    print("   🏪 gateway - Local IB Gateway (127.0.0.1:4002)")
    print("   🌐 tws     - Remote TWS (192.168.1.2:7497)")

    print("\n🔧 Mode Switching Commands:")
    print("   ib-switch gateway    # Switch to local Gateway mode")
    print("   ib-switch tws        # Switch to remote TWS mode")
    print("   ib-mode              # Show current mode")
    print("   ib-check             # Test current mode connectivity")

    print("\n🧪 Testing Commands:")
    print("   ib-test              # Basic connection test")
    print("   ib-test-advanced     # Comprehensive connection test")
    print("   ib-trigger           # Trigger connections")

    print("\n🚀 Launch Commands:")
    print("   spyder-launch        # Launch connection selector")
    print("   spyder-dashboard     # Launch trading dashboard")
    print("   spyder-gateway       # Launch with Gateway mode")
    print("   spyder-tws           # Launch with TWS mode")

    print("\n✨ Key Features:")
    print("   ✅ Supports both local Gateway and remote TWS")
    print("   ✅ Easy mode switching with ib-switch command")
    print("   ✅ Docker parts removed as requested")
    print("   ✅ Remote TWS IP updated to 192.168.1.2")
    print("   ✅ Universal 8-Client ID allocation (100-107)")
    print("   ✅ Automatic mode-aware connectivity testing")

    print("\n💡 Next Steps:")
    print("   1. Reload your shell: source ~/.bashrc")
    print("   2. Test connectivity: ib-check")
    print("   3. Switch modes as needed: ib-switch [gateway|tws]")
    print("   4. Launch SPYDER: spyder-launch")


def main():
    """Main application function"""

    print("🕷️ SPYDER - Apply Dual-Mode Bashrc Configuration")
    print("=" * 60)
    print("Applying flexible bashrc configuration supporting:")
    print("   🏪 Local IB Gateway (127.0.0.1:4002)")
    print("   🌐 Remote TWS (192.168.1.2:7497)")
    print("   🔄 Easy mode switching")
    print("   🚫 Docker parts removed")

    # Step 1: Backup current bashrc
    print("\n[Step 1] Backing up current .bashrc...")
    backup_path = backup_current_bashrc()

    # Step 2: Apply new configuration
    print("\n[Step 2] Applying new dual-mode configuration...")
    if not apply_new_bashrc():
        print("❌ Failed to apply new configuration")
        return 1

    # Step 3: Show summary
    print("\n[Step 3] Configuration summary...")
    show_summary()

    print("\n🎉 SUCCESS!")
    print("✅ Dual-mode bashrc configuration installed")

    if backup_path:
        print(f"✅ Original bashrc backed up to: {backup_path}")

    print(f"\n🚀 To activate the new configuration:")
    print(f"   source ~/.bashrc")
    print(f"   ib-check")

    return 0


if __name__ == "__main__":
    sys.exit(main())
