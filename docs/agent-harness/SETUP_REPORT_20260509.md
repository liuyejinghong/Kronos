# Kronos Agent Harness Setup Report

Date: 2026-05-09

## Executive Conclusion

Kronos now has a repository-local persistent Agent Harness: a small set of
bootloader rules plus durable markdown memory, decision, progress, and product
truth files. The goal is not to preserve every chat token. The goal is to make
the next agent recover the same product state, decisions, architecture
constraints, lessons learned, and verification rules without relying on a
single provider's chat history.

## 2026 Practice Scan

### OpenAI / Codex

OpenAI's 2026 harness engineering guidance points to a clear pattern:
engineers design environments, intent specs, and feedback loops; agents execute
inside that harness. The most relevant lesson for Kronos is that repository
knowledge should be the system of record, while `AGENTS.md` should behave like
a concise map, not a giant encyclopedia.

Practical implications for Kronos:
- Keep `AGENTS.md` short and navigational.
- Store durable knowledge in structured repository files.
- Treat plans, progress, decisions, and verification as first-class artifacts.
- Add mechanical checks so documentation drift is detectable.

Sources:
- https://openai.com/index/harness-engineering/
- https://developers.openai.com/codex/guides/agents-md
- https://openai.github.io/openai-agents-python/sessions/
- https://openai.github.io/openai-agents-python/tracing/
- https://openai.github.io/openai-agents-python/guardrails/

### Anthropic / Claude Code

Claude Code's official memory model uses project-level `CLAUDE.md` files,
hierarchical loading, project/user/local scopes, and hooks for deterministic
behavior. Claude Code hooks can also inject context at session start, but this
repository currently keeps `.claude/` local/ignored, so the portable layer is
the root `CLAUDE.md` plus shared markdown memory.

Practical implications for Kronos:
- Root `CLAUDE.md` must point to the same memory stack as Codex.
- Any future Claude hook should load `MEMORY.md`, `DECISIONS.md`, and recent
  progress, but not duplicate the canonical state.
- Hooks are useful for deterministic verification, but should be introduced
  only when they are committed and maintained deliberately.

Sources:
- https://code.claude.com/docs/en/memory
- https://code.claude.com/docs/en/settings
- https://code.claude.com/docs/en/hooks

### Cursor

Cursor's current official model is Project Rules under `.cursor/rules/`,
version-controlled and scoped to the codebase. Cursor Memories are
project-scoped and can preserve context across sessions, but generated memories
require user approval and are Cursor-specific. For cross-tool continuity,
Kronos should use Cursor rules as a bootloader and markdown files as the
portable source of truth.

Practical implications for Kronos:
- Use `.cursor/rules/*.mdc` with `alwaysApply: true` for boot protocol.
- Keep rules focused and composable.
- Let Cursor Memories augment the repo memory, not replace it.

Sources:
- https://docs.cursor.com/context/rules
- https://docs.cursor.com/en/context/memories

### Community: OpenHarness / Harness-Mem

OpenHarness points toward a standard API layer for agent harnesses, including
execution, tools, memory, agents, and sessions. Harness-Mem-style community
packages emphasize cross-session memory, plans, review-result tracking,
guardrail activations, and a project SSOT.

Practical implications for Kronos:
- The memory shape should be portable: memory blocks, decision blocks, progress
  logs, and verification checkpoints.
- Do not adopt a new runtime dependency until Kronos needs multi-harness
  portability or automated memory hooks beyond markdown.
- Use the community pattern now, not necessarily the community package.

Sources:
- https://openharness.ai/
- https://openharness.ai/api-reference.html
- https://mcpmarket.com/ja/tools/skills/harness-mem
- https://pypi.org/project/openharness-ai/

## Files Created Or Updated

Created:
- `MEMORY.md`
- `DECISIONS.md`
- `docs/agent-harness/PROGRESS_LOG.md`
- `docs/agent-harness/USAGE_GUIDE.md`
- `docs/agent-harness/SETUP_REPORT_20260509.md`
- `.cursor/rules/00-kronos-agent-harness.mdc`
- `.cursor/rules/10-kronos-memory-protocol.mdc`
- `.cursor/rules/20-kronos-product-context.mdc`
- `scripts/harness_memory_check.py`

Updated:
- `AGENTS.md`
- `CLAUDE.md`

## Kronos-Specific Deep Analysis

### 1. Kronos already had a product-control spine

Kronos is not starting from zero. `TODO.md`, `docs/PROJECT_STATUS.md`,
`docs/ROADMAP.md`, `docs/PRODUCT_CONTROL_PANEL.md`, OpenSpec changes, release
docs, and UX review docs already form a strong project-control layer. The
right Harness move is therefore not to create a second management system. It is
to add a memory boot protocol that tells every agent which existing files are
authoritative.

This is why `MEMORY.md` summarizes current state but does not replace
`TODO.md` or `docs/PROJECT_STATUS.md`.

### 2. The biggest Kronos risk is not code amnesia, it is product-state drift

Kronos changes quickly across versions: v0.4.4 result cards, v0.4.5
interpretability, v0.4.7 observation plans, v0.4.8 testnet paper trading, and
v0.4.9 Web status / real testnet evidence. A new agent can easily mix old
Agent MVP facts with the current product boundary.

The harness addresses this by requiring a current-state reconciliation step:
`MEMORY.md` gives the map, while `TODO.md` and status docs provide the live
release truth.

### 3. Long memory should be canonical, not exhaustive

For Kronos, "zero drift" does not mean every chat line is retained. It means
all durable conclusions are recorded in the right place:
- status in `TODO.md` / status docs;
- long-lived lessons in `MEMORY.md`;
- tradeoff decisions in `DECISIONS.md`;
- recent handoff progress in `docs/agent-harness/PROGRESS_LOG.md`;
- detailed product evidence in `docs/` and `openspec/changes/`.

This avoids the failure mode where a giant instruction file becomes too stale
and too large to be useful.

### 4. Current Kronos Agent work makes this unusually high leverage

Kronos itself is an Agent product. Its internal product thesis is that an Agent
must read evidence, remember failures, and avoid repeating invalid research
directions. The development harness now mirrors that product thesis: the coding
agents working on Kronos must also read evidence, remember failures, and avoid
repeating invalid project assumptions.

That symmetry matters. It means the development process is no longer separate
from the product architecture; it is an applied example of the same operating
model.

### 5. The harness should stay dependency-light for now

OpenHarness and Harness-Mem are directionally aligned with Kronos' needs, but
adopting them immediately would add another runtime surface before Kronos has a
specific integration requirement. The current repo-local markdown setup gives
the project 80% of the continuity value with almost no operational risk.

Future adoption becomes attractive when Kronos needs:
- automatic memory write hooks across multiple agent tools;
- a standard API for memory blocks and sessions;
- multi-agent conformance tests;
- or a shared memory service for long-running background agents.

## Guarantees And Limits

What this setup guarantees:
- New agents have a stable, versioned place to recover current project memory.
- Cursor, Codex, and Claude Code all point to the same persistent memory stack.
- Durable decisions and lessons have explicit homes.
- Harness integrity can be checked mechanically.

What it cannot guarantee by itself:
- Cursor will save generated Memories without user approval.
- Every external agent will obey the protocol if it ignores project files.
- Product status will stay current unless agents update the existing control
  docs when real state changes.

## Verification

Run:

```bash
python3 scripts/harness_memory_check.py
uv run ruff check scripts/harness_memory_check.py
```

Expected:
- all required harness files exist;
- core boot markers are present;
- Cursor rules exist;
- Python checker passes lint.
