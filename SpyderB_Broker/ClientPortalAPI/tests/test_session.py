#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: test_session.py
Purpose: Unit tests for Session Manager
Author: Mohamed Talib
Last Updated: 2025-11-08
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from threading import Event

from SpyderB_Broker.ClientPortalAPI.session import (
    SessionManager,
    SessionConfig,
    SessionError,
    TickleError
)


class TestSessionConfig:
    """Test cases for SessionConfig dataclass"""

    @pytest.mark.unit
    def test_default_config(self):
        """Test default configuration values"""
        config = SessionConfig()

        assert config.tickle_interval == 240  # 4 minutes
        assert config.health_check_interval == 60  # 1 minute
        assert config.session_max_duration == 86400  # 24 hours
        assert config.tickle_timeout == 10
        assert config.auto_restart is True

    @pytest.mark.unit
    def test_custom_config(self):
        """Test custom configuration values"""
        config = SessionConfig(
            tickle_interval=300,
            health_check_interval=120,
            session_max_duration=43200,
            auto_restart=False
        )

        assert config.tickle_interval == 300
        assert config.health_check_interval == 120
        assert config.session_max_duration == 43200
        assert config.auto_restart is False


class TestSessionManager:
    """Test cases for SessionManager class"""

    @pytest.mark.unit
    def test_session_manager_creation(self, mock_http_session):
        """Test that session manager can be created"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(
            auth_client=auth_client,
            base_url="https://localhost:5000"
        )

        assert session_mgr.auth_client == auth_client
        assert session_mgr.base_url == "https://localhost:5000"
        assert session_mgr.session == mock_http_session
        assert session_mgr.is_running is False
        assert session_mgr.tickle_count == 0

    @pytest.mark.unit
    def test_session_manager_with_custom_config(self, mock_http_session):
        """Test session manager with custom configuration"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        config = SessionConfig(tickle_interval=300)

        session_mgr = SessionManager(
            auth_client=auth_client,
            base_url="https://localhost:5000",
            config=config
        )

        assert session_mgr.config.tickle_interval == 300

    @pytest.mark.unit
    @patch('SpyderB_Broker.ClientPortalAPI.session.Thread')
    def test_start_session(self, mock_thread_class, mock_http_session):
        """Test starting session manager"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(auth_client, "https://localhost:5000")

        # Mock threads
        tickle_thread = Mock()
        health_thread = Mock()
        mock_thread_class.side_effect = [tickle_thread, health_thread]

        session_mgr.start()

        assert session_mgr.is_running is True
        assert session_mgr.session_start_time is not None
        assert tickle_thread.start.called
        assert health_thread.start.called

    @pytest.mark.unit
    @patch('SpyderB_Broker.ClientPortalAPI.session.Thread')
    def test_stop_session(self, mock_thread_class, mock_http_session):
        """Test stopping session manager"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(auth_client, "https://localhost:5000")

        # Mock threads
        tickle_thread = Mock()
        health_thread = Mock()
        mock_thread_class.side_effect = [tickle_thread, health_thread]

        session_mgr.start()
        session_mgr.stop()

        assert session_mgr.is_running is False
        assert session_mgr._stop_event.is_set()

    @pytest.mark.unit
    def test_tickle_success(self, mock_http_session, mock_http_response):
        """Test successful tickle request"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        # Configure mock response
        mock_http_response.status_code = 200
        mock_http_session.post.return_value = mock_http_response

        session_mgr = SessionManager(auth_client, "https://localhost:5000")
        session_mgr.session_start_time = datetime.now()

        result = session_mgr.tickle()

        assert result is True
        assert session_mgr.tickle_count == 1
        assert session_mgr.last_tickle is not None
        mock_http_session.post.assert_called_once_with(
            "https://localhost:5000/tickle",
            timeout=10
        )

    @pytest.mark.unit
    def test_tickle_failure(self, mock_http_session):
        """Test tickle request failure"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        # Configure mock to raise exception
        mock_http_session.post.side_effect = Exception("Network error")

        session_mgr = SessionManager(auth_client, "https://localhost:5000")
        session_mgr.session_start_time = datetime.now()

        with pytest.raises(TickleError):
            session_mgr.tickle()

    @pytest.mark.unit
    def test_tickle_callback_on_failure(self, mock_http_session):
        """Test that callback is called on tickle failure"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        # Configure mock to raise exception
        mock_http_session.post.side_effect = Exception("Network error")

        callback = Mock()
        session_mgr = SessionManager(
            auth_client,
            "https://localhost:5000",
            on_tickle_failed=callback
        )
        session_mgr.session_start_time = datetime.now()

        with pytest.raises(TickleError):
            session_mgr.tickle()

        assert callback.called

    @pytest.mark.unit
    def test_get_session_age(self, mock_http_session):
        """Test getting session age in hours"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(auth_client, "https://localhost:5000")

        # Set session start time to 2 hours ago
        session_mgr.session_start_time = datetime.now() - timedelta(hours=2)

        age = session_mgr.get_session_age()

        assert 1.9 < age < 2.1  # Allow small margin

    @pytest.mark.unit
    def test_get_stats(self, mock_http_session):
        """Test getting session statistics"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(auth_client, "https://localhost:5000")
        session_mgr.session_start_time = datetime.now()
        session_mgr.last_tickle = datetime.now()
        session_mgr.tickle_count = 5

        stats = session_mgr.get_stats()

        assert 'session_start_time' in stats
        assert 'session_age_hours' in stats
        assert 'is_running' in stats
        assert 'tickle_count' in stats
        assert stats['tickle_count'] == 5
        assert stats['is_running'] is False

    @pytest.mark.unit
    def test_context_manager_enter_exit(self, mock_http_session):
        """Test using SessionManager as context manager"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(auth_client, "https://localhost:5000")

        with patch.object(session_mgr, 'start') as mock_start:
            with patch.object(session_mgr, 'stop') as mock_stop:
                with session_mgr:
                    assert mock_start.called

                assert mock_stop.called

    @pytest.mark.unit
    def test_validate_session_not_started(self, mock_http_session):
        """Test session validation when not started"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(auth_client, "https://localhost:5000")

        is_valid, reason = session_mgr.validate_session()

        assert is_valid is False
        assert "not started" in reason.lower()

    @pytest.mark.unit
    def test_validate_session_expired(self, mock_http_session):
        """Test session validation when expired (> 24 hours)"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(auth_client, "https://localhost:5000")
        session_mgr.session_start_time = datetime.now() - timedelta(hours=25)

        is_valid, reason = session_mgr.validate_session()

        assert is_valid is False
        assert "expired" in reason.lower()

    @pytest.mark.unit
    def test_validate_session_no_recent_tickle(self, mock_http_session):
        """Test session validation when no recent tickle"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(auth_client, "https://localhost:5000")
        session_mgr.session_start_time = datetime.now()
        session_mgr.last_tickle = datetime.now() - timedelta(minutes=10)

        is_valid, reason = session_mgr.validate_session()

        assert is_valid is False
        assert "tickle" in reason.lower()

    @pytest.mark.unit
    def test_validate_session_healthy(self, mock_http_session):
        """Test session validation when healthy"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(auth_client, "https://localhost:5000")
        session_mgr.session_start_time = datetime.now()
        session_mgr.last_tickle = datetime.now()

        is_valid, reason = session_mgr.validate_session()

        assert is_valid is True
        assert reason == "Session is healthy"


