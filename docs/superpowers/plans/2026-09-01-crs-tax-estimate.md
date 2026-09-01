# 境外投资补税测算 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有 crs-report-generator 升级为本地 Agent 上的境外投资补税测算助手：白话问询、全年结单归堆、从数据表匹配买入成本、年内盈亏互抵，并输出客户能看懂的税额和税局材料建议。

**Architecture:** Skill 入口只负责触发、问询路由、禁止事项和输出契约。确定性计算全部放进 scripts：结单解析、交易标准化、成本匹配、年内互抵、测算表生成。references 按需加载问询话术、券商解析、互抵规则、个税口径和材料清单。现有华泰解析器保留为第一版模板，但不再直接生成 CRS 申报表。

**Tech Stack:** Python 3.10+，pytest，pdfplumber，openpyxl，本地 Markdown skill 文件。

**Spec:** [docs/superpowers/specs/2026-09-01-crs-tax-estimate-design.md](../specs/2026-09-01-crs-tax-estimate-design.md)

## Global Constraints

- 对外名称是「境外投资补税测算」；客户对话不出现 CRS、TIN、金融机构编号、税收居民。
- 前端就是 WorkBuddy / 豆包 Work 这类本地 Agent，不另做网站，不上传云端。
- 不采集身份证、户口本、银行密码、验证码。
- 买入价只能从结单数据表读取；禁止询问、估计、用现价或均价代替。
- 配不上买入记录的卖出整笔暂不算入确定税额。
- 分红和利息不能被亏损冲掉；只有同一年已匹配卖出盈亏可以互抵；亏损不结转下一年。
- 输出必须标明：这是测算底稿，不是税务意见。
- 测试只用合成或脱敏数据，不把真实客户 PDF 放进仓库。
- 内部目录名可继续使用 crs-report-generator。

## File Structure

- `skills/crs-report-generator/SKILL.md`：触发、问询路由、禁止事项、输出契约
- `skills/crs-report-generator/references/interview.md`：5 步白话问询
- `skills/crs-report-generator/references/matching.md`：成本匹配与年内互抵
- `skills/crs-report-generator/references/tax-estimate.md`：个税测算口径和客户四块结果
- `skills/crs-report-generator/references/documents.md`：税局材料建议，不含身份证采集
- `skills/crs-report-generator/scripts/models.py`：交易、缺口、测算结果的数据结构
- `skills/crs-report-generator/scripts/interview.py`：问询状态机
- `skills/crs-report-generator/scripts/matching.py`：成本匹配
- `skills/crs-report-generator/scripts/offset.py`：年内盈亏互抵
- `skills/crs-report-generator/scripts/estimate.py`：税额测算
- `skills/crs-report-generator/scripts/report.py`：客户结果和测算表
- `skills/crs-report-generator/scripts/crs_generator.py`：保留华泰解析，改为给匹配层提供标准化交易
- `tests/`：合成案例测试

---

### Task 1: 数据模型和缺口记录

**Files:**
- Create: `skills/crs-report-generator/scripts/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: 无
- Produces: `Trade`, `MatchedSale`, `UnmatchedSale`, `IncomeItem`, `Gap`

- [ ] **Step 1: Write the failing test**

```python
from scripts.models import Trade, Gap

def test_unmatched_sale_is_a_gap_not_an_estimate():
    sale = Trade(side="sell", symbol="AAPL", qty=10, amount=1000, currency="USD", date="2024-06-01", source="htsc.pdf")
    gap = Gap(kind="missing_buy", trade=sale, message="还缺买入记录")
    assert gap.kind == "missing_buy"
    assert gap.trade.symbol == "AAPL"
    assert "估" not in gap.message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py::test_unmatched_sale_is_a_gap_not_an_estimate -v`
Expected: FAIL because `scripts.models` does not exist

- [ ] **Step 3: Write minimal implementation**

Create `Trade` with `side, symbol, qty, price, amount, fees, currency, date, account, source`.
Create `Gap` with `kind, trade, message`.
Do not add estimated cost fields.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/crs-report-generator/scripts/models.py tests/test_models.py
git commit -m "feat: add trade and gap models without estimated cost"
```

