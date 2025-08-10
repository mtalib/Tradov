#!/bin/bash
# ===============================================================================
# SPYDER - SPY Dock Icon Definitive Fix
# This will fix your non-functional dock icon in Ubuntu
# Author: Mohamed Talib
# Date: 2025-01-11
# ===============================================================================

set -e

# Configuration
SPYDER_HOME="/home/adam/Projects/Spyder"
ICON_FILE="$SPYDER_HOME/assets/spyder-icon.png"  # Your actual icon location
DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"
SCRIPTS_DIR="$SPYDER_HOME/SpyderQ_Scripts"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    SPY DOCK ICON DEFINITIVE FIX           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# ===============================================================================
# STEP 1: Verify icon file exists
# ===============================================================================

echo -e "${CYAN}[Step 1/7] Verifying icon file...${NC}"

if [ -f "$ICON_FILE" ]; then
    echo -e "${GREEN}[✓]${NC} Icon found: spyder-icon.png"
    ICON_SIZE=$(du -h "$ICON_FILE" | cut -f1)
    echo -e "    Size: $ICON_SIZE"
else
    echo -e "${RED}[✗]${NC} Icon not found at: $ICON_FILE"
    echo -e "${YELLOW}[!]${NC} Looking for icon in other locations..."
    
    # Search for the icon
    POSSIBLE_ICONS=(
        "$SPYDER_HOME/assets/spyder_icon.png"
        "$SPYDER_HOME/assets/spy-icon.png"
        "$SPYDER_HOME/assets/spy_icon.png"
        "$SPYDER_HOME/spyder-icon.png"
        "$SPYDER_HOME/icon.png"
    )
    
    for icon in "${POSSIBLE_ICONS[@]}"; do
        if [ -f "$icon" ]; then
            echo -e "${GREEN}[✓]${NC} Found icon at: $icon"
            ICON_FILE="$icon"
            break
        fi
    done
    
    if [ ! -f "$ICON_FILE" ]; then
        echo -e "${YELLOW}[!]${NC} No icon found, creating default..."
        mkdir -p "$SPYDER_HOME/assets"
        
        # Create a simple SPY icon using ImageMagick if available
        if command -v convert &> /dev/null; then
            convert -size 256x256 xc:'#1e3a5f' \
                -fill '#ffffff' -gravity center \
                -pointsize 96 -font "DejaVu-Sans-Bold" \
                -annotate +0+0 'SPY' \
                -bordercolor '#4a90e2' -border 5 \
                "$SPYDER_HOME/assets/spyder-icon.png"
            ICON_FILE="$SPYDER_HOME/assets/spyder-icon.png"
            echo -e "${GREEN}[✓]${NC} Created default icon"
        fi
    fi
fi

# ===============================================================================
# STEP 2: Create launcher wrapper script
# ===============================================================================

echo -e "${CYAN}[Step 2/7] Creating launcher wrapper...${NC}"

# Create a wrapper script that handles all the startup logic
WRAPPER_SCRIPT="$SPYDER_HOME/launch_spyder.sh"

cat > "$WRAPPER_SCRIPT" << 'EOF'
#!/bin/bash
# SPYDER Launcher Wrapper - Ensures proper startup

# Set environment
export SPYDER_HOME="/home/adam/Projects/Spyder"
export PATH="$SPYDER_HOME/SpyderQ_Scripts:$PATH"

# Log startup attempt
echo "[$(date)] Spyder launch attempted" >> "$SPYDER_HOME/logs/launcher.log"

# Change to Spyder directory
cd "$SPYDER_HOME" || exit 1

# Check if we have a terminal
if [ -t 0 ]; then
    # Running in terminal
    echo "Starting Spyder Trading System..."
    exec "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh"
else
    # Running from GUI (dock icon)
    # Open in a new terminal
    if command -v gnome-terminal &> /dev/null; then
        gnome-terminal --working-directory="$SPYDER_HOME" \
            --title="Spyder Trading System" \
            -- bash -c "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh; echo 'Press Enter to close...'; read"
    elif command -v xterm &> /dev/null; then
        xterm -T "Spyder Trading System" -e "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh"
    else
        # Fallback - try to run directly
        "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh" &
    fi
fi
EOF

