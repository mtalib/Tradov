#!/bin/bash
# Find and fix duplicate SPY desktop files

echo "🔍 FINDING ALL SPY DESKTOP FILES"
echo "==============================="
echo "This explains the duplicate icons and separate gears!"
echo ""

echo "Step 1: Finding all SPY/Spyder desktop files"
echo "--------------------------------------------"

# Search for all Spyder-related desktop files
ALL_SPY_DESKTOPS=""

# Search in common locations
SEARCH_LOCATIONS=(
    "$HOME/.local/share/applications"
    "/usr/share/applications"
    "/usr/local/share/applications"
    "/var/lib/snapd/desktop/applications"
)

echo "🔍 Searching for all Spyder/SPY desktop files..."

for location in "${SEARCH_LOCATIONS[@]}"; do
    if [ -d "$location" ]; then
        echo "Checking: $location"
        
        # Look for any files with spy, spyder, or SPY in name or content
        FOUND_FILES=$(find "$location" -name "*spy*" -o -name "*spyder*" -o -name "*SPY*" -o -name "*Spyder*" 2>/dev/null)
        
        if [ -n "$FOUND_FILES" ]; then
            echo "🎯 Found files:"
            for file in $FOUND_FILES; do
                echo "  📄 $file"
                ALL_SPY_DESKTOPS="$ALL_SPY_DESKTOPS $file"
            done
        fi
        
        # Also search file contents for Spyder/SPY
        CONTENT_MATCHES=$(grep -l -i "spyder\|spy.*trading\|spy.*options" "$location"/*.desktop 2>/dev/null | head -5)
        if [ -n "$CONTENT_MATCHES" ]; then
            echo "🎯 Found by content:"
            for file in $CONTENT_MATCHES; do
                echo "  📄 $file"
                if [[ "$ALL_SPY_DESKTOPS" != *"$file"* ]]; then
                    ALL_SPY_DESKTOPS="$ALL_SPY_DESKTOPS $file"
                fi
            done
        fi
    fi
done

echo ""
echo "Step 2: Analyzing all found desktop files"
echo "========================================="

if [ -n "$ALL_SPY_DESKTOPS" ]; then
    echo "📋 COMPLETE LIST OF SPY DESKTOP FILES:"
    echo "======================================"
    
    i=1
    for desktop_file in $ALL_SPY_DESKTOPS; do
        if [ -f "$desktop_file" ]; then
            echo ""
            echo "🔍 File #$i: $desktop_file"
            echo "----------------------------------------"
            
            # Extract key information
            NAME=$(grep "^Name=" "$desktop_file" | cut -d'=' -f2- | head -1)
            EXEC=$(grep "^Exec=" "$desktop_file" | cut -d'=' -f2- | head -1)
            COMMENT=$(grep "^Comment=" "$desktop_file" | cut -d'=' -f2- | head -1)
            STARTUP_WM_CLASS=$(grep "^StartupWMClass=" "$desktop_file" | cut -d'=' -f2- | head -1)
            
            echo "📝 Name: $NAME"
            echo "🚀 Exec: $EXEC"
            echo "💬 Comment: $COMMENT"
            echo "🔧 StartupWMClass: $STARTUP_WM_CLASS"
            echo "📍 Location: $desktop_file"
            
            i=$((i+1))
        fi
    done
    
    echo ""
    echo "Step 3: Identifying the problem"
    echo "=============================="
    echo "🎯 You have MULTIPLE SPY desktop files - this causes:"
    echo "   ❌ Duplicate icons in Applications view"
    echo "   ❌ Separate gear icons in dock"
    echo "   ❌ Confusion about which one to pin"
    echo ""
    
    echo "Step 4: Recommended action"
    echo "========================="
    echo ""
    echo "🧪 TESTING APPROACH:"
    echo "1. **Launch each one individually** to see which works best"
    echo "2. **Keep only the working one**"
    echo "3. **Remove or rename the others**"
    echo ""
    
    i=1
    for desktop_file in $ALL_SPY_DESKTOPS; do
        if [ -f "$desktop_file" ]; then
            EXEC_COMMAND=$(grep "^Exec=" "$desktop_file" | cut -d'=' -f2-)
            echo "🧪 Test #$i: $desktop_file"
            echo "   Command: $EXEC_COMMAND"
            echo "   Test: gtk-launch $(basename "$desktop_file" .desktop)"
            echo ""
            i=$((i+1))
        fi
    done
    
    echo "Step 5: Clean up duplicates"
    echo "=========================="
    echo ""
    echo "After testing, choose the BEST working desktop file, then:"
    echo ""
    
    i=1
    for desktop_file in $ALL_SPY_DESKTOPS; do
        if [ -f "$desktop_file" ]; then
            echo "🗑️  Option $i: Remove $(basename "$desktop_file")"
            echo "    rm \"$desktop_file\""
            echo ""
            i=$((i+1))
        fi
    done
    
    echo "🎯 RECOMMENDED STEPS:"
    echo "===================="
    echo "1. **Test each desktop file** using the gtk-launch commands above"
    echo "2. **Choose the one that launches dashboard correctly**"
    echo "3. **Remove the other desktop files**"
    echo "4. **Update desktop database**: update-desktop-database ~/.local/share/applications/"
    echo "5. **Add to dock**: Super key → Search → Add to Favorites"
    echo ""
    echo "This will eliminate the duplicate icons and fix the dock integration!"
    
else
    echo "❌ No SPY desktop files found"
    echo "This is strange - if icons appear in Applications, desktop files must exist"
    echo ""
    echo "🔍 Alternative search:"
    echo "find /usr -name '*.desktop' -exec grep -l 'SPY\|Spyder' {} \\; 2>/dev/null"
    echo "find $HOME -name '*.desktop' -exec grep -l 'SPY\|Spyder' {} \\; 2>/dev/null"
fi

echo ""
echo "📋 SUMMARY"
echo "=========="
echo "Multiple desktop files = Multiple icons = Dock confusion"
echo "Solution: Keep only ONE working desktop file"
