#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB09_ClientPortal_Examples.py
Purpose: Complete usage examples demonstrating Client Portal API components

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-11-09 Time: 12:45:00

Module Description:
    Comprehensive usage examples for the Client Portal API, demonstrating:

    EXAMPLE 1: CP Gateway Basic Usage (Development/Paper Trading)
    - Setting up CP Gateway authentication
    - Creating session manager with automatic tickle
    - Making basic API requests
    - Proper session cleanup

    EXAMPLE 2: OAuth 2.0 Production Usage
    - OAuth 2.0 authentication with consumer key
    - Production-ready configuration
    - Higher rate limits (50 req/sec)
    - Access token management

    EXAMPLE 3: Context Manager Pattern
    - Using SessionManager as context manager
    - Automatic resource cleanup with 'with' statement
    - Exception handling within context

    EXAMPLE 4: Error Handling & Retry Logic
    - Comprehensive error handling patterns
    - Retry strategies with exponential backoff
    - Rate limit error recovery
    - Authentication error handling

    Prerequisites:
    - CP Gateway: Download from IBKR, run locally on port 5000
    - OAuth 2.0: Obtain consumer key from IBKR portal
    - Paper/Live Account: IBKR account with API access enabled

Module Constants:
    None - This is an examples/demonstration module

Change Log:
    2025-11-08 (v1.0.0):
        - Initial examples for OAuth 2.0 and CP Gateway
        - Context manager usage pattern
        - Error handling demonstrations
    2025-11-09 (v1.0.1):
        - Refactored to follow 1-SPECS format standard
        - Integrated SpyderLogger replacing standard logging
        - Updated module header with Series, Purpose, and description

References:
    - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md
    - https://interactivebrokers.github.io/cpwebapi/
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# (None required)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# Initialize logger
logger = SpyderLogger.get_logger(__name__)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

__all__ = [
    'example_1_cp_gateway_basic',
    'example_2_oauth_production',
    'example_3_with_context_manager',
    'example_4_error_handling',
    'main',
]


# ==============================================================================
# EXAMPLE FUNCTIONS
# ==============================================================================

