#!/bin/bash
# Simple terminal launcher that avoids display issues

cd /home/adam/Projects/Spyder
source .venv/bin/activate

# Disable pyautogui
export SPYDER_NO_AUTOMATION=1

# Use text mode if GUI fails
python << END
import sys
sys.path.insert(0, '/home/adam/Projects/Spyder')

try:
    # Try GUI first
    from SpyderG_GUI import SpyderG01_MainWindow
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = SpyderG01_MainWindow.MainWindow()
    window.show()
    sys.exit(app.exec())
except Exception as e:
    print(f"GUI failed: {e}")
    print("Starting in console mode...")
    
    # Fall back to console mode
    from SpyderA_Core import SpyderA01_Main
    SpyderA01_Main.main(["--headless"])
END
