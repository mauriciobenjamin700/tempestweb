# Production Dockerfile for a tempestweb Mode B (server) app.
#
# Build context = your tempestweb project root (the dir with app.py +
# tempestweb.toml). One uvicorn worker per container — WS/SSE session state is
# in-process, so scale horizontally with replicas behind a sticky-session load
# balancer (see docs/deploy.md), not with --workers.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the framework with the server extra. Pin the version in production.
RUN pip install "tempestweb[server]"

# Copy the project (app.py, tempestweb.toml, any modules/assets).
COPY . .

# The host binds 0.0.0.0 so the container is reachable; the reverse proxy
# terminates TLS and forwards to it (see examples/deploy/nginx.conf).
EXPOSE 8000

# Liveness/readiness at GET /health (Track S — S4).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["tempestweb", "run", "--mode", "server", "--host", "0.0.0.0", "--port", "8000"]