---

### Task 2: 成本匹配，禁止估计买入价

**Files:**
- Create: `skills/crs-report-generator/scripts/matching.py`
- Test: `tests/test_matching.py`

**Interfaces:**
- Consumes: `list[Trade]`
- Produces: `match_trades(trades) -> tuple[list[MatchedSale], list[UnmatchedSale]]`

- [ ] **Step 1: Write the failing tests**

```python
from scripts.matching import match_trades
from scripts.models import Trade

def test_matches_same_symbol_buy_before_sell():
    trades = [
        Trade(side="buy", symbol="AAPL", qty=10, price=100, amount=1000, currency="USD", date="2024-01-10", source="a.pdf"),
        Trade(side="sell", symbol="AAPL", qty=10, price=120, amount=1200, currency="USD", date="2024-06-01", source="b.pdf"),
    ]
    matched, unmatched = match_trades(trades)
    assert len(matched) == 1
    assert matched[0].gain == 200
    assert unmatched == []

def test_unmatched_sell_is_not_priced():
    trades = [
        Trade(side="sell", symbol="TSLA", qty=5, price=200, amount=1000, currency="USD", date="2024-06-01", source="b.pdf"),
    ]
    matched, unmatched = match_trades(trades)
    assert matched == []
    assert len(unmatched) == 1
    assert unmatched[0].estimated_cost is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_matching.py -v`
Expected: FAIL because `match_trades` does not exist

- [ ] **Step 3: Write minimal implementation**

FIFO match by symbol and account. Consume earlier buys first. If remaining sell qty > 0, emit `UnmatchedSale` with `estimated_cost=None`. Never fill cost from last price or average price.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_matching.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/crs-report-generator/scripts/matching.py tests/test_matching.py
git commit -m "feat: match sells to statement buys without estimating cost"
```

---

### Task 3: 年内盈亏互抵，分红不被冲掉

**Files:**
- Create: `skills/crs-report-generator/scripts/offset.py`
- Test: `tests/test_offset.py`

**Interfaces:**
- Consumes: `list[MatchedSale]`, `list[IncomeItem]`
- Produces: `offset_year(matched_sales, income_items) -> OffsetResult`

- [ ] **Step 1: Write the failing tests**

```python
from scripts.offset import offset_year
from scripts.models import MatchedSale, IncomeItem

def test_stock_gain_and_loss_offset_within_year():
    sales = [
        MatchedSale(symbol="AAA", gain=800, year=2024),
        MatchedSale(symbol="BBB", gain=-300, year=2024),
    ]
    result = offset_year(sales, [])
    assert result.transfer_net == 500
    assert result.dividend_net == 0

def test_loss_does_not_reduce_dividends():
    sales = [MatchedSale(symbol="AAA", gain=-300, year=2024)]
    income = [IncomeItem(kind="dividend", amount=200, year=2024)]
    result = offset_year(sales, income)
    assert result.transfer_net == 0
    assert result.dividend_net == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_offset.py -v`
Expected: FAIL because `offset_year` does not exist

- [ ] **Step 3: Write minimal implementation**

`transfer_net = max(sum(gains), 0)`. Dividends and interest stay separate. Do not carry loss to next year.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_offset.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/crs-report-generator/scripts/offset.py tests/test_offset.py
git commit -m "feat: offset matched stock gains and losses within one year"
```

---

### Task 4: 白话问询状态机

**Files:**
- Create: `skills/crs-report-generator/scripts/interview.py`
- Create: `skills/crs-report-generator/references/interview.md`
- Test: `tests/test_interview.py`

**Interfaces:**
- Consumes: 客户上一句回答
- Produces: `next_question(state, answer) -> InterviewState`

- [ ] **Step 1: Write the failing tests**

