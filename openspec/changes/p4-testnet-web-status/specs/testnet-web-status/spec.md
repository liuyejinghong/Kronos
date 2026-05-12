## ADDED Requirements

### Requirement: Real testnet E2E must keep all paper trading gates
系统 SHALL 只有在测试网凭证、合格观察候选、观察计划和 preflight 全部通过后，才允许真实 Binance testnet 下单。

#### Scenario: Credentials are missing
- **WHEN** 用户尝试真实 testnet E2E
- **AND** Binance testnet API Key / Secret 未配置
- **THEN** 系统 MUST 拒绝启动
- **AND** 系统 MUST 给出配置测试网凭证的下一步

#### Scenario: No promoted candidate exists
- **WHEN** 真实数据研究没有 promoted 候选
- **THEN** 系统 MUST 拒绝进入 testnet 下单
- **AND** 系统 MUST 保留阻塞报告

#### Scenario: Preflight passes and user authorizes
- **WHEN** 凭证、观察计划、风控和 preflight 全部通过
- **AND** 用户明确授权
- **THEN** 系统 MAY 提交一笔受限 Binance testnet 订单

### Requirement: Real testnet evidence must be traceable
系统 SHALL 保留真实 testnet 订单、成交、错误、状态和报告证据。

#### Scenario: Testnet order is submitted
- **WHEN** 系统提交 Binance testnet 订单
- **THEN** 系统 MUST 记录 testnet order id
- **AND** 系统 MUST 记录 symbol、side、quantity、status 和时间

#### Scenario: Testnet fill is observed
- **WHEN** 系统查询到 Binance testnet trade 明细
- **THEN** 系统 MUST 记录 trade id、成交价、数量、手续费、手续费资产和成交时间
- **AND** 报告 MUST 说明 testnet 不代表实盘收益

### Requirement: Web must display paper trading status
系统 SHALL 在 Web 工作台展示测试网模拟盘状态。

#### Scenario: No paper run exists
- **WHEN** 用户打开 Web 工作台
- **AND** 没有 paper run
- **THEN** 系统 MUST 显示尚未运行和下一步
- **AND** 系统 MUST NOT 显示技术错误

#### Scenario: Paper run exists
- **WHEN** 用户打开 Web 工作台
- **AND** 存在 paper run
- **THEN** 系统 MUST 显示环境、状态、run id、更新时间和报告入口
- **AND** 环境 MUST 标记为 testnet

### Requirement: Web must display recent orders, fills, errors, and report
系统 SHALL 展示最近 paper run 的关键证据。

#### Scenario: Orders and fills exist
- **WHEN** paper run 有订单或成交
- **THEN** Web MUST 显示最近订单和成交摘要
- **AND** Web MUST 显示订单 ID / trade ID 的脱敏或完整测试网标识

#### Scenario: Errors exist
- **WHEN** paper run 有错误记录
- **THEN** Web MUST 显示错误类型、可读原因和发生时间

### Requirement: Web paper visibility must be read-only and redacted
系统 SHALL 保持 Web paper 状态展示只读和脱敏。

#### Scenario: Web API returns paper status
- **WHEN** Web API 返回 paper 状态
- **THEN** 响应 MUST NOT 包含 API Key 或 Secret 原文
- **AND** 响应 MUST NOT 提供 mainnet/live 切换

#### Scenario: User wants to start live trading from Web
- **WHEN** 用户在 v0.4.9 Web 工作台寻找实盘启动入口
- **THEN** 系统 MUST NOT 提供该入口
- **AND** 系统 SHOULD 说明当前只支持 testnet 状态查看
