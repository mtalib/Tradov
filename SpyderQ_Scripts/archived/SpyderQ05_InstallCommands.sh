#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Script: SpyderQ05_InstallCommands.sh
# Group: Q (Scripts/Installation)
# Purpose: Install Spyder commands system-wide for easy access
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 12:00:00
#
# Description:
#     Installs the 'spyder' command system-wide by creating symbolic links
#     and aliases. Also sets up systemd services and bash completions for
#     enhanced user experience.
# ===============================================================================

set -e  # Exit on error

# Configuration
SPYDER_HOME="/home/adam/Projects/Spyder"
SCRIPTS_DIR="$SPYDER_HOME/SpyderQ_Scripts"
INSTALL_DIR="/usr/local/bin"
SYSTEMD_DIR="/etc/systemd/system"
BASH_COMPLETION_DIR="/etc/bash_completion.d"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  SPYDER COMMAND INSTALLATION${NC}"
    echo -e "${BLUE}================================================${NC}"
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
    echo -e "${BLUE}[i]${NC} $1"
}

# ===============================================================================
# INSTALLATION FUNCTIONS
# ===============================================================================

install_main_command() {
    print_info "Installing main 'spyder' command..."
    
    # Create wrapper script
    cat > /tmp/spyder << 'EOF'
#!/bin/bash
# Spyder command wrapper
exec "$HOME/Spyder/scripts/SpyderQ16_SpyderControl.sh" "$@"
EOF
    
    # Make executable
    chmod +x /tmp/spyder
    
    # Install to system
    if sudo mv /tmp/spyder "$INSTALL_DIR/spyder"; then
        print_success "Main command installed to $INSTALL_DIR/spyder"
    else
        print_error "Failed to install main command"
        return 1
    fi
}

install_bash_completion() {
    print_info "Installing bash completion..."
    
    # Create completion script
    cat > /tmp/spyder-completion.bash << 'EOF'
# Bash completion for spyder command
_spyder_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # Main commands
    opts="start stop restart status monitor logs check backup clean help"
    
    # Component-specific options
    case "${prev}" in
        logs)
            local components="master watchdog metrics dashboard agents all"
            COMPREPLY=( $(compgen -W "${components}" -- ${cur}) )
            return 0
            ;;
        start)
            local options="--with-dashboard"
            COMPREPLY=( $(compgen -W "${options}" -- ${cur}) )
            return 0
            ;;
        *)
            ;;
    esac
    
    COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
    return 0
}

complete -F _spyder_completion spyder
EOF
    
    # Install completion
    if sudo cp /tmp/spyder-completion.bash "$BASH_COMPLETION_DIR/spyder"; then
        print_success "Bash completion installed"
        print_info "Run 'source /etc/bash_completion' to activate"
    else
        print_warning "Could not install bash completion (non-critical)"
    fi
}

install_systemd_services() {
    print_info "Installing systemd services..."
    
    # Copy service files
    local services=(
        "SpyderQ70_Watchdog.service"
        "SpyderQ71_Metrics.service"
        "SpyderQ74_SpyderMain.service"
    )
    
    for service in "${services[@]}"; do
        if [ -f "$SPYDER_HOME/services/$service" ]; then
            # Update user in service file
            sed "s/\$USER/$USER/g" "$SPYDER_HOME/services/$service" > "/tmp/$service"
            
            if sudo cp "/tmp/$service" "$SYSTEMD_DIR/$service"; then
                print_success "Installed $service"
            else
                print_error "Failed to install $service"
            fi
        else
            print_warning "$service not found"
        fi
    done
    
    # Reload systemd
    sudo systemctl daemon-reload
    print_success "Systemd configuration reloaded"
}

