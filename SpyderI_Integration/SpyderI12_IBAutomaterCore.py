#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderI12_IBAutomaterCore.py
Group: I (Integration)
Purpose: Simplified IBAutomater for process management and connection testing
Author: Mohamed Talib
Date Created: 2025-08-15
Last Updated: 2025-08-15 Time: 15:00:00

Description:
    Simplified IBAutomater focused on essential automation: IB Gateway process
    management, connection testing, and monitoring. Handles startup, shutdown,
    restart detection, and API readiness verification. No UI automation - user
    logs in manually. Provides clean process control with Ubuntu dock integration
    for seamless manual fallback when needed.
"""

import logging
import subprocess
import threading
import time
import socket
import platform
import signal
import sys
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum
import psutil

# ================================================================================================
# CONFIGURATION AND ENUMS
# ================================================================================================

class TradingMode(Enum):
    """Trading mode enumeration"""
    PAPER = "paper"
    LIVE = "live"

class IBEvent(Enum):
    """Event types for IBAutomater"""
    PROCESS_STARTED = "process_started"
    PROCESS_STOPPED = "process_stopped"
    CONNECTION_READY = "connection_ready"
    CONNECTION_LOST = "connection_lost"
    GATEWAY_EXITED = "gateway_exited"
    RESTART_DETECTED = "restart_detected"
    OUTPUT_RECEIVED = "output_received"
    ERROR_RECEIVED = "error_received"

@dataclass
class IBConfig:
    """Configuration for IB Gateway automation"""
    ib_directory: str
    ib_version: str
    trading_mode: TradingMode
    port: int
    java_heap_size: str = "4096m"
    connection_timeout: float = 60.0
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if not Path(self.ib_directory).exists():
            raise ValueError(f"IB directory does not exist: {self.ib_directory}")
        if not (1024 <= self.port <= 65535):
            raise ValueError(f"Invalid port number: {self.port}")

@dataclass
class StartResult:
    """Result of a start operation"""
    success: bool
    process_id: Optional[int] = None
    error_message: Optional[str] = None
    
    @property
    def has_error(self) -> bool:
        return not self.success

# ================================================================================================
# CUSTOM EXCEPTIONS
# ================================================================================================

class IBAutomaterError(Exception):
    """Base exception for IBAutomater errors"""
    pass

class ProcessError(IBAutomaterError):
    """Exception raised when process management fails"""
    pass

class ConnectionError(IBAutomaterError):
    """Exception raised when connection fails"""
    pass

# ================================================================================================
# EVENT SYSTEM
# ================================================================================================

class EventEmitter:
    """Simple event emitter for IBAutomater"""
    
    def __init__(self):
        self._handlers: Dict[IBEvent, list] = {}
        self.logger = logging.getLogger(f"{__name__}.EventEmitter")
    
    def on(self, event_type: IBEvent, handler: Callable):
        """Register an event handler"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def emit(self, event_type: IBEvent, data: Any = None):
        """Emit an event to all registered handlers"""
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    handler({"event": event_type.value, "data": data, "timestamp": time.time()})
                except Exception as e:
                    self.logger.error(f"Error in event handler for {event_type.value}: {e}")

# ================================================================================================
# CONNECTION TESTER
# ================================================================================================

