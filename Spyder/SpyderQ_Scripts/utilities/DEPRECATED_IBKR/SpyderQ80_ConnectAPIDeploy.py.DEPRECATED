#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ80_ConnectAPIDeploy.py
Purpose: Connect API deployment utility

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-10-20 Time: 22:25:00

Module Description:
    This script provides utilities for deploying the Connect API integration.
    It handles the installation, configuration, and verification of the Connect API
    components required for the migration from IB Gateway/TWS API.

Module Constants:
    DEFAULT_INSTALL_DIR (str): Default installation directory
    DEFAULT_CONFIG_DIR (str): Default configuration directory
    DEFAULT_LOG_DIR (str): Default log directory
    DEPLOYMENT_LOG_FILE (str): Deployment log file name

Change Log:
    2025-10-20 (v1.0.0):
        - Initial script creation
        - Implemented core deployment functionality
        - Added installation and configuration steps
        - Implemented verification and rollback capabilities

    2025-10-15 (v0.9.0):
        - Beta version for testing
        - Basic deployment structure
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import asyncio
import json
import uuid
import warnings
import shutil
import subprocess
import platform
import stat
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import argparse
import yaml

# Import configuration migration
from SpyderI_Integration.SpyderI07_ConfigurationMigration import (
    ConfigurationMigration, MigrationConfig, MigrationResult
)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import Connect API components
from SpyderB_Broker.SpyderB01_ConnectAPI import ConnectAPI
from SpyderB_Broker.SpyderB02_OrderManager import OrderManager
from SpyderC_MarketData.SpyderC02_MarketDataFeed import MarketDataFeed
from SpyderE_Risk.SpyderE01_RiskManager import RiskManager

# Import configuration migration
from SpyderI_Integration.SpyderI07_ConfigurationMigration import (
    ConfigurationMigration, MigrationConfig, run_migration
)

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_INSTALL_DIR = "/opt/spyder"
DEFAULT_CONFIG_DIR = "config"
DEFAULT_LOG_DIR = "logs"
DEPLOYMENT_LOG_FILE = "deployment.log"

