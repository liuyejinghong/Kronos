## ADDED Requirements

### Requirement: Strategy results must be segmented by market regime
系统 SHALL 把同一策略在不同市场状态下的结果分开呈现。

#### Scenario: Report generated for one strategy
- **WHEN** 系统生成研究报告或 Agent 结论
- **THEN** 系统 MUST 至少区分牛市、熊市、震荡市和高波动环境
- **AND** 每个分段 MUST 有独立摘要和独立结论

#### Scenario: One regime is weak but overall average looks okay
- **WHEN** 某个分段明显表现较差
- **THEN** 系统 MUST 单独暴露该分段的风险
- **AND** 系统 MUST NOT 仅用整体平均值掩盖分段差异

### Requirement: Regime labels must be stable across surfaces
系统 SHALL 在报告、Agent、Web 和 watchlist 相关输出中使用一致的市场状态标签。

#### Scenario: User compares two reports
- **WHEN** 用户比较不同批次或不同策略的结果
- **THEN** 系统 MUST 使用同一套 regime 标签与定义
- **AND** 系统 MUST NOT 在不同界面里用不同名称表示同一状态

### Requirement: Regime segmentation must support gating decisions
系统 SHALL 让每个市场状态分段可以独立支持或反对继续观察。

#### Scenario: Strategy works in trend but not in chop
- **WHEN** 一个策略只在趋势环境里表现好
- **THEN** 系统 MUST 明确说明它在震荡环境中的风险
- **AND** 系统 MUST 支持按 regime 单独给出是否继续观察的判断
