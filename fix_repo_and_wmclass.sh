#!/bin/bash
# Fix repository issues and install wmctrl for WM_CLASS diagnosis

echo "🔧 FIXING REPOSITORY ISSUES"
echo "============================"

# Option 1: Remove the problematic PPA
echo "1. Removing problematic deadsnakes PPA..."
sudo add-apt-repository --remove ppa:deadsnakes/ppa -y 2>/dev/null || echo "PPA not found or already removed"

# Option 2: Alternative - just disable it temporarily
echo "2. Checking for PPA files to disable..."
if [ -f /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-plucky.list ]; then
    sudo mv /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-plucky.list /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-plucky.list.disabled
    echo "✅ Disabled problematic PPA file"
fi

# Try updating apt without the problematic repo
echo "3. Updating package lists..."
sudo apt update

# Install wmctrl
echo "4. Installing wmctrl..."
sudo apt install wmctrl -y

echo ""
echo "✅ Repository fixed and wmctrl installed!"
echo ""
echo "🎯 NOW LET'S FIX THE WM_CLASS ISSUE"
echo "=================================="
echo ""

# Re-run the diagnostic with wmctrl now available
echo "Running enhanced diagnostic with wmctrl..."
python3 check_wmclass.py

echo ""
echo "🧪 NEXT STEPS:"
echo "1. Launch your dashboard from SPY icon"
echo "2. Run: xprop WM_CLASS"
echo "3. Click on dashboard window"
echo "4. Use that exact WM_CLASS value in desktop file"