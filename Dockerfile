# syntax=docker/dockerfile:1
# Imagen de la API (FastAPI + uvicorn). Instala dependencias con uv.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# uv: compila bytecode y copia en vez de symlink (mejor dentro de contenedor).
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Capa de dependencias cacheable: sólo lockfile + manifest primero, así un
# cambio de código no reinstala todo.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Código de la app (lo que no aplica queda fuera vía .dockerignore).
COPY . .
# EXTRAS="local-embed" instala sentence-transformers/torch para EMBEDDING_PROVIDER=local_st
# o RERANK_PROVIDER=cross_encoder (imagen mucho más grande). Vacío = sólo `dummy`.
ARG EXTRAS=""
RUN if [ -n "$EXTRAS" ]; then uv sync --frozen --no-dev --extra "$EXTRAS"; else uv sync --frozen --no-dev; fi

EXPOSE 8000

# `db init` crea las tablas (idempotente) antes de servir, para que el primer
# `docker compose up` funcione sin pasos manuales. Luego arranca uvicorn.
# ponytail: init inline en el CMD; si el arranque necesita más pasos, mover a un entrypoint.sh
CMD ["sh", "-c", "uv run open-data-jalisco db init && uv run uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --app-dir ."]