chmod +x "$WRAPPER_SCRIPT"
echo -e "${GREEN}[✓]${NC} Wrapper script created"

# ===============================================================================
# STEP 3: Remove old desktop files
# ===============================================================================

echo -e "${CYAN}[Step 3/7] Cleaning old launchers...${NC}"

# Remove any existing desktop files
rm -f ~/.local/share/applications/spyder*.desktop 2>/dev/null || true
rm -f ~/Desktop/spyder*.desktop 2>/dev/null || true

echo -e "${GREEN}[✓]${NC} Old launchers removed"

# ===============================================================================
# STEP 4: Create new desktop launcher
# ===============================================================================

echo -e "${CYAN}[Step 4/7] Creating new desktop launcher...${NC}"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Spyder Trading System
Comment=Automated SPY Options Trading Platform
GenericName=SPY Trading

# Use the wrapper script for launching
Exec=$WRAPPER_SCRIPT

# Set to true to open in terminal
Terminal=false

# Icon path - using your actual icon location
Icon=$ICON_FILE

# Working directory
Path=$SPYDER_HOME

# Categories for menu
Categories=Finance;Trading;Application;

# Keywords for search
Keywords=trading;options;spy;spyder;stocks;market;finance;

# Startup notification
StartupNotify=true
StartupWMClass=spyder-trading

# Actions for right-click menu
Actions=Stop;Status;Monitor;Terminal;Config;Logs;

# Stop Trading Action
[Desktop Action Stop]
Name=Stop Trading System
Exec=bash -c "cd $SPYDER_HOME && ./SpyderQ_Scripts/SpyderQ11_StopAll.sh"
Icon=process-stop

# Status Check Action
[Desktop Action Status]
Name=Check System Status  
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- bash -c "./SpyderQ_Scripts/SpyderQ20_Status.sh; echo 'Press Enter to close...'; read"
Icon=dialog-information

# Monitor Action
[Desktop Action Monitor]
Name=Open System Monitor
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- ./SpyderQ_Scripts/SpyderQ21_Monitor.sh
Icon=utilities-system-monitor

# Terminal Action
[Desktop Action Terminal]
Name=Open Spyder Terminal
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- bash
Icon=utilities-terminal

# Configuration Action
[Desktop Action Config]
Name=Edit Configuration
Exec=gedit $SPYDER_HOME/.env
Icon=preferences-system

# Logs Action
[Desktop Action Logs]
Name=View System Logs
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- bash -c "tail -f logs/system/main.log"
Icon=text-x-log
EOF

echo -e "${GREEN}[✓]${NC} Desktop launcher created"

# ===============================================================================
# STEP 5: Update desktop database and set permissions
# ===============================================================================

echo -e "${CYAN}[Step 5/7] Setting permissions and updating database...${NC}"

# Set executable permissions
chmod +x "$DESKTOP_FILE"

# Trust the desktop file (Ubuntu specific)
gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true

# Update desktop database
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true

echo -e "${GREEN}[✓]${NC} Permissions set and database updated"

# ===============================================================================
# STEP 6: Fix dock icon
# ===============================================================================

echo -e "${CYAN}[Step 6/7] Fixing dock icon...${NC}"

# Get current favorites
CURRENT_FAVS=$(gsettings get org.gnome.shell favorite-apps 2>/dev/null || echo "[]")

# Remove any old Spyder entries from favorites
CLEANED_FAVS=$(echo "$CURRENT_FAVS" | sed "s/'spyder[^']*'//g" | sed 's/, ,/,/g' | sed 's/\[, /\[/g' | sed 's/, \]/\]/g' | sed 's/,,/,/g')

# Add our new launcher if not present
if [[ ! "$CLEANED_FAVS" == *"spyder-trading.desktop"* ]]; then
    # Add to end of favorites
    if [ "$CLEANED_FAVS" == "[]" ]; then
        NEW_FAVS="['spyder-trading.desktop']"
    else
        NEW_FAVS="${CLEANED_FAVS%]}, 'spyder-trading.desktop']"
    fi
    
    # Set the new favorites
    gsettings set org.gnome.shell favorite-apps "$NEW_FAVS" 2>/dev/null && {
        echo -e "${GREEN}[✓]${NC} Added to dock favorites"
    } || {
        echo -e "${YELLOW}[!]${NC} Could not update dock automatically"
    }
