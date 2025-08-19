#!/bin/bash
# Systematic testing of different WM_CLASS values until dock integration works

SPYDER_HOME="/home/adam/Projects/Spyder"
DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"

echo "🧪 SYSTEMATIC WM_CLASS TESTING"
echo "==============================="
echo "We'll test different WM_CLASS values until the dock integration works."
echo ""

# Array of WM_CLASS values to test
WM_CLASS_OPTIONS=(
    "Python3"
    "python3"
    "SpyderTradingDashboard"
    "SpyderG05_TradingDashboard"
    "SPYDER"
    "spyder"
    "spyder-trading"
    "SpyderG05"
    "TradingDashboard"
)

echo "📋 WM_CLASS values we'll test:"
for i in "${!WM_CLASS_OPTIONS[@]}"; do
    echo "  $((i+1)). ${WM_CLASS_OPTIONS[i]}"
done

echo ""
echo "🎯 Testing Strategy:"
echo "1. Update desktop file with each WM_CLASS"
echo "2. Update launcher script with matching app name"
echo "3. Test SPY icon click"
echo "4. Check if orange dot appears UNDER SPY (success) or separate gear (fail)"
echo ""

# Function to update configuration with specific WM_CLASS
update_wmclass() {
    local wmclass="$1"
    
    echo "🔧 Testing WM_CLASS: $wmclass"
    echo "-----------------------------"
    
    # Update launcher script
    cat > "$SPYDER_HOME/launch_dashboard_fixed.sh" << EOF
#!/bin/bash
cd "$SPYDER_HOME"
source .venv/bin/activate

python3 -c "
import sys
sys.path.insert(0, '.')
from PyQt6.QtWidgets import QApplication
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# Set application name for dock integration
app = QApplication(sys.argv)
app.setApplicationName('$wmclass')
app.setApplicationDisplayName('SPYDER Trading System')
app.setDesktopFileName('spyder-trading')

dashboard = SpyderTradingDashboard()
dashboard.setWindowTitle('SPYDER - Autonomous Options Trading System v1.0')
dashboard.show()
dashboard.raise_()
app.exec()
"
EOF
    
    chmod +x "$SPYDER_HOME/launch_dashboard_fixed.sh"
    
    # Update desktop file
    sed -i "s/StartupWMClass=.*/StartupWMClass=$wmclass/" "$DESKTOP_FILE"
    
    # Update desktop database
    update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
    
    echo "✅ Updated configuration with WM_CLASS: $wmclass"
}

# Function to test the current configuration
test_configuration() {
    echo ""
    echo "🧪 TEST THIS CONFIGURATION:"
    echo "1. Press Alt+F2, type 'r', press Enter (reload desktop)"
    echo "2. Click your SPY dock icon"
    echo "3. Observe the result:"
    echo "   ✅ SUCCESS: Orange dot appears UNDER SPY icon"
    echo "   ❌ FAIL: Separate gear icon with orange dot appears"
    echo ""
    read -p "Did you get SUCCESS (orange dot under SPY)? (y/n): " result
    
    if [[ $result =~ ^[Yy]$ ]]; then
        return 0  # Success
    else
        return 1  # Fail
    fi
}

# Start testing
echo "🚀 Starting systematic testing..."
echo ""

for wmclass in "${WM_CLASS_OPTIONS[@]}"; do
    update_wmclass "$wmclass"
    
    if test_configuration; then
        echo ""
        echo "🎉 SUCCESS! Found working WM_CLASS: $wmclass"
        echo "=============================================="
        echo ""
        echo "✅ Your SPY dock icon is now properly integrated!"
        echo "✅ Orange dot should appear under SPY icon when dashboard is running"
        echo "✅ No more separate gear icon"
        echo ""
        echo "🔧 Final configuration:"
        echo "  StartupWMClass: $wmclass"
        echo "  Desktop file: $DESKTOP_FILE"
        echo "  Launcher: $SPYDER_HOME/launch_dashboard_fixed.sh"
        echo ""
        echo "Test completed successfully!"
        exit 0
    else
        echo "❌ $wmclass didn't work, trying next option..."
        echo ""
        
        # Kill any running dashboard before next test
        pkill -f "SpyderG05_TradingDashboard" 2>/dev/null || true
        sleep 1
    fi
done

echo ""
echo "😞 None of the standard WM_CLASS values worked."
echo "==============================================="
echo ""
echo "🔍 Let's try a different approach - manual detection:"
echo ""

# Launch dashboard and try to detect its actual WM_CLASS
echo "🚀 Launching dashboard for manual inspection..."
cd "$SPYDER_HOME"
source .venv/bin/activate

python3 -c "
import sys
sys.path.insert(0, '.')
from PyQt6.QtWidgets import QApplication
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

app = QApplication([])
dashboard = SpyderTradingDashboard()
dashboard.show()
dashboard.raise_()

print('Dashboard launched for inspection')
app.exec()
" &

DASHBOARD_PID=$!
sleep 5

echo ""
echo "🔍 Now let's inspect the actual window properties:"
echo ""

# Try multiple methods to get window info
if command -v xwininfo >/dev/null 2>&1; then
    echo "📊 Window information available. Manual steps:"
    echo "1. Run: xwininfo | grep -i class"
    echo "2. Click on the dashboard window"
    echo "3. Look for WM_CLASS or class information"
fi

echo ""
echo "📋 Alternative methods to try:"
echo "1. xprop | grep -i class (click on dashboard)"
echo "2. wmctrl -lx (look for dashboard in list)"
echo "3. ps aux | grep SpyderG (check process name)"
echo ""

echo "🎯 If you find a different WM_CLASS value:"
echo "1. Note it down"
echo "2. Kill this dashboard (Ctrl+C or pkill -f SpyderG05)"
echo "3. Run this script again"
echo "4. We can add your custom value to test"
echo ""

read -p "Press Enter to continue or Ctrl+C to stop and investigate manually..."

# Clean up
kill $DASHBOARD_PID 2>/dev/null || true

echo ""
echo "🔧 TROUBLESHOOTING OPTIONS:"
echo "=========================="
echo ""
echo "1. **Custom WM_CLASS test:**"
echo "   If you found a different value, edit this script and add it to WM_CLASS_OPTIONS"
echo ""
echo "2. **Alternative approach - Use process name:**"
echo "   Try StartupWMClass=SpyderG05_TradingDashboard"
echo ""
echo "3. **Nuclear option - Desktop file name matching:**"
echo "   Some systems match by desktop file name instead of WM_CLASS"
echo ""
echo "4. **Wayland compatibility issue:**"
echo "   Your system uses Wayland. Some dock integrations work differently."
echo "   Try switching to X11 session temporarily to test."
echo ""

read -p "Would you like to try a custom WM_CLASS value? (y/n): " custom
if [[ $custom =~ ^[Yy]$ ]]; then
    read -p "Enter the custom WM_CLASS value: " CUSTOM_WMCLASS
    update_wmclass "$CUSTOM_WMCLASS"
    test_configuration
fi