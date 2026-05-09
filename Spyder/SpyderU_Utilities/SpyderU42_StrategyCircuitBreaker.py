#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: Spyder.SpyderU_Utilities
Module: SpyderU42_StrategyCircuitBreaker.py
Purpose: Strategy-level circuit breaker that automatically isolates misbehaving
         trading strategies to prevent a single bad strategy from causing
         cascading failures or excessive portfolio losses.

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-28 Time: 00:00:00

Module Description:
    Implements a per-strategy circuit breaker pattern modelled on the
    standard CLOSED → OPEN → HALF_OPEN state machine.  Each strategy
    tracked by its string identifier independently accumulates failure
    counts, consecutive-failure counts, and cumulative P&L impact.

    When a strategy trips its configured threshold (consecutive failures
    OR cumulative dollar loss) its circuit moves to OPEN and
    ``is_allowed()`` returns False, preventing the strategy engine from
    submitting new orders for that strategy until the recovery timeout
    has elapsed.

    After ``recovery_timeout`` seconds the circuit transitions to
    HALF_OPEN.  The next successful ``record_success()`` call moves it
    back to CLOSED.  A further failure in HALF_OPEN immediately
    re-opens the circuit and restarts the timeout.

    Operators can call ``manually_reset()`` at any time to force a
    strategy back to CLOSED (e.g. after a code fix or manual review).

Usage:
    from Spyder.SpyderU_Utilities.SpyderU42_StrategyCircuitBreaker import (
        get_strategy_circuit_breaker,
        StrategyCircuitBreakerState,
    )

    scb = get_strategy_circuit_breaker()

    # Guard before sending orders
    if scb.is_allowed("iron_condor_SPY"):
        # … submit orders …
        scb.record_success("iron_condor_SPY")
    else:
        logger.warning("iron_condor_SPY circuit is open – skipping")

    # On failure
    scb.record_failure("iron_condor_SPY", reason="order rejected", pnl_impact=-120.0)

    # Track P&L separately (e.g. from fill callbacks)
    scb.record_pnl("iron_condor_SPY", pnl=-45.0)

    # Human-readable dashboard
    print(scb.get_status_report())

Integration Points:
    - SpyderD_Strategies / SpyderD31_StrategyOrchestrator: call is_allowed()
      before dispatching strategy signals.
    - SpyderE_Risk / SpyderE01_RiskManager: call record_pnl() from P&L
      callbacks so loss-based tripping works without needing an explicit
      failure event.
    - SpyderG_GUI / SpyderG05_TradingDashboard: call get_all_states() to
      render per-strategy circuit status in the dashboard.
    - SpyderI_Integration / SpyderI09_DiagnosticsEngine_HealthChecks:
      include get_status_report() in system health output.

Change Log:
    2026-03-28:
        - Initial implementation
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum, auto

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import get_logger

logger = get_logger(__name__)


# ==============================================================================
# ENUMERATIONS
# ==============================================================================

class StrategyCircuitBreakerState(Enum):
    """Operating state of a per-strategy circuit breaker."""

    CLOSED = auto()     # Normal – strategy is allowed to trade
    OPEN = auto()       # Tripped – strategy is isolated, orders blocked
    HALF_OPEN = auto()  # Recovery probe – one test call permitted


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class StrategyFailureRecord:
    """Tracks all circuit-breaker state for a single strategy.

    Attributes:
        strategy_id: Unique identifier for the strategy.
        failure_count: Total failure events recorded (never reset on recovery).
        consecutive_failures: Failures in the current unbroken run.
        last_failure_time: Wall-clock time of the most recent failure.
        last_failure_reason: Human-readable reason string from the last failure.
        total_loss: Cumulative P&L impact (negative = loss) since the last
            manual reset or initial registration.
        state: Current circuit-breaker state for this strategy.
        tripped_at: Wall-clock time the circuit last transitioned to OPEN.
        recovery_attempts: Number of HALF_OPEN probes attempted so far.
    """

    strategy_id: str
    failure_count: int = 0
    consecutive_failures: int = 0
    last_failure_time: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
    last_failure_reason: str = ""
    total_loss: float = 0.0
    state: StrategyCircuitBreakerState = StrategyCircuitBreakerState.CLOSED
    tripped_at: datetime | None = None
    recovery_attempts: int = 0


