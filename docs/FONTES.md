# Proposta de novas fontes de dados

Hoje o radar coleta de **YouTube** (via yt-dlp), **Steam**, **Kitsu** e **RSS**.
Esta proposta lista o que adicionar, por prioridade. Todas devolvem
`ReleaseCandidate` e passam pelo mesmo funil (dedupe → análise → *release gate*).

> Confirme os termos de uso e os limites de cada API antes de ativar em produção;
> várias exigem atribuição ou restringem uso comercial.

## Fase 1 — sem chave, alto retorno

| Fonte | Categoria | Acesso | O que traz | Esforço |
|---|---|---|---|---|
| **AniList** | anime, mangá | GraphQL público (`status: NOT_YET_RELEASED`) | Estreias com data, capa, popularidade; complementa o Kitsu | baixo |
| **Jikan (MyAnimeList)** | anime | REST público `/seasons/upcoming` | Temporada seguinte, notas e membros do MAL | baixo |
| **TVmaze** | séries | REST público (`/schedule/web`, `/shows`) | Estreias de séries/streaming com data exata | baixo |
| **YouTube via feed Atom** | todas | `youtube.com/feeds/videos.xml?channel_id=…` | Descoberta de vídeos **sem yt-dlp** (menos bloqueios); yt-dlp só para o que passar | médio |
| **MangaDex** | mangá | REST público | Lançamentos e adaptações anunciadas | baixo |
| **Wikipedia / Wikidata** | filmes, séries, jogos | SPARQL (`publication date` futura) | Calendário de estreias confirmado por fonte aberta | médio |

## Fase 2 — chave gratuita

| Fonte | Categoria | Acesso | O que traz | Esforço |
|---|---|---|---|---|
| **TMDB** | filmes, séries | REST (`/movie/upcoming`, `/tv/on_the_air`), chave grátis | Principal fonte de estreias de cinema e TV, com região (`BR`) | baixo |
| **Trakt** | filmes, séries | REST (calendários), client id | Calendário de estreias e popularidade | médio |
| **IGDB** | jogos | Twitch OAuth (client credentials) | Datas de lançamento por plataforma, hype count | médio |
| **RAWG** | jogos | REST, chave grátis | Jogos "coming soon" com plataformas e gêneros | baixo |
| **Reddit** (RSS por subreddit) | todas | `reddit.com/r/<sub>/.rss` | Anúncios e teasers antes da imprensa (`r/movies`, `r/anime`, `r/Games`) | baixo |

## Fase 3 — extras

- **GOG / Nintendo eShop / Epic**: páginas "em breve" (APIs não oficiais; avaliar fragilidade).
- **Feeds de estúdio**: A24, Studio Ghibli, Crunchyroll News, Nintendo Life, via `RSS_SOURCES`.
- **Saídas novas**: feed RSS/Atom e `.ics` (calendário) do radar, webhook para Discord/Slack/Matrix e ntfy, além do Telegram.

## Como plugar (contrato)

```python
# src/release_radar/sources/anilist.py
def fetch_anilist(client: httpx.Client, limit: int) -> list[ReleaseCandidate]:
    ...  # external_id="anilist:<id>", source="anilist", category="anime"
```

1. Criar o módulo em `sources/` e registrá-lo em `_build_fetchers` (`sources/__init__.py`).
2. Adicionar `<FONTE>_ENABLED` / `<FONTE>_LIMIT` em `config.py` e `.env.example`
   (e, se editável pelo painel, em `settings_store.py`).
3. Passar a data oficial em `upload_date`/`description`, já que datas explícitas das
   fontes têm prioridade sobre a LLM.
4. Testes com `httpx.MockTransport`, sem rede (veja `tests/test_sources_kitsu.py`).
5. Respeitar `net_guard`: apenas URLs públicas.

## Ordem sugerida

1. **TMDB + TVmaze** (cobrem filmes e séries, hoje o ponto mais fraco só com RSS/YouTube).
2. **AniList + Jikan** (anime com data e popularidade, reduz dependência do Kitsu).
3. **IGDB** (datas por plataforma para jogos).
4. **YouTube via Atom** (robustez) e **saídas** (RSS/iCal/webhooks).
