#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Module: SpyderS05_GEXDEXCalculator.py
Group: S (Signals)
Purpose: GEX, DEX, VEX, and CHEX calculations from live SPY options chain data

Last Updated: 2026-04-10 Time: 00:00:00

Description:
    Computes Net Gamma Exposure (GEX), Net Delta Exposure (DEX), Net Vanna
    Exposure (VEX), and Net Charm Exposure (CHEX) for SPY from the live options
    chain sourced through SpyderN09_GammaExposure or SpyderN03_OptionsChainManager.

    GEX formula (per strike):
        GEX = open_interest × gamma × contract_multiplier² × spot_price
    Net GEX = sum(call GEX) - sum(put GEX)

    A negative net GEX indicates dealers are short gamma — expect amplified moves.
    A positive net GEX indicates dealers are long gamma — expect mean-reversion.

    OGL (Options Gravity Level) is the strike with maximum absolute GEX, i.e. the
    level at which dealer hedging flow is largest (effectively max-pain by gamma).

    Vanna (VEX): ∂Δ/∂σ = -n(d₁) × d₂ / σ
        Measures how dealer delta changes when IV moves.  A large positive VEX
        means a vol spike forces dealers to BUY delta (buying pressure).

    Charm (CHEX): ∂Δ/∂T = -n(d₁) × [2(r-q)T - d₂σ√T] / (2Tσ√T)
        Measures how dealer delta decays with time.  Critical on 0-DTE sessions:
        negative CHEX into the close means dealers are sellers as time decays.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import math
