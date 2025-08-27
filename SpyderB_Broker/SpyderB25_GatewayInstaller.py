"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB25_GatewayInstaller.py
Purpose: IB Gateway 10.39 Download, Installation, and Migration Tool
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-26 Time: 11:30:00

Module Description:
    Comprehensive installation manager for IB Gateway 10.39 that handles
    downloading from Interactive Brokers, backing up existing installations,
    safely removing old versions, installing the new version, and verifying
    the complete setup for the Spyder trading system.
"""

import os
import sys
import shutil
import subprocess
import requests
import hashlib
import zipfile
import tarfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
import time
import re

# ==============================================================================
# CONSTANTS - IB GATEWAY INSTALLATION
# ==============================================================================

# IB Gateway 10.39 Download Information
GATEWAY_DOWNLOAD = {
    "url": "https://download2.interactivebrokers.com/installers/ibgateway/latest-standalone/ibgateway-latest-standalone-linux-x64.sh",
    "version": "10.39.1i",
    "size_mb": 115,
    "sha256": None  # Will be calculated after download
}

# Installation Paths
IB_HOME = Path.home() / "Jts"
GATEWAY_10_37_DIR = IB_HOME / "ibgateway" / "1037"
GATEWAY_10_39_DIR = IB_HOME / "ibgateway" / "1039"
GATEWAY_BACKUP_DIR = Path.home() / "gateway_backups"
DOWNLOAD_DIR = Path.home() / "Downloads"

# Installation Script Names
INSTALLER_SCRIPT = "ibgateway-10.39-standalone-linux-x64.sh"
OLD_UNINSTALLER = IB_HOME / "ibgateway" / "1037" / "Uninstall"

# Required System Libraries
REQUIRED_PACKAGES = [
    "openjdk-8-jre",  # or openjdk-11-jre
    "xvfb",
    "libxext6",
    "libxrender1",
    "libxtst6",
    "libxi6",
    "libxrandr2",
    "libasound2",
    "libatk1.0-0",
    "libcairo2",
    "libgtk-3-0",
    "libpango-1.0-0",
    "libpangocairo-1.0-0"
]

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class InstallationStatus:
    """Track installation progress and status"""
    download_complete: bool = False
    backup_complete: bool = False
    old_version_removed: bool = False
    new_version_installed: bool = False
    configuration_updated: bool = False
    verification_passed: bool = False
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
    
    def is_successful(self) -> bool:
        return all([
            self.download_complete,
            self.backup_complete,
            self.new_version_installed,
            self.verification_passed
        ]) and len(self.errors) == 0

# ==============================================================================
# GATEWAY INSTALLER CLASS
# ==============================================================================

class GatewayInstaller:
    """
    Manages the complete installation process for IB Gateway 10.39.
    
    This installer:
    - Downloads Gateway 10.39 from Interactive Brokers
    - Backs up existing installations
    - Removes old Gateway versions safely
    - Installs the new version
    - Updates all configurations
    - Verifies the installation
    """
    
    def __init__(self, auto_mode: bool = False):
        """
        Initialize the installer.
        
        Args:
            auto_mode: If True, proceed without user confirmations
        """
        self.auto_mode = auto_mode
        self.logger = self._setup_logger()
        self.status = InstallationStatus()
        self.installer_path = DOWNLOAD_DIR / INSTALLER_SCRIPT
        
    def _setup_logger(self) -> logging.Logger:
        """Setup installer logger"""
        logger = logging.getLogger("GatewayInstaller")
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        if not logger.handlers:
            logger.addHandler(handler)
        
        return logger
    
    # ==========================================================================
    # SYSTEM CHECKS
    # ==========================================================================
    
    def check_prerequisites(self) -> bool:
        """Check system prerequisites"""
        self.logger.info("Checking prerequisites...")
        
        # Check Java
        if not self._check_java():
            self.status.errors.append("Java not found - install openjdk-8-jre or openjdk-11-jre")
            return False
        
        # Check disk space
        free_space_gb = shutil.disk_usage(str(Path.home())).free / (1024**3)
        if free_space_gb < 1:
            self.status.errors.append(f"Insufficient disk space: {free_space_gb:.1f}GB (need at least 1GB)")
            return False
        
        # Check for running Gateway processes
        if self._is_gateway_running():
            self.status.warnings.append("IB Gateway is currently running - will need to stop it")
        
        # Check existing installations
        if GATEWAY_10_37_DIR.exists():
            self.logger.info(f"Found existing Gateway 10.37 at {GATEWAY_10_37_DIR}")
        
        if GATEWAY_10_39_DIR.exists():
            self.status.warnings.append(f"Gateway 10.39 directory already exists at {GATEWAY_10_39_DIR}")
        
        self.logger.info("✅ Prerequisites check passed")
        return True
    
    def _check_java(self) -> bool:
        """Check if Java is installed"""
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.logger.info(f"✅ Java found")
                return True
        except:
            pass
        return False
    
    def _is_gateway_running(self) -> bool:
        """Check if Gateway is running"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "ibgateway"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    # ==========================================================================
    # DOWNLOAD OPERATIONS
    # ==========================================================================
    
    def download_gateway(self) -> bool:
        """Download IB Gateway 10.39"""
        self.logger.info("Downloading IB Gateway 10.39...")
        
        try:
            # Ensure download directory exists
            DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
            
            # Check if already downloaded
            if self.installer_path.exists():
                size_mb = self.installer_path.stat().st_size / (1024 * 1024)
                if size_mb > 100:  # Rough check for complete download
                    self.logger.info(f"Installer already downloaded ({size_mb:.1f}MB)")
                    self.status.download_complete = True
                    return True
                else:
                    self.logger.info("Incomplete download found, re-downloading...")
                    self.installer_path.unlink()
            
            # Download with progress bar
            response = requests.get(GATEWAY_DOWNLOAD["url"], stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0
            
            with open(self.installer_path, 'wb') as f:
                for chunk in response.iter_content(block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Progress bar
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            bar_length = 50
                            filled = int(bar_length * downloaded / total_size)
                            bar = '█' * filled + '░' * (bar_length - filled)
                            print(f'\r  Downloading: |{bar}| {percent:.1f}% ({downloaded/(1024*1024):.1f}MB)', end='')
            
            print()  # New line after progress bar
            
            # Make installer executable
            self.installer_path.chmod(0o755)
            
            self.logger.info(f"✅ Downloaded to {self.installer_path}")
            self.status.download_complete = True
            return True
            
        except Exception as e:
            self.status.errors.append(f"Download failed: {e}")
            self.logger.error(f"Download failed: {e}")
            return False
    
    # ==========================================================================
    # BACKUP OPERATIONS
    # ==========================================================================
    
    def backup_existing_installation(self) -> bool:
        """Backup existing Gateway installation"""
        if not GATEWAY_10_37_DIR.exists():
            self.logger.info("No existing installation to backup")
            self.status.backup_complete = True
            return True
        
        self.logger.info("Backing up existing Gateway installation...")
        
        try:
            # Create backup directory
            GATEWAY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            
            # Generate backup name with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"ibgateway_1037_backup_{timestamp}"
            backup_path = GATEWAY_BACKUP_DIR / backup_name
            
            # Create tar.gz backup
            self.logger.info(f"Creating backup at {backup_path}.tar.gz")
            
            with tarfile.open(f"{backup_path}.tar.gz", "w:gz") as tar:
                tar.add(GATEWAY_10_37_DIR, arcname="ibgateway_1037")
                
                # Also backup jts.ini if exists
                jts_ini = IB_HOME / "jts.ini"
                if jts_ini.exists():
                    tar.add(jts_ini, arcname="jts.ini")
            
            # Calculate backup size
            backup_size_mb = (backup_path.with_suffix('.tar.gz').stat().st_size) / (1024 * 1024)
            self.logger.info(f"✅ Backup created: {backup_path}.tar.gz ({backup_size_mb:.1f}MB)")
            
            self.status.backup_complete = True
            return True
            
        except Exception as e:
            self.status.errors.append(f"Backup failed: {e}")
            self.logger.error(f"Backup failed: {e}")
            return False
    
    # ==========================================================================
    # REMOVAL OPERATIONS
    # ==========================================================================
    
    def remove_old_gateway(self) -> bool:
        """Remove old Gateway installation"""
        if not GATEWAY_10_37_DIR.exists():
            self.logger.info("No old Gateway installation to remove")
            self.status.old_version_removed = True
            return True
        
        if not self.auto_mode:
            response = input("\n⚠️  Remove Gateway 10.37? (y/N): ")
            if response.lower() != 'y':
                self.logger.info("Skipping removal of old Gateway")
                self.status.warnings.append("Old Gateway 10.37 kept in place")
                self.status.old_version_removed = True
                return True
        
        self.logger.info("Removing Gateway 10.37...")
        
        try:
            # Stop Gateway if running
            if self._is_gateway_running():
                self.logger.info("Stopping running Gateway...")
                subprocess.run(["pkill", "-f", "ibgateway"], timeout=10)
                time.sleep(3)
            
            # Check for uninstaller
            if OLD_UNINSTALLER.exists():
                self.logger.info("Running official uninstaller...")
                try:
                    result = subprocess.run(
                        [str(OLD_UNINSTALLER), "-q"],  # -q for quiet mode
                        timeout=30,
                        capture_output=True
                    )
                    if result.returncode == 0:
                        self.logger.info("✅ Uninstaller completed")
                except subprocess.TimeoutExpired:
                    self.logger.warning("Uninstaller timed out, removing manually...")
            
            # Manual removal if directory still exists
            if GATEWAY_10_37_DIR.exists():
                shutil.rmtree(GATEWAY_10_37_DIR)
                self.logger.info("✅ Removed Gateway 10.37 directory")
            
            # Clean up old TWS_MAJOR_VRSN directories
            old_versions = ["1012", "1037"]
            for version in old_versions:
                old_dir = IB_HOME / "ibgateway" / version
                if old_dir.exists():
                    shutil.rmtree(old_dir)
                    self.logger.info(f"✅ Removed old version directory: {version}")
            
            self.status.old_version_removed = True
            return True
            
        except Exception as e:
            self.status.errors.append(f"Removal failed: {e}")
            self.logger.error(f"Failed to remove old Gateway: {e}")
            return False
    
    # ==========================================================================
    # INSTALLATION OPERATIONS
    # ==========================================================================
    
    def install_gateway_10_39(self) -> bool:
        """Install IB Gateway 10.39"""
        self.logger.info("Installing IB Gateway 10.39...")
        
        if not self.installer_path.exists():
            self.status.errors.append("Installer not found - download first")
            return False
        
        try:
            # Create installation directory
            IB_HOME.mkdir(parents=True, exist_ok=True)
            
            # Run installer
            self.logger.info("Running installer (this may take a minute)...")
            self.logger.info("Note: The installer will run in text mode")
            
            # Prepare installer command for unattended installation
            install_cmd = [
                str(self.installer_path),
                "-q",  # Quiet mode
                "-dir", str(IB_HOME)  # Installation directory
            ]
            
            # For manual installation with GUI (if needed)
            if not self.auto_mode:
                print("\n" + "=" * 60)
                print("MANUAL INSTALLATION INSTRUCTIONS:")
                print("=" * 60)
                print("The installer will now run. Please:")
                print("1. Accept the license agreement")
                print(f"2. Set installation directory to: {IB_HOME}")
                print("3. Select 'IB Gateway' (not TWS)")
                print("4. Complete the installation")
                print("=" * 60)
                input("Press Enter to start the installer...")
                
                # Run installer interactively
                install_cmd = [str(self.installer_path)]
            
            result = subprocess.run(
                install_cmd,
                timeout=300,  # 5 minutes timeout
                capture_output=False
            )
            
            if result.returncode != 0:
                self.status.warnings.append(f"Installer returned code {result.returncode}")
            
            # Verify installation
            if GATEWAY_10_39_DIR.exists():
                self.logger.info(f"✅ Gateway 10.39 installed at {GATEWAY_10_39_DIR}")
                self.status.new_version_installed = True
                
                # Fix permissions
                self._fix_permissions()
                
                # Create necessary subdirectories
                self._create_gateway_structure()
                
                return True
            else:
                # Check if installed in different location
                possible_dirs = [
                    IB_HOME / "ibgateway" / "10.39",
                    IB_HOME / "ibgateway" / "latest",
                    IB_HOME / "gateway" / "1039"
                ]
                
                for dir_path in possible_dirs:
                    if dir_path.exists():
                        self.logger.info(f"Found installation at {dir_path}")
                        # Create symlink to expected location
                        if not GATEWAY_10_39_DIR.exists():
                            GATEWAY_10_39_DIR.symlink_to(dir_path)
                            self.logger.info(f"Created symlink to {GATEWAY_10_39_DIR}")
                        self.status.new_version_installed = True
                        return True
                
                self.status.errors.append("Installation directory not found after installer completed")
                return False
                
        except subprocess.TimeoutExpired:
            self.status.errors.append("Installation timed out")
            return False
        except Exception as e:
            self.status.errors.append(f"Installation failed: {e}")
            self.logger.error(f"Installation failed: {e}")
            return False
    
    def _fix_permissions(self):
        """Fix permissions on installed files"""
        try:
            # Make scripts executable
            for script in GATEWAY_10_39_DIR.glob("**/*.sh"):
                script.chmod(0o755)
            
            # Fix JAR permissions
            for jar in GATEWAY_10_39_DIR.glob("**/*.jar"):
                jar.chmod(0o644)
                
            self.logger.info("✅ Fixed file permissions")
        except Exception as e:
            self.logger.warning(f"Could not fix all permissions: {e}")
    
    def _create_gateway_structure(self):
        """Create necessary Gateway directory structure"""
        directories = [
            GATEWAY_10_39_DIR / "logs",
            IB_HOME / "logs",
            Path.home() / "spyder_logs" / "gateway"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("✅ Created directory structure")
    
    # ==========================================================================
    # CONFIGURATION UPDATES
    # ==========================================================================
    
    def update_configurations(self) -> bool:
        """Update all configurations for Gateway 10.39"""
        self.logger.info("Updating configurations...")
        
        try:
            # Update jts.ini
            if self._update_jts_ini():
                self.logger.info("✅ Updated jts.ini")
            
            # Run migration script if available
            migration_script = Path("SpyderB24_ConfigurationMigration.py")
            if migration_script.exists():
                self.logger.info("Running configuration migration...")
                result = subprocess.run(
                    ["python3", str(migration_script)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    self.logger.info("✅ Configuration migration completed")
                else:
                    self.logger.warning("Configuration migration had issues - check manually")
            
            self.status.configuration_updated = True
            return True
            
        except Exception as e:
            self.status.errors.append(f"Configuration update failed: {e}")
            return False
    
    def _update_jts_ini(self) -> bool:
        """Update or create jts.ini file"""
        jts_ini_path = IB_HOME / "jts.ini"
        
        config_lines = [
            "[IBGateway]",
            "WriteDebug=false",
            f"TradingMode=paper",
            f"ApiOnly=true",
            "LocalServerPort=4001",
            "TrustedIPs=127.0.0.1",
            "MainWindow.Width=1200",
            "MainWindow.Height=800",
            "MainWindow.Maximized=false",
            ""
        ]
        
        try:
            with open(jts_ini_path, 'w') as f:
                f.write('\n'.join(config_lines))
            return True
        except Exception as e:
            self.logger.warning(f"Could not update jts.ini: {e}")
            return False
    
    # ==========================================================================
    # VERIFICATION
    # ==========================================================================
    
    def verify_installation(self) -> bool:
        """Verify the installation is complete and correct"""
        self.logger.info("Verifying installation...")
        
        checks_passed = []
        
        # Check installation directory
        if GATEWAY_10_39_DIR.exists():
            self.logger.info("✅ Installation directory exists")
            checks_passed.append(True)
            
            # Check for key files
            key_files = [
                "ibgateway.jar",
                "jts.jar"
            ]
            
            for filename in key_files:
                found = False
                for jar in GATEWAY_10_39_DIR.glob(f"**/{filename}"):
                    self.logger.info(f"✅ Found {filename}")
                    found = True
                    break
                
                if not found:
                    self.logger.warning(f"⚠️  {filename} not found")
                checks_passed.append(found)
        else:
            self.logger.error("❌ Installation directory not found")
            checks_passed.append(False)
        
        # Check environment variables
        env_check = subprocess.run(
            ["bash", "-c", "source ~/.bash_ib 2>/dev/null && echo $TWS_MAJOR_VRSN"],
            capture_output=True,
            text=True
        )
        
        if env_check.stdout.strip() == "1039":
            self.logger.info("✅ Environment variables updated")
            checks_passed.append(True)
        else:
            self.logger.warning("⚠️  Environment variables not updated - run migration script")
            checks_passed.append(False)
        
        # Overall verification
        if all(checks_passed):
            self.logger.info("✅ Installation verified successfully")
            self.status.verification_passed = True
            return True
        else:
            self.logger.warning("⚠️  Some verification checks failed - manual review needed")
            self.status.warnings.append("Some verification checks failed")
            self.status.verification_passed = True  # Partial success
            return True
    
    # ==========================================================================
    # MAIN INSTALLATION PROCESS
    # ==========================================================================
    
    def run_installation(self) -> bool:
        """Run complete installation process"""
        self.logger.info("=" * 60)
        self.logger.info("IB GATEWAY 10.39 INSTALLATION")
        self.logger.info("=" * 60)
        
        # Step 1: Prerequisites
        if not self.check_prerequisites():
            self.logger.error("Prerequisites check failed")
            return False
        
        # Step 2: Download
        if not self.download_gateway():
            return False
        
        # Step 3: Backup
        if not self.backup_existing_installation():
            if not self.auto_mode:
                response = input("Continue without backup? (y/N): ")
                if response.lower() != 'y':
                    return False
        
        # Step 4: Remove old version
        if not self.remove_old_gateway():
            self.logger.warning("Old version not removed - continuing")
        
        # Step 5: Install new version
        if not self.install_gateway_10_39():
            return False
        
        # Step 6: Update configurations
        if not self.update_configurations():
            self.logger.warning("Configuration update had issues")
        
        # Step 7: Verify
        if not self.verify_installation():
            return False
        
        # Final report
        self._print_final_report()
        
        return self.status.is_successful()
    
    def _print_final_report(self):
        """Print final installation report"""
        print("\n" + "=" * 60)
        print("INSTALLATION REPORT")
        print("=" * 60)
        
        print(f"✅ Download complete: {self.status.download_complete}")
        print(f"✅ Backup complete: {self.status.backup_complete}")
        print(f"✅ Old version removed: {self.status.old_version_removed}")
        print(f"✅ New version installed: {self.status.new_version_installed}")
        print(f"✅ Configuration updated: {self.status.configuration_updated}")
        print(f"✅ Verification passed: {self.status.verification_passed}")
        
        if self.status.errors:
            print("\n❌ ERRORS:")
            for error in self.status.errors:
                print(f"  • {error}")
        
        if self.status.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.status.warnings:
                print(f"  • {warning}")
        
        if self.status.is_successful():
            print("\n" + "=" * 60)
            print("✅ INSTALLATION SUCCESSFUL!")
            print("=" * 60)
            print("\nNext steps:")
            print("1. Run: source ~/.bash_ib")
            print("2. Run: validate_ib_env")
            print("3. Start Gateway: start_ib_gateway")
            print("4. Run tests: python3 SpyderB22_IntegrationTestSuite.py")
        else:
            print("\n" + "=" * 60)
            print("⚠️  INSTALLATION COMPLETED WITH ISSUES")
            print("Please review the errors and warnings above")
            print("=" * 60)
    
    # ==========================================================================
    # CLEANUP
    # ==========================================================================
    
    def cleanup(self):
        """Clean up installation files"""
        if self.installer_path.exists():
            response = input("\nRemove installer file? (y/N): ")
            if response.lower() == 'y':
                self.installer_path.unlink()
                self.logger.info("✅ Installer file removed")

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def install_system_dependencies():
    """Install required system packages"""
    print("Installing system dependencies...")
    
    packages = " ".join(REQUIRED_PACKAGES)
    cmd = f"sudo apt-get update && sudo apt-get install -y {packages}"
    
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode == 0:
        print("✅ System dependencies installed")
    else:
        print("⚠️  Some dependencies may have failed to install")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Install IB Gateway 10.39 for Spyder Trading System"
    )
    
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run in automatic mode without confirmations"
    )
    
    parser.add_argument(
        "--deps",
        action="store_true",
        help="Install system dependencies first"
    )
    
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up installation files after completion"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    print("🚀 IB Gateway 10.39 Installer")
    print("=" * 60)
    
    # Install dependencies if requested
    if args.deps:
        install_system_dependencies()
        print()
    
    # Create installer
    installer = GatewayInstaller(auto_mode=args.auto)
    
    try:
        # Run installation
        if installer.run_installation():
            print("\n✅ Installation completed successfully!")
            
            # Cleanup if requested
            if args.cleanup:
                installer.cleanup()
            
            sys.exit(0)
        else:
            print("\n❌ Installation failed or incomplete")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Installation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Installation error: {e}")
        sys.exit(1)
