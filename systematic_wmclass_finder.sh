#!/bin/bash
# Systematic approach to find the real PyQt6 dashboard WM_CLASS

echo "🎯 SYSTEMATIC DASHBOARD WM_CLASS FINDER"
echo "======================================="

# Step 1: Kill everything to start clean
echo "Step 1: Cleaning slate..."
pkill -f "brave\|firefox\|chrome" 2>/dev/null || true
pkill -f "SpyderG\|fast_launcher" 2>/dev/null || true
sleep 2

echo "✅ Cleaned running processes"

# Step 2: Show baseline (should be minimal)
echo ""
echo "Step 2: Baseline windows (before launching dashboard):"
wmctrl -lx 2>/dev/null || echo "wmctrl not available"

# Step 3: Instructions for user
echo ""
echo "Step 3: Now launch your dashboard"
echo "================================="
echo "1. Click your SPY dock icon"
echo "2. Wait for dashboard window to open"
echo "3. Do NOT open any browsers"
echo "4. Press Enter when dashboard is visible..."
read -p "Press Enter after dashboard is open: "

# Step 4: Show what's running now
echo ""
echo "Step 4: Windows after dashboard launch:"
echo "======================================="
wmctrl -lx

echo ""
echo "Step 5: Looking for PyQt6 processes:"
echo "==================================="
ps aux | grep -E "(python.*Qt|SpyderG|TradingDashboard)" | grep -v grep

echo ""
echo "Step 6: Automatic WM_CLASS detection:"
echo "===================================="

# Try to automatically find the dashboard window
DASHBOARD_WINDOW=$(wmctrl -lx | grep -v "Desktop" | grep -E "(python|Python|SpyderG|TradingDashboard|fast_launcher)" | head -1)

if [ -n "$DASHBOARD_WINDOW" ]; then
    echo "🎯 Found potential dashboard window:"
    echo "$DASHBOARD_WINDOW"
    
    # Extract WM_CLASS from the line
    WM_CLASS=$(echo "$DASHBOARD_WINDOW" | awk '{print $3}')
    echo ""
    echo "🔧 Extracted WM_CLASS: $WM_CLASS"
    
    # Update desktop file automatically
    DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"
    
    if [ -f "$DESKTOP_FILE" ]; then
        echo "📝 Updating desktop file..."
        cp "$DESKTOP_FILE" "$DESKTOP_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        sed -i "s/StartupWMClass=.*/StartupWMClass=$WM_CLASS/" "$DESKTOP_FILE"
        update-desktop-database ~/.local/share/applications/ 2>/dev/null
        
        echo "✅ Updated desktop file:"
        echo "   StartupWMClass=$WM_CLASS"
        echo ""
        echo "🧪 TEST THE FIX:"
        echo "1. Close dashboard"
        echo "2. Press Alt+F2, type 'r', press Enter"
        echo "3. Click SPY icon"
        echo "4. Check if orange dot appears under SPY (not separate gear)"
    else
        echo "❌ Desktop file not found: $DESKTOP_FILE"
    fi
else
    echo "❌ No PyQt6 dashboard window found"
    echo ""
    echo "🔍 Manual check needed:"
    echo "1. Make sure dashboard is actually running"
    echo "2. Run: xprop WM_CLASS"
    echo "3. Click ONLY on the dashboard window (not browser!)"
    echo "4. Look for WM_CLASS like:"
    echo "   - python3, Python3"
    echo "   - SpyderG05_TradingDashboard"
    echo "   - fast_launcher"
fi

echo ""
echo "Step 7: All windows currently open:"
echo "=================================="
wmctrl -lx | grep -v Desktop