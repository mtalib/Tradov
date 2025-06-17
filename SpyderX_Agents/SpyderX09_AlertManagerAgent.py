#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX09_AlertManagerAgent.py
Purpose: AI-Enhanced Alert Management and Intelligent Notifications
Group: X (AI Agents)

Description:
    Replaces traditional alert modules (SpyderJ group) with an intelligent
    AI agent that filters, prioritizes, and delivers alerts through appropriate
    channels. Reduces alert fatigue while ensuring critical information is
    never missed.

    Replaced Modules:
    - SpyderJ01_AlertEngine
    - SpyderJ02_NotificationChannels
    - SpyderJ03_AlertFilters
    - SpyderJ04_AlertHistory
    - SpyderJ05_AlertDashboard
    
    This agent ensures traders receive the right information at the right time
    through the right channel with appropriate context.

Author: AI Trading Assistant
Date: 2025-01-17
Version: 1.0.0

Dependencies:
    - ollama (for LLM integration)
    - numpy, pandas
    - asyncio
    - email/smtp (for email alerts)
    - twilio (for SMS alerts)
    - discord.py (for Discord alerts)
    - slack_sdk (for Slack alerts)
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import hashlib
import re
from abc import ABC, abstractmethod

# Import Spyder core components
from SpyderU01_DataStructures import (
    Portfolio, Position, Trade, MarketData
)
from SpyderU02_Configuration import config
from SpyderU03_Logger import SpyderLogger
from SpyderU04_EventManager import Event, EventType
from SpyderU12_AgentIntegration import SpyderBaseAgent, AgentState

# Alert Types
class AlertType(Enum):
    """Types of alerts"""
    # Trading Alerts
    TRADE_EXECUTED = "trade_executed"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    
    # Risk Alerts
    RISK_LIMIT_WARNING = "risk_limit_warning"
    RISK_LIMIT_BREACH = "risk_limit_breach"
    DRAWDOWN_WARNING = "drawdown_warning"
    MARGIN_CALL = "margin_call"
    POSITION_SIZE_ALERT = "position_size_alert"
    
    # Market Alerts
    MARKET_VOLATILITY = "market_volatility"
    UNUSUAL_VOLUME = "unusual_volume"
    PRICE_BREAKOUT = "price_breakout"
    SUPPORT_RESISTANCE = "support_resistance"
    MARKET_REGIME_CHANGE = "market_regime_change"
    
    # Performance Alerts
    DAILY_PNL = "daily_pnl"
    MILESTONE_REACHED = "milestone_reached"
    STREAK_ALERT = "streak_alert"
    PERFORMANCE_WARNING = "performance_warning"
    
    # System Alerts
    SYSTEM_ERROR = "system_error"
    CONNECTION_LOST = "connection_lost"
    DATA_FEED_ISSUE = "data_feed_issue"
    STRATEGY_ERROR = "strategy_error"
    
    # Scheduled Alerts
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"
    REPORT_READY = "report_ready"
    MAINTENANCE_REMINDER = "maintenance_reminder"

# Alert Priority Levels
class AlertPriority(Enum):
    """Alert priority levels"""
    CRITICAL = 5  # Immediate action required
    HIGH = 4      # Important, needs attention soon
    MEDIUM = 3    # Normal priority
    LOW = 2       # Informational
    DEBUG = 1     # Development/debugging only