def example_1_cp_gateway_basic():
    """
    Example 1: Basic usage with CP Gateway (Development/Paper Trading)

    Prerequisites:
    1. Download and run CP Gateway from IBKR
    2. Authenticate via browser at https://localhost:5000
    3. Ensure gateway is running on port 5000
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic CP Gateway Usage")
    print("=" * 70)

    try:
        from SpyderB_Broker.ClientPortalAPI import (
            CPGatewayAuth,
            CPGatewayConfig,
            SessionManager,
            ClientPortalRESTClient
        )

        # Step 1: Configure CP Gateway
        print("\n1️⃣  Configuring CP Gateway...")
        gateway_config = CPGatewayConfig(
            host='localhost',
            port=5000,
            ssl=True  # Gateway uses HTTPS with self-signed cert
        )
        print(f"   Gateway URL: {gateway_config.base_url}")

        # Step 2: Create authentication
        print("\n2️⃣  Creating authentication...")
        auth = CPGatewayAuth(gateway_config)

        # Check if authenticated
        if not auth.is_authenticated():
            print("   ❌ Not authenticated!")
            print("   Please open https://localhost:5000 in your browser")
            print("   and complete the login process.")
            return
        print("   ✅ Authenticated!")

        # Step 3: Create session manager
        print("\n3️⃣  Creating session manager...")
        session_mgr = SessionManager(
            auth_client=auth,
            base_url=gateway_config.base_url
        )
        session_mgr.start()
        print("   ✅ Session started (tickle every 4 minutes)")

        # Step 4: Create REST client
        print("\n4️⃣  Creating REST client...")
        client = ClientPortalRESTClient(session_mgr)
        print(f"   ✅ Client ready (rate limit: {client.config.rate_limit} req/sec)")

        # Step 5: Make some API calls
        print("\n5️⃣  Making API calls...")

        # Get accounts
        print("   📊 Fetching accounts...")
        accounts = client.get_accounts()
        print(f"   Found {len(accounts)} accounts:")
        for account in accounts:
            print(f"      - {account.get('id')}: {account.get('type')}")

        # Get positions for first account
        if accounts:
            account_id = accounts[0]['id']
            print(f"\n   📈 Fetching positions for {account_id}...")
            try:
                positions = client.get_positions(account_id)
                print(f"   Found {len(positions)} positions")
                for pos in positions[:3]:  # Show first 3
                    print(f"      - {pos.get('contractDesc')}: {pos.get('position')} @ {pos.get('avgCost')}")
            except Exception as e:
                print(f"   ⚠️  Could not fetch positions: {e}")

        # Get market data for SPY
        print("\n   💹 Fetching market data for SPY...")
        try:
            spy_data = client.get_market_data_snapshot(
                conids=[756733],  # SPY contract ID
                fields=[31, 84, 86]  # last, bid, ask
            )
            if spy_data:
                data = spy_data[0]
                print(f"   SPY: Last={data.get('31')}, Bid={data.get('84')}, Ask={data.get('86')}")
        except Exception as e:
            print(f"   ⚠️  Could not fetch market data: {e}")

        # Step 6: Show statistics
        print("\n6️⃣  Statistics:")
        client_stats = client.get_stats()
        print(f"   Total requests: {client_stats['total_requests']}")
        print(f"   Success rate: {client_stats['success_rate']:.1f}%")

        session_stats = session_mgr.get_stats()
        print(f"   Session age: {session_stats['session_age_hours']:.2f} hours")
        print(f"   Tickle count: {session_stats['tickle_count']}")

        # Step 7: Cleanup
        print("\n7️⃣  Cleaning up...")
        session_mgr.stop()
        print("   ✅ Session stopped")

        print("\n✅ Example completed successfully!")

    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)
        print(f"\n❌ Example failed: {e}")


def example_2_oauth_production():
    """
    Example 2: OAuth 2.0 for Production/Institutional Accounts

    Prerequisites:
    1. Obtain OAuth consumer key from IBKR
    2. Generate RSA private key
    3. Set environment variables:
       - IBKR_CONSUMER_KEY
       - IBKR_PRIVATE_KEY_PATH
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 2: OAuth 2.0 Production Usage")
    print("=" * 70)

    try:
        from SpyderB_Broker.ClientPortalAPI import (
            create_oauth_client_from_env,
            SessionManager,
            ClientPortalRESTClient
        )

        # Check if credentials are available
        if not os.getenv('IBKR_CONSUMER_KEY') or not os.getenv('IBKR_PRIVATE_KEY_PATH'):
            print("\n⚠️  OAuth credentials not found in environment")
            print("   Set these environment variables:")
            print("     - IBKR_CONSUMER_KEY")
            print("     - IBKR_PRIVATE_KEY_PATH")
            print("\n   This example is for institutional/production accounts.")
            return

        # Step 1: Create OAuth client
        print("\n1️⃣  Creating OAuth client from environment...")
        oauth_client = create_oauth_client_from_env()
        print("   ✅ OAuth client created")

        # Step 2: Get access token
        print("\n2️⃣  Obtaining access token...")
        token = oauth_client.get_access_token()
        print(f"   ✅ Token obtained: {token[:20]}...")
        print(f"   Token expires at: {oauth_client.token_expiry}")

        # Step 3: Create session manager
        print("\n3️⃣  Creating session manager...")
        session_mgr = SessionManager(
            auth_client=oauth_client,
            base_url="https://api.ibkr.com/v1/api"
        )
        session_mgr.start()
        print("   ✅ Session started")

        # Step 4: Create REST client
        print("\n4️⃣  Creating REST client...")
        client = ClientPortalRESTClient(session_mgr)
        print(f"   ✅ Client ready (rate limit: {client.config.rate_limit} req/sec)")

        # Step 5: Make API calls
        print("\n5️⃣  Making API calls...")
        accounts = client.get_accounts()
        print(f"   Found {len(accounts)} accounts")

        # Cleanup
        session_mgr.stop()

        print("\n✅ OAuth example completed successfully!")

    except Exception as e:
        logger.error(f"OAuth example failed: {e}", exc_info=True)
        print(f"\n❌ OAuth example failed: {e}")


