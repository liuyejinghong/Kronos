## 0. 规格收口

- [x] 0.1 创建 v0.4.8 版本需求文档
- [x] 0.2 创建 OpenSpec proposal/design/spec/tasks
- [x] 0.3 同步 TODO、PROJECT_STATUS、ROADMAP、CHANGELOG 到 v0.4.8 边界

## 1. 凭证与环境边界

- [ ] 1.1 定义 Binance 测试网凭证存储和脱敏状态
- [ ] 1.2 定义 testnet endpoint allowlist，paper mode 拒绝 mainnet/live
- [ ] 1.3 定义 Docker 环境下凭证注入和缺凭证提示

## 2. Preflight

- [ ] 2.1 检查观察计划存在且符合测试网模拟盘准入
- [ ] 2.2 检查凭证、测试网连接、账户状态和风控限额
- [ ] 2.3 写出 preflight 报告和失败原因

## 3. 测试网模拟盘运行

- [ ] 3.1 新增 `kronos paper start/status/stop`
- [ ] 3.2 提交受限 Binance 测试网订单并记录 order id
- [ ] 3.3 查询测试网订单 / 成交状态并写入本地 ledger
- [ ] 3.4 停止后不再提交新订单

## 4. 报告与复盘

- [ ] 4.1 生成模拟盘 Markdown 报告和 JSON 摘要
- [ ] 4.2 报告明确 testnet 成交不等于实盘收益
- [ ] 4.3 `report latest` 或后续入口能指向模拟盘报告

## 5. 测试与验证

- [ ] 5.1 单元测试覆盖凭证脱敏、环境门禁、preflight、订单状态和停止状态
- [ ] 5.2 集成测试覆盖 `paper credentials/preflight/start/status/stop`
- [ ] 5.3 安全测试覆盖报告和日志不泄漏 API Key / Secret
- [ ] 5.4 Docker fresh 验证缺凭证提示和安全路径
- [ ] 5.5 完成 ruff、pytest、mypy、前端构建和 Docker 验证