class ConnectionTester:
    """Test IB Gateway API connections"""
    
    def __init__(self, port: int):
        self.port = port
        self.logger = logging.getLogger(f"{__name__}.ConnectionTester")
    
    def test_port_open(self) -> bool:
        """Test if the API port is open"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        
        try:
            result = sock.connect_ex(("127.0.0.1", self.port))
            return result == 0
        except Exception:
            return False
        finally:
            sock.close()
    
    def test_api_response(self) -> bool:
        """Test if API server is responding"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        try:
            sock.connect(("127.0.0.1", self.port))
            
            # Send API handshake
            sock.send(b'API\0')
            time.sleep(0.5)
            sock.send(b'v100..176')
            
            # Try to receive response
            sock.settimeout(3)
            response = sock.recv(1024)
            
            return len(response) > 0
            
        except Exception:
            return False
        finally:
            sock.close()
    
    def wait_for_connection(self, timeout: float = 60.0) -> bool:
        """Wait for API connection to be ready"""
        self.logger.info(f"Waiting for API connection on port {self.port}...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.test_port_open() and self.test_api_response():
                self.logger.info("✅ API connection is ready!")
                return True
            time.sleep(2)
        
        self.logger.error(f"❌ API connection not ready after {timeout} seconds")
        return False

# ================================================================================================
# PROCESS MANAGER
# ================================================================================================

class ProcessManager:
    """Manages IB Gateway process lifecycle"""
    
    def __init__(self, config: IBConfig, event_emitter: EventEmitter):
        self.config = config
        self.event_emitter = event_emitter
        self.process: Optional[subprocess.Popen] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_monitoring = threading.Event()
        self.logger = logging.getLogger(f"{__name__}.ProcessManager")
    
    def start_gateway(self) -> int:
        """Start the IB Gateway process"""
        if self.is_running():
            raise ProcessError("Gateway is already running")
        
        try:
            args = self._get_gateway_args()
            self.logger.info(f"🚀 Starting IB Gateway: {' '.join(args)}")
            
            # Start the process
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=self.config.ib_directory
            )
            
            # Start monitoring
            self._start_monitoring()
            
            self.logger.info(f"✅ IB Gateway started (PID: {self.process.pid})")
            self.event_emitter.emit(IBEvent.PROCESS_STARTED, self.process.pid)
            
            return self.process.pid
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start IB Gateway: {e}")
            raise ProcessError(f"Failed to start gateway: {e}")
    
    def stop_gateway(self) -> bool:
        """Stop the IB Gateway process"""
        if not self.is_running():
            self.logger.info("Gateway is not running")
            return True
        
        try:
            self.logger.info("🛑 Stopping IB Gateway...")
            self.stop_monitoring.set()
            
            # Terminate process gracefully
            if self.process:
                self.process.terminate()
                
                # Wait for graceful shutdown
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.logger.warning("Gateway did not shutdown gracefully, forcing kill")
                    self.process.kill()
                    self.process.wait()
                
                self.process = None
            
            # Wait for monitor thread to finish
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5)
            
            self.logger.info("✅ IB Gateway stopped")
            self.event_emitter.emit(IBEvent.PROCESS_STOPPED, None)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping gateway: {e}")
            return False
    
    def is_running(self) -> bool:
        """Check if the gateway process is running"""
        if self.process is None:
            return False
        
        try:
            return self.process.poll() is None
        except:
            return False
    
    def get_process_id(self) -> Optional[int]:
        """Get the process ID of the running gateway"""
        if self.is_running():
            return self.process.pid
        return None
    
    def get_memory_usage(self) -> Optional[float]:
        """Get memory usage in MB"""
        if not self.is_running():
            return None
        
        try:
            process = psutil.Process(self.process.pid)
            return process.memory_info().rss / 1024 / 1024
        except:
            return None
    
    def get_cpu_usage(self) -> Optional[float]:
        """Get CPU usage percentage"""
        if not self.is_running():
            return None
        
        try:
            process = psutil.Process(self.process.pid)
            return process.cpu_percent()
        except:
            return None
    
    def _get_gateway_args(self) -> list:
        """Get command line arguments for starting IB Gateway"""
        system = platform.system().lower()
        
        if system == "windows":
            executable = str(Path(self.config.ib_directory) / "ibgateway.exe")
        elif system == "darwin":  # macOS
            executable = str(Path(self.config.ib_directory) / "IBGateway.app" / "Contents" / "MacOS" / "IBGateway")
        else:  # Linux
            executable = str(Path(self.config.ib_directory) / "ibgateway")
        
        # Basic arguments for IB Gateway
        args = [executable]
        
        # Add Java options if needed
        if hasattr(self.config, 'java_heap_size'):
            args.extend([f"-Xmx{self.config.java_heap_size}"])
        
        return args
    
    def _start_monitoring(self):
        """Start process monitoring threads"""
        self.stop_monitoring.clear()
        
        # Start main monitor thread
        self.monitor_thread = threading.Thread(target=self._monitor_process, daemon=True)
        self.monitor_thread.start()
        
        # Start output reading threads
        if self.process:
            threading.Thread(target=self._read_output, args=(self.process.stdout, "output"), daemon=True).start()
            threading.Thread(target=self._read_output, args=(self.process.stderr, "error"), daemon=True).start()
    
    def _monitor_process(self):
        """Monitor the gateway process"""
        while not self.stop_monitoring.is_set():
            if self.process and self.process.poll() is not None:
                # Process has exited
                exit_code = self.process.returncode
                self.logger.warning(f"⚠️ Gateway process exited (code: {exit_code})")
                
                self.event_emitter.emit(IBEvent.GATEWAY_EXITED, {
                    "exit_code": exit_code,
                    "unexpected": True
                })
                break
            
            time.sleep(1)
    
    def _read_output(self, stream, stream_type: str):
        """Read output from process stream"""
        if not stream:
            return
        
        try:
            for line in iter(stream.readline, ''):
                if self.stop_monitoring.is_set():
                    break
                
                line = line.strip()
                if line:
                    if stream_type == "output":
                        self.event_emitter.emit(IBEvent.OUTPUT_RECEIVED, line)
                    else:
                        self.event_emitter.emit(IBEvent.ERROR_RECEIVED, line)
                    
                    # Check for specific messages
                    if "API server listening" in line:
                        self.event_emitter.emit(IBEvent.CONNECTION_READY, line)
                    elif "restart" in line.lower():
                        self.event_emitter.emit(IBEvent.RESTART_DETECTED, line)
                        
        except Exception as e:
            self.logger.error(f"Error reading {stream_type} stream: {e}")

