## 0. 规格收口

- [x] 0.1 创建 v0.4.9 版本需求文档
- [x] 0.2 创建 OpenSpec proposal/design/spec/tasks
- [x] 0.3 同步 TODO、PROJECT_STATUS、ROADMAP、PRODUCT_CONTROL_PANEL 到 v0.4.9 开发边界

## 1. 真实 testnet E2E 验收

- [x] 1.1 配置 Binance testnet 凭证并确认脱敏状态
- [x] 1.2 使用真实数据产出 promoted > 0 的观察候选；初始无候选阻塞已保留，后续 `signal_persistence_density` 横截面候选通过
- [x] 1.3 从合格候选生成观察计划并通过 preflight
- [x] 1.4 在用户明确授权下提交最小 testnet 订单
- [x] 1.5 保存 order id、trade 明细、成交时间、手续费、状态 JSON 和 Markdown 报告
- [x] 1.6 补交易所 `MIN_NOTIONAL` 前置检查，避免低于最小名义金额时只暴露 Binance HTTP 400

## 2. Paper 状态读取

- [x] 2.1 定义 paper status API response 模型
- [x] 2.2 读取 `reports/paper/current_status.json`
- [x] 2.3 读取最近 run 的 orders/fills/errors/report
- [x] 2.4 缺文件、无 run、失败 run、停止 run 都返回产品化状态

## 3. Web API

- [x] 3.1 新增 `GET /api/paper/status`
- [x] 3.2 新增 `GET /api/paper/runs/{run_id}/report`
- [x] 3.3 确认 API 不返回 API Key / Secret
- [x] 3.4 API 测试覆盖空状态、失败状态和有 run 状态

## 4. Web 工作台

- [x] 4.1 新增测试网模拟盘状态面板或页面入口
- [x] 4.2 展示 environment、status、run id、更新时间和下一步
- [x] 4.3 展示最近订单、成交、错误和报告入口
- [x] 4.4 桌面和窄屏可读，长路径折叠
- [x] 4.5 明确 testnet 不等于实盘收益

## 5. 测试与验证

- [x] 5.1 单元测试覆盖状态读取和缺文件路径
- [x] 5.2 集成测试覆盖 Web paper API
- [x] 5.3 前端 typecheck / lint / build 通过
- [x] 5.4 手工或浏览器验证 Web 状态面板
- [x] 5.5 文档和 TODO / ROADMAP / PROJECT_STATUS 索引一致
- [x] 5.6 真实 Binance testnet 验收记录已落档：`docs/TESTNET_E2E_ACCEPTANCE_20260509.md`
- [x] 5.7 多画像模拟用户验收已落档：`docs/KRONOS_V049_PERSONA_ACCEPTANCE_20260511.md`
