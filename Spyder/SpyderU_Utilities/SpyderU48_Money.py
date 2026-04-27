"""A22/O4 (v14): Decimal-backed Money type for cent-precise accounting.

Floating-point P&L accumulators drift: summing ten thousand fills with
prices like 0.10 will not equal 1000.00 exactly. ``Money`` scales all
arithmetic to integer cents via :class:`decimal.Decimal` so accumulation is
exact, and converts back to float only at display boundaries.

v14 scope: used **only** in ``E13_DayProfitTarget`` for the account-wide
kill-switch accumulator — the one site where a few-cent drift can toggle
the day's trading state. Broader rollout tracked as A22-followup.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

__all__ = ["Money", "ZERO"]

_TWOPLACES = Decimal("0.01")
_Numeric = Union[int, float, str, Decimal, "Money"]


def _to_decimal(value: _Numeric) -> Decimal:
    if isinstance(value, Money):
        return value._amount
    if isinstance(value, Decimal):
        return value.quantize(_TWOPLACES, rounding=ROUND_HALF_UP)
    # Go through str to avoid float representation surprises (e.g. 0.1).
    return Decimal(str(value)).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)


class Money:
    """Immutable cent-precise monetary amount."""

    __slots__ = ("_amount",)

    def __init__(self, value: _Numeric = 0) -> None:
        object.__setattr__(self, "_amount", _to_decimal(value))

    # Arithmetic — every op returns a new Money, preserving immutability.
    def __add__(self, other: _Numeric) -> "Money":
        return Money(self._amount + _to_decimal(other))

    def __radd__(self, other: _Numeric) -> "Money":
        return self.__add__(other)

    def __sub__(self, other: _Numeric) -> "Money":
        return Money(self._amount - _to_decimal(other))

    def __rsub__(self, other: _Numeric) -> "Money":
        return Money(_to_decimal(other) - self._amount)

    def __neg__(self) -> "Money":
        return Money(-self._amount)

    def __mul__(self, scalar: _Numeric) -> "Money":
        # Multiplication by a scalar (quantity / price) — not by Money.
        if isinstance(scalar, Money):
            raise TypeError("Cannot multiply Money by Money")
        return Money(self._amount * _to_decimal(scalar))

    __rmul__ = __mul__

    # Comparisons
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Money):
            return self._amount == other._amount
        if isinstance(other, (int, float, Decimal)):
            return self._amount == _to_decimal(other)
        return NotImplemented

    def __lt__(self, other: _Numeric) -> bool:
        return self._amount < _to_decimal(other)

    def __le__(self, other: _Numeric) -> bool:
        return self._amount <= _to_decimal(other)

    def __gt__(self, other: _Numeric) -> bool:
        return self._amount > _to_decimal(other)

    def __ge__(self, other: _Numeric) -> bool:
        return self._amount >= _to_decimal(other)

    def __hash__(self) -> int:
        return hash(self._amount)

    # Display boundary
    def to_float(self) -> float:
        """Convert to float — ONLY at display / external-API boundaries."""
        return float(self._amount)

    def to_decimal(self) -> Decimal:
        return self._amount

    def __repr__(self) -> str:
        return f"Money({self._amount})"

    def __str__(self) -> str:
        return f"${self._amount:.2f}"


ZERO = Money(0)
