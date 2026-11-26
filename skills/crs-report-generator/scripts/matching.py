from collections import defaultdict, deque
from decimal import Decimal

from scripts.models import MatchedSale, Trade, UnmatchedSale, to_decimal, to_qty, year_of

ZERO = Decimal("0")


def _sort_key(indexed: tuple[int, Trade]) -> tuple[str, int, int]:
    index, trade = indexed
    # 同一天先买后卖，再按原始顺序；避免 T+0 因记录顺序颠倒误报缺买入记录。
    return (trade.date, 0 if trade.side == "buy" else 1, index)


def match_trades(trades: list[Trade]) -> tuple[list[MatchedSale], list[UnmatchedSale]]:
    """按 FIFO 用更早的买入匹配卖出。

    - 同一证券、同一账户、同一币种才互相匹配，币种不同绝不混算。
    - 数量、金额、费用全部用 Decimal。
    - 买入费用计入成本，卖出费用从收入里扣。
    - 配不上买入的部分整笔暂不算（UnmatchedSale，不估成本）。
    """
    # 每个队列元素: [买入交易, 剩余数量, 总数量, 含费总成本]
    buys: dict[tuple, deque[list]] = defaultdict(deque)
    matched: list[MatchedSale] = []
    unmatched: list[UnmatchedSale] = []

    for _, trade in sorted(enumerate(trades), key=_sort_key):
        key = (trade.symbol, trade.account, trade.currency)
        qty = to_qty(trade.qty)
        if qty <= 0:
            continue
        if trade.side == "buy":
            total_cost = abs(to_decimal(trade.amount)) + abs(to_decimal(trade.fees))
            buys[key].append([trade, qty, qty, total_cost])
            continue
        if trade.side != "sell":
            continue

        sale_fees = abs(to_decimal(trade.fees))
        net_proceeds = abs(to_decimal(trade.amount)) - sale_fees
        remaining = qty
        while remaining > 0 and buys[key]:
            entry = buys[key][0]
            buy, available, buy_qty, buy_total_cost = entry
            match_qty = min(remaining, available)
            proceeds = net_proceeds * match_qty / qty
            cost = buy_total_cost * match_qty / buy_qty
            fees = sale_fees * match_qty / qty + abs(to_decimal(buy.fees)) * match_qty / buy_qty
            matched.append(
                MatchedSale(
                    sale=trade,
                    buy=buy,
                    qty=match_qty,
                    proceeds=proceeds,
                    cost=cost,
                    gain=proceeds - cost,
                    year=year_of(trade.date),
                    currency=trade.currency,
                    fees=fees,
                )
            )
            remaining -= match_qty
            available -= match_qty
            if available <= 0:
                buys[key].popleft()
            else:
                entry[1] = available

        if remaining > 0:
            unmatched.append(
                UnmatchedSale(
                    sale=trade,
                    qty=remaining,
                    proceeds=net_proceeds * remaining / qty,
                )
            )

    return matched, unmatched
