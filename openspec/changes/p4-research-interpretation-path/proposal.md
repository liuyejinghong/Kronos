## Why

v0.4.4 解决的是“用户第一眼能不能看懂结果”。但交易者在下一步会立刻追问三个问题：为什么会这样、在什么市场状态下会这样、能不能先放到只读观察里再看一下。

Kronos 现在已经有报告、诊断、watchlist 和 smoke-test 的基础能力，但这些能力还没有被组织成一条稳定的解释路径。v0.4.5 要补的不是更多功能按钮，而是把结果卡之后的解释链路收口。

## What Changes

- 新增关键交易重放路径，让用户能从报告跳到关键入场 / 出场 / 失败节点。
- 新增市场状态分段评估，把同一策略在牛市、熊市、震荡市和高波动环境下的表现分开呈现。
- 新增只读观察边界，明确虚拟订单、延迟、滑点和人工闸门，避免把观察态误认为实盘。
- 新增逐 symbol smoke-test 约束，保证策略配置中的每个品种都被单独验证。

## Capabilities

### New Capabilities

- `strategy-interpretation`: 从结果卡继续下钻到关键交易、市场状态和样本外解释。
- `paper-observation-boundary`: 明确只读观察态与真实执行态的边界。

### Modified Capabilities

- `report-latest`: 最新报告第一屏之后必须能继续下钻到关键交易和市场状态分段。
- `strategy-smoke-test`: smoke-test 必须覆盖所有声明 symbol。
- `agent-workbench`: Agent 和 Web 需要展示“为什么这样”“在哪个环境下这样”“是否值得继续观察”。

## Impact

- **新增用户路径**：`report latest` 稳定展示结果卡，随后通过 `report replay`、`report regime`、`report observation` 进入解释下钻。
- **新增约束**：多品种策略不能只验证第一个 symbol。
- **不变约束**：不引入实盘执行、不自动下单、不把观察态说成收益证明。