@dataclass
class StrategyCircuitBreakerConfig:
    """Configuration knobs for the strategy circuit breaker.

    Attributes:
        failure_threshold: Number of consecutive failures before tripping
            the circuit to OPEN.  Default: 5.
        loss_threshold: Cumulative dollar loss (negative float) that, once
            breached, trips the circuit regardless of failure count.
            Default: -500.0.
        recovery_timeout: Seconds the circuit stays OPEN before
            automatically transitioning to HALF_OPEN.  Default: 300.0 (5 min).
        half_open_max_attempts: Maximum HALF_OPEN probe attempts before
            treating further failures as a permanent re-open.  Currently
            informational – each failed probe still re-opens immediately.
            Default: 3.
        reset_timeout: Seconds of clean operation (no failures) before the
            cumulative counters are silently reset to baseline.
            Default: 3600.0 (1 hour).
    """

    failure_threshold: int = 5
    loss_threshold: float = -500.0
    recovery_timeout: float = 300.0
    half_open_max_attempts: int = 3
    reset_timeout: float = 3600.0


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class StrategyCircuitBreaker:
    """Per-strategy circuit breaker for the Spyder trading system.

    Maintains an independent ``StrategyFailureRecord`` for every strategy
    that registers activity.  All public methods are thread-safe via a
    single ``threading.Lock``.

    Args:
        config: Optional ``StrategyCircuitBreakerConfig`` instance.  When
            omitted the default thresholds are used.

    Examples:
        scb = StrategyCircuitBreaker()

        if scb.is_allowed("my_strategy"):
            try:
                execute_strategy("my_strategy")
                scb.record_success("my_strategy")
            except Exception as exc:
                scb.record_failure("my_strategy", reason=str(exc), pnl_impact=-50.0)
    """

    def __init__(self, config: StrategyCircuitBreakerConfig | None = None) -> None:
        self._config: StrategyCircuitBreakerConfig = config or StrategyCircuitBreakerConfig()
        self._records: dict[str, StrategyFailureRecord] = {}
        self._lock: threading.Lock = threading.Lock()
        logger.info(
            "StrategyCircuitBreaker initialised "
            f"(failure_threshold={self._config.failure_threshold}, "
            f"loss_threshold={self._config.loss_threshold}, "
            f"recovery_timeout={self._config.recovery_timeout}s)"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create(self, strategy_id: str) -> StrategyFailureRecord:
        """Return the record for *strategy_id*, creating it on first access.

        Must be called with ``self._lock`` held.
        """
        if strategy_id not in self._records:
            self._records[strategy_id] = StrategyFailureRecord(
                strategy_id=strategy_id
            )
            logger.debug("Registered new strategy in circuit breaker: %r", strategy_id)
        return self._records[strategy_id]

    def _check_auto_transition(self, record: StrategyFailureRecord) -> None:
        """Transition OPEN → HALF_OPEN when the recovery timeout has elapsed.

        Must be called with ``self._lock`` held.
        """
        if (
            record.state == StrategyCircuitBreakerState.OPEN
            and record.tripped_at is not None
        ):
            elapsed = (
                datetime.now(UTC) - record.tripped_at
            ).total_seconds()
            if elapsed >= self._config.recovery_timeout:
                record.state = StrategyCircuitBreakerState.HALF_OPEN
                record.recovery_attempts += 1
                logger.info(
                    f"Strategy {record.strategy_id!r} circuit → HALF_OPEN "
                    f"(attempt {record.recovery_attempts}, "
                    f"elapsed {elapsed:.1f}s)"
                )

    def _check_reset_timeout(self, record: StrategyFailureRecord) -> None:
        """Silently reset cumulative counters after a long clean period.

        If the strategy has been in CLOSED state for longer than
        ``reset_timeout`` seconds since its last failure, the
        ``consecutive_failures`` and ``total_loss`` counters are zeroed.

        Must be called with ``self._lock`` held.
        """
        if record.state != StrategyCircuitBreakerState.CLOSED:
            return
        if record.consecutive_failures == 0 and record.total_loss >= 0.0:
            return  # Nothing to reset
        elapsed = (
            datetime.now(UTC) - record.last_failure_time
        ).total_seconds()
        if elapsed >= self._config.reset_timeout:
            record.consecutive_failures = 0
            record.total_loss = 0.0
            logger.debug(
                f"Strategy {record.strategy_id!r} counters reset after "
                f"{elapsed:.0f}s clean period"
            )

    def _trip_circuit(self, record: StrategyFailureRecord, reason: str) -> None:
        """Move *record* to OPEN and emit a warning log.

        Must be called with ``self._lock`` held.
        """
        record.state = StrategyCircuitBreakerState.OPEN
        record.tripped_at = datetime.now(UTC)
        logger.warning(
            f"CIRCUIT TRIPPED for strategy {record.strategy_id!r} – {reason}. "
            f"consecutive_failures={record.consecutive_failures}, "
            f"total_loss={record.total_loss:.2f}. "
            f"Recovery in {self._config.recovery_timeout:.0f}s."
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_allowed(self, strategy_id: str) -> bool:
        """Return *True* if the strategy is permitted to trade.

        Triggers the automatic OPEN → HALF_OPEN transition when the
        recovery timeout has elapsed so that the caller can proceed with
        a probe trade.

        Args:
            strategy_id: Strategy identifier.

        Returns:
            ``True`` when the circuit is CLOSED or HALF_OPEN (probe
            permitted).  ``False`` when OPEN.
        """
        with self._lock:
            record = self._get_or_create(strategy_id)
            self._check_auto_transition(record)
            allowed = record.state != StrategyCircuitBreakerState.OPEN
            if not allowed:
                tripped_secs = (
                    (datetime.now(UTC) - record.tripped_at).total_seconds()
                    if record.tripped_at
                    else 0.0
                )
                remaining = max(
                    0.0, self._config.recovery_timeout - tripped_secs
                )
                logger.debug(
                    f"Strategy {strategy_id!r} blocked – circuit OPEN "
                    f"(retry in {remaining:.1f}s)"
                )
            return allowed

    def record_success(self, strategy_id: str) -> None:
        """Record a successful strategy execution.

        In HALF_OPEN this closes the circuit.  In CLOSED this resets the
        consecutive failure counter and, if applicable, the reset-timeout
        counter.

        Args:
            strategy_id: Strategy identifier.
        """
        with self._lock:
            record = self._get_or_create(strategy_id)
            prev_state = record.state

            record.consecutive_failures = 0

            if prev_state == StrategyCircuitBreakerState.HALF_OPEN:
                record.state = StrategyCircuitBreakerState.CLOSED
                record.tripped_at = None
                logger.info(
                    f"Strategy {strategy_id!r} circuit → CLOSED "
                    f"(recovered after {record.recovery_attempts} probe attempt(s))"
                )
            elif prev_state == StrategyCircuitBreakerState.CLOSED:
                self._check_reset_timeout(record)
                logger.debug(
                    "Strategy %r recorded success (circuit CLOSED)", strategy_id
                )

    def record_failure(
        self,
        strategy_id: str,
        reason: str,
        pnl_impact: float = 0.0,
    ) -> None:
        """Record a strategy failure and conditionally trip the circuit.

        The circuit is tripped (→ OPEN) when either:
        - ``consecutive_failures`` reaches ``failure_threshold``, or
        - ``total_loss`` drops at or below ``loss_threshold``.

        A failure in HALF_OPEN immediately re-opens the circuit.

        Args:
            strategy_id: Strategy identifier.
            reason: Short human-readable description of the failure.
            pnl_impact: Dollar P&L change caused by this failure event
                (negative = loss).  This is *added* to ``total_loss``.
        """
        with self._lock:
            record = self._get_or_create(strategy_id)

            record.failure_count += 1
            record.consecutive_failures += 1
            record.last_failure_time = datetime.now(UTC)
            record.last_failure_reason = reason

            if pnl_impact != 0.0:
                record.total_loss += pnl_impact

            logger.debug(
                f"Strategy {strategy_id!r} failure #{record.failure_count} "
                f"(consecutive={record.consecutive_failures}, "
                f"total_loss={record.total_loss:.2f}): {reason}"
            )

            # HALF_OPEN probe failed – re-open immediately
            if record.state == StrategyCircuitBreakerState.HALF_OPEN:
                self._trip_circuit(
                    record,
                    f"probe failed in HALF_OPEN: {reason}",
                )
                return

            # Already OPEN – just update counters, no re-trip needed
            if record.state == StrategyCircuitBreakerState.OPEN:
                return

            # CLOSED – check whether either threshold has been breached
            consecutive_breached = (
                record.consecutive_failures >= self._config.failure_threshold
            )
            loss_breached = (
                self._config.loss_threshold < 0
                and record.total_loss <= self._config.loss_threshold
            )

            if consecutive_breached:
                self._trip_circuit(
                    record,
                    f"consecutive failure threshold "
                    f"({self._config.failure_threshold}) reached",
                )
            elif loss_breached:
                self._trip_circuit(
                    record,
                    f"loss threshold ({self._config.loss_threshold:.2f}) breached "
                    f"(total_loss={record.total_loss:.2f})",
                )

    def record_pnl(self, strategy_id: str, pnl: float) -> None:
        """Track a P&L update for a strategy without recording a failure event.

        Useful for updating cumulative loss from fill callbacks or mark-to-
        market events independently of discrete failure signals.  If the
        cumulative loss crosses ``loss_threshold`` the circuit is tripped.

        Args:
            strategy_id: Strategy identifier.
            pnl: Dollar P&L delta (negative = loss, positive = gain).
        """
        with self._lock:
            record = self._get_or_create(strategy_id)
            record.total_loss += pnl

            logger.debug(
                f"Strategy {strategy_id!r} P&L update: {pnl:+.2f} "
                f"(cumulative total_loss={record.total_loss:.2f})"
            )

            if (
                record.state == StrategyCircuitBreakerState.CLOSED
                and self._config.loss_threshold < 0
                and record.total_loss <= self._config.loss_threshold
            ):
                record.consecutive_failures = 0  # loss-only trip
                self._trip_circuit(
                    record,
                    f"loss threshold ({self._config.loss_threshold:.2f}) breached "
                    f"via P&L update (total_loss={record.total_loss:.2f})",
                )

    def get_state(self, strategy_id: str) -> StrategyCircuitBreakerState:
        """Return the current circuit state for *strategy_id*.

        If the strategy has not been seen before, it is registered as CLOSED.

        Args:
            strategy_id: Strategy identifier.

        Returns:
            Current ``StrategyCircuitBreakerState``.
        """
        with self._lock:
            record = self._get_or_create(strategy_id)
            self._check_auto_transition(record)
            return record.state

    def get_all_states(self) -> dict[str, StrategyFailureRecord]:
        """Return a shallow copy of all per-strategy records.

        Returns:
            Dict mapping strategy_id → ``StrategyFailureRecord``.  The
            values are the live record objects – callers should not mutate
            them.
        """
        with self._lock:
            for record in self._records.values():
                self._check_auto_transition(record)
            return dict(self._records)

    def manually_reset(self, strategy_id: str) -> None:
        """Operator override: force a strategy circuit back to CLOSED.

        Resets all failure counters, loss accumulator, and clears the
        tripped timestamp.  Use after a code fix or manual review has
        confirmed the strategy is safe to resume.

        Args:
            strategy_id: Strategy identifier.
        """
        with self._lock:
            record = self._get_or_create(strategy_id)
            prev_state = record.state
            record.state = StrategyCircuitBreakerState.CLOSED
            record.consecutive_failures = 0
            record.total_loss = 0.0
            record.tripped_at = None
            record.recovery_attempts = 0
            record.last_failure_reason = ""
            logger.warning(
                f"Strategy {strategy_id!r} circuit MANUALLY RESET "
                f"(was {prev_state.name})"
            )

    def get_status_report(self) -> str:
        """Return a human-readable status report for all tracked strategies.

        Returns:
            Multi-line string suitable for logging or display in a health
            dashboard.
        """
        with self._lock:
            if not self._records:
                return "StrategyCircuitBreaker: no strategies registered."

            lines: list[str] = [
                "=" * 60,
                "STRATEGY CIRCUIT BREAKER STATUS",
                f"  Config: failure_threshold={self._config.failure_threshold}, "
                f"loss_threshold={self._config.loss_threshold:.2f}, "
                f"recovery_timeout={self._config.recovery_timeout:.0f}s",
                "-" * 60,
            ]

            for strategy_id, record in sorted(self._records.items()):
                self._check_auto_transition(record)
                state_label = record.state.name

                tripped_info = ""
                if record.tripped_at is not None:
                    elapsed = (
                        datetime.now(UTC) - record.tripped_at
                    ).total_seconds()
                    if record.state == StrategyCircuitBreakerState.OPEN:
                        remaining = max(
                            0.0, self._config.recovery_timeout - elapsed
                        )
                        tripped_info = (
                            f" | tripped {elapsed:.0f}s ago"
                            f" | retry in {remaining:.0f}s"
                        )
                    else:
                        tripped_info = f" | tripped {elapsed:.0f}s ago"

                lines.append(
                    f"  [{state_label:<9}] {strategy_id}"
                    f" | failures={record.failure_count}"
                    f" | consec={record.consecutive_failures}"
                    f" | loss={record.total_loss:.2f}"
                    f" | probes={record.recovery_attempts}"
                    + tripped_info
                )
                if record.last_failure_reason:
                    lines.append(
                        f"             last_reason: {record.last_failure_reason}"
                    )

            lines.append("=" * 60)
            return "\n".join(lines)


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================

_strategy_circuit_breaker: StrategyCircuitBreaker | None = None
_singleton_lock: threading.Lock = threading.Lock()


def get_strategy_circuit_breaker(
    config: StrategyCircuitBreakerConfig | None = None,
) -> StrategyCircuitBreaker:
    """Return the process-wide ``StrategyCircuitBreaker`` singleton.

    The instance is created on the first call.  Subsequent calls ignore
    the *config* argument and return the already-initialised instance.

    Args:
        config: Optional configuration for the singleton.  Only applied
            on the very first call.

    Returns:
        The singleton ``StrategyCircuitBreaker``.
    """
    global _strategy_circuit_breaker
    with _singleton_lock:
        if _strategy_circuit_breaker is None:
            _strategy_circuit_breaker = StrategyCircuitBreaker(config=config)
    return _strategy_circuit_breaker


# ==============================================================================
# PUBLIC EXPORTS
# ==============================================================================

__all__ = [
    "StrategyCircuitBreakerState",
    "StrategyFailureRecord",
    "StrategyCircuitBreakerConfig",
    "StrategyCircuitBreaker",
    "get_strategy_circuit_breaker",
]


# ==============================================================================
# USAGE EXAMPLE
# ==============================================================================

if __name__ == "__main__":
    import time

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    )

    # ------------------------------------------------------------------ setup
    config = StrategyCircuitBreakerConfig(
        failure_threshold=3,
        loss_threshold=-200.0,
        recovery_timeout=5.0,   # short timeout for the demo
        half_open_max_attempts=3,
        reset_timeout=60.0,
    )
    scb = StrategyCircuitBreaker(config=config)

    STRATEGY = "iron_condor_SPY"

    # ------------------------------------------------------------------ normal operation
    print("\n--- Normal operation ---")  # noqa: T201
    for i in range(2):
        if scb.is_allowed(STRATEGY):
            print(f"  Trade {i + 1}: allowed")  # noqa: T201
            scb.record_success(STRATEGY)

    # ------------------------------------------------------------------ trip via consecutive failures  # noqa: E501
    print("\n--- Injecting 3 consecutive failures (threshold=3) ---")  # noqa: T201
    for i in range(3):
        if scb.is_allowed(STRATEGY):
            scb.record_failure(
                STRATEGY,
                reason=f"order rejected ({i + 1})",
                pnl_impact=-30.0,
            )
        else:
            print(f"  Trade {i + 1}: BLOCKED (circuit open)")  # noqa: T201

    print(f"\n  State after failures: {scb.get_state(STRATEGY).name}")  # noqa: T201
    print(f"\n  is_allowed now: {scb.is_allowed(STRATEGY)}")  # noqa: T201

    # ------------------------------------------------------------------ wait for recovery
    print(f"\n--- Waiting {config.recovery_timeout + 1:.0f}s for HALF_OPEN transition ---")  # noqa: T201
    time.sleep(config.recovery_timeout + 1)

    print(f"  State after timeout: {scb.get_state(STRATEGY).name}")  # noqa: T201
    print(f"  is_allowed (HALF_OPEN probe): {scb.is_allowed(STRATEGY)}")  # noqa: T201

    # ------------------------------------------------------------------ successful probe closes circuit  # noqa: E501
    print("\n--- Recording success in HALF_OPEN ---")  # noqa: T201
    scb.record_success(STRATEGY)
    print(f"  State after success: {scb.get_state(STRATEGY).name}")  # noqa: T201

    # ------------------------------------------------------------------ trip via P&L loss
    LOSS_STRATEGY = "put_spread_QQQ"
    print(f"\n--- Tripping {LOSS_STRATEGY!r} via P&L loss (threshold=-200) ---")  # noqa: T201
    scb.record_pnl(LOSS_STRATEGY, pnl=-150.0)
    print(f"  After -150: {scb.get_state(LOSS_STRATEGY).name}")  # noqa: T201
    scb.record_pnl(LOSS_STRATEGY, pnl=-80.0)
    print(f"  After -80 more: {scb.get_state(LOSS_STRATEGY).name}")  # noqa: T201

    # ------------------------------------------------------------------ manual reset
    print(f"\n--- Manually resetting {LOSS_STRATEGY!r} ---")  # noqa: T201
    scb.manually_reset(LOSS_STRATEGY)
    print(f"  State after reset: {scb.get_state(LOSS_STRATEGY).name}")  # noqa: T201

    # ------------------------------------------------------------------ status report
    print("\n--- Full status report ---")  # noqa: T201
    print(scb.get_status_report())  # noqa: T201
