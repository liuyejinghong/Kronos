# Kronos Agent Harness Progress Log

This log is for recent harness setup and handoff progress. Keep entries concise
and append-only unless correcting a factual error.

## 2026-05-09 - Persistent Agent Harness bootstrap

Status: complete

Scope:
- Create a repository-local persistent memory framework for Codex, Cursor,
  Claude Code, and future agents.
- Ground the design in 2026 official harness practices and current Kronos
  project-control documents.
- Avoid adding new runtime dependencies or storing secrets.

Actions completed:
- Added `MEMORY.md` as the long-lived project memory and boot map.
- Added `DECISIONS.md` as the durable decision log.
- Added Cursor project rules under `.cursor/rules/`.
- Added setup report, usage guide, and this progress log under
  `docs/agent-harness/`.
- Updated root `AGENTS.md` and `CLAUDE.md` so Codex and Claude Code load the
  same memory protocol.
- Added `scripts/harness_memory_check.py` to mechanically verify the harness
  file set.

Verification:
- `python3 scripts/harness_memory_check.py`
- `uv run ruff check scripts/harness_memory_check.py`

Remaining risks:
- Cursor Memories still require Cursor-side settings and approval behavior; the
  repository can provide rules and files, but cannot force the IDE to save
  generated memories without user approval.
- Claude Code hooks can automate more of the read/write cycle, but `.claude/`
  is currently local/ignored in this repository. The durable cross-tool layer is
  therefore markdown-first.

## 2026-05-09 - Agent Memory Control planned into v0.4.10

Status: complete

Scope:
- Convert the harness setup conclusion into a product version plan for Kronos.
- Add development constraints before implementation, per user request.
- Link the plan from the normal project-control surfaces.

Actions completed:
- Added `docs/RELEASE_0.4.10_AGENT_MEMORY_CONTROL.md`.
- Added OpenSpec change `openspec/changes/p4-agent-memory-control/` with
  proposal, design, tasks, and spec.
