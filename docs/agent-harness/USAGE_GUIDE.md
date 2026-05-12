# Kronos Agent Harness Usage Guide

Last updated: 2026-05-09

This guide explains how a new agent should recover context and how every agent
should keep long-lived memory current.

## New Session Checklist

At the start of a new Codex, Cursor, Claude Code, or other agent session:

1. Read `AGENTS.md`.
2. Read `MEMORY.md`.
3. Read `DECISIONS.md`.
4. Read `docs/agent-harness/PROGRESS_LOG.md`.
5. For current product status, verify against `TODO.md`,
   `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, and
   `docs/PRODUCT_CONTROL_PANEL.md`.
6. For implementation tasks, read the relevant release, OpenSpec, review, or
   acceptance document before editing code.

## What To Update

Update `MEMORY.md` when:
- current product state or active backlog changes;
- a lesson learned should prevent repeated mistakes;
- the user gives a durable preference;
- a future agent would need a handoff summary to avoid rediscovery.

Update `DECISIONS.md` when:
- an architecture, product, harness, security, or process decision is made;
- an alternative is rejected and should not be re-litigated;
- a previous decision is superseded.

Update `docs/agent-harness/PROGRESS_LOG.md` when:
- harness setup changes;
- a session creates reusable handoff or verification evidence;
- memory maintenance itself is performed.

Update existing product docs when:
- version status changes;
- `TODO.md` changes;
- a release boundary moves;
- docs and runtime evidence disagree.

## What Not To Store

Do not store:
- raw API keys, passwords, tokens, Binance credentials, or private URLs;
- full command logs unless the log itself is the durable artifact;
- speculative ideas without a decision or evidence;
- every chat turn;
- duplicate copies of product docs that already have a canonical home.

Use summaries plus links to evidence.

## End-of-Task Checklist

Before finishing a task:

1. State the result in PM-readable Chinese unless the user requested technical
   detail.
2. List changed files when files changed.
3. Report verification performed and any known gaps.
4. Update `MEMORY.md`, `DECISIONS.md`, or the progress log if durable state
   changed.
5. Make sure a new agent can answer: what changed, why, how it was verified,
   and what remains.

## Tool-Specific Notes

### Codex

Codex reads `AGENTS.md` at session start. `AGENTS.md` now points to the memory
stack, so a Codex agent should explicitly read `MEMORY.md` and `DECISIONS.md`
before making current-state claims.

### Cursor

Cursor project rules live in `.cursor/rules/`. The Kronos rules are always
applied and instruct Cursor Agent to use the repository memory stack. Cursor's
own Memories feature may also create project memories, but repository markdown
remains the cross-tool source of truth.

### Claude Code

Claude Code reads `CLAUDE.md` as project memory. `CLAUDE.md` now points Claude
to the same repository-local memory stack. Claude hooks could automate context
injection later, but this setup keeps the durable layer portable.

## Recovery Prompt For A New Agent

Use this prompt when starting a new agent:

```text
You are working in /Users/ethan/Kronos. Before answering or editing, read
AGENTS.md, MEMORY.md, DECISIONS.md, docs/agent-harness/PROGRESS_LOG.md,
TODO.md, docs/PROJECT_STATUS.md, and docs/ROADMAP.md. Then summarize the
current Kronos product state, the active backlog, and any relevant recent
decisions in Chinese. Do not rely on chat history alone.
```

## Mechanical Verification

Run this after editing harness files:

```bash
python3 scripts/harness_memory_check.py
```

For Python hygiene on the checker:

```bash
uv run ruff check scripts/harness_memory_check.py
```
