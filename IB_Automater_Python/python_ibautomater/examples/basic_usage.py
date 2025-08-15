#!/usr/bin/env python3
"""
Basic usage example for Python IBAutomater

This example demonstrates how to use IBAutomater to start IB Gateway,
handle events, and manage the gateway lifecycle.
"""

import logging
import time
from ibautomater import IBAutomater

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def on_output_data_received(data):
    """Handle output data from IB Gateway"""
    logger.info(f"Gateway Output: {data}")


def on_error_data_received(data):
    """Handle error data from IB Gateway"""
    logger.error(f"Gateway Error: {data}")


def on_exited(event_args):
    """Handle gateway exit events"""
    logger.warning(f"Gateway exited: {event_args.reason} (code: {event_args.exit_code})")
    
    # Check if this was unexpected
    if event_args.unexpected:
        logger.error("Gateway exited unexpectedly!")
        # Here you could implement restart logic


def on_restarted(event_data):
    """Handle gateway restart events"""
    logger.info("Gateway restarted automatically")
    # Here you could reconnect your trading application


def main():
    """Main example function"""
    
    # Configuration - UPDATE THESE VALUES
    config = {
        "ib_directory": "/path/to/ib/gateway",  # Update this path
        "ib_version": "10.19",                  # Update version
        "username": "your_username",            # Update username
        "password": "your_password",            # Update password
        "trading_mode": "paper",                # "paper" or "live"
        "port": 7497,                          # API port
        "export_ib_gateway_logs": False
    }
    
    # Create IBAutomater instance
    try:
        automater = IBAutomater(**config)
        
        # Setup event handlers
        automater.on_output_data_received = on_output_data_received
        automater.on_error_data_received = on_error_data_received
        automater.on_exited = on_exited
        automater.on_restarted = on_restarted
        
        logger.info("IBAutomater created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create IBAutomater: {e}")
        return
    
    try:
        # Start IB Gateway
        logger.info("Starting IB Gateway...")
        result = automater.start(wait_for_connection=True)
        
        if result.success:
            logger.info(f"IB Gateway started successfully (PID: {result.process_id})")
            
            # Keep running for demonstration
            logger.info("Gateway is running. Monitoring for 60 seconds...")
            
            for i in range(60):
                if not automater.is_running():
                    logger.warning("Gateway stopped running!")
                    break
                
                # Log status every 10 seconds
                if i % 10 == 0:
                    memory = automater.get_memory_usage()
                    cpu = automater.get_cpu_usage()
                    logger.info(f"Status - Memory: {memory:.1f}MB, CPU: {cpu:.1f}%")
                
                time.sleep(1)
            
        else:
            logger.error(f"Failed to start IB Gateway: {result.error_message}")
            return
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    
    except Exception as e:
        logger.error(f"Error during execution: {e}")
    
    finally:
        # Stop IB Gateway
        if automater.is_running():
            logger.info("Stopping IB Gateway...")
            if automater.stop():
                logger.info("IB Gateway stopped successfully")
            else:
                logger.error("Failed to stop IB Gateway")


def context_manager_example():
    """Example using context manager for automatic cleanup"""
    
    config = {
        "ib_directory": "/path/to/ib/gateway",
        "ib_version": "10.19",
        "username": "your_username",
        "password": "your_password",
        "trading_mode": "paper",
        "port": 7497
    }
    
    # Using context manager ensures automatic cleanup
    with IBAutomater(**config) as automater:
        # Setup event handlers
        automater.on_output_data_received = on_output_data_received
        automater.on_error_data_received = on_error_data_received
        
        # Start gateway
        result = automater.start()
        
        if result.success:
            logger.info("Gateway started, doing some work...")
            time.sleep(30)  # Do some work
        
        # Gateway will be automatically stopped when exiting the context


def restart_handling_example():
    """Example showing how to handle auto-restarts"""
    
    config = {
        "ib_directory": "/path/to/ib/gateway",
        "ib_version": "10.19", 
        "username": "your_username",
        "password": "your_password",
        "trading_mode": "paper",
        "port": 7497
    }
    
    def handle_exit(event_args):
        """Handle gateway exit with restart logic"""
        logger.warning(f"Gateway exited: {event_args.reason}")
        
        # Check if we should restart
        if event_args.unexpected:
            logger.info("Attempting to restart gateway...")
            time.sleep(5)  # Wait before restart
            
            result = automater.restart()
            if result.success:
                logger.info("Gateway restarted successfully")
            else:
                logger.error(f"Failed to restart: {result.error_message}")
    
    def handle_restart(event_data):
        """Handle auto-restart events"""
        logger.info("Gateway auto-restarted, reconnecting...")
        # Here you would reconnect your trading application
        # For example, if using ib_async:
        # await ib.connectAsync()
    
    automater = IBAutomater(**config)
    automater.on_exited = handle_exit
    automater.on_restarted = handle_restart
    
    # Start and keep running
    result = automater.start()
    if result.success:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            automater.stop()


if __name__ == "__main__":
    # Run the main example
    main()
    
    # Uncomment to try other examples:
    # context_manager_example()
    # restart_handling_example()

