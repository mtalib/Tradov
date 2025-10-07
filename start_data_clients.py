#!/usr/bin/env python3
"""
Standalone script to start the 11 data clients for market data collection.

This script initializes and starts the MultiClientDataManager which manages
clients 1-11 for connecting to IB Gateway. Run this before starting the
main Spyder dashboard.

Usage:
    python start_data_clients.py

The script will:
1. Initialize the MultiClientDataManager
2. Start all 11 data clients (IDs 1-11)
3. Keep running to maintain connections
4. Handle graceful shutdown on Ctrl+C
"""

import sys
import time
import signal
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def setup_logging():
    """Setup basic logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(__name__)


def main():
    """Main function to start and manage data clients."""
    logger = setup_logging()

    print("=" * 60)
    print("🚀 SPYDER DATA CLIENTS STARTUP")
    print("=" * 60)
    print("This script starts 11 data clients (IDs 1-11) for market data.")
    print("Make sure IB Gateway is running and logged in before proceeding.")
    print()

    # Import the MultiClientDataManager
    try:
        from SpyderB_Broker.SpyderB08_MultiClientDataManager import get_manager_instance

        logger.info("✅ Successfully imported MultiClientDataManager")
    except ImportError as e:
        logger.error(f"❌ Failed to import MultiClientDataManager: {e}")
        print("\nPlease ensure the SpyderB_Broker module is available.")
        return 1

    # Global variable to track running state
    running = True
    manager = None

    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully."""
        nonlocal running, manager
        print(f"\n🛑 Received signal {signum}, shutting down...")
        running = False
        if manager:
            try:
                logger.info("Stopping data clients...")
                manager.stop()
                logger.info("✅ Data clients stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping clients: {e}")

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Get the manager instance
        logger.info("🔧 Initializing MultiClientDataManager...")
        manager = get_manager_instance()

        if not manager:
            logger.error("❌ Failed to get MultiClientDataManager instance")
            return 1

        # Start all data clients
        logger.info("🚀 Starting all data clients (IDs 1-11)...")
        success = manager.start()

        if not success:
            logger.error("❌ Failed to start data clients")
            return 1

        logger.info("✅ All data clients started successfully!")

        # Show status
        status = manager.get_status()
        if status:
            connected_clients = status.get("connected_clients", 0)
            total_clients = status.get("total_clients", 0)
            logger.info(
                f"📊 Status: {connected_clients}/{total_clients} clients connected"
            )

        print()
        print("🟢 DATA CLIENTS RUNNING")
        print("=" * 30)
        print("• Client IDs 1-11 are now connecting to IB Gateway")
        print("• You can now start the main Spyder dashboard")
        print("• Press Ctrl+C to stop all clients and exit")
        print()

        # Keep the script running
        while running:
            try:
                time.sleep(5)

                # Optionally show periodic status updates
                if hasattr(manager, "get_status"):
                    status = manager.get_status()
                    if status:
                        connected = status.get("connected_clients", 0)
                        if connected > 0:
                            # Show a heartbeat every 30 seconds
                            current_time = time.time()
                            if not hasattr(main, "_last_heartbeat"):
                                main._last_heartbeat = current_time

                            if current_time - main._last_heartbeat >= 30:
                                logger.info(
                                    f"💓 Heartbeat: {connected} clients connected"
                                )
                                main._last_heartbeat = current_time

            except KeyboardInterrupt:
                break

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return 1

    finally:
        # Cleanup
        if manager:
            try:
                logger.info("🔄 Cleaning up...")
                manager.stop()
                logger.info("✅ Cleanup completed")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

    print("\n" + "=" * 60)
    print("👋 SPYDER DATA CLIENTS SHUTDOWN COMPLETE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
