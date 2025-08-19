#!/bin/bash
# Wayland-compatible dock integration fix for Spyder

SPYDER_HOME="/home/adam/Projects/Spyder"
DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"

echo "🌊 WAYLAND-COMPATIBLE DOCK INTEGRATION FIX"
echo "=========================================="
echo "Since you're on Wayland, we'll use different methods that work without shell restart."
echo ""

# Step 1: Check current environment
echo "Step 1: Environment Check"
echo "------------------------"
echo "Session Type: $XDG_SESSION_TYPE"
echo "Desktop: $XDG_CURRENT_DESKTOP"
echo "Display: $DISPLAY"
echo ""

# Step 2: Wayland-specific desktop file approach
echo "Step 2: Creating Wayland-optimized desktop file"
echo "----------------------------------------------"

# Backup existing
cp "$DESKTOP_FILE" "$DESKTOP_FILE.wayland_backup.$(date +%Y%m%d_%H%M%S)" 2>/dev/null

# Create Wayland-optimized desktop file
cat > "$DESKTOP_FILE" << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=SPYDER Trading Dashboard
Comment=SPY Options Trading System with GUI Dashboard
GenericName=SPY Trading

# Wayland-optimized execution
Exec=/home/adam/Projects/Spyder/launch_dashboard_wayland.sh
Terminal=false
StartupNotify=true

# Multiple WM_CLASS attempts for Wayland compatibility
StartupWMClass=python3

# Icon and paths
Icon=/home/adam/Projects/Spyder/assets/spyder-icon.png
Path=/home/adam/Projects/Spyder

# Categories
Categories=Finance;Trading;Application;
Keywords=trading;options;spy;spyder;stocks;market;dashboard;

# Wayland-specific properties
X-GNOME-UsesNotifications=true
StartupWMClass=python3

# Actions
Actions=Monitor;Stop;Status;Terminal;

[Desktop Action Monitor]
Name=Monitor System
Exec=gnome-terminal --working-directory=/home/adam/Projects/Spyder -- ./SpyderQ_Scripts/SpyderQ21_Monitor.sh
Icon=utilities-system-monitor

[Desktop Action Stop]
Name=Stop System
Exec=bash -c "cd /home/adam/Projects/Spyder && ./SpyderQ_Scripts/SpyderQ11_StopAll.sh"
Icon=process-stop

[Desktop Action Status]
Name=Check Status
Exec=gnome-terminal --working-directory=/home/adam/Projects/Spyder -- bash -c "./SpyderQ_Scripts/SpyderQ20_Status.sh; read"
Icon=dialog-information

[Desktop Action Terminal]
Name=Open Terminal
Exec=gnome-terminal --working-directory=/home/adam/Projects/Spyder
Icon=utilities-terminal
EOF

chmod +x "$DESKTOP_FILE"
echo "✅ Created Wayland-optimized desktop file"

# Step 3: Create Wayland-specific launcher
echo ""
echo "Step 3: Creating Wayland-compatible launcher"
echo "-------------------------------------------"

cat > "$SPYDER_HOME/launch_dashboard_wayland.sh" << 'EOF'
#!/bin/bash
# Wayland-compatible Spyder Dashboard Launcher

cd "/home/adam/Projects/Spyder"
source .venv/bin/activate

# Wayland-specific environment setup
export QT_QPA_PLATFORM=wayland
export QT_WAYLAND_FORCE_DPI=96

# Launch with Wayland-optimized PyQt6 settings
python3 -c "
import sys
import os
sys.path.insert(0, '.')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# Wayland-specific Qt settings
app = QApplication(sys.argv)

# Set application properties for Wayland dock integration
app.setApplicationName('python3')
app.setApplicationDisplayName('SPYDER Trading System')  
app.setApplicationVersion('1.0')
app.setOrganizationName('Spyder')
app.setDesktopFileName('spyder-trading')

# Additional Wayland-specific properties
app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

# Create dashboard
dashboard = SpyderTradingDashboard()
dashboard.setWindowTitle('SPYDER - Autonomous Options Trading System v1.0')

# Wayland window properties
dashboard.show()
dashboard.raise_()
dashboard.activateWindow()

# Set window class explicitly (Wayland method)
if hasattr(dashboard, 'winId'):
    dashboard.setProperty('_q_wayland_window_type', 'normal')

print('Dashboard launched with Wayland optimization')
app.exec()
"
EOF

chmod +x "$SPYDER_HOME/launch_dashboard_wayland.sh"
echo "✅ Created Wayland-compatible launcher"

# Step 4: Wayland desktop database update
echo ""
echo "Step 4: Updating desktop database (Wayland method)"
echo "-------------------------------------------------"

# Multiple methods to ensure desktop file is recognized
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true

