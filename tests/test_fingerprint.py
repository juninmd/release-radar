from release_radar.fingerprint import content_hash, normalize_text


def test_normalize_text_removes_noise() -> None:
    assert normalize_text("Trailer: TESTE!!! https://x.test/a") == "trailer teste"


def test_content_hash_is_stable_for_spacing_and_case() -> None:
    left = content_hash("Novo Trailer", "Canal")
    right = content_hash(" novo   trailer ", "canal")
    assert left == right
