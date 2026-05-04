# Kronos Onboarding 根因修复方案

> 基于 `docs/ONBOARDING_UX_REVIEW.md` 的发现

## 设计原则

1. **不补丁**：每个修复解决根因，不是给问题打补丁
2. **零依赖启动**：新用户不需要 API Key、代理、前置数据就能看到 Kronos 在做什么
3. **中英双语**：CLI 和 README 支持简体中文和英语切换

---

## Fix 1: README.md（双语）

**根因**：项目没有任何面向用户的文档入口。

**方案**：
- 创建 `README.md`，中英双语
- 结构：一句话介绍 → Quick Start（3 步）→ 这是什么 → 文档索引
- Quick Start 只包含 3 个命令：安装 → quickstart → 打开 Web
- 语言切换：README 顶部中英双语并列

## Fix 2: `kronos quickstart` 命令

**根因**：新用户没有"一键体验"路径，每个功能都需要前置步骤。

**方案**：
- 新增 `kronos quickstart` 命令
- 流程：
  1. 检测本地数据是否存在
  2. 如果不存在，生成 7 天 BTCUSDT synthetic kline 数据（基于随机游走）
  3. 运行 `kronos research auto-run`（最小窗口，快速完成）
  4. 输出 PM 可读报告路径
  5. 提示 Web 工作台 URL（`http://127.0.0.1:3000`）
  6. 提示下一步（配置 DeepSeek、同步真实数据）
- 选项：
  - `--lang zh/en` 切换语言
  - `--skip-data-gen` 跳过数据生成（已有数据时）
  - `--open-web` 自动打开浏览器

## Fix 3: 配置自动发现

**根因**：`load_config()` 只接受显式路径，不支持 fallback。

**方案**：
- 修改 `load_config()` 支持以下 fallback 链：
  1. 显式传入的路径
  2. `KRONOS_CONFIG` 环境变量
  3. `./configs/dev.toml`
  4. `../configs/dev.toml`（向上查找 3 层）
  5. `~/.kronos/config.toml`
  6. 内置默认值（Pydantic model defaults）
- 当使用 fallback 时，打印 info 日志说明使用了哪个配置

## Fix 4: 中英双语 i18n

**根因**：CLI 输出全部硬编码中文。

**方案**：
- 创建 `kronos/common/i18n.py`：简单的 gettext 风格翻译字典
- 支持 `zh`（简体中文，默认）和 `en`（英语）
- 通过以下方式切换：
  1. `--lang en` CLI 全局选项
  2. `KRONOS_LANG=en` 环境变量
  3. `[runtime] lang = "en"` 配置文件
- 优先级：CLI > 环境变量 > 配置文件 > 默认(zh)
- 第一版只翻译 CLI 帮助文本和 quickstart 输出

## Fix 5: 内置 Sample 数据生成器

**根因**：没有数据时，整个系统不可用。

**方案**：
- 创建 `kronos/data/seed.py`：sample 数据生成器
- 生成 BTCUSDT 最近 7 天的 1m synthetic kline 数据
- 使用随机游走 + 微弱趋势 + 日内季节性生成逼真但明显是 mock 的数据
- 写入标准 Parquet 分区格式（与真实数据结构一致，可直接被 query 层读取）
- 数据标记 `venue = "synthetic"` 以区分真实数据

---

## 实现文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `README.md` | 新建 | 双语 README |
| `kronos/common/i18n.py` | 新建 | 中英双语翻译字典 |
| `kronos/common/config.py` | 修改 | 配置自动发现 fallback 链 |
| `kronos/data/seed.py` | 新建 | Sample 数据生成器 |
| `cli/main.py` | 修改 | 新增 `quickstart` 命令 + `--lang` 全局选项 |
| `docs/ONBOARDING_UX_REVIEW.md` | 已完成 | 问题报告 |
| `docs/ONBOARDING_FIX_PLAN.md` | 本文件 | 修复方案 |

## 验收标准

1. 全新 venv 中执行 `uv sync --dev && kronos quickstart` 能跑通全流程
2. `kronos --lang en quickstart` 输出英文
3. 从 `/tmp` 目录运行 `kronos data status` 能自动发现配置
4. README 中英双语，Quick Start 不超过 3 步
5. 现有 `496 passed` 测试不受影响
