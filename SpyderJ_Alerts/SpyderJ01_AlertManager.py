#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderJ01_AlertManager.py
Group: J (Notifications)
Purpose: Alert system orchestration

Description:
This module manages the alert and notification system for the Spyder trading
platform. It coordinates multiple notification channels (email, SMS, desktop,
Telegram), implements alert rules and filtering, manages notification priorities
and rate limiting, and ensures critical alerts are delivered reliably. The system
supports customizable alert templates, scheduling, and maintains a history of
all notifications for audit purposes.

Author: Mohamed Talib
Created: 2025-01-27
Version: 1.4
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import os
import json
import asyncio
import smtplib
import threading
import queue
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Set, Tuple, Any, Callable, Union
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import hashlib
import pickle

# =============================================================================
# Third-Party Imports
# =============================================================================
import requests
from jinja2 import Environment, FileSystemLoader, Template
from twilio.rest import Client as TwilioClient
from plyer import notification as desktop_notification
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import pandas as pd

# =============================================================================
# Local Application Imports
# =============================================================================
from SpyderA_Core.SpyderA03_Configuration import get_config_manager
from SpyderA_Core.SpyderA05_EventManager import get_event_manager
from SpyderH_Storage.SpyderH01_DatabaseManager import get_database_manager
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, NotificationError
from SpyderU_Utilities.SpyderU03_DateTimeUtils import is_trading_hours, to_local_time
from SpyderU_Utilities.SpyderU07_Constants import (
    MAX_ALERTS_PER_MINUTE,
    ALERT_RETENTION_DAYS,
    CRITICAL_ALERT_RETRY_COUNT
)

# =============================================================================
# Constants
# =============================================================================
# Alert configuration
DEFAULT_RATE_LIMIT = 10  # Alerts per minute
DEFAULT_COOLDOWN = 300  # 5 minutes between similar alerts
ALERT_QUEUE_SIZE = 1000
BATCH_SEND_INTERVAL = 5  # Seconds

# Channel priorities
CHANNEL_PRIORITIES = {
    'telegram': 1,
    'sms': 2,
    'email': 3,
    'desktop': 4
}

# Retry configuration
RETRY_DELAYS = [10, 30, 60, 300]  # Seconds
MAX_RETRY_ATTEMPTS = len(RETRY_DELAYS)

# Template directory
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

# Alert history
HISTORY_TABLE = "alert_history"
HISTORY_RETENTION_DAYS = 30

# =============================================================================
# Enumerations
# =============================================================================
class AlertLevel(Enum):
    """Alert severity levels."""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

class AlertCategory(Enum):
    """Alert categories."""
    SYSTEM = auto()
    TRADING = auto()
    RISK = auto()
    POSITION = auto()
    MARKET = auto()
    PERFORMANCE = auto()
    CONNECTION = auto()

class NotificationChannel(Enum):
    """Notification channels."""
    EMAIL = "email"
    SMS = "sms"
    TELEGRAM = "telegram"
    DESKTOP = "desktop"
    WEBHOOK = "webhook"

