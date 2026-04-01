#!/bin/bash
# ~/.bashrc - SPYDER Dual-Mode Configuration
# Ubuntu 25.04 64-bit + GNOME 48 + Wayland
# Author: Mohamed Talib & SPYDER AI System
# Created: 2025-08-26
# Updated: 2025-10-07 - Tradier API + Databento market data
# Broker: Tradier REST API | Market Data: Databento

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


