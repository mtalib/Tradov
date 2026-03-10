#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Unknown
Module: fix_launcher_widget_order.py
Purpose: Quick fix for AttributeError in StreamlinedSpyderLauncher

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    Quick fix for AttributeError in StreamlinedSpyderLauncher

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
from pathlib import Path

LAUNCHER_FILE = Path.home() / "Projects" / "Spyder" / "SpyderG_GUI" / "SpyderG08_IBKRLoginLauncher_Enhanced.py"

def apply_fix():
    print("🔧 Applying widget creation order fix...")

    if not LAUNCHER_FILE.exists():
        print(f"❌ Error: File not found: {LAUNCHER_FILE}")
        return 1

    # Read the file
    with open(LAUNCHER_FILE) as f:
        content = f.read()

    # Check if already fixed
    if "# Update info based on initial mode (after button is created)" in content:
        print("✅ File is already fixed!")
        return 0

    # Find and replace the problematic section
    old_code = """        self.info_label.pack(fill='both')

        # Update info based on initial mode
        self._on_mode_change()

        # Launch button
        self.launch_btn = tk.Button(
            main_frame,
            text="🚀 CONNECT & LAUNCH",
            font=("Arial", 12, "bold"),
            bg=self.colors['accent'],
            fg=self.colors['bg'],
            activebackground='#00dd00',
            activeforeground=self.colors['bg'],
            command=self.connect_and_launch,
            cursor="hand2",
            relief='flat',
            bd=0,
            padx=40,
            pady=15
        )
        self.launch_btn.pack(pady=20)"""

    new_code = """        self.info_label.pack(fill='both')

        # Launch button (create BEFORE calling _on_mode_change)
        self.launch_btn = tk.Button(
            main_frame,
            text="🚀 CONNECT & LAUNCH",
            font=("Arial", 12, "bold"),
            bg=self.colors['accent'],
            fg=self.colors['bg'],
            activebackground='#00dd00',
            activeforeground=self.colors['bg'],
            command=self.connect_and_launch,
            cursor="hand2",
            relief='flat',
            bd=0,
            padx=40,
            pady=15
        )
        self.launch_btn.pack(pady=20)

        # Update info based on initial mode (after button is created)
        self._on_mode_change()"""

    if old_code not in content:
        print("❌ Error: Could not find the code to replace")
        print("The file may have been modified. Please download the fixed version.")
        return 1

    # Create backup
    backup_file = LAUNCHER_FILE.with_suffix('.py.fix_backup')
    with open(backup_file, 'w') as f:
        f.write(content)
    print(f"✅ Backup created: {backup_file}")

    # Apply fix
    fixed_content = content.replace(old_code, new_code)

    # Write fixed file
    with open(LAUNCHER_FILE, 'w') as f:
        f.write(fixed_content)

    print("✅ Fix applied successfully!")
    print(f"📝 File updated: {LAUNCHER_FILE}")
    print("\n🧪 You can now test the launcher:")
    print(f"   python {LAUNCHER_FILE}")

    return 0

if __name__ == "__main__":
    sys.exit(apply_fix())
