from decimal import Decimal

from scripts.estimate import estimate_tax
from scripts.models import IncomeItem, OffsetResult
from scripts.offset import offset_year


def test_foreign_tax_credit_within_limit():
    taxed = estimate_tax(OffsetResult(transfer_net=0, dividend_net=1000, dividend_foreign_tax_paid=100))
    assert taxed.dividend_gross_tax == Decimal("200.00")
    assert taxed.dividend_credit == Decimal("100.00")
    assert taxed.dividend_tax == Decimal("100.00")


def test_foreign_tax_credit_is_capped_at_gross_tax_when_over_limit():
    # 美股 30% 预扣 > 中国 20%：最多抵到 20%，补税为 0，不会出现负数退税。
    taxed = estimate_tax(OffsetResult(transfer_net=0, dividend_net=1000, dividend_foreign_tax_paid=300))
    assert taxed.dividend_gross_tax == Decimal("200.00")
    assert taxed.dividend_credit == Decimal("200.00")
    assert taxed.dividend_tax == 0
    assert taxed.tax_due == 0


def test_excess_credit_does_not_spill_into_other_categories():
    taxed = estimate_tax(
        OffsetResult(transfer_net=500, dividend_net=100, interest_net=50, dividend_foreign_tax_paid=999)
    )
    assert taxed.dividend_tax == 0
    assert taxed.interest_tax == Decimal("10.00")
    assert taxed.transfer_tax == Decimal("100.00")
    assert taxed.tax_due == Decimal("110.00")


def test_withholding_only_item_counts_toward_dividend_credit():
    income = [
        IncomeItem(kind="dividend", amount=100, year=2024, currency="USD"),
        IncomeItem(kind="dividend", amount=0, foreign_tax_paid=10, year=2024, currency="USD"),
    ]
    taxed = estimate_tax(offset_year([], income, target_year=2024))
    assert taxed.dividend_credit == Decimal("10.00")
    assert taxed.dividend_tax == Decimal("10.00")


def test_estimate_per_currency_bucket_without_fx():
    income = [
        IncomeItem(kind="dividend", amount=100, year=2024, currency="USD", foreign_tax_paid=30),
        IncomeItem(kind="dividend", amount=100, year=2024, currency="HKD"),
    ]
    taxed = estimate_tax(offset_year([], income, target_year=2024))
    assert taxed.tax_due is None
    assert taxed.by_currency["USD"].tax_due == 0
    assert taxed.by_currency["HKD"].tax_due == Decimal("20.00")


def test_legacy_rates_still_twenty_percent():
    taxed = estimate_tax(OffsetResult(transfer_net=500, dividend_net=200))
    assert taxed.transfer_tax == 100
    assert taxed.dividend_tax == 40
