# Kronos 开发文档 v1.0 — 最终版

## 执行摘要

> **Kronos 开发文档 v1.0 已通过 Oracle 最终评审并完成所有修正。22 个 OpenSpec 模块全部 validate 通过。文档覆盖 6 个 Phase、5 个全局规范，可支撑 Phase 1 立即开工。**

---

## 一、文档分层策略（折中方案）

不同 Phase 的文档写到不同深度，兼顾"不跑偏"和"不过期"：

| 文档层级 | Phase 1 | Phase 2-3 | Phase 4-6 |
|---|---|---|---|
| proposal（为什么做） | ✅ 详细 | ✅ 详细 | ✅ 详细 |
| design（技术决策） | ✅ 详细 | ✅ 详细 | ⬜ 概要（关键决策 + 待定标记） |
| specs（行为规格） | ✅ 详细 WHEN/THEN | ⬜ 概要（requirement 列表，无 scenario） | ⬜ 概要 |
| tasks（实现清单） | ✅ 详细 checkbox | ❌ 不写（启动时再写） | ❌ 不写 |
| 接口契约 | ✅ 详细 | ✅ 详细（跨层接口必须现在定） | ⬜ 概要 |

**核心原则**：
- **接口契约和全局规范现在就写死** → 防止后续 Phase 跑偏
- **实现细节（tasks）留到 Phase 启动时再写** → 防止过早写的 spec 过期
- **每个 Phase 启动前，先将概要级 spec 升级为详细级** → just-in-time 补充

---

## 二、完整目录结构

```
Kronos/
├── openspec/
│   ├── changes/                          # OpenSpec 变更文档（按模块）
│   │   │
│   │   │── # ═══ 全局文档 ═══
│   │   ├── global-release-workflow/       # 发版流程 + 版本管理
│   │   ├── global-module-contracts/       # 模块间依赖关系 + 接口契约
│   │   ├── global-code-standards/         # 代码规范 + 贡献指南
│   │   ├── global-testing-strategy/       # 测试策略
│   │   ├── global-deployment/             # 部署和运维规范（概要，P5 详化）
│   │   │
│   │   │── # ═══ Phase 1: 地基（详细级）═══
│   │   ├── p1-data-layer/                 # ✅ 已完成（Oracle 评审后修正）
│   │   ├── p1-factor-platform/            # 因子中台
│   │   ├── p1-backtest-engine/            # 基础回测引擎
│   │   │
│   │   │── # ═══ Phase 2: 研究能力（详细 proposal/design + 概要 specs）═══
│   │   ├── p2-factor-families/            # 补全因子家族
│   │   ├── p2-signal-diagnostics/         # Signal 诊断系统
│   │   ├── p2-walkforward/                # Walk-forward 验证
│   │   ├── p2-experiment-management/      # 实验管理
│   │   │
│   │   │── # ═══ Phase 3: 组合与风控（详细 proposal/design + 概要 specs）═══
│   │   ├── p3-portfolio-construction/     # 组合构建
│   │   ├── p3-risk-engine/                # 风控引擎
│   │   ├── p3-freqtrade-crosscheck/       # Freqtrade 交叉验证
│   │   ├── p3-notification-system/        # 通知系统
│   │   │
│   │   │── # ═══ Phase 4: AI 研究自动化（概要级）═══
│   │   ├── p4-factor-auto-generation/     # 因子自动生成
│   │   ├── p4-ml-factors/                 # ML 因子
│   │   ├── p4-knowledge-base/             # 研究知识库
│   │   │
│   │   │── # ═══ Phase 5: 执行与运营（概要级）═══
│   │   ├── p5-execution-layer/            # 执行层
│   │   ├── p5-monitoring/                 # 监控和告警
│   │   │
│   │   │── # ═══ Phase 6: 治理与上线（概要级）═══
│   │   ├── p6-governance/                 # 研究治理
│   │   └── p6-live-launch/                # 上线流程
│   │
│   └── specs/                             # 归档后的累积行为规格
│
├── docs/                                  # 非 OpenSpec 格式的文档
│   ├── DEVELOPMENT_PLAN.md                # ← 本文档（元文档 / 地图）
│   ├── ARCHITECTURE.md                    # 架构概览（从量化研究库引用）
│   └── CHANGELOG.md                       # 变更日志
│
├── AGENTS.md                              # AI agent 工作指南
├── README.md                              # 项目介绍
└── ...
```

---

## 三、全局文档清单

这些文档不属于任何 Phase，是整个项目的约束和规范。

### 3.1 发版流程 + 版本管理 (`global-release-workflow`)

| 内容 | 深度 |
|---|---|
| 语义化版本规范（SemVer） | ✅ 详细 |
| Git 分支策略（main + feature branch） | ✅ 详细 |
| Tag 和 Release 流程 | ✅ 详细 |
| 数据版本管理（data_snapshot_id） | ✅ 详细 |
| 配置版本管理（config_hash） | ✅ 详细 |
| 实验可复现性保证 | ✅ 详细 |
| CHANGELOG 维护规范 | ✅ 详细 |

### 3.2 模块间依赖关系 + 接口契约 (`global-module-contracts`)

| 内容 | 深度 |
|---|---|
| 五层架构依赖方向图 | ✅ 详细 |
| Layer 1 → Layer 2 接口（data.load() 契约） | ✅ 详细 |
| Layer 2 → Layer 3 接口（因子评分 → 组合权重） | ✅ 详细 |
| Layer 3 → 执行层接口（TargetPortfolio） | ✅ 详细 |
| 跨层共享类型定义 | ✅ 详细 |
| 配置契约（TOML section 划分） | ✅ 详细 |

