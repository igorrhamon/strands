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

# Copy application code (avoid --chown for broader Docker compatibility)
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY templates/ ./templates/
COPY static/ ./static/
COPY server_fastapi.py .
COPY main.py .

# Ensure correct ownership for non-root user
RUN chown -R strands:strands /app || true

# Set environment variables
ENV PATH=/home/strands/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Switch to non-root user
USER strands

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose ports
EXPOSE 8000 8001

# Run the application
CMD ["python", "-m", "uvicorn", "server_fastapi:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4"]
