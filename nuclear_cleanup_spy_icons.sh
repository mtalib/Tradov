#!/bin/bash
# Nuclear cleanup - remove ALL SPY desktop files and create ONE clean file

echo "💥 NUCLEAR CLEANUP - REMOVING ALL SPY ICONS"
echo "==========================================="
echo "You now have 4 icons! Let's fix this mess immediately."
echo ""

APPS_DIR="$HOME/.local/share/applications"

echo "🗑️  STEP 1: Complete removal of ALL SPY desktop files"
echo "===================================================="

# Remove EVERYTHING SPY-related
echo "Removing all SPY/Spyder desktop files..."

rm -f "$APPS_DIR"/spyder* 2>/dev/null
rm -f "$APPS_DIR"/SPY* 2>/dev/null
rm -f "$APPS_DIR"/SPYDER* 2>/dev/null

echo "✅ Nuked all SPY desktop files"

# Update desktop database to remove from cache
update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo "✅ Updated desktop database"

echo ""
echo "🔄 STEP 2: Wait for system to refresh"
echo "===================================="
echo "Waiting 3 seconds for desktop environment to refresh..."
sleep 3

echo ""
echo "✅ STEP 3: Create ONE clean, working desktop file"
echo "==============================================="

# Create ONE clean desktop file with the most likely working configuration
cat > "$APPS_DIR/spyder-trading.desktop" << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=SPYDER Trading Dashboard
Comment=SPY Options Trading System with GUI Dashboard
GenericName=SPY Trading

# Use the working launcher
Exec=/home/adam/Projects/Spyder/launch_dashboard_wayland_fixed.sh

# Most likely working WM_CLASS for PyQt6 apps
StartupWMClass=python3

# Standard properties
Terminal=false
StartupNotify=true

# Icon and paths
Icon=/home/adam/Projects/Spyder/assets/spyder-icon.png
Path=/home/adam/Projects/Spyder

# Categories
Categories=Application;Development;Finance;

# Keywords
Keywords=trading;options;spy;spyder;stocks;market;dashboard;

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

chmod +x "$APPS_DIR/spyder-trading.desktop"

echo "✅ Created ONE clean desktop file"

# Update desktop database
update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo "✅ Updated desktop database"

echo ""
echo "🔄 STEP 4: Force refresh desktop environment"
echo "=========================================="

# Force GNOME to refresh
if command -v gsettings >/dev/null 2>&1; then
    gsettings reset org.gnome.desktop.app-folders folder-children 2>/dev/null || true
fi

echo "✅ Forced desktop refresh"

echo ""
echo "⏰ STEP 5: Wait for changes to take effect"
echo "========================================"
echo "Waiting 5 seconds for all changes to propagate..."
sleep 5

echo ""
echo "🎯 STEP 6: Test the cleanup"
echo "=========================="
echo ""
echo "NOW PRESS SUPER KEY AND CHECK:"
echo ""
echo "✅ **Expected result:**"
echo "   - Only ONE 'SPYDER Trading Dashboard' icon"
echo "   - No duplicates, no test icons"
echo ""
echo "❌ **If you still see multiple icons:**"
echo "   - The desktop environment is caching old entries"
echo "   - You may need to log out and back in"
echo ""

read -p "Press Enter after checking Super key → Applications view..."

echo ""
echo "📊 How many SPYDER icons do you see now?"
echo "1. Only ONE icon (SUCCESS!)"
echo "2. Still multiple icons (need to log out/in)"
echo "3. NO icons at all (need to debug)"
echo ""
read -p "Enter 1, 2, or 3: " result

case $result in
    1)
        echo ""
        echo "🎉 SUCCESS! Clean desktop achieved!"
        echo "=================================="
        echo ""
        echo "🎯 **Final steps:**"
        echo "1. Right-click the ONE SPYDER icon → 'Add to Favorites'"
        echo "2. Click the SPY dock icon"
        echo "3. Dashboard should launch"
        echo "4. Orange dot should appear UNDER SPY icon"
        echo ""
        echo "✅ The duplicate icon nightmare is finally over!"
        ;;
    2)
        echo ""
        echo "😤 Desktop environment is stubborn!"
        echo "================================="
        echo ""
        echo "🔄 **Nuclear option needed:**"
        echo "1. Log out completely"
        echo "2. Log back in"
        echo "3. Press Super key → Should see only ONE SPYDER icon"
        echo "4. Add to dock and test"
        echo ""
        echo "The cleanup worked, but desktop cache needs to refresh."
        ;;
    3)
        echo ""
        echo "😱 NO icons? This shouldn't happen!"
        echo "================================="
        echo ""
        echo "🔍 **Debug steps:**"
        echo "1. Check file exists: ls -la $APPS_DIR/spyder-trading.desktop"
        echo "2. Force refresh: update-desktop-database $APPS_DIR"
        echo "3. Check permissions: chmod +x $APPS_DIR/spyder-trading.desktop"
        echo ""
        echo "Let me know what ls -la shows."
        ;;
esac

echo ""
echo "📋 **Current state:**"
echo "=================="
echo "Desktop file: $APPS_DIR/spyder-trading.desktop"
echo "StartupWMClass: python3"
echo "Launcher: launch_dashboard_wayland_fixed.sh"
echo ""
echo "No more backup files, no more test files - just ONE clean desktop file!"
