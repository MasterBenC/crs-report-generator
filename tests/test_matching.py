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
