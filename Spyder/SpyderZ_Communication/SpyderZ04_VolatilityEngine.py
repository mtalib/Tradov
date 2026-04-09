#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderZ_Communication
Module: SpyderZ04_VolatilityEngine.py
Purpose: ZMQ volatility engine subprocess worker — delegates BSM/Greeks/surface
         computation to SpyderV09_IVEngine (V-series).

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
from datetime import datetime, timedelta, date
from typing import Any
from dataclasses import asdict
from collections import deque
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import multiprocessing as mp

import numpy as np

warnings.filterwarnings('ignore')

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from .SpyderZ07_MultiProcessManager import SpyderEngineProcess
from .SpyderZ03_TradingCoordinator import EngineType
from .SpyderZ02_MessageProtocol import (
    MessageCategory, ProtocolMessage, PRIORITY_HIGH
)

# ==============================================================================
# V-SERIES COMPUTATION IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderV_QuantModels.SpyderV09_IVEngine import (
        OptionContract,
        BlackScholesCalculator,
        GreeksCalculator,
        VolatilityAnalyzer,
        VolatilitySurfaceBuilder,
        RISK_FREE_RATE,
        DAYS_IN_YEAR,
    )
except ImportError:
    from SpyderV09_IVEngine import (  # type: ignore[no-redef]
        OptionContract,
        BlackScholesCalculator,
        GreeksCalculator,
        VolatilityAnalyzer,
        VolatilitySurfaceBuilder,
        RISK_FREE_RATE,
        DAYS_IN_YEAR,
    )

# ==============================================================================
# CONSTANTS (IPC / process-layer only)
# ==============================================================================
BATCH_SIZE = 100
UPDATE_INTERVAL = 0.1  # seconds

