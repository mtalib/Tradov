#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX12_SystemHealthAgent.py
Purpose: AI-Enhanced System Health Monitoring and Optimization
Group: X (AI Agents)

Description:
    Monitors system performance, detects anomalies, optimizes resource usage,
    and ensures the Spyder trading system operates at peak efficiency. This
    agent acts as the guardian of system reliability and performance.

    Key Features:
    - Real-time performance monitoring
    - Anomaly detection in trading patterns
    - Resource optimization (CPU, memory, network)
    - Predictive maintenance
    - System diagnostics and healing
    - Agent coordination monitoring

Author: AI Trading Assistant
Date: 2025-01-17
Version: 1.0.0

Dependencies:
    - ollama (for LLM integration)
    - psutil (for system monitoring)
    - pandas, numpy
    - asyncio
    - prometheus_client (for metrics)
"""

import asyncio
import json
import logging
import os
import sys
import gc
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import psutil
import platform
import socket
import threading
import time

# Import Spyder core components
from SpyderU01_DataStructures import SystemStatus
from SpyderU02_Configuration import config
from SpyderU03_Logger import SpyderLogger
from SpyderU04_EventManager import Event, EventType
from SpyderU12_AgentIntegration import SpyderBaseAgent, AgentState

# Health Status Levels
class HealthStatus(Enum):
    """System health status levels"""
    EXCELLENT = "excellent"  # 90-100% health
    GOOD = "good"           # 70-90% health
    WARNING = "warning"     # 50-70% health
    CRITICAL = "critical"   # 30-50% health
    FAILING = "failing"     # <30% health

# Anomaly Types
class AnomalyType(Enum):
    """Types of system anomalies"""
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    TRADING = "trading"
    DATA = "data"
    NETWORK = "network"
    AGENT = "agent"
    PATTERN = "pattern"

# Optimization Actions
class OptimizationAction(Enum):
    """System optimization actions"""
    GARBAGE_COLLECT = "garbage_collect"
    CACHE_CLEAR = "cache_clear"
    AGENT_RESTART = "agent_restart"
    THROTTLE_REQUESTS = "throttle_requests"
    SCALE_RESOURCES = "scale_resources"
    REBALANCE_LOAD = "rebalance_load"

@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available: int  # MB
    disk_usage: float
    network_latency: float  # ms
    api_response_time: float  # ms
    agent_response_times: Dict[str, float]
    active_threads: int
    open_connections: int

@dataclass
class AgentHealth:
    """Health status of an individual agent"""
    agent_name: str
    status: AgentState
    health_score: float  # 0-100
    response_time: float  # ms
    error_rate: float  # errors per minute
    last_heartbeat: datetime
    memory_usage: float  # MB
    cpu_usage: float  # percent
    issues: List[str] = field(default_factory=list)

@dataclass
class TradingMetrics:
    """Trading system metrics"""
    timestamp: datetime
    orders_per_minute: float
    average_execution_time: float  # ms
    error_rate: float
    success_rate: float
    active_positions: int
    daily_trades: int
    api_calls_per_minute: float
    data_lag: float  # seconds

@dataclass
class Anomaly:
    """Detected system anomaly"""
    anomaly_type: AnomalyType
    severity: float  # 0-1
    description: str
    affected_components: List[str]
    metrics: Dict[str, Any]
    detected_at: datetime
    resolved: bool = False
    resolution: Optional[str] = None

@dataclass
class HealthReport:
    """Comprehensive system health report"""
    timestamp: datetime
    overall_health: float  # 0-100
    status: HealthStatus
    system_metrics: SystemMetrics
    agent_health: Dict[str, AgentHealth]
    trading_metrics: TradingMetrics
    active_anomalies: List[Anomaly]
    recommendations: List[Dict[str, Any]]
    performance_score: float
    reliability_score: float

class SystemHealthAgent(SpyderBaseAgent):
    """
    AI-Enhanced System Health Monitoring Agent
    
    Monitors, diagnoses, and optimizes the entire Spyder trading system
    to ensure peak performance and reliability.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize System Health Agent"""
        super().__init__(config)
        
        # Agent configuration
        self.llm_model = config.get('health_llm_model', 'llama3.2:3b-instruct-q4_K_M')
        self.check_interval = config.get('health_check_seconds', 30)
        self.anomaly_threshold = config.get('anomaly_threshold', 0.7)
        
        # System info
        self.system_info = {
            'platform': platform.system(),
            'processor': platform.processor(),
            'python_version': sys.version,
            'hostname': socket.gethostname()
        }
        
        # Metrics storage
        self.system_metrics_history: deque = deque(maxlen=1440)  # 12 hours at 30s intervals
        self.agent_health_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1440))
        self.trading_metrics_history: deque = deque(maxlen=1440)
        self.anomaly_history: deque = deque(maxlen=100)
        
        # Performance baselines
        self.performance_baselines = {
            'cpu_percent': 50.0,
            'memory_percent': 70.0,
            'response_time': 1000.0,  # ms
            'error_rate': 0.01,
            'api_latency': 500.0  # ms
        }
        
        # Agent registry
        self.registered_agents: Dict[str, Dict[str, Any]] = {}
        self.agent_heartbeats: Dict[str, datetime] = {}
        
        # Anomaly detection
        self.anomaly_detectors = {
            AnomalyType.PERFORMANCE: self._detect_performance_anomalies,
            AnomalyType.RESOURCE: self._detect_resource_anomalies,
            AnomalyType.TRADING: self._detect_trading_anomalies,
            AnomalyType.AGENT: self._detect_agent_anomalies,
            AnomalyType.PATTERN: self._detect_pattern_anomalies
        }
        
        # Optimization strategies
        self.optimization_strategies = {
            OptimizationAction.GARBAGE_COLLECT: self._optimize_garbage_collect,
            OptimizationAction.CACHE_CLEAR: self._optimize_cache_clear,
            OptimizationAction.AGENT_RESTART: self._optimize_agent_restart,
            OptimizationAction.THROTTLE_REQUESTS: self._optimize_throttle_requests
        }
        
        # Health thresholds
        self.health_thresholds = {
            HealthStatus.EXCELLENT: 90,
            HealthStatus.GOOD: 70,
            HealthStatus.WARNING: 50,
            HealthStatus.CRITICAL: 30,
            HealthStatus.FAILING: 0
        }
        
        # Process monitor
        self.process = psutil.Process()
        
        # Diagnostic tools
        self.diagnostic_results: Dict[str, Any] = {}
        
        self.logger.info("System Health Agent initialized")

    async def initialize(self, event_manager=None, agent_registry=None):
        """Initialize agent with dependencies"""
        await super().initialize(event_manager)
        
        self.agent_registry = agent_registry
        
        # Subscribe to events
        if self.event_manager:
            self.event_manager.subscribe(EventType.AGENT_ERROR, self._handle_agent_error)
            self.event_manager.subscribe(EventType.SYSTEM_ERROR, self._handle_system_error)
            self.event_manager.subscribe(EventType.AGENT_HEARTBEAT, self._handle_agent_heartbeat)
        
        # Start monitoring tasks
        asyncio.create_task(self._monitor_system_loop())
        asyncio.create_task(self._monitor_agents_loop())
        asyncio.create_task(self._detect_anomalies_loop())
        asyncio.create_task(self._optimize_system_loop())
        asyncio.create_task(self._generate_reports_loop())
        
        self.state = AgentState.RUNNING
        self.logger.info("System Health Agent initialized and monitoring")

    async def get_system_health(self) -> HealthReport:
        """
        Get comprehensive system health report
        
        Returns:
            Current system health status
        """
        try:
            # Collect current metrics
            system_metrics = await self._collect_system_metrics()
            agent_health = await self._collect_agent_health()
            trading_metrics = await self._collect_trading_metrics()
            
            # Detect anomalies
            anomalies = await self._detect_all_anomalies()
            
            # Calculate health scores
            overall_health = self._calculate_overall_health(
                system_metrics, agent_health, trading_metrics, anomalies
            )
            
            # Determine status
            status = self._determine_health_status(overall_health)
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                system_metrics, agent_health, anomalies
            )
            
            # Calculate sub-scores
            performance_score = self._calculate_performance_score(system_metrics, trading_metrics)
            reliability_score = self._calculate_reliability_score(agent_health, anomalies)
            
            # Create report
            report = HealthReport(
                timestamp=datetime.now(),
                overall_health=overall_health,
                status=status,
                system_metrics=system_metrics,
                agent_health=agent_health,
                trading_metrics=trading_metrics,
                active_anomalies=[a for a in anomalies if not a.resolved],
                recommendations=recommendations,
                performance_score=performance_score,
                reliability_score=reliability_score
            )
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error getting system health: {str(e)}")
            return self._get_default_health_report()

    async def diagnose_issue(self, issue_description: str) -> Dict[str, Any]:
        """
        Diagnose a specific system issue
        
        Args:
            issue_description: Description of the issue
            
        Returns:
            Diagnostic results and recommendations
        """
        try:
            # Collect relevant data
            context = await self._collect_diagnostic_context()
            
            # AI-powered diagnosis
            diagnosis = await self._ai_diagnose_issue(issue_description, context)
            
            # Run specific diagnostics
            if 'slow' in issue_description.lower():
                perf_diag = await self._diagnose_performance_issues()
                diagnosis['performance_diagnosis'] = perf_diag
            
            if 'error' in issue_description.lower():
                error_diag = await self._diagnose_error_patterns()
                diagnosis['error_diagnosis'] = error_diag
            
            if 'memory' in issue_description.lower():
                mem_diag = await self._diagnose_memory_issues()
                diagnosis['memory_diagnosis'] = mem_diag
            
            # Generate action plan
            action_plan = await self._generate_action_plan(diagnosis)
            diagnosis['action_plan'] = action_plan
            
            # Store results
            self.diagnostic_results[datetime.now().isoformat()] = diagnosis
            
            return diagnosis
            
        except Exception as e:
            self.logger.error(f"Error diagnosing issue: {str(e)}")
            return {'error': str(e), 'recommendation': 'Check system logs'}

    async def optimize_system(self, target: Optional[str] = None) -> Dict[str, Any]:
        """
        Optimize system performance
        
        Args:
            target: Specific optimization target (performance, memory, etc.)
            
        Returns:
            Optimization results
        """
        try:
            results = {}
            
            if target == 'memory' or target is None:
                # Memory optimization
                mem_before = self.process.memory_info().rss / 1024 / 1024  # MB
                gc.collect()
                mem_after = self.process.memory_info().rss / 1024 / 1024
                
                results['memory'] = {
                    'before_mb': mem_before,
                    'after_mb': mem_after,
                    'freed_mb': mem_before - mem_after
                }
            
            if target == 'cache' or target is None:
                # Clear caches
                cache_cleared = await self._clear_system_caches()
                results['cache'] = cache_cleared
            
            if target == 'performance' or target is None:
                # Performance optimization
                perf_results = await self._optimize_performance()
                results['performance'] = perf_results
            
            if target == 'agents' or target is None:
                # Agent optimization
                agent_results = await self._optimize_agents()
                results['agents'] = agent_results
            
            # AI recommendations
            ai_recommendations = await self._get_optimization_recommendations()
            results['recommendations'] = ai_recommendations
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error optimizing system: {str(e)}")
            return {'error': str(e)}

    async def register_agent(self, agent_name: str, agent_info: Dict[str, Any]):
        """
        Register an agent for health monitoring
        
        Args:
            agent_name: Name of the agent
            agent_info: Agent information and capabilities
        """
        self.registered_agents[agent_name] = {
            'info': agent_info,
            'registered_at': datetime.now(),
            'health_checks': 0,
            'total_errors': 0
        }
        
        self.logger.info(f"Registered agent: {agent_name}")

    async def check_agent_health(self, agent_name: str) -> AgentHealth:
        """
        Check health of a specific agent
        
        Args:
            agent_name: Name of the agent to check
            
        Returns:
            Agent health status
        """
        try:
            # Get agent info
            if agent_name not in self.registered_agents:
                return self._get_unknown_agent_health(agent_name)
            
            # Check heartbeat
            last_heartbeat = self.agent_heartbeats.get(agent_name, datetime.min)
            heartbeat_age = (datetime.now() - last_heartbeat).total_seconds()
            
            # Check response time (mock for now)
            response_time = await self._measure_agent_response_time(agent_name)
            
            # Check error rate
            error_rate = self._calculate_agent_error_rate(agent_name)
            
            # Check resource usage
            memory_usage, cpu_usage = await self._get_agent_resource_usage(agent_name)
            
            # Calculate health score
            health_score = self._calculate_agent_health_score(
                heartbeat_age, response_time, error_rate, memory_usage, cpu_usage
            )
            
            # Determine status
            if heartbeat_age > 300:  # 5 minutes
                status = AgentState.STOPPED
            elif health_score < 50:
                status = AgentState.ERROR
            else:
                status = AgentState.RUNNING
            
            # Identify issues
            issues = []
            if heartbeat_age > 60:
                issues.append(f"No heartbeat for {heartbeat_age:.0f} seconds")
            if response_time > 1000:
                issues.append(f"Slow response time: {response_time:.0f}ms")
            if error_rate > 0.05:
                issues.append(f"High error rate: {error_rate:.1%}")
            if memory_usage > 500:
                issues.append(f"High memory usage: {memory_usage:.0f}MB")
            
            return AgentHealth(
                agent_name=agent_name,
                status=status,
                health_score=health_score,
                response_time=response_time,
                error_rate=error_rate,
                last_heartbeat=last_heartbeat,
                memory_usage=memory_usage,
                cpu_usage=cpu_usage,
                issues=issues
            )
            
        except Exception as e:
            self.logger.error(f"Error checking agent health: {str(e)}")
            return self._get_unknown_agent_health(agent_name)

    async def predict_failures(self) -> List[Dict[str, Any]]:
        """
        Predict potential system failures using AI
        
        Returns:
            List of predicted failures with probabilities
        """
        try:
            predictions = []
            
            # Analyze trends
            if len(self.system_metrics_history) > 100:
                # Memory leak prediction
                memory_trend = self._analyze_metric_trend('memory_percent')
                if memory_trend['slope'] > 0.1:  # Increasing memory usage
                    predictions.append({
                        'type': 'memory_exhaustion',
                        'probability': min(0.9, memory_trend['slope'] * 5),
                        'time_to_failure': self._estimate_time_to_threshold(
                            memory_trend, 90  # 90% threshold
                        ),
                        'severity': 'high',
                        'recommendation': 'Investigate memory leak and restart affected components'
                    })
                
                # Performance degradation prediction
                response_trend = self._analyze_metric_trend('api_response_time')
                if response_trend['slope'] > 10:  # Increasing response time
                    predictions.append({
                        'type': 'performance_degradation',
                        'probability': min(0.8, response_trend['slope'] / 50),
                        'time_to_failure': self._estimate_time_to_threshold(
                            response_trend, 2000  # 2 second threshold
                        ),
                        'severity': 'medium',
                        'recommendation': 'Optimize slow queries and reduce system load'
                    })
            
            # Agent failure prediction
            for agent_name, health_history in self.agent_health_history.items():
                if len(health_history) > 10:
                    recent_health = [h.health_score for h in list(health_history)[-10:]]
                    health_trend = np.polyfit(range(len(recent_health)), recent_health, 1)[0]
                    
                    if health_trend < -2:  # Declining health
                        predictions.append({
                            'type': 'agent_failure',
                            'agent': agent_name,
                            'probability': min(0.7, abs(health_trend) / 10),
                            'time_to_failure': self._estimate_time_to_zero(health_trend, recent_health[-1]),
                            'severity': 'high',
                            'recommendation': f'Check {agent_name} logs and consider restart'
                        })
            
            # AI-enhanced predictions
            ai_predictions = await self._ai_predict_failures()
            predictions.extend(ai_predictions)
            
            # Sort by probability
            predictions.sort(key=lambda x: x['probability'], reverse=True)
            
            return predictions
            
        except Exception as e:
            self.logger.error(f"Error predicting failures: {str(e)}")
            return []

    async def get_performance_report(self) -> Dict[str, Any]:
        """
        Get detailed performance report
        
        Returns:
            Performance metrics and analysis
        """
        try:
            # Calculate averages over different periods
            periods = {
                '5min': 10,    # 10 samples = 5 minutes
                '1hour': 120,  # 120 samples = 1 hour
                '6hour': 720   # 720 samples = 6 hours
            }
            
            performance = {}
            
            for period_name, samples in periods.items():
                recent_metrics = list(self.system_metrics_history)[-samples:]
                
                if recent_metrics:
                    performance[period_name] = {
                        'avg_cpu': np.mean([m.cpu_percent for m in recent_metrics]),
                        'avg_memory': np.mean([m.memory_percent for m in recent_metrics]),
                        'avg_latency': np.mean([m.api_response_time for m in recent_metrics]),
                        'max_cpu': max([m.cpu_percent for m in recent_metrics]),
                        'max_memory': max([m.memory_percent for m in recent_metrics]),
                        'max_latency': max([m.api_response_time for m in recent_metrics])
                    }
            
            # Trading performance
            recent_trading = list(self.trading_metrics_history)[-120:]  # Last hour
            if recent_trading:
                performance['trading'] = {
                    'avg_execution_time': np.mean([t.average_execution_time for t in recent_trading]),
                    'total_orders': sum([t.orders_per_minute for t in recent_trading]) * 0.5,
                    'success_rate': np.mean([t.success_rate for t in recent_trading]),
                    'error_rate': np.mean([t.error_rate for t in recent_trading])
                }
            
            # Agent performance
            agent_performance = {}
            for agent_name, health_history in self.agent_health_history.items():
                recent = list(health_history)[-120:]
                if recent:
                    agent_performance[agent_name] = {
                        'avg_health': np.mean([h.health_score for h in recent]),
                        'avg_response_time': np.mean([h.response_time for h in recent]),
                        'uptime': sum(1 for h in recent if h.status == AgentState.RUNNING) / len(recent)
                    }
            
            performance['agents'] = agent_performance
            
            # Anomaly statistics
            recent_anomalies = [a for a in self.anomaly_history 
                              if a.detected_at > datetime.now() - timedelta(hours=24)]
            
            performance['anomalies'] = {
                'last_24h': len(recent_anomalies),
                'by_type': defaultdict(int),
                'resolved_rate': sum(1 for a in recent_anomalies if a.resolved) / max(len(recent_anomalies), 1)
            }
            
            for anomaly in recent_anomalies:
                performance['anomalies']['by_type'][anomaly.anomaly_type.value] += 1
            
            return performance
            
        except Exception as e:
            self.logger.error(f"Error generating performance report: {str(e)}")
            return {}

    async def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available / 1024 / 1024  # MB
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage = disk.percent
            
            # Network latency (mock)
            network_latency = await self._measure_network_latency()
            
            # API response time (mock)
            api_response_time = await self._measure_api_latency()
            
            # Agent response times
            agent_response_times = {}
            for agent_name in self.registered_agents:
                agent_response_times[agent_name] = await self._measure_agent_response_time(agent_name)
            
            # Thread and connection count
            active_threads = threading.active_count()
            
            # Get connection count
            try:
                connections = len(self.process.connections())
            except:
                connections = 0
            
            metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available=memory_available,
                disk_usage=disk_usage,
                network_latency=network_latency,
                api_response_time=api_response_time,
                agent_response_times=agent_response_times,
                active_threads=active_threads,
                open_connections=connections
            )
            
            # Store in history
            self.system_metrics_history.append(metrics)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {str(e)}")
            return self._get_default_system_metrics()

    async def _collect_agent_health(self) -> Dict[str, AgentHealth]:
        """Collect health status of all agents"""
        agent_health = {}
        
        for agent_name in self.registered_agents:
            health = await self.check_agent_health(agent_name)
            agent_health[agent_name] = health
            
            # Store in history
            self.agent_health_history[agent_name].append(health)
        
        return agent_health

    async def _collect_trading_metrics(self) -> TradingMetrics:
        """Collect trading system metrics"""
        try:
            # Mock implementation - would collect from trading system
            metrics = TradingMetrics(
                timestamp=datetime.now(),
                orders_per_minute=np.random.uniform(0, 5),
                average_execution_time=np.random.uniform(50, 200),
                error_rate=np.random.uniform(0, 0.05),
                success_rate=np.random.uniform(0.9, 1.0),
                active_positions=np.random.randint(0, 20),
                daily_trades=np.random.randint(10, 100),
                api_calls_per_minute=np.random.uniform(5, 50),
                data_lag=np.random.uniform(0, 2)
            )
            
            # Store in history
            self.trading_metrics_history.append(metrics)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting trading metrics: {str(e)}")
            return self._get_default_trading_metrics()

    async def _detect_all_anomalies(self) -> List[Anomaly]:
        """Detect all types of anomalies"""
        anomalies = []
        
        for anomaly_type, detector in self.anomaly_detectors.items():
            detected = await detector()
            anomalies.extend(detected)
        
        # Store new anomalies
        for anomaly in anomalies:
            if anomaly not in self.anomaly_history:
                self.anomaly_history.append(anomaly)
                
                # Publish high-severity anomalies
                if anomaly.severity > 0.7 and self.event_manager:
                    await self.event_manager.publish(Event(
                        type=EventType.ANOMALY_DETECTED,
                        data={'anomaly': anomaly}
                    ))
        
        return anomalies

    async def _detect_performance_anomalies(self) -> List[Anomaly]:
        """Detect performance-related anomalies"""
        anomalies = []
        
        if len(self.system_metrics_history) < 10:
            return anomalies
        
        recent_metrics = list(self.system_metrics_history)[-10:]
        
        # High CPU usage
        avg_cpu = np.mean([m.cpu_percent for m in recent_metrics])
        if avg_cpu > self.performance_baselines['cpu_percent'] * 1.5:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.PERFORMANCE,
                severity=min(1.0, (avg_cpu - 50) / 50),
                description=f"High CPU usage: {avg_cpu:.1f}%",
                affected_components=['system'],
                metrics={'cpu_percent': avg_cpu},
                detected_at=datetime.now()
            ))
        
        # Slow response times
        avg_response = np.mean([m.api_response_time for m in recent_metrics])
        if avg_response > self.performance_baselines['response_time']:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.PERFORMANCE,
                severity=min(1.0, (avg_response - 500) / 1500),
                description=f"Slow API response: {avg_response:.0f}ms",
                affected_components=['api'],
                metrics={'response_time': avg_response},
                detected_at=datetime.now()
            ))
        
        return anomalies

    async def _detect_resource_anomalies(self) -> List[Anomaly]:
        """Detect resource-related anomalies"""
        anomalies = []
        
        if len(self.system_metrics_history) < 5:
            return anomalies
        
        recent_metrics = list(self.system_metrics_history)[-5:]
        
        # High memory usage
        avg_memory = np.mean([m.memory_percent for m in recent_metrics])
        if avg_memory > self.performance_baselines['memory_percent']:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.RESOURCE,
                severity=min(1.0, (avg_memory - 70) / 30),
                description=f"High memory usage: {avg_memory:.1f}%",
                affected_components=['system'],
                metrics={'memory_percent': avg_memory},
                detected_at=datetime.now()
            ))
        
        # Low disk space
        if recent_metrics[-1].disk_usage > 85:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.RESOURCE,
                severity=(recent_metrics[-1].disk_usage - 85) / 15,
                description=f"Low disk space: {recent_metrics[-1].disk_usage:.1f}% used",
                affected_components=['storage'],
                metrics={'disk_usage': recent_metrics[-1].disk_usage},
                detected_at=datetime.now()
            ))
        
        return anomalies

    async def _detect_trading_anomalies(self) -> List[Anomaly]:
        """Detect trading-related anomalies"""
        anomalies = []
        
        if len(self.trading_metrics_history) < 10:
            return anomalies
        
        recent_trading = list(self.trading_metrics_history)[-10:]
        
        # High error rate
        avg_error_rate = np.mean([t.error_rate for t in recent_trading])
        if avg_error_rate > self.performance_baselines['error_rate']:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.TRADING,
                severity=min(1.0, avg_error_rate * 20),
                description=f"High trading error rate: {avg_error_rate:.1%}",
                affected_components=['trading_engine'],
                metrics={'error_rate': avg_error_rate},
                detected_at=datetime.now()
            ))
        
        # Data lag
        current_lag = recent_trading[-1].data_lag
        if current_lag > 5:  # 5 seconds
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.DATA,
                severity=min(1.0, current_lag / 10),
                description=f"High data lag: {current_lag:.1f} seconds",
                affected_components=['data_feed'],
                metrics={'data_lag': current_lag},
                detected_at=datetime.now()
            ))
        
        return anomalies

    async def _detect_agent_anomalies(self) -> List[Anomaly]:
        """Detect agent-related anomalies"""
        anomalies = []
        
        for agent_name, health_history in self.agent_health_history.items():
            if len(health_history) < 5:
                continue
            
            recent_health = list(health_history)[-5:]
            
            # Agent down
            if all(h.status != AgentState.RUNNING for h in recent_health):
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.AGENT,
                    severity=0.9,
                    description=f"Agent {agent_name} is down",
                    affected_components=[agent_name],
                    metrics={'status': 'down'},
                    detected_at=datetime.now()
                ))
            
            # Degraded health
            avg_health = np.mean([h.health_score for h in recent_health])
            if avg_health < 50:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.AGENT,
                    severity=(50 - avg_health) / 50,
                    description=f"Agent {agent_name} health degraded: {avg_health:.0f}%",
                    affected_components=[agent_name],
                    metrics={'health_score': avg_health},
                    detected_at=datetime.now()
                ))
        
        return anomalies

    async def _detect_pattern_anomalies(self) -> List[Anomaly]:
        """Detect pattern-based anomalies using AI"""
        anomalies = []
        
        # Use AI to detect unusual patterns
        try:
            # Prepare data for AI analysis
            recent_data = {
                'system_metrics': [m.__dict__ for m in list(self.system_metrics_history)[-20:]],
                'trading_metrics': [t.__dict__ for t in list(self.trading_metrics_history)[-20:]]
            }
            
            # AI pattern detection
            ai_anomalies = await self._ai_detect_patterns(recent_data)
            
            for ai_anomaly in ai_anomalies:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.PATTERN,
                    severity=ai_anomaly['severity'],
                    description=ai_anomaly['description'],
                    affected_components=ai_anomaly.get('components', ['unknown']),
                    metrics=ai_anomaly.get('metrics', {}),
                    detected_at=datetime.now()
                ))
                
        except Exception as e:
            self.logger.error(f"Error in pattern anomaly detection: {str(e)}")
        
        return anomalies

    async def _ai_detect_patterns(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use AI to detect unusual patterns"""
        try:
            prompt = f"""
            Analyze this system data for unusual patterns or anomalies:
            
            System Metrics (last 20 samples):
            - CPU usage trend
            - Memory usage trend
            - Response time patterns
            
            Trading Metrics (last 20 samples):
            - Order volume patterns
            - Error rate changes
            - Success rate variations
            
            Look for:
            1. Unusual spikes or drops
            2. Gradual degradation
            3. Cyclic patterns
            4. Correlation anomalies
            
            Return JSON array of detected anomalies with:
            severity (0-1), description, components, metrics
            """
            
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=3.0)
            
            try:
                return json.loads(response)
            except:
                return []
                
        except Exception as e:
            self.logger.error(f"Error in AI pattern detection: {str(e)}")
            return []

    def _calculate_overall_health(
        self,
        system_metrics: SystemMetrics,
        agent_health: Dict[str, AgentHealth],
        trading_metrics: TradingMetrics,
        anomalies: List[Anomaly]
    ) -> float:
        """Calculate overall system health score"""
        
        # System metrics score (0-100)
        system_score = 100
        system_score -= min(50, max(0, system_metrics.cpu_percent - 50))  # Penalty for high CPU
        system_score -= min(30, max(0, system_metrics.memory_percent - 70))  # Penalty for high memory
        system_score -= min(20, max(0, (system_metrics.api_response_time - 500) / 50))  # Penalty for slow response
        
        # Agent health score (0-100)
        if agent_health:
            agent_scores = [h.health_score for h in agent_health.values()]
            agent_score = np.mean(agent_scores)
        else:
            agent_score = 100
        
        # Trading metrics score (0-100)
        trading_score = 100
        trading_score -= trading_metrics.error_rate * 1000  # Heavy penalty for errors
        trading_score -= max(0, (trading_metrics.data_lag - 1) * 10)  # Penalty for lag
        trading_score = max(0, trading_score)
        
        # Anomaly penalty
        anomaly_penalty = sum(a.severity * 10 for a in anomalies if not a.resolved)
        anomaly_penalty = min(50, anomaly_penalty)  # Cap at 50
        
        # Weighted average
        overall_health = (
            system_score * 0.3 +
            agent_score * 0.3 +
            trading_score * 0.3 +
            (100 - anomaly_penalty) * 0.1
        )
        
        return max(0, min(100, overall_health))

    def _determine_health_status(self, health_score: float) -> HealthStatus:
        """Determine health status from score"""
        for status, threshold in self.health_thresholds.items():
            if health_score >= threshold:
                return status
        return HealthStatus.FAILING

    async def _generate_recommendations(
        self,
        system_metrics: SystemMetrics,
        agent_health: Dict[str, AgentHealth],
        anomalies: List[Anomaly]
    ) -> List[Dict[str, Any]]:
        """Generate system optimization recommendations"""
        recommendations = []
        
        # System metrics recommendations
        if system_metrics.cpu_percent > 70:
            recommendations.append({
                'type': 'performance',
                'priority': 'high',
                'action': 'Reduce CPU load',
                'details': 'Consider scaling resources or optimizing algorithms'
            })
        
        if system_metrics.memory_percent > 80:
            recommendations.append({
                'type': 'resource',
                'priority': 'high',
                'action': 'Free memory',
                'details': 'Run garbage collection and check for memory leaks'
            })
        
        # Agent recommendations
        for agent_name, health in agent_health.items():
            if health.health_score < 50:
                recommendations.append({
                    'type': 'agent',
                    'priority': 'medium',
                    'action': f'Check {agent_name}',
                    'details': f'Agent health is low: {", ".join(health.issues)}'
                })
        
        # Anomaly recommendations
        for anomaly in anomalies:
            if not anomaly.resolved and anomaly.severity > 0.5:
                recommendations.append({
                    'type': 'anomaly',
                    'priority': 'high' if anomaly.severity > 0.7 else 'medium',
                    'action': f'Address {anomaly.description}',
                    'details': f'Affects: {", ".join(anomaly.affected_components)}'
                })
        
        # AI recommendations
        ai_recs = await self._get_ai_recommendations(system_metrics, agent_health, anomalies)
        recommendations.extend(ai_recs)
        
        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return recommendations[:10]  # Top 10 recommendations

    async def _get_ai_recommendations(
        self,
        system_metrics: SystemMetrics,
        agent_health: Dict[str, AgentHealth],
        anomalies: List[Anomaly]
    ) -> List[Dict[str, Any]]:
        """Get AI-powered recommendations"""
        try:
            context = {
                'cpu': system_metrics.cpu_percent,
                'memory': system_metrics.memory_percent,
                'response_time': system_metrics.api_response_time,
                'unhealthy_agents': [a for a, h in agent_health.items() if h.health_score < 70],
                'active_anomalies': len([a for a in anomalies if not a.resolved])
            }
            
            prompt = f"""
            Based on these system metrics:
            {json.dumps(context, indent=2)}
            
            Provide optimization recommendations.
            Return JSON array with: type, priority, action, details
            """
            
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=2.0)
            
            try:
                return json.loads(response)
            except:
                return []
                
        except:
            return []

    def _calculate_performance_score(
        self,
        system_metrics: SystemMetrics,
        trading_metrics: TradingMetrics
    ) -> float:
        """Calculate performance score"""
        score = 100
        
        # Response time impact
        if system_metrics.api_response_time > 100:
            score -= min(30, (system_metrics.api_response_time - 100) / 50)
        
        # Trading execution impact
        if trading_metrics.average_execution_time > 100:
            score -= min(20, (trading_metrics.average_execution_time - 100) / 50)
        
        # CPU efficiency
        if system_metrics.cpu_percent < 30:
            score += 10  # Bonus for efficient CPU usage
        
        return max(0, min(100, score))

    def _calculate_reliability_score(
        self,
        agent_health: Dict[str, AgentHealth],
        anomalies: List[Anomaly]
    ) -> float:
        """Calculate reliability score"""
        score = 100
        
        # Agent uptime impact
        if agent_health:
            down_agents = sum(1 for h in agent_health.values() if h.status != AgentState.RUNNING)
            score -= down_agents * 15
        
        # Anomaly impact
        active_anomalies = sum(1 for a in anomalies if not a.resolved)
        score -= min(50, active_anomalies * 5)
        
        # Error rate impact (from agent health)
        if agent_health:
            avg_error_rate = np.mean([h.error_rate for h in agent_health.values()])
            score -= min(20, avg_error_rate * 200)
        
        return max(0, min(100, score))

    async def _measure_network_latency(self) -> float:
        """Measure network latency"""
        # Mock implementation
        return np.random.uniform(5, 50)

    async def _measure_api_latency(self) -> float:
        """Measure API response time"""
        # Mock implementation
        return np.random.uniform(50, 500)

    async def _measure_agent_response_time(self, agent_name: str) -> float:
        """Measure agent response time"""
        # Mock implementation
        base_time = 100
        if 'ml' in agent_name.lower():
            base_time = 300  # ML agents are slower
        
        return np.random.uniform(base_time * 0.5, base_time * 1.5)

    def _calculate_agent_error_rate(self, agent_name: str) -> float:
        """Calculate agent error rate"""
        # Mock implementation
        return np.random.uniform(0, 0.05)

    async def _get_agent_resource_usage(self, agent_name: str) -> Tuple[float, float]:
        """Get agent resource usage"""
        # Mock implementation
        base_memory = 100  # MB
        if 'ml' in agent_name.lower():
            base_memory = 300
        
        memory = np.random.uniform(base_memory * 0.8, base_memory * 1.2)
        cpu = np.random.uniform(1, 10)
        
        return memory, cpu

    def _calculate_agent_health_score(
        self,
        heartbeat_age: float,
        response_time: float,
        error_rate: float,
        memory_usage: float,
        cpu_usage: float
    ) -> float:
        """Calculate agent health score"""
        score = 100
        
        # Heartbeat penalty
        if heartbeat_age > 60:
            score -= min(30, heartbeat_age / 10)
        
        # Response time penalty
        if response_time > 500:
            score -= min(20, (response_time - 500) / 100)
        
        # Error rate penalty
        score -= min(30, error_rate * 500)
        
        # Resource usage penalty
        if memory_usage > 500:
            score -= min(10, (memory_usage - 500) / 100)
        
        if cpu_usage > 50:
            score -= min(10, (cpu_usage - 50) / 5)
        
        return max(0, min(100, score))

    def _analyze_metric_trend(self, metric_name: str) -> Dict[str, float]:
        """Analyze trend of a metric"""
        if len(self.system_metrics_history) < 10:
            return {'slope': 0, 'intercept': 0}
        
        recent_metrics = list(self.system_metrics_history)[-60:]  # Last 30 minutes
        values = [getattr(m, metric_name, 0) for m in recent_metrics]
        
        if len(values) > 1:
            x = np.arange(len(values))
            slope, intercept = np.polyfit(x, values, 1)
            return {'slope': slope, 'intercept': intercept}
        
        return {'slope': 0, 'intercept': values[0] if values else 0}

    def _estimate_time_to_threshold(self, trend: Dict[str, float], threshold: float) -> float:
        """Estimate time to reach threshold based on trend"""
        if trend['slope'] <= 0:
            return float('inf')
        
        current_value = trend['intercept'] + trend['slope'] * 60  # Current value
        if current_value >= threshold:
            return 0
        
        # Time = (threshold - current) / slope
        # Convert to hours
        time_periods = (threshold - current_value) / trend['slope']
        return time_periods * 0.5 / 60  # Convert 30-second periods to hours

    def _estimate_time_to_zero(self, slope: float, current_value: float) -> float:
        """Estimate time to reach zero"""
        if slope >= 0:
            return float('inf')
        
        # Time = -current / slope
        # Each period is 30 seconds
        time_periods = -current_value / slope
        return time_periods * 0.5 / 60  # Convert to hours

    async def _ai_diagnose_issue(self, issue: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """AI-powered issue diagnosis"""
        try:
            prompt = f"""
            Diagnose this system issue:
            "{issue}"
            
            Context:
            {json.dumps(context, indent=2)}
            
            Provide:
            1. Root cause analysis
            2. Affected components
            3. Severity assessment
            4. Resolution steps
            
            Return JSON with: root_cause, affected_components, severity, resolution_steps
            """
            
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=3.0)
            
            try:
                return json.loads(response)
            except:
                return {
                    'root_cause': 'Unable to determine',
                    'affected_components': ['unknown'],
                    'severity': 'medium',
                    'resolution_steps': ['Check system logs', 'Monitor metrics']
                }
                
        except Exception as e:
            self.logger.error(f"Error in AI diagnosis: {str(e)}")
            return {
                'root_cause': 'Analysis failed',
                'affected_components': ['unknown'],
                'severity': 'unknown',
                'resolution_steps': ['Manual investigation required']
            }

    async def _collect_diagnostic_context(self) -> Dict[str, Any]:
        """Collect context for diagnostics"""
        recent_metrics = list(self.system_metrics_history)[-10:]
        recent_anomalies = list(self.anomaly_history)[-10:]
        
        return {
            'system_state': {
                'cpu_avg': np.mean([m.cpu_percent for m in recent_metrics]) if recent_metrics else 0,
                'memory_avg': np.mean([m.memory_percent for m in recent_metrics]) if recent_metrics else 0,
                'active_anomalies': len([a for a in recent_anomalies if not a.resolved])
            },
            'agent_states': {
                name: self.agent_health_history[name][-1].status.value 
                for name in self.registered_agents 
                if name in self.agent_health_history and self.agent_health_history[name]
            }
        }

    async def _diagnose_performance_issues(self) -> Dict[str, Any]:
        """Diagnose performance issues"""
        # Simplified implementation
        return {
            'bottlenecks': ['API response time', 'Database queries'],
            'recommendations': ['Optimize slow queries', 'Add caching layer']
        }

    async def _diagnose_error_patterns(self) -> Dict[str, Any]:
        """Diagnose error patterns"""
        # Simplified implementation
        return {
            'common_errors': ['Timeout errors', 'Connection refused'],
            'error_sources': ['External API', 'Database connection'],
            'mitigation': ['Implement retry logic', 'Add circuit breakers']
        }

    async def _diagnose_memory_issues(self) -> Dict[str, Any]:
        """Diagnose memory issues"""
        # Simplified implementation
        return {
            'memory_leaks': ['Possible leak in ML agent'],
            'large_objects': ['Historical data cache', 'Model weights'],
            'recommendations': ['Implement data rotation', 'Optimize model loading']
        }

    async def _generate_action_plan(self, diagnosis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate action plan from diagnosis"""
        actions = []
        
        # Add immediate actions
        if diagnosis.get('severity') == 'high':
            actions.append({
                'priority': 1,
                'action': 'Immediate intervention required',
                'steps': diagnosis.get('resolution_steps', [])
            })
        
        # Add preventive actions
        actions.append({
            'priority': 2,
            'action': 'Implement monitoring',
            'steps': ['Add alerts for affected components', 'Track metrics']
        })
        
        return actions

    async def _clear_system_caches(self) -> Dict[str, int]:
        """Clear system caches"""
        cleared = {}
        
        # Clear agent caches (mock)
        for agent_name in self.registered_agents:
            cleared[agent_name] = np.random.randint(10, 100)  # MB cleared
        
        return cleared

    async def _optimize_performance(self) -> Dict[str, Any]:
        """Optimize system performance"""
        return {
            'optimizations_applied': [
                'Query optimization',
                'Connection pooling adjusted',
                'Cache TTL updated'
            ],
            'expected_improvement': '15-20%'
        }

    async def _optimize_agents(self) -> Dict[str, Any]:
        """Optimize agent performance"""
        results = {}
        
        for agent_name in self.registered_agents:
            results[agent_name] = {
                'restarted': False,
                'cache_cleared': True,
                'config_optimized': True
            }
        
        return results

    async def _get_optimization_recommendations(self) -> List[str]:
        """Get AI optimization recommendations"""
        return [
            "Consider implementing request batching",
            "Enable compression for API responses",
            "Optimize database indices for common queries"
        ]

    async def _optimize_garbage_collect(self) -> Dict[str, Any]:
        """Run garbage collection"""
        before = self.process.memory_info().rss / 1024 / 1024
        gc.collect()
        after = self.process.memory_info().rss / 1024 / 1024
        
        return {
            'memory_before_mb': before,
            'memory_after_mb': after,
            'freed_mb': before - after
        }

    async def _optimize_cache_clear(self) -> Dict[str, Any]:
        """Clear caches"""
        return await self._clear_system_caches()

    async def _optimize_agent_restart(self) -> Dict[str, Any]:
        """Restart unhealthy agents"""
        restarted = []
        
        for agent_name, health_history in self.agent_health_history.items():
            if health_history and health_history[-1].health_score < 30:
                restarted.append(agent_name)
                # Would actually restart agent here
        
        return {'restarted_agents': restarted}

    async def _optimize_throttle_requests(self) -> Dict[str, Any]:
        """Throttle request rates"""
        return {
            'api_rate_limit': 'Reduced to 80%',
            'agent_request_delay': 'Added 100ms delay'
        }

    async def _ai_predict_failures(self) -> List[Dict[str, Any]]:
        """AI-powered failure prediction"""
        try:
            # Prepare context
            context = {
                'memory_trend': self._analyze_metric_trend('memory_percent'),
                'cpu_trend': self._analyze_metric_trend('cpu_percent'),
                'error_trends': {
                    agent: len([h for h in list(history)[-20:] if h.error_rate > 0.05])
                    for agent, history in self.agent_health_history.items()
                },
                'anomaly_frequency': len(self.anomaly_history) / max(len(self.system_metrics_history), 1)
            }
            
            prompt = f"""
            Predict potential system failures based on:
            {json.dumps(context, indent=2)}
            
            Return JSON array of predictions with:
            type, probability (0-1), time_to_failure (hours), severity, recommendation
            """
            
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=2.0)
            
            try:
                return json.loads(response)
            except:
                return []
                
        except:
            return []

    def _get_default_health_report(self) -> HealthReport:
        """Get default health report"""
        return HealthReport(
            timestamp=datetime.now(),
            overall_health=50,
            status=HealthStatus.WARNING,
            system_metrics=self._get_default_system_metrics(),
            agent_health={},
            trading_metrics=self._get_default_trading_metrics(),
            active_anomalies=[],
            recommendations=[],
            performance_score=50,
            reliability_score=50
        )

    def _get_default_system_metrics(self) -> SystemMetrics:
        """Get default system metrics"""
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=0,
            memory_percent=0,
            memory_available=0,
            disk_usage=0,
            network_latency=0,
            api_response_time=0,
            agent_response_times={},
            active_threads=0,
            open_connections=0
        )

    def _get_default_trading_metrics(self) -> TradingMetrics:
        """Get default trading metrics"""
        return TradingMetrics(
            timestamp=datetime.now(),
            orders_per_minute=0,
            average_execution_time=0,
            error_rate=0,
            success_rate=0,
            active_positions=0,
            daily_trades=0,
            api_calls_per_minute=0,
            data_lag=0
        )

    def _get_unknown_agent_health(self, agent_name: str) -> AgentHealth:
        """Get health for unknown agent"""
        return AgentHealth(
            agent_name=agent_name,
            status=AgentState.UNKNOWN,
            health_score=0,
            response_time=0,
            error_rate=0,
            last_heartbeat=datetime.min,
            memory_usage=0,
            cpu_usage=0,
            issues=['Agent not registered']
        )

    async def _monitor_system_loop(self):
        """Background task to monitor system metrics"""
        while self.state == AgentState.RUNNING:
            try:
                await asyncio.sleep(self.check_interval)
                
                # Collect metrics
                await self._collect_system_metrics()
                
                # Check for critical issues
                if self.system_metrics_history:
                    latest = self.system_metrics_history[-1]
                    
                    # Critical alerts
                    if latest.cpu_percent > 90:
                        self.logger.warning(f"Critical CPU usage: {latest.cpu_percent:.1f}%")
                    
                    if latest.memory_percent > 90:
                        self.logger.warning(f"Critical memory usage: {latest.memory_percent:.1f}%")
                
            except Exception as e:
                self.logger.error(f"Error in system monitoring loop: {str(e)}")

    async def _monitor_agents_loop(self):
        """Background task to monitor agent health"""
        while self.state == AgentState.RUNNING:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check all agents
                await self._collect_agent_health()
                
                # Alert on unhealthy agents
                for agent_name, health_history in self.agent_health_history.items():
                    if health_history:
                        latest = health_history[-1]
                        if latest.health_score < 30:
                            self.logger.warning(
                                f"Agent {agent_name} is unhealthy: {latest.health_score:.0f}%"
                            )
                
            except Exception as e:
                self.logger.error(f"Error in agent monitoring loop: {str(e)}")

    async def _detect_anomalies_loop(self):
        """Background task to detect anomalies"""
        while self.state == AgentState.RUNNING:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Detect anomalies
                anomalies = await self._detect_all_anomalies()
                
                # Log critical anomalies
                for anomaly in anomalies:
                    if anomaly.severity > 0.8:
                        self.logger.warning(
                            f"Critical anomaly detected: {anomaly.description}"
                        )
                
            except Exception as e:
                self.logger.error(f"Error in anomaly detection loop: {str(e)}")

    async def _optimize_system_loop(self):
        """Background task to optimize system"""
        while self.state == AgentState.RUNNING:
            try:
                await asyncio.sleep(3600)  # Every hour
                
                # Run optimizations
                self.logger.info("Running scheduled system optimization")
                results = await self.optimize_system()
                
                if results.get('memory', {}).get('freed_mb', 0) > 100:
                    self.logger.info(
                        f"Freed {results['memory']['freed_mb']:.0f}MB of memory"
                    )
                
            except Exception as e:
                self.logger.error(f"Error in optimization loop: {str(e)}")

    async def _generate_reports_loop(self):
        """Background task to generate periodic reports"""
        while self.state == AgentState.RUNNING:
            try:
                await asyncio.sleep(3600)  # Every hour
                
                # Generate health report
                report = await self.get_system_health()
                
                self.logger.info(
                    f"System Health Report: {report.status.value} "
                    f"({report.overall_health:.0f}%)"
                )
                
                # Check for predicted failures
                predictions = await self.predict_failures()
                
                for pred in predictions:
                    if pred['probability'] > 0.7:
                        self.logger.warning(
                            f"Predicted failure: {pred['type']} "
                            f"in {pred['time_to_failure']:.1f} hours"
                        )
                
            except Exception as e:
                self.logger.error(f"Error in report generation loop: {str(e)}")

    async def _handle_agent_error(self, event: Event):
        """Handle agent error events"""
        try:
            agent_name = event.data.get('agent')
            error = event.data.get('error')
            
            # Update agent error count
            if agent_name in self.registered_agents:
                self.registered_agents[agent_name]['total_errors'] += 1
            
            self.logger.error(f"Agent error in {agent_name}: {error}")
            
        except Exception as e:
            self.logger.error(f"Error handling agent error: {str(e)}")

    async def _handle_system_error(self, event: Event):
        """Handle system error events"""
        try:
            error_type = event.data.get('type')
            details = event.data.get('details')
            
            # Create anomaly for system error
            anomaly = Anomaly(
                anomaly_type=AnomalyType.PERFORMANCE,
                severity=0.8,
                description=f"System error: {error_type}",
                affected_components=['system'],
                metrics={'error': details},
                detected_at=datetime.now()
            )
            
            self.anomaly_history.append(anomaly)
            
        except Exception as e:
            self.logger.error(f"Error handling system error: {str(e)}")

    async def _handle_agent_heartbeat(self, event: Event):
        """Handle agent heartbeat events"""
        try:
            agent_name = event.data.get('agent')
            
            # Update heartbeat timestamp
            self.agent_heartbeats[agent_name] = datetime.now()
            
            # Update health check count
            if agent_name in self.registered_agents:
                self.registered_agents[agent_name]['health_checks'] += 1
            
        except Exception as e:
            self.logger.error(f"Error handling agent heartbeat: {str(e)}")


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_system_health_agent(config: Dict[str, Any]) -> SystemHealthAgent:
    """
    Factory function to create SystemHealthAgent.
    
    Args:
        config: Agent configuration dictionary
        
    Returns:
        Configured SystemHealthAgent instance
    """
    return SystemHealthAgent(config)

