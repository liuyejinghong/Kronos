# Kronos Agent MVP 资产盘点

更新时间：2026-04-29

## 结论

当前仓库不应推倒重来。

已有资产里，真正有价值的是一套确定性量化研究工具层：数据、因子、验证、walk-forward、回测、实验账本、知识库和中文报告。这些应成为 Agent 的工具箱。

需要收紧的是旧的产品口径：`research auto-run`、`kronos run today`、本地定时脚本和部分早期状态文档，都不能再代表 Agent MVP 主线。它们可以保留为工具或历史证据，但要从“产品核心”归档到“工具底座 / 历史参考”。

本轮归档方式是 **主线归档**：

- 不删除代码。
- 不移动已有文件。
- 不破坏测试和历史证据。
- 在文档中明确哪些资产不再作为 Agent MVP 主线入口。
- 后续如果要物理搬迁或删除，再单独做一次小范围清理变更。

## 资产分类

| 分类 | 资产 | 判断 | Agent MVP 用法 | 当前动作 |
|---|---|---|---|---|
| 直接复用 | `kronos/data/` | 已有 Binance USDM 拉取、Parquet 存储、查询、覆盖率和 gap 检查 | 作为 Agent 工具层的数据读取和数据新鲜度检查 | 保留 |
| 直接复用 | `kronos/factor/` | 已有因子协议、12 个 legacy 候选映射、验证、Alphalens adapter 和报告 | Agent 提出假设后调用这些确定性因子工具验证 | 保留 |
| 直接复用 | `kronos/research/backtest/` | 已有研究型回测、成本、资金费率、指标和 Freqtrade bridge | 作为 Agent tool executor 的回测工具候选 | 保留 |
| 直接复用 | `kronos/research/walkforward/` | 已有 nested split、轻量参数搜索和 lookahead audit | 作为 Agent 判断稳定性的确定性证据 | 保留 |
| 直接复用 | `kronos/research/experiments/` | 已有 run_id、artifact 目录、JSONL ledger、DuckDB 查询 | Agent run 应继续写入同一实验账本体系 | 保留 |
| 直接复用 | `kronos/research/knowledge_base/` | 已有 SQLite + FTS，并已支持 Agent plan / decision 写入 | 作为 Agent 记忆层，但后续要收紧写入规则 | 保留并扩展 |
| 直接复用 | `kronos/common/` | 已有配置、错误类型、共享类型和结构化日志入口 | Batch 1 的 Agent schema 和错误报告应沿用这些风格 | 保留 |
| 直接复用 | `tests/unit/`、`tests/integration/`、`tests/e2e/` | 覆盖数据、因子、研究、Agent CLI、Run MVP 和 E2E | 新 Agent 模块必须延续当前测试纪律 | 保留并新增 `tests/unit/agent/` |
| 包一层复用 | `kronos/research/agent_planner.py` | 已能从上一轮结果生成假设，并读取专项证据给出处置建议 | 作为早期 deterministic Agent planner 适配到新 `kronos/agent` runtime | 保留，但不作为最终 runtime 架构 |
| 包一层复用 | `cli/main.py` 中的 `agent propose` / `agent conclude` | 当前 CLI 已可用，但还是分散命令 | 后续由 Agent runtime 统一编排，再保留 CLI 作为手动入口 | 保留并逐步包进 runtime |
| 包一层复用 | `kronos/research/workbench.py` | PM 可读研究报告和候选处置已经成熟 | 作为 Agent tool executor 的一个确定性工具 | 保留 |
| 包一层复用 | `kronos/research/watchlist_evidence.py` | 能做观察名单专项证据复盘 | 作为 Agent 针对候选补证据的工具 | 保留 |
| 包一层复用 | `kronos/run_mvp.py` | 产品级运行状态页可用，但产品定位已变 | 作为 Agent 底层健康检查 / 一键工具，不再代表 MVP 主线 | 保留，降级为工具底座 |
| 延期保留 | `kronos/portfolio/` | 已有基础 allocator 和风险 review 串联 | 等候选通过验证后再接入，不进入 Batch 1-4 主线 | 延期 |
| 延期保留 | `kronos/risk/` | 已有基础 risk verdict 和通知钩子 | 等模拟盘 / 实盘申请阶段再接入 | 延期 |
| 延期保留 | `kronos/notify/` | 已有 notifier surface 和 Telegram 通道 | 后续做 Agent 事件通知或风险通知时复用 | 延期 |
| 延期保留 | `openspec/changes/p5-*`、`p6-*` | 执行、监控、治理和实盘上线规格过早 | 等 Agent 研究闭环和模拟盘成熟后再恢复 | 延期 |
| 主线归档 | `scripts/run_mvp_auto_research.sh` | 仍可作为手动/定时研究工具，但“定时运行”不是当前 MVP | 不作为 Agent MVP 启动方式 | 归档为工具底座 |
| 主线归档 | `scripts/launchd/com.kronos.auto-run.plist.example` | launchd 定时模板会强化错误产品口径 | 只保留为未来工具模板，当前不安装、不启用 | 归档为历史模板 |
| 主线归档 | `docs/MVP_ACCEPTANCE.md` | 只证明 Run MVP 工具入口，不代表 Agent MVP | 保留为工具底座验收历史 | 归档为历史验收 |
| 主线归档 | `docs/DEVELOPMENT_PLAN.md`、`docs/IMPLEMENTATION_STATUS.md` | 早期模块规划和状态页已被新总控文档覆盖 | 只作为历史规划参考 | 归档为历史文档 |
| 保留占位 | `kronos/ai/`、`kronos/api/`、`kronos/execution/`、`kronos/governance/` | 当前为空壳，没有可复用实现 | 暂不从这些包开始写 Agent MVP；按执行计划新增 `kronos/agent` | 保留为空壳，不作为主线 |
| 生成物清理候选 | `__pycache__/` | Python 运行生成物，`.gitignore` 已覆盖 | 不属于项目资产 | 后续可安全清理 |

