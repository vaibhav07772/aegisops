# ============================================================
# AegisOps — multi-service image (API + Streamlit UI)
# ============================================================
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: gcc for native builds, curl for health checks, tini for PID 1
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Python deps first (better layer caching — invalidated only when requirements change)
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# App code (invalidates cache only when source changes)
COPY . .

# Ensure shell entrypoint has LF endings + executable bit; create data dirs
RUN sed -i 's/\r$//' scripts/docker_entrypoint.sh && \
    chmod +x scripts/docker_entrypoint.sh && \
    mkdir -p data/raw data/metrics data/logs data/traces data/runs \
             data/models data/runbooks data/incidents data/chroma

EXPOSE 8000 8501

ENTRYPOINT ["tini", "--", "scripts/docker_entrypoint.sh"]
CMD ["api"]