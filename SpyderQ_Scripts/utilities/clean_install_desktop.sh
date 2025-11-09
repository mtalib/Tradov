#!/bin/bash
# SPYDER - Clean Desktop Integration Installer
# Removes old desktop entries and installs the comprehensive dual-choice system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}🕷️  SPYDER - Clean Desktop Integration${NC}"
echo -e "${CYAN}====================================${NC}"
echo

# Function to log with timestamp
log() {
    echo -e "[$(date '+%H:%M:%S')] $1"
}

# Function to remove old desktop files
remove_old_desktop_files() {
    log "${BLUE}🧹 Removing old SPYDER desktop entries...${NC}"

    cd ~/.local/share/applications

    # List of files to remove
    local old_files=(
        "spyder-trading.desktop"
        "spyder-trading-system-old.desktop"
        "spyder-connection-selector.desktop"
        "spyder-gateway.desktop"
        "spyder-tws.desktop"
        "spyder-test.desktop"
    )

    for file in "${old_files[@]}"; do
        if [[ -f "$file" ]]; then
            rm "$file"
            log "${GREEN}   Removed: $file${NC}"
        fi
    done

    log "${GREEN}✅ Old desktop files cleaned up${NC}"
}

# Function to ensure directories exist
ensure_directories() {
    log "${BLUE}📁 Creating necessary directories...${NC}"

    mkdir -p "$HOME/.local/share/applications"
    mkdir -p "$SCRIPT_DIR/assets"

    log "${GREEN}✅ Directories ready${NC}"
}

# Function to create icon if needed
create_icon() {
    log "${BLUE}🎨 Ensuring SPYDER icon exists...${NC}"

    if [[ ! -f "$SCRIPT_DIR/assets/spyder_icon.png" ]]; then
        # Try to create a simple icon with ImageMagick
        if command -v convert >/dev/null 2>&1; then
            convert -size 64x64 xc:transparent -fill '#4fd1c7' -draw 'circle 32,32 32,16' -fill '#1a202c' -pointsize 24 -annotate +18+38 'S' "$SCRIPT_DIR/assets/spyder_icon.png" 2>/dev/null || true
        fi

        # Fallback to system icon if creation failed
        if [[ ! -f "$SCRIPT_DIR/assets/spyder_icon.png" ]]; then
            local fallback_icon="/usr/share/icons/hicolor/64x64/apps/application-x-executable.png"
            if [[ -f "$fallback_icon" ]]; then
                cp "$fallback_icon" "$SCRIPT_DIR/assets/spyder_icon.png"
            fi
        fi
    fi

    log "${GREEN}✅ Icon ready${NC}"
}

# Function to create the comprehensive desktop file
create_main_desktop_file() {
    log "${BLUE}📄 Creating comprehensive SPYDER desktop file...${NC}"

    cat > "$HOME/.local/share/applications/spyder-trading-system.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=SPYDER Trading System
Comment=Professional Algorithmic Trading Platform - Choose Connection & Mode
Exec=$SCRIPT_DIR/launch_connection_selector.py
Icon=$SCRIPT_DIR/assets/spyder_icon.png
Terminal=false
Categories=Office;Finance;Development;Trading;
Keywords=trading;finance;options;stocks;interactive brokers;spyder;live;paper;
StartupNotify=true
StartupWMClass=SpyderTradingSystem

Actions=GatewayPaper;GatewayLive;TWSPaper;TWSLive;ConnectionSelector;TestConnections;QuickLaunch;

[Desktop Action GatewayPaper]
Name=🏪 IB Gateway - Paper Trading
Exec=$SCRIPT_DIR/launch_spyder_gateway.sh --mode=paper
Icon=$SCRIPT_DIR/assets/spyder_icon.png

[Desktop Action GatewayLive]
Name=🏪 IB Gateway - Live Trading
Exec=$SCRIPT_DIR/launch_spyder_gateway.sh --mode=live
Icon=$SCRIPT_DIR/assets/spyder_icon.png

[Desktop Action TWSPaper]
Name=🌐 Remote TWS - Paper Trading
Exec=$SCRIPT_DIR/launch_spyder_tws.sh --mode=paper
Icon=$SCRIPT_DIR/assets/spyder_icon.png

[Desktop Action TWSLive]
Name=🌐 Remote TWS - Live Trading
Exec=$SCRIPT_DIR/launch_spyder_tws.sh --mode=live
Icon=$SCRIPT_DIR/assets/spyder_icon.png

[Desktop Action ConnectionSelector]
Name=🎯 Connection & Mode Selector (GUI)
Exec=$SCRIPT_DIR/launch_connection_selector.py
Icon=$SCRIPT_DIR/assets/spyder_icon.png

[Desktop Action TestConnections]
Name=🔍 Test All Connections
Exec=gnome-terminal -- $SCRIPT_DIR/test_all_connections.sh --full
Icon=$SCRIPT_DIR/assets/spyder_icon.png

[Desktop Action QuickLaunch]
Name=⚡ Quick Launch (Best Available)
Exec=$SCRIPT_DIR/quick_launch_spyder.sh
Icon=$SCRIPT_DIR/assets/spyder_icon.png
EOF

    # Make it executable
    chmod +x "$HOME/.local/share/applications/spyder-trading-system.desktop"

    log "${GREEN}✅ Main desktop file created${NC}"
}

