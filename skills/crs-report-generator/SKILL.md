---
name: crs-report-generator
description: Use when a client needs to estimate China individual income tax on overseas brokerage or bank statements, prepare documents for the tax bureau, or offset annual stock gains and losses from local agent chats such as WorkBuddy or 豆包 Work.
---

# 境外投资补税测算

在 WorkBuddy / 豆包 Work 这类本地 Agent 里，用白话问询收集必要信息，读取全年券商结单，从数据表匹配买入成本，做年内盈亏互抵，然后告诉客户大概要补多少税、给税局准备什么。

这是测算底稿，不是税务意见。

## 问询

一次只问一句，按 [references/interview.md](references/interview.md)：

1. 算哪一年
2. 这一年主要住哪儿；不清楚再问住满半年没有、家里是否还在国内
3. 钱放在哪几家
4. 把能找到的结单都传上来
5. 有没有分红、利息或外国扣过税

禁止问税收居民、TIN、身份证号、买入价、金融机构编号。身份证只提示客户自己带去税局或交给中介。

## 计算

买入价只从结单数据表读取，规则见 [references/matching.md](references/matching.md)。配不上的卖出整笔暂不算。分红和利息不能被亏损冲掉。

## 输出

默认只给客户四块：大概要补多少钱、这钱是怎么来的、还缺哪些单子、给税局准备什么。材料建议见 [references/documents.md](references/documents.md)。测算口径见 [references/tax-estimate.md](references/tax-estimate.md)。