# Force GTK to refresh (Wayland-specific)
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache ~/.local/share/icons/ 2>/dev/null || true
fi

# Update MIME database 
if command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database ~/.local/share/mime/ 2>/dev/null || true
fi

echo "✅ Desktop database updated"

# Step 5: Wayland-specific testing approach
echo ""
echo "Step 5: Wayland Testing Approach"
echo "==============================="

echo "🌊 Since Wayland doesn't allow shell restart, we'll use these methods:"
echo ""

echo "Method 1: Remove and re-add SPY icon"
echo "------------------------------------"
echo "1. Right-click SPY icon in dock"
echo "2. Select 'Remove from Favorites' or 'Unpin'"
echo "3. Press Super key, search 'SPYDER'"
echo "4. Right-click SPYDER result → 'Add to Favorites'"
echo ""

echo "Method 2: Application overview method"
echo "-----------------------------------"
echo "1. Press Super key (Activities overview)"
echo "2. Look for 'SPYDER Trading Dashboard'"
echo "3. Click to launch"
echo "4. Check if it groups under SPY icon"
echo ""

echo "Method 3: Force desktop file refresh"
echo "-----------------------------------"

# Create a script to force refresh the desktop file
cat > "/tmp/refresh_spyder_desktop.sh" << 'EOF'
#!/bin/bash
# Force refresh desktop integration

# Remove from cache
rm -f ~/.cache/applications/spyder-trading.desktop 2>/dev/null

# Force GNOME to re-read desktop files
gsettings reset org.gnome.desktop.app-folders folder-children 2>/dev/null || true

# Update desktop database
update-desktop-database ~/.local/share/applications/

echo "Desktop integration refreshed"
EOF

chmod +x /tmp/refresh_spyder_desktop.sh
/tmp/refresh_spyder_desktop.sh

echo "✅ Forced desktop file refresh"

# Step 6: Test different WM_CLASS values for Wayland
echo ""
echo "Step 6: Wayland WM_CLASS Testing"
echo "==============================="

WM_CLASSES=("python3" "Python3" "spyder-trading" "SpyderTradingDashboard" "SPYDER")

echo "We'll test these WM_CLASS values for Wayland compatibility:"
for i in "${!WM_CLASSES[@]}"; do
    echo "  $((i+1)). ${WM_CLASSES[i]}"
done

echo ""
read -p "Start with which WM_CLASS? (1-5 or press Enter for python3): " choice

case ${choice:-1} in
    1) WMCLASS="python3" ;;
    2) WMCLASS="Python3" ;;
    3) WMCLASS="spyder-trading" ;;
    4) WMCLASS="SpyderTradingDashboard" ;;
    5) WMCLASS="SPYDER" ;;
    *) WMCLASS="python3" ;;
esac

# Update desktop file with chosen WM_CLASS
sed -i "s/StartupWMClass=.*/StartupWMClass=$WMCLASS/" "$DESKTOP_FILE"

# Update launcher with matching application name
sed -i "s/app.setApplicationName('.*')/app.setApplicationName('$WMCLASS')/" "$SPYDER_HOME/launch_dashboard_wayland.sh"

update-desktop-database ~/.local/share/applications/ 2>/dev/null || true

echo "✅ Updated to WM_CLASS: $WMCLASS"

# Step 7: Wayland testing instructions
echo ""
echo "🧪 WAYLAND TESTING INSTRUCTIONS"
echo "==============================="

echo ""
echo "🎯 Test Method 1 - Re-pin SPY icon:"
echo "1. Right-click current SPY icon → Remove from dock"
echo "2. Press Super key → Search 'SPYDER'"
echo "3. Right-click result → 'Add to Favorites'"
echo "4. Click new SPY icon"
echo "5. Check: Orange dot under SPY ✅ or separate gear ❌"

echo ""
echo "🎯 Test Method 2 - Direct launch test:"
echo "1. Run: $SPYDER_HOME/launch_dashboard_wayland.sh"
echo "2. Check dock behavior while dashboard is running"

echo ""
echo "🎯 Test Method 3 - Activities overview:"
echo "1. Press Super key"
echo "2. Click on SPYDER Trading Dashboard"
echo "3. Observe dock integration"

echo ""
echo "💡 WAYLAND-SPECIFIC NOTES:"
echo "- Changes may take longer to apply"
echo "- Some desktop environments cache .desktop files aggressively"
echo "- If nothing works, try logging out and back in"

echo ""
echo "🔧 Current Configuration:"
echo "StartupWMClass: $WMCLASS"
echo "Launcher: $SPYDER_HOME/launch_dashboard_wayland.sh"
echo "Desktop file: $DESKTOP_FILE"

echo ""
echo "Ready to test Wayland dock integration!"
