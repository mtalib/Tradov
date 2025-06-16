#!/bin/bash
# SPYDER Trading System - Ubuntu Setup Script
# This script sets up the complete environment for Spyder on Ubuntu

echo "======================================"
echo "SPYDER Trading System Setup"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if running on Ubuntu
if ! grep -q "Ubuntu" /etc/os-release; then
    print_error "This script is designed for Ubuntu. Detected: $(lsb_release -d)"
    exit 1
fi

print_status "Ubuntu detected: $(lsb_release -d)"

# Update system packages
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install system dependencies
print_status "Installing system dependencies..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libssl-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    git \
    curl \
    wget

# Install TA-Lib dependencies (required for technical analysis)
print_status "Installing TA-Lib dependencies..."
sudo apt install -y \
    gcc \
    make \
    wget \
    tar

# Download and install TA-Lib
print_status "Installing TA-Lib library..."
cd /tmp
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
cd ~/

# Install PyQt5 system dependencies
print_status "Installing PyQt5 dependencies..."
sudo apt install -y \
    python3-pyqt5 \
    pyqt5-dev-tools \
    qttools5-dev-tools \
    libqt5designer5 \
    libqt5help5 \
    python3-pyqt5.qtwebengine

# Install additional libraries for notifications
print_status "Installing notification dependencies..."
sudo apt install -y \
    libnotify-bin \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-notify-0.7

# Create project directory
print_status "Creating project directory..."
PROJECT_DIR="$HOME/spyder-trading"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Create directory structure
print_status "Creating project structure..."
mkdir -p {logs,data,reports/{daily,risk,backtest},config,models,sounds,templates/{email,report}}

# Create subdirectories for each module group
for group in A_Core B_Broker C_MarketData D_Strategies E_Risk F_Analysis G_GUI H_Storage I_Backtest J_Alerts K_Reports L_ML U_Utilities T_Tests Z_Temp; do
    mkdir -p "Spyder${group}"
done

# Create Python virtual environment
print_status "Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install Python dependencies
print_status "Installing Python dependencies..."
# Create requirements.txt if it doesn't exist
if [ ! -f requirements.txt ]; then
    cat > requirements.txt << 'EOF'
# Core Dependencies
numpy==1.24.3
pandas==2.0.3
matplotlib==3.7.2
seaborn==0.12.2
scipy==1.11.1

# PyQt5 for GUI
PyQt5==5.15.9
PyQt5-Qt5==5.15.2
PyQt5-sip==12.12.1

# Interactive Brokers API
ib_insync==0.9.86

# Technical Analysis
ta-lib==0.4.28
pandas-ta==0.3.14b0

# Machine Learning
scikit-learn==1.3.0
optuna==3.3.0
arch==6.1.0
empyrical==0.5.5

# Genetic Algorithm
deap==1.4.1

# Email and Validation
email-validator==2.0.0.post2
jinja2==3.1.2

# PDF Generation
reportlab==4.0.4
Pillow==10.0.0

# Excel Support
openpyxl==3.1.2
xlsxwriter==3.1.2

# Desktop Notifications
plyer==2.1.0

# Encryption
cryptography==41.0.3

# Additional Utilities
python-dateutil==2.8.2
pytz==2023.3
requests==2.31.0
pyyaml==6.0.1
python-dotenv==1.0.0

# Development Tools
black==23.7.0
flake8==6.1.0
pytest==7.4.0
pytest-cov==4.1.0

# Logging enhancements
colorlog==6.7.0

# Performance monitoring
psutil==5.9.5
EOF
fi

pip install -r requirements.txt

# Create .env file for environment variables
print_status "Creating environment configuration..."
cat > .env << 'EOF'
# SPYDER Trading System Configuration

# Environment
ENVIRONMENT=development
TRADING_MODE=paper  # paper or live

# Interactive Brokers Configuration
IB_HOST=127.0.0.1
IB_PORT=7497  # 7497 for paper trading, 7496 for live trading
IB_CLIENT_ID=1

# Database
DATABASE_PATH=./data/spyder.db
BACKUP_PATH=./data/backups/

# Logging
LOG_LEVEL=INFO
LOG_PATH=./logs/

# Email Configuration (update with your settings)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=Spyder Trading System <your_email@gmail.com>

# Notifications
ENABLE_EMAIL_NOTIFICATIONS=true
ENABLE_DESKTOP_NOTIFICATIONS=true

# Risk Management
MAX_DAILY_LOSS=1000
MAX_POSITION_SIZE=0.20
MAX_MARGIN_USAGE=0.70

# Performance
ENABLE_PERFORMANCE_MONITORING=true
CACHE_ENABLED=true
EOF

# Create main configuration file
print_status "Creating main configuration file..."
cat > config/robola_config.yaml << 'EOF'
# SPYDER Trading System Configuration

system:
  name: "Spyder Trading System"
  version: "1.0.0"
  trading_mode: "paper"  # paper or live
  
trading:
  market_open: "09:30"
  market_close: "16:00"
  timezone: "America/New_York"
  
  strategies:
    - name: "IronCondor"
      enabled: true
      allocation: 0.30
    - name: "CreditSpread"
      enabled: true
      allocation: 0.40
    - name: "ZeroDTE"
      enabled: false
      allocation: 0.00
    - name: "Straddle"
      enabled: true
      allocation: 0.30
      
risk_management:
  max_daily_loss: 1000
  max_drawdown: 0.15
  max_positions: 10
  position_size_limits:
    min: 0.01
    max: 0.20
    
