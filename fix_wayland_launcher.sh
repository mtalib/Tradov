#!/bin/bash
# Fix the Wayland launcher PyQt6 error

SPYDER_HOME="/home/adam/Projects/Spyder"

echo "🔧 FIXING WAYLAND LAUNCHER ERROR"
echo "================================"

echo "The error was: AA_UseHighDpiPixmaps attribute doesn't exist"
echo "Let's create a working Wayland launcher..."

# Create fixed Wayland launcher
cat > "$SPYDER_HOME/launch_dashboard_wayland_fixed.sh" << 'EOF'
#!/bin/bash
# Fixed Wayland-compatible Spyder Dashboard Launcher

cd "/home/adam/Projects/Spyder"
source .venv/bin/activate

# Wayland-specific environment setup
export QT_QPA_PLATFORM=wayland
export QT_WAYLAND_FORCE_DPI=96

# Launch with fixed PyQt6 settings (no problematic attributes)
python3 -c "
import sys
import os
sys.path.insert(0, '.')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# Create Qt application
app = QApplication(sys.argv)

# Set application properties for dock integration (no problematic attributes)
app.setApplicationName('python3')
app.setApplicationDisplayName('SPYDER Trading System')  
app.setApplicationVersion('1.0')
app.setOrganizationName('Spyder')
app.setDesktopFileName('spyder-trading')

# Create dashboard
dashboard = SpyderTradingDashboard()
dashboard.setWindowTitle('SPYDER - Autonomous Options Trading System v1.0')

# Show dashboard
dashboard.show()
dashboard.raise_()
dashboard.activateWindow()

print('✅ Dashboard launched successfully with Wayland optimization')
print('Window is now visible and ready for WM_CLASS detection')

app.exec()
"
EOF

chmod +x "$SPYDER_HOME/launch_dashboard_wayland_fixed.sh"

echo "✅ Created fixed Wayland launcher: launch_dashboard_wayland_fixed.sh"

# Update desktop file to use the fixed launcher
DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"

if [ -f "$DESKTOP_FILE" ]; then
    # Update the Exec line to use the fixed launcher
    sed -i "s|Exec=.*|Exec=$SPYDER_HOME/launch_dashboard_wayland_fixed.sh|" "$DESKTOP_FILE"
    echo "✅ Updated desktop file to use fixed launcher"
    
    # Update desktop database
    update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
    echo "✅ Updated desktop database"
else
    echo "❌ Desktop file not found: $DESKTOP_FILE"
fi

echo ""
echo "🚀 NOW TRY LAUNCHING THE DASHBOARD:"
echo "==================================="
echo ""
echo "Method 1 - Direct launch (to get WM_CLASS):"
echo "$SPYDER_HOME/launch_dashboard_wayland_fixed.sh &"
echo ""
echo "Method 2 - Test the dock icon:"
echo "1. Remove any existing SPY icons from dock"
echo "2. Press Super key"
echo "3. Search 'SPYDER Trading'"
echo "4. Right-click result → Add to Favorites"
echo "5. Click the new SPY icon"
echo ""
echo "🎯 Once dashboard is running:"
echo "1. Open new terminal"
echo "2. Run: xprop WM_CLASS" 
echo "3. Click on dashboard window"
echo "4. Note the WM_CLASS value"
echo ""
echo "The fixed launcher should work without PyQt6 errors!"
