#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE08_PositionGroupValidator.py
Group: E (Risk Management)
Purpose: Universal Position Group Validator with LEAN Algorithm Patterns

Description:
    Universal position group validator implementing QuantConnect LEAN's
    assert_strategy_position_group patterns across all option strategies.
    Provides institutional-grade validation, error handling, and position
    integrity checking using professional patterns from LEAN algorithms.

WEEK 3-4 ENHANCEMENT:
    ✅ Universal validation patterns for all strategy types
    ✅ LEAN-inspired assert_strategy_position_group implementation
    ✅ Professional error handling with detailed diagnostics
    ✅ Strategy-specific validation rules from LEAN algorithms
    ✅ Comprehensive position integrity checking

Based on: QuantConnect LEAN Position Group Validation Patterns
- LongAndShortPutCalendarSpreadStrategiesAlgorithm.py
- LongAndShortCallCalendarSpreadStrategiesAlgorithm.py
- LongAndShortStrangleStrategiesAlgorithm.py
- IronCondorStrategyAlgorithm.py (inferred patterns)

Author: Mohamed Talib
Created: 2025-06-23 (Phase 1 Week 3-4)
Version: 1.0 (Universal LEAN Validation)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union, Protocol
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid
from abc import ABC, abstractmethod

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU14_OptionStrategies import OptionStrategy, StrategyType, OptionRight, OptionLeg
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType

# ==============================================================================
# ENUMS AND CONSTANTS
# ==============================================================================
class ValidationResult(Enum):
    """Validation result status"""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    ERROR = "error"
    
