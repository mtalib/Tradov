#!/bin/bash
#
# Setup script for IBAuto - IB Gateway Automation
# This script installs and configures the IBAuto launcher
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Paths
SPYDER_PATH="$HOME/Spyder"
DESKTOP_FILE="$HOME/.local/share/applications/ibautomater.desktop"
LAUNCHER_SCRIPT="$SPYDER_PATH/launch_ibautomater.sh"
VENV_PATH="$HOME/.venv"

echo -e "${BLUE}${BOLD}"
echo "============================================================"
echo "           IBAuto Setup - IB Gateway Automation            "
echo "============================================================"
echo -e "${NC}"

# Step 1: Check prerequisites
echo -e "${GREEN}Step 1:${NC} Checking prerequisites..."

if [ ! -d "$SPYDER_PATH" ]; then
    echo -e "${RED}Error:${NC} Spyder directory not found at $SPYDER_PATH"
    exit 1
fi

if [ ! -d "$HOME/Jts/ibgateway" ]; then
    echo -e "${YELLOW}Warning:${NC} IB Gateway not found at $HOME/Jts/ibgateway"
    echo "Please install IB Gateway first"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 2: Setup Python virtual environment
echo -e "${GREEN}Step 2:${NC} Setting up Python environment..."

if [ ! -d "$VENV_PATH" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"

echo "Installing required Python packages..."
pip install --quiet --upgrade pip
pip install --quiet --upgrade \
    pyautogui>=0.9.54 \
    opencv-python>=4.5.0 \
    pillow>=8.0.0 \
    psutil>=5.8.0 \
    numpy>=1.20.0 \
    ib-insync

echo -e "${GREEN}✓${NC} Python environment ready"

# Step 3: Create launcher script
echo -e "${GREEN}Step 3:${NC} Creating launcher script..."

if [ -f "$LAUNCHER_SCRIPT" ]; then
    echo -e "${YELLOW}Warning:${NC} Launcher script already exists"
    read -p "Overwrite? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping launcher script creation"
    else
        echo "Backing up existing launcher..."
        cp "$LAUNCHER_SCRIPT" "${LAUNCHER_SCRIPT}.backup.$(date +%Y%m%d_%H%M%S)"
    fi
fi

# The launcher script should already be created from the artifact above
# Just make it executable
if [ -f "$LAUNCHER_SCRIPT" ]; then
    chmod +x "$LAUNCHER_SCRIPT"
    echo -e "${GREEN}✓${NC} Launcher script ready"
else
    echo -e "${RED}Error:${NC} Launcher script not found. Please create launch_ibautomater.sh first"
    exit 1
fi

# Step 4: Create desktop entry
echo -e "${GREEN}Step 4:${NC} Creating desktop entry..."

mkdir -p "$HOME/.local/share/applications"

# Create desktop file
cat > "$DESKTOP_FILE" << 'EOF'
[Desktop Entry]
Type=Application
Version=1.0
Name=IBAuto
Comment=IB Gateway with Automated Login
GenericName=IB Gateway Automation
Keywords=trading;broker;gateway;ib;interactive;brokers;automation;

Exec=LAUNCHER_PATH --gui
Icon=ICON_PATH
Path=SPYDER_PATH

Terminal=false
StartupNotify=true
Categories=Finance;Network;Application;

Actions=Status;Stop;Terminal;

[Desktop Action Status]
Name=Check Status
Exec=LAUNCHER_PATH --status
Icon=dialog-information

[Desktop Action Stop]
Name=Stop Gateway
Exec=LAUNCHER_PATH --stop
Icon=process-stop

[Desktop Action Terminal]
Name=Open in Terminal
Exec=gnome-terminal --working-directory=SPYDER_PATH -- bash -c "source VENV_PATH/bin/activate; python3 SpyderI01_IBAutomaterFullIntegration.py; bash"
Icon=utilities-terminal
EOF

# Replace placeholders
sed -i "s|LAUNCHER_PATH|$LAUNCHER_SCRIPT|g" "$DESKTOP_FILE"
sed -i "s|SPYDER_PATH|$SPYDER_PATH|g" "$DESKTOP_FILE"
sed -i "s|VENV_PATH|$VENV_PATH|g" "$DESKTOP_FILE"

# Find and set icon
if [ -f "$HOME/Jts/ibgateway/1037/.install4j/ibgateway.png" ]; then
    ICON_PATH="$HOME/Jts/ibgateway/1037/.install4j/ibgateway.png"
elif [ -f "$HOME/Jts/ibgateway/1037/ibgateway.png" ]; then
    ICON_PATH="$HOME/Jts/ibgateway/1037/ibgateway.png"
else
    # Use a generic icon
    ICON_PATH="applications-finance"
fi
sed -i "s|ICON_PATH|$ICON_PATH|g" "$DESKTOP_FILE"

chmod +x "$DESKTOP_FILE"

echo -e "${GREEN}✓${NC} Desktop entry created"

# Step 5: Update desktop database
echo -e "${GREEN}Step 5:${NC} Updating desktop database..."
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

# Step 6: Create custom icon (optional)
echo -e "${GREEN}Step 6:${NC} Creating custom icon..."

ICON_DIR="$HOME/.local/share/icons"
mkdir -p "$ICON_DIR"

# Create a simple SVG icon if no IB icon exists
if [ ! -f "$ICON_PATH" ]; then
    cat > "$ICON_DIR/ibautomater.svg" << 'EOF'
<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <rect width="48" height="48" rx="8" fill="#1976D2"/>
  <text x="24" y="32" font-family="Arial" font-size="24" font-weight="bold" text-anchor="middle" fill="white">IB</text>
  <circle cx="38" cy="10" r="6" fill="#4CAF50"/>
  <text x="38" y="14" font-family="Arial" font-size="10" text-anchor="middle" fill="white">A</text>
</svg>
EOF
    
    # Update desktop file to use custom icon
    sed -i "s|ICON_PATH|$ICON_DIR/ibautomater.svg|g" "$DESKTOP_FILE"
    echo -e "${GREEN}✓${NC} Custom icon created"
fi

# Step 7: Setup credentials (optional)
echo -e "${GREEN}Step 7:${NC} Credential setup..."

CRED_FILE="$HOME/.spyder/ib_credentials.json"

if [ ! -f "$CRED_FILE" ]; then
    echo -e "${YELLOW}No credentials found.${NC}"
    read -p "Would you like to set up credentials now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$SPYDER_PATH"
        python3 << 'EOF'
import sys
from SpyderI01_IBAutomaterFullIntegration import SpyderIBAutomaterConfig, SpyderIBAutomater

config = SpyderIBAutomaterConfig()
automater = SpyderIBAutomater(config)
automater.setup_credentials()
EOF
    else
        echo "You can set up credentials later by running the launcher"
    fi
else
    echo -e "${GREEN}✓${NC} Credentials already configured"
fi

# Step 8: Add to favorites (instructions)
echo ""
echo -e "${BLUE}${BOLD}============================================================${NC}"
echo -e "${GREEN}${BOLD}Setup Complete!${NC}"
echo -e "${BLUE}${BOLD}============================================================${NC}"
echo ""
echo -e "${BOLD}To add IBAuto to your Ubuntu dock:${NC}"
echo "1. Press the Super key (Windows key) to open Activities"
echo "2. Type 'IBAuto' to search for the application"
echo "3. Right-click on the IBAuto icon when it appears"
echo "4. Select 'Add to Favorites' to pin it to the dock"
echo ""
echo -e "${BOLD}Alternative method:${NC}"
echo "1. Open the application by clicking on it"
echo "2. Right-click on its icon in the dock while it's running"
echo "3. Select 'Add to Favorites'"
echo ""
echo -e "${BOLD}To launch IBAuto:${NC}"
echo "• Click the IBAuto icon in the dock"
echo "• Or run: $LAUNCHER_SCRIPT"
echo ""
echo -e "${BOLD}Right-click menu options:${NC}"
echo "• Check Status - View gateway status"
echo "• Stop Gateway - Stop the running gateway"
echo "• Open in Terminal - Launch in terminal mode"
echo ""
echo -e "${GREEN}${BOLD}IBAuto is ready to use!${NC}"
