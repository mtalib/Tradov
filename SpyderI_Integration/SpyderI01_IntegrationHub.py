#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderI01_IntegrationHub.py
Group: I (Integration)
Purpose: Central integration coordinator for all SPYDER modules

Description:
    The Integration Hub serves as the central coordinator for all module
    integrations within the SPYDER ecosystem. It manages module discovery,
    registration, health monitoring, and communication routing between
    components. Features include automatic module detection, dependency
    resolution, real-time health monitoring, configuration synchronization,
    and intelligent routing of events and data between modules.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-01
Last Updated: 2025-07-01 Time: 16:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import threading
import time
import inspect
import importlib
import pkgutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, deque
import json
import uuid
import weakref
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import networkx as nx
from networkx.algorithms import dag

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Module discovery patterns
SPYDER_MODULE_PATTERN = r"Spyder[A-Z]\d+_.*\.py"
MODULE_GROUPS = {
    'A': 'Core', 'B': 'Broker', 'C': 'MarketData', 'D': 'Strategies',
    'E': 'Risk', 'F': 'Analysis', 'G': 'GUI', 'H': 'Storage',
    'I': 'Integration', 'J': 'Alerts', 'K': 'Reports', 'L': 'ML',
    'M': 'Monitoring', 'N': 'OptionsAnalytics', 'O': 'RiskControl',
    'P': 'Portfolio', 'R': 'Runtime', 'T': 'ThirdParty', 'U': 'Utilities',
    'X': 'Agents', 'Z': 'Communication'
}

# Health check intervals
HEALTH_CHECK_INTERVAL = 30  # seconds
DEPENDENCY_CHECK_INTERVAL = 60  # seconds
MODULE_DISCOVERY_INTERVAL = 300  # 5 minutes

# Module states
class ModuleState(Enum):
    """Module operational states."""
    UNKNOWN = "unknown"
    DISCOVERED = "discovered"
    LOADING = "loading"
    LOADED = "loaded"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"
    UNLOADING = "unloading"

class IntegrationLevel(Enum):
    """Levels of module integration."""
    STANDALONE = "standalone"  # No dependencies
    BASIC = "basic"            # Basic imports only
    INTEGRATED = "integrated"  # Uses other modules
    ADVANCED = "advanced"      # Complex integrations
    ECOSYSTEM = "ecosystem"    # Deeply integrated

