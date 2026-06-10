# syntax=docker/dockerfile:1.7

# ---- Stage 1: build the React frontend --------------------------------------
FROM node:20-alpine AS frontend-build
WORKDIR /build

# Cache deps separately from source so most rebuilds skip npm install
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Path prefix the bundle should assume — must match the backend's URL_PREFIX
# at runtime. Passed via `docker compose build --build-arg VITE_URL_PREFIX=...`
# or the `args:` block in docker-compose.yml.
ARG VITE_URL_PREFIX=""
ENV VITE_URL_PREFIX=${VITE_URL_PREFIX}

COPY frontend/ ./
RUN npm run build


# ---- Stage 2: refresh the SDE skill catalogue --------------------------------
# The BuildKit cache mount persists the processed artifact across builds on
# this host, so the ~80 MB download only happens when CCP ships a new SDE
# build (or the cache is cold). Nothing SDE-related is committed to git.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS sde
WORKDIR /sde
RUN uv pip install --system httpx
COPY scripts/refresh_sde.py ./
RUN --mount=type=cache,target=/sde-cache,id=nvskills-sde \
    python refresh_sde.py --cache /sde-cache --out /out/sde


# ---- Stage 3: Python runtime --------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime
WORKDIR /app

# Install Python deps first so the layer is cached unless deps change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code + committed demo fixtures + access-gate config example
COPY app/ ./app/
COPY data_demo/ ./data_demo/
COPY config.toml ./

# Artifacts from the earlier stages
COPY --from=sde /out/sde ./var/sde/
COPY --from=frontend-build /build/dist ./frontend/dist/

# Run unprivileged.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app/var
EXPOSE 8083
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
# Honor $PORT if the host platform injects one; default 8083.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8083}"]
