import pytest

pytest.importorskip("pdfplumber")

from scripts.crs_generator import HTSCParser, parse_amount, parse_income_line  # noqa: E402


@pytest.mark.parametrize("raw", ["-", "", "  ", None, "—", "--"])
def test_parse_amount_empty_markers_return_none(raw):
    assert parse_amount(raw) is None


@pytest.mark.parametrize(
    "raw, expected",
    [("1,234.50", 1234.5), ("-1,234.50", -1234.5), ("(88.00)", -88.0), ("12.00-", -12.0), ("0", 0.0)],
)
def test_parse_amount_values(raw, expected):
    assert parse_amount(raw) == expected


SUMMARY_WITH_DASH = (
    "HKD 1,000.00 0.00 - 2,000.00 0.00 500.00 0.00 3,500.00 1.0000 3,500.00\n"
    "USD 10.00 0.00 - 20.00 0.00 0.00 0.00 30.00 7.8000 234.00\n"
)


def test_net_balance_dash_does_not_crash():
    data = HTSCParser.parse(SUMMARY_WITH_DASH)
    assert data["currencies"]["HKD"]["net_balance"] is None
    assert data["currencies"]["HKD"]["cash"] == 1000.0
    assert data["currencies"]["USD"]["net_balance"] is None


def test_negative_net_balance_keeps_sign():
    data = HTSCParser.parse("HKD 1,000.00 0.00 -500.00 2,000.00 0.00 500.00 0.00 3,500.00 1.0000 3,500.00\n")
    assert data["currencies"]["HKD"]["net_balance"] == -500.0


MOVEMENTS = """户口变动
0006261313 2024-06-03 2024-05-30 买卖交易 买入开仓 BAC:US @ 28.85 (200) (5,770.00) 10,000.00
0006261400 2024-06-28 2024-06-28 公司行动 现金股息 BAC:US USD 0.24/股 48.00 10,048.00
0006261401 2024-06-28 2024-06-28 公司行动 预扣税 BAC:US USD (14.40) 10,033.60
持货结存
"""


def test_htsc_extracts_dividend_and_withholding():
    data = HTSCParser.parse(MOVEMENTS)
    assert len(data["transactions"]) == 1
    assert data["dividends"] == [
        {
            "ref_no": "0006261400",
            "date": "2024-06-28",
            "product": "BAC",
            "currency": "USD",
            "amount": 48.0,
            "raw": "0006261400 2024-06-28 2024-06-28 公司行动 现金股息 BAC:US USD 0.24/股 48.00 10,048.00",
        }
    ]
    assert data["withholding_taxes"][0]["amount"] == 14.4
    assert data["withholding_taxes"][0]["product"] == "BAC"


def test_htsc_without_dividend_lines_keeps_empty_lists():
    text = "户口变动\n0006261313 2024-06-03 2024-05-30 买卖交易 买入开仓 BAC:US @ 28.85 (200) (5,770.00) 10,000.00\n"
    data = HTSCParser.parse(text)
    assert data["dividends"] == []
    assert data["withholding_taxes"] == []


def test_trade_amount_dash_becomes_none_not_crash():
    text = "户口变动\n0006261313 2024-06-03 2024-05-30 买卖交易 卖出平仓 BAC:US @ 28.85 (200) - 10,000.00\n"
    data = HTSCParser.parse(text)
    assert data["transactions"][0]["amount"] is None


def test_income_line_ignores_unrelated_text():
    assert parse_income_line("重要提示：股息以实际入账为准") is None
