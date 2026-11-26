import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "crs-report-generator"

SAMPLE = {
    "trades": [
        {"side": "buy", "symbol": "AAA", "qty": 100, "amount": 1000, "fees": 10, "currency": "HKD", "date": "2023-05-02"},
        {"side": "sell", "symbol": "AAA", "qty": 100, "amount": 1500, "fees": 15, "currency": "HKD", "date": "2024-03-01"},
        {"side": "sell", "symbol": "BBB", "qty": 5, "amount": 500, "currency": "USD", "date": "2024-04-01"},
        {"side": "sell", "symbol": "AAA", "qty": 1, "amount": 99, "currency": "HKD", "date": "2025-01-02"},
    ],
    "income": [
        {"kind": "dividend", "amount": 100, "foreign_tax_paid": 30, "currency": "USD", "date": "2024-06-01"},
        {"kind": "dividend", "amount": 999, "currency": "USD", "date": "2023-06-01"},
    ],
}


def write_sample(tmp_path: Path) -> Path:
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(SAMPLE), encoding="utf-8")
    return path


def run(args, cwd):
    return subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def test_cli_module_json_with_fx(tmp_path):
    sample = write_sample(tmp_path)
    proc = run(["-m", "scripts.cli", "--year", "2024", "--fx-rates", "HKD=0.92,USD=7.20", "--format", "json", str(sample)], SKILL_DIR)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["year"] == 2024
    assert data["tax_due"]["currency"] == "CNY"
    assert data["tax_due"]["total"] == 87.4  # (1485-1010)*0.92*20%；分红抵免超限额后为 0
    assert data["missing"]["unmatched_sales"][0]["symbol"] == "BBB"
    assert len(data["sections"]) == 4


def test_cli_direct_script_path_markdown_without_fx(tmp_path):
    sample = write_sample(tmp_path)
    proc = run([str(SKILL_DIR / "scripts" / "cli.py"), "--year", "2024", str(sample)], tmp_path)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "未提供汇率，按原币种分列" in out
    assert "税前应纳" in out and "外国已扣税抵免" in out and "预计需补税" in out
    assert "这是测算底稿" in out


def test_cli_fx_json_file_and_output_file(tmp_path):
    sample = write_sample(tmp_path)
    rates = tmp_path / "rates.json"
    rates.write_text(json.dumps({"HKD": 0.92}), encoding="utf-8")
    out = tmp_path / "report.json"
    proc = run(["-m", "scripts.cli", "--year", "2024", "--fx-rates", str(rates), "--format", "json", "--output", str(out), str(sample)], SKILL_DIR)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["fx"]["missing_currencies"] == ["USD"]
    assert data["tax_due"]["total"] is None
    assert data["tax_due"]["by_currency"] == {"CNY": 87.4, "USD": 0.0}


def test_cli_requires_year(tmp_path):
    sample = write_sample(tmp_path)
    proc = run(["-m", "scripts.cli", str(sample)], SKILL_DIR)
    assert proc.returncode == 2
    assert "--year" in proc.stderr


def test_cli_rejects_bad_fx(tmp_path):
    sample = write_sample(tmp_path)
    proc = run(["-m", "scripts.cli", "--year", "2024", "--fx-rates", "HKD=abc", str(sample)], SKILL_DIR)
    assert proc.returncode == 2
