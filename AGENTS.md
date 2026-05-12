# Repository Guidelines

## Persistent Agent Harness
Before planning, editing, or reporting current project state, load the
repository-local memory stack:

1. `MEMORY.md` — durable project memory, lessons, and handoff state.
2. `DECISIONS.md` — architecture/product/process decisions and rejected
   alternatives.
3. `docs/agent-harness/PROGRESS_LOG.md` — recent harness and handoff progress.
4. `TODO.md`, `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, and
   `docs/PRODUCT_CONTROL_PANEL.md` — current product truth.

Do not rely on chat history alone. If a change creates durable knowledge, update
the appropriate memory file before final handoff. Never store secrets, raw API
keys, passwords, exchange credentials, or private tokens in memory files.

## Version Planning Gate
Before starting development for any new version, create and index the full
development plan first:

1. `docs/RELEASE_<version>_<topic>.md` with product goal, scope, non-goals,
   risks, tests, and completion criteria.
2. `openspec/changes/<change-id>/proposal.md`, `design.md`, `tasks.md`, and
   `specs/*/spec.md`.
3. Index links in `TODO.md`, `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, and
   `docs/PRODUCT_CONTROL_PANEL.md`.

Do not implement version work from a bare TODO item unless the user explicitly
asks for an emergency patch.

## Project Structure & Module Organization
`kronos/` contains the application code, organized by domain: `data/` for ingestion and storage, `factor/` for factor definitions and materialization, and placeholders such as `execution/`, `risk/`, and `portfolio/` for later phases. `cli/main.py` exposes the Typer-based `kronos` CLI. Runtime config lives in `configs/` (`dev.toml`, `backtest.toml`). Tests are split into `tests/unit`, `tests/integration`, and `tests/e2e`. Planning and design records live under `openspec/changes/`, with broader project docs in `docs/`.

## Build, Test, and Development Commands
Use `uv` for local development.

- `uv sync --dev`: create/update the Python 3.12 environment with dev tools.
- `uv run kronos data status --config configs/dev.toml`: run the CLI against local dev config.
- `uv run pytest`: run the full test suite.
- `uv run pytest -m "not e2e"`: run unit and integration tests only.
- `uv run pytest --cov=kronos --cov-report=term-missing`: verify the 80% coverage floor.
- `uv run ruff check . && uv run ruff format .`: lint and format the repo.
- `uv run mypy kronos cli`: run strict type checks.

## Coding Style & Naming Conventions
Target Python 3.12, 4-space indentation, and a 100-character line length. Ruff enforces import order and core lint rules; mypy runs in strict mode, so new functions should be fully typed. Use `snake_case` for modules, functions, and variables, `PascalCase` for classes and Pydantic models, and `UPPER_SNAKE_CASE` for constants. Keep CLI wiring in `cli/`; place reusable business logic in `kronos/`.

## Testing Guidelines
Pytest is the test runner, with `pytest-cov` for coverage and Hypothesis available for property tests. Name test files `test_*.py` and mirror the code area they cover, for example `tests/unit/test_sync.py`. Prefer unit tests for pure transformations, integration tests for CLI/storage flows, and `tests/e2e` for acceptance scenarios. Maintain at least 80% coverage for `kronos/`.

## Commit & Pull Request Guidelines
Recent history uses concise Conventional Commit subjects such as `feat: add Binance USDM adapter...`. Keep commits focused and imperative. Pull requests should summarize the user-visible change, note any config or data-layout impact, link the relevant issue or OpenSpec change, and include verification output for `ruff`, `mypy`, and `pytest`.

## Security & Configuration Tips
Do not commit secrets or exchange credentials. Keep local overrides in TOML config files under `configs/`, and treat generated market data as runtime state, not source-controlled assets.
