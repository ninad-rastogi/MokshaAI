FROM python:3.14.6-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /uvx /bin/

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/moksha-venv
ENV PATH="/opt/moksha-venv/bin:$PATH"
ENV UV_LINK_MODE=copy
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install the exact production dependency graph before copying application code.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY . .

# Create runtime directories and drop root privileges.
RUN groupadd --gid 10001 moksha \
    && useradd --uid 10001 --gid moksha --create-home moksha \
    && mkdir -p data/docs data/embeddings \
    && chown -R moksha:moksha /app

USER moksha

EXPOSE 8000

# Default command (overridden in docker-compose)
CMD ["uvicorn", "moksha.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
