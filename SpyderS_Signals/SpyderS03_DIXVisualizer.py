#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderS03_DIXVisualizer.py
Group: S (Signals)
Purpose: DIX Visualization and Analysis Tools

Description:
    This module provides comprehensive visualization and analysis tools for DIX data.
    It creates time series charts, component analysis visualizations, dashboards,
    and automated reports. The module integrates with both full and demo DIX
    calculators to provide visual insights into dark pool sentiment for SPY
    options trading decisions.

Spyder Version: 1.0
Author: Manus AI
Date Created: 2025-07-14
Last Updated: 2025-07-15 Time: 11:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import json
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import seaborn as sns
import logging

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderS_Signals.SpyderS01_DIXCalculator import SpyderDIXCalculator, DIXResult
    from SpyderS_Signals.SpyderS02_DIXDemo import SpyderDIXDemo
except ImportError:
    # Fallback for standalone operation
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    SpyderLogger = logging
    
    class SpyderErrorHandler:
        def handle_error(self, error, code):
            logging.error(f"{code}: {error}")
    
    # Import from local
    from SpyderS01_DIXCalculator import SpyderDIXCalculator, DIXResult
    from SpyderS02_DIXDemo import SpyderDIXDemo

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Visualization Settings
DEFAULT_FIGURE_SIZE = (16, 10)
DEFAULT_DPI = 300
DEFAULT_STYLE = 'seaborn-v0_8'

# Color Schemes
DIX_COLORS = {
    'bullish': '#2ECC71',      # Green
    'neutral': '#F39C12',      # Orange
    'bearish': '#E74C3C',      # Red
    'primary': '#2E86AB',      # Blue
    'secondary': '#A23B72',    # Purple
    'background': '#F8F8F8',   # Light gray
    'grid': '#E0E0E0'          # Gray
}

# DIX Thresholds
DIX_BEARISH_THRESHOLD = 50.0
DIX_NEUTRAL_THRESHOLD = 45.0
DIX_STRONG_BEARISH = 53.0
DIX_STRONG_BULLISH = 42.0

# Chart Defaults
MAX_SYMBOLS_TO_SHOW = 15
DEFAULT_SAVE_PATH = '/home/ubuntu/spyder_dix_charts/'

# ==============================================================================
# ENUMS
# ==============================================================================
class ChartType(Enum):
    """Available chart types"""
    TIME_SERIES = "time_series"
    COMPONENT_ANALYSIS = "component_analysis"
    DASHBOARD = "dashboard"
    DISTRIBUTION = "distribution"
    HEATMAP = "heatmap"

class ReportFormat(Enum):
    """Report output formats"""
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    JSON = "json"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ChartConfig:
    """Configuration for chart generation"""
    type: ChartType
    title: str
    figure_size: Tuple[int, int]
    dpi: int
    save_path: str
    show_legend: bool
    show_grid: bool
    
