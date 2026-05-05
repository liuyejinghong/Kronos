# v0.3.0 小白用户 Docker 首次体验模拟

> 模拟时间：2026-05-05 | 版本：v0.3.0 (commit `3de2694`)
> 角色：会 `docker compose up`，不会 Python，没用过量化系统
> 环境：全新 Docker，无缓存

## 一句话结论

`docker compose up` 可以跑通完整 quickstart 流程（构建 3 分钟 → 数据生成 → R-breaker 注册 → 策略评估 → 报告输出）。但后续交互体验有 4 个结构性问题：每次 `docker compose run` 重复下载依赖、agent start 体验断裂、"下一步"指引在 Docker 内不可用、benchmark 基准数据因 synthetic 短期数据波动无参考价值。

## 完整操作流水

### 步骤 1：git clone ✅

```bash
git clone https://github.com/liuyejinghong/Kronos.git
```

成功。无问题。

### 步骤 2：看 README ⚠️

README 快速开始写的是 `uv sync --dev && uv run kronos quickstart`——这是本地 Python 路径。Docker 路径没有在 README 里说明。用户需要自己发现有 `docker-compose.yml` 文件。

**问题 1**：README 没有 Docker 部署说明。用户需要自己推断 `docker compose up`。

### 步骤 3：docker compose up ✅

构建 + 运行成功。耗时约 3 分钟（首次构建，下载 151MB Python 包）。quickstart 完整执行：

```
⚡ Kronos 快速开始
✅ 7 天 BTCUSDT sample 数据已生成 (10080 bars)
✅ R-breaker 日内突破 已注册
📊 同期持有 BTC: -14.2%
1 个策略已评估，0 通过验证
✅ 完成
```

**问题 2**：`kronos==0.0.0` 显示在构建日志中——`pyproject.toml` 里的版本号没同步到 `VERSION` 文件的 `0.3.0`。

### 步骤 4：查看报告 ✅

```bash
docker compose run --rm kronos ls /kronos/reports/research/experiments/
```

成功。列出了 6 个产物目录和 `ledger.jsonl`。

**问题 3**：`docker compose run` 每次执行都重新 "Building kronos"——因为容器是无状态的，每次 run 都创建新容器。对小白用户来说，看到"Building"会以为又出问题了。

### 步骤 5：启动交互式 Agent ❌

按 entrypoint 提示执行：

```bash
docker compose run --rm kronos uv run kronos agent start
```

结果：命令触发了大量额外下载（statsmodels 9.6MB、mypy 13.1MB、ruff 10.1MB），因为 `uv run` 自动检测到缺失的 dev 依赖并下载。Dockerfile 用 `--no-dev` 安装的依赖集不完整，运行时 `uv run` 又补装了。

**问题 4（严重）**：`docker compose run` 每次执行都在下载新依赖。用户体验极差——以为系统坏了。根因是 `uv run` 的自动补全机制与 `--no-dev` 的预期冲突。

## 发现的问题清单

| # | 问题 | 严重度 | 根因 |
|---|------|--------|------|
| 1 | README 没有 Docker 部署说明 | 🟡 | 文档缺失 |
| 2 | pyproject.toml 版本号仍是 0.0.0，与 VERSION (0.3.0) 不同步 | 🟡 | 版本管理体系不完整 |
| 3 | `docker compose run` 每次重建 kronos 包 + 可能下载新依赖 | 🔴 | 容器无状态 + uv run 自动补全 |
| 4 | benchmark "同期持有 BTC: -14.2%" 来自 7 天 synthetic 数据，无参考价值 | 🟡 | 数据窗口太短且非真实行情 |
| 5 | quickstart 输出的"下一步"含 `npm run dev`（Docker 内无效） | 🟡 | 虽然 entrypoint 追加了 Docker 指引，但 quickstart 自身的"下一步"仍然输出 |
| 6 | Docker 无法使用 Web 工作台（无 Node.js/前端服务） | 🟡 | docker-compose 只有 CLI 服务，无 web 服务 |
| 7 | 容器名称 `kronos-kronos-1` 对小白用户无意义 | 🔵 | docker compose 默认命名 |

## 产品逻辑问题

### Benchmarks 用 synthetic 数据给出 -14.2% 会误导用户

7 天随机游走数据，持有 BTC 的收益理论上应该在 0% 附近。但 -14.2% 说明随机游走的初始方向是剧烈下跌。这个数字对用户决策毫无参考价值，甚至可能让用户觉得"R-breaker 在熊市表现差"——但这是假数据，根本没有熊市。

**建议**：synthetic 数据生成时应该用更温和的参数（更低的 sigma，或者直接从真实 BTC 的统计特征采样），确保 benchmark 在合理范围内（比如 ±3%）。

### "下一步"双重输出造成信息混乱

quickstart 的 i18n 输出"1. 启动 Web 工作台：cd web && npm run dev"，紧接着 entrypoint 又输出 Docker 专用指引。用户看到两套互相矛盾的"下一步"，不知道该跟哪个。

**建议**：quickstart 检测运行环境（是否有 `/.dockerenv` 文件），Docker 内自动切换为 Docker 专用指引，不输出本地命令。

### `docker compose run` 不是"重新运行"

docker compose 的 `run` 命令会启动新容器、挂载 volume、执行命令。但对小白用户来说，`docker compose up` 和 `docker compose run` 的区别完全不清楚。"上次已经跑过了，为什么每次还 Building？"——这个困惑是 Docker 本身的复杂性，但 Kronos 的 Docker 设计加剧了它。

**建议**：提供一个 `docker compose exec kronos uv run kronos agent start` 的替代方案（exec 进入已运行的容器），或者在 README 里解释 Docker 使用模式。

## 优化建议（按优先级）

1. **🔴 修 `uv run` 自动下载问题**：在 Dockerfile 的 `uv sync` 之后加 `ENV UV_NO_SYNC=1`，禁止 `uv run` 自动补全依赖。这样 `docker compose run` 就不会再下载额外包。

2. **🟡 同步版本号**：`pyproject.toml` 里的 `version` 改为 `0.3.0`。

3. **🟡 README 加 Docker 说明**：在快速开始后加一行"Docker 用户：`docker compose up`"。

4. **🟡 quickstart 检测 Docker 环境**：通过 `/.dockerenv` 文件判断，自动切换输出。

5. **🔵 Synthetic 数据温和化**：降低 sigma，让 benchmark 在 ±5% 内。

6. **🔵 docker-compose 加 web 服务**：让用户能在 Docker 内用浏览器打开 Web 工作台。
