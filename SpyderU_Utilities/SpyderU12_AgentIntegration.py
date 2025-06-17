#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU12_AgentIntegration.py
Group: U (Utilities)
Purpose: AI Agent Integration and Management

Description:
    This module handles the integration of AI agents with the existing Spyder system.
    It provides agent lifecycle management, event routing between agents and traditional
    modules, configuration management for AI components, and performance monitoring.
    The module serves as the central hub for all AI agent operations within Spyder.

Author: Mohamed Talib
Spyder Version: 1.0
Last Updated: 2025-01-27 Time: 14:45
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event
from SpyderA_Core.SpyderA03_Configuration import Configuration

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_MAX_WORKERS = 4
AGENT_HEARTBEAT_INTERVAL = 60  # seconds
DEFAULT_AGENT_TIMEOUT = 30  # seconds
AI_AGENTS_GROUP = "SpyderX_Agents"

# ==============================================================================
# ENUMS
# ==============================================================================
class AgentStatus(Enum):
    """AI Agent status enumeration"""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class IntegrationMode(Enum):
    """Integration mode for AI agents"""
    AUGMENT = "augment"  # AI enhances existing modules
    REPLACE = "replace"  # AI replaces module functionality
    HYBRID = "hybrid"    # Mixed approach

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class AgentConfig:
    """Configuration for an AI agent"""
    name: str
    module_name: str
    factory_function: str
    enabled: bool = True
    integration_mode: IntegrationMode = IntegrationMode.AUGMENT
    config: Dict[str, Any] = None
    augments_modules: List[str] = None  # List of modules this agent enhances
    
    def __post_init__(self):
        if self.augments_modules is None:
            self.augments_modules = []
        if self.config is None:
            self.config = {}
    
    
