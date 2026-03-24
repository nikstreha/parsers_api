FROM python:3.14.2-trixie

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libxt6 \
    libx11-xcb1 \
    libxcb1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

COPY pyproject.toml uv.lock* .

RUN uv sync --frozen --no-cache

ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

RUN uv run camoufox fetch

COPY . .

CMD ["uv", "run", "src/cli.py", "--workers", "1"]
