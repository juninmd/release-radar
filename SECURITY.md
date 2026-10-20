# Política de segurança

## Reportar uma vulnerabilidade

**Não abra uma issue pública.** Use o botão
[*Report a vulnerability*](../../security/advisories/new) da aba *Security* do
repositório (GitHub Private Vulnerability Reporting). Respondemos assim que possível.

## O que o projeto já faz

- Segredos só por variáveis de ambiente (`.env` está no `.gitignore`; veja `.env.example`).
- Consultas SQL parametrizadas.
- Feeds RSS: DOCTYPE recusado (XXE), tamanho máximo e proteção contra **SSRF**
  (hosts internos, redirecionamentos e resolução DNS para IP privado são bloqueados).
- Painel em `127.0.0.1` por padrão; `/api/run` e `/api/settings` exigem
  `RELEASE_RADAR_API_TOKEN` fora de localhost.
- Cabeçalhos de segurança e CSP restritiva; erros genéricos na API (sem vazar conexão).
- Dependabot semanal (pip, npm, cargo e GitHub Actions).

## Ao hospedar sua instância

- Defina `RELEASE_RADAR_API_TOKEN` e coloque o painel atrás de HTTPS.
- Nunca versione `.env`, tokens do Telegram ou chaves de LLM.
- Ative *secret scanning* e *push protection* no repositório.

Versões suportadas: apenas a branch `main`.
