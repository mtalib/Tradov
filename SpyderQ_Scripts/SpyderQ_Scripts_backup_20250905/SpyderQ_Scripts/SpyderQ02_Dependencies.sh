#!/bin/bash
# =============================================================================
# SPYDER INSTALLATION SCRIPT (ENHANCED)
# Spyder Requirements Installation Script for Ubuntu
# =============================================================================

echo "🚀 Spyder Installation Script (Ubuntu - ENHANCED)"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to install with error handling
install_requirements() {
    local file=$1
    local description=$2
    
    print_status "Installing $description..."
    if pip install -r "$file"; then
        print_success "$description installed successfully"
    else
        print_error "Failed to install $description"
        read -p "Continue with other components? (y/N): " continue_install
        if [[ ! $continue_install =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    echo ""
}

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
print_status "Python version: $python_version"

# Check if we're in virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    print_warning "Not in a virtual environment"
    read -p "Continue anyway? (y/N): " continue_install
    if [[ ! $continue_install =~ ^[Yy]$ ]]; then
        print_status "Create virtual environment first:"
        echo "python3 -m venv .venv"
        echo "source .venv/bin/activate"
        exit 1
    fi
else
    print_success "Virtual environment detected: $VIRTUAL_ENV"
fi

# Check if requirements files exist
for req_file in requirements-core.txt requirements-trading.txt requirements-gui.txt requirements-ai.txt; do
    if [ ! -f "$req_file" ]; then
        print_error "Required file not found: $req_file"
        exit 1
    fi
done

print_success "All requirements files found"

# Installation options
echo ""
print_status "Choose installation type:"
echo "1. Full installation (all components)"
echo "2. Minimal (core + trading only)" 
echo "3. Custom (choose components)"
echo "4. Development (includes dev tools)"

read -p "Enter choice (1-4): " install_choice

case $install_choice in
    1)
        print_status "Installing all components..."
        install_requirements "requirements.txt" "All Components"
        ;;
    2)
        print_status "Installing minimal setup..."
        install_requirements "requirements-core.txt" "Core Dependencies"
        install_requirements "requirements-trading.txt" "Trading Dependencies"
        ;;
    3)
        print_status "Custom installation..."
        install_requirements "requirements-core.txt" "Core Dependencies (Required)"
        
        read -p "📈 Install trading components? (Y/n): " trading
        if [[ ! $trading =~ ^[Nn]$ ]]; then
            install_requirements "requirements-trading.txt" "Trading Dependencies"
        fi
        
        read -p "🖥️  Install GUI components? (y/N): " gui
        if [[ $gui =~ ^[Yy]$ ]]; then
            install_requirements "requirements-gui.txt" "GUI Dependencies (PyQt6)"
        fi
        
        read -p "🧠 Install AI/ML components? (y/N): " ai
        if [[ $ai =~ ^[Yy]$ ]]; then
            install_requirements "requirements-ai.txt" "AI/ML Dependencies"
        fi
        ;;
    4)
        print_status "Installing development environment..."
        install_requirements "requirements.txt" "All Components"
        install_requirements "requirements-dev.txt" "Development Tools"
        
        # Setup pre-commit hooks
        if command -v pre-commit &> /dev/null; then
            print_status "Setting up pre-commit hooks..."
            pre-commit install
            print_success "Pre-commit hooks installed"
        fi
        ;;
    *)
        print_error "Invalid choice"
        exit 1
        ;;
esac

print_success "🎉 Installation Complete!"
echo ""
print_status "🧪 Test your installation:"
echo "python -c 'import pandas, numpy, sqlalchemy; print(\"Core: OK\")'"
echo "python -c 'import ib_insync; print(\"Trading: OK\")'"
echo "python -c 'import PyQt6; print(\"GUI: OK\")'"
echo ""
print_status "🚀 Your Spyder system is ready!"
echo "Start with: python SpyderA_Core/SpyderA01_Main.py"
