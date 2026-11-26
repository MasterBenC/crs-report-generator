"""统一命令行入口：结单 PDF / JSON -> 四板块补税测算报告。

在 skill 目录下运行：
    python3 -m scripts.cli --year 2024 --fx-rates HKD=0.92,USD=7.20 statements/*.pdf
或直接用脚本路径：
    python3 /path/to/crs-report-generator/scripts/cli.py --year 2024 trades.json

退出码：0 成功；2 参数或输入有误。
"""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    # 直接用脚本路径运行时，把 skill 目录加入 sys.path，保证 `scripts.*` 导入一致。
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.adapter import load_inputs  # noqa: E402
from scripts.fx import parse_fx_rates  # noqa: E402
from scripts.pipeline import run_pipeline  # noqa: E402
from scripts.report import render_markdown, report_to_dict  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.cli",
        description="境外投资补税测算：读取结单 PDF 或 JSON，输出四板块报告（测算底稿，需人工审核）。",
    )
    parser.add_argument("inputs", nargs="+", help="结单 PDF（目前华泰模板）或 JSON（解析输出 / trades+income 结构化输入）")
    parser.add_argument("--year", type=int, required=True, help="申报年度，例如 2024。只统计这一年的卖出和分红利息")
    parser.add_argument(
        "--fx-rates",
        help="汇率：JSON 文件路径，或 HKD=0.92,USD=7.20（1 单位外币 = 多少人民币）。不给则按原币种分列",
    )
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="输出格式，默认 markdown")
    parser.add_argument("--output", help="写入文件；不给则输出到标准输出")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not 1900 <= args.year <= 2100:
        parser.error("--year 应是四位年份，例如 2024")
    try:
        fx_rates = parse_fx_rates(args.fx_rates)
        adapted = load_inputs(args.inputs)
    except (ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    report = run_pipeline(
        adapted.trades,
        adapted.income_items,
        year=args.year,
        fx_rates=fx_rates,
        input_warnings=adapted.warnings,
    )
    if args.format == "json":
        text = json.dumps(report_to_dict(report), ensure_ascii=False, indent=2)
    else:
        text = render_markdown(report)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