### 3.3 代码规范 + 贡献指南 (`global-code-standards`)

| 内容 | 深度 |
|---|---|
| Python 代码风格（ruff 配置） | ✅ 详细 |
| 类型标注规范（mypy strict） | ✅ 详细 |
| 命名约定 | ✅ 详细 |
| 错误处理规范 | ✅ 详细 |
| 日志规范（structlog） | ✅ 详细 |
| import 顺序 | ✅ 详细 |
| docstring 规范 | ✅ 详细 |
| pre-commit hooks | ✅ 详细 |

### 3.4 测试策略 (`global-testing-strategy`)

| 内容 | 深度 |
|---|---|
| 测试分层（unit / integration / e2e） | ✅ 详细 |
| 覆盖率目标（> 80%） | ✅ 详细 |
| pytest + hypothesis 使用规范 | ✅ 详细 |
| Mock 策略（交易所 API mock） | ✅ 详细 |
| 测试数据管理 | ✅ 详细 |
| CI 集成（pre-commit + pytest） | ✅ 详细 |

### 3.5 部署和运维 (`global-deployment`)

| 内容 | 深度 |
|---|---|
| dev / backtest / live 三环境定义 | ✅ 详细 |
| VPS 部署方案 | ⬜ 概要（Phase 5 详化） |
| 监控和告警 | ⬜ 概要（Phase 5 详化） |
| 灾难恢复 | ⬜ 概要 |

---

## 四、各 Phase 模块文档状态追踪

### Phase 1: 地基

| 模块 | proposal | design | specs | tasks | Oracle 评审 | 状态 |
|---|---|---|---|---|---|---|
| p1-data-layer | ✅ | ✅ | ✅ 6 caps | ✅ 9 groups | ✅ 已修正 | **完成** |
| p1-factor-platform | ✅ | ✅ | ✅ 4 caps | ✅ 7 groups | ⬜ 待审 | **已写** |
| p1-backtest-engine | ✅ | ✅ | ✅ 3 caps | ✅ | ⬜ 待审 | **已写** |

### Phase 2: 研究能力

| 模块 | proposal | design | specs(概要) | Oracle 评审 | 状态 |
|---|---|---|---|---|---|
| p2-factor-families | ✅ | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p2-signal-diagnostics | ✅ | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p2-walkforward | ✅ | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p2-experiment-management | ✅ | ✅ | ✅ 详细（前拉） | ⬜ 待审 | **已写** |

### Phase 3: 组合与风控

| 模块 | proposal | design | specs(概要) | Oracle 评审 | 状态 |
|---|---|---|---|---|---|
| p3-portfolio-construction | ✅ | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p3-risk-engine | ✅ | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p3-freqtrade-crosscheck | ✅ | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p3-notification-system | ✅ | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |

### Phase 4-6: 概要级

| 模块 | proposal | 关键决策 | Oracle 评审 | 状态 |
|---|---|---|---|---|
| p4-factor-auto-generation | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p4-ml-factors | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p4-knowledge-base | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p5-execution-layer | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p5-monitoring | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p6-governance | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |
| p6-live-launch | ✅ | ✅ 概要 | ⬜ 待审 | **已写** |

### 全局文档

| 文档 | 状态 |
|---|---|
| global-release-workflow | ✅ 完成（proposal + design + 3 specs + tasks） |
| global-module-contracts | ✅ 完成（proposal + design + 3 specs + tasks）— Oracle 评审后冻结共享类型唯一版 |
| global-code-standards | ✅ 完成（proposal + design + 2 specs + tasks） |
| global-testing-strategy | ✅ 合并到 global-code-standards |
| global-deployment | ✅ 完成（proposal + design + 1 spec）— Oracle 评审后补充 |

---

## 五、编写流程

每个模块文档的产出流程：

```
1. openspec new change "<name>"
2. 按依赖顺序撰写 artifact（proposal → design → specs → tasks）
3. openspec validate --all 验证格式
4. Oracle 独立评审
5. 根据评审意见修正
6. 再次 validate
7. 标记完成，更新本文档状态表
```

所有模块完成后，整体产出 Kronos 开发文档 v1.0 最终版。

---

## 六、文档维护规范

### 何时更新

- **Phase 启动前**：将该 Phase 的概要级 spec 升级为详细级（补 WHEN/THEN scenario + tasks）
- **实现中发现设计偏差**：更新 design.md 的决策记录，标注变更原因
- **模块完成后**：`openspec archive` 归档变更，合并到累积 specs
- **跨 Phase 的接口变更**：必须同步更新 `global-module-contracts`

### 版本演进

| 版本 | 里程碑 | 内容 |
|---|---|---|
| **v1.0** | 当前 | 完整骨架 + P1 详细 + P2-P3 概要 + P4-P6 概要 + 全局文档 |
| **v1.1** | P1 实现完成后 | P1 实现经验反馈 + P2 详细化 |
| **v1.2** | P2 实现完成后 | P2 实现经验反馈 + P3 详细化 |
| **v2.0** | P3 实现完成后 | 系统进入可交易状态，文档大版本升级 |

---

## 七、最终一句话

> **开发文档 v1.0 不是一次性写完就不动的东西——它是一个有版本、有维护规范、有升级路径的活文档体系。接口契约和全局规范写死防跑偏，实现细节 just-in-time 防过期。**
