#!/bin/bash
# install_fresh_gateway.sh - Download and install fresh IB Gateway

echo "=================================================="
echo "FRESH IB GATEWAY INSTALLATION"
echo "=================================================="

# Step 1: Backup old installation
echo -e "\n[1] Backing up old installation..."
if [ -d "$HOME/Jts" ]; then
    backup_name="Jts_backup_$(date +%Y%m%d_%H%M%S)"
    mv "$HOME/Jts" "$HOME/$backup_name"
    echo "✅ Old installation backed up to: ~/$backup_name"
else
    echo "ℹ️  No existing installation found"
fi

# Step 2: Create download directory
echo -e "\n[2] Creating download directory..."
mkdir -p ~/Downloads/IB
cd ~/Downloads/IB

# Step 3: Download IB Gateway
echo -e "\n[3] Downloading IB Gateway..."
echo "Choose your download method:"
echo "1) Download STABLE version (recommended)"
echo "2) Download LATEST version"
echo "3) I'll download manually"

read -p "Enter choice (1-3): " choice

case $choice in
    1)
        # Stable version
        echo "Downloading stable version..."
        wget -O ibgateway-stable-standalone-linux-x64.sh \
            "https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh"
        ;;
    2)
        # Latest version
        echo "Downloading latest version..."
        wget -O ibgateway-latest-standalone-linux-x64.sh \
            "https://download2.interactivebrokers.com/installers/ibgateway/latest-standalone/ibgateway-latest-standalone-linux-x64.sh"
        ;;
    3)
        echo -e "\nManual download instructions:"
        echo "1. Go to: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php"
        echo "2. Download: IB Gateway for Linux"
        echo "3. Save to: ~/Downloads/IB/"
        echo "4. Run this script again after downloading"
        exit 0
        ;;
esac

# Step 4: Make installer executable
echo -e "\n[4] Preparing installer..."
chmod +x ibgateway-*.sh

# Step 5: Install
echo -e "\n[5] Installing IB Gateway..."
echo "ℹ️  The installer will open. Follow these steps:"
echo "   1. Click 'Next' through the installer"
echo "   2. Accept the license"
echo "   3. Install to default location (/home/$USER/Jts)"
echo "   4. Complete installation"
echo ""
read -p "Press Enter to start installer..."

# Run installer
./ibgateway-*.sh

# Step 6: Post-installation setup
echo -e "\n[6] Post-installation setup..."

# Create initial config with API enabled
mkdir -p ~/Jts/ibgateway/paper
cat > ~/Jts/ibgateway/paper/ibgateway.vmoptions << 'EOF'
-Xmx768m
-XX:+UseG1GC
-Dawt.useSystemAAFontSettings=lcd
-Dsun.java2d.uiScale=1.0
-DjtsConfigDir=paper
EOF

# Step 7: Create launcher script
echo -e "\n[7] Creating launcher script..."
cat > ~/start_ibgateway.sh << 'EOF'
#!/bin/bash
# Start IB Gateway with proper settings

echo "Starting IB Gateway..."
cd ~/Jts
./ibgateway &

echo ""
echo "=================================================="
echo "IB GATEWAY STARTING"
echo "=================================================="
echo ""
echo "1. LOG IN first with your credentials"
echo "2. Complete 2FA authentication"
echo "3. THEN configure API:"
echo "   - Click Configure → Settings → API → Settings"
echo "   - UNCHECK 'Read-Only API'"
echo "   - Socket port: 4002"
echo "   - Click OK"
echo "4. RESTART IB Gateway after configuring"
echo ""
echo "=================================================="
EOF

chmod +x ~/start_ibgateway.sh

echo -e "\n=================================================="
echo "INSTALLATION COMPLETE!"
echo "=================================================="
echo ""
echo "To start IB Gateway:"
echo "   ~/start_ibgateway.sh"
echo ""
echo "IMPORTANT - Fix 2FA first:"
echo "1. Make sure your system time is synchronized"
echo "2. Check IBKR mobile app notifications are enabled"
echo "3. Try alternative auth methods if needed"
echo ""
echo "=================================================="