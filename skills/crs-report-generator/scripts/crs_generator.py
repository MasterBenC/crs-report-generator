"""
CRS Report Generator v3.0
Auto-detect broker, extract key fields, generate CRS Excel form.

Supports: 华泰(HTSC), 富途(Futu), 盈透(IBKR), 辉立(Phillip)
"""
import re
import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from collections import defaultdict

try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "pdfplumber", "-q"])
    import pdfplumber

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, numbers
    from openpyxl.utils import get_column_letter
except ImportError:
    print("Installing openpyxl...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, numbers
    from openpyxl.utils import get_column_letter


class BrokerDetector:
    """Auto-detect broker from PDF content."""

    PATTERNS = {
        "htsc": {
            "name": "华泰金融控股（香港）有限公司",
            "name_en": "Huatai Financial Holdings (Hong Kong) Co., Limited",
            "country": "HK",
            "keywords": ["华泰金融控股", "HTSC", "htsc.com", "B01829"],
        },
        "futu": {
            "name": "富途证券国际（香港）有限公司",
            "name_en": "Futu Securities International (Hong Kong) Limited",
            "country": "HK",
            "keywords": ["富途证券", "Futu Securities", "futuhk", "futunn"],
        },
        "ibkr": {
            "name": "盈透证券",
            "name_en": "Interactive Brokers LLC",
            "country": "US",
            "keywords": ["Interactive Brokers", "IBKR", "盈透"],
        },
        "phillip": {
            "name": "辉立证券（香港）有限公司",
            "name_en": "Phillip Securities (Hong Kong) Limited",
            "country": "HK",
            "keywords": ["辉立证券", "Phillip Securities", "phillip.com"],
        },
    }

    @classmethod
    def detect(cls, text):
        scores = {}
        for broker_id, info in cls.PATTERNS.items():
            score = sum(1 for kw in info["keywords"] if kw.lower() in text.lower())
            if score > 0:
                scores[broker_id] = score
        if scores:
            best = max(scores, key=scores.get)
            return best, cls.PATTERNS[best]
        return None, None


class HTSCParser:
    """Parser for 华泰(HTSC) Hong Kong daily/monthly statements."""

    @staticmethod
    def parse(text):
        data = {
            "client_name": None,
            "account_number": None,
            "account_type": None,
            "address": None,
            "statement_date": None,
            "currencies": {},
            "holdings": [],
            "total_value_hkd": None,
            "transactions": [],
            "fees": {},
        }

        lines = text.split("\n")

        # --- Client name and account ---
        for line in lines:
            # Pattern: "张三 (0123456789) 客户户口 : 0123456789"
            m = re.search(r"(\S+)\s*\((\d+)\).*客户户口\s*:\s*(\d+)", line)
            if m:
                data["client_name"] = m.group(1)
                data["account_number"] = m.group(3)
            # Account type
            if "户口类别" in line:
                m = re.search(r"户口类别\s*:\s*(.+?)\s", line)
                if m:
                    data["account_type"] = m.group(1)
            # Address
            if "區" in line or "市" in line or "省" in line:
                if not data["address"] and "省" not in line:
                    continue
                if re.search(r"[\u4e00-\u9fff]{2,}(?:省|市|區|镇|路|號|号|座)", line):
                    if not re.search(r"(?:皇后|中心|大道|Tel|电话|傳真)", line):
                        data["address"] = line.strip()

        # --- Address: collect multi-line ---
        addr_lines = []
        capture = False
        for line in lines:
            if re.search(r"[\u4e00-\u9fff]{2,}省[\u4e00-\u9fff]{2,}市", line):
                capture = True
            if capture:
                if re.search(r"(?:客户主任|列印|户口类别)", line):
                    break
                clean = line.strip()
                if clean and not re.search(r"(?:皇后|中心|大道|Tel|电话|傳真|^$)", clean):
                    addr_lines.append(clean)
        if addr_lines:
            data["address"] = "".join(addr_lines)

        # --- Statement date ---
        for line in lines:
            m = re.search(r"列印于\s*(\d{4}-\d{2}-\d{2})", line)
            if m:
                data["statement_date"] = m.group(1)
                break
            m = re.search(r"日结单\s*\((\d{4}-\d{2}-\d{2})\)", line)
            if m:
                data["statement_date"] = m.group(1)
                break

        # --- Portfolio total value ---
        for line in lines:
            m = re.search(r"投资组合总值\s*HKD\s*([\d,]+\.?\d*)", line)
            if m:
                data["total_value_hkd"] = float(m.group(1).replace(",", ""))

        # --- Portfolio summary ---
        for line in lines:
            # HKD line
            m = re.search(
                r"HKD\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d\-,]+\.?\d*)\s+"
                r"([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+"
                r"([\d,]+\.?\d*)\s+([\d,.]+)\s+([\d,]+\.?\d*)", line
            )
            if m:
                cash = float(m.group(1).replace(",", ""))
                net = float(m.group(3).replace(",", "").replace("-", ""))
                stocks = float(m.group(4).replace(",", ""))
                fund = float(m.group(6).replace(",", ""))
                total = float(m.group(8).replace(",", ""))
                data["currencies"]["HKD"] = {
                    "cash": cash, "net_balance": net,
                    "stocks_value": stocks, "fund_value": fund,
                    "total": total, "exchange_rate": float(m.group(9).replace(",", "")),
                }
            # USD line
            m = re.search(
                r"USD\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d\-,]+\.?\d*)\s+"
                r"([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+"
                r"([\d,]+\.?\d*)\s+([\d,.]+)\s+([\d,]+\.?\d*)", line
            )
            if m:
                cash = float(m.group(1).replace(",", ""))
                net = float(m.group(3).replace(",", "").replace("-", ""))
                stocks = float(m.group(4).replace(",", ""))
                fund = float(m.group(6).replace(",", ""))
                total = float(m.group(8).replace(",", ""))
                data["currencies"]["USD"] = {
                    "cash": cash, "net_balance": net,
                    "stocks_value": stocks, "fund_value": fund,
                    "total": total, "exchange_rate": float(m.group(9).replace(",", "")),
                }

        # --- Holdings ---
        in_holdings = False
        current_section = None
        for line in lines:
            if "持货结存" in line:
                in_holdings = True
                continue
            if in_holdings:
                # Section header: e.g. "HK - HONG KONG STOCK (HKD)" or "FUND - FUND (USD)"
                m = re.match(r"(FUND|HK|US)\s*-\s*(.+?)\s*\((\w+)\)", line)
                if m:
                    current_section = m.group(3)
                    continue
                # Stop conditions
                if any(kw in line for kw in ["预告", "股票借贷", "利息", "待交收", "成交单据", "融资", "重要提示"]):
                    in_holdings = False
                    continue
                # Holding line: "CODE  NAME  QTY...  PRICE  VALUE..."
                # Look for known stock patterns
                # HK stock: "00401 万嘉集团 200 200 0 200 0.166 33.20 0 0.00 0.00"
                # US stock: "AAPL 苹果 10 10 0 10 180.95 1,809.50 60 1,085.70 0.00"
                # Fund: "HK0000846540 ChinaAMC Select... 1,120.95 1,121.59..."
                parts = line.split()
                if len(parts) >= 6:
                    # Try to detect if this is a holding line
                    code = parts[0]
                    # Fund pattern
                    if re.match(r"[A-Z]{2}\d{8,}", code):
                        try:
                            qty_idx = None
                            price_idx = None
                            val_idx = None
                            for i, p in enumerate(parts):
                                if re.match(r"^[\d,]+\.?\d*$", p) and qty_idx is None:
                                    qty_idx = i
                                elif re.match(r"^[\d,]+\.?\d*$", p) and price_idx is None and i > qty_idx:
                                    # Check if likely a price (less digits after decimal or looks like a price)
                                    if "." in p and len(p.split(".")[1]) <= 4:
                                        price_idx = i
                                        break
                            if qty_idx and price_idx:
                                name = " ".join(parts[1:qty_idx])
                                market_value = float(parts[price_idx + 1].replace(",", ""))
                                data["holdings"].append({
                                    "code": code,
                                    "name": name,
                                    "currency": current_section or "HKD",
                                    "type": "fund",
                                    "market_value": market_value,
                                })
                        except (ValueError, IndexError):
                            pass
                    # US stock: "AAPL 苹果 10 10 0 10 180.95 1,809.50 60 1,085.70 0.00"
                    elif re.match(r"^[A-Z]{1,5}$", code):
                        try:
                            # Find numeric value that looks like market value
                            numbers_in_line = []
                            for p in parts:
                                try:
                                    v = float(p.replace(",", ""))
                                    numbers_in_line.append(v)
                                except ValueError:
                                    pass
                            if len(numbers_in_line) >= 2:
                                market_value = numbers_in_line[-3]  # Usually the market value
                                data["holdings"].append({
                                    "code": code,
                                    "name": parts[1] if len(parts) > 1 else "",
                                    "currency": current_section or "USD",
                                    "type": "stock",
                                    "market_value": market_value,
                                })
                        except (ValueError, IndexError):
                            pass
                    # HK stock: "00401 万嘉集团 200 200 0 200 0.166 33.20 0 0.00 0.00"
                    elif re.match(r"^\d{5}$", code):
                        try:
                            numbers_in_line = []
                            for p in parts:
                                try:
                                    v = float(p.replace(",", ""))
                                    numbers_in_line.append(v)
                                except ValueError:
                                    pass
                            if len(numbers_in_line) >= 2:
                                market_value = numbers_in_line[-3]
                                data["holdings"].append({
                                    "code": code,
                                    "name": parts[1] if len(parts) > 1 else "",
                                    "currency": current_section or "HKD",
                                    "type": "stock",
                                    "market_value": market_value,
                                })
                        except (ValueError, IndexError):
                            pass

        # --- Transactions from 户口变动 ---
        in_movements = False
        in_trade_confirm = False
        for i, line in enumerate(lines):
            # Track which section we're in
            if "户口变动" in line:
                in_movements = True
                in_trade_confirm = False
                continue
            if "成交单据" in line:
                in_trade_confirm = True
                in_movements = False
                continue
            if in_movements and any(kw in line for kw in ["持货结存", "待交收", "利息", "预告", "股票借贷", "重要提示", "融资"]):
                in_movements = False
                continue
            if in_trade_confirm and any(kw in line for kw in ["户口变动", "持货结存", "利息", "预告"]):
                in_trade_confirm = False
                continue

            # ---- Parse 户口变动 format ----
            if in_movements:
                m = re.search(
                    r"(\d{10})\s+(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})\s+买卖交易\s+"
                    r"(买入|卖出)(开仓|平仓)\s+(.+?)\s+@?\s*([\d,.]+)\s*"
                    r"\(?(\d[\d,]*)\)?\s+\(?([\d,\-]+\.?\d*)\)?\s+\(?([\d,\-]+\.?\d*)\)?",
                    line
                )
                if m:
                    ref_no = m.group(1)
                    settlement_date = m.group(2)
                    trade_date = m.group(3)
                    direction = m.group(4)
                    open_close = m.group(5)
                    product = m.group(6).strip().rstrip(":")
                    price = float(m.group(7).replace(",", ""))
                    qty = int(m.group(8).replace(",", ""))
                    amount = float(m.group(9).replace(",", ""))
                    data["transactions"].append({
                        "ref_no": ref_no,
                        "settlement_date": settlement_date,
                        "trade_date": trade_date,
                        "direction": direction,
                        "open_close": open_close,
                        "product": product,
                        "price": price,
                        "quantity": qty,
                        "amount": amount,
                    })
                continue

            # ---- Parse 成交单据 format ----
            if in_trade_confirm:
                # Match header line: "0006261313 2023-06-02 卖出 BAC:US USD 28.855 (200)CLEARING..."
                m = re.search(
                    r"(\d{10})\s+(\d{4}-\d{2}-\d{2})\s+(买入|卖出)\s+"
                    r"([A-Z]+):?(?:US|HK)?\s+(HKD|USD|CNH|JPY)\s+"
                    r"([\d,.]+)\s+\(?(\d[\d,]*)\)?",
                    line
                )
                if m:
                    ref_no = m.group(1)
                    trade_date = m.group(2)
                    direction = m.group(3)
                    product = m.group(4)
                    ccy = m.group(5)
                    price = float(m.group(6).replace(",", ""))
                    qty = int(m.group(7).replace(",", ""))
                    # Look for net amount in following lines
                    net_amount = None
                    for j in range(i+1, min(i+8, len(lines))):
                        nm = re.search(r"净金额\s+\(?([\d,\-]+\.?\d*)\)?", lines[j])
                        if nm:
                            net_amount = float(nm.group(1).replace(",", ""))
                            break
                    data["transactions"].append({
                        "ref_no": ref_no,
                        "trade_date": trade_date,
                        "direction": direction,
                        "product": product,
                        "currency": ccy,
                        "price": price,
                        "quantity": qty,
                        "net_amount": net_amount,
                    })
                continue
        for line in lines:
            m = re.search(r"(?:融资计息|利息).*?([\d,]+\.?\d*)\s*<(\d+)%>", line)
            if m:
                data["fees"]["margin_interest"] = float(m.group(1).replace(",", ""))

        return data


def parse_statement(pdf_path):
    """Main entry: parse any supported broker PDF."""
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"

    broker_id, broker_info = BrokerDetector.detect(full_text)
    if not broker_id:
        return {"error": "Unsupported broker", "text_preview": full_text[:500]}

    if broker_id == "htsc":
        data = HTSCParser.parse(full_text)
    else:
        return {"error": f"Parser for {broker_info['name']} not yet implemented"}

    data["broker_id"] = broker_id
    data["broker"] = broker_info
    return data


def generate_crs_excel(data, output_path, client_info=None):
    """Generate a professional CRS Excel report."""
    wb = Workbook()

    # --- Style definitions ---
    title_font = Font(name="Microsoft YaHei", size=14, bold=True, color="1A4334")
    header_font = Font(name="Microsoft YaHei", size=11, bold=True, color="FFFFFF")
    body_font = Font(name="Microsoft YaHei", size=10)
    body_font_en = Font(name="Calibri", size=10)
    note_font = Font(name="Microsoft YaHei", size=9, italic=True, color="64748B")

    header_fill = PatternFill(start_color="1A4334", end_color="1A4334", fill_type="solid")
    alt_fill = PatternFill(start_color="F5F7F8", end_color="F5F7F8", fill_type="solid")
    light_fill = PatternFill(start_color="F2F8F5", end_color="F2F8F5", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="DDE1E4"),
        right=Side(style="thin", color="DDE1E4"),
        top=Side(style="thin", color="DDE1E4"),
        bottom=Side(style="thin", color="DDE1E4"),
    )
    header_border = Border(
        left=Side(style="thin", color="1A4334"),
        right=Side(style="thin", color="1A4334"),
        top=Side(style="thin", color="1A4334"),
        bottom=Side(style="medium", color="1A4334"),
    )

    def style_header(ws, row, cols, values):
        for i, v in enumerate(values, 1):
            cell = ws.cell(row=row, column=i, value=v)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = header_border

    def style_row(ws, row, cols, values, font=None, fill=None):
        for i, v in enumerate(values, 1):
            cell = ws.cell(row=row, column=i, value=v)
            cell.font = font or body_font
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if fill:
                cell.fill = fill

    def auto_width(ws, min_width=10, max_width=40):
        for col in ws.columns:
            max_len = min_width
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value:
                    max_len = max(max_len, min(len(str(cell.value)) * 1.2, max_width))
            ws.column_dimensions[col_letter].width = max_len

    # =====================================================
    # Sheet 1: CRS 申报信息
    # =====================================================
    ws1 = wb.active
    ws1.title = "CRS申报信息"

    # Title
    ws1.merge_cells("A1:D1")
    ws1.cell(row=1, column=1, value="CRS 金融账户信息申报表").font = title_font
    ws1.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 36

    # Subtitle
    ws1.merge_cells("A2:D2")
    broker_name = data.get("broker", {}).get("name", "")
    ws1.cell(row=2, column=1, value=f"数据来源：{broker_name} | "
             f"结单日期：{data.get('statement_date', 'N/A')}").font = note_font
    ws1.cell(row=2, column=1).alignment = Alignment(horizontal="center")

    # --- Section A: Account Holder ---
    r = 4
    ws1.merge_cells(f"A{r}:D{r}")
    ws1.cell(row=r, column=1, value="A. 账户持有人信息").font = Font(name="Microsoft YaHei", size=12, bold=True, color="1A4334")

    r = 5
    style_header(ws1, r, 4, ["字段", "内容（中文）", "内容（英文）", "备注"])
    rows_a = [
        ("姓名", data.get("client_name", ""), client_info.get("name_en", "") if client_info else "", ""),
        ("身份证号 / TIN", "", client_info.get("tin", "") if client_info else "", "需手动填写"),
        ("出生日期", "", client_info.get("dob", "") if client_info else "", "需手动填写"),
        ("地址", data.get("address", ""), client_info.get("address_en", "") if client_info else "", ""),
        ("税务居民国/地区", "中国", "China", ""),
    ]
    for i, row_data in enumerate(rows_a):
        r = 6 + i
        style_row(ws1, r, 4, row_data, fill=alt_fill if i % 2 == 0 else None)

    # --- Section B: Financial Institution ---
    r = 12
    ws1.merge_cells(f"A{r}:D{r}")
    ws1.cell(row=r, column=1, value="B. 金融机构信息").font = Font(name="Microsoft YaHei", size=12, bold=True, color="1A4334")

    r = 13
    style_header(ws1, r, 4, ["字段", "内容（中文）", "内容（英文）", "备注"])
    inst = data.get("broker", {})
    rows_b = [
        ("金融机构名称", inst.get("name", ""), inst.get("name_en", ""), ""),
        ("所在国家/地区", "中国香港", "Hong Kong, China", ""),
        ("账户号码", data.get("account_number", ""), data.get("account_number", ""), ""),
        ("账户类型", data.get("account_type", ""), "Margin / Custody Account", ""),
        ("账户开立日期", "", "", "需手动填写"),
    ]
    for i, row_data in enumerate(rows_b):
        r = 14 + i
        style_row(ws1, r, 4, row_data, fill=alt_fill if i % 2 == 0 else None)

    # --- Section C: Account Value ---
    r = 20
    ws1.merge_cells(f"A{r}:D{r}")
    ws1.cell(row=r, column=1, value="C. 账户余额/价值").font = Font(name="Microsoft YaHei", size=12, bold=True, color="1A4334")

    r = 21
    style_header(ws1, r, 4, ["币种", "现金余额", "持仓市值", "合计"])
    total_hkd = 0
    for i, (ccy, info) in enumerate(data.get("currencies", {}).items()):
        r = 22 + i
        cash = info.get("net_balance", info.get("cash", 0))
        stocks = info.get("stocks_value", 0)
        fund_v = info.get("fund_value", 0)
        total = info.get("total", 0)
        rate = info.get("exchange_rate", 1)
        hkd_eq = total * rate if rate else total
        total_hkd += hkd_eq
        style_row(ws1, r, 4, [
            ccy,
            f"{cash:,.2f}",
            f"{stocks + fund_v:,.2f}",
            f"{total:,.2f} (≈HKD {hkd_eq:,.2f})",
        ], fill=alt_fill if i % 2 == 0 else None)
    # Total row
    r = 22 + len(data.get("currencies", {}))
    style_row(ws1, r, 4, [
        "合计(HKD)", "", "",
        f"{data.get('total_value_hkd', total_hkd):,.2f}",
    ], font=Font(name="Microsoft YaHei", size=10, bold=True), fill=light_fill)

    # --- Section D: Income ---
    r_start_d = r + 2
    ws1.merge_cells(f"A{r_start_d}:D{r_start_d}")
    ws1.cell(row=r_start_d, column=1, value="D. 收入信息（本报告期）").font = Font(name="Microsoft YaHei", size=12, bold=True, color="1A4334")

    r = r_start_d + 1
    style_header(ws1, r, 4, ["收入类型", "币种", "金额", "备注"])
    
    # Calculate from transactions
    total_sells = defaultdict(float)
    total_buys = defaultdict(float)
    sell_count = defaultdict(int)
    buy_count = defaultdict(int)
    
    for t in data.get("transactions", []):
        ccy = t.get("currency", "USD")
        amt = t.get("net_amount") or t.get("amount", 0)
        if t.get("direction") == "卖出" or t.get("open_close") == "平仓":
            total_sells[ccy] += abs(amt)
            sell_count[ccy] += 1
        elif t.get("direction") == "买入" or t.get("open_close") == "开仓":
            total_buys[ccy] += abs(amt)
            buy_count[ccy] += 1
    
    income_rows = []
    # Gross sale proceeds
    for ccy in sorted(set(list(total_sells.keys()) + list(total_buys.keys()))):
        if total_sells[ccy] > 0:
            income_rows.append((
                f"卖出总收益（{sell_count[ccy]}笔）",
                ccy,
                f"{total_sells[ccy]:,.2f}",
                "未扣除买入成本，净收益需匹配买入记录计算"
            ))
        if total_buys[ccy] > 0:
            income_rows.append((
                f"买入总支出（{buy_count[ccy]}笔）",
                ccy,
                f"({total_buys[ccy]:,.2f})",
                "用于计算持仓成本基准"
            ))
    
    # Net estimate for same-product matched trades
    # Simple match: same product + sell + buy on this statement
    sells_by_product = defaultdict(list)
    buys_by_product = defaultdict(list)
    for t in data.get("transactions", []):
        product = t.get("product", "").split(":")[0].strip()
        amt = t.get("net_amount") or t.get("amount", 0)
        if t.get("direction") == "卖出" or t.get("open_close") == "平仓":
            sells_by_product[product].append(abs(amt))
        elif t.get("direction") == "买入":
            buys_by_product[product].append(abs(amt))
    
    matched_products = set(sells_by_product.keys()) & set(buys_by_product.keys())
    if matched_products:
        net_gains = defaultdict(float)
        for p in matched_products:
            total_sell = sum(sells_by_product[p])
            total_buy = sum(buys_by_product[p])
            # Note: this is approximate — quantities may not match exactly
            net_gains["HKD"] += 0  # placeholder, needs currency tracking
        income_rows.append((
            "⚠️ 同日买卖价差（参考）",
            "—",
            "—",
            f"同产品有买卖但数量/币种可能不匹配，需人工核验: {', '.join(sorted(matched_products))}"
        ))
    
    if not income_rows:
        income_rows = [
            ("卖出总收益", "—", "—", "本结单中未发现卖出交易"),
            ("买入总支出", "—", "—", "本结单中未发现买入交易"),
        ]
    
    # Also add a note about what's needed for full P&L
    income_rows.append((
        "💡 提示",
        "",
        "",
        "完整CRS收入申报需汇总全年结单。每笔卖出的净收益 = 卖出金额 - 对应买入成本。单日结单无法提供完整买入成本基准。"
    ))
    
    for i, row_data in enumerate(income_rows):
        r = r_start_d + 2 + i
        f = body_font
        if row_data[0].startswith("💡"):
            f = note_font
        style_row(ws1, r, 4, row_data, font=f, fill=alt_fill if i % 2 == 0 else None)

    # --- Disclaimer ---
    r = r + 3
    ws1.merge_cells(f"A{r}:D{r}")
    ws1.cell(row=r, column=1, value=(
        "⚠️ 免责声明：本表由系统自动生成，仅供参考。申报前请由专业税务顾问审核。"
        "\n部分字段（TIN、出生日期、收入明细）需手动补充。"
    )).font = note_font
    ws1.row_dimensions[r].height = 36

    auto_width(ws1)
    ws1.column_dimensions["B"].width = 30
    ws1.column_dimensions["C"].width = 35

    # =====================================================
    # Sheet 2: 持仓明细
    # =====================================================
    ws2 = wb.create_sheet("持仓明细")

    ws2.merge_cells("A1:F1")
    ws2.cell(row=1, column=1, value=f"持仓明细 — {data.get('statement_date', 'N/A')}").font = title_font
    ws2.row_dimensions[1].height = 30

    r = 3
    style_header(ws2, r, 6, ["代码", "名称", "币种", "类型", "市值", "备注"])
    holdings = data.get("holdings", [])
    if holdings:
        for i, h in enumerate(holdings):
            r = 4 + i
            style_row(ws2, r, 6, [
                h.get("code", ""),
                h.get("name", ""),
                h.get("currency", ""),
                h.get("type", ""),
                f"{h.get('market_value', 0):,.2f}",
                "",
            ], fill=alt_fill if i % 2 == 0 else None)
    else:
        r = 4
        style_row(ws2, r, 6, ["", "(未能自动提取持仓明细，请查看PDF原文)", "", "", "", ""])

    auto_width(ws2)

    # =====================================================
    # Sheet 3: 交易明细
    # =====================================================
    ws3 = wb.create_sheet("交易明细")

    ws3.merge_cells("A1:H1")
    ws3.cell(row=1, column=1, value=f"交易明细 — {data.get('statement_date', 'N/A')}").font = title_font
    ws3.row_dimensions[1].height = 30

    r = 3
    style_header(ws3, r, 8, ["日期", "方向", "产品", "币种", "价格", "数量", "金额", "参考编号"])
    transactions = data.get("transactions", [])
    if transactions:
        # Separate sell and buy for summary
        total_sell = 0
        total_buy = 0
        for i, t in enumerate(transactions):
            r = 4 + i
            direction = t.get("direction", "")
            open_close = t.get("open_close", "")
            label = f"{direction}{open_close}" if open_close else direction
            amt = t.get("net_amount") or t.get("amount", 0)
            style_row(ws3, r, 8, [
                t.get("trade_date", "") or t.get("settlement_date", ""),
                label,
                t.get("product", ""),
                t.get("currency", ""),
                f"{t.get('price', 0):.4f}",
                t.get("quantity", 0),
                f"{amt:,.2f}",
                t.get("ref_no", ""),
            ], fill=alt_fill if i % 2 == 0 else None)
            if direction == "卖出":
                total_sell += abs(amt)
            elif direction == "买入":
                total_buy += abs(amt)

        # Summary rows
        r = 4 + len(transactions) + 1
        style_row(ws3, r, 8, [
            "", "卖出合计", "", "", "", "", f"{total_sell:,.2f}", ""
        ], font=Font(name="Microsoft YaHei", size=10, bold=True), fill=light_fill)
        r += 1
        style_row(ws3, r, 8, [
            "", "买入合计", "", "", "", "", f"({total_buy:,.2f})", ""
        ], font=Font(name="Microsoft YaHei", size=10, bold=True))
        r += 1
        style_row(ws3, r, 8, [
            "", "⚠️ 净收益需匹配买入成本", "", "", "", "",
            f"卖出 {total_sell:,.2f} - 买入成本 = 净收益", ""
        ], font=note_font)
    else:
        r = 4
        style_row(ws3, r, 8, ["", "(未能自动提取交易明细)", "", "", "", "", "", ""])

    auto_width(ws3)

    # =====================================================
    # Sheet 4: 原始数据
    # =====================================================
    ws4 = wb.create_sheet("原始提取数据")
    ws4.cell(row=1, column=1, value="自动提取的原始数据（JSON格式，供核查）").font = note_font
    # Remove large raw text for cleaner JSON
    clean_data = {k: v for k, v in data.items() if k != "_raw_text"}
    json_str = json.dumps(clean_data, ensure_ascii=False, indent=2, default=str)
    for i, line in enumerate(json_str.split("\n"), 2):
        ws4.cell(row=i, column=1, value=line).font = Font(name="Consolas", size=9)
    ws4.column_dimensions["A"].width = 100

    wb.save(output_path)
    return output_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CRS Report Generator v3.0")
    parser.add_argument("pdf", help="Path to broker PDF statement")
    parser.add_argument("-o", "--output", default=None, help="Output Excel file path")
    parser.add_argument("--client-name-en", default=None, help="Client name in English")
    parser.add_argument("--tin", default=None, help="Tax Identification Number")
    parser.add_argument("--dob", default=None, help="Date of birth (YYYY-MM-DD)")
    parser.add_argument("--json", action="store_true", help="Output extracted data as JSON only")

    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: File not found: {args.pdf}")
        sys.exit(1)

    print(f"📄 Parsing: {pdf_path.name}")
    data = parse_statement(str(pdf_path))

    if "error" in data:
        print(f"❌ {data['error']}")
        if "text_preview" in data:
            print(f"Preview: {data['text_preview'][:300]}")
        sys.exit(1)

    client_info = {}
    if args.client_name_en:
        client_info["name_en"] = args.client_name_en
    if args.tin:
        client_info["tin"] = args.tin
    if args.dob:
        client_info["dob"] = args.dob

    print(f"✅ Detected: {data['broker']['name']}")
    print(f"   Client: {data.get('client_name', 'N/A')}")
    print(f"   Account: {data.get('account_number', 'N/A')}")
    print(f"   Date: {data.get('statement_date', 'N/A')}")
    print(f"   Total Value HKD: {data.get('total_value_hkd', 'N/A'):,.2f}")

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        output = args.output or f"CRS_{data.get('client_name','report')}_{data.get('statement_date','')}.xlsx"
        # Sanitize only the filename, not the directory path
        import os
        dirname = os.path.dirname(output) or "."
        basename = os.path.basename(output)
        basename = basename.replace("/", "-").replace(" ", "_")
        output = os.path.join(dirname, basename)
        generate_crs_excel(data, output, client_info)
        print(f"📊 Report saved: {output}")


if __name__ == "__main__":
    main()
