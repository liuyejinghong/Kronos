# Kronos Decision Log

Last updated: 2026-05-11

This file records durable decisions for future agents. Append new entries in
reverse chronological order when a choice would otherwise be rediscovered in a
new session.

## D-20260511-011 - Complete v0.4.10 as read-only Agent Memory Control

Status: accepted

Decision: v0.4.10 completes Agent Memory Control as a read-only Web product
surface backed by repository files. It reads memory, decisions, progress, TODO,
project status, roadmap, and product control docs; it generates a handoff pack;
and it runs explicit drift / secret-like checks without auto-writing long-term
memory.

Context: v0.4.9 simulated user acceptance showed that Web first screens must
make the current version, acceptance object, latest successful run, source docs,
and next action obvious. The user explicitly asked to补充 this constraint before
starting v0.4.10 development.

Consequences:
- `kronos/agent/memory_control/` is the productized memory reader/checker
  boundary.
- `kronos/web/routes/memory.py` exposes `/api/agent/memory/*` routes.
- `web/components/agent-memory-panel.tsx` is the first Web surface.
- `docs/KRONOS_V0410_PERSONA_ACCEPTANCE_20260511.md` is the acceptance record.
- Future memory write automation needs a separate version plan and human gate.

Rejected: auto-apply memory updates from the Web console | first-version memory
pollution risk is higher than the convenience benefit.
Rejected: introduce vector DB or OpenHarness runtime dependency for v0.4.10 |
file-backed memory is enough for the accepted product surface and stays
tool-agnostic.

Confidence: high
Scope-risk: moderate

## D-20260511-010 - Treat v0.4.9 acceptance as multi-persona, not single-run only

Status: accepted

Decision: v0.4.9 product acceptance is the real testnet run plus a
multi-persona simulated user check. The acceptance record is
`docs/KRONOS_V049_PERSONA_ACCEPTANCE_20260511.md`, covering the L1 operator
success path, empty status, no-credential preflight block, reviewer evidence,
and Web desktop / narrow-screen reading path.

Context: The first user-view recheck proved the successful path but was not a
complete simulated-user process. The user asked to follow the real process.
Running the no-credential path in an isolated `KRONOS_SECRET_STORE_PATH`
confirmed the product blocks safely instead of reading local configured
testnet credentials.

Consequences:
- A single filled testnet order is evidence for execution plumbing, not the
  entire product acceptance.
- Future acceptance should include empty state, missing credential, reviewer,
  and Web reading paths where relevant.
- The remaining product follow-up is first-screen clarity: v0.4.10 should show
  current version, acceptance object, latest successful run, and source docs so
  old batch language does not confuse the user.

Rejected: consider `20260509T134805Z-paper` alone sufficient for product
acceptance | it omits new-user and reviewer failure/safety paths.
Rejected: use the local configured SecretStore for no-credential tests | it
would mask the exact path a new user sees.

Confidence: high
Scope-risk: narrow

## D-20260509-009 - Complete v0.4.9 with a real testnet E2E acceptance run

Status: accepted

Decision: v0.4.9 is complete only after both Web paper-status visibility and a
real Binance testnet E2E acceptance run are verified. The accepted run is
`20260509T134805Z-paper`, sourced from a real promoted observation candidate
and gated by observation-plan metadata plus paper preflight.

Context: The initial v0.4.9 attempt was blocked by missing promoted candidates,
which was correct. A later real-data cross-section run promoted
`signal_persistence_density`; the observation plan and preflight passed; a
first ETHUSDT 0.001 order exposed Binance testnet `MIN_NOTIONAL=20`, then an
ETHUSDT 0.01 order completed with order id `8693595272` and trade id
`272130743`.

Consequences:
- `docs/TESTNET_E2E_ACCEPTANCE_20260509.md` is the acceptance record.
- Testnet success does not imply strategy profitability or live-trading
  readiness.
- `paper start` must check exchange minimum notional before order submission
  when the testnet adapter can provide it.
