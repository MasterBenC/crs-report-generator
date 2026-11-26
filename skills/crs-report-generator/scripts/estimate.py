from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal

from scripts.models import CENT, OffsetResult, to_decimal

DIVIDEND_RATE = Decimal("0.20")
INTEREST_RATE = Decimal("0.20")
TRANSFER_RATE = Decimal("0.20")
ZERO = Decimal("0")


def _tax(base, rate: Decimal) -> Decimal:
    return (max(to_decimal(base), ZERO) * rate).quantize(CENT, rounding=ROUND_HALF_UP)


def _credit(foreign_tax_paid, gross_tax: Decimal) -> Decimal:
    # 每类所得可抵免额不超过该类所得按 20% 算出的应纳税额。
    paid = abs(to_decimal(foreign_tax_paid)).quantize(CENT, rounding=ROUND_HALF_UP)
    return min(paid, gross_tax)


def _estimate_bucket(offset: OffsetResult) -> OffsetResult:
    dividend_gross = _tax(offset.dividend_net, DIVIDEND_RATE)
    interest_gross = _tax(offset.interest_net, INTEREST_RATE)
    transfer_gross = _tax(offset.transfer_net, TRANSFER_RATE)
    dividend_credit = _credit(offset.dividend_foreign_tax_paid, dividend_gross)
    interest_credit = _credit(offset.interest_foreign_tax_paid, interest_gross)
    return replace(
        offset,
        dividend_gross_tax=dividend_gross,
        interest_gross_tax=interest_gross,
        transfer_gross_tax=transfer_gross,
        dividend_credit=dividend_credit,
        interest_credit=interest_credit,
        dividend_tax=dividend_gross - dividend_credit,
        interest_tax=interest_gross - interest_credit,
        transfer_tax=transfer_gross,
        estimated=True,
        by_currency={},
        notes=list(offset.notes),
        missing_fx=list(offset.missing_fx),
    )


def estimate_tax(offset: OffsetResult) -> OffsetResult:
    """按币种桶分别测算；多币种未折算时顶层不出合计。"""
    if not offset.by_currency:
        return _estimate_bucket(offset)
    buckets = {label: _estimate_bucket(bucket) for label, bucket in offset.by_currency.items()}
    if len(buckets) == 1:
        only = next(iter(buckets.values()))
        return replace(
            only,
            year=offset.year,
            fx_converted=offset.fx_converted,
            missing_fx=list(offset.missing_fx),
            notes=list(offset.notes),
            by_currency=buckets,
        )
    return replace(offset, estimated=True, by_currency=buckets, notes=list(offset.notes), missing_fx=list(offset.missing_fx))
