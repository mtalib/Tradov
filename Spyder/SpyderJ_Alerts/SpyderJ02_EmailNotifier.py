#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderJ_Alerts
Module: SpyderJ02_EmailNotifier.py
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
from datetime import datetime
from typing import Any
from dataclasses import field
from enum import Enum, auto
from pathlib import Path
import threading
import queue
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import jinja2
from email_validator import validate_email, EmailNotValidError

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU04_Encryption import EncryptionManager

SMTP_SERVERS = {
    'gmail': {
        'server': 'smtp.gmail.com',
        'port': 587,
        'use_tls': True
    },
    'outlook': {
        'server': 'smtp-mail.outlook.com',
        'port': 587,
        'use_tls': True
    },
    'yahoo': {
        'server': 'smtp.mail.yahoo.com',
        'port': 587,
        'use_tls': True
    }
}

# Email limits
MAX_RECIPIENTS = 10
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_RETRIES = 3
RETRY_DELAY = 60  # seconds

# Template directory
TEMPLATE_DIR = Path(__file__).parent / 'templates'

# ==============================================================================
# ENUMS
# ==============================================================================
class NotificationType(Enum):
    """Types of email notifications"""
    TRADE_EXECUTION = auto()
    POSITION_ALERT = auto()
    RISK_WARNING = auto()
    SYSTEM_ALERT = auto()
    DAILY_SUMMARY = auto()
    WEEKLY_REPORT = auto()
    ERROR_ALERT = auto()
    PERFORMANCE_UPDATE = auto()

class Priority(Enum):
    """Email priority levels"""
    LOW = "5"
    NORMAL = "3"
    HIGH = "1"
    URGENT = "1"

class EmailStatus(Enum):
    """Email sending status"""
    PENDING = auto()
    SENT = auto()
    FAILED = auto()
    RETRYING = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class EmailConfig:
    """Email configuration"""
    smtp_server: str
    smtp_port: int
    use_tls: bool
    username: str
    password: str  # Encrypted
    from_address: str
    from_name: str = "Spyder Trading System"
    reply_to: str | None = None

class EmailRecipient:
    """Email recipient"""
    email: str
    name: str | None = None
    notification_types: list[NotificationType] = field(default_factory=list)
    active: bool = True

class EmailMessage:
    """Email message"""
    recipients: list[EmailRecipient]
    subject: str
    body_html: str
    body_text: str
    notification_type: NotificationType
    priority: Priority = Priority.NORMAL
    attachments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

class EmailQueueItem:
    """Item in email queue"""
    message: EmailMessage
    attempts: int = 0
    status: EmailStatus = EmailStatus.PENDING
    last_attempt: datetime | None = None
    error: str | None = None