- Tests must use an isolated secret-store path, not the user's local
  `.kronos-secrets/agent_secrets.json` credentials.
- Auto-run can select a registered factor name directly as an ephemeral
  candidate so validation users are not forced to mutate the candidate store.

Rejected: treat the initial no-candidate preflight block as final v0.4.9
completion | the user explicitly asked to complete 0.4.9 and proceed into
simulated user acceptance.
Rejected: bypass observation metadata or preflight to force an order | would
weaken the safety chain established in v0.4.8.

Confidence: high
Scope-risk: moderate

## D-20260509-008 - Complete v0.4.9 as read-only Web paper status

Status: accepted

Decision: v0.4.9 first completed the Web visibility part of testnet paper
trading: read paper status, recent orders/fills/errors, and paper reports from
`reports/paper/` through a read-only Web API and dashboard panel. The real
Binance testnet E2E was completed afterward under D-20260509-009.

Context: The user asked to start v0.4.9. The codebase already had CLI paper
trading and local ledger/report artifacts. The user later provided Binance
testnet credentials, which were written to the local ignored SecretStore. The
initial real E2E attempt was properly blocked because no promoted real 90-day
candidate was available at that point.

Consequences:
- `kronos/web/routes/paper.py` is the paper Web API boundary.
- `web/components/paper-status-panel.tsx` is the first product surface.
- Web report responses sanitize secret-like text before returning Markdown,
  while local `paper_report.md` remains the disk evidence artifact.
- Real testnet order submission remains gated by credentials, promoted
  candidate, observation plan, preflight, and explicit user authorization.

Rejected: add a Web start button for testnet orders | would turn a read-only
status release into a trading control surface and risk bypassing preflight.
Rejected: mark real E2E as done with mock data | would corrupt the evidence
chain and weaken the v0.4.8 safety gate.

Confidence: high
Scope-risk: moderate

## D-20260509-007 - Require release docs and OpenSpec before every version

Status: accepted

Decision: Every Kronos version must have a complete release development plan
and OpenSpec change before implementation starts.

Context: The user explicitly said every version should have a full development
plan before development. v0.4.10 already followed this pattern; v0.4.9 was only
listed in TODO and status docs, so it needed to be corrected.

Consequences:
- Each version needs `docs/RELEASE_<version>_<topic>.md`.
- Each version needs an OpenSpec change with proposal, design, tasks, and spec.
- TODO, Project Status, Roadmap, and Product Control Panel must index the
  version docs before coding.
- Bare TODO items are not sufficient authorization to start normal version
  development.

Rejected: keep using TODO-only version entries | too easy for agents to start
implementation without agreed scope, risks, tests, and non-goals.

Confidence: high
Scope-risk: moderate

## D-20260509-006 - Plan Agent Memory Control for v0.4.10 after testnet Web status

Status: accepted

Decision: Productize the persistent Agent Harness as a v0.4.10 P1 module named
Agent Memory Control / Agent 记忆与交接控制台, after the v0.4.9 testnet paper
trading status/report Web work.

Context: The user approved the product direction and asked to put it into the
version plan with indexes and development documents first. The active v0.4.9
line still owns real testnet evidence and Web status/report visibility.

Consequences:
- v0.4.10 has a release requirement doc and OpenSpec before implementation.
- `TODO.md`, `PROJECT_STATUS.md`, `ROADMAP.md`, and
  `PRODUCT_CONTROL_PANEL.md` index the new module.
- The first implementation must be read-only, source-linked, redacted, and
  suggestion-oriented.

Rejected: implement immediately in v0.4.9 | would distract from the testnet
paper-trading Web visibility line.
Rejected: allow automatic memory overwrite in the first version | long-term
memory pollution is more dangerous than requiring manual confirmation.

Confidence: high
Scope-risk: moderate

## D-20260509-005 - Do not store secrets or raw transcripts in memory

Status: accepted

Decision: Persistent memory stores summarized project facts, decisions, lessons,
and evidence pointers only. It must not store raw API keys, passwords, tokens,
private exchange credentials, or full unfiltered chat/tool transcripts.

