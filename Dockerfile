# =============================================================================
# Nemawashi Enterprise Multi-Agent Governance Engine
# Production Container Image (CPython 3.12-slim + uv)
# Optimized for AWS EC2 Free Tier (t2.micro / t3.micro, 1 GiB RAM)
# =============================================================================

FROM python:3.12-slim

# Set environment flags for container performance and clean execution
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/usr/local/bin:$PATH"

WORKDIR /app

# Install high-performance uv package installer from official binary image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create isolated non-root system user and pre-create state directories
RUN groupadd -g 10001 nemawashi && \
    useradd -u 10001 -g nemawashi -s /bin/bash -m nemawashi && \
    mkdir -p /app/audit_logs /app/cache /app/storage/suspended_states && \
    chown -R nemawashi:nemawashi /app

# Copy dependency manifests and project metadata
COPY --chown=nemawashi:nemawashi requirements.txt pyproject.toml /app/

# Install dependencies system-wide using uv
RUN uv pip install --system --no-cache -r requirements.txt

# Copy source tree, prompts, tests, and configuration
COPY --chown=nemawashi:nemawashi src/ /app/src/
COPY --chown=nemawashi:nemawashi prompts/ /app/prompts/
COPY --chown=nemawashi:nemawashi tests/ /app/tests/

# Install the nemawashi package in editable/system mode
RUN uv pip install --system --no-cache --no-deps -e .

# Drop privileges to non-root user
USER nemawashi

# Expose gateway port
EXPOSE 8000

# Native healthcheck using standard library urllib (zero external binary dependencies)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')"

# Default entrypoint starts non-blocking FastAPI Ingress Gateway
CMD ["uvicorn", "nemawashi.main:app", "--host", "0.0.0.0", "--port", "8000"]
