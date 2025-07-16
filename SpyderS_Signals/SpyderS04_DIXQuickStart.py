#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderS04_DIXQuickStart.py
Group: S (Signals)
Purpose: DIX Quick Start Demo and Testing Module

Description:
    This module provides a quick start demonstration of the complete DIX 
    implementation. It showcases DIX calculation, visualization generation,
    and analysis capabilities in a simple, easy-to-run format. The module
    is designed for testing, demonstration, and quick analysis of current
    dark pool sentiment for SPY options trading decisions.

Spyder Version: 1.0
Author: Manus AI
Date Created: 2025-07-14
Last Updated: 2025-07-15 Time: 11:45:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import argparse

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import logging

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderS_Signals.SpyderS01_DIXCalculator import SpyderDIXCalculator
    from SpyderS_Signals.SpyderS02_DIXDemo import SpyderDIXDemo
    from SpyderS_Signals.SpyderS03_DIXVisualizer import SpyderDIXVisualizer
except ImportError:
    # Fallback for standalone operation
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    SpyderLogger = logging
    
    class SpyderErrorHandler:
        def handle_error(self, error, code):
            logging.error(f"{code}: {error}")
    
    # Import from local
    from SpyderS01_DIXCalculator import SpyderDIXCalculator
    from SpyderS02_DIXDemo import SpyderDIXDemo
    from SpyderS03_DIXVisualizer import SpyderDIXVisualizer

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Display Settings
BANNER_WIDTH = 70
SECTION_WIDTH = 45
SUCCESS_SYMBOL = "✅"
ERROR_SYMBOL = "❌"
WARNING_SYMBOL = "⚠️"
INFO_SYMBOL = "📊"

# Trading Recommendations
TRADING_IMPLICATIONS = {
    'BULLISH': {
        'strategies': [
            "Call spreads or covered calls",
            "Long-biased directional trades",
            "Reduced hedging positions",
            "Selling put spreads for income"
        ],
        'risk': "Lower risk environment, but maintain stops"
    },
    'BEARISH': {
        'strategies': [
            "Put spreads or protective puts",
            "Short-biased or defensive positions",
            "Increased hedging",
            "Selling call spreads for income"
        ],
        'risk': "Higher risk environment, tighten risk management"
    },
    'NEUTRAL': {
        'strategies': [
            "Neutral strategies (straddles, strangles)",
            "Range-bound trading approaches",
            "Iron condors or butterflies",
            "Standard risk management"
        ],
        'risk': "Balanced risk, wait for directional signals"
    }
}

# ==============================================================================
# ENUMS
# ==============================================================================
class RunMode(Enum):
    """Quick start run modes"""
    QUICK = "quick"      # Minimal output
    NORMAL = "normal"    # Standard output
    DETAILED = "detailed"  # Full analysis
    TEST = "test"        # Testing mode

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class QuickStartConfig:
    """Configuration for quick start"""
    mode: RunMode
    use_demo: bool
    generate_charts: bool
    generate_report: bool
    days_back: int

