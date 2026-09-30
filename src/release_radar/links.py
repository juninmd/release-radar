from urllib.parse import urlsplit


def link_kind(url: str, source: str) -> str:
    """Classifica pelo destino para feeds com links diretos para o YouTube."""
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        host = ""
    if host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com"):
        return "video"
    return "catalog" if source in {"steam", "kitsu"} else "article"
