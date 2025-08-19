#!/bin/bash
# Debug why dashboard process is running but no window appears

echo "🔍 DEBUG: Dashboard Process Running But No Window"
echo "================================================"

echo "Step 1: Check if dashboard process is still running:"
echo "---------------------------------------------------"
DASHBOARD_PID=$(ps aux | grep "SpyderG05_TradingDashboard" | grep -v grep | awk '{print $2}')

if [ -n "$DASHBOARD_PID" ]; then
    echo "✅ Dashboard process found: PID $DASHBOARD_PID"
    
    echo ""
    echo "Step 2: Check process status:"
    echo "----------------------------"
    ps -p $DASHBOARD_PID -o pid,ppid,cmd,stat
    
    echo ""
    echo "Step 3: Check if process has any windows:"
    echo "----------------------------------------"
    # Check if the process has created any X11 windows
    if command -v xwininfo >/dev/null; then
        echo "🔍 Searching for X11 windows by process..."
        # This is tricky - let's try a different approach
    fi
    
    # Check all windows and see if any belong to this PID
    echo "🔍 All windows with PIDs:"
    wmctrl -lp
    
    echo ""
    echo "Step 4: Check if dashboard window is minimized:"
    echo "----------------------------------------------"
    # Try to find any window with our PID
    DASHBOARD_WINDOW=$(wmctrl -lp | grep "$DASHBOARD_PID")
    
    if [ -n "$DASHBOARD_WINDOW" ]; then
        echo "🎯 Found dashboard window: $DASHBOARD_WINDOW"
        
        # Extract window ID and try to raise it
        WINDOW_ID=$(echo "$DASHBOARD_WINDOW" | awk '{print $1}')
        echo "🔧 Attempting to bring window to front..."
        wmctrl -i -a "$WINDOW_ID"
        
        echo "✅ Dashboard window should now be visible!"
        echo "Try Alt+Tab or check your taskbar"
    else
        echo "❌ No window found for dashboard process"
        echo "This suggests the Qt application started but failed to create a window"
    fi
    
else
    echo "❌ Dashboard process not found - it may have exited"
    echo ""
    echo "🔍 Checking for any Python GUI processes:"
    ps aux | grep python | grep -E "(Qt|GUI|PyQt)" | grep -v grep
fi

echo ""
echo "Step 5: Test dashboard visibility:"
echo "---------------------------------"

echo "🧪 Let's check what's happening with the dashboard:"
echo ""
echo "A) If dashboard process is running but no window:"
echo "   - The Qt application may have failed silently"
echo "   - Check for DISPLAY issues"
echo "   - Possible missing dependencies"
echo ""
echo "B) To test, try stopping current dashboard and restarting:"
echo "   1. In the terminal where dashboard is running, press Ctrl+C"
echo "   2. Check for any error messages"
echo "   3. Try launching again with verbose output"

echo ""
echo "Step 6: Environment check:"
echo "-------------------------"
echo "DISPLAY variable: $DISPLAY"
echo "XDG_SESSION_TYPE: $XDG_SESSION_TYPE"

if [ -z "$DISPLAY" ]; then
    echo "❌ DISPLAY not set - this could prevent Qt windows from appearing"
else
    echo "✅ DISPLAY is set"
fi

echo ""
echo "Step 7: Quick window test:"
echo "-------------------------"
echo "🧪 Testing if Qt can create windows in this environment:"

cd /home/adam/Projects/Spyder
source .venv/bin/activate 2>/dev/null

python3 -c "
import sys
try:
    from PyQt6.QtWidgets import QApplication, QLabel, QWidget
    
    app = QApplication([])
    
    # Create a simple test window
    window = QWidget()
    window.setWindowTitle('Qt Test Window')
    window.resize(300, 200)
    
    label = QLabel('If you can see this, Qt works!')
    label.setParent(window)
    label.move(50, 50)
    
    window.show()
    print('✅ Test window created - should be visible for 3 seconds')
    
    # Show for 3 seconds then close
    from PyQt6.QtCore import QTimer
    timer = QTimer()
    timer.timeout.connect(app.quit)
    timer.start(3000)  # 3 seconds
    
    app.exec()
    print('✅ Qt test completed')
    
except Exception as e:
    print(f'❌ Qt test failed: {e}')
    import traceback
    traceback.print_exc()
" &

echo "🔍 A test window should appear for 3 seconds..."
sleep 4

echo ""
echo "Step 8: Next actions:"
echo "-------------------"
echo "1. Check if you saw the test window"
echo "2. If test window worked, dashboard should work too"
echo "3. If no test window, we have a Qt/display issue"
echo "4. Try stopping dashboard (Ctrl+C) and check for errors"