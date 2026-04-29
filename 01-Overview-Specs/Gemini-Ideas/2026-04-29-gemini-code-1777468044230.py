'''
Fail-Fast Startup Validation:
Inject this validation sequence before enabling the trading loop. If mode == "live" and an error is caught, sys.exit() immediately.
'''

from copy import deepcopy

def validate_autonomous_readiness_config(config: dict, mode: str) -> dict:
    effective = deepcopy(config)
    errors = []

    # Helper functions assumed: require_float_range, require_int_range, require_bool
    
    # 1. Liquidity rules
    require_float_range("autonomous_readiness.liquidity.max_spread_pct", 0.01, 0.50)
    require_int_range("autonomous_readiness.liquidity.max_quote_age_ms", 100, 10000)
    
    # 2. Execution rules
    require_float_range("autonomous_readiness.execution.max_slippage_bps", 1, 200)
    require_bool("autonomous_readiness.execution.halt_on_quality_breach")

    # 3. Event-clock rules
    require_bool("autonomous_readiness.event_clock.enabled")
    require_int_range("autonomous_readiness.event_clock.blackout_pre_minutes", 0, 240)

    ok = len(errors) == 0
    if not ok and mode == "live":
        ok = False

    return {"ok": ok, "effective": effective, "errors": errors}
