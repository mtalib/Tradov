#!/bin/bash
# Get the REAL WM_CLASS and fix the configuration

SPYDER_HOME="/home/adam/Projects/Spyder"
DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"

echo "🔧 FIXING WM_CLASS CONFIGURATION"
echo "================================"
echo "The previous attempt used 'WM_CLASS' as literal text instead of the actual value."
echo "Let's get the REAL WM_CLASS and fix this properly."
echo ""

# Step 1: Launch dashboard again and get REAL WM_CLASS
echo "Step 1: Launching dashboard to get real WM_CLASS"
echo "------------------------------------------------"

cd "$SPYDER_HOME"
source .venv/bin/activate

# Launch dashboard in background
python3 -c "
import sys
sys.path.insert(0, '.')
from PyQt6.QtWidgets import QApplication
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

app = QApplication([])
app.setApplicationName('SpyderTradingDashboard')  # Set a known name
dashboard = SpyderTradingDashboard()
dashboard.show()
dashboard.raise_()

print('Dashboard is now visible!')
print('Dashboard window title:', dashboard.windowTitle())
app.exec()
" &

DASHBOARD_PID=$!
echo "📊 Dashboard launched with PID: $DASHBOARD_PID"
echo ""
echo "🔍 Wait 5 seconds for dashboard to appear..."
sleep 5

echo ""
echo "🎯 NOW - VERY IMPORTANT:"
echo "========================"
echo "1. Look for the dashboard window (trading interface, NOT browser)"
echo "2. The dashboard should have title: 'SPYDER - Autonomous Options Trading System v1.0'"
echo "3. Open a NEW terminal and run: xprop WM_CLASS"
echo "4. Click on the DASHBOARD window (the trading interface)"
echo "5. You'll see something like: WM_CLASS(STRING) = \"python3\", \"Python3\""
echo "6. The SECOND string (\"Python3\") is what we need"
echo ""

# Give user time to get WM_CLASS
echo "Please do the xprop step now..."
echo ""
read -p "Enter the SECOND string from WM_CLASS (e.g., Python3, SpyderTradingDashboard): " REAL_WM_CLASS

# Kill the dashboard
kill $DASHBOARD_PID 2>/dev/null
sleep 2

echo ""
echo "✅ You entered: $REAL_WM_CLASS"

# Validate the input
if [ "$REAL_WM_CLASS" = "WM_CLASS" ] || [ "$REAL_WM_CLASS" = "WM_CLASS(STRING)" ] || [ -z "$REAL_WM_CLASS" ]; then
    echo "❌ That's still not the real WM_CLASS value!"
    echo "Let's try a different approach..."
    
    # Try common PyQt6 WM_CLASS values
    echo ""
    echo "🧪 Let's test common PyQt6 WM_CLASS values:"
    echo "1. python3"
    echo "2. Python3" 
    echo "3. SpyderTradingDashboard"
    echo "4. SpyderG05_TradingDashboard"
    echo ""
    read -p "Choose 1-4 or enter a custom value: " CHOICE
    
    case $CHOICE in
        1) REAL_WM_CLASS="python3" ;;
        2) REAL_WM_CLASS="Python3" ;;
        3) REAL_WM_CLASS="SpyderTradingDashboard" ;;
        4) REAL_WM_CLASS="SpyderG05_TradingDashboard" ;;
        *) REAL_WM_CLASS="$CHOICE" ;;
    esac
fi

echo ""
echo "Step 2: Updating configuration with real WM_CLASS: $REAL_WM_CLASS"
echo "================================================================="

# Update the launcher script
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
app.setApplicationName('$REAL_WM_CLASS')  # Match WM_CLASS
app.setApplicationDisplayName('SPYDER Trading System')
app.setDesktopFileName('spyder-trading')  # Match .desktop file name

# Create and show dashboard
dashboard = SpyderTradingDashboard()
dashboard.setWindowTitle('SPYDER - Autonomous Options Trading System v1.0')
dashboard.show()
dashboard.raise_()
dashboard.activateWindow()

app.exec()
"
EOF

chmod +x "$SPYDER_HOME/launch_dashboard_fixed.sh"
echo "✅ Updated launcher script with WM_CLASS: $REAL_WM_CLASS"

# Update desktop file
sed -i "s/StartupWMClass=.*/StartupWMClass=$REAL_WM_CLASS/" "$DESKTOP_FILE"
echo "✅ Updated desktop file with StartupWMClass=$REAL_WM_CLASS"

# Update desktop database
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
echo "✅ Updated desktop database"

echo ""
echo "Step 3: Testing the fix"
echo "======================="

echo "🧪 TEST THE FIX NOW:"
echo "1. Press Alt+F2, type 'r', press Enter (reload desktop)"
echo "2. Click your SPY dock icon"
echo "3. Check if orange dot appears UNDER SPY icon (not separate gear)"
echo ""

echo "🎯 What should happen:"
echo "✅ Dashboard opens when clicking SPY"
echo "✅ Orange dot appears UNDER the SPY icon"
echo "❌ NO separate gear icon with orange dot"
echo ""

echo "If you still see a separate gear icon, try these WM_CLASS values:"
echo "- python3"
echo "- Python3"  
echo "- SpyderTradingDashboard"
echo ""

echo "🔧 Current configuration:"
echo "Desktop file: $DESKTOP_FILE"
echo "StartupWMClass: $REAL_WM_CLASS"
echo "Launcher: $SPYDER_HOME/launch_dashboard_fixed.sh"

echo ""
echo "Ready to test! Click your SPY icon now!"
