"""
Main IBAutomater class - Python implementation of IBAutomater
"""

import logging
import threading
import time
from typing import Optional, Callable

from .config import IBConfig, TradingMode
from .events import EventEmitter, IBEvent, StartResult, ExitedEventArgs
from .exceptions import IBAutomaterError, ProcessError, AuthenticationError
from .process_manager import ProcessManager
from .ui_automation import UIAutomation


class IBAutomater:
    """
    Python implementation of IBAutomater for Interactive Brokers Gateway automation
    
    Provides comprehensive automation including:
    - Gateway startup and shutdown
    - Automated login with credentials
    - Two-factor authentication handling
    - Auto-restart detection and management
    - Event-driven notifications
    """
    
    def __init__(
        self,
        ib_directory: str,
        ib_version: str,
        username: str,
        password: str,
        trading_mode: str,
        port: int,
        export_ib_gateway_logs: bool = False
    ):
        """
        Initialize IBAutomater
        
        Args:
            ib_directory: Path to IB Gateway installation directory
            ib_version: IB Gateway version (e.g., "10.19")
            username: IB account username
            password: IB account password
            trading_mode: Trading mode ("paper" or "live")
            port: API port number
            export_ib_gateway_logs: Whether to export IB Gateway logs
        """
        # Convert trading mode string to enum
        mode = TradingMode.PAPER if trading_mode.lower() == "paper" else TradingMode.LIVE
        
        # Create configuration
        self.config = IBConfig(
            ib_directory=ib_directory,
            ib_version=ib_version,
            username=username,
            password=password,
            trading_mode=mode,
            port=port,
            export_logs=export_ib_gateway_logs
        )
        
        # Initialize components
        self.event_emitter = EventEmitter()
        self.process_manager = ProcessManager(self.config, self.event_emitter)
        self.ui_automation = UIAutomation(self.config, self.event_emitter)
        
        # State tracking
        self._last_start_result: Optional[StartResult] = None
        self._login_thread: Optional[threading.Thread] = None
        self._is_starting = False
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Event handler properties (for compatibility with C# version)
        self.output_data_received: Optional[Callable] = None
        self.error_data_received: Optional[Callable] = None
        self.exited: Optional[Callable] = None
        self.restarted: Optional[Callable] = None
        
        # Setup internal event handlers
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """Setup internal event handlers"""
        self.event_emitter.on(IBEvent.OUTPUT_DATA_RECEIVED, self._on_output_data)
        self.event_emitter.on(IBEvent.ERROR_DATA_RECEIVED, self._on_error_data)
        self.event_emitter.on(IBEvent.EXITED, self._on_exited)
        self.event_emitter.on(IBEvent.RESTARTED, self._on_restarted)
    
    def start(self, wait_for_connection: bool = True) -> StartResult:
        """
        Start IB Gateway and perform automated login
        
        Args:
            wait_for_connection: Whether to wait for successful connection
            
        Returns:
            StartResult indicating success or failure
        """
        if self._is_starting:
            return StartResult(False, "ALREADY_STARTING", "Start operation already in progress")
        
        if self.process_manager.is_running():
            return StartResult(False, "ALREADY_RUNNING", "IB Gateway is already running")
        
        self._is_starting = True
        
        try:
            self.logger.info("Starting IB Gateway...")
            
            # Start the gateway process
            process_id = self.process_manager.start_gateway()
            
            # Start login automation in separate thread
            if wait_for_connection:
                self._login_thread = threading.Thread(
                    target=self._perform_login_sequence,
                    daemon=True
                )
                self._login_thread.start()
            
            result = StartResult(True, process_id=process_id)
            self._last_start_result = result
            
            self.logger.info(f"IB Gateway started successfully with PID: {process_id}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to start IB Gateway: {e}"
            self.logger.error(error_msg)
            result = StartResult(False, "START_FAILED", error_msg)
            self._last_start_result = result
            return result
        
        finally:
            self._is_starting = False
    
    def stop(self) -> bool:
        """
        Stop IB Gateway
        
        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            self.logger.info("Stopping IB Gateway...")
            
            # Stop the gateway process
            success = self.process_manager.stop_gateway()
            
            if success:
                self.logger.info("IB Gateway stopped successfully")
            else:
                self.logger.error("Failed to stop IB Gateway")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error stopping IB Gateway: {e}")
            return False
    
    def restart(self) -> StartResult:
        """
        Restart IB Gateway
        
        Returns:
            StartResult indicating success or failure
        """
        self.logger.info("Restarting IB Gateway...")
        
        # Stop if running
        if self.process_manager.is_running():
            self.stop()
        
        # Wait a moment
        time.sleep(2)
        
        # Start again
        return self.start()
    
    def get_last_start_result(self) -> Optional[StartResult]:
        """
        Get the result of the last start operation
        
        Returns:
            StartResult from the last start attempt, or None if never started
        """
        return self._last_start_result
    
    def is_running(self) -> bool:
        """
        Check if IB Gateway is currently running
        
        Returns:
            True if running, False otherwise
        """
        return self.process_manager.is_running()
    
    def get_process_id(self) -> Optional[int]:
        """
        Get the process ID of the running gateway
        
        Returns:
            Process ID if running, None otherwise
        """
        return self.process_manager.get_process_id()
    
    def get_memory_usage(self) -> Optional[float]:
        """
        Get memory usage of the gateway process in MB
        
        Returns:
            Memory usage in MB, or None if not running
        """
        return self.process_manager.get_memory_usage()
    
    def get_cpu_usage(self) -> Optional[float]:
        """
        Get CPU usage percentage of the gateway process
        
        Returns:
            CPU usage percentage, or None if not running
        """
        return self.process_manager.get_cpu_usage()
    
    def _perform_login_sequence(self):
        """Perform the automated login sequence"""
        try:
            self.logger.info("Starting login sequence...")
            
            # Wait for gateway to fully start
            time.sleep(5)
            
            # Perform login
            success = self.ui_automation.perform_login()
            
            if success:
                self.logger.info("Login completed successfully")
                # Dismiss any remaining dialogs
                self.ui_automation.dismiss_dialogs()
            else:
                self.logger.error("Login failed")
                
        except Exception as e:
            self.logger.error(f"Login sequence failed: {e}")
            self._last_start_result = StartResult(False, "LOGIN_FAILED", str(e))
    
    def _on_output_data(self, event_data):
        """Handle output data events"""
        if self.output_data_received:
            try:
                self.output_data_received(event_data.data)
            except Exception as e:
                self.logger.error(f"Error in output_data_received handler: {e}")
    
    def _on_error_data(self, event_data):
        """Handle error data events"""
        if self.error_data_received:
            try:
                self.error_data_received(event_data.data)
            except Exception as e:
                self.logger.error(f"Error in error_data_received handler: {e}")
    
    def _on_exited(self, event_data):
        """Handle process exited events"""
        if self.exited:
            try:
                args = ExitedEventArgs(
                    exit_code=event_data.data,
                    reason="Process exited",
                    unexpected=True
                )
                self.exited(args)
            except Exception as e:
                self.logger.error(f"Error in exited handler: {e}")
    
    def _on_restarted(self, event_data):
        """Handle process restarted events"""
        if self.restarted:
            try:
                self.restarted(event_data)
            except Exception as e:
                self.logger.error(f"Error in restarted handler: {e}")
    
    # Context manager support
    def __enter__(self):
        """Enter context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager"""
        if self.is_running():
            self.stop()
    
    # Property-style event handlers (for easier usage)
    @property
    def on_output_data_received(self) -> Optional[Callable]:
        """Get the output data received event handler"""
        return self.output_data_received
    
    @on_output_data_received.setter
    def on_output_data_received(self, handler: Callable):
        """Set the output data received event handler"""
        self.output_data_received = handler
    
    @property
    def on_error_data_received(self) -> Optional[Callable]:
        """Get the error data received event handler"""
        return self.error_data_received
    
    @on_error_data_received.setter
    def on_error_data_received(self, handler: Callable):
        """Set the error data received event handler"""
        self.error_data_received = handler
    
    @property
    def on_exited(self) -> Optional[Callable]:
        """Get the exited event handler"""
        return self.exited
    
    @on_exited.setter
    def on_exited(self, handler: Callable):
        """Set the exited event handler"""
        self.exited = handler
    
    @property
    def on_restarted(self) -> Optional[Callable]:
        """Get the restarted event handler"""
        return self.restarted
    
    @on_restarted.setter
    def on_restarted(self, handler: Callable):
        """Set the restarted event handler"""
        self.restarted = handler