# ================================================================================================
# SIMPLIFIED IBAUTOMATER
# ================================================================================================

class IBAutomater:
    """
    Simplified IBAutomater for IB Gateway process management and connection testing
    
    Features:
    - Automated gateway startup/shutdown
    - Connection testing and monitoring
    - Process health monitoring
    - Event notifications
    - Manual login support (no UI automation)
    """
    
    def __init__(
        self,
        ib_directory: str,
        ib_version: str,
        trading_mode: str,
        port: int
    ):
        """
        Initialize IBAutomater
        
        Args:
            ib_directory: Path to IB Gateway installation directory
            ib_version: IB Gateway version (e.g., "10.39")
            trading_mode: Trading mode ("paper" or "live")
            port: API port number
        """
        self.logger = logging.getLogger(f"{__name__}.IBAutomater")
        
        # Convert trading mode string to enum
        mode = TradingMode.PAPER if trading_mode.lower() == "paper" else TradingMode.LIVE
        
        # Create configuration
        self.config = IBConfig(
            ib_directory=ib_directory,
            ib_version=ib_version,
            trading_mode=mode,
            port=port
        )
        
        # Initialize components
        self.event_emitter = EventEmitter()
        self.process_manager = ProcessManager(self.config, self.event_emitter)
        self.connection_tester = ConnectionTester(port)
        
        # State tracking
        self._last_start_result: Optional[StartResult] = None
        self._startup_lock = threading.Lock()
        
        self.logger.info(f"🎯 IBAutomater initialized for {trading_mode} trading on port {port}")
    
    # ==============================================================================================
    # PUBLIC INTERFACE
    # ==============================================================================================
    
    def start(self, wait_for_manual_login: bool = True) -> StartResult:
        """
        Start the IB Gateway (user logs in manually)
        
        Args:
            wait_for_manual_login: Whether to wait for user to complete login
            
        Returns:
            StartResult indicating success or failure
        """
        with self._startup_lock:
            try:
                self.logger.info("🚀 Starting IB Gateway automation...")
                
                # Check if already running
                if self.is_running():
                    self.logger.warning("Gateway is already running")
                    return StartResult(True, process_id=self.process_manager.get_process_id())
                
                # Start the gateway process
                process_id = self.process_manager.start_gateway()
                
                self.logger.info("📝 Gateway started - please log in manually")
                
                # Wait for manual login if requested
                if wait_for_manual_login:
                    self.logger.info("⏳ Waiting for you to complete login...")
                    if self.connection_tester.wait_for_connection(self.config.connection_timeout):
                        self.logger.info("🎉 Login successful - API is ready!")
                    else:
                        self.logger.warning("⚠️ Timeout waiting for login - you can continue manually")
                
                result = StartResult(True, process_id=process_id)
                self._last_start_result = result
                
                return result
                
            except Exception as e:
                self.logger.error(f"❌ Failed to start IB Gateway: {e}")
                result = StartResult(False, error_message=str(e))
                self._last_start_result = result
                return result
    
    def stop(self) -> bool:
        """Stop the IB Gateway"""
        return self.process_manager.stop_gateway()
    
    def restart(self) -> StartResult:
        """Restart the IB Gateway"""
        self.logger.info("🔄 Restarting IB Gateway...")
        
        # Stop first
        if not self.stop():
            return StartResult(False, error_message="Failed to stop gateway")
        
        # Wait a moment
        time.sleep(3)
        
        # Start again
        return self.start()
    
    def is_running(self) -> bool:
        """Check if the IB Gateway is running"""
        return self.process_manager.is_running()
    
    def is_connected(self) -> bool:
        """Check if API connection is working"""
        return self.connection_tester.test_api_response()
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status information"""
        status = {
            "running": self.is_running(),
            "connected": self.is_connected(),
            "port": self.config.port,
            "trading_mode": self.config.trading_mode.value,
            "process_id": self.process_manager.get_process_id(),
            "memory_mb": self.process_manager.get_memory_usage(),
            "cpu_percent": self.process_manager.get_cpu_usage()
        }
        return status
    
    def wait_for_connection(self, timeout: float = 60.0) -> bool:
        """Wait for API connection to be ready"""
        return self.connection_tester.wait_for_connection(timeout)
    
    # ==============================================================================================
    # EVENT HANDLERS
    # ==============================================================================================
    
    def on_process_started(self, handler: Callable):
        """Register handler for process started event"""
        self.event_emitter.on(IBEvent.PROCESS_STARTED, handler)
    
    def on_process_stopped(self, handler: Callable):
        """Register handler for process stopped event"""
        self.event_emitter.on(IBEvent.PROCESS_STOPPED, handler)
    
    def on_connection_ready(self, handler: Callable):
        """Register handler for connection ready event"""
        self.event_emitter.on(IBEvent.CONNECTION_READY, handler)
    
    def on_gateway_exited(self, handler: Callable):
        """Register handler for gateway exit event"""
        self.event_emitter.on(IBEvent.GATEWAY_EXITED, handler)
    
    def on_restart_detected(self, handler: Callable):
        """Register handler for restart detection event"""
        self.event_emitter.on(IBEvent.RESTART_DETECTED, handler)
    
    # ==============================================================================================
    # CONTEXT MANAGER SUPPORT
    # ==============================================================================================
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()

# ================================================================================================
# UBUNTU DESKTOP INTEGRATION
# ================================================================================================

def create_ubuntu_launcher():
    """Create Ubuntu desktop launcher for IBAutomater"""
    desktop_content = """[Desktop Entry]
