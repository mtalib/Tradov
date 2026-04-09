#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Module: SpyderS05_GEXDEXCalculator.py
Group: S (Signals)
Purpose: GEX (Gamma Exposure) and DEX (Delta Exposure) calculations from real options chain data

Last Updated: 2026-03-03 Time: 00:00:00

Description:
    Computes Net Gamma Exposure (GEX) and Net Delta Exposure (DEX) for SPY from
    the live options chain sourced through SpyderN09_GammaExposure or directly
    from SpyderN03_OptionsChainManager.

    GEX formula (per strike):
        GEX = open_interest × gamma × contract_multiplier² × spot_price
    Net GEX = sum(call GEX) - sum(put GEX)

    A negative net GEX indicates dealers are short gamma — expect amplified moves.
    A positive net GEX indicates dealers are long gamma — expect mean-reversion.

    OGL (Options Gravity Level) is the strike with maximum absolute GEX, i.e. the
    level at which dealer hedging flow is largest (effectively max-pain by gamma).
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
from datetime import datetime

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    logger = SpyderLogger
except ImportError:
    logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================
CONTRACT_MULTIPLIER = 100  # Standard US equity option multiplier


# ==============================================================================
# EXCEPTIONS
# ==============================================================================
class DataUnavailableError(RuntimeError):
    """Raised when required options chain data is not available."""
    pass