else
    echo -e "${GREEN}[✓]${NC} Already in dock favorites"
fi

# ===============================================================================
# STEP 7: Create desktop shortcut
# ===============================================================================

echo -e "${CYAN}[Step 7/7] Creating desktop shortcut...${NC}"

DESKTOP_DIR="$HOME/Desktop"
if [ -d "$DESKTOP_DIR" ]; then
    cp "$DESKTOP_FILE" "$DESKTOP_DIR/spyder-trading.desktop"
    chmod +x "$DESKTOP_DIR/spyder-trading.desktop"
    
    # Trust the desktop file
    gio set "$DESKTOP_DIR/spyder-trading.desktop" metadata::trusted true 2>/dev/null || true
    
    echo -e "${GREEN}[✓]${NC} Desktop shortcut created"
else
    echo -e "${YELLOW}[!]${NC} Desktop folder not found"
fi

# ===============================================================================
# Fix script permissions
# ===============================================================================

echo -e "${CYAN}Ensuring all scripts are executable...${NC}"

chmod +x "$SCRIPTS_DIR/SpyderQ10_StartAll.sh" 2>/dev/null || true
chmod +x "$SCRIPTS_DIR/SpyderQ11_StopAll.sh" 2>/dev/null || true
chmod +x "$SCRIPTS_DIR/SpyderQ20_Status.sh" 2>/dev/null || true
chmod +x "$SCRIPTS_DIR/SpyderQ21_Monitor.sh" 2>/dev/null || true

echo -e "${GREEN}[✓]${NC} Script permissions fixed"

# ===============================================================================
# Refresh GNOME Shell
# ===============================================================================

echo ""
echo -e "${CYAN}Refreshing desktop environment...${NC}"

# Try different methods to refresh
if command -v gnome-shell &> /dev/null; then
    # For GNOME - restart the shell
    echo -e "${YELLOW}[!]${NC} Press Alt+F2, type 'r', and press Enter to refresh GNOME"
    
    # Alternative method
    killall -HUP gnome-shell 2>/dev/null || true
fi

# Refresh icons
gtk-update-icon-cache -f ~/.local/share/icons/ 2>/dev/null || true

# ===============================================================================
# VERIFICATION
# ===============================================================================

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         SPY ICON FIX COMPLETE!            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""

# Test if the launcher works
if [ -f "$WRAPPER_SCRIPT" ] && [ -x "$WRAPPER_SCRIPT" ]; then
    echo -e "${GREEN}✓${NC} Launcher wrapper is executable"
fi

if [ -f "$DESKTOP_FILE" ]; then
    echo -e "${GREEN}✓${NC} Desktop file created successfully"
fi

# Show the icon location
echo ""
echo -e "${CYAN}Icon Details:${NC}"
echo "  Location: $ICON_FILE"
if [ -f "$ICON_FILE" ]; then
    echo "  Status: File exists"
    file "$ICON_FILE" | grep -o "PNG image data.*"
fi

echo ""
echo -e "${CYAN}Your SPY icon should now work!${NC}"
echo ""
echo "Try these methods to launch:"
echo "  1. ${GREEN}Click the SPY icon in your dock${NC}"
echo "  2. ${GREEN}Search for 'Spyder' in Activities${NC}"
echo "  3. ${GREEN}Double-click desktop shortcut${NC}"
echo "  4. ${GREEN}Run: $WRAPPER_SCRIPT${NC}"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "  • If the icon still doesn't work in dock:"
echo "    1. Right-click the dock icon and select 'Remove from Favorites'"
echo "    2. Open Activities (Super key)"
echo "    3. Search for 'Spyder'"
echo "    4. Right-click the icon and select 'Add to Favorites'"
echo ""
echo "  • To refresh GNOME immediately:"
echo "    Press ${GREEN}Alt+F2${NC}, type ${GREEN}r${NC}, press ${GREEN}Enter${NC}"
echo ""
echo "  • Alternative: Log out and log back in"
echo ""

# Create a test launcher command
echo -e "${CYAN}Testing the launcher...${NC}"
echo "To test manually, run:"
echo "  ${GREEN}$WRAPPER_SCRIPT${NC}"
