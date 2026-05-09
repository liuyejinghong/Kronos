## 0. 规格收口

- [x] 0.1 创建 v0.4.7 版本需求文档
- [x] 0.2 创建 OpenSpec proposal/design/spec/tasks
- [x] 0.3 同步 TODO、PROJECT_STATUS、ROADMAP 到 v0.4.7 边界

## 1. 观察计划契约

- [x] 1.1 定义只读观察计划的数据来源和输出结构
- [x] 1.2 定义 sample / 短样本 / 未通过 / 已通过 的准入判断
- [x] 1.3 定义虚拟订单、延迟、滑点和人工闸门默认假设

## 2. 用户入口

- [x] 2.1 新增 `kronos report observation-plan`
- [x] 2.2 支持指定报告路径和默认最新报告
- [x] 2.3 无报告时输出产品化下一步提示

## 3. 产物

- [x] 3.1 写出 `paper_observation_plan.md`
- [x] 3.2 输出来源报告和计划路径
- [x] 3.3 报告正文明确不启动模拟盘或真实订单

## 4. 测试与收口

- [x] 4.1 单元测试覆盖观察计划生成和准入判断
- [x] 4.2 集成测试覆盖 CLI 成功/失败路径
- [x] 4.3 同步 CHANGELOG、VERSION、README
- [x] 4.4 完成 ruff、pytest、mypy、前端构建和 Docker 验证
