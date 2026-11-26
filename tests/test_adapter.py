import json
from decimal import Decimal

import pytest

from scripts.adapter import from_json_data, from_parsed_statement, load_inputs
from scripts.pipeline import run_pipeline


PARSED = {
    "broker_id": "htsc",
    "client_name": "测试",
    "account_number": "0000000001",
    "transactions": [
        {"ref_no": "1000000001", "settlement_date": "2024-01-04", "trade_date": "2024-01-02", "direction": "买入",
         "open_close": "开仓", "product": "BAC:US", "price": 10.0, "quantity": 100, "amount": 1000.0},
        {"ref_no": "1000000001", "trade_date": "2024-01-02", "direction": "买入", "product": "BAC",
         "currency": "USD", "price": 10.0, "quantity": 100, "net_amount": 1005.0},
        {"ref_no": "1000000002", "trade_date": "2024-03-02", "direction": "卖出", "product": "BAC",
         "currency": "USD", "price": 12.0, "quantity": 100, "net_amount": 1195.0},
        {"ref_no": "1000000003", "trade_date": "2024-03-03", "direction": "卖出", "product": "00700",
         "quantity": 10, "amount": None},
    ],
    "dividends": [{"ref_no": "1000000010", "date": "2024-06-28", "product": "BAC", "currency": "USD", "amount": 48.0}],
    "withholding_taxes": [{"ref_no": "1000000011", "date": "2024-06-28", "product": "BAC", "currency": "USD", "amount": 14.4}],
}


def test_parsed_statement_to_trades_and_income():
    adapted = from_parsed_statement(PARSED, "htsc.pdf")
    assert len(adapted.trades) == 2  # 同一单据号只留一条，缺金额的那笔跳过并提示
    buy = adapted.trades[0]
    assert (buy.side, buy.symbol, buy.currency, buy.amount) == ("buy", "BAC", "USD", Decimal("1005.0"))
    assert any("00700" in w for w in adapted.warnings)
    kinds = [(i.kind, i.amount, i.foreign_tax_paid) for i in adapted.income_items]
    assert kinds == [("dividend", Decimal("48.0"), 0), ("dividend", 0, Decimal("14.4"))]


def test_parsed_statement_without_dividends_creates_no_income():
    data = dict(PARSED, dividends=[], withholding_taxes=[])
    assert from_parsed_statement(data, "x.pdf").income_items == []


def test_parse_error_becomes_warning():
    adapted = from_json_data({"error": "Unsupported broker"}, "odd.pdf")
    assert adapted.trades == [] and adapted.warnings


def test_duplicate_statements_are_counted_once(tmp_path):
    a = tmp_path / "daily.json"
    b = tmp_path / "monthly.json"
    a.write_text(json.dumps(PARSED), encoding="utf-8")
    b.write_text(json.dumps(PARSED), encoding="utf-8")
    adapted = load_inputs([str(a), str(b)])
    assert len(adapted.trades) == 2
    assert len(adapted.income_items) == 2


def test_end_to_end_from_parsed_statement():
    adapted = from_parsed_statement(PARSED, "htsc.pdf")
    report = run_pipeline(adapted.trades, adapted.income_items, year=2024, fx_rates={"USD": 7})
    taxed = report.tax_due_inputs
    assert taxed.transfer_net == Decimal("1330.0")  # (1195 - 1005) * 7
    assert taxed.dividend_gross_tax == Decimal("67.20")  # 48 * 7 * 20%
    assert taxed.dividend_credit == Decimal("67.20")  # 14.4 * 7 = 100.8，超限额只抵 67.2
    assert report.tax_due == Decimal("266.00")


def test_structured_input_validation():
    with pytest.raises(ValueError):
        from_json_data({"trades": [{"side": "hold", "symbol": "A", "qty": 1, "amount": 1, "date": "2024-01-01"}]}, "x")
    with pytest.raises(ValueError):
        from_json_data({"income": [{"kind": "rent", "amount": 1, "date": "2024-01-01"}]}, "x")