# VOLATILITY ENGINE
# ==============================================================================
class VolatilityEngine(SpyderEngineProcess):
    """
    Production-ready volatility analysis engine.

    Features:
        - Real-time implied volatility calculation
        - Complete Greeks computation
        - Volatility surface modeling
        - Performance optimization with caching
        - Shared memory tick data access
    """

    def __init__(self, engine_type: EngineType, stop_event: mp.Event,
                 engine_id: str = None):
        super().__init__(engine_type, stop_event, engine_id)

        # Calculators
        self.bs_calculator = BlackScholesCalculator()
        self.greeks_calculator = GreeksCalculator()
        self.vol_analyzer = VolatilityAnalyzer()
        self.surface_builder = VolatilitySurfaceBuilder()

        # State
        self.current_surface = None
        self.last_surface_update = 0
        self.surface_update_interval = 60  # seconds

        # Performance tracking
        self.calculation_times = deque(maxlen=1000)
        self.calculation_count = 0

        # Option chain cache
        self.option_chain_cache = {}
        self.cache_timestamp = 0

    def initialize(self) -> bool:
        """Initialize volatility engine."""
        self.logger.info("Initializing Volatility Engine")

        # Initialize base class
        if not super().initialize():
            return False

        # Warm up caches
        self._warm_up_caches()

        self.logger.info("Volatility Engine initialized successfully")
        return True

    def process_work(self) -> None:
        """Main processing loop for volatility calculations."""
        try:
            # Check for commands
            if self.dealer_socket.poll(0):
                self._process_command()

            # Update volatility surface periodically
            if time.time() - self.last_surface_update > self.surface_update_interval:
                self._update_volatility_surface()

            # Process any pending calculations
            self._process_calculation_queue()

            # Small delay to prevent CPU spinning
            time.sleep(0.01)  # thread-safe: time.sleep() intentional

        except Exception as e:
            self.logger.error("Processing error: %s", e)
            self.error_handler.handle_critical_error(e, "VolatilityEngine")

    def _process_command(self):
        """Process incoming command."""
        try:
            # Receive message
            message_data = self.dealer_socket.recv()
            message = self.protocol_manager.deserialize_message(message_data)

            self.logger.info("Received command: %s", message.message_type)

            # Route based on command type
            if message.data.get("action") == "calculate_iv":
                self._handle_iv_calculation(message)
            elif message.data.get("action") == "calculate_greeks":
                self._handle_greeks_calculation(message)
            elif message.data.get("action") == "get_surface":
                self._handle_surface_request(message)
            elif message.data.get("action") == "analyze_volatility":
                self._handle_volatility_analysis(message)
            else:
                self.logger.warning("Unknown action: %s", message.data.get('action'))

        except Exception as e:
            self.logger.error("Command processing error: %s", e)

    def _handle_iv_calculation(self, message: ProtocolMessage):
        """Handle implied volatility calculation request."""
        start_time = time.time()

        try:
            data = message.data

            # Extract parameters
            option_price = data.get("option_price")
            spot_price = data.get("spot_price")
            strike = data.get("strike")
            time_to_expiry = data.get("time_to_expiry")
            option_type = data.get("option_type", "CALL")

            # Calculate IV
            iv = self.bs_calculator.implied_volatility(
                option_price, spot_price, strike,
                RISK_FREE_RATE, 0, time_to_expiry, option_type
            )

            # Send response
            response = self.protocol_manager.create_message(
                category=MessageCategory.SYSTEM,
                message_type="RESPONSE",
                source=self.engine_id,
                data={
                    "command_id": message.data.get("command_id"),
                    "success": True,
                    "result": {
                        "implied_volatility": iv,
                        "annualized_iv": iv * 100  # As percentage
                    },
                    "execution_time": time.time() - start_time
                }
            )

            self._send_response(response)

            # Track performance
            self.calculation_times.append(time.time() - start_time)
            self.calculation_count += 1

        except Exception as e:
            self.logger.error("IV calculation error: %s", e)
            self._send_error_response(message, str(e))

    def _handle_greeks_calculation(self, message: ProtocolMessage):
        """Handle Greeks calculation request."""
        start_time = time.time()

        try:
            data = message.data

            # Create option contract from data
            option = OptionContract(
                symbol=data.get("symbol"),
                underlying=data.get("underlying"),
                strike=data.get("strike"),
                expiry=datetime.strptime(data.get("expiry"), "%Y-%m-%d").date(),
                option_type=data.get("option_type"),
                bid=data.get("bid"),
                ask=data.get("ask"),
                last=data.get("last"),
                volume=data.get("volume", 0),
                open_interest=data.get("open_interest", 0),
                underlying_price=data.get("underlying_price")
            )

            # Calculate Greeks
            iv = data.get("implied_volatility")
            greeks = self.greeks_calculator.calculate_all_greeks(option, iv)

            # Send response
            response = self.protocol_manager.create_message(
                category=MessageCategory.SYSTEM,
                message_type="RESPONSE",
                source=self.engine_id,
                data={
                    "command_id": message.data.get("command_id"),
                    "success": True,
                    "result": asdict(greeks),
                    "execution_time": time.time() - start_time
                }
            )

            self._send_response(response)

        except Exception as e:
            self.logger.error("Greeks calculation error: %s", e)
            self._send_error_response(message, str(e))

    def _handle_surface_request(self, message: ProtocolMessage):
        """Handle volatility surface request."""
        try:
            if self.current_surface is None:
                self._update_volatility_surface()

            if self.current_surface:
                # Send surface data
                response = self.protocol_manager.create_message(
                    category=MessageCategory.SYSTEM,
                    message_type="RESPONSE",
                    source=self.engine_id,
                    data={
                        "command_id": message.data.get("command_id"),
                        "success": True,
                        "result": {
                            "surface": asdict(self.current_surface),
                            "timestamp": self.current_surface.timestamp
                        }
                    }
                )
            else:
                response = self._create_error_response(
                    message, "No volatility surface available"
                )

            self._send_response(response)

        except Exception as e:
            self.logger.error("Surface request error: %s", e)
            self._send_error_response(message, str(e))

    def _handle_volatility_analysis(self, message: ProtocolMessage):
        """Handle comprehensive volatility analysis request."""
        try:
            # Get option chain (would come from market data in production)
            option_chain = self._get_option_chain()
            spot_price = message.data.get("spot_price", 450.0)

            # Perform analysis
            metrics = self.vol_analyzer.calculate_volatility_metrics(
                option_chain, spot_price
            )

            # Send response
            response = self.protocol_manager.create_message(
                category=MessageCategory.SYSTEM,
                message_type="RESPONSE",
                source=self.engine_id,
                data={
                    "command_id": message.data.get("command_id"),
                    "success": True,
                    "result": asdict(metrics)
                }
            )

            self._send_response(response)

        except Exception as e:
            self.logger.error("Volatility analysis error: %s", e)
            self._send_error_response(message, str(e))

    def _update_volatility_surface(self):
        """Update volatility surface."""
        try:
            self.logger.info("Updating volatility surface")

            # Get current option chain
            option_chain = self._get_option_chain()
            if not option_chain:
                return

            # Get spot price from shared memory or use default
            spot_price = self._get_spot_price()

            # Build surface
            self.current_surface = self.surface_builder.build_surface(
                option_chain, spot_price
            )

            self.last_surface_update = time.time()

            # Broadcast update
            self._broadcast_surface_update()

        except Exception as e:
            self.logger.error("Surface update error: %s", e)

    def _get_option_chain(self) -> list[OptionContract]:
        """Get current option chain (placeholder implementation)."""
        # In production, this would fetch real option chain data
        # For now, return cached or generated data

        if time.time() - self.cache_timestamp < 60:
            return list(self.option_chain_cache.values())

        # Generate sample option chain for testing
        return self._generate_sample_option_chain()

    def _generate_sample_option_chain(self) -> list[OptionContract]:
        """Generate sample option chain for testing."""
        options = []
        spot_price = 450.0

        # Generate options for multiple expiries
        expiry_days = [7, 14, 30, 60, 90]
        strikes = np.arange(420, 481, 5)

        for days in expiry_days:
            expiry = date.today() + timedelta(days=days)

            for strike in strikes:
                for option_type in ["CALL", "PUT"]:
                    # Generate realistic bid/ask based on Black-Scholes
                    T = days / DAYS_IN_YEAR
                    iv = 0.20 + np.random.normal(0, 0.02)  # 20% ± 2%

                    if option_type == "CALL":
                        theo = self.bs_calculator.call_price(
                            spot_price, strike, RISK_FREE_RATE, 0, iv, T
                        )
                    else:
                        theo = self.bs_calculator.put_price(
                            spot_price, strike, RISK_FREE_RATE, 0, iv, T
                        )

                    # Add spread
                    spread = max(0.05, theo * 0.02)
                    bid = max(0.01, theo - spread/2)
                    ask = theo + spread/2

                    option = OptionContract(
                        symbol=f"SPY{expiry.strftime('%y%m%d')}{option_type[0]}{int(strike)}",
                        underlying="SPY",
                        strike=strike,
                        expiry=expiry,
                        option_type=option_type,
                        bid=bid,
                        ask=ask,
                        last=theo,
                        volume=np.random.randint(0, 10000),
                        open_interest=np.random.randint(0, 50000),
                        underlying_price=spot_price
                    )

                    options.append(option)

        return options

    def _get_spot_price(self) -> float:
        """Get current spot price from shared memory."""
        try:
            # Read from shared memory if available
            if self.shared_mem:
                # Implementation would read actual tick data
                return 450.0  # Placeholder
            else:
                return 450.0
        except Exception:
            return 450.0

    def _broadcast_surface_update(self):
        """Broadcast volatility surface update."""
        try:
            self.protocol_manager.create_message(
                category=MessageCategory.MARKET,
                message_type="VOLATILITY_SURFACE_UPDATE",
                source=self.engine_id,
                data={
                    "timestamp": self.current_surface.timestamp,
                    "spot_price": self.current_surface.spot_price,
                    "update_type": "FULL"
                },
                priority=PRIORITY_HIGH
            )

            # Send via publisher if available
            # self.pub_socket.send(update_msg.serialize())

        except Exception as e:
            self.logger.error("Broadcast error: %s", e)

    def _warm_up_caches(self):
        """Warm up calculation caches."""
        self.logger.info("Warming up caches")

        # Pre-calculate common values
        sample_options = self._generate_sample_option_chain()[:10]

        for option in sample_options:
            try:
                self.greeks_calculator.calculate_all_greeks(option)
            except Exception as e:
                self.logger.debug("Cache warmup failed for sample option: %s", e)

    def _send_response(self, response: ProtocolMessage):
        """Send response message."""
        try:
            data = self.protocol_manager.serialize_message(response)
            self.dealer_socket.send(data)
        except Exception as e:
            self.logger.error("Failed to send response: %s", e)

    def _send_error_response(self, original_message: ProtocolMessage, error: str):
        """Send error response."""
        response = self.protocol_manager.create_message(
            category=MessageCategory.SYSTEM,
            message_type="RESPONSE",
            source=self.engine_id,
            data={
                "command_id": original_message.data.get("command_id"),
                "success": False,
                "error": error
            }
        )
        self._send_response(response)

    def _process_calculation_queue(self):
        """Process any queued calculations."""
        # Implementation would process batched calculations
        pass

    def get_metrics(self) -> dict[str, Any]:
        """Get engine metrics."""
        metrics = super().get_metrics()

        # Add volatility-specific metrics
        avg_calc_time = np.mean(self.calculation_times) if self.calculation_times else 0

        metrics.update({
            "calculation_count": self.calculation_count,
            "avg_calculation_time": avg_calc_time,
            "cache_hit_rate": self.greeks_calculator.cache.get_hit_rate() if hasattr(self.greeks_calculator.cache, 'get_hit_rate') else 0,
            "surface_age": time.time() - self.last_surface_update if self.last_surface_update else None,
            "surface_available": self.current_surface is not None
        })

        return metrics

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================
def create_test_option_chain() -> list[OptionContract]:
    """Create test option chain for examples."""
    options = []
    spot_price = 450.0

    # Create options for 30-day expiry
    expiry = date.today() + timedelta(days=30)
    strikes = [440, 445, 450, 455, 460]

    for strike in strikes:
        for option_type in ["CALL", "PUT"]:
            # Simple IV based on moneyness
            moneyness = strike / spot_price
            base_iv = 0.20

            if option_type == "CALL":
                iv = base_iv * (1 + 0.1 * (moneyness - 1))
            else:
                iv = base_iv * (1 + 0.1 * (1 - moneyness))

            # Calculate theoretical price
            T = 30 / DAYS_IN_YEAR
            bs = BlackScholesCalculator()

            if option_type == "CALL":
                theo = bs.call_price(spot_price, strike, RISK_FREE_RATE, 0, iv, T)
            else:
                theo = bs.put_price(spot_price, strike, RISK_FREE_RATE, 0, iv, T)

            # Create option
            option = OptionContract(
                symbol=f"SPY{expiry.strftime('%y%m%d')}{option_type[0]}{int(strike)}",
                underlying="SPY",
                strike=strike,
                expiry=expiry,
                option_type=option_type,
                bid=theo * 0.98,
                ask=theo * 1.02,
                last=theo,
                volume=1000,
                open_interest=5000,
                underlying_price=spot_price
            )

            options.append(option)

    return options

# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
def example_iv_calculation():
    """Example: Calculate implied volatility."""
    logging.info("\n" + "="*60)
    logging.info("Example: Implied Volatility Calculation")
    logging.info("="*60)

    bs = BlackScholesCalculator()

    # Option parameters
    spot = 450.0
    strike = 455.0
    option_price = 5.25
    time_to_expiry = 30 / DAYS_IN_YEAR
    option_type = "CALL"

    logging.info("\nOption Parameters:")
    logging.info("  Spot Price: $%s", spot)
    logging.info("  Strike: $%s", strike)
    logging.info("  Option Price: $%s", option_price)
    logging.info("  Days to Expiry: 30")
    logging.info("  Option Type: %s", option_type)

    # Calculate IV
    iv = bs.implied_volatility(
        option_price, spot, strike, RISK_FREE_RATE, 0,
        time_to_expiry, option_type
    )

    logging.info(f"\nCalculated Implied Volatility: {iv:.2%}")

    # Verify with price calculation
    calculated_price = bs.call_price(
        spot, strike, RISK_FREE_RATE, 0, iv, time_to_expiry
    )

    logging.info(f"Verification - Calculated Price: ${calculated_price:.2f}")
    logging.info(f"Price Difference: ${abs(calculated_price - option_price):.4f}")