# ==============================================================================
# ENUMS
# ==============================================================================
class DeploymentResult(Enum):
    """Deployment result status"""
    SUCCESS = auto()
    PARTIAL_SUCCESS = auto()
    FAILED = auto()
    ROLLED_BACK = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class DeploymentConfig:
    """Deployment configuration"""
    install_dir: str = DEFAULT_INSTALL_DIR
    config_dir: str = DEFAULT_CONFIG_DIR
    log_dir: str = DEFAULT_LOG_DIR
    source_config_file: str = ""
    dry_run: bool = True
    create_backup: bool = True
    verify_installation: bool = True
    rollback_on_failure: bool = True
    service_user: str = "spyder"
    service_group: str = "spyder"

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class ConnectAPIDeployer:
    """
    Connect API deployment utility.

    This class provides utilities for deploying the Connect API integration.
    It handles the installation, configuration, and verification of the Connect API
    components required for the migration from IB Gateway/TWS API.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        config: Deployment configuration
        deployment_log: Deployment log entries
        _deployment_lock: Thread lock for deployment operations
    """

    def __init__(self, config: DeploymentConfig):
        """
        Initialize the Connect API deployer.

        Args:
            config: Deployment configuration
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config

        # Deployment management
        self.deployment_log: List[str] = []
        self._deployment_lock = threading.RLock()

        self.logger.info("ConnectAPIDeployer initialized")

    def deploy(self) -> DeploymentResult:
        """
        Perform the Connect API deployment.

        Returns:
            Deployment result status
        """
        try:
            with self._deployment_lock:
                self._log("Starting Connect API deployment...")

                # Check prerequisites
                if not self._check_prerequisites():
                    self._log("Prerequisites check failed")
                    return DeploymentResult.FAILED

                # Create directories
                if not self._create_directories():
                    self._log("Failed to create directories")
                    return DeploymentResult.FAILED

                # Install dependencies
                if not self._install_dependencies():
                    self._log("Failed to install dependencies")
                    return DeploymentResult.FAILED

                # Migrate configuration
                if self.config.source_config_file:
                    migration_result = self._migrate_configuration()
                    if migration_result != MigrationResult.SUCCESS:
                        self._log("Configuration migration failed")
                        return DeploymentResult.FAILED

                # Install service files
                if not self._install_service_files():
                    self._log("Failed to install service files")
                    return DeploymentResult.FAILED

                # Set permissions
                if not self._set_permissions():
                    self._log("Failed to set permissions")
                    return DeploymentResult.FAILED

                # Verify installation
                if self.config.verify_installation and not self._verify_installation():
                    self._log("Installation verification failed")

                    # Rollback if enabled
                    if self.config.rollback_on_failure:
                        self._rollback()
                        return DeploymentResult.ROLLED_BACK

                    return DeploymentResult.FAILED

                self._log("Connect API deployment completed successfully")
                return DeploymentResult.SUCCESS

        except Exception as e:
            self.logger.error(f"Connect API deployment failed: {e}")
            self.error_handler.handle_error(e, "deploy")
            self._log(f"Connect API deployment failed: {str(e)}")

            # Rollback if enabled
            if self.config.rollback_on_failure:
                self._rollback()
                return DeploymentResult.ROLLED_BACK

            return DeploymentResult.FAILED

    def _check_prerequisites(self) -> bool:
        """
        Check deployment prerequisites.

        Returns:
            True if prerequisites are met
        """
        try:
            self._log("Checking prerequisites...")

            # Check Python version
            if sys.version_info < (3, 8):
                self._log(f"Python 3.8+ required, found {sys.version}")
                return False

            # Check operating system
            if platform.system() not in ["Linux", "Darwin", "Windows"]:
                self._log(f"Unsupported operating system: {platform.system()}")
                return False

            # Check if running as root (for system installation)
            if platform.system() == "Linux" and os.geteuid() != 0:
                self._log("System installation requires root privileges")
                return False

            # Check required Python packages
            required_packages = [
                "websockets",
                "numpy",
                "pandas",
                "PyQt5",
                "pyyaml"
            ]

            for package in required_packages:
                try:
                    __import__(package)
                except ImportError:
                    self._log(f"Required package not found: {package}")
                    return False

            self._log("Prerequisites check passed")
            return True

        except Exception as e:
            self.logger.error(f"Error checking prerequisites: {e}")
            self.error_handler.handle_error(e, "_check_prerequisites")
            self._log(f"Error checking prerequisites: {str(e)}")
            return False

    def _create_directories(self) -> bool:
        """
        Create required directories.

        Returns:
            True if directories created successfully
        """
        try:
            self._log("Creating directories...")

            # Create installation directory
            os.makedirs(self.config.install_dir, exist_ok=True)

            # Create configuration directory
            config_dir = os.path.join(self.config.install_dir, self.config.config_dir)
            os.makedirs(config_dir, exist_ok=True)

            # Create log directory
            log_dir = os.path.join(self.config.install_dir, self.config.log_dir)
            os.makedirs(log_dir, exist_ok=True)

            # Create data directory
            data_dir = os.path.join(self.config.install_dir, "data")
            os.makedirs(data_dir, exist_ok=True)

            # Create backup directory
            backup_dir = os.path.join(self.config.install_dir, "config_backups")
            os.makedirs(backup_dir, exist_ok=True)

            self._log("Directories created successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error creating directories: {e}")
            self.error_handler.handle_error(e, "_create_directories")
            self._log(f"Error creating directories: {str(e)}")
            return False

    def _install_dependencies(self) -> bool:
        """
        Install required dependencies.

        Returns:
            True if dependencies installed successfully
        """
        try:
            self._log("Installing dependencies...")

            # Install Python packages
            packages = [
                "websockets>=10.0",
                "numpy>=1.21.0",
                "pandas>=1.3.0",
                "PyQt5>=5.15.0",
                "pyyaml>=6.0"
            ]

            for package in packages:
                self._log(f"Installing {package}...")

                if self.config.dry_run:
                    self._log(f"Dry run: Would install {package}")
                    continue

                # Install package
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    self._log(f"Failed to install {package}: {result.stderr}")
                    return False

            self._log("Dependencies installed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error installing dependencies: {e}")
            self.error_handler.handle_error(e, "_install_dependencies")
            self._log(f"Error installing dependencies: {str(e)}")
            return False

    def _migrate_configuration(self) -> MigrationResult:
        """
        Migrate configuration from IB Gateway to Connect API.

        Returns:
            Migration result status
        """
        try:
            self._log("Migrating configuration...")

            # Create migration configuration
            migration_config = MigrationConfig(
                source_config_file=self.config.source_config_file,
                target_config_file=os.path.join(
                    self.config.install_dir,
                    self.config.config_dir,
                    "connect_api_config.json"
                ),
                backup_dir=os.path.join(self.config.install_dir, "config_backups"),
                dry_run=self.config.dry_run,
                create_backup=self.config.create_backup,
                validate_config=True,
                rollback_on_failure=self.config.rollback_on_failure
            )

            # Run migration
            migration = ConfigurationMigration(migration_config)
            result = migration.migrate_configuration()

            # Save migration log
            migration.save_migration_log()

            self._log(f"Configuration migration result: {result.name}")
            return result

        except Exception as e:
            self.logger.error(f"Error migrating configuration: {e}")
            self.error_handler.handle_error(e, "_migrate_configuration")
            self._log(f"Error migrating configuration: {str(e)}")
            return MigrationResult.FAILED

    def _install_service_files(self) -> bool:
        """
        Install service files.

        Returns:
            True if service files installed successfully
        """
        try:
            self._log("Installing service files...")

            if platform.system() != "Linux":
                self._log("Service files only supported on Linux")
                return True

            # Create systemd service file
            service_content = f"""[Unit]
