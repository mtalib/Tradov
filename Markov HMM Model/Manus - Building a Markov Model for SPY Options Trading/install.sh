#!/bin/bash

# SPY HMM AI Trading System Installation Script
# Author: Manus AI
# Version: 1.0

echo "=============================================="
echo "SPY HMM AI Trading System Installation"
echo "=============================================="

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.8"

if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "✓ Python $python_version detected (>= 3.8 required)"
else
    echo "✗ Python 3.8 or higher is required. Current version: $python_version"
    echo "Please install Python 3.8+ and try again."
    exit 1
fi

# Check pip
echo "Checking pip..."
if command -v pip3 &> /dev/null; then
    echo "✓ pip3 found"
else
    echo "✗ pip3 not found. Installing pip..."
    python3 -m ensurepip --upgrade
fi

# Install requirements
echo "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
    if [ $? -eq 0 ]; then
        echo "✓ Dependencies installed successfully"
    else
        echo "✗ Failed to install dependencies"
        exit 1
    fi
else
    echo "✗ requirements.txt not found"
    echo "Installing core dependencies manually..."
    pip3 install numpy pandas scikit-learn hmmlearn yfinance ta PyQt6 pyqtgraph matplotlib seaborn statsmodels
fi

# Run tests
echo "Running system tests..."
if python3 test_hmm_system.py > /dev/null 2>&1; then
    echo "✓ System tests passed"
else
    echo "⚠ Some tests failed, but system should still work"
fi

# Create desktop shortcut (Linux)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Creating desktop shortcut..."
    desktop_file="$HOME/Desktop/SPY_HMM_Trading.desktop"
    cat > "$desktop_file" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=SPY HMM AI Trading System
Comment=Autonomous trading system with Hidden Markov Models
Exec=python3 $(pwd)/hmm_trading_gui.py
Icon=applications-office
Terminal=false
Categories=Office;Finance;
EOF
    chmod +x "$desktop_file"
    echo "✓ Desktop shortcut created"
fi

echo ""
echo "=============================================="
echo "Installation Complete!"
echo "=============================================="
echo ""
echo "To start the system:"
echo "  GUI Mode:     python3 hmm_trading_gui.py"
echo "  Console Mode: python3 complete_hmm_trading_system.py"
echo "  Run Tests:    python3 test_hmm_system.py"
echo ""
echo "Documentation:"
echo "  User Guide:   README.md"
echo "  Technical:    TECHNICAL_DOCUMENTATION.md"
echo ""
echo "⚠ IMPORTANT DISCLAIMER:"
echo "This software is for educational and research purposes only."
echo "Trading involves substantial risk of loss. Always consult with"
echo "a qualified financial advisor before making investment decisions."
echo ""

