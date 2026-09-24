from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    youtube_sources: str = (
        # filmes
        "movies|@RottenTomatoesTRAILERS,"
        "movies|@KinoCheck,"
        "movies|@ONEMedia,"
        "movies|@A24,"
        "movies|@20thcenturystudios,"
        "movies|@UniversalPictures,"
        "movies|@warnerbros,"
        "movies|@MARVEL,"
        # series
        "series|@NetflixBrasil,"
        "series|@Netflix,"
        "series|@PrimeVideo,"
        "series|@DisneyPlus,"
        "series|@AppleTV,"
        "series|@HBOMax,"
        # jogos
        "games|@PlayStation,"
        "games|@XboxViewTV,"
        "games|@NintendoAmerica,"
        "games|@EASPORTSFC,"
        "games|@EASPORTS,"
        "games|@IGN,"
        "games|@GameSpot,"
        "games|@ubisoft,"
        "games|@Bethesda,"
        "games|@GameTrailers,"
        # animes
        "anime|@Crunchyroll,"
        "anime|@CrunchyrollDubs,"
        "anime|@TOHOanimation,"
        "anime|@AniplexUSA,"
        "anime|@netflixanime,"
        "anime|@AnimeExpo"
    )
    # Feeds RSS oficiais/editoriais (sem API key). Formato: "categoria|url".
    rss_sources: str = (
        "games|https://blog.playstation.com/feed/,"
        "games|https://news.xbox.com/en-us/feed/,"
        "games|https://store.steampowered.com/feeds/news.xml,"
        "anime|https://www.animenewsnetwork.com/all/rss.xml,"
        "movies|https://www.slashfilm.com/feed/,"
        "movies|https://collider.com/feed/,"
        "series|https://deadline.com/feed/"
    )
    rss_limit: int = 5

    # Steam: jogos "em breve" mais populares da loja (API publica, sem key).
    steam_enabled: bool = True
    steam_limit: int = 8
    steam_country: str = "br"
    steam_language: str = "portuguese"

    # Kitsu: animes anunciados, ordenados por audiencia (API publica, sem key).
    kitsu_enabled: bool = True
    kitsu_limit: int = 8

    http_timeout: float = 20.0

    source_limit: int = 10
    max_items_per_run: int = 20
    max_transcription_seconds: int = 420
    analyze_video_content: bool = True

    # Anti-bloqueio do YouTube (yt-dlp). player_client alternativo e/ou cookies.
    # Ex.: youtube_player_client="tv,mweb,web_safari";
    #      youtube_cookies_file="/secrets/yt/cookies.txt"
    youtube_player_client: str = ""
    youtube_cookies_file: str = ""

    whisper_base_url: str = "http://whisper.ai.svc.cluster.local:9000"
    whisper_timeout: float = 600.0

    llm_base_url: str = "http://litellm.ai.svc.cluster.local:4000/v1"
    llm_model: str = "cloud/auto"
    llm_api_key: str = ""
    llm_timeout: float = 120.0

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "release_radar"
    postgres_user: str = "postgres"
    postgres_password: str = ""

    data_dir: Path = Field(default=Path("/tmp/release-radar"))
    audio_dir: Path = Field(default=Path("/tmp/release-radar/audio"))

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def yt_dlp_opts(self) -> dict:
        """Opcoes extras de yt-dlp para driblar bloqueio (player_client/cookies)."""
        opts: dict = {}
        clients = [c.strip() for c in self.youtube_player_client.split(",") if c.strip()]
        if clients:
            opts["extractor_args"] = {"youtube": {"player_client": clients}}
        if self.youtube_cookies_file:
            opts["cookiefile"] = self.youtube_cookies_file
        return opts

    @property
    def parsed_sources(self) -> list[tuple[str, str]]:
        return _parse_categorized(self.youtube_sources)

    @property
    def parsed_rss_sources(self) -> list[tuple[str, str]]:
        return _parse_categorized(self.rss_sources)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def _parse_categorized(raw_value: str) -> list[tuple[str, str]]:
    """Converte "categoria|alvo,categoria|alvo" em pares; sem "|" cai em unknown."""
    sources: list[tuple[str, str]] = []
    for raw in raw_value.split(","):
        item = raw.strip()
        if not item:
            continue
        if "|" not in item:
            sources.append(("unknown", item))
            continue
        category, target = item.split("|", 1)
        sources.append((category.strip(), target.strip()))
    return sources


@lru_cache
def get_settings() -> Settings:
    return Settings()
