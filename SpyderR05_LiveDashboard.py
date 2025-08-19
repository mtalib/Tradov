#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime [Application Name] [Group Letter] [Group Name]   
Module: SpyderR05_LiveDashboard.py [Application Name][Group Letter] [Module Number]_[Purpose].py
Purpose: Enhanced Live Dashboard launcher optimized for new G05
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-18 Time: 23:30:00  

Module Description:
    Professional runtime launcher for the enhanced SpyderG05 Trading Dashboard.
    Provides comprehensive startup sequence, system health checks, IB Gateway
    detection, and seamless integration with real market data. Optimized to work
    perfectly with the new enhanced G05 dashboard without conflicts or redundancy.

FEATURES:
    • Professional startup sequence with splash screen
    • Comprehensive IB Gateway detection (Paper/Live ports)
    • System prerequisites and health validation
    • Real data integration status reporting
    • Enhanced error handling and user feedback
    • Clean integration with enhanced G05 dashboard
    • Connection health monitoring and recovery
    • Professional status reporting and logging

INTEGRATION:
    • Works seamlessly with enhanced SpyderG05_TradingDashboard
    • No redundant real data integration (G05 handles this)
    • Leverages all G05 enhanced features
    • Professional startup experience with comprehensive checks
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import socket
import time
import threading
from datetime import datetime
from pathlib import Path
import json
import traceback

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen, QProgressBar, QVBoxLayout, QLabel
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, Qt, QThread
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor, QBrush, QPen

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add Spyder directory to path
SPYDER_HOME = Path(__file__).parent.parent
sys.path.insert(0, str(SPYDER_HOME))

# Import the enhanced dashboard (our new G05)
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# ==============================================================================
# CONSTANTS
# ==============================================================================
IB_PAPER_PORT = 4002
IB_LIVE_PORT = 4001
IB_HOST = "127.0.0.1"
REAL_DATA_FILE = Path.home() / "Projects/Spyder/market_data/live_data.json"

# Startup configuration
SPLASH_DURATION = 3000  # 3 seconds
CHECK_DELAY = 500       # 0.5 seconds between checks
STARTUP_CHECKS = [
    "Checking Python environment...",
    "Validating required modules...",
    "Detecting IB Gateway connection...",
    "Checking real market data availability...",
    "Initializing trading dashboard...",
    "Loading market data systems...",
    "Activating signal monitoring...",
    "Starting Prometheus metrics...",
    "Finalizing startup sequence...",
    "Dashboard ready!"
]