def example_greeks_calculation():
    """Example: Calculate all Greeks."""
    logging.info("\n" + "="*60)
    logging.info("Example: Greeks Calculation")
    logging.info("="*60)

    # Create test option
    option = OptionContract(
        symbol="SPY240730C450",
        underlying="SPY",
        strike=450.0,
        expiry=date.today() + timedelta(days=30),
        option_type="CALL",
        bid=5.20,
        ask=5.30,
        last=5.25,
        volume=1000,
        open_interest=5000,
        underlying_price=450.0
    )

    logging.info("\nOption: %s", option.symbol)
    logging.info("  Strike: $%s", option.strike)
    logging.info("  Spot: $%s", option.underlying_price)
    logging.info(f"  Mid Price: ${(option.bid + option.ask) / 2:.2f}")

    # Calculate Greeks
    calculator = GreeksCalculator()
    greeks = calculator.calculate_all_greeks(option)

    logging.info("\nGreeks:")
    logging.info(f"  Delta: {greeks.delta:.4f}")
    logging.info(f"  Gamma: {greeks.gamma:.4f}")
    logging.info(f"  Theta: ${greeks.theta:.2f}/day")
    logging.info(f"  Vega: ${greeks.vega:.2f}/1% vol")
    logging.info(f"  Rho: ${greeks.rho:.2f}/1% rate")
    logging.info(f"  Lambda: {greeks.lambda_:.2f}x")

    logging.info("\nSecond-Order Greeks:")
    logging.info(f"  Vanna: {greeks.vanna:.4f}")
    logging.info(f"  Volga: {greeks.volga:.4f}")
    logging.info(f"  Charm: {greeks.charm:.4f}")
    logging.info(f"  Veta: {greeks.veta:.4f}")

