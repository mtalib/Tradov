#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER TRADING SYSTEM - DIRECT GUI LAUNCHER
Bypasses command line arguments and launches GUI directly
Works with Wayland/X11
"""

import os
import sys
import logging
from pathlib import Path

# Set up environment for Wayland
os.environ['GDK_BACKEND'] = 'wayland,x11'
os.environ['QT_QPA_PLATFORM'] = 'wayland'
os.environ['SPYDER_NO_AUTOMATION'] = '1'  # Disable pyautogui

# Add Spyder to path
SPYDER_HOME = Path(__file__).parent
sys.path.insert(0, str(SPYDER_HOME))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_requirements():
    """Check if required modules are available"""
    missing = []
    
    try:
        import PyQt6
        logger.info("✓ PyQt6 available")
    except ImportError:
        missing.append("PyQt6")
        logger.error("✗ PyQt6 not installed")
    
    try:
        import pandas
        logger.info("✓ pandas available")
    except ImportError:
        missing.append("pandas")
        logger.error("✗ pandas not installed")
    
    try:
        import ib_async
        logger.info("✓ ib_async available")
    except ImportError:
        try:
            import ib_insync
            logger.info("✓ ib_insync available")
        except ImportError:
            missing.append("ib_async or ib_insync")
            logger.error("✗ Neither ib_async nor ib_insync installed")
    
    return missing

def launch_gui():
    """Launch the Spyder GUI directly"""
    
    print("="*60)
    print("SPYDER TRADING SYSTEM - DIRECT GUI LAUNCHER")
    print("="*60)
    print()
    
    # Check requirements
    missing = check_requirements()
    if missing:
        print(f"\n⚠️  Missing requirements: {', '.join(missing)}")
        print("Install with: pip install PyQt6 pandas ib-async")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    try:
        # Import PyQt6
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtCore import Qt
        
        # Create application
        app = QApplication(sys.argv)
        app.setApplicationName("Spyder Trading System")
        app.setOrganizationName("Spyder")
        
        # Try to import and create main window
        try:
            logger.info("Importing Spyder modules...")
            
            # Import the main window
            from SpyderG_GUI.SpyderG01_MainWindow import MainWindow
            
            logger.info("Creating main window...")
            
            # Create and configure the main window
            window = MainWindow()
            window.setWindowTitle("Spyder Trading System")
            
            # Set window properties for Wayland
            window.setAttribute(Qt.WindowAttribute.WA_ShowWithoutActivating, False)
            
            # Show the window
            window.show()
            
            logger.info("✓ GUI launched successfully")
            print("\n✓ Spyder Trading System GUI launched!")
            print("Check the application window.")
            
            # Run the application
            sys.exit(app.exec())
            
        except ImportError as e:
            logger.error(f"Import error: {e}")
            
            # Show error dialog
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Import Error")
            msg.setText("Failed to import Spyder modules")
            msg.setDetailedText(str(e))
            msg.exec()
            
            # Try alternative: Import core modules and create minimal GUI
            try:
                print("\nTrying minimal GUI mode...")
                
                from PyQt6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton
                
                class MinimalSpyderWindow(QMainWindow):
                    def __init__(self):
                        super().__init__()
                        self.setWindowTitle("Spyder Trading System - Minimal Mode")
                        self.setGeometry(100, 100, 800, 600)
                        
                        # Central widget
                        central = QWidget()
                        self.setCentralWidget(central)
                        
                        # Layout
                        layout = QVBoxLayout(central)
                        
                        # Info label
                        info = QLabel(
                            "Spyder Trading System - Minimal Mode\n\n"
                            "Some modules could not be loaded.\n"
                            "This is a fallback GUI.\n\n"
                            f"Error: {str(e)}"
                        )
                        info.setWordWrap(True)
                        layout.addWidget(info)
                        
                        # Start button (placeholder)
                        btn = QPushButton("Check System Status")
                        btn.clicked.connect(self.check_status)
                        layout.addWidget(btn)
                        
                    def check_status(self):
                        """Check system status"""
                        import subprocess
                        result = subprocess.run(
                            ["python", str(SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py"), "--version"],
                            capture_output=True,
                            text=True
                        )
                        
                        msg = QMessageBox()
                        msg.setWindowTitle("System Status")
                        msg.setText("Spyder System Check")
                        msg.setDetailedText(f"Output:\n{result.stdout}\n{result.stderr}")
                        msg.exec()
                
                # Create minimal window
                window = MinimalSpyderWindow()
                window.show()
                
                logger.info("✓ Minimal GUI launched")
                sys.exit(app.exec())
                
            except Exception as e2:
                logger.error(f"Failed to create minimal GUI: {e2}")
                QMessageBox.critical(None, "Fatal Error", f"Could not create GUI:\n{str(e2)}")
                sys.exit(1)
                
    except ImportError as e:
        logger.error(f"PyQt6 not available: {e}")
        print(f"\n✗ Error: PyQt6 not installed")
        print("Install with: pip install PyQt6")
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    launch_gui()
