#!/bin/bash
# Find the working Claude Flow desktop setup to replicate for Spyder

echo "🔍 FINDING CLAUDEFLOW SETUP TO REPLICATE"
echo "========================================"
echo "Let's analyze your working ClaudeFlow icon to copy its exact method."
echo ""

echo "Step 1: Finding ClaudeFlow desktop file"
echo "--------------------------------------"

# Search for ClaudeFlow desktop files
CLAUDE_FLOW_DESKTOP=""

# Common locations to check
DESKTOP_LOCATIONS=(
    "$HOME/.local/share/applications"
    "/usr/share/applications"
    "/usr/local/share/applications"
)

echo "🔍 Searching for ClaudeFlow desktop files..."

for location in "${DESKTOP_LOCATIONS[@]}"; do
    if [ -d "$location" ]; then
        echo "Checking: $location"
        
        # Look for files with Claude, Flow, claudeflow variations
        FOUND_FILES=$(find "$location" -name "*claude*" -o -name "*flow*" -o -name "*Claude*" -o -name "*Flow*" 2>/dev/null)
        
        if [ -n "$FOUND_FILES" ]; then
            echo "🎯 Found potential ClaudeFlow files:"
            echo "$FOUND_FILES"
            
            # Check each file for ClaudeFlow content (all variations)
            for file in $FOUND_FILES; do
                if grep -q -i "claudeflow\|claude.*flow\|flow.*claude\|claude-flow" "$file" 2>/dev/null; then
                    CLAUDE_FLOW_DESKTOP="$file"
                    echo "✅ Found ClaudeFlow desktop file: $file"
                    break
                fi
            done
        fi
    fi
done

if [ -z "$CLAUDE_FLOW_DESKTOP" ]; then
    echo "❌ ClaudeFlow desktop file not found in standard locations"
    echo ""
    echo "🔍 Let's search manually..."
    echo "Manual search methods:"
    echo "1. find $HOME -name '*claude*' -name '*.desktop' 2>/dev/null"
    echo "2. find $HOME -name '*flow*' -name '*.desktop' 2>/dev/null"
    echo "3. grep -r 'ClaudeFlow\|Claude Flow' $HOME/.local/share/applications/ 2>/dev/null"
    echo ""
    
    # Try broader search for all ClaudeFlow variations
    echo "🔍 Trying broader search for ClaudeFlow (all variations)..."
    BROAD_SEARCH=$(find $HOME -name "*.desktop" -exec grep -l -i "claudeflow\|claude.*flow\|flow.*claude\|claude-flow" {} \; 2>/dev/null)
    
    if [ -n "$BROAD_SEARCH" ]; then
        echo "🎯 Found via broad search:"
        echo "$BROAD_SEARCH"
        CLAUDE_FLOW_DESKTOP=$(echo "$BROAD_SEARCH" | head -1)
    fi
fi

if [ -n "$CLAUDE_FLOW_DESKTOP" ]; then
    echo ""
    echo "Step 2: Analyzing ClaudeFlow desktop file"
    echo "========================================="
    
    echo "📄 ClaudeFlow desktop file: $CLAUDE_FLOW_DESKTOP"
    echo ""
    echo "📋 Content analysis:"
    echo "-------------------"
    cat "$CLAUDE_FLOW_DESKTOP"
    
    echo ""
    echo "🔧 Key properties to copy:"
    echo "-------------------------"
    
    # Extract key properties
    NAME=$(grep "^Name=" "$CLAUDE_FLOW_DESKTOP" | cut -d'=' -f2-)
    EXEC=$(grep "^Exec=" "$CLAUDE_FLOW_DESKTOP" | cut -d'=' -f2-)
    ICON=$(grep "^Icon=" "$CLAUDE_FLOW_DESKTOP" | cut -d'=' -f2-)
    STARTUP_WM_CLASS=$(grep "^StartupWMClass=" "$CLAUDE_FLOW_DESKTOP" | cut -d'=' -f2-)
    CATEGORIES=$(grep "^Categories=" "$CLAUDE_FLOW_DESKTOP" | cut -d'=' -f2-)
    
    echo "✅ Name: $NAME"
    echo "✅ Exec: $EXEC"
    echo "✅ Icon: $ICON"
    echo "✅ StartupWMClass: $STARTUP_WM_CLASS"
    echo "✅ Categories: $CATEGORIES"
    
    echo ""
    echo "Step 3: Understanding the working pattern"
    echo "========================================"
    
    # Check if ClaudeFlow is currently running
    echo "🔍 Checking if ClaudeFlow is currently running..."
    
    if pgrep -f "claudeflow\|claude.*flow\|flow.*claude\|claude-flow" >/dev/null; then
        echo "✅ ClaudeFlow process found"
        echo "📊 Process details:"
        ps aux | grep -E "claudeflow|claude.*flow|flow.*claude|claude-flow" | grep -v grep
        
        echo ""
        echo "🎯 Getting actual WM_CLASS from running ClaudeFlow:"
        echo "Run this in another terminal:"
        echo "1. xprop WM_CLASS"
        echo "2. Click on ClaudeFlow window"
        echo "3. Note the WM_CLASS value"
        
    else
        echo "⚠️ ClaudeFlow not currently running"
        echo "To test the working pattern:"
        echo "1. Launch ClaudeFlow from dock"
        echo "2. Run: xprop WM_CLASS"
        echo "3. Click on ClaudeFlow window"
        echo "4. Compare with desktop file StartupWMClass"
    fi
    
    echo ""
    echo "Step 4: Creating Spyder desktop file using ClaudeFlow pattern"
    echo "==========================================================="
    
    # Create Spyder desktop file based on ClaudeFlow pattern
    SPYDER_DESKTOP="$HOME/.local/share/applications/spyder-trading.desktop"
    
    echo "📝 Creating new Spyder desktop file based on ClaudeFlow pattern..."
    
    # Backup existing
    if [ -f "$SPYDER_DESKTOP" ]; then
        cp "$SPYDER_DESKTOP" "$SPYDER_DESKTOP.before_claude_flow_method.$(date +%Y%m%d_%H%M%S)"
        echo "✅ Backed up existing Spyder desktop file"
    fi
    
    # Create new desktop file using ClaudeFlow as template
    cat > "$SPYDER_DESKTOP" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=SPYDER Trading Dashboard
