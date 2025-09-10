#!/bin/bash
# ===============================================================================
# SPYDER DESKTOP LAUNCHER CLEANUP & SETUP SCRIPT
# FOR UBUNTU WAYLAND
# ===============================================================================
# This script removes all duplicate desktop launchers and creates one clean,
# properly configured desktop launcher for the Spyder Options Trading System
# ===============================================================================

set -e  # Exit on any error

echo "🧹 SPYDER DESKTOP LAUNCHER CLEANUP & SETUP"
echo "=========================================="
echo ""

# ===============================================================================
# STEP 1: BACKUP EXISTING DESKTOP FILES
# ===============================================================================
echo "📋 Step 1: Backing up existing desktop files..."
BACKUP_DIR="$HOME/.local/share/applications/spyder_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Find and backup existing spyder desktop files
existing_files=$(find ~/.local/share/applications/ -name "*spyder*" -o -name "*spy*" -name "*.desktop" 2>/dev/null || true)
if [ ! -z "$existing_files" ]; then
    echo "Found existing desktop files:"
    echo "$existing_files"
    echo ""
    echo "Backing up to: $BACKUP_DIR"
    
    for file in $existing_files; do
        if [ -f "$file" ]; then
            cp "$file" "$BACKUP_DIR/"
            echo "  ✅ Backed up: $(basename $file)"
        fi
    done
else
    echo "No existing Spyder desktop files found."
fi
echo ""

