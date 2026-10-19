from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

import psycopg2
from rich.console import Console
from rich.table import Table

from .config import get_settings
from .db import init_db
from .logging_setup import configure_logging
from .pipeline import run_sync


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="release-radar")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="Busca, analisa e publica anúncios de estreias futuras")
    run.add_argument("--limit", type=positive_int, default=None, help="Máximo de itens analisados")
    run.add_argument("--dry-run", action="store_true", help="Testa sem gravar itens ou publicar")
    run.add_argument("--verbose", action="store_true", help="Exibe logs detalhados")
    run.add_argument("--json", action="store_true", help="Exibe o resultado em JSON para automação")
    web = sub.add_parser("web", help="Inicia o painel de links publicados")
    web.add_argument("--host", default="127.0.0.1", help="Endereço de escuta (padrão: local)")
    web.add_argument(
        "--port", type=positive_int, default=8765, help="Porta do painel (padrão: 8765)"
    )
    args = parser.parse_args()

    if args.command == "web":
        from .web import serve

        if args.port > 65535:
            parser.error("a porta deve estar entre 1 e 65535")
        dsn = get_settings().postgres_dsn
        try:
            init_db(dsn)
        except psycopg2.Error:
            parser.exit(1, "Não foi possível conectar ao PostgreSQL. Confira POSTGRES_* no .env.\n")
        serve(dsn, args.host, args.port)
        return

    if args.command != "run":
        parser.print_help()
        return

    settings = get_settings()
    configure_logging(verbose=args.verbose, json_logs=settings.json_logs)
    stats = run_sync(settings, limit=args.limit, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(asdict(stats), ensure_ascii=False))
        return
    table = Table(title="Resultado da busca" + (" · teste a seco" if args.dry_run else ""))
    table.add_column("Resultado")
    table.add_column("Quantidade", justify="right")
    labels = {
        "discovered": "Links encontrados",
        "reserved": "Novos links registrados",
        "analyzed": "Itens analisados",
        "posted": "Publicados no Telegram",
        "skipped_existing": "Já encontrados anteriormente",
        "skipped_not_release": "Sem anúncio de estreia",
        "skipped_released": "Já lançados",
        "skipped_unconfirmed": "Estreia futura não confirmada",
        "skipped_clip": "Clipes e comentários (não são trailers)",
        "skipped_duplicate": "Trailer de obra já publicada",
        "failed": "Falhas de processamento",
    }
    for key, label in labels.items():
        table.add_row(label, str(getattr(stats, key)))
    for source, errors in sorted(stats.source_errors.items()):
        table.add_row(f"Falhas na fonte {source}", str(errors))
    table.caption = f"{stats.duration_seconds:.1f}s no total, {stats.llm_seconds:.1f}s na análise"
    if stats.aborted:
        table.caption += f" · rodada interrompida: {stats.aborted}"
    Console().print(table)


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("informe um número inteiro positivo") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("informe um número inteiro maior que zero")
    return parsed
