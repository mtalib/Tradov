#!/bin/bash
# ==============================================================================
# SPYDER LAUNCHER DIAGNOSTIC AND FIX SCRIPT
# 
# This script diagnoses and fixes issues with the Spyder launcher
# Run this to troubleshoot why the SPY icon isn't working
# ==============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  SPYDER LAUNCHER DIAGNOSTIC & FIX${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ==============================================================================
# STEP 1: Find Spyder Installation
# ==============================================================================
echo -e "${YELLOW}[1] Checking Spyder installation location...${NC}"

# Try common locations
POSSIBLE_PATHS=(
    "$HOME/Projects/Spyder"
    "$HOME/Spyder"
    "/home/adam/Projects/Spyder"
    "/home/adam/Spyder"
    "$(pwd)"
)

SPYDER_HOME=""
for path in "${POSSIBLE_PATHS[@]}"; do
    if [ -d "$path" ] && [ -f "$path/SpyderA_Core/SpyderA01_Main.py" ]; then
        SPYDER_HOME="$path"
        echo -e "${GREEN}✓ Found Spyder at: $SPYDER_HOME${NC}"
        break
    fi
done

if [ -z "$SPYDER_HOME" ]; then
    echo -e "${RED}✗ Could not find Spyder installation${NC}"
    echo "Please specify the Spyder directory:"
    read -p "Enter path: " SPYDER_HOME
    if [ ! -d "$SPYDER_HOME" ]; then
        echo -e "${RED}Directory does not exist!${NC}"
        exit 1
    fi
fi

# ==============================================================================
# STEP 2: Check Virtual Environment
# ==============================================================================
echo ""
echo -e "${YELLOW}[2] Checking Python virtual environment...${NC}"

VENV_PATHS=(
    "$SPYDER_HOME/.venv"
    "$SPYDER_HOME/venv"
    "$SPYDER_HOME/spyder_venv"
    "$HOME/.virtualenvs/spyder"
)

VENV_PATH=""
for path in "${VENV_PATHS[@]}"; do
    if [ -d "$path" ] && [ -f "$path/bin/python" ]; then
        VENV_PATH="$path"
        echo -e "${GREEN}✓ Found venv at: $VENV_PATH${NC}"
        break
    fi
done

if [ -z "$VENV_PATH" ]; then
    echo -e "${YELLOW}⚠ No virtual environment found${NC}"
    echo "Would you like to create one? (y/n)"
    read -p "> " create_venv
    if [ "$create_venv" = "y" ]; then
        echo "Creating virtual environment..."
        python3 -m venv "$SPYDER_HOME/.venv"
        VENV_PATH="$SPYDER_HOME/.venv"
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    fi
fi

# ==============================================================================
# STEP 3: Check Startup Scripts
# ==============================================================================
echo ""
echo -e "${YELLOW}[3] Checking startup scripts...${NC}"

# Check for main startup script
STARTUP_SCRIPT=""
if [ -f "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh" ]; then
    STARTUP_SCRIPT="$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh"
    echo -e "${GREEN}✓ Found SpyderQ10_StartAll.sh${NC}"
elif [ -f "$SPYDER_HOME/scripts/start_spyder.sh" ]; then
    STARTUP_SCRIPT="$SPYDER_HOME/scripts/start_spyder.sh"
    echo -e "${GREEN}✓ Found start_spyder.sh${NC}"
else
    echo -e "${YELLOW}⚠ No startup script found, will create one${NC}"
fi

# ==============================================================================
# STEP 4: Check Desktop Launcher
# ==============================================================================
echo ""
echo -e "${YELLOW}[4] Checking desktop launcher...${NC}"

DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"
if [ -f "$DESKTOP_FILE" ]; then
    echo -e "${GREEN}✓ Desktop file exists${NC}"
    echo "Current content:"
    grep "Exec=" "$DESKTOP_FILE"
else
    echo -e "${YELLOW}⚠ Desktop file not found${NC}"
fi

# ==============================================================================
# STEP 5: Create/Fix Launcher Script
# ==============================================================================
echo ""
echo -e "${YELLOW}[5] Creating/Fixing launcher script...${NC}"

# Create the main launcher script
LAUNCHER_SCRIPT="$SPYDER_HOME/launch_spyder.sh"
cat > "$LAUNCHER_SCRIPT" << EOF
#!/bin/bash
# ==============================================================================
# SPYDER LAUNCHER SCRIPT
# Generated on: $(date)
# ==============================================================================

# Configuration
export SPYDER_HOME="$SPYDER_HOME"
VENV_PATH="$VENV_PATH"
LOG_FILE="\$SPYDER_HOME/logs/launcher.log"

# Create log directory if needed
mkdir -p "\$SPYDER_HOME/logs"

# Function to log messages
log_message() {
    echo "[\$(date '+%Y-%m-%d %H:%M:%S')] \$1" >> "\$LOG_FILE"
    echo "\$1"
}

# Start logging
log_message "========================================="
log_message "Starting Spyder Trading System"
log_message "SPYDER_HOME: \$SPYDER_HOME"
log_message "VENV_PATH: \$VENV_PATH"

# Change to Spyder directory
cd "\$SPYDER_HOME" || {
    log_message "ERROR: Cannot change to Spyder directory"
    exit 1
}

# Activate virtual environment if it exists
if [ -n "\$VENV_PATH" ] && [ -f "\$VENV_PATH/bin/activate" ]; then
    log_message "Activating virtual environment..."
    source "\$VENV_PATH/bin/activate"
else
    log_message "WARNING: No virtual environment, using system Python"
fi

# Check if IB Gateway is running (optional)
if pgrep -x "java" > /dev/null && pgrep -f "ibgateway" > /dev/null; then
    log_message "IB Gateway is running"
