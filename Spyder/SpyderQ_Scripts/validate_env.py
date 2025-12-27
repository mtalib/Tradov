#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Environment Configuration Validator
Validates .env file for IBKR Web API OAuth 2.0 setup
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
load_dotenv()

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓{Colors.END} {text}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠{Colors.END} {text}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗{Colors.END} {text}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ{Colors.END} {text}")

def validate_env_file():
    """Validate .env file exists"""
    env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        print_error(f".env file not found at: {env_path}")
        print_info("Create .env from template:")
        print_info("  $ cp .env.example .env")
        return False

    print_success(f".env file found: {env_path}")
    return True

def validate_trading_mode():
    """Validate trading mode configuration"""
    print_header("TRADING MODE")

    errors = []
    warnings = []

    # Check TRADING_MODE
    trading_mode = os.environ.get("TRADING_MODE", "").lower()
    if not trading_mode:
        errors.append("TRADING_MODE not set")
    elif trading_mode not in ["paper", "live"]:
        errors.append(f"Invalid TRADING_MODE: '{trading_mode}' (must be 'paper' or 'live')")
    elif trading_mode == "paper":
        print_success(f"Trading Mode: {trading_mode} (SAFE)")
    else:
        print_warning(f"Trading Mode: {trading_mode} (LIVE - REAL MONEY)")

    # Check live trading confirmation
    if trading_mode == "live":
        live_confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "false").lower() == "true"
        require_confirmation = os.environ.get("REQUIRE_LIVE_CONFIRMATION", "true").lower() == "true"

        if require_confirmation and not live_confirmed:
            errors.append("LIVE mode requires LIVE_TRADING_CONFIRMED=true")
            print_error("Live trading blocked: LIVE_TRADING_CONFIRMED not set")
        elif not require_confirmation:
            warnings.append("REQUIRE_LIVE_CONFIRMATION=false (unsafe)")
        else:
            print_warning("Live trading CONFIRMED - will trade with real money")

    return errors, warnings

def validate_oauth_config():
    """Validate OAuth 2.0 configuration"""
    print_header("OAUTH 2.0 CONFIGURATION")

    errors = []
    warnings = []

    # Check API base URL
    api_url = os.environ.get("IBKR_API_BASE_URL", "")
    if not api_url:
        errors.append("IBKR_API_BASE_URL not set")
    elif api_url == "https://api.ibkr.com/v1/api":
        print_success(f"API URL: {api_url} (Production)")
    else:
        print_warning(f"API URL: {api_url} (Custom)")

    # Check OAuth token URL
    token_url = os.environ.get("IBKR_OAUTH_TOKEN_URL", "")
    if not token_url:
        errors.append("IBKR_OAUTH_TOKEN_URL not set")
    else:
        print_success(f"Token URL: {token_url}")

    # Check consumer key
    consumer_key = os.environ.get("IBKR_OAUTH_CONSUMER_KEY", "")
    if not consumer_key:
        errors.append("IBKR_OAUTH_CONSUMER_KEY not set")
    elif consumer_key == "your_consumer_key_here":
        errors.append("IBKR_OAUTH_CONSUMER_KEY is placeholder value")
        print_error("Consumer key not configured (still using placeholder)")
    else:
        print_success(f"Consumer Key: {consumer_key[:10]}... (configured)")

    # Check private key path
    key_path = os.environ.get("IBKR_OAUTH_PRIVATE_KEY_PATH", "")
    if not key_path:
        errors.append("IBKR_OAUTH_PRIVATE_KEY_PATH not set")
    else:
        key_file = Path(key_path)
        if not key_file.is_absolute():
            # Resolve relative to project root
            key_file = Path(__file__).parent.parent / key_path

        if not key_file.exists():
            errors.append(f"Private key file not found: {key_path}")
            print_error(f"Private key missing: {key_path}")
        else:
            print_success(f"Private Key: {key_path} (found)")

            # Check file permissions
            if key_file.stat().st_mode & 0o077:
                warnings.append(f"Private key has insecure permissions: {oct(key_file.stat().st_mode)}")
                print_warning("Private key permissions too open (should be 600)")
                print_info(f"  Fix with: chmod 600 {key_path}")

    # Check auth method
    auth_method = os.environ.get("IBKR_AUTH_METHOD", "oauth2")
    if auth_method != "oauth2":
        warnings.append(f"Unexpected auth method: {auth_method}")
    else:
        print_success(f"Auth Method: {auth_method}")

    return errors, warnings

