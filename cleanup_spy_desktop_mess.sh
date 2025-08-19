#!/bin/bash
# Clean up the SPY desktop file mess and fix dock integration

echo "🧹 CLEANING UP SPY DESKTOP FILE MESS"
echo "===================================="
echo "You have 10 desktop files! No wonder there are duplicate icons."
echo ""

APPS_DIR="$HOME/.local/share/applications"

echo "🔍 CURRENT PROBLEM:"
echo "=================="
echo "Current active file: spyder-trading.desktop"
echo "   StartupWMClass: tilix  ❌ WRONG! (copied from ClaudeFlow)"
echo "   ClaudeFlow uses tilix (terminal), Spyder uses Python"
echo ""

echo "🎯 SOLUTION: Test the 2 most promising candidates"
echo "================================================"

echo ""
echo "✅ Candidate #1: python3 StartupWMClass (most likely to work)"
echo "------------------------------------------------------------"
echo "File: spyder-trading.desktop.before_claude_flow_method.20250819_130431"
echo "StartupWMClass: python3"
echo "Launcher: launch_dashboard_wayland.sh"
echo ""

echo "✅ Candidate #2: spyder-trading StartupWMClass" 
echo "----------------------------------------------"
echo "File: spyder-trading-OLD.desktop"
echo "StartupWMClass: spyder-trading"
echo "Launcher: launch_dashboard.sh"
echo ""

echo "🧪 TESTING APPROACH:"
echo "==================="
echo "We'll test both candidates and keep the working one"
echo ""

# Test Candidate #1 (python3)
echo "🧪 Testing Candidate #1 (python3 WMClass)..."
echo "--------------------------------------------"

# Copy the promising candidate to be the active file
cp "$APPS_DIR/spyder-trading.desktop.before_claude_flow_method.20250819_130431" "$APPS_DIR/spyder-trading-test1.desktop"

# But update it to use the working fixed launcher
sed -i 's|Exec=.*|Exec=/home/adam/Projects/Spyder/launch_dashboard_wayland_fixed.sh|' "$APPS_DIR/spyder-trading-test1.desktop"

# Update name for testing
sed -i 's|Name=.*|Name=SPYDER Test 1 (python3)|' "$APPS_DIR/spyder-trading-test1.desktop"

echo "✅ Created test file: spyder-trading-test1.desktop"
echo "   StartupWMClass: python3"
echo "   Launcher: launch_dashboard_wayland_fixed.sh"

# Test Candidate #2 (spyder-trading)
echo ""
echo "🧪 Testing Candidate #2 (spyder-trading WMClass)..."
echo "---------------------------------------------------"

# Copy the old candidate
cp "$APPS_DIR/spyder-trading-OLD.desktop" "$APPS_DIR/spyder-trading-test2.desktop"

# Update it to use the working fixed launcher
sed -i 's|Exec=.*|Exec=/home/adam/Projects/Spyder/launch_dashboard_wayland_fixed.sh|' "$APPS_DIR/spyder-trading-test2.desktop"

# Update name for testing
sed -i 's|Name=.*|Name=SPYDER Test 2 (spyder-trading)|' "$APPS_DIR/spyder-trading-test2.desktop"

echo "✅ Created test file: spyder-trading-test2.desktop"
echo "   StartupWMClass: spyder-trading"  
echo "   Launcher: launch_dashboard_wayland_fixed.sh"

# Update desktop database
update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo ""
echo "🎯 NOW TEST BOTH CANDIDATES:"
echo "============================"
echo ""
echo "1. **Press Super key**"
echo "2. **Look for these icons:**"
echo "   📊 'SPYDER Test 1 (python3)'"
echo "   📊 'SPYDER Test 2 (spyder-trading)'"
echo ""
echo "3. **Test each one:**"
echo "   - Click icon"
echo "   - See if dashboard launches"
echo "   - Add to dock (if it works)"
echo "   - Check if orange dot appears UNDER the icon (not separate)"
echo ""

read -p "Press Enter after you've tested both candidates and identified the working one..."

