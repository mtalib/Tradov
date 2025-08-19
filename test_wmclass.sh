#!/bin/bash
# WM_CLASS Fix Tester
echo "🧪 WM_CLASS FIX TESTER"
echo "=================="

DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"

# Test different WM_CLASS values
WM_CLASSES=("SPYDER" "spyder" "python3" "SpyderG05_TradingDashboard" "spyder-trading" "fast_launcher")

for wmclass in "${WM_CLASSES[@]}"; do
    echo "🔧 Testing WMClass: $wmclass"
    
    # Backup current file
    cp "$DESKTOP_FILE" "$DESKTOP_FILE.backup"
    
    # Update WMClass
    sed -i "s/^StartupWMClass=.*/StartupWMClass=$wmclass/" "$DESKTOP_FILE"
    
    # Update desktop database
    update-desktop-database ~/.local/share/applications/
    
    echo "   Updated to: StartupWMClass=$wmclass"
    echo "   Test your SPY icon now, then press Enter to try next..."
    read
done

echo "✅ Testing complete!"
