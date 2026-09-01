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
    income = [IncomeItem(kind="dividend", amount=200, year=2024)]
    result = offset_year(sales, income)
    assert result.transfer_net == 0
    assert result.dividend_net == 200
