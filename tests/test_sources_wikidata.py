from __future__ import annotations

from datetime import date

import httpx

from release_radar.analyzer import fallback_analysis, source_release_date
from release_radar.sources.wikidata import fetch_wikidata

TODAY = date(2026, 10, 25)
ENTITY = "http://www.wikidata.org/entity/"
WIKI = "https://en.wikipedia.org/wiki/"
COMMONS = "http://commons.wikimedia.org/wiki/Special:FilePath/"


def uri(qid: str) -> dict:
    return {"type": "uri", "value": f"{ENTITY}{qid}"}


def shortlist(*qids: str) -> dict:
    return {"results": {"bindings": [{"item": uri(qid)} for qid in qids]}}


def row(
    qid: str,
    label: str,
    day: str,
    prec: int = 11,
    *,
    description: str = "upcoming film",
    article: str | None = None,
    image: str | None = None,
) -> dict:
    out = {
        "item": uri(qid),
        "itemLabel": {"value": label},
        "itemDescription": {"value": description},
        "date": {"value": f"{day}T00:00:00Z"},
        "prec": {"value": str(prec)},
    }
    if article:
        out["article"] = {"type": "uri", "value": WIKI + article}
    if image:
        out["image"] = {"type": "uri", "value": COMMONS + image}
    return out


def client_for(details_rows: list[dict], *qids: str) -> tuple[httpx.Client, list[str]]:
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["query"]
        queries.append(query)
        if "VALUES ?item" in query:
            return httpx.Response(200, json={"results": {"bindings": details_rows}})
        return httpx.Response(200, json=shortlist(*qids))

    return httpx.Client(transport=httpx.MockTransport(handler)), queries


def test_future_film_becomes_a_catalog_candidate() -> None:
    rows = [
        row("Q1", "Shrek 5", "2027-06-30", article="Shrek_5", image="Shrek 5.jpg"),
        # Uma data por regiao: vale a menor.
        row("Q2", "Spider Film", "2027-06-18", article="Spider_Film"),
        row("Q2", "Spider Film", "2027-06-04", article="Spider_Film"),
    ]
    client, _ = client_for(rows, "Q1", "Q2")
    with client:
        found = fetch_wikidata(client, "movies", limit=5, today=TODAY)

    assert [item.external_id for item in found] == ["wikidata:Q1", "wikidata:Q2"]
    shrek, spider = found
    assert shrek.source == "wikidata"
    assert shrek.category == "movies"
    assert shrek.title == "Shrek 5"
    assert shrek.url == "https://en.wikipedia.org/wiki/Shrek_5"
    assert shrek.channel == "Wikipedia"
    assert shrek.thumbnail == (
        "https://commons.wikimedia.org/wiki/Special:FilePath/Shrek 5.jpg?width=600"
    )
    assert source_release_date(shrek) == "2027-06-30"
    assert source_release_date(spider) == "2027-06-04"
    analysis = fallback_analysis(shrek, "")
    assert analysis.release_status == "upcoming"
    assert analysis.release_date == "2027-06-30"


def test_released_somewhere_or_imprecise_dates_are_rejected() -> None:
    rows = [
        # Ja estreou em uma regiao: nao e mais estreia futura.
        row("Q1", "Ja Estreou", "2026-05-21"),
        row("Q1", "Ja Estreou", "2027-02-01", prec=10),
        row("Q1", "Ja Estreou", "2026-12-16"),
        # Data so de ano/mes vira 1o do periodo: sem dia confirmado nao ha estreia.
        row("Q2", "So Mes", "2027-03-01", prec=10),
        row("Q3", "So Ano", "2027-01-01", prec=9),
        # Mes iniciado antes de hoje pode ja ter estreado.
        row("Q4", "Mes Corrente", "2026-10-01", prec=10),
        row("Q4", "Mes Corrente", "2026-12-25"),
        row("Q5", "Valido", "2026-12-25", article="Valido"),
    ]
    client, _ = client_for(rows, "Q1", "Q2", "Q3", "Q4", "Q5")
    with client:
        found = fetch_wikidata(client, "movies", limit=10, today=TODAY)

    assert [item.title for item in found] == ["Valido"]


def test_unlabeled_items_and_missing_article_fallbacks() -> None:
    rows = [
        row("Q1", "Q1", "2027-01-10"),  # sem rotulo em ingles: o servico devolve o proprio Q-id
        row("Q2", "Sem Artigo", "2027-01-10", image="x.jpg"),
        row("Q3", "Imagem Estranha", "2027-01-10", article="A"),
    ]
    rows[2]["image"] = {"type": "uri", "value": "http://evil.test/x.jpg"}
    client, _ = client_for(rows, "Q1", "Q2", "Q3")
    with client:
        found = fetch_wikidata(client, "games", limit=10, today=TODAY)

    assert [item.title for item in found] == ["Sem Artigo", "Imagem Estranha"]
    no_article, odd_image = found
    assert no_article.category == "games"
    assert no_article.url == "https://www.wikidata.org/wiki/Q2"
    assert no_article.channel == "Wikidata"
    assert odd_image.thumbnail is None


def test_queries_use_the_kind_filters_horizon_and_limit() -> None:
    client, queries = client_for([row("Q1", "Obra", "2027-01-10")], "Q1")
    with client:
        found = fetch_wikidata(client, "games", limit=2, days_ahead=30, today=TODAY)

    shortlist_query, details_query = queries
    assert "wd:Q7889" in shortlist_query
    assert "wd:Q11424" not in shortlist_query
    assert '"2026-10-25T00:00:00Z"' in shortlist_query
    assert '"2026-11-24T00:00:00Z"' in shortlist_query
    assert "LIMIT 6" in shortlist_query
    assert "DeprecatedRank" in details_query
    assert "wd:Q1" in details_query
    assert len(found) == 1


def test_empty_shortlist_skips_the_details_request() -> None:
    client, queries = client_for(
        [],
    )
    with client:
        assert fetch_wikidata(client, "movies", limit=3, today=TODAY) == []

    assert len(queries) == 1


def test_limit_caps_the_result_in_shortlist_order() -> None:
    rows = [row(f"Q{n}", f"Obra {n}", "2027-01-10") for n in range(1, 5)]
    client, _ = client_for(rows, "Q1", "Q2", "Q3", "Q4")
    with client:
        found = fetch_wikidata(client, "movies", limit=2, today=TODAY)

    assert [item.title for item in found] == ["Obra 1", "Obra 2"]


def test_malformed_ids_from_the_service_are_ignored() -> None:
    bad = {
        "results": {"bindings": [{"item": {"value": f"{ENTITY}Q1}} DROP"}}, {"item": uri("Q9")}]}
    }
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(request.url.params["query"])
        if "VALUES ?item" in queries[-1]:
            return httpx.Response(200, json={"results": {"bindings": []}})
        return httpx.Response(200, json=bad)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetch_wikidata(client, "movies", limit=3, today=TODAY)

    assert "DROP" not in queries[1]
    assert "wd:Q9" in queries[1]