- Added TODO items #87-#91 for v0.4.10.
- Indexed v0.4.10 from `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, and
  `docs/PRODUCT_CONTROL_PANEL.md`.
- Updated `MEMORY.md` and `DECISIONS.md` with the durable placement decision.

Verification:
- `rg` confirmed v0.4.10 release doc and OpenSpec are linked from TODO,
  Project Status, Roadmap, and Product Control Panel.
- `python3 scripts/harness_memory_check.py`

## 2026-05-09 - v0.4.9 release plan and version planning gate

Status: complete

Scope:
- Answer whether v0.4.9 had a development document.
- Correct the gap by creating the missing v0.4.9 release plan and OpenSpec.
- Preserve the rule that every version needs a complete development plan before
  implementation.

Actions completed:
- Added `docs/RELEASE_0.4.9_TESTNET_WEB_STATUS.md`.
- Added OpenSpec change `openspec/changes/p4-testnet-web-status/` with
  proposal, design, tasks, and spec.
- Updated `AGENTS.md`, `CLAUDE.md`, `MEMORY.md`, and `DECISIONS.md` with the
  version planning gate.

Verification:
- Pending final index check after TODO / Project Status / Roadmap / Product
  Control Panel sync.

## 2026-05-09 - v0.4.9 Web paper status implementation

Status: complete

Scope:
- Implement the v0.4.9 Web visibility slice for Binance testnet paper trading.
- Keep real testnet E2E gated until credentials and a promoted observation
  candidate exist. This slice completed before the later real E2E acceptance
  run.

Actions completed:
- Added `kronos/web/routes/paper.py` with paper status and report endpoints.
- Added paper response schemas and Web app context path wiring.
- Added `web/components/paper-status-panel.tsx` and paper API client types.
- Updated the report reader so it can show paper run reports.
- Redacted secret-like text in both status payloads and paper report Markdown
  before Web API responses leave the backend.
- Updated version/status docs and persistent memory with the v0.4.9 outcome.

Verification:
- `uv run pytest tests/integration/web/test_routes.py tests/unit/execution/test_paper.py`
- `uv run ruff check kronos/web/app.py kronos/web/schemas.py kronos/web/routes/paper.py tests/integration/web/test_routes.py tests/unit/execution/test_paper.py`
- `npm --prefix web run typecheck`
- `npm --prefix web run lint`
- `npm --prefix web run build`
- Browser checked desktop and narrow viewports with a temporary sample paper
  run; console had no new errors after the `latest` report request cleanup.
- Architect review initially blocked on report-body redaction; the issue was
  fixed and covered by `test_paper_run_report_route_redacts_secret_like_markdown`.

Remaining risks:
- Real Binance testnet E2E has not run because the correct product gates still
  block it: testnet credentials are now configured locally and no-order
  connectivity passed, but there is still no promoted real-data candidate.

## 2026-05-09 - v0.4.9 real testnet E2E and Web acceptance

Status: complete

Scope:
- Finish v0.4.9 beyond Web visibility by generating a real promoted candidate,
  running Binance testnet E2E, and checking the Web product surface.

Actions completed:
- Fixed single-symbol validation so unavailable `rank_ic_positive_ratio` is
  treated as not applicable, not negative evidence.
- Let `research auto-run --candidates <factor_name>` use registered factor names
  as ephemeral research candidates.
- Fixed auto-run coverage copy for resampled timeframes: 4h now reports 1m data
  as the source being resampled.
- Generated promoted run
  `20260509T-v049-signal-persistence-4h-cross-section`.
- Generated observation plan and passed paper preflight without forging
  metadata.
- Found Binance testnet `MIN_NOTIONAL=20` on the first ETHUSDT 0.001 attempt
  and added a local pre-order minimum-notional check.
- Completed ETHUSDT BUY 0.01 testnet run `20260509T134805Z-paper` with order
  id `8693595272`, trade id `272130743`, and fee `0.0092516 USDT`.
- Verified Web status/report API and browser report view.
- Isolated test secret storage with `KRONOS_SECRET_STORE_PATH` so local tests
  do not read or mutate the user's ignored testnet credentials.
- Added `docs/TESTNET_E2E_ACCEPTANCE_20260509.md` and updated TODO, Project
  Status, Roadmap, Product Control Panel, Changelog, Memory, Decisions, and
  OpenSpec tasks.

Verification:
- Targeted pytest for validation, paper, CLI candidate selection, and coverage.
- `uv run pytest -m "not e2e"`: 591 passed, 5 deselected.
- `uv run mypy kronos cli`
- `python3 scripts/harness_memory_check.py`
- `git diff --check`
- Web API `GET /api/paper/status` and
  `GET /api/paper/runs/20260509T134805Z-paper/report`.
- Browser check on `http://127.0.0.1:3020`: dashboard showed completed/testnet
  run; report page showed order, fill, fee, and fill time; no current-page
  console errors.

Remaining risks:
- Testnet fill proves execution plumbing only. It must not be interpreted as
  strategy profitability or mainnet readiness.

## 2026-05-11 - v0.4.9 simulated user re-acceptance

Status: complete

Scope:
- Re-test v0.4.9 as a user instead of only trusting the 2026-05-09 acceptance
  document.

Actions completed:
- Confirmed CLI status path shows completed/testnet run
  `20260509T134805Z-paper`, order id `8693595272`, and `FILLED`.
- Confirmed paper preflight still passes and only prints the masked testnet API
  key suffix.
- Found a small UX gap: users could not confirm the installed Kronos version
  from the CLI. Added `kronos --version` / `kronos -V`, now returning `0.4.9`.
- Re-tested the Web workbench on a clean local backend/frontend pair. The
  dashboard paper card shows read-only testnet status and the report entry.
- Clicked the Web report entry; the report displays environment, run id, order
  id, `FILLED`, fill price, quantity, fee, fill time, and mainnet boundary.
- Checked the report at desktop and 390px mobile width; no current-page browser
  console errors or warnings.

Verification:
- `uv run kronos --version`
- `uv run kronos paper status --output-path reports/paper`
- `uv run kronos paper preflight --plan reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/paper_observation_plan.md --output-path reports/paper`
- `uv run pytest tests/integration/test_cli.py::test_cli_version_matches_package_version tests/integration/test_cli.py::TestPaperCLI::test_paper_mock_start_status_and_stop tests/integration/web/test_routes.py::test_paper_status_route_returns_latest_run_evidence tests/integration/web/test_routes.py::test_paper_run_report_route_redacts_secret_like_markdown tests/unit/execution/test_paper.py::test_min_exchange_notional_failure_writes_readable_status`
- `uv run ruff check cli/main.py tests/integration/test_cli.py tests/integration/web/test_routes.py tests/unit/execution/test_paper.py`
- `uv run mypy kronos cli`
- `npm --prefix web run typecheck`