```python
from scripts.interview import start_interview, next_question

def test_first_question_asks_year_in_plain_language():
    state = start_interview()
    assert "哪一年" in state.question
    assert "税收居民" not in state.question
    assert "买入" not in state.question

def test_unknown_residence_does_not_use_tax_resident_term():
    state = start_interview()
    state = next_question(state, "2024")
    state = next_question(state, "我也不清楚")
    assert "税收居民" not in state.question
    assert "住" in state.question or "半年" in state.question

def test_never_asks_for_buy_price_or_id_card():
    texts = []
    state = start_interview()
    for answer in ["2024", "大部分时间在国内", "华泰", "先这些单子", "不知道"]:
        texts.append(state.question)
        state = next_question(state, answer)
    texts.append(state.question or "")
    blob = "".join(texts)
    assert "买入价" not in blob
    assert "身份证" not in blob
    assert "TIN" not in blob
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_interview.py -v`
Expected: FAIL because interview helpers do not exist

- [ ] **Step 3: Write minimal implementation**

Implement the 5 questions from the spec, one at a time. If residence is unclear, ask about time in China and whether family remains in China. Never ask buy price, TIN, or ID card. Put the exact wording in `references/interview.md` and keep `interview.py` aligned with it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_interview.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/crs-report-generator/scripts/interview.py skills/crs-report-generator/references/interview.md tests/test_interview.py
git commit -m "feat: add plain-language interview without tax jargon"
```

---

### Task 5: 客户结果和税局材料建议

**Files:**
- Create: `skills/crs-report-generator/scripts/estimate.py`
- Create: `skills/crs-report-generator/scripts/report.py`
- Create: `skills/crs-report-generator/references/tax-estimate.md`
- Create: `skills/crs-report-generator/references/documents.md`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `OffsetResult`, `list[UnmatchedSale]`
- Produces: `build_client_report(...) -> ClientReport`

- [ ] **Step 1: Write the failing tests**

```python
from scripts.report import build_client_report
from scripts.models import UnmatchedSale, OffsetResult

