# Kronos 审查问题根因与修复方案（2026-05-06）

> 来源：`docs/reviews/KRONOS_CODE_PRODUCT_REVIEW_20260506.md`
> 目标：先解释根因，再给修复方案，并按本方案落地。本文不新增 v0.4.0 功能，只修复产品信任、交付边界和本地资产安全问题。

## 总体判断

这组问题的共同根因不是功能缺失，而是“产品状态没有统一事实源”。代码层面表现为用户本地资产和测试资产没有隔离、快速入口缺少稳定语义；产品层面表现为 README、TODO、项目状态、主设计文档同时描述不同版本的 Kronos。

修复原则：

1. 用户本地资产优先保护，测试不得默认读写真实 home 目录。
2. 产品文档只保留一个当前事实口径，把愿景和已交付能力分开。
3. 快速入口要符合用户理解，而不是只满足工程上“能找到一个文件”。
4. 当前版本继续停在研究报告和 Agent 复盘，不偷偷引入模拟盘或实盘边界。

## 问题 1：用户策略资产可能被测试流程误清空

**根因**

候选策略注册模块把真实持久化文件固定到 `~/.kronos/candidates.json`，并把测试需要的 `clear_candidates()` 做成会写入同一文件的全局函数。测试流程复用了真实产品存储，没有测试专用路径。

**修复方案**

- 增加候选注册路径解析函数，优先读取 `KRONOS_CANDIDATES_PATH`。
- 增加测试专用 fixture，把 `KRONOS_CANDIDATES_PATH` 指向 `tmp_path`。
- 增加回归测试：设置测试路径后，真实 home 下的候选文件不会被创建或改写。
- 保留默认生产路径 `~/.kronos/candidates.json`，不破坏 quickstart 到 agent start 的跨进程共享。

## 问题 2：项目控制面不可信

**根因**

发布流程同步了 `VERSION`、`CHANGELOG`、README 和 `TODO`，但没有把 `docs/PROJECT_STATUS.md` 当成发布门禁。该文档累积了多个阶段的历史状态，旧状态没有归档，导致“当前事实”和“历史证据”混在一起。

**修复方案**

- 重写 `docs/PROJECT_STATUS.md` 为 v0.3.3 当前状态。
- 明确当前能力、未交付能力、v0.4.0 前置修复和验证口径。
- 把历史 Agent MVP 批次保留为证据，不再作为当前最高优先级。

## 问题 3：主产品设计文档把未来能力写成当前能力

**根因**

`docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md` 同时承载了目标体验、当前能力和实现计划。v0.3.0 范围收缩后，只在文档后段追加了“AI 创建、历史重放后移”的说明，没有回收前段示例和能力矩阵。

**修复方案**

- 在文档顶部增加“当前能力边界”。
- 把自然语言策略创建、TOML 策略文件、历史重放、实时模拟盘全部标记为 v0.4.0 目标。
- 把前段用户路径示例改为“目标体验草案”，避免读者误以为已经交付。
- 更新能力矩阵，v0.3.3 只标记 R-breaker quickstart、研究报告、Agent 复盘和 report latest。

## 问题 4：v0.4.0 产品目标过期

**根因**

v0.3.3 已完成 R-breaker 首次判断闭环，但 `TODO.md` 下一版本目标仍停留在上一阶段。

**修复方案**

- 更新 `TODO.md` 的 v0.4.0 产品目标：从“判断 R-breaker”改为“创建/配置策略，并在模拟盘前看到可判定证据”。
- 保留 P2 待办，但重新命名为 v0.4.0 主线。

## 问题 5：“最新报告”可能展示被 touch 过的旧报告

**根因**

`kronos report latest` 用文件修改时间判断最新报告，没有优先读取 run summary 或 run id。文件被编辑器或脚本触碰后，旧报告可能被误判为最新。

**修复方案**

- 发现报告时读取同目录的 `agent_run_summary.json` 或 `auto_run_summary.json`。
- 优先用 summary 中的 `started_at` / `finished_at` / run id 时间判断最新。
- 只有没有结构化时间时才回退到文件 mtime。
- 增加单元测试：旧报告文件 mtime 更新后，仍按结构化运行时间选择真正最新 run。

## 问题 6：模型配置入口允许写入当前不支持的 provider

**根因**

provider 状态读取接口有 DeepSeek 白名单，secret 写入接口没有复用白名单；底层 secret store 被设计为通用存储，但产品层目前只支持 DeepSeek。

**修复方案**

- 抽出统一 provider 解析函数。
- status 和 secret 写入都拒绝非 DeepSeek provider。
- 增加 Web route 测试：未知 provider 写入返回 404，且不会写入 secret 文件。

## 问题 7：Agent 工具输入缺少统一校验

**根因**

工具定义包含 `input_schema`，但 executor 没有执行它。当前靠各工具 handler 自己报错，错误信息会分散且不适合自然语言策略创建后的用户解释。

**修复方案**

- 在 `AgentToolExecutor.execute()` 进入 handler 前校验 required 字段。
- 校验失败时返回失败记录，错误码区分为 tool input invalid，不调用 handler。
- 增加单元测试：缺少 required 字段时不会执行 handler，并写入可解释错误。

## 问题 8：Agent 环境检查过于沉默

**根因**

Agent console 为了首次使用体验吞掉了数据读取和 secret store 异常，导致“缺失”和“损坏”无法区分。

**修复方案**

- 保持用户界面不被 traceback 打断。
- 对环境扫描异常记录 warning 日志。
- 为未来 UI 提供诊断依据，不改变当前对话主流程。

## 问题 9：版本展示轻微不一致

**根因**

README badge 采用 minor 级版本，其他 release 元数据采用 patch 级版本。

**修复方案**

- README 中英文 badge 同步为 `0.3.3`。
- 后续 release checklist 要同步 README badge、VERSION、pyproject、CHANGELOG、TODO 和 PROJECT_STATUS。

## 验证计划

1. `uv run pytest tests/unit/factor/test_candidates.py tests/unit/test_reports_latest.py tests/unit/agent/test_tools.py tests/integration/web/test_routes.py -q`
2. `uv run ruff check .`
3. `uv run mypy kronos cli`
4. `git diff --check`

如果全量非 e2e 测试耗时可接受，再运行 `uv run pytest -m "not e2e"`。
