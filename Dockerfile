FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 radar \
    && useradd --system --uid 10001 --gid radar --create-home --home-dir /home/radar radar

# Versao fixa: o build de hoje precisa ser o mesmo de amanha.
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

# O .venv fica com root (somente leitura para o app); o processo roda sem privilegios.
USER radar

# Uma rodada do bot. O painel usa o mesmo image: `release-radar web --host 0.0.0.0`
# (veja docker-compose.yml, que tambem define o HEALTHCHECK do painel em /healthz).
CMD ["release-radar", "run"]
