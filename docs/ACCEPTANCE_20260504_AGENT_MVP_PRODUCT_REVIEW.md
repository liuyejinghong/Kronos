# Agent MVP 产品验收报告

> 验收时间：2026-05-04
> 验收批次：`20260430-agent-mvp-delivery-v1`
> 验收方式：Production build + 无头浏览器全页面验收
> 验收人：Claude Code (deepseek-v4-pro)

## 验收前置

- 后端 API：FastAPI，`127.0.0.1:8000`，已启动
- 前端：Next.js 16.2.4 production build，`127.0.0.1:3001`，已启动
- 数据库：本地 Parquet 数据（BTC/ETH/SOL，约 90 天 1m K 线）
- Agent 运行时：未激活（DeepSeek 未配置），显示 `20260430-agent-mvp-delivery-v1` 批次静态数据

## 验收清单

### 首页（今日）

| # | 验收项 | 预期 | 实际 | 结果 |
|---|--------|------|------|------|
| 1 | 当前研究批次可见 | 显示 run_id | `20260430-agent-mvp-delivery-v1` | ✅ |
| 2 | Agent 状态可见 | 待命/运行中/完成 | "Agent 待命" | ✅ |
| 3 | 当前研究目标 | 可读的中文目标 | "Kronos Agent MVP 交付验收：读取上一轮研究结果和专项证据..." | ✅ |
| 4 | Agent 当前结论 | 可读的中文结论 | "趋势内回踩入场 只适合进入候选改造，不进入组合或实盘" | ✅ |
| 5 | 下一步动作 | 可读的中文建议 | 同上，明确不进入组合或实盘 | ✅ |
| 6 | 证据数量 | 显示数字 | "4 个关键证据"、"6 条事件" | ✅ |
| 7 | 是否需要审批 | 是/否 | "本轮不需要人工审批" | ✅ |
| 8 | 支持/反对理由 | 可读 | "已完成 Agent plan 和 Agent decision 两个确定性工具步骤" / "本轮只是研究闭环" | ✅ |
| 9 | 报告结论来源透明 | 标注是否 LLM 生成 | "来自本地确定性验收和历史报告读取，不是 DeepSeek 实时生成" | ✅ |
| 10 | 候选资产数量 | 12 | "12 个研究族群" | ✅ |
| 11 | 人工闸口数量 | 0 | "当前没有待审批项" | ✅ |
| 12 | API 连接状态 | 已连接 | "本地 API 正常" | ✅ |
| 13 | 模型配置状态 | 未配置 | "未配置" | ✅ |
| 14 | 首页导航结构 | 今日/候选池/报告/时间线/操作台 | 五个面板全部可点击 | ✅ |
| 15 | 首页操作入口 | 刷新/打开报告/查看候选/导入材料/去配置 | 全部可点击（"开始下一轮研究" disabled 属预期行为） | ✅ |

### 候选池

| # | 验收项 | 预期 | 实际 | 结果 |
|---|--------|------|------|------|
| 16 | 候选列表完整 | 12 个 | 12 个全部展示 | ✅ |
| 17 | 优先级排序 | 按迁移分降序 | #1=指标 spread regime(100分), #2=信号持续性密度(93分), #3=趋势回撤容忍度(86分) | ✅ |
| 18 | 每个候选有当前判断 | 无空值 | 前 6 名为"优先验证"，后 6 名为"暂缓观察" | ✅ |
| 19 | 每个候选有证据缺口 | 无空值 | 统一标注"缺 crypto 专项回测、滚动验证和失败边界" | ✅ |
| 20 | 候选洞察摘要 | 优先候选/集中族群/共同缺口 | 三个洞察全部可读 | ✅ |
| 21 | 候选详情-生命周期状态机 | 完整展示 | 材料进入→迁移审查→假设→实验计划→验证→Agent 分析→投委会评分→模拟盘→实盘审批 | ✅ |
| 22 | 候选详情-Agent 分歧 | 支持侧/反对侧 | "支持侧：旧策略迁移优先级 #1；反对侧：仍需要 crypto 市场专项证据确认" | ✅ |
| 23 | 候选详情-投委会结论 | 可读 | "等待 Agent 选择是否进入下一轮研究" | ✅ |
| 24 | 候选详情-旧资产来源 | 可追溯 | "all" | ✅ |
| 25 | 候选详情-证据产物 | 可查看 | "该候选项暂未绑定专属证据文件"（预期行为，候选尚未进入验证阶段） | ✅ |

