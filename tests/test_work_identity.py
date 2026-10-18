from __future__ import annotations

import pytest

from release_radar.work_identity import classify_video_title, work_key


@pytest.mark.parametrize(
    "title",
    [
        "Avengers: Doomsday | Official Trailer",
        "Official Trailer #2 | Avengers: Doomsday",
        "AVENGERS: DOOMSDAY - Final Trailer",
        "Avengers: Doomsday | Teaser Trailer | Marvel Studios",
        "Avengers: Doomsday – Novo Trailer Oficial Dublado",
        "Avengers: Doomsday (TV Spot)",
    ],
)
def test_trailer_variants_of_one_work_share_a_key(title: str) -> None:
    assert work_key(title, "movies", "Marvel Studios") == "movies:avengers doomsday"


def test_sequels_and_other_categories_stay_distinct() -> None:
    assert work_key("Dune | Official Trailer", "movies") != work_key(
        "Dune: Part Two | Official Trailer", "movies"
    )
    assert work_key("Halloween | Official Trailer", "movies") != work_key(
        "Halloween | Official Trailer", "games"
    )


def test_titles_with_modifier_words_keep_them_outside_trailer_phrases() -> None:
    assert work_key("Final Fantasy VII Rebirth | Official Trailer", "games") == (
        "games:final fantasy vii rebirth"
    )
    assert work_key("New Super Mario Bros. Trailer", "games") == "games:new super mario bros"


def test_title_with_nothing_but_a_trailer_phrase_has_no_identity() -> None:
    # Sem obra identificavel nao ha como deduplicar: chave vazia nunca casa com nada.
    assert work_key("Official Trailer", "movies") == ""


def test_non_latin_titles_keep_their_own_identity() -> None:
    first = work_key("『呪術廻戦』ティザーPV", "anime")
    second = work_key("『葬送のフリーレン』ティザーPV", "anime")
    assert first != second
    assert first.startswith("anime:") and len(first) > len("anime:")


@pytest.mark.parametrize(
    "title",
    [
        "Dune: Part Three | Official Movie Trailer",
        "Dune: Part Three | Official Game Trailer",
        "Dune: Part Three Movie Trailer #2",
    ],
)
def test_generic_descriptors_next_to_trailer_are_noise(title: str) -> None:
    assert work_key(title, "movies").endswith("dune part three")


@pytest.mark.parametrize(
    "title",
    [
        "Interview with the Vampire | Season 3 Official Trailer",
        "Ranking of Kings Season 2 | Official Trailer",
        "Scenes from a Marriage | Trailer",
        "Short Circuit | Trailer",
        "Breakdown | Official Trailer",
    ],
)
def test_commentary_words_inside_a_real_title_do_not_make_a_clip(title: str) -> None:
    assert classify_video_title(title) == "trailer"


@pytest.mark.parametrize(
    "title",
    ["Dune Official Trailer Breakdown", "Dune Trailer Interview", "Dune Trailer Review"],
)
def test_commentary_attached_to_the_trailer_is_still_a_clip(title: str) -> None:
    assert classify_video_title(title) == "clip"


@pytest.mark.parametrize(
    "title",
    [
        "Movie Clip - The Chase Scene",
        "Avengers: Doomsday | Official Clip",
        "Behind the Scenes of Dune",
        "Dune Part Two: Featurette",
        "Avengers Doomsday Official Trailer REACTION",
        "Trailer Breakdown: every easter egg explained",
        "Cena exclusiva de Duna | Netflix",
        "Entrevista com o elenco de Duna",
        "GTA 6 Trailer Review",
    ],
)
def test_clips_and_commentary_are_not_trailers(title: str) -> None:
    assert classify_video_title(title) == "clip"


@pytest.mark.parametrize(
    "title",
    [
        "Avengers: Doomsday | Official Trailer",
        "Stranger Things 5 | Teaser",
        "Hollow Knight: Silksong - Announcement Trailer",
        "Duna: Parte Dois | Trailer Oficial",
        "Official Trailer 2 | Scenes of Tomorrow",
    ],
)
def test_trailers_are_recognised(title: str) -> None:
    assert classify_video_title(title) == "trailer"


def test_untitled_marketing_is_left_to_the_analysis() -> None:
    assert classify_video_title("Dune: Part Three") == "unknown"
