#!/bin/bash
# Initialize Git repository for SPYDER Trading System

echo "Initializing Git repository for SPYDER..."

# Initialize git
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: SPYDER Automated SPY Options Trading System

- Complete trading engine with 58 modules
- Support for multiple strategies (Iron Condor, Credit Spreads, etc.)
- Advanced risk management
- Real-time monitoring and notifications
- Comprehensive backtesting capabilities
- Machine learning optimization
- Paper trading and live trading modes"

# Instructions for adding remote
echo ""
echo "Git repository initialized!"
echo ""
echo "To push to GitHub:"
echo "1. Create a new private repository on GitHub (do NOT initialize with README)"
echo "2. Run the following commands:"
echo ""
echo "git remote add origin https://github.com/YOUR_USERNAME/spyder-trading.git"
echo "git branch -M main"
echo "git push -u origin main"
echo ""
echo "Replace YOUR_USERNAME with your GitHub username"
