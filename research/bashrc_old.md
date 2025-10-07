(.venv) adam@Captova:~/Projects/Spyder$ cat  ~/.bashrc
# ~/.bashrc - System Configuration
# Ubuntu 25.04 64-bit + GNOME 48 + Wayland
# Author: Mohamed Talib
# Created: 2025-08-26
# Updated: 2025-01-24 - Added complete Spyder IB configuration

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
HISTCONTROL=ignoreboth
shopt -s histappend
HISTSIZE=2000
HISTFILESIZE=4000
shopt -s checkwinsize
shopt -s globstar

[ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"

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
# Core system paths
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PATH="$HOME/.local/bin:$PATH"

# Development tools paths
export PATH="$HOME/.npm-global/bin:$PATH"
export PATH="$HOME/.bun/bin:$PATH"
export PATH="$HOME/.local/share/pnpm:$PATH"
export PATH="$HOME/.pyenv/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"

# ===============================================================================
# DEVELOPMENT TOOLS CONFIGURATION
# ===============================================================================
# Node.js and package managers
export BUN_INSTALL="$HOME/.bun"
export PNPM_HOME="$HOME/.local/share/pnpm"

# Python environment management
export PYENV_ROOT="$HOME/.pyenv"

# Initialize pyenv if available
if command -v pyenv 1>/dev/null 2>&1; then
    eval "$(pyenv init -)"
fi

# ===============================================================================
# CUSTOM DIRECTORY SHORTCUTS
# ===============================================================================
export XDG_PROJECTS_DIR="$HOME/Projects"
export XDG_DROPBOX_DIR="$HOME/DropBox"
export XDG_BACKUP_DIR="$HOME/Backup"
export XDG_TESTING_DIR="$HOME/Testing"

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
# Anthropic API (replace with your actual key)
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxxxxxxxxxxx
# Interactive Brokers Credentials (replace with your actual credentials)
export IB_USERNAME="xxxxxxxxx"
export IB_PASSWORD="xxxxxxxxxx$"
export GEMINI_API_KEY="xxxxxxxxxxxxxxxxxxxxxY"
export GEMINI_MODEL="gemini-2.5-pro"
# ===============================================================================
# INTERACTIVE BROKERS CONFIGURATION - COMPLETE SETUP
# ===============================================================================
# IB Gateway Version Configuration

# IB Gateway Connection Settings

# Default to paper trading (safety first!)

# IB Client ID Allocation (as per Spyder architecture)

# IB Gateway Installation Paths

# IB Gateway Docker Configuration

# IB Data Subscription Settings

# IB Server Selection (Force Zurich routing)

# ===============================================================================
# ===============================================================================
# INTERACTIVE BROKERS CONFIGURATION - REMOTE TWS SETUP
# ===============================================================================
# IB Gateway Version Configuration
export TWS_MAJOR_VRSN="1039"
export IB_GATEWAY_VERSION="10.39"

# Remote TWS Configuration (Updated for Windows Computer)
export IB_REMOTE_TWS_HOST="192.168.1.244"
export IB_TWS_PORT_PAPER="7497"        # TWS Paper Trading Port
export IB_TWS_PORT_LIVE="7496"         # TWS Live Trading Port

# Legacy Gateway Ports (for backward compatibility)
export IB_GATEWAY_HOST="192.168.1.244"   # Updated to remote TWS
export IB_GATEWAY_PORT_PAPER="7497"    # Updated to TWS paper port
export IB_GATEWAY_PORT_LIVE="7496"     # Updated to TWS live port

# Default to paper trading (safety first!)
export IB_DEFAULT_PORT="$IB_TWS_PORT_PAPER"
export IB_TRADING_MODE="paper"

# IB Client ID Allocation (as per Spyder architecture)
export IB_ORDER_EXECUTION_CLIENT="1"    # For order execution
export IB_MASTER_CLIENT="2"             # For account/positions monitoring
export IB_DASHBOARD_CLIENT="3"          # For market data dashboard
export IB_HISTORICAL_CLIENT="4"         # For historical data
export IB_SCANNER_CLIENT="5"            # For market scanners
export IB_RISK_CLIENT="6"               # For risk management
export IB_BACKUP_CLIENT="7"             # Backup connection
export IB_TEST_CLIENT="8"               # For testing
export IB_MONITOR_CLIENT="9"            # For system monitoring
export IB_ADMIN_CLIENT="10"             # Administrative tasks
export IB_NEWSFEED_CLIENT="11"          # News feed heartbeat

# Remote TWS Connection Settings
export IB_CONNECTION_TYPE="remote_tws"
export IB_WINDOWS_COMPUTER="192.168.1.244"
export IB_CONNECTION_TIMEOUT="30"
export IB_RECONNECTION_ATTEMPTS="5"

# IB Gateway Installation Paths (Local - for reference only)
export IB_GATEWAY_DIR="$HOME/Jts/ibgateway/1039"
export IB_TWS_DIR="$HOME/Jts/tws"
export IBC_PATH="$HOME/IBC"
export IBC_INI="$HOME/IBC/config.ini"

# IB Data Subscription Settings
export IB_MARKET_DATA_TYPE="3"  # 3=delayed, 1=live (requires subscription)

# IB Server Selection (Note: This is handled by remote TWS)
export IB_PREFERRED_SERVER="zdc1.ibllc.com"  # Zurich server
export IB_FORCE_ZURICH="true"

# SPYDER TRADING SYSTEM CONFIGURATION
# ===============================================================================
# Spyder System Settings
export SPYDER_ENV="development"  # development, testing, production
export SPYDER_LOG_LEVEL="INFO"   # DEBUG, INFO, WARNING, ERROR, CRITICAL
export SPYDER_DATABASE="$SPYDER_HOME/data/spyder.db"

# Spyder Trading Parameters
export SPYDER_MAX_POSITIONS="10"
export SPYDER_MAX_DAILY_TRADES="50"
export SPYDER_RISK_LIMIT="10000"  # Maximum risk per day in USD

# Spyder Performance Settings
export SPYDER_ENABLE_CACHE="true"
export SPYDER_CACHE_TTL="300"  # Cache time-to-live in seconds
export SPYDER_THREAD_POOL_SIZE="10"

# ===============================================================================
# STANDARD UBUNTU ALIASES
# ===============================================================================
# Enable color support for ls and add handy aliases
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
alias c='clear'
alias h='history'
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'

# System monitoring shortcuts
alias df='df -h'
alias du='du -h'
alias free='free -h'
alias ps='ps aux'
alias top='htop'

# Network shortcuts
alias ports='netstat -tuln'
alias myip='curl ifconfig.me'

# Simple notification alias
alias alert='notify-send "Command completed"'

# ===============================================================================
# GIT ALIASES
# ===============================================================================
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git log --oneline'
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
# GENERAL PROJECT NAVIGATION
# ===============================================================================
alias cdprojects='cd $XDG_PROJECTS_DIR'
alias cdbackup='cd $XDG_BACKUP_DIR'
alias cddropbox='cd $XDG_DROPBOX_DIR'
alias cdtesting='cd $XDG_TESTING_DIR'

# ===============================================================================
# SPYDER PROJECT ALIASES
# ===============================================================================
alias cdspyder='cd $SPYDER_HOME'
alias spyder-logs='tail -f $SPYDER_LOGS/spyder.log'
alias spyder-test='cd $SPYDER_HOME && python -m pytest'
alias spyder-run='cd $SPYDER_HOME && python SpyderA01_Main.py'

# ===============================================================================
# DOCKER ALIASES (General, for managing containers)
# ===============================================================================
alias dps='docker ps'
alias dpsa='docker ps -a'
alias dlog='docker logs'
alias dexec='docker exec -it'
alias dstop='docker stop'
alias dstart='docker start'
alias drestart='docker restart'

# ===============================================================================
# ===============================================================================
# IB GATEWAY DOCKER ALIASES - DISABLED FOR REMOTE TWS
# ===============================================================================
# Docker aliases disabled because we're using remote TWS on Windows computer.
# The TWS application runs on 192.168.1.244, not in a local Docker container.

# ===============================================================================
# IB REMOTE TWS CONNECTION TESTING ALIASES
# ===============================================================================
# Updated aliases for testing remote TWS connection
alias ib-test='python $SPYDER_HOME/simple_ib_test.py --ip 192.168.1.244 --port 7497'
alias ib-test-comprehensive='python $SPYDER_HOME/simple_ib_test.py --ip 192.168.1.244 --port 7497 --comprehensive'
alias ib-diagnose='python $SPYDER_HOME/diagnose_tws_handshake.py --windows-ip 192.168.1.244 --port 7497'
alias ib-ports='python $SPYDER_HOME/debug_tws_connection.py --ip 192.168.1.244 --port 7497'
alias ib-status='python $SPYDER_HOME/SpyderQ_Scripts/SpyderQ22_CheckIBStatus.py'

alias ib-test='python $SPYDER_HOME/SpyderB_Broker/SpyderB23_IBKRConnectionTester.py'
alias ib-ports='netstat -tuln | grep -E ":(4001|4002|7496|7497)"'

# ===============================================================================
# USEFUL FUNCTIONS
# ===============================================================================
# Function to create a backup with timestamp
backup() {
    if [ -z "$1" ]; then
        echo "Usage: backup <file_or_directory>"
        return 1
    fi
    cp -r "$1" "$1.backup_$(date +%Y%m%d_%H%M%S)"
    echo "Backup created: $1.backup_$(date +%Y%m%d_%H%M%S)"
}

# Function to extract various archive formats
extract() {
    if [ -f "$1" ] ; then
        case $1 in
            *.tar.bz2)   tar xjf "$1"   ;;
            *.tar.gz)    tar xzf "$1"   ;;
            *.bz2)       bunzip2 "$1"   ;;
            *.rar)       unrar e "$1"   ;;
            *.gz)        gunzip "$1"    ;;
            *.tar)       tar xf "$1"    ;;
            *.tbz2)      tar xjf "$1"   ;;
            *.tgz)       tar xzf "$1"   ;;
            *.zip)       unzip "$1"     ;;
            *.Z)         uncompress "$1";;
            *.7z)        7z x "$1"      ;;
            *)     echo "'$1' cannot be extracted" ;;
        esac
    else
        echo "'$1' is not a valid file"
    fi
}