class DeliveryStatus(Enum):
    """Alert delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"

# =============================================================================
# Data Classes
# =============================================================================
class Alert:
    """
    Represents an alert to be sent.
    
    Attributes:
        alert_id: Unique alert identifier
        level: Alert severity level
        category: Alert category
        title: Alert title
        message: Alert message body
        details: Additional details
        channels: Target notification channels
        timestamp: Alert creation time
        metadata: Additional metadata
        attachments: File attachments
        priority: Alert priority (1-10)
        expires_at: Alert expiration time
    """
    alert_id: str
    level: AlertLevel
    category: AlertCategory
    title: str
    message: str
    details: Optional[Dict[str, Any]] = None
    channels: List[NotificationChannel] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    attachments: List[str] = field(default_factory=list)
    priority: int = 5
    expires_at: Optional[datetime] = None
    
    def __hash__(self):
        """Make Alert hashable for deduplication."""
        return hash(self.alert_id)

class AlertRule:
    """
    Rule for alert filtering and routing.
    
    Attributes:
        rule_id: Unique rule identifier
        name: Rule name
        condition: Condition function
        channels: Target channels
        template: Message template
        cooldown: Cooldown period in seconds
        enabled: Rule enabled status
        schedule: Time-based schedule
        rate_limit: Max alerts per period
    """
    rule_id: str
    name: str
    condition: Callable[[Alert], bool]
    channels: List[NotificationChannel]
    template: Optional[str] = None
    cooldown: int = DEFAULT_COOLDOWN
    enabled: bool = True
    schedule: Optional[Dict[str, Any]] = None
    rate_limit: Optional[int] = None

class NotificationResult:
    """
    Result of notification attempt.
    
    Attributes:
        alert_id: Alert identifier
        channel: Notification channel
        status: Delivery status
        timestamp: Attempt timestamp
        error: Error message if failed
        response: Channel response
        retry_count: Number of retries
    """
    alert_id: str
    channel: NotificationChannel
    status: DeliveryStatus
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    response: Optional[Dict[str, Any]] = None
    retry_count: int = 0

class AlertHistory:
    """
    Historical alert record.
    
    Attributes:
        alert: Original alert
        results: Delivery results
        first_sent: First send attempt
        last_sent: Last send attempt
        total_attempts: Total delivery attempts
    """
    alert: Alert
    results: List[NotificationResult] = field(default_factory=list)
    first_sent: Optional[datetime] = None
    last_sent: Optional[datetime] = None
    total_attempts: int = 0

# =============================================================================
# Class Definitions
# =============================================================================
class AlertManager:
    """
    Central alert and notification management system.
    
    This class orchestrates all alerts and notifications in the Spyder system,
    managing multiple notification channels, implementing alert rules and
    filtering, handling rate limiting and retries, and maintaining alert history.
    
    Features:
    - Multi-channel notification support
    - Alert rules and filtering
    - Rate limiting and cooldown
    - Template-based messaging
    - Retry logic for critical alerts
    - Alert history and audit trail
    - Scheduled notifications
    
    Attributes:
        logger (Logger): Module logger
        config (ConfigManager): Configuration manager
        event_manager (EventManager): Event system
        channels (Dict): Active notification channels
        rules (Dict): Alert rules
        alert_queue (Queue): Pending alerts queue
        history (Dict): Recent alert history
        rate_limiter (RateLimiter): Rate limiting system
        _worker_thread (Thread): Alert processing thread
    """
    
    def __init__(self):
        """Initialize the alert manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = get_config_manager()
        self.event_manager = get_event_manager()
        self.database = get_database_manager()
        
        # Alert configuration
        self.enabled = self.config.get('alerts.enabled', True)
        self.rate_limit = self.config.get('alerts.rate_limit', DEFAULT_RATE_LIMIT)
        
        # Notification channels
        self.channels: Dict[NotificationChannel, Any] = {}
        self._initialize_channels()
        
        # Alert rules
        self.rules: Dict[str, AlertRule] = {}
        self._load_rules()
        
        # Alert queue and processing
        self.alert_queue: queue.Queue = queue.Queue(maxsize=ALERT_QUEUE_SIZE)
        self.retry_queue: queue.PriorityQueue = queue.PriorityQueue()
        
        # Alert history and deduplication
        self.history: Dict[str, AlertHistory] = {}
        self.recent_alerts: deque = deque(maxlen=1000)
        self._cooldown_tracker: Dict[str, datetime] = {}
        
        # Rate limiting
        self.rate_limiter = RateLimiter(self.rate_limit)
        
        # Template engine
        self.template_env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=True
        )
        
        # Threading
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._process_alerts,
            name="AlertManager-Worker",
            daemon=True
        )
        
        # Statistics
        self.stats = {
            'total_alerts': 0,
            'sent_successfully': 0,
            'failed_alerts': 0,
            'rate_limited': 0,
            'by_channel': defaultdict(int),
            'by_level': defaultdict(int)
        }
        
        # Start processing
        self._start_processing()
        
        # Subscribe to system events
        self._subscribe_to_events()
        
        self.logger.info("Alert manager initialized")
    
    def _initialize_channels(self) -> None:
        """Initialize notification channels."""
        # Email channel
        if self.config.get('alerts.email.enabled', False):
            self.channels[NotificationChannel.EMAIL] = EmailChannel(
                smtp_host=self.config.get('alerts.email.smtp_host'),
                smtp_port=self.config.get('alerts.email.smtp_port', 587),
                username=self.config.get('alerts.email.username'),
                password=self.config.get('alerts.email.password'),
                from_address=self.config.get('alerts.email.from_address'),
                to_addresses=self.config.get('alerts.email.to_addresses', [])
            )
            self.logger.info("Email channel initialized")
        
        # SMS channel (Twilio)
        if self.config.get('alerts.sms.enabled', False):
            self.channels[NotificationChannel.SMS] = SMSChannel(
                account_sid=self.config.get('alerts.sms.twilio_sid'),
                auth_token=self.config.get('alerts.sms.twilio_token'),
                from_number=self.config.get('alerts.sms.from_number'),
                to_numbers=self.config.get('alerts.sms.to_numbers', [])
            )
            self.logger.info("SMS channel initialized")
        
        # Telegram channel
        if self.config.get('alerts.telegram.enabled', False):
            self.channels[NotificationChannel.TELEGRAM] = TelegramChannel(
                bot_token=self.config.get('alerts.telegram.bot_token'),
                chat_ids=self.config.get('alerts.telegram.chat_ids', [])
            )
            self.logger.info("Telegram channel initialized")
        
        # Desktop notifications
        if self.config.get('alerts.desktop.enabled', True):
            self.channels[NotificationChannel.DESKTOP] = DesktopChannel()
            self.logger.info("Desktop channel initialized")
    
    def _load_rules(self) -> None:
        """Load alert rules from configuration."""
        # Default rules
        self._add_default_rules()
        
        # Custom rules from config
        custom_rules = self.config.get('alerts.rules', [])
        for rule_config in custom_rules:
            try:
                rule = self._create_rule_from_config(rule_config)
                self.add_rule(rule)
            except Exception as e:
                self.logger.error(f"Failed to load rule {rule_config.get('name')}: {str(e)}")
    
    def _add_default_rules(self) -> None:
        """Add default alert rules."""
        # Critical alerts go to all channels
        self.add_rule(AlertRule(
            rule_id="critical_all_channels",
            name="Critical Alerts - All Channels",
            condition=lambda alert: alert.level == AlertLevel.CRITICAL,
            channels=[ch for ch in NotificationChannel],
            cooldown=0  # No cooldown for critical
        ))
        
        # Risk alerts
        self.add_rule(AlertRule(
            rule_id="risk_alerts",
            name="Risk Management Alerts",
            condition=lambda alert: alert.category == AlertCategory.RISK and alert.level >= AlertLevel.WARNING,
            channels=[NotificationChannel.TELEGRAM, NotificationChannel.SMS],
            cooldown=300
        ))
        
        # Trading hours only
        self.add_rule(AlertRule(
            rule_id="trading_hours_only",
            name="Trading Hours Only",
            condition=lambda alert: is_trading_hours() and alert.category == AlertCategory.TRADING,
            channels=[NotificationChannel.DESKTOP],
            cooldown=60
        ))
        
        # Performance summaries
        self.add_rule(AlertRule(
            rule_id="performance_summary",
            name="Performance Summaries",
            condition=lambda alert: alert.category == AlertCategory.PERFORMANCE,
            channels=[NotificationChannel.EMAIL],
            cooldown=3600  # 1 hour
        ))
    
    def _subscribe_to_events(self) -> None:
        """Subscribe to system events for alerts."""
        # Risk events
        self.event_manager.subscribe('RISK_LIMIT_EXCEEDED', self._on_risk_limit_exceeded)
        self.event_manager.subscribe('CIRCUIT_BREAKER_TRIGGERED', self._on_circuit_breaker)
        
        # Trading events
        self.event_manager.subscribe('POSITION_OPENED', self._on_position_opened)
        self.event_manager.subscribe('POSITION_CLOSED', self._on_position_closed)
        self.event_manager.subscribe('ORDER_REJECTED', self._on_order_rejected)
        
        # System events
        self.event_manager.subscribe('CONNECTION_LOST', self._on_connection_lost)
        self.event_manager.subscribe('CONNECTION_RESTORED', self._on_connection_restored)
        
        # Performance events
        self.event_manager.subscribe('DAILY_SUMMARY', self._on_daily_summary)
    
    def _start_processing(self) -> None:
        """Start alert processing thread."""
        self._worker_thread.start()
        self.logger.debug("Alert processing started")
    
    # =========================================================================
    # Public Methods - Alert Creation
    # =========================================================================
    
    def send_alert(self, level: AlertLevel, category: AlertCategory,
                  title: str, message: str, **kwargs) -> str:
        """
        Send an alert through configured channels.
        
        Args:
            level: Alert severity level
            category: Alert category
            title: Alert title
            message: Alert message
            **kwargs: Additional alert parameters
            
        Returns:
            Alert ID
        """
        # Create alert
        alert = Alert(
            alert_id=self._generate_alert_id(),
            level=level,
            category=category,
            title=title,
            message=message,
            details=kwargs.get('details'),
            channels=kwargs.get('channels', []),
            priority=kwargs.get('priority', self._level_to_priority(level)),
            metadata=kwargs.get('metadata', {}),
            attachments=kwargs.get('attachments', []),
            expires_at=kwargs.get('expires_at')
        )
        
        # Add to queue
        try:
            self.alert_queue.put_nowait(alert)
            self.stats['total_alerts'] += 1
            self.stats['by_level'][level.name] += 1
            
            self.logger.debug(f"Alert queued: {alert.alert_id} - {title}")
            
            return alert.alert_id
            
        except queue.Full:
            self.logger.error("Alert queue full, dropping alert")
            self.stats['failed_alerts'] += 1
            raise NotificationError("Alert queue full")
    
    def send_critical_alert(self, title: str, message: str, **kwargs) -> str:
        """
        Send a critical alert with highest priority.
        
        Args:
            title: Alert title
            message: Alert message
            **kwargs: Additional parameters
            
        Returns:
            Alert ID
        """
        return self.send_alert(
            AlertLevel.CRITICAL,
            kwargs.get('category', AlertCategory.SYSTEM),
            title,
            message,
            priority=10,
            **kwargs
        )
    
    def send_batch_alerts(self, alerts: List[Dict[str, Any]]) -> List[str]:
        """
        Send multiple alerts in batch.
        
        Args:
            alerts: List of alert dictionaries
            
        Returns:
            List of alert IDs
        """
        alert_ids = []
        
        for alert_data in alerts:
            try:
                alert_id = self.send_alert(**alert_data)
                alert_ids.append(alert_id)
            except Exception as e:
                self.logger.error(f"Failed to queue batch alert: {str(e)}")
        
        return alert_ids
    
    # =========================================================================
    # Public Methods - Rule Management
    # =========================================================================
    
    def add_rule(self, rule: AlertRule) -> None:
        """
        Add an alert rule.
        
        Args:
            rule: Alert rule to add
        """
        self.rules[rule.rule_id] = rule
        self.logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_id: str) -> None:
        """
        Remove an alert rule.
        
        Args:
            rule_id: Rule ID to remove
        """
        if rule_id in self.rules:
            del self.rules[rule_id]
            self.logger.info(f"Removed alert rule: {rule_id}")
    
    def enable_rule(self, rule_id: str) -> None:
        """Enable an alert rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
    
    def disable_rule(self, rule_id: str) -> None:
        """Disable an alert rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
    
    # =========================================================================
    # Public Methods - Channel Management
    # =========================================================================
    
    def enable_channel(self, channel: NotificationChannel) -> None:
        """Enable a notification channel."""
        if channel in self.channels:
            self.channels[channel].enabled = True
            self.logger.info(f"Enabled channel: {channel.value}")
    
    def disable_channel(self, channel: NotificationChannel) -> None:
        """Disable a notification channel."""
        if channel in self.channels:
            self.channels[channel].enabled = False
            self.logger.info(f"Disabled channel: {channel.value}")
    
    def test_channel(self, channel: NotificationChannel) -> bool:
        """
        Test a notification channel.
        
        Args:
            channel: Channel to test
            
        Returns:
            bool: Test success status
        """
        if channel not in self.channels:
            return False
        
        test_alert = Alert(
            alert_id="TEST_" + self._generate_alert_id(),
            level=AlertLevel.INFO,
            category=AlertCategory.SYSTEM,
            title="Test Alert",
            message="This is a test alert from Spyder Trading System",
            channels=[channel]
        )
        
        try:
            result = self.channels[channel].send(test_alert)
            return result.status == DeliveryStatus.SENT
        except Exception as e:
            self.logger.error(f"Channel test failed: {str(e)}")
            return False
    
    # =========================================================================
    # Public Methods - Alert History
    # =========================================================================
    
    def get_alert_history(self, hours: int = 24, 
                         level: Optional[AlertLevel] = None,
                         category: Optional[AlertCategory] = None) -> List[AlertHistory]:
        """
        Get alert history.
        
        Args:
            hours: Hours of history to retrieve
            level: Filter by level
            category: Filter by category
            
        Returns:
            List of alert history records
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        
        history = []
        for alert_history in self.history.values():
            if alert_history.first_sent and alert_history.first_sent >= cutoff:
                if level and alert_history.alert.level != level:
                    continue
                if category and alert_history.alert.category != category:
                    continue
                history.append(alert_history)
        
        return sorted(history, key=lambda h: h.first_sent or datetime.min, reverse=True)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get alert statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            'total_alerts': self.stats['total_alerts'],
            'sent_successfully': self.stats['sent_successfully'],
            'failed_alerts': self.stats['failed_alerts'],
            'rate_limited': self.stats['rate_limited'],
            'by_channel': dict(self.stats['by_channel']),
            'by_level': dict(self.stats['by_level']),
            'queue_size': self.alert_queue.qsize(),
            'active_rules': sum(1 for r in self.rules.values() if r.enabled),
            'active_channels': sum(1 for c in self.channels.values() if hasattr(c, 'enabled') and c.enabled)
        }
    
    # =========================================================================
    # Private Methods - Alert Processing
    # =========================================================================
    
    def _process_alerts(self) -> None:
        """Main alert processing loop."""
        while not self._stop_event.is_set():
            try:
                # Process new alerts
                self._process_new_alerts()
                
                # Process retries
                self._process_retries()
                
                # Cleanup old history
                self._cleanup_history()
                
                # Sleep briefly
                self._stop_event.wait(1)
                
            except Exception as e:
                self.logger.error(f"Error in alert processing: {str(e)}")
    
    def _process_new_alerts(self) -> None:
        """Process new alerts from queue."""
        batch = []
        
        # Collect alerts for batch processing
        while not self.alert_queue.empty() and len(batch) < 10:
            try:
                alert = self.alert_queue.get_nowait()
                batch.append(alert)
            except queue.Empty:
                break
        
        # Process batch
        for alert in batch:
            try:
                self._process_single_alert(alert)
            except Exception as e:
                self.logger.error(f"Failed to process alert {alert.alert_id}: {str(e)}")
    
    def _process_single_alert(self, alert: Alert) -> None:
        """
        Process a single alert.
        
        Args:
            alert: Alert to process
        """
        # Check expiration
        if alert.expires_at and datetime.now() > alert.expires_at:
            self.logger.debug(f"Alert {alert.alert_id} expired, skipping")
            return
        
        # Check cooldown
        if self._is_in_cooldown(alert):
            self.logger.debug(f"Alert {alert.alert_id} in cooldown, skipping")
            self.stats['rate_limited'] += 1
            return
        
        # Apply rules to determine channels
        channels = self._apply_rules(alert)
        
        # Add explicitly requested channels
        for channel in alert.channels:
            if channel not in channels:
                channels.append(channel)
        
        if not channels:
            self.logger.debug(f"No channels selected for alert {alert.alert_id}")
            return
        
        # Check rate limit
        if not self.rate_limiter.check():
            self.logger.warning("Rate limit exceeded, queuing for retry")
            self.stats['rate_limited'] += 1
            self._queue_retry(alert, 60)  # Retry in 1 minute
            return
        
        # Create history record
        history = AlertHistory(alert=alert)
        self.history[alert.alert_id] = history
        
        # Send to channels
        for channel in channels:
            if channel in self.channels:
                self._send_to_channel(alert, channel, history)
        
        # Update cooldown
        self._update_cooldown(alert)
        
        # Record alert
        self.recent_alerts.append(alert)
    
    def _send_to_channel(self, alert: Alert, channel: NotificationChannel,
                        history: AlertHistory) -> None:
        """
        Send alert to specific channel.
        
        Args:
            alert: Alert to send
            channel: Target channel
            history: Alert history record
        """
        try:
            # Apply template if available
            formatted_alert = self._format_alert(alert, channel)
            
            # Send through channel
            result = self.channels[channel].send(formatted_alert)
            
            # Update history
            history.results.append(result)
            history.total_attempts += 1
            
            if not history.first_sent:
                history.first_sent = datetime.now()
            history.last_sent = datetime.now()
            
            # Update statistics
            if result.status == DeliveryStatus.SENT:
                self.stats['sent_successfully'] += 1
                self.stats['by_channel'][channel.value] += 1
            else:
                self.stats['failed_alerts'] += 1
                
                # Retry critical alerts
                if alert.level == AlertLevel.CRITICAL and result.retry_count < MAX_RETRY_ATTEMPTS:
                    self._queue_retry(alert, RETRY_DELAYS[result.retry_count])
            
            self.logger.debug(f"Alert {alert.alert_id} sent to {channel.value}: {result.status.value}")
            
        except Exception as e:
            self.logger.error(f"Failed to send alert to {channel.value}: {str(e)}")
            self.stats['failed_alerts'] += 1
    
    def _process_retries(self) -> None:
        """Process retry queue."""
        current_time = datetime.now()
        
        while not self.retry_queue.empty():
            try:
                retry_time, alert = self.retry_queue.get_nowait()
                
                if retry_time <= current_time:
                    # Process retry
                    self._process_single_alert(alert)
                else:
                    # Put back in queue
                    self.retry_queue.put((retry_time, alert))
                    break
                    
            except queue.Empty:
                break
    
    # =========================================================================
    # Private Methods - Alert Rules
    # =========================================================================
    
    def _apply_rules(self, alert: Alert) -> List[NotificationChannel]:
        """
        Apply rules to determine target channels.
        
        Args:
            alert: Alert to process
            
        Returns:
            List of target channels
        """
        channels = set()
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            try:
                if rule.condition(alert):
                    # Check schedule
                    if rule.schedule and not self._check_schedule(rule.schedule):
                        continue
                    
                    # Add channels
                    for channel in rule.channels:
                        channels.add(channel)
                        
            except Exception as e:
                self.logger.error(f"Error applying rule {rule.name}: {str(e)}")
        
        # Sort by priority
        return sorted(channels, key=lambda c: CHANNEL_PRIORITIES.get(c.value, 99))
    
    def _check_schedule(self, schedule: Dict[str, Any]) -> bool:
        """
        Check if current time matches schedule.
        
        Args:
            schedule: Schedule configuration
            
        Returns:
            bool: Schedule match status
        """
        current_time = datetime.now()
        
        # Check days of week
        if 'days' in schedule:
            if current_time.weekday() not in schedule['days']:
                return False
        
        # Check time range
        if 'start_time' in schedule and 'end_time' in schedule:
            start = time.fromisoformat(schedule['start_time'])
            end = time.fromisoformat(schedule['end_time'])
            current = current_time.time()
            
            if not (start <= current <= end):
                return False
        
        return True
    
    # =========================================================================
    # Private Methods - Formatting
    # =========================================================================
    
    def _format_alert(self, alert: Alert, channel: NotificationChannel) -> Alert:
        """
        Format alert for specific channel.
        
        Args:
            alert: Original alert
            channel: Target channel
            
        Returns:
            Formatted alert
        """
        # Find applicable template
        template_name = f"{alert.category.name.lower()}_{alert.level.name.lower()}.{channel.value}.j2"
        
        try:
            template = self.template_env.get_template(template_name)
        except:
            # Fall back to default template
            try:
                template = self.template_env.get_template(f"default.{channel.value}.j2")
            except:
                # No template, return original
                return alert
        
        # Render template
        rendered_message = template.render(
            alert=alert,
            timestamp=alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            details=alert.details or {},
            metadata=alert.metadata
        )
        
        # Create formatted alert
        formatted = Alert(
            alert_id=alert.alert_id,
            level=alert.level,
            category=alert.category,
            title=alert.title,
            message=rendered_message,
            details=alert.details,
            channels=[channel],
            timestamp=alert.timestamp,
            metadata=alert.metadata,
            attachments=alert.attachments,
            priority=alert.priority,
            expires_at=alert.expires_at
        )
        
        return formatted
    
    # =========================================================================
    # Private Methods - Utilities
    # =========================================================================
    
    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"ALERT_{timestamp}"
    
    def _level_to_priority(self, level: AlertLevel) -> int:
        """Convert alert level to priority."""
        priorities = {
            AlertLevel.DEBUG: 1,
            AlertLevel.INFO: 3,
            AlertLevel.WARNING: 5,
            AlertLevel.ERROR: 7,
            AlertLevel.CRITICAL: 10
        }
        return priorities.get(level, 5)
    
    def _is_in_cooldown(self, alert: Alert) -> bool:
        """Check if alert type is in cooldown."""
        # Create cooldown key
        key = f"{alert.category.name}_{alert.level.name}_{alert.title}"
        
        if key in self._cooldown_tracker:
            last_sent = self._cooldown_tracker[key]
            cooldown_period = timedelta(seconds=DEFAULT_COOLDOWN)
            
            # Check rules for custom cooldown
            for rule in self.rules.values():
                if rule.enabled and rule.condition(alert):
                    cooldown_period = timedelta(seconds=rule.cooldown)
                    break
            
            if datetime.now() - last_sent < cooldown_period:
                return True
        
        return False
    
    def _update_cooldown(self, alert: Alert) -> None:
        """Update cooldown tracker."""
        key = f"{alert.category.name}_{alert.level.name}_{alert.title}"
        self._cooldown_tracker[key] = datetime.now()
    
    def _queue_retry(self, alert: Alert, delay_seconds: int) -> None:
        """Queue alert for retry."""
        retry_time = datetime.now() + timedelta(seconds=delay_seconds)
        self.retry_queue.put((retry_time, alert))
    
    def _cleanup_history(self) -> None:
        """Clean up old alert history."""
        cutoff = datetime.now() - timedelta(days=ALERT_RETENTION_DAYS)
        
        # Clean in-memory history
        old_alerts = []
        for alert_id, history in self.history.items():
            if history.last_sent and history.last_sent < cutoff:
                old_alerts.append(alert_id)
        
        for alert_id in old_alerts:
            del self.history[alert_id]
        
        # Clean cooldown tracker
        current_time = datetime.now()
        old_cooldowns = []
        for key, last_sent in self._cooldown_tracker.items():
            if current_time - last_sent > timedelta(hours=24):
                old_cooldowns.append(key)
        
        for key in old_cooldowns:
            del self._cooldown_tracker[key]
    
    def _create_rule_from_config(self, config: Dict[str, Any]) -> AlertRule:
        """Create rule from configuration."""
        # This would parse the configuration and create a rule
        # Simplified for this example
        return AlertRule(
            rule_id=config['id'],
            name=config['name'],
            condition=lambda alert: True,  # Would be parsed from config
            channels=[NotificationChannel(ch) for ch in config.get('channels', [])],
            cooldown=config.get('cooldown', DEFAULT_COOLDOWN),
            enabled=config.get('enabled', True)
        )
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    def _on_risk_limit_exceeded(self, event_data: Dict[str, Any]) -> None:
        """Handle risk limit exceeded event."""
        self.send_alert(
            level=AlertLevel.CRITICAL,
            category=AlertCategory.RISK,
            title="Risk Limit Exceeded",
            message=f"Risk limit exceeded: {event_data.get('limit_type')}",
            details=event_data
        )
    
    def _on_circuit_breaker(self, event_data: Dict[str, Any]) -> None:
        """Handle circuit breaker event."""
        self.send_alert(
            level=AlertLevel.CRITICAL,
            category=AlertCategory.RISK,
            title="Circuit Breaker Triggered",
            message=f"Trading halted: {event_data.get('reason')}",
            details=event_data
        )
    
    def _on_position_opened(self, event_data: Dict[str, Any]) -> None:
        """Handle position opened event."""
        self.send_alert(
            level=AlertLevel.INFO,
            category=AlertCategory.POSITION,
            title="Position Opened",
            message=f"New position: {event_data.get('symbol')} - {event_data.get('quantity')} contracts",
            details=event_data
        )
    
    def _on_position_closed(self, event_data: Dict[str, Any]) -> None:
        """Handle position closed event."""
        pnl = event_data.get('realized_pnl', 0)
        level = AlertLevel.INFO if pnl >= 0 else AlertLevel.WARNING
        
        self.send_alert(
            level=level,
            category=AlertCategory.POSITION,
            title="Position Closed",
            message=f"Position closed: {event_data.get('symbol')} - P&L: ${pnl:+,.2f}",
            details=event_data
        )
    
    def _on_order_rejected(self, event_data: Dict[str, Any]) -> None:
        """Handle order rejected event."""
        self.send_alert(
            level=AlertLevel.ERROR,
            category=AlertCategory.TRADING,
            title="Order Rejected",
            message=f"Order rejected: {event_data.get('reason')}",
            details=event_data
        )
    
    def _on_connection_lost(self, event_data: Dict[str, Any]) -> None:
        """Handle connection lost event."""
        self.send_alert(
            level=AlertLevel.CRITICAL,
            category=AlertCategory.CONNECTION,
            title="Connection Lost",
            message="Lost connection to Interactive Brokers",
            details=event_data
        )
    
    def _on_connection_restored(self, event_data: Dict[str, Any]) -> None:
        """Handle connection restored event."""
        self.send_alert(
            level=AlertLevel.INFO,
            category=AlertCategory.CONNECTION,
            title="Connection Restored",
            message="Connection to Interactive Brokers restored",
            details=event_data
        )
    
    def _on_daily_summary(self, event_data: Dict[str, Any]) -> None:
        """Handle daily summary event."""
        self.send_alert(
            level=AlertLevel.INFO,
            category=AlertCategory.PERFORMANCE,
            title="Daily Trading Summary",
            message=self._format_daily_summary(event_data),
            details=event_data,
            channels=[NotificationChannel.EMAIL]
        )
    
    def _format_daily_summary(self, data: Dict[str, Any]) -> str:
        """Format daily summary message."""
        return f"""
