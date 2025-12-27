#!/bin/bash
# ~/.bashrc - SPYDER Dual-Mode Configuration
# Ubuntu 25.04 64-bit + GNOME 48 + Wayland
# Author: Mohamed Talib & SPYDER AI System
# Created: 2025-08-26
# Updated: 2025-10-07 - Client IDs 101-108 + Dual Credentials (Paper/Live)
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
    PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
else
    PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w\$ '
fi
unset color_prompt force_color_prompt

case "$TERM" in
xterm*|rxvt*)
    PS1="\[\e]0;${debian_chroot:+($debian_chroot)}\u@\h: \w\a\]$PS1"
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
# API Keys (replace with your actual keys)
export ANTHROPIC_API_KEY="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"
export GEMINI_API_KEY="AIzaSyCFep-rScEUnB9TaPff0DLbaE6kOnH1UmY"
export GEMINI_MODEL="gemini-2.5-pro"
export ZAI_API_KEY="2c4f34c2f28a48f4bc8a17deb274eb05.kERAfHjDoZq7YNwM"
export ZHIPUAI_API_KEY="2c4f34c2f28a48f4bc8a17deb274eb05.kERAfHjDoZq7YNwM"

# ===============================================================================
# GLM-4.6 via Claude Code Integration (Zed IDE)
# ===============================================================================
export ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic"
export ANTHROPIC_AUTH_TOKEN="2c4f34c2f28a48f4bc8a17deb274eb05.kERAfHjDoZq7YNwM"
export ANTHROPIC_API_KEY="2c4f34c2f28a48f4bc8a17deb274eb05.kERAfHjDoZq7YNwM"
# alias glm-claude="claude --ide"

# ===============================================================================
# Maestro CLM Coder via TCP Port | Speaks the Zed Agent Protocol (ACP) over TCP
# Runs as a separate, standalone process (not inside Zed)
# Listens for connections on a TCP port (like a mini web server)
# Zed connects to it over the network (localhost), instead of spawning it as a subprocess
# It can run before, after, or independently of Zed
# ===============================================================================

maestro-glm() {
  echo "🎩 Launching GLM-4.6 TCP Agent on port 5678..."
  nohup python3 ~/.maestro-agents/glm-tcp/server.py >/dev/null 2>&1 &
  sleep 1
  echo "🧠 Starting Zed IDE..."
  zed
}

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
export IB_GATEWAY_PORT_PAPER_LOCAL="4002"
export IB_GATEWAY_PORT_LIVE_LOCAL="4001"

# Local Gateway Installation Paths
export IB_GATEWAY_DIR="$HOME/Jts/ibgateway/1039"
export IB_JTS_INI="$HOME/Jts/jts.ini"
export IB_GATEWAY_EXECUTABLE="$IB_GATEWAY_DIR/ibgateway"

# ===============================================================================
# REMOTE TWS CONFIGURATION
# ===============================================================================
# Remote TWS Settings
export IB_REMOTE_TWS_HOST="192.168.1.2"
export IB_TWS_PORT_PAPER="7497"
export IB_TWS_PORT_LIVE="7496"

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
    export IB_CONNECTION_TYPE="local_gateway"
    export IB_HOST="$IB_GATEWAY_HOST_LOCAL"
    export IB_PORT_PAPER="$IB_GATEWAY_PORT_PAPER_LOCAL"
    export IB_PORT_LIVE="$IB_GATEWAY_PORT_LIVE_LOCAL"
    export IB_DEFAULT_PORT="$IB_PORT_PAPER"
    export IB_MODE_DESCRIPTION="Local IB Gateway"
else
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
export IB_TRADING_MODE="${IB_TRADING_MODE:-paper}"

# ===============================================================================
# SPYDER GATEWAY CREDENTIALS - DUAL MODE (PAPER + LIVE)
# ===============================================================================
# Paper Trading Credentials (Safe Mode)
export IB_PAPER_USERNAME="mtalib342"
export IB_PAPER_PASSWORD="Gintaro007$"

# Live Trading Credentials (Real Money - Use with Extreme Caution!)
export IB_LIVE_USERNAME="mtalib007"
export IB_LIVE_PASSWORD="Alifima007$"