@dataclass
class QuickStartResult:
    """Result of quick start execution"""
    success: bool
    dix_value: Optional[float]
    sentiment: Optional[str]
    charts_generated: List[str]
    report_path: Optional[str]
    execution_time: float

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderDIXQuickStart:
    """
    DIX Quick Start Demo and Testing Module.
    
    This class provides a simple interface to demonstrate the complete
    DIX implementation including calculation, visualization, and analysis.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        config: Quick start configuration
        calculator: DIX calculator instance
        visualizer: DIX visualizer instance
        
    Example:
        >>> quick_start = SpyderDIXQuickStart()
        >>> quick_start.run()
    """
    
    def __init__(self, config: Optional[QuickStartConfig] = None):
        """
        Initialize Quick Start module.
        
        Args:
            config: Optional configuration
        """
        self.logger = SpyderLogger.get_logger(__name__) if hasattr(SpyderLogger, 'get_logger') else logging.getLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Default configuration
        self.config = config or QuickStartConfig(
            mode=RunMode.NORMAL,
            use_demo=True,
            generate_charts=True,
            generate_report=True,
            days_back=5
        )
        
        # Initialize components
        if self.config.use_demo:
            self.calculator = SpyderDIXDemo()
            self.logger.info("Using DIX Demo calculator")
        else:
            self.calculator = SpyderDIXCalculator()
            self.logger.info("Using full DIX calculator")
            
        self.visualizer = SpyderDIXVisualizer(use_demo=self.config.use_demo)
        
        self.logger.info(f"{self.__class__.__name__} initialized")
        
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def run(self) -> QuickStartResult:
        """
        Run complete DIX quick start demonstration.
        
        Returns:
            QuickStartResult object
        """
        start_time = datetime.now()
        charts_generated = []
        report_path = None
        
        try:
            # Print banner
            self._print_banner()
            
            # Initialize components
            if not self._initialize_components():
                return QuickStartResult(
                    success=False,
                    dix_value=None,
                    sentiment=None,
                    charts_generated=[],
                    report_path=None,
                    execution_time=0
                )
            
            # Step 1: Calculate DIX
            print(f"\n{INFO_SYMBOL} Step 1: Calculating DIX...")
            print("-" * SECTION_WIDTH)
            
            results = self.calculator.run_calculation()
            
            if not results:
                print(f"{ERROR_SYMBOL} DIX calculation failed")
                return QuickStartResult(
                    success=False,
                    dix_value=None,
                    sentiment=None,
                    charts_generated=[],
                    report_path=None,
                    execution_time=(datetime.now() - start_time).total_seconds()
                )
            
            # Display results
            dix_pct = results['dix_percentage']
            sentiment = self._determine_sentiment(dix_pct)
            
            print(f"{SUCCESS_SYMBOL} DIX Calculation Complete!")
            print(f"   DIX Value: {dix_pct:.2f}%")
            print(f"   Date: {results['date']}")
            print(f"   Components: {results['num_symbols']} stocks")
            print(f"   Market Cap: ${results['total_market_cap']:,.0f}")
            print()
            
            # Display interpretation
            self._display_interpretation(dix_pct, sentiment)
            
            # Step 2: Generate visualizations
            if self.config.generate_charts:
                print(f"\n{INFO_SYMBOL} Step 2: Generating Visualizations...")
                print("-" * SECTION_WIDTH)
                
                # Component analysis
                chart_path = self.visualizer.create_component_analysis_chart(results)
                if chart_path:
                    charts_generated.append(chart_path)
                    print(f"{SUCCESS_SYMBOL} Component Analysis Chart: {os.path.basename(chart_path)}")
                
                # Dashboard
                dashboard_path = self.visualizer.create_summary_dashboard(results)
                if dashboard_path:
                    charts_generated.append(dashboard_path)
                    print(f"{SUCCESS_SYMBOL} Summary Dashboard: {os.path.basename(dashboard_path)}")
                
                # Time series (if detailed mode)
                if self.config.mode == RunMode.DETAILED:
                    try:
                        history = self.visualizer.calculate_historical_dix(
                            days_back=self.config.days_back
                        )
                        if len(history) > 1:
                            ts_path = self.visualizer.create_time_series_chart(history)
                            if ts_path:
                                charts_generated.append(ts_path)
                                print(f"{SUCCESS_SYMBOL} Time Series Chart: {os.path.basename(ts_path)}")
                    except Exception as e:
                        print(f"{WARNING_SYMBOL} Time series generation skipped: {e}")
            
            # Step 3: Generate report
            if self.config.generate_report:
                print(f"\n{INFO_SYMBOL} Step 3: Generating Analysis Report...")
                print("-" * SECTION_WIDTH)
                
                report_path = self.visualizer.generate_analysis_report(results)
                if report_path:
                    print(f"{SUCCESS_SYMBOL} Analysis Report: {os.path.basename(report_path)}")
            
            # Step 4: Show top contributors
            if self.config.mode != RunMode.QUICK:
                self._display_top_contributors(results)
            
            # Step 5: Trading implications
            self._display_trading_implications(sentiment)
            
            # Summary
            self._print_summary(charts_generated, report_path)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return QuickStartResult(
                success=True,
                dix_value=dix_pct,
                sentiment=sentiment,
                charts_generated=charts_generated,
                report_path=report_path,
                execution_time=execution_time
            )
            
        except Exception as e:
            self.logger.error(f"Quick start failed: {e}")
            self.error_handler.handle_error(e, "QUICKSTART_ERROR")
            
            return QuickStartResult(
                success=False,
                dix_value=None,
                sentiment=None,
                charts_generated=charts_generated,
                report_path=report_path,
                execution_time=(datetime.now() - start_time).total_seconds()
            )
    
    def run_test_suite(self) -> bool:
        """
        Run comprehensive test suite.
        
        Returns:
            bool: True if all tests pass
        """
        print("="*BANNER_WIDTH)
        print("DIX MODULE TEST SUITE")
        print("="*BANNER_WIDTH)
        
        all_passed = True
        
        # Test 1: Calculator initialization
        print(f"\n{INFO_SYMBOL} Test 1: Calculator Initialization")
        if self.calculator.initialize():
            print(f"{SUCCESS_SYMBOL} Calculator initialized")
        else:
            print(f"{ERROR_SYMBOL} Calculator initialization failed")
            all_passed = False
        
        # Test 2: DIX calculation
        print(f"\n{INFO_SYMBOL} Test 2: DIX Calculation")
        results = self.calculator.run_calculation()
        if results and 'dix_percentage' in results:
            print(f"{SUCCESS_SYMBOL} DIX calculated: {results['dix_percentage']:.2f}%")
        else:
            print(f"{ERROR_SYMBOL} DIX calculation failed")
            all_passed = False
        
        # Test 3: Visualizer initialization
        print(f"\n{INFO_SYMBOL} Test 3: Visualizer Initialization")
        if self.visualizer.initialize():
            print(f"{SUCCESS_SYMBOL} Visualizer initialized")
        else:
            print(f"{ERROR_SYMBOL} Visualizer initialization failed")
            all_passed = False
        
        # Test 4: Chart generation
        if results:
            print(f"\n{INFO_SYMBOL} Test 4: Chart Generation")
            chart_path = self.visualizer.create_summary_dashboard(results)
            if chart_path and os.path.exists(chart_path):
                print(f"{SUCCESS_SYMBOL} Dashboard created: {os.path.basename(chart_path)}")
            else:
                print(f"{ERROR_SYMBOL} Dashboard creation failed")
                all_passed = False
        
        # Summary
        print("\n" + "="*BANNER_WIDTH)
        if all_passed:
            print(f"{SUCCESS_SYMBOL} ALL TESTS PASSED")
        else:
            print(f"{ERROR_SYMBOL} SOME TESTS FAILED")
        print("="*BANNER_WIDTH)
        
        return all_passed
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _initialize_components(self) -> bool:
        """Initialize calculator and visualizer components."""
        try:
            if not self.calculator.initialize():
                print(f"{ERROR_SYMBOL} Calculator initialization failed")
                return False
                
            if not self.visualizer.initialize():
                print(f"{ERROR_SYMBOL} Visualizer initialization failed")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Component initialization failed: {e}")
            return False
    
    def _print_banner(self) -> None:
        """Print quick start banner."""
        print("="*BANNER_WIDTH)
        print("DIX (DARK INDEX) QUICK START DEMO")
        print("="*BANNER_WIDTH)
        print("This demo calculates the DIX using " + 
              ("major S&P 500 stocks" if self.config.use_demo else "all S&P 500 stocks"))
        print("and generates comprehensive analysis and visualizations.")
        print()
    
    def _determine_sentiment(self, dix_pct: float) -> str:
        """Determine market sentiment from DIX percentage."""
        if dix_pct > 50:
            return 'BEARISH'
        elif dix_pct < 45:
            return 'BULLISH'
        else:
            return 'NEUTRAL'
    
    def _display_interpretation(self, dix_pct: float, sentiment: str) -> None:
        """Display DIX interpretation."""
        if sentiment == 'BEARISH':
            emoji = "🔴"
            interpretation = "Higher short volume in dark pools suggests bearish sentiment"
        elif sentiment == 'BULLISH':
            emoji = "🟢"
            interpretation = "Lower short volume in dark pools suggests bullish sentiment"
        else:
            emoji = "🟡"
            interpretation = "Mixed sentiment in dark pools"
        
        print(f"Market Sentiment: {emoji} {sentiment}")
        print(f"Interpretation: {interpretation}")
    
    def _display_top_contributors(self, results: Dict) -> None:
        """Display top contributing stocks."""
        print(f"\n{INFO_SYMBOL} Top 10 Contributors to DIX")
        print("-" * SECTION_WIDTH)
        
        breakdown = results['breakdown']
        sorted_breakdown = sorted(
            breakdown.items(),
            key=lambda x: x[1]['market_cap'],
            reverse=True
        )[:10]
        
        print(f"{'Symbol':<8} {'DPI':<8} {'Weight':<8} {'Contribution':<12}")
        print("-" * 45)
        
        for symbol, data in sorted_breakdown:
            contribution = data['dpi'] * data['weight']
            print(f"{symbol:<8} {data['dpi']:<8.4f} {data['weight']:<8.4f} "
                  f"{contribution:<12.6f}")
    
    def _display_trading_implications(self, sentiment: str) -> None:
        """Display trading implications."""
        print(f"\n{INFO_SYMBOL} Trading Implications for SPY Options")
        print("-" * SECTION_WIDTH)
        
        implications = TRADING_IMPLICATIONS[sentiment]
        
        print(f"\n{sentiment} Market Conditions - Consider:")
        for strategy in implications['strategies']:
            print(f"   • {strategy}")
        
        print(f"\nRisk Note: {implications['risk']}")
        
        print("\n" + WARNING_SYMBOL + " IMPORTANT:")
        print("   • DIX is most effective for 1-5 day time horizons")
        print("   • Always combine with other analysis and risk management")
    
    def _print_summary(self, charts: List[str], report: Optional[str]) -> None:
        """Print execution summary."""
        print("\n" + "="*BANNER_WIDTH)
        print("QUICK START DEMO COMPLETE")
        print("="*BANNER_WIDTH)
        
        if charts or report:
            print("Generated Files:")
            for chart in charts:
                print(f"• {chart}")
            if report:
                print(f"• {report}")
        
        print("\nNext Steps:")
        print("1. Review the generated visualizations")
        print("2. Read the analysis report for detailed insights")
        print("3. Integrate DIX into your trading workflow")
        if self.config.use_demo:
            print("4. Consider upgrading to full S&P 500 implementation")
        
        print("\nFor more information, see DIX documentation")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up module resources."""
        self.calculator.cleanup()
        self.visualizer.cleanup()
        self.logger.info("Quick Start cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='DIX Quick Start Demo - Calculate and visualize Dark Index'
    )
    
    parser.add_argument(
        '--mode',
        type=str,
        choices=['quick', 'normal', 'detailed', 'test'],
        default='normal',
        help='Run mode (default: normal)'
    )
    
    parser.add_argument(
        '--full',
        action='store_true',
        help='Use full S&P 500 calculation instead of demo'
    )
    
    parser.add_argument(
        '--no-charts',
        action='store_true',
        help='Skip chart generation'
    )
    
    parser.add_argument(
        '--no-report',
        action='store_true',
        help='Skip report generation'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=5,
        help='Days of history for time series (default: 5)'
    )
    
    return parser.parse_args()

def main() -> None:
    """Main execution function."""
    # Parse arguments
    args = parse_arguments()
    
    # Create configuration
    config = QuickStartConfig(
        mode=RunMode(args.mode),
        use_demo=not args.full,
        generate_charts=not args.no_charts,
        generate_report=not args.no_report,
        days_back=args.days
    )
    
    # Run quick start
    quick_start = SpyderDIXQuickStart(config)
    
    try:
        if config.mode == RunMode.TEST:
            # Run test suite
            success = quick_start.run_test_suite()
            sys.exit(0 if success else 1)
        else:
            # Run normal demo
            result = quick_start.run()
            
            if result.success:
                print(f"\n{SUCCESS_SYMBOL} Execution completed in "
                      f"{result.execution_time:.1f} seconds")
                sys.exit(0)
            else:
                print(f"\n{ERROR_SYMBOL} Execution failed")
                sys.exit(1)
                
    except KeyboardInterrupt:
        print(f"\n{WARNING_SYMBOL} Interrupted by user")
        sys.exit(130)
        
    except Exception as e:
        print(f"\n{ERROR_SYMBOL} Unexpected error: {e}")
        sys.exit(1)
        
    finally:
        quick_start.cleanup()

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module can be imported or run directly

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    main()
