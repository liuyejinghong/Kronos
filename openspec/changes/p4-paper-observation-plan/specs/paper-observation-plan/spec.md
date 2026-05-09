## ADDED Requirements

### Requirement: Observation plan must be generated from an existing report
系统 SHALL 从已有研究报告生成只读观察计划，不得在没有报告证据时凭空生成观察建议。

#### Scenario: Latest report exists
- **WHEN** 用户运行 `kronos report observation-plan`
- **THEN** 系统 MUST 找到最新产品报告
- **AND** 系统 MUST 生成只读观察计划
- **AND** 系统 MUST 记录来源报告路径

#### Scenario: No report exists
- **WHEN** 用户运行 `kronos report observation-plan` 且没有任何研究报告
- **THEN** 系统 MUST 失败并提示先运行 quickstart 或研究工作台

### Requirement: Observation plan must include an eligibility verdict
系统 SHALL 在观察计划中给出是否适合进入只读观察的明确判断。

#### Scenario: Report is generated from sample data
- **WHEN** 来源报告来自 sample 试跑
- **THEN** 系统 MUST 明确说明不建议进入观察
- **AND** 系统 MUST 引导用户先同步真实行情

#### Scenario: Report has promoted candidates
- **WHEN** 来源报告中存在通过验证的策略
- **THEN** 系统 MAY 给出“只读观察候选”判断
- **AND** 系统 MUST 明确这仍不是模拟盘运行或实盘建议

### Requirement: Observation plan must include virtual order assumptions
系统 SHALL 在观察计划中记录虚拟订单、延迟和滑点假设。

#### Scenario: User reads the plan
- **WHEN** 用户阅读只读观察计划
- **THEN** 系统 MUST 明确说明不会发送真实订单
- **AND** 系统 MUST 说明默认延迟和滑点假设
- **AND** 系统 MUST 说明未来虚拟成交必须标记为虚拟成交

### Requirement: Observation plan must preserve human gate
系统 SHALL 在只读观察计划中保留人工闸门，不得自动升级到更强执行态。

#### Scenario: Observation looks promising
- **WHEN** 计划或未来观察结果看起来有吸引力
- **THEN** 系统 MUST 仍然要求人工确认
- **AND** 系统 MUST NOT 自动进入实盘执行
