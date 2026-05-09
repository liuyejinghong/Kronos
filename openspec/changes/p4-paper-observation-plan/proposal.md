## Why

v0.4.5 已经定义了只读观察边界，但用户仍缺少一个可执行的中间产物：研究报告之后，真正进入实时模拟盘之前，系统应该先生成一份只读观察计划。

这份计划不是 paper trading 引擎，也不是实盘前置开关。它是一个产品闸门：把“当前研究结果能不能继续观察、按什么假设观察、哪些动作必须人工确认”写清楚。

## What Changes

- 新增 `kronos report observation-plan` 用户入口。
- 新增只读观察计划 Markdown 产物。
- 计划从最新报告或指定报告生成，不凭空生成。
- 计划必须包含观察准入判断、虚拟订单假设、延迟/滑点假设、人工闸门和来源报告。
- sample 试跑、短样本和未通过策略必须被明确拦住或降级。

## Capabilities

### New Capabilities

- `paper-observation-plan`: 从研究报告生成只读观察计划。

### Modified Capabilities

- `report-latest`: 结果卡之后可以自然接到观察计划。
- `paper-observation-boundary`: 从静态边界说明升级为可落盘计划。

## Impact

- **新增用户路径**：`report latest -> report observation-plan`。
- **新增产物**：`paper_observation_plan.md`。
- **不变约束**：不接真实 API Key，不启动实时模拟盘，不自动下单，不把观察计划说成收益证明。
