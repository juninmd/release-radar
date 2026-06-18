# Release Radar

Radar privado de lancamentos de filmes, series, jogos e animes.

Fluxo:

1. Busca trailers e anuncios em canais YouTube configurados.
2. Deduplica por `youtube_id`, URL e `content_hash` no PostgreSQL.
3. Captura descricao, thumbnail, metadados e, quando viavel, transcreve audio do trailer via Whisper do cluster.
4. Analisa titulo, descricao e transcricao via LiteLLM.
5. Publica no Telegram com trailer, sinopse, janela de lancamento, plataformas, leitura do trailer e resumo transcrito.

## Local

```bash
uv sync
copy .env.example .env
uv run release-radar run --dry-run --limit 3
uv run pytest
uv run ruff check src tests
```

## Cluster

Imagem: `ghcr.io/juninmd/release-radar:latest`

Servicos internos:

- Whisper: `http://whisper.ai.svc.cluster.local:9000`
- LiteLLM: `http://litellm.ai.svc.cluster.local:4000/v1`
- Postgres: secret gerenciado via ExternalSecret

Telegram usa o mesmo bot/chat do `nando-moura-analyzer` via propriedades SOPS compartilhadas.