else
    log_message "WARNING: IB Gateway may not be running"
    echo "IB Gateway doesn't appear to be running."
    echo "Would you like to continue anyway? (y/n)"
    read -p "> " continue_anyway
    if [ "\$continue_anyway" != "y" ]; then
        exit 0
    fi
fi

# Launch Spyder based on available method
log_message "Launching Spyder..."

# Method 1: Try the main Python script
if [ -f "\$SPYDER_HOME/SpyderA_Core/SpyderA01_Main.py" ]; then
    log_message "Starting via SpyderA01_Main.py..."
    python "\$SPYDER_HOME/SpyderA_Core/SpyderA01_Main.py" --gui 2>&1 | tee -a "\$LOG_FILE"
    
# Method 2: Try the Q-Script
elif [ -f "\$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh" ]; then
    log_message "Starting via SpyderQ10_StartAll.sh..."
    bash "\$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh" 2>&1 | tee -a "\$LOG_FILE"
    
# Method 3: Try the launcher Python script
elif [ -f "\$SPYDER_HOME/SpyderQ_Scripts/SpyderQ14_MainLauncher.py" ]; then
    log_message "Starting via SpyderQ14_MainLauncher.py..."
    python "\$SPYDER_HOME/SpyderQ_Scripts/SpyderQ14_MainLauncher.py" --gui 2>&1 | tee -a "\$LOG_FILE"
    
else
    log_message "ERROR: No suitable startup method found!"
    echo "ERROR: Could not find a way to start Spyder"
    echo "Please check your installation"
    exit 1
fi

log_message "Spyder launcher finished"
EOF

chmod +x "$LAUNCHER_SCRIPT"
echo -e "${GREEN}✓ Created launcher script: $LAUNCHER_SCRIPT${NC}"

# ==============================================================================
# STEP 6: Create/Update Desktop File
# ==============================================================================
echo ""
echo -e "${YELLOW}[6] Creating/Updating desktop launcher...${NC}"

mkdir -p "$HOME/.local/share/applications"

# Find or create icon
ICON_PATH="$SPYDER_HOME/assets/spyder-icon.png"
if [ ! -f "$ICON_PATH" ]; then
    ICON_PATH="$SPYDER_HOME/assets/spy-icon.png"
fi
if [ ! -f "$ICON_PATH" ]; then
    ICON_PATH="applications-python"  # Use system icon as fallback
fi

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Spyder Trading System
Comment=Autonomous SPY Options Trading System
Icon=$ICON_PATH
Exec=$LAUNCHER_SCRIPT
Path=$SPYDER_HOME
Terminal=true
Categories=Finance;Application;
Keywords=trading;options;spy;finance;stocks;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"
echo -e "${GREEN}✓ Created desktop file: $DESKTOP_FILE${NC}"

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null
fi

# ==============================================================================
# STEP 7: Create Command Line Alias
# ==============================================================================
echo ""
echo -e "${YELLOW}[7] Creating command line alias...${NC}"

ALIAS_LINE="alias spyder='$LAUNCHER_SCRIPT'"
if ! grep -q "$ALIAS_LINE" "$HOME/.bashrc"; then
    echo "$ALIAS_LINE" >> "$HOME/.bashrc"
    echo -e "${GREEN}✓ Added 'spyder' alias to ~/.bashrc${NC}"
else
    echo -e "${GREEN}✓ Alias already exists${NC}"
fi

# ==============================================================================
# STEP 8: Test the Launcher
# ==============================================================================
echo ""
echo -e "${YELLOW}[8] Testing launcher...${NC}"

# Test if Python can import Spyder modules
if [ -n "$VENV_PATH" ] && [ -f "$VENV_PATH/bin/python" ]; then
    PYTHON_CMD="$VENV_PATH/bin/python"
else
    PYTHON_CMD="python3"
fi

echo "Testing Python imports..."
$PYTHON_CMD -c "
import sys
sys.path.insert(0, '$SPYDER_HOME')
try:
    from SpyderA_Core import SpyderA01_Main
    print('✓ Can import SpyderA01_Main')
except ImportError as e:
    print(f'✗ Cannot import SpyderA01_Main: {e}')
    
try:
    from SpyderG_GUI import SpyderG01_MainWindow
    print('✓ Can import SpyderG01_MainWindow')
except ImportError as e:
    print(f'✗ Cannot import SpyderG01_MainWindow: {e}')
"

# ==============================================================================
# SUMMARY
# ==============================================================================
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  DIAGNOSTIC COMPLETE${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}✓ Configuration Summary:${NC}"
echo "  • Spyder Home: $SPYDER_HOME"
echo "  • Virtual Env: $VENV_PATH"
echo "  • Launcher Script: $LAUNCHER_SCRIPT"
echo "  • Desktop File: $DESKTOP_FILE"
echo ""
echo -e "${GREEN}✓ Next Steps:${NC}"
echo "  1. Reload your desktop (Alt+F2, type 'r', press Enter)"
echo "  2. The SPY icon should now work"
echo "  3. Or run from terminal: spyder"
echo "  4. Or run directly: $LAUNCHER_SCRIPT"
echo ""
echo -e "${YELLOW}If the launcher still doesn't work:${NC}"
echo "  • Check the log file: $SPYDER_HOME/logs/launcher.log"
echo "  • Make sure IB Gateway is running"
echo "  • Verify Python dependencies are installed"
echo ""

# Ask if user wants to test launch now
echo -e "${YELLOW}Would you like to test the launcher now? (y/n)${NC}"
read -p "> " test_now
if [ "$test_now" = "y" ]; then
    echo "Launching Spyder..."
    "$LAUNCHER_SCRIPT"
fi