# ==============================================================================
# EMAIL NOTIFIER CLASS
# ==============================================================================
class EmailNotifier:
    """
    Handles email notifications for the trading system.

    Features:
    - Multiple email provider support
    - HTML email templates
    - Attachment support
    - Retry mechanism
    - Asynchronous sending
    - Recipient management
    """

    def __init__(self, config: EmailConfig):
        """
        Initialize email notifier.

        Args:
            config: Email configuration
        """
        self.config = config
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.encryption = EncryptionManager()

        # Decrypt password
        self.smtp_password = self.encryption.decrypt(config.password)

        # Recipient management
        self.recipients: dict[str, EmailRecipient] = {}

        # Email queue
        self.email_queue: queue.Queue[EmailQueueItem] = queue.Queue()

        # Template engine
        self.template_env = self._setup_template_engine()

        # Sending thread
        self._sender_thread: threading.Thread | None = None
        self._running = False

        # Statistics
        self.stats = {
            'sent': 0,
            'failed': 0,
            'retried': 0
        }

        self.logger.info("EmailNotifier initialized")

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start email sender thread"""
        if self._running:
            return

        self._running = True
        self._sender_thread = threading.Thread(
            target=self._sender_loop,
            daemon=True,
            name="EmailSender"
        )
        self._sender_thread.start()

        self.logger.info("Email sender thread started")

    def stop(self) -> None:
        """Stop email sender thread"""
        self._running = False

        if self._sender_thread:
            self._sender_thread.join(timeout=5.0)

        self.logger.info("Email sender thread stopped")

    # ==========================================================================
    # RECIPIENT MANAGEMENT
    # ==========================================================================
    def add_recipient(self, recipient: EmailRecipient) -> bool:
        """
        Add email recipient.

        Args:
            recipient: Recipient to add

        Returns:
            Success status
        """
        try:
            # Validate email
            validation = validate_email(recipient.email)
            recipient.email = validation.email

            self.recipients[recipient.email] = recipient
            self.logger.info("Added recipient: %s", recipient.email)
            return True

        except EmailNotValidError as e:
            self.logger.error("Invalid email address: %s", e)
            return False

    def remove_recipient(self, email: str) -> None:
        """Remove email recipient"""
        if email in self.recipients:
            del self.recipients[email]
            self.logger.info("Removed recipient: %s", email)

    def update_recipient_preferences(
        self,
        email: str,
        notification_types: list[NotificationType]
    ) -> None:
        """Update recipient notification preferences"""
        if email in self.recipients:
            self.recipients[email].notification_types = notification_types
            self.logger.info("Updated preferences for: %s", email)

    # ==========================================================================
    # NOTIFICATION METHODS
    # ==========================================================================
    def send_trade_notification(
        self,
        trade_data: dict[str, Any]
    ) -> None:
        """Send trade execution notification"""
        # Get recipients for trade notifications
        recipients = self._get_recipients_for_type(NotificationType.TRADE_EXECUTION)

        if not recipients:
            return

        # Render template
        subject = f"Trade Executed: {trade_data['symbol']} {trade_data['action']}"

        context = {
            'trade': trade_data,
            'timestamp': datetime.now(),
            'system_name': 'Spyder Trading System'
        }

        body_html = self._render_template('trade_execution.html', context)
        body_text = self._render_template('trade_execution.txt', context)

        # Create message
        message = EmailMessage(
            recipients=recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            notification_type=NotificationType.TRADE_EXECUTION,
            priority=Priority.HIGH,
            metadata={'trade_id': trade_data.get('trade_id')}
        )

        # Queue message
        self._queue_email(message)

    def send_position_alert(
        self,
        position_data: dict[str, Any],
        alert_type: str
    ) -> None:
        """Send position alert notification"""
        recipients = self._get_recipients_for_type(NotificationType.POSITION_ALERT)

        if not recipients:
            return

        # Determine priority based on alert type
        priority = Priority.URGENT if alert_type in ['stop_loss', 'margin_call'] else Priority.HIGH

        subject = f"Position Alert: {position_data['symbol']} - {alert_type.replace('_', ' ').title()}"

        context = {
            'position': position_data,
            'alert_type': alert_type,
            'timestamp': datetime.now()
        }

        body_html = self._render_template('position_alert.html', context)
        body_text = self._render_template('position_alert.txt', context)

        message = EmailMessage(
            recipients=recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            notification_type=NotificationType.POSITION_ALERT,
            priority=priority
        )

        self._queue_email(message)

    def send_risk_warning(
        self,
        risk_data: dict[str, Any]
    ) -> None:
        """Send risk warning notification"""
        recipients = self._get_recipients_for_type(NotificationType.RISK_WARNING)

        if not recipients:
            return

        subject = f"Risk Warning: {risk_data['risk_type']}"

        context = {
            'risk': risk_data,
            'timestamp': datetime.now(),
            'recommended_actions': risk_data.get('recommended_actions', [])
        }

        body_html = self._render_template('risk_warning.html', context)
        body_text = self._render_template('risk_warning.txt', context)

        message = EmailMessage(
            recipients=recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            notification_type=NotificationType.RISK_WARNING,
            priority=Priority.URGENT
        )

        self._queue_email(message)

    def send_daily_summary(
        self,
        summary_data: dict[str, Any],
        attachments: list[dict[str, Any]] | None = None
    ) -> None:
        """Send daily trading summary"""
        recipients = self._get_recipients_for_type(NotificationType.DAILY_SUMMARY)

        if not recipients:
            return

        date_str = datetime.now().strftime('%Y-%m-%d')
        subject = f"Daily Trading Summary - {date_str}"

        context = {
            'summary': summary_data,
            'date': date_str,
            'timestamp': datetime.now()
        }

        body_html = self._render_template('daily_summary.html', context)
        body_text = self._render_template('daily_summary.txt', context)

        message = EmailMessage(
            recipients=recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            notification_type=NotificationType.DAILY_SUMMARY,
            priority=Priority.NORMAL,
            attachments=attachments or []
        )

        self._queue_email(message)

    def send_system_alert(
        self,
        alert_data: dict[str, Any]
    ) -> None:
        """Send system alert notification"""
        recipients = self._get_recipients_for_type(NotificationType.SYSTEM_ALERT)

        if not recipients:
            return

        subject = f"System Alert: {alert_data['alert_type']}"

        context = {
            'alert': alert_data,
            'timestamp': datetime.now()
        }

        body_html = self._render_template('system_alert.html', context)
        body_text = self._render_template('system_alert.txt', context)

        # Determine priority
        priority = Priority.URGENT if alert_data.get('severity') == 'critical' else Priority.HIGH

        message = EmailMessage(
            recipients=recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            notification_type=NotificationType.SYSTEM_ALERT,
            priority=priority
        )

        self._queue_email(message)

    def send_custom_notification(
        self,
        recipients: list[str],
        subject: str,
        body: str,
        html: bool = False,
        priority: Priority = Priority.NORMAL,
        attachments: list[dict[str, Any]] | None = None
    ) -> None:
        """Send custom notification"""
        # Validate recipients
        valid_recipients = []
        for email in recipients:
            if email in self.recipients and self.recipients[email].active:
                valid_recipients.append(self.recipients[email])

        if not valid_recipients:
            self.logger.warning("No valid recipients for custom notification")
            return

        if html:
            body_html = body
            body_text = self._html_to_text(body)
        else:
            body_html = f"<pre>{body}</pre>"
            body_text = body

        message = EmailMessage(
            recipients=valid_recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            notification_type=NotificationType.SYSTEM_ALERT,
            priority=priority,
            attachments=attachments or []
        )

        self._queue_email(message)

    # ==========================================================================
    # EMAIL SENDING
    # ==========================================================================
    def _sender_loop(self) -> None:
        """Main email sender loop"""
        while self._running:
            try:
                # Get item from queue with timeout
                try:
                    item = self.email_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Check if retry needed
                if item.status == EmailStatus.FAILED and item.attempts < MAX_RETRIES:
                    if item.last_attempt:
                        time_since_attempt = (datetime.now() - item.last_attempt).seconds
                        if time_since_attempt < RETRY_DELAY:
                            # Re-queue for later
                            self.email_queue.put(item)
                            continue

                # Send email
                success = self._send_email(item)

                if success:
                    item.status = EmailStatus.SENT
                    self.stats['sent'] += 1
                    self.logger.info("Email sent: %s", item.message.subject)
                else:
                    item.attempts += 1
                    item.last_attempt = datetime.now()

                    if item.attempts >= MAX_RETRIES:
                        item.status = EmailStatus.FAILED
                        self.stats['failed'] += 1
                        self.logger.error("Email failed after %s attempts: %s", MAX_RETRIES, item.message.subject)
                    else:
                        item.status = EmailStatus.RETRYING
                        self.stats['retried'] += 1
                        self.email_queue.put(item)  # Re-queue
                        self.logger.warning("Email retry scheduled: %s", item.message.subject)

            except Exception as e:
                self.logger.error("Error in sender loop: %s", e)
                self.error_handler.handle_error(e, "_sender_loop")

    def _send_email(self, item: EmailQueueItem) -> bool:
        """
        Send single email.

        Args:
            item: Email queue item

        Returns:
            Success status
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.config.from_name} <{self.config.from_address}>"
            msg['To'] = ', '.join([r.email for r in item.message.recipients])
            msg['Subject'] = item.message.subject
            msg['Date'] = email.utils.formatdate(localtime=True)
            msg['X-Priority'] = item.message.priority.value

            if self.config.reply_to:
                msg['Reply-To'] = self.config.reply_to

            # Add text and HTML parts
            msg.attach(MIMEText(item.message.body_text, 'plain'))
            msg.attach(MIMEText(item.message.body_html, 'html'))

            # Add attachments
            for attachment in item.message.attachments:
                self._add_attachment(msg, attachment)

            # Connect to server
            context = ssl.create_default_context()

            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls(context=context)

                server.login(self.config.username, self.smtp_password)

                # Send to all recipients
                recipient_emails = [r.email for r in item.message.recipients]
                server.send_message(msg, to_addrs=recipient_emails)

            return True

        except Exception as e:
            item.error = str(e)
            self.logger.error("Failed to send email: %s", e)
            return False

    def _add_attachment(
        self,
        msg: MIMEMultipart,
        attachment: dict[str, Any]
    ) -> None:
        """Add attachment to email"""
        try:
            # Get attachment data
            filename = attachment['filename']
            data = attachment['data']

            # Check size
            if len(data) > MAX_ATTACHMENT_SIZE:
                self.logger.warning("Attachment too large: %s", filename)
                return

            # Create attachment
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(data)
            encoders.encode_base64(part)

            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )

            msg.attach(part)

        except Exception as e:
            self.logger.error("Error adding attachment: %s", e)

    # ==========================================================================
    # TEMPLATE RENDERING
    # ==========================================================================
    def _setup_template_engine(self) -> jinja2.Environment:
        """Setup Jinja2 template engine"""
        # Create template directory if it doesn't exist
        TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

        # Create default templates
        self._create_default_templates()

        # Setup Jinja2
        loader = jinja2.FileSystemLoader(str(TEMPLATE_DIR))
        env = jinja2.Environment(
            loader=loader,
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )

        # Add custom filters
        env.filters['currency'] = lambda x: f"${x:,.2f}"
        env.filters['percent'] = lambda x: f"{x:.2%}"
        env.filters['datetime'] = lambda x: x.strftime('%Y-%m-%d %H:%M:%S')

        return env

    def _render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render email template"""
        try:
            template = self.template_env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            self.logger.error("Error rendering template %s: %s", template_name, e)
            return f"Error rendering template: {e}"

    def _create_default_templates(self) -> None:
        """Create default email templates"""
        # Trade execution template
        trade_html = """
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Trade Execution Notification</h2>
            <p>A trade has been executed in your Spyder Trading System:</p>

            <table style="border-collapse: collapse; width: 100%;">
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Symbol:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ trade.symbol }}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Action:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ trade.action }}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Quantity:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ trade.quantity }}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Price:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ trade.price | currency }}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Time:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ timestamp | datetime }}</td>
                </tr>
            </table>

            <p style="margin-top: 20px; color: #666;">
                This is an automated notification from {{ system_name }}.
            </p>
        </body>
        </html>
        """

        trade_txt = """