Description=SPYDER Connect API Service
After=network.target

[Service]
Type=simple
User={self.config.service_user}
Group={self.config.service_group}
WorkingDirectory={self.config.install_dir}
ExecStart={sys.executable} {os.path.join(self.config.install_dir, "main.py")}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

            service_file = os.path.join(
                self.config.install_dir,
                "spyder-connect-api.service"
            )

            if not self.config.dry_run:
                with open(service_file, 'w') as f:
                    f.write(service_content)

                # Install service
                subprocess.run([
                    "cp", service_file, "/etc/systemd/system/"
                ], check=True)

                # Reload systemd
                subprocess.run([
                    "systemctl", "daemon-reload"
                ], check=True)

                # Enable service
                subprocess.run([
                    "systemctl", "enable", "spyder-connect-api"
                ], check=True)

            self._log("Service files installed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error installing service files: {e}")
            self.error_handler.handle_error(e, "_install_service_files")
            self._log(f"Error installing service files: {str(e)}")
            return False

    def _set_permissions(self) -> bool:
        """
        Set file and directory permissions.

        Returns:
            True if permissions set successfully
        """
        try:
            self._log("Setting permissions...")

            if platform.system() != "Linux":
                self._log("Permission setting only supported on Linux")
                return True

            # Set ownership
            subprocess.run([
                "chown", "-R",
                f"{self.config.service_user}:{self.config.service_group}",
                self.config.install_dir
            ], check=True)

            # Set directory permissions
            for root, dirs, files in os.walk(self.config.install_dir):
                for d in dirs:
                    os.chmod(os.path.join(root, d), 0o755)

                for f in files:
                    # Set execute permission for scripts
                    if f.endswith(".py") or f.endswith(".sh"):
                        os.chmod(os.path.join(root, f), 0o755)
                    else:
                        os.chmod(os.path.join(root, f), 0o644)

            self._log("Permissions set successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error setting permissions: {e}")
            self.error_handler.handle_error(e, "_set_permissions")
            self._log(f"Error setting permissions: {str(e)}")
            return False

    def _verify_installation(self) -> bool:
        """
        Verify the installation.

        Returns:
            True if installation is verified
        """
        try:
            self._log("Verifying installation...")

            # Check if directories exist
            required_dirs = [
                self.config.install_dir,
                os.path.join(self.config.install_dir, self.config.config_dir),
                os.path.join(self.config.install_dir, self.config.log_dir),
                os.path.join(self.config.install_dir, "data")
            ]

            for dir_path in required_dirs:
                if not os.path.exists(dir_path):
                    self._log(f"Required directory not found: {dir_path}")
                    return False

            # Check if configuration file exists
            config_file = os.path.join(
                self.config.install_dir,
                self.config.config_dir,
                "connect_api_config.json"
            )

            if not os.path.exists(config_file):
                self._log(f"Configuration file not found: {config_file}")
                return False

            # Load and validate configuration
            with open(config_file, 'r') as f:
                config_data = json.load(f)

            # Check required configuration fields
            required_fields = ["api_key", "client_id", "account"]
            for field in required_fields:
                if field not in config_data:
                    self._log(f"Required configuration field not found: {field}")
                    return False

            self._log("Installation verification passed")
            return True

        except Exception as e:
            self.logger.error(f"Error verifying installation: {e}")
            self.error_handler.handle_error(e, "_verify_installation")
            self._log(f"Error verifying installation: {str(e)}")
            return False

    def _rollback(self) -> bool:
        """
        Rollback the deployment.

        Returns:
            True if rollback successful
        """
        try:
            self._log("Rolling back deployment...")

            # Remove service
            if platform.system() == "Linux":
                try:
                    subprocess.run([
                        "systemctl", "stop", "spyder-connect-api"
                    ], check=False)

                    subprocess.run([
                        "systemctl", "disable", "spyder-connect-api"
                    ], check=False)

                    subprocess.run([
                        "rm", "-f", "/etc/systemd/system/spyder-connect-api.service"
                    ], check=False)

                    subprocess.run([
                        "systemctl", "daemon-reload"
                    ], check=False)
                except subprocess.CalledProcessError:
                    pass  # Ignore errors during rollback

            # Remove installation directory
            if os.path.exists(self.config.install_dir):
                shutil.rmtree(self.config.install_dir)

            self._log("Deployment rollback completed")
            return True

        except Exception as e:
            self.logger.error(f"Error rolling back deployment: {e}")
            self.error_handler.handle_error(e, "_rollback")
            self._log(f"Error rolling back deployment: {str(e)}")
            return False

    def _log(self, message: str):
        """
        Add message to deployment log.

        Args:
            message: Log message
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.deployment_log.append(log_entry)
        self.logger.info(message)

    def save_deployment_log(self) -> bool:
        """
        Save deployment log to file.

        Returns:
            True if log saved successfully
        """
        try:
            log_path = os.path.join(
                self.config.install_dir,
                self.config.log_dir,
                DEPLOYMENT_LOG_FILE
            )

            with open(log_path, 'w') as f:
                f.write("\n".join(self.deployment_log))

            self.logger.info(f"Deployment log saved to {log_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving deployment log: {e}")
            self.error_handler.handle_error(e, "save_deployment_log")
            return False


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_deployment_config(
    install_dir: str = DEFAULT_INSTALL_DIR,
    config_dir: str = DEFAULT_CONFIG_DIR,
    log_dir: str = DEFAULT_LOG_DIR,
    source_config_file: str = "",
    dry_run: bool = True,
    **kwargs
) -> DeploymentConfig:
    """
    Factory function to create a deployment configuration.

    Args:
        install_dir: Installation directory
        config_dir: Configuration directory
        log_dir: Log directory
        source_config_file: Source configuration file path
        dry_run: Whether to perform a dry run
        **kwargs: Additional configuration parameters

    Returns:
        DeploymentConfig instance
    """
    return DeploymentConfig(
        install_dir=install_dir,
        config_dir=config_dir,
        log_dir=log_dir,
        source_config_file=source_config_file,
        dry_run=dry_run,
        **kwargs
    )


def run_deployment(
    install_dir: str = DEFAULT_INSTALL_DIR,
    config_dir: str = DEFAULT_CONFIG_DIR,
    log_dir: str = DEFAULT_LOG_DIR,
    source_config_file: str = "",
    dry_run: bool = True,
    **kwargs
) -> DeploymentResult:
    """
    Run Connect API deployment.

    Args:
        install_dir: Installation directory
        config_dir: Configuration directory
        log_dir: Log directory
        source_config_file: Source configuration file path
        dry_run: Whether to perform a dry run
        **kwargs: Additional deployment parameters

    Returns:
        Deployment result status
    """
    # Create deployment configuration
    config = create_deployment_config(
        install_dir=install_dir,
        config_dir=config_dir,
        log_dir=log_dir,
        source_config_file=source_config_file,
        dry_run=dry_run,
        **kwargs
    )

    # Create deployer instance
    deployer = ConnectAPIDeployer(config)

    # Run deployment
    result = deployer.deploy()

    # Save deployment log
    deployer.save_deployment_log()

    return result


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Deploy Connect API integration")
    parser.add_argument("--install-dir", default=DEFAULT_INSTALL_DIR, help="Installation directory")
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR, help="Configuration directory")
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR, help="Log directory")
    parser.add_argument("--source-config", help="Source configuration file")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Perform a dry run")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating backup")
    parser.add_argument("--no-verify", action="store_true", help="Skip installation verification")

    args = parser.parse_args()

    # Run deployment
    result = run_deployment(
        install_dir=args.install_dir,
        config_dir=args.config_dir,
        log_dir=args.log_dir,
        source_config_file=args.source_config,
        dry_run=args.dry_run,
        create_backup=not args.no_backup,
        verify_installation=not args.no_verify
    )

    # Print result
    print(f"Deployment result: {result.name}")