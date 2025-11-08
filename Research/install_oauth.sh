#!/bin/bash
# ==============================================================================
# SPYDER OAuth Integration - Installation Script
# ==============================================================================
# This script installs the OAuth authentication system and creates a desktop
# launcher that opens the Spyder Dashboard directly (no authentication window)
#
# Author: Mohamed Talib
# Date: 2025-10-24
# ==============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SPYDER_HOME="$HOME/Projects/Spyder"
VENV_PATH="$SPYDER_HOME/.venv"
DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"
CERT_DIR="$HOME/.spyder/certs"

# ==============================================================================
# Helper Functions
# ==============================================================================

print_header() {
    echo -e "${BLUE}"
    echo "=============================================================================="
    echo "$1"
    echo "=============================================================================="
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# ==============================================================================
# Installation Steps
# ==============================================================================

install_oauth_system() {
    print_header "SPYDER OAuth Authentication Installation"
    
    # Check if Spyder directory exists
    if [ ! -d "$SPYDER_HOME" ]; then
        print_error "Spyder directory not found at: $SPYDER_HOME"
        echo "Please update the SPYDER_HOME variable in this script"
        exit 1
    fi
    
    print_info "Spyder home: $SPYDER_HOME"
    
    # Step 1: Activate virtual environment
    print_info "Step 1: Activating virtual environment..."
    if [ ! -f "$VENV_PATH/bin/activate" ]; then
        print_error "Virtual environment not found at: $VENV_PATH"
        exit 1
    fi
    source "$VENV_PATH/bin/activate"
    print_success "Virtual environment activated"
    
    # Step 2: Install ibind with OAuth support
    print_info "Step 2: Installing ibind with OAuth support..."
    pip install 'ibind[oauth]'
    print_success "ibind[oauth] installed"
    
    # Step 3: Copy OAuth files
    print_info "Step 3: Copying OAuth authentication files..."
    
    # Copy auth manager
    if [ -f "SpyderB03_IBKRAuthManager.py" ]; then
        cp SpyderB03_IBKRAuthManager.py "$SPYDER_HOME/SpyderB_Broker/"
        print_success "SpyderB03_IBKRAuthManager.py copied"
    else
        print_warning "SpyderB03_IBKRAuthManager.py not found in current directory"
    fi
    
    # Copy OAuth setup dialog
    if [ -f "SpyderG06_OAuthSetupDialog.py" ]; then
        cp SpyderG06_OAuthSetupDialog.py "$SPYDER_HOME/SpyderG_GUI/"
        print_success "SpyderG06_OAuthSetupDialog.py copied"
    else
        print_warning "SpyderG06_OAuthSetupDialog.py not found in current directory"
    fi
    
    # Step 4: Create certificate directory
    print_info "Step 4: Creating certificate directory..."
    mkdir -p "$CERT_DIR"
    chmod 700 "$CERT_DIR"
    print_success "Certificate directory created: $CERT_DIR"
    
    # Step 5: Create desktop launcher
    print_info "Step 5: Creating desktop launcher..."
    create_desktop_launcher
    
    # Step 6: Display next steps
    print_header "Installation Complete! 🎉"
    echo ""
    echo "Next Steps:"
    echo ""
    echo "1. 📝 Modify SpyderG05_TradingDashboard.py"
    echo "   - Use the code snippets from OAUTH_CODE_SNIPPETS.md"
    echo "   - Or follow the guide in OAUTH_INTEGRATION_GUIDE.md"
    echo ""
    echo "2. 🔑 Get OAuth Credentials from IBKR:"
    echo "   - Visit: https://portal.interactivebrokers.com"
    echo "   - Settings → API → OAuth Apps"
    echo "   - Create OAuth Consumer Key"
    echo "   - Download certificates to: $CERT_DIR"
    echo ""
    echo "3. 🚀 Launch Spyder Dashboard:"
    echo "   - Click the Spyder icon in your applications"
    echo "   - Or run: $SPYDER_HOME/SpyderG_GUI/SpyderG05_TradingDashboard.py"
    echo ""
    echo "4. 🔐 Configure OAuth (First Time):"
    echo "   - Click '🔐 Authenticate' button in dashboard"
    echo "   - Follow the setup wizard"
    echo "   - Test connection"
    echo "   - Save credentials"
    echo ""
    echo "5. ✅ Subsequent Launches:"
    echo "   - Dashboard auto-authenticates"
    echo "   - Start trading immediately!"
    echo ""
}

create_desktop_launcher() {
    # Create desktop entry
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=SPYDER Trading
Comment=Autonomous Options Trading System - OAuth Authentication
Exec=$VENV_PATH/bin/python $SPYDER_HOME/SpyderG_GUI/SpyderG05_TradingDashboard.py
Icon=$SPYDER_HOME/assets/spyder_icon.png
Terminal=false
Categories=Finance;Trading;Development;
StartupNotify=true
Keywords=trading;options;stocks;finance;ibkr;
EOF
    
    # Make executable
    chmod +x "$DESKTOP_FILE"
    
    # Update desktop database
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
    fi
    
    print_success "Desktop launcher created: $DESKTOP_FILE"
    print_info "You can now find 'SPYDER Trading' in your applications menu"
}

create_default_icon() {
    # Create assets directory if it doesn't exist
    mkdir -p "$SPYDER_HOME/assets"
    
    # Create a simple text-based icon placeholder
    local icon_path="$SPYDER_HOME/assets/spyder_icon.png"
    if [ ! -f "$icon_path" ]; then
        print_info "Creating placeholder icon..."
        # Just create an empty file as placeholder
        touch "$icon_path"
        print_warning "Please replace $icon_path with your actual icon"
    fi
}

# ==============================================================================
# Main Execution
# ==============================================================================

main() {
    # Check if running from correct directory
    if [ ! -f "SpyderB03_IBKRAuthManager.py" ] || [ ! -f "SpyderG06_OAuthSetupDialog.py" ]; then
        print_warning "OAuth files not found in current directory"
        print_info "This script should be run from the directory containing:"
        print_info "  - SpyderB03_IBKRAuthManager.py"
        print_info "  - SpyderG06_OAuthSetupDialog.py"
        print_info ""
        read -p "Do you want to continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Run installation
    install_oauth_system
}

# Run main function
main "$@"
