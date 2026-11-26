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


from scripts.estimate import estimate_tax
from scripts.models import FX_MISSING_NOTE, IncomeItem
from scripts.offset import offset_year
from scripts.report import render_markdown, report_to_dict


def test_section_two_shows_gross_credit_and_due():
    taxed = estimate_tax(OffsetResult(transfer_net=0, dividend_net=1000, dividend_foreign_tax_paid=300, currency="CNY"))
    report = build_client_report(taxed, [])
    text = render_markdown(report)
    assert "税前应纳" in text and "外国已扣税抵免" in text and "预计需补税" in text
    for title in ["大概要补多少钱", "这钱是怎么来的", "还缺哪些单子", "给税局准备什么"]:
        assert title in text
    data = report_to_dict(report)
    dividend = data["breakdown"][0]["categories"][0]
    assert dividend == {
        "kind": "dividend",
        "label": "分红",
        "income": 1000.0,
        "gross_tax": 200.0,
        "foreign_tax_paid": 300.0,
        "foreign_tax_credit": 200.0,
        "tax_due": 0.0,
    }


def test_split_currency_report_has_no_total():
    income = [
        IncomeItem(kind="dividend", amount=100, year=2024, currency="USD"),
        IncomeItem(kind="dividend", amount=100, year=2024, currency="HKD"),
    ]
    report = build_client_report(offset_year([], income, target_year=2024), [])
    assert report.tax_due is None
    assert set(report.tax_due_by_currency) == {"USD", "HKD"}
    data = report_to_dict(report)
    assert data["tax_due"]["total"] is None
    assert FX_MISSING_NOTE in data["fx"]["notes"]
    assert FX_MISSING_NOTE in render_markdown(report)


def test_report_output_contains_no_identity_fields():
    report = build_client_report(OffsetResult(transfer_net=0, dividend_net=0), [])
    blob = str(report_to_dict(report)) + render_markdown(report)
    for word in ["TIN", "身份证号", "金融机构编号", "account"]:
        assert word not in blob
