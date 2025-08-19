#!/bin/bash
# Debug why the dashboard isn't launching from SPY icon

SPYDER_HOME="/home/adam/Projects/Spyder"
DASHBOARD_LAUNCHER="$SPYDER_HOME/launch_dashboard.sh"

echo "🔍 DEBUGGING DASHBOARD LAUNCH ISSUE"
echo "==================================="

# Step 1: Check if launcher script exists
echo "Step 1: Checking launcher script..."
echo "-----------------------------------"

if [ -f "$DASHBOARD_LAUNCHER" ]; then
    echo "✅ Launcher script exists: $DASHBOARD_LAUNCHER"
    echo "📝 Content:"
    echo "----------"
    cat "$DASHBOARD_LAUNCHER"
    echo "----------"
    echo "🔧 Permissions:"
    ls -la "$DASHBOARD_LAUNCHER"
else
    echo "❌ Launcher script NOT found: $DASHBOARD_LAUNCHER"
    echo ""
    echo "🛠️ CREATING BASIC LAUNCHER SCRIPT..."
    
    cat > "$DASHBOARD_LAUNCHER" << 'EOF'
#!/bin/bash
# Basic Spyder Dashboard Launcher

cd "/home/adam/Projects/Spyder"

# Activate virtual environment
source .venv/bin/activate

# Launch dashboard with error logging
echo "🚀 Launching Spyder Dashboard..."
echo "================================"

# Try different launch methods
echo "Method 1: SpyderG05_TradingDashboard..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    dashboard = SpyderTradingDashboard()
    dashboard.show()
    print('✅ Dashboard launched successfully!')
    app.exec()
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
except Exception as e:
    print(f'❌ Error: {e}')
    exit(1)
" 2>&1 | tee dashboard_launch.log

echo "Dashboard launch complete."
EOF
    
    chmod +x "$DASHBOARD_LAUNCHER"
    echo "✅ Created basic launcher script"
fi

echo ""
echo "Step 2: Checking Python modules..."
echo "----------------------------------"

cd "$SPYDER_HOME"
source .venv/bin/activate 2>/dev/null || echo "⚠️ Virtual environment not found"

echo "🐍 Python path:"
python3 -c "import sys; print('\n'.join(sys.path))"

echo ""
echo "📦 Checking key modules:"

# Check PyQt6
python3 -c "from PyQt6.QtWidgets import QApplication; print('✅ PyQt6 installed')" 2>/dev/null || echo "❌ PyQt6 not found"

# Check dashboard module
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
    print('✅ SpyderG05_TradingDashboard module found')
except ImportError as e:
    print(f'❌ Dashboard module not found: {e}')
    
    # Check what's in the SpyderG_GUI directory
    import os
    gui_dir = './SpyderG_GUI'
    if os.path.exists(gui_dir):
        print(f'📁 Files in {gui_dir}:')
        for f in os.listdir(gui_dir):
            if f.endswith('.py'):
                print(f'  📄 {f}')
    else:
        print(f'❌ Directory not found: {gui_dir}')
"

echo ""
echo "Step 3: Test dashboard launch manually..."
echo "----------------------------------------"

echo "🧪 Testing direct launch:"
python3 -c "
import sys
sys.path.insert(0, '.')

print('Testing dashboard import and launch...')

try:
    print('1. Importing PyQt6...')
    from PyQt6.QtWidgets import QApplication
    
    print('2. Importing dashboard...')
    from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
    
    print('3. Creating QApplication...')
    app = QApplication([])
    
    print('4. Creating dashboard...')
    dashboard = SpyderTradingDashboard()
    
    print('5. Showing dashboard...')
    dashboard.show()
    
    print('✅ Dashboard should be visible now!')
    print('   Check if a window appeared on your screen')
    
    # Don't run app.exec() in this test - just show it's working
    
except Exception as e:
    print(f'❌ Error during launch: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo "Step 4: Check desktop file configuration..."
echo "------------------------------------------"

DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"
echo "📄 Desktop file: $DESKTOP_FILE"

if [ -f "$DESKTOP_FILE" ]; then
    echo "Current Exec line:"
    grep "^Exec=" "$DESKTOP_FILE"
    
    echo ""
    echo "🧪 Test desktop file launch:"
    echo "Run this command manually:"
    echo "  $DASHBOARD_LAUNCHER"
else
    echo "❌ Desktop file not found!"
fi

echo ""
echo "Step 5: Alternative launch methods..."
echo "------------------------------------"

echo "If the above doesn't work, try these alternatives:"
echo ""
echo "🔧 Method 1 - Direct python launch:"
echo "cd $SPYDER_HOME && source .venv/bin/activate && python3 SpyderG_GUI/SpyderG05_TradingDashboard.py"
echo ""
echo "🔧 Method 2 - Via entry point:"
echo "cd $SPYDER_HOME && source .venv/bin/activate && python3 SpyderG_GUI/SpyderG02_GUIEntry.py"
echo ""
echo "🔧 Method 3 - Fast launcher:"
echo "cd $SPYDER_HOME && source .venv/bin/activate && python3 fast_launcher.py"

echo ""
echo "🎯 NEXT STEPS:"
echo "============="
echo "1. Run this script to see where the issue is"
echo "2. Try the manual launch methods above"
echo "3. Once you get a working method, we'll update the SPY icon"
echo "4. Then we'll get the correct WM_CLASS for that working dashboard"