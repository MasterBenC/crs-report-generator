"""把解析结果或结构化 JSON 转成 Trade / IncomeItem 列表。

支持两种输入：
1. crs_generator.py 的解析输出（含 transactions / dividends / withholding_taxes）。
2. 结构化 JSON：{"trades": [...], "income": [...]}，字段见 SKILL.md。

不读取、不输出姓名、地址、账号以外的身份信息；账号只在内部用来区分匹配队列。
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

from scripts.models import IncomeItem, Trade, to_decimal, year_of

SIDE_MAP = {"买入": "buy", "卖出": "sell", "buy": "buy", "sell": "sell"}
INCOME_KINDS = {"dividend", "interest"}
MARKET_CURRENCY = {"US": "USD", "HK": "HKD"}


@dataclass
class AdaptedInput:
    trades: list[Trade] = field(default_factory=list)
    income_items: list[IncomeItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def extend(self, other: "AdaptedInput") -> None:
        self.trades.extend(other.trades)
        self.income_items.extend(other.income_items)
        self.warnings.extend(other.warnings)


def normalize_symbol(product: str | None) -> tuple[str, str | None]:
    """"BAC:US" -> ("BAC", "US")；"00700" -> ("00700", None)。"""
    text = (product or "").strip().rstrip(":").strip()
    if ":" in text:
        symbol, market = text.split(":", 1)
        return symbol.strip(), market.strip().upper() or None
    return text, None


def _currency(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def from_parsed_statement(data: dict, source: str) -> AdaptedInput:
    """crs_generator.parse_statement() 的输出 -> AdaptedInput。

    同一单据号同时出现在“户口变动”和“成交单据”时只保留一条（优先带币种和净金额的那条）。
    """
    result = AdaptedInput()
    if data.get("error"):
        result.warnings.append(f"{source} 读不出来（{data['error']}），这份单子里的交易暂时没算进去")
        return result

    account = data.get("account_number")
    chosen: dict[tuple, dict] = {}
    order: list[tuple] = []
    for index, txn in enumerate(data.get("transactions") or []):
        side = SIDE_MAP.get(str(txn.get("direction", "")).strip())
        if side is None:
            continue
        ref = txn.get("ref_no")
        key = ("ref", ref, side) if ref else ("idx", index)
        score = (txn.get("currency") is not None, txn.get("net_amount") is not None)
        if key not in chosen:
            order.append(key)
            chosen[key] = dict(txn, _side=side, _score=score)
        elif score > chosen[key]["_score"]:
            chosen[key] = dict(txn, _side=side, _score=score)

    for key in order:
        txn = chosen[key]
        symbol, market = normalize_symbol(txn.get("product"))
        amount = txn.get("net_amount")
        if amount is None:
            amount = txn.get("amount")
        date = txn.get("trade_date") or txn.get("settlement_date")
        qty = txn.get("quantity")
        if amount is None or not date or not qty:
            result.warnings.append(f"{source} 里 {symbol or '某笔'} 的交易缺金额、数量或日期，这笔暂时没算")
            continue
        currency = _currency(txn.get("currency")) or MARKET_CURRENCY.get(market or "")
        result.trades.append(
            Trade(
                side=txn["_side"],
                symbol=symbol,
                qty=abs(to_decimal(qty)),
                # 结单上的是扣费后的净额，所以 fees 留空，避免重复扣。
                amount=abs(to_decimal(amount)),
                currency=currency,
                date=str(date),
                source=source,
                price=txn.get("price"),
                fees=None,
                account=account,
                ref_no=txn.get("ref_no"),
            )
        )

    for kind, key in (("dividend", "dividends"), ("withholding", "withholding_taxes")):
        for item in data.get(key) or []:
            year = year_of(item.get("date"))
            if item.get("amount") is None or year is None:
                result.warnings.append(f"{source} 里有一条分红或预扣税缺金额或日期，暂时没算")
                continue
            symbol, market = normalize_symbol(item.get("product"))
            currency = _currency(item.get("currency")) or MARKET_CURRENCY.get(market or "")
            amount = abs(to_decimal(item["amount"]))
            result.income_items.append(
                IncomeItem(
                    kind="dividend",
                    amount=amount if kind == "dividend" else 0,
                    foreign_tax_paid=amount if kind == "withholding" else 0,
                    year=year,
                    currency=currency,
                    symbol=symbol or None,
                    date=item.get("date"),
                    source=source,
                    ref_no=item.get("ref_no"),
                )
            )
    return result


def from_structured(data: dict, source: str) -> AdaptedInput:
    result = AdaptedInput()
    for i, raw in enumerate(data.get("trades") or []):
        side = SIDE_MAP.get(str(raw.get("side", "")).strip().lower()) or SIDE_MAP.get(str(raw.get("side", "")).strip())
        if side is None:
            raise ValueError(f"{source} trades[{i}] 的 side 只能是 buy/sell")
        for name in ("symbol", "qty", "amount", "date"):
            if raw.get(name) in (None, ""):
                raise ValueError(f"{source} trades[{i}] 缺少 {name}")
        result.trades.append(
            Trade(
                side=side,
                symbol=str(raw["symbol"]).strip(),
                qty=to_decimal(raw["qty"]),
                amount=to_decimal(raw["amount"]),
                currency=_currency(raw.get("currency")),
                date=str(raw["date"]),
                source=str(raw.get("source") or source),
                price=raw.get("price"),
                fees=raw.get("fees"),
                account=raw.get("account"),
                ref_no=raw.get("ref_no"),
            )
        )
    for i, raw in enumerate(data.get("income") or []):
        kind = str(raw.get("kind", "")).strip().lower()
        if kind not in INCOME_KINDS:
            raise ValueError(f"{source} income[{i}] 的 kind 只能是 dividend/interest")
        year = raw.get("year") or year_of(raw.get("date"))
        if year is None or raw.get("amount") in (None, ""):
            raise ValueError(f"{source} income[{i}] 缺少 amount 或 date/year")
        result.income_items.append(
            IncomeItem(
                kind=kind,
                amount=to_decimal(raw["amount"]),
                year=int(year),
                foreign_tax_paid=to_decimal(raw.get("foreign_tax_paid")),
                currency=_currency(raw.get("currency")),
                symbol=raw.get("symbol"),
                date=raw.get("date"),
                source=str(raw.get("source") or source),
                ref_no=raw.get("ref_no"),
            )
        )
    return result


def from_json_data(data, source: str) -> AdaptedInput:
    if isinstance(data, list):
        merged = AdaptedInput()
        for i, entry in enumerate(data):
            merged.extend(from_json_data(entry, f"{source}#{i}"))
        return merged
    if not isinstance(data, dict):
        raise ValueError(f"{source} 不是可识别的 JSON 对象")
    if "trades" in data or "income" in data:
        return from_structured(data, source)
    if "transactions" in data or "broker_id" in data or "error" in data:
        return from_parsed_statement(data, source)
    raise ValueError(f"{source} 既不是解析输出，也不是 trades/income 结构化 JSON")


def _dedupe_across_files(adapted: AdaptedInput) -> AdaptedInput:
    """日结单、月结单里重复出现的同一单据号只算一次；没有单据号的记录不去重。"""
    seen: set[tuple] = set()
    trades: list[Trade] = []
    for trade in adapted.trades:
        if trade.ref_no:
            key = (trade.account, trade.ref_no, trade.side)
            if key in seen:
                continue
            seen.add(key)
        trades.append(trade)
    income: list[IncomeItem] = []
    for item in adapted.income_items:
        if item.ref_no:
            key = (item.ref_no, item.kind, item.symbol, str(to_decimal(item.amount)), str(to_decimal(item.foreign_tax_paid)))
            if key in seen:
                continue
            seen.add(key)
        income.append(item)
    return AdaptedInput(trades=trades, income_items=income, warnings=adapted.warnings)


def load_inputs(paths: list[str]) -> AdaptedInput:
    merged = AdaptedInput()
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            raise ValueError(f"找不到输入文件: {raw_path}")
        source = path.name
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            from scripts.crs_generator import parse_statement

            merged.extend(from_parsed_statement(parse_statement(str(path)), source))
        elif suffix == ".json":
            merged.extend(from_json_data(json.loads(path.read_text(encoding="utf-8")), source))
        else:
            raise ValueError(f"只支持 .pdf 或 .json 输入: {raw_path}")
    return _dedupe_across_files(merged)
