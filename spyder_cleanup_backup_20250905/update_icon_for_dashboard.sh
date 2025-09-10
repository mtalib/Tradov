#!/bin/bash
# ===============================================================================
# Update SPY Icon to Launch Dashboard on Single Click
# ===============================================================================

SPYDER_HOME="/home/adam/Projects/Spyder"
DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"
DASHBOARD_LAUNCHER="$SPYDER_HOME/launch_dashboard.sh"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}  Updating SPY Icon for Dashboard Launch${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""

# Step 1: Make the dashboard launcher executable
echo -e "${YELLOW}[1/3]${NC} Setting up dashboard launcher..."
chmod +x "$DASHBOARD_LAUNCHER"
echo -e "${GREEN}[✓]${NC} Dashboard launcher ready"

# Step 2: Update the desktop file
echo -e "${YELLOW}[2/3]${NC} Updating desktop launcher..."

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Spyder Trading Dashboard
Comment=SPY Options Trading System with GUI Dashboard
GenericName=SPY Trading

# MAIN ACTION - Single Click launches Dashboard
Exec=$DASHBOARD_LAUNCHER

# No terminal for main GUI launch
Terminal=false

# Icon
Icon=$SPYDER_HOME/assets/spyder-icon.png

# Working directory
Path=$SPYDER_HOME

# Categories
Categories=Finance;Trading;Application;

# Keywords
Keywords=trading;options;spy;spyder;stocks;market;dashboard;

# Startup
StartupNotify=true
StartupWMClass=spyder-trading

# RIGHT-CLICK MENU ACTIONS (these stay the same)
Actions=Monitor;Stop;Status;Terminal;Config;Logs;Restart;

# System Monitor
[Desktop Action Monitor]
Name=Open System Monitor
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- ./SpyderQ_Scripts/SpyderQ21_Monitor.sh
Icon=utilities-system-monitor

# Stop System
[Desktop Action Stop]
Name=Stop Trading System
Exec=bash -c "cd $SPYDER_HOME && ./SpyderQ_Scripts/SpyderQ11_StopAll.sh"
Icon=process-stop

# Check Status
[Desktop Action Status]
Name=Check System Status
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- bash -c "./SpyderQ_Scripts/SpyderQ20_Status.sh; echo ''; echo 'Press Enter to close...'; read"
Icon=dialog-information

# Open Terminal
[Desktop Action Terminal]
Name=Open Spyder Terminal
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- bash
Icon=utilities-terminal

# Edit Config
[Desktop Action Config]
Name=Edit Configuration
Exec=gedit $SPYDER_HOME/.env
Icon=preferences-system

# View Logs
[Desktop Action Logs]
Name=View System Logs
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- bash -c "tail -f logs/system/main.log"
Icon=text-x-log

# Restart System
[Desktop Action Restart]
Name=Restart Trading System
Exec=bash -c "cd $SPYDER_HOME && ./SpyderQ_Scripts/SpyderQ11_StopAll.sh && sleep 2 && $DASHBOARD_LAUNCHER"
Icon=view-refresh
EOF

chmod +x "$DESKTOP_FILE"
echo -e "${GREEN}[✓]${NC} Desktop file updated"

# Step 3: Update desktop database
echo -e "${YELLOW}[3/3]${NC} Refreshing desktop database..."
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
echo -e "${GREEN}[✓]${NC} Database updated"

# Create a simple test to verify PyQt6
echo ""
echo -e "${BLUE}Checking PyQt6 installation...${NC}"
python3 -c "from PyQt6.QtWidgets import QApplication; print('✓ PyQt6 is installed')" 2>/dev/null || {
    echo -e "${YELLOW}[!]${NC} PyQt6 not found. Installing..."
    pip install PyQt6
}

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}       ICON UPDATE COMPLETE!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "Your SPY icon will now:"
echo "  • ${GREEN}Single Click${NC} → Launch Spyder Dashboard GUI"
echo "  • ${GREEN}Right Click${NC} → Show menu (Monitor, Stop, Status, etc.)"
echo ""
echo "To apply changes:"
echo "  1. Press ${GREEN}Alt+F2${NC}, type ${GREEN}r${NC}, press ${GREEN}Enter${NC}"
echo "  2. Or log out and back in"
echo ""
echo "Test the dashboard launcher directly:"
echo "  ${GREEN}$DASHBOARD_LAUNCHER${NC}"