## 2026-05-11 - v0.4.9 multi-persona simulated user acceptance

Status: complete

Scope:
- Re-run acceptance as a process, not just a successful-path spot check.
- Cover successful CLI/Web use, empty status, missing credentials, and
  reviewer safety questions.

Actions completed:
- Added `docs/KRONOS_V049_PERSONA_ACCEPTANCE_20260511.md`.
- Ran `kronos --version` and confirmed `0.4.9`.
- Ran normal `paper status` and confirmed completed/testnet run
  `20260509T134805Z-paper` with order id `8693595272` and `FILLED`.
- Ran normal `paper preflight` and confirmed it still passes with masked
  credential output.
- Ran isolated no-secret `paper status`; it gives a clear next step.
- Ran isolated no-secret `paper preflight`; it blocks on missing Binance
  testnet API Key / Secret.
- Ran a dedicated Web dashboard acceptance. The first pass found the testnet
  paper panel too low for a v0.4.9 first-glance user check.
- Moved the testnet paper panel to the top of the dashboard content area and
  changed the status badge from `completed` to `已完成`.
- Re-checked desktop and 390px mobile: desktop shows the panel and report
  entry in the first screen; mobile exposes the testnet module and boundary
  copy in the first screen; the report opens and console has 0 errors/warnings.
- Indexed the acceptance report from TODO, Project Status, Roadmap, Product
  Control Panel, Changelog, release doc, OpenSpec tasks, Memory, and Decisions.

Verification:
- `uv run kronos --version`
- `uv run kronos paper status --output-path reports/paper`
- `uv run kronos paper preflight --plan reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/paper_observation_plan.md --output-path reports/paper`
- isolated `KRONOS_SECRET_STORE_PATH` status and preflight checks
- Browser dashboard acceptance on `http://127.0.0.1:3025` at desktop and 390px
  mobile widths

Remaining risks:
- v0.4.9 passes, but the Web first screen should make the current version and
  acceptance object more obvious in v0.4.10.

## 2026-05-11 - v0.4.10 Agent Memory Control implementation

Status: complete, pending product review

Scope:
- Productize the repository-local Agent Harness as a Web-visible memory and
  handoff control surface.
- Preserve the read-only-first boundary and avoid adding a runtime dependency.
- Make the first screen explicit about current version, acceptance object,
  latest successful run, source docs, and next action.

Actions completed:
- Added `kronos/agent/memory_control/` with file-backed models, readers,
  redaction, drift checks, and handoff prompt generation.
- Added Web API routes under `/api/agent/memory/summary`,
  `/api/agent/memory/decisions`, `/api/agent/memory/handoff`, and
  `/api/agent/memory/check`.
- Added Web workbench sidebar entry `记忆`, an Agent memory page, and a
  dashboard v0.4.10 memory snapshot.
- Added unit and integration coverage for missing files, index drift, secret
  redaction, and Web summary responses.
- Added `docs/KRONOS_V0410_PERSONA_ACCEPTANCE_20260511.md`.
- Updated version docs, OpenSpec tasks, TODO, Project Status, Roadmap, Product
  Control Panel, README, Changelog, Memory, and Decisions to v0.4.10.

Verification:
- `uv run pytest tests/integration/web/test_routes.py tests/unit/agent/test_memory_control.py`
- `uv run ruff check kronos/agent/memory_control kronos/web/routes/memory.py kronos/web/app.py tests/unit/agent/test_memory_control.py tests/integration/web/test_routes.py`
- `uv run mypy kronos cli`
- `npm --prefix web run lint`
- `npm --prefix web run typecheck`
- `npm --prefix web run build`
- `python3 scripts/harness_memory_check.py`
- Browser acceptance on `http://127.0.0.1:3022`, including 390px narrow
  viewport; fixed one overflow issue from long English decision titles.

Remaining risks:
- v0.4.10 uses explicit rules and file-backed summaries only; semantic memory
  quality checks and automatic memory writes need separate future planning.
