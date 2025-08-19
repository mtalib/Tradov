#!/bin/bash
# Identify all windows to find the actual dashboard

echo "🔍 WINDOW IDENTIFICATION TOOL"
echo "=============================="

echo "Step 1: Current running processes related to Spyder:"
echo "----------------------------------------------------"
ps aux | grep -E "(python|spy|dash|fast_launcher|SpyderG05)" | grep -v grep

echo ""
echo "Step 2: All open windows:"
echo "------------------------"
if command -v wmctrl &> /dev/null; then
    echo "Window ID | Desktop | PID | WM_CLASS | Title"
    echo "----------|---------|-----|----------|------"
    wmctrl -lxp
else
    echo "Installing wmctrl first..."
    sudo apt install wmctrl -y
    echo "Window ID | Desktop | PID | WM_CLASS | Title"  
    echo "----------|---------|-----|----------|------"
    wmctrl -lxp
fi

echo ""
echo "Step 3: Let's identify your dashboard window:"
echo "--------------------------------------------"
echo "Look at the list above and find windows that might be your dashboard."
echo "Common patterns to look for:"
echo "  🔹 WM_CLASS containing: python, Python3, fast_launcher, SpyderG05"
echo "  🔹 Title containing: Dashboard, Trading, Spyder, SPY"
echo ""

echo "Step 4: Interactive window selection:"
echo "------------------------------------"
echo "I'll help you click on each potential window..."

# List potential dashboard windows
if command -v wmctrl &> /dev/null; then
    echo ""
    echo "🎯 Potential dashboard windows:"
    wmctrl -lx | grep -v "brave-browser" | grep -E "(python|Python|dash|trading|spy|Spy|fast|launcher)" || echo "No obvious dashboard windows found"
    
    echo ""
    echo "🎯 All non-browser windows:"
    wmctrl -lx | grep -v "brave-browser"
fi

echo ""
echo "Step 5: Manual identification:"
echo "-----------------------------"
echo "1. Look at your screen - identify which window looks like your trading dashboard"
echo "2. Run: xprop WM_CLASS"
echo "3. Click ONLY on that dashboard window (not browser, not terminal)"
echo "4. The WM_CLASS should NOT be 'brave-browser'"

echo ""
echo "🚨 If dashboard keeps showing as 'brave-browser':"
echo "  This means your dashboard might be web-based (running in browser)"
echo "  In that case, the WM_CLASS should be 'brave-browser' and that's correct!"

echo ""
echo "Step 6: Quick test - Close all browsers:"
echo "---------------------------------------"
echo "1. Close all browser windows"
echo "2. Launch dashboard from SPY icon"  
echo "3. Run: xprop WM_CLASS"
echo "4. Click on the dashboard"
echo "5. If you still get 'brave-browser', then dashboard IS web-based"