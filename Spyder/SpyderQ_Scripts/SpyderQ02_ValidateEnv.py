#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: validate_env.py
Purpose: SPYDER - Environment Configuration Validator (Tradier)

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-07 Time: 00:00:00

Module Description:
    Validates .env configuration for Tradier-backed paper/live workflows.
    Run this script before starting Spyder to confirm required variables
    are present and correctly formatted.

Change Log:
    2026-04-07:
    - Removed stale provider-migration references
    2026-03-03:
        - Removed legacy broker OAuth validation (broker migrated to Tradier)
        - Added Tradier API key and account validation
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from dotenv import load_dotenv

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
    script_path = Path(__file__).resolve()
    env_candidates = [
        script_path.parents[2] / ".env",  # repo root
        script_path.parents[1] / ".env",  # legacy in-package fallback
    ]
    env_path = next((p for p in env_candidates if p.exists()), env_candidates[0])

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

    trading_mode = os.environ.get("TRADING_MODE", "").lower()
    if not trading_mode:
        errors.append("TRADING_MODE not set")
    elif trading_mode not in ["sandbox", "paper", "live"]:
        errors.append(f"Invalid TRADING_MODE: '{trading_mode}' (must be 'sandbox', 'paper', or 'live')")
    elif trading_mode in ("sandbox", "paper"):
        print_success(f"Trading Mode: {trading_mode} (SAFE — no real money)")
    else:
        print_warning(f"Trading Mode: {trading_mode} (LIVE — REAL MONEY)")

    if trading_mode == "paper":
        paper_source_raw = os.environ.get(
            "SPYDER_PAPER_ACCOUNT_SOURCE",
            "spyderbox_local",
        ).strip().lower()
        if paper_source_raw in {"spyderbox", "spyderbox_local", "local", "internal", "db"}:
            print_success("Paper Account Source: spyderbox_local (SpyderBox-local paper ledger)")
        else:
            warnings.append(
                "SPYDER_PAPER_ACCOUNT_SOURCE is not local; policy forces spyderbox_local in paper mode"
            )
            print_warning(
                "Paper Account Source override ignored — using spyderbox_local "
                "(sandbox fallback disabled)"
            )

    if trading_mode == "live":
        live_confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "false").lower() == "true"
        require_confirmation = os.environ.get("REQUIRE_LIVE_CONFIRMATION", "true").lower() == "true"

        if require_confirmation and not live_confirmed:
            errors.append("LIVE mode requires LIVE_TRADING_CONFIRMED=true")
            print_error("Live trading blocked: LIVE_TRADING_CONFIRMED not set to 'true'")
        elif not require_confirmation:
            warnings.append("REQUIRE_LIVE_CONFIRMATION=false (unsafe — strongly discouraged)")
        else:
            print_warning("Live trading CONFIRMED — will trade with real money")

    return errors, warnings

