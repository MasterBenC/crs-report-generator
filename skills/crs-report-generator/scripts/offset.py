from decimal import Decimal

from scripts.fx import BASE_CURRENCY, normalize_rates, rate_for
from scripts.models import (
    FX_MISSING_NOTE,
    UNKNOWN_CURRENCY_LABEL,
    IncomeItem,
    MatchedSale,
    OffsetResult,
    to_decimal,
    year_of,
)

ZERO = Decimal("0")


def _sale_year(sale: MatchedSale) -> int | None:
    return year_of(sale.sale.date) if sale.sale.date else sale.year


def _bucket_label(currency: str | None) -> str:
    return currency.strip().upper() if currency else UNKNOWN_CURRENCY_LABEL


def offset_year(
    matched_sales: list[MatchedSale],
    income_items: list[IncomeItem],
    target_year: int | None = None,
    fx_rates: dict | None = None,
) -> OffsetResult:
    """年内盈亏互抵。

    - target_year: 只统计卖出日期 / 收入所属年度等于该年的记录；
      更早年份的买入只在匹配阶段用来提供成本，不会把别的年份的盈亏或分红算进来。
    - fx_rates: 提供时统一折算为 CNY 再互抵；缺某币种汇率的记录单独按原币种列出。
      不提供时按币种分桶，不同币种绝不相加。
    """
    rates = normalize_rates(fx_rates)
    buckets: dict[str, dict[str, Decimal]] = {}
    missing_fx: set[str] = set()

    def bucket_for(currency: str | None) -> tuple[str, Decimal]:
        if rates is not None:
            rate = rate_for(currency, rates)
            if rate is not None:
                return BASE_CURRENCY, rate
            missing_fx.add(_bucket_label(currency))
        return _bucket_label(currency), Decimal("1")

    def add(currency: str | None, field_name: str, amount: Decimal) -> None:
        label, rate = bucket_for(currency)
        bucket = buckets.setdefault(
            label,
            {"gain": ZERO, "dividend": ZERO, "interest": ZERO, "dividend_ftp": ZERO, "interest_ftp": ZERO},
        )
        bucket[field_name] += amount * rate

    for sale in matched_sales:
        if target_year is not None and _sale_year(sale) != target_year:
            continue
        add(sale.currency if sale.currency is not None else sale.sale.currency, "gain", to_decimal(sale.gain))

    for item in income_items:
        if target_year is not None and item.year != target_year:
            continue
        if item.kind not in {"dividend", "interest"}:
            continue
        add(item.currency, item.kind, to_decimal(item.amount))
        add(item.currency, f"{item.kind}_ftp", abs(to_decimal(item.foreign_tax_paid)))

    notes: list[str] = []
    if rates is None and any(label != BASE_CURRENCY for label in buckets):
        notes.append(FX_MISSING_NOTE)
    if missing_fx:
        notes.append(
            "汇率表缺少 " + "、".join(sorted(missing_fx)) + " 的汇率，这部分按原币种单列，没有算进人民币合计"
        )

    by_currency = {
        label: OffsetResult(
            transfer_net=max(values["gain"], ZERO),
            dividend_net=values["dividend"],
            interest_net=values["interest"],
            dividend_foreign_tax_paid=values["dividend_ftp"],
            interest_foreign_tax_paid=values["interest_ftp"],
            currency=label,
            year=target_year,
            fx_converted=label == BASE_CURRENCY and rates is not None,
        )
        for label, values in buckets.items()
    }

    common = dict(
        year=target_year,
        fx_converted=rates is not None and not missing_fx,
        missing_fx=sorted(missing_fx),
        notes=notes,
        by_currency=by_currency,
    )
    if len(by_currency) > 1:
        # 多个币种且无法统一折算：顶层不给合计，严禁跨币种相加。
        return OffsetResult(
            transfer_net=None,
            dividend_net=None,
            interest_net=None,
            dividend_tax=None,
            transfer_tax=None,
            interest_tax=None,
            dividend_foreign_tax_paid=None,
            interest_foreign_tax_paid=None,
            dividend_gross_tax=None,
            interest_gross_tax=None,
            transfer_gross_tax=None,
            dividend_credit=None,
            interest_credit=None,
            currency=None,
            **common,
        )
    if by_currency:
        only = next(iter(by_currency.values()))
        return OffsetResult(
            transfer_net=only.transfer_net,
            dividend_net=only.dividend_net,
            interest_net=only.interest_net,
            dividend_foreign_tax_paid=only.dividend_foreign_tax_paid,
            interest_foreign_tax_paid=only.interest_foreign_tax_paid,
            currency=only.currency,
            **common,
        )
    return OffsetResult(
        transfer_net=ZERO,
        dividend_net=ZERO,
        interest_net=ZERO,
        currency=BASE_CURRENCY if rates is not None else None,
        **common,
    )
