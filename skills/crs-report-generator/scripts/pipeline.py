from scripts.estimate import estimate_tax
from scripts.matching import match_trades
from scripts.models import IncomeItem, Trade, year_of
from scripts.offset import offset_year
from scripts.report import ClientReport, build_client_report


def run_pipeline(
    trades: list[Trade],
    income_items: list[IncomeItem],
    year: int | None = None,
    fx_rates: dict | None = None,
    input_warnings: list[str] | None = None,
) -> ClientReport:
    """match_trades -> offset_year -> estimate_tax -> build_client_report。"""
    matched, unmatched = match_trades(trades)
    if year is not None:
        # 只报告申报年度内的缺口；更早年份的卖出与当年无关。
        unmatched = [item for item in unmatched if year_of(item.sale.date) == year]
    offset = offset_year(matched, income_items, target_year=year, fx_rates=fx_rates)
    taxed = estimate_tax(offset)
    return build_client_report(taxed, unmatched, input_warnings=input_warnings)
