#!/bin/bash
# SPYDER Dock Launcher - Shows connection selector by default

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# If connection selector exists, use it; otherwise show menu
if [[ -f "$SCRIPT_DIR/launch_connection_selector.py" ]]; then
    python3 "$SCRIPT_DIR/launch_connection_selector.py"
else
    # Fallback menu using zenity if available
    if command -v zenity >/dev/null 2>&1; then
        choice=$(zenity --list --title="SPYDER Trading System" \
            --text="Choose launch option:" \
            --column="Option" \
            "Tradier API (Default)" \
            "Test Connections" \
            --height=300 --width=400 2>/dev/null)

        case "$choice" in
            "Tradier API (Default)")
                "$SCRIPT_DIR/launch_dashboard_production.py"
                ;;
            "Test Connections")
                gnome-terminal -- "$SCRIPT_DIR/test_all_connections.sh" --full
                ;;
        esac
    else
        # Ultimate fallback - launch connection selector directly
        python3 "$SCRIPT_DIR/launch_connection_selector.py" || \
        gnome-terminal -- "$SCRIPT_DIR/launch_dashboard_production.py"
    fi
fi
