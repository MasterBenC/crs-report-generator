---
name: crs-report-generator
slug: crs-report-generator
version: 3.1.0
displayName: 境外投资补税测算
description: Use when a client needs to estimate China individual income tax on overseas brokerage or bank statements, prepare documents for the tax bureau, or offset annual stock gains and losses from local agent chats such as WorkBuddy or 豆包 Work.
summary: 从境外券商或银行结单测算中国个人所得税补税金额，并列出给税局的材料。不是 CRS 官方申报表。
homepage: https://github.com/MasterBenC/crs-report-generator
license: MIT
---

# 境外投资补税测算

在 WorkBuddy / 豆包 Work / Claude / Codex 这类本地 Agent 里使用。客户把全年境外券商或银行结单发过来后，用很短的白话问询，从单子里匹配买入成本，做年内盈亏互抵，然后只回答两件事：大概要补多少税，给税局准备什么。

这是测算底稿，不是税务意见，也不是 CRS 官方申报表。

客户可能完全不懂税务。默认用短句、白话，一次只问一句。能从文件里读到的，不问客户。结单只在本地处理，不要上传身份证，也不要自动安装软件包。

## 何时使用

- 客户有海外券商或银行账户，被税局要求补所得税
- 客户问“我要交多少税”“税局要什么材料”
- 需要把全年多份结单做成可复核底稿
- 需要把同一年已卖出的盈亏互抵后再测算

不要用来解释 CRS 制度，不要生成可直接提交的官方 CRS XML/申报表，不要采集身份证。

## 问询

按 [references/interview.md](references/interview.md)，默认 5 步：

1. 您想算哪一年的税？
2. 这一年您主要住在哪儿？大部分时间在国内、两边跑、住在国外，或我也不清楚。
   若不清楚、两边跑或住国外，再问：这一年在中国住满半年了吗？家里是不是还在国内？
   不确定时，先按要在中国交税来算，并明白告诉客户这个假设。
3. 钱放在哪几家了？客户可以不说，直接传单子。
4. 把这一年能找到的月结单、年结单都传上来。系统负责按人、账户、年份归堆。这些是敏感财务文件，只在本地处理；能打码账号后半段更好，没有也不强求。
5. 这一年有没有分过红、收过利息，或者外国已经扣过税？

禁止问：税收居民、TIN、身份证号、买入价、金融机构编号。
身份证只提示客户自己带去税局或交给中介，不要让客户上传。

## 计算

1. 识别券商，能用模板就用模板；华泰已有模板，其他券商走通用提取。解析只产出交易和余额，不生成看起来像官方申报表的 Excel。
2. 从结单数据表抽出买入、卖出、分红、利息。买入价只从单子读取，规则见 [references/matching.md](references/matching.md)。
3. 同一证券用更早的买入匹配卖出。配不上的卖出整笔暂不算，标成还缺买入记录。
4. 分红和利息单独算，不能被亏损冲掉。已匹配卖出按年内盈亏互抵；互抵后为负则这一块按 0。口径见 [references/tax-estimate.md](references/tax-estimate.md)。
5. 只算申报年度内的卖出和分红利息；更早年份的买入只用来配成本。
6. 外国已扣的税按类别抵免，每类最多抵到这类所得按 20% 算出的税额。
7. 不同币种不直接相加：有汇率就全部折成人民币再互抵；没汇率就按原币种分列，并写明“未提供汇率，按原币种分列”。汇率由顾问从可靠来源提供，不问客户。

禁止：让客户回忆买入价、用现价或均价估计成本、把配不上的卖出当作收益、把单张结单的当日买卖价差当成全年资本利得、运行时自动 pip 安装依赖。

## 命令行（Agent 用）

在本 skill 目录下运行（不需要联网，不会自动安装任何包）：

```bash
# 客户把全年结单传上来后：PDF（目前华泰模板）和 JSON 可以一起给
python3 -m scripts.cli --year 2024 statements/*.pdf

# 顾问拿到汇率后：统一折成人民币再算
python3 -m scripts.cli --year 2024 --fx-rates HKD=0.92,USD=7.20 statements/*.pdf
python3 -m scripts.cli --year 2024 --fx-rates rates.json --format json --output report.json trades.json

# 不在 skill 目录时，直接用脚本路径
python3 /path/to/crs-report-generator/scripts/cli.py --year 2024 trades.json
```

参数：

- `inputs`：一个或多个 `.pdf` / `.json`。JSON 可以是 `scripts/crs_generator.py` 的解析输出，也可以是结构化输入：
  `{"trades": [{"side": "buy", "symbol": "AAA", "qty": 100, "amount": 1000, "fees": 10, "currency": "HKD", "date": "2024-01-02"}], "income": [{"kind": "dividend", "amount": 100, "foreign_tax_paid": 10, "currency": "USD", "date": "2024-06-01"}]}`。
  `amount` 是不含费用的成交金额；已是扣费后净额时不要再填 `fees`。
- `--year`（必填）：申报年度。
- `--fx-rates`（可选）：JSON 文件或 `HKD=0.92,USD=7.20`，表示 1 单位外币等于多少人民币。缺某个币种时，那部分按原币种单列，不会当成 1。
- `--format`：`markdown`（默认，给客户看的四块）或 `json`（结构化，给顾问或后续处理）。
- `--output`：写到文件；不给就打印出来。

何时用哪条：先不带 `--fx-rates` 跑一遍看缺哪些单子；拿到汇率后带上 `--fx-rates` 出人民币合计；需要交给别的程序时用 `--format json`。只看某份 PDF 读出了什么，用 `python3 scripts/crs_generator.py 文件.pdf`（含姓名地址，只给顾问看，不要转发）。退出码 0 成功，2 参数或输入有误。

## 输出

默认只给客户四块：

1. 大概要补多少钱。只加已经对得上的分红、利息和互抵后净收益。
2. 这钱是怎么来的。互抵说成“亏的减赚的”；每类写清“税前应纳 / 外国已扣税抵免 / 预计需补税”。
3. 还缺哪些单子。缺了哪些卖出会先不算。
4. 给税局准备什么。见 [references/documents.md](references/documents.md)。

顾问需要时再展开匹配过程、互抵过程和原始提取。那些不交给税局。不要输出 CRS 申报表、官方表格或带有固定税务居民身份的合规文件。

所有结果都写明：这是测算底稿，正式申报前需要人工审核。