def validate_account_config():
    """Validate account configuration"""
    print_header("ACCOUNT CONFIGURATION")

    errors = []
    warnings = []

    # Check account ID
    account_id = os.environ.get("IBKR_ACCOUNT_ID", "")
    if not account_id:
        warnings.append("IBKR_ACCOUNT_ID not set")
        print_warning("Account ID not configured")
    elif account_id == "DU1234567":
        errors.append("IBKR_ACCOUNT_ID is placeholder value")
        print_error("Account ID not configured (still using placeholder)")
    elif account_id.startswith("DU"):
        print_success(f"Account ID: {account_id} (PAPER account)")
    else:
        trading_mode = os.environ.get("TRADING_MODE", "").lower()
        if trading_mode == "paper":
            warnings.append(f"Paper mode but account {account_id} looks like live account")
            print_warning(f"Account {account_id} may be live account (expected DU...)")
        else:
            print_success(f"Account ID: {account_id} (LIVE account)")

    return errors, warnings

def validate_system_config():
    """Validate system configuration"""
    print_header("SYSTEM CONFIGURATION")

    warnings = []

    # Check log level
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    print_info(f"Log Level: {log_level}")

    # Check debug mode
    debug_mode = os.environ.get("DEBUG_MODE", "false").lower() == "true"
    if debug_mode:
        print_warning("Debug Mode: ENABLED (verbose logging)")
    else:
        print_success("Debug Mode: DISABLED")

    return [], warnings

def validate_notifications():
    """Validate notification configuration"""
    print_header("NOTIFICATIONS (Optional)")

    # Telegram
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if telegram_token and telegram_chat:
        print_success("Telegram: Configured")
    else:
        print_info("Telegram: Not configured (optional)")

    # Email
    email = os.environ.get("EMAIL_ADDRESS", "")
    email_pass = os.environ.get("EMAIL_PASSWORD", "")
    if email and email_pass:
        print_success(f"Email: Configured ({email})")
    else:
        print_info("Email: Not configured (optional)")

    return [], []

def print_summary(all_errors, all_warnings):
    """Print validation summary"""
    print_header("VALIDATION SUMMARY")

    total_errors = sum(len(e) for e in all_errors)
    total_warnings = sum(len(w) for w in all_warnings)

    if total_errors == 0 and total_warnings == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ CONFIGURATION VALID{Colors.END}")
        print(f"{Colors.GREEN}  All checks passed! Ready for paper trading.{Colors.END}\n")
        return True

    if total_errors > 0:
        print(f"{Colors.RED}{Colors.BOLD}✗ CONFIGURATION INVALID{Colors.END}")
        print(f"{Colors.RED}  {total_errors} error(s) found{Colors.END}\n")

        print(f"{Colors.BOLD}Errors:{Colors.END}")
        for error_list in all_errors:
            for error in error_list:
                print(f"  {Colors.RED}✗{Colors.END} {error}")
        print()

    if total_warnings > 0:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠ {total_warnings} warning(s) found{Colors.END}\n")
        print(f"{Colors.BOLD}Warnings:{Colors.END}")
        for warning_list in all_warnings:
            for warning in warning_list:
                print(f"  {Colors.YELLOW}⚠{Colors.END} {warning}")
        print()

    if total_errors > 0:
        print(f"{Colors.RED}Fix errors before running Spyder.{Colors.END}\n")
        return False
    elif total_warnings > 0:
        print(f"{Colors.YELLOW}Warnings should be addressed but system may run.{Colors.END}\n")
        return True

    return True

def main():
    """Main validation function"""
    print_header("SPYDER .ENV CONFIGURATION VALIDATOR")
    print_info("Validating IBKR Web API OAuth 2.0 configuration...\n")

    # Check .env file exists
    if not validate_env_file():
        sys.exit(1)

    print()

    # Run all validations
    all_errors = []
    all_warnings = []

    errors, warnings = validate_trading_mode()
    all_errors.append(errors)
    all_warnings.append(warnings)

    errors, warnings = validate_oauth_config()
    all_errors.append(errors)
    all_warnings.append(warnings)

    errors, warnings = validate_account_config()
    all_errors.append(errors)
    all_warnings.append(warnings)

    errors, warnings = validate_system_config()
    all_errors.append(errors)
    all_warnings.append(warnings)

    errors, warnings = validate_notifications()
    all_errors.append(errors)
    all_warnings.append(warnings)

    # Print summary
    is_valid = print_summary(all_errors, all_warnings)

    if is_valid:
        print(f"{Colors.BOLD}Next Steps:{Colors.END}")
        print("  1. Ensure OAuth app is registered with IBKR")
        print("  2. Generate RSA key pair if not done:")
        print("     $ mkdir -p config/keys")
        print("     $ openssl genrsa -out config/keys/private_key.pem 2048")
        print("     $ openssl rsa -in config/keys/private_key.pem -pubout -out config/keys/public_key.pem")
        print("  3. Upload public key to IBKR OAuth app settings")
        print("  4. Test configuration:")
        print("     $ python config/config.py")
        print("  5. Run tests:")
        print("     $ python SpyderT_Testing/SpyderT23_ClientPortal_Auth_Test.py")
        print("  6. Start paper trading:")
        print("     $ python SpyderA_Core/SpyderA01_Main.py")
        print()
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
