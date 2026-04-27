#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderJ_Alerts
Module: SpyderJ05_TelegramBot.py
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
import json
import time
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import threading
from queue import Queue, Empty

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024

# Rate limiting
RATE_LIMIT_MESSAGES = 30  # Max messages per window
RATE_LIMIT_WINDOW = 1    # Window in seconds
RATE_LIMIT_BURST = 5     # Burst messages allowed

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1
CONNECTION_TIMEOUT = 10
READ_TIMEOUT = 30

# Message queue
QUEUE_MAX_SIZE = 1000
WORKER_THREAD_NAME = "TelegramWorker"

# ==============================================================================
# ENUMS
# ==============================================================================
class MessagePriority(Enum):
    """Message priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class MessageType(Enum):
    """Message types for formatting"""
    TRADE_OPEN = "trade_open"
    TRADE_CLOSE = "trade_close"
    STOP_LOSS = "stop_loss"
    PROFIT_TARGET = "profit_target"
    ALERT = "alert"
    ERROR = "error"
    SUMMARY = "summary"
    SYSTEM = "system"
    MARKET = "market"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class TelegramMessage:
    """Telegram message structure"""
    content: str
    chat_id: str
    priority: MessagePriority = MessagePriority.NORMAL
    message_type: MessageType = MessageType.SYSTEM
    parse_mode: str = "HTML"
    disable_notification: bool = False
    reply_markup: dict | None = None
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class NotificationStats:
    """Notification statistics"""
    messages_sent: int = 0
    messages_failed: int = 0
    last_sent: datetime | None = None
    last_error: str | None = None
    total_errors: int = 0
    uptime_start: datetime = field(default_factory=datetime.now)

# ==============================================================================
# TELEGRAM BOT CLASS
# ==============================================================================
class TelegramBot:
    """
    Telegram bot for trading notifications.

    Features:
    - Asynchronous message sending
    - Rate limiting and burst control
    - Message formatting with emojis
    - Error handling and retries
    - Priority queue for messages
    - Rich media support
    - Trading-specific templates
    """

    def __init__(self, bot_token: str, chat_id: str, event_manager: EventManager):
        """
        Initialize Telegram bot.

        Args:
            bot_token: Bot token from BotFather
            chat_id: Default chat ID for notifications
            event_manager: Event manager instance
        """
        self.bot_token = bot_token
        self.default_chat_id = chat_id
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # API session with retries
        self.session = self._create_session()

        # Message queue and worker
        self.message_queue = Queue(maxsize=QUEUE_MAX_SIZE)
        self.worker_thread = None
        self.running = False

        # Rate limiting
        self.rate_limiter = RateLimiter(RATE_LIMIT_MESSAGES, RATE_LIMIT_WINDOW)

        # Statistics
        self.stats = NotificationStats()

        # Message templates
        self.templates = self._load_templates()

        # Emoji mappings
        self.emojis = {
            'profit': '💰',
            'loss': '📉',
            'alert': '⚠️',
            'success': '✅',
            'error': '❌',
            'trade': '📊',
            'bull': '🟢',
            'bear': '🔴',
            'neutral': '⚪',
            'time': '⏰',
            'chart': '📈',
            'warning': '⚠️',
            'info': 'ℹ️',
            'robot': '🤖',
            'rocket': '🚀',
            'fire': '🔥',
            'stop': '🛑',
            'target': '🎯',
            'money': '💵',
            'calendar': '📅',
            'pin': '📌'
        }

        # Verify bot connection
        self._verify_bot()

        # Register event handlers
        self._register_event_handlers()

        self.logger.info("TelegramBot initialized")

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start the telegram bot worker"""
        if self.running:
            return

        self.running = True
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name=WORKER_THREAD_NAME,
            daemon=True
        )
        self.worker_thread.start()

        # Send startup message
        self.send_system_message("🤖 Spyder Trading Bot Started", priority=MessagePriority.HIGH)

        self.logger.info("Telegram bot started")

    def stop(self) -> None:
        """Stop the telegram bot worker"""
        if not self.running:
            return

        # Send shutdown message
        self.send_system_message("🛑 Spyder Trading Bot Stopping", priority=MessagePriority.HIGH)

        self.running = False

        # Wait for worker to finish
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

        # Close session
        self.session.close()

        self.logger.info("Telegram bot stopped")

    # ==========================================================================
    # PUBLIC METHODS - SENDING MESSAGES
    # ==========================================================================
    def send_message(
        self,
        text: str,
        chat_id: str | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        message_type: MessageType = MessageType.SYSTEM,
        disable_notification: bool = False,
        reply_markup: dict | None = None
    ) -> bool:
        """
        Queue a message for sending.

        Args:
            text: Message text (supports HTML)
            chat_id: Target chat ID (uses default if None)
            priority: Message priority
            message_type: Type of message for formatting
            disable_notification: Silent notification
            reply_markup: Inline keyboard markup

        Returns:
            Success status
        """
        try:
            message = TelegramMessage(
                content=text,
                chat_id=chat_id or self.default_chat_id,
                priority=priority,
                message_type=message_type,
                disable_notification=disable_notification,
                reply_markup=reply_markup
            )

            # Add to queue based on priority
            if priority == MessagePriority.CRITICAL:
                # Send immediately for critical messages
                return self._send_message_now(message)
            else:
                self.message_queue.put((priority.value, message), block=False)
                return True

        except Exception as e:
            self.logger.error("Failed to queue message: %s", e)
            return False

    def send_trade_opened(
        self,
        symbol: str,
        strategy: str,
        position_type: str,
        quantity: int,
        entry_price: float,
        target_price: float | None = None,
        stop_price: float | None = None,
        max_risk: float | None = None
    ) -> bool:
        """Send trade opened notification"""
        emoji = self.emojis['bull'] if 'CALL' in position_type.upper() else self.emojis['bear']

        message = f"""
{emoji} <b>TRADE OPENED</b>

{self.emojis['chart']} <b>Strategy:</b> {strategy}
{self.emojis['pin']} <b>Symbol:</b> {symbol}
{self.emojis['trade']} <b>Type:</b> {position_type}
{self.emojis['money']} <b>Quantity:</b> {quantity}
{self.emojis['money']} <b>Entry Price:</b> ${entry_price:.2f}
"""

        if target_price:
            message += f"{self.emojis['target']} <b>Target:</b> ${target_price:.2f}\n"

        if stop_price:
            message += f"{self.emojis['stop']} <b>Stop Loss:</b> ${stop_price:.2f}\n"

        if max_risk:
            message += f"{self.emojis['warning']} <b>Max Risk:</b> ${max_risk:.2f}\n"

        message += f"\n{self.emojis['time']} <i>{datetime.now().strftime('%I:%M %p')}</i>"

        return self.send_message(
            message,
            priority=MessagePriority.HIGH,
            message_type=MessageType.TRADE_OPEN
        )

    def send_trade_closed(
        self,
        symbol: str,
        strategy: str,
        position_type: str,
        entry_price: float,
        exit_price: float,
        quantity: int,
        pnl: float,
        pnl_percent: float,
        reason: str = "Target reached"
    ) -> bool:
        """Send trade closed notification"""
        if pnl >= 0:
            emoji = self.emojis['profit']
            status = "PROFIT"
            pnl_emoji = self.emojis['success']
        else:
            emoji = self.emojis['loss']
            status = "LOSS"
            pnl_emoji = self.emojis['error']

        message = f"""
{emoji} <b>TRADE CLOSED - {status}</b>

{self.emojis['chart']} <b>Strategy:</b> {strategy}
{self.emojis['pin']} <b>Symbol:</b> {symbol}
{self.emojis['trade']} <b>Type:</b> {position_type}
{self.emojis['money']} <b>Entry:</b> ${entry_price:.2f}
{self.emojis['money']} <b>Exit:</b> ${exit_price:.2f}
{self.emojis['money']} <b>Quantity:</b> {quantity}

{pnl_emoji} <b>P&L:</b> ${pnl:+.2f} ({pnl_percent:+.1f}%)
{self.emojis['info']} <b>Reason:</b> {reason}

{self.emojis['time']} <i>{datetime.now().strftime('%I:%M %p')}</i>
"""

        return self.send_message(
            message,
            priority=MessagePriority.HIGH,
            message_type=MessageType.TRADE_CLOSE
        )

    def send_stop_loss_alert(
        self,
        symbol: str,
        entry_price: float,
        stop_price: float,
        loss_amount: float
    ) -> bool:
        """Send stop loss triggered alert"""
        message = f"""
{self.emojis['stop']} <b>STOP LOSS TRIGGERED</b> {self.emojis['stop']}

{self.emojis['pin']} <b>Symbol:</b> {symbol}
{self.emojis['money']} <b>Entry:</b> ${entry_price:.2f}
{self.emojis['money']} <b>Stop:</b> ${stop_price:.2f}
{self.emojis['loss']} <b>Loss:</b> ${loss_amount:.2f}

<i>Position closed to limit losses</i>

{self.emojis['time']} <i>{datetime.now().strftime('%I:%M %p')}</i>
"""

        return self.send_message(
            message,
            priority=MessagePriority.CRITICAL,
            message_type=MessageType.STOP_LOSS
        )

    def send_daily_summary(
        self,
        date: datetime,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        gross_pnl: float,
        commissions: float,
        net_pnl: float,
        win_rate: float,
        best_trade: dict | None = None,
        worst_trade: dict | None = None,
        account_balance: float | None = None
    ) -> bool:
        """Send daily trading summary"""
        if net_pnl >= 0:
            emoji = self.emojis['profit']
            status_emoji = self.emojis['success']
        else:
            emoji = self.emojis['loss']
            status_emoji = self.emojis['error']

        message = f"""
{self.emojis['calendar']} <b>DAILY SUMMARY</b> {emoji}

<b>Date:</b> {date.strftime('%B %d, %Y')}

<b>📊 Trading Activity:</b>
• Total Trades: {total_trades}
• Winners: {winning_trades} {self.emojis['success']}
• Losers: {losing_trades} {self.emojis['error']}
• Win Rate: {win_rate:.1f}%

<b>💰 P&L Breakdown:</b>
• Gross P&L: ${gross_pnl:+.2f}
• Commissions: -${commissions:.2f}
• <b>Net P&L: ${net_pnl:+.2f}</b> {status_emoji}
"""

        if best_trade:
            message += f"\n<b>🏆 Best Trade:</b>\n{best_trade['symbol']} +${best_trade['pnl']:.2f}"

        if worst_trade:
            message += f"\n<b>😞 Worst Trade:</b>\n{worst_trade['symbol']} -${abs(worst_trade['pnl']):.2f}"  # noqa: E501

        if account_balance:
            message += f"\n\n<b>💼 Account Balance:</b> ${account_balance:,.2f}"

        message += f"\n\n{self.emojis['robot']} <i>Spyder Trading System</i>"

        return self.send_message(
            message,
            priority=MessagePriority.NORMAL,
            message_type=MessageType.SUMMARY
        )

    def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "info"
    ) -> bool:
        """Send general alert"""
        severity_emojis = {
            'info': self.emojis['info'],
            'warning': self.emojis['warning'],
            'error': self.emojis['error'],
            'critical': self.emojis['fire']
        }

        emoji = severity_emojis.get(severity, self.emojis['alert'])

        formatted_message = f"""
{emoji} <b>{title.upper()}</b>

{message}

{self.emojis['time']} <i>{datetime.now().strftime('%I:%M %p')}</i>
"""

        priority = MessagePriority.CRITICAL if severity == 'critical' else MessagePriority.HIGH

        return self.send_message(
            formatted_message,
            priority=priority,
            message_type=MessageType.ALERT
        )

    def send_system_message(
        self,
        message: str,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> bool:
        """Send system status message"""
        return self.send_message(
            message,
            priority=priority,
            message_type=MessageType.SYSTEM
        )

    def send_market_update(
        self,
        spy_price: float,
        spy_change: float,
        spy_change_percent: float,
        vix: float,
        market_sentiment: str = "Neutral"
    ) -> bool:
        """Send market update"""
        if spy_change >= 0:
            trend_emoji = self.emojis['bull']
        else:
            trend_emoji = self.emojis['bear']

        sentiment_emojis = {
            'Bullish': self.emojis['bull'],
            'Bearish': self.emojis['bear'],
            'Neutral': self.emojis['neutral']
        }

        sentiment_emoji = sentiment_emojis.get(market_sentiment, self.emojis['neutral'])

        message = f"""
{self.emojis['chart']} <b>MARKET UPDATE</b>

<b>SPY:</b> ${spy_price:.2f} {trend_emoji}
<b>Change:</b> ${spy_change:+.2f} ({spy_change_percent:+.2f}%)
<b>VIX:</b> {vix:.2f}
<b>Sentiment:</b> {market_sentiment} {sentiment_emoji}

{self.emojis['time']} <i>{datetime.now().strftime('%I:%M %p')}</i>
"""

        return self.send_message(
            message,
            priority=MessagePriority.LOW,
            message_type=MessageType.MARKET
        )

    def send_confirmation_request(
        self,
        order: dict,
        reason: str,
        timeout: int = 60,
    ) -> bool | None:
        """
        Send a high-risk order confirmation request via inline keyboard and poll
        for the operator's response.

        Sends a Telegram message with ✅ APPROVE and ❌ REJECT inline buttons,
        then polls getUpdates until the operator responds or the timeout expires.

        Args:
            order:   Order details dict (symbol, side, quantity, type, price).
            reason:  Human-readable reason the order is flagged as high-risk.
            timeout: Seconds to wait for a response before giving up (default 60).

        Returns:
            True  — operator approved.
            False — operator rejected.
            None  — timed out; caller should fall back to autonomous decision.
        """
        order_id = order.get('id', f"ord_{int(datetime.now().timestamp())}")
        approve_data = f"spyder_approve_{order_id}"
        reject_data = f"spyder_reject_{order_id}"

        text = (
            f"\U0001f6a8 <b>HIGH-RISK ORDER \u2014 APPROVAL REQUIRED</b>\n\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Symbol:</b> {order.get('symbol', 'N/A')}\n"
            f"<b>Side:</b> {order.get('side', 'N/A')}\n"
            f"<b>Quantity:</b> {order.get('quantity', 'N/A')}\n"
            f"<b>Type:</b> {order.get('type', 'N/A')}\n"
            f"<b>Price:</b> {order.get('price', 'MARKET')}\n\n"
            f"\u23f3 <i>Approval window: {timeout}s</i>\n"
            f"\U0001f550 <i>{datetime.now().strftime('%H:%M:%S ET')}</i>"
        )

        reply_markup = {
            "inline_keyboard": [[
                {"text": "\u2705 APPROVE", "callback_data": approve_data},
                {"text": "\u274c REJECT",  "callback_data": reject_data},
            ]]
        }

        sent = self.send_message(
            text,
            priority=MessagePriority.CRITICAL,
            message_type=MessageType.ALERT,
            reply_markup=reply_markup,
        )
        if not sent:
            self.logger.warning("Could not send high-risk confirmation request via Telegram.")
            return None

        # Poll getUpdates for the callback response
        poll_timeout = min(10, timeout)
        gotten_update_id: int | None = None
        deadline = time.monotonic() + timeout

        try:
            updates_url = TELEGRAM_API_URL.format(token=self.bot_token, method="getUpdates")

            # Advance offset past stale updates so we only see fresh callbacks
            init_resp = self.session.get(
                updates_url, params={"limit": 1, "timeout": 0}, timeout=CONNECTION_TIMEOUT
            )
            if init_resp.ok:
                prior = init_resp.json().get("result", [])
                if prior:
                    gotten_update_id = prior[-1]["update_id"] + 1

            while time.monotonic() < deadline:
                remaining = int(deadline - time.monotonic())
                params = {
                    "offset": gotten_update_id,
                    "timeout": min(poll_timeout, max(1, remaining)),
                    "allowed_updates": ["callback_query"],
                }
                resp = self.session.get(
                    updates_url, params=params, timeout=poll_timeout + 5
                )
                if not resp.ok:
                    time.sleep(1)
                    continue

                for update in resp.json().get("result", []):
                    gotten_update_id = update["update_id"] + 1
                    cq = update.get("callback_query")
                    if not cq:
                        continue
                    data = cq.get("data", "")
                    # Acknowledge the button press (cosmetic — non-critical)
                    try:
                        ack_url = TELEGRAM_API_URL.format(
                            token=self.bot_token, method="answerCallbackQuery"
                        )
                        self.session.post(
                            ack_url,
                            json={"callback_query_id": cq["id"], "text": "Response received"},
                            timeout=CONNECTION_TIMEOUT,
                        )
                    except Exception as _ack_err:
                        self.logger.debug("Telegram callback ack failed (non-critical): %s", _ack_err)  # noqa: E501

                    operator = cq.get("from", {}).get("username", "operator")
                    if data == approve_data:
                        self.logger.info(
                            "High-risk order %s APPROVED via Telegram by %s.", order_id, operator
                        )
                        return True
                    if data == reject_data:
                        self.logger.warning(
                            "High-risk order %s REJECTED via Telegram by %s.", order_id, operator
                        )
                        return False

        except Exception as e:
            self.logger.error("Error polling Telegram for confirmation: %s", e)
            return None

        self.logger.warning(
            "Confirmation request for order %s timed out after %ss.", order_id, timeout
        )
        return None

    # ==========================================================================
    # PRIVATE METHODS - MESSAGE SENDING
    # ==========================================================================
    def _send_message_now(self, message: TelegramMessage) -> bool:
        """Send message immediately via Telegram API"""
        try:
            # Check rate limit
            if not self.rate_limiter.allow_request():
                self.logger.warning("Rate limit exceeded, queueing message")
                self.message_queue.put((message.priority.value, message))
                return True

            # Prepare API request
            url = TELEGRAM_API_URL.format(
                token=self.bot_token,
                method="sendMessage"
            )

            # Split long messages
            messages = self._split_message(message.content)

            for msg_part in messages:
                payload = {
                    'chat_id': message.chat_id,
                    'text': msg_part,
                    'parse_mode': message.parse_mode,
                    'disable_notification': message.disable_notification
                }

                if message.reply_markup and msg_part == messages[-1]:
                    payload['reply_markup'] = json.dumps(message.reply_markup)

                # Send request
                response = self.session.post(url, json=payload, timeout=CONNECTION_TIMEOUT)
                response.raise_for_status()

                # Update stats
                self.stats.messages_sent += 1
                self.stats.last_sent = datetime.now()

            return True

        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to send message: %s", e)
            self.stats.messages_failed += 1
            self.stats.last_error = str(e)
            self.stats.total_errors += 1

            # Retry if possible
            if message.retry_count < MAX_RETRIES:
                message.retry_count += 1
                time.sleep(RETRY_DELAY * message.retry_count)  # thread-safe: time.sleep() intentional  # noqa: E501
                return self._send_message_now(message)

            return False

    def _worker_loop(self) -> None:
        """Worker thread for sending queued messages"""
        while self.running:
            try:
                # Get message from queue (timeout allows graceful shutdown)
                priority, message = self.message_queue.get(timeout=1)

                # Send message
                self._send_message_now(message)

                # Mark task done
                self.message_queue.task_done()

            except Empty:
                continue
            except Exception as e:
                self.logger.error("Worker error: %s", e)

    def _split_message(self, text: str) -> list[str]:
        """Split long messages to fit Telegram limits"""
        if len(text) <= MAX_MESSAGE_LENGTH:
            return [text]

        messages = []
        lines = text.split('\n')
        current_message = ""

        for line in lines:
            if len(current_message) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                messages.append(current_message.strip())
                current_message = line + '\n'
            else:
                current_message += line + '\n'

        if current_message:
            messages.append(current_message.strip())

        return messages

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry logic"""
        session = requests.Session()

        retry = Retry(
            total=MAX_RETRIES,
            backoff_factor=RETRY_DELAY,
            status_forcelist=[429, 500, 502, 503, 504]
        )

        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        return session

    def _verify_bot(self) -> bool:
        """Verify bot token and connection"""
        try:
            url = TELEGRAM_API_URL.format(
                token=self.bot_token,
                method="getMe"
            )

            response = self.session.get(url, timeout=CONNECTION_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            if data.get('ok'):
                bot_info = data['result']
                self.logger.info("Bot verified: @%s", bot_info['username'])
                return True
            else:
                self.logger.error("Bot verification failed: %s", data)
                return False

        except Exception as e:
            self.logger.error("Bot verification error: %s", e)
            return False

    def _load_templates(self) -> dict[str, str]:
        """Load message templates"""
        return {
            'trade_open': "{emoji} <b>TRADE OPENED</b>\n\n{details}",
            'trade_close': "{emoji} <b>TRADE CLOSED</b>\n\n{details}",
            'alert': "{emoji} <b>{title}</b>\n\n{message}",
            'error': "{emoji} <b>ERROR</b>\n\n{error_message}",
            'summary': "{emoji} <b>{title}</b>\n\n{content}"
        }

    def _register_event_handlers(self) -> None:
        """Register event handlers for automatic notifications"""
        # Trade events
        self.event_manager.subscribe(
            self._handle_trade_event,
            event_type=EventType.TRADE,
            subscriber_id="telegram_trade"
        )

        # Alert events
        self.event_manager.subscribe(
            self._handle_alert_event,
            event_type=EventType.ALERT,
            subscriber_id="telegram_alert"
        )

        # System events
        self.event_manager.subscribe(
            self._handle_system_event,
            event_type=EventType.SYSTEM,
            subscriber_id="telegram_system"
        )

    def _handle_trade_event(self, event: Event) -> None:
        """Handle trade events"""
        try:
            trade_type = event.data.get('type')

            if trade_type == 'opened':
                self.send_trade_opened(
                    symbol=event.data['symbol'],
                    strategy=event.data['strategy'],
                    position_type=event.data['position_type'],
                    quantity=event.data['quantity'],
                    entry_price=event.data['entry_price'],
                    target_price=event.data.get('target_price'),
                    stop_price=event.data.get('stop_price'),
                    max_risk=event.data.get('max_risk')
                )

            elif trade_type == 'closed':
                self.send_trade_closed(
                    symbol=event.data['symbol'],
                    strategy=event.data['strategy'],
                    position_type=event.data['position_type'],
                    entry_price=event.data['entry_price'],
                    exit_price=event.data['exit_price'],
                    quantity=event.data['quantity'],
                    pnl=event.data['pnl'],
                    pnl_percent=event.data['pnl_percent'],
                    reason=event.data.get('reason', 'Manual close')
                )

        except Exception as e:
            self.logger.error("Error handling trade event: %s", e)

    def _handle_alert_event(self, event: Event) -> None:
        """Handle alert events"""
        try:
            self.send_alert(
                title=event.data.get('title', 'Alert'),
                message=event.data.get('message', ''),
                severity=event.data.get('severity', 'info')
            )
        except Exception as e:
            self.logger.error("Error handling alert event: %s", e)

    def _handle_system_event(self, event: Event) -> None:
        """Handle system events"""
        try:
            if event.data.get('type') == 'error':
                self.send_alert(
                    title="System Error",
                    message=event.data.get('message', 'Unknown error'),
                    severity='error'
                )
        except Exception as e:
            self.logger.error("Error handling system event: %s", e)

    # ==========================================================================
    # PUBLIC METHODS - UTILITIES
    # ==========================================================================
    def get_stats(self) -> dict[str, Any]:
        """Get bot statistics"""
        uptime = datetime.now() - self.stats.uptime_start

        return {
            'messages_sent': self.stats.messages_sent,
            'messages_failed': self.stats.messages_failed,
            'total_errors': self.stats.total_errors,
            'last_sent': self.stats.last_sent.isoformat() if self.stats.last_sent else None,
            'last_error': self.stats.last_error,
            'uptime_seconds': uptime.total_seconds(),
            'queue_size': self.message_queue.qsize(),
            'is_running': self.running
        }

    def clear_queue(self) -> int:
        """Clear message queue and return number of cleared messages"""
        count = 0
        try:
            while not self.message_queue.empty():
                self.message_queue.get_nowait()
                count += 1
        except Empty:
            pass

        self.logger.info("Cleared %s messages from queue", count)
        return count

# ==============================================================================
# RATE LIMITER CLASS
# ==============================================================================
class RateLimiter:
    """Simple rate limiter using sliding window"""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()
        self.lock = threading.Lock()

    def allow_request(self) -> bool:
        """Check if request is allowed"""
        with self.lock:
            now = time.time()

            # Remove old requests outside window
            while self.requests and self.requests[0] < now - self.window_seconds:
                self.requests.popleft()

            # Check if we can make request
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True

            return False

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test the Telegram bot
    from SpyderA_Core.SpyderA05_EventManager import EventManager

    # Test configuration
    BOT_TOKEN = "YOUR_BOT_TOKEN"  # Replace with actual token  # noqa: S105
    CHAT_ID = "YOUR_CHAT_ID"      # Replace with actual chat ID

    # Initialize
    event_manager = EventManager()
    bot = TelegramBot(BOT_TOKEN, CHAT_ID, event_manager)

    # Start bot
    bot.start()

    # Test messages

    # Test trade opened
    bot.send_trade_opened(
        symbol="SPY 450C",
        strategy="Iron Condor",
        position_type="Call Credit Spread",
        quantity=10,
        entry_price=2.50,
        target_price=1.25,
        stop_price=3.75,
        max_risk=1250
    )

    time.sleep(2)  # thread-safe: time.sleep() intentional

    # Test trade closed
    bot.send_trade_closed(
        symbol="SPY 450C",
        strategy="Iron Condor",
        position_type="Call Credit Spread",
        entry_price=2.50,
        exit_price=1.25,
        quantity=10,
        pnl=125,
        pnl_percent=50,
        reason="Target reached"
    )

    time.sleep(2)  # thread-safe: time.sleep() intentional

    # Test daily summary
    bot.send_daily_summary(
        date=datetime.now(),
        total_trades=5,
        winning_trades=3,
        losing_trades=2,
        gross_pnl=450,
        commissions=25,
        net_pnl=425,
        win_rate=60.0,
        best_trade={'symbol': 'SPY 450P', 'pnl': 250},
        worst_trade={'symbol': 'SPY 460C', 'pnl': -100},
        account_balance=10425
    )

    time.sleep(2)  # thread-safe: time.sleep() intentional

    # Test alert
    bot.send_alert(
        title="High Volatility Alert",
        message="VIX has increased by 15% in the last hour. Consider reducing position sizes.",
        severity="warning"
    )

    time.sleep(5)  # thread-safe: time.sleep() intentional

    # Get stats
    stats = bot.get_stats()

    # Stop bot
    bot.stop()