# Function to check Remote TWS connectivity
ib-check() {
    echo "🔍 Checking Remote TWS connectivity..."
    echo "----------------------------------------"
    echo "🌐 Remote TWS: 192.168.1.244:7497"
    echo ""

    # Check network connectivity
    if ping -c 1 -W 3 192.168.1.244 &>/dev/null; then
        echo "✅ Network connectivity to 192.168.1.244: OK"
    else
        echo "❌ Network connectivity to 192.168.1.244: FAILED"
        echo "   Check if Windows computer is reachable"
        return 1
    fi

    # Check TWS port
    if nc -zv 192.168.1.244 7497 2>/dev/null; then
        echo "✅ TWS port 7497 is accessible"
    else
        echo "❌ TWS port 7497 is not accessible"
        echo "   Check if TWS is running on Windows computer"
    fi

    # Check live port too
    if nc -zv 192.168.1.244 7496 2>/dev/null; then
        echo "✅ TWS port 7496 is accessible"
    else
        echo "❌ TWS port 7496 is not accessible"
    fi

    echo ""
    echo "🔧 Environment:"
    echo "   IB_REMOTE_TWS_HOST=$IB_REMOTE_TWS_HOST"
    echo "   IB_TWS_PORT_PAPER=$IB_TWS_PORT_PAPER"
    echo "   IB_TRADING_MODE=$IB_TRADING_MODE"
    echo ""
    echo "🧪 Quick Tests:"
    echo "   Run: ib-test"
    echo "   Run: ib-diagnose"
    echo "   Run: ib-status"
}

