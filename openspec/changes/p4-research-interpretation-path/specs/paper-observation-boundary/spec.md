## ADDED Requirements

### Requirement: Paper observation must be explicitly read-only
系统 SHALL 在进入只读观察前明确这是只读观察态，不得与真实执行态混淆。

#### Scenario: User enters observation mode
- **WHEN** 用户进入只读观察路径
- **THEN** 系统 MUST 明确说明当前不会发送真实订单
- **AND** 系统 MUST 记录这是只读观察态，而不是实盘态

### Requirement: Paper observation must include virtual order assumptions
系统 SHALL 在只读观察中记录虚拟订单、延迟和滑点假设。

#### Scenario: Observation generates a fill
- **WHEN** 观察态产生虚拟成交
- **THEN** 系统 MUST 记录使用的延迟和滑点假设
- **AND** 系统 MUST 将该成交标记为虚拟成交而非真实成交

### Requirement: Paper observation must preserve human gate
系统 SHALL 在只读观察与更强执行态之间保留人工闸门。

#### Scenario: Observation looks promising
- **WHEN** 只读观察结果看起来有吸引力
- **THEN** 系统 MUST 仍然要求人工确认后再进入下一步
- **AND** 系统 MUST NOT 自动升级到实盘执行

### Requirement: Paper observation must stay separated from live execution
系统 SHALL 将只读观察态与实盘执行态在文案、状态和报告上严格分开。

#### Scenario: User compares paper and live
- **WHEN** 用户查看观察态和执行态
- **THEN** 系统 MUST 清楚区分两者的权限、风险和结果含义
- **AND** 系统 MUST NOT 使用同一份默认文案模糊边界
