"""
Process management for IB Gateway
"""

import logging
import subprocess
import threading
import time
from typing import Optional, Callable

import psutil

from .config import IBConfig
from .events import EventEmitter, IBEvent
from .exceptions import ProcessError


class ProcessManager:
    """Manages IB Gateway process lifecycle"""
    
    def __init__(self, config: IBConfig, event_emitter: EventEmitter):
        self.config = config
        self.event_emitter = event_emitter
        self.process: Optional[subprocess.Popen] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_monitoring = threading.Event()
        self.logger = logging.getLogger(__name__)
    
    def start_gateway(self) -> int:
        """Start the IB Gateway process"""
        if self.is_running():
            raise ProcessError("Gateway is already running")
        
        try:
            args = self.config.get_gateway_args()
            self.logger.info(f"Starting IB Gateway with args: {args}")
            
            # Start the process
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Start monitoring thread
            self.stop_monitoring.clear()
            self.monitor_thread = threading.Thread(
                target=self._monitor_process,
                daemon=True
            )
            self.monitor_thread.start()
            
            # Start output reading threads
            threading.Thread(
                target=self._read_output,
                args=(self.process.stdout, IBEvent.OUTPUT_DATA_RECEIVED),
                daemon=True
            ).start()
            
            threading.Thread(
                target=self._read_output,
                args=(self.process.stderr, IBEvent.ERROR_DATA_RECEIVED),
                daemon=True
            ).start()
            
            self.event_emitter.emit(IBEvent.PROCESS_STARTED, self.process.pid)
            self.logger.info(f"IB Gateway started with PID: {self.process.pid}")
            
            return self.process.pid
            
        except Exception as e:
            self.logger.error(f"Failed to start IB Gateway: {e}")
            raise ProcessError(f"Failed to start IB Gateway: {e}")
    
    def stop_gateway(self, timeout: int = 30) -> bool:
        """Stop the IB Gateway process"""
        if not self.is_running():
            self.logger.warning("Gateway is not running")
            return True
        
        try:
            self.logger.info("Stopping IB Gateway...")
            
            # Signal monitoring thread to stop
            self.stop_monitoring.set()
            
            # Try graceful shutdown first
            self.process.terminate()
            
            # Wait for process to exit
            try:
                self.process.wait(timeout=timeout)
                self.logger.info("IB Gateway stopped gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                self.logger.warning("Graceful shutdown timed out, force killing...")
                self.process.kill()
                self.process.wait()
                self.logger.info("IB Gateway force killed")
            
            self.event_emitter.emit(IBEvent.PROCESS_STOPPED, self.process.returncode)
            self.process = None
            
            # Wait for monitor thread to finish
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop IB Gateway: {e}")
            raise ProcessError(f"Failed to stop IB Gateway: {e}")
    
    def is_running(self) -> bool:
        """Check if the IB Gateway process is running"""
        if self.process is None:
            return False
        
        try:
            # Check if process is still alive
            return self.process.poll() is None
        except Exception:
            return False
    
    def get_process_id(self) -> Optional[int]:
        """Get the process ID of the running gateway"""
        if self.process:
            return self.process.pid
        return None
    
    def restart_gateway(self) -> int:
        """Restart the IB Gateway process"""
        self.logger.info("Restarting IB Gateway...")
        
        if self.is_running():
            self.stop_gateway()
        
        # Wait a moment before restarting
        time.sleep(2)
        
        return self.start_gateway()
    
    def _monitor_process(self):
        """Monitor the gateway process for unexpected exits"""
        while not self.stop_monitoring.is_set() and self.is_running():
            time.sleep(1)
        
        # Process has exited
        if self.process and not self.stop_monitoring.is_set():
            exit_code = self.process.returncode
            self.logger.warning(f"IB Gateway exited unexpectedly with code: {exit_code}")
            
            # Check if this was an auto-restart
            if self._is_auto_restart():
                self.event_emitter.emit(IBEvent.RESTARTED, exit_code)
            else:
                self.event_emitter.emit(IBEvent.EXITED, exit_code)
    
    def _read_output(self, stream, event_type: IBEvent):
        """Read output from process stream and emit events"""
        try:
            for line in iter(stream.readline, ''):
                if line:
                    self.event_emitter.emit(event_type, line.strip())
        except Exception as e:
            self.logger.error(f"Error reading process output: {e}")
    
    def _is_auto_restart(self) -> bool:
        """Detect if the process exit was due to auto-restart"""
        # This is a simplified implementation
        # In a real implementation, you would check for specific exit codes
        # or log messages that indicate an auto-restart
        
        # Check if exit happened around the configured auto-restart time
        current_time = time.strftime("%H:%M")
        restart_time = self.config.auto_restart_time
        
        # Simple time comparison (within 5 minutes of restart time)
        try:
            restart_hour, restart_min = map(int, restart_time.split(':'))
            current_hour, current_min = map(int, current_time.split(':'))
            
            restart_minutes = restart_hour * 60 + restart_min
            current_minutes = current_hour * 60 + current_min
            
            # Check if within 5 minutes of restart time
            diff = abs(current_minutes - restart_minutes)
            return diff <= 5 or diff >= (24 * 60 - 5)  # Handle day boundary
            
        except Exception:
            return False
    
    def get_memory_usage(self) -> Optional[float]:
        """Get memory usage of the gateway process in MB"""
        if not self.is_running():
            return None
        
        try:
            process = psutil.Process(self.process.pid)
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    def get_cpu_usage(self) -> Optional[float]:
        """Get CPU usage percentage of the gateway process"""
        if not self.is_running():
            return None
        
        try:
            process = psutil.Process(self.process.pid)
            return process.cpu_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

