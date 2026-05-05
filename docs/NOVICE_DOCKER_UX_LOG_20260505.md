# 小白用户 Docker 首次部署 Kronos — 体验日志

> 模拟时间：2026-05-05
> 模拟角色：会 `docker compose up`，不会 Python，没用过量化系统
> 部署方式：Docker（`git clone` → `docker compose up`）

## 一句话结论

经历 4 轮根因修复后，Docker 首次部署路径可以跑通：`docker compose up` → 构建镜像 → 自动运行 quickstart → 生成数据 → 注册 R-breaker → 评估策略 → 输出报告。但修复过程暴露了 4 个架构层面的问题。

## 模拟过程

### 第 1 轮：原始版本（commit `c50a3a2`）

```bash
git clone https://github.com/liuyejinghong/Kronos.git && cd Kronos
docker compose up
```

**结果**：构建失败。

```
failed to solve: failed to read dockerfile: open Dockerfile: no such file or directory
```

**根因**：`.gitignore` 里 `Dockerfile*` 规则把正式 `Dockerfile` 也排除了，导致 Dockerfile 未提交到仓库。

**小白视角**：看到 `docker-compose.yml` 存在，但 `docker compose up` 报错说找不到 Dockerfile。不知道是 bug 还是自己操作错了。停止。

### 第 2 轮：修复 Dockerfile 追踪

**根因修复**：`.gitignore` 改为只排除 `Dockerfile.fresh*`

**结果**：Dockerfile 可被 Docker 找到，但构建仍失败。

```
E: Failed to fetch http://deb.debian.org/debian/pool/main/n/node-npm-bundled/...
E: Unable to fetch some archives
```

构建过程耗时 8+ 分钟（下载 500+ 个 Debian 包），最终因网络超时失败。

**根因**：Dockerfile 里 `apt-get install build-essential git curl nodejs npm` 这行引入了海量 Debian 包：
- `build-essential`：gcc/g++/make/binutils 全家桶（~200MB，300+ 包）
- `nodejs` + `npm`：Node.js 完整运行时（~100MB，200+ 包）
- 从 Debian 官方源下载，国内网络极不稳定（502、EOF、超时）

**小白视角**：等了很久，进度条一直在下载东西，最后红色报错。完全不知道发生了什么，只能放弃。

### 第 3 轮：精简 Dockerfile（去掉 nodejs/npm）

**修复**：Dockerfile 去掉 `nodejs npm`（quickstart 不需要前端），保留 `build-essential`。

**结果**：构建仍失败。即使只剩 `git build-essential`，Debian 源仍不稳定，下载 `git` 包时超时。

**根因**：`build-essential` 本身依然引入了 gcc/g++/binutils 等大量包。而且这些**完全不需要**——pyarrow、duckdb、numpy、pandas、scipy 全部有预编译 wheel，不需要任何 C 编译器。

**小白视角**：和第 2 轮一样，只是报错信息稍微短了一点。仍然失败。

### 第 4 轮：彻底去掉 apt-get

**修复**：
1. Dockerfile 完全移除 `apt-get` — 裸 `python:3.12-slim` 就够了
2. 添加 `.dockerignore` — 排除 `.git/`、`data/`、`reports/`、`__pycache__/` 等，build context 从 ~2GB 降到 ~1MB
3. 修正 COPY 顺序 — `COPY kronos/` 必须在 `uv sync` 之前（hatchling 需要源码构建包）
4. 添加 `matplotlib` 到生产依赖（`diagnostics/reporting.py` 模块级 import）

**结果**：构建成功。docker compose up → 自动运行 quickstart → 输出：

```
⚡ Kronos 快速开始
✅ 7 天 BTCUSDT sample 数据已生成
✅ R-breaker 日内突破 已注册
✅ 1 个策略已评估
✅ 快速开始完成！
```

### 当前 Dockerfile（最终版）

```dockerfile
FROM python:3.12-slim
RUN pip install uv --no-cache-dir
WORKDIR /kronos
COPY pyproject.toml uv.lock ./
COPY kronos/ kronos/
RUN uv sync --frozen --no-dev --no-cache
COPY cli/ cli/
COPY configs/ configs/
COPY VERSION ./
CMD ["uv", "run", "--no-dev", "kronos", "quickstart"]
```

## 发现的问题

| # | 问题 | 用户视角 | 严重度 |
|---|------|----------|--------|
| 1 | `.gitignore` 误杀 `Dockerfile` | `docker-compose.yml` 存在但 `docker compose up` 失败，困惑 | 🔴 已修 |
| 2 | `apt-get build-essential` 完全多余 | 8 分钟下载 500+ 包后失败，无法理解 | 🔴 已修 |
| 3 | `matplotlib` 模块级 import 但不在生产依赖 | `--no-dev` 下 ModuleNotFoundError | 🔴 已修 |
| 4 | Dockerfile COPY 顺序错误 | hatchling 找不到源码目录 | 🟡 已修 |
| 5 | 下一步引导仍指向 `npm run dev`（Docker 里没 node） | 用户按提示做会失败 | 🟡 待修 |
| 6 | Docker 容器启动即退出（quickstart 完成后） | 用户看不到结果，不知道数据在哪 | 🟡 待修 |

## 关键经验

1. **永远不要在 Dockerfile 里盲目加 `apt-get install build-essential`**。先验证是否真的需要编译。Python 科学计算栈（pyarrow/duckdb/numpy/pandas/scipy）全部有预编译 wheel。

2. **`.dockerignore` 是第一优先级**。不写的话整个项目目录（含 `.git/`、`data/`、`reports/`）都进 build context，白白浪费时间和带宽。

3. **COPY 顺序决定缓存效率**。`pyproject.toml` + `kronos/` 在 `uv sync` 之前，这样依赖层可以缓存；`cli/`、`configs/` 在之后，源码改动不触发重装。