class HealthStatus(Enum):
    """Module health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ModuleInfo:
    """Information about a SPYDER module."""
    module_id: str
    module_name: str
    group: str
    group_name: str
    file_path: str
    class_name: Optional[str] = None
    version: str = "1.0"
    description: str = ""
    state: ModuleState = ModuleState.DISCOVERED
    health: HealthStatus = HealthStatus.UNKNOWN
    integration_level: IntegrationLevel = IntegrationLevel.STANDALONE
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    capabilities: List[str] = field(default_factory=list)
    last_health_check: Optional[datetime] = None
    error_count: int = 0
    load_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class IntegrationMapping:
    """Mapping between modules for integration."""
    source_module: str
    target_module: str
    integration_type: str  # 'import', 'event', 'data', 'api'
    method: str  # How they integrate
    strength: float  # Integration strength (0.0 to 1.0)
    bidirectional: bool = False
    required: bool = False
    active: bool = True

@dataclass
class HealthReport:
    """Health report for a module."""
    module_id: str
    status: HealthStatus
    timestamp: datetime
    response_time: float
    memory_usage: float
    error_rate: float
    dependencies_healthy: bool
    issues: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# INTEGRATION HUB CLASS
# ==============================================================================
class IntegrationHub:
    """
    Central integration coordinator for all SPYDER modules.
    
    The Integration Hub manages the entire SPYDER ecosystem by:
    - Discovering and cataloging all modules
    - Tracking dependencies and relationships
    - Monitoring health and performance
    - Coordinating module communications
    - Managing configuration synchronization
    - Providing centralized diagnostics
    
    Features:
    - Automatic module discovery and registration
    - Dependency graph management and resolution
    - Real-time health monitoring and alerting
    - Dynamic module loading and unloading
    - Configuration propagation and synchronization
    - Integration performance optimization
    - Comprehensive diagnostics and reporting
    
    Attributes:
        modules: Registry of all discovered modules
        dependency_graph: Graph of module dependencies
        health_reports: Latest health reports for all modules
        integration_mappings: How modules integrate with each other
        active_instances: Currently active module instances
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the Integration Hub."""
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        
        # Configuration
        self.config = config or {}
        self.auto_discovery = self.config.get('auto_discovery', True)
        self.health_monitoring = self.config.get('health_monitoring', True)
        self.dependency_resolution = self.config.get('dependency_resolution', True)
        
        # Module registry
        self.modules: Dict[str, ModuleInfo] = {}
        self.active_instances: Dict[str, Any] = {}
        self.module_factories: Dict[str, Callable] = {}
        
        # Dependency management
        self.dependency_graph = nx.DiGraph()
        self.integration_mappings: List[IntegrationMapping] = []
        self.load_order: List[str] = []
        
        # Health monitoring
        self.health_reports: Dict[str, HealthReport] = {}
        self.health_history: deque = deque(maxlen=1000)
        self.performance_metrics: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Threading
        self._stop_event = threading.Event()
        self._discovery_thread = None
        self._health_thread = None
        self._dependency_thread = None
        
        # Statistics
        self.stats = {
            'modules_discovered': 0,
            'modules_loaded': 0,
            'integrations_active': 0,
            'health_checks_performed': 0,
            'dependency_resolutions': 0,
            'errors_handled': 0
        }
        
        # Initialize
        self._initialize_hub()
        
        self.logger.info("🔗 Integration Hub initialized - SPYDER ecosystem coordination active")
    
    # ==========================================================================
    # INITIALIZATION AND STARTUP
    # ==========================================================================
    def _initialize_hub(self) -> None:
        """Initialize the integration hub."""
        try:
            # Discover existing modules
            if self.auto_discovery:
                self.discover_modules()
            
            # Build dependency graph
            if self.dependency_resolution:
                self._build_dependency_graph()
            
            # Start monitoring threads
            self._start_monitoring()
            
            # Register for events
            self._register_event_handlers()
            
            self.logger.info("✅ Integration Hub fully initialized")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_initialize_hub'
            })
    
    def discover_modules(self, scan_paths: List[str] = None) -> None:
        """
        Discover all SPYDER modules in the ecosystem.
        
        Args:
            scan_paths: Paths to scan for modules (optional)
        """
        try:
            if scan_paths is None:
                # Default scan paths
                scan_paths = [
                    'SpyderA_Core', 'SpyderB_Broker', 'SpyderC_MarketData',
                    'SpyderD_Strategies', 'SpyderE_Risk', 'SpyderF_Analysis',
                    'SpyderG_GUI', 'SpyderH_Storage', 'SpyderI_Integration',
                    'SpyderJ_Alerts', 'SpyderK_Reports', 'SpyderL_ML',
                    'SpyderM_Monitoring', 'SpyderN_OptionsAnalytics',
                    'SpyderE_Risk', 'SpyderP_Portfolio', 'SpyderR_Runtime',
                    'SpyderT_ThirdParty', 'SpyderU_Utilities', 'SpyderX_Agents',
                    'SpyderZ_Communication'
                ]
            
            discovered_count = 0
            
            for scan_path in scan_paths:
                try:
                    modules_found = self._scan_module_group(scan_path)
                    discovered_count += modules_found
                    
                except ImportError:
                    self.logger.debug(f"Module group {scan_path} not found")
                except Exception as e:
                    self.logger.warning(f"Error scanning {scan_path}: {e}")
            
            self.stats['modules_discovered'] = len(self.modules)
            
            self.logger.info(f"📦 Discovered {discovered_count} new modules ({len(self.modules)} total)")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'discover_modules'
            })
    
    def _scan_module_group(self, group_path: str) -> int:
        """Scan a specific module group for SPYDER modules."""
        modules_found = 0
        
        try:
            # Import the package
            package = importlib.import_module(group_path)
            
            # Scan for modules in the package
            for importer, module_name, ispkg in pkgutil.iter_modules(
                package.__path__, package.__name__ + "."
            ):
                if not ispkg and self._is_spyder_module(module_name):
                    module_info = self._analyze_module(module_name, group_path)
                    if module_info:
                        self.modules[module_info.module_id] = module_info
                        modules_found += 1
                        
        except Exception as e:
            self.logger.debug(f"Could not scan {group_path}: {e}")
        
        return modules_found
    
    def _is_spyder_module(self, module_name: str) -> bool:
        """Check if a module follows SPYDER naming convention."""
        import re
        pattern = r".*\.Spyder[A-Z]\d+_.*"
        return bool(re.match(pattern, module_name))
    
    def _analyze_module(self, module_name: str, group_path: str) -> Optional[ModuleInfo]:
        """Analyze a module and extract information."""
        try:
            # Parse module name
            parts = module_name.split('.')[-1]  # Get last part (actual module name)
            
            # Extract group and number
            if len(parts) < 9:  # SpyderX##_
                return None
                
            group = parts[6]  # Character after 'Spyder'
            group_name = MODULE_GROUPS.get(group, 'Unknown')
            
            # Try to import and analyze
            try:
                module = importlib.import_module(module_name)
                
                # Extract metadata
                version = getattr(module, '__version__', '1.0')
                description = getattr(module, '__doc__', '').split('\n')[0] if hasattr(module, '__doc__') else ''
                
                # Find main class
                main_class = self._find_main_class(module)
                
                # Analyze dependencies
                dependencies = self._analyze_dependencies(module)
                
                # Determine integration level
                integration_level = self._determine_integration_level(dependencies)
                
                # Extract capabilities
                capabilities = self._extract_capabilities(module, main_class)
                
                module_info = ModuleInfo(
                    module_id=parts,
                    module_name=parts,
                    group=group,
                    group_name=group_name,
                    file_path=module.__file__ if hasattr(module, '__file__') else '',
                    class_name=main_class.__name__ if main_class else None,
                    version=version,
                    description=description.strip(),
                    state=ModuleState.DISCOVERED,
                    integration_level=integration_level,
                    dependencies=dependencies,
                    capabilities=capabilities,
                    metadata={
                        'module_object': weakref.ref(module),
                        'import_name': module_name,
                        'group_path': group_path
                    }
                )
                
                return module_info
                
            except ImportError as e:
                self.logger.debug(f"Could not import {module_name}: {e}")
                return None
                
        except Exception as e:
            self.logger.debug(f"Error analyzing {module_name}: {e}")
            return None
    
    def _find_main_class(self, module: Any) -> Optional[type]:
        """Find the main class in a module."""
        try:
            # Look for classes that match module naming pattern
            module_name = module.__name__.split('.')[-1]
            
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (obj.__module__ == module.__name__ and 
                    (name == module_name or name.startswith('Spyder'))):
                    return obj
                    
            return None
            
        except Exception:
            return None
    
    def _analyze_dependencies(self, module: Any) -> Set[str]:
        """Analyze module dependencies."""
        dependencies = set()
        
        try:
            # Check imports in module
            if hasattr(module, '__file__'):
                with open(module.__file__, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Find SPYDER imports
                import re
                spyder_imports = re.findall(
                    r'from\s+(Spyder[A-Z]_\w+\.Spyder[A-Z]\d+_\w+)|import\s+(Spyder[A-Z]\d+_\w+)',
                    content
                )
                
                for match in spyder_imports:
                    dep = match[0] or match[1]
                    if dep:
                        dependencies.add(dep.split('.')[-1])  # Get module name
                        
        except Exception as e:
            self.logger.debug(f"Could not analyze dependencies: {e}")
        
        return dependencies
    
    def _determine_integration_level(self, dependencies: Set[str]) -> IntegrationLevel:
        """Determine the integration level of a module."""
        dep_count = len(dependencies)
        
        if dep_count == 0:
            return IntegrationLevel.STANDALONE
        elif dep_count <= 2:
            return IntegrationLevel.BASIC
        elif dep_count <= 5:
            return IntegrationLevel.INTEGRATED
        elif dep_count <= 10:
            return IntegrationLevel.ADVANCED
        else:
            return IntegrationLevel.ECOSYSTEM
    
    def _extract_capabilities(self, module: Any, main_class: Optional[type]) -> List[str]:
        """Extract capabilities from a module."""
        capabilities = []
        
        try:
            # Check for common method patterns
            if main_class:
                methods = [name for name, _ in inspect.getmembers(main_class, inspect.ismethod)]
                
                # Common capability patterns
                capability_patterns = {
                    'monitoring': ['monitor', 'check_health', 'get_status'],
                    'trading': ['generate_signals', 'execute_trade', 'manage_position'],
                    'analysis': ['analyze', 'calculate', 'evaluate'],
                    'risk_management': ['check_risk', 'validate', 'limit'],
                    'data_processing': ['process', 'transform', 'parse'],
                    'alerting': ['send_alert', 'notify', 'trigger'],
                    'reporting': ['generate_report', 'create_report', 'export'],
                    'integration': ['register', 'connect', 'integrate']
                }
                
                for capability, patterns in capability_patterns.items():
                    if any(any(pattern in method.lower() for pattern in patterns) for method in methods):
                        capabilities.append(capability)
                        
        except Exception as e:
            self.logger.debug(f"Could not extract capabilities: {e}")
        
        return capabilities
    
    # ==========================================================================
    # DEPENDENCY MANAGEMENT
    # ==========================================================================
    def _build_dependency_graph(self) -> None:
        """Build dependency graph for all modules."""
        try:
            # Clear existing graph
            self.dependency_graph.clear()
            
            # Add all modules as nodes
            for module_id, module_info in self.modules.items():
                self.dependency_graph.add_node(module_id, **module_info.__dict__)
            
            # Add dependency edges
            for module_id, module_info in self.modules.items():
                for dependency in module_info.dependencies:
                    if dependency in self.modules:
                        self.dependency_graph.add_edge(dependency, module_id)
                        
                        # Update dependents
                        self.modules[dependency].dependents.add(module_id)
            
            # Calculate load order
            self._calculate_load_order()
            
            self.logger.info(f"📊 Built dependency graph: {len(self.modules)} modules, {self.dependency_graph.number_of_edges()} dependencies")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_build_dependency_graph'
            })
    
    def _calculate_load_order(self) -> None:
        """Calculate optimal module load order based on dependencies."""
        try:
            if self.dependency_graph.number_of_nodes() == 0:
                return
            
            # Check for cycles
            if not dag.is_directed_acyclic_graph(self.dependency_graph):
                cycles = list(dag.simple_cycles(self.dependency_graph))
                self.logger.warning(f"⚠️ Dependency cycles detected: {cycles}")
            
            # Topological sort for load order
            self.load_order = list(dag.topological_sort(self.dependency_graph))
            
            self.logger.info(f"📋 Calculated module load order: {len(self.load_order)} modules")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_load_order'
            })
            # Fallback: alphabetical order
            self.load_order = sorted(self.modules.keys())
    
    def get_dependencies(self, module_id: str, recursive: bool = False) -> Set[str]:
        """Get dependencies for a module."""
        try:
            if module_id not in self.modules:
                return set()
            
            if not recursive:
                return self.modules[module_id].dependencies.copy()
            
            # Get recursive dependencies using graph
            dependencies = set()
            if module_id in self.dependency_graph:
                predecessors = nx.ancestors(self.dependency_graph, module_id)
                dependencies.update(predecessors)
            
            return dependencies
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'get_dependencies',
                'module_id': module_id
            })
            return set()
    
    def get_dependents(self, module_id: str, recursive: bool = False) -> Set[str]:
        """Get modules that depend on this module."""
        try:
            if module_id not in self.modules:
                return set()
            
            if not recursive:
                return self.modules[module_id].dependents.copy()
            
            # Get recursive dependents using graph
            dependents = set()
            if module_id in self.dependency_graph:
                successors = nx.descendants(self.dependency_graph, module_id)
                dependents.update(successors)
            
            return dependents
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'get_dependents',
                'module_id': module_id
            })
            return set()
    
    # ==========================================================================
    # MODULE REGISTRATION AND LIFECYCLE
    # ==========================================================================
    def register_module(self, module_instance: Any, module_info: ModuleInfo = None) -> bool:
        """
        Register an active module instance.
        
        Args:
            module_instance: The module instance
            module_info: Module information (optional)
            
        Returns:
            Whether registration was successful
        """
        try:
            # Extract module info if not provided
            if module_info is None:
                module_name = module_instance.__class__.__name__
                module_info = self._create_module_info_from_instance(module_instance)
            
            module_id = module_info.module_id
            
            # Update registry
            self.modules[module_id] = module_info
            self.active_instances[module_id] = module_instance
            
            # Update state
            module_info.state = ModuleState.ACTIVE
            module_info.load_time = datetime.now()
            
            # Register factory if available
            if hasattr(module_instance.__class__, 'create_instance'):
                self.module_factories[module_id] = module_instance.__class__.create_instance
            
            # Rebuild dependency graph
            self._build_dependency_graph()
            
            # Perform initial health check
            self._perform_health_check(module_id)
            
            self.stats['modules_loaded'] += 1
            
            self.logger.info(f"📋 Registered module: {module_id}")
            
            # Emit event
            self.event_manager.publish(Event(
                type=EventType.SYSTEM,
                source="IntegrationHub",
                data={
                    'action': 'module_registered',
                    'module_id': module_id,
                    'module_info': module_info.__dict__
                }
            ))
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'register_module',
                'module_id': getattr(module_info, 'module_id', 'unknown') if module_info else 'unknown'
            })
            return False
    
    def unregister_module(self, module_id: str) -> bool:
        """Unregister a module."""
        try:
            if module_id not in self.modules:
                return False
            
            # Update state
            self.modules[module_id].state = ModuleState.UNLOADING
            
            # Remove from active instances
            if module_id in self.active_instances:
                del self.active_instances[module_id]
            
            # Remove from factories
            if module_id in self.module_factories:
                del self.module_factories[module_id]
            
            # Remove from health reports
            if module_id in self.health_reports:
                del self.health_reports[module_id]
            
            # Update state to disabled
            self.modules[module_id].state = ModuleState.DISABLED
            
            self.logger.info(f"📤 Unregistered module: {module_id}")
            
            # Emit event
            self.event_manager.publish(Event(
                type=EventType.SYSTEM,
                source="IntegrationHub",
                data={
                    'action': 'module_unregistered',
                    'module_id': module_id
                }
            ))
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'unregister_module',
                'module_id': module_id
            })
            return False
    
    def _create_module_info_from_instance(self, instance: Any) -> ModuleInfo:
        """Create module info from an instance."""
        class_name = instance.__class__.__name__
        
        # Parse SPYDER module name
        if class_name.startswith('Spyder'):
            group = class_name[6] if len(class_name) > 6 else 'U'
            group_name = MODULE_GROUPS.get(group, 'Unknown')
        else:
            group = 'U'
            group_name = 'Utilities'
        
        return ModuleInfo(
            module_id=class_name,
            module_name=class_name,
            group=group,
            group_name=group_name,
            file_path=inspect.getfile(instance.__class__),
            class_name=class_name,
            description=instance.__class__.__doc__.split('\n')[0] if instance.__class__.__doc__ else '',
            state=ModuleState.ACTIVE,
            capabilities=self._extract_capabilities_from_instance(instance)
        )
    
    def _extract_capabilities_from_instance(self, instance: Any) -> List[str]:
        """Extract capabilities from a module instance."""
        capabilities = []
        
        try:
            # Check methods
            methods = [name for name in dir(instance) if not name.startswith('_')]
            
            capability_patterns = {
                'monitoring': ['monitor', 'check', 'status', 'health'],
                'trading': ['signal', 'trade', 'position', 'order'],
                'analysis': ['analyze', 'calculate', 'evaluate', 'compute'],
                'risk_management': ['risk', 'validate', 'limit', 'check'],
                'data_processing': ['process', 'transform', 'parse', 'load'],
                'alerting': ['alert', 'notify', 'send', 'trigger'],
                'reporting': ['report', 'generate', 'export', 'create'],
                'integration': ['register', 'connect', 'integrate', 'sync']
            }
            
            for capability, patterns in capability_patterns.items():
                if any(any(pattern in method.lower() for pattern in patterns) for method in methods):
                    capabilities.append(capability)
                    
        except Exception:
            pass
        
        return capabilities
    
    # ==========================================================================
    # HEALTH MONITORING
    # ==========================================================================
    def _perform_health_check(self, module_id: str) -> HealthReport:
        """Perform health check on a module."""
        try:
            start_time = time.time()
            
            if module_id not in self.modules:
                return self._create_offline_health_report(module_id)
            
            module_info = self.modules[module_id]
            instance = self.active_instances.get(module_id)
            
            # Basic health check
            status = HealthStatus.HEALTHY
            issues = []
            metrics = {}
            
            # Check if instance is available
            if instance is None:
                status = HealthStatus.OFFLINE
                issues.append("Module instance not available")
            else:
                # Check if module has health check method
                if hasattr(instance, 'health_check'):
                    try:
                        health_result = instance.health_check()
                        if isinstance(health_result, dict):
                            if not health_result.get('healthy', True):
                                status = HealthStatus.WARNING
                                issues.extend(health_result.get('issues', []))
                            metrics.update(health_result.get('metrics', {}))
                    except Exception as e:
                        status = HealthStatus.CRITICAL
                        issues.append(f"Health check failed: {str(e)}")
                
                # Check error count
                if module_info.error_count > 10:
                    status = HealthStatus.WARNING
                    issues.append(f"High error count: {module_info.error_count}")
                elif module_info.error_count > 50:
                    status = HealthStatus.CRITICAL
                    issues.append(f"Critical error count: {module_info.error_count}")
            
            # Check dependencies
            dependencies_healthy = self._check_dependencies_health(module_id)
            if not dependencies_healthy:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
                issues.append("Some dependencies are unhealthy")
            
            # Response time
            response_time = (time.time() - start_time) * 1000  # ms
            
            # Create health report
            report = HealthReport(
                module_id=module_id,
                status=status,
                timestamp=datetime.now(),
                response_time=response_time,
                memory_usage=0.0,  # Would implement actual memory monitoring
                error_rate=module_info.error_count / max(1, (datetime.now() - (module_info.load_time or datetime.now())).total_seconds()),
                dependencies_healthy=dependencies_healthy,
                issues=issues,
                metrics=metrics
            )
            
            # Store report
            self.health_reports[module_id] = report
            self.health_history.append({
                'timestamp': report.timestamp,
                'module_id': module_id,
                'status': status.value,
                'response_time': response_time
            })
            
            # Update module info
            module_info.health = status
            module_info.last_health_check = report.timestamp
            return report
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_perform_health_check',
                'module_id': module_id
            })   
                 
                    
            
            
            