Trade Execution Notification

A trade has been executed in your Spyder Trading System:

Symbol: {{ trade.symbol }}
Action: {{ trade.action }}
Quantity: {{ trade.quantity }}
Price: {{ trade.price | currency }}
Time: {{ timestamp | datetime }}

This is an automated notification from {{ system_name }}.
"""

        # Save templates
        (TEMPLATE_DIR / 'trade_execution.html').write_text(trade_html)
        (TEMPLATE_DIR / 'trade_execution.txt').write_text(trade_txt)

        # Create other default templates similarly...

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _get_recipients_for_type(
        self,
        notification_type: NotificationType
    ) -> list[EmailRecipient]:
        """Get recipients subscribed to notification type"""
        recipients = []

        for recipient in self.recipients.values():
            if recipient.active and notification_type in recipient.notification_types:
                recipients.append(recipient)

        return recipients

    def _queue_email(self, message: EmailMessage) -> None:
        """Add email to send queue"""
        item = EmailQueueItem(message=message)
        self.email_queue.put(item)

        self.logger.debug("Email queued: %s", message.subject)

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text"""
        # Simple conversion - could use html2text library
        import re

        # Remove HTML tags
        text = re.sub('<[^<]+?>', '', html)

        # Replace common entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def get_stats(self) -> dict[str, int]:
        """Get email sending statistics"""
        return self.stats.copy()

    def test_connection(self) -> bool:
        """Test SMTP connection"""
        try:
            context = ssl.create_default_context()

            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls(context=context)

                server.login(self.config.username, self.smtp_password)

            self.logger.info("SMTP connection test successful")
            return True

        except Exception as e:
            self.logger.error("SMTP connection test failed: %s", e)
            return False

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    import email.utils

    # Test email notifier
    config = EmailConfig(
        smtp_server='smtp.gmail.com',
        smtp_port=587,
        use_tls=True,
        username='your_email@gmail.com',
        password='encrypted_password',  # Would be encrypted
        from_address='your_email@gmail.com',
        from_name='Spyder Trading'
    )

    notifier = EmailNotifier(config)

    # Add test recipient
    recipient = EmailRecipient(
        email='test@example.com',
        name='Test User',
        notification_types=[
            NotificationType.TRADE_EXECUTION,
            NotificationType.DAILY_SUMMARY
        ]
    )
    notifier.add_recipient(recipient)

    # Start notifier
    notifier.start()

    # Send test notifications
    trade_data = {
        'trade_id': 'TEST001',
        'symbol': 'SPY 450C',
        'action': 'BUY TO OPEN',
        'quantity': 10,
        'price': 5.50,
        'strategy': 'IronCondor'
    }

    notifier.send_trade_notification(trade_data)

    # Wait for sending
    time.sleep(5)  # thread-safe: time.sleep() intentional

    # Stop notifier
    notifier.stop()

    # Print stats
