"""Published reporting-period and payment-date FX rules, using only public data."""

from zoneinfo import ZoneInfo

from .models import DataError, timestamp
from .money import convert_minor


def in_period(manifest, at: str) -> bool:
    return timestamp(manifest.period_start) <= timestamp(at) < timestamp(manifest.period_end)


def payment_date(manifest, at: str) -> str:
    return timestamp(at).astimezone(ZoneInfo(manifest.timezone)).date().isoformat()


def payment_quote(public, payment):
    if payment.currency == public.manifest.base_currency:
        return None
    key = (payment_date(public.manifest, payment.timestamp), payment.currency, public.manifest.base_currency)
    quotes = [rate for rate in public.fx if (rate.date, rate.source_currency, rate.target_currency) == key]
    if len(quotes) != 1:
        raise DataError("payment requires exactly one FX quote on its local policy date")
    return quotes[0]


def payment_value_minor(public, payment) -> int:
    exponents = public.manifest.currency_exponents
    if payment.currency not in exponents:
        raise DataError("payment currency exponent is missing")
    quote = payment_quote(public, payment)
    if quote is None:
        return payment.amount_minor
    return convert_minor(payment.amount_minor, exponents[payment.currency],
                         exponents[public.manifest.base_currency], quote.rate, public.policy.rounding)
