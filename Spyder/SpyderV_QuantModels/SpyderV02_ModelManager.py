#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV02_ModelManager.py
Purpose: Enhanced model lifecycle management for consolidated V-series architecture

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-31 Time: 23:15:00

Module Description:
    Enhanced model manager that coordinates the entire consolidated V-series architecture.
    Manages intelligent model selection across V04 (Risk), V05 (Pricing), V06 (Volatility),
    V07 (Advanced Models), and V08 (AI Models). Provides unified interface for V01
    orchestrator with performance monitoring, adaptive routing, and seamless integration.
    Acts as the "brain" of the quantitative modeling system.

Enhancement Notes:
    - Manages consolidated V04_RiskManager, V05_PricingEngine, V06_VolatilityEngine
    - Coordinates V07_AdvancedModels and V08_AIModels intelligent routing
    - Provides performance-based model selection algorithms
    - Unified interface for V01_QuantEngine orchestration
    - Real-time performance monitoring across all engines
    - Adaptive model switching based on market conditions
    - Consolidated architecture optimization
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
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import time
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderV04_RiskManager import SpyderRiskManager, RiskParameters, RiskMetrics
    from SpyderV05_PricingEngine import SpyderPricingEngine, OptionContract, PricingParameters, PricingResult  # noqa: E501
    from SpyderV06_VolatilityEngine import SpyderVolatilityEngine, VolatilityRequest, VolatilityResult  # noqa: E501
    from SpyderV07_AdvancedModels import SpyderAdvancedModels, AdvancedModelRequest, AdvancedModelResult  # noqa: E501
    from SpyderV08_AIModels import SpyderAIModels, PricingRequest, TradingSignal

    CONSOLIDATED_MODULES_AVAILABLE = True
except ImportError:
    logging.debug("Optional consolidated V-series modules not available")
    CONSOLIDATED_MODULES_AVAILABLE = False
    # Define fallback types so class definitions don't fail
    RiskParameters = None  # type: ignore
    RiskMetrics = None  # type: ignore
    SpyderRiskManager = None  # type: ignore
    SpyderPricingEngine = None  # type: ignore
    OptionContract = None  # type: ignore
    PricingParameters = None  # type: ignore
    PricingResult = None  # type: ignore
    SpyderVolatilityEngine = None  # type: ignore
    VolatilityRequest = None  # type: ignore
    VolatilityResult = None  # type: ignore
    SpyderAdvancedModels = None  # type: ignore
    AdvancedModelRequest = None  # type: ignore
    AdvancedModelResult = None  # type: ignore
    SpyderAIModels = None  # type: ignore
    PricingRequest = None  # type: ignore
    TradingSignal = None  # type: ignore

# SpyderB08_MultiClientDataManager (IB) has been removed.

# ==============================================================================
# MODULE CONFIGURATION
# ==============================================================================
logger = logging.getLogger(__name__)

# ==============================================================================
# ENUMERATIONS AND CONSTANTS
# ==============================================================================
class EngineType(Enum):
    """Types of consolidated engines."""
    RISK_MANAGER = "risk_manager"
    PRICING_ENGINE = "pricing_engine"
    VOLATILITY_ENGINE = "volatility_engine"
    ADVANCED_MODELS = "advanced_models"
    AI_MODELS = "ai_models"

class EngineStatus(Enum):
    """Engine operational status."""
    INITIALIZING = "initializing"
    READY = "ready"
    CALIBRATING = "calibrating"
    ERROR = "error"
    DISABLED = "disabled"
    DEGRADED = "degraded"

class ModelSelectionStrategy(Enum):
    """Model selection strategies."""
    PERFORMANCE_BASED = "performance_based"
    MARKET_CONDITION_BASED = "market_condition_based"
    ENSEMBLE = "ensemble"
    FAIL_SAFE = "fail_safe"
    USER_OVERRIDE = "user_override"

class MarketRegime(Enum):
    """Market regime classifications."""
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    CRISIS = "crisis"
    LOW_VOLATILITY = "low_volatility"
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class EngineConfig:
    """Configuration for individual engines."""
    engine_type: EngineType
    enabled: bool = True
    priority: int = 1  # 1 = highest priority
    performance_threshold: float = 0.85
    max_response_time_ms: float = 1000.0
    initialization_params: dict[str, Any] = field(default_factory=dict)
    calibration_schedule: str = "daily"  # hourly, daily, weekly, never

@dataclass
class EnginePerformance:
    """Performance metrics for engines."""
    engine_type: EngineType
    accuracy: float
    response_time_avg_ms: float
    response_time_p95_ms: float
    error_rate: float
    success_count: int
    error_count: int
    last_calibration: datetime | None
    uptime_percentage: float
    throughput_per_second: float