install_aliases() {
    print_info "Installing shell aliases..."
    
    # Check if aliases already exist
    if grep -q "# SPYDER Aliases" ~/.bashrc; then
        print_warning "Aliases already exist in ~/.bashrc"
    else
        # Add aliases to bashrc
        cat >> ~/.bashrc << 'EOF'

# SPYDER Aliases
alias spyder-start='spyder start'
alias spyder-stop='spyder stop'
alias spyder-status='spyder status'
alias spyder-monitor='spyder monitor'
alias spyder-logs='spyder logs'
alias spyder-dash='spyder start --with-dashboard'
alias spyder-env='source ~/Spyder/spyder_venv/bin/activate && cd ~/Spyder'

# Quick access to Spyder directories
alias cdspyder='cd ~/Spyder'
alias cdlogs='cd ~/Spyder/logs'
alias cddata='cd ~/Spyder/data'

# Service management
alias spyder-enable='sudo systemctl enable SpyderQ74_SpyderMain.service'
alias spyder-disable='sudo systemctl disable SpyderQ74_SpyderMain.service'
alias spyder-service-status='sudo systemctl status SpyderQ74_SpyderMain.service'
EOF
        
        print_success "Aliases added to ~/.bashrc"
        print_info "Run 'source ~/.bashrc' to activate"
    fi
}

create_desktop_shortcut() {
    print_info "Creating desktop shortcut..."
    
    # Create desktop entry
    cat > ~/.local/share/applications/spyder-trading.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Spyder Trading System
Comment=Autonomous Options Trading System
Icon=$SPYDER_HOME/assets/spyder-icon.png
Exec=spyder start --with-dashboard
Terminal=true
Categories=Finance;Application;
Keywords=trading;options;spy;finance;
EOF
    
    # Make executable
    chmod +x ~/.local/share/applications/spyder-trading.desktop
    
    print_success "Desktop shortcut created"
    print_info "Should appear in your applications menu"
}

# ===============================================================================
# UNINSTALL FUNCTION
# ===============================================================================

uninstall() {
    print_header
    print_warning "This will remove all Spyder system-wide installations"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Uninstall cancelled"
        return 0
    fi
    
    # Remove main command
    sudo rm -f "$INSTALL_DIR/spyder"
    print_success "Removed spyder command"
    
    # Remove bash completion
    sudo rm -f "$BASH_COMPLETION_DIR/spyder"
    print_success "Removed bash completion"
    
    # Remove systemd services
    sudo systemctl stop SpyderQ74_SpyderMain.service 2>/dev/null || true
    sudo systemctl disable SpyderQ74_SpyderMain.service 2>/dev/null || true
    sudo rm -f "$SYSTEMD_DIR"/SpyderQ*.service
    sudo systemctl daemon-reload
    print_success "Removed systemd services"
    
    # Remove desktop shortcut
    rm -f ~/.local/share/applications/spyder-trading.desktop
    print_success "Removed desktop shortcut"
    
    print_success "Uninstall complete"
    print_info "Aliases in ~/.bashrc were not removed (do manually if desired)"
}

# ===============================================================================
# MAIN INSTALLATION
# ===============================================================================

main() {
    print_header
    echo ""
    
    # Check if running uninstall
    if [ "$1" == "--uninstall" ]; then
        uninstall
        exit 0
    fi
    
    # Check prerequisites
    if [ ! -d "$SPYDER_HOME" ]; then
        print_error "Spyder not found at $SPYDER_HOME"
        print_info "Run SpyderQ01_Setup.sh first"
        exit 1
    fi
    
    if [ ! -f "$SCRIPTS_DIR/SpyderQ16_SpyderControl.sh" ]; then
        print_error "Control script not found"
        print_info "Ensure all Q-scripts are properly installed"
        exit 1
    fi
    
    # Run installation steps
    echo "This will install Spyder commands system-wide"
    echo "You may be prompted for sudo password"
    echo ""
    
    install_main_command
    install_bash_completion
    install_systemd_services
    install_aliases
    create_desktop_shortcut
    
    echo ""
    print_success "Installation complete!"
    echo ""
    echo "Available commands:"
    echo "  spyder start    - Start trading system"
    echo "  spyder stop     - Stop trading system"
    echo "  spyder status   - Check system status"
    echo "  spyder monitor  - Live monitoring"
    echo "  spyder help     - Show all commands"
    echo ""
    echo "To enable auto-start on boot:"
    echo "  sudo systemctl enable SpyderQ74_SpyderMain.service"
    echo ""
    echo "To activate aliases and completion:"
    echo "  source ~/.bashrc"
    echo "  source /etc/bash_completion"
    echo ""
    print_info "To uninstall: $0 --uninstall"
}

# Run main
main "$@"