@dataclass
class VisualizationResult:
    """Result of visualization generation"""
    chart_type: ChartType
    file_path: str
    creation_time: datetime
    metadata: Dict[str, Any]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderDIXVisualizer:
    """
    DIX Visualization and Analysis Tools.
    
    This class provides comprehensive visualization capabilities for DIX data,
    including time series analysis, component breakdowns, dashboards, and
    automated report generation.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        calculator: DIX calculator instance
        results_history: Historical calculation results
        
    Example:
        >>> visualizer = SpyderDIXVisualizer()
        >>> visualizer.initialize()
        >>> dashboard = visualizer.create_dashboard(results)
    """
    
    def __init__(self, use_demo: bool = True):
        """
        Initialize the DIX Visualizer.
        
        Args:
            use_demo: Use demo calculator (True) or full calculator (False)
        """
        self.logger = SpyderLogger.get_logger(__name__) if hasattr(SpyderLogger, 'get_logger') else logging.getLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Initialize calculator
        if use_demo:
            self.calculator = SpyderDIXDemo()
            self.logger.info("Using DIX Demo calculator")
        else:
            self.calculator = SpyderDIXCalculator()
            self.logger.info("Using full DIX calculator")
        
        self.results_history = []
        
        # Configure matplotlib
        plt.style.use(DEFAULT_STYLE)
        warnings.filterwarnings('ignore')
        
        # Create output directory if needed
        os.makedirs(DEFAULT_SAVE_PATH, exist_ok=True)
        
        self.logger.info(f"{self.__class__.__name__} initialized")
        
    # ==========================================================================
    # PUBLIC METHODS - INITIALIZATION
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize visualizer components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing DIX Visualizer...")
            
            # Initialize calculator
            if not self.calculator.initialize():
                raise Exception("Calculator initialization failed")
            
            self.logger.info("DIX Visualizer initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Visualizer initialization failed: {e}")
            self.error_handler.handle_error(e, "VIZ_INIT_ERROR")
            return False
    
    # ==========================================================================
    # PUBLIC METHODS - CHART GENERATION
    # ==========================================================================
    def create_time_series_chart(self, results_history: Optional[List[Dict]] = None,
                               save_path: Optional[str] = None) -> Optional[str]:
        """
        Create DIX time series chart.
        
        Args:
            results_history: List of historical results (None to calculate)
            save_path: Path to save chart
            
        Returns:
            Path to saved chart or None
        """
        try:
            # Get historical data if not provided
            if results_history is None:
                results_history = self.calculate_historical_dix(days_back=10)
            
            if not results_history:
                raise ValueError("No historical data available")
            
            # Prepare data
            dates = []
            dix_values = []
            
            for result in results_history:
                if isinstance(result, dict):
                    dates.append(result.get('date_obj', datetime.strptime(result['date'], '%Y%m%d')))
                    dix_values.append(result['dix_percentage'])
                else:
                    dates.append(datetime.strptime(result.date, '%Y%m%d'))
                    dix_values.append(result.dix_percentage)
            
            # Sort by date
            sorted_data = sorted(zip(dates, dix_values))
            dates, dix_values = zip(*sorted_data)
            
            # Create chart
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # Plot DIX line
            ax.plot(dates, dix_values, marker='o', linewidth=2.5, markersize=8,
                   color=DIX_COLORS['primary'], label='DIX (%)')
            
            # Add threshold lines
            ax.axhline(y=DIX_BEARISH_THRESHOLD, color=DIX_COLORS['bearish'],
                      linestyle='--', alpha=0.7, label='Bearish (>50%)')
            ax.axhline(y=DIX_NEUTRAL_THRESHOLD, color=DIX_COLORS['neutral'],
                      linestyle='--', alpha=0.7, label='Neutral (45%)')
            
            # Fill zones
            ax.fill_between(dates, dix_values, DIX_BEARISH_THRESHOLD,
                          where=[d >= DIX_BEARISH_THRESHOLD for d in dix_values],
                          color=DIX_COLORS['bearish'], alpha=0.2)
            ax.fill_between(dates, dix_values, DIX_NEUTRAL_THRESHOLD,
                          where=[(d >= DIX_NEUTRAL_THRESHOLD and d < DIX_BEARISH_THRESHOLD) 
                                for d in dix_values],
                          color=DIX_COLORS['neutral'], alpha=0.2)
            ax.fill_between(dates, dix_values, 0,
                          where=[d < DIX_NEUTRAL_THRESHOLD for d in dix_values],
                          color=DIX_COLORS['bullish'], alpha=0.2)
            
            # Formatting
            ax.set_title('DIX (Dark Index) Time Series\nS&P 500 Dark Pool Sentiment',
                        fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Date', fontsize=12, fontweight='bold')
            ax.set_ylabel('DIX (%)', fontsize=12, fontweight='bold')
            
            # Format axes
            ax.set_ylim(35, 65)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1f}%'))
            ax.grid(True, alpha=0.3, color=DIX_COLORS['grid'])
            
            # Add latest value annotation
            latest_date = dates[-1]
            latest_value = dix_values[-1]
            ax.annotate(f'Latest: {latest_value:.2f}%',
                       xy=(latest_date, latest_value),
                       xytext=(10, 10), textcoords='offset points',
                       bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                       arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
            
            # Legend and layout
            ax.legend(loc='upper right', frameon=True, fancybox=True, shadow=True)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Save
            if save_path is None:
                save_path = os.path.join(DEFAULT_SAVE_PATH, 'dix_time_series.png')
            
            plt.savefig(save_path, dpi=DEFAULT_DPI, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"Time series chart saved to {save_path}")
            return save_path
            
        except Exception as e:
            self.logger.error(f"Time series chart creation failed: {e}")
            self.error_handler.handle_error(e, "VIZ_TIMESERIES_ERROR")
            return None
    
    def create_component_analysis_chart(self, results: Dict,
                                      save_path: Optional[str] = None) -> Optional[str]:
        """
        Create component analysis chart.
        
        Args:
            results: DIX calculation results
            save_path: Path to save chart
            
        Returns:
            Path to saved chart or None
        """
        try:
            breakdown = results.get('breakdown', {})
            if not breakdown:
                raise ValueError("No breakdown data available")
            
            # Prepare data
            symbols = list(breakdown.keys())
            dpi_values = [breakdown[s]['dpi'] for s in symbols]
            weights = [breakdown[s]['weight'] for s in symbols]
            contributions = [breakdown[s]['dpi'] * breakdown[s]['weight'] for s in symbols]
            market_caps = [breakdown[s]['market_cap'] for s in symbols]
            
            # Sort by contribution
            sorted_data = sorted(zip(symbols, dpi_values, weights, contributions, market_caps),
                               key=lambda x: x[3], reverse=True)
            
            # Limit to top N
            sorted_data = sorted_data[:MAX_SYMBOLS_TO_SHOW]
            symbols, dpi_values, weights, contributions, market_caps = zip(*sorted_data)
            
            # Create figure with subplots
            fig = plt.figure(figsize=DEFAULT_FIGURE_SIZE)
            gs = GridSpec(2, 2, figure=fig)
            
            # 1. DPI by Symbol
            ax1 = fig.add_subplot(gs[0, 0])
            colors = [DIX_COLORS['bearish'] if d > 0.5 else 
                     DIX_COLORS['neutral'] if d > 0.45 else 
                     DIX_COLORS['bullish'] for d in dpi_values]
            
            ax1.bar(symbols, [d*100 for d in dpi_values], color=colors)
            ax1.set_title('Dark Pool Indicator by Symbol', fontsize=14, fontweight='bold')
            ax1.set_ylabel('DPI (%)')
            ax1.tick_params(axis='x', rotation=45)
            ax1.axhline(y=50, color=DIX_COLORS['bearish'], linestyle='--', alpha=0.7)
            ax1.axhline(y=45, color=DIX_COLORS['neutral'], linestyle='--', alpha=0.7)
            ax1.grid(True, alpha=0.3)
            
            # 2. Market Cap Weights
            ax2 = fig.add_subplot(gs[0, 1])
            colors = plt.cm.Set3(np.linspace(0, 1, len(symbols)))
            ax2.pie(weights, labels=symbols, autopct='%1.1f%%',
                   colors=colors, startangle=90)
            ax2.set_title('Market Cap Weights', fontsize=14, fontweight='bold')
            
            # 3. Contribution to DIX
            ax3 = fig.add_subplot(gs[1, 0])
            ax3.barh(symbols, [c*100 for c in contributions], color='steelblue')
            ax3.set_title('Contribution to DIX (%)', fontsize=14, fontweight='bold')
            ax3.set_xlabel('Contribution (%)')
            ax3.grid(True, alpha=0.3)
            
            # 4. Market Cap vs DPI Scatter
            ax4 = fig.add_subplot(gs[1, 1])
            scatter = ax4.scatter([m/1e12 for m in market_caps], [d*100 for d in dpi_values],
                                s=[w*1000 for w in weights], alpha=0.6,
                                c=contributions, cmap='RdYlGn_r')
            ax4.set_title('Market Cap vs DPI', fontsize=14, fontweight='bold')
            ax4.set_xlabel('Market Cap (Trillions $)')
            ax4.set_ylabel('DPI (%)')
            ax4.grid(True, alpha=0.3)
            
            # Colorbar
            cbar = plt.colorbar(scatter, ax=ax4)
            cbar.set_label('Contribution to DIX')
            
            # Overall title
            fig.suptitle(f'DIX Component Analysis - {results["date"]}\n'
                        f'DIX: {results["dix_percentage"]:.2f}% ({results["num_symbols"]} components)',
                        fontsize=16, fontweight='bold')
            
            plt.tight_layout()
            
            # Save
            if save_path is None:
                save_path = os.path.join(DEFAULT_SAVE_PATH, 'dix_component_analysis.png')
            
            plt.savefig(save_path, dpi=DEFAULT_DPI, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"Component analysis chart saved to {save_path}")
            return save_path
            
        except Exception as e:
            self.logger.error(f"Component analysis chart creation failed: {e}")
            self.error_handler.handle_error(e, "VIZ_COMPONENT_ERROR")
            return None
    
    def create_summary_dashboard(self, results: Dict,
                               save_path: Optional[str] = None) -> Optional[str]:
        """
        Create comprehensive DIX dashboard.
        
        Args:
            results: DIX calculation results
            save_path: Path to save dashboard
            
        Returns:
            Path to saved dashboard or None
        """
        try:
            fig = plt.figure(figsize=DEFAULT_FIGURE_SIZE)
            gs = GridSpec(3, 4, hspace=0.3, wspace=0.3)
            
            # 1. DIX Gauge (top left, 2x2)
            ax_gauge = fig.add_subplot(gs[0:2, 0:2])
            self._create_dix_gauge(ax_gauge, results['dix'])
            
            # 2. Key Metrics (top right)
            ax_metrics = fig.add_subplot(gs[0, 2:])
            self._create_metrics_panel(ax_metrics, results)
            
            # 3. Top Contributors (middle right)
            ax_contributors = fig.add_subplot(gs[1, 2:])
            self._create_top_contributors(ax_contributors, results)
            
            # 4. DPI Distribution (bottom left)
            ax_dist = fig.add_subplot(gs[2, 0:2])
            self._create_dpi_distribution(ax_dist, results)
            
            # 5. Sentiment Indicator (bottom right)
            ax_sentiment = fig.add_subplot(gs[2, 2:])
            self._create_sentiment_indicator(ax_sentiment, results)
            
            # Overall title
            fig.suptitle(f'DIX (Dark Index) Dashboard - {results["date"]}',
                        fontsize=20, fontweight='bold')
            
            # Save
            if save_path is None:
                save_path = os.path.join(DEFAULT_SAVE_PATH, 'dix_dashboard.png')
            
            plt.savefig(save_path, dpi=DEFAULT_DPI, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"Dashboard saved to {save_path}")
            return save_path
            
        except Exception as e:
            self.logger.error(f"Dashboard creation failed: {e}")
            self.error_handler.handle_error(e, "VIZ_DASHBOARD_ERROR")
            return None
    
    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    def calculate_historical_dix(self, days_back: int = 10) -> List[Dict]:
        """
        Calculate historical DIX values.
        
        Args:
            days_back: Number of days to calculate
            
        Returns:
            List of calculation results
        """
        self.logger.info(f"Calculating historical DIX for {days_back} days...")
        
        historical_results = []
        current_date = datetime.now()
        
        for i in range(days_back):
            # Calculate date (skip weekends)
            target_date = current_date - timedelta(days=i)
            while target_date.weekday() >= 5:  # Skip weekends
                target_date -= timedelta(days=1)
            
            date_str = target_date.strftime('%Y%m%d')
            
            try:
                self.logger.info(f"Calculating DIX for {date_str}...")
                results = self.calculator.run_calculation(date_str)
                
                if results:
                    results['date_obj'] = target_date
                    historical_results.append(results)
                    
            except Exception as e:
                self.logger.warning(f"Could not calculate DIX for {date_str}: {e}")
                continue
        
        self.results_history = historical_results
        self.logger.info(f"Calculated DIX for {len(historical_results)} dates")
        
        return historical_results
    
    def generate_analysis_report(self, results: Dict,
                               format: ReportFormat = ReportFormat.MARKDOWN,
                               save_path: Optional[str] = None) -> Optional[str]:
        """
        Generate comprehensive analysis report.
        
        Args:
            results: DIX calculation results
            format: Report format
            save_path: Path to save report
            
        Returns:
            Path to saved report or None
        """
        try:
            if format == ReportFormat.MARKDOWN:
                report_content = self._generate_markdown_report(results)
                extension = '.md'
            elif format == ReportFormat.JSON:
                report_content = json.dumps(results, indent=2, default=str)
                extension = '.json'
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            # Save report
            if save_path is None:
                filename = f'dix_analysis_report_{results["date"]}{extension}'
                save_path = os.path.join(DEFAULT_SAVE_PATH, filename)
            
            with open(save_path, 'w') as f:
                f.write(report_content)
            
            self.logger.info(f"Analysis report saved to {save_path}")
            return save_path
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            self.error_handler.handle_error(e, "VIZ_REPORT_ERROR")
            return None
    
    # ==========================================================================
    # PRIVATE METHODS - CHART COMPONENTS
    # ==========================================================================
    def _create_dix_gauge(self, ax, dix_value: float) -> None:
        """Create gauge visualization for DIX value."""
        # Create gauge arc
        theta = np.linspace(0, np.pi, 100)
        
        # Color zones
        zones = [
            (0, DIX_NEUTRAL_THRESHOLD/100, DIX_COLORS['bullish']),
            (DIX_NEUTRAL_THRESHOLD/100, DIX_BEARISH_THRESHOLD/100, DIX_COLORS['neutral']),
            (DIX_BEARISH_THRESHOLD/100, 1.0, DIX_COLORS['bearish'])
        ]
        
        for start, end, color in zones:
            mask = (theta >= start * np.pi) & (theta <= end * np.pi)
            ax.fill_between(theta[mask], 0, 1, color=color, alpha=0.3)
        
        # DIX needle
        dix_angle = dix_value * np.pi
        ax.plot([dix_angle, dix_angle], [0, 0.8], 'k-', linewidth=4)
        ax.plot(dix_angle, 0.8, 'ko', markersize=10)
        
        # Formatting
        ax.set_ylim(0, 1)
        ax.set_xlim(0, np.pi)
        ax.set_title(f'DIX: {dix_value*100:.2f}%', fontsize=16, fontweight='bold')
        ax.set_xticks([0, np.pi/4, np.pi/2, 3*np.pi/4, np.pi])
        ax.set_xticklabels(['0%', '25%', '50%', '75%', '100%'])
        ax.set_yticks([])
        ax.grid(True, alpha=0.3)
    
    def _create_metrics_panel(self, ax, results: Dict) -> None:
        """Create key metrics panel."""
        ax.axis('off')
        
        metrics = [
            ('DIX Value', f'{results["dix_percentage"]:.2f}%'),
            ('Components', f'{results["num_symbols"]}'),
            ('Market Cap', f'${results["total_market_cap"]/1e12:.1f}T'),
            ('Date', results['date'])
        ]
        
        for i, (label, value) in enumerate(metrics):
            ax.text(0, 0.8 - i*0.2, f'{label}:', fontsize=12, fontweight='bold')
            ax.text(0.5, 0.8 - i*0.2, value, fontsize=12)
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title('Key Metrics', fontsize=14, fontweight='bold')
    
    def _create_top_contributors(self, ax, results: Dict) -> None:
        """Create top contributors chart."""
        breakdown = results['breakdown']
        
        # Get top 5 contributors
        sorted_items = sorted(breakdown.items(),
                            key=lambda x: x[1]['dpi'] * x[1]['weight'],
                            reverse=True)[:5]
        
        symbols = [item[0] for item in sorted_items]
        contributions = [item[1]['dpi'] * item[1]['weight'] * 100 
                        for item in sorted_items]
        
        ax.barh(symbols, contributions, color='steelblue')
        ax.set_title('Top 5 Contributors', fontsize=14, fontweight='bold')
        ax.set_xlabel('Contribution (%)')
        ax.grid(True, alpha=0.3)
    
    def _create_dpi_distribution(self, ax, results: Dict) -> None:
        """Create DPI distribution histogram."""
        breakdown = results['breakdown']
        dpi_values = [data['dpi'] * 100 for data in breakdown.values()]
        
        ax.hist(dpi_values, bins=15, alpha=0.7, color='skyblue', edgecolor='black')
        ax.axvline(x=50, color=DIX_COLORS['bearish'], linestyle='--', 
                  label='Bearish (>50%)')
        ax.axvline(x=45, color=DIX_COLORS['neutral'], linestyle='--', 
                  label='Neutral (45-50%)')
        ax.axvline(x=np.mean(dpi_values), color='blue', linestyle='-', 
                  linewidth=2, label='Mean')
        
        ax.set_title('DPI Distribution', fontsize=14, fontweight='bold')
        ax.set_xlabel('DPI (%)')
        ax.set_ylabel('Count')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    def _create_sentiment_indicator(self, ax, results: Dict) -> None:
        """Create sentiment indicator."""
        ax.axis('off')
        
        dix_pct = results['dix_percentage']
        
        if dix_pct > DIX_BEARISH_THRESHOLD:
            sentiment = 'BEARISH'
            color = DIX_COLORS['bearish']
            emoji = '🔴'
        elif dix_pct > DIX_NEUTRAL_THRESHOLD:
            sentiment = 'NEUTRAL'
            color = DIX_COLORS['neutral']
            emoji = '🟡'
        else:
            sentiment = 'BULLISH'
            color = DIX_COLORS['bullish']
            emoji = '🟢'
        
        ax.text(0.5, 0.7, emoji, fontsize=60, ha='center')
        ax.text(0.5, 0.4, sentiment, fontsize=20, fontweight='bold',
                ha='center', color=color)
        ax.text(0.5, 0.2, f'{dix_pct:.2f}%', fontsize=16, ha='center')
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title('Market Sentiment', fontsize=14, fontweight='bold')
    
    def _generate_markdown_report(self, results: Dict) -> str:
        """Generate markdown format report."""
        dix_pct = results['dix_percentage']
        
        # Determine sentiment
        if dix_pct > DIX_BEARISH_THRESHOLD:
            sentiment = 'BEARISH'
            emoji = '🔴'
        elif dix_pct > DIX_NEUTRAL_THRESHOLD:
            sentiment = 'NEUTRAL'
            emoji = '🟡'
        else:
            sentiment = 'BULLISH'
            emoji = '🟢'
        
        report = f"""# DIX (Dark Index) Analysis Report
## Date: {results['date']}

### Executive Summary
- **DIX Value**: {results['dix_percentage']:.2f}%
- **Market Sentiment**: {emoji} {sentiment}
- **Components Analyzed**: {results['num_symbols']} stocks
- **Total Market Cap**: ${results['total_market_cap']:,.0f}

### DIX Interpretation
"""
        
        # Add interpretation based on value
        if dix_pct > DIX_STRONG_BEARISH:
            report += """
🔴 **STRONG BEARISH SIGNAL** (DIX > 53%)
- Very high dark pool short volume indicates strong bearish sentiment
- Institutional traders are heavily shorting in dark pools
- High probability of downward pressure on SPY
- **Action**: Consider aggressive hedging or put positions
"""
        elif dix_pct > DIX_BEARISH_THRESHOLD:
            report += """
🔴 **BEARISH SIGNAL** (DIX > 50%)
- Elevated dark pool short volume suggests bearish sentiment
- Institutional activity leaning negative
- Increased risk of downside moves
- **Action**: Consider defensive positioning
"""
        elif dix_pct < DIX_STRONG_BULLISH:
            report += """
🟢 **STRONG BULLISH SIGNAL** (DIX < 42%)
- Very low dark pool short volume indicates bullish sentiment
- Institutions are reducing short exposure
- High probability of upward momentum
- **Action**: Consider aggressive long positions
"""
        elif dix_pct < DIX_NEUTRAL_THRESHOLD:
            report += """
🟢 **BULLISH SIGNAL** (DIX < 45%)
- Lower dark pool short volume suggests bullish sentiment
- Reduced institutional shorting activity
- Favorable for upside moves
- **Action**: Consider call positions or reduced hedges
"""
        else:
            report += """
🟡 **NEUTRAL SIGNAL** (DIX 45-50%)
- Balanced dark pool activity
- No clear directional bias from institutions
- Market in equilibrium
- **Action**: Consider neutral strategies or wait for clearer signals
"""
        
        # Add top contributors
        breakdown = results['breakdown']
        sorted_breakdown = sorted(breakdown.items(),
                                key=lambda x: x[1]['market_cap'],
                                reverse=True)[:10]
        
        report += """
### Top 10 Contributors by Market Cap

| Symbol | DPI | Market Cap | Weight | Contribution |
|--------|-----|------------|--------|--------------|
"""
        
        for symbol, data in sorted_breakdown:
            contribution = data['dpi'] * data['weight']
            report += f"| {symbol} | {data['dpi']:.4f} | ${data['market_cap']:,.0f} | "
            report += f"{data['weight']:.4f} | {contribution:.6f} |\n"
        
        # Add statistical analysis
        dpi_values = [data['dpi'] for data in breakdown.values()]
        
        report += f"""
### Statistical Analysis

- **Mean DPI**: {np.mean(dpi_values):.4f} ({np.mean(dpi_values)*100:.2f}%)
- **Median DPI**: {np.median(dpi_values):.4f} ({np.median(dpi_values)*100:.2f}%)
- **Std Deviation**: {np.std(dpi_values):.4f}
- **Min DPI**: {np.min(dpi_values):.4f} ({np.min(dpi_values)*100:.2f}%)
- **Max DPI**: {np.max(dpi_values):.4f} ({np.max(dpi_values)*100:.2f}%)

### Trading Implications for SPY Options

Based on the current DIX reading of {dix_pct:.2f}%:

1. **Recommended Strategies**:
"""
        
        # Add strategy recommendations
        if dix_pct < DIX_NEUTRAL_THRESHOLD:
            report += """   - Bull call spreads 1-2 weeks out
   - Selling put spreads for income
   - Long calls on pullbacks
   - Reduced portfolio hedges
"""
        elif dix_pct > DIX_BEARISH_THRESHOLD:
            report += """   - Bear put spreads 1-2 weeks out
   - Buying protective puts
   - Selling call spreads
   - Increased portfolio hedges
"""
        else:
            report += """   - Iron condors or butterflies
   - Straddles/strangles for volatility
   - Calendar spreads
   - Neutral delta strategies
"""
        
        report += """
2. **Risk Management**:
   - DIX is most effective for 1-5 day time horizons
   - Always use stop losses and position sizing
   - Combine with other technical indicators
   - Monitor for divergences with price action

3. **Key Levels to Watch**:
   - DIX > 53%: Strong bearish zone
   - DIX > 50%: Bearish threshold
   - DIX 45-50%: Neutral zone
   - DIX < 45%: Bullish threshold
   - DIX < 42%: Strong bullish zone

### Methodology

- **Data Source**: FINRA Daily Short Sale Volume Files
- **Calculation**: Dollar-weighted average of Dark Pool Indicators
- **Formula**: DIX = Σ(DPI_i × MarketCap_i) / Σ(MarketCap_i)
- **Components**: """ + ('Demo mode - major stocks only' if results.get('metadata', {}).get('demo_mode') 
                           else 'Full S&P 500 constituents')
        
        report += f"""

### Disclaimer

This analysis is for informational purposes only and should not be considered financial advice. 
DIX is one indicator among many and should be used in conjunction with other analysis tools. 
Always conduct your own research and consult with qualified professionals before making trading decisions.

---
*Report generated by Spyder DIX Visualizer on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        return report
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up module resources."""
        self.results_history = []
        plt.close('all')  # Close any open plots
        self.logger.info("DIX Visualizer cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_quick_dashboard(use_demo: bool = True) -> Optional[str]:
    """
    Create a quick DIX dashboard.
    
    Args:
        use_demo: Use demo calculator
        
    Returns:
        Path to dashboard or None
    """
    try:
        visualizer = SpyderDIXVisualizer(use_demo=use_demo)
        visualizer.initialize()
        
        # Calculate current DIX
        results = visualizer.calculator.run_calculation()
        
        if results:
            return visualizer.create_summary_dashboard(results)
        
        return None
        
    except Exception as e:
        logging.error(f"Quick dashboard failed: {e}")
        return None

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_visualizer_instance: Optional[SpyderDIXVisualizer] = None

def get_visualizer_instance(use_demo: bool = True) -> SpyderDIXVisualizer:
    """
    Get singleton instance of visualizer.
    
    Args:
        use_demo: Use demo calculator
        
    Returns:
        Visualizer instance
    """
    global _visualizer_instance
    if _visualizer_instance is None:
        _visualizer_instance = SpyderDIXVisualizer(use_demo=use_demo)
        _visualizer_instance.initialize()
    return _visualizer_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("="*70)
    print("DIX VISUALIZER TEST")
    print("="*70)
    
    visualizer = SpyderDIXVisualizer(use_demo=True)
    
    if visualizer.initialize():
        print("✅ Visualizer initialized")
        
        # Calculate current DIX
        print("\n📊 Calculating current DIX...")
        results = visualizer.calculator.run_calculation()
        
        if results:
            print(f"   DIX: {results['dix_percentage']:.2f}%")
            
            # Create visualizations
            print("\n🎨 Creating visualizations...")
            
            # 1. Component analysis
            chart1 = visualizer.create_component_analysis_chart(results)
            if chart1:
                print(f"✅ Component analysis: {chart1}")
            
            # 2. Dashboard
            chart2 = visualizer.create_summary_dashboard(results)
            if chart2:
                print(f"✅ Dashboard: {chart2}")
            
            # 3. Report
            report = visualizer.generate_analysis_report(results)
            if report:
                print(f"✅ Analysis report: {report}")
            
            # 4. Time series (if historical data available)
            print("\n📈 Attempting time series...")
            try:
                history = visualizer.calculate_historical_dix(days_back=5)
                if len(history) > 1:
                    chart3 = visualizer.create_time_series_chart(history)
                    if chart3:
                        print(f"✅ Time series: {chart3}")
                else:
                    print("⚠️  Insufficient historical data")
            except Exception as e:
                print(f"⚠️  Time series failed: {e}")
        
        # Cleanup
        visualizer.cleanup()
        print("\n✅ Visualizer test completed")
    else:
        print("❌ Visualizer initialization failed")
