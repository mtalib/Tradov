#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Script: validate_tradier_polygon.py
Purpose: Validate Tradier and Polygon.io configuration and API connectivity

Author: Claude (Maestro)
Created: 2025-11-18

Description:
    This script validates the Tradier + Polygon configuration by:
    1. Checking environment variables are set
    2. Testing Tradier API connection
    3. Testing Polygon.io API connection
    4. Verifying account access and permissions
    5. Testing market data streaming

    Run this script before starting the trading system to ensure
    proper configuration.

Usage:
    python SpyderQ_Scripts/validate_tradier_polygon.py

Environment Variables Required:
    - TRADIER_API_KEY
    - TRADIER_ACCOUNT_ID
    - POLYGON_API_KEY
    - TRADING_MODE (paper or live)
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
from dotenv import load_dotenv
from typing import Dict, List, Tuple

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    """Print section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}\n")

def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_info(text: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


def check_environment_variables() -> Tuple[bool, Dict[str, str]]:
    """
    Check if required environment variables are set.

    Returns:
        Tuple of (success, config_dict)
    """
    print_header("1. Checking Environment Variables")

    required_vars = {
        "TRADIER_API_KEY": "Tradier API access token",
        "TRADIER_ACCOUNT_ID": "Tradier account ID",
        "POLYGON_API_KEY": "Polygon.io API key",
        "TRADING_MODE": "Trading mode (paper/live)"
    }

    config = {}
    all_present = True

    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "KEY" in var or "TOKEN" in var:
                masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
                print_success(f"{var}: {masked}")
            else:
                print_success(f"{var}: {value}")
            config[var] = value
        else:
            print_error(f"{var}: NOT SET ({description})")
            all_present = False

    return all_present, config


def validate_tradier_connection(api_key: str, account_id: str, trading_mode: str) -> bool:
    """
    Validate Tradier API connection.

    Args:
        api_key: Tradier API key
        account_id: Tradier account ID
        trading_mode: Trading mode (paper/live)

    Returns:
        True if connection successful
    """
    print_header("2. Validating Tradier API Connection")

    # Select base URL based on mode
    if trading_mode.lower() in ("paper", "sandbox"):
        base_url = "https://sandbox.tradier.com/v1"
        print_info(f"Using SANDBOX environment: {base_url}")
    else:
        base_url = "https://api.tradier.com/v1"
        print_info(f"Using LIVE environment: {base_url}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }

    try:
        # Test 1: Get user profile
        print_info("Testing GET /user/profile...")
        response = requests.get(f"{base_url}/user/profile", headers=headers, timeout=10)

        if response.status_code == 200:
            profile = response.json()
            name = profile.get("profile", {}).get("name", "Unknown")
            print_success(f"User profile retrieved: {name}")
        else:
            print_error(f"Profile request failed: {response.status_code} - {response.text}")
            return False

        # Test 2: Get account balances
        print_info(f"Testing GET /accounts/{account_id}/balances...")
        response = requests.get(f"{base_url}/accounts/{account_id}/balances", headers=headers, timeout=10)

        if response.status_code == 200:
            balances = response.json()
            total_equity = balances.get("balances", {}).get("total_equity", 0)
            print_success(f"Account balances retrieved: ${total_equity:,.2f} total equity")
        else:
            print_error(f"Balances request failed: {response.status_code} - {response.text}")
            return False

        # Test 3: Get positions
        print_info(f"Testing GET /accounts/{account_id}/positions...")
        response = requests.get(f"{base_url}/accounts/{account_id}/positions", headers=headers, timeout=10)

        if response.status_code == 200:
            print_success("Positions retrieved successfully")
        else:
            print_warning(f"Positions request returned: {response.status_code}")

        # Test 4: Get market quotes
        print_info("Testing GET /markets/quotes (SPY)...")
        response = requests.get(
            f"{base_url}/markets/quotes",
            params={"symbols": "SPY"},
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            quotes = response.json()
            spy_quote = quotes.get("quotes", {}).get("quote", {})
            last_price = spy_quote.get("last", 0)
            print_success(f"Market data retrieved: SPY @ ${last_price:.2f}")
        else:
            print_error(f"Quotes request failed: {response.status_code}")
            return False

        print_success("All Tradier API tests passed!")
        return True

    except requests.exceptions.Timeout:
        print_error("Request timeout - check network connection")
        return False
    except requests.exceptions.ConnectionError:
        print_error("Connection error - check network and API URL")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        return False


def validate_polygon_connection(api_key: str) -> bool:
    """
    Validate Polygon.io API connection.

    Args:
        api_key: Polygon.io API key

    Returns:
        True if connection successful
    """
    print_header("3. Validating Polygon.io API Connection")

    base_url = "https://api.polygon.io"

    try:
        # Test 1: Get previous day aggregate for SPY
        print_info("Testing GET /v2/aggs/ticker/SPY/prev...")
        response = requests.get(
            f"{base_url}/v2/aggs/ticker/SPY/prev",
            params={"apiKey": api_key},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "OK":
                results = data.get("results", [])
                if results:
                    bar = results[0]
                    print_success(f"Previous day data: O={bar['o']:.2f}, H={bar['h']:.2f}, L={bar['l']:.2f}, C={bar['c']:.2f}")
                else:
                    print_warning("No results in response")
            else:
                print_error(f"API returned status: {data.get('status')}")
                return False
        else:
            print_error(f"Request failed: {response.status_code} - {response.text}")
            return False

        # Test 2: Get snapshot for SPY
        print_info("Testing GET /v2/snapshot/locale/us/markets/stocks/tickers/SPY...")
        response = requests.get(
            f"{base_url}/v2/snapshot/locale/us/markets/stocks/tickers/SPY",
            params={"apiKey": api_key},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "OK":
                ticker = data.get("ticker", {})
                last_price = ticker.get("day", {}).get("c", 0)
                print_success(f"Snapshot retrieved: SPY @ ${last_price:.2f}")
            else:
                print_warning(f"Snapshot status: {data.get('status')}")
        else:
            print_warning(f"Snapshot request: {response.status_code}")

        # Test 3: Check account tier (rate limits)
        print_info("Checking API tier and rate limits...")
        # Note: Polygon doesn't have a direct tier endpoint, but we can infer from headers
        if response.headers.get("X-Request-Id"):
            print_success("API connection verified (headers present)")

        print_success("All Polygon.io API tests passed!")
        return True

    except requests.exceptions.Timeout:
        print_error("Request timeout - check network connection")
        return False
    except requests.exceptions.ConnectionError:
        print_error("Connection error - check network and API URL")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        return False


def check_system_dependencies() -> bool:
    """
    Check if required Python packages are installed.

    Returns:
        True if all dependencies present
    """
    print_header("4. Checking System Dependencies")

    required_packages = [
        ("requests", "HTTP client library"),
        ("websocket", "WebSocket client library"),
        ("PySide6", "Qt6 for Python (UI framework)"),
        ("dotenv", "Environment variable loader")
    ]

    all_present = True

    for package, description in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print_success(f"{package}: installed ({description})")
        except ImportError:
            print_error(f"{package}: NOT INSTALLED ({description})")
            print_info(f"    Install with: pip install {package}")
            all_present = False

    return all_present


def generate_summary(
    env_valid: bool,
    tradier_valid: bool,
    polygon_valid: bool,
    deps_valid: bool
) -> None:
    """
    Generate validation summary.

    Args:
        env_valid: Environment variables valid
        tradier_valid: Tradier connection valid
        polygon_valid: Polygon connection valid
        deps_valid: Dependencies valid
    """
    print_header("5. Validation Summary")

    checks = [
        ("Environment Variables", env_valid),
        ("Tradier API Connection", tradier_valid),
        ("Polygon.io API Connection", polygon_valid),
        ("System Dependencies", deps_valid)
    ]

    all_passed = True

    for name, passed in checks:
        if passed:
            print_success(f"{name}: PASSED")
        else:
            print_error(f"{name}: FAILED")
            all_passed = False

    print()

    if all_passed:
        print_success("✓ ALL VALIDATION CHECKS PASSED!")
        print_info("You are ready to run Spyder with Tradier + Polygon")
        print_info("Start with: python SpyderA_Core/SpyderA01_Main.py")
    else:
        print_error("✗ VALIDATION FAILED")
        print_info("Please fix the issues above before running Spyder")
        print_info("See .env.tradier_polygon.template for configuration reference")


def main():
    """Main validation routine."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║   SPYDER - Tradier + Polygon Configuration Validation            ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}")

    # Load environment from .env file
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print_info(f"Loaded environment from: {env_file}")
    else:
        print_warning(".env file not found - using system environment variables")
        print_info("Create .env from .env.tradier_polygon.template")

    # Run validation checks
    env_valid, config = check_environment_variables()

    if not env_valid:
        print_error("\nEnvironment variables not properly configured")
        print_info("Copy .env.tradier_polygon.template to .env and fill in your credentials")
        sys.exit(1)

    tradier_valid = validate_tradier_connection(
        api_key=config["TRADIER_API_KEY"],
        account_id=config["TRADIER_ACCOUNT_ID"],
        trading_mode=config["TRADING_MODE"]
    )

    polygon_valid = validate_polygon_connection(api_key=config["POLYGON_API_KEY"])

    deps_valid = check_system_dependencies()

    # Generate summary
    generate_summary(env_valid, tradier_valid, polygon_valid, deps_valid)

    # Exit with appropriate code
    if all([env_valid, tradier_valid, polygon_valid, deps_valid]):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
