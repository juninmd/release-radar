from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from ..models import ReleaseCandidate
from ..resilience import with_retries

logger = logging.getLogger(__name__)

SPARQL_URL = "https://query.wikidata.org/sparql"
# O servico SPARQL e lento (varios segundos para ordenar por popularidade) e corta em 60s.
REQUEST_TIMEOUT = 40.0
# kind -> (classes P31 do Wikidata, minimo de paginas em outras linguas).
# O numero de sitelinks e o proxy de popularidade: filtra obras obscuras e rascunhos.
KINDS: dict[str, tuple[tuple[str, ...], int]] = {
    "movies": (("Q11424", "Q202866"), 10),  # filme, filme de animacao
    "games": (("Q7889",), 6),  # jogo eletronico
}
DAY_PRECISION = 11
_QID_RE = re.compile(r"^Q\d+$")
_COMMONS_FILE = "http://commons.wikimedia.org/wiki/Special:FilePath/"
_SHORTLIST_FACTOR = 3
_MAX_SHORTLIST = 60


def fetch_wikidata(
    client: httpx.Client,
    kind: str,
    limit: int,
    days_ahead: int = 365,
    today: date | None = None,
) -> list[ReleaseCandidate]:
    """Filmes ou jogos com estreia futura confirmada no Wikidata (SPARQL publico, sem key).

    Dois passos leves em vez de uma consulta so, que estoura o tempo do servico:
    1) candidatos com alguma data futura, por popularidade; 2) todas as datas deles.
    O Wikidata guarda uma data por regiao; o item so entra se NENHUMA data (de qualquer
    precisao) ja passou e ao menos uma tem precisao de dia. Assim "lancado na Espanha
    em maio" ou "2027" (que vira 1o de janeiro) nunca viram uma estreia futura falsa.
    """
    classes, min_links = KINDS[kind]
    today = today or datetime.now(UTC).date()
    horizon = today + timedelta(days=days_ahead)
    qids = _shortlist(client, classes, min_links, today, horizon, limit)
    if not qids:
        return []
    rows = _query(client, _details_query(qids))
    works = _group(rows, today)
    candidates: list[ReleaseCandidate] = []
    for qid in qids:
        work = works.get(qid)
        if work is not None:
            candidates.append(_to_candidate(qid, work, kind, today))
    return candidates[:limit]


def _shortlist(
    client: httpx.Client,
    classes: tuple[str, ...],
    min_links: int,
    today: date,
    horizon: date,
    limit: int,
) -> list[str]:
    values = " ".join(f"wd:{item}" for item in classes)
    query = f"""
SELECT DISTINCT ?item ?links WHERE {{
  VALUES ?class {{ {values} }}
  ?item wdt:P31 ?class; wdt:P577 ?date; wikibase:sitelinks ?links .
  FILTER(?date > "{today.isoformat()}T00:00:00Z"^^xsd:dateTime
         && ?date < "{horizon.isoformat()}T00:00:00Z"^^xsd:dateTime
         && ?links >= {int(min_links)})
}} ORDER BY DESC(?links) LIMIT {min(max(limit * _SHORTLIST_FACTOR, 1), _MAX_SHORTLIST)}
"""
    qids: list[str] = []
    for row in _query(client, query):
        qid = _qid(row.get("item"))
        if qid and qid not in qids:
            qids.append(qid)
    return qids


def _details_query(qids: list[str]) -> str:
    values = " ".join(f"wd:{qid}" for qid in qids)
    return f"""
SELECT ?item ?itemLabel ?itemDescription ?date ?prec ?article ?image WHERE {{
  VALUES ?item {{ {values} }}
  ?item p:P577 ?statement .
  ?statement wikibase:rank ?rank; psv:P577 ?node .
  FILTER(?rank != wikibase:DeprecatedRank)
  ?node wikibase:timeValue ?date; wikibase:timePrecision ?prec .
  OPTIONAL {{ ?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/> }}
  OPTIONAL {{ ?item wdt:P18 ?image }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def _query(client: httpx.Client, query: str) -> list[dict[str, Any]]:
    def call() -> dict[str, Any]:
        response = client.get(
            SPARQL_URL,
            params={"query": query, "format": "json"},
            headers={"Accept": "application/sparql-results+json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    payload = with_retries(call, attempts=2, label="Wikidata SPARQL")
    return list((payload.get("results") or {}).get("bindings") or [])


def _value(row: dict[str, Any], key: str) -> str:
    return str((row.get(key) or {}).get("value") or "")


def _qid(binding: Any) -> str:
    uri = str((binding or {}).get("value") or "")
    qid = uri.rsplit("/", 1)[-1]
    return qid if _QID_RE.match(qid) else ""


def _day(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _group(rows: list[dict[str, Any]], today: date) -> dict[str, dict[str, Any]]:
    """Junta as linhas (uma por data) por obra e descarta o que nao e estreia futura."""
    raw: dict[str, dict[str, Any]] = {}
    for row in rows:
        qid = _qid(row.get("item"))
        released = _day(_value(row, "date"))
        if not qid or released is None:
            continue
        work = raw.setdefault(
            qid,
            {"dates": [], "all": [], "title": "", "description": "", "article": "", "image": ""},
        )
        work["all"].append(released)
        if _value(row, "prec").isdigit() and int(_value(row, "prec")) >= DAY_PRECISION:
            work["dates"].append(released)
        work["title"] = work["title"] or _value(row, "itemLabel")
        work["description"] = work["description"] or _value(row, "itemDescription")
        work["article"] = work["article"] or _value(row, "article")
        work["image"] = work["image"] or _value(row, "image")
    return {
        qid: work
        for qid, work in raw.items()
        if work["dates"]
        and min(work["all"]) > today
        and work["title"]
        and not _QID_RE.match(work["title"])
    }


def _thumbnail(image: str) -> str | None:
    if not image.startswith(_COMMONS_FILE):
        return None
    return (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        + image[len(_COMMONS_FILE) :]
        + ("?width=600")
    )


def _to_candidate(qid: str, work: dict[str, Any], kind: str, today: date) -> ReleaseCandidate:
    first = min(work["dates"]).isoformat()
    article = work["article"]
    lines = [
        work["description"],
        f"Estreia prevista: {first}",
        "Fonte: Wikidata (menor data entre as regioes com dia confirmado)",
    ]
    return ReleaseCandidate(
        external_id=f"wikidata:{qid}",
        title=work["title"],
        url=article or f"https://www.wikidata.org/wiki/{qid}",
        channel="Wikipedia" if article else "Wikidata",
        category=kind,
        duration=0,
        upload_date=today.strftime("%Y%m%d"),
        thumbnail=_thumbnail(work["image"]),
        description="\n".join(line for line in lines if line),
        source="wikidata",
    )