# ==============================================================================
# MAIN CALCULATOR CLASS
# ==============================================================================
class GEXDEXCalculator:
    """
    Computes Net Gamma Exposure (GEX), Net Delta Exposure (DEX), and the
    Options Gravity Level (OGL) from a live SPY options chain snapshot.

    Usage::

        calc = GEXDEXCalculator()
        result = calc.calculate_all(chain_df, spot_price=580.0)

    Args:
        chain_df (pd.DataFrame): Options chain with columns:
            strike, option_type ('call'/'put'), open_interest,
            gamma, delta, implied_volatility.
        spot_price (float): Current underlying price.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("GEXDEXCalculator initialized (real options chain mode)")
        self._last_result: dict | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_all(self, chain_df=None, spot_price: float | None = None) -> dict:
        """
        Compute GEX, DEX and OGL from an options chain snapshot.

        Args:
            chain_df: DataFrame with options chain data (strikes, OI, greeks).
            spot_price: Current SPY spot price.

        Returns:
            dict with keys: gex, dex, ogl, timestamp, num_strikes, data_source.

        Raises:
            DataUnavailableError: If chain_df is None or empty and no cached
                result is available.
        """
        if chain_df is not None and len(chain_df) > 0:
            result = self._compute_from_chain(chain_df, spot_price)
            self._last_result = result
            return result

        # Attempt to pull chain from SpyderN09 / SpyderN03 if no data passed
        try:
            result = self._compute_from_internal_sources(spot_price)
            self._last_result = result
            return result
        except Exception as exc:
            raise DataUnavailableError(
                "GEX/DEX calculation requires a live options chain snapshot. "
                "Ensure SpyderN09_GammaExposure or SpyderN03_OptionsChainManager "
                f"is running and providing data. Root cause: {exc}"
            ) from exc

    def get_gex(self, chain_df=None, spot_price: float | None = None) -> float:
        """
        Return net GEX in billions of dollars.

        Raises:
            DataUnavailableError: If no options chain data is available.
        """
        return self.calculate_all(chain_df, spot_price)["gex"]

    def get_dex(self, chain_df=None, spot_price: float | None = None) -> float:
        """
        Return net DEX in millions of dollars.

        Raises:
            DataUnavailableError: If no options chain data is available.
        """
        return self.calculate_all(chain_df, spot_price)["dex"]

    def get_ogl(self, chain_df=None, spot_price: float | None = None) -> float:
        """
        Return the Options Gravity Level (max-gamma strike) in dollars.

        Raises:
            DataUnavailableError: If no options chain data is available.
        """
        return self.calculate_all(chain_df, spot_price)["ogl"]

    def calculate_simulated(self) -> dict:
        """
        Return simulated GEX/DEX/OGL values for testing and offline analysis.

        Returns:
            dict with keys: gex, dex, ogl, timestamp, num_strikes, data_source.
        """
        rng = np.random.default_rng()
        result = {
            "gex": float(rng.normal(0.5, 2.0)),
            "dex": float(rng.normal(10.0, 50.0)),
            "ogl": float(rng.normal(580.0, 5.0)),
            "timestamp": datetime.now(),
            "num_strikes": 20,
            "data_source": "simulated",
        }
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # Internal computation
    # ------------------------------------------------------------------

    def _compute_from_chain(self, chain_df, spot_price: float | None) -> dict:
        """Compute GEX/DEX from a DataFrame with options chain data."""

        df = chain_df.copy()

        required = {"strike", "option_type", "open_interest", "gamma", "delta"}
        missing = required - set(df.columns)
        if missing:
            raise DataUnavailableError(
                f"Options chain DataFrame is missing required columns: {missing}"
            )

        # Normalise option_type
        df["option_type"] = df["option_type"].str.lower()

        calls = df[df["option_type"] == "call"]
        puts = df[df["option_type"] == "put"]

        # GEX per contract = OI × gamma × multiplier²× spot
        spot = spot_price if spot_price else 1.0

        call_gex = (calls["open_interest"] * calls["gamma"]
                    * CONTRACT_MULTIPLIER ** 2 * spot).sum()
        put_gex = (puts["open_interest"] * puts["gamma"]
                   * CONTRACT_MULTIPLIER ** 2 * spot).sum()

        net_gex = call_gex - put_gex  # dollars
        net_gex_billions = net_gex / 1e9

        # DEX = sum(OI × delta × multiplier × spot)
        call_dex = (calls["open_interest"] * calls["delta"]
                    * CONTRACT_MULTIPLIER * spot).sum()
        put_dex = (puts["open_interest"] * puts["delta"]
                   * CONTRACT_MULTIPLIER * spot).sum()
        net_dex_millions = (call_dex + put_dex) / 1e6

        # OGL — strike where |GEX| is largest (dealer hedging gravity)
        df["gex_contrib"] = np.where(
            df["option_type"] == "call",
            df["open_interest"] * df["gamma"] * CONTRACT_MULTIPLIER ** 2 * spot,
            -df["open_interest"] * df["gamma"] * CONTRACT_MULTIPLIER ** 2 * spot,
        )
        by_strike = df.groupby("strike")["gex_contrib"].sum()
        ogl = float(by_strike.abs().idxmax()) if not by_strike.empty else (spot_price or 0.0)

        return {
            "gex": net_gex_billions,
            "dex": net_dex_millions,
            "ogl": ogl,
            "timestamp": datetime.now(),
            "num_strikes": int(df["strike"].nunique()),
            "data_source": "live_chain",
        }

    def _compute_from_internal_sources(self, spot_price: float | None) -> dict:
        """Try to obtain chain data from SpyderN09 or SpyderN03 singletons."""
        # Try SpyderN09_GammaExposure first
        try:
            from SpyderN_OptionsAnalytics.SpyderN09_GammaExposure import GammaExposureCalculator
            gex_calc = GammaExposureCalculator()
            result = gex_calc.get_spy_gex_summary()
            return {
                "gex": result.get("net_gex_billions", 0.0),
                "dex": result.get("net_dex_millions", 0.0),
                "ogl": result.get("max_gamma_strike", spot_price or 0.0),
                "timestamp": datetime.now(),
                "num_strikes": result.get("num_strikes", 0),
                "data_source": "SpyderN09_GammaExposure",
            }
        except Exception as e:
            logging.getLogger(__name__).debug("SpyderN09 GEX calculation unavailable, using fallback: %s", e)

        # Fallback: SpyderN03 options chain manager (preferred over deprecated B30)
        try:
            from SpyderN_OptionsAnalytics.SpyderN03_OptionsChainManager import OptionsChainManager
            chain_mgr = OptionsChainManager()
            chain_df = chain_mgr.get_chain("SPY")
            if chain_df.empty:
                raise DataUnavailableError("SpyderN03_OptionsChainManager returned empty chain for SPY")
            return self._compute_from_chain(chain_df, spot_price)
        except DataUnavailableError:
            raise
        except Exception as e:
            raise DataUnavailableError(
                f"SpyderN03_OptionsChainManager fallback failed: {e}"
            ) from e


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================
_gex_calculator: GEXDEXCalculator | None = None


def get_gex_calculator() -> GEXDEXCalculator:
    """Return the module-level GEXDEXCalculator singleton."""
    global _gex_calculator
    if _gex_calculator is None:
        _gex_calculator = GEXDEXCalculator()
    return _gex_calculator

