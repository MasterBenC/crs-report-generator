from pathlib import Path


def test_skill_copy_is_tax_estimate_not_crs_form():
    text = Path("skills/crs-report-generator/SKILL.md").read_text(encoding="utf-8")
    assert "境外投资补税测算" in text
    assert "CRS 金融账户信息申报表" not in text
    assert "需手动填写" not in text
    assert "客户身份证号 (TIN)" not in text
    assert "WorkBuddy" in text or "豆包" in text
    assert "禁止问" in text


def test_skill_version_and_cli_docs():
    text = Path("skills/crs-report-generator/SKILL.md").read_text(encoding="utf-8")
    assert "version: 3.1.0" in text
    assert "python3 -m scripts.cli --year" in text
    assert "--fx-rates" in text


def test_readme_and_install_do_not_require_openpyxl():
    assert "openpyxl" not in Path("README.md").read_text(encoding="utf-8")
    install = Path("install.sh").read_text(encoding="utf-8")
    assert "openpyxl" not in install
    assert "rsync -a --delete --exclude='__pycache__' --exclude='*.pyc'" in install
