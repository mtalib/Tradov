# IBKR Client Portal Web API - Best Practices & Implementation Guide

## 🎯 Executive Summary

This document outlines best practices for implementing Interactive Brokers Client Portal Web API in the Spyder trading system. The Client Portal Web API provides a modern REST + WebSocket interface for real-time market data, order execution, and account management, replacing the legacy TWS API/IB Gateway approach.

**Last Updated:** 2025-11-08
**API Version:** v1.0+
**Documentation:** https://interactivebrokers.github.io/cpwebapi/

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Authentication & Authorization](#authentication--authorization)
3. [Connection Management](#connection-management)
4. [Rate Limiting & Throttling](#rate-limiting--throttling)
5. [Market Data Subscriptions](#market-data-subscriptions)
6. [Order Management](#order-management)
7. [Error Handling](#error-handling)
8. [Security Best Practices](#security-best-practices)
9. [Performance Optimization](#performance-optimization)
10. [Migration from TWS API](#migration-from-tws-api)
11. [Implementation Checklist](#implementation-checklist)

---

## 🏗️ Architecture Overview

### **REST + WebSocket Hybrid**

The Client Portal Web API uses a dual-protocol approach:

```
┌─────────────────────────────────────────────────────────────┐
│                    Spyder Trading System                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────┐         ┌─────────────────┐            │
│  │  REST Client   │◄────────┤  HTTP Requests  │            │
│  │                │         │  (Sync Ops)     │            │
│  │  - Orders      │         │  - Account Info │            │
│  │  - Positions   │         │  - Historical   │            │
│  │  - Config      │         │  - Order Entry  │            │
│  └────────────────┘         └─────────────────┘            │
│                                                              │
│  ┌────────────────┐         ┌─────────────────┐            │
│  │ WebSocket      │◄────────┤  Async Streams  │            │
│  │ Client         │         │  (Real-time)    │            │
│  │                │         │  - Market Data  │            │
│  │  - Live Quotes │         │  - Order Status │            │
│  │  - Account     │         │  - PnL Updates  │            │
│  │    Updates     │         │  - Executions   │            │
│  └────────────────┘         └─────────────────┘            │
│                                                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  Client Portal       │
            │  Gateway (Optional)  │
            │  or OAuth 2.0        │
            └──────────┬───────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  IBKR Infrastructure │
            └──────────────────────┘
```

### **Key Components**

1. **REST API Client** - Synchronous operations
   - Account queries
   - Order placement/modification/cancellation
   - Historical data requests
   - Portfolio positions
   - Configuration

2. **WebSocket Client** - Asynchronous event streaming
   - Real-time market data
   - Order status updates
   - Account/PnL updates
   - Trade executions

3. **Session Manager** - Maintains authentication
   - Tickle keepalive (every 4-5 minutes)
   - Re-authentication handling
   - Session state monitoring

---

## 🔐 Authentication & Authorization

### **Account Requirements**

⚠️ **CRITICAL:** Client Portal API supports **IBKR Pro accounts ONLY**

### **Authentication Methods**

#### **1. Client Portal Gateway (Individual Accounts)**

**Use Case:** Individual traders, development, testing

```python
# CP Gateway Configuration
CP_GATEWAY_CONFIG = {
    'host': 'localhost',
    'port': 5000,  # Default port
    'ssl': True,
    'cacert': '/path/to/cacert.pem',  # For SSL verification
    'session_timeout': 360,  # 6 minutes
    'max_session_duration': 86400,  # 24 hours
}
```

**Setup Process:**

1. **Download Gateway:**
   ```bash
   # Download from IBKR website
   wget https://download2.interactivebrokers.com/portal/clientportal.gw.zip
   unzip clientportal.gw.zip -d ~/ibkr-gateway
   ```

2. **Configure Gateway:**
   ```bash
   # Edit conf.yaml
   cd ~/ibkr-gateway
   nano conf.yaml
   ```

   ```yaml
   # conf.yaml
   listenPort: 5000
   listenSsl: true
   sslCert: certs/cert.pem
   sslKey: certs/key.pem
   ips: ["127.0.0.1"]  # Restrict to localhost
   readonly: false
   ```

3. **Launch Gateway:**
   ```bash
   cd ~/ibkr-gateway
   ./bin/run.sh root/conf.yaml &

   # Or use systemd service (recommended)
   sudo systemctl start ibkr-gateway
   ```

4. **Initial Authentication:**
   ```python
   import requests

   # Navigate to https://localhost:5000 in browser
   # Complete 2FA authentication
   # Session lasts 24 hours or until midnight (NY/Zurich/HK time)
   ```

#### **2. OAuth 2.0 (Institutional/Enterprise Accounts)**

**Use Case:** Production trading, institutional clients, automated systems

**OAuth 2.0 Flow (private_key_jwt):**

```python
import jwt
import time
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

class IBKROAuth2Client:
    """OAuth 2.0 authentication using private_key_jwt"""

    def __init__(self, consumer_key: str, private_key_path: str):
        self.consumer_key = consumer_key
        self.private_key = self._load_private_key(private_key_path)
        self.token_url = "https://api.ibkr.com/v1/oauth2/token"
        self.access_token = None
        self.token_expiry = None

    def _load_private_key(self, path: str):
        """Load private key for JWT signing"""
        with open(path, 'rb') as f:
            return serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )

    def _create_jwt_assertion(self) -> str:
        """Create JWT assertion for token request"""
        now = int(time.time())

        payload = {
            'iss': self.consumer_key,  # Issuer (your consumer key)
            'sub': self.consumer_key,  # Subject (your consumer key)
            'aud': self.token_url,     # Audience (token endpoint)
            'exp': now + 300,           # Expiration (5 minutes)
            'iat': now,                 # Issued at
            'jti': f"{self.consumer_key}-{now}"  # Unique ID
        }

        return jwt.encode(
            payload,
            self.private_key,
            algorithm='RS256',
            headers={'kid': self.consumer_key}
        )

    def get_access_token(self) -> str:
        """Obtain access token using private_key_jwt"""

        # Check if current token is still valid
        if self.access_token and self.token_expiry:
            if time.time() < self.token_expiry - 60:  # 1 min buffer
                return self.access_token

        # Request new token
        jwt_assertion = self._create_jwt_assertion()

        data = {
            'grant_type': 'client_credentials',
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'client_assertion': jwt_assertion
        }

        response = requests.post(self.token_url, data=data)
        response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data['access_token']
        self.token_expiry = time.time() + token_data.get('expires_in', 3600)

        return self.access_token

# Usage
oauth_client = IBKROAuth2Client(
    consumer_key='YOUR_CONSUMER_KEY',
    private_key_path='/secure/path/to/private_key.pem'
)

access_token = oauth_client.get_access_token()
```

### **Best Practices: Authentication**

✅ **DO:**
- Store credentials in `.env` file (NEVER commit to git)
- Use OAuth 2.0 for production/institutional accounts
- Implement automatic token refresh
- Use `private_key_jwt` (more secure than client_secret)
- Enable 2FA on IBKR account
- Restrict API access by IP address in IBKR settings

❌ **DON'T:**
- Hardcode credentials in source code
- Share authentication tokens
- Use CP Gateway for production (use OAuth 2.0)
- Store private keys in version control
- Disable SSL certificate verification

---

## 🔄 Connection Management

### **Session Lifecycle**

```python
class SessionManager:
    """Manages Client Portal session lifecycle"""

    def __init__(self, base_url: str, auth_client):
        self.base_url = base_url
        self.auth_client = auth_client
        self.session = requests.Session()
        self.last_tickle = 0
        self.tickle_interval = 240  # 4 minutes (6 min timeout)
        self.session_started = None
        self.session_max_duration = 86400  # 24 hours

    def _update_auth_header(self):
        """Update session with fresh auth token"""
        token = self.auth_client.get_access_token()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        })

    def start_session(self):
        """Initialize session"""
        self._update_auth_header()

        # Validate session
        response = self.session.post(f'{self.base_url}/iserver/auth/status')
        response.raise_for_status()

        status = response.json()
        if not status.get('authenticated', False):
            raise Exception("Authentication failed")

        self.session_started = time.time()
        self._start_tickle_thread()

        return status

    def _start_tickle_thread(self):
        """Start background thread for tickle keepalive"""
        import threading

        def tickle_loop():
            while True:
                time.sleep(self.tickle_interval)
                self.tickle()

        thread = threading.Thread(target=tickle_loop, daemon=True)
        thread.start()

    def tickle(self):
        """Send keepalive to prevent session timeout"""
        try:
            response = self.session.post(f'{self.base_url}/tickle')
            response.raise_for_status()
            self.last_tickle = time.time()

            # Check if approaching 24-hour limit
            session_age = time.time() - self.session_started
            if session_age > (self.session_max_duration - 3600):  # 1 hour warning
                logger.warning(f"Session approaching 24-hour limit: {session_age/3600:.1f} hours")

        except Exception as e:
            logger.error(f"Tickle failed: {e}")
            # Attempt to re-authenticate
            self.start_session()

    def is_session_valid(self) -> bool:
        """Check if session is still valid"""
        try:
            response = self.session.post(f'{self.base_url}/iserver/auth/status')
            return response.json().get('authenticated', False)
        except:
            return False

    def logout(self):
        """Clean session logout"""
        try:
            self.session.post(f'{self.base_url}/logout')
        except Exception as e:
            logger.error(f"Logout failed: {e}")

# Usage
session_mgr = SessionManager(
    base_url='https://localhost:5000/v1/api',
    auth_client=oauth_client
)
session_mgr.start_session()
```

### **Best Practices: Sessions**

✅ **DO:**
- Send `/tickle` every 4-5 minutes (timeout is 6 minutes)
- Monitor session age (24-hour maximum)
- Implement automatic re-authentication
- Handle session timeouts gracefully
- Use connection pooling for HTTP requests
- Implement exponential backoff for retries

❌ **DON'T:**
- Rely on session lasting indefinitely
- Ignore session timeout warnings
- Create multiple concurrent sessions (limit: 1 per account)
- Skip tickle keepalive

---

## ⚡ Rate Limiting & Throttling

### **Rate Limits (as of 2025)**

| Method | Limit | Scope |
|--------|-------|-------|
| OAuth 2.0 | 50 req/sec | Per authenticated user |
| CP Gateway | 10 req/sec | Per authenticated user |
| WebSocket Heartbeat | 1 per 10 sec | Per connection |
| Market Data Lines | 100+ | Based on commissions/equity |
| WebSocket Streams | ~5-100 | Concurrent market data streams |

### **Implementation**

```python
import time
from collections import deque
from threading import Lock
import asyncio

class RateLimiter:
    """Token bucket rate limiter for IBKR API"""

    def __init__(self, rate_limit: int = 10, per_seconds: int = 1):
        """
        Args:
            rate_limit: Maximum requests allowed
            per_seconds: Time window in seconds
        """
        self.rate_limit = rate_limit
        self.per_seconds = per_seconds
        self.tokens = rate_limit
        self.last_refill = time.time()
        self.lock = Lock()
        self.request_history = deque(maxlen=rate_limit * 10)

    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens proportional to elapsed time
        tokens_to_add = (elapsed / self.per_seconds) * self.rate_limit
        self.tokens = min(self.rate_limit, self.tokens + tokens_to_add)
        self.last_refill = now

    def acquire(self, tokens: int = 1, blocking: bool = True) -> bool:
        """
        Acquire tokens for request

        Args:
            tokens: Number of tokens to acquire
            blocking: If True, wait until tokens available

        Returns:
            True if tokens acquired, False if not available (non-blocking)
        """
        with self.lock:
            self._refill_tokens()

            if self.tokens >= tokens:
                self.tokens -= tokens
                self.request_history.append(time.time())
                return True

            if not blocking:
                return False

            # Calculate wait time
            wait_time = (tokens - self.tokens) / (self.rate_limit / self.per_seconds)

        # Wait outside of lock
        time.sleep(wait_time)
        return self.acquire(tokens, blocking=True)

    async def acquire_async(self, tokens: int = 1) -> bool:
        """Async version of acquire"""
        while True:
            with self.lock:
                self._refill_tokens()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    self.request_history.append(time.time())
                    return True

                # Calculate wait time
                wait_time = (tokens - self.tokens) / (self.rate_limit / self.per_seconds)

            await asyncio.sleep(wait_time)

    def get_current_rate(self) -> float:
        """Get current request rate (req/sec)"""
        if len(self.request_history) < 2:
            return 0.0

        now = time.time()
        recent = [t for t in self.request_history if now - t < self.per_seconds]
        return len(recent) / self.per_seconds

    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return {
            'tokens_available': self.tokens,
            'max_tokens': self.rate_limit,
            'current_rate': self.get_current_rate(),
            'limit_rate': self.rate_limit / self.per_seconds,
            'requests_last_window': len([
                t for t in self.request_history
                if time.time() - t < self.per_seconds
            ])
        }


class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter that adapts based on 429 responses"""

    def __init__(self, initial_rate: int = 10, per_seconds: int = 1):
        super().__init__(initial_rate, per_seconds)
        self.original_rate = initial_rate
        self.backoff_factor = 0.8
        self.recovery_factor = 1.1
        self.min_rate = 1
        self.consecutive_successes = 0
        self.recovery_threshold = 100  # Requests before attempting recovery

    def handle_rate_limit_error(self):
        """Called when 429 (rate limit) error received"""
        with self.lock:
            # Reduce rate by backoff factor
            new_rate = max(self.min_rate, int(self.rate_limit * self.backoff_factor))
            logger.warning(f"Rate limit hit. Reducing from {self.rate_limit} to {new_rate} req/sec")
            self.rate_limit = new_rate
            self.tokens = min(self.tokens, new_rate)
            self.consecutive_successes = 0

    def handle_success(self):
        """Called on successful request"""
        self.consecutive_successes += 1

        # Gradually increase rate after sustained success
        if self.consecutive_successes >= self.recovery_threshold:
            with self.lock:
                if self.rate_limit < self.original_rate:
                    new_rate = min(
                        self.original_rate,
                        int(self.rate_limit * self.recovery_factor)
                    )
                    logger.info(f"Recovering rate limit from {self.rate_limit} to {new_rate} req/sec")
                    self.rate_limit = new_rate
                    self.consecutive_successes = 0


# Usage
# For CP Gateway users
cp_limiter = AdaptiveRateLimiter(rate_limit=10, per_seconds=1)

# For OAuth users
oauth_limiter = AdaptiveRateLimiter(rate_limit=50, per_seconds=1)

# Before each API request
def make_api_request(endpoint, data, rate_limiter):
    rate_limiter.acquire()

    try:
        response = requests.post(endpoint, json=data)

        if response.status_code == 429:  # Too Many Requests
            rate_limiter.handle_rate_limit_error()
            # Retry with backoff
            time.sleep(1)
            return make_api_request(endpoint, data, rate_limiter)

        response.raise_for_status()
        rate_limiter.handle_success()
        return response.json()

    except Exception as e:
        logger.error(f"API request failed: {e}")
        raise
```

### **Best Practices: Rate Limiting**

✅ **DO:**
- Implement client-side rate limiting (don't rely on server rejection)
- Use adaptive rate limiting that backs off on 429 errors
- Monitor your current request rate
- Batch requests when possible
- Use WebSocket for frequent updates (not polling)
- Cache data to reduce API calls

❌ **DON'T:**
- Ignore 429 (Too Many Requests) responses
- Poll endpoints continuously without rate limiting
- Create multiple sessions to bypass limits (violation of ToS)
- Use tight polling loops for market data (use WebSocket)

---

## 📊 Market Data Subscriptions

### **Market Data Endpoints**

```python
class MarketDataClient:
    """Client Portal market data management"""

    def __init__(self, session: SessionManager, rate_limiter: RateLimiter):
        self.session = session
        self.rate_limiter = rate_limiter
        self.base_url = session.base_url
        self.subscriptions = set()

    def get_market_data_snapshot(self, conid: int, fields: list) -> dict:
        """
        Get current market data snapshot

        Args:
            conid: Contract ID
            fields: List of field numbers (e.g., [31, 84, 86] for last/bid/ask)

        Returns:
            Market data snapshot
        """
        self.rate_limiter.acquire()

        endpoint = f"{self.base_url}/iserver/marketdata/snapshot"
        params = {
            'conids': conid,
            'fields': ','.join(map(str, fields))
        }

        response = self.session.session.get(endpoint, params=params)
        response.raise_for_status()

        return response.json()

    def subscribe_market_data(self, conid: int, fields: list) -> dict:
        """
        Subscribe to streaming market data

        Note: Use WebSocket for actual streaming. This is for initial subscription.
        """
        self.rate_limiter.acquire()

        endpoint = f"{self.base_url}/iserver/marketdata/snapshot"
        params = {
            'conids': conid,
            'fields': ','.join(map(str, fields))
        }

        response = self.session.session.get(endpoint, params=params)
        response.raise_for_status()

        self.subscriptions.add(conid)
        return response.json()

    def unsubscribe_market_data(self, conid: int):
        """Unsubscribe from market data"""
        self.rate_limiter.acquire()

        endpoint = f"{self.base_url}/iserver/marketdata/unsubscribe"
        data = {'conid': conid}

        response = self.session.session.post(endpoint, json=data)
        response.raise_for_status()

        self.subscriptions.discard(conid)

    def unsubscribe_all(self):
        """Unsubscribe from all market data"""
        self.rate_limiter.acquire()

        endpoint = f"{self.base_url}/iserver/marketdata/unsubscribeall"
        response = self.session.session.post(endpoint)
        response.raise_for_status()

        self.subscriptions.clear()


# Field IDs (common ones)
FIELD_IDS = {
    'last_price': 31,
    'symbol': 55,
    'bid': 84,
    'ask': 86,
    'bid_size': 88,
    'ask_size': 85,
    'volume': 87,
    'last_size': 7295,
    'high': 70,
    'low': 71,
    'close': 82,
    'open': 7282,
    'change': 82,
    'change_percent': 83,
}
```

### **WebSocket Market Data**

```python
import websocket
import json
import threading

class MarketDataWebSocket:
    """WebSocket client for real-time market data"""

    def __init__(self, session_manager: SessionManager):
        self.session = session_manager
        self.ws_url = "wss://localhost:5000/v1/api/ws"
        self.ws = None
        self.callbacks = {}
        self.running = False
        self.last_heartbeat = 0
        self.heartbeat_interval = 10  # seconds

    def connect(self):
        """Establish WebSocket connection"""
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )

        # Start WebSocket in background thread
        ws_thread = threading.Thread(target=self._run_forever, daemon=True)
        ws_thread.start()

        # Start heartbeat thread
        hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        hb_thread.start()

    def _run_forever(self):
        """Run WebSocket connection"""
        self.running = True
        self.ws.run_forever(
            sslopt={"cert_reqs": ssl.CERT_NONE}  # For self-signed certs
        )

    def _on_open(self, ws):
        """Called when WebSocket connection established"""
        logger.info("WebSocket connected")

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)

            # Route to appropriate callback
            topic = data.get('topic')
            if topic and topic in self.callbacks:
                self.callbacks[topic](data)
            else:
                # Generic market data update
                self._handle_market_data(data)

        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")

    def _handle_market_data(self, data):
        """Process market data updates"""
        # Extract contract ID and field updates
        for item in data:
            conid = item.get('conid')
            if not conid:
                continue

            # Fire callback if registered
            callback = self.callbacks.get(f'md_{conid}')
            if callback:
                callback(item)

    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.running = False

        # Attempt reconnection
        if self.should_reconnect():
            time.sleep(5)
            self.connect()

    def _heartbeat_loop(self):
        """Send periodic heartbeat to keep connection alive"""
        while self.running:
            time.sleep(self.heartbeat_interval)

            try:
                if self.ws and self.ws.sock and self.ws.sock.connected:
                    # Send ping
                    self.ws.send(json.dumps({'ping': int(time.time())}))
                    self.last_heartbeat = time.time()
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")

    def subscribe(self, conid: int, fields: list, callback: callable):
        """
        Subscribe to market data for a contract

        Args:
            conid: Contract ID
            fields: List of field IDs to subscribe to
            callback: Function to call with updates
        """
        subscription = {
            'subscribe': True,
            'conid': conid,
            'fields': fields
        }

        self.ws.send(json.dumps(subscription))
        self.callbacks[f'md_{conid}'] = callback

        logger.info(f"Subscribed to market data for {conid}")

    def unsubscribe(self, conid: int):
        """Unsubscribe from market data"""
        unsubscribe = {
            'unsubscribe': True,
            'conid': conid
        }

        self.ws.send(json.dumps(unsubscribe))
        self.callbacks.pop(f'md_{conid}', None)

    def close(self):
        """Close WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()


# Usage
def on_market_data_update(data):
    """Callback for market data updates"""
    print(f"Market data: {data}")

ws_client = MarketDataWebSocket(session_manager)
ws_client.connect()

# Subscribe to SPY
spy_conid = 756733  # SPY contract ID
ws_client.subscribe(
    conid=spy_conid,
    fields=[FIELD_IDS['last_price'], FIELD_IDS['bid'], FIELD_IDS['ask']],
    callback=on_market_data_update
)
```

### **Best Practices: Market Data**

✅ **DO:**
- Use WebSocket for real-time streaming data
- Unsubscribe from unused data to free up lines
- Monitor your market data line usage
- Cache snapshots to reduce API calls
- Use batch requests for multiple contracts
- Implement reconnection logic for WebSocket
- Send WebSocket heartbeat every 10 seconds

❌ **DON'T:**
- Poll REST endpoints for real-time data (use WebSocket)
- Subscribe to more contracts than your line limit
- Leave zombie subscriptions active
- Ignore market data subscription limits

---

## 📝 Order Management

### **Order Placement**

```python
from dataclasses import dataclass
from enum import Enum

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(Enum):
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP_LMT"

class TimeInForce(Enum):
    DAY = "DAY"
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate or Cancel
    GTD = "GTD"  # Good Till Date


@dataclass
class Order:
    """Order representation"""
    conid: int
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: float = None
    stop_price: float = None
    tif: TimeInForce = TimeInForce.DAY
    account_id: str = None
    outside_rth: bool = False  # Outside regular trading hours


class OrderManager:
    """Order management via Client Portal API"""

    def __init__(self, session: SessionManager, rate_limiter: RateLimiter):
        self.session = session
        self.rate_limiter = rate_limiter
        self.base_url = session.base_url
        self.orders = {}  # order_id -> order

    def place_order(self, order: Order) -> dict:
        """
        Place a new order

        Args:
            order: Order object

        Returns:
            Order confirmation
        """
        self.rate_limiter.acquire()

        # Build order payload
        payload = {
            'conid': order.conid,
            'secType': f'{order.conid}:STK',  # Adjust for asset type
            'orderType': order.order_type.value,
            'side': order.side.value,
            'quantity': order.quantity,
            'tif': order.tif.value,
            'outsideRTH': order.outside_rth
        }

        if order.price:
            payload['price'] = order.price

        if order.stop_price:
            payload['auxPrice'] = order.stop_price

        if order.account_id:
            payload['acctId'] = order.account_id

        endpoint = f"{self.base_url}/iserver/account/{order.account_id}/orders"

        response = self.session.session.post(endpoint, json={'orders': [payload]})
        response.raise_for_status()

        result = response.json()

        # Handle order confirmation dialog (may require confirmation)
        if isinstance(result, list) and len(result) > 0:
            order_status = result[0]

            if order_status.get('id'):  # Order ID received
                order_id = order_status['id']
                self.orders[order_id] = order
                logger.info(f"Order placed: {order_id}")
                return order_status

            # May need confirmation
            if 'message' in order_status:
                reply_id = order_status.get('id')
                return self._confirm_order(reply_id, order.account_id)

        raise Exception(f"Unexpected order response: {result}")

    def _confirm_order(self, reply_id: str, account_id: str) -> dict:
        """Confirm order (for orders requiring confirmation)"""
        self.rate_limiter.acquire()

        endpoint = f"{self.base_url}/iserver/reply/{reply_id}"
        payload = {'confirmed': True}

        response = self.session.session.post(endpoint, json=payload)
        response.raise_for_status()

        return response.json()

    def modify_order(self, order_id: str, account_id: str, **modifications) -> dict:
        """
        Modify an existing order

        Args:
            order_id: Order ID to modify
            account_id: Account ID
            **modifications: Fields to modify (quantity, price, etc.)
        """
        self.rate_limiter.acquire()

        endpoint = f"{self.base_url}/iserver/account/{account_id}/order/{order_id}"

        response = self.session.session.post(endpoint, json=modifications)
        response.raise_for_status()

        return response.json()

    def cancel_order(self, order_id: str, account_id: str) -> dict:
        """Cancel an order"""
        self.rate_limiter.acquire()

        endpoint = f"{self.base_url}/iserver/account/{account_id}/order/{order_id}"

        response = self.session.session.delete(endpoint)
        response.raise_for_status()

        self.orders.pop(order_id, None)
        logger.info(f"Order cancelled: {order_id}")

        return response.json()

    def get_live_orders(self, account_id: str = None) -> list:
        """Get all live orders"""
        self.rate_limiter.acquire()

        endpoint = f"{self.base_url}/iserver/account/orders"
        params = {}
        if account_id:
            params['accountId'] = account_id

        response = self.session.session.get(endpoint, params=params)
        response.raise_for_status()

        return response.json().get('orders', [])

    def get_order_status(self, order_id: str) -> dict:
        """Get status of specific order"""
        self.rate_limiter.acquire()

        endpoint = f"{self.base_url}/iserver/account/order/status/{order_id}"

        response = self.session.session.get(endpoint)
        response.raise_for_status()

        return response.json()


# Usage Example
order_mgr = OrderManager(session_manager, rate_limiter)

# Market order to buy 100 shares of SPY
buy_order = Order(
    conid=756733,  # SPY
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    quantity=100,
    account_id='DU123456'  # Your account
)

result = order_mgr.place_order(buy_order)
print(f"Order placed: {result}")

# Limit order to sell
sell_order = Order(
    conid=756733,
    side=OrderSide.SELL,
    order_type=OrderType.LIMIT,
    quantity=100,
    price=450.00,
    tif=TimeInForce.GTC,
    account_id='DU123456'
)

result = order_mgr.place_order(sell_order)
```

### **Order Validation**

```python
class OrderValidator:
    """Validate orders before submission"""

    @staticmethod
    def validate_order(order: Order, account_info: dict) -> tuple[bool, str]:
        """
        Validate order before submission

        Returns:
            (is_valid, error_message)
        """
        # Check quantity
        if order.quantity <= 0:
            return False, "Quantity must be positive"

        if order.quantity > 10000:  # Example limit
            return False, f"Quantity {order.quantity} exceeds maximum"

        # Check price for limit orders
        if order.order_type == OrderType.LIMIT:
            if not order.price or order.price <= 0:
                return False, "Limit orders require valid price"

        # Check stop price for stop orders
        if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
            if not order.stop_price or order.stop_price <= 0:
                return False, "Stop orders require valid stop price"

        # Check buying power
        if order.side == OrderSide.BUY:
            estimated_cost = order.quantity * (order.price or 0)
            available_funds = account_info.get('availableFunds', 0)

            if estimated_cost > available_funds:
                return False, f"Insufficient funds: need {estimated_cost}, have {available_funds}"

        return True, ""


# Usage
validator = OrderValidator()
account = get_account_info()  # Fetch account details

is_valid, error = validator.validate_order(buy_order, account)
if not is_valid:
    logger.error(f"Order validation failed: {error}")
else:
    result = order_mgr.place_order(buy_order)
```

### **Best Practices: Orders**

✅ **DO:**
- Validate orders before submission
- Implement order confirmation workflows
- Handle order rejections gracefully
- Monitor order status via WebSocket
- Implement retry logic for network failures
- Log all order activities
- Use appropriate time-in-force settings

❌ **DON'T:**
- Submit orders without validation
- Ignore order confirmation requirements
- Assume orders will fill immediately
- Place duplicate orders on retry without checking status
- Skip error handling

---

## 🛡️ Error Handling

### **Common Error Codes**

| Code | Meaning | Handling |
|------|---------|----------|
| 400 | Bad Request | Validate request payload |
| 401 | Unauthorized | Re-authenticate |
| 403 | Forbidden | Check permissions/subscriptions |
| 404 | Not Found | Verify contract ID/endpoint |
| 429 | Too Many Requests | Implement rate limiting |
| 500 | Internal Server Error | Retry with backoff |
| 503 | Service Unavailable | Wait and retry |

### **Error Handling Implementation**

```python
import functools
import time

class APIError(Exception):
    """Base API error"""
    pass

class AuthenticationError(APIError):
    """Authentication failure"""
    pass

class RateLimitError(APIError):
    """Rate limit exceeded"""
    pass

class ValidationError(APIError):
    """Request validation failed"""
    pass


def with_error_handling(max_retries=3, backoff_factor=2):
    """Decorator for API error handling and retries"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                except requests.exceptions.HTTPError as e:
                    status_code = e.response.status_code

                    # Handle specific status codes
                    if status_code == 401:
                        # Re-authenticate and retry
                        logger.warning("Authentication expired, re-authenticating...")
                        self = args[0] if args else None
                        if hasattr(self, 'session'):
                            self.session.start_session()
                        # Retry immediately
                        continue

                    elif status_code == 429:
                        # Rate limit - backoff and retry
                        wait_time = backoff_factor ** attempt
                        logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue

                    elif status_code >= 500:
                        # Server error - retry with backoff
                        if attempt < max_retries - 1:
                            wait_time = backoff_factor ** attempt
                            logger.warning(f"Server error {status_code}, retrying in {wait_time}s...")
                            time.sleep(wait_time)
                            continue

                    elif status_code == 400:
                        # Bad request - don't retry
                        raise ValidationError(f"Invalid request: {e.response.text}")

                    # Other errors - don't retry
                    raise APIError(f"API error {status_code}: {e.response.text}")

                except requests.exceptions.ConnectionError as e:
                    # Network error - retry
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor ** attempt
                        logger.warning(f"Connection error, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    last_exception = e

                except Exception as e:
                    # Unexpected error
                    logger.error(f"Unexpected error in {func.__name__}: {e}")
                    raise

            # All retries exhausted
            raise APIError(f"Max retries ({max_retries}) exceeded") from last_exception

        return wrapper
    return decorator


# Usage
class RobustOrderManager(OrderManager):
    """Order manager with robust error handling"""

    @with_error_handling(max_retries=3)
    def place_order(self, order: Order) -> dict:
        """Place order with automatic error handling and retries"""
        return super().place_order(order)

    @with_error_handling(max_retries=3)
    def cancel_order(self, order_id: str, account_id: str) -> dict:
        """Cancel order with error handling"""
        return super().cancel_order(order_id, account_id)
```

### **Best Practices: Error Handling**

✅ **DO:**
- Implement exponential backoff for retries
- Log all errors with context
- Handle authentication expiry automatically
- Validate requests before submission
- Monitor error rates
- Implement circuit breaker pattern for cascading failures
- Provide meaningful error messages to users

❌ **DON'T:**
- Retry indefinitely without backoff
- Ignore 429 rate limit errors
- Retry on 4xx errors (client errors)
- Suppress errors without logging
- Expose sensitive data in error messages

---

## 🔒 Security Best Practices

### **1. Credential Management**

```bash
# .env file (NEVER commit to git!)
IBKR_CONSUMER_KEY=your_consumer_key
IBKR_PRIVATE_KEY_PATH=/secure/path/to/private_key.pem
IBKR_ACCOUNT_ID=DU123456

# Production settings
CP_GATEWAY_HOST=localhost
CP_GATEWAY_PORT=5000
CP_GATEWAY_SSL=true
CP_GATEWAY_CACERT=/path/to/cacert.pem

# Security settings
ALLOWED_IPS=127.0.0.1,10.0.0.5
MAX_ORDER_SIZE=10000
REQUIRE_ORDER_CONFIRMATION=true
```

```python
# Load from environment
from dotenv import load_dotenv
import os

load_dotenv()

IBKR_CONFIG = {
    'consumer_key': os.getenv('IBKR_CONSUMER_KEY'),
    'private_key_path': os.getenv('IBKR_PRIVATE_KEY_PATH'),
    'account_id': os.getenv('IBKR_ACCOUNT_ID'),
}

# Validate required variables
required_vars = ['IBKR_CONSUMER_KEY', 'IBKR_PRIVATE_KEY_PATH']
missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    raise ValueError(f"Missing required environment variables: {missing}")
```

### **2. SSL/TLS Configuration**

```python
import ssl
import requests

# For self-signed certificates (CP Gateway)
session = requests.Session()
session.verify = '/path/to/cacert.pem'  # Or False for self-signed (not recommended)

# For production with OAuth
session = requests.Session()
session.verify = True  # Verify SSL certificates

# Custom SSL context
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED
```

### **3. IP Whitelisting**

```python
# Restrict API access to specific IPs
ALLOWED_IPS = os.getenv('ALLOWED_IPS', '127.0.0.1').split(',')

def validate_request_ip(request_ip: str) -> bool:
    """Validate request comes from allowed IP"""
    return request_ip in ALLOWED_IPS

# In your request handler
if not validate_request_ip(request.remote_addr):
    raise SecurityError("Unauthorized IP address")
```

### **4. Order Limits & Controls**

```python
# Implement trading guardrails
class TradingControls:
    """Safety controls for trading"""

    MAX_ORDER_SIZE = int(os.getenv('MAX_ORDER_SIZE', 1000))
    MAX_DAILY_ORDERS = 500
    MAX_POSITION_SIZE = 100000  # USD
    REQUIRE_CONFIRMATION = os.getenv('REQUIRE_ORDER_CONFIRMATION', 'true').lower() == 'true'

    def __init__(self):
        self.daily_order_count = 0
        self.last_reset = datetime.now().date()

    def can_place_order(self, order: Order, current_position_value: float) -> tuple[bool, str]:
        """Check if order is allowed"""

        # Reset daily counter
        if datetime.now().date() > self.last_reset:
            self.daily_order_count = 0
            self.last_reset = datetime.now().date()

        # Check order size
        if order.quantity > self.MAX_ORDER_SIZE:
            return False, f"Order size {order.quantity} exceeds limit {self.MAX_ORDER_SIZE}"

        # Check daily order limit
        if self.daily_order_count >= self.MAX_DAILY_ORDERS:
            return False, f"Daily order limit {self.MAX_DAILY_ORDERS} reached"

        # Check position size
        estimated_value = order.quantity * (order.price or 0)
        new_position_value = current_position_value + estimated_value

        if abs(new_position_value) > self.MAX_POSITION_SIZE:
            return False, f"Position size would exceed limit {self.MAX_POSITION_SIZE}"

        return True, ""

    def record_order(self):
        """Record order placement"""
        self.daily_order_count += 1
```

### **Security Checklist**

✅ **DO:**
- Store credentials in `.env` file (gitignored)
- Use OAuth 2.0 with private_key_jwt for production
- Enable 2FA on IBKR account
- Restrict API access by IP address
- Use SSL/TLS for all connections
- Implement order size limits
- Log all security events
- Rotate credentials regularly
- Use separate accounts for paper/live trading
- Implement emergency kill switch

❌ **DON'T:**
- Hardcode credentials in source code
- Commit `.env` or private keys to git
- Disable SSL certificate verification (except testing)
- Share API credentials
- Use production credentials in development
- Allow unlimited order sizes
- Expose sensitive data in logs

---

## ⚡ Performance Optimization

### **1. Connection Pooling**

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session_with_retry() -> requests.Session:
    """Create session with connection pooling and retry logic"""

    session = requests.Session()

    # Retry configuration
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "DELETE"]
    )

    # Connection pooling
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,  # Number of connection pools
        pool_maxsize=20,      # Max connections per pool
        pool_block=False
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session
```

### **2. Response Caching**

```python
from functools import lru_cache
from datetime import datetime, timedelta
import hashlib

class CachedAPIClient:
    """API client with response caching"""

    def __init__(self, session: SessionManager):
        self.session = session
        self.cache = {}
        self.cache_ttl = {}

    def _cache_key(self, endpoint: str, params: dict = None) -> str:
        """Generate cache key"""
        key_data = f"{endpoint}:{str(sorted((params or {}).items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get_cached(self, endpoint: str, params: dict = None,
                    ttl_seconds: int = 60) -> dict:
        """
        Get with caching

        Args:
            endpoint: API endpoint
            params: Request parameters
            ttl_seconds: Cache time-to-live
        """
        cache_key = self._cache_key(endpoint, params)

        # Check cache
        if cache_key in self.cache:
            expiry = self.cache_ttl.get(cache_key)
            if expiry and datetime.now() < expiry:
                return self.cache[cache_key]

        # Cache miss - fetch from API
        response = self.session.session.get(endpoint, params=params)
        response.raise_for_status()

        data = response.json()

        # Update cache
        self.cache[cache_key] = data
        self.cache_ttl[cache_key] = datetime.now() + timedelta(seconds=ttl_seconds)

        return data

    def clear_cache(self, pattern: str = None):
        """Clear cache entries"""
        if pattern:
            # Clear matching entries
            keys_to_remove = [k for k in self.cache.keys() if pattern in k]
            for key in keys_to_remove:
                self.cache.pop(key, None)
                self.cache_ttl.pop(key, None)
        else:
            # Clear all
            self.cache.clear()
            self.cache_ttl.clear()


# Usage
cached_client = CachedAPIClient(session_manager)

# Cache account info for 5 minutes
account_info = cached_client.get_cached(
    '/iserver/account',
    ttl_seconds=300
)

# Cache positions for 30 seconds
positions = cached_client.get_cached(
    f'/portfolio/{account_id}/positions',
    ttl_seconds=30
)
```

### **3. Async Request Batching**

```python
import asyncio
import aiohttp

class AsyncAPIClient:
    """Async API client for concurrent requests"""

    def __init__(self, session_manager: SessionManager):
        self.session = session_manager
        self.base_url = session_manager.base_url

    async def get_async(self, endpoint: str, params: dict = None) -> dict:
        """Async GET request"""
        url = f"{self.base_url}{endpoint}"
        headers = self.session.session.headers

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, ssl=False) as response:
                response.raise_for_status()
                return await response.json()

    async def batch_get_market_data(self, conids: list[int]) -> dict[int, dict]:
        """Fetch market data for multiple contracts concurrently"""

        tasks = []
        for conid in conids:
            task = self.get_async(
                '/iserver/marketdata/snapshot',
                params={'conids': conid, 'fields': '31,84,86'}
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Map results back to contract IDs
        data_map = {}
        for conid, result in zip(conids, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch data for {conid}: {result}")
            else:
                data_map[conid] = result

        return data_map


# Usage
async def fetch_portfolio_data():
    """Fetch data for entire portfolio concurrently"""

    async_client = AsyncAPIClient(session_manager)

    # List of contract IDs in portfolio
    conids = [756733, 265598, 8314, ...]  # SPY, AAPL, MSFT, etc.

    # Fetch all market data concurrently
    market_data = await async_client.batch_get_market_data(conids)

    return market_data

# Run async function
market_data = asyncio.run(fetch_portfolio_data())
```

### **Performance Optimization Checklist**

✅ **DO:**
- Use connection pooling
- Cache frequently accessed data
- Batch requests when possible
- Use WebSocket for real-time data (not polling)
- Implement async/concurrent requests
- Monitor API response times
- Use CDN for static content
- Compress request/response data

❌ **DON'T:**
- Create new session for each request
- Poll REST endpoints for real-time data
- Make sequential requests that could be concurrent
- Cache sensitive data indefinitely
- Ignore slow query warnings

---

## 🔄 Migration from TWS API

### **Key Differences**

| Feature | TWS API (ib_async) | Client Portal Web API |
|---------|-------------------|----------------------|
| Protocol | Binary TCP | REST + WebSocket |
| Authentication | Username/Password | OAuth 2.0 / CP Gateway |
| Connection | Direct to TWS/Gateway | Via CP Gateway or OAuth |
| Language | Python (ib_async library) | Any (HTTP/WebSocket) |
| Session | Persistent connection | HTTP sessions + tickle |
| Market Data | reqMktData() | GET /marketdata + WebSocket |
| Orders | placeOrder() | POST /orders |
| Rate Limit | 50 msg/sec | 10-50 req/sec |

### **Migration Strategy**

#### **Phase 1: Parallel Implementation (2 weeks)**
- Implement new Client Portal client alongside existing TWS client
- Test in paper trading mode
- Validate data consistency between both APIs

#### **Phase 2: Feature Parity (3-4 weeks)**
- Implement all required endpoints (market data, orders, positions)
- Create adapter layer for backward compatibility
- Update all SpyderB_Broker modules

#### **Phase 3: Testing & Validation (2 weeks)**
- Comprehensive integration testing
- Performance benchmarking
- Load testing

#### **Phase 4: Cutover (1 week)**
- Switch production to Client Portal API
- Deprecate TWS API code
- Monitor for issues

### **Code Migration Examples**

#### **Market Data Subscription**

```python
# OLD: TWS API (ib_async)
from ib_async import IB, Stock

ib = IB()
ib.connect('127.0.0.1', 4002, clientId=1)

contract = Stock('SPY', 'SMART', 'USD')
ib.qualifyContracts(contract)
ticker = ib.reqMktData(contract)

def on_ticker_update(ticker):
    print(f"Price: {ticker.last}")

ticker.updateEvent += on_ticker_update
ib.run()

# NEW: Client Portal Web API
session_mgr = SessionManager('https://localhost:5000/v1/api', oauth_client)
session_mgr.start_session()

ws_client = MarketDataWebSocket(session_mgr)
ws_client.connect()

def on_market_data(data):
    print(f"Price: {data.get('31')}")  # Field 31 = last price

spy_conid = 756733
ws_client.subscribe(
    conid=spy_conid,
    fields=[31, 84, 86],  # last, bid, ask
    callback=on_market_data
)
```

#### **Order Placement**

```python
# OLD: TWS API
from ib_async import IB, Stock, MarketOrder

ib = IB()
ib.connect('127.0.0.1', 4002, clientId=1)

contract = Stock('SPY', 'SMART', 'USD')
order = MarketOrder('BUY', 100)

trade = ib.placeOrder(contract, order)
print(f"Order ID: {trade.order.orderId}")

# NEW: Client Portal Web API
session_mgr = SessionManager('https://localhost:5000/v1/api', oauth_client)
session_mgr.start_session()

order_mgr = OrderManager(session_mgr, rate_limiter)

order = Order(
    conid=756733,  # SPY
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    quantity=100,
    account_id='DU123456'
)

result = order_mgr.place_order(order)
print(f"Order ID: {result['order_id']}")
```

---

## ✅ Implementation Checklist

### **Setup**

- [ ] Download and install CP Gateway (or setup OAuth 2.0)
- [ ] Configure environment variables in `.env`
- [ ] Generate OAuth keys (if using OAuth)
- [ ] Configure SSL certificates
- [ ] Set up IP whitelisting in IBKR account settings
- [ ] Subscribe to required market data in IBKR account

### **Authentication**

- [ ] Implement OAuth 2.0 client (or CP Gateway auth)
- [ ] Implement session management
- [ ] Implement tickle keepalive
- [ ] Handle session expiration/renewal
- [ ] Test 24-hour session limit handling

### **API Clients**

- [ ] Implement REST API client with rate limiting
- [ ] Implement WebSocket client for real-time data
- [ ] Implement market data manager
- [ ] Implement order manager
- [ ] Implement position tracker
- [ ] Implement account manager

### **Error Handling**

- [ ] Implement retry logic with exponential backoff
- [ ] Handle authentication errors
- [ ] Handle rate limit errors (429)
- [ ] Handle network errors
- [ ] Implement error logging
- [ ] Implement circuit breaker pattern

### **Security**

- [ ] Store credentials securely (`.env`)
- [ ] Never commit credentials to git
- [ ] Use SSL/TLS for all connections
- [ ] Implement IP whitelisting
- [ ] Implement order size limits
- [ ] Enable 2FA on IBKR account
- [ ] Implement audit logging

### **Performance**

- [ ] Implement connection pooling
- [ ] Implement response caching
- [ ] Use WebSocket for real-time data (not polling)
- [ ] Implement async/concurrent requests where appropriate
- [ ] Monitor API response times
- [ ] Implement request batching

### **Testing**

- [ ] Unit tests for all components
- [ ] Integration tests with paper trading account
- [ ] Load testing for rate limits
- [ ] WebSocket reconnection testing
- [ ] Error scenario testing
- [ ] End-to-end trading workflow testing

### **Monitoring**

- [ ] Log all API requests/responses
- [ ] Monitor rate limit usage
- [ ] Monitor session health
- [ ] Track order success/failure rates
- [ ] Alert on authentication failures
- [ ] Dashboard for API metrics

### **Documentation**

- [ ] Document API client usage
- [ ] Document error handling patterns
- [ ] Document deployment process
- [ ] Create runbook for common issues
- [ ] Document migration from TWS API

---

## 📚 Additional Resources

- **Official Documentation:** https://interactivebrokers.github.io/cpwebapi/
- **IBKR Web API Campus:** https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/
- **OAuth 2.0 RFC:** https://tools.ietf.org/html/rfc6749
- **WebSocket RFC:** https://tools.ietf.org/html/rfc6455
- **GitHub Examples:** https://github.com/Voyz/ibind (Third-party library)

---

## 🆘 Troubleshooting

### **Common Issues**

1. **Session Timeout**
   - **Symptom:** 401 Unauthorized after ~6 minutes
   - **Solution:** Implement tickle keepalive every 4-5 minutes

2. **Rate Limit Exceeded**
   - **Symptom:** 429 Too Many Requests
   - **Solution:** Implement client-side rate limiting, reduce request frequency

3. **WebSocket Disconnections**
   - **Symptom:** WebSocket closes unexpectedly
   - **Solution:** Implement heartbeat, reconnection logic

4. **Market Data Not Updating**
   - **Symptom:** Stale data on WebSocket
   - **Solution:** Check market data subscriptions, verify market is open

5. **Order Confirmation Required**
   - **Symptom:** Order not immediately confirmed
   - **Solution:** Implement confirmation reply logic

---

## 📝 Summary

The Client Portal Web API provides a modern, REST-based interface for IBKR trading. Key takeaways:

1. **Use OAuth 2.0 for production** (CP Gateway for development)
2. **Implement tickle keepalive** every 4-5 minutes
3. **Use WebSocket for real-time data** (not polling)
4. **Implement robust rate limiting** (10-50 req/sec depending on auth method)
5. **Handle errors gracefully** with retries and backoff
6. **Secure credentials** in `.env` file
7. **Test thoroughly** in paper trading before live

**Next Steps:**
1. Review this document with development team
2. Setup CP Gateway or OAuth 2.0
3. Implement authentication and session management
4. Build REST and WebSocket clients
5. Migrate SpyderB_Broker modules
6. Test extensively in paper mode
7. Deploy to production

---

**Document Version:** 1.0
**Last Updated:** 2025-11-08
**Maintained By:** Spyder Development Team
