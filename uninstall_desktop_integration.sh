#!/bin/bash
# SPYDER Desktop Integration Uninstaller

echo "🗑️  Removing SPYDER desktop integration..."

# Remove desktop files
rm -f "$HOME/.local/share/applications/spyder-"*.desktop
echo "   Removed desktop files"

# Remove context menu entries
rm -f "$HOME/.local/share/file-manager/actions/spyder-trading.desktop"
echo "   Removed context menu entries"

# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    echo "   Updated desktop database"
fi

echo "✅ SPYDER desktop integration removed"
echo "   Launcher scripts in project directory remain available"
