#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE08_PositionGroupValidator.py
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
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading
from abc import ABC, abstractmethod

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    import logging
    SpyderLogger = type('SpyderLogger', (), {
        'get_logger': lambda name: logging.getLogger(name)
    })()

try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, ErrorCategory, ErrorSeverity  # noqa: E501
except ImportError:
    class ErrorCategory(Enum):
        VALIDATION = "validation"
        CALCULATION = "calculation"
        SYSTEM = "system"

    class ErrorSeverity(Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"

    SpyderErrorHandler = type('SpyderErrorHandler', (), {
        'handle_error': lambda self, e, context: logging.warning("Error in %s: %s", context, e)
    })

try:
    from SpyderU_Utilities.SpyderU14_OptionStrategies import OptionStrategy, StrategyType, OptionRight  # noqa: E501, F401
except ImportError:
    # Define minimal enums if not available
    class StrategyType(Enum):
        IRON_CONDOR = "iron_condor"
        CREDIT_SPREAD = "credit_spread"
        CALENDAR_SPREAD = "calendar_spread"
        STRADDLE = "straddle"
        STRANGLE = "strangle"
        BUTTERFLY = "butterfly"
        RATIO_SPREAD = "ratio_spread"
        DIAGONAL_SPREAD = "diagonal_spread"

    class OptionRight(Enum):
        CALL = "C"
        PUT = "P"

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Validation thresholds
PRICE_TOLERANCE = 0.01          # 1 cent tolerance
STRIKE_SPACING_MIN = 0.50       # Minimum $0.50 between strikes
TIME_SYNC_TOLERANCE = 1         # 1 second sync tolerance
MAX_POSITION_AGE = 3600        # 1 hour max age for validation

# Greeks validation limits
MAX_DELTA_NEUTRAL_DEVIATION = 0.05  # 5% deviation for delta neutral
MAX_GAMMA_EXPOSURE = 100            # Max gamma per position
MAX_VEGA_EXPOSURE = 500             # Max vega per position
MAX_THETA_DECAY = -200              # Max theta decay per day

# Strategy-specific limits
IRON_CONDOR_MAX_WIDTH = 50         # Max width for iron condor
CALENDAR_MIN_TIME_SPREAD = 7       # Minimum days between expirations
RATIO_MAX_RATIO = 3                # Maximum ratio for ratio spreads

# ==============================================================================
# ENUMS
# ==============================================================================
class ValidationResult(Enum):
    """Validation result types."""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    NEEDS_ADJUSTMENT = "needs_adjustment"

class ValidationCategory(Enum):
    """Categories of validation checks."""
    STRUCTURE = "structure"
    PRICING = "pricing"
    GREEKS = "greeks"
    RISK = "risk"
    EXECUTION = "execution"
    COMPLIANCE = "compliance"

class PositionRelationship(Enum):
    """Relationships between positions."""
    LONG_SHORT_PAIR = "long_short_pair"
    STRIKE_SPREAD = "strike_spread"
    TIME_SPREAD = "time_spread"
    RATIO = "ratio"
    HEDGE = "hedge"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PositionLeg:
    """Individual position leg."""
    symbol: str
    quantity: int
    side: str  # 'BUY' or 'SELL'
    option_type: OptionRight
    strike: float
    expiration: datetime
    entry_price: float
    current_price: float
    implied_volatility: float
    # Greeks
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    rho: float = 0.0
    # Metadata
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class PositionGroup:
    """Group of related positions forming a strategy."""
    group_id: str
    strategy_type: StrategyType
    legs: list[PositionLeg]
    underlying_price: float
    created_at: datetime
    last_validated: datetime | None = None
    validation_status: ValidationResult = ValidationResult.VALID
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidationReport:
    """Detailed validation report."""
    group_id: str
    timestamp: datetime
    overall_result: ValidationResult
    checks_performed: dict[ValidationCategory, ValidationResult]
    errors: list[str]
    warnings: list[str]
    recommendations: list[str]
    metrics: dict[str, float]
    adjustments_needed: list[dict[str, Any]]

@dataclass
class GreeksLimits:
    """Greeks exposure limits."""
    max_delta: float = 100
    max_gamma: float = 50
    max_vega: float = 200
    max_theta: float = -100
    max_rho: float = 50
    delta_neutral_tolerance: float = 0.05

@dataclass
class StrategyConstraints:
    """Strategy-specific constraints."""
    strategy_type: StrategyType
    min_strikes: int
    max_strikes: int
    required_relationships: list[PositionRelationship]
    strike_rules: dict[str, Any]
    time_rules: dict[str, Any]
    quantity_rules: dict[str, Any]
    greeks_limits: GreeksLimits

# ==============================================================================
# VALIDATION RULES
# ==============================================================================
class ValidationRule(ABC):
    """Abstract base class for validation rules."""

    @abstractmethod
    def validate(self, position_group: PositionGroup) -> tuple[ValidationResult, list[str]]:
        """Validate position group against rule."""
        pass

    @abstractmethod
    def get_category(self) -> ValidationCategory:
        """Get validation category."""
        pass

class StructureValidationRule(ValidationRule):
    """Validates position structure."""

    def __init__(self, constraints: StrategyConstraints):
        self.constraints = constraints

    def validate(self, position_group: PositionGroup) -> tuple[ValidationResult, list[str]]:
        """Validate structure matches strategy requirements."""
        errors = []

        # Check number of legs
        num_legs = len(position_group.legs)
        if num_legs < self.constraints.min_strikes:
            errors.append(f"Too few legs: {num_legs} < {self.constraints.min_strikes}")
        elif num_legs > self.constraints.max_strikes:
            errors.append(f"Too many legs: {num_legs} > {self.constraints.max_strikes}")

        # Validate based on strategy type
        if position_group.strategy_type == StrategyType.IRON_CONDOR:
            errors.extend(self._validate_iron_condor_structure(position_group))
        elif position_group.strategy_type == StrategyType.CALENDAR_SPREAD:
            errors.extend(self._validate_calendar_structure(position_group))
        elif position_group.strategy_type == StrategyType.CREDIT_SPREAD:
            errors.extend(self._validate_credit_spread_structure(position_group))

        result = ValidationResult.INVALID if errors else ValidationResult.VALID
        return result, errors

    def get_category(self) -> ValidationCategory:
        return ValidationCategory.STRUCTURE

    def _validate_iron_condor_structure(self, group: PositionGroup) -> list[str]:
        """Validate iron condor structure."""
        errors = []

        if len(group.legs) != 4:
            errors.append("Iron condor must have exactly 4 legs")
            return errors

        # Sort legs by strike
        sorted_legs = sorted(group.legs, key=lambda x: x.strike)

        # Check put spread (lower strikes)
        if not (sorted_legs[0].option_type == OptionRight.PUT and
                sorted_legs[1].option_type == OptionRight.PUT):
            errors.append("Lower strikes must be puts")

        # Check call spread (higher strikes)
        if not (sorted_legs[2].option_type == OptionRight.CALL and
                sorted_legs[3].option_type == OptionRight.CALL):
            errors.append("Higher strikes must be calls")

        # Check long/short relationships
        if not (sorted_legs[0].quantity > 0 and sorted_legs[1].quantity < 0):
            errors.append("Put spread must be long lower, short higher")

        if not (sorted_legs[2].quantity < 0 and sorted_legs[3].quantity > 0):
            errors.append("Call spread must be short lower, long higher")

        # Check strike spacing
        put_width = sorted_legs[1].strike - sorted_legs[0].strike
        call_width = sorted_legs[3].strike - sorted_legs[2].strike

        if abs(put_width - call_width) > PRICE_TOLERANCE:
            errors.append(f"Spread widths must match: put={put_width}, call={call_width}")

        return errors

    def _validate_calendar_structure(self, group: PositionGroup) -> list[str]:
        """Validate calendar spread structure."""
        errors = []

        if len(group.legs) != 2:
            errors.append("Calendar spread must have exactly 2 legs")
            return errors

        # Same strike
        if abs(group.legs[0].strike - group.legs[1].strike) > PRICE_TOLERANCE:
            errors.append("Calendar spread legs must have same strike")

        # Different expirations
        time_diff = abs((group.legs[0].expiration - group.legs[1].expiration).days)
        if time_diff < CALENDAR_MIN_TIME_SPREAD:
            errors.append(f"Insufficient time spread: {time_diff} days")

        # Opposite quantities
        if group.legs[0].quantity * group.legs[1].quantity >= 0:
            errors.append("Calendar legs must have opposite signs")

        return errors

    def _validate_credit_spread_structure(self, group: PositionGroup) -> list[str]:
        """Validate credit spread structure."""
        errors = []

        if len(group.legs) != 2:
            errors.append("Credit spread must have exactly 2 legs")
            return errors

        # Same option type
        if group.legs[0].option_type != group.legs[1].option_type:
            errors.append("Credit spread legs must be same option type")

        # Opposite quantities
        if group.legs[0].quantity * group.legs[1].quantity >= 0:
            errors.append("Credit spread must have opposite position signs")

        # Check it's actually a credit spread (short closer to money)
        if group.legs[0].option_type == OptionRight.CALL:
            # Bull call spread - short lower strike
            short_leg = min(group.legs, key=lambda x: x.strike)
            if short_leg.quantity > 0:
                errors.append("Call credit spread must be short lower strike")
        else:
            # Bear put spread - short higher strike
            short_leg = max(group.legs, key=lambda x: x.strike)
            if short_leg.quantity > 0:
                errors.append("Put credit spread must be short higher strike")

        return errors

class GreeksValidationRule(ValidationRule):
    """Validates Greeks exposure."""

    def __init__(self, limits: GreeksLimits):
        self.limits = limits

    def validate(self, position_group: PositionGroup) -> tuple[ValidationResult, list[str]]:
        """Validate Greeks are within limits."""
        errors = []
        warnings = []

        # Calculate aggregate Greeks
        total_delta = sum(leg.delta * leg.quantity for leg in position_group.legs)
        total_gamma = sum(leg.gamma * leg.quantity for leg in position_group.legs)
        total_vega = sum(leg.vega * leg.quantity for leg in position_group.legs)
        total_theta = sum(leg.theta * leg.quantity for leg in position_group.legs)

        # Check limits
        if abs(total_delta) > self.limits.max_delta:
            errors.append(f"Delta exceeds limit: {total_delta:.1f} > {self.limits.max_delta}")

        if abs(total_gamma) > self.limits.max_gamma:
            errors.append(f"Gamma exceeds limit: {total_gamma:.1f} > {self.limits.max_gamma}")

        if abs(total_vega) > self.limits.max_vega:
            errors.append(f"Vega exceeds limit: {total_vega:.1f} > {self.limits.max_vega}")

        if total_theta < -self.limits.max_theta:
            warnings.append(f"High theta decay: {total_theta:.1f}")

        # Check delta neutrality if required
        if position_group.strategy_type in [StrategyType.IRON_CONDOR, StrategyType.BUTTERFLY]:
            delta_ratio = abs(total_delta) / max(sum(abs(leg.delta * leg.quantity)
                                                    for leg in position_group.legs), 1)
            if delta_ratio > self.limits.delta_neutral_tolerance:
                warnings.append(f"Position not delta neutral: {delta_ratio:.2%}")

        if errors:
            return ValidationResult.INVALID, errors + warnings
        elif warnings:
            return ValidationResult.WARNING, warnings
        else:
            return ValidationResult.VALID, []

    def get_category(self) -> ValidationCategory:
        return ValidationCategory.GREEKS

class PricingValidationRule(ValidationRule):
    """Validates pricing relationships."""

    def validate(self, position_group: PositionGroup) -> tuple[ValidationResult, list[str]]:
        """Validate pricing is consistent."""
        errors = []
        warnings = []

        # Check bid-ask spreads
        for leg in position_group.legs:
            # Simplified check - would use actual bid/ask in production
            if leg.current_price <= 0:
                errors.append(f"Invalid price for {leg.symbol}: {leg.current_price}")

        # Validate option pricing relationships
        if position_group.strategy_type == StrategyType.CREDIT_SPREAD:
            errors.extend(self._validate_spread_pricing(position_group))

        # Check for pricing anomalies
        for leg in position_group.legs:
            intrinsic = self._calculate_intrinsic_value(
                leg, position_group.underlying_price
            )
            if leg.current_price < intrinsic - PRICE_TOLERANCE:
                warnings.append(
                    f"Option trading below intrinsic: {leg.symbol} "
                    f"(price={leg.current_price:.2f}, intrinsic={intrinsic:.2f})"
                )

        if errors:
            return ValidationResult.INVALID, errors + warnings
        elif warnings:
            return ValidationResult.WARNING, warnings
        else:
            return ValidationResult.VALID, []

    def get_category(self) -> ValidationCategory:
        return ValidationCategory.PRICING

    def _validate_spread_pricing(self, group: PositionGroup) -> list[str]:
        """Validate spread pricing relationships."""
        errors = []

        if len(group.legs) < 2:
            return errors

        # For vertical spreads, check price relationships
        if group.legs[0].expiration == group.legs[1].expiration:
            if group.legs[0].option_type == OptionRight.CALL:
                # Calls: lower strike should be more expensive
                lower_strike_leg = min(group.legs, key=lambda x: x.strike)
                higher_strike_leg = max(group.legs, key=lambda x: x.strike)

                if lower_strike_leg.current_price < higher_strike_leg.current_price:
                    errors.append("Call pricing violation: lower strike cheaper")
            else:
                # Puts: higher strike should be more expensive
                lower_strike_leg = min(group.legs, key=lambda x: x.strike)
                higher_strike_leg = max(group.legs, key=lambda x: x.strike)

                if higher_strike_leg.current_price < lower_strike_leg.current_price:
                    errors.append("Put pricing violation: higher strike cheaper")

        return errors

    def _calculate_intrinsic_value(self, leg: PositionLeg, underlying: float) -> float:
        """Calculate intrinsic value of option."""
        if leg.option_type == OptionRight.CALL:
            return max(0, underlying - leg.strike)
        else:
            return max(0, leg.strike - underlying)

# ==============================================================================
# POSITION GROUP VALIDATOR CLASS
# ==============================================================================
class PositionGroupValidator:
    """
    Universal position group validator.

    Implements comprehensive validation for all option strategy types using
    LEAN-inspired patterns. Ensures position integrity, risk limits, and
    proper strategy construction.

    Attributes:
        logger: Module logger
        strategy_constraints: Constraints by strategy type
        validation_rules: Active validation rules

    Example:
        >>> validator = PositionGroupValidator()
        >>> group = PositionGroup(...)
        >>> report = validator.validate_position_group(group)
        >>> if report.overall_result == ValidationResult.VALID:
        ...     # Proceed with position
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize position group validator.

        Args:
            config: Optional configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}

        # Thread safety
        self._lock = threading.RLock()

        # Initialize strategy constraints
        self.strategy_constraints = self._initialize_constraints()

        # Validation rules
        self.validation_rules: dict[ValidationCategory, list[ValidationRule]] = {
            ValidationCategory.STRUCTURE: [],
            ValidationCategory.PRICING: [],
            ValidationCategory.GREEKS: [],
            ValidationCategory.RISK: [],
            ValidationCategory.EXECUTION: [],
            ValidationCategory.COMPLIANCE: []
        }

        # Initialize default rules
        self._initialize_default_rules()

        # Validation history
        self.validation_history: list[ValidationReport] = []

        # Statistics
        self.validation_stats = defaultdict(lambda: {'total': 0, 'valid': 0, 'invalid': 0})

        self.logger.info("PositionGroupValidator initialized")

    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================
    def _initialize_constraints(self) -> dict[StrategyType, StrategyConstraints]:
        """Initialize strategy constraints."""
        constraints = {}

        # Iron Condor constraints
        constraints[StrategyType.IRON_CONDOR] = StrategyConstraints(
            strategy_type=StrategyType.IRON_CONDOR,
            min_strikes=4,
            max_strikes=4,
            required_relationships=[
                PositionRelationship.STRIKE_SPREAD,
                PositionRelationship.LONG_SHORT_PAIR
            ],
            strike_rules={
                'min_width': 2.5,
                'max_width': IRON_CONDOR_MAX_WIDTH,
                'put_call_separation': 5.0
            },
            time_rules={'same_expiration': True},
            quantity_rules={'equal_quantities': True},
            greeks_limits=GreeksLimits(
                max_delta=20,
                max_gamma=10,
                max_vega=100,
                delta_neutral_tolerance=0.1
            )
        )

        # Credit Spread constraints
        constraints[StrategyType.CREDIT_SPREAD] = StrategyConstraints(
            strategy_type=StrategyType.CREDIT_SPREAD,
            min_strikes=2,
            max_strikes=2,
            required_relationships=[PositionRelationship.STRIKE_SPREAD],
            strike_rules={
                'min_width': 1.0,
                'max_width': 10.0
            },
            time_rules={'same_expiration': True},
            quantity_rules={'opposite_signs': True, 'equal_magnitudes': True},
            greeks_limits=GreeksLimits(max_delta=50, max_gamma=25)
        )

        # Calendar Spread constraints
        constraints[StrategyType.CALENDAR_SPREAD] = StrategyConstraints(
            strategy_type=StrategyType.CALENDAR_SPREAD,
            min_strikes=2,
            max_strikes=2,
            required_relationships=[PositionRelationship.TIME_SPREAD],
            strike_rules={'same_strike': True},
            time_rules={
                'different_expirations': True,
                'min_time_spread': CALENDAR_MIN_TIME_SPREAD
            },
            quantity_rules={'opposite_signs': True},
            greeks_limits=GreeksLimits(max_vega=150, max_theta=-50)
        )

        # Add more strategies as needed...

        return constraints

    def _initialize_default_rules(self) -> None:
        """Initialize default validation rules."""
        # Add structure rules for each strategy
        for _strategy_type, constraints in self.strategy_constraints.items():
            self.validation_rules[ValidationCategory.STRUCTURE].append(
                StructureValidationRule(constraints)
            )

        # Add universal rules
        self.validation_rules[ValidationCategory.PRICING].append(
            PricingValidationRule()
        )

        # Add Greeks rules with default limits
        default_greeks_limits = GreeksLimits()
        self.validation_rules[ValidationCategory.GREEKS].append(
            GreeksValidationRule(default_greeks_limits)
        )

    # ==========================================================================
    # PUBLIC METHODS - VALIDATION
    # ==========================================================================
    def validate_position_group(self, position_group: PositionGroup) -> ValidationReport:
        """
        Validate a position group.

        Args:
            position_group: Position group to validate

        Returns:
            Comprehensive validation report
        """
        with self._lock:
            # Create report
            report = ValidationReport(
                group_id=position_group.group_id,
                timestamp=datetime.now(timezone.utc),
                overall_result=ValidationResult.VALID,
                checks_performed={},
                errors=[],
                warnings=[],
                recommendations=[],
                metrics={},
                adjustments_needed=[]
            )

            try:
                # Update last validated time
                position_group.last_validated = datetime.now(timezone.utc)

                # Run all validation rules
                for category, rules in self.validation_rules.items():
                    category_result = ValidationResult.VALID
                    category_messages = []

                    for rule in rules:
                        if rule.get_category() == category:
                            result, messages = rule.validate(position_group)

                            # Update category result (worst case)
                            if result == ValidationResult.INVALID:
                                category_result = ValidationResult.INVALID
                                report.errors.extend(messages)
                            elif result == ValidationResult.WARNING and category_result != ValidationResult.INVALID:  # noqa: E501
                                category_result = ValidationResult.WARNING
                                report.warnings.extend(messages)

                            category_messages.extend(messages)

                    report.checks_performed[category] = category_result

                # Calculate metrics
                report.metrics = self._calculate_validation_metrics(position_group)

                # Determine overall result
                if any(r == ValidationResult.INVALID for r in report.checks_performed.values()):
                    report.overall_result = ValidationResult.INVALID
                elif any(r == ValidationResult.WARNING for r in report.checks_performed.values()):
                    report.overall_result = ValidationResult.WARNING

                # Generate recommendations
                report.recommendations = self._generate_recommendations(position_group, report)

                # Check if adjustments needed
                if report.overall_result in [ValidationResult.WARNING, ValidationResult.NEEDS_ADJUSTMENT]:  # noqa: E501
                    report.adjustments_needed = self._calculate_adjustments(position_group, report)

                # Update statistics
                self._update_statistics(position_group.strategy_type, report.overall_result)

                # Store in history
                self.validation_history.append(report)

                # Log result
                self.logger.info(
                    f"Validated {position_group.strategy_type.value} group {position_group.group_id}: "  # noqa: E501
                    f"{report.overall_result.value}"
                )

                return report

            except Exception as e:
                self.logger.error("Validation error: %s", e)
                self.error_handler.handle_error(e, {"method": "validate_position_group"})

                report.overall_result = ValidationResult.INVALID
                report.errors.append(f"Validation error: {str(e)}")
                return report

    def validate_proposed_adjustment(self,
                                   current_group: PositionGroup,
                                   proposed_changes: list[dict[str, Any]]) -> ValidationReport:
        """
        Validate proposed adjustments to a position group.

        Args:
            current_group: Current position group
            proposed_changes: List of proposed changes

        Returns:
            Validation report for proposed state
        """
        # Create copy of current group
        adjusted_group = self._apply_proposed_changes(current_group, proposed_changes)

        # Validate the adjusted group
        report = self.validate_position_group(adjusted_group)

        # Add adjustment context
        report.metadata['is_adjustment'] = True
        report.metadata['original_group_id'] = current_group.group_id
        report.metadata['proposed_changes'] = proposed_changes

        return report

    def assert_strategy_position_group(self, position_group: PositionGroup) -> None:
        """
        LEAN-style assertion for position group validity.

        Raises exception if position group is invalid.

        Args:
            position_group: Position group to assert

        Raises:
            AssertionError: If position group is invalid
        """
        report = self.validate_position_group(position_group)

        if report.overall_result == ValidationResult.INVALID:
            error_msg = f"Position group {position_group.group_id} validation failed:\n"
            error_msg += "\n".join(f"  - {error}" for error in report.errors)

            self.logger.error(error_msg)
            raise AssertionError(error_msg)

        if report.warnings:
            warning_msg = f"Position group {position_group.group_id} has warnings:\n"
            warning_msg += "\n".join(f"  - {warning}" for warning in report.warnings)
            self.logger.warning(warning_msg)

    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    def _calculate_validation_metrics(self, position_group: PositionGroup) -> dict[str, float]:
        """Calculate validation metrics."""
        metrics = {}

        # Position metrics
        metrics['num_legs'] = len(position_group.legs)
        metrics['total_quantity'] = sum(abs(leg.quantity) for leg in position_group.legs)

        # Greeks metrics
        metrics['total_delta'] = sum(leg.delta * leg.quantity for leg in position_group.legs)
        metrics['total_gamma'] = sum(leg.gamma * leg.quantity for leg in position_group.legs)
        metrics['total_vega'] = sum(leg.vega * leg.quantity for leg in position_group.legs)
        metrics['total_theta'] = sum(leg.theta * leg.quantity for leg in position_group.legs)

        # Risk metrics
        metrics['max_loss'] = self._calculate_max_loss(position_group)
        metrics['max_profit'] = self._calculate_max_profit(position_group)
        metrics['breakeven_points'] = len(self._calculate_breakevens(position_group))

        # Time metrics
        min_dte = min((leg.expiration - datetime.now(timezone.utc)).days for leg in position_group.legs)
        metrics['min_days_to_expiry'] = max(0, min_dte)

        return metrics

    def _calculate_max_loss(self, position_group: PositionGroup) -> float:
        """Calculate maximum loss for position group."""
        if position_group.strategy_type == StrategyType.IRON_CONDOR:
            # Max loss is spread width minus credit received
            sorted_legs = sorted(position_group.legs, key=lambda x: x.strike)
            put_width = sorted_legs[1].strike - sorted_legs[0].strike

            # Calculate net credit
            net_credit = sum(leg.entry_price * leg.quantity * 100 for leg in position_group.legs)

            return (put_width * 100) - net_credit

        elif position_group.strategy_type == StrategyType.CREDIT_SPREAD:
            # Max loss is spread width minus credit
            strikes = [leg.strike for leg in position_group.legs]
            spread_width = abs(max(strikes) - min(strikes))
            net_credit = sum(leg.entry_price * leg.quantity * 100 for leg in position_group.legs)

            return (spread_width * 100) - net_credit

        # Default calculation
        return sum(abs(leg.entry_price * leg.quantity * 100) for leg in position_group.legs)

    def _calculate_max_profit(self, position_group: PositionGroup) -> float:
        """Calculate maximum profit for position group."""
        if position_group.strategy_type in [StrategyType.IRON_CONDOR, StrategyType.CREDIT_SPREAD]:
            # Max profit is net credit received
            return sum(leg.entry_price * leg.quantity * 100 for leg in position_group.legs)

        # Default calculation
        return 0.0

    def _calculate_breakevens(self, position_group: PositionGroup) -> list[float]:
        """Calculate breakeven points."""
        breakevens = []

        if position_group.strategy_type == StrategyType.CREDIT_SPREAD:
            # Single breakeven point
            if position_group.legs[0].option_type == OptionRight.CALL:
                # Bull call spread
                short_strike = min(leg.strike for leg in position_group.legs if leg.quantity < 0)
                net_credit = sum(leg.entry_price for leg in position_group.legs)
                breakevens.append(short_strike + net_credit)
            else:
                # Bear put spread
                short_strike = max(leg.strike for leg in position_group.legs if leg.quantity < 0)
                net_credit = sum(leg.entry_price for leg in position_group.legs)
                breakevens.append(short_strike - net_credit)

        elif position_group.strategy_type == StrategyType.IRON_CONDOR:
            # Two breakeven points
            sorted_legs = sorted(position_group.legs, key=lambda x: x.strike)
            net_credit = sum(leg.entry_price for leg in position_group.legs)

            # Lower breakeven (put side)
            breakevens.append(sorted_legs[1].strike - net_credit)

            # Upper breakeven (call side)
            breakevens.append(sorted_legs[2].strike + net_credit)

        return breakevens

    def _generate_recommendations(self, position_group: PositionGroup,
                                report: ValidationReport) -> list[str]:
        """Generate recommendations based on validation."""
        recommendations = []

        # Greeks recommendations
        metrics = report.metrics

        if abs(metrics.get('total_delta', 0)) > 50:
            recommendations.append(
                f"Consider delta hedging - current delta: {metrics['total_delta']:.1f}"
            )

        if metrics.get('total_theta', 0) < -100:
            recommendations.append(
                f"High theta decay: ${metrics['total_theta']:.0f}/day"
            )

        if metrics.get('min_days_to_expiry', 0) < 5:
            recommendations.append(
                "Position approaching expiration - consider rolling or closing"
            )

        # Strategy-specific recommendations
        if position_group.strategy_type == StrategyType.IRON_CONDOR:
            if abs(metrics.get('total_delta', 0)) > 10:
                recommendations.append(
                    "Iron condor delta imbalanced - consider adjustment"
                )

        return recommendations

    def _calculate_adjustments(self, position_group: PositionGroup,
                             report: ValidationReport) -> list[dict[str, Any]]:
        """Calculate needed adjustments."""
        adjustments = []

        # Delta adjustment
        if abs(report.metrics.get('total_delta', 0)) > 20:
            delta_adjustment = {
                'type': 'delta_hedge',
                'current_delta': report.metrics['total_delta'],
                'target_delta': 0,
                'shares_needed': -int(report.metrics['total_delta'] * 100)
            }
            adjustments.append(delta_adjustment)

        # Time adjustment
        if report.metrics.get('min_days_to_expiry', 0) < 5:
            time_adjustment = {
                'type': 'roll_position',
                'reason': 'approaching_expiration',
                'days_remaining': report.metrics['min_days_to_expiry']
            }
            adjustments.append(time_adjustment)

        return adjustments

    def _apply_proposed_changes(self, current_group: PositionGroup,
                               changes: list[dict[str, Any]]) -> PositionGroup:
        """Apply proposed changes to create new position group."""
        # Deep copy current group
        import copy
        adjusted_group = copy.deepcopy(current_group)

        for change in changes:
            change_type = change.get('type')

            if change_type == 'add_leg':
                new_leg = PositionLeg(**change['leg_data'])
                adjusted_group.legs.append(new_leg)

            elif change_type == 'remove_leg':
                leg_id = change.get('leg_id')
                adjusted_group.legs = [
                    leg for leg in adjusted_group.legs
                    if leg.position_id != leg_id
                ]

            elif change_type == 'modify_leg':
                leg_id = change.get('leg_id')
                for leg in adjusted_group.legs:
                    if leg.position_id == leg_id:
                        for key, value in change.get('modifications', {}).items():
                            setattr(leg, key, value)

        return adjusted_group

    def _update_statistics(self, strategy_type: StrategyType, result: ValidationResult) -> None:
        """Update validation statistics."""
        stats = self.validation_stats[strategy_type.value]
        stats['total'] += 1

        if result == ValidationResult.VALID:
            stats['valid'] += 1
        elif result == ValidationResult.INVALID:
            stats['invalid'] += 1

    # ==========================================================================
    # PUBLIC METHODS - CONFIGURATION
    # ==========================================================================
    def add_validation_rule(self, category: ValidationCategory, rule: ValidationRule) -> None:
        """Add custom validation rule."""
        with self._lock:
            self.validation_rules[category].append(rule)
            self.logger.info("Added validation rule for %s", category.value)

    def update_constraints(self, strategy_type: StrategyType,
                         constraints: StrategyConstraints) -> None:
        """Update strategy constraints."""
        with self._lock:
            self.strategy_constraints[strategy_type] = constraints
            self.logger.info("Updated constraints for %s", strategy_type.value)

    def get_validation_statistics(self) -> dict[str, dict[str, Any]]:
        """Get validation statistics."""
        with self._lock:
            return dict(self.validation_stats)

    def get_recent_reports(self, hours: int = 24) -> list[ValidationReport]:
        """Get recent validation reports."""
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            return [
                report for report in self.validation_history
                if report.timestamp >= cutoff
            ]

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_position_group_validator(config: dict[str, Any] | None = None) -> PositionGroupValidator:
    """
    Create position group validator instance.

    Args:
        config: Optional configuration

    Returns:
        PositionGroupValidator instance
    """
    return PositionGroupValidator(config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    # Create validator
    validator = create_position_group_validator()

    # Test Iron Condor validation

    # Create iron condor position group
    iron_condor_legs = [
        # Put spread
        PositionLeg(
            symbol="SPY_250117P380",
            quantity=1,
            side="BUY",
            option_type=OptionRight.PUT,
            strike=380,
            expiration=datetime.now(timezone.utc) + timedelta(days=45),
            entry_price=0.50,
            current_price=0.45,
            implied_volatility=0.18,
            delta=-0.05,
            gamma=0.001,
            vega=0.5,
            theta=-0.5
        ),
        PositionLeg(
            symbol="SPY_250117P390",
            quantity=-1,
            side="SELL",
            option_type=OptionRight.PUT,
            strike=390,
            expiration=datetime.now(timezone.utc) + timedelta(days=45),
            entry_price=1.00,
            current_price=0.95,
            implied_volatility=0.17,
            delta=-0.10,
            gamma=0.002,
            vega=1.0,
            theta=-1.0
        ),
        # Call spread
        PositionLeg(
            symbol="SPY_250117C410",
            quantity=-1,
            side="SELL",
            option_type=OptionRight.CALL,
            strike=410,
            expiration=datetime.now(timezone.utc) + timedelta(days=45),
            entry_price=1.00,
            current_price=0.95,
            implied_volatility=0.17,
            delta=0.10,
            gamma=0.002,
            vega=1.0,
            theta=-1.0
        ),
        PositionLeg(
            symbol="SPY_250117C420",
            quantity=1,
            side="BUY",
            option_type=OptionRight.CALL,
            strike=420,
            expiration=datetime.now(timezone.utc) + timedelta(days=45),
            entry_price=0.50,
            current_price=0.45,
            implied_volatility=0.18,
            delta=0.05,
            gamma=0.001,
            vega=0.5,
            theta=-0.5
        )
    ]

    iron_condor_group = PositionGroup(
        group_id="IC_001",
        strategy_type=StrategyType.IRON_CONDOR,
        legs=iron_condor_legs,
        underlying_price=400,
        created_at=datetime.now(timezone.utc)
    )

    # Validate iron condor
    ic_report = validator.validate_position_group(iron_condor_group)

    for _category, _result in ic_report.checks_performed.items():
        pass

    if ic_report.errors:
        for _error in ic_report.errors:
            pass

    if ic_report.warnings:
        for _warning in ic_report.warnings:
            pass

    for _metric, _value in ic_report.metrics.items():
        pass

    if ic_report.recommendations:
        for _rec in ic_report.recommendations:
            pass

    # Test Credit Spread validation

    credit_spread_legs = [
        PositionLeg(
            symbol="SPY_250117P395",
            quantity=-1,
            side="SELL",
            option_type=OptionRight.PUT,
            strike=395,
            expiration=datetime.now(timezone.utc) + timedelta(days=30),
            entry_price=2.00,
            current_price=1.95,
            implied_volatility=0.16,
            delta=-0.20,
            gamma=0.003,
            vega=2.0,
            theta=-2.0
        ),
        PositionLeg(
            symbol="SPY_250117P390",
            quantity=1,
            side="BUY",
            option_type=OptionRight.PUT,
            strike=390,
            expiration=datetime.now(timezone.utc) + timedelta(days=30),
            entry_price=1.00,
            current_price=0.95,
            implied_volatility=0.17,
            delta=-0.15,
            gamma=0.002,
            vega=1.5,
            theta=-1.5
        )
    ]

    credit_spread_group = PositionGroup(
        group_id="CS_001",
        strategy_type=StrategyType.CREDIT_SPREAD,
        legs=credit_spread_legs,
        underlying_price=400,
        created_at=datetime.now(timezone.utc)
    )

    # Validate credit spread
    cs_report = validator.validate_position_group(credit_spread_group)


    # Test LEAN-style assertion

    try:
        validator.assert_strategy_position_group(credit_spread_group)
    except AssertionError:
        pass

    # Show statistics

    stats = validator.get_validation_statistics()
    for _strategy, counts in stats.items():
        if counts['total'] > 0:
            pass

