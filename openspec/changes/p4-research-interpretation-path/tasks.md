## 0. 规格收口

- [x] 0.1 确认 v0.4.5 版本需求文档与当前产品边界一致
- [x] 0.2 将 v0.4.5 目标回写到 `docs/PROJECT_STATUS.md`、`docs/ROADMAP.md` 和 `docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md`
- [x] 0.3 确认本变更不扩展到实盘执行、自动下单或多用户控制平面

## 1. 关键交易重放

- [x] 1.1 定义关键交易的筛选原则
- [x] 1.2 定义入场 / 出场 / 失败窗口的解释字段
- [x] 1.3 设计 `report latest` 后的独立重放入口
- [x] 1.4 补单元与集成测试覆盖关键交易解释

## 2. 市场状态分段评估

- [x] 2.1 复用现有 watchlist 分市场状态证据入口
- [x] 2.2 定义分段表现摘要和分段结论的 CLI 阅读入口
- [x] 2.3 定义分段结果在报告入口中的展示位置
- [x] 2.4 补分段评估入口测试

## 3. 只读观察边界

- [x] 3.1 定义只读观察的报告边界
- [x] 3.2 定义虚拟订单、延迟、滑点和人工闸门文案
- [x] 3.3 定义观察态与实盘态的文案隔离
- [x] 3.4 补观察态入口测试

## 4. 逐 symbol smoke-test

- [x] 4.1 定义每个 symbol 的独立 smoke-test 结果结构
- [x] 4.2 定义一个 symbol 失败时的阻断和展示行为
- [x] 4.3 定义多 symbol smoke-test 的 CLI 输出
- [x] 4.4 补多 symbol smoke-test 测试

## 5. 文档与验证

- [x] 5.1 同步 README / README.en / TODO / PROJECT_STATUS / ROADMAP / 产品设计文档
- [x] 5.2 运行针对性测试、ruff、mypy 和必要的集成验证
