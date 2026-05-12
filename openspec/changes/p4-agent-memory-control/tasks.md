## 0. 规格收口

- [x] 0.1 创建 v0.4.10 版本需求文档
- [x] 0.2 创建 OpenSpec proposal/design/spec/tasks
- [x] 0.3 同步 TODO、PROJECT_STATUS、ROADMAP、PRODUCT_CONTROL_PANEL 到 v0.4.10 规划边界

## 1. 记忆读取与摘要模型

- [x] 1.1 定义当前状态、决策、教训、交接包和检查结果模型
- [x] 1.2 从 `MEMORY.md`、`DECISIONS.md`、`PROGRESS_LOG.md` 读取摘要
- [x] 1.3 从 `TODO.md`、`PROJECT_STATUS.md`、`ROADMAP.md` 读取版本和下一步
- [x] 1.4 所有摘要保留来源文件引用

## 2. 漂移与安全检查

- [x] 2.1 检查当前版本 / 下一版本字段是否一致
- [x] 2.2 检查 release docs 和 OpenSpec 是否被 TODO / ROADMAP / PROJECT_STATUS 索引
- [x] 2.3 检查记忆文件必备段落是否存在
- [x] 2.4 检查疑似 API Key / Secret / token 并脱敏输出

## 3. 交接包生成

- [x] 3.1 生成新 Agent 接手提示词
- [x] 3.2 交接包包含项目路径、必读文件、当前边界、当前待办和禁止事项
- [x] 3.3 交接包只引用来源文件，不复制大段正文或 secrets

## 4. Web API

- [x] 4.1 新增 Agent 记忆 summary API
- [x] 4.2 新增 decisions / lessons API
- [x] 4.3 新增 handoff API
- [x] 4.4 新增 drift check API

## 5. Web 工作台

- [x] 5.1 新增 Agent 记忆 / 交接控制台入口
- [x] 5.2 展示当前状态卡、决策与教训、交接包、一致性检查
- [x] 5.3 首屏展示当前版本、当前验收对象、最新成功运行 / 验收记录、来源文档和建议下一步
- [x] 5.4 桌面和窄屏可读，长路径不挤爆布局
- [x] 5.5 不展示工程噪音和 secrets

## 6. 测试与验证

- [x] 6.1 单元测试覆盖缺文件、版本冲突、索引缺失和必备段落缺失
- [x] 6.2 单元测试覆盖 secret-like 字符串脱敏
- [x] 6.3 集成测试覆盖 Web API
- [x] 6.4 前端 typecheck / lint / build 通过
- [x] 6.5 文档和 TODO / ROADMAP / PROJECT_STATUS 索引一致
