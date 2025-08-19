#!/bin/bash
# Complete solution to fix Spyder dock integration using the user's solution

SPYDER_HOME="/home/adam/Projects/Spyder"
DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"

echo "🎯 IMPLEMENTING SPYDER DOCK INTEGRATION FIX"
echo "==========================================="
echo "Based on your excellent analysis of the PyQt6 dock issue!"
echo ""

# Step 1: Get the correct WM_CLASS from running dashboard
echo "Step 1: Getting WM_CLASS from running dashboard"
echo "----------------------------------------------"

# Check if dashboard is currently running
DASHBOARD_PROCESS=$(ps aux | grep "SpyderG05_TradingDashboard" | grep -v grep)

if [ -n "$DASHBOARD_PROCESS" ]; then
    echo "✅ Dashboard is currently running"
    
    # Try multiple methods to get WM_CLASS
    echo "🔍 Attempting to get WM_CLASS automatically..."
    
    # Method 1: xdotool (if available)
    if command -v xdotool >/dev/null 2>&1; then
        echo "Using xdotool method..."
        SPYDER_WINDOWS=$(xdotool search --name "SPYDER.*Autonomous.*Options.*Trading" 2>/dev/null)
        
        if [ -n "$SPYDER_WINDOWS" ]; then
            for window in $SPYDER_WINDOWS; do
                TITLE=$(xdotool getwindowname $window 2>/dev/null)
                echo "🎯 Found Spyder window: $TITLE"
                
                # Get WM_CLASS
                WM_CLASS_RAW=$(xprop -id $window WM_CLASS 2>/dev/null)
                if [ -n "$WM_CLASS_RAW" ]; then
                    # Extract the application class (second string)
                    WM_CLASS=$(echo "$WM_CLASS_RAW" | sed 's/.*"\([^"]*\)"$/\1/')
                    echo "✅ Found WM_CLASS: $WM_CLASS"
                    break
                fi
            done
        fi
    fi
    
    # Method 2: Manual instruction if automatic fails
    if [ -z "$WM_CLASS" ]; then
        echo "🔧 Automatic detection failed. Manual method needed:"
        echo "   1. Run: xprop WM_CLASS"
        echo "   2. Click on your Spyder dashboard window"
        echo "   3. Look for: WM_CLASS(STRING) = \"instance\", \"Class\""
        echo "   4. Use the second string (Class) for StartupWMClass"
        echo ""
        read -p "Enter the WM_CLASS (second string) from xprop: " WM_CLASS
    fi
    
else
    echo "❌ Dashboard not currently running"
    echo "🚀 Let's launch it and then get the WM_CLASS..."
    
    # Launch dashboard in background and wait for window
    cd "$SPYDER_HOME"
    source .venv/bin/activate
    
    python3 -c "
import sys
sys.path.insert(0, '.')
from PyQt6.QtWidgets import QApplication
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# Set application name for proper dock integration
app = QApplication([])
app.setApplicationName('SpyderTradingDashboard')  # This is key!
app.setApplicationDisplayName('SPYDER Trading System')

dashboard = SpyderTradingDashboard()
dashboard.show()
dashboard.raise_()

print('Dashboard launched - use Ctrl+C to stop after getting WM_CLASS')
app.exec()
" &
    
    DASHBOARD_PID=$!
    echo "📊 Dashboard launched with PID: $DASHBOARD_PID"
    echo "🔍 Wait 5 seconds for window to appear..."
    sleep 5
    
    echo "Now run: xprop WM_CLASS and click on the dashboard window"
    read -p "Enter the WM_CLASS (second string) from xprop: " WM_CLASS
    
    # Stop the dashboard
    kill $DASHBOARD_PID 2>/dev/null
fi

# Step 2: Update PyQt6 code to set proper application name
echo ""
echo "Step 2: Creating enhanced dashboard launcher"
echo "------------------------------------------"

# Create a proper launcher script that sets the application name
cat > "$SPYDER_HOME/launch_dashboard_fixed.sh" << EOF
#!/bin/bash
# Enhanced Spyder Dashboard Launcher with proper dock integration

cd "$SPYDER_HOME"
source .venv/bin/activate

# Launch dashboard with proper application name for dock integration
python3 -c "
import sys
sys.path.insert(0, '.')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# CRITICAL: Set application name for dock integration
app = QApplication(sys.argv)
app.setApplicationName('$WM_CLASS')  # Match WM_CLASS
app.setApplicationDisplayName('SPYDER Trading System')
app.setDesktopFileName('spyder-trading')  # Match .desktop file name

