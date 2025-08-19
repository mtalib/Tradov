#!/usr/bin/env python3
"""
Diagnostic script to find the correct WM_CLASS for Spyder dashboard
"""

import subprocess
import sys
import time
from pathlib import Path

def check_wmclass():
    """Check WM_CLASS of running Spyder processes"""
    
    print("🔍 WM_CLASS DIAGNOSTIC FOR SPYDER DASHBOARD")
    print("=" * 50)
    
    # Check current desktop file setting
    desktop_file = Path.home() / ".local/share/applications/spyder-trading.desktop"
    if desktop_file.exists():
        with open(desktop_file, 'r') as f:
            content = f.read()
            for line in content.split('\n'):
                if line.startswith('StartupWMClass='):
                    print(f"📄 Current desktop file WMClass: {line}")
                    break
    
    print("\n🔍 Checking running windows...")
    
    # Method 1: wmctrl
    try:
        result = subprocess.run(['wmctrl', '-lx'], capture_output=True, text=True)
        if result.returncode == 0:
            print("\n📋 All windows (wmctrl -lx):")
            lines = result.stdout.strip().split('\n')
            spyder_windows = []
            
            for line in lines:
                if line and any(keyword in line.lower() for keyword in ['spyder', 'spy', 'trading', 'python']):
                    print(f"  📌 {line}")
                    spyder_windows.append(line)
            
            if spyder_windows:
                print(f"\n🎯 Found {len(spyder_windows)} potential Spyder windows")
            else:
                print("\n⚠️ No Spyder windows found via wmctrl")
        else:
            print("❌ wmctrl not available")
    except FileNotFoundError:
        print("❌ wmctrl not installed")
    
    # Method 2: xprop (if available)
    try:
        print("\n🔍 WM_CLASS detection methods:")
        print("1. Launch your dashboard from SPY icon")
        print("2. Click on the dashboard window")
        print("3. Run: xprop WM_CLASS")
        print("4. This will show the actual WM_CLASS")
    except:
        pass
    
    # Method 3: Process checking
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if result.returncode == 0:
            print("\n🔄 Running Spyder processes:")
            lines = result.stdout.split('\n')
            for line in lines:
                if any(keyword in line for keyword in ['SpyderG05', 'SpyderR05', 'fast_launcher', 'TradingDashboard']):
                    # Extract just the relevant part
                    parts = line.split()
                    if len(parts) > 10:
                        cmd = ' '.join(parts[10:])
                        print(f"  🔹 {cmd}")
    except Exception as e:
        print(f"❌ Process check failed: {e}")

def suggest_fixes():
    """Suggest fixes for WM_CLASS issues"""
    
    print(f"\n🛠️ COMMON FIXES:")
    print("=" * 30)
    
    fixes = [
        ("python3", "Python application detected - try WMClass=python3"),
        ("SpyderG05_TradingDashboard", "Dashboard script - try WMClass=SpyderG05_TradingDashboard"), 
        ("spyder-trading", "Trading app - try WMClass=spyder-trading"),
        ("SPYDER", "Current setting - might need lowercase: spyder"),
        ("fast_launcher", "Fast launcher - try WMClass=fast_launcher"),
    ]
    
    print("📋 Try these WMClass values in your desktop file:")
    for wmclass, description in fixes:
        print(f"  🔧 StartupWMClass={wmclass}  # {description}")
    
    print(f"\n🎯 STEPS TO FIX:")
    print("1. Launch dashboard from SPY icon")
    print("2. Note the gear icon that appears")
    print("3. Right-click gear icon → Properties (or use xprop)")
    print("4. Find the WM_CLASS value")
    print("5. Update desktop file with correct StartupWMClass")

def create_fix_script():
    """Create a script to test different WM_CLASS values"""
    
    fix_script = '''#!/bin/bash
# WM_CLASS Fix Tester
echo "🧪 WM_CLASS FIX TESTER"
echo "=================="

DESKTOP_FILE="$HOME/.local/share/applications/spyder-trading.desktop"

# Test different WM_CLASS values
WM_CLASSES=("SPYDER" "spyder" "python3" "SpyderG05_TradingDashboard" "spyder-trading" "fast_launcher")

for wmclass in "${WM_CLASSES[@]}"; do
    echo "🔧 Testing WMClass: $wmclass"
    
    # Backup current file
    cp "$DESKTOP_FILE" "$DESKTOP_FILE.backup"
    
    # Update WMClass
    sed -i "s/^StartupWMClass=.*/StartupWMClass=$wmclass/" "$DESKTOP_FILE"
    
    # Update desktop database
    update-desktop-database ~/.local/share/applications/
    
    echo "   Updated to: StartupWMClass=$wmclass"
    echo "   Test your SPY icon now, then press Enter to try next..."
    read
done

echo "✅ Testing complete!"
'''
    
    script_path = Path.home() / "Projects/Spyder/test_wmclass.sh"
    with open(script_path, 'w') as f:
        f.write(fix_script)
    
    script_path.chmod(0o755)
    print(f"\n📝 Created WM_CLASS tester script: {script_path}")
    print("   Run: ~/Projects/Spyder/test_wmclass.sh")

def main():
    """Main diagnostic function"""
    check_wmclass()
    suggest_fixes()
    create_fix_script()
    
    print(f"\n🎯 QUICK TEST:")
    print("1. Launch dashboard from SPY icon")
    print("2. Run: xprop WM_CLASS")
    print("3. Click on the dashboard window")  
    print("4. Note the WM_CLASS value shown")
    print("5. Update your desktop file with that value")

if __name__ == "__main__":
    main()
