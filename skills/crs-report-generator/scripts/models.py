from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

Number = int | float | str | Decimal

# 未提供汇率时，结果按原币种分桶，并带上这句标记。
FX_MISSING_NOTE = "未提供汇率，按原币种分列"
# 币种为空时用的桶名（只用于展示，不参与任何折算）。
UNKNOWN_CURRENCY_LABEL = "未标币种"
QTY_QUANTUM = Decimal("0.00000001")
CENT = Decimal("0.01")


def to_decimal(value: Number | None, default: Decimal = Decimal("0")) -> Decimal:
    """把 int/float/str/Decimal 安全转成 Decimal。

    float 先转 str 再转 Decimal，避免 0.1 + 0.2 这类二进制残差。
    None、空串、"-" 一律返回 default。
    """
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("金额或数量不能是布尔值")
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, int):
        return Decimal(value)
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "—", "--"}:
        return default
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"无法识别的数值: {value!r}") from exc


def to_qty(value: Number | None) -> Decimal:
    """数量统一到 8 位小数，吸收碎股的浮点残差。"""
    return to_decimal(value).quantize(QTY_QUANTUM)


def money(value: Number | None) -> Decimal:
    return to_decimal(value).quantize(CENT)


def year_of(date: str | None) -> int | None:
    if not date or len(str(date)) < 4 or not str(date)[:4].isdigit():
        return None
    return int(str(date)[:4])


@dataclass
class Trade:
    """一笔买入或卖出。

    amount 是成交金额（不含费用）；如果来源给的已经是扣费后的净额，fees 留空。
    """

    side: str
    symbol: str
    qty: Number
    amount: Number
    currency: str | None
    date: str
    source: str
    price: Number | None = None
    fees: Number | None = None
    account: str | None = None
    # 结单单据号，只用于多份结单之间去重。
    ref_no: str | None = None


@dataclass
class Gap:
    kind: str
    trade: Trade
    message: str


@dataclass
class MatchedSale:
    sale: Trade
    buy: Trade
    qty: Decimal
    proceeds: Decimal
    cost: Decimal
    gain: Decimal
    year: int | None = None
    currency: str | None = None
    fees: Decimal = Decimal("0")


@dataclass
class UnmatchedSale:
    sale: Trade
    qty: Decimal
    proceeds: Decimal
    # 红线：配不上买入记录就整笔暂不算，永远不估成本。
    estimated_cost: None = None


@dataclass
class IncomeItem:
    """分红或利息。foreign_tax_paid 是境外已扣的税（同币种）。"""

    kind: str
    amount: Number
    year: int
    foreign_tax_paid: Number = 0
    currency: str | None = None
    symbol: str | None = None
    date: str | None = None
    source: str | None = None
    ref_no: str | None = None


@dataclass
class OffsetResult:
    """某一币种桶（或已折算的 CNY）的年内互抵与测算结果。

    当未提供汇率且存在多个币种时，顶层金额字段为 None（严禁跨币种相加），
    各币种结果放在 by_currency 里。
    """

    transfer_net: Number | None = 0
    dividend_net: Number | None = 0
    interest_net: Number | None = 0
    # 以下 *_tax 是抵免外国已扣税之后的预计需补税。
    dividend_tax: Number | None = 0
    transfer_tax: Number | None = 0
    interest_tax: Number | None = 0
    dividend_foreign_tax_paid: Number | None = 0
    interest_foreign_tax_paid: Number | None = 0
    dividend_gross_tax: Number | None = 0
    interest_gross_tax: Number | None = 0
    transfer_gross_tax: Number | None = 0
    dividend_credit: Number | None = 0
    interest_credit: Number | None = 0
    currency: str | None = None
    year: int | None = None
    estimated: bool = False
    fx_converted: bool = False
    missing_fx: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    by_currency: dict[str, "OffsetResult"] = field(default_factory=dict)

    @property
    def is_split(self) -> bool:
        """True 表示结果按多个币种分列，顶层没有合计。"""
        return len(self.by_currency) > 1

    @property
    def tax_due(self) -> Decimal | None:
        if self.is_split:
            return None
        return (
            to_decimal(self.dividend_tax)
            + to_decimal(self.interest_tax)
            + to_decimal(self.transfer_tax)
        )