def example_3_with_context_manager():
    """
    Example 3: Using context manager for automatic cleanup
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Context Manager Usage (Automatic Cleanup)")
    print("=" * 70)

    try:
        from SpyderB_Broker.ClientPortalAPI import (
            CPGatewayAuth,
            CPGatewayConfig,
            SessionManager,
            ClientPortalRESTClient
        )

        gateway_config = CPGatewayConfig(host='localhost', port=5000)
        auth = CPGatewayAuth(gateway_config)

        if not auth.is_authenticated():
            print("   ❌ Not authenticated! Please login at https://localhost:5000")
            return

        # Context manager automatically starts and stops session
        print("\n📍 Using context manager (auto cleanup)...")

        with SessionManager(auth, gateway_config.base_url) as session_mgr:
            print("   ✅ Session started")

            client = ClientPortalRESTClient(session_mgr)

            # Make API calls
            accounts = client.get_accounts()
            print(f"   Found {len(accounts)} accounts")

            # Session will automatically stop when exiting the 'with' block
            print("   Session will auto-stop on exit...")

        print("   ✅ Session stopped automatically!")

    except Exception as e:
        logger.error(f"Context manager example failed: {e}", exc_info=True)
        print(f"\n❌ Example failed: {e}")


def example_4_error_handling():
    """
    Example 4: Error handling and retry logic
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Error Handling and Retry Logic")
    print("=" * 70)

    try:
        from SpyderB_Broker.ClientPortalAPI import (
            CPGatewayAuth,
            CPGatewayConfig,
            SessionManager,
            ClientPortalRESTClient,
            APIError,
            RateLimitError,
            AuthenticationError
        )

        gateway_config = CPGatewayConfig(host='localhost', port=5000)
        auth = CPGatewayAuth(gateway_config)

        if not auth.is_authenticated():
            print("   ❌ Not authenticated!")
            return

        with SessionManager(auth, gateway_config.base_url) as session_mgr:
            client = ClientPortalRESTClient(session_mgr)

            print("\n📍 Demonstrating error handling...")

            # Valid request
            print("\n   ✅ Making valid request...")
            try:
                accounts = client.get_accounts()
                print(f"   Success: Found {len(accounts)} accounts")
            except APIError as e:
                print(f"   ❌ API Error: {e}")

            # Invalid endpoint (will fail)
            print("\n   ⚠️  Making invalid request (should fail)...")
            try:
                result = client.get('/invalid/endpoint/that/does/not/exist')
                print(f"   Unexpected success: {result}")
            except APIError as e:
                print(f"   ✅ Expected error caught: {type(e).__name__}")

            # Show statistics
            stats = client.get_stats()
            print(f"\n   📊 Statistics:")
            print(f"      Total requests: {stats['total_requests']}")
            print(f"      Successful: {stats['successful_requests']}")
            print(f"      Failed: {stats['failed_requests']}")
            print(f"      Success rate: {stats['success_rate']:.1f}%")

    except Exception as e:
        logger.error(f"Error handling example failed: {e}", exc_info=True)
        print(f"\n❌ Example failed: {e}")


def main():
    """Run all examples"""
    print("=" * 70)
    print("IBKR CLIENT PORTAL API - COMPLETE USAGE EXAMPLES")
    print("=" * 70)

    examples = [
        ("Basic CP Gateway Usage", example_1_cp_gateway_basic),
        ("OAuth 2.0 Production", example_2_oauth_production),
        ("Context Manager", example_3_with_context_manager),
        ("Error Handling", example_4_error_handling),
    ]

    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\n" + "-" * 70)
    choice = input("\nEnter example number to run (or 'all' for all examples): ").strip()

    if choice.lower() == 'all':
        for name, func in examples:
            func()
    elif choice.isdigit() and 1 <= int(choice) <= len(examples):
        examples[int(choice) - 1][1]()
    else:
        print("Invalid choice")

    print("\n" + "=" * 70)
    print("Examples complete!")
    print("=" * 70)
    print("\nFor more information:")
    print("  - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md")
    print("  - https://interactivebrokers.github.io/cpwebapi/")


if __name__ == '__main__':
    # Initialize SpyderLogger for main execution
    SpyderLogger.initialize(log_level='INFO')
    main()
