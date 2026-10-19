# Release Radar

Um radar privado para descobrir filmes, séries, jogos e animes que ainda vão
estrear. O bot reúne anúncios de várias fontes, analisa o conteúdo e publica os
links aprovados no Telegram. O painel web organiza essas publicações para você
encontrar algo para assistir, ler ou acompanhar.

## O que você encontra no painel

- **YouTube:** trailers, teasers e anúncios (selo **Trailer**, **Teaser** ou
  **Anúncio**), incluindo links do YouTube encontrados em RSS. Clipes, cenas,
  bastidores, entrevistas e reações não aparecem, e cada obra mostra só o trailer
  mais recente.
- **Artigos:** notícias e anúncios editoriais.
- **Páginas oficiais:** páginas de jogos na Steam e de animes no Kitsu.
- Busca por título ou fonte, sem exigir acentos, e filtros por categoria e disponibilidade.
- Datas legíveis, detalhes completos e botões para assistir, ler ou abrir a página.
- Ordenação por **Estreia mais próxima** e o aviso **Novo** para o que foi publicado nas últimas 48 horas.
- Atualização sem recarregar a página e nova tentativa quando a conexão falhar.

O painel mostra os **120 links mais recentes publicados pelo bot**. Os filtros
atuam nessa seleção. Publicações anteriores continuam no histórico e podem
aparecer como **Já disponível** quando a estreia passar; isso não gera uma nova
mensagem no Telegram. **A confirmar** significa que uma publicação antiga não
tem dados suficientes para determinar a disponibilidade atual.

As capturas de [desktop, celular e outros estados](docs/UI_PREVIEW.md) usam
dados fictícios e mostram a interface real executada em Chromium.

## Como o bot decide o que publicar

1. Coleta links das fontes configuradas, alternando as fontes para que nenhuma monopolize a rodada.
2. Evita repetir itens com o mesmo identificador, URL ou conteúdo já registrado no PostgreSQL.
   Para vídeos, também reconhece a **mesma obra** por trás de vários trailers
   ("Official Trailer", "Final Trailer #2", "TV Spot"...) e publica só o primeiro.
   Itens já conhecidos nem chegam ao yt-dlp.
3. Enriquece os metadados e, quando habilitado, transcreve trailers do YouTube.
4. Descarta **clipes e comentários** (cena, clipe, featurette, bastidores,
   entrevista, reação, review) antes de transcrever ou chamar a LLM; a análise
   também classifica o vídeo em `content_type` e o título de clipe sempre vence.
5. Analisa se o link anuncia uma obra relevante que ainda vai estrear.
6. Confere a data e a disponibilidade antes de publicar no Telegram.

Uma obra marcada como já lançada, ou com estreia hoje ou no passado, **não é
publicada**. Para publicar, o bot exige uma data futura ou uma confirmação de
que a obra ainda está por vir. Sem evidência, guarda o motivo
`Estreia futura nao confirmada`. Apenas conter “trailer” no título não basta.

Datas explícitas vindas das fontes têm prioridade sobre a análise. Sem a chave
da análise, Steam e Kitsu ainda fornecem a indicação de obra futura;
YouTube e RSS precisam de evidência adicional. Essa regra reduz as postagens
incertas, mas continua dependendo da qualidade dos metadados e da análise.

> A identificação da obra compara o título (sem "trailer", "teaser", canal e
> similares) e, depois da análise, o título original informado pela LLM. Títulos
> muito diferentes para a mesma obra ainda podem passar; artigos e páginas
> oficiais não entram nessa regra. Publicações antigas ganham a chave
> automaticamente na próxima inicialização do banco (coluna `work_key`,
> reversível com `DROP COLUMN`).

## Executar localmente