# Dynamic credential selection based on trading mode
# Credentials automatically switch when IB_TRADING_MODE changes
if [ "$IB_TRADING_MODE" = "live" ]; then
    export IB_USERNAME="mtalib007"
    export IB_PASSWORD="Alifima007$"
else
    # Default to paper (safety first!)
    export IB_USERNAME="mtalib342"
    export IB_PASSWORD="Gintaro007$"
fi

# ===============================================================================
# UNIVERSAL 8-CLIENT ID ALLOCATION (SPYDER Architecture)
# Client IDs: 101-108 (maps perfectly to Client 1-8)
# Formula: client_id = 100 + client_number
# ===============================================================================
# Special System Coordinator (ID 100)
export IB_SYSTEM_COORDINATOR="100"

# Production Client IDs (101-108 = Clients 1-8)
export IB_ORDER_EXECUTION_CLIENT="101"
export IB_ADMIN_NEWS_CLIENT="102"
export IB_CORE_DATA_CLIENT="103"
export IB_SPY_OPTIONS_CLIENT="104"
export IB_VOLATILITY_CLIENT="105"
export IB_MAJOR_INDICES_CLIENT="106"
export IB_EXTENDED_SECTORS_CLIENT="107"
export IB_INTERNATIONAL_CLIENT="108"

# Legacy client IDs for backward compatibility
export IB_MASTER_CLIENT="$IB_ADMIN_NEWS_CLIENT"
export IB_DASHBOARD_CLIENT="$IB_CORE_DATA_CLIENT"
export IB_TEST_CLIENT="999"

# IB Data Subscription Settings
export IB_MARKET_DATA_TYPE="3"
export IB_PREFERRED_SERVER="zdc1.ibllc.com"

# ===============================================================================
# Spyder System Settings
export SPYDER_ENV="development"
export SPYDER_LOG_LEVEL="INFO"
export SPYDER_DATABASE="$SPYDER_HOME/data/spyder.db"

# Spyder Trading Parameters
export SPYDER_MAX_POSITIONS="10"
export SPYDER_MAX_DAILY_TRADES="50"
export SPYDER_RISK_LIMIT="10000"

# Spyder Performance Settings
export SPYDER_ENABLE_CACHE="true"
export SPYDER_CACHE_TTL="300"
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

alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias ~='cd ~'
alias -- -='cd -'
alias df='df -h'
alias du='du -h'
alias free='free -h'
alias ports='netstat -tulanp'
alias myip='curl -s ifconfig.me && echo'
alias speedtest='curl -s https://raw.githubusercontent.com/sivel/speedtest-cli/master/speedtest.py | python3 -'
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
# IB CONNECTION MODE SWITCHING
# ===============================================================================
alias ib-mode-gateway='export IB_CONNECTION_MODE="gateway"; source ~/.bashrc; echo "🪟 Switched to Local IB Gateway mode"'
alias ib-mode-tws='export IB_CONNECTION_MODE="tws"; source ~/.bashrc; echo "🌐 Switched to Remote TWS mode"'
alias ib-mode='echo "Current mode: $IB_CONNECTION_MODE ($IB_MODE_DESCRIPTION)"; echo "Host: $IB_HOST:$IB_DEFAULT_PORT"'

# ===============================================================================
# IB TRADING MODE SWITCHING (PAPER/LIVE)
# ===============================================================================
alias ib-mode-paper='export IB_TRADING_MODE="paper"; source ~/.bashrc; echo "📄 Switched to PAPER trading (safe mode)"'
alias ib-show-mode='echo "Trading Mode: $IB_TRADING_MODE | Active User: $IB_USERNAME | Port: $IB_DEFAULT_PORT"'

# ===============================================================================
# IB CONNECTION TESTING ALIASES
# ===============================================================================
alias ib-test='python $SPYDER_HOME/test_simple_gateway_connection.py'
alias ib-test-advanced='python $SPYDER_HOME/test_direct_connection.py'
alias ib-trigger='python $SPYDER_HOME/trigger_connections_simple.py'
alias ib-ports='netstat -tuln | grep -E ":(4001|4002|7496|7497)"'
alias ib-status='python $SPYDER_HOME/SpyderQ_Scripts/SpyderQ22_CheckIBStatus.py 2>/dev/null || echo "Status script not found"'