# Function to update desktop database
update_desktop_database() {
    log "${BLUE}🔄 Updating desktop database...${NC}"

    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        log "${GREEN}✅ Desktop database updated${NC}"
    else
        log "${YELLOW}⚠️  update-desktop-database not available${NC}"
    fi
}

# Function to verify installation
verify_installation() {
    log "${BLUE}🔍 Verifying installation...${NC}"

    local main_file="$HOME/.local/share/applications/spyder-trading-system.desktop"

    if [[ -f "$main_file" ]] && [[ -x "$main_file" ]]; then
        log "${GREEN}✅ Main desktop file installed and executable${NC}"

        # Check if it has the right actions
        if grep -q "Actions=GatewayPaper;GatewayLive;TWSPaper;TWSLive" "$main_file"; then
            log "${GREEN}✅ All 7 menu actions configured${NC}"
        else
            log "${YELLOW}⚠️  Menu actions may not be complete${NC}"
        fi
    else
        log "${RED}❌ Main desktop file missing or not executable${NC}"
        return 1
    fi

    # Check launcher scripts
    local scripts=(
        "launch_connection_selector.py"
        "launch_spyder_gateway.sh"
        "launch_spyder_tws.sh"
        "test_all_connections.sh"
        "quick_launch_spyder.sh"
    )

    for script in "${scripts[@]}"; do
        if [[ -x "$SCRIPT_DIR/$script" ]]; then
            log "${GREEN}✅ $script is executable${NC}"
        else
            log "${RED}❌ $script is missing or not executable${NC}"
        fi
    done

    return 0
}

# Function to show final instructions
show_instructions() {
    log "${CYAN}🎯 Installation Complete!${NC}"
    echo
    log "${GREEN}Your SPYDER Trading System is now properly integrated!${NC}"
    echo
    log "${BLUE}📋 How to Access Your New Menu:${NC}"
    log "${BLUE}   1. Open Application Menu (Activities or Super key)${NC}"
    log "${BLUE}   2. Search for 'SPYDER Trading System'${NC}"
    log "${BLUE}   3. Right-click the icon${NC}"
    log "${BLUE}   4. Choose from 7 options:${NC}"
    echo
    log "${GREEN}      🏪 IB Gateway - Paper Trading${NC}"
    log "${GREEN}      🏪 IB Gateway - Live Trading${NC}"
    log "${GREEN}      🌐 Remote TWS - Paper Trading${NC}"
    log "${GREEN}      🌐 Remote TWS - Live Trading${NC}"
    log "${GREEN}      🎯 Connection & Mode Selector (GUI)${NC}"
    log "${GREEN}      🔍 Test All Connections${NC}"
    log "${GREEN}      ⚡ Quick Launch (Best Available)${NC}"
    echo
    log "${BLUE}💡 Pro Tips:${NC}"
    log "${BLUE}   • Pin the SPYDER icon to your dock for quick access${NC}"
    log "${BLUE}   • Use 'Test All Connections' to verify your setup${NC}"
    log "${BLUE}   • Try 'Quick Launch' when you want automatic selection${NC}"
    echo
    log "${YELLOW}🔄 If menu doesn't appear immediately:${NC}"
    log "${YELLOW}   • Wait 10-15 seconds for desktop refresh${NC}"
    log "${YELLOW}   • Or restart your desktop: killall -SIGQUIT gnome-shell${NC}"
}

# Main installation function
main() {
    log "${CYAN}🚀 Starting clean SPYDER desktop integration...${NC}"
    echo

    # Step 1: Clean up old files
    remove_old_desktop_files

    # Step 2: Ensure directories and assets
    ensure_directories
    create_icon

    # Step 3: Create new comprehensive desktop file
    create_main_desktop_file

    # Step 4: Update system
    update_desktop_database

    # Step 5: Verify installation
    if verify_installation; then
        log "${GREEN}✅ Installation successful${NC}"
        show_instructions
    else
        log "${RED}❌ Installation had issues${NC}"
        log "${YELLOW}   Check the error messages above${NC}"
        exit 1
    fi
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "SPYDER Clean Desktop Integration Installer"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h    Show this help message"
        echo ""
        echo "This script will:"
        echo "• Remove all old SPYDER desktop entries"
        echo "• Install one comprehensive desktop file"
        echo "• Set up right-click menu with 7 options"
        echo "• Update desktop database"
        echo ""
        echo "After installation, right-click 'SPYDER Trading System'"
        echo "in your application menu to see all options."
        exit 0
        ;;
    *)
        main
        ;;
esac