Você precisa de Python 3.11+, [uv](https://docs.astral.sh/uv/) e PostgreSQL.
Para transcrever áudio, também precisa de ffmpeg e de um serviço Whisper.

```powershell
uv sync --locked
Copy-Item .env.example .env
```

Preencha o `.env` com a conexão `POSTGRES_*`. Para analisar links do YouTube e
artigos, configure `LLM_BASE_URL`, `LLM_MODEL` e `LLM_API_KEY`. Para publicar,
configure também `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.

Comece com um teste sem publicação:

```powershell
uv run release-radar run --dry-run --limit 3
```

O teste a seco inicializa as tabelas, mas **não registra os itens, não salva
análises e não envia mensagens**. Isso preserva a próxima rodada real.
O resultado explica quantos links foram encontrados, analisados, rejeitados
por já terem sido lançados ou retidos por falta de confirmação.

Para publicar uma rodada ou abrir o painel:

```powershell
uv run release-radar run --limit 12
uv run release-radar web
```

Abra **http://127.0.0.1:8765**. O painel também inicializa as tabelas quando a
base ainda estiver vazia. `--port 9000` troca a porta. Ele escuta apenas em
localhost por padrão; para acesso remoto, configure autenticação no proxy
antes de usar `--host 0.0.0.0`.

Use `release-radar run --help` para ver os parâmetros ou `--json` para obter
o resultado em JSON em uma automação.

## Fontes e configuração

| Fonte | Categoria | Configuração | Como funciona |
|---|---|---|---|
| YouTube | Todas | `YOUTUBE_SOURCES`, `SOURCE_LIMIT` | Canais configurados; única fonte com transcrição de áudio |
| Steam | Jogos | `STEAM_ENABLED`, `STEAM_LIMIT`, `STEAM_COUNTRY`, `STEAM_LANGUAGE` | Jogos classificados pela loja como “em breve” |
| Kitsu | Animes | `KITSU_ENABLED`, `KITSU_LIMIT` | Animes classificados como `upcoming` |
| RSS | Por feed | `RSS_SOURCES`, `RSS_LIMIT` | RSS 2.0, RDF e Atom |

Use `categoria|endereço` nas listas de fontes, separando entradas por vírgula.
As categorias aceitas são `movies`, `series`, `games` e `anime`.
Veja o [.env.example](.env.example) para os demais limites e serviços.

O banco mantém os IDs antigos do YouTube e usa prefixos nas demais fontes:
`steam:`, `kitsu:` e `rss:`. A inicialização migra bases antigas com a coluna
`youtube_id` para `external_id` e adiciona `source`, preservando o histórico.

## Testes e validação

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
uv build
```

O painel é escrito em TypeScript (`frontend/src/app.ts`) e compilado para
`src/release_radar/static/app.js`, que é versionado. Depois de editar o `.ts`:

```powershell
cd frontend
npm ci
npm run check   # typecheck, testes (vitest) e build
```

A CI falha se o `app.js` commitado divergir do que o `app.ts` gera.

Para testar o navegador, instale o grupo opcional e o Chromium:

```powershell
uv sync --locked --group browser
uv run --group browser playwright install chromium
uv run --group browser pytest tests/test_frontend.py -q
```

Os testes de navegador usam dados fictícios e não acessam fontes nem Telegram.
Defina `RELEASE_RADAR_SCREENSHOT_DIR` para guardar as capturas. Para usar um
Chromium já instalado, defina `PLAYWRIGHT_CHROMIUM_EXECUTABLE` com seu caminho.

Os testes de banco aceitam `RELEASE_RADAR_TEST_DSN` e criam um schema isolado
por teste. Use uma base destinada a testes. Sem essa variável, tentam usar
`pgserver` quando instalado; sem ambos, os testes de PostgreSQL são pulados.
Sem o grupo `browser`, os testes de navegador também são pulados.

A CI do PR executa lint, formatação, `mypy`, o check do frontend (incluindo a
verificação do `app.js` gerado), testes com PostgreSQL e Chromium, gera o pacote
distribuível e guarda as capturas da UI como artefato. Cada push na `main` roda
os mesmos checks antes de publicar a imagem Docker (`docker.yml` reutiliza o
workflow `build.yml`).

## Banco de dados e migrações

O esquema é versionado em `src/release_radar/sql/NNNN_nome.sql`. Na inicialização
(`run` e `web`), as migrações pendentes são aplicadas em ordem, cada uma em sua
transação e protegidas por um advisory lock, e registradas em `schema_migrations`.
Para mudar o esquema, crie o próximo arquivo numerado (nunca edite um já aplicado).
As migrações iniciais são idempotentes e adotam bases criadas antes do runner.

## Resiliência e observabilidade

- **Retry com backoff** (exponencial, com jitter e respeito a `Retry-After`) nas
  fontes HTTP (Steam, Kitsu, RSS), no Whisper e na LLM. Só falhas transitórias
  (rede, timeout, 429 e 5xx) são repetidas.
- **Circuit breaker por rodada:** três falhas seguidas do Whisper/download
  desligam a transcrição pelo resto da rodada; três falhas seguidas da LLM
  interrompem a rodada (`aborted: llm_unavailable`) em vez de marcar vários
  itens como falhos.
- **Estatísticas por rodada** (`--json` ou o log `Run finished`): candidatos por
  fonte, falhas por fonte (`source_errors`), transcrições, tempo total e tempo na LLM.
- `LOG_FORMAT=json` emite uma linha JSON por log (stderr), pronta para
  Loki/Datadog/CloudWatch; o padrão continua legível no terminal.

## Painel (API)

`GET /api/releases` usa um pool de conexões, cache de 15 s (com *single-flight*;
se o banco cair, serve o último resultado por até 5 min), limite de requisições
por IP (60 de rajada, 2/s; responde `429` com `Retry-After`) e leitura paginada
até completar os 120 itens mesmo com muitos clipes ocultos. Os arquivos
estáticos usam `ETag` e `Cache-Control: no-cache` (um deploy novo aparece na
hora e, sem mudança, o navegador recebe `304`). `GET /healthz` confere o banco.
O painel **não tem autenticação**: se sair da máquina local, coloque-o atrás de
um proxy com autenticação (por trás de proxy, o limite vale por IP do proxy).

## Container e cluster

A imagem existente é `ghcr.io/juninmd/release-radar:latest`. Ela roda sem
privilégios (usuário `radar`), com a versão do `uv` fixada. O comando padrão
executa uma rodada do bot. Para servir o painel em outro processo/container,
use `release-radar web --host 0.0.0.0 --port 8765`, com as mesmas variáveis de
conexão ao PostgreSQL; `GET /healthz` serve de probe de liveness/readiness.

Para rodar tudo localmente, o `docker-compose.yml` sobe PostgreSQL e painel
(`docker compose up -d db web`, em http://127.0.0.1:8765) e roda uma rodada do
bot sob demanda (`docker compose run --rm bot`).

Os valores padrão dos serviços internos estão no [.env.example](.env.example).
O painel não expõe tokens de Telegram, chaves da análise ou transcrições na API.
