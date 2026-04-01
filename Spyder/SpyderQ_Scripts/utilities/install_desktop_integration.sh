#!/bin/bash
# SPYDER - Desktop Integration Installer
# Installs desktop files and creates right-click menu for connection selection

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

echo -e "${CYAN}🕷️  SPYDER - Desktop Integration Installer${NC}"
echo -e "${CYAN}==========================================${NC}"
echo

# Function to log with timestamp
log() {
    echo -e "[$(date '+%H:%M:%S')] $1"
}

# Function to check if desktop environment supports .desktop files
check_desktop_environment() {
    if [[ -n "$XDG_CURRENT_DESKTOP" ]]; then
        log "${GREEN}✅ Desktop environment detected: $XDG_CURRENT_DESKTOP${NC}"
        return 0
    elif [[ -n "$DESKTOP_SESSION" ]]; then
        log "${GREEN}✅ Desktop session detected: $DESKTOP_SESSION${NC}"
        return 0
    else
        log "${YELLOW}⚠️  Desktop environment not clearly detected${NC}"
        log "${YELLOW}   Installation will proceed but functionality may vary${NC}"
        return 0
    fi
}

# Function to create necessary directories
create_directories() {
    log "${BLUE}📁 Creating necessary directories...${NC}"

    # Create user desktop applications directory
    mkdir -p "$HOME/.local/share/applications"
    log "${GREEN}   Created: $HOME/.local/share/applications${NC}"

    # Create assets directory if it doesn't exist
    mkdir -p "$SCRIPT_DIR/assets"
    log "${GREEN}   Created: $SCRIPT_DIR/assets${NC}"

    # Create desktop directory if it doesn't exist
    mkdir -p "$SCRIPT_DIR/desktop"
    log "${GREEN}   Created: $SCRIPT_DIR/desktop${NC}"
}

# Function to create default icons if they don't exist
create_default_icons() {
    log "${BLUE}🎨 Creating default icons...${NC}"

    # Create a simple SVG icon for SPYDER if it doesn't exist
    if [[ ! -f "$SCRIPT_DIR/assets/spyder_icon.png" ]]; then
        # Try to find a suitable system icon
        if command -v convert >/dev/null 2>&1; then
            # Use ImageMagick to create a simple icon
            convert -size 64x64 xc:transparent -fill '#4fd1c7' -draw 'circle 32,32 32,16' -fill '#1a202c' -pointsize 24 -annotate +18+38 'S' "$SCRIPT_DIR/assets/spyder_icon.png" 2>/dev/null || true
        fi

        if [[ ! -f "$SCRIPT_DIR/assets/spyder_icon.png" ]]; then
            # Fallback: use system application icon
            local fallback_icon="/usr/share/icons/hicolor/64x64/apps/application-x-executable.png"
            if [[ -f "$fallback_icon" ]]; then
                cp "$fallback_icon" "$SCRIPT_DIR/assets/spyder_icon.png"
                log "${GREEN}   Using system fallback icon${NC}"
            else
                log "${YELLOW}   No icon available - using system default${NC}"
            fi
        else
            log "${GREEN}   Generated SPYDER icon${NC}"
        fi
    fi

    # Create other icons if they don't exist
    for icon in gateway_icon.png tws_icon.png test_icon.png; do
        if [[ ! -f "$SCRIPT_DIR/assets/$icon" ]] && [[ -f "$SCRIPT_DIR/assets/spyder_icon.png" ]]; then
            cp "$SCRIPT_DIR/assets/spyder_icon.png" "$SCRIPT_DIR/assets/$icon"
        fi
    done
}

