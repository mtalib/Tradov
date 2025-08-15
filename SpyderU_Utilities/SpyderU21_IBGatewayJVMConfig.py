#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderU21_IBGatewayJVMConfig.py
Group: U (Utilities)
Purpose: IB Gateway JVM memory configuration and startup optimization
Author: Mohamed Talib
Date Created: 2025-08-15
Last Updated: 2025-08-15 Time: 14:30:00

Description:
    This module configures optimal JVM memory parameters for IB Gateway stability
    and performance. It addresses common API timeout issues by setting proper heap
    sizes, garbage collection parameters, and memory management options. Creates
    optimized startup scripts with institutional-grade JVM settings for reliable
    automated trading operations.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import subprocess
import shutil
import time
import socket
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import psutil

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    # Fallback for standalone testing
    import logging
    SpyderLogger = logging
    SpyderErrorHandler = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
# JVM Memory Configuration (Institutional Grade)
DEFAULT_HEAP_SIZE_GB = 4  # 4GB for stability
MINIMUM_HEAP_SIZE_GB = 2  # Minimum for basic operation
MAXIMUM_HEAP_SIZE_GB = 8  # Maximum before diminishing returns

# IB Gateway Paths
IB_GATEWAY_BASE_DIR = Path.home() / "Jts"
IB_GATEWAY_VERSION_DIRS = ["1037", "1039", "latest"]  # Common version directories

# JVM Stability Parameters
JVM_STABILITY_PARAMS = [
    "-XX:+UseG1GC",                    # Use G1 garbage collector for low latency
    "-XX:MaxGCPauseMillis=250",        # Limit GC pause to 250ms
    "-XX:+UnlockExperimentalVMOptions",
    "-XX:+UseCGroupMemoryLimitForHeap", # Container awareness
    "-XX:+HeapDumpOnOutOfMemoryError", # Crash diagnostics
    "-XX:+ExitOnOutOfMemoryError",     # Clean restart on OOM
    "-XX:+PrintGCDetails",             # GC logging for monitoring
    "-XX:+PrintGCTimeStamps",          # Timestamp GC events
    "-XX:NewRatio=3",                  # Young generation ratio
    "-XX:SurvivorRatio=8",             # Survivor space ratio
    "-Djava.net.preferIPv4Stack=true", # Prefer IPv4 for networking
    "-Dsun.net.useExclusiveBind=false" # Allow port sharing
]

# API Test Configuration
API_TEST_TIMEOUT = 10  # seconds
API_HANDSHAKE_SEQUENCE = [b'API\0', b'v100..176']

# ==============================================================================
# ENUMS
# ==============================================================================
class JVMConfigStatus(Enum):
    """JVM configuration status"""
    OPTIMAL = "optimal"
    NEEDS_ADJUSTMENT = "needs_adjustment"
    INSUFFICIENT_MEMORY = "insufficient_memory"
    ERROR = "error"

class GatewayTestResult(Enum):
    """Gateway API test result"""
    SUCCESS = "success"
    PORT_CLOSED = "port_closed"
    API_TIMEOUT = "api_timeout"
    HANDSHAKE_FAILED = "handshake_failed"
    CONNECTION_ERROR = "connection_error"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SystemMemoryInfo:
    """System memory information"""
    total_gb: float
    available_gb: float
    used_gb: float
    usage_percent: float
    recommended_heap_gb: int
    can_allocate_4gb: bool
    
@dataclass
class JVMConfig:
    """JVM configuration parameters"""
    heap_size_gb: int
    initial_heap_gb: int
    gc_params: List[str]
    stability_params: List[str]
    monitoring_params: List[str]
    
    def get_jvm_args(self) -> List[str]:
        """Get complete JVM arguments list"""
        args = [
            f"-Xms{self.initial_heap_gb}g",
            f"-Xmx{self.heap_size_gb}g"
        ]
        args.extend(self.gc_params)
        args.extend(self.stability_params)
        args.extend(self.monitoring_params)
        return args

