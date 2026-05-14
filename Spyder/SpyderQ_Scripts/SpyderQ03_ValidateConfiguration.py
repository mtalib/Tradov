#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: validate_configuration.py
Purpose: SPYDER - Configuration Validator

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Configuration Validator

Change Log:
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
from enum import Enum

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class ValidationLevel(Enum):
    """Validation severity levels"""
    ERROR = "ERROR"  # Blocks startup
    WARNING = "WARNING"  # Allows startup but issues warning
    INFO = "INFO"  # Informational only


class ValidationResult:
    """Result of a validation check"""

    def __init__(
        self,
        key: str,
        level: ValidationLevel,
        message: str,
        suggestion: str | None = None
    ):
        self.key = key
        self.level = level
        self.message = message
        self.suggestion = suggestion

    def __str__(self) -> str:
        result = f"[{self.level.value}] {self.key}: {self.message}"
        if self.suggestion:
            result += f"\n  → {self.suggestion}"
        return result


class ConfigurationValidator:
    """Validates Spyder system configuration"""

    def __init__(self):
        self.errors: list[ValidationResult] = []
        self.warnings: list[ValidationResult] = []
        self.info: list[ValidationResult] = []

    def add_result(self, result: ValidationResult):
        """Add validation result"""
        if result.level == ValidationLevel.ERROR:
            self.errors.append(result)
        elif result.level == ValidationLevel.WARNING:
            self.warnings.append(result)
        else:
            self.info.append(result)

    def validate_all(self) -> bool:
        """
        Run all validation checks.

        Returns:
            bool: True if no errors, False otherwise
        """
        print("=" * 70)
        print("SPYDER CONFIGURATION VALIDATOR")
        print("=" * 70)
        print()

        # Run all validation checks
        self._validate_trading_mode()
        self._validate_tradier_config()
        self._validate_risk_config()
        self._validate_logging_config()
        self._validate_security_config()

        # Display results
        self._display_results()

        return len(self.errors) == 0

    def _validate_trading_mode(self):
        """Validate trading mode configuration"""
        mode = os.environ.get("TRADING_MODE", "").lower()

        if not mode:
            self.add_result(ValidationResult(
                "TRADING_MODE",
                ValidationLevel.ERROR,
                "Not set",
                "Set TRADING_MODE=paper in .env file"
            ))
        elif mode not in ["paper", "live"]:
            self.add_result(ValidationResult(
                "TRADING_MODE",
                ValidationLevel.ERROR,
                f"Invalid value: '{mode}'",
                "Must be 'paper' or 'live'"
            ))
        elif mode == "live":
            # Extra checks for live trading
            confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "").lower()
            if confirmed != "true":
                self.add_result(ValidationResult(
                    "LIVE_TRADING_CONFIRMED",
                    ValidationLevel.ERROR,
                    "Live trading not confirmed",
                    "Set LIVE_TRADING_CONFIRMED=true to enable live trading"
                ))
            else:
                self.add_result(ValidationResult(
                    "TRADING_MODE",
                    ValidationLevel.WARNING,
                    "⚠️  LIVE TRADING MODE ENABLED - Real money at risk!",
                    None
                ))
        else:
            self.add_result(ValidationResult(
                "TRADING_MODE",
                ValidationLevel.INFO,
                f"Set to '{mode}' (safe mode)",
                None
            ))

    def _validate_tradier_config(self):
        """Validate Tradier API configuration"""
        api_key = os.environ.get("TRADIER_API_KEY", "")
        account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")

        # API Key validation
        if not api_key:
            self.add_result(ValidationResult(
                "TRADIER_API_KEY",
                ValidationLevel.ERROR,
                "Not set",
                "Get API key from https://brokerage.tradier.com/"
            ))
        elif api_key == "your_tradier_api_key_here":
            self.add_result(ValidationResult(
                "TRADIER_API_KEY",
                ValidationLevel.ERROR,
                "Using template value",
                "Replace with actual Tradier API key"
            ))
        elif len(api_key) < 20:
            self.add_result(ValidationResult(
                "TRADIER_API_KEY",
                ValidationLevel.WARNING,
                "Appears too short, may be invalid",
                "Verify API key format"
            ))
        else:
            self.add_result(ValidationResult(
                "TRADIER_API_KEY",
                ValidationLevel.INFO,
                "Present (not validating actual key)",
                None
            ))

        # Account ID validation
        if not account_id:
            self.add_result(ValidationResult(
                "TRADIER_ACCOUNT_ID",
                ValidationLevel.ERROR,
                "Not set",
                "Get account ID from Tradier dashboard"
            ))
        elif account_id == "your_account_id_here":
            self.add_result(ValidationResult(
                "TRADIER_ACCOUNT_ID",
                ValidationLevel.ERROR,
                "Using template value",
                "Replace with actual Tradier account ID"
            ))
        else:
            self.add_result(ValidationResult(
                "TRADIER_ACCOUNT_ID",
                ValidationLevel.INFO,
                f"Set to '{account_id}'",
                None
            ))

    def _validate_risk_config(self):
        """Validate risk management configuration"""
        # Max Position Size
        max_pos = os.environ.get("MAX_POSITION_SIZE", "0.10")
        try:
            max_pos_float = float(max_pos)
            if max_pos_float <= 0 or max_pos_float > 1.0:
                self.add_result(ValidationResult(
                    "MAX_POSITION_SIZE",
                    ValidationLevel.ERROR,
                    f"Invalid value: {max_pos_float}",
                    "Must be between 0 and 1.0 (percentage of account)"
                ))
        except ValueError:
            self.add_result(ValidationResult(
                "MAX_POSITION_SIZE",
                ValidationLevel.ERROR,
                f"Not a valid number: '{max_pos}'",
                "Set to decimal value (e.g., 0.10 for 10%)"
            ))

        # Max Daily Loss
        max_loss = os.environ.get("MAX_DAILY_LOSS", "0.05")
        try:
            max_loss_float = float(max_loss)
            if max_loss_float <= 0 or max_loss_float > 1.0:
                self.add_result(ValidationResult(
                    "MAX_DAILY_LOSS",
                    ValidationLevel.ERROR,
                    f"Invalid value: {max_loss_float}",
                    "Must be between 0 and 1.0 (percentage of account)"
                ))
        except ValueError:
            self.add_result(ValidationResult(
                "MAX_DAILY_LOSS",
                ValidationLevel.ERROR,
                f"Not a valid number: '{max_loss}'",
                "Set to decimal value (e.g., 0.05 for 5%)"
            ))

        # Max Open Positions
        max_positions = os.environ.get("MAX_OPEN_POSITIONS", "5")
        try:
            max_positions_int = int(max_positions)
            if max_positions_int < 1:
                self.add_result(ValidationResult(
                    "MAX_OPEN_POSITIONS",
                    ValidationLevel.ERROR,
                    f"Must be at least 1, got: {max_positions_int}",
                    "Set to positive integer"
                ))
        except ValueError:
            self.add_result(ValidationResult(
                "MAX_OPEN_POSITIONS",
                ValidationLevel.ERROR,
                f"Not a valid integer: '{max_positions}'",
                "Set to integer value (e.g., 5)"
            ))

    def _validate_logging_config(self):
        """Validate logging configuration"""
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        if log_level not in valid_levels:
            self.add_result(ValidationResult(
                "LOG_LEVEL",
                ValidationLevel.WARNING,
                f"Invalid value: '{log_level}'",
                f"Should be one of: {', '.join(valid_levels)}"
            ))

        gui_log_level = os.environ.get("GUI_LOG_LEVEL", "INFO").upper()
        if gui_log_level not in valid_levels:
            self.add_result(ValidationResult(
                "GUI_LOG_LEVEL",
                ValidationLevel.WARNING,
                f"Invalid value: '{gui_log_level}'",
                f"Should be one of: {', '.join(valid_levels)}"
            ))

        # Check log file path
        log_file = os.environ.get("LOG_FILE_PATH", "logs/spyder.log")
        log_dir = Path(log_file).parent

        if not log_dir.exists():
            self.add_result(ValidationResult(
                "LOG_FILE_PATH",
                ValidationLevel.INFO,
                f"Log directory '{log_dir}' will be created",
                None
            ))

    def _validate_security_config(self):
        """Validate security configuration"""
        override_password = os.environ.get("EMERGENCY_OVERRIDE_PASSWORD", "")

        if not override_password:
            self.add_result(ValidationResult(
                "EMERGENCY_OVERRIDE_PASSWORD",
                ValidationLevel.WARNING,
                "Not set - emergency override will not work",
                "Set a strong password for emergency override functionality"
            ))
        elif override_password == "your_secure_password_here":  # noqa: S105
            self.add_result(ValidationResult(
                "EMERGENCY_OVERRIDE_PASSWORD",
                ValidationLevel.WARNING,
                "Using template value - should be changed",
                "Set a strong unique password"
            ))
        elif len(override_password) < 12:
            self.add_result(ValidationResult(
                "EMERGENCY_OVERRIDE_PASSWORD",
                ValidationLevel.WARNING,
                "Password is short, consider using longer password",
                "Use at least 12 characters for security"
            ))

    def _display_results(self):
        """Display validation results"""
        print()

        # Display info messages
        if self.info:
            print("ℹ️  INFORMATION:")
            print("-" * 70)
            for result in self.info:
                print(f"  ✓ {result.key}: {result.message}")
            print()

        # Display warnings
        if self.warnings:
            print("⚠️  WARNINGS:")
            print("-" * 70)
            for result in self.warnings:
                print(f"  ⚠️  {result.key}: {result.message}")
                if result.suggestion:
                    print(f"      → {result.suggestion}")
            print()

        # Display errors
        if self.errors:
            print("❌ ERRORS:")
            print("-" * 70)
            for result in self.errors:
                print(f"  ❌ {result.key}: {result.message}")
                if result.suggestion:
                    print(f"      → {result.suggestion}")
            print()

        # Summary
        print("=" * 70)
        print("SUMMARY:")
        print(f"  ℹ️  Info: {len(self.info)}")
        print(f"  ⚠️  Warnings: {len(self.warnings)}")
        print(f"  ❌ Errors: {len(self.errors)}")
        print("=" * 70)

        if self.errors:
            print()
            print("❌ CONFIGURATION INVALID - System cannot start")
            print("   Fix the errors above and run validation again")
            print()
        else:
            print()
            print("✅ CONFIGURATION VALID - System ready to start")
            if self.warnings:
                print("   Note: Some warnings present - review recommended")
            print()


def main():
    """Main entry point"""
    try:
        # Load .env file if present
        env_file = Path(project_root) / ".env"
        if env_file.exists():
            print(f"Loading configuration from: {env_file}")
            from dotenv import load_dotenv
            load_dotenv(env_file)
        else:
            print("No .env file found - using environment variables only")
            print("Create .env from template: cp .env.template .env")
            print()

        # Run validation
        validator = ConfigurationValidator()
        is_valid = validator.validate_all()

        # Exit with appropriate code
        sys.exit(0 if is_valid else 1)

    except KeyboardInterrupt:
        print("\n\nValidation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