# ===============================================================================
# STEP 2: REMOVE DUPLICATE DESKTOP FILES
# ===============================================================================
echo "🗑️ Step 2: Removing old/duplicate desktop files..."
rm -f ~/.local/share/applications/spyder*.desktop 2>/dev/null || true
rm -f ~/.local/share/applications/*spy*.desktop 2>/dev/null || true
echo "✅ Cleaned up old desktop files"
echo ""

# ===============================================================================
# STEP 3: VERIFY PROJECT PATHS
# ===============================================================================
echo "🔍 Step 3: Verifying Spyder project paths..."

# Set project paths
PROJECT_ROOT="$HOME/Projects/Spyder"
MAIN_LAUNCHER="$PROJECT_ROOT/SpyderQ_Scripts/SpyderQ14_MainLauncher.py"
ICON_PATH="$PROJECT_ROOT/assets/spyder-icon.png"
VENV_PATH="$PROJECT_ROOT/.venv"

echo "Project root: $PROJECT_ROOT"
echo "Main launcher: $MAIN_LAUNCHER"
echo "Icon: $ICON_PATH"
echo "Virtual env: $VENV_PATH"
echo ""

# Check if main launcher exists
if [ ! -f "$MAIN_LAUNCHER" ]; then
    echo "❌ ERROR: Main launcher not found at $MAIN_LAUNCHER"
    echo "Please verify your Spyder project path and try again."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "⚠️ WARNING: Virtual environment not found at $VENV_PATH"
    echo "Creating virtual environment..."
    cd "$PROJECT_ROOT"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    # Add any required packages here
    echo "✅ Virtual environment created"
fi

# Check if icon exists, create a simple one if not
if [ ! -f "$ICON_PATH" ]; then
    echo "⚠️ WARNING: Icon not found at $ICON_PATH"
    echo "Creating icon directory..."
    mkdir -p "$(dirname $ICON_PATH)"
    
    # Create a simple SVG icon and convert to PNG if possible
    cat > "${ICON_PATH%.png}.svg" << 'EOF'
<svg width="64" height="64" xmlns="http://www.w3.org/2000/svg">
  <rect width="64" height="64" fill="#1a237e"/>
  <text x="32" y="38" text-anchor="middle" fill="white" font-size="24" font-family="monospace">S</text>
  <text x="32" y="52" text-anchor="middle" fill="#00e676" font-size="8" font-family="monospace">SPYDER</text>
</svg>
EOF
    
    # Try to convert SVG to PNG using available tools
    if command -v convert >/dev/null 2>&1; then
        convert "${ICON_PATH%.png}.svg" "$ICON_PATH" 2>/dev/null || true
    elif command -v inkscape >/dev/null 2>&1; then
        inkscape "${ICON_PATH%.png}.svg" --export-type=png --export-filename="$ICON_PATH" 2>/dev/null || true
    else
        # Use the SVG as icon
        ICON_PATH="${ICON_PATH%.png}.svg"
    fi
    
    echo "✅ Created icon at $ICON_PATH"
fi
echo ""

# ===============================================================================
# STEP 4: CREATE SINGLE CLEAN DESKTOP LAUNCHER
# ===============================================================================
echo "🚀 Step 4: Creating single desktop launcher..."

DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading-system.desktop"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Spyder Options Trading System
Comment=Autonomous SPY Options Trading Platform
GenericName=Options Trading System
Keywords=trading;options;spy;finance;spyder;
Icon=$ICON_PATH
Exec=bash -c 'cd $PROJECT_ROOT && source .venv/bin/activate && python SpyderQ_Scripts/SpyderQ14_MainLauncher.py --mode paper --gui'
Terminal=false
StartupNotify=true
Categories=Office;Finance;Development;
MimeType=text/x-python;
Actions=PaperMode;LiveMode;Dashboard;Status;

[Desktop Action PaperMode]
Name=Start Paper Trading
Exec=bash -c 'cd $PROJECT_ROOT && source .venv/bin/activate && python SpyderQ_Scripts/SpyderQ14_MainLauncher.py --mode paper --gui'

[Desktop Action LiveMode]
Name=Start Live Trading
Exec=bash -c 'cd $PROJECT_ROOT && source .venv/bin/activate && python SpyderQ_Scripts/SpyderQ14_MainLauncher.py --mode live --gui'

[Desktop Action Dashboard]
Name=Dashboard Only
Exec=bash -c 'cd $PROJECT_ROOT && source .venv/bin/activate && python SpyderQ_Scripts/SpyderQ14_MainLauncher.py --module SpyderG05_TradingDashboard'

[Desktop Action Status]
Name=System Status
Exec=bash -c 'cd $PROJECT_ROOT && source .venv/bin/activate && python SpyderQ_Scripts/SpyderQ14_MainLauncher.py --status'
EOF

# Make desktop file executable
chmod +x "$DESKTOP_FILE"

echo "✅ Created desktop launcher: $DESKTOP_FILE"
echo ""

# ===============================================================================
# STEP 5: WAYLAND-SPECIFIC OPTIMIZATIONS
# ===============================================================================
echo "🖥️ Step 5: Applying Wayland optimizations..."

# Create a Wayland-optimized launcher script
LAUNCHER_SCRIPT="$PROJECT_ROOT/spyder_wayland_launcher.sh"
cat > "$LAUNCHER_SCRIPT" << 'EOF'
#!/bin/bash
# Spyder Wayland Launcher Script
# Optimized for Ubuntu Wayland environment

# Set Wayland-specific environment variables
export QT_QPA_PLATFORM=wayland
export QT_WAYLAND_FORCE_DPI=96
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export QT_SCALE_FACTOR=1

# Set project root
PROJECT_ROOT="$HOME/Projects/Spyder"
cd "$PROJECT_ROOT"

# Activate virtual environment
source .venv/bin/activate

# Parse arguments or use defaults
MODE="${1:-paper}"
GUI="${2:---gui}"

echo "🚀 Starting Spyder Options Trading System"
echo "Mode: $MODE"
echo "GUI: $GUI"
echo ""

# Launch with proper Wayland settings
python SpyderQ_Scripts/SpyderQ14_MainLauncher.py --mode "$MODE" $GUI
EOF

chmod +x "$LAUNCHER_SCRIPT"

echo "✅ Created Wayland launcher: $LAUNCHER_SCRIPT"
echo ""

# ===============================================================================
# STEP 6: UPDATE DESKTOP DATABASE
# ===============================================================================
echo "🔄 Step 6: Updating desktop database..."
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
echo "✅ Desktop database updated"
echo ""

# ===============================================================================
# STEP 7: VERIFICATION
# ===============================================================================
echo "✅ SETUP COMPLETE!"
echo "=================="
echo ""
echo "📋 Summary:"
echo "  • Removed duplicate desktop files (backed up to: $BACKUP_DIR)"
echo "  • Created single desktop launcher: $(basename $DESKTOP_FILE)"
echo "  • Created Wayland-optimized launcher: $LAUNCHER_SCRIPT"
echo "  • Updated desktop database"
echo ""
echo "🚀 You can now launch Spyder by:"
echo "  1. Searching 'Spyder' in your applications menu"
echo "  2. Right-clicking the launcher for different modes"
echo "  3. Running directly: $LAUNCHER_SCRIPT"
echo ""
echo "🔧 Available launcher modes:"
echo "  • Paper Trading (default): $LAUNCHER_SCRIPT paper --gui"
echo "  • Live Trading: $LAUNCHER_SCRIPT live --gui"
echo "  • Headless: $LAUNCHER_SCRIPT paper --headless"
echo "  • Status Check: $LAUNCHER_SCRIPT status"
echo ""

# Show the new desktop file
echo "📄 Your new desktop launcher configuration:"
echo "----------------------------------------"
cat "$DESKTOP_FILE"
