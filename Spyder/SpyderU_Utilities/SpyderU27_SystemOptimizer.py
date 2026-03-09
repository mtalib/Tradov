#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU27_SystemOptimizer.py
Purpose: System-level optimizations for trading performance
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-13 Time: 18:30:00

Module Description:
    This module provides system-level optimizations for the Spyder trading system.
    It handles TCP keep-alive settings, firewall configuration, IB Gateway JVM tuning,
    and other Ubuntu system optimizations that improve trading performance and
    connection reliability. Essential for preventing timeout issues and optimizing
    system resources for high-frequency trading operations.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import subprocess
import platform
from typing import Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import shutil

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import psutil
except ImportError:
    psutil = None

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_TCP_KEEPALIVE_TIME = 60      # seconds (reduced from 7200)
DEFAULT_TCP_KEEPALIVE_INTVL = 15     # seconds
DEFAULT_TCP_KEEPALIVE_PROBES = 5     # number of probes

IB_GATEWAY_PORTS = [4001, 4002]      # Live and Paper trading ports
IB_GATEWAY_JVM_HEAP = "4096m"        # 4GB heap size

# ==============================================================================
# ENUMS
# ==============================================================================
class OptimizationLevel(Enum):
    """System optimization levels"""
    BASIC = "basic"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"
    ULTRA = "ultra"

class SystemComponent(Enum):
    """System components that can be optimized"""
    NETWORK = "network"
    MEMORY = "memory"
    FIREWALL = "firewall"
    JVM = "jvm"
    DOCKER = "docker"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptimizationResult:
    """Result of a system optimization"""
    component: SystemComponent
    success: bool
    message: str
    details: dict[str, Any] | None = None

