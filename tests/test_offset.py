from scripts.offset import offset_year
from scripts.models import IncomeItem, MatchedSale, Trade


def matched_sale(symbol: str, gain: float, year: int) -> MatchedSale:
    trade = Trade(
        side="sell",
        symbol=symbol,
        qty=1,
        amount=0,
        currency="USD",
        date=f"{year}-01-01",
        source="test",
    )
    return MatchedSale(
        sale=trade,
        buy=trade,
        qty=1,
        proceeds=0,
        cost=0,
        gain=gain,
        year=year,
    )


def test_stock_gain_and_loss_offset_within_year():
    sales = [
        matched_sale(symbol="AAA", gain=800, year=2024),
        matched_sale(symbol="BBB", gain=-300, year=2024),
    ]
    result = offset_year(sales, [])
    assert result.transfer_net == 500
    assert result.dividend_net == 0


def test_loss_does_not_reduce_dividends():
    sales = [matched_sale(symbol="AAA", gain=-300, year=2024)]
    # v3.1.0：收入要带币种，否则会和 USD 卖出分成两个桶（不跨币种相加）。
    income = [IncomeItem(kind="dividend", amount=200, year=2024, currency="USD")]
    result = offset_year(sales, income)
    assert result.transfer_net == 0
    assert result.dividend_net == 200


from decimal import Decimal

from scripts.models import FX_MISSING_NOTE


def sale_in(currency: str, gain, date: str) -> MatchedSale:
    trade = Trade(side="sell", symbol="X", qty=1, amount=0, currency=currency, date=date, source="t")
    return MatchedSale(sale=trade, buy=trade, qty=Decimal(1), proceeds=Decimal(0), cost=Decimal(0), gain=Decimal(str(gain)), currency=currency)


def test_target_year_excludes_other_years_sales_and_income():
    sales = [
        sale_in("HKD", 100, "2023-12-31"),
        sale_in("HKD", 300, "2024-06-30"),
        sale_in("HKD", -50, "2025-01-01"),
    ]
    income = [
        IncomeItem(kind="dividend", amount=70, year=2023, currency="HKD"),
        IncomeItem(kind="dividend", amount=40, year=2024, currency="HKD"),
        IncomeItem(kind="interest", amount=9, year=2025, currency="HKD"),
    ]
    result = offset_year(sales, income, target_year=2024)
    assert result.transfer_net == 300
    assert result.dividend_net == 40
    assert result.interest_net == 0
    assert result.year == 2024


def test_without_fx_currencies_are_bucketed_not_added():
    sales = [sale_in("HKD", 100, "2024-01-01"), sale_in("USD", 10, "2024-02-01")]
    income = [IncomeItem(kind="dividend", amount=5, year=2024, currency="USD")]
    result = offset_year(sales, income, target_year=2024)
    assert result.is_split
    assert result.transfer_net is None  # 顶层不给跨币种合计
    assert result.by_currency["HKD"].transfer_net == 100
    assert result.by_currency["USD"].transfer_net == 10
    assert result.by_currency["USD"].dividend_net == 5
    assert FX_MISSING_NOTE in result.notes


def test_loss_in_one_currency_does_not_offset_gain_in_another_without_fx():
    sales = [sale_in("HKD", 100, "2024-01-01"), sale_in("USD", -100, "2024-02-01")]
    result = offset_year(sales, [], target_year=2024)
    assert result.by_currency["HKD"].transfer_net == 100
    assert result.by_currency["USD"].transfer_net == 0


def test_with_fx_everything_is_converted_to_cny_before_offset():
    sales = [sale_in("HKD", 100, "2024-01-01"), sale_in("USD", -10, "2024-02-01")]
    income = [IncomeItem(kind="dividend", amount=10, year=2024, currency="USD", foreign_tax_paid=1)]
    result = offset_year(sales, income, target_year=2024, fx_rates={"HKD": "0.92", "usd": 7.2})
    assert not result.is_split
    assert result.currency == "CNY"
    assert result.fx_converted
    assert result.transfer_net == Decimal("20.00")  # 92 - 72
    assert result.dividend_net == Decimal("72.0")
    assert result.dividend_foreign_tax_paid == Decimal("7.2")
    assert FX_MISSING_NOTE not in result.notes


def test_missing_rate_is_listed_separately_not_treated_as_one():
    sales = [sale_in("HKD", 100, "2024-01-01"), sale_in("JPY", 1000, "2024-02-01")]
    result = offset_year(sales, [], target_year=2024, fx_rates={"HKD": 0.92})
    assert result.missing_fx == ["JPY"]
    assert result.is_split
    assert result.by_currency["CNY"].transfer_net == Decimal("92.00")
    assert result.by_currency["JPY"].transfer_net == 1000
    assert any("JPY" in note for note in result.notes)


def test_cny_needs_no_rate():
    result = offset_year([sale_in("CNY", 10, "2024-01-01")], [], target_year=2024, fx_rates={"HKD": 0.9})
    assert result.currency == "CNY"
    assert result.missing_fx == []
