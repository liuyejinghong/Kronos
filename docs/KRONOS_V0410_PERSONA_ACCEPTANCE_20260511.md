# Kronos v0.4.10 多画像模拟用户验收记录

> 日期：2026-05-11
> 版本：0.4.10
> 验收对象：Agent 记忆与交接控制台
> 状态：通过，待产品 review

## 验收结论

v0.4.10 已把开发侧 Agent Harness 产品化为 Web 可验收能力。模拟用户打开 Web 工作台后，可以从侧边栏进入「记忆」，首屏看到当前版本、下一版本、当前验收对象、最新成功运行 / 验收记录、来源文档和建议下一步。

该版本保持只读优先，不自动覆盖 `MEMORY.md`、`DECISIONS.md` 或长期记忆文件；交接包和检查结果均来自仓库文件事实源，不依赖当前聊天上下文。

## 覆盖画像

| 画像 | 关注点 | 验收结果 |
|---|---|---|
| L1 交易研究者 | 新会话接手时先看哪里、当前版本做什么 | 通过：Web 侧边栏有「记忆」入口，首屏显示 v0.4.10 验收对象和下一步 |
| L2 项目负责人 | 决策、失败教训、交接包是否可 review | 通过：决策与教训独立展示，每条保留来源文件；交接包可复制 |
| L3 安全审查者 | 是否泄漏 secret，是否自动写长期记忆 | 通过：只读优先，疑似 secret 检查与脱敏覆盖；无自动写入入口 |
| L4 新 Agent / 新模型 | 是否能立即恢复上下文 | 通过：交接包包含项目路径、必读文件、当前边界、待办和安全禁令 |

## 产品路径

1. 启动本地 FastAPI 后端。
2. 启动 Web 工作台。
3. 打开首页，确认 v0.4.9 testnet paper 状态仍在今日页优先展示。
4. 点击侧边栏「记忆」。
5. 首屏确认：
   - 当前版本：`0.4.10`
   - 下一版本：`0.4.11`
   - 当前验收对象：Agent 记忆与交接控制台
   - 最新成功运行 / 验收记录：`20260509T134805Z-paper` 和 v0.4.9 多画像验收
   - 来源文档：`MEMORY.md`、`TODO.md`、`docs/PROJECT_STATUS.md`、`docs/ROADMAP.md`、`docs/PRODUCT_CONTROL_PANEL.md`
   - 建议下一步：产品 review 后规划 v0.4.11 失败记忆约束
6. 查看「最近决策与拒绝方案」和「经验教训」。
7. 查看并复制「一键交接包」。
8. 查看「记忆一致性检查」，确认通过 / 警告 / 阻塞计数和来源文件。

## 验收证据

- Web API：`GET /api/agent/memory/summary`
- Web API：`GET /api/agent/memory/handoff`
- Web API：`GET /api/agent/memory/check`
- Web 页面：侧边栏「记忆」
- 单元测试：`tests/unit/agent/test_memory_control.py`
- 集成测试：`tests/integration/web/test_routes.py::test_agent_memory_summary_route_returns_acceptance_first_state`

## 发现并修复的问题

| 问题 | 处理 |
|---|---|
| v0.4.10 首屏验收约束在文档里不够硬 | 已补入 release doc、OpenSpec spec/tasks、PROJECT_STATUS、ROADMAP 和 PRODUCT_CONTROL_PANEL |
| 窄屏下英文决策标题会撑宽卡片 | 已给记忆页标题、正文、路径和交接包补充换行约束 |
| 决策日志原始标题偏工程化 / 英文化 | 已在 memory reader 中给常见决策增加中文产品标题和摘要 |
| 系统 `uvicorn` 使用全局 Python 会遇到 pandas/pytz 环境问题 | 验收改用项目环境 `uv run python -m uvicorn ...` |

## 验证命令

```bash
uv run pytest tests/integration/web/test_routes.py tests/unit/agent/test_memory_control.py
uv run ruff check kronos/agent/memory_control kronos/web/routes/memory.py kronos/web/app.py tests/unit/agent/test_memory_control.py tests/integration/web/test_routes.py
uv run mypy kronos cli
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run build
python3 scripts/harness_memory_check.py
```

## 剩余风险

- v0.4.10 只做文件事实源的规则摘要和检查，不做 LLM 语义级记忆审计。
- 交接包只引用来源文件和短摘要，不复制长文档；新 Agent 仍必须按 `AGENTS.md` 的 boot protocol 读取事实源。
- 下一版建议进入 v0.4.11：把失败记忆约束接入 Agent 候选生成和研究决策，避免重复提出已失败方向。