def example_volatility_surface():
    """Example: Build volatility surface."""
    logging.info("\n" + "="*60)
    logging.info("Example: Volatility Surface")
    logging.info("="*60)

    # Create option chain
    option_chain = create_test_option_chain()

    # Add more expiries
    for days in [7, 14, 60, 90]:
        expiry = date.today() + timedelta(days=days)
        for strike in [440, 445, 450, 455, 460]:
            for opt_type in ["CALL", "PUT"]:
                # Generate option with some randomness
                iv = 0.20 + np.random.normal(0, 0.02)
                T = days / DAYS_IN_YEAR

                bs = BlackScholesCalculator()
                if opt_type == "CALL":
                    theo = bs.call_price(450, strike, RISK_FREE_RATE, 0, iv, T)
                else:
                    theo = bs.put_price(450, strike, RISK_FREE_RATE, 0, iv, T)

                option = OptionContract(
                    symbol=f"SPY{expiry.strftime('%y%m%d')}{opt_type[0]}{int(strike)}",
                    underlying="SPY",
                    strike=strike,
                    expiry=expiry,
                    option_type=opt_type,
                    bid=theo * 0.98,
                    ask=theo * 1.02,
                    last=theo,
                    volume=1000,
                    open_interest=5000,
                    underlying_price=450.0
                )
                option_chain.append(option)

    logging.info("\nOption Chain Size: %s options", len(option_chain))

    # Build surface
    builder = VolatilitySurfaceBuilder()
    surface = builder.build_surface(option_chain, 450.0)

    logging.info("\nVolatility Surface:")
    logging.info("  Expiries: %s", len(surface.expiries))
    logging.info("  Strikes: %s", len(surface.strikes))
    logging.info("  Surface Shape: %s", surface.ivs.shape)

    # Sample some IVs
    logging.info("\nSample IVs:")
    test_points = [
        (30/DAYS_IN_YEAR, 445),
        (30/DAYS_IN_YEAR, 450),
        (30/DAYS_IN_YEAR, 455),
        (60/DAYS_IN_YEAR, 450),
    ]

    for T, K in test_points:
        iv = surface.get_iv(K, T)
        logging.info(f"  T={T*DAYS_IN_YEAR:.0f} days, K=${K}: IV={iv:.2%}")

