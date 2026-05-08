## ADDED Requirements

### Requirement: Smoke-test must evaluate every declared symbol
系统 SHALL 对策略配置中声明的每个 symbol 单独执行 smoke-test。

#### Scenario: Strategy has multiple symbols
- **WHEN** 一个策略配置里声明了多个 symbol
- **THEN** 系统 MUST 对每个 symbol 生成独立的 smoke-test 结果
- **AND** 系统 MUST NOT 只验证第一个 symbol 就返回整体成功

### Requirement: Symbol-level failures must be visible
系统 SHALL 在多品种 smoke-test 中显式暴露单个 symbol 的失败。

#### Scenario: One symbol fails but others pass
- **WHEN** 某个 symbol 失败而其他 symbol 通过
- **THEN** 系统 MUST 在结果里指出失败的 symbol 和失败原因
- **AND** 系统 MUST NOT 用整体通过掩盖局部失败

### Requirement: Multi-symbol smoke-test must keep product language
系统 SHALL 用交易者可理解的语言描述逐 symbol smoke-test 的结果。

#### Scenario: User reads smoke-test report
- **WHEN** 用户查看多品种 smoke-test 输出
- **THEN** 系统 MUST 告诉用户“哪个品种能跑、哪个品种不能跑、为什么”
- **AND** 系统 MUST 仍然保留可追踪的技术细节和配置路径