Version=1.0
Type=Application
Name=Spyder IBAutomater
Comment=Automated IB Gateway Launcher for Spyder Trading System
Exec=python3 /home/{user}/Projects/Spyder/SpyderI12_IBAutomaterCore.py
Icon=/home/{user}/Projects/Spyder/icons/spyder_ibautomater.png
Terminal=true
Categories=Office;Finance;
StartupNotify=true
Keywords=trading;ib;gateway;spyder;
""".format(user=os.getenv('USER', 'user'))
    
    # Create desktop file
    desktop_file = Path.home() / ".local/share/applications/spyder-ibautomater.desktop"
    desktop_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(desktop_file, 'w') as f:
        f.write(desktop_content)
    
    # Make executable
    desktop_file.chmod(0o755)
    
    print(f"✅ Created Ubuntu launcher: {desktop_file}")
    print("🔍 You can now find 'Spyder IBAutomater' in your applications menu")

# ================================================================================================
# UTILITY FUNCTIONS
# ================================================================================================

def create_simple_automater(
    ib_directory: str = "/opt/ibc",
    ib_version: str = "10.39",
    trading_mode: str = "paper",
    port: int = 4002
) -> IBAutomater:
    """Create a simple IBAutomater with common settings"""
    return IBAutomater(
        ib_directory=ib_directory,
        ib_version=ib_version,
        trading_mode=trading_mode,
        port=port
    )

def check_ib_installation(ib_directory: str) -> bool:
    """Check if IB Gateway is properly installed"""
    try:
        path = Path(ib_directory)
        if not path.exists():
            return False
        
        system = platform.system().lower()
        
        if system == "windows":
            executable = path / "ibgateway.exe"
        elif system == "darwin":
            executable = path / "IBGateway.app"
        else:
            executable = path / "ibgateway"
        
        return executable.exists()
        
    except Exception:
        return False

# ================================================================================================
# MAIN EXECUTION
# ================================================================================================

if __name__ == "__main__":
    # Setup logging with colors
    import os
    
    class ColoredFormatter(logging.Formatter):
        """Colored log formatter for terminal output"""
        
        COLORS = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m', # Magenta
        }
        RESET = '\033[0m'
        
        def format(self, record):
            if record.levelname in self.COLORS:
                record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            return super().format(record)
    
    # Setup logging
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            handler,
            logging.FileHandler('spyder_ibautomater.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--create-launcher":
            create_ubuntu_launcher()
            sys.exit(0)
        elif sys.argv[1] == "--help":
            print("""
