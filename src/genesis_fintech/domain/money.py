"""Bounded Decimal conversion, independent of the caller's Decimal context."""

from decimal import Context, Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext

from .models import DataError, ROUNDINGS, integer, rate_string


def convert_minor(amount_minor: int, source_exponent: int, target_exponent: int,
                  rate: str, rounding: str = "ROUND_HALF_EVEN") -> int:
    integer(amount_minor, "amount_minor")
    integer(source_exponent, "source_exponent", 0, 6)
    integer(target_exponent, "target_exponent", 0, 6)
    rate_string(rate)
    if type(rounding) is not str or rounding not in ROUNDINGS:
        raise DataError("rounding: unsupported")
    mode = ROUND_HALF_EVEN if rounding == "ROUND_HALF_EVEN" else ROUND_HALF_UP
    with localcontext(Context(prec=80, rounding=mode)):
        result = (Decimal(amount_minor) * Decimal(rate) * (Decimal(10) ** (target_exponent - source_exponent)))
        converted = int(result.quantize(Decimal(1)))
    return integer(converted, "converted amount")