class TestSessionManagerIntegration:
    """Integration tests for SessionManager"""

    @pytest.mark.integration
    @pytest.mark.slow
    @patch('SpyderB_Broker.ClientPortalAPI.session.Thread')
    def test_session_lifecycle(self, mock_thread_class, mock_http_session, mock_http_response):
        """Test complete session lifecycle"""
        auth_client = Mock()
        auth_client.session = mock_http_session
        mock_http_session.post.return_value = mock_http_response

        # Mock threads to not actually run
        tickle_thread = Mock()
        health_thread = Mock()
        mock_thread_class.side_effect = [tickle_thread, health_thread]

        config = SessionConfig(tickle_interval=1, health_check_interval=1)
        session_mgr = SessionManager(auth_client, "https://localhost:5000", config=config)

        # Start session
        session_mgr.start()
        assert session_mgr.is_running is True

        # Perform tickle
        result = session_mgr.tickle()
        assert result is True
        assert session_mgr.tickle_count == 1

        # Check statistics
        stats = session_mgr.get_stats()
        assert stats['tickle_count'] == 1
        assert stats['is_running'] is True

        # Stop session
        session_mgr.stop()
        assert session_mgr.is_running is False

    @pytest.mark.integration
    @patch('SpyderB_Broker.ClientPortalAPI.session.Thread')
    def test_session_with_callbacks(self, mock_thread_class, mock_http_session):
        """Test session manager with all callbacks"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        # Create callback mocks
        on_session_expired = Mock()
        on_tickle_failed = Mock()
        on_reconnected = Mock()

        # Mock threads
        tickle_thread = Mock()
        health_thread = Mock()
        mock_thread_class.side_effect = [tickle_thread, health_thread]

        session_mgr = SessionManager(
            auth_client,
            "https://localhost:5000",
            on_session_expired=on_session_expired,
            on_tickle_failed=on_tickle_failed,
            on_reconnected=on_reconnected
        )

        session_mgr.start()

        # Simulate tickle failure
        mock_http_session.post.side_effect = Exception("Network error")

        with pytest.raises(TickleError):
            session_mgr.tickle()

        # Verify callback was called
        assert on_tickle_failed.called

        session_mgr.stop()

    @pytest.mark.integration
    @pytest.mark.slow
    def test_tickle_prevents_timeout(self, mock_http_session, mock_http_response):
        """Test that regular tickles keep session alive"""
        auth_client = Mock()
        auth_client.session = mock_http_session
        mock_http_session.post.return_value = mock_http_response

        config = SessionConfig(tickle_interval=240)  # 4 minutes
        session_mgr = SessionManager(auth_client, "https://localhost:5000", config=config)
        session_mgr.session_start_time = datetime.now()

        # Simulate multiple tickles
        for i in range(5):
            session_mgr.tickle()
            time.sleep(0.1)

        assert session_mgr.tickle_count == 5

        # Verify session is still valid
        is_valid, reason = session_mgr.validate_session()
        assert is_valid is True


class TestSessionManagerEdgeCases:
    """Test edge cases and error scenarios"""

    @pytest.mark.unit
    @patch('SpyderB_Broker.ClientPortalAPI.session.Thread')
    def test_double_start(self, mock_thread_class, mock_http_session):
        """Test that starting already-started session is handled"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        tickle_thread = Mock()
        health_thread = Mock()
        mock_thread_class.side_effect = [tickle_thread, health_thread]

        session_mgr = SessionManager(auth_client, "https://localhost:5000")

        session_mgr.start()

        # Try to start again - should handle gracefully
        with patch('SpyderB_Broker.ClientPortalAPI.session.logger') as mock_logger:
            session_mgr.start()
            # Should log warning but not crash
            assert mock_logger.warning.called or session_mgr.is_running

    @pytest.mark.unit
    def test_tickle_before_start(self, mock_http_session, mock_http_response):
        """Test tickle before session is started"""
        auth_client = Mock()
        auth_client.session = mock_http_session
        mock_http_session.post.return_value = mock_http_response

        session_mgr = SessionManager(auth_client, "https://localhost:5000")

        # Should still work (just won't have session_start_time for age calculation)
        result = session_mgr.tickle()
        assert result is True

    @pytest.mark.unit
    def test_stop_before_start(self, mock_http_session):
        """Test stopping session that was never started"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(auth_client, "https://localhost:5000")

        # Should handle gracefully
        session_mgr.stop()
        assert session_mgr.is_running is False

    @pytest.mark.unit
    def test_session_age_before_start(self, mock_http_session):
        """Test getting session age before starting"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        session_mgr = SessionManager(auth_client, "https://localhost:5000")

        age = session_mgr.get_session_age()
        assert age == 0.0

    @pytest.mark.unit
    def test_http_error_during_tickle(self, mock_http_session):
        """Test HTTP error response during tickle"""
        auth_client = Mock()
        auth_client.session = mock_http_session

        # Mock HTTP error
        error_response = Mock()
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = Exception("Internal Server Error")
        mock_http_session.post.return_value = error_response

        session_mgr = SessionManager(auth_client, "https://localhost:5000")
        session_mgr.session_start_time = datetime.now()

        with pytest.raises(TickleError):
            session_mgr.tickle()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
