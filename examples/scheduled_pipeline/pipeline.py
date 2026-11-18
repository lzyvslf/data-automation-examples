"""定时复盘流水线示例。

演示一条无人值守链路：采集 -> 清洗聚合 -> 模块化报告 -> 推送。
包含重试退避、失败告警、断点续跑和空值标注。示例不请求真实行情接口，
数据源由 provider 注入，便于本地跑通和替换。

运行：
    python pipeline.py
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("pipeline")

RETRY_TIMES = 3
BACKOFF_SECONDS = [2, 5, 10]  # 第 1/2/3 次重试前等待时长
REPORT_MODULES = [
    "market_overview", "limit_up_down", "dragon_tiger", "money_flow",
    "sector_perf", "volume_move", "leaders", "northbound",
    "stock_move", "news", "conclusion",
]
EMPTY_MARK = "暂无数据"


@dataclass
class StageState:
    """记录各阶段是否成功，用于断点续跑。"""

    stages: Dict[str, bool] = field(default_factory=dict)

    def done(self, stage: str) -> bool:
        return self.stages.get(stage, False)

    def mark(self, stage: str, ok: bool) -> None:
        self.stages[stage] = ok


def fetch_source(source: str) -> List[dict]:
    """模拟外部数据源。真实场景替换为接口调用。

    抛出异常由上层重试；返回空列表视为空值/限流，单独归类。
    """
    raise NotImplementedError("在真实场景中替换为具体数据源采集")


def collect(source_fetch: Callable[[str], List[dict]]) -> Dict[str, List[dict]]:
    collected: Dict[str, List[dict]] = {}
    for source in ("src_a", "src_b", "src_c"):
        data: List[dict] = []
        for attempt in range(1, RETRY_TIMES + 1):
            try:
                data = source_fetch(source)
                break
            except Exception as exc:  # 单源失败不阻塞主流程
                logger.warning("采集失败 %s 第 %d 次：%s", source, attempt, exc)
                if attempt < RETRY_TIMES:
                    time.sleep(BACKOFF_SECONDS[attempt - 1])
                else:
                    logger.error("源 %s 重试 %d 次仍失败，跳过该源", source, RETRY_TIMES)
        collected[source] = data
    return collected


def clean(collected: Dict[str, List[dict]]) -> List[dict]:
    """去重、补缺标记、格式统一；脏数据不进入报告。"""
    seen = set()
    rows: List[dict] = []
    for source, items in collected.items():
        for item in items:
            key = (item.get("code"), item.get("date"))
            if key in seen:
                continue
            seen.add(key)
            row = {"source": source, "code": item.get("code"), "date": item.get("date")}
            for field_name in ("close", "volume"):
                value = item.get(field_name)
                row[field_name] = value if value is not None else None
            rows.append(row)
    return rows


def build_report(rows: List[dict]) -> Dict[str, str]:
    report: Dict[str, str] = {}
    for module in REPORT_MODULES:
        report[module] = _render_module(module, rows)
    return report


def _render_module(module: str, rows: List[dict]) -> str:
    if not rows:
        return f"{module}: {EMPTY_MARK}"
    # 真实场景按模块口径聚合；这里仅演示模板填充与空值标注。
    return f"{module}: 共 {len(rows)} 条记录已聚合"


def alert(message: str) -> None:
    """告警钩子。真实场景替换为推送渠道。"""
    logger.warning("[ALERT] %s", message)


def run(source_fetch: Optional[Callable[[str], List[dict]]] = None,
        push: Optional[Callable[[Dict[str, str]], None]] = None) -> Dict[str, str]:
    state = StageState()

    # 断点续跑：已成功的阶段不重复执行。
    if not state.done("collect"):
        collected = collect(source_fetch or fetch_source)
        state.mark("collect", True)
    else:
        collected = {}

    if not state.done("clean"):
        rows = clean(collected)
        state.mark("clean", True)
    else:
        rows = []

    report = build_report(rows)
    state.mark("report", True)

    if push is not None:
        try:
            push(report)
        except Exception as exc:
            alert(f"推送失败：{exc}")
    return report


def _demo_fetch(source: str) -> List[dict]:
    return [
        {"code": "600000", "date": "2026-11-17", "close": 10.20, "volume": 120000},
        {"code": "600001", "date": "2026-11-17", "close": 20.00, "volume": 300000},
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="定时复盘流水线示例")
    parser.add_argument("--print-report", action="store_true", help="打印生成的报告模块")
    args = parser.parse_args()

    report = run(source_fetch=_demo_fetch)
    logger.info("流水线执行完成，模块数：%d", len(report))
    if args.print_report:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
