# Multi-stage build for Strands Agent System

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 strands

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/strands/.local

# Copy application code
COPY --chown=strands:strands src/ ./src/
COPY --chown=strands:strands swarm_intelligence/ ./swarm_intelligence/
COPY --chown=strands:strands semantica/ ./semantica/
COPY --chown=strands:strands scripts/ ./scripts/
COPY --chown=strands:strands static/ ./static/
COPY --chown=strands:strands templates/ ./templates/

# Copy top-level entrypoints
COPY --chown=strands:strands server_fastapi.py ./server_fastapi.py
COPY --chown=strands:strands main.py ./main.py

# Ensure Python can import modules from /app/src, /app and other internal packages
ENV PYTHONPATH=/app:/app/src:/app/semantica:$PYTHONPATH

# Set environment variables
ENV PATH=/home/strands/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Switch to non-root user
USER strands

# Health check (main.py FastAPI listener)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/health || exit 1

# Expose ports
EXPOSE 8080 8000 8001

# Run default entrypoint for Alertmanager webhook listener
CMD ["python", "main.py"]
