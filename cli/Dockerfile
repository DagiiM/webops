# WebOps CLI - Production Docker Image
# Multi-stage build for optimal security and size

FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r webops && useradd -r -g webops webops

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    nginx \
    systemd \
    && rm -rf /var/lib/apt/lists/*

# Set up application
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY webops_cli/ ./webops_cli/
COPY setup.py .
COPY README.md .
COPY pyproject.toml .

# Install the CLI package
RUN pip install -e .

# Create necessary directories
RUN mkdir -p /app/logs /app/config && \
    chown -R webops:webops /app

# Copy entrypoint script
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Switch to non-root user
USER webops

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD webops --help > /dev/null || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Run entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["webops", "--help"]