from pathlib import Path


def test_skill_copy_is_tax_estimate_not_crs_form():
    text = Path("skills/crs-report-generator/SKILL.md").read_text(encoding="utf-8")
    assert "境外投资补税测算" in text
    assert "CRS 金融账户信息申报表" not in text
    assert "需手动填写" not in text
    assert "客户身份证号 (TIN)" not in text
    assert "WorkBuddy" in text or "豆包" in text
    assert "禁止问" in text