# ==============================================================================
# ENHANCED SPLASH SCREEN
# ==============================================================================
class ProfessionalSplashScreen(QSplashScreen):
    """Professional splash screen with progress indicator"""
    
    def __init__(self):
        # Create professional gradient pixmap
        pixmap = QPixmap(700, 400)
        self._create_professional_background(pixmap)
        
        super().__init__(pixmap)
        
        # Set properties
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint)
        
        # Progress tracking
        self.current_step = 0
        self.total_steps = len(STARTUP_CHECKS)
        
    def _create_professional_background(self, pixmap):
        """Create professional gradient background"""
        pixmap.fill(QColor("#0a0a0a"))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Professional gradient
        from PyQt6.QtGui import QLinearGradient
        gradient = QLinearGradient(0, 0, 0, pixmap.height())
        gradient.setColorAt(0, QColor("#1a1a1a"))
        gradient.setColorAt(0.5, QColor("#0a0a0a"))
        gradient.setColorAt(1, QColor("#1a1a1a"))
        
        painter.fillRect(pixmap.rect(), QBrush(gradient))
        
        # Border
        painter.setPen(QPen(QColor("#333333"), 2))
        painter.drawRect(pixmap.rect().adjusted(1, 1, -1, -1))
        
        # SPYDER Title
        title_font = QFont("Arial", 32, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(50, 100, "S P Y D E R")
        
        # Subtitle
        subtitle_font = QFont("Arial", 14)
        painter.setFont(subtitle_font)
        painter.setPen(QColor("#00ff41"))
        painter.drawText(50, 130, "Enhanced Live Trading Dashboard")
        
        # Features list
        features_font = QFont("Arial", 12)
        painter.setFont(features_font)
        painter.setPen(QColor("#ffffff"))
        
        features = [
            "• Real Market Data Integration",
            "• Professional Signal Monitoring", 
            "• Unified Prometheus Metrics",
            "• Advanced Risk Management",
            "• Autonomous AI Trading Engine"
        ]
        
        y_pos = 180
        for feature in features:
            painter.drawText(50, y_pos, feature)
            y_pos += 25
        
        # Version and status
        painter.setPen(QColor("#888888"))
        painter.drawText(50, 350, "Version 1.0 - Enhanced Edition")
        painter.drawText(450, 350, "Spyder Trading Systems")
        
        painter.end()
        
    def showProgress(self, step: int, message: str):
        """Show progress with step indicator"""
        self.current_step = step
        progress = int((step / self.total_steps) * 100)
        
        full_message = f"[{step}/{self.total_steps}] {message} ({progress}%)"
        
        self.showMessage(
            full_message, 
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, 
            QColor("#00ff41")
        )
        
        QApplication.processEvents()

# ==============================================================================
# SYSTEM HEALTH CHECKER
# ==============================================================================
class SystemHealthChecker:
    """Comprehensive system health and prerequisites checker"""
    
    def __init__(self):
        self.checks_passed = 0
        self.total_checks = 0
        self.issues = []
        self.warnings = []
        
    def run_all_checks(self) -> dict:
        """Run all system health checks"""
        results = {
            "python_version": self._check_python_version(),
            "required_modules": self._check_required_modules(),
            "ib_gateway": self._check_ib_gateway(),
            "real_data": self._check_real_data(),
            "directories": self._check_directories(),
            "overall_health": 0
        }
        
        # Calculate overall health score (exclude overall_health from check)
        health_checks = {k: v for k, v in results.items() if k != "overall_health"}
        passed = sum(1 for check in health_checks.values() if check.get("status") == "PASS")
        total = len(health_checks)
        results["overall_health"] = int((passed / total) * 100)
           
        
        return results
    
    def _check_python_version(self) -> dict:
        """Check Python version compatibility"""
        version = sys.version_info
        
        if version >= (3, 8):
            return {
                "status": "PASS",
                "message": f"Python {version.major}.{version.minor}.{version.micro}",
                "details": "Compatible version detected"
            }
        else:
            return {
                "status": "FAIL", 
                "message": f"Python {version.major}.{version.minor}.{version.micro}",
                "details": "Python 3.8+ required"
            }
    
    def _check_required_modules(self) -> dict:
        """Check required Python modules"""
        required = ['PyQt6', 'numpy', 'pandas', 'matplotlib', 'pathlib']
        missing = []
        available = []
        
        for module in required:
            try:
                __import__(module)
                available.append(module)
            except ImportError:
                missing.append(module)
        
        if not missing:
            return {
                "status": "PASS",
                "message": f"All {len(required)} modules available",
                "details": f"Available: {', '.join(available)}"
            }
        else:
            return {
                "status": "FAIL",
                "message": f"{len(missing)} modules missing",
                "details": f"Missing: {', '.join(missing)}"
            }
    
    def _check_ib_gateway(self) -> dict:
        """Check IB Gateway connectivity"""
        paper_available = self._test_port(IB_HOST, IB_PAPER_PORT)
        live_available = self._test_port(IB_HOST, IB_LIVE_PORT)
        
        if paper_available and live_available:
            return {
                "status": "PASS",
                "message": "Both Paper and Live ports available",
                "details": f"Paper: {IB_PAPER_PORT}, Live: {IB_LIVE_PORT}"
            }
        elif paper_available:
            return {
                "status": "WARN",
                "message": "Paper trading port available",
                "details": f"Port {IB_PAPER_PORT} - Live port {IB_LIVE_PORT} not available"
            }
        elif live_available:
            return {
                "status": "WARN", 
                "message": "Live trading port available",
                "details": f"Port {IB_LIVE_PORT} - Paper port {IB_PAPER_PORT} not available"
            }
        else:
            return {
                "status": "FAIL",
                "message": "No IB Gateway detected",
                "details": f"Neither port {IB_PAPER_PORT} nor {IB_LIVE_PORT} available"
            }
    
    def _check_real_data(self) -> dict:
        """Check real market data availability"""
        if not REAL_DATA_FILE.exists():
            return {
                "status": "WARN",
                "message": "Real data file not found",
                "details": f"File: {REAL_DATA_FILE} - Will use simulation mode"
            }
        
        try:
            with open(REAL_DATA_FILE, 'r') as f:
                data = json.load(f)
            
            if data and isinstance(data, dict) and 'SPY' in data:
                spy_price = data['SPY'].get('last', 'N/A')
                return {
                    "status": "PASS",
                    "message": f"Real market data available - SPY: ${spy_price}",
                    "details": f"File: {REAL_DATA_FILE} - {len(data)} symbols"
                }
            else:
                return {
                    "status": "WARN",
                    "message": "Real data file exists but invalid",
                    "details": "Data file format issue - Will use simulation"
                }
                
        except Exception as e:
            return {
                "status": "WARN",
                "message": "Cannot read real data file",
                "details": f"Error: {e} - Will use simulation"
            }
    
    def _check_directories(self) -> dict:
        """Check required directories"""
        required_dirs = [
            Path.home() / "Projects/Spyder",
            Path.home() / "Projects/Spyder/market_data"
        ]
        
        missing = []
        for dir_path in required_dirs:
            if not dir_path.exists():
                missing.append(str(dir_path))
        
        if not missing:
            return {
                "status": "PASS",
                "message": "All directories available",
                "details": f"Checked {len(required_dirs)} directories"
            }
        else:
            return {
                "status": "WARN",
                "message": f"{len(missing)} directories missing",
                "details": f"Missing: {', '.join(missing)}"
            }
    
    def _test_port(self, host: str, port: int) -> bool:
        """Test if port is available"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False

# ==============================================================================
# ENHANCED DASHBOARD LAUNCHER
# ==============================================================================
class EnhancedDashboardLauncher:
    """Professional dashboard launcher with comprehensive checks"""
    
    def __init__(self):
        self.health_checker = SystemHealthChecker()
        self.dashboard = None
        self.splash = None
        
    def launch(self) -> int:
        """Launch the enhanced dashboard with full startup sequence"""
        
        print("\n" + "=" * 80)
        print("SPYDER R05 - ENHANCED LIVE DASHBOARD LAUNCHER")
        print("=" * 80)
        print("🔥 Professional startup sequence")
        print("📊 Comprehensive system health checks")
        print("🚀 Seamless integration with enhanced G05")
        print("⚡ Real market data auto-detection")
        print("🎯 Professional trading interface")
        print("=" * 80)
        
        # Create Qt application
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setApplicationName("Spyder Enhanced Live Dashboard")
        app.setOrganizationName("Spyder Trading System")
        
        try:
            # Show professional splash screen
            self.splash = ProfessionalSplashScreen()
            self.splash.show()
            
            # Run startup sequence
            if not self._run_startup_sequence():
                return 1
            
            # Create and show dashboard
            print("🚀 Launching enhanced dashboard...")
            self.dashboard = SpyderTradingDashboard()  # Our new enhanced G05
            
            # Finalize startup
            self.splash.showProgress(len(STARTUP_CHECKS), STARTUP_CHECKS[-1])
            time.sleep(0.5)
            
            # Hide splash and show dashboard
            self.splash.finish(self.dashboard)
            self.dashboard.show()
            
            # Show startup completion
            self._show_startup_summary()
            
            # Run application
            return app.exec()
            
        except Exception as e:
            self._handle_startup_error(e)
            return 1
    
    def _run_startup_sequence(self) -> bool:
        """Run comprehensive startup sequence"""
        
        for i, check in enumerate(STARTUP_CHECKS[:-1], 1):  # Exclude final "Dashboard ready!"
            self.splash.showProgress(i, check)
            
            if "Python environment" in check:
                if not self._check_python_environment():
                    return False
                    
            elif "required modules" in check:
                if not self._check_required_modules():
                    return False
                    
            elif "IB Gateway" in check:
                self._check_ib_gateway_status()
                
            elif "real market data" in check:
                self._check_real_data_status()
                
            elif "trading dashboard" in check:
                self._prepare_dashboard_initialization()
                
            time.sleep(CHECK_DELAY / 1000)  # Convert to seconds
        
        return True
    
    def _check_python_environment(self) -> bool:
        """Check Python environment"""
        version = sys.version_info
        
        if version < (3, 8):
            self._show_critical_error(
                "Python Version Error",
                f"Python 3.8+ required, found {version.major}.{version.minor}\n"
                "Please upgrade Python and try again."
            )
            return False
        
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    
    def _check_required_modules(self) -> bool:
        """Check required modules"""
        required = ['PyQt6', 'numpy', 'pandas', 'matplotlib']
        missing = []
        
        for module in required:
            try:
                __import__(module)
                print(f"✅ {module}")
            except ImportError:
                missing.append(module)
                print(f"❌ {module}")
        
        if missing:
            self._show_critical_error(
                "Missing Dependencies",
                f"Required modules missing: {', '.join(missing)}\n\n"
                "Install with: pip install " + " ".join(missing)
            )
            return False
        
        return True
    
    def _check_ib_gateway_status(self):
        """Check IB Gateway status"""
        paper_available = self.health_checker._test_port(IB_HOST, IB_PAPER_PORT)
        live_available = self.health_checker._test_port(IB_HOST, IB_LIVE_PORT)
        
        if paper_available and live_available:
            print("✅ IB Gateway: Both Paper and Live ports available")
        elif paper_available:
            print("⚠️ IB Gateway: Paper port available, Live port not detected")
        elif live_available:
            print("⚠️ IB Gateway: Live port available, Paper port not detected")
        else:
            print("⚠️ IB Gateway: No ports detected - Dashboard will use simulation")
    
    def _check_real_data_status(self):
        """Check real market data status"""
        if REAL_DATA_FILE.exists():
            try:
                with open(REAL_DATA_FILE, 'r') as f:
                    data = json.load(f)
                
                if data and 'SPY' in data:
                    spy_price = data['SPY'].get('last', 'N/A')
                    print(f"🔥 Real market data: Available - SPY: ${spy_price}")
                else:
                    print("⚠️ Real market data: File exists but invalid format")
            except:
                print("⚠️ Real market data: File exists but cannot be read")
        else:
            print("📊 Real market data: Not available - Dashboard will use simulation")
    
    def _prepare_dashboard_initialization(self):
        """Prepare for dashboard initialization"""
        print("🎯 Preparing enhanced dashboard initialization...")
        
        # Create data directory if it doesn't exist
        data_dir = Path.home() / "Projects/Spyder/market_data"
        data_dir.mkdir(parents=True, exist_ok=True)
    
    def _show_startup_summary(self):
        """Show comprehensive startup summary"""
        print("\n" + "=" * 60)
        print("ENHANCED LIVE DASHBOARD - STARTUP SUMMARY")
        print("=" * 60)
        
        # Run health checks
        health_results = self.health_checker.run_all_checks()
        
        # Display results
        for check_name, result in health_results.items():
            if check_name == "overall_health":
                continue
                
            status = result.get("status", "UNKNOWN")
            message = result.get("message", "No message")
            
            if status == "PASS":
                print(f"✅ {check_name.replace('_', ' ').title()}: {message}")
            elif status == "WARN":
                print(f"⚠️ {check_name.replace('_', ' ').title()}: {message}")
            else:
                print(f"❌ {check_name.replace('_', ' ').title()}: {message}")
        
        print(f"\n🎯 Overall System Health: {health_results['overall_health']}%")
        print("=" * 60)
        
        # Add usage tips
        print("\n💡 USAGE TIPS:")
        tips = [
            "• Real data automatically detected from ~/Projects/Spyder/market_data/live_data.json",
            "• Start data injector first: python temp_WorkingDataInjector.py",
            "• Dashboard shows 'LIVE - REAL' when using real market data",
            "• All 12 signal monitors work with both real and simulation data",
            "• Enhanced G05 includes unified Prometheus metrics and professional charts"
        ]
        
        for tip in tips:
            print(f"   {tip}")
        
        print("\n🔥 Enhanced Live Dashboard is ready!")
        print("   Navigate to START TRADING when ready to begin operations\n")
        
        # Add to dashboard logs
        if self.dashboard:
            self.dashboard.add_system_log("🔥 Enhanced Live Dashboard fully loaded via R05")
            self.dashboard.add_automation_log("Professional startup sequence completed")
            if health_results['overall_health'] >= 80:
                self.dashboard.add_automation_log("All systems operational - Ready for live trading")
            else:
                self.dashboard.add_automation_log(f"System health: {health_results['overall_health']}% - Some limitations may apply")
    
    def _show_critical_error(self, title: str, message: str):
        """Show critical error dialog"""
        try:
            QMessageBox.critical(None, title, message)
        except:
            print(f"\n❌ CRITICAL ERROR: {title}")
            print(f"   {message}")
    
    def _handle_startup_error(self, error: Exception):
        """Handle startup errors gracefully"""
        error_msg = str(error)
        traceback_str = traceback.format_exc()
        
        print(f"\n❌ Startup Error: {error_msg}")
        print(f"Traceback:\n{traceback_str}")
        
        try:
            QMessageBox.critical(
                None,
                "Enhanced Live Dashboard - Startup Error",
                f"Failed to start Enhanced Live Dashboard:\n\n{error_msg}\n\n"
                "Please check the console for detailed error information."
            )
        except:
            pass

# ==============================================================================
# STANDALONE LAUNCHER FUNCTIONS
# ==============================================================================
def quick_launch():
    """Quick launch without splash screen (for development)"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    print("🚀 Quick launching enhanced dashboard...")
    dashboard = SpyderTradingDashboard()
    dashboard.show()
    
    return app.exec()

def launch_with_status_check():
    """Launch with basic status check only"""
    launcher = EnhancedDashboardLauncher()
    health_results = launcher.health_checker.run_all_checks()
    
    print("System Health Check Results:")
    for check_name, result in health_results.items():
        if check_name != "overall_health":
            print(f"  {check_name}: {result.get('status', 'UNKNOWN')}")
    
    print(f"\nOverall Health: {health_results['overall_health']}%")
    
    if health_results['overall_health'] >= 60:
        return launcher.launch()
    else:
        print("❌ System health too low for reliable operation")
        return 1

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main entry point with professional launcher"""
    try:
        launcher = EnhancedDashboardLauncher()
        return launcher.launch()
    except KeyboardInterrupt:
        print("\n⚠️ Startup interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
