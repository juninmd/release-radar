"""API local de demonstração para o app desktop, com dados fictícios.

Sobe um PostgreSQL efêmero (pgserver), semeia alguns lançamentos e serve as
rotas do painel em http://127.0.0.1:8765, para testar o app desktop de ponta a
ponta sem cluster, sem fontes externas e sem Telegram.

Uso (da raiz do repositório):

    uv run --with pgserver python desktop/scripts/local_api.py

Depois aponte o app em Ajustes → Conexão e app para http://127.0.0.1:8765.

As miniaturas apontam para picsum.photos só para exercitar o carregamento de
imagem; sem internet o cartão cai no marcador de radar.
"""

from __future__ import annotations

import logging
import tempfile
import threading
import time
from pathlib import Path

import pgserver

from release_radar.analyzer import analysis_from_json
from release_radar.db import get_connection, init_db, mark_posted, reserve_candidate, save_analysis
from release_radar.models import ReleaseCandidate
from release_radar.web import create_server

PORT = 8765

FIXTURES = [
    {
        "source": "youtube",
        "url": "https://youtu.be/nessie-duna",
        "title": "Trailer oficial de Duna: Parte Três",
        "channel": "KinoCheck",
        "category": "movies",
        "thumbnail": "https://picsum.photos/seed/duna-tres/320/180",
        "analysis": {
            "title": "Duna: Parte Três",
            "synopsis": "A conclusão da saga de Paul Atreides no deserto de Arrakis.",
            "release_status": "upcoming",
            "release_date": "2027-03-19",
            "why_it_matters": "Franquia premiada e um dos trailers mais aguardados do ano.",
            "platforms": ["Cinema"],
        },
    },
    {
        "source": "youtube",
        "url": "https://youtu.be/nessie-round6",
        "thumbnail": "https://picsum.photos/seed/round6-t3/320/180",
        "title": "Teaser da nova temporada de Round 6",
        "channel": "Netflix Brasil",
        "category": "series",
        "analysis": {
            "title": "Round 6 · Temporada 3",
            "synopsis": "Os sobreviventes encaram a rodada final dos jogos coreanos.",
            "release_status": "upcoming",
            "release_date": "2027-06-27",
            "platforms": ["Netflix"],
        },
    },
    {
        "source": "rss",
        "url": "https://blog.playstation.com/demo-astro",
        "thumbnail": "https://picsum.photos/seed/astro-world/320/180",
        "title": "Anúncio: novo jogo do Astro chega em 2027",
        "channel": "PlayStation Blog",
        "category": "games",
        "analysis": {
            "title": "Astro World",
            "synopsis": "Nova aventura 3D do mascote do PlayStation, com coop local.",
            "release_status": "upcoming",
            "release_date": "2027-02-11",
            "platforms": ["PS5"],
        },
    },
    {
        "source": "steam",
        "url": "https://store.steampowered.com/app/999999/demo/",
        "thumbnail": "https://picsum.photos/seed/silksong/320/180",
        "title": "Steam · Em breve: Hollow Knight: Silksong",
        "channel": "Steam",
        "category": "games",
        "analysis": {
            "title": "Hollow Knight: Silksong",
            "synopsis": "Hornet assume o papel principal nesta sequência metroidvania.",
            "release_status": "upcoming",
            "release_date": "2027-01-15",
            "platforms": ["PC", "Switch"],
        },
    },
    {
        "source": "kitsu",
        "url": "https://kitsu.io/anime/demo-frieren",
        "thumbnail": "https://picsum.photos/seed/frieren-t2/320/180",
        "title": "Kitsu · Upcoming: Frieren 2ª temporada",
        "channel": "Kitsu",
        "category": "anime",
        "analysis": {
            "title": "Frieren e a Jornada para o Além · T2",
            "synopsis": "A elfa maga segue colecionando memórias e magias pelo continente.",
            "release_status": "upcoming",
            "release_date": "2027-10-03",
            "platforms": ["Crunchyroll"],
        },
    },
    {
        "source": "rss",
        "url": "https://collider.com/demo-arcane",
        "thumbnail": "https://picsum.photos/seed/arcane-filme/320/180",
        "title": "Arcane encerra com filme animado, diz produtora",
        "channel": "Collider",
        "category": "series",
        "analysis": {
            "title": "Arcane · O Filme",
            "synopsis": "O desfecho da história de Vi e Jinx chega aos cinemas.",
            "release_status": "released",
            "release_date": "2026-09-01",
            "why_it_matters": "Já disponível — bom para conferir esse estado no painel.",
            "platforms": ["Cinema"],
        },
    },
]


def seed(dsn: str) -> int:
    """Semeia uma vez; repetir a execução não duplica (ON CONFLICT DO NOTHING)."""
    init_db(dsn)
    conn = get_connection(dsn)
    created = 0
    try:
        for index, fixture in enumerate(FIXTURES, start=1):
            candidate = ReleaseCandidate(
                external_id=f"{fixture['source']}:demo{index}",
                title=fixture["title"],
                url=fixture["url"],
                channel=fixture["channel"],
                category=fixture["category"],
                duration=0,
                upload_date=None,
                thumbnail=fixture["thumbnail"],
                source=fixture["source"],
            )
            if not reserve_candidate(conn, candidate, f"hash-demo-{index}"):
                continue
            analysis = analysis_from_json(
                candidate, {"is_release_signal": True, **fixture["analysis"]}
            )
            save_analysis(conn, candidate, "", analysis)
            mark_posted(conn, candidate.external_id)
            created += 1
    finally:
        conn.close()
    return created


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data_dir = Path(tempfile.gettempdir()) / "release-radar-demo-pg"
    server_pg = pgserver.get_server(data_dir)
    created = seed(server_pg.get_uri())

    httpd = create_server(server_pg.get_uri(), host="127.0.0.1", port=PORT)
    print(f"{created} itens fictícios criados", flush=True)
    print(f"API de demonstração pronta em http://127.0.0.1:{PORT}", flush=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        httpd.shutdown()
        server_pg.cleanup()


if __name__ == "__main__":
    main()
