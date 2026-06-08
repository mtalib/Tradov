#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovV_QuantModels
Module: TradovV01_QuantEngine.py
Purpose: Quantitative models orchestrator - coordination and delegation only

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-31 Time: 18:30:00

Module Description:
    Pure orchestration engine for all quantitative models in the Tradov system.
    No longer performs any calculations - delegates all pricing to V05_PricingEngine
    and all risk calculations to V04_RiskManager. Focuses solely on coordination,
    model selection logic, data flow management, and providing unified interface
    for external consumers. Eliminates all calculation duplications.

Consolidation Notes:
    - REMOVED: All pricing calculations (delegated to V05_PricingEngine)
    - REMOVED: All risk calculations (delegated to V04_RiskManager)
    - REMOVED: Duplicate model implementations
    - ENHANCED: Orchestration and coordination logic
    - ENHANCED: Data flow management between V04/V05
    - MAINTAINED: Unified external interface
    - OPTIMIZED: For pure coordination performance
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
from datetime import datetime, UTC
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# TradovB08_MultiClientDataManager (IB) has been removed.

# Import consolidated V-series modules
try:
    from .TradovV04_RiskManager import TradovRiskManager, RiskParameters, RiskMetrics  # noqa: F401
    from .TradovV05_PricingEngine import (
        TradovPricingEngine,
        OptionContract,
        PricingParameters,
        PricingResult,  # noqa: F401
    )

    CONSOLIDATED_MODULES_AVAILABLE = True
except ImportError:
    logging.info("⚠️  Consolidated V04/V05 modules not available")
    TradovRiskManager = None
    TradovPricingEngine = None
    CONSOLIDATED_MODULES_AVAILABLE = False


# ==============================================================================
# CONFIGURATION CONSTANTS
# ==============================================================================
class RequestType(Enum):
    """Types of quantitative requests."""

    PRICE_SINGLE = "price_single"
    PRICE_PORTFOLIO = "price_portfolio"
    CALCULATE_GREEKS = "calculate_greeks"
    ASSESS_RISK = "assess_risk"
    STRESS_TEST = "stress_test"
    MODEL_VALIDATION = "model_validation"


class DataSource(Enum):
    """Data source types from TradovB08."""

    CORE_DATA = 3  # Client 3: Core market data
    TRAD_OPTIONS = 4  # Client 4: TRAD options chains
    MARKET_INTERNALS = 6  # Client 6: VUD + market internals
    INTERNATIONAL = 10  # Client 10: International markets


