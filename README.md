# 境外投资补税测算

给 WorkBuddy / 豆包 Work 这类本地 Agent 用的 skill。客户把全年境外券商或银行结单传进来，系统用白话问几句，从单子里匹配买入成本，做年内盈亏互抵，然后告诉客户大概要补多少税、给税局准备什么。

这是测算底稿，不是税务意见。

## 第一版范围

- 本地 Agent 白话问询，不另做网站
- 全年多份结单归堆
- 华泰模板可用，其他券商走通用提取
- 买入价只从数据表读取，不估计
- 已卖出盈亏可以互抵，分红不能被亏损冲掉
- 不采集身份证

## 安装

把 `skills/crs-report-generator` 拷到当前 Agent 的 skills 目录，或运行 `bash install.sh <skills 目录>`。

依赖：`pip install pdfplumber openpyxl pytest`
