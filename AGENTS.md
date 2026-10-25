# AGENTS.md

Bot de radar de estreias (filmes, séries, jogos, animes): coleta, análise por LLM, publicação no Telegram, painel web e widget desktop.

## Stack
- Python 3.11+ (`uv`, hatchling), PostgreSQL, `src/release_radar/`; CLI `release-radar` (`run`, `web`).
- Painel: TypeScript em `frontend/src/app.ts`, compilado para `src/release_radar/static/app.js` (versionado).
- Desktop: Tauri v2 + React em `desktop/` (Bun, Rust).

## Comandos
- Setup: `uv sync --locked` e `cp .env.example .env`
- Lint/tipos: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
- Testes: `uv run pytest -q` (navegador: `uv sync --locked --group browser` + Chromium)
- Build: `uv build`
- Frontend (após editar o `.ts`): `cd frontend && npm ci && npm run check` e commitar o `app.js`
- Desktop: `cd desktop && bun install --frozen-lockfile && bun run lint && bun test && bun run build`; Rust: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` em `desktop/src-tauri`

## Gates de CI
`build.yml` (ruff, mypy, frontend, `app.js` em dia, pytest, `uv build`), `desktop.yml` (lint, bun test, cargo fmt/clippy/test), `validate.yml` e `security.yml` (reusables de `juninmd/base-actions`), `docker.yml` (publica a imagem).

## Não fazer
- Não versionar `.env`, tokens ou chaves; só nomes de variáveis em docs.
- Não editar migração já aplicada em `src/release_radar/sql/`; crie `NNNN_nome.sql`.
- Não editar `app.js` à mão nem lockfiles; regenere.
- Teste não acessa rede nem Telegram (use `httpx.MockTransport`); nova fonte: ver `docs/FONTES.md`.
- Não afrouxe o release gate (só publica estreia futura confirmada) nem as proteções SSRF/XXE/CSRF.

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