Daily Trading Summary - {datetime.now().strftime('%Y-%m-%d')}

Total P&L: ${data.get('total_pnl', 0):+,.2f}
Total Trades: {data.get('total_trades', 0)}
Win Rate: {data.get('win_rate', 0):.1%}
Positions Open: {data.get('open_positions', 0)}

Top Performing Strategy: {data.get('top_strategy', 'N/A')}
Worst Performing Strategy: {data.get('worst_strategy', 'N/A')}

Account Equity: ${data.get('account_equity', 0):,.2f}
Daily Return: {data.get('daily_return', 0):+.2%}
"""
    
    def shutdown(self) -> None:
        """Shutdown alert manager."""
        self.logger.info("Shutting down alert manager")
        
        # Stop processing
        self._stop_event.set()
        
        # Wait for worker thread
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
        
        # Close channels
        for channel in self.channels.values():
            if hasattr(channel, 'close'):
                channel.close()
        
        self.logger.info("Alert manager shutdown complete")

# =============================================================================
# Channel Implementations
# =============================================================================
class EmailChannel:
    """Email notification channel."""
    
    def __init__(self, smtp_host: str, smtp_port: int, username: str,
                password: str, from_address: str, to_addresses: List[str]):
        """Initialize email channel."""
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.to_addresses = to_addresses
        self.enabled = True
        
    def send(self, alert: Alert) -> NotificationResult:
        """Send email notification."""
        if not self.enabled:
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.EMAIL,
                status=DeliveryStatus.FAILED,
                error="Channel disabled"
            )
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_address
            msg['To'] = ', '.join(self.to_addresses)
            msg['Subject'] = f"[{alert.level.name}] {alert.title}"
            
            # Add body
            body = alert.message
            if alert.details:
                body += "\n\nDetails:\n" + json.dumps(alert.details, indent=2)
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments
            for attachment_path in alert.attachments:
                if os.path.exists(attachment_path):
                    with open(attachment_path, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {os.path.basename(attachment_path)}'
                        )
                        msg.attach(part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.EMAIL,
                status=DeliveryStatus.SENT
            )
            
        except Exception as e:
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.EMAIL,
                status=DeliveryStatus.FAILED,
                error=str(e)
            )

class SMSChannel:
    """SMS notification channel using Twilio."""
    
    def __init__(self, account_sid: str, auth_token: str,
                from_number: str, to_numbers: List[str]):
        """Initialize SMS channel."""
        self.client = TwilioClient(account_sid, auth_token)
        self.from_number = from_number
        self.to_numbers = to_numbers
        self.enabled = True
        
    def send(self, alert: Alert) -> NotificationResult:
        """Send SMS notification."""
        if not self.enabled:
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.SMS,
                status=DeliveryStatus.FAILED,
                error="Channel disabled"
            )
        
        try:
            # Format message for SMS (limited length)
            message = f"[{alert.level.name}] {alert.title}\n{alert.message[:140]}"
            
            # Send to all numbers
            for to_number in self.to_numbers:
                self.client.messages.create(
                    body=message,
                    from_=self.from_number,
                    to=to_number
                )
            
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.SMS,
                status=DeliveryStatus.SENT
            )
            
        except Exception as e:
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.SMS,
                status=DeliveryStatus.FAILED,
                error=str(e)
            )

class TelegramChannel:
    """Telegram notification channel."""
    
    def __init__(self, bot_token: str, chat_ids: List[str]):
        """Initialize Telegram channel."""
        self.bot = telegram.Bot(token=bot_token)
        self.chat_ids = chat_ids
        self.enabled = True
        
    def send(self, alert: Alert) -> NotificationResult:
        """Send Telegram notification."""
        if not self.enabled:
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.TELEGRAM,
                status=DeliveryStatus.FAILED,
                error="Channel disabled"
            )
        
        try:
            # Format message with markdown
            level_emoji = {
                AlertLevel.DEBUG: "🔍",
                AlertLevel.INFO: "ℹ️",
                AlertLevel.WARNING: "⚠️",
                AlertLevel.ERROR: "❌",
                AlertLevel.CRITICAL: "🚨"
            }
            
            emoji = level_emoji.get(alert.level, "📢")
            message = f"{emoji} *{alert.title}*\n\n{alert.message}"
            
            # Add details if present
            if alert.details:
                details_text = "\n".join(f"• {k}: {v}" for k, v in alert.details.items())
                message += f"\n\n*Details:*\n{details_text}"
            
            # Send to all chats
            for chat_id in self.chat_ids:
                self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=telegram.ParseMode.MARKDOWN
                )
            
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.TELEGRAM,
                status=DeliveryStatus.SENT
            )
            
        except Exception as e:
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.TELEGRAM,
                status=DeliveryStatus.FAILED,
                error=str(e)
            )

class DesktopChannel:
    """Desktop notification channel."""
    
    def __init__(self):
        """Initialize desktop channel."""
        self.enabled = True
        
    def send(self, alert: Alert) -> NotificationResult:
        """Send desktop notification."""
        if not self.enabled:
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.DESKTOP,
                status=DeliveryStatus.FAILED,
                error="Channel disabled"
            )
        
        try:
            # Desktop notifications are brief
            desktop_notification.notify(
                title=f"[{alert.level.name}] {alert.title}",
                message=alert.message[:256],  # Limit length
                app_name="Spyder Trading",
                timeout=10
            )
            
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.DESKTOP,
                status=DeliveryStatus.SENT
            )
            
        except Exception as e:
            return NotificationResult(
                alert_id=alert.alert_id,
                channel=NotificationChannel.DESKTOP,
                status=DeliveryStatus.FAILED,
                error=str(e)
            )

# =============================================================================
# Helper Classes
# =============================================================================
class RateLimiter:
    """Simple rate limiter implementation."""
    
    def __init__(self, max_per_minute: int):
        """Initialize rate limiter."""
        self.max_per_minute = max_per_minute
        self.requests = deque()
        self._lock = threading.Lock()
        
    def check(self) -> bool:
        """Check if request is allowed."""
        with self._lock:
            now = datetime.now()
            
            # Remove old requests
            cutoff = now - timedelta(minutes=1)
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            # Check limit
            if len(self.requests) >= self.max_per_minute:
                return False
            
            # Add request
            self.requests.append(now)
            return True

# =============================================================================
# Module Functions
# =============================================================================
def get_alert_manager() -> AlertManager:
    """
    Get singleton instance of alert manager.
    
    Returns:
        AlertManager instance
    """
    global _ALERT_MANAGER_INSTANCE
    if _ALERT_MANAGER_INSTANCE is None:
        _ALERT_MANAGER_INSTANCE = AlertManager()
    return _ALERT_MANAGER_INSTANCE

def send_quick_alert(title: str, message: str, level: AlertLevel = AlertLevel.INFO) -> str:
    """
    Send a quick alert without detailed configuration.
    
    Args:
        title: Alert title
        message: Alert message
        level: Alert level
        
    Returns:
        Alert ID
    """
    manager = get_alert_manager()
    return manager.send_alert(
        level=level,
        category=AlertCategory.SYSTEM,
        title=title,
        message=message
    )

# =============================================================================
# Module Initialization
# =============================================================================
_ALERT_MANAGER_INSTANCE: Optional[AlertManager] = None