# Delivery Channels
class DeliveryChannel(Enum):
    """Alert delivery channels"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    DISCORD = "discord"
    SLACK = "slack"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    DESKTOP = "desktop"
    LOG = "log"

@dataclass
class Alert:
    """Alert data structure"""
    alert_id: str
    alert_type: AlertType
    priority: AlertPriority
    title: str
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    source: str
    tags: List[str] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, str]] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    group_id: Optional[str] = None
    dedupe_key: Optional[str] = None

@dataclass
class AlertRule:
    """Alert filtering and routing rule"""
    rule_id: str
    name: str
    conditions: Dict[str, Any]
    actions: Dict[str, Any]
    priority_override: Optional[AlertPriority] = None
    channels: List[DeliveryChannel] = field(default_factory=list)
    schedule: Optional[Dict[str, Any]] = None
    enabled: bool = True
    cooldown_minutes: int = 0
    max_alerts_per_hour: Optional[int] = None

@dataclass
class AlertDelivery:
    """Alert delivery record"""
    delivery_id: str
    alert_id: str
    channel: DeliveryChannel
    recipient: str
    status: str  # sent, failed, pending
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0

@dataclass
class AlertSummary:
    """Alert summary for digest"""
    period: Tuple[datetime, datetime]
    total_alerts: int
    by_type: Dict[AlertType, int]
    by_priority: Dict[AlertPriority, int]
    top_alerts: List[Alert]
    suppressed_count: int
    delivery_stats: Dict[DeliveryChannel, Dict[str, int]]

class AlertChannel(ABC):
    """Abstract base class for alert channels"""
    
    @abstractmethod
    async def send(self, alert: Alert, recipient: str) -> bool:
        """Send alert through channel"""
        pass
    
    @abstractmethod
    async def validate_recipient(self, recipient: str) -> bool:
        """Validate recipient format"""
        pass

class AlertManagerAgent(SpyderBaseAgent):
    """
    AI-Enhanced Alert Manager Agent
    
    Intelligently manages alerts with filtering, prioritization,
    and multi-channel delivery with natural language enhancements.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Alert Manager Agent"""
        super().__init__(config)
        
        # Agent configuration
        self.llm_model = config.get('alert_llm_model', 'llama3.2:3b-instruct-q4_K_M')
        self.default_cooldown = config.get('alert_cooldown_minutes', 5)
        self.max_alerts_per_hour = config.get('max_alerts_per_hour', 50)
        
        # Alert storage
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.delivery_history: List[AlertDelivery] = []
        
        # Rules and filters
        self.alert_rules: Dict[str, AlertRule] = {}
        self.channel_preferences: Dict[AlertType, List[DeliveryChannel]] = {}
        self.recipient_preferences: Dict[str, Dict[str, Any]] = {}
        
        # Deduplication and rate limiting
        self.alert_cache: Dict[str, datetime] = {}  # dedupe_key -> last_sent
        self.rate_limits: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Alert grouping
        self.alert_groups: Dict[str, List[Alert]] = defaultdict(list)
        self.group_timers: Dict[str, asyncio.Task] = {}
        
        # Channel implementations
        self.channels: Dict[DeliveryChannel, AlertChannel] = {}
        self._initialize_channels()
        
        # Performance tracking
        self.delivery_metrics: Dict[DeliveryChannel, Dict[str, int]] = defaultdict(
            lambda: {'sent': 0, 'delivered': 0, 'failed': 0}
        )
        
        # AI enhancement cache
        self.enhanced_messages: Dict[str, str] = {}
        
        # Alert patterns
        self.alert_patterns: Dict[str, List[Alert]] = defaultdict(list)
        self.pattern_insights: Dict[str, str] = {}
        
        self.logger.info("Alert Manager Agent initialized")

    async def initialize(self, event_manager=None):
        """Initialize agent with dependencies"""
        await super().initialize(event_manager)
        
        # Load alert rules
        await self._load_alert_rules()
        
        # Load recipient preferences
        await self._load_recipient_preferences()
        
        # Subscribe to all events for alert generation
        if self.event_manager:
            # Trading events
            self.event_manager.subscribe(EventType.TRADE_EXECUTED, self._handle_trade_event)
            self.event_manager.subscribe(EventType.ORDER_FILLED, self._handle_order_event)
            self.event_manager.subscribe(EventType.ORDER_REJECTED, self._handle_order_event)
            
            # Risk events
            self.event_manager.subscribe(EventType.RISK_ALERT, self._handle_risk_event)
            self.event_manager.subscribe(EventType.DRAWDOWN_ALERT, self._handle_risk_event)
            
            # Market events
            self.event_manager.subscribe(EventType.MARKET_DATA_UPDATE, self._handle_market_event)
            self.event_manager.subscribe(EventType.VOLATILITY_SPIKE, self._handle_market_event)
            
            # Performance events
            self.event_manager.subscribe(EventType.DAILY_PNL_UPDATE, self._handle_performance_event)
            self.event_manager.subscribe(EventType.REPORT_GENERATED, self._handle_report_event)
            
            # System events
            self.event_manager.subscribe(EventType.SYSTEM_ERROR, self._handle_system_event)
            self.event_manager.subscribe(EventType.CONNECTION_STATUS, self._handle_system_event)
        
        # Start background tasks
        asyncio.create_task(self._process_alert_queue())
        asyncio.create_task(self._send_scheduled_alerts())
        asyncio.create_task(self._analyze_alert_patterns())
        asyncio.create_task(self._cleanup_expired_alerts())
        
        self.state = AgentState.RUNNING
        self.logger.info("Alert Manager Agent initialized and running")

    async def create_alert(
        self,
        alert_type: AlertType,
        title: str,
        message: str,
        priority: Optional[AlertPriority] = None,
        details: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        dedupe_key: Optional[str] = None,
        group_id: Optional[str] = None
    ) -> Alert:
        """
        Create and process a new alert
        
        Args:
            alert_type: Type of alert
            title: Alert title
            message: Alert message
            priority: Override default priority
            details: Additional details
            tags: Alert tags for filtering
            dedupe_key: Key for deduplication
            group_id: Group ID for batching
            
        Returns:
            Created alert
        """
        try:
            # Determine priority if not specified
            if priority is None:
                priority = self._determine_priority(alert_type, details)
            
            # Check deduplication
            if dedupe_key and self._is_duplicate(dedupe_key):
                self.logger.debug(f"Alert deduplicated: {dedupe_key}")
                return None
            
            # Create alert
            alert = Alert(
                alert_id=self._generate_alert_id(),
                alert_type=alert_type,
                priority=priority,
                title=title,
                message=message,
                details=details or {},
                timestamp=datetime.now(),
                source=self.__class__.__name__,
                tags=tags or [],
                dedupe_key=dedupe_key,
                group_id=group_id
            )
            
            # Apply rules and filters
            alert = await self._apply_alert_rules(alert)
            
            if alert:  # Alert not filtered out
                # Enhance with AI
                alert = await self._enhance_alert_with_ai(alert)
                
                # Store alert
                self.active_alerts[alert.alert_id] = alert
                self.alert_history.append(alert)
                
                # Update deduplication cache
                if dedupe_key:
                    self.alert_cache[dedupe_key] = datetime.now()
                
                # Process alert
                await self._process_alert(alert)
                
                self.logger.info(
                    f"Alert created: {alert.alert_type.value} - {alert.title} "
                    f"(Priority: {alert.priority.value})"
                )
            
            return alert
            
        except Exception as e:
            self.logger.error(f"Error creating alert: {str(e)}")
            return None

    async def send_alert(
        self,
        alert: Alert,
        channels: Optional[List[DeliveryChannel]] = None,
        recipients: Optional[List[str]] = None
    ) -> List[AlertDelivery]:
        """
        Send alert through specified channels
        
        Args:
            alert: Alert to send
            channels: Override default channels
            recipients: Override default recipients
            
        Returns:
            List of delivery records
        """
        try:
            # Determine channels
            if not channels:
                channels = self._determine_channels(alert)
            
            # Determine recipients
            if not recipients:
                recipients = self._determine_recipients(alert, channels)
            
            # Check rate limits
            if not self._check_rate_limits(alert):
                self.logger.warning(f"Alert rate limited: {alert.alert_type.value}")
                return []
            
            deliveries = []
            
            for channel in channels:
                for recipient in recipients.get(channel, []):
                    # Create delivery record
                    delivery = AlertDelivery(
                        delivery_id=self._generate_delivery_id(),
                        alert_id=alert.alert_id,
                        channel=channel,
                        recipient=recipient,
                        status='pending'
                    )
                    
                    # Send through channel
                    success = await self._send_through_channel(
                        alert, channel, recipient, delivery
                    )
                    
                    # Update delivery record
                    if success:
                        delivery.status = 'sent'
                        delivery.sent_at = datetime.now()
                        self.delivery_metrics[channel]['sent'] += 1
                    else:
                        delivery.status = 'failed'
                        self.delivery_metrics[channel]['failed'] += 1
                    
                    deliveries.append(delivery)
                    self.delivery_history.append(delivery)
            
            return deliveries
            
        except Exception as e:
            self.logger.error(f"Error sending alert: {str(e)}")
            return []

    async def get_alert_summary(
        self,
        hours: int = 24,
        alert_types: Optional[List[AlertType]] = None
    ) -> AlertSummary:
        """
        Get summary of alerts for period
        
        Args:
            hours: Number of hours to look back
            alert_types: Filter by alert types
            
        Returns:
            Alert summary
        """
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            period = (start_time, end_time)
            
            # Filter alerts
            period_alerts = [
                alert for alert in self.alert_history
                if start_time <= alert.timestamp <= end_time
            ]
            
            if alert_types:
                period_alerts = [
                    alert for alert in period_alerts
                    if alert.alert_type in alert_types
                ]
            
            # Count by type
            by_type = defaultdict(int)
            for alert in period_alerts:
                by_type[alert.alert_type] += 1
            
            # Count by priority
            by_priority = defaultdict(int)
            for alert in period_alerts:
                by_priority[alert.priority] += 1
            
            # Top alerts (highest priority)
            top_alerts = sorted(
                period_alerts,
                key=lambda a: (a.priority.value, a.timestamp),
                reverse=True
            )[:10]
            
            # Delivery stats
            delivery_stats = {}
            period_deliveries = [
                d for d in self.delivery_history
                if d.sent_at and start_time <= d.sent_at <= end_time
            ]
            
            for channel in DeliveryChannel:
                channel_deliveries = [
                    d for d in period_deliveries if d.channel == channel
                ]
                delivery_stats[channel] = {
                    'sent': len([d for d in channel_deliveries if d.status == 'sent']),
                    'failed': len([d for d in channel_deliveries if d.status == 'failed']),
                    'pending': len([d for d in channel_deliveries if d.status == 'pending'])
                }
            
            # Count suppressed alerts
            suppressed = len([
                key for key, timestamp in self.alert_cache.items()
                if start_time <= timestamp <= end_time
            ])
            
            return AlertSummary(
                period=period,
                total_alerts=len(period_alerts),
                by_type=dict(by_type),
                by_priority=dict(by_priority),
                top_alerts=top_alerts,
                suppressed_count=suppressed,
                delivery_stats=delivery_stats
            )
            
        except Exception as e:
            self.logger.error(f"Error generating alert summary: {str(e)}")
            return None

    async def create_alert_rule(
        self,
        name: str,
        conditions: Dict[str, Any],
        actions: Dict[str, Any],
        channels: Optional[List[DeliveryChannel]] = None,
        priority_override: Optional[AlertPriority] = None,
        schedule: Optional[Dict[str, Any]] = None
    ) -> AlertRule:
        """
        Create custom alert rule
        
        Args:
            name: Rule name
            conditions: Conditions for rule to apply
            actions: Actions to take
            channels: Delivery channels
            priority_override: Override alert priority
            schedule: Schedule constraints
            
        Returns:
            Created rule
        """
        try:
            rule = AlertRule(
                rule_id=self._generate_rule_id(),
                name=name,
                conditions=conditions,
                actions=actions,
                priority_override=priority_override,
                channels=channels or [],
                schedule=schedule,
                enabled=True
            )
            
            # Validate rule
            if self._validate_rule(rule):
                self.alert_rules[rule.rule_id] = rule
                
                # Persist rule
                await self._save_rule(rule)
                
                self.logger.info(f"Alert rule created: {name}")
                return rule
            else:
                self.logger.error(f"Invalid alert rule: {name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating alert rule: {str(e)}")
            return None

    async def update_preferences(
        self,
        recipient: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """
        Update recipient preferences
        
        Args:
            recipient: Recipient identifier
            preferences: Preference settings
            
        Returns:
            Success status
        """
        try:
            self.recipient_preferences[recipient] = preferences
            
            # Persist preferences
            await self._save_preferences(recipient, preferences)
            
            self.logger.info(f"Updated preferences for {recipient}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating preferences: {str(e)}")
            return False

    def _initialize_channels(self):
        """Initialize delivery channels"""
        # Email channel
        self.channels[DeliveryChannel.EMAIL] = EmailChannel(self.config)
        
        # SMS channel
        self.channels[DeliveryChannel.SMS] = SMSChannel(self.config)
        
        # Discord channel
        self.channels[DeliveryChannel.DISCORD] = DiscordChannel(self.config)
        
        # Slack channel
        self.channels[DeliveryChannel.SLACK] = SlackChannel(self.config)
        
        # Desktop notifications
        self.channels[DeliveryChannel.DESKTOP] = DesktopChannel(self.config)
        
        # Log channel (always available)
        self.channels[DeliveryChannel.LOG] = LogChannel(self.config)

    def _determine_priority(
        self,
        alert_type: AlertType,
        details: Optional[Dict[str, Any]]
    ) -> AlertPriority:
        """Determine alert priority based on type and details"""
        # Critical alerts
        critical_types = [
            AlertType.RISK_LIMIT_BREACH,
            AlertType.MARGIN_CALL,
            AlertType.SYSTEM_ERROR,
            AlertType.CONNECTION_LOST
        ]
        
        if alert_type in critical_types:
            return AlertPriority.CRITICAL
        
        # High priority alerts
        high_types = [
            AlertType.RISK_LIMIT_WARNING,
            AlertType.DRAWDOWN_WARNING,
            AlertType.ORDER_REJECTED,
            AlertType.STRATEGY_ERROR
        ]
        
        if alert_type in high_types:
            return AlertPriority.HIGH
        
        # Check details for priority hints
        if details:
            if details.get('loss_amount', 0) > 1000:
                return AlertPriority.HIGH
            if details.get('drawdown', 0) > 0.05:
                return AlertPriority.HIGH
            if details.get('volatility_spike', False):
                return AlertPriority.MEDIUM
        
        # Default priorities by category
        if alert_type.value.startswith('trade_'):
            return AlertPriority.MEDIUM
        elif alert_type.value.startswith('market_'):
            return AlertPriority.LOW
        else:
            return AlertPriority.MEDIUM

    def _is_duplicate(self, dedupe_key: str) -> bool:
        """Check if alert is duplicate"""
        if dedupe_key in self.alert_cache:
            last_sent = self.alert_cache[dedupe_key]
            cooldown = timedelta(minutes=self.default_cooldown)
            
            if datetime.now() - last_sent < cooldown:
                return True
        
        return False

    def _generate_alert_id(self) -> str:
        """Generate unique alert ID"""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(f"alert_{timestamp}".encode()).hexdigest()[:12]

    def _generate_delivery_id(self) -> str:
        """Generate unique delivery ID"""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(f"delivery_{timestamp}".encode()).hexdigest()[:12]

    def _generate_rule_id(self) -> str:
        """Generate unique rule ID"""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(f"rule_{timestamp}".encode()).hexdigest()[:12]

    async def _apply_alert_rules(self, alert: Alert) -> Optional[Alert]:
        """Apply rules to filter and modify alert"""
        for rule_id, rule in self.alert_rules.items():
            if not rule.enabled:
                continue
            
            # Check conditions
            if self._matches_conditions(alert, rule.conditions):
                # Apply actions
                if 'suppress' in rule.actions and rule.actions['suppress']:
                    self.logger.debug(f"Alert suppressed by rule {rule.name}")
                    return None
                
                if 'modify_priority' in rule.actions:
                    alert.priority = AlertPriority(rule.actions['modify_priority'])
                
                if 'add_tags' in rule.actions:
                    alert.tags.extend(rule.actions['add_tags'])
                
                if 'set_channels' in rule.actions:
                    # Store channel override
                    alert.details['channel_override'] = rule.actions['set_channels']
                
                # Apply priority override
                if rule.priority_override:
                    alert.priority = rule.priority_override
        
        return alert

    def _matches_conditions(self, alert: Alert, conditions: Dict[str, Any]) -> bool:
        """Check if alert matches rule conditions"""
        for field, condition in conditions.items():
            if field == 'alert_type':
                if isinstance(condition, list):
                    if alert.alert_type.value not in condition:
                        return False
                elif alert.alert_type.value != condition:
                    return False
            
            elif field == 'priority':
                if isinstance(condition, str):
                    if condition == 'gte' and alert.priority.value < conditions.get('priority_value', 3):
                        return False
                    elif condition == 'lte' and alert.priority.value > conditions.get('priority_value', 3):
                        return False
            
            elif field == 'tags':
                required_tags = condition if isinstance(condition, list) else [condition]
                if not all(tag in alert.tags for tag in required_tags):
                    return False
            
            elif field == 'details':
                for detail_key, detail_condition in condition.items():
                    if detail_key not in alert.details:
                        return False
                    
                    if isinstance(detail_condition, dict):
                        # Complex condition
                        if 'gte' in detail_condition:
                            if alert.details[detail_key] < detail_condition['gte']:
                                return False
                        if 'lte' in detail_condition:
                            if alert.details[detail_key] > detail_condition['lte']:
                                return False
                    else:
                        # Simple equality
                        if alert.details[detail_key] != detail_condition:
                            return False
            
            elif field == 'time':
                # Time-based conditions
                current_time = datetime.now().time()
                if 'after' in condition:
                    after_time = time.fromisoformat(condition['after'])
                    if current_time < after_time:
                        return False
                if 'before' in condition:
                    before_time = time.fromisoformat(condition['before'])
                    if current_time > before_time:
                        return False
        
        return True

    async def _enhance_alert_with_ai(self, alert: Alert) -> Alert:
        """Enhance alert with AI-generated context"""
        try:
            # Check cache
            cache_key = f"{alert.alert_type.value}_{alert.title}"
            if cache_key in self.enhanced_messages:
                alert.message = self.enhanced_messages[cache_key]
                return alert
            
            # Prepare context for AI
            context = {
                'alert_type': alert.alert_type.value,
                'title': alert.title,
                'original_message': alert.message,
                'details': alert.details,
                'priority': alert.priority.value
            }
            
            prompt = f"""
            Enhance this trading alert with helpful context:
            
            Type: {context['alert_type']}
            Title: {context['title']}
            Message: {context['original_message']}
            Details: {json.dumps(context['details'], indent=2)}
            
            Provide:
            1. A clear, concise enhanced message (2-3 sentences)
            2. What this means for the trader
            3. Any recommended actions
            
            Keep it professional but conversational. Format as JSON:
            {{
                "enhanced_message": "...",
                "implications": "...",
                "actions": ["action1", "action2"]
            }}
            """
            
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=2.0)
            ai_enhancement = json.loads(response)
            
            # Update alert
            alert.message = ai_enhancement['enhanced_message']
            
            # Add implications to details
            alert.details['implications'] = ai_enhancement['implications']
            
            # Add suggested actions
            for action in ai_enhancement.get('actions', []):
                alert.actions.append({
                    'label': action,
                    'type': 'suggestion'
                })
            
            # Cache enhanced message
            self.enhanced_messages[cache_key] = alert.message
            
        except Exception as e:
            self.logger.debug(f"AI enhancement failed, using original: {str(e)}")
        
        return alert

    def _determine_channels(self, alert: Alert) -> List[DeliveryChannel]:
        """Determine delivery channels for alert"""
        # Check for override
        if 'channel_override' in alert.details:
            return alert.details['channel_override']
        
        # Use priority-based defaults
        if alert.priority == AlertPriority.CRITICAL:
            return [DeliveryChannel.SMS, DeliveryChannel.EMAIL, DeliveryChannel.DESKTOP]
        elif alert.priority == AlertPriority.HIGH:
            return [DeliveryChannel.EMAIL, DeliveryChannel.DESKTOP]
        elif alert.priority == AlertPriority.MEDIUM:
            return [DeliveryChannel.EMAIL]
        else:
            return [DeliveryChannel.LOG]

    def _determine_recipients(
        self,
        alert: Alert,
        channels: List[DeliveryChannel]
    ) -> Dict[DeliveryChannel, List[str]]:
        """Determine recipients for each channel"""
        recipients = defaultdict(list)
        
        # Get default recipients from config
        for channel in channels:
            if channel == DeliveryChannel.EMAIL:
                recipients[channel] = self.config.get('alert_email_recipients', [])
            elif channel == DeliveryChannel.SMS:
                recipients[channel] = self.config.get('alert_sms_recipients', [])
            elif channel == DeliveryChannel.DISCORD:
                recipients[channel] = [self.config.get('discord_webhook_url', '')]
            elif channel == DeliveryChannel.SLACK:
                recipients[channel] = [self.config.get('slack_webhook_url', '')]
            elif channel == DeliveryChannel.DESKTOP:
                recipients[channel] = ['default']
            elif channel == DeliveryChannel.LOG:
                recipients[channel] = ['system']
        
        # Apply recipient preferences
        for recipient, prefs in self.recipient_preferences.items():
            # Check if recipient wants this alert type
            if 'alert_types' in prefs:
                if alert.alert_type.value not in prefs['alert_types']:
                    # Remove from all channels
                    for channel in recipients:
                        if recipient in recipients[channel]:
                            recipients[channel].remove(recipient)
            
            # Check quiet hours
            if 'quiet_hours' in prefs:
                start_hour = prefs['quiet_hours']['start']
                end_hour = prefs['quiet_hours']['end']
                current_hour = datetime.now().hour
                
                if start_hour <= current_hour <= end_hour:
                    # Only allow critical alerts
                    if alert.priority != AlertPriority.CRITICAL:
                        for channel in recipients:
                            if recipient in recipients[channel]:
                                recipients[channel].remove(recipient)
        
        return dict(recipients)

    def _check_rate_limits(self, alert: Alert) -> bool:
        """Check if alert passes rate limits"""
        # Global rate limit
        global_key = 'global'
        self.rate_limits[global_key].append(datetime.now())
        
        # Remove old entries
        cutoff = datetime.now() - timedelta(hours=1)
        self.rate_limits[global_key] = deque(
            [t for t in self.rate_limits[global_key] if t > cutoff],
            maxlen=100
        )
        
        if len(self.rate_limits[global_key]) > self.max_alerts_per_hour:
            return False
        
        # Per-type rate limit
        type_key = alert.alert_type.value
        self.rate_limits[type_key].append(datetime.now())
        
        # Type-specific limits
        type_limits = {
            AlertType.TRADE_EXECUTED: 20,
            AlertType.MARKET_VOLATILITY: 5,
            AlertType.DAILY_PNL: 1
        }
        
        type_limit = type_limits.get(alert.alert_type, 10)
        
        if len(self.rate_limits[type_key]) > type_limit:
            return False
        
        return True

    async def _send_through_channel(
        self,
        alert: Alert,
        channel: DeliveryChannel,
        recipient: str,
        delivery: AlertDelivery
    ) -> bool:
        """Send alert through specific channel"""
        try:
            if channel in self.channels:
                channel_impl = self.channels[channel]
                
                # Validate recipient
                if not await channel_impl.validate_recipient(recipient):
                    delivery.error_message = f"Invalid recipient: {recipient}"
                    return False
                
                # Send alert
                success = await channel_impl.send(alert, recipient)
                
                if success:
                    delivery.delivered_at = datetime.now()
                else:
                    delivery.error_message = "Channel send failed"
                
                return success
            else:
                delivery.error_message = f"Channel not configured: {channel.value}"
                return False
                
        except Exception as e:
            delivery.error_message = str(e)
            self.logger.error(f"Error sending through {channel.value}: {str(e)}")
            return False

    async def _process_alert(self, alert: Alert):
        """Process alert for delivery"""
        # Check if alert should be grouped
        if alert.group_id:
            self.alert_groups[alert.group_id].append(alert)
            
            # Reset group timer
            if alert.group_id in self.group_timers:
                self.group_timers[alert.group_id].cancel()
            
            # Set new timer
            self.group_timers[alert.group_id] = asyncio.create_task(
                self._send_grouped_alerts(alert.group_id)
            )
        else:
            # Send immediately
            await self.send_alert(alert)

    async def _send_grouped_alerts(self, group_id: str):
        """Send grouped alerts after delay"""
        # Wait for more alerts
        await asyncio.sleep(30)  # 30 second grouping window
        
        if group_id in self.alert_groups:
            alerts = self.alert_groups[group_id]
            
            if alerts:
                # Create summary alert
                summary = await self._create_group_summary(alerts)
                await self.send_alert(summary)
                
                # Clear group
                del self.alert_groups[group_id]
                del self.group_timers[group_id]

    async def _create_group_summary(self, alerts: List[Alert]) -> Alert:
        """Create summary alert for grouped alerts"""
        # Determine highest priority
        max_priority = max(alert.priority for alert in alerts)
        
        # Create summary
        summary_title = f"Alert Summary ({len(alerts)} alerts)"
        
        # Group by type
        by_type = defaultdict(list)
        for alert in alerts:
            by_type[alert.alert_type].append(alert)
        
        # Build message
        message_parts = []
        for alert_type, type_alerts in by_type.items():
            message_parts.append(
                f"{alert_type.value}: {len(type_alerts)} alerts"
            )
        
        summary_message = "\n".join(message_parts)
        
        # Create summary alert
        return Alert(
            alert_id=self._generate_alert_id(),
            alert_type=AlertType.SYSTEM_ERROR,  # Generic type
            priority=max_priority,
            title=summary_title,
            message=summary_message,
            details={'grouped_alerts': [a.alert_id for a in alerts]},
            timestamp=datetime.now(),
            source="Alert Grouping"
        )

    async def _process_alert_queue(self):
        """Process queued alerts"""
        while self.state == AgentState.RUNNING:
            try:
                # Process any pending retries
                for delivery in self.delivery_history:
                    if delivery.status == 'failed' and delivery.retry_count < 3:
                        # Retry after delay
                        if delivery.sent_at:
                            retry_delay = timedelta(minutes=5 * (delivery.retry_count + 1))
                            if datetime.now() - delivery.sent_at > retry_delay:
                                # Find original alert
                                if delivery.alert_id in self.active_alerts:
                                    alert = self.active_alerts[delivery.alert_id]
                                    
                                    # Retry delivery
                                    delivery.retry_count += 1
                                    success = await self._send_through_channel(
                                        alert,
                                        delivery.channel,
                                        delivery.recipient,
                                        delivery
                                    )
                                    
                                    if success:
                                        delivery.status = 'sent'
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error processing alert queue: {str(e)}")

    async def _send_scheduled_alerts(self):
        """Send scheduled alerts"""
        while self.state == AgentState.RUNNING:
            try:
                now = datetime.now()
                
                # Market open alert
                if now.hour == 9 and now.minute == 30 and now.second < 5:
                    await self.create_alert(
                        AlertType.MARKET_OPEN,
                        "Market Open",
                        "SPY options market is now open for trading",
                        priority=AlertPriority.LOW
                    )
                
                # Market close alert
                if now.hour == 16 and now.minute == 0 and now.second < 5:
                    await self.create_alert(
                        AlertType.MARKET_CLOSE,
                        "Market Close",
                        "SPY options market has closed",
                        priority=AlertPriority.LOW
                    )
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error sending scheduled alerts: {str(e)}")

    async def _analyze_alert_patterns(self):
        """Analyze alert patterns for insights"""
        while self.state == AgentState.RUNNING:
            try:
                # Analyze recent alerts
                recent_alerts = list(self.alert_history)[-1000:]
                
                if len(recent_alerts) > 100:
                    # Find patterns
                    patterns = await self._find_alert_patterns(recent_alerts)
                    
                    # Generate insights
                    for pattern_name, pattern_alerts in patterns.items():
                        insight = await self._generate_pattern_insight(
                            pattern_name, pattern_alerts
                        )
                        self.pattern_insights[pattern_name] = insight
                
                await asyncio.sleep(3600)  # Analyze hourly
                
            except Exception as e:
                self.logger.error(f"Error analyzing patterns: {str(e)}")

    async def _find_alert_patterns(
        self,
        alerts: List[Alert]
    ) -> Dict[str, List[Alert]]:
        """Find patterns in alerts"""
        patterns = {}
        
        # Time-based patterns
        by_hour = defaultdict(list)
        for alert in alerts:
            by_hour[alert.timestamp.hour].append(alert)
        
        # Find peak hours
        peak_hours = sorted(by_hour.items(), key=lambda x: len(x[1]), reverse=True)[:3]
        if peak_hours:
            patterns['peak_hours'] = [alert for hour, alerts in peak_hours for alert in alerts]
        
        # Type sequences
        type_sequences = []
        for i in range(len(alerts) - 2):
            sequence = [
                alerts[i].alert_type,
                alerts[i+1].alert_type,
                alerts[i+2].alert_type
            ]
            type_sequences.append(sequence)
        
        # Find common sequences
        from collections import Counter
        sequence_counts = Counter(tuple(s) for s in type_sequences)
        
        if sequence_counts:
            most_common = sequence_counts.most_common(1)[0]
            if most_common[1] > 5:  # At least 5 occurrences
                patterns['common_sequence'] = [
                    alert for alert in alerts
                    if alert.alert_type in most_common[0]
                ]
        
        return patterns

    async def _generate_pattern_insight(
        self,
        pattern_name: str,
        pattern_alerts: List[Alert]
    ) -> str:
        """Generate insight from alert pattern"""
        prompt = f"""
        Analyze this alert pattern and provide insight:
        
        Pattern: {pattern_name}
        Number of alerts: {len(pattern_alerts)}
        Alert types: {[a.alert_type.value for a in pattern_alerts[:10]]}
        
        Provide a brief insight about what this pattern might indicate
        and any recommendations for the trader.
        """
        
        try:
            insight = await asyncio.wait_for(self._query_llm(prompt), timeout=3.0)
            return insight
        except:
            return f"Pattern detected: {pattern_name} with {len(pattern_alerts)} alerts"

    async def _cleanup_expired_alerts(self):
        """Clean up expired alerts"""
        while self.state == AgentState.RUNNING:
            try:
                now = datetime.now()
                
                # Remove expired alerts
                expired_ids = []
                for alert_id, alert in self.active_alerts.items():
                    if alert.expires_at and alert.expires_at < now:
                        expired_ids.append(alert_id)
                
                for alert_id in expired_ids:
                    del self.active_alerts[alert_id]
                
                if expired_ids:
                    self.logger.info(f"Cleaned up {len(expired_ids)} expired alerts")
                
                await asyncio.sleep(3600)  # Clean hourly
                
            except Exception as e:
                self.logger.error(f"Error cleaning expired alerts: {str(e)}")

    async def _load_alert_rules(self):
        """Load alert rules from storage"""
        # Would load from database/file
        # Default rules
        self.alert_rules['high_drawdown'] = AlertRule(
            rule_id='high_drawdown',
            name='High Drawdown Alert',
            conditions={
                'alert_type': ['drawdown_warning'],
                'details': {'drawdown': {'gte': 0.05}}
            },
            actions={'modify_priority': AlertPriority.CRITICAL.value},
            channels=[DeliveryChannel.SMS, DeliveryChannel.EMAIL]
        )

    async def _load_recipient_preferences(self):
        """Load recipient preferences from storage"""
        # Would load from database/file
        pass

    async def _save_rule(self, rule: AlertRule):
        """Save alert rule to storage"""
        # Would save to database/file
        pass

    async def _save_preferences(self, recipient: str, preferences: Dict[str, Any]):
        """Save recipient preferences to storage"""
        # Would save to database/file
        pass

    def _validate_rule(self, rule: AlertRule) -> bool:
        """Validate alert rule"""
        # Check required fields
        if not rule.name or not rule.conditions:
            return False
        
        # Validate conditions structure
        # (simplified validation)
        
        return True

    async def _handle_trade_event(self, event: Event):
        """Handle trade-related events"""
        if hasattr(event, 'data'):
            trade = event.data.get('trade')
            if trade:
                await self.create_alert(
                    AlertType.TRADE_EXECUTED,
                    f"Trade Executed: {trade.symbol}",
                    f"{trade.side} {trade.quantity} contracts at ${trade.price:.2f}",
                    details={
                        'symbol': trade.symbol,
                        'side': trade.side,
                        'quantity': trade.quantity,
                        'price': trade.price,
                        'pnl': getattr(trade, 'pnl', 0)
                    },
                    tags=['trade', trade.symbol]
                )

    async def _handle_order_event(self, event: Event):
        """Handle order-related events"""
        if hasattr(event, 'data'):
            order = event.data.get('order')
            if order:
                if event.event_type == EventType.ORDER_FILLED:
                    await self.create_alert(
                        AlertType.ORDER_FILLED,
                        f"Order Filled: {order.symbol}",
                        f"Order {order.order_id} filled at ${order.fill_price:.2f}",
                        priority=AlertPriority.MEDIUM,
                        details={'order': order}
                    )
                elif event.event_type == EventType.ORDER_REJECTED:
                    await self.create_alert(
                        AlertType.ORDER_REJECTED,
                        f"Order Rejected: {order.symbol}",
                        f"Order {order.order_id} rejected: {order.reject_reason}",
                        priority=AlertPriority.HIGH,
                        details={'order': order}
                    )

    async def _handle_risk_event(self, event: Event):
        """Handle risk-related events"""
        if hasattr(event, 'data'):
            if event.event_type == EventType.RISK_ALERT:
                risk_type = event.data.get('risk_type')
                if risk_type == 'position_limit':
                    await self.create_alert(
                        AlertType.RISK_LIMIT_WARNING,
                        "Position Limit Warning",
                        event.data.get('message', 'Position approaching limit'),
                        priority=AlertPriority.HIGH,
                        details=event.data
                    )
            elif event.event_type == EventType.DRAWDOWN_ALERT:
                drawdown = event.data.get('drawdown', 0)
                await self.create_alert(
                    AlertType.DRAWDOWN_WARNING,
                    f"Drawdown Alert: {abs(drawdown):.1%}",
                    f"Portfolio drawdown has reached {abs(drawdown):.1%}",
                    priority=AlertPriority.HIGH if abs(drawdown) > 0.05 else AlertPriority.MEDIUM,
                    details={'drawdown': drawdown}
                )

    async def _handle_market_event(self, event: Event):
        """Handle market-related events"""
        if event.event_type == EventType.VOLATILITY_SPIKE:
            if hasattr(event, 'data'):
                vix = event.data.get('vix', 0)
                if vix > 30:
                    await self.create_alert(
                        AlertType.MARKET_VOLATILITY,
                        "High Volatility Alert",
                        f"VIX has spiked to {vix:.1f}",
                        priority=AlertPriority.HIGH,
                        details={'vix': vix}
                    )

    async def _handle_performance_event(self, event: Event):
        """Handle performance-related events"""
        if hasattr(event, 'data'):
            if event.event_type == EventType.DAILY_PNL_UPDATE:
                pnl = event.data.get('daily_pnl', 0)
                await self.create_alert(
                    AlertType.DAILY_PNL,
                    f"Daily P&L: ${pnl:,.2f}",
                    f"Today's profit/loss: ${pnl:,.2f}",
                    priority=AlertPriority.LOW,
                    details={'pnl': pnl},
                    dedupe_key='daily_pnl'
                )

    async def _handle_report_event(self, event: Event):
        """Handle report-related events"""
        if hasattr(event, 'data'):
            report = event.data.get('report')
            if report:
                await self.create_alert(
                    AlertType.REPORT_READY,
                    f"{report.report_type.value.title()} Report Ready",
                    "Your performance report is ready for review",
                    priority=AlertPriority.LOW,
                    details={'report_type': report.report_type.value}
                )

    async def _handle_system_event(self, event: Event):
        """Handle system-related events"""
        if event.event_type == EventType.SYSTEM_ERROR:
            if hasattr(event, 'data'):
                error = event.data.get('error', 'Unknown error')
                await self.create_alert(
                    AlertType.SYSTEM_ERROR,
                    "System Error",
                    f"System error occurred: {error}",
                    priority=AlertPriority.CRITICAL,
                    details=event.data
                )

    async def _query_llm(self, prompt: str) -> str:
        """Query LLM for alert enhancements"""
        # Mock implementation
        if "enhance this trading alert" in prompt:
            return json.dumps({
                "enhanced_message": "Trade executed successfully with favorable pricing. Position aligns with current market conditions.",
                "implications": "This trade increases your portfolio exposure to upside SPY movement",
                "actions": ["Monitor position closely", "Consider setting stop loss at -2%"]
            })
        else:
            return "Alert pattern indicates increased trading activity during volatile periods"

    async def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        stats = {
            'active_alerts': len(self.active_alerts),
            'total_sent_24h': 0,
            'by_priority_24h': defaultdict(int),
            'by_channel_24h': defaultdict(int),
            'delivery_success_rate': 0,
            'average_delivery_time': 0,
            'top_alert_types': [],
            'pattern_insights': self.pattern_insights
        }
        
        # Calculate 24h stats
        cutoff = datetime.now() - timedelta(hours=24)
        recent_alerts = [a for a in self.alert_history if a.timestamp > cutoff]
        stats['total_sent_24h'] = len(recent_alerts)
        
        # By priority
        for alert in recent_alerts:
            stats['by_priority_24h'][alert.priority.value] += 1
        
        # Delivery stats
        recent_deliveries = [d for d in self.delivery_history 
                           if d.sent_at and d.sent_at > cutoff]
        
        if recent_deliveries:
            success_count = len([d for d in recent_deliveries if d.status == 'sent'])
            stats['delivery_success_rate'] = success_count / len(recent_deliveries)
            
            # Average delivery time
            delivery_times = []
            for d in recent_deliveries:
                if d.delivered_at and d.sent_at:
                    delivery_times.append((d.delivered_at - d.sent_at).seconds)
            
            if delivery_times:
                stats['average_delivery_time'] = np.mean(delivery_times)
        
        # By channel
        for delivery in recent_deliveries:
            stats['by_channel_24h'][delivery.channel.value] += 1
        
        # Top alert types
        type_counts = defaultdict(int)
        for alert in recent_alerts:
            type_counts[alert.alert_type.value] += 1
        
        stats['top_alert_types'] = sorted(
            type_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return stats

    async def shutdown(self):
        """Shutdown agent gracefully"""
        self.state = AgentState.STOPPED
        
        # Cancel group timers
        for timer in self.group_timers.values():
            timer.cancel()
        
        # Send any pending grouped alerts
        for group_id, alerts in self.alert_groups.items():
            if alerts:
                summary = await self._create_group_summary(alerts)
                await self.send_alert(summary)
        
        self.logger.info("Alert Manager Agent shutdown complete")


# Channel Implementations

class EmailChannel(AlertChannel):
    """Email delivery channel"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        # Would initialize SMTP connection
    
    async def send(self, alert: Alert, recipient: str) -> bool:
        """Send alert via email"""
        # Mock implementation
        return True
    
    async def validate_recipient(self, recipient: str) -> bool:
        """Validate email address"""
        import re
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        return bool(re.match(pattern, recipient))