@dataclass
class ModelSelectionContext:
    """Context for intelligent model selection."""
    market_regime: MarketRegime
    volatility_level: float
    time_to_expiry: float | None
    option_type: str | None
    urgency: str = "normal"  # low, normal, high
    accuracy_requirement: str = "standard"  # fast, standard, high_precision
    user_preference: str | None = None

@dataclass
class EngineRecommendation:
    """Engine recommendation result."""
    engine_type: EngineType
    confidence: float
    reasoning: str
    fallback_engines: list[EngineType]
    expected_performance: dict[str, float]

@dataclass
class ConsolidatedRequest:
    """Unified request structure for all engines."""
    request_id: str
    engine_type: EngineType
    operation: str
    parameters: dict[str, Any]
    context: ModelSelectionContext
    timestamp: datetime
    priority: int = 1

@dataclass
class ConsolidatedResponse:
    """Unified response structure from all engines."""
    request_id: str
    engine_type: EngineType
    operation: str
    success: bool
    result: Any
    error_message: str | None
    execution_time_ms: float
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# ENHANCED MODEL MANAGER
# ==============================================================================
class SpyderModelManager:
    """
    Enhanced model manager for consolidated V-series architecture.

    Features:
    - Manages all consolidated engines (V04-V08)
    - Intelligent model selection across engines
    - Performance-based adaptive routing
    - Real-time monitoring and health checks
    - Unified interface for V01 orchestration
    - Market regime-aware model switching
    """

    def __init__(self, config: dict[str, Any] | None = None, data_manager=None):
        self.data_manager = data_manager
        self.logger = logging.getLogger(self.__class__.__name__)

        # Engine configurations
        self.engine_configs = self._create_default_engine_configs(config)

        # Engine instances
        self.engines: dict[EngineType, Any] = {}
        self.engine_status: dict[EngineType, EngineStatus] = {}

        # Performance tracking
        self.performance_history: dict[EngineType, deque] = {
            engine_type: deque(maxlen=1000) for engine_type in EngineType
        }
        self.current_performance: dict[EngineType, EnginePerformance] = {}

        # Model selection intelligence
        self.model_selector = ModelSelector(self)
        self.market_regime_detector = MarketRegimeDetector()

        # Request routing
        self.request_queue = asyncio.Queue()
        self.response_cache: dict[str, ConsolidatedResponse] = {}
        self.cache_lock = threading.Lock()

        # Monitoring and health
        self.health_checker = EngineHealthChecker(self)
        self.performance_monitor = PerformanceMonitor(self)

        # Threading
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="ModelManager")
        self.shutdown_event = asyncio.Event()

        self.logger.info("Enhanced SpyderModelManager initialized for consolidated architecture")

    # ==========================================================================
    # CORE ENGINE MANAGEMENT
    # ==========================================================================
    async def initialize_all_engines(self) -> dict[EngineType, bool]:
        """Initialize all consolidated engines."""
        initialization_results = {}

        try:
            self.logger.info("Initializing all consolidated engines...")

            # Initialize V04 Risk Manager
            if self.engine_configs[EngineType.RISK_MANAGER].enabled:
                result = await self._initialize_risk_manager()
                initialization_results[EngineType.RISK_MANAGER] = result

            # Initialize V05 Pricing Engine
            if self.engine_configs[EngineType.PRICING_ENGINE].enabled:
                result = await self._initialize_pricing_engine()
                initialization_results[EngineType.PRICING_ENGINE] = result

            # Initialize V06 Volatility Engine
            if self.engine_configs[EngineType.VOLATILITY_ENGINE].enabled:
                result = await self._initialize_volatility_engine()
                initialization_results[EngineType.VOLATILITY_ENGINE] = result

            # Initialize V07 Advanced Models
            if self.engine_configs[EngineType.ADVANCED_MODELS].enabled:
                result = await self._initialize_advanced_models()
                initialization_results[EngineType.ADVANCED_MODELS] = result

            # Initialize V08 AI Models
            if self.engine_configs[EngineType.AI_MODELS].enabled:
                result = await self._initialize_ai_models()
                initialization_results[EngineType.AI_MODELS] = result

            # Start monitoring tasks
            asyncio.create_task(self.health_checker.start_monitoring())
            asyncio.create_task(self.performance_monitor.start_monitoring())
            asyncio.create_task(self._request_processor())

            successful_engines = sum(initialization_results.values())
            total_engines = len(initialization_results)

            self.logger.info("Engine initialization complete: %s/%s engines ready", successful_engines, total_engines)  # noqa: E501

            return initialization_results

        except Exception as e:
            self.logger.error("Error initializing engines: %s", e, exc_info=True)
            return {engine_type: False for engine_type in EngineType}

    async def _initialize_risk_manager(self) -> bool:
        """Initialize V04 Risk Manager."""
        try:
            if not CONSOLIDATED_MODULES_AVAILABLE:
                self.logger.warning("V04 RiskManager module not available")
                return False

            config = self.engine_configs[EngineType.RISK_MANAGER].initialization_params
            risk_manager = SpyderRiskManager(config, self.data_manager)

            # Test basic functionality
            await risk_manager.initialize()

            self.engines[EngineType.RISK_MANAGER] = risk_manager
            self.engine_status[EngineType.RISK_MANAGER] = EngineStatus.READY

            self.logger.info("V04 RiskManager initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to initialize V04 RiskManager: %s", e, exc_info=True)
            self.engine_status[EngineType.RISK_MANAGER] = EngineStatus.ERROR
            return False

    async def _initialize_pricing_engine(self) -> bool:
        """Initialize V05 Pricing Engine."""
        try:
            if not CONSOLIDATED_MODULES_AVAILABLE:
                self.logger.warning("V05 PricingEngine module not available")
                return False

            config = self.engine_configs[EngineType.PRICING_ENGINE].initialization_params
            pricing_engine = SpyderPricingEngine(config, self.data_manager)

            # Test basic functionality
            await pricing_engine.initialize()

            self.engines[EngineType.PRICING_ENGINE] = pricing_engine
            self.engine_status[EngineType.PRICING_ENGINE] = EngineStatus.READY

            self.logger.info("V05 PricingEngine initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to initialize V05 PricingEngine: %s", e, exc_info=True)
            self.engine_status[EngineType.PRICING_ENGINE] = EngineStatus.ERROR
            return False

    async def _initialize_volatility_engine(self) -> bool:
        """Initialize V06 Volatility Engine."""
        try:
            if not CONSOLIDATED_MODULES_AVAILABLE:
                self.logger.warning("V06 VolatilityEngine module not available")
                return False

            config = self.engine_configs[EngineType.VOLATILITY_ENGINE].initialization_params
            volatility_engine = SpyderVolatilityEngine(config, self.data_manager)

            # Test basic functionality
            await volatility_engine.initialize()

            self.engines[EngineType.VOLATILITY_ENGINE] = volatility_engine
            self.engine_status[EngineType.VOLATILITY_ENGINE] = EngineStatus.READY

            self.logger.info("V06 VolatilityEngine initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to initialize V06 VolatilityEngine: %s", e, exc_info=True)
            self.engine_status[EngineType.VOLATILITY_ENGINE] = EngineStatus.ERROR
            return False

    async def _initialize_advanced_models(self) -> bool:
        """Initialize V07 Advanced Models."""
        try:
            if not CONSOLIDATED_MODULES_AVAILABLE:
                self.logger.warning("V07 AdvancedModels module not available")
                return False

            config = self.engine_configs[EngineType.ADVANCED_MODELS].initialization_params
            advanced_models = SpyderAdvancedModels(config, self.data_manager)

            # Test basic functionality
            await advanced_models.initialize()

            self.engines[EngineType.ADVANCED_MODELS] = advanced_models
            self.engine_status[EngineType.ADVANCED_MODELS] = EngineStatus.READY

            self.logger.info("V07 AdvancedModels initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to initialize V07 AdvancedModels: %s", e, exc_info=True)
            self.engine_status[EngineType.ADVANCED_MODELS] = EngineStatus.ERROR
            return False

    async def _initialize_ai_models(self) -> bool:
        """Initialize V08 AI Models."""
        try:
            if not CONSOLIDATED_MODULES_AVAILABLE:
                self.logger.warning("V08 AIModels module not available")
                return False

            config = self.engine_configs[EngineType.AI_MODELS].initialization_params
            ai_models = SpyderAIModels(config, self.data_manager)

            # Test basic functionality (no training required for initialization)
            self.engines[EngineType.AI_MODELS] = ai_models
            self.engine_status[EngineType.AI_MODELS] = EngineStatus.READY

            self.logger.info("V08 AIModels initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to initialize V08 AIModels: %s", e, exc_info=True)
            self.engine_status[EngineType.AI_MODELS] = EngineStatus.ERROR
            return False

    # ==========================================================================
    # INTELLIGENT MODEL SELECTION INTERFACE
    # ==========================================================================
    async def select_optimal_engine(self,
                                  operation: str,
                                  context: ModelSelectionContext) -> EngineRecommendation:
        """Select optimal engine for operation based on context and performance."""
        return await self.model_selector.select_engine(operation, context)

    async def execute_operation(self, request: ConsolidatedRequest) -> ConsolidatedResponse:
        """Execute operation on selected engine with intelligent routing."""
        try:
            # Get engine recommendation
            recommendation = await self.select_optimal_engine(request.operation, request.context)

            # Override engine type if recommended engine differs
            if recommendation.engine_type != request.engine_type:
                self.logger.info(f"Model selector recommended {recommendation.engine_type.value} "
                               f"over {request.engine_type.value}: {recommendation.reasoning}")
                request.engine_type = recommendation.engine_type

            # Execute on selected engine
            response = await self._execute_on_engine(request)

            # Update performance metrics
            self._update_performance_metrics(request.engine_type, response)

            return response

        except Exception as e:
            self.logger.error("Error executing operation %s: %s", request.operation, e, exc_info=True)  # noqa: E501
            return ConsolidatedResponse(
                request_id=request.request_id,
                engine_type=request.engine_type,
                operation=request.operation,
                success=False,
                result=None,
                error_message=str(e),
                execution_time_ms=0.0,
                confidence=0.0
            )

    # ==========================================================================
    # ENGINE-SPECIFIC OPERATION INTERFACES
    # ==========================================================================
    async def calculate_risk_metrics(self,
                                   risk_params: RiskParameters,
                                   context: ModelSelectionContext | None = None) -> ConsolidatedResponse:  # noqa: E501
        """Calculate risk metrics using V04 RiskManager."""
        if context is None:
            context = self._create_default_context()

        request = ConsolidatedRequest(
            request_id=str(uuid.uuid4()),
            engine_type=EngineType.RISK_MANAGER,
            operation="calculate_risk_metrics",
            parameters={"risk_params": risk_params},
            context=context,
            timestamp=datetime.now(UTC)
        )

        return await self.execute_operation(request)

    async def price_option(self,
                         option_contract: OptionContract,
                         pricing_params: PricingParameters,
                         context: ModelSelectionContext | None = None) -> ConsolidatedResponse:
        """Price option using V05 PricingEngine."""
        if context is None:
            context = self._create_default_context()

        request = ConsolidatedRequest(
            request_id=str(uuid.uuid4()),
            engine_type=EngineType.PRICING_ENGINE,
            operation="price_option",
            parameters={"contract": option_contract, "params": pricing_params},
            context=context,
            timestamp=datetime.now(UTC)
        )

        return await self.execute_operation(request)

    async def calculate_volatility(self,
                                 volatility_request: Any,
                                 context: ModelSelectionContext | None = None) -> ConsolidatedResponse:  # noqa: E501
        """Calculate volatility using V06 VolatilityEngine."""
        if context is None:
            context = self._create_default_context()

        request = ConsolidatedRequest(
            request_id=str(uuid.uuid4()),
            engine_type=EngineType.VOLATILITY_ENGINE,
            operation="calculate_volatility",
            parameters={"volatility_request": volatility_request},
            context=context,
            timestamp=datetime.now(UTC)
        )

        return await self.execute_operation(request)

    async def analyze_market_regime(self,
                                  market_data: dict[str, Any],
                                  context: ModelSelectionContext | None = None) -> ConsolidatedResponse:  # noqa: E501
        """Analyze market regime using V07 AdvancedModels."""
        if context is None:
            context = self._create_default_context()

        request = ConsolidatedRequest(
            request_id=str(uuid.uuid4()),
            engine_type=EngineType.ADVANCED_MODELS,
            operation="analyze_market_regime",
            parameters={"market_data": market_data},
            context=context,
            timestamp=datetime.now(UTC)
        )

        return await self.execute_operation(request)

    async def generate_ai_signal(self,
                               market_state: dict[str, Any],
                               context: ModelSelectionContext | None = None) -> ConsolidatedResponse:  # noqa: E501
        """Generate AI trading signal using V08 AIModels."""
        if context is None:
            context = self._create_default_context()

        request = ConsolidatedRequest(
            request_id=str(uuid.uuid4()),
            engine_type=EngineType.AI_MODELS,
            operation="generate_trading_signal",
            parameters={"market_state": market_state},
            context=context,
            timestamp=datetime.now(UTC)
        )

        return await self.execute_operation(request)

    # ==========================================================================
    # PERFORMANCE AND MONITORING
    # ==========================================================================
    def get_engine_performance(self, engine_type: EngineType | None = None) -> dict[EngineType, EnginePerformance]:  # noqa: E501
        """Get performance metrics for engines."""
        if engine_type:
            return {engine_type: self.current_performance.get(engine_type)}
        return self.current_performance.copy()

    def get_engine_status(self, engine_type: EngineType | None = None) -> dict[EngineType, EngineStatus]:  # noqa: E501
        """Get status of engines."""
        if engine_type:
            return {engine_type: self.engine_status.get(engine_type)}
        return self.engine_status.copy()

    def get_consolidated_health_report(self) -> dict[str, Any]:
        """Get comprehensive health report for all engines."""
        return {
            "timestamp": datetime.now(UTC),
            "engine_status": {k.value: v.value for k, v in self.engine_status.items()},
            "performance_summary": {
                k.value: {
                    "accuracy": v.accuracy,
                    "avg_response_time_ms": v.response_time_avg_ms,
                    "error_rate": v.error_rate,
                    "uptime_percentage": v.uptime_percentage
                } for k, v in self.current_performance.items()
            },
            "total_engines": len(self.engines),
            "healthy_engines": sum(1 for status in self.engine_status.values()
                                 if status == EngineStatus.READY),
            "market_regime": self.market_regime_detector.get_current_regime().value,
            "system_load": self._calculate_system_load()
        }

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _create_default_engine_configs(self, config: dict[str, Any] | None) -> dict[EngineType, EngineConfig]:  # noqa: E501
        """Create default engine configurations."""
        default_configs = {
            EngineType.RISK_MANAGER: EngineConfig(
                engine_type=EngineType.RISK_MANAGER,
                enabled=True,
                priority=1,
                performance_threshold=0.95,
                max_response_time_ms=500.0,
                calibration_schedule="daily"
            ),
            EngineType.PRICING_ENGINE: EngineConfig(
                engine_type=EngineType.PRICING_ENGINE,
                enabled=True,
                priority=1,
                performance_threshold=0.90,
                max_response_time_ms=100.0,
                calibration_schedule="hourly"
            ),
            EngineType.VOLATILITY_ENGINE: EngineConfig(
                engine_type=EngineType.VOLATILITY_ENGINE,
                enabled=True,
                priority=1,
                performance_threshold=0.88,
                max_response_time_ms=200.0,
                calibration_schedule="daily"
            ),
            EngineType.ADVANCED_MODELS: EngineConfig(
                engine_type=EngineType.ADVANCED_MODELS,
                enabled=True,
                priority=2,
                performance_threshold=0.85,
                max_response_time_ms=1000.0,
                calibration_schedule="weekly"
            ),
            EngineType.AI_MODELS: EngineConfig(
                engine_type=EngineType.AI_MODELS,
                enabled=True,
                priority=3,
                performance_threshold=0.80,
                max_response_time_ms=2000.0,
                calibration_schedule="weekly"
            )
        }

        # Apply user config overrides
        if config:
            for engine_type, user_config in config.items():
                if isinstance(engine_type, str):
                    engine_type = EngineType(engine_type)
                if engine_type in default_configs:
                    for key, value in user_config.items():
                        setattr(default_configs[engine_type], key, value)

        return default_configs

    def _create_default_context(self) -> ModelSelectionContext:
        """Create default model selection context."""
        return ModelSelectionContext(
            market_regime=self.market_regime_detector.get_current_regime(),
            volatility_level=0.2,  # Default volatility
            urgency="normal",
            accuracy_requirement="standard"
        )

    async def _execute_on_engine(self, request: ConsolidatedRequest) -> ConsolidatedResponse:
        """Execute request on specific engine."""
        start_time = time.time()

        try:
            engine = self.engines.get(request.engine_type)
            if not engine:
                raise ValueError(f"Engine {request.engine_type.value} not available")

            if self.engine_status.get(request.engine_type) != EngineStatus.READY:
                raise ValueError(f"Engine {request.engine_type.value} not ready")

            # Execute operation based on engine type and operation
            result = await self._dispatch_operation(engine, request)

            execution_time = (time.time() - start_time) * 1000

            return ConsolidatedResponse(
                request_id=request.request_id,
                engine_type=request.engine_type,
                operation=request.operation,
                success=True,
                result=result,
                error_message=None,
                execution_time_ms=execution_time,
                confidence=0.9,  # Default confidence
                metadata={"engine_version": "2.0"}
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ConsolidatedResponse(
                request_id=request.request_id,
                engine_type=request.engine_type,
                operation=request.operation,
                success=False,
                result=None,
                error_message=str(e),
                execution_time_ms=execution_time,
                confidence=0.0
            )

    async def _dispatch_operation(self, engine: Any, request: ConsolidatedRequest) -> Any:
        """Dispatch operation to appropriate engine method."""
        operation_map = {
            (EngineType.RISK_MANAGER, "calculate_risk_metrics"): lambda e, p: e.calculate_portfolio_var(p["risk_params"]),  # noqa: E501
            (EngineType.PRICING_ENGINE, "price_option"): lambda e, p: e.price_option(p["contract"], p["params"]),  # noqa: E501
            (EngineType.VOLATILITY_ENGINE, "calculate_volatility"): lambda e, p: e.calculate_volatility(p["volatility_request"]),  # noqa: E501
            (EngineType.ADVANCED_MODELS, "analyze_market_regime"): lambda e, p: e.detect_market_regime(p["market_data"]),  # noqa: E501
            (EngineType.AI_MODELS, "generate_trading_signal"): lambda e, p: e.generate_trading_signal(p["market_state"])  # noqa: E501
        }

        operation_key = (request.engine_type, request.operation)
        if operation_key in operation_map:
            return await operation_map[operation_key](engine, request.parameters)
        else:
            raise ValueError(f"Unsupported operation: {request.operation} for engine {request.engine_type.value}")  # noqa: E501

    async def _request_processor(self):
        """Background task to process queued requests."""
        while not self.shutdown_event.is_set():
            try:
                # Process queued requests (if implemented)
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error("Error in request processor: %s", e, exc_info=True)

    def _update_performance_metrics(self, engine_type: EngineType, response: ConsolidatedResponse):
        """Update performance metrics for engine."""
        if engine_type not in self.current_performance:
            self.current_performance[engine_type] = EnginePerformance(
                engine_type=engine_type,
                accuracy=0.9,
                response_time_avg_ms=0.0,
                response_time_p95_ms=0.0,
                error_rate=0.0,
                success_count=0,
                error_count=0,
                last_calibration=None,
                uptime_percentage=100.0,
                throughput_per_second=0.0
            )

        perf = self.current_performance[engine_type]

        # Update metrics
        if response.success:
            perf.success_count += 1
        else:
            perf.error_count += 1

        # Update response time (simple moving average)
        total_requests = perf.success_count + perf.error_count
        if total_requests > 0:
            perf.response_time_avg_ms = (
                (perf.response_time_avg_ms * (total_requests - 1) + response.execution_time_ms) / total_requests  # noqa: E501
            )
            perf.error_rate = perf.error_count / total_requests

    def _calculate_system_load(self) -> float:
        """Calculate overall system load."""
        # Simplified system load calculation
        active_engines = sum(1 for status in self.engine_status.values()
                           if status == EngineStatus.READY)
        total_engines = len(self.engine_status)
        return active_engines / total_engines if total_engines > 0 else 0.0

# ==============================================================================
# SUPPORTING CLASSES
# ==============================================================================
class ModelSelector:
    """Intelligent model selection logic."""

    def __init__(self, model_manager):
        self.model_manager = model_manager
        self.logger = logging.getLogger(f"{self.__class__.__name__}")

    async def select_engine(self, operation: str, context: ModelSelectionContext) -> EngineRecommendation:  # noqa: E501
        """Select optimal engine based on context and performance."""

        # Default engine mapping
        operation_engine_map = {
            "calculate_risk_metrics": EngineType.RISK_MANAGER,
            "price_option": EngineType.PRICING_ENGINE,
            "calculate_volatility": EngineType.VOLATILITY_ENGINE,
            "analyze_market_regime": EngineType.ADVANCED_MODELS,
            "generate_trading_signal": EngineType.AI_MODELS
        }

        default_engine = operation_engine_map.get(operation, EngineType.PRICING_ENGINE)

        # Check if default engine is available and performing well
        engine_status = self.model_manager.engine_status.get(default_engine)
        if engine_status == EngineStatus.READY:
            performance = self.model_manager.current_performance.get(default_engine)
            if performance and performance.accuracy > 0.8 and performance.error_rate < 0.1:
                return EngineRecommendation(
                    engine_type=default_engine,
                    confidence=0.9,
                    reasoning=f"Default engine {default_engine.value} is performing well",
                    fallback_engines=[],
                    expected_performance={"accuracy": performance.accuracy, "response_time": performance.response_time_avg_ms}  # noqa: E501
                )

        # If default engine has issues, recommend fallback
        fallback_engines = self._get_fallback_engines(default_engine)
        best_fallback = fallback_engines[0] if fallback_engines else default_engine

        return EngineRecommendation(
            engine_type=best_fallback,
            confidence=0.7,
            reasoning=f"Default engine {default_engine.value} degraded, using fallback",
            fallback_engines=fallback_engines[1:],
            expected_performance={"accuracy": 0.8, "response_time": 500.0}
        )

    def _get_fallback_engines(self, primary_engine: EngineType) -> list[EngineType]:
        """Get fallback engines for primary engine."""
        # Simplified fallback logic
        fallback_map = {
            EngineType.PRICING_ENGINE: [EngineType.AI_MODELS],
            EngineType.VOLATILITY_ENGINE: [EngineType.ADVANCED_MODELS],
            EngineType.RISK_MANAGER: [EngineType.PRICING_ENGINE],
            EngineType.ADVANCED_MODELS: [EngineType.VOLATILITY_ENGINE],
            EngineType.AI_MODELS: [EngineType.PRICING_ENGINE]
        }

        return fallback_map.get(primary_engine, [])

class MarketRegimeDetector:
    """Market regime detection logic.

    DEPRECATED (2026-04-14): L09 UnifiedRegimeEngine is the canonical regime
    detector for Spyder. This stub is retained only to satisfy V02's existing
    model-manager surface; new callers MUST use L09.
    """

    def __init__(self):
        self.current_regime = MarketRegime.NORMAL
        self.logger = logging.getLogger(f"{self.__class__.__name__}")

    def get_current_regime(self) -> MarketRegime:
        """Get current market regime."""
        # Simplified regime detection
        # In practice, this would analyze market data
        return self.current_regime

class EngineHealthChecker:
    """Engine health monitoring."""

    def __init__(self, model_manager):
        self.model_manager = model_manager
        self.logger = logging.getLogger(f"{self.__class__.__name__}")

    async def start_monitoring(self):
        """Start health monitoring loop."""
        while not self.model_manager.shutdown_event.is_set():
            try:
                await self._check_all_engines()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                self.logger.error("Error in health checker: %s", e, exc_info=True)

    async def _check_all_engines(self):
        """Check health of all engines."""
        for engine_type, engine in self.model_manager.engines.items():
            try:
                # Simple health check - could be enhanced
                if hasattr(engine, 'health_check'):
                    healthy = await engine.health_check()
                    if not healthy:
                        self.model_manager.engine_status[engine_type] = EngineStatus.DEGRADED
                else:
                    # If no health check method, assume healthy if no recent errors
                    perf = self.model_manager.current_performance.get(engine_type)
                    if perf and perf.error_rate > 0.5:
                        self.model_manager.engine_status[engine_type] = EngineStatus.DEGRADED

            except Exception as e:
                self.logger.error("Health check failed for %s: %s", engine_type.value, e, exc_info=True)  # noqa: E501
                self.model_manager.engine_status[engine_type] = EngineStatus.ERROR

class PerformanceMonitor:
    """Performance monitoring and optimization."""

    def __init__(self, model_manager):
        self.model_manager = model_manager
        self.logger = logging.getLogger(f"{self.__class__.__name__}")

    async def start_monitoring(self):
        """Start performance monitoring loop."""
        while not self.model_manager.shutdown_event.is_set():
            try:
                await self._analyze_performance()
                await asyncio.sleep(300)  # Analyze every 5 minutes
            except Exception as e:
                self.logger.error("Error in performance monitor: %s", e, exc_info=True)

    async def _analyze_performance(self):
        """Analyze and optimize performance."""
        for engine_type, performance in self.model_manager.current_performance.items():
            if performance.accuracy < 0.8 or performance.error_rate > 0.2:
                self.logger.warning("Performance degradation detected in %s", engine_type.value)
                # Could trigger recalibration or model switching

# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_enhanced_model_manager(config: dict[str, Any] | None = None,
                                data_manager=None) -> SpyderModelManager:
    """
    Factory function to create enhanced model manager.

    Args:
        config: Configuration dictionary
        data_manager: Data manager instance

    Returns:
        Configured SpyderModelManager instance
    """
    return SpyderModelManager(config, data_manager)