# Function to check Remote TWS connectivity
ib-check() {
    echo "🔍 Checking Remote TWS connectivity..."
    echo "----------------------------------------"
    echo "🌐 Remote TWS: 192.168.1.244:7497"
    echo ""

    # Check network connectivity
    if ping -c 1 -W 3 192.168.1.244 &>/dev/null; then
        echo "✅ Network connectivity to 192.168.1.244: OK"
    else
        echo "❌ Network connectivity to 192.168.1.244: FAILED"
        echo "   Check if Windows computer is reachable"
        return 1
    fi

    # Check TWS port
    if nc -zv 192.168.1.244 7497 2>/dev/null; then
        echo "✅ TWS port 7497 is accessible"
    else
        echo "❌ TWS port 7497 is not accessible"
        echo "   Check if TWS is running on Windows computer"
    fi

    # Check live port too
    if nc -zv 192.168.1.244 7496 2>/dev/null; then
        echo "✅ TWS port 7496 is accessible"
    else
        echo "❌ TWS port 7496 is not accessible"
    fi

    echo ""
    echo "🔧 Environment:"
    echo "   IB_REMOTE_TWS_HOST=$IB_REMOTE_TWS_HOST"
    echo "   IB_TWS_PORT_PAPER=$IB_TWS_PORT_PAPER"
    echo "   IB_TRADING_MODE=$IB_TRADING_MODE"
    echo ""
    echo "🧪 Quick Tests:"
    echo "   Run: ib-test"
    echo "   Run: ib-diagnose"
    echo "   Run: ib-status"
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
# Set default editor
export EDITOR="nano"
export VISUAL="code"

# Display IB Gateway status on login (optional - comment out if not wanted)
# echo "🚀 Spyder Trading System Environment Loaded"
# echo "   Remote TWS: 192.168.1.244:7497 (Paper)"
# echo "   Trading Mode: $IB_TRADING_MODE"
# echo "   Run 'ib-check' to verify Remote TWS status"

# ===============================================================================
# END OF .bashrc
# ===============================================================================
export PATH=$HOME/.npm-global/bin:$PATH
source /etc/profile.d/vte.sh
. "$HOME/.cargo/env"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
alias specify="~/.local/bin/spec-kit-launch"
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
export PATH=$PATH:/home/adam/.nvm/versions/node/v20.19.5/bin
(.venv) adam@Captova:~/Projects/Spyder$ 


