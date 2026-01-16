#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderP_PortfolioMgmt
Module: SpyderP03_CorrelationAnalyzer.py
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
import os
import sys
import asyncio
import warnings
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pickle
import pandas as pd
import numpy as np
from scipy import stats
from scipy.cluster.hierarchy import linkage, dendrogram, cut_tree
from scipy.spatial.distance import squareform
from sklearn.decomposition import PCA, FactorAnalysis
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
import networkx as nx
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import MarketRegime
from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import UnifiedRegimeEngine as RegimeClassifier
from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import RegimeType
from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import create_unified_regime_engine as create_regime_classifier
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager
from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import MarketRegime

                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
            elif format.lower() == 'pickle':
                with open(file_path, 'wb') as f:
                    pickle.dump(export_data, f)
            elif format.lower() == 'csv':
                # Export correlation history as CSV
                df = pd.DataFrame([
                    {
                        'timestamp': metrics.timestamp,
                        'average_correlation': metrics.average_correlation,
                        'max_correlation': metrics.max_correlation,
                        'diversification_ratio': metrics.diversification_ratio,
                        'regime': metrics.regime.value
                    }
                    for metrics in self.correlation_history
                ])
                df.to_csv(file_path, index=False)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            self.logger.info(f"Correlation data exported to {file_path}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to export correlation data to {file_path}")
            return False

    def import_correlation_data(self, file_path: str, format: str = 'json') -> bool:
        """
        Import correlation analysis data from file.
        
        Args:
            file_path: Path to the data file
            format: Import format ('json', 'pickle')
            
        Returns:
            Success status
        """
        try:
            if format.lower() == 'json':
                import json
                with open(file_path, 'r') as f:
                    import_data = json.load(f)
            elif format.lower() == 'pickle':
                with open(file_path, 'rb') as f:
                    import_data = pickle.load(f)
            else:
                raise ValueError(f"Unsupported import format: {format}")
            
            # Reconstruct correlation history
            for hist_data in import_data.get('correlation_history', []):
                metrics = CorrelationMetrics(
                    correlation_matrix=np.array(hist_data['correlation_matrix']),
                    average_correlation=hist_data['average_correlation'],
                    max_correlation=hist_data['max_correlation'],
                    min_correlation=hist_data.get('min_correlation', 0.0),
                    correlation_dispersion=hist_data.get('correlation_dispersion', 0.0),
                    eigenvalues=np.array(hist_data.get('eigenvalues', [])),
                    condition_number=hist_data.get('condition_number', 1.0),
                    diversification_ratio=hist_data['diversification_ratio'],
                    concentration_index=hist_data.get('concentration_index', 0.0),
                    regime=CorrelationRegime(hist_data['regime']),
                    timestamp=datetime.fromisoformat(hist_data['timestamp'])
                )
                self.correlation_history.append(metrics)
            
            self.logger.info(f"Correlation data imported from {file_path}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to import correlation data from {file_path}")
            return False

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def create_correlation_analyzer(config: Optional[Dict[str, Any]] = None) -> CorrelationAnalyzer:
    """
    Factory function to create a CorrelationAnalyzer instance.
    
    Args:
        config: Configuration parameters
        
    Returns:
        Configured CorrelationAnalyzer instance
    """
    return CorrelationAnalyzer(config)

def calculate_pairwise_correlation(returns1: pd.Series, returns2: pd.Series,
                                 method: str = 'pearson') -> float:
    """
    Calculate correlation between two return series.
    
    Args:
        returns1: First return series
        returns2: Second return series
        method: Correlation method ('pearson', 'spearman', 'kendall')
        
    Returns:
        Correlation coefficient
    """
    try:
        # Align series
        aligned_data = pd.DataFrame({'series1': returns1, 'series2': returns2}).dropna()
        
        if len(aligned_data) < 2:
            return 0.0
        
        return aligned_data['series1'].corr(aligned_data['series2'], method=method)
        
    except Exception:
        return 0.0

def detect_correlation_regime_simple(correlation_matrix: np.ndarray) -> CorrelationRegime:
    """
    Simple correlation regime detection utility.
    
    Args:
        correlation_matrix: Correlation matrix
        
    Returns:
        Detected correlation regime
    """
    try:
        # Calculate average off-diagonal correlation
        mask = ~np.eye(correlation_matrix.shape[0], dtype=bool)
        avg_correlation = np.mean(np.abs(correlation_matrix[mask]))
        
        if avg_correlation >= EXTREME_CORRELATION_THRESHOLD:
            return CorrelationRegime.CRISIS_CORRELATION
        elif avg_correlation >= HIGH_CORRELATION_THRESHOLD:
            return CorrelationRegime.HIGH_CORRELATION
        elif avg_correlation >= DIVERSIFICATION_THRESHOLD:
            return CorrelationRegime.NORMAL_CORRELATION
        else:
            return CorrelationRegime.LOW_CORRELATION
            
    except Exception:
        return CorrelationRegime.NORMAL_CORRELATION

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Global correlation analyzer instance
_global_correlation_analyzer: Optional[CorrelationAnalyzer] = None

def get_global_correlation_analyzer() -> Optional[CorrelationAnalyzer]:
    """Get global correlation analyzer instance"""
    return _global_correlation_analyzer

