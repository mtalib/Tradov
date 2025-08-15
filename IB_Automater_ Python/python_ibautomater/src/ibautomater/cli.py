"""
Command-line interface for IBAutomater
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from .ibautomater import IBAutomater
from .config import TradingMode


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('ibautomater.log')
        ]
    )


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Python IBAutomater - Interactive Brokers Gateway Automation"
    )
    
    # Required arguments
    parser.add_argument(
        "--ib-directory",
        required=True,
        help="Path to IB Gateway installation directory"
    )
    parser.add_argument(
        "--ib-version",
        required=True,
        help="IB Gateway version (e.g., '10.19')"
    )
    parser.add_argument(
        "--username",
        required=True,
        help="IB account username"
    )
    parser.add_argument(
        "--password",
        required=True,
        help="IB account password"
    )
    parser.add_argument(
        "--trading-mode",
        choices=["paper", "live"],
        required=True,
        help="Trading mode"
    )
    parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="API port number"
    )
    
    # Optional arguments
    parser.add_argument(
        "--export-logs",
        action="store_true",
        help="Export IB Gateway logs"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for connection after starting"
    )
    
    # Commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start IB Gateway")
    start_parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon (keep running)"
    )
    
    # Stop command
    subparsers.add_parser("stop", help="Stop IB Gateway")
    
    # Restart command
    subparsers.add_parser("restart", help="Restart IB Gateway")
    
    # Status command
    subparsers.add_parser("status", help="Check IB Gateway status")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Validate IB directory
    if not Path(args.ib_directory).exists():
        logger.error(f"IB directory does not exist: {args.ib_directory}")
        sys.exit(1)
    
    # Create IBAutomater instance
    try:
        automater = IBAutomater(
            ib_directory=args.ib_directory,
            ib_version=args.ib_version,
            username=args.username,
            password=args.password,
            trading_mode=args.trading_mode,
            port=args.port,
            export_ib_gateway_logs=args.export_logs
        )
        
        # Setup event handlers
        automater.on_output_data_received = lambda data: logger.info(f"Gateway: {data}")
        automater.on_error_data_received = lambda data: logger.error(f"Gateway Error: {data}")
        automater.on_exited = lambda args: logger.warning(f"Gateway exited: {args.reason}")
        automater.on_restarted = lambda data: logger.info("Gateway restarted")
        
    except Exception as e:
        logger.error(f"Failed to create IBAutomater: {e}")
        sys.exit(1)
    
    # Execute command
    if args.command == "start":
        logger.info("Starting IB Gateway...")
        result = automater.start(wait_for_connection=not args.no_wait)
        
        if result.success:
            logger.info(f"IB Gateway started successfully (PID: {result.process_id})")
            
            if args.daemon:
                logger.info("Running in daemon mode. Press Ctrl+C to stop.")
                try:
                    while automater.is_running():
                        time.sleep(1)
                except KeyboardInterrupt:
                    logger.info("Stopping IB Gateway...")
                    automater.stop()
        else:
            logger.error(f"Failed to start IB Gateway: {result.error_message}")
            sys.exit(1)
    
    elif args.command == "stop":
        logger.info("Stopping IB Gateway...")
        if automater.stop():
            logger.info("IB Gateway stopped successfully")
        else:
            logger.error("Failed to stop IB Gateway")
            sys.exit(1)
    
    elif args.command == "restart":
        logger.info("Restarting IB Gateway...")
        result = automater.restart()
        
        if result.success:
            logger.info(f"IB Gateway restarted successfully (PID: {result.process_id})")
        else:
            logger.error(f"Failed to restart IB Gateway: {result.error_message}")
            sys.exit(1)
    
    elif args.command == "status":
        if automater.is_running():
            pid = automater.get_process_id()
            memory = automater.get_memory_usage()
            cpu = automater.get_cpu_usage()
            
            logger.info(f"IB Gateway is running (PID: {pid})")
            if memory:
                logger.info(f"Memory usage: {memory:.1f} MB")
            if cpu:
                logger.info(f"CPU usage: {cpu:.1f}%")
        else:
            logger.info("IB Gateway is not running")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

