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
            --text="Choose connection method:" \
            --column="Option" \
            "IB Gateway (Local)" \
            "Remote TWS API" \
            "Test Connections" \
            --height=300 --width=400 2>/dev/null)

        case "$choice" in
            "IB Gateway (Local)")
                "$SCRIPT_DIR/launch_spyder_gateway.sh"
                ;;
            "Remote TWS API")
                "$SCRIPT_DIR/launch_spyder_tws.sh"
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
