from scripts.models import Trade, Gap


def test_unmatched_sale_is_a_gap_not_an_estimate():
    sale = Trade(side="sell", symbol="AAPL", qty=10, amount=1000, currency="USD", date="2024-06-01", source="htsc.pdf")
    gap = Gap(kind="missing_buy", trade=sale, message="还缺买入记录")
    assert gap.kind == "missing_buy"
    assert gap.trade.symbol == "AAPL"
    assert "估" not in gap.message