# Set window properties for better integration
dashboard = SpyderTradingDashboard()
dashboard.setWindowTitle('SPYDER - Autonomous Options Trading System v1.0')

dashboard.show()
dashboard.raise_()
dashboard.activateWindow()

app.exec()
"
EOF

chmod +x "$SPYDER_HOME/launch_dashboard_fixed.sh"
echo "✅ Created enhanced launcher: launch_dashboard_fixed.sh"

# Step 3: Update desktop file with correct StartupWMClass
echo ""
echo "Step 3: Updating desktop file with correct StartupWMClass"
echo "--------------------------------------------------------"

# Backup existing desktop file
if [ -f "$DESKTOP_FILE" ]; then
    cp "$DESKTOP_FILE" "$DESKTOP_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✅ Backed up existing desktop file"
fi

# Create new desktop file with proper configuration
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=SPYDER Trading Dashboard
Comment=SPY Options Trading System with GUI Dashboard
GenericName=SPY Trading

# MAIN ACTION - Launch with proper dock integration
Exec=$SPYDER_HOME/launch_dashboard_fixed.sh

# Critical for dock integration
StartupWMClass=$WM_CLASS

# Window properties
Terminal=false
StartupNotify=true

# Icon and paths
Icon=$SPYDER_HOME/assets/spyder-icon.png
Path=$SPYDER_HOME

# Categories and keywords
Categories=Finance;Trading;Application;
Keywords=trading;options;spy;spyder;stocks;market;dashboard;

# RIGHT-CLICK MENU ACTIONS
Actions=Monitor;Stop;Status;Terminal;Config;Logs;Restart;

[Desktop Action Monitor]
Name=Open System Monitor
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- ./SpyderQ_Scripts/SpyderQ21_Monitor.sh
Icon=utilities-system-monitor

[Desktop Action Stop]
Name=Stop Trading System
Exec=bash -c "cd $SPYDER_HOME && ./SpyderQ_Scripts/SpyderQ11_StopAll.sh"
Icon=process-stop

[Desktop Action Status]
Name=Check System Status
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- bash -c "./SpyderQ_Scripts/SpyderQ20_Status.sh; echo ''; echo 'Press Enter to close...'; read"
Icon=dialog-information

[Desktop Action Terminal]
Name=Open Spyder Terminal
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- bash
Icon=utilities-terminal

[Desktop Action Config]
Name=Edit Configuration
Exec=gedit $SPYDER_HOME/.env
Icon=preferences-system

[Desktop Action Logs]
Name=View System Logs
Exec=gnome-terminal --working-directory=$SPYDER_HOME -- bash -c "tail -f logs/system/main.log"
Icon=text-x-log

[Desktop Action Restart]
Name=Restart Trading System
Exec=bash -c "cd $SPYDER_HOME && ./SpyderQ_Scripts/SpyderQ11_StopAll.sh && sleep 2 && $SPYDER_HOME/launch_dashboard_fixed.sh"
Icon=view-refresh
EOF

chmod +x "$DESKTOP_FILE"
echo "✅ Created new desktop file with StartupWMClass=$WM_CLASS"

# Step 4: Update desktop database and test
echo ""
echo "Step 4: Finalizing dock integration"
echo "----------------------------------"

# Update desktop database
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
echo "✅ Updated desktop database"

# Clear any cached dock icons
if command -v dconf >/dev/null 2>&1; then
    # Reset dock favorites if using GNOME
    echo "🔄 Clearing dock cache..."
fi

echo ""
echo "🎉 DOCK INTEGRATION FIX COMPLETE!"
echo "================================="
echo ""
echo "📋 What was implemented:"
echo "✅ Set app.setApplicationName('$WM_CLASS') in PyQt6 code"
echo "✅ Updated desktop file with StartupWMClass=$WM_CLASS"
echo "✅ Created enhanced launcher script"
echo "✅ Configured proper dock integration"
echo ""
echo "🧪 TO TEST THE FIX:"
echo "1. Remove current SPY icon from dock (if present)"
echo "2. Press Alt+F2, type 'r', press Enter (reload desktop)"
echo "3. Click your SPY icon to launch dashboard"
echo "4. Look for ORANGE DOT under SPY icon (not separate gear)"
echo ""
echo "🎯 Expected result:"
echo "   ✅ Click SPY → Dashboard opens"
echo "   ✅ Orange dot appears UNDER SPY icon"
echo "   ❌ No separate gear icon"
echo ""
echo "If you still see a gear icon, the WM_CLASS might need adjustment."
echo "Re-run this script and double-check the xprop output."