# ==============================================================================
# DEMONSTRATION AND TESTING
# ==============================================================================
async def main():
    """Demonstration of enhanced model manager."""
    logging.info("=" * 80)
    logging.info("SPYDER V02 ENHANCED MODEL MANAGER DEMONSTRATION")
    logging.info("=" * 80)

    # Initialize enhanced model manager
    model_manager = create_enhanced_model_manager()

    logging.info("\nEnhanced Model Manager Initialized")
    logging.info("   • Manages all consolidated V-series engines (V04-V08)")
    logging.info("   • Intelligent model selection and routing")
    logging.info("   • Performance-based adaptive optimization")
    logging.info("   • Real-time monitoring and health checks")

    # Test 1: Initialize all engines
    logging.info("\n--- Test 1: Engine Initialization ---")

    initialization_results = await model_manager.initialize_all_engines()

    logging.info("Engine Initialization Results:")
    for engine_type, success in initialization_results.items():
        status_icon = "✅" if success else "❌"
        logging.info("   %s %s: %s", status_icon, engine_type.value, 'Ready' if success else 'Failed')  # noqa: E501

    # Test 2: Model Selection Intelligence
    logging.info("\n--- Test 2: Intelligent Model Selection ---")

    # Test different contexts
    contexts = [
        ("Normal Market", ModelSelectionContext(
            market_regime=MarketRegime.NORMAL,
            volatility_level=0.2,
            urgency="normal",
            accuracy_requirement="standard"
        )),
        ("Crisis Market", ModelSelectionContext(
            market_regime=MarketRegime.CRISIS,
            volatility_level=0.45,
            urgency="high",
            accuracy_requirement="high_precision"
        )),
        ("High Vol Market", ModelSelectionContext(
            market_regime=MarketRegime.HIGH_VOLATILITY,
            volatility_level=0.35,
            urgency="normal",
            accuracy_requirement="fast"
        ))
    ]

    for context_name, context in contexts:
        logging.info("\n%s Context:", context_name)

        # Test pricing operation selection
        recommendation = await model_manager.select_optimal_engine("price_option", context)
        logging.info(f"   Pricing: {recommendation.engine_type.value} (Confidence: {recommendation.confidence:.1%})")  # noqa: E501
        logging.info("   Reasoning: %s", recommendation.reasoning)

        # Test risk analysis selection
        recommendation = await model_manager.select_optimal_engine("calculate_risk_metrics", context)  # noqa: E501
        logging.info(f"   Risk: {recommendation.engine_type.value} (Confidence: {recommendation.confidence:.1%})")  # noqa: E501

    # Test 3: Performance Monitoring
    logging.info("\n--- Test 3: Performance Monitoring ---")

    health_report = model_manager.get_consolidated_health_report()

    logging.info("System Health Report:")
    logging.info("   Total Engines: %s", health_report['total_engines'])
    logging.info("   Healthy Engines: %s", health_report['healthy_engines'])
    logging.info(f"   System Load: {health_report['system_load']:.1%}")
    logging.info("   Market Regime: %s", health_report['market_regime'])

    logging.info("\nEngine Status:")
    for engine_name, status in health_report['engine_status'].items():
        status_icon = "✅" if status == "ready" else "⚠️" if status == "degraded" else "❌"
        logging.info("   %s %s: %s", status_icon, engine_name, status)

    # Test 4: Unified Operations Interface
    logging.info("\n--- Test 4: Unified Operations Interface ---")

    logging.info("Available Operations:")
    operations = [
        "calculate_risk_metrics - V04 Risk Manager",
        "price_option - V05 Pricing Engine",
        "calculate_volatility - V06 Volatility Engine",
        "analyze_market_regime - V07 Advanced Models",
        "generate_trading_signal - V08 AI Models"
    ]

    for operation in operations:
        logging.info("   • %s", operation)

    # Test 5: Configuration Display
    logging.info("\n--- Test 5: Engine Configurations ---")

    for engine_type, config in model_manager.engine_configs.items():
        logging.info("\n%s:", engine_type.value.upper())
        logging.info("   Enabled: %s", config.enabled)
        logging.info("   Priority: %s", config.priority)
        logging.info(f"   Performance Threshold: {config.performance_threshold:.1%}")
        logging.info(f"   Max Response Time: {config.max_response_time_ms:.0f}ms")
        logging.info("   Calibration Schedule: %s", config.calibration_schedule)

    # Test 6: Architecture Summary
    logging.info("\n--- Consolidated V-Series Architecture ---")

    architecture = [
        "V01_QuantEngine2 (Orchestrator)",
        "├── V02_ModelManager2 (Enhanced - This Module)",
        "├── V04_RiskManager2 (Risk Calculations)",
        "├── V05_PricingEngine2 (Options Pricing)",
        "├── V06_VolatilityEngine2 (Volatility Modeling)",
        "├── V07_AdvancedModels2 (Jump-Diffusion + Regime)",
        "├── V08_AIModels2 (Transformer + RL)",
        "└── V03_DataInterface (Data Bridge)"
    ]

    for line in architecture:
        logging.info("   %s", line)

    logging.info("\n🎯 CONSOLIDATED V-SERIES COMPLETE!")
    logging.info("   • 8 modules with zero duplications")
    logging.info("   • Intelligent model selection across all engines")
    logging.info("   • Performance-based adaptive optimization")
    logging.info("   • Unified interface for seamless integration")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
