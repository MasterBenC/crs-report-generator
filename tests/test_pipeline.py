from scripts.pipeline import run_pipeline
from scripts.models import Trade, IncomeItem


def test_pipeline_excludes_unmatched_sell_from_tax_due():
    trades = [
        Trade(side="buy", symbol="AAA", qty=10, price=10, amount=100, currency="HKD", date="2024-01-01", source="1.pdf"),
        Trade(side="sell", symbol="AAA", qty=10, price=15, amount=150, currency="HKD", date="2024-06-01", source="2.pdf"),
        Trade(side="sell", symbol="BBB", qty=8, price=20, amount=160, currency="HKD", date="2024-07-01", source="3.pdf"),
    ]
    # v3.1.0：收入必须带币种，否则会被单列为“未标币种”，不能和 HKD 互相加总。
    income = [IncomeItem(kind="dividend", amount=50, year=2024, currency="HKD")]
    report = run_pipeline(trades, income)
    assert report.unmatched[0].sale.symbol == "BBB"
    assert report.tax_due_inputs.transfer_net == 50
    assert report.tax_due_inputs.dividend_net == 50


def test_pipeline_with_year_only_counts_target_year_and_its_gaps():
    trades = [
        Trade(side="buy", symbol="AAA", qty=10, amount=100, currency="HKD", date="2023-01-01", source="1.pdf"),
        Trade(side="sell", symbol="AAA", qty=5, amount=80, currency="HKD", date="2023-12-31", source="1.pdf"),
        Trade(side="sell", symbol="AAA", qty=5, amount=90, currency="HKD", date="2024-01-02", source="2.pdf"),
        Trade(side="sell", symbol="OLD", qty=1, amount=10, currency="HKD", date="2023-06-01", source="1.pdf"),
    ]
    income = [
        IncomeItem(kind="dividend", amount=30, year=2023, currency="HKD"),
        IncomeItem(kind="dividend", amount=20, year=2024, currency="HKD"),
    ]
    report = run_pipeline(trades, income, year=2024)
    assert report.tax_due_inputs.transfer_net == 40  # 90 - 50，2023 年的卖出不算
    assert report.tax_due_inputs.dividend_net == 20
    assert report.unmatched == []  # 2023 年的缺口与 2024 年无关
    assert report.tax_due == 12