class SMSChannel(AlertChannel):
    """SMS delivery channel"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        # Would initialize Twilio client
    
    async def send(self, alert: Alert, recipient: str) -> bool:
        """Send alert via SMS"""
        # Mock implementation
        return True
    
    async def validate_recipient(self, recipient: str) -> bool:
        """Validate phone number"""
        import re
        pattern = r'^\+?1?\d{10,15}$'
        return bool(re.match(pattern, recipient))


class DiscordChannel(AlertChannel):
    """Discord delivery channel"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.webhook_url = config.get('discord_webhook_url')
    
    async def send(self, alert: Alert, recipient: str) -> bool:
        """Send alert to Discord"""
        # Mock implementation
        return True
    
    async def validate_recipient(self, recipient: str) -> bool:
        """Validate Discord webhook URL"""
        return recipient.startswith('https://discord.com/api/webhooks/')


class SlackChannel(AlertChannel):
    """Slack delivery channel"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.webhook_url = config.get('slack_webhook_url')
    
    async def send(self, alert: Alert, recipient: str) -> bool:
        """Send alert to Slack"""
        # Mock implementation
        return True
    
    async def validate_recipient(self, recipient: str) -> bool:
        """Validate Slack webhook URL"""
        return recipient.startswith('https://hooks.slack.com/')


class DesktopChannel(AlertChannel):
    """Desktop notification channel"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    async def send(self, alert: Alert, recipient: str) -> bool:
        """Send desktop notification"""
        # Mock implementation
        return True
    
    async def validate_recipient(self, recipient: str) -> bool:
        """Desktop notifications always valid"""
        return True