# Function to create desktop entry files
create_desktop_files() {
    log "${BLUE}📄 Creating desktop entry files...${NC}"

    # Main comprehensive desktop file with all options
[ -n "$SCRIPT_DIR/spyder_dock_launcher.sh" ] || true
    cat > "$SCRIPT_DIR/desktop/spyder-trading-system-complete.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=SPYDER Trading System
Comment=Professional Algorithmic Trading Platform - Choose Connection & Mode
Exec=$SCRIPT_DIR/spyder_dock_launcher.sh
Icon=$SCRIPT_DIR/assets/spyder_icon.png
Terminal=false
Categories=Office;Finance;Development;Trading;
Keywords=trading;finance;options;stocks;spyder;live;paper;tradier;
StartupNotify=true
StartupWMClass=SpyderTradingSystem

Actions=TradierSandbox;TradierLive;ConnectionSelector;TestConnections;QuickLaunch;

[Desktop Action TradierSandbox]
Name=🏪 Tradier API - Sandbox Mode
Exec=$SCRIPT_DIR/spyder_dock_launcher.sh --mode=sandbox
Icon=$SCRIPT_DIR/assets/spyder_icon.png

[Desktop Action TradierLive]
Name=💰 Tradier API - Live Trading
Exec=$SCRIPT_DIR/spyder_dock_launcher.sh --mode=live
Icon=$SCRIPT_DIR/assets/spyder_icon.png

[Desktop Action ConnectionSelector]
Name=🎯 Connection & Mode Selector (GUI)
Exec=$SCRIPT_DIR/launch_connection_selector.py
Icon=$SCRIPT_DIR/assets/spyder_icon.png

[Desktop Action TestConnections]
Name=🔍 Test All Connections
Exec=gnome-terminal -- $SCRIPT_DIR/test_all_connections.sh --full
Icon=$SCRIPT_DIR/assets/test_icon.png

[Desktop Action QuickLaunch]
Name=⚡ Quick Launch (Best Available)
Exec=$SCRIPT_DIR/quick_launch_spyder.sh
Icon=$SCRIPT_DIR/assets/spyder_icon.png
EOF

    # Individual launcher desktop files
    cat > "$SCRIPT_DIR/desktop/spyder-tradier.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=SPYDER - Tradier API
Comment=Launch SPYDER with Tradier REST API
Exec=$SCRIPT_DIR/spyder_dock_launcher.sh
Icon=$SCRIPT_DIR/assets/spyder_icon.png
Terminal=false
Categories=Office;Finance;Development;
Keywords=trading;finance;tradier;api;spyder;
StartupNotify=true
NoDisplay=false
EOF

    cat > "$SCRIPT_DIR/desktop/spyder-test.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=SPYDER Connection Test
Comment=Test all SPYDER connection methods
Exec=$SCRIPT_DIR/test_all_connections.sh --full
Icon=$SCRIPT_DIR/assets/test_icon.png
Terminal=true
Categories=Office;Finance;Development;System;
Keywords=test;connection;diagnostic;spyder;
StartupNotify=true
NoDisplay=true
EOF

    log "${GREEN}✅ Desktop files created${NC}"
}

