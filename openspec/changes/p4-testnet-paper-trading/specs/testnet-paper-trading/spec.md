## ADDED Requirements

### Requirement: Paper trading must use Binance testnet only
系统 SHALL 只允许 `paper` 命令连接 Binance 模拟盘 / 测试网，不得连接主网或实盘端点。

#### Scenario: User starts paper trading
- **WHEN** 用户运行 `kronos paper start`
- **THEN** 系统 MUST 使用 Binance testnet endpoint
- **AND** 系统 MUST 在输出和报告中标记 `testnet`
- **AND** 系统 MUST NOT 使用 mainnet endpoint

#### Scenario: Mainnet config is provided
- **WHEN** 用户或配置尝试把 paper mode 指向 mainnet/live
- **THEN** 系统 MUST 拒绝启动
- **AND** 系统 MUST 提示 v0.4.8 只支持测试网模拟盘

### Requirement: Testnet credentials must be local and redacted
系统 SHALL 本地保存 Binance 测试网 API Key 和 Secret，并在所有用户可见输出中脱敏。

#### Scenario: Credentials are configured
- **WHEN** 用户运行 `kronos paper credentials status`
- **THEN** 系统 MUST 只显示 configured 状态和脱敏尾号
- **AND** 系统 MUST NOT 输出原始 API Key 或 Secret

#### Scenario: Credentials are missing
- **WHEN** 用户运行 `kronos paper preflight`
- **THEN** 系统 MUST 失败
- **AND** 系统 MUST 给出配置测试网凭证的下一步

### Requirement: Preflight must gate every paper run
系统 SHALL 在任何测试网订单提交前通过 preflight。

#### Scenario: Observation plan is not eligible
- **WHEN** 观察计划来自 sample、短样本、证据不足或未通过策略
- **THEN** 系统 MUST 拒绝启动模拟盘
- **AND** 系统 MUST 解释不能启动的产品原因

#### Scenario: Preflight passes
- **WHEN** 凭证、测试网连接、观察计划和风控限额都通过
- **THEN** 系统 MAY 允许 `paper start`
- **AND** 系统 MUST 写出 preflight 报告

### Requirement: Orders and fills must come from testnet responses
系统 SHALL 只把 Binance 测试网返回的订单和成交记录称为测试网订单 / 成交。

#### Scenario: Testnet order is submitted
- **WHEN** 策略信号触发测试网下单
- **THEN** 系统 MUST 记录 Binance testnet order id
- **AND** 系统 MUST 记录请求、响应、状态和环境

#### Scenario: Fill is observed
- **WHEN** 系统查询到测试网成交
- **THEN** 系统 MUST 记录成交价、数量、手续费和成交时间
- **AND** 系统 MUST 标记成交来源为 testnet

### Requirement: Paper run must be bounded and stoppable
系统 SHALL 限制 v0.4.8 模拟盘运行范围，并支持停止。

#### Scenario: User stops paper trading
- **WHEN** 用户运行 `kronos paper stop`
- **THEN** 系统 MUST 写入停止状态
- **AND** 运行循环 MUST NOT 再提交新订单

#### Scenario: Paper run ends
- **WHEN** 模拟盘运行结束或被停止
- **THEN** 系统 MUST 生成用户可读报告
- **AND** 报告 MUST 区分信号、订单、成交、失败和停止

### Requirement: Testnet results must not auto-upgrade to live
系统 SHALL 保留实盘人工闸门，不得因为测试网表现自动进入实盘。

#### Scenario: Testnet run is profitable
- **WHEN** 模拟盘报告显示测试网盈利
- **THEN** 系统 MUST NOT 自动创建 live order
- **AND** 系统 MUST 提示这只是测试网结果，需要人工评审