@dataclass
class AgentMetrics:
    """Performance metrics for an AI agent"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_processing_time: float = 0.0
    last_call_time: Optional[datetime] = None
    average_latency_ms: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    @property
    def average_processing_time(self) -> float:
        """Calculate average processing time"""
        if self.successful_calls == 0:
            return 0.0
        return self.total_processing_time / self.successful_calls


@dataclass
class AgentResponse:
    """Standardized response from AI agents"""
    agent_name: str
    request_id: str
    status: str  # 'success', 'error', 'timeout'
    data: Dict[str, Any]
    processing_time_ms: float
    timestamp: datetime

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class AIAgentManager:
    """
    Central manager for all AI agents in Spyder.
    
    This class handles agent lifecycle, routing, and integration with
    the existing Spyder system. It provides a unified interface for
    all AI agent operations.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_manager: Spyder event manager
        config: System configuration
        agents: Dictionary of active agents
        agent_configs: Agent configuration data
        agent_metrics: Performance metrics for each agent
        
    Example:
        >>> manager = AIAgentManager(event_manager, config)
        >>> manager.initialize()
        >>> manager.start()
    """
    
    def __init__(self, event_manager: EventManager, config: Configuration):
        """Initialize the AI Agent Manager."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = event_manager
        self.config = config
        
        # Agent registry
        self.agents: Dict[str, Any] = {}
        self.agent_configs: Dict[str, AgentConfig] = {}
        self.agent_status: Dict[str, AgentStatus] = {}
        self.agent_metrics: Dict[str, AgentMetrics] = {}
        
        # Async execution
        self.loop = None
        self.executor = ThreadPoolExecutor(max_workers=DEFAULT_MAX_WORKERS)
        
        # Control flags
        self.is_running = False
        self._stop_event = None
        
        # Request tracking
        self._request_counter = 0
        self._pending_requests: Dict[str, datetime] = {}
        
        self.logger.info(f"{self.__class__.__name__} initialized")
        
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize module components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Create event loop
            self.loop = asyncio.new_event_loop()
            self._stop_event = asyncio.Event()
            
            # Load agent configurations
            self._load_agent_configs()
            
            # Initialize enabled agents
            self._initialize_agents()
            
            # Setup event subscriptions
            self._setup_event_subscriptions()
            
            self.logger.info("AI Agent Manager initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False
            
    def start(self) -> bool:
        """
        Start the AI agent manager.
        
        Returns:
            bool: True if started successfully
        """
        try:
            self.logger.info("Starting AI Agent Manager...")
            
            if self.is_running:
                self.logger.warning("AI Agent Manager already running")
                return False
            
            self.is_running = True
            
            # Start async event loop in separate thread
            self.executor.submit(self._run_event_loop)
            
            # Start heartbeat monitoring
            self._start_heartbeat()
            
            # Start all agents
            for name, agent in self.agents.items():
                if hasattr(agent, 'start'):
                    agent.start()
                self.agent_status[name] = AgentStatus.READY
            
            self.logger.info("AI Agent Manager started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start AI Agent Manager: {e}")
            self.is_running = False
            return False
    
    def stop(self) -> bool:
        """
        Stop the AI agent manager.
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            self.logger.info("Stopping AI Agent Manager...")
            
            if not self.is_running:
                self.logger.warning("AI Agent Manager not running")
                return False
            
            self.is_running = False
            
            # Signal stop
            if self.loop and self._stop_event:
                self.loop.call_soon_threadsafe(self._stop_event.set)
            
            # Stop all agents
            for name, agent in self.agents.items():
                if hasattr(agent, 'stop'):
                    agent.stop()
                self.agent_status[name] = AgentStatus.SHUTDOWN
            
            # Stop event loop
            if self.loop:
                self.loop.call_soon_threadsafe(self.loop.stop)
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            self.logger.info("AI Agent Manager stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping AI Agent Manager: {e}")
            return False
            
    def cleanup(self) -> None:
        """Clean up module resources."""
        # Clean up agents
        for name, agent in self.agents.items():
            if hasattr(agent, 'cleanup'):
                agent.cleanup()
                
        self.logger.info("AI Agent Manager cleanup completed")
    
    def get_agent(self, name: str) -> Optional[Any]:
        """
        Get a specific agent by name.
        
        Args:
            name: Agent name
            
        Returns:
            Agent instance or None
        """
        return self.agents.get(name)
        
    def get_agent_status(self, agent_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status of agents.
        
        Args:
            agent_name: Specific agent name or None for all agents
            
        Returns:
            Status information
        """
        if agent_name:
            return self._get_single_agent_status(agent_name)
        
        # Return all agent statuses
        status = {
            'manager_running': self.is_running,
            'total_agents': len(self.agents),
            'active_agents': sum(1 for s in self.agent_status.values() if s == AgentStatus.READY),
            'agents': {}
        }
        
        for name in self.agents:
            status['agents'][name] = self._get_single_agent_status(name)
            
        return status
    
    async def process_request(
        self, 
        agent_name: str, 
        request_type: str, 
        data: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> AgentResponse:
        """
        Process a request for a specific agent.
        
        Args:
            agent_name: Name of the agent
            request_type: Type of request
            data: Request data
            timeout: Request timeout in seconds
            
        Returns:
            AgentResponse with results
        """
        request_id = self._generate_request_id()
        start_time = datetime.now()
        
        if agent_name not in self.agents:
            self.logger.error(f"Agent {agent_name} not found")
            return AgentResponse(
                agent_name=agent_name,
                request_id=request_id,
                status='error',
                data={'error': f'Agent {agent_name} not found'},
                processing_time_ms=0,
                timestamp=datetime.now()
            )
            
        try:
            # Track request
            self._pending_requests[request_id] = start_time
            
            # Update metrics
            self.agent_metrics[agent_name].total_calls += 1
            self.agent_status[agent_name] = AgentStatus.BUSY
            
            # Get agent
            agent = self.agents[agent_name]
            
            # Process based on agent type
            if agent_name == 'greeks_agent':
                result = await self._process_greeks_request(agent, request_type, data)
            else:
                # Generic processing for other agents
                result = await self._process_generic_request(agent, request_type, data)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Update metrics
            self.agent_metrics[agent_name].successful_calls += 1
            self.agent_metrics[agent_name].total_processing_time += processing_time / 1000
            self.agent_metrics[agent_name].last_call_time = datetime.now()
            
            return AgentResponse(
                agent_name=agent_name,
                request_id=request_id,
                status='success',
                data=result,
                processing_time_ms=processing_time,
                timestamp=datetime.now()
            )
            
        except asyncio.TimeoutError:
            self.agent_metrics[agent_name].failed_calls += 1
            return AgentResponse(
                agent_name=agent_name,
                request_id=request_id,
                status='timeout',
                data={'error': 'Request timeout'},
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.agent_metrics[agent_name].failed_calls += 1
            self.logger.error(f"Error processing request: {e}")
            return AgentResponse(
                agent_name=agent_name,
                request_id=request_id,
                status='error',
                data={'error': str(e)},
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                timestamp=datetime.now()
            )
            
        finally:
            self.agent_status[agent_name] = AgentStatus.READY
            self._pending_requests.pop(request_id, None)
            
    # ==========================================================================
    # PRIVATE METHODS - INITIALIZATION
    # ==========================================================================
    def _load_agent_configs(self):
        """Load agent configurations."""
        # Define available agents
        self.agent_configs = {
            "greeks_agent": AgentConfig(
                name="greeks_agent",
                module_name="SpyderX01_GreeksAgent",
                factory_function="create_greeks_agent",
                enabled=self.config.get('ai_agents', {}).get('greeks_agent', {}).get('enabled', True),
                integration_mode=IntegrationMode.AUGMENT,
                config={
                    'risk_free_rate': self.config.get('risk_free_rate', 0.05),
                    'llm_model': self.config.get('llm_model', 'llama3.2:3b-instruct-q4_K_M'),
                    'greek_limits': self.config.get('greek_limits', {
                        'delta': 100,
                        'gamma': 50,
                        'vega': 200,
                        'theta': -300
                    })
                },
                augments_modules=[
                    'SpyderF06_GreeksCalculator',
                    'SpyderE06_GreeksManager'
                ]
            ),
            # Future agents will be added here:
            # "flow_agent": AgentConfig(
            #     name="flow_agent",
            #     module_name="SpyderX02_FlowAgent",
            #     factory_function="create_flow_agent",
            #     augments_modules=['SpyderM01_OrderFlow']
            # ),
            # "strategy_agent": AgentConfig(
            #     name="strategy_agent",
            #     module_name="SpyderX03_StrategyAgent",
            #     factory_function="create_strategy_agent",
            #     augments_modules=['SpyderD08_StrategyManager']
            # ),
            # "risk_agent": AgentConfig(
            #     name="risk_agent",
            #     module_name="SpyderX04_RiskAgent",
            #     factory_function="create_risk_agent",
            #     augments_modules=['SpyderE01_RiskManager']
            # ),
        }
        
    def _initialize_agents(self):
        """Initialize all configured AI agents."""
        for agent_name, agent_config in self.agent_configs.items():
            if agent_config.enabled:
                try:
                    self._create_agent(agent_config)
                    self.logger.info(f"Initialized AI agent: {agent_config.name}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize agent {agent_config.name}: {e}")
                    
    def _create_agent(self, agent_config: AgentConfig):
        """Create and register an AI agent."""
        try:
            # Update status
            self.agent_status[agent_config.name] = AgentStatus.INITIALIZING
            
            # Dynamic import
            module_path = f"{AI_AGENTS_GROUP}.{agent_config.module_name}"
            module = __import__(module_path, fromlist=[agent_config.factory_function])
            factory = getattr(module, agent_config.factory_function)
            
            # Create agent
            agent = factory(agent_config.config)
            
            # Initialize agent with event manager
            if hasattr(agent, 'initialize'):
                agent.initialize(self.event_manager)
            
            # Register
            self.agents[agent_config.name] = agent
            self.agent_metrics[agent_config.name] = AgentMetrics()
            self.agent_status[agent_config.name] = AgentStatus.READY
            
        except Exception as e:
            self.logger.error(f"Error creating agent {agent_config.name}: {e}")
            self.agent_status[agent_config.name] = AgentStatus.ERROR
            raise
            
    def _setup_event_subscriptions(self):
        """Subscribe to events that trigger AI agents."""
        # Greeks calculation requests
        self.event_manager.subscribe('ai_calculate_greeks', self._handle_greeks_request)
        
        # Position analysis requests
        self.event_manager.subscribe('ai_analyze_position', self._handle_position_analysis)
        
        # Market data updates (for context)
        self.event_manager.subscribe('market_data_update', self._handle_market_update)
        
        # Strategy signals (future integration)
        self.event_manager.subscribe('strategy_signal', self._handle_strategy_signal)
        
        self.logger.debug("AI Agent event subscriptions completed")
        
    # ==========================================================================
    # PRIVATE METHODS - EVENT HANDLERS
    # ==========================================================================
    def _handle_greeks_request(self, event: Event):
        """Handle Greeks calculation request."""
        asyncio.run_coroutine_threadsafe(
            self._async_greeks_calculation(event),
            self.loop
        )
        
    def _handle_position_analysis(self, event: Event):
        """Handle position analysis request."""
        asyncio.run_coroutine_threadsafe(
            self._async_position_analysis(event),
            self.loop
        )
        
    def _handle_market_update(self, event: Event):
        """Store market context for agents."""
        # This could be used to maintain market state for agents
        self.logger.debug(f"Market update received: {event.data.get('symbol', 'Unknown')}")
        
    def _handle_strategy_signal(self, event: Event):
        """Handle strategy signals (future integration)."""
        self.logger.debug(f"Strategy signal received: {event.data.get('signal_type', 'Unknown')}")
        
    async def _async_greeks_calculation(self, event: Event):
        """Async Greeks calculation handler."""
        agent_name = 'greeks_agent'
        
        try:
            # Extract data
            contracts = event.data.get('contracts', [])
            market_context = event.data.get('market_context', {})
            
            # Process request
            response = await self.process_request(
                agent_name,
                'calculate_greeks',
                {
                    'contracts': contracts,
                    'market_context': market_context
                }
            )
            
            # Emit results
            if response.status == 'success':
                self.event_manager.emit(Event(
                    type='ai_greeks_calculated',
                    data=response.data
                ))
            else:
                self.event_manager.emit(Event(
                    type='ai_greeks_error',
                    data={'error': response.data.get('error', 'Unknown error')}
                ))
                
        except Exception as e:
            self.logger.error(f"Error in async Greeks calculation: {e}")
            self.event_manager.emit(Event(
                type='ai_greeks_error',
                data={'error': str(e)}
            ))
            
    async def _async_position_analysis(self, event: Event):
        """Async position analysis handler."""
        analysis_type = event.data.get('analysis_type', 'greeks')
        
        if analysis_type == 'greeks':
            await self._async_greeks_calculation(event)
        # Future analysis types will be added here
        
    # ==========================================================================
    # PRIVATE METHODS - REQUEST PROCESSING
    # ==========================================================================
    async def _process_greeks_request(
        self, 
        agent: Any, 
        request_type: str, 
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process Greeks-specific requests."""
        if request_type == 'calculate_greeks':
            contracts = data.get('contracts', [])
            market_context = data.get('market_context', {})
            
            # Convert contracts if needed
            from SpyderX_Agents.SpyderX01_GreeksAgent import OptionContract
            
            option_contracts = []
            for c in contracts:
                if isinstance(c, dict):
                    option_contracts.append(OptionContract(
                        symbol=c['symbol'],
                        strike=c['strike'],
                        expiry=datetime.fromisoformat(c['expiry']),
                        option_type=c['option_type'],
                        underlying_price=c['underlying_price'],
                        market_price=c.get('market_price'),
                        bid=c.get('bid'),
                        ask=c.get('ask'),
                        volume=c.get('volume'),
                        open_interest=c.get('open_interest')
                    ))
                else:
                    option_contracts.append(c)
                    
            return await agent.analyze_position(option_contracts, market_context)
            
        else:
            raise ValueError(f"Unknown request type for Greeks agent: {request_type}")
            
    async def _process_generic_request(
        self, 
        agent: Any, 
        request_type: str, 
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process generic agent requests."""
        # Check if agent has the requested method
        method_name = f"process_{request_type}"
        if hasattr(agent, method_name):
            method = getattr(agent, method_name)
            if asyncio.iscoroutinefunction(method):
                return await method(data)
            else:
                return method(data)
        else:
            raise ValueError(f"Agent does not support request type: {request_type}")
            
    # ==========================================================================
    # PRIVATE METHODS - MONITORING
    # ==========================================================================
    def _run_event_loop(self):
        """Run the async event loop."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        
    def _start_heartbeat(self):
        """Start heartbeat monitoring."""
        async def heartbeat():
            while not self._stop_event.is_set():
                self._check_agent_health()
                await asyncio.sleep(AGENT_HEARTBEAT_INTERVAL)
                
        asyncio.run_coroutine_threadsafe(heartbeat(), self.loop)
        
    def _check_agent_health(self):
        """Check health of all agents."""
        for name, agent in self.agents.items():
            try:
                if hasattr(agent, 'get_performance_metrics'):
                    metrics = agent.get_performance_metrics()
                    self.logger.debug(f"Agent {name} health check: {metrics}")
                    
                    # Update latency metric
                    if 'last_analysis_time_ms' in metrics:
                        self.agent_metrics[name].average_latency_ms = metrics['last_analysis_time_ms']
                        
            except Exception as e:
                self.logger.error(f"Health check failed for {name}: {e}")
                self.agent_status[name] = AgentStatus.ERROR
                
    def _get_single_agent_status(self, agent_name: str) -> Dict[str, Any]:
        """Get status for a single agent."""
        if agent_name not in self.agents:
            return {'error': f'Agent {agent_name} not found'}
            
        config = self.agent_configs[agent_name]
        metrics = self.agent_metrics[agent_name]
        status = self.agent_status[agent_name]
        
        # Get agent-specific metrics if available
        agent_metrics = {}
        agent = self.agents.get(agent_name)
        if agent and hasattr(agent, 'get_performance_metrics'):
            try:
                agent_metrics = agent.get_performance_metrics()
            except:
                pass
                
        return {
            'name': agent_name,
            'status': status.value,
            'enabled': config.enabled,
            'integration_mode': config.integration_mode.value,
            'augments_modules': config.augments_modules,
            'metrics': {
                'total_calls': metrics.total_calls,
                'successful_calls': metrics.successful_calls,
                'failed_calls': metrics.failed_calls,
                'success_rate': f"{metrics.success_rate:.1%}",
                'avg_processing_time': f"{metrics.average_processing_time:.3f}s",
                'avg_latency_ms': f"{metrics.average_latency_ms:.1f}",
                'last_call': metrics.last_call_time.isoformat() if metrics.last_call_time else None
            },
            'agent_specific_metrics': agent_metrics,
            'config': config.config
        }
        
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        self._request_counter += 1
        return f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._request_counter}"
        
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start the module."""
        if not self.is_running:
            self.start()
            
    def stop(self) -> None:
        """Stop the module."""
        if self.is_running:
            self.stop()

# ==============================================================================
# INTEGRATION HELPER CLASSES
# ==============================================================================
class GreeksIntegration:
    """
    Helper class to integrate Greeks Agent with existing modules.
    
    Provides backward compatibility and simplified interface for
    modules that need Greeks calculations.
    """
    
    def __init__(self, agent_manager: AIAgentManager):
        """Initialize Greeks integration helper."""
        self.agent_manager = agent_manager
        self.logger = SpyderLogger(__name__)
        
    def calculate_greeks_legacy(self, contracts: List[Dict]) -> Dict[str, Any]:
        """
        Legacy interface for Greeks calculation.
        
        Maintains compatibility with existing code that expects
        synchronous Greeks calculations.
        
        Args:
            contracts: List of contract dictionaries
            
        Returns:
            Dict with status and results
        """
        try:
            # Run async method in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                self.agent_manager.process_request(
                    'greeks_agent',
                    'calculate_greeks',
                    {
                        'contracts': contracts,
                        'market_context': self._get_current_market_context()
                    }
                )
            )
            
            if result.status == 'success':
                return {
                    'status': 'success',
                    'data': result.data,
                    'processing_time_ms': result.processing_time_ms
                }
            else:
                return {
                    'status': 'error',
                    'error': result.data.get('error', 'Unknown error')
                }
                
        except Exception as e:
            self.logger.error(f"Legacy Greeks calculation error: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    def _get_current_market_context(self) -> Dict[str, Any]:
        """Get current market context for Greeks calculation."""
        # This would integrate with market data modules
        # For now, return mock data
        return {
            'vix': 15.0,
            'trend': 'neutral',
            'volume': 'average',
            'regime': 'normal',
            'timestamp': datetime.now().isoformat()
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_ai_agent_manager(event_manager: EventManager, config: Configuration) -> AIAgentManager:
    """
    Factory function to create AI Agent Manager.
    
    Args:
        event_manager: Spyder event manager
        config: System configuration
        
    Returns:
        Configured AIAgentManager instance
    """
    manager = AIAgentManager(event_manager, config)
    manager.initialize()
    return manager

def integrate_greeks_agent(agent_manager: AIAgentManager) -> GreeksIntegration:
    """
    Create Greeks integration helper.
    
    Args:
        agent_manager: AI Agent Manager instance
        
    Returns:
        GreeksIntegration helper
    """
    return GreeksIntegration(agent_manager)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_module_instance: Optional[AIAgentManager] = None

def get_module_instance(event_manager: Optional[EventManager] = None, 
                       config: Optional[Configuration] = None) -> AIAgentManager:
    """
    Get singleton instance of the module.
    
    Args:
        event_manager: Event manager if creating new instance
        config: Configuration if creating new instance
        
    Returns:
        Module instance
    """
    global _module_instance
    if _module_instance is None and event_manager and config:
        _module_instance = AIAgentManager(event_manager, config)
    return _module_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("Testing SpyderU12_AgentIntegration module...")
    print("=" * 60)
    
    # Create mock dependencies
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from SpyderA_Core.SpyderA03_Configuration import Configuration
    
    # Create event manager
    event_manager = EventManager()
    
    # Create configuration
    config = Configuration({
        'risk_free_rate': 0.05,
        'llm_model': 'llama3.2:3b-instruct-q4_K_M',
        'ai_agents': {
            'greeks_agent': {
                'enabled': True
            }
        },
        'greek_limits': {
            'delta': 100,
            'gamma': 50,
            'vega': 200,
            'theta': -300
        }
    })
    
    # Create AI agent manager
    print("\n1. Creating AI Agent Manager...")
    ai_manager = AIAgentManager(event_manager, config)
    
    if ai_manager.initialize():
        print("✅ AI Agent Manager initialized successfully")
        
        # Start the manager
        print("\n2. Starting AI Agent Manager...")
        if ai_manager.start():
            print("✅ AI Agent Manager started successfully")
        else:
            print("❌ Failed to start AI Agent Manager")
            
        # Get status
        print("\n3. Getting agent status...")
        status = ai_manager.get_agent_status()
        print(f"Manager running: {status['manager_running']}")
        print(f"Total agents: {status['total_agents']}")
        print(f"Active agents: {status['active_agents']}")
        
        for agent_name, agent_status in status['agents'].items():
            print(f"\n{agent_name}:")
            print(f"  Status: {agent_status['status']}")
            print(f"  Integration Mode: {agent_status['integration_mode']}")
            print(f"  Augments: {', '.join(agent_status['augments_modules'])}")
            
        # Test legacy integration
        print("\n4. Testing legacy integration...")
        greeks_integration = integrate_greeks_agent(ai_manager)
        
        test_contracts = [
            {
                'symbol': 'SPY_240201C550',
                'strike': 550.0,
                'expiry': (datetime.now() + timedelta(days=10)).isoformat(),
                'option_type': 'call',
                'underlying_price': 548.50,
                'market_price': 5.25
            }
        ]
        
        result = greeks_integration.calculate_greeks_legacy(test_contracts)
        print(f"Legacy result: {result['status']}")
        if result['status'] == 'success':
            print(f"Processing time: {result.get('processing_time_ms', 0):.1f}ms")
            
        # Give async operations time to complete
        import time
        time.sleep(2)
        
        # Stop manager
        print("\n5. Stopping AI Agent Manager...")
        if ai_manager.stop():
            print("✅ AI Agent Manager stopped successfully")
        else:
            print("❌ Failed to stop AI Agent Manager")
            
        # Cleanup
        ai_manager.cleanup()
        print("✅ Module test completed")
    else:
        print("❌ Module initialization failed")