@dataclass
class GatewayInfo:
    """IB Gateway installation information"""
    base_dir: Path
    version_dir: Optional[Path]
    jar_file: Optional[Path]
    is_installed: bool
    version: Optional[str]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class IBGatewayJVMConfig:
    """
    IB Gateway JVM memory configuration and optimization manager.
    
    This class provides comprehensive JVM memory configuration for IB Gateway
    to resolve API timeout issues and ensure stable operation. It analyzes
    system resources, generates optimal JVM parameters, and creates startup
    scripts with institutional-grade memory management settings.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        system_memory: System memory information
        jvm_config: Current JVM configuration
        gateway_info: IB Gateway installation info
        
    Example:
        >>> config_manager = IBGatewayJVMConfig()
        >>> config_manager.analyze_system()
        >>> config_manager.optimize_jvm_settings()
        >>> config_manager.create_startup_script()
        >>> config_manager.test_api_connection()
    """
    
    def __init__(self):
        """Initialize the JVM configuration manager."""
        self.logger = SpyderLogger.get_logger(__name__) if SpyderLogger else logging.getLogger(__name__)
        self.error_handler = SpyderErrorHandler() if SpyderErrorHandler else None
        
        self.system_memory: Optional[SystemMemoryInfo] = None
        self.jvm_config: Optional[JVMConfig] = None
        self.gateway_info: Optional[GatewayInfo] = None
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    def analyze_system(self) -> SystemMemoryInfo:
        """
        Analyze system memory and determine optimal JVM settings.
        
        Returns:
            SystemMemoryInfo with recommendations
        """
        try:
            memory = psutil.virtual_memory()
            total_gb = memory.total / (1024**3)
            available_gb = memory.available / (1024**3)
            used_gb = memory.used / (1024**3)
            usage_percent = memory.percent
            
            # Determine recommended heap size
            if available_gb >= 6.0:
                recommended_heap_gb = 4
            elif available_gb >= 4.0:
                recommended_heap_gb = 3
            elif available_gb >= 3.0:
                recommended_heap_gb = 2
            else:
                recommended_heap_gb = 1
            
            can_allocate_4gb = available_gb >= 5.0  # Leave 1GB headroom
            
            self.system_memory = SystemMemoryInfo(
                total_gb=round(total_gb, 1),
                available_gb=round(available_gb, 1),
                used_gb=round(used_gb, 1),
                usage_percent=round(usage_percent, 1),
                recommended_heap_gb=recommended_heap_gb,
                can_allocate_4gb=can_allocate_4gb
            )
            
            self.logger.info(f"System analysis complete - Available: {available_gb:.1f}GB, "
                           f"Recommended heap: {recommended_heap_gb}GB")
            
            return self.system_memory
            
        except Exception as e:
            self.logger.error(f"System analysis failed: {e}")
            raise
    
    def find_gateway_installation(self) -> GatewayInfo:
        """
        Find IB Gateway installation directory and version.
        
        Returns:
            GatewayInfo with installation details
        """
        try:
            base_dir = IB_GATEWAY_BASE_DIR
            version_dir = None
            jar_file = None
            is_installed = False
            version = None
            
            if base_dir.exists():
                # Look for ibgateway subdirectory
                gateway_dir = base_dir / "ibgateway"
                if gateway_dir.exists():
                    # Find version directory
                    for ver_name in IB_GATEWAY_VERSION_DIRS:
                        ver_path = gateway_dir / ver_name
                        if ver_path.exists():
                            version_dir = ver_path
                            version = ver_name
                            break
                    
                    # Look for ibgateway.jar
                    if version_dir:
                        jar_path = version_dir / "ibgateway.jar"
                        if jar_path.exists():
                            jar_file = jar_path
                            is_installed = True
            
            self.gateway_info = GatewayInfo(
                base_dir=base_dir,
                version_dir=version_dir,
                jar_file=jar_file,
                is_installed=is_installed,
                version=version
            )
            
            if is_installed:
                self.logger.info(f"IB Gateway found: {version_dir}")
            else:
                self.logger.warning("IB Gateway installation not found")
            
            return self.gateway_info
            
        except Exception as e:
            self.logger.error(f"Gateway search failed: {e}")
            raise
    
    # ==========================================================================
    # PUBLIC METHODS - CONFIGURATION
    # ==========================================================================
    def create_optimal_jvm_config(self, heap_size_gb: Optional[int] = None) -> JVMConfig:
        """
        Create optimal JVM configuration for IB Gateway.
        
        Args:
            heap_size_gb: Override heap size (uses system analysis if None)
            
        Returns:
            JVMConfig with optimal settings
        """
        try:
            if not self.system_memory:
                self.analyze_system()
            
            # Determine heap size
            if heap_size_gb is None:
                heap_size_gb = self.system_memory.recommended_heap_gb
            
            # Validate heap size
            if heap_size_gb > self.system_memory.available_gb - 1:
                self.logger.warning(f"Requested heap size {heap_size_gb}GB too large, "
                                  f"reducing to {self.system_memory.recommended_heap_gb}GB")
                heap_size_gb = self.system_memory.recommended_heap_gb
            
            # Create configuration
            self.jvm_config = JVMConfig(
                heap_size_gb=heap_size_gb,
                initial_heap_gb=heap_size_gb,  # Fixed size for stability
                gc_params=[
                    "-XX:+UseG1GC",
                    "-XX:MaxGCPauseMillis=250",
                    "-XX:G1HeapRegionSize=16m"
                ],
                stability_params=[
                    "-XX:+HeapDumpOnOutOfMemoryError",
                    f"-XX:HeapDumpPath={Path.home()}/ib_heap_dumps/",
                    "-XX:+ExitOnOutOfMemoryError",
                    "-XX:+UnlockExperimentalVMOptions",
                    "-Djava.net.preferIPv4Stack=true",
                    "-Dsun.net.useExclusiveBind=false"
                ],
                monitoring_params=[
                    "-XX:+PrintGC",
                    "-XX:+PrintGCTimeStamps",
                    f"-Xloggc:{Path.home()}/ib_gc.log"
                ]
            )
            
            self.logger.info(f"JVM config created: {heap_size_gb}GB heap")
            return self.jvm_config
            
        except Exception as e:
            self.logger.error(f"JVM config creation failed: {e}")
            raise
    
    def create_startup_script(self, script_path: Optional[Path] = None) -> Path:
        """
        Create optimized IB Gateway startup script.
        
        Args:
            script_path: Output script path (default: ~/start_ib_gateway_optimized.sh)
            
        Returns:
            Path to created script
        """
        try:
            if not self.gateway_info:
                self.find_gateway_installation()
            
            if not self.gateway_info.is_installed:
                raise RuntimeError("IB Gateway not found - cannot create startup script")
            
            if not self.jvm_config:
                self.create_optimal_jvm_config()
            
            if script_path is None:
                script_path = Path.home() / "start_ib_gateway_optimized.sh"
            
            # Create heap dump directory
            heap_dump_dir = Path.home() / "ib_heap_dumps"
            heap_dump_dir.mkdir(exist_ok=True)
            
            # Generate script content
            jvm_args = " ".join(self.jvm_config.get_jvm_args())
            
            script_content = f'''#!/bin/bash
# Optimized IB Gateway Startup Script
# Generated by Spyder IBGatewayJVMConfig
# Date: {time.strftime("%Y-%m-%d %H:%M:%S")}

echo "================================================"
echo "  Starting IB Gateway with Optimized JVM Settings"
echo "  Heap Size: {self.jvm_config.heap_size_gb}GB"
echo "  Version: {self.gateway_info.version}"
echo "================================================"

# Set environment
export JAVA_OPTS="{jvm_args}"
export IB_GATEWAY_DIR="{self.gateway_info.version_dir}"

# Display memory info
echo "System Memory:"
free -h | grep Mem

echo ""
echo "JVM Arguments:"
echo "{jvm_args}"

echo ""
echo "Starting IB Gateway..."

# Change to gateway directory
cd "{self.gateway_info.version_dir}"

# Start IB Gateway with optimized settings
java {jvm_args} \\
    -cp "{self.gateway_info.jar_file}" \\
    ibgateway.GWClient \\
    "$@"

echo "IB Gateway stopped"
'''
            
            # Write script
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Make executable
            script_path.chmod(0o755)
            
            self.logger.info(f"Startup script created: {script_path}")
            return script_path
            
        except Exception as e:
            self.logger.error(f"Startup script creation failed: {e}")
            raise
    
    # ==========================================================================
    # PUBLIC METHODS - TESTING
    # ==========================================================================
    def test_api_connection(self, port: int = 4002) -> Tuple[GatewayTestResult, str]:
        """
        Test IB Gateway API connection with enhanced diagnostics.
        
        Args:
            port: API port to test (default: 4002 for paper trading)
            
        Returns:
            Tuple of (test_result, message)
        """
        try:
            # Test 1: Port connectivity
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            
            result = sock.connect_ex(("127.0.0.1", port))
            if result != 0:
                sock.close()
                return GatewayTestResult.PORT_CLOSED, f"Port {port} is not accessible"
            
            self.logger.info(f"Port {port} is open")
            
            # Test 2: API handshake
            try:
                # Send API handshake sequence
                for data in API_HANDSHAKE_SEQUENCE:
                    sock.send(data)
                    time.sleep(0.2)
                
                # Wait for response
                sock.settimeout(API_TEST_TIMEOUT)
                response = sock.recv(1024)
                
                if response:
                    message = f"API handshake successful - received {len(response)} bytes"
                    self.logger.info(message)
                    return GatewayTestResult.SUCCESS, message
                else:
                    return GatewayTestResult.HANDSHAKE_FAILED, "No response to API handshake"
                    
            except socket.timeout:
                return GatewayTestResult.API_TIMEOUT, f"API handshake timed out after {API_TEST_TIMEOUT}s"
            
            finally:
                sock.close()
                
        except Exception as e:
            return GatewayTestResult.CONNECTION_ERROR, f"Connection test failed: {e}"
    
    def diagnose_memory_issues(self) -> Dict[str, Any]:
        """
        Diagnose potential memory-related issues with IB Gateway.
        
        Returns:
            Dictionary with diagnostic information
        """
        try:
            if not self.system_memory:
                self.analyze_system()
            
            diagnosis = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "system_memory": {
                    "total_gb": self.system_memory.total_gb,
                    "available_gb": self.system_memory.available_gb,
                    "usage_percent": self.system_memory.usage_percent
                },
                "recommendations": [],
                "warnings": [],
                "status": "unknown"
            }
            
            # Check if 4GB allocation is possible
            if not self.system_memory.can_allocate_4gb:
                diagnosis["warnings"].append(
                    f"Insufficient memory for 4GB heap allocation "
                    f"(only {self.system_memory.available_gb:.1f}GB available)"
                )
                diagnosis["recommendations"].append(
                    f"Consider closing other applications or upgrading to at least 8GB RAM"
                )
            
            # Check current processes
            ib_processes = [p for p in psutil.process_iter(['pid', 'name', 'memory_info']) 
                          if 'java' in p.info['name'].lower()]
            
            if ib_processes:
                for proc in ib_processes:
                    memory_mb = proc.info['memory_info'].rss / (1024**2)
                    if memory_mb > 100:  # Likely IB Gateway process
                        diagnosis["current_java_processes"] = {
                            "pid": proc.info['pid'],
                            "memory_mb": round(memory_mb, 1)
                        }
                        
                        if memory_mb < 1024:  # Less than 1GB
                            diagnosis["warnings"].append(
                                f"Java process using only {memory_mb:.1f}MB - "
                                "may indicate insufficient heap allocation"
                            )
            
            # Determine overall status
            if self.system_memory.can_allocate_4gb and not diagnosis["warnings"]:
                diagnosis["status"] = "optimal"
            elif self.system_memory.available_gb >= 3.0:
                diagnosis["status"] = "acceptable"
            else:
                diagnosis["status"] = "problematic"
            
            return diagnosis
            
        except Exception as e:
            self.logger.error(f"Memory diagnosis failed: {e}")
            return {"error": str(e), "status": "error"}
    
    # ==========================================================================
    # PUBLIC METHODS - REPORTING
    # ==========================================================================
    def generate_configuration_report(self) -> str:
        """
        Generate comprehensive configuration report.
        
        Returns:
            Formatted report string
        """
        try:
            if not self.system_memory:
                self.analyze_system()
            
            if not self.gateway_info:
                self.find_gateway_installation()
            
            report_lines = [
                "=" * 80,
                "IB GATEWAY JVM CONFIGURATION REPORT",
                f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 80,
                "",
                "SYSTEM MEMORY ANALYSIS:",
                f"  Total Memory: {self.system_memory.total_gb:.1f} GB",
                f"  Available Memory: {self.system_memory.available_gb:.1f} GB",
                f"  Memory Usage: {self.system_memory.usage_percent:.1f}%",
                f"  Can Allocate 4GB: {'✓' if self.system_memory.can_allocate_4gb else '✗'}",
                "",
                "IB GATEWAY INSTALLATION:",
                f"  Installed: {'✓' if self.gateway_info.is_installed else '✗'}",
                f"  Base Directory: {self.gateway_info.base_dir}",
                f"  Version: {self.gateway_info.version or 'Not found'}",
                f"  JAR File: {self.gateway_info.jar_file or 'Not found'}",
                "",
            ]
            
            if self.jvm_config:
                report_lines.extend([
                    "RECOMMENDED JVM CONFIGURATION:",
                    f"  Heap Size: {self.jvm_config.heap_size_gb} GB",
                    f"  Initial Heap: {self.jvm_config.initial_heap_gb} GB",
                    "  JVM Arguments:",
                ])
                
                for arg in self.jvm_config.get_jvm_args():
                    report_lines.append(f"    {arg}")
                
                report_lines.append("")
            
            # Test API connection
            test_result, test_message = self.test_api_connection()
            report_lines.extend([
                "API CONNECTION TEST:",
                f"  Result: {test_result.value}",
                f"  Message: {test_message}",
                "",
            ])
            
            # Memory diagnosis
            diagnosis = self.diagnose_memory_issues()
            report_lines.extend([
                "MEMORY DIAGNOSIS:",
                f"  Status: {diagnosis.get('status', 'unknown')}",
            ])
            
            if diagnosis.get('warnings'):
                report_lines.append("  Warnings:")
                for warning in diagnosis['warnings']:
                    report_lines.append(f"    • {warning}")
            
            if diagnosis.get('recommendations'):
                report_lines.append("  Recommendations:")
                for rec in diagnosis['recommendations']:
                    report_lines.append(f"    • {rec}")
            
            report_lines.extend([
                "",
                "=" * 80
            ])
            
            return "\n".join(report_lines)
            
        except Exception as e:
            return f"Report generation failed: {e}"

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def quick_memory_fix() -> bool:
    """
    Quick fix for common IB Gateway memory issues.
    
    Returns:
        bool: True if fix was applied successfully
    """
    try:
        config_manager = IBGatewayJVMConfig()
        
        print("Analyzing system memory...")
        config_manager.analyze_system()
        
        print("Finding IB Gateway installation...")
        config_manager.find_gateway_installation()
        
        if not config_manager.gateway_info.is_installed:
            print("❌ IB Gateway not found")
            return False
        
        print("Creating optimal JVM configuration...")
        config_manager.create_optimal_jvm_config()
        
        print("Creating startup script...")
        script_path = config_manager.create_startup_script()
        
        print(f"✅ Optimized startup script created: {script_path}")
        print("\nTo start IB Gateway with optimized settings:")
        print(f"  bash {script_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Quick fix failed: {e}")
        return False

def test_current_gateway() -> None:
    """Test current IB Gateway API connection."""
    config_manager = IBGatewayJVMConfig()
    
    print("Testing IB Gateway API connection...")
    result, message = config_manager.test_api_connection()
    
    if result == GatewayTestResult.SUCCESS:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
        
        if result == GatewayTestResult.API_TIMEOUT:
            print("\n💡 API timeout suggests JVM memory issues")
            print("   Run quick_memory_fix() to resolve")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing and CLI interface
    print("=" * 80)
    print("SPYDER U21 - IB Gateway JVM Configuration")
    print("=" * 80)
    
    config_manager = IBGatewayJVMConfig()
    
    try:
        # Generate and display report
        report = config_manager.generate_configuration_report()
        print(report)
        
        # Offer quick fix if needed
        if not config_manager.system_memory.can_allocate_4gb:
            print("\n⚠️  System may need memory optimization")
            response = input("Apply quick memory fix? (y/n): ")
            if response.lower() == 'y':
                quick_memory_fix()
        
    except Exception as e:
        print(f"❌ Error: {e}")
