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
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from queue import Empty, Queue
from typing import Any
from zoneinfo import ZoneInfo

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
from Spyder.SpyderA_Core.SpyderA05_EventManager import (
    EventManager,
    Event,
    EventType,
    EventPriority,
)
from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import get_session_supervisor

_ET_TZ = ZoneInfo("America/New_York")

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
COMMAND_POLL_THREAD_NAME = "TelegramCommandPoller"
SUMMARY_THREAD_NAME = "TelegramSummaryPublisher"
COMMAND_AUDIT_DIR = Path("market_data/operator_commands")
PENDING_QUEUE_DIR = Path("market_data/telegram_pending")
PENDING_QUEUE_FILE = PENDING_QUEUE_DIR / "pending_messages.jsonl"

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
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

@dataclass
class NotificationStats:
    """Notification statistics"""
    messages_sent: int = 0
    messages_failed: int = 0
    last_sent: datetime | None = None
    last_error: str | None = None
    total_errors: int = 0
    uptime_start: datetime = field(default_factory=lambda: datetime.now(UTC))

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
        self.command_session = self._create_session(retry_total=0)

        # Message queue and worker
        self.message_queue = Queue(maxsize=QUEUE_MAX_SIZE)
        self.worker_thread = None
        self.command_thread = None
        self.summary_thread = None
        self.running = False
        self._stop_event = threading.Event()
        self._command_poll_timeout_seconds: int = max(
            1,
            int(os.environ.get("TELEGRAM_COMMAND_POLL_TIMEOUT_S", "5") or "5"),
        )
        self._command_poll_request_timeout_seconds: int = max(
            self._command_poll_timeout_seconds + 1,
            int(
                os.environ.get(
                    "TELEGRAM_COMMAND_POLL_REQUEST_TIMEOUT_S",
                    str(self._command_poll_timeout_seconds + 1),
                )
                or str(self._command_poll_timeout_seconds + 1)
            ),
        )
        self._update_offset: int | None = None
        self._allowed_user_ids = self._load_allowed_user_ids()
        self._pending_confirms: dict[int, dict[str, Any]] = {}
        self._pending_file_lock = threading.Lock()
        self._pending_queue_file: Path = PENDING_QUEUE_FILE
        self._pending_replay_limit: int = max(
            1,
            int(os.environ.get("TELEGRAM_PENDING_REPLAY_LIMIT", "200") or "200"),
        )
        self._pending_max_rows: int = max(
            100,
            int(os.environ.get("TELEGRAM_PENDING_MAX_ROWS", "2000") or "2000"),
        )
        self._pending_max_age_hours: int = max(
            1,
            int(os.environ.get("TELEGRAM_PENDING_MAX_AGE_HOURS", "168") or "168"),
        )
        self._resume_dual_approval: bool = os.environ.get(
            "TELEGRAM_RESUME_DUAL_APPROVAL", "0"
        ).strip().lower() in ("1", "true", "yes", "on")
        self._resume_pending: dict[str, Any] | None = None
        self._recent_trade_close_keys: dict[str, float] = {}
        self._trade_close_dedup_window_seconds: int = 30

        # Periodic P/L reporting controls
        self._pl_reporting_enabled: bool = os.environ.get(
            "TELEGRAM_PL_REPORTING_ENABLED", "1"
        ).strip().lower() in ("1", "true", "yes", "on")
        self._pl_heartbeat_interval_min: int = max(
            1, int(os.environ.get("TELEGRAM_PL_HEARTBEAT_INTERVAL_MIN", "30") or "30")
        )
        self._pl_loop_sleep_seconds: int = max(
            10, int(os.environ.get("TELEGRAM_PL_LOOP_SLEEP_SECONDS", "30") or "30")
        )
        self._last_pl_heartbeat_et: datetime | None = None
        self._last_eod_summary_date: str | None = None
        self._last_eow_summary_week: str | None = None

        # P/L threshold-triggered alert controls (proposal §Threshold-triggered alerts)
        self._pl_high_loss_pct: float = float(
            os.environ.get("TELEGRAM_HIGH_LOSS_PCT", "0.01") or "0.01"
        )
        self._pl_critical_loss_pct: float = float(
            os.environ.get("TELEGRAM_CRITICAL_LOSS_PCT", "0.02") or "0.02"
        )
        self._pl_profit_step_pct: float = float(
            os.environ.get("TELEGRAM_PROFIT_STEP_PCT", "0.01") or "0.01"
        )
        self._pl_account_nlv: float = float(
            os.environ.get("TELEGRAM_ACCOUNT_NLV", "0.0") or "0.0"
        )
        self._pl_threshold_cooldown_min: int = int(
            os.environ.get("TELEGRAM_THRESHOLD_COOLDOWN_MIN", "15") or "15"
        )
        self._pl_info_session_cap: int = int(
            os.environ.get("TELEGRAM_INFO_SESSION_CAP", "30") or "30"
        )
        self._last_high_loss_alert_et: datetime | None = None
        self._last_critical_loss_alert_et: datetime | None = None
        self._last_profit_milestone_amount: float = 0.0
        self._last_drawdown_accel_alert_et: datetime | None = None
        self._last_drawdown_accel_net_pl: float = 0.0
        self._pl_info_alert_count_today: int = 0
        self._pl_info_alert_reset_date: str | None = None

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
        stop_event = getattr(self, "_stop_event", None)
        if stop_event is None:
            stop_event = threading.Event()
            self._stop_event = stop_event
        stop_event.clear()
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name=WORKER_THREAD_NAME,
            daemon=True
        )
        self.worker_thread.start()

        # Start inbound command polling only when at least one operator user-id
        # is configured; fail-closed by design.
        if self._allowed_user_ids:
            self.command_thread = threading.Thread(
                target=self._command_poll_loop,
                name=COMMAND_POLL_THREAD_NAME,
                daemon=True,
            )
            self.command_thread.start()
            self.logger.info(
                "Telegram operator command polling enabled for %d user(s)",
                len(self._allowed_user_ids),
            )
        else:
            self.logger.warning(
                "Telegram operator command polling disabled: "
                "TELEGRAM_ALLOWED_USER_IDS not configured"
            )

        if self._pl_reporting_enabled:
            self.summary_thread = threading.Thread(
                target=self._summary_loop,
                name=SUMMARY_THREAD_NAME,
                daemon=True,
            )
            self.summary_thread.start()
            self.logger.info(
                "Telegram periodic P/L reporting enabled (heartbeat=%d min)",
                self._pl_heartbeat_interval_min,
            )
        else:
            self.logger.info("Telegram periodic P/L reporting disabled")

        # Replay previously persisted pending messages (best effort).
        self._replay_pending_messages()

        # Send startup message
        self.send_system_message("🟢 Spyder Autonomous Trader Started", priority=MessagePriority.HIGH)

        self.logger.info("Telegram bot started")

    def stop(self) -> None:
        """Stop the telegram bot worker"""
        if not self.running:
            return

        # Send shutdown message
        self.send_system_message("� Spyder Autonomous Trader Stopped", priority=MessagePriority.HIGH)

        self.running = False
        stop_event = getattr(self, "_stop_event", None)
        if stop_event is not None:
            stop_event.set()

        # Close HTTP sessions before joining so long-polling requests unblock.
        if getattr(self, "session", None) is not None:
            self.session.close()
        command_session = getattr(self, "command_session", None)
        if command_session is not None and command_session is not self.session:
            command_session.close()

        shutdown_budget_s = float(os.getenv("SPYDER_TELEGRAM_STOP_TIMEOUT_S", "2.5"))
        deadline = time.monotonic() + max(0.1, shutdown_budget_s)

        for thread_name in ("worker_thread", "command_thread", "summary_thread"):
            thread = getattr(self, thread_name, None)
            if thread is None:
                continue
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0.0:
                break
            thread.join(timeout=remaining)

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
                sent = self._send_message_now(message)
                if not sent:
                    self._handle_failed_delivery(message, "immediate_send_failed")
                return sent
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

        message += f"\n{self.emojis['time']} <i>{datetime.now(_ET_TZ).strftime('%I:%M %p ET')}</i>"

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

