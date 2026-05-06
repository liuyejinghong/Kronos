# Kronos 代码与产品方向审查报告（2026-05-06）

> 审查对象：当前 `main` 分支 v0.3.3 后的代码、README/TODO/产品设计文档和最近评测文档。
> 审查目的：只给出结论、证据、根因和建议判定，不直接修复。后续由项目 owner review 后决定是否修复、降级或判定为接受风险。

## 结论先行

本轮没有发现新的远程代码执行、SQL 注入或路径穿越级别 CRITICAL。v0.3.3 的主路径已经比 v0.3.1 明显收敛：`quickstart`、`report latest`、交易语言解释、数据同步说明和模拟盘边界都已进入产品链路。

但项目当前不适合直接进入 v0.4.0 功能堆叠。主要原因不是单点代码 bug，而是产品控制面和本地状态边界出现分叉：控制文档仍在讲 v0.2.0/v0.3.0，主设计文档又同时把 AI 策略创建、历史重放标成当前能力和未来能力；同时候选策略注册测试会直接写入真实 `~/.kronos/candidates.json`，这会伤到本地优先产品最重要的用户资产边界。

建议先判定并修复 P0-1 到 P0-3，再进入 v0.4.0 的 AI 策略创建、模拟盘、历史重放等新增能力。

## 审查方法

- 对照 `TODO.md`、`CHANGELOG.md`、README、`docs/PROJECT_STATUS.md`、`docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md` 和最近 Docker/交易者评测。
- 静态审查核心路径：CLI、报告 latest、候选注册、Agent console、Agent tools、Web settings、Binance loader。
- 未运行全量测试：本轮发现测试会触达真实候选注册文件，继续跑测试可能改写本机真实 `~/.kronos/candidates.json`。在修复该隔离问题前，测试本身不再是无副作用验证动作。

## P0-1：候选策略测试会清空真实用户候选池

**严重度**：P0 / High

**证据**

- `kronos/factor/candidates.py:16` 将候选注册持久化路径硬编码到 `Path.home() / ".kronos" / "candidates.json"`。
- `kronos/factor/candidates.py:106-110` 的 `clear_candidates()` 会把内存 registry 清空并 `_save_to_disk([])`。
- `tests/unit/factor/test_candidates.py:24-30` 在每个测试 setup/teardown 都调用 `clear_candidates()`。
- `tests/integration/test_cli.py:26-40` 的 `_register_test_candidates()` 先 `clear_candidates()` 再注册测试候选；`tests/integration/test_cli.py:319-323` 的 promotion CLI 测试 setup/teardown 会触发它。
- `tests/integration/web/test_routes.py:52-77` 也直接 `clear_candidates()` / `register_candidate()`。

**直接结果**

开发者或 CI 在真实工作目录运行 `uv run pytest -m "not e2e"` 时，有可能清空或覆盖本机真实 `~/.kronos/candidates.json`。对 Kronos 这种本地优先产品来说，候选池就是用户策略资产；测试不应触达它。

**根因**

候选注册模块把“产品持久化路径”和“测试 registry 后端”绑定在模块级全局常量上，且缺少路径注入、环境变量覆盖或测试 fixture 隔离。`clear_candidates()` 的 docstring 写着“useful for testing”，但实现没有测试隔离边界。

**建议判定**

阻断 v0.4.0 新功能。先把候选注册持久化路径改为可注入，例如 `KRONOS_CANDIDATES_PATH`、配置项或 `CandidateRegistryStore(path=...)`；测试必须使用 `tmp_path`，并增加一条回归测试证明默认 `Path.home()` 文件不会被测试修改。

## P0-2：项目控制面文档严重滞后，已经误导下一步路线

**严重度**：P0 / Product

**证据**

- `docs/PROJECT_STATUS.md:3` 仍写 `版本：0.2.0`，但当前 `TODO.md:3`、`CHANGELOG.md:8`、`VERSION`/`pyproject.toml` 已是 v0.3.3。
- `docs/PROJECT_STATUS.md:7-11` 仍以 v0.2.0/v0.3.0 为当前口径。
- `docs/PROJECT_STATUS.md:39-40` 同一张表里一边说 Agent MVP Batch 8 已完成，一边说首次使用闭环仍“外部交易者试用未通过、没有内置可运行示例策略”。
- `docs/PROJECT_STATUS.md:111` 又说 Agent 研究闭环 Batch 7 已完成，和上方 Batch 8 交付状态冲突。
- `docs/PROJECT_STATUS.md:142-148` 的最高优先级仍是 v0.3.1/v0.3.2 前的首次使用闭环、Docker 资产、Web 空状态等事项，但 `TODO.md:58-67` 已标注 v0.3.3 收口完成。

**直接结果**

