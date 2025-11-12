#!/usr/bin/env python3
"""
Spyder System Validation Script
Tests all critical components and identifies issues
"""

import sys
import socket
import asyncio
from datetime import datetime
from typing import Tuple

# Color codes for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'


class SpyderValidator:
    """Comprehensive system validator."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        
    def print_header(self, text: str) -> None:
        """Print section header."""
        print(f"\n{BOLD}{CYAN}{'=' * 80}{RESET}")
        print(f"{BOLD}{CYAN}{text.center(80)}{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 80}{RESET}\n")
        
    def print_test(self, name: str, passed: bool, message: str = "") -> None:
        """Print test result."""
        if passed:
            print(f"{GREEN}✓{RESET} {name}")
            if message:
                print(f"  {message}")
            self.passed += 1
        else:
            print(f"{RED}✗{RESET} {name}")
            if message:
                print(f"  {RED}{message}{RESET}")
            self.failed += 1
            
    def print_warning(self, name: str, message: str) -> None:
        """Print warning."""
        print(f"{YELLOW}⚠{RESET} {name}")
        print(f"  {YELLOW}{message}{RESET}")
        self.warnings += 1
        
    def check_ib_gateway(self) -> Tuple[bool, str]:
        """Check if IB Gateway is running."""
        ports_to_check = [
            (4002, "Paper Trading"),
            (4001, "Live Trading"),
            (7497, "TWS Paper"),
            (7496, "TWS Live")
        ]
        
        for port, mode in ports_to_check:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('127.0.0.1', port))
                sock.close()
                
                if result == 0:
                    return True, f"IB Gateway/TWS detected on port {port} ({mode})"
            except Exception as e:
                continue
                
        return False, "No IB Gateway/TWS detected on any standard port"
        
    def check_import(self, module_name: str) -> Tuple[bool, str]:
        """Check if a module can be imported."""
        try:
            __import__(module_name)
            return True, f"{module_name} imported successfully"
        except ImportError as e:
            return False, f"Failed to import {module_name}: {e}"
            
    def check_python_version(self) -> Tuple[bool, str]:
        """Check Python version."""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 9:
            return True, f"Python {version.major}.{version.minor}.{version.micro}"
        else:
            return False, f"Python {version.major}.{version.minor} is too old (need 3.9+)"
            
    async def check_ib_async_connection(self) -> Tuple[bool, str]:
        """Test actual IB async connection."""
        try:
            from ib_async import IB
            
            ib = IB()
            
            # Try paper trading port first
            ports = [4002, 4001, 7497, 7496]
            
            for port in ports:
                try:
                    await asyncio.wait_for(
                        ib.connectAsync('127.0.0.1', port, clientId=999),
                        timeout=5
                    )
                    
                    if ib.isConnected():
                        ib.disconnect()
                        return True, f"Successfully connected to port {port}"
                        
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    continue
                    
            return False, "Could not establish test connection to any IB port"
            
        except ImportError:
            return False, "ib_async not installed"
        except Exception as e:
            return False, f"Connection test failed: {e}"
            
    def check_file_exists(self, filepath: str) -> Tuple[bool, str]:
        """Check if critical file exists."""
        import os
        if os.path.exists(filepath):
            return True, f"File found: {filepath}"
        else:
            return False, f"File missing: {filepath}"
            
    def run_validation(self):
        """Run complete validation suite."""
        
        print(f"\n{BOLD}{CYAN}")
        print("=" * 80)
        print("SPYDER TRADING SYSTEM VALIDATION".center(80))
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print(RESET)
        
        # Test 1: Python Environment
        self.print_header("PYTHON ENVIRONMENT")
        passed, msg = self.check_python_version()
        self.print_test("Python Version (3.9+)", passed, msg)
        
        # Test 2: Core Dependencies
        self.print_header("CORE DEPENDENCIES")
        
        dependencies = [
            'PyQt6',
            'numpy',
            'pandas',
            'ib_async',
            'asyncio',
        ]
        
        for dep in dependencies:
            passed, msg = self.check_import(dep)
            self.print_test(f"Import {dep}", passed, msg)
            
        # Test 3: IB Gateway Connection
        self.print_header("IB GATEWAY CONNECTIVITY")
        
        passed, msg = self.check_ib_gateway()
        self.print_test("IB Gateway Running", passed, msg)
        
        # Test async connection if gateway is running
        if passed:
            try:
                loop = asyncio.get_event_loop()
                passed, msg = loop.run_until_complete(
                    self.check_ib_async_connection()
                )
                self.print_test("IB Async Connection Test", passed, msg)
            except Exception as e:
                self.print_test("IB Async Connection Test", False, str(e))
        else:
            self.print_warning(
                "IB Connection Test Skipped",
                "Start IB Gateway/TWS before running connection tests"
            )
            
        # Test 4: Critical Files
        self.print_header("CRITICAL FILES")
        
        critical_files = [
            'SpyderB_Broker/SpyderB08_MultiClientDataManager.py',
            'SpyderG_GUI/SpyderG05_TradingDashboard.py',
            'SpyderU_Utilities/SpyderU01_Logger.py',
            '.env'
        ]
        
        for filepath in critical_files:
            passed, msg = self.check_file_exists(filepath)
            if not passed and filepath == '.env':
                self.print_warning(filepath, "Create .env from .env.template")
            else:
                self.print_test(filepath, passed, msg)
                
        # Test 5: Import Spyder Modules
        self.print_header("SPYDER MODULES")
        
        spyder_modules = [
            'SpyderU_Utilities.SpyderU01_Logger',
            'SpyderU_Utilities.SpyderU02_ErrorHandler',
        ]
        
        for module in spyder_modules:
            passed, msg = self.check_import(module)
            self.print_test(f"Import {module}", passed, msg)
            
        # Summary
        self.print_header("VALIDATION SUMMARY")
        
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"{GREEN}Passed:{RESET}   {self.passed}/{total} ({pass_rate:.1f}%)")
        print(f"{RED}Failed:{RESET}   {self.failed}/{total}")
        print(f"{YELLOW}Warnings:{RESET} {self.warnings}")
        
        if self.failed == 0:
            print(f"\n{GREEN}{BOLD}✓ ALL TESTS PASSED{RESET}")
            print(f"{GREEN}System is ready for operation{RESET}")
        elif self.failed <= 2:
            print(f"\n{YELLOW}{BOLD}⚠ SOME ISSUES DETECTED{RESET}")
            print(f"{YELLOW}Review failed tests above{RESET}")
        else:
            print(f"\n{RED}{BOLD}✗ CRITICAL ISSUES DETECTED{RESET}")
            print(f"{RED}Fix failed tests before running system{RESET}")
            
        print(f"\n{CYAN}{'=' * 80}{RESET}\n")
        
        return self.failed == 0


def main():
    """Run validation."""
    validator = SpyderValidator()
    success = validator.run_validation()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
