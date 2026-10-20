# Contribuindo

1. `uv sync --locked` e copie `.env.example` para `.env`.
2. Antes de abrir o PR: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q`.
3. Nova fonte de dados? Veja [docs/FONTES.md](docs/FONTES.md): uma função `fetch_*`
   em `src/release_radar/sources/` que devolve `ReleaseCandidate`, registrada em
   `sources/__init__.py`, com testes sem rede (use `httpx.MockTransport`).
4. Nunca inclua segredos, URLs internas ou dados reais de usuários em código, testes ou capturas.