项目是产品驱动的，控制面文档会决定下一轮 agent 或开发者优先级。现在它会把人拉回已经完成的 P0，同时掩盖真正应该判定的 v0.4.0 前置风险。

**根因**

版本发布流程只同步了 `VERSION`、`CHANGELOG`、`README`、`TODO`，没有把 `docs/PROJECT_STATUS.md` 作为 release gate。控制台文档从 Agent MVP 交付期累积而来，缺少“当前事实 / 历史证据 / 下一步判定”三层拆分。

**建议判定**

阻断 v0.4.0 功能规划。先把 `PROJECT_STATUS.md` 重写成 v0.3.3 当前事实，并明确：已完成、未完成、下一步需 owner 判定的问题。之后把它加入版本发布 checklist。

## P0-3：主产品设计文档把未来能力写成当前能力

**严重度**：P0 / Product

**证据**

- `docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md:294-302` 的“版本当前能力”表把 v0.3.0 的“定义策略”写成 `R-breaker + AI 自然语言创建`，并把“历史重放”标为已具备。
- 同一文档 `docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md:465-484` 又把 AI 自然语言创建、历史重放、实时模拟盘后移到 v0.4.0。
- `TODO.md:93-101` 也把 AI 自然语言策略创建、实时模拟盘、历史重放、市场状态分段、TOML 策略配置列为 v0.4.0 预留。
- README 当前边界是正确的：`README.md:56` 明确当前版本只产出研究报告和 Agent 复盘，不会启动模拟盘或真实下单。

**直接结果**

新接手开发者按主设计文档执行，会误以为 AI 创建和历史重放已经是 v0.3.x 当前能力，只需要打磨；用户按设计文档理解，会把未交付能力当作承诺。产品信任会被版本口径消耗。

**根因**

主设计文档同时承载“目标体验脚本”“当前能力矩阵”“版本计划”，但没有清晰标记哪些是 vision，哪些是 shipped，哪些是 deferred。后续补丁在文档末尾追加了正确边界，但没有回收前文旧表。

**建议判定**

阻断 v0.4.0 需求拆解。先将该文档拆成两层：v0.3.3 已交付能力和 v0.4.0 目标体验。AI 创建、历史重放、实时模拟盘只能出现在目标/待办区域，不能出现在“当前能力”区域。

## P1-1：`report latest` 的“最新”语义依赖文件 mtime

**严重度**：P1 / Medium

**证据**

- `kronos/reporting/latest.py:43-58` 遍历 `reports/research/experiments/*/{REPORT_FILENAMES}` 后用 `(stat.st_mtime, path)` 取最大值。
- `LatestReport` 不读取 run_id、summary JSON、实验账本或报告内部时间。

**直接结果**

如果用户、编辑器或脚本触碰了旧报告文件，`kronos report latest` 可能展示被 touch 过的旧 run，而不是真正最新研究 run。这会直接影响“用户不用 ls 目录”的产品承诺。

**根因**

v0.3.3 为快速补上入口，选择了无状态文件扫描方案，但项目已经有 run_id、summary JSON、ledger 等更稳定的时间来源，没有建立报告索引或 manifest。

**建议判定**

可接受为 v0.3.3 临时方案，但 v0.4.0 前应改成优先读取 `agent_run_summary.json` / `auto_run_summary.json` / run_id 时间戳，再 fallback 到 mtime。

## P1-2：Web LLM secret 写入接口没有复用 provider 白名单

**严重度**：P1 / Medium

**证据**

- `kronos/web/routes/settings.py:65-69` 的 provider status 接口会 normalize provider，并对非 DeepSeek 返回 404。
- `kronos/web/routes/settings.py:90-100` 的 secret 写入接口直接把 path 参数 `provider` 传给 `LocalSecretStore.set_secret()`。
- `kronos/agent/secrets.py:107-111` 只做字符串 normalize，不限制 provider 集合。

**直接结果**

本地 Web API 可以写入任意 provider 名称的 secret，例如 `foo` 或拼写错误的 provider。当前 UI 只读 DeepSeek，短期不会泄露 secret，但会制造不可见配置状态；如果未来把 Web 暴露到局域网或新增 provider，会扩大配置面和审计难度。

**根因**

状态查询接口做了 provider 边界，写入接口没有共享同一个校验函数。SecretStore 被设计成通用 provider store，但产品层目前只支持 DeepSeek，两个层级的边界没有对齐。

**建议判定**

v0.4.0 前修复。把 provider normalize + whitelist 抽成共享函数，写入、读取、删除都一致拒绝未支持 provider。

## P1-3：v0.4.0 backlog 的产品目标已经过期

**严重度**：P1 / Product

**证据**

