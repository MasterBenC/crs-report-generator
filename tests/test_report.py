from scripts.report import build_client_report
from scripts.models import UnmatchedSale, OffsetResult, Trade


def test_client_report_has_four_sections_and_no_id_collection():
    result = OffsetResult(dividend_net=200, transfer_net=500, dividend_tax=40, transfer_tax=100)
    unmatched = [UnmatchedSale(sale=Trade(side="sell", symbol="TSLA", qty=5, amount=1000, currency="USD", date="2024-06-01", source="t.pdf"), qty=5, proceeds=1000)]
    report = build_client_report(result, unmatched)
    assert report.tax_due == 140
    assert "TSLA" in report.missing_docs
    assert "身份证" not in report.requested_uploads
    assert "自己带" in report.tax_bureau_notes
    assert report.sections == ["大概要补多少钱", "这钱是怎么来的", "还缺哪些单子", "给税局准备什么"]