## 下一步复用原则

1. Batch 1 从 `kronos/agent` 开始，不在 `kronos/research/agent_planner.py` 上继续堆 runtime。
2. `agent_planner.py` 当前能力要复用，但只能作为工具或适配层，不能替代 Agent runtime / event timeline / prompt version / role registry。
3. 所有确定性研究能力继续留在 `kronos/research/`、`kronos/factor/`、`kronos/data/`，不要为了 Agent MVP 复制一份。
4. `research auto-run` 和 `kronos run today` 保留为 Agent 可调用工具，不再作为产品入口宣传。
5. Web 和 supervisor 开发前，必须先完成 Batch 1 contracts / observability foundation。
6. 执行层、组合层、通知层不删除，但必须等候选通过验证和人工闸门后再进入主线。

## 当前真正不可作为主线的资产

| 资产 | 原因 | 处理 |
|---|---|---|
| 定时运行脚本和 launchd 模板 | 会把产品带回“每天重复跑报告”的错误方向 | 主线归档，未来仅作为工具模板 |
| Run MVP 验收口径 | 已被用户纠偏，Run MVP 不是 Agent MVP | 主线归档，保留历史证据 |
| 早期模块状态文档 | 容易和当前 Agent MVP 文档冲突 | 主线归档，读取时以新总控文档为准 |
| 空占位包 | 没有实现内容，不能当作复用资产 | 保留但不作为开发入口 |
| `__pycache__/` | 运行生成物 | 清理候选 |

## 开发准入影响

可以进入研发阶段，但第一步不是继续旧 `auto-run`，也不是直接做 Web。

下一步应按 `docs/AGENT_MVP_EXECUTION_PLAN.md` 执行：

1. Batch 1 已完成：`kronos/agent` 模块骨架、基础枚举、ID 类型、Agent run/task/event schema、角色/prompt/输出契约、事件写入器、PM 报告、机器摘要、错误报告和测试 fixture 已建立。
2. 下一步执行 Batch 2：Agent Supervisor skeleton。
3. Batch 2 仍应复用当前确定性研究工具，不把 `research auto-run` 或定时器重新拉回产品核心。

这能最大化复用旧研究资产，同时避免继续被旧 Run MVP / 定时器路线带偏。
