# Kronos Persistent Memory

Last updated: 2026-05-11
Owner: Agent harness / all coding agents working in this repository

This file is the long-lived, repository-local memory for Kronos. Read it at the
start of every new agent session, after context compaction, and before making
claims about current project state. Update it when durable facts, decisions,
lessons learned, or handoff-critical progress changes.

## Boot Protocol

1. Read `AGENTS.md` for repository-wide behavior and verification rules.
2. Read this file for current long-lived project memory.
3. Read `DECISIONS.md` for durable decisions and rejected alternatives.
4. Read `docs/agent-harness/PROGRESS_LOG.md` for recent harness and handoff
   progress.
5. For current product state, verify against `TODO.md`,
   `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, and
   `docs/PRODUCT_CONTROL_PANEL.md`.
6. For a task-specific area, read the relevant release/OpenSpec/review docs
   before changing code.

Do not rely on chat memory alone. If a fact should survive a new conversation,
it belongs in this file, `DECISIONS.md`, or an indexed project document.

## Current Kronos State

- Kronos is a local-first crypto strategy research Agent, not a generic
  backtest toy and not a live-trading bot.
- Current version state on 2026-05-11: v0.4.10 is complete as Agent Memory
  Control / Agent 记忆与交接控制台; the next planned line is v0.4.11.
- v0.4.8 added the Binance testnet paper-trading minimum loop:
  credentials, preflight, start/status/stop, ledger, and report. The default
  automated path uses mock testnet and must not touch mainnet or real funds.
- v0.4.9 added testnet paper-trading status visibility in the Web workbench:
  `/api/paper/status`, `/api/paper/runs/{run_id}/report`, and the
  `PaperStatusPanel` dashboard block.
- v0.4.9 real testnet acceptance succeeded with run `20260509T134805Z-paper`:
  ETHUSDT BUY 0.01 MARKET, order id `8693595272`, trade id `272130743`,
  status `FILLED`, fee `0.0092516 USDT`. Evidence is in
  `docs/TESTNET_E2E_ACCEPTANCE_20260509.md` and `reports/paper/`.
- v0.4.9 multi-persona simulated user acceptance is also complete:
  `docs/KRONOS_V049_PERSONA_ACCEPTANCE_20260511.md` covers the successful CLI
  and Web path, empty status, no-credential preflight block, reviewer evidence,
  and the remaining v0.4.10 product follow-up.
- v0.4.10 productized the persistent harness into a Web-visible Agent Memory
  Control surface: current state, acceptance target, latest successful run,
  source docs, decisions, lessons, handoff package, and memory-drift checks.
  The acceptance record is `docs/KRONOS_V0410_PERSONA_ACCEPTANCE_20260511.md`.
- The current product boundary is research reports, Agent review, strategy
  drafts, strategy config trial runs, read-only observation plans, and Binance
  testnet paper trading. Mainnet live trading remains out of scope.

## Product Direction

- Product north star: a crypto strategy research Agent that can choose
  candidates, form hypotheses, run deterministic validation tools, explain
  results, remember failures, and propose the next action behind human gates.
- Agent suggestions must be traceable to reports, experiment artifacts,
  failures, or explicit hypotheses. No ungrounded strategy advice.
- The Web workbench is the product control surface; the Agent Supervisor is the
  runtime body. Browser close must not be treated as Agent stop in future
  runtime design.
- Old A-share / futures / QuantPort strategy assets are candidate material and
  factor mines. They should not be wholesale-migrated into Kronos as the main
  product line.

## Durable Operating Lessons

- Every new version must have a release development plan and OpenSpec before
  implementation starts. Required indexes: `TODO.md`, `docs/PROJECT_STATUS.md`,
  `docs/ROADMAP.md`, and `docs/PRODUCT_CONTROL_PANEL.md`.
- The user prefers PM/business-readable Chinese progress reports for Kronos:
  module, state, impact, next step. Avoid leading with class/function/file
  names unless technical detail is requested.
- Literal UX evidence matters. For fresh Docker or onboarding evaluation,
  actually run the path, stop on real errors, and do not fill product gaps with
  assumptions.
- `TODO.md` is the live backlog. `docs/PROJECT_STATUS.md`,
  `docs/ROADMAP.md`, and `docs/PRODUCT_CONTROL_PANEL.md` are product/status
  mirrors. Keep them aligned when state changes.
- Existing planning files `task_plan.md`, `findings.md`, and `progress.md`
  are useful local working-memory surfaces, but they are not the only durable
  project memory. Promote durable conclusions into this file or docs.
- Agent MVP artifacts should include PM-readable reports, machine summaries,
  event timelines, and error reports. Logs and timelines are product evidence,
  not afterthoughts.
- No secrets in memory. Store only secret locations, masked status, and
  handling rules. Never write raw API keys, passwords, tokens, or private
  exchange credentials into markdown memory.
- Local tests must isolate credentials with `KRONOS_SECRET_STORE_PATH`; they
  must not read the user's real `.kronos-secrets/agent_secrets.json`.
- User-style acceptance should include empty/no-credential paths as well as
  successful runs. Do not treat one successful testnet order as a complete
  product acceptance if the new-user and reviewer paths have not been checked.
- Mainnet/live trading, credential changes, destructive cleanup, and irreversible
  state changes require explicit user confirmation and current-state
  verification.

## Harness Memory Layers

| Layer | File or directory | Purpose | Update rule |
|---|---|---|---|
| Bootstrap rules | `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/` | Tell agents how to load and maintain memory | Keep short; use as map, not encyclopedia |
| Long memory | `MEMORY.md` | Current durable facts, lessons, and handoff state | Update after meaningful state changes |
| Decision log | `DECISIONS.md` | Architecture/product/process decisions and rejected alternatives | Append new decisions; do not silently rewrite history |
| Recent progress | `docs/agent-harness/PROGRESS_LOG.md` | Session-level harness progress and verification | Append concise entries |
| Product truth | `TODO.md`, `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md` | Current product status and next work | Update with feature/release state changes |
| Deep docs | `docs/`, `openspec/changes/` | Specs, reviews, acceptance, release requirements | Prefer task-specific docs over chat summaries |

## Memory Write Triggers

Update persistent memory when any of these happens:

- a product version, release boundary, or active backlog changes;
- an architecture decision is made or reversed;
- a repeated bug, UX failure, or agent mistake is diagnosed;
- the user states a durable preference or project rule;
- a task creates a reusable workflow, command, or verification pattern;
- a blocker or handoff point would confuse a new agent without context.

Do not write transient command output, speculative ideas, raw logs, or secrets.
Summarize what matters and point to evidence.

## Verification Loop

Before claiming completion:

1. Identify what proves the claim.
2. Run the relevant local check or read the relevant truth source.
3. If docs and code disagree, report the mismatch and update the stale doc when
   the task authorizes it.
4. Record durable state changes in the memory layer above.
5. Leave the next agent with a clear stop point, changed files, verification,
   and remaining risks.

## Recent Memory Updates

### 2026-05-09 - Persistent Agent Harness Enabled

- Added a repo-local Agent Harness memory layer so Codex, Cursor, Claude Code,
  and future agents can recover the same project state without relying on a
  single chat transcript.
- The harness intentionally reuses Kronos' existing project-control documents
  instead of creating a parallel planning system.
- See `docs/agent-harness/SETUP_REPORT_20260509.md` and
  `docs/agent-harness/USAGE_GUIDE.md`.

### 2026-05-09 - Agent Memory Control Planned For v0.4.10

- Productized the harness conclusion into a planned v0.4.10 module:
  Agent Memory Control / Agent 记忆与交接控制台.
- Created `docs/RELEASE_0.4.10_AGENT_MEMORY_CONTROL.md` and
  `openspec/changes/p4-agent-memory-control/`.
- Indexed the plan from `TODO.md`, `docs/PROJECT_STATUS.md`,
  `docs/ROADMAP.md`, and `docs/PRODUCT_CONTROL_PANEL.md`.
- Durable constraint: v0.4.10 is P1 and follows v0.4.9; it is read-only first,
  source-linked, redacted, and must not automatically overwrite long-term
  memory.

### 2026-05-09 - Version Planning Gate And v0.4.9 Plan Added

- User set a durable rule: every version must have a complete development plan
  before implementation starts.
- Added v0.4.9 release plan `docs/RELEASE_0.4.9_TESTNET_WEB_STATUS.md`.
- Added OpenSpec `openspec/changes/p4-testnet-web-status/`.
- Durable constraint: v0.4.9 is testnet evidence plus Web paper-status
  visibility; it must preserve credentials, promoted-candidate, observation
  plan, preflight, and explicit-user-authorization gates.

### 2026-05-09 - v0.4.9 Web Paper Status Completed

- Added Web paper status/report API and a dashboard paper-status panel.
- Web now reads paper status, orders, fills, errors, and Markdown reports from
  `reports/paper/` without exposing raw Binance testnet credentials.
- User-provided Binance testnet credentials are stored in the local ignored
  SecretStore, and no-order account/ticker connectivity passed.

### 2026-05-09 - v0.4.9 Real Testnet E2E Accepted

- Generated a real-data promoted observation candidate:
  `20260509T-v049-signal-persistence-4h-cross-section`, using
  `signal_persistence_density` over ETHUSDT/BTCUSDT/SOLUSDT, 4h resampled from
  90.14 days of 1m data.
- Observation plan and `paper preflight` passed without forging metadata.
- First ETHUSDT 0.001 order was rejected by Binance testnet `MIN_NOTIONAL=20`;
  v0.4.9 now checks exchange minimum notional before order submission.
- Second ETHUSDT 0.01 testnet order completed as `20260509T134805Z-paper`.
- Web workbench browser acceptance showed completed/testnet status, order,
  fill, fee, report entry, and no current-page console errors.

### 2026-05-11 - v0.4.10 Agent Memory Control Completed

- Added `kronos/agent/memory_control/` for repository-file-backed memory
  summaries, handoff prompt generation, drift checks, and redaction.
- Added Web API routes under `/api/agent/memory/*`.
- Added Web workbench sidebar entry `记忆` and dashboard v0.4.10 memory
  snapshot.
- The first screen now shows current version, next version, acceptance target,
  latest successful run / acceptance record, source docs, and recommended next
  action.
- Added `docs/KRONOS_V0410_PERSONA_ACCEPTANCE_20260511.md`.
- Durable constraint: the memory console is read-only first and must not
  automatically overwrite `MEMORY.md`, `DECISIONS.md`, or other long-term
  memory.