@dataclass
class SystemDiagnostics:
    """System diagnostic information"""
    os_info: dict[str, str]
    memory_info: dict[str, int]
    network_config: dict[str, Any]
    java_info: dict[str, str] | None
    docker_info: dict[str, str] | None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SystemOptimizer:
    """
    System-level optimizer for trading performance.

    This class provides comprehensive system optimization for the Spyder
    trading system, including network tuning, memory optimization, and
    IB Gateway configuration. Designed specifically for Ubuntu systems
    running automated trading workloads.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        optimization_level: Current optimization level
        applied_optimizations: List of applied optimizations
    """

    def __init__(self, optimization_level: OptimizationLevel = OptimizationLevel.STANDARD):
        """Initialize the system optimizer."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.optimization_level = optimization_level
        self.applied_optimizations: list[OptimizationResult] = []

        self.logger.info(f"SystemOptimizer initialized with {optimization_level.value} level")

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def optimize_tcp_keepalive(self) -> OptimizationResult:
        """
        Optimize TCP keep-alive settings for trading connections.

        Returns:
            OptimizationResult: Result of the optimization
        """
        try:
            if not self._is_root():
                return OptimizationResult(
                    component=SystemComponent.NETWORK,
                    success=False,
                    message="Root privileges required for TCP optimization"
                )

            # Define optimized TCP settings
            tcp_settings = {
                'net.ipv4.tcp_keepalive_time': DEFAULT_TCP_KEEPALIVE_TIME,
                'net.ipv4.tcp_keepalive_intvl': DEFAULT_TCP_KEEPALIVE_INTVL,
                'net.ipv4.tcp_keepalive_probes': DEFAULT_TCP_KEEPALIVE_PROBES,
                'net.ipv4.tcp_fin_timeout': 15,
                'net.ipv4.tcp_tw_reuse': 1,
                'net.core.rmem_default': 262144,
                'net.core.rmem_max': 16777216,
                'net.core.wmem_default': 262144,
                'net.core.wmem_max': 16777216,
            }

            # Apply settings
            failed_settings = []
            for setting, value in tcp_settings.items():
                try:
                    subprocess.run([
                        'sysctl', '-w', f'{setting}={value}'
                    ], check=True, capture_output=True)
                except subprocess.CalledProcessError:
                    failed_settings.append(setting)

            # Make permanent by updating /etc/sysctl.conf
            if not failed_settings:
                self._update_sysctl_conf(tcp_settings)

            success = len(failed_settings) == 0
            message = "TCP keep-alive optimized" if success else f"Failed settings: {failed_settings}"

            result = OptimizationResult(
                component=SystemComponent.NETWORK,
                success=success,
                message=message,
                details={'settings': tcp_settings, 'failed': failed_settings}
            )

            self.applied_optimizations.append(result)
            self.logger.info(f"TCP optimization: {message}")

            return result

        except Exception as e:
            self.logger.error(f"TCP optimization failed: {e}")
            result = OptimizationResult(
                component=SystemComponent.NETWORK,
                success=False,
                message=f"TCP optimization error: {e}"
            )
            self.applied_optimizations.append(result)
            return result

    def configure_firewall(self) -> OptimizationResult:
        """
        Configure UFW firewall for IB Gateway ports.

        Returns:
            OptimizationResult: Result of the optimization
        """
        try:
            if not shutil.which('ufw'):
                return OptimizationResult(
                    component=SystemComponent.FIREWALL,
                    success=False,
                    message="UFW firewall not installed"
                )

            commands_success = []
            commands_failed = []

            # Configure IB Gateway ports
            for port in IB_GATEWAY_PORTS:
                try:
                    subprocess.run([
                        'ufw', 'allow', f'{port}/tcp'
                    ], check=True, capture_output=True)
                    commands_success.append(f"port {port}")
                except subprocess.CalledProcessError as e:
                    commands_failed.append(f"port {port}: {e}")

            # Enable UFW if not already enabled
            try:
                subprocess.run([
                    'ufw', '--force', 'enable'
                ], check=True, capture_output=True)
                commands_success.append("firewall enabled")
            except subprocess.CalledProcessError as e:
                commands_failed.append(f"enable firewall: {e}")

            success = len(commands_failed) == 0
            message = "Firewall configured" if success else f"Failed: {commands_failed}"

            result = OptimizationResult(
                component=SystemComponent.FIREWALL,
                success=success,
                message=message,
                details={'success': commands_success, 'failed': commands_failed}
            )

            self.applied_optimizations.append(result)
            self.logger.info(f"Firewall configuration: {message}")

            return result

        except Exception as e:
            self.logger.error(f"Firewall configuration failed: {e}")
            result = OptimizationResult(
                component=SystemComponent.FIREWALL,
                success=False,
                message=f"Firewall configuration error: {e}"
            )
            self.applied_optimizations.append(result)
            return result

    def optimize_ib_gateway_jvm(self) -> OptimizationResult:
        """
        Generate optimized JVM settings for IB Gateway.

        Returns:
            OptimizationResult: Result of the optimization
        """
        try:
            # Generate optimized JVM arguments
            jvm_args = [
                f"-Xmx{IB_GATEWAY_JVM_HEAP}",
                f"-Xms{IB_GATEWAY_JVM_HEAP}",
                "-XX:+UseG1GC",
                "-XX:MaxGCPauseMillis=100",
                "-XX:+UseStringDeduplication",
                "-XX:+OptimizeStringConcat",
                "-XX:+UseCompressedOops",
                "-Djava.net.preferIPv4Stack=true",
                "-Dsun.net.useExclusiveBind=false"
            ]

            # Create JVM configuration file
            jvm_config_path = Path.home() / ".ibgateway" / "jvm_args.txt"
            jvm_config_path.parent.mkdir(exist_ok=True)

            with open(jvm_config_path, 'w') as f:
                for arg in jvm_args:
                    f.write(f"{arg}\n")

            result = OptimizationResult(
                component=SystemComponent.JVM,
                success=True,
                message=f"JVM configuration saved to {jvm_config_path}",
                details={'jvm_args': jvm_args, 'config_path': str(jvm_config_path)}
            )

            self.applied_optimizations.append(result)
            self.logger.info(f"JVM optimization: {result.message}")

            return result

        except Exception as e:
            self.logger.error(f"JVM optimization failed: {e}")
            result = OptimizationResult(
                component=SystemComponent.JVM,
                success=False,
                message=f"JVM optimization error: {e}"
            )
            self.applied_optimizations.append(result)
            return result

    def generate_docker_compose(self) -> OptimizationResult:
        """
        Generate optimized Docker Compose configuration for IB Gateway.

        Returns:
            OptimizationResult: Result of the optimization
        """
        try:
            docker_compose = {
                'version': '3.8',
                'services': {
                    'ib-gateway': {
                        'image': 'ghcr.io/gnzsnz/ib-gateway:latest',
                        'container_name': 'spyder-ib-gateway',
                        'environment': {
                            'TWS_USERID': '${TWS_USERID}',
                            'TWS_PASSWORD': '${TWS_PASSWORD}',
                            'TRADING_MODE': 'paper',
                            'READ_ONLY_API': 'no',
                            'TWOFA_TIMEOUT_TIME': '180',
                            'JAVA_OPTS': f'-Xmx{IB_GATEWAY_JVM_HEAP} -Xms{IB_GATEWAY_JVM_HEAP} -XX:+UseG1GC'
                        },
                        'ports': [
                            '4001:4001',  # Live trading
                            '4002:4002',  # Paper trading
                            '5900:5900'   # VNC
                        ],
                        'volumes': [
                            './ib-gateway-data:/home/ibgateway',
                            '/etc/localtime:/etc/localtime:ro'
                        ],
                        'restart': 'unless-stopped',
                        'mem_limit': '6g',
                        'cpus': '2.0',
                        'healthcheck': {
                            'test': ['CMD', 'nc', '-z', 'localhost', '4002'],
                            'interval': '30s',
                            'timeout': '10s',
                            'retries': 3,
                            'start_period': '60s'
                        }
                    }
                }
            }

            # Save Docker Compose file
            compose_path = Path.cwd() / "docker-compose.yml"

            import yaml
            with open(compose_path, 'w') as f:
                yaml.dump(docker_compose, f, default_flow_style=False, indent=2)

            # Create .env template
            env_path = Path.cwd() / ".env.template"
            with open(env_path, 'w') as f:
                f.write("# IB Gateway Configuration\n")
                f.write("TWS_USERID=your_ib_username\n")
                f.write("TWS_PASSWORD=your_ib_password\n")

            result = OptimizationResult(
                component=SystemComponent.DOCKER,
                success=True,
                message=f"Docker Compose configuration saved to {compose_path}",
                details={'compose_path': str(compose_path), 'env_path': str(env_path)}
            )

            self.applied_optimizations.append(result)
            self.logger.info(f"Docker optimization: {result.message}")

            return result

        except Exception as e:
            self.logger.error(f"Docker Compose generation failed: {e}")
            result = OptimizationResult(
                component=SystemComponent.DOCKER,
                success=False,
                message=f"Docker Compose error: {e}"
            )
            self.applied_optimizations.append(result)
            return result

    def run_system_diagnostics(self) -> SystemDiagnostics:
        """
        Run comprehensive system diagnostics.

        Returns:
            SystemDiagnostics: System diagnostic information
        """
        try:
            # OS Information
            os_info = {
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor()
            }

            # Memory Information
            memory_info = {}
            if psutil:
                mem = psutil.virtual_memory()
                memory_info = {
                    'total': mem.total,
                    'available': mem.available,
                    'percent': mem.percent,
                    'used': mem.used,
                    'free': mem.free
                }

            # Network Configuration
            network_config = self._get_network_config()

            # Java Information
            java_info = self._get_java_info()

            # Docker Information
            docker_info = self._get_docker_info()

            diagnostics = SystemDiagnostics(
                os_info=os_info,
                memory_info=memory_info,
                network_config=network_config,
                java_info=java_info,
                docker_info=docker_info
            )

            self.logger.info("System diagnostics completed")
            return diagnostics

        except Exception as e:
            self.logger.error(f"System diagnostics failed: {e}")
            return SystemDiagnostics({}, {}, {}, None, None)

    def optimize_all(self) -> list[OptimizationResult]:
        """
        Run all system optimizations.

        Returns:
            List[OptimizationResult]: Results of all optimizations
        """
        results = []

        self.logger.info(f"Starting system optimization (level: {self.optimization_level.value})")

        # Run optimizations based on level
        if self.optimization_level in [OptimizationLevel.STANDARD, OptimizationLevel.AGGRESSIVE, OptimizationLevel.ULTRA]:
            results.append(self.optimize_tcp_keepalive())
            results.append(self.configure_firewall())
            results.append(self.optimize_ib_gateway_jvm())

        if self.optimization_level in [OptimizationLevel.AGGRESSIVE, OptimizationLevel.ULTRA]:
            results.append(self.generate_docker_compose())

        successful = len([r for r in results if r.success])
        total = len(results)

        self.logger.info(f"System optimization completed: {successful}/{total} successful")

        return results

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _is_root(self) -> bool:
        """Check if running as root."""
        return os.geteuid() == 0

    def _update_sysctl_conf(self, settings: dict[str, Any]) -> None:
        """Update /etc/sysctl.conf with settings."""
        try:
            sysctl_path = Path("/etc/sysctl.conf")

            # Read existing content
            existing_content = ""
            if sysctl_path.exists():
                with open(sysctl_path) as f:
                    existing_content = f.read()

            # Add Spyder section
            spyder_section = "\n# Spyder Trading System Optimizations\n"
            for setting, value in settings.items():
                spyder_section += f"{setting} = {value}\n"

            # Write updated content
            with open(sysctl_path, 'w') as f:
                f.write(existing_content + spyder_section)

        except Exception as e:
            self.logger.error(f"Failed to update sysctl.conf: {e}")

    def _get_network_config(self) -> dict[str, Any]:
        """Get current network configuration."""
        try:
            # Get TCP keep-alive settings
            tcp_settings = {}
            tcp_params = [
                'net.ipv4.tcp_keepalive_time',
                'net.ipv4.tcp_keepalive_intvl',
                'net.ipv4.tcp_keepalive_probes'
            ]

            for param in tcp_params:
                try:
                    result = subprocess.run([
                        'sysctl', '-n', param
                    ], capture_output=True, text=True, check=True)
                    tcp_settings[param] = int(result.stdout.strip())
                except Exception:
                    tcp_settings[param] = None

            return {'tcp_keepalive': tcp_settings}

        except Exception:
            return {}

    def _get_java_info(self) -> dict[str, str] | None:
        """Get Java installation information."""
        try:
            result = subprocess.run([
                'java', '-version'
            ], capture_output=True, text=True)

            if result.returncode == 0:
                version_output = result.stderr  # Java outputs version to stderr
                return {
                    'available': True,
                    'version_output': version_output
                }
            else:
                return {'available': False}

        except FileNotFoundError:
            return {'available': False}
        except Exception:
            return None

    def _get_docker_info(self) -> dict[str, str] | None:
        """Get Docker installation information."""
        try:
            result = subprocess.run([
                'docker', '--version'
            ], capture_output=True, text=True)

            if result.returncode == 0:
                return {
                    'available': True,
                    'version': result.stdout.strip()
                }
            else:
                return {'available': False}

        except FileNotFoundError:
            return {'available': False}
        except Exception:
            return None

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_system_optimizer(level: OptimizationLevel = OptimizationLevel.STANDARD) -> SystemOptimizer:
    """
    Get system optimizer instance.

    Args:
        level: Optimization level

    Returns:
        SystemOptimizer instance
    """
    return SystemOptimizer(level)

def optimize_system_for_trading() -> list[OptimizationResult]:
    """
    Quick function to optimize system for trading.

    Returns:
        List of optimization results
    """
    optimizer = SystemOptimizer(OptimizationLevel.STANDARD)
    return optimizer.optimize_all()

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level instance
_system_optimizer_instance: SystemOptimizer | None = None

def get_global_optimizer() -> SystemOptimizer:
    """
    Get global system optimizer instance.

    Returns:
        SystemOptimizer instance
    """
    global _system_optimizer_instance
    if _system_optimizer_instance is None:
        _system_optimizer_instance = SystemOptimizer()
    return _system_optimizer_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    optimizer = SystemOptimizer()

    diagnostics = optimizer.run_system_diagnostics()

    jvm_result = optimizer.optimize_ib_gateway_jvm()

    docker_result = optimizer.generate_docker_compose()