def set_global_correlation_analyzer(analyzer: CorrelationAnalyzer) -> None:
    """Set global correlation analyzer instance"""
    global _global_correlation_analyzer
    _global_correlation_analyzer = analyzer

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code
    print("=" * 80)
    print("SPYDER P03 - Correlation Analyzer Test")
    print("=" * 80)
    
    # Create analyzer
    analyzer = CorrelationAnalyzer()
    
    # Test data generation
    print("\n1. Generating Test Data...")
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=252, freq='D')
    
    # Generate correlated strategy returns
    base_returns = np.random.normal(0.0005, 0.02, 252)
    
    strategy_returns = {
        'strategy_1': pd.Series(base_returns + np.random.normal(0, 0.01, 252), index=dates),
        'strategy_2': pd.Series(0.8 * base_returns + np.random.normal(0, 0.01, 252), index=dates),
        'strategy_3': pd.Series(0.3 * base_returns + np.random.normal(0, 0.015, 252), index=dates),
        'strategy_4': pd.Series(-0.2 * base_returns + np.random.normal(0, 0.012, 252), index=dates)
    }
    
    print(f"Generated returns for {len(strategy_returns)} strategies over {len(dates)} days")
    
    # Test correlation analysis
    print("\n2. Testing Correlation Analysis...")
    
    async def run_tests():
        # Basic correlation analysis
        metrics = await analyzer.analyze_portfolio_correlations(strategy_returns)
        print(f"Average correlation: {metrics.average_correlation:.3f}")
        print(f"Diversification ratio: {metrics.diversification_ratio:.3f}")
        print(f"Current regime: {metrics.regime.value}")
        
        # Rolling correlation analysis
        rolling_results = await analyzer.calculate_rolling_correlations(60)
        print(f"Rolling correlations calculated for {len(rolling_results)} pairs")
        
        # Correlation forecasting
        if rolling_results:
            first_pair = list(rolling_results.keys())[0]
            forecast = await analyzer.forecast_correlations(first_pair, horizon=10)
            if forecast:
                print(f"Forecast generated for {first_pair}: confidence={forecast.model_confidence:.3f}")
        
        # Cluster analysis
        cluster_result = await analyzer.perform_cluster_analysis()
        if cluster_result:
            print(f"Cluster analysis: {len(cluster_result.clusters)} clusters found")
            print(f"Silhouette score: {cluster_result.silhouette_score:.3f}")
        
        # Factor analysis
        factor_result = await analyzer.perform_factor_analysis(n_factors=2)
        if factor_result:
            print(f"Factor analysis: common factor risk={factor_result.common_factor_risk:.3f}")
        
        # Anomaly detection
        anomalies = await analyzer.detect_correlation_anomalies()
        print(f"Anomaly detection: {len(anomalies)} anomalies found")
        
        # Generate comprehensive report
        report = await analyzer.generate_correlation_report()
        print(f"Report generated with {len(report.get('recommendations', []))} recommendations")
    
    # Run async tests
    import asyncio
    asyncio.run(run_tests())
    
    # Test utility functions
    print("\n3. Testing Utility Functions...")
    
    # Test pairwise correlation
    corr = calculate_pairwise_correlation(
        strategy_returns['strategy_1'], 
        strategy_returns['strategy_2']
    )
    print(f"Pairwise correlation: {corr:.3f}")
    
    # Test simple regime detection
    test_matrix = np.array([[1.0, 0.8, 0.6], [0.8, 1.0, 0.7], [0.6, 0.7, 1.0]])
    regime = detect_correlation_regime_simple(test_matrix)
    print(f"Simple regime detection: {regime.value}")
    
    # Test data export/import
    print("\n4. Testing Data Export/Import...")
    export_success = analyzer.export_correlation_data("test_correlation_data.json", "json")
    print(f"Export successful: {export_success}")
    
    if export_success:
        # Clear data and reimport
        analyzer.correlation_history.clear()
        import_success = analyzer.import_correlation_data("test_correlation_data.json", "json")
        print(f"Import successful: {import_success}")
        print(f"Correlation history restored: {len(analyzer.correlation_history)} entries")
        
        # Clean up test file
        import os
        try:
            os.remove("test_correlation_data.json")
            print("Test file cleaned up")
        except:
            pass
    
    # Test summary functions
    print("\n5. Testing Summary Functions...")
    summary = analyzer.get_correlation_summary()
    print(f"Summary generated with {len(summary)} fields")
    
    if strategy_returns:
        profile = analyzer.get_strategy_correlation_profile('strategy_1')
        print(f"Strategy profile: avg_correlation={profile.get('average_correlation', 0):.3f}")
    
    print("\n✅ Correlation Analyzer test completed successfully")
    
    # Demonstrate integration examples
    print("\n" + "=" * 80)
    print("INTEGRATION EXAMPLES")
    print("=" * 80)
    
    print("\n1. Real-time Monitoring Setup...")
    print("# To start real-time monitoring:")
    print("# await analyzer.start_real_time_monitoring(update_frequency=300)")
    print("# This will continuously monitor correlations every 5 minutes")
    
    print("\n2. Integration with Portfolio Manager...")
    print("# Update strategy returns from portfolio:")
    print("# analyzer.update_strategy_returns('new_strategy', returns_series)")
    print("# Get active correlation alerts:")
    print(f"# Active alerts: {len(analyzer.get_active_alerts(24))}")
    
    print("\n3. Risk Management Integration...")
    print("# Check current correlation regime for risk decisions:")
    print(f"# Current regime: {analyzer.current_regime.value}")
    print("# Get correlation-based recommendations:")
    
    example_recommendations = [
        "Monitor correlation spikes during market stress",
        "Implement dynamic position sizing based on correlation regime", 
        "Use correlation forecasts for proactive risk management",
        "Set up automated alerts for correlation threshold breaches",
        "Integrate cluster analysis for strategy grouping"
    ]
    
    print("Risk management recommendations:")
    for rec in example_recommendations:
        print(f"  • {rec}")
    
    print("\n✅ All integration examples completed successfully")
