#!/bin/bash
# Find the currently running PyQt6 dashboard window

echo "🔍 FINDING YOUR RUNNING DASHBOARD"
echo "================================="

echo "Step 1: All current windows:"
echo "----------------------------"
wmctrl -lx

echo ""
echo "Step 2: Looking for Python/PyQt windows:"
echo "---------------------------------------"
PYTHON_WINDOWS=$(wmctrl -lx | grep -i -E "(python|qt|spyder|dashboard|trading)" | grep -v "Desktop")

if [ -n "$PYTHON_WINDOWS" ]; then
    echo "🎯 Found Python/Qt windows:"
    echo "$PYTHON_WINDOWS"
    
    # Extract just the WM_CLASS from the first match
    FIRST_PYTHON_WINDOW=$(echo "$PYTHON_WINDOWS" | head -1)
    WM_CLASS=$(echo "$FIRST_PYTHON_WINDOW" | awk '{print $3}')
    
    echo ""
    echo "🔧 First Python window WM_CLASS: $WM_CLASS"
    
    # If we found a Python window, that's likely our dashboard
    if [[ "$WM_CLASS" == *"python"* ]] || [[ "$WM_CLASS" == *"Python"* ]] || [[ "$WM_CLASS" == *"Spyder"* ]]; then
        echo "✅ This looks like your dashboard!"
        echo ""
        echo "🛠️ UPDATING DESKTOP FILE NOW..."
        
        DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"
        if [ -f "$DESKTOP_FILE" ]; then
            # Backup and update
            cp "$DESKTOP_FILE" "$DESKTOP_FILE.backup.$(date +%Y%m%d_%H%M%S)"
            sed -i "s/StartupWMClass=.*/StartupWMClass=$WM_CLASS/" "$DESKTOP_FILE"
            update-desktop-database ~/.local/share/applications/ 2>/dev/null
            
            echo "✅ Updated desktop file:"
            echo "   StartupWMClass=$WM_CLASS"
            echo ""
            echo "🧪 TO TEST THE FIX:"
            echo "1. Close your current dashboard (Ctrl+C in the terminal where it's running)"
            echo "2. Press Alt+F2, type 'r', press Enter (reload desktop)"
            echo "3. Click your SPY icon"
            echo "4. Check if you get orange dot under SPY instead of separate gear"
        else
            echo "❌ Desktop file not found"
        fi
    fi
else
    echo "❌ No Python/PyQt windows found"
    echo ""
    echo "🔍 Alternative search - all non-browser windows:"
    wmctrl -lx | grep -v -i -E "(brave|firefox|chrome|browser)" | grep -v "Desktop"
fi

echo ""
echo "Step 3: Process check:"
echo "---------------------"
echo "🐍 Python processes that might be your dashboard:"
ps aux | grep python | grep -E "(SpyderG|TradingDashboard|dashboard)" | grep -v grep

echo ""
echo "Step 4: Window focus check:"
echo "-------------------------"
echo "Your dashboard might be running but not focused. Try:"
echo "1. Alt+Tab to cycle through windows"
echo "2. Look for 'Spyder' or 'Trading' in the window list"
echo "3. Click on that window to bring it to front"
echo "4. Then run: xprop WM_CLASS and click on it"

echo ""
echo "Step 5: Manual verification:"
echo "---------------------------"
echo "If dashboard is visible on your screen:"
echo "1. Take note of its window title/appearance"
echo "2. Close ALL browser windows temporarily"
echo "3. Run: xprop WM_CLASS"
echo "4. Click ONLY on the dashboard window"
echo "5. You should NOT get 'brave-browser'"