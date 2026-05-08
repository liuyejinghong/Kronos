## ADDED Requirements

### Requirement: Replay report must expose key-trade replay
系统 SHALL 提供独立关键交易重放入口，让用户能从结果卡之后继续查看关键入场、出场和失败节点。

#### Scenario: User opens replay after latest report
- **WHEN** 用户查看 `report latest` 的结果卡后继续解释下钻
- **THEN** 系统 MUST 提供 `report replay` 关键交易重放入口
- **AND** 重放 MUST 包含入场原因、出场原因、结果和周边市场背景

#### Scenario: Strategy had failing windows
- **WHEN** 一段策略表现明显变差或连续失败
- **THEN** 系统 MUST 将失败窗口单独暴露出来
- **AND** 系统 MUST NOT 只给总收益或总回撤而不解释过程

### Requirement: Replay must stay on key events by default
系统 SHALL 默认只展示关键交易和关键失败窗口，不要求用户先看全量逐 bar 播放。

#### Scenario: Many trades exist
- **WHEN** 一轮研究里存在大量交易
- **THEN** 系统 MUST 默认优先展示代表性和关键性最高的交易
- **AND** 系统 MAY 提供更细粒度下钻，但不能把全量回放当作第一屏

### Requirement: Replay must not imply profitability
系统 SHALL 在关键交易重放中保持证据边界，不得把重放过程描述成收益证明或实盘证明。

#### Scenario: User asks whether replay proves strategy is good
- **WHEN** 用户将重放结果理解为盈利证明
- **THEN** 系统 MUST 明确说明重放只能解释过程，不能替代验证结论
