from scripts.pipeline import run_pipeline
from scripts.models import Trade, IncomeItem


def test_pipeline_excludes_unmatched_sell_from_tax_due():
    trades = [
        Trade(side="buy", symbol="AAA", qty=10, price=10, amount=100, currency="HKD", date="2024-01-01", source="1.pdf"),
        Trade(side="sell", symbol="AAA", qty=10, price=15, amount=150, currency="HKD", date="2024-06-01", source="2.pdf"),
        Trade(side="sell", symbol="BBB", qty=8, price=20, amount=160, currency="HKD", date="2024-07-01", source="3.pdf"),
    ]
    income = [IncomeItem(kind="dividend", amount=50, year=2024)]
    report = run_pipeline(trades, income)
    assert report.unmatched[0].sale.symbol == "BBB"
    assert report.tax_due_inputs.transfer_net == 50
    assert report.tax_due_inputs.dividend_net == 50