{self.emojis['time']} <i>{datetime.now(_ET_TZ).strftime('%I:%M %p ET')}</i>
"""

        return self.send_message(
            message,
            priority=MessagePriority.HIGH,
            message_type=MessageType.TRADE_CLOSE
        )

    def send_compact_trade_message(
        self,
        event_type: str,
        strategy: str,
        symbol: str,
        pnl: float = 0.0,
        pnl_percent: float = 0.0,
    ) -> bool:
        """Send a compact single-line trade notification for live event handlers."""
        time_str = datetime.now(_ET_TZ).strftime("%I:%M %p ET")
        if event_type == "opened":
            text = f"🎯 <b>{strategy}</b> executed · {symbol}  <i>{time_str}</i>"
        else:
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            pct_part = f" ({pnl_percent:+.1f}%)" if pnl_percent else ""
            icon = "💰" if pnl >= 0 else "📉"
            text = f"{icon} <b>{strategy}</b> closed · P&L: <b>{pnl_str}</b>{pct_part}  <i>{time_str}</i>"
        msg_type = MessageType.TRADE_OPEN if event_type == "opened" else MessageType.TRADE_CLOSE
        return self.send_message(text, priority=MessagePriority.HIGH, message_type=msg_type)

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

{self.emojis['time']} <i>{datetime.now(_ET_TZ).strftime('%I:%M %p ET')}</i>
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

{self.emojis['time']} <i>{datetime.now(_ET_TZ).strftime('%I:%M %p ET')}</i>
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

{self.emojis['time']} <i>{datetime.now(_ET_TZ).strftime('%I:%M %p ET')}</i>
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
        order_id = order.get('id', f"ord_{int(datetime.now(UTC).timestamp())}")
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
            f"\U0001f550 <i>{datetime.now(_ET_TZ).strftime('%H:%M:%S ET')}</i>"
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
                self.stats.last_sent = datetime.now(UTC)

            return True

        except requests.exceptions.ConnectionError as ce:
            # TCP-level reset (ECONNRESET 104) — Telegram closes idle keep-alive
            # connections after ~5 minutes.  Recreate the session so the retry
            # uses a fresh connection rather than the stale pooled socket.
            self.stats.messages_failed += 1
            self.stats.last_error = str(ce)
            self.stats.total_errors += 1
            if message.retry_count < MAX_RETRIES:
                message.retry_count += 1
                try:
                    self.session.close()
                except Exception:
                    pass
                self.session = self._create_session()
                time.sleep(RETRY_DELAY * message.retry_count)
                return self._send_message_now(message)
            self.logger.error("Failed to send message: %s", ce)
            return False

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

    def _handle_failed_delivery(self, message: TelegramMessage, reason: str) -> None:
        """Persist failed delivery and escalate summary failures."""
        self._persist_pending_message(message, reason=reason)

        # Requirement: raise HIGH alert when EOD/EOW summary delivery fails.
        if message.message_type == MessageType.SUMMARY:
            text = message.content or ""
            is_eod = "EOD P/L SUMMARY" in text
            is_eow = "END-OF-WEEK P/L SUMMARY" in text
            if is_eod or is_eow:
                summary_type = "EOD" if is_eod else "EOW"
                self.send_alert(
                    title=f"Telegram {summary_type} Summary Delivery Failure",
                    message=(
                        f"Delivery failed after retry budget; message persisted for replay. "
                        f"Reason: {reason}"
                    ),
                    severity="warning",
                )

    def _serialize_message(self, message: TelegramMessage, reason: str) -> dict[str, Any]:
        """Serialize TelegramMessage for durable queue storage."""
        return {
            "reason": reason,
            "content": message.content,
            "chat_id": message.chat_id,
            "priority": message.priority.name,
            "message_type": message.message_type.name,
            "parse_mode": message.parse_mode,
            "disable_notification": message.disable_notification,
            "reply_markup": message.reply_markup,
            "retry_count": message.retry_count,
            "timestamp": message.timestamp.isoformat(),
            "persisted_at": datetime.now(UTC).isoformat(),
        }

    def _deserialize_message(self, payload: dict[str, Any]) -> TelegramMessage:
        """Deserialize durable queue payload back into TelegramMessage."""
        priority_name = str(payload.get("priority", MessagePriority.NORMAL.name))
        msg_type_name = str(payload.get("message_type", MessageType.SYSTEM.name))
        try:
            priority = MessagePriority[priority_name]
        except Exception:
            priority = MessagePriority.NORMAL
        try:
            msg_type = MessageType[msg_type_name]
        except Exception:
            msg_type = MessageType.SYSTEM

        ts_raw = payload.get("timestamp")
        ts_val = datetime.now(UTC)
        if isinstance(ts_raw, str):
            try:
                ts_val = datetime.fromisoformat(ts_raw)
            except Exception:
                ts_val = datetime.now(UTC)

        return TelegramMessage(
            content=str(payload.get("content", "")),
            chat_id=str(payload.get("chat_id", self.default_chat_id)),
            priority=priority,
            message_type=msg_type,
            parse_mode=str(payload.get("parse_mode", "HTML")),
            disable_notification=bool(payload.get("disable_notification", False)),
            reply_markup=payload.get("reply_markup"),
            retry_count=int(payload.get("retry_count", 0) or 0),
            timestamp=ts_val,
        )

    def _persist_pending_message(self, message: TelegramMessage, reason: str) -> None:
        """Append failed message to durable pending queue file (JSONL)."""
        try:
            self._pending_queue_file.parent.mkdir(parents=True, exist_ok=True)
            row = self._serialize_message(message, reason=reason)
            with self._pending_file_lock, self._pending_queue_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=True) + "\n")
            self._enforce_pending_retention()
            self.logger.warning("Persisted failed Telegram message for replay: reason=%s", reason)
        except Exception as exc:
            self.logger.error("Failed to persist pending Telegram message: %s", exc)

    def _pending_row_is_expired(self, payload: dict[str, Any], now_utc: datetime) -> bool:
        """Return True when pending row exceeds configured retention age."""
        ts_raw = payload.get("persisted_at") or payload.get("timestamp")
        if not isinstance(ts_raw, str):
            return True
        try:
            ts = datetime.fromisoformat(ts_raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            return (now_utc - ts).total_seconds() > self._pending_max_age_hours * 3600
        except Exception:
            return True

    def _enforce_pending_retention(self) -> None:
        """Prune pending queue by age/row limits and remove invalid rows."""
        try:
            if not self._pending_queue_file.exists():
                return

            with self._pending_file_lock:
                rows = self._pending_queue_file.read_text(encoding="utf-8").splitlines()

                if not rows:
                    self._pending_queue_file.unlink(missing_ok=True)
                    return

                now_utc = datetime.now(UTC)
                kept: list[str] = []
                dropped = 0
                for line in rows:
                    if not line.strip():
                        dropped += 1
                        continue
                    try:
                        payload = json.loads(line)
                    except Exception:
                        dropped += 1
                        continue

                    if self._pending_row_is_expired(payload, now_utc):
                        dropped += 1
                        continue

                    kept.append(line)

                if len(kept) > self._pending_max_rows:
                    overflow = len(kept) - self._pending_max_rows
                    dropped += overflow
                    kept = kept[-self._pending_max_rows :]

                if kept:
                    self._pending_queue_file.write_text("\n".join(kept) + "\n", encoding="utf-8")
                else:
                    self._pending_queue_file.unlink(missing_ok=True)

            if dropped > 0:
                self.logger.info("Pruned Telegram pending queue rows=%d", dropped)
        except Exception as exc:
            self.logger.error("Failed enforcing Telegram pending retention: %s", exc)

    def _replay_pending_messages(self, limit: int | None = None) -> None:
        """Replay durable pending queue messages and keep unresolved rows."""
        try:
            self._enforce_pending_retention()
            if not self._pending_queue_file.exists():
                return

            replay_limit = self._pending_replay_limit if limit is None else max(1, int(limit))

            with self._pending_file_lock:
                rows = self._pending_queue_file.read_text(encoding="utf-8").splitlines()

            if not rows:
                return

            remaining: list[str] = []
            replayed = 0
            failed = 0

            for line in rows:
                if replayed >= replay_limit:
                    remaining.append(line)
                    continue

                try:
                    payload = json.loads(line)
                    msg = self._deserialize_message(payload)
                    if self._send_message_now(msg):
                        replayed += 1
                    else:
                        failed += 1
                        remaining.append(line)
                except Exception:
                    failed += 1
                    remaining.append(line)

            with self._pending_file_lock:
                if remaining:
                    self._pending_queue_file.write_text("\n".join(remaining) + "\n", encoding="utf-8")
                else:
                    self._pending_queue_file.unlink(missing_ok=True)

            self.logger.info(
                "Telegram pending replay completed: replayed=%d failed=%d remaining=%d",
                replayed,
                failed,
                len(remaining),
            )
            self._enforce_pending_retention()
        except Exception as exc:
            self.logger.error("Telegram pending replay failed: %s", exc)

    def _worker_loop(self) -> None:
        """Worker thread for sending queued messages"""
        while self.running:
            try:
                # Get message from queue (timeout allows graceful shutdown)
                priority, message = self.message_queue.get(timeout=1)

                # Send message
                sent = self._send_message_now(message)
                if not sent:
                    self._handle_failed_delivery(message, "queued_send_failed")

                # Mark task done
                self.message_queue.task_done()

            except Empty:
                continue
            except Exception as e:
                self.logger.error("Worker error: %s", e)

    @staticmethod
    def _now_et() -> datetime:
        """Current US/Eastern time with timezone awareness."""
        try:
            return datetime.now(ZoneInfo("America/New_York"))
        except Exception:
            return datetime.now(UTC)

    @staticmethod
    def _coerce_float(value: Any, default: float = 0.0) -> float:
        """Safely coerce arbitrary values to float."""
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _summary_loop(self) -> None:
        """Periodic loop for intraday heartbeat and end-of-day P/L summaries."""
        stop_event = getattr(self, "_stop_event", None)
        while self.running and not (stop_event is not None and stop_event.is_set()):
            try:
                self._run_periodic_pl_notifications_once()
            except Exception as exc:
                self.logger.error("Telegram periodic P/L loop error: %s", exc)
            if stop_event is not None:
                if stop_event.wait(self._pl_loop_sleep_seconds):
                    break
            else:
                time.sleep(self._pl_loop_sleep_seconds)

    def _run_periodic_pl_notifications_once(self, now_et: datetime | None = None) -> None:
        """Single periodic reporting tick (test-friendly, no internal sleeping)."""
        now = now_et or self._now_et()
        if now.weekday() >= 5:
            return

        current_time = now.time()
        heartbeat_start = now.replace(hour=9, minute=30, second=0, microsecond=0).time()
        heartbeat_end = now.replace(hour=16, minute=15, second=0, microsecond=0).time()

        if heartbeat_start <= current_time < heartbeat_end:
            snapshot = self._build_pl_snapshot(now)
            # Threshold-triggered alerts run every tick during the session window.
            self._check_pl_threshold_alerts(now, snapshot)
            if self._should_send_heartbeat(now):
                self.send_message(
                    self._format_pl_heartbeat_message(snapshot),
                    priority=MessagePriority.NORMAL,
                    message_type=MessageType.SUMMARY,
                )
                self._last_pl_heartbeat_et = now
            return

        eod_window_start = now.replace(hour=16, minute=16, second=0, microsecond=0).time()
        eod_window_end = now.replace(hour=16, minute=20, second=59, microsecond=0).time()
        date_key = now.strftime("%Y-%m-%d")

        if eod_window_start <= current_time <= eod_window_end and self._last_eod_summary_date != date_key:
            snapshot = self._build_pl_snapshot(now)
            self.send_message(
                self._format_eod_summary_message(snapshot),
                priority=MessagePriority.HIGH,
                message_type=MessageType.SUMMARY,
            )
            self._last_eod_summary_date = date_key

        # EOW summary — Friday 16:20–17:00 ET (primary window)
        eow_start = now.replace(hour=16, minute=20, second=0, microsecond=0).time()
        eow_end = now.replace(hour=17, minute=0, second=0, microsecond=0).time()
        if now.weekday() == 4 and eow_start <= current_time <= eow_end:
            week_key = now.strftime("%G-W%V")
            if self._last_eow_summary_week != week_key:
                self.send_eow_summary(now, week_key)

    def _should_send_heartbeat(self, now_et: datetime) -> bool:
        """Return True when the heartbeat interval has elapsed."""
        if self._last_pl_heartbeat_et is None:
            return True
        elapsed = (now_et - self._last_pl_heartbeat_et).total_seconds()
        return elapsed >= self._pl_heartbeat_interval_min * 60

    def _build_pl_snapshot(self, now_et: datetime) -> dict[str, Any]:
        """Build best-effort intraday P/L snapshot from runtime state."""
        supervisor = get_session_supervisor()
        session_running = bool(supervisor and getattr(supervisor, "is_running", False))
        broker = getattr(supervisor, "broker", None) if supervisor is not None else None
        risk = getattr(supervisor, "risk", None) if supervisor is not None else None

        account_id = "N/A"
        realized_pl = 0.0
        unrealized_pl = 0.0
        positions_count = 0
        top_winner = ("N/A", 0.0)
        top_loser = ("N/A", 0.0)

        try:
            if broker is not None and hasattr(broker, "get_account"):
                acct = broker.get_account() or {}
                acct_node = acct.get("account", {}) if isinstance(acct, dict) else {}
                account_id = str(acct_node.get("account_number") or acct_node.get("account_id") or "N/A")
                realized_pl = self._coerce_float(
                    acct_node.get("close_pl", acct_node.get("realized_pl", realized_pl)),
                    realized_pl,
                )
        except Exception as exc:
            self.logger.debug("P/L snapshot account fetch failed: %s", exc)

        if risk is not None:
            realized_pl = self._coerce_float(
                getattr(risk, "daily_pnl", None),
                realized_pl,
            )

        positions: list[dict[str, Any]] = []
        try:
            if broker is not None and hasattr(broker, "get_positions"):
                pos_resp = broker.get_positions()
                if isinstance(pos_resp, list):
                    raw = pos_resp
                else:
                    raw = (pos_resp.get("positions") or {}).get("position", [])
                    if isinstance(raw, dict):
                        raw = [raw]
                for pos in raw:
                    if not isinstance(pos, dict):
                        continue
                    qty = self._coerce_float(pos.get("quantity", 0.0), 0.0)
                    if qty == 0:
                        continue
                    symbol = str(pos.get("symbol") or "UNKNOWN")
                    open_pl = self._coerce_float(
                        pos.get("unrealized_pl", pos.get("unrealized_pnl", pos.get("open_pl", 0.0))),
                        0.0,
                    )
                    positions.append({"symbol": symbol, "open_pl": open_pl})
                positions_count = len(positions)
        except Exception as exc:
            self.logger.debug("P/L snapshot positions fetch failed: %s", exc)

        if positions:
            unrealized_pl = sum(p["open_pl"] for p in positions)
            winner = max(positions, key=lambda p: p["open_pl"])
            loser = min(positions, key=lambda p: p["open_pl"])
            top_winner = (winner["symbol"], winner["open_pl"])
            top_loser = (loser["symbol"], loser["open_pl"])

        net_pl = realized_pl + unrealized_pl

        risk_state = "NORMAL"
        if not session_running:
            risk_state = "WARNING"
        if net_pl <= -1000:
            risk_state = "CRITICAL"

        return {
            "timestamp_et": now_et,
            "mode": os.environ.get("TRADING_MODE", "paper").upper(),
            "account_id": account_id,
            "session_running": session_running,
            "realized_pl_day": realized_pl,
            "unrealized_pl": unrealized_pl,
            "net_pl_day": net_pl,
            "open_positions": positions_count,
            "top_winner": top_winner,
            "top_loser": top_loser,
            "risk_state": risk_state,
        }

    def _format_pl_heartbeat_message(self, snapshot: dict[str, Any]) -> str:
        """Format periodic intraday heartbeat P/L Telegram message."""
        ts = snapshot["timestamp_et"].strftime("%Y-%m-%d %H:%M")
        winner_symbol, winner_pl = snapshot["top_winner"]
        loser_symbol, loser_pl = snapshot["top_loser"]
        return (
            "📈 <b>P/L HEARTBEAT</b>\n"
            f"Time (ET): {ts}\n"
            f"Mode/Acct: {snapshot['mode']} / {snapshot['account_id']}\n"
            f"Session Running: {'YES' if snapshot['session_running'] else 'NO'}\n"
            f"Realized P/L (Day): ${snapshot['realized_pl_day']:+.2f}\n"
            f"Unrealized P/L: ${snapshot['unrealized_pl']:+.2f}\n"
            f"Net P/L (Day): ${snapshot['net_pl_day']:+.2f}\n"
            f"Open Positions: {snapshot['open_positions']}\n"
            f"Top Winner: {winner_symbol} ${winner_pl:+.2f}\n"
            f"Top Loser: {loser_symbol} ${loser_pl:+.2f}\n"
            f"Risk State: {snapshot['risk_state']}"
        )

    def _format_eod_summary_message(self, snapshot: dict[str, Any]) -> str:
        """Format end-of-day summary Telegram message."""
        ts = snapshot["timestamp_et"].strftime("%Y-%m-%d")
        return (
            "📅 <b>EOD P/L SUMMARY</b>\n"
            f"Date (ET): {ts}\n"
            f"Mode/Acct: {snapshot['mode']} / {snapshot['account_id']}\n"
            f"Realized P/L (Day): ${snapshot['realized_pl_day']:+.2f}\n"
            f"Unrealized Carry: ${snapshot['unrealized_pl']:+.2f}\n"
            f"Net P/L (Day): ${snapshot['net_pl_day']:+.2f}\n"
            f"Open Positions: {snapshot['open_positions']}\n"
            f"Risk State: {snapshot['risk_state']}"
        )

    # ==========================================================================
    # P/L THRESHOLD ALERTS
    # ==========================================================================

    def _get_nlv(self, snapshot: dict[str, Any]) -> float:
        """Return best-effort NLV for threshold calculations.

        Uses env-configured NLV first; falls back to deriving from the
        snapshot balance when available.
        """
        if self._pl_account_nlv > 0:
            return self._pl_account_nlv
        # Attempt to infer from session supervisor account balance
        try:
            from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import (
                get_session_supervisor,
            )
            supervisor = get_session_supervisor()
            broker = getattr(supervisor, "broker", None) if supervisor else None
            if broker and hasattr(broker, "get_account"):
                acct = broker.get_account() or {}
                node = acct.get("account", {}) if isinstance(acct, dict) else {}
                total_equity = self._coerce_float(
                    node.get("total_equity", node.get("net_value", 0.0)), 0.0
                )
                if total_equity > 0:
                    return total_equity
        except Exception:
            pass
        return 0.0

    def _info_alert_allowed(self, now_et: datetime) -> bool:
        """Return True when session INFO alert cap has not been reached."""
        date_key = now_et.strftime("%Y-%m-%d")
        if self._pl_info_alert_reset_date != date_key:
            self._pl_info_alert_count_today = 0
            self._pl_info_alert_reset_date = date_key
        return self._pl_info_alert_count_today < self._pl_info_session_cap

    def _cooldown_elapsed(
        self, last_alert_et: "datetime | None", now_et: datetime
    ) -> bool:
        """Return True when the per-trigger cooldown period has elapsed."""
        if last_alert_et is None:
            return True
        return (now_et - last_alert_et).total_seconds() >= self._pl_threshold_cooldown_min * 60

    def _check_pl_threshold_alerts(
        self, now_et: datetime, snapshot: dict[str, Any]
    ) -> None:
        """Evaluate P/L thresholds and dispatch Telegram alerts when breached.

        Checks (in priority order):
          1. Critical daily loss (≥ 2 % NLV) — no cap, 15-min cooldown
          2. High daily loss (≥ 1 % NLV) — INFO cap, 15-min cooldown
          3. Drawdown acceleration (≥ 0.35 % NLV drop in 15 min) — INFO cap
          4. Profit milestones (every 1 % NLV step above start) — INFO cap
        """
        try:
            net_pl = self._coerce_float(snapshot.get("net_pl_day"), 0.0)
            nlv = self._get_nlv(snapshot)
            if nlv <= 0:
                return  # cannot compute percentage thresholds without NLV

            high_loss_threshold = -nlv * self._pl_high_loss_pct
            critical_loss_threshold = -nlv * self._pl_critical_loss_pct
            profit_step = nlv * self._pl_profit_step_pct

            import uuid as _uuid

            # ── 1. Critical loss ──────────────────────────────────────────────
            if net_pl <= critical_loss_threshold and self._cooldown_elapsed(
                self._last_critical_loss_alert_et, now_et
            ):
                cid = f"thresh-crit-{_uuid.uuid4().hex[:8]}"
                self.send_message(
                    self._format_pl_threshold_alert(
                        "CRITICAL_DAILY_LOSS",
                        snapshot,
                        critical_loss_threshold,
                        cid,
                    ),
                    priority=MessagePriority.CRITICAL,
                    message_type=MessageType.ALERT,
                )
                self._last_critical_loss_alert_et = now_et
                self.logger.warning("P/L threshold CRITICAL_DAILY_LOSS fired: net_pl=%.2f", net_pl)
                return  # critical supersedes lower-severity triggers this tick

            # ── 2. High loss ──────────────────────────────────────────────────
            if (
                net_pl <= high_loss_threshold
                and self._cooldown_elapsed(self._last_high_loss_alert_et, now_et)
                and self._info_alert_allowed(now_et)
            ):
                cid = f"thresh-loss-{_uuid.uuid4().hex[:8]}"
                self.send_message(
                    self._format_pl_threshold_alert(
                        "HIGH_DAILY_LOSS",
                        snapshot,
                        high_loss_threshold,
                        cid,
                    ),
                    priority=MessagePriority.HIGH,
                    message_type=MessageType.ALERT,
                )
                self._last_high_loss_alert_et = now_et
                self._pl_info_alert_count_today += 1
                self.logger.info("P/L threshold HIGH_DAILY_LOSS fired: net_pl=%.2f", net_pl)

            # ── 3. Drawdown acceleration ──────────────────────────────────────
            if (
                self._last_drawdown_accel_alert_et is not None
                and self._info_alert_allowed(now_et)
                and self._cooldown_elapsed(self._last_drawdown_accel_alert_et, now_et)
            ):
                drop_since = self._last_drawdown_accel_net_pl - net_pl
                accel_threshold = nlv * 0.0035  # 0.35 % NLV in cooldown window
                if drop_since >= accel_threshold:
                    cid = f"thresh-accel-{_uuid.uuid4().hex[:8]}"
                    self.send_message(
                        self._format_pl_threshold_alert(
                            "DRAWDOWN_ACCELERATION",
                            snapshot,
                            accel_threshold,
                            cid,
                        ),
                        priority=MessagePriority.HIGH,
                        message_type=MessageType.ALERT,
                    )
                    self._last_drawdown_accel_alert_et = now_et
                    self._last_drawdown_accel_net_pl = net_pl
                    self._pl_info_alert_count_today += 1
                    self.logger.info(
                        "P/L threshold DRAWDOWN_ACCELERATION fired: drop=%.2f", drop_since
                    )
            else:
                # Initialise / update acceleration baseline each cooldown window
                if self._last_drawdown_accel_alert_et is None:
                    self._last_drawdown_accel_alert_et = now_et
                    self._last_drawdown_accel_net_pl = net_pl

            # ── 4. Profit milestones ──────────────────────────────────────────
            if profit_step > 0 and net_pl > 0 and self._info_alert_allowed(now_et):
                milestone = (net_pl // profit_step) * profit_step
                if milestone > self._last_profit_milestone_amount:
                    cid = f"thresh-profit-{_uuid.uuid4().hex[:8]}"
                    self.send_message(
                        self._format_pl_threshold_alert(
                            "PROFIT_MILESTONE",
                            snapshot,
                            milestone,
                            cid,
                        ),
                        priority=MessagePriority.NORMAL,
                        message_type=MessageType.SUMMARY,
                    )
                    self._last_profit_milestone_amount = milestone
                    self._pl_info_alert_count_today += 1
                    self.logger.info(
                        "P/L threshold PROFIT_MILESTONE fired: milestone=%.2f", milestone
                    )

        except Exception as exc:
            self.logger.error("_check_pl_threshold_alerts error: %s", exc)

    def _format_pl_threshold_alert(
        self,
        trigger_type: str,
        snapshot: dict[str, Any],
        threshold: float,
        correlation_id: str,
    ) -> str:
        """Format a P/L threshold-triggered Telegram alert message."""
        ts = snapshot["timestamp_et"].strftime("%Y-%m-%d %H:%M")
        net_pl = self._coerce_float(snapshot.get("net_pl_day"), 0.0)
        realized = self._coerce_float(snapshot.get("realized_pl_day"), 0.0)
        unrealized = self._coerce_float(snapshot.get("unrealized_pl"), 0.0)

        label_map = {
            "CRITICAL_DAILY_LOSS": ("🚨", "CRITICAL: DAILY LOSS LIMIT BREACH"),
            "HIGH_DAILY_LOSS": ("⚠️", "WARNING: HIGH DAILY LOSS"),
            "DRAWDOWN_ACCELERATION": ("📉", "ALERT: DRAWDOWN ACCELERATION"),
            "PROFIT_MILESTONE": ("🎯", "INFO: PROFIT MILESTONE REACHED"),
        }
        icon, title = label_map.get(trigger_type, ("🔔", trigger_type))

        return (
            f"{icon} <b>{title}</b>\n"
            f"Time (ET): {ts}\n"
            f"Mode/Acct: {snapshot['mode']} / {snapshot['account_id']}\n"
            f"Net P/L (Day): ${net_pl:+.2f}\n"
            f"Realized: ${realized:+.2f}  |  Unrealized: ${unrealized:+.2f}\n"
            f"Threshold: ${threshold:+.2f}\n"
            f"Open Positions: {snapshot.get('open_positions', 0)}\n"
            f"Risk State: {snapshot.get('risk_state', 'UNKNOWN')}\n"
            f"Correlation: {correlation_id}"
        )

    # ==========================================================================
    # EOW SUMMARY
    # ==========================================================================

    def send_eow_summary(self, now_et: datetime, week_key: str) -> None:
        """Build and dispatch the weekly P/L Telegram summary for *week_key*.

        Saves `market_data/weekly/weekly_pnl_summary_{week_key}.json` atomically
        and deduplicates with `_last_eow_summary_week`.
        """
        try:
            snapshot = self._build_weekly_pl_snapshot(now_et)
            self.send_message(
                self._format_eow_summary_message(snapshot, week_key),
                priority=MessagePriority.HIGH,
                message_type=MessageType.SUMMARY,
            )
            self._last_eow_summary_week = week_key
            self._save_weekly_pnl_artifact(snapshot, week_key)
            self.logger.info("EOW P/L summary dispatched: week=%s", week_key)
        except Exception as exc:
            self.logger.error("send_eow_summary error: %s", exc)

    def _build_weekly_pl_snapshot(self, now_et: datetime) -> dict[str, Any]:
        """Aggregate weekly P/L data from daily EOD review artifacts.

        Reads up to 5 `market_data/eod_reviews/eod_{date}.json` files for the
        current ISO week (Mon–Fri) and aggregates totals.
        """
        import json as _json
        from pathlib import Path as _Path

        # Identify Mon–Fri dates for the current ISO week.
        iso_cal = now_et.isocalendar()
        week_start = now_et.date() - __import__("datetime").timedelta(
            days=now_et.weekday()
        )
        week_dates = [week_start + __import__("datetime").timedelta(days=i) for i in range(5)]

        project_root = _Path(__file__).resolve().parent.parent.parent
        eod_dir = project_root / "market_data" / "eod_reviews"

        total_pl = 0.0
        trade_count = 0
        win_count = 0
        max_drawdown = 0.0
        best_day = ("N/A", 0.0)
        worst_day = ("N/A", 0.0)
        days_with_data = 0

        for d in week_dates:
            date_str = d.strftime("%Y-%m-%d")
            eod_file = eod_dir / f"eod_{date_str}.json"
            if not eod_file.exists():
                continue
            try:
                data = _json.loads(eod_file.read_text(encoding="utf-8"))
                day_pl = float(data.get("net_pl_day", data.get("pnl", 0.0)) or 0.0)
                total_pl += day_pl
                trade_count += int(data.get("trade_count", 0) or 0)
                win_count += int(data.get("win_count", 0) or 0)
                day_dd = float(data.get("max_drawdown", 0.0) or 0.0)
                if abs(day_dd) > abs(max_drawdown):
                    max_drawdown = day_dd
                if days_with_data == 0 or day_pl > best_day[1]:
                    best_day = (date_str, day_pl)
                if days_with_data == 0 or day_pl < worst_day[1]:
                    worst_day = (date_str, day_pl)
                days_with_data += 1
            except Exception as exc:
                self.logger.debug("EOW: failed to read %s: %s", eod_file, exc)

        win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0.0
        nlv = self._pl_account_nlv or 0.0
        net_return_pct = (total_pl / nlv * 100) if nlv > 0 else 0.0

        return {
            "timestamp_et": now_et,
            "iso_week": f"{iso_cal.year}-W{iso_cal.week:02d}",
            "mode": os.environ.get("TRADING_MODE", "paper").upper(),
            "weekly_pl": total_pl,
            "net_return_pct": net_return_pct,
            "trade_count": trade_count,
            "win_rate": win_rate,
            "max_drawdown": max_drawdown,
            "best_day": best_day,
            "worst_day": worst_day,
            "days_traded": days_with_data,
        }

    def _format_eow_summary_message(
        self, snapshot: dict[str, Any], week_key: str
    ) -> str:
        """Format the end-of-week P/L Telegram summary message."""
        best_d, best_pl = snapshot["best_day"]
        worst_d, worst_pl = snapshot["worst_day"]
        return (
            "📆 <b>END-OF-WEEK P/L SUMMARY</b>\n"
            f"Week: {week_key}  |  Mode: {snapshot['mode']}\n"
            f"Weekly Net P/L: ${snapshot['weekly_pl']:+.2f} "
            f"({snapshot['net_return_pct']:+.2f}% NLV)\n"
            f"Days Traded: {snapshot['days_traded']}\n"
            f"Trades: {snapshot['trade_count']}  |  "
            f"Win Rate: {snapshot['win_rate']:.1f}%\n"
            f"Max Weekly Drawdown: ${snapshot['max_drawdown']:.2f}\n"
            f"Best Day:  {best_d} ${best_pl:+.2f}\n"
            f"Worst Day: {worst_d} ${worst_pl:+.2f}\n"
            f"Generated: {snapshot['timestamp_et'].strftime('%Y-%m-%d %H:%M ET')}"
        )

    def _save_weekly_pnl_artifact(
        self, snapshot: dict[str, Any], week_key: str
    ) -> None:
        """Atomically save the weekly P/L summary JSON artifact."""
        import json as _json
        import tempfile
        from pathlib import Path as _Path

        project_root = _Path(__file__).resolve().parent.parent.parent
        out_dir = project_root / "market_data" / "weekly"
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"weekly_pnl_summary_{week_key}.json"
            payload = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in snapshot.items()}
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=out_dir,
                suffix=".tmp",
                delete=False,
            ) as tmp:
                _json.dump(payload, tmp, indent=2)
                tmp_path = _Path(tmp.name)
            tmp_path.replace(out_path)
            self.logger.info("Weekly P/L artifact saved: %s", out_path)
        except Exception as exc:
            self.logger.error("Failed to save weekly P/L artifact: %s", exc)

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
    # INBOUND COMMAND HANDLING
    # ==========================================================================
    def _load_allowed_user_ids(self) -> set[int]:
        """Load authorized Telegram operator user IDs from env."""
        env_key = "TELEGRAM_ALLOWED_USER_IDS"
        raw = os.environ.get(env_key, "").strip()
        if not raw:
            # Backward-compatible alias used by some runbooks/docs.
            env_key = "TELEGRAM_APPROVED_USER_IDS"
            raw = os.environ.get(env_key, "").strip()
        if not raw:
            return set()

        ids: set[int] = set()
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                ids.add(int(token))
            except ValueError:
                self.logger.warning(
                    "Ignoring invalid %s token: %s",
                    env_key,
                    token,
                )
        if ids:
            self.logger.info("Loaded %d authorized Telegram user IDs from %s", len(ids), env_key)
        return ids

    def _command_poll_loop(self) -> None:
        """Long-poll Telegram for text commands from authorized operators."""
        stop_event = getattr(self, "_stop_event", None)
        session = getattr(self, "command_session", None) or self.session
        poll_timeout = max(
            1,
            int(getattr(self, "_command_poll_timeout_seconds", 5) or 5),
        )
        request_timeout = max(
            poll_timeout + 1,
            int(
                getattr(
                    self,
                    "_command_poll_request_timeout_seconds",
                    poll_timeout + 1,
                )
                or (poll_timeout + 1)
            ),
        )
        updates_url = TELEGRAM_API_URL.format(token=self.bot_token, method="getUpdates")

        # Advance offset to ignore stale backlog when bot starts.
        try:
            init_resp = session.get(
                updates_url,
                params={"limit": 1, "timeout": 0},
                timeout=CONNECTION_TIMEOUT,
            )
            if init_resp.ok:
                prior = init_resp.json().get("result", [])
                if prior:
                    self._update_offset = prior[-1]["update_id"] + 1
        except Exception as exc:
            self.logger.debug("Telegram command poll init offset failed: %s", exc)

        while self.running and not (stop_event is not None and stop_event.is_set()):
            try:
                params = {
                    "offset": self._update_offset,
                    "timeout": poll_timeout,
                    "allowed_updates": ["message"],
                }
                resp = session.get(
                    updates_url,
                    params=params,
                    timeout=request_timeout,
                )
                if not resp.ok:
                    if stop_event is not None:
                        if stop_event.wait(1):
                            break
                    else:
                        time.sleep(1)
                    continue

                for update in resp.json().get("result", []):
                    self._update_offset = update["update_id"] + 1
                    self._handle_inbound_update(update)

            except Exception as exc:
                self.logger.error("Telegram command poll error: %s", exc)
                if stop_event is not None:
                    if stop_event.wait(1):
                        break
                else:
                    time.sleep(1)

    def _handle_inbound_update(self, update: dict[str, Any]) -> None:
        """Handle a single Telegram update payload."""
        message = update.get("message") or {}
        text = str(message.get("text", "")).strip()
        if not text.startswith("/"):
            return

        from_user = message.get("from") or {}
        user_id = from_user.get("id")
        username = from_user.get("username", "unknown")
        chat_id = str((message.get("chat") or {}).get("id", self.default_chat_id))
        parts = text.split()
        command = parts[0].lower()
        correlation_id = f"tgcmd-{update.get('update_id', 'na')}-{uuid.uuid4().hex[:6]}"

        if not isinstance(user_id, int):
            return

        if user_id not in self._allowed_user_ids:
            self.logger.warning(
                "Unauthorized Telegram command rejected: cmd=%s user_id=%s",
                command,
                user_id,
            )
            self.send_message(
                f"⛔ Unauthorized operator command.\nCorrelation: {correlation_id}",
                chat_id=chat_id,
                priority=MessagePriority.HIGH,
                message_type=MessageType.ALERT,
            )
            self._append_command_audit(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "correlation_id": correlation_id,
                    "command": command,
                    "user_id": user_id,
                    "username": username,
                    "authorized": False,
                    "result": "rejected",
                }
            )
            return

        if command == "/confirm":
            self._handle_confirm_command(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                args=parts[1:],
                correlation_id=correlation_id,
            )
            return

        if command == "/status":
            self._handle_status_command(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                correlation_id=correlation_id,
            )
            return

        if command == "/halt":
            self._request_confirmation(
                chat_id,
                user_id,
                username,
                action="halt",
                correlation_id=correlation_id,
            )
            return

        if command == "/flatten":
            self._request_confirmation(
                chat_id,
                user_id,
                username,
                action="flatten",
                correlation_id=correlation_id,
            )
            return

        if command == "/resume":
            self._request_confirmation(
                chat_id,
                user_id,
                username,
                action="resume",
                correlation_id=correlation_id,
            )
            return

        if command == "/help":
            self.send_message(
                "Available commands: /status, /halt, /flatten, /resume, /confirm, /help",
                chat_id=chat_id,
                priority=MessagePriority.NORMAL,
                message_type=MessageType.SYSTEM,
            )
            self._append_command_audit(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "correlation_id": correlation_id,
                    "command": "/help",
                    "user_id": user_id,
                    "username": username,
                    "authorized": True,
                    "result": "ok",
                }
            )
            return

        self.send_message(
            f"Unknown command: {command}. Use /help.",
            chat_id=chat_id,
            priority=MessagePriority.NORMAL,
            message_type=MessageType.SYSTEM,
        )

    def _handle_status_command(
        self,
        chat_id: str,
        user_id: int,
        username: str,
        correlation_id: str,
    ) -> None:
        """Respond with bot and halt-state status."""
        kill_lock = Path.home() / ".spyder_kill_lock"
        kill_lock_active = kill_lock.exists()
        bot_stats = self.get_stats()
        failed_gates = self._resume_preflight_failed_gates()
        supervisor = get_session_supervisor()

        text = (
            "📟 <b>SPYDER STATUS</b>\n\n"
            f"Bot Running: {'YES' if bot_stats.get('is_running') else 'NO'}\n"
            f"Session Running: {'YES' if bool(supervisor and getattr(supervisor, 'is_running', False)) else 'NO'}\n"
            f"Queue Size: {bot_stats.get('queue_size', 0)}\n"
            f"Messages Sent: {bot_stats.get('messages_sent', 0)}\n"
            f"Kill Lock: {'ACTIVE' if kill_lock_active else 'INACTIVE'}\n"
            f"Resume Dual Approval: {'ON' if self._resume_dual_approval else 'OFF'}\n"
            f"Resume Failed Gates: {', '.join(failed_gates) if failed_gates else 'none'}\n"
            f"Checked At (ET): {datetime.now(_ET_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Correlation: {correlation_id}"
        )

        self.send_message(
            text,
            chat_id=chat_id,
            priority=MessagePriority.NORMAL,
            message_type=MessageType.SYSTEM,
        )
        self._append_command_audit(
            {
                "ts": datetime.now(UTC).isoformat(),
                "correlation_id": correlation_id,
                "command": "/status",
                "user_id": user_id,
                "username": username,
                "authorized": True,
                "result": "ok",
                "kill_lock_active": kill_lock_active,
                "resume_failed_gates": failed_gates,
            }
        )

    def _handle_halt_command(self, chat_id: str, user_id: int, username: str, correlation_id: str) -> None:
        """Emit KILL_SWITCH through the event manager."""
        reason = f"Operator HALT via Telegram user_id={user_id} username={username}"
        emitted = self.event_manager.emit(
            EventType.KILL_SWITCH,
            {
                "reason": reason,
                "source": "TelegramBot",
                "operator_user_id": user_id,
                "operator_username": username,
            },
            priority=EventPriority.EMERGENCY,
            source="TelegramBot",
        )

        if emitted:
            self.send_message(
                f"🛑 <b>HALT command accepted.</b> KILL_SWITCH emitted.\nCorrelation: {correlation_id}",
                chat_id=chat_id,
                priority=MessagePriority.CRITICAL,
                message_type=MessageType.ALERT,
            )
            result = "emitted"
        else:
            self.send_message(
                f"❌ HALT command failed: could not emit KILL_SWITCH.\nCorrelation: {correlation_id}",
                chat_id=chat_id,
                priority=MessagePriority.CRITICAL,
                message_type=MessageType.ERROR,
            )
            result = "emit_failed"

        self._append_command_audit(
            {
                "ts": datetime.now(UTC).isoformat(),
                "correlation_id": correlation_id,
                "command": "/halt",
                "user_id": user_id,
                "username": username,
                "authorized": True,
                "result": result,
            }
        )

    def _request_confirmation(
        self,
        chat_id: str,
        user_id: int,
        username: str,
        action: str,
        correlation_id: str,
    ) -> None:
        """Create a short-lived confirmation token for dangerous commands."""
        token = uuid.uuid4().hex[:6].upper()
        expires_at = time.time() + 60
        if action == "resume" and self._resume_dual_approval:
            self._resume_pending = {
                "token": token,
                "expires_at": expires_at,
                "requested_by": user_id,
                "approvers": set(),
                "correlation_id": correlation_id,
            }
        self._pending_confirms[user_id] = {
            "action": action,
            "token": token,
            "expires_at": expires_at,
            "username": username,
            "correlation_id": correlation_id,
        }
        dual_line = "\nDual approval required: 2 operators" if action == "resume" and self._resume_dual_approval else ""
        self.send_message(
            (
                f"⚠️ Confirm {action.upper()} within 60s:\n"
                f"/confirm {action} {token}"
                f"{dual_line}\n"
                f"Correlation: {correlation_id}"
            ),
            chat_id=chat_id,
            priority=MessagePriority.HIGH,
            message_type=MessageType.ALERT,
        )

    def _handle_confirm_command(
        self,
        chat_id: str,
        user_id: int,
        username: str,
        args: list[str],
        correlation_id: str,
    ) -> None:
        """Verify and execute pending command confirmation."""
        if len(args) != 2:
            self.send_message(
                "Usage: /confirm <halt|flatten|resume> <TOKEN>",
                chat_id=chat_id,
                priority=MessagePriority.NORMAL,
                message_type=MessageType.SYSTEM,
            )
            return

        action = args[0].strip().lower()
        token = args[1].strip().upper()
        # Dual-approval path for resume in live mode.
        if action == "resume" and self._resume_dual_approval and self._resume_pending is not None:
            pending_resume = self._resume_pending
            if time.time() > float(pending_resume.get("expires_at", 0)):
                self._resume_pending = None
                self.send_message(
                    "Resume confirmation token expired. Reissue /resume.",
                    chat_id=chat_id,
                    priority=MessagePriority.HIGH,
                    message_type=MessageType.ALERT,
                )
                return
            if token != str(pending_resume.get("token")):
                self.send_message(
                    "Invalid resume confirmation token.",
                    chat_id=chat_id,
                    priority=MessagePriority.HIGH,
                    message_type=MessageType.ALERT,
                )
                return

            approvers = pending_resume.get("approvers", set())
            if user_id in approvers:
                self.send_message(
                    "Your resume approval was already recorded.",
                    chat_id=chat_id,
                    priority=MessagePriority.NORMAL,
                    message_type=MessageType.SYSTEM,
                )
                return
            approvers.add(user_id)
            pending_resume["approvers"] = approvers
            pending_resume["last_username"] = username

            if len(approvers) < 2:
                self.send_message(
                    (
                        "⏳ Resume approval recorded. Waiting for second operator.\n"
                        f"Approvals: {len(approvers)}/2\n"
                        f"Correlation: {pending_resume.get('correlation_id', correlation_id)}"
                    ),
                    chat_id=chat_id,
                    priority=MessagePriority.HIGH,
                    message_type=MessageType.ALERT,
                )
                return

            self._resume_pending = None
            self._handle_resume_command(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                correlation_id=str(pending_resume.get("correlation_id", correlation_id)),
                approved_by=sorted(list(approvers)),
            )
            return

        pending = self._pending_confirms.get(user_id)
        if not pending:
            self.send_message(
                "No pending confirmation found.",
                chat_id=chat_id,
                priority=MessagePriority.NORMAL,
                message_type=MessageType.SYSTEM,
            )
            return

        if time.time() > float(pending.get("expires_at", 0)):
            self._pending_confirms.pop(user_id, None)
            self.send_message(
                "Confirmation token expired. Reissue command.",
                chat_id=chat_id,
                priority=MessagePriority.HIGH,
                message_type=MessageType.ALERT,
            )
            return

        if action != pending.get("action") or token != pending.get("token"):
            self.send_message(
                "Invalid confirmation token/action.",
                chat_id=chat_id,
                priority=MessagePriority.HIGH,
                message_type=MessageType.ALERT,
            )
            return

        self._pending_confirms.pop(user_id, None)
        if action == "halt":
            self._handle_halt_command(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                correlation_id=str(pending.get("correlation_id", correlation_id)),
            )
            return
        if action == "flatten":
            self._handle_flatten_command(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                correlation_id=str(pending.get("correlation_id", correlation_id)),
            )
            return
        if action == "resume":
            self._handle_resume_command(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                correlation_id=str(pending.get("correlation_id", correlation_id)),
                approved_by=[user_id],
            )
            return

        self.send_message(
            f"Unsupported confirmation action: {action}",
            chat_id=chat_id,
            priority=MessagePriority.NORMAL,
            message_type=MessageType.SYSTEM,
        )

    def _handle_flatten_command(self, chat_id: str, user_id: int, username: str, correlation_id: str) -> None:
        """Best-effort flatten via active supervisor/engine and event emit."""
        supervisor = get_session_supervisor()
        flatten_ok = False
        detail = ""

        try:
            self.event_manager.emit(
                EventType.FLATTEN_REQUEST,
                {
                    "reason": "Operator FLATTEN via Telegram",
                    "operator_user_id": user_id,
                    "operator_username": username,
                },
                priority=EventPriority.EMERGENCY,
                source="TelegramBot",
            )
        except Exception as exc:
            self.logger.warning("Failed emitting FLATTEN_REQUEST (continuing): %s", exc)

        try:
            if supervisor is None or not getattr(supervisor, "is_running", False):
                detail = "No active SessionSupervisor"
            else:
                supervisor.stop(flatten=True)
                flatten_ok = True
                detail = "Supervisor stop(flatten=True) executed"
        except Exception as exc:
            detail = f"Flatten failed: {exc}"

        self.send_message(
            (
                "🧯 <b>FLATTEN command result</b>\n"
                f"Success: {'YES' if flatten_ok else 'NO'}\n"
                f"Detail: {detail}\n"
                f"Correlation: {correlation_id}"
            ),
            chat_id=chat_id,
            priority=MessagePriority.CRITICAL if flatten_ok else MessagePriority.HIGH,
            message_type=MessageType.ALERT,
        )
        self._append_command_audit(
            {
                "ts": datetime.now(UTC).isoformat(),
                "correlation_id": correlation_id,
                "command": "/flatten",
                "user_id": user_id,
                "username": username,
                "authorized": True,
                "result": "ok" if flatten_ok else "failed",
                "detail": detail,
            }
        )

    def _handle_resume_command(
        self,
        chat_id: str,
        user_id: int,
        username: str,
        correlation_id: str,
        approved_by: list[int],
    ) -> None:
        """Resume path with preflight checks and kill-lock clear."""
        failed_gates = self._resume_preflight_failed_gates()
        if self._resume_dual_approval and len(approved_by) < 2:
            failed_gates.append("dual_approval")
        if failed_gates:
            self.send_message(
                (
                    "⛔ <b>RESUME denied</b>\n"
                    f"Failed gates: {', '.join(failed_gates)}\n"
                    f"Correlation: {correlation_id}"
                ),
                chat_id=chat_id,
                priority=MessagePriority.HIGH,
                message_type=MessageType.ALERT,
            )
            self._append_command_audit(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "correlation_id": correlation_id,
                    "command": "/resume",
                    "user_id": user_id,
                    "username": username,
                    "authorized": True,
                    "result": "denied",
                    "failed_gates": failed_gates,
                    "approved_by": approved_by,
                }
            )
            return

        kill_lock = Path.home() / ".spyder_kill_lock"
        lock_cleared = False
        try:
            if kill_lock.exists():
                kill_lock.unlink()
                lock_cleared = True
        except Exception as exc:
            self.logger.error("Failed to clear kill lock: %s", exc)

        supervisor = get_session_supervisor()
        resumed = False
        if supervisor is not None:
            engine = getattr(supervisor, "engine", None)
            try:
                if engine is not None and hasattr(engine, "resume_trading"):
                    resumed = bool(engine.resume_trading())
            except Exception as exc:
                self.logger.error("Resume action failed: %s", exc)

        self.send_message(
            (
                "▶️ <b>RESUME command processed</b>\n"
                f"Kill Lock Cleared: {'YES' if lock_cleared else 'NO/NA'}\n"
                f"Engine Resume Called: {'YES' if resumed else 'NO'}\n"
                f"Approved By: {approved_by}\n"
                f"Correlation: {correlation_id}"
            ),
            chat_id=chat_id,
            priority=MessagePriority.HIGH,
            message_type=MessageType.SYSTEM,
        )
        self._append_command_audit(
            {
                "ts": datetime.now(UTC).isoformat(),
                "correlation_id": correlation_id,
                "command": "/resume",
                "user_id": user_id,
                "username": username,
                "authorized": True,
                "result": "processed",
                "kill_lock_cleared": lock_cleared,
                "engine_resumed": resumed,
                "approved_by": approved_by,
            }
        )

    def _resume_preflight_failed_gates(self) -> list[str]:
        """Return failed preflight gate names for resume requests."""
        failed: list[str] = []
        now_utc = datetime.now(UTC)
        # Trading-day gate (simple, conservative): weekdays only.
        if now_utc.weekday() >= 5:
            failed.append("trading_day")

        supervisor = get_session_supervisor()
        if supervisor is None or not getattr(supervisor, "is_running", False):
            failed.append("session_supervisor")
            return failed

        if getattr(supervisor, "broker", None) is None:
            failed.append("broker_health")

        risk = getattr(supervisor, "risk", None)
        if risk is not None and hasattr(risk, "_account_state_synced"):
            if not bool(risk._account_state_synced):
                failed.append("risk_sync")

        return failed

    def _append_command_audit(self, payload: dict[str, Any]) -> None:
        """Append operator command audit JSONL entry."""
        try:
            COMMAND_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
            day = datetime.now(UTC).strftime("%Y-%m-%d")
            audit_file = COMMAND_AUDIT_DIR / f"operator_commands_{day}.jsonl"
            with audit_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, sort_keys=True) + "\n")
        except Exception as exc:
            self.logger.error("Failed to append Telegram command audit: %s", exc)

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _create_session(self, retry_total: int | None = None) -> requests.Session:
        """Create HTTP session with an optional retry budget override."""
        if retry_total is None:
            retry_total = MAX_RETRIES
        return self._build_session(int(retry_total))

    def _build_session(self, retry_total: int) -> requests.Session:
        """Create HTTP session with configurable retry budget."""
        session = requests.Session()

        retry = Retry(
            total=retry_total,
            connect=retry_total,
            read=retry_total,
            redirect=retry_total,
            status=retry_total,
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
        def _subscribe(event_type: EventType, handler: Any, subscriber_name: str) -> None:
            """Subscribe handler across supported event manager signatures."""
            try:
                # Primary SpyderA05 EventManager signature.
                self.event_manager.subscribe(
                    event_type=event_type,
                    handler=handler,
                    name=subscriber_name,
                )
                return
            except TypeError:
                pass

            # Fallback for simple bus-style APIs.
            self.event_manager.subscribe(event_type, handler)

        # Trade events
        _subscribe(EventType.TRADE, self._handle_trade_event, "telegram_trade")
        _subscribe(EventType.POSITION_CLOSED, self._handle_position_closed_event, "telegram_position_closed")

        # Alert events
        _subscribe(EventType.ALERT, self._handle_alert_event, "telegram_alert")

        # System events
        _subscribe(EventType.SYSTEM, self._handle_system_event, "telegram_system")

    def _handle_trade_event(self, event: Event) -> None:
        """Handle trade events"""
        try:
            trade_type = event.data.get('type')
            strategy = event.data.get('strategy', 'Strategy')
            symbol = event.data.get('symbol', '')

            if trade_type == 'opened':
                self.logger.info("🎯 Executed: %s · %s", strategy, symbol)
                self.send_compact_trade_message(
                    "opened",
                    strategy=strategy,
                    symbol=symbol,
                )

            elif trade_type == 'closed':
                pnl = float(event.data.get('pnl', 0.0) or 0.0)
                pnl_percent = float(event.data.get('pnl_percent', 0.0) or 0.0)
                pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                self.logger.info(
                    "%s Closed: %s · P&L: %s",
                    "💰" if pnl >= 0 else "📉",
                    strategy,
                    pnl_str,
                )
                self.send_compact_trade_message(
                    "closed",
                    strategy=strategy,
                    symbol=symbol,
                    pnl=pnl,
                    pnl_percent=pnl_percent,
                )

        except Exception as e:
            self.logger.error("Error handling trade event: %s", e)

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        """Safely convert arbitrary value to float."""
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_int(value: Any, default: int = 1) -> int:
        """Safely convert arbitrary value to int."""
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _enum_name(value: Any, default: str = "UNKNOWN") -> str:
        """Convert enum-like values to printable names."""
        if value is None:
            return default
        name = getattr(value, "name", None)
        if name:
            return str(name)
        return str(value)

    def _build_trade_close_dedup_key(self, event: Event, payload: dict[str, Any]) -> str:
        """Build a stable dedup key for close notifications."""
        position_id = payload.get("position_id") or payload.get("spread_id")
        if position_id:
            return f"pos:{position_id}"

        symbol = payload.get("symbol", "UNKNOWN")
        strategy = payload.get("strategy") or payload.get("strategy_name") or (event.source or "UNKNOWN")
        reason = payload.get("exit_reason") or payload.get("reason") or "closed"
        pnl = round(self._to_float(payload.get("pnl", payload.get("realized_pnl", 0.0))), 2)
        return f"fallback:{strategy}:{symbol}:{reason}:{pnl}"

    def _should_skip_trade_close_notification(self, dedup_key: str) -> bool:
        """Return True when a matching close alert was sent recently."""
        now_ts = time.time()
        window = getattr(self, "_trade_close_dedup_window_seconds", 30)

        recent: dict[str, float] = getattr(self, "_recent_trade_close_keys", {})
        # Opportunistic cleanup to prevent unbounded growth.
        stale_keys = [k for k, ts in recent.items() if now_ts - ts > window]
        for stale_key in stale_keys:
            recent.pop(stale_key, None)

        last_ts = recent.get(dedup_key)
        if last_ts is not None and now_ts - last_ts <= window:
            return True

        recent[dedup_key] = now_ts
        self._recent_trade_close_keys = recent
        return False

    def _handle_position_closed_event(self, event: Event) -> None:
        """Normalize POSITION_CLOSED payloads into trade-close Telegram alerts."""
        try:
            payload = dict(event.data or {})
            dedup_key = self._build_trade_close_dedup_key(event, payload)
            if self._should_skip_trade_close_notification(dedup_key):
                self.logger.debug("Skipping duplicate trade-close alert key=%s", dedup_key)
                return

            strategy = payload.get("strategy") or payload.get("strategy_name") or event.source or "Strategy"
            symbol = payload.get("symbol") or payload.get("underlying") or "SPY"

            quantity = self._to_int(
                payload.get("quantity") or payload.get("position_size") or payload.get("contracts"),
                default=1,
            )

            entry_price = self._to_float(
                payload.get("entry_price") or payload.get("credit_received") or payload.get("credit"),
                default=0.0,
            )

            pnl = self._to_float(payload.get("pnl", payload.get("realized_pnl", 0.0)), default=0.0)
            pnl_percent = self._to_float(payload.get("pnl_percent"), default=0.0)
            if pnl_percent == 0.0:
                notional = abs(entry_price * max(quantity, 1))
                if notional > 0:
                    pnl_percent = (pnl / notional) * 100.0

            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            self.logger.info(
                "%s Closed: %s · P&L: %s",
                "💰" if pnl >= 0 else "📉",
                str(strategy),
                pnl_str,
            )
            self.send_compact_trade_message(
                "closed",
                strategy=str(strategy),
                symbol=str(symbol),
                pnl=pnl,
                pnl_percent=pnl_percent,
            )
        except Exception as e:
            self.logger.error("Error handling position closed event: %s", e)

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
            event_type = event.data.get('type')

            if event_type == 'error':
                self.send_alert(
                    title="System Error",
                    message=event.data.get('message', 'Unknown error'),
                    severity='error'
                )

            elif event_type == 'telegram_send':
                # Generic forwarding path used by other modules (e.g. A04 preflight
                # dispatch) to avoid direct imports into this module.
                text = event.data.get('text') or event.data.get('message', '')
                if text:
                    self.send_message(text)

        except Exception as e:
            self.logger.error("Error handling system event: %s", e)

    # ==========================================================================
    # PUBLIC METHODS - UTILITIES
    # ==========================================================================
    def get_stats(self) -> dict[str, Any]:
        """Get bot statistics"""
        uptime = datetime.now(UTC) - self.stats.uptime_start

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
    test_event_manager = EventManager()
    bot = TelegramBot(BOT_TOKEN, CHAT_ID, test_event_manager)

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
        date=datetime.now(UTC),
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
