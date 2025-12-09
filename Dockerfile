FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=300
ENV PIP_NO_CACHE_DIR=0
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV UVENV=/app/.venv
ENV UV_HTTP_TIMEOUT=600
ENV UV_HTTP_RETRIES=5

RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    ca-certificates \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY uv.lock pyproject.toml README.md /app/

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/app/.cache/uv \
    uv sync --frozen

COPY src/ /app/
ENV VIRTUAL_ENV=${UVENV}
ENV PATH="${UVENV}/bin:${PATH}"
RUN --mount=type=cache,target=/root/.cache/pip \
    uv pip install -e .

VOLUME ["/app/data"]
EXPOSE 8080

# If webhook_endpoint.py exports FastAPI instance named `app`
CMD ["uvicorn", "ai_companion.interfaces.whatsapp.webhook_endpoint:app", "--host", "0.0.0.0", "--port", "8080"]
