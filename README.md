# Release Radar

Um radar privado para descobrir filmes, séries, jogos e animes que ainda vão
estrear. O bot reúne anúncios de várias fontes, analisa o conteúdo e publica os
links aprovados no Telegram. O painel web organiza essas publicações para você
encontrar algo para assistir, ler ou acompanhar.

## O que você encontra no painel

- **YouTube:** vídeos e trailers, incluindo links do YouTube encontrados em RSS.
- **Artigos:** notícias e anúncios editoriais.
- **Páginas oficiais:** páginas de jogos na Steam e de animes no Kitsu.
- Busca por título ou fonte, sem exigir acentos, e filtros por categoria e disponibilidade.
- Datas legíveis, detalhes completos e botões para assistir, ler ou abrir a página.
- Atualização sem recarregar a página e nova tentativa quando a conexão falhar.

O painel mostra os **120 links mais recentes publicados pelo bot**. Os filtros
atuam nessa seleção. Publicações anteriores continuam no histórico e podem
aparecer como **Já disponível** quando a estreia passar; isso não gera uma nova
mensagem no Telegram. **A confirmar** significa que uma publicação antiga não
tem dados suficientes para determinar a disponibilidade atual.

As capturas de [desktop, celular e outros estados](docs/UI_PREVIEW.md) usam
dados fictícios e mostram a interface real executada em Chromium.

## App desktop

Há também um app de desktop em [`desktop/`](desktop/README.md) (Tauri v2 +
React): uma janela compacta sempre no topo, com ícone na bandeja, notificações de
novidades, atalho global `Ctrl+Shift+R`, skins e atualização assinada. Ele
**consome a API publicada** pelo painel — não fala com o PostgreSQL nem com o
Telegram — e permite disparar uma rodada do bot e ajustar fontes e limites pela
própria interface. O painel web continua igual.

Para servir essa API em rede, defina `RELEASE_RADAR_API_TOKEN` e suba o painel
com `--host 0.0.0.0` (veja [.env.example](.env.example) e
[desktop/README.md](desktop/README.md)). Sem o token, uma exposição fora de
`localhost` passa a recusar `/api/run` e `/api/settings` com 403 até que você
defina o token ou `RELEASE_RADAR_ALLOW_ANON=true`.

## Como o bot decide o que publicar

1. Coleta links das fontes configuradas, alternando as fontes para que nenhuma monopolize a rodada.
2. Evita repetir itens com o mesmo identificador, URL ou conteúdo já registrado no PostgreSQL.
3. Enriquece os metadados e, quando habilitado, transcreve trailers do YouTube.
4. Analisa se o link anuncia uma obra relevante que ainda vai estrear.
5. Confere a data e a disponibilidade antes de publicar no Telegram.

Uma obra marcada como já lançada, ou com estreia hoje ou no passado, **não é
publicada**. Para publicar, o bot exige uma data futura ou uma confirmação de
que a obra ainda está por vir. Sem evidência, guarda o motivo
`Estreia futura nao confirmada`. Apenas conter “trailer” no título não basta.

Datas explícitas vindas das fontes têm prioridade sobre a análise. Sem a chave
da análise, Steam e Kitsu ainda fornecem a indicação de obra futura;
YouTube e RSS precisam de evidência adicional. Essa regra reduz as postagens
incertas, mas continua dependendo da qualidade dos metadados e da análise.

> A deduplicação atual reconhece identificadores, URLs e conteúdo. Links
> diferentes para a mesma obra ainda podem ser registrados separadamente.

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
uv run pytest -q
uv build
```

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

A CI do PR executa lint, testes com PostgreSQL e Chromium, gera o pacote
distribuível e guarda as capturas da UI como artefato.

## Container e cluster

A imagem existente é `ghcr.io/juninmd/release-radar:latest`. O comando padrão
executa uma rodada do bot. Para servir o painel em outro processo/container,
use `uv run release-radar web --host 0.0.0.0 --port 8765`, com as mesmas
variáveis de conexão ao PostgreSQL.

O painel expõe: `GET /api/releases` (os links publicados, aberto),
`GET /api/health`, `POST`/`GET /api/run` (dispara e acompanha uma rodada) e
`GET`/`PUT /api/settings` (fontes e limites). Com `RELEASE_RADAR_API_TOKEN`
definido, tudo menos `/api/releases` e `/api/health` exige
`Authorization: Bearer <token>`; sem o token, fora de `localhost` essas rotas de
escrita respondem 403 (use `RELEASE_RADAR_ALLOW_ANON=true` para liberar). Os
ajustes salvos ficam na tabela `radar_settings` e sobrescrevem apenas as fontes e
limites permitidos.

Os valores padrão dos serviços internos estão no [.env.example](.env.example).
O painel não expõe tokens de Telegram, chaves da análise ou transcrições na API.
