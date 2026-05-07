## 0. 规格收口

- [x] 0.1 确认 v0.4.3 版本需求文档与 OpenSpec change 的边界一致
- [x] 0.2 将 `docs/ROADMAP.md`、`docs/PROJECT_STATUS.md`、`TODO.md` 同步到 v0.4.3 规划口径
- [x] 0.3 确认本变更不扩展到历史重放、模拟盘或实盘执行

## 1. 策略起草契约

- [x] 1.1 定义自然语言输入、策略概要和草案的结构化契约
- [x] 1.2 定义模板匹配、澄清问题和拒绝语义
- [x] 1.3 定义草案与现有 `StrategyConfig` 的兼容约束

## 2. 用户入口

- [x] 2.1 设计 `kronos strategy draft` 命令行为
- [x] 2.2 设计 `kronos agent start` 中“我有一个策略想法”的分支
- [x] 2.3 设计 Docker 下路径和下一步命令的产品化输出

## 3. 验证与产物

- [x] 3.1 草案必须能进入 `validate`
- [x] 3.2 草案必须能继续进入 `smoke-test`
- [x] 3.3 草案注册后必须能被 Agent/Web 读到

## 4. 测试与收口

- [x] 4.1 补单元测试覆盖输入结构化、模板命中、拒绝和澄清
- [x] 4.2 补 CLI / integration 测试覆盖 draft / validate / smoke-test / register
- [x] 4.3 补 Docker 复测，确保路径和下一步命令可复制
- [x] 4.4 在实现完成后同步 CHANGELOG、VERSION、TODO 和 PROJECT_STATUS
