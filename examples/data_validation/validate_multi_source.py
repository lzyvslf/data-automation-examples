"""多源行情数据交叉校验示例。

演示思路：先对齐口径，再比对关键字段，最后按一致 / 可接受偏差 / 不一致
三类输出校验结论。示例数据为合成数据，不接入任何真实行情接口。

运行：
    python validate_multi_source.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# 偏离阈值：收盘价 1%，成交量 5%。超过即记为不一致。
CLOSE_TOLERANCE = 0.01
VOLUME_TOLERANCE = 0.05


@dataclass
class SourceRecord:
    source: str
    code: str
    date: str
    close: Optional[float]
    volume: Optional[float]
    adj: str  # 复权方式，如 qfq / hfq / none


@dataclass
class ValidationResult:
    key: str
    code: str
    date: str
    status: str
    notes: List[str] = field(default_factory=list)
    diffs: List[dict] = field(default_factory=list)


def normalize(raw: dict) -> SourceRecord:
    """统一字段口径：缺失值保留为 None，不填零、不前向填充。"""
    return SourceRecord(
        source=raw["source"],
        code=raw["code"].strip().upper(),
        date=raw["date"],
        close=_to_float(raw.get("close")),
        volume=_to_float(raw.get("volume")),
        adj=str(raw.get("adj", "none")).lower(),
    )


def _to_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def align(records: List[SourceRecord]) -> Dict[str, Dict[str, SourceRecord]]:
    """以 (代码, 交易日) 为对齐键，按源归组。"""
    aligned: Dict[str, Dict[str, SourceRecord]] = {}
    for rec in records:
        key = f"{rec.code}|{rec.date}"
        aligned.setdefault(key, {})[rec.source] = rec
    return aligned


def _deviation(a: float, b: float) -> float:
    base = b if b not in (0, None) else a
    if base in (0, None):
        return 0.0
    return abs(a - b) / base


def compare(key: str, code: str, date: str, by_source: Dict[str, SourceRecord]) -> ValidationResult:
    notes: List[str] = []
    diffs: List[dict] = []
    sources = list(by_source.values())

    # 任一源缺字段，先记缺失，不参与数值比对。
    missing = [s.source for s in sources if s.close is None or s.volume is None]
    if missing:
        notes.append(f"缺失字段，来源：{', '.join(missing)}")

    closes = {s.source: s.close for s in sources if s.close is not None}
    volumes = {s.source: s.volume for s in sources if s.volume is not None}

    inconsistent = False
    acceptable = False

    if len(closes) >= 2:
        ref = next(iter(closes.values()))
        for src, close in closes.items():
            dev = _deviation(close, ref)
            diffs.append({"field": "close", "source": src, "value": close, "deviation": round(dev, 4)})
            if dev > CLOSE_TOLERANCE:
                inconsistent = True
            elif dev > CLOSE_TOLERANCE / 2:
                acceptable = True

    if len(volumes) >= 2:
        ref = next(iter(volumes.values()))
        for src, vol in volumes.items():
            dev = _deviation(vol, ref)
            diffs.append({"field": "volume", "source": src, "value": vol, "deviation": round(dev, 4)})
            if dev > VOLUME_TOLERANCE:
                inconsistent = True
            elif dev > VOLUME_TOLERANCE / 2:
                acceptable = True

    if inconsistent:
        status = "inconsistent"
    elif missing:
        status = "missing"
    elif acceptable:
        status = "acceptable"
    else:
        status = "consistent"

    return ValidationResult(key=key, code=code, date=date, status=status, notes=notes, diffs=diffs)


def validate(records: List[SourceRecord]) -> List[ValidationResult]:
    aligned = align(records)
    results: List[ValidationResult] = []
    for key, by_source in aligned.items():
        first = next(iter(by_source.values()))
        results.append(compare(key, first.code, first.date, by_source))
    return results


def _demo_records() -> List[SourceRecord]:
    raw = [
        # 一致记录
        {"source": "src_a", "code": "600000", "date": "2026-11-17", "close": 10.20, "volume": 120000, "adj": "qfq"},
        {"source": "src_b", "code": "600000", "date": "2026-11-17", "close": 10.21, "volume": 121000, "adj": "qfq"},
        {"source": "src_c", "code": "600000", "date": "2026-11-17", "close": 10.20, "volume": 119500, "adj": "qfq"},
        # 小偏差可接受
        {"source": "src_a", "code": "600001", "date": "2026-11-17", "close": 20.00, "volume": 300000, "adj": "qfq"},
        {"source": "src_b", "code": "600001", "date": "2026-11-17", "close": 20.15, "volume": 305000, "adj": "qfq"},
        # 不一致：收盘价偏离过大
        {"source": "src_a", "code": "600002", "date": "2026-11-17", "close": 8.80, "volume": 80000, "adj": "qfq"},
        {"source": "src_b", "code": "600002", "date": "2026-11-17", "close": 9.60, "volume": 81000, "adj": "qfq"},
        # 缺失值单独标记
        {"source": "src_a", "code": "600003", "date": "2026-11-17", "close": None, "volume": None, "adj": "qfq"},
        {"source": "src_b", "code": "600003", "date": "2026-11-17", "close": 15.40, "volume": 220000, "adj": "qfq"},
    ]
    return [normalize(r) for r in raw]


def main() -> None:
    results = validate(_demo_records())
    summary = {"consistent": 0, "acceptable": 0, "inconsistent": 0, "missing": 0}
    for r in results:
        summary[r.status] += 1
        print(f"[{r.status}] {r.code} {r.date}")
        for note in r.notes:
            print(f"  - {note}")
        for d in r.diffs:
            print(f"  - {d['field']} {d['source']}={d['value']} dev={d['deviation']}")

    print("\n汇总：", json.dumps(summary, ensure_ascii=False))
    blocked = [r.key for r in results if r.status == "inconsistent"]
    print("未通过校验、不进入后续环节的记录：", blocked or "无")


if __name__ == "__main__":
    main()