class Priority(Enum):
    """Request priority levels."""

    CRITICAL = 1  # Real-time trading decisions
    HIGH = 2  # Risk management
    MEDIUM = 3  # Portfolio analysis
    LOW = 4  # Research and backtesting


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class QuantRequest:
    """Unified quantitative request structure."""

    request_id: str
    request_type: RequestType
    priority: Priority
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    timeout_seconds: float = 30.0
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class QuantResponse:
    """Unified quantitative response structure."""

    request_id: str
    success: bool
    data: dict[str, Any]
    execution_time_ms: float
    model_used: str | None = None
    warnings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationMetrics:
    """Orchestration performance metrics."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0.0
    requests_by_type: dict[str, int] = field(default_factory=dict)
    requests_by_priority: dict[str, int] = field(default_factory=dict)
    pricing_engine_calls: int = 0
    risk_manager_calls: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(UTC))


# ==============================================================================
# MAIN ORCHESTRATOR CLASS
# ==============================================================================
class TradovQuantEngine:
    """
    Pure quantitative models orchestrator for Tradov trading system.

    Provides unified interface for all quantitative operations while delegating
    all calculations to specialized engines. No duplicate calculations - acts
    solely as coordinator, data flow manager, and external interface provider.

    Key Responsibilities:
    - Request routing to appropriate engines (V04/V05)
    - Data flow coordination between modules
    - Performance monitoring and optimization
    - Error handling and retry logic
    - Unified external interface
    - Model lifecycle management
    """

    def __init__(
        self, config: dict[str, Any] = None, data_manager: Any = None
    ):
        """Initialize pure orchestration engine."""
        self.config = config or {}
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)

        # Orchestration state
        self.is_running = False
        self.shutdown_requested = False

        # Performance metrics
        self.metrics = OrchestrationMetrics()

        # Request tracking
        self.active_requests: dict[str, QuantRequest] = {}
        self.request_history: list[QuantResponse] = []
        self.max_history_size = self.config.get("max_history_size", 1000)

        # Initialize consolidated engines
        self.pricing_engine: TradovPricingEngine | None = None
        self.risk_manager: TradovRiskManager | None = None

        if CONSOLIDATED_MODULES_AVAILABLE:
            self._initialize_engines()
        else:
            self.logger.error("Consolidated modules V04/V05 not available")
            raise ImportError(
                "Cannot initialize without V04_RiskManager and V05_PricingEngine"
            )

        # Threading for async operations
        self.thread_pool = ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 8)
        )

        self.logger.info("TradovQuantEngine (Orchestrator) initialized successfully")

    def _initialize_engines(self):
        """Initialize the consolidated pricing and risk engines."""
        try:
            # Initialize V05 Pricing Engine
            pricing_config = self.config.get("pricing_engine", {})
            self.pricing_engine = TradovPricingEngine(
                config=pricing_config, data_manager=self.data_manager
            )

            # Initialize V04 Risk Manager
            risk_config = self.config.get("risk_manager", {})
            self.risk_manager = TradovRiskManager(
                config=risk_config, data_manager=self.data_manager
            )

            self.logger.info("Consolidated engines V04/V05 initialized successfully")

        except Exception as e:
            self.logger.error("Failed to initialize engines: %s", e, exc_info=True)
            raise

    # ==========================================================================
    # MAIN ORCHESTRATION INTERFACE
    # ==========================================================================

    async def start(self):
        """Start the orchestration engine."""
        if self.is_running:
            self.logger.warning("Engine already running")
            return

        self.is_running = True
        self.shutdown_requested = False

        self.logger.info("TradovQuantEngine orchestration started")

    async def shutdown(self):
        """Graceful shutdown of orchestration engine."""
        self.logger.info("Initiating graceful shutdown...")

        self.shutdown_requested = True

        # Wait for active requests to complete
        if self.active_requests:
            self.logger.info(
                "Waiting for %s active requests...", len(self.active_requests)
            )
            await asyncio.sleep(2.0)  # Grace period

        # Shutdown engines
        if self.pricing_engine:
            await self.pricing_engine.shutdown()

        if self.risk_manager:
            # Risk manager doesn't have async shutdown, but we can clean up
            self.risk_manager.reset_risk_manager()

        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)

        self.is_running = False
        self.logger.info("TradovQuantEngine shutdown complete")

    # ==========================================================================
    # UNIFIED REQUEST PROCESSING
    # ==========================================================================

    async def process_request(self, request: QuantRequest) -> QuantResponse:
        """
        Process unified quantitative request.

        Args:
            request: Quantitative request specification

        Returns:
            QuantResponse: Unified response with results
        """
        start_time = time.time()

        # Validate engine availability
        if not self.is_running:
            return self._create_error_response(
                request, "Engine not running", start_time
            )

        try:
            # Track request
            self.active_requests[request.request_id] = request
            self._update_request_metrics(request)

            # Route request to appropriate handler
            if request.request_type == RequestType.PRICE_SINGLE:
                response_data = await self._handle_price_single(request)
            elif request.request_type == RequestType.PRICE_PORTFOLIO:
                response_data = await self._handle_price_portfolio(request)
            elif request.request_type == RequestType.CALCULATE_GREEKS:
                response_data = await self._handle_calculate_greeks(request)
            elif request.request_type == RequestType.ASSESS_RISK:
                response_data = await self._handle_assess_risk(request)
            elif request.request_type == RequestType.STRESS_TEST:
                response_data = await self._handle_stress_test(request)
            elif request.request_type == RequestType.MODEL_VALIDATION:
                response_data = await self._handle_model_validation(request)
            else:
                raise ValueError(f"Unknown request type: {request.request_type}")

            # Create successful response
            execution_time = (time.time() - start_time) * 1000
            response = QuantResponse(
                request_id=request.request_id,
                success=True,
                data=response_data,
                execution_time_ms=execution_time,
            )

            # Update metrics
            self.metrics.successful_requests += 1
            self._update_response_time(execution_time)

            return response

        except Exception as e:
            self.logger.error("Error processing request %s: %s", request.request_id, e, exc_info=True)  # noqa: E501
            self.metrics.failed_requests += 1

            return self._create_error_response(request, str(e), start_time)

        finally:
            # Clean up
            if request.request_id in self.active_requests:
                del self.active_requests[request.request_id]

    # ==========================================================================
    # REQUEST HANDLERS (DELEGATION TO V04/V05)
    # ==========================================================================

    async def _handle_price_single(self, request: QuantRequest) -> dict[str, Any]:
        """Handle single option pricing request."""
        if not self.pricing_engine:
            raise ValueError("Pricing engine not available")

        # Extract contract from request data
        contract_data = request.data.get("contract")
        if not contract_data:
            raise ValueError("Contract data required for pricing")

        # Convert to OptionContract
        contract = self._convert_to_option_contract(contract_data)

        # Get pricing parameters
        params_data = request.data.get("parameters", {})
        parameters = self._convert_to_pricing_parameters(params_data)

        # Delegate to V05 PricingEngine
        result = await self.pricing_engine.price_option(contract, parameters)
        self.metrics.pricing_engine_calls += 1

        return {
            "price": result.theoretical_price,
            "greeks": {
                "delta": result.greeks.delta,
                "gamma": result.greeks.gamma,
                "vega": result.greeks.vega,
                "theta": result.greeks.theta,
                "rho": result.greeks.rho,
                "vanna": result.greeks.vanna,
                "volga": result.greeks.volga,
                "charm": result.greeks.charm,
                "veta": result.greeks.veta,
            },
            "model_used": result.model_used.value,
            "early_exercise_premium": result.early_exercise_premium,
            "calculation_time_ms": result.calculation_time_ms,
            "accuracy_estimate": result.accuracy_estimate,
            "warnings": result.warnings,
        }

    async def _handle_price_portfolio(self, request: QuantRequest) -> dict[str, Any]:
        """Handle portfolio pricing request."""
        if not self.pricing_engine:
            raise ValueError("Pricing engine not available")

        # Extract contracts from request data
        contracts_data = request.data.get("contracts")
        if not contracts_data:
            raise ValueError("Contracts data required for portfolio pricing")

        # Convert to OptionContracts
        contracts = [
            self._convert_to_option_contract(contract_data)
            for contract_data in contracts_data
        ]

        # Get pricing parameters
        params_data = request.data.get("parameters", {})
        parameters = self._convert_to_pricing_parameters(params_data)

        # Delegate to V05 PricingEngine
        results = await self.pricing_engine.price_portfolio(contracts, parameters)
        self.metrics.pricing_engine_calls += 1

        # Aggregate results
        portfolio_value = sum(result.theoretical_price for result in results)
        portfolio_delta = sum(result.greeks.delta for result in results)
        portfolio_gamma = sum(result.greeks.gamma for result in results)
        portfolio_vega = sum(result.greeks.vega for result in results)
        portfolio_theta = sum(result.greeks.theta for result in results)

        return {
            "portfolio_value": portfolio_value,
            "portfolio_greeks": {
                "delta": portfolio_delta,
                "gamma": portfolio_gamma,
                "vega": portfolio_vega,
                "theta": portfolio_theta,
            },
            "individual_results": [
                {
                    "price": result.theoretical_price,
                    "delta": result.greeks.delta,
                    "model_used": result.model_used.value,
                }
                for result in results
            ],
            "total_contracts": len(results),
            "successful_pricings": sum(1 for r in results if r.convergence_achieved),
        }

    async def _handle_calculate_greeks(self, request: QuantRequest) -> dict[str, Any]:
        """Handle Greeks calculation request."""
        # Greeks are calculated as part of pricing, so delegate to pricing
        return await self._handle_price_single(request)

    async def _handle_assess_risk(self, request: QuantRequest) -> dict[str, Any]:
        """Handle risk assessment request."""
        if not self.risk_manager:
            raise ValueError("Risk manager not available")

        # Extract portfolio from request data
        portfolio_data = request.data.get("portfolio")
        if not portfolio_data:
            raise ValueError("Portfolio data required for risk assessment")

        # Get risk parameters
        params_data = request.data.get("parameters", {})
        risk_params = self._convert_to_risk_parameters(params_data)

        # Delegate to V04 RiskManager
        risk_metrics = await self.risk_manager.calculate_portfolio_risk(
            portfolio=portfolio_data, parameters=risk_params
        )
        self.metrics.risk_manager_calls += 1

        return {
            "var": risk_metrics.var,
            "cvar": risk_metrics.cvar,
            "expected_shortfall": risk_metrics.expected_shortfall,
            "cvar_var_ratio": risk_metrics.cvar_var_ratio,
            "portfolio_value": risk_metrics.portfolio_value,
            "maximum_drawdown": risk_metrics.maximum_drawdown,
            "sharpe_ratio": risk_metrics.sharpe_ratio,
            "risk_utilization": risk_metrics.risk_utilization,
            "diversification_ratio": risk_metrics.diversification_ratio,
            "model_accuracy": risk_metrics.model_accuracy,
            "calculation_method": risk_metrics.calculation_method.value,
            "warnings": risk_metrics.warnings,
        }

    async def _handle_stress_test(self, request: QuantRequest) -> dict[str, Any]:
        """Handle stress testing request."""
        if not self.risk_manager:
            raise ValueError("Risk manager not available")

        # Extract custom scenarios if provided
        custom_scenarios = request.data.get("custom_scenarios")

        # Delegate to V04 RiskManager
        stress_results = await self.risk_manager.run_stress_tests(custom_scenarios)
        self.metrics.risk_manager_calls += 1

        return {
            "total_scenarios": len(stress_results),
            "scenarios": [
                {
                    "name": result.scenario.name,
                    "description": result.scenario.description,
                    "portfolio_loss": result.portfolio_loss,
                    "loss_percentage": result.loss_percentage,
                    "var_breach": result.var_breach,
                    "cvar_breach": result.cvar_breach,
                    "hedge_recommendations": result.hedge_recommendations,
                    "recovery_time_estimate": result.recovery_time_estimate,
                }
                for result in stress_results
            ],
            "worst_scenario": (
                max(stress_results, key=lambda x: abs(x.portfolio_loss)).scenario.name
                if stress_results
                else None
            ),
        }

    async def _handle_model_validation(self, request: QuantRequest) -> dict[str, Any]:
        """Handle model validation request."""
        validation_results = {}

        # Get pricing engine performance if available
        if self.pricing_engine:
            pricing_performance = self.pricing_engine.get_performance_summary()
            validation_results["pricing_engine"] = pricing_performance

        # Get risk manager performance if available
        if self.risk_manager:
            risk_performance = self.risk_manager.get_performance_metrics()
            validation_results["risk_manager"] = risk_performance

        # Add orchestration metrics
        validation_results["orchestration"] = {
            "total_requests": self.metrics.total_requests,
            "success_rate": self.metrics.successful_requests
            / max(self.metrics.total_requests, 1),
            "avg_response_time_ms": self.metrics.avg_response_time_ms,
            "active_requests": len(self.active_requests),
            "pricing_engine_calls": self.metrics.pricing_engine_calls,
            "risk_manager_calls": self.metrics.risk_manager_calls,
        }

        return validation_results

    # ==========================================================================
    # DATA CONVERSION UTILITIES
    # ==========================================================================

    def _convert_to_option_contract(
        self, contract_data: dict[str, Any]
    ) -> "OptionContract":
        """Convert dictionary to OptionContract."""
        from Tradov.TradovV_QuantModels.TradovV05_PricingEngine import OptionType, ExerciseStyle, OptionContract  # noqa: E501

        return OptionContract(
            underlying_price=contract_data["underlying_price"],
            strike_price=contract_data["strike_price"],
            time_to_expiry=contract_data["time_to_expiry"],
            risk_free_rate=contract_data.get("risk_free_rate", 0.05),
            dividend_yield=contract_data.get("dividend_yield", 0.02),
            volatility=contract_data.get("volatility", 0.25),
            option_type=OptionType(contract_data.get("option_type", "call")),
            exercise_style=ExerciseStyle(
                contract_data.get("exercise_style", "american")
            ),
        )

    def _convert_to_pricing_parameters(
        self, params_data: dict[str, Any]
    ) -> "PricingParameters":
        """Convert dictionary to PricingParameters."""
        from Tradov.TradovV_QuantModels.TradovV05_PricingEngine import PricingModel, PricingParameters  # noqa: E501

        return PricingParameters(
            model=PricingModel(params_data.get("model", "auto")),
            binomial_steps=params_data.get("binomial_steps", 100),
            monte_carlo_sims=params_data.get("monte_carlo_sims", 10000),
            use_cache=params_data.get("use_cache", True),
            parallel_processing=params_data.get("parallel_processing", True),
        )

    def _convert_to_risk_parameters(
        self, params_data: dict[str, Any]
    ) -> "RiskParameters":
        """Convert dictionary to RiskParameters."""
        from Tradov.TradovV_QuantModels.TradovV04_RiskManager import RiskMethod

        return RiskParameters(
            confidence_level=params_data.get("confidence_level", 0.95),
            time_horizon=params_data.get("time_horizon", 1),
            method=RiskMethod(params_data.get("method", "historical")),
            lookback_days=params_data.get("lookback_days", 252),
            monte_carlo_sims=params_data.get("monte_carlo_sims", 10000),
        )

    # ==========================================================================
    # CONVENIENCE METHODS (HIGH-LEVEL INTERFACE)
    # ==========================================================================

    async def price_option(
        self,
        underlying_price: float,
        strike_price: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str = "call",
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.02,
    ) -> dict[str, Any]:
        """
        Convenient method for pricing single option.

        Args:
            underlying_price: Current underlying price
            strike_price: Option strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility
            option_type: 'call' or 'put'
            risk_free_rate: Risk-free rate
            dividend_yield: Dividend yield

        Returns:
            Dict with price and Greeks
        """
        request = QuantRequest(
            request_id=f"price_{int(time.time() * 1000)}",
            request_type=RequestType.PRICE_SINGLE,
            priority=Priority.HIGH,
            data={
                "contract": {
                    "underlying_price": underlying_price,
                    "strike_price": strike_price,
                    "time_to_expiry": time_to_expiry,
                    "volatility": volatility,
                    "option_type": option_type,
                    "risk_free_rate": risk_free_rate,
                    "dividend_yield": dividend_yield,
                }
            },
        )

        response = await self.process_request(request)

        if response.success:
            return response.data
        else:
            raise ValueError(
                f"Pricing failed: {response.data.get('error', 'Unknown error')}"
            )

    async def assess_portfolio_risk(
        self,
        portfolio: list[dict[str, Any]],
        confidence_level: float = 0.95,
        method: str = "historical",
    ) -> dict[str, Any]:
        """
        Convenient method for portfolio risk assessment.

        Args:
            portfolio: List of positions with market data
            confidence_level: VaR confidence level
            method: Risk calculation method

        Returns:
            Dict with risk metrics
        """
        request = QuantRequest(
            request_id=f"risk_{int(time.time() * 1000)}",
            request_type=RequestType.ASSESS_RISK,
            priority=Priority.HIGH,
            data={
                "portfolio": portfolio,
                "parameters": {"confidence_level": confidence_level, "method": method},
            },
        )

        response = await self.process_request(request)

        if response.success:
            return response.data
        else:
            raise ValueError(
                f"Risk assessment failed: {response.data.get('error', 'Unknown error')}"
            )

    # ==========================================================================
    # METRICS AND MONITORING
    # ==========================================================================

    def _update_request_metrics(self, request: QuantRequest):
        """Update request metrics."""
        self.metrics.total_requests += 1

        # Track by type
        request_type = request.request_type.value
        self.metrics.requests_by_type[request_type] = (
            self.metrics.requests_by_type.get(request_type, 0) + 1
        )

        # Track by priority
        priority = request.priority.name
        self.metrics.requests_by_priority[priority] = (
            self.metrics.requests_by_priority.get(priority, 0) + 1
        )

    def _update_response_time(self, execution_time_ms: float):
        """Update average response time."""
        current_avg = self.metrics.avg_response_time_ms
        total_requests = self.metrics.successful_requests

        self.metrics.avg_response_time_ms = (
            current_avg * (total_requests - 1) + execution_time_ms
        ) / total_requests

    def _create_error_response(
        self, request: QuantRequest, error_message: str, start_time: float
    ) -> QuantResponse:
        """Create error response."""
        execution_time = (time.time() - start_time) * 1000

        return QuantResponse(
            request_id=request.request_id,
            success=False,
            data={"error": error_message},
            execution_time_ms=execution_time,
            warnings=[f"Request failed: {error_message}"],
        )

    def get_orchestration_status(self) -> dict[str, Any]:
        """Get comprehensive orchestration status."""
        return {
            "engine_running": self.is_running,
            "active_requests": len(self.active_requests),
            "total_requests_processed": self.metrics.total_requests,
            "success_rate": self.metrics.successful_requests
            / max(self.metrics.total_requests, 1),
            "avg_response_time_ms": self.metrics.avg_response_time_ms,
            "engines_available": {
                "pricing_engine": self.pricing_engine is not None,
                "risk_manager": self.risk_manager is not None,
            },
            "requests_by_type": dict(self.metrics.requests_by_type),
            "requests_by_priority": dict(self.metrics.requests_by_priority),
            "pricing_engine_calls": self.metrics.pricing_engine_calls,
            "risk_manager_calls": self.metrics.risk_manager_calls,
            "last_metrics_reset": self.metrics.last_reset.isoformat(),
        }

    def reset_metrics(self):
        """Reset orchestration metrics."""
        self.metrics = OrchestrationMetrics()
        self.request_history.clear()
        self.logger.info("Orchestration metrics reset")


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_quant_engine(
    config: dict[str, Any] = None, data_manager: Any = None
) -> TradovQuantEngine:
    """Factory function to create TradovQuantEngine orchestrator."""
    return TradovQuantEngine(config, data_manager)


# ==============================================================================
# DEMONSTRATION AND TESTING
# ==============================================================================
async def main():
    """Demonstration of pure orchestration engine."""
    logging.info("=" * 80)
    logging.info("TRADOV V01 PURE ORCHESTRATION ENGINE DEMONSTRATION")
    logging.info("=" * 80)

    # Initialize orchestration engine
    config = {
        "max_workers": 4,
        "max_history_size": 100,
        "pricing_engine": {
            "default_model": "auto",
            "binomial_steps": 100,
            "use_cache": True,
        },
        "risk_manager": {"default_confidence": 0.95, "lookback_days": 252},
    }

    try:
        quant_engine = create_quant_engine(config)
        await quant_engine.start()

        logging.info("\n✅ Pure Orchestration Engine Started")
        logging.info("   • No calculation code - pure coordination only")
        logging.info("   • Delegates pricing to V05_PricingEngine")
        logging.info("   • Delegates risk to V04_RiskManager")
        logging.info("   • Unified interface for external consumers")

        # Test 1: Single Option Pricing
        logging.info("\n--- Test 1: Single Option Pricing (Delegated to V05) ---")
        try:
            result = await quant_engine.price_option(
                underlying_price=450.0,
                strike_price=455.0,
                time_to_expiry=30 / 365,
                volatility=0.25,
                option_type="call",
            )

            logging.info(f"   Option Price: ${result['price']:.4f}")
            logging.info(f"   Delta: {result['greeks']['delta']:.4f}")
            logging.info("   Model Used: %s", result['model_used'])
            logging.info(f"   Calculation Time: {result['calculation_time_ms']:.1f}ms")

        except Exception as e:
            logging.info("   ❌ Error: %s", e)

        # Test 2: Portfolio Risk Assessment
        logging.info("\n--- Test 2: Portfolio Risk Assessment (Delegated to V04) ---")
        try:
            sample_portfolio = [
                {
                    "id": "TRAD_CALL_455",
                    "type": "option",
                    "market_value": 3500,
                    "delta": 0.45,
                    "gamma": 0.02,
                    "vega": 0.15,
                },
                {
                    "id": "TRAD_PUT_445",
                    "type": "option",
                    "market_value": -1600,
                    "delta": -0.40,
                    "gamma": 0.02,
                    "vega": 0.15,
                },
            ]

            risk_result = await quant_engine.assess_portfolio_risk(
                portfolio=sample_portfolio, confidence_level=0.95, method="historical"
            )

            logging.info(f"   Portfolio VaR (95%): ${risk_result['var']:,.2f}")
            logging.info(f"   Portfolio CVaR (95%): ${risk_result['cvar']:,.2f}")
            logging.info(f"   Risk Utilization: {risk_result['risk_utilization']:.1%}")
            logging.info("   Calculation Method: %s", risk_result['calculation_method'])

        except Exception as e:
            logging.info("   ❌ Error: %s", e)

        # Test 3: Unified Request Processing
        logging.info("\n--- Test 3: Unified Request Processing ---")
        try:
            # Create a unified request
            unified_request = QuantRequest(
                request_id="test_unified_001",
                request_type=RequestType.PRICE_PORTFOLIO,
                priority=Priority.HIGH,
                data={
                    "contracts": [
                        {
                            "underlying_price": 450.0,
                            "strike_price": 450.0,
                            "time_to_expiry": 21 / 365,
                            "volatility": 0.22,
                            "option_type": "call",
                        },
                        {
                            "underlying_price": 450.0,
                            "strike_price": 450.0,
                            "time_to_expiry": 21 / 365,
                            "volatility": 0.22,
                            "option_type": "put",
                        },
                    ]
                },
            )

            response = await quant_engine.process_request(unified_request)

            if response.success:
                logging.info("   Request ID: %s", response.request_id)
                logging.info(f"   Portfolio Value: ${response.data['portfolio_value']:.2f}")
                logging.info(
                    f"   Portfolio Delta: {response.data['portfolio_greeks']['delta']:.4f}"
                )
                logging.info(f"   Execution Time: {response.execution_time_ms:.1f}ms")
                logging.info("   Contracts Processed: %s", response.data['total_contracts'])
            else:
                logging.info("   ❌ Request Failed: %s", response.data.get('error'))

        except Exception as e:
            logging.info("   ❌ Error: %s", e)

        # Test 4: Orchestration Status
        logging.info("\n--- Test 4: Orchestration Performance ---")
        try:
            status = quant_engine.get_orchestration_status()

            logging.info("   Engine Running: %s", status['engine_running'])
            logging.info("   Total Requests: %s", status['total_requests_processed'])
            logging.info(f"   Success Rate: {status['success_rate']:.1%}")
            logging.info(f"   Avg Response Time: {status['avg_response_time_ms']:.1f}ms")
            logging.info("   Pricing Engine Calls: %s", status['pricing_engine_calls'])
            logging.info("   Risk Manager Calls: %s", status['risk_manager_calls'])

            logging.info("\n   Engines Available:")
            for engine, available in status["engines_available"].items():
                logging.info("     %s: %s", engine, '✅' if available else '❌')

            if status["requests_by_type"]:
                logging.info("\n   Requests by Type:")
                for req_type, count in status["requests_by_type"].items():
                    logging.info("     %s: %s", req_type, count)

        except Exception as e:
            logging.info("   ❌ Error: %s", e)

        # Shutdown
        await quant_engine.shutdown()

        logging.info("\n" + "=" * 80)
        logging.info("✅ PURE ORCHESTRATION ENGINE FEATURES DEMONSTRATED:")
        logging.info("   • REMOVED: All pricing calculations (delegated to V05)")
        logging.info("   • REMOVED: All risk calculations (delegated to V04)")
        logging.info("   • ENHANCED: Pure coordination and orchestration logic")
        logging.info("   • ENHANCED: Unified external interface for all quant operations")
        logging.info("   • ENHANCED: Intelligent request routing and data flow management")
        logging.info("   • ENHANCED: Performance monitoring and metrics tracking")
        logging.info("   • MAINTAINED: Backward compatibility with existing interfaces")
        logging.info("   • OPTIMIZED: For coordination performance, not calculation")
        logging.info("   • INTEGRATED: Seamless V04/V05 engine coordination")
        logging.info("   • ELIMINATED: All calculation duplications across V-series")
        logging.info("=" * 80)

    except Exception as e:
        logging.info("\n❌ INITIALIZATION ERROR: %s", e)
        logging.info("   Make sure V04_RiskManager and V05_PricingEngine are available")


if __name__ == "__main__":
    asyncio.run(main())
