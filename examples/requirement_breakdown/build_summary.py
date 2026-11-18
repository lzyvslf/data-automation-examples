"""规则型需求拆解示例：多张销售明细 CSV 汇总成一张总表，标出当周新增金额。

对应拆解步骤：先写规则清单，再分采集 / 清洗 / 处理 / 输出四段，
容易变的内容参数化，关键步骤记日志，输出前做行数与合计核对。

运行：
    python build_summary.py --input-dir ../../samples --output summary.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("summary")

REQUIRED_COLUMNS = {"order_no", "amount", "updated_at"}


def collect(input_dir: Path) -> List[dict]:
    """采集：读取目录下所有明细 csv，跳过汇总产物文件。"""
    files = sorted(p for p in input_dir.glob("*.csv") if not p.name.startswith("summary"))
    if not files:
        raise FileNotFoundError(f"目录下没有明细 csv 文件：{input_dir}")
    rows: List[dict] = []
    for f in files:
        with f.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                rows.append(row)
    logger.info("采集完成，文件 %d 个，原始行 %d", len(files), len(rows))
    return rows


def clean(rows: List[dict]) -> List[dict]:
    """清洗：统一表头与数据类型，非法金额直接报错停下。"""
    cleaned: List[dict] = []
    for row in rows:
        missing = REQUIRED_COLUMNS - set(row.keys())
        if missing:
            raise ValueError(f"缺字段 {missing}，表头：{list(row.keys())}")
        try:
            amount = float(row["amount"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"金额不是数字：{row}") from exc
        cleaned.append(
            {"order_no": row["order_no"].strip(), "amount": amount,
             "updated_at": row["updated_at"].strip()}
        )
    logger.info("清洗完成，有效行 %d", len(cleaned))
    return cleaned


def process(rows: List[dict], week_start: date) -> List[dict]:
    """处理：按单号去重求和，标出当周新增金额。"""
    agg: Dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "updated_at": ""})
    for row in rows:
        item = agg[row["order_no"]]
        item["amount"] += row["amount"]
        item["updated_at"] = max(item["updated_at"], row["updated_at"])

    summary: List[dict] = []
    for order_no, item in agg.items():
        updated = datetime.strptime(item["updated_at"], "%Y-%m-%d").date()
        is_new = week_start <= updated
        summary.append({
            "order_no": order_no,
            "total_amount": round(item["amount"], 2),
            "week_new_amount": round(item["amount"], 2) if is_new else 0.0,
            "updated_at": item["updated_at"],
        })
    logger.info("聚合完成，订单数 %d", len(summary))
    return summary


def output(summary: List[dict], output_path: Path) -> None:
    """输出：写汇总表，写前核对合计金额。"""
    source_total = round(sum(r["total_amount"] for r in summary), 2)
    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["order_no", "total_amount", "week_new_amount", "updated_at"])
        writer.writeheader()
        writer.writerows(summary)
    logger.info("已写出 %s，合计金额 %.2f", output_path, source_total)


def main() -> None:
    parser = argparse.ArgumentParser(description="销售明细汇总示例")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--week-start", default=None, help="当周起始日期 YYYY-MM-DD，默认今天")
    args = parser.parse_args()

    week_start = (
        datetime.strptime(args.week_start, "%Y-%m-%d").date()
        if args.week_start else date.today()
    )

    rows = collect(args.input_dir)
    cleaned = clean(rows)
    summary = process(cleaned, week_start)
    output(summary, args.output)


if __name__ == "__main__":
    main()
