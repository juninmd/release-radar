# AGENTS.md

Release radar bot for upcoming releases (movies, series, games, anime): it collects, analyzes with an LLM, publishes to Telegram, and serves a web panel and a desktop widget.

## Stack
- Python 3.11+ (`uv`, hatchling), PostgreSQL. Package in `src/release_radar/`; CLI `release-radar` (`run`, `web`).
- Web panel: TypeScript in `frontend/src/app.ts`, compiled to `src/release_radar/static/app.js` (committed).
- Desktop: Tauri v2 + React in `desktop/` (Bun, Rust).

## Commands
- Setup: `uv sync --locked` and `cp .env.example .env`
- Lint and types: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
- Tests: `uv run pytest -q` (browser tests: `uv sync --locked --group browser` plus Chromium)
- Build: `uv build`
- Frontend (after editing the `.ts`): `cd frontend && npm ci && npm run check`, then commit `app.js`
- Desktop: `cd desktop && bun install --frozen-lockfile && bun run lint && bun test && bun run build`
- Desktop Rust: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` in `desktop/src-tauri`

## Structure
- `src/release_radar/`: pipeline, sources, analyzer, dedupe, release policy, Telegram bot, web panel
- `src/release_radar/sql/`: migrations
- `src/release_radar/static/app.js`: generated from `frontend/`
- `frontend/`: web panel source (TypeScript, vitest)
- `desktop/`: Tauri widget (React, Bun, Rust)
- `docs/FONTES.md`: how to add a new source
- `.github/workflows/`: `build.yml`, `desktop.yml`, `docker.yml`, `validate.yml`, `security.yml`

## Conventions
- Never commit `.env`, tokens or keys. Docs name variables only.
- Migrations are immutable once applied: add a new `NNNN_nome.sql` instead of editing one.
- Do not hand-edit `app.js` or lockfiles. Regenerate them.
- Tests must not touch the network or Telegram; use `httpx.MockTransport`.
- A new source follows `docs/FONTES.md`.
- Do not weaken the release gate (it only publishes confirmed future premieres), or the SSRF, XXE and CSRF protections.

## CI gates
- `build.yml`: ruff, mypy, frontend (`npm run check`), `app.js` up to date, pytest, `uv build`
- `desktop.yml`: lint, bun test, cargo fmt, clippy, test
- `validate.yml` and `security.yml`: reusable workflows from `juninmd/base-actions`
- `docker.yml`: publishes the image

<!-- base-actions-main-policy -->
## GitHub Actions — padrão obrigatório (@main)

- Referencie as actions internas sempre pelo branch, nunca por SHA:
  - `uses: juninmd/base-actions/<action>@main`
  - `uses: juninmd/base-actions/.github/workflows/<arquivo>.yml@main`
- Não fixe `@<sha>` em `juninmd/base-actions`: a atualização é centralizada no
  `main` e passa a valer no próximo run.
- PRs cujos checks não iniciam por billing/spending limit são mesclados pelo bot central
  `juninmd/base-actions/.github/workflows/auto-merge-billing-blocked.yml`.
  Para impedir o merge automático de um PR, aplique a label `do-not-merge`.
