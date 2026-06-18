from __future__ import annotations

import argparse

from rich.console import Console

from .config import get_settings
from .pipeline import configure_logging, run_sync


def main() -> None:
    parser = argparse.ArgumentParser(prog="release-radar")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="Busca, analisa e publica novos lancamentos")
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        return

    configure_logging(verbose=args.verbose)
    stats = run_sync(get_settings(), limit=args.limit, dry_run=args.dry_run)
    Console().print(
        {
            "discovered": stats.discovered,
            "reserved": stats.reserved,
            "analyzed": stats.analyzed,
            "posted": stats.posted,
            "skipped_existing": stats.skipped_existing,
            "skipped_not_release": stats.skipped_not_release,
            "failed": stats.failed,
        }
    )