class LogChannel(AlertChannel):
    """Log file channel"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = SpyderLogger("AlertLog")
    
    async def send(self, alert: Alert, recipient: str) -> bool:
        """Log alert"""
        self.logger.info(
            f"[{alert.priority.name}] {alert.alert_type.value}: "
            f"{alert.title} - {alert.message}"
        )
        return True
    
    async def validate_recipient(self, recipient: str) -> bool:
        """Log channel always valid"""
        return True


# Factory function
def create_alert_manager_agent(config: Dict[str, Any]) -> AlertManagerAgent:
    """Create and return an Alert Manager Agent instance"""
    return AlertManagerAgent(config)


# Usage Example:
if __name__ == "__main__":
    # Example configuration
    test_config = {
        'alert_llm_model': 'llama3.2:3b-instruct-q4_K_M',
        'alert_cooldown_minutes': 5,
        'max_alerts_per_hour': 50,
        'alert_email_recipients': ['trader@example.com'],
        'alert_sms_recipients': ['+1234567890'],
        'discord_webhook_url': 'https://discord.com/api/webhooks/...',
        'slack_webhook_url': 'https://hooks.slack.com/...'
    }
    
    # Create agent
    alert_agent = create_alert_manager_agent(test_config)
    
    # Example usage
    async def example_usage():
        await alert_agent.initialize()
        
        # Create various alerts
        await alert_agent.create_alert(
            AlertType.TRADE_EXECUTED,
            "Iron Condor Opened",
            "Sold 405/410/420/425 Iron Condor for $2.50 credit",
            details={
                'strategy': 'iron_condor',
                'credit': 250,
                'max_loss': 250
            }
        )
        
        await alert_agent.create_alert(
            AlertType.RISK_LIMIT_WARNING,
            "Approaching Daily Loss Limit",
            "Current loss: $450, Daily limit: $500",
            priority=AlertPriority.HIGH,
            details={
                'current_loss': 450,
                'limit': 500,
                'percentage': 90
            }
        )
        
        # Get alert summary
        summary = await alert_agent.get_alert_summary(hours=24)
        print(f"Alerts in last 24h: {summary.total_alerts}")
        print(f"By priority: {summary.by_priority}")
        
        # Create custom rule
        rule = await alert_agent.create_alert_rule(
            name="High Loss Alert",
            conditions={
                'alert_type': ['trade_executed'],
                'details': {'pnl': {'lte': -100}}
            },
            actions={
                'modify_priority': AlertPriority.HIGH.value,
                'add_tags': ['high_loss']
            },
            channels=[DeliveryChannel.SMS, DeliveryChannel.EMAIL]
        )
        
        print(f"Created rule: {rule.name}")
    
    # Run example
    # asyncio.run(example_usage())