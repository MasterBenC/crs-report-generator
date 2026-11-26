from scripts.matching import match_trades
from scripts.models import Trade


def test_matches_same_symbol_buy_before_sell():
    trades = [
        Trade(side="buy", symbol="AAPL", qty=10, price=100, amount=1000, currency="USD", date="2024-01-10", source="a.pdf"),
        Trade(side="sell", symbol="AAPL", qty=10, price=120, amount=1200, currency="USD", date="2024-06-01", source="b.pdf"),
    ]
    matched, unmatched = match_trades(trades)
    assert len(matched) == 1
    assert matched[0].gain == 200
    assert unmatched == []


def test_unmatched_sell_is_not_priced():
    trades = [
        Trade(side="sell", symbol="TSLA", qty=5, price=200, amount=1000, currency="USD", date="2024-06-01", source="b.pdf"),
    ]
    matched, unmatched = match_trades(trades)
    assert matched == []
    assert len(unmatched) == 1
    assert unmatched[0].estimated_cost is None


from decimal import Decimal


def test_fees_are_added_to_cost_and_deducted_from_proceeds():
    trades = [
        Trade(side="buy", symbol="AAA", qty=100, amount=1000, fees=10, currency="HKD", date="2024-01-02", source="a"),
        Trade(side="sell", symbol="AAA", qty=100, amount=1500, fees=15, currency="HKD", date="2024-03-01", source="b"),
    ]
    matched, unmatched = match_trades(trades)
    assert unmatched == []
    assert matched[0].cost == Decimal("1010")
    assert matched[0].proceeds == Decimal("1485")
    assert matched[0].gain == Decimal("475")
    assert matched[0].fees == Decimal("25")


def test_partial_match_allocates_fees_pro_rata():
    trades = [
        Trade(side="buy", symbol="AAA", qty=10, amount=100, fees=2, currency="HKD", date="2024-01-02", source="a"),
        Trade(side="sell", symbol="AAA", qty=4, amount=60, fees=1, currency="HKD", date="2024-03-01", source="b"),
    ]
    matched, _ = match_trades(trades)
    assert matched[0].cost == Decimal("40.8")
    assert matched[0].proceeds == Decimal("59")


def test_same_day_buy_and_sell_in_reverse_record_order_still_match():
    trades = [
        Trade(side="sell", symbol="AAA", qty=10, amount=120, currency="USD", date="2024-05-06", source="t"),
        Trade(side="buy", symbol="AAA", qty=10, amount=100, currency="USD", date="2024-05-06", source="t"),
    ]
    matched, unmatched = match_trades(trades)
    assert unmatched == []
    assert matched[0].gain == 20


def test_same_day_keeps_original_order_among_buys():
    trades = [
        Trade(side="buy", symbol="AAA", qty=1, amount=10, currency="USD", date="2024-05-06", source="first"),
        Trade(side="buy", symbol="AAA", qty=1, amount=30, currency="USD", date="2024-05-06", source="second"),
        Trade(side="sell", symbol="AAA", qty=1, amount=20, currency="USD", date="2024-05-06", source="s"),
    ]
    matched, _ = match_trades(trades)
    assert matched[0].buy.source == "first"


def test_fractional_shares_fifo_has_no_float_residue():
    trades = [
        Trade(side="buy", symbol="FRAC", qty=0.1, amount=10, currency="USD", date="2024-01-01", source="a"),
        Trade(side="buy", symbol="FRAC", qty=0.2, amount=20, currency="USD", date="2024-01-02", source="a"),
        Trade(side="sell", symbol="FRAC", qty=0.3, amount=36, currency="USD", date="2024-02-01", source="b"),
    ]
    assert 0.1 + 0.2 != 0.3  # 浮点残差确实存在
    matched, unmatched = match_trades(trades)
    assert unmatched == []
    assert [m.qty for m in matched] == [Decimal("0.1"), Decimal("0.2")]
    assert sum(m.gain for m in matched) == Decimal("6")


def test_different_currencies_never_match_each_other():
    trades = [
        Trade(side="buy", symbol="AAA", qty=10, amount=100, currency="HKD", date="2024-01-01", source="a"),
        Trade(side="sell", symbol="AAA", qty=10, amount=20, currency="USD", date="2024-02-01", source="b"),
    ]
    matched, unmatched = match_trades(trades)
    assert matched == []
    assert unmatched[0].estimated_cost is None


def test_earlier_year_buy_is_used_for_fifo():
    trades = [
        Trade(side="buy", symbol="AAA", qty=5, amount=50, currency="HKD", date="2022-12-30", source="a"),
        Trade(side="sell", symbol="AAA", qty=5, amount=70, currency="HKD", date="2024-01-03", source="b"),
    ]
    matched, unmatched = match_trades(trades)
    assert unmatched == []
    assert matched[0].year == 2024
