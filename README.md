# Release Radar

Radar privado de lancamentos de filmes, series, jogos e animes.

Fluxo:

1. Busca trailers e anuncios em canais YouTube configurados.
2. Complementa com fontes sem API key: Steam (jogos "em breve"), Kitsu (animes anunciados) e feeds RSS oficiais/editoriais.
3. Intercala as fontes por rodada para que nenhuma monopolize o `max_items_per_run`.
4. Deduplica por `external_id`, URL e `content_hash` no PostgreSQL.
5. Captura descricao, thumbnail, metadados e, quando viavel, transcreve audio do trailer via Whisper do cluster (so YouTube).
6. Analisa titulo, descricao e transcricao via LiteLLM.
7. Publica no Telegram com trailer, sinopse, janela de lancamento, plataformas, leitura do trailer e resumo transcrito.

## Fontes

| Fonte | Categoria | Config | Observacao |
|---|---|---|---|
| YouTube | todas | `youtube_sources`, `source_limit` | unica fonte com transcricao de audio |
| Steam | games | `steam_enabled`, `steam_limit`, `steam_country`, `steam_language` | busca `popularcomingsoon` + `appdetails`, sem key |
| Kitsu | anime | `kitsu_enabled`, `kitsu_limit` | animes `upcoming` por audiencia, sem key |
| RSS | por feed | `rss_sources` (`categoria\|url`), `rss_limit` | RSS 2.0, RDF e Atom via stdlib |

AniList e Jikan/MyAnimeList foram descartados: a API do AniList esta desativada (HTTP 403) e a do Jikan
responde 504 desde o upstream. Ids do YouTube seguem crus no banco; as demais fontes usam prefixo
(`steam:`, `kitsu:`, `rss:`), entao itens ja publicados nao sao repostados.

`init_db` migra bases antigas renomeando `youtube_id` para `external_id` e adicionando `source`.
Rollback: `ALTER TABLE release_items RENAME COLUMN external_id TO youtube_id` (idem em `release_events`)
e `ALTER TABLE release_items DROP COLUMN source`.

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
