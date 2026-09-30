from psycopg2.extensions import parse_dsn

from release_radar.config import Settings


def test_postgres_dsn_preserves_special_characters_and_socket_paths() -> None:
    settings = Settings(
        _env_file=None,
        postgres_host="/tmp/example-postgres",
        postgres_db="radar demo",
        postgres_user="demo user",
        postgres_password="demo@secret:' \\",
    )
    result = parse_dsn(settings.postgres_dsn)
    assert result["host"] == settings.postgres_host
    assert result["dbname"] == settings.postgres_db
    assert result["user"] == settings.postgres_user
    assert result["password"] == settings.postgres_password
