from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from psycopg2.extensions import make_dsn
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
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
        "games|https://www.gematsu.com/feed,"
        "games|https://www.eurogamer.net/feed,"
        "games|https://www.nintendolife.com/feeds/latest,"
        "games|https://www.pushsquare.com/feeds/latest,"
        "movies|https://collider.com/feed/,"
        "movies|https://variety.com/feed/,"
        "movies|https://www.hollywoodreporter.com/feed/,"
        "series|https://deadline.com/feed/,"
        "series|https://www.whats-on-netflix.com/feed/"
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

    # AniList: animes anunciados, por popularidade (GraphQL publico, sem key).
    anilist_enabled: bool = True
    anilist_limit: int = 8

    # Jikan (MyAnimeList): proxima temporada de animes (API publica, sem key).
    jikan_enabled: bool = False
    jikan_limit: int = 8

    # TVmaze: estreias (1x01) de series em streaming nos proximos dias (sem key).
    tvmaze_enabled: bool = True
    tvmaze_limit: int = 8
    tvmaze_days: int = 14

    # Wikidata: filmes e jogos com estreia futura confirmada (SPARQL publico, sem key).
    # Desligada por padrao: o Wikimedia aplica politica anti-bot e responde 403 a alguns
    # clientes; ative com WIKIDATA_ENABLED=true e confira os logs. O limite vale por tipo.
    wikidata_enabled: bool = False
    wikidata_limit: int = 6
    wikidata_days: int = 365

    http_timeout: float = 20.0

    # "text" (legivel, padrao) ou "json" (uma linha JSON por log, para agregadores).
    log_format: str = "text"

    source_limit: int = 10
    max_items_per_run: int = 20
    max_transcription_seconds: int = 420
    analyze_video_content: bool = True

    # Anti-bloqueio do YouTube (yt-dlp). player_client alternativo e/ou cookies.
    # Ex.: youtube_player_client="tv,mweb,web_safari";
    #      youtube_cookies_file="/secrets/yt/cookies.txt"
    youtube_player_client: str = ""
    youtube_cookies_file: str = ""

    whisper_base_url: str = "http://localhost:9000"
    whisper_timeout: float = 600.0

    llm_base_url: str = "http://localhost:4000/v1"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_timeout: float = 120.0

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Protege /api/run e /api/settings quando o painel e exposto em rede.
    release_radar_api_token: str = ""
    # Escotilha explicita: permite escrita anonima mesmo fora de localhost.
    release_radar_allow_anon: bool = False
    # Hosts adicionais permitidos para o painel / rotas de escrita (separados por virgula).
    release_radar_allowed_hosts: str = ""

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "release_radar"
    postgres_user: str = "postgres"
    postgres_password: str = ""

    data_dir: Path = Field(default=Path("/tmp/release-radar"))
    audio_dir: Path = Field(default=Path("/tmp/release-radar/audio"))

    @property
    def json_logs(self) -> bool:
        return self.log_format.strip().lower() == "json"

    @property
    def postgres_dsn(self) -> str:
        return make_dsn(
            host=self.postgres_host,
            port=self.postgres_port,
            dbname=self.postgres_db,
            user=self.postgres_user,
            password=self.postgres_password,
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
