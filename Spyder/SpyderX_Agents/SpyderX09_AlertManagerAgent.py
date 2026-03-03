#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Agents
Module: SpyderX09_AlertManagerAgent.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import re

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.info("Warning: Ollama not installed. AI features will be limited.")

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Alert types
class AlertType(Enum):
    """Alert type enumeration."""
    PRICE = "PRICE"
    VOLUME = "VOLUME"
    VOLATILITY = "VOLATILITY"
    RISK = "RISK"
    OPPORTUNITY = "OPPORTUNITY"
    SYSTEM = "SYSTEM"
    PERFORMANCE = "PERFORMANCE"
    MARKET_REGIME = "MARKET_REGIME"
    EXECUTION = "EXECUTION"
    CUSTOM = "CUSTOM"

# Alert severity levels
class AlertSeverity(Enum):
    """Alert severity enumeration."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

# Alert delivery channels
class DeliveryChannel(Enum):
    """Delivery channel enumeration."""
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    WEBHOOK = "WEBHOOK"
    LOG = "LOG"
    UI = "UI"

# Alert conditions
ALERT_CONDITIONS = {
    'price_breakout': 'Price breaks above/below threshold',
    'volume_spike': 'Volume exceeds normal range',
    'volatility_change': 'Volatility regime change',
    'drawdown_limit': 'Drawdown exceeds threshold',
    'win_streak': 'Consecutive winning trades',
    'loss_streak': 'Consecutive losing trades',
    'correlation_break': 'Correlation pattern breaks',
    'system_error': 'System error or failure',
    'opportunity_detected': 'High probability trade setup'
}

# Default configuration
DEFAULT_CONFIG = {
    'max_alerts_per_hour': 20,
    'alert_cooldown_minutes': 5,
    'critical_always_send': True,
    'aggregate_similar_alerts': True,
    'ai_enhancement_enabled': True,
    'delivery_retry_attempts': 3
}

# Model configuration
DEFAULT_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_TEMPERATURE = 0.3

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class AlertCondition:
    """Alert condition data structure."""
    name: str
    type: AlertType
    expression: str  # Condition expression
    threshold: Optional[float] = None
    comparison: str = ">"  # >, <, ==, !=, >=, <=
    cooldown_minutes: int = 5
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Alert:
    """Alert data structure."""
    id: str
    timestamp: datetime
    type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    data: Dict[str, Any]
    source: str
    condition_name: Optional[str] = None
    ai_enhanced: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AlertDelivery:
    """Alert delivery data structure."""
    alert_id: str
    channel: DeliveryChannel
    recipient: str
    status: str  # 'pending', 'sent', 'failed'
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    error_message: Optional[str] = None

@dataclass
class AlertAnalysis:
    """Alert analysis data structure."""
    alert_patterns: List[str]
    alert_frequency: Dict[str, int]
    severity_distribution: Dict[str, int]
    recommendations: List[str]
    noise_level: float  # 0-1, higher means more noise
    optimization_suggestions: List[str]

# ==============================================================================
# ALERT MANAGER AGENT CLASS
# ==============================================================================

class SpyderX09_AlertManagerAgent:
    """
    AI-Enhanced Alert Management Agent.
    
    This agent manages alerts intelligently using AI to prioritize, contextualize,
    and optimize alert delivery for the SPY options trading system.
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL,
                 temperature: float = DEFAULT_TEMPERATURE):
        """
        Initialize the Alert Manager Agent.
        
        Args:
            model_name: Ollama model to use
            temperature: Temperature for AI responses
        """
        self.model_name = model_name
        self.temperature = temperature
        self.logger = self._setup_logger()
        self.config = DEFAULT_CONFIG.copy()
        
        # Initialize Ollama if available
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                ollama.list()  # Test connection
                self.ollama_client = ollama
                self.logger.info("Ollama connection established")
            except Exception as e:
                self.logger.error(f"Failed to connect to Ollama: {e}")
        
        # Alert management
        self.conditions: Dict[str, AlertCondition] = {}
        self.active_alerts: List[Alert] = []
        self.alert_history = deque(maxlen=1000)
        self.delivery_queue: List[AlertDelivery] = []
        
        # Cooldown tracking
        self.last_alert_time: Dict[str, datetime] = {}
        
        # Delivery handlers
        self.delivery_handlers: Dict[DeliveryChannel, Callable] = {
            DeliveryChannel.LOG: self._deliver_to_log,
            DeliveryChannel.UI: self._deliver_to_ui
        }
        
        # Statistics
        self.alert_stats = defaultdict(lambda: {'count': 0, 'last_time': None})
        
        # Alert aggregation
        self.alert_buffer = deque(maxlen=100)
        self.aggregation_window = timedelta(minutes=1)
    
    def _setup_logger(self) -> logging.Logger:
        """Set up module logger."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    # ==========================================================================
    # ALERT MANAGEMENT METHODS
    # ==========================================================================
    
    def add_condition(self, condition: AlertCondition) -> bool:
        """
        Add an alert condition.
        
        Args:
            condition: AlertCondition to add
            
        Returns:
            True if added successfully
        """
        try:
            self.conditions[condition.name] = condition
            self.logger.info(f"Added alert condition: {condition.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add condition: {e}")
            return False
    
    async def check_conditions(self, market_data: Dict[str, Any]) -> List[Alert]:
        """
        Check all conditions and generate alerts.
        
        Args:
            market_data: Current market data
            
        Returns:
            List of generated alerts
        """
        alerts = []
        
        for name, condition in self.conditions.items():
            if not condition.enabled:
                continue
                
            # Check cooldown
            if self._is_in_cooldown(name, condition.cooldown_minutes):
                continue
            
            # Evaluate condition
            if self._evaluate_condition(condition, market_data):
                alert = await self._create_alert(condition, market_data)
                if alert:
                    alerts.append(alert)
                    self.last_alert_time[name] = datetime.now()
        
        # Process alerts with AI if enabled
        if alerts and self.config['ai_enhancement_enabled']:
            alerts = await self._enhance_alerts_with_ai(alerts, market_data)
        
        # Add to history and active alerts
        for alert in alerts:
            self.alert_history.append(alert)
            self.active_alerts.append(alert)
            self._update_stats(alert)
        
        # Manage alert queue size
        self._manage_alert_queue()
        
        return alerts
    
    async def process_custom_alert(self, title: str, message: str,
                                 severity: AlertSeverity = AlertSeverity.MEDIUM,
                                 data: Optional[Dict[str, Any]] = None) -> Alert:
        """
        Process a custom alert.
        
        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity
            data: Additional data
            
        Returns:
            Generated alert
        """
        alert = Alert(
            id=self._generate_alert_id(),
            timestamp=datetime.now(),
            type=AlertType.CUSTOM,
            severity=severity,
            title=title,
            message=message,
            data=data or {},
            source="custom",
            ai_enhanced=False
        )
        
        # Enhance with AI if enabled
        if self.config['ai_enhancement_enabled']:
            alert = await self._enhance_single_alert(alert)
        
        # Add to queues
        self.alert_history.append(alert)
        self.active_alerts.append(alert)
        self._update_stats(alert)
        
        return alert
    
    # ==========================================================================
    # ALERT DELIVERY METHODS
    # ==========================================================================
    
    async def deliver_alerts(self, alerts: List[Alert],
                           channels: Optional[List[DeliveryChannel]] = None) -> Dict[str, Any]:
        """
        Deliver alerts through specified channels.
        
        Args:
            alerts: List of alerts to deliver
            channels: Delivery channels (default: based on severity)
            
        Returns:
            Delivery summary
        """
        if not channels:
            channels = self._select_channels_by_severity(alerts)
        
        delivery_tasks = []
        
        for alert in alerts:
            for channel in channels:
                if channel in self.delivery_handlers:
                    delivery = AlertDelivery(
                        alert_id=alert.id,
                        channel=channel,
                        recipient=self._get_recipient(channel),
                        status='pending'
                    )
                    self.delivery_queue.append(delivery)
                    
                    # Create delivery task
                    task = self._deliver_alert(alert, delivery)
                    delivery_tasks.append(task)
        
        # Execute deliveries
        results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
        
        # Summarize results
        summary = {
            'total_attempts': len(delivery_tasks),
            'successful': sum(1 for r in results if r is True),
            'failed': sum(1 for r in results if r is False or isinstance(r, Exception)),
            'by_channel': defaultdict(lambda: {'success': 0, 'failed': 0})
        }
        
        for delivery, result in zip(self.delivery_queue[-len(delivery_tasks):], results):
            if result is True:
                summary['by_channel'][delivery.channel.value]['success'] += 1
            else:
                summary['by_channel'][delivery.channel.value]['failed'] += 1
        
        return summary
    
    async def _deliver_alert(self, alert: Alert, delivery: AlertDelivery) -> bool:
        """Deliver a single alert."""
        handler = self.delivery_handlers.get(delivery.channel)
        if not handler:
            self.logger.error(f"No handler for channel: {delivery.channel}")
            return False
        
        max_attempts = self.config['delivery_retry_attempts']
        
        for attempt in range(max_attempts):
            try:
                delivery.attempts = attempt + 1
                delivery.last_attempt = datetime.now()
                
                # Call delivery handler
                success = await handler(alert, delivery.recipient)
                
                if success:
                    delivery.status = 'sent'
                    return True
                
            except Exception as e:
                delivery.error_message = str(e)
                self.logger.error(f"Delivery failed: {e}")
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        delivery.status = 'failed'
        return False
    
    # ==========================================================================
    # AI INTEGRATION METHODS
    # ==========================================================================
    
    async def _enhance_alerts_with_ai(self, alerts: List[Alert],
                                    market_data: Dict[str, Any]) -> List[Alert]:
        """Enhance multiple alerts with AI context."""
        if not self.ollama_client or not alerts:
            return alerts
        
        # Group similar alerts for context
        alert_groups = self._group_similar_alerts(alerts)
        enhanced_alerts = []
        
        for group in alert_groups:
            if len(group) > 1:
                # Enhance as a group
                enhanced = await self._enhance_alert_group(group, market_data)
                enhanced_alerts.extend(enhanced)
            else:
                # Enhance individually
                enhanced = await self._enhance_single_alert(group[0], market_data)
                enhanced_alerts.append(enhanced)
        
        return enhanced_alerts
    
    async def _enhance_single_alert(self, alert: Alert,
                                  market_data: Optional[Dict[str, Any]] = None) -> Alert:
        """Enhance a single alert with AI."""
        if not self.ollama_client:
            return alert
        
        prompt = f"""Enhance this trading alert with context and actionable insights:

Alert Details:
- Type: {alert.type.value}
- Severity: {alert.severity.value}
- Title: {alert.title}
- Message: {alert.message}
- Data: {json.dumps(alert.data, indent=2)}

{f"Market Context: {json.dumps(market_data, indent=2)}" if market_data else ""}

Recent Alert History: {self._get_recent_alert_summary()}

Provide a JSON response with:
{{
    "enhanced_message": "more detailed and actionable message",
    "context": "relevant market context",
    "action_items": ["specific action 1", "specific action 2"],
    "related_risks": ["risk 1", "risk 2"],
    "priority_adjustment": "INCREASE/MAINTAIN/DECREASE",
    "confidence": 0.0-1.0
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                enhancement = json.loads(text[start:end])
                
                # Apply enhancements
                alert.message = enhancement.get('enhanced_message', alert.message)
                alert.metadata['ai_context'] = enhancement.get('context', '')
                alert.metadata['action_items'] = enhancement.get('action_items', [])
                alert.metadata['related_risks'] = enhancement.get('related_risks', [])
                alert.ai_enhanced = True
                
                # Adjust severity if recommended
                if enhancement.get('priority_adjustment') == 'INCREASE':
                    alert.severity = self._increase_severity(alert.severity)
                elif enhancement.get('priority_adjustment') == 'DECREASE':
                    alert.severity = self._decrease_severity(alert.severity)
                
                return alert
            else:
                return alert
                
        except Exception as e:
            self.logger.error(f"AI alert enhancement failed: {e}")
            return alert
    
    async def _enhance_alert_group(self, alerts: List[Alert],
                                 market_data: Dict[str, Any]) -> List[Alert]:
        """Enhance a group of related alerts."""
        if not self.ollama_client:
            return alerts
        
        # Create summary of alert group
        alert_summary = {
            'count': len(alerts),
            'types': list(set(a.type.value for a in alerts)),
            'severities': list(set(a.severity.value for a in alerts)),
            'titles': [a.title for a in alerts]
        }
        
        prompt = f"""Analyze this group of related trading alerts and provide insights:

Alert Group Summary:
{json.dumps(alert_summary, indent=2)}

Market Context:
{json.dumps(market_data, indent=2)}

Provide a JSON response with:
{{
    "group_interpretation": "what these alerts together indicate",
    "combined_severity": "CRITICAL/HIGH/MEDIUM/LOW",
    "recommended_action": "primary action to take",
    "risk_assessment": "overall risk from these alerts",
    "should_aggregate": true/false,
    "aggregated_message": "combined message if should_aggregate is true"
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                group_analysis = json.loads(text[start:end])
                
                if group_analysis.get('should_aggregate', False):
                    # Create a single aggregated alert
                    aggregated = Alert(
                        id=self._generate_alert_id(),
                        timestamp=datetime.now(),
                        type=alerts[0].type,
                        severity=self._parse_severity(
                            group_analysis.get('combined_severity', 'MEDIUM')
                        ),
                        title=f"Multiple Related Alerts ({len(alerts)})",
                        message=group_analysis.get('aggregated_message', ''),
                        data={
                            'alert_count': len(alerts),
                            'alert_ids': [a.id for a in alerts],
                            'group_interpretation': group_analysis.get('group_interpretation', ''),
                            'risk_assessment': group_analysis.get('risk_assessment', '')
                        },
                        source='aggregation',
                        ai_enhanced=True
                    )
                    return [aggregated]
                else:
                    # Enhance each alert with group context
                    for alert in alerts:
                        alert.metadata['group_context'] = group_analysis.get('group_interpretation', '')
                        alert.metadata['group_action'] = group_analysis.get('recommended_action', '')
                        alert.ai_enhanced = True
                    return alerts
            else:
                return alerts
                
        except Exception as e:
            self.logger.error(f"AI alert group enhancement failed: {e}")
            return alerts
    
    async def analyze_alert_patterns(self) -> AlertAnalysis:
        """Analyze alert patterns using AI."""
        recent_alerts = list(self.alert_history)[-100:]  # Last 100 alerts
        
        if not recent_alerts:
            return AlertAnalysis(
                alert_patterns=[],
                alert_frequency={},
                severity_distribution={},
                recommendations=["No alerts to analyze"],
                noise_level=0.0,
                optimization_suggestions=[]
            )
        
        # Calculate basic statistics
        alert_frequency = defaultdict(int)
        severity_distribution = defaultdict(int)
        
        for alert in recent_alerts:
            alert_frequency[alert.type.value] += 1
            severity_distribution[alert.severity.value] += 1
        
        # Get AI analysis
        ai_patterns = await self._get_ai_alert_patterns(recent_alerts)
        
        # Calculate noise level
        noise_level = self._calculate_noise_level(recent_alerts)
        
        # Generate recommendations
        recommendations = self._generate_alert_recommendations(
            alert_frequency, severity_distribution, noise_level, ai_patterns
        )
        
        return AlertAnalysis(
            alert_patterns=ai_patterns.get('patterns', []),
            alert_frequency=dict(alert_frequency),
            severity_distribution=dict(severity_distribution),
            recommendations=recommendations,
            noise_level=noise_level,
            optimization_suggestions=ai_patterns.get('optimizations', [])
        )
    
    async def _get_ai_alert_patterns(self, alerts: List[Alert]) -> Dict[str, Any]:
        """Get AI analysis of alert patterns."""
        if not self.ollama_client:
            return False
    
    # ==========================================================================
    # CONDITION EVALUATION METHODS
    # ==========================================================================
    
    def _evaluate_condition(self, condition: AlertCondition,
                          market_data: Dict[str, Any]) -> bool:
        """Evaluate an alert condition."""
        try:
            # Extract value from market data using condition expression
            # Simple implementation - in production, use safe expression evaluation
            value = self._extract_value(condition.expression, market_data)
            
            if value is None or condition.threshold is None:
                return False
            
            # Compare based on operator
            comparisons = {
                '>': lambda x, y: x > y,
                '<': lambda x, y: x < y,
                '>=': lambda x, y: x >= y,
                '<=': lambda x, y: x <= y,
                '==': lambda x, y: x == y,
                '!=': lambda x, y: x != y
            }
            
            comparison_func = comparisons.get(condition.comparison)
            if comparison_func:
                return comparison_func(value, condition.threshold)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Condition evaluation failed: {e}")
            return False
    
    def _extract_value(self, expression: str, data: Dict[str, Any]) -> Optional[float]:
        """Extract value from data using expression."""
        # Simple dot notation support (e.g., "price.current", "volume.avg")
        parts = expression.split('.')
        value = data
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        
        # Convert to float if possible
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    
    async def _create_alert(self, condition: AlertCondition,
                          market_data: Dict[str, Any]) -> Optional[Alert]:
        """Create an alert from a triggered condition."""
        try:
            # Extract relevant data
            value = self._extract_value(condition.expression, market_data)
            
            # Determine severity based on condition type and value
            severity = self._determine_severity(condition, value)
            
            # Create alert message
            message = self._format_alert_message(condition, value, market_data)
            
            alert = Alert(
                id=self._generate_alert_id(),
                timestamp=datetime.now(),
                type=condition.type,
                severity=severity,
                title=f"{condition.type.value} Alert: {condition.name}",
                message=message,
                data={
                    'condition': condition.name,
                    'expression': condition.expression,
                    'threshold': condition.threshold,
                    'actual_value': value,
                    'market_data': market_data
                },
                source='condition',
                condition_name=condition.name
            )
            
            return alert
            
        except Exception as e:
            self.logger.error(f"Alert creation failed: {e}")
            return None
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _is_in_cooldown(self, condition_name: str, cooldown_minutes: int) -> bool:
        """Check if condition is in cooldown period."""
        if condition_name not in self.last_alert_time:
            return False
        
        time_since_last = datetime.now() - self.last_alert_time[condition_name]
        return time_since_last < timedelta(minutes=cooldown_minutes)
    
    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        return f"ALERT_{timestamp}"
    
    def _determine_severity(self, condition: AlertCondition,
                          value: Optional[float]) -> AlertSeverity:
        """Determine alert severity based on condition and value."""
        # Risk alerts are typically high severity
        if condition.type == AlertType.RISK:
            if value and condition.threshold:
                deviation = abs(value - condition.threshold) / condition.threshold
                if deviation > 0.5:
                    return AlertSeverity.CRITICAL
                elif deviation > 0.2:
                    return AlertSeverity.HIGH
            return AlertSeverity.HIGH
        
        # System alerts
        elif condition.type == AlertType.SYSTEM:
            return AlertSeverity.CRITICAL
        
        # Opportunity alerts
        elif condition.type == AlertType.OPPORTUNITY:
            return AlertSeverity.MEDIUM
        
        # Default based on metadata
        return AlertSeverity(condition.metadata.get('severity', 'MEDIUM'))
    
    def _format_alert_message(self, condition: AlertCondition,
                            value: Optional[float],
                            market_data: Dict[str, Any]) -> str:
        """Format alert message."""
        if value is not None and condition.threshold is not None:
            change_pct = ((value - condition.threshold) / condition.threshold) * 100
            return (f"{condition.expression} is {value:.2f} "
                   f"({change_pct:+.1f}% from threshold {condition.threshold:.2f})")
        else:
            return f"{condition.name} condition triggered"
    
    def _select_channels_by_severity(self, alerts: List[Alert]) -> List[DeliveryChannel]:
        """Select delivery channels based on alert severity."""
        channels = [DeliveryChannel.LOG]  # Always log
        
        # Get highest severity
        if not alerts:
            return channels
        
        highest_severity = min(alerts, key=lambda a: 
                             ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'].index(a.severity.value))
        
        if highest_severity.severity == AlertSeverity.CRITICAL:
            channels.extend([DeliveryChannel.EMAIL, DeliveryChannel.SMS, DeliveryChannel.UI])
        elif highest_severity.severity == AlertSeverity.HIGH:
            channels.extend([DeliveryChannel.EMAIL, DeliveryChannel.UI])
        elif highest_severity.severity == AlertSeverity.MEDIUM:
            channels.append(DeliveryChannel.UI)
        
        return list(set(channels))  # Remove duplicates
    
    def _get_recipient(self, channel: DeliveryChannel) -> str:
        """Get recipient for delivery channel."""
        # In production, this would come from configuration
        recipients = {
            DeliveryChannel.EMAIL: "trader@example.com",
            DeliveryChannel.SMS: "+1234567890",
            DeliveryChannel.PUSH: "user_device_token",
            DeliveryChannel.WEBHOOK: "https://api.example.com/alerts",
            DeliveryChannel.LOG: "system",
            DeliveryChannel.UI: "dashboard"
        }
        return recipients.get(channel, "unknown")
    
    async def _deliver_to_log(self, alert: Alert, recipient: str) -> bool:
        """Deliver alert to log."""
        self.logger.info(f"ALERT [{alert.severity.value}]: {alert.title} - {alert.message}")
        return True
    
    async def _deliver_to_ui(self, alert: Alert, recipient: str) -> bool:
        """Deliver alert to UI (placeholder)."""
        # In production, this would send to UI via websocket or message queue
        self.logger.info(f"UI Alert: {alert.title}")
        return True
    
    def _group_similar_alerts(self, alerts: List[Alert]) -> List[List[Alert]]:
        """Group similar alerts for batch processing."""
        if not self.config['aggregate_similar_alerts']:
            return [[alert] for alert in alerts]
        
        groups = []
        grouped_ids = set()
        
        for i, alert1 in enumerate(alerts):
            if alert1.id in grouped_ids:
                continue
                
            group = [alert1]
            grouped_ids.add(alert1.id)
            
            for j, alert2 in enumerate(alerts[i+1:], i+1):
                if alert2.id in grouped_ids:
                    continue
                    
                if self._are_similar_alerts(alert1, alert2):
                    group.append(alert2)
                    grouped_ids.add(alert2.id)
            
            groups.append(group)
        
        return groups
    
    def _are_similar_alerts(self, alert1: Alert, alert2: Alert) -> bool:
        """Check if two alerts are similar enough to group."""
        # Same type and similar severity
        if alert1.type != alert2.type:
            return False
        
        # Within aggregation window
        time_diff = abs((alert1.timestamp - alert2.timestamp).total_seconds())
        if time_diff > self.aggregation_window.total_seconds():
            return False
        
        # Similar severity (within one level)
        severity_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
        sev1_idx = severity_order.index(alert1.severity.value)
        sev2_idx = severity_order.index(alert2.severity.value)
        
        return abs(sev1_idx - sev2_idx) <= 1
    
    def _update_stats(self, alert: Alert):
        """Update alert statistics."""
        key = f"{alert.type.value}_{alert.severity.value}"
        self.alert_stats[key]['count'] += 1
        self.alert_stats[key]['last_time'] = alert.timestamp
    
    def _manage_alert_queue(self):
        """Manage alert queue size and remove old alerts."""
        # Remove alerts older than 24 hours
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.active_alerts = [a for a in self.active_alerts 
                            if a.timestamp > cutoff_time]
        
        # Check rate limiting
        recent_count = sum(1 for a in self.active_alerts 
                         if a.timestamp > datetime.now() - timedelta(hours=1))
        
        if recent_count > self.config['max_alerts_per_hour']:
            self.logger.warning(f"Alert rate limit reached: {recent_count} alerts/hour")
    
    def _get_recent_alert_summary(self) -> str:
        """Get summary of recent alerts for AI context."""
        recent = list(self.alert_history)[-10:]
        if not recent:
            return "No recent alerts"
        
        summary_lines = []
        for alert in recent:
            time_ago = (datetime.now() - alert.timestamp).total_seconds() / 60
            summary_lines.append(
                f"- {alert.type.value} ({alert.severity.value}): "
                f"{alert.title} ({time_ago:.0f}m ago)"
            )
        
        return "\n".join(summary_lines)
    
    def _increase_severity(self, severity: AlertSeverity) -> AlertSeverity:
        """Increase alert severity by one level."""
        severity_order = ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        current_idx = severity_order.index(severity.value)
        new_idx = min(current_idx + 1, len(severity_order) - 1)
        return AlertSeverity(severity_order[new_idx])
    
    def _decrease_severity(self, severity: AlertSeverity) -> AlertSeverity:
        """Decrease alert severity by one level."""
        severity_order = ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        current_idx = severity_order.index(severity.value)
        new_idx = max(current_idx - 1, 0)
        return AlertSeverity(severity_order[new_idx])
    
    def _parse_severity(self, severity_str: str) -> AlertSeverity:
        """Parse severity string to enum."""
        try:
            return AlertSeverity(severity_str.upper())
        except:
            return AlertSeverity.MEDIUM
    
    def _count_by_attribute(self, alerts: List[Alert], attribute: str) -> Dict[str, int]:
        """Count alerts by attribute."""
        counts = defaultdict(int)
        for alert in alerts:
            value = getattr(alert, attribute)
            if hasattr(value, 'value'):  # Enum
                value = value.value
            counts[str(value)] += 1
        return dict(counts)
    
    def _get_hourly_distribution(self, alerts: List[Alert]) -> Dict[int, int]:
        """Get hourly distribution of alerts."""
        hourly_counts = defaultdict(int)
        for alert in alerts:
            hour = alert.timestamp.hour
            hourly_counts[hour] += 1
        return dict(hourly_counts)
    
    def _format_alert_samples(self, alerts: List[Alert]) -> str:
        """Format alert samples for AI prompt."""
        samples = []
        for alert in alerts[:5]:  # First 5 alerts
            samples.append({
                'type': alert.type.value,
                'severity': alert.severity.value,
                'title': alert.title,
                'time': alert.timestamp.isoformat()
            })
        return json.dumps(samples, indent=2)
    
    def _calculate_noise_level(self, alerts: List[Alert]) -> float:
        """Calculate alert noise level (0-1)."""
        if not alerts:
            return 0.0
        
        # Factors that contribute to noise
        noise_factors = []
        
        # Factor 1: High frequency of low-severity alerts
        low_severity_ratio = sum(1 for a in alerts 
                               if a.severity in [AlertSeverity.LOW, AlertSeverity.INFO]) / len(alerts)
        noise_factors.append(low_severity_ratio * 0.4)
        
        # Factor 2: Repeated similar alerts
        unique_titles = len(set(a.title for a in alerts))
        repetition_ratio = 1 - (unique_titles / len(alerts))
        noise_factors.append(repetition_ratio * 0.3)
        
        # Factor 3: Alerts without AI enhancement
        non_enhanced_ratio = sum(1 for a in alerts if not a.ai_enhanced) / len(alerts)
        noise_factors.append(non_enhanced_ratio * 0.3)
        
        return min(1.0, sum(noise_factors))
    
    def _generate_alert_recommendations(self, frequency: Dict[str, int],
                                      severity_dist: Dict[str, int],
                                      noise_level: float,
                                      ai_patterns: Dict[str, Any]) -> List[str]:
        """Generate recommendations for alert optimization."""
        recommendations = []
        
        # Noise level recommendations
        if noise_level > 0.7:
            recommendations.append("High alert noise detected - consider adjusting thresholds")
        elif noise_level > 0.5:
            recommendations.append("Moderate alert noise - review low-severity alert conditions")
        
        # Frequency recommendations
        total_alerts = sum(frequency.values())
        if total_alerts > 100:
            recommendations.append("High alert volume - enable alert aggregation")
        
        # Severity balance
        if severity_dist.get('CRITICAL', 0) > total_alerts * 0.2:
            recommendations.append("Too many critical alerts - review severity classifications")
        
        # Add AI recommendations
        ai_recs = ai_patterns.get('optimizations', [])
        recommendations.extend(ai_recs[:2])  # Add top 2 AI recommendations
        
        return recommendations

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_alert_manager_agent(model_name: str = DEFAULT_MODEL,
                             temperature: float = DEFAULT_TEMPERATURE) -> SpyderX09_AlertManagerAgent:
    """
    Factory function to create Alert Manager Agent instance.
    
    Args:
        model_name: Ollama model to use
        temperature: Temperature for AI responses
        
    Returns:
        SpyderX09_AlertManagerAgent instance
    """
    return SpyderX09_AlertManagerAgent(model_name, temperature)

# Singleton instance
_module_instance = None

def get_module_instance() -> SpyderX09_AlertManagerAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        _module_instance = create_alert_manager_agent()
    return _module_instance

# ==============================================================================
# TEST EXECUTION
# ==============================================================================

async def test_alert_manager():
    """Test the Alert Manager Agent functionality."""
    logging.info("="*80)
    logging.info("Testing SpyderX09_AlertManagerAgent")
    logging.info("="*80)
    
    agent = create_alert_manager_agent()
    
    # Add test conditions
    logging.info("\nAdding Alert Conditions")
    logging.info("-"*40)
    
    # Price breakout condition
    price_condition = AlertCondition(
        name="price_breakout_high",
        type=AlertType.PRICE,
        expression="price.current",
        threshold=455.00,
        comparison=">",
        cooldown_minutes=5,
        metadata={'severity': 'HIGH'}
    )
    agent.add_condition(price_condition)
    logging.info(f"Added: {price_condition.name}")
    
    # Volume spike condition
    volume_condition = AlertCondition(
        name="volume_spike",
        type=AlertType.VOLUME,
        expression="volume.current",
        threshold=1500000,
        comparison=">",
        cooldown_minutes=10,
        metadata={'severity': 'MEDIUM'}
    )
    agent.add_condition(volume_condition)
    logging.info(f"Added: {volume_condition.name}")
    
    # Risk condition
    risk_condition = AlertCondition(
        name="drawdown_warning",
        type=AlertType.RISK,
        expression="risk.drawdown",
        threshold=0.05,
        comparison=">",
        cooldown_minutes=30,
        metadata={'severity': 'HIGH'}
    )
    agent.add_condition(risk_condition)
    logging.info(f"Added: {risk_condition.name}")
    
    # Test condition checking
    logging.info("\n\nTest 1: Condition Checking")
    logging.info("-"*40)
    
    market_data = {
        'price': {'current': 456.50, 'open': 454.00},
        'volume': {'current': 2000000, 'average': 1000000},
        'risk': {'drawdown': 0.08}
    }
    
    alerts = await agent.check_conditions(market_data)
    logging.info(f"Generated {len(alerts)} alerts:")
    for alert in alerts:
        logging.info(f"  - [{alert.severity.value}] {alert.title}: {alert.message}")
    
    # Test custom alert
    logging.info("\n\nTest 2: Custom Alert")
    logging.info("-"*40)
    
    custom_alert = await agent.process_custom_alert(
        title="Strategy Performance Alert",
        message="Win rate dropped below 50% in last 20 trades",
        severity=AlertSeverity.HIGH,
        data={'win_rate': 0.45, 'trades': 20}
    )
    logging.info(f"Custom Alert: [{custom_alert.severity.value}] {custom_alert.title}")
    logging.info(f"Message: {custom_alert.message}")
    if custom_alert.ai_enhanced:
        logging.info(f"AI Context: {custom_alert.metadata.get('ai_context', 'N/A')}")
    
    # Test alert delivery
    logging.info("\n\nTest 3: Alert Delivery")
    logging.info("-"*40)
    
    all_alerts = alerts + [custom_alert]
    if all_alerts:
        delivery_summary = await agent.deliver_alerts(all_alerts)
        logging.info(f"Delivery Summary:")
        logging.info(f"  Total Attempts: {delivery_summary['total_attempts']}")
        logging.info(f"  Successful: {delivery_summary['successful']}")
        logging.info(f"  Failed: {delivery_summary['failed']}")
        logging.info(f"  By Channel:")
        for channel, stats in delivery_summary['by_channel'].items():
            logging.info(f"    {channel}: {stats['success']} success, {stats['failed']} failed")
    
    # Test alert pattern analysis
    logging.info("\n\nTest 4: Alert Pattern Analysis")
    logging.info("-"*40)
    
    # Generate more sample alerts for pattern analysis
    for i in range(20):
        await agent.process_custom_alert(
            title=f"Test Alert {i}",
            message=f"Test message {i}",
            severity=AlertSeverity.MEDIUM if i % 3 == 0 else AlertSeverity.LOW,
            data={'index': i}
        )
    
    analysis = await agent.analyze_alert_patterns()
    logging.info(f"Alert Analysis:")
    logging.info(f"  Noise Level: {analysis.noise_level:.1%}")
    logging.info(f"  Alert Frequency by Type:")
    for alert_type, count in analysis.alert_frequency.items():
        logging.info(f"    {alert_type}: {count}")
    logging.info(f"  Recommendations:")
    for rec in analysis.recommendations[:3]:
        logging.info(f"    - {rec}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print(f"Initializing {__name__}")
    print(f"Ollama Available: {OLLAMA_AVAILABLE}")
    
    # Run async tests
    asyncio.run(test_alert_manager())
    
    print("\n" + "="*80)
    print("SpyderX09_AlertManagerAgent module loaded successfully!")
    print("="*80)
