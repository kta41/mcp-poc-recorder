FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# --frozen: the lockfile is the single source of truth for reproducible builds.
RUN uv sync --no-dev --frozen \
    && uv run playwright install --with-deps chromium

RUN useradd --create-home --uid 10001 recorder \
    && mkdir -p /app/build/recordings \
    && chown -R recorder:recorder /app/build /home/recorder

USER recorder

CMD ["/app/.venv/bin/poc-recorder-mcp"]