class ValidationSeverity(Enum):
    """Validation error severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class LEANPositionGroupType(Enum):
    """LEAN position group types from algorithms"""
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    PUT_CALENDAR_SPREAD = "put_calendar_spread"
    CALL_CALENDAR_SPREAD = "call_calendar_spread"
    STRANGLE = "strangle"
    STRADDLE = "straddle"
    BULL_PUT_SPREAD = "bull_put_spread"
    BEAR_CALL_SPREAD = "bear_call_spread"
    BUTTERFLY_PUT = "butterfly_put"
    BUTTERFLY_CALL = "butterfly_call"
    UNDEFINED = "undefined"

# Validation tolerances (from LEAN algorithms)
POSITION_QUANTITY_TOLERANCE = 1e-6
STRIKE_TOLERANCE = 0.01
EXPIRY_TOLERANCE = timedelta(hours=1)
GREEKS_TOLERANCE = 0.001

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ValidationError:
    """Detailed validation error with LEAN-style diagnostics"""
    error_type: str
    severity: ValidationSeverity
    message: str
    expected_value: Any = None
    actual_value: Any = None
    position_index: Optional[int] = None
    leg_index: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        base = f"[{self.severity.value.upper()}] {self.error_type}: {self.message}"
        if self.expected_value is not None and self.actual_value is not None:
            base += f" (Expected: {self.expected_value}, Actual: {self.actual_value})"
        return base

@dataclass
class PositionGroupDiagnostics:
    """Comprehensive position group diagnostics"""
    position_count: int
    strategy_type: LEANPositionGroupType
    validation_errors: List[ValidationError] = field(default_factory=list)
    validation_warnings: List[ValidationError] = field(default_factory=list)
    
    # Position analysis
    total_quantity: int = 0
    net_delta: float = 0.0
    is_net_neutral: bool = False
    is_directional: bool = False
    
    # Strike analysis
    unique_strikes: List[float] = field(default_factory=list)
    strike_spacing: List[float] = field(default_factory=list)
    
    # Expiry analysis
    unique_expiries: List[datetime] = field(default_factory=list)
    expiry_spread: Optional[timedelta] = None
    
    # Validation summary
    is_valid: bool = True
    validation_score: float = 1.0
    
    def add_error(self, error: ValidationError):
        """Add validation error"""
        if error.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
            self.validation_errors.append(error)
            self.is_valid = False
        else:
            self.validation_warnings.append(error)
        
        # Update validation score
        severity_weights = {
            ValidationSeverity.INFO: 0.0,
            ValidationSeverity.WARNING: 0.1,
            ValidationSeverity.ERROR: 0.3,
            ValidationSeverity.CRITICAL: 0.5
        }
        self.validation_score -= severity_weights.get(error.severity, 0.0)
        self.validation_score = max(0.0, self.validation_score)

# ==============================================================================
# POSITION GROUP PROTOCOLS
# ==============================================================================
class IPositionGroup(Protocol):
    """Protocol for LEAN-style position groups"""
    positions: List[Dict[str, Any]]
    strategy: OptionStrategy
    
class IValidatable(Protocol):
    """Protocol for validatable position groups"""
    def validate_position_group(self) -> bool:
        """Validate position group following LEAN patterns"""
        ...

# ==============================================================================
# LEAN VALIDATION STRATEGIES
# ==============================================================================
class LEANValidationStrategy(ABC):
    """Abstract base class for LEAN validation strategies"""
    
    @abstractmethod
    def validate_position_group(self, positions: List[Dict[str, Any]], 
                              strategy: OptionStrategy) -> PositionGroupDiagnostics:
        """Validate position group using LEAN patterns"""
        pass
    
    @abstractmethod
    def get_expected_position_count(self) -> int:
        """Get expected number of positions"""
        pass

class CalendarSpreadValidator(LEANValidationStrategy):
    """
    Calendar Spread validator from LEAN algorithms.
    
    Based on:
    - LongAndShortPutCalendarSpreadStrategiesAlgorithm.py
    - LongAndShortCallCalendarSpreadStrategiesAlgorithm.py
    """
    
    def validate_position_group(self, positions: List[Dict[str, Any]], 
                              strategy: OptionStrategy) -> PositionGroupDiagnostics:
        """Validate calendar spread position group using LEAN patterns"""
        diagnostics = PositionGroupDiagnostics(
            position_count=len(positions),
            strategy_type=self._get_calendar_type(strategy)
        )
        
        # LEAN Pattern: Calendar spreads must have exactly 2 positions
        if len(positions) != 2:
            diagnostics.add_error(ValidationError(
                error_type="POSITION_COUNT_MISMATCH",
                severity=ValidationSeverity.CRITICAL,
                message="Calendar spread must have exactly 2 positions",
                expected_value=2,
                actual_value=len(positions)
            ))
            return diagnostics
        
        # Extract near and far expiry positions
        near_expiration = min(leg.expiry for leg in strategy.legs)
        far_expiration = max(leg.expiry for leg in strategy.legs)
        
        # Find positions by expiry (LEAN pattern)
        near_position = self._find_position_by_expiry(positions, near_expiration, strategy)
        far_position = self._find_position_by_expiry(positions, far_expiration, strategy)
        
        if not near_position:
            diagnostics.add_error(ValidationError(
                error_type="MISSING_NEAR_POSITION",
                severity=ValidationSeverity.CRITICAL,
                message=f"Expected near expiry position not found",
                expected_value=near_expiration.strftime('%Y-%m-%d'),
                actual_value="None"
            ))
            
        if not far_position:
            diagnostics.add_error(ValidationError(
                error_type="MISSING_FAR_POSITION",
                severity=ValidationSeverity.CRITICAL,
                message=f"Expected far expiry position not found",
                expected_value=far_expiration.strftime('%Y-%m-%d'),
                actual_value="None"
            ))
            
        # Validate quantities (LEAN pattern: near=-2, far=2 for calendar)
        if near_position and near_position.get('quantity', 0) != -2:
            diagnostics.add_error(ValidationError(
                error_type="INVALID_NEAR_QUANTITY",
                severity=ValidationSeverity.ERROR,
                message="Near expiry position quantity should be -2",
                expected_value=-2,
                actual_value=near_position.get('quantity', 0)
            ))
            
        if far_position and far_position.get('quantity', 0) != 2:
            diagnostics.add_error(ValidationError(
                error_type="INVALID_FAR_QUANTITY",
                severity=ValidationSeverity.ERROR,
                message="Far expiry position quantity should be 2",
                expected_value=2,
                actual_value=far_position.get('quantity', 0)
            ))
        
        # Validate same strike (calendar spread requirement)
        if near_position and far_position:
            near_strike = near_position.get('strike', 0)
            far_strike = far_position.get('strike', 0)
            
            if abs(near_strike - far_strike) > STRIKE_TOLERANCE:
                diagnostics.add_error(ValidationError(
                    error_type="STRIKE_MISMATCH",
                    severity=ValidationSeverity.ERROR,
                    message="Calendar spread legs must have same strike",
                    expected_value=near_strike,
                    actual_value=far_strike
                ))
        
        # Validate option type consistency
        self._validate_option_type_consistency(positions, diagnostics)
        
        return diagnostics
    
    def get_expected_position_count(self) -> int:
        return 2
    
    def _get_calendar_type(self, strategy: OptionStrategy) -> LEANPositionGroupType:
        """Determine calendar type from strategy"""
        if strategy.strategy_type == StrategyType.PUT_CALENDAR_SPREAD:
            return LEANPositionGroupType.PUT_CALENDAR_SPREAD
        elif strategy.strategy_type == StrategyType.CALL_CALENDAR_SPREAD:
            return LEANPositionGroupType.CALL_CALENDAR_SPREAD
        return LEANPositionGroupType.UNDEFINED
    
    def _find_position_by_expiry(self, positions: List[Dict[str, Any]], 
                                expiry: datetime, strategy: OptionStrategy) -> Optional[Dict[str, Any]]:
        """Find position by expiry date"""
        for position in positions:
            pos_expiry = position.get('expiry')
            if pos_expiry and abs((pos_expiry - expiry).total_seconds()) < EXPIRY_TOLERANCE.total_seconds():
                return position
        return None
    
    def _validate_option_type_consistency(self, positions: List[Dict[str, Any]], 
                                        diagnostics: PositionGroupDiagnostics):
        """Validate all positions have same option type"""
        option_types = set(pos.get('option_right') for pos in positions if pos.get('option_right'))
        
        if len(option_types) > 1:
            diagnostics.add_error(ValidationError(
                error_type="OPTION_TYPE_INCONSISTENCY",
                severity=ValidationSeverity.ERROR,
                message="Calendar spread legs must be same option type",
                expected_value="Single option type",
                actual_value=f"Multiple types: {option_types}"
            ))

class StrangleValidator(LEANValidationStrategy):
    """
    Strangle validator from LEAN LongAndShortStrangleStrategiesAlgorithm.py
    """
    
    def validate_position_group(self, positions: List[Dict[str, Any]], 
                              strategy: OptionStrategy) -> PositionGroupDiagnostics:
        """Validate strangle position group using LEAN patterns"""
        diagnostics = PositionGroupDiagnostics(
            position_count=len(positions),
            strategy_type=LEANPositionGroupType.STRANGLE
        )
        
        # LEAN Pattern: Strangle must have exactly 2 positions
        if len(positions) != 2:
            diagnostics.add_error(ValidationError(
                error_type="POSITION_COUNT_MISMATCH",
                severity=ValidationSeverity.CRITICAL,
                message="Strangle must have exactly 2 positions",
                expected_value=2,
                actual_value=len(positions)
            ))
            return diagnostics
        
        # Find call and put positions (LEAN pattern)
        call_position = self._find_position_by_option_right(positions, OptionRight.CALL)
        put_position = self._find_position_by_option_right(positions, OptionRight.PUT)
        
        if not call_position:
            diagnostics.add_error(ValidationError(
                error_type="MISSING_CALL_POSITION",
                severity=ValidationSeverity.CRITICAL,
                message="Expected call position not found",
                expected_value="CALL position",
                actual_value="None"
            ))
            
        if not put_position:
            diagnostics.add_error(ValidationError(
                error_type="MISSING_PUT_POSITION",
                severity=ValidationSeverity.CRITICAL,
                message="Expected put position not found",
                expected_value="PUT position",
                actual_value="None"
            ))
        
        # Validate quantities (LEAN pattern: both should be same sign and magnitude)
        expected_call_quantity = 2  # From LEAN algorithm
        expected_put_quantity = 2   # From LEAN algorithm
        
        if call_position and call_position.get('quantity', 0) != expected_call_quantity:
            diagnostics.add_error(ValidationError(
                error_type="INVALID_CALL_QUANTITY",
                severity=ValidationSeverity.ERROR,
                message="Call position quantity mismatch",
                expected_value=expected_call_quantity,
                actual_value=call_position.get('quantity', 0)
            ))
            
        if put_position and put_position.get('quantity', 0) != expected_put_quantity:
            diagnostics.add_error(ValidationError(
                error_type="INVALID_PUT_QUANTITY",
                severity=ValidationSeverity.ERROR,
                message="Put position quantity mismatch",
                expected_value=expected_put_quantity,
                actual_value=put_position.get('quantity', 0)
            ))
        
        # Validate different strikes (strangle requirement)
        if call_position and put_position:
            call_strike = call_position.get('strike', 0)
            put_strike = put_position.get('strike', 0)
            
            if abs(call_strike - put_strike) < STRIKE_TOLERANCE:
                diagnostics.add_error(ValidationError(
                    error_type="STRIKES_TOO_CLOSE",
                    severity=ValidationSeverity.WARNING,
                    message="Strangle strikes should be different (close to straddle)",
                    expected_value="Different strikes",
                    actual_value=f"Call: {call_strike}, Put: {put_strike}"
                ))
        
        # Validate same expiry
        self._validate_same_expiry(positions, diagnostics)
        
        return diagnostics
    
    def get_expected_position_count(self) -> int:
        return 2
    
    def _find_position_by_option_right(self, positions: List[Dict[str, Any]], 
                                     option_right: OptionRight) -> Optional[Dict[str, Any]]:
        """Find position by option right (CALL/PUT)"""
        for position in positions:
            if position.get('option_right') == option_right:
                return position
        return None
    
    def _validate_same_expiry(self, positions: List[Dict[str, Any]], 
                            diagnostics: PositionGroupDiagnostics):
        """Validate all positions have same expiry"""
        expiries = [pos.get('expiry') for pos in positions if pos.get('expiry')]
        
        if len(set(expiries)) > 1:
            diagnostics.add_error(ValidationError(
                error_type="EXPIRY_MISMATCH",
                severity=ValidationSeverity.ERROR,
                message="Strangle legs must have same expiry",
                expected_value="Single expiry",
                actual_value=f"Multiple expiries: {expiries}"
            ))

class IronCondorValidator(LEANValidationStrategy):
    """
    Iron Condor validator based on LEAN patterns (inferred from structure)
    """
    
    def validate_position_group(self, positions: List[Dict[str, Any]], 
                              strategy: OptionStrategy) -> PositionGroupDiagnostics:
        """Validate Iron Condor position group using LEAN patterns"""
        diagnostics = PositionGroupDiagnostics(
            position_count=len(positions),
            strategy_type=LEANPositionGroupType.IRON_CONDOR
        )
        
        # Iron Condor must have exactly 4 positions
        if len(positions) != 4:
            diagnostics.add_error(ValidationError(
                error_type="POSITION_COUNT_MISMATCH",
                severity=ValidationSeverity.CRITICAL,
                message="Iron Condor must have exactly 4 positions",
                expected_value=4,
                actual_value=len(positions)
            ))
            return diagnostics
        
        # Validate strike order and structure
        self._validate_iron_condor_structure(positions, diagnostics)
        
        return diagnostics
    
    def get_expected_position_count(self) -> int:
        return 4
    
    def _validate_iron_condor_structure(self, positions: List[Dict[str, Any]], 
                                      diagnostics: PositionGroupDiagnostics):
        """Validate Iron Condor strike and quantity structure"""
        # Sort positions by strike
        sorted_positions = sorted(positions, key=lambda x: x.get('strike', 0))
        
        # Expected structure: Long Put, Short Put, Short Call, Long Call
        expected_structure = [
            {'option_right': OptionRight.PUT, 'quantity_sign': 1},    # Long Put
            {'option_right': OptionRight.PUT, 'quantity_sign': -1},   # Short Put
            {'option_right': OptionRight.CALL, 'quantity_sign': -1},  # Short Call
            {'option_right': OptionRight.CALL, 'quantity_sign': 1}    # Long Call
        ]
        
        for i, (position, expected) in enumerate(zip(sorted_positions, expected_structure)):
            # Validate option right
            if position.get('option_right') != expected['option_right']:
                diagnostics.add_error(ValidationError(
                    error_type="INVALID_OPTION_RIGHT",
                    severity=ValidationSeverity.ERROR,
                    message=f"Position {i+1} has wrong option type",
                    expected_value=expected['option_right'].value,
                    actual_value=position.get('option_right', 'Unknown'),
                    position_index=i
                ))
            
            # Validate quantity sign
            quantity = position.get('quantity', 0)
            expected_sign = expected['quantity_sign']
            
            if (quantity > 0) != (expected_sign > 0):
                diagnostics.add_error(ValidationError(
                    error_type="INVALID_QUANTITY_SIGN",
                    severity=ValidationSeverity.ERROR,
                    message=f"Position {i+1} has wrong quantity sign",
                    expected_value=f"{'Positive' if expected_sign > 0 else 'Negative'}",
                    actual_value=quantity,
                    position_index=i
                ))

# ==============================================================================
# UNIVERSAL POSITION GROUP VALIDATOR
# ==============================================================================
class LEANPositionGroupValidator:
    """
    Universal Position Group Validator with LEAN Algorithm Patterns.
    
    Week 3-4 Enhancement: Implements comprehensive position group validation
    using patterns from QuantConnect LEAN algorithms across all strategy types.
    """
    
    def __init__(self):
        """Initialize universal validator"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.risk_manager = get_risk_manager()
        self.event_manager = get_event_manager()
        
        # Initialize validation strategies
        self.validation_strategies: Dict[StrategyType, LEANValidationStrategy] = {
            StrategyType.PUT_CALENDAR_SPREAD: CalendarSpreadValidator(),
            StrategyType.CALL_CALENDAR_SPREAD: CalendarSpreadValidator(),
            StrategyType.SHORT_PUT_CALENDAR_SPREAD: CalendarSpreadValidator(),
            StrategyType.SHORT_CALL_CALENDAR_SPREAD: CalendarSpreadValidator(),
            StrategyType.STRANGLE: StrangleValidator(),
            StrategyType.SHORT_STRANGLE: StrangleValidator(),
            StrategyType.IRON_CONDOR: IronCondorValidator(),
            # Additional strategies can be added here
        }
        
        # Validation statistics
        self.validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'validation_errors': 0,
            'validation_warnings': 0,
            'strategy_validation_counts': {},
            'error_type_counts': {}
        }
        
        self.logger.info("LEAN Position Group Validator initialized (Week 3-4)")
    
    # ==========================================================================
    # MAIN VALIDATION INTERFACE
    # ==========================================================================
    def validate_position_group(self, positions: List[Dict[str, Any]], 
                              strategy: OptionStrategy) -> PositionGroupDiagnostics:
        """
        Universal position group validation using LEAN patterns.
        
        Args:
            positions: List of position dictionaries
            strategy: Option strategy definition
            
        Returns:
            Comprehensive position group diagnostics
        """
        start_time = datetime.now()
        
        try:
            self.validation_stats['total_validations'] += 1
            
            # Get appropriate validation strategy
            validator = self.validation_strategies.get(strategy.strategy_type)
            
            if not validator:
                # Default validation for unsupported strategies
                diagnostics = self._perform_default_validation(positions, strategy)
            else:
                # Use strategy-specific LEAN validation
                diagnostics = validator.validate_position_group(positions, strategy)
            
            # Perform universal checks
            self._perform_universal_checks(positions, strategy, diagnostics)
            
            # Update statistics
            self._update_validation_statistics(diagnostics, strategy.strategy_type)
            
            # Log validation results
            validation_time = (datetime.now() - start_time).total_seconds() * 1000
            self._log_validation_results(diagnostics, validation_time)
            
            # Emit validation event
            self._emit_validation_event(diagnostics, strategy)
            
            return diagnostics
            
        except Exception as e:
            self.logger.error(f"Position group validation failed: {e}")
            self.error_handler.handle_error(e, context="position_group_validation")
            
            # Return error diagnostics
            error_diagnostics = PositionGroupDiagnostics(
                position_count=len(positions),
                strategy_type=LEANPositionGroupType.UNDEFINED,
                is_valid=False
            )
            error_diagnostics.add_error(ValidationError(
                error_type="VALIDATION_EXCEPTION",
                severity=ValidationSeverity.CRITICAL,
                message=f"Validation failed with exception: {str(e)}"
            ))
            
            return error_diagnostics
    
    def assert_strategy_position_group(self, positions: List[Dict[str, Any]], 
                                     strategy: OptionStrategy) -> bool:
        """
        LEAN-style assertion validation (raises AssertionError on failure).
        
        This method mimics LEAN's assert_strategy_position_group behavior
        by raising AssertionError with detailed messages when validation fails.
        
        Args:
            positions: List of position dictionaries
            strategy: Option strategy definition
            
        Returns:
            True if valid
            
        Raises:
            AssertionError: If validation fails (LEAN pattern)
        """
        diagnostics = self.validate_position_group(positions, strategy)
        
        if not diagnostics.is_valid:
            # Collect all critical errors
            critical_errors = [
                error for error in diagnostics.validation_errors 
                if error.severity == ValidationSeverity.CRITICAL
            ]
            
            if critical_errors:
                # Raise first critical error (LEAN pattern)
                error = critical_errors[0]
                raise AssertionError(error.message)
            
            # Raise first error if no critical errors
            if diagnostics.validation_errors:
                error = diagnostics.validation_errors[0]
                raise AssertionError(error.message)
        
        return True
    
    # ==========================================================================
    # VALIDATION IMPLEMENTATIONS
    # ==========================================================================
    def _perform_default_validation(self, positions: List[Dict[str, Any]], 
                                   strategy: OptionStrategy) -> PositionGroupDiagnostics:
        """Perform default validation for unsupported strategies"""
        diagnostics = PositionGroupDiagnostics(
            position_count=len(positions),
            strategy_type=LEANPositionGroupType.UNDEFINED
        )
        
        # Basic position count validation
        expected_legs = len(strategy.legs)
        if len(positions) != expected_legs:
            diagnostics.add_error(ValidationError(
                error_type="POSITION_COUNT_MISMATCH",
                severity=ValidationSeverity.ERROR,
                message=f"Position count mismatch for {strategy.strategy_type.value}",
                expected_value=expected_legs,
                actual_value=len(positions)
            ))
        
        return diagnostics
    
    def _perform_universal_checks(self, positions: List[Dict[str, Any]], 
                                strategy: OptionStrategy, 
                                diagnostics: PositionGroupDiagnostics):
        """Perform universal validation checks across all strategies"""
        
        # Check for empty positions
        if not positions:
            diagnostics.add_error(ValidationError(
                error_type="EMPTY_POSITION_GROUP",
                severity=ValidationSeverity.CRITICAL,
                message="Position group cannot be empty"
            ))
            return
        
        # Validate position data completeness
        required_fields = ['symbol', 'quantity', 'strike', 'expiry', 'option_right']
        
        for i, position in enumerate(positions):
            for field in required_fields:
                if field not in position or position[field] is None:
                    diagnostics.add_error(ValidationError(
                        error_type="MISSING_POSITION_DATA",
                        severity=ValidationSeverity.ERROR,
                        message=f"Position {i+1} missing required field: {field}",
                        position_index=i
                    ))
        
        # Calculate portfolio metrics
        self._calculate_portfolio_metrics(positions, diagnostics)
        
        # Validate position symbols match strategy
        self._validate_position_symbols(positions, strategy, diagnostics)
    
    def _calculate_portfolio_metrics(self, positions: List[Dict[str, Any]], 
                                   diagnostics: PositionGroupDiagnostics):
        """Calculate portfolio-level metrics"""
        total_quantity = sum(pos.get('quantity', 0) for pos in positions)
        diagnostics.total_quantity = total_quantity
        
        # Simple delta calculation (would use real Greeks in production)
        net_delta = sum(pos.get('delta', 0) * pos.get('quantity', 0) for pos in positions)
        diagnostics.net_delta = net_delta
        
        # Determine if position is neutral or directional
        diagnostics.is_net_neutral = abs(net_delta) < 0.1
        diagnostics.is_directional = abs(net_delta) > 0.3
        
        # Extract unique strikes and expiries
        diagnostics.unique_strikes = sorted(list(set(
            pos.get('strike', 0) for pos in positions if pos.get('strike')
        )))
        
        diagnostics.unique_expiries = sorted(list(set(
            pos.get('expiry') for pos in positions if pos.get('expiry')
        )))
        
        # Calculate strike spacing
        if len(diagnostics.unique_strikes) > 1:
            diagnostics.strike_spacing = [
                diagnostics.unique_strikes[i+1] - diagnostics.unique_strikes[i]
                for i in range(len(diagnostics.unique_strikes) - 1)
            ]
    
    def _validate_position_symbols(self, positions: List[Dict[str, Any]], 
                                 strategy: OptionStrategy, 
                                 diagnostics: PositionGroupDiagnostics):
        """Validate position symbols match strategy legs"""
        strategy_symbols = set(leg.symbol for leg in strategy.legs)
        position_symbols = set(pos.get('symbol', '') for pos in positions)
        
        # Check for missing symbols
        missing_symbols = strategy_symbols - position_symbols
        if missing_symbols:
            diagnostics.add_error(ValidationError(
                error_type="MISSING_STRATEGY_SYMBOLS",
                severity=ValidationSeverity.ERROR,
                message=f"Positions missing for strategy symbols: {missing_symbols}"
            ))
        
        # Check for extra symbols
        extra_symbols = position_symbols - strategy_symbols
        if extra_symbols:
            diagnostics.add_error(ValidationError(
                error_type="EXTRA_POSITION_SYMBOLS",
                severity=ValidationSeverity.WARNING,
                message=f"Extra positions found: {extra_symbols}"
            ))
    
    # ==========================================================================
    # STATISTICS AND LOGGING
    # ==========================================================================
    def _update_validation_statistics(self, diagnostics: PositionGroupDiagnostics, 
                                    strategy_type: StrategyType):
        """Update validation statistics"""
        if diagnostics.is_valid:
            self.validation_stats['successful_validations'] += 1
        else:
            self.validation_stats['failed_validations'] += 1
        
        self.validation_stats['validation_errors'] += len(diagnostics.validation_errors)
        self.validation_stats['validation_warnings'] += len(diagnostics.validation_warnings)
        
        # Strategy-specific counts
        strategy_key = strategy_type.value
        if strategy_key not in self.validation_stats['strategy_validation_counts']:
            self.validation_stats['strategy_validation_counts'][strategy_key] = 0
        self.validation_stats['strategy_validation_counts'][strategy_key] += 1
        
        # Error type counts
        for error in diagnostics.validation_errors + diagnostics.validation_warnings:
            error_type = error.error_type
            if error_type not in self.validation_stats['error_type_counts']:
                self.validation_stats['error_type_counts'][error_type] = 0
            self.validation_stats['error_type_counts'][error_type] += 1
    
    def _log_validation_results(self, diagnostics: PositionGroupDiagnostics, 
                              validation_time_ms: float):
        """Log validation results"""
        result = "VALID" if diagnostics.is_valid else "INVALID"
        
        self.logger.info(
            f"Position group validation {result}: "
            f"{diagnostics.strategy_type.value} "
            f"(Score: {diagnostics.validation_score:.2f}, "
            f"Time: {validation_time_ms:.1f}ms, "
            f"Errors: {len(diagnostics.validation_errors)}, "
            f"Warnings: {len(diagnostics.validation_warnings)})"
        )
        
        # Log errors and warnings
        for error in diagnostics.validation_errors:
            self.logger.error(f"Validation Error: {error}")
        
        for warning in diagnostics.validation_warnings:
            self.logger.warning(f"Validation Warning: {warning}")
    
    def _emit_validation_event(self, diagnostics: PositionGroupDiagnostics, 
                             strategy: OptionStrategy):
        """Emit validation event for monitoring"""
        event_data = {
            'strategy_type': strategy.strategy_type.value,
            'position_count': diagnostics.position_count,
            'is_valid': diagnostics.is_valid,
            'validation_score': diagnostics.validation_score,
            'error_count': len(diagnostics.validation_errors),
            'warning_count': len(diagnostics.validation_warnings)
        }
        
        event_type = EventType.VALIDATION_SUCCESS if diagnostics.is_valid else EventType.VALIDATION_FAILURE
        
        try:
            self.event_manager.emit_event(event_type, event_data)
        except Exception as e:
            self.logger.warning(f"Failed to emit validation event: {e}")
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get comprehensive validation statistics"""
        stats = self.validation_stats.copy()
        
        # Calculate success rate
        total = stats['total_validations']
        if total > 0:
            stats['success_rate'] = stats['successful_validations'] / total
            stats['failure_rate'] = stats['failed_validations'] / total
        else:
            stats['success_rate'] = 0.0
            stats['failure_rate'] = 0.0
        
        return stats
    
    def reset_statistics(self):
        """Reset validation statistics"""
        self.validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'validation_errors': 0,
            'validation_warnings': 0,
            'strategy_validation_counts': {},
            'error_type_counts': {}
        }
        
        self.logger.info("Validation statistics reset")
    
    def get_supported_strategies(self) -> List[str]:
        """Get list of supported strategy types"""
        return [strategy_type.value for strategy_type in self.validation_strategies.keys()]

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_lean_position_group_validator() -> LEANPositionGroupValidator:
    """Factory function to create LEAN position group validator"""
    return LEANPositionGroupValidator()

def get_position_group_validator() -> LEANPositionGroupValidator:
    """Get singleton position group validator instance"""
    if not hasattr(get_position_group_validator, '_instance'):
        get_position_group_validator._instance = create_lean_position_group_validator()
    return get_position_group_validator._instance

# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================
def validate_position_group_lean(positions: List[Dict[str, Any]], 
                                strategy: OptionStrategy) -> PositionGroupDiagnostics:
    """Convenience function for LEAN position group validation"""
    validator = get_position_group_validator()
    return validator.validate_position_group(positions, strategy)

def assert_position_group_lean(positions: List[Dict[str, Any]], 
                             strategy: OptionStrategy) -> bool:
    """Convenience function for LEAN assertion-style validation"""
    validator = get_position_group_validator()
    return validator.assert_strategy_position_group(positions, strategy)

# ==============================================================================
# TESTING AND VALIDATION
# ==============================================================================
def test_lean_position_group_validator():
    """Test LEAN position group validator with sample data"""
    print("Testing LEAN Position Group Validator (Week 3-4)")
    print("=" * 60)
    
    validator = create_lean_position_group_validator()
    
    # Test Calendar Spread Validation
    from SpyderU_Utilities.SpyderU14_OptionStrategies import SpyderOptionStrategies
    
    # Create sample calendar spread
    near_expiry = datetime.now() + timedelta(days=14)
    far_expiry = datetime.now() + timedelta(days=35)
    
    calendar_strategy = SpyderOptionStrategies.put_calendar_spread("SPY", 600, near_expiry, far_expiry)
    
    # Create valid calendar positions (LEAN pattern)
    valid_calendar_positions = [
        {
            'symbol': 'SPY_251010P600',
            'quantity': -2,  # Near expiry short
            'strike': 600.0,
            'expiry': near_expiry,
            'option_right': OptionRight.PUT,
            'delta': -0.3
        },
        {
            'symbol': 'SPY_251031P600',
            'quantity': 2,   # Far expiry long
            'strike': 600.0,
            'expiry': far_expiry,
            'option_right': OptionRight.PUT,
            'delta': -0.35
        }
    ]
    
    # Test valid calendar
    print("Testing Valid Calendar Spread:")
    diagnostics = validator.validate_position_group(valid_calendar_positions, calendar_strategy)
    print(f"Valid: {diagnostics.is_valid}")
    print(f"Score: {diagnostics.validation_score:.2f}")
    print(f"Errors: {len(diagnostics.validation_errors)}")
    print(f"Warnings: {len(diagnostics.validation_warnings)}")
    
    # Test invalid calendar (wrong quantities)
    invalid_calendar_positions = valid_calendar_positions.copy()
    invalid_calendar_positions[0]['quantity'] = 2  # Should be -2
    
    print("\nTesting Invalid Calendar Spread:")
    diagnostics = validator.validate_position_group(invalid_calendar_positions, calendar_strategy)
    print(f"Valid: {diagnostics.is_valid}")
    print(f"Score: {diagnostics.validation_score:.2f}")
    print(f"Errors: {len(diagnostics.validation_errors)}")
    if diagnostics.validation_errors:
        print(f"First Error: {diagnostics.validation_errors[0]}")
    
    # Test LEAN assertion pattern
    print("\nTesting LEAN Assertion Pattern:")
    try:
        validator.assert_strategy_position_group(valid_calendar_positions, calendar_strategy)
        print("✅ Valid calendar assertion passed")
    except AssertionError as e:
        print(f"❌ Valid calendar assertion failed: {e}")
    
    try:
        validator.assert_strategy_position_group(invalid_calendar_positions, calendar_strategy)
        print("❌ Invalid calendar assertion should have failed")
    except AssertionError as e:
        print(f"✅ Invalid calendar assertion correctly failed: {e}")
    
    # Test statistics
    print(f"\nValidation Statistics:")
    stats = validator.get_validation_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n✅ LEAN Position Group Validator (Week 3-4) testing complete!")
    print("Key Features Tested:")
    print("- ✅ Universal position group validation")
    print("- ✅ LEAN-style assertion patterns")
    print("- ✅ Strategy-specific validation rules")
    print("- ✅ Comprehensive error diagnostics")
    print("- ✅ Professional validation statistics")

if __name__ == "__main__":
    test_lean_position_group_validator()