# Kronos 主线归档索引

更新时间：2026-04-29

## 用途

这份索引记录“不再作为当前 Agent MVP 主线”的资产。

归档不等于删除。当前采用主线归档：

- 文件仍保留在原路径，避免破坏历史证据和测试。
- 后续 Agent 执行时，以这里的归档状态判断是否可继续沿用。
- 如果未来需要物理搬迁或删除，再单独开清理任务。

## 已归档出当前主线

| 资产 | 当前归档状态 | 原因 | 未来可用性 |
|---|---|---|---|
| `scripts/run_mvp_auto_research.sh` | 工具底座归档 | 代表 one-shot / scheduler 研究循环，不是 Agent MVP 产品入口 | Agent 有明确监控或重复验证需求时，可作为工具模板复用 |
| `scripts/launchd/com.kronos.auto-run.plist.example` | 历史模板归档 | 当前不安装定时器；每天重复跑同一批结论没有产品价值 | 后续有真实定时需求时重新评审 |
| `docs/MVP_ACCEPTANCE.md` | 历史验收归档 | 只证明 Run MVP 工具入口，不证明 Agent MVP | 保留为工具底座验收记录 |
| `docs/DEVELOPMENT_PLAN.md` | 历史规划归档 | 已被 `PROJECT_STATUS`、`ROADMAP`、Agent MVP 开发规划和执行计划覆盖 | 查历史模块规划时可读，不作为当前执行真源 |
| `docs/IMPLEMENTATION_STATUS.md` | 历史状态归档 | 状态口径已迁移到 `PROJECT_STATUS.md` 和 `TODO.md` | 查历史实现记录时可读 |
| `kronos/ai/` | 空占位归档 | 当前没有实现，不作为 Agent MVP 开发入口 | 后续如有 AI provider 层需求，重新设计后使用 |
| `kronos/api/` | 空占位归档 | 当前没有实现，Web 后端应按 FastAPI schema 重新设计 | 后续 Web backend 批次评估 |
| `kronos/execution/` | 空占位归档 | 当前不推进实盘执行 | 等模拟盘 / 实盘审批阶段恢复 |
| `kronos/governance/` | 空占位归档 | 当前 governance 先由 OpenSpec 和文档约束 | 等 Agent 审批、实盘准入和审计需求成熟后恢复 |
| `__pycache__/` | 生成物清理候选 | Python 运行生成物，不属于产品资产 | 可在独立清理任务中删除 |

## 仍在主线内的复用资产

这些不应归档：

- `kronos/data/`
- `kronos/factor/`
- `kronos/research/backtest/`
- `kronos/research/walkforward/`
- `kronos/research/experiments/`
- `kronos/research/knowledge_base/`
- `kronos/research/workbench.py`
- `kronos/research/watchlist_evidence.py`
- `kronos/research/agent_planner.py`
- `cli/main.py`
- `tests/`

详细复用方式见 `docs/AGENT_MVP_ASSET_INVENTORY.md`。
