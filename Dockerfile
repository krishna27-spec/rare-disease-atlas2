# One small image that serves both the API and the website.
# Works as-is on Render, Fly.io, Railway, Hugging Face Spaces (Docker) or any host that runs a container.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app

# dependencies first, so they are cached between builds
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# the code, the built graph and the built site (no raw downloads, no caches)
COPY src ./src
COPY data/graph ./data/graph
COPY data/manual ./data/manual
COPY web/dist ./web/dist

# the host tells us which port to listen on; 8000 if it does not
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uv run --no-sync uvicorn src.atlas.server:app --host 0.0.0.0 --port ${PORT}"]