Context: Kronos now includes exchange credential handling for Binance testnet
paper trading. Long-lived agent memory must improve continuity without creating
a security sink.

Consequences:
- Secret values stay in the existing SecretStore/config mechanisms only.
- Memory can record masked status and safe handling rules.
- Long logs are linked or summarized; they are not copied wholesale.

Rejected: store every chat and command output in `MEMORY.md` | this would bloat
context, leak sensitive material, and make future agents worse at finding the
canonical fact.

Confidence: high
Scope-risk: narrow

## D-20260509-004 - Do not add a runtime OpenHarness or Harness-Mem dependency yet

Status: accepted

Decision: Enable a filesystem-based harness using repository markdown,
Cursor rules, Codex/Claude instruction files, and a local checker script. Do not
add a new third-party harness runtime dependency in this pass.

Context: The user's goal is cross-session memory and agent handoff continuity
inside the existing Kronos project. Current official and community practice
supports repo-local system-of-record memory, but Kronos does not yet need a new
agent runtime layer.

Consequences:
- The setup is tool-agnostic across Codex, Cursor, and Claude Code.
- There is no dependency, packaging, or security-review burden from a new agent
  framework.
- Future adoption of OpenHarness/Harness-Mem remains possible if Kronos needs
  multi-harness API portability or automated memory hooks beyond markdown.

Rejected: install Harness-Mem immediately | useful direction, but it would add
an external CLI/runtime surface before Kronos has a concrete need for it.
Rejected: migrate Kronos Agent runtime to OpenHarness | too broad and unrelated
to the requested persistent project memory layer.

Confidence: high
Scope-risk: narrow

## D-20260509-003 - Treat existing Kronos control docs as product truth

Status: accepted

Decision: The harness must reuse and point to `TODO.md`,
`docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, and
`docs/PRODUCT_CONTROL_PANEL.md` instead of inventing a parallel product status
system.

Context: Kronos already has a mature project-control layer. A new memory system
would drift if it duplicated release status and backlog ownership.

Consequences:
- `MEMORY.md` stores the current durable summary and navigation map.
- Version and backlog changes still land in the existing control documents.
- Future agents must reconcile the memory layer with the product truth files
  before reporting current status.

Rejected: make `MEMORY.md` the only status source | too likely to diverge from
the project's existing roadmap and TODO surfaces.

Confidence: high
Scope-risk: moderate

## D-20260509-002 - Use instruction files as bootloaders, not encyclopedias

Status: accepted

Decision: `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/*.mdc` should stay short
and point agents toward canonical memory/docs. They should not copy the whole
project history.

Context: Official harness guidance favors a small stable map plus structured
repo-local docs. Large monolithic instruction files waste context and rot.

Consequences:
- Agents start with the same boot protocol across tools.
- Detailed state lives in `MEMORY.md`, `DECISIONS.md`, and `docs/`.
- Drift is easier to detect because each file has a bounded job.

Rejected: one giant `AGENTS.md` | hard to verify, expensive in context, and
likely to become stale.

Confidence: high
Scope-risk: narrow

## D-20260509-001 - Make repository-local files the cross-session memory SSOT

Status: accepted

Decision: Kronos' persistent agent memory is file-based and repository-local:
`MEMORY.md`, `DECISIONS.md`, `docs/agent-harness/PROGRESS_LOG.md`,
tool-specific bootstrap rules, and existing product-control docs.

Context: The user wants new agents, new chats, and Cursor restarts to recover
the prior work, decisions, architecture, and lessons learned without relying on
opaque chat history.

Consequences:
- Memory survives model switches and new conversations.
- Every agent can inspect, diff, and update the same artifacts.
- Memory remains human-readable and reviewable in normal code review.

Rejected: rely on provider chat history only | not portable across tools and
fragile under compaction or new sessions.
Rejected: rely only on Cursor Memories | useful in Cursor, but not available to
Codex, Claude Code, shell agents, or CI-style workflows.

Confidence: high
Scope-risk: moderate
