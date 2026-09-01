from dataclasses import dataclass


@dataclass
class Trade:
    side: str
    symbol: str
    qty: float
    amount: float
    currency: str
    date: str
    source: str
    price: float | None = None
    fees: float | None = None
    account: str | None = None


@dataclass
class Gap:
    kind: str
    trade: Trade
    message: str