echo ""
echo "🏆 WHICH ONE WORKED?"
echo "===================="
echo "1. Test 1 (python3) worked"
echo "2. Test 2 (spyder-trading) worked"  
echo "3. Neither worked properly"
echo "4. Both worked (choose your preference)"
echo ""
read -p "Enter 1, 2, 3, or 4: " choice

case $choice in
    1)
        WINNER="spyder-trading-test1.desktop"
        WINNER_WMCLASS="python3"
        echo "✅ Winner: Test 1 (python3)"
        ;;
    2)
        WINNER="spyder-trading-test2.desktop"
        WINNER_WMCLASS="spyder-trading"
        echo "✅ Winner: Test 2 (spyder-trading)"
        ;;
    3)
        echo "❌ Neither worked. We need to debug further."
        echo "Let's check what WM_CLASS your dashboard actually uses:"
        echo ""
        echo "1. Launch dashboard: ~/Projects/Spyder/launch_dashboard_wayland_fixed.sh &"
        echo "2. Run: xprop WM_CLASS"
        echo "3. Click on dashboard window"
        echo "4. Tell me the exact WM_CLASS value"
        exit 1
        ;;
    4)
        echo "🤔 Both worked? Let's use python3 (most standard for PyQt apps)"
        WINNER="spyder-trading-test1.desktop"
        WINNER_WMCLASS="python3"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "🧹 CLEANUP: Removing all the clutter"
echo "===================================="

# Remove the current broken file and all backups
echo "🗑️  Removing broken files and backups..."

rm -f "$APPS_DIR/spyder-trading.desktop" 2>/dev/null
rm -f "$APPS_DIR"/spyder-trading.desktop.backup.* 2>/dev/null
rm -f "$APPS_DIR"/spyder-trading.desktop.before_* 2>/dev/null
rm -f "$APPS_DIR/spyder-trading.desktop.save" 2>/dev/null
rm -f "$APPS_DIR/spyder-trading.desktop.wayland_backup"* 2>/dev/null

echo "✅ Removed all backup and broken files"

# Keep only the winner
if [ "$WINNER" = "spyder-trading-test1.desktop" ]; then
    rm -f "$APPS_DIR/spyder-trading-test2.desktop"
    mv "$APPS_DIR/spyder-trading-test1.desktop" "$APPS_DIR/spyder-trading.desktop"
    rm -f "$APPS_DIR/spyder-trading-OLD.desktop"
else
    rm -f "$APPS_DIR/spyder-trading-test1.desktop"
    mv "$APPS_DIR/spyder-trading-test2.desktop" "$APPS_DIR/spyder-trading.desktop"
    rm -f "$APPS_DIR/spyder-trading-OLD.desktop"
fi

# Clean up the winner file (remove test name)
sed -i 's|Name=SPYDER Test.*|Name=SPYDER Trading Dashboard|' "$APPS_DIR/spyder-trading.desktop"

echo "✅ Kept only the working desktop file"

# Update desktop database
update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo ""
echo "🎉 CLEANUP COMPLETE!"
echo "===================="
echo ""
echo "✅ **Result:**"
echo "   - Only ONE desktop file remains: spyder-trading.desktop"
echo "   - StartupWMClass: $WINNER_WMCLASS"
echo "   - No more duplicate icons!"
echo ""
echo "🎯 **Final Test:**"
echo "1. Press Super key"
echo "2. Search 'SPYDER Trading'"
echo "3. You should see only ONE icon"
echo "4. Right-click → 'Add to Favorites'"
echo "5. Click SPY icon → Dashboard launches"
echo "6. Orange dot should appear UNDER SPY icon (not separate)"
echo ""
echo "🎊 **Success Criteria:**"
echo "✅ Only one SPYDER icon in Applications"
echo "✅ Dashboard launches when clicking SPY"
echo "✅ Orange dot under SPY icon (no separate gear)"
echo ""

# Show current state
echo "📋 **Current desktop file:**"
echo "=========================="
echo "File: $APPS_DIR/spyder-trading.desktop"
echo "Content:"
echo "--------"
head -15 "$APPS_DIR/spyder-trading.desktop"

echo ""
echo "🎯 The duplicate icon nightmare is finally over!"
