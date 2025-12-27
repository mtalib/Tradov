#!/usr/bin/env python3
"""
SPYDER - Client ID Rotation Manager
Prevents "clientId already in use" errors by managing rotating client ID pool
Based on production algorithmic trading systems research
"""

import time
import threading
from dataclasses import dataclass
from typing import Optional, Set
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClientConnection:
    """Track client connection state and cleanup timing"""

    client_id: int
    connected_at: float
    disconnected_at: Optional[float] = None
    cleanup_required: bool = False


class ClientIDManager:
    """
    Production-grade client ID rotation manager

    Features:
    - Rotating pool of 1-100 to prevent conflicts
    - Mandatory cleanup delays (500ms-2s) after disconnect
    - Thread-safe operations
    - Automatic stale connection cleanup
    - Debug logging for troubleshooting
    """

    def __init__(self, min_id: int = 1, max_id: int = 100, cleanup_delay: float = 1.0):
        self.min_id = min_id
        self.max_id = max_id
        self.cleanup_delay = cleanup_delay

        self._current_id = min_id
        self._active_connections: dict[int, ClientConnection] = {}
        self._recently_used: Set[int] = set()
        self._lock = threading.Lock()

        logger.info(
            f"ClientIDManager initialized: ID range {min_id}-{max_id}, cleanup delay {cleanup_delay}s"
        )

    def get_next_id(self) -> int:
        """
        Get next available client ID with collision protection

        Returns:
            int: Safe client ID to use

        Raises:
            RuntimeError: If all IDs are in use (should trigger Gateway restart)
        """
        with self._lock:
            self._cleanup_stale_connections()

            # Try to find next available ID
            attempts = 0
            max_attempts = self.max_id - self.min_id + 1

            while attempts < max_attempts:
                candidate_id = self._current_id

                # Advance to next ID (with wrap-around)
                self._current_id += 1
                if self._current_id > self.max_id:
                    self._current_id = self.min_id

                # Check if ID is available
                if self._is_id_available(candidate_id):
                    # Mark as active
                    connection = ClientConnection(
                        client_id=candidate_id, connected_at=time.time()
                    )
                    self._active_connections[candidate_id] = connection
                    self._recently_used.add(candidate_id)

                    logger.debug(f"Allocated client ID {candidate_id}")
                    return candidate_id

                attempts += 1

            # All IDs exhausted - critical situation
            active_count = len(self._active_connections)
            recent_count = len(self._recently_used)

            logger.error(
                f"Client ID pool exhausted! Active: {active_count}, Recent: {recent_count}"
            )
            logger.error(f"Active connections: {list(self._active_connections.keys())}")

            raise RuntimeError(
                f"All client IDs ({self.min_id}-{self.max_id}) are in use. "
                f"Gateway restart required. Active: {active_count}, Recent: {recent_count}"
            )

    def _is_id_available(self, client_id: int) -> bool:
        """Check if client ID is safe to use"""
        # Never reuse active connections
        if client_id in self._active_connections:
            return False

        # Check if recently used and still in cleanup period
        if client_id in self._recently_used:
            return False

        return True

    def mark_disconnected(self, client_id: int) -> None:
        """
        Mark client ID as disconnected and schedule cleanup

        Args:
            client_id: The client ID that was disconnected
        """
        with self._lock:
            if client_id in self._active_connections:
                connection = self._active_connections[client_id]
                connection.disconnected_at = time.time()
                connection.cleanup_required = True

                logger.debug(f"Marked client ID {client_id} as disconnected")
            else:
                logger.warning(
                    f"Attempted to mark unknown client ID {client_id} as disconnected"
                )

    def _cleanup_stale_connections(self) -> None:
        """Remove connections that have completed their cleanup delay"""
        current_time = time.time()

        # Clean up recently used IDs that are past cleanup delay
        expired_recent = set()
        for client_id in self._recently_used:
            if client_id in self._active_connections:
                connection = self._active_connections[client_id]
                if (
                    connection.cleanup_required
                    and connection.disconnected_at
                    and current_time - connection.disconnected_at >= self.cleanup_delay
                ):
                    expired_recent.add(client_id)

        # Remove expired IDs
        for client_id in expired_recent:
            del self._active_connections[client_id]
            self._recently_used.discard(client_id)
            logger.debug(
                f"Cleaned up client ID {client_id} after {self.cleanup_delay}s delay"
            )

    def force_cleanup(self, client_id: int) -> None:
        """Force immediate cleanup of a client ID (emergency use only)"""
        with self._lock:
            if client_id in self._active_connections:
                del self._active_connections[client_id]
            self._recently_used.discard(client_id)
            logger.warning(f"Force cleaned client ID {client_id}")

    def get_status(self) -> dict:
        """Get current manager status for monitoring"""
        with self._lock:
            self._cleanup_stale_connections()

            return {
                "total_ids": self.max_id - self.min_id + 1,
                "active_connections": len(self._active_connections),
                "recently_used": len(self._recently_used),
                "available_ids": (self.max_id - self.min_id + 1)
                - len(self._recently_used),
                "active_client_ids": list(self._active_connections.keys()),
                "cleanup_delay": self.cleanup_delay,
            }

    @contextmanager
    def managed_client_id(self):
        """
        Context manager for automatic client ID lifecycle management

        Usage:
            with client_manager.managed_client_id() as client_id:
                ib.connect('127.0.0.1', 4001, clientId=client_id)
                # ... use connection ...
            # ID automatically marked for cleanup
        """
        client_id = self.get_next_id()
        try:
            yield client_id
        finally:
            self.mark_disconnected(client_id)
            # Add mandatory cleanup delay
            time.sleep(self.cleanup_delay)


# Global client ID manager instance
_global_client_manager: Optional[ClientIDManager] = None


def get_client_manager(
    min_id: int = 1, max_id: int = 100, cleanup_delay: float = 1.0
) -> ClientIDManager:
    """Get or create global client ID manager"""
    global _global_client_manager

    if _global_client_manager is None:
        _global_client_manager = ClientIDManager(min_id, max_id, cleanup_delay)

    return _global_client_manager


def reset_client_manager() -> None:
    """Reset global client manager (for testing)"""
    global _global_client_manager
    _global_client_manager = None


# Convenience functions
def get_safe_client_id() -> int:
    """Get a safe client ID from the global manager"""
    return get_client_manager().get_next_id()


def mark_client_disconnected(client_id: int) -> None:
    """Mark client ID as disconnected in global manager"""
    get_client_manager().mark_disconnected(client_id)


@contextmanager
def safe_client_connection():
    """Context manager for safe client ID management"""
    with get_client_manager().managed_client_id() as client_id:
        yield client_id


if __name__ == "__main__":
    # Test the client ID manager
    logging.basicConfig(level=logging.DEBUG)

    print("🧪 Testing Client ID Manager")
    print("=" * 40)

    manager = ClientIDManager(min_id=1, max_id=5, cleanup_delay=0.1)

    # Test normal allocation
    print("Testing normal allocation:")
    for i in range(3):
        client_id = manager.get_next_id()
        print(f"  Allocated: {client_id}")
        manager.mark_disconnected(client_id)

    print(f"\nStatus: {manager.get_status()}")

    # Test cleanup
    print("\nWaiting for cleanup...")
    time.sleep(0.2)
    print(f"Status after cleanup: {manager.get_status()}")

    # Test context manager
    print("\nTesting context manager:")
    with manager.managed_client_id() as client_id:
        print(f"  Using client ID: {client_id}")

    print(f"Final status: {manager.get_status()}")
    print("✅ Client ID Manager test completed")
