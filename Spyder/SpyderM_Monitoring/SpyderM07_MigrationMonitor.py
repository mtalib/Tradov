#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderM_Monitoring
Module: SpyderM07_MigrationMonitor.py
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
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import is_spyderx_enabled
import logging

DIVERGENCE_THRESHOLD = 0.1  # 10% divergence triggers alert
PERFORMANCE_WINDOW = 1000   # Number of comparisons to track

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ComparisonResult:
    """Single comparison between SpyderF and SpyderX"""
    timestamp: datetime
    module_name: str
    spyderf_result: Any
    spyderx_result: Any
    execution_time_f: float
    execution_time_x: float
    divergence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MigrationMetrics:
    """Aggregated migration metrics"""
    module_name: str
    total_comparisons: int = 0
    avg_divergence: float = 0.0
    max_divergence: float = 0.0
    avg_speedup: float = 0.0
    error_count_f: int = 0
    error_count_x: int = 0
    confidence_score: float = 0.0

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class MigrationMonitor:
    """
    Monitor and track SpyderF to SpyderX migration progress.
    
    This class provides real-time comparison between traditional and AI modules,
    tracking performance, accuracy, and reliability metrics.
    """
    
    def __init__(self):
        """Initialize migration monitor"""
        self.logger = SpyderLogger.get_logger(__name__)
        
        # Tracking storage
        self.comparisons: Dict[str, List[ComparisonResult]] = defaultdict(list)
        self.metrics: Dict[str, MigrationMetrics] = {}
        
        # Performance tracking
        self.performance_buffer = defaultdict(lambda: {
            'divergences': [],
            'speedups': [],
            'errors_f': 0,
            'errors_x': 0
        })
        
        self.logger.info("Migration monitor initialized")
    
    # ==========================================================================
    # COMPARISON METHODS
    # ==========================================================================
    def compare_analysis(
        self,
        module_name: str,
        spyderf_func: callable,
        spyderx_func: callable,
        *args,
        **kwargs
    ) -> Tuple[Any, ComparisonResult]:
        """
        Compare SpyderF and SpyderX analysis results.
        
        Args:
            module_name: Name of the module being compared
            spyderf_func: Traditional analysis function
            spyderx_func: AI analysis function
            *args, **kwargs: Arguments for both functions
            
        Returns:
            Tuple of (result, comparison_metrics)
        """
        comparison = ComparisonResult(
            timestamp=datetime.now(),
            module_name=module_name,
            spyderf_result=None,
            spyderx_result=None,
            execution_time_f=0.0,
            execution_time_x=0.0,
            divergence=0.0
        )
        
        # Run SpyderF (traditional)
        try:
            start_time = time.time()
            spyderf_result = spyderf_func(*args, **kwargs)
            comparison.execution_time_f = time.time() - start_time
            comparison.spyderf_result = spyderf_result
        except Exception as e:
            self.logger.error(f"SpyderF error in {module_name}: {e}")
            self.performance_buffer[module_name]['errors_f'] += 1
            return None, comparison
        
        # Run SpyderX if enabled
        if is_spyderx_enabled("ENABLE_SPYDERX_SHADOW"):
            try:
                start_time = time.time()
                spyderx_result = spyderx_func(*args, **kwargs)
                comparison.execution_time_x = time.time() - start_time
                comparison.spyderx_result = spyderx_result
                
                # Calculate divergence
                comparison.divergence = self._calculate_divergence(
                    spyderf_result, spyderx_result
                )
                
                # Log if significant divergence
                if comparison.divergence > DIVERGENCE_THRESHOLD:
                    self.logger.warning(
                        f"{module_name} divergence: {comparison.divergence:.2%}"
                    )
                
            except Exception as e:
                self.logger.error(f"SpyderX error in {module_name}: {e}")
                self.performance_buffer[module_name]['errors_x'] += 1
        
        # Store comparison
        self._store_comparison(comparison)
        
        # Return traditional result (safe default during migration)
        return spyderf_result, comparison
    
    def _calculate_divergence(self, result_f: Any, result_x: Any) -> float:
        """Calculate divergence between two results"""
        try:
            # Handle numeric results
            if isinstance(result_f, (int, float)) and isinstance(result_x, (int, float)):
                if result_f == 0:
                    return float('inf') if result_x != 0 else 0.0
                return abs(result_f - result_x) / abs(result_f)
            
            # Handle dict results
            elif isinstance(result_f, dict) and isinstance(result_x, dict):
                divergences = []
                for key in result_f:
                    if key in result_x:
                        div = self._calculate_divergence(result_f[key], result_x[key])
                        if div != float('inf'):
                            divergences.append(div)
                return statistics.mean(divergences) if divergences else 0.0
            
            # Handle list/array results
            elif hasattr(result_f, '__len__') and hasattr(result_x, '__len__'):
                if len(result_f) != len(result_x):
                    return 1.0  # 100% divergence for different sizes
                
                divergences = []
                for f, x in zip(result_f, result_x):
                    div = self._calculate_divergence(f, x)
                    if div != float('inf'):
                        divergences.append(div)
                return statistics.mean(divergences) if divergences else 0.0
            
            # Default: check equality
            else:
                return 0.0 if result_f == result_x else 1.0
                
        except Exception as e:
            self.logger.error(f"Error calculating divergence: {e}")
            return 1.0
    
    def _store_comparison(self, comparison: ComparisonResult):
        """Store comparison result and update metrics"""
        module = comparison.module_name
        
        # Add to comparison history
        self.comparisons[module].append(comparison)
        
        # Limit history size
        if len(self.comparisons[module]) > PERFORMANCE_WINDOW:
            self.comparisons[module].pop(0)
        
        # Update performance buffer
        if comparison.spyderx_result is not None:
            self.performance_buffer[module]['divergences'].append(comparison.divergence)
            
            if comparison.execution_time_f > 0:
                speedup = comparison.execution_time_f / comparison.execution_time_x
                self.performance_buffer[module]['speedups'].append(speedup)
        
        # Update aggregated metrics
        self._update_metrics(module)
    
    def _update_metrics(self, module_name: str):
        """Update aggregated metrics for a module"""
        if module_name not in self.metrics:
            self.metrics[module_name] = MigrationMetrics(module_name=module_name)
        
        metrics = self.metrics[module_name]
        buffer = self.performance_buffer[module_name]
        comparisons = self.comparisons[module_name]
        
        # Update counts
        metrics.total_comparisons = len(comparisons)
        metrics.error_count_f = buffer['errors_f']
        metrics.error_count_x = buffer['errors_x']
        
        # Update divergence metrics
        if buffer['divergences']:
            metrics.avg_divergence = statistics.mean(buffer['divergences'])
            metrics.max_divergence = max(buffer['divergences'])
        
        # Update speedup metrics
        if buffer['speedups']:
            metrics.avg_speedup = statistics.mean(buffer['speedups'])
        
        # Calculate confidence score
        metrics.confidence_score = self._calculate_confidence(metrics)
    
    def _calculate_confidence(self, metrics: MigrationMetrics) -> float:
        """Calculate confidence score for migration readiness"""
        if metrics.total_comparisons < 100:
            return 0.0  # Not enough data
        
        # Factors for confidence
        divergence_score = max(0, 1 - metrics.avg_divergence)
        error_score = max(0, 1 - (metrics.error_count_x / max(1, metrics.total_comparisons)))
        speedup_score = min(1, metrics.avg_speedup / 2)  # 2x speedup = full score
        
        # Weighted average
        confidence = (
            divergence_score * 0.5 +  # Accuracy is most important
            error_score * 0.3 +        # Reliability is important
            speedup_score * 0.2        # Performance is nice to have
        )
        
        return confidence
    
    # ==========================================================================
    # REPORTING METHODS
    # ==========================================================================
    def get_migration_report(self) -> Dict[str, Any]:
        """Generate comprehensive migration report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'modules': {},
            'summary': {
                'total_modules': len(self.metrics),
                'ready_for_migration': [],
                'needs_work': [],
                'critical_issues': []
            }
        }
        
        for module_name, metrics in self.metrics.items():
            module_report = {
                'comparisons': metrics.total_comparisons,
                'avg_divergence': f"{metrics.avg_divergence:.2%}",
                'max_divergence': f"{metrics.max_divergence:.2%}",
                'avg_speedup': f"{metrics.avg_speedup:.2f}x",
                'errors': {
                    'spyderf': metrics.error_count_f,
                    'spyderx': metrics.error_count_x
                },
                'confidence': f"{metrics.confidence_score:.2%}",
                'status': self._get_migration_status(metrics)
            }
            
            report['modules'][module_name] = module_report
            
            # Categorize modules
            if metrics.confidence_score >= 0.9:
                report['summary']['ready_for_migration'].append(module_name)
            elif metrics.confidence_score >= 0.7:
                report['summary']['needs_work'].append(module_name)
            else:
                report['summary']['critical_issues'].append(module_name)
        
        return report
    
    def _get_migration_status(self, metrics: MigrationMetrics) -> str:
        """Determine migration status for a module"""
        if metrics.confidence_score >= 0.9:
            return "✅ Ready for migration"
        elif metrics.confidence_score >= 0.7:
            return "⚠️ Needs tuning"
        elif metrics.confidence_score >= 0.5:
            return "❌ Not ready"
        else:
            return "🚫 Critical issues"
    
    def print_summary(self):
        """Print migration summary to console"""
        report = self.get_migration_report()
        
        logging.info("\n" + "=" * 60)
        logging.info("SPYDERX MIGRATION STATUS REPORT")
        logging.info("=" * 60)
        logging.info(f"Generated: {report['timestamp']}")
        logging.info(f"Total Modules Monitored: {report['summary']['total_modules']}")
        
        logging.info("\n📊 Module Status:")
        for module, data in report['modules'].items():
            logging.info(f"\n{module}:")
            logging.info(f"  Status: {data['status']}")
            logging.info(f"  Comparisons: {data['comparisons']}")
            logging.info(f"  Avg Divergence: {data['avg_divergence']}")
            logging.info(f"  Speedup: {data['avg_speedup']}")
            logging.info(f"  Confidence: {data['confidence']}")
        
        logging.info("\n📈 Migration Readiness:")
        logging.info(f"  ✅ Ready: {len(report['summary']['ready_for_migration'])}")
        logging.info(f"  ⚠️  Needs Work: {len(report['summary']['needs_work'])}")
        logging.info(f"  🚫 Critical Issues: {len(report['summary']['critical_issues'])}")
        
        if report['summary']['ready_for_migration']:
            logging.info(f"\n🚀 Ready for migration: {', '.join(report['summary']['ready_for_migration'])}")


# ==============================================================================
# SINGLETON INSTANCE
# ==============================================================================
_migration_monitor = None

def get_migration_monitor() -> MigrationMonitor:
    """Get singleton migration monitor instance"""
    global _migration_monitor
    if _migration_monitor is None:
        _migration_monitor = MigrationMonitor()
    return _migration_monitor