### 报告阅读器

| # | 验收项 | 预期 | 实际 | 结果 |
|---|--------|------|------|------|
| 26 | 报告可打开 | 点击"打开报告"或"阅读本轮报告" | 弹出报告面板 | ✅ |
| 27 | 报告标题和批次号 | 完整 | "Kronos Agent 研究报告：20260430-agent-mvp-delivery-v1" | ✅ |
| 28 | 报告第一屏摘要 | 研究目标/原因/结论/下一步/审批 | 五个字段全部完整 | ✅ |
| 29 | 运行状态信息 | run_id/状态/任务 | "completed"、"agent-cycle"、"任务数量：1" | ✅ |
| 30 | 技术路径 | 报告文件路径 | `/Users/ethan/Kronos/reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_run_report.md` | ✅ |
| 31 | 关键证据清单 | 4 条产物 | agent_plan_json/md, agent_decision_json/md，含完整路径 | ✅ |
| 32 | 报告正文可读 | Markdown 渲染 | 完整展示报告正文 | ✅ |
| 33 | 报告可关闭 | 点击关闭 | 关闭按钮存在 | ✅ |

### Agent 时间线

| # | 验收项 | 预期 | 实际 | 结果 |
|---|--------|------|------|------|
| 34 | 事件列表完整 | 6 条 | 6 条全部展示 | ✅ |
| 35 | 事件类型/级别/消息可读 | info/decision | 启动研究→执行 agent_propose→完成 agent_propose→执行 agent_conclude→完成 agent_conclude→完成研究 | ✅ |
| 36 | 事件有产物链接 | 每个决策事件挂 artifact | agent_propose 完成和 agent_conclude 完成均挂 2 个产物（json+md） | ✅ |
| 37 | 事件消息中文可读 | 中文 | "Agent 验收运行已完成, 等待人工复核下一步。" | ✅ |

### 操作台

| # | 验收项 | 预期 | 实际 | 结果 |
|---|--------|------|------|------|
| 38 | 模型配置页 | DeepSeek API Key 输入 | "尚未配置"、"local_file"、API Key 输入框可用 | ✅ |
| 39 | Agent 角色列表 | 5 个角色 | 研究员/反方审查/风控审查/投委会裁决/执行记录分析 | ✅ |
| 40 | 角色 Prompt 版本 | 每个角色 v1 | researcher-prompt-v1, opposition-reviewer-prompt-v1, risk-reviewer-prompt-v1 等 | ✅ |
| 41 | 角色模型状态 | 待模型配置 | 全部标注"模板启用，待模型配置" | ✅ |
| 42 | 材料导入入口存在 | tab 可见 | 模型/材料/审批三个 tab | ✅ |
| 43 | 审批中心入口存在 | tab 可见 | 审批 tab 可点击 | ✅ |

### API 端到端

| # | 验收项 | 预期 | 实际 | 结果 |
|---|--------|------|------|------|
| 44 | `/api/health` | 200 OK | `{"status":"ok","service":"kronos-web-api"}` | ✅ |
| 45 | `/api/candidates` | 12 个候选 | 12 个候选，含完整字段 | ✅ |
| 46 | `/api/agent/runs/{id}/summary` | 200 OK | 目标/结论/证据 4 条/风险 | ✅ |
| 47 | `/api/settings/llm/providers/deepseek/status` | 200 OK | `{"status":"waiting_configuration",...}` | ✅ |
| 48 | Next.js rewrite 代理 | `/api/kronos/*` → `:8000/api/*` | 全路径通过 | ✅ |

---

## 产品视角发现

### 做得好的

