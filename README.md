# data-automation-examples

Python 数据处理与自动化脚本示例集。三个示例对应常见的工程场景：多源数据校验、定时复盘流水线、规则型需求拆解。代码只用标准库，clone 下来即可运行，示例数据为合成数据。

## 目录结构

```
data-automation-examples/
├── examples/
│   ├── data_validation/        # 多源数据交叉校验
│   │   └── validate_multi_source.py
│   ├── scheduled_pipeline/    # 定时复盘流水线
│   │   └── pipeline.py
│   └── requirement_breakdown/  # 规则型需求拆解到脚本
│       └── build_summary.py
├── samples/                    # 合成样例数据
├── requirements.txt
└── LICENSE
```

## 环境要求

- Python 3.11 及以上
- 无第三方依赖，不需要额外安装包

## 快速运行

### 1. 多源数据交叉校验

以代码加交易日为对齐键，统一口径，对收盘价、成交量算偏离幅度，结论分为
consistent / acceptable / inconsistent / missing 四类，只有通过校验的记录才进入后续环节。

```bash
python examples/data_validation/validate_multi_source.py
```

### 2. 定时复盘流水线

演示采集、清洗聚合、模块化报告、推送一条链路，包含重试退避（3 次，间隔 2/5/10 秒）、
失败告警、断点续跑和空值标注。数据源由 provider 注入，方便替换成真实接口。

```bash
python examples/scheduled_pipeline/pipeline.py --print-report
```

### 3. 规则型需求拆解

读取目录下多张销售明细 CSV，按单号去重求和，标出当周新增金额。演示规则清单、
四段流水线、参数化、日志校验和最小可用版本的拆解思路。

```bash
python examples/requirement_breakdown/build_summary.py \
  --input-dir samples \
  --output summary_demo.csv \
  --week-start 2026-11-17
```

## 设计边界

- 仓库内不包含任何真实业务数据、接口密钥或私有工程代码，样例数据均为合成。
- 涉及行情与复盘的示例只讲数据工程与自动化方法，不构成任何投资建议。
- 不提供绕过平台限制、批量违规采集或灰产相关的实现。

## License

MIT
