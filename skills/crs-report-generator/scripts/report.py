from dataclasses import dataclass, field
from decimal import Decimal

from scripts.estimate import estimate_tax
from scripts.models import CENT, FX_MISSING_NOTE, OffsetResult, UnmatchedSale, to_decimal


SECTIONS = ["大概要补多少钱", "这钱是怎么来的", "还缺哪些单子", "给税局准备什么"]
DISCLAIMER = "这是测算底稿，正式申报前需要人工审核。"
TAX_BUREAU_NOTES = "给税局准备：这一年的境外结单、测算表、缺材料说明。身份证请自己带去税局或交给中介，不要上传到这里。"
CATEGORY_LABELS = {"dividend": "分红", "interest": "利息", "transfer": "卖出股票基金（亏的减赚的）"}


@dataclass
class ClientReport:
    tax_due: Decimal | None
    missing_docs: str
    requested_uploads: list[str] = field(default_factory=list)
    tax_bureau_notes: str = ""
    sections: list[str] = field(default_factory=lambda: list(SECTIONS))
    unmatched: list[UnmatchedSale] = field(default_factory=list)
    tax_due_inputs: OffsetResult | None = None
    tax_due_by_currency: dict[str, Decimal] = field(default_factory=dict)
    currency: str | None = None
    year: int | None = None
    notes: list[str] = field(default_factory=list)
    input_warnings: list[str] = field(default_factory=list)


def _is_estimated(result: OffsetResult) -> bool:
    if result.estimated:
        return True
    return any(to_decimal(value) for value in (result.dividend_tax, result.transfer_tax, result.interest_tax))


def build_client_report(
    result: OffsetResult,
    unmatched: list[UnmatchedSale],
    input_warnings: list[str] | None = None,
) -> ClientReport:
    taxed = result if _is_estimated(result) else estimate_tax(result)
    symbols = ", ".join(
        item.sale.symbol if hasattr(item, "sale") else getattr(item, "symbol", "") for item in unmatched
    )
    missing = f"{symbols} 还缺买入记录，这些笔暂时不算。" if unmatched else "单子齐了，已匹配的买卖都算进去了。"
    if taxed.is_split:
        by_currency = {label: bucket.tax_due for label, bucket in taxed.by_currency.items()}
    else:
        by_currency = {taxed.currency: taxed.tax_due} if taxed.currency else {}
    return ClientReport(
        tax_due=taxed.tax_due,
        missing_docs=missing,
        requested_uploads=[],
        tax_bureau_notes=TAX_BUREAU_NOTES,
        unmatched=unmatched,
        tax_due_inputs=taxed,
        tax_due_by_currency=by_currency,
        currency=None if taxed.is_split else taxed.currency,
        year=taxed.year,
        notes=list(taxed.notes),
        input_warnings=list(input_warnings or []),
    )


def _num(value) -> float | None:
    if value is None:
        return None
    return float(to_decimal(value).quantize(CENT))


def _fmt(value) -> str:
    if value is None:
        return "—"
    return f"{to_decimal(value).quantize(CENT):,}"


def _buckets(result: OffsetResult) -> list[OffsetResult]:
    if result.by_currency:
        return list(result.by_currency.values())
    return [result]


def _categories(bucket: OffsetResult) -> list[dict]:
    return [
        {
            "kind": "dividend",
            "label": CATEGORY_LABELS["dividend"],
            "income": _num(bucket.dividend_net),
            "gross_tax": _num(bucket.dividend_gross_tax),
            "foreign_tax_paid": _num(bucket.dividend_foreign_tax_paid),
            "foreign_tax_credit": _num(bucket.dividend_credit),
            "tax_due": _num(bucket.dividend_tax),
        },
        {
            "kind": "interest",
            "label": CATEGORY_LABELS["interest"],
            "income": _num(bucket.interest_net),
            "gross_tax": _num(bucket.interest_gross_tax),
            "foreign_tax_paid": _num(bucket.interest_foreign_tax_paid),
            "foreign_tax_credit": _num(bucket.interest_credit),
            "tax_due": _num(bucket.interest_tax),
        },
        {
            "kind": "transfer",
            "label": CATEGORY_LABELS["transfer"],
            "income": _num(bucket.transfer_net),
            "gross_tax": _num(bucket.transfer_gross_tax),
            "foreign_tax_paid": 0.0,
            "foreign_tax_credit": 0.0,
            "tax_due": _num(bucket.transfer_tax),
        },
    ]


