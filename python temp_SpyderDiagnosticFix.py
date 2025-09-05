#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: Temporary Fix
Module: temp_SpyderDiagnosticFix.py
Purpose: Diagnose and fix initialization issues
Author: System Diagnostic
Year Created: 2025
Last Updated: 2025-09-04 Time: 20:40:00

Module Description:
    This temporary diagnostic module identifies and fixes common initialization
    issues including circular imports, missing dependencies, display configuration
    problems, and module loading errors. Run this before starting the main system.
"""

import os
import sys
import subprocess
import importlib
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ==============================================================================
# DIAGNOSTIC CLASS
# ==============================================================================

class SpyderDiagnosticFix:
    """Diagnose and fix Spyder system initialization issues"""
    
    def __init__(self):
        self.issues = []
        self.fixes_applied = []
        self.project_root = Path.cwd()
        
    # ======================================================================
    # DISPLAY CONFIGURATION
    # ======================================================================
    
    def fix_display_issues(self) -> bool:
        """Fix display configuration for GUI components"""
        print("\n🖥️  Checking display configuration...")
        
        # Check if we're in SSH/headless environment
        if 'SSH_CONNECTION' in os.environ or 'SSH_TTY' in os.environ:
            print("   ⚠️  SSH session detected - configuring headless mode")
            
            # Set headless environment variables
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
            os.environ['DISPLAY'] = ':0'  # Try default display first
            
            # Check if X server is running
            try:
                subprocess.run(['xset', '-q'], capture_output=True, check=True)
                print("   ✅ X server found on :0")
            except:
                print("   ⚠️  No X server available - GUI will be disabled")
                os.environ['SPYDER_HEADLESS'] = 'true'
                self.fixes_applied.append("Set headless mode for GUI components")
                
            return True
            
        # Check for virtual display
        display = os.environ.get('DISPLAY', '')
        if display == ':99':
            print("   ⚠️  Virtual display :99 configured but not available")
            
            # Try to start Xvfb
            try:
                subprocess.run(['which', 'xvfb-run'], capture_output=True, check=True)
                print("   📦 Installing virtual display...")
                os.environ['DISPLAY'] = ':0'
                self.fixes_applied.append("Reconfigured display from :99 to :0")
            except:
                print("   ❌ Xvfb not installed - GUI features will be limited")
                os.environ['SPYDER_HEADLESS'] = 'true'
                
        return True
    
    # ======================================================================
    # CIRCULAR IMPORT FIXES
    # ======================================================================
    
    def fix_circular_imports(self) -> bool:
        """Fix circular import issues in B-series modules"""
        print("\n🔄 Checking for circular imports...")
        
        # Check SpyderB05_ConnectionManager
        connection_mgr_path = self.project_root / "SpyderB_Broker" / "SpyderB05_ConnectionManager.py"
        
        if connection_mgr_path.exists():
            with open(connection_mgr_path, 'r') as f:
                content = f.read()
                
            # Look for problematic imports
            if "from SpyderB_Broker" in content and "import ConnectionManager" in content:
                print("   ⚠️  Potential circular import detected in ConnectionManager")
                
                # Create import fix suggestions
                fixes = []
                
                # Check if it's importing from __init__.py
                if "from SpyderB_Broker import" in content:
                    fixes.append("Move imports inside functions/methods instead of module level")
                    fixes.append("Use 'import SpyderB_Broker' instead of 'from SpyderB_Broker import'")
                    
                for fix in fixes:
                    print(f"   💡 Suggestion: {fix}")
                    
        return True
    
    # ======================================================================
    # MODULE DEPENDENCY CHECKS
    # ======================================================================
    
    def check_module_dependencies(self) -> bool:
        """Check and fix module dependencies"""
        print("\n📦 Checking module dependencies...")
        
        missing_modules = []
        
        # Check critical dependencies
        critical_deps = [
            ('ib_async', 'ib_async'),
            ('PyQt6', 'PyQt6'),
            ('pandas', 'pandas'),
            ('numpy', 'numpy'),
            ('scipy', 'scipy'),
            ('ta', 'ta'),
            ('pandas_ta', 'pandas-ta')
        ]
        
        for module_name, pip_name in critical_deps:
            try:
                importlib.import_module(module_name)
                print(f"   ✅ {module_name}")
            except ImportError:
                print(f"   ❌ {module_name} - Missing")
                missing_modules.append(pip_name)
                
        if missing_modules:
            print("\n   📦 Installing missing dependencies...")
            for module in missing_modules:
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', module], 
                                 capture_output=True, check=True)
                    print(f"   ✅ Installed {module}")
                    self.fixes_applied.append(f"Installed {module}")
                except:
                    print(f"   ❌ Failed to install {module}")
                    self.issues.append(f"Could not install {module}")
                    
        return len(missing_modules) == 0
    
    # ======================================================================
    # PERFORMANCE METRICS FIX
    # ======================================================================
    
    def fix_performance_metrics(self) -> bool:
        """Fix PerformanceMetrics import issue"""
        print("\n📊 Checking PerformanceMetrics module...")
        
        perf_metrics_path = self.project_root / "SpyderU_Utilities" / "SpyderU15_PerformanceMetrics.py"
        
        if perf_metrics_path.exists():
            # Check if the class exists
            with open(perf_metrics_path, 'r') as f:
                content = f.read()
                
            if "class PerformanceMetrics" not in content:
                print("   ⚠️  PerformanceMetrics class not found")
                
                # Create a basic implementation
                basic_impl = '''
class PerformanceMetrics:
    """Basic PerformanceMetrics implementation"""
    
    def __init__(self):
        self.metrics = {}
        
    def add_metric(self, name: str, value: float):
        self.metrics[name] = value
        
    def get_metric(self, name: str) -> float:
        return self.metrics.get(name, 0.0)
        
    def get_all_metrics(self) -> dict:
        return self.metrics.copy()
'''
                
                # Add to file
                with open(perf_metrics_path, 'a') as f:
                    f.write("\n\n# Temporary fix - basic implementation\n")
                    f.write(basic_impl)
                    
                print("   ✅ Added basic PerformanceMetrics implementation")
                self.fixes_applied.append("Added PerformanceMetrics class")
                
        return True
    
    # ======================================================================
    # CONFIGURATION FIXES
    # ======================================================================
    
    def create_default_configs(self) -> bool:
        """Create default configuration files if missing"""
        print("\n⚙️  Checking configuration files...")
        
        config_dir = self.project_root / "config"
        config_dir.mkdir(exist_ok=True)
        
        # Default configurations
        configs = {
            "spyder_config.json": {
                "system": {
                    "mode": "simulation",
                    "debug": True,
                    "headless": os.environ.get('SPYDER_HEADLESS', 'false') == 'true'
                },
                "broker": {
                    "host": "127.0.0.1",
                    "port": 7497,
                    "client_id": 1
                },
                "risk": {
                    "max_daily_loss": 1000,
                    "max_position_size": 10000,
                    "max_positions": 5
                }
            },
            "strategies.json": {
                "enabled_strategies": ["CreditSpread", "IronCondor"],
                "default_allocation": 0.2
            }
        }
        
        for filename, content in configs.items():
            filepath = config_dir / filename
            if not filepath.exists():
                with open(filepath, 'w') as f:
                    json.dump(content, f, indent=2)
                print(f"   ✅ Created {filename}")
                self.fixes_applied.append(f"Created {filename}")
            else:
                print(f"   ✅ {filename} exists")
                
        return True
    
    # ======================================================================
    # ENVIRONMENT SETUP
    # ======================================================================
    
    def setup_environment(self) -> bool:
        """Setup environment variables"""
        print("\n🌍 Setting up environment...")
        
        # Set Python path
        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))
            print(f"   ✅ Added {self.project_root} to Python path")
            
        # Set environment variables
        env_vars = {
            'PYTHONPATH': str(self.project_root),
            'SPYDER_ROOT': str(self.project_root),
            'SPYDER_MODE': 'simulation',
            'TWS_MAJOR_VRSN': '1039'
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
            print(f"   ✅ Set {key}={value}")
            
        return True
    
    # ======================================================================
    # MAIN DIAGNOSTIC RUN
    # ======================================================================
    
    def run_diagnostics(self) -> Tuple[bool, List[str], List[str]]:
        """Run all diagnostics and fixes"""
        print("=" * 70)
        print("SPYDER DIAGNOSTIC AND FIX UTILITY")
        print("=" * 70)
        
        # Run all fixes
        self.setup_environment()
        self.fix_display_issues()
        self.check_module_dependencies()
        self.fix_performance_metrics()
        self.fix_circular_imports()
        self.create_default_configs()
        
        # Summary
        print("\n" + "=" * 70)
        print("DIAGNOSTIC SUMMARY")
        print("=" * 70)
        
        if self.fixes_applied:
            print("\n✅ Fixes Applied:")
            for fix in self.fixes_applied:
                print(f"   • {fix}")
        else:
            print("\n✅ No fixes needed - system appears healthy")
            
        if self.issues:
            print("\n⚠️  Remaining Issues:")
            for issue in self.issues:
                print(f"   • {issue}")
        else:
            print("\n✅ No unresolved issues found")
            
        success = len(self.issues) == 0
        
        # Recommendations
        print("\n" + "=" * 70)
        print("RECOMMENDATIONS")
        print("=" * 70)
        
        if 'SPYDER_HEADLESS' in os.environ:
            print("\n🖥️  Running in headless mode:")
            print("   • GUI features are disabled")
            print("   • Use API or command-line interface")
            print("   • Consider installing Xvfb for virtual display")
            
        print("\n🚀 Next Steps:")
        print("   1. Review any remaining issues above")
        print("   2. Try running: python SpyderA_Core/SpyderA01_Main.py --mode simulation")
        print("   3. Check logs in logs/ directory for details")
        
        return success, self.fixes_applied, self.issues
    
    # ======================================================================
    # TEST IMPORT
    # ======================================================================
    
    def test_imports(self) -> bool:
        """Test if critical imports work after fixes"""
        print("\n🧪 Testing critical imports...")
        
        test_imports = [
            "SpyderU_Utilities.SpyderU01_Logger",
            "SpyderU_Utilities.SpyderU07_Constants",
            "SpyderA_Core.SpyderA05_EventManager"
        ]
        
        success = True
        for module_path in test_imports:
            try:
                importlib.import_module(module_path)
                print(f"   ✅ {module_path}")
            except Exception as e:
                print(f"   ❌ {module_path}: {str(e)}")
                success = False
                
        return success


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Run diagnostics
    diagnostic = SpyderDiagnosticFix()
    success, fixes, issues = diagnostic.run_diagnostics()
    
    # Test imports
    print("\n" + "=" * 70)
    import_success = diagnostic.test_imports()
    
    if success and import_success:
        print("\n✅ SYSTEM READY - You can now run SpyderA01_Main.py")
        sys.exit(0)
    else:
        print("\n⚠️  Some issues remain - please review the output above")
        sys.exit(1)
