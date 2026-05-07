## ADDED Requirements

### Requirement: 自然语言策略起草必须先输出结构化策略概要
系统 SHALL 将用户的自然语言策略想法转成结构化策略概要，再决定是否输出 TOML 草案。

#### Scenario: 用户给出清晰意图
- **WHEN** 用户输入一段自然语言策略描述
- **THEN** 系统 MUST 输出策略概要，至少包含意图、模板候选、品种、周期、关键参数、默认假设、未确定项和下一步动作

#### Scenario: 用户输入过于模糊
- **WHEN** 用户的描述缺少策略类型、品种或周期等关键字段
- **THEN** 系统 MUST 提出澄清问题，不能静默补全并直接写出草案

### Requirement: 策略起草必须基于当前支持模板
系统 SHALL 仅允许将自然语言意图映射到当前支持的策略模板。v0.4.3 首版至少 MUST 支持现有的 R-breaker 相关模板；不支持的意图必须明确拒绝。

#### Scenario: 命中支持模板
- **WHEN** 用户的意图可以映射到当前支持模板
- **THEN** 系统 MUST 生成对应模板的策略草案

#### Scenario: 无法命中支持模板
- **WHEN** 用户的意图无法映射到当前支持模板
- **THEN** 系统 MUST 返回 unsupported_template 之类的明确结果，并说明原因和下一步

### Requirement: 草案必须输出可验证的 TOML
系统 SHALL 为成功起草的策略输出一个可编辑、可验证的 TOML 草案，且该草案 MUST 兼容现有 `kronos strategy validate`。

#### Scenario: 输出草案
- **WHEN** 策略概要通过模板匹配
- **THEN** 系统 MUST 输出 TOML 草案，并使用现有策略配置结构

#### Scenario: 草案不合法
- **WHEN** 生成内容无法通过现有策略配置校验
- **THEN** 系统 MUST 给出可读的修正原因，而不是输出一个不可验证的“完成品”

### Requirement: 起草流程必须接入现有验证链路
系统 SHALL 保持 `validate → smoke-test → register` 作为策略草案的后续标准链路，不得在起草版本绕过这些步骤。

#### Scenario: 草案生成完成
- **WHEN** 系统生成策略草案
- **THEN** 系统 MUST 明确下一步是 `validate`、`smoke-test` 或 `register`

#### Scenario: 用户要求立即进入验证
- **WHEN** 用户要求继续验证草案
- **THEN** 系统 MUST 复用现有验证命令和验证结果口径，而不是另起一套口径

### Requirement: 起草流程必须保留可追溯性
系统 SHALL 记录策略起草使用的 prompt_version、model_provider、model_name、输入摘要、模板命中和输出路径。

#### Scenario: 回查草案来源
- **WHEN** 用户或开发者回查某份草案
- **THEN** 系统 MUST 能定位到当次输入、模板命中和输出位置

### Requirement: 起草阶段不得输出伪证据
系统 SHALL 在起草阶段禁止输出盈利、有效性或历史表现结论；这些结论 MUST 仅来自后续验证、烟雾测试或报告链路。

#### Scenario: 用户问“能赚钱吗”
- **WHEN** 用户在起草阶段询问策略是否赚钱
- **THEN** 系统 MUST 明确说明草案阶段不能得出盈利结论，并引导进入验证链路

### Requirement: Docker 场景必须可复制
系统 SHALL 在 Docker 场景输出可复制的草案和下一步命令，不得把宿主机路径误导给容器用户。

#### Scenario: Docker 运行
- **WHEN** 用户在 Docker 内运行策略起草
- **THEN** 系统 MUST 输出容器内可直接复制的路径与下一步命令