Comment=SPY Options Trading System with GUI Dashboard
GenericName=SPY Trading

# Using ClaudeFlow pattern
Exec=/home/adam/Projects/Spyder/launch_dashboard_wayland.sh
Terminal=false
StartupNotify=true

# Copy StartupWMClass pattern from ClaudeFlow
StartupWMClass=${STARTUP_WM_CLASS:-python3}

# Icon and paths
Icon=/home/adam/Projects/Spyder/assets/spyder-icon.png
Path=/home/adam/Projects/Spyder

# Copy Categories pattern from ClaudeFlow
Categories=${CATEGORIES:-Application;Development;}

# Keywords
Keywords=trading;options;spy;spyder;stocks;market;dashboard;

# Actions (same as before)
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

    chmod +x "$SPYDER_DESKTOP"
    
    echo "✅ Created Spyder desktop file using ClaudeFlow pattern"
    
    # Update desktop database
    update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
    echo "✅ Updated desktop database"
    
    echo ""
    echo "Step 5: Testing the ClaudeFlow method"
    echo "===================================="
    
    echo "🧪 Now test the ClaudeFlow method:"
    echo ""
    echo "1. **Remove duplicate SPY icons:**"
    echo "   - Right-click both SPY icons → Remove from dock"
    echo "   - Clear the dock completely of SPY icons"
    echo ""
    echo "2. **Add fresh icon using Activities:**"
    echo "   - Press Super key"
    echo "   - Search 'SPYDER Trading'"
    echo "   - Right-click result → Add to Favorites"
    echo ""
    echo "3. **Test integration:**"
    echo "   - Click new SPY icon"
    echo "   - Should launch dashboard"
    echo "   - Should show orange dot UNDER SPY icon (not separate)"
    echo ""
    echo "🎯 If this works, the ClaudeFlow method is successful!"
    
else
    echo ""
    echo "❌ Could not find ClaudeFlow desktop file"
    echo ""
    echo "🔍 Alternative investigation methods:"
    echo "======================================"
    echo ""
    echo "1. **Manual search:**"
    echo "   cd ~/.local/share/applications"
    echo "   ls -la *claude* *flow* *Claude* *Flow*"
    echo ""
    echo "2. **Find by dock:**"
    echo "   - Right-click ClaudeFlow icon in dock"
    echo "   - Select Properties (if available)"
    echo "   - Note the command/exec path"
    echo ""
    echo "3. **Process inspection:**"
    echo "   - Launch ClaudeFlow"
    echo "   - Run: ps aux | grep -i 'claude\|flow'"
    echo "   - Note the exact command and parameters"
    echo ""
    echo "4. **Desktop search:**"
    echo "   find / -name '*.desktop' -exec grep -l 'ClaudeFlow\|claudeflow' {} \\; 2>/dev/null"
fi

echo ""
echo "📋 SUMMARY"
echo "=========="
echo "The goal is to find how ClaudeFlow achieves perfect dock integration"
echo "and replicate that exact method for Spyder to avoid duplicate icons."
echo ""
echo "Next steps based on findings above ⬆️"
