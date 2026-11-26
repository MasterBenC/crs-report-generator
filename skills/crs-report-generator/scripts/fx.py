"""汇率表：1 单位外币 = 多少人民币。只有 CNY 自己按 1，其他币种缺了就标出来，绝不默认 1。"""
import json
from decimal import Decimal
from pathlib import Path

from scripts.models import to_decimal

BASE_CURRENCY = "CNY"


def normalize_rates(rates: dict | None) -> dict[str, Decimal] | None:
    if rates is None:
        return None
    normalized: dict[str, Decimal] = {}
    for currency, value in rates.items():
        code = str(currency).strip().upper()
        if not code:
            raise ValueError("汇率表里有空的币种代码")
        rate = to_decimal(value, default=Decimal("-1"))
        if rate <= 0:
            raise ValueError(f"{code} 的汇率必须是正数，收到 {value!r}")
        normalized[code] = rate
    return normalized


def rate_for(currency: str | None, rates: dict[str, Decimal]) -> Decimal | None:
    """返回折算到 CNY 的汇率；查不到返回 None（调用方必须单独列出该币种）。"""
    if currency is None:
        return None
    code = currency.strip().upper()
    if code == BASE_CURRENCY:
        return rates.get(code, Decimal("1"))
    return rates.get(code)


def parse_fx_rates(value: str | None) -> dict[str, Decimal] | None:
    """解析 --fx-rates：JSON 文件路径，或 HKD=0.92,USD=7.20 这样的映射。"""
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise ValueError("--fx-rates 不能为空")
    path = Path(text)
    if path.suffix.lower() == ".json" or path.is_file():
        if not path.is_file():
            raise ValueError(f"找不到汇率文件: {text}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("汇率 JSON 必须是 {\"HKD\": 0.92} 这样的对象")
        return normalize_rates(data)
    pairs: dict[str, str] = {}
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError(f"汇率格式应为 币种=汇率，收到 {chunk!r}")
        code, rate = chunk.split("=", 1)
        pairs[code] = rate
    if not pairs:
        raise ValueError("--fx-rates 里没有读到任何汇率")
    return normalize_rates(pairs)
