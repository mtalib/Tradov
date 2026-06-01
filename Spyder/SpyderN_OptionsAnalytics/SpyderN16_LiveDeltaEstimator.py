#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderN_OptionsAnalytics
Module: SpyderN16_LiveDeltaEstimator.py
Purpose: Fast local Black-Scholes delta estimator for SPX/SPXW risk checks.
"""

from __future__ import annotations

import datetime as dt
import math

from Spyder.SpyderU_Utilities.SpyderU51_OptionTypesAndTime import OptionType, ShortLeg, now_et

_EXPIRY_TIME_ET = dt.time(16, 0)
_SECONDS_PER_YEAR = 365.0 * 24 * 3600
_DEFAULT_RISK_FREE = 0.04


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_scholes_delta(
    *,
    spot: float,
    strike: float,
    t_years: float,
    volatility: float,
    option_type: OptionType,
    risk_free_rate: float = _DEFAULT_RISK_FREE,
) -> float:
    """Return signed delta for a call/put option."""

    if t_years <= 0.0 or volatility <= 0.0 or spot <= 0.0 or strike <= 0.0:
        in_the_money = spot > strike if option_type is OptionType.CALL else spot < strike
        sign = 1.0 if option_type is OptionType.CALL else -1.0
        return sign * (1.0 if in_the_money else 0.0)

    sqrt_t = math.sqrt(t_years)
    d1 = (
        math.log(spot / strike)
        + (risk_free_rate + 0.5 * volatility * volatility) * t_years
    ) / (volatility * sqrt_t)

    if option_type is OptionType.CALL:
        return _norm_cdf(d1)
    return _norm_cdf(d1) - 1.0


def time_to_expiry_years(now: dt.datetime | None = None) -> float:
    """Return fraction of year until same-day 16:00 ET expiry."""

    now = now or now_et()
    expiry_dt = dt.datetime.combine(now.date(), _EXPIRY_TIME_ET, tzinfo=now.tzinfo)
    seconds = max((expiry_dt - now).total_seconds(), 0.0)
    return seconds / _SECONDS_PER_YEAR


def estimate_live_delta(leg: ShortLeg, quote: dict) -> float | None:
    """Estimate live delta from quote payload; return None when inputs are missing."""

    spot = quote.get("underlying_price") or quote.get("underlying_last") or quote.get("last")
    greeks = quote.get("greeks") or {}
    volatility = (
        greeks.get("mid_iv")
        or greeks.get("smv_vol")
        or greeks.get("bid_iv")
        or greeks.get("ask_iv")
    )

    if spot is None or volatility is None:
        return None

    try:
        spot_f = float(spot)
        vol_f = float(volatility)
    except (TypeError, ValueError):
        return None

    return black_scholes_delta(
        spot=spot_f,
        strike=leg.strike,
        t_years=time_to_expiry_years(),
        volatility=vol_f,
        option_type=leg.option_type,
    )