# Function to install desktop files
install_desktop_files() {
    log "${BLUE}💾 Installing desktop files...${NC}"

    # Copy desktop files to user applications directory
    for desktop_file in "$SCRIPT_DIR/desktop"/*.desktop; do
        if [[ -f "$desktop_file" ]]; then
            local filename=$(basename "$desktop_file")
            cp "$desktop_file" "$HOME/.local/share/applications/"
            chmod +x "$HOME/.local/share/applications/$filename"
            log "${GREEN}   Installed: $filename${NC}"
        fi
    done

    # Update desktop database if available
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        log "${GREEN}✅ Desktop database updated${NC}"
    fi
}

# Function to create dock/taskbar launcher
create_dock_launcher() {
    log "${BLUE}🔗 Creating dock launcher...${NC}"

    # Create a launcher script that can be pinned to dock
    cat > "$SCRIPT_DIR/spyder_dock_launcher.sh" << 'EOF'
#!/bin/bash
# SPYDER Dock Launcher - Shows connection selector by default

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# If connection selector exists, use it; otherwise show menu
if [[ -f "$SCRIPT_DIR/launch_connection_selector.py" ]]; then
    python3 "$SCRIPT_DIR/launch_connection_selector.py"
else
    # Fallback menu using zenity if available
    if command -v zenity >/dev/null 2>&1; then
        choice=$(zenity --list --title="SPYDER Trading System" \
            --text="Choose connection method:" \
            --column="Option" \
            "Tradier API (Default)" \
            "Test Connections" \
            --height=300 --width=400 2>/dev/null)

        case "$choice" in
            "Tradier API (Default)")
                "$SCRIPT_DIR/spyder_dock_launcher.sh"
                ;;
            "Test Connections")
                gnome-terminal -- "$SCRIPT_DIR/test_all_connections.sh" --full
                ;;
        esac
    else
        # Ultimate fallback - launch connection selector directly
        python3 "$SCRIPT_DIR/launch_connection_selector.py" || \
        gnome-terminal -- "$SCRIPT_DIR/launch_dashboard_production.py"
    fi
fi
EOF

    chmod +x "$SCRIPT_DIR/spyder_dock_launcher.sh"
    log "${GREEN}✅ Dock launcher created: spyder_dock_launcher.sh${NC}"
}

# Function to create menu entry for right-click context
create_context_menu() {
    log "${BLUE}📋 Setting up context menu integration...${NC}"

    # For file managers that support custom actions
    local context_dir="$HOME/.local/share/file-manager/actions"
    mkdir -p "$context_dir" 2>/dev/null || true

    if [[ -d "$context_dir" ]]; then
        cat > "$context_dir/spyder-trading.desktop" << EOF
[Desktop Entry]
Type=Action
Name[en]=SPYDER Trading Options
Tooltip[en]=Launch SPYDER Trading System
Icon=$SCRIPT_DIR/assets/spyder_icon.png

[X-Action-Profile profile-zero]
Exec=$SCRIPT_DIR/launch_connection_selector.py %f
MimeTypes=application/x-desktop;
Name[en]=SPYDER Connection Selector
SelectionCount==1
EOF
        log "${GREEN}   Context menu entry created${NC}"
    fi
}

# Function to verify installation
verify_installation() {
    log "${BLUE}🔍 Verifying installation...${NC}"

    local issues=0

    # Check if desktop files were created
    if [[ -f "$HOME/.local/share/applications/spyder-connection-selector.desktop" ]]; then
        log "${GREEN}✅ Main desktop file installed${NC}"
    else
        log "${RED}❌ Main desktop file missing${NC}"
        issues=$((issues + 1))
    fi

    # Check if launcher scripts are executable
    for script in launch_connection_selector.py spyder_dock_launcher.sh test_all_connections.sh; do
        if [[ -x "$SCRIPT_DIR/$script" ]]; then
            log "${GREEN}✅ $script is executable${NC}"
        else
            log "${RED}❌ $script is not executable${NC}"
            issues=$((issues + 1))
        fi
    done

    # Check if Python dependencies are available (basic check)
    if python3 -c "import PySide6" 2>/dev/null; then
        log "${GREEN}✅ PySide6 available for GUI${NC}"
    else
        log "${YELLOW}⚠️  PySide6 not available - GUI may not work${NC}"
        log "${YELLOW}   Install with: pip install PySide6${NC}"
    fi

    return $issues
}

# Function to show usage instructions
show_usage_instructions() {
    log "${CYAN}🎯 Installation Complete!${NC}"
    echo
    log "${GREEN}Your SPYDER Trading System is now integrated with your desktop!${NC}"
    echo
    log "${BLUE}📋 Available Options:${NC}"
    log "${BLUE}   1. Application Menu: Search for 'SPYDER Trading System'${NC}"
    log "${BLUE}   2. Right-click Menu: Right-click SPYDER icon → Choose connection${NC}"
    log "${BLUE}   3. Command Line:${NC}"
    log "${BLUE}      • Connection Selector: ./launch_connection_selector.py${NC}"
    log "${BLUE}      • Tradier API: ./spyder_dock_launcher.sh${NC}"
    log "${BLUE}      • Test Connections: ./test_all_connections.sh${NC}"
    echo
    log "${BLUE}🚀 Quick Start:${NC}"
    log "${BLUE}   1. Right-click the SPYDER icon in your application menu${NC}"
    log "${BLUE}   2. Choose your preferred connection method${NC}"
    log "${BLUE}   3. SPYDER will launch with the selected configuration${NC}"
    echo
    log "${BLUE}💡 Pro Tips:${NC}"
    log "${BLUE}   • Use 'Test All Connections' to verify both methods work${NC}"
    log "${BLUE}   • Pin the main launcher to your dock for quick access${NC}"
    log "${BLUE}   • The connection selector remembers your last choice${NC}"
    echo
}

# Function to create uninstaller
create_uninstaller() {
    log "${BLUE}🗑️  Creating uninstaller...${NC}"

    cat > "$SCRIPT_DIR/uninstall_desktop_integration.sh" << 'EOF'
#!/bin/bash
# SPYDER Desktop Integration Uninstaller

echo "🗑️  Removing SPYDER desktop integration..."

# Remove desktop files
rm -f "$HOME/.local/share/applications/spyder-"*.desktop
echo "   Removed desktop files"

# Remove context menu entries
rm -f "$HOME/.local/share/file-manager/actions/spyder-trading.desktop"
echo "   Removed context menu entries"

# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    echo "   Updated desktop database"
fi

echo "✅ SPYDER desktop integration removed"
echo "   Launcher scripts in project directory remain available"
EOF

    chmod +x "$SCRIPT_DIR/uninstall_desktop_integration.sh"
    log "${GREEN}✅ Uninstaller created: uninstall_desktop_integration.sh${NC}"
}

# Main installation function
main() {
    log "${CYAN}🚀 Starting SPYDER desktop integration installation...${NC}"
    echo

    # Check prerequisites
    check_desktop_environment

    # Create necessary directories and files
    create_directories
    create_default_icons
    create_desktop_files
    install_desktop_files
    create_dock_launcher
    create_context_menu
    create_uninstaller

    # Verify installation
    log "${BLUE}🔍 Verifying installation...${NC}"
    if verify_installation; then
        log "${GREEN}✅ Installation verification passed${NC}"
    else
        log "${YELLOW}⚠️  Some issues found but installation completed${NC}"
    fi

    # Show usage instructions
    show_usage_instructions
}

# Handle command line arguments
case "${1:-}" in
    --uninstall)
        log "${YELLOW}🗑️  Uninstalling desktop integration...${NC}"
        if [[ -f "$SCRIPT_DIR/uninstall_desktop_integration.sh" ]]; then
            bash "$SCRIPT_DIR/uninstall_desktop_integration.sh"
        else
            # Manual uninstall
            rm -f "$HOME/.local/share/applications/spyder-"*.desktop
            rm -f "$HOME/.local/share/file-manager/actions/spyder-trading.desktop"
            update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
            log "${GREEN}✅ Desktop integration removed${NC}"
        fi
        exit 0
        ;;
    --help|-h)
        echo "SPYDER Desktop Integration Installer"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --uninstall   Remove desktop integration"
        echo "  --help, -h    Show this help message"
        echo ""
        echo "This installer will:"
        echo "• Create desktop application entries"
        echo "• Set up right-click context menus"
        echo "• Install dock launcher"
        echo "• Create uninstaller script"
        echo ""
        echo "After installation, you can:"
        echo "• Find SPYDER in your application menu"
        echo "• Right-click SPYDER icon for connection options"
        echo "• Pin to dock for quick access"
        exit 0
        ;;
    *)
        main
        ;;
esac
