## MODIFIED Requirements

### Requirement: Quickstart and latest report must start with a result card
系统 SHALL 在首次体验结果页和最新报告摘要中优先展示稳定结果卡，帮助用户判断本次运行的边界和下一步。

#### Scenario: Quickstart finishes an automatic research run
- **WHEN** `kronos quickstart` 生成自动研究报告
- **THEN** 系统 MUST 在报告路径前展示结果卡
- **AND** 结果卡 MUST 包含数据来源、样本范围、评估对象、结论、可信度和下一步

#### Scenario: User opens latest report
- **WHEN** 用户运行 `kronos report latest`
- **THEN** 系统 MUST 先展示结果卡，再展示报告路径和 run_dir

#### Scenario: Sample data is used
- **WHEN** 结果来自 sample 或 synthetic 数据
- **THEN** 系统 MUST 明确说明这是流程试跑
- **AND** 系统 MUST NOT 暗示策略已经被证明有效或无效

### Requirement: Strategy next steps must preserve gates but use trader-facing language first
系统 SHALL 保留 `validate → smoke-test → register` 作为后续标准链路，但用户可见说明必须先解释每一步的交易研究含义。

#### Scenario: Strategy draft is ready
- **WHEN** `kronos strategy draft` 成功生成 TOML 草案
- **THEN** 系统 MUST 先说明草案不是可交易策略
- **AND** 系统 MUST 将三步解释为检查配置、空跑确认、进入候选池
- **AND** 系统 MUST 保留可复制的 `validate`、`smoke-test` 和 `register` 命令

#### Scenario: Default R-breaker config is created
- **WHEN** `kronos strategy init-r-breaker` 成功生成 TOML
- **THEN** 系统 MUST 将后续步骤解释为空跑确认和进入候选池

### Requirement: Docker first run must reduce false error perception
系统 SHALL 在 Docker 默认入口中说明首次运行的正常等待和结果边界，并把主下一步收敛为读取最新报告。

#### Scenario: Docker quickstart starts
- **WHEN** 用户运行 `docker compose up`
- **THEN** entrypoint MUST 说明首次运行会准备研究环境并生成 sample 流程试跑报告
- **AND** entrypoint MUST 说明依赖安装或下载输出不等于失败

#### Scenario: Docker quickstart completes
- **WHEN** Docker quickstart 完成
- **THEN** entrypoint MUST 优先提示用户读取 `report latest`
- **AND** Agent 或策略起草入口 MUST 作为读完结论后的后续动作