from datetime import datetime, timezone

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

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
    Computes Net Gamma Exposure (GEX), Net Delta Exposure (DEX), Net Vanna
    Exposure (VEX), Net Charm Exposure (CHEX), and the Options Gravity Level
    (OGL) from a live SPY options chain snapshot.

    Usage::

        calc = GEXDEXCalculator()
        result = calc.calculate_all(chain_df, spot_price=580.0)
        # result keys: gex, dex, ogl, vex, chex, timestamp, num_strikes, data_source

    Args:
        chain_df (pd.DataFrame): Options chain with columns:
            strike, option_type ('call'/'put'), open_interest, gamma, delta,
            implied_volatility, expiration_date (or dte).
        spot_price (float): Current underlying price.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.debug("GEXDEXCalculator initialized (real options chain mode)")
        self._last_result: dict | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_all(self, chain_df=None, spot_price: float | None = None) -> dict:
        """
        Compute GEX, DEX, VEX, CHEX, and OGL from an options chain snapshot.

        Args:
            chain_df: DataFrame with options chain data (strikes, OI, greeks).
            spot_price: Current SPY spot price.

        Returns:
            dict with keys: gex, dex, ogl, vex, chex, timestamp, num_strikes,
            data_source.

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

    def get_vex(self, chain_df=None, spot_price: float | None = None) -> float:
        """
        Return Net Vanna Exposure (VEX) in millions of dollars per 1-vol-point.

        A large positive VEX means a volatility spike forces dealers to buy delta
        (bullish pressure). Negative VEX means dealers sell delta when vol rises.

        Raises:
            DataUnavailableError: If no options chain data is available.
        """
        return self.calculate_all(chain_df, spot_price)["vex"]

    def get_chex(self, chain_df=None, spot_price: float | None = None) -> float:
        """
        Return Net Charm Exposure (CHEX) in delta-equivalents per trading day.

        A large negative CHEX into market close means dealer delta is decaying
        downward — they become net sellers as time passes (common on 0-DTE).

        Raises:
            DataUnavailableError: If no options chain data is available.
        """
        return self.calculate_all(chain_df, spot_price)["chex"]

    def calculate_simulated(self) -> dict:
        """
        Return simulated GEX/DEX/VEX/CHEX/OGL values for testing and offline analysis.

        Returns:
            dict with keys: gex, dex, ogl, vex, chex, timestamp, num_strikes,
            data_source.
        """
        rng = np.random.default_rng()
        result = {
            "gex": float(rng.normal(0.5, 2.0)),
            "dex": float(rng.normal(10.0, 50.0)),
            "ogl": float(rng.normal(580.0, 5.0)),
            "vex": float(rng.normal(0.0, 5.0)),
            "chex": float(rng.normal(0.0, 200.0)),
            "timestamp": datetime.now(timezone.utc),
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

        # Second-order Greeks: Vanna (VEX) and Charm (CHEX)
        vex, chex = self._compute_second_order_greeks(df, spot)

        return {
            "gex": net_gex_billions,
            "dex": net_dex_millions,
            "ogl": ogl,
            "vex": vex,
            "chex": chex,
            "timestamp": datetime.now(timezone.utc),
            "num_strikes": int(df["strike"].nunique()),
            "data_source": "live_chain",
        }

    def _compute_second_order_greeks(
        self,
        df: pd.DataFrame,
        spot_price: float,
        risk_free_rate: float = 0.045,
        div_yield: float = 0.013,
    ) -> tuple[float, float]:
        """
        Compute Net Vanna Exposure (VEX) and Net Charm Exposure (CHEX) via BSM.

        Uses Black-Scholes-Merton second-order Greek formulas.  Input DataFrame
        must already have been validated (required columns present).

        Formulas
        --------
        d₁ = [ln(S/K) + (r - q + σ²/2) × T] / (σ√T)
        d₂ = d₁ - σ√T
        n(d₁) = standard-normal PDF evaluated at d₁

        Vanna = ∂Δ/∂σ = −n(d₁) × d₂ / σ
        Charm = ∂Δ/∂T = −n(d₁) × [2(r-q)T − d₂σ√T] / (2Tσ√T)

        Sign convention mirrors GEX: calls positive, puts negative.

        Args:
            df: Options chain DataFrame (already validated, option_type normalised).
            spot_price: Current underlying (S).
            risk_free_rate: Annualised risk-free rate (default 4.5%).
            div_yield: Continuous dividend yield (default 1.3% for SPY).

        Returns:
            (vex, chex):
                vex  — Net Vanna Exposure in $M per 1-vol-point move.
                chex — Net Charm Exposure in delta-equivalents per trading day.
        """
        S = spot_price if spot_price else 1.0
        r = risk_free_rate
        q = div_yield

        # Resolve time-to-expiry (years) from 'dte' or 'expiration_date' column.
        if "dte" in df.columns:
            T_days = df["dte"].fillna(1).values.astype(float)
        elif "expiration_date" in df.columns:
            today = pd.Timestamp.now().normalize()
            T_days = (
                pd.to_datetime(df["expiration_date"]) - today
            ).dt.days.fillna(1).values.astype(float)
        else:
            # Cannot compute second-order greeks without expiry info.
            self.logger.debug(
                "VEX/CHEX skipped: no 'dte' or 'expiration_date' column in chain."
            )
            return 0.0, 0.0

        T = np.maximum(T_days / 365.0, 1.0 / 365.0)  # floor at 1 trading day

        K = df["strike"].values.astype(float)

        # Accept 'implied_volatility' or Tradier's 'smv_vol'
        if "implied_volatility" in df.columns:
            sigma = df["implied_volatility"].fillna(0.0).values.astype(float)
        elif "smv_vol" in df.columns:
            sigma = df["smv_vol"].fillna(0.0).values.astype(float)
        else:
            self.logger.debug("VEX/CHEX skipped: no implied_volatility column.")
            return 0.0, 0.0

        oi = df["open_interest"].fillna(0).values.astype(float)
        is_call = df["option_type"].str.lower() == "call"
        signs = np.where(is_call, 1.0, -1.0)

        valid = (K > 0) & (sigma > 0) & (oi > 0) & np.isfinite(K) & np.isfinite(sigma)

        sqrt_T = np.sqrt(T)
        with np.errstate(divide="ignore", invalid="ignore"):
            d1 = np.where(
                valid,
                (np.log(np.where(valid, S / K, 1.0)) + (r - q + 0.5 * sigma**2) * T)
                / (sigma * sqrt_T),
                0.0,
            )
            d2 = d1 - sigma * sqrt_T

            # Standard-normal PDF: n(d1) = (1/√(2π)) · exp(−d1²/2)
            n_d1 = np.where(valid, np.exp(-0.5 * d1**2) / math.sqrt(2.0 * math.pi), 0.0)

            # Vanna: ∂Δ/∂σ = −n(d1) × d2/σ
            vanna = np.where(valid & (sigma > 0), -n_d1 * d2 / sigma, 0.0)

            # Charm: ∂Δ/∂T (expressed per year; divide by 252 for per-trading-day)
            denom_charm = 2.0 * T * sigma * sqrt_T
            charm = np.where(
                valid & (denom_charm > 0),
                -n_d1 * (2.0 * (r - q) * T - d2 * sigma * sqrt_T) / denom_charm,
                0.0,
            )

        # Aggregate exposures (calls positive, puts negative — same as GEX)
        vex = float(np.nansum(signs * vanna * oi * CONTRACT_MULTIPLIER)) / 1e6
        chex = float(np.nansum(signs * charm * oi * CONTRACT_MULTIPLIER)) / 252.0

        return vex, chex

    def _compute_from_internal_sources(self, spot_price: float | None) -> dict:
        """Try to obtain chain data from SpyderN09 or SpyderN03 singletons."""
        # Try SpyderN09_GammaExposure first
        try:
            from SpyderN_OptionsAnalytics.SpyderN09_GammaExposure import GammaExposureCalculator
            gex_calc = GammaExposureCalculator()
            result = gex_calc.get_spy_gex_summary()
            n_strikes = result.get("num_strikes", 0)
            if n_strikes == 0:
                # OPRA stream not yet active — fall through so the chain
                # fallback (N03 → Tradier B40) computes a real GEX instead
                # of propagating the zero that N09 returns without live data.
                raise DataUnavailableError(
                    "SpyderN09 returned 0 strikes — OPRA stream not active; using chain fallback"
                )
            return {
                "gex": result.get("net_gex_billions", 0.0),
                "dex": result.get("net_dex_millions", 0.0),
                "ogl": result.get("max_gamma_strike", spot_price or 0.0),
                "timestamp": datetime.now(timezone.utc),
                "num_strikes": n_strikes,
                "data_source": "SpyderN09_GammaExposure",
            }
        except Exception as e:
            logging.getLogger(__name__).debug("SpyderN09 GEX calculation unavailable, using fallback: %s", e)  # noqa: E501

        # Fallback: SpyderN03 options chain manager (preferred over deprecated B30)
        try:
            from SpyderN_OptionsAnalytics.SpyderN03_OptionsChainManager import OptionsChainManager
            chain_mgr = OptionsChainManager()
            chain_df = chain_mgr.get_chain("SPY")
            if chain_df.empty:
                raise DataUnavailableError("SpyderN03_OptionsChainManager returned empty chain for SPY")  # noqa: E501
            return self._compute_from_chain(chain_df, spot_price)
        except DataUnavailableError:
            pass  # fall through to Tradier direct fetch below
        except Exception as e:
            logging.getLogger(__name__).debug("SpyderN03 fallback unavailable: %s", e)

        # Final fallback: Tradier B40 direct API — fetch chain with greeks for nearest expiry
        try:
            import pandas as pd
            from datetime import date as _date
            from scipy.stats import norm as _norm
            from Spyder.SpyderB_Broker.SpyderB40_TradierClient import create_tradier_client_from_env

            client = create_tradier_client_from_env()

            # Get available SPY expirations
            exps_resp = client.get_option_expirations("SPY")
            exps = exps_resp.get("expirations", {}).get("date", [])
            if not exps:
                raise DataUnavailableError("No SPY expirations returned from Tradier")
            if isinstance(exps, str):
                exps = [exps]

            # Pick the soonest future expiration (but at least 1 day out)
            today_str = str(_date.today())
            future_exps = sorted(e for e in exps if e > today_str)
            if not future_exps:
                raise DataUnavailableError("No future SPY expirations available from Tradier")
            nearest = future_exps[0]

            greeks_list = client.get_option_chain_with_greeks("SPY", nearest)
            if not greeks_list:
                raise DataUnavailableError(f"Empty options chain from Tradier for SPY {nearest}")

            # Convert GreekData objects to the DataFrame format _compute_from_chain expects
            rows = [
                {
                    "strike": g.strike,
                    "option_type": g.option_type,
                    "open_interest": g.open_interest,
                    "gamma": g.gamma,
                    "delta": g.delta,
                    "implied_volatility": g.iv,
                    "expiration_date": g.expiration,
                }
                for g in greeks_list
            ]
            chain_df = pd.DataFrame(rows)
            if chain_df.empty:
                raise DataUnavailableError("Tradier chain DataFrame is empty after conversion")

            # Pull spot price if caller didn't supply it
            if spot_price is None:
                # 1) Try Tradier market data quote (no account auth needed)
                try:
                    quote_resp = client.get_quotes(["SPY"])
                    quote = quote_resp.get("quotes", {}).get("quote", {})
                    if isinstance(quote, list):
                        quote = next((q for q in quote if q.get("symbol") == "SPY"), {})
                    spot_price = float(quote.get("last") or 0) or None
                except Exception:
                    pass
                # 2) Fallback: yfinance (works on weekends)
                if not spot_price:
                    try:
                        import yfinance as yf
                        data = yf.Ticker("SPY").history(period="1d", interval="1m")
                        if not data.empty:
                            spot_price = float(data["Close"].iloc[-1])
                    except Exception:
                        pass
                # 3) Estimate from chain mid-price if still missing
                if not spot_price:
                    atm_rows = chain_df[chain_df["implied_volatility"] > 0]
                    if not atm_rows.empty:
                        spot_price = float(atm_rows["strike"].median())

            # On weekends / non-trading hours Tradier returns gamma=0 for all
            # strikes.  Compute BSM gamma & delta from IV so GEX is non-trivial.
            gamma_all_zero = (chain_df["gamma"].abs().sum() == 0)
            delta_all_zero = (chain_df["delta"].abs().sum() == 0)

            if (gamma_all_zero or delta_all_zero) and spot_price:
                S = float(spot_price)
                r, q = 0.045, 0.013  # risk-free, dividend yield for SPY
                today = _date.today()
                # dte per row in years
                exps_dates = pd.to_datetime(chain_df["expiration_date"])
                T_days = (exps_dates - pd.Timestamp(today)).dt.days.clip(lower=1)
                T = T_days.values / 365.0

                K = chain_df["strike"].values.astype(float)
                sigma = chain_df["implied_volatility"].values.astype(float)
                # Only compute where IV is valid
                valid = sigma > 0.0
                bsm_gamma = np.zeros(len(chain_df))
                bsm_delta = np.zeros(len(chain_df))
                if valid.any():
                    sv = sigma[valid]
                    Tv = T[valid]
                    Kv = K[valid]
                    d1 = (np.log(S / Kv) + (r - q + 0.5 * sv ** 2) * Tv) / (sv * np.sqrt(Tv))
                    bsm_gamma[valid] = _norm.pdf(d1) / (S * sv * np.sqrt(Tv))
                    # delta varies by option type
                    types = chain_df["option_type"].str.lower().values
                    is_call = types == "call"
                    bsm_delta[valid & is_call] = (
                        np.exp(-q * Tv) * _norm.cdf(d1)
                    )[is_call[valid]]
                    bsm_delta[valid & ~is_call] = (
                        np.exp(-q * Tv) * (_norm.cdf(d1) - 1)
                    )[~is_call[valid]]

                if gamma_all_zero:
                    chain_df["gamma"] = bsm_gamma
                if delta_all_zero:
                    chain_df["delta"] = bsm_delta

                logging.getLogger(__name__).debug(
                    "BSM greeks computed for %d / %d options (Tradier returned zeros)",
                    int(valid.sum()), len(chain_df),
                )

            result = self._compute_from_chain(chain_df, spot_price)
            result["data_source"] = "SpyderB40_TradierClient"
            return result

        except DataUnavailableError:
            raise
        except Exception as e:
            raise DataUnavailableError(
                f"Tradier B40 direct fallback failed: {e}"
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


# Alias for backward compatibility with P01 and N09
GammaExposureCalculator = GEXDEXCalculator