- `TODO.md:71-74` 仍写下一版本 v0.4.0 的产品目标是“让一个非开发交易者在 10 分钟内判断 R-breaker 是否值得进入模拟盘观察”。
- 但 `TODO.md:76-91` 的 P0/P1 已标为完成。
- 真正未做的 v0.4.0 内容在 `TODO.md:93-101`：AI 自然语言策略创建、实时模拟盘、历史重放、市场状态分段、TOML 策略配置。

**直接结果**

下一轮开发可能继续围绕 R-breaker 首次判断打转，而不是明确进入“从研究报告到可观察模拟盘”的下一阶段。产品目标和实际 backlog 不一致，会让优先级评审失真。

**根因**

v0.3.3 收口后只追加了已完成事项，没有同步重写 v0.4.0 的北极星目标和分阶段验收标准。

**建议判定**

先改产品目标再拆任务。建议 v0.4.0 目标改成：“让用户能用自然语言或 TOML 定义一个策略，并在历史重放/模拟盘前看到可判定的风险边界。”

## P2-1：Agent tool 的 input_schema 当前只是文档，不是执行校验

**严重度**：P2 / Low-Medium

**证据**

- `kronos/agent/tools.py:120-132` 取到 tool definition 后直接 `handler(dict(payload))`。
- `AgentToolDefinition.input_schema` 没有在 executor 层校验。

**直接结果**

工具白名单能保证 tool name，但不能保证 payload 结构。当前 handler 多数会自己报错，所以不是立即安全洞；但随着 AI 自然语言策略创建进入 v0.4.0，工具输入会更依赖 LLM，schema 不执行会增加失败路径和不可解释错误。

**根因**

Agent 工具层先完成了确定性工具调用和事件记录，schema 先作为描述存在，没有接入 JSON Schema/Pydantic 校验。

**建议判定**

不阻断 v0.3.3，但 v0.4.0 的 AI 创建前应补上 schema 校验和错误分类。

## P2-2：Agent console 环境扫描吞掉异常

**严重度**：P2 / Low

**证据**

- `kronos/agent/console.py:79-91` 检测数据 synthetic 状态和 DeepSeek secret 时，两个 `except Exception: pass` 会吞掉所有异常。

**直接结果**

如果 parquet 损坏、secret store JSON 损坏或权限异常，Agent 会把它表现成“没有数据/没有模型”，而不是提示状态损坏。对首次用户友好，但对本地优先产品的可诊断性偏弱。

**根因**

onboarding 优先级压过了故障透明度，环境探测没有区分“缺失”和“损坏”。

**建议判定**

可延后。建议至少记录 debug/warning 事件，用户界面仍可保持友好提示。

## P2-3：README 版本 badge 仍是 minor 口径

**严重度**：P2 / Low

**证据**

- `README.md:5` badge 为 `version-0.3`。
- `CHANGELOG.md:8`、`TODO.md:3`、`VERSION` 和 `pyproject.toml` 当前为 v0.3.3。

**直接结果**

不像 v0.3.1 时的版本错乱那么严重，但对新用户仍会造成“当前到底是 0.3 还是 0.3.3”的轻微信任损耗。

**根因**

README badge 采用 minor 级展示，而 release 元数据采用 patch 级展示。项目没有明确 badge 版本策略。

**建议判定**

可接受或统一。若 README 作为 release 面向用户，建议 badge 同步 patch；若只展示 minor，应在 release checklist 明确这是刻意选择。

## 未列为问题的观察

- `kronos data sync` 无 `--since` 时，K 线和 funding loader 会从 `startTime=0` 开始分页，OI endpoint 按 Binance 历史限制返回最近窗口；这和 `docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md:462` 的“增量同步或交易所最早可用历史”基本一致，不单独列缺陷。
- `kronos/web/routes/_mappers.py` 的 run_id 校验仍允许普通点号，但拒绝以点号开头且不允许 slash/backslash；未发现新的路径穿越证据。
- v0.3.3 已明确当前版本不会启动模拟盘或真实下单，README 的用户边界是正确的。

## 建议处理顺序

1. 先修 P0-1：测试和候选注册持久化路径隔离。否则后续测试验证本身不可信。
2. 再修 P0-2/P0-3：重写项目控制面和主设计文档，把 current / target / deferred 分开。
3. 然后判定 P1-1/P1-2/P1-3 是否纳入 v0.4.0 gate。
4. P2 项可以进入 backlog，不阻断当前 owner review。

## 验收建议

- `uv run pytest -m "not e2e"` 在修复候选持久化隔离前不应作为无副作用命令运行。
- P0-1 修复后应补一个测试：运行 candidate registry 测试时，真实 home 下的 `~/.kronos/candidates.json` 不被读写。
- 文档修复后应执行一次人工交叉检查：`README.md`、`README.en.md`、`TODO.md`、`CHANGELOG.md`、`docs/PROJECT_STATUS.md`、`docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md` 对“当前能力 / 下一版本 / 未接入模拟盘”口径一致。
