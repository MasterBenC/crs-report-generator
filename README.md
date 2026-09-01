# CRS Report Generator

从券商/银行 PDF 结单自动提取账户信息，生成**美化版 CRS 金融账户信息申报表**（Excel 标准格式）。专为移民/离岸/多币种账户的年度 CRS 申报整理而生，比手动誊抄快得多。

> ⚠️ **免责声明**：本工具仅用于整理与核对，输出的表格**不构成法律或税务意见**。正式申报前请由专业税务顾问审核。

## 功能特性

- 📄 **多券商自动识别** — 华泰(HTSC)、富途(Futu)、盈透(IBKR)、辉立(Phillip) 自动判断
- 🎨 **CRS 标准 Excel** — 账户持有人 / 金融机构 / 余额 / 收入 四大板块，专业配色
- 👤 **客户信息提取** — 姓名、账号、地址、账户类型
- 💰 **多币种汇总** — HKD、USD、CNH、JPY 等，自动换算港币等值
- 🏷️ **持仓明细** — 股票、基金、债券分类列出
- 🔍 **原始数据留存** — 第三页保留完整 JSON，供人工核查

## 快速开始

```bash
# 1. 安装依赖
pip install pdfplumber openpyxl

# 2. 一键生成（自动识别券商）
python3 crs_generator.py 券商结单.pdf -o CRS_申报表.xlsx

# 3. 只预览提取结果（不生成 Excel）
python3 crs_generator.py 券商结单.pdf --json
```

补充客户信息（TIN / 出生日期 / 英文名从 PDF 里通常提不出来，需手动补）：

```bash
python3 crs_generator.py 券商结单.pdf \
    --client-name-en "Zhang San" \
    --tin "440xxxxxxxxxxxxxxxx" \
    --dob "1990-01-01"
```

## 支持的券商

| 券商 | 识别关键词 | 状态 |
|------|-----------|------|
| 华泰 (HTSC) | 华泰金融控股、HTSC、B01829 | ✅ 完成 |
| 富途 (Futu) | 富途证券、Futu Securities、futunn | 🔜 待适配 |
| 盈透 (IBKR) | Interactive Brokers、IBKR | 🔜 待适配 |
| 辉立 (Phillip) | 辉立证券、Phillip Securities | 🔜 待适配 |

> 富途 / 盈透 / 辉立的**券商识别**已就位（`BrokerDetector`），但它们的**具体结单版式解析器**尚未实现。欢迎 PR 补充。

## 安装为 Hermes / Claude / OpenClaw Skill

本仓库就是一个标准 Skill 目录结构，一键安装：

```bash
# Ubuntu/macOS
bash install.sh

# 指定安装到某个 agent 的 skills 目录
bash install.sh ~/.claude/skills
bash install.sh ~/.hermes/skills
```

装完后，直接在对话里说：**"帮我处理这份券商流水，生成 CRS 申报表"**，再上传 PDF 即可。

## 项目结构

```
crs-report-generator/
├── SKILL.md               # Skill 元数据 + 使用说明
├── scripts/
│   └── crs_generator.py   # 核心：解析 + 生成 Excel
├── install.sh             # 一键安装
├── README.md
└── LICENSE
```

## 工作原理

1. `pdfplumber` 提取 PDF 文本层（结单需为**文本型 PDF**，非图片扫描）
2. `BrokerDetector` 按关键词自动识别券商
3. 对应版式解析器（当前 HTSC 已实现）抽取姓名/账号/余额/持仓/交易
4. `openpyxl` 生成带样式的多 Sheet Excel，末页留存完整提取 JSON

## 已知局限

- **持仓明细**：多行名称的基金/股票可能未合并解析（华泰结单中基金名跨两行时，第二行名称会被丢弃）
- **完整净收益**：单份结单只能算资产快照与同日买卖价差；真正的资本利得需串联多份结单匹配买入成本
- **收入信息**：股息/利息/卖出收益需汇总全年结单，单份结单无法覆盖

## 贡献

欢迎 PR：补齐富途 / 盈透 / 辉立解析器、修复持仓跨行合并、支持多结单成本匹配。

## License

MIT License — 详见 [LICENSE](LICENSE)。