Spyder IBAutomater - Simplified IB Gateway Automation

Usage:
    python3 SpyderI12_IBAutomaterCore.py                 # Run test
    python3 SpyderI12_IBAutomaterCore.py --create-launcher # Create Ubuntu launcher
    python3 SpyderI12_IBAutomaterCore.py --help          # Show this help

Features:
    🚀 Automated gateway startup
    🔌 Connection testing
    📊 Process monitoring  
    📝 Manual login support
    🖥️ Ubuntu dock integration
            """)
            sys.exit(0)
    
    # Test configuration - adjust for your system
    test_config = {
        "ib_directory": "/opt/ibc",
        "ib_version": "10.39", 
        "trading_mode": "paper",
        "port": 4002
    }
    
    try:
        logger.info("🎯 Testing Spyder IBAutomater...")
        
        # Test installation check
        if not check_ib_installation(test_config["ib_directory"]):
            logger.error(f"❌ IB Gateway not found at {test_config['ib_directory']}")
            logger.info("💡 Update the ib_directory path in the test_config")
            sys.exit(1)
        
        # Create automater
        automater = create_simple_automater(**test_config)
        
        # Setup event handlers
        automater.on_process_started(lambda e: logger.info(f"🚀 Process Started: PID {e['data']}"))
        automater.on_connection_ready(lambda e: logger.info(f"🎉 Connection Ready: {e['data']}"))
        automater.on_gateway_exited(lambda e: logger.warning(f"⚠️ Gateway Exited: {e['data']}"))
        
        logger.info("✅ IBAutomater test completed successfully")
        logger.info("🖥️ Run with --create-launcher to add Ubuntu dock icon")
        
    except Exception as e:
        logger.error(f"❌ IBAutomater test failed: {e}")
        sys.exit(1)