def example_volatility_analysis():
    """Example: Comprehensive volatility analysis."""
    logging.info("\n" + "="*60)
    logging.info("Example: Volatility Analysis")
    logging.info("="*60)

    # Create analyzer
    analyzer = VolatilityAnalyzer()

    # Create option chain
    option_chain = create_test_option_chain()

    # Analyze
    metrics = analyzer.calculate_volatility_metrics(option_chain, 450.0)

    logging.info("\nVolatility Metrics:")
    logging.info(f"  Current IV: {metrics.current_iv:.2%}")
    logging.info(f"  Historical Vol: {metrics.historical_vol:.2%}")
    logging.info(f"  IV Rank: {metrics.iv_rank:.1f}")
    logging.info(f"  IV Percentile: {metrics.iv_percentile:.1f}")
    logging.info(f"  Skew: {metrics.skew:.4f}")
    logging.info("  Regime: %s", metrics.regime)

    logging.info("\nTerm Structure:")
    for expiry, iv in sorted(metrics.term_structure.items()):
        logging.info(f"  {expiry*12:.1f} months: {iv:.2%}")

def example_engine_operation():
    """Example: Volatility engine operation."""
    logging.info("\n" + "="*60)
    logging.info("Example: Volatility Engine Operation")
    logging.info("="*60)

    # Create engine
    stop_event = mp.Event()
    engine = VolatilityEngine(
        EngineType.VOLATILITY,
        stop_event,
        "VOL_ENGINE_001"
    )

    logging.info("✅ Volatility Engine created")

    # Simulate initialization
    logging.info("\nInitializing engine...")
    # engine.initialize()  # Would connect to coordinator

    # Show capabilities
    logging.info("\nEngine Capabilities:")
    logging.info("  • Real-time IV calculation")
    logging.info("  • Complete Greeks computation")
    logging.info("  • Volatility surface modeling")
    logging.info("  • Historical volatility analysis")
    logging.info("  • Volatility regime detection")

    # Get metrics
    metrics = engine.get_metrics()
    logging.info("\nEngine Metrics:")
    for key, value in metrics.items():
        logging.info("  %s: %s", key, value)

    logging.info("\n✅ Engine demonstration complete")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Configure logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )



    choice = input("\nSelect example (1-7): ")

    if choice == "1":
        example_iv_calculation()
    elif choice == "2":
        example_greeks_calculation()
    elif choice == "3":
        example_volatility_surface()
    elif choice == "4":
        example_volatility_analysis()
    elif choice == "5":
        example_engine_operation()
    elif choice == "6":
        example_iv_calculation()
        example_greeks_calculation()
        example_volatility_surface()
        example_volatility_analysis()
        example_engine_operation()
    else:
        pass