def test_client_report_has_four_sections_and_no_id_collection():
    result = OffsetResult(dividend_net=200, transfer_net=500, dividend_tax=40, transfer_tax=100)
    unmatched = [UnmatchedSale(symbol="TSLA", qty=5, amount=1000)]
    report = build_client_report(result, unmatched)
    assert report.tax_due == 140
    assert "TSLA" in report.missing_docs
    assert "身份证" not in report.requested_uploads
    assert "自己带" in report.tax_bureau_notes
    assert report.sections == ["大概要补多少钱", "这钱是怎么来的", "还缺哪些单子", "给税局准备什么"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py -v`
Expected: FAIL because report helpers do not exist

- [ ] **Step 3: Write minimal implementation**

`tax_due` is only dividend tax plus transfer tax from matched and offset amounts. Unmatched sales appear in missing docs, not in tax_due. Tax bureau list includes statements, estimate sheet, and gap note. ID card is mentioned only as something the client brings themselves.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/crs-report-generator/scripts/estimate.py skills/crs-report-generator/scripts/report.py skills/crs-report-generator/references/tax-estimate.md skills/crs-report-generator/references/documents.md tests/test_report.py
git commit -m "feat: build client tax estimate and bureau document list"
```

---

### Task 6: 改写 skill 入口，去掉 CRS 申报表产品定位

**Files:**
- Modify: `skills/crs-report-generator/SKILL.md`
- Modify: `README.md`
- Create: `skills/crs-report-generator/references/matching.md`
- Test: `tests/test_skill_copy.py`

**Interfaces:**
- Consumes: Task 4 and Task 5 wording
- Produces: Agent-facing skill instructions that route to interview, matching, offset, and client report

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

def test_skill_copy_is_tax_estimate_not_crs_form():
    text = Path("skills/crs-report-generator/SKILL.md").read_text(encoding="utf-8")
    assert "境外投资补税测算" in text
    assert "CRS 金融账户信息申报表" not in text
    assert "身份证号" not in text
    assert "买入价" not in text
    assert "WorkBuddy" in text or "豆包" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_skill_copy.py -v`
Expected: FAIL because current SKILL.md still describes CRS Excel generation

- [ ] **Step 3: Rewrite SKILL.md**

Keep the folder name. Change description to triggering conditions only: use when a client needs to estimate China individual income tax on overseas brokerage or bank statements, prepare documents for the tax bureau, or offset annual stock gains and losses. Body must include: 5-step interview routing, no ID collection, no buy-price questions, match-from-statements rule, four-section client output, and links to references. Update README to the same product story.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_skill_copy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/crs-report-generator/SKILL.md skills/crs-report-generator/references/matching.md README.md tests/test_skill_copy.py
git commit -m "docs: reposition skill as overseas tax estimate assistant"
```

---

### Task 7: 把华泰解析接到匹配层，而不是直接出申报表

**Files:**
- Modify: `skills/crs-report-generator/scripts/crs_generator.py`
- Create: `skills/crs-report-generator/scripts/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: parsed HTSC trades as `list[Trade]`
- Produces: `run_pipeline(trades, income_items) -> ClientReport`

- [ ] **Step 1: Write the failing test**

```python
from scripts.pipeline import run_pipeline
from scripts.models import Trade, IncomeItem

def test_pipeline_excludes_unmatched_sell_from_tax_due():
    trades = [
        Trade(side="buy", symbol="AAA", qty=10, price=10, amount=100, currency="HKD", date="2024-01-01", source="1.pdf"),
        Trade(side="sell", symbol="AAA", qty=10, price=15, amount=150, currency="HKD", date="2024-06-01", source="2.pdf"),
        Trade(side="sell", symbol="BBB", qty=8, price=20, amount=160, currency="HKD", date="2024-07-01", source="3.pdf"),
    ]
    income = [IncomeItem(kind="dividend", amount=50, year=2024)]
    report = run_pipeline(trades, income)
    assert report.unmatched[0].symbol == "BBB"
    assert report.tax_due_inputs.transfer_net == 50
    assert report.tax_due_inputs.dividend_net == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL because pipeline does not exist

- [ ] **Step 3: Write minimal implementation**

`run_pipeline` calls `match_trades`, `offset_year`, then `build_client_report`. Keep HTSC parser as a source of trades. Stop treating a single statement as a complete CRS filing.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline.py tests/test_matching.py tests/test_offset.py tests/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/crs-report-generator/scripts/pipeline.py skills/crs-report-generator/scripts/crs_generator.py tests/test_pipeline.py
git commit -m "feat: run statement trades through matching and tax estimate pipeline"
```

---

### Task 8: 回归检查与发布说明

**Files:**
- Modify: `README.md`
- Create: `docs/superpowers/plans/2026-09-01-crs-tax-estimate-handoff.md` only if execution needs a short operator note; otherwise keep README as the user-facing note

**Interfaces:**
- Consumes: all previous tasks
- Produces: a skill that can be installed into a local agent and answers with tax due plus document list

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests -v`
Expected: all tests PASS

- [ ] **Step 2: Manual copy sweep**

Read `SKILL.md`, `README.md`, and client report strings. Confirm none ask for ID upload, buy price, TIN, or CRS filing.

- [ ] **Step 3: Commit release notes in README**

State first-version scope: HTSC template plus generic extraction, annual offset, local agent interview. Later brokers remain follow-up work.

```bash
git add README.md
git commit -m "docs: describe overseas tax estimate first release"
```

## Spec coverage

- 小白问询、不出现税收居民：Task 4, Task 6
- 买入价只从数据表读取：Task 2, Task 7
- 年内盈亏互抵、分红不冲亏损：Task 3
- 客户四块结果、不收身份证：Task 5
- 本地 Agent、不另做网站：Task 6
- 华泰解析保留但不再当最终答案：Task 7
- 合成测试、禁止真实客户 PDF：all test files