notifications:
  email:
    enabled: true
    recipients:
      - email: "trader@example.com"
        types: ["trade_execution", "risk_alert", "daily_summary"]
  desktop:
    enabled: true
    sound_enabled: true
    quiet_hours:
      enabled: false
      start: "22:00"
      end: "07:00"
EOF

# Create launcher script
print_status "Creating launcher script..."
cat > robola_launcher.py << 'EOF'
#!/usr/bin/env python3
"""
SPYDER Trading System Launcher
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run main application
from RobolaA_Core.RobolaA01_Main import main

if __name__ == "__main__":
    print("Starting SPYDER Trading System...")
    print("=" * 50)
    
    # Check trading mode from environment
    from dotenv import load_dotenv
    load_dotenv()
    
    trading_mode = os.getenv('TRADING_MODE', 'paper')
    print(f"Trading Mode: {trading_mode.upper()}")
    
    if trading_mode == 'live':
        response = input("\nWARNING: Live trading mode! Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Exiting...")
            sys.exit(0)
    
    print("=" * 50)
    
    # Start the application
    main()
EOF

chmod +x robola_launcher.py

# Create test script
print_status "Creating test script..."
cat > test_setup.py << 'EOF'
#!/usr/bin/env python3
"""
Test SPYDER Setup
"""

import sys
import importlib

def test_imports():
    """Test if all required packages can be imported"""
    packages = [
        'numpy',
        'pandas',
        'matplotlib',
        'PyQt5',
        'ib_insync',
        'talib',
        'sklearn',
        'reportlab',
        'cryptography',
        'plyer'
    ]
    
    print("Testing package imports...")
    failed = []
    
    for package in packages:
        try:
            importlib.import_module(package)
            print(f"✓ {package}")
        except ImportError as e:
            print(f"✗ {package}: {e}")
            failed.append(package)
    
    if failed:
        print(f"\nFailed imports: {', '.join(failed)}")
        return False
    else:
        print("\nAll packages imported successfully!")
        return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
EOF

chmod +x test_setup.py

# Create VSCode configuration
print_status "Creating VSCode configuration..."
mkdir -p .vscode
cat > .vscode/settings.json << 'EOF'
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    },
    "editor.formatOnSave": true,
    "editor.rulers": [88],
    "python.analysis.typeCheckingMode": "basic"
}
EOF

cat > .vscode/launch.json << 'EOF'
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Spyder Trading System",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/robola_launcher.py",
            "console": "integratedTerminal",
            "env": {
                "PYTHONPATH": "${workspaceFolder}",
                "TRADING_MODE": "paper"
            }
        },
        {
            "name": "Spyder (Live Trading)",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/robola_launcher.py",
            "console": "integratedTerminal",
            "env": {
                "PYTHONPATH": "${workspaceFolder}",
                "TRADING_MODE": "live"
            }
        },
        {
            "name": "Test Setup",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/test_setup.py",
            "console": "integratedTerminal"
        }
    ]
}
EOF

# Create .gitignore
print_status "Creating .gitignore..."
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Project specific
logs/
data/*.db
data/backups/
reports/
models/*.pkl
.env
*.log

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/
*.cover

# Distribution
build/
dist/
*.egg-info/
EOF

# Create README
print_status "Creating README..."
cat > README.md << 'EOF'
# SPYDER - Automated SPY Options Trading System

## Overview
SPYDER is a fully automated options trading system designed for SPY options on Interactive Brokers.

## Features
- Automated strategy selection based on market conditions
- Multiple trading strategies (Iron Condor, Credit Spreads, etc.)
- Advanced risk management
- Real-time monitoring and notifications
- Comprehensive backtesting
- Machine learning optimization

## Setup
1. Clone this repository
2. Run the setup script: `./setup_robola.sh`
3. Configure your IB credentials in `.env`
4. Start IB Gateway or TWS
5. Run the system: `python robola_launcher.py`

## Trading Modes
- **Paper Trading**: Set `TRADING_MODE=paper` in `.env` (default)
- **Live Trading**: Set `TRADING_MODE=live` in `.env` (use with caution!)

## Directory Structure
- `RobolaA_Core/` - Core trading engine
- `RobolaB_Broker/` - IB integration
- `RobolaC_MarketData/` - Market data handling
- `RobolaD_Strategies/` - Trading strategies
- `RobolaE_Risk/` - Risk management
- `RobolaF_Analysis/` - Technical analysis
- `RobolaG_GUI/` - User interface
- `RobolaH_Storage/` - Data storage
- `RobolaI_Backtest/` - Backtesting
- `RobolaJ_Alerts/` - Notifications
- `RobolaK_Reports/` - Reporting
- `RobolaL_ML/` - Machine learning
- `RobolaU_Utilities/` - Utilities

## Important Notes
- Always start with paper trading
- Monitor the system regularly
- Review daily reports
- Keep risk parameters conservative

## Support
For issues or questions, please check the documentation in each module.
EOF

# Test the setup
print_status "Testing Python package imports..."
source venv/bin/activate
python test_setup.py

if [ $? -eq 0 ]; then
    print_status "Setup completed successfully!"
else
    print_error "Some packages failed to import. Please check the errors above."
fi

# Final instructions
echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Copy all your Spyder*.py modules to their respective directories"
echo "2. Update the .env file with your IB credentials and email settings"
echo "3. Start Interactive Brokers Gateway or TWS"
echo "4. Open this folder in VSCode: code $PROJECT_DIR"
echo "5. Run the system: python robola_launcher.py"
echo ""
echo "Project location: $PROJECT_DIR"
echo ""
echo "To activate the virtual environment in the future:"
echo "cd $PROJECT_DIR && source venv/bin/activate"
echo ""
print_warning "Remember to start with PAPER TRADING mode!"
