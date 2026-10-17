# Release Radar · App desktop

App de desktop (Tauri v2 + React) que mostra as novidades do radar em uma janela
compacta, sempre no topo, com ícone na bandeja, notificações e atalho global.
**Ele consome a API publicada pelo seu cluster** — não fala com o PostgreSQL nem
com o Telegram, e o token de acesso nunca chega ao webview: só o processo Rust
conversa com a rede.

O painel web (`release-radar web`) continua igual; este app é uma segunda forma
de olhar os mesmos dados.

## O que ele faz

- **Novidades:** os 120 links publicados pelo bot, com os mesmos filtros do
  painel web (tipo, categoria, disponibilidade, busca sem acentos) e os mesmos
  cards (YouTube, artigos e páginas oficiais).
- **Widget:** janela sem moldura ancorada no canto inferior direito, com
  **sempre no topo**, mostrar/ocultar por bandeja e atalho global (padrão
  `Ctrl+Shift+R`, editável nos Ajustes). Se a tecla pedida já estiver ocupada por
  outro programa, o app tenta sozinho `Ctrl+Alt+D`, `Ctrl+Shift+Space` e
  `Ctrl+Alt+R`, e mostra qual ficou ativo.
- **Notificações:** ao detectar links novos, avisa pelo sistema e marca um sino
  no cabeçalho com a lista de novidades.
- **Rodada do bot:** "Buscar novidades agora" dispara o pipeline no cluster e
  acompanha o resultado (encontrados, analisados, publicados…).
- **Fontes e limites:** edita os ajustes que a API expõe (canais, feeds, limites,
  Steam/Kitsu) sem mexer no `.env`.
- **Skins:** Radar (escuro), Claro e Seguir o sistema.
- **Atualizações:** verifica e instala a nova versão assinada pela chave do
  projeto, com um clique.

## Requisitos

- A API do Release Radar acessível (o painel servido com `release-radar web
  --host 0.0.0.0`, atrás do seu ingresso/HTTPS).
- Para desenvolver: [Bun](https://bun.sh) ≥ 1.2, Rust estável ≥ 1.77 e as
  [dependências do Tauri v2](https://v2.tauri.app/start/prerequisites/) do sistema.

## Configurar a API

No cluster, sirva a API e defina um token antes de expô-la:

```bash
export RELEASE_RADAR_API_TOKEN="um-segredo-longo"
uv run release-radar web --host 0.0.0.0 --port 8765
```

Com o token definido, `POST /api/run`, `GET/PUT /api/settings` e `GET /api/run`
exigem `Authorization: Bearer <token>`; `GET /api/releases` e `GET /api/health`
seguem abertos. Sem token, esses endpoints ficam abertos para quem alcançar a
porta — o servidor avisa no log quando isso acontece fora de localhost.

No app, abra **Ajustes → Conexão e app** e informe o endereço
(ex.: `https://radar.exemplo.com`) e o token. Use **Testar conexão** para
confirmar.

## Testar sem um cluster

Há um script que sobe um PostgreSQL efêmero, semeia lançamentos fictícios e
serve a API em `http://127.0.0.1:8765` (sem fontes externas, sem Telegram):

```bash
uv run --with pgserver python desktop/scripts/local_api.py
```

Depois aponte o app em **Ajustes → Conexão e app** para `http://127.0.0.1:8765`
(deixe o token vazio) e use **Testar conexão**. Para parar, encerre o script.

## Desenvolver

```bash
bun install
bun run tauri:dev          # app com recarga rápida
bun run lint && bun test   # tipos e testes de UI (lógica pura)
bun run build              # tsc + vite -> dist/
cd src-tauri && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

Para testar a interface no navegador, sem o Tauri, aponte `VITE_API_BASE` para a
API e rode `bun run dev` — o Vite cria um proxy `/api` e as chamadas de leitura
funcionam (as ações de escrita, como disparar a rodada, exigem o app instalado).

Duas observações de plataforma, medidas no Windows:

- A janela nasce com `visible: true` no `tauri.conf.json` e é **ancorada no canto
  no setup**, reafirmada no primeiro carregamento. Criar a janela oculta e chamar
  `show()` depois (setup, `on_page_load` ou comando) **não** a torna visível no
  Windows; por isso o config declara a janela visível.
- O `devCsp` é proposital e amplamente permissivo: o preâmbulo do Vite + React
  Refresh não passa no `csp` estrito. Ele vale **só** para o servidor de
  desenvolvimento — o `csp` de produção continua fechado, sem origem remota.


## Gerar o instalador

```bash
bun run tauri:build        # instalador da plataforma atual
```

As atualizações automáticas só instalam pacotes assinados. Para uma release
assinada, use a configuração extra do updater com a chave privada em ambiente:

```bash
TAURI_SIGNING_PRIVATE_KEY=... bun run tauri:build -- --config src-tauri/tauri.updater.conf.json
```

A chave pública correspondente está em `src-tauri/tauri.conf.json`
(`plugins.updater.pubkey`). **Nunca** faça commit da chave privada nem da senha.

## Ícone

A arte base é gerada sem dependências do app e serve de entrada para o CLI do
Tauri:

```bash
uv run --with pillow python scripts/make_icon.py   # escreve app-icon.png
bun x tauri icon app-icon.png                      # regenera src-tauri/icons
```

## Como as peças se ligam

```text
src/                     React (uma pasta por assunto)
  lib/api.ts             único lugar que chama invoke(); tipos do IPC aqui
  lib/useRadar.ts        estado, polling e detecção de novidades
  lib/{format,filters,newItems,theme,updater}.ts   lógica pura + testes ao lado
  components/            Header, Filters, ReleaseCard, SettingsPanel, RunPanel...
src-tauri/src/
  lib.rs                 plugins, bandeja, atalho global, estado inicial
  config.rs              ajustes locais (endereço, token, skin, atalho) em disco
  shortcut.rs            registro do atalho global com alternativas livres
  api.rs                 cliente HTTP do radar (reqwest) e comandos de leitura/escrita
  commands.rs            janela, notificação, link externo, autostart
  tray.rs, window.rs     bandeja e ancoragem/visibilidade da janela
```

O token fica apenas no arquivo de configuração do app
(`%APPDATA%\com.junin.release-radar\config.json`); a interface recebe no máximo
um `hasToken`. Links externos só abrem se forem `http(s)://`.