def report_to_dict(report: ClientReport) -> dict:
    """四板块结构化输出。不含姓名、地址、账号、证件号。"""
    result = report.tax_due_inputs or OffsetResult()
    return {
        "year": report.year,
        "disclaimer": DISCLAIMER,
        "sections": list(report.sections),
        "fx": {
            "converted_to_cny": bool(result.fx_converted),
            "missing_currencies": list(result.missing_fx),
            "notes": list(report.notes),
        },
        "tax_due": {
            "currency": report.currency,
            "total": _num(report.tax_due),
            "by_currency": {label: _num(value) for label, value in report.tax_due_by_currency.items()},
        },
        "breakdown": [
            {"currency": bucket.currency, "categories": _categories(bucket)} for bucket in _buckets(result)
        ],
        "missing": {
            "text": report.missing_docs,
            "unmatched_sales": [
                {
                    "symbol": item.sale.symbol,
                    "date": item.sale.date,
                    "currency": item.sale.currency,
                    "qty": str(item.qty.normalize()) if isinstance(item.qty, Decimal) else item.qty,
                    "proceeds": _num(item.proceeds),
                    "source": item.sale.source,
                }
                for item in report.unmatched
            ],
            "input_warnings": list(report.input_warnings),
        },
        "tax_bureau": report.tax_bureau_notes,
    }


def render_markdown(report: ClientReport) -> str:
    result = report.tax_due_inputs or OffsetResult()
    year = f"{report.year} 年" if report.year else ""
    lines = [f"# 境外投资补税测算 {year}".rstrip(), "", f"> {DISCLAIMER}", ""]

    lines += [f"## 1. {SECTIONS[0]}", ""]
    if report.tax_due is not None:
        unit = report.currency or "原币种"
        lines.append(f"大概要补 **{_fmt(report.tax_due)} {unit}**。只算已经对得上的分红、利息和互抵后的净收益。")
    else:
        lines.append("币种没法统一折算，按币种分别列出，不能直接相加：")
        for label, value in report.tax_due_by_currency.items():
            lines.append(f"- {label}：{_fmt(value)}")
    for note in report.notes:
        lines.append(f"- 注意：{note}")
    lines.append("")

    lines += [f"## 2. {SECTIONS[1]}", ""]
    lines.append("卖出的股票基金先配上买入记录，再把同一年亏的减赚的；减完还是亏就按 0。分红、利息单独算，不能用亏损冲掉。")
    lines.append("")
    lines.append("| 币种 | 类别 | 所得 | 税前应纳 | 外国已扣税抵免 | 预计需补税 |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for bucket in _buckets(result):
        for cat in _categories(bucket):
            lines.append(
                f"| {bucket.currency or '—'} | {cat['label']} | {_fmt(cat['income'])} | {_fmt(cat['gross_tax'])} "
                f"| {_fmt(cat['foreign_tax_credit'])} | {_fmt(cat['tax_due'])} |"
            )
    lines.append("")
    lines.append("外国已扣税抵免：每类所得最多抵到这类所得按 20% 算出的税额，多扣的部分不退也不挪到别的类别。")
    lines.append("")

    lines += [f"## 3. {SECTIONS[2]}", "", report.missing_docs]
    for item in report.unmatched:
        lines.append(f"- {item.sale.date} 卖出 {item.sale.symbol}（{item.sale.currency or '未标币种'}），缺买入记录，整笔暂不算")
    for warning in report.input_warnings:
        lines.append(f"- {warning}")
    lines.append("")

    lines += [f"## 4. {SECTIONS[3]}", "", report.tax_bureau_notes, ""]
    return "\n".join(lines)


__all__ = [
    "ClientReport",
    "FX_MISSING_NOTE",
    "SECTIONS",
    "build_client_report",
    "render_markdown",
    "report_to_dict",
]