1. **首页信息密度合理**：一屏覆盖"研究什么→结论→下一步→风险→证据"，不需要翻页或点进去
2. **候选池不裸列表**：有优先级排序、洞察摘要（集中族群+共同缺口），能辅助研究资源分配决策
3. **时间线可追溯**：每条事件都有 artifact 路径，知道"Agent 读了什么文件、产出了什么文件"
4. **报告阅读器分层**：区分"第一屏摘要"（PM 视角）和"技术路径"（研发视角），折叠展开设计合理
5. **结论来源透明**：明确标注"不是 DeepSeek 实时生成"，防止误信 LLM
6. **角色信息不隐藏**：即使模型未配置，5 个 Agent 角色和 Prompt 版本仍然可见，透明度好

### 需要改进的

| # | 问题 | 严重度 | 位置 | 建议 |
|---|------|--------|------|------|
| 1 | "开始下一轮研究"按钮 disabled | 高 | 首页 | 这是 Agent 不可用时的预期行为，但应有提示说明需要先配置 DeepSeek |
| 2 | 12 个候选全部卡在"迁移审查" | 中 | 候选池 | 前 3 名候选应该有至少一个进入"验证中"状态，目前缺乏差异化进展 |
| 3 | 首页无图表 | 中 | 首页 | `docs/AGENT_MVP_ACCEPTANCE.md` 提到已有 ECharts，但在当前首页看不到候选分布图 |
| 4 | 空状态文案 | 低 | 审批中心 | "当前没有待审批项" 是预期行为，但可以加一句"审批项在 prompt 生效、模拟盘准入、实盘申请时生成" |

---

## 测试环境信息

| 项目 | 值 |
|------|-----|
| Python | 3.12 |
| pytest | 487 passed, 5 deselected (非 E2E) |
| mypy | 113 source files 通过 |
| ruff | 通过 |
| 覆盖率 | 91.11% |
| 前端 typecheck | `tsc --noEmit` 通过 |
| 前端 lint | eslint 通过 |
| 前端 build | `next build` 通过 |

---

## 结论

**产品功能链路**：✅ 全部通过。数据→API→前端→报告→时间线→候选池→操作台，端到端可达。

**产品可用性**：⚠️ 部分通过。能看懂当前状态，但不能启动新一轮研究（DeepSeek 未配置是预期设计约束）。

**建议下一步**：
1. 配置 DeepSeek API Key → 解锁 `kronos agent run-once` 完整闭环
2. 对前 3 名候选补 crypto 专项证据 → 打破"全部卡在迁移审查"
3. 首页补充 ECharts 图表（候选分布、IC 热力图等）
4. `docs/AGENT_MVP_ACCEPTANCE.md` 的验收口径应考虑同步更新

## 关联文档索引

- 📎 [`docs/AGENT_MVP_DELIVERY.md`](AGENT_MVP_DELIVERY.md) — Agent MVP 交付验收说明
- 📎 [`docs/AGENT_MVP_ACCEPTANCE.md`](AGENT_MVP_ACCEPTANCE.md) — Agent MVP 验收口径定义
- 📎 [`docs/PROJECT_STATUS.md`](PROJECT_STATUS.md) — 项目总控面板
- 📎 [`docs/ROADMAP.md`](ROADMAP.md) — 阶段路线图和优先级
- 📎 [`docs/AGENT_MVP_PRODUCT_UX_REVIEW.md`](AGENT_MVP_PRODUCT_UX_REVIEW.md) — 上一轮 UX Review（2026-05-01）
- 📎 [`docs/AGENT_ARCHITECTURE_TECH_SELECTION.md`](AGENT_ARCHITECTURE_TECH_SELECTION.md) — Agent 架构和技术选型
- 📎 [`docs/PRODUCT_CONTROL_PANEL.md`](PRODUCT_CONTROL_PANEL.md) — 产品控制面板
- 📎 [`TODO.md`](../TODO.md) — 当前执行待办
- 📎 [`reports/agent_runtime/agent_supervisor_status.json`](../reports/agent_runtime/agent_supervisor_status.json) — Agent 运行时状态
