from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    youtube_sources: str = (
        "movies|@MovieclipsTrailers,"
        "series|@NetflixBrasil,"
        "games|@PlayStation,"
        "games|@Xbox,"
        "games|@NintendoAmerica,"
        "anime|@Crunchyroll"
    )
    source_limit: int = 6
    max_items_per_run: int = 12
    max_transcription_seconds: int = 420
    analyze_video_content: bool = True

    whisper_base_url: str = "http://whisper.ai.svc.cluster.local:9000"
    whisper_timeout: float = 600.0

    llm_base_url: str = "http://litellm.ai.svc.cluster.local:4000/v1"
    llm_model: str = "cloud/llama-8b"
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
    def parsed_sources(self) -> list[tuple[str, str]]:
        sources: list[tuple[str, str]] = []
        for raw in self.youtube_sources.split(","):
            item = raw.strip()
            if not item:
                continue
            if "|" not in item:
                sources.append(("unknown", item))
                continue
            category, channel = item.split("|", 1)
            sources.append((category.strip(), channel.strip()))
        return sources

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
