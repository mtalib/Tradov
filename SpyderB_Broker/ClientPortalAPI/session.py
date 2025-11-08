#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: SpyderB_Broker/ClientPortalAPI/session.py
Purpose: Session management for Client Portal Web API
Author: Mohamed Talib
Last Updated: 2025-11-08

Module Description:
    Manages Client Portal API session lifecycle including:
    - Session initialization and validation
    - Automatic tickle keepalive (prevents 6-minute timeout)
    - 24-hour session limit handling
    - Connection health monitoring
    - Automatic re-authentication

    CRITICAL: Client Portal sessions timeout after 6 minutes without activity.
    This module automatically sends /tickle requests every 4-5 minutes to
    keep the session alive.

References:
    - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md
    - https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/
"""

import time
import threading
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import requests
from threading import Lock, Event

from .auth import OAuthClient, CPGatewayAuth

logger = logging.getLogger(__name__)


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class SessionConfig:
    """Session manager configuration"""
    tickle_interval: int = 240  # 4 minutes (timeout is 6 minutes)
    session_max_duration: int = 86400  # 24 hours
    health_check_interval: int = 60  # 1 minute
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 3
    reconnect_delay: int = 5  # seconds

    def validate(self):
        """Validate configuration"""
        if self.tickle_interval >= 360:
            logger.warning(
                f"Tickle interval {self.tickle_interval}s is close to 6-minute timeout. "
                "Recommended: 240s (4 minutes)"
            )
        if self.tickle_interval < 60:
            raise ValueError("Tickle interval must be at least 60 seconds")


# ==============================================================================
# SESSION MANAGER
# ==============================================================================

class SessionManager:
    """
    Manages Client Portal API session lifecycle

    Features:
    - Automatic tickle keepalive every 4-5 minutes
    - 24-hour session tracking
    - Connection health monitoring
    - Automatic re-authentication
    - Thread-safe operations

    Usage with OAuth:
        >>> from SpyderB_Broker.ClientPortalAPI import OAuthClient, SessionManager
        >>> oauth_client = OAuthClient(oauth_config)
        >>> session_mgr = SessionManager(auth_client=oauth_client, base_url=base_url)
        >>> session_mgr.start()
        >>> # Session will automatically tickle every 4 minutes
        >>> # Use session_mgr.session for API requests

    Usage with CP Gateway:
        >>> from SpyderB_Broker.ClientPortalAPI import CPGatewayAuth, SessionManager
        >>> gateway_auth = CPGatewayAuth(gateway_config)
        >>> session_mgr = SessionManager(auth_client=gateway_auth, base_url=base_url)
        >>> session_mgr.start()

    Important:
        - Always call stop() when done to clean up threads
        - Session times out after 6 minutes without tickle
        - Session expires after 24 hours (resets at midnight ET/Zurich/HK)
    """

    def __init__(
        self,
        auth_client,  # OAuthClient or CPGatewayAuth
        base_url: str,
        config: Optional[SessionConfig] = None
    ):
        """
        Initialize session manager

        Args:
            auth_client: OAuthClient or CPGatewayAuth instance
            base_url: Base URL for API (e.g., 'https://localhost:5000/v1/api')
            config: Session configuration (optional)
        """
        self.auth_client = auth_client
        self.base_url = base_url.rstrip('/')
        self.config = config or SessionConfig()
        self.config.validate()

        # Session state
        self.session = requests.Session()
        self.session_started: Optional[datetime] = None
        self.last_tickle: Optional[datetime] = None
        self.last_activity: Optional[datetime] = None
        self.authenticated = False
        self.session_id: Optional[str] = None

        # Threading
        self._tickle_thread: Optional[threading.Thread] = None
        self._health_thread: Optional[threading.Thread] = None
        self._stop_event = Event()
        self._lock = Lock()

        # Statistics
        self.tickle_count = 0
        self.failed_tickles = 0
        self.reconnect_count = 0

        # Callbacks
        self.on_session_expired: Optional[Callable] = None
        self.on_tickle_failed: Optional[Callable] = None
        self.on_reconnected: Optional[Callable] = None

        logger.info(f"Session manager initialized: {base_url}")

    def start(self) -> bool:
        """
        Start session and background threads

        Returns:
            True if session started successfully

        Raises:
            Exception: If authentication fails
        """
        with self._lock:
            if self.authenticated:
                logger.warning("Session already started")
                return True

            logger.info("Starting session...")

            # Update session with authentication
            self._update_auth_headers()

            # Validate session
            if not self._validate_session():
                raise Exception("Session validation failed")

            # Record session start
            self.session_started = datetime.now()
            self.last_activity = datetime.now()
            self.authenticated = True

            # Start background threads
            self._start_tickle_thread()
            self._start_health_thread()

            logger.info(
                f"✅ Session started successfully. "
                f"Tickle interval: {self.config.tickle_interval}s"
            )
            return True

    def stop(self):
        """Stop session and background threads"""
        logger.info("Stopping session...")

        # Signal threads to stop
        self._stop_event.set()

        # Wait for threads to finish (with timeout)
        if self._tickle_thread and self._tickle_thread.is_alive():
            self._tickle_thread.join(timeout=5)

        if self._health_thread and self._health_thread.is_alive():
            self._health_thread.join(timeout=5)

        with self._lock:
            self.authenticated = False
            self.session_started = None

        logger.info("Session stopped")

    def _update_auth_headers(self):
        """Update session headers with authentication"""
        if isinstance(self.auth_client, OAuthClient):
            # OAuth: Get access token and set Bearer header
            headers = self.auth_client.get_authorization_header()
            self.session.headers.update(headers)
            logger.debug("Session updated with OAuth token")

        else:
            # CP Gateway: Session already has cookies from authentication
            logger.debug("Using CP Gateway session cookies")

        # Set common headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Spyder-Trading-System/1.0'
        })

    def _validate_session(self) -> bool:
        """
        Validate session by checking auth status

        Returns:
            True if session is valid
        """
        try:
            url = f"{self.base_url}/iserver/auth/status"
            response = self.session.post(url, timeout=30)
            response.raise_for_status()

            status = response.json()
            authenticated = status.get('authenticated', False)

            if authenticated:
                logger.info("✅ Session validated successfully")
                # Extract session info if available
                if 'MAC' in status:
                    self.session_id = status['MAC']
                return True
            else:
                logger.error("❌ Session validation failed - not authenticated")
                return False

        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return False

    def _start_tickle_thread(self):
        """Start background thread for tickle keepalive"""
        def tickle_loop():
            logger.info(f"Tickle thread started (interval: {self.config.tickle_interval}s)")

            while not self._stop_event.is_set():
                # Wait for tickle interval (with ability to stop early)
                if self._stop_event.wait(timeout=self.config.tickle_interval):
                    break  # Stop event was set

                # Send tickle
                try:
                    self.tickle()
                except Exception as e:
                    logger.error(f"Tickle failed: {e}")

            logger.info("Tickle thread stopped")

        self._tickle_thread = threading.Thread(
            target=tickle_loop,
            name="SessionTickleThread",
            daemon=True
        )
        self._tickle_thread.start()

    def _start_health_thread(self):
        """Start background thread for health monitoring"""
        def health_loop():
            logger.info(f"Health thread started (interval: {self.config.health_check_interval}s)")

            while not self._stop_event.is_set():
                # Wait for health check interval
                if self._stop_event.wait(timeout=self.config.health_check_interval):
                    break

                # Check health
                try:
                    self._check_session_health()
                except Exception as e:
                    logger.error(f"Health check failed: {e}")

            logger.info("Health thread stopped")

        self._health_thread = threading.Thread(
            target=health_loop,
            name="SessionHealthThread",
            daemon=True
        )
        self._health_thread.start()

    def tickle(self) -> bool:
        """
        Send tickle keepalive request

        Returns:
            True if tickle succeeded

        Note:
            This is called automatically every 4-5 minutes by background thread.
            You normally don't need to call this manually.
        """
        try:
            url = f"{self.base_url}/tickle"

            # Update auth headers before tickle (in case token expired)
            if isinstance(self.auth_client, OAuthClient):
                self._update_auth_headers()

            response = self.session.post(url, timeout=10)
            response.raise_for_status()

            # Update state
            with self._lock:
                self.last_tickle = datetime.now()
                self.last_activity = datetime.now()
                self.tickle_count += 1

            # Check session age
            session_age = self.get_session_age()
            remaining = self.config.session_max_duration - session_age

            logger.debug(
                f"💚 Tickle #{self.tickle_count} successful. "
                f"Session age: {session_age/3600:.1f}h, "
                f"Remaining: {remaining/3600:.1f}h"
            )

            # Warn if approaching 24-hour limit
            if remaining < 3600:  # Less than 1 hour remaining
                logger.warning(
                    f"⚠️ Session approaching 24-hour limit! "
                    f"Remaining: {remaining/60:.0f} minutes"
                )

            return True

        except Exception as e:
            with self._lock:
                self.failed_tickles += 1

            logger.error(f"💔 Tickle failed: {e}")

            # Trigger callback
            if self.on_tickle_failed:
                self.on_tickle_failed(e)

            # Attempt reconnection if enabled
            if self.config.auto_reconnect:
                logger.info("Attempting automatic reconnection...")
                return self._attempt_reconnect()

            return False

    def _check_session_health(self):
        """Check overall session health"""
        if not self.authenticated:
            return

        # Check session age
        session_age = self.get_session_age()

        # Check if session expired (24 hours)
        if session_age >= self.config.session_max_duration:
            logger.error("❌ Session expired (24-hour limit reached)")

            with self._lock:
                self.authenticated = False

            # Trigger callback
            if self.on_session_expired:
                self.on_session_expired()

            # Attempt reconnection
            if self.config.auto_reconnect:
                self._attempt_reconnect()

            return

        # Check time since last tickle
        if self.last_tickle:
            time_since_tickle = (datetime.now() - self.last_tickle).total_seconds()

            # Warn if tickle is overdue
            if time_since_tickle > self.config.tickle_interval + 60:
                logger.warning(
                    f"⚠️ Tickle overdue by {time_since_tickle - self.config.tickle_interval:.0f}s. "
                    f"Session may timeout!"
                )

        # Validate session is still authenticated
        if not self._validate_session():
            logger.error("❌ Session validation failed during health check")

            with self._lock:
                self.authenticated = False

            if self.config.auto_reconnect:
                self._attempt_reconnect()

    def _attempt_reconnect(self) -> bool:
        """
        Attempt to reconnect session

        Returns:
            True if reconnection successful
        """
        for attempt in range(self.config.max_reconnect_attempts):
            logger.info(f"Reconnection attempt {attempt + 1}/{self.config.max_reconnect_attempts}")

            try:
                # Stop current session
                self._stop_event.set()
                time.sleep(1)

                # Reset stop event
                self._stop_event.clear()

                # Re-initialize
                self._update_auth_headers()

                if self._validate_session():
                    # Restart threads
                    self.session_started = datetime.now()
                    self.last_activity = datetime.now()
                    self.authenticated = True
                    self.reconnect_count += 1

                    self._start_tickle_thread()
                    self._start_health_thread()

                    logger.info("✅ Reconnection successful!")

                    # Trigger callback
                    if self.on_reconnected:
                        self.on_reconnected()

                    return True

            except Exception as e:
                logger.error(f"Reconnection attempt failed: {e}")

            # Wait before next attempt
            time.sleep(self.config.reconnect_delay)

        logger.error("❌ All reconnection attempts failed")
        return False

    def is_authenticated(self) -> bool:
        """
        Check if session is currently authenticated

        Returns:
            True if authenticated
        """
        with self._lock:
            return self.authenticated

    def get_session_age(self) -> int:
        """
        Get session age in seconds

        Returns:
            Session age in seconds, or 0 if not started
        """
        if not self.session_started:
            return 0
        return int((datetime.now() - self.session_started).total_seconds())

    def get_time_since_last_tickle(self) -> Optional[int]:
        """
        Get time since last tickle in seconds

        Returns:
            Seconds since last tickle, or None if no tickle yet
        """
        if not self.last_tickle:
            return None
        return int((datetime.now() - self.last_tickle).total_seconds())

    def get_session(self) -> requests.Session:
        """
        Get the authenticated requests session

        Returns:
            Requests session with authentication

        Usage:
            >>> session = session_mgr.get_session()
            >>> response = session.get(f'{base_url}/portfolio/accounts')
        """
        return self.session

    def get_stats(self) -> Dict[str, Any]:
        """
        Get session statistics

        Returns:
            Dict with session statistics
        """
        return {
            'authenticated': self.authenticated,
            'session_age_seconds': self.get_session_age(),
            'session_age_hours': self.get_session_age() / 3600,
            'session_started': self.session_started.isoformat() if self.session_started else None,
            'last_tickle': self.last_tickle.isoformat() if self.last_tickle else None,
            'time_since_tickle': self.get_time_since_last_tickle(),
            'tickle_count': self.tickle_count,
            'failed_tickles': self.failed_tickles,
            'reconnect_count': self.reconnect_count,
            'tickle_interval': self.config.tickle_interval,
            'session_id': self.session_id
        }

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()

    def __repr__(self) -> str:
        status = "authenticated" if self.authenticated else "not authenticated"
        age = self.get_session_age()
        return f"SessionManager({status}, age={age}s, tickles={self.tickle_count})"


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================

if __name__ == '__main__':
    """Example usage of SessionManager"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
    )

    print("=" * 60)
    print("IBKR Client Portal API - Session Manager Example")
    print("=" * 60)

    # Example with CP Gateway
    print("\nExample: Session Manager with CP Gateway")
    print("-" * 60)

    try:
        from .auth import CPGatewayAuth, CPGatewayConfig

        config = CPGatewayConfig(host='localhost', port=5000)
        auth = CPGatewayAuth(config)

        # Create session manager
        session_config = SessionConfig(
            tickle_interval=240,  # 4 minutes
            auto_reconnect=True
        )

        session_mgr = SessionManager(
            auth_client=auth,
            base_url=config.base_url,
            config=session_config
        )

        # Define callbacks
        def on_tickle_failed(error):
            print(f"⚠️ Tickle failed: {error}")

        def on_reconnected():
            print("✅ Session reconnected!")

        session_mgr.on_tickle_failed = on_tickle_failed
        session_mgr.on_reconnected = on_reconnected

        # Start session (starts tickle thread automatically)
        if session_mgr.start():
            print("✅ Session started successfully")
            print(f"Stats: {session_mgr.get_stats()}")

            # Use session for API calls
            session = session_mgr.get_session()
            # response = session.get(f'{base_url}/portfolio/accounts')

            print("\nSession is running. Tickle will happen every 4 minutes.")
            print("Press Ctrl+C to stop...")

            try:
                # Keep running
                while True:
                    time.sleep(10)
                    stats = session_mgr.get_stats()
                    print(f"Session stats: {stats}")

            except KeyboardInterrupt:
                print("\nStopping session...")
                session_mgr.stop()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("For more information, see:")
    print("  - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md")
    print("=" * 60)