# ===============================================================================
# SPYDER LAUNCH ALIASES
# ===============================================================================
alias spyder-launch='python $SPYDER_HOME/launch_connection_selector.py'
alias spyder-dashboard='python $SPYDER_HOME/launch_dashboard_with_proactive_connections.py'
alias spyder-gateway='$SPYDER_HOME/launch_spyder_gateway.sh --mode=paper'
alias spyder-tws='$SPYDER_HOME/launch_spyder_tws.sh --mode=paper'

# ===============================================================================
# USEFUL FUNCTIONS
# ===============================================================================
backup() {
    if [ $# -eq 0 ]; then
        echo "Usage: backup <file_or_directory>"
        return 1
    fi
    cp -r "$1" "${1}.backup.$(date +%Y%m%d_%H%M%S)"
}

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

ib-check() {
    echo "🔍 Checking IB connectivity..."
    echo "=========================================="
    echo "🎯 Current Mode: $IB_CONNECTION_MODE ($IB_MODE_DESCRIPTION)"
    echo "🌐 Target Host: $IB_HOST:$IB_DEFAULT_PORT"
    echo "💰 Trading Mode: $IB_TRADING_MODE"
    
    # Show which credentials are active
    if [ "$IB_TRADING_MODE" = "live" ]; then
        echo "🔴 LIVE CREDENTIALS ACTIVE: $IB_USERNAME"
        echo "   ⚠️  WARNING: REAL MONEY ACCOUNT!"
    else
        echo "📄 PAPER CREDENTIALS ACTIVE: $IB_USERNAME"
    fi
    echo ""

    if ping -c 1 "$IB_HOST" >/dev/null 2>&1; then
        echo "✅ Host $IB_HOST is reachable"
    else
        echo "❌ Host $IB_HOST is not reachable"
        if [ "$IB_CONNECTION_MODE" = "tws" ]; then
            echo "   Check if Windows computer is online"
        fi
        return 1
    fi

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
    echo "   IB_USERNAME=$IB_USERNAME"
    echo ""
    echo "🎯 Client ID Mapping (101-108 = Clients 1-8):"
    echo "   100: System Coordinator"
    echo "   101: Client 1 (Order Execution)"
    echo "   102: Client 2 (Admin/News)"
    echo "   103: Client 3 (Core Data)"
    echo "   104: Client 4 (SPY Options)"
    echo "   105: Client 5 (Volatility)"
    echo "   106: Client 6 (Indices)"
    echo "   107: Client 7 (Sectors)"
    echo "   108: Client 8 (International)"
    echo ""
    echo "🧪 Quick Tests:"
    echo "   ib-test          # Basic connection test"
    echo "   ib-test-advanced # Comprehensive test"
    echo "   ib-trigger       # Trigger connections"
    echo "   spyder-launch    # Launch SPYDER dashboard"
}

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

ib-mode-live() {
    echo ""
    echo "⚠️  =================================="
    echo "⚠️  WARNING: LIVE TRADING MODE"
    echo "⚠️  =================================="
    echo ""
    echo "   This will switch to REAL MONEY credentials!"
    echo "   All trades will use your LIVE account."
    echo "   Current paper user: $IB_PAPER_USERNAME"
    echo "   Will switch to live user: $IB_LIVE_USERNAME"
    echo ""
    read -p "   Type 'YES' in ALL CAPS to confirm: " confirm
    
    if [ "$confirm" = "YES" ]; then
        export IB_TRADING_MODE="live"
        source ~/.bashrc
        echo ""
        echo "🔴 LIVE TRADING MODE ACTIVATED 🔴"
        echo "   Active credentials: $IB_USERNAME"
        echo ""
        ib-check
    else
        echo ""
        echo "❌ Live mode cancelled - staying in paper mode"
        echo "   Current user: $IB_USERNAME (paper)"
        echo ""
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
# END OF .bashrc
# ===============================================================================
export ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic"
export ANTHROPIC_AUTH_TOKEN="YOUR_GLM4.6_API_KEY"
adam@Captova:~$ 


