#!/bin/bash
# ===============================================================================
# SPYDER - SPY Icon Quick Fix Script
# Purpose: Fixes your non-functional SPY icon in Ubuntu dock
# Author: Mohamed Talib
# Date: 2025-01-11
# ===============================================================================

set -e

# Configuration
SPYDER_HOME="/home/adam/Projects/Spyder"
SCRIPTS_DIR="$SPYDER_HOME/SpyderQ_Scripts"
ICON_FILE="$SPYDER_HOME/assets/spyder-icon.png"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      SPYDER SPY ICON FIX UTILITY          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Check if icon file exists
if [ ! -f "$ICON_FILE" ]; then
    echo -e "${YELLOW}[!]${NC} Icon not found. Creating default icon..."
    mkdir -p "$SPYDER_HOME/assets"
    
    # Create a simple SPY icon using ImageMagick or as a placeholder
    if command -v convert &> /dev/null; then
        convert -size 256x256 xc:'#1a1a2e' \
            -fill '#0f3460' -draw "circle 128,128 128,20" \
            -fill white -gravity center -pointsize 72 -font "DejaVu-Sans-Bold" \
            -annotate +0+0 'SPY' \
            "$ICON_FILE"
        echo -e "${GREEN}[✓]${NC} Created SPY icon"
    else
        # Create a placeholder if ImageMagick not available
        echo "SPY" > "$SPYDER_HOME/assets/spy-icon.txt"
        echo -e "${YELLOW}[!]${NC} Please add a proper PNG icon to: $ICON_FILE"
    fi
fi

# Step 2: Create the desktop launcher file
echo -e "${YELLOW}[2/5]${NC} Creating desktop launcher..."
cat > "$SPYDER_HOME/spyder-trading.desktop" << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Spyder Trading System
Comment=Automated SPY Options Trading Platform
GenericName=Options Trading System

# Main execution command
Exec=/home/adam/Projects/Spyder/SpyderQ_Scripts/SpyderQ10_StartAll.sh
Terminal=false
StartupNotify=true

# Icon configuration
Icon=/home/adam/Projects/Spyder/assets/spyder-icon.png

# Categories
Categories=Finance;Trading;Application;

# Keywords for search
Keywords=trading;options;spy;spyder;stocks;market;

# Right-click actions
Actions=Stop;Status;Monitor;Config;Logs;

[Desktop Action Stop]
Name=Stop Trading System
Exec=/home/adam/Projects/Spyder/SpyderQ_Scripts/SpyderQ11_StopAll.sh
Icon=process-stop

[Desktop Action Status]
Name=Check System Status
Exec=gnome-terminal -- /home/adam/Projects/Spyder/SpyderQ_Scripts/SpyderQ20_Status.sh
Icon=dialog-information

[Desktop Action Monitor]
Name=Open System Monitor
Exec=gnome-terminal -- /home/adam/Projects/Spyder/SpyderQ_Scripts/SpyderQ21_Monitor.sh
Icon=utilities-system-monitor

[Desktop Action Config]
Name=Edit Configuration
Exec=gedit /home/adam/Projects/Spyder/.env
Icon=preferences-system

[Desktop Action Logs]
Name=View Logs
Exec=gnome-terminal -- tail -f /home/adam/Projects/Spyder/logs/system/main.log
Icon=text-x-log

StartupWMClass=spyder-trading
X-GNOME-Autostart-enabled=false
EOF

echo -e "${GREEN}[✓]${NC} Desktop launcher created"

# Step 3: Install to applications
echo -e "${YELLOW}[3/5]${NC} Installing launcher..."
mkdir -p ~/.local/share/applications
cp "$SPYDER_HOME/spyder-trading.desktop" ~/.local/share/applications/
chmod +x ~/.local/share/applications/spyder-trading.desktop

# Step 4: Update desktop database
echo -e "${YELLOW}[4/5]${NC} Updating desktop database..."
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true

# Step 5: Fix the dock icon
echo -e "${YELLOW}[5/5]${NC} Fixing dock icon..."

# Get current favorites from GNOME Shell
if command -v gsettings &> /dev/null; then
    CURRENT_FAVS=$(gsettings get org.gnome.shell favorite-apps 2>/dev/null || echo "[]")
    
    # Remove any old spyder entries
    CLEANED_FAVS=$(echo "$CURRENT_FAVS" | sed "s/'spyder[^']*'//g" | sed 's/, ,/,/g' | sed 's/\[,/\[/g' | sed 's/,\]/\]/g')
    
    # Add the new launcher
    if [[ ! "$CLEANED_FAVS" == *"spyder-trading.desktop"* ]]; then
        NEW_FAVS="${CLEANED_FAVS%]}, 'spyder-trading.desktop']"
        NEW_FAVS=$(echo "$NEW_FAVS" | sed 's/\[, /\[/g')  # Clean up if it's the first item
        gsettings set org.gnome.shell favorite-apps "$NEW_FAVS" 2>/dev/null && {
            echo -e "${GREEN}[✓]${NC} Added to dock"
        } || {
            echo -e "${YELLOW}[!]${NC} Could not add to dock automatically"
        }
    fi
fi

# Make scripts executable
chmod +x "$SCRIPTS_DIR/SpyderQ10_StartAll.sh" 2>/dev/null || true
chmod +x "$SCRIPTS_DIR/SpyderQ11_StopAll.sh" 2>/dev/null || true
chmod +x "$SCRIPTS_DIR/SpyderQ20_Status.sh" 2>/dev/null || true
chmod +x "$SCRIPTS_DIR/SpyderQ21_Monitor.sh" 2>/dev/null || true

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         SPY ICON FIXED! 🚀                ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo "Your SPY icon should now work! Try:"
echo "  1. Look for 'Spyder Trading System' in your dock"
echo "  2. Search for 'Spyder' in applications (Super key)"
echo "  3. Right-click the icon for quick actions"
echo ""
echo -e "${YELLOW}If the icon doesn't appear immediately:${NC}"
echo "  • Press Alt+F2, type 'r', press Enter (restart GNOME)"
echo "  • Or log out and log back in"
echo ""
echo "To test launch directly:"
echo "  $SCRIPTS_DIR/SpyderQ10_StartAll.sh"
