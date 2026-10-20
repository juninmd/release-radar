# Prévia do painel do Release Radar

As imagens desta pasta foram capturadas em 30/09/2026 a partir da UI real servida por `release_radar.web`, com o navegador Chromium e os dados fictícios definidos em `tests/test_frontend.py`. Elas mostram o painel em desktop, celular e os estados de carregamento, vazio e falha da API.

## Telas

### Computador

![Painel no computador, com filtros e cards separados por tipo de link](previews/desktop.png)

### Celular

<img src="previews/mobile.png" alt="Painel no celular, com filtros e cards em uma coluna" width="390">

| Estado | Evidência |
| --- | --- |
| Conteúdo carregado em desktop | [desktop.png](previews/desktop.png) |
| Conteúdo carregado em 390px | [mobile.png](previews/mobile.png) |
| Carregando | [loading.png](previews/loading.png) |
| Nenhum resultado | [empty.png](previews/empty.png) |
| Falha ao carregar | [error.png](previews/error.png) |

O painel separa os destinos com os filtros `YouTube`, `Artigos` e `Páginas oficiais`. Os cards exibem a situação da estreia (`Vai estrear`, `Já disponível` ou `A confirmar`) e oferecem busca, categoria, disponibilidade, detalhes e o link de destino. A tela móvel foi verificada sem rolagem horizontal.

## Captura da API

O endpoint real foi executado contra o PostgreSQL isolado de testes, usando um schema temporário exclusivo que foi removido ao final. Os registros usados são fictícios e foram publicados apenas nesse banco de validação.

- [GET /api/releases — 200](previews/api-example.json)
- [GET /api/releases — 503](previews/api-error-example.json)

O retorno aplica o limite de 120 itens e entrega somente itens com status `posted`; o erro 503 não expõe detalhes da conexão.

## CLI capturada

Os comandos abaixo foram executados com as fontes YouTube/RSS vazias, Steam/Kitsu desativados, tokens vazios e conexão apontando somente para o PostgreSQL isolado de validação. Nenhuma fonte externa ou Telegram foi chamado.

```console
$ release-radar --help
usage: release-radar [-h] {run,web} ...

positional arguments:
  {run,web}
    run       Busca, analisa e publica anúncios de estreias futuras
    web       Inicia o painel de links publicados

options:
  -h, --help  show this help message and exit
```

```console
$ release-radar run --dry-run --limit 3
[09/30/26 01:18:59] INFO     Discovered 0 candidates             pipeline.py:69
      Resultado da busca · teste a seco
│ Resultado                     │ Quantidade │
│ Links encontrados             │          0 │
│ Novos links registrados       │          0 │
│ Itens analisados              │          0 │
│ Publicados no Telegram        │          0 │
│ Já encontrados anteriormente  │          0 │
│ Sem anúncio de estreia        │          0 │
│ Já lançados                   │          0 │
│ Estreia futura não confirmada │          0 │
│ Falhas de processamento       │          0 │
└───────────────────────────────┴────────────┘
```

```console
$ release-radar run --dry-run --limit 3 --json
[09/30/26 01:19:00] INFO     Discovered 0 candidates             pipeline.py:69
{"discovered": 0, "reserved": 0, "analyzed": 0, "posted": 0, "skipped_existing": 0, "skipped_not_release": 0, "skipped_released": 0, "skipped_unconfirmed": 0, "failed": 0}
```

O teste de navegador foi executado com `PLAYWRIGHT_CHROMIUM_EXECUTABLE` apontando para o Chromium local e `RELEASE_RADAR_SCREENSHOT_DIR=docs/previews`: `4 passed in 20.70s`.

As linhas de log acima vêm de `stderr`; em `--json`, `stdout` contém somente o objeto JSON. A suíte completa final, incluindo PostgreSQL, CLI e navegador, passou com **73 testes**.