def validate_tradier_config():
    """Validate Tradier broker credentials"""
    print_header("TRADIER BROKER CONFIGURATION")

    errors = []
    warnings = []

    # API Key
    api_key = os.environ.get("TRADIER_API_KEY", "")
    if not api_key:
        errors.append("TRADIER_API_KEY not set")
        print_error("TRADIER_API_KEY missing")
    elif api_key == "your_tradier_api_key_here":
        errors.append("TRADIER_API_KEY is still the placeholder value")
        print_error("TRADIER_API_KEY not configured (still using placeholder)")
    else:
        print_success(f"TRADIER_API_KEY: {api_key[:8]}... (configured)")

    # Account ID
    account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
    if not account_id:
        errors.append("TRADIER_ACCOUNT_ID not set")
        print_error("TRADIER_ACCOUNT_ID missing")
    else:
        print_success(f"TRADIER_ACCOUNT_ID: {account_id} (configured)")

    # Environment
    tradier_env_raw = os.environ.get("TRADIER_ENVIRONMENT", "sandbox").strip().lower()
    if tradier_env_raw in ("live", "production"):
        tradier_env = "live"
    elif tradier_env_raw == "sandbox":
        tradier_env = "sandbox"
    else:
        tradier_env = "invalid"

    if tradier_env == "invalid":
        errors.append(
            f"TRADIER_ENVIRONMENT='{tradier_env_raw}' is invalid; "
            "must be 'sandbox', 'live', or 'production'"
        )
    elif tradier_env == "sandbox":
        print_success("TRADIER_ENVIRONMENT: sandbox (safe — connects to https://sandbox.tradier.com)")
    else:
        trading_mode = os.environ.get("TRADING_MODE", "").strip().lower()
        if trading_mode == "paper":
            print_success(
                "TRADIER_ENVIRONMENT: live (paper mode — live quotes, simulated fills)"
            )
        else:
            print_warning("TRADIER_ENVIRONMENT: live (LIVE endpoint — real-money capable)")
            if trading_mode == "sandbox":
                warnings.append(
                    "TRADIER_ENVIRONMENT=live but TRADING_MODE='sandbox' — "
                    "set TRADING_MODE=paper/live or switch TRADIER_ENVIRONMENT to sandbox"
                )

    return errors, warnings

def validate_system_config():
    """Validate system configuration"""
    print_header("SYSTEM CONFIGURATION")

    warnings = []

    log_level = os.environ.get("LOG_LEVEL", "INFO")
    print_info(f"Log Level: {log_level}")

    debug_mode = os.environ.get("DEBUG_MODE", "false").lower() == "true"
    if debug_mode:
        print_warning("Debug Mode: ENABLED (verbose logging)")
    else:
        print_success("Debug Mode: DISABLED")

    return [], warnings

def validate_notifications():
    """Validate notification configuration"""
    print_header("NOTIFICATIONS (Optional)")

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if telegram_token and telegram_chat:
        print_success("Telegram: Configured")
    else:
        print_info("Telegram: Not configured (optional)")

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
        print(f"{Colors.GREEN}  All checks passed! Ready to run Spyder.{Colors.END}\n")
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
    else:
        print(f"{Colors.YELLOW}Warnings should be addressed but system may run.{Colors.END}\n")
        return True

def main():
    """Main validation function"""
    print_header("SPYDER .ENV CONFIGURATION VALIDATOR")
    market_data_provider = str(
        os.environ.get("MARKET_DATA_PROVIDER")
        or os.environ.get("DATA_PROVIDER")
        or "tradier"
    ).strip().lower()
    provider_label = market_data_provider.capitalize() if market_data_provider else "Tradier"
    print_info(f"Broker: Tradier  |  Market Data: {provider_label}\n")

    if not validate_env_file():
        sys.exit(1)

    print()

    all_errors = []
    all_warnings = []

    errors, warnings = validate_trading_mode()
    all_errors.append(errors)
    all_warnings.append(warnings)

    errors, warnings = validate_tradier_config()
    all_errors.append(errors)
    all_warnings.append(warnings)

    errors, warnings = validate_system_config()
    all_errors.append(errors)
    all_warnings.append(warnings)

    errors, warnings = validate_notifications()
    all_errors.append(errors)
    all_warnings.append(warnings)

    is_valid = print_summary(all_errors, all_warnings)

    if is_valid:
        print(f"{Colors.BOLD}Next Steps:{Colors.END}")
        print("  1. Obtain Tradier API key: https://developer.tradier.com")
        print("  2. Set TRADING_MODE=paper and TRADIER_ENVIRONMENT=live for paper trading with live quotes")
        print("  4. Test configuration:")
        print("     $ python config/config.py")
        print("  5. Run tests:")
        print("     $ pytest SpyderT_Testing/")
        print("  6. Start paper trading:")
        print("     $ python SpyderA_Core/SpyderA01_Main.py")
        print()